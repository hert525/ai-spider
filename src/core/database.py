"""
数据库层 — 支持 PostgreSQL (asyncpg) 和 SQLite (aiosqlite) 双后端。

默认使用 PostgreSQL，通过 DATABASE_URL 环境变量配置:
  DATABASE_URL=postgresql://ai_spider:password@localhost:5432/ai_spider

如果 DATABASE_URL 以 sqlite:// 开头或未设置，回退到 SQLite。
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from loguru import logger
from src.core.config import settings

# 检测数据库类型
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
USE_PG = DATABASE_URL.startswith("postgresql://") or DATABASE_URL.startswith("postgres://")


# ---- PostgreSQL Schema ----
_PG_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    email TEXT UNIQUE NOT NULL,
    username TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    api_key TEXT UNIQUE,
    role TEXT DEFAULT 'user',
    quota_projects INTEGER DEFAULT 20,
    quota_tasks INTEGER DEFAULT 100,
    status TEXT DEFAULT 'active',
    daily_task_limit INTEGER DEFAULT 100,
    storage_limit_mb INTEGER DEFAULT 500,
    max_concurrent_tasks INTEGER DEFAULT 5,
    created_at TEXT,
    updated_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_api_key ON users(api_key);

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
    sink_config TEXT DEFAULT '{}',
    user_id TEXT DEFAULT '',
    worker_pool_id TEXT DEFAULT '',
    use_browser INTEGER DEFAULT 0,
    proxy_config TEXT DEFAULT '{}',
    stealth_level TEXT DEFAULT 'off',
    enable_screenshot INTEGER DEFAULT 0,
    created_at TEXT,
    updated_at TEXT
);

CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY,
    project_id TEXT,
    name TEXT,
    user_id TEXT DEFAULT '',
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
    last_run_at TEXT DEFAULT '',
    next_run_at TEXT DEFAULT '',
    created_at TEXT,
    updated_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_tasks_project ON tasks(project_id);
CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);

CREATE TABLE IF NOT EXISTS task_runs (
    id TEXT PRIMARY KEY,
    task_id TEXT,
    worker_id TEXT,
    user_id TEXT DEFAULT '',
    status TEXT DEFAULT 'running',
    items_count INTEGER DEFAULT 0,
    pages_crawled INTEGER DEFAULT 0,
    error TEXT DEFAULT '',
    retry_count INTEGER DEFAULT 0,
    max_retries INTEGER DEFAULT 3,
    next_retry_at TEXT DEFAULT '',
    started_at TEXT,
    finished_at TEXT,
    duration_ms INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS workers (
    id TEXT PRIMARY KEY,
    hostname TEXT DEFAULT '',
    ip TEXT DEFAULT '',
    pool_id TEXT DEFAULT '',
    status TEXT DEFAULT 'offline',
    max_concurrency INTEGER DEFAULT 3,
    active_jobs INTEGER DEFAULT 0,
    total_completed INTEGER DEFAULT 0,
    total_failed INTEGER DEFAULT 0,
    cpu_percent REAL DEFAULT 0,
    memory_mb REAL DEFAULT 0,
    memory_total_mb REAL DEFAULT 0,
    disk_percent REAL DEFAULT 0,
    python_version TEXT DEFAULT '',
    os_info TEXT DEFAULT '',
    tags TEXT DEFAULT '[]',
    current_tasks TEXT DEFAULT '[]',
    last_heartbeat TEXT DEFAULT '',
    registered_at TEXT DEFAULT '',
    updated_at TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS data_records (
    id TEXT PRIMARY KEY,
    project_id TEXT,
    task_id TEXT,
    task_run_id TEXT,
    data TEXT DEFAULT '{}',
    data_hash TEXT DEFAULT '',
    created_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_data_project ON data_records(project_id);
CREATE INDEX IF NOT EXISTS idx_data_task ON data_records(task_id);
CREATE INDEX IF NOT EXISTS idx_data_hash ON data_records(data_hash);

CREATE TABLE IF NOT EXISTS worker_pools (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT DEFAULT '',
    region TEXT DEFAULT '',
    country TEXT DEFAULT '',
    tags TEXT DEFAULT '[]',
    max_concurrency INTEGER DEFAULT 50,
    status TEXT DEFAULT 'active',
    created_at TEXT DEFAULT '',
    updated_at TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS proxy_pools (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT DEFAULT '',
    proxy_type TEXT DEFAULT 'http',
    mode TEXT DEFAULT 'single',
    proxies TEXT DEFAULT '[]',
    rotating_api TEXT DEFAULT '',
    test_url TEXT DEFAULT 'https://httpbin.org/ip',
    is_public INTEGER DEFAULT 0,
    status TEXT DEFAULT 'active',
    created_at TEXT DEFAULT '',
    updated_at TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS system_config (
    key TEXT PRIMARY KEY,
    value TEXT DEFAULT '',
    category TEXT DEFAULT 'general',
    label TEXT DEFAULT '',
    description TEXT DEFAULT '',
    field_type TEXT DEFAULT 'text',
    options TEXT DEFAULT '[]',
    sort_order INTEGER DEFAULT 0,
    updated_at TEXT DEFAULT '',
    updated_by TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS seed_templates (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT DEFAULT '',
    category TEXT DEFAULT 'general',
    icon TEXT DEFAULT '🕷️',
    target_url TEXT DEFAULT '',
    mode TEXT DEFAULT 'smart_scraper',
    code TEXT DEFAULT '',
    extract_schema TEXT DEFAULT '{}',
    use_browser INTEGER DEFAULT 0,
    proxy_required INTEGER DEFAULT 0,
    tags TEXT DEFAULT '[]',
    difficulty TEXT DEFAULT 'easy',
    author TEXT DEFAULT 'system',
    download_count INTEGER DEFAULT 0,
    rating REAL DEFAULT 0,
    rating_count INTEGER DEFAULT 0,
    status TEXT DEFAULT 'active',
    original_code TEXT DEFAULT '',
    source_url TEXT DEFAULT '',
    original_format TEXT DEFAULT '',
    created_at TEXT DEFAULT '',
    updated_at TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS browser_sessions (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    domain TEXT NOT NULL,
    name TEXT DEFAULT '',
    cookies TEXT DEFAULT '{}',
    local_storage TEXT DEFAULT '{}',
    user_agent TEXT DEFAULT '',
    status TEXT DEFAULT 'active',
    expires_at TEXT DEFAULT '',
    created_at TEXT DEFAULT '',
    updated_at TEXT DEFAULT '',
    UNIQUE(user_id, domain)
);

CREATE TABLE IF NOT EXISTS notification_configs (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL UNIQUE,
    webhook_url TEXT DEFAULT '',
    email TEXT DEFAULT '',
    telegram_bot_token TEXT DEFAULT '',
    telegram_chat_id TEXT DEFAULT '',
    events TEXT DEFAULT '["task_failed"]',
    enabled INTEGER DEFAULT 1,
    created_at TEXT DEFAULT '',
    updated_at TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS notification_logs (
    id TEXT PRIMARY KEY,
    user_id TEXT DEFAULT '',
    event TEXT NOT NULL,
    channel TEXT NOT NULL,
    data TEXT DEFAULT '{}',
    status TEXT DEFAULT 'sent',
    error TEXT DEFAULT '',
    created_at TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS proxy_permissions (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    proxy_pool_id TEXT NOT NULL,
    granted_by TEXT DEFAULT '',
    created_at TEXT DEFAULT '',
    UNIQUE(user_id, proxy_pool_id)
);

CREATE TABLE IF NOT EXISTS project_versions (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    version INTEGER NOT NULL,
    code TEXT DEFAULT '',
    extraction_rules TEXT DEFAULT '',
    config_json TEXT DEFAULT '{}',
    change_summary TEXT DEFAULT '',
    created_at TEXT DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_project_versions_project ON project_versions(project_id);
CREATE INDEX IF NOT EXISTS idx_project_versions_pv ON project_versions(project_id, version);
"""

# JSON字段需要序列化/反序列化
_JSON_FIELDS = {
    "projects": ["extracted_data", "messages", "test_results", "sink_config", "proxy_config"],
    "tasks": ["target_urls"],
    "workers": ["tags", "current_tasks"],
    "worker_pools": ["tags"],
    "data_records": ["data"],
    "task_runs": [],
    "proxy_pools": ["proxies"],
    "seed_templates": ["tags", "extract_schema"],
}

# 合法表名白名单
_ALLOWED_TABLES = {
    "users", "projects", "tasks", "task_runs", "workers", "worker_pools",
    "data_records", "proxy_pools", "system_config", "seed_templates",
    "browser_sessions", "notification_configs", "notification_logs",
    "proxy_permissions", "project_versions",
}


def _check_table(table: str) -> str:
    """校验表名，防止SQL注入"""
    if table not in _ALLOWED_TABLES:
        raise ValueError(f"非法表名: {table}")
    return table


def _serialize(table: str, data: dict) -> dict:
    """将list/dict字段序列化为JSON字符串"""
    result = dict(data)
    for field in _JSON_FIELDS.get(table, []):
        if field in result and not isinstance(result[field], str):
            result[field] = json.dumps(result[field], ensure_ascii=False)
    return result


def _deserialize(table: str, row: dict) -> dict:
    """将JSON字符串反序列化回Python对象"""
    result = dict(row)
    for field in _JSON_FIELDS.get(table, []):
        if field in result and isinstance(result[field], str):
            try:
                result[field] = json.loads(result[field])
            except (json.JSONDecodeError, TypeError):
                pass
    return result


# ════════════════════════════════════════
#  PostgreSQL 后端 (asyncpg)
# ════════════════════════════════════════

if USE_PG:
    import asyncpg

    _pool: asyncpg.Pool | None = None

    async def _get_pool() -> asyncpg.Pool:
        global _pool
        if _pool is None:
            _pool = await asyncpg.create_pool(
                DATABASE_URL,
                min_size=2,
                max_size=10,
                command_timeout=30,
            )
        return _pool

    # Migrations: add columns that may not exist in older databases
    _MIGRATIONS = [
        "ALTER TABLE workers ADD COLUMN IF NOT EXISTS pool_id TEXT DEFAULT ''",
        "ALTER TABLE projects ADD COLUMN IF NOT EXISTS worker_pool_id TEXT DEFAULT ''",
        "ALTER TABLE notification_configs ADD COLUMN IF NOT EXISTS telegram_bot_token TEXT DEFAULT ''",
    ]

    async def init_db():
        """初始化PostgreSQL: 建表 + 连接池"""
        pool = await _get_pool()
        # 逐条执行建表（asyncpg不支持executemany for DDL）
        for stmt in _PG_SCHEMA.split(";"):
            stmt = stmt.strip()
            if stmt:
                try:
                    await pool.execute(stmt)
                except Exception as e:
                    # 忽略已存在的表/索引
                    if "already exists" not in str(e):
                        logger.warning(f"Schema执行警告: {e}")
        # Run migrations for existing databases
        for mig in _MIGRATIONS:
            try:
                await pool.execute(mig)
            except Exception as e:
                if "already exists" not in str(e) and "duplicate column" not in str(e).lower():
                    logger.warning(f"Migration warning: {e}")
        logger.info(f"Database initialized (PostgreSQL: {DATABASE_URL.split('@')[-1]})")

    async def close_db():
        """关闭连接池"""
        global _pool
        if _pool:
            await _pool.close()
            _pool = None

    class DB:
        """异步数据库操作 — PostgreSQL后端"""

        async def insert(self, table: str, data: dict):
            _check_table(table)
            data = _serialize(table, data)
            cols = ", ".join(data.keys())
            placeholders = ", ".join(f"${i+1}" for i in range(len(data)))
            pool = await _get_pool()
            await pool.execute(
                f"INSERT INTO {table} ({cols}) VALUES ({placeholders})",
                *data.values(),
            )

        async def get(self, table: str, id: str) -> dict | None:
            _check_table(table)
            pool = await _get_pool()
            row = await pool.fetchrow(f"SELECT * FROM {table} WHERE id = $1", id)
            if row:
                return _deserialize(table, dict(row))
            return None

        async def list(self, table: str, where: dict | None = None, order: str = "created_at DESC", limit: int = 200) -> list[dict]:
            _check_table(table)
            pool = await _get_pool()
            sql = f"SELECT * FROM {table}"
            params = []
            idx = 1
            if where:
                conditions = []
                for k, v in where.items():
                    if v is not None:
                        conditions.append(f"{k} = ${idx}")
                        params.append(v)
                        idx += 1
                if conditions:
                    sql += " WHERE " + " AND ".join(conditions)
            sql += f" ORDER BY {order} LIMIT {limit}"
            rows = await pool.fetch(sql, *params)
            return [_deserialize(table, dict(r)) for r in rows]

        async def update(self, table: str, id: str, data: dict):
            _check_table(table)
            data = _serialize(table, data)
            idx = 1
            sets = []
            params = []
            for k, v in data.items():
                sets.append(f"{k} = ${idx}")
                params.append(v)
                idx += 1
            params.append(id)
            pool = await _get_pool()
            await pool.execute(
                f"UPDATE {table} SET {', '.join(sets)} WHERE id = ${idx}",
                *params,
            )

        async def delete(self, table: str, id: str) -> bool:
            _check_table(table)
            pool = await _get_pool()
            result = await pool.execute(f"DELETE FROM {table} WHERE id = $1", id)
            return result.split()[-1] != "0"

        async def count(self, table: str, where: dict | None = None) -> int:
            _check_table(table)
            pool = await _get_pool()
            sql = f"SELECT COUNT(*) FROM {table}"
            params = []
            idx = 1
            if where:
                conditions = []
                for k, v in where.items():
                    if v is not None:
                        conditions.append(f"{k} = ${idx}")
                        params.append(v)
                        idx += 1
                if conditions:
                    sql += " WHERE " + " AND ".join(conditions)
            row = await pool.fetchval(sql, *params)
            return row or 0

        async def insert_many(self, table: str, records: list[dict]):
            if not records:
                return
            _check_table(table)
            pool = await _get_pool()
            async with pool.acquire() as conn:
                async with conn.transaction():
                    for data in records:
                        data = _serialize(table, data)
                        cols = ", ".join(data.keys())
                        placeholders = ", ".join(f"${i+1}" for i in range(len(data)))
                        await conn.execute(
                            f"INSERT INTO {table} ({cols}) VALUES ({placeholders})",
                            *data.values(),
                        )

        async def execute(self, sql: str, params: list | None = None):
            """执行原始SQL（支持?占位符，自动转$N）"""
            sql, params = sql_param(sql, params)
            pool = await _get_pool()
            await pool.execute(sql, *params)

        async def query(self, sql: str, params: list | None = None) -> list[dict]:
            """执行原始SQL查询（支持?占位符，自动转$N）"""
            sql, params = sql_param(sql, params)
            pool = await _get_pool()
            rows = await pool.fetch(sql, *params)
            return [dict(r) for r in rows]


# ════════════════════════════════════════
#  SQLite 后端 (aiosqlite) — 回退方案
# ════════════════════════════════════════

else:
    import aiosqlite

    DB_PATH = settings.db_path

    # SQLite schema（和PG共用同一份定义）
    _SQLITE_SCHEMA = _PG_SCHEMA.replace("$1", "?").replace("$2", "?")

    async def get_db() -> aiosqlite.Connection:
        Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
        conn = await aiosqlite.connect(DB_PATH)
        conn.row_factory = aiosqlite.Row
        return conn

    # SQLite migrations (no IF NOT EXISTS for ALTER TABLE)
    _SQLITE_MIGRATIONS = [
        ("workers", "pool_id", "ALTER TABLE workers ADD COLUMN pool_id TEXT DEFAULT ''"),
        ("projects", "worker_pool_id", "ALTER TABLE projects ADD COLUMN worker_pool_id TEXT DEFAULT ''"),
        ("notification_configs", "telegram_bot_token", "ALTER TABLE notification_configs ADD COLUMN telegram_bot_token TEXT DEFAULT ''"),
    ]

    async def init_db():
        conn = await get_db()
        try:
            await conn.executescript(_SQLITE_SCHEMA)
            await conn.commit()
            # Run migrations for existing databases
            for table, col, sql in _SQLITE_MIGRATIONS:
                try:
                    cursor = await conn.execute(f"PRAGMA table_info({table})")
                    columns = [row[1] for row in await cursor.fetchall()]
                    if col not in columns:
                        await conn.execute(sql)
                        await conn.commit()
                except Exception as e:
                    logger.warning(f"SQLite migration warning: {e}")
        finally:
            await conn.close()
        logger.info(f"Database initialized (SQLite: {DB_PATH})")

    async def close_db():
        pass  # SQLite无连接池

    class DB:
        """异步数据库操作 — SQLite后端"""

        async def insert(self, table: str, data: dict):
            _check_table(table)
            data = _serialize(table, data)
            cols = ", ".join(data.keys())
            placeholders = ", ".join(["?"] * len(data))
            conn = await get_db()
            try:
                await conn.execute(f"INSERT INTO {table} ({cols}) VALUES ({placeholders})", list(data.values()))
                await conn.commit()
            finally:
                await conn.close()

        async def get(self, table: str, id: str) -> dict | None:
            _check_table(table)
            conn = await get_db()
            try:
                cursor = await conn.execute(f"SELECT * FROM {table} WHERE id = ?", [id])
                row = await cursor.fetchone()
                if row:
                    return _deserialize(table, dict(row))
                return None
            finally:
                await conn.close()

        async def list(self, table: str, where: dict | None = None, order: str = "created_at DESC", limit: int = 200) -> list[dict]:
            _check_table(table)
            conn = await get_db()
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
                cursor = await conn.execute(sql, params)
                rows = await cursor.fetchall()
                return [_deserialize(table, dict(r)) for r in rows]
            finally:
                await conn.close()

        async def update(self, table: str, id: str, data: dict):
            _check_table(table)
            data = _serialize(table, data)
            sets = ", ".join(f"{k} = ?" for k in data.keys())
            conn = await get_db()
            try:
                await conn.execute(f"UPDATE {table} SET {sets} WHERE id = ?", list(data.values()) + [id])
                await conn.commit()
            finally:
                await conn.close()

        async def delete(self, table: str, id: str) -> bool:
            _check_table(table)
            conn = await get_db()
            try:
                cursor = await conn.execute(f"DELETE FROM {table} WHERE id = ?", [id])
                await conn.commit()
                return cursor.rowcount > 0
            finally:
                await conn.close()

        async def count(self, table: str, where: dict | None = None) -> int:
            _check_table(table)
            conn = await get_db()
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
                cursor = await conn.execute(sql, params)
                row = await cursor.fetchone()
                return row[0]
            finally:
                await conn.close()

        async def insert_many(self, table: str, records: list[dict]):
            if not records:
                return
            _check_table(table)
            conn = await get_db()
            try:
                for data in records:
                    data = _serialize(table, data)
                    cols = ", ".join(data.keys())
                    placeholders = ", ".join(["?"] * len(data))
                    await conn.execute(f"INSERT INTO {table} ({cols}) VALUES ({placeholders})", list(data.values()))
                await conn.commit()
            finally:
                await conn.close()

        async def execute(self, sql: str, params: list | None = None):
            conn = await get_db()
            try:
                await conn.execute(sql, params or [])
                await conn.commit()
            finally:
                await conn.close()

        async def query(self, sql: str, params: list | None = None) -> list[dict]:
            conn = await get_db()
            try:
                cursor = await conn.execute(sql, params or [])
                rows = await cursor.fetchall()
                return [dict(r) for r in rows]
            finally:
                await conn.close()


db = DB()


def sql_param(sql: str, params: list | None = None) -> tuple[str, list | tuple]:
    """
    统一SQL参数占位符：代码统一写 ? 占位符，
    PostgreSQL模式下自动转换为 $1, $2, ...
    """
    if not USE_PG or not params:
        return sql, params or []

    # 将 ? 替换为 $1, $2, ...
    result = []
    idx = 1
    for char in sql:
        if char == "?":
            result.append(f"${idx}")
            idx += 1
        else:
            result.append(char)
    return "".join(result), params
