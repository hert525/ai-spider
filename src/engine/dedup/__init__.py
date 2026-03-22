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
]
