"""
FastAPI server - User API + Admin API + WebSocket.
"""
import json
from datetime import datetime
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from typing import Optional
from loguru import logger
from pathlib import Path

from src.ai.generator import generate_crawler, refine_crawler, generate_crawler_stream
from src.executor.sandbox import run_in_sandbox
from src.core.store import store
from src.core.tasks import task_store, Task, TaskRun, TaskStatus, TaskType
from src.core.workers import worker_manager
from src.core.models import CrawlerStatus

app = FastAPI(title="AI Spider", version="0.2.0")

WEB_DIR = Path(__file__).resolve().parent.parent / "web"


# ── Request Models ──────────────────────────────────────
class CreateProjectReq(BaseModel):
    description: str
    target_url: str = ""
    name: str = ""

class RefineReq(BaseModel):
    feedback: str

class TestReq(BaseModel):
    target_url: str = ""
    max_pages: int = 5

class CreateTaskReq(BaseModel):
    project_id: str
    name: str = ""
    target_urls: list[str] = []
    task_type: str = "one_time"
    cron_expr: str = ""
    max_pages: int = 100
    max_items: int = 10000
    timeout_seconds: int = 300
    concurrency: int = 3
    priority: int = 5

class WorkerRegisterReq(BaseModel):
    worker_id: str
    hostname: str = ""
    ip: str = ""
    max_concurrency: int = 3
    tags: list[str] = []

class WorkerHeartbeatReq(BaseModel):
    status: str = "online"
    cpu_percent: float = 0
    memory_mb: float = 0
    active_jobs: int = 0
    total_completed: int = 0
    total_failed: int = 0


# ══════════════════════════════════════════════════════════
#  PAGES
# ══════════════════════════════════════════════════════════

@app.get("/")
async def index():
    """User dashboard."""
    p = WEB_DIR / "templates" / "index.html"
    if p.exists():
        return HTMLResponse(p.read_text("utf-8"))
    return HTMLResponse("<h1>AI Spider</h1><p><a href='/admin'>Admin</a> | <a href='/docs'>API Docs</a></p>")

@app.get("/admin")
async def admin_page():
    """Admin dashboard."""
    p = WEB_DIR / "templates" / "admin.html"
    if p.exists():
        return HTMLResponse(p.read_text("utf-8"))
    return HTMLResponse("<h1>Admin</h1>")


# ══════════════════════════════════════════════════════════
#  USER API — /api/
# ══════════════════════════════════════════════════════════

# ── Projects ────────────────────────────────────────────
@app.get("/api/projects")
async def list_projects():
    return [p.model_dump() for p in store.list()]

@app.post("/api/projects")
async def create_project(req: CreateProjectReq):
    logger.info(f"Creating project: {req.description[:50]}...")
    code = await generate_crawler(req.description, req.target_url)
    project = store.create(
        name=req.name or req.description[:30],
        description=req.description,
        target_url=req.target_url,
        code=code,
        status=CrawlerStatus.DRAFT,
        messages=[
            {"role": "user", "content": req.description},
            {"role": "assistant", "content": f"已生成爬虫代码 v1（{len(code)}字符）"},
        ],
    )
    return project.model_dump()

@app.get("/api/projects/{pid}")
async def get_project(pid: str):
    proj = store.get(pid)
    if not proj:
        raise HTTPException(404, "Project not found")
    return proj.model_dump()

@app.delete("/api/projects/{pid}")
async def delete_project(pid: str):
    if not store.delete(pid):
        raise HTTPException(404)
    return {"ok": True}

@app.post("/api/projects/{pid}/test")
async def test_project(pid: str, req: TestReq):
    proj = store.get(pid)
    if not proj:
        raise HTTPException(404)
    url = req.target_url or proj.target_url
    if not url:
        raise HTTPException(400, "No target URL")
    store.update(pid, status=CrawlerStatus.TESTING)
    result = await run_in_sandbox(proj.code, url, max_pages=req.max_pages)
    test_entry = {
        "version": proj.version,
        "status": result.status,
        "output": result.output[:10],
        "error": result.error,
        "pages_crawled": result.pages_crawled,
        "duration_ms": result.duration_ms,
    }
    new_status = CrawlerStatus.TESTED if result.status == "success" else CrawlerStatus.FAILED
    store.update(pid, status=new_status, test_results=proj.test_results + [test_entry])
    return result.model_dump()

@app.post("/api/projects/{pid}/refine")
async def refine_project(pid: str, req: RefineReq):
    proj = store.get(pid)
    if not proj:
        raise HTTPException(404)
    last_results = proj.test_results[-1]["output"] if proj.test_results else []
    new_code = await refine_crawler(proj.code, req.feedback, last_results)
    messages = proj.messages + [
        {"role": "user", "content": req.feedback},
        {"role": "assistant", "content": f"已修改代码 v{proj.version + 1}"},
    ]
    store.update(pid, code=new_code, version=proj.version + 1, status=CrawlerStatus.DRAFT, messages=messages)
    return store.get(pid).model_dump()

@app.post("/api/projects/{pid}/approve")
async def approve_project(pid: str):
    proj = store.get(pid)
    if not proj:
        raise HTTPException(404)
    store.update(pid, status=CrawlerStatus.APPROVED)
    return {"ok": True}

# ── Tasks (User) ────────────────────────────────────────
@app.get("/api/tasks")
async def list_tasks(project_id: str = "", status: str = ""):
    return [t.model_dump() for t in task_store.list(
        project_id=project_id or None,
        status=TaskStatus(status) if status else None
    )]

@app.post("/api/tasks")
async def create_task(req: CreateTaskReq):
    proj = store.get(req.project_id)
    if not proj:
        raise HTTPException(400, "Project not found")
    if proj.status not in (CrawlerStatus.TESTED, CrawlerStatus.APPROVED):
        raise HTTPException(400, "Project must be tested/approved before creating tasks")
    urls = req.target_urls or ([proj.target_url] if proj.target_url else [])
    task = task_store.create(
        project_id=req.project_id,
        name=req.name or proj.name,
        task_type=TaskType(req.task_type),
        target_urls=urls,
        max_pages=req.max_pages,
        max_items=req.max_items,
        timeout_seconds=req.timeout_seconds,
        concurrency=req.concurrency,
        priority=req.priority,
        cron_expr=req.cron_expr or None,
    )
    return task.model_dump()

@app.get("/api/tasks/{tid}")
async def get_task(tid: str):
    task = task_store.get(tid)
    if not task:
        raise HTTPException(404)
    return task.model_dump()

@app.post("/api/tasks/{tid}/cancel")
async def cancel_task(tid: str):
    task = task_store.update(tid, status=TaskStatus.CANCELLED)
    if not task:
        raise HTTPException(404)
    return {"ok": True}

@app.delete("/api/tasks/{tid}")
async def delete_task(tid: str):
    if not task_store.delete(tid):
        raise HTTPException(404)
    return {"ok": True}


# ══════════════════════════════════════════════════════════
#  ADMIN API — /admin/api/
# ══════════════════════════════════════════════════════════

@app.get("/admin/api/dashboard")
async def admin_dashboard():
    """Overview stats for admin."""
    return {
        "tasks": task_store.stats(),
        "workers": worker_manager.stats(),
        "projects": {
            "total": len(store.list()),
            "by_status": _count_by_status(),
        },
    }

@app.get("/admin/api/tasks")
async def admin_list_tasks(status: str = "", limit: int = 50):
    tasks = task_store.list(status=TaskStatus(status) if status else None)
    return [t.model_dump() for t in tasks[:limit]]

@app.get("/admin/api/tasks/{tid}")
async def admin_get_task(tid: str):
    task = task_store.get(tid)
    if not task:
        raise HTTPException(404)
    return task.model_dump()

@app.post("/admin/api/tasks/{tid}/retry")
async def admin_retry_task(tid: str):
    task = task_store.get(tid)
    if not task:
        raise HTTPException(404)
    task_store.update(tid, status=TaskStatus.QUEUED)
    return {"ok": True}

@app.post("/admin/api/tasks/{tid}/pause")
async def admin_pause_task(tid: str):
    task_store.update(tid, status=TaskStatus.PAUSED)
    return {"ok": True}

@app.post("/admin/api/tasks/{tid}/resume")
async def admin_resume_task(tid: str):
    task_store.update(tid, status=TaskStatus.QUEUED)
    return {"ok": True}

# ── Workers ─────────────────────────────────────────────
@app.get("/admin/api/workers")
async def admin_list_workers():
    return [w.model_dump() for w in worker_manager.list()]

@app.post("/admin/api/workers/register")
async def admin_register_worker(req: WorkerRegisterReq):
    w = worker_manager.register(
        req.worker_id, hostname=req.hostname, ip=req.ip,
        max_concurrency=req.max_concurrency, tags=req.tags,
    )
    return w.model_dump()

@app.post("/admin/api/workers/{wid}/heartbeat")
async def admin_worker_heartbeat(wid: str, req: WorkerHeartbeatReq):
    w = worker_manager.heartbeat(wid, **req.model_dump())
    if not w:
        raise HTTPException(404, "Worker not registered")
    return w.model_dump()

@app.delete("/admin/api/workers/{wid}")
async def admin_remove_worker(wid: str):
    worker_manager.unregister(wid)
    return {"ok": True}

# ── Logs ────────────────────────────────────────────────
@app.get("/admin/api/logs")
async def admin_logs(limit: int = 100):
    """Read recent application logs."""
    log_path = BASE_DIR / "data" / "app.log"
    if not log_path.exists():
        return {"lines": []}
    lines = log_path.read_text("utf-8").strip().split("\n")
    return {"lines": lines[-limit:]}


# ══════════════════════════════════════════════════════════
#  WEBSOCKET
# ══════════════════════════════════════════════════════════

@app.websocket("/ws/generate")
async def ws_generate(ws: WebSocket):
    await ws.accept()
    try:
        while True:
            data = await ws.receive_json()
            description = data.get("description", "")
            target_url = data.get("target_url", "")
            await ws.send_json({"type": "start"})
            full_code = ""
            async for chunk in generate_crawler_stream(description, target_url):
                full_code += chunk
                await ws.send_json({"type": "chunk", "content": chunk})
            await ws.send_json({"type": "done", "code": full_code})
    except WebSocketDisconnect:
        pass


# ── Helpers ─────────────────────────────────────────────
def _count_by_status() -> dict:
    counts = {}
    for p in store.list():
        counts[p.status] = counts.get(p.status, 0) + 1
    return counts


# ── Entrypoint ──────────────────────────────────────────
def main():
    import uvicorn
    from src.core.config import settings
    uvicorn.run("src.api.server:app", host=settings.host, port=settings.port, reload=settings.debug)

if __name__ == "__main__":
    main()
