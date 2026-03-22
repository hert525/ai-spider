"""
滚动分区布隆过滤器去重器 - 支持持久化和自动轮换。

适用场景：超大规模持续去重，分区轮换避免布隆过滤器溢出。
从 wukong/dedup/rotation_deduper.py 移植并适配 async 接口。
"""
from __future__ import annotations

import asyncio
import hashlib
import math
import os
import pickle
import threading
import time
from pathlib import Path
from typing import Any

from loguru import logger

from src.engine.dedup.base import BaseDeduper


class BloomPartition:
    """单个布隆过滤器分区（线程安全，支持持久化）"""

    def __init__(
        self,
        partition_id: int,
        max_elements: int = 500_000_000,
        error_rate: float = 0.0001,
        storage_path: str | None = None,
    ):
        self.partition_id = partition_id
        self.max_elements = max_elements
        self.error_rate = error_rate
        self.element_count = 0
        self.storage_path = Path(storage_path) if storage_path else None
        self._lock = threading.RLock()

        # 计算布隆过滤器最优参数
        self.bit_array_size = math.ceil(-(max_elements * math.log(error_rate)) / (math.log(2) ** 2))
        self.num_hashes = max(1, math.ceil((self.bit_array_size / max_elements) * math.log(2)))

        # 使用 bytearray 实现位数组
        self._bits = bytearray(math.ceil(self.bit_array_size / 8))

        # 从磁盘加载（如果存在）
        if self.storage_path and self.storage_path.exists():
            self._load_from_disk()

    def _get_positions(self, key: str) -> list[int]:
        """双重哈希计算位置"""
        h1 = int(hashlib.md5(key.encode()).hexdigest(), 16)
        h2 = int(hashlib.sha1(key.encode()).hexdigest(), 16)
        return [(h1 + i * h2) % self.bit_array_size for i in range(self.num_hashes)]

    def add(self, key: str) -> bool:
        """添加元素到分区"""
        with self._lock:
            if self.element_count >= self.max_elements:
                return False
            positions = self._get_positions(key)
            for pos in positions:
                byte_idx = pos >> 3
                bit_idx = pos & 7
                self._bits[byte_idx] |= (1 << bit_idx)
            self.element_count += 1
            return True

    def contains(self, key: str) -> bool:
        """检查元素是否存在"""
        with self._lock:
            positions = self._get_positions(key)
            return all(
                bool(self._bits[pos >> 3] & (1 << (pos & 7)))
                for pos in positions
            )

    def persist(self) -> None:
        """将分区状态持久化到磁盘"""
        if not self.storage_path:
            return
        with self._lock:
            temp_path = self.storage_path.with_suffix(".tmp")
            try:
                with open(temp_path, "wb") as f:
                    pickle.dump({
                        "bits": bytes(self._bits),
                        "element_count": self.element_count,
                        "config": {
                            "max_elements": self.max_elements,
                            "error_rate": self.error_rate,
                        },
                        "timestamp": time.time(),
                    }, f)
                temp_path.replace(self.storage_path)
            except Exception as e:
                logger.error(f"分区 {self.partition_id} 持久化失败: {e}")

    def _load_from_disk(self) -> None:
        """从磁盘加载分区状态"""
        try:
            with open(self.storage_path, "rb") as f:
                data = pickle.load(f)
            # 配置校验
            if (data["config"]["max_elements"] != self.max_elements or
                    data["config"]["error_rate"] != self.error_rate):
                logger.warning(f"分区 {self.partition_id} 配置不匹配，重置")
                self.reset()
                return
            self._bits = bytearray(data["bits"])
            self.element_count = data["element_count"]
            logger.debug(f"分区 {self.partition_id} 已加载 ({self.element_count:,} 个元素)")
        except Exception as e:
            logger.error(f"分区 {self.partition_id} 加载失败: {e}")
            self.reset()

    def reset(self) -> None:
        """重置分区"""
        with self._lock:
            self._bits = bytearray(math.ceil(self.bit_array_size / 8))
            self.element_count = 0


class RotationDeduper(BaseDeduper):
    """
    滚动分区布隆过滤器去重器。

    特性：
    - 多分区轮换：当前分区满后自动切换到下一个
    - 持久化：定期将状态写入磁盘，重启不丢失
    - 适合持续运行的大规模爬虫

    Args:
        partitions: 分区数量
        max_elements_per_partition: 每个分区的最大元素数
        error_rate: 误判率
        storage_dir: 持久化存储目录
        persist_interval: 持久化间隔（秒）
    """

    def __init__(
        self,
        partitions: int = 20,
        max_elements_per_partition: int = 500_000_000,
        error_rate: float = 0.0001,
        storage_dir: str = "data/dedup_persist",
        persist_interval: int = 300,
    ):
        self.partition_count = partitions
        self.max_elements = max_elements_per_partition
        self.error_rate = error_rate
        self.storage_dir = Path(storage_dir).absolute()
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.persist_interval = persist_interval

        # 初始化分区
        self.partitions = [
            BloomPartition(
                partition_id=i,
                max_elements=max_elements_per_partition,
                error_rate=error_rate,
                storage_path=str(self.storage_dir / f"partition_{i}.bf"),
            )
            for i in range(partitions)
        ]

        # 加载元数据（当前分区索引）
        self._meta_path = self.storage_dir / "rotation_meta.pkl"
        self._meta_lock = threading.RLock()
        self.current_partition_idx = 0
        self._load_meta()

        # 后台持久化任务
        self._persist_task: asyncio.Task | None = None
        self._shutdown_event = asyncio.Event()

        logger.info(
            f"RotationDeduper: 初始化完成 "
            f"(分区={partitions}, 每分区={max_elements_per_partition:,}, "
            f"存储={self.storage_dir})"
        )

    def _save_meta(self) -> None:
        """保存元数据"""
        with self._meta_lock:
            temp_path = self._meta_path.with_suffix(".tmp")
            with open(temp_path, "wb") as f:
                pickle.dump({
                    "current_partition_idx": self.current_partition_idx,
                    "config": {
                        "partitions": self.partition_count,
                        "max_elements": self.max_elements,
                        "error_rate": self.error_rate,
                    },
                }, f)
            temp_path.replace(self._meta_path)

    def _load_meta(self) -> None:
        """加载元数据"""
        if not self._meta_path.exists():
            return
        try:
            with open(self._meta_path, "rb") as f:
                meta = pickle.load(f)
            if (meta["config"]["partitions"] != self.partition_count or
                    meta["config"]["max_elements"] != self.max_elements):
                logger.warning("RotationDeduper: 元数据配置不匹配，重置")
                self.current_partition_idx = 0
            else:
                self.current_partition_idx = meta["current_partition_idx"]
                logger.debug(f"RotationDeduper: 加载元数据，当前分区={self.current_partition_idx}")
        except Exception as e:
            logger.error(f"RotationDeduper: 元数据加载失败: {e}")
            self.current_partition_idx = 0

    async def exists(self, key: str, **kwargs: Any) -> bool:
        """检查key是否在任意分区中存在"""
        for partition in self.partitions:
            if partition.contains(key):
                return True
        return False

    async def add(self, key: str, **kwargs: Any) -> bool:
        """添加key到当前活跃分区"""
        current = self.partitions[self.current_partition_idx]
        if not current.add(key):
            # 当前分区已满，执行轮换
            self._rotate()
            return await self.add(key)
        return True

    def _rotate(self) -> None:
        """轮换到下一个分区"""
        with self._meta_lock:
            old_idx = self.current_partition_idx
            next_idx = (old_idx + 1) % self.partition_count

            logger.info(f"RotationDeduper: 分区轮换 {old_idx} → {next_idx}")

            # 持久化当前分区
            self.partitions[old_idx].persist()

            # 重置下一个分区
            if self.partitions[next_idx].element_count > 0:
                self.partitions[next_idx].reset()

            self.current_partition_idx = next_idx
            self._save_meta()

    async def start_persistence(self) -> None:
        """启动后台持久化任务"""
        async def _persist_loop():
            while not self._shutdown_event.is_set():
                try:
                    await asyncio.sleep(self.persist_interval)
                    if self._shutdown_event.is_set():
                        break
                    # 在线程池中执行持久化（避免阻塞事件循环）
                    loop = asyncio.get_event_loop()
                    await loop.run_in_executor(None, self._persist_all)
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"RotationDeduper: 持久化失败: {e}")

        self._persist_task = asyncio.create_task(_persist_loop())
        logger.info(f"RotationDeduper: 后台持久化已启动 (间隔={self.persist_interval}s)")

    def _persist_all(self) -> None:
        """持久化所有分区和元数据"""
        for partition in self.partitions:
            partition.persist()
        self._save_meta()

    async def close(self) -> None:
        """优雅关闭：停止后台任务并执行最终持久化"""
        self._shutdown_event.set()
        if self._persist_task:
            self._persist_task.cancel()
            try:
                await self._persist_task
            except asyncio.CancelledError:
                pass

        # 最终持久化
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._persist_all)
        logger.info("RotationDeduper: 已关闭并完成最终持久化")
