"""Notification system — email, webhook, telegram.

Supports per-user notification_configs with fallback to global settings.
"""
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

    async def _get_user_config(self, user_id: str) -> dict | None:
        """Load user's notification_configs row, return None if not found or disabled."""
        if not user_id:
            return None
        try:
            from src.core.database import db
            rows = await db.query(
                "SELECT * FROM notification_configs WHERE user_id = ? AND enabled = 1",
                [user_id],
            )
            if rows:
                cfg = rows[0]
                if isinstance(cfg.get("events"), str):
                    try:
                        cfg["events"] = json.loads(cfg["events"])
                    except Exception:
                        cfg["events"] = ["task_failed"]
                return cfg
        except Exception as e:
            logger.warning(f"Failed to load user notification config: {e}")
        return None

    async def _resolve_channels(self, event: str, channels: list[str] | None, user_id: str) -> tuple[list[str], dict | None]:
        """Determine which channels to send to.

        Priority:
        1. If channels explicitly provided, use those
        2. If user has notification_configs, use their configured channels + check event filter
        3. Fallback to ["webhook"] with global settings
        
        Returns (channels, user_config_or_None)
        """
        user_cfg = await self._get_user_config(user_id)

        if channels is not None:
            return channels, user_cfg

        if user_cfg:
            # Check event filter
            allowed_events = user_cfg.get("events", ["task_failed"])
            if event not in allowed_events and event != "test_notification":
                return [], user_cfg

            # Determine channels from user config
            resolved = []
            if user_cfg.get("webhook_url"):
                resolved.append("webhook")
            if user_cfg.get("email"):
                resolved.append("email")
            if user_cfg.get("telegram_chat_id"):
                resolved.append("telegram")
            return resolved, user_cfg

        return ["webhook"], None

    async def notify(self, event: str, data: dict, channels: list[str] | None = None, user_id: str = ""):
        """Send notification to configured channels.

        Events: task_completed, task_failed, worker_offline, worker_online, quota_warning, test_notification
        """
        resolved_channels, user_cfg = await self._resolve_channels(event, channels, user_id)

        if not resolved_channels:
            return

        for channel in resolved_channels:
            try:
                if channel == "webhook":
                    await self._send_webhook(event, data, user_cfg)
                elif channel == "email":
                    await self._send_email(event, data, user_cfg)
                elif channel == "telegram":
                    await self._send_telegram(event, data, user_cfg)
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

    async def _send_webhook(self, event: str, data: dict, user_cfg: dict | None = None):
        url = None
        if user_cfg:
            url = user_cfg.get("webhook_url")
        if not url:
            from src.core.settings_manager import settings_manager
            url = await settings_manager.get("notification_webhook_url")
            if not url:
                url = await settings_manager.get("webhook_url")
        if not url:
            return
        async with httpx.AsyncClient(timeout=10) as client:
            await client.post(url, json={"event": event, "data": data})

    async def _send_email(self, event: str, data: dict, user_cfg: dict | None = None):
        from src.core.settings_manager import settings_manager

        # User-level email target
        to_email = None
        if user_cfg:
            to_email = user_cfg.get("email")

        # Global SMTP settings (always from global config)
        smtp_host = await settings_manager.get("notification_smtp_host")
        smtp_port = int(await settings_manager.get("notification_smtp_port") or 587)
        smtp_user = await settings_manager.get("notification_smtp_user")
        smtp_pass = await settings_manager.get("notification_smtp_pass")
        if not to_email:
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
        with smtplib.SMTP(host, port, timeout=15) as server:
            server.starttls()
            server.login(user, passwd)
            server.send_message(msg)

    async def _send_telegram(self, event: str, data: dict, user_cfg: dict | None = None):
        bot_token = None
        chat_id = None

        if user_cfg:
            bot_token = user_cfg.get("telegram_bot_token")
            chat_id = user_cfg.get("telegram_chat_id")

        # Fallback to global settings
        if not bot_token or not chat_id:
            from src.core.settings_manager import settings_manager
            if not bot_token:
                bot_token = await settings_manager.get("notification_telegram_bot_token")
            if not chat_id:
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
