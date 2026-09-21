# MFG-C2-023 — Unit Tests: ECRWorkflowGraphNode (Cat 2 GraphNode wrapper, src/graph/graph.py)
#
# GraphNode is not a FunctionNode/BaseNode subject to the PB-6 discovery scan
# (it deliberately delegates S-1..S-4 lifecycle gating to the inner subgraph) —
# tested directly here instead. extract_input()/merge_output() are exercised
# in isolation (they run *inside* GraphNode.execute(), which itself needs a
# real subgraph to invoke — see tests/integration/test_graph.py for the
# full end-to-end path).

import json

from src.graph.graph import ECRWorkflowGraphNode


class TestECRWorkflowGraphNode:
    def test_extract_input_prefers_validated_input(self):
        node = ECRWorkflowGraphNode()
        payload = json.dumps({"ecr_document": {"title": "t"}})
        state = {"validated_input": payload, "user_input": "raw", "correlation_id": "c1"}
        assert node.extract_input(state) == payload

    def test_extract_input_falls_back_to_user_input(self):
        node = ECRWorkflowGraphNode()
        state = {"user_input": "raw fallback", "correlation_id": "c1"}
        assert node.extract_input(state) == "raw fallback"

    def test_merge_output_maps_all_fields(self):
        node = ECRWorkflowGraphNode()
        sub_result = {
            "ecr_metadata": {"title": "t"},
            "impact_level": "SAFETY_CRITICAL",
            "ppap_level": 4,
            "downstream_impact": [{"entity_type": "part", "entity": "BRK-1001"}],
            "lead_time": {"business_days": 20, "basis": "x"},
            "safety_notice": "notice text",
            "ppap_advisory_notice": "advisory text",
            "status": "success",
        }
        state = {"correlation_id": "c1"}
        merged = node.merge_output(state, sub_result)
        assert merged["impact_level"] == "SAFETY_CRITICAL"
        assert merged["ppap_level"] == 4
        assert merged["safety_notice"] == "notice text"
        assert merged["ppap_advisory_notice"] == "advisory text"
        assert merged["downstream_impact"] == sub_result["downstream_impact"]
        assert merged["lead_time"] == sub_result["lead_time"]

    def test_parent_config_forwards_llm_and_criteria(self):
        llm = object()
        node = ECRWorkflowGraphNode(llm=llm, criteria="custom criteria")
        cfg = node._parent_config()
        assert cfg["llm"] is llm
        assert cfg["criteria"] == "custom criteria"
