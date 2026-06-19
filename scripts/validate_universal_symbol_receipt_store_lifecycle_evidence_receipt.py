"""Validate the Universal Symbol receipt-store lifecycle evidence receipt.

Purpose: prove receipt-store lifecycle evidence remains explicit and
non-authorizing until live active grant, temporal, revocation, replacement, and
audit evidence exists.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: lifecycle evidence schema/example, reapproval revocation witness,
approval decision witness, temporal reapproval receipt schema, docs, proof
coverage matrix, and tests.
Invariants:
  - The receipt is not lifecycle authority.
  - Reapproval, revocation, grant extension, replacement decision, lifecycle
    audit commit, receipt append, raw payload storage, raw secret storage,
    runtime dispatch, connector calls, mutation, and terminal closure remain
    denied.
  - Missing live lifecycle evidence blocks lifecycle recording and logs
    Delta_reject refs.
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
DEFAULT_SCHEMA_PATH = (
    REPO_ROOT / "schemas" / "universal_symbol_receipt_store_lifecycle_evidence_receipt.schema.json"
)
DEFAULT_RECEIPT_PATH = (
    REPO_ROOT / "examples" / "universal_symbol_receipt_store_lifecycle_evidence_receipt.foundation.json"
)

AUTHORITY_DENIAL_FIELDS: tuple[str, ...] = (
    "receipt_store_reapproval_recorded",
    "receipt_store_revocation_recorded",
    "approval_grant_extended",
    "replacement_decision_recorded",
    "lifecycle_audit_committed",
    "receipt_store_append_performed",
    "raw_payload_stored",
    "raw_secret_stored",
    "runtime_dispatch_performed",
    "connector_call_performed",
    "state_mutation_performed",
    "terminal_closure_allowed",
)

REQUIRED_EVIDENCE_KINDS: tuple[str, ...] = (
    "active_grant_identity",
    "reapproval_window",
    "expiry_evidence",
    "revocation_request",
    "revocation_effect_boundary",
    "replacement_decision",
    "lifecycle_audit_receipt",
)

CONSISTENCY_CONSTRAINT_TRUE_FIELDS: tuple[str, ...] = (
    "active_grant_matches_approval_decision_required",
    "reapproval_window_after_decision_required",
    "expiry_after_grant_required",
    "revocation_effect_boundary_required",
    "replacement_decision_links_revoked_grant_required",
    "lifecycle_audit_receipt_required",
    "all_live_evidence_required_before_lifecycle_recording",
)

REJECTION_POLICY_TRUE_FIELDS: tuple[str, ...] = (
    "missing_active_grant_blocks_lifecycle_recording",
    "missing_reapproval_window_blocks_lifecycle_recording",
    "missing_expiry_evidence_blocks_lifecycle_recording",
    "missing_revocation_request_blocks_lifecycle_recording",
    "missing_replacement_decision_blocks_lifecycle_recording",
    "missing_lifecycle_audit_blocks_lifecycle_recording",
    "unknown_hard_constraint_blocks_lifecycle_recording",
    "failed_precondition_logs_delta_reject",
)

REQUIRED_BLOCKED_REASONS: tuple[str, ...] = (
    "active_grant_identity_missing",
    "reapproval_window_missing",
    "expiry_evidence_missing",
    "revocation_request_missing",
    "revocation_effect_boundary_missing",
    "replacement_decision_path_missing",
    "lifecycle_audit_receipt_missing",
    "receipt_store_lifecycle_recording_forbidden",
    "terminal_closure_not_allowed",
)

REQUIRED_EVIDENCE_REFS: tuple[str, ...] = (
    "schemas/universal_symbol_receipt_store_lifecycle_evidence_receipt.schema.json",
    "examples/universal_symbol_receipt_store_lifecycle_evidence_receipt.foundation.json",
    "schemas/universal_symbol_receipt_store_lifecycle_evidence_bundle.schema.json",
    "examples/universal_symbol_receipt_store_lifecycle_evidence_bundle.foundation.json",
    "schemas/universal_symbol_receipt_store_reapproval_revocation_witness.schema.json",
    "examples/universal_symbol_receipt_store_reapproval_revocation_witness.foundation.json",
    "schemas/universal_symbol_receipt_store_operator_reapproval_expiry_witness.schema.json",
    "examples/universal_symbol_receipt_store_operator_reapproval_expiry_witness.foundation.json",
    "schemas/universal_symbol_receipt_store_operator_revocation_witness.schema.json",
    "examples/universal_symbol_receipt_store_operator_revocation_witness.foundation.json",
    "schemas/universal_symbol_receipt_store_replacement_decision_receipt.schema.json",
    "examples/universal_symbol_receipt_store_replacement_decision_receipt.foundation.json",
    "schemas/universal_symbol_receipt_store_operator_approval_decision_witness.schema.json",
    "examples/universal_symbol_receipt_store_operator_approval_decision_witness.foundation.json",
    "schemas/temporal_reapproval_receipt.schema.json",
    "schemas/universal_symbol.schema.json",
    "docs/91_universal_symbol_kernel.md",
    "docs/92_universal_symbol_kernel_audit.md",
    "scripts/validate_universal_symbol_receipt_store_lifecycle_evidence_receipt.py",
    "scripts/produce_universal_symbol_receipt_store_lifecycle_evidence_receipt.py",
    "scripts/verify_universal_symbol_receipt_store_lifecycle_evidence_refs.py",
    "scripts/validate_universal_symbol_receipt_store_operator_reapproval_expiry_witness.py",
    "scripts/validate_universal_symbol_receipt_store_operator_revocation_witness.py",
    "scripts/validate_universal_symbol_receipt_store_replacement_decision_receipt.py",
    "tests/test_validate_universal_symbol_receipt_store_lifecycle_evidence_receipt.py",
    "tests/test_produce_universal_symbol_receipt_store_lifecycle_evidence_receipt.py",
    "tests/test_verify_universal_symbol_receipt_store_lifecycle_evidence_refs.py",
    "scripts/validate_universal_symbol_receipt_store_lifecycle_evidence_bundle.py",
    "tests/test_validate_universal_symbol_receipt_store_lifecycle_evidence_bundle.py",
    "scripts/proof_coverage_matrix.py",
    "tests/test_proof_coverage_matrix.py",
)


class UniversalSymbolReceiptStoreLifecycleEvidenceReceiptError(ValueError):
    """Raised when the lifecycle evidence receipt violates Foundation Mode."""


def load_json_object(path: Path) -> dict[str, Any]:
    """Return a JSON object or raise a validation error with causal context."""

    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise UniversalSymbolReceiptStoreLifecycleEvidenceReceiptError(f"missing file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise UniversalSymbolReceiptStoreLifecycleEvidenceReceiptError(f"invalid json: {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise UniversalSymbolReceiptStoreLifecycleEvidenceReceiptError(f"expected object: {path}")
    return value


def validate_universal_symbol_receipt_store_lifecycle_evidence_receipt(
    receipt_path: Path = DEFAULT_RECEIPT_PATH,
    schema_path: Path = DEFAULT_SCHEMA_PATH,
) -> dict[str, Any]:
    """Validate schema shape, denied lifecycle authority, and evidence refs."""

    schema = load_json_object(schema_path)
    receipt = load_json_object(receipt_path)
    errors: list[str] = []

    _validate_schema_boundary(schema, errors)
    _validate_json_schema(receipt, schema, errors)
    _validate_receipt_boundary(receipt, errors)
    _validate_lifecycle_subject(receipt, errors)
    _validate_live_evidence_requirements(receipt, errors)
    _validate_consistency_constraints(receipt, errors)
    _validate_authority_denials(receipt, errors)
    _validate_rejection_policy(receipt, errors)
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
        "lifecycle_evidence_decision": receipt.get("lifecycle_evidence_decision", ""),
        "authority_denial_count": len(AUTHORITY_DENIAL_FIELDS),
        "live_evidence_requirement_count": len(receipt.get("required_live_evidence", []))
        if isinstance(receipt.get("required_live_evidence"), list)
        else 0,
        "evidence_ref_count": len(receipt.get("evidence_refs", []))
        if isinstance(receipt.get("evidence_refs"), list)
        else 0,
        "errors": errors,
    }
    if errors:
        raise UniversalSymbolReceiptStoreLifecycleEvidenceReceiptError("; ".join(errors))
    return report


def _validate_schema_boundary(schema: Mapping[str, Any], errors: list[str]) -> None:
    if schema.get("$id") != "urn:mullusi:schema:universal-symbol-receipt-store-lifecycle-evidence-receipt:1":
        errors.append("schema id drift")
    if schema.get("additionalProperties") is not False:
        errors.append("schema must reject additional properties")
    required = schema.get("required")
    if not isinstance(required, list) or "authority_denials" not in required:
        errors.append("schema must require authority_denials")


def _validate_json_schema(receipt: Mapping[str, Any], schema: Mapping[str, Any], errors: list[str]) -> None:
    if jsonschema is None:
        errors.append("jsonschema dependency missing")
        return
    validator = jsonschema.Draft202012Validator(schema, format_checker=jsonschema.FormatChecker())
    schema_errors = sorted(validator.iter_errors(receipt), key=lambda error: tuple(error.path))
    for error in schema_errors:
        path = ".".join(str(part) for part in error.absolute_path) or "$"
        errors.append(f"schema validation failed at {path}: {error.message}")


def _validate_receipt_boundary(receipt: Mapping[str, Any], errors: list[str]) -> None:
    if receipt.get("foundation_mode") is not True:
        errors.append("foundation_mode must remain true")
    if receipt.get("solver_outcome") != "AwaitingEvidence":
        errors.append("solver_outcome must remain AwaitingEvidence")
    if (
        receipt.get("lifecycle_evidence_decision")
        != "blocked_pending_live_grant_temporal_revocation_replacement_and_audit_evidence"
    ):
        errors.append("lifecycle_evidence_decision must remain blocked")
    if receipt.get("lifecycle_evidence_receipt_is_not_lifecycle_authority") is not True:
        errors.append("lifecycle evidence receipt must not grant lifecycle authority")


def _validate_lifecycle_subject(receipt: Mapping[str, Any], errors: list[str]) -> None:
    subject = _mapping(receipt.get("lifecycle_subject"))
    if subject.get("authority_scope") != "receipt-store-lifecycle-evidence-only":
        errors.append("lifecycle_subject.authority_scope must remain evidence-only")
    for field_name in (
        "symbol_ref",
        "approval_decision_witness_ref",
        "reapproval_revocation_witness_ref",
        "operator_reapproval_expiry_witness_ref",
        "operator_revocation_witness_ref",
        "replacement_decision_receipt_ref",
        "tenant_scope_ref",
    ):
        if not isinstance(subject.get(field_name), str) or not subject.get(field_name):
            errors.append(f"lifecycle_subject.{field_name} must be a non-empty ref")


def _validate_live_evidence_requirements(receipt: Mapping[str, Any], errors: list[str]) -> None:
    requirements = receipt.get("required_live_evidence")
    if not isinstance(requirements, list) or not requirements:
        errors.append("required_live_evidence must be non-empty")
        return
    evidence_kinds: list[str] = []
    for requirement in requirements:
        if not isinstance(requirement, dict):
            errors.append("live evidence requirement entries must be objects")
            continue
        evidence_kinds.append(str(requirement.get("evidence_kind")))
        if requirement.get("proof_state") not in {"Unknown", "BudgetUnknown", "Fail"}:
            errors.append(f"{requirement.get('evidence_id')}: proof_state must block lifecycle recording")
        if requirement.get("current_decision") != "lifecycle_recording_blocked":
            errors.append(f"{requirement.get('evidence_id')}: current_decision must be lifecycle_recording_blocked")
        if not str(requirement.get("delta_reject_ref", "")).startswith("delta-reject://"):
            errors.append(f"{requirement.get('evidence_id')}: delta_reject_ref must be logged")
    _require_members("required_live_evidence", evidence_kinds, REQUIRED_EVIDENCE_KINDS, errors)


def _validate_consistency_constraints(receipt: Mapping[str, Any], errors: list[str]) -> None:
    constraints = _mapping(receipt.get("evidence_consistency_constraints"))
    for field_name in CONSISTENCY_CONSTRAINT_TRUE_FIELDS:
        if constraints.get(field_name) is not True:
            errors.append(f"evidence_consistency_constraints.{field_name} must remain true")


def _validate_authority_denials(receipt: Mapping[str, Any], errors: list[str]) -> None:
    denials = _mapping(receipt.get("authority_denials"))
    for field_name in AUTHORITY_DENIAL_FIELDS:
        if denials.get(field_name) is not False:
            errors.append(f"authority_denials.{field_name} must remain false")


def _validate_rejection_policy(receipt: Mapping[str, Any], errors: list[str]) -> None:
    rejection_policy = _mapping(receipt.get("rejection_policy"))
    for field_name in REJECTION_POLICY_TRUE_FIELDS:
        if rejection_policy.get(field_name) is not True:
            errors.append(f"rejection_policy.{field_name} must remain true")


def _validate_blocked_reasons(receipt: Mapping[str, Any], errors: list[str]) -> None:
    blocked_reasons = receipt.get("blocked_reasons")
    if not isinstance(blocked_reasons, list):
        errors.append("blocked_reasons must be a list")
        return
    _require_members("blocked_reasons", [item for item in blocked_reasons if isinstance(item, str)], REQUIRED_BLOCKED_REASONS, errors)


def _validate_contract_summary(receipt: Mapping[str, Any], errors: list[str]) -> None:
    summary = _mapping(receipt.get("contract_summary"))
    observed_counts = {
        "live_evidence_requirement_count": _list_len(receipt.get("required_live_evidence")),
        "consistency_constraint_count": len(CONSISTENCY_CONSTRAINT_TRUE_FIELDS),
        "authority_denial_count": len(AUTHORITY_DENIAL_FIELDS),
        "rejection_check_count": len(REJECTION_POLICY_TRUE_FIELDS),
        "blocked_reason_count": _list_len(receipt.get("blocked_reasons")),
        "evidence_ref_count": _list_len(receipt.get("evidence_refs")),
    }
    for field_name, observed_count in observed_counts.items():
        if observed_count is not None and summary.get(field_name) != observed_count:
            errors.append(f"{field_name} drift")


def _validate_evidence_refs(receipt: Mapping[str, Any], errors: list[str]) -> None:
    refs = receipt.get("evidence_refs")
    if not isinstance(refs, list):
        errors.append("evidence_refs must be a list")
        return
    missing = tuple(ref for ref in REQUIRED_EVIDENCE_REFS if ref not in refs)
    if missing:
        errors.append("missing required evidence refs: " + ", ".join(missing))


def _validate_evidence_ref_files(receipt: Mapping[str, Any], errors: list[str]) -> None:
    refs = receipt.get("evidence_refs")
    if not isinstance(refs, list):
        return
    for ref in refs:
        if not isinstance(ref, str) or "://" in ref:
            continue
        ref_path = Path(ref)
        if ref_path.is_absolute():
            errors.append(f"evidence ref must be repository-relative: {ref}")
            continue
        resolved = (REPO_ROOT / ref_path).resolve()
        if REPO_ROOT.resolve() not in resolved.parents and resolved != REPO_ROOT.resolve():
            errors.append(f"evidence ref escapes repository: {ref}")
            continue
        if not resolved.exists():
            errors.append(f"evidence ref file missing: {ref}")


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _list_len(value: Any) -> int | None:
    return len(value) if isinstance(value, list) else None


def _require_members(
    field_name: str,
    observed_values: list[str],
    required_values: tuple[str, ...],
    errors: list[str],
) -> None:
    for missing_value in sorted(set(required_values) - set(observed_values)):
        errors.append(f"{field_name} missing required value: {missing_value}")
    if len(observed_values) != len(set(observed_values)):
        errors.append(f"{field_name} values must be unique")


def _repo_relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return str(path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--receipt", type=Path, default=DEFAULT_RECEIPT_PATH)
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA_PATH)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    try:
        report = validate_universal_symbol_receipt_store_lifecycle_evidence_receipt(
            args.receipt,
            args.schema,
        )
    except UniversalSymbolReceiptStoreLifecycleEvidenceReceiptError as exc:
        if args.json:
            print(json.dumps({"valid": False, "errors": str(exc).split("; ")}, indent=2, sort_keys=True))
        else:
            print(f"[FAIL] universal_symbol_receipt_store_lifecycle_evidence_receipt: {exc}")
            print("STATUS: failed")
        return 1

    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print("[PASS] universal_symbol_receipt_store_lifecycle_evidence_receipt")
        print("STATUS: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
