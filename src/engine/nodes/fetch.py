"""FetchNode - Fetches web page content using httpx or playwright."""
from __future__ import annotations

import httpx
from loguru import logger
from .base import BaseNode
from src.core.config import settings
from src.engine.proxy import ProxyManager


class FetchNode(BaseNode):
    """Fetch a URL and store raw HTML in state."""

    def __init__(self, use_browser: bool = False, proxy_config: dict | None = None, proxy_pool_id: str = ""):
        super().__init__("FetchNode")
        self.use_browser = use_browser
        self.proxy_config = proxy_config
        self.proxy_pool_id = proxy_pool_id
        self._proxy_manager: ProxyManager | None = None
        if proxy_config and not proxy_pool_id:
            self._proxy_manager = ProxyManager(proxy_config)
        elif not proxy_pool_id:
            self._proxy_manager = self._make_default_proxy_manager()

    async def _get_proxy_manager(self) -> ProxyManager:
        if self._proxy_manager is not None:
            return self._proxy_manager
        if self.proxy_pool_id:
            self._proxy_manager = await ProxyManager.from_pool_id(self.proxy_pool_id)
            return self._proxy_manager
        self._proxy_manager = ProxyManager()
        return self._proxy_manager

    @staticmethod
    def _make_default_proxy_manager() -> ProxyManager:
        """Create proxy manager from global default if set."""
        if settings.default_proxy:
            return ProxyManager({
                "enabled": True,
                "mode": "single",
                "proxy_url": settings.default_proxy,
            })
        return ProxyManager()

    async def execute(self, state: dict) -> dict:
        url = state.get("url", "")
        if not url:
            raise ValueError("No URL provided in state")

        self.logger.info(f"Fetching: {url}")

        # Pass proxy_config through state for downstream nodes
        if self.proxy_config:
            state["proxy_config"] = self.proxy_config

        if self.use_browser:
            html = await self._fetch_browser(url)
        else:
            html = await self._fetch_httpx(url)

        state["raw_html"] = html
        state["fetch_url"] = url
        self.logger.info(f"Fetched {len(html)} chars")
        return state

    async def _fetch_httpx(self, url: str) -> str:
        headers = {"User-Agent": settings.user_agent}
        pm = await self._get_proxy_manager()
        proxies = await pm.get_httpx_proxies_async()
        if proxies:
            self.logger.info(f"Using proxy for httpx request")
        try:
            async with httpx.AsyncClient(
                follow_redirects=True,
                timeout=30,
                proxies=proxies,
            ) as client:
                resp = await client.get(url, headers=headers)
                resp.raise_for_status()
                return resp.text
        except Exception as e:
            if not self.use_browser:
                self.logger.warning(f"httpx failed ({e}), falling back to playwright")
                return await self._fetch_browser(url)
            raise

    async def _fetch_browser(self, url: str) -> str:
        try:
            from playwright.async_api import async_playwright
            proxy = await (await self._get_proxy_manager()).get_playwright_proxy_async()
            if proxy:
                self.logger.info(f"Using proxy for playwright")
            launch_args = {
                "headless": True,
                "args": ['--no-sandbox', '--disable-dev-shm-usage'],
            }
            if proxy:
                launch_args["proxy"] = proxy
            async with async_playwright() as p:
                browser = await p.chromium.launch(**launch_args)
                page = await browser.new_page()
                await page.goto(url, wait_until="networkidle", timeout=30000)
                html = await page.content()
                await browser.close()
                return html
        except ImportError:
            self.logger.warning("Playwright not available, falling back to httpx")
            headers = {"User-Agent": settings.user_agent}
            proxies = await (await self._get_proxy_manager()).get_httpx_proxies_async()
            async with httpx.AsyncClient(
                follow_redirects=True,
                timeout=30,
                proxies=proxies,
            ) as client:
                resp = await client.get(url, headers=headers)
                resp.raise_for_status()
                return resp.text
