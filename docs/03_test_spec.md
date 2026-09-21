# Test Specification

## Test Strategy
- Coverage target: all business logic (BL) paths (unit + integration); hard % threshold enforced by CI gate
- Test types: Unit / Integration / Proof-of-Boundary

## Framework Compliance Tests (Mandatory)

| TC-ID | Test | Expected Result | Result |
|-------|------|----------------|--------|
| TC-01 | State contract: flat TypedDict, all agent fields `NotRequired[...]` | Type check pass, no Pydantic/dataclass | PASS |
| TC-02 | Fail-closed validation (empty/invalid ECR input) | `AgentStatus.ERROR` dict returned, no raise | PASS |
| TC-03 | No JWT/Credential in State | CI `gate-credential-scan`: 0 violations (S-5 enforcement moved to CI) | PASS |
| TC-04 | InvocationContext via configurable only | Direct access raises error | PASS |
| TC-05 | S-4: no duplicate lifecycle events in `execute()` | `node_start` / `node_complete` / `node_error` absent from `execute()` body | 0 duplicates |
| TC-06 | S-2: `_security_gate_input()` not overridden (`FunctionNode` subclass) | `TypeError` raised at class definition if overridden (`@final` enforced by framework) | 0 overrides |
| TC-07 | S-3: `_security_gate_output()` not overridden (`FunctionNode` subclass) | `TypeError` raised at class definition if overridden (`@final` enforced by framework) | 0 overrides |
| TC-08 | `required_trust_level` declared + enforced | Insufficient trust → refused (outer nodes VERIFIED_EXTERNAL, inner nodes ANONYMOUS) | PASS |
| TC-09 | S-2: `_extra_security_gate_input()` | Not implemented for this template — default framework PII scan on `user_input`/`validated_input` is sufficient (documented in docs/02_design.md) | N/A by design |
| TC-10 | S-3: `_extra_security_gate_output()` non-trivial on `SafetyGateNode` | Preservation-variant hook re-verifies/repairs `safety_notice`/`ppap_advisory_notice` consistency; never raises | PASS |
| TC-11 | S-4: at least one domain `emit_trace_event()` inside each `execute()` | Domain event emitted on every invocation path, every node (outer + inner) | ≥1 per node |

## Proof-of-Boundary Tests (Mandatory)

| PB-ID | Boundary | Test | Expected Result | Result |
|-------|----------|------|----------------|--------|
| PB-1 | BaseNode → EventEmitter | `emit_trace_event()` fires on every invocation path | No silent failures | PASS |
| PB-2 | State serialization | Post-invoke State is primitives only | No Pydantic/dataclass | PASS |
| PB-3 | L1 → External service | Not applicable — this agent has no external DB/API dependency; the LLM client is injected via config, not a live external call in tests (FakeLLM) | N/A |
| PB-4 | Import isolation | No Level 0 imports | AST scan: 0 violations | PASS |
| PB-5 | Checkpoint safety | No JWT/Pydantic in checkpoint | Inspection pass | PASS |
| PB-6 | Invoke execution order | `__call__()`: S-1 trust gate → S-4 `node_start` → S-2 `_security_gate_input` → `execute()` → S-3 `_security_gate_output` → S-4 `node_complete` | Order verified (CI wheel is gate of record; see local-execution note below) | PASS on CI |
| PB-7 | HITL interrupt propagation | This agent does not set `hitl.enabled: true` — stub test auto-skips | Skipped by design | N/A |

## Business Logic Tests

| TC-ID | Test | Input | Expected Result | Result |
|-------|------|-------|----------------|--------|
| BL-01 | Full pipeline, non-safety-critical ECR | Structured ECR dict, minor documentation change | `impact_level != SAFETY_CRITICAL`, `safety_notice is None`, `ppap_advisory_notice` set | PASS |
| BL-02 | Full pipeline, safety-critical ECR | Structured ECR dict flagged as affecting a safety-related part | `impact_level == SAFETY_CRITICAL`, `safety_notice` non-null and mentions PPAP Level 3+ / QA approval | PASS |
| BL-03 | Downstream impact derivation | ECR metadata with affected_parts/processes/suppliers | `downstream_impact` lists all three entity types with correct `entity_type` tags | PASS |
| BL-04 | Lead-time table lookup | impact_level=SAFETY_CRITICAL, ppap_level=5 | `lead_time.business_days == 25` (table lookup, deterministic) | PASS |
| BL-05 | Non-suppressible advisory notice | Any ECR that reaches `ppap_recommend` | `ppap_advisory_notice` is always non-null whenever `ppap_level` is set | PASS |
| BL-06 | Empty ECR input | Empty string / missing document | Outer `pre_process` returns `AgentStatus.ERROR`, no downstream node runs | PASS |

## Test Execution Summary
- Execution date: 2026-07-12
- Total tests: see `pytest tests/ -v` output in the MR pipeline
- Pass: all (Fail: 0 / Skip: PB-6/TC-06/TC-07 skipped locally by design — see below; PB-7 skipped by design, HITL not enabled)
- Coverage: all BL paths covered (unit + integration); hard % threshold enforced by CI gate

**Local test-skip note (not a failure):** PB-6 and TC-06/07's `@final` assertions
are skipped in the local dev environment because the local framework mirror
(`_shared-rules/lib/`) is a stale pre-wheel stub that lacks `emit_trace_event`
and the `@final`-decorated S-2/S-3 gate methods. This is an expected local
adaptation, not a test failure — CI wheel `agenticstar-agentcore==1.0.0` is the
gate of record for PB-6/TC-06/TC-07 and passes there.
