"""Validate the Universal Symbol runtime admission evidence receipt.

Purpose: prove live runtime admission evidence remains incomplete and
non-authorizing until operator, orchestration, receipt-store, skill-lane,
rollback, and proof evidence exists.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: runtime admission evidence schema/example, runtime admission
policy, runtime authority witness, skill runtime authority witness, docs, and
tests.
Invariants:
  - The receipt does not grant runtime authority.
  - Every required live evidence item blocks runtime admission.
  - Runtime registration, live dispatch, connector calls, writes, append,
    mutation, terminal closure, and production readiness remain denied.
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
DEFAULT_SCHEMA_PATH = REPO_ROOT / "schemas" / "universal_symbol_runtime_admission_evidence_receipt.schema.json"
DEFAULT_RECEIPT_PATH = REPO_ROOT / "examples" / "universal_symbol_runtime_admission_evidence_receipt.foundation.json"

REQUIRED_EVIDENCE_KINDS: tuple[str, ...] = (
    "live_runtime_witness",
    "runtime_authority_witness",
    "operator_approval",
    "uao_decision",
    "phi_gov_decision",
    "life_meaning_judgment",
    "receipt_store_authority",
    "skill_lane_witness",
    "lane_runtime_authority_evidence",
    "rollback_recovery_handoff",
)

CONSISTENCY_CONSTRAINT_TRUE_FIELDS: tuple[str, ...] = (
    "runtime_authority_witness_matches_policy_required",
    "operator_approval_matches_authority_scope_required",
    "uao_decision_matches_effect_boundary_required",
    "phi_gov_decision_matches_state_write_required",
    "life_meaning_judgment_matches_effect_required",
    "receipt_store_authority_denial_respected",
    "skill_lane_witnesses_match_admission_matrix_required",
    "rollback_recovery_handoff_required",
    "proof_coverage_surface_closed_required",
    "all_live_evidence_required_before_runtime_admission",
)

AUTHORITY_DENIAL_FIELDS: tuple[str, ...] = (
    "runtime_admission_granted",
    "runtime_registration_performed",
    "live_dispatch_enabled",
    "connector_call_enabled",
    "filesystem_write_enabled",
    "external_write_enabled",
    "receipt_store_append_enabled",
    "raw_payload_stored",
    "raw_secret_stored",
    "state_mutation_performed",
    "terminal_closure_allowed",
    "production_readiness_claimed",
)

REJECTION_POLICY_TRUE_FIELDS: tuple[str, ...] = (
    "missing_live_runtime_witness_blocks_admission",
    "missing_operator_approval_blocks_admission",
    "missing_orchestration_decision_blocks_admission",
    "missing_receipt_store_authority_blocks_admission",
    "missing_skill_lane_witness_blocks_admission",
    "missing_rollback_recovery_blocks_admission",
    "unknown_hard_constraint_blocks_admission",
    "failed_precondition_logs_delta_reject",
)

REQUIRED_BLOCKED_REASONS: tuple[str, ...] = (
    "live_runtime_witness_missing",
    "runtime_authority_witness_missing",
    "operator_approval_missing",
    "uao_decision_missing",
    "phi_gov_decision_missing",
    "life_meaning_judgment_missing",
    "receipt_store_authority_missing",
    "skill_lane_witness_missing",
    "rollback_recovery_handoff_missing",
    "proof_coverage_missing",
    "runtime_admission_forbidden",
    "terminal_closure_not_allowed",
)

REQUIRED_EVIDENCE_REFS: tuple[str, ...] = (
    "schemas/universal_symbol_runtime_admission_evidence_receipt.schema.json",
    "examples/universal_symbol_runtime_admission_evidence_receipt.foundation.json",
    "schemas/universal_symbol_runtime_live_witness_input_receipt.schema.json",
    "examples/universal_symbol_runtime_live_witness_input_receipt.foundation.json",
    "schemas/universal_symbol_runtime_admission_policy.schema.json",
    "examples/universal_symbol_runtime_admission_policy.foundation.json",
    "schemas/universal_symbol_runtime_authority_witness.schema.json",
    "examples/universal_symbol_runtime_authority_witness.foundation.json",
    "schemas/universal_symbol_runtime_authority_read_model.schema.json",
    "examples/universal_symbol_runtime_authority_read_model.foundation.json",
    "schemas/universal_symbol_skill_runtime_authority_witness.schema.json",
    "examples/universal_symbol_skill_runtime_authority_witness.foundation.json",
    "schemas/universal_symbol_lane_runtime_authority_evidence_receipt.schema.json",
    "examples/universal_symbol_lane_runtime_authority_evidence_receipt.foundation.json",
    "schemas/universal_symbol_receipt_store_authority_witness.schema.json",
    "examples/universal_symbol_receipt_store_authority_witness.foundation.json",
    "schemas/universal_symbol_receipt_store_operator_approval_witness.schema.json",
    "examples/universal_symbol_receipt_store_operator_approval_witness.foundation.json",
    "schemas/universal_symbol_receipt_store_recovery_witness.schema.json",
    "examples/universal_symbol_receipt_store_recovery_witness.foundation.json",
    "schemas/universal_symbol.schema.json",
    "docs/91_universal_symbol_kernel.md",
    "docs/92_universal_symbol_kernel_audit.md",
    "scripts/validate_universal_symbol_runtime_admission_evidence_receipt.py",
    "scripts/validate_universal_symbol_runtime_live_witness_input_receipt.py",
    "scripts/validate_universal_symbol_runtime_admission_policy.py",
    "scripts/validate_universal_symbol_runtime_authority_witness.py",
    "scripts/validate_universal_symbol_runtime_authority_read_model.py",
    "scripts/validate_universal_symbol_lane_runtime_authority_evidence_receipt.py",
    "scripts/proof_coverage_matrix.py",
    "tests/test_validate_universal_symbol_kernel.py",
    "tests/test_proof_coverage_matrix.py",
)


class UniversalSymbolRuntimeAdmissionEvidenceReceiptError(ValueError):
    """Raised when the runtime admission evidence receipt violates Foundation Mode."""


def load_json_object(path: Path) -> dict[str, Any]:
    """Return a JSON object or raise a validation error with causal context."""

    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise UniversalSymbolRuntimeAdmissionEvidenceReceiptError(f"missing file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise UniversalSymbolRuntimeAdmissionEvidenceReceiptError(f"invalid json: {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise UniversalSymbolRuntimeAdmissionEvidenceReceiptError(f"expected object: {path}")
    return value


def validate_universal_symbol_runtime_admission_evidence_receipt(
    receipt_path: Path = DEFAULT_RECEIPT_PATH,
    schema_path: Path = DEFAULT_SCHEMA_PATH,
) -> dict[str, Any]:
    """Validate schema shape, live-evidence blockers, and denied authority."""

    schema = load_json_object(schema_path)
    receipt = load_json_object(receipt_path)
    errors: list[str] = []

    _validate_schema_boundary(schema, errors)
    _validate_json_schema(receipt, schema, errors)
    _validate_receipt_boundary(receipt, errors)
    _validate_runtime_subject(receipt, errors)
    _validate_live_evidence(receipt, errors)
    _validate_consistency_constraints(receipt, errors)
    _validate_authority_denials(receipt, errors)
    _validate_rejection_policy(receipt, errors)
    _validate_blocked_reasons(receipt, errors)
    _validate_contract_summary(receipt, errors)
    _validate_evidence_refs(receipt, errors)
    _validate_evidence_ref_files(receipt, errors)

    result = {
        "receipt_path": _repo_relative(receipt_path),
        "schema_path": _repo_relative(schema_path),
        "valid": not errors,
        "receipt_id": receipt.get("receipt_id", ""),
        "solver_outcome": receipt.get("solver_outcome", ""),
        "admission_evidence_decision": receipt.get("admission_evidence_decision", ""),
        "live_evidence_requirement_count": _list_len(receipt.get("required_live_evidence")) or 0,
        "authority_denial_count": len(AUTHORITY_DENIAL_FIELDS),
        "consistency_constraint_count": len(CONSISTENCY_CONSTRAINT_TRUE_FIELDS),
        "evidence_ref_count": _list_len(receipt.get("evidence_refs")) or 0,
        "errors": errors,
    }
    if errors:
        raise UniversalSymbolRuntimeAdmissionEvidenceReceiptError("; ".join(errors))
    return result


def _validate_schema_boundary(schema: Mapping[str, Any], errors: list[str]) -> None:
    if schema.get("$id") != "urn:mullusi:schema:universal-symbol-runtime-admission-evidence-receipt:1":
        errors.append("schema id drift")
    if schema.get("additionalProperties") is not False:
        errors.append("schema must reject additional properties")
    required = schema.get("required")
    if not isinstance(required, list) or "required_live_evidence" not in required:
        errors.append("schema must require required_live_evidence")


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
    if receipt.get("admission_evidence_decision") != (
        "blocked_pending_live_runtime_admission_operator_orchestration_receipt_store_skill_recovery_and_proof_evidence"
    ):
        errors.append("admission_evidence_decision must remain blocked")
    if receipt.get("receipt_is_not_runtime_authority") is not True:
        errors.append("receipt must not be runtime authority")


def _validate_runtime_subject(receipt: Mapping[str, Any], errors: list[str]) -> None:
    subject = _mapping(receipt.get("runtime_subject"))
    expected_refs = {
        "runtime_admission_policy_ref": "schemas/universal_symbol_runtime_admission_policy.schema.json",
        "runtime_authority_witness_ref": "schemas/universal_symbol_runtime_authority_witness.schema.json",
        "runtime_authority_read_model_ref": "schemas/universal_symbol_runtime_authority_read_model.schema.json",
        "skill_runtime_authority_witness_ref": "schemas/universal_symbol_skill_runtime_authority_witness.schema.json",
    }
    for field_name, expected_ref in expected_refs.items():
        if subject.get(field_name) != expected_ref:
            errors.append(f"runtime_subject.{field_name} drift")
    if subject.get("authority_scope") != "runtime-admission-evidence-only":
        errors.append("runtime_subject.authority_scope must remain evidence-only")


def _validate_live_evidence(receipt: Mapping[str, Any], errors: list[str]) -> None:
    requirements = receipt.get("required_live_evidence")
    if not isinstance(requirements, list) or not requirements:
        errors.append("required_live_evidence must be non-empty")
        return
    evidence_kinds: list[str] = []
    for requirement in requirements:
        if not isinstance(requirement, dict):
            errors.append("required_live_evidence entries must be objects")
            continue
        evidence_id = str(requirement.get("evidence_id"))
        evidence_kinds.append(str(requirement.get("evidence_kind")))
        if requirement.get("evidence_kind") == "live_runtime_witness" and requirement.get(
            "required_evidence_ref"
        ) != "schemas/universal_symbol_runtime_live_witness_input_receipt.schema.json":
            errors.append("live_runtime_witness must bind runtime live witness input receipt schema")
        if requirement.get("proof_state") not in {"Unknown", "BudgetUnknown", "Fail"}:
            errors.append(f"{evidence_id}: proof_state must block admission")
        if requirement.get("current_decision") != "runtime_admission_blocked":
            errors.append(f"{evidence_id}: current_decision must remain blocked")
        if not str(requirement.get("required_evidence_ref", "")):
            errors.append(f"{evidence_id}: required_evidence_ref is required")
        if not str(requirement.get("delta_reject_ref", "")).startswith("delta-reject://"):
            errors.append(f"{evidence_id}: delta_reject_ref must be logged")
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
    observed = [item for item in blocked_reasons if isinstance(item, str)]
    _require_members("blocked_reasons", observed, REQUIRED_BLOCKED_REASONS, errors)


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
        report = validate_universal_symbol_runtime_admission_evidence_receipt(args.receipt, args.schema)
    except UniversalSymbolRuntimeAdmissionEvidenceReceiptError as exc:
        if args.json:
            print(json.dumps({"valid": False, "errors": str(exc).split("; ")}, indent=2, sort_keys=True))
        else:
            print(f"[FAIL] universal_symbol_runtime_admission_evidence_receipt: {exc}")
            print("STATUS: failed")
        return 1

    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print("[PASS] universal_symbol_runtime_admission_evidence_receipt")
        print("STATUS: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
