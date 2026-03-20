"""
Data models for crawler projects.
"""
from datetime import datetime
from enum import Enum
from typing import Optional, Any
from pydantic import BaseModel, Field
import uuid


class CrawlerStatus(str, Enum):
    DRAFT = "draft"           # AI generated, not tested yet
    TESTING = "testing"       # Running sandbox test
    TESTED = "tested"         # Test completed, awaiting review
    APPROVED = "approved"     # User approved, ready for deployment
    RUNNING = "running"       # Deployed and running
    PAUSED = "paused"
    FAILED = "failed"
    COMPLETED = "completed"


class CrawlerProject(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    name: str = ""
    description: str = ""  # User's natural language description
    target_url: str = ""
    code: str = ""         # Generated Python crawler code
    status: CrawlerStatus = CrawlerStatus.DRAFT
    version: int = 1
    test_results: list[dict[str, Any]] = []
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    # Conversation history for iterative refinement
    messages: list[dict[str, str]] = []


class TestRun(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    project_id: str
    code: str
    status: str = "pending"  # pending / running / success / error
    output: list[dict[str, Any]] = []
    error: Optional[str] = None
    pages_crawled: int = 0
    duration_ms: int = 0
    created_at: datetime = Field(default_factory=datetime.now)


class CrawlTask(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    project_id: str
    code: str
    target_urls: list[str] = []
    status: str = "queued"  # queued / running / completed / failed
    total_items: int = 0
    progress: int = 0
    worker_id: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.now)
