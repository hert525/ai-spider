"""
FetchNode - 抓取网页内容。

集成增强功能（从 wukong 移植）：
- 增强版代理管理（健康检测、自动失败切换、质量统计）
- 流控限速（全局QPS + 域名维度限速）
- 监控指标（请求计数/成功率/延迟自动上报）
- User-Agent 智能轮换
"""
from __future__ import annotations

import asyncio
import json
import random
import time
from urllib.parse import urlparse

import httpx
from loguru import logger
from .base import BaseNode
from src.core.config import settings
from src.engine.proxy import ProxyManager
from src.engine.proxy_manager import EnhancedProxyManager, ua_manager
from src.engine.rate_limiter import AsyncRateLimiter
from src.engine import metrics


# 全局限速器实例（可通过配置调整）
_rate_limiter: AsyncRateLimiter | None = None


def get_rate_limiter() -> AsyncRateLimiter:
    """获取全局限速器（懒初始化）"""
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = AsyncRateLimiter(
            global_qps=int(getattr(settings, "global_qps", 100)),
            enabled=getattr(settings, "rate_limit_enabled", False),
        )
    return _rate_limiter


class FetchNode(BaseNode):
    """
    抓取节点 - 使用 httpx 或 playwright 抓取网页。

    增强功能：
    - 代理健康检测 + 自动失败切换
    - 全局/域名级限速
    - 自动指标上报
    - User-Agent 智能轮换 + Client Hints
    """

    def __init__(self, use_browser: bool = False, proxy_config: dict | None = None,
                 proxy_pool_id: str = "", stealth_level: str = "off",
                 enable_screenshot: bool = False, user_id: str = "",
                 rate_limit_enabled: bool = False, enhanced_proxy: bool = False):
        super().__init__("FetchNode")
        self.use_browser = use_browser
        self.proxy_config = proxy_config
        self.proxy_pool_id = proxy_pool_id
        self.stealth_level = stealth_level
        self.enable_screenshot = enable_screenshot
        self.user_id = user_id
        self.enhanced_proxy = enhanced_proxy
        self._proxy_manager: ProxyManager | None = None
        self._enhanced_proxy_manager: EnhancedProxyManager | None = None

        if proxy_config and not proxy_pool_id:
            if enhanced_proxy:
                self._enhanced_proxy_manager = EnhancedProxyManager(proxy_config)
            else:
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

    async def _get_enhanced_proxy(self) -> EnhancedProxyManager | None:
        """获取增强版代理管理器"""
        if not self.enhanced_proxy:
            return None
        if self._enhanced_proxy_manager is not None:
            return self._enhanced_proxy_manager
        if self.proxy_pool_id:
            self._enhanced_proxy_manager = await EnhancedProxyManager.from_pool_id(self.proxy_pool_id)
            return self._enhanced_proxy_manager
        return None

    @staticmethod
    def _make_default_proxy_manager() -> ProxyManager:
        """从全局默认配置创建代理管理器"""
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

        self.logger.info(f"抓取: {url}")

        # 通过state传递代理配置给下游节点
        if self.proxy_config:
            state["proxy_config"] = self.proxy_config

        # 限速等待
        limiter = get_rate_limiter()
        wait_time = await limiter.acquire(url)
        if wait_time > 0:
            self.logger.debug(f"限速等待: {wait_time:.2f}s")

        # 记录开始时间
        start_time = time.time()

        try:
            if self.use_browser:
                html = await self._fetch_browser(url, state)
            else:
                html = await self._fetch_httpx(url)

            # 上报成功指标
            duration = time.time() - start_time
            await metrics.incr_fetch_success(url=url, status=200)
            await metrics.observe_fetch_duration(duration, url=url)
            await metrics.incr_requests_total(method="GET", status=200)

            # 增强代理管理器上报成功
            epm = await self._get_enhanced_proxy()
            if epm and state.get("_last_proxy"):
                epm.report_success(state["_last_proxy"], duration * 1000)

        except Exception as e:
            # 上报失败指标
            duration = time.time() - start_time
            await metrics.incr_fetch_failure(url=url, reason=type(e).__name__)
            await metrics.incr_requests_total(method="GET", status=0)

            # 增强代理管理器上报失败
            epm = await self._get_enhanced_proxy()
            if epm and state.get("_last_proxy"):
                epm.report_failure(state["_last_proxy"])

            raise

        state["raw_html"] = html
        state["fetch_url"] = url
        state["fetch_duration"] = round(duration, 3)
        self.logger.info(f"抓取完成: {len(html)} 字符, 耗时 {duration:.2f}s")
        return state

    async def _fetch_httpx(self, url: str, state: dict | None = None) -> str:
        if state is None:
            state = {}

        # User-Agent 智能轮换（使用增强UA管理器）
        if self.stealth_level and self.stealth_level != "off":
            user_agent = ua_manager.random()
            headers = {"User-Agent": user_agent}
            # 生成 Client Hints 头部
            hints = ua_manager.generate_client_hints(user_agent)
            headers.update(hints)
        else:
            headers = {"User-Agent": settings.user_agent}

        # 加载域名Cookie
        domain = urlparse(url).netloc
        saved_cookies = await self._load_cookies_for_domain(domain)
        cookie_jar = None
        if saved_cookies:
            cookie_jar = httpx.Cookies()
            for c in saved_cookies:
                cookie_jar.set(c.get("name", ""), c.get("value", ""), domain=c.get("domain", domain))
            self.logger.info(f"已加载 {len(saved_cookies)} 个Cookie ({domain})")

        # 获取代理（优先使用增强版代理管理器）
        proxies = None
        proxy_url = None
        epm = await self._get_enhanced_proxy()
        if epm:
            proxies = await epm.get_httpx_proxies()
            if proxies:
                proxy_url = list(proxies.values())[0]
                state["_last_proxy"] = proxy_url
                self.logger.info(f"使用增强代理: {proxy_url[:40]}...")
        else:
            pm = await self._get_proxy_manager()
            proxies = await pm.get_httpx_proxies_async()
            if proxies:
                self.logger.info(f"使用代理进行httpx请求")

        try:
            # httpx >= 0.28 用 proxy 参数（单个URL），旧版用 proxies（dict）
            _proxy_arg = proxy_url if proxy_url else None
            async with httpx.AsyncClient(
                follow_redirects=True,
                timeout=30,
                proxy=_proxy_arg,
                cookies=cookie_jar,
            ) as client:
                resp = await client.get(url, headers=headers)
                resp.raise_for_status()
                return resp.text
        except Exception as e:
            self.logger.warning(f"httpx失败 ({e}), 尝试curl_cffi降级")
            # 第二级降级：curl_cffi（TLS指纹模拟，绕过Cloudflare等）
            try:
                curl_text = await self._fetch_curl_cffi(url, proxies=proxies, cookies=cookie_jar)
                if curl_text:
                    return curl_text
            except Exception as ce:
                self.logger.warning(f"curl_cffi也失败 ({ce})")

            # 第三级降级：playwright（完整浏览器渲染）
            if not self.use_browser:
                self.logger.warning(f"curl_cffi失败, 最终降级到playwright")
                return await self._fetch_browser(url, state or {})
            raise

    async def _fetch_curl_cffi(
        self,
        url: str,
        proxies: dict | None = None,
        cookies: httpx.Cookies | None = None,
    ) -> str | None:
        """使用 curl_cffi 抓取（TLS指纹模拟，绕过反爬检测）"""
        try:
            from src.engine.curl_fetcher import get_curl_fetcher, HAS_CURL_CFFI
            if not HAS_CURL_CFFI:
                return None
        except ImportError:
            return None

        # 转换代理格式
        proxy_url = None
        proxy_list = None
        if proxies:
            proxy_url = list(proxies.values())[0] if proxies else None
        
        fetcher = get_curl_fetcher(
            proxy_url=proxy_url,
            rotate_fingerprint=True,  # 自动轮换指纹
        )

        # 转换cookie
        cookie_dict = None
        if cookies:
            cookie_dict = dict(cookies)

        resp = await fetcher.get(
            url,
            cookies=cookie_dict,
            max_retries=2,  # curl_cffi层再试2次
        )

        if resp.ok and resp.text:
            self.logger.info(
                f"curl_cffi成功: {url} → {resp.status_code}, "
                f"{len(resp.text)}字符, fp={resp.fingerprint}, "
                f"{resp.elapsed_ms:.0f}ms"
            )
            return resp.text

        if resp.error:
            self.logger.warning(f"curl_cffi失败: {url} → {resp.error}")
        return None

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
