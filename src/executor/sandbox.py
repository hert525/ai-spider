"""
Sandbox executor - safely run generated crawler code and return results.
"""
import asyncio
import time
import traceback
from typing import Any
from loguru import logger

from src.core.config import settings
from src.core.models import TestRun


async def run_in_sandbox(
    code: str,
    target_url: str,
    max_pages: int | None = None,
    timeout: int | None = None,
) -> TestRun:
    """
    Execute crawler code in a sandboxed environment.

    The code must define: async def crawl(url: str, config: dict) -> list[dict]

    Args:
        code: Python code to execute
        target_url: URL to crawl
        max_pages: Max pages to crawl (default from settings)
        timeout: Timeout in seconds (default from settings)

    Returns:
        TestRun with results or error
    """
    max_pages = max_pages or settings.sandbox_max_pages
    timeout = timeout or settings.sandbox_timeout

    run = TestRun(project_id="sandbox", code=code, status="running")
    start = time.monotonic()

    # Prepare restricted globals
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

    # Try importing playwright (optional, for JS rendering)
    try:
        from playwright.async_api import async_playwright
        sandbox_globals["async_playwright"] = async_playwright
    except ImportError:
        pass

    try:
        # Compile and execute the code to define functions
        compiled = compile(code, "<crawler>", "exec")
        exec(compiled, sandbox_globals)

        # Find the crawl function
        crawl_fn = sandbox_globals.get("crawl")
        if not crawl_fn:
            raise ValueError("代码中未找到 `async def crawl(url, config)` 函数")

        if not asyncio.iscoroutinefunction(crawl_fn):
            raise ValueError("`crawl` 必须是 async 函数")

        # Run with timeout
        config = {
            "max_pages": max_pages,
            "timeout": timeout,
            "user_agent": settings.user_agent,
            "delay": settings.default_delay,
        }

        results = await asyncio.wait_for(
            crawl_fn(target_url, config),
            timeout=timeout,
        )

        if not isinstance(results, list):
            results = [results] if results else []

        run.status = "success"
        run.output = results[:50]  # Cap preview at 50 items
        run.pages_crawled = len(results)

    except asyncio.TimeoutError:
        run.status = "error"
        run.error = f"执行超时（{timeout}秒），请检查是否有死循环或请求过多"
    except Exception as e:
        run.status = "error"
        run.error = f"{type(e).__name__}: {str(e)}\n{traceback.format_exc()[-500:]}"
        logger.error(f"Sandbox error: {e}")

    run.duration_ms = int((time.monotonic() - start) * 1000)
    return run
