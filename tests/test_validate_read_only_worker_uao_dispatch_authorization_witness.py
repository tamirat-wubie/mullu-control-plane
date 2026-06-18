"""Purpose: verify ReadOnlyWorkerUaoDispatchAuthorizationWitness validation.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: UAO dispatch authorization witness schema, fixture,
validator, and SDLC artifacts.
Invariants:
  - UAO dispatch authorization, Phi_gov dispatch authorization, runtime dispatch
    admission, runtime dispatch, worker invocation, receipt emission, receipt
    append, success claims, and terminal closure remain denied.
  - Validation remains deterministic and read-only.
  - Mfidel atomicity remains preserved.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from scripts import validate_sdlc_artifact as sdlc_validator
from scripts.validate_read_only_worker_uao_dispatch_authorization_witness import (
    DEFAULT_RECEIPT_PATH,
    DEFAULT_SCHEMA_PATH,
    build_mutated_uao_dispatch_authorization_witness,
    validate_uao_dispatch_authorization_witness,
    validate_uao_dispatch_authorization_witness_record,
)
from scripts.validate_schemas import _load_schema


def test_uao_dispatch_authorization_witness_fixture_passes() -> None:
    errors = validate_uao_dispatch_authorization_witness()

    assert errors == []
    assert DEFAULT_SCHEMA_PATH.exists()
    assert DEFAULT_RECEIPT_PATH.exists()


def test_uao_dispatch_authorization_witness_rejects_authority_drift() -> None:
    schema = _load_schema(DEFAULT_SCHEMA_PATH)
    mutated = build_mutated_uao_dispatch_authorization_witness(
        authority_scope__active_runtime_lease_observed=True,
        authority_scope__uao_dispatch_authorization_performed=True,
        authority_scope__phi_gov_dispatch_authorization_performed=True,
        authority_scope__success_claim_allowed=True,
    )

    errors = validate_uao_dispatch_authorization_witness_record(mutated, schema)

    assert "authority_scope.active_runtime_lease_observed must be false" in errors
    assert "authority_scope.uao_dispatch_authorization_performed must be false" in errors
    assert "authority_scope.phi_gov_dispatch_authorization_performed must be false" in errors
    assert "authority_scope.success_claim_allowed must be false" in errors


def test_uao_dispatch_authorization_witness_rejects_contract_drift() -> None:
    schema = _load_schema(DEFAULT_SCHEMA_PATH)
    mutated = build_mutated_uao_dispatch_authorization_witness(
        uao_dispatch_authorization_contract__witness_mode="LIVE_DISPATCH",
        uao_dispatch_authorization_contract__target_uao_dispatch_authorization_ref="candidate://wrong",
        uao_dispatch_authorization_contract__uao_authorization_profile="WRONG_PROFILE",
        uao_dispatch_authorization_contract__source_active_runtime_lease_admission_witness_ref="examples/wrong.json",
    )

    errors = validate_uao_dispatch_authorization_witness_record(mutated, schema)

    assert (
        "uao_dispatch_authorization_contract.witness_mode must be "
        "UAO_DISPATCH_AUTHORIZATION_WITNESS_ONLY"
    ) in errors
    assert (
        "uao_dispatch_authorization_contract.target_uao_dispatch_authorization_ref is invalid"
    ) in errors
    assert "uao_dispatch_authorization_contract.uao_authorization_profile is invalid" in errors
    assert (
        "uao_dispatch_authorization_contract."
        "source_active_runtime_lease_admission_witness_ref is invalid"
    ) in errors


def test_uao_dispatch_authorization_witness_requires_authorization_input_refs() -> None:
    schema = _load_schema(DEFAULT_SCHEMA_PATH)
    mutated = build_mutated_uao_dispatch_authorization_witness()
    mutated["uao_dispatch_authorization_contract"]["required_authorization_input_refs"] = [
        "evidence://uao/action-orchestration/request"
    ]
    mutated["evidence_refs"] = [
        "schemas/read_only_worker_uao_dispatch_authorization_witness.schema.json"
    ]

    errors = validate_uao_dispatch_authorization_witness_record(mutated, schema)

    assert any(
        "required_authorization_input_refs missing required ref" in error for error in errors
    )
    assert any("evidence_refs missing required ref" in error for error in errors)
    assert any(
        "contract_summary.authorization_input_ref_count must match observed count" in error
        for error in errors
    )


def test_uao_dispatch_authorization_witness_rejects_admission_drift() -> None:
    schema = _load_schema(DEFAULT_SCHEMA_PATH)
    mutated = build_mutated_uao_dispatch_authorization_witness(
        activation_evaluation__active_runtime_lease_observed=True,
        activation_evaluation__runtime_dispatch_allowed=True,
        admission_decision__uao_dispatch_authorized=True,
        admission_decision__phi_gov_dispatch_authorized=True,
    )

    errors = validate_uao_dispatch_authorization_witness_record(mutated, schema)

    assert "activation_evaluation.active_runtime_lease_observed must be false" in errors
    assert "activation_evaluation.runtime_dispatch_allowed must be false" in errors
    assert "admission_decision.uao_dispatch_authorized must be false" in errors
    assert "admission_decision.phi_gov_dispatch_authorized must be false" in errors


def test_uao_dispatch_authorization_witness_rejects_summary_drift() -> None:
    schema = _load_schema(DEFAULT_SCHEMA_PATH)
    mutated = build_mutated_uao_dispatch_authorization_witness(
        contract_summary__activation_true_check_count=0,
        contract_summary__activation_denied_check_count=0,
        contract_summary__receipt_ref_count=0,
    )

    errors = validate_uao_dispatch_authorization_witness_record(mutated, schema)

    assert "contract_summary.activation_true_check_count must match observed count" in errors
    assert "contract_summary.activation_denied_check_count must match observed count" in errors
    assert "contract_summary.receipt_ref_count must match observed count" in errors


def test_uao_dispatch_authorization_witness_cli_json_paths_are_workspace_relative() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "scripts/validate_read_only_worker_uao_dispatch_authorization_witness.py",
            "--json",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)

    assert payload["status"] == "passed"
    assert payload["schema_path"] in {
        "schemas\\read_only_worker_uao_dispatch_authorization_witness.schema.json",
        "schemas/read_only_worker_uao_dispatch_authorization_witness.schema.json",
    }
    assert payload["errors"] == []


def test_uao_dispatch_authorization_witness_rejects_malformed_payload() -> None:
    schema = _load_schema(DEFAULT_SCHEMA_PATH)

    errors = validate_uao_dispatch_authorization_witness_record([], schema)

    assert any("must be object" in error or "must be a JSON object" in error for error in errors)
    assert len(errors) >= 1
    assert schema["$id"] == "urn:mullusi:schema:read-only-worker-uao-dispatch-authorization-witness:1"


def test_uao_dispatch_authorization_witness_sdlc_artifacts_validate() -> None:
    requirement_path = Path(
        "examples/sdlc/requirement_uao_dispatch_authorization_witness_20260618.json"
    )
    design_path = Path("examples/sdlc/design_uao_dispatch_authorization_witness_20260618.json")
    requirement = sdlc_validator.load_json_object(requirement_path, "UAO dispatch authorization requirement")
    design = sdlc_validator.load_json_object(design_path, "UAO dispatch authorization design")

    requirement_errors = sdlc_validator.validate_artifact_record("requirement", requirement)
    design_errors = sdlc_validator.validate_artifact_record("design_decision", design)

    assert requirement_errors == []
    assert design_errors == []
    assert design["requirement_id"] == requirement["requirement_id"]
    assert DEFAULT_RECEIPT_PATH.name == "read_only_worker_uao_dispatch_authorization_witness.foundation.json"
    assert DEFAULT_SCHEMA_PATH.name == "read_only_worker_uao_dispatch_authorization_witness.schema.json"
