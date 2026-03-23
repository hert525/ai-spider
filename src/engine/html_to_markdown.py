"""HTML to Markdown converter — zero external dependencies.

Produces clean, LLM-friendly Markdown from raw HTML.
Handles: headings, lists, links, images, tables, code blocks, bold/italic, blockquotes.
Strips: scripts, styles, nav, footer, ads.
"""
from __future__ import annotations

import re
import html as html_mod
from urllib.parse import urljoin


# Tags to completely remove (including content)
STRIP_TAGS = {"script", "style", "noscript", "svg", "iframe", "nav", "footer",
              "header", "aside", "form", "button", "input", "select", "textarea",
              "head", "title"}

# Block-level tags that get newlines
BLOCK_TAGS = {"div", "p", "section", "article", "main", "h1", "h2", "h3",
              "h4", "h5", "h6", "ul", "ol", "li", "blockquote", "pre",
              "table", "tr", "td", "th", "thead", "tbody", "figure",
              "figcaption", "dl", "dt", "dd", "hr", "br"}


def html_to_markdown(html_str: str, base_url: str = "") -> str:
    """Convert HTML string to clean Markdown.

    Args:
        html_str: Raw HTML content
        base_url: Base URL for resolving relative links

    Returns:
        Clean Markdown string
    """
    if not html_str:
        return ""

    # 1. Extract <title> before stripping
    title_match = re.search(r'<title[^>]*>(.*?)</title>', html_str, re.DOTALL | re.IGNORECASE)
    title = html_mod.unescape(title_match.group(1).strip()) if title_match else ""

    # 2. Remove strip tags and their content
    for tag in STRIP_TAGS:
        html_str = re.sub(
            rf'<{tag}[^>]*>.*?</{tag}>',
            '', html_str, flags=re.DOTALL | re.IGNORECASE
        )
    # Self-closing variants
    html_str = re.sub(r'<(script|style|noscript|svg|iframe)[^>]*/>', '', html_str, flags=re.IGNORECASE)

    # Remove HTML comments
    html_str = re.sub(r'<!--.*?-->', '', html_str, flags=re.DOTALL)

    # 3. Try to extract main content area
    main_content = html_str
    for selector in [r'<main[^>]*>(.*?)</main>',
                     r'<article[^>]*>(.*?)</article>',
                     r'<div[^>]*(?:id|class)="[^"]*(?:content|main|article|post)[^"]*"[^>]*>(.*?)</div>']:
        match = re.search(selector, html_str, re.DOTALL | re.IGNORECASE)
        if match and len(match.group(1)) > 200:
            main_content = match.group(1)
            break

    # 4. Process elements
    md = main_content

    # Headings
    for level in range(1, 7):
        prefix = "#" * level
        md = re.sub(
            rf'<h{level}[^>]*>(.*?)</h{level}>',
            lambda m: f"\n\n{prefix} {_clean_inline(m.group(1))}\n\n",
            md, flags=re.DOTALL | re.IGNORECASE
        )

    # Pre/code blocks (must be before inline code/bold to avoid interference)
    def _code_block(m):
        code = _strip_tags(m.group(1))
        code = html_mod.unescape(code)
        # Try to detect language from class
        lang_match = re.search(r'class="[^"]*(?:language-|lang-)(\w+)', m.group(0))
        lang = lang_match.group(1) if lang_match else ""
        return f"\n\n```{lang}\n{code.strip()}\n```\n\n"

    md = re.sub(r'<pre[^>]*>(.*?)</pre>', _code_block, md, flags=re.DOTALL | re.IGNORECASE)

    # Code (inline) — after pre blocks
    md = re.sub(r'<code[^>]*>(.*?)</code>', r'`\1`', md, flags=re.DOTALL | re.IGNORECASE)

    # Bold — use word boundary to avoid matching <body>, <br> etc.
    md = re.sub(r'<strong[^>]*>(.*?)</strong>', r'**\1**', md, flags=re.DOTALL | re.IGNORECASE)
    md = re.sub(r'<b(?:\s[^>]*)?>([^<]*(?:<(?!/b>)[^<]*)*)</b>', r'**\1**', md, flags=re.DOTALL | re.IGNORECASE)

    # Italic — avoid matching <img>, <input> etc.
    md = re.sub(r'<em[^>]*>(.*?)</em>', r'*\1*', md, flags=re.DOTALL | re.IGNORECASE)
    md = re.sub(r'<i(?:\s[^>]*)?>([^<]*(?:<(?!/i>)[^<]*)*)</i>', r'*\1*', md, flags=re.DOTALL | re.IGNORECASE)

    # Images
    def _img(m):
        attrs = m.group(0)
        src = _get_attr(attrs, "src") or _get_attr(attrs, "data-src")
        alt = _get_attr(attrs, "alt") or ""
        if not src:
            return ""
        if base_url:
            src = urljoin(base_url, src)
        return f"![{alt}]({src})"

    md = re.sub(r'<img[^>]*/?>', _img, md, flags=re.IGNORECASE)

    # Links
    def _link(m):
        href = _get_attr(m.group(1), "href")
        text = _clean_inline(m.group(2))
        if not href or href.startswith("javascript:"):
            return text
        if base_url:
            href = urljoin(base_url, href)
        return f"[{text}]({href})" if text else href

    md = re.sub(r'<a([^>]*)>(.*?)</a>', _link, md, flags=re.DOTALL | re.IGNORECASE)

    # Blockquotes
    def _blockquote(m):
        content = _clean_inline(m.group(1))
        lines = content.split('\n')
        quoted = '\n'.join(f'> {line}' for line in lines)
        return f"\n\n{quoted}\n\n"

    md = re.sub(r'<blockquote[^>]*>(.*?)</blockquote>', _blockquote, md, flags=re.DOTALL | re.IGNORECASE)

    # Tables
    md = _convert_tables(md)

    # Lists
    md = _convert_lists(md)

    # Horizontal rules
    md = re.sub(r'<hr[^>]*/?>',  '\n\n---\n\n', md, flags=re.IGNORECASE)

    # Line breaks
    md = re.sub(r'<br[^>]*/?>',  '\n', md, flags=re.IGNORECASE)

    # Paragraphs
    md = re.sub(r'<p[^>]*>(.*?)</p>', lambda m: f"\n\n{_clean_inline(m.group(1))}\n\n",
                md, flags=re.DOTALL | re.IGNORECASE)

    # Divs → newlines
    md = re.sub(r'</?div[^>]*>', '\n', md, flags=re.IGNORECASE)

    # Strip remaining tags
    md = _strip_tags(md)

    # Decode HTML entities
    md = html_mod.unescape(md)

    # Clean up whitespace
    md = re.sub(r'\n{3,}', '\n\n', md)
    md = re.sub(r' {2,}', ' ', md)
    md = md.strip()

    # Add title only if no h1 exists in content
    if title and "# " not in md[:200]:
        md = f"# {title}\n\n{md}"

    return md


def _strip_tags(text: str) -> str:
    """Remove all HTML tags."""
    return re.sub(r'<[^>]+>', '', text)


def _clean_inline(text: str) -> str:
    """Clean inline text: strip tags, collapse whitespace."""
    text = _strip_tags(text)
    text = html_mod.unescape(text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def _get_attr(tag_str: str, attr: str) -> str:
    """Extract attribute value from tag string."""
    match = re.search(rf'{attr}\s*=\s*["\']([^"\']*)["\']', tag_str)
    return match.group(1) if match else ""


def _convert_tables(md: str) -> str:
    """Convert HTML tables to Markdown tables."""
    def _table(m):
        table_html = m.group(0)
        rows = re.findall(r'<tr[^>]*>(.*?)</tr>', table_html, re.DOTALL | re.IGNORECASE)
        if not rows:
            return ""

        md_rows = []
        for i, row in enumerate(rows):
            cells = re.findall(r'<(?:td|th)[^>]*>(.*?)</(?:td|th)>', row, re.DOTALL | re.IGNORECASE)
            cells = [_clean_inline(c) for c in cells]
            if not cells:
                continue
            md_rows.append("| " + " | ".join(cells) + " |")
            # Add separator after header row
            if i == 0:
                md_rows.append("| " + " | ".join(["---"] * len(cells)) + " |")

        return "\n\n" + "\n".join(md_rows) + "\n\n" if md_rows else ""

    return re.sub(r'<table[^>]*>.*?</table>', _table, md, flags=re.DOTALL | re.IGNORECASE)


def _convert_lists(md: str) -> str:
    """Convert HTML lists to Markdown lists."""
    # Unordered lists
    def _ul(m):
        items = re.findall(r'<li[^>]*>(.*?)</li>', m.group(1), re.DOTALL | re.IGNORECASE)
        lines = [f"- {_clean_inline(item)}" for item in items]
        return "\n\n" + "\n".join(lines) + "\n\n"

    md = re.sub(r'<ul[^>]*>(.*?)</ul>', _ul, md, flags=re.DOTALL | re.IGNORECASE)

    # Ordered lists
    def _ol(m):
        items = re.findall(r'<li[^>]*>(.*?)</li>', m.group(1), re.DOTALL | re.IGNORECASE)
        lines = [f"{i+1}. {_clean_inline(item)}" for i, item in enumerate(items)]
        return "\n\n" + "\n".join(lines) + "\n\n"

    md = re.sub(r'<ol[^>]*>(.*?)</ol>', _ol, md, flags=re.DOTALL | re.IGNORECASE)

    return md
