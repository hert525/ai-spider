"""Tasks API."""
from __future__ import annotations

from src.core.database import db as _db
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from src.core.database import db
from src.core.models import TaskStatus
from src.core.auth import get_current_user
from src.scheduler.task_manager import task_manager

router = APIRouter()


async def _verify_task_owner(task_id: str, user_id: str):
    row = await _db.get("tasks", task_id)
    if not row:
        raise HTTPException(404, "Task not found")
    if True:
        if row["user_id"] != user_id:
            raise HTTPException(403, "Not your task")


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


# ── Dead Letter Queue & Queue Stats (must be before /tasks/{tid}) ──

@router.get("/tasks/dead-letters")
async def list_dead_letters(limit: int = 50, user: dict = Depends(get_current_user)):
    """List dead-letter tasks (exceeded max retries)."""
    from src.scheduler.queue import task_queue
    try:
        items = await task_queue.list_dead_letters(limit=limit)
        for item in items:
            tid = item.get("task_id", "")
            task = await db.get("tasks", tid)
            if task:
                item["name"] = task.get("name", "")
                item["project_id"] = task.get("project_id", "")
        return items
    except Exception:
        return []


class RetryDeadLetterReq(BaseModel):
    task_id: str
    priority: int = 5


@router.post("/tasks/dead-letters/retry")
async def retry_dead_letter(body: RetryDeadLetterReq, user: dict = Depends(get_current_user)):
    from src.scheduler.queue import task_queue
    ok = await task_queue.retry_dead_letter(body.task_id, body.priority)
    if ok:
        await db.update("tasks", body.task_id, {"status": "pending"})
        return {"ok": True}
    raise HTTPException(404, "Task not found in dead-letter queue")


@router.delete("/tasks/dead-letters")
async def clear_dead_letters(user: dict = Depends(get_current_user)):
    from src.scheduler.queue import task_queue
    count = await task_queue.clear_dead_letters()
    return {"cleared": count}


@router.get("/tasks/queue/stats")
async def queue_stats(user: dict = Depends(get_current_user)):
    from src.scheduler.queue import task_queue
    return await task_queue.stats()


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
async def cancel_task(tid: str, user: dict = Depends(get_current_user)):
    await _verify_task_owner(tid, user["id"])
    ok = await task_manager.cancel_task(tid)
    if not ok:
        raise HTTPException(404)
    return {"ok": True}


@router.post("/tasks/{tid}/retry")
async def retry_task(tid: str, user: dict = Depends(get_current_user)):
    await _verify_task_owner(tid, user["id"])
    ok = await task_manager.retry_task(tid)
    if not ok:
        raise HTTPException(404)
    return {"ok": True}


@router.post("/tasks/{tid}/pause")
async def pause_task(tid: str, user: dict = Depends(get_current_user)):
    await _verify_task_owner(tid, user["id"])
    await task_manager.update_task(tid, status=TaskStatus.PAUSED)
    return {"ok": True}


@router.delete("/tasks/{tid}")
async def delete_task(tid: str, user: dict = Depends(get_current_user)):
    await _verify_task_owner(tid, user["id"])
    if not await task_manager.delete_task(tid):
        raise HTTPException(404)
    return {"ok": True}


class BatchCreateItem(BaseModel):
    project_id: str
    config: dict = {}


class BatchCreateReq(BaseModel):
    tasks: list[BatchCreateItem]


@router.post("/tasks/batch")
async def batch_create_tasks(body: BatchCreateReq, user: dict = Depends(get_current_user)):
    """批量创建任务并入队"""
    from src.core.quota import quota_manager

    results = []
    for item in body.tasks:
        try:
            # 检查配额
            quota = await quota_manager.check_daily_quota(user.get("id", ""))
            if not quota["allowed"]:
                results.append({"project_id": item.project_id, "ok": False, "error": "每日任务配额已用完"})
                continue

            proj = await db.get("projects", item.project_id)
            if not proj:
                results.append({"project_id": item.project_id, "ok": False, "error": "项目不存在"})
                continue

            cfg = item.config
            urls = cfg.get("target_urls") or ([proj.get("target_url")] if proj.get("target_url") else [])

            task_data = await task_manager.create_task(
                project_id=item.project_id,
                user_id=user.get("id", ""),
                task_type=cfg.get("task_type", "one_time"),
                target_urls=urls,
                priority=cfg.get("priority", 5),
                cron_expr=cfg.get("cron_expr", ""),
                max_pages=cfg.get("max_pages", 100),
                max_items=cfg.get("max_items", 10000),
                timeout_seconds=cfg.get("timeout_seconds", 300),
                concurrency=cfg.get("concurrency", 3),
                name=cfg.get("name", proj.get("name", "")),
            )
            results.append({"project_id": item.project_id, "ok": True, "task": task_data})
        except Exception as e:
            results.append({"project_id": item.project_id, "ok": False, "error": str(e)[:120]})

    success_count = sum(1 for r in results if r.get("ok"))
    return {"total": len(body.tasks), "success": success_count, "failed": len(body.tasks) - success_count, "results": results}


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


