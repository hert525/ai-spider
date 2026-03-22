"""
内存去重器 - 基于集合 + 可选布隆过滤器。

适用场景：单机中小规模去重，无需外部依赖。
从 wukong/dedup/memory_deduper.py 移植并适配 async 接口。
"""
from __future__ import annotations

import threading
from collections import OrderedDict
from typing import Any

from loguru import logger

from src.engine.dedup.base import BaseDeduper


class MemoryDeduper(BaseDeduper):
    """
    内存去重器。

    支持两种模式：
    - set模式：精确去重，使用 Python set
    - lru模式：带 LRU 淘汰的去重，限制最大内存使用

    Args:
        capacity: 最大容量（超过后触发 LRU 淘汰）
        use_bloom: 是否启用布隆过滤器加速（需要 rbloom 库）
        bloom_error_rate: 布隆过滤器误判率
    """

    def __init__(
        self,
        capacity: int = 1_000_000,
        use_bloom: bool = False,
        bloom_error_rate: float = 0.001,
    ):
        self.capacity = capacity
        self.use_bloom = use_bloom
        self._lock = threading.Lock()

        # 布隆过滤器（可选）
        self._bloom = None
        if use_bloom:
            try:
                from rbloom import Bloom
                self._bloom = Bloom(capacity, bloom_error_rate)
                logger.info(f"MemoryDeduper: 布隆过滤器已启用 (容量={capacity}, 误判率={bloom_error_rate})")
            except ImportError:
                logger.warning("MemoryDeduper: rbloom 未安装，回退到纯集合模式")

        # LRU有序字典
        self._store: OrderedDict[str, bool] = OrderedDict()

    async def exists(self, key: str, **kwargs: Any) -> bool:
        """检查key是否存在"""
        with self._lock:
            # 布隆过滤器快速判断
            if self._bloom is not None:
                if key not in self._bloom:
                    return False
            # 精确检查
            if key in self._store:
                # 移动到末尾（最近使用）
                self._store.move_to_end(key)
                return True
            return False

    async def add(self, key: str, **kwargs: Any) -> bool:
        """添加key到去重集合"""
        with self._lock:
            if key in self._store:
                self._store.move_to_end(key)
                return True

            # 容量检查，超出时淘汰最久未使用的
            while len(self._store) >= self.capacity:
                evicted_key, _ = self._store.popitem(last=False)
                logger.debug(f"MemoryDeduper: LRU淘汰 key={evicted_key[:32]}...")

            self._store[key] = True

            if self._bloom is not None:
                self._bloom.add(key)

            return True

    @property
    def size(self) -> int:
        """当前已存储的key数量"""
        return len(self._store)

    async def clear(self) -> None:
        """清空所有数据"""
        with self._lock:
            self._store.clear()
            if self._bloom is not None and self.use_bloom:
                try:
                    from rbloom import Bloom
                    self._bloom = Bloom(self.capacity, 0.001)
                except ImportError:
                    pass
