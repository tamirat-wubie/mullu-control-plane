"""Validate the Universal Symbol receipt-store reapproval revocation witness.

Purpose: prove UniversalSymbol receipt-store lifecycle changes remain blocked
until approval decision, active grant, reapproval window, expiry, revocation,
replacement decision, and lifecycle audit evidence exist.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: reapproval revocation schema/example, operator approval decision
witness, operator identity witness, operator approval witness, docs, proof
coverage matrix, and tests.
Invariants:
  - The witness is not lifecycle authority.
  - Reapproval recording, revocation recording, approval decision recording,
    approval recording, write-path registration, receipt append, replacement
    decision recording, raw payload storage, raw secret storage, runtime
    dispatch, connector calls, mutation, and terminal closure remain denied.
  - Unknown hard lifecycle preconditions block lifecycle change and log
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
    REPO_ROOT / "schemas" / "universal_symbol_receipt_store_reapproval_revocation_witness.schema.json"
)
DEFAULT_WITNESS_PATH = (
    REPO_ROOT / "examples" / "universal_symbol_receipt_store_reapproval_revocation_witness.foundation.json"
)

AUTHORITY_DENIAL_FIELDS: tuple[str, ...] = (
    "receipt_store_reapproval_recorded",
    "receipt_store_revocation_recorded",
    "receipt_store_approval_decision_recorded",
    "receipt_store_operator_approval_recorded",
    "receipt_store_write_path_registered",
    "receipt_store_append_performed",
    "replacement_decision_recorded",
    "raw_payload_stored",
    "raw_secret_stored",
    "runtime_dispatch_performed",
    "connector_call_performed",
    "state_mutation_performed",
    "terminal_closure_allowed",
)

REQUIRED_REQUIREMENT_IDS: tuple[str, ...] = (
    "requirement://approval-decision-witness",
    "requirement://active-grant-identity",
    "requirement://reapproval-window",
    "requirement://expiry-evidence",
    "requirement://revocation-request",
    "requirement://revocation-effect-boundary",
    "requirement://replacement-decision-path",
    "requirement://lifecycle-audit-receipt",
)

LIFECYCLE_CONSTRAINT_TRUE_FIELDS: tuple[str, ...] = (
    "approval_decision_witness_required",
    "active_grant_identity_required",
    "reapproval_window_required",
    "expiry_evidence_required",
    "revocation_request_required",
    "revocation_effect_boundary_required",
    "replacement_decision_path_required",
    "lifecycle_audit_receipt_required",
)

REJECTION_POLICY_TRUE_FIELDS: tuple[str, ...] = (
    "missing_approval_decision_blocks_lifecycle_change",
    "missing_active_grant_blocks_lifecycle_change",
    "missing_reapproval_window_blocks_lifecycle_change",
    "missing_revocation_boundary_blocks_lifecycle_change",
    "unknown_hard_constraint_blocks_lifecycle_change",
    "failed_precondition_logs_delta_reject",
)

REQUIRED_BLOCKED_REASONS: tuple[str, ...] = (
    "approval_decision_witness_missing",
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
    "schemas/universal_symbol_receipt_store_reapproval_revocation_witness.schema.json",
    "examples/universal_symbol_receipt_store_reapproval_revocation_witness.foundation.json",
    "schemas/universal_symbol_receipt_store_operator_approval_decision_witness.schema.json",
    "examples/universal_symbol_receipt_store_operator_approval_decision_witness.foundation.json",
    "schemas/universal_symbol_receipt_store_operator_identity_witness.schema.json",
    "examples/universal_symbol_receipt_store_operator_identity_witness.foundation.json",
    "schemas/universal_symbol_receipt_store_operator_approval_witness.schema.json",
    "examples/universal_symbol_receipt_store_operator_approval_witness.foundation.json",
    "schemas/universal_symbol.schema.json",
    "docs/91_universal_symbol_kernel.md",
    "docs/92_universal_symbol_kernel_audit.md",
    "scripts/validate_universal_symbol_receipt_store_reapproval_revocation_witness.py",
    "scripts/validate_universal_symbol_receipt_store_operator_approval_decision_witness.py",
    "tests/test_validate_universal_symbol_kernel.py",
    "scripts/proof_coverage_matrix.py",
    "tests/test_proof_coverage_matrix.py",
)


class UniversalSymbolReceiptStoreReapprovalRevocationWitnessError(ValueError):
    """Raised when the reapproval revocation witness violates Foundation Mode."""


def load_json_object(path: Path) -> dict[str, Any]:
    """Return a JSON object or raise a validation error with causal context."""

    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise UniversalSymbolReceiptStoreReapprovalRevocationWitnessError(f"missing file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise UniversalSymbolReceiptStoreReapprovalRevocationWitnessError(f"invalid json: {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise UniversalSymbolReceiptStoreReapprovalRevocationWitnessError(f"expected object: {path}")
    return value


def validate_universal_symbol_receipt_store_reapproval_revocation_witness(
    witness_path: Path = DEFAULT_WITNESS_PATH,
    schema_path: Path = DEFAULT_SCHEMA_PATH,
) -> dict[str, Any]:
    """Validate schema shape, denied lifecycle authority, and evidence refs."""

    schema = load_json_object(schema_path)
    witness = load_json_object(witness_path)
    errors: list[str] = []

    _validate_schema_boundary(schema, errors)
    _validate_json_schema(witness, schema, errors)
    _validate_witness_boundary(witness, errors)
    _validate_lifecycle_requirements(witness, errors)
    _validate_authority_denials(witness, errors)
    _validate_lifecycle_constraints(witness, errors)
    _validate_rejection_policy(witness, errors)
    _validate_blocked_reasons(witness, errors)
    _validate_contract_summary(witness, errors)
    _validate_evidence_refs(witness, errors)
    _validate_evidence_ref_files(witness, errors)

    report = {
        "witness_path": _repo_relative(witness_path),
        "schema_path": _repo_relative(schema_path),
        "valid": not errors,
        "witness_id": witness.get("witness_id", ""),
        "solver_outcome": witness.get("solver_outcome", ""),
        "reapproval_revocation_decision": witness.get("reapproval_revocation_decision", ""),
        "authority_denial_count": len(AUTHORITY_DENIAL_FIELDS),
        "lifecycle_requirement_count": len(witness.get("lifecycle_requirements", []))
        if isinstance(witness.get("lifecycle_requirements"), list)
        else 0,
        "evidence_ref_count": len(witness.get("evidence_refs", []))
        if isinstance(witness.get("evidence_refs"), list)
        else 0,
        "errors": errors,
    }
    if errors:
        raise UniversalSymbolReceiptStoreReapprovalRevocationWitnessError("; ".join(errors))
    return report


def _validate_schema_boundary(schema: Mapping[str, Any], errors: list[str]) -> None:
    if schema.get("$id") != "urn:mullusi:schema:universal-symbol-receipt-store-reapproval-revocation-witness:1":
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
    if (
        witness.get("reapproval_revocation_decision")
        != "blocked_pending_approval_decision_grant_expiry_revocation_replacement_and_audit_evidence"
    ):
        errors.append("reapproval_revocation_decision must remain blocked")
    if witness.get("reapproval_revocation_witness_is_not_lifecycle_authority") is not True:
        errors.append("reapproval revocation witness must not grant lifecycle authority")


def _validate_lifecycle_requirements(witness: Mapping[str, Any], errors: list[str]) -> None:
    requirements = witness.get("lifecycle_requirements")
    if not isinstance(requirements, list) or not requirements:
        errors.append("lifecycle_requirements must be non-empty")
        return
    requirement_ids: list[str] = []
    for requirement in requirements:
        if not isinstance(requirement, dict):
            errors.append("lifecycle requirement entries must be objects")
            continue
        requirement_ids.append(str(requirement.get("requirement_id")))
        if requirement.get("proof_state") not in {"Unknown", "BudgetUnknown", "Fail"}:
            errors.append(f"{requirement.get('requirement_id')}: proof_state must block lifecycle change")
        if requirement.get("current_decision") != "lifecycle_change_blocked":
            errors.append(f"{requirement.get('requirement_id')}: current_decision must be lifecycle_change_blocked")
        if not str(requirement.get("delta_reject_ref", "")).startswith("delta-reject://"):
            errors.append(f"{requirement.get('requirement_id')}: delta_reject_ref must be logged")
    _require_members("lifecycle_requirements", requirement_ids, REQUIRED_REQUIREMENT_IDS, errors)


def _validate_authority_denials(witness: Mapping[str, Any], errors: list[str]) -> None:
    denials = _mapping(witness.get("authority_denials"))
    for field_name in AUTHORITY_DENIAL_FIELDS:
        if denials.get(field_name) is not False:
            errors.append(f"authority_denials.{field_name} must remain false")


def _validate_lifecycle_constraints(witness: Mapping[str, Any], errors: list[str]) -> None:
    constraints = _mapping(witness.get("lifecycle_constraints"))
    for field_name in LIFECYCLE_CONSTRAINT_TRUE_FIELDS:
        if constraints.get(field_name) is not True:
            errors.append(f"lifecycle_constraints.{field_name} must remain true")


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
        "lifecycle_requirement_count": _list_len(witness.get("lifecycle_requirements")),
        "authority_denial_count": len(AUTHORITY_DENIAL_FIELDS),
        "lifecycle_constraint_count": len(LIFECYCLE_CONSTRAINT_TRUE_FIELDS),
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
        report = validate_universal_symbol_receipt_store_reapproval_revocation_witness(
            args.witness,
            args.schema,
        )
    except UniversalSymbolReceiptStoreReapprovalRevocationWitnessError as exc:
        if args.json:
            print(json.dumps({"valid": False, "errors": str(exc).split("; ")}, indent=2, sort_keys=True))
        else:
            print(f"[FAIL] universal_symbol_receipt_store_reapproval_revocation_witness: {exc}")
            print("STATUS: failed")
        return 1

    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print("[PASS] universal_symbol_receipt_store_reapproval_revocation_witness")
        print("STATUS: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
