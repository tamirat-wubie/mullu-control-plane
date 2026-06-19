"""Validate the Universal Symbol lane runtime authority evidence value receipt.

Purpose: prove lane-level evidence refs can be recorded without verifying them,
granting lane runtime authority, admitting runtime, dispatching, appending, or
allowing terminal closure.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: lane evidence value schema/example, lane evidence receipt, skill
runtime authority witness, runtime live witness input receipt, docs, and tests.
Invariants:
  - The receipt stores refs only, not raw evidence payloads.
  - Every lane and evidence kind remains ProofState Unknown, BudgetUnknown, or Fail.
  - Lane runtime authority, runtime admission, dispatch, connector calls,
    writes, receipt append, mutation, and terminal closure remain denied.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping

try:
    import jsonschema
except ImportError:  # pragma: no cover - dependency is expected in CI/dev envs.
    jsonschema = None


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SCHEMA_PATH = REPO_ROOT / "schemas" / "universal_symbol_lane_runtime_authority_evidence_value_receipt.schema.json"
DEFAULT_RECEIPT_PATH = (
    REPO_ROOT / "examples" / "universal_symbol_lane_runtime_authority_evidence_value_receipt.foundation.json"
)

LANES: dict[str, str] = {
    "skill://teamops-shared-inbox": "skill",
    "skill://software-dev": "skill",
    "component://governance-core": "component",
    "receipt://worker-ledger": "receipt",
}

EVIDENCE_KINDS: tuple[str, ...] = (
    "operator_approval",
    "receipt_store_authority",
    "recovery_evidence",
    "audit_receipt",
    "live_runtime_witness",
    "blocked_action_refs",
)

CONSTRAINT_TRUE_FIELDS: tuple[str, ...] = (
    "ref_only_input_required",
    "raw_evidence_value_storage_forbidden",
    "operator_supplied_refs_are_not_authority",
    "all_lanes_require_all_value_kinds",
    "live_runtime_witness_still_required",
    "receipt_store_authority_still_required",
    "audit_and_recovery_still_required",
    "terminal_closure_denial_required",
)

AUTHORITY_DENIAL_FIELDS: tuple[str, ...] = (
    "lane_runtime_authority_granted",
    "runtime_admission_granted",
    "runtime_registration_performed",
    "skill_admission_recorded",
    "live_dispatch_enabled",
    "connector_call_enabled",
    "filesystem_write_enabled",
    "external_write_enabled",
    "receipt_store_append_enabled",
    "raw_payload_stored",
    "raw_secret_stored",
    "state_mutation_performed",
    "terminal_closure_allowed",
)

REJECTION_POLICY_TRUE_FIELDS: tuple[str, ...] = (
    "missing_lane_value_blocks_lane_authority",
    "unverified_value_ref_blocks_lane_authority",
    "raw_value_payload_blocks_receipt",
    "missing_receipt_store_authority_blocks_lane_authority",
    "missing_recovery_or_audit_blocks_lane_authority",
    "unknown_hard_constraint_blocks_lane_authority",
    "failed_precondition_logs_delta_reject",
)

REQUIRED_BLOCKED_REASONS: tuple[str, ...] = (
    "lane_evidence_values_unverified",
    "operator_approval_value_not_authority",
    "receipt_store_authority_value_not_authority",
    "recovery_value_not_execution",
    "audit_value_not_closure",
    "live_runtime_witness_value_not_acceptance",
    "blocked_action_refs_not_terminal_closure",
    "lane_runtime_authority_forbidden",
    "runtime_admission_forbidden",
    "terminal_closure_not_allowed",
)

REQUIRED_EVIDENCE_REFS: tuple[str, ...] = (
    "schemas/universal_symbol_lane_runtime_authority_evidence_value_receipt.schema.json",
    "examples/universal_symbol_lane_runtime_authority_evidence_value_receipt.foundation.json",
    "schemas/universal_symbol_lane_runtime_authority_evidence_receipt.schema.json",
    "examples/universal_symbol_lane_runtime_authority_evidence_receipt.foundation.json",
    "schemas/universal_symbol_skill_runtime_authority_witness.schema.json",
    "examples/universal_symbol_skill_runtime_authority_witness.foundation.json",
    "schemas/universal_symbol_runtime_live_witness_input_receipt.schema.json",
    "examples/universal_symbol_runtime_live_witness_input_receipt.foundation.json",
    "schemas/universal_symbol_runtime_admission_evidence_receipt.schema.json",
    "examples/universal_symbol_runtime_admission_evidence_receipt.foundation.json",
    "docs/91_universal_symbol_kernel.md",
    "docs/92_universal_symbol_kernel_audit.md",
    "scripts/produce_universal_symbol_lane_runtime_authority_evidence_value_receipt.py",
    "scripts/validate_universal_symbol_lane_runtime_authority_evidence_value_receipt.py",
    "scripts/proof_coverage_matrix.py",
    "tests/test_produce_universal_symbol_lane_runtime_authority_evidence_value_receipt.py",
    "tests/test_validate_universal_symbol_kernel.py",
    "tests/test_proof_coverage_matrix.py",
)


class UniversalSymbolLaneRuntimeAuthorityEvidenceValueReceiptError(ValueError):
    """Raised when the lane evidence value receipt violates Foundation Mode."""


def load_json_object(path: Path) -> dict[str, Any]:
    """Return a JSON object or raise a validation error with causal context."""

    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise UniversalSymbolLaneRuntimeAuthorityEvidenceValueReceiptError(f"missing file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise UniversalSymbolLaneRuntimeAuthorityEvidenceValueReceiptError(f"invalid json: {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise UniversalSymbolLaneRuntimeAuthorityEvidenceValueReceiptError(f"expected object: {path}")
    return value


def validate_universal_symbol_lane_runtime_authority_evidence_value_receipt(
    receipt_path: Path = DEFAULT_RECEIPT_PATH,
    schema_path: Path = DEFAULT_SCHEMA_PATH,
) -> dict[str, Any]:
    """Validate schema shape, lane value refs, and denied authority."""

    schema = load_json_object(schema_path)
    receipt = load_json_object(receipt_path)
    errors: list[str] = []

    _validate_schema_boundary(schema, errors)
    _validate_json_schema(receipt, schema, errors)
    _validate_receipt_boundary(receipt, errors)
    _validate_subject(receipt, errors)
    _validate_lane_value_items(receipt, errors)
    _validate_true_fields(receipt.get("evidence_value_constraints"), CONSTRAINT_TRUE_FIELDS, errors)
    _validate_false_fields(receipt.get("authority_denials"), AUTHORITY_DENIAL_FIELDS, errors)
    _validate_true_fields(receipt.get("rejection_policy"), REJECTION_POLICY_TRUE_FIELDS, errors)
    _validate_blocked_reasons(receipt, errors)
    _validate_contract_summary(receipt, errors)
    _validate_evidence_refs(receipt, errors)
    _validate_evidence_ref_files(receipt, errors)

    report = {
        "receipt_path": _repo_relative(receipt_path),
        "schema_path": _repo_relative(schema_path),
        "valid": not errors,
        "receipt_id": receipt.get("receipt_id", ""),
        "solver_outcome": receipt.get("solver_outcome", ""),
        "value_receipt_decision": receipt.get("value_receipt_decision", ""),
        "lane_count": len(LANES),
        "evidence_value_kind_count": len(EVIDENCE_KINDS),
        "evidence_value_item_count": _list_len(receipt.get("lane_value_items")) or 0,
        "authority_denial_count": len(AUTHORITY_DENIAL_FIELDS),
        "evidence_ref_count": _list_len(receipt.get("evidence_refs")) or 0,
        "errors": errors,
    }
    if errors:
        raise UniversalSymbolLaneRuntimeAuthorityEvidenceValueReceiptError("; ".join(errors))
    return report


def validate_lane_runtime_authority_evidence_value_receipt_object(
    receipt: Mapping[str, Any],
    *,
    schema_path: Path = DEFAULT_SCHEMA_PATH,
) -> list[str]:
    """Return validation errors for a generated lane evidence value receipt."""

    schema = load_json_object(schema_path)
    errors: list[str] = []
    _validate_json_schema(receipt, schema, errors)
    _validate_receipt_boundary(receipt, errors)
    _validate_lane_value_items(receipt, errors)
    _validate_false_fields(receipt.get("authority_denials"), AUTHORITY_DENIAL_FIELDS, errors)
    return errors


def _validate_schema_boundary(schema: Mapping[str, Any], errors: list[str]) -> None:
    if schema.get("$id") != "urn:mullusi:schema:universal-symbol-lane-runtime-authority-evidence-value-receipt:1":
        errors.append("schema id drift")
    if schema.get("additionalProperties") is not False:
        errors.append("schema must reject additional properties")
    required = schema.get("required")
    if not isinstance(required, list) or "lane_value_items" not in required:
        errors.append("schema must require lane_value_items")


def _validate_json_schema(receipt: Mapping[str, Any], schema: Mapping[str, Any], errors: list[str]) -> None:
    if jsonschema is None:
        errors.append("jsonschema dependency missing")
        return
    validator = jsonschema.Draft202012Validator(schema, format_checker=jsonschema.FormatChecker())
    for error in sorted(validator.iter_errors(receipt), key=lambda item: tuple(item.path)):
        path = ".".join(str(part) for part in error.absolute_path) or "$"
        errors.append(f"schema validation failed at {path}: {error.message}")


def _validate_receipt_boundary(receipt: Mapping[str, Any], errors: list[str]) -> None:
    if receipt.get("foundation_mode") is not True:
        errors.append("foundation_mode must remain true")
    if receipt.get("solver_outcome") != "AwaitingEvidence":
        errors.append("solver_outcome must remain AwaitingEvidence")
    if receipt.get("value_receipt_decision") != (
        "blocked_pending_lane_evidence_value_verification_runtime_authority_and_admission"
    ):
        errors.append("value_receipt_decision must remain blocked")
    if receipt.get("receipt_is_not_lane_authority") is not True:
        errors.append("receipt must not be lane authority")


def _validate_subject(receipt: Mapping[str, Any], errors: list[str]) -> None:
    subject = receipt.get("value_subject")
    if not isinstance(subject, dict):
        errors.append("value_subject must be object")
        return
    expected = {
        "lane_runtime_authority_evidence_receipt_ref": "schemas/universal_symbol_lane_runtime_authority_evidence_receipt.schema.json",
        "skill_runtime_authority_witness_ref": "schemas/universal_symbol_skill_runtime_authority_witness.schema.json",
        "runtime_live_witness_input_receipt_ref": "schemas/universal_symbol_runtime_live_witness_input_receipt.schema.json",
        "value_scope": "lane-runtime-authority-evidence-refs-only",
    }
    for field, value in expected.items():
        if subject.get(field) != value:
            errors.append(f"value_subject {field} drift")


def _validate_lane_value_items(receipt: Mapping[str, Any], errors: list[str]) -> None:
    items = receipt.get("lane_value_items")
    if not isinstance(items, list):
        errors.append("lane_value_items must be list")
        return
    observed_pairs: set[tuple[str, str]] = set()
    for item in items:
        if not isinstance(item, dict):
            errors.append("lane value item must be object")
            continue
        lane_ref = item.get("lane_ref")
        evidence_kind = item.get("evidence_kind")
        observed_pairs.add((str(lane_ref), str(evidence_kind)))
        if lane_ref not in LANES:
            errors.append(f"unknown lane_ref: {lane_ref}")
        elif item.get("symbol_kind") != LANES[str(lane_ref)]:
            errors.append(f"{lane_ref}: symbol_kind drift")
        if evidence_kind not in EVIDENCE_KINDS:
            errors.append(f"{lane_ref}: unknown evidence_kind {evidence_kind}")
        if item.get("proof_state") not in {"Unknown", "BudgetUnknown", "Fail"}:
            errors.append(f"{lane_ref}: proof_state must remain blocking")
        if item.get("value_state") != "operator_reference_recorded_not_verified":
            errors.append(f"{lane_ref}: value_state must remain unverified")
        if item.get("current_decision") != "lane_runtime_authority_blocked":
            errors.append(f"{lane_ref}: current_decision must remain blocked")
        supplied_ref = item.get("supplied_evidence_ref")
        if not isinstance(supplied_ref, str) or not supplied_ref.strip():
            errors.append(f"{lane_ref}: supplied_evidence_ref must be non-empty")
        if _looks_like_raw_secret(str(supplied_ref)):
            errors.append(f"{lane_ref}: supplied_evidence_ref must not contain raw secret-like value")
        delta_reject_ref = item.get("delta_reject_ref")
        if not isinstance(delta_reject_ref, str) or not delta_reject_ref.startswith("delta-reject://"):
            errors.append(f"{lane_ref}: delta_reject_ref drift")
    for lane_ref in LANES:
        for evidence_kind in EVIDENCE_KINDS:
            if (lane_ref, evidence_kind) not in observed_pairs:
                errors.append(f"missing lane evidence value: {lane_ref} {evidence_kind}")


def _validate_true_fields(value: object, fields: tuple[str, ...], errors: list[str]) -> None:
    if not isinstance(value, dict):
        errors.append("expected true-field object")
        return
    for field in fields:
        if value.get(field) is not True:
            errors.append(f"{field} must remain true")


def _validate_false_fields(value: object, fields: tuple[str, ...], errors: list[str]) -> None:
    if not isinstance(value, dict):
        errors.append("authority_denials must be object")
        return
    for field in fields:
        if value.get(field) is not False:
            errors.append(f"{field} must remain denied")


def _validate_blocked_reasons(receipt: Mapping[str, Any], errors: list[str]) -> None:
    reasons = receipt.get("blocked_reasons")
    if not isinstance(reasons, list):
        errors.append("blocked_reasons must be list")
        return
    for reason in REQUIRED_BLOCKED_REASONS:
        if reason not in reasons:
            errors.append(f"missing blocked reason: {reason}")


def _validate_contract_summary(receipt: Mapping[str, Any], errors: list[str]) -> None:
    summary = receipt.get("contract_summary")
    if not isinstance(summary, dict):
        errors.append("contract_summary must be object")
        return
    expected = {
        "lane_count": len(LANES),
        "evidence_value_kind_count": len(EVIDENCE_KINDS),
        "evidence_value_item_count": _list_len(receipt.get("lane_value_items")),
        "evidence_value_constraint_count": len(CONSTRAINT_TRUE_FIELDS),
        "authority_denial_count": len(AUTHORITY_DENIAL_FIELDS),
        "rejection_check_count": len(REJECTION_POLICY_TRUE_FIELDS),
        "blocked_reason_count": _list_len(receipt.get("blocked_reasons")),
        "evidence_ref_count": _list_len(receipt.get("evidence_refs")),
    }
    for field, value in expected.items():
        if value is not None and summary.get(field) != value:
            errors.append(f"{field} drift")


def _validate_evidence_refs(receipt: Mapping[str, Any], errors: list[str]) -> None:
    refs = receipt.get("evidence_refs")
    if not isinstance(refs, list):
        errors.append("evidence_refs must be list")
        return
    for ref in REQUIRED_EVIDENCE_REFS:
        if ref not in refs:
            errors.append(f"missing evidence ref: {ref}")


def _validate_evidence_ref_files(receipt: Mapping[str, Any], errors: list[str]) -> None:
    refs = receipt.get("evidence_refs")
    if not isinstance(refs, list):
        return
    for ref in refs:
        if isinstance(ref, str) and ref.startswith(("schemas/", "examples/", "docs/", "scripts/", "tests/")):
            if not (REPO_ROOT / ref).exists():
                errors.append(f"evidence ref missing file: {ref}")


def _looks_like_raw_secret(value: str) -> bool:
    lowered = value.lower()
    secret_markers = ("secret=", "token=", "password=", "private_key=", "api_key=")
    return any(marker in lowered for marker in secret_markers)


def _repo_relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def _list_len(value: object) -> int | None:
    return len(value) if isinstance(value, list) else None


def main(argv: list[str] | None = None) -> int:
    """Validate the lane runtime authority evidence value receipt and print status."""

    parser = argparse.ArgumentParser(
        description="Validate Universal Symbol lane runtime authority evidence value receipt."
    )
    parser.add_argument("--receipt", type=Path, default=DEFAULT_RECEIPT_PATH)
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA_PATH)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        report = validate_universal_symbol_lane_runtime_authority_evidence_value_receipt(args.receipt, args.schema)
    except UniversalSymbolLaneRuntimeAuthorityEvidenceValueReceiptError as exc:
        if args.json:
            print(json.dumps({"valid": False, "errors": str(exc).split("; ")}, indent=2, sort_keys=True))
        else:
            print(f"[FAIL] universal_symbol_lane_runtime_authority_evidence_value_receipt: {exc}")
            print("STATUS: failed")
        return 1
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0
    print("[PASS] universal_symbol_lane_runtime_authority_evidence_value_receipt")
    print("STATUS: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
