"""Data API - export and preview."""
from __future__ import annotations

import json
import csv
import io
from fastapi import APIRouter, HTTPException, Depends, Query
from fastapi.responses import StreamingResponse
from src.core.database import db
from src.core.auth import get_current_user

router = APIRouter()


@router.get("/data")
async def list_data(project_id: str = "", task_id: str = "", page: int = 1, page_size: int = 20):
    """List data records with pagination."""
    where = {}
    if project_id:
        where["project_id"] = project_id
    if task_id:
        where["task_id"] = task_id

    offset = (page - 1) * page_size
    total = await db.count("data_records", where=where or None)
    
    # Manual pagination via query
    sql = "SELECT * FROM data_records"
    params = []
    if where:
        conditions = [f"{k} = ?" for k in where]
        sql += " WHERE " + " AND ".join(conditions)
        params = list(where.values())
    sql += f" ORDER BY created_at DESC LIMIT {page_size} OFFSET {offset}"
    
    rows = await db.query(sql, params)
    # Deserialize data field
    for row in rows:
        if isinstance(row.get("data"), str):
            try:
                row["data"] = json.loads(row["data"])
            except:
                pass

    return {
        "items": rows,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size,
    }


@router.get("/data/export/json")
async def export_json(project_id: str = "", task_id: str = ""):
    """Export data as JSON."""
    where = {}
    if project_id:
        where["project_id"] = project_id
    if task_id:
        where["task_id"] = task_id

    rows = await db.list("data_records", where=where or None, limit=10000)
    data = []
    for row in rows:
        d = row.get("data", {})
        if isinstance(d, str):
            try:
                d = json.loads(d)
            except:
                pass
        data.append(d)

    content = json.dumps(data, ensure_ascii=False, indent=2)
    return StreamingResponse(
        io.BytesIO(content.encode()),
        media_type="application/json",
        headers={"Content-Disposition": "attachment; filename=data.json"},
    )


@router.get("/data/export/csv")
async def export_csv(project_id: str = "", task_id: str = ""):
    """Export data as CSV."""
    where = {}
    if project_id:
        where["project_id"] = project_id
    if task_id:
        where["task_id"] = task_id

    rows = await db.list("data_records", where=where or None, limit=10000)
    data = []
    for row in rows:
        d = row.get("data", {})
        if isinstance(d, str):
            try:
                d = json.loads(d)
            except:
                pass
        if isinstance(d, dict):
            data.append(d)

    if not data:
        return StreamingResponse(
            io.BytesIO(b""),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=data.csv"},
        )

    output = io.StringIO()
    fieldnames = list(data[0].keys())
    writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction='ignore')
    writer.writeheader()
    writer.writerows(data)

    return StreamingResponse(
        io.BytesIO(output.getvalue().encode("utf-8-sig")),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=data.csv"},
    )


@router.get("/data/export")
async def export_data(
    project_id: str = "",
    format: str = Query("json", alias="format"),
    user: dict = Depends(get_current_user),
):
    """Export data as JSON or CSV (unified endpoint)."""
    if format == "csv":
        return await export_csv(project_id=project_id)
    return await export_json(project_id=project_id)


@router.get("/data/preview")
async def preview_data(project_id: str = "", task_id: str = "", limit: int = 20,
                       user: dict = Depends(get_current_user)):
    """Preview data as table with column info (for frontend table rendering)."""
    where = {}
    if project_id:
        where["project_id"] = project_id
    if task_id:
        where["task_id"] = task_id
    rows = await db.list("data_records", where=where, limit=limit, order="created_at DESC")

    if not rows:
        return {"columns": [], "rows": [], "total": 0}

    # Parse data field (stored as JSON string)
    import json as _json
    parsed_rows = []
    all_keys: dict[str, str] = {}  # key -> type
    for r in rows:
        data = r.get("data", "{}")
        if isinstance(data, str):
            try:
                data = _json.loads(data)
            except _json.JSONDecodeError:
                data = {"raw": data}
        if isinstance(data, dict):
            parsed_rows.append(data)
            for k, v in data.items():
                if k not in all_keys:
                    all_keys[k] = type(v).__name__

    # Build columns
    columns = [{"name": k, "type": v} for k, v in all_keys.items()]

    # Quality stats
    total_count = await db.count("data_records", where)
    null_rates = {}
    for col in all_keys:
        null_count = sum(1 for r in parsed_rows if not r.get(col))
        null_rates[col] = round(null_count / len(parsed_rows) * 100, 1) if parsed_rows else 0

    return {
        "columns": columns,
        "rows": parsed_rows,
        "total": total_count,
        "showing": len(parsed_rows),
        "null_rates": null_rates,
    }
