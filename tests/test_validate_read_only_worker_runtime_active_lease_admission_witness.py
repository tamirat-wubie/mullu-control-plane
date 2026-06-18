"""Purpose: verify ReadOnlyWorkerRuntimeActiveLeaseAdmissionWitness validation.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: active lease admission witness schema, fixture, validator, and
SDLC artifacts.
Invariants:
  - active lease admission, lease claims, distributed lease execution, dispatch,
    receipt append, success claims, and terminal closure remain denied.
  - Validation remains deterministic and read-only.
  - Mfidel atomicity remains preserved.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from scripts import validate_sdlc_artifact as sdlc_validator
from scripts.validate_read_only_worker_runtime_active_lease_admission_witness import (
    DEFAULT_RECEIPT_PATH,
    DEFAULT_SCHEMA_PATH,
    build_mutated_active_lease_admission_witness,
    validate_active_lease_admission_witness,
    validate_active_lease_admission_witness_record,
)
from scripts.validate_schemas import _load_schema


def test_active_lease_admission_witness_fixture_passes() -> None:
    errors = validate_active_lease_admission_witness()

    assert errors == []
    assert DEFAULT_SCHEMA_PATH.exists()
    assert DEFAULT_RECEIPT_PATH.exists()


def test_active_lease_admission_witness_rejects_authority_drift() -> None:
    schema = _load_schema(DEFAULT_SCHEMA_PATH)
    mutated = build_mutated_active_lease_admission_witness(
        authority_scope__active_runtime_lease_admission_performed=True,
        authority_scope__distributed_lease_claim_performed=True,
        authority_scope__success_claim_allowed=True,
    )

    errors = validate_active_lease_admission_witness_record(mutated, schema)

    assert "authority_scope.active_runtime_lease_admission_performed must be false" in errors
    assert "authority_scope.distributed_lease_claim_performed must be false" in errors
    assert "authority_scope.success_claim_allowed must be false" in errors


def test_active_lease_admission_witness_rejects_contract_drift() -> None:
    schema = _load_schema(DEFAULT_SCHEMA_PATH)
    mutated = build_mutated_active_lease_admission_witness(
        active_lease_admission_contract__witness_mode="LIVE_LEASE_CLAIM",
        active_lease_admission_contract__target_active_runtime_lease_ref="candidate://wrong",
        active_lease_admission_contract__temporal_lease_window_schema_ref="schemas/wrong.schema.json",
    )

    errors = validate_active_lease_admission_witness_record(mutated, schema)

    assert (
        "active_lease_admission_contract.witness_mode must be "
        "ACTIVE_RUNTIME_LEASE_ADMISSION_WITNESS_ONLY"
    ) in errors
    assert "active_lease_admission_contract.target_active_runtime_lease_ref is invalid" in errors
    assert "active_lease_admission_contract.temporal_lease_window_schema_ref is invalid" in errors


def test_active_lease_admission_witness_requires_runtime_refs() -> None:
    schema = _load_schema(DEFAULT_SCHEMA_PATH)
    mutated = build_mutated_active_lease_admission_witness()
    mutated["active_lease_admission_contract"]["required_runtime_input_refs"] = [
        "evidence://operator-approval/active-runtime-lease-admission"
    ]
    mutated["evidence_refs"] = [
        "schemas/read_only_worker_runtime_active_lease_admission_witness.schema.json"
    ]

    errors = validate_active_lease_admission_witness_record(mutated, schema)

    assert any("required_runtime_input_refs missing required ref" in error for error in errors)
    assert any("evidence_refs missing required ref" in error for error in errors)
    assert any("contract_summary.runtime_input_ref_count must match observed count" in error for error in errors)


def test_active_lease_admission_witness_rejects_lease_evaluation_drift() -> None:
    schema = _load_schema(DEFAULT_SCHEMA_PATH)
    mutated = build_mutated_active_lease_admission_witness(
        lease_evaluation__active_temporal_lease_window_required=False,
        lease_evaluation__lease_claim_performed=True,
        admission_decision__runtime_dispatch_admitted=True,
    )

    errors = validate_active_lease_admission_witness_record(mutated, schema)

    assert "lease_evaluation.active_temporal_lease_window_required must be true" in errors
    assert "lease_evaluation.lease_claim_performed must be false" in errors
    assert "admission_decision.runtime_dispatch_admitted must be false" in errors


def test_active_lease_admission_witness_rejects_summary_drift() -> None:
    schema = _load_schema(DEFAULT_SCHEMA_PATH)
    mutated = build_mutated_active_lease_admission_witness(
        contract_summary__lease_true_check_count=0,
        contract_summary__lease_denied_check_count=0,
        contract_summary__receipt_ref_count=0,
    )

    errors = validate_active_lease_admission_witness_record(mutated, schema)

    assert "contract_summary.lease_true_check_count must match observed count" in errors
    assert "contract_summary.lease_denied_check_count must match observed count" in errors
    assert "contract_summary.receipt_ref_count must match observed count" in errors


def test_active_lease_admission_witness_cli_json_paths_are_workspace_relative() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "scripts/validate_read_only_worker_runtime_active_lease_admission_witness.py",
            "--json",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)

    assert payload["status"] == "passed"
    assert payload["schema_path"] in {
        "schemas\\read_only_worker_runtime_active_lease_admission_witness.schema.json",
        "schemas/read_only_worker_runtime_active_lease_admission_witness.schema.json",
    }
    assert payload["errors"] == []


def test_active_lease_admission_witness_rejects_malformed_payload() -> None:
    schema = _load_schema(DEFAULT_SCHEMA_PATH)

    errors = validate_active_lease_admission_witness_record([], schema)

    assert any("must be object" in error or "must be a JSON object" in error for error in errors)
    assert len(errors) >= 1
    assert schema["$id"] == "urn:mullusi:schema:read-only-worker-runtime-active-lease-admission-witness:1"


def test_active_lease_admission_witness_sdlc_artifacts_validate() -> None:
    requirement_path = Path("examples/sdlc/requirement_runtime_active_lease_admission_witness_20260618.json")
    design_path = Path("examples/sdlc/design_runtime_active_lease_admission_witness_20260618.json")
    requirement = sdlc_validator.load_json_object(requirement_path, "runtime active lease admission requirement")
    design = sdlc_validator.load_json_object(design_path, "runtime active lease admission design")

    requirement_errors = sdlc_validator.validate_artifact_record("requirement", requirement)
    design_errors = sdlc_validator.validate_artifact_record("design_decision", design)

    assert requirement_errors == []
    assert design_errors == []
    assert design["requirement_id"] == requirement["requirement_id"]
    assert DEFAULT_RECEIPT_PATH.name == "read_only_worker_runtime_active_lease_admission_witness.foundation.json"
    assert DEFAULT_SCHEMA_PATH.name == "read_only_worker_runtime_active_lease_admission_witness.schema.json"
