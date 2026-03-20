"""S3 sink - writes records to Amazon S3."""
from __future__ import annotations

import json
from datetime import datetime, timezone

from src.sinks.base import BaseSink


class S3Sink(BaseSink):
    """Write records to S3 in jsonl or json format."""

    def __init__(self, config: dict):
        self.bucket = config.get("bucket", "")
        self.prefix = config.get("prefix", "crawl-data")
        self.region = config.get("region", "us-east-1")
        self.access_key = config.get("access_key", "")
        self.secret_key = config.get("secret_key", "")
        self.format = config.get("format", "jsonl")
        self._buffer: list[dict] = []
        self.batch_size = config.get("batch_size", 1000)
        self._client = None
        self._last_project_id = ""

    def _get_client(self):
        if self._client is not None:
            return self._client
        try:
            import boto3
        except ImportError:
            raise RuntimeError(
                "boto3 is not installed. Install it with: "
                "pip install boto3"
            )
        kwargs = {"region_name": self.region}
        if self.access_key and self.secret_key:
            kwargs["aws_access_key_id"] = self.access_key
            kwargs["aws_secret_access_key"] = self.secret_key
        self._client = boto3.client("s3", **kwargs)
        return self._client

    def _build_key(self, project_id: str) -> str:
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
        ext = self.format
        return f"{self.prefix}/{project_id}/{ts}.{ext}"

    def _serialize(self, records: list[dict]) -> bytes:
        if self.format == "jsonl":
            return "\n".join(
                json.dumps(r, ensure_ascii=False) for r in records
            ).encode("utf-8")
        else:
            return json.dumps(records, ensure_ascii=False, indent=2).encode("utf-8")

    async def _flush(self):
        if not self._buffer:
            return
        client = self._get_client()
        key = self._build_key(self._last_project_id)
        body = self._serialize(self._buffer)
        client.put_object(Bucket=self.bucket, Key=key, Body=body)
        self._buffer.clear()

    async def write(self, records: list[dict], metadata: dict) -> int:
        try:
            self._get_client()
        except RuntimeError as e:
            raise RuntimeError(str(e))

        self._last_project_id = metadata.get("project_id", "default")
        self._buffer.extend(records)
        count = len(records)

        if len(self._buffer) >= self.batch_size:
            await self._flush()

        return count

    async def close(self):
        await self._flush()
        self._client = None
