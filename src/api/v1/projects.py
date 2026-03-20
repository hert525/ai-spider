"""Projects API - CRUD + AI generation."""
import json
from datetime import datetime
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from loguru import logger

from src.core.database import db
from src.core.models import Project, ProjectMode, ProjectStatus, _uid

router = APIRouter()


class CreateProjectReq(BaseModel):
    description: str
    target_url: str = ""
    name: str = ""
    mode: str = "code_generator"  # "smart_scraper" or "code_generator"


class RefineReq(BaseModel):
    feedback: str


class TestReq(BaseModel):
    target_url: str = ""
    max_pages: int = 5


@router.get("/projects")
async def list_projects():
    rows = await db.list("projects")
    return rows


@router.post("/projects")
async def create_project(req: CreateProjectReq):
    mode = ProjectMode(req.mode)
    project = Project(
        name=req.name or req.description[:30],
        description=req.description,
        target_url=req.target_url,
        mode=mode,
        status=ProjectStatus.GENERATING,
    )
    await db.insert("projects", project.model_dump())
    
    try:
        if mode == ProjectMode.SMART_SCRAPER:
            from src.engine.graphs import SmartScraperGraph
            graph = SmartScraperGraph()
            state = await graph.run(req.target_url, req.description)
            extracted = state.get("extracted_data", [])
            await db.update("projects", project.id, {
                "status": ProjectStatus.GENERATED,
                "extracted_data": json.dumps(extracted, ensure_ascii=False),
                "messages": json.dumps([
                    {"role": "user", "content": req.description},
                    {"role": "assistant", "content": f"已提取 {len(extracted) if isinstance(extracted, list) else 1} 条数据"},
                ], ensure_ascii=False),
                "updated_at": datetime.now().isoformat(),
            })
        else:
            from src.engine.graphs import CodeGeneratorGraph
            graph = CodeGeneratorGraph()
            state = await graph.run(req.target_url, req.description)
            code = state.get("generated_code", "")
            v_status = state.get("validation_status", "unknown")
            await db.update("projects", project.id, {
                "status": ProjectStatus.GENERATED,
                "code": code,
                "messages": json.dumps([
                    {"role": "user", "content": req.description},
                    {"role": "assistant", "content": f"已生成爬虫代码（验证状态: {v_status}）"},
                ], ensure_ascii=False),
                "updated_at": datetime.now().isoformat(),
            })
    except Exception as e:
        logger.error(f"Generation failed: {e}")
        await db.update("projects", project.id, {
            "status": ProjectStatus.FAILED,
            "messages": json.dumps([
                {"role": "user", "content": req.description},
                {"role": "assistant", "content": f"生成失败: {str(e)}"},
            ], ensure_ascii=False),
            "updated_at": datetime.now().isoformat(),
        })

    return await db.get("projects", project.id)


@router.get("/projects/{pid}")
async def get_project(pid: str):
    proj = await db.get("projects", pid)
    if not proj:
        raise HTTPException(404, "Project not found")
    return proj


@router.delete("/projects/{pid}")
async def delete_project(pid: str):
    if not await db.delete("projects", pid):
        raise HTTPException(404)
    return {"ok": True}


@router.put("/projects/{pid}/code")
async def update_code(pid: str, req: dict):
    """Manually update project code."""
    proj = await db.get("projects", pid)
    if not proj:
        raise HTTPException(404)
    await db.update("projects", pid, {
        "code": req.get("code", ""),
        "version": proj.get("version", 1) + 1,
        "updated_at": datetime.now().isoformat(),
    })
    return await db.get("projects", pid)


@router.post("/projects/{pid}/test")
async def test_project(pid: str, req: TestReq):
    proj = await db.get("projects", pid)
    if not proj:
        raise HTTPException(404)
    
    url = req.target_url or proj.get("target_url", "")
    if not url:
        raise HTTPException(400, "No target URL")

    await db.update("projects", pid, {"status": ProjectStatus.TESTING})

    mode = proj.get("mode", "code_generator")

    if mode == "smart_scraper":
        # Re-run LLM extraction
        from src.engine.graphs.smart_scraper import SmartScraperGraph
        graph = SmartScraperGraph()
        state = await graph.run(url=url, description=proj.get("description", ""))
        extracted = state.get("extracted_data", [])
        result = {
            "output": extracted if isinstance(extracted, list) else [extracted],
            "error": state.get("error", ""),
            "pages_crawled": 1,
            "duration_ms": state.get("_exec_time_ms", 0),
        }
    else:
        from src.engine.sandbox import run_code_in_sandbox
        result = await run_code_in_sandbox(proj["code"], url)
    
    # Update test results
    test_results = proj.get("test_results", [])
    if isinstance(test_results, str):
        test_results = json.loads(test_results)
    test_results.append({
        "version": proj.get("version", 1),
        "status": "success" if not result.get("error") else "failed",
        "output_count": len(result.get("output", [])),
        "error": result.get("error", ""),
        "duration_ms": result.get("duration_ms", 0),
    })
    
    new_status = ProjectStatus.TESTED if not result.get("error") else ProjectStatus.FAILED
    await db.update("projects", pid, {
        "status": new_status,
        "test_results": json.dumps(test_results, ensure_ascii=False),
        "updated_at": datetime.now().isoformat(),
    })
    
    return result


@router.post("/projects/{pid}/refine")
async def refine_project(pid: str, req: RefineReq):
    proj = await db.get("projects", pid)
    if not proj:
        raise HTTPException(404)

    from litellm import acompletion
    from src.core.config import settings
    from src.engine.prompts.refine import REFINE_WITH_FEEDBACK_PROMPT

    test_results = proj.get("test_results", [])
    if isinstance(test_results, str):
        test_results = json.loads(test_results)
    last_output = json.dumps(test_results[-1] if test_results else {}, ensure_ascii=False)

    prompt = REFINE_WITH_FEEDBACK_PROMPT.format(
        code=proj.get("code", ""),
        test_results=last_output,
        feedback=req.feedback,
    )

    params = settings.get_llm_params()
    resp = await acompletion(
        **params,
        messages=[
            {"role": "system", "content": "你是Python爬虫专家。根据用户反馈修改代码。只输出代码。"},
            {"role": "user", "content": prompt},
        ],
    )

    new_code = resp.choices[0].message.content
    if "```python" in new_code:
        new_code = new_code.split("```python", 1)[1].split("```", 1)[0].strip()

    messages = proj.get("messages", [])
    if isinstance(messages, str):
        messages = json.loads(messages)
    messages.extend([
        {"role": "user", "content": req.feedback},
        {"role": "assistant", "content": f"已修改代码 v{proj.get('version', 1) + 1}"},
    ])

    await db.update("projects", pid, {
        "code": new_code,
        "version": proj.get("version", 1) + 1,
        "status": ProjectStatus.DRAFT,
        "messages": json.dumps(messages, ensure_ascii=False),
        "updated_at": datetime.now().isoformat(),
    })

    return await db.get("projects", pid)
