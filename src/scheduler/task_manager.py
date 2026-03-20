"""Task manager - orchestrates task lifecycle."""
import json
from datetime import datetime
from loguru import logger
from src.core.database import db
from src.core.models import Task, TaskStatus, TaskRun
from src.scheduler.queue import task_queue


class TaskManager:
    """Manage task lifecycle: create → queue → run → complete."""

    async def create_task(self, task: Task) -> Task:
        """Create a task and optionally queue it."""
        await db.insert("tasks", task.model_dump())
        if task.status == TaskStatus.QUEUED:
            await task_queue.push(task.id, task.priority)
        logger.info(f"Task created: {task.id} ({task.task_type})")
        return task

    async def get_task(self, task_id: str) -> Task | None:
        data = await db.get("tasks", task_id)
        return Task(**data) if data else None

    async def list_tasks(self, project_id: str = None, status: str = None, limit: int = 50) -> list[Task]:
        where = {}
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

    async def queue_task(self, task_id: str):
        task = await self.get_task(task_id)
        if task:
            await self.update_task(task_id, status=TaskStatus.QUEUED)
            await task_queue.push(task_id, task.priority)

    async def start_run(self, task_id: str, worker_id: str) -> TaskRun:
        run = TaskRun(task_id=task_id, worker_id=worker_id)
        await db.insert("task_runs", run.model_dump())
        await self.update_task(task_id, status=TaskStatus.RUNNING, worker_id=worker_id)
        return run

    async def complete_run(self, run_id: str, items_count: int = 0, pages_crawled: int = 0):
        now = datetime.now().isoformat()
        await db.update("task_runs", run_id, {
            "status": TaskStatus.SUCCESS,
            "items_count": items_count,
            "pages_crawled": pages_crawled,
            "finished_at": now,
        })

    async def fail_run(self, run_id: str, error: str):
        now = datetime.now().isoformat()
        await db.update("task_runs", run_id, {
            "status": TaskStatus.FAILED,
            "error": error,
            "finished_at": now,
        })

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
