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
    telegram_bot_token: str = ""
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
        # Mask telegram_bot_token for security
        token = r.get("telegram_bot_token", "")
        if token:
            r["telegram_bot_token"] = token[:5] + "***" if len(token) > 5 else "***"
        return r
    return {
        "webhook_url": "",
        "email": "",
        "telegram_bot_token": "",
        "telegram_chat_id": "",
        "events": ["task_failed"],
        "enabled": True,
    }


@router.post("/config")
async def save_config(req: NotificationConfigReq, user: dict = Depends(get_current_user)):
    now = datetime.now().isoformat()
    existing = await db.query("SELECT * FROM notification_configs WHERE user_id = ?", [user["id"]])
    data = {
        "webhook_url": req.webhook_url,
        "email": req.email,
        "telegram_bot_token": req.telegram_bot_token,
        "telegram_chat_id": req.telegram_chat_id,
        "events": json.dumps(req.events),
        "enabled": 1 if req.enabled else 0,
        "updated_at": now,
    }
    # If token is masked (contains ***), don't overwrite the real token
    if "***" in (req.telegram_bot_token or ""):
        if existing:
            data["telegram_bot_token"] = existing[0].get("telegram_bot_token", "")
        else:
            data.pop("telegram_bot_token", None)
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
    """Send a test notification to all configured channels for the user."""
    # Let notifier resolve channels from user config (pass channels=None)
    await notifier.notify(
        "test_notification",
        {"message": "这是一条测试通知", "user": user.get("username", ""), "time": datetime.now().isoformat()},
        channels=None,
        user_id=user["id"],
    )
    return {"ok": True, "message": "Test notification sent to all configured channels"}


@router.post("/test/{channel}")
async def test_notification_channel(channel: str, user: dict = Depends(get_current_user)):
    """Send a test notification to a specific channel."""
    if channel not in ("webhook", "email", "telegram"):
        raise HTTPException(400, f"Unknown channel: {channel}")
    await notifier.notify(
        "test_notification",
        {"message": f"这是一条 {channel} 测试通知", "user": user.get("username", ""), "time": datetime.now().isoformat()},
        channels=[channel],
        user_id=user["id"],
    )
    return {"ok": True, "message": f"Test notification sent via {channel}"}


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
