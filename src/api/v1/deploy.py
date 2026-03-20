"""Deploy API - Worker deployment management."""
from __future__ import annotations

import secrets
import uuid
from datetime import datetime, timedelta
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse, PlainTextResponse
from pydantic import BaseModel

from src.core.auth import require_admin
from src.core.database import db

router = APIRouter(prefix="/deploy", tags=["deploy"])

DEPLOY_DIR = Path(__file__).resolve().parent.parent.parent.parent / "deploy"


# ── Schema ──

class CreateTokenRequest(BaseModel):
    name: str = "default"
    expires_hours: int = 720  # 30 days


class CreateTokenResponse(BaseModel):
    id: str
    token: str
    name: str
    expires_at: str


# ── Helpers ──

async def _init_deploy_table():
    """Ensure deploy_tokens table exists."""
    await db.execute("""
        CREATE TABLE IF NOT EXISTS deploy_tokens (
            id TEXT PRIMARY KEY,
            name TEXT DEFAULT '',
            token TEXT UNIQUE NOT NULL,
            created_by TEXT DEFAULT '',
            expires_at TEXT DEFAULT '',
            used_count INTEGER DEFAULT 0,
            last_used_at TEXT DEFAULT '',
            status TEXT DEFAULT 'active',
            created_at TEXT DEFAULT ''
        )
    """)


async def _validate_deploy_token(token: str) -> dict | None:
    """Validate a deploy token and return its record."""
    await _init_deploy_table()
    rows = await db.query(
        "SELECT * FROM deploy_tokens WHERE token = ? AND status = 'active'",
        [token],
    )
    if not rows:
        return None
    record = rows[0]
    # Check expiry
    if record.get("expires_at"):
        try:
            exp = datetime.fromisoformat(record["expires_at"])
            if datetime.utcnow() > exp:
                return None
        except (ValueError, TypeError):
            pass
    # Update usage
    await db.execute(
        "UPDATE deploy_tokens SET used_count = used_count + 1, last_used_at = ? WHERE id = ?",
        [datetime.utcnow().isoformat(), record["id"]],
    )
    return record


# ── Public endpoints (token-gated) ──

@router.get("/install-script")
async def get_install_script(request: Request, token: str = ""):
    """Return the install script with master URL and token pre-filled."""
    script_path = DEPLOY_DIR / "install-worker.sh"
    if not script_path.exists():
        raise HTTPException(500, "Install script not found on server")

    # Determine master URL from request
    host = request.headers.get("host", request.url.hostname or "127.0.0.1")
    scheme = request.headers.get("x-forwarded-proto", "http")
    master_url = f"{scheme}://{host}"

    script_content = script_path.read_text("utf-8")

    return PlainTextResponse(
        script_content,
        media_type="text/x-shellscript",
        headers={"Content-Disposition": "attachment; filename=install-worker.sh"},
    )


@router.get("/worker-package")
async def get_worker_package(token: str = ""):
    """Download the worker package tarball."""
    if not token:
        raise HTTPException(401, "Deploy token required")

    record = await _validate_deploy_token(token)
    if not record:
        raise HTTPException(403, "Invalid or expired deploy token")

    package_path = DEPLOY_DIR / "worker-package.tar.gz"
    if not package_path.exists():
        raise HTTPException(500, "Worker package not built. Run build-worker-package.sh on the master first.")

    return FileResponse(
        str(package_path),
        media_type="application/gzip",
        filename="worker-package.tar.gz",
    )


# ── Admin endpoints ──

@router.post("/tokens")
async def create_deploy_token(
    req: CreateTokenRequest,
    user: dict = Depends(require_admin),
):
    """Generate a new deploy token."""
    await _init_deploy_table()

    token_id = str(uuid.uuid4())[:8]
    token_value = secrets.token_urlsafe(32)
    now = datetime.utcnow()
    expires_at = (now + timedelta(hours=req.expires_hours)).isoformat()

    await db.execute(
        """INSERT INTO deploy_tokens (id, name, token, created_by, expires_at, created_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        [token_id, req.name, token_value, user.get("username", ""), expires_at, now.isoformat()],
    )

    return CreateTokenResponse(
        id=token_id,
        token=token_value,
        name=req.name,
        expires_at=expires_at,
    )


@router.get("/tokens")
async def list_deploy_tokens(user: dict = Depends(require_admin)):
    """List all deploy tokens."""
    await _init_deploy_table()
    rows = await db.query("SELECT * FROM deploy_tokens ORDER BY created_at DESC")
    return rows


@router.delete("/tokens/{token_id}")
async def revoke_deploy_token(token_id: str, user: dict = Depends(require_admin)):
    """Revoke a deploy token."""
    await _init_deploy_table()
    await db.execute(
        "UPDATE deploy_tokens SET status = 'revoked' WHERE id = ?",
        [token_id],
    )
    return {"ok": True}


@router.get("/command")
async def get_deploy_command(request: Request, user: dict = Depends(require_admin)):
    """Return the one-liner deploy command with an active token."""
    await _init_deploy_table()

    # Find first active token
    rows = await db.query(
        "SELECT token FROM deploy_tokens WHERE status = 'active' ORDER BY created_at DESC LIMIT 1"
    )
    if not rows:
        # Auto-create one
        resp = await create_deploy_token(CreateTokenRequest(name="auto"), user=user)
        token_value = resp.token
    else:
        token_value = rows[0]["token"]

    host = request.headers.get("host", request.url.hostname or "127.0.0.1")
    scheme = request.headers.get("x-forwarded-proto", "http")
    master_url = f"{scheme}://{host}"

    command = (
        f"curl -sSL {master_url}/api/v1/deploy/install-script | "
        f"bash -s -- --master {master_url} --token {token_value}"
    )

    return {"command": command, "token": token_value, "master_url": master_url}
