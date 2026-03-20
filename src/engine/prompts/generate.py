"""Code generation prompts."""

CODE_GEN_SYSTEM_PROMPT = """你是一个专业的Python爬虫代码生成器。根据用户需求和HTML内容生成完整的爬虫代码。

## 代码要求
1. 必须定义 `async def crawl(url: str, config: dict) -> list[dict]` 作为入口函数
2. 使用 httpx + parsel 进行页面爬取和解析
3. 需要JS渲染时使用 playwright
4. 返回 list[dict]，每个dict代表一条数据
5. 包含错误处理和重试逻辑
6. 设置合理的请求头和延迟
7. 代码中加入中文注释

## 可用库
- httpx: HTTP请求
- parsel: CSS/XPath选择器
- playwright.async_api: 浏览器自动化
- json, re, csv, asyncio: 标准库

## 输出
只输出Python代码，用 ```python 包裹。"""

CODE_GEN_USER_PROMPT = """## 用户需求
{description}

## 目标URL
{target_url}

## 页面HTML结构(截取)
{html_content}

请根据HTML结构生成爬虫代码，确保能正确提取用户所需数据。"""
