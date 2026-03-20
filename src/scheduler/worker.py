"""Worker process - pulls tasks from queue and executes them."""
from __future__ import annotations

import asyncio
import json
import os
import platform
from datetime import datetime

from loguru import logger

try:
    import aiohttp
except ImportError:
    aiohttp = None

try:
    import psutil
except ImportError:
    psutil = None


def _get_system_info() -> dict:
    """Get basic system info, with or without psutil."""
    info: dict = {"cpu_percent": 0.0, "memory_mb": 0.0}
    if psutil:
        info["cpu_percent"] = psutil.cpu_percent(interval=0.1)
        info["memory_mb"] = psutil.virtual_memory().used / (1024 * 1024)
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
        self.worker_id = worker_id or f"worker-{platform.node()}"
        self.master_url = master_url.rstrip("/")
        self.max_concurrency = max_concurrency
        self.tags = tags or []
        self.active_jobs = 0
        self.total_completed = 0
        self.total_failed = 0
        self._running = False
        self._session: aiohttp.ClientSession | None = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            if aiohttp is None:
                raise RuntimeError("aiohttp is required for worker. pip install aiohttp")
            self._session = aiohttp.ClientSession()
        return self._session

    async def start(self) -> None:
        """Register with master and start polling loop."""
        await self._register()
        self._running = True
        asyncio.create_task(self._heartbeat_loop())
        logger.info(f"Worker {self.worker_id} started, polling {self.master_url}")
        await self._poll_loop()

    async def stop(self) -> None:
        self._running = False
        if self._session and not self._session.closed:
            await self._session.close()

    async def _register(self) -> None:
        """POST /api/v1/workers/register"""
        session = await self._get_session()
        payload = {
            "worker_id": self.worker_id,
            "hostname": platform.node(),
            "ip": "127.0.0.1",
            "max_concurrency": self.max_concurrency,
            "tags": self.tags,
        }
        try:
            async with session.post(f"{self.master_url}/api/v1/workers/register", json=payload) as resp:
                data = await resp.json()
                logger.info(f"Registered with master: {data.get('id', self.worker_id)}")
        except Exception as e:
            logger.error(f"Failed to register: {e}")

    async def _heartbeat_loop(self) -> None:
        """Send heartbeat every 15 seconds."""
        while self._running:
            await asyncio.sleep(15)
            try:
                session = await self._get_session()
                info = _get_system_info()
                payload = {
                    "status": "busy" if self.active_jobs >= self.max_concurrency else "online",
                    "cpu_percent": info["cpu_percent"],
                    "memory_mb": info["memory_mb"],
                    "active_jobs": self.active_jobs,
                    "total_completed": self.total_completed,
                    "total_failed": self.total_failed,
                }
                async with session.post(
                    f"{self.master_url}/api/v1/workers/{self.worker_id}/heartbeat",
                    json=payload,
                ) as resp:
                    if resp.status != 200:
                        logger.warning(f"Heartbeat failed: {resp.status}")
            except Exception as e:
                logger.error(f"Heartbeat error: {e}")

    async def _poll_loop(self) -> None:
        """Poll for tasks from master."""
        while self._running:
            if self.active_jobs >= self.max_concurrency:
                await asyncio.sleep(2)
                continue
            try:
                session = await self._get_session()
                async with session.post(
                    f"{self.master_url}/api/v1/workers/{self.worker_id}/poll"
                ) as resp:
                    if resp.status == 404:
                        await asyncio.sleep(3)
                        continue
                    if resp.status != 200:
                        await asyncio.sleep(5)
                        continue
                    task = await resp.json()
                    if not task or not task.get("task_id"):
                        await asyncio.sleep(3)
                        continue
                    self.active_jobs += 1
                    asyncio.create_task(self._execute_task(task))
            except Exception as e:
                logger.error(f"Poll error: {e}")
                await asyncio.sleep(5)

    async def _execute_task(self, task: dict) -> None:
        """Execute a single task and report results."""
        task_id = task["task_id"]
        run_id = task["run_id"]
        logger.info(f"Executing task {task_id}")

        try:
            code = task.get("code", "")
            target_urls = task.get("target_urls", [])
            timeout = task.get("timeout_seconds", 300)

            if not code:
                raise ValueError("No code in task")

            total_items = 0
            total_pages = 0
            all_items: list[dict] = []

            # Import sandbox runner
            from src.engine.sandbox import run_code_in_sandbox

            for url in target_urls:
                result = await run_code_in_sandbox(code, url, timeout=timeout)
                output = result.get("output", [])
                if output:
                    all_items.extend(output)
                    total_items += len(output)
                total_pages += result.get("pages_crawled", 0)

            # Report success
            await self._report(task_id, run_id, "success", items=all_items,
                               items_count=total_items, pages_crawled=total_pages)
            self.total_completed += 1
            logger.info(f"Task {task_id} done: {total_items} items")

        except Exception as e:
            logger.error(f"Task {task_id} failed: {e}")
            await self._report(task_id, run_id, "failed", error=str(e))
            self.total_failed += 1
        finally:
            self.active_jobs -= 1

    async def _report(self, task_id: str, run_id: str, status: str, **kwargs) -> None:
        """POST /api/v1/workers/{id}/report"""
        try:
            session = await self._get_session()
            payload = {"task_id": task_id, "run_id": run_id, "status": status, **kwargs}
            async with session.post(
                f"{self.master_url}/api/v1/workers/{self.worker_id}/report",
                json=payload,
            ) as resp:
                if resp.status != 200:
                    logger.warning(f"Report failed: {resp.status}")
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
