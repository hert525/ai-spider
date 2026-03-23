"""Auth API - register, login, user info."""
from __future__ import annotations

from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from src.core.database import db
from src.core.auth import hash_password, verify_password, generate_api_key, get_current_user
from src.core.models import _uid

router = APIRouter(prefix="/auth", tags=["auth"])


class RegisterReq(BaseModel):
    email: str
    username: str
    password: str


class LoginReq(BaseModel):
    email: str
    password: str


@router.post("/register")
async def register(req: RegisterReq):
    """Register a new user."""
    existing = await db.query("SELECT id FROM users WHERE email = ?", [req.email])
    if existing:
        raise HTTPException(400, "Email already registered")

    api_key = generate_api_key()
    now = datetime.now().isoformat()
    user = {
        "id": _uid(),
        "email": req.email,
        "username": req.username,
        "password_hash": await hash_password(req.password),
        "api_key": api_key,
        "role": "user",
        "quota_projects": 20,
        "quota_tasks": 100,
        "status": "active",
        "created_at": now,
        "updated_at": now,
    }
    await db.insert("users", user)
    return {"user": {k: v for k, v in user.items() if k != "password_hash"}, "api_key": api_key}


@router.post("/login")
async def login(req: LoginReq):
    """Login and return API key. Accepts email or username."""
    rows = await db.query("SELECT * FROM users WHERE email = ?", [req.email])
    if not rows:
        rows = await db.query("SELECT * FROM users WHERE username = ?", [req.email])
    if not rows:
        raise HTTPException(401, "Invalid credentials")
    user = rows[0]
    if not await verify_password(req.password, user["password_hash"]):
        raise HTTPException(401, "Invalid credentials")
    if user.get("status") != "active":
        raise HTTPException(403, "Account suspended")
    return {"api_key": user["api_key"], "user": {k: v for k, v in user.items() if k != "password_hash"}}


@router.get("/me")
async def me(user: dict = Depends(get_current_user)):
    """Get current user info."""
    return {k: v for k, v in user.items() if k != "password_hash"}


@router.post("/regenerate-key")
async def regenerate_key(user: dict = Depends(get_current_user)):
    """Regenerate API key."""
    new_key = generate_api_key()
    await db.update("users", user["id"], {"api_key": new_key, "updated_at": datetime.now().isoformat()})
    return {"api_key": new_key}
