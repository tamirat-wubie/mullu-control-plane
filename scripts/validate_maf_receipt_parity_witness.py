#!/usr/bin/env python3
"""Validate the MafReceiptParityWitness contract.

Purpose: verify that Python receipt schema surfaces are mapped to Rust MAF
crate surfaces by digest-only evidence without claiming runtime binding.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: Python standard library and schema validation helpers.
Invariants:
  - Validation is read-only and deterministic.
  - Rust execution, subprocess, PyO3, CLI, and connector authority remain denied.
  - Parity is static digest evidence until fixture, ABI, and failure witnesses exist.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
import sys
from pathlib import Path
from typing import Any


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from scripts.validate_schemas import _load_schema, _validate_schema_instance  # noqa: E402


DEFAULT_SCHEMA_PATH = WORKSPACE_ROOT / "schemas" / "maf_receipt_parity_witness.schema.json"
DEFAULT_WITNESS_PATH = WORKSPACE_ROOT / "examples" / "maf_receipt_parity_witness.foundation.json"
EXPECTED_SCHEMA_ID = "urn:mullusi:schema:maf-receipt-parity-witness:1"
EXPECTED_SCHEMA_TITLE = "MAF Receipt Parity Witness"
EXPECTED_WITNESS_VERSION = "maf_receipt_parity_witness.v1"
EXPECTED_PARITY_MODE = "digest_only_static_surface_map"
REQUIRED_FUTURE_WITNESSES = {
    "witness://maf/abi-cli-contract",
    "witness://maf/subprocess-effect-boundary",
    "witness://maf/deterministic-fixture-parity",
    "witness://maf/failure-receipt-path",
}
REQUIRED_PYTHON_SCHEMAS = {
    "schemas/sdlc_transition_receipt.schema.json",
    "schemas/worker_failure_receipt.schema.json",
    "schemas/universal_action_orchestration.schema.json",
    "schemas/capability_descriptor.schema.json",
    "schemas/policy_decision.schema.json",
    "schemas/supervisor_tick.schema.json",
    "schemas/learning_admission.schema.json",
    "schemas/kernel_proof.schema.json",
    "schemas/agent_identity.schema.json",
    "schemas/github_action_execution_receipt.schema.json",
}
REQUIRED_RUST_CRATES = {
    "maf-kernel": ("maf/rust/crates/maf-kernel/Cargo.toml", "maf/rust/crates/maf-kernel/src/lib.rs", False),
    "maf-event": ("maf/rust/crates/maf-event/Cargo.toml", "maf/rust/crates/maf-event/src/lib.rs", False),
    "maf-governance": ("maf/rust/crates/maf-governance/Cargo.toml", "maf/rust/crates/maf-governance/src/lib.rs", False),
    "maf-orchestration": ("maf/rust/crates/maf-orchestration/Cargo.toml", "maf/rust/crates/maf-orchestration/src/lib.rs", False),
    "maf-capability": ("maf/rust/crates/maf-capability/Cargo.toml", "maf/rust/crates/maf-capability/src/lib.rs", False),
    "maf-agent": ("maf/rust/crates/maf-agent/Cargo.toml", "maf/rust/crates/maf-agent/src/lib.rs", False),
    "maf-supervisor": ("maf/rust/crates/maf-supervisor/Cargo.toml", "maf/rust/crates/maf-supervisor/src/lib.rs", False),
    "maf-ops": ("maf/rust/crates/maf-ops/Cargo.toml", "maf/rust/crates/maf-ops/src/lib.rs", False),
    "maf-learning": ("maf/rust/crates/maf-learning/Cargo.toml", "maf/rust/crates/maf-learning/src/lib.rs", False),
    "maf-truth-kernel": ("maf/rust/crates/maf-truth-kernel/Cargo.toml", "maf/rust/crates/maf-truth-kernel/src/lib.rs", False),
    "maf-cli": ("maf/rust/crates/maf-cli/Cargo.toml", "maf/rust/crates/maf-cli/src/main.rs", True),
}
REQUIRED_RECEIPT_REFS = {
    "maf_receipt_parity_witness_schema": "schemas/maf_receipt_parity_witness.schema.json",
    "maf_receipt_parity_witness_example": "examples/maf_receipt_parity_witness.foundation.json",
    "maf_receipt_parity_witness_validator": "scripts/validate_maf_receipt_parity_witness.py",
    "maf_receipt_parity_witness_tests": "tests/test_validate_maf_receipt_parity_witness.py",
    "maf_boundary_doc": "maf/MAF_BOUNDARY.md",
    "maf_receipt_coverage_doc": "docs/MAF_RECEIPT_COVERAGE.md",
    "rust_workspace_manifest": "maf/rust/Cargo.toml",
    "universal_action_orchestration_schema": "schemas/universal_action_orchestration.schema.json",
    "life_meaning_judgment_schema": "schemas/life_meaning_judgment.schema.json",
    "worker_failure_receipt_schema": "schemas/worker_failure_receipt.schema.json",
}
REQUIRED_EVIDENCE_REFS = (
    "schemas/maf_receipt_parity_witness.schema.json",
    "examples/maf_receipt_parity_witness.foundation.json",
    "scripts/validate_maf_receipt_parity_witness.py",
    "tests/test_validate_maf_receipt_parity_witness.py",
    "docs/93_maf_receipt_parity_witness_contract.md",
    "docs/82_cross_repo_opportunity_map.md",
    "docs/MAF_RECEIPT_COVERAGE.md",
    "maf/MAF_BOUNDARY.md",
    "maf/rust/Cargo.toml",
    "examples/sdlc/requirement_maf_receipt_parity_witness_20260618.json",
    "examples/sdlc/design_maf_receipt_parity_witness_20260618.json",
    "examples/sdlc/security_review_maf_receipt_parity_witness_20260618.json",
)
AUTHORITY_FALSE_FLAGS = (
    "pyo3_binding_allowed",
    "subprocess_execution_allowed",
    "cli_execution_allowed",
    "rust_crate_execution_allowed",
    "python_imports_rust_allowed",
    "external_connector_call_allowed",
    "network_call_allowed",
    "secret_access_allowed",
    "filesystem_write_allowed",
    "runtime_dispatch_allowed",
    "canonical_state_mutation_allowed",
    "terminal_closure_allowed",
    "success_claim_allowed",
)
SECRET_MARKERS = ("BEGIN PRIVATE KEY", "api_key", "access_token", "refresh_token", "client_secret")


class MafReceiptParityWitnessError(ValueError):
    """Raised when a MafReceiptParityWitness artifact cannot load."""


def load_json_object(json_path: Path, label: str) -> dict[str, Any]:
    """Load one JSON object from disk."""

    path = json_path if json_path.is_absolute() else WORKSPACE_ROOT / json_path
    if not path.exists():
        raise FileNotFoundError(f"missing {label}: {path}")
    if not path.is_file():
        raise IsADirectoryError(f"{label} path is not a file: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise MafReceiptParityWitnessError(f"{label} must be a JSON object")
    return payload


def canonical_source_digest(source_path: Path) -> str:
    """Return the repository-stable SHA-256 digest for a text source file."""

    source_text = source_path.read_text(encoding="utf-8")
    canonical_text = source_text.replace("\r\n", "\n")
    return hashlib.sha256(canonical_text.encode("utf-8")).hexdigest()


def validate_schema_artifact(schema: dict[str, Any]) -> list[str]:
    """Return deterministic schema artifact errors."""

    errors: list[str] = []
    if schema.get("$id") != EXPECTED_SCHEMA_ID:
        errors.append("schema $id is invalid")
    if schema.get("title") != EXPECTED_SCHEMA_TITLE:
        errors.append("schema title is invalid")
    if schema.get("type") != "object":
        errors.append("schema root type must be object")
    if schema.get("additionalProperties") is not False:
        errors.append("schema root must close additional properties")
    required_fields = schema.get("required")
    properties = schema.get("properties")
    if not isinstance(required_fields, list):
        errors.append("schema required field must be a list")
    if not isinstance(properties, dict):
        errors.append("schema properties must be an object")
    if isinstance(required_fields, list) and isinstance(properties, dict):
        for field_name in (
            "witness_id",
            "witness_version",
            "generated_at",
            "solver_outcome",
            "parity_scope",
            "python_schema_surfaces",
            "rust_crate_surfaces",
            "parity_mappings",
            "authority_boundary",
            "receipt_refs",
            "contract_summary",
            "evidence_refs",
        ):
            if field_name not in required_fields:
                errors.append(f"schema missing required field: {field_name}")
            if field_name not in properties:
                errors.append(f"schema missing property: {field_name}")
    return errors


def validate_maf_receipt_parity_witness_record(
    record: Any,
    schema: dict[str, Any] | None = None,
) -> list[str]:
    """Return deterministic validation errors for one parity witness."""

    schema_payload = schema or _load_schema(DEFAULT_SCHEMA_PATH)
    errors = _validate_schema_instance(schema_payload, record)
    if not isinstance(record, dict):
        errors.append("maf receipt parity witness must be a JSON object")
        return errors

    if record.get("witness_version") != EXPECTED_WITNESS_VERSION:
        errors.append("witness_version must match maf_receipt_parity_witness.v1")

    _reject_secret_markers(record, errors)
    _validate_parity_scope(record.get("parity_scope"), errors)
    _validate_python_schema_surfaces(record.get("python_schema_surfaces"), errors)
    _validate_rust_crate_surfaces(record.get("rust_crate_surfaces"), errors)
    _validate_parity_mappings(record, errors)
    _validate_authority_boundary(record.get("authority_boundary"), errors)
    _validate_contract_summary(record, errors)
    _validate_receipt_refs(record.get("receipt_refs"), errors)
    _require_subset(record, "evidence_refs", REQUIRED_EVIDENCE_REFS, errors)
    _validate_solver_outcome(record, errors)
    return errors


def validate_maf_receipt_parity_witness(
    schema_path: Path = DEFAULT_SCHEMA_PATH,
    witness_path: Path = DEFAULT_WITNESS_PATH,
) -> list[str]:
    """Validate the schema artifact and default Foundation Mode witness."""

    schema = _load_schema(schema_path)
    witness = load_json_object(witness_path, "MafReceiptParityWitness")
    errors = validate_schema_artifact(schema)
    errors.extend(validate_maf_receipt_parity_witness_record(witness, schema))
    return errors


def build_mutated_maf_receipt_parity_witness(**updates: Any) -> dict[str, Any]:
    """Build a deterministic mutated copy of the default witness."""

    witness = load_json_object(DEFAULT_WITNESS_PATH, "MafReceiptParityWitness")
    mutated = deepcopy(witness)
    for dotted_key, value in updates.items():
        target: Any = mutated
        segments = dotted_key.split("__")
        for segment in segments[:-1]:
            if isinstance(target, list):
                target = target[int(segment)]
                continue
            next_target = target.get(segment)
            if not isinstance(next_target, (dict, list)):
                next_target = {}
                target[segment] = next_target
            target = next_target
        final_segment = segments[-1]
        if isinstance(target, list):
            target[int(final_segment)] = value
        else:
            target[final_segment] = value
    return mutated


def workspace_display_path(path: Path) -> str:
    """Return a stable workspace-relative display path when possible."""

    resolved_path = path if path.is_absolute() else WORKSPACE_ROOT / path
    try:
        return str(resolved_path.resolve().relative_to(WORKSPACE_ROOT)).replace("\\", "/")
    except ValueError:
        return str(path)


def _validate_parity_scope(scope: Any, errors: list[str]) -> None:
    if not isinstance(scope, dict):
        errors.append("parity_scope must be an object")
        return
    if scope.get("foundation_mode") is not True:
        errors.append("parity_scope.foundation_mode must be true")
    if scope.get("parity_mode") != EXPECTED_PARITY_MODE:
        errors.append("parity_scope.parity_mode must be digest_only_static_surface_map")
    for flag in ("runtime_binding_claimed", "rust_execution_performed", "python_to_rust_call_path_claimed"):
        if scope.get(flag) is not False:
            errors.append(f"parity_scope.{flag} must be false")
    if scope.get("direct_runtime_binding_deferred") is not True:
        errors.append("parity_scope.direct_runtime_binding_deferred must be true")
    future_witnesses = set(scope.get("required_future_witnesses") or [])
    missing = sorted(REQUIRED_FUTURE_WITNESSES - future_witnesses)
    for ref in missing:
        errors.append(f"required_future_witnesses missing required ref: {ref}")


def _validate_python_schema_surfaces(surfaces: Any, errors: list[str]) -> None:
    if not isinstance(surfaces, list):
        errors.append("python_schema_surfaces must be a list")
        return
    by_ref = {surface.get("schema_ref"): surface for surface in surfaces if isinstance(surface, dict)}
    for schema_ref in sorted(REQUIRED_PYTHON_SCHEMAS):
        surface = by_ref.get(schema_ref)
        if not isinstance(surface, dict):
            errors.append(f"python_schema_surfaces missing required schema: {schema_ref}")
            continue
        if surface.get("required_for_parity") is not True:
            errors.append(f"{schema_ref} required_for_parity must be true")
        _validate_digest_field(surface, "schema_digest_sha256", schema_ref, errors)


def _validate_rust_crate_surfaces(surfaces: Any, errors: list[str]) -> None:
    if not isinstance(surfaces, list):
        errors.append("rust_crate_surfaces must be a list")
        return
    by_name = {surface.get("crate_name"): surface for surface in surfaces if isinstance(surface, dict)}
    for crate_name, (manifest_ref, entry_ref, cli_surface) in sorted(REQUIRED_RUST_CRATES.items()):
        surface = by_name.get(crate_name)
        if not isinstance(surface, dict):
            errors.append(f"rust_crate_surfaces missing required crate: {crate_name}")
            continue
        if surface.get("crate_manifest_ref") != manifest_ref:
            errors.append(f"{crate_name} crate_manifest_ref must be {manifest_ref}")
        if surface.get("crate_entry_ref") != entry_ref:
            errors.append(f"{crate_name} crate_entry_ref must be {entry_ref}")
        if surface.get("execution_authority_denied") is not True:
            errors.append(f"{crate_name} execution_authority_denied must be true")
        if surface.get("cli_surface") is not cli_surface:
            errors.append(f"{crate_name} cli_surface must be {cli_surface}")
        expected_kind = "binary" if cli_surface else "library"
        if surface.get("crate_kind") != expected_kind:
            errors.append(f"{crate_name} crate_kind must be {expected_kind}")
        _validate_digest_field(surface, "crate_manifest_digest_sha256", manifest_ref, errors)
        _validate_digest_field(surface, "crate_entry_digest_sha256", entry_ref, errors)


def _validate_parity_mappings(record: dict[str, Any], errors: list[str]) -> None:
    mappings = record.get("parity_mappings")
    if not isinstance(mappings, list):
        errors.append("parity_mappings must be a list")
        return
    schema_refs = {surface.get("schema_ref") for surface in record.get("python_schema_surfaces", []) if isinstance(surface, dict)}
    crate_names = {surface.get("crate_name") for surface in record.get("rust_crate_surfaces", []) if isinstance(surface, dict)}
    mapped_schema_refs = {mapping.get("python_schema_ref") for mapping in mappings if isinstance(mapping, dict)}
    for schema_ref in sorted(REQUIRED_PYTHON_SCHEMAS):
        if schema_ref not in mapped_schema_refs:
            errors.append(f"parity_mappings missing required schema mapping: {schema_ref}")
    for mapping in mappings:
        if not isinstance(mapping, dict):
            errors.append("parity_mappings entries must be objects")
            continue
        schema_ref = mapping.get("python_schema_ref")
        crate_name = mapping.get("rust_crate_name")
        if schema_ref not in schema_refs:
            errors.append(f"parity_mappings references unknown python_schema_ref: {schema_ref}")
        if crate_name not in crate_names:
            errors.append(f"parity_mappings references unknown rust_crate_name: {crate_name}")
        if mapping.get("runtime_binding_allowed") is not False:
            errors.append(f"{mapping.get('mapping_id')} runtime_binding_allowed must be false")
        gap_refs = mapping.get("gap_refs")
        if not isinstance(gap_refs, list) or not gap_refs:
            errors.append(f"{mapping.get('mapping_id')} gap_refs required")
        if mapping.get("parity_status") == "digest_recorded_gap_open":
            if not any("runtime-binding-not-claimed" in str(ref) for ref in gap_refs or []):
                errors.append(f"{mapping.get('mapping_id')} must retain runtime-binding-not-claimed gap")
        if mapping.get("parity_status") == "authority_denied" and crate_name != "maf-cli":
            errors.append(f"{mapping.get('mapping_id')} authority_denied is only valid for maf-cli")


def _validate_authority_boundary(boundary: Any, errors: list[str]) -> None:
    if not isinstance(boundary, dict):
        errors.append("authority_boundary must be an object")
        return
    if boundary.get("digest_only_static_read_allowed") is not True:
        errors.append("authority_boundary.digest_only_static_read_allowed must be true")
    for flag in AUTHORITY_FALSE_FLAGS:
        if boundary.get(flag) is not False:
            errors.append(f"authority_boundary.{flag} must be false")


def _validate_contract_summary(record: dict[str, Any], errors: list[str]) -> None:
    summary = record.get("contract_summary")
    if not isinstance(summary, dict):
        errors.append("contract_summary must be an object")
        return
    python_schema_count = len(record.get("python_schema_surfaces") or [])
    rust_crate_count = len(record.get("rust_crate_surfaces") or [])
    mapping_count = len(record.get("parity_mappings") or [])
    authority_boundary = record.get("authority_boundary") if isinstance(record.get("authority_boundary"), dict) else {}
    authority_denial_count = sum(1 for flag in AUTHORITY_FALSE_FLAGS if authority_boundary.get(flag) is False)
    awaiting_gap_count = sum(
        len(mapping.get("gap_refs") or [])
        for mapping in record.get("parity_mappings", [])
        if isinstance(mapping, dict)
    )
    evidence_ref_count = len(record.get("evidence_refs") or [])
    expected_counts = {
        "python_schema_surface_count": python_schema_count,
        "rust_crate_surface_count": rust_crate_count,
        "parity_mapping_count": mapping_count,
        "authority_denial_count": authority_denial_count,
        "awaiting_gap_count": awaiting_gap_count,
        "evidence_ref_count": evidence_ref_count,
    }
    for field_name, expected_value in expected_counts.items():
        if summary.get(field_name) != expected_value:
            errors.append(f"contract_summary.{field_name} must be {expected_value}")


def _validate_receipt_refs(refs: Any, errors: list[str]) -> None:
    if not isinstance(refs, dict):
        errors.append("receipt_refs must be an object")
        return
    for key, expected_ref in REQUIRED_RECEIPT_REFS.items():
        if refs.get(key) != expected_ref:
            errors.append(f"receipt_refs.{key} must be {expected_ref}")


def _validate_solver_outcome(record: dict[str, Any], errors: list[str]) -> None:
    scope = record.get("parity_scope") if isinstance(record.get("parity_scope"), dict) else {}
    if scope.get("runtime_binding_claimed") is not False or scope.get("rust_execution_performed") is not False:
        errors.append("runtime binding and rust execution must remain unclaimed")
    if record.get("solver_outcome") != "AwaitingEvidence":
        errors.append("solver_outcome must remain AwaitingEvidence while fixture, ABI, and failure witnesses are open")


def _validate_digest_field(record: dict[str, Any], digest_field: str, source_ref: str, errors: list[str]) -> None:
    source_path = WORKSPACE_ROOT / source_ref
    if not source_path.exists():
        errors.append(f"{source_ref} source path is missing")
        return
    expected_digest = canonical_source_digest(source_path)
    if record.get(digest_field) != expected_digest:
        errors.append(f"{source_ref} {digest_field} does not match source digest")


def _require_subset(record: dict[str, Any], field_name: str, required_refs: tuple[str, ...], errors: list[str]) -> None:
    values = record.get(field_name)
    if not isinstance(values, list):
        errors.append(f"{field_name} must be a list")
        return
    value_set = set(values)
    for required_ref in required_refs:
        if required_ref not in value_set:
            errors.append(f"{field_name} missing required ref: {required_ref}")


def _reject_secret_markers(record: dict[str, Any], errors: list[str]) -> None:
    serialized = json.dumps(record, sort_keys=True)
    for marker in SECRET_MARKERS:
        if marker in serialized:
            errors.append(f"secret marker is not allowed in MafReceiptParityWitness: {marker}")


def _format_errors(errors: list[str]) -> str:
    return "\n".join(f"- {error}" for error in errors)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA_PATH)
    parser.add_argument("--witness", type=Path, default=DEFAULT_WITNESS_PATH)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    schema_path = args.schema if args.schema.is_absolute() else WORKSPACE_ROOT / args.schema
    witness_path = args.witness if args.witness.is_absolute() else WORKSPACE_ROOT / args.witness
    errors = validate_maf_receipt_parity_witness(schema_path, witness_path)

    if args.json:
        print(
            json.dumps(
                {
                    "status": "passed" if not errors else "failed",
                    "schema_path": workspace_display_path(schema_path),
                    "witness_path": workspace_display_path(witness_path),
                    "errors": errors,
                },
                indent=2,
                sort_keys=True,
            )
        )
    elif errors:
        print("[FAIL] MafReceiptParityWitness validation failed:")
        print(_format_errors(errors))
    else:
        print("[PASS] MafReceiptParityWitness validation passed")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
