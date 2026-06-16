#!/usr/bin/env python3
"""Validate the MafReceiptParityWitness contract.

Purpose: verify Foundation Mode MAF receipt parity witnesses without invoking
Rust, PyO3, subprocesses, network calls, MAF CLI commands, or runtime binding.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: Python standard library, schema validation helpers, local MAF
workspace manifests, and local Python/Rust hash parity tests.
Invariants:
  - Validation is read-only and deterministic.
  - MAF Rust does not certify Python runtime requests in Foundation Mode.
  - Hash parity evidence remains test-time evidence, not runtime authority.
  - FFI, subprocess, CLI, network, production, success, and terminal closure
    claims remain denied until separately governed.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
import json
import re
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
EXPECTED_SCHEMA_TITLE = "Maf Receipt Parity Witness"
EXPECTED_VERSION = "maf_receipt_parity_witness.v1"
EXPECTED_PROJECTION_MODE = "foundation_maf_receipt_parity"
EXPECTED_RECEIPT_HASH = "27bf13eff30cd9fd5fc334eff381e9b2349037bd0ef9dc88c2ca15d114a77fe5"
EXPECTED_STATE_HASH = "965b4f39a0784ee6858ff1e38a591b741edb48787395f2391e2089dbfadc534d"
EXPECTED_CRATES = (
    "maf-agent",
    "maf-capability",
    "maf-cli",
    "maf-event",
    "maf-governance",
    "maf-kernel",
    "maf-learning",
    "maf-ops",
    "maf-orchestration",
    "maf-supervisor",
    "maf-truth-kernel",
)
FALSE_AUTHORITY_FIELDS = (
    "pyo3_binding_present",
    "python_imports_rust_runtime",
    "rust_subprocess_invoked",
    "maf_cli_invoked",
    "network_call_performed",
    "filesystem_mutation_performed",
    "receipt_emission_mutated",
    "runtime_certification_claimed",
    "rust_certifies_python_claimed",
    "production_binding_claimed",
    "terminal_closure_allowed",
    "success_claim_allowed",
)
REQUIRED_RECEIPT_REFS = {
    "maf_receipt_parity_witness_schema": "schemas/maf_receipt_parity_witness.schema.json",
    "maf_boundary_doc": "maf/MAF_BOUNDARY.md",
    "maf_receipt_coverage_doc": "docs/MAF_RECEIPT_COVERAGE.md",
    "audit_f8_scoping_doc": "docs/AUDIT_F8_SCOPING_PLAN.md",
    "rust_workspace_manifest": "maf/rust/Cargo.toml",
    "python_hash_contract_test": "mcoi/tests/test_proof_hash_contract.py",
    "rust_hash_contract_test": "maf/rust/crates/maf-kernel/src/lib.rs",
}
REQUIRED_EVIDENCE_REFS = (
    "schemas/maf_receipt_parity_witness.schema.json",
    "examples/maf_receipt_parity_witness.foundation.json",
    "scripts/validate_maf_receipt_parity_witness.py",
    "tests/test_validate_maf_receipt_parity_witness.py",
    "maf/MAF_BOUNDARY.md",
    "docs/MAF_RECEIPT_COVERAGE.md",
    "docs/AUDIT_F8_SCOPING_PLAN.md",
    "maf/rust/Cargo.toml",
    "maf/rust/crates/maf-kernel/src/lib.rs",
    "mcoi/tests/test_proof_hash_contract.py",
    "docs/82_cross_repo_opportunity_map.md",
    "docs/89_maf_receipt_parity_witness_contract.md",
    "examples/sdlc/requirement_maf_receipt_parity_witness_20260616.json",
)


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


def parse_workspace_members(cargo_toml_path: Path = WORKSPACE_ROOT / "maf" / "rust" / "Cargo.toml") -> tuple[str, ...]:
    """Return workspace crate member names from the local MAF Cargo manifest."""

    manifest_text = cargo_toml_path.read_text(encoding="utf-8")
    members = re.findall(r'"crates/([^"]+)"', manifest_text)
    return tuple(sorted(members))


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
    required = schema.get("required")
    properties = schema.get("properties")
    if not isinstance(required, list):
        errors.append("schema required field must be a list")
    if not isinstance(properties, dict):
        errors.append("schema properties must be an object")
    if isinstance(required, list) and isinstance(properties, dict):
        for field_name in (
            "witness_id",
            "witness_version",
            "generated_at",
            "solver_outcome",
            "workspace_scope",
            "hash_parity_witnesses",
            "crate_surface_mappings",
            "authority_boundary",
            "receipt_refs",
            "contract_summary",
            "evidence_refs",
            "gap_refs",
        ):
            if field_name not in required:
                errors.append(f"schema missing required field: {field_name}")
            if field_name not in properties:
                errors.append(f"schema missing property: {field_name}")
    return errors


def validate_maf_receipt_parity_witness_record(record: Any, schema: dict[str, Any] | None = None) -> list[str]:
    """Return deterministic validation errors for one MAF parity witness."""

    schema_payload = schema or _load_schema(DEFAULT_SCHEMA_PATH)
    errors = _validate_schema_instance(schema_payload, record)
    if not isinstance(record, dict):
        errors.append("MAF receipt parity witness must be a JSON object")
        return errors

    if record.get("witness_version") != EXPECTED_VERSION:
        errors.append("witness_version must match maf_receipt_parity_witness.v1")

    _validate_workspace_scope(record.get("workspace_scope"), errors)
    _validate_hash_parity_witnesses(record.get("hash_parity_witnesses"), errors)
    _validate_crate_surface_mappings(record.get("crate_surface_mappings"), errors)
    _validate_authority_boundary(record.get("authority_boundary"), errors)
    _validate_receipt_refs(record.get("receipt_refs"), errors)
    _require_subset(record, "evidence_refs", REQUIRED_EVIDENCE_REFS, errors)
    _validate_contract_summary(record, errors)
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

    resolved = path if path.is_absolute() else WORKSPACE_ROOT / path
    try:
        return str(resolved.resolve().relative_to(WORKSPACE_ROOT)).replace("\\", "/")
    except ValueError:
        return str(path)


def _validate_workspace_scope(scope: Any, errors: list[str]) -> None:
    if not isinstance(scope, dict):
        errors.append("workspace_scope must be an object")
        return
    if scope.get("projection_mode") != EXPECTED_PROJECTION_MODE:
        errors.append(f"workspace_scope.projection_mode must be {EXPECTED_PROJECTION_MODE}")
    if scope.get("foundation_mode") is not True:
        errors.append("workspace_scope.foundation_mode must be true")
    if scope.get("python_runtime_binding_claimed") is not False:
        errors.append("workspace_scope.python_runtime_binding_claimed must remain false")
    if scope.get("rust_runtime_certification_claimed") is not False:
        errors.append("workspace_scope.rust_runtime_certification_claimed must remain false")
    member_count = len(parse_workspace_members())
    if scope.get("rust_workspace_member_count") != member_count:
        errors.append("workspace_scope.rust_workspace_member_count must match maf/rust/Cargo.toml")


def _validate_hash_parity_witnesses(witnesses: Any, errors: list[str]) -> None:
    if not isinstance(witnesses, list):
        errors.append("hash_parity_witnesses must be a list")
        return

    python_hash_test = (WORKSPACE_ROOT / "mcoi" / "tests" / "test_proof_hash_contract.py").read_text(encoding="utf-8")
    rust_hash_test = (WORKSPACE_ROOT / "maf" / "rust" / "crates" / "maf-kernel" / "src" / "lib.rs").read_text(encoding="utf-8")
    expected_by_kind = {
        "receipt_hash": EXPECTED_RECEIPT_HASH,
        "state_hash": EXPECTED_STATE_HASH,
    }
    observed_kinds: set[str] = set()
    for index, witness in enumerate(witnesses):
        if not isinstance(witness, dict):
            errors.append(f"hash_parity_witnesses[{index}] must be an object")
            continue
        witness_kind = witness.get("witness_kind")
        observed_kinds.add(str(witness_kind))
        expected_hash = expected_by_kind.get(str(witness_kind))
        if expected_hash is None:
            errors.append(f"hash_parity_witnesses[{index}].witness_kind is not recognized")
            continue
        observed_expected_hash = witness.get("expected_sha256")
        if observed_expected_hash != expected_hash:
            errors.append(f"hash_parity_witnesses[{index}].expected_sha256 must match canonical constant")
        if isinstance(observed_expected_hash, str) and observed_expected_hash not in python_hash_test:
            errors.append(f"hash_parity_witnesses[{index}] expected hash missing from Python test")
        if isinstance(observed_expected_hash, str) and observed_expected_hash not in rust_hash_test:
            errors.append(f"hash_parity_witnesses[{index}] expected hash missing from Rust test")
        if expected_hash not in python_hash_test:
            errors.append(f"hash_parity_witnesses[{index}] expected hash missing from Python test")
        if expected_hash not in rust_hash_test:
            errors.append(f"hash_parity_witnesses[{index}] expected hash missing from Rust test")
        if witness.get("parity_status") != "test_time_hash_parity_verified":
            errors.append(f"hash_parity_witnesses[{index}].parity_status must be test_time_hash_parity_verified")
    for required_kind in expected_by_kind:
        if required_kind not in observed_kinds:
            errors.append(f"hash_parity_witnesses missing required kind: {required_kind}")


def _validate_crate_surface_mappings(mappings: Any, errors: list[str]) -> None:
    if not isinstance(mappings, list):
        errors.append("crate_surface_mappings must be a list")
        return

    observed_crates = {mapping.get("rust_crate") for mapping in mappings if isinstance(mapping, dict)}
    missing_crates = set(EXPECTED_CRATES) - observed_crates
    unexpected_crates = observed_crates - set(EXPECTED_CRATES)
    for crate_name in sorted(missing_crates):
        errors.append(f"crate_surface_mappings missing crate: {crate_name}")
    for crate_name in sorted(unexpected_crates):
        errors.append(f"crate_surface_mappings unexpected crate: {crate_name}")

    workspace_members = set(parse_workspace_members())
    for index, mapping in enumerate(mappings):
        if not isinstance(mapping, dict):
            errors.append(f"crate_surface_mappings[{index}] must be an object")
            continue
        crate_name = mapping.get("rust_crate")
        if crate_name not in workspace_members:
            errors.append(f"crate_surface_mappings[{index}].rust_crate missing from Cargo workspace")
        rust_surface_ref = mapping.get("rust_surface_ref")
        if not isinstance(rust_surface_ref, str) or not rust_surface_ref:
            errors.append(f"crate_surface_mappings[{index}].rust_surface_ref must be non-empty")
        elif "::" in rust_surface_ref:
            path_text = rust_surface_ref.split("::", 1)[0]
            if not (WORKSPACE_ROOT / path_text).exists():
                errors.append(f"crate_surface_mappings[{index}].rust_surface_ref path missing: {path_text}")
        elif not (WORKSPACE_ROOT / rust_surface_ref).exists():
            errors.append(f"crate_surface_mappings[{index}].rust_surface_ref path missing: {rust_surface_ref}")
        python_surface_ref = mapping.get("python_surface_ref")
        if not isinstance(python_surface_ref, str) or not python_surface_ref:
            errors.append(f"crate_surface_mappings[{index}].python_surface_ref must be non-empty")
        elif "::" in python_surface_ref:
            path_text = python_surface_ref.split("::", 1)[0]
            if not (WORKSPACE_ROOT / path_text).exists():
                errors.append(f"crate_surface_mappings[{index}].python_surface_ref path missing: {path_text}")
        elif not (WORKSPACE_ROOT / python_surface_ref).exists():
            errors.append(f"crate_surface_mappings[{index}].python_surface_ref path missing: {python_surface_ref}")
        for schema_ref in mapping.get("schema_refs", []):
            if not isinstance(schema_ref, str) or not (WORKSPACE_ROOT / schema_ref).exists():
                errors.append(f"crate_surface_mappings[{index}].schema_refs missing: {schema_ref}")
        status = mapping.get("parity_status")
        gap_refs = mapping.get("gap_refs")
        if status in {"awaiting_runtime_binding", "awaiting_rust_fixture"} and not gap_refs:
            errors.append(f"crate_surface_mappings[{index}].gap_refs required for awaiting parity status")
        if status == "test_time_hash_parity_verified" and gap_refs:
            errors.append(f"crate_surface_mappings[{index}].gap_refs must be empty for hash parity verified mapping")


def _validate_authority_boundary(boundary: Any, errors: list[str]) -> None:
    if not isinstance(boundary, dict):
        errors.append("authority_boundary must be an object")
        return
    for field_name in FALSE_AUTHORITY_FIELDS:
        if boundary.get(field_name) is not False:
            errors.append(f"authority_boundary.{field_name} must be false")


def _validate_receipt_refs(receipt_refs: Any, errors: list[str]) -> None:
    if not isinstance(receipt_refs, dict):
        errors.append("receipt_refs must be an object")
        return
    for key, expected_value in REQUIRED_RECEIPT_REFS.items():
        if receipt_refs.get(key) != expected_value:
            errors.append(f"receipt_refs.{key} must be {expected_value}")


def _validate_contract_summary(record: dict[str, Any], errors: list[str]) -> None:
    summary = record.get("contract_summary")
    if not isinstance(summary, dict):
        errors.append("contract_summary must be an object")
        return
    hash_witnesses = record.get("hash_parity_witnesses", [])
    mappings = record.get("crate_surface_mappings", [])
    authority = record.get("authority_boundary", {})
    evidence_refs = record.get("evidence_refs", [])
    gap_refs = record.get("gap_refs", [])
    if isinstance(hash_witnesses, list) and summary.get("hash_parity_witness_count") != len(hash_witnesses):
        errors.append("contract_summary.hash_parity_witness_count must match hash_parity_witnesses")
    if isinstance(mappings, list):
        awaiting_count = sum(
            1
            for mapping in mappings
            if isinstance(mapping, dict) and mapping.get("parity_status") != "test_time_hash_parity_verified"
        )
        if summary.get("crate_surface_mapping_count") != len(mappings):
            errors.append("contract_summary.crate_surface_mapping_count must match crate_surface_mappings")
        if summary.get("awaiting_runtime_binding_count") != awaiting_count:
            errors.append("contract_summary.awaiting_runtime_binding_count must match crate_surface_mappings")
    if isinstance(authority, dict):
        denial_count = sum(1 for field_name in FALSE_AUTHORITY_FIELDS if authority.get(field_name) is False)
        if summary.get("authority_denial_count") != denial_count:
            errors.append("contract_summary.authority_denial_count must match authority_boundary")
    if isinstance(evidence_refs, list):
        required_evidence_count = len(REQUIRED_EVIDENCE_REFS)
        if summary.get("evidence_ref_count") != len(evidence_refs):
            errors.append("contract_summary.evidence_ref_count must match evidence_refs")
        elif len(evidence_refs) != required_evidence_count:
            errors.append("contract_summary.evidence_ref_count must match required evidence_refs")
    if isinstance(gap_refs, list) and summary.get("gap_ref_count") != len(gap_refs):
        errors.append("contract_summary.gap_ref_count must match gap_refs")


def _validate_solver_outcome(record: dict[str, Any], errors: list[str]) -> None:
    boundary = record.get("authority_boundary", {})
    gaps = record.get("gap_refs", [])
    mappings = record.get("crate_surface_mappings", [])
    has_unverified_mapping = isinstance(mappings, list) and any(
        isinstance(mapping, dict) and mapping.get("parity_status") != "test_time_hash_parity_verified"
        for mapping in mappings
    )
    if isinstance(boundary, dict):
        runtime_claims = (
            boundary.get("pyo3_binding_present"),
            boundary.get("python_imports_rust_runtime"),
            boundary.get("rust_subprocess_invoked"),
            boundary.get("maf_cli_invoked"),
            boundary.get("runtime_certification_claimed"),
            boundary.get("rust_certifies_python_claimed"),
            boundary.get("production_binding_claimed"),
        )
        if any(runtime_claim is True for runtime_claim in runtime_claims):
            errors.append("solver_outcome cannot claim runtime parity while authority boundary is true")
    if (gaps or has_unverified_mapping) and record.get("solver_outcome") != "AwaitingEvidence":
        errors.append("solver_outcome must remain AwaitingEvidence while gap_refs or unverified mappings exist")


def _require_subset(record: dict[str, Any], field_name: str, required_values: tuple[str, ...], errors: list[str]) -> None:
    values = record.get(field_name)
    if not isinstance(values, list):
        errors.append(f"{field_name} must be a list")
        return
    observed = set(values)
    for required_value in required_values:
        if required_value not in observed:
            errors.append(f"{field_name} missing required ref: {required_value}")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments."""

    parser = argparse.ArgumentParser(description="Validate MAF receipt parity witness.")
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA_PATH), help="Path to schema JSON.")
    parser.add_argument("--witness", default=str(DEFAULT_WITNESS_PATH), help="Path to witness JSON.")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable result.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""

    args = parse_args(argv)
    schema_path = Path(args.schema)
    witness_path = Path(args.witness)
    errors = validate_maf_receipt_parity_witness(schema_path, witness_path)
    if args.json:
        print(
            json.dumps(
                {
                    "status": "failed" if errors else "passed",
                    "schema_path": workspace_display_path(schema_path),
                    "witness_path": workspace_display_path(witness_path),
                    "errors": errors,
                },
                indent=2,
                sort_keys=True,
            )
        )
    elif errors:
        for error in errors:
            print(f"[FAIL] {error}")
        print("STATUS: failed")
    else:
        print("[PASS] maf_receipt_parity_witness")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
