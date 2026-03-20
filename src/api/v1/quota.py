"""Quota API — usage, limits."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from src.core.auth import get_current_user
from src.core.quota import quota_manager

router = APIRouter(prefix="/quota", tags=["quota"])


@router.get("")
async def get_quota(user: dict = Depends(get_current_user)):
    """Get current user quota usage."""
    daily = await quota_manager.check_daily_quota(user["id"])
    storage = await quota_manager.check_storage_quota(user["id"])
    return {**daily, **storage}


@router.get("/usage")
async def get_usage(user: dict = Depends(get_current_user)):
    """Detailed usage stats by day."""
    from src.core.database import db

    # Last 7 days usage
    rows = await db.query(
        """SELECT DATE(created_at) as day, COUNT(*) as task_count
           FROM tasks WHERE user_id = ?
           GROUP BY DATE(created_at) ORDER BY day DESC LIMIT 7""",
        [user["id"]],
    )

    # Per-project usage
    project_rows = await db.query(
        """SELECT p.name, COUNT(t.id) as task_count
           FROM tasks t JOIN projects p ON t.project_id = p.id
           WHERE t.user_id = ?
           GROUP BY t.project_id ORDER BY task_count DESC LIMIT 10""",
        [user["id"]],
    )

    daily = await quota_manager.check_daily_quota(user["id"])
    storage = await quota_manager.check_storage_quota(user["id"])

    return {
        "quota": {**daily, **storage},
        "daily_usage": rows,
        "project_usage": project_rows,
    }
