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

请修复代码中的问题。只输出修改后的完整代码，用 ```python 包裹。"""

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
