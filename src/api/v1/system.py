"""System API - stats, logs, settings, info."""
from __future__ import annotations

import sys
import time

from fastapi import APIRouter, Depends
from loguru import logger

from src.core.config import settings, BASE_DIR
from src.core.database import db
from src.core.auth import require_admin
from src.scheduler.task_manager import task_manager
from src.scheduler.worker import worker_manager

router = APIRouter()

_start_time = time.time()


@router.get("/system/stats")
async def system_stats():
    task_stats = await task_manager.stats()
    worker_stats = await worker_manager.stats()
    project_count = await db.count("projects")
    data_count = await db.count("data_records")
    return {
        "projects": project_count,
        "data_records": data_count,
        "tasks": task_stats,
        "workers": worker_stats,
    }


@router.get("/system/info")
async def system_info(user: dict = Depends(require_admin)):
    redis_connected = False
    try:
        from src.scheduler.queue import task_queue
        if hasattr(task_queue, "redis") and task_queue.redis:
            await task_queue.redis.ping()
            redis_connected = True
    except Exception:
        pass

    total_projects = await db.count("projects")
    total_tasks = await db.count("tasks")
    total_workers = await db.count("workers")

    return {
        "version": "2.0.0",
        "uptime_seconds": int(time.time() - _start_time),
        "python_version": sys.version.split()[0],
        "redis_connected": redis_connected,
        "db_path": str(settings.db_path),
        "llm_model": getattr(settings, "llm_model", "unknown"),
        "total_projects": total_projects,
        "total_tasks": total_tasks,
        "total_workers": total_workers,
    }


@router.get("/system/logs")
async def system_logs(limit: int = 100, level: str = ""):
    log_path = BASE_DIR / "data" / "app.log"
    if not log_path.exists():
        return []
    lines = log_path.read_text("utf-8").strip().split("\n")
    results = []
    for line in reversed(lines):
        if len(results) >= limit:
            break
        # Parse loguru format: "2026-03-20 21:43:01.123 | INFO | ..."
        parts = line.split(" | ", 2)
        if len(parts) >= 3:
            log_time = parts[0].strip()
            log_level = parts[1].strip()
            log_msg = parts[2].strip()
        else:
            log_time = ""
            log_level = "INFO"
            log_msg = line
        if level and log_level != level.upper():
            continue
        results.append({"time": log_time, "level": log_level, "message": log_msg})
    return results


@router.get("/system/settings")
async def system_settings():
    return {
        "llm_model": settings.llm_model,
        "llm_provider": settings.llm_provider,
        "redis_url": settings.redis_url,
        "db_path": settings.db_path,
        "sandbox_timeout": settings.sandbox_timeout,
        "default_concurrency": settings.default_concurrency,
    }
