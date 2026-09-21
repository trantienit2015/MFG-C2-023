# MFG-C2-023 — Unit Tests: PPAPLevelRecommendNode (inner, LLM, advisory only)

from framework.schemas.agent_status import AgentStatus
from framework.schemas.trust_level import TrustLevel
from src.nodes.ppap_level_recommend_node import PPAPLevelRecommendNode


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


class TestPPAPLevelRecommendNode:
    def test_trust_level_declared(self):
        assert PPAPLevelRecommendNode.required_trust_level == TrustLevel.ANONYMOUS

    def test_success_path(self):
        node = PPAPLevelRecommendNode(llm=FakeLLM("I recommend PPAP level 4."))
        state = {
            "ecr_metadata": {"title": "t"},
            "impact_level": "SAFETY_CRITICAL",
            "node_history": [],
            "error_log": [],
        }
        result = node.execute(state)
        assert result["status"] == AgentStatus.SUCCESS
        assert result["ppap_level"] == 4

    def test_success_path_with_canonical_dict_llm(self):
        # Canonical BaseLLM.complete() returns a dict, not a bare string — a
        # node that treats it as a string crashes with a real client (3m).
        node = PPAPLevelRecommendNode(llm=DictLLM("I recommend PPAP level 2."))
        state = {"ecr_metadata": {"title": "t"}, "impact_level": "MINOR", "node_history": [], "error_log": []}
        result = node.execute(state)
        assert result["status"] == AgentStatus.SUCCESS
        assert result["ppap_level"] == 2

    def test_out_of_range_response_ignored(self):
        node = PPAPLevelRecommendNode(llm=FakeLLM("level 9"))
        state = {"ecr_metadata": {"title": "t"}, "impact_level": "MINOR", "node_history": [], "error_log": []}
        result = node.execute(state)
        assert result["status"] == AgentStatus.SUCCESS
        assert 0 <= result["ppap_level"] <= 5

    def test_missing_upstream_fields_returns_error_not_raise(self):
        node = PPAPLevelRecommendNode(llm=FakeLLM("3"))
        result = node.execute({"node_history": [], "error_log": []})
        assert result["status"] == AgentStatus.ERROR

    def test_llm_raises_returns_error_not_success(self):
        # A CONFIGURED-but-failing LLM must not be silently swallowed into a
        # deterministic-fallback SUCCESS — that hides a real provider outage.
        node = PPAPLevelRecommendNode(llm=RaisingLLM())
        state = {"ecr_metadata": {"title": "t"}, "impact_level": "MINOR", "node_history": [], "error_log": []}
        result = node.execute(state)
        assert result["status"] == AgentStatus.ERROR
        assert any("LLM call failed" in entry for entry in result["error_log"])

    def test_llm_empty_response_returns_error_not_success(self):
        node = PPAPLevelRecommendNode(llm=EmptyLLM())
        state = {"ecr_metadata": {"title": "t"}, "impact_level": "MINOR", "node_history": [], "error_log": []}
        result = node.execute(state)
        assert result["status"] == AgentStatus.ERROR
        assert any("empty response" in entry for entry in result["error_log"])
