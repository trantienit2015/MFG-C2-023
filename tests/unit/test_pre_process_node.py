# MFG-C2-023 — Unit Tests: PreProcessNode (outer)

import json

from framework.schemas.agent_status import AgentStatus
from framework.schemas.trust_level import TrustLevel
from src.nodes.pre_process_node import PreProcessNode


class TestPreProcessNode:
    def setup_method(self):
        self.node = PreProcessNode()

    def test_trust_level_declared(self):
        assert PreProcessNode.required_trust_level == TrustLevel.VERIFIED_EXTERNAL

    def test_success_path_dict_input(self):
        state = {
            "user_input": {"change_id": "ECR-1", "title": "t", "description": "d"},
            "node_history": [],
            "error_log": [],
        }
        result = self.node.execute(state)
        assert result["status"] == AgentStatus.SUCCESS
        payload = json.loads(result["validated_input"])
        assert payload["ecr_document"]["change_id"] == "ECR-1"

    def test_success_path_json_string_input(self):
        state = {
            "user_input": json.dumps({"ecr_document": {"title": "from json string"}}),
            "node_history": [],
            "error_log": [],
        }
        result = self.node.execute(state)
        assert result["status"] == AgentStatus.SUCCESS
        payload = json.loads(result["validated_input"])
        assert payload["ecr_document"]["title"] == "from json string"

    def test_success_path_free_text_input(self):
        state = {"user_input": "Change bracket material", "node_history": [], "error_log": []}
        result = self.node.execute(state)
        assert result["status"] == AgentStatus.SUCCESS

    def test_empty_input_returns_error(self):
        state = {"user_input": "", "node_history": [], "error_log": []}
        result = self.node.execute(state)
        assert result["status"] == AgentStatus.ERROR
        assert result["error_log"]
