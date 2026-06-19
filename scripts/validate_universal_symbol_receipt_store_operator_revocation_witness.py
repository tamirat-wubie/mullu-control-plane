"""Validate the Universal Symbol receipt-store operator revocation witness.

Purpose: prove UniversalSymbol receipt-store revocation binding remains blocked
until operator identity, approval decision, revocation state, revocation scope,
reason, effective time, propagation, and audit evidence exist.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: revocation schema/example, approval decision witness, operator
identity witness, docs, proof matrix, and tests.
Invariants: revocation authority, approval recording, receipt append, runtime
dispatch, mutation, and terminal closure remain denied.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping

try:
    import jsonschema
except ImportError:  # pragma: no cover
    jsonschema = None


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SCHEMA_PATH = REPO_ROOT / "schemas" / "universal_symbol_receipt_store_operator_revocation_witness.schema.json"
DEFAULT_WITNESS_PATH = (
    REPO_ROOT / "examples" / "universal_symbol_receipt_store_operator_revocation_witness.foundation.json"
)

AUTHORITY_DENIAL_FIELDS: tuple[str, ...] = (
    "receipt_store_revocation_bound",
    "receipt_store_approval_decision_recorded",
    "receipt_store_operator_approval_recorded",
    "receipt_store_writer_identity_registered",
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

REQUIRED_REQUIREMENT_IDS: tuple[str, ...] = (
    "requirement://operator-identity-witness",
    "requirement://approval-decision-ref",
    "requirement://revocation-state",
    "requirement://revocation-scope",
    "requirement://revocation-reason",
    "requirement://effective-at",
    "requirement://propagation-receipt",
    "requirement://audit-receipt",
)

TRUE_CONSTRAINT_FIELDS: tuple[str, ...] = (
    "operator_identity_witness_required",
    "approval_decision_ref_required",
    "revocation_state_required",
    "revocation_scope_required",
    "revocation_reason_required",
    "effective_at_required",
    "propagation_receipt_required",
    "audit_receipt_required",
)

TRUE_REJECTION_FIELDS: tuple[str, ...] = (
    "missing_operator_identity_blocks_revocation",
    "missing_approval_decision_blocks_revocation",
    "missing_revocation_state_blocks_revocation",
    "missing_revocation_scope_blocks_revocation",
    "unknown_hard_constraint_blocks_revocation",
    "failed_precondition_logs_delta_reject",
)

REQUIRED_BLOCKED_REASONS: tuple[str, ...] = (
    "operator_identity_witness_missing",
    "approval_decision_ref_missing",
    "revocation_state_missing",
    "revocation_scope_missing",
    "revocation_reason_missing",
    "effective_at_missing",
    "propagation_receipt_missing",
    "audit_receipt_missing",
    "receipt_store_revocation_binding_forbidden",
    "terminal_closure_not_allowed",
)

REQUIRED_EVIDENCE_REFS: tuple[str, ...] = (
    "schemas/universal_symbol_receipt_store_operator_revocation_witness.schema.json",
    "examples/universal_symbol_receipt_store_operator_revocation_witness.foundation.json",
    "schemas/universal_symbol_receipt_store_operator_approval_decision_witness.schema.json",
    "examples/universal_symbol_receipt_store_operator_approval_decision_witness.foundation.json",
    "schemas/universal_symbol_receipt_store_operator_identity_witness.schema.json",
    "examples/universal_symbol_receipt_store_operator_identity_witness.foundation.json",
    "schemas/universal_symbol.schema.json",
    "docs/91_universal_symbol_kernel.md",
    "docs/92_universal_symbol_kernel_audit.md",
    "scripts/validate_universal_symbol_receipt_store_operator_revocation_witness.py",
    "tests/test_validate_universal_symbol_kernel.py",
    "scripts/proof_coverage_matrix.py",
    "tests/test_proof_coverage_matrix.py",
)


class UniversalSymbolReceiptStoreOperatorRevocationWitnessError(ValueError):
    """Raised when the revocation witness violates Foundation Mode."""


def load_json_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise UniversalSymbolReceiptStoreOperatorRevocationWitnessError(f"missing file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise UniversalSymbolReceiptStoreOperatorRevocationWitnessError(f"invalid json: {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise UniversalSymbolReceiptStoreOperatorRevocationWitnessError(f"expected object: {path}")
    return value


def validate_universal_symbol_receipt_store_operator_revocation_witness(
    witness_path: Path = DEFAULT_WITNESS_PATH,
    schema_path: Path = DEFAULT_SCHEMA_PATH,
) -> dict[str, Any]:
    schema = load_json_object(schema_path)
    witness = load_json_object(witness_path)
    errors: list[str] = []

    _validate_schema_boundary(schema, errors)
    _validate_json_schema(witness, schema, errors)
    _validate_witness_boundary(witness, errors)
    _validate_requirements(witness, errors)
    _validate_false_fields("authority_denials", witness.get("authority_denials"), AUTHORITY_DENIAL_FIELDS, errors)
    _validate_true_fields("revocation_constraints", witness.get("revocation_constraints"), TRUE_CONSTRAINT_FIELDS, errors)
    _validate_true_fields("rejection_policy", witness.get("rejection_policy"), TRUE_REJECTION_FIELDS, errors)
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
        "revocation_decision": witness.get("revocation_decision", ""),
        "authority_denial_count": len(AUTHORITY_DENIAL_FIELDS),
        "revocation_requirement_count": _list_len(witness.get("revocation_requirements")) or 0,
        "evidence_ref_count": _list_len(witness.get("evidence_refs")) or 0,
        "errors": errors,
    }
    if errors:
        raise UniversalSymbolReceiptStoreOperatorRevocationWitnessError("; ".join(errors))
    return report


def _validate_schema_boundary(schema: Mapping[str, Any], errors: list[str]) -> None:
    if schema.get("$id") != "urn:mullusi:schema:universal-symbol-receipt-store-operator-revocation-witness:1":
        errors.append("schema id drift")
    if schema.get("additionalProperties") is not False:
        errors.append("schema must reject additional properties")
    if "authority_denials" not in (schema.get("required") if isinstance(schema.get("required"), list) else []):
        errors.append("schema must require authority_denials")


def _validate_json_schema(witness: Mapping[str, Any], schema: Mapping[str, Any], errors: list[str]) -> None:
    if jsonschema is None:
        errors.append("jsonschema dependency missing")
        return
    validator = jsonschema.Draft202012Validator(schema, format_checker=jsonschema.FormatChecker())
    for error in sorted(validator.iter_errors(witness), key=lambda item: tuple(item.path)):
        path = ".".join(str(part) for part in error.absolute_path) or "$"
        errors.append(f"schema validation failed at {path}: {error.message}")


def _validate_witness_boundary(witness: Mapping[str, Any], errors: list[str]) -> None:
    if witness.get("foundation_mode") is not True:
        errors.append("foundation_mode must remain true")
    if witness.get("solver_outcome") != "AwaitingEvidence":
        errors.append("solver_outcome must remain AwaitingEvidence")
    if witness.get("revocation_decision") != "blocked_pending_live_revocation_state_scope_and_audit_evidence":
        errors.append("revocation_decision must remain blocked")
    if witness.get("revocation_witness_is_not_revocation_authority") is not True:
        errors.append("revocation witness must not grant revocation authority")


def _validate_requirements(witness: Mapping[str, Any], errors: list[str]) -> None:
    requirements = witness.get("revocation_requirements")
    if not isinstance(requirements, list) or not requirements:
        errors.append("revocation_requirements must be non-empty")
        return
    requirement_ids: list[str] = []
    for requirement in requirements:
        if not isinstance(requirement, dict):
            errors.append("revocation requirement entries must be objects")
            continue
        requirement_ids.append(str(requirement.get("requirement_id")))
        if requirement.get("proof_state") not in {"Unknown", "BudgetUnknown", "Fail"}:
            errors.append(f"{requirement.get('requirement_id')}: proof_state must block revocation")
        if requirement.get("current_decision") != "revocation_blocked":
            errors.append(f"{requirement.get('requirement_id')}: current_decision must be revocation_blocked")
        if not str(requirement.get("delta_reject_ref", "")).startswith("delta-reject://"):
            errors.append(f"{requirement.get('requirement_id')}: delta_reject_ref must be logged")
    _require_members("revocation_requirements", requirement_ids, REQUIRED_REQUIREMENT_IDS, errors)


def _validate_false_fields(section_name: str, value: Any, fields: tuple[str, ...], errors: list[str]) -> None:
    section = _mapping(value)
    for field in fields:
        if section.get(field) is not False:
            errors.append(f"{section_name}.{field} must remain false")


def _validate_true_fields(section_name: str, value: Any, fields: tuple[str, ...], errors: list[str]) -> None:
    section = _mapping(value)
    for field in fields:
        if section.get(field) is not True:
            errors.append(f"{section_name}.{field} must remain true")


def _validate_blocked_reasons(witness: Mapping[str, Any], errors: list[str]) -> None:
    blocked_reasons = witness.get("blocked_reasons")
    if not isinstance(blocked_reasons, list):
        errors.append("blocked_reasons must be a list")
        return
    _require_members("blocked_reasons", [item for item in blocked_reasons if isinstance(item, str)], REQUIRED_BLOCKED_REASONS, errors)


def _validate_contract_summary(witness: Mapping[str, Any], errors: list[str]) -> None:
    summary = _mapping(witness.get("contract_summary"))
    observed = {
        "revocation_requirement_count": _list_len(witness.get("revocation_requirements")),
        "authority_denial_count": len(AUTHORITY_DENIAL_FIELDS),
        "revocation_constraint_count": len(TRUE_CONSTRAINT_FIELDS),
        "rejection_check_count": len(TRUE_REJECTION_FIELDS),
        "blocked_reason_count": _list_len(witness.get("blocked_reasons")),
        "evidence_ref_count": _list_len(witness.get("evidence_refs")),
    }
    for field, count in observed.items():
        if count is not None and summary.get(field) != count:
            errors.append(f"{field} drift")


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
        resolved = (REPO_ROOT / Path(ref)).resolve()
        if REPO_ROOT.resolve() not in resolved.parents and resolved != REPO_ROOT.resolve():
            errors.append(f"evidence ref escapes repository: {ref}")
        elif not resolved.exists():
            errors.append(f"evidence ref file missing: {ref}")


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _list_len(value: Any) -> int | None:
    return len(value) if isinstance(value, list) else None


def _require_members(field: str, observed: list[str], required: tuple[str, ...], errors: list[str]) -> None:
    for missing in sorted(set(required) - set(observed)):
        errors.append(f"{field} missing required value: {missing}")
    if len(observed) != len(set(observed)):
        errors.append(f"{field} values must be unique")


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
        report = validate_universal_symbol_receipt_store_operator_revocation_witness(args.witness, args.schema)
    except UniversalSymbolReceiptStoreOperatorRevocationWitnessError as exc:
        if args.json:
            print(json.dumps({"valid": False, "errors": str(exc).split("; ")}, indent=2, sort_keys=True))
        else:
            print(f"[FAIL] universal_symbol_receipt_store_operator_revocation_witness: {exc}")
            print("STATUS: failed")
        return 1
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print("[PASS] universal_symbol_receipt_store_operator_revocation_witness")
        print("STATUS: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
