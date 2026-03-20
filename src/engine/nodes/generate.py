"""GenerateNode - LLM code generation for crawlers."""
from litellm import acompletion
from .base import BaseNode
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

        prompt = CODE_GEN_USER_PROMPT.format(
            description=description,
            target_url=target_url,
            html_content=content,
        )

        self.logger.info("Generating crawler code...")
        params = settings.get_llm_params()
        resp = await acompletion(
            **params,
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

        params = settings.get_llm_params()
        resp = await acompletion(
            **params,
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
