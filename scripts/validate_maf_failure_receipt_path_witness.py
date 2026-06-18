#!/usr/bin/env python3
"""Validate the MafFailureReceiptPathWitness contract.

Purpose: verify that MAF failure receipt path closure is static, digest-only,
and read-only before any executable runtime binding can be claimed.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: Python standard library and schema validation helpers.
Invariants:
  - Validation is read-only and deterministic.
  - Failure receipt path closure grants reconsideration only, not execution.
  - Runtime binding, subprocess execution, CLI execution, writes, raw failure
    payloads, terminal closure, and success claims remain denied.
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


DEFAULT_SCHEMA_PATH = WORKSPACE_ROOT / "schemas" / "maf_failure_receipt_path_witness.schema.json"
DEFAULT_WITNESS_PATH = WORKSPACE_ROOT / "examples" / "maf_failure_receipt_path_witness.foundation.json"
EXPECTED_SCHEMA_ID = "urn:mullusi:schema:maf-failure-receipt-path-witness:1"
EXPECTED_SCHEMA_TITLE = "MAF Failure Receipt Path Witness"
EXPECTED_WITNESS_VERSION = "maf_failure_receipt_path_witness.v1"
EXPECTED_PATH_MODE = "static_failure_receipt_materialization_path"
CLOSED_WITNESS_REFS = {"witness://maf/failure-receipt-path"}
FORBIDDEN_FUTURE_WITNESSES = {"witness://maf/failure-receipt-path"}
REQUIRED_SOURCE_ARTIFACTS = {
    "schemas/maf_deterministic_fixture_parity_witness.schema.json": "deterministic_fixture_parity_schema",
    "examples/maf_deterministic_fixture_parity_witness.foundation.json": "deterministic_fixture_parity_example",
    "scripts/validate_maf_deterministic_fixture_parity_witness.py": "deterministic_fixture_parity_validator",
    "tests/test_validate_maf_deterministic_fixture_parity_witness.py": "deterministic_fixture_parity_tests",
    "docs/96_maf_deterministic_fixture_parity_witness.md": "deterministic_fixture_parity_doc",
    "schemas/worker_failure_receipt.schema.json": "failure_receipt_schema",
    "schemas/verification_result.schema.json": "verification_result_schema",
    "schemas/kernel_proof.schema.json": "kernel_proof_schema",
    "schemas/sdlc_transition_receipt.schema.json": "transition_receipt_schema",
    "maf/rust/crates/maf-cli/src/main.rs": "cli_entry",
}
REQUIRED_FAILURE_PATH_CONTROLS = {
    "verify-receipt-chain": {
        "path_id": "maf-failure-path-verify-receipt-chain",
        "failure_source_ref": "fixture://maf/verify-receipt-chain/static-digest-v1",
        "failure_receipt_ref": "schemas/worker_failure_receipt.schema.json",
        "verification_ref": "schemas/verification_result.schema.json",
    },
    "verify-kernel-proof": {
        "path_id": "maf-failure-path-verify-kernel-proof",
        "failure_source_ref": "fixture://maf/verify-kernel-proof/static-digest-v1",
        "failure_receipt_ref": "schemas/kernel_proof.schema.json",
        "verification_ref": "schemas/verification_result.schema.json",
    },
    "emit-transition-receipt": {
        "path_id": "maf-failure-path-emit-transition-receipt",
        "failure_source_ref": "fixture://maf/emit-transition-receipt/static-digest-v1",
        "failure_receipt_ref": "schemas/sdlc_transition_receipt.schema.json",
        "verification_ref": "schemas/worker_failure_receipt.schema.json",
    },
}
REQUIRED_RECEIPT_REFS = {
    "maf_failure_receipt_path_witness_schema": "schemas/maf_failure_receipt_path_witness.schema.json",
    "maf_failure_receipt_path_witness_example": "examples/maf_failure_receipt_path_witness.foundation.json",
    "maf_failure_receipt_path_witness_validator": "scripts/validate_maf_failure_receipt_path_witness.py",
    "maf_failure_receipt_path_witness_tests": "tests/test_validate_maf_failure_receipt_path_witness.py",
    "maf_failure_receipt_path_witness_doc": "docs/97_maf_failure_receipt_path_witness.md",
    "maf_deterministic_fixture_parity_witness_schema": "schemas/maf_deterministic_fixture_parity_witness.schema.json",
    "maf_deterministic_fixture_parity_witness_example": "examples/maf_deterministic_fixture_parity_witness.foundation.json",
    "maf_deterministic_fixture_parity_witness_validator": "scripts/validate_maf_deterministic_fixture_parity_witness.py",
    "maf_deterministic_fixture_parity_witness_tests": "tests/test_validate_maf_deterministic_fixture_parity_witness.py",
    "rust_cli_entry": "maf/rust/crates/maf-cli/src/main.rs",
    "universal_action_orchestration_schema": "schemas/universal_action_orchestration.schema.json",
    "life_meaning_judgment_schema": "schemas/life_meaning_judgment.schema.json",
    "worker_failure_receipt_schema": "schemas/worker_failure_receipt.schema.json",
    "verification_result_schema": "schemas/verification_result.schema.json",
    "sdlc_transition_receipt_schema": "schemas/sdlc_transition_receipt.schema.json",
    "kernel_proof_schema": "schemas/kernel_proof.schema.json",
}
FALSE_AUTHORITY_FLAGS = {
    "runtime_binding_allowed",
    "cli_execution_allowed",
    "subprocess_execution_allowed",
    "pyo3_binding_allowed",
    "rust_crate_execution_allowed",
    "python_imports_rust_allowed",
    "shell_invocation_allowed",
    "child_process_spawn_allowed",
    "network_call_allowed",
    "secret_access_allowed",
    "raw_failure_payload_retention_allowed",
    "filesystem_write_allowed",
    "runtime_dispatch_allowed",
    "canonical_state_mutation_allowed",
    "terminal_closure_allowed",
    "success_claim_allowed",
}
SECRET_MARKERS = ("token", "password", "private_key", "credential")


def canonical_source_digest(path: Path) -> str:
    text = path.read_text(encoding="utf-8").replace("\r\n", "\n").replace("\r", "\n")
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def canonical_path_control_digest(control: dict[str, Any]) -> str:
    descriptor = "|".join(
        [
            str(control.get("path_id", "")),
            str(control.get("failure_source_ref", "")),
            str(control.get("failure_receipt_ref", "")),
            str(control.get("verification_ref", "")),
            str(control.get("materialization_status", "")),
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


def build_mutated_maf_failure_receipt_path_witness(**overrides: Any) -> dict[str, Any]:
    record = deepcopy(load_json_object(DEFAULT_WITNESS_PATH, "MafFailureReceiptPathWitness"))
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


def _validate_path_scope(witness: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    scope = witness.get("path_scope", {})
    if witness.get("witness_version") != EXPECTED_WITNESS_VERSION:
        errors.append(f"witness_version must be {EXPECTED_WITNESS_VERSION}")
    if witness.get("solver_outcome") != "AwaitingEvidence":
        errors.append("solver_outcome must remain AwaitingEvidence")
    if scope.get("foundation_mode") is not True:
        errors.append("foundation_mode must be true")
    if scope.get("path_mode") != EXPECTED_PATH_MODE:
        errors.append(f"path_mode must be {EXPECTED_PATH_MODE}")
    if scope.get("failure_receipt_path_closed") is not True:
        errors.append("failure_receipt_path_closed must be true")
    if scope.get("runtime_binding_reconsideration_only") is not True:
        errors.append("runtime_binding_reconsideration_only must be true")
    for flag in (
        "runtime_binding_claimed",
        "subprocess_execution_claimed",
        "cli_execution_claimed",
        "command_behavior_claimed",
    ):
        if scope.get(flag) is not False:
            errors.append(f"{flag} must remain false")
    future_witnesses = set(scope.get("required_future_witnesses", []))
    if future_witnesses:
        errors.append("required_future_witnesses must be empty after failure receipt path closure")
    forbidden = future_witnesses & FORBIDDEN_FUTURE_WITNESSES
    if forbidden:
        errors.append(f"closed failure receipt path witness must not remain future: {sorted(forbidden)}")
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


def _validate_failure_path_controls(witness: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    controls = witness.get("failure_path_controls", [])
    by_command = {control.get("command_name"): control for control in controls}
    if set(by_command) != set(REQUIRED_FAILURE_PATH_CONTROLS):
        errors.append("failure_path_controls must cover exactly the required MAF command descriptors")
    for command_name, descriptor in REQUIRED_FAILURE_PATH_CONTROLS.items():
        control = by_command.get(command_name)
        if control is None:
            errors.append(f"missing failure path control for {command_name}")
            continue
        for field_name, expected_value in descriptor.items():
            if control.get(field_name) != expected_value:
                errors.append(f"{command_name} {field_name} must be {expected_value}")
        if control.get("materialization_status") != "static_failure_receipt_path":
            errors.append(f"{command_name} materialization_status must be static_failure_receipt_path")
        if control.get("runtime_materialization_allowed") is not False:
            errors.append(f"{command_name} runtime_materialization_allowed must remain false")
        if control.get("raw_failure_payload_retained") is not False:
            errors.append(f"{command_name} raw_failure_payload_retained must remain false")
        expected_digest = canonical_path_control_digest(control)
        if control.get("path_descriptor_digest_sha256") != expected_digest:
            errors.append(f"{command_name} path descriptor digest drift: expected {expected_digest}")
    return errors


def _validate_authority_boundary(witness: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    boundary = witness.get("authority_boundary", {})
    if boundary.get("static_failure_path_read_allowed") is not True:
        errors.append("static_failure_path_read_allowed must be true")
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
        errors.append("evidence_refs must include the failure receipt path witness ref")
    if "gap://maf/failure-receipt-path-open" in evidence_refs:
        errors.append("evidence_refs must not retain the open failure receipt path gap")
    summary = witness.get("contract_summary", {})
    expected_summary = {
        "source_artifact_count": len(witness.get("source_artifacts", [])),
        "failure_path_control_count": len(witness.get("failure_path_controls", [])),
        "authority_denial_count": len(FALSE_AUTHORITY_FLAGS),
        "open_gap_count": 0,
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
        if marker in serialized:
            errors.append(f"witness must not contain secret marker {marker}")
    return errors


def validate_maf_failure_receipt_path_witness_record(
    witness: dict[str, Any],
    schema_path: Path = DEFAULT_SCHEMA_PATH,
) -> list[str]:
    errors: list[str] = []
    errors.extend(_validate_schema_contract(schema_path, witness))
    errors.extend(_validate_path_scope(witness))
    errors.extend(_validate_source_artifacts(witness))
    errors.extend(_validate_failure_path_controls(witness))
    errors.extend(_validate_authority_boundary(witness))
    errors.extend(_validate_receipts_and_summary(witness))
    errors.extend(_validate_no_secret_markers(witness))
    return errors


def validate_maf_failure_receipt_path_witness(
    schema_path: Path = DEFAULT_SCHEMA_PATH,
    witness_path: Path = DEFAULT_WITNESS_PATH,
) -> list[str]:
    witness = load_json_object(witness_path, "MafFailureReceiptPathWitness")
    return validate_maf_failure_receipt_path_witness_record(witness, schema_path)


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate the MafFailureReceiptPathWitness contract.")
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA_PATH)
    parser.add_argument("--witness", type=Path, default=DEFAULT_WITNESS_PATH)
    parser.add_argument("--json", action="store_true", help="Emit machine-readable validation output.")
    args = parser.parse_args()

    errors = validate_maf_failure_receipt_path_witness(args.schema, args.witness)
    if args.json:
        print(json.dumps({"ok": not errors, "errors": errors}, indent=2, sort_keys=True))
    elif errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
