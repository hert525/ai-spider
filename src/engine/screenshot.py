"""Screenshot capture for crawl evidence."""
from __future__ import annotations

import os, time
from pathlib import Path
from loguru import logger

SCREENSHOT_DIR = Path("data/screenshots")


class ScreenshotManager:
    def __init__(self):
        SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)

    async def capture(self, page, task_id: str, step: str = "result") -> str:
        """Capture screenshot and return file path."""
        timestamp = int(time.time())
        filename = f"{task_id}_{step}_{timestamp}.png"
        filepath = SCREENSHOT_DIR / filename

        await page.screenshot(path=str(filepath), full_page=True)
        logger.info(f"Screenshot saved: {filepath}")
        return str(filepath)

    async def capture_element(self, page, selector: str, task_id: str, step: str = "element") -> str:
        """Capture screenshot of a specific element."""
        timestamp = int(time.time())
        filename = f"{task_id}_{step}_{timestamp}.png"
        filepath = SCREENSHOT_DIR / filename

        element = await page.query_selector(selector)
        if element:
            await element.screenshot(path=str(filepath))
        else:
            await page.screenshot(path=str(filepath), full_page=True)

        return str(filepath)

    def list_screenshots(self, task_id: str) -> list[dict]:
        """List all screenshots for a task."""
        screenshots = []
        for f in SCREENSHOT_DIR.glob(f"{task_id}_*"):
            screenshots.append({
                "filename": f.name,
                "path": str(f),
                "size": f.stat().st_size,
                "created": f.stat().st_ctime,
            })
        return sorted(screenshots, key=lambda x: x["created"])

    def cleanup(self, max_age_days: int = 7):
        """Delete old screenshots."""
        cutoff = time.time() - max_age_days * 86400
        count = 0
        for f in SCREENSHOT_DIR.glob("*.png"):
            if f.stat().st_ctime < cutoff:
                f.unlink()
                count += 1
        if count:
            logger.info(f"Cleaned up {count} old screenshots")


screenshot_manager = ScreenshotManager()
