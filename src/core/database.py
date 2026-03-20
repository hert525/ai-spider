"""SQLite database with aiosqlite."""
from __future__ import annotations
import json
import aiosqlite
from pathlib import Path
from loguru import logger
from src.core.config import settings

DB_PATH = settings.db_path

_SCHEMA = """
CREATE TABLE IF NOT EXISTS projects (
    id TEXT PRIMARY KEY,
    name TEXT,
    description TEXT,
    target_url TEXT,
    mode TEXT DEFAULT 'code_generator',
    status TEXT DEFAULT 'draft',
    code TEXT DEFAULT '',
    extracted_data TEXT DEFAULT '[]',
    version INTEGER DEFAULT 1,
    messages TEXT DEFAULT '[]',
    test_results TEXT DEFAULT '[]',
    created_at TEXT,
    updated_at TEXT
);

CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY,
    project_id TEXT,
    name TEXT,
    task_type TEXT DEFAULT 'one_time',
    status TEXT DEFAULT 'queued',
    target_urls TEXT DEFAULT '[]',
    cron_expr TEXT DEFAULT '',
    priority INTEGER DEFAULT 5,
    max_pages INTEGER DEFAULT 100,
    max_items INTEGER DEFAULT 10000,
    timeout_seconds INTEGER DEFAULT 300,
    concurrency INTEGER DEFAULT 3,
    retry_count INTEGER DEFAULT 0,
    max_retries INTEGER DEFAULT 3,
    worker_id TEXT,
    created_at TEXT,
    updated_at TEXT
);

CREATE TABLE IF NOT EXISTS task_runs (
    id TEXT PRIMARY KEY,
    task_id TEXT,
    worker_id TEXT,
    status TEXT DEFAULT 'running',
    items_count INTEGER DEFAULT 0,
    pages_crawled INTEGER DEFAULT 0,
    error TEXT DEFAULT '',
    started_at TEXT,
    finished_at TEXT,
    duration_ms INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS workers (
    id TEXT PRIMARY KEY,
    hostname TEXT,
    ip TEXT,
    status TEXT DEFAULT 'online',
    max_concurrency INTEGER DEFAULT 3,
    active_jobs INTEGER DEFAULT 0,
    total_completed INTEGER DEFAULT 0,
    total_failed INTEGER DEFAULT 0,
    cpu_percent REAL DEFAULT 0,
    memory_mb REAL DEFAULT 0,
    tags TEXT DEFAULT '[]',
    last_heartbeat TEXT,
    registered_at TEXT
);

CREATE TABLE IF NOT EXISTS data_records (
    id TEXT PRIMARY KEY,
    project_id TEXT,
    task_id TEXT,
    task_run_id TEXT,
    data TEXT DEFAULT '{}',
    created_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_tasks_project ON tasks(project_id);
CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_data_project ON data_records(project_id);
CREATE INDEX IF NOT EXISTS idx_data_task ON data_records(task_id);
"""

# JSON fields that need serialization
_JSON_FIELDS = {
    "projects": ["extracted_data", "messages", "test_results"],
    "tasks": ["target_urls"],
    "workers": ["tags"],
    "data_records": ["data"],
    "task_runs": [],
}


async def get_db() -> aiosqlite.Connection:
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    db = await aiosqlite.connect(DB_PATH)
    db.row_factory = aiosqlite.Row
    await db.executescript(_SCHEMA)
    return db


async def init_db():
    db = await get_db()
    await db.close()
    logger.info(f"Database initialized at {DB_PATH}")


def _serialize(table: str, data: dict) -> dict:
    """Convert lists/dicts to JSON strings for storage."""
    result = dict(data)
    for field in _JSON_FIELDS.get(table, []):
        if field in result and not isinstance(result[field], str):
            result[field] = json.dumps(result[field], ensure_ascii=False)
    return result


def _deserialize(table: str, row: dict) -> dict:
    """Convert JSON strings back to Python objects."""
    result = dict(row)
    for field in _JSON_FIELDS.get(table, []):
        if field in result and isinstance(result[field], str):
            try:
                result[field] = json.loads(result[field])
            except (json.JSONDecodeError, TypeError):
                pass
    return result


class DB:
    """Async database helper."""

    async def insert(self, table: str, data: dict):
        data = _serialize(table, data)
        cols = ", ".join(data.keys())
        placeholders = ", ".join(["?"] * len(data))
        db = await get_db()
        try:
            await db.execute(f"INSERT INTO {table} ({cols}) VALUES ({placeholders})", list(data.values()))
            await db.commit()
        finally:
            await db.close()

    async def get(self, table: str, id: str) -> dict | None:
        db = await get_db()
        try:
            cursor = await db.execute(f"SELECT * FROM {table} WHERE id = ?", [id])
            row = await cursor.fetchone()
            if row:
                return _deserialize(table, dict(row))
            return None
        finally:
            await db.close()

    async def list(self, table: str, where: dict | None = None, order: str = "created_at DESC", limit: int = 200) -> list[dict]:
        db = await get_db()
        try:
            sql = f"SELECT * FROM {table}"
            params = []
            if where:
                conditions = []
                for k, v in where.items():
                    if v is not None:
                        conditions.append(f"{k} = ?")
                        params.append(v)
                if conditions:
                    sql += " WHERE " + " AND ".join(conditions)
            sql += f" ORDER BY {order} LIMIT {limit}"
            cursor = await db.execute(sql, params)
            rows = await cursor.fetchall()
            return [_deserialize(table, dict(r)) for r in rows]
        finally:
            await db.close()

    async def update(self, table: str, id: str, data: dict):
        data = _serialize(table, data)
        sets = ", ".join(f"{k} = ?" for k in data.keys())
        db = await get_db()
        try:
            await db.execute(f"UPDATE {table} SET {sets} WHERE id = ?", list(data.values()) + [id])
            await db.commit()
        finally:
            await db.close()

    async def delete(self, table: str, id: str) -> bool:
        db = await get_db()
        try:
            cursor = await db.execute(f"DELETE FROM {table} WHERE id = ?", [id])
            await db.commit()
            return cursor.rowcount > 0
        finally:
            await db.close()

    async def count(self, table: str, where: dict | None = None) -> int:
        db = await get_db()
        try:
            sql = f"SELECT COUNT(*) FROM {table}"
            params = []
            if where:
                conditions = []
                for k, v in where.items():
                    if v is not None:
                        conditions.append(f"{k} = ?")
                        params.append(v)
                if conditions:
                    sql += " WHERE " + " AND ".join(conditions)
            cursor = await db.execute(sql, params)
            row = await cursor.fetchone()
            return row[0]
        finally:
            await db.close()

    async def insert_many(self, table: str, records: list[dict]):
        if not records:
            return
        db = await get_db()
        try:
            for data in records:
                data = _serialize(table, data)
                cols = ", ".join(data.keys())
                placeholders = ", ".join(["?"] * len(data))
                await db.execute(f"INSERT INTO {table} ({cols}) VALUES ({placeholders})", list(data.values()))
            await db.commit()
        finally:
            await db.close()

    async def query(self, sql: str, params: list | None = None) -> list[dict]:
        db = await get_db()
        try:
            cursor = await db.execute(sql, params or [])
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]
        finally:
            await db.close()


db = DB()
