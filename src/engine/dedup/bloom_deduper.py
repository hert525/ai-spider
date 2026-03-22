"""
布隆过滤器去重器 - 基于内存的大规模去重方案。

适用场景：超大规模去重（亿级），内存友好，允许极低误判率。
从 wukong/dedup/memory_deduper.py (Bloom部分) 移植。
"""
from __future__ import annotations

import asyncio
import hashlib
import math
import threading
from typing import Any

from loguru import logger

from src.engine.dedup.base import BaseDeduper


class BloomFilterDeduper(BaseDeduper):
    """
    布隆过滤器去重器。

    使用自实现的位数组布隆过滤器，支持：
    - 亿级元素去重
    - 可配置误判率
    - 内存高效（1亿元素约120MB @ 0.01%误判率）
    - 线程安全

    Args:
        capacity: 预期最大元素数
        error_rate: 误判率（越低越耗内存）
    """

    def __init__(
        self,
        capacity: int = 100_000_000,
        error_rate: float = 0.0001,
    ):
        self.capacity = capacity
        self.error_rate = error_rate
        self._lock = threading.Lock()
        self._count = 0

        # 计算最优参数
        self._bit_size = self._calc_bit_size(capacity, error_rate)
        self._num_hashes = self._calc_num_hashes(self._bit_size, capacity)

        # 使用 bytearray 作为位数组
        self._bits = bytearray(math.ceil(self._bit_size / 8))

        logger.info(
            f"BloomFilterDeduper: 初始化完成 "
            f"(容量={capacity:,}, 误判率={error_rate}, "
            f"位数组={self._bit_size:,}位/{self._bit_size // 8 // 1024 // 1024}MB, "
            f"哈希函数={self._num_hashes}个)"
        )

    @staticmethod
    def _calc_bit_size(n: int, p: float) -> int:
        """计算最优位数组大小: m = -(n * ln(p)) / (ln(2)^2)"""
        return math.ceil(-(n * math.log(p)) / (math.log(2) ** 2))

    @staticmethod
    def _calc_num_hashes(m: int, n: int) -> int:
        """计算最优哈希函数数量: k = (m/n) * ln(2)"""
        return max(1, math.ceil((m / n) * math.log(2)))

    def _get_positions(self, key: str) -> list[int]:
        """计算 key 在位数组中的多个位置（使用双重哈希）"""
        h1 = int(hashlib.md5(key.encode()).hexdigest(), 16)
        h2 = int(hashlib.sha1(key.encode()).hexdigest(), 16)
        return [(h1 + i * h2) % self._bit_size for i in range(self._num_hashes)]

    def _check_bit(self, pos: int) -> bool:
        """检查位数组中指定位是否为1"""
        byte_idx = pos >> 3  # pos // 8
        bit_idx = pos & 7     # pos % 8
        return bool(self._bits[byte_idx] & (1 << bit_idx))

    def _set_bit(self, pos: int) -> None:
        """设置位数组中指定位为1"""
        byte_idx = pos >> 3
        bit_idx = pos & 7
        self._bits[byte_idx] |= (1 << bit_idx)

    async def exists(self, key: str, **kwargs: Any) -> bool:
        """检查key是否可能存在"""
        with self._lock:
            positions = self._get_positions(key)
            return all(self._check_bit(pos) for pos in positions)

    async def add(self, key: str, **kwargs: Any) -> bool:
        """添加key到布隆过滤器"""
        with self._lock:
            if self._count >= self.capacity:
                logger.warning(f"BloomFilterDeduper: 已达容量上限 {self.capacity:,}")
                return False

            positions = self._get_positions(key)
            for pos in positions:
                self._set_bit(pos)
            self._count += 1
            return True

    @property
    def size(self) -> int:
        """当前已添加的元素数"""
        return self._count

    @property
    def fill_ratio(self) -> float:
        """位数组填充率"""
        set_bits = sum(bin(byte).count('1') for byte in self._bits)
        return set_bits / self._bit_size if self._bit_size > 0 else 0.0
