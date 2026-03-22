"""预置种子模板 — 从JSON文件加载"""
from __future__ import annotations

import json
from pathlib import Path
from loguru import logger

_SEEDS_FILE = Path(__file__).parent.parent.parent / "data" / "seed_templates_preset.json"


def _load_seeds() -> list[dict]:
    """从JSON文件加载种子模板"""
    if not _SEEDS_FILE.exists():
        logger.warning(f"种子模板文件不存在: {_SEEDS_FILE}")
        return []
    try:
        with open(_SEEDS_FILE, "r", encoding="utf-8") as f:
            templates = json.load(f)
        logger.info(f"加载了 {len(templates)} 个预置种子模板")
        return templates
    except Exception as e:
        logger.error(f"加载种子模板失败: {e}")
        return []


SEED_TEMPLATES = _load_seeds()
