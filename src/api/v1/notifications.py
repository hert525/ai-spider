"""Notifications API — config, test, history."""
from __future__ import annotations

import json
from datetime import datetime

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from src.core.database import db
from src.core.auth import get_current_user
from src.core.models import _uid
from src.core.notifier import notifier

router = APIRouter(prefix="/notifications", tags=["notifications"])


class NotificationConfigReq(BaseModel):
    webhook_url: str = ""
    email: str = ""
    telegram_chat_id: str = ""
    events: list[str] = ["task_failed"]
    enabled: bool = True


@router.get("/config")
async def get_config(user: dict = Depends(get_current_user)):
    rows = await db.query("SELECT * FROM notification_configs WHERE user_id = ?", [user["id"]])
    if rows:
        r = rows[0]
        if isinstance(r.get("events"), str):
            try:
                r["events"] = json.loads(r["events"])
            except Exception:
                pass
        return r
    return {"webhook_url": "", "email": "", "telegram_chat_id": "", "events": ["task_failed"], "enabled": True}


@router.post("/config")
async def save_config(req: NotificationConfigReq, user: dict = Depends(get_current_user)):
    now = datetime.now().isoformat()
    existing = await db.query("SELECT id FROM notification_configs WHERE user_id = ?", [user["id"]])
    data = {
        "webhook_url": req.webhook_url,
        "email": req.email,
        "telegram_chat_id": req.telegram_chat_id,
        "events": json.dumps(req.events),
        "enabled": 1 if req.enabled else 0,
        "updated_at": now,
    }
    if existing:
        await db.update("notification_configs", existing[0]["id"], data)
    else:
        data["id"] = _uid()
        data["user_id"] = user["id"]
        data["created_at"] = now
        await db.insert("notification_configs", data)
    return {"ok": True}


@router.post("/test")
async def test_notification(user: dict = Depends(get_current_user)):
    """Send a test notification."""
    await notifier.notify(
        "test_notification",
        {"message": "这是一条测试通知", "user": user.get("username", "")},
        channels=["webhook"],
        user_id=user["id"],
    )
    return {"ok": True, "message": "Test notification sent"}


@router.get("/history")
async def notification_history(limit: int = 50, user: dict = Depends(get_current_user)):
    if user.get("role") == "admin":
        rows = await db.query(
            "SELECT * FROM notification_logs ORDER BY created_at DESC LIMIT ?", [limit]
        )
    else:
        rows = await db.query(
            "SELECT * FROM notification_logs WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
            [user["id"], limit],
        )
    for r in rows:
        if isinstance(r.get("data"), str):
            try:
                r["data"] = json.loads(r["data"])
            except Exception:
                pass
    return rows
