"""AgentCore Platform v1.0"""

# MFG-C2-023 — ECR Classification & Impact Assessment Agent
#
# Cat 2: outer AgentBaseGraph (fixed 5-node backbone) + GraphNode in the
# `main` slot wrapping the inner ECR classification workflow (6 business
# steps, src/graph/domain_workflow_graph.py). See
# the security/contract reference doc cat2-pattern reference for the full
# contract. The GraphNode wrapper class lives in THIS file (not src/nodes/)
# per the Cat 2 convention — PB-6 (test_pb_invoke_order.py) only discovers
# BaseNode subclasses under src/nodes/, and GraphNode.__call__() deliberately
# does not run the standard S-1..S-4 lifecycle (it delegates gating to the
# inner subgraph), so keeping it out of src/nodes/ avoids a false PB-6 trip.
#
# Pipeline:
#   Outer: START -> initialize -> pre_process -> main(GraphNode) -> post_process -> finalize -> END
#   Inner (src/graph/domain_workflow_graph.py):
#     START -> ecr_extract -> impact_classify -> ppap_recommend
#            -> downstream_impact -> lead_time_estimate -> safety_gate -> END

from typing import Any, ClassVar, cast

from framework.graph.agent_base_graph import AgentBaseGraph
from framework.nodes.graph_node import GraphNode
from framework.schemas.agent_state import AgentState
from framework.schemas.trust_level import TrustLevel
from shared.utils.audit_logger import emit_trace_event
from src.services.llm_resolver import _UNSET
from src.nodes.post_process_node import PostProcessNode
from src.nodes.pre_process_node import PreProcessNode
from src.schemas.state import State


class ECRWorkflowGraphNode(GraphNode):
    """Wraps the inner ECR classification workflow; assigned to the `main` slot."""

    # S-1: outer main-slot wrapper — first node in outer backbone receiving
    # caller input; must match agent.yaml required_trust_level (see
    # pre_process_node.py / post_process_node.py siblings).
    required_trust_level: ClassVar[TrustLevel] = TrustLevel.VERIFIED_EXTERNAL
    error_strategy: ClassVar[str] = "propagate"
    propagate_hitl: ClassVar[bool] = False

    def __init__(self, llm: Any = _UNSET, criteria: str | None = None):
        super().__init__()
        self._llm = llm
        self._criteria = criteria

    def get_subgraph(self) -> Any:
        from src.graph.domain_workflow_graph import ECRWorkflowGraph

        sg = ECRWorkflowGraph(config=self._parent_config())
        sg.compile()
        return sg

    def extract_input(self, state: AgentState) -> str:
        # S-4: runs inside GraphNode.execute() - audit dispatch into the inner subgraph.
        emit_trace_event(
            "ecr_workflow_dispatched",
            {"correlation_id": state.get("correlation_id")},
            state,
        )
        return cast(str, state.get("validated_input", state.get("user_input", "")))

    def merge_output(self, state: AgentState, sub_result: dict[str, Any]) -> dict[str, Any]:
        # S-4: runs inside GraphNode.execute() - audit the subgraph outcome merged back out.
        emit_trace_event(
            "ecr_workflow_completed",
            {
                "correlation_id": state.get("correlation_id"),
                "impact_level": sub_result.get("impact_level"),
            },
            state,
        )
        return {
            "ecr_metadata": sub_result.get("ecr_metadata", {}),
            "impact_level": sub_result.get("impact_level"),
            "ppap_level": sub_result.get("ppap_level"),
            "downstream_impact": sub_result.get("downstream_impact", []),
            "lead_time": sub_result.get("lead_time", {}),
            "safety_notice": sub_result.get("safety_notice"),
            "ppap_advisory_notice": sub_result.get("ppap_advisory_notice"),
            "status": sub_result.get("status"),
        }

    def _parent_config(self) -> dict[str, Any]:
        # Omit `llm` when unset: writing {"llm": None} makes the inner graph
        # read an explicit None and skip secret resolution entirely.
        cfg = {"criteria": self._criteria}
        if self._llm is not _UNSET:
            cfg["llm"] = self._llm
        return cfg


class ECRClassificationGraph(AgentBaseGraph):
    """Outer Cat 2 graph for MFG-C2-023 — ECR Classification & Impact Assessment.

    Backbone: initialize -> pre_process -> main (ECRWorkflowGraphNode) ->
    post_process -> finalize (fixed; add_edges() is NOT overridden).
    """

    @property
    def name(self) -> str:
        return "mfg-c2-023"

    @property
    def state_schema(self) -> type:
        return State

    def register_nodes(self) -> None:
        super().register_nodes()  # injects InitializeNode + FinalizeNode

        cfg = self.config if hasattr(self, "config") and self.config else {}
        # "llm" absent -> _UNSET (resolve from ctx.secrets inside execute());
        # present and None -> deliberate opt-out.
        llm = cfg["llm"] if "llm" in cfg else _UNSET
        criteria = self.config.get("criteria") if hasattr(self, "config") else None

        self._nodes["pre_process"] = PreProcessNode()
        self._nodes["main"] = ECRWorkflowGraphNode(llm=llm, criteria=criteria)
        self._nodes["post_process"] = PostProcessNode()

    def get_output(self, state: AgentState) -> dict[str, Any]:
        """Surface the prose reply AND the machine-readable result.

        AgentBaseGraph.get_output() returns only
        {output, status, trace_id, correlation_id, node_history}, so the
        structured result a parent Cat 2 agent consumes would never reach the
        caller. "output" stays the human-facing prose (what the Marketplace
        chat renders); "final_output" carries the JSON contract.

        The `or` fallback is deliberate: the error path never runs
        post_process, so no prose exists yet on a failed run.
        """
        base = super().get_output(state)
        base["final_output"] = state.get("ecr_assessment")
        return cast(dict[str, Any], base)

    # add_edges() is NOT overridden - backbone wiring belongs to the framework.


# Alias used by config/agent.yaml (module: "src.graph", class: "ECRClassificationGraph").
Graph = ECRClassificationGraph
