#!/usr/bin/env python3
"""Validate the MafAbiCliContractWitness contract.

Purpose: verify the MAF ABI/CLI boundary remains witness-only before runtime
binding can be reconsidered.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: Python standard library and schema validation helpers.
Invariants: validation is read-only; CLI execution, subprocess execution,
Rust execution, Python binding, writes, dispatch, closure, and success claims
remain denied.
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


DEFAULT_SCHEMA_PATH = WORKSPACE_ROOT / "schemas" / "maf_abi_cli_contract_witness.schema.json"
DEFAULT_WITNESS_PATH = WORKSPACE_ROOT / "examples" / "maf_abi_cli_contract_witness.foundation.json"
EXPECTED_SCHEMA_ID = "urn:mullusi:schema:maf-abi-cli-contract-witness:1"
EXPECTED_SCHEMA_TITLE = "MAF ABI CLI Contract Witness"
EXPECTED_WITNESS_VERSION = "maf_abi_cli_contract_witness.v1"
REQUIRED_SOURCE_REFS = {
    "maf/rust/Cargo.toml",
    "maf/rust/crates/maf-cli/Cargo.toml",
    "maf/rust/crates/maf-cli/src/main.rs",
    "schemas/maf_receipt_parity_witness.schema.json",
    "examples/maf_receipt_parity_witness.foundation.json",
}
REQUIRED_FUTURE_WITNESSES = {
    "witness://maf/subprocess-effect-boundary",
    "witness://maf/deterministic-fixture-parity",
    "witness://maf/failure-receipt-path",
}
REQUIRED_RECEIPT_REFS = {
    "maf_abi_cli_contract_witness_schema": "schemas/maf_abi_cli_contract_witness.schema.json",
    "maf_abi_cli_contract_witness_example": "examples/maf_abi_cli_contract_witness.foundation.json",
    "maf_abi_cli_contract_witness_validator": "scripts/validate_maf_abi_cli_contract_witness.py",
    "maf_abi_cli_contract_witness_tests": "tests/test_validate_maf_abi_cli_contract_witness.py",
    "maf_receipt_parity_witness_schema": "schemas/maf_receipt_parity_witness.schema.json",
    "worker_failure_receipt_schema": "schemas/worker_failure_receipt.schema.json",
}
REQUIRED_EVIDENCE_REFS = (
    "schemas/maf_abi_cli_contract_witness.schema.json",
    "examples/maf_abi_cli_contract_witness.foundation.json",
    "scripts/validate_maf_abi_cli_contract_witness.py",
    "tests/test_validate_maf_abi_cli_contract_witness.py",
    "docs/94_maf_abi_cli_contract_witness_contract.md",
    "schemas/maf_receipt_parity_witness.schema.json",
    "examples/maf_receipt_parity_witness.foundation.json",
    "maf/rust/crates/maf-cli/Cargo.toml",
    "maf/rust/crates/maf-cli/src/main.rs",
)
AUTHORITY_FALSE_FLAGS = (
    "cli_execution_allowed",
    "subprocess_execution_allowed",
    "rust_crate_execution_allowed",
    "python_to_rust_binding_allowed",
    "abi_stability_claim_allowed",
    "external_connector_call_allowed",
    "network_call_allowed",
    "secret_access_allowed",
    "filesystem_write_allowed",
    "runtime_dispatch_allowed",
    "terminal_closure_allowed",
    "success_claim_allowed",
)
SECRET_MARKERS = ("BEGIN PRIVATE KEY", "api_key", "access_token", "refresh_token", "client_secret")


class MafAbiCliContractWitnessError(ValueError):
    """Raised when a MafAbiCliContractWitness artifact cannot load."""


def load_json_object(json_path: Path, label: str) -> dict[str, Any]:
    path = json_path if json_path.is_absolute() else WORKSPACE_ROOT / json_path
    if not path.exists():
        raise FileNotFoundError(f"missing {label}: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise MafAbiCliContractWitnessError(f"{label} must be a JSON object")
    return payload


def canonical_source_digest(source_path: Path) -> str:
    source_text = source_path.read_text(encoding="utf-8")
    canonical_text = source_text.replace("\r\n", "\n")
    return hashlib.sha256(canonical_text.encode("utf-8")).hexdigest()


def validate_schema_artifact(schema: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if schema.get("$id") != EXPECTED_SCHEMA_ID:
        errors.append("schema $id is invalid")
    if schema.get("title") != EXPECTED_SCHEMA_TITLE:
        errors.append("schema title is invalid")
    if schema.get("additionalProperties") is not False:
        errors.append("schema root must close additional properties")
    for field_name in (
        "witness_id",
        "witness_version",
        "contract_scope",
        "source_digests",
        "cli_contract",
        "authority_boundary",
        "receipt_refs",
        "contract_summary",
        "evidence_refs",
    ):
        if field_name not in schema.get("required", []):
            errors.append(f"schema missing required field: {field_name}")
        if field_name not in schema.get("properties", {}):
            errors.append(f"schema missing property: {field_name}")
    return errors


def validate_maf_abi_cli_contract_witness_record(record: Any, schema: dict[str, Any] | None = None) -> list[str]:
    schema_payload = schema or _load_schema(DEFAULT_SCHEMA_PATH)
    errors = _validate_schema_instance(schema_payload, record)
    if not isinstance(record, dict):
        errors.append("maf abi cli contract witness must be a JSON object")
        return errors
    if record.get("witness_version") != EXPECTED_WITNESS_VERSION:
        errors.append("witness_version must match maf_abi_cli_contract_witness.v1")
    _reject_secret_markers(record, errors)
    _validate_scope(record.get("contract_scope"), errors)
    _validate_source_digests(record.get("source_digests"), errors)
    _validate_cli_contract(record.get("cli_contract"), errors)
    _validate_authority_boundary(record.get("authority_boundary"), errors)
    _validate_receipt_refs(record.get("receipt_refs"), errors)
    _require_subset(record, "evidence_refs", REQUIRED_EVIDENCE_REFS, errors)
    _validate_contract_summary(record, errors)
    return errors


def validate_maf_abi_cli_contract_witness(
    schema_path: Path = DEFAULT_SCHEMA_PATH,
    witness_path: Path = DEFAULT_WITNESS_PATH,
) -> list[str]:
    schema = _load_schema(schema_path)
    witness = load_json_object(witness_path, "MafAbiCliContractWitness")
    errors = validate_schema_artifact(schema)
    errors.extend(validate_maf_abi_cli_contract_witness_record(witness, schema))
    return errors


def build_mutated_maf_abi_cli_contract_witness(**updates: Any) -> dict[str, Any]:
    witness = load_json_object(DEFAULT_WITNESS_PATH, "MafAbiCliContractWitness")
    mutated = deepcopy(witness)
    for dotted_key, value in updates.items():
        target: Any = mutated
        segments = dotted_key.split("__")
        for segment in segments[:-1]:
            target = target[int(segment)] if isinstance(target, list) else target[segment]
        final_segment = segments[-1]
        if isinstance(target, list):
            target[int(final_segment)] = value
        else:
            target[final_segment] = value
    return mutated


def workspace_display_path(path: Path) -> str:
    resolved_path = path if path.is_absolute() else WORKSPACE_ROOT / path
    try:
        return str(resolved_path.resolve().relative_to(WORKSPACE_ROOT)).replace("\\", "/")
    except ValueError:
        return str(path)


def _validate_scope(scope: Any, errors: list[str]) -> None:
    if not isinstance(scope, dict):
        errors.append("contract_scope must be an object")
        return
    if scope.get("foundation_mode") is not True:
        errors.append("contract_scope.foundation_mode must be true")
    for flag in ("runtime_binding_claimed", "cli_execution_performed", "abi_stability_claimed"):
        if scope.get(flag) is not False:
            errors.append(f"contract_scope.{flag} must be false")
    missing = sorted(REQUIRED_FUTURE_WITNESSES - set(scope.get("required_future_witnesses") or []))
    for ref in missing:
        errors.append(f"required_future_witnesses missing required ref: {ref}")


def _validate_source_digests(source_digests: Any, errors: list[str]) -> None:
    if not isinstance(source_digests, list):
        errors.append("source_digests must be a list")
        return
    by_ref = {item.get("source_ref"): item for item in source_digests if isinstance(item, dict)}
    for source_ref in sorted(REQUIRED_SOURCE_REFS):
        item = by_ref.get(source_ref)
        if not isinstance(item, dict):
            errors.append(f"source_digests missing required source: {source_ref}")
            continue
        source_path = WORKSPACE_ROOT / source_ref
        if item.get("digest_sha256") != canonical_source_digest(source_path):
            errors.append(f"{source_ref} digest_sha256 does not match source digest")


def _validate_cli_contract(contract: Any, errors: list[str]) -> None:
    if not isinstance(contract, dict):
        errors.append("cli_contract must be an object")
        return
    if contract.get("accepted_argument_schema_ref") == "schemas/maf_abi_cli_contract_witness.schema.json":
        errors.append("accepted_argument_schema_ref cannot self-certify")
    for field_name in ("accepted_argument_schema_ref", "output_receipt_schema_ref"):
        if not str(contract.get(field_name, "")).startswith("gap://"):
            errors.append(f"cli_contract.{field_name} must remain a gap ref")
    if contract.get("failure_receipt_schema_ref") != "schemas/worker_failure_receipt.schema.json":
        errors.append("cli_contract.failure_receipt_schema_ref must be schemas/worker_failure_receipt.schema.json")


def _validate_authority_boundary(boundary: Any, errors: list[str]) -> None:
    if not isinstance(boundary, dict):
        errors.append("authority_boundary must be an object")
        return
    for flag in AUTHORITY_FALSE_FLAGS:
        if boundary.get(flag) is not False:
            errors.append(f"authority_boundary.{flag} must be false")


def _validate_receipt_refs(refs: Any, errors: list[str]) -> None:
    if not isinstance(refs, dict):
        errors.append("receipt_refs must be an object")
        return
    for key, expected_ref in REQUIRED_RECEIPT_REFS.items():
        if refs.get(key) != expected_ref:
            errors.append(f"receipt_refs.{key} must be {expected_ref}")


def _validate_contract_summary(record: dict[str, Any], errors: list[str]) -> None:
    summary = record.get("contract_summary")
    if not isinstance(summary, dict):
        errors.append("contract_summary must be an object")
        return
    boundary = record.get("authority_boundary") if isinstance(record.get("authority_boundary"), dict) else {}
    expected = {
        "source_digest_count": len(record.get("source_digests") or []),
        "authority_denial_count": sum(1 for flag in AUTHORITY_FALSE_FLAGS if boundary.get(flag) is False),
        "future_witness_count": len((record.get("contract_scope") or {}).get("required_future_witnesses") or []),
        "evidence_ref_count": len(record.get("evidence_refs") or []),
    }
    for field_name, expected_value in expected.items():
        if summary.get(field_name) != expected_value:
            errors.append(f"contract_summary.{field_name} must be {expected_value}")


def _require_subset(record: dict[str, Any], field_name: str, required_refs: tuple[str, ...], errors: list[str]) -> None:
    values = record.get(field_name)
    if not isinstance(values, list):
        errors.append(f"{field_name} must be a list")
        return
    for required_ref in required_refs:
        if required_ref not in values:
            errors.append(f"{field_name} missing required ref: {required_ref}")


def _reject_secret_markers(record: dict[str, Any], errors: list[str]) -> None:
    serialized = json.dumps(record, sort_keys=True)
    for marker in SECRET_MARKERS:
        if marker in serialized:
            errors.append(f"secret marker is not allowed in MafAbiCliContractWitness: {marker}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA_PATH)
    parser.add_argument("--witness", type=Path, default=DEFAULT_WITNESS_PATH)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    schema_path = args.schema if args.schema.is_absolute() else WORKSPACE_ROOT / args.schema
    witness_path = args.witness if args.witness.is_absolute() else WORKSPACE_ROOT / args.witness
    errors = validate_maf_abi_cli_contract_witness(schema_path, witness_path)
    if args.json:
        print(json.dumps({
            "status": "passed" if not errors else "failed",
            "schema_path": workspace_display_path(schema_path),
            "witness_path": workspace_display_path(witness_path),
            "errors": errors,
        }, indent=2, sort_keys=True))
    elif errors:
        print("[FAIL] MafAbiCliContractWitness validation failed:")
        for error in errors:
            print(f"- {error}")
    else:
        print("[PASS] MafAbiCliContractWitness validation passed")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
