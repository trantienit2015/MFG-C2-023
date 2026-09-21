"""AgentCore Platform v1.0"""

# Inner subgraph node (Cat 2) — LLM-based advisory PPAP-level recommendation.
# Trust: ANONYMOUS — inner subgraph node (see ecr_content_extract_node.py).

from typing import Any, ClassVar

from framework.nodes.function_node import FunctionNode
from framework.schemas.agent_status import AgentStatus
from framework.schemas.trust_level import TrustLevel
from shared.utils.audit_logger import emit_trace_event

from src.services.llm_resolver import _UNSET, resolve_llm
from src.services.ecr_rules_service import build_ppap_prompt, parse_ppap_level


class PPAPLevelRecommendNode(FunctionNode):
    """Recommend a PPAP submission level (0-5) — advisory only.

    This recommendation is never a binding decision. The non-suppressible
    "advisory only" disclaimer that must accompany every ppap_level in the
    final output is enforced downstream by SafetyGateNode (the last inner
    node), independent of what this node produces — see safety_gate_node.py.
    """

    required_trust_level: ClassVar[TrustLevel] = TrustLevel.ANONYMOUS

    def __init__(self, llm: Any = _UNSET):
        self._llm = llm

    @staticmethod
    def _extract_text(raw: Any) -> str:
        # Canonical BaseLLM.complete() returns a dict {"content": str, ...}; a
        # string-fake (test double) may return a bare string. Normalize both
        # so downstream digit-parsing never crashes on a real client.
        if isinstance(raw, dict):
            content = raw.get("content", "")
            return content if isinstance(content, str) else ""
        if isinstance(raw, str):
            return raw
        return ""

    def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        ecr_metadata = state.get("ecr_metadata", {})
        impact_level = state.get("impact_level", "")
        if not ecr_metadata or not impact_level:
            return {
                "status": AgentStatus.ERROR.value,
                "error_log": ["PPAPLevelRecommendNode: ecr_metadata/impact_level missing"],
            }

        prompt = build_ppap_prompt(ecr_metadata, impact_level)

        llm = resolve_llm(self._llm, state)
        if llm is None:
            # Deterministic-core mode: no LLM configured at all -> fallback default.
            ppap_level = parse_ppap_level("")
        else:
            try:
                raw_response = llm.complete(prompt)
            except Exception as exc:  # noqa: BLE001 - narrow classification below
                emit_trace_event(
                    "ppap_level_recommendation_failed",
                    {"correlation_id": state.get("correlation_id"), "reason": str(exc)},
                    state,
                )
                return {
                    "status": AgentStatus.ERROR.value,
                    "error_log": [f"PPAPLevelRecommendNode: LLM call failed: {exc}"],
                }

            text = self._extract_text(raw_response)
            if not text:
                emit_trace_event(
                    "ppap_level_recommendation_failed",
                    {"correlation_id": state.get("correlation_id"), "reason": "empty LLM response"},
                    state,
                )
                return {
                    "status": AgentStatus.ERROR.value,
                    "error_log": ["PPAPLevelRecommendNode: LLM returned an empty response"],
                }
            ppap_level = parse_ppap_level(text)

        emit_trace_event(
            "ppap_level_recommended",
            {"correlation_id": state.get("correlation_id"), "ppap_level": ppap_level},
            state,
        )
        return {"ppap_level": ppap_level, "status": AgentStatus.SUCCESS.value}
