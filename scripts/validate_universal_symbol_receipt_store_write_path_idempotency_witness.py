"""Validate the Universal Symbol receipt-store write-path idempotency witness.

Purpose: prove UniversalSymbol receipt-store write-path idempotency remains
blocked until deterministic key derivation, canonical input, tenant/actor
binding, write-path binding, payload digest binding, replay collision checks,
duplicate-effect denial, and audit receipt evidence exist.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: write-path idempotency schema/example, write-path witness, path
custody witness, path confinement witness, writer registration witness, append
audit witness, receipt-store authority witness, docs, and tests.
Invariants:
  - The witness is not append authority.
  - Idempotency binding, write-path registration, path custody registration,
    receipt append, duplicate append, raw payload storage, raw secret storage,
    runtime dispatch, connector calls, mutation, and terminal closure remain
    denied.
  - Unknown hard preconditions block idempotency and log Delta_reject refs.
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
    REPO_ROOT / "schemas" / "universal_symbol_receipt_store_write_path_idempotency_witness.schema.json"
)
DEFAULT_WITNESS_PATH = (
    REPO_ROOT / "examples" / "universal_symbol_receipt_store_write_path_idempotency_witness.foundation.json"
)

AUTHORITY_DENIAL_FIELDS: tuple[str, ...] = (
    "receipt_store_write_path_idempotency_bound",
    "receipt_store_write_path_registered",
    "receipt_store_path_custody_registered",
    "receipt_store_append_performed",
    "duplicate_append_allowed",
    "raw_payload_stored",
    "raw_secret_stored",
    "runtime_dispatch_performed",
    "connector_call_performed",
    "state_mutation_performed",
    "terminal_closure_allowed",
)

REQUIRED_REQUIREMENT_IDS: tuple[str, ...] = (
    "requirement://deterministic-key-derivation",
    "requirement://canonical-input",
    "requirement://tenant-actor-binding",
    "requirement://write-path-binding",
    "requirement://payload-digest-binding",
    "requirement://replay-collision-check",
    "requirement://duplicate-effect-denial",
    "requirement://audit-receipt",
)

IDEMPOTENCY_CONSTRAINT_TRUE_FIELDS: tuple[str, ...] = (
    "deterministic_key_derivation_required",
    "canonical_input_required",
    "tenant_actor_binding_required",
    "write_path_binding_required",
    "payload_digest_binding_required",
    "replay_collision_check_required",
    "duplicate_effect_denial_required",
    "audit_receipt_required",
)

REJECTION_POLICY_TRUE_FIELDS: tuple[str, ...] = (
    "missing_key_derivation_blocks_idempotency",
    "missing_canonical_input_blocks_idempotency",
    "missing_digest_binding_blocks_idempotency",
    "missing_replay_collision_check_blocks_idempotency",
    "unknown_hard_constraint_blocks_idempotency",
    "failed_precondition_logs_delta_reject",
)

REQUIRED_BLOCKED_REASONS: tuple[str, ...] = (
    "deterministic_key_derivation_missing",
    "canonical_input_missing",
    "tenant_actor_binding_missing",
    "write_path_binding_missing",
    "payload_digest_binding_missing",
    "replay_collision_check_missing",
    "duplicate_effect_denial_missing",
    "audit_receipt_missing",
    "receipt_store_write_path_idempotency_forbidden",
    "terminal_closure_not_allowed",
)

REQUIRED_EVIDENCE_REFS: tuple[str, ...] = (
    "schemas/universal_symbol_receipt_store_write_path_idempotency_witness.schema.json",
    "examples/universal_symbol_receipt_store_write_path_idempotency_witness.foundation.json",
    "schemas/universal_symbol_receipt_store_write_path_witness.schema.json",
    "examples/universal_symbol_receipt_store_write_path_witness.foundation.json",
    "schemas/universal_symbol_receipt_store_path_custody_witness.schema.json",
    "examples/universal_symbol_receipt_store_path_custody_witness.foundation.json",
    "schemas/universal_symbol_receipt_store_path_confinement_witness.schema.json",
    "examples/universal_symbol_receipt_store_path_confinement_witness.foundation.json",
    "schemas/universal_symbol_receipt_store_writer_registration_witness.schema.json",
    "examples/universal_symbol_receipt_store_writer_registration_witness.foundation.json",
    "schemas/universal_symbol_append_audit_witness.schema.json",
    "examples/universal_symbol_append_audit_witness.foundation.json",
    "schemas/universal_symbol_receipt_store_authority_witness.schema.json",
    "examples/universal_symbol_receipt_store_authority_witness.foundation.json",
    "schemas/universal_symbol_adapter_receipt_persistence_policy.schema.json",
    "schemas/universal_symbol_runtime_admission_policy.schema.json",
    "schemas/universal_symbol.schema.json",
    "docs/91_universal_symbol_kernel.md",
    "docs/92_universal_symbol_kernel_audit.md",
    "scripts/validate_universal_symbol_receipt_store_write_path_idempotency_witness.py",
    "tests/test_validate_universal_symbol_kernel.py",
    "scripts/proof_coverage_matrix.py",
    "tests/test_proof_coverage_matrix.py",
)


class UniversalSymbolReceiptStoreWritePathIdempotencyWitnessError(ValueError):
    """Raised when the write-path idempotency witness violates Foundation Mode."""


def load_json_object(path: Path) -> dict[str, Any]:
    """Return a JSON object or raise a validation error with causal context."""

    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise UniversalSymbolReceiptStoreWritePathIdempotencyWitnessError(f"missing file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise UniversalSymbolReceiptStoreWritePathIdempotencyWitnessError(f"invalid json: {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise UniversalSymbolReceiptStoreWritePathIdempotencyWitnessError(f"expected object: {path}")
    return value


def validate_universal_symbol_receipt_store_write_path_idempotency_witness(
    witness_path: Path = DEFAULT_WITNESS_PATH,
    schema_path: Path = DEFAULT_SCHEMA_PATH,
) -> dict[str, Any]:
    """Validate schema shape, denied append authority, and evidence refs."""

    schema = load_json_object(schema_path)
    witness = load_json_object(witness_path)
    errors: list[str] = []

    _validate_schema_boundary(schema, errors)
    _validate_json_schema(witness, schema, errors)
    _validate_witness_boundary(witness, errors)
    _validate_idempotency_requirements(witness, errors)
    _validate_authority_denials(witness, errors)
    _validate_idempotency_constraints(witness, errors)
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
        "idempotency_decision": witness.get("idempotency_decision", ""),
        "authority_denial_count": len(AUTHORITY_DENIAL_FIELDS),
        "idempotency_requirement_count": len(witness.get("idempotency_requirements", []))
        if isinstance(witness.get("idempotency_requirements"), list)
        else 0,
        "evidence_ref_count": len(witness.get("evidence_refs", []))
        if isinstance(witness.get("evidence_refs"), list)
        else 0,
        "errors": errors,
    }
    if errors:
        raise UniversalSymbolReceiptStoreWritePathIdempotencyWitnessError("; ".join(errors))
    return report


def _validate_schema_boundary(schema: Mapping[str, Any], errors: list[str]) -> None:
    if schema.get("$id") != "urn:mullusi:schema:universal-symbol-receipt-store-write-path-idempotency-witness:1":
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
        witness.get("idempotency_decision")
        != "blocked_pending_key_derivation_digest_replay_and_collision_evidence"
    ):
        errors.append("idempotency_decision must remain blocked")
    if witness.get("idempotency_witness_is_not_append_authority") is not True:
        errors.append("idempotency witness must not grant append authority")


def _validate_idempotency_requirements(witness: Mapping[str, Any], errors: list[str]) -> None:
    requirements = witness.get("idempotency_requirements")
    if not isinstance(requirements, list) or not requirements:
        errors.append("idempotency_requirements must be non-empty")
        return
    requirement_ids: list[str] = []
    for requirement in requirements:
        if not isinstance(requirement, dict):
            errors.append("idempotency requirement entries must be objects")
            continue
        requirement_ids.append(str(requirement.get("requirement_id")))
        if requirement.get("proof_state") not in {"Unknown", "BudgetUnknown", "Fail"}:
            errors.append(f"{requirement.get('requirement_id')}: proof_state must block idempotency")
        if requirement.get("current_decision") != "idempotency_blocked":
            errors.append(f"{requirement.get('requirement_id')}: current_decision must be idempotency_blocked")
        if not str(requirement.get("delta_reject_ref", "")).startswith("delta-reject://"):
            errors.append(f"{requirement.get('requirement_id')}: delta_reject_ref must be logged")
    _require_members("idempotency_requirements", requirement_ids, REQUIRED_REQUIREMENT_IDS, errors)


def _validate_authority_denials(witness: Mapping[str, Any], errors: list[str]) -> None:
    denials = _mapping(witness.get("authority_denials"))
    for field_name in AUTHORITY_DENIAL_FIELDS:
        if denials.get(field_name) is not False:
            errors.append(f"authority_denials.{field_name} must remain false")


def _validate_idempotency_constraints(witness: Mapping[str, Any], errors: list[str]) -> None:
    constraints = _mapping(witness.get("idempotency_constraints"))
    for field_name in IDEMPOTENCY_CONSTRAINT_TRUE_FIELDS:
        if constraints.get(field_name) is not True:
            errors.append(f"idempotency_constraints.{field_name} must remain true")


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
    _require_members("blocked_reasons", [str(reason) for reason in blocked_reasons], REQUIRED_BLOCKED_REASONS, errors)


def _validate_contract_summary(witness: Mapping[str, Any], errors: list[str]) -> None:
    summary = _mapping(witness.get("contract_summary"))
    expected_values = {
        "idempotency_requirement_count": _list_len(witness.get("idempotency_requirements")),
        "authority_denial_count": len(AUTHORITY_DENIAL_FIELDS),
        "idempotency_constraint_count": len(IDEMPOTENCY_CONSTRAINT_TRUE_FIELDS),
        "rejection_check_count": len(REJECTION_POLICY_TRUE_FIELDS),
        "blocked_reason_count": _list_len(witness.get("blocked_reasons")),
        "evidence_ref_count": _list_len(witness.get("evidence_refs")),
    }
    for field_name, expected_value in expected_values.items():
        if summary.get(field_name) != expected_value:
            errors.append(f"contract_summary.{field_name} drift: expected {expected_value}")


def _validate_evidence_refs(witness: Mapping[str, Any], errors: list[str]) -> None:
    evidence_refs = witness.get("evidence_refs")
    if not isinstance(evidence_refs, list):
        errors.append("evidence_refs must be a list")
        return
    _require_members("evidence_refs", [str(ref) for ref in evidence_refs], REQUIRED_EVIDENCE_REFS, errors)


def _validate_evidence_ref_files(witness: Mapping[str, Any], errors: list[str]) -> None:
    evidence_refs = witness.get("evidence_refs")
    if not isinstance(evidence_refs, list):
        return
    for evidence_ref in evidence_refs:
        if not isinstance(evidence_ref, str):
            errors.append("evidence_refs entries must be strings")
            continue
        if evidence_ref.startswith(("schemas/", "examples/", "docs/", "scripts/", "tests/")):
            if not (REPO_ROOT / evidence_ref).exists():
                errors.append(f"evidence ref missing on disk: {evidence_ref}")


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, dict) else {}


def _list_len(value: Any) -> int:
    return len(value) if isinstance(value, list) else 0


def _require_members(label: str, actual_values: list[str], expected_values: tuple[str, ...], errors: list[str]) -> None:
    actual = set(actual_values)
    for expected_value in expected_values:
        if expected_value not in actual:
            errors.append(f"{label} missing {expected_value}")


def _repo_relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate the UniversalSymbol receipt-store write-path idempotency witness."
    )
    parser.add_argument("--witness", type=Path, default=DEFAULT_WITNESS_PATH)
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA_PATH)
    parser.add_argument("--json", action="store_true", help="Emit a machine-readable validation report.")
    args = parser.parse_args()

    try:
        report = validate_universal_symbol_receipt_store_write_path_idempotency_witness(args.witness, args.schema)
    except UniversalSymbolReceiptStoreWritePathIdempotencyWitnessError as exc:
        if args.json:
            print(json.dumps({"valid": False, "errors": [str(exc)]}, indent=2, sort_keys=True))
        else:
            print(f"[FAIL] universal_symbol_receipt_store_write_path_idempotency_witness: {exc}")
            print("STATUS: failed")
        return 1
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print("[PASS] universal_symbol_receipt_store_write_path_idempotency_witness")
        print("STATUS: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
