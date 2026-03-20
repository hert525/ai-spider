"""FastAPI application - main entry point."""
from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.responses import FileResponse
from loguru import logger
from starlette.middleware.base import BaseHTTPMiddleware

from src.core.config import settings, BASE_DIR
from src.core.logging import setup_logging
from src.core.database import init_db, db
from src.api.v1 import projects, tasks, workers, data, system, auth, admin
from src.api.v1.proxy_admin import router as proxy_admin_router
from src.api.v1.settings import router as settings_router
from src.api.v1.deploy import router as deploy_router
from src.api.v1.seeds import router as seeds_router
from src.api.v1.browser_sessions import router as browser_sessions_router
from src.api.v1.stats import router as stats_router
from src.api.v1.export import router as export_router
from src.api.v1.notifications import router as notifications_router
from src.api.v1.quota import router as quota_router
from src.api.ws import ws_manager

# Configure logging before anything else
setup_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    # Initialize seed templates if table is empty
    from src.core.seeds import SEED_TEMPLATES
    seed_count = await db.count("seed_templates")
    if seed_count == 0:
        from src.core.models import _uid
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat()
        for tmpl in SEED_TEMPLATES:
            record = {
                "id": _uid(),
                "download_count": 0,
                "rating": 0,
                "rating_count": 0,
                "status": "active",
                "author": "system",
                "created_at": now,
                "updated_at": now,
                **tmpl,
            }
            await db.insert("seed_templates", record)
        logger.info(f"Initialized {len(SEED_TEMPLATES)} seed templates")
    from src.core.settings_manager import settings_manager
    await settings_manager.init()
    from src.scheduler.queue import task_queue
    from src.scheduler.cron_scheduler import cron_scheduler
    try:
        await task_queue.connect()
    except Exception as e:
        logger.warning(f"Redis connection failed: {e}. Task queue disabled.")
    await cron_scheduler.start()
    logger.info("AI Spider started")
    yield
    await cron_scheduler.stop()
    await task_queue.close()
    logger.info("AI Spider stopped")


app = FastAPI(
    title="AI Spider API",
    description="AI驱动的智能爬虫平台",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# ── Include routers ──
app.include_router(auth.router, prefix="/api/v1", tags=["auth"])
app.include_router(projects.router, prefix="/api/v1", tags=["projects"])
app.include_router(tasks.router, prefix="/api/v1", tags=["tasks"])
app.include_router(workers.router, prefix="/api/v1", tags=["workers"])
app.include_router(data.router, prefix="/api/v1", tags=["data"])
app.include_router(system.router, prefix="/api/v1", tags=["system"])
app.include_router(admin.router, prefix="/api/v1")
app.include_router(proxy_admin_router, prefix="/api/v1")
app.include_router(settings_router, prefix="/api/v1")
app.include_router(deploy_router, prefix="/api/v1")
app.include_router(seeds_router, prefix="/api/v1")
app.include_router(browser_sessions_router, prefix="/api/v1")
app.include_router(stats_router, prefix="/api/v1")
app.include_router(export_router, prefix="/api/v1")
app.include_router(notifications_router, prefix="/api/v1")
app.include_router(quota_router, prefix="/api/v1")

# Also mount under /api/ for backward compat
app.include_router(projects.router, prefix="/api", tags=["projects-compat"], include_in_schema=False)
app.include_router(tasks.router, prefix="/api", tags=["tasks-compat"], include_in_schema=False)

# ── Request logging middleware ──
class RequestLogMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        start = time.monotonic()
        response = await call_next(request)
        duration = (time.monotonic() - start) * 1000
        if not request.url.path.startswith("/static"):
            logger.info(f"{request.method} {request.url.path} → {response.status_code} ({duration:.0f}ms)")
        return response

app.add_middleware(RequestLogMiddleware)


# ── Rate limit middleware ──
class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        api_key = request.headers.get("X-API-Key") or request.query_params.get("api_key")
        if api_key and api_key.startswith("sk-"):
            from src.core.quota import quota_manager
            allowed = await quota_manager.check_rate_limit(api_key, limit=60, window=60)
            if not allowed:
                return JSONResponse({"error": "Rate limit exceeded (60/min)"}, status_code=429)
        return await call_next(request)

app.add_middleware(RateLimitMiddleware)


# ── Global exception handlers ──
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.detail},
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception(f"Unhandled error: {request.method} {request.url}")
    return JSONResponse(
        status_code=500,
        content={"error": str(exc), "detail": "Internal server error"},
    )


WEB_DIR = Path(__file__).resolve().parent.parent / "web"


@app.get("/")
async def index():
    p = WEB_DIR / "templates" / "index.html"
    if p.exists():
        return HTMLResponse(p.read_text("utf-8"))
    return HTMLResponse("<h1>AI Spider</h1>")


@app.get("/admin")
async def admin_page():
    p = WEB_DIR / "templates" / "admin.html"
    if p.exists():
        return HTMLResponse(p.read_text("utf-8"))
    return HTMLResponse("<h1>Admin</h1>")


@app.get("/login")
async def login_page():
    """登录/注册页面"""
    p = WEB_DIR / "templates" / "login.html"
    if p.exists():
        return FileResponse(str(p), media_type="text/html")
    return HTMLResponse("<h1>Login</h1>")


# ── Admin API (backward compat wrapper) ──
@app.get("/admin/api/dashboard")
async def admin_dashboard():
    from src.scheduler.task_manager import task_manager
    from src.scheduler.worker import worker_manager
    from src.core.database import db
    
    task_stats = await task_manager.stats()
    worker_stats = await worker_manager.stats()
    project_count = await db.count("projects")
    
    return {
        "tasks": task_stats,
        "workers": worker_stats,
        "projects": {"total": project_count},
    }


@app.get("/admin/api/tasks")
async def admin_list_tasks(status: str = "", limit: int = 50):
    from src.scheduler.task_manager import task_manager
    tasks_list = await task_manager.list_tasks(status=status or None, limit=limit)
    return [t.model_dump() for t in tasks_list]


@app.get("/admin/api/workers")
async def admin_list_workers():
    from src.scheduler.worker import worker_manager
    workers_list = await worker_manager.list_workers()
    return [w.model_dump() for w in workers_list]


@app.post("/admin/api/workers/register")
async def admin_register_worker(req: dict):
    from src.scheduler.worker import worker_manager
    w = await worker_manager.register(**req)
    return w.model_dump()


@app.post("/admin/api/workers/{wid}/heartbeat")
async def admin_heartbeat(wid: str, req: dict):
    from src.scheduler.worker import worker_manager
    w = await worker_manager.heartbeat(wid, **req)
    if not w:
        from fastapi import HTTPException
        raise HTTPException(404)
    return w.model_dump()


@app.get("/admin/api/logs")
async def admin_logs(limit: int = 100):
    from src.core.logging import LOG_DIR
    # Find latest spider log file
    log_files = sorted(LOG_DIR.glob("spider_*.log"), reverse=True)
    if not log_files:
        return {"lines": []}
    lines = log_files[0].read_text("utf-8").strip().split("\n")
    return {"lines": lines[-limit:]}


@app.websocket("/ws/{api_key}")
async def websocket_endpoint(websocket: WebSocket, api_key: str):
    """WebSocket endpoint for real-time updates."""
    await websocket.accept()
    users = await db.query("SELECT * FROM users WHERE api_key = ?", [api_key])
    if not users:
        await websocket.close(code=4001, reason="Invalid API key")
        return

    is_admin = users[0].get("role") == "admin"
    # Already accepted above, just register
    if api_key not in ws_manager._connections:
        ws_manager._connections[api_key] = set()
    ws_manager._connections[api_key].add(websocket)
    if is_admin:
        ws_manager._admin_connections.add(websocket)
    try:
        while True:
            data_msg = await websocket.receive_text()
            msg = json.loads(data_msg)
            if msg.get("type") == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        await ws_manager.disconnect(websocket, api_key)


def main():
    import uvicorn
    uvicorn.run("src.api.app:app", host=settings.host, port=settings.port, reload=settings.debug)


if __name__ == "__main__":
    main()
