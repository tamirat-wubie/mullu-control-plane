#!/usr/bin/env python3
"""Validate the writer duty scope witness operator read model.

Purpose: prove the writer duty scope operator projection is read-only and
bounded while duty binding, receipt-store append, raw payload exposure,
mutation, and terminal closure remain denied.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: writer duty scope read-model schema/example and writer duty
scope witness validator constants.
Invariants:
  - The read model is a projection, not duty authority.
  - Every duty requirement appears exactly once.
  - Raw detail visibility and authority remain denied per row.
  - Delta_reject logging remains visible as bounded status only.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Mapping

try:
    import jsonschema
except ImportError:  # pragma: no cover - dependency is expected in CI/dev envs.
    jsonschema = None


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validate_universal_symbol_receipt_store_writer_duty_scope_witness import (  # noqa: E402
    AUTHORITY_DENIAL_FIELDS,
    DEFAULT_WITNESS_PATH as DEFAULT_WRITER_DUTY_SCOPE_WITNESS_PATH,
    REQUIRED_BLOCKED_REASONS,
    REQUIRED_REQUIREMENT_IDS,
)


DEFAULT_SCHEMA_PATH = (
    REPO_ROOT / "schemas" / "universal_symbol_receipt_store_writer_duty_scope_read_model.schema.json"
)
DEFAULT_READ_MODEL_PATH = (
    REPO_ROOT / "examples" / "universal_symbol_receipt_store_writer_duty_scope_read_model.foundation.json"
)

EXPECTED_WITNESS_REF = "examples/universal_symbol_receipt_store_writer_duty_scope_witness.foundation.json"
EXPECTED_WRITER_DUTY_SCOPE_DECISION = "blocked_pending_writer_role_action_bounds_and_separation_evidence"

READ_MODEL_CONSTRAINT_TRUE_FIELDS: tuple[str, ...] = (
    "read_only_projection",
    "no_state_mutation",
    "no_receipt_store_append",
    "no_raw_payload",
    "no_raw_secret",
    "no_writer_duty_scope_binding",
    "no_terminal_closure",
)

REQUIRED_EVIDENCE_REFS: tuple[str, ...] = (
    "schemas/universal_symbol_receipt_store_writer_duty_scope_read_model.schema.json",
    "examples/universal_symbol_receipt_store_writer_duty_scope_read_model.foundation.json",
    "schemas/universal_symbol_receipt_store_writer_duty_scope_witness.schema.json",
    "examples/universal_symbol_receipt_store_writer_duty_scope_witness.foundation.json",
    "scripts/validate_universal_symbol_receipt_store_writer_duty_scope_read_model.py",
    "scripts/validate_universal_symbol_receipt_store_writer_duty_scope_witness.py",
    "tests/test_validate_universal_symbol_receipt_store_writer_duty_scope_read_model.py",
    "tests/test_validate_universal_symbol_kernel.py",
    "scripts/proof_coverage_matrix.py",
    "tests/test_proof_coverage_matrix.py",
)

EXPECTED_OPERATOR_STATUS_SUMMARY: dict[str, str] = {
    "primary_status": "Writer duty scope blocked",
    "role_status": "Awaiting evidence",
    "scope_status": "Awaiting evidence",
    "raw_detail_visibility": "hidden_by_default",
    "operator_action": "Collect writer role, action bounds, and separation evidence",
}


class UniversalSymbolReceiptStoreWriterDutyScopeReadModelError(ValueError):
    """Raised when the writer duty scope read model violates Foundation Mode."""


def validate_universal_symbol_receipt_store_writer_duty_scope_read_model(
    read_model_path: Path = DEFAULT_READ_MODEL_PATH,
    schema_path: Path = DEFAULT_SCHEMA_PATH,
) -> dict[str, Any]:
    """Validate schema shape, bounded rows, and denied duty authority."""

    schema = load_json_object(schema_path)
    read_model = load_json_object(read_model_path)
    errors: list[str] = []

    _validate_schema_boundary(schema, errors)
    _validate_json_schema(read_model, schema, errors)
    _validate_read_model_boundary(read_model, errors)
    _validate_operator_status_summary(read_model, errors)
    _validate_witness_projection(read_model, errors)
    _validate_source_witness_alignment(read_model, errors)
    _validate_requirement_rows(read_model, errors)
    _validate_effective_denials(read_model, errors)
    _validate_read_model_constraints(read_model, errors)
    _validate_contract_summary(read_model, errors)
    _validate_evidence_refs(read_model, errors)
    _validate_evidence_ref_files(read_model, errors)

    report = {
        "read_model_path": _repo_relative(read_model_path),
        "schema_path": _repo_relative(schema_path),
        "valid": not errors,
        "read_model_id": read_model.get("read_model_id", ""),
        "solver_outcome": read_model.get("solver_outcome", ""),
        "primary_status": _mapping(read_model.get("operator_status_summary")).get("primary_status", ""),
        "requirement_row_count": _list_len(read_model.get("requirement_rows")) or 0,
        "effective_denial_count": len(AUTHORITY_DENIAL_FIELDS),
        "read_model_constraint_count": len(READ_MODEL_CONSTRAINT_TRUE_FIELDS),
        "evidence_ref_count": _list_len(read_model.get("evidence_refs")) or 0,
        "errors": errors,
    }
    if errors:
        raise UniversalSymbolReceiptStoreWriterDutyScopeReadModelError("; ".join(errors))
    return report


def load_json_object(path: Path) -> dict[str, Any]:
    """Return a JSON object or raise a validation error with causal context."""

    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise UniversalSymbolReceiptStoreWriterDutyScopeReadModelError(f"missing file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise UniversalSymbolReceiptStoreWriterDutyScopeReadModelError(f"invalid json: {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise UniversalSymbolReceiptStoreWriterDutyScopeReadModelError(f"expected object: {path}")
    return value


def _validate_schema_boundary(schema: Mapping[str, Any], errors: list[str]) -> None:
    expected_id = "urn:mullusi:schema:universal-symbol-receipt-store-writer-duty-scope-read-model:1"
    if schema.get("$id") != expected_id:
        errors.append("schema id drift")
    if schema.get("additionalProperties") is not False:
        errors.append("schema must reject additional properties")
    required = schema.get("required")
    if not isinstance(required, list) or "effective_denials" not in required:
        errors.append("schema must require effective_denials")


def _validate_json_schema(read_model: Mapping[str, Any], schema: Mapping[str, Any], errors: list[str]) -> None:
    if jsonschema is None:
        errors.append("jsonschema dependency missing")
        return
    validator = jsonschema.Draft202012Validator(schema, format_checker=jsonschema.FormatChecker())
    schema_errors = sorted(validator.iter_errors(read_model), key=lambda error: tuple(error.path))
    for error in schema_errors:
        path = ".".join(str(part) for part in error.absolute_path) or "$"
        errors.append(f"schema validation failed at {path}: {error.message}")


def _validate_read_model_boundary(read_model: Mapping[str, Any], errors: list[str]) -> None:
    if read_model.get("foundation_mode") is not True:
        errors.append("foundation_mode must remain true")
    if read_model.get("solver_outcome") != "AwaitingEvidence":
        errors.append("solver_outcome must remain AwaitingEvidence")
    if read_model.get("read_model_is_not_duty_authority") is not True:
        errors.append("read model must not be duty authority")


def _validate_operator_status_summary(read_model: Mapping[str, Any], errors: list[str]) -> None:
    summary = _mapping(read_model.get("operator_status_summary"))
    for field_name, expected_value in EXPECTED_OPERATOR_STATUS_SUMMARY.items():
        if summary.get(field_name) != expected_value:
            errors.append(f"operator_status_summary.{field_name} drift")


def _validate_witness_projection(read_model: Mapping[str, Any], errors: list[str]) -> None:
    projection = _mapping(read_model.get("witness_projection"))
    if projection.get("witness_ref") != EXPECTED_WITNESS_REF:
        errors.append("witness_projection.witness_ref drift")
    if projection.get("writer_duty_scope_decision") != EXPECTED_WRITER_DUTY_SCOPE_DECISION:
        errors.append("witness_projection.writer_duty_scope_decision must remain blocked")
    if projection.get("authority_granted") is not False:
        errors.append("witness_projection.authority_granted must remain false")
    if projection.get("duty_requirement_count") != len(REQUIRED_REQUIREMENT_IDS):
        errors.append("witness_projection.duty_requirement_count drift")
    if projection.get("blocked_reason_count") != len(REQUIRED_BLOCKED_REASONS):
        errors.append("witness_projection.blocked_reason_count drift")


def _validate_source_witness_alignment(read_model: Mapping[str, Any], errors: list[str]) -> None:
    projection = _mapping(read_model.get("witness_projection"))
    if projection.get("witness_ref") != EXPECTED_WITNESS_REF:
        return
    try:
        witness = load_json_object(DEFAULT_WRITER_DUTY_SCOPE_WITNESS_PATH)
    except UniversalSymbolReceiptStoreWriterDutyScopeReadModelError as exc:
        errors.append(f"source writer duty scope witness unavailable: {exc}")
        return

    witness_summary = _mapping(witness.get("contract_summary"))
    expected_counts = {
        "duty_requirement_count": witness_summary.get("duty_requirement_count"),
        "blocked_reason_count": witness_summary.get("blocked_reason_count"),
    }
    for field_name, expected_count in expected_counts.items():
        if projection.get(field_name) != expected_count:
            errors.append(f"witness_projection.{field_name} must match source writer duty scope witness")
    if projection.get("writer_duty_scope_decision") != witness.get("writer_duty_scope_decision"):
        errors.append("witness_projection.writer_duty_scope_decision must match source writer duty scope witness")


def _validate_requirement_rows(read_model: Mapping[str, Any], errors: list[str]) -> None:
    rows = read_model.get("requirement_rows")
    if not isinstance(rows, list) or not rows:
        errors.append("requirement_rows must be non-empty")
        return
    requirement_ids: list[str] = []
    for row in rows:
        if not isinstance(row, Mapping):
            errors.append("requirement_rows must contain objects")
            continue
        requirement_ids.append(str(row.get("requirement_id", "")))
        if row.get("proof_state") not in {"Unknown", "BudgetUnknown", "Fail"}:
            errors.append(f"{row.get('requirement_id')}: proof_state must block writer duty scope")
        if row.get("delta_reject_logged") is not True:
            errors.append(f"{row.get('requirement_id')}: delta_reject_logged must remain true")
        if row.get("raw_detail_visible") is not False:
            errors.append(f"{row.get('requirement_id')}: raw_detail_visible must remain false")
        if row.get("authority_granted") is not False:
            errors.append(f"{row.get('requirement_id')}: authority_granted must remain false")
    _require_members("requirement_rows", requirement_ids, REQUIRED_REQUIREMENT_IDS, errors)


def _validate_effective_denials(read_model: Mapping[str, Any], errors: list[str]) -> None:
    denials = _mapping(read_model.get("effective_denials"))
    for field_name in AUTHORITY_DENIAL_FIELDS:
        if denials.get(field_name) is not False:
            errors.append(f"effective_denials.{field_name} must remain false")


def _validate_read_model_constraints(read_model: Mapping[str, Any], errors: list[str]) -> None:
    constraints = _mapping(read_model.get("read_model_constraints"))
    for field_name in READ_MODEL_CONSTRAINT_TRUE_FIELDS:
        if constraints.get(field_name) is not True:
            errors.append(f"read_model_constraints.{field_name} must remain true")


def _validate_contract_summary(read_model: Mapping[str, Any], errors: list[str]) -> None:
    summary = _mapping(read_model.get("contract_summary"))
    rows = _list_of_mappings(read_model.get("requirement_rows"))
    observed_counts = {
        "requirement_row_count": len(rows),
        "effective_denial_count": len(AUTHORITY_DENIAL_FIELDS),
        "read_model_constraint_count": len(READ_MODEL_CONSTRAINT_TRUE_FIELDS),
        "evidence_ref_count": _list_len(read_model.get("evidence_refs")),
    }
    for field_name, observed_count in observed_counts.items():
        if observed_count is not None and summary.get(field_name) != observed_count:
            errors.append(f"{field_name} drift")


def _validate_evidence_refs(read_model: Mapping[str, Any], errors: list[str]) -> None:
    refs = read_model.get("evidence_refs")
    if not isinstance(refs, list):
        errors.append("evidence_refs must be a list")
        return
    missing = tuple(ref for ref in REQUIRED_EVIDENCE_REFS if ref not in refs)
    if missing:
        errors.append("missing required evidence refs: " + ", ".join(missing))


def _validate_evidence_ref_files(read_model: Mapping[str, Any], errors: list[str]) -> None:
    refs = read_model.get("evidence_refs")
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


def _list_of_mappings(value: Any) -> list[Mapping[str, Any]]:
    return [item for item in value if isinstance(item, Mapping)] if isinstance(value, list) else []


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
    parser.add_argument("--read-model", type=Path, default=DEFAULT_READ_MODEL_PATH)
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA_PATH)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    try:
        report = validate_universal_symbol_receipt_store_writer_duty_scope_read_model(
            args.read_model,
            args.schema,
        )
    except UniversalSymbolReceiptStoreWriterDutyScopeReadModelError as exc:
        if args.json:
            print(json.dumps({"valid": False, "errors": str(exc).split("; ")}, indent=2, sort_keys=True))
        else:
            print(f"[FAIL] universal_symbol_receipt_store_writer_duty_scope_read_model: {exc}")
            print("STATUS: failed")
        return 1

    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print("[PASS] universal_symbol_receipt_store_writer_duty_scope_read_model")
        print("STATUS: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
