"""AgentCore Platform v1.0"""

# Service layer: pure domain logic for ECR classification, PPAP-level lead-time
# estimation, and rule-based downstream impact derivation. No agenticstar
# imports, no side effects, no credentials. Nodes call this module; it is
# deliberately deterministic and unit-testable in isolation from the graph.

from __future__ import annotations

from typing import Any

VALID_IMPACT_LEVELS = ("SAFETY_CRITICAL", "MAJOR", "MINOR", "ADMINISTRATIVE")

# Placeholder classification criteria — a clearly-labeled, config-injectable
# stand-in for the real ISO 9001 §8.3 + OEM-specific PPAP/APQP criteria set,
# which is still pending customer confirmation (see docs/02_design.md). This
# is NOT a business secret; it is a generic reference to public ISO wording
# and is injected into the LLM prompt as plain configuration text, replaceable
# per-customer without a code change.
DEFAULT_CLASSIFICATION_CRITERIA = """\
[PLACEHOLDER CRITERIA — replace with the customer-confirmed ISO 9001 Section 8.3 +
OEM-specific PPAP/APQP impact-classification rubric before production use]

- SAFETY_CRITICAL: the change affects form/fit/function of a safety-related part,
  a regulatory/compliance requirement, or a characteristic flagged safety/critical
  on the control plan.
- MAJOR: the change affects form/fit/function of a non-safety part, a supplier or
  manufacturing process change, or a change requiring customer PPAP re-submission.
- MINOR: the change affects documentation, non-critical dimensions/tolerances, or
  packaging/labeling with no form/fit/function impact.
- ADMINISTRATIVE: the change is clerical (drawing revision notes, internal part
  numbering, non-technical documentation) with no physical or process impact.
"""

# Deterministic PPAP-level -> review lead-time table (business days). This is
# a simple, explainable rule-based mapping — no LLM, no external call.
_LEAD_TIME_TABLE_BUSINESS_DAYS: dict[str, dict[int, int]] = {
    "SAFETY_CRITICAL": {0: 10, 1: 10, 2: 12, 3: 15, 4: 20, 5: 25},
    "MAJOR": {0: 5, 1: 5, 2: 7, 3: 10, 4: 12, 5: 15},
    "MINOR": {0: 2, 1: 2, 2: 3, 3: 4, 4: 5, 5: 6},
    "ADMINISTRATIVE": {0: 1, 1: 1, 2: 1, 3: 2, 4: 2, 5: 2},
}


def extract_ecr_metadata(raw_input: dict[str, Any] | str) -> dict[str, Any]:
    """Extract structured ECR change metadata from a free-text or structured input.

    Accepts either a dict already shaped like an ECR record, or a plain text
    document — in the text case this performs a best-effort deterministic
    extraction (title = first line, description = remainder, no parts/
    processes/suppliers detected). A real deployment would replace the
    text-parsing branch with a proper document-structure parser; the dict
    branch is the primary, structured-input path.
    """
    if isinstance(raw_input, dict):
        return {
            "change_id": raw_input.get("change_id") or raw_input.get("ecr_id") or "UNKNOWN",
            "title": raw_input.get("title", ""),
            "description": raw_input.get("description", ""),
            "affected_parts": list(raw_input.get("affected_parts", []) or []),
            "affected_processes": list(raw_input.get("affected_processes", []) or []),
            "affected_suppliers": list(raw_input.get("affected_suppliers", []) or []),
            "requested_by": raw_input.get("requested_by", ""),
        }

    text = (raw_input or "").strip()
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    title = lines[0] if lines else ""
    description = "\n".join(lines[1:]) if len(lines) > 1 else ""
    return {
        "change_id": "UNKNOWN",
        "title": title,
        "description": description,
        "affected_parts": [],
        "affected_processes": [],
        "affected_suppliers": [],
        "requested_by": "",
    }


def derive_downstream_impact(ecr_metadata: dict[str, Any]) -> list[dict[str, Any]]:
    """Rule-based (no LLM) list of affected parts/processes/suppliers.

    Deterministic: echoes and tags each entity found in ecr_metadata with its
    entity_type, so downstream consumers get one uniform list shape.
    """
    impact: list[dict[str, Any]] = []
    for part in ecr_metadata.get("affected_parts", []) or []:
        impact.append({"entity_type": "part", "entity": part})
    for process in ecr_metadata.get("affected_processes", []) or []:
        impact.append({"entity_type": "process", "entity": process})
    for supplier in ecr_metadata.get("affected_suppliers", []) or []:
        impact.append({"entity_type": "supplier", "entity": supplier})
    return impact


def estimate_lead_time(impact_level: str, ppap_level: int) -> dict[str, Any]:
    """Deterministic table lookup mapping impact_level + ppap_level -> business days."""
    level = impact_level if impact_level in _LEAD_TIME_TABLE_BUSINESS_DAYS else "MINOR"
    clamped_ppap = max(0, min(5, int(ppap_level) if ppap_level is not None else 0))
    business_days = _LEAD_TIME_TABLE_BUSINESS_DAYS[level][clamped_ppap]
    return {
        "business_days": business_days,
        "basis": f"impact_level={level}, ppap_level={clamped_ppap} (rule table lookup)",
    }


def build_classification_prompt(ecr_metadata: dict[str, Any], criteria: str = DEFAULT_CLASSIFICATION_CRITERIA) -> str:
    """Build the LLM prompt for impact-level classification."""
    return (
        "Classify the following Engineering Change Request against the criteria below. "
        f"Respond with exactly one of: {', '.join(VALID_IMPACT_LEVELS)}.\n\n"
        f"CRITERIA:\n{criteria}\n\n"
        f"ECR:\nTitle: {ecr_metadata.get('title', '')}\n"
        f"Description: {ecr_metadata.get('description', '')}\n"
        f"Affected parts: {ecr_metadata.get('affected_parts', [])}\n"
        f"Affected processes: {ecr_metadata.get('affected_processes', [])}\n"
    )


def build_ppap_prompt(ecr_metadata: dict[str, Any], impact_level: str) -> str:
    """Build the LLM prompt for the advisory PPAP submission-level recommendation."""
    return (
        "Recommend a PPAP submission level (integer 0-5) for the following ECR, given its "
        f"impact classification of {impact_level}. This is an advisory recommendation only. "
        "Respond with a single integer 0-5.\n\n"
        f"Title: {ecr_metadata.get('title', '')}\n"
        f"Description: {ecr_metadata.get('description', '')}\n"
    )


def parse_impact_level(raw_response: str) -> str:
    """Best-effort extraction of a valid impact level from an LLM text response."""
    upper = (raw_response or "").upper()
    for level in VALID_IMPACT_LEVELS:
        if level in upper:
            return level
    return "MINOR"


def parse_ppap_level(raw_response: str) -> int:
    """Best-effort extraction of an integer 0-5 PPAP level from an LLM text response."""
    for token in (raw_response or "").replace(",", " ").split():
        stripped = token.strip(".:")
        if stripped.isdigit():
            value = int(stripped)
            if 0 <= value <= 5:
                return value
    return 3
