"""Kafka sink - writes records to Kafka topics via aiokafka."""
from __future__ import annotations

import json

from src.sinks.base import BaseSink


class KafkaSink(BaseSink):
    """Write records to a Kafka topic."""

    def __init__(self, config: dict):
        self.bootstrap_servers = config.get("bootstrap_servers", "localhost:9092")
        self.topic = config.get("topic", "crawl-data")
        self.key_field = config.get("key_field")
        self._producer = None

    async def _ensure_producer(self):
        if self._producer is not None:
            return self._producer
        try:
            from aiokafka import AIOKafkaProducer
        except ImportError:
            raise RuntimeError(
                "aiokafka is not installed. Install it with: "
                "pip install aiokafka"
            )
        self._producer = AIOKafkaProducer(
            bootstrap_servers=self.bootstrap_servers,
            value_serializer=lambda v: json.dumps(v, ensure_ascii=False).encode("utf-8"),
            key_serializer=lambda k: k.encode("utf-8") if k else None,
        )
        await self._producer.start()
        return self._producer

    async def write(self, records: list[dict], metadata: dict) -> int:
        try:
            producer = await self._ensure_producer()
        except RuntimeError as e:
            # Friendly error: library not installed
            raise RuntimeError(str(e))

        for rec in records:
            key = str(rec.get(self.key_field, "")) if self.key_field else None
            await producer.send_and_wait(self.topic, value=rec, key=key)

        return len(records)

    async def close(self):
        if self._producer is not None:
            await self._producer.stop()
            self._producer = None
