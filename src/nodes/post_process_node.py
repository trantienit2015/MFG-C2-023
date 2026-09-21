"""AgentCore Platform v1.0"""

# Outer node (Cat 2 backbone). Trust: VERIFIED_EXTERNAL - matches this
# agent's config/agent.yaml required_trust_level (see pre_process_node.py).

from typing import Any, ClassVar

from framework.nodes.function_node import FunctionNode
from framework.schemas.agent_status import AgentStatus
from framework.schemas.trust_level import TrustLevel
from shared.utils.audit_logger import emit_trace_event

from src.services.progress import emit_progress


class PostProcessNode(FunctionNode):
    """Assemble the final ECR classification & impact assessment output.

    Fields (impact_level, ppap_level, downstream_impact, lead_time,
    safety_notice, ppap_advisory_notice) were already merged into the outer
    state by ECRWorkflowGraphNode.merge_output() - this node only shapes the
    final formatted_output the caller sees.
    """

    required_trust_level: ClassVar[TrustLevel] = TrustLevel.VERIFIED_EXTERNAL

    def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        emit_progress("Assembling the impact assessment.", "post_process")
        assessment = {
            "impact_level": state.get("impact_level"),
            "ppap_level": state.get("ppap_level"),
            "ppap_advisory_notice": state.get("ppap_advisory_notice"),
            "downstream_impact": state.get("downstream_impact", []),
            "lead_time": state.get("lead_time", {}),
            "safety_notice": state.get("safety_notice"),
        }

        emit_trace_event(
            "ecr_assessment_finalized",
            {
                "correlation_id": state.get("correlation_id"),
                "impact_level": assessment["impact_level"],
            },
            state,
        )
        # AgentBaseGraph.get_output() surfaces state["formatted_output"] as the
        # chat reply, so it must be human-readable prose — a dict here reaches the
        # change-board reviewer as raw JSON. The machine-readable contract for a
        # parent Cat 2 agent stays on ecr_assessment / final_output.
        return {
            "ecr_assessment": assessment,
            "formatted_output": self._render_assessment(state, assessment),
            "status": AgentStatus.SUCCESS.value,
        }

    @staticmethod
    def _plural(kind: str) -> str:
        """English plural for an entity_type label ("process" -> "processes")."""
        if kind.endswith(("s", "x", "z", "ch", "sh")):
            return kind + "es"
        return kind + "s"

    @classmethod
    def _render_assessment(cls, state: dict[str, Any], assessment: dict[str, Any]) -> str:
        """Render the ECR impact assessment as Markdown prose for a human reader."""
        metadata = state.get("ecr_metadata", {}) or {}
        raw_change_id = str(metadata.get("change_id") or "").strip()
        # "UNKNOWN" is the rule engine's internal placeholder for free-text input
        # that carried no ECR number; say so in words rather than showing the token.
        change_id = raw_change_id if raw_change_id and raw_change_id != "UNKNOWN" else "(no ECR number supplied)"
        title = str(metadata.get("title") or "").strip()
        impact = str(assessment.get("impact_level") or "UNKNOWN").upper()
        ppap = assessment.get("ppap_level")
        downstream = assessment.get("downstream_impact", []) or []
        lead_time = assessment.get("lead_time", {}) or {}

        head = "## Engineering Change Request — Impact Assessment"
        ident = f"**ECR:** {change_id}" + (f" · {title}" if title else "")
        verdict = f"**Impact level:** {impact}" + (f" · **PPAP level:** {ppap}" if ppap else "")

        if downstream:
            grouped: dict[str, Any] = {}
            for item in downstream:
                grouped.setdefault(str(item.get("entity_type", "other")), []).append(str(item.get("entity", "")))
            rows = [
                f"- **{cls._plural(kind)} affected ({len(names)}):** " + ", ".join(n for n in names if n)
                for kind, names in sorted(grouped.items())
            ]
            downstream_text = "### Downstream impact" + "\n" + "\n".join(rows)
        else:
            downstream_text = "### Downstream impact" + "\n" + "- No affected part, process or supplier was identified."

        days = lead_time.get("business_days") if isinstance(lead_time, dict) else None
        if days is not None:
            basis = str(lead_time.get("basis") or "").strip()
            lead_text = f"**Estimated review lead time:** {days} business day(s)"
            if basis:
                lead_text += f" — {basis}"
        else:
            lead_text = ""

        parts = [head, ident, verdict, downstream_text]
        if lead_text:
            parts.append(lead_text)

        # Safety and PPAP advisories are the actionable consequence — never drop them,
        # and keep them verbatim so the S-3 preservation check downstream still matches.
        safety = str(assessment.get("safety_notice") or "").strip()
        if safety:
            parts.append(f"⚠ **Safety notice:** {safety}")
        advisory = str(assessment.get("ppap_advisory_notice") or "").strip()
        if advisory:
            parts.append(f"_{advisory}_")

        return ("\n" + "\n").join(parts)
