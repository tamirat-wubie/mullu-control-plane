#!/usr/bin/env python3
"""Validate the MafDeterministicFixtureParityWitness contract.

Purpose: verify that MAF deterministic fixture parity is static, digest-only,
and read-only before any runtime binding or subprocess execution can be claimed.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: Python standard library and schema validation helpers.
Invariants:
  - Validation is read-only and deterministic.
  - Fixture parity closes only static descriptor parity.
  - Runtime binding, subprocess execution, CLI execution, writes, raw payloads,
    terminal closure, and success claims remain denied.
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


DEFAULT_SCHEMA_PATH = WORKSPACE_ROOT / "schemas" / "maf_deterministic_fixture_parity_witness.schema.json"
DEFAULT_WITNESS_PATH = WORKSPACE_ROOT / "examples" / "maf_deterministic_fixture_parity_witness.foundation.json"
EXPECTED_SCHEMA_ID = "urn:mullusi:schema:maf-deterministic-fixture-parity-witness:1"
EXPECTED_SCHEMA_TITLE = "MAF Deterministic Fixture Parity Witness"
EXPECTED_WITNESS_VERSION = "maf_deterministic_fixture_parity_witness.v1"
EXPECTED_PARITY_MODE = "static_digest_fixture_parity"
REQUIRED_REMAINING_WITNESSES = {"witness://maf/failure-receipt-path"}
CLOSED_WITNESS_REFS = {"witness://maf/deterministic-fixture-parity"}
FORBIDDEN_FUTURE_WITNESSES = {"witness://maf/deterministic-fixture-parity"}
REQUIRED_SOURCE_ARTIFACTS = {
    "schemas/maf_subprocess_effect_boundary_witness.schema.json": "subprocess_effect_boundary_schema",
    "examples/maf_subprocess_effect_boundary_witness.foundation.json": "subprocess_effect_boundary_example",
    "scripts/validate_maf_subprocess_effect_boundary_witness.py": "subprocess_effect_boundary_validator",
    "tests/test_validate_maf_subprocess_effect_boundary_witness.py": "subprocess_effect_boundary_tests",
    "maf/rust/crates/maf-cli/src/main.rs": "cli_entry",
    "schemas/worker_failure_receipt.schema.json": "failure_receipt_schema",
    "schemas/verification_result.schema.json": "verification_result_schema",
    "schemas/sdlc_transition_receipt.schema.json": "transition_receipt_schema",
    "schemas/kernel_proof.schema.json": "kernel_proof_schema",
}
REQUIRED_FIXTURE_DESCRIPTORS = {
    "verify-receipt-chain": {
        "input_contract_ref": "schemas/worker_failure_receipt.schema.json",
        "expected_output_contract_ref": "schemas/verification_result.schema.json",
        "fixture_material_ref": "fixture://maf/verify-receipt-chain/static-digest-v1",
    },
    "verify-kernel-proof": {
        "input_contract_ref": "schemas/kernel_proof.schema.json",
        "expected_output_contract_ref": "schemas/verification_result.schema.json",
        "fixture_material_ref": "fixture://maf/verify-kernel-proof/static-digest-v1",
    },
    "emit-transition-receipt": {
        "input_contract_ref": "schemas/sdlc_transition_receipt.schema.json",
        "expected_output_contract_ref": "schemas/worker_failure_receipt.schema.json",
        "fixture_material_ref": "fixture://maf/emit-transition-receipt/static-digest-v1",
    },
}
REQUIRED_RECEIPT_REFS = {
    "maf_deterministic_fixture_parity_witness_schema": "schemas/maf_deterministic_fixture_parity_witness.schema.json",
    "maf_deterministic_fixture_parity_witness_example": "examples/maf_deterministic_fixture_parity_witness.foundation.json",
    "maf_deterministic_fixture_parity_witness_validator": "scripts/validate_maf_deterministic_fixture_parity_witness.py",
    "maf_deterministic_fixture_parity_witness_tests": "tests/test_validate_maf_deterministic_fixture_parity_witness.py",
    "maf_deterministic_fixture_parity_witness_doc": "docs/96_maf_deterministic_fixture_parity_witness.md",
    "maf_subprocess_effect_boundary_witness_schema": "schemas/maf_subprocess_effect_boundary_witness.schema.json",
    "maf_subprocess_effect_boundary_witness_example": "examples/maf_subprocess_effect_boundary_witness.foundation.json",
    "maf_subprocess_effect_boundary_witness_validator": "scripts/validate_maf_subprocess_effect_boundary_witness.py",
    "maf_subprocess_effect_boundary_witness_tests": "tests/test_validate_maf_subprocess_effect_boundary_witness.py",
    "rust_cli_entry": "maf/rust/crates/maf-cli/src/main.rs",
    "universal_action_orchestration_schema": "schemas/universal_action_orchestration.schema.json",
    "life_meaning_judgment_schema": "schemas/life_meaning_judgment.schema.json",
    "worker_failure_receipt_schema": "schemas/worker_failure_receipt.schema.json",
    "verification_result_schema": "schemas/verification_result.schema.json",
    "sdlc_transition_receipt_schema": "schemas/sdlc_transition_receipt.schema.json",
    "kernel_proof_schema": "schemas/kernel_proof.schema.json",
}
FALSE_AUTHORITY_FLAGS = {
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
    "raw_fixture_payload_retention_allowed",
    "filesystem_write_allowed",
    "runtime_dispatch_allowed",
    "canonical_state_mutation_allowed",
    "terminal_closure_allowed",
    "success_claim_allowed",
}
SECRET_MARKERS = ("secret", "token", "password", "private_key", "credential")


def canonical_source_digest(path: Path) -> str:
    text = path.read_text(encoding="utf-8").replace("\r\n", "\n").replace("\r", "\n")
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def canonical_fixture_digest(vector: dict[str, Any]) -> str:
    descriptor = "|".join(
        [
            str(vector.get("command_name", "")),
            str(vector.get("input_contract_ref", "")),
            str(vector.get("expected_output_contract_ref", "")),
            str(vector.get("fixture_material_ref", "")),
        ]
    )
    return hashlib.sha256(descriptor.encode("utf-8")).hexdigest()


def load_json_object(path: Path, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"{label} at {path} is not valid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"{label} at {path} must be a JSON object")
    return payload


def _set_nested_value(record: dict[str, Any], dotted_key: str, value: Any) -> None:
    parts = dotted_key.split("__")
    current: Any = record
    for part in parts[:-1]:
        current = current[part]
    current[parts[-1]] = value


def build_mutated_maf_deterministic_fixture_parity_witness(**overrides: Any) -> dict[str, Any]:
    record = deepcopy(load_json_object(DEFAULT_WITNESS_PATH, "MafDeterministicFixtureParityWitness"))
    for dotted_key, value in overrides.items():
        _set_nested_value(record, dotted_key, value)
    return record


def _validate_schema_contract(schema_path: Path, witness: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    schema = _load_schema(schema_path)
    if schema.get("$id") != EXPECTED_SCHEMA_ID:
        errors.append(f"schema $id must be {EXPECTED_SCHEMA_ID}")
    if schema.get("title") != EXPECTED_SCHEMA_TITLE:
        errors.append(f"schema title must be {EXPECTED_SCHEMA_TITLE}")
    errors.extend(_validate_schema_instance(schema, witness, str(DEFAULT_WITNESS_PATH)))
    return errors


def _validate_parity_scope(witness: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    scope = witness.get("parity_scope", {})
    if witness.get("witness_version") != EXPECTED_WITNESS_VERSION:
        errors.append(f"witness_version must be {EXPECTED_WITNESS_VERSION}")
    if witness.get("solver_outcome") != "AwaitingEvidence":
        errors.append("solver_outcome must remain AwaitingEvidence")
    if scope.get("foundation_mode") is not True:
        errors.append("foundation_mode must be true")
    if scope.get("parity_mode") != EXPECTED_PARITY_MODE:
        errors.append(f"parity_mode must be {EXPECTED_PARITY_MODE}")
    if scope.get("deterministic_fixture_parity_closed") is not True:
        errors.append("deterministic_fixture_parity_closed must be true")
    for flag in (
        "runtime_binding_claimed",
        "subprocess_execution_claimed",
        "cli_execution_claimed",
        "command_behavior_claimed",
    ):
        if scope.get(flag) is not False:
            errors.append(f"{flag} must remain false")
    future_witnesses = set(scope.get("required_future_witnesses", []))
    if future_witnesses != REQUIRED_REMAINING_WITNESSES:
        errors.append("required_future_witnesses must contain only the failure receipt path witness")
    forbidden = future_witnesses & FORBIDDEN_FUTURE_WITNESSES
    if forbidden:
        errors.append(f"closed fixture parity witness must not remain future: {sorted(forbidden)}")
    return errors


def _validate_source_artifacts(witness: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    artifacts = witness.get("source_artifacts", [])
    by_ref = {artifact.get("artifact_ref"): artifact for artifact in artifacts}
    for artifact_ref, expected_role in REQUIRED_SOURCE_ARTIFACTS.items():
        artifact = by_ref.get(artifact_ref)
        if artifact is None:
            errors.append(f"missing source artifact {artifact_ref}")
            continue
        if artifact.get("artifact_role") != expected_role:
            errors.append(f"{artifact_ref} artifact_role must be {expected_role}")
        if artifact.get("execution_authority_denied") is not True:
            errors.append(f"{artifact_ref} must deny execution authority")
        expected_digest = canonical_source_digest(WORKSPACE_ROOT / artifact_ref)
        if artifact.get("artifact_digest_sha256") != expected_digest:
            errors.append(f"{artifact_ref} digest drift: expected {expected_digest}")
    return errors


def _validate_fixture_vectors(witness: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    vectors = witness.get("fixture_vectors", [])
    by_command = {vector.get("command_name"): vector for vector in vectors}
    if set(by_command) != set(REQUIRED_FIXTURE_DESCRIPTORS):
        errors.append("fixture_vectors must cover exactly the required MAF command descriptors")
    for command_name, descriptor in REQUIRED_FIXTURE_DESCRIPTORS.items():
        vector = by_command.get(command_name)
        if vector is None:
            errors.append(f"missing fixture vector for {command_name}")
            continue
        for field_name, expected_value in descriptor.items():
            if vector.get(field_name) != expected_value:
                errors.append(f"{command_name} {field_name} must be {expected_value}")
        if vector.get("execution_allowed") is not False:
            errors.append(f"{command_name} execution_allowed must remain false")
        if vector.get("raw_payload_retained") is not False:
            errors.append(f"{command_name} raw_payload_retained must remain false")
        if vector.get("parity_status") != "static_digest_parity":
            errors.append(f"{command_name} parity_status must be static_digest_parity")
        if vector.get("failure_path_blocked_by") != "witness://maf/failure-receipt-path":
            errors.append(f"{command_name} must remain blocked by the failure receipt path witness")
        expected_digest = canonical_fixture_digest(vector)
        if vector.get("fixture_material_digest_sha256") != expected_digest:
            errors.append(f"{command_name} fixture digest drift: expected {expected_digest}")
    return errors


def _validate_authority_boundary(witness: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    boundary = witness.get("authority_boundary", {})
    if boundary.get("static_fixture_read_allowed") is not True:
        errors.append("static_fixture_read_allowed must be true")
    for flag in sorted(FALSE_AUTHORITY_FLAGS):
        if boundary.get(flag) is not False:
            errors.append(f"{flag} must remain false")
    return errors


def _validate_receipts_and_summary(witness: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    receipt_refs = witness.get("receipt_refs", {})
    for key, expected_value in REQUIRED_RECEIPT_REFS.items():
        if receipt_refs.get(key) != expected_value:
            errors.append(f"receipt_refs.{key} must be {expected_value}")
    evidence_refs = set(witness.get("evidence_refs", []))
    if not CLOSED_WITNESS_REFS.issubset(evidence_refs):
        errors.append("evidence_refs must include the deterministic fixture parity witness ref")
    if "gap://maf/failure-receipt-path-open" not in evidence_refs:
        errors.append("evidence_refs must retain the open failure receipt path gap")
    summary = witness.get("contract_summary", {})
    expected_summary = {
        "source_artifact_count": len(witness.get("source_artifacts", [])),
        "fixture_vector_count": len(witness.get("fixture_vectors", [])),
        "authority_denial_count": len(FALSE_AUTHORITY_FLAGS),
        "open_gap_count": 1,
        "evidence_ref_count": len(witness.get("evidence_refs", [])),
    }
    for key, expected_value in expected_summary.items():
        if summary.get(key) != expected_value:
            errors.append(f"contract_summary.{key} must be {expected_value}")
    return errors


def _validate_no_secret_markers(witness: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    serialized = json.dumps(witness, sort_keys=True).lower()
    for marker in SECRET_MARKERS:
        if marker in serialized and marker != "secret":
            errors.append(f"witness must not contain secret marker {marker}")
    return errors


def validate_maf_deterministic_fixture_parity_witness_record(
    witness: dict[str, Any],
    schema_path: Path = DEFAULT_SCHEMA_PATH,
) -> list[str]:
    errors: list[str] = []
    errors.extend(_validate_schema_contract(schema_path, witness))
    errors.extend(_validate_parity_scope(witness))
    errors.extend(_validate_source_artifacts(witness))
    errors.extend(_validate_fixture_vectors(witness))
    errors.extend(_validate_authority_boundary(witness))
    errors.extend(_validate_receipts_and_summary(witness))
    errors.extend(_validate_no_secret_markers(witness))
    return errors


def validate_maf_deterministic_fixture_parity_witness(
    schema_path: Path = DEFAULT_SCHEMA_PATH,
    witness_path: Path = DEFAULT_WITNESS_PATH,
) -> list[str]:
    witness = load_json_object(witness_path, "MafDeterministicFixtureParityWitness")
    return validate_maf_deterministic_fixture_parity_witness_record(witness, schema_path)


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate the MafDeterministicFixtureParityWitness contract.")
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA_PATH)
    parser.add_argument("--witness", type=Path, default=DEFAULT_WITNESS_PATH)
    parser.add_argument("--json", action="store_true", help="Emit machine-readable validation output.")
    args = parser.parse_args()

    errors = validate_maf_deterministic_fixture_parity_witness(args.schema, args.witness)
    if args.json:
        print(json.dumps({"ok": not errors, "errors": errors}, indent=2, sort_keys=True))
    elif errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
