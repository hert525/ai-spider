"""Task lifecycle manager."""
from __future__ import annotations

import uuid
from datetime import datetime

from loguru import logger

from src.core.database import db
from src.core.models import Task, TaskStatus, TaskType, TaskRun, _uid
from src.scheduler.queue import task_queue


class TaskManager:
    """Manages task lifecycle: create → queue → assign → complete/fail."""

    # ── creation ──

    async def create_task(
        self,
        project_id: str,
        user_id: str,
        task_type: str = "one_time",
        target_urls: list[str] | None = None,
        priority: int = 5,
        cron_expr: str = "",
        max_pages: int = 100,
        timeout_seconds: int = 300,
        concurrency: int = 3,
        name: str = "",
        max_items: int = 10000,
    ) -> dict:
        """Create task in DB and enqueue to Redis."""
        task = Task(
            project_id=project_id,
            name=name,
            user_id=user_id,
            task_type=TaskType(task_type),
            target_urls=target_urls or [],
            priority=priority,
            cron_expr=cron_expr,
            max_pages=max_pages,
            max_items=max_items,
            timeout_seconds=timeout_seconds,
            concurrency=concurrency,
            status=TaskStatus.QUEUED,
        )
        await db.insert("tasks", task.model_dump())
        await task_queue.enqueue(task.id, priority)
        logger.info(f"Task {task.id} created & enqueued for project {project_id}")
        return task.model_dump()

    # ── assignment (called by worker poll) ──

    async def assign_task(self, worker_id: str) -> dict | None:
        """Pop a task from the queue and assign to a worker."""
        task_id = await task_queue.dequeue(worker_id)
        if not task_id:
            return None

        now = datetime.now().isoformat()
        await db.update("tasks", task_id, {
            "status": TaskStatus.RUNNING,
            "worker_id": worker_id,
            "updated_at": now,
        })

        # Create a task_run record
        run = TaskRun(task_id=task_id, worker_id=worker_id)
        await db.insert("task_runs", run.model_dump())

        task_data = await db.get("tasks", task_id)
        if not task_data:
            return None

        # Fetch project code so the worker can execute
        project = await db.get("projects", task_data["project_id"])

        return {
            "task_id": task_id,
            "run_id": run.id,
            "project_id": task_data["project_id"],
            "target_urls": task_data.get("target_urls", []),
            "timeout_seconds": task_data.get("timeout_seconds", 300),
            "concurrency": task_data.get("concurrency", 3),
            "max_pages": task_data.get("max_pages", 100),
            "code": project.get("code", "") if project else "",
            "mode": project.get("mode", "code_generator") if project else "code_generator",
            "description": project.get("description", "") if project else "",
            "target_url": task_data.get("target_urls", [""])[0] if task_data.get("target_urls") else "",
        }

    # ── completion ──

    async def complete_task(self, task_id: str, run_id: str, items_count: int, pages_crawled: int) -> None:
        now = datetime.now().isoformat()
        await db.update("task_runs", run_id, {
            "status": TaskStatus.SUCCESS,
            "items_count": items_count,
            "pages_crawled": pages_crawled,
            "finished_at": now,
        })
        await db.update("tasks", task_id, {
            "status": TaskStatus.SUCCESS,
            "updated_at": now,
        })
        await task_queue.complete(task_id, {"items_count": items_count, "pages_crawled": pages_crawled})
        logger.info(f"Task {task_id} completed: {items_count} items, {pages_crawled} pages")

    async def fail_task(self, task_id: str, run_id: str, error: str) -> None:
        now = datetime.now().isoformat()
        await db.update("task_runs", run_id, {
            "status": TaskStatus.FAILED,
            "error": error,
            "finished_at": now,
        })
        # Check retry
        task_data = await db.get("tasks", task_id)
        retry_count = (task_data or {}).get("retry_count", 0)
        max_retries = (task_data or {}).get("max_retries", 3)

        if retry_count < max_retries:
            await db.update("tasks", task_id, {
                "status": TaskStatus.QUEUED,
                "retry_count": retry_count + 1,
                "worker_id": None,
                "updated_at": now,
            })
            priority = (task_data or {}).get("priority", 5)
            await task_queue.enqueue(task_id, priority)
            logger.info(f"Task {task_id} failed, retry {retry_count + 1}/{max_retries}")
        else:
            await db.update("tasks", task_id, {
                "status": TaskStatus.FAILED,
                "updated_at": now,
            })
            await task_queue.fail(task_id, error)
            logger.error(f"Task {task_id} failed permanently: {error}")

    # ── manual retry ──

    async def retry_task(self, task_id: str) -> bool:
        task_data = await db.get("tasks", task_id)
        if not task_data:
            return False
        now = datetime.now().isoformat()
        await db.update("tasks", task_id, {
            "status": TaskStatus.QUEUED,
            "retry_count": 0,
            "worker_id": None,
            "updated_at": now,
        })
        await task_queue.enqueue(task_id, task_data.get("priority", 5))
        logger.info(f"Task {task_id} manually re-queued")
        return True

    # ── cancel ──

    async def cancel_task(self, task_id: str) -> bool:
        task_data = await db.get("tasks", task_id)
        if not task_data:
            return False
        await db.update("tasks", task_id, {
            "status": TaskStatus.CANCELLED,
            "updated_at": datetime.now().isoformat(),
        })
        logger.info(f"Task {task_id} cancelled")
        return True

    # ── helpers used by existing code ──

    async def get_task(self, task_id: str) -> Task | None:
        data = await db.get("tasks", task_id)
        return Task(**data) if data else None

    async def list_tasks(self, project_id: str | None = None, status: str | None = None, limit: int = 50) -> list[Task]:
        where: dict = {}
        if project_id:
            where["project_id"] = project_id
        if status:
            where["status"] = status
        rows = await db.list("tasks", where=where or None, limit=limit)
        return [Task(**r) for r in rows]

    async def update_task(self, task_id: str, **kwargs) -> Task | None:
        kwargs["updated_at"] = datetime.now().isoformat()
        await db.update("tasks", task_id, kwargs)
        return await self.get_task(task_id)

    async def delete_task(self, task_id: str) -> bool:
        return await db.delete("tasks", task_id)

    async def get_runs(self, task_id: str) -> list[TaskRun]:
        rows = await db.list("task_runs", where={"task_id": task_id})
        return [TaskRun(**r) for r in rows]

    async def stats(self) -> dict:
        counts = {}
        for status in TaskStatus:
            counts[status.value] = await db.count("tasks", {"status": status.value})
        queue_stats = await task_queue.stats()
        return {"by_status": counts, "queue": queue_stats}


task_manager = TaskManager()
