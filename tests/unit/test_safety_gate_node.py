# MFG-C2-023 — Unit Tests: SafetyGateNode (inner, deterministic, S-3 preservation-variant hook)
#
# This is the most safety-critical node in the agent: it guarantees the two
# non-suppressible notices required by docs/02_design.md — the SAFETY_CRITICAL
# PPAP-Level-3+/QA-approval notice, and the PPAP "advisory only" disclaimer.

from framework.schemas.agent_status import AgentStatus
from framework.schemas.trust_level import TrustLevel
from src.nodes.safety_gate_node import PPAP_ADVISORY_NOTICE, SAFETY_CRITICAL_NOTICE, SafetyGateNode


class TestSafetyGateNode:
    def setup_method(self):
        self.node = SafetyGateNode()

    def test_trust_level_declared(self):
        assert SafetyGateNode.required_trust_level == TrustLevel.ANONYMOUS

    # -- execute(): the primary, always-executed enforcement path --------------

    def test_safety_critical_always_attaches_safety_notice(self):
        state = {"impact_level": "SAFETY_CRITICAL", "ppap_level": 4, "node_history": [], "error_log": []}
        result = self.node.execute(state)
        assert result["status"] == AgentStatus.SUCCESS
        assert result["safety_notice"] == SAFETY_CRITICAL_NOTICE
        assert "PPAP Level 3" in result["safety_notice"]
        assert "QA approval" in result["safety_notice"] or "QA" in result["safety_notice"]

    def test_non_safety_critical_has_no_safety_notice(self):
        for level in ("MAJOR", "MINOR", "ADMINISTRATIVE"):
            state = {"impact_level": level, "ppap_level": 2, "node_history": [], "error_log": []}
            result = self.node.execute(state)
            assert result["safety_notice"] is None, f"unexpected safety_notice for {level}"

    def test_ppap_advisory_notice_always_present_when_ppap_level_set(self):
        for level in ("SAFETY_CRITICAL", "MAJOR", "MINOR", "ADMINISTRATIVE"):
            state = {"impact_level": level, "ppap_level": 1, "node_history": [], "error_log": []}
            result = self.node.execute(state)
            assert result["ppap_advisory_notice"] == PPAP_ADVISORY_NOTICE

    def test_no_ppap_level_no_advisory_notice(self):
        state = {"impact_level": "MAJOR", "ppap_level": None, "node_history": [], "error_log": []}
        result = self.node.execute(state)
        assert result["ppap_advisory_notice"] is None

    def test_empty_state_does_not_raise(self):
        result = self.node.execute({"node_history": [], "error_log": []})
        assert result["status"] == AgentStatus.SUCCESS
        assert result["safety_notice"] is None
        assert result["ppap_advisory_notice"] is None

    # -- _extra_security_gate_output(): the S-3 preservation-variant backstop --

    def test_hook_signature_never_raises_and_returns_dict(self):
        state = {"impact_level": "SAFETY_CRITICAL", "ppap_level": 5, "safety_notice": SAFETY_CRITICAL_NOTICE,
                 "ppap_advisory_notice": PPAP_ADVISORY_NOTICE}
        result = self.node._extra_security_gate_output(state)
        assert isinstance(result, dict)

    def test_hook_repairs_dropped_safety_notice(self):
        """Simulates a future bug where the safety notice was dropped upstream —
        the preservation-variant hook must restore it deterministically."""
        state = {
            "impact_level": "SAFETY_CRITICAL",
            "ppap_level": 3,
            "safety_notice": None,  # incorrectly dropped
            "ppap_advisory_notice": PPAP_ADVISORY_NOTICE,
        }
        repaired = self.node._extra_security_gate_output(state)
        assert repaired["safety_notice"] == SAFETY_CRITICAL_NOTICE

    def test_hook_repairs_dropped_advisory_notice(self):
        state = {
            "impact_level": "MINOR",
            "ppap_level": 2,
            "safety_notice": None,
            "ppap_advisory_notice": None,  # incorrectly dropped
        }
        repaired = self.node._extra_security_gate_output(state)
        assert repaired["ppap_advisory_notice"] == PPAP_ADVISORY_NOTICE

    def test_hook_is_noop_when_already_consistent(self):
        state = {
            "impact_level": "MAJOR",
            "ppap_level": 3,
            "safety_notice": None,
            "ppap_advisory_notice": PPAP_ADVISORY_NOTICE,
        }
        result = self.node._extra_security_gate_output(state)
        assert result == state
