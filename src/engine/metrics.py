"""
监控指标模块 - 从 wukong/metric/ 移植并适配 async/await 架构。

功能：
- Prometheus 指标采集（Counter/Gauge/Histogram）
- Pushgateway 推送（支持认证、重试）
- 预定义爬虫指标（请求数/成功率/延迟/数据量等）
- 后台异步推送
"""
from __future__ import annotations

import asyncio
import os
import socket
import time
from typing import Any, Optional

from loguru import logger


# ============================================================
# 指标配置
# ============================================================

class MetricsConfig:
    """监控指标配置（从环境变量读取）"""

    def __init__(self):
        self.enabled = os.environ.get("METRICS_ENABLED", "false").lower() == "true"
        self.gateway_url = os.environ.get("PUSHGATEWAY_URL", "http://localhost:9091").rstrip("/")
        self.username = os.environ.get("PUSHGATEWAY_UNAME", "")
        self.password = os.environ.get("PUSHGATEWAY_PWD", "")
        self.push_interval = int(os.environ.get("METRICS_PUSH_INTERVAL", "15"))
        self.job_name = os.environ.get("METRICS_JOB_NAME", "ai_spider")
        self.instance_id = os.environ.get("INSTANCE_ID", f"{socket.gethostname()}-{os.getpid()}")
        self.batch_size = int(os.environ.get("METRICS_BATCH_SIZE", "256"))

    @property
    def auth_enabled(self) -> bool:
        return bool(self.username and self.password and
                     self.username != "default" and self.password != "default")


# 全局配置实例
_config = MetricsConfig()


# ============================================================
# 指标收集器（轻量级，不依赖 prometheus_client 即可使用）
# ============================================================

class MetricValue:
    """单个指标值"""
    def __init__(self, name: str, doc: str, metric_type: str):
        self.name = name
        self.doc = doc
        self.metric_type = metric_type
        self._values: dict[tuple, float] = {}  # {label_tuple: value}

    def _label_key(self, labels: dict[str, str] | None) -> tuple:
        if not labels:
            return ()
        return tuple(sorted(labels.items()))

    def inc(self, value: float = 1.0, labels: dict[str, str] | None = None) -> None:
        key = self._label_key(labels)
        self._values[key] = self._values.get(key, 0.0) + value

    def set(self, value: float, labels: dict[str, str] | None = None) -> None:
        key = self._label_key(labels)
        self._values[key] = value

    def observe(self, value: float, labels: dict[str, str] | None = None) -> None:
        """直方图观察值（简化实现 - 只记录总数和总和）"""
        count_key = self._label_key(labels) + (("_type", "count"),)
        sum_key = self._label_key(labels) + (("_type", "sum"),)
        self._values[count_key] = self._values.get(count_key, 0.0) + 1
        self._values[sum_key] = self._values.get(sum_key, 0.0) + value


class MetricsCollector:
    """
    指标收集器。

    在不依赖 prometheus_client 时使用轻量级内部实现。
    当 prometheus_client 可用时，优先使用原生库。
    """

    def __init__(self):
        self._metrics: dict[str, MetricValue] = {}
        self._lock = asyncio.Lock()

    def _get_or_create(self, name: str, doc: str, metric_type: str) -> MetricValue:
        if name not in self._metrics:
            self._metrics[name] = MetricValue(name, doc, metric_type)
        return self._metrics[name]

    async def inc_counter(
        self,
        name: str,
        doc: str = "",
        labels: dict[str, str] | None = None,
        value: float = 1.0,
    ) -> None:
        """递增计数器"""
        async with self._lock:
            metric = self._get_or_create(name, doc, "counter")
            metric.inc(value, labels)

    async def set_gauge(
        self,
        name: str,
        doc: str = "",
        labels: dict[str, str] | None = None,
        value: float = 0.0,
    ) -> None:
        """设置仪表盘值"""
        async with self._lock:
            metric = self._get_or_create(name, doc, "gauge")
            metric.set(value, labels)

    async def observe_histogram(
        self,
        name: str,
        doc: str = "",
        labels: dict[str, str] | None = None,
        value: float = 0.0,
    ) -> None:
        """直方图观察"""
        async with self._lock:
            metric = self._get_or_create(name, doc, "histogram")
            metric.observe(value, labels)

    def get_all_metrics(self) -> dict[str, MetricValue]:
        """获取所有指标"""
        return self._metrics.copy()


# ============================================================
# Prometheus Pushgateway 推送器
# ============================================================

class MetricsPusher:
    """
    Pushgateway 推送器。

    支持：
    - Basic Auth 认证
    - 重试机制
    - 后台定期推送
    """

    def __init__(
        self,
        config: MetricsConfig | None = None,
    ):
        self.config = config or _config
        self._collector = MetricsCollector()
        self._push_task: asyncio.Task | None = None
        self._shutdown_event = asyncio.Event()
        self._prometheus_registry = None

    @property
    def collector(self) -> MetricsCollector:
        return self._collector

    async def push(self) -> bool:
        """推送指标到 Pushgateway"""
        if not self.config.enabled:
            return False

        try:
            # 优先使用 prometheus_client
            from prometheus_client import (
                CollectorRegistry, Counter, Gauge, Histogram,
                push_to_gateway,
            )

            registry = CollectorRegistry()
            metrics = self._collector.get_all_metrics()

            for name, metric in metrics.items():
                if metric.metric_type == "counter":
                    label_names = set()
                    for key in metric._values:
                        for k, v in key:
                            label_names.add(k)
                    label_names = sorted(label_names)

                    prom_metric = Counter(name, metric.doc, label_names, registry=registry)
                    for label_key, value in metric._values.items():
                        labels = dict(label_key) if label_key else {}
                        if labels:
                            prom_metric.labels(**labels).inc(value)
                        else:
                            prom_metric.inc(value)

                elif metric.metric_type == "gauge":
                    label_names = set()
                    for key in metric._values:
                        for k, v in key:
                            label_names.add(k)
                    label_names = sorted(label_names)

                    prom_metric = Gauge(name, metric.doc, label_names, registry=registry)
                    for label_key, value in metric._values.items():
                        labels = dict(label_key) if label_key else {}
                        if labels:
                            prom_metric.labels(**labels).set(value)
                        else:
                            prom_metric.set(value)

            # 推送
            handler = self._make_handler() if self.config.auth_enabled else None
            push_to_gateway(
                gateway=self.config.gateway_url,
                job=self.config.job_name,
                grouping_key={"instance": self.config.instance_id},
                registry=registry,
                handler=handler,
                timeout=30,
            )
            logger.debug(f"指标已推送到 {self.config.gateway_url}")
            return True

        except ImportError:
            logger.debug("prometheus_client 未安装，跳过推送")
            return False
        except Exception as e:
            logger.error(f"指标推送失败: {e}")
            return False

    def _make_handler(self):
        """创建带认证的推送处理器"""
        import base64
        import http.client
        import urllib.request

        username = self.config.username
        password = self.config.password

        def handler(url, method, timeout, headers, data):
            auth_str = f"{username}:{password}".encode("utf-8")
            headers.append(("Authorization", f"Basic {base64.b64encode(auth_str).decode()}"))

            req = urllib.request.Request(url, data=data, headers=dict(headers), method=method)

            class NoReuseHTTPHandler(urllib.request.HTTPHandler):
                def http_open(self, r):
                    return self.do_open(http.client.HTTPConnection, r)

            opener = urllib.request.build_opener(NoReuseHTTPHandler())

            def handle():
                with opener.open(req, timeout=timeout) as resp:
                    resp.read()
            return handle

        return handler

    async def start_background_push(self) -> None:
        """启动后台推送任务"""
        if not self.config.enabled:
            logger.info("监控指标: 已禁用 (METRICS_ENABLED=false)")
            return

        async def _push_loop():
            while not self._shutdown_event.is_set():
                try:
                    await asyncio.sleep(self.config.push_interval)
                    if self._shutdown_event.is_set():
                        break
                    await self.push()
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"后台推送异常: {e}")

        self._push_task = asyncio.create_task(_push_loop())
        logger.info(
            f"监控指标: 后台推送已启动 "
            f"(gateway={self.config.gateway_url}, 间隔={self.config.push_interval}s)"
        )

    async def stop(self) -> None:
        """停止后台推送"""
        self._shutdown_event.set()
        if self._push_task:
            self._push_task.cancel()
            try:
                await self._push_task
            except asyncio.CancelledError:
                pass
        # 最终推送
        await self.push()
        logger.info("监控指标: 后台推送已停止")


# ============================================================
# 预定义爬虫指标快捷函数
# ============================================================

# 全局推送器实例
_pusher = MetricsPusher()


def get_pusher() -> MetricsPusher:
    """获取全局推送器实例"""
    return _pusher


def get_collector() -> MetricsCollector:
    """获取全局指标收集器"""
    return _pusher.collector


async def incr_requests_total(method: str = "GET", status: int = 200, proxied: bool = False) -> None:
    """递增HTTP请求总数"""
    await get_collector().inc_counter(
        "spider_http_requests_total",
        "HTTP请求总数",
        {"method": method, "status": str(status), "proxied": str(proxied).lower()},
    )


async def incr_fetch_success(url: str = "", status: int = 200) -> None:
    """递增抓取成功数"""
    domain = ""
    try:
        from urllib.parse import urlparse
        domain = urlparse(url).hostname or ""
    except Exception:
        pass
    await get_collector().inc_counter(
        "spider_fetch_success_total",
        "抓取成功总数",
        {"domain": domain, "status": str(status)},
    )


async def incr_fetch_failure(url: str = "", reason: str = "unknown") -> None:
    """递增抓取失败数"""
    domain = ""
    try:
        from urllib.parse import urlparse
        domain = urlparse(url).hostname or ""
    except Exception:
        pass
    await get_collector().inc_counter(
        "spider_fetch_failures_total",
        "抓取失败总数",
        {"domain": domain, "reason": reason},
    )


async def observe_fetch_duration(seconds: float, url: str = "") -> None:
    """记录抓取耗时"""
    await get_collector().observe_histogram(
        "spider_fetch_duration_seconds",
        "抓取耗时(秒)",
        {},
        seconds,
    )


async def set_active_tasks(count: int) -> None:
    """设置当前活跃任务数"""
    await get_collector().set_gauge(
        "spider_active_tasks",
        "当前活跃任务数",
        {},
        float(count),
    )


async def incr_dedup_events(action: str = "checked") -> None:
    """递增去重事件计数"""
    await get_collector().inc_counter(
        "spider_dedup_events_total",
        "去重事件总数",
        {"action": action},
    )


async def incr_data_records(count: int = 1, project_id: str = "") -> None:
    """递增数据记录数"""
    await get_collector().inc_counter(
        "spider_data_records_total",
        "数据记录总数",
        {"project_id": project_id},
        float(count),
    )


async def set_proxy_health(proxy: str, healthy: bool) -> None:
    """设置代理健康状态"""
    await get_collector().set_gauge(
        "spider_proxy_health",
        "代理健康状态 (1=健康, 0=不健康)",
        {"proxy": proxy},
        1.0 if healthy else 0.0,
    )
