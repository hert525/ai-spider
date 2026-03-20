"""
Project store - in-memory + file persistence for crawler projects.
"""
import json
from pathlib import Path
from typing import Optional
from loguru import logger

from src.core.models import CrawlerProject, CrawlerStatus
from src.core.config import BASE_DIR

STORE_DIR = BASE_DIR / "data" / "projects"


class ProjectStore:
    """Simple file-backed project store."""

    def __init__(self):
        self._projects: dict[str, CrawlerProject] = {}
        STORE_DIR.mkdir(parents=True, exist_ok=True)
        self._load_all()

    def _load_all(self):
        for f in STORE_DIR.glob("*.json"):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                proj = CrawlerProject(**data)
                self._projects[proj.id] = proj
            except Exception as e:
                logger.warning(f"Failed to load project {f}: {e}")

    def _save(self, proj: CrawlerProject):
        path = STORE_DIR / f"{proj.id}.json"
        path.write_text(proj.model_dump_json(indent=2), encoding="utf-8")

    def list(self) -> list[CrawlerProject]:
        return sorted(self._projects.values(), key=lambda p: p.updated_at, reverse=True)

    def get(self, project_id: str) -> Optional[CrawlerProject]:
        return self._projects.get(project_id)

    def create(self, **kwargs) -> CrawlerProject:
        proj = CrawlerProject(**kwargs)
        self._projects[proj.id] = proj
        self._save(proj)
        return proj

    def update(self, project_id: str, **kwargs) -> Optional[CrawlerProject]:
        proj = self._projects.get(project_id)
        if not proj:
            return None
        from datetime import datetime
        for k, v in kwargs.items():
            if hasattr(proj, k):
                setattr(proj, k, v)
        proj.updated_at = datetime.now()
        self._save(proj)
        return proj

    def delete(self, project_id: str) -> bool:
        if project_id in self._projects:
            del self._projects[project_id]
            path = STORE_DIR / f"{project_id}.json"
            path.unlink(missing_ok=True)
            return True
        return False


# Singleton
store = ProjectStore()
