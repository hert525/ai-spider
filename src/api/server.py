"""
FastAPI server - API + WebSocket for the AI Spider platform.
"""
import json
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel
from typing import Optional
from loguru import logger
from pathlib import Path

from src.ai.generator import generate_crawler, refine_crawler, generate_crawler_stream
from src.executor.sandbox import run_in_sandbox
from src.core.store import store
from src.core.models import CrawlerStatus

app = FastAPI(title="AI Spider", version="0.1.0")

# Static files
STATIC_DIR = Path(__file__).resolve().parent.parent / "web"
if (STATIC_DIR / "static").exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR / "static")), name="static")


# ── Request models ──────────────────────────────────────
class CreateRequest(BaseModel):
    description: str
    target_url: str = ""
    name: str = ""


class RefineRequest(BaseModel):
    feedback: str


class TestRequest(BaseModel):
    target_url: str = ""
    max_pages: int = 5


# ── REST API ────────────────────────────────────────────
@app.get("/")
async def index():
    html_path = STATIC_DIR / "templates" / "index.html"
    if html_path.exists():
        return HTMLResponse(html_path.read_text(encoding="utf-8"))
    return {"message": "AI Spider API", "docs": "/docs"}


@app.get("/api/projects")
async def list_projects():
    projects = store.list()
    return [p.model_dump() for p in projects]


@app.post("/api/projects")
async def create_project(req: CreateRequest):
    """Create a new crawler project: generate code from description."""
    logger.info(f"Creating project: {req.description[:50]}...")

    # Generate crawler code via AI
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


@app.get("/api/projects/{project_id}")
async def get_project(project_id: str):
    proj = store.get(project_id)
    if not proj:
        raise HTTPException(404, "Project not found")
    return proj.model_dump()


@app.post("/api/projects/{project_id}/test")
async def test_project(project_id: str, req: TestRequest):
    """Run the crawler in sandbox and return results."""
    proj = store.get(project_id)
    if not proj:
        raise HTTPException(404, "Project not found")

    url = req.target_url or proj.target_url
    if not url:
        raise HTTPException(400, "No target URL specified")

    store.update(project_id, status=CrawlerStatus.TESTING)

    result = await run_in_sandbox(proj.code, url, max_pages=req.max_pages)

    # Save test results
    test_entry = {
        "version": proj.version,
        "status": result.status,
        "output": result.output[:10],  # Preview
        "error": result.error,
        "pages_crawled": result.pages_crawled,
        "duration_ms": result.duration_ms,
    }
    test_results = proj.test_results + [test_entry]

    new_status = CrawlerStatus.TESTED if result.status == "success" else CrawlerStatus.FAILED
    store.update(project_id, status=new_status, test_results=test_results)

    return result.model_dump()


@app.post("/api/projects/{project_id}/refine")
async def refine_project(project_id: str, req: RefineRequest):
    """Refine crawler code based on user feedback."""
    proj = store.get(project_id)
    if not proj:
        raise HTTPException(404, "Project not found")

    # Get latest test results for context
    last_results = proj.test_results[-1]["output"] if proj.test_results else []

    new_code = await refine_crawler(proj.code, req.feedback, last_results)

    messages = proj.messages + [
        {"role": "user", "content": req.feedback},
        {"role": "assistant", "content": f"已根据反馈修改代码 v{proj.version + 1}"},
    ]

    store.update(
        project_id,
        code=new_code,
        version=proj.version + 1,
        status=CrawlerStatus.DRAFT,
        messages=messages,
    )

    return store.get(project_id).model_dump()


@app.post("/api/projects/{project_id}/approve")
async def approve_project(project_id: str):
    """Approve the crawler for deployment."""
    proj = store.get(project_id)
    if not proj:
        raise HTTPException(404, "Project not found")
    store.update(project_id, status=CrawlerStatus.APPROVED)
    return {"status": "approved"}


@app.delete("/api/projects/{project_id}")
async def delete_project(project_id: str):
    if not store.delete(project_id):
        raise HTTPException(404, "Project not found")
    return {"status": "deleted"}


# ── WebSocket for streaming ─────────────────────────────
@app.websocket("/ws/generate")
async def ws_generate(ws: WebSocket):
    """WebSocket endpoint for streaming code generation."""
    await ws.accept()
    try:
        while True:
            data = await ws.receive_json()
            action = data.get("action", "generate")

            if action == "generate":
                description = data.get("description", "")
                target_url = data.get("target_url", "")
                await ws.send_json({"type": "start"})
                full_code = ""
                async for chunk in generate_crawler_stream(description, target_url):
                    full_code += chunk
                    await ws.send_json({"type": "chunk", "content": chunk})
                await ws.send_json({"type": "done", "code": full_code})

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected")


# ── Entrypoint ──────────────────────────────────────────
def main():
    import uvicorn
    from src.core.config import settings
    uvicorn.run(
        "src.api.server:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
    )


if __name__ == "__main__":
    main()
