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
            content = (
                "[SPA检测] 此页面是SPA应用（React/Vue/Next.js），HTML中不包含实际数据。"
                "数据由JavaScript动态加载，通常来自后端API。"
                "请使用策略A（直接请求API）获取数据，不要用CSS选择器解析HTML。\n\n"
                + content[:15000]
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
        return text.strip()
