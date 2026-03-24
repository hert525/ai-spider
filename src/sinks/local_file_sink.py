"""Local file sink - writes to JSONL, CSV, or JSON files."""
from __future__ import annotations

import csv
import io
import json
import os
from datetime import datetime, timezone

from src.sinks.base import BaseSink


class LocalFileSink(BaseSink):
    """Write records to local files in jsonl/csv/json format."""

    def __init__(self, config: dict):
        self.output_dir = config.get("output_dir", "data/output")
        self.format = config.get("format", "jsonl")
        self.filename_template = config.get("filename_template", "{project_id}_{timestamp}.{format}")

    def _resolve_path(self, metadata: dict) -> str:
        project_id = metadata.get("project_id", "default")
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        base_dir = self.output_dir.format(project_id=project_id)
        filename = self.filename_template.format(
            project_id=project_id,
            timestamp=ts,
            format=self.format,
        )
        os.makedirs(base_dir, exist_ok=True)
        return os.path.join(base_dir, filename)

    async def write(self, records: list[dict], metadata: dict) -> int:
        if not records:
            return 0

        path = self._resolve_path(metadata)
        fmt = self.format

        if fmt == "jsonl":
            with open(path, "a", encoding="utf-8") as f:
                for rec in records:
                    f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        elif fmt == "csv":
            file_exists = os.path.exists(path) and os.path.getsize(path) > 0
            headers = list(records[0].keys())
            with open(path, "a", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=headers, extrasaction="ignore")
                if not file_exists:
                    writer.writeheader()
                writer.writerows(records)
        elif fmt == "json":
            existing: list = []
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    try:
                        existing = json.load(f)
                    except json.JSONDecodeError:
                        existing = []
            existing.extend(records)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(existing, f, ensure_ascii=False, indent=2)
        elif fmt == "parquet":
            import pyarrow as pa
            import pyarrow.parquet as pq
            table = pa.Table.from_pylist(records)
            if os.path.exists(path):
                old_table = pq.read_table(path)
                table = pa.concat_tables([old_table, table], promote_options="default")
            pq.write_table(table, path, compression="snappy")
        else:
            raise ValueError(f"Unsupported format: {fmt}")

        return len(records)

    async def close(self):
        pass
