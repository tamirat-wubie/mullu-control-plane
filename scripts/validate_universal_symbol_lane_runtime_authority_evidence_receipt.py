"""Validate the Universal Symbol lane runtime authority evidence receipt.

Purpose: prove lane-level runtime authority evidence remains incomplete and
non-authorizing for the current UniversalSymbol runtime admission lanes.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: lane runtime authority evidence schema/example, skill runtime
authority witness, runtime admission evidence receipt, receipt-store authority
witness, docs, and tests.
Invariants:
  - The receipt does not grant lane runtime authority.
  - Every lane remains blocked pending live operator, receipt, recovery, audit,
    and runtime witness evidence.
  - Dispatch, connector calls, writes, receipt append, mutation, terminal
    closure, and production readiness remain denied.
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
DEFAULT_SCHEMA_PATH = REPO_ROOT / "schemas" / "universal_symbol_lane_runtime_authority_evidence_receipt.schema.json"
DEFAULT_RECEIPT_PATH = REPO_ROOT / "examples" / "universal_symbol_lane_runtime_authority_evidence_receipt.foundation.json"

REQUIRED_LANE_REFS: tuple[str, ...] = (
    "skill://teamops-shared-inbox",
    "skill://software-dev",
    "component://governance-core",
    "receipt://worker-ledger",
)

REQUIRED_BLOCKERS: tuple[str, ...] = (
    "operator_approval_missing",
    "receipt_store_authority_missing",
    "recovery_evidence_missing",
    "audit_receipt_missing",
    "live_runtime_witness_missing",
)

LANE_EVIDENCE_CONSTRAINT_TRUE_FIELDS: tuple[str, ...] = (
    "operator_approval_required",
    "receipt_store_authority_required",
    "rollback_recovery_required",
    "lane_audit_receipt_required",
    "live_runtime_witness_required",
    "blocked_action_refs_required",
    "all_lane_evidence_required_before_admission",
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
    "missing_operator_approval_blocks_lane_authority",
    "missing_receipt_store_authority_blocks_lane_authority",
    "missing_recovery_blocks_lane_authority",
    "missing_audit_receipt_blocks_lane_authority",
    "missing_live_runtime_witness_blocks_lane_authority",
    "unknown_hard_constraint_blocks_lane_authority",
    "failed_precondition_logs_delta_reject",
)

REQUIRED_BLOCKED_REASONS: tuple[str, ...] = (
    "lane_operator_approval_missing",
    "receipt_store_authority_missing",
    "rollback_recovery_missing",
    "lane_audit_receipt_missing",
    "live_runtime_witness_missing",
    "blocked_action_refs_missing",
    "lane_runtime_authority_forbidden",
    "runtime_admission_forbidden",
    "terminal_closure_not_allowed",
)

REQUIRED_EVIDENCE_REFS: tuple[str, ...] = (
    "schemas/universal_symbol_lane_runtime_authority_evidence_receipt.schema.json",
    "examples/universal_symbol_lane_runtime_authority_evidence_receipt.foundation.json",
    "schemas/universal_symbol_skill_runtime_authority_witness.schema.json",
    "examples/universal_symbol_skill_runtime_authority_witness.foundation.json",
    "schemas/universal_symbol_runtime_admission_evidence_receipt.schema.json",
    "examples/universal_symbol_runtime_admission_evidence_receipt.foundation.json",
    "schemas/universal_symbol_runtime_admission_policy.schema.json",
    "examples/universal_symbol_runtime_admission_policy.foundation.json",
    "schemas/universal_symbol_runtime_authority_witness.schema.json",
    "examples/universal_symbol_runtime_authority_witness.foundation.json",
    "schemas/universal_symbol_receipt_store_authority_witness.schema.json",
    "examples/universal_symbol_receipt_store_authority_witness.foundation.json",
    "schemas/universal_symbol_receipt_store_recovery_witness.schema.json",
    "examples/universal_symbol_receipt_store_recovery_witness.foundation.json",
    "schemas/universal_symbol.schema.json",
    "docs/91_universal_symbol_kernel.md",
    "docs/92_universal_symbol_kernel_audit.md",
    "scripts/validate_universal_symbol_lane_runtime_authority_evidence_receipt.py",
    "scripts/validate_universal_symbol_skill_runtime_authority_witness.py",
    "scripts/validate_universal_symbol_runtime_admission_evidence_receipt.py",
    "scripts/proof_coverage_matrix.py",
    "tests/test_validate_universal_symbol_kernel.py",
    "tests/test_proof_coverage_matrix.py",
)


class UniversalSymbolLaneRuntimeAuthorityEvidenceReceiptError(ValueError):
    """Raised when the lane runtime authority evidence receipt violates Foundation Mode."""


def load_json_object(path: Path) -> dict[str, Any]:
    """Return a JSON object or raise a validation error with causal context."""

    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise UniversalSymbolLaneRuntimeAuthorityEvidenceReceiptError(f"missing file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise UniversalSymbolLaneRuntimeAuthorityEvidenceReceiptError(f"invalid json: {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise UniversalSymbolLaneRuntimeAuthorityEvidenceReceiptError(f"expected object: {path}")
    return value


def validate_universal_symbol_lane_runtime_authority_evidence_receipt(
    receipt_path: Path = DEFAULT_RECEIPT_PATH,
    schema_path: Path = DEFAULT_SCHEMA_PATH,
) -> dict[str, Any]:
    """Validate schema shape, lane evidence blockers, and denied authority."""

    schema = load_json_object(schema_path)
    receipt = load_json_object(receipt_path)
    errors: list[str] = []

    _validate_schema_boundary(schema, errors)
    _validate_json_schema(receipt, schema, errors)
    _validate_receipt_boundary(receipt, errors)
    _validate_lane_evidence_items(receipt, errors)
    _validate_lane_evidence_constraints(receipt, errors)
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
        "lane_evidence_decision": receipt.get("lane_evidence_decision", ""),
        "lane_evidence_item_count": _list_len(receipt.get("lane_evidence_items")) or 0,
        "authority_denial_count": len(AUTHORITY_DENIAL_FIELDS),
        "lane_evidence_constraint_count": len(LANE_EVIDENCE_CONSTRAINT_TRUE_FIELDS),
        "evidence_ref_count": _list_len(receipt.get("evidence_refs")) or 0,
        "errors": errors,
    }
    if errors:
        raise UniversalSymbolLaneRuntimeAuthorityEvidenceReceiptError("; ".join(errors))
    return result


def _validate_schema_boundary(schema: Mapping[str, Any], errors: list[str]) -> None:
    if schema.get("$id") != "urn:mullusi:schema:universal-symbol-lane-runtime-authority-evidence-receipt:1":
        errors.append("schema id drift")
    if schema.get("additionalProperties") is not False:
        errors.append("schema must reject additional properties")
    required = schema.get("required")
    if not isinstance(required, list) or "lane_evidence_items" not in required:
        errors.append("schema must require lane_evidence_items")


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
    if receipt.get("lane_evidence_decision") != (
        "blocked_pending_live_lane_operator_receipt_recovery_audit_and_runtime_evidence"
    ):
        errors.append("lane_evidence_decision must remain blocked")
    if receipt.get("receipt_is_not_lane_authority") is not True:
        errors.append("receipt must not be lane authority")


def _validate_lane_evidence_items(receipt: Mapping[str, Any], errors: list[str]) -> None:
    items = receipt.get("lane_evidence_items")
    if not isinstance(items, list) or not items:
        errors.append("lane_evidence_items must be non-empty")
        return
    lane_refs: list[str] = []
    for item in items:
        if not isinstance(item, dict):
            errors.append("lane evidence entries must be objects")
            continue
        lane_ref = str(item.get("lane_ref"))
        lane_refs.append(lane_ref)
        if item.get("proof_state") not in {"Unknown", "BudgetUnknown", "Fail"}:
            errors.append(f"{lane_ref}: proof_state must block authority")
        if item.get("lane_evidence_state") != "blocked_pending_live_lane_evidence":
            errors.append(f"{lane_ref}: lane_evidence_state must remain blocked")
        if item.get("current_decision") != "lane_runtime_authority_blocked":
            errors.append(f"{lane_ref}: current_decision must remain blocked")
        blockers = _string_list(item.get("blocker_classifications"))
        _require_members(f"{lane_ref}.blocker_classifications", blockers, REQUIRED_BLOCKERS, errors)
        if _string_list(item.get("observed_evidence_refs")):
            errors.append(f"{lane_ref}: observed_evidence_refs must remain empty in Foundation Mode")
        if len(_string_list(item.get("required_evidence_refs"))) < 5:
            errors.append(f"{lane_ref}: required_evidence_refs must include lane evidence")
        blocked_actions = set(_string_list(item.get("blocked_action_refs")))
        if len(blocked_actions) < 3:
            errors.append(f"{lane_ref}: blocked_action_refs must include at least three actions")
        if not any("terminal-closure" in action or "terminal_closure" in action for action in blocked_actions):
            errors.append(f"{lane_ref}: terminal closure must be blocked")
        if not str(item.get("delta_reject_ref", "")).startswith("delta-reject://"):
            errors.append(f"{lane_ref}: delta_reject_ref must be logged")
    _require_members("lane_evidence_items", lane_refs, REQUIRED_LANE_REFS, errors)


def _validate_lane_evidence_constraints(receipt: Mapping[str, Any], errors: list[str]) -> None:
    constraints = _mapping(receipt.get("lane_evidence_constraints"))
    for field_name in LANE_EVIDENCE_CONSTRAINT_TRUE_FIELDS:
        if constraints.get(field_name) is not True:
            errors.append(f"lane_evidence_constraints.{field_name} must remain true")


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
        "lane_evidence_item_count": _list_len(receipt.get("lane_evidence_items")),
        "lane_evidence_constraint_count": len(LANE_EVIDENCE_CONSTRAINT_TRUE_FIELDS),
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
        report = validate_universal_symbol_lane_runtime_authority_evidence_receipt(args.receipt, args.schema)
    except UniversalSymbolLaneRuntimeAuthorityEvidenceReceiptError as exc:
        if args.json:
            print(json.dumps({"valid": False, "errors": str(exc).split("; ")}, indent=2, sort_keys=True))
        else:
            print(f"[FAIL] universal_symbol_lane_runtime_authority_evidence_receipt: {exc}")
            print("STATUS: failed")
        return 1

    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print("[PASS] universal_symbol_lane_runtime_authority_evidence_receipt")
        print("STATUS: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
