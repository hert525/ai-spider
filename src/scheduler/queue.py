"""Redis-based task queue."""
from __future__ import annotations

import json
from datetime import datetime

import redis.asyncio as aioredis
from loguru import logger

from src.core.config import settings


class TaskQueue:
    """Priority task queue backed by Redis sorted set."""

    QUEUE_KEY = "spider:tasks:queue"       # sorted set, score=priority
    RUNNING_KEY = "spider:tasks:running"   # hash: task_id -> worker_id
    RESULT_KEY = "spider:tasks:results"    # list for completed results

    def __init__(self) -> None:
        self._redis: aioredis.Redis | None = None

    async def connect(self) -> None:
        """Lazy connect to Redis."""
        if self._redis is None:
            self._redis = aioredis.from_url(settings.redis_url, decode_responses=True)
            logger.info(f"TaskQueue connected to Redis: {settings.redis_url}")

    async def _r(self) -> aioredis.Redis:
        await self.connect()
        return self._redis  # type: ignore[return-value]

    async def enqueue(self, task_id: str, priority: int = 5) -> None:
        """Add task to the priority queue. Lower score = higher priority."""
        r = await self._r()
        await r.zadd(self.QUEUE_KEY, {task_id: priority})
        logger.info(f"Task {task_id} enqueued (priority={priority})")

    async def dequeue(self, worker_id: str) -> str | None:
        """Pop highest-priority task and track it as running."""
        r = await self._r()
        results = await r.zpopmin(self.QUEUE_KEY, count=1)
        if not results:
            return None
        task_id, _score = results[0]
        await r.hset(self.RUNNING_KEY, task_id, worker_id)
        logger.info(f"Task {task_id} dequeued -> worker {worker_id}")
        return task_id

    async def complete(self, task_id: str, result: dict) -> None:
        """Mark task completed: remove from running, push result."""
        r = await self._r()
        await r.hdel(self.RUNNING_KEY, task_id)
        await r.lpush(self.RESULT_KEY, json.dumps({
            "task_id": task_id,
            "result": result,
            "completed_at": datetime.now().isoformat(),
        }))

    async def fail(self, task_id: str, error: str) -> None:
        """Mark task failed: remove from running."""
        r = await self._r()
        await r.hdel(self.RUNNING_KEY, task_id)
        await r.lpush(self.RESULT_KEY, json.dumps({
            "task_id": task_id,
            "error": error,
            "failed_at": datetime.now().isoformat(),
        }))

    async def get_queue_size(self) -> int:
        r = await self._r()
        return await r.zcard(self.QUEUE_KEY)

    async def get_running_count(self) -> int:
        r = await self._r()
        return await r.hlen(self.RUNNING_KEY)

    async def stats(self) -> dict:
        try:
            return {
                "queued": await self.get_queue_size(),
                "running": await self.get_running_count(),
            }
        except Exception:
            return {"queued": 0, "running": 0, "error": "Redis unavailable"}

    async def close(self) -> None:
        if self._redis:
            await self._redis.aclose()
            self._redis = None
            logger.info("TaskQueue Redis connection closed")


task_queue = TaskQueue()
