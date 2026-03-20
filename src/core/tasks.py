"""
Task manager - schedule, queue, and track crawl tasks.
"""
import json
import time
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional, Any
from pydantic import BaseModel, Field
from loguru import logger
import uuid

from src.core.config import BASE_DIR

TASKS_DIR = BASE_DIR / "data" / "tasks"
TASKS_DIR.mkdir(parents=True, exist_ok=True)


class TaskType(str, Enum):
    ONE_TIME = "one_time"       # 单次运行
    SCHEDULED = "scheduled"     # 定时运行
    CONTINUOUS = "continuous"   # 持续运行


class TaskStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"
    CANCELLED = "cancelled"


class TaskRun(BaseModel):
    """A single execution record of a task."""
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    task_id: str
    status: TaskStatus = TaskStatus.QUEUED
    worker_id: Optional[str] = None
    items_crawled: int = 0
    items_total: int = 0
    pages_visited: int = 0
    errors: list[str] = []
    output_preview: list[dict] = []
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    duration_ms: int = 0
    created_at: datetime = Field(default_factory=datetime.now)


class Task(BaseModel):
    """A crawl task definition."""
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    project_id: str
    name: str = ""
    task_type: TaskType = TaskType.ONE_TIME
    target_urls: list[str] = []
    status: TaskStatus = TaskStatus.QUEUED
    priority: int = 5  # 1=highest, 10=lowest
    # Schedule config (for scheduled tasks)
    cron_expr: Optional[str] = None  # e.g. "0 */6 * * *"
    # Limits
    max_pages: int = 100
    max_items: int = 10000
    timeout_seconds: int = 300
    concurrency: int = 3
    # Stats
    total_runs: int = 0
    successful_runs: int = 0
    failed_runs: int = 0
    total_items: int = 0
    last_run_at: Optional[datetime] = None
    # Runs history
    runs: list[TaskRun] = []
    # Meta
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    created_by: str = "user"


class TaskStore:
    """File-backed task store."""

    def __init__(self):
        self._tasks: dict[str, Task] = {}
        self._load_all()

    def _load_all(self):
        for f in TASKS_DIR.glob("*.json"):
            try:
                data = json.loads(f.read_text("utf-8"))
                task = Task(**data)
                self._tasks[task.id] = task
            except Exception as e:
                logger.warning(f"Failed to load task {f}: {e}")

    def _save(self, task: Task):
        path = TASKS_DIR / f"{task.id}.json"
        path.write_text(task.model_dump_json(indent=2), encoding="utf-8")

    def list(self, status: Optional[TaskStatus] = None, project_id: Optional[str] = None) -> list[Task]:
        tasks = self._tasks.values()
        if status:
            tasks = [t for t in tasks if t.status == status]
        if project_id:
            tasks = [t for t in tasks if t.project_id == project_id]
        return sorted(tasks, key=lambda t: t.created_at, reverse=True)

    def get(self, task_id: str) -> Optional[Task]:
        return self._tasks.get(task_id)

    def create(self, **kwargs) -> Task:
        task = Task(**kwargs)
        self._tasks[task.id] = task
        self._save(task)
        return task

    def update(self, task_id: str, **kwargs) -> Optional[Task]:
        task = self._tasks.get(task_id)
        if not task:
            return None
        for k, v in kwargs.items():
            if hasattr(task, k):
                setattr(task, k, v)
        task.updated_at = datetime.now()
        self._save(task)
        return task

    def delete(self, task_id: str) -> bool:
        if task_id in self._tasks:
            del self._tasks[task_id]
            (TASKS_DIR / f"{task_id}.json").unlink(missing_ok=True)
            return True
        return False

    def add_run(self, task_id: str, run: TaskRun) -> Optional[Task]:
        task = self._tasks.get(task_id)
        if not task:
            return None
        task.runs.append(run)
        task.total_runs += 1
        task.last_run_at = datetime.now()
        task.updated_at = datetime.now()
        self._save(task)
        return task

    def update_run(self, task_id: str, run_id: str, **kwargs) -> Optional[TaskRun]:
        task = self._tasks.get(task_id)
        if not task:
            return None
        for run in task.runs:
            if run.id == run_id:
                for k, v in kwargs.items():
                    if hasattr(run, k):
                        setattr(run, k, v)
                if kwargs.get("status") == TaskStatus.COMPLETED:
                    task.successful_runs += 1
                    task.total_items += run.items_crawled
                elif kwargs.get("status") == TaskStatus.FAILED:
                    task.failed_runs += 1
                task.updated_at = datetime.now()
                self._save(task)
                return run
        return None

    def stats(self) -> dict:
        """Global stats."""
        tasks = list(self._tasks.values())
        return {
            "total_tasks": len(tasks),
            "queued": sum(1 for t in tasks if t.status == TaskStatus.QUEUED),
            "running": sum(1 for t in tasks if t.status == TaskStatus.RUNNING),
            "completed": sum(1 for t in tasks if t.status == TaskStatus.COMPLETED),
            "failed": sum(1 for t in tasks if t.status == TaskStatus.FAILED),
            "total_runs": sum(t.total_runs for t in tasks),
            "total_items": sum(t.total_items for t in tasks),
        }


task_store = TaskStore()
