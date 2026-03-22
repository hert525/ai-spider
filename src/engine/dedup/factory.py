"""去重器工厂 - 根据配置创建对应的去重策略"""
from __future__ import annotations

from enum import Enum
from typing import Any

from loguru import logger

from src.engine.dedup.base import BaseDeduper


class DedupStrategy(str, Enum):
    """去重策略枚举"""
    MEMORY = "memory"          # 内存去重（默认）
    REDIS = "redis"            # Redis分布式去重
    BLOOM = "bloom"            # 大规模布隆过滤器
    ROTATION = "rotation"      # 滚动分区布隆过滤器
    NONE = "none"              # 不去重


class _NullDeduper(BaseDeduper):
    """空去重器 - 不做任何去重"""
    async def exists(self, key: str, **kwargs: Any) -> bool:
        return False

    async def add(self, key: str, **kwargs: Any) -> bool:
        return True


def create_deduper(strategy: str = "memory", **kwargs: Any) -> BaseDeduper:
    """
    根据策略名称创建去重器实例。

    Args:
        strategy: 去重策略 (memory/redis/bloom/rotation/none)
        **kwargs: 传递给具体去重器的参数

    Returns:
        BaseDeduper 实例

    示例::

        # 内存去重
        deduper = create_deduper("memory", capacity=500_000)

        # Redis去重
        deduper = create_deduper("redis", redis_url="redis://localhost:6379/3")

        # 布隆过滤器
        deduper = create_deduper("bloom", capacity=100_000_000, error_rate=0.0001)

        # 滚动分区
        deduper = create_deduper("rotation", partitions=10, storage_dir="/data/dedup")
    """
    strategy = strategy.lower()

    if strategy == DedupStrategy.NONE:
        logger.info("去重器: 已禁用 (none)")
        return _NullDeduper()

    elif strategy == DedupStrategy.MEMORY:
        from src.engine.dedup.memory_deduper import MemoryDeduper
        deduper = MemoryDeduper(**kwargs)
        logger.info(f"去重器: MemoryDeduper (容量={kwargs.get('capacity', 1_000_000):,})")
        return deduper

    elif strategy == DedupStrategy.REDIS:
        from src.engine.dedup.redis_deduper import RedisDeduper
        deduper = RedisDeduper(**kwargs)
        logger.info(f"去重器: RedisDeduper (url={kwargs.get('redis_url', 'default')})")
        return deduper

    elif strategy == DedupStrategy.BLOOM:
        from src.engine.dedup.bloom_deduper import BloomFilterDeduper
        deduper = BloomFilterDeduper(**kwargs)
        logger.info(f"去重器: BloomFilterDeduper (容量={kwargs.get('capacity', 100_000_000):,})")
        return deduper

    elif strategy == DedupStrategy.ROTATION:
        from src.engine.dedup.rotation_deduper import RotationDeduper
        deduper = RotationDeduper(**kwargs)
        logger.info(f"去重器: RotationDeduper (分区={kwargs.get('partitions', 20)})")
        return deduper

    else:
        raise ValueError(f"未知的去重策略: {strategy}. 可选: {[e.value for e in DedupStrategy]}")
