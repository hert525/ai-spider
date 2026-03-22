"""
流控限速模块 - 从 wukong/cms/ 移植并适配 async/await 架构。

功能：
- SlidingWindowCounter: 滑动窗口计数器
- DimensionLimiter: 按维度（域名/IP等）分别限速
- PressureController: 全局流量压力控制器
- AsyncRateLimiter: 异步限速器（集成到 fetch node）
"""
from __future__ import annotations

import asyncio
import json
import time
from collections import deque
from pathlib import Path
from typing import Any, Optional

from loguru import logger


# ============================================================
# 滑动窗口计数器（从 wukong/cms/sliding_window_counter.py 移植）
# ============================================================

class SlidingWindowCounter:
    """
    滑动窗口计数器。

    在固定时间窗口内统计请求数量，超过阈值则限速。
    适配异步场景，使用 asyncio.Lock 替代 threading.Lock。
    """

    def __init__(self, window_size_sec: int = 5, max_requests: int = 100):
        self.window_size_sec = window_size_sec
        self.max_requests = max_requests
        self._timestamps: deque[float] = deque()
        self._lock = asyncio.Lock()

    async def add(self, timestamp: float | None = None) -> None:
        """记录一次请求"""
        ts = timestamp or time.time()
        async with self._lock:
            self._cleanup(ts)
            self._timestamps.append(ts)

    async def count(self, timestamp: float | None = None) -> int:
        """获取当前窗口内的请求数量"""
        ts = timestamp or time.time()
        async with self._lock:
            self._cleanup(ts)
            return len(self._timestamps)

    async def is_allowed(self, timestamp: float | None = None) -> bool:
        """检查是否允许新请求"""
        ts = timestamp or time.time()
        async with self._lock:
            self._cleanup(ts)
            return len(self._timestamps) < self.max_requests

    def _cleanup(self, now: float) -> None:
        """清理过期的时间戳"""
        cutoff = now - self.window_size_sec
        while self._timestamps and self._timestamps[0] < cutoff:
            self._timestamps.popleft()

    def to_dict(self) -> dict:
        """序列化（用于持久化）"""
        return {
            "window_size_sec": self.window_size_sec,
            "max_requests": self.max_requests,
            "timestamps": list(self._timestamps),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SlidingWindowCounter":
        """从字典反序列化"""
        counter = cls(
            window_size_sec=data["window_size_sec"],
            max_requests=data["max_requests"],
        )
        now = time.time()
        valid = [ts for ts in data["timestamps"] if ts >= now - counter.window_size_sec]
        counter._timestamps = deque(valid)
        return counter


# ============================================================
# 维度限速器（从 wukong/cms/dimension_limiter.py 移植）
# ============================================================

class DimensionLimiter:
    """
    按维度分别限速。

    支持按 域名、IP、项目ID 等维度独立设置限速规则。

    Args:
        dimension: 维度名称（如 "domain", "ip"）
        default_window_sec: 默认时间窗口（秒）
        default_max_requests: 默认窗口内最大请求数
        rules: 特定维度值的限速规则 { "example.com": {"window_sec": 5, "max_requests": 10} }
    """

    def __init__(
        self,
        dimension: str = "domain",
        default_window_sec: int = 5,
        default_max_requests: int = 100,
        rules: dict[str, dict] | None = None,
    ):
        self.dimension = dimension
        self.default_window_sec = default_window_sec
        self.default_max_requests = default_max_requests
        self.rules = rules or {}
        self._counters: dict[str, SlidingWindowCounter] = {}

    def _get_counter(self, value: str) -> SlidingWindowCounter:
        """获取或创建对应维度值的计数器"""
        if value not in self._counters:
            rule = self.rules.get(value, {})
            window = rule.get("window_sec", self.default_window_sec)
            max_req = rule.get("max_requests", self.default_max_requests)
            self._counters[value] = SlidingWindowCounter(window, max_req)
        return self._counters[value]

    async def report(self, value: str) -> None:
        """上报一次请求"""
        counter = self._get_counter(value)
        await counter.add()

    async def is_allowed(self, value: str) -> bool:
        """检查是否允许请求"""
        counter = self._get_counter(value)
        return await counter.is_allowed()

    async def wait_if_needed(self, value: str) -> float:
        """
        如果超限则等待到允许为止。

        Returns:
            实际等待时间（秒）
        """
        waited = 0.0
        while not await self.is_allowed(value):
            sleep_time = 0.1  # 100ms 轮询
            await asyncio.sleep(sleep_time)
            waited += sleep_time
            if waited > 30.0:
                logger.warning(f"DimensionLimiter: {self.dimension}={value} 等待超过30s，强制放行")
                break
        return waited


# ============================================================
# 流量压力控制器（从 wukong/cms/pressure_controller.py 移植）
# ============================================================

class PressureController:
    """
    全局流量压力控制器。

    管理多个维度的限速器，支持：
    - 热加载配置文件
    - 按维度分别限速
    - 统一的限速检查接口

    Args:
        config_path: JSON配置文件路径（可选）
        rules: 直接传入的规则列表（可选）
    """

    def __init__(
        self,
        config_path: str | None = None,
        rules: list[dict] | None = None,
    ):
        self._limiters: dict[str, DimensionLimiter] = {}
        self.config_path = config_path

        if rules:
            self._update_rules(rules)
        elif config_path:
            self._load_config()

    def _load_config(self) -> None:
        """从配置文件加载规则"""
        if not self.config_path:
            return
        try:
            path = Path(self.config_path)
            if not path.exists():
                logger.warning(f"PressureController: 配置文件不存在 {self.config_path}")
                return
            with open(path, "r") as f:
                rules = json.load(f)
            self._update_rules(rules)
            logger.info(f"PressureController: 已加载配置 {self.config_path}")
        except Exception as e:
            logger.error(f"PressureController: 加载配置失败: {e}")

    def _update_rules(self, rules: list[dict]) -> None:
        """更新限速规则"""
        for rule in rules:
            dim = rule.get("dimension", "default")
            self._limiters[dim] = DimensionLimiter(
                dimension=dim,
                default_window_sec=rule.get("window_sec", 5),
                default_max_requests=rule.get("max_requests", 100),
                rules=rule.get("rules", {}),
            )
        logger.info(f"PressureController: 已更新 {len(rules)} 条限速规则")

    async def report(self, dimension: str, value: str) -> None:
        """上报请求"""
        limiter = self._limiters.get(dimension)
        if limiter:
            await limiter.report(value)

    async def is_allowed(self, dimension: str, value: str) -> bool:
        """检查是否允许请求"""
        limiter = self._limiters.get(dimension)
        if not limiter:
            return True  # 未配置的维度默认允许
        return await limiter.is_allowed(value)

    async def wait_if_needed(self, dimension: str, value: str) -> float:
        """如果超限则等待"""
        limiter = self._limiters.get(dimension)
        if not limiter:
            return 0.0
        return await limiter.wait_if_needed(value)


# ============================================================
# 异步限速器（集成用简化接口）
# ============================================================

class AsyncRateLimiter:
    """
    异步限速器 - 提供简洁接口供 fetch node 使用。

    支持：
    - 全局QPS限制
    - 按域名限速
    - 自动等待

    示例::

        limiter = AsyncRateLimiter(
            global_qps=50,
            domain_rules={"example.com": {"window_sec": 1, "max_requests": 5}}
        )

        # 在请求前调用
        await limiter.acquire("https://example.com/page1")
    """

    def __init__(
        self,
        global_qps: int = 100,
        domain_rules: dict[str, dict] | None = None,
        enabled: bool = True,
    ):
        self.enabled = enabled

        # 全局限速（按秒）
        self._global = SlidingWindowCounter(
            window_size_sec=1,
            max_requests=global_qps,
        )

        # 域名维度限速
        self._domain_limiter = DimensionLimiter(
            dimension="domain",
            default_window_sec=1,
            default_max_requests=10,  # 默认每域名每秒10个请求
            rules=domain_rules or {},
        )

    async def acquire(self, url: str) -> float:
        """
        获取请求许可。如果超限会自动等待。

        Args:
            url: 要请求的URL

        Returns:
            等待时间（秒）
        """
        if not self.enabled:
            return 0.0

        total_wait = 0.0

        # 全局限速检查
        while not await self._global.is_allowed():
            await asyncio.sleep(0.05)
            total_wait += 0.05

        # 域名限速检查
        domain = self._extract_domain(url)
        if domain:
            wait = await self._domain_limiter.wait_if_needed(domain)
            total_wait += wait

        # 记录请求
        await self._global.add()
        if domain:
            await self._domain_limiter.report(domain)

        if total_wait > 0.1:
            logger.debug(f"限速等待: {url[:60]}... ({total_wait:.2f}s)")

        return total_wait

    @staticmethod
    def _extract_domain(url: str) -> str:
        """从URL提取域名"""
        try:
            from urllib.parse import urlparse
            return urlparse(url).hostname or ""
        except Exception:
            return ""
