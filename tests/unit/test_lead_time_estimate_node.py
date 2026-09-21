# MFG-C2-023 — Unit Tests: LeadTimeEstimateNode (inner, deterministic)

from framework.schemas.agent_status import AgentStatus
from framework.schemas.trust_level import TrustLevel
from src.nodes.lead_time_estimate_node import LeadTimeEstimateNode


class TestLeadTimeEstimateNode:
    def setup_method(self):
        self.node = LeadTimeEstimateNode()

    def test_trust_level_declared(self):
        assert LeadTimeEstimateNode.required_trust_level == TrustLevel.ANONYMOUS

    def test_success_path_safety_critical_max_ppap(self):
        state = {"impact_level": "SAFETY_CRITICAL", "ppap_level": 5, "node_history": [], "error_log": []}
        result = self.node.execute(state)
        assert result["status"] == AgentStatus.SUCCESS
        assert result["lead_time"]["business_days"] == 25

    def test_success_path_administrative_min_ppap(self):
        state = {"impact_level": "ADMINISTRATIVE", "ppap_level": 0, "node_history": [], "error_log": []}
        result = self.node.execute(state)
        assert result["status"] == AgentStatus.SUCCESS
        assert result["lead_time"]["business_days"] == 1

    def test_missing_inputs_returns_error_not_raise(self):
        result = self.node.execute({"node_history": [], "error_log": []})
        assert result["status"] == AgentStatus.ERROR
