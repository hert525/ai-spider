"""Browser sessions API — cookie/session management."""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from urllib.parse import urlparse

from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import FileResponse
from pydantic import BaseModel
from loguru import logger

from src.core.database import db
from src.core.models import _uid
from src.core.auth import get_current_user
from src.engine.screenshot import screenshot_manager, SCREENSHOT_DIR

router = APIRouter()


# ── Models ──

class ImportCookiesReq(BaseModel):
    domain: str
    cookies: str | list[dict]
    name: str = ""


class TestSessionReq(BaseModel):
    test_url: str


# ── Cookie parsing helpers ──

def _parse_cookie_string(cookie_str: str, domain: str) -> list[dict]:
    """Parse 'key=value; key2=value2' format."""
    cookies = []
    for pair in cookie_str.split(";"):
        pair = pair.strip()
        if "=" not in pair:
            continue
        name, value = pair.split("=", 1)
        cookies.append({
            "name": name.strip(),
            "value": value.strip(),
            "domain": domain,
            "path": "/",
        })
    return cookies


def _parse_netscape_cookies(content: str, domain: str) -> list[dict]:
    """Parse Netscape/Mozilla cookie file format."""
    cookies = []
    for line in content.strip().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) >= 7:
            cookies.append({
                "name": parts[5],
                "value": parts[6],
                "domain": parts[0],
                "path": parts[2],
            })
    return cookies


def _parse_cookies(raw: str | list[dict], domain: str) -> list[dict]:
    """Auto-detect and parse cookie format."""
    if isinstance(raw, list):
        # Already JSON list
        return raw

    raw = raw.strip()

    # Try JSON array
    if raw.startswith("["):
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            pass

    # Try Netscape format (contains tabs)
    if "\t" in raw and "\n" in raw:
        result = _parse_netscape_cookies(raw, domain)
        if result:
            return result

    # Default: browser cookie string
    return _parse_cookie_string(raw, domain)


# ── Routes ──

@router.post("/sessions/import-cookies")
async def import_cookies(req: ImportCookiesReq, user: dict = Depends(get_current_user)):
    """Import cookies for a domain. Supports JSON, Netscape, or browser cookie string."""
    cookies = _parse_cookies(req.cookies, req.domain)
    if not cookies:
        raise HTTPException(400, "No cookies parsed from input")

    now = datetime.now(timezone.utc).isoformat()
    session_id = _uid()

    # Upsert: delete existing for same user+domain
    existing = await db.query(
        "SELECT id FROM browser_sessions WHERE user_id = ? AND domain = ?",
        [user["id"], req.domain],
    )
    if existing:
        await db.delete("browser_sessions", existing[0]["id"])

    await db.insert("browser_sessions", {
        "id": session_id,
        "user_id": user["id"],
        "domain": req.domain,
        "name": req.name or req.domain,
        "cookies": json.dumps(cookies, ensure_ascii=False),
        "local_storage": "{}",
        "user_agent": "",
        "status": "active",
        "expires_at": "",
        "created_at": now,
        "updated_at": now,
    })

    return {"id": session_id, "domain": req.domain, "cookie_count": len(cookies)}


@router.get("/sessions")
async def list_sessions(user: dict = Depends(get_current_user)):
    """List all saved sessions for the current user."""
    rows = await db.list("browser_sessions", where={"user_id": user["id"]})
    for r in rows:
        # Parse cookies count without sending full cookies
        try:
            c = json.loads(r.get("cookies", "[]")) if isinstance(r.get("cookies"), str) else r.get("cookies", [])
            r["cookie_count"] = len(c)
        except Exception:
            r["cookie_count"] = 0
        r.pop("cookies", None)
        r.pop("local_storage", None)
    return rows


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str, user: dict = Depends(get_current_user)):
    """Delete a saved session."""
    session = await db.get("browser_sessions", session_id)
    if not session:
        raise HTTPException(404, "Session not found")
    if session["user_id"] != user["id"] and user.get("role") != "admin":
        raise HTTPException(403)
    await db.delete("browser_sessions", session_id)
    return {"ok": True}


@router.post("/sessions/{session_id}/test")
async def test_session(session_id: str, req: TestSessionReq, user: dict = Depends(get_current_user)):
    """Test if a session is still valid by visiting a URL with saved cookies."""
    session = await db.get("browser_sessions", session_id)
    if not session:
        raise HTTPException(404, "Session not found")

    cookies_raw = session.get("cookies", "[]")
    cookies = json.loads(cookies_raw) if isinstance(cookies_raw, str) else cookies_raw

    try:
        from playwright.async_api import async_playwright

        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-dev-shm-usage"],
            )
            context = await browser.new_context()
            # Add cookies
            for c in cookies:
                cookie = {
                    "name": c.get("name", ""),
                    "value": c.get("value", ""),
                    "domain": c.get("domain", session["domain"]),
                    "path": c.get("path", "/"),
                }
                try:
                    await context.add_cookies([cookie])
                except Exception:
                    pass
            page = await context.new_page()
            await page.goto(req.test_url, wait_until="networkidle", timeout=30000)
            screenshot_path = await screenshot_manager.capture(page, session_id, "test")
            title = await page.title()
            await browser.close()

        return {
            "ok": True,
            "title": title,
            "screenshot": screenshot_path,
        }
    except Exception as e:
        logger.error(f"Session test failed: {e}")
        raise HTTPException(500, f"Test failed: {str(e)}")


# ── Screenshot routes ──

@router.get("/tasks/{task_id}/screenshots")
async def list_task_screenshots(task_id: str, user: dict = Depends(get_current_user)):
    """List all screenshots for a task."""
    return screenshot_manager.list_screenshots(task_id)


@router.get("/screenshots/{filename}")
async def get_screenshot(filename: str, user: dict = Depends(get_current_user)):
    """Serve a screenshot file."""
    filepath = SCREENSHOT_DIR / filename
    if not filepath.exists():
        raise HTTPException(404, "Screenshot not found")
    return FileResponse(str(filepath), media_type="image/png")
