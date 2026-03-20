"""DeepCrawler graph - BFS/DFS deep crawling."""
import asyncio
from urllib.parse import urljoin, urlparse
from loguru import logger
from src.engine.nodes import FetchNode, ParseNode, ExtractNode
from src.core.config import settings


class DeepCrawlerGraph:
    """Deep crawl a site using BFS/DFS, extracting data from each page."""

    def __init__(self, max_pages: int = 10, mode: str = "bfs", use_browser: bool = False):
        self.max_pages = max_pages
        self.mode = mode  # "bfs" or "dfs"
        self.use_browser = use_browser
        self.fetch_node = FetchNode(use_browser=use_browser)
        self.parse_node = ParseNode()
        self.extract_node = ExtractNode()

    async def run(self, start_url: str, description: str, url_pattern: str = "") -> dict:
        """Crawl starting from start_url, collecting data from each page.
        
        Args:
            start_url: Starting URL
            description: What data to extract
            url_pattern: Optional regex pattern to filter URLs
            
        Returns:
            dict with 'all_data', 'pages_crawled', 'urls_visited'
        """
        visited = set()
        queue = [start_url]
        all_data = []
        base_domain = urlparse(start_url).netloc

        import re
        pattern = re.compile(url_pattern) if url_pattern else None

        while queue and len(visited) < self.max_pages:
            if self.mode == "bfs":
                url = queue.pop(0)
            else:
                url = queue.pop()

            if url in visited:
                continue
            visited.add(url)

            try:
                state = {"url": url, "description": description}
                state = await self.fetch_node.execute(state)
                state = await self.parse_node.execute(state)
                state = await self.extract_node.execute(state)

                extracted = state.get("extracted_data", [])
                if isinstance(extracted, list):
                    all_data.extend(extracted)
                else:
                    all_data.append(extracted)

                # Collect new links
                for link in state.get("links", []):
                    href = link.get("href", "")
                    abs_url = urljoin(url, href)
                    parsed = urlparse(abs_url)
                    # Same domain only
                    if parsed.netloc == base_domain and abs_url not in visited:
                        if pattern is None or pattern.search(abs_url):
                            queue.append(abs_url)

                logger.info(f"Deep crawl: {len(visited)}/{self.max_pages} pages, {len(all_data)} items")

                # Polite delay
                await asyncio.sleep(settings.default_delay)

            except Exception as e:
                logger.warning(f"Error crawling {url}: {e}")

        return {
            "all_data": all_data,
            "pages_crawled": len(visited),
            "urls_visited": list(visited),
        }
