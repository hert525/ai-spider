"""
增强版代理管理器 - 从 wukong/proxy/manager.py 移植并适配 async/await 架构。

功能：
- 多策略代理选择（随机、轮询、加权）
- 代理健康检测与自动失败切换
- VolcanoProxy 火山引擎住宅代理支持（session管理、国家选择、自动刷新）
- BrightData 数据中心代理支持
- 旋转代理API支持
- 代理质量统计
"""
from __future__ import annotations

import asyncio
import os
import random
import time
from dataclasses import dataclass, field
from typing import Optional
from urllib.parse import urlparse

import httpx
from loguru import logger


# ============================================================
# 代理质量统计
# ============================================================

@dataclass
class ProxyStats:
    """单个代理的质量统计"""
    total_requests: int = 0
    success_count: int = 0
    fail_count: int = 0
    total_latency_ms: float = 0.0
    last_used: float = 0.0
    last_fail_time: float = 0.0
    consecutive_fails: int = 0

    @property
    def success_rate(self) -> float:
        """成功率"""
        if self.total_requests == 0:
            return 1.0
        return self.success_count / self.total_requests

    @property
    def avg_latency_ms(self) -> float:
        """平均延迟"""
        if self.success_count == 0:
            return float('inf')
        return self.total_latency_ms / self.success_count

    def record_success(self, latency_ms: float) -> None:
        """记录成功请求"""
        self.total_requests += 1
        self.success_count += 1
        self.total_latency_ms += latency_ms
        self.last_used = time.time()
        self.consecutive_fails = 0

    def record_failure(self) -> None:
        """记录失败请求"""
        self.total_requests += 1
        self.fail_count += 1
        self.last_fail_time = time.time()
        self.last_used = time.time()
        self.consecutive_fails += 1

    def is_healthy(self, max_consecutive_fails: int = 5, cooldown_sec: float = 60.0) -> bool:
        """判断代理是否健康"""
        if self.consecutive_fails >= max_consecutive_fails:
            # 冷却时间内不使用
            if time.time() - self.last_fail_time < cooldown_sec:
                return False
        return True


# ============================================================
# 增强版代理管理器
# ============================================================

class EnhancedProxyManager:
    """
    增强版代理管理器，支持多种策略和代理质量监控。

    保留 AI Spider 原有的数据库模型兼容性，同时增加：
    - 代理健康检测
    - 自动失败切换
    - 质量统计
    """

    @classmethod
    async def from_pool_id(cls, pool_id: str) -> "EnhancedProxyManager":
        """从数据库加载代理池配置"""
        from src.core.database import db
        pool = await db.get("proxy_pools", pool_id)
        if not pool or pool.get("status") != "active":
            return cls({})
        return cls({
            "enabled": True,
            "mode": pool["mode"],
            "proxy_url": pool["proxies"][0] if pool.get("proxies") else "",
            "proxy_list": pool.get("proxies", []),
            "rotating_api": pool.get("rotating_api", ""),
            "protocol": pool.get("proxy_type", "http"),
        })

    def __init__(self, config: dict | None = None):
        config = config or {}
        self.enabled = config.get("enabled", False)
        self.mode = config.get("mode", "single")  # single/pool/random_pool/rotating/round_robin
        self.proxy_url = config.get("proxy_url", "")
        self.proxy_list: list[str] = config.get("proxy_list", [])
        self.rotating_api = config.get("rotating_api", "")
        self.protocol = config.get("protocol", "http")

        # 健康检测配置
        self.max_consecutive_fails = config.get("max_consecutive_fails", 5)
        self.cooldown_sec = config.get("cooldown_sec", 60.0)
        self.auto_failover = config.get("auto_failover", True)

        # 轮询索引
        self._index = 0

        # 代理质量统计 { proxy_url -> ProxyStats }
        self._stats: dict[str, ProxyStats] = {}

    def _get_stats(self, proxy: str) -> ProxyStats:
        """获取或创建代理统计"""
        if proxy not in self._stats:
            self._stats[proxy] = ProxyStats()
        return self._stats[proxy]

    def _get_healthy_proxies(self) -> list[str]:
        """获取健康的代理列表"""
        if not self.auto_failover:
            return self.proxy_list
        healthy = [
            p for p in self.proxy_list
            if self._get_stats(p).is_healthy(self.max_consecutive_fails, self.cooldown_sec)
        ]
        # 如果所有代理都不健康，返回全部（避免死锁）
        return healthy if healthy else self.proxy_list

    def get_proxy(self) -> str | None:
        """获取下一个代理URL（同步）"""
        if not self.enabled:
            return None

        if self.mode == "single":
            return self.proxy_url or None

        elif self.mode == "round_robin":
            proxies = self._get_healthy_proxies()
            if not proxies:
                return None
            proxy = proxies[self._index % len(proxies)]
            self._index += 1
            return proxy

        elif self.mode in ("pool", "random_pool"):
            proxies = self._get_healthy_proxies()
            if not proxies:
                return None
            return random.choice(proxies)

        elif self.mode == "rotating":
            return None  # 需要用 async 方法

        return None

    async def get_rotating_proxy(self) -> str | None:
        """从旋转代理API获取新代理"""
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
            logger.warning(f"获取旋转代理失败: {e}")
        return None

    async def get_proxy_url(self) -> str | None:
        """获取代理URL（支持同步和异步模式）"""
        if not self.enabled:
            return None
        if self.mode == "rotating":
            return await self.get_rotating_proxy()
        return self.get_proxy()

    def report_success(self, proxy_url: str, latency_ms: float) -> None:
        """上报代理请求成功"""
        if proxy_url:
            self._get_stats(proxy_url).record_success(latency_ms)

    def report_failure(self, proxy_url: str) -> None:
        """上报代理请求失败"""
        if proxy_url:
            self._get_stats(proxy_url).record_failure()
            stats = self._get_stats(proxy_url)
            if stats.consecutive_fails >= self.max_consecutive_fails:
                logger.warning(
                    f"代理 {proxy_url} 连续失败 {stats.consecutive_fails} 次，"
                    f"进入冷却 {self.cooldown_sec}s"
                )

    def get_all_stats(self) -> dict[str, dict]:
        """获取所有代理的统计信息"""
        return {
            proxy: {
                "total_requests": s.total_requests,
                "success_rate": round(s.success_rate * 100, 1),
                "avg_latency_ms": round(s.avg_latency_ms, 1),
                "consecutive_fails": s.consecutive_fails,
                "is_healthy": s.is_healthy(self.max_consecutive_fails, self.cooldown_sec),
            }
            for proxy, s in self._stats.items()
        }

    async def get_httpx_proxies(self) -> dict | None:
        """获取 httpx 代理配置"""
        proxy = await self.get_proxy_url()
        if not proxy:
            return None
        return {"http://": proxy, "https://": proxy}

    async def get_playwright_proxy(self) -> dict | None:
        """获取 Playwright 代理配置"""
        proxy = await self.get_proxy_url()
        if not proxy:
            return None
        return {"server": proxy}


# ============================================================
# 火山引擎代理管理器（从 wukong VolcanoProxyManager 移植）
# ============================================================

class VolcanoProxyManager:
    """
    火山引擎(Vortex IP)住宅代理管理器。

    支持功能：
    - 国家/地区选择
    - Session保持（同IP复用）
    - 自动Session刷新
    - 异步接口
    """

    # 支持的国家/地区
    SUPPORTED_COUNTRIES = ["at", "de", "fr", "ca", "ro", "us", "ch", "es", "sg", "it", "uk", "hk"]

    def __init__(
        self,
        https_endpoint: str = "",
        http_endpoint: str = "",
        country: str | None = None,
        password: str | None = None,
        enable_session: bool = True,
        session_refresh_interval: float = 600.0,
    ):
        self.http_endpoint = http_endpoint or os.environ.get("VOL_HTTP_ENDPOINT", "")
        self.https_endpoint = https_endpoint or os.environ.get("VOL_HTTPS_ENDPOINT", "")

        # 解析端点
        self.http_host, self.http_port, self._password = self._parse_endpoint(self.http_endpoint)
        self.https_host, self.https_port, _ = self._parse_endpoint(self.https_endpoint)

        if password:
            self._password = password

        # 国家配置
        if country is not None:
            country = country.lower()
            if country not in self.SUPPORTED_COUNTRIES:
                logger.warning(f"VolcanoProxy: 国家 '{country}' 不在支持列表中，将原样使用")
        self.country = country

        # Session管理
        self.enable_session = enable_session
        self.session_refresh_interval = session_refresh_interval
        self._session_id: str | None = self._generate_session_id() if enable_session else None
        self._session_lock = asyncio.Lock()
        self._refresh_task: asyncio.Task | None = None

    @staticmethod
    def _parse_endpoint(endpoint: str) -> tuple[str | None, int | None, str | None]:
        """解析端点URL"""
        if not endpoint:
            return None, None, None
        if "://" in endpoint:
            parsed = urlparse(endpoint)
            return parsed.hostname, parsed.port, parsed.password
        if ":" in endpoint:
            parts = endpoint.rsplit(":", 1)
            try:
                return parts[0], int(parts[1]), None
            except ValueError:
                return endpoint, None, None
        return endpoint, None, None

    @staticmethod
    def _generate_session_id() -> str:
        """生成8位随机Session ID"""
        return f"{random.randint(10000000, 99999999)}"

    def _build_proxy_user(self, session_id: str | None = None) -> str:
        """构建代理用户字符串"""
        user = "proxy"
        if self.country:
            user = f"{user}-cot-{self.country}"
        if session_id:
            user = f"{user}-sid-{session_id}"
        return user

    def _build_proxy_url(self, scheme: str, host: str | None, port: int | None,
                         session_id: str | None = None) -> str:
        """构建代理URL"""
        if not host:
            return ""
        user = self._build_proxy_user(session_id)
        pwd = self._password or ""
        url = f"{scheme}://{user}:{pwd}@{host}"
        if port:
            url = f"{url}:{port}"
        return url

    async def get_proxies(self) -> dict[str, str]:
        """获取HTTP/HTTPS代理URL对"""
        async with self._session_lock:
            session_id = self._session_id
        http_url = self._build_proxy_url("http", self.http_host, self.http_port, session_id)
        https_url = self._build_proxy_url("https", self.https_host, self.https_port, session_id)
        return {"http://": http_url, "https://": https_url}

    async def refresh_session(self) -> None:
        """刷新Session ID以获取新IP"""
        if not self.enable_session:
            return
        async with self._session_lock:
            old_id = self._session_id
            self._session_id = self._generate_session_id()
            logger.debug(f"VolcanoProxy: Session刷新 {old_id} → {self._session_id}")

    async def start_auto_refresh(self) -> None:
        """启动自动Session刷新"""
        if not self.enable_session:
            return

        async def _refresh_loop():
            while True:
                await asyncio.sleep(self.session_refresh_interval)
                await self.refresh_session()

        self._refresh_task = asyncio.create_task(_refresh_loop())
        logger.info(f"VolcanoProxy: 自动刷新已启动 (间隔 {self.session_refresh_interval}s)")

    async def stop_auto_refresh(self) -> None:
        """停止自动Session刷新"""
        if self._refresh_task:
            self._refresh_task.cancel()
            try:
                await self._refresh_task
            except asyncio.CancelledError:
                pass
            self._refresh_task = None
            logger.info("VolcanoProxy: 自动刷新已停止")


# ============================================================
# BrightData 代理管理器（从 wukong BrightDataProxyManager 移植）
# ============================================================

class BrightDataProxyManager:
    """
    BrightData 数据中心代理管理器。

    支持功能：
    - 多国家/地区IP
    - 自动国家轮换
    - 异步接口
    """

    def __init__(
        self,
        customer_id: str = "",
        zone_pwd: str = "",
        host: str = "brd.superproxy.io",
        port: int = 33335,
        zone_name: str = "datacenter_proxy1",
        countries: list[str] | None = None,
    ):
        self.customer_id = customer_id or os.environ.get("BD_CUSTOMER_ID", "")
        self.zone_pwd = zone_pwd or os.environ.get("BD_ZONE_PWD", "")
        self.host = host
        self.port = port
        self.zone_name = zone_name
        self.countries = countries or []

    def _get_country(self) -> str | None:
        """随机选择一个国家代码"""
        if not self.countries:
            return None
        return random.choice(self.countries).lower()

    def get_proxy_url(self) -> str:
        """生成代理URL"""
        user = f"brd-customer-{self.customer_id}-zone-{self.zone_name}"
        country = self._get_country()
        if country:
            user = f"{user}-country-{country}"
        return f"http://{user}:{self.zone_pwd}@{self.host}:{self.port}"

    async def get_proxies(self) -> dict[str, str]:
        """获取HTTP/HTTPS代理URL对"""
        url = self.get_proxy_url()
        return {"http://": url, "https://": url}


# ============================================================
# User-Agent 管理器
# ============================================================

# 常用桌面UA池（从 wukong/proxy/user_agent.py 移植并更新）
DESKTOP_USER_AGENTS = [
    # Chrome (Windows)
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    # Chrome (macOS)
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    # Chrome (Linux)
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    # Firefox
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:133.0) Gecko/20100101 Firefox/133.0",
    "Mozilla/5.0 (X11; Linux x86_64; rv:133.0) Gecko/20100101 Firefox/133.0",
    # Safari
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.2 Safari/605.1.15",
    # Edge
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0",
]

MOBILE_USER_AGENTS = [
    # Chrome Android
    "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 13; SM-S918B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36",
    # Safari iOS
    "Mozilla/5.0 (iPhone; CPU iPhone OS 18_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.2 Mobile/15E148 Safari/604.1",
]


class UserAgentManager:
    """User-Agent 管理器，支持桌面/移动端UA随机选取"""

    def __init__(self, custom_uas: list[str] | None = None):
        self._custom_uas = custom_uas or []
        self._desktop_uas = DESKTOP_USER_AGENTS.copy()
        self._mobile_uas = MOBILE_USER_AGENTS.copy()

    def random_desktop(self) -> str:
        """随机获取桌面UA"""
        pool = self._custom_uas + self._desktop_uas
        return random.choice(pool) if pool else DESKTOP_USER_AGENTS[0]

    def random_mobile(self) -> str:
        """随机获取移动端UA"""
        pool = self._mobile_uas
        return random.choice(pool) if pool else MOBILE_USER_AGENTS[0]

    def random(self, mobile_ratio: float = 0.1) -> str:
        """随机获取UA，默认10%概率返回移动端"""
        if random.random() < mobile_ratio:
            return self.random_mobile()
        return self.random_desktop()

    @staticmethod
    def generate_client_hints(user_agent: str) -> dict[str, str]:
        """根据UA生成 Sec-CH-UA 相关头部（从 wukong 移植）"""
        import re
        headers: dict[str, str] = {}

        chrome_match = re.search(r"Chrome/(\d+)", user_agent)
        edge_match = re.search(r"Edg/(\d+)", user_agent)

        if chrome_match:
            version = chrome_match.group(1)
            hints = [f'"Chromium";v="{version}"', '"Not_A Brand";v="8"']
            if edge_match:
                hints.append(f'"Microsoft Edge";v="{edge_match.group(1)}"')
            else:
                hints.append(f'"Google Chrome";v="{version}"')
            headers["Sec-CH-UA"] = ", ".join(hints)
            headers["Sec-CH-UA-Mobile"] = "?0"

            # 检测平台
            if "Windows" in user_agent:
                headers["Sec-CH-UA-Platform"] = '"Windows"'
            elif "Macintosh" in user_agent:
                headers["Sec-CH-UA-Platform"] = '"macOS"'
            elif "Linux" in user_agent:
                headers["Sec-CH-UA-Platform"] = '"Linux"'

        return headers


# 全局User-Agent管理器实例
ua_manager = UserAgentManager()
