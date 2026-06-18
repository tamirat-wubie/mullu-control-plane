"""Purpose: verify ReadOnlyWorkerRuntimeDispatchAdmissionWitness validation.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: runtime dispatch admission witness schema, fixture,
validator, and SDLC artifacts.
Invariants:
  - runtime dispatch admission, schema registry writes, runtime
    dispatch, worker invocation, runtime receipt emission, success claims, and
    terminal closure remain denied.
  - Validation remains deterministic and read-only.
  - Mfidel atomicity remains preserved.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from scripts import validate_sdlc_artifact as sdlc_validator
from scripts.validate_read_only_worker_runtime_dispatch_admission_witness import (
    DEFAULT_RECEIPT_PATH,
    DEFAULT_SCHEMA_PATH,
    build_mutated_runtime_dispatch_admission_witness,
    validate_runtime_dispatch_admission_witness,
    validate_runtime_dispatch_admission_witness_record,
)
from scripts.validate_schemas import _load_schema


def test_runtime_dispatch_admission_witness_fixture_passes() -> None:
    errors = validate_runtime_dispatch_admission_witness()

    assert errors == []
    assert DEFAULT_SCHEMA_PATH.exists()
    assert DEFAULT_RECEIPT_PATH.exists()


def test_runtime_dispatch_admission_witness_rejects_authority_drift() -> None:
    schema = _load_schema(DEFAULT_SCHEMA_PATH)
    mutated = build_mutated_runtime_dispatch_admission_witness(
        authority_scope__runtime_dispatch_admission_performed=True,
        authority_scope__schema_registry_write_performed=True,
        authority_scope__success_claim_allowed=True,
    )

    errors = validate_runtime_dispatch_admission_witness_record(mutated, schema)

    assert "authority_scope.runtime_dispatch_admission_performed must be false" in errors
    assert "authority_scope.schema_registry_write_performed must be false" in errors
    assert "authority_scope.success_claim_allowed must be false" in errors


def test_runtime_dispatch_admission_witness_rejects_contract_drift() -> None:
    schema = _load_schema(DEFAULT_SCHEMA_PATH)
    mutated = build_mutated_runtime_dispatch_admission_witness(
        runtime_dispatch_admission_witness_contract__witness_mode="LIVE_SCHEMA_ACTIVATION",
        runtime_dispatch_admission_witness_contract__target_runtime_dispatch_admission_ref="candidate://wrong",
        runtime_dispatch_admission_witness_contract__dispatch_admission_profile="WRONG_PROFILE",
        runtime_dispatch_admission_witness_contract__source_store_activation_witness_ref="examples/wrong.json",
    )

    errors = validate_runtime_dispatch_admission_witness_record(mutated, schema)

    assert (
        "runtime_dispatch_admission_witness_contract.witness_mode must be "
        "LIVE_RUNTIME_DISPATCH_ADMISSION_WITNESS_ONLY"
    ) in errors
    assert (
        "runtime_dispatch_admission_witness_contract."
        "target_runtime_dispatch_admission_ref is invalid"
    ) in errors
    assert "runtime_dispatch_admission_witness_contract.dispatch_admission_profile is invalid" in errors
    assert (
        "runtime_dispatch_admission_witness_contract.source_store_activation_witness_ref is invalid"
        in errors
    )


def test_runtime_dispatch_admission_witness_requires_source_refs() -> None:
    schema = _load_schema(DEFAULT_SCHEMA_PATH)
    mutated = build_mutated_runtime_dispatch_admission_witness()
    mutated["runtime_dispatch_admission_witness_contract"]["required_source_receipt_refs"] = [
        "examples/read_only_worker_runtime_receipt_emitter_registration_witness.foundation.json"
    ]
    mutated["evidence_refs"] = [
        "schemas/read_only_worker_runtime_dispatch_admission_witness.schema.json"
    ]

    errors = validate_runtime_dispatch_admission_witness_record(mutated, schema)

    assert any("required_source_receipt_refs missing required ref" in error for error in errors)
    assert any("evidence_refs missing required ref" in error for error in errors)
    assert any("contract_summary.source_receipt_ref_count must match observed count" in error for error in errors)


def test_runtime_dispatch_admission_witness_rejects_admission_drift() -> None:
    schema = _load_schema(DEFAULT_SCHEMA_PATH)
    mutated = build_mutated_runtime_dispatch_admission_witness(
        activation_evaluation__schema_registry_write_performed=True,
        activation_evaluation__worker_invocation_allowed=True,
        admission_decision__runtime_dispatch_admitted=True,
    )

    errors = validate_runtime_dispatch_admission_witness_record(mutated, schema)

    assert "activation_evaluation.schema_registry_write_performed must be false" in errors
    assert "activation_evaluation.worker_invocation_allowed must be false" in errors
    assert "admission_decision.runtime_dispatch_admitted must be false" in errors


def test_runtime_dispatch_admission_witness_rejects_summary_drift() -> None:
    schema = _load_schema(DEFAULT_SCHEMA_PATH)
    mutated = build_mutated_runtime_dispatch_admission_witness(
        contract_summary__activation_true_check_count=0,
        contract_summary__activation_denied_check_count=0,
        contract_summary__receipt_ref_count=0,
    )

    errors = validate_runtime_dispatch_admission_witness_record(mutated, schema)

    assert "contract_summary.activation_true_check_count must match observed count" in errors
    assert "contract_summary.activation_denied_check_count must match observed count" in errors
    assert "contract_summary.receipt_ref_count must match observed count" in errors


def test_runtime_dispatch_admission_witness_cli_json_paths_are_workspace_relative() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "scripts/validate_read_only_worker_runtime_dispatch_admission_witness.py",
            "--json",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)

    assert payload["status"] == "passed"
    assert payload["schema_path"] in {
        "schemas\\read_only_worker_runtime_dispatch_admission_witness.schema.json",
        "schemas/read_only_worker_runtime_dispatch_admission_witness.schema.json",
    }
    assert payload["errors"] == []


def test_runtime_dispatch_admission_witness_rejects_malformed_payload() -> None:
    schema = _load_schema(DEFAULT_SCHEMA_PATH)

    errors = validate_runtime_dispatch_admission_witness_record([], schema)

    assert any("must be object" in error or "must be a JSON object" in error for error in errors)
    assert len(errors) >= 1
    assert schema["$id"] == "urn:mullusi:schema:read-only-worker-runtime-dispatch-admission-witness:1"


def test_runtime_dispatch_admission_witness_sdlc_artifacts_validate() -> None:
    requirement_path = Path(
        "examples/sdlc/requirement_runtime_dispatch_admission_witness_20260618.json"
    )
    design_path = Path("examples/sdlc/design_runtime_dispatch_admission_witness_20260618.json")
    requirement = sdlc_validator.load_json_object(requirement_path, "runtime dispatch admission requirement")
    design = sdlc_validator.load_json_object(design_path, "runtime dispatch admission design")

    requirement_errors = sdlc_validator.validate_artifact_record("requirement", requirement)
    design_errors = sdlc_validator.validate_artifact_record("design_decision", design)

    assert requirement_errors == []
    assert design_errors == []
    assert design["requirement_id"] == requirement["requirement_id"]
    assert DEFAULT_RECEIPT_PATH.name == "read_only_worker_runtime_dispatch_admission_witness.foundation.json"
    assert DEFAULT_SCHEMA_PATH.name == "read_only_worker_runtime_dispatch_admission_witness.schema.json"
