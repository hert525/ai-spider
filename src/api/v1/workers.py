"""Worker management API endpoints."""
from __future__ import annotations
from datetime import datetime
from fastapi import APIRouter
from pydantic import BaseModel
from loguru import logger

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


@router.get("")
async def list_workers():
    now = datetime.now()
    result = []
    for wid, w in _workers.items():
        # Mark stale workers offline
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
