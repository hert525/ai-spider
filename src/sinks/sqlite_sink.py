"""SQLite sink - writes to data_records table (default behavior)."""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from src.sinks.base import BaseSink


class SQLiteSink(BaseSink):
    """Write records to SQLite data_records table via the existing db helper."""

    async def write(self, records: list[dict], metadata: dict) -> int:
        from src.core.database import db

        project_id = metadata.get("project_id", "")
        task_id = metadata.get("task_id", "")
        now = datetime.now(timezone.utc).isoformat()

        rows = []
        for rec in records:
            rows.append({
                "id": uuid.uuid4().hex[:16],
                "project_id": project_id,
                "task_id": task_id,
                "data": json.dumps(rec, ensure_ascii=False),
                "created_at": now,
            })

        for row in rows:
            await db.insert("data_records", row)

        return len(rows)

    async def close(self):
        pass
