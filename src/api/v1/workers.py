"""Worker management API endpoints."""
from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from loguru import logger

from src.scheduler.task_manager import task_manager
from src.core.database import db
from src.core.models import DataRecord, _uid

router = APIRouter(prefix="/workers", tags=["workers"])

# In-memory worker registry
_workers: dict[str, dict] = {}


class WorkerRegisterReq(BaseModel):
    worker_id: str
    hostname: str = ""
    ip: str = ""
    max_concurrency: int = 3
    tags: list[str] = []


class WorkerHeartbeatReq(BaseModel):
    status: str = "online"
    cpu_percent: float = 0
    memory_mb: float = 0
    active_jobs: int = 0
    total_completed: int = 0
    total_failed: int = 0


class WorkerReportReq(BaseModel):
    task_id: str
    run_id: str
    status: str  # "success" or "failed"
    items: list[dict] = []
    items_count: int = 0
    pages_crawled: int = 0
    error: str = ""


@router.get("")
async def list_workers():
    now = datetime.now()
    result = []
    for wid, w in _workers.items():
        if (now - w.get("last_heartbeat", now)).total_seconds() > 60:
            w["status"] = "offline"
        result.append(w)
    return result


@router.post("/register")
async def register_worker(req: WorkerRegisterReq):
    w = {
        "id": req.worker_id,
        "hostname": req.hostname,
        "ip": req.ip,
        "status": "online",
        "max_concurrency": req.max_concurrency,
        "active_jobs": 0,
        "total_completed": 0,
        "total_failed": 0,
        "cpu_percent": 0,
        "memory_mb": 0,
        "tags": req.tags,
        "last_heartbeat": datetime.now(),
        "registered_at": datetime.now(),
    }
    _workers[req.worker_id] = w
    return w


@router.post("/{worker_id}/heartbeat")
async def worker_heartbeat(worker_id: str, req: WorkerHeartbeatReq):
    w = _workers.get(worker_id)
    if not w:
        return {"error": "not registered"}
    w.update({
        "status": req.status,
        "cpu_percent": req.cpu_percent,
        "memory_mb": req.memory_mb,
        "active_jobs": req.active_jobs,
        "total_completed": req.total_completed,
        "total_failed": req.total_failed,
        "last_heartbeat": datetime.now(),
    })
    return w


@router.post("/{worker_id}/poll")
async def worker_poll(worker_id: str):
    """Worker pulls a task from the queue."""
    if worker_id not in _workers:
        raise HTTPException(404, "Worker not registered")

    assignment = await task_manager.assign_task(worker_id)
    if not assignment:
        raise HTTPException(404, "No tasks available")

    return assignment


@router.post("/{worker_id}/report")
async def worker_report(worker_id: str, req: WorkerReportReq):
    """Worker reports task completion or failure."""
    if req.status == "success":
        # Store data records if items provided
        if req.items:
            task_data = await db.get("tasks", req.task_id)
            project_id = task_data["project_id"] if task_data else ""
            records = []
            for item in req.items:
                records.append(DataRecord(
                    project_id=project_id,
                    task_id=req.task_id,
                    task_run_id=req.run_id,
                    data=item,
                ).model_dump())
            await db.insert_many("data_records", records)

        await task_manager.complete_task(
            req.task_id, req.run_id,
            items_count=req.items_count or len(req.items),
            pages_crawled=req.pages_crawled,
        )
    else:
        await task_manager.fail_task(req.task_id, req.run_id, req.error)

    # Update worker stats in memory
    w = _workers.get(worker_id)
    if w:
        if req.status == "success":
            w["total_completed"] = w.get("total_completed", 0) + 1
        else:
            w["total_failed"] = w.get("total_failed", 0) + 1

    return {"ok": True}


@router.delete("/{worker_id}")
async def remove_worker(worker_id: str):
    _workers.pop(worker_id, None)
    return {"ok": True}


def get_stats():
    workers = list(_workers.values())
    online = sum(1 for w in workers if w.get("status") == "online")
    return {
        "total": len(workers),
        "online": online,
        "offline": len(workers) - online,
    }
