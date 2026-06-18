#!/usr/bin/env python3
"""Validate the WorkerFailureReceipt contract.

Purpose: verify post-dispatch worker failure receipts for failed steps,
partial effects, rollback obligations, recovery obligations, and no-success
guards.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: Python standard library and scripts/validate_schemas.py.
Invariants:
  - Validation is read-only and deterministic.
  - Worker failure receipts cannot claim success or terminal closure.
  - Partial or unknown effects require recovery evidence or an explicit block.
  - Rollback-required states require rollback action refs.
  - Raw secrets and raw worker output are not retained in the receipt.
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


DEFAULT_SCHEMA_PATH = WORKSPACE_ROOT / "schemas" / "worker_failure_receipt.schema.json"
DEFAULT_RECEIPT_PATH = WORKSPACE_ROOT / "examples" / "worker_failure_receipt.foundation.json"
EXPECTED_SCHEMA_ID = "urn:mullusi:schema:worker-failure-receipt:1"
EXPECTED_SCHEMA_TITLE = "Worker Failure Receipt"
EXPECTED_RECEIPT_VERSION = "worker_failure_receipt.v1"
REQUIRED_EVIDENCE_REFS = (
    "schemas/worker_failure_receipt.schema.json",
    "examples/worker_failure_receipt.foundation.json",
    "scripts/validate_worker_failure_receipt.py",
    "tests/test_validate_worker_failure_receipt.py",
    "docs/79_worker_failure_receipt_contract.md",
    "docs/maps/MULLUSI_GAP_REGISTER.md",
    "examples/sdlc/requirement_worker_failure_receipt_contract_20260614.json",
    "examples/sdlc/design_worker_failure_receipt_contract_20260614.json",
)
FALSE_GUARDS = (
    "terminal_closure",
    "success_claim_allowed",
    "execution_authority_renewal_allowed",
    "raw_secret_material_included",
)
RECOVERY_STATES = {
    "PARTIAL_EXECUTION_RECORDED",
    "TIMEOUT_WITH_UNKNOWN_EFFECT",
    "ROLLBACK_REQUIRED",
    "RECOVERY_REQUIRED",
}
PARTIAL_OR_UNKNOWN_EFFECTS = {
    "partial_effect_recorded",
    "effect_unknown",
    "rollback_pending",
    "recovery_pending",
}


class WorkerFailureReceiptError(ValueError):
    """Raised when a WorkerFailureReceipt artifact cannot be loaded."""


def load_json_object(json_path: Path, label: str) -> dict[str, Any]:
    """Load one JSON object from disk."""

    if not json_path.exists():
        raise FileNotFoundError(f"missing {label}: {json_path}")
    if not json_path.is_file():
        raise IsADirectoryError(f"{label} path is not a file: {json_path}")
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise WorkerFailureReceiptError(f"{label} must be a JSON object")
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
            "receipt_id",
            "receipt_version",
            "worker_dispatch_ref",
            "receipt_state",
            "failure_class",
            "effect_status",
            "rollback_required",
            "recovery_required",
            "failure_summary",
            "failed_step_refs",
            "partial_effect_refs",
            "rollback_action_refs",
            "recovery_action_refs",
            "blocked_reason_refs",
            "governance_guards",
            "receipt_envelope",
            "evidence_refs",
        ):
            if field_name not in required_fields:
                errors.append(f"schema missing required field: {field_name}")
            if field_name not in properties:
                errors.append(f"schema missing property: {field_name}")
        receipt_version_schema = properties.get("receipt_version", {})
        if not isinstance(receipt_version_schema, dict) or receipt_version_schema.get("const") != EXPECTED_RECEIPT_VERSION:
            errors.append("schema property receipt_version must const worker_failure_receipt.v1")
    return errors


def validate_receipt_record(record: Any, schema: dict[str, Any] | None = None) -> list[str]:
    """Return deterministic validation errors for one WorkerFailureReceipt payload."""

    schema_payload = schema or _load_schema(DEFAULT_SCHEMA_PATH)
    errors = _validate_schema_instance(schema_payload, record)
    if not isinstance(record, dict):
        errors.append("worker failure receipt must be a JSON object")
        return errors

    if record.get("receipt_version") != EXPECTED_RECEIPT_VERSION:
        errors.append("receipt_version must match worker_failure_receipt.v1")
    _validate_counts(record, errors)
    _validate_failure_paths(record, errors)
    _validate_recovery_rules(record, errors)
    _validate_rollback_rules(record, errors)
    _validate_governance_guards(record.get("governance_guards"), errors)
    _require_subset(record, "evidence_refs", REQUIRED_EVIDENCE_REFS, errors)
    return errors


def validate_receipt(
    schema_path: Path = DEFAULT_SCHEMA_PATH,
    receipt_path: Path = DEFAULT_RECEIPT_PATH,
) -> list[str]:
    """Validate the schema artifact and default Foundation Mode receipt."""

    schema = _load_schema(schema_path)
    receipt = load_json_object(receipt_path, "WorkerFailureReceipt")
    errors = validate_schema_artifact(schema)
    errors.extend(validate_receipt_record(receipt, schema))
    return errors


def workspace_display_path(path: Path) -> str:
    """Return a stable workspace-relative display path when possible."""

    resolved_path = path if path.is_absolute() else WORKSPACE_ROOT / path
    try:
        return str(resolved_path.resolve().relative_to(WORKSPACE_ROOT))
    except ValueError:
        return str(path)


def build_mutated_receipt(**updates: Any) -> dict[str, Any]:
    """Build a deterministic mutated copy of the default receipt for tests."""

    receipt = load_json_object(DEFAULT_RECEIPT_PATH, "WorkerFailureReceipt")
    mutated = deepcopy(receipt)
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


def _validate_counts(record: dict[str, Any], errors: list[str]) -> None:
    summary = record.get("failure_summary")
    if not isinstance(summary, dict):
        errors.append("failure_summary must be an object")
        return
    counted_fields = {
        "completed_step_count": record.get("completed_step_refs"),
        "failed_step_count": record.get("failed_step_refs"),
        "partial_effect_count": record.get("partial_effect_refs"),
        "rollback_action_count": record.get("rollback_action_refs"),
        "recovery_action_count": record.get("recovery_action_refs"),
        "blocked_reason_count": record.get("blocked_reason_refs"),
    }
    for summary_field, collection in counted_fields.items():
        if isinstance(collection, list) and summary.get(summary_field) != len(collection):
            errors.append(f"failure_summary.{summary_field} must match {summary_field.removesuffix('_count')} list length")
    if summary.get("raw_output_included") is not False:
        errors.append("raw worker output must not be included")
    if summary.get("raw_secret_material_included") is not False:
        errors.append("raw secret material must not be included")


def _validate_failure_paths(record: dict[str, Any], errors: list[str]) -> None:
    failed_step_refs = record.get("failed_step_refs")
    if not isinstance(failed_step_refs, list) or not failed_step_refs:
        errors.append("worker failure receipt requires failed_step_refs")
    if record.get("receipt_state") == "FAILED_BEFORE_EXECUTION" and record.get("effect_status") != "no_effect_confirmed":
        errors.append("FAILED_BEFORE_EXECUTION requires no_effect_confirmed")
    if record.get("effect_status") == "no_effect_confirmed" and record.get("partial_effect_refs"):
        errors.append("no_effect_confirmed cannot include partial_effect_refs")
    if record.get("effect_status") == "partial_effect_recorded" and not record.get("partial_effect_refs"):
        errors.append("partial_effect_recorded requires partial_effect_refs")


def _validate_recovery_rules(record: dict[str, Any], errors: list[str]) -> None:
    receipt_state = record.get("receipt_state")
    effect_status = record.get("effect_status")
    recovery_action_refs = record.get("recovery_action_refs")
    blocked_reason_refs = record.get("blocked_reason_refs")
    needs_recovery = receipt_state in RECOVERY_STATES or effect_status in PARTIAL_OR_UNKNOWN_EFFECTS
    if needs_recovery and record.get("recovery_required") is not True:
        errors.append("partial, timeout, rollback, recovery, or unknown effect states require recovery_required true")
    if record.get("recovery_required") is True:
        if not isinstance(recovery_action_refs, list) or not isinstance(blocked_reason_refs, list):
            errors.append("recovery_required requires recovery_action_refs and blocked_reason_refs lists")
        elif not recovery_action_refs and not blocked_reason_refs:
            errors.append("recovery_required requires recovery_action_refs or blocked_reason_refs")
    if receipt_state == "SAFE_HALT_RECORDED" and record.get("solver_outcome") != "SafeHalt":
        errors.append("SAFE_HALT_RECORDED requires solver_outcome SafeHalt")


def _validate_rollback_rules(record: dict[str, Any], errors: list[str]) -> None:
    receipt_state = record.get("receipt_state")
    rollback_action_refs = record.get("rollback_action_refs")
    if receipt_state == "ROLLBACK_REQUIRED" and record.get("rollback_required") is not True:
        errors.append("ROLLBACK_REQUIRED requires rollback_required true")
    if record.get("rollback_required") is True:
        if not isinstance(rollback_action_refs, list) or not rollback_action_refs:
            errors.append("rollback_required requires rollback_action_refs")
    if receipt_state == "FAILED_BEFORE_EXECUTION" and record.get("rollback_required") is True:
        errors.append("FAILED_BEFORE_EXECUTION cannot require rollback")


def _validate_governance_guards(guards: Any, errors: list[str]) -> None:
    if not isinstance(guards, dict):
        errors.append("governance_guards must be an object")
        return
    for guard_name in FALSE_GUARDS:
        if guards.get(guard_name) is not False:
            errors.append(f"governance_guards.{guard_name} must be false")
    if guards.get("mfidel_atomicity_preserved") is not True:
        errors.append("governance_guards.mfidel_atomicity_preserved must be true")
    if guards.get("partial_or_unknown_effect_requires_recovery") is not True:
        errors.append("governance_guards.partial_or_unknown_effect_requires_recovery must be true")


def _require_subset(record: dict[str, Any], field_name: str, required_values: tuple[str, ...], errors: list[str]) -> None:
    values = record.get(field_name)
    if not isinstance(values, list):
        errors.append(f"{field_name} must be a list")
        return
    for missing_value in sorted(set(required_values) - set(values)):
        errors.append(f"{field_name} missing required ref: {missing_value}")


def main(argv: list[str] | None = None) -> int:
    """Validate WorkerFailureReceipt artifacts from the command line."""

    parser = argparse.ArgumentParser(description="Validate WorkerFailureReceipt contract.")
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA_PATH)
    parser.add_argument("--receipt", type=Path, default=DEFAULT_RECEIPT_PATH)
    parser.add_argument("--json", action="store_true", help="emit a machine-readable receipt")
    args = parser.parse_args(argv)
    errors = validate_receipt(args.schema, args.receipt)
    if args.json:
        print(
            json.dumps(
                {
                    "receipt_id": "worker_failure_receipt_validation",
                    "schema_path": workspace_display_path(args.schema),
                    "receipt_path": workspace_display_path(args.receipt),
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
        print("[PASS] worker_failure_receipt")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
