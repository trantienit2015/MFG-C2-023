"""AgentCore Platform v1.0"""

# Inner subgraph node (Cat 2) — first step of the ECR classification workflow.
# Trust: ANONYMOUS — trust is authenticated once at the outer backbone; an
# inner node requiring more would be a privilege-escalation (see
# the security/contract reference doc S-1).

import json
from typing import Any, ClassVar

from framework.nodes.function_node import FunctionNode
from framework.schemas.agent_status import AgentStatus
from framework.schemas.trust_level import TrustLevel
from shared.utils.audit_logger import emit_trace_event
from src.services.ecr_rules_service import extract_ecr_metadata


class ECRContentExtractNode(FunctionNode):
    """Extract structured ECR change metadata from the free-text/structured input.

    The inner graph does not see the outer state — it only receives the
    string `user_input` seeded by GraphNode.extract_input() (the outer
    pre_process's validated_input, JSON-encoded). This node parses that JSON
    back into a payload dict and derives ecr_metadata from it.
    """

    required_trust_level: ClassVar[TrustLevel] = TrustLevel.ANONYMOUS

    def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        raw = state.get("user_input", "")
        try:
            payload = json.loads(raw) if isinstance(raw, str) else raw
        except (ValueError, TypeError):
            payload = None

        if not payload:
            emit_trace_event(
                "ecr_content_extract_failed",
                {"correlation_id": state.get("correlation_id")},
                state,
            )
            return {
                "status": AgentStatus.ERROR.value,
                "error_log": ["ECRContentExtractNode: no ECR payload in inner input"],
            }

        ecr_source = payload.get("ecr_document", payload) if isinstance(payload, dict) else payload
        ecr_metadata = extract_ecr_metadata(ecr_source)

        emit_trace_event(
            "ecr_content_extracted",
            {
                "correlation_id": state.get("correlation_id"),
                "affected_part_count": len(ecr_metadata.get("affected_parts", [])),
            },
            state,
        )
        return {"ecr_metadata": ecr_metadata, "status": AgentStatus.SUCCESS.value}
