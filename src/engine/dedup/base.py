"""去重基类 - 定义统一的去重接口"""
from __future__ import annotations

import hashlib
from abc import ABC, abstractmethod
from typing import Any


class BaseDeduper(ABC):
    """
    去重器基类。

    所有去重策略必须实现 exists() 和 add() 两个异步方法。
    """

    @abstractmethod
    async def exists(self, key: str, **kwargs: Any) -> bool:
        """
        检查 key 是否已存在（已被处理过）。

        Args:
            key: 去重键（URL、内容hash等）

        Returns:
            True 表示已存在（重复），False 表示不存在（新数据）
        """
        ...

    @abstractmethod
    async def add(self, key: str, **kwargs: Any) -> bool:
        """
        将 key 加入去重集合。

        Args:
            key: 去重键

        Returns:
            True 表示添加成功
        """
        ...

    async def exists_and_add(self, key: str, **kwargs: Any) -> bool:
        """
        原子性地检查并添加（如不存在则添加）。

        Returns:
            True 表示已存在（重复），False 表示新数据且已添加
        """
        if await self.exists(key, **kwargs):
            return True
        await self.add(key, **kwargs)
        return False

    @staticmethod
    def hash_key(content: str) -> str:
        """生成内容的SHA256哈希值作为去重键"""
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    @staticmethod
    def url_key(url: str) -> str:
        """标准化URL作为去重键"""
        # 去掉尾部斜杠和查询参数中的随机token
        url = url.rstrip("/")
        return hashlib.md5(url.encode("utf-8")).hexdigest()

    async def close(self) -> None:
        """释放资源（子类可按需重写）"""
        pass
