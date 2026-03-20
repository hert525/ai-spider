"""Base sink interface for data output."""
from __future__ import annotations

from abc import ABC, abstractmethod
from pydantic import BaseModel
from typing import Any


class SinkConfig(BaseModel):
    """Base config for all sinks."""
    sink_type: str  # "local_file", "sqlite", "kafka", "s3"


class BaseSink(ABC):
    """Abstract base class for data output sinks."""

    @abstractmethod
    async def write(self, records: list[dict], metadata: dict) -> int:
        """Write records. metadata contains project_id, task_id, etc. Returns count written."""
        ...

    @abstractmethod
    async def close(self):
        """Cleanup resources."""
        ...

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        await self.close()
