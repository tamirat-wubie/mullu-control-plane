"""Purpose: verify ReadOnlyWorkerReceiptAppendWitness validation.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: Receipt Append witness schema, fixture,
validator, and SDLC artifacts.
Invariants:
  - UAO dispatch authorization, Receipt Append, runtime dispatch
    admission, runtime dispatch, worker invocation, receipt emission, receipt
    append, success claims, and terminal closure remain denied.
  - Validation remains deterministic and read-only.
  - Mfidel atomicity remains preserved.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from scripts import validate_sdlc_artifact as sdlc_validator
from scripts.validate_read_only_worker_receipt_append_witness import (
    DEFAULT_RECEIPT_PATH,
    DEFAULT_SCHEMA_PATH,
    build_mutated_receipt_append_witness,
    main,
    validate_receipt_append_witness,
    validate_receipt_append_witness_record,
)
from scripts.validate_schemas import _load_schema


def test_receipt_append_witness_fixture_passes() -> None:
    errors = validate_receipt_append_witness()

    assert errors == []
    assert DEFAULT_SCHEMA_PATH.exists()
    assert DEFAULT_RECEIPT_PATH.exists()


def test_receipt_append_witness_rejects_authority_drift() -> None:
    schema = _load_schema(DEFAULT_SCHEMA_PATH)
    mutated = build_mutated_receipt_append_witness(
        authority_scope__active_runtime_lease_observed=True,
        authority_scope__uao_dispatch_authorization_performed=True,
        authority_scope__receipt_append_performed=True,
        authority_scope__success_claim_allowed=True,
    )

    errors = validate_receipt_append_witness_record(mutated, schema)

    assert "authority_scope.active_runtime_lease_observed must be false" in errors
    assert "authority_scope.uao_dispatch_authorization_performed must be false" in errors
    assert "authority_scope.receipt_append_performed must be false" in errors
    assert "authority_scope.success_claim_allowed must be false" in errors


def test_receipt_append_witness_rejects_contract_drift() -> None:
    schema = _load_schema(DEFAULT_SCHEMA_PATH)
    mutated = build_mutated_receipt_append_witness(
        receipt_append_contract__witness_mode="LIVE_DISPATCH",
        receipt_append_contract__target_receipt_append_ref="candidate://wrong",
        receipt_append_contract__append_profile="WRONG_PROFILE",
        receipt_append_contract__source_effect_reconciliation_witness_ref="examples/wrong.json",
        receipt_append_contract__source_runtime_receipt_emission_admission_witness_ref="examples/wrong.json",
        receipt_append_contract__source_runtime_receipt_store_activation_witness_ref="examples/wrong.json",
    )

    errors = validate_receipt_append_witness_record(mutated, schema)

    assert (
        "receipt_append_contract.witness_mode must be "
        "RECEIPT_APPEND_WITNESS_ONLY"
    ) in errors
    assert (
        "receipt_append_contract.target_receipt_append_ref is invalid"
    ) in errors
    assert (
        "receipt_append_contract.append_profile is invalid"
    ) in errors
    assert (
        "receipt_append_contract."
        "source_effect_reconciliation_witness_ref is invalid"
    ) in errors
    assert (
        "receipt_append_contract."
        "source_runtime_receipt_emission_admission_witness_ref is invalid"
    ) in errors
    assert (
        "receipt_append_contract."
        "source_runtime_receipt_store_activation_witness_ref is invalid"
    ) in errors


def test_receipt_append_witness_requires_authorization_input_refs() -> None:
    schema = _load_schema(DEFAULT_SCHEMA_PATH)
    mutated = build_mutated_receipt_append_witness()
    mutated["receipt_append_contract"]["required_authorization_input_refs"] = [
        "evidence://phi-gov/model-freeze"
    ]
    mutated["evidence_refs"] = [
        "schemas/read_only_worker_receipt_append_witness.schema.json"
    ]

    errors = validate_receipt_append_witness_record(mutated, schema)

    assert any(
        "required_authorization_input_refs missing required ref" in error for error in errors
    )
    assert any("evidence_refs missing required ref" in error for error in errors)
    assert any(
        "contract_summary.authorization_input_ref_count must match observed count" in error
        for error in errors
    )


def test_receipt_append_witness_rejects_admission_drift() -> None:
    schema = _load_schema(DEFAULT_SCHEMA_PATH)
    mutated = build_mutated_receipt_append_witness(
        activation_evaluation__active_runtime_lease_observed=True,
        activation_evaluation__runtime_dispatch_allowed=True,
        admission_decision__uao_dispatch_authorized=True,
        admission_decision__phi_gov_dispatch_authorized=True,
    )

    errors = validate_receipt_append_witness_record(mutated, schema)

    assert "activation_evaluation.active_runtime_lease_observed must be false" in errors
    assert "activation_evaluation.runtime_dispatch_allowed must be false" in errors
    assert "admission_decision.uao_dispatch_authorized must be false" in errors
    assert "admission_decision.phi_gov_dispatch_authorized must be false" in errors


def test_receipt_append_witness_rejects_summary_drift() -> None:
    schema = _load_schema(DEFAULT_SCHEMA_PATH)
    mutated = build_mutated_receipt_append_witness(
        contract_summary__activation_true_check_count=0,
        contract_summary__activation_denied_check_count=0,
        contract_summary__receipt_ref_count=0,
    )

    errors = validate_receipt_append_witness_record(mutated, schema)

    assert "contract_summary.activation_true_check_count must match observed count" in errors
    assert "contract_summary.activation_denied_check_count must match observed count" in errors
    assert "contract_summary.receipt_ref_count must match observed count" in errors


def test_receipt_append_witness_cli_json_paths_are_workspace_relative(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(sys, "argv", ["validate_read_only_worker_receipt_append_witness.py"])
        exit_code = main(["--json"])

    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["status"] == "passed"
    assert payload["schema_path"] in {
        "schemas\\read_only_worker_receipt_append_witness.schema.json",
        "schemas/read_only_worker_receipt_append_witness.schema.json",
    }
    assert payload["errors"] == []


def test_receipt_append_witness_rejects_malformed_payload() -> None:
    schema = _load_schema(DEFAULT_SCHEMA_PATH)

    errors = validate_receipt_append_witness_record([], schema)

    assert any("must be object" in error or "must be a JSON object" in error for error in errors)
    assert len(errors) >= 1
    assert schema["$id"] == "urn:mullusi:schema:read-only-worker-receipt-append-witness:1"


def test_receipt_append_witness_sdlc_artifacts_validate() -> None:
    requirement_path = Path(
        "examples/sdlc/requirement_receipt_append_witness_20260619.json"
    )
    design_path = Path("examples/sdlc/design_receipt_append_witness_20260619.json")
    requirement = sdlc_validator.load_json_object(requirement_path, "Receipt Append requirement")
    design = sdlc_validator.load_json_object(design_path, "Receipt Append design")

    requirement_errors = sdlc_validator.validate_artifact_record("requirement", requirement)
    design_errors = sdlc_validator.validate_artifact_record("design_decision", design)

    assert requirement_errors == []
    assert design_errors == []
    assert design["requirement_id"] == requirement["requirement_id"]
    assert DEFAULT_RECEIPT_PATH.name == "read_only_worker_receipt_append_witness.foundation.json"
    assert DEFAULT_SCHEMA_PATH.name == "read_only_worker_receipt_append_witness.schema.json"
