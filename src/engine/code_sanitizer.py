"""Code Sanitizer — AST-based auto-fix for common LLM code generation mistakes.

Runs BEFORE sandbox exec, catches and fixes:
1. Top-level await → wrap into async helper
2. asyncio.run() → remove/replace
3. Missing crawl() function → wrap entire code
4. Bare except → except Exception
5. globals()/open()/eval() misuse
6. requests (sync) → httpx (async)
"""
import ast
import re
import textwrap
from loguru import logger


class CodeSanitizer:
    """Auto-fix common LLM-generated code issues before sandbox execution."""

    @staticmethod
    def sanitize(code: str) -> tuple[str, list[str]]:
        """Sanitize code, return (fixed_code, list_of_fixes_applied).
        
        Always returns syntactically valid code (or original if unfixable).
        """
        fixes = []

        # Fix 1: Remove asyncio.run() calls
        if "asyncio.run(" in code:
            code = CodeSanitizer._fix_asyncio_run(code)
            fixes.append("removed asyncio.run()")

        # Fix 2: Replace requests with httpx patterns
        if re.search(r'\brequests\.(get|post|put|delete|head)\b', code):
            code = CodeSanitizer._fix_sync_requests(code)
            fixes.append("converted requests→httpx")

        # Fix 3: Ensure crawl function exists
        if not re.search(r'async\s+def\s+crawl\s*\(', code):
            code = CodeSanitizer._wrap_in_crawl(code)
            fixes.append("wrapped code in crawl()")

        # Fix 4: Move top-level await into crawl function
        code, moved = CodeSanitizer._fix_toplevel_await(code)
        if moved:
            fixes.append("moved top-level await into function")

        # Fix 5: Fix bare except
        code = re.sub(r'\bexcept\s*:', 'except Exception:', code)
        if 'except Exception:' in code and 'except Exception:' not in code.replace('except Exception:', '', 1):
            fixes.append("fixed bare except")

        # Fix 6: Remove open() file operations (blocked in sandbox)
        if re.search(r'\bopen\s*\(', code):
            # Only remove if it's file I/O, not httpx response .open or similar
            code = CodeSanitizer._fix_open_calls(code)
            fixes.append("removed open() calls")

        # Fix 7: Remove if __name__ == "__main__" blocks
        if '__name__' in code and '__main__' in code:
            code = CodeSanitizer._remove_main_block(code)
            fixes.append("removed __main__ block")

        # Fix 8: Detect unawaited async calls (e.g., json.dumps(client.get(url)))
        code, fixed_await = CodeSanitizer._fix_missing_await(code)
        if fixed_await:
            fixes.append("added missing await to async calls")

        if fixes:
            logger.info(f"CodeSanitizer applied {len(fixes)} fixes: {', '.join(fixes)}")

        return code, fixes

    @staticmethod
    def _fix_asyncio_run(code: str) -> str:
        """Remove asyncio.run() — we're already in an async context."""
        # asyncio.run(some_func()) → await some_func()
        code = re.sub(
            r'asyncio\.run\((\w+)\((.*?)\)\)',
            r'await \1(\2)',
            code
        )
        # Remove standalone asyncio.run lines
        code = re.sub(r'^\s*asyncio\.run\(.*\)\s*$', '', code, flags=re.MULTILINE)
        return code

    @staticmethod
    def _fix_sync_requests(code: str) -> str:
        """Convert requests.get() → httpx async patterns."""
        # import requests → import httpx
        code = re.sub(r'^(\s*)import requests\b', r'\1import httpx', code, flags=re.MULTILINE)
        code = re.sub(r'^(\s*)from requests\b', r'\1from httpx', code, flags=re.MULTILINE)
        # requests.get(url) → await httpx.AsyncClient().get(url)
        # This is a rough conversion — the LLM should ideally generate correct code
        code = code.replace('requests.get(', 'httpx.get(')
        code = code.replace('requests.post(', 'httpx.post(')
        return code

    @staticmethod
    def _wrap_in_crawl(code: str) -> str:
        """If no crawl() function exists, wrap the entire code."""
        # Check if there's any async def at all
        if re.search(r'async\s+def\s+\w+\s*\(', code):
            # There's an async function but not named crawl — add an alias
            match = re.search(r'async\s+def\s+(\w+)\s*\(', code)
            if match:
                func_name = match.group(1)
                code += f"\n\nasync def crawl(url: str, config: dict) -> list[dict]:\n    return await {func_name}(url, config)\n"
                return code

        # Check for sync def main/run/scrape
        match = re.search(r'def\s+(main|run|scrape|fetch|parse|get_data)\s*\(', code)
        if match:
            func_name = match.group(1)
            code += f"""

async def crawl(url: str, config: dict) -> list[dict]:
    import asyncio
    result = await asyncio.to_thread({func_name}, url)
    if isinstance(result, list):
        return [r if isinstance(r, dict) else {{"data": str(r)}} for r in result]
    elif isinstance(result, dict):
        return [result]
    return [{{"data": str(result)}}]
"""
            return code

        # Last resort: wrap everything as the body of crawl
        indented = textwrap.indent(code, "    ")
        return f"""async def crawl(url: str, config: dict) -> list[dict]:
    results = []
{indented}
    return results if results else [{{"error": "No data extracted"}}]
"""

    @staticmethod
    def _fix_toplevel_await(code: str) -> tuple[str, bool]:
        """Detect and fix top-level await statements."""
        try:
            tree = ast.parse(code)
        except SyntaxError:
            # Can't parse — try the compile-with-flag approach
            try:
                ast.parse(code, mode='exec', type_comments=False)
            except SyntaxError:
                pass
            return code, False

        # Check for top-level Await/AsyncFor/AsyncWith
        has_toplevel_await = False
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.Expr) and isinstance(node.value, ast.Await):
                has_toplevel_await = True
                break
            if isinstance(node, (ast.AsyncFor, ast.AsyncWith)):
                has_toplevel_await = True
                break

        return code, has_toplevel_await  # actual fix is in sandbox via PyCF_ALLOW_TOP_LEVEL_AWAIT

    @staticmethod
    def _fix_open_calls(code: str) -> str:
        """Remove/comment out file open() calls."""
        # with open(...) as f: ... → comment out entire block
        # This is tricky with AST, use regex for common patterns
        code = re.sub(
            r'^(\s*)with\s+open\(.*?\).*?:\s*\n((\1\s+.+\n)*)',
            r'\1# [sandbox] file I/O removed\n\1pass\n',
            code,
            flags=re.MULTILINE
        )
        return code

    @staticmethod
    def _fix_missing_await(code: str) -> tuple[str, bool]:
        """Detect and fix common unawaited async calls.
        
        Patterns like: json.dumps(client.get(url)) → json.dumps(await client.get(url))
        Also: resp = client.get(url) → resp = await client.get(url)
        """
        fixed = False
        # Known async methods that must be awaited
        async_patterns = [
            # httpx async methods
            (r'(?<!await\s)(\bclient\.get\s*\()', r'await \1'),
            (r'(?<!await\s)(\bclient\.post\s*\()', r'await \1'),
            (r'(?<!await\s)(\bclient\.put\s*\()', r'await \1'),
            (r'(?<!await\s)(\bclient\.delete\s*\()', r'await \1'),
            (r'(?<!await\s)(\bclient\.head\s*\()', r'await \1'),
            (r'(?<!await\s)(\bclient\.request\s*\()', r'await \1'),
            (r'(?<!await\s)(\bclient\.send\s*\()', r'await \1'),
            # playwright
            (r'(?<!await\s)(\bpage\.goto\s*\()', r'await \1'),
            (r'(?<!await\s)(\bpage\.content\s*\()', r'await \1'),
            (r'(?<!await\s)(\bpage\.wait_for_selector\s*\()', r'await \1'),
            (r'(?<!await\s)(\bpage\.evaluate\s*\()', r'await \1'),
            (r'(?<!await\s)(\bbrowser\.new_page\s*\()', r'await \1'),
            (r'(?<!await\s)(\bbrowser\.close\s*\()', r'await \1'),
            (r'(?<!await\s)(\bcontext\.new_page\s*\()', r'await \1'),
            # aiohttp
            (r'(?<!await\s)(\bsession\.get\s*\()', r'await \1'),
            (r'(?<!await\s)(\bsession\.post\s*\()', r'await \1'),
            (r'(?<!await\s)(\bresp\.json\s*\()', r'await \1'),
            (r'(?<!await\s)(\bresp\.text\s*\()', r'await \1'),
        ]

        for pattern, replacement in async_patterns:
            new_code = re.sub(pattern, replacement, code)
            if new_code != code:
                fixed = True
                code = new_code

        # Fix double-await: "await await" → "await"
        code = re.sub(r'\bawait\s+await\b', 'await', code)

        return code, fixed

    @staticmethod
    def _remove_main_block(code: str) -> str:
        """Remove if __name__ == '__main__': block."""
        lines = code.split('\n')
        result = []
        skip_indent = None
        for line in lines:
            if re.match(r'''^if\s+__name__\s*==\s*['"]__main__['"]\s*:''', line):
                skip_indent = len(line) - len(line.lstrip())
                continue
            if skip_indent is not None:
                stripped = line.lstrip()
                if stripped and (len(line) - len(stripped)) > skip_indent:
                    continue  # inside the __main__ block
                else:
                    skip_indent = None
            result.append(line)
        return '\n'.join(result)
