"""FastAPI application - main entry point."""
import json
from datetime import datetime
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from loguru import logger

from src.core.config import settings, BASE_DIR
from src.core.database import init_db
from src.api.v1 import projects, tasks, workers, data, system
from src.api.ws import router as ws_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    logger.info("AI Spider started")
    yield
    logger.info("AI Spider stopped")


app = FastAPI(title="AI Spider", version="2.0.0", lifespan=lifespan)

# ── Include routers ──
app.include_router(projects.router, prefix="/api/v1", tags=["projects"])
app.include_router(tasks.router, prefix="/api/v1", tags=["tasks"])
app.include_router(workers.router, prefix="/api/v1", tags=["workers"])
app.include_router(data.router, prefix="/api/v1", tags=["data"])
app.include_router(system.router, prefix="/api/v1", tags=["system"])
app.include_router(ws_router)

# Also mount under /api/ for backward compat
app.include_router(projects.router, prefix="/api", tags=["projects-compat"], include_in_schema=False)
app.include_router(tasks.router, prefix="/api", tags=["tasks-compat"], include_in_schema=False)

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
    log_path = BASE_DIR / "data" / "app.log"
    if not log_path.exists():
        return {"lines": []}
    lines = log_path.read_text("utf-8").strip().split("\n")
    return {"lines": lines[-limit:]}


def main():
    import uvicorn
    uvicorn.run("src.api.app:app", host=settings.host, port=settings.port, reload=settings.debug)


if __name__ == "__main__":
    main()
