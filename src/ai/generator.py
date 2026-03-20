"""
AI Engine - Generate and refine crawler code from natural language.
"""
import json
from typing import AsyncIterator
from loguru import logger
from litellm import acompletion

from src.core.config import settings

SYSTEM_PROMPT = """你是一个专业的Python爬虫代码生成器。用户会用自然语言描述他们想要爬取的数据，你需要生成完整可运行的Python爬虫代码。

## 代码要求

1. 必须定义一个 `async def crawl(url: str, config: dict) -> list[dict]` 函数作为入口
2. 使用 httpx + parsel 进行静态页面爬取，需要JS渲染时使用 playwright
3. 返回结构化的字典列表，每个字典代表一条数据
4. 包含完善的错误处理和重试逻辑
5. 遵守 robots.txt，设置合理的请求间隔
6. 代码中加入中文注释说明关键步骤

## 可用的库（已安装）

- httpx: HTTP请求
- parsel: CSS/XPath选择器解析
- playwright.async_api: 浏览器自动化（需要JS渲染时用）
- json, re, csv: 标准库
- asyncio: 异步

## 输出格式

只输出Python代码，不要其他解释。代码用 ```python 包裹。
"""

REFINE_PROMPT = """用户对上一版爬虫代码提出了修改意见。请根据反馈修改代码。

## 当前代码
```python
{current_code}
```

## 上次测试结果（前5条）
```json
{test_results}
```

## 用户反馈
{feedback}

请输出修改后的完整代码，用 ```python 包裹。只输出代码，不要其他解释。
"""


def _build_llm_params() -> dict:
    """Build LiteLLM completion params from settings."""
    model = settings.llm_model
    # LiteLLM requires provider prefix
    if settings.llm_provider and "/" not in model:
        model = f"{settings.llm_provider}/{model}"
    params = {"model": model, "api_key": settings.llm_api_key}
    if settings.llm_base_url:
        params["api_base"] = settings.llm_base_url
    elif settings.llm_provider == "deepseek":
        params["api_base"] = "https://api.deepseek.com/v1"
    return params


def _extract_code(text: str) -> str:
    """Extract Python code from LLM response."""
    if "```python" in text:
        code = text.split("```python", 1)[1]
        if "```" in code:
            code = code.split("```", 1)[0]
        return code.strip()
    if "```" in text:
        code = text.split("```", 1)[1]
        if "```" in code:
            code = code.split("```", 1)[0]
        return code.strip()
    return text.strip()


async def generate_crawler(description: str, target_url: str = "") -> str:
    """
    Generate crawler code from natural language description.

    Args:
        description: Natural language description of what to crawl
        target_url: Optional target URL for context

    Returns:
        Generated Python code string
    """
    user_msg = description
    if target_url:
        user_msg += f"\n\n目标网址: {target_url}"

    params = _build_llm_params()
    response = await acompletion(
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ],
        temperature=0.3,
        max_tokens=4096,
        **params,
    )

    raw = response.choices[0].message.content
    code = _extract_code(raw)
    logger.info(f"Generated crawler code: {len(code)} chars")
    return code


async def refine_crawler(
    current_code: str,
    feedback: str,
    test_results: list[dict] | None = None,
) -> str:
    """
    Refine crawler code based on user feedback.

    Args:
        current_code: Current version of the code
        feedback: User's natural language feedback
        test_results: Results from the last test run

    Returns:
        Refined Python code string
    """
    results_str = json.dumps(test_results[:5] if test_results else [], ensure_ascii=False, indent=2)
    prompt = REFINE_PROMPT.format(
        current_code=current_code,
        test_results=results_str,
        feedback=feedback,
    )

    params = _build_llm_params()
    response = await acompletion(
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        temperature=0.3,
        max_tokens=4096,
        **params,
    )

    raw = response.choices[0].message.content
    code = _extract_code(raw)
    logger.info(f"Refined crawler code: {len(code)} chars")
    return code


async def generate_crawler_stream(description: str, target_url: str = "") -> AsyncIterator[str]:
    """
    Stream-generate crawler code (for real-time display in frontend).
    """
    user_msg = description
    if target_url:
        user_msg += f"\n\n目标网址: {target_url}"

    params = _build_llm_params()
    response = await acompletion(
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ],
        temperature=0.3,
        max_tokens=4096,
        stream=True,
        **params,
    )

    async for chunk in response:
        delta = chunk.choices[0].delta
        if delta and delta.content:
            yield delta.content
