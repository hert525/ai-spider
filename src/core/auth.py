"""Authentication and authorization."""
from __future__ import annotations

import asyncio
import secrets
from typing import Optional

import bcrypt
from fastapi import Header, HTTPException, Depends

from src.core.database import db


async def hash_password(password: str) -> str:
    """Hash password with bcrypt. Returns bcrypt hash string."""
    hashed = await asyncio.to_thread(
        bcrypt.hashpw, password.encode("utf-8"), bcrypt.gensalt()
    )
    return hashed.decode("utf-8")


async def verify_password(password: str, hashed: str) -> bool:
    """Verify password against bcrypt hash.

    Also supports legacy 'salt$sha256hash' format for migration.
    """
    hashed_bytes = hashed.encode("utf-8") if isinstance(hashed, str) else hashed
    # Legacy SHA-256 format: salt$hash (64-char hex after $)
    if b"$" in hashed_bytes and not hashed_bytes.startswith(b"$2"):
        import hashlib
        salt, h = hashed.split("$", 1)
        if len(h) == 64:  # SHA-256 hex digest
            legacy_match = hashlib.sha256((salt + password).encode()).hexdigest() == h
            if legacy_match:
                # TODO: upgrade hash to bcrypt on next login
                pass
            return legacy_match
    try:
        return await asyncio.to_thread(
            bcrypt.checkpw, password.encode("utf-8"), hashed_bytes
        )
    except (ValueError, TypeError):
        return False


def generate_api_key() -> str:
    """Generate API key: sk- + 32 hex chars."""
    return "sk-" + secrets.token_hex(16)


async def get_current_user(
    x_api_key: Optional[str] = Header(None),
    authorization: Optional[str] = Header(None),
) -> dict:
    """Extract and validate user from request headers."""
    api_key = x_api_key
    if not api_key and authorization:
        if authorization.startswith("Bearer "):
            api_key = authorization[7:].strip()
    if not api_key:
        raise HTTPException(status_code=401, detail="Missing API key")

    rows = await db.query("SELECT * FROM users WHERE api_key = ? AND status = 'active'", [api_key])
    if not rows:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return rows[0]


async def require_admin(user: dict = Depends(get_current_user)) -> dict:
    """Require admin role."""
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin required")
    return user
