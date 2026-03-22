"""
基于IP的滑动窗口限流中间件。

默认限制:
- 60次/分钟
- 1000次/小时

白名单IP（不限流）: 127.0.0.1

超限返回 429 Too Many Requests。
"""
from __future__ import annotations

import time
from collections import defaultdict
from threading import Lock

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from loguru import logger


# 白名单IP列表（不限流）
WHITELIST_IPS = {"127.0.0.1", "::1"}

# 默认限流配置
DEFAULT_MINUTE_LIMIT = 60    # 每分钟最大请求数
DEFAULT_HOUR_LIMIT = 1000    # 每小时最大请求数


class SlidingWindowCounter:
    """滑动窗口计数器"""

    def __init__(self):
        # {ip: [(timestamp, count), ...]}
        self._minute_windows: dict[str, list[float]] = defaultdict(list)
        self._hour_windows: dict[str, list[float]] = defaultdict(list)
        self._lock = Lock()

    def _cleanup(self, records: list[float], window_seconds: float) -> list[float]:
        """清理过期记录"""
        cutoff = time.time() - window_seconds
        return [t for t in records if t > cutoff]

    def check_and_record(
        self,
        ip: str,
        minute_limit: int = DEFAULT_MINUTE_LIMIT,
        hour_limit: int = DEFAULT_HOUR_LIMIT,
    ) -> tuple[bool, dict]:
        """
        检查IP是否超限，如果没超限则记录本次请求。

        返回: (是否允许, 限流信息dict)
        """
        now = time.time()

        with self._lock:
            # 清理过期记录
            self._minute_windows[ip] = self._cleanup(self._minute_windows[ip], 60)
            self._hour_windows[ip] = self._cleanup(self._hour_windows[ip], 3600)

            minute_count = len(self._minute_windows[ip])
            hour_count = len(self._hour_windows[ip])

            info = {
                "minute_remaining": max(0, minute_limit - minute_count),
                "hour_remaining": max(0, hour_limit - hour_count),
                "minute_limit": minute_limit,
                "hour_limit": hour_limit,
            }

            # 检查是否超限
            if minute_count >= minute_limit:
                info["exceeded"] = "minute"
                info["retry_after"] = 60
                return False, info

            if hour_count >= hour_limit:
                info["exceeded"] = "hour"
                info["retry_after"] = 3600
                return False, info

            # 记录本次请求
            self._minute_windows[ip].append(now)
            self._hour_windows[ip].append(now)

            return True, info


# 全局计数器实例
_counter = SlidingWindowCounter()


class IPRateLimitMiddleware(BaseHTTPMiddleware):
    """基于IP的滑动窗口限流中间件"""

    def __init__(
        self,
        app,
        minute_limit: int = DEFAULT_MINUTE_LIMIT,
        hour_limit: int = DEFAULT_HOUR_LIMIT,
    ):
        super().__init__(app)
        self.minute_limit = minute_limit
        self.hour_limit = hour_limit

    async def dispatch(self, request: Request, call_next):
        # 获取客户端IP
        client_ip = request.client.host if request.client else "unknown"

        # 白名单IP不限流
        if client_ip in WHITELIST_IPS:
            return await call_next(request)

        # 静态资源和健康检查不限流
        path = request.url.path
        if path.startswith("/static") or path == "/health" or path == "/docs" or path == "/redoc":
            return await call_next(request)

        # 检查限流
        allowed, info = _counter.check_and_record(
            client_ip,
            minute_limit=self.minute_limit,
            hour_limit=self.hour_limit,
        )

        if not allowed:
            exceeded = info.get("exceeded", "minute")
            retry_after = info.get("retry_after", 60)
            logger.warning(f"IP限流触发: {client_ip} 超过{exceeded}限制")
            return JSONResponse(
                status_code=429,
                content={
                    "error": "Too Many Requests",
                    "detail": f"请求频率超限（{exceeded}级别），请稍后重试",
                    "retry_after": retry_after,
                },
                headers={"Retry-After": str(retry_after)},
            )

        # 正常请求，添加限流信息到响应头
        response = await call_next(request)
        response.headers["X-RateLimit-Remaining-Minute"] = str(info["minute_remaining"])
        response.headers["X-RateLimit-Remaining-Hour"] = str(info["hour_remaining"])
        return response
