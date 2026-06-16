"""Purpose: verify ReadOnlyWorkerRuntimeReceiptEmitterRegistrationWitness validation.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: runtime receipt emitter witness schema, fixture, validator, SDLC artifacts.
Invariants:
  - runtime receipt emitter registration, emitter registration binding, runtime dispatch,
    worker invocation, runtime receipt emission, success claims, and terminal
    closure remain denied.
  - Validation remains deterministic and read-only.
  - Mfidel atomicity remains preserved.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from scripts import validate_sdlc_artifact as sdlc_validator
from scripts.validate_read_only_worker_runtime_receipt_emitter_registration_witness import (
    DEFAULT_RECEIPT_PATH,
    DEFAULT_SCHEMA_PATH,
    build_mutated_runtime_receipt_emitter_registration_witness,
    validate_runtime_receipt_emitter_registration_witness,
    validate_runtime_receipt_emitter_registration_witness_record,
)
from scripts.validate_schemas import _load_schema


def test_runtime_receipt_emitter_registration_witness_fixture_passes() -> None:
    errors = validate_runtime_receipt_emitter_registration_witness()

    assert errors == []
    assert DEFAULT_SCHEMA_PATH.exists()
    assert DEFAULT_RECEIPT_PATH.exists()


def test_runtime_receipt_emitter_registration_witness_rejects_authority_drift() -> None:
    schema = _load_schema(DEFAULT_SCHEMA_PATH)
    mutated = build_mutated_runtime_receipt_emitter_registration_witness(
        authority_scope__runtime_receipt_emitter_registration_performed=True,
        authority_scope__runtime_dispatch_allowed=True,
        authority_scope__success_claim_allowed=True,
    )

    errors = validate_runtime_receipt_emitter_registration_witness_record(mutated, schema)

    assert "authority_scope.runtime_receipt_emitter_registration_performed must be false" in errors
    assert "authority_scope.runtime_dispatch_allowed must be false" in errors
    assert "authority_scope.success_claim_allowed must be false" in errors


def test_runtime_receipt_emitter_registration_witness_rejects_contract_drift() -> None:
    schema = _load_schema(DEFAULT_SCHEMA_PATH)
    mutated = build_mutated_runtime_receipt_emitter_registration_witness(
        runtime_receipt_emitter_registration_witness_contract__witness_mode="LIVE_emitter_REGISTRATION",
        runtime_receipt_emitter_registration_witness_contract__target_runtime_receipt_emitter_ref="candidate://wrong",
        runtime_receipt_emitter_registration_witness_contract__emitter_profile="WRONG_PROFILE",
    )

    errors = validate_runtime_receipt_emitter_registration_witness_record(mutated, schema)

    assert (
        "runtime_receipt_emitter_registration_witness_contract.witness_mode must be "
        "LIVE_runtime_receipt_emitter_registration_WITNESS_ONLY"
    ) in errors
    assert "runtime_receipt_emitter_registration_witness_contract.target_runtime_receipt_emitter_ref is invalid" in errors
    assert "runtime_receipt_emitter_registration_witness_contract.emitter_profile is invalid" in errors


def test_runtime_receipt_emitter_registration_witness_requires_source_refs() -> None:
    schema = _load_schema(DEFAULT_SCHEMA_PATH)
    mutated = build_mutated_runtime_receipt_emitter_registration_witness()
    mutated["runtime_receipt_emitter_registration_witness_contract"]["required_source_receipt_refs"] = [
        "examples/read_only_worker_runtime_runner_registration_witness.foundation.json"
    ]
    mutated["evidence_refs"] = ["schemas/read_only_worker_runtime_receipt_emitter_registration_witness.schema.json"]

    errors = validate_runtime_receipt_emitter_registration_witness_record(mutated, schema)

    assert any("required_source_receipt_refs missing required ref" in error for error in errors)
    assert any("evidence_refs missing required ref" in error for error in errors)
    assert any("contract_summary.source_receipt_ref_count must match observed count" in error for error in errors)


def test_runtime_receipt_emitter_registration_witness_rejects_admission_drift() -> None:
    schema = _load_schema(DEFAULT_SCHEMA_PATH)
    mutated = build_mutated_runtime_receipt_emitter_registration_witness(
        registration_evaluation__emitter_registration_binding_performed=True,
        registration_evaluation__worker_invocation_allowed=True,
        admission_decision__runtime_dispatch_admitted=True,
    )

    errors = validate_runtime_receipt_emitter_registration_witness_record(mutated, schema)

    assert "registration_evaluation.emitter_registration_binding_performed must be false" in errors
    assert "registration_evaluation.worker_invocation_allowed must be false" in errors
    assert "admission_decision.runtime_dispatch_admitted must be false" in errors


def test_runtime_receipt_emitter_registration_witness_rejects_summary_drift() -> None:
    schema = _load_schema(DEFAULT_SCHEMA_PATH)
    mutated = build_mutated_runtime_receipt_emitter_registration_witness(
        contract_summary__registration_true_check_count=0,
        contract_summary__registration_denied_check_count=0,
        contract_summary__receipt_ref_count=0,
    )

    errors = validate_runtime_receipt_emitter_registration_witness_record(mutated, schema)

    assert "contract_summary.registration_true_check_count must match observed count" in errors
    assert "contract_summary.registration_denied_check_count must match observed count" in errors
    assert "contract_summary.receipt_ref_count must match observed count" in errors


def test_runtime_receipt_emitter_registration_witness_cli_json_paths_are_workspace_relative() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "scripts/validate_read_only_worker_runtime_receipt_emitter_registration_witness.py",
            "--json",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)

    assert payload["status"] == "passed"
    assert payload["schema_path"] == "schemas\\read_only_worker_runtime_receipt_emitter_registration_witness.schema.json" or payload["schema_path"] == "schemas/read_only_worker_runtime_receipt_emitter_registration_witness.schema.json"
    assert payload["errors"] == []


def test_runtime_receipt_emitter_registration_witness_rejects_malformed_payload() -> None:
    schema = _load_schema(DEFAULT_SCHEMA_PATH)

    errors = validate_runtime_receipt_emitter_registration_witness_record([], schema)

    assert any("must be object" in error or "must be a JSON object" in error for error in errors)
    assert len(errors) >= 1
    assert schema["$id"] == "urn:mullusi:schema:read-only-worker-runtime-receipt-emitter-registration-witness:1"


def test_runtime_receipt_emitter_registration_witness_sdlc_artifacts_validate() -> None:
    requirement_path = Path("examples/sdlc/requirement_runtime_receipt_emitter_registration_witness_20260616.json")
    design_path = Path("examples/sdlc/design_runtime_receipt_emitter_registration_witness_20260616.json")
    requirement = sdlc_validator.load_json_object(requirement_path, "runtime receipt emitter witness requirement")
    design = sdlc_validator.load_json_object(design_path, "runtime receipt emitter witness design")

    requirement_errors = sdlc_validator.validate_artifact_record("requirement", requirement)
    design_errors = sdlc_validator.validate_artifact_record("design_decision", design)

    assert requirement_errors == []
    assert design_errors == []
    assert design["requirement_id"] == requirement["requirement_id"]
    assert DEFAULT_RECEIPT_PATH.name == "read_only_worker_runtime_receipt_emitter_registration_witness.foundation.json"
    assert DEFAULT_SCHEMA_PATH.name == "read_only_worker_runtime_receipt_emitter_registration_witness.schema.json"
