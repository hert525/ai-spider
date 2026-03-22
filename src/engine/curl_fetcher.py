"""
curl_cffi 请求引擎 — 从 wukong/core/pure.py 移植并适配 async 架构。

核心能力：
- 基于 curl_cffi 的 TLS 指纹模拟（impersonate Chrome/Firefox/Safari）
- 连接池复用 + TCP Keep-Alive
- 慢连接检测 + 最大文件限制
- 自动重试（指数退避）+ 代理轮换
- 异步接口，兼容 AI Spider 架构

与 httpx FetchNode 的关系：
- httpx 用于常规请求（大部分网站够用）
- curl_cffi 用于反爬严格的网站（Cloudflare/Akamai等TLS指纹检测）
- FetchNode 在 httpx 失败时自动 fallback 到 curl_cffi
"""
from __future__ import annotations

import asyncio
import os
import random
import time
from dataclasses import dataclass, field
from typing import Any, Optional
from urllib.parse import urlparse

from loguru import logger

try:
    import curl_cffi
    import curl_cffi.requests
    from curl_cffi.requests.exceptions import RequestException
    HAS_CURL_CFFI = True
except ImportError:
    HAS_CURL_CFFI = False


# ---- 支持的浏览器指纹 ----
BROWSER_FINGERPRINTS = [
    "chrome",
    "chrome110",
    "chrome116",
    "chrome120",
    "chrome131",
    "safari",
    "safari_ios",
    "firefox",
]


@dataclass
class CurlResponse:
    """统一的响应对象"""
    url: str = ""
    status_code: int = 0
    headers: dict = field(default_factory=dict)
    text: str = ""
    content: bytes = b""
    ok: bool = False
    elapsed_ms: float = 0.0
    proxy_used: str | None = None
    error: str | None = None
    fingerprint: str = "chrome"

    @property
    def json(self) -> Any:
        """解析JSON响应"""
        import json
        return json.loads(self.text)


class CurlFetcher:
    """
    基于 curl_cffi 的异步请求引擎。

    特性：
    - TLS指纹模拟（绕过Cloudflare/Akamai检测）
    - 连接池复用
    - 自动重试 + 代理切换
    - 慢连接保护

    用法::

        fetcher = CurlFetcher()
        resp = await fetcher.get("https://example.com")
        print(resp.status_code, resp.text[:100])
        fetcher.close()
    """

    def __init__(
        self,
        fingerprint: str = "chrome",
        connect_timeout: int = 30,
        request_timeout: int = 60,
        max_retries: int = 3,
        max_file_size: int = 10 * 1024 * 1024,  # 10MB
        max_connects: int = 10,
        proxy_url: str | None = None,
        proxy_list: list[str] | None = None,
        rotate_fingerprint: bool = False,
    ):
        if not HAS_CURL_CFFI:
            raise ImportError("curl_cffi 未安装，运行: pip install curl_cffi")

        self.fingerprint = fingerprint
        self.connect_timeout = connect_timeout
        self.request_timeout = request_timeout
        self.max_retries = max_retries
        self.max_file_size = max_file_size
        self.max_connects = max_connects
        self.proxy_url = proxy_url
        self.proxy_list = proxy_list or []
        self.rotate_fingerprint = rotate_fingerprint

        # 统计
        self._total_requests = 0
        self._total_success = 0
        self._total_failures = 0

        # 创建 session
        self._session = self._create_session()

    def _create_session(self) -> curl_cffi.requests.Session:
        """创建并配置 curl_cffi Session（连接池 + 超时 + Keep-Alive）"""
        curl_options = {
            curl_cffi.CurlOpt.CONNECTTIMEOUT: self.connect_timeout,
            curl_cffi.CurlOpt.TIMEOUT: self.request_timeout,
            # 慢连接检测：传输速率 < 1 byte/s 持续 60s 则中断
            curl_cffi.CurlOpt.LOW_SPEED_LIMIT: 1,
            curl_cffi.CurlOpt.LOW_SPEED_TIME: 60,
            # 文件大小限制
            curl_cffi.CurlOpt.MAXFILESIZE: self.max_file_size,
            # 连接池
            curl_cffi.CurlOpt.MAXCONNECTS: self.max_connects,
            curl_cffi.CurlOpt.FAILONERROR: False,
            # TCP Keep-Alive
            curl_cffi.CurlOpt.TCP_KEEPALIVE: 1,
            curl_cffi.CurlOpt.TCP_KEEPIDLE: 60,
            curl_cffi.CurlOpt.TCP_KEEPINTVL: 10,
        }

        session = curl_cffi.requests.Session(
            impersonate=self.fingerprint,
            timeout=self.request_timeout,
            curl_options=curl_options,
        )

        logger.debug(
            f"CurlFetcher: 创建Session fingerprint={self.fingerprint}, "
            f"connect_timeout={self.connect_timeout}s, "
            f"max_connects={self.max_connects}"
        )
        return session

    def _get_fingerprint(self) -> str:
        """获取浏览器指纹（支持轮换）"""
        if self.rotate_fingerprint:
            return random.choice(BROWSER_FINGERPRINTS)
        return self.fingerprint

    def _get_proxy(self, retry: int = 0) -> dict[str, str] | None:
        """获取代理配置（支持轮换）"""
        if self.proxy_list:
            idx = retry % len(self.proxy_list)
            proxy = self.proxy_list[idx]
            return {"http": proxy, "https": proxy}
        if self.proxy_url:
            return {"http": self.proxy_url, "https": self.proxy_url}
        return None

    async def get(self, url: str, **kwargs) -> CurlResponse:
        """异步 GET 请求"""
        return await self.request("GET", url, **kwargs)

    async def post(self, url: str, **kwargs) -> CurlResponse:
        """异步 POST 请求"""
        return await self.request("POST", url, **kwargs)

    async def request(
        self,
        method: str,
        url: str,
        headers: dict | None = None,
        cookies: dict | None = None,
        data: Any = None,
        json_data: Any = None,
        max_retries: int | None = None,
        **kwargs,
    ) -> CurlResponse:
        """
        执行HTTP请求（带自动重试 + 代理轮换）。

        在线程池中运行 curl_cffi（它是同步的），不阻塞事件循环。
        """
        retries = max_retries if max_retries is not None else self.max_retries
        last_error = None

        for attempt in range(retries):
            proxy = self._get_proxy(attempt)
            fp = self._get_fingerprint()
            start = time.monotonic()

            try:
                # curl_cffi 是同步的，在线程池中执行
                resp = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: self._sync_request(
                        method=method,
                        url=url,
                        headers=headers,
                        cookies=cookies,
                        data=data,
                        json_data=json_data,
                        proxies=proxy,
                        impersonate=fp,
                    ),
                )

                elapsed = (time.monotonic() - start) * 1000
                self._total_requests += 1

                result = CurlResponse(
                    url=url,
                    status_code=resp.status_code,
                    headers=dict(resp.headers) if resp.headers else {},
                    text=resp.text or "",
                    content=resp.content or b"",
                    ok=200 <= resp.status_code < 400,
                    elapsed_ms=elapsed,
                    proxy_used=list(proxy.values())[0] if proxy else None,
                    fingerprint=fp,
                )

                if result.ok:
                    self._total_success += 1
                    return result

                # 非200但有响应，某些情况可以返回（如403检测）
                if resp.status_code in (403, 503):
                    logger.warning(
                        f"CurlFetcher: {method} {url} → {resp.status_code} "
                        f"(attempt {attempt + 1}/{retries}, fp={fp})"
                    )
                    last_error = f"HTTP {resp.status_code}"
                    # 重试前等待（指数退避）
                    if attempt < retries - 1:
                        wait = min(2 ** attempt + random.random(), 10)
                        await asyncio.sleep(wait)
                    continue

                # 其他状态码直接返回
                self._total_success += 1
                return result

            except Exception as e:
                elapsed = (time.monotonic() - start) * 1000
                self._total_requests += 1
                self._total_failures += 1
                error_type = type(e).__name__
                last_error = f"{error_type}: {e}"

                logger.warning(
                    f"CurlFetcher: {method} {url} → {error_type} "
                    f"(attempt {attempt + 1}/{retries}, {elapsed:.0f}ms)"
                )

                # 指数退避
                if attempt < retries - 1:
                    wait = min(2 ** attempt + random.random(), 10)
                    await asyncio.sleep(wait)

        # 全部重试失败
        return CurlResponse(
            url=url,
            status_code=0,
            ok=False,
            error=last_error,
        )

    def _sync_request(
        self,
        method: str,
        url: str,
        headers: dict | None = None,
        cookies: dict | None = None,
        data: Any = None,
        json_data: Any = None,
        proxies: dict | None = None,
        impersonate: str = "chrome",
    ):
        """同步执行单次请求（供线程池调用）"""
        return self._session.request(
            method=method,
            url=url,
            headers=headers,
            cookies=cookies,
            data=data,
            json=json_data,
            proxies=proxies,
            impersonate=impersonate,
            timeout=self.request_timeout,
        )

    def stats(self) -> dict:
        """返回统计信息"""
        return {
            "total_requests": self._total_requests,
            "total_success": self._total_success,
            "total_failures": self._total_failures,
            "success_rate": (
                round(self._total_success / self._total_requests * 100, 1)
                if self._total_requests > 0
                else 0
            ),
        }

    def close(self):
        """关闭session释放连接池"""
        if self._session:
            try:
                self._session.close()
            except Exception:
                pass


# ---- 全局单例 ----
_default_fetcher: CurlFetcher | None = None


def get_curl_fetcher(**kwargs) -> CurlFetcher:
    """获取全局 CurlFetcher 实例"""
    global _default_fetcher
    if _default_fetcher is None:
        _default_fetcher = CurlFetcher(**kwargs)
    return _default_fetcher
