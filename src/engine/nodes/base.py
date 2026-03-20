"""Base node for the DAG execution engine."""
from abc import ABC, abstractmethod
from typing import Any
from loguru import logger


class BaseNode(ABC):
    """Base class for all DAG nodes."""

    def __init__(self, node_name: str = "BaseNode"):
        self.node_name = node_name
        self.logger = logger.bind(node=node_name)

    @abstractmethod
    async def execute(self, state: dict) -> dict:
        """Execute this node's logic, reading/writing from state dict."""
        ...

    def __repr__(self):
        return f"<{self.__class__.__name__}:{self.node_name}>"
