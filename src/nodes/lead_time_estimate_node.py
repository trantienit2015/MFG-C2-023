"""AgentCore Platform v1.0"""

# Inner subgraph node (Cat 2) — deterministic (no LLM) lead-time estimation.
# Trust: ANONYMOUS — inner subgraph node (see ecr_content_extract_node.py).

from typing import Any, ClassVar

from framework.nodes.function_node import FunctionNode
from framework.schemas.agent_status import AgentStatus
from framework.schemas.trust_level import TrustLevel
from shared.utils.audit_logger import emit_trace_event
from src.services.ecr_rules_service import estimate_lead_time


class LeadTimeEstimateNode(FunctionNode):
    """Estimate the review lead time from impact_level + ppap_level — a simple
    rule-table lookup, deterministic, no LLM."""

    required_trust_level: ClassVar[TrustLevel] = TrustLevel.ANONYMOUS

    def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        impact_level = state.get("impact_level", "")
        ppap_level = state.get("ppap_level")
        if not impact_level or ppap_level is None:
            return {
                "status": AgentStatus.ERROR.value,
                "error_log": ["LeadTimeEstimateNode: impact_level/ppap_level missing"],
            }

        lead_time = estimate_lead_time(impact_level, ppap_level)

        emit_trace_event(
            "lead_time_estimated",
            {"correlation_id": state.get("correlation_id"), "business_days": lead_time["business_days"]},
            state,
        )
        return {"lead_time": lead_time, "status": AgentStatus.SUCCESS.value}
