"""CodeGenerator graph - Generate code + 4-round validation."""
from __future__ import annotations

from .base import BaseGraph
from src.engine.nodes import FetchNode, ParseNode, GenerateNode, ValidateNode


class CodeGeneratorGraph(BaseGraph):
    """Fetch → Parse → Generate Code → 4-round Validate."""

    def __init__(self, use_browser: bool = False, max_retries: int = 3, proxy_config: dict | None = None):
        super().__init__(
            nodes=[
                FetchNode(use_browser=use_browser, proxy_config=proxy_config),
                ParseNode(),
                GenerateNode(),
                ValidateNode(max_retries=max_retries),
            ],
            graph_name="CodeGenerator",
        )

    async def run(self, url: str, description: str) -> dict:
        """Generate and validate crawler code.
        
        Returns:
            dict with 'generated_code', 'validation_status', etc.
        """
        state = await self.execute({
            "url": url,
            "description": description,
        })
        return state
