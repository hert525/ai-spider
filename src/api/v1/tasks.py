"""Tasks API."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from src.core.database import db
from src.core.models import TaskStatus
from src.core.auth import get_current_user
from src.scheduler.task_manager import task_manager

router = APIRouter()


class CreateTaskReq(BaseModel):
    project_id: str
    name: str = ""
    target_urls: list[str] = []
    task_type: str = "one_time"
    cron_expr: str = ""
    max_pages: int = 100
    max_items: int = 10000
    timeout_seconds: int = 300
    concurrency: int = 3
    priority: int = 5


@router.get("/tasks")
async def list_tasks(project_id: str = "", status: str = "", user: dict = Depends(get_current_user)):
    where = {}
    if project_id:
        where["project_id"] = project_id
    if status:
        where["status"] = status
    if user.get("role") != "admin":
        where["user_id"] = user["id"]
    rows = await db.list("tasks", where=where or None)
    return rows


@router.post("/tasks")
async def create_task(req: CreateTaskReq, user: dict = Depends(get_current_user)):
    # Check daily quota
    from src.core.quota import quota_manager
    quota = await quota_manager.check_daily_quota(user.get("id", ""))
    if not quota["allowed"]:
        raise HTTPException(429, f"Daily task limit reached ({quota['daily_tasks_limit']})")

    proj = await db.get("projects", req.project_id)
    if not proj:
        raise HTTPException(400, "Project not found")

    urls = req.target_urls or ([proj.get("target_url")] if proj.get("target_url") else [])

    task_data = await task_manager.create_task(
        project_id=req.project_id,
        user_id=user.get("id", ""),
        task_type=req.task_type,
        target_urls=urls,
        priority=req.priority,
        cron_expr=req.cron_expr,
        max_pages=req.max_pages,
        max_items=req.max_items,
        timeout_seconds=req.timeout_seconds,
        concurrency=req.concurrency,
        name=req.name or proj.get("name", ""),
    )
    return task_data


@router.get("/tasks/{tid}")
async def get_task(tid: str, user: dict = Depends(get_current_user)):
    task = await db.get("tasks", tid)
    if not task:
        raise HTTPException(404)
    return task


@router.get("/tasks/{tid}/runs")
async def get_task_runs(tid: str, user: dict = Depends(get_current_user)):
    runs = await task_manager.get_runs(tid)
    return [r.model_dump() for r in runs]


@router.post("/tasks/{tid}/cancel")
async def cancel_task(tid: str):
    ok = await task_manager.cancel_task(tid)
    if not ok:
        raise HTTPException(404)
    return {"ok": True}


@router.post("/tasks/{tid}/retry")
async def retry_task(tid: str):
    ok = await task_manager.retry_task(tid)
    if not ok:
        raise HTTPException(404)
    return {"ok": True}


@router.post("/tasks/{tid}/pause")
async def pause_task(tid: str):
    await task_manager.update_task(tid, status=TaskStatus.PAUSED)
    return {"ok": True}


@router.delete("/tasks/{tid}")
async def delete_task(tid: str):
    if not await task_manager.delete_task(tid):
        raise HTTPException(404)
    return {"ok": True}


class BatchTaskIds(BaseModel):
    task_ids: list[str]


@router.post("/tasks/batch/cancel")
async def batch_cancel_tasks(body: BatchTaskIds, user: dict = Depends(get_current_user)):
    results = {"cancelled": 0, "failed": 0}
    for tid in body.task_ids:
        try:
            ok = await task_manager.cancel_task(tid)
            if ok:
                results["cancelled"] += 1
            else:
                results["failed"] += 1
        except Exception:
            results["failed"] += 1
    return results


@router.post("/tasks/batch/delete")
async def batch_delete_tasks(body: BatchTaskIds, user: dict = Depends(get_current_user)):
    results = {"deleted": 0, "failed": 0}
    for tid in body.task_ids:
        try:
            ok = await task_manager.delete_task(tid)
            if ok:
                results["deleted"] += 1
            else:
                results["failed"] += 1
        except Exception:
            results["failed"] += 1
    return results
