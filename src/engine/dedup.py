"""Data deduplication and cleaning."""
from __future__ import annotations

import hashlib
import json

from loguru import logger


class DataDeduplicator:
    """去重和数据清洗"""

    @staticmethod
    def compute_hash(item: dict, keys: list[str] | None = None) -> str:
        """计算数据项哈希（用于去重）"""
        if keys:
            data = {k: item.get(k, "") for k in keys}
        else:
            data = {k: v for k, v in item.items() if not k.startswith("_")}
        raw = json.dumps(data, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(raw.encode()).hexdigest()

    @staticmethod
    def deduplicate(items: list[dict], keys: list[str] | None = None) -> list[dict]:
        """去除重复数据"""
        seen: set[str] = set()
        result = []
        for item in items:
            h = DataDeduplicator.compute_hash(item, keys)
            if h not in seen:
                seen.add(h)
                result.append(item)
        removed = len(items) - len(result)
        if removed:
            logger.info(f"Dedup: removed {removed} duplicates from {len(items)} items")
        return result

    @staticmethod
    def clean(items: list[dict]) -> list[dict]:
        """清洗数据：去除空值、trim字符串、标准化"""
        cleaned = []
        for item in items:
            clean_item = {}
            for k, v in item.items():
                if v is None or v == "":
                    continue
                if isinstance(v, str):
                    v = v.strip()
                    if not v:
                        continue
                clean_item[k] = v
            if clean_item:
                cleaned.append(clean_item)
        return cleaned

    @staticmethod
    async def deduplicate_against_db(
        items: list[dict], project_id: str, keys: list[str] | None = None
    ) -> list[dict]:
        """与数据库已有数据去重"""
        from src.core.database import db

        rows = await db.query(
            "SELECT data_hash FROM data_records WHERE project_id = ? AND data_hash != ''",
            [project_id],
        )
        existing_hashes = {row["data_hash"] for row in rows if row.get("data_hash")}

        new_items = []
        for item in items:
            h = DataDeduplicator.compute_hash(item, keys)
            if h not in existing_hashes:
                item["_data_hash"] = h
                new_items.append(item)

        logger.info(f"DB dedup: {len(items)} → {len(new_items)} new items")
        return new_items


deduplicator = DataDeduplicator()
