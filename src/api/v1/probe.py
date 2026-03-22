"""站点探测 & 意图解析 API路由"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from src.core.auth import get_current_user

router = APIRouter()


# ── 站点探测 ──

class ProbeRequest(BaseModel):
    url: str


@router.post("/probe")
async def probe_site_api(req: ProbeRequest, user: dict = Depends(get_current_user)):
    """探测目标网站技术栈和反爬机制"""
    from src.engine.probe import probe_site
    result = await probe_site(req.url)
    return result


# ── 意图解析 ──

class IntentRequest(BaseModel):
    text: str


@router.post("/intent")
async def parse_intent_api(req: IntentRequest, user: dict = Depends(get_current_user)):
    """自然语言→爬虫任务参数"""
    from src.engine.intent_parser import parse_intent
    result = await parse_intent(req.text)
    return result
