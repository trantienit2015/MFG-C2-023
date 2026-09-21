"""AgentCore Platform v1.0"""

# Inner subgraph node (Cat 2) — final step of the ECR classification workflow.
# Trust: ANONYMOUS — inner subgraph node (see ecr_content_extract_node.py).
#
# This is the single safety-critical enforcement point of the agent:
#   1. Whenever impact_level == "SAFETY_CRITICAL", a non-suppressible notice
#      requiring PPAP Level 3+ and QA approval MUST be attached.
#   2. Whenever a ppap_level is present, a non-suppressible "advisory only,
#      not a binding decision" disclaimer MUST be attached — independent of
#      the safety notice above.
#
# execute() sets both fields deterministically and unconditionally (this node
# is a fixed, always-executed step of the inner pipeline — there is no
# routing path around it). _extra_security_gate_output() is a second,
# independent enforcement layer (S-3 "preservation variant" — see
# the security/contract reference doc S-2/S-3): it re-checks this
# node's OWN output dict for internal consistency and repairs it in place if
# anything upstream (a future refactor, a bug) ever caused the two fields to
# drift out of sync with impact_level/ppap_level. It never raises and always
# returns a dict, per the framework's _extra_security_gate_output contract.

from typing import Any, ClassVar

from framework.nodes.function_node import FunctionNode
from framework.schemas.agent_status import AgentStatus
from framework.schemas.trust_level import TrustLevel
from shared.utils.audit_logger import emit_trace_event

SAFETY_CRITICAL_NOTICE = (
    "SAFETY_CRITICAL: this change requires PPAP Level 3 or higher and explicit "
    "QA approval before proceeding. This notice cannot be suppressed."
)
PPAP_ADVISORY_NOTICE = (
    "This PPAP level recommendation is advisory only and is NOT a binding decision. "
    "Final PPAP submission level must be confirmed by Quality Engineering."
)


def _compute_notices(impact_level: str, ppap_level: Any) -> tuple[str | None, str | None]:
    safety_notice = SAFETY_CRITICAL_NOTICE if impact_level == "SAFETY_CRITICAL" else None
    ppap_advisory_notice = PPAP_ADVISORY_NOTICE if ppap_level is not None else None
    return safety_notice, ppap_advisory_notice


class SafetyGateNode(FunctionNode):
    """Attach the non-suppressible SAFETY_CRITICAL + PPAP-advisory notices."""

    required_trust_level: ClassVar[TrustLevel] = TrustLevel.ANONYMOUS

    def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        impact_level = state.get("impact_level", "")
        ppap_level = state.get("ppap_level")

        safety_notice, ppap_advisory_notice = _compute_notices(impact_level, ppap_level)

        # The outer pre_process -> main edge is unconditional (fixed AgentBaseGraph
        # backbone) and this inner pipeline is wired as a straight sequence, so an
        # upstream failure (e.g. ECRContentExtractNode rejecting empty input) still
        # flows all the way down to this last node. Preserve that ERROR status
        # instead of unconditionally overwriting it with SUCCESS - this node adds
        # safety notices, it does not get to erase a real upstream failure.
        upstream_status = state.get("status")
        upstream_failed = upstream_status in (AgentStatus.ERROR.value, AgentStatus.ERROR.value)
        status = AgentStatus.ERROR.value if upstream_failed else AgentStatus.SUCCESS.value

        emit_trace_event(
            "safety_gate_evaluated",
            {
                "correlation_id": state.get("correlation_id"),
                "safety_notice_attached": safety_notice is not None,
                "ppap_advisory_attached": ppap_advisory_notice is not None,
                "upstream_failed": upstream_failed,
            },
            state,
        )
        return {
            "safety_notice": safety_notice,
            "ppap_advisory_notice": ppap_advisory_notice,
            "impact_level": impact_level,
            "ppap_level": ppap_level,
            "status": status,
        }

    def _extra_security_gate_output(self, state: dict[str, Any]) -> dict[str, Any]:
        """Preservation-variant S-3 hook: re-verify + repair notice consistency.

        Reads this node's own output keys (impact_level, ppap_level,
        safety_notice, ppap_advisory_notice — all echoed by execute() above)
        and, if they have drifted out of sync, deterministically recomputes
        the notices in place. Never raises, always returns a dict.
        """
        impact_level = state.get("impact_level", "")
        ppap_level = state.get("ppap_level")
        expected_safety, expected_advisory = _compute_notices(impact_level, ppap_level)

        if state.get("safety_notice") == expected_safety and state.get("ppap_advisory_notice") == expected_advisory:
            return state

        repaired = dict(state)
        repaired["safety_notice"] = expected_safety
        repaired["ppap_advisory_notice"] = expected_advisory
        return repaired
