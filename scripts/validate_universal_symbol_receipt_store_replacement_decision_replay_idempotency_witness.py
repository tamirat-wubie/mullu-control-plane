"""Validate the replacement decision replay idempotency witness.

Purpose: prove UniversalSymbol receipt-store replacement decision replay remains
blocked until replacement receipt binding, deterministic idempotency key,
canonical replay input, decision digest, tenant/scope digest, replay cursor,
duplicate-effect denial, and audit receipt evidence exist.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: replay/idempotency schema/example, replacement decision receipt,
lifecycle audit receipt, UniversalSymbol kernel docs, proof matrix, and tests.
Invariants:
  - The witness is not replay authority.
  - Replay binding, idempotency acceptance, replacement recording, receipt
    append, replay state commit, duplicate effects, raw payload storage, raw
    secret storage, runtime dispatch, connector calls, mutation, and terminal
    closure remain denied.
  - Unknown hard preconditions block replay and log Delta_reject refs.
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
    REPO_ROOT
    / "schemas"
    / "universal_symbol_receipt_store_replacement_decision_replay_idempotency_witness.schema.json"
)
DEFAULT_WITNESS_PATH = (
    REPO_ROOT
    / "examples"
    / "universal_symbol_receipt_store_replacement_decision_replay_idempotency_witness.foundation.json"
)

AUTHORITY_DENIAL_FIELDS: tuple[str, ...] = (
    "replacement_replay_bound",
    "idempotency_key_accepted",
    "replacement_decision_recorded",
    "receipt_store_append_performed",
    "replay_state_committed",
    "duplicate_effect_allowed",
    "raw_payload_stored",
    "raw_secret_stored",
    "runtime_dispatch_performed",
    "connector_call_performed",
    "state_mutation_performed",
    "terminal_closure_allowed",
)

REQUIRED_REQUIREMENT_IDS: tuple[str, ...] = (
    "requirement://replacement-decision-receipt",
    "requirement://deterministic-idempotency-key",
    "requirement://canonical-replay-input",
    "requirement://decision-digest-binding",
    "requirement://tenant-scope-digest",
    "requirement://replay-cursor",
    "requirement://duplicate-effect-denial",
    "requirement://audit-receipt",
)

REPLAY_CONSTRAINT_TRUE_FIELDS: tuple[str, ...] = (
    "replacement_decision_receipt_required",
    "deterministic_idempotency_key_required",
    "canonical_replay_input_required",
    "decision_digest_binding_required",
    "tenant_scope_digest_required",
    "replay_cursor_required",
    "duplicate_effect_denial_required",
    "audit_receipt_required",
)

REJECTION_POLICY_TRUE_FIELDS: tuple[str, ...] = (
    "missing_replacement_receipt_blocks_replay",
    "missing_key_or_canonical_input_blocks_replay",
    "missing_digest_binding_blocks_replay",
    "missing_cursor_or_duplicate_denial_blocks_replay",
    "unknown_hard_constraint_blocks_replay",
    "failed_precondition_logs_delta_reject",
)

REQUIRED_BLOCKED_REASONS: tuple[str, ...] = (
    "replacement_decision_receipt_missing",
    "deterministic_idempotency_key_missing",
    "canonical_replay_input_missing",
    "decision_digest_binding_missing",
    "tenant_scope_digest_missing",
    "replay_cursor_missing",
    "duplicate_effect_denial_missing",
    "audit_receipt_missing",
    "replacement_replay_forbidden",
    "terminal_closure_not_allowed",
)

REQUIRED_EVIDENCE_REFS: tuple[str, ...] = (
    "schemas/universal_symbol_receipt_store_replacement_decision_replay_idempotency_witness.schema.json",
    "examples/universal_symbol_receipt_store_replacement_decision_replay_idempotency_witness.foundation.json",
    "schemas/universal_symbol_receipt_store_replacement_decision_receipt.schema.json",
    "examples/universal_symbol_receipt_store_replacement_decision_receipt.foundation.json",
    "schemas/universal_symbol_receipt_store_lifecycle_audit_receipt.schema.json",
    "examples/universal_symbol_receipt_store_lifecycle_audit_receipt.foundation.json",
    "schemas/universal_symbol.schema.json",
    "docs/91_universal_symbol_kernel.md",
    "docs/92_universal_symbol_kernel_audit.md",
    "scripts/validate_universal_symbol_receipt_store_replacement_decision_replay_idempotency_witness.py",
    "tests/test_validate_universal_symbol_kernel.py",
    "scripts/proof_coverage_matrix.py",
    "tests/test_proof_coverage_matrix.py",
)


class UniversalSymbolReceiptStoreReplacementDecisionReplayIdempotencyWitnessError(ValueError):
    """Raised when the replacement replay/idempotency witness violates Foundation Mode."""


def load_json_object(path: Path) -> dict[str, Any]:
    """Return a JSON object or raise a validation error with causal context."""

    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise UniversalSymbolReceiptStoreReplacementDecisionReplayIdempotencyWitnessError(
            f"missing file: {path}"
        ) from exc
    except json.JSONDecodeError as exc:
        raise UniversalSymbolReceiptStoreReplacementDecisionReplayIdempotencyWitnessError(
            f"invalid json: {path}: {exc}"
        ) from exc
    if not isinstance(value, dict):
        raise UniversalSymbolReceiptStoreReplacementDecisionReplayIdempotencyWitnessError(
            f"expected object: {path}"
        )
    return value


def validate_universal_symbol_receipt_store_replacement_decision_replay_idempotency_witness(
    witness_path: Path = DEFAULT_WITNESS_PATH,
    schema_path: Path = DEFAULT_SCHEMA_PATH,
) -> dict[str, Any]:
    """Validate schema shape, denied replay authority, and evidence refs."""

    schema = load_json_object(schema_path)
    witness = load_json_object(witness_path)
    errors: list[str] = []

    _validate_schema_boundary(schema, errors)
    _validate_json_schema(witness, schema, errors)
    _validate_witness_boundary(witness, errors)
    _validate_replay_requirements(witness, errors)
    _validate_authority_denials(witness, errors)
    _validate_replay_constraints(witness, errors)
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
        "replay_idempotency_decision": witness.get("replay_idempotency_decision", ""),
        "authority_denial_count": len(AUTHORITY_DENIAL_FIELDS),
        "replay_requirement_count": len(witness.get("replay_requirements", []))
        if isinstance(witness.get("replay_requirements"), list)
        else 0,
        "evidence_ref_count": len(witness.get("evidence_refs", []))
        if isinstance(witness.get("evidence_refs"), list)
        else 0,
        "errors": errors,
    }
    if errors:
        raise UniversalSymbolReceiptStoreReplacementDecisionReplayIdempotencyWitnessError("; ".join(errors))
    return report


def _validate_schema_boundary(schema: Mapping[str, Any], errors: list[str]) -> None:
    expected = "urn:mullusi:schema:universal-symbol-receipt-store-replacement-decision-replay-idempotency-witness:1"
    if schema.get("$id") != expected:
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
        witness.get("replay_idempotency_decision")
        != "blocked_pending_replacement_receipt_key_digest_cursor_duplicate_denial_and_audit_evidence"
    ):
        errors.append("replay_idempotency_decision must remain blocked")
    if witness.get("replay_idempotency_witness_is_not_replay_authority") is not True:
        errors.append("replay idempotency witness must not grant replay authority")


def _validate_replay_requirements(witness: Mapping[str, Any], errors: list[str]) -> None:
    requirements = witness.get("replay_requirements")
    if not isinstance(requirements, list) or not requirements:
        errors.append("replay_requirements must be non-empty")
        return
    requirement_ids: list[str] = []
    for requirement in requirements:
        if not isinstance(requirement, dict):
            errors.append("replay requirement entries must be objects")
            continue
        requirement_ids.append(str(requirement.get("requirement_id")))
        if requirement.get("proof_state") not in {"Unknown", "BudgetUnknown", "Fail"}:
            errors.append(f"{requirement.get('requirement_id')}: proof_state must block replay")
        if requirement.get("current_decision") != "replacement_replay_blocked":
            errors.append(f"{requirement.get('requirement_id')}: current_decision must block replay")
        if not str(requirement.get("delta_reject_ref", "")).startswith("delta-reject://"):
            errors.append(f"{requirement.get('requirement_id')}: delta_reject_ref must be logged")
    _require_members("replay_requirements", requirement_ids, REQUIRED_REQUIREMENT_IDS, errors)


def _validate_authority_denials(witness: Mapping[str, Any], errors: list[str]) -> None:
    denials = _mapping(witness.get("authority_denials"))
    for field_name in AUTHORITY_DENIAL_FIELDS:
        if denials.get(field_name) is not False:
            errors.append(f"authority_denials.{field_name} must remain false")


def _validate_replay_constraints(witness: Mapping[str, Any], errors: list[str]) -> None:
    constraints = _mapping(witness.get("replay_constraints"))
    for field_name in REPLAY_CONSTRAINT_TRUE_FIELDS:
        if constraints.get(field_name) is not True:
            errors.append(f"replay_constraints.{field_name} must remain true")


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
    requirements = witness.get("replay_requirements")
    blocked_reasons = witness.get("blocked_reasons")
    evidence_refs = witness.get("evidence_refs")
    if isinstance(requirements, list) and summary.get("replay_requirement_count") != len(requirements):
        errors.append("replay_requirement_count drift")
    if summary.get("authority_denial_count") != len(AUTHORITY_DENIAL_FIELDS):
        errors.append("authority_denial_count drift")
    if summary.get("replay_constraint_count") != len(REPLAY_CONSTRAINT_TRUE_FIELDS):
        errors.append("replay_constraint_count drift")
    if summary.get("rejection_check_count") != len(REJECTION_POLICY_TRUE_FIELDS):
        errors.append("rejection_check_count drift")
    if isinstance(blocked_reasons, list) and summary.get("blocked_reason_count") != len(blocked_reasons):
        errors.append("blocked_reason_count drift")
    if isinstance(evidence_refs, list) and summary.get("evidence_ref_count") != len(evidence_refs):
        errors.append("evidence_ref_count drift")


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
        description="Validate the replacement decision replay idempotency witness."
    )
    parser.add_argument("--witness", type=Path, default=DEFAULT_WITNESS_PATH)
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA_PATH)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    try:
        report = validate_universal_symbol_receipt_store_replacement_decision_replay_idempotency_witness(
            args.witness,
            args.schema,
        )
    except UniversalSymbolReceiptStoreReplacementDecisionReplayIdempotencyWitnessError as exc:
        if args.json:
            print(json.dumps({"valid": False, "errors": [str(exc)]}, indent=2, sort_keys=True))
        else:
            print(f"[FAIL] universal_symbol_receipt_store_replacement_decision_replay_idempotency_witness: {exc}")
        return 1

    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print("[PASS] universal_symbol_receipt_store_replacement_decision_replay_idempotency_witness")
        print("STATUS: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
