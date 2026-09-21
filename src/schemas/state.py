"""AgentCore Platform v1.0"""

# ADR-005: State must be a flat TypedDict (see ADR-005 for the prohibited
# alternatives). LangGraph checkpoints use msgpack serialization, so only
# plain serializable fields are allowed. Do NOT add credentials or secrets.
#
# This contract: every agent-specific field is
# wrapped in NotRequired[...] - a bare field would be absent from a resumed
# checkpoint (msgpack) or raise KeyError when a downstream node reads it
# before it is written. Nodes always read via state.get("field", default).

from typing import NotRequired

from framework.schemas.agent_state import AgentState


# Type-check note: the wheel ships no py.typed, so mypy resolves AgentState to
# Any and reports every NotRequired below as valid-type. The fields are correct
# (NotRequired is required here) -- the report is a packaging artifact, suppressed
# per field. Drop these ignores once the wheel ships py.typed.
class State(AgentState):
    """Agent state for MFG-C2-023 - ECR Classification & Impact Assessment.

    All shared fields (user_input, validated_input, status, session_id,
    node_history, error_log, hitl_*, etc.) are inherited from AgentState.
    Only ECR-domain-specific fields are declared below.
    """

    # Structured metadata extracted from the raw ECR document (change_id,
    # title, description, affected_parts/processes/suppliers, ...).
    ecr_metadata: NotRequired[dict]  # type: ignore[valid-type]

    # Classification result: SAFETY_CRITICAL | MAJOR | MINOR | ADMINISTRATIVE.
    impact_level: NotRequired[str]  # type: ignore[valid-type]

    # Advisory PPAP submission level recommendation, 0-5. Advisory only -
    # never a binding decision (see ppap_advisory_notice below).
    ppap_level: NotRequired[int]  # type: ignore[valid-type]

    # Rule-based list of affected parts/processes/suppliers derived from
    # ecr_metadata (deterministic, no LLM).
    downstream_impact: NotRequired[list]  # type: ignore[valid-type]

    # Estimated review lead time, e.g. {"business_days": 10, "basis": "..."}.
    lead_time: NotRequired[dict]  # type: ignore[valid-type]

    # Non-suppressible safety notice. Set (non-empty str) whenever
    # impact_level == "SAFETY_CRITICAL"; otherwise None.
    safety_notice: NotRequired[str | None]  # type: ignore[valid-type]

    # Non-suppressible "advisory only, not a binding decision" disclaimer.
    # Always set whenever ppap_level is present.
    ppap_advisory_notice: NotRequired[str | None]  # type: ignore[valid-type]

    # The assembled machine-readable assessment PostProcessNode produces, kept
    # separate from the prose in formatted_output (which is what the chat renders).
    # It must be declared here or LangGraph drops the channel and
    # get_output()["final_output"] comes back empty.
    ecr_assessment: NotRequired[dict]  # type: ignore[valid-type]
