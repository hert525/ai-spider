"""Redis task queue."""
import json
from datetime import datetime
from loguru import logger

try:
    import redis.asyncio as aioredis
except ImportError:
    aioredis = None

from src.core.config import settings

QUEUE_KEY = "spider:task_queue"
RUNNING_KEY = "spider:running_tasks"


class TaskQueue:
    """Redis-backed task queue with priority support."""

    def __init__(self):
        self._redis = None

    async def _get_redis(self):
        if self._redis is None:
            if aioredis is None:
                raise RuntimeError("redis package not installed")
            self._redis = aioredis.from_url(settings.redis_url, decode_responses=True)
        return self._redis

    async def push(self, task_id: str, priority: int = 5, data: dict | None = None):
        """Push task to queue. Lower priority number = higher priority."""
        r = await self._get_redis()
        payload = json.dumps({"task_id": task_id, "data": data or {}, "queued_at": datetime.now().isoformat()})
        await r.zadd(QUEUE_KEY, {payload: priority})
        logger.info(f"Task {task_id} queued (priority={priority})")

    async def pop(self) -> dict | None:
        """Pop highest priority task from queue."""
        r = await self._get_redis()
        results = await r.zpopmin(QUEUE_KEY, count=1)
        if not results:
            return None
        payload, score = results[0]
        data = json.loads(payload)
        # Track as running
        await r.hset(RUNNING_KEY, data["task_id"], payload)
        return data

    async def complete(self, task_id: str):
        """Mark task as completed."""
        r = await self._get_redis()
        await r.hdel(RUNNING_KEY, task_id)

    async def fail(self, task_id: str):
        """Mark task as failed."""
        r = await self._get_redis()
        await r.hdel(RUNNING_KEY, task_id)

    async def size(self) -> int:
        r = await self._get_redis()
        return await r.zcard(QUEUE_KEY)

    async def running_count(self) -> int:
        r = await self._get_redis()
        return await r.hlen(RUNNING_KEY)

    async def stats(self) -> dict:
        try:
            return {
                "queued": await self.size(),
                "running": await self.running_count(),
            }
        except Exception:
            return {"queued": 0, "running": 0, "error": "Redis unavailable"}


task_queue = TaskQueue()
