"""Notification system — email, webhook, telegram."""
from __future__ import annotations

import asyncio
import json
import smtplib
from datetime import datetime, timezone
from email.mime.text import MIMEText

import httpx
from loguru import logger

from src.core.models import _uid


class Notifier:
    """Send notifications on task completion/failure, worker offline etc."""

    async def notify(self, event: str, data: dict, channels: list[str] | None = None, user_id: str = ""):
        """Send notification to configured channels.

        Events: task_completed, task_failed, worker_offline, worker_online, quota_warning
        """
        if channels is None:
            channels = ["webhook"]

        for channel in channels:
            try:
                if channel == "webhook":
                    await self._send_webhook(event, data)
                elif channel == "email":
                    await self._send_email(event, data)
                elif channel == "telegram":
                    await self._send_telegram(event, data)
            except Exception as e:
                logger.error(f"Notification failed ({channel}): {e}")
                await self._log(user_id, event, channel, data, "failed", str(e))
                continue
            await self._log(user_id, event, channel, data, "sent", "")

    async def _log(self, user_id: str, event: str, channel: str, data: dict, status: str, error: str):
        """Log notification to DB."""
        try:
            from src.core.database import db
            await db.insert("notification_logs", {
                "id": _uid(),
                "user_id": user_id,
                "event": event,
                "channel": channel,
                "data": json.dumps(data, ensure_ascii=False, default=str),
                "status": status,
                "error": error,
                "created_at": datetime.now(timezone.utc).isoformat(),
            })
        except Exception as e:
            logger.error(f"Failed to log notification: {e}")

    async def _send_webhook(self, event: str, data: dict):
        from src.core.settings_manager import settings_manager
        url = await settings_manager.get("notification_webhook_url")
        if not url:
            url = await settings_manager.get("webhook_url")
        if not url:
            return
        async with httpx.AsyncClient(timeout=10) as client:
            await client.post(url, json={"event": event, "data": data})

    async def _send_email(self, event: str, data: dict):
        from src.core.settings_manager import settings_manager

        smtp_host = await settings_manager.get("notification_smtp_host")
        smtp_port = int(await settings_manager.get("notification_smtp_port") or 587)
        smtp_user = await settings_manager.get("notification_smtp_user")
        smtp_pass = await settings_manager.get("notification_smtp_pass")
        to_email = await settings_manager.get("notification_email_to")

        if not all([smtp_host, smtp_user, smtp_pass, to_email]):
            return

        subject = f"[AI Spider] {event}"
        body = f"事件: {event}\n\n详情:\n"
        for k, v in data.items():
            body += f"  {k}: {v}\n"

        msg = MIMEText(body, "plain", "utf-8")
        msg["Subject"] = subject
        msg["From"] = smtp_user
        msg["To"] = to_email

        await asyncio.to_thread(self._send_email_sync, msg, smtp_host, smtp_port, smtp_user, smtp_pass)

    def _send_email_sync(self, msg, host, port, user, passwd):
        with smtplib.SMTP(host, port) as server:
            server.starttls()
            server.login(user, passwd)
            server.send_message(msg)

    async def _send_telegram(self, event: str, data: dict):
        from src.core.settings_manager import settings_manager
        bot_token = await settings_manager.get("notification_telegram_bot_token")
        chat_id = await settings_manager.get("notification_telegram_chat_id")

        if not bot_token or not chat_id:
            return

        text = f"🕷️ *{event}*\n"
        for k, v in data.items():
            text += f"• {k}: {v}\n"

        async with httpx.AsyncClient(timeout=10) as client:
            await client.post(
                f"https://api.telegram.org/bot{bot_token}/sendMessage",
                json={"chat_id": chat_id, "text": text, "parse_mode": "Markdown"},
            )


notifier = Notifier()
