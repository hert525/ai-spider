"""Projects API - CRUD + AI generation."""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Depends, Body
from pydantic import BaseModel
from typing import Optional
from loguru import logger

from src.core.database import db
from src.core.models import Project, ProjectMode, ProjectStatus, _uid
from src.core.auth import get_current_user

router = APIRouter()


def _resolve_proxy_config(proj: dict) -> dict | None:
    """Get effective proxy config: project-level or global default."""
    pc = proj.get("proxy_config", {})
    if isinstance(pc, str):
        import json as _json
        try:
            pc = _json.loads(pc)
        except Exception:
            pc = {}
    if pc and pc.get("enabled"):
        return pc
    # Check if proxy_pool_id is set
    pool_id = pc.get("proxy_pool_id") if isinstance(pc, dict) else None
    if pool_id:
        # Will be resolved async in caller
        return {"proxy_pool_id": pool_id}
    # Fallback to global default
    from src.core.config import settings
    if settings.default_proxy:
        return {"enabled": True, "mode": "single", "proxy_url": settings.default_proxy}
    return None


async def _resolve_proxy_manager(proj: dict):
    """Get ProxyManager, supporting pool_id resolution."""
    from src.engine.proxy import ProxyManager
    pc = _resolve_proxy_config(proj)
    if not pc:
        return ProxyManager()
    pool_id = pc.get("proxy_pool_id")
    if pool_id:
        return await ProxyManager.from_pool_id(pool_id)
    return ProxyManager(pc)


class CreateProjectReq(BaseModel):
    description: str
    target_url: str = ""
    name: str = ""
    mode: str = "code_generator"  # "smart_scraper" or "code_generator"
    sink_config: dict = {}
    use_browser: bool = False
    proxy_config: dict = {}


class UpdateSinkReq(BaseModel):
    sink_config: dict


class UpdateProxyReq(BaseModel):
    proxy_pool_id: str = ""


class RefineReq(BaseModel):
    feedback: str


class TestReq(BaseModel):
    target_url: str = ""
    max_pages: int = 5


@router.get("/projects")
async def list_projects(user: dict = Depends(get_current_user)):
    """List projects for current user (admin sees all)."""
    if user.get("role") == "admin":
        rows = await db.list("projects")
    else:
        rows = await db.list("projects", where={"user_id": user["id"]})
    return rows


@router.post("/projects")
async def create_project(req: CreateProjectReq, user: dict = Depends(get_current_user)):
    import asyncio

    mode = ProjectMode(req.mode)
    project = Project(
        name=req.name or req.description[:30],
        description=req.description,
        target_url=req.target_url,
        mode=mode,
        status=ProjectStatus.GENERATING,
    )
    project_data = project.model_dump()
    project_data["user_id"] = user["id"]
    project_data["sink_config"] = req.sink_config
    project_data["proxy_config"] = req.proxy_config
    project_data["use_browser"] = 1 if req.use_browser else 0
    await db.insert("projects", project_data)

    # WS push: project created (immediate, status=generating)
    try:
        from src.api.ws import ws_manager
        api_key = user.get("api_key", "")
        msg = {
            "type": "project_created",
            "project": {"id": project.id, "name": project_data.get("name", ""), "status": "generating"},
        }
        if api_key:
            await ws_manager.send_to_user(api_key, msg)
        await ws_manager.broadcast_admin(msg)
    except Exception as e:
        logger.warning(f"WS push failed in create_project: {e}")

    # Run AI generation in background — return immediately
    async def _generate_bg():
        try:
            proxy_cfg = _resolve_proxy_config(project_data)
            if mode == ProjectMode.SMART_SCRAPER:
                from src.engine.graphs import SmartScraperGraph
                steps = ["抓取页面", "解析内容", "AI提取数据"]
                graph = SmartScraperGraph(use_browser=req.use_browser, proxy_config=proxy_cfg)
            else:
                from src.engine.graphs import CodeGeneratorGraph
                steps = ["抓取页面", "解析内容", "AI生成代码", "验证代码"]
                graph = CodeGeneratorGraph(use_browser=req.use_browser, proxy_config=proxy_cfg)

            # Execute nodes one by one with progress updates
            state = {"url": req.target_url, "description": req.description}
            total = len(graph.nodes)
            for i, node in enumerate(graph.nodes):
                step_label = steps[i] if i < len(steps) else node.node_name
                progress = {"step": i + 1, "total": total, "label": step_label}
                await db.update("projects", project.id, {
                    "progress": json.dumps(progress, ensure_ascii=False),
                })
                # WS push progress
                try:
                    from src.api.ws import ws_manager
                    await ws_manager.send_to_user(user.get("api_key", ""), {
                        "type": "project_progress",
                        "project_id": project.id,
                        "progress": progress,
                    })
                except Exception:
                    pass
                state = await node.execute(state)

            # Save final result
            if mode == ProjectMode.SMART_SCRAPER:
                extracted = state.get("extracted_data", [])
                await db.update("projects", project.id, {
                    "status": ProjectStatus.GENERATED,
                    "extracted_data": json.dumps(extracted, ensure_ascii=False),
                    "messages": json.dumps([
                        {"role": "user", "content": req.description},
                        {"role": "assistant", "content": f"已提取 {len(extracted) if isinstance(extracted, list) else 1} 条数据"},
                    ], ensure_ascii=False),
                    "progress": None,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                })
            else:
                code = state.get("generated_code", "")
                v_status = state.get("validation_status", "unknown")
                await db.update("projects", project.id, {
                    "status": ProjectStatus.GENERATED,
                    "code": code,
                    "messages": json.dumps([
                        {"role": "user", "content": req.description},
                        {"role": "assistant", "content": f"已生成爬虫代码（验证状态: {v_status}）"},
                    ], ensure_ascii=False),
                    "progress": None,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                })
        except Exception as e:
            logger.error(f"Generation failed for project {project.id}: {e}")
            await db.update("projects", project.id, {
                "status": ProjectStatus.FAILED,
                "messages": json.dumps([
                    {"role": "user", "content": req.description},
                    {"role": "assistant", "content": f"生成失败: {str(e)}"},
                ], ensure_ascii=False),
                "progress": None,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            })

        # WS push: generation complete
        try:
            from src.api.ws import ws_manager
            updated_proj = await db.get("projects", project.id)
            done_msg = {
                "type": "project_updated",
                "project": {"id": project.id, "name": updated_proj.get("name", ""), "status": updated_proj.get("status", "")},
            }
            api_key_bg = user.get("api_key", "")
            if api_key_bg:
                await ws_manager.send_to_user(api_key_bg, done_msg)
            await ws_manager.broadcast_admin(done_msg)
        except Exception as e:
            logger.warning(f"WS push failed in _generate_bg: {e}")

    asyncio.create_task(_generate_bg())

    # Return immediately with generating status
    return await db.get("projects", project.id)


@router.get("/projects/{pid}")
async def get_project(pid: str, user: dict = Depends(get_current_user)):
    proj = await db.get("projects", pid)
    if not proj:
        raise HTTPException(404, "Project not found")
    return proj


@router.delete("/projects/{pid}")
async def delete_project(pid: str, user: dict = Depends(get_current_user)):
    if not await db.delete("projects", pid):
        raise HTTPException(404)
    return {"ok": True}


@router.put("/projects/{pid}")
async def update_project(pid: str, body: dict = Body(...), user: dict = Depends(get_current_user)):
    """更新项目配置"""
    allowed_fields = ["name", "description", "target_url", "prompt", "mode", "cron_expr",
                      "proxy_pool_id", "sink_type", "sink_config", "stealth_level", "enable_screenshot",
                      "use_browser"]
    updates = {k: v for k, v in body.items() if k in allowed_fields}
    if not updates:
        raise HTTPException(400, "No valid fields to update")

    updates["updated_at"] = datetime.now(timezone.utc).isoformat()
    await db.update("projects", pid, updates)
    return {"ok": True}


@router.put("/projects/{pid}/code")
async def update_code(pid: str, req: dict, user: dict = Depends(get_current_user)):
    """Manually update project code."""
    proj = await db.get("projects", pid)
    if not proj:
        raise HTTPException(404)
    await db.update("projects", pid, {
        "code": req.get("code", ""),
        "version": proj.get("version", 1) + 1,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    })
    return await db.get("projects", pid)


@router.post("/projects/{pid}/test")
async def test_project(pid: str, req: TestReq, user: dict = Depends(get_current_user)):
    proj = await db.get("projects", pid)
    if not proj:
        raise HTTPException(404)
    
    url = req.target_url or proj.get("target_url", "")
    if not url:
        raise HTTPException(400, "No target URL")

    await db.update("projects", pid, {"status": ProjectStatus.TESTING})

    # Helper to push progress via WebSocket
    async def _push_progress(step: str, detail: str = "", status: str = "running"):
        try:
            from src.api.ws import ws_manager
            api_key = user.get("api_key", "")
            msg = {"type": "test_progress", "project_id": pid, "step": step, "detail": detail, "status": status}
            if api_key:
                await ws_manager.send_to_user(api_key, msg)
        except Exception:
            pass

    mode = proj.get("mode", "code_generator")

    if mode == "smart_scraper":
        await _push_progress("AI智能提取模式", "正在抓取页面并用AI提取数据...")
        from src.engine.graphs.smart_scraper import SmartScraperGraph
        proxy_cfg = _resolve_proxy_config(proj)
        graph = SmartScraperGraph(use_browser=bool(proj.get("use_browser")), proxy_config=proxy_cfg)
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
        proxy_cfg = _resolve_proxy_config(proj)
        code = proj.get("code", "")

        # Detect placeholder/default template code — regenerate with LLM
        _is_placeholder = (
            not code.strip()
            or "example.com" in code
            or (not re.search(r'async\s+def\s+crawl', code) and len(code) < 500)
        )
        if _is_placeholder and url:
            await _push_progress("检测到默认模板", "正在用AI为目标URL生成专用爬虫代码...")
            try:
                from src.engine.graphs.code_generator import CodeGeneratorGraph
                graph = CodeGeneratorGraph(max_retries=3)
                state = await graph.run(url=url, description=proj.get("description", ""))
                generated = state.get("generated_code", "")
                if generated and "crawl" in generated:
                    code = generated
                    # Save the generated code back to project
                    await db.update("projects", pid, {
                        "code": code,
                        "updated_at": datetime.now(timezone.utc).isoformat(),
                    })
                    await _push_progress("代码生成完成", f"已生成 {len(code)} 字符的专用爬虫代码", status="ok")
            except Exception as gen_e:
                logger.warning(f"Auto code generation failed: {gen_e}")
                await _push_progress("代码生成失败", str(gen_e)[:100], status="fail")

        # If browser mode enabled, pre-render HTML with Playwright and pass to sandbox
        pre_rendered_html = None
        logger.info(f"Browser mode check: use_browser={proj.get('use_browser')!r}, type={type(proj.get('use_browser'))}")
        if proj.get("use_browser"):
            await _push_progress("浏览器渲染", "正在启动 Playwright 加载页面...")
            try:
                from playwright.async_api import async_playwright
                async with async_playwright() as pw:
                    browser = await pw.chromium.launch(headless=True, args=[
                        "--no-sandbox", "--disable-dev-shm-usage",
                        "--disable-blink-features=AutomationControlled",
                    ])
                    context = await browser.new_context(
                        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                    )
                    # Inject cookies if configured
                    cookie_config = proj.get("cookie_config")
                    if cookie_config:
                        if isinstance(cookie_config, str):
                            import json as _json
                            try: cookie_config = _json.loads(cookie_config)
                            except: cookie_config = {}
                        cookies = cookie_config.get("cookies", [])
                        if cookies:
                            await context.add_cookies(cookies)
                    page = await context.new_page()
                    # Hide webdriver flag to bypass JS anti-bot checks
                    await page.add_init_script('Object.defineProperty(navigator, "webdriver", {get: () => false})')
                    await page.goto(url, wait_until="networkidle", timeout=45000)
                    # Wait for JS challenges + dynamic data to load
                    # Some sites need: round 1 = JS challenge, round 2 = page shell, round 3 = data
                    for _wait_round in range(6):
                        await page.wait_for_timeout(3000)
                        _check_html = await page.content()
                        _has_real_content = (
                            len(_check_html) > 5000
                            and "__jsl_clearance" not in _check_html[:2000]
                        )
                        if _has_real_content:
                            # Check if dynamic data has loaded (look for table data cells)
                            from parsel import Selector as _Sel
                            _sel = _Sel(text=_check_html)
                            _data_cells = len(_sel.css("table tr td"))
                            if _data_cells > 0:
                                logger.info(f"Browser: data loaded after {(_wait_round+1)*3}s ({_data_cells} cells)")
                                break
                            # No data yet but page is real - wait one more round
                            if _wait_round >= 3:
                                logger.info(f"Browser: page loaded but no table data after {(_wait_round+1)*3}s, proceeding")
                                break
                    # Check if page has JS-based pagination with an API backend
                    # Auto-detect by scanning network requests for pagination patterns
                    _pagination_done = False
                    _wants_pagination = (
                        (proj.get("description") and "翻页" in proj.get("description", ""))
                        or (proj.get("description") and "全部" in proj.get("description", ""))
                        or (proj.get("description") and "所有" in proj.get("description", ""))
                    )
                    # Also auto-detect: check if page has pagination controls
                    if not _wants_pagination:
                        try:
                            _has_pager = await page.evaluate("""
                                () => {
                                    // Check onclick-based pagination
                                    const onclickLinks = document.querySelectorAll('a[onclick*="gotoPage"], a[onclick*="nextPage"], a[onclick*="changePage"]');
                                    if (onclickLinks.length > 0) return true;
                                    // Check common pagination elements
                                    const paginationEls = document.querySelectorAll('.pagination a, .pager a, .page-link, [class*="pagination"]');
                                    if (paginationEls.length > 0) return true;
                                    // Check text-based: look for "下一页" in any <a>
                                    const allLinks = document.querySelectorAll('a');
                                    for (const a of allLinks) {
                                        const t = a.textContent || '';
                                        if (t.includes('下一页') || t.includes('Next') || t.includes('next')) return true;
                                    }
                                    return false;
                                }
                            """)
                            if _has_pager:
                                _wants_pagination = True
                                logger.info("Browser: auto-detected pagination controls on page")
                        except Exception:
                            pass

                    if _wants_pagination:
                        try:
                            _api_urls = await page.evaluate("""
                                () => {
                                    const entries = performance.getEntriesByType('resource');
                                    return entries
                                        .filter(e => e.name.includes('pageIndex') || e.name.includes('pageSize') || e.name.includes('page='))
                                        .map(e => e.name);
                                }
                            """)
                            if _api_urls:
                                _api_url = _api_urls[-1]  # Last API call is the data one
                                logger.info(f"Browser: detected pagination API: {_api_url}")
                                # Fetch first page with large pageSize to get totalCount
                                import re as _re
                                _base_api = _re.sub(r'pageSize=\d+', 'pageSize=500', _api_url)
                                _base_api = _re.sub(r'pageIndex=\d+', 'pageIndex=0', _base_api)

                                all_data = []
                                page_idx = 0
                                while True:
                                    _paged_api = _re.sub(r'pageIndex=\d+', f'pageIndex={page_idx}', _base_api)
                                    _resp_text = await page.evaluate("""
                                        (url) => {
                                            return new Promise((resolve, reject) => {
                                                var xhr = new XMLHttpRequest();
                                                xhr.open("GET", url, true);
                                                xhr.onload = () => resolve(xhr.responseText);
                                                xhr.onerror = () => reject("XHR error");
                                                xhr.timeout = 15000;
                                                xhr.ontimeout = () => reject("XHR timeout");
                                                xhr.send();
                                            });
                                        }
                                    """, _paged_api)
                                    import json as _json2
                                    _resp_data = _json2.loads(_resp_text)
                                    _items = _resp_data.get("data", [])
                                    if not _items:
                                        break
                                    all_data.extend(_items)
                                    _total = _resp_data.get("totalCount", 0)
                                    _page_count = _resp_data.get("pageCount", 1)
                                    logger.info(f"Browser pagination: page {page_idx+1}/{_page_count}, got {len(_items)} items, total so far: {len(all_data)}/{_total}")
                                    page_idx += 1
                                    if page_idx >= _page_count:
                                        break

                                if all_data:
                                    # Build an HTML table from JSON data
                                    _keys = list(all_data[0].keys())
                                    _html_parts = ['<html><body><table><tr>']
                                    _html_parts.extend(f'<th>{k}</th>' for k in _keys)
                                    _html_parts.append('</tr>')
                                    for item in all_data:
                                        _html_parts.append('<tr>')
                                        _html_parts.extend(f'<td>{item.get(k, "")}</td>' for k in _keys)
                                        _html_parts.append('</tr>')
                                    _html_parts.append('</table></body></html>')
                                    pre_rendered_html = ''.join(_html_parts)
                                    _pagination_done = True
                                    logger.info(f"Browser pagination complete: {len(all_data)} total items, HTML: {len(pre_rendered_html)} chars")
                        except Exception as _pag_e:
                            logger.warning(f"Pagination fetch failed, falling back to single page: {_pag_e}")

                    if not _pagination_done:
                        pre_rendered_html = await page.content()
                    # Count data cells for logging
                    from parsel import Selector as _PRSel
                    _pr_cells = len(_PRSel(text=pre_rendered_html).css("table tr td"))
                    logger.info(f"Browser pre-render done: {len(pre_rendered_html)} chars, {_pr_cells} table cells")
                    await browser.close()
                    await _push_progress("浏览器渲染完成", f"页面大小: {len(pre_rendered_html)//1024}KB", status="ok")
            except Exception as e:
                import traceback
                await _push_progress("浏览器渲染失败", str(e)[:100], status="fail")
                logger.error(f"Playwright pre-render failed: {e}\n{traceback.format_exc()}")

        await _push_progress("执行爬虫代码", "正在沙箱中运行代码...")
        result = await run_code_in_sandbox(code, url, proxy_config=proxy_cfg, html=pre_rendered_html)

        # Auto-fix: if execution failed, use LLM to fix and retry (up to 3 rounds)
        if result.get("error") and code.strip():
            await _push_progress("代码执行出错", result["error"][:100], status="fail")
            await _push_progress("启动自动修复", "AI正在分析错误并修复代码...")
            from src.core.llm import llm_completion
            fix_code = code
            for fix_round in range(5):
                error_msg = result["error"]
                await _push_progress(f"自动修复 第{fix_round+1}轮", "AI重新生成代码中...")
                logger.info(f"Auto-fix round {fix_round+1}/3 for project {pid}: {error_msg[:100]}")
                try:
                    fix_prompt = f"""以下Python爬虫代码执行出错，请修复。只返回修复后的完整Python代码，不要解释。

错误信息:
{error_msg[:500]}

原始代码:
```python
{fix_code}
```

目标URL: {url}

要求:
1. 必须定义 async def crawl(url, config) -> list[dict] 函数
2. 返回 list[dict]
3. 不要用 asyncio.run()，直接用 await
4. 只用 httpx, parsel, bs4, lxml, re, json, csv, math, datetime, collections 等白名单库
5. 如果需要代理，从 config.get("proxy") 获取
6. 沙箱限制: 禁止 import os/subprocess/sys/pathlib/socket/pickle/playwright 等系统模块
7. 可用的内置函数: len/range/enumerate/zip/map/filter/sorted/min/max/sum/abs/print/isinstance/type/hasattr/getattr/globals/locals 等常用函数
8. 不要使用 open()/exec()/eval()/compile() 等不安全函数
9. ⚠️ 必须优先检查 config.get("pre_rendered_html")！有则直接用 Selector 解析，不要发HTTP请求
10. 不要在沙箱里启动 playwright"""
                    resp = await llm_completion(
                        messages=[{"role": "user", "content": fix_prompt}],
                        temperature=0.2,
                        max_tokens=4000,
                    )
                    new_code = resp.choices[0].message.content.strip()
                    # Extract code from markdown block if present
                    if "```python" in new_code:
                        new_code = new_code.split("```python", 1)[1].split("```", 1)[0].strip()
                    elif "```" in new_code:
                        new_code = new_code.split("```", 1)[1].split("```", 1)[0].strip()
                    
                    await _push_progress(f"第{fix_round+1}轮修复", "重新执行修复后的代码...")
                    result = await run_code_in_sandbox(new_code, url, proxy_config=proxy_cfg)
                    fix_code = new_code
                    if not result.get("error"):
                        # Fix succeeded — save the fixed code
                        logger.info(f"Auto-fix succeeded on round {fix_round+1}")
                        await _push_progress(f"第{fix_round+1}轮修复成功", f"提取到 {len(result.get('output',[]))} 条数据", status="ok")
                        await db.update("projects", pid, {
                            "code": new_code,
                            "updated_at": datetime.now(timezone.utc).isoformat(),
                        })
                        result["auto_fixed"] = True
                        result["fix_rounds"] = fix_round + 1
                        break
                    else:
                        await _push_progress(f"第{fix_round+1}轮仍失败", result["error"][:80], status="fail")
                except Exception as fix_e:
                    logger.warning(f"Auto-fix round {fix_round+1} failed: {fix_e}")
                    break

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
        "updated_at": datetime.now(timezone.utc).isoformat(),
    })

    # WS push: test complete
    try:
        from src.api.ws import ws_manager
        api_key = user.get("api_key", "")
        test_msg = {
            "type": "test_complete",
            "project_id": pid,
            "status": "success" if not result.get("error") else "failed",
            "output_count": len(result.get("output", [])),
        }
        if api_key:
            await ws_manager.send_to_user(api_key, test_msg)
        await ws_manager.broadcast_admin(test_msg)
    except Exception as e:
        logger.warning(f"WS push failed in test_project: {e}")

    return result


@router.post("/projects/{pid}/refine")
async def refine_project(pid: str, req: RefineReq, user: dict = Depends(get_current_user)):
    proj = await db.get("projects", pid)
    if not proj:
        raise HTTPException(404)

    from src.core.llm import llm_completion
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

    resp = await llm_completion(
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
        "updated_at": datetime.now(timezone.utc).isoformat(),
    })

    return await db.get("projects", pid)


@router.put("/projects/{pid}/sink")
async def update_sink(pid: str, req: UpdateSinkReq, user: dict = Depends(get_current_user)):
    """Update sink configuration for a project."""
    proj = await db.get("projects", pid)
    if not proj:
        raise HTTPException(404, "Project not found")
    if user.get("role") != "admin" and proj.get("user_id") != user["id"]:
        raise HTTPException(403, "Not your project")

    await db.update("projects", pid, {
        "sink_config": req.sink_config,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    })
    return await db.get("projects", pid)


@router.put("/projects/{pid}/proxy")
async def update_proxy(pid: str, req: UpdateProxyReq, user: dict = Depends(get_current_user)):
    """Update proxy configuration for a project (by proxy_pool_id)."""
    proj = await db.get("projects", pid)
    if not proj:
        raise HTTPException(404, "Project not found")
    if user.get("role") != "admin" and proj.get("user_id") != user["id"]:
        raise HTTPException(403, "Not your project")

    # Validate user has permission to use this proxy pool
    if req.proxy_pool_id:
        pool = await db.get("proxy_pools", req.proxy_pool_id)
        if not pool:
            raise HTTPException(404, "Proxy pool not found")
        if not pool.get("is_public"):
            perms = await db.query(
                "SELECT id FROM proxy_permissions WHERE user_id = ? AND proxy_pool_id = ?",
                [user["id"], req.proxy_pool_id],
            )
            if not perms and user.get("role") != "admin":
                raise HTTPException(403, "No permission to use this proxy pool")

    proxy_config = {"proxy_pool_id": req.proxy_pool_id} if req.proxy_pool_id else {}
    await db.update("projects", pid, {
        "proxy_config": proxy_config,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    })
    return await db.get("projects", pid)


@router.post("/projects/{pid}/test-proxy")
async def test_proxy(pid: str, user: dict = Depends(get_current_user)):
    """Test proxy configuration by accessing httpbin.org/ip."""
    proj = await db.get("projects", pid)
    if not proj:
        raise HTTPException(404, "Project not found")

    pm = await _resolve_proxy_manager(proj)
    if not pm.enabled:
        return {"ok": False, "error": "No proxy configured", "ip": None}

    proxy_url = await pm.get_proxy_url()
    if not proxy_url:
        return {"ok": False, "error": "Could not get proxy URL", "ip": None}

    try:
        import httpx as _httpx
        async with _httpx.AsyncClient(proxy=proxy_url, timeout=15) as client:
            resp = await client.get("https://httpbin.org/ip")
            resp.raise_for_status()
            data = resp.json()
            return {"ok": True, "error": "", "ip": data.get("origin", ""), "proxy": proxy_url}
    except Exception as e:
        return {"ok": False, "error": str(e), "ip": None, "proxy": proxy_url}


@router.get("/proxies/available")
async def list_available_proxies(user: dict = Depends(get_current_user)):
    """List proxy pools available to the current user."""
    if user.get("role") == "admin":
        # Admin sees all active pools
        pools = await db.list("proxy_pools", where={"status": "active"})
    else:
        # Public pools + explicitly granted
        pools = await db.query(
            """SELECT DISTINCT pp.* FROM proxy_pools pp
               LEFT JOIN proxy_permissions perm ON pp.id = perm.proxy_pool_id AND perm.user_id = ?
               WHERE pp.status = 'active' AND (pp.is_public = 1 OR perm.user_id IS NOT NULL)
               ORDER BY pp.created_at DESC""",
            [user["id"]],
        )
    return pools
