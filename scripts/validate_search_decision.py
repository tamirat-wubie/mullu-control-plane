#!/usr/bin/env python3
"""Validate the SearchDecision contract.

Purpose: verify the pre-retrieval decision contract for search need,
freshness, source scope, budget, and retrieval safety.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: Python standard library and scripts/validate_schemas.py.
Invariants:
  - Validation is read-only and deterministic.
  - SearchDecision never performs retrieval or grants connector authority.
  - BudgetUnknown blocks deep retrieval.
  - Retrieved content remains evidence only, not instruction authority.
  - Mfidel atomicity remains preserved.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
import json
import sys
from pathlib import Path
from typing import Any

WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from scripts.validate_schemas import _load_schema, _validate_schema_instance  # noqa: E402


DEFAULT_SCHEMA_PATH = WORKSPACE_ROOT / "schemas" / "search_decision.schema.json"
DEFAULT_DECISION_PATH = WORKSPACE_ROOT / "examples" / "search_decision.foundation.json"
EXPECTED_SCHEMA_ID = "urn:mullusi:schema:search-decision:1"
EXPECTED_SCHEMA_TITLE = "Search Decision"
EXPECTED_DECISION_VERSION = "search_decision.v1"
REQUIRED_EVIDENCE_REFS = (
    "schemas/search_decision.schema.json",
    "examples/search_decision.foundation.json",
    "scripts/validate_search_decision.py",
    "tests/test_validate_search_decision.py",
    "docs/77_search_decision_contract.md",
    "docs/maps/MULLUSI_SEARCH_LAYER_MAP.md",
    "examples/sdlc/requirement_search_decision_contract_20260614.json",
    "examples/sdlc/design_search_decision_contract_20260614.json",
)
FALSE_GUARDS = (
    "execution_authority_granted",
    "connector_authority_granted",
    "external_retrieval_performed",
    "terminal_closure",
    "raw_secret_material_included",
    "retrieved_instruction_authority_granted",
)


class SearchDecisionError(ValueError):
    """Raised when a SearchDecision artifact cannot be loaded."""


def load_json_object(json_path: Path, label: str) -> dict[str, Any]:
    """Load one JSON object from disk."""

    if not json_path.exists():
        raise FileNotFoundError(f"missing {label}: {json_path}")
    if not json_path.is_file():
        raise IsADirectoryError(f"{label} path is not a file: {json_path}")
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise SearchDecisionError(f"{label} must be a JSON object")
    return payload


def validate_schema_artifact(schema: dict[str, Any]) -> list[str]:
    """Return deterministic schema artifact errors."""

    errors: list[str] = []
    if schema.get("$id") != EXPECTED_SCHEMA_ID:
        errors.append("schema $id is invalid")
    if schema.get("title") != EXPECTED_SCHEMA_TITLE:
        errors.append("schema title is invalid")
    if schema.get("type") != "object":
        errors.append("schema root type must be object")
    if schema.get("additionalProperties") is not False:
        errors.append("schema root must close additional properties")

    required_fields = schema.get("required")
    properties = schema.get("properties")
    if not isinstance(required_fields, list):
        errors.append("schema required field must be a list")
    if not isinstance(properties, dict):
        errors.append("schema properties must be an object")
    if isinstance(required_fields, list) and isinstance(properties, dict):
        for field_name in (
            "decision_id",
            "decision_version",
            "decision_state",
            "search_need",
            "freshness",
            "source_plan",
            "budget_decision",
            "retrieval_safety",
            "governance_guards",
            "receipt_envelope",
            "evidence_refs",
        ):
            if field_name not in required_fields:
                errors.append(f"schema missing required field: {field_name}")
            if field_name not in properties:
                errors.append(f"schema missing property: {field_name}")
        decision_version_schema = properties.get("decision_version", {})
        if not isinstance(decision_version_schema, dict) or decision_version_schema.get("const") != EXPECTED_DECISION_VERSION:
            errors.append("schema property decision_version must const search_decision.v1")
    return errors


def validate_decision_record(record: Any, schema: dict[str, Any] | None = None) -> list[str]:
    """Return deterministic validation errors for one SearchDecision payload."""

    schema_payload = schema or _load_schema(DEFAULT_SCHEMA_PATH)
    errors = _validate_schema_instance(schema_payload, record)
    if not isinstance(record, dict):
        errors.append("search decision must be a JSON object")
        return errors

    if record.get("decision_version") != EXPECTED_DECISION_VERSION:
        errors.append("decision_version must match search_decision.v1")
    _validate_state_alignment(record, errors)
    _validate_freshness(record.get("freshness"), errors)
    _validate_budget(record.get("decision_state"), record.get("budget_decision"), errors)
    _validate_source_plan(record.get("decision_state"), record.get("source_plan"), errors)
    _validate_retrieval_safety(record.get("retrieval_safety"), errors)
    _validate_governance_guards(record.get("governance_guards"), errors)
    _require_subset(record, "evidence_refs", REQUIRED_EVIDENCE_REFS, errors)
    return errors


def validate_decision(
    schema_path: Path = DEFAULT_SCHEMA_PATH,
    decision_path: Path = DEFAULT_DECISION_PATH,
) -> list[str]:
    """Validate the schema artifact and default Foundation Mode decision."""

    schema = _load_schema(schema_path)
    decision = load_json_object(decision_path, "SearchDecision")
    errors = validate_schema_artifact(schema)
    errors.extend(validate_decision_record(decision, schema))
    return errors


def workspace_display_path(path: Path) -> str:
    """Return a stable workspace-relative display path when possible."""

    resolved_path = path if path.is_absolute() else WORKSPACE_ROOT / path
    try:
        return str(resolved_path.resolve().relative_to(WORKSPACE_ROOT))
    except ValueError:
        return str(path)


def build_mutated_decision(**updates: Any) -> dict[str, Any]:
    """Build a deterministic mutated copy of the default decision for tests."""

    decision = load_json_object(DEFAULT_DECISION_PATH, "SearchDecision")
    mutated = deepcopy(decision)
    for dotted_key, value in updates.items():
        target = mutated
        segments = dotted_key.split("__")
        for segment in segments[:-1]:
            next_target = target.get(segment)
            if not isinstance(next_target, dict):
                next_target = {}
                target[segment] = next_target
            target = next_target
        target[segments[-1]] = value
    return mutated


def _validate_state_alignment(record: dict[str, Any], errors: list[str]) -> None:
    search_need = record.get("search_need")
    if not isinstance(search_need, dict):
        errors.append("search_need must be an object")
        return
    decision_state = record.get("decision_state")
    classification = search_need.get("classification")
    state_by_classification = {
        "no_search_needed": "NO_SEARCH_NEEDED",
        "cache_allowed": "CACHE_HIT_ALLOWED",
        "local_search_required": "LOCAL_SEARCH_ALLOWED",
        "web_search_light_allowed": "WEB_SEARCH_LIGHT_ALLOWED",
        "web_search_deep_approval_required": "WEB_SEARCH_DEEP_APPROVAL_REQUIRED",
        "search_blocked": {"SEARCH_BLOCKED_BY_BUDGET", "SEARCH_BLOCKED_BY_UNKNOWN"},
    }
    expected_state = state_by_classification.get(classification)
    if isinstance(expected_state, set):
        if decision_state not in expected_state:
            errors.append("decision_state must match blocked search_need classification")
    elif expected_state and decision_state != expected_state:
        errors.append("decision_state must match search_need classification")


def _validate_freshness(freshness: Any, errors: list[str]) -> None:
    if not isinstance(freshness, dict):
        errors.append("freshness must be an object")
        return
    state = freshness.get("state")
    required = freshness.get("freshness_required")
    current_claim_allowed = freshness.get("current_info_claim_allowed")
    proof_state = freshness.get("proof_state")
    if state in {"required", "stale_must_refresh", "unknown_blocked"} and required is not True:
        errors.append("freshness_required must be true when freshness state requires evidence")
    if proof_state in {"Unknown", "BudgetUnknown", "Fail"} and current_claim_allowed is not False:
        errors.append("current_info_claim_allowed must be false unless freshness proof passes")
    if state == "not_required" and required is not False:
        errors.append("freshness_required must be false when freshness is not required")


def _validate_budget(decision_state: Any, budget: Any, errors: list[str]) -> None:
    if not isinstance(budget, dict):
        errors.append("budget_decision must be an object")
        return
    state = budget.get("state")
    approval_required = budget.get("approval_required")
    proof_state = budget.get("proof_state")
    approved_ref = budget.get("approved_budget_ref")
    if decision_state == "WEB_SEARCH_DEEP_APPROVAL_REQUIRED" and state != "approval_required":
        errors.append("deep web search must require budget approval")
    if state in {"approval_required", "blocked_by_budget", "unknown_blocked"} and approved_ref is not None:
        errors.append("blocked or approval-required budget decision cannot carry approved_budget_ref")
    if proof_state == "BudgetUnknown" and approval_required is not True:
        errors.append("BudgetUnknown requires approval_required true")


def _validate_source_plan(decision_state: Any, source_plan: Any, errors: list[str]) -> None:
    if not isinstance(source_plan, dict):
        errors.append("source_plan must be an object")
        return
    selected_sources = set(source_plan.get("selected_sources", []))
    allowed_sources = set(source_plan.get("allowed_sources", []))
    if selected_sources - allowed_sources:
        errors.append("selected_sources must be a subset of allowed_sources")
    if "web" in selected_sources and decision_state == "WEB_SEARCH_DEEP_APPROVAL_REQUIRED":
        if source_plan.get("external_retrieval_allowed") is not False:
            errors.append("deep web search awaiting approval cannot allow external retrieval")
    if source_plan.get("tenant_scope_required") is not True:
        errors.append("tenant_scope_required must remain true")


def _validate_retrieval_safety(retrieval_safety: Any, errors: list[str]) -> None:
    if not isinstance(retrieval_safety, dict):
        errors.append("retrieval_safety must be an object")
        return
    if retrieval_safety.get("retrieved_content_authority") != "evidence_only":
        errors.append("retrieved content authority must remain evidence_only")
    for field_name in (
        "prompt_injection_guard",
        "private_source_scope_required",
    ):
        if retrieval_safety.get(field_name) is not True:
            errors.append(f"retrieval_safety.{field_name} must be true")
    for field_name in (
        "tool_instruction_from_source_allowed",
        "policy_instruction_from_source_allowed",
    ):
        if retrieval_safety.get(field_name) is not False:
            errors.append(f"retrieval_safety.{field_name} must be false")


def _validate_governance_guards(guards: Any, errors: list[str]) -> None:
    if not isinstance(guards, dict):
        errors.append("governance_guards must be an object")
        return
    for guard_name in FALSE_GUARDS:
        if guards.get(guard_name) is not False:
            errors.append(f"governance_guards.{guard_name} must be false")
    if guards.get("mfidel_atomicity_preserved") is not True:
        errors.append("governance_guards.mfidel_atomicity_preserved must be true")


def _require_subset(record: dict[str, Any], field_name: str, required_values: tuple[str, ...], errors: list[str]) -> None:
    values = record.get(field_name)
    if not isinstance(values, list):
        errors.append(f"{field_name} must be a list")
        return
    for missing_value in sorted(set(required_values) - set(values)):
        errors.append(f"{field_name} missing required ref: {missing_value}")


def main(argv: list[str] | None = None) -> int:
    """Validate SearchDecision artifacts from the command line."""

    parser = argparse.ArgumentParser(description="Validate SearchDecision contract.")
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA_PATH)
    parser.add_argument("--decision", type=Path, default=DEFAULT_DECISION_PATH)
    parser.add_argument("--json", action="store_true", help="emit a machine-readable receipt")
    args = parser.parse_args(argv)
    errors = validate_decision(args.schema, args.decision)
    if args.json:
        print(
            json.dumps(
                {
                    "receipt_id": "search_decision_validation",
                    "schema_path": workspace_display_path(args.schema),
                    "decision_path": workspace_display_path(args.decision),
                    "status": "passed" if not errors else "failed",
                    "errors": errors,
                },
                indent=2,
                sort_keys=True,
            )
        )
    elif errors:
        for error in errors:
            print(f"[FAIL] {error}")
    else:
        print("[PASS] search_decision")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
