"""Validate the Universal Symbol runtime live witness input receipt.

Purpose: prove live runtime witness input collection remains incomplete,
non-authorizing, and Foundation Mode bounded until named endpoint, process,
probe, dry-run, receipt-store denial, operator, freshness, and proof inputs
exist.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: runtime live witness input schema/example, runtime admission
evidence receipt, runtime authority read model, docs, and tests.
Invariants:
  - The receipt does not grant runtime authority.
  - Every required live-witness input blocks live witness acceptance.
  - Runtime admission, dispatch, connector calls, writes, append, mutation,
    and terminal closure remain denied.
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
DEFAULT_SCHEMA_PATH = REPO_ROOT / "schemas" / "universal_symbol_runtime_live_witness_input_receipt.schema.json"
DEFAULT_RECEIPT_PATH = REPO_ROOT / "examples" / "universal_symbol_runtime_live_witness_input_receipt.foundation.json"

REQUIRED_INPUT_KINDS: tuple[str, ...] = (
    "runtime_endpoint",
    "runtime_process_identity",
    "runtime_health_probe",
    "runtime_no_effect_dry_run",
    "receipt_store_append_denial",
    "operator_observation",
    "freshness_window",
    "proof_coverage_binding",
)

CONSISTENCY_CONSTRAINT_TRUE_FIELDS: tuple[str, ...] = (
    "endpoint_matches_declared_runtime_required",
    "process_identity_matches_endpoint_required",
    "health_probe_matches_process_required",
    "dry_run_has_no_effect_required",
    "receipt_store_append_denial_required",
    "operator_observation_matches_probe_required",
    "freshness_window_required",
    "all_inputs_required_before_live_runtime_witness",
)

AUTHORITY_DENIAL_FIELDS: tuple[str, ...] = (
    "live_runtime_witness_accepted",
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
)

REJECTION_POLICY_TRUE_FIELDS: tuple[str, ...] = (
    "missing_endpoint_blocks_live_witness",
    "missing_process_identity_blocks_live_witness",
    "missing_health_probe_blocks_live_witness",
    "missing_no_effect_dry_run_blocks_live_witness",
    "missing_receipt_store_denial_blocks_live_witness",
    "missing_operator_observation_blocks_live_witness",
    "unknown_hard_constraint_blocks_live_witness",
    "failed_precondition_logs_delta_reject",
)

REQUIRED_BLOCKED_REASONS: tuple[str, ...] = (
    "runtime_endpoint_input_missing",
    "runtime_process_identity_input_missing",
    "runtime_health_probe_input_missing",
    "runtime_no_effect_dry_run_input_missing",
    "receipt_store_append_denial_input_missing",
    "operator_observation_input_missing",
    "freshness_window_input_missing",
    "live_runtime_witness_forbidden",
    "runtime_admission_forbidden",
    "terminal_closure_not_allowed",
)

REQUIRED_EVIDENCE_REFS: tuple[str, ...] = (
    "schemas/universal_symbol_runtime_live_witness_input_receipt.schema.json",
    "examples/universal_symbol_runtime_live_witness_input_receipt.foundation.json",
    "schemas/universal_symbol_runtime_admission_evidence_receipt.schema.json",
    "examples/universal_symbol_runtime_admission_evidence_receipt.foundation.json",
    "schemas/universal_symbol_runtime_admission_policy.schema.json",
    "examples/universal_symbol_runtime_admission_policy.foundation.json",
    "schemas/universal_symbol_runtime_authority_read_model.schema.json",
    "examples/universal_symbol_runtime_authority_read_model.foundation.json",
    "schemas/universal_symbol_runtime_authority_witness.schema.json",
    "examples/universal_symbol_runtime_authority_witness.foundation.json",
    "schemas/universal_symbol_receipt_store_authority_witness.schema.json",
    "examples/universal_symbol_receipt_store_authority_witness.foundation.json",
    "schemas/universal_symbol.schema.json",
    "docs/91_universal_symbol_kernel.md",
    "docs/92_universal_symbol_kernel_audit.md",
    "scripts/produce_universal_symbol_runtime_live_witness_input_receipt.py",
    "scripts/validate_universal_symbol_runtime_live_witness_input_receipt.py",
    "scripts/validate_universal_symbol_runtime_admission_evidence_receipt.py",
    "scripts/validate_universal_symbol_runtime_authority_read_model.py",
    "scripts/proof_coverage_matrix.py",
    "tests/test_produce_universal_symbol_runtime_live_witness_input_receipt.py",
    "tests/test_validate_universal_symbol_kernel.py",
    "tests/test_proof_coverage_matrix.py",
)


class UniversalSymbolRuntimeLiveWitnessInputReceiptError(ValueError):
    """Raised when the live witness input receipt violates Foundation Mode."""


def load_json_object(path: Path) -> dict[str, Any]:
    """Return a JSON object or raise a validation error with causal context."""

    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise UniversalSymbolRuntimeLiveWitnessInputReceiptError(f"missing file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise UniversalSymbolRuntimeLiveWitnessInputReceiptError(f"invalid json: {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise UniversalSymbolRuntimeLiveWitnessInputReceiptError(f"expected object: {path}")
    return value


def validate_universal_symbol_runtime_live_witness_input_receipt(
    receipt_path: Path = DEFAULT_RECEIPT_PATH,
    schema_path: Path = DEFAULT_SCHEMA_PATH,
) -> dict[str, Any]:
    """Validate schema shape, input blockers, and denied authority."""

    schema = load_json_object(schema_path)
    receipt = load_json_object(receipt_path)
    errors: list[str] = []

    _validate_schema_boundary(schema, errors)
    _validate_json_schema(receipt, schema, errors)
    _validate_receipt_boundary(receipt, errors)
    _validate_input_subject(receipt, errors)
    _validate_input_channels(receipt, errors)
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
        "input_receipt_decision": receipt.get("input_receipt_decision", ""),
        "input_channel_count": _list_len(receipt.get("required_input_channels")) or 0,
        "authority_denial_count": len(AUTHORITY_DENIAL_FIELDS),
        "consistency_constraint_count": len(CONSISTENCY_CONSTRAINT_TRUE_FIELDS),
        "evidence_ref_count": _list_len(receipt.get("evidence_refs")) or 0,
        "errors": errors,
    }
    if errors:
        raise UniversalSymbolRuntimeLiveWitnessInputReceiptError("; ".join(errors))
    return result


def _validate_schema_boundary(schema: Mapping[str, Any], errors: list[str]) -> None:
    if schema.get("$id") != "urn:mullusi:schema:universal-symbol-runtime-live-witness-input-receipt:1":
        errors.append("schema id drift")
    if schema.get("additionalProperties") is not False:
        errors.append("schema must reject additional properties")
    required = schema.get("required")
    if not isinstance(required, list) or "required_input_channels" not in required:
        errors.append("schema must require required_input_channels")


def _validate_json_schema(receipt: Mapping[str, Any], schema: Mapping[str, Any], errors: list[str]) -> None:
    if jsonschema is None:
        errors.append("jsonschema dependency missing")
        return
    validator = jsonschema.Draft202012Validator(schema, format_checker=jsonschema.FormatChecker())
    for error in sorted(validator.iter_errors(receipt), key=lambda item: tuple(item.path)):
        path = ".".join(str(part) for part in error.absolute_path) or "$"
        errors.append(f"schema validation failed at {path}: {error.message}")


def _validate_receipt_boundary(receipt: Mapping[str, Any], errors: list[str]) -> None:
    if receipt.get("foundation_mode") is not True:
        errors.append("foundation_mode must remain true")
    if receipt.get("solver_outcome") != "AwaitingEvidence":
        errors.append("solver_outcome must remain AwaitingEvidence")
    if receipt.get("input_receipt_decision") != (
        "blocked_pending_live_endpoint_process_probe_dry_run_no_effect_receipt_denial_operator_and_freshness_inputs"
    ):
        errors.append("input_receipt_decision must remain blocked")
    if receipt.get("receipt_is_not_runtime_authority") is not True:
        errors.append("receipt must not be runtime authority")


def _validate_input_subject(receipt: Mapping[str, Any], errors: list[str]) -> None:
    subject = receipt.get("input_subject")
    if not isinstance(subject, dict):
        errors.append("input_subject must be object")
        return
    expected = {
        "runtime_admission_evidence_receipt_ref": "schemas/universal_symbol_runtime_admission_evidence_receipt.schema.json",
        "runtime_admission_policy_ref": "schemas/universal_symbol_runtime_admission_policy.schema.json",
        "runtime_authority_read_model_ref": "schemas/universal_symbol_runtime_authority_read_model.schema.json",
        "input_scope": "runtime-live-witness-inputs-only",
    }
    for field, value in expected.items():
        if subject.get(field) != value:
            errors.append(f"input_subject {field} drift")


def _validate_input_channels(receipt: Mapping[str, Any], errors: list[str]) -> None:
    channels = receipt.get("required_input_channels")
    if not isinstance(channels, list):
        errors.append("required_input_channels must be list")
        return
    kinds = {channel.get("input_kind") for channel in channels if isinstance(channel, dict)}
    for kind in REQUIRED_INPUT_KINDS:
        if kind not in kinds:
            errors.append(f"missing input kind: {kind}")
    for channel in channels:
        if not isinstance(channel, dict):
            errors.append("input channel must be object")
            continue
        if channel.get("current_decision") != "live_runtime_witness_blocked":
            errors.append(f"input channel {channel.get('input_id', '<unknown>')} must remain blocked")
        if channel.get("proof_state") not in {"Unknown", "BudgetUnknown", "Fail"}:
            errors.append(f"input channel {channel.get('input_id', '<unknown>')} proof_state must block")
        delta_reject_ref = channel.get("delta_reject_ref")
        if not isinstance(delta_reject_ref, str) or not delta_reject_ref.startswith("delta-reject://"):
            errors.append(f"input channel {channel.get('input_id', '<unknown>')} delta_reject_ref drift")


def _validate_consistency_constraints(receipt: Mapping[str, Any], errors: list[str]) -> None:
    constraints = receipt.get("input_consistency_constraints")
    if not isinstance(constraints, dict):
        errors.append("input_consistency_constraints must be object")
        return
    for field in CONSISTENCY_CONSTRAINT_TRUE_FIELDS:
        if constraints.get(field) is not True:
            errors.append(f"{field} must remain true")


def _validate_authority_denials(receipt: Mapping[str, Any], errors: list[str]) -> None:
    denials = receipt.get("authority_denials")
    if not isinstance(denials, dict):
        errors.append("authority_denials must be object")
        return
    for field in AUTHORITY_DENIAL_FIELDS:
        if denials.get(field) is not False:
            errors.append(f"{field} must remain denied")


def _validate_rejection_policy(receipt: Mapping[str, Any], errors: list[str]) -> None:
    policy = receipt.get("rejection_policy")
    if not isinstance(policy, dict):
        errors.append("rejection_policy must be object")
        return
    for field in REJECTION_POLICY_TRUE_FIELDS:
        if policy.get(field) is not True:
            errors.append(f"{field} must remain true")


def _validate_blocked_reasons(receipt: Mapping[str, Any], errors: list[str]) -> None:
    reasons = receipt.get("blocked_reasons")
    if not isinstance(reasons, list):
        errors.append("blocked_reasons must be list")
        return
    for reason in REQUIRED_BLOCKED_REASONS:
        if reason not in reasons:
            errors.append(f"missing blocked reason: {reason}")


def _validate_contract_summary(receipt: Mapping[str, Any], errors: list[str]) -> None:
    summary = receipt.get("contract_summary")
    if not isinstance(summary, dict):
        errors.append("contract_summary must be object")
        return
    expected = {
        "input_channel_count": _list_len(receipt.get("required_input_channels")),
        "consistency_constraint_count": len(CONSISTENCY_CONSTRAINT_TRUE_FIELDS),
        "authority_denial_count": len(AUTHORITY_DENIAL_FIELDS),
        "rejection_check_count": len(REJECTION_POLICY_TRUE_FIELDS),
        "blocked_reason_count": _list_len(receipt.get("blocked_reasons")),
        "evidence_ref_count": _list_len(receipt.get("evidence_refs")),
    }
    for field, value in expected.items():
        if value is not None and summary.get(field) != value:
            errors.append(f"{field} drift")


def _validate_evidence_refs(receipt: Mapping[str, Any], errors: list[str]) -> None:
    refs = receipt.get("evidence_refs")
    if not isinstance(refs, list):
        errors.append("evidence_refs must be list")
        return
    for ref in REQUIRED_EVIDENCE_REFS:
        if ref not in refs:
            errors.append(f"missing evidence ref: {ref}")


def _validate_evidence_ref_files(receipt: Mapping[str, Any], errors: list[str]) -> None:
    refs = receipt.get("evidence_refs")
    if not isinstance(refs, list):
        return
    for ref in refs:
        if isinstance(ref, str) and ref.startswith(("schemas/", "examples/", "docs/", "scripts/", "tests/")):
            if not (REPO_ROOT / ref).exists():
                errors.append(f"evidence ref missing file: {ref}")


def _repo_relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def _list_len(value: object) -> int | None:
    return len(value) if isinstance(value, list) else None


def main(argv: list[str] | None = None) -> int:
    """Validate the runtime live witness input receipt and print status."""

    parser = argparse.ArgumentParser(description="Validate Universal Symbol runtime live witness input receipt.")
    parser.add_argument("--receipt", type=Path, default=DEFAULT_RECEIPT_PATH)
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA_PATH)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        report = validate_universal_symbol_runtime_live_witness_input_receipt(args.receipt, args.schema)
    except UniversalSymbolRuntimeLiveWitnessInputReceiptError as exc:
        if args.json:
            print(json.dumps({"valid": False, "errors": str(exc).split("; ")}, indent=2, sort_keys=True))
        else:
            print(f"[FAIL] universal_symbol_runtime_live_witness_input_receipt: {exc}")
            print("STATUS: failed")
        return 1
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0
    print("[PASS] universal_symbol_runtime_live_witness_input_receipt")
    print("STATUS: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
