"""Code refinement prompts."""

REFINE_CODE_PROMPT = """## 当前代码
```python
{code}
```

## 错误类型: {error_type}
## 错误信息
{error_message}

## 分析
{analysis}

## 原始需求
{description}

## 页面HTML(截取)
{html_content}

请修复代码中的问题。

## 诊断思路
1. 如果返回空结果且HTML看起来是SPA框架（React/Vue/Next.js）→ 数据不在HTML中，需要**直接请求后端API获取JSON数据**
2. 如果CSS选择器不匹配 → 对照HTML用正确的选择器
3. 如果数据在 `<script>` 标签中 → 用正则提取JSON

## 沙箱限制
- 只能import白名单模块: httpx, parsel, bs4, lxml, json, re, csv, math, time, datetime, asyncio, collections, itertools, functools, string, hashlib, base64, html, urllib.parse
- 禁止: os, subprocess, sys, pathlib, socket, pickle, playwright 等
- 禁止: open(), eval(), exec(), compile()
- 不要用 asyncio.run()，直接用 await
- 检查 config.get("pre_rendered_html")，如果是SPA空壳则改用API请求策略
- 不要在沙箱里启动 playwright，浏览器渲染由外部系统处理
- ⚠️ httpx注意事项（极重要）：
  - `resp = await client.get(url)` — get/post是协程，必须await
  - `data = resp.json()` — json()是普通方法，不要await！
  - `text = resp.text` — text是属性不是方法，不要加括号！不要await！
  - 这和aiohttp完全不同

只输出修改后的完整代码，用 ```python 包裹。"""

REFINE_WITH_FEEDBACK_PROMPT = """## 当前代码
```python
{code}
```

## 上次测试结果(前5条)
```json
{test_results}
```

## 用户反馈
{feedback}

请根据反馈修改代码。只输出完整代码，用 ```python 包裹。"""
