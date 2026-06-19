"""Validate the Universal Symbol receipt-store lifecycle audit receipt.

Purpose: prove UniversalSymbol receipt-store lifecycle audit recording remains
blocked until source lifecycle witness, approval decision witness, active grant,
lifecycle event kind, before/after authority envelope, Delta_reject ledger,
redaction/digest binding, and auditor identity evidence exist.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: lifecycle audit receipt schema/example, reapproval revocation
witness, operator approval decision witness, UniversalSymbol kernel docs, proof
coverage matrix, and tests.
Invariants:
  - The receipt is not lifecycle authority.
  - Lifecycle audit recording, reapproval recording, revocation recording,
    receipt append, replacement decision recording, raw payload storage, raw
    secret storage, runtime dispatch, connector calls, mutation, terminal
    closure, and production readiness remain denied.
  - Unknown hard preconditions block audit recording and log Delta_reject refs.
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
DEFAULT_SCHEMA_PATH = REPO_ROOT / "schemas" / "universal_symbol_receipt_store_lifecycle_audit_receipt.schema.json"
DEFAULT_RECEIPT_PATH = (
    REPO_ROOT / "examples" / "universal_symbol_receipt_store_lifecycle_audit_receipt.foundation.json"
)

AUTHORITY_DENIAL_FIELDS: tuple[str, ...] = (
    "receipt_store_lifecycle_audit_recorded",
    "receipt_store_reapproval_recorded",
    "receipt_store_revocation_recorded",
    "receipt_store_append_performed",
    "replacement_decision_recorded",
    "raw_payload_stored",
    "raw_secret_stored",
    "runtime_dispatch_performed",
    "connector_call_performed",
    "state_mutation_performed",
    "terminal_closure_allowed",
    "production_readiness_claimed",
)

REQUIRED_REQUIREMENT_IDS: tuple[str, ...] = (
    "requirement://source-lifecycle-witness",
    "requirement://approval-decision-witness",
    "requirement://active-grant-ref",
    "requirement://lifecycle-event-kind",
    "requirement://before-after-authority-envelope",
    "requirement://delta-reject-ledger",
    "requirement://redaction-digest-binding",
    "requirement://auditor-identity",
)

AUDIT_CONSTRAINT_TRUE_FIELDS: tuple[str, ...] = (
    "source_lifecycle_witness_required",
    "approval_decision_witness_required",
    "active_grant_ref_required",
    "lifecycle_event_kind_required",
    "before_after_authority_envelope_required",
    "delta_reject_ledger_required",
    "redaction_digest_binding_required",
    "auditor_identity_required",
)

REJECTION_POLICY_TRUE_FIELDS: tuple[str, ...] = (
    "missing_lifecycle_witness_blocks_audit",
    "missing_decision_or_grant_blocks_audit",
    "missing_authority_envelope_blocks_audit",
    "missing_delta_reject_or_digest_blocks_audit",
    "unknown_hard_constraint_blocks_audit",
    "failed_precondition_logs_delta_reject",
)

REQUIRED_BLOCKED_REASONS: tuple[str, ...] = (
    "source_lifecycle_witness_missing",
    "approval_decision_witness_missing",
    "active_grant_ref_missing",
    "lifecycle_event_kind_missing",
    "before_after_authority_envelope_missing",
    "delta_reject_ledger_missing",
    "redaction_digest_binding_missing",
    "auditor_identity_missing",
    "lifecycle_audit_recording_forbidden",
    "terminal_closure_not_allowed",
)

REQUIRED_EVIDENCE_REFS: tuple[str, ...] = (
    "schemas/universal_symbol_receipt_store_lifecycle_audit_receipt.schema.json",
    "examples/universal_symbol_receipt_store_lifecycle_audit_receipt.foundation.json",
    "schemas/universal_symbol_receipt_store_reapproval_revocation_witness.schema.json",
    "examples/universal_symbol_receipt_store_reapproval_revocation_witness.foundation.json",
    "schemas/universal_symbol_receipt_store_operator_approval_decision_witness.schema.json",
    "examples/universal_symbol_receipt_store_operator_approval_decision_witness.foundation.json",
    "schemas/universal_symbol.schema.json",
    "docs/91_universal_symbol_kernel.md",
    "docs/92_universal_symbol_kernel_audit.md",
    "scripts/validate_universal_symbol_receipt_store_lifecycle_audit_receipt.py",
    "tests/test_validate_universal_symbol_kernel.py",
    "scripts/proof_coverage_matrix.py",
    "tests/test_proof_coverage_matrix.py",
)


class UniversalSymbolReceiptStoreLifecycleAuditReceiptError(ValueError):
    """Raised when the lifecycle audit receipt violates Foundation Mode."""


def load_json_object(path: Path) -> dict[str, Any]:
    """Return a JSON object or raise a validation error with causal context."""

    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise UniversalSymbolReceiptStoreLifecycleAuditReceiptError(f"missing file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise UniversalSymbolReceiptStoreLifecycleAuditReceiptError(f"invalid json: {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise UniversalSymbolReceiptStoreLifecycleAuditReceiptError(f"expected object: {path}")
    return value


def validate_universal_symbol_receipt_store_lifecycle_audit_receipt(
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
    _validate_audit_requirements(receipt, errors)
    _validate_authority_denials(receipt, errors)
    _validate_audit_constraints(receipt, errors)
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
        "audit_decision": receipt.get("audit_decision", ""),
        "authority_denial_count": len(AUTHORITY_DENIAL_FIELDS),
        "audit_requirement_count": len(receipt.get("audit_requirements", []))
        if isinstance(receipt.get("audit_requirements"), list)
        else 0,
        "evidence_ref_count": len(receipt.get("evidence_refs", []))
        if isinstance(receipt.get("evidence_refs"), list)
        else 0,
        "errors": errors,
    }
    if errors:
        raise UniversalSymbolReceiptStoreLifecycleAuditReceiptError("; ".join(errors))
    return report


def _validate_schema_boundary(schema: Mapping[str, Any], errors: list[str]) -> None:
    if schema.get("$id") != "urn:mullusi:schema:universal-symbol-receipt-store-lifecycle-audit-receipt:1":
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
        receipt.get("audit_decision")
        != "blocked_pending_lifecycle_witness_decision_grant_delta_reject_digest_and_auditor_evidence"
    ):
        errors.append("audit_decision must remain blocked")
    if receipt.get("lifecycle_audit_receipt_is_not_lifecycle_authority") is not True:
        errors.append("lifecycle audit receipt must not grant lifecycle authority")


def _validate_audit_requirements(receipt: Mapping[str, Any], errors: list[str]) -> None:
    requirements = receipt.get("audit_requirements")
    if not isinstance(requirements, list) or not requirements:
        errors.append("audit_requirements must be non-empty")
        return
    requirement_ids: list[str] = []
    for requirement in requirements:
        if not isinstance(requirement, dict):
            errors.append("audit requirement entries must be objects")
            continue
        requirement_ids.append(str(requirement.get("requirement_id")))
        if requirement.get("proof_state") not in {"Unknown", "BudgetUnknown", "Fail"}:
            errors.append(f"{requirement.get('requirement_id')}: proof_state must block audit")
        if requirement.get("current_decision") != "lifecycle_audit_blocked":
            errors.append(f"{requirement.get('requirement_id')}: current_decision must block audit")
        if not str(requirement.get("delta_reject_ref", "")).startswith("delta-reject://"):
            errors.append(f"{requirement.get('requirement_id')}: delta_reject_ref must be logged")
    _require_members("audit_requirements", requirement_ids, REQUIRED_REQUIREMENT_IDS, errors)


def _validate_authority_denials(receipt: Mapping[str, Any], errors: list[str]) -> None:
    denials = _mapping(receipt.get("authority_denials"))
    for field_name in AUTHORITY_DENIAL_FIELDS:
        if denials.get(field_name) is not False:
            errors.append(f"authority_denials.{field_name} must remain false")


def _validate_audit_constraints(receipt: Mapping[str, Any], errors: list[str]) -> None:
    constraints = _mapping(receipt.get("audit_constraints"))
    for field_name in AUDIT_CONSTRAINT_TRUE_FIELDS:
        if constraints.get(field_name) is not True:
            errors.append(f"audit_constraints.{field_name} must remain true")


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
    _require_members("blocked_reasons", [str(reason) for reason in blocked_reasons], REQUIRED_BLOCKED_REASONS, errors)


def _validate_contract_summary(receipt: Mapping[str, Any], errors: list[str]) -> None:
    summary = _mapping(receipt.get("contract_summary"))
    requirements = receipt.get("audit_requirements")
    blocked_reasons = receipt.get("blocked_reasons")
    evidence_refs = receipt.get("evidence_refs")
    if isinstance(requirements, list) and summary.get("audit_requirement_count") != len(requirements):
        errors.append("audit_requirement_count drift")
    if summary.get("authority_denial_count") != len(AUTHORITY_DENIAL_FIELDS):
        errors.append("authority_denial_count drift")
    if summary.get("audit_constraint_count") != len(AUDIT_CONSTRAINT_TRUE_FIELDS):
        errors.append("audit_constraint_count drift")
    if summary.get("rejection_check_count") != len(REJECTION_POLICY_TRUE_FIELDS):
        errors.append("rejection_check_count drift")
    if isinstance(blocked_reasons, list) and summary.get("blocked_reason_count") != len(blocked_reasons):
        errors.append("blocked_reason_count drift")
    if isinstance(evidence_refs, list) and summary.get("evidence_ref_count") != len(evidence_refs):
        errors.append("evidence_ref_count drift")


def _validate_evidence_refs(receipt: Mapping[str, Any], errors: list[str]) -> None:
    evidence_refs = receipt.get("evidence_refs")
    if not isinstance(evidence_refs, list):
        errors.append("evidence_refs must be a list")
        return
    _require_members("evidence_refs", [str(ref) for ref in evidence_refs], REQUIRED_EVIDENCE_REFS, errors)


def _validate_evidence_ref_files(receipt: Mapping[str, Any], errors: list[str]) -> None:
    evidence_refs = receipt.get("evidence_refs")
    if not isinstance(evidence_refs, list):
        return
    for evidence_ref in evidence_refs:
        if not isinstance(evidence_ref, str):
            errors.append("evidence refs must be strings")
            continue
        if evidence_ref.startswith(("schemas/", "examples/", "docs/", "scripts/", "tests/")):
            path = REPO_ROOT / evidence_ref
            if not path.exists():
                errors.append(f"evidence ref missing: {evidence_ref}")


def _mapping(value: object) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return value
    return {}


def _require_members(name: str, observed: list[str], required: tuple[str, ...], errors: list[str]) -> None:
    missing = sorted(set(required) - set(observed))
    if missing:
        errors.append(f"{name} missing required values: {', '.join(missing)}")


def _repo_relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return str(path)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate the UniversalSymbol receipt-store lifecycle audit receipt."
    )
    parser.add_argument("--receipt", type=Path, default=DEFAULT_RECEIPT_PATH)
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA_PATH)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    try:
        report = validate_universal_symbol_receipt_store_lifecycle_audit_receipt(args.receipt, args.schema)
    except UniversalSymbolReceiptStoreLifecycleAuditReceiptError as exc:
        if args.json:
            print(json.dumps({"valid": False, "errors": [str(exc)]}, indent=2, sort_keys=True))
        else:
            print(f"[FAIL] universal_symbol_receipt_store_lifecycle_audit_receipt: {exc}")
        return 1

    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print("[PASS] universal_symbol_receipt_store_lifecycle_audit_receipt")
        print("STATUS: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
