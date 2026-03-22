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
from src.api.v1.probe import router as probe_router
from src.api.v1.proxy_admin import router as proxy_admin_router
from src.api.v1.settings import router as settings_router
from src.api.v1.deploy import router as deploy_router
from src.api.v1.seeds import router as seeds_router
from src.api.v1.browser_sessions import router as browser_sessions_router
from src.api.v1.stats import router as stats_router
from src.api.v1.monitoring import router as monitoring_router
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
    # 关闭数据库连接池
    from src.core.database import close_db
    await close_db()
    logger.info("AI Spider stopped")


import os as _os
_debug = _os.getenv("DEBUG", "false").lower() == "true"

app = FastAPI(
    title="AI Spider API",
    description="AI驱动的智能爬虫平台",
    version="2.0.0",
    docs_url="/docs" if _debug else None,
    redoc_url="/redoc" if _debug else None,
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
app.include_router(monitoring_router, prefix="/api/v1")
app.include_router(export_router, prefix="/api/v1")
app.include_router(notifications_router, prefix="/api/v1")
app.include_router(quota_router, prefix="/api/v1")
app.include_router(probe_router, prefix="/api/v1", tags=["probe"])

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

# ── IP限流中间件 ──
from src.api.middleware.rate_limit import IPRateLimitMiddleware
app.add_middleware(IPRateLimitMiddleware, minute_limit=60, hour_limit=1000)

# ── CORS ──
from starlette.middleware.cors import CORSMiddleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://rthe525.top",
        "https://www.rthe525.top",
        "http://127.0.0.1:8901",
        "http://localhost:8901",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["X-API-Key", "Content-Type", "Authorization"],
)


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
    """WebSocket endpoint for real-time updates — 含服务端心跳检测。"""
    await websocket.accept()
    users = await db.query("SELECT * FROM users WHERE api_key = ?", [api_key])
    if not users:
        await websocket.close(code=4001, reason="Invalid API key")
        return

    is_admin = users[0].get("role") == "admin"
    # 注册连接
    if api_key not in ws_manager._connections:
        ws_manager._connections[api_key] = set()
    ws_manager._connections[api_key].add(websocket)
    if is_admin:
        ws_manager._admin_connections.add(websocket)

    import asyncio as _asyncio

    last_pong_time = time.monotonic()

    async def _heartbeat_loop():
        """服务端每30秒发送ping，检测客户端存活"""
        nonlocal last_pong_time
        while True:
            await _asyncio.sleep(30)
            # 检查是否超过90秒无pong响应
            if time.monotonic() - last_pong_time > 90:
                logger.warning(f"WS心跳超时(90s)，断开: {api_key[:10]}...")
                await websocket.close(code=4002, reason="Heartbeat timeout")
                return
            try:
                await websocket.send_json({"type": "ping"})
            except Exception:
                return

    heartbeat_task = _asyncio.create_task(_heartbeat_loop())

    try:
        while True:
            data_msg = await websocket.receive_text()
            msg = json.loads(data_msg)
            if msg.get("type") == "ping":
                await websocket.send_json({"type": "pong"})
            elif msg.get("type") == "pong":
                # 客户端回复pong，更新存活时间
                last_pong_time = time.monotonic()
    except WebSocketDisconnect:
        pass
    finally:
        heartbeat_task.cancel()
        await ws_manager.disconnect(websocket, api_key)


def main():
    import uvicorn
    uvicorn.run("src.api.app:app", host=settings.host, port=settings.port, reload=settings.debug)


if __name__ == "__main__":
    main()


# ── 健康检查 ──
@app.get("/health")
async def health_check():
    """健康检查端点 — 用于负载均衡器/K8s探针"""
    import time
    checks = {"status": "ok", "timestamp": time.time()}

    # 数据库
    try:
        from src.core.database import db, USE_PG
        cnt = await db.count("users")
        checks["database"] = {"ok": True, "backend": "postgresql" if USE_PG else "sqlite", "users": cnt}
    except Exception as e:
        checks["database"] = {"ok": False, "error": str(e)}
        checks["status"] = "degraded"

    # Redis
    try:
        from src.scheduler.queue import task_queue
        if task_queue._redis:
            await task_queue._redis.ping()
            checks["redis"] = {"ok": True}
        else:
            checks["redis"] = {"ok": False, "error": "not connected"}
    except Exception as e:
        checks["redis"] = {"ok": False, "error": str(e)}

    # Worker
    try:
        workers = await db.list("workers", where={"status": "online"}, order="registered_at DESC")
        checks["workers"] = {"ok": len(workers) > 0, "online": len(workers)}
    except Exception:
        checks["workers"] = {"ok": False, "online": 0}

    # PG连接池
    if USE_PG:
        try:
            from src.core.database import _pool
            if _pool:
                checks["pg_pool"] = {
                    "size": _pool.get_size(),
                    "free": _pool.get_idle_size(),
                    "min": _pool.get_min_size(),
                    "max": _pool.get_max_size(),
                }
        except Exception:
            pass

    return checks
