"""FetchNode - Fetches web page content using httpx or playwright."""
import httpx
from loguru import logger
from .base import BaseNode
from src.core.config import settings


class FetchNode(BaseNode):
    """Fetch a URL and store raw HTML in state."""

    def __init__(self, use_browser: bool = False):
        super().__init__("FetchNode")
        self.use_browser = use_browser

    async def execute(self, state: dict) -> dict:
        url = state.get("url", "")
        if not url:
            raise ValueError("No URL provided in state")

        self.logger.info(f"Fetching: {url}")

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
        async with httpx.AsyncClient(follow_redirects=True, timeout=30) as client:
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
            return resp.text

    async def _fetch_browser(self, url: str) -> str:
        try:
            from playwright.async_api import async_playwright
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()
                await page.goto(url, wait_until="networkidle", timeout=30000)
                html = await page.content()
                await browser.close()
                return html
        except ImportError:
            self.logger.warning("Playwright not available, falling back to httpx")
            return await self._fetch_httpx(url)
