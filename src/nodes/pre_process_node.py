"""AgentCore Platform v1.0"""

# Outer node (Cat 2 backbone). Trust: VERIFIED_EXTERNAL - matches this
# agent's config/agent.yaml required_trust_level (outer boundary receiving
# input directly from the caller - the security/contract reference doc S-1).

import json
from typing import Any, ClassVar

from framework.nodes.function_node import FunctionNode
from framework.schemas.agent_status import AgentStatus
from framework.schemas.trust_level import TrustLevel
from shared.utils.audit_logger import emit_trace_event

from src.services.progress import emit_progress


class PreProcessNode(FunctionNode):
    """Validate the raw ECR input and serialize it for the inner subgraph.

    The inner Cat 2 subgraph does not see the outer state - GraphNode only
    forwards a single string (validated_input). This node accepts either a
    JSON string or a dict-shaped ECR document as user_input, validates it is
    non-empty, and re-serializes it as the JSON envelope the inner graph's
    first node (ECRContentExtractNode) expects.
    """

    required_trust_level: ClassVar[TrustLevel] = TrustLevel.VERIFIED_EXTERNAL

    def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        emit_progress("Validating the ECR document.", "pre_process")
        user_input = state.get("user_input", "")

        ecr_document: dict[str, Any] | str | None
        if isinstance(user_input, dict):
            ecr_document = user_input
        elif isinstance(user_input, str) and user_input.strip():
            try:
                parsed = json.loads(user_input)
                ecr_document = parsed.get("ecr_document", parsed) if isinstance(parsed, dict) else user_input
            except ValueError:
                # Not JSON - treat as a free-text ECR document body.
                ecr_document = user_input
        else:
            ecr_document = None

        if not ecr_document:
            emit_trace_event(
                "ecr_input_rejected",
                {"correlation_id": state.get("correlation_id")},
                state,
            )
            return {
                "status": AgentStatus.ERROR.value,
                "error_log": ["PreProcessNode: user_input is empty or missing"],
            }

        validated_input = json.dumps({"ecr_document": ecr_document}, ensure_ascii=False)
        emit_trace_event(
            "ecr_input_validated",
            {"correlation_id": state.get("correlation_id")},
            state,
        )
        return {
            "validated_input": validated_input,
            "status": AgentStatus.SUCCESS.value,
        }
