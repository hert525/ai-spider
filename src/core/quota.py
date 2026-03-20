"""User quota and rate limiting."""
from __future__ import annotations

import time
from collections import defaultdict

from loguru import logger


class QuotaManager:
    """Manage user quotas: daily tasks, storage, API rate limits."""

    def __init__(self):
        self._rate_limits: dict[str, list[float]] = defaultdict(list)

    async def check_rate_limit(self, user_id: str, limit: int = 60, window: int = 60) -> bool:
        """Check if user exceeded rate limit. Returns True if allowed."""
        now = time.time()
        self._rate_limits[user_id] = [t for t in self._rate_limits[user_id] if now - t < window]
        if len(self._rate_limits[user_id]) >= limit:
            return False
        self._rate_limits[user_id].append(now)
        return True

    async def check_daily_quota(self, user_id: str) -> dict:
        """Check user's daily task quota."""
        from datetime import date, timedelta
        from src.core.database import db

        today = date.today()
        next_day = today + timedelta(days=1)
        rows = await db.query(
            "SELECT COUNT(*) as cnt FROM tasks WHERE user_id = ? AND created_at >= ? AND created_at < ?",
            [user_id, f"{today.isoformat()}T00:00:00", f"{next_day.isoformat()}T00:00:00"],
        )
        used = rows[0]["cnt"] if rows else 0

        user_rows = await db.query(
            "SELECT daily_task_limit, storage_limit_mb FROM users WHERE id = ?", [user_id]
        )
        daily_limit = 100
        if user_rows and user_rows[0].get("daily_task_limit"):
            daily_limit = user_rows[0]["daily_task_limit"]

        return {
            "daily_tasks_used": used,
            "daily_tasks_limit": daily_limit,
            "remaining": max(0, daily_limit - used),
            "allowed": used < daily_limit,
        }

    async def check_storage_quota(self, user_id: str) -> dict:
        """Check user's storage usage."""
        from src.core.database import db

        rows = await db.query(
            "SELECT SUM(LENGTH(data)) as total FROM data_records WHERE task_id IN (SELECT id FROM tasks WHERE user_id = ?)",
            [user_id],
        )
        used_bytes = rows[0]["total"] if rows and rows[0]["total"] else 0

        user_rows = await db.query("SELECT storage_limit_mb FROM users WHERE id = ?", [user_id])
        limit_mb = 500
        if user_rows and user_rows[0].get("storage_limit_mb"):
            limit_mb = user_rows[0]["storage_limit_mb"]

        used_mb = used_bytes / (1024 * 1024)
        return {
            "used_mb": round(used_mb, 2),
            "limit_mb": limit_mb,
            "remaining_mb": round(max(0, limit_mb - used_mb), 2),
            "allowed": used_mb < limit_mb,
        }


quota_manager = QuotaManager()
