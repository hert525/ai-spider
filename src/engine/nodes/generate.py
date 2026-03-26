"""GenerateNode - LLM code generation for crawlers."""
from .base import BaseNode
from src.core.llm import llm_completion
from src.core.config import settings
from src.engine.prompts.generate import CODE_GEN_SYSTEM_PROMPT, CODE_GEN_USER_PROMPT


class GenerateNode(BaseNode):
    """Generate Python crawler code using LLM."""

    def __init__(self):
        super().__init__("GenerateNode")

    async def execute(self, state: dict) -> dict:
        description = state.get("description", "")
        target_url = state.get("url", "")
        reduced_html = state.get("reduced_html", "")
        clean_text = state.get("clean_text", "")

        content = reduced_html[:25000] if reduced_html else clean_text[:25000]

        # SPA detection: guide LLM to use API strategy instead of CSS selectors
        if state.get("is_spa"):
            self.logger.info("SPA detected — injecting API strategy hint into prompt")

            # Try to probe common API endpoints and show the actual response structure to LLM
            api_hint = await self._probe_api(target_url)

            content = (
                "[SPA检测] 此页面是SPA应用（React/Vue/Next.js），HTML中不包含实际数据。"
                "数据由JavaScript动态加载，通常来自后端API。"
                "请使用策略A（直接请求API）获取数据，不要用CSS选择器解析HTML。\n"
                + api_hint + "\n\n"
                + content[:12000]
            )

        prompt = CODE_GEN_USER_PROMPT.format(
            description=description,
            target_url=target_url,
            html_content=content,
        )

        self.logger.info("Generating crawler code...")
        resp = await llm_completion(
            messages=[
                {"role": "system", "content": CODE_GEN_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
        )

        code = self._extract_code(resp.choices[0].message.content)
        state["generated_code"] = code
        self.logger.info(f"Generated {len(code)} chars of code")
        return state

    async def regenerate(self, state: dict, error_type: str, error_msg: str, analysis: str) -> str:
        """Regenerate code based on error feedback."""
        from src.engine.prompts.refine import REFINE_CODE_PROMPT
        
        prompt = REFINE_CODE_PROMPT.format(
            code=state.get("generated_code", ""),
            error_type=error_type,
            error_message=error_msg,
            analysis=analysis,
            description=state.get("description", ""),
            html_content=state.get("reduced_html", "")[:15000],
        )

        resp = await llm_completion(
            messages=[
                {"role": "system", "content": CODE_GEN_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
        )
        return self._extract_code(resp.choices[0].message.content)

    def _extract_code(self, text: str) -> str:
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
        # No code blocks — try to extract just the code part
        # Look for 'import' or 'async def' or 'def' as start markers
        lines = text.split('\n')
        code_start = None
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith(('import ', 'from ', 'async def ', 'def ', '#!')):
                code_start = i
                break
        if code_start is not None:
            return '\n'.join(lines[code_start:]).strip()
        # Last resort: return as-is but log warning
        self.logger.warning("Could not extract code block from LLM response, using raw text")
        return text.strip()

    async def _probe_api(self, target_url: str) -> str:
        """Try common API patterns for a URL and return a hint with actual response structure."""
        import httpx
        import json
        from urllib.parse import urlparse

        parsed = urlparse(target_url)
        domain = parsed.hostname or ""
        path = parsed.path.rstrip("/")

        # Build candidate API URLs based on common patterns
        candidates = []
        # Pattern: api.{domain}/api/...
        base_domain = domain.removeprefix("www.")
        # Extract path segments for hints
        # e.g. /zh/market-activity/stocks/aapl/historical → extract 'aapl', 'historical'
        segments = [s for s in path.split("/") if s and s not in ("zh", "en")]

        # Common API patterns
        candidates.append(f"https://api.{base_domain}/api/{'/'.join(segments[-3:])}")
        candidates.append(f"https://api.{base_domain}/api/{'/'.join(segments[-2:])}")
        candidates.append(f"https://{domain}/api/{'/'.join(segments[-3:])}")
        candidates.append(f"https://{domain}/api/{'/'.join(segments[-2:])}")
        candidates.append(f"https://{domain}/_next/data/{'/'.join(segments)}.json")

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json",
        }

        for api_url in candidates:
            try:
                async with httpx.AsyncClient(headers=headers, timeout=10, follow_redirects=True) as client:
                    resp = await client.get(api_url)
                    if resp.status_code == 200:
                        text = resp.text[:3000]
                        try:
                            data = json.loads(text)
                            # Truncate to show structure
                            preview = json.dumps(data, ensure_ascii=False, indent=2)[:2000]
                            self.logger.info(f"API probe hit: {api_url} → {len(resp.text)} chars")
                            return (
                                f"\n[API探测成功] 发现API: {api_url}\n"
                                f"响应JSON结构（前2000字符）:\n```json\n{preview}\n```\n"
                                f"请根据此真实JSON结构编写代码，确保字段路径正确！"
                            )
                        except json.JSONDecodeError:
                            continue
            except Exception:
                continue

        self.logger.info("API probe: no common API endpoints found")
        return ""
