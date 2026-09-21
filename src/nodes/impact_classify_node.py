"""AgentCore Platform v1.0"""

# Inner subgraph node (Cat 2) — LLM-based impact classification.
# Trust: ANONYMOUS — inner subgraph node (see ecr_content_extract_node.py).

from typing import Any, ClassVar

from framework.nodes.function_node import FunctionNode
from framework.schemas.agent_status import AgentStatus
from framework.schemas.trust_level import TrustLevel
from shared.utils.audit_logger import emit_trace_event

from src.services.llm_resolver import _UNSET, resolve_llm
from src.services.ecr_rules_service import (
    DEFAULT_CLASSIFICATION_CRITERIA,
    build_classification_prompt,
    parse_impact_level,
)


class ImpactClassifyNode(FunctionNode):
    """Classify ECR impact level: SAFETY_CRITICAL / MAJOR / MINOR / ADMINISTRATIVE.

    Classification is performed against ISO 9001 Section 8.3 + OEM-specific
    PPAP/APQP criteria. The criteria text is injectable via constructor
    (config-driven) so a customer-specific rubric can replace the placeholder
    without a code change — see docs/02_design.md.
    """

    required_trust_level: ClassVar[TrustLevel] = TrustLevel.ANONYMOUS

    def __init__(self, llm: Any = _UNSET, criteria: str = DEFAULT_CLASSIFICATION_CRITERIA):
        self._llm = llm
        self._criteria = criteria

    @staticmethod
    def _extract_text(raw: Any) -> str:
        # Canonical BaseLLM.complete() returns a dict {"content": str, ...}; a
        # string-fake (test double) may return a bare string. Normalize both
        # so downstream keyword-match never crashes on a real client.
        if isinstance(raw, dict):
            content = raw.get("content", "")
            return content if isinstance(content, str) else ""
        if isinstance(raw, str):
            return raw
        return ""

    def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        ecr_metadata = state.get("ecr_metadata", {})
        if not ecr_metadata:
            return {
                "status": AgentStatus.ERROR.value,
                "error_log": ["ImpactClassifyNode: ecr_metadata missing (upstream extraction failed)"],
            }

        prompt = build_classification_prompt(ecr_metadata, self._criteria)

        llm = resolve_llm(self._llm, state)
        if llm is None:
            # Deterministic-core mode: no LLM configured at all -> fallback default.
            impact_level = parse_impact_level("")
        else:
            try:
                raw_response = llm.complete(prompt)
            except Exception as exc:  # noqa: BLE001 - narrow classification below
                emit_trace_event(
                    "ecr_impact_classification_failed",
                    {"correlation_id": state.get("correlation_id"), "reason": str(exc)},
                    state,
                )
                return {
                    "status": AgentStatus.ERROR.value,
                    "error_log": [f"ImpactClassifyNode: LLM call failed: {exc}"],
                }

            text = self._extract_text(raw_response)
            if not text:
                emit_trace_event(
                    "ecr_impact_classification_failed",
                    {"correlation_id": state.get("correlation_id"), "reason": "empty LLM response"},
                    state,
                )
                return {
                    "status": AgentStatus.ERROR.value,
                    "error_log": ["ImpactClassifyNode: LLM returned an empty response"],
                }
            impact_level = parse_impact_level(text)

        emit_trace_event(
            "ecr_impact_classified",
            {"correlation_id": state.get("correlation_id"), "impact_level": impact_level},
            state,
        )
        return {"impact_level": impact_level, "status": AgentStatus.SUCCESS.value}
