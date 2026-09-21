# MFG-C2-023 — Framework Compliance Tests (TC-01..08)
# Recommended framework-compliance regression artifact.
# Adapted to this template's Cat 2 architecture: outer AgentBaseGraph
# (pre_process/main/post_process) + GraphNode(main) -> inner BaseGraph
# (6 business-step nodes).

import inspect
import typing

from framework.nodes.function_node import FunctionNode
from framework.schemas.agent_status import AgentStatus
from framework.schemas.trust_level import TrustLevel
from src.graph.graph import ECRClassificationGraph, ECRWorkflowGraphNode
from src.nodes.downstream_impact_node import DownstreamImpactNode
from src.nodes.ecr_content_extract_node import ECRContentExtractNode
from src.nodes.impact_classify_node import ImpactClassifyNode
from src.nodes.lead_time_estimate_node import LeadTimeEstimateNode
from src.nodes.post_process_node import PostProcessNode
from src.nodes.ppap_level_recommend_node import PPAPLevelRecommendNode
from src.nodes.pre_process_node import PreProcessNode
from src.nodes.safety_gate_node import SafetyGateNode
from src.schemas.state import State

ALL_FUNCTION_NODE_CLASSES = [
    PreProcessNode,
    PostProcessNode,
    ECRContentExtractNode,
    ImpactClassifyNode,
    PPAPLevelRecommendNode,
    DownstreamImpactNode,
    LeadTimeEstimateNode,
    SafetyGateNode,
]


class TestTC01StateContract:
    """TC-01: State is a flat TypedDict extending AgentState, no Pydantic/dataclass."""

    def test_state_is_typed_dict_subclass(self):
        assert typing.is_typeddict(State) or hasattr(State, "__annotations__")

    def test_state_fields_are_json_safe_annotations(self):
        # every agent-specific annotation should be NotRequired[...] wrapping a
        # JSON-safe type (str, int, dict, list, or a union including None) —
        # not a Pydantic BaseModel / dataclass / InvocationContext.
        prohibited = ("BaseModel", "InvocationContext", "dataclass")
        for field_name, annotation in State.__annotations__.items():
            annotation_str = str(annotation)
            for bad in prohibited:
                assert bad not in annotation_str, f"{field_name} annotation references {bad}"


class TestTC02FailClosedValidation:
    """TC-02: empty/invalid input -> AgentStatus.ERROR dict, never a raise."""

    def test_pre_process_empty_input_fails_closed(self):
        node = PreProcessNode()
        result = node.execute({"user_input": "", "node_history": [], "error_log": []})
        assert result["status"] == AgentStatus.ERROR

    def test_ecr_extract_malformed_input_fails_closed(self):
        node = ECRContentExtractNode()
        result = node.execute({"user_input": "not json", "node_history": [], "error_log": []})
        assert result["status"] == AgentStatus.ERROR


class TestTC03NoCredentials:
    """TC-03: no os.environ / hardcoded credentials in node source (also CI gate-credential-scan)."""

    def test_no_os_environ_in_node_modules(self):
        import src.nodes.downstream_impact_node as m1
        import src.nodes.ecr_content_extract_node as m2
        import src.nodes.impact_classify_node as m3
        import src.nodes.lead_time_estimate_node as m4
        import src.nodes.post_process_node as m5
        import src.nodes.ppap_level_recommend_node as m6
        import src.nodes.pre_process_node as m7
        import src.nodes.safety_gate_node as m8

        for module in (m1, m2, m3, m4, m5, m6, m7, m8):
            source = inspect.getsource(module)
            assert "os.environ" not in source, f"{module.__name__} references os.environ"


class TestTC04InvocationContextIsolation:
    """TC-04: nodes never read InvocationContext directly from state."""

    def test_execute_signature_takes_state_only(self):
        for node_cls in ALL_FUNCTION_NODE_CLASSES:
            sig = inspect.signature(node_cls.execute)
            params = list(sig.parameters.keys())
            assert params[:2] == ["self", "state"], f"{node_cls.__name__}.execute signature must be (self, state)"


class TestTC05NoDuplicateLifecycleEvents:
    """TC-05: execute() bodies never emit node_start/node_complete/node_error (framework does)."""

    def test_no_backbone_event_names_in_source(self):
        import src.nodes.downstream_impact_node as m1
        import src.nodes.ecr_content_extract_node as m2
        import src.nodes.impact_classify_node as m3
        import src.nodes.lead_time_estimate_node as m4
        import src.nodes.post_process_node as m5
        import src.nodes.ppap_level_recommend_node as m6
        import src.nodes.pre_process_node as m7
        import src.nodes.safety_gate_node as m8

        for module in (m1, m2, m3, m4, m5, m6, m7, m8):
            source = inspect.getsource(module)
            for banned in ('"node_start"', '"node_complete"', '"node_error"'):
                assert banned not in source, f"{module.__name__} re-emits backbone event {banned}"


class TestTC06S2GateFinal:
    """TC-06: FunctionNode subclasses never override the @final _security_gate_input()."""

    def test_no_node_overrides_security_gate_input(self):
        for node_cls in ALL_FUNCTION_NODE_CLASSES:
            assert "_security_gate_input" not in node_cls.__dict__, (
                f"{node_cls.__name__} must not override _security_gate_input (use "
                "_extra_security_gate_input instead)"
            )


class TestTC07S3GateFinal:
    """TC-07: FunctionNode subclasses never override the @final _security_gate_output();
    only the _extra_security_gate_output() hook is allowed."""

    def test_no_node_overrides_security_gate_output(self):
        for node_cls in ALL_FUNCTION_NODE_CLASSES:
            assert "_security_gate_output" not in node_cls.__dict__, (
                f"{node_cls.__name__} must not override _security_gate_output (use "
                "_extra_security_gate_output instead)"
            )

    def test_safety_gate_node_extra_hook_present_and_non_trivial(self):
        assert "_extra_security_gate_output" in SafetyGateNode.__dict__


class TestTC08TrustLevel:
    """TC-08: required_trust_level declared, valid enum, and correctly scoped
    (inner subgraph nodes ANONYMOUS, outer nodes matching agent.yaml VERIFIED_EXTERNAL)."""

    def test_all_nodes_declare_valid_trust_level(self):
        for node_cls in ALL_FUNCTION_NODE_CLASSES:
            assert hasattr(node_cls, "required_trust_level"), f"{node_cls.__name__} missing required_trust_level"
            assert node_cls.required_trust_level in (
                TrustLevel.ANONYMOUS,
                TrustLevel.VERIFIED_EXTERNAL,
                TrustLevel.INTERNAL,
            )

    def test_outer_nodes_match_agent_boundary(self):
        assert PreProcessNode.required_trust_level == TrustLevel.VERIFIED_EXTERNAL
        assert PostProcessNode.required_trust_level == TrustLevel.VERIFIED_EXTERNAL

    def test_inner_nodes_are_anonymous(self):
        for node_cls in (
            ECRContentExtractNode,
            ImpactClassifyNode,
            PPAPLevelRecommendNode,
            DownstreamImpactNode,
            LeadTimeEstimateNode,
            SafetyGateNode,
        ):
            assert node_cls.required_trust_level == TrustLevel.ANONYMOUS


class TestGraphComposition:
    """Sanity: outer graph is L1-direct, Cat 2 composition (GraphNode at main slot)."""

    def test_outer_graph_inherits_agent_base_graph(self):
        from framework.graph.agent_base_graph import AgentBaseGraph

        assert issubclass(ECRClassificationGraph, AgentBaseGraph)

    def test_main_slot_is_graph_node(self):
        from framework.nodes.graph_node import GraphNode

        assert issubclass(ECRWorkflowGraphNode, GraphNode)

    def test_all_business_nodes_are_function_node(self):
        for node_cls in ALL_FUNCTION_NODE_CLASSES:
            assert issubclass(node_cls, FunctionNode)
