# Template Design Specification

## Position in AgentCore Architecture

- **Agent Class**: `ECRClassificationGraph` (`src/graph/graph.py`)
- **L1 Base**: `AgentBaseGraph` (L1 direct) — outer graph. Cat 2: the `main` slot
  wraps an inner `BaseGraph` subgraph (`ECRWorkflowGraph`,
  `src/graph/domain_workflow_graph.py`) via a `GraphNode` (`ECRWorkflowGraphNode`,
  defined in `src/graph/graph.py`).
- **Three-Layer Separation**:
  - State: flat TypedDict composition (`State(AgentState)`, all agent-specific
    fields wrapped `NotRequired[...]`) — no Pydantic (msgpack incompatible)
  - Node: L1 inheritance (`FunctionNode`, Template Method — `execute(self, state) -> dict` override only)
  - Graph: composition (`register_nodes()` for node substitution; outer + inner)

## Architecture Overview

### Node Configuration

**Outer graph (`ECRClassificationGraph`, `AgentBaseGraph`):**

| Node | Responsibility | Input State | Output State | Inherits/Overrides |
|------|---------------|-------------|--------------|-------------------|
| initialize | schema_version, session_id, trust_level | — | — | InitializeNode (default) |
| pre_process | Validate raw ECR input (JSON or free-text); serialize to `validated_input` JSON envelope for the inner subgraph | `user_input` | `validated_input` | `PreProcessNode` (`FunctionNode`), trust `VERIFIED_EXTERNAL` |
| main | Dispatch to the inner ECR classification workflow; merge results back | `validated_input` | `ecr_metadata, impact_level, ppap_level, downstream_impact, lead_time, safety_notice, ppap_advisory_notice` | `ECRWorkflowGraphNode` (`GraphNode`) |
| post_process | Assemble the final `formatted_output` dict | merged fields above | `formatted_output` | `PostProcessNode` (`FunctionNode`), trust `VERIFIED_EXTERNAL` |
| finalize | response_metadata, total_time_ms | — | — | FinalizeNode (default) |

**Inner workflow (`ECRWorkflowGraph`, `BaseGraph`, `src/graph/domain_workflow_graph.py`):**

| # | Node | Responsibility | LLM? | Trust |
|---|------|-----------------|------|-------|
| 1 | `ecr_extract` (`ECRContentExtractNode`) | Parse the JSON envelope from the outer `validated_input`; extract structured `ecr_metadata` (change_id, title, description, affected parts/processes/suppliers) | No | ANONYMOUS |
| 2 | `impact_classify` (`ImpactClassifyNode`) | Classify impact level SAFETY_CRITICAL / MAJOR / MINOR / ADMINISTRATIVE against a config-injectable ISO 9001 §8.3 + OEM PPAP/APQP criteria set | Yes | ANONYMOUS |
| 3 | `ppap_recommend` (`PPAPLevelRecommendNode`) | Recommend an advisory PPAP submission level 0–5 | Yes | ANONYMOUS |
| 4 | `downstream_impact` (`DownstreamImpactNode`) | Rule-based list of affected parts/processes/suppliers, derived from `ecr_metadata` | No | ANONYMOUS |
| 5 | `lead_time_estimate` (`LeadTimeEstimateNode`) | Table-lookup estimate of review lead time from impact_level + ppap_level | No | ANONYMOUS |
| 6 | `safety_gate` (`SafetyGateNode`) | Attach the two non-suppressible notices (see Security below) | No | ANONYMOUS |

Inner nodes are all `ANONYMOUS` — caller trust is authenticated once at the outer
backbone (`pre_process`/`post_process` = `VERIFIED_EXTERNAL`, matching
`config/agent.yaml agent.required_trust_level`); an inner node requiring more
would be an unwarranted privilege escalation.

### Data Flow

```
Outer: START → initialize → pre_process → main(GraphNode) → {route} → post_process → finalize → END
                                                ↓ (retry, max 3)
                                              pre_process

Inner (invoked from `main`):
  START → ecr_extract → impact_classify → ppap_recommend
         → downstream_impact → lead_time_estimate → safety_gate → END
```

The inner subgraph does not see the outer state — `GraphNode.extract_input()`
forwards only the outer `validated_input` string (a JSON envelope
`{"ecr_document": ...}` built by the outer `pre_process`). The inner graph's
first node (`ECRContentExtractNode`) `json.loads()`s it back into a payload.
Config (the LLM client, classification criteria) reaches the inner graph via
`ECRWorkflowGraphNode._parent_config()`, never via state.

### State Definition

| Field | Type | Purpose | Required |
|-------|------|---------|----------|
| `ecr_metadata` | `NotRequired[dict]` | Structured change metadata extracted from the raw ECR document | No |
| `impact_level` | `NotRequired[str]` | SAFETY_CRITICAL / MAJOR / MINOR / ADMINISTRATIVE | No |
| `ppap_level` | `NotRequired[int]` | Advisory PPAP submission level 0–5 | No |
| `downstream_impact` | `NotRequired[list]` | List of `{entity_type, entity}` affected parts/processes/suppliers | No |
| `lead_time` | `NotRequired[dict]` | `{business_days, basis}` | No |
| `safety_notice` | `NotRequired[str \| None]` | Non-suppressible SAFETY_CRITICAL notice; `None` when not triggered | No |
| `ppap_advisory_notice` | `NotRequired[str \| None]` | Non-suppressible "advisory only" disclaimer; always set alongside `ppap_level` | No |

`user_input`, `validated_input`, `status`, `node_history`, `error_log`, and other
shared fields are inherited from `AgentState` and not re-declared.

**State Constraints (mandatory):**
- Flat TypedDict only (primitives + JSON-serializable types)
- No JWT, API keys, credentials in State (checkpoint DB leakage)
- InvocationContext via `config["configurable"]` only (not in State)
- No Pydantic models, dataclass, arbitrary Python objects (msgpack incompatible)

## Framework Utilization

### Shared Components Used
- [x] InvocationContext (correlation_id, session_id, permissions, credential handle)
- [ ] ConnectionPolicy (retry/timeout strategy) — default `max_retry: 3` from `agent.yaml`, no custom policy
- [ ] SecurityViolationError — not directly raised; validation failures return `AgentStatus.ERROR` dicts (fail-closed, no raise)
- [ ] S-2: `_extra_security_gate_input()` — not implemented; the default framework PII scan on `user_input`/`validated_input` is sufficient for this domain (no additional PII-shaped fields)
- [x] S-3: `_extra_security_gate_output()` — implemented on `SafetyGateNode` as a **preservation-variant** hook: re-verifies that `safety_notice`/`ppap_advisory_notice` are internally consistent with `impact_level`/`ppap_level` in this node's own output, and deterministically repairs them if they ever drift — never raises, always returns a dict.
- [x] S-4: `emit_trace_event()` — at least one domain-specific event inside every node's `execute()` (`ecr_input_validated`/`ecr_input_rejected`, `ecr_content_extracted`, `ecr_impact_classified`, `ppap_level_recommended`, `downstream_impact_derived`, `lead_time_estimated`, `safety_gate_evaluated`, `ecr_assessment_finalized`), plus dispatch/completion events on the `GraphNode` wrapper (`ecr_workflow_dispatched`/`ecr_workflow_completed`) emitted from `extract_input()`/`merge_output()`.

> **S-2/S-3 gate behaviour by node type (ADR-017):**
> - `FunctionNode` subclass → framework `@final` gate always runs automatically;
>   extend via `_extra_security_gate_input()` / `_extra_security_gate_output()` only
> - `GraphNode` / `RemoteAgentNode` → deliberate no-op (upstream or remote node's gate already applied)
> - Custom `BaseNode` subclass → must implement `_security_gate_input()` and
>   `_security_gate_output()` directly (`@abstractmethod` — omission raises `TypeError` at instantiation)

### Composition Pattern

- **Pattern**: `GraphNode` (subgraph) — Cat 2 outer/inner composition
- **Composition target**: `ECRWorkflowGraph` (inner `BaseGraph`, `src/graph/domain_workflow_graph.py`)
- **Error propagation strategy**: `propagate` (fail-fast — inner errors re-raise as `SubgraphError`; no HITL in this agent, `propagate_hitl=False`)

## Security Posture — SAFETY_CRITICAL gate & PPAP advisory boundary

This agent's single safety-critical invariant: **no output path may present a
SAFETY_CRITICAL classification without the mandated PPAP-Level-3+/QA-approval
notice, and no output path may present a `ppap_level` without the "advisory
only" disclaimer.** Enforced by `SafetyGateNode`, the fixed last step of the
inner pipeline (there is no conditional route around it):
1. `execute()` unconditionally recomputes both notices from `impact_level` /
   `ppap_level` on every invocation.
2. `_extra_security_gate_output()` re-verifies the node's own output keys and
   deterministically repairs them if inconsistent — a second, independent
   enforcement layer (S-3 preservation variant).

PPAP recommendations (`PPAPLevelRecommendNode`) are explicitly documented as
advisory-only in code comments and never treated as a binding decision anywhere
in the pipeline.


### Known limitation — S-2 masks two-word supplier names

The framework's S-2 input gate (`framework.security.detect_pii`) classifies a
two-word capitalised phrase as a Latin-script person name, so a supplier named
like `Acme Metals` is masked to `[MASKED]` before `execute()` runs. A supplier
name is business data an ECR assessment is meant to keep, so the mask is a false
positive here.

Verified in the deployed image (agentcore 1.0.3): `detect_pii("supplier Acme
Metals")` returns `[{'type': 'name', 'value': 'Acme Metals'}]`, while
`Acme Corp`, `BRK-1001` and the change description are untouched.

**Not worked around in this template, by design.** The impact is bounded:

- Impact level, PPAP level, lead time and the safety notice are derived from the
  change description and rule tables, none of which are masked. The assessment
  itself is therefore unaffected.
- **Both input paths are masked, including the structured one.** S-2 runs on
  `user_input` / `validated_input`, and the outer `pre_process` serialises the
  whole ECR document — `affected_suppliers` included — into that string before
  the gate sees it, so a supplier submitted as structured data is masked exactly
  as one mentioned in free text.

Verified on the deployed image by invoking the agent with a structured
`affected_suppliers: ["<two-word name> GmbH"]`: the report returns
`suppliers affected (1): [MASKED] GmbH`. The entity is still counted and still
listed as a supplier; only the name itself is masked.

There is consequently no input shape a caller can use to preserve the supplier
name in the report. This template does not work around it: review criterion #16
forbids re-implementing a substrate capability, and a template-local PII regex is
exactly that. Out of scope for this template.

## Import Isolation Confirmation
- [x] Template does not import agenticstar-platform SDK (Level 0)
- [x] Import targets: framework/ and shared/ only (no agents/base/ required)

## Design Decision Record

| Decision | Option A | Option B | Chosen | Rationale |
|----------|----------|----------|--------|-----------|
| L1 base type | AgentBaseGraph | AutonomousBaseGraph | **AgentBaseGraph** | Fixed 6-step workflow, no autonomous think/act loop needed |
| Composition pattern | Flat 3-slot (Cat 1 style) | GraphNode + inner subgraph | **GraphNode + inner subgraph** | Cat 2 mandate (`gate-composition`) — 6 business steps orchestrated for one specific job-to-be-done |
| Classification criteria source | Hardcoded in prompt | Config-injectable placeholder | **Config-injectable placeholder** | Real ISO/OEM criteria pending customer confirmation; avoids hardcoding a business secret or a wrong assumption |
| Safety/advisory notice enforcement | Ad-hoc per-node | Single dedicated last-step node (`SafetyGateNode`) | **Dedicated last-step node** | Guarantees a single, always-executed enforcement point with no bypass path |
