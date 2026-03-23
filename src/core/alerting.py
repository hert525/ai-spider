"""Alerting system — threshold-based alerts for crawl health.

Monitors:
- Task failure rate (> threshold → alert)
- Worker offline events
- Queue depth (too many pending tasks)
- Data quality (high null/error rates)
"""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Awaitable

from loguru import logger


@dataclass
class AlertRule:
    """A single alert rule."""
    name: str
    metric: str           # "task_failure_rate", "worker_offline", "queue_depth", "data_quality"
    threshold: float      # e.g., 30.0 for 30%
    operator: str = ">"   # >, <, >=, <=, ==
    window_seconds: int = 300  # Look-back window
    cooldown_seconds: int = 600  # Min time between same alerts
    severity: str = "warning"  # info, warning, critical
    enabled: bool = True
    last_fired: float = 0


@dataclass
class Alert:
    """A fired alert."""
    rule_name: str
    metric: str
    value: float
    threshold: float
    severity: str
    message: str
    fired_at: str = field(default_factory=lambda: datetime.now().isoformat())


class AlertManager:
    """Manages alert rules and fires notifications."""

    def __init__(self):
        self.rules: list[AlertRule] = []
        self._handlers: list[Callable[[Alert], Awaitable[None]]] = []
        self._history: list[Alert] = []  # Recent alerts
        self._max_history = 100

        # Default rules
        self.rules = [
            AlertRule(
                name="高失败率",
                metric="task_failure_rate",
                threshold=30.0,
                operator=">",
                window_seconds=600,
                cooldown_seconds=1800,
                severity="critical",
            ),
            AlertRule(
                name="Worker离线",
                metric="worker_offline",
                threshold=1,
                operator=">=",
                cooldown_seconds=300,
                severity="warning",
            ),
            AlertRule(
                name="队列积压",
                metric="queue_depth",
                threshold=50,
                operator=">",
                cooldown_seconds=900,
                severity="warning",
            ),
            AlertRule(
                name="数据质量低",
                metric="data_quality",
                threshold=50.0,  # null rate > 50%
                operator=">",
                window_seconds=300,
                cooldown_seconds=1800,
                severity="warning",
            ),
        ]

    def add_handler(self, handler: Callable[[Alert], Awaitable[None]]) -> None:
        """Register an alert handler (e.g., send to webhook, email, WS)."""
        self._handlers.append(handler)

    async def check_and_fire(self, metric: str, value: float,
                              context: str = "") -> Alert | None:
        """Check if any rule triggers for the given metric value."""
        now = time.time()
        for rule in self.rules:
            if not rule.enabled or rule.metric != metric:
                continue

            triggered = False
            if rule.operator == ">" and value > rule.threshold:
                triggered = True
            elif rule.operator == ">=" and value >= rule.threshold:
                triggered = True
            elif rule.operator == "<" and value < rule.threshold:
                triggered = True
            elif rule.operator == "<=" and value <= rule.threshold:
                triggered = True
            elif rule.operator == "==" and value == rule.threshold:
                triggered = True

            if triggered and (now - rule.last_fired) > rule.cooldown_seconds:
                rule.last_fired = now
                alert = Alert(
                    rule_name=rule.name,
                    metric=metric,
                    value=value,
                    threshold=rule.threshold,
                    severity=rule.severity,
                    message=f"⚠️ [{rule.severity.upper()}] {rule.name}: "
                            f"{metric}={value:.1f} (阈值{rule.operator}{rule.threshold}) "
                            f"{context}",
                )
                self._history.append(alert)
                if len(self._history) > self._max_history:
                    self._history = self._history[-self._max_history:]

                logger.warning(f"Alert fired: {alert.message}")

                # Notify all handlers
                for handler in self._handlers:
                    try:
                        await handler(alert)
                    except Exception as e:
                        logger.error(f"Alert handler error: {e}")

                return alert
        return None

    def get_history(self, limit: int = 50) -> list[dict]:
        """Get recent alert history."""
        return [
            {
                "rule_name": a.rule_name,
                "metric": a.metric,
                "value": a.value,
                "threshold": a.threshold,
                "severity": a.severity,
                "message": a.message,
                "fired_at": a.fired_at,
            }
            for a in reversed(self._history[:limit])
        ]

    def get_rules(self) -> list[dict]:
        """Get all alert rules."""
        return [
            {
                "name": r.name,
                "metric": r.metric,
                "threshold": r.threshold,
                "operator": r.operator,
                "severity": r.severity,
                "enabled": r.enabled,
                "cooldown_seconds": r.cooldown_seconds,
            }
            for r in self.rules
        ]


# Global instance
alert_manager = AlertManager()


# ── Default handler: WebSocket broadcast ──

async def ws_alert_handler(alert: Alert) -> None:
    """Broadcast alert to admin WebSocket clients."""
    try:
        from src.api.ws import ws_manager
        await ws_manager.broadcast_admin({
            "type": "alert",
            "alert": {
                "rule_name": alert.rule_name,
                "severity": alert.severity,
                "message": alert.message,
                "fired_at": alert.fired_at,
            },
        })
    except Exception:
        pass

alert_manager.add_handler(ws_alert_handler)
