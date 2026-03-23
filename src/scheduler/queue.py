"""Redis-based reliable task queue with ACK/retry/dead-letter support."""
from __future__ import annotations

import json
import time
from datetime import datetime

import redis.asyncio as aioredis
from loguru import logger

from src.core.config import settings

# Default retry config
DEFAULT_MAX_RETRIES = 3
DEFAULT_TASK_TIMEOUT = 300  # 5 minutes
DEFAULT_ACK_TIMEOUT = 60    # 1 minute to ACK after dequeue


class TaskQueue:
    """Priority task queue with ACK/NACK, retry, dead-letter, and timeout.

    Redis keys:
        spider:tasks:queue       - sorted set: {task_id: priority}
        spider:tasks:running     - hash: {task_id: JSON(worker_id, dequeued_at, ack_at)}
        spider:tasks:results     - list: completed/failed results
        spider:tasks:dead        - list: dead-letter tasks (exceeded max retries)
        spider:tasks:meta:{id}   - hash: retry_count, max_retries, last_error, created_at
    """

    QUEUE_KEY = "spider:tasks:queue"
    RUNNING_KEY = "spider:tasks:running"
    RESULT_KEY = "spider:tasks:results"
    DEAD_KEY = "spider:tasks:dead"
    META_PREFIX = "spider:tasks:meta:"

    def __init__(self) -> None:
        self._redis: aioredis.Redis | None = None

    async def connect(self) -> None:
        if self._redis is None:
            self._redis = aioredis.from_url(settings.redis_url, decode_responses=True)
            logger.info(f"TaskQueue connected to Redis: {settings.redis_url}")

    async def _r(self) -> aioredis.Redis:
        await self.connect()
        return self._redis  # type: ignore[return-value]

    # ── Enqueue ──

    async def enqueue(self, task_id: str, priority: int = 5,
                      max_retries: int = DEFAULT_MAX_RETRIES) -> None:
        """Add task to priority queue. Lower score = higher priority."""
        r = await self._r()
        await r.zadd(self.QUEUE_KEY, {task_id: priority})
        # Initialize meta if not exists
        meta_key = self.META_PREFIX + task_id
        if not await r.exists(meta_key):
            await r.hset(meta_key, mapping={
                "retry_count": 0,
                "max_retries": max_retries,
                "last_error": "",
                "created_at": datetime.now().isoformat(),
                "priority": priority,
            })
            await r.expire(meta_key, 86400 * 7)  # TTL 7 days
        logger.info(f"Task {task_id} enqueued (priority={priority})")

    # ── Dequeue + ACK ──

    async def dequeue(self, worker_id: str) -> str | None:
        """Pop highest-priority task. Must ACK within ACK_TIMEOUT or task returns to queue."""
        r = await self._r()
        results = await r.zpopmin(self.QUEUE_KEY, count=1)
        if not results:
            return None
        task_id, _score = results[0]
        run_info = json.dumps({
            "worker_id": worker_id,
            "dequeued_at": time.time(),
            "acked": False,
        })
        await r.hset(self.RUNNING_KEY, task_id, run_info)
        logger.info(f"Task {task_id} dequeued -> worker {worker_id}")
        return task_id

    async def ack(self, task_id: str) -> bool:
        """Worker confirms it started processing. Prevents ACK-timeout re-queue."""
        r = await self._r()
        raw = await r.hget(self.RUNNING_KEY, task_id)
        if not raw:
            return False
        info = json.loads(raw)
        info["acked"] = True
        info["ack_at"] = time.time()
        await r.hset(self.RUNNING_KEY, task_id, json.dumps(info))
        return True

    # ── Complete / Fail / NACK ──

    async def complete(self, task_id: str, result: dict) -> None:
        """Mark task successfully completed."""
        r = await self._r()
        await r.hdel(self.RUNNING_KEY, task_id)
        await r.lpush(self.RESULT_KEY, json.dumps({
            "task_id": task_id,
            "status": "success",
            "result": result,
            "completed_at": datetime.now().isoformat(),
        }))
        # Clean meta after success
        await r.delete(self.META_PREFIX + task_id)
        logger.info(f"Task {task_id} completed")

    async def fail(self, task_id: str, error: str) -> None:
        """Mark task failed. Will retry if under max_retries, else dead-letter."""
        r = await self._r()
        await r.hdel(self.RUNNING_KEY, task_id)

        meta_key = self.META_PREFIX + task_id
        retry_count = int(await r.hget(meta_key, "retry_count") or 0)
        max_retries = int(await r.hget(meta_key, "max_retries") or DEFAULT_MAX_RETRIES)
        priority = int(await r.hget(meta_key, "priority") or 5)

        await r.hset(meta_key, mapping={
            "retry_count": retry_count + 1,
            "last_error": error[:500],
            "last_failed_at": datetime.now().isoformat(),
        })

        if retry_count + 1 >= max_retries:
            # Dead letter
            await self._dead_letter(task_id, error, retry_count + 1)
        else:
            # Retry with exponential backoff encoded in priority (lower priority = wait)
            backoff_priority = priority + (retry_count + 1) * 2
            await r.zadd(self.QUEUE_KEY, {task_id: backoff_priority})
            logger.warning(
                f"Task {task_id} failed (attempt {retry_count + 1}/{max_retries}), "
                f"re-queued with priority {backoff_priority}: {error[:100]}"
            )

    async def nack(self, task_id: str, error: str = "NACK") -> None:
        """Explicitly reject task — same as fail (triggers retry/dead-letter)."""
        await self.fail(task_id, error)

    # ── Dead Letter ──

    async def _dead_letter(self, task_id: str, error: str, attempts: int) -> None:
        """Move task to dead-letter queue."""
        r = await self._r()
        await r.lpush(self.DEAD_KEY, json.dumps({
            "task_id": task_id,
            "error": error[:500],
            "attempts": attempts,
            "dead_at": datetime.now().isoformat(),
        }))
        logger.error(f"Task {task_id} dead-lettered after {attempts} attempts: {error[:100]}")

    async def list_dead_letters(self, limit: int = 50) -> list[dict]:
        """List dead-letter tasks."""
        r = await self._r()
        items = await r.lrange(self.DEAD_KEY, 0, limit - 1)
        return [json.loads(i) for i in items]

    async def retry_dead_letter(self, task_id: str, priority: int = 5) -> bool:
        """Move a dead-letter task back to the queue."""
        r = await self._r()
        # Remove from dead-letter list
        items = await r.lrange(self.DEAD_KEY, 0, -1)
        for item in items:
            data = json.loads(item)
            if data.get("task_id") == task_id:
                await r.lrem(self.DEAD_KEY, 1, item)
                # Reset meta
                meta_key = self.META_PREFIX + task_id
                await r.hset(meta_key, mapping={
                    "retry_count": 0,
                    "last_error": "",
                    "priority": priority,
                })
                await r.zadd(self.QUEUE_KEY, {task_id: priority})
                logger.info(f"Dead-letter task {task_id} re-queued")
                return True
        return False

    async def clear_dead_letters(self) -> int:
        """Clear all dead-letter tasks."""
        r = await self._r()
        count = await r.llen(self.DEAD_KEY)
        await r.delete(self.DEAD_KEY)
        return count

    # ── Timeout Sweeper ──

    async def sweep_timed_out(self, ack_timeout: int = DEFAULT_ACK_TIMEOUT,
                               task_timeout: int = DEFAULT_TASK_TIMEOUT) -> list[str]:
        """Sweep running tasks that timed out. Call periodically from scheduler.

        - Unacked tasks past ack_timeout → fail + retry
        - Acked tasks past task_timeout → fail + retry
        Returns list of recovered task_ids.
        """
        r = await self._r()
        running = await r.hgetall(self.RUNNING_KEY)
        now = time.time()
        recovered = []

        for task_id, raw in running.items():
            try:
                info = json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                # Corrupted entry, remove it
                await r.hdel(self.RUNNING_KEY, task_id)
                continue

            dequeued_at = info.get("dequeued_at", now)
            acked = info.get("acked", False)

            if not acked and (now - dequeued_at) > ack_timeout:
                logger.warning(f"Task {task_id} ACK timeout ({ack_timeout}s), recovering")
                await self.fail(task_id, f"ACK timeout after {int(now - dequeued_at)}s")
                recovered.append(task_id)
            elif acked and (now - dequeued_at) > task_timeout:
                logger.warning(f"Task {task_id} execution timeout ({task_timeout}s), recovering")
                await self.fail(task_id, f"Execution timeout after {int(now - dequeued_at)}s")
                recovered.append(task_id)

        if recovered:
            logger.info(f"Swept {len(recovered)} timed-out tasks: {recovered}")
        return recovered

    # ── Recover from restart ──

    async def recover_running_tasks(self) -> list[str]:
        """On startup, re-queue all 'running' tasks (server crashed mid-execution).
        Returns list of recovered task_ids.
        """
        r = await self._r()
        running = await r.hgetall(self.RUNNING_KEY)
        recovered = []
        for task_id, raw in running.items():
            try:
                info = json.loads(raw)
                priority = 3  # High priority for recovered tasks
                meta_key = self.META_PREFIX + task_id
                saved_priority = await r.hget(meta_key, "priority")
                if saved_priority:
                    priority = max(1, int(saved_priority) - 2)  # Boost priority
            except Exception:
                priority = 3

            await r.hdel(self.RUNNING_KEY, task_id)
            await r.zadd(self.QUEUE_KEY, {task_id: priority})
            recovered.append(task_id)
            logger.info(f"Recovered task {task_id} from crashed state -> re-queued (priority={priority})")

        if recovered:
            logger.info(f"Recovered {len(recovered)} tasks from previous crash")
        return recovered

    # ── Stats ──

    async def get_queue_size(self) -> int:
        r = await self._r()
        return await r.zcard(self.QUEUE_KEY)

    async def get_running_count(self) -> int:
        r = await self._r()
        return await r.hlen(self.RUNNING_KEY)

    async def get_dead_count(self) -> int:
        r = await self._r()
        return await r.llen(self.DEAD_KEY)

    async def get_task_meta(self, task_id: str) -> dict | None:
        """Get retry metadata for a task."""
        r = await self._r()
        data = await r.hgetall(self.META_PREFIX + task_id)
        return data if data else None

    async def stats(self) -> dict:
        try:
            return {
                "queued": await self.get_queue_size(),
                "running": await self.get_running_count(),
                "dead": await self.get_dead_count(),
            }
        except Exception:
            return {"queued": 0, "running": 0, "dead": 0, "error": "Redis unavailable"}

    async def close(self) -> None:
        if self._redis:
            await self._redis.aclose()
            self._redis = None
            logger.info("TaskQueue Redis connection closed")


task_queue = TaskQueue()
