#!/usr/bin/env python3
"""Validate the MafRuntimeBindingAdmissionWitness contract.

Purpose: verify that MAF runtime-binding admission remains evidence-gated and
does not grant executable runtime authority.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: Python standard library and schema validation helpers.
Invariants:
  - Validation is read-only and deterministic.
  - Admission records prerequisites; it does not start implementation.
  - Runtime binding, PyO3, subprocess execution, backend flips, writes,
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


DEFAULT_SCHEMA_PATH = WORKSPACE_ROOT / "schemas" / "maf_runtime_binding_admission_witness.schema.json"
DEFAULT_WITNESS_PATH = WORKSPACE_ROOT / "examples" / "maf_runtime_binding_admission_witness.foundation.json"
EXPECTED_SCHEMA_ID = "urn:mullusi:schema:maf-runtime-binding-admission-witness:1"
EXPECTED_SCHEMA_TITLE = "MAF Runtime Binding Admission Witness"
EXPECTED_WITNESS_VERSION = "maf_runtime_binding_admission_witness.v1"
EXPECTED_ADMISSION_MODE = "governed_runtime_binding_admission"
REQUIRED_IMPLEMENTATION_EVIDENCE = {
    "evidence://maf/runtime-binding/uao-admission",
    "evidence://maf/runtime-binding/implementation-design",
    "evidence://maf/runtime-binding/rollback-recovery",
    "evidence://maf/runtime-binding/runtime-execution-receipts",
    "evidence://maf/runtime-binding/ci-rust-backend-lane",
    "evidence://maf/runtime-binding/terminal-closure-review",
}
REQUIRED_ADMISSION_REQUIREMENTS = {
    "maf-runtime-binding-uao-admission": "evidence://maf/runtime-binding/uao-admission",
    "maf-runtime-binding-implementation-design": "evidence://maf/runtime-binding/implementation-design",
    "maf-runtime-binding-rollback-recovery": "evidence://maf/runtime-binding/rollback-recovery",
    "maf-runtime-binding-runtime-execution-receipts": "evidence://maf/runtime-binding/runtime-execution-receipts",
    "maf-runtime-binding-ci-rust-backend-lane": "evidence://maf/runtime-binding/ci-rust-backend-lane",
    "maf-runtime-binding-terminal-closure-review": "evidence://maf/runtime-binding/terminal-closure-review",
}
REQUIRED_SOURCE_ARTIFACTS = {
    "schemas/maf_failure_receipt_path_witness.schema.json": "failure_receipt_path_schema",
    "examples/maf_failure_receipt_path_witness.foundation.json": "failure_receipt_path_example",
    "scripts/validate_maf_failure_receipt_path_witness.py": "failure_receipt_path_validator",
    "tests/test_validate_maf_failure_receipt_path_witness.py": "failure_receipt_path_tests",
    "docs/97_maf_failure_receipt_path_witness.md": "failure_receipt_path_doc",
    "docs/AUDIT_F8_SCOPING_PLAN.md": "runtime_binding_scoping_plan",
    "maf/MAF_BOUNDARY.md": "maf_boundary",
    "schemas/universal_action_orchestration.schema.json": "uao_schema",
    "schemas/life_meaning_judgment.schema.json": "life_meaning_judgment_schema",
}
REQUIRED_RECEIPT_REFS = {
    "maf_runtime_binding_admission_witness_schema": "schemas/maf_runtime_binding_admission_witness.schema.json",
    "maf_runtime_binding_admission_witness_example": "examples/maf_runtime_binding_admission_witness.foundation.json",
    "maf_runtime_binding_admission_witness_validator": "scripts/validate_maf_runtime_binding_admission_witness.py",
    "maf_runtime_binding_admission_witness_tests": "tests/test_validate_maf_runtime_binding_admission_witness.py",
    "maf_runtime_binding_admission_witness_doc": "docs/98_maf_runtime_binding_admission_witness.md",
    "maf_failure_receipt_path_witness_schema": "schemas/maf_failure_receipt_path_witness.schema.json",
    "maf_failure_receipt_path_witness_example": "examples/maf_failure_receipt_path_witness.foundation.json",
    "maf_failure_receipt_path_witness_validator": "scripts/validate_maf_failure_receipt_path_witness.py",
    "maf_failure_receipt_path_witness_tests": "tests/test_validate_maf_failure_receipt_path_witness.py",
    "maf_failure_receipt_path_witness_doc": "docs/97_maf_failure_receipt_path_witness.md",
    "maf_f8_scoping_plan": "docs/AUDIT_F8_SCOPING_PLAN.md",
    "maf_boundary_doc": "maf/MAF_BOUNDARY.md",
    "universal_action_orchestration_schema": "schemas/universal_action_orchestration.schema.json",
    "life_meaning_judgment_schema": "schemas/life_meaning_judgment.schema.json",
}
FALSE_AUTHORITY_FLAGS = {
    "implementation_start_allowed",
    "runtime_binding_allowed",
    "pyo3_binding_allowed",
    "subprocess_execution_allowed",
    "cli_execution_allowed",
    "rust_crate_execution_allowed",
    "python_imports_rust_allowed",
    "ci_rust_backend_required_allowed",
    "default_backend_flip_allowed",
    "network_call_allowed",
    "secret_access_allowed",
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


def build_mutated_maf_runtime_binding_admission_witness(**overrides: Any) -> dict[str, Any]:
    record = deepcopy(load_json_object(DEFAULT_WITNESS_PATH, "MafRuntimeBindingAdmissionWitness"))
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


def _validate_admission_scope(witness: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    scope = witness.get("admission_scope", {})
    if witness.get("witness_version") != EXPECTED_WITNESS_VERSION:
        errors.append(f"witness_version must be {EXPECTED_WITNESS_VERSION}")
    if witness.get("solver_outcome") != "AwaitingEvidence":
        errors.append("solver_outcome must remain AwaitingEvidence")
    if scope.get("foundation_mode") is not True:
        errors.append("foundation_mode must be true")
    if scope.get("admission_mode") != EXPECTED_ADMISSION_MODE:
        errors.append(f"admission_mode must be {EXPECTED_ADMISSION_MODE}")
    if scope.get("static_prerequisites_closed") is not True:
        errors.append("static_prerequisites_closed must be true")
    if scope.get("runtime_binding_admission_recorded") is not True:
        errors.append("runtime_binding_admission_recorded must be true")
    for flag in ("runtime_binding_claimed", "implementation_authority_claimed", "terminal_closure_claimed"):
        if scope.get(flag) is not False:
            errors.append(f"{flag} must remain false")
    if set(scope.get("required_implementation_evidence", [])) != REQUIRED_IMPLEMENTATION_EVIDENCE:
        errors.append("required_implementation_evidence must exactly match runtime-binding evidence gates")
    expected_refs = {
        "failure_receipt_path_ref": "witness://maf/failure-receipt-path",
        "deterministic_fixture_parity_ref": "witness://maf/deterministic-fixture-parity",
        "subprocess_effect_boundary_ref": "witness://maf/subprocess-effect-boundary",
        "abi_cli_contract_ref": "witness://maf/abi-cli-contract",
        "parity_witness_ref": "witness://maf/receipt-parity",
        "f8_plan_ref": "docs/AUDIT_F8_SCOPING_PLAN.md",
    }
    for key, expected_value in expected_refs.items():
        if scope.get(key) != expected_value:
            errors.append(f"{key} must be {expected_value}")
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


def _validate_admission_requirements(witness: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    requirements = witness.get("admission_requirements", [])
    by_id = {requirement.get("requirement_id"): requirement for requirement in requirements}
    if set(by_id) != set(REQUIRED_ADMISSION_REQUIREMENTS):
        errors.append("admission_requirements must cover exactly the required runtime-binding evidence gates")
    for requirement_id, requirement_ref in REQUIRED_ADMISSION_REQUIREMENTS.items():
        requirement = by_id.get(requirement_id)
        if requirement is None:
            errors.append(f"missing admission requirement {requirement_id}")
            continue
        if requirement.get("requirement_ref") != requirement_ref:
            errors.append(f"{requirement_id} requirement_ref must be {requirement_ref}")
        if requirement.get("required_before") != "runtime_binding_implementation":
            errors.append(f"{requirement_id} required_before must be runtime_binding_implementation")
        if requirement.get("evidence_state") != "AwaitingEvidence":
            errors.append(f"{requirement_id} evidence_state must remain AwaitingEvidence")
        if requirement.get("admission_status") != "blocked_until_evidence":
            errors.append(f"{requirement_id} admission_status must remain blocked_until_evidence")
        if requirement.get("execution_allowed") is not False:
            errors.append(f"{requirement_id} execution_allowed must remain false")
    return errors


def _validate_authority_boundary(witness: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    boundary = witness.get("authority_boundary", {})
    if boundary.get("static_admission_read_allowed") is not True:
        errors.append("static_admission_read_allowed must be true")
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
    if "gap://maf/runtime-binding-implementation-evidence" not in evidence_refs:
        errors.append("evidence_refs must retain the runtime binding implementation evidence gap")
    if "witness://maf/failure-receipt-path" not in evidence_refs:
        errors.append("evidence_refs must include the failure receipt path witness ref")
    summary = witness.get("contract_summary", {})
    expected_summary = {
        "source_artifact_count": len(witness.get("source_artifacts", [])),
        "admission_requirement_count": len(witness.get("admission_requirements", [])),
        "authority_denial_count": len(FALSE_AUTHORITY_FLAGS),
        "open_evidence_count": len(witness.get("admission_scope", {}).get("required_implementation_evidence", [])),
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


def validate_maf_runtime_binding_admission_witness_record(
    witness: dict[str, Any],
    schema_path: Path = DEFAULT_SCHEMA_PATH,
) -> list[str]:
    errors: list[str] = []
    errors.extend(_validate_schema_contract(schema_path, witness))
    errors.extend(_validate_admission_scope(witness))
    errors.extend(_validate_source_artifacts(witness))
    errors.extend(_validate_admission_requirements(witness))
    errors.extend(_validate_authority_boundary(witness))
    errors.extend(_validate_receipts_and_summary(witness))
    errors.extend(_validate_no_secret_markers(witness))
    return errors


def validate_maf_runtime_binding_admission_witness(
    schema_path: Path = DEFAULT_SCHEMA_PATH,
    witness_path: Path = DEFAULT_WITNESS_PATH,
) -> list[str]:
    witness = load_json_object(witness_path, "MafRuntimeBindingAdmissionWitness")
    return validate_maf_runtime_binding_admission_witness_record(witness, schema_path)


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate the MafRuntimeBindingAdmissionWitness contract.")
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA_PATH)
    parser.add_argument("--witness", type=Path, default=DEFAULT_WITNESS_PATH)
    parser.add_argument("--json", action="store_true", help="Emit machine-readable validation output.")
    args = parser.parse_args()

    errors = validate_maf_runtime_binding_admission_witness(args.schema, args.witness)
    if args.json:
        print(json.dumps({"ok": not errors, "errors": errors}, indent=2, sort_keys=True))
    elif errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
