"""Code format adapters — wraps various spider formats into our standard interface."""
from __future__ import annotations

import ast
import re
from loguru import logger


class CodeAdapter:
    """Detects and adapts different spider code formats."""

    @staticmethod
    def detect_format(code: str) -> str:
        """Detect the code format.
        Returns: 'standard' | 'scrapy' | 'requests' | 'selenium' | 'playwright' | 'script' | 'unknown'
        """
        if re.search(r'async\s+def\s+crawl\s*\(', code):
            return 'standard'
        if 'import scrapy' in code or 'from scrapy' in code:
            return 'scrapy'
        if 'playwright' in code and ('async_playwright' in code or 'sync_playwright' in code):
            return 'playwright'
        if 'from selenium' in code or 'import selenium' in code:
            return 'selenium'
        if 'import requests' in code or 'from requests' in code:
            return 'requests'
        if 'import httpx' in code or 'from httpx' in code:
            return 'requests'
        if '__name__' in code and '__main__' in code:
            return 'script'
        return 'unknown'

    @staticmethod
    def wrap(code: str, format: str = None) -> str:
        """Wrap code into our standard async def crawl() format."""
        if format is None:
            format = CodeAdapter.detect_format(code)
        if format == 'standard':
            return code
        handler = {
            'scrapy': CodeAdapter._wrap_scrapy,
            'requests': CodeAdapter._wrap_requests,
            'selenium': CodeAdapter._wrap_selenium,
            'playwright': CodeAdapter._wrap_playwright,
            'script': CodeAdapter._wrap_script,
        }.get(format, CodeAdapter._wrap_generic)
        return handler(code)

    @staticmethod
    def _wrap_scrapy(code: str) -> str:
        return f'''# Auto-adapted from Scrapy spider
import asyncio

try:
    from scrapy.crawler import CrawlerRunner
    from scrapy.utils.project import get_project_settings
    from scrapy import signals
    import scrapy
    _HAS_SCRAPY = True
except ImportError:
    _HAS_SCRAPY = False

# --- Original Scrapy Code ---
{code}
# --- End Original ---

async def crawl(url: str, config: dict) -> list[dict]:
    """Adapter: runs Scrapy spider and collects items."""
    if not _HAS_SCRAPY:
        return [{{"error": "scrapy not installed. Run: pip install scrapy"}}]

    items = []
    import inspect
    spider_classes = [obj for name, obj in globals().items()
                     if inspect.isclass(obj) and issubclass(obj, scrapy.Spider) and obj is not scrapy.Spider]

    if not spider_classes:
        return [{{"error": "No Spider class found in code"}}]

    SpiderClass = spider_classes[0]
    if url:
        SpiderClass.start_urls = [url]

    from scrapy.utils.log import configure_logging
    configure_logging({{"LOG_ENABLED": False}})

    settings = get_project_settings()
    settings.update({{
        "LOG_ENABLED": False,
        "ROBOTSTXT_OBEY": False,
    }})

    runner = CrawlerRunner(settings)

    def item_scraped(item, **kwargs):
        items.append(dict(item))

    crawler = runner.create_crawler(SpiderClass)
    crawler.signals.connect(item_scraped, signal=signals.item_scraped)

    await runner.crawl(crawler)
    return items
'''

    @staticmethod
    def _wrap_requests(code: str) -> str:
        return f'''# Auto-adapted from requests/httpx script
import asyncio
import json
import re

# --- Original Code ---
{code}
# --- End Original ---

async def crawl(url: str, config: dict) -> list[dict]:
    """Adapter: runs the original script and captures output."""
    for func_name in ['main', 'run', 'scrape', 'fetch', 'parse', 'spider', 'crawl_sync', 'get_data']:
        fn = globals().get(func_name)
        if fn and callable(fn):
            try:
                if asyncio.iscoroutinefunction(fn):
                    result = await fn(url) if url else await fn()
                else:
                    result = await asyncio.to_thread(fn, url) if url else await asyncio.to_thread(fn)
                if isinstance(result, list):
                    return [r if isinstance(r, dict) else {{"data": str(r)}} for r in result]
                elif isinstance(result, dict):
                    return [result]
                elif result is not None:
                    return [{{"data": str(result)}}]
            except Exception as e:
                return [{{"error": str(e)}}]

    return [{{"error": "No callable entry function found (main/run/scrape/fetch/parse)"}}]
'''

    @staticmethod
    def _wrap_selenium(code: str) -> str:
        return f'''# Auto-adapted from Selenium script
import asyncio

# --- Original Code ---
{code}
# --- End Original ---

async def crawl(url: str, config: dict) -> list[dict]:
    """Adapter: runs Selenium script."""
    for func_name in ['main', 'run', 'scrape', 'get_data']:
        if func_name in dir():
            func = globals()[func_name]
            result = await asyncio.to_thread(func, url) if url else await asyncio.to_thread(func)
            if isinstance(result, list):
                return [r if isinstance(r, dict) else {{"data": str(r)}} for r in result]
            elif isinstance(result, dict):
                return [result]
    return [{{"error": "No entry function found"}}]
'''

    @staticmethod
    def _wrap_playwright(code: str) -> str:
        return f'''# Auto-adapted from Playwright script
{code}

if 'crawl' not in dir():
    async def crawl(url: str, config: dict) -> list[dict]:
        for func_name in ['main', 'run', 'scrape']:
            if func_name in dir():
                func = globals()[func_name]
                import asyncio
                result = await func(url) if asyncio.iscoroutinefunction(func) else func(url)
                if isinstance(result, list):
                    return [r if isinstance(r, dict) else {{"data": str(r)}} for r in result]
                elif isinstance(result, dict):
                    return [result]
        return [{{"error": "No entry function found"}}]
'''

    @staticmethod
    def _wrap_script(code: str) -> str:
        clean_code = re.sub(r"if\s+__name__\s*==\s*['\"]__main__['\"]\s*:", "# __main__ removed", code)
        return CodeAdapter._wrap_requests(clean_code)

    @staticmethod
    def _wrap_generic(code: str) -> str:
        return CodeAdapter._wrap_requests(code)
