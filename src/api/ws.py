"""WebSocket manager for real-time updates."""
from __future__ import annotations

import json
import asyncio
from typing import Dict, Set
from fastapi import WebSocket, WebSocketDisconnect
from loguru import logger


class ConnectionManager:
    """Manages WebSocket connections per user."""

    def __init__(self):
        self._connections: Dict[str, Set[WebSocket]] = {}
        self._admin_connections: Set[WebSocket] = set()

    async def connect(self, ws: WebSocket, api_key: str, is_admin: bool = False):
        await ws.accept()
        if api_key not in self._connections:
            self._connections[api_key] = set()
        self._connections[api_key].add(ws)
        if is_admin:
            self._admin_connections.add(ws)
        logger.info(f"WS connected: {api_key[:10]}... (admin={is_admin})")

    async def disconnect(self, ws: WebSocket, api_key: str):
        self._connections.get(api_key, set()).discard(ws)
        self._admin_connections.discard(ws)
        logger.info(f"WS disconnected: {api_key[:10]}...")

    async def send_to_user(self, api_key: str, message: dict):
        """Send message to all connections of a user."""
        for ws in list(self._connections.get(api_key, [])):
            try:
                await ws.send_json(message)
            except Exception:
                self._connections.get(api_key, set()).discard(ws)

    async def broadcast_admin(self, message: dict):
        """Send to all admin connections."""
        for ws in list(self._admin_connections):
            try:
                await ws.send_json(message)
            except Exception:
                self._admin_connections.discard(ws)

    async def broadcast_all(self, message: dict):
        """Send to everyone."""
        for conns in self._connections.values():
            for ws in list(conns):
                try:
                    await ws.send_json(message)
                except Exception:
                    conns.discard(ws)


ws_manager = ConnectionManager()
