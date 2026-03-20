"""Logging configuration with loguru."""
from __future__ import annotations

import sys
from pathlib import Path

from loguru import logger

LOG_DIR = Path(__file__).parent.parent.parent / "data" / "logs"


def setup_logging():
    """Configure loguru for the application."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    # Remove default handler
    logger.remove()

    # Console output (colored)
    logger.add(
        sys.stderr,
        level="INFO",
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level:8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>",
    )

    # File output (rotating)
    logger.add(
        str(LOG_DIR / "spider_{time:YYYY-MM-DD}.log"),
        rotation="00:00",
        retention="30 days",
        level="DEBUG",
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level:8} | {name}:{function}:{line} - {message}",
        encoding="utf-8",
    )

    # Error log (separate file)
    logger.add(
        str(LOG_DIR / "error_{time:YYYY-MM-DD}.log"),
        rotation="00:00",
        retention="60 days",
        level="ERROR",
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level:8} | {name}:{function}:{line} - {message}",
        encoding="utf-8",
    )
