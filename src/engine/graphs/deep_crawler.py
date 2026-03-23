"""DeepCrawler graph - Production-grade BFS/DFS deep crawling.

Features:
- URL Frontier with priority queue (important pages first)
- robots.txt compliance
- Sitemap discovery & parsing
- Incremental crawling (skip already-seen URLs via dedup)
- Depth control
- Page type detection (list vs detail)
- Politeness: per-domain concurrency + delay
- Checkpoint/resume support
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import re
import time
from dataclasses import dataclass, field
from datetime import datetime
from urllib.parse import urljoin, urlparse

from loguru import logger

from src.core.config import settings
from src.engine.nodes import FetchNode, ParseNode, ExtractNode


# ── URL Frontier ──

@dataclass(order=True)
class URLItem:
    """Prioritized URL for the frontier."""
    priority: int
    url: str = field(compare=False)
    depth: int = field(compare=False, default=0)
    parent_url: str = field(compare=False, default="")
    page_type: str = field(compare=False, default="unknown")  # list, detail, unknown


class URLFrontier:
    """Priority-based URL frontier with dedup."""

    def __init__(self, max_size: int = 10000):
        self._queue: list[URLItem] = []
        self._seen: set[str] = set()
        self.max_size = max_size

    def add(self, url: str, priority: int = 5, depth: int = 0,
            parent_url: str = "", page_type: str = "unknown") -> bool:
        """Add URL if not already seen. Returns True if added."""
        normalized = self._normalize(url)
        if normalized in self._seen or len(self._queue) >= self.max_size:
            return False
        self._seen.add(normalized)
        item = URLItem(priority=priority, url=url, depth=depth,
                       parent_url=parent_url, page_type=page_type)
        # Simple priority insert (heap would be better for large queues)
        self._queue.append(item)
        self._queue.sort()
        return True

    def pop(self) -> URLItem | None:
        return self._queue.pop(0) if self._queue else None

    def is_seen(self, url: str) -> bool:
        return self._normalize(url) in self._seen

    def mark_seen(self, url: str) -> None:
        self._seen.add(self._normalize(url))

    @property
    def size(self) -> int:
        return len(self._queue)

    @property
    def total_seen(self) -> int:
        return len(self._seen)

    @staticmethod
    def _normalize(url: str) -> str:
        """Normalize URL for dedup (strip fragment, trailing slash)."""
        parsed = urlparse(url)
        path = parsed.path.rstrip("/") or "/"
        return f"{parsed.scheme}://{parsed.netloc}{path}?{parsed.query}" if parsed.query else f"{parsed.scheme}://{parsed.netloc}{path}"


# ── Robots.txt Parser ──

class RobotsChecker:
    """Simple robots.txt parser."""

    def __init__(self):
        self._rules: dict[str, list[tuple[str, str]]] = {}  # domain -> [(allow/disallow, path)]
        self._sitemaps: dict[str, list[str]] = {}  # domain -> [sitemap_urls]
        self._crawl_delays: dict[str, float] = {}

    async def fetch_robots(self, base_url: str) -> None:
        """Fetch and parse robots.txt for a domain."""
        import httpx
        parsed = urlparse(base_url)
        domain = parsed.netloc
        if domain in self._rules:
            return

        robots_url = f"{parsed.scheme}://{domain}/robots.txt"
        rules: list[tuple[str, str]] = []
        sitemaps: list[str] = []
        delay = 0.0

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(robots_url, follow_redirects=True)
                if resp.status_code == 200:
                    current_agent = False
                    for line in resp.text.splitlines():
                        line = line.strip()
                        if line.startswith("#") or not line:
                            continue
                        key, _, value = line.partition(":")
                        key = key.strip().lower()
                        value = value.strip()

                        if key == "user-agent":
                            current_agent = value == "*" or "spider" in value.lower()
                        elif current_agent:
                            if key == "disallow" and value:
                                rules.append(("disallow", value))
                            elif key == "allow" and value:
                                rules.append(("allow", value))
                            elif key == "crawl-delay":
                                try:
                                    delay = float(value)
                                except ValueError:
                                    pass
                        if key == "sitemap":
                            sitemaps.append(value)
        except Exception as e:
            logger.debug(f"robots.txt fetch failed for {domain}: {e}")

        self._rules[domain] = rules
        self._sitemaps[domain] = sitemaps
        self._crawl_delays[domain] = delay
        logger.info(f"robots.txt for {domain}: {len(rules)} rules, {len(sitemaps)} sitemaps, delay={delay}")

    def is_allowed(self, url: str) -> bool:
        """Check if URL is allowed by robots.txt."""
        parsed = urlparse(url)
        domain = parsed.netloc
        rules = self._rules.get(domain, [])
        if not rules:
            return True

        path = parsed.path
        # Check most specific match (longer path wins)
        allowed = True
        best_len = 0
        for action, pattern in rules:
            if path.startswith(pattern) and len(pattern) >= best_len:
                best_len = len(pattern)
                allowed = action == "allow"
        return allowed

    def get_sitemaps(self, base_url: str) -> list[str]:
        domain = urlparse(base_url).netloc
        return self._sitemaps.get(domain, [])

    def get_crawl_delay(self, base_url: str) -> float:
        domain = urlparse(base_url).netloc
        return self._crawl_delays.get(domain, 0.0)


# ── Sitemap Parser ──

async def parse_sitemap(sitemap_url: str, max_urls: int = 500) -> list[str]:
    """Parse a sitemap XML and return URLs."""
    import httpx
    urls: list[str] = []
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(sitemap_url, follow_redirects=True)
            if resp.status_code != 200:
                return urls

            content = resp.text
            # Simple XML parsing (avoid lxml dependency)
            # Handle sitemap index
            if "<sitemapindex" in content:
                for match in re.finditer(r"<loc>\s*(.*?)\s*</loc>", content):
                    sub_url = match.group(1).strip()
                    if len(urls) >= max_urls:
                        break
                    sub_urls = await parse_sitemap(sub_url, max_urls - len(urls))
                    urls.extend(sub_urls)
            else:
                for match in re.finditer(r"<loc>\s*(.*?)\s*</loc>", content):
                    urls.append(match.group(1).strip())
                    if len(urls) >= max_urls:
                        break
    except Exception as e:
        logger.debug(f"Sitemap parse failed {sitemap_url}: {e}")
    return urls


# ── Page Type Detector ──

def detect_page_type(url: str, html: str = "", links_count: int = 0) -> str:
    """Heuristic detection: is this a list page or detail page?"""
    path = urlparse(url).path.lower()

    # URL pattern heuristics
    list_patterns = [r"/list", r"/index", r"/page/\d", r"/category", r"/tag/",
                     r"/search", r"\?page=", r"/p/\d", r"/archive"]
    detail_patterns = [r"/detail", r"/article/", r"/post/", r"/item/",
                       r"/product/", r"/news/\d", r"/\d{4}/\d{2}/"]

    for p in list_patterns:
        if re.search(p, path + ("?" + urlparse(url).query if urlparse(url).query else "")):
            return "list"
    for p in detail_patterns:
        if re.search(p, path):
            return "detail"

    # Links count heuristic: many outgoing links = list page
    if links_count > 20:
        return "list"
    elif links_count < 5:
        return "detail"

    return "unknown"


# ── Checkpoint ──

class CrawlCheckpoint:
    """Save/restore crawl progress for resume."""

    def __init__(self, checkpoint_dir: str = ""):
        self.checkpoint_dir = checkpoint_dir

    def save(self, crawl_id: str, state: dict) -> None:
        if not self.checkpoint_dir:
            return
        import os
        os.makedirs(self.checkpoint_dir, exist_ok=True)
        path = f"{self.checkpoint_dir}/{crawl_id}.json"
        with open(path, "w") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)

    def load(self, crawl_id: str) -> dict | None:
        if not self.checkpoint_dir:
            return None
        path = f"{self.checkpoint_dir}/{crawl_id}.json"
        try:
            with open(path) as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return None

    def delete(self, crawl_id: str) -> None:
        if not self.checkpoint_dir:
            return
        import os
        path = f"{self.checkpoint_dir}/{crawl_id}.json"
        try:
            os.remove(path)
        except FileNotFoundError:
            pass


# ── Main Deep Crawler ──

class DeepCrawlerGraph:
    """Production-grade deep crawler with URL frontier, robots.txt, sitemap, and checkpointing.

    Args:
        max_pages: Maximum pages to crawl
        max_depth: Maximum link depth from start URL (0=unlimited)
        mode: "bfs" (breadth-first) or "dfs" (depth-first)
        respect_robots: Whether to obey robots.txt
        use_sitemap: Whether to discover URLs from sitemap
        incremental: Skip URLs already in dedup store
        use_browser: Use browser for JS-rendered pages
        proxy_config: Proxy configuration
        checkpoint_dir: Directory for saving crawl checkpoints
        domain_concurrency: Max concurrent requests per domain
    """

    def __init__(
        self,
        max_pages: int = 50,
        max_depth: int = 3,
        mode: str = "bfs",
        respect_robots: bool = True,
        use_sitemap: bool = True,
        incremental: bool = False,
        use_browser: bool = False,
        proxy_config: dict | None = None,
        checkpoint_dir: str = "",
        domain_concurrency: int = 2,
    ):
        self.max_pages = max_pages
        self.max_depth = max_depth
        self.mode = mode
        self.respect_robots = respect_robots
        self.use_sitemap = use_sitemap
        self.incremental = incremental
        self.domain_concurrency = domain_concurrency

        self.fetch_node = FetchNode(use_browser=use_browser, proxy_config=proxy_config)
        self.parse_node = ParseNode()
        self.extract_node = ExtractNode()

        self.robots = RobotsChecker()
        self.frontier = URLFrontier(max_size=max_pages * 10)
        self.checkpoint = CrawlCheckpoint(checkpoint_dir)

        # Stats
        self.stats = {
            "pages_crawled": 0,
            "pages_failed": 0,
            "data_items": 0,
            "urls_discovered": 0,
            "urls_filtered_robots": 0,
            "urls_filtered_depth": 0,
            "urls_filtered_dedup": 0,
            "start_time": 0,
            "elapsed_seconds": 0,
        }

    async def run(self, start_url: str, description: str,
                  url_pattern: str = "", crawl_id: str = "") -> dict:
        """Run deep crawl.

        Args:
            start_url: Starting URL
            description: What data to extract from each page
            url_pattern: Optional regex to filter discovered URLs
            crawl_id: Optional ID for checkpoint resume

        Returns:
            dict with all_data, pages_crawled, stats, etc.
        """
        self.stats["start_time"] = time.time()
        base_domain = urlparse(start_url).netloc
        pattern = re.compile(url_pattern) if url_pattern else None
        all_data: list[dict] = []
        visited_urls: list[str] = []

        # Resume from checkpoint?
        if crawl_id:
            saved = self.checkpoint.load(crawl_id)
            if saved:
                all_data = saved.get("all_data", [])
                for u in saved.get("visited", []):
                    self.frontier.mark_seen(u)
                visited_urls = saved.get("visited", [])
                self.stats = saved.get("stats", self.stats)
                logger.info(f"Resumed crawl {crawl_id}: {len(visited_urls)} pages already done")

        # Robots.txt
        if self.respect_robots:
            await self.robots.fetch_robots(start_url)
            crawl_delay = self.robots.get_crawl_delay(start_url)
            if crawl_delay > 0:
                logger.info(f"Respecting crawl-delay: {crawl_delay}s")

        # Sitemap URLs
        if self.use_sitemap:
            sitemaps = self.robots.get_sitemaps(start_url)
            if not sitemaps:
                # Try common sitemap paths
                parsed = urlparse(start_url)
                sitemaps = [f"{parsed.scheme}://{parsed.netloc}/sitemap.xml"]

            for sm_url in sitemaps[:3]:  # Max 3 sitemaps
                sm_urls = await parse_sitemap(sm_url, max_urls=self.max_pages * 2)
                for u in sm_urls:
                    if urlparse(u).netloc == base_domain:
                        if pattern is None or pattern.search(u):
                            self.frontier.add(u, priority=3, depth=1, page_type="detail")
                if sm_urls:
                    logger.info(f"Sitemap {sm_url}: discovered {len(sm_urls)} URLs")

        # Seed the frontier
        self.frontier.add(start_url, priority=1, depth=0, page_type="list")

        # Incremental dedup
        dedup = None
        if self.incremental:
            try:
                from src.engine.dedup import get_deduper
                dedup = get_deduper()
            except Exception:
                logger.warning("Incremental mode: dedup not available, falling back to in-memory")

        # ── Main crawl loop ──
        sem = asyncio.Semaphore(self.domain_concurrency)

        while self.frontier.size > 0 and self.stats["pages_crawled"] < self.max_pages:
            item = self.frontier.pop()
            if item is None:
                break

            url = item.url
            depth = item.depth

            # Depth check
            if self.max_depth > 0 and depth > self.max_depth:
                self.stats["urls_filtered_depth"] += 1
                continue

            # Robots check
            if self.respect_robots and not self.robots.is_allowed(url):
                self.stats["urls_filtered_robots"] += 1
                continue

            # Incremental dedup check
            if dedup:
                url_hash = hashlib.md5(url.encode()).hexdigest()
                if await dedup.is_duplicate(url_hash):
                    self.stats["urls_filtered_dedup"] += 1
                    continue

            # Crawl with concurrency control
            async with sem:
                try:
                    state = {"url": url, "description": description}
                    state = await self.fetch_node.execute(state)
                    state = await self.parse_node.execute(state)
                    state = await self.extract_node.execute(state)

                    # Collect data
                    extracted = state.get("extracted_data", [])
                    if isinstance(extracted, list):
                        all_data.extend(extracted)
                        self.stats["data_items"] += len(extracted)
                    elif extracted:
                        all_data.append(extracted)
                        self.stats["data_items"] += 1

                    self.stats["pages_crawled"] += 1
                    visited_urls.append(url)

                    # Mark as seen in dedup store
                    if dedup:
                        url_hash = hashlib.md5(url.encode()).hexdigest()
                        await dedup.mark_seen(url_hash)

                    # Discover new links
                    links = state.get("links", [])
                    links_count = len(links)
                    page_type = detect_page_type(url, state.get("clean_text", ""), links_count)

                    for link in links:
                        href = link.get("href", "")
                        if not href:
                            continue
                        abs_url = urljoin(url, href)
                        parsed = urlparse(abs_url)

                        # Same domain only, no fragments
                        if parsed.netloc != base_domain:
                            continue
                        clean_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
                        if parsed.query:
                            clean_url += f"?{parsed.query}"

                        if pattern and not pattern.search(clean_url):
                            continue

                        # Priority: list pages get higher priority (discover more URLs)
                        child_type = detect_page_type(clean_url)
                        child_priority = 2 if child_type == "list" else 4
                        if self.frontier.add(clean_url, priority=child_priority,
                                             depth=depth + 1, parent_url=url,
                                             page_type=child_type):
                            self.stats["urls_discovered"] += 1

                    # Progress log
                    if self.stats["pages_crawled"] % 5 == 0:
                        logger.info(
                            f"Deep crawl progress: {self.stats['pages_crawled']}/{self.max_pages} pages, "
                            f"{self.stats['data_items']} items, frontier={self.frontier.size}"
                        )

                    # Checkpoint every 10 pages
                    if crawl_id and self.stats["pages_crawled"] % 10 == 0:
                        self.checkpoint.save(crawl_id, {
                            "all_data": all_data,
                            "visited": visited_urls,
                            "stats": self.stats,
                        })

                    # Politeness delay
                    delay = settings.default_delay
                    if self.respect_robots:
                        robot_delay = self.robots.get_crawl_delay(start_url)
                        if robot_delay > 0:
                            delay = max(delay, robot_delay)
                    await asyncio.sleep(delay)

                except Exception as e:
                    self.stats["pages_failed"] += 1
                    logger.warning(f"Error crawling {url} (depth={depth}): {e}")

        # Final stats
        self.stats["elapsed_seconds"] = round(time.time() - self.stats["start_time"], 1)

        # Clean up checkpoint on completion
        if crawl_id:
            self.checkpoint.delete(crawl_id)

        logger.info(
            f"Deep crawl complete: {self.stats['pages_crawled']} pages, "
            f"{self.stats['data_items']} items, {self.stats['elapsed_seconds']}s"
        )

        return {
            "all_data": all_data,
            "pages_crawled": self.stats["pages_crawled"],
            "urls_visited": visited_urls,
            "stats": self.stats,
        }
