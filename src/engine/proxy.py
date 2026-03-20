"""Proxy manager for crawler requests."""
from __future__ import annotations

import random

import httpx
from loguru import logger


class ProxyManager:
    """Manages proxy rotation and selection."""

    def __init__(self, config: dict | None = None):
        config = config or {}
        self.enabled = config.get("enabled", False)
        self.mode = config.get("mode", "single")
        self.proxy_url = config.get("proxy_url", "")
        self.proxy_list = config.get("proxy_list", [])
        self.rotating_api = config.get("rotating_api", "")
        self.protocol = config.get("protocol", "http")
        self._index = 0

    def get_proxy(self) -> str | None:
        """Get next proxy URL."""
        if not self.enabled:
            return None

        if self.mode == "single":
            return self.proxy_url or None

        elif self.mode == "pool":
            if not self.proxy_list:
                return None
            proxy = self.proxy_list[self._index % len(self.proxy_list)]
            self._index += 1
            return proxy

        elif self.mode == "random_pool":
            if not self.proxy_list:
                return None
            return random.choice(self.proxy_list)

        elif self.mode == "rotating":
            # For rotating mode, caller should use get_rotating_proxy() instead
            return None

        return None

    async def get_rotating_proxy(self) -> str | None:
        """Fetch a fresh proxy from rotating API."""
        if not self.rotating_api:
            return None
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(self.rotating_api)
                proxy = resp.text.strip()
                if proxy and (":" in proxy):
                    if not proxy.startswith("http"):
                        proxy = f"{self.protocol}://{proxy}"
                    return proxy
        except Exception as e:
            logger.warning(f"Failed to get rotating proxy: {e}")
        return None

    async def get_proxy_url(self) -> str | None:
        """Get proxy URL, supporting both sync and rotating modes."""
        if not self.enabled:
            return None
        if self.mode == "rotating":
            return await self.get_rotating_proxy()
        return self.get_proxy()

    def get_httpx_proxies(self) -> dict | None:
        """Get proxy dict for httpx."""
        proxy = self.get_proxy()
        if not proxy:
            return None
        return {"http://": proxy, "https://": proxy}

    async def get_httpx_proxies_async(self) -> dict | None:
        """Get proxy dict for httpx (supports rotating)."""
        proxy = await self.get_proxy_url()
        if not proxy:
            return None
        return {"http://": proxy, "https://": proxy}

    def get_playwright_proxy(self) -> dict | None:
        """Get proxy dict for playwright."""
        proxy = self.get_proxy()
        if not proxy:
            return None
        return {"server": proxy}

    async def get_playwright_proxy_async(self) -> dict | None:
        """Get proxy dict for playwright (supports rotating)."""
        proxy = await self.get_proxy_url()
        if not proxy:
            return None
        return {"server": proxy}
