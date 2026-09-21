# MFG-C2-023 — Unit Tests: DownstreamImpactNode (inner, deterministic)

from framework.schemas.agent_status import AgentStatus
from framework.schemas.trust_level import TrustLevel
from src.nodes.downstream_impact_node import DownstreamImpactNode


class TestDownstreamImpactNode:
    def setup_method(self):
        self.node = DownstreamImpactNode()

    def test_trust_level_declared(self):
        assert DownstreamImpactNode.required_trust_level == TrustLevel.ANONYMOUS

    def test_success_path_all_entity_types(self):
        state = {
            "ecr_metadata": {
                "affected_parts": ["BRK-1001"],
                "affected_processes": ["stamping"],
                "affected_suppliers": ["ACME Metals"],
            },
            "node_history": [],
            "error_log": [],
        }
        result = self.node.execute(state)
        assert result["status"] == AgentStatus.SUCCESS
        entity_types = {e["entity_type"] for e in result["downstream_impact"]}
        assert entity_types == {"part", "process", "supplier"}

    def test_missing_ecr_metadata_returns_error_not_raise(self):
        result = self.node.execute({"node_history": [], "error_log": []})
        assert result["status"] == AgentStatus.ERROR
