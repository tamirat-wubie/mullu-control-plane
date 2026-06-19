"""Validate the Universal Symbol runtime authority read model.

Purpose: prove the runtime authority operator projection is read-only and
shows simple status while runtime authority, dispatch, connector calls,
receipt-store append, mutation, and terminal closure remain denied.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: runtime authority read-model schema/example, runtime admission
policy, runtime authority witness, receipt-store authority witness, docs, and
tests.
Invariants:
  - The read model does not grant runtime authority.
  - Operator-facing status stays simple and audit details are hidden by default.
  - Every projected authority link blocks activation.
  - The read model performs no dispatch, append, connector call, or mutation.
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
DEFAULT_SCHEMA_PATH = REPO_ROOT / "schemas" / "universal_symbol_runtime_authority_read_model.schema.json"
DEFAULT_READ_MODEL_PATH = REPO_ROOT / "examples" / "universal_symbol_runtime_authority_read_model.foundation.json"

EFFECTIVE_DENIAL_FIELDS: tuple[str, ...] = (
    "runtime_authority_granted",
    "runtime_registration_performed",
    "live_dispatch_enabled",
    "connector_call_enabled",
    "filesystem_write_enabled",
    "external_write_enabled",
    "receipt_store_append_enabled",
    "state_mutation_performed",
    "terminal_closure_allowed",
    "production_readiness_claimed",
)

READ_MODEL_CONSTRAINT_TRUE_FIELDS: tuple[str, ...] = (
    "read_only_projection",
    "no_state_mutation",
    "no_connector_call",
    "no_runtime_dispatch",
    "no_receipt_store_append",
    "no_raw_payload",
    "no_raw_secret",
    "audit_details_hidden_by_default",
    "audit_details_link_allowed",
)

REQUIRED_LINK_IDS: tuple[str, ...] = (
    "runtime-authority-read-model://runtime-admission-policy",
    "runtime-authority-read-model://runtime-authority-witness",
    "runtime-authority-read-model://receipt-store-authority",
    "runtime-authority-read-model://operator-approval",
    "runtime-authority-read-model://lifecycle-evidence",
    "runtime-authority-read-model://lifecycle-audit",
    "runtime-authority-read-model://rollback-recovery",
    "runtime-authority-read-model://proof-coverage",
)

REQUIRED_EVIDENCE_REFS: tuple[str, ...] = (
    "schemas/universal_symbol_runtime_authority_read_model.schema.json",
    "examples/universal_symbol_runtime_authority_read_model.foundation.json",
    "schemas/universal_symbol_runtime_admission_policy.schema.json",
    "examples/universal_symbol_runtime_admission_policy.foundation.json",
    "schemas/universal_symbol_runtime_authority_witness.schema.json",
    "examples/universal_symbol_runtime_authority_witness.foundation.json",
    "schemas/universal_symbol_receipt_store_authority_witness.schema.json",
    "examples/universal_symbol_receipt_store_authority_witness.foundation.json",
    "schemas/universal_symbol_receipt_store_operator_approval_witness.schema.json",
    "examples/universal_symbol_receipt_store_operator_approval_witness.foundation.json",
    "schemas/universal_symbol_receipt_store_lifecycle_evidence_receipt.schema.json",
    "examples/universal_symbol_receipt_store_lifecycle_evidence_receipt.foundation.json",
    "schemas/universal_symbol_receipt_store_lifecycle_audit_receipt.schema.json",
    "examples/universal_symbol_receipt_store_lifecycle_audit_receipt.foundation.json",
    "schemas/universal_symbol_receipt_store_recovery_witness.schema.json",
    "examples/universal_symbol_receipt_store_recovery_witness.foundation.json",
    "schemas/universal_symbol.schema.json",
    "docs/91_universal_symbol_kernel.md",
    "docs/92_universal_symbol_kernel_audit.md",
    "scripts/validate_universal_symbol_runtime_authority_read_model.py",
    "scripts/proof_coverage_matrix.py",
    "tests/test_validate_universal_symbol_kernel.py",
    "tests/test_proof_coverage_matrix.py",
)


class UniversalSymbolRuntimeAuthorityReadModelError(ValueError):
    """Raised when the runtime authority read model violates Foundation Mode."""


def load_json_object(path: Path) -> dict[str, Any]:
    """Return a JSON object or raise a validation error with causal context."""

    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise UniversalSymbolRuntimeAuthorityReadModelError(f"missing file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise UniversalSymbolRuntimeAuthorityReadModelError(f"invalid json: {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise UniversalSymbolRuntimeAuthorityReadModelError(f"expected object: {path}")
    return value


def validate_universal_symbol_runtime_authority_read_model(
    read_model_path: Path = DEFAULT_READ_MODEL_PATH,
    schema_path: Path = DEFAULT_SCHEMA_PATH,
) -> dict[str, Any]:
    """Validate schema shape, read-only projection, and denied authority."""

    schema = load_json_object(schema_path)
    read_model = load_json_object(read_model_path)
    errors: list[str] = []

    _validate_schema_boundary(schema, errors)
    _validate_json_schema(read_model, schema, errors)
    _validate_read_model_boundary(read_model, errors)
    _validate_operator_status_summary(read_model, errors)
    _validate_authority_chain_projection(read_model, errors)
    _validate_effective_denials(read_model, errors)
    _validate_read_model_constraints(read_model, errors)
    _validate_contract_summary(read_model, errors)
    _validate_evidence_refs(read_model, errors)
    _validate_evidence_ref_files(read_model, errors)

    result = {
        "read_model_path": _repo_relative(read_model_path),
        "schema_path": _repo_relative(schema_path),
        "valid": not errors,
        "read_model_id": read_model.get("read_model_id", ""),
        "solver_outcome": read_model.get("solver_outcome", ""),
        "primary_status": _mapping(read_model.get("operator_status_summary")).get("primary_status", ""),
        "authority_chain_projection_count": _list_len(read_model.get("authority_chain_projection")) or 0,
        "effective_denial_count": len(EFFECTIVE_DENIAL_FIELDS),
        "read_model_constraint_count": len(READ_MODEL_CONSTRAINT_TRUE_FIELDS),
        "evidence_ref_count": _list_len(read_model.get("evidence_refs")) or 0,
        "errors": errors,
    }
    if errors:
        raise UniversalSymbolRuntimeAuthorityReadModelError("; ".join(errors))
    return result


def _validate_schema_boundary(schema: Mapping[str, Any], errors: list[str]) -> None:
    if schema.get("$id") != "urn:mullusi:schema:universal-symbol-runtime-authority-read-model:1":
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
    if read_model.get("read_model_is_not_runtime_authority") is not True:
        errors.append("read model must not be runtime authority")


def _validate_operator_status_summary(read_model: Mapping[str, Any], errors: list[str]) -> None:
    summary = _mapping(read_model.get("operator_status_summary"))
    expected_values = {
        "primary_status": "Blocked for safety",
        "approval_status": "Needs approval",
        "dispatch_status": "Not active",
        "receipt_store_status": "Evidence saved",
        "audit_detail_visibility": "hidden_by_default",
    }
    for field_name, expected_value in expected_values.items():
        if summary.get(field_name) != expected_value:
            errors.append(f"operator_status_summary.{field_name} drift")


def _validate_authority_chain_projection(read_model: Mapping[str, Any], errors: list[str]) -> None:
    projection = read_model.get("authority_chain_projection")
    if not isinstance(projection, list) or not projection:
        errors.append("authority_chain_projection must be non-empty")
        return
    link_ids: list[str] = []
    for link in projection:
        if not isinstance(link, dict):
            errors.append("authority chain projection entries must be objects")
            continue
        link_ids.append(str(link.get("link_id")))
        if link.get("proof_state") not in {"Unknown", "BudgetUnknown", "Fail"}:
            errors.append(f"{link.get('link_id')}: proof_state must block activation")
        if link.get("activation_allowed") is not False:
            errors.append(f"{link.get('link_id')}: activation_allowed must remain false")
    _require_members("authority_chain_projection", link_ids, REQUIRED_LINK_IDS, errors)


def _validate_effective_denials(read_model: Mapping[str, Any], errors: list[str]) -> None:
    denials = _mapping(read_model.get("effective_denials"))
    for field_name in EFFECTIVE_DENIAL_FIELDS:
        if denials.get(field_name) is not False:
            errors.append(f"effective_denials.{field_name} must remain false")


def _validate_read_model_constraints(read_model: Mapping[str, Any], errors: list[str]) -> None:
    constraints = _mapping(read_model.get("read_model_constraints"))
    for field_name in READ_MODEL_CONSTRAINT_TRUE_FIELDS:
        if constraints.get(field_name) is not True:
            errors.append(f"read_model_constraints.{field_name} must remain true")


def _validate_contract_summary(read_model: Mapping[str, Any], errors: list[str]) -> None:
    summary = _mapping(read_model.get("contract_summary"))
    observed_counts = {
        "authority_chain_projection_count": _list_len(read_model.get("authority_chain_projection")),
        "effective_denial_count": len(EFFECTIVE_DENIAL_FIELDS),
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
        report = validate_universal_symbol_runtime_authority_read_model(args.read_model, args.schema)
    except UniversalSymbolRuntimeAuthorityReadModelError as exc:
        if args.json:
            print(json.dumps({"valid": False, "errors": str(exc).split("; ")}, indent=2, sort_keys=True))
        else:
            print(f"[FAIL] universal_symbol_runtime_authority_read_model: {exc}")
            print("STATUS: failed")
        return 1

    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print("[PASS] universal_symbol_runtime_authority_read_model")
        print("STATUS: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
