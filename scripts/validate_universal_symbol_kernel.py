"""Validate the Universal Symbol Kernel foundation contract.

Purpose: enforce the first platform-wide symbol-native boundary without granting
runtime authority.
Governance scope: identity, boundary, metadata, relations, causality, lineage,
governance, proof, skill projection, authority denial, and evidence references.
Invariants:
  - Everything-symbolizable is a contract flag, not execution authority.
  - Raw private payloads and raw secrets are never admitted.
  - Connector calls, external writes, filesystem writes, runtime dispatch,
    state mutation, terminal closure, and success claims remain denied.
  - The foundation example must satisfy the canonical JSON Schema and carry
    evidence refs for schema, example, docs, validator, and tests.
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
DEFAULT_SCHEMA_PATH = REPO_ROOT / "schemas" / "universal_symbol.schema.json"
DEFAULT_SYMBOL_PATH = REPO_ROOT / "examples" / "universal_symbol_kernel.foundation.json"

AUTHORITY_DENIAL_FIELDS: tuple[str, ...] = (
    "raw_private_payload_stored",
    "raw_secret_value_stored",
    "connector_call_performed",
    "external_write_performed",
    "filesystem_write_performed",
    "runtime_dispatch_performed",
    "state_mutation_performed",
    "terminal_closure_allowed",
    "success_claim_allowed",
)

REQUIRED_EVIDENCE_REFS: tuple[str, ...] = (
    "schemas/universal_symbol.schema.json",
    "schemas/universal_symbol_adapter_receipt_persistence_policy.schema.json",
    "schemas/universal_symbol_append_audit_witness.schema.json",
    "schemas/universal_symbol_receipt_store_operator_approval_witness.schema.json",
    "schemas/universal_symbol_receipt_store_operator_identity_witness.schema.json",
    "schemas/universal_symbol_receipt_store_operator_approval_decision_witness.schema.json",
    "schemas/universal_symbol_receipt_store_reapproval_revocation_witness.schema.json",
    "schemas/universal_symbol_receipt_store_tenant_scope_witness.schema.json",
    "schemas/universal_symbol_receipt_store_writer_duty_scope_witness.schema.json",
    "schemas/universal_symbol_receipt_store_path_confinement_witness.schema.json",
    "schemas/universal_symbol_receipt_store_write_path_idempotency_witness.schema.json",
    "schemas/universal_symbol_receipt_store_durability_replay_witness.schema.json",
    "schemas/universal_symbol_receipt_store_recovery_witness.schema.json",
    "schemas/universal_symbol_receipt_store_path_custody_witness.schema.json",
    "schemas/universal_symbol_receipt_store_writer_identity_witness.schema.json",
    "schemas/universal_symbol_receipt_store_writer_registration_witness.schema.json",
    "schemas/universal_symbol_receipt_store_write_path_witness.schema.json",
    "schemas/universal_symbol_receipt_store_authority_witness.schema.json",
    "schemas/universal_symbol_runtime_admission_policy.schema.json",
    "examples/universal_symbol_kernel.foundation.json",
    "examples/universal_symbol_adapter_receipt_persistence_policy.foundation.json",
    "examples/universal_symbol_append_audit_witness.foundation.json",
    "examples/universal_symbol_receipt_store_operator_approval_witness.foundation.json",
    "examples/universal_symbol_receipt_store_operator_identity_witness.foundation.json",
    "examples/universal_symbol_receipt_store_operator_approval_decision_witness.foundation.json",
    "examples/universal_symbol_receipt_store_reapproval_revocation_witness.foundation.json",
    "examples/universal_symbol_receipt_store_tenant_scope_witness.foundation.json",
    "examples/universal_symbol_receipt_store_writer_duty_scope_witness.foundation.json",
    "examples/universal_symbol_receipt_store_path_confinement_witness.foundation.json",
    "examples/universal_symbol_receipt_store_write_path_idempotency_witness.foundation.json",
    "examples/universal_symbol_receipt_store_durability_replay_witness.foundation.json",
    "examples/universal_symbol_receipt_store_recovery_witness.foundation.json",
    "examples/universal_symbol_receipt_store_path_custody_witness.foundation.json",
    "examples/universal_symbol_receipt_store_writer_identity_witness.foundation.json",
    "examples/universal_symbol_receipt_store_writer_registration_witness.foundation.json",
    "examples/universal_symbol_receipt_store_write_path_witness.foundation.json",
    "examples/universal_symbol_receipt_store_authority_witness.foundation.json",
    "examples/universal_symbol_runtime_admission_policy.foundation.json",
    "docs/40_proof_coverage_matrix.md",
    "docs/91_universal_symbol_kernel.md",
    "docs/92_universal_symbol_kernel_audit.md",
    "mcoi/mcoi_runtime/core/symbol_skill_adapter.py",
    "mcoi/mcoi_runtime/app/symbol_operator_read_models.py",
    "mcoi/mcoi_runtime/app/software_receipt_observability.py",
    "mcoi/mcoi_runtime/app/routers/components.py",
    "mcoi/tests/test_symbol_skill_adapter.py",
    "mcoi/tests/test_symbol_operator_read_models.py",
    "mcoi/tests/test_software_receipt_observability.py",
    "scripts/proof_coverage_matrix.py",
    "scripts/validate_universal_symbol_adapter_receipt_persistence_policy.py",
    "scripts/validate_universal_symbol_append_audit_witness.py",
    "scripts/validate_universal_symbol_kernel.py",
    "scripts/validate_universal_symbol_receipt_store_operator_approval_witness.py",
    "scripts/validate_universal_symbol_receipt_store_operator_identity_witness.py",
    "scripts/validate_universal_symbol_receipt_store_operator_approval_decision_witness.py",
    "scripts/validate_universal_symbol_receipt_store_reapproval_revocation_witness.py",
    "scripts/validate_universal_symbol_receipt_store_tenant_scope_witness.py",
    "scripts/validate_universal_symbol_receipt_store_writer_duty_scope_witness.py",
    "scripts/validate_universal_symbol_receipt_store_path_confinement_witness.py",
    "scripts/validate_universal_symbol_receipt_store_write_path_idempotency_witness.py",
    "scripts/validate_universal_symbol_receipt_store_durability_replay_witness.py",
    "scripts/validate_universal_symbol_receipt_store_recovery_witness.py",
    "scripts/validate_universal_symbol_receipt_store_path_custody_witness.py",
    "scripts/validate_universal_symbol_receipt_store_writer_identity_witness.py",
    "scripts/validate_universal_symbol_receipt_store_writer_registration_witness.py",
    "scripts/validate_universal_symbol_receipt_store_write_path_witness.py",
    "scripts/validate_universal_symbol_receipt_store_authority_witness.py",
    "scripts/validate_universal_symbol_runtime_admission_policy.py",
    "tests/fixtures/proof_coverage_matrix.json",
    "tests/test_proof_coverage_matrix.py",
    "tests/test_validate_universal_symbol_kernel.py",
)

SYMBOLIZABLE_FLAGS: tuple[tuple[str, str], ...] = (
    ("symbol_metadata", "metadata_is_symbolizable"),
    ("symbol_relations", "relation_is_symbolizable"),
    ("symbol_causality", "causality_is_symbolizable"),
    ("symbol_proof", "proof_is_symbolizable"),
)


class UniversalSymbolValidationError(ValueError):
    """Raised when the Universal Symbol Kernel contract is violated."""


def load_json_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise UniversalSymbolValidationError(f"missing file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise UniversalSymbolValidationError(f"invalid json: {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise UniversalSymbolValidationError(f"expected object: {path}")
    return value


def validate_universal_symbol_kernel(
    symbol_path: Path = DEFAULT_SYMBOL_PATH,
    schema_path: Path = DEFAULT_SCHEMA_PATH,
) -> dict[str, Any]:
    schema = load_json_object(schema_path)
    symbol = load_json_object(symbol_path)
    errors: list[str] = []

    _validate_schema_boundary(schema, errors)
    _validate_json_schema(symbol, schema, errors)
    _validate_required_sections(symbol, errors)
    _validate_identity(symbol, errors)
    _validate_foundation_governance(symbol, errors)
    _validate_symbolizable_surfaces(symbol, errors)
    _validate_authority_denials(symbol, errors)
    _validate_contract_summary(symbol, schema, errors)
    _validate_evidence_refs(symbol, errors)
    _validate_evidence_ref_files(symbol, errors)

    result = {
        "symbol_path": _repo_relative(symbol_path),
        "schema_path": _repo_relative(schema_path),
        "valid": not errors,
        "errors": errors,
        "symbol_id": symbol.get("symbol_id", ""),
        "symbol_version": symbol.get("symbol_version", ""),
        "authority_denial_count": len(AUTHORITY_DENIAL_FIELDS),
        "evidence_ref_count": len(symbol.get("evidence_refs", [])) if isinstance(symbol.get("evidence_refs"), list) else 0,
    }
    if errors:
        raise UniversalSymbolValidationError("; ".join(errors))
    return result


def _validate_schema_boundary(schema: Mapping[str, Any], errors: list[str]) -> None:
    if schema.get("$id") != "urn:mullusi:schema:universal-symbol:1":
        errors.append("schema id drift")
    if schema.get("additionalProperties") is not False:
        errors.append("schema must reject additional properties")
    required = schema.get("required")
    if not isinstance(required, list) or "symbol_authority_boundary" not in required:
        errors.append("schema must require symbol_authority_boundary")
    if not _schema_symbol_kind_values(schema):
        errors.append("schema must declare symbol_identity.symbol_kind enum")
    if len(_schema_symbol_kind_values(schema)) != len(set(_schema_symbol_kind_values(schema))):
        errors.append("schema symbol_kind enum must not contain duplicates")
    defs = _mapping(schema.get("$defs"))
    string_array = _mapping(defs.get("string_array"))
    string_items = _mapping(string_array.get("items"))
    if string_items.get("minLength") != 1:
        errors.append("schema string_array items must be non-empty")


def _validate_json_schema(symbol: Mapping[str, Any], schema: Mapping[str, Any], errors: list[str]) -> None:
    if jsonschema is None:
        errors.append("jsonschema dependency missing")
        return
    validator = jsonschema.Draft202012Validator(schema, format_checker=jsonschema.FormatChecker())
    schema_errors = sorted(validator.iter_errors(symbol), key=lambda error: tuple(error.path))
    for error in schema_errors:
        path = ".".join(str(part) for part in error.absolute_path) or "$"
        errors.append(f"schema validation failed at {path}: {error.message}")


def _validate_required_sections(symbol: Mapping[str, Any], errors: list[str]) -> None:
    required_sections = (
        "symbol_identity",
        "symbol_boundary",
        "symbol_metadata",
        "symbol_relations",
        "symbol_causality",
        "symbol_lineage",
        "symbol_governance",
        "symbol_proof",
        "symbol_skill_projection",
        "symbol_authority_boundary",
        "contract_summary",
    )
    for section in required_sections:
        if not isinstance(symbol.get(section), dict):
            errors.append(f"missing object section: {section}")


def _validate_identity(symbol: Mapping[str, Any], errors: list[str]) -> None:
    symbol_id = symbol.get("symbol_id")
    if not isinstance(symbol_id, str) or not symbol_id.startswith("universal-symbol-"):
        errors.append("symbol_id must use universal-symbol prefix")
    if symbol.get("symbol_version") != "universal_symbol.v1":
        errors.append("symbol_version must be universal_symbol.v1")
    identity = _mapping(symbol.get("symbol_identity"))
    if identity.get("definition", "") == "":
        errors.append("symbol definition is required")
    if identity.get("symbol_kind") != "concept":
        errors.append("foundation example must define the kernel as a concept symbol")


def _validate_foundation_governance(symbol: Mapping[str, Any], errors: list[str]) -> None:
    governance = _mapping(symbol.get("symbol_governance"))
    if governance.get("governance_mode") != "foundation":
        errors.append("foundation example must remain governance_mode=foundation")
    if governance.get("authority_refs") not in ([], None):
        errors.append("foundation example must not carry authority refs")
    if governance.get("approval_refs") not in ([], None):
        errors.append("foundation example must not carry approval refs")
    blocked = governance.get("blocked_action_refs")
    if not isinstance(blocked, list) or len(blocked) < 7:
        errors.append("foundation example must list blocked action refs")
    proof = _mapping(symbol.get("symbol_proof"))
    if proof.get("proof_state") != "awaiting_evidence":
        errors.append("foundation example proof_state must remain awaiting_evidence")
    if proof.get("terminal_closure_ref") != "":
        errors.append("foundation example must not carry terminal closure ref")
    projection = _mapping(symbol.get("symbol_skill_projection"))
    if projection.get("skill_projection_is_advisory_only") is not True:
        errors.append("skill projection must remain advisory only")


def _validate_symbolizable_surfaces(symbol: Mapping[str, Any], errors: list[str]) -> None:
    for section_name, field_name in SYMBOLIZABLE_FLAGS:
        section = _mapping(symbol.get(section_name))
        if section.get(field_name) is not True:
            errors.append(f"{section_name}.{field_name} must be true")
    summary = _mapping(symbol.get("contract_summary"))
    if summary.get("everything_symbolizable") is not True:
        errors.append("contract summary must set everything_symbolizable=true")
    if summary.get("symbol_native_boundary") is not True:
        errors.append("contract summary must set symbol_native_boundary=true")


def _validate_authority_denials(symbol: Mapping[str, Any], errors: list[str]) -> None:
    boundary = _mapping(symbol.get("symbol_authority_boundary"))
    for field_name in AUTHORITY_DENIAL_FIELDS:
        if boundary.get(field_name) is not False:
            errors.append(f"authority boundary must deny {field_name}")


def _validate_contract_summary(symbol: Mapping[str, Any], schema: Mapping[str, Any], errors: list[str]) -> None:
    summary = _mapping(symbol.get("contract_summary"))
    if summary.get("authority_denial_count") != len(AUTHORITY_DENIAL_FIELDS):
        errors.append("authority_denial_count drift")
    symbolizable_count = summary.get("symbolizable_surface_count")
    expected_symbolizable_count = len(_schema_symbol_kind_values(schema))
    if not isinstance(symbolizable_count, int):
        errors.append("symbolizable_surface_count must be an integer")
    elif symbolizable_count != expected_symbolizable_count:
        errors.append(
            f"symbolizable_surface_count drift: expected {expected_symbolizable_count}, got {symbolizable_count}"
        )
    evidence_count = summary.get("evidence_ref_count")
    evidence_refs = symbol.get("evidence_refs")
    if isinstance(evidence_refs, list) and evidence_count != len(evidence_refs):
        errors.append("evidence_ref_count drift")


def _validate_evidence_refs(symbol: Mapping[str, Any], errors: list[str]) -> None:
    refs = symbol.get("evidence_refs")
    if not isinstance(refs, list):
        errors.append("evidence_refs must be a list")
        return
    missing = tuple(ref for ref in REQUIRED_EVIDENCE_REFS if ref not in refs)
    if missing:
        errors.append("missing required evidence refs: " + ", ".join(missing))


def _validate_evidence_ref_files(symbol: Mapping[str, Any], errors: list[str]) -> None:
    refs = symbol.get("evidence_refs")
    if not isinstance(refs, list):
        return
    for ref in refs:
        if not isinstance(ref, str) or "://" in ref:
            continue
        ref_path = Path(ref)
        if ref_path.is_absolute():
            errors.append(f"evidence ref must be repository-relative: {ref}")
            continue
        candidate_path = (REPO_ROOT / ref_path).resolve()
        try:
            candidate_path.relative_to(REPO_ROOT.resolve())
        except ValueError:
            errors.append(f"evidence ref escapes repository: {ref}")
            continue
        if not candidate_path.exists():
            errors.append(f"evidence ref file missing: {ref}")


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _schema_symbol_kind_values(schema: Mapping[str, Any]) -> tuple[str, ...]:
    properties = _mapping(schema.get("properties"))
    identity = _mapping(properties.get("symbol_identity"))
    identity_properties = _mapping(identity.get("properties"))
    symbol_kind = _mapping(identity_properties.get("symbol_kind"))
    values = symbol_kind.get("enum")
    if not isinstance(values, list):
        return ()
    return tuple(value for value in values if isinstance(value, str))


def _repo_relative(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate Universal Symbol Kernel foundation example")
    parser.add_argument("--symbol", type=Path, default=DEFAULT_SYMBOL_PATH)
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA_PATH)
    parser.add_argument("--json", action="store_true", help="emit JSON validation report")
    args = parser.parse_args()

    try:
        report = validate_universal_symbol_kernel(args.symbol, args.schema)
    except UniversalSymbolValidationError as exc:
        if args.json:
            print(json.dumps({"valid": False, "error": str(exc)}, indent=2, sort_keys=True))
        else:
            print(f"[FAIL] universal_symbol_kernel: {exc}")
        return 1

    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print("[PASS] universal_symbol_kernel")
        print("STATUS: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
