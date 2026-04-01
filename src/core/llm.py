"""
统一LLM调用层 — 支持多Provider自动Fallback。

调用链: 主模型 → 备用模型列表 → 报错
避免单一Provider故障(余额不足/限流/宕机)导致整个系统不可用。

用法::

    from src.core.llm import llm_completion

    resp = await llm_completion(
        messages=[{"role": "user", "content": "Hello"}],
        temperature=0.0,
    )
"""
from __future__ import annotations

import os
from loguru import logger

# Fallback模型链（按优先级顺序）
# 格式: "provider/model" （litellm标准格式）
_FALLBACK_MODELS: list[str] = []


def _get_fallback_models() -> list[str]:
    """获取Fallback模型链"""
    global _FALLBACK_MODELS
    if _FALLBACK_MODELS:
        return _FALLBACK_MODELS

    # 从环境变量读取（逗号分隔）
    env_fallback = os.getenv("LLM_FALLBACK_MODELS", "").strip()
    if env_fallback:
        _FALLBACK_MODELS = [m.strip() for m in env_fallback.split(",") if m.strip()]
    return _FALLBACK_MODELS


async def llm_completion(
    messages: list[dict],
    model: str | None = None,
    temperature: float = 0.0,
    max_tokens: int = 4096,
    **kwargs,
) -> dict:
    """
    统一LLM调用，支持自动Fallback。

    1. 先用指定model（或默认model）
    2. 失败后按LLM_FALLBACK_MODELS顺序尝试
    3. 全部失败则raise最后的异常

    返回litellm的response对象。
    """
    from litellm import acompletion
    from src.core.config import settings

    # 主模型
    if model is None:
        model = settings.llm_model_string

    # 构建尝试列表: [主模型] + fallback
    models_to_try = [model] + _get_fallback_models()
    # 去重但保持顺序
    seen = set()
    unique_models = []
    for m in models_to_try:
        if m not in seen:
            seen.add(m)
            unique_models.append(m)

    # 主模型的额外参数（api_key/api_base）
    primary_params = settings.get_llm_params()
    primary_params.pop("model", None)  # model单独传

    last_error = None
    for i, m in enumerate(unique_models):
        try:
            # 主模型用配置的api_key/api_base；同provider的fallback也继承api_base
            if i == 0:
                extra = primary_params
            else:
                # fallback模型如果和主模型同provider，继承api_base
                _fb_provider = m.split("/")[0] if "/" in m else ""
                _pri_provider = unique_models[0].split("/")[0] if "/" in unique_models[0] else ""
                if _fb_provider == _pri_provider and "api_base" in primary_params:
                    extra = {"api_base": primary_params["api_base"]}
                else:
                    extra = {}
            # 过滤掉kwargs中已有的key
            call_extra = {k: v for k, v in extra.items() if k not in kwargs}
            resp = await acompletion(
                model=m,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                **call_extra,
                **kwargs,
            )
            if i > 0:
                logger.info(f"LLM Fallback成功: {unique_models[0]} → {m}")
            return resp
        except Exception as e:
            last_error = e
            error_msg = str(e)
            # 判断是否值得重试（余额不足/限流/服务不可用）
            retriable = any(kw in error_msg.lower() for kw in [
                "insufficient balance", "rate limit", "quota exceeded",
                "server error", "502", "503", "timeout", "connection",
            ])
            if retriable and i < len(unique_models) - 1:
                logger.warning(f"LLM调用失败 ({m}): {error_msg[:80]}... → 尝试 {unique_models[i+1]}")
                continue
            else:
                raise

    raise last_error  # type: ignore
