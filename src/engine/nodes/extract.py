"""ExtractNode - LLM-based structured data extraction from HTML."""
import json
from .base import BaseNode
from src.core.llm import llm_completion
from src.core.config import settings
from src.engine.prompts.extract import EXTRACT_SYSTEM_PROMPT, EXTRACT_USER_PROMPT


class ExtractNode(BaseNode):
    """Use LLM to extract structured data directly from HTML/text."""

    def __init__(self):
        super().__init__("ExtractNode")

    async def execute(self, state: dict) -> dict:
        description = state.get("description", "")
        reduced_html = state.get("reduced_html", "")
        clean_text = state.get("clean_text", "")

        if not description:
            raise ValueError("No description in state")

        # Use reduced HTML if available, otherwise clean text
        content = reduced_html[:30000] if reduced_html else clean_text[:30000]

        prompt = EXTRACT_USER_PROMPT.format(
            description=description,
            content=content,
        )

        self.logger.info("Calling LLM for extraction...")
        resp = await llm_completion(
            messages=[
                {"role": "system", "content": EXTRACT_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=0.1,
        )

        result_text = resp.choices[0].message.content
        extracted = self._parse_json(result_text)

        state["extracted_data"] = extracted
        state["llm_response"] = result_text
        self.logger.info(f"Extracted {len(extracted) if isinstance(extracted, list) else 1} items")
        return state

    def _parse_json(self, text: str) -> list | dict:
        """Extract JSON from LLM response."""
        # Try direct parse
        text = text.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            lines = lines[1:]  # remove ```json
            text = "\n".join(lines)
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            # Try to find JSON in text
            import re
            match = re.search(r'[\[{].*[}\]]', text, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group())
                except json.JSONDecodeError:
                    pass
            return [{"raw": text}]
