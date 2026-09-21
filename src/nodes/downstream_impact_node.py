"""AgentCore Platform v1.0"""

# Inner subgraph node (Cat 2) — deterministic (no LLM) downstream impact list.
# Trust: ANONYMOUS — inner subgraph node (see ecr_content_extract_node.py).

from typing import Any, ClassVar

from framework.nodes.function_node import FunctionNode
from framework.schemas.agent_status import AgentStatus
from framework.schemas.trust_level import TrustLevel
from shared.utils.audit_logger import emit_trace_event
from src.services.ecr_rules_service import derive_downstream_impact


class DownstreamImpactNode(FunctionNode):
    """List affected parts/processes/suppliers — rule-based, deterministic, no LLM."""

    required_trust_level: ClassVar[TrustLevel] = TrustLevel.ANONYMOUS

    def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        ecr_metadata = state.get("ecr_metadata", {})
        if not ecr_metadata:
            return {
                "status": AgentStatus.ERROR.value,
                "error_log": ["DownstreamImpactNode: ecr_metadata missing"],
            }

        downstream_impact = derive_downstream_impact(ecr_metadata)

        emit_trace_event(
            "downstream_impact_derived",
            {"correlation_id": state.get("correlation_id"), "impact_entity_count": len(downstream_impact)},
            state,
        )
        return {"downstream_impact": downstream_impact, "status": AgentStatus.SUCCESS.value}
