"""
Worker manager - track distributed workers and assign tasks.
"""
import time
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field
from loguru import logger


class WorkerInfo(BaseModel):
    id: str
    hostname: str = ""
    ip: str = ""
    status: str = "online"  # online / busy / offline
    current_task_id: Optional[str] = None
    current_run_id: Optional[str] = None
    max_concurrency: int = 3
    active_jobs: int = 0
    total_completed: int = 0
    total_failed: int = 0
    cpu_percent: float = 0
    memory_mb: float = 0
    last_heartbeat: datetime = Field(default_factory=datetime.now)
    registered_at: datetime = Field(default_factory=datetime.now)
    tags: list[str] = []  # e.g. ["playwright", "high-memory"]


class WorkerManager:
    """In-memory worker registry."""

    def __init__(self):
        self._workers: dict[str, WorkerInfo] = {}

    def register(self, worker_id: str, **kwargs) -> WorkerInfo:
        if worker_id in self._workers:
            w = self._workers[worker_id]
            w.status = "online"
            w.last_heartbeat = datetime.now()
            for k, v in kwargs.items():
                if hasattr(w, k):
                    setattr(w, k, v)
        else:
            w = WorkerInfo(id=worker_id, **kwargs)
            self._workers[worker_id] = w
        return w

    def heartbeat(self, worker_id: str, **stats) -> Optional[WorkerInfo]:
        w = self._workers.get(worker_id)
        if not w:
            return None
        w.last_heartbeat = datetime.now()
        w.status = stats.get("status", "online")
        for k in ("cpu_percent", "memory_mb", "active_jobs", "total_completed", "total_failed"):
            if k in stats:
                setattr(w, k, stats[k])
        return w

    def unregister(self, worker_id: str):
        self._workers.pop(worker_id, None)

    def list(self) -> list[WorkerInfo]:
        # Mark stale workers as offline (no heartbeat for 60s)
        now = datetime.now()
        for w in self._workers.values():
            if (now - w.last_heartbeat).total_seconds() > 60:
                w.status = "offline"
        return sorted(self._workers.values(), key=lambda w: w.registered_at)

    def get(self, worker_id: str) -> Optional[WorkerInfo]:
        return self._workers.get(worker_id)

    def get_available(self) -> Optional[WorkerInfo]:
        """Get a worker that can accept tasks."""
        candidates = [
            w for w in self._workers.values()
            if w.status == "online" and w.active_jobs < w.max_concurrency
        ]
        if not candidates:
            return None
        # Pick the one with fewest active jobs
        return min(candidates, key=lambda w: w.active_jobs)

    def stats(self) -> dict:
        workers = self.list()
        return {
            "total_workers": len(workers),
            "online": sum(1 for w in workers if w.status == "online"),
            "busy": sum(1 for w in workers if w.status == "busy"),
            "offline": sum(1 for w in workers if w.status == "offline"),
            "total_completed": sum(w.total_completed for w in workers),
        }


worker_manager = WorkerManager()
