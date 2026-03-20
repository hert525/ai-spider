"""FetchNode - Fetches web page content using httpx or playwright."""
from __future__ import annotations

import asyncio
import json
import random
from urllib.parse import urlparse

import httpx
from loguru import logger
from .base import BaseNode
from src.core.config import settings
from src.engine.proxy import ProxyManager


class FetchNode(BaseNode):
    """Fetch a URL and store raw HTML in state."""

    def __init__(self, use_browser: bool = False, proxy_config: dict | None = None,
                 proxy_pool_id: str = "", stealth_level: str = "off",
                 enable_screenshot: bool = False, user_id: str = ""):
        super().__init__("FetchNode")
        self.use_browser = use_browser
        self.proxy_config = proxy_config
        self.proxy_pool_id = proxy_pool_id
        self.stealth_level = stealth_level
        self.enable_screenshot = enable_screenshot
        self.user_id = user_id
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

    async def _load_cookies_for_domain(self, domain: str) -> list[dict] | None:
        """Load saved cookies for a domain from the database."""
        if not self.user_id:
            return None
        try:
            from src.core.database import db
            rows = await db.query(
                "SELECT cookies FROM browser_sessions WHERE user_id = ? AND domain = ? AND status = 'active'",
                [self.user_id, domain],
            )
            if rows:
                cookies_raw = rows[0]["cookies"]
                return json.loads(cookies_raw) if isinstance(cookies_raw, str) else cookies_raw
        except Exception as e:
            self.logger.warning(f"Failed to load cookies for {domain}: {e}")
        return None

    async def execute(self, state: dict) -> dict:
        url = state.get("url", "")
        if not url:
            raise ValueError("No URL provided in state")

        self.logger.info(f"Fetching: {url}")

        # Pass proxy_config through state for downstream nodes
        if self.proxy_config:
            state["proxy_config"] = self.proxy_config

        if self.use_browser:
            html = await self._fetch_browser(url, state)
        else:
            html = await self._fetch_httpx(url)

        state["raw_html"] = html
        state["fetch_url"] = url
        self.logger.info(f"Fetched {len(html)} chars")
        return state

    async def _fetch_httpx(self, url: str) -> str:
        headers = {"User-Agent": settings.user_agent}

        # Load cookies for domain if available
        domain = urlparse(url).netloc
        saved_cookies = await self._load_cookies_for_domain(domain)
        cookie_jar = None
        if saved_cookies:
            cookie_jar = httpx.Cookies()
            for c in saved_cookies:
                cookie_jar.set(c.get("name", ""), c.get("value", ""), domain=c.get("domain", domain))
            self.logger.info(f"Loaded {len(saved_cookies)} cookies for {domain}")

        # Apply stealth user-agent if enabled
        if self.stealth_level and self.stealth_level != "off":
            from src.engine.stealth import USER_AGENTS
            headers["User-Agent"] = random.choice(USER_AGENTS)

        pm = await self._get_proxy_manager()
        proxies = await pm.get_httpx_proxies_async()
        if proxies:
            self.logger.info(f"Using proxy for httpx request")
        try:
            async with httpx.AsyncClient(
                follow_redirects=True,
                timeout=30,
                proxies=proxies,
                cookies=cookie_jar,
            ) as client:
                resp = await client.get(url, headers=headers)
                resp.raise_for_status()
                return resp.text
        except Exception as e:
            if not self.use_browser:
                self.logger.warning(f"httpx failed ({e}), falling back to playwright")
                return await self._fetch_browser(url, {})
            raise

    async def _fetch_browser(self, url: str, state: dict) -> str:
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

                # Build context options with stealth if enabled
                context_opts = {}
                if self.stealth_level and self.stealth_level != "off":
                    from src.engine.stealth import get_stealth_context_options
                    context_opts = get_stealth_context_options(self.stealth_level)

                # Load saved session/cookies
                domain = urlparse(url).netloc
                saved_cookies = await self._load_cookies_for_domain(domain)

                context = await browser.new_context(**context_opts)

                # Add saved cookies to context
                if saved_cookies:
                    for c in saved_cookies:
                        cookie = {
                            "name": c.get("name", ""),
                            "value": c.get("value", ""),
                            "domain": c.get("domain", domain),
                            "path": c.get("path", "/"),
                        }
                        try:
                            await context.add_cookies([cookie])
                        except Exception:
                            pass
                    self.logger.info(f"Loaded {len(saved_cookies)} cookies for {domain}")

                page = await context.new_page()

                # Apply stealth scripts
                if self.stealth_level and self.stealth_level != "off":
                    from src.engine.stealth import apply_stealth
                    await apply_stealth(page, self.stealth_level)

                # Random delay to mimic human behavior
                if self.stealth_level and self.stealth_level != "off":
                    await asyncio.sleep(random.uniform(0.5, 2.0))

                await page.goto(url, wait_until="networkidle", timeout=30000)

                # Another small random delay after load
                if self.stealth_level and self.stealth_level != "off":
                    await asyncio.sleep(random.uniform(0.3, 1.0))

                html = await page.content()

                # Screenshot if enabled
                if self.enable_screenshot:
                    task_id = state.get("task_id", "unknown")
                    try:
                        from src.engine.screenshot import screenshot_manager
                        screenshot_path = await screenshot_manager.capture(page, task_id)
                        state["screenshot"] = screenshot_path
                        self.logger.info(f"Screenshot captured: {screenshot_path}")
                    except Exception as e:
                        self.logger.warning(f"Screenshot failed: {e}")

                # Save updated cookies back
                if self.user_id and saved_cookies is not None:
                    try:
                        new_cookies = await context.cookies()
                        if new_cookies:
                            from src.core.database import db
                            from datetime import datetime, timezone
                            cookie_list = [{"name": c["name"], "value": c["value"],
                                           "domain": c.get("domain", domain),
                                           "path": c.get("path", "/")} for c in new_cookies]
                            await db.execute(
                                "UPDATE browser_sessions SET cookies = ?, updated_at = ? WHERE user_id = ? AND domain = ?",
                                [json.dumps(cookie_list, ensure_ascii=False),
                                 datetime.now(timezone.utc).isoformat(),
                                 self.user_id, domain],
                            )
                    except Exception as e:
                        self.logger.warning(f"Failed to save updated cookies: {e}")

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
