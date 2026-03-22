"""
数据保留与自动清理 — 防止数据库无限增长。

定时清理:
- data_records: 超过retention天数的记录
- task_runs: 超过retention天数的运行记录
- notification_logs: 超过30天的通知日志
- workers: 超过7天未心跳的离线worker
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from loguru import logger


async def cleanup_expired_data(retention_days: int = 90) -> dict:
    """清理过期数据，返回清理统计"""
    from src.core.database import db

    stats = {}
    cutoff = (datetime.now(timezone.utc) - timedelta(days=retention_days)).isoformat()

    # 清理过期数据记录
    try:
        rows = await db.query(
            "SELECT COUNT(*) as cnt FROM data_records WHERE created_at < ? AND created_at != ''",
            [cutoff],
        )
        count = rows[0]["cnt"] if rows else 0
        if count > 0:
            await db.execute(
                "DELETE FROM data_records WHERE created_at < ? AND created_at != ''",
                [cutoff],
            )
            logger.info(f"清理了 {count} 条过期数据记录 (>{retention_days}天)")
        stats["data_records"] = count
    except Exception as e:
        logger.error(f"清理data_records失败: {e}")
        stats["data_records"] = f"error: {e}"

    # 清理过期任务运行记录
    try:
        rows = await db.query(
            "SELECT COUNT(*) as cnt FROM task_runs WHERE started_at < ? AND started_at != ''",
            [cutoff],
        )
        count = rows[0]["cnt"] if rows else 0
        if count > 0:
            await db.execute(
                "DELETE FROM task_runs WHERE started_at < ? AND started_at != ''",
                [cutoff],
            )
            logger.info(f"清理了 {count} 条过期任务运行记录")
        stats["task_runs"] = count
    except Exception as e:
        logger.error(f"清理task_runs失败: {e}")
        stats["task_runs"] = f"error: {e}"

    # 清理过期通知日志(30天)
    notify_cutoff = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    try:
        rows = await db.query(
            "SELECT COUNT(*) as cnt FROM notification_logs WHERE created_at < ? AND created_at != ''",
            [notify_cutoff],
        )
        count = rows[0]["cnt"] if rows else 0
        if count > 0:
            await db.execute(
                "DELETE FROM notification_logs WHERE created_at < ? AND created_at != ''",
                [notify_cutoff],
            )
        stats["notification_logs"] = count
    except Exception as e:
        stats["notification_logs"] = f"error: {e}"

    # 清理僵尸Worker(7天无心跳)
    worker_cutoff = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    try:
        rows = await db.query(
            "SELECT COUNT(*) as cnt FROM workers WHERE last_heartbeat < ? AND last_heartbeat != '' AND status != 'disabled'",
            [worker_cutoff],
        )
        count = rows[0]["cnt"] if rows else 0
        if count > 0:
            await db.execute(
                "DELETE FROM workers WHERE last_heartbeat < ? AND last_heartbeat != '' AND status != 'disabled'",
                [worker_cutoff],
            )
            logger.info(f"清理了 {count} 个僵尸Worker")
        stats["stale_workers"] = count
    except Exception as e:
        stats["stale_workers"] = f"error: {e}"

    return stats
