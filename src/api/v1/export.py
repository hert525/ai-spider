"""Data export API — CSV, JSON, Excel."""
from __future__ import annotations

import csv
import io
import json
from datetime import datetime

from fastapi import APIRouter, HTTPException, Depends, Query
from fastapi.responses import StreamingResponse, JSONResponse

from src.core.database import db
from src.core.auth import get_current_user
from src.core.models import _uid

router = APIRouter(prefix="/export", tags=["export"])


async def _get_task_data(task_id: str, user: dict, limit: int = 0) -> tuple[list[dict], str]:
    """Fetch scraped data for a task. Returns (rows, project_name)."""
    task = await db.get("tasks", task_id)
    if not task:
        raise HTTPException(404, "Task not found")
    if user.get("role") != "admin" and task.get("user_id") != user.get("id"):
        raise HTTPException(403, "Access denied")

    project = await db.get("projects", task.get("project_id", ""))
    project_name = (project or {}).get("name", "export") if project else "export"

    sql = "SELECT * FROM data_records WHERE task_id = ? ORDER BY created_at DESC"
    params = [task_id]
    if limit > 0:
        sql += f" LIMIT {limit}"
    rows = await db.query(sql, params)

    # Parse JSON data field
    result = []
    for r in rows:
        d = dict(r)
        if isinstance(d.get("data"), str):
            try:
                d["data"] = json.loads(d["data"])
            except (json.JSONDecodeError, TypeError):
                pass
        result.append(d)
    return result, project_name


def _flatten(data: dict, prefix: str = "") -> dict:
    """Flatten nested dict for CSV export."""
    out = {}
    for k, v in data.items():
        key = f"{prefix}{k}" if not prefix else f"{prefix}.{k}"
        if isinstance(v, dict):
            out.update(_flatten(v, key))
        elif isinstance(v, list):
            out[key] = json.dumps(v, ensure_ascii=False)
        else:
            out[key] = v
    return out


def _rows_to_flat(rows: list[dict]) -> list[dict]:
    """Convert data_records rows to flat dicts for export."""
    flat = []
    for r in rows:
        d = r.get("data", {})
        if isinstance(d, dict):
            item = _flatten(d)
        else:
            item = {"data": str(d)}
        item["_id"] = r.get("id", "")
        item["_task_id"] = r.get("task_id", "")
        item["_created_at"] = r.get("created_at", "")
        flat.append(item)
    return flat


@router.get("/{task_id}/preview")
async def export_preview(task_id: str, user: dict = Depends(get_current_user)):
    """Preview first 10 records."""
    rows, _ = await _get_task_data(task_id, user, limit=10)
    flat = _rows_to_flat(rows)
    return {"total_preview": len(flat), "data": flat}


@router.get("/{task_id}")
async def export_task(
    task_id: str,
    format: str = Query("json", pattern="^(csv|json|excel)$"),
    user: dict = Depends(get_current_user),
):
    """Export task data as CSV, JSON, or Excel."""
    rows, project_name = await _get_task_data(task_id, user)
    flat = _rows_to_flat(rows)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_name = f"{project_name}_{task_id}_{ts}"

    if format == "json":
        return JSONResponse(
            content=flat,
            headers={"Content-Disposition": f'attachment; filename="{base_name}.json"'},
        )

    if format == "csv":
        if not flat:
            return StreamingResponse(io.BytesIO(b""), media_type="text/csv")
        all_keys = list(dict.fromkeys(k for row in flat for k in row.keys()))
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=all_keys, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(flat)
        buf.seek(0)
        return StreamingResponse(
            iter([buf.getvalue().encode("utf-8-sig")]),
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{base_name}.csv"'},
        )

    if format == "excel":
        from openpyxl import Workbook
        wb = Workbook()
        ws = wb.active
        ws.title = "Data"
        if flat:
            all_keys = list(dict.fromkeys(k for row in flat for k in row.keys()))
            ws.append(all_keys)
            for row in flat:
                ws.append([str(row.get(k, "")) for k in all_keys])
        buf = io.BytesIO()
        wb.save(buf)
        buf.seek(0)
        return StreamingResponse(
            buf,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f'attachment; filename="{base_name}.xlsx"'},
        )


@router.get("/project/{project_id}")
async def export_project(
    project_id: str,
    format: str = Query("json", pattern="^(csv|json|excel)$"),
    limit: int = Query(10000, le=50000),
    user: dict = Depends(get_current_user),
):
    """Export all data for a project."""
    project = await db.get("projects", project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    if user.get("role") != "admin" and project.get("user_id") != user.get("id"):
        raise HTTPException(403, "Access denied")

    project_name = project.get("name", "export")
    sql = "SELECT * FROM data_records WHERE project_id = ? ORDER BY created_at DESC LIMIT ?"
    rows = await db.query(sql, [project_id, limit])

    result = []
    for r in rows:
        d = dict(r)
        if isinstance(d.get("data"), str):
            try:
                d["data"] = json.loads(d["data"])
            except (json.JSONDecodeError, TypeError):
                pass
        result.append(d)

    flat = _rows_to_flat(result)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_name = f"{project_name}_{project_id}_{ts}"

    if format == "json":
        return JSONResponse(
            content=flat,
            headers={"Content-Disposition": f'attachment; filename="{base_name}.json"'},
        )

    if format == "csv":
        if not flat:
            return StreamingResponse(io.BytesIO(b""), media_type="text/csv")
        all_keys = list(dict.fromkeys(k for row in flat for k in row.keys()))
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=all_keys, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(flat)
        buf.seek(0)
        return StreamingResponse(
            iter([buf.getvalue().encode("utf-8-sig")]),
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{base_name}.csv"'},
        )

    if format == "excel":
        from openpyxl import Workbook
        wb = Workbook()
        ws = wb.active
        ws.title = "Data"
        if flat:
            all_keys = list(dict.fromkeys(k for row in flat for k in row.keys()))
            ws.append(all_keys)
            for row in flat:
                ws.append([str(row.get(k, "")) for k in all_keys])
        buf = io.BytesIO()
        wb.save(buf)
        buf.seek(0)
        return StreamingResponse(
            buf,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f'attachment; filename="{base_name}.xlsx"'},
        )
