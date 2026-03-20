"""Admin Proxy Pool management API."""
from __future__ import annotations

import random
import time
from datetime import datetime

import httpx
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from src.core.auth import require_admin
from src.core.database import db
from src.core.models import _uid

router = APIRouter(prefix="/admin/proxies", tags=["proxy-admin"])


class CreateProxyPoolReq(BaseModel):
    name: str
    description: str = ""
    proxy_type: str = "http"
    mode: str = "single"
    proxies: list[str] = []
    rotating_api: str = ""
    test_url: str = "https://httpbin.org/ip"
    is_public: int = 0


class UpdateProxyPoolReq(BaseModel):
    name: str | None = None
    description: str | None = None
    proxy_type: str | None = None
    mode: str | None = None
    proxies: list[str] | None = None
    rotating_api: str | None = None
    test_url: str | None = None
    is_public: int | None = None
    status: str | None = None


class GrantReq(BaseModel):
    user_id: str | None = None
    user_ids: list[str] | None = None


@router.post("")
async def create_proxy_pool(req: CreateProxyPoolReq, user: dict = Depends(require_admin)):
    now = datetime.now().isoformat()
    pool_id = _uid()
    data = {
        "id": pool_id,
        "name": req.name,
        "description": req.description,
        "proxy_type": req.proxy_type,
        "mode": req.mode,
        "proxies": req.proxies,
        "rotating_api": req.rotating_api,
        "test_url": req.test_url,
        "is_public": req.is_public,
        "status": "active",
        "created_at": now,
        "updated_at": now,
    }
    await db.insert("proxy_pools", data)
    return await db.get("proxy_pools", pool_id)


@router.get("")
async def list_proxy_pools(user: dict = Depends(require_admin)):
    return await db.list("proxy_pools", order="created_at DESC")


@router.get("/{pool_id}")
async def get_proxy_pool(pool_id: str, user: dict = Depends(require_admin)):
    pool = await db.get("proxy_pools", pool_id)
    if not pool:
        raise HTTPException(404, "Proxy pool not found")
    return pool


@router.put("/{pool_id}")
async def update_proxy_pool(pool_id: str, req: UpdateProxyPoolReq, user: dict = Depends(require_admin)):
    pool = await db.get("proxy_pools", pool_id)
    if not pool:
        raise HTTPException(404, "Proxy pool not found")
    updates: dict = {}
    for field in ["name", "description", "proxy_type", "mode", "proxies", "rotating_api", "test_url", "is_public", "status"]:
        val = getattr(req, field)
        if val is not None:
            updates[field] = val
    updates["updated_at"] = datetime.now().isoformat()
    await db.update("proxy_pools", pool_id, updates)
    return await db.get("proxy_pools", pool_id)


@router.delete("/{pool_id}")
async def delete_proxy_pool(pool_id: str, user: dict = Depends(require_admin)):
    pool = await db.get("proxy_pools", pool_id)
    if not pool:
        raise HTTPException(404, "Proxy pool not found")
    # Delete permissions too
    await db.query("DELETE FROM proxy_permissions WHERE proxy_pool_id = ?", [pool_id])
    await db.delete("proxy_pools", pool_id)
    return {"ok": True}


@router.post("/{pool_id}/test")
async def test_proxy_pool(pool_id: str, user: dict = Depends(require_admin)):
    pool = await db.get("proxy_pools", pool_id)
    if not pool:
        raise HTTPException(404, "Proxy pool not found")

    test_url = pool.get("test_url") or "https://httpbin.org/ip"
    proxies_list = pool.get("proxies", [])
    mode = pool.get("mode", "single")
    proxy_type = pool.get("proxy_type", "http")

    proxy_url: str | None = None
    if mode == "rotating":
        rotating_api = pool.get("rotating_api", "")
        if not rotating_api:
            return {"ok": False, "error": "No rotating API configured", "ip": None}
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(rotating_api)
                proxy_url = resp.text.strip()
                if proxy_url and ":" in proxy_url and not proxy_url.startswith("http"):
                    proxy_url = f"{proxy_type}://{proxy_url}"
        except Exception as e:
            return {"ok": False, "error": f"Failed to fetch rotating proxy: {e}", "ip": None}
    else:
        if not proxies_list:
            return {"ok": False, "error": "No proxies configured", "ip": None}
        proxy_url = random.choice(proxies_list)

    if not proxy_url:
        return {"ok": False, "error": "Could not get proxy URL", "ip": None}

    try:
        start = time.monotonic()
        async with httpx.AsyncClient(proxies={"http://": proxy_url, "https://": proxy_url}, timeout=15) as client:
            resp = await client.get(test_url)
            resp.raise_for_status()
            latency_ms = int((time.monotonic() - start) * 1000)
            data = resp.json() if "json" in resp.headers.get("content-type", "") else {"raw": resp.text[:200]}
            return {"ok": True, "ip": data.get("origin", data.get("raw", "")), "proxy": proxy_url, "latency_ms": latency_ms}
    except Exception as e:
        return {"ok": False, "error": str(e), "ip": None, "proxy": proxy_url}


@router.get("/{pool_id}/permissions")
async def get_permissions(pool_id: str, user: dict = Depends(require_admin)):
    pool = await db.get("proxy_pools", pool_id)
    if not pool:
        raise HTTPException(404, "Proxy pool not found")
    perms = await db.query(
        "SELECT pp.*, u.email, u.username FROM proxy_permissions pp LEFT JOIN users u ON pp.user_id = u.id WHERE pp.proxy_pool_id = ?",
        [pool_id],
    )
    return perms


@router.post("/{pool_id}/grant")
async def grant_permission(pool_id: str, req: GrantReq, user: dict = Depends(require_admin)):
    pool = await db.get("proxy_pools", pool_id)
    if not pool:
        raise HTTPException(404, "Proxy pool not found")
    user_ids = req.user_ids or ([req.user_id] if req.user_id else [])
    if not user_ids:
        raise HTTPException(400, "user_id or user_ids required")
    now = datetime.now().isoformat()
    granted = 0
    for uid in user_ids:
        try:
            await db.insert("proxy_permissions", {
                "id": _uid(),
                "user_id": uid,
                "proxy_pool_id": pool_id,
                "granted_by": user["id"],
                "created_at": now,
            })
            granted += 1
        except Exception:
            pass  # duplicate
    return {"ok": True, "granted": granted}


@router.delete("/{pool_id}/revoke/{user_id}")
async def revoke_permission(pool_id: str, user_id: str, user: dict = Depends(require_admin)):
    await db.query("DELETE FROM proxy_permissions WHERE proxy_pool_id = ? AND user_id = ?", [pool_id, user_id])
    return {"ok": True}


@router.post("/{pool_id}/grant-all")
async def grant_all(pool_id: str, user: dict = Depends(require_admin)):
    pool = await db.get("proxy_pools", pool_id)
    if not pool:
        raise HTTPException(404, "Proxy pool not found")
    await db.update("proxy_pools", pool_id, {"is_public": 1, "updated_at": datetime.now().isoformat()})
    return {"ok": True}
