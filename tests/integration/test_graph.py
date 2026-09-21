# MFG-C2-023 — Integration Tests: full outer+inner graph compile + invoke
#
# The public invoke() result exposes the agent's final answer under the
# framework-standard `output` key (AgentBaseGraph.get_output() maps
# state["formatted_output"] -> result["output"]) - PostProcessNode itself
# still writes to the `formatted_output` state field (see unit tests).

import pytest

import json

from framework.schemas.agent_status import AgentStatus
from framework.schemas.invocation_context import InvocationContext
from framework.schemas.trust_level import TrustLevel
from src.graph.graph import ECRClassificationGraph


class FakeLLM:
    """Deterministic fake LLM — routes on a keyword baked into the prompt so
    tests can drive either branch without depending on real model output."""

    def __init__(self, impact_response: str = "MAJOR", ppap_response: str = "3"):
        self._impact_response = impact_response
        self._ppap_response = ppap_response

    def complete(self, prompt: str) -> str:
        if "Classify the following" in prompt:
            return self._impact_response
        return self._ppap_response


def _structured_ecr_input() -> str:
    return json.dumps(
        {
            "ecr_document": {
                "change_id": "ECR-2026-0142",
                "title": "Revise bracket material spec",
                "description": "Change bracket material from steel grade A to grade B",
                "affected_parts": ["BRK-1001"],
                "affected_processes": ["stamping"],
                "affected_suppliers": ["ACME Metals"],
            }
        }
    )


def _ctx() -> InvocationContext:
    return InvocationContext(session_id="it-1", caller_trust_level=TrustLevel.VERIFIED_EXTERNAL, caller_id="tester")


class TestECRClassificationGraphIntegration:
    def test_full_pipeline_major_impact(self):
        agent = ECRClassificationGraph(config={"llm": FakeLLM(impact_response="MAJOR", ppap_response="3")})
        agent.compile()
        result = agent.invoke(_structured_ecr_input(), ctx=_ctx())

        assert result.get("status") in (AgentStatus.SUCCESS.value, AgentStatus.SUCCESS)
        # get_output() surfaces formatted_output as the chat reply, so "output" is
        # prose for a human; the structured assessment is on final_output.
        reply = result.get("output") or ""
        assert isinstance(reply, str) and reply.strip()
        with pytest.raises(json.JSONDecodeError):
            json.loads(reply)  # a JSON reply here would be a UX regression
        output = result.get("final_output") or {}
        assert output.get("impact_level") == "MAJOR"
        assert output.get("ppap_level") == 3
        assert output.get("safety_notice") is None
        assert output.get("ppap_advisory_notice")  # always set once ppap_level present
        assert output.get("downstream_impact")

        node_history = result.get("node_history") or []
        assert len(node_history) >= 5  # Initialize, pre_process, main(GraphNode), post_process, Finalize

    def test_full_pipeline_safety_critical(self):
        agent = ECRClassificationGraph(config={"llm": FakeLLM(impact_response="SAFETY_CRITICAL", ppap_response="4")})
        agent.compile()
        result = agent.invoke(_structured_ecr_input(), ctx=_ctx())

        output = result.get("final_output") or {}
        assert output.get("impact_level") == "SAFETY_CRITICAL"
        assert output.get("safety_notice")
        assert "PPAP Level 3" in output["safety_notice"]
        assert output.get("ppap_advisory_notice")
        # The safety notice must survive into what the reviewer actually reads.
        assert "PPAP Level 3" in (result.get("output") or "")

    def test_empty_input_fails_closed(self):
        # The outer pre_process -> main edge is unconditional (fixed AgentBaseGraph
        # backbone), so empty input still dispatches into the inner subgraph.
        # ECRContentExtractNode (first inner node) rejects it, and SafetyGateNode
        # (last inner node) propagates that ERROR status through to the end
        # rather than papering over it with SUCCESS.
        agent = ECRClassificationGraph(config={"llm": FakeLLM()})
        agent.compile()
        result = agent.invoke("", ctx=_ctx())
        assert result.get("status") in (AgentStatus.ERROR.value, AgentStatus.ERROR)
