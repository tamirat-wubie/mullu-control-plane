#!/usr/bin/env python3
"""Validate the MafAbiCliContractWitness contract.

Purpose: verify that the MAF CLI/ABI contract is recorded as scaffold-only
static evidence without claiming command execution, subprocess, PyO3, or
runtime binding authority.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: Python standard library and schema validation helpers.
Invariants:
  - Validation is read-only and deterministic.
  - CLI execution, subprocess execution, PyO3, and Rust execution remain denied.
  - Command behavior remains AwaitingEvidence until executable witnesses exist.
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
EXPECTED_CONTRACT_MODE = "scaffold_only_static_cli_contract"
REQUIRED_FUTURE_WITNESSES = {
    "witness://maf/subprocess-effect-boundary",
    "witness://maf/deterministic-fixture-parity",
    "witness://maf/failure-receipt-path",
}
REQUIRED_CLI_ARTIFACTS = {
    "maf/rust/Cargo.toml": "workspace_manifest",
    "maf/rust/crates/maf-cli/Cargo.toml": "cli_manifest",
    "maf/rust/crates/maf-cli/src/main.rs": "cli_entry",
    "schemas/maf_receipt_parity_witness.schema.json": "parity_witness",
    "maf/MAF_BOUNDARY.md": "boundary_doc",
}
REQUIRED_COMMANDS = {
    "verify-receipt-chain",
    "verify-kernel-proof",
    "emit-transition-receipt",
}
REQUIRED_RECEIPT_REFS = {
    "maf_abi_cli_contract_witness_schema": "schemas/maf_abi_cli_contract_witness.schema.json",
    "maf_abi_cli_contract_witness_example": "examples/maf_abi_cli_contract_witness.foundation.json",
    "maf_abi_cli_contract_witness_validator": "scripts/validate_maf_abi_cli_contract_witness.py",
    "maf_abi_cli_contract_witness_tests": "tests/test_validate_maf_abi_cli_contract_witness.py",
    "maf_receipt_parity_witness_schema": "schemas/maf_receipt_parity_witness.schema.json",
    "maf_receipt_parity_witness_example": "examples/maf_receipt_parity_witness.foundation.json",
    "maf_boundary_doc": "maf/MAF_BOUNDARY.md",
    "maf_receipt_coverage_doc": "docs/MAF_RECEIPT_COVERAGE.md",
    "rust_workspace_manifest": "maf/rust/Cargo.toml",
    "rust_cli_manifest": "maf/rust/crates/maf-cli/Cargo.toml",
    "rust_cli_entry": "maf/rust/crates/maf-cli/src/main.rs",
    "universal_action_orchestration_schema": "schemas/universal_action_orchestration.schema.json",
    "life_meaning_judgment_schema": "schemas/life_meaning_judgment.schema.json",
    "worker_failure_receipt_schema": "schemas/worker_failure_receipt.schema.json",
}
REQUIRED_EVIDENCE_REFS = (
    "schemas/maf_abi_cli_contract_witness.schema.json",
    "examples/maf_abi_cli_contract_witness.foundation.json",
    "scripts/validate_maf_abi_cli_contract_witness.py",
    "tests/test_validate_maf_abi_cli_contract_witness.py",
    "docs/94_maf_abi_cli_contract_witness.md",
    "docs/82_cross_repo_opportunity_map.md",
    "docs/93_maf_receipt_parity_witness_contract.md",
    "schemas/maf_receipt_parity_witness.schema.json",
    "examples/maf_receipt_parity_witness.foundation.json",
    "docs/MAF_RECEIPT_COVERAGE.md",
    "maf/MAF_BOUNDARY.md",
    "maf/rust/Cargo.toml",
    "maf/rust/crates/maf-cli/Cargo.toml",
    "maf/rust/crates/maf-cli/src/main.rs",
    "examples/sdlc/requirement_maf_abi_cli_contract_witness_20260618.json",
    "examples/sdlc/design_maf_abi_cli_contract_witness_20260618.json",
    "examples/sdlc/security_review_maf_abi_cli_contract_witness_20260618.json",
)
AUTHORITY_FALSE_FLAGS = (
    "cli_execution_allowed",
    "subprocess_execution_allowed",
    "pyo3_binding_allowed",
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


class MafAbiCliContractWitnessError(ValueError):
    """Raised when a MafAbiCliContractWitness artifact cannot load."""


def load_json_object(json_path: Path, label: str) -> dict[str, Any]:
    """Load one JSON object from disk."""

    path = json_path if json_path.is_absolute() else WORKSPACE_ROOT / json_path
    if not path.exists():
        raise FileNotFoundError(f"missing {label}: {path}")
    if not path.is_file():
        raise IsADirectoryError(f"{label} path is not a file: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise MafAbiCliContractWitnessError(f"{label} must be a JSON object")
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
            "abi_scope",
            "cli_artifacts",
            "command_contracts",
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


def validate_maf_abi_cli_contract_witness_record(
    record: Any,
    schema: dict[str, Any] | None = None,
) -> list[str]:
    """Return deterministic validation errors for one ABI/CLI witness."""

    schema_payload = schema or _load_schema(DEFAULT_SCHEMA_PATH)
    errors = _validate_schema_instance(schema_payload, record)
    if not isinstance(record, dict):
        errors.append("maf ABI CLI contract witness must be a JSON object")
        return errors

    if record.get("witness_version") != EXPECTED_WITNESS_VERSION:
        errors.append("witness_version must match maf_abi_cli_contract_witness.v1")

    _reject_secret_markers(record, errors)
    _validate_abi_scope(record.get("abi_scope"), errors)
    _validate_cli_artifacts(record.get("cli_artifacts"), errors)
    _validate_command_contracts(record.get("command_contracts"), errors)
    _validate_authority_boundary(record.get("authority_boundary"), errors)
    _validate_contract_summary(record, errors)
    _validate_receipt_refs(record.get("receipt_refs"), errors)
    _require_subset(record, "evidence_refs", REQUIRED_EVIDENCE_REFS, errors)
    _validate_solver_outcome(record, errors)
    return errors


def validate_maf_abi_cli_contract_witness(
    schema_path: Path = DEFAULT_SCHEMA_PATH,
    witness_path: Path = DEFAULT_WITNESS_PATH,
) -> list[str]:
    """Validate the schema artifact and default Foundation Mode witness."""

    schema = _load_schema(schema_path)
    witness = load_json_object(witness_path, "MafAbiCliContractWitness")
    errors = validate_schema_artifact(schema)
    errors.extend(validate_maf_abi_cli_contract_witness_record(witness, schema))
    return errors


def build_mutated_maf_abi_cli_contract_witness(**updates: Any) -> dict[str, Any]:
    """Build a deterministic mutated copy of the default witness."""

    witness = load_json_object(DEFAULT_WITNESS_PATH, "MafAbiCliContractWitness")
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


def _validate_abi_scope(scope: Any, errors: list[str]) -> None:
    if not isinstance(scope, dict):
        errors.append("abi_scope must be an object")
        return
    if scope.get("foundation_mode") is not True:
        errors.append("abi_scope.foundation_mode must be true")
    if scope.get("contract_mode") != EXPECTED_CONTRACT_MODE:
        errors.append("abi_scope.contract_mode must be scaffold_only_static_cli_contract")
    if scope.get("cli_scaffold_only") is not True:
        errors.append("abi_scope.cli_scaffold_only must be true")
    for flag in ("runtime_binding_claimed", "command_behavior_claimed", "subprocess_effect_boundary_closed"):
        if scope.get(flag) is not False:
            errors.append(f"abi_scope.{flag} must be false")
    future_witnesses = set(scope.get("required_future_witnesses") or [])
    for ref in sorted(REQUIRED_FUTURE_WITNESSES - future_witnesses):
        errors.append(f"required_future_witnesses missing required ref: {ref}")


def _validate_cli_artifacts(artifacts: Any, errors: list[str]) -> None:
    if not isinstance(artifacts, list):
        errors.append("cli_artifacts must be a list")
        return
    by_ref = {artifact.get("artifact_ref"): artifact for artifact in artifacts if isinstance(artifact, dict)}
    for artifact_ref, artifact_role in sorted(REQUIRED_CLI_ARTIFACTS.items()):
        artifact = by_ref.get(artifact_ref)
        if not isinstance(artifact, dict):
            errors.append(f"cli_artifacts missing required artifact: {artifact_ref}")
            continue
        if artifact.get("artifact_role") != artifact_role:
            errors.append(f"{artifact_ref} artifact_role must be {artifact_role}")
        if artifact.get("execution_authority_denied") is not True:
            errors.append(f"{artifact_ref} execution_authority_denied must be true")
        _validate_digest_field(artifact, "artifact_digest_sha256", artifact_ref, errors)


def _validate_command_contracts(command_contracts: Any, errors: list[str]) -> None:
    if not isinstance(command_contracts, list):
        errors.append("command_contracts must be a list")
        return
    by_name = {
        command.get("command_name"): command
        for command in command_contracts
        if isinstance(command, dict)
    }
    for command_name in sorted(REQUIRED_COMMANDS):
        if command_name not in by_name:
            errors.append(f"command_contracts missing required command: {command_name}")
    for command in command_contracts:
        if not isinstance(command, dict):
            errors.append("command_contract entries must be objects")
            continue
        if command.get("availability_status") != "AwaitingEvidence":
            errors.append(f"{command.get('command_id')} availability_status must be AwaitingEvidence")
        if command.get("execution_allowed") is not False:
            errors.append(f"{command.get('command_id')} execution_allowed must be false")
        gap_refs = command.get("gap_refs")
        if not isinstance(gap_refs, list) or not gap_refs:
            errors.append(f"{command.get('command_id')} gap_refs required")
        if not any("cli-command-not-implemented" in str(ref) for ref in gap_refs or []):
            errors.append(f"{command.get('command_id')} must retain cli-command-not-implemented gap")


def _validate_authority_boundary(boundary: Any, errors: list[str]) -> None:
    if not isinstance(boundary, dict):
        errors.append("authority_boundary must be an object")
        return
    if boundary.get("static_contract_read_allowed") is not True:
        errors.append("authority_boundary.static_contract_read_allowed must be true")
    for flag in AUTHORITY_FALSE_FLAGS:
        if boundary.get(flag) is not False:
            errors.append(f"authority_boundary.{flag} must be false")


def _validate_contract_summary(record: dict[str, Any], errors: list[str]) -> None:
    summary = record.get("contract_summary")
    if not isinstance(summary, dict):
        errors.append("contract_summary must be an object")
        return
    authority_boundary = record.get("authority_boundary") if isinstance(record.get("authority_boundary"), dict) else {}
    expected_counts = {
        "cli_artifact_count": len(record.get("cli_artifacts") or []),
        "command_contract_count": len(record.get("command_contracts") or []),
        "authority_denial_count": sum(1 for flag in AUTHORITY_FALSE_FLAGS if authority_boundary.get(flag) is False),
        "awaiting_gap_count": sum(
            len(command.get("gap_refs") or [])
            for command in record.get("command_contracts", [])
            if isinstance(command, dict)
        ),
        "evidence_ref_count": len(record.get("evidence_refs") or []),
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
    if record.get("solver_outcome") != "AwaitingEvidence":
        errors.append("solver_outcome must remain AwaitingEvidence while CLI execution is unavailable")
    scope = record.get("abi_scope") if isinstance(record.get("abi_scope"), dict) else {}
    if scope.get("runtime_binding_claimed") is not False or scope.get("command_behavior_claimed") is not False:
        errors.append("runtime binding and command behavior must remain unclaimed")


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
            errors.append(f"secret marker is not allowed in MafAbiCliContractWitness: {marker}")


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
    errors = validate_maf_abi_cli_contract_witness(schema_path, witness_path)

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
        print("[FAIL] MafAbiCliContractWitness validation failed:")
        print(_format_errors(errors))
    else:
        print("[PASS] MafAbiCliContractWitness validation passed")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
