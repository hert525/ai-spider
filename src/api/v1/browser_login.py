"""Browser Login API — interactive remote browser for session capture.

Flow:
1. POST /browser-login/start → launches Playwright, returns session_id
2. WS receives screenshots as base64 images (type: browser_frame)
3. POST /browser-login/{sid}/click → click at coordinates
4. POST /browser-login/{sid}/type → type text
5. POST /browser-login/{sid}/navigate → go to URL
6. POST /browser-login/{sid}/save → save cookies to browser_sessions
7. POST /browser-login/{sid}/stop → close browser
"""
from __future__ import annotations

import asyncio
import base64
import json
from datetime import datetime, timezone
from urllib.parse import urlparse

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from loguru import logger

from src.core.database import db
from src.core.models import _uid
from src.core.auth import get_current_user

router = APIRouter(prefix="/browser-login", tags=["browser-login"])

# Active browser sessions: {session_id: BrowserLoginSession}
_active_sessions: dict[str, "BrowserLoginSession"] = {}


class BrowserLoginSession:
    """Manages a single interactive browser session."""

    def __init__(self, session_id: str, api_key: str, project_id: str = ""):
        self.session_id = session_id
        self.api_key = api_key
        self.project_id = project_id
        self.browser = None
        self.context = None
        self.page = None
        self._screenshot_task = None
        self._running = False
        self._pw = None

    async def start(self, url: str):
        from playwright.async_api import async_playwright
        self._pw = await async_playwright().start()
        self.browser = await self._pw.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-blink-features=AutomationControlled"],
        )
        self.context = await self.browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        )
        # Stealth
        await self.context.add_init_script('Object.defineProperty(navigator, "webdriver", {get: () => false})')
        self.page = await self.context.new_page()
        await self.page.goto(url, wait_until="domcontentloaded", timeout=30000)
        self._running = True
        # Start screenshot loop
        self._screenshot_task = asyncio.create_task(self._screenshot_loop())

    async def _screenshot_loop(self):
        """Continuously capture and send screenshots via WS."""
        while self._running:
            try:
                screenshot_bytes = await self.page.screenshot(type="jpeg", quality=60)
                b64 = base64.b64encode(screenshot_bytes).decode("ascii")
                url = self.page.url
                title = await self.page.title()

                from src.api.ws import ws_manager
                await ws_manager.send_to_user(self.api_key, {
                    "type": "browser_frame",
                    "session_id": self.session_id,
                    "image": f"data:image/jpeg;base64,{b64}",
                    "url": url,
                    "title": title,
                })
            except Exception as e:
                if self._running:
                    logger.warning(f"Screenshot loop error: {e}")
            await asyncio.sleep(0.5)  # 2 FPS

    async def click(self, x: int, y: int):
        if self.page:
            await self.page.mouse.click(x, y)
            await asyncio.sleep(0.3)  # Wait for potential navigation

    async def type_text(self, text: str):
        if self.page:
            await self.page.keyboard.type(text, delay=50)

    async def press_key(self, key: str):
        if self.page:
            await self.page.keyboard.press(key)

    async def navigate(self, url: str):
        if self.page:
            await self.page.goto(url, wait_until="domcontentloaded", timeout=30000)

    async def scroll(self, delta_y: int):
        if self.page:
            await self.page.mouse.wheel(0, delta_y)

    async def get_cookies(self) -> list[dict]:
        if self.context:
            return await self.context.cookies()
        return []

    async def stop(self):
        self._running = False
        if self._screenshot_task:
            self._screenshot_task.cancel()
            try:
                await self._screenshot_task
            except asyncio.CancelledError:
                pass
        if self.browser:
            await self.browser.close()
        if self._pw:
            await self._pw.stop()


# ── Request Models ──

class StartReq(BaseModel):
    url: str
    project_id: str = ""

class ClickReq(BaseModel):
    x: int
    y: int

class TypeReq(BaseModel):
    text: str

class KeyReq(BaseModel):
    key: str  # e.g. "Enter", "Tab", "Backspace"

class NavigateReq(BaseModel):
    url: str

class ScrollReq(BaseModel):
    delta_y: int = 300

class SaveReq(BaseModel):
    name: str = ""
    project_id: str = ""


# ── Routes ──

@router.post("/start")
async def start_login(req: StartReq, user: dict = Depends(get_current_user)):
    """Start an interactive browser session for login."""
    # Limit to 1 active session per user
    for sid, sess in list(_active_sessions.items()):
        if sess.api_key == user.get("api_key"):
            await sess.stop()
            del _active_sessions[sid]

    session_id = _uid()
    session = BrowserLoginSession(
        session_id=session_id,
        api_key=user.get("api_key", ""),
        project_id=req.project_id,
    )

    try:
        await session.start(req.url)
    except Exception as e:
        logger.error(f"Browser login start failed: {e}")
        raise HTTPException(500, f"Failed to start browser: {str(e)}")

    _active_sessions[session_id] = session
    logger.info(f"Browser login started: {session_id} → {req.url}")

    return {
        "session_id": session_id,
        "url": req.url,
        "viewport": {"width": 1280, "height": 800},
    }


def _get_session(sid: str) -> BrowserLoginSession:
    session = _active_sessions.get(sid)
    if not session:
        raise HTTPException(404, "Browser session not found or expired")
    return session


@router.post("/{sid}/click")
async def click(sid: str, req: ClickReq, user: dict = Depends(get_current_user)):
    session = _get_session(sid)
    await session.click(req.x, req.y)
    return {"ok": True}


@router.post("/{sid}/type")
async def type_text(sid: str, req: TypeReq, user: dict = Depends(get_current_user)):
    session = _get_session(sid)
    await session.type_text(req.text)
    return {"ok": True}


@router.post("/{sid}/key")
async def press_key(sid: str, req: KeyReq, user: dict = Depends(get_current_user)):
    session = _get_session(sid)
    await session.press_key(req.key)
    return {"ok": True}


@router.post("/{sid}/navigate")
async def navigate(sid: str, req: NavigateReq, user: dict = Depends(get_current_user)):
    session = _get_session(sid)
    await session.navigate(req.url)
    return {"ok": True}


@router.post("/{sid}/scroll")
async def scroll(sid: str, req: ScrollReq, user: dict = Depends(get_current_user)):
    session = _get_session(sid)
    await session.scroll(req.delta_y)
    return {"ok": True}


@router.post("/{sid}/save")
async def save_session(sid: str, req: SaveReq, user: dict = Depends(get_current_user)):
    """Save cookies from current browser session."""
    session = _get_session(sid)
    cookies = await session.get_cookies()
    if not cookies:
        raise HTTPException(400, "No cookies to save")

    # Get domain from current page URL
    current_url = session.page.url if session.page else ""
    domain = urlparse(current_url).hostname or ""

    project_id = req.project_id or session.project_id or ""
    now = datetime.now(timezone.utc).isoformat()
    record_id = _uid()

    # Upsert: remove existing for same user+domain+project
    if project_id:
        existing = await db.query(
            "SELECT id FROM browser_sessions WHERE user_id = ? AND domain = ? AND project_id = ?",
            [user["id"], domain, project_id],
        )
    else:
        existing = await db.query(
            "SELECT id FROM browser_sessions WHERE user_id = ? AND domain = ? AND (project_id IS NULL OR project_id = '')",
            [user["id"], domain],
        )
    for e in existing:
        await db.delete("browser_sessions", e["id"])

    await db.insert("browser_sessions", {
        "id": record_id,
        "user_id": user["id"],
        "domain": domain,
        "project_id": project_id,
        "name": req.name or f"Login session - {domain}",
        "cookies": json.dumps(cookies, ensure_ascii=False),
        "local_storage": "{}",
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "status": "active",
        "expires_at": "",
        "created_at": now,
        "updated_at": now,
    })

    logger.info(f"Browser login saved: {record_id} domain={domain} cookies={len(cookies)}")

    return {
        "id": record_id,
        "domain": domain,
        "cookie_count": len(cookies),
        "url": current_url,
    }


@router.post("/{sid}/stop")
async def stop_login(sid: str, user: dict = Depends(get_current_user)):
    """Stop and close the browser session."""
    session = _get_session(sid)
    await session.stop()
    del _active_sessions[sid]
    logger.info(f"Browser login stopped: {sid}")
    return {"ok": True}


@router.get("/active")
async def list_active(user: dict = Depends(get_current_user)):
    """List active browser login sessions for current user."""
    api_key = user.get("api_key", "")
    result = []
    for sid, sess in _active_sessions.items():
        if sess.api_key == api_key:
            result.append({
                "session_id": sid,
                "url": sess.page.url if sess.page else "",
                "project_id": sess.project_id,
            })
    return result
