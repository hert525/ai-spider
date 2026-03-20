"""Pydantic models for the application."""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field
import uuid


def _uid() -> str:
    return uuid.uuid4().hex[:12]


# ── Enums ──
class ProjectMode(str, Enum):
    SMART_SCRAPER = "smart_scraper"
    CODE_GENERATOR = "code_generator"


class ProjectStatus(str, Enum):
    DRAFT = "draft"
    GENERATING = "generating"
    GENERATED = "generated"
    TESTING = "testing"
    TESTED = "tested"
    FAILED = "failed"
    APPROVED = "approved"


class TaskStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PAUSED = "paused"


class TaskType(str, Enum):
    ONE_TIME = "one_time"
    CRON = "cron"
    CONTINUOUS = "continuous"


class WorkerStatus(str, Enum):
    ONLINE = "online"
    OFFLINE = "offline"
    BUSY = "busy"
    DISABLED = "disabled"
    DRAINING = "draining"
    ERROR = "error"


# ── Project ──
class Project(BaseModel):
    id: str = Field(default_factory=_uid)
    name: str = ""
    description: str = ""
    target_url: str = ""
    mode: ProjectMode = ProjectMode.CODE_GENERATOR
    status: ProjectStatus = ProjectStatus.DRAFT
    code: str = ""
    extracted_data: Optional[list] = None
    version: int = 1
    messages: list[dict] = []
    test_results: list[dict] = []
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


# ── Task ──
class Task(BaseModel):
    id: str = Field(default_factory=_uid)
    project_id: str = ""
    name: str = ""
    user_id: str = ""
    task_type: TaskType = TaskType.ONE_TIME
    status: TaskStatus = TaskStatus.QUEUED
    target_urls: list[str] = []
    cron_expr: str = ""
    priority: int = 5
    max_pages: int = 100
    max_items: int = 10000
    timeout_seconds: int = 300
    concurrency: int = 3
    retry_count: int = 0
    max_retries: int = 3
    worker_id: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class TaskRun(BaseModel):
    id: str = Field(default_factory=_uid)
    task_id: str = ""
    worker_id: str = ""
    status: TaskStatus = TaskStatus.RUNNING
    items_count: int = 0
    pages_crawled: int = 0
    error: str = ""
    started_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    finished_at: str = ""
    duration_ms: int = 0


# ── Worker ──
class Worker(BaseModel):
    id: str = ""
    hostname: str = ""
    ip: str = ""
    status: WorkerStatus = WorkerStatus.ONLINE
    max_concurrency: int = 3
    active_jobs: int = 0
    total_completed: int = 0
    total_failed: int = 0
    cpu_percent: float = 0
    memory_mb: float = 0
    memory_total_mb: float = 0
    disk_percent: float = 0
    python_version: str = ""
    os_info: str = ""
    tags: list[str] = []
    current_tasks: list[str] = []
    last_heartbeat: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    registered_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


# ── Test result ──
class TestResult(BaseModel):
    status: str = "success"
    output: list[dict] = []
    error: str = ""
    pages_crawled: int = 0
    duration_ms: int = 0


# ── Data record ──
class DataRecord(BaseModel):
    id: str = Field(default_factory=_uid)
    project_id: str = ""
    task_id: str = ""
    task_run_id: str = ""
    data: dict = {}
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
