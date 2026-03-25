"""
AI Spider Python SDK — 内网调用爬虫系统

用法:
    from ai_spider_client import SpiderClient
    
    client = SpiderClient("https://rthe525.top/spider", "sk-your-api-key")
    
    # 一键：创建项目 → 等待生成 → 测试 → 拿数据
    data = client.quick_crawl(
        url="https://quotes.toscrape.com/",
        fields="quote,author,tags",
        timeout=300,
    )
    print(data)  # [{"quote": "...", "author": "...", "tags": "..."}, ...]
"""
from __future__ import annotations
import time
import json
import logging
from typing import Optional
from urllib.parse import urljoin

import httpx

logger = logging.getLogger("ai_spider_client")


class SpiderError(Exception):
    """API error with status code and detail."""
    def __init__(self, status: int, detail: str):
        self.status = status
        self.detail = detail
        super().__init__(f"HTTP {status}: {detail}")


class SpiderClient:
    """AI Spider REST API client.
    
    Args:
        base_url: Server URL, e.g. "https://rthe525.top/spider" or "http://192.168.1.100:8901"
        api_key: User API key (from /api/v1/auth/login or admin panel)
        timeout: Default request timeout in seconds
    """

    def __init__(self, base_url: str, api_key: str, timeout: int = 60):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self._client = httpx.Client(
            base_url=self.base_url,
            headers={"X-API-Key": api_key, "Content-Type": "application/json"},
            timeout=timeout,
            follow_redirects=True,
        )

    def _request(self, method: str, path: str, **kwargs) -> dict | list:
        resp = self._client.request(method, path, **kwargs)
        if resp.status_code >= 400:
            detail = resp.text[:500]
            try:
                detail = resp.json().get("detail", detail)
            except Exception:
                pass
            raise SpiderError(resp.status_code, detail)
        if not resp.content:
            return {}
        return resp.json()

    # ── Auth ──

    def me(self) -> dict:
        """Get current user info."""
        return self._request("GET", "/api/v1/auth/me")

    # ── Projects ──

    def list_projects(self) -> list[dict]:
        """List all projects."""
        return self._request("GET", "/api/v1/projects")

    def get_project(self, project_id: str) -> dict:
        """Get project details."""
        return self._request("GET", f"/api/v1/projects/{project_id}")

    def create_project(
        self,
        target_url: str,
        description: str,
        name: str = "",
        mode: str = "code_generator",
        use_browser: bool = False,
        enable_pagination: bool = False,
    ) -> dict:
        """Create a new project. Triggers async AI code generation.
        
        Args:
            target_url: URL to crawl
            description: Comma-separated field names or natural language description
            name: Project name (auto-generated from description if empty)
            mode: "code_generator" or "smart_scraper"
            use_browser: Force Playwright browser mode
            enable_pagination: Enable multi-page crawling
            
        Returns:
            Project dict with id, status="generating"
        """
        body = {
            "name": name or description[:30],
            "description": description,
            "target_url": target_url,
            "mode": mode,
        }
        if use_browser:
            body["use_browser"] = True
        if enable_pagination:
            body["enable_pagination"] = True
        return self._request("POST", "/api/v1/projects", json=body)

    def update_project(self, project_id: str, **fields) -> dict:
        """Update project fields (name, description, target_url, use_browser, etc.)."""
        return self._request("PUT", f"/api/v1/projects/{project_id}", json=fields)

    def update_code(self, project_id: str, code: str) -> dict:
        """Save/replace project crawler code."""
        return self._request("PUT", f"/api/v1/projects/{project_id}/code", json={"code": code})

    def delete_project(self, project_id: str) -> dict:
        """Delete a project."""
        return self._request("DELETE", f"/api/v1/projects/{project_id}")

    def wait_for_generation(self, project_id: str, timeout: int = 300, poll_interval: int = 5) -> dict:
        """Poll until project leaves 'generating' status.
        
        Returns:
            Updated project dict
        Raises:
            TimeoutError if generation doesn't complete in time
        """
        deadline = time.time() + timeout
        while time.time() < deadline:
            proj = self.get_project(project_id)
            status = proj.get("status", "")
            if status != "generating":
                logger.info(f"Project {project_id} ready: status={status}")
                return proj
            time.sleep(poll_interval)
        raise TimeoutError(f"Project {project_id} still generating after {timeout}s")

    # ── Test / Run ──

    def test_project(self, project_id: str, timeout: int = 120) -> dict:
        """Run a test crawl. Returns output data + error info.
        
        Returns:
            {"output": [...], "error": "", "auto_fixed": false, "duration_ms": ...}
        """
        old_timeout = self._client.timeout
        self._client.timeout = httpx.Timeout(timeout)
        try:
            return self._request("POST", f"/api/v1/projects/{project_id}/test", json={})
        finally:
            self._client.timeout = old_timeout

    # ── Data ──

    def list_data(self, project_id: str = "", limit: int = 100, offset: int = 0) -> list[dict]:
        """List crawled data records."""
        params = {"limit": limit, "offset": offset}
        if project_id:
            params["project_id"] = project_id
        return self._request("GET", "/api/v1/data", params=params)

    def data_stats(self, project_id: str = "") -> dict:
        """Get data statistics."""
        params = {}
        if project_id:
            params["project_id"] = project_id
        return self._request("GET", "/api/v1/data/stats", params=params)

    def export_data(self, project_id: str, format: str = "json") -> str:
        """Export data as JSON or CSV string."""
        resp = self._client.get(
            f"/api/v1/data/export/{format}",
            params={"project_id": project_id},
        )
        return resp.text

    # ── Tasks ──

    def create_task(
        self,
        project_id: str,
        name: str = "",
        cron_expr: str = "",
        worker_id: str = "",
    ) -> dict:
        """Create a scheduled task from a project."""
        body = {"project_id": project_id}
        if name:
            body["name"] = name
        if cron_expr:
            body["cron_expr"] = cron_expr
        if worker_id:
            body["worker_id"] = worker_id
        return self._request("POST", "/api/v1/tasks", json=body)

    def list_tasks(self) -> list[dict]:
        return self._request("GET", "/api/v1/tasks")

    def get_task(self, task_id: str) -> dict:
        return self._request("GET", f"/api/v1/tasks/{task_id}")

    def get_task_runs(self, task_id: str) -> list[dict]:
        return self._request("GET", f"/api/v1/tasks/{task_id}/runs")

    # ── Workers ──

    def list_workers(self) -> list[dict]:
        return self._request("GET", "/api/v1/workers")

    # ── Convenience ──

    def quick_crawl(
        self,
        url: str,
        fields: str,
        name: str = "",
        use_browser: bool = False,
        enable_pagination: bool = False,
        gen_timeout: int = 300,
        test_timeout: int = 120,
    ) -> list[dict]:
        """One-shot: create project → wait for code gen → test → return data.
        
        Args:
            url: Target URL
            fields: Comma-separated field names, e.g. "title,price,rating"
            name: Optional project name
            use_browser: Force browser mode (for JS-heavy sites)
            enable_pagination: Enable pagination
            gen_timeout: Max seconds to wait for code generation
            test_timeout: Max seconds for test execution
            
        Returns:
            List of extracted data dicts
            
        Raises:
            SpiderError: If API returns error
            TimeoutError: If generation times out
            RuntimeError: If test returns error
        """
        # 1. Create
        proj = self.create_project(
            target_url=url,
            description=fields,
            name=name,
            use_browser=use_browser,
            enable_pagination=enable_pagination,
        )
        project_id = proj["id"]
        logger.info(f"Created project {project_id}, generating...")

        # 2. Wait for generation
        proj = self.wait_for_generation(project_id, timeout=gen_timeout)
        logger.info(f"Generation done: status={proj['status']}")

        # 3. Test
        result = self.test_project(project_id, timeout=test_timeout)
        if result.get("error"):
            raise RuntimeError(f"Crawl failed: {result['error'][:200]}")

        output = result.get("output", [])
        logger.info(f"Got {len(output)} items")
        return output

    def close(self):
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


# ── CLI usage ──
if __name__ == "__main__":
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="AI Spider CLI")
    parser.add_argument("--server", default="http://127.0.0.1:8901", help="Server URL")
    parser.add_argument("--key", required=True, help="API key")
    
    sub = parser.add_subparsers(dest="cmd")
    
    # quick_crawl
    crawl_p = sub.add_parser("crawl", help="One-shot crawl")
    crawl_p.add_argument("url", help="Target URL")
    crawl_p.add_argument("fields", help="Comma-separated field names")
    crawl_p.add_argument("--browser", action="store_true")
    crawl_p.add_argument("--pagination", action="store_true")
    crawl_p.add_argument("--timeout", type=int, default=300)
    
    # list
    list_p = sub.add_parser("list", help="List projects")
    
    # test
    test_p = sub.add_parser("test", help="Test a project")
    test_p.add_argument("project_id")
    
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    
    client = SpiderClient(args.server, args.key)
    
    if args.cmd == "crawl":
        data = client.quick_crawl(
            url=args.url,
            fields=args.fields,
            use_browser=args.browser,
            enable_pagination=args.pagination,
            gen_timeout=args.timeout,
        )
        print(json.dumps(data, ensure_ascii=False, indent=2))
    elif args.cmd == "list":
        for p in client.list_projects():
            print(f"{p['id'][:8]}  {p.get('status','?'):12}  {p.get('name','')[:40]}")
    elif args.cmd == "test":
        r = client.test_project(args.project_id)
        print(json.dumps(r, ensure_ascii=False, indent=2)[:3000])
    else:
        parser.print_help()
