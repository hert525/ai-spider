"""Worker process - polls queue and executes tasks."""
import asyncio
import platform
from datetime import datetime
from loguru import logger
from src.core.database import db
from src.core.models import Worker, WorkerStatus, TaskStatus
from src.scheduler.queue import task_queue
from src.scheduler.task_manager import task_manager
from src.engine.sandbox import run_code_in_sandbox


class WorkerManager:
    """Manage worker registration and heartbeats."""

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

    async def unregister(self, worker_id: str):
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


async def worker_loop(worker_id: str = "local-worker"):
    """Main worker loop - poll queue and execute tasks."""
    await worker_manager.register(
        worker_id,
        hostname=platform.node(),
        ip="127.0.0.1",
    )
    logger.info(f"Worker {worker_id} started, polling for tasks...")

    while True:
        try:
            task_data = await task_queue.pop()
            if not task_data:
                await asyncio.sleep(2)
                continue

            task_id = task_data["task_id"]
            task = await task_manager.get_task(task_id)
            if not task:
                await task_queue.complete(task_id)
                continue

            # Get project code
            project = await db.get("projects", task.project_id)
            if not project or not project.get("code"):
                await task_manager.update_task(task_id, status=TaskStatus.FAILED)
                await task_queue.complete(task_id)
                continue

            run = await task_manager.start_run(task_id, worker_id)
            logger.info(f"Executing task {task_id}")

            try:
                total_items = 0
                total_pages = 0
                for url in task.target_urls:
                    result = await run_code_in_sandbox(
                        project["code"], url, timeout=task.timeout_seconds
                    )
                    if result.get("output"):
                        # Store data
                        from src.core.models import DataRecord, _uid
                        records = []
                        for item in result["output"]:
                            records.append(DataRecord(
                                project_id=task.project_id,
                                task_id=task_id,
                                task_run_id=run.id,
                                data=item,
                            ).model_dump())
                        await db.insert_many("data_records", records)
                        total_items += len(result["output"])
                    total_pages += result.get("pages_crawled", 0)

                await task_manager.complete_run(run.id, items_count=total_items, pages_crawled=total_pages)
                await task_manager.update_task(task_id, status=TaskStatus.SUCCESS)
                await task_queue.complete(task_id)
                logger.info(f"Task {task_id} completed: {total_items} items")

            except Exception as e:
                logger.error(f"Task {task_id} failed: {e}")
                await task_manager.fail_run(run.id, str(e))
                await task_manager.update_task(task_id, status=TaskStatus.FAILED)
                await task_queue.fail(task_id)

        except Exception as e:
            logger.error(f"Worker error: {e}")
            await asyncio.sleep(5)
