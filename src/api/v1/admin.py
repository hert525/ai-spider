"""Admin API - user management and statistics."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from src.core.auth import require_admin
from src.core.database import db

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/users")
async def list_users(user: dict = Depends(require_admin)):
    rows = await db.list("users", limit=1000)
    for r in rows:
        r.pop("password_hash", None)
    return rows


class RoleUpdate(BaseModel):
    role: str


@router.put("/users/{uid}/role")
async def update_user_role(uid: str, body: RoleUpdate, user: dict = Depends(require_admin)):
    if body.role not in ("admin", "user"):
        raise HTTPException(400, "role must be 'admin' or 'user'")
    target = await db.get("users", uid)
    if not target:
        raise HTTPException(404, "User not found")
    await db.update("users", uid, {"role": body.role})
    return {"ok": True}


class StatusUpdate(BaseModel):
    status: str


@router.put("/users/{uid}/status")
async def update_user_status(uid: str, body: StatusUpdate, user: dict = Depends(require_admin)):
    if body.status not in ("active", "suspended"):
        raise HTTPException(400, "status must be 'active' or 'suspended'")
    target = await db.get("users", uid)
    if not target:
        raise HTTPException(404, "User not found")
    await db.update("users", uid, {"status": body.status})
    return {"ok": True}


@router.delete("/users/{uid}")
async def delete_user(uid: str, user: dict = Depends(require_admin)):
    target = await db.get("users", uid)
    if not target:
        raise HTTPException(404, "User not found")
    # Delete user's tasks
    tasks = await db.list("tasks", where={"user_id": uid}, limit=10000)
    for t in tasks:
        await db.delete("tasks", t["id"])
    # Delete user's projects
    projects = await db.list("projects", where={"user_id": uid}, limit=10000)
    for p in projects:
        await db.delete("projects", p["id"])
    # Delete user
    await db.delete("users", uid)
    return {"ok": True}


@router.get("/stats")
async def admin_stats(user: dict = Depends(require_admin)):
    users = await db.count("users")
    projects = await db.count("projects")
    tasks = await db.count("tasks")
    tasks_running = await db.count("tasks", where={"status": "running"})
    workers = await db.count("workers")
    workers_online = await db.count("workers", where={"status": "online"})
    data_records = await db.count("data_records")
    return {
        "users": users,
        "projects": projects,
        "tasks": tasks,
        "tasks_running": tasks_running,
        "workers": workers,
        "workers_online": workers_online,
        "data_records": data_records,
    }


class UpdateQuotaReq(BaseModel):
    daily_task_limit: int | None = None
    storage_limit_mb: int | None = None
    max_concurrent_tasks: int | None = None


@router.put("/users/{user_id}/quota")
async def update_user_quota(user_id: str, req: UpdateQuotaReq, user: dict = Depends(require_admin)):
    target = await db.get("users", user_id)
    if not target:
        raise HTTPException(404, "User not found")
    update = {}
    if req.daily_task_limit is not None:
        update["daily_task_limit"] = req.daily_task_limit
    if req.storage_limit_mb is not None:
        update["storage_limit_mb"] = req.storage_limit_mb
    if req.max_concurrent_tasks is not None:
        update["max_concurrent_tasks"] = req.max_concurrent_tasks
    if update:
        from datetime import datetime, timezone
        update["updated_at"] = datetime.now(timezone.utc).isoformat()
        await db.update("users", user_id, update)
    return {"ok": True}
