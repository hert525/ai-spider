"""Worker Pool management API endpoints."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from loguru import logger

from src.core.database import db
from src.core.models import WorkerPool, _uid
from src.core.auth import get_current_user

router = APIRouter(prefix="/worker-pools", tags=["worker-pools"])


# ── Request models ──

class CreatePoolReq(BaseModel):
    name: str
    description: str = ""
    region: str = ""       # e.g. "us", "cn", "eu", "jp", "ap"
    country: str = ""      # e.g. "US", "CN", "DE", "JP"
    tags: list[str] = []
    max_concurrency: int = 50


class UpdatePoolReq(BaseModel):
    name: str | None = None
    description: str | None = None
    region: str | None = None
    country: str | None = None
    tags: list[str] | None = None
    max_concurrency: int | None = None
    status: str | None = None  # "active" or "disabled"


# ── Endpoints ──

@router.get("")
async def list_pools(user: dict = Depends(get_current_user)):
    """List all worker pools. All users can see active pools."""
    if user.get("role") == "admin":
        rows = await db.list("worker_pools", order="created_at DESC", limit=200)
    else:
        rows = await db.list("worker_pools", where={"status": "active"}, order="created_at DESC", limit=200)

    # Attach worker count per pool
    for pool in rows:
        workers = await db.query(
            "SELECT COUNT(*) as cnt FROM workers WHERE pool_id = ?",
            [pool["id"]],
        )
        pool["worker_count"] = workers[0]["cnt"] if workers else 0
        # Count online workers
        online = await db.query(
            "SELECT COUNT(*) as cnt FROM workers WHERE pool_id = ? AND status = 'online'",
            [pool["id"]],
        )
        pool["online_count"] = online[0]["cnt"] if online else 0

    return rows


@router.get("/{pool_id}")
async def get_pool(pool_id: str, user: dict = Depends(get_current_user)):
    """Get a specific worker pool with its workers."""
    pool = await db.get("worker_pools", pool_id)
    if not pool:
        raise HTTPException(404, "Worker pool not found")

    # Attach workers in this pool
    workers = await db.query(
        "SELECT * FROM workers WHERE pool_id = ? ORDER BY status, hostname",
        [pool_id],
    )
    pool["workers"] = workers
    pool["worker_count"] = len(workers)
    pool["online_count"] = sum(1 for w in workers if w.get("status") == "online")

    return pool


@router.post("")
async def create_pool(req: CreatePoolReq, user: dict = Depends(get_current_user)):
    """Create a new worker pool (admin only)."""
    if user.get("role") != "admin":
        raise HTTPException(403, "Admin only")

    pool = WorkerPool(
        name=req.name,
        description=req.description,
        region=req.region,
        country=req.country,
        tags=req.tags,
        max_concurrency=req.max_concurrency,
    )
    await db.insert("worker_pools", pool.model_dump())
    logger.info(f"Worker pool created: {pool.id} ({req.name}, region={req.region})")
    return await db.get("worker_pools", pool.id)


@router.put("/{pool_id}")
async def update_pool(pool_id: str, req: UpdatePoolReq, user: dict = Depends(get_current_user)):
    """Update a worker pool (admin only)."""
    if user.get("role") != "admin":
        raise HTTPException(403, "Admin only")

    pool = await db.get("worker_pools", pool_id)
    if not pool:
        raise HTTPException(404, "Worker pool not found")

    updates = {k: v for k, v in req.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(400, "No fields to update")

    updates["updated_at"] = datetime.now(timezone.utc).isoformat()
    await db.update("worker_pools", pool_id, updates)
    return await db.get("worker_pools", pool_id)


@router.delete("/{pool_id}")
async def delete_pool(pool_id: str, user: dict = Depends(get_current_user)):
    """Delete a worker pool (admin only). Workers in this pool become unassigned."""
    if user.get("role") != "admin":
        raise HTTPException(403, "Admin only")

    pool = await db.get("worker_pools", pool_id)
    if not pool:
        raise HTTPException(404, "Worker pool not found")

    # Unassign workers from this pool
    workers = await db.query(
        "SELECT id FROM workers WHERE pool_id = ?", [pool_id]
    )
    for w in workers:
        await db.update("workers", w["id"], {"pool_id": "", "updated_at": datetime.now(timezone.utc).isoformat()})

    await db.delete("worker_pools", pool_id)
    logger.info(f"Worker pool deleted: {pool_id}, {len(workers)} workers unassigned")
    return {"ok": True, "unassigned_workers": len(workers)}


@router.post("/{pool_id}/workers/{worker_id}")
async def add_worker_to_pool(pool_id: str, worker_id: str, user: dict = Depends(get_current_user)):
    """Move a worker into this pool (admin only)."""
    if user.get("role") != "admin":
        raise HTTPException(403, "Admin only")

    pool = await db.get("worker_pools", pool_id)
    if not pool:
        raise HTTPException(404, "Worker pool not found")

    worker = await db.get("workers", worker_id)
    if not worker:
        raise HTTPException(404, "Worker not found")

    await db.update("workers", worker_id, {
        "pool_id": pool_id,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    })
    logger.info(f"Worker {worker_id} moved to pool {pool_id} ({pool.get('name', '')})")
    return {"ok": True}


@router.delete("/{pool_id}/workers/{worker_id}")
async def remove_worker_from_pool(pool_id: str, worker_id: str, user: dict = Depends(get_current_user)):
    """Remove a worker from this pool (admin only)."""
    if user.get("role") != "admin":
        raise HTTPException(403, "Admin only")

    worker = await db.get("workers", worker_id)
    if not worker:
        raise HTTPException(404, "Worker not found")
    if worker.get("pool_id") != pool_id:
        raise HTTPException(400, "Worker not in this pool")

    await db.update("workers", worker_id, {
        "pool_id": "",
        "updated_at": datetime.now(timezone.utc).isoformat(),
    })
    return {"ok": True}
