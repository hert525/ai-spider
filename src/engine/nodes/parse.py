"""ParseNode - Clean HTML into structured text/markdown."""
import re
from .base import BaseNode


class ParseNode(BaseNode):
    """Parse raw HTML to clean text and extract links."""

    def __init__(self, output_format: str = "text"):
        super().__init__("ParseNode")
        self.output_format = output_format  # "text", "markdown", "html"

    async def execute(self, state: dict) -> dict:
        raw_html = state.get("raw_html", "")
        if not raw_html:
            raise ValueError("No raw_html in state")

        from parsel import Selector
        sel = Selector(text=raw_html)

        # Remove script, style, nav, footer
        for tag in ["script", "style", "nav", "footer", "header", "noscript", "svg"]:
            for el in sel.css(tag):
                pass  # parsel doesn't support removal, we'll clean in text extraction

        # Extract clean text
        clean_text = self._html_to_clean_text(raw_html)
        
        # Extract links
        links = []
        for a in sel.css("a[href]"):
            href = a.attrib.get("href", "")
            text = a.css("::text").get("").strip()
            if href and not href.startswith(("#", "javascript:")):
                links.append({"href": href, "text": text})

        # Reduced HTML (remove scripts/styles but keep structure)
        reduced_html = self._reduce_html(raw_html)

        state["clean_text"] = clean_text
        state["links"] = links
        state["reduced_html"] = reduced_html

        # Markdown output
        if self.output_format == "markdown" or state.get("output_format") == "markdown":
            from src.engine.html_to_markdown import html_to_markdown
            base_url = state.get("url", "")
            state["markdown"] = html_to_markdown(raw_html, base_url=base_url)
            self.logger.info(f"Parsed: {len(clean_text)} chars text, {len(state['markdown'])} chars markdown, {len(links)} links")
        else:
            self.logger.info(f"Parsed: {len(clean_text)} chars text, {len(links)} links")
        return state

    def _html_to_clean_text(self, html: str) -> str:
        """Strip HTML to clean readable text."""
        # Remove script and style blocks
        text = re.sub(r'<(script|style|noscript|svg)[^>]*>.*?</\1>', '', html, flags=re.DOTALL | re.IGNORECASE)
        # Remove HTML tags
        text = re.sub(r'<[^>]+>', ' ', text)
        # Decode entities
        import html as html_mod
        text = html_mod.unescape(text)
        # Collapse whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        return text

    def _reduce_html(self, html: str) -> str:
        """Remove scripts/styles but keep DOM structure."""
        reduced = re.sub(r'<(script|style|noscript|svg)[^>]*>.*?</\1>', '', html, flags=re.DOTALL | re.IGNORECASE)
        # Remove comments
        reduced = re.sub(r'<!--.*?-->', '', reduced, flags=re.DOTALL)
        # Remove excessive attributes (keep id, class, href, src)
        reduced = re.sub(r'\s+(on\w+|data-\w+|aria-\w+)="[^"]*"', '', reduced)
        # Collapse whitespace in tags
        reduced = re.sub(r'>\s+<', '><', reduced)
        # Limit size
        if len(reduced) > 50000:
            reduced = reduced[:50000] + "\n<!-- truncated -->"
        return reduced
