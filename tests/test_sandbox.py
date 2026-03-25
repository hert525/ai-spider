"""Sandbox integration tests — run before every deploy."""
import asyncio
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from src.engine.sandbox import run_code_in_sandbox
from src.engine.code_sanitizer import CodeSanitizer


# ── CodeSanitizer Tests ──

class TestCodeSanitizer:
    def test_remove_asyncio_run(self):
        code = "import asyncio\nasyncio.run(main())"
        fixed, fixes = CodeSanitizer.sanitize(code)
        assert "asyncio.run" not in fixed
        assert any("asyncio" in f for f in fixes)

    def test_remove_blocked_imports(self):
        code = "import os\nimport sys\nimport json\nasync def crawl(url, config): return []"
        fixed, fixes = CodeSanitizer.sanitize(code)
        # os/sys should be commented out or replaced with pass
        for line in fixed.split("\n"):
            if line.strip().startswith("import os") or line.strip().startswith("import sys"):
                pytest.fail(f"Blocked import not removed: {line}")
        assert "import json" in fixed
        assert any("blocked" in f for f in fixes)

    def test_preserve_indentation(self):
        code = "async def crawl(url, config):\n    import sys\n    return []"
        fixed, fixes = CodeSanitizer.sanitize(code)
        # Should not cause IndentationError
        compile(fixed, "<test>", "exec")

    def test_mixed_import_keeps_safe(self):
        code = "    import io, sys, json"
        fixed, fixes = CodeSanitizer.sanitize(code)
        assert "import io" in fixed or "import json" in fixed
        # Indentation preserved
        assert fixed.strip().startswith(("import", "pass", "async"))

    def test_fix_missing_await(self):
        code = "async def crawl(url, config):\n    async with httpx.AsyncClient() as client:\n        resp = client.get(url)\n    return []"
        fixed, fixes = CodeSanitizer.sanitize(code)
        assert "await client.get" in fixed

    def test_no_double_await(self):
        code = "async def crawl(url, config):\n    resp = await client.get(url)\n    return []"
        fixed, _ = CodeSanitizer.sanitize(code)
        assert "await await" not in fixed

    def test_wrap_in_crawl(self):
        code = "async def scrape(url, config):\n    return [{'a': 1}]"
        fixed, fixes = CodeSanitizer.sanitize(code)
        assert "async def crawl" in fixed

    def test_fix_proxies_to_proxy(self):
        code = 'import httpx\nasync def crawl(url, config):\n    async with httpx.AsyncClient(proxies={"http://": "x"}) as c:\n        pass\n    return []'
        fixed, fixes = CodeSanitizer.sanitize(code)
        assert "proxy=proxy" in fixed or "proxies" not in fixed.split("httpx")[1]


# ── Sandbox Execution Tests ──

class TestSandbox:
    """Test sandbox execution with various code patterns."""

    def _run(self, code, url="https://example.com", html=""):
        return asyncio.get_event_loop().run_until_complete(
            run_code_in_sandbox(code, url, html=html)
        )

    def test_basic_crawl(self):
        code = """
async def crawl(url: str, config: dict) -> list[dict]:
    return [{"url": url, "status": "ok"}]
"""
        result = self._run(code)
        assert not result["error"], result["error"]
        assert len(result["output"]) == 1
        assert result["output"][0]["status"] == "ok"

    def test_html_injection(self):
        """Pre-rendered HTML should be returned by httpx monkey-patch."""
        code = """
import httpx
from parsel import Selector

async def crawl(url: str, config: dict) -> list[dict]:
    async with httpx.AsyncClient() as client:
        resp = await client.get(url)
        sel = Selector(text=resp.text)
        titles = sel.css("h1::text").getall()
        return [{"title": t} for t in titles]
"""
        html = "<html><body><h1>Test Title</h1></body></html>"
        result = self._run(code, html=html)
        assert not result["error"], result["error"]
        assert len(result["output"]) == 1
        assert result["output"][0]["title"] == "Test Title"

    def test_html_injection_with_query_params(self):
        """URL with query params should still match for HTML injection."""
        code = """
import httpx
from parsel import Selector

async def crawl(url: str, config: dict) -> list[dict]:
    async with httpx.AsyncClient() as client:
        resp = await client.get(url + "?page=1")
        sel = Selector(text=resp.text)
        items = sel.css("li::text").getall()
        return [{"item": i} for i in items]
"""
        html = "<html><body><ul><li>A</li><li>B</li></ul></body></html>"
        result = self._run(code, url="https://example.com/data", html=html)
        assert not result["error"], result["error"]
        assert len(result["output"]) == 2

    def test_blocked_import_rejected(self):
        code = """
import subprocess
async def crawl(url, config):
    return [{"x": 1}]
"""
        result = self._run(code)
        # Should be sanitized or blocked
        # The sanitizer removes the import, so it should still work
        # (the code just won't have subprocess available)
        assert not result.get("error") or "subprocess" in result.get("error", "")

    def test_globals_available(self):
        code = """
async def crawl(url: str, config: dict) -> list[dict]:
    g = globals()
    return [{"has_httpx": "httpx" in str(g)}]
"""
        result = self._run(code)
        assert not result["error"], result["error"]

    def test_toplevel_await(self):
        """Top-level await should not crash."""
        code = """
import asyncio
await asyncio.sleep(0)

async def crawl(url: str, config: dict) -> list[dict]:
    return [{"ok": True}]
"""
        result = self._run(code)
        assert not result["error"], result["error"]

    def test_fallback_function_name(self):
        """If no crawl() exists but main() does, it should be found."""
        code = """
async def main(url, config=None):
    return [{"found": True}]
"""
        result = self._run(code)
        assert not result["error"], result["error"]

    def test_pre_rendered_html_via_config(self):
        """Code using config.get('pre_rendered_html') should work."""
        code = """
from parsel import Selector

async def crawl(url: str, config: dict) -> list[dict]:
    pre_html = config.get("pre_rendered_html")
    if pre_html:
        sel = Selector(text=pre_html)
    else:
        import httpx
        async with httpx.AsyncClient() as c:
            resp = await c.get(url)
            sel = Selector(text=resp.text)
    return [{"name": t.strip()} for t in sel.css("td::text").getall() if t.strip()]
"""
        html = "<table><tr><td>Alice</td><td>Bob</td></tr></table>"
        result = self._run(code, html=html)
        assert not result["error"], result["error"]
        assert len(result["output"]) == 2
        assert result["output"][0]["name"] == "Alice"

    def test_json_dumps_coroutine_error(self):
        """json.dumps on a coroutine should give clear error."""
        code = """
import json

async def helper():
    return {"a": 1}

async def crawl(url: str, config: dict) -> list[dict]:
    try:
        json.dumps(helper())  # forgot await
    except TypeError as e:
        return [{"error": str(e)}]
    return []
"""
        result = self._run(code)
        assert not result["error"], result["error"]
        # Should catch the coroutine error (either our custom msg or Python's default)
        err_text = str(result["output"])
        assert "coroutine" in err_text or "await" in err_text


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
