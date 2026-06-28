"""Validate the Universal Symbol skill runtime authority witness.

Purpose: prove skill-by-skill UniversalSymbol runtime authority remains blocked
until lane-level operator, receipt-store, recovery, and audit evidence exists.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: skill runtime authority witness schema/example, runtime admission
policy, runtime authority witness, receipt-store authority witness, docs, and
tests.
Invariants:
  - The witness does not grant skill runtime authority.
  - Every declared runtime admission lane remains blocked.
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
DEFAULT_SCHEMA_PATH = REPO_ROOT / "schemas" / "universal_symbol_skill_runtime_authority_witness.schema.json"
DEFAULT_WITNESS_PATH = REPO_ROOT / "examples" / "universal_symbol_skill_runtime_authority_witness.foundation.json"

REQUIRED_LANE_REFS: tuple[str, ...] = (
    "skill://teamops-shared-inbox",
    "skill://software-dev",
    "component://governance-core",
    "receipt://worker-ledger",
)

AUTHORITY_DENIAL_FIELDS: tuple[str, ...] = (
    "skill_runtime_authority_granted",
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
    "production_readiness_claimed",
)

LANE_CONSTRAINT_TRUE_FIELDS: tuple[str, ...] = (
    "runtime_admission_policy_required",
    "runtime_authority_witness_required",
    "operator_approval_required",
    "receipt_store_authority_required",
    "rollback_recovery_required",
    "lane_audit_receipt_required",
    "blocked_action_refs_required",
    "terminal_closure_denial_required",
)

REJECTION_POLICY_TRUE_FIELDS: tuple[str, ...] = (
    "missing_lane_authority_blocks_admission",
    "missing_operator_approval_blocks_admission",
    "missing_receipt_store_authority_blocks_admission",
    "missing_recovery_blocks_admission",
    "missing_audit_receipt_blocks_admission",
    "unknown_hard_constraint_blocks_admission",
    "failed_precondition_logs_delta_reject",
)

REQUIRED_BLOCKED_REASONS: tuple[str, ...] = (
    "runtime_admission_policy_missing",
    "runtime_authority_witness_missing",
    "lane_operator_approval_missing",
    "receipt_store_authority_missing",
    "rollback_recovery_missing",
    "lane_audit_receipt_missing",
    "blocked_action_refs_missing",
    "skill_runtime_authority_binding_forbidden",
    "terminal_closure_not_allowed",
)

REQUIRED_EVIDENCE_REFS: tuple[str, ...] = (
    "schemas/universal_symbol_skill_runtime_authority_witness.schema.json",
    "examples/universal_symbol_skill_runtime_authority_witness.foundation.json",
    "schemas/universal_symbol_runtime_admission_policy.schema.json",
    "examples/universal_symbol_runtime_admission_policy.foundation.json",
    "schemas/universal_symbol_runtime_authority_witness.schema.json",
    "examples/universal_symbol_runtime_authority_witness.foundation.json",
    "schemas/universal_symbol_lane_runtime_authority_evidence_receipt.schema.json",
    "examples/universal_symbol_lane_runtime_authority_evidence_receipt.foundation.json",
    "schemas/universal_symbol_receipt_store_authority_witness.schema.json",
    "examples/universal_symbol_receipt_store_authority_witness.foundation.json",
    "schemas/universal_symbol_receipt_store_recovery_witness.schema.json",
    "examples/universal_symbol_receipt_store_recovery_witness.foundation.json",
    "schemas/universal_symbol.schema.json",
    "docs/91_universal_symbol_kernel.md",
    "docs/92_universal_symbol_kernel_audit.md",
    "scripts/validate_universal_symbol_skill_runtime_authority_witness.py",
    "scripts/validate_universal_symbol_lane_runtime_authority_evidence_receipt.py",
    "scripts/validate_universal_symbol_runtime_admission_policy.py",
    "scripts/validate_universal_symbol_runtime_authority_witness.py",
    "scripts/validate_universal_symbol_receipt_store_authority_witness.py",
    "scripts/validate_universal_symbol_receipt_store_recovery_witness.py",
    "scripts/proof_coverage_matrix.py",
    "tests/test_validate_universal_symbol_kernel.py",
    "tests/test_proof_coverage_matrix.py",
)


class UniversalSymbolSkillRuntimeAuthorityWitnessError(ValueError):
    """Raised when the skill runtime authority witness violates Foundation Mode."""


def load_json_object(path: Path) -> dict[str, Any]:
    """Return a JSON object or raise a validation error with causal context."""

    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise UniversalSymbolSkillRuntimeAuthorityWitnessError(f"missing file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise UniversalSymbolSkillRuntimeAuthorityWitnessError(f"invalid json: {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise UniversalSymbolSkillRuntimeAuthorityWitnessError(f"expected object: {path}")
    return value


def validate_universal_symbol_skill_runtime_authority_witness(
    witness_path: Path = DEFAULT_WITNESS_PATH,
    schema_path: Path = DEFAULT_SCHEMA_PATH,
) -> dict[str, Any]:
    """Validate schema shape, lane requirements, and denied authority."""

    schema = load_json_object(schema_path)
    witness = load_json_object(witness_path)
    errors: list[str] = []

    _validate_schema_boundary(schema, errors)
    _validate_json_schema(witness, schema, errors)
    _validate_witness_boundary(witness, errors)
    _validate_lane_requirements(witness, errors)
    _validate_authority_denials(witness, errors)
    _validate_lane_constraints(witness, errors)
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
        "skill_authority_decision": witness.get("skill_authority_decision", ""),
        "lane_requirement_count": _list_len(witness.get("lane_requirements")) or 0,
        "authority_denial_count": len(AUTHORITY_DENIAL_FIELDS),
        "lane_constraint_count": len(LANE_CONSTRAINT_TRUE_FIELDS),
        "evidence_ref_count": _list_len(witness.get("evidence_refs")) or 0,
        "errors": errors,
    }
    if errors:
        raise UniversalSymbolSkillRuntimeAuthorityWitnessError("; ".join(errors))
    return result


def _validate_schema_boundary(schema: Mapping[str, Any], errors: list[str]) -> None:
    if schema.get("$id") != "urn:mullusi:schema:universal-symbol-skill-runtime-authority-witness:1":
        errors.append("schema id drift")
    if schema.get("additionalProperties") is not False:
        errors.append("schema must reject additional properties")
    required = schema.get("required")
    if not isinstance(required, list) or "lane_requirements" not in required:
        errors.append("schema must require lane_requirements")


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
    if witness.get("skill_authority_decision") != (
        "blocked_pending_lane_operator_receipt_recovery_and_audit_evidence"
    ):
        errors.append("skill_authority_decision must remain blocked")
    if witness.get("skill_runtime_authority_witness_is_not_skill_authority") is not True:
        errors.append("skill runtime authority witness must not be skill authority")


def _validate_lane_requirements(witness: Mapping[str, Any], errors: list[str]) -> None:
    requirements = witness.get("lane_requirements")
    if not isinstance(requirements, list) or not requirements:
        errors.append("lane_requirements must be non-empty")
        return
    lane_refs: list[str] = []
    for requirement in requirements:
        if not isinstance(requirement, dict):
            errors.append("lane requirement entries must be objects")
            continue
        lane_ref = str(requirement.get("lane_ref"))
        lane_refs.append(lane_ref)
        if requirement.get("proof_state") not in {"Unknown", "BudgetUnknown", "Fail"}:
            errors.append(f"{lane_ref}: proof_state must block authority")
        if requirement.get("admission_state") != "blocked_pending_live_runtime_authority":
            errors.append(f"{lane_ref}: admission_state must remain blocked")
        if len(_string_list(requirement.get("required_evidence_refs"))) < 6:
            errors.append(f"{lane_ref}: required_evidence_refs must include lane evidence")
        blocked_actions = set(_string_list(requirement.get("blocked_action_refs")))
        if len(blocked_actions) < 3:
            errors.append(f"{lane_ref}: blocked_action_refs must include at least three actions")
        if not any("terminal-closure" in action or "terminal_closure" in action for action in blocked_actions):
            errors.append(f"{lane_ref}: terminal closure must be blocked")
        if not str(requirement.get("delta_reject_ref", "")).startswith("delta-reject://"):
            errors.append(f"{lane_ref}: delta_reject_ref must be logged")
    _require_members("lane_requirements", lane_refs, REQUIRED_LANE_REFS, errors)


def _validate_authority_denials(witness: Mapping[str, Any], errors: list[str]) -> None:
    denials = _mapping(witness.get("authority_denials"))
    for field_name in AUTHORITY_DENIAL_FIELDS:
        if denials.get(field_name) is not False:
            errors.append(f"authority_denials.{field_name} must remain false")


def _validate_lane_constraints(witness: Mapping[str, Any], errors: list[str]) -> None:
    constraints = _mapping(witness.get("lane_constraints"))
    for field_name in LANE_CONSTRAINT_TRUE_FIELDS:
        if constraints.get(field_name) is not True:
            errors.append(f"lane_constraints.{field_name} must remain true")


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
    observed = [item for item in blocked_reasons if isinstance(item, str)]
    _require_members("blocked_reasons", observed, REQUIRED_BLOCKED_REASONS, errors)


def _validate_contract_summary(witness: Mapping[str, Any], errors: list[str]) -> None:
    summary = _mapping(witness.get("contract_summary"))
    observed_counts = {
        "lane_requirement_count": _list_len(witness.get("lane_requirements")),
        "authority_denial_count": len(AUTHORITY_DENIAL_FIELDS),
        "lane_constraint_count": len(LANE_CONSTRAINT_TRUE_FIELDS),
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


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


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
    for unexpected_value in sorted(set(observed_values) - set(required_values)):
        errors.append(f"{field_name} has unexpected value: {unexpected_value}")
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
        report = validate_universal_symbol_skill_runtime_authority_witness(args.witness, args.schema)
    except UniversalSymbolSkillRuntimeAuthorityWitnessError as exc:
        if args.json:
            print(json.dumps({"valid": False, "errors": str(exc).split("; ")}, indent=2, sort_keys=True))
        else:
            print(f"[FAIL] universal_symbol_skill_runtime_authority_witness: {exc}")
            print("STATUS: failed")
        return 1

    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print("[PASS] universal_symbol_skill_runtime_authority_witness")
        print("STATUS: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
