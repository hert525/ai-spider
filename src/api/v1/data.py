"""Data API - export and preview."""
import json
import csv
import io
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from src.core.database import db

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
