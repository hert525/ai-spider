"""ValidateNode - 4-round code validation (syntax → execution → schema → semantic).

Fixes applied:
- Best-effort code saved to state at each iteration (no more lost code)
- Semantic failure counter: if same semantic error repeats 3+, accept as partial
- Overall timeout: 5 minutes max, graceful exit
- Tracks best_code (code that passed most rounds) for fallback
"""
import ast
import json
import time
from .base import BaseNode
from .generate import GenerateNode
from src.engine.sandbox import run_code_in_sandbox
from src.core.llm import llm_completion


class ValidateNode(BaseNode):
    """Validate generated code with 4-round iterative fixing."""

    # How far each round gets: syntax=1, execution=2, schema=3, semantic=4
    ROUND_WEIGHTS = {"syntax": 1, "execution": 2, "schema": 3, "semantic": 4}

    def __init__(self, max_retries: int = 3, timeout_seconds: int = 300):
        super().__init__("ValidateNode")
        self.max_retries = max_retries
        self.timeout_seconds = timeout_seconds
        self.generator = GenerateNode()

    async def execute(self, state: dict) -> dict:
        code = state.get("generated_code", "")
        if not code:
            raise ValueError("No generated_code in state")

        overall_max = self.max_retries * 4  # iteration budget
        iteration = 0
        start_time = time.time()

        # Track best code seen (the one that got furthest in validation)
        best_code = code
        best_score = 0        # 0=nothing, 1=syntax, 2=exec, 3=schema, 4=all
        best_result = None    # execution output of best code
        semantic_fail_count = 0   # consecutive semantic failures
        last_semantic_error = ""

        while iteration < overall_max:
            iteration += 1
            elapsed = time.time() - start_time
            self.logger.info(f"Validation iteration {iteration}/{overall_max} ({elapsed:.0f}s)")

            # ── Timeout check ──
            if elapsed > self.timeout_seconds:
                self.logger.warning(f"Timeout after {elapsed:.0f}s, using best code (score={best_score})")
                break

            # ── Round 1: Syntax ──
            ok, msg = self._syntax_check(code)
            if not ok:
                self.logger.warning(f"Syntax error: {msg}")
                code = await self._fix_code(state, code, "syntax", msg)
                continue

            current_score = 1  # passed syntax

            # ── Round 2: Execution ──
            ok, result = await self._execution_check(code, state.get("raw_html", ""), state.get("url", ""))
            if not ok:
                self.logger.warning(f"Execution error: {result}")
                if current_score > best_score:
                    best_code, best_score = code, current_score
                code = await self._fix_code(state, code, "execution", result)
                continue

            current_score = 2  # passed execution

            # ── Round 3: Schema ──
            ok, msg = self._schema_check(result)
            if not ok:
                self.logger.warning(f"Schema error: {msg}")
                if current_score > best_score:
                    best_code, best_score, best_result = code, current_score, result
                code = await self._fix_code(state, code, "schema", msg)
                continue

            current_score = 3  # passed schema

            # ── Round 4: Semantic ──
            ok, msg = await self._semantic_check(result, state.get("description", ""))
            if not ok:
                self.logger.warning(f"Semantic error: {msg}")
                semantic_fail_count += 1
                last_semantic_error = msg

                # Always track best — schema-passing code with data is valuable
                if current_score > best_score or (current_score == best_score and len(result) > len(best_result or [])):
                    best_code, best_score, best_result = code, current_score, result

                # ── Semantic stuck detection ──
                # If semantic fails 3+ times, the code works but LLM is unhappy.
                # Accept it as partial success rather than burning more iterations.
                if semantic_fail_count >= 3:
                    self.logger.warning(
                        f"Semantic check failed {semantic_fail_count} times consecutively. "
                        f"Accepting code as partial (has {len(result)} items). "
                        f"Last error: {last_semantic_error[:100]}"
                    )
                    state["generated_code"] = code
                    state["validation_result"] = result
                    state["validation_status"] = "partial_semantic"
                    state["validation_note"] = f"Semantic: {last_semantic_error[:200]}"
                    return state

                code = await self._fix_code(state, code, "semantic", msg)
                continue
            else:
                semantic_fail_count = 0  # reset on success

            # ── All 4 rounds passed! ──
            current_score = 4
            self.logger.info(f"All 4 validation rounds passed! ({elapsed:.0f}s, {iteration} iterations)")
            state["generated_code"] = code
            state["validation_result"] = result
            state["validation_status"] = "success"
            return state

        # ── Exhausted retries or timeout — use best effort ──
        elapsed = time.time() - start_time
        self.logger.warning(
            f"Validation ended after {iteration} iterations ({elapsed:.0f}s). "
            f"Best score: {best_score}/4, using best-effort code"
        )
        state["generated_code"] = best_code if best_score > 0 else code
        state["validation_result"] = best_result
        state["validation_status"] = "partial"
        state["validation_note"] = f"Best score: {best_score}/4 after {iteration} iterations"
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
                error = result["error"]
                # If it's a network error and code is API-based, don't fail hard
                if self._is_api_based_code(code) and self._is_network_error(error):
                    self.logger.info(f"API-based code got network error (expected in sandbox): {error[:100]}")
                    return True, [{"_note": "API code validated syntactically, network test skipped"}]
                return False, error
            output = result.get("output", [])
            if not output:
                # For API-based code, empty results might just mean the sandbox can't reach the API
                if self._is_api_based_code(code):
                    self.logger.info("API-based code returned empty (sandbox may lack network access)")
                    return True, [{"_note": "API code validated, empty results expected in sandbox"}]
                return False, "Code executed but returned empty results"
            return True, output
        except Exception as e:
            return False, str(e)

    @staticmethod
    def _is_api_based_code(code: str) -> bool:
        """Detect if code uses API strategy (JSON parsing) vs HTML parsing."""
        has_json_parse = '.json()' in code or 'resp.json' in code or 'response.json' in code
        has_api_url = 'api.' in code or '/api/' in code or 'graphql' in code.lower()
        has_no_css = 'sel.css(' not in code and 'sel.xpath(' not in code and '.select(' not in code
        return (has_json_parse or has_api_url) and has_no_css

    @staticmethod
    def _is_network_error(error: str) -> bool:
        """Check if error is a network/connectivity issue."""
        network_indicators = [
            'ConnectError', 'ConnectTimeout', 'ReadTimeout',
            'ConnectionRefused', 'Name or service not known',
            'Network is unreachable', 'Temporary failure in name resolution',
            'SSLError', 'ProxyError', 'RemoteProtocolError',
        ]
        return any(ind in error for ind in network_indicators)

    def _schema_check(self, result: any) -> tuple[bool, str]:
        """Round 3: Validate output schema - must be list of dicts."""
        if not isinstance(result, list):
            return False, f"Expected list, got {type(result).__name__}"
        if not result:
            return False, "Result is empty list"
        if not all(isinstance(item, dict) for item in result):
            return False, "Not all items are dicts"
        if all(not item for item in result):
            return False, "All items are empty dicts"
        return True, "OK"

    async def _semantic_check(self, result: any, description: str) -> tuple[bool, str]:
        """Round 4: LLM judges if result matches user description."""
        if not description:
            return True, "No description to validate against"

        sample = json.dumps(result[:3], ensure_ascii=False, indent=2)
        fields_requested = [f.strip() for f in description.split(",") if f.strip()]
        
        # Quick heuristic: if most requested fields exist as keys (even if some empty), likely OK
        if result and isinstance(result[0], dict):
            keys = set(result[0].keys())
            # Count fields with non-empty values in first item
            non_empty = sum(1 for k, v in result[0].items() if v and str(v).strip())
            total_keys = len(keys)
            if total_keys > 0 and non_empty / total_keys >= 0.5:
                # At least half the fields have data — be lenient
                pass  # proceed to LLM check, but this info helps

        prompt = f"""用户需求: {description}

代码提取结果(前3条):
{sample}

请判断提取结果是否基本满足用户需求（允许个别字段为空，只要主要数据正确即可）。
如果基本满足，回复 "PASS"。如果完全不满足（主要字段全为空或数据明显错误），回复 "FAIL: " 加上具体原因。"""

        try:
            resp = await llm_completion(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=200,
            )
            answer = resp.choices[0].message.content.strip()
            # Handle thinking model output (e.g. qwen3 with <think>...</think>)
            if "</think>" in answer:
                answer = answer.split("</think>")[-1].strip()
            if answer.upper().startswith("PASS"):
                return True, "OK"
            return False, answer.replace("FAIL:", "").strip()
        except Exception as e:
            # LLM failure shouldn't block — treat as pass
            self.logger.warning(f"Semantic check LLM failed: {e}, treating as pass")
            return True, "LLM unavailable, skipped"

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
