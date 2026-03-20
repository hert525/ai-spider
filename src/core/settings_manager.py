"""Centralized settings manager with DB persistence."""
from __future__ import annotations

from loguru import logger
from src.core.database import db

# 默认配置定义 — 按分类组织
DEFAULT_CONFIGS = [
    # === 基本设置 ===
    {"key": "site_name", "value": "AI Spider", "category": "general", "label": "站点名称", "description": "平台显示名称", "field_type": "text", "sort_order": 1},
    {"key": "site_description", "value": "AI驱动的智能爬虫平台", "category": "general", "label": "站点描述", "description": "平台描述信息", "field_type": "text", "sort_order": 2},
    {"key": "allow_registration", "value": "true", "category": "general", "label": "开放注册", "description": "是否允许新用户注册", "field_type": "boolean", "sort_order": 3},
    {"key": "default_user_role", "value": "user", "category": "general", "label": "默认用户角色", "description": "新注册用户的默认角色", "field_type": "select", "options": '["user","viewer"]', "sort_order": 4},
    {"key": "max_projects_per_user", "value": "10", "category": "general", "label": "用户项目上限", "description": "每个用户最多创建的项目数", "field_type": "number", "sort_order": 5},
    {"key": "max_tasks_per_day", "value": "100", "category": "general", "label": "每日任务上限", "description": "每个用户每天最多提交的任务数", "field_type": "number", "sort_order": 6},

    # === AI/LLM设置 ===
    {"key": "llm_provider", "value": "deepseek", "category": "ai", "label": "LLM 提供商", "description": "AI模型提供商", "field_type": "select", "options": '["deepseek","openai","anthropic","ollama","custom"]', "sort_order": 1},
    {"key": "llm_model", "value": "deepseek-chat", "category": "ai", "label": "模型名称", "description": "使用的模型", "field_type": "text", "sort_order": 2},
    {"key": "llm_api_key", "value": "", "category": "ai", "label": "API Key", "description": "LLM API密钥（留空使用环境变量）", "field_type": "password", "sort_order": 3},
    {"key": "llm_base_url", "value": "", "category": "ai", "label": "API Base URL", "description": "自定义API地址（留空使用默认）", "field_type": "text", "sort_order": 4},
    {"key": "llm_temperature", "value": "0.1", "category": "ai", "label": "Temperature", "description": "生成温度 0-2", "field_type": "number", "sort_order": 5},
    {"key": "llm_max_tokens", "value": "4096", "category": "ai", "label": "最大Token数", "description": "单次生成最大token", "field_type": "number", "sort_order": 6},
    {"key": "code_gen_max_retries", "value": "3", "category": "ai", "label": "代码生成重试次数", "description": "验证失败后最大重试", "field_type": "number", "sort_order": 7},
    {"key": "extract_prompt_language", "value": "zh", "category": "ai", "label": "提取语言", "description": "AI提取结果使用的语言", "field_type": "select", "options": '["zh","en"]', "sort_order": 8},

    # === 爬虫设置 ===
    {"key": "default_delay", "value": "1.0", "category": "crawler", "label": "默认请求延迟(秒)", "description": "两次请求之间的默认延迟", "field_type": "number", "sort_order": 1},
    {"key": "default_timeout", "value": "30", "category": "crawler", "label": "请求超时(秒)", "description": "HTTP请求超时时间", "field_type": "number", "sort_order": 2},
    {"key": "max_pages_per_task", "value": "100", "category": "crawler", "label": "单任务最大页数", "description": "一个任务最多爬取的页面数", "field_type": "number", "sort_order": 3},
    {"key": "default_user_agent", "value": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36", "category": "crawler", "label": "默认User-Agent", "description": "HTTP请求使用的UA", "field_type": "textarea", "sort_order": 4},
    {"key": "respect_robots_txt", "value": "true", "category": "crawler", "label": "遵守robots.txt", "description": "是否遵守网站的robots.txt规则", "field_type": "boolean", "sort_order": 5},
    {"key": "auto_playwright_fallback", "value": "true", "category": "crawler", "label": "自动Playwright降级", "description": "httpx失败时自动使用Playwright重试", "field_type": "boolean", "sort_order": 6},

    # === 沙箱设置 ===
    {"key": "sandbox_timeout", "value": "30", "category": "sandbox", "label": "执行超时(秒)", "description": "代码沙箱执行超时时间", "field_type": "number", "sort_order": 1},
    {"key": "sandbox_max_memory_mb", "value": "512", "category": "sandbox", "label": "内存上限(MB)", "description": "沙箱进程内存限制", "field_type": "number", "sort_order": 2},
    {"key": "sandbox_allowed_modules", "value": "httpx,parsel,json,re,csv,asyncio,bs4,lxml", "category": "sandbox", "label": "允许的Python模块", "description": "沙箱中可以import的模块(逗号分隔)", "field_type": "textarea", "sort_order": 3},
    {"key": "sandbox_network_enabled", "value": "true", "category": "sandbox", "label": "允许网络访问", "description": "沙箱中是否允许网络请求", "field_type": "boolean", "sort_order": 4},

    # === Worker设置 ===
    {"key": "worker_concurrency", "value": "3", "category": "worker", "label": "Worker并发数", "description": "每个Worker同时执行的任务数", "field_type": "number", "sort_order": 1},
    {"key": "worker_heartbeat_interval", "value": "15", "category": "worker", "label": "心跳间隔(秒)", "description": "Worker心跳上报间隔", "field_type": "number", "sort_order": 2},
    {"key": "worker_task_timeout", "value": "300", "category": "worker", "label": "任务超时(秒)", "description": "单个任务最大执行时间", "field_type": "number", "sort_order": 3},
    {"key": "worker_max_retries", "value": "3", "category": "worker", "label": "最大重试次数", "description": "任务失败后自动重试次数", "field_type": "number", "sort_order": 4},
    {"key": "worker_offline_threshold", "value": "60", "category": "worker", "label": "离线判定(秒)", "description": "超过此时间无心跳视为离线", "field_type": "number", "sort_order": 5},

    # === 存储设置 ===
    {"key": "default_sink_type", "value": "sqlite", "category": "storage", "label": "默认存储方式", "description": "数据默认存储位置", "field_type": "select", "options": '["sqlite","file","kafka","s3"]', "sort_order": 1},
    {"key": "data_retention_days", "value": "90", "category": "storage", "label": "数据保留天数", "description": "爬取数据保留时间(0=永久)", "field_type": "number", "sort_order": 2},
    {"key": "max_data_size_mb", "value": "1024", "category": "storage", "label": "数据存储上限(MB)", "description": "单个项目最大数据量", "field_type": "number", "sort_order": 3},
    {"key": "file_export_format", "value": "json", "category": "storage", "label": "默认导出格式", "description": "数据导出默认格式", "field_type": "select", "options": '["json","csv","jsonl"]', "sort_order": 4},

    # === 安全设置 ===
    {"key": "rate_limit_per_minute", "value": "60", "category": "security", "label": "API限流(次/分)", "description": "每分钟最大API调用次数", "field_type": "number", "sort_order": 1},
    {"key": "blocked_domains", "value": "", "category": "security", "label": "禁止爬取的域名", "description": "禁止爬取的域名列表(每行一个)", "field_type": "textarea", "sort_order": 2},
    {"key": "require_email_verification", "value": "false", "category": "security", "label": "需要邮箱验证", "description": "注册后是否需要邮箱验证", "field_type": "boolean", "sort_order": 3},
    {"key": "session_timeout_hours", "value": "24", "category": "security", "label": "会话超时(小时)", "description": "API Key有效时间(0=永久)", "field_type": "number", "sort_order": 4},
    {"key": "max_login_attempts", "value": "5", "category": "security", "label": "最大登录尝试", "description": "连续失败后锁定", "field_type": "number", "sort_order": 5},

    # === 通知设置 ===
    {"key": "notify_task_complete", "value": "false", "category": "notification", "label": "任务完成通知", "description": "任务完成时是否发送通知", "field_type": "boolean", "sort_order": 1},
    {"key": "notify_task_failed", "value": "true", "category": "notification", "label": "任务失败通知", "description": "任务失败时发送通知", "field_type": "boolean", "sort_order": 2},
    {"key": "notify_worker_offline", "value": "true", "category": "notification", "label": "Worker离线通知", "description": "Worker离线时发送通知", "field_type": "boolean", "sort_order": 3},
    {"key": "webhook_url", "value": "", "category": "notification", "label": "Webhook URL", "description": "通知发送的Webhook地址", "field_type": "text", "sort_order": 4},
    {"key": "notification_webhook_url", "value": "", "category": "notification", "label": "通知Webhook URL", "description": "全局通知Webhook地址", "field_type": "text", "sort_order": 5},
    {"key": "notification_smtp_host", "value": "", "category": "notification", "label": "SMTP主机", "description": "邮件通知SMTP服务器", "field_type": "text", "sort_order": 6},
    {"key": "notification_smtp_port", "value": "587", "category": "notification", "label": "SMTP端口", "description": "SMTP端口", "field_type": "number", "sort_order": 7},
    {"key": "notification_smtp_user", "value": "", "category": "notification", "label": "SMTP用户名", "description": "SMTP登录用户", "field_type": "text", "sort_order": 8},
    {"key": "notification_smtp_pass", "value": "", "category": "notification", "label": "SMTP密码", "description": "SMTP登录密码", "field_type": "password", "sort_order": 9},
    {"key": "notification_email_to", "value": "", "category": "notification", "label": "通知邮箱", "description": "接收通知的邮箱地址", "field_type": "text", "sort_order": 10},
    {"key": "notification_telegram_bot_token", "value": "", "category": "notification", "label": "Telegram Bot Token", "description": "Telegram Bot的API Token", "field_type": "password", "sort_order": 11},
    {"key": "notification_telegram_chat_id", "value": "", "category": "notification", "label": "Telegram Chat ID", "description": "接收通知的Telegram Chat ID", "field_type": "text", "sort_order": 12},
    {"key": "notification_events", "value": "task_failed,worker_offline", "category": "notification", "label": "通知事件", "description": "触发通知的事件类型(逗号分隔)", "field_type": "text", "sort_order": 13},

    # Browser / anti-detection
    {"key": "default_stealth_level", "value": "off", "category": "browser", "label": "默认反爬等级", "description": "新项目的默认反爬伪装等级", "field_type": "select", "options": '["off","basic","medium","full"]', "sort_order": 1},
    {"key": "screenshot_retention_days", "value": "7", "category": "browser", "label": "截图保留天数", "description": "自动清理超过此天数的截图", "field_type": "number", "sort_order": 2},
    {"key": "screenshot_max_storage_mb", "value": "500", "category": "browser", "label": "截图最大存储(MB)", "description": "截图目录最大占用空间", "field_type": "number", "sort_order": 3},
    {"key": "enable_screenshot_default", "value": "false", "category": "browser", "label": "默认开启截图", "description": "新项目是否默认开启截图存证", "field_type": "boolean", "sort_order": 4},
]


class SettingsManager:
    """Centralized settings manager."""

    def __init__(self):
        self._cache: dict[str, str] = {}

    async def init(self):
        """Initialize default configs if not exists."""
        for cfg in DEFAULT_CONFIGS:
            existing = await db.query("SELECT key FROM system_config WHERE key = ?", [cfg["key"]])
            if not existing:
                await db.insert("system_config", cfg)
        await self._refresh_cache()
        logger.info(f"Settings manager initialized with {len(self._cache)} configs")

    async def _refresh_cache(self):
        rows = await db.query("SELECT key, value FROM system_config")
        self._cache = {r["key"]: r["value"] for r in rows}

    async def get(self, key: str, default: str = "") -> str:
        return self._cache.get(key, default)

    async def get_bool(self, key: str, default: bool = False) -> bool:
        v = self._cache.get(key, str(default).lower())
        return v.lower() in ("true", "1", "yes")

    async def get_int(self, key: str, default: int = 0) -> int:
        try:
            return int(self._cache.get(key, str(default)))
        except (ValueError, TypeError):
            return default

    async def get_float(self, key: str, default: float = 0.0) -> float:
        try:
            return float(self._cache.get(key, str(default)))
        except (ValueError, TypeError):
            return default

    async def set(self, key: str, value: str, updated_by: str = ""):
        from datetime import datetime, timezone
        await db.execute(
            "UPDATE system_config SET value = ?, updated_at = ?, updated_by = ? WHERE key = ?",
            [value, datetime.now(timezone.utc).isoformat(), updated_by, key]
        )
        self._cache[key] = value

    async def get_by_category(self, category: str) -> list[dict]:
        return await db.query(
            "SELECT * FROM system_config WHERE category = ? ORDER BY sort_order",
            [category]
        )

    async def get_all_grouped(self) -> dict[str, list[dict]]:
        rows = await db.query("SELECT * FROM system_config ORDER BY category, sort_order")
        grouped: dict[str, list[dict]] = {}
        for r in rows:
            cat = r["category"]
            if cat not in grouped:
                grouped[cat] = []
            grouped[cat].append(r)
        return grouped

    async def reset_keys(self, keys: list[str] | None = None):
        """Reset specified keys (or all) to default values."""
        from datetime import datetime, timezone
        defaults = {c["key"]: c["value"] for c in DEFAULT_CONFIGS}
        if not keys:
            keys = list(defaults.keys())
        for key in keys:
            if key in defaults:
                await db.execute(
                    "UPDATE system_config SET value = ?, updated_at = ? WHERE key = ?",
                    [defaults[key], datetime.now(timezone.utc).isoformat(), key]
                )
        await self._refresh_cache()

    async def export_all(self) -> dict[str, str]:
        """Export all config as key-value dict."""
        rows = await db.query("SELECT key, value FROM system_config")
        return {r["key"]: r["value"] for r in rows}

    async def import_configs(self, data: dict[str, str], updated_by: str = ""):
        """Import config from key-value dict."""
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat()
        for key, value in data.items():
            existing = await db.query("SELECT key FROM system_config WHERE key = ?", [key])
            if existing:
                await db.execute(
                    "UPDATE system_config SET value = ?, updated_at = ?, updated_by = ? WHERE key = ?",
                    [value, now, updated_by, key]
                )
        await self._refresh_cache()


settings_manager = SettingsManager()
