# MFG-C2-023 — Unit Tests: ECRWorkflowGraph (inner Cat 2 subgraph shape)

from framework.schemas.agent_status import AgentStatus
from src.graph.domain_workflow_graph import ECRWorkflowGraph


class TestECRWorkflowGraph:
    def test_name_and_state_schema(self):
        graph = ECRWorkflowGraph(config={})
        assert graph.name == "ecr_classification_workflow"
        from src.schemas.state import State

        assert graph.state_schema is State

    def test_get_output_shape(self):
        graph = ECRWorkflowGraph(config={})
        state = {
            "ecr_metadata": {"title": "t"},
            "impact_level": "MAJOR",
            "ppap_level": 2,
            "downstream_impact": [],
            "lead_time": {"business_days": 5, "basis": "x"},
            "safety_notice": None,
            "ppap_advisory_notice": "advisory",
            "status": AgentStatus.SUCCESS,
            "trace_id": "t1",
            "correlation_id": "c1",
            "node_history": ["a", "b"],
        }
        output = graph.get_output(state)
        assert output["impact_level"] == "MAJOR"
        assert output["ppap_advisory_notice"] == "advisory"
        assert output["node_history"] == ["a", "b"]

    def test_route_linear_topology(self):
        from langgraph.graph import END

        graph = ECRWorkflowGraph(config={})
        assert graph.route({"status": AgentStatus.SUCCESS.value}) == "safety_gate"
        assert graph.route({"status": AgentStatus.ERROR.value}) == END
