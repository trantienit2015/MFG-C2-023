# MFG-C2-023 — Unit Tests: ImpactClassifyNode (inner, LLM)

from framework.schemas.agent_status import AgentStatus
from framework.schemas.trust_level import TrustLevel
from src.nodes.impact_classify_node import ImpactClassifyNode


class FakeLLM:
    def __init__(self, response: str):
        self._response = response

    def complete(self, prompt: str) -> str:
        return self._response


class DictLLM:
    """Canonical BaseLLM.complete() shape — returns {"content": str}."""

    def __init__(self, content: str):
        self._content = content

    def complete(self, prompt: str) -> dict:
        return {"content": self._content}


class EmptyLLM:
    def complete(self, prompt: str) -> dict:
        return {"content": ""}


class RaisingLLM:
    def complete(self, prompt: str):
        raise RuntimeError("provider timeout")


class TestImpactClassifyNode:
    def test_trust_level_declared(self):
        assert ImpactClassifyNode.required_trust_level == TrustLevel.ANONYMOUS

    def test_success_path_safety_critical(self):
        node = ImpactClassifyNode(llm=FakeLLM("This is SAFETY_CRITICAL because ..."))
        state = {"ecr_metadata": {"title": "t", "description": "d"}, "node_history": [], "error_log": []}
        result = node.execute(state)
        assert result["status"] == AgentStatus.SUCCESS
        assert result["impact_level"] == "SAFETY_CRITICAL"

    def test_success_path_major(self):
        node = ImpactClassifyNode(llm=FakeLLM("MAJOR"))
        state = {"ecr_metadata": {"title": "t", "description": "d"}, "node_history": [], "error_log": []}
        result = node.execute(state)
        assert result["status"] == AgentStatus.SUCCESS
        assert result["impact_level"] == "MAJOR"

    def test_success_path_with_canonical_dict_llm(self):
        # Canonical BaseLLM.complete() returns a dict, not a bare string — a
        # node that treats it as a string crashes with a real client (3m).
        node = ImpactClassifyNode(llm=DictLLM("MAJOR"))
        state = {"ecr_metadata": {"title": "t", "description": "d"}, "node_history": [], "error_log": []}
        result = node.execute(state)
        assert result["status"] == AgentStatus.SUCCESS
        assert result["impact_level"] == "MAJOR"

    def test_missing_ecr_metadata_returns_error_not_raise(self):
        node = ImpactClassifyNode(llm=FakeLLM("MAJOR"))
        result = node.execute({"node_history": [], "error_log": []})
        assert result["status"] == AgentStatus.ERROR

    def test_no_llm_configured_does_not_raise(self):
        node = ImpactClassifyNode(llm=None)
        state = {"ecr_metadata": {"title": "t"}, "node_history": [], "error_log": []}
        result = node.execute(state)
        assert result["status"] == AgentStatus.SUCCESS
        assert result["impact_level"] == "MINOR"  # default fallback, no LLM response

    def test_llm_raises_returns_error_not_success(self):
        # A CONFIGURED-but-failing LLM must not be silently swallowed into a
        # deterministic-fallback SUCCESS — that hides a real provider outage.
        node = ImpactClassifyNode(llm=RaisingLLM())
        state = {"ecr_metadata": {"title": "t", "description": "d"}, "node_history": [], "error_log": []}
        result = node.execute(state)
        assert result["status"] == AgentStatus.ERROR
        assert any("LLM call failed" in entry for entry in result["error_log"])

    def test_llm_empty_response_returns_error_not_success(self):
        node = ImpactClassifyNode(llm=EmptyLLM())
        state = {"ecr_metadata": {"title": "t", "description": "d"}, "node_history": [], "error_log": []}
        result = node.execute(state)
        assert result["status"] == AgentStatus.ERROR
        assert any("empty response" in entry for entry in result["error_log"])
