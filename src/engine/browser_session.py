"""Browser session manager — persist login state across crawls."""
from __future__ import annotations

import json, os
from pathlib import Path
from loguru import logger

SESSION_DIR = Path("data/browser_sessions")


class BrowserSessionManager:
    """管理浏览器登录态，支持：
    1. 保存/加载Playwright browser context的storage state (cookies + localStorage)
    2. 按用户+站点隔离
    3. 过期管理
    """

    def __init__(self):
        SESSION_DIR.mkdir(parents=True, exist_ok=True)

    def _session_path(self, user_id: str, domain: str) -> Path:
        """Get session file path for user+domain."""
        safe_domain = domain.replace(".", "_").replace("/", "_")
        return SESSION_DIR / f"{user_id}_{safe_domain}.json"

    async def save_session(self, user_id: str, domain: str, context):
        """Save browser context storage state."""
        path = self._session_path(user_id, domain)
        state = await context.storage_state()
        with open(path, "w") as f:
            json.dump(state, f, ensure_ascii=False)
        logger.info(f"Session saved: {user_id}@{domain}")

    async def load_session(self, user_id: str, domain: str) -> dict | None:
        """Load saved storage state."""
        path = self._session_path(user_id, domain)
        if not path.exists():
            return None
        try:
            with open(path) as f:
                state = json.load(f)
            logger.info(f"Session loaded: {user_id}@{domain}")
            return state
        except Exception as e:
            logger.warning(f"Failed to load session: {e}")
            return None

    async def delete_session(self, user_id: str, domain: str):
        """Delete saved session."""
        path = self._session_path(user_id, domain)
        if path.exists():
            path.unlink()

    async def list_sessions(self, user_id: str) -> list[dict]:
        """List all saved sessions for a user."""
        sessions = []
        for f in SESSION_DIR.glob(f"{user_id}_*.json"):
            domain = f.stem.replace(f"{user_id}_", "").replace("_", ".")
            stat = f.stat()
            sessions.append({
                "domain": domain,
                "size": stat.st_size,
                "modified": stat.st_mtime,
            })
        return sessions


session_manager = BrowserSessionManager()
