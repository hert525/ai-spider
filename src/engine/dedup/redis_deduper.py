"""
Redis去重器 - 基于 Redis SET/GET 实现分布式去重。

适用场景：分布式多节点去重，支持TTL自动过期。
从 wukong/dedup/redis_deduper.py 移植并适配 async 接口。
"""
from __future__ import annotations

from typing import Any

from loguru import logger

from src.engine.dedup.base import BaseDeduper


class RedisDeduper(BaseDeduper):
    """
    Redis去重器。

    使用 Redis 的 SET/GET 实现分布式去重，支持：
    - TTL 自动过期（默认365天）
    - 分布式多节点共享
    - 高性能并发

    Args:
        redis_url: Redis连接URL
        prefix: key前缀（用于隔离不同项目）
        ttl: key的过期时间（秒），默认365天
    """

    def __init__(
        self,
        redis_url: str = "redis://127.0.0.1:6379/3",
        prefix: str = "dedup:",
        ttl: int = 60 * 60 * 24 * 365,
    ):
        self.prefix = prefix
        self.ttl = ttl
        self._redis = None
        self._redis_url = redis_url

    async def _get_redis(self):
        """懒初始化Redis连接"""
        if self._redis is None:
            try:
                import redis.asyncio as aioredis
                self._redis = aioredis.from_url(
                    self._redis_url,
                    decode_responses=True,
                    max_connections=128,
                )
                logger.info(f"RedisDeduper: 已连接 {self._redis_url}")
            except ImportError:
                raise ImportError("需要安装 redis[hiredis] 包: pip install redis[hiredis]")
        return self._redis

    def _make_key(self, key: str) -> str:
        """生成带前缀的Redis key"""
        return f"{self.prefix}{key}"

    async def exists(self, key: str, **kwargs: Any) -> bool:
        """检查key是否存在"""
        r = await self._get_redis()
        result = await r.exists(self._make_key(key))
        return bool(result)

    async def add(self, key: str, **kwargs: Any) -> bool:
        """添加key到Redis（带TTL）"""
        r = await self._get_redis()
        redis_key = self._make_key(key)
        await r.setex(redis_key, self.ttl, "1")
        return True

    async def exists_and_add(self, key: str, **kwargs: Any) -> bool:
        """
        原子性检查并添加（使用 SET NX）。

        Returns:
            True 表示已存在（重复），False 表示新数据且已添加
        """
        r = await self._get_redis()
        redis_key = self._make_key(key)
        # SET NX 返回 True 表示设置成功（key不存在），False 表示key已存在
        result = await r.set(redis_key, "1", ex=self.ttl, nx=True)
        return not bool(result)  # NX返回True表示成功设置(不存在)，我们返回False

    async def close(self) -> None:
        """关闭Redis连接"""
        if self._redis:
            await self._redis.close()
            self._redis = None
            logger.info("RedisDeduper: Redis连接已关闭")

    async def count(self) -> int:
        """获取去重集合中的key数量（近似值）"""
        r = await self._get_redis()
        cursor = 0
        count = 0
        while True:
            cursor, keys = await r.scan(cursor, match=f"{self.prefix}*", count=1000)
            count += len(keys)
            if cursor == 0:
                break
        return count
