"""Worker process - pulls tasks from queue and executes them."""
from __future__ import annotations

import asyncio
import os
import platform
from datetime import datetime

from loguru import logger

try:
    import psutil
except ImportError:
    psutil = None


def _get_system_info() -> dict:
    info: dict = {"cpu_percent": 0.0, "memory_mb": 0.0, "memory_total_mb": 0.0, "disk_percent": 0.0}
    if psutil:
        info["cpu_percent"] = psutil.cpu_percent(interval=0.1)
        proc_mem = psutil.Process().memory_info().rss / (1024 * 1024)
        info["memory_mb"] = proc_mem
        try:
            info["memory_total_mb"] = psutil.virtual_memory().total / (1024 * 1024)
        except Exception:
            pass
        try:
            info["disk_percent"] = psutil.disk_usage('/').percent
        except Exception:
            pass
    else:
        try:
            load = os.getloadavg()
            info["cpu_percent"] = load[0] * 100 / max(os.cpu_count() or 1, 1)
        except (OSError, AttributeError):
            pass
    return info


class WorkerProcess:
    """Standalone worker that polls master API for tasks and executes them."""

    def __init__(
        self,
        worker_id: str | None = None,
        master_url: str = "http://127.0.0.1:8901",
        max_concurrency: int = 3,
        tags: list[str] | None = None,
    ):
        self.worker_id = worker_id or f"worker-{platform.node()}-{os.getpid()}"
        self.master_url = master_url.rstrip("/")
        self.max_concurrency = max_concurrency
        self.tags = tags or []
        self.active_jobs = 0
        self.total_completed = 0
        self.total_failed = 0
        self._running = False
        self._client = None
        self._running_task_ids: set[str] = set()

    async def _get_client(self):
        import httpx
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client

    async def start(self) -> None:
        await self._register()
        self._running = True
        asyncio.create_task(self._heartbeat_loop())
        logger.info(f"Worker {self.worker_id} started, polling {self.master_url}")
        await self._poll_loop()

    async def stop(self) -> None:
        self._running = False
        if self._client:
            await self._client.aclose()

    @staticmethod
    def _get_local_ip() -> str:
        """获取本机出口IP"""
        import socket
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "127.0.0.1"

    async def _register(self) -> None:
        """注册到master，失败后指数退避重试（最多10次）"""
        client = await self._get_client()
        payload = {
            "worker_id": self.worker_id,
            "hostname": platform.node(),
            "ip": self._get_local_ip(),
            "max_concurrency": self.max_concurrency,
            "tags": self.tags,
        }
        for attempt in range(10):
            try:
                resp = await client.post(f"{self.master_url}/api/v1/workers/register", json=payload)
                data = resp.json()
                logger.info(f"注册成功: {data.get('id', self.worker_id)}")
                self._registered = True
                return
            except Exception as e:
                wait = min(2 ** attempt + 1, 60)
                logger.warning(f"注册失败 (第{attempt+1}次): {e}, {wait}s后重试")
                await asyncio.sleep(wait)
        logger.error(f"注册失败: 已重试10次，放弃。请检查master是否运行在 {self.master_url}")

    async def _heartbeat_loop(self) -> None:
        while self._running:
            await asyncio.sleep(15)
            try:
                client = await self._get_client()
                info = _get_system_info()
                payload = {
                    "status": "busy" if self.active_jobs >= self.max_concurrency else "online",
                    "cpu_percent": info["cpu_percent"],
                    "memory_mb": info["memory_mb"],
                    "memory_total_mb": info.get("memory_total_mb", 0),
                    "disk_percent": info.get("disk_percent", 0),
                    "python_version": platform.python_version(),
                    "os_info": f"{platform.system()} {platform.release()}",
                    "active_jobs": self.active_jobs,
                    "current_tasks": list(getattr(self, '_running_task_ids', set())),
                    "total_completed": self.total_completed,
                    "total_failed": self.total_failed,
                }
                resp = await client.post(
                    f"{self.master_url}/api/v1/workers/{self.worker_id}/heartbeat",
                    json=payload,
                )
                if resp.status_code != 200:
                    logger.warning(f"Heartbeat failed: {resp.status_code}")
            except Exception as e:
                logger.error(f"Heartbeat error: {e}")

    async def _poll_loop(self) -> None:
        while self._running:
            if self.active_jobs >= self.max_concurrency:
                await asyncio.sleep(2)
                continue
            try:
                client = await self._get_client()
                resp = await client.post(
                    f"{self.master_url}/api/v1/workers/{self.worker_id}/poll"
                )
                if resp.status_code == 404:
                    # worker未注册，尝试重新注册
                    logger.warning("Worker未注册，尝试重新注册...")
                    await self._register()
                    await asyncio.sleep(5)
                    continue
                if resp.status_code != 200:
                    await asyncio.sleep(5)
                    continue
                task = resp.json()
                if not task or not task.get("task_id"):
                    # 无任务，安静等待
                    await asyncio.sleep(3)
                    continue
                self.active_jobs += 1
                self._running_task_ids.add(task.get("task_id", ""))
                asyncio.create_task(self._execute_task(task))
            except Exception as e:
                logger.error(f"Poll error: {e}")
                await asyncio.sleep(5)

    async def _execute_task(self, task: dict) -> None:
        task_id = task["task_id"]
        run_id = task["run_id"]
        mode = task.get("mode", "code_generator")
        retry_count = task.get("retry_count", 0)
        max_retries = task.get("max_retries", 3)
        logger.info(f"Executing task {task_id} (mode={mode}, attempt={retry_count+1}/{max_retries+1})")

        try:
            target_urls = task.get("target_urls", [])
            if isinstance(target_urls, str):
                import json as _json
                try:
                    target_urls = _json.loads(target_urls)
                except Exception:
                    target_urls = [target_urls]
            timeout = task.get("timeout_seconds", 300)
            logger.info(f"Task {task_id}: mode={mode}, use_browser={task.get('use_browser')}, urls={target_urls}, code_len={len(task.get('code',''))}")
            all_items: list[dict] = []
            total_pages = 0

            if mode == "smart_scraper":
                all_items, total_pages = await self._run_smart_scraper(task, target_urls, timeout)
            else:
                all_items, total_pages = await self._run_code(task, target_urls, timeout)

            await self._report(task_id, run_id, "success",
                               items=all_items,
                               items_count=len(all_items),
                               pages_crawled=total_pages)
            self.total_completed += 1
            logger.info(f"Task {task_id} done: {len(all_items)} items")

            # Notify on success
            try:
                from src.core.notifier import notifier
                await notifier.notify("task_completed", {
                    "task_id": task_id,
                    "items_count": len(all_items),
                    "pages_crawled": total_pages,
                })
            except Exception:
                pass

        except Exception as e:
            # Report failure — retry is handled by the Redis queue (queue.fail()),
            # NOT here. Previous recursive self._execute_task() caused double-retry.
            logger.error(f"Task {task_id} failed (attempt {retry_count+1}/{max_retries+1}): {e}")
            await self._report(task_id, run_id, "failed", error=str(e))
            self.total_failed += 1
            # Only notify on final failure (not during retries)
            if retry_count >= max_retries:
                try:
                    from src.core.notifier import notifier
                    await notifier.notify("task_failed", {
                        "task_id": task_id,
                        "error": str(e),
                        "retries": max_retries,
                    })
                except Exception:
                    pass
        finally:
            self.active_jobs -= 1
            self._running_task_ids.discard(task_id)

    async def _run_code(self, task: dict, target_urls: list[str], timeout: int) -> tuple[list[dict], int]:
        code = task.get("code", "")
        if not code:
            raise ValueError("No code in task")

        from src.engine.sandbox import run_code_in_sandbox

        proxy_config = task.get("proxy_config")
        if isinstance(proxy_config, str):
            import json as _json
            try:
                proxy_config = _json.loads(proxy_config)
            except Exception:
                proxy_config = None
        use_browser = task.get("use_browser", False)

        # Extract pagination config from proxy_config if present
        pagination = None
        if proxy_config and isinstance(proxy_config, dict):
            pagination = proxy_config.get("pagination")

        all_items: list[dict] = []
        total_pages = 0
        for url in target_urls:
            pre_html = None
            api_data = None
            if use_browser and "pre_rendered_html" in code:
                pre_html, api_data = await self._pre_render(url, pagination=pagination)
            result = await run_code_in_sandbox(
                code, url, timeout=timeout, proxy_config=proxy_config,
                html=pre_html, api_data=api_data,
            )
            output = result.get("output", [])
            if output:
                all_items.extend(output)
            total_pages += result.get("pages_crawled", 0)
        return all_items, total_pages

    async def _pre_render(self, url: str, pagination: dict | None = None) -> tuple[str | None, list | None]:
        """Pre-render a page with Playwright and return (html, api_data).

        Handles JS challenge (cookie-based anti-bot) by:
        1. Injecting stealth scripts to hide webdriver detection
        2. Waiting for JS challenge to complete (cookie set + redirect)
        3. Intercepting all JSON API responses during page load
        4. If pagination config provided, auto-paginate to collect all data

        pagination config (from project.proxy_config["pagination"]):
        {
            "api_pattern": "showreportdata",     # URL pattern to intercept
            "page_fn": "gotoPage('bdzq', {page}, {size})",  # JS to call
            "page_size": 500,
            "total_key": "totalCount",           # JSON key for total count
            "data_key": "data",                  # JSON key for items array
        }

        Returns (html, api_data) where api_data is a list of all JSON items
        collected from API responses, or None if no pagination.
        """
        try:
            import json as _json
            from playwright.async_api import async_playwright
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-http2"])
                context = await browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
                )
                page = await context.new_page()
                await page.add_init_script("""
                    Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                    window.chrome = {runtime: {}};
                """)

                # Intercept JSON API responses
                api_responses: list[str] = []
                api_pattern = (pagination or {}).get("api_pattern", "")

                async def _capture(response):
                    if api_pattern and api_pattern in response.url:
                        try:
                            api_responses.append(await response.text())
                        except Exception:
                            pass
                if api_pattern:
                    page.on("response", _capture)

                await page.goto(url, wait_until="networkidle", timeout=45000)
                await page.wait_for_timeout(8000)

                # Verify JS challenge passed — if page is still a challenge page,
                # wait longer and retry (challenge scripts need variable time)
                if pagination and not api_responses:
                    html_check = await page.content()
                    if len(html_check) < 65000 or "document.cookie" in html_check[:2000]:
                        logger.info("JS challenge may not have completed, waiting longer...")
                        await page.wait_for_timeout(5000)
                        # If still stuck, try reload (cookies should be set now)
                        if not api_responses:
                            logger.info("Reloading page after challenge wait...")
                            await page.reload(wait_until="networkidle", timeout=30000)
                            await page.wait_for_timeout(8000)

                all_api_data = None

                # Auto-paginate if config provided and initial API response captured
                if pagination and api_responses:
                    data_key = pagination.get("data_key", "data")
                    total_key = pagination.get("total_key", "totalCount")
                    page_fn = pagination.get("page_fn", "")
                    page_size = pagination.get("page_size", 500)

                    first = _json.loads(api_responses[0])
                    total_count = first.get(total_key, 0)
                    all_api_data = list(first.get(data_key, []))
                    logger.info(f"Pre-render pagination: total={total_count}, first_page={len(all_api_data)}")

                    if total_count > len(all_api_data) and page_fn:
                        pages_needed = (total_count + page_size - 1) // page_size
                        for pi in range(0, pages_needed):
                            api_responses.clear()
                            js = page_fn.replace("{page}", str(pi)).replace("{size}", str(page_size))
                            await page.evaluate(js)
                            await page.wait_for_timeout(3000)
                            if api_responses:
                                batch = _json.loads(api_responses[0])
                                items = batch.get(data_key, [])
                                if items:
                                    all_api_data.extend(items)
                                    logger.info(f"  Page {pi}: +{len(items)} (total: {len(all_api_data)})")
                                if len(items) < page_size:
                                    break
                            else:
                                logger.warning(f"  Page {pi}: no API response, stopping")
                                break

                html = await page.content()
                await browser.close()
                logger.info(f"Pre-rendered {url}: {len(html)} chars, api_items={len(all_api_data) if all_api_data else 0}")
                return html, all_api_data
        except Exception as e:
            logger.warning(f"Pre-render failed for {url}: {e}")
            return None, None

    async def _run_smart_scraper(self, task: dict, target_urls: list[str], timeout: int) -> tuple[list[dict], int]:
        description = task.get("description", "")
        if not description:
            raise ValueError("No description for smart_scraper mode")

        all_items: list[dict] = []
        total_pages = 0

        try:
            from scrapegraphai.graphs import SmartScraperGraph
        except ImportError:
            raise RuntimeError("scrapegraphai not installed")

        from src.core.config import settings

        for url in target_urls:
            try:
                graph = SmartScraperGraph(
                    prompt=description,
                    source=url,
                    config={
                        "llm": {
                            "model": settings.llm_model or "openai/gpt-4o-mini",
                            "api_key": settings.llm_api_key or os.environ.get("OPENAI_API_KEY", ""),
                            "base_url": settings.llm_base_url or None,
                        },
                        "verbose": False,
                    },
                )
                result = await asyncio.to_thread(graph.run)
                if isinstance(result, dict):
                    all_items.append(result)
                elif isinstance(result, list):
                    all_items.extend(result)
                total_pages += 1
            except Exception as e:
                logger.warning(f"SmartScraper failed for {url}: {e}")

        return all_items, total_pages

    async def _report(self, task_id: str, run_id: str, status: str, **kwargs) -> None:
        try:
            client = await self._get_client()
            payload = {"task_id": task_id, "run_id": run_id, "status": status, **kwargs}
            resp = await client.post(
                f"{self.master_url}/api/v1/workers/{self.worker_id}/report",
                json=payload,
            )
            if resp.status_code != 200:
                logger.warning(f"Report failed: {resp.status_code}")
        except Exception as e:
            logger.error(f"Report error: {e}")


# ── WorkerManager (for master side, backward compat) ──

from src.core.database import db
from src.core.models import Worker, WorkerStatus


class WorkerManager:
    """Manage worker registration, heartbeats, and failover (master side)."""

    HEARTBEAT_TIMEOUT = 60  # seconds before marking worker offline
    _sweep_task: asyncio.Task | None = None

    async def start_sweeper(self) -> None:
        """Start background task to detect offline workers and recover their tasks."""
        if self._sweep_task is None:
            self._sweep_task = asyncio.create_task(self._sweep_loop())
            logger.info("WorkerManager sweeper started")

    async def stop_sweeper(self) -> None:
        if self._sweep_task:
            self._sweep_task.cancel()
            self._sweep_task = None

    async def _sweep_loop(self) -> None:
        """Periodically check for offline workers and timed-out tasks."""
        from src.scheduler.queue import task_queue
        while True:
            try:
                await asyncio.sleep(30)
                # 1. Mark offline workers
                await self._detect_offline_workers()
                # 2. Sweep timed-out tasks in queue
                recovered = await task_queue.sweep_timed_out()
                if recovered:
                    # Update task status in DB
                    for tid in recovered:
                        try:
                            task = await db.get("tasks", tid)
                            if task and task.get("status") == "running":
                                await db.update("tasks", tid, {
                                    "status": "pending",
                                    "updated_at": datetime.now().isoformat(),
                                })
                        except Exception:
                            pass
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Sweeper error: {e}")
                await asyncio.sleep(10)

    async def _detect_offline_workers(self) -> None:
        """Detect workers that missed heartbeats and recover their tasks."""
        from src.scheduler.queue import task_queue
        workers = await db.list("workers", order="last_heartbeat DESC")
        now = datetime.utcnow()
        for w in workers:
            if w.get("status") in ("offline", "disabled"):
                continue
            last_hb = w.get("last_heartbeat", "")
            if not last_hb:
                continue
            try:
                # Strip timezone info to get naive UTC datetime for comparison
                hb_time = datetime.fromisoformat(last_hb.replace("Z", "+00:00").replace("+00:00", ""))
                elapsed = (now - hb_time).total_seconds()
            except (ValueError, TypeError):
                continue

            if elapsed > self.HEARTBEAT_TIMEOUT:
                wid = w["id"]
                logger.warning(f"Worker {wid} offline (no heartbeat for {int(elapsed)}s)")
                await db.update("workers", wid, {"status": "offline"})

                # Recover tasks assigned to this worker
                current_tasks = w.get("current_tasks", [])
                if isinstance(current_tasks, str):
                    import json as _json
                    try:
                        current_tasks = _json.loads(current_tasks)
                    except Exception:
                        current_tasks = []
                for tid in current_tasks:
                    logger.info(f"Recovering task {tid} from offline worker {wid}")
                    try:
                        await task_queue.fail(tid, f"Worker {wid} went offline")
                    except Exception as e:
                        logger.error(f"Failed to recover task {tid}: {e}")

    async def register(self, worker_id: str, **kwargs) -> Worker:
        w = Worker(id=worker_id, **kwargs)
        existing = await db.get("workers", worker_id)
        if existing:
            await db.update("workers", worker_id, {
                "status": WorkerStatus.ONLINE,
                "last_heartbeat": datetime.now().isoformat(),
                **{k: v for k, v in kwargs.items() if v},
            })
        else:
            await db.insert("workers", w.model_dump())
        logger.info(f"Worker registered: {worker_id}")
        return w

    async def heartbeat(self, worker_id: str, **kwargs) -> Worker | None:
        existing = await db.get("workers", worker_id)
        if not existing:
            return None
        update = {"last_heartbeat": datetime.now().isoformat()}
        update.update({k: v for k, v in kwargs.items() if v is not None})
        await db.update("workers", worker_id, update)
        data = await db.get("workers", worker_id)
        return Worker(**data) if data else None

    async def list_workers(self) -> list[Worker]:
        rows = await db.list("workers", order="last_heartbeat DESC")
        return [Worker(**r) for r in rows]

    async def unregister(self, worker_id: str) -> None:
        await db.delete("workers", worker_id)

    async def stats(self) -> dict:
        workers = await self.list_workers()
        return {
            "total": len(workers),
            "online": sum(1 for w in workers if w.status == WorkerStatus.ONLINE),
            "busy": sum(1 for w in workers if w.status == WorkerStatus.BUSY),
            "offline": sum(1 for w in workers if w.status == WorkerStatus.OFFLINE),
        }


worker_manager = WorkerManager()


# ── CLI entry point ──

async def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="AI Spider Worker")
    parser.add_argument("--master", default="http://127.0.0.1:8901")
    parser.add_argument("--concurrency", type=int, default=3)
    parser.add_argument("--tags", default="")
    parser.add_argument("--id", default=None, dest="worker_id")
    args = parser.parse_args()

    worker = WorkerProcess(
        worker_id=args.worker_id,
        master_url=args.master,
        max_concurrency=args.concurrency,
        tags=args.tags.split(",") if args.tags else [],
    )
    try:
        await worker.start()
    except KeyboardInterrupt:
        await worker.stop()


if __name__ == "__main__":
    asyncio.run(main())
