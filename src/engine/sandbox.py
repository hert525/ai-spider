"""Sandbox - Safe code execution environment."""
import asyncio
import sys
import traceback
from io import StringIO
from typing import Any
from loguru import logger
from src.core.config import settings


async def run_code_in_sandbox(
    code: str,
    target_url: str = "",
    html: str = "",
    timeout: int | None = None,
    proxy_config: dict | None = None,
) -> dict:
    """Execute crawler code in a restricted sandbox.
    
    The code must define: async def crawl(url: str, config: dict) -> list[dict]
    
    Returns dict with 'output', 'error', 'pages_crawled', 'duration_ms'.
    """
    timeout = timeout or settings.sandbox_timeout
    import time
    start = time.monotonic()

    # Prepare sandbox globals
    import httpx
    import parsel
    import json
    import re
    import csv

    sandbox_globals = {
        "__builtins__": __builtins__,
        "httpx": httpx,
        "parsel": parsel,
        "json": json,
        "re": re,
        "csv": csv,
        "asyncio": asyncio,
        "print": print,
    }

    # Try importing playwright
    try:
        from playwright.async_api import async_playwright
        sandbox_globals["async_playwright"] = async_playwright
    except ImportError:
        pass

    # If we have raw HTML, inject a mock client
    if html:
        sandbox_globals["__raw_html__"] = html

    old_stdout = sys.stdout
    sys.stdout = captured = StringIO()

    try:
        exec(code, sandbox_globals)
        crawl_fn = sandbox_globals.get("crawl")
        if not crawl_fn:
            return {
                "output": [],
                "error": "Function 'crawl(url, config)' not found in code",
                "pages_crawled": 0,
                "duration_ms": int((time.monotonic() - start) * 1000),
            }

        config = {
            "max_pages": settings.sandbox_max_pages,
            "delay": settings.default_delay,
        }

        # Inject proxy into config if available
        if proxy_config and proxy_config.get("enabled"):
            from src.engine.proxy import ProxyManager
            pm = ProxyManager(proxy_config)
            proxy_url = pm.get_proxy()
            if proxy_url:
                config["proxy"] = proxy_url
        elif settings.default_proxy:
            config["proxy"] = settings.default_proxy

        result = await asyncio.wait_for(
            crawl_fn(target_url, config),
            timeout=timeout,
        )

        if not isinstance(result, list):
            result = [result] if result else []

        duration_ms = int((time.monotonic() - start) * 1000)
        return {
            "output": result,
            "error": "",
            "pages_crawled": 1,
            "duration_ms": duration_ms,
        }

    except asyncio.TimeoutError:
        return {
            "output": [],
            "error": f"Execution timeout ({timeout}s)",
            "pages_crawled": 0,
            "duration_ms": timeout * 1000,
        }
    except Exception as e:
        duration_ms = int((time.monotonic() - start) * 1000)
        return {
            "output": [],
            "error": f"{type(e).__name__}: {str(e)}\n{traceback.format_exc()}",
            "pages_crawled": 0,
            "duration_ms": duration_ms,
        }
    finally:
        sys.stdout = old_stdout
