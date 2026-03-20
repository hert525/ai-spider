"""Base graph for DAG workflow execution."""
import time
from typing import Any
from loguru import logger
from src.engine.nodes.base import BaseNode


class BaseGraph:
    """DAG execution engine - executes nodes sequentially."""

    def __init__(self, nodes: list[BaseNode], graph_name: str = "BaseGraph"):
        self.nodes = nodes
        self.graph_name = graph_name

    async def execute(self, initial_state: dict) -> dict:
        """Execute all nodes in sequence, passing state through."""
        state = dict(initial_state)
        start = time.monotonic()
        
        logger.info(f"▶ Starting graph: {self.graph_name} ({len(self.nodes)} nodes)")
        
        for node in self.nodes:
            node_start = time.monotonic()
            try:
                state = await node.execute(state)
                elapsed = int((time.monotonic() - node_start) * 1000)
                logger.info(f"  ✓ {node.node_name} ({elapsed}ms)")
            except Exception as e:
                elapsed = int((time.monotonic() - node_start) * 1000)
                logger.error(f"  ✗ {node.node_name} failed ({elapsed}ms): {e}")
                state["error"] = str(e)
                state["error_node"] = node.node_name
                raise

        total = int((time.monotonic() - start) * 1000)
        logger.info(f"✓ Graph {self.graph_name} completed ({total}ms)")
        state["_exec_time_ms"] = total
        return state
