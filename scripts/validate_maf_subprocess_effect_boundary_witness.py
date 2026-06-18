#!/usr/bin/env python3
"""Validate the MafSubprocessEffectBoundaryWitness contract.

Purpose: verify that the MAF subprocess effect-boundary envelope is recorded
as denied-by-default static evidence without invoking subprocesses, CLI
commands, shell behavior, Rust execution, runtime dispatch, or raw output
retention.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: Python standard library and schema validation helpers.
Invariants:
  - Validation is read-only and deterministic.
  - Subprocess execution, shell invocation, child process spawn, and CLI execution remain denied.
  - Runtime binding remains AwaitingEvidence until fixture parity and failure receipt witnesses exist.
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


DEFAULT_SCHEMA_PATH = WORKSPACE_ROOT / "schemas" / "maf_subprocess_effect_boundary_witness.schema.json"
DEFAULT_WITNESS_PATH = WORKSPACE_ROOT / "examples" / "maf_subprocess_effect_boundary_witness.foundation.json"
EXPECTED_SCHEMA_ID = "urn:mullusi:schema:maf-subprocess-effect-boundary-witness:1"
EXPECTED_SCHEMA_TITLE = "MAF Subprocess Effect Boundary Witness"
EXPECTED_WITNESS_VERSION = "maf_subprocess_effect_boundary_witness.v1"
EXPECTED_BOUNDARY_MODE = "denied_by_default_subprocess_effect_boundary"
REQUIRED_FUTURE_WITNESSES = {
    "witness://maf/deterministic-fixture-parity",
    "witness://maf/failure-receipt-path",
}
CLOSED_WITNESS_REFS = {
    "witness://maf/subprocess-effect-boundary",
}
REQUIRED_SOURCE_ARTIFACTS = {
    "schemas/maf_abi_cli_contract_witness.schema.json": "abi_cli_contract",
    "examples/maf_abi_cli_contract_witness.foundation.json": "abi_cli_example",
    "scripts/validate_maf_abi_cli_contract_witness.py": "abi_cli_validator",
    "tests/test_validate_maf_abi_cli_contract_witness.py": "abi_cli_tests",
    "maf/rust/Cargo.toml": "workspace_manifest",
    "maf/rust/crates/maf-cli/Cargo.toml": "cli_manifest",
    "maf/rust/crates/maf-cli/src/main.rs": "cli_entry",
}
REQUIRED_CONTROL_FAMILIES = {
    "command_resolution",
    "argv",
    "cwd",
    "environment",
    "stdin",
    "stdout",
    "stderr",
    "timeout",
    "exit_code",
    "filesystem",
    "process_network",
    "receipt_failure",
}
REQUIRED_RECEIPT_REFS = {
    "maf_subprocess_effect_boundary_witness_schema": "schemas/maf_subprocess_effect_boundary_witness.schema.json",
    "maf_subprocess_effect_boundary_witness_example": "examples/maf_subprocess_effect_boundary_witness.foundation.json",
    "maf_subprocess_effect_boundary_witness_validator": "scripts/validate_maf_subprocess_effect_boundary_witness.py",
    "maf_subprocess_effect_boundary_witness_tests": "tests/test_validate_maf_subprocess_effect_boundary_witness.py",
    "maf_subprocess_effect_boundary_witness_doc": "docs/95_maf_subprocess_effect_boundary_witness.md",
    "maf_abi_cli_contract_witness_schema": "schemas/maf_abi_cli_contract_witness.schema.json",
    "maf_abi_cli_contract_witness_example": "examples/maf_abi_cli_contract_witness.foundation.json",
    "maf_abi_cli_contract_witness_validator": "scripts/validate_maf_abi_cli_contract_witness.py",
    "maf_abi_cli_contract_witness_tests": "tests/test_validate_maf_abi_cli_contract_witness.py",
    "maf_receipt_parity_witness_schema": "schemas/maf_receipt_parity_witness.schema.json",
    "maf_receipt_parity_witness_example": "examples/maf_receipt_parity_witness.foundation.json",
    "maf_boundary_doc": "maf/MAF_BOUNDARY.md",
    "rust_workspace_manifest": "maf/rust/Cargo.toml",
    "rust_cli_manifest": "maf/rust/crates/maf-cli/Cargo.toml",
    "rust_cli_entry": "maf/rust/crates/maf-cli/src/main.rs",
    "universal_action_orchestration_schema": "schemas/universal_action_orchestration.schema.json",
    "life_meaning_judgment_schema": "schemas/life_meaning_judgment.schema.json",
    "worker_failure_receipt_schema": "schemas/worker_failure_receipt.schema.json",
}
REQUIRED_EVIDENCE_REFS = (
    "schemas/maf_subprocess_effect_boundary_witness.schema.json",
    "examples/maf_subprocess_effect_boundary_witness.foundation.json",
    "scripts/validate_maf_subprocess_effect_boundary_witness.py",
    "tests/test_validate_maf_subprocess_effect_boundary_witness.py",
    "docs/95_maf_subprocess_effect_boundary_witness.md",
    "docs/82_cross_repo_opportunity_map.md",
    "docs/94_maf_abi_cli_contract_witness.md",
    "docs/93_maf_receipt_parity_witness_contract.md",
    "schemas/maf_abi_cli_contract_witness.schema.json",
    "examples/maf_abi_cli_contract_witness.foundation.json",
    "scripts/validate_maf_abi_cli_contract_witness.py",
    "tests/test_validate_maf_abi_cli_contract_witness.py",
    "schemas/maf_receipt_parity_witness.schema.json",
    "examples/maf_receipt_parity_witness.foundation.json",
    "docs/MAF_RECEIPT_COVERAGE.md",
    "maf/MAF_BOUNDARY.md",
    "maf/rust/Cargo.toml",
    "maf/rust/crates/maf-cli/Cargo.toml",
    "maf/rust/crates/maf-cli/src/main.rs",
    "examples/sdlc/requirement_maf_subprocess_effect_boundary_witness_20260618.json",
    "examples/sdlc/design_maf_subprocess_effect_boundary_witness_20260618.json",
    "examples/sdlc/security_review_maf_subprocess_effect_boundary_witness_20260618.json",
)
AUTHORITY_FALSE_FLAGS = (
    "cli_execution_allowed",
    "subprocess_execution_allowed",
    "runtime_binding_allowed",
    "pyo3_binding_allowed",
    "rust_crate_execution_allowed",
    "python_imports_rust_allowed",
    "shell_invocation_allowed",
    "child_process_spawn_allowed",
    "network_call_allowed",
    "secret_access_allowed",
    "environment_secret_allowed",
    "stdin_secret_allowed",
    "raw_stdout_retention_allowed",
    "raw_stderr_retention_allowed",
    "filesystem_write_allowed",
    "runtime_dispatch_allowed",
    "canonical_state_mutation_allowed",
    "terminal_closure_allowed",
    "success_claim_allowed",
)
SECRET_MARKERS = ("BEGIN PRIVATE KEY", "api_key", "access_token", "refresh_token", "client_secret")


class MafSubprocessEffectBoundaryWitnessError(ValueError):
    """Raised when a MafSubprocessEffectBoundaryWitness artifact cannot load."""


def load_json_object(json_path: Path, label: str) -> dict[str, Any]:
    """Load one JSON object from disk."""

    path = json_path if json_path.is_absolute() else WORKSPACE_ROOT / json_path
    if not path.exists():
        raise FileNotFoundError(f"missing {label}: {path}")
    if not path.is_file():
        raise IsADirectoryError(f"{label} path is not a file: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise MafSubprocessEffectBoundaryWitnessError(f"{label} must be a JSON object")
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
            "boundary_scope",
            "source_artifacts",
            "effect_controls",
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


def validate_maf_subprocess_effect_boundary_witness_record(
    record: Any,
    schema: dict[str, Any] | None = None,
) -> list[str]:
    """Return deterministic validation errors for one subprocess boundary witness."""

    schema_payload = schema or _load_schema(DEFAULT_SCHEMA_PATH)
    errors = _validate_schema_instance(schema_payload, record)
    if not isinstance(record, dict):
        errors.append("maf subprocess effect boundary witness must be a JSON object")
        return errors

    if record.get("witness_version") != EXPECTED_WITNESS_VERSION:
        errors.append("witness_version must match maf_subprocess_effect_boundary_witness.v1")

    _reject_secret_markers(record, errors)
    _validate_boundary_scope(record.get("boundary_scope"), errors)
    _validate_source_artifacts(record.get("source_artifacts"), errors)
    _validate_effect_controls(record.get("effect_controls"), errors)
    _validate_authority_boundary(record.get("authority_boundary"), errors)
    _validate_contract_summary(record, errors)
    _validate_receipt_refs(record.get("receipt_refs"), errors)
    _require_subset(record, "evidence_refs", REQUIRED_EVIDENCE_REFS, errors)
    _validate_solver_outcome(record, errors)
    return errors


def validate_maf_subprocess_effect_boundary_witness(
    schema_path: Path = DEFAULT_SCHEMA_PATH,
    witness_path: Path = DEFAULT_WITNESS_PATH,
) -> list[str]:
    """Validate the schema artifact and default Foundation Mode witness."""

    schema = _load_schema(schema_path)
    witness = load_json_object(witness_path, "MafSubprocessEffectBoundaryWitness")
    errors = validate_schema_artifact(schema)
    errors.extend(validate_maf_subprocess_effect_boundary_witness_record(witness, schema))
    return errors


def build_mutated_maf_subprocess_effect_boundary_witness(**updates: Any) -> dict[str, Any]:
    """Build a deterministic mutated copy of the default witness."""

    witness = load_json_object(DEFAULT_WITNESS_PATH, "MafSubprocessEffectBoundaryWitness")
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


def _validate_boundary_scope(scope: Any, errors: list[str]) -> None:
    if not isinstance(scope, dict):
        errors.append("boundary_scope must be an object")
        return
    if scope.get("foundation_mode") is not True:
        errors.append("boundary_scope.foundation_mode must be true")
    if scope.get("boundary_mode") != EXPECTED_BOUNDARY_MODE:
        errors.append("boundary_scope.boundary_mode must be denied_by_default_subprocess_effect_boundary")
    if scope.get("subprocess_effect_boundary_closed") is not True:
        errors.append("boundary_scope.subprocess_effect_boundary_closed must be true")
    for flag in ("runtime_binding_claimed", "subprocess_execution_claimed"):
        if scope.get(flag) is not False:
            errors.append(f"boundary_scope.{flag} must be false")
    future_witnesses = set(scope.get("required_future_witnesses") or [])
    for ref in sorted(REQUIRED_FUTURE_WITNESSES - future_witnesses):
        errors.append(f"required_future_witnesses missing required ref: {ref}")
    for ref in sorted(CLOSED_WITNESS_REFS & future_witnesses):
        errors.append(f"required_future_witnesses must not retain closed ref: {ref}")


def _validate_source_artifacts(artifacts: Any, errors: list[str]) -> None:
    if not isinstance(artifacts, list):
        errors.append("source_artifacts must be a list")
        return
    by_ref = {artifact.get("artifact_ref"): artifact for artifact in artifacts if isinstance(artifact, dict)}
    for artifact_ref, artifact_role in sorted(REQUIRED_SOURCE_ARTIFACTS.items()):
        artifact = by_ref.get(artifact_ref)
        if not isinstance(artifact, dict):
            errors.append(f"source_artifacts missing required artifact: {artifact_ref}")
            continue
        if artifact.get("artifact_role") != artifact_role:
            errors.append(f"{artifact_ref} artifact_role must be {artifact_role}")
        if artifact.get("execution_authority_denied") is not True:
            errors.append(f"{artifact_ref} execution_authority_denied must be true")
        _validate_digest_field(artifact, "artifact_digest_sha256", artifact_ref, errors)


def _validate_effect_controls(effect_controls: Any, errors: list[str]) -> None:
    if not isinstance(effect_controls, list):
        errors.append("effect_controls must be a list")
        return
    families = {
        control.get("control_family")
        for control in effect_controls
        if isinstance(control, dict)
    }
    for family in sorted(REQUIRED_CONTROL_FAMILIES - families):
        errors.append(f"effect_controls missing required control_family: {family}")
    for control in effect_controls:
        if not isinstance(control, dict):
            errors.append("effect_controls entries must be objects")
            continue
        control_id = control.get("control_id")
        if control.get("boundary_status") != "denied_until_witnessed":
            errors.append(f"{control_id} boundary_status must be denied_until_witnessed")
        if control.get("execution_allowed") is not False:
            errors.append(f"{control_id} execution_allowed must be false")
        if control.get("raw_retention_allowed") is not False:
            errors.append(f"{control_id} raw_retention_allowed must be false")
        policy_ref = control.get("policy_ref")
        if not isinstance(policy_ref, str) or not policy_ref.startswith("policy://maf/subprocess/"):
            errors.append(f"{control_id} policy_ref must use policy://maf/subprocess/")
        gap_refs = control.get("gap_refs")
        if not isinstance(gap_refs, list) or not gap_refs:
            errors.append(f"{control_id} gap_refs required")
            continue
        if any(ref == "gap://maf/subprocess-effect-boundary-open" for ref in gap_refs):
            errors.append(f"{control_id} must not retain subprocess-effect-boundary-open gap")
        if not any(ref in {"gap://maf/deterministic-fixture-parity-open", "gap://maf/failure-receipt-path-open"} for ref in gap_refs):
            errors.append(f"{control_id} must bind fixture-parity or failure-receipt gap")


def _validate_authority_boundary(boundary: Any, errors: list[str]) -> None:
    if not isinstance(boundary, dict):
        errors.append("authority_boundary must be an object")
        return
    if boundary.get("static_boundary_read_allowed") is not True:
        errors.append("authority_boundary.static_boundary_read_allowed must be true")
    for flag in AUTHORITY_FALSE_FLAGS:
        if boundary.get(flag) is not False:
            errors.append(f"authority_boundary.{flag} must be false")


def _validate_contract_summary(record: dict[str, Any], errors: list[str]) -> None:
    summary = record.get("contract_summary")
    if not isinstance(summary, dict):
        errors.append("contract_summary must be an object")
        return
    authority_boundary = record.get("authority_boundary") if isinstance(record.get("authority_boundary"), dict) else {}
    future_witnesses = []
    scope = record.get("boundary_scope")
    if isinstance(scope, dict) and isinstance(scope.get("required_future_witnesses"), list):
        future_witnesses = scope["required_future_witnesses"]
    expected_counts = {
        "source_artifact_count": len(record.get("source_artifacts") or []),
        "effect_control_count": len(record.get("effect_controls") or []),
        "authority_denial_count": sum(1 for flag in AUTHORITY_FALSE_FLAGS if authority_boundary.get(flag) is False),
        "open_gap_count": len(set(future_witnesses)),
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
        errors.append("solver_outcome must remain AwaitingEvidence while runtime execution is unavailable")
    scope = record.get("boundary_scope") if isinstance(record.get("boundary_scope"), dict) else {}
    if scope.get("runtime_binding_claimed") is not False or scope.get("subprocess_execution_claimed") is not False:
        errors.append("runtime binding and subprocess execution must remain unclaimed")


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
            errors.append(f"secret marker is not allowed in MafSubprocessEffectBoundaryWitness: {marker}")


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
    errors = validate_maf_subprocess_effect_boundary_witness(schema_path, witness_path)

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
        print("[FAIL] MafSubprocessEffectBoundaryWitness validation failed:")
        print(_format_errors(errors))
    else:
        print("[PASS] MafSubprocessEffectBoundaryWitness validation passed")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
