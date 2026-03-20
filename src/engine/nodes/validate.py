"""ValidateNode - 4-round code validation (syntax → execution → schema → semantic)."""
import ast
import json
from litellm import acompletion
from .base import BaseNode
from .generate import GenerateNode
from src.engine.sandbox import run_code_in_sandbox
from src.core.config import settings


class ValidateNode(BaseNode):
    """Validate generated code with 4-round iterative fixing.
    
    Round 1: Syntax check (ast.parse)
    Round 2: Sandbox execution check
    Round 3: Output schema validation
    Round 4: Semantic validation (LLM judges if output matches description)
    """

    def __init__(self, max_retries: int = 3):
        super().__init__("ValidateNode")
        self.max_retries = max_retries
        self.generator = GenerateNode()

    async def execute(self, state: dict) -> dict:
        code = state.get("generated_code", "")
        if not code:
            raise ValueError("No generated_code in state")

        overall_max = self.max_retries * 4  # total budget
        iteration = 0

        while iteration < overall_max:
            iteration += 1
            self.logger.info(f"Validation iteration {iteration}")

            # Round 1: Syntax
            ok, msg = self._syntax_check(code)
            if not ok:
                self.logger.warning(f"Syntax error: {msg}")
                code = await self._fix_code(state, code, "syntax", msg)
                continue

            # Round 2: Execution
            ok, result = await self._execution_check(code, state.get("raw_html", ""), state.get("url", ""))
            if not ok:
                self.logger.warning(f"Execution error: {result}")
                code = await self._fix_code(state, code, "execution", result)
                continue

            # Round 3: Schema validation
            ok, msg = self._schema_check(result)
            if not ok:
                self.logger.warning(f"Schema error: {msg}")
                code = await self._fix_code(state, code, "schema", msg)
                continue

            # Round 4: Semantic validation
            ok, msg = await self._semantic_check(result, state.get("description", ""))
            if not ok:
                self.logger.warning(f"Semantic error: {msg}")
                code = await self._fix_code(state, code, "semantic", msg)
                continue

            # All checks passed
            self.logger.info("All 4 validation rounds passed!")
            state["generated_code"] = code
            state["validation_result"] = result
            state["validation_status"] = "success"
            return state

        # Exhausted retries - use best effort
        self.logger.warning("Max validation iterations reached, using current code")
        state["generated_code"] = code
        state["validation_status"] = "partial"
        return state

    def _syntax_check(self, code: str) -> tuple[bool, str]:
        """Round 1: Check Python syntax."""
        try:
            ast.parse(code)
            return True, "OK"
        except SyntaxError as e:
            return False, f"Line {e.lineno}: {e.msg}"

    async def _execution_check(self, code: str, html: str, url: str) -> tuple[bool, any]:
        """Round 2: Execute in sandbox."""
        try:
            result = await run_code_in_sandbox(code, url, html)
            if result.get("error"):
                return False, result["error"]
            output = result.get("output", [])
            if not output:
                return False, "Code executed but returned empty results"
            return True, output
        except Exception as e:
            return False, str(e)

    def _schema_check(self, result: any) -> tuple[bool, str]:
        """Round 3: Validate output schema - must be list of dicts."""
        if not isinstance(result, list):
            return False, f"Expected list, got {type(result).__name__}"
        if not result:
            return False, "Result is empty list"
        if not all(isinstance(item, dict) for item in result):
            return False, "Not all items are dicts"
        # Check for empty dicts
        if all(not item for item in result):
            return False, "All items are empty dicts"
        return True, "OK"

    async def _semantic_check(self, result: any, description: str) -> tuple[bool, str]:
        """Round 4: LLM judges if result matches user description."""
        if not description:
            return True, "No description to validate against"

        sample = json.dumps(result[:3], ensure_ascii=False, indent=2)
        prompt = f"""用户需求: {description}

代码提取结果(前3条):
{sample}

请判断提取结果是否满足用户需求。如果满足，回复 "PASS"。如果不满足，回复 "FAIL: " 加上具体原因。"""

        params = settings.get_llm_params()
        resp = await acompletion(
            **params,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=200,
        )
        answer = resp.choices[0].message.content.strip()
        if answer.upper().startswith("PASS"):
            return True, "OK"
        return False, answer.replace("FAIL:", "").strip()

    async def _fix_code(self, state: dict, code: str, error_type: str, error_msg: str) -> str:
        """Use LLM to fix code based on error."""
        state_copy = dict(state)
        state_copy["generated_code"] = code
        
        analysis = f"Error type: {error_type}\nError: {error_msg}"
        try:
            new_code = await self.generator.regenerate(state_copy, error_type, error_msg, analysis)
            return new_code
        except Exception as e:
            self.logger.error(f"Failed to regenerate code: {e}")
            return code
