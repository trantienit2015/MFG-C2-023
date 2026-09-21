# MFG-C2-023 — Unit Tests: PostProcessNode (outer)

import json
import pytest

from framework.schemas.agent_status import AgentStatus
from framework.schemas.trust_level import TrustLevel
from src.nodes.post_process_node import PostProcessNode


class TestPostProcessNode:
    def setup_method(self):
        self.node = PostProcessNode()

    def test_trust_level_declared(self):
        assert PostProcessNode.required_trust_level == TrustLevel.VERIFIED_EXTERNAL

    def test_success_path_assembles_output(self):
        state = {
            "impact_level": "MAJOR",
            "ppap_level": 3,
            "ppap_advisory_notice": "advisory only",
            "downstream_impact": [{"entity_type": "part", "entity": "BRK-1001"}],
            "lead_time": {"business_days": 10, "basis": "x"},
            "safety_notice": None,
            "node_history": [],
            "error_log": [],
        }
        result = self.node.execute(state)
        assert result["status"] == AgentStatus.SUCCESS.value
        # Machine-readable contract for a parent Cat 2 agent.
        out = result["ecr_assessment"]
        assert out["impact_level"] == "MAJOR"
        assert out["ppap_level"] == 3
        assert out["safety_notice"] is None
        assert out["ppap_advisory_notice"] == "advisory only"
        # Chat reply: prose a reviewer can read, never raw JSON.
        prose = result["formatted_output"]
        assert isinstance(prose, str)
        with pytest.raises(json.JSONDecodeError):
            json.loads(prose)
        assert "MAJOR" in prose and "BRK-1001" in prose

    def test_empty_state_does_not_raise(self):
        result = self.node.execute({"node_history": [], "error_log": []})
        assert result["status"] == AgentStatus.SUCCESS.value
        assert result["ecr_assessment"]["impact_level"] is None
        assert isinstance(result["formatted_output"], str)
        assert result["formatted_output"].strip()
