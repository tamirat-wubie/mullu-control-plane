#!/usr/bin/env python3
"""Validate the CapturePolicyDecisionLedger contract.

Purpose: verify the pre-capture ledger contract for source surface, policy
scope, sensitivity floor, budget window, and capture decision safety.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: Python standard library and scripts/validate_schemas.py.
Invariants:
  - Validation is read-only and deterministic.
  - CapturePolicyDecisionLedger never performs capture.
  - Raw observed content and raw secret material are never serialized.
  - Connector, execution, memory-write, and terminal-closure authority remain denied.
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


DEFAULT_SCHEMA_PATH = WORKSPACE_ROOT / "schemas" / "capture_policy_decision_ledger.schema.json"
DEFAULT_LEDGER_PATH = WORKSPACE_ROOT / "examples" / "capture_policy_decision_ledger.foundation.json"
EXPECTED_SCHEMA_ID = "urn:mullusi:schema:capture-policy-decision-ledger:1"
EXPECTED_SCHEMA_TITLE = "Capture Policy Decision Ledger"
EXPECTED_LEDGER_VERSION = "capture_policy_decision_ledger.v1"
REQUIRED_EVIDENCE_REFS = (
    "schemas/capture_policy_decision_ledger.schema.json",
    "examples/capture_policy_decision_ledger.foundation.json",
    "scripts/validate_capture_policy_decision_ledger.py",
    "tests/test_validate_capture_policy_decision_ledger.py",
    "docs/81_capture_policy_decision_ledger_contract.md",
    "examples/sdlc/requirement_capture_policy_decision_ledger_20260615.json",
    "examples/sdlc/design_capture_policy_decision_ledger_20260615.json",
)
FALSE_GUARDS = (
    "capture_performed",
    "raw_observed_content_serialized",
    "raw_secret_material_included",
    "connector_authority_granted",
    "execution_authority_granted",
    "memory_write_authority_granted",
    "terminal_closure",
)
HARD_BLOCK_CLASSIFICATIONS = {"credential", "secret", "payment"}
REDACTION_CLASSIFICATIONS = {"confidential", "sensitive", "restricted", "health", "minor", "biometric"}


class CapturePolicyDecisionLedgerError(ValueError):
    """Raised when a CapturePolicyDecisionLedger artifact cannot be loaded."""


def load_json_object(json_path: Path, label: str) -> dict[str, Any]:
    """Load one JSON object from disk."""

    if not json_path.exists():
        raise FileNotFoundError(f"missing {label}: {json_path}")
    if not json_path.is_file():
        raise IsADirectoryError(f"{label} path is not a file: {json_path}")
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise CapturePolicyDecisionLedgerError(f"{label} must be a JSON object")
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
            "ledger_id",
            "ledger_version",
            "source_surface",
            "policy_scope",
            "sensitivity_floor",
            "budget_window",
            "decisions",
            "governance_guards",
            "receipt_envelope",
            "evidence_refs",
        ):
            if field_name not in required_fields:
                errors.append(f"schema missing required field: {field_name}")
            if field_name not in properties:
                errors.append(f"schema missing property: {field_name}")
        version_schema = properties.get("ledger_version", {})
        if not isinstance(version_schema, dict) or version_schema.get("const") != EXPECTED_LEDGER_VERSION:
            errors.append("schema property ledger_version must const capture_policy_decision_ledger.v1")
    return errors


def validate_ledger_record(record: Any, schema: dict[str, Any] | None = None) -> list[str]:
    """Return deterministic validation errors for one CapturePolicyDecisionLedger payload."""

    schema_payload = schema or _load_schema(DEFAULT_SCHEMA_PATH)
    errors = _validate_schema_instance(schema_payload, record)
    if not isinstance(record, dict):
        errors.append("capture policy decision ledger must be a JSON object")
        return errors

    if record.get("ledger_version") != EXPECTED_LEDGER_VERSION:
        errors.append("ledger_version must match capture_policy_decision_ledger.v1")
    _validate_policy_scope(record.get("policy_scope"), record.get("decisions"), errors)
    _validate_sensitivity_floor(record.get("sensitivity_floor"), record.get("decisions"), errors)
    _validate_budget_window(record.get("budget_window"), record.get("decisions"), errors)
    _validate_decisions(record.get("decisions"), errors)
    _validate_governance_guards(record.get("governance_guards"), errors)
    _require_subset(record, "evidence_refs", REQUIRED_EVIDENCE_REFS, errors)
    return errors


def validate_ledger(
    schema_path: Path = DEFAULT_SCHEMA_PATH,
    ledger_path: Path = DEFAULT_LEDGER_PATH,
) -> list[str]:
    """Validate the schema artifact and default Foundation Mode ledger."""

    schema = _load_schema(schema_path)
    ledger = load_json_object(ledger_path, "CapturePolicyDecisionLedger")
    errors = validate_schema_artifact(schema)
    errors.extend(validate_ledger_record(ledger, schema))
    return errors


def workspace_display_path(path: Path) -> str:
    """Return a stable workspace-relative display path when possible."""

    resolved_path = path if path.is_absolute() else WORKSPACE_ROOT / path
    try:
        return str(resolved_path.resolve().relative_to(WORKSPACE_ROOT))
    except ValueError:
        return str(path)


def build_mutated_ledger(**updates: Any) -> dict[str, Any]:
    """Build a deterministic mutated copy of the default ledger for tests."""

    ledger = load_json_object(DEFAULT_LEDGER_PATH, "CapturePolicyDecisionLedger")
    mutated = deepcopy(ledger)
    for dotted_key, value in updates.items():
        _assign_nested_value(mutated, dotted_key.split("__"), value)
    return mutated


def _assign_nested_value(target: Any, segments: list[str], value: Any) -> None:
    """Assign a nested mutation using dict keys and list indexes."""

    cursor = target
    for segment in segments[:-1]:
        if isinstance(cursor, list):
            cursor = cursor[int(segment)]
        elif isinstance(cursor, dict):
            cursor = cursor[segment]
        else:
            raise CapturePolicyDecisionLedgerError(f"cannot traverse mutation segment: {segment}")
    final_segment = segments[-1]
    if isinstance(cursor, list):
        cursor[int(final_segment)] = value
    elif isinstance(cursor, dict):
        cursor[final_segment] = value
    else:
        raise CapturePolicyDecisionLedgerError(f"cannot assign mutation segment: {final_segment}")


def _validate_policy_scope(policy_scope: Any, decisions: Any, errors: list[str]) -> None:
    if not isinstance(policy_scope, dict):
        errors.append("policy_scope must be an object")
        return
    if policy_scope.get("tenant_scope_required") is not True:
        errors.append("policy_scope.tenant_scope_required must remain true")
    allowed_event_kinds = set(policy_scope.get("allowed_event_kinds", []))
    allowed_capture_classes = set(policy_scope.get("allowed_capture_classes", []))
    if not isinstance(decisions, list):
        return
    for decision in decisions:
        if not isinstance(decision, dict):
            continue
        if decision.get("event_kind") not in allowed_event_kinds:
            errors.append("decision event_kind must be allowed by policy_scope")
        if decision.get("capture_class") not in allowed_capture_classes:
            errors.append("decision capture_class must be allowed by policy_scope")
        if decision.get("policy_ref") != policy_scope.get("policy_ref"):
            errors.append("decision policy_ref must match policy_scope.policy_ref")


def _validate_sensitivity_floor(sensitivity_floor: Any, decisions: Any, errors: list[str]) -> None:
    if not isinstance(sensitivity_floor, dict):
        errors.append("sensitivity_floor must be an object")
        return
    blocked = set(sensitivity_floor.get("blocked_classifications", []))
    redacted = set(sensitivity_floor.get("redaction_required_classifications", []))
    if not HARD_BLOCK_CLASSIFICATIONS <= blocked:
        errors.append("sensitivity_floor must block credential, secret, and payment classifications")
    if not REDACTION_CLASSIFICATIONS <= redacted:
        errors.append("sensitivity_floor must require redaction for private classifications")
    if sensitivity_floor.get("raw_value_serialization_allowed") is not False:
        errors.append("sensitivity_floor.raw_value_serialization_allowed must be false")
    if sensitivity_floor.get("credential_capture_allowed") is not False:
        errors.append("sensitivity_floor.credential_capture_allowed must be false")
    if not isinstance(decisions, list):
        return
    for decision in decisions:
        if not isinstance(decision, dict):
            continue
        sensitivity = decision.get("sensitivity")
        if not isinstance(sensitivity, dict):
            errors.append("decision sensitivity must be an object")
            continue
        classification = sensitivity.get("classification")
        if classification in blocked:
            _require_blocked_sensitivity_decision(decision, sensitivity, errors)
        if classification in redacted and decision.get("capture_class") == "ALLOW":
            errors.append("redaction-required classification cannot be captured with ALLOW")


def _require_blocked_sensitivity_decision(
    decision: dict[str, Any],
    sensitivity: dict[str, Any],
    errors: list[str],
) -> None:
    if decision.get("capture_class") != "BLOCK":
        errors.append("blocked sensitivity classification must use capture_class BLOCK")
    if decision.get("decision_state") != "CAPTURE_BLOCKED_BY_SENSITIVITY":
        errors.append("blocked sensitivity classification must use CAPTURE_BLOCKED_BY_SENSITIVITY")
    if sensitivity.get("blocked") is not True:
        errors.append("blocked sensitivity classification must mark blocked true")
    if sensitivity.get("raw_value_serialized") is not False:
        errors.append("sensitivity.raw_value_serialized must be false")
    if decision.get("stored_payload_ref") is not None:
        errors.append("blocked sensitivity classification cannot carry stored_payload_ref")


def _validate_budget_window(budget_window: Any, decisions: Any, errors: list[str]) -> None:
    if not isinstance(budget_window, dict):
        errors.append("budget_window must be an object")
        return
    proof_state = budget_window.get("proof_state")
    if proof_state in {"Fail", "Unknown", "BudgetUnknown"} and _has_capture_admitting_decision(decisions):
        errors.append("budget_window proof_state must pass before REDACT or ALLOW decisions")
    max_events = budget_window.get("max_events")
    max_bytes = budget_window.get("max_bytes")
    remaining_events = budget_window.get("remaining_events")
    remaining_bytes = budget_window.get("remaining_bytes")
    if isinstance(max_events, int) and isinstance(remaining_events, int) and remaining_events > max_events:
        errors.append("budget_window.remaining_events cannot exceed max_events")
    if isinstance(max_bytes, int) and isinstance(remaining_bytes, int) and remaining_bytes > max_bytes:
        errors.append("budget_window.remaining_bytes cannot exceed max_bytes")
    if not isinstance(decisions, list):
        return
    for decision in decisions:
        if not isinstance(decision, dict):
            continue
        budget = decision.get("budget")
        if not isinstance(budget, dict):
            errors.append("decision budget must be an object")
            continue
        if budget.get("scope_ref") != budget_window.get("window_ref"):
            errors.append("decision budget.scope_ref must match budget_window.window_ref")
        if budget.get("budget_exceeded") is True and decision.get("decision_state") != "CAPTURE_BLOCKED_BY_BUDGET":
            errors.append("budget-exceeded decision must use CAPTURE_BLOCKED_BY_BUDGET")


def _has_capture_admitting_decision(decisions: Any) -> bool:
    if not isinstance(decisions, list):
        return False
    return any(
        isinstance(decision, dict) and decision.get("capture_class") in {"ALLOW", "REDACT"}
        for decision in decisions
    )


def _validate_decisions(decisions: Any, errors: list[str]) -> None:
    if not isinstance(decisions, list):
        errors.append("decisions must be a list")
        return
    for decision in decisions:
        if not isinstance(decision, dict):
            errors.append("capture decision must be an object")
            continue
        capture_class = decision.get("capture_class")
        decision_state = decision.get("decision_state")
        expected_state = {
            "ALLOW": "CAPTURE_ALLOWED",
            "REDACT": "CAPTURE_REDACTED",
            "REVIEW_REQUIRED": "CAPTURE_REVIEW_REQUIRED",
        }.get(capture_class)
        if expected_state and decision_state != expected_state:
            errors.append("decision_state must match capture_class")
        if capture_class == "BLOCK" and decision_state not in {
            "CAPTURE_BLOCKED_BY_POLICY",
            "CAPTURE_BLOCKED_BY_SENSITIVITY",
            "CAPTURE_BLOCKED_BY_BUDGET",
        }:
            errors.append("BLOCK capture_class must use a blocked decision_state")
        sensitivity = decision.get("sensitivity")
        if isinstance(sensitivity, dict):
            if sensitivity.get("raw_value_serialized") is not False:
                errors.append("sensitivity.raw_value_serialized must be false")
            if sensitivity.get("secret_marker_detected") is True:
                _require_blocked_sensitivity_decision(decision, sensitivity, errors)
        if capture_class == "BLOCK" and decision.get("stored_payload_ref") is not None:
            errors.append("BLOCK capture_class cannot carry stored_payload_ref")


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
    """Validate CapturePolicyDecisionLedger artifacts from the command line."""

    parser = argparse.ArgumentParser(description="Validate CapturePolicyDecisionLedger contract.")
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA_PATH)
    parser.add_argument("--ledger", type=Path, default=DEFAULT_LEDGER_PATH)
    parser.add_argument("--json", action="store_true", help="emit a machine-readable receipt")
    args = parser.parse_args(argv)
    errors = validate_ledger(args.schema, args.ledger)
    if args.json:
        print(
            json.dumps(
                {
                    "receipt_id": "capture_policy_decision_ledger_validation",
                    "schema_path": workspace_display_path(args.schema),
                    "ledger_path": workspace_display_path(args.ledger),
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
        print("[PASS] capture_policy_decision_ledger")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
