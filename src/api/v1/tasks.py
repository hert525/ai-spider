"""Tasks API."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from src.core.database import db
from src.core.models import Task, TaskType, TaskStatus
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
async def list_tasks(project_id: str = "", status: str = ""):
    where = {}
    if project_id:
        where["project_id"] = project_id
    if status:
        where["status"] = status
    rows = await db.list("tasks", where=where or None)
    return rows


@router.post("/tasks")
async def create_task(req: CreateTaskReq):
    proj = await db.get("projects", req.project_id)
    if not proj:
        raise HTTPException(400, "Project not found")

    urls = req.target_urls or ([proj.get("target_url")] if proj.get("target_url") else [])
    task = Task(
        project_id=req.project_id,
        name=req.name or proj.get("name", ""),
        task_type=TaskType(req.task_type),
        target_urls=urls,
        max_pages=req.max_pages,
        max_items=req.max_items,
        timeout_seconds=req.timeout_seconds,
        concurrency=req.concurrency,
        priority=req.priority,
        cron_expr=req.cron_expr,
    )
    await task_manager.create_task(task)
    return task.model_dump()


@router.get("/tasks/{tid}")
async def get_task(tid: str):
    task = await db.get("tasks", tid)
    if not task:
        raise HTTPException(404)
    return task


@router.get("/tasks/{tid}/runs")
async def get_task_runs(tid: str):
    runs = await task_manager.get_runs(tid)
    return [r.model_dump() for r in runs]


@router.post("/tasks/{tid}/cancel")
async def cancel_task(tid: str):
    await task_manager.update_task(tid, status=TaskStatus.CANCELLED)
    return {"ok": True}


@router.post("/tasks/{tid}/retry")
async def retry_task(tid: str):
    await task_manager.queue_task(tid)
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
