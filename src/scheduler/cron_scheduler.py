"""Cron task scheduler - checks for due cron tasks and enqueues them."""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

from loguru import logger

from src.core.database import db
from src.scheduler.queue import task_queue


class CronScheduler:
    """Background scheduler that checks cron tasks every 60 seconds."""

    def __init__(self):
        self._running = False
        self._task: asyncio.Task | None = None

    async def start(self):
        self._running = True
        self._task = asyncio.create_task(self._loop())
        logger.info("CronScheduler started")

    async def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("CronScheduler stopped")

    async def _loop(self):
        while self._running:
            try:
                await self._check_and_enqueue()
            except Exception as e:
                logger.error(f"CronScheduler error: {e}")
            await asyncio.sleep(60)

    async def _check_and_enqueue(self):
        """Find cron tasks that are due and enqueue them."""
        cron_tasks = await db.query(
            "SELECT * FROM tasks WHERE task_type='cron' AND status NOT IN ('running', 'cancelled')"
        )

        now = datetime.now(timezone.utc)
        for task in cron_tasks:
            cron_expr = task.get("cron_expr", "")
            if not cron_expr:
                continue

            if self._is_due(cron_expr, now):
                logger.info(f"Cron task {task['id']} is due, enqueuing")
                await db.update("tasks", task["id"], {
                    "status": "queued",
                    "last_run_at": now.isoformat(),
                    "next_run_at": self._calc_next_run(cron_expr, now),
                    "updated_at": now.isoformat(),
                })
                await task_queue.enqueue(task["id"], task.get("priority", 5))

    def _is_due(self, cron_expr: str, now: datetime | None = None) -> bool:
        """Check if cron expression matches current time.

        Standard 5-field cron: minute hour day month weekday
        Supports: * */N N N,M N-M
        """
        if now is None:
            now = datetime.now(timezone.utc)

        parts = cron_expr.strip().split()
        if len(parts) != 5:
            logger.warning(f"Invalid cron expression: {cron_expr}")
            return False

        current = [now.minute, now.hour, now.day, now.month, now.isoweekday() % 7]
        # isoweekday: Mon=1..Sun=7, %7 gives Mon=1..Sat=6,Sun=0 (standard cron: Sun=0)
        ranges = [(0, 59), (0, 23), (1, 31), (1, 12), (0, 6)]

        for field, val, (lo, hi) in zip(parts, current, ranges):
            if not self._field_matches(field, val, lo, hi):
                return False
        return True

    def _field_matches(self, field: str, value: int, lo: int, hi: int) -> bool:
        """Check if a single cron field matches the given value."""
        for item in field.split(","):
            if self._item_matches(item.strip(), value, lo, hi):
                return True
        return False

    def _item_matches(self, item: str, value: int, lo: int, hi: int) -> bool:
        if item == "*":
            return True

        if item.startswith("*/"):
            step = int(item[2:])
            return step > 0 and (value - lo) % step == 0

        if "-" in item:
            a, b = item.split("-", 1)
            return int(a) <= value <= int(b)

        return value == int(item)

    def _calc_next_run(self, cron_expr: str, now: datetime) -> str:
        """Calculate approximate next run time by scanning forward minute-by-minute."""
        candidate = now.replace(second=0, microsecond=0) + timedelta(minutes=1)
        # Scan up to 48 hours ahead
        for _ in range(48 * 60):
            if self._is_due(cron_expr, candidate):
                return candidate.isoformat()
            candidate += timedelta(minutes=1)
        return ""


cron_scheduler = CronScheduler()
