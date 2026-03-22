"""Worker management API endpoints — database-backed."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from loguru import logger

from src.scheduler.task_manager import task_manager
from src.core.database import db
from src.core.models import DataRecord, Worker, WorkerStatus, _uid
from src.core.settings_manager import settings_manager

router = APIRouter(prefix="/workers", tags=["workers"])


async def verify_worker_token(request: Request):
    """Verify worker token from X-Worker-Token header."""
    token = request.headers.get("X-Worker-Token", "")
    if not token:
        raise HTTPException(401, "Worker token required")
    rows = await db.query("SELECT id FROM workers WHERE token = ?", [token])
    if not rows:
        raise HTTPException(401, "Invalid worker token")
    return {"token": token}


# ── Request models ──

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
    memory_total_mb: float = 0
    disk_percent: float = 0
    python_version: str = ""
    os_info: str = ""
    active_jobs: int = 0
    current_tasks: list[str] = []
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


# ── Helpers ──

def _offline_threshold() -> int:
    return 60


async def _offline_threshold_async() -> int:
    try:
        val = await settings_manager.get("worker_offline_threshold", "60")
        return int(val)
    except Exception:
        return 60


def _mark_offline_if_stale(w: dict, threshold: int = 60) -> dict:
    """Mark worker offline if heartbeat is stale (unless disabled)."""
    if w.get("status") in ("disabled",):
        return w
    lh = w.get("last_heartbeat", "")
    if lh:
        try:
            dt = datetime.fromisoformat(lh)
            delta = (datetime.now(timezone.utc) - dt).total_seconds()
            if delta > threshold:
                w["status"] = "offline"
        except Exception:
            pass
    else:
        w["status"] = "offline"
    return w


# ── Endpoints ──

@router.get("")
async def list_workers():
    rows = await db.list("workers", order="registered_at DESC", limit=500)
    threshold = await _offline_threshold_async()
    for w in rows:
        _mark_offline_if_stale(w, threshold)
    return rows


@router.get("/{worker_id}")
async def get_worker(worker_id: str):
    w = await db.get("workers", worker_id)
    if not w:
        raise HTTPException(404, "Worker not found")
    threshold = await _offline_threshold_async()
    _mark_offline_if_stale(w, threshold)
    # Attach recent task runs
    runs = await db.query(
        "SELECT * FROM task_runs WHERE worker_id = ? ORDER BY started_at DESC LIMIT 20",
        [worker_id],
    )
    w["recent_runs"] = runs
    return w


@router.post("/register")
async def register_worker(req: WorkerRegisterReq):
    now = datetime.now(timezone.utc).isoformat()
    existing = await db.get("workers", req.worker_id)
    if existing:
        await db.update("workers", req.worker_id, {
            "hostname": req.hostname or existing.get("hostname", ""),
            "ip": req.ip or existing.get("ip", ""),
            "status": "online",
            "max_concurrency": req.max_concurrency,
            "tags": req.tags,
            "last_heartbeat": now,
            "updated_at": now,
        })
    else:
        w = Worker(
            id=req.worker_id,
            hostname=req.hostname,
            ip=req.ip,
            max_concurrency=req.max_concurrency,
            tags=req.tags,
            status=WorkerStatus.ONLINE,
            last_heartbeat=now,
            registered_at=now,
            updated_at=now,
        )
        await db.insert("workers", w.model_dump())
    return await db.get("workers", req.worker_id)


@router.post("/{worker_id}/heartbeat")
async def worker_heartbeat(worker_id: str, req: WorkerHeartbeatReq):
    existing = await db.get("workers", worker_id)
    if not existing:
        return {"error": "not registered"}
    now = datetime.now(timezone.utc).isoformat()
    # Preserve disabled/draining status
    status = req.status
    if existing.get("status") in ("disabled", "draining"):
        status = existing["status"]
    await db.update("workers", worker_id, {
        "status": status,
        "cpu_percent": req.cpu_percent,
        "memory_mb": req.memory_mb,
        "memory_total_mb": req.memory_total_mb,
        "disk_percent": req.disk_percent,
        "python_version": req.python_version,
        "os_info": req.os_info,
        "active_jobs": req.active_jobs,
        "current_tasks": req.current_tasks,
        "total_completed": req.total_completed,
        "total_failed": req.total_failed,
        "last_heartbeat": now,
        "updated_at": now,
    })
    return await db.get("workers", worker_id)


@router.post("/{worker_id}/poll")
async def worker_poll(worker_id: str):
    """Worker pulls a task from the queue."""
    w = await db.get("workers", worker_id)
    if not w:
        raise HTTPException(404, "Worker not registered")
    if w.get("status") in ("disabled", "draining"):
        raise HTTPException(403, "Worker is disabled or draining")

    assignment = await task_manager.assign_task(worker_id)
    if not assignment:
        return {"task": None}  # 无任务时返回200+空，不是404
    return assignment


@router.post("/{worker_id}/report")
async def worker_report(worker_id: str, req: WorkerReportReq):
    """Worker reports task completion or failure."""
    if req.status == "success":
        if req.items:
            task_data = await db.get("tasks", req.task_id)
            project_id = task_data["project_id"] if task_data else ""

            # Clean and deduplicate
            from src.engine.dedup import deduplicator
            items = deduplicator.clean(req.items)
            items = deduplicator.deduplicate(items)
            if project_id:
                items = await deduplicator.deduplicate_against_db(items, project_id)

            records = []
            for item in items:
                data_hash = item.pop("_data_hash", "")
                rec = DataRecord(
                    project_id=project_id,
                    task_id=req.task_id,
                    task_run_id=req.run_id,
                    data=item,
                ).model_dump()
                rec["data_hash"] = data_hash
                records.append(rec)
            if records:
                await db.insert_many("data_records", records)

        await task_manager.complete_task(
            req.task_id, req.run_id,
            items_count=req.items_count or len(req.items),
            pages_crawled=req.pages_crawled,
        )
    else:
        await task_manager.fail_task(req.task_id, req.run_id, req.error)

    # WebSocket push
    try:
        from src.api.ws import ws_manager
        task_data = await db.get("tasks", req.task_id)
        if task_data:
            user_id = task_data.get("user_id")
            if user_id:
                user_rows = await db.query("SELECT api_key FROM users WHERE id = ?", [user_id])
                if user_rows:
                    await ws_manager.send_to_user(user_rows[0]["api_key"], {
                        "type": "task_update",
                        "task_id": req.task_id,
                        "status": req.status,
                        "items_count": req.items_count or len(req.items),
                    })
            await ws_manager.broadcast_admin({
                "type": "task_update",
                "task_id": req.task_id,
                "status": req.status,
                "items_count": req.items_count or len(req.items),
            })
    except Exception as e:
        logger.warning(f"WS push failed in report: {e}")

    return {"ok": True}


@router.delete("/{worker_id}")
async def remove_worker(worker_id: str):
    deleted = await db.delete("workers", worker_id)
    if not deleted:
        raise HTTPException(404, "Worker not found")
    return {"ok": True}


@router.put("/{worker_id}/disable")
async def disable_worker(worker_id: str):
    w = await db.get("workers", worker_id)
    if not w:
        raise HTTPException(404, "Worker not found")
    await db.update("workers", worker_id, {
        "status": "disabled",
        "updated_at": datetime.now(timezone.utc).isoformat(),
    })
    return {"ok": True, "status": "disabled"}


@router.put("/{worker_id}/enable")
async def enable_worker(worker_id: str):
    w = await db.get("workers", worker_id)
    if not w:
        raise HTTPException(404, "Worker not found")
    await db.update("workers", worker_id, {
        "status": "online",
        "updated_at": datetime.now(timezone.utc).isoformat(),
    })
    return {"ok": True, "status": "online"}


@router.post("/{worker_id}/drain")
async def drain_worker(worker_id: str):
    w = await db.get("workers", worker_id)
    if not w:
        raise HTTPException(404, "Worker not found")
    await db.update("workers", worker_id, {
        "status": "draining",
        "updated_at": datetime.now(timezone.utc).isoformat(),
    })
    return {"ok": True, "status": "draining"}


def get_stats():
    """Sync stats helper for dashboard (called from sync context)."""
    import asyncio
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            return {"total": 0, "online": 0, "offline": 0}
    except RuntimeError:
        pass
    return {"total": 0, "online": 0, "offline": 0}


async def get_stats_async() -> dict:
    rows = await db.list("workers", order="registered_at DESC", limit=500)
    threshold = await _offline_threshold_async()
    for w in rows:
        _mark_offline_if_stale(w, threshold)
    online = sum(1 for w in rows if w.get("status") == "online")
    disabled = sum(1 for w in rows if w.get("status") == "disabled")
    draining = sum(1 for w in rows if w.get("status") == "draining")
    return {
        "total": len(rows),
        "online": online,
        "offline": len(rows) - online - disabled - draining,
        "disabled": disabled,
        "draining": draining,
    }
