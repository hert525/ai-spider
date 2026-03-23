"""Data API - export and preview."""
from __future__ import annotations

import json
import csv
import io
from collections import Counter
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends, Query
from fastapi.responses import StreamingResponse
from src.core.database import db
from src.core.auth import get_current_user

router = APIRouter()


def _build_where_clause(where: dict[str, str]) -> tuple[str, list[str]]:
    conditions = [f"{key} = ?" for key, value in where.items() if value]
    params = [value for value in where.values() if value]
    return (" WHERE " + " AND ".join(conditions)) if conditions else "", params


def _parse_record_data(raw: object) -> dict:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                return parsed
            return {"raw": parsed}
        except json.JSONDecodeError:
            return {"raw": raw}
    return {}


async def _load_preview_payload(project_id: str = "", task_id: str = "", limit: int = 20) -> dict:
    where = {}
    if project_id:
        where["project_id"] = project_id
    if task_id:
        where["task_id"] = task_id

    rows = await db.list("data_records", where=where, limit=limit, order="created_at DESC")
    if not rows:
        return {"columns": [], "rows": [], "total": 0, "showing": 0, "null_rates": {}}

    parsed_rows = []
    all_keys: dict[str, str] = {}
    for row in rows:
        data = _parse_record_data(row.get("data", "{}"))
        parsed_rows.append(data)
        for key, value in data.items():
            if key not in all_keys:
                all_keys[key] = type(value).__name__

    columns = [{"name": key, "type": value} for key, value in all_keys.items()]
    total_count = await db.count("data_records", where or None)
    null_rates = {}
    for col in all_keys:
        null_count = sum(1 for row in parsed_rows if not row.get(col))
        null_rates[col] = round(null_count / len(parsed_rows) * 100, 1) if parsed_rows else 0

    return {
        "columns": columns,
        "rows": parsed_rows,
        "total": total_count,
        "showing": len(parsed_rows),
        "null_rates": null_rates,
    }


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
    where_clause, params = _build_where_clause(where)
    sql += where_clause
    sql += f" ORDER BY created_at DESC LIMIT {page_size} OFFSET {offset}"

    rows = await db.query(sql, params)

    # Deserialize data field
    for row in rows:
        if isinstance(row.get("data"), str):
            try:
                row["data"] = json.loads(row["data"])
            except Exception:
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
    return await _load_preview_payload(project_id=project_id, task_id=task_id, limit=limit)


@router.get("/data/stats")
async def data_stats(project_id: str = "", task_id: str = "", user: dict = Depends(get_current_user)):
    """Overview stats for the data page."""
    where = {}
    if project_id:
        where["project_id"] = project_id
    if task_id:
        where["task_id"] = task_id

    total = await db.count("data_records", where or None)
    where_clause, params = _build_where_clause(where)

    projects_sql = "SELECT COUNT(DISTINCT project_id) as count FROM data_records"
    if where_clause:
        projects_sql += where_clause + " AND project_id != ''"
    else:
        projects_sql += " WHERE project_id != ''"
    projects_rows = await db.query(projects_sql, params)
    projects_count = int(projects_rows[0]["count"]) if projects_rows else 0

    today = datetime.now().strftime("%Y-%m-%d")
    today_sql = f"SELECT COUNT(*) as count FROM data_records{where_clause}"
    today_params = list(params)
    if where_clause:
        today_sql += " AND substr(created_at, 1, 10) = ?"
    else:
        today_sql += " WHERE substr(created_at, 1, 10) = ?"
    today_params.append(today)
    today_rows = await db.query(today_sql, today_params)
    today_count = int(today_rows[0]["count"]) if today_rows else 0

    preview = await _load_preview_payload(project_id=project_id, task_id=task_id, limit=100)
    null_rates = list(preview.get("null_rates", {}).values())
    quality_score = round(max(0, 100 - (sum(null_rates) / len(null_rates))), 1) if null_rates else 0

    return {
        "total": total,
        "projects_count": projects_count,
        "today_count": today_count,
        "quality_score": quality_score,
        "null_rates": preview.get("null_rates", {}),
    }


@router.get("/data/stats/timeline")
async def data_timeline(project_id: str = "", task_id: str = "", user: dict = Depends(get_current_user)):
    """Collection timeline aggregated by day and hour."""
    where = {}
    if project_id:
        where["project_id"] = project_id
    if task_id:
        where["task_id"] = task_id

    sql = "SELECT created_at FROM data_records"
    where_clause, params = _build_where_clause(where)
    sql += where_clause + " ORDER BY created_at ASC"
    rows = await db.query(sql, params)

    daily_counter: Counter[str] = Counter()
    hourly_counter: Counter[str] = Counter()
    for row in rows:
        created_at = row.get("created_at") or ""
        if len(created_at) >= 10:
            daily_counter[created_at[:10]] += 1
        if len(created_at) >= 13:
            hourly_counter[created_at[:13] + ":00"] += 1

    daily = [{"bucket": bucket, "count": count} for bucket, count in sorted(daily_counter.items())]
    hourly = [{"bucket": bucket, "count": count} for bucket, count in sorted(hourly_counter.items())]
    recommended_granularity = "hour" if len(daily) <= 1 else "day"

    return {
        "daily": daily,
        "hourly": hourly,
        "recommended_granularity": recommended_granularity,
        "total_points": len(daily if recommended_granularity == "day" else hourly),
    }


@router.get("/scrape/markdown")
async def scrape_to_markdown(url: str, user: dict = Depends(get_current_user)):
    """Fetch a URL and return clean Markdown. LLM-ready output."""
    if not url.startswith("http"):
        raise HTTPException(400, "URL must start with http:// or https://")
    try:
        from src.engine.nodes import FetchNode, ParseNode
        fetch = FetchNode()
        parse = ParseNode(output_format="markdown")
        state = {"url": url, "description": "", "output_format": "markdown"}
        state = await fetch.execute(state)
        state = await parse.execute(state)
        markdown = state.get("markdown", "")
        clean_text = state.get("clean_text", "")
        links_count = len(state.get("links", []))
        return {
            "url": url,
            "markdown": markdown,
            "text_length": len(clean_text),
            "markdown_length": len(markdown),
            "links_count": links_count,
        }
    except Exception as e:
        raise HTTPException(500, f"Scrape failed: {str(e)}")


@router.get("/scrape/markdown/raw")
async def scrape_to_markdown_raw(url: str, user: dict = Depends(get_current_user)):
    """Fetch a URL and return raw Markdown as plain text (for piping to LLMs)."""
    if not url.startswith("http"):
        raise HTTPException(400, "URL must start with http:// or https://")
    try:
        from src.engine.nodes import FetchNode, ParseNode
        fetch = FetchNode()
        parse = ParseNode(output_format="markdown")
        state = {"url": url, "description": "", "output_format": "markdown"}
        state = await fetch.execute(state)
        state = await parse.execute(state)
        markdown = state.get("markdown", "")
        return StreamingResponse(
            iter([markdown]),
            media_type="text/markdown",
            headers={"Content-Disposition": f"inline; filename=page.md"},
        )
    except Exception as e:
        raise HTTPException(500, f"Scrape failed: {str(e)}")
