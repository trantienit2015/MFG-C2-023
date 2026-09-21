"""AgentCore Platform v1.0"""

# src/graph/domain_workflow_graph.py — inner graph for the Cat 2 ECR
# classification workflow. Instantiated by ECRWorkflowGraphNode.get_subgraph()
# in graph.py. Inherits BaseGraph directly (fully custom linear topology).
#
# Pipeline: START -> ecr_extract -> impact_classify -> ppap_recommend
#                   -> downstream_impact -> lead_time_estimate -> safety_gate -> END

from typing import Any
from langgraph.graph import END, START

from framework.graph.base_graph import BaseGraph
from framework.schemas.agent_state import AgentState
from framework.schemas.agent_status import AgentStatus
from src.services.llm_resolver import _UNSET
from src.nodes.downstream_impact_node import DownstreamImpactNode
from src.nodes.ecr_content_extract_node import ECRContentExtractNode
from src.nodes.impact_classify_node import ImpactClassifyNode
from src.nodes.lead_time_estimate_node import LeadTimeEstimateNode
from src.nodes.ppap_level_recommend_node import PPAPLevelRecommendNode
from src.nodes.safety_gate_node import SafetyGateNode
from src.schemas.state import State


class ECRWorkflowGraph(BaseGraph):
    """Inner graph implementing the 6-step ECR classification workflow.

    Called by ECRWorkflowGraphNode.get_subgraph() in graph.py. No super()
    call in register_nodes() (BaseGraph.register_nodes() is abstract); does
    NOT register initialize/finalize (outer backbone concern).
    """

    @property
    def name(self) -> str:
        return "ecr_classification_workflow"

    @property
    def state_schema(self) -> type:
        return State

    def _validate_config(self) -> None:
        """No mandatory config keys for the inner workflow itself; the LLM
        client and classification criteria are optional and forwarded via
        _parent_config() in graph.py."""
        pass

    def register_nodes(self) -> None:
        cfg = self.config if hasattr(self, "config") and self.config else {}
        # Same distinction as the outer graph: absent key -> _UNSET.
        llm = cfg["llm"] if "llm" in cfg else _UNSET
        criteria = self.config.get("criteria") if hasattr(self, "config") else None

        self._nodes["ecr_extract"] = ECRContentExtractNode()
        self._nodes["impact_classify"] = (
            ImpactClassifyNode(llm=llm, criteria=criteria) if criteria else ImpactClassifyNode(llm=llm)
        )
        self._nodes["ppap_recommend"] = PPAPLevelRecommendNode(llm=llm)
        self._nodes["downstream_impact"] = DownstreamImpactNode()
        self._nodes["lead_time_estimate"] = LeadTimeEstimateNode()
        self._nodes["safety_gate"] = SafetyGateNode()

    def add_edges(self) -> None:
        self._sg.add_edge(START, "ecr_extract")
        self._sg.add_edge("ecr_extract", "impact_classify")
        self._sg.add_edge("impact_classify", "ppap_recommend")
        self._sg.add_edge("ppap_recommend", "downstream_impact")
        self._sg.add_edge("downstream_impact", "lead_time_estimate")
        self._sg.add_edge("lead_time_estimate", "safety_gate")
        self._sg.add_edge("safety_gate", END)

    def route(self, state: AgentState) -> str:
        """Required by BaseGraph ABC. Linear topology - never called unless
        add_conditional_edges() is wired (it is not)."""
        return END if state.get("status") == AgentStatus.ERROR.value else "safety_gate"

    def get_output(self, state: AgentState) -> dict[str, Any]:
        """Shape the sub_result dict consumed by ECRWorkflowGraphNode.merge_output()."""
        return {
            "ecr_metadata": state.get("ecr_metadata", {}),
            "impact_level": state.get("impact_level"),
            "ppap_level": state.get("ppap_level"),
            "downstream_impact": state.get("downstream_impact", []),
            "lead_time": state.get("lead_time", {}),
            "safety_notice": state.get("safety_notice"),
            "ppap_advisory_notice": state.get("ppap_advisory_notice"),
            "status": state.get("status"),
            "trace_id": state.get("trace_id"),
            "correlation_id": state.get("correlation_id"),
            "node_history": state.get("node_history", []),
        }
