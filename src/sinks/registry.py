"""Sink registry - factory pattern for creating sinks."""
from __future__ import annotations

from typing import Dict, Type

from src.sinks.base import BaseSink

_SINKS: Dict[str, Type[BaseSink]] = {}


def register_sink(name: str, cls: Type[BaseSink]):
    """Register a sink class by name."""
    _SINKS[name] = cls


def get_sink(name: str, config: dict | None = None) -> BaseSink:
    """Create a sink instance by name with optional config."""
    if name not in _SINKS:
        raise ValueError(f"Unknown sink type: {name!r}. Available: {list(_SINKS.keys())}")
    cls = _SINKS[name]
    if config is None:
        config = {}
    # SQLiteSink takes no config args; others take config dict
    try:
        return cls(config)
    except TypeError:
        return cls()


class SinkRegistry:
    """Helper class exposing registry operations."""
    register = staticmethod(register_sink)
    get = staticmethod(get_sink)
    
    @staticmethod
    def available() -> list[str]:
        return list(_SINKS.keys())


# Auto-register built-in sinks
from src.sinks.sqlite_sink import SQLiteSink
from src.sinks.local_file_sink import LocalFileSink
from src.sinks.kafka_sink import KafkaSink
from src.sinks.s3_sink import S3Sink
from src.sinks.parquet_sink import ParquetSink

register_sink("sqlite", SQLiteSink)
register_sink("local_file", LocalFileSink)
register_sink("kafka", KafkaSink)
register_sink("s3", S3Sink)
register_sink("parquet", ParquetSink)
