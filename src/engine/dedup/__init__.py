"""
去重模块 - 从 wukong/dedup/ 移植并适配 async/await 架构。

支持4种去重策略：
- MemoryDeduper: 内存布隆过滤器（轻量级，适合中小规模）
- RedisDeduper: Redis去重（分布式，支持TTL过期）
- BloomFilterDeduper: 大规模布隆过滤器（内存友好）
- RotationDeduper: 滚动分区布隆过滤器（持久化，超大规模）
"""
from src.engine.dedup.base import BaseDeduper
from src.engine.dedup.memory_deduper import MemoryDeduper
from src.engine.dedup.redis_deduper import RedisDeduper
from src.engine.dedup.bloom_deduper import BloomFilterDeduper
from src.engine.dedup.rotation_deduper import RotationDeduper
from src.engine.dedup.factory import create_deduper, DedupStrategy

__all__ = [
    "BaseDeduper",
    "MemoryDeduper",
    "RedisDeduper",
    "BloomFilterDeduper",
    "RotationDeduper",
    "create_deduper",
    "DedupStrategy",
    "DataDeduplicator",
    "deduplicator",
]


# ---- 兼容旧接口: DataDeduplicator (原 dedup.py 的功能) ----
import hashlib
import json
from loguru import logger


class DataDeduplicator:
    """去重和数据清洗（兼容旧接口，供 workers.py 等调用）"""

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
