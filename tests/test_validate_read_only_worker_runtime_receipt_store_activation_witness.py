"""Purpose: verify ReadOnlyWorkerRuntimeReceiptStoreActivationWitness validation.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: runtime receipt-store activation witness schema, fixture,
validator, and SDLC artifacts.
Invariants:
  - runtime receipt-store activation, schema registry writes, runtime
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
from scripts.validate_read_only_worker_runtime_receipt_store_activation_witness import (
    DEFAULT_RECEIPT_PATH,
    DEFAULT_SCHEMA_PATH,
    build_mutated_runtime_receipt_store_activation_witness,
    validate_runtime_receipt_store_activation_witness,
    validate_runtime_receipt_store_activation_witness_record,
)
from scripts.validate_read_only_worker_runtime_receipt_store_operator_approval_witness import (
    DEFAULT_RECEIPT_PATH as DEFAULT_OPERATOR_APPROVAL_RECEIPT_PATH,
    DEFAULT_SCHEMA_PATH as DEFAULT_OPERATOR_APPROVAL_SCHEMA_PATH,
    build_mutated_operator_approval_witness,
    validate_operator_approval_witness,
    validate_operator_approval_witness_record,
)
from scripts.validate_schemas import _load_schema


def test_runtime_receipt_store_activation_witness_fixture_passes() -> None:
    errors = validate_runtime_receipt_store_activation_witness()

    assert errors == []
    assert DEFAULT_SCHEMA_PATH.exists()
    assert DEFAULT_RECEIPT_PATH.exists()


def test_runtime_receipt_store_operator_approval_witness_fixture_passes() -> None:
    errors = validate_operator_approval_witness()

    assert errors == []
    assert DEFAULT_OPERATOR_APPROVAL_SCHEMA_PATH.exists()
    assert DEFAULT_OPERATOR_APPROVAL_RECEIPT_PATH.exists()


def test_runtime_receipt_store_operator_approval_witness_rejects_authority_drift() -> None:
    schema = _load_schema(DEFAULT_OPERATOR_APPROVAL_SCHEMA_PATH)
    mutated = build_mutated_operator_approval_witness(
        authority_scope__operator_approval_collected=True,
        authority_scope__receipt_store_append_allowed=True,
        admission_decision__receipt_store_append_admitted=True,
    )

    errors = validate_operator_approval_witness_record(mutated, schema)

    assert "authority_scope.operator_approval_collected must be false" in errors
    assert "authority_scope.receipt_store_append_allowed must be false" in errors
    assert "admission_decision.receipt_store_append_admitted must be false" in errors


def test_runtime_receipt_store_operator_approval_witness_rejects_contract_drift() -> None:
    schema = _load_schema(DEFAULT_OPERATOR_APPROVAL_SCHEMA_PATH)
    mutated = build_mutated_operator_approval_witness(
        operator_approval_witness_contract__witness_mode="LIVE_APPROVAL_AUTHORITY",
        operator_approval_witness_contract__approval_profile="WRONG_PROFILE",
        operator_approval_witness_contract__target_activation_witness_ref="examples/wrong.json",
    )

    errors = validate_operator_approval_witness_record(mutated, schema)

    assert any("operator_approval_witness_contract.witness_mode" in error for error in errors)
    assert any("operator_approval_witness_contract.approval_profile" in error for error in errors)
    assert any("operator_approval_witness_contract.target_activation_witness_ref" in error for error in errors)


def test_runtime_receipt_store_activation_witness_rejects_authority_drift() -> None:
    schema = _load_schema(DEFAULT_SCHEMA_PATH)
    mutated = build_mutated_runtime_receipt_store_activation_witness(
        authority_scope__runtime_receipt_store_activation_performed=True,
        authority_scope__schema_registry_write_performed=True,
        authority_scope__success_claim_allowed=True,
    )

    errors = validate_runtime_receipt_store_activation_witness_record(mutated, schema)

    assert "authority_scope.runtime_receipt_store_activation_performed must be false" in errors
    assert "authority_scope.schema_registry_write_performed must be false" in errors
    assert "authority_scope.success_claim_allowed must be false" in errors


def test_runtime_receipt_store_activation_witness_rejects_contract_drift() -> None:
    schema = _load_schema(DEFAULT_SCHEMA_PATH)
    mutated = build_mutated_runtime_receipt_store_activation_witness(
        runtime_receipt_store_activation_witness_contract__witness_mode="LIVE_SCHEMA_ACTIVATION",
        runtime_receipt_store_activation_witness_contract__target_runtime_receipt_store_activation_ref="candidate://wrong",
        runtime_receipt_store_activation_witness_contract__receipt_store_activation_profile="WRONG_PROFILE",
    )

    errors = validate_runtime_receipt_store_activation_witness_record(mutated, schema)

    assert (
        "runtime_receipt_store_activation_witness_contract.witness_mode must be "
        "LIVE_RUNTIME_RECEIPT_STORE_ACTIVATION_WITNESS_ONLY"
    ) in errors
    assert (
        "runtime_receipt_store_activation_witness_contract."
        "target_runtime_receipt_store_activation_ref is invalid"
    ) in errors
    assert "runtime_receipt_store_activation_witness_contract.receipt_store_activation_profile is invalid" in errors


def test_runtime_receipt_store_activation_witness_requires_source_refs() -> None:
    schema = _load_schema(DEFAULT_SCHEMA_PATH)
    mutated = build_mutated_runtime_receipt_store_activation_witness()
    mutated["runtime_receipt_store_activation_witness_contract"]["required_source_receipt_refs"] = [
        "examples/read_only_worker_runtime_receipt_emitter_registration_witness.foundation.json"
    ]
    mutated["evidence_refs"] = [
        "schemas/read_only_worker_runtime_receipt_store_activation_witness.schema.json"
    ]

    errors = validate_runtime_receipt_store_activation_witness_record(mutated, schema)

    assert any("required_source_receipt_refs missing required ref" in error for error in errors)
    assert any("evidence_refs missing required ref" in error for error in errors)
    assert any("contract_summary.source_receipt_ref_count must match observed count" in error for error in errors)


def test_runtime_receipt_store_activation_witness_rejects_admission_drift() -> None:
    schema = _load_schema(DEFAULT_SCHEMA_PATH)
    mutated = build_mutated_runtime_receipt_store_activation_witness(
        activation_evaluation__schema_registry_write_performed=True,
        activation_evaluation__worker_invocation_allowed=True,
        admission_decision__runtime_dispatch_admitted=True,
    )

    errors = validate_runtime_receipt_store_activation_witness_record(mutated, schema)

    assert "activation_evaluation.schema_registry_write_performed must be false" in errors
    assert "activation_evaluation.worker_invocation_allowed must be false" in errors
    assert "admission_decision.runtime_dispatch_admitted must be false" in errors


def test_runtime_receipt_store_activation_witness_rejects_summary_drift() -> None:
    schema = _load_schema(DEFAULT_SCHEMA_PATH)
    mutated = build_mutated_runtime_receipt_store_activation_witness(
        contract_summary__activation_true_check_count=0,
        contract_summary__activation_denied_check_count=0,
        contract_summary__receipt_ref_count=0,
    )

    errors = validate_runtime_receipt_store_activation_witness_record(mutated, schema)

    assert "contract_summary.activation_true_check_count must match observed count" in errors
    assert "contract_summary.activation_denied_check_count must match observed count" in errors
    assert "contract_summary.receipt_ref_count must match observed count" in errors


def test_runtime_receipt_store_activation_witness_cli_json_paths_are_workspace_relative() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "scripts/validate_read_only_worker_runtime_receipt_store_activation_witness.py",
            "--json",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)

    assert payload["status"] == "passed"
    assert payload["schema_path"] in {
        "schemas\\read_only_worker_runtime_receipt_store_activation_witness.schema.json",
        "schemas/read_only_worker_runtime_receipt_store_activation_witness.schema.json",
    }
    assert payload["errors"] == []


def test_runtime_receipt_store_activation_witness_rejects_malformed_payload() -> None:
    schema = _load_schema(DEFAULT_SCHEMA_PATH)

    errors = validate_runtime_receipt_store_activation_witness_record([], schema)

    assert any("must be object" in error or "must be a JSON object" in error for error in errors)
    assert len(errors) >= 1
    assert schema["$id"] == "urn:mullusi:schema:read-only-worker-runtime-receipt-store-activation-witness:1"


def test_runtime_receipt_store_activation_witness_sdlc_artifacts_validate() -> None:
    requirement_path = Path(
        "examples/sdlc/requirement_runtime_receipt_store_activation_witness_20260618.json"
    )
    design_path = Path("examples/sdlc/design_runtime_receipt_store_activation_witness_20260618.json")
    requirement = sdlc_validator.load_json_object(requirement_path, "runtime receipt-store activation requirement")
    design = sdlc_validator.load_json_object(design_path, "runtime receipt-store activation design")

    requirement_errors = sdlc_validator.validate_artifact_record("requirement", requirement)
    design_errors = sdlc_validator.validate_artifact_record("design_decision", design)

    assert requirement_errors == []
    assert design_errors == []
    assert design["requirement_id"] == requirement["requirement_id"]
    assert DEFAULT_RECEIPT_PATH.name == "read_only_worker_runtime_receipt_store_activation_witness.foundation.json"
    assert DEFAULT_SCHEMA_PATH.name == "read_only_worker_runtime_receipt_store_activation_witness.schema.json"
