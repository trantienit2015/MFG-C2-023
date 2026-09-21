# PB-6 companion: outer GraphNode boundary verification.
#
# PB-6 (test_pb_invoke_order.py) only discovers BaseNode subclasses under
# src/nodes/. ECRWorkflowGraphNode lives in src/graph/graph.py (the Cat 2
# canonical location: the main-slot wrapper belongs with the graph it composes), so
# no PB-6 probe ever reaches it - yet it is the outer security boundary that receives
# caller input first. This file covers that boundary explicitly:
#   1. S-1  - the trust gate is declared and honoured by __call__().
#   2. #9   - extract_input() takes only contracted fields; merge_output() maps
#             subgraph fields explicitly (no raw pass-through of sub_result).
#   3. S-2/S-3 delegation - a GraphNode's __call__() intentionally delegates the
#      S-2/S-3 lifecycle to the inner subgraph (see framework/nodes/graph_node.py);
#      this asserts the inner entry node really does carry those gates, so the
#      delegation is proven rather than assumed.

import pytest

from framework.nodes.function_node import FunctionNode
from framework.schemas.agent_status import AgentStatus
from framework.schemas.trust_level import TrustLevel

from src.graph.graph import ECRWorkflowGraphNode
from src.nodes.ecr_content_extract_node import ECRContentExtractNode


class TestGraphNodeS1TrustGate:
    """S-1: the outer main-slot wrapper declares a valid trust level and enforces it."""

    def test_required_trust_level_is_declared_and_valid(self):
        assert "required_trust_level" in ECRWorkflowGraphNode.__dict__, (
            "outer GraphNode must declare required_trust_level explicitly - implicit inheritance "
            "leaves the first caller-facing boundary undeclared"
        )
        assert ECRWorkflowGraphNode.required_trust_level in (
            TrustLevel.ANONYMOUS,
            TrustLevel.VERIFIED_EXTERNAL,
            TrustLevel.INTERNAL,
        )

    def test_insufficient_trust_is_refused_before_execute(self, monkeypatch):
        """A caller below the declared level is denied and execute() never runs."""
        monkeypatch.setattr(ECRWorkflowGraphNode, "required_trust_level", TrustLevel.INTERNAL)

        executed = []
        monkeypatch.setattr(
            ECRWorkflowGraphNode,
            "execute",
            lambda self, state: executed.append(True) or {"status": AgentStatus.SUCCESS.value},
        )

        node = ECRWorkflowGraphNode()
        result = node(
            {
                "caller_trust_level": TrustLevel.ANONYMOUS.value,
                "correlation_id": "pb-graphnode-s1",
                "user_input": "",
            }
        )

        assert not executed, "execute() ran despite an insufficient caller trust level"
        assert result.get("status") == AgentStatus.ERROR.value
        assert any("trust" in str(entry).lower() for entry in result.get("error_log", [])), result


class TestGraphNodeBoundaryMapping:
    """Criterion #9: the schema boundary maps fields explicitly in both directions."""

    def test_extract_input_prefers_validated_input(self):
        node = ECRWorkflowGraphNode()
        extracted = node.extract_input(
            {
                "validated_input": '{"ecr_document": {"part_number": "R-100"}}',
                "user_input": "raw caller text",
                "session_id": "should-not-leak",
            }
        )
        assert extracted == '{"ecr_document": {"part_number": "R-100"}}'
        assert "should-not-leak" not in extracted
        assert "raw caller text" not in extracted

    def test_extract_input_falls_back_to_user_input_when_unvalidated(self):
        node = ECRWorkflowGraphNode()
        assert node.extract_input({"user_input": "fallback"}) == "fallback"

    def test_merge_output_maps_fields_explicitly_and_drops_unknown_keys(self):
        node = ECRWorkflowGraphNode()
        sub_result = {
            "ecr_metadata": {"affected_parts": ["R-101"]},
            "impact_level": "major",
            "ppap_level": 3,
            "downstream_impact": [{"part_number": "R-101"}],
            "lead_time": {"days": 14},
            "safety_notice": None,
            "ppap_advisory_notice": None,
            "status": AgentStatus.SUCCESS.value,
            "error_log": [],
            # Not part of the parent contract - must NOT be passed through.
            "internal_debug_blob": {"secret": "leak"},
            "node_history": ["ecr_extract", "impact_classify", "ppap_recommend"],
        }

        merged = node.merge_output({"correlation_id": "pb-graphnode-merge"}, sub_result)

        assert set(merged) == {
            "ecr_metadata",
            "impact_level",
            "ppap_level",
            "downstream_impact",
            "lead_time",
            "safety_notice",
            "ppap_advisory_notice",
            "status",
        }
        assert "internal_debug_blob" not in merged
        assert "node_history" not in merged
        assert merged["status"] == AgentStatus.SUCCESS.value


class TestInnerGatingDelegationIsReal:
    """S-2/S-3 delegation: the inner entry node actually carries the gates."""

    def test_inner_entry_node_is_a_function_node(self):
        # GraphNode.__call__() delegates the S-2/S-3 lifecycle to the inner
        # subgraph by design (framework/nodes/graph_node.py). That is only sound
        # if the inner entry node runs the FunctionNode gate pipeline itself.
        assert issubclass(ECRContentExtractNode, FunctionNode)

    @pytest.mark.skipif(
        not hasattr(FunctionNode, "_security_gate_input"),
        reason="local framework mirror lacks the @final S-2/S-3 gates -- CI wheel is the gate of record",
    )
    def test_inner_entry_node_carries_the_delegated_gates(self):
        assert hasattr(ECRContentExtractNode, "_security_gate_input")
        assert hasattr(ECRContentExtractNode, "_security_gate_output")

    def test_inner_entry_node_declares_its_own_trust_level(self):
        assert "required_trust_level" in ECRContentExtractNode.__dict__
        assert ECRContentExtractNode.required_trust_level == TrustLevel.ANONYMOUS, (
            "inner subgraph nodes run behind the outer backbone's authenticated boundary - "
            "they must not require an elevated trust level (privilege escalation)"
        )

    def test_inner_entry_node_fails_closed_on_malformed_input(self):
        result = ECRContentExtractNode().execute({"user_input": "not json"})
        assert result["status"] == AgentStatus.ERROR.value


@pytest.mark.parametrize("attr", ["get_subgraph", "extract_input", "merge_output"])
def test_all_mandatory_graphnode_abstract_methods_are_implemented(attr):
    """Criterion #9: all three GraphNode abstract methods are implemented locally."""
    assert attr in ECRWorkflowGraphNode.__dict__
