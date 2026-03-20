"""Settings API - admin configuration management."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from src.core.auth import require_admin
from src.core.settings_manager import settings_manager

router = APIRouter(prefix="/admin/settings", tags=["settings"])


class ConfigUpdate(BaseModel):
    key: str
    value: str


class BatchUpdate(BaseModel):
    configs: list[ConfigUpdate]


class ResetRequest(BaseModel):
    keys: list[str] = []


class ImportRequest(BaseModel):
    data: dict[str, str]


@router.get("")
async def get_all_settings(user: dict = Depends(require_admin)):
    """Get all settings grouped by category."""
    return await settings_manager.get_all_grouped()


@router.get("/{category}")
async def get_category_settings(category: str, user: dict = Depends(require_admin)):
    """Get settings for a specific category."""
    items = await settings_manager.get_by_category(category)
    if not items:
        raise HTTPException(404, f"Category '{category}' not found")
    return items


@router.put("")
async def update_settings(body: BatchUpdate, user: dict = Depends(require_admin)):
    """Batch update settings."""
    updated_by = user.get("email", user.get("username", "admin"))
    for cfg in body.configs:
        await settings_manager.set(cfg.key, cfg.value, updated_by=updated_by)
    return {"ok": True, "updated": len(body.configs)}


@router.post("/reset")
async def reset_settings(body: ResetRequest, user: dict = Depends(require_admin)):
    """Reset settings to defaults."""
    await settings_manager.reset_keys(body.keys or None)
    return {"ok": True}


@router.post("/export")
async def export_settings(user: dict = Depends(require_admin)):
    """Export all settings as JSON."""
    data = await settings_manager.export_all()
    return {"data": data}


@router.post("/import")
async def import_settings(body: ImportRequest, user: dict = Depends(require_admin)):
    """Import settings from JSON."""
    updated_by = user.get("email", user.get("username", "admin"))
    await settings_manager.import_configs(body.data, updated_by=updated_by)
    return {"ok": True, "imported": len(body.data)}
