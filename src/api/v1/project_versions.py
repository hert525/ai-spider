"""Project Versions API — list, detail, rollback."""
from __future__ import annotations

import json
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Depends
from loguru import logger

from src.core.database import db
from src.core.auth import get_current_user
from src.core.models import _uid

router = APIRouter(tags=["project-versions"])


async def save_project_version(
    project_id: str,
    code: str = "",
    extraction_rules: str = "",
    config_json: dict | None = None,
    change_summary: str = "",
) -> int:
    """Save a new version snapshot for a project. Returns new version number."""
    # Get current max version
    rows = await db.query(
        "SELECT MAX(version) as max_v FROM project_versions WHERE project_id = ?",
        [project_id],
    )
    max_v = rows[0]["max_v"] if rows and rows[0]["max_v"] is not None else 0
    new_version = max_v + 1

    await db.insert("project_versions", {
        "id": _uid(),
        "project_id": project_id,
        "version": new_version,
        "code": code,
        "extraction_rules": extraction_rules,
        "config_json": json.dumps(config_json or {}, ensure_ascii=False),
        "change_summary": change_summary,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    logger.info(f"Saved version {new_version} for project {project_id}: {change_summary}")
    return new_version


@router.get("/projects/{pid}/versions")
async def list_versions(pid: str, limit: int = 50, user: dict = Depends(get_current_user)):
    """List all versions for a project."""
    proj = await db.get("projects", pid)
    if not proj:
        raise HTTPException(404, "Project not found")

    rows = await db.query(
        "SELECT id, project_id, version, change_summary, created_at, "
        "LENGTH(code) as code_length, LENGTH(extraction_rules) as rules_length "
        "FROM project_versions WHERE project_id = ? ORDER BY version DESC LIMIT ?",
        [pid, limit],
    )
    return rows


@router.get("/projects/{pid}/versions/{version}")
async def get_version(pid: str, version: int, user: dict = Depends(get_current_user)):
    """Get a specific version with full code."""
    rows = await db.query(
        "SELECT * FROM project_versions WHERE project_id = ? AND version = ?",
        [pid, version],
    )
    if not rows:
        raise HTTPException(404, f"Version {version} not found")
    row = rows[0]
    if isinstance(row.get("config_json"), str):
        try:
            row["config_json"] = json.loads(row["config_json"])
        except Exception:
            pass
    return row


@router.post("/projects/{pid}/versions/{version}/rollback")
async def rollback_version(pid: str, version: int, user: dict = Depends(get_current_user)):
    """Rollback project to a specific version."""
    proj = await db.get("projects", pid)
    if not proj:
        raise HTTPException(404, "Project not found")

    rows = await db.query(
        "SELECT * FROM project_versions WHERE project_id = ? AND version = ?",
        [pid, version],
    )
    if not rows:
        raise HTTPException(404, f"Version {version} not found")

    target = rows[0]

    # Save current state as a new version before rollback
    current_code = proj.get("code", "")
    current_rules = proj.get("extraction_rules", "") or ""
    await save_project_version(
        project_id=pid,
        code=current_code,
        extraction_rules=current_rules,
        change_summary=f"Auto-save before rollback to v{version}",
    )

    # Apply rollback
    update_data = {
        "code": target.get("code", ""),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    if target.get("extraction_rules"):
        update_data["extraction_rules"] = target["extraction_rules"]

    await db.update("projects", pid, update_data)
    logger.info(f"Project {pid} rolled back to version {version}")

    return {
        "ok": True,
        "rolled_back_to": version,
        "message": f"已回滚到版本 {version}",
    }
