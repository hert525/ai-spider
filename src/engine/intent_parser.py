"""
意图解析模块 — 自然语言→爬虫任务参数。

将用户的自然语言描述解析为结构化的爬虫任务配置。

用法::

    from src.engine.intent_parser import parse_intent
    result = await parse_intent("帮我爬取豆瓣电影Top250的名称和评分")
"""
from __future__ import annotations

import json
from loguru import logger

from src.core.llm import llm_completion


# 系统提示词：指导LLM将自然语言转换为爬虫任务参数
_SYSTEM_PROMPT = """你是一个爬虫意图解析器。用户会用自然语言描述他们想爬取的内容，你需要将其解析为结构化的爬虫任务参数。

请严格按照以下JSON格式输出（不要输出其他内容）：
{
  "url": "目标网站URL",
  "extract_fields": ["需要提取的字段列表"],
  "graph_type": "smart_scraper 或 code_generator",
  "description": "任务简要描述",
  "use_browser": false,
  "max_pages": 1,
  "confidence": 0.9
}

规则：
1. url: 根据用户描述推测最可能的目标URL，如果无法确定则留空字符串
2. extract_fields: 用户想要提取的数据字段，用中文
3. graph_type: 
   - "smart_scraper": 适用于大多数网页内容提取
   - "code_generator": 适用于需要复杂交互（登录、翻页等）的场景
4. use_browser: 如果目标网站需要JS渲染（SPA、动态加载）则为true
5. max_pages: 根据描述估算需要爬取的页数
6. confidence: 0-1之间，表示你对解析结果的信心程度

只输出JSON，不要输出其他解释文字。"""


async def parse_intent(text: str) -> dict:
    """
    解析用户自然语言意图，返回爬虫任务参数。

    参数:
        text: 用户的自然语言描述

    返回:
        解析后的任务参数dict
    """
    if not text or not text.strip():
        return {
            "error": "输入不能为空",
            "url": "",
            "extract_fields": [],
            "graph_type": "smart_scraper",
        }

    try:
        resp = await llm_completion(
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": text.strip()},
            ],
            temperature=0.0,
            max_tokens=1024,
        )

        # 提取LLM返回的文本
        content = resp.choices[0].message.content.strip()

        # 尝试从返回内容中提取JSON
        # 处理可能被markdown代码块包裹的情况
        if content.startswith("```"):
            # 去掉markdown代码块标记
            lines = content.split("\n")
            json_lines = []
            in_block = False
            for line in lines:
                if line.strip().startswith("```"):
                    in_block = not in_block
                    continue
                if in_block or not line.strip().startswith("```"):
                    json_lines.append(line)
            content = "\n".join(json_lines)

        result = json.loads(content)

        # 确保必要字段存在
        result.setdefault("url", "")
        result.setdefault("extract_fields", [])
        result.setdefault("graph_type", "smart_scraper")
        result.setdefault("description", "")
        result.setdefault("use_browser", False)
        result.setdefault("max_pages", 1)
        result.setdefault("confidence", 0.5)
        result["original_text"] = text

        logger.info(f"意图解析成功: '{text[:50]}' → {result.get('url', '')}")
        return result

    except json.JSONDecodeError as e:
        logger.warning(f"意图解析JSON解码失败: {e}")
        return {
            "error": f"LLM返回格式异常: {str(e)[:80]}",
            "url": "",
            "extract_fields": [],
            "graph_type": "smart_scraper",
            "original_text": text,
        }
    except Exception as e:
        logger.error(f"意图解析失败: {e}")
        return {
            "error": f"解析失败: {str(e)[:120]}",
            "url": "",
            "extract_fields": [],
            "graph_type": "smart_scraper",
            "original_text": text,
        }
