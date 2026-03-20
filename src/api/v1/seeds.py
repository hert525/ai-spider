"""Seed templates API — template marketplace."""
from __future__ import annotations

import re
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel
from typing import Optional
from loguru import logger

from src.core.database import db
from src.core.models import _uid
from src.core.auth import get_current_user

router = APIRouter()


# ── Models ──

class SeedRate(BaseModel):
    rating: float  # 1-5


class SeedCreate(BaseModel):
    name: str
    description: str = ""
    category: str = "general"
    icon: str = "🕷️"
    target_url: str = ""
    mode: str = "smart_scraper"
    code: str = ""
    extract_schema: dict = {}
    use_browser: int = 0
    proxy_required: int = 0
    tags: list = []
    difficulty: str = "easy"
    status: str = "active"


class SeedUseRequest(BaseModel):
    params: dict = {}  # for {keyword} etc placeholder fill


# ── User endpoints ──

@router.get("/seeds")
async def list_seeds(
    category: Optional[str] = None,
    difficulty: Optional[str] = None,
    keyword: Optional[str] = None,
    tag: Optional[str] = None,
    limit: int = 100,
):
    """List seed templates with filtering."""
    conditions = []
    params = []

    conditions.append("status = ?")
    params.append("active")

    if category:
        conditions.append("category = ?")
        params.append(category)
    if difficulty:
        conditions.append("difficulty = ?")
        params.append(difficulty)
    if keyword:
        conditions.append("(name LIKE ? OR description LIKE ?)")
        params.extend([f"%{keyword}%", f"%{keyword}%"])
    if tag:
        conditions.append("tags LIKE ?")
        params.append(f"%{tag}%")

    where = " WHERE " + " AND ".join(conditions) if conditions else ""
    sql = f"SELECT * FROM seed_templates{where} ORDER BY download_count DESC LIMIT {limit}"
    rows = await db.query(sql, params)

    # Deserialize JSON fields
    import json
    for r in rows:
        for f in ("tags", "extract_schema"):
            if isinstance(r.get(f), str):
                try:
                    r[f] = json.loads(r[f])
                except Exception:
                    pass
    return rows


@router.get("/seeds/categories")
async def seed_categories():
    """Get all categories with counts."""
    rows = await db.query(
        "SELECT category, COUNT(*) as count FROM seed_templates WHERE status='active' GROUP BY category ORDER BY count DESC"
    )
    from src.core.seeds import CATEGORY_LABELS
    result = []
    for r in rows:
        cat = r["category"]
        result.append({
            "key": cat,
            "label": CATEGORY_LABELS.get(cat, cat),
            "count": r["count"],
        })
    return result


@router.get("/seeds/{sid}")
async def get_seed(sid: str):
    """Get seed template detail."""
    seed = await db.get("seed_templates", sid)
    if not seed:
        raise HTTPException(404, "模板不存在")
    return seed


@router.post("/seeds/{sid}/use")
async def use_seed(sid: str, body: SeedUseRequest = SeedUseRequest(), user=Depends(get_current_user)):
    """Use a seed template to create a new project."""
    seed = await db.get("seed_templates", sid)
    if not seed:
        raise HTTPException(404, "模板不存在")

    now = datetime.now(timezone.utc).isoformat()

    # Fill placeholders in target_url
    target_url = seed.get("target_url", "")
    if body.params:
        for k, v in body.params.items():
            target_url = target_url.replace("{" + k + "}", v)

    project = {
        "id": _uid(),
        "user_id": user["id"],
        "name": f"{seed['name']} (from template)",
        "description": seed.get("description", ""),
        "target_url": target_url,
        "mode": seed.get("mode", "smart_scraper"),
        "code": seed.get("code", ""),
        "use_browser": seed.get("use_browser", 0),
        "status": "generated" if seed.get("code") else "draft",
        "extracted_data": "[]",
        "version": 1,
        "messages": "[]",
        "test_results": "[]",
        "sink_config": "{}",
        "proxy_config": "{}",
        "created_at": now,
        "updated_at": now,
    }
    await db.insert("projects", project)

    # Update download count
    await db.execute(
        "UPDATE seed_templates SET download_count = download_count + 1 WHERE id = ?",
        [sid],
    )

    return project


@router.post("/seeds/{sid}/rate")
async def rate_seed(sid: str, body: SeedRate, user=Depends(get_current_user)):
    """Rate a seed template."""
    if not 1 <= body.rating <= 5:
        raise HTTPException(400, "评分需在1-5之间")
    seed = await db.get("seed_templates", sid)
    if not seed:
        raise HTTPException(404, "模板不存在")

    old_rating = seed.get("rating", 0) or 0
    old_count = seed.get("rating_count", 0) or 0
    new_count = old_count + 1
    new_rating = (old_rating * old_count + body.rating) / new_count

    await db.execute(
        "UPDATE seed_templates SET rating = ?, rating_count = ? WHERE id = ?",
        [round(new_rating, 2), new_count, sid],
    )
    return {"rating": round(new_rating, 2), "rating_count": new_count}


# ── Admin endpoints ──

@router.post("/admin/seeds")
async def create_seed(body: SeedCreate, user=Depends(get_current_user)):
    """Create a seed template (admin only)."""
    if user.get("role") != "admin":
        raise HTTPException(403, "仅管理员可操作")
    now = datetime.now(timezone.utc).isoformat()
    data = {
        "id": _uid(),
        **body.model_dump(),
        "author": user.get("username", "admin"),
        "download_count": 0,
        "rating": 0,
        "rating_count": 0,
        "created_at": now,
        "updated_at": now,
    }
    await db.insert("seed_templates", data)
    return data


@router.put("/admin/seeds/{sid}")
async def update_seed(sid: str, body: SeedCreate, user=Depends(get_current_user)):
    """Update a seed template (admin only)."""
    if user.get("role") != "admin":
        raise HTTPException(403, "仅管理员可操作")
    seed = await db.get("seed_templates", sid)
    if not seed:
        raise HTTPException(404, "模板不存在")
    now = datetime.now(timezone.utc).isoformat()
    data = {**body.model_dump(), "updated_at": now}
    await db.update("seed_templates", sid, data)
    return {**seed, **data}


@router.delete("/admin/seeds/{sid}")
async def delete_seed(sid: str, user=Depends(get_current_user)):
    """Delete a seed template (admin only)."""
    if user.get("role") != "admin":
        raise HTTPException(403, "仅管理员可操作")
    ok = await db.delete("seed_templates", sid)
    if not ok:
        raise HTTPException(404, "模板不存在")
    return {"ok": True}


@router.post("/admin/seeds/import")
async def import_seeds(body: list[dict], user=Depends(get_current_user)):
    """Batch import seed templates (admin only)."""
    if user.get("role") != "admin":
        raise HTTPException(403, "仅管理员可操作")
    now = datetime.now(timezone.utc).isoformat()
    count = 0
    for item in body:
        item.setdefault("id", _uid())
        item.setdefault("author", user.get("username", "admin"))
        item.setdefault("created_at", now)
        item.setdefault("updated_at", now)
        item.setdefault("download_count", 0)
        item.setdefault("rating", 0)
        item.setdefault("rating_count", 0)
        item.setdefault("status", "active")
        await db.insert("seed_templates", item)
        count += 1
    return {"imported": count}


# ── GitHub Import ──

class GithubImportReq(BaseModel):
    url: str
    name: str = ""
    description: str = ""
    category: str = "community"


@router.post("/admin/seeds/import-github")
async def import_from_github(req: GithubImportReq, user=Depends(get_current_user)):
    """Import a spider from GitHub URL.

    Accepts GitHub repo URL, file URL, or raw URL.
    """
    if user.get("role") != "admin":
        raise HTTPException(403, "仅管理员可操作")

    from src.engine.adapters import CodeAdapter

    url = req.url
    code = await _fetch_github_code(url)
    fmt = CodeAdapter.detect_format(code)
    wrapped_code = CodeAdapter.wrap(code, fmt)
    metadata = _extract_metadata(code, url)

    now = datetime.now(timezone.utc).isoformat()
    template = {
        "id": _uid(),
        "name": req.name or metadata.get("name", "GitHub Import"),
        "description": req.description or metadata.get("description", f"Imported from {url}"),
        "category": req.category or "community",
        "icon": "🐙",
        "target_url": metadata.get("target_url", ""),
        "mode": "code_generator",
        "code": wrapped_code,
        "original_code": code,
        "source_url": url,
        "original_format": fmt,
        "tags": [fmt, "github", "community"],
        "difficulty": "medium",
        "author": metadata.get("author", "community"),
        "status": "draft",
        "download_count": 0,
        "rating": 0,
        "rating_count": 0,
        "created_at": now,
        "updated_at": now,
    }
    await db.insert("seed_templates", template)

    return {
        "template": template,
        "detected_format": fmt,
        "message": f"Imported as {fmt} format, wrapped to standard interface. Status: draft (review needed)",
    }


@router.post("/admin/seeds/sync-community")
async def sync_community_seeds(user=Depends(get_current_user)):
    """Pull all community seed sources from GitHub."""
    if user.get("role") != "admin":
        raise HTTPException(403, "仅管理员可操作")

    from src.engine.adapters import CodeAdapter
    from src.core.community_seeds import COMMUNITY_SOURCES

    now = datetime.now(timezone.utc).isoformat()
    results = []

    for src in COMMUNITY_SOURCES:
        try:
            code = await _fetch_github_code(src["url"])
            fmt = CodeAdapter.detect_format(code)
            wrapped = CodeAdapter.wrap(code, fmt)
            template = {
                "id": _uid(),
                "name": src["name"],
                "description": f"社区爬虫: {src['name']} (from {src['url']})",
                "category": src.get("category", "community"),
                "icon": src.get("icon", "🐙"),
                "target_url": "",
                "mode": "code_generator",
                "code": wrapped,
                "original_code": code,
                "source_url": src["url"],
                "original_format": fmt,
                "tags": [fmt, "github", "community"],
                "difficulty": "medium",
                "author": "community",
                "status": "draft",
                "download_count": 0,
                "rating": 0,
                "rating_count": 0,
                "created_at": now,
                "updated_at": now,
            }
            await db.insert("seed_templates", template)
            results.append({"name": src["name"], "status": "ok", "format": fmt})
        except Exception as e:
            results.append({"name": src["name"], "status": "error", "error": str(e)})

    return {"results": results, "total": len(results)}


@router.post("/admin/seeds/detect-format")
async def detect_format(body: dict, user=Depends(get_current_user)):
    """Detect code format without importing."""
    if user.get("role") != "admin":
        raise HTTPException(403, "仅管理员可操作")

    from src.engine.adapters import CodeAdapter

    code = body.get("code", "")
    fmt = CodeAdapter.detect_format(code)
    wrapped = CodeAdapter.wrap(code, fmt)
    return {"format": fmt, "wrapped_code": wrapped}


async def _fetch_github_code(url: str) -> str:
    """Fetch code from various GitHub URL formats."""
    import httpx

    raw_url = url
    if 'github.com' in url and '/blob/' in url:
        raw_url = url.replace('github.com', 'raw.githubusercontent.com').replace('/blob/', '/')
    elif 'github.com' in url and '/tree/' not in url and '/blob/' not in url:
        # Repo URL — try to find main spider file
        for branch in ['master', 'main']:
            repo_raw = url.replace('github.com', 'raw.githubusercontent.com') + f'/{branch}/'
            for filename in ['spider.py', 'main.py', 'crawl.py', 'scraper.py', 'app.py', 'run.py']:
                try:
                    async with httpx.AsyncClient(timeout=10) as client:
                        resp = await client.get(repo_raw + filename)
                        if resp.status_code == 200:
                            return resp.text
                except Exception:
                    continue
        raise HTTPException(400, "Could not find spider code in repo. Please provide a direct file URL.")

    async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
        resp = await client.get(raw_url)
        resp.raise_for_status()
        return resp.text


def _extract_metadata(code: str, url: str) -> dict:
    """Extract metadata from code comments and URL."""
    metadata: dict = {}

    # Try to extract name from first docstring or comment
    m = re.search(r'"""(.+?)"""', code)
    if m:
        metadata["description"] = m.group(1).strip()

    m = re.search(r"#\s*(.+)", code)
    if m:
        metadata.setdefault("name", m.group(1).strip()[:50])

    # Extract author from GitHub URL
    parts = url.rstrip("/").split("/")
    if len(parts) >= 4 and "github.com" in url:
        metadata["author"] = parts[-2]

    # Try to find target URL in code
    url_match = re.search(r"""['"]https?://[^'"]+['"]""", code)
    if url_match:
        metadata["target_url"] = url_match.group(0).strip("'\"")

    return metadata
