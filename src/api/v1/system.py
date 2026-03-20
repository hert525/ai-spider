"""System API - stats, logs, settings."""
from fastapi import APIRouter
from src.core.config import settings, BASE_DIR
from src.core.database import db
from src.scheduler.task_manager import task_manager
from src.scheduler.worker import worker_manager

router = APIRouter()


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


@router.get("/system/logs")
async def system_logs(limit: int = 100):
    log_path = BASE_DIR / "data" / "app.log"
    if not log_path.exists():
        return {"lines": []}
    lines = log_path.read_text("utf-8").strip().split("\n")
    return {"lines": lines[-limit:]}


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
