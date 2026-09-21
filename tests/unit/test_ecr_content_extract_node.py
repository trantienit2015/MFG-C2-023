# MFG-C2-023 — Unit Tests: ECRContentExtractNode (inner)

import json

from framework.schemas.agent_status import AgentStatus
from framework.schemas.trust_level import TrustLevel
from src.nodes.ecr_content_extract_node import ECRContentExtractNode


class TestECRContentExtractNode:
    def setup_method(self):
        self.node = ECRContentExtractNode()

    def test_trust_level_declared(self):
        assert ECRContentExtractNode.required_trust_level == TrustLevel.ANONYMOUS

    def test_success_path(self):
        payload = {
            "ecr_document": {
                "change_id": "ECR-1",
                "title": "Revise bracket material",
                "description": "steel A -> steel B",
                "affected_parts": ["BRK-1001"],
                "affected_processes": ["stamping"],
                "affected_suppliers": ["ACME Metals"],
            }
        }
        state = {"user_input": json.dumps(payload), "node_history": [], "error_log": []}
        result = self.node.execute(state)
        assert result["status"] == AgentStatus.SUCCESS
        assert result["ecr_metadata"]["change_id"] == "ECR-1"
        assert result["ecr_metadata"]["affected_parts"] == ["BRK-1001"]

    def test_empty_input_returns_error_not_raise(self):
        result = self.node.execute({"user_input": "", "node_history": [], "error_log": []})
        assert result["status"] == AgentStatus.ERROR
        assert result["error_log"]

    def test_malformed_json_returns_error_not_raise(self):
        result = self.node.execute({"user_input": "{not json", "node_history": [], "error_log": []})
        assert result["status"] == AgentStatus.ERROR
