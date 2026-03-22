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

    async def _register(self) -> None:
        """注册到master，失败后指数退避重试（最多10次）"""
        client = await self._get_client()
        payload = {
            "worker_id": self.worker_id,
            "hostname": platform.node(),
            "ip": "127.0.0.1",
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
            timeout = task.get("timeout_seconds", 300)
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
            # Retry logic
            if retry_count < max_retries:
                retry_delays = [10, 30, 90]
                delay = retry_delays[min(retry_count, len(retry_delays) - 1)]
                logger.warning(f"Task {task_id} failed (attempt {retry_count+1}/{max_retries}), retrying in {delay}s: {e}")
                try:
                    await self._report(task_id, run_id, "retrying", error=str(e),
                                       retry_count=retry_count + 1,
                                       next_retry_at=(datetime.utcnow() + __import__('datetime').timedelta(seconds=delay)).isoformat())
                except Exception:
                    pass
                await asyncio.sleep(delay)
                task["retry_count"] = retry_count + 1
                self.active_jobs -= 1
                self._running_task_ids.discard(task_id)
                self.active_jobs += 1
                self._running_task_ids.add(task_id)
                await self._execute_task(task)
                return
            else:
                logger.error(f"Task {task_id} failed after {max_retries} retries: {e}")
                await self._report(task_id, run_id, "failed", error=str(e))
                self.total_failed += 1
                # Notify on final failure
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

        all_items: list[dict] = []
        total_pages = 0
        for url in target_urls:
            result = await run_code_in_sandbox(code, url, timeout=timeout, proxy_config=proxy_config)
            output = result.get("output", [])
            if output:
                all_items.extend(output)
            total_pages += result.get("pages_crawled", 0)
        return all_items, total_pages

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
    """Manage worker registration and heartbeats (master side)."""

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
