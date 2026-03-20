"""Authentication and authorization."""
from __future__ import annotations

import hashlib
import secrets
from typing import Optional

from fastapi import Header, HTTPException, Depends

from src.core.database import db


def _hash_with_salt(password: str, salt: str) -> str:
    return hashlib.sha256((salt + password).encode()).hexdigest()


async def hash_password(password: str) -> str:
    """Hash password with random salt. Returns 'salt$hash'."""
    salt = secrets.token_hex(16)
    h = _hash_with_salt(password, salt)
    return f"{salt}${h}"


async def verify_password(password: str, hashed: str) -> bool:
    """Verify password against 'salt$hash'."""
    if "$" not in hashed:
        return False
    salt, h = hashed.split("$", 1)
    return _hash_with_salt(password, salt) == h


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
