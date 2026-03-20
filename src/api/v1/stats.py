"""Stats API for monitoring dashboard."""
from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends

from src.core.database import db
from src.core.auth import get_current_user

router = APIRouter(prefix="/stats", tags=["stats"])


@router.get("/overview")
async def overview(user: dict = Depends(get_current_user)):
    """系统总览统计"""
    now = datetime.now()
    day_ago = (now - timedelta(hours=24)).isoformat()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()

    total_users = await db.count("users")
    active_users = await db.query(
        "SELECT COUNT(DISTINCT user_id) as c FROM tasks WHERE updated_at >= ?", [day_ago]
    )
    total_projects = await db.count("projects")
    total_tasks = await db.count("tasks")
    tasks_today = await db.query(
        "SELECT COUNT(*) as c FROM tasks WHERE created_at >= ?", [today_start]
    )
    success_count = await db.count("tasks", {"status": "success"})
    failed_count = await db.count("tasks", {"status": "failed"})
    total_finished = success_count + failed_count
    success_rate = round(success_count / total_finished * 100, 1) if total_finished > 0 else 0

    total_data = await db.count("data_records")

    workers = await db.query(
        "SELECT COUNT(*) as c FROM workers WHERE last_heartbeat >= ?", [day_ago]
    )

    return {
        "total_users": total_users,
        "active_users_24h": active_users[0]["c"] if active_users else 0,
        "total_projects": total_projects,
        "total_tasks": total_tasks,
        "tasks_today": tasks_today[0]["c"] if tasks_today else 0,
        "tasks_success_rate": success_rate,
        "total_data_items": total_data,
        "active_workers": workers[0]["c"] if workers else 0,
    }


@router.get("/tasks/trend")
async def tasks_trend(days: int = 7, user: dict = Depends(get_current_user)):
    """任务趋势（最近N天）"""
    result = []
    now = datetime.now()
    for i in range(days - 1, -1, -1):
        day = now - timedelta(days=i)
        date_str = day.strftime("%Y-%m-%d")
        start = date_str + "T00:00:00"
        end = date_str + "T23:59:59"

        rows = await db.query(
            "SELECT status, COUNT(*) as c FROM tasks WHERE created_at >= ? AND created_at <= ? GROUP BY status",
            [start, end],
        )
        counts = {r["status"]: r["c"] for r in rows}
        result.append({
            "date": date_str,
            "total": sum(counts.values()),
            "success": counts.get("success", 0),
            "failed": counts.get("failed", 0),
        })
    return result


@router.get("/tasks/hourly")
async def tasks_hourly(user: dict = Depends(get_current_user)):
    """每小时任务分布"""
    today = datetime.now().strftime("%Y-%m-%d")
    rows = await db.query(
        "SELECT created_at FROM tasks WHERE created_at >= ?", [today + "T00:00:00"]
    )
    hourly = [0] * 24
    for r in rows:
        try:
            h = int(r["created_at"][11:13])
            hourly[h] += 1
        except (ValueError, IndexError, TypeError):
            pass
    return [{"hour": h, "count": c} for h, c in enumerate(hourly)]


@router.get("/projects/top")
async def top_projects(limit: int = 10, user: dict = Depends(get_current_user)):
    """热门项目"""
    rows = await db.query(
        """SELECT p.id as project_id, p.name,
                  COUNT(DISTINCT t.id) as task_count,
                  COUNT(DISTINCT d.id) as data_count
           FROM projects p
           LEFT JOIN tasks t ON t.project_id = p.id
           LEFT JOIN data_records d ON d.project_id = p.id
           GROUP BY p.id
           ORDER BY task_count DESC
           LIMIT ?""",
        [limit],
    )
    return rows


@router.get("/users/active")
async def active_users(days: int = 7, user: dict = Depends(get_current_user)):
    """用户活跃度"""
    since = (datetime.now() - timedelta(days=days)).isoformat()
    rows = await db.query(
        """SELECT u.id as user_id, u.username as name,
                  COUNT(t.id) as task_count,
                  MAX(t.updated_at) as last_active
           FROM users u
           LEFT JOIN tasks t ON t.user_id = u.id AND t.created_at >= ?
           GROUP BY u.id
           HAVING task_count > 0
           ORDER BY task_count DESC
           LIMIT 20""",
        [since],
    )
    return rows


@router.get("/workers/load")
async def workers_load(user: dict = Depends(get_current_user)):
    """Worker负载"""
    rows = await db.query(
        """SELECT id as worker_id, cpu_percent as cpu, memory_mb as memory,
                  total_completed as tasks_completed, registered_at as uptime,
                  status, active_jobs, last_heartbeat
           FROM workers ORDER BY last_heartbeat DESC"""
    )
    return rows
