"""
Parquet存储Sink - 从 wukong/storage/ 移植并适配 async 架构。

功能：
- Parquet格式写入（高效列式存储）
- 多种压缩支持（gzip/zstd/lz4/snappy）
- 自动文件分片（按行数/大小/时间）
- 异步写入接口
"""
from __future__ import annotations

import asyncio
import gc
import json
import os
import time
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Optional

from loguru import logger

from src.sinks.base import BaseSink


# ============================================================
# 压缩格式（从 wukong/storage/compression.py 移植）
# ============================================================

class CompressionFormat(str, Enum):
    """支持的压缩格式"""
    NONE = "none"
    GZIP = "gzip"
    LZ4 = "lz4"
    ZSTD = "zstd"
    SNAPPY = "snappy"


def compress_data(data: bytes, fmt: CompressionFormat) -> bytes:
    """压缩数据"""
    if fmt == CompressionFormat.NONE:
        return data
    elif fmt == CompressionFormat.GZIP:
        import gzip
        return gzip.compress(data)
    elif fmt == CompressionFormat.LZ4:
        import lz4.frame
        return lz4.frame.compress(data)
    elif fmt == CompressionFormat.ZSTD:
        import zstandard as zstd
        return zstd.ZstdCompressor().compress(data)
    else:
        raise ValueError(f"不支持的压缩格式: {fmt}")


def decompress_data(data: bytes, fmt: CompressionFormat) -> bytes:
    """解压数据"""
    if fmt == CompressionFormat.NONE:
        return data
    elif fmt == CompressionFormat.GZIP:
        import gzip
        return gzip.decompress(data)
    elif fmt == CompressionFormat.LZ4:
        import lz4.frame
        return lz4.frame.decompress(data)
    elif fmt == CompressionFormat.ZSTD:
        import zstandard as zstd
        return zstd.ZstdDecompressor().decompress(data)
    else:
        raise ValueError(f"不支持的压缩格式: {fmt}")


# ============================================================
# 文件分片策略（从 wukong/storage/writer.py 移植）
# ============================================================

class SplitGranularity(str, Enum):
    """文件按时间分片粒度"""
    NONE = "none"
    HOUR = "hour"
    DAY = "day"


# ============================================================
# Parquet Sink（从 wukong/storage/writer.py ParquetWriter 移植）
# ============================================================

class ParquetSink(BaseSink):
    """
    Parquet文件存储 Sink。

    支持：
    - 列式存储（高效压缩、高性能分析查询）
    - 多种压缩（ZSTD推荐，压缩比高）
    - 自动分片（按行数/大小/时间自动切分文件）
    - 异步写入（在线程池中执行IO操作）

    Args:
        config: 配置字典
            - output_dir: 输出目录 (默认 "data/parquet_output")
            - compression: 压缩格式 (none/gzip/zstd/lz4/snappy)
            - max_records: 每文件最大行数 (默认 10000)
            - max_size_mb: 每文件最大大小MB (默认 512)
            - split_by_time: 时间分片粒度 (none/hour/day)
            - compression_level: 压缩级别
    """

    def __init__(self, config: dict):
        self.output_dir = config.get("output_dir", "data/parquet_output")
        self.compression = CompressionFormat(config.get("compression", "zstd"))
        self.max_records = config.get("max_records", 10_000)
        self.max_size_mb = config.get("max_size_mb", 512.0)
        self.split_by_time = SplitGranularity(config.get("split_by_time", "none"))
        self.compression_level = config.get("compression_level", 11)  # ZSTD默认级别

        # 缓冲区
        self._buffer: list[dict] = []
        self._buffer_size: int = 0
        self._file_count: int = 0
        self._total_records: int = 0
        self._lock = asyncio.Lock()

        # 统计
        self._stats = {
            "files_written": 0,
            "records_written": 0,
            "bytes_written": 0,
            "start_time": time.time(),
        }

        logger.info(
            f"ParquetSink: 初始化 (目录={self.output_dir}, "
            f"压缩={self.compression.value}, 每文件最大={self.max_records}行)"
        )

    def _estimate_size(self, record: dict) -> int:
        """估算记录大小（字节）"""
        size = 0
        for v in record.values():
            if isinstance(v, (str, bytes)):
                size += len(v)
            elif isinstance(v, (int, float)):
                size += 8
            else:
                size += 64
        return size

    def _get_time_folder(self) -> str:
        """根据时间分片粒度获取子目录"""
        if self.split_by_time == SplitGranularity.NONE:
            return ""
        now = datetime.now()
        if self.split_by_time == SplitGranularity.DAY:
            return now.strftime("%Y%m%d")
        elif self.split_by_time == SplitGranularity.HOUR:
            return os.path.join(now.strftime("%Y%m%d"), now.strftime("%H"))
        return ""

    def _generate_filename(self, metadata: dict) -> str:
        """生成文件路径"""
        project_id = metadata.get("project_id", "default")
        base_dir = os.path.join(self.output_dir, project_id)
        time_folder = self._get_time_folder()
        if time_folder:
            base_dir = os.path.join(base_dir, time_folder)
        os.makedirs(base_dir, exist_ok=True)

        ts = int(time.time_ns())
        filename = f"part-{ts}.parquet"
        return os.path.join(base_dir, filename)

    def _should_flush(self) -> bool:
        """判断是否需要刷写"""
        if len(self._buffer) >= self.max_records:
            return True
        if self._buffer_size >= self.max_size_mb * 1024 * 1024:
            return True
        return False

    async def write(self, records: list[dict], metadata: dict) -> int:
        """写入记录到缓冲区，满时自动刷写"""
        if not records:
            return 0

        async with self._lock:
            for rec in records:
                self._buffer.append(rec)
                self._buffer_size += self._estimate_size(rec)

            if self._should_flush():
                await self._flush(metadata)

            return len(records)

    async def _flush(self, metadata: dict) -> None:
        """将缓冲区数据写入 Parquet 文件"""
        if not self._buffer:
            return

        data_to_write = self._buffer
        self._buffer = []
        self._buffer_size = 0

        filepath = self._generate_filename(metadata)

        # 在线程池中执行IO密集操作
        loop = asyncio.get_event_loop()
        written_bytes = await loop.run_in_executor(
            None, self._write_parquet_sync, data_to_write, filepath
        )

        self._file_count += 1
        self._total_records += len(data_to_write)
        self._stats["files_written"] += 1
        self._stats["records_written"] += len(data_to_write)
        self._stats["bytes_written"] += written_bytes

        logger.debug(
            f"ParquetSink: 写入 {filepath} "
            f"(records={len(data_to_write)}, size={written_bytes / 1024 / 1024:.2f}MB)"
        )

    def _write_parquet_sync(self, records: list[dict], filepath: str) -> int:
        """同步写入Parquet文件（在线程池中调用）"""
        try:
            import pyarrow as pa
            import pyarrow.parquet as pq

            table = pa.Table.from_pylist(records)

            # Parquet内部压缩（不需要外部压缩）
            compression_map = {
                CompressionFormat.NONE: "NONE",
                CompressionFormat.GZIP: "GZIP",
                CompressionFormat.LZ4: "LZ4",
                CompressionFormat.ZSTD: "ZSTD",
                CompressionFormat.SNAPPY: "SNAPPY",
            }

            writer_args: dict[str, Any] = {
                "compression": compression_map.get(self.compression, "NONE"),
                "version": "2.6",
                "data_page_version": "2.0",
                "use_dictionary": True,
                "write_statistics": True,
            }
            if self.compression != CompressionFormat.NONE:
                writer_args["compression_level"] = self.compression_level

            buf = pa.BufferOutputStream()
            pq.write_table(table, buf, **writer_args)
            parquet_data = buf.getvalue().to_pybytes()

            # 原子写入
            temp_path = filepath + ".tmp"
            with open(temp_path, "wb") as f:
                f.write(parquet_data)
            os.replace(temp_path, filepath)

            # 清理
            del records
            gc.collect()

            return len(parquet_data)

        except ImportError:
            logger.error("ParquetSink: pyarrow 未安装。请运行: pip install pyarrow")
            # 降级为 JSONL
            return self._write_jsonl_fallback(records, filepath)

    def _write_jsonl_fallback(self, records: list[dict], filepath: str) -> int:
        """PyArrow 不可用时降级为 JSONL 写入"""
        jsonl_path = filepath.replace(".parquet", ".jsonl")
        data = "\n".join(json.dumps(r, ensure_ascii=False) for r in records).encode("utf-8")

        if self.compression != CompressionFormat.NONE:
            data = compress_data(data, self.compression)
            jsonl_path += f".{self.compression.value}"

        with open(jsonl_path, "wb") as f:
            f.write(data)

        logger.warning(f"ParquetSink: 降级写入 JSONL: {jsonl_path}")
        return len(data)

    def get_stats(self) -> dict:
        """获取写入统计"""
        elapsed = time.time() - self._stats["start_time"]
        return {
            **self._stats,
            "elapsed_seconds": round(elapsed, 1),
            "records_per_second": round(self._stats["records_written"] / max(elapsed, 0.01), 1),
        }

    async def close(self) -> None:
        """关闭Sink，刷写剩余数据"""
        async with self._lock:
            if self._buffer:
                await self._flush({"project_id": "default"})
        logger.info(
            f"ParquetSink: 已关闭 "
            f"(files={self._stats['files_written']}, "
            f"records={self._stats['records_written']})"
        )
