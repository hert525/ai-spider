"""SmartScraper graph - LLM direct extraction without code generation."""
from __future__ import annotations

from .base import BaseGraph
from src.engine.nodes import FetchNode, ParseNode, ExtractNode


class SmartScraperGraph(BaseGraph):
    """Fetch → Parse → LLM Extract structured data directly."""

    def __init__(self, use_browser: bool = False, proxy_config: dict | None = None):
        super().__init__(
            nodes=[
                FetchNode(use_browser=use_browser, proxy_config=proxy_config),
                ParseNode(),
                ExtractNode(),
            ],
            graph_name="SmartScraper",
        )

    async def run(self, url: str, description: str) -> dict:
        """Convenience method to run the graph.
        
        Returns:
            dict with 'extracted_data', 'clean_text', etc.
        """
        state = await self.execute({
            "url": url,
            "description": description,
        })
        return state
