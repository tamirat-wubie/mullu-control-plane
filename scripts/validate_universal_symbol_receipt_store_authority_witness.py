"""Validate the Universal Symbol receipt-store authority witness.

Purpose: prove UniversalSymbol receipt-store authority remains blocked until
append audit, writer registration, write-path registration, operator identity,
approval decision, lifecycle evidence, lifecycle audit, replacement decision,
idempotency, durability replay, and recovery evidence exist.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: authority witness schema/example, UniversalSymbol schema,
runtime admission policy, adapter persistence policy, docs, and tests.
Invariants:
  - The witness does not grant receipt-store authority.
  - Receipt-store writer registration, write-path registration, and append are
    denied.
  - Raw payloads, raw secrets, runtime dispatch, connector calls, mutation, and
    terminal closure remain denied.
  - Unknown hard preconditions block append and log Delta_reject references.
  - Operator approval, temporal lifecycle, revocation, lifecycle audit, and
    replacement-decision contracts are bound before append authority can exist.
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
DEFAULT_SCHEMA_PATH = REPO_ROOT / "schemas" / "universal_symbol_receipt_store_authority_witness.schema.json"
DEFAULT_WITNESS_PATH = REPO_ROOT / "examples" / "universal_symbol_receipt_store_authority_witness.foundation.json"

AUTHORITY_DENIAL_FIELDS: tuple[str, ...] = (
    "receipt_store_authority_granted",
    "receipt_store_writer_registered",
    "receipt_store_write_path_registered",
    "receipt_store_append_performed",
    "raw_payload_stored",
    "raw_secret_stored",
    "runtime_dispatch_performed",
    "connector_call_performed",
    "state_mutation_performed",
    "terminal_closure_allowed",
)

REJECTION_POLICY_TRUE_FIELDS: tuple[str, ...] = (
    "unknown_hard_constraint_blocks_append",
    "budget_unknown_escalates_to_phi_gov",
    "failed_precondition_logs_delta_reject",
    "raw_payload_rejected",
    "raw_secret_rejected",
    "terminal_closure_rejected",
)

REQUIRED_REQUIREMENT_IDS: tuple[str, ...] = (
    "requirement://append-audit-witness",
    "requirement://receipt-store-writer-registration",
    "requirement://receipt-store-write-path",
    "requirement://operator-approval",
    "requirement://operator-identity",
    "requirement://operator-approval-decision",
    "requirement://operator-reapproval-expiry",
    "requirement://operator-revocation",
    "requirement://lifecycle-evidence-receipt",
    "requirement://lifecycle-audit-receipt",
    "requirement://replacement-decision-receipt",
    "requirement://rollback-recovery",
    "requirement://idempotency",
    "requirement://durability-replay",
)

REQUIRED_PRECONDITION_IDS: tuple[str, ...] = (
    "precondition://authority-granted",
    "precondition://append-audit",
    "precondition://writer-registration",
    "precondition://write-path-registration",
    "precondition://operator-identity",
    "precondition://operator-approval-decision",
    "precondition://operator-reapproval-expiry",
    "precondition://operator-revocation",
    "precondition://lifecycle-evidence-receipt",
    "precondition://lifecycle-audit-receipt",
    "precondition://replacement-decision-receipt",
    "precondition://idempotency-key",
    "precondition://rollback-recovery",
    "precondition://raw-payload-secret-denial",
)

REQUIRED_BLOCKED_REASONS: tuple[str, ...] = (
    "append_audit_witness_not_admitted",
    "receipt_store_writer_registration_missing",
    "receipt_store_write_path_missing",
    "operator_approval_missing",
    "operator_identity_missing",
    "operator_approval_decision_missing",
    "operator_reapproval_expiry_missing",
    "operator_revocation_missing",
    "lifecycle_evidence_receipt_missing",
    "lifecycle_audit_receipt_missing",
    "replacement_decision_receipt_missing",
    "rollback_recovery_witness_missing",
    "idempotency_witness_missing",
    "durability_replay_witness_missing",
    "raw_payload_storage_forbidden",
    "raw_secret_storage_forbidden",
    "terminal_closure_not_allowed",
)

REQUIRED_EVIDENCE_REFS: tuple[str, ...] = (
    "schemas/universal_symbol_receipt_store_authority_witness.schema.json",
    "examples/universal_symbol_receipt_store_authority_witness.foundation.json",
    "schemas/universal_symbol_append_audit_witness.schema.json",
    "examples/universal_symbol_append_audit_witness.foundation.json",
    "schemas/universal_symbol_receipt_store_path_custody_witness.schema.json",
    "examples/universal_symbol_receipt_store_path_custody_witness.foundation.json",
    "schemas/universal_symbol_receipt_store_writer_identity_witness.schema.json",
    "examples/universal_symbol_receipt_store_writer_identity_witness.foundation.json",
    "schemas/universal_symbol_receipt_store_writer_registration_witness.schema.json",
    "examples/universal_symbol_receipt_store_writer_registration_witness.foundation.json",
    "schemas/universal_symbol_receipt_store_write_path_witness.schema.json",
    "examples/universal_symbol_receipt_store_write_path_witness.foundation.json",
    "schemas/universal_symbol_receipt_store_operator_approval_witness.schema.json",
    "examples/universal_symbol_receipt_store_operator_approval_witness.foundation.json",
    "scripts/validate_universal_symbol_receipt_store_operator_approval_witness.py",
    "schemas/universal_symbol_receipt_store_operator_identity_witness.schema.json",
    "examples/universal_symbol_receipt_store_operator_identity_witness.foundation.json",
    "scripts/validate_universal_symbol_receipt_store_operator_identity_witness.py",
    "schemas/universal_symbol_receipt_store_operator_approval_decision_witness.schema.json",
    "examples/universal_symbol_receipt_store_operator_approval_decision_witness.foundation.json",
    "scripts/validate_universal_symbol_receipt_store_operator_approval_decision_witness.py",
    "schemas/universal_symbol_receipt_store_operator_reapproval_expiry_witness.schema.json",
    "examples/universal_symbol_receipt_store_operator_reapproval_expiry_witness.foundation.json",
    "scripts/validate_universal_symbol_receipt_store_operator_reapproval_expiry_witness.py",
    "schemas/universal_symbol_receipt_store_operator_revocation_witness.schema.json",
    "examples/universal_symbol_receipt_store_operator_revocation_witness.foundation.json",
    "scripts/validate_universal_symbol_receipt_store_operator_revocation_witness.py",
    "schemas/universal_symbol_receipt_store_reapproval_revocation_witness.schema.json",
    "examples/universal_symbol_receipt_store_reapproval_revocation_witness.foundation.json",
    "scripts/validate_universal_symbol_receipt_store_reapproval_revocation_witness.py",
    "schemas/universal_symbol_receipt_store_lifecycle_evidence_receipt.schema.json",
    "examples/universal_symbol_receipt_store_lifecycle_evidence_receipt.foundation.json",
    "scripts/validate_universal_symbol_receipt_store_lifecycle_evidence_receipt.py",
    "schemas/universal_symbol_receipt_store_lifecycle_audit_receipt.schema.json",
    "examples/universal_symbol_receipt_store_lifecycle_audit_receipt.foundation.json",
    "scripts/validate_universal_symbol_receipt_store_lifecycle_audit_receipt.py",
    "schemas/universal_symbol_receipt_store_replacement_decision_receipt.schema.json",
    "examples/universal_symbol_receipt_store_replacement_decision_receipt.foundation.json",
    "scripts/validate_universal_symbol_receipt_store_replacement_decision_receipt.py",
    "schemas/universal_symbol_receipt_store_durability_replay_witness.schema.json",
    "examples/universal_symbol_receipt_store_durability_replay_witness.foundation.json",
    "schemas/universal_symbol_adapter_receipt_persistence_policy.schema.json",
    "examples/universal_symbol_adapter_receipt_persistence_policy.foundation.json",
    "schemas/universal_symbol_runtime_admission_policy.schema.json",
    "schemas/universal_symbol.schema.json",
    "docs/91_universal_symbol_kernel.md",
    "docs/92_universal_symbol_kernel_audit.md",
    "scripts/validate_universal_symbol_append_audit_witness.py",
    "scripts/validate_universal_symbol_receipt_store_path_custody_witness.py",
    "scripts/validate_universal_symbol_receipt_store_writer_identity_witness.py",
    "scripts/validate_universal_symbol_receipt_store_writer_registration_witness.py",
    "scripts/validate_universal_symbol_receipt_store_write_path_witness.py",
    "scripts/validate_universal_symbol_receipt_store_durability_replay_witness.py",
    "scripts/validate_universal_symbol_receipt_store_authority_witness.py",
    "tests/test_validate_universal_symbol_kernel.py",
    "scripts/proof_coverage_matrix.py",
    "tests/test_proof_coverage_matrix.py",
)


class UniversalSymbolReceiptStoreAuthorityWitnessError(ValueError):
    """Raised when the receipt-store authority witness violates Foundation Mode."""


def load_json_object(path: Path) -> dict[str, Any]:
    """Return a JSON object or raise a validation error with causal context."""

    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise UniversalSymbolReceiptStoreAuthorityWitnessError(f"missing file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise UniversalSymbolReceiptStoreAuthorityWitnessError(f"invalid json: {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise UniversalSymbolReceiptStoreAuthorityWitnessError(f"expected object: {path}")
    return value


def validate_universal_symbol_receipt_store_authority_witness(
    witness_path: Path = DEFAULT_WITNESS_PATH,
    schema_path: Path = DEFAULT_SCHEMA_PATH,
) -> dict[str, Any]:
    """Validate schema shape, denied authority, and append-blocking evidence."""

    schema = load_json_object(schema_path)
    witness = load_json_object(witness_path)
    errors: list[str] = []

    _validate_schema_boundary(schema, errors)
    _validate_json_schema(witness, schema, errors)
    _validate_witness_boundary(witness, errors)
    _validate_authority_requirements(witness, errors)
    _validate_authority_denials(witness, errors)
    _validate_append_preconditions(witness, errors)
    _validate_rejection_policy(witness, errors)
    _validate_blocked_reasons(witness, errors)
    _validate_contract_summary(witness, errors)
    _validate_evidence_refs(witness, errors)
    _validate_evidence_ref_files(witness, errors)

    result = {
        "witness_path": _repo_relative(witness_path),
        "schema_path": _repo_relative(schema_path),
        "valid": not errors,
        "witness_id": witness.get("witness_id", ""),
        "solver_outcome": witness.get("solver_outcome", ""),
        "authority_decision": witness.get("authority_decision", ""),
        "authority_denial_count": len(AUTHORITY_DENIAL_FIELDS),
        "authority_requirement_count": len(witness.get("authority_requirements", []))
        if isinstance(witness.get("authority_requirements"), list)
        else 0,
        "append_precondition_count": len(witness.get("append_preconditions", []))
        if isinstance(witness.get("append_preconditions"), list)
        else 0,
        "evidence_ref_count": len(witness.get("evidence_refs", []))
        if isinstance(witness.get("evidence_refs"), list)
        else 0,
        "errors": errors,
    }
    if errors:
        raise UniversalSymbolReceiptStoreAuthorityWitnessError("; ".join(errors))
    return result


def _validate_schema_boundary(schema: Mapping[str, Any], errors: list[str]) -> None:
    if schema.get("$id") != "urn:mullusi:schema:universal-symbol-receipt-store-authority-witness:1":
        errors.append("schema id drift")
    if schema.get("additionalProperties") is not False:
        errors.append("schema must reject additional properties")
    required = schema.get("required")
    if not isinstance(required, list) or "authority_denials" not in required:
        errors.append("schema must require authority_denials")


def _validate_json_schema(witness: Mapping[str, Any], schema: Mapping[str, Any], errors: list[str]) -> None:
    if jsonschema is None:
        errors.append("jsonschema dependency missing")
        return
    validator = jsonschema.Draft202012Validator(schema, format_checker=jsonschema.FormatChecker())
    schema_errors = sorted(validator.iter_errors(witness), key=lambda error: tuple(error.path))
    for error in schema_errors:
        path = ".".join(str(part) for part in error.absolute_path) or "$"
        errors.append(f"schema validation failed at {path}: {error.message}")


def _validate_witness_boundary(witness: Mapping[str, Any], errors: list[str]) -> None:
    if witness.get("foundation_mode") is not True:
        errors.append("foundation_mode must remain true")
    if witness.get("solver_outcome") != "AwaitingEvidence":
        errors.append("solver_outcome must remain AwaitingEvidence")
    if witness.get("authority_decision") != "blocked_pending_append_audit_and_store_authority":
        errors.append("authority_decision must remain blocked")
    if witness.get("authority_is_granted") is not False:
        errors.append("authority_is_granted must remain false")


def _validate_authority_requirements(witness: Mapping[str, Any], errors: list[str]) -> None:
    requirements = witness.get("authority_requirements")
    if not isinstance(requirements, list) or not requirements:
        errors.append("authority_requirements must be non-empty")
        return
    requirement_ids: list[str] = []
    for requirement in requirements:
        if not isinstance(requirement, dict):
            errors.append("authority requirement entries must be objects")
            continue
        requirement_ids.append(str(requirement.get("requirement_id")))
        if requirement.get("proof_state") not in {"Unknown", "BudgetUnknown", "Fail"}:
            errors.append(f"{requirement.get('requirement_id')}: proof_state must block authority")
        if requirement.get("current_decision") != "authority_blocked":
            errors.append(f"{requirement.get('requirement_id')}: current_decision must be authority_blocked")
    _require_members("authority_requirements", requirement_ids, REQUIRED_REQUIREMENT_IDS, errors)


def _validate_authority_denials(witness: Mapping[str, Any], errors: list[str]) -> None:
    denials = _mapping(witness.get("authority_denials"))
    for field_name in AUTHORITY_DENIAL_FIELDS:
        if denials.get(field_name) is not False:
            errors.append(f"authority_denials.{field_name} must remain false")


def _validate_append_preconditions(witness: Mapping[str, Any], errors: list[str]) -> None:
    preconditions = witness.get("append_preconditions")
    if not isinstance(preconditions, list) or not preconditions:
        errors.append("append_preconditions must be non-empty")
        return
    precondition_ids: list[str] = []
    for precondition in preconditions:
        if not isinstance(precondition, dict):
            errors.append("append precondition entries must be objects")
            continue
        precondition_ids.append(str(precondition.get("precondition_id")))
        if precondition.get("proof_state") not in {"Unknown", "BudgetUnknown", "Fail"}:
            errors.append(f"{precondition.get('precondition_id')}: proof_state must block append")
        if precondition.get("append_decision") != "block_append":
            errors.append(f"{precondition.get('precondition_id')}: append_decision must be block_append")
        if not str(precondition.get("delta_reject_ref", "")).startswith("delta-reject://"):
            errors.append(f"{precondition.get('precondition_id')}: delta_reject_ref must be logged")
    _require_members("append_preconditions", precondition_ids, REQUIRED_PRECONDITION_IDS, errors)


def _validate_rejection_policy(witness: Mapping[str, Any], errors: list[str]) -> None:
    rejection_policy = _mapping(witness.get("rejection_policy"))
    for field_name in REJECTION_POLICY_TRUE_FIELDS:
        if rejection_policy.get(field_name) is not True:
            errors.append(f"rejection_policy.{field_name} must remain true")


def _validate_blocked_reasons(witness: Mapping[str, Any], errors: list[str]) -> None:
    blocked_reasons = witness.get("blocked_reasons")
    if not isinstance(blocked_reasons, list):
        errors.append("blocked_reasons must be a list")
        return
    _require_members("blocked_reasons", [item for item in blocked_reasons if isinstance(item, str)], REQUIRED_BLOCKED_REASONS, errors)


def _validate_contract_summary(witness: Mapping[str, Any], errors: list[str]) -> None:
    summary = _mapping(witness.get("contract_summary"))
    observed_counts = {
        "authority_requirement_count": _list_len(witness.get("authority_requirements")),
        "authority_denial_count": len(AUTHORITY_DENIAL_FIELDS),
        "append_precondition_count": _list_len(witness.get("append_preconditions")),
        "rejection_check_count": len(REJECTION_POLICY_TRUE_FIELDS),
        "blocked_reason_count": _list_len(witness.get("blocked_reasons")),
        "evidence_ref_count": _list_len(witness.get("evidence_refs")),
    }
    for field_name, observed_count in observed_counts.items():
        if observed_count is not None and summary.get(field_name) != observed_count:
            errors.append(f"{field_name} drift")


def _validate_evidence_refs(witness: Mapping[str, Any], errors: list[str]) -> None:
    refs = witness.get("evidence_refs")
    if not isinstance(refs, list):
        errors.append("evidence_refs must be a list")
        return
    missing = tuple(ref for ref in REQUIRED_EVIDENCE_REFS if ref not in refs)
    if missing:
        errors.append("missing required evidence refs: " + ", ".join(missing))


def _validate_evidence_ref_files(witness: Mapping[str, Any], errors: list[str]) -> None:
    refs = witness.get("evidence_refs")
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
    parser.add_argument("--witness", type=Path, default=DEFAULT_WITNESS_PATH)
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA_PATH)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    try:
        report = validate_universal_symbol_receipt_store_authority_witness(args.witness, args.schema)
    except UniversalSymbolReceiptStoreAuthorityWitnessError as exc:
        if args.json:
            print(json.dumps({"valid": False, "errors": str(exc).split("; ")}, indent=2, sort_keys=True))
        else:
            print(f"[FAIL] universal_symbol_receipt_store_authority_witness: {exc}")
            print("STATUS: failed")
        return 1

    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print("[PASS] universal_symbol_receipt_store_authority_witness")
        print("STATUS: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
