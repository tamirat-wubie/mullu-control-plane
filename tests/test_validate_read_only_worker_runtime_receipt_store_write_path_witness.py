"""Purpose: verify ReadOnlyWorkerRuntimeReceiptStoreWritePathWitness validation.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_read_only_worker_runtime_receipt_store_write_path_witness and SDLC validator.
Invariants:
  - Receipt-store writer registration and append are not performed by the witness.
  - Runtime dispatch and runtime receipt emission remain denied.
  - Future append-only, idempotency, failure, reconciliation, and terminal-closure guards are explicit.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts import validate_read_only_worker_runtime_receipt_store_write_path_witness as validator
from scripts import validate_sdlc_artifact as sdlc_validator


def test_store_write_path_witness_passes() -> None:
    errors = validator.validate_store_write_path_witness()
    receipt = validator.load_json_object(validator.DEFAULT_RECEIPT_PATH, "store write-path witness")

    assert errors == []
    assert receipt["receipt_version"] == validator.EXPECTED_RECEIPT_VERSION
    assert receipt["selected_worker_path"] == "read_only_repo_inspection"
    assert receipt["authority_scope"]["foundation_witness_only"] is True
    assert receipt["authority_scope"]["receipt_store_write_path_registered"] is False
    assert receipt["authority_scope"]["receipt_store_append_performed"] is False
    assert receipt["write_path_witness_contract"]["witness_mode"] == "RECEIPT_STORE_WRITE_PATH_WITNESS_ONLY"
    assert receipt["write_path_witness_contract"]["write_path_profile"] == (
        "APPEND_ONLY_DIGEST_ONLY_IDEMPOTENT_RECEIPT_STORE"
    )
    assert receipt["write_path_evaluation"]["append_only_policy_required"] is True
    assert receipt["write_path_evaluation"]["idempotency_key_required"] is True
    assert receipt["write_path_evaluation"]["raw_output_retention_allowed"] is False
    assert receipt["write_path_evaluation"]["receipt_store_append_performed"] is False
    assert receipt["admission_decision"]["runtime_dispatch_admitted"] is False
    assert receipt["admission_decision"]["terminal_closure_allowed"] is False
    assert validator.validate_store_write_path_witness_record(receipt) == []


def test_store_write_path_witness_rejects_authority_drift() -> None:
    mutated = validator.build_mutated_store_write_path_witness(
        authority_scope__foundation_witness_only=False,
        authority_scope__receipt_store_writer_registration_performed=True,
        authority_scope__receipt_store_write_path_registered=True,
        authority_scope__receipt_store_append_performed=True,
        authority_scope__runtime_runner_registration_performed=True,
        authority_scope__dispatch_endpoint_registration_performed=True,
        authority_scope__runtime_receipt_emitter_registration_performed=True,
        authority_scope__runtime_receipt_schema_binding_performed=True,
        authority_scope__runtime_dispatch_allowed=True,
        authority_scope__runtime_receipt_emission_allowed=True,
        authority_scope__external_network_allowed=True,
        authority_scope__secret_access_allowed=True,
        authority_scope__filesystem_write_allowed=True,
        authority_scope__connector_authority_allowed=True,
        authority_scope__terminal_closure_allowed=True,
        authority_scope__success_claim_allowed=True,
    )

    errors = validator.validate_store_write_path_witness_record(mutated)

    assert any("foundation_witness_only" in error for error in errors)
    assert any("receipt_store_writer_registration_performed" in error for error in errors)
    assert any("receipt_store_write_path_registered" in error for error in errors)
    assert any("receipt_store_append_performed" in error for error in errors)
    assert any("runtime_runner_registration_performed" in error for error in errors)
    assert any("dispatch_endpoint_registration_performed" in error for error in errors)
    assert any("runtime_receipt_emitter_registration_performed" in error for error in errors)
    assert any("runtime_receipt_schema_binding_performed" in error for error in errors)
    assert any("runtime_dispatch_allowed" in error for error in errors)
    assert any("runtime_receipt_emission_allowed" in error for error in errors)
    assert any("external_network_allowed" in error for error in errors)
    assert any("secret_access_allowed" in error for error in errors)
    assert any("filesystem_write_allowed" in error for error in errors)
    assert any("connector_authority_allowed" in error for error in errors)
    assert any("terminal_closure_allowed" in error for error in errors)
    assert any("success_claim_allowed" in error for error in errors)


def test_store_write_path_witness_rejects_contract_drift() -> None:
    mutated = validator.build_mutated_store_write_path_witness(
        selected_worker_path="read_only_search",
        write_path_witness_contract__worker_id="worker_search",
        write_path_witness_contract__capability="read_only_search",
        write_path_witness_contract__operation_family="web_search",
        write_path_witness_contract__witness_mode="LIVE_RECEIPT_STORE_WRITER",
        write_path_witness_contract__runtime_receipt_kind="runtime_receipt",
        write_path_witness_contract__source_schema_binding_witness_ref="examples/other.json",
        write_path_witness_contract__source_runtime_receipt_candidate_ref="examples/other.json",
        write_path_witness_contract__target_receipt_store_write_path_ref="receipt-store://live",
        write_path_witness_contract__write_path_profile="MUTABLE_RAW_OUTPUT_STORE",
    )

    errors = validator.validate_store_write_path_witness_record(mutated)

    assert any("selected_worker_path must be read_only_repo_inspection" in error for error in errors)
    assert any("match runtime receipt candidate" in error for error in errors)
    assert any("match schema binding witness" in error for error in errors)
    assert any("write_path_witness_contract.worker_id" in error for error in errors)
    assert any("write_path_witness_contract.capability" in error for error in errors)
    assert any("write_path_witness_contract.operation_family" in error for error in errors)
    assert any("write_path_witness_contract.witness_mode" in error for error in errors)
    assert any("write_path_witness_contract.runtime_receipt_kind" in error for error in errors)
    assert any("source_schema_binding_witness_ref" in error for error in errors)
    assert any("source_runtime_receipt_candidate_ref" in error for error in errors)
    assert any("target_receipt_store_write_path_ref" in error for error in errors)
    assert any("write_path_profile" in error for error in errors)


def test_store_write_path_witness_rejects_missing_required_refs() -> None:
    mutated = validator.build_mutated_store_write_path_witness(
        write_path_witness_contract__required_source_receipt_refs=[
            "examples/read_only_worker_runtime_receipt_schema_binding_witness.foundation.json"
        ],
        write_path_witness_contract__required_write_path_input_refs=[
            "evidence://runtime-receipt-schema-binding-witness"
        ],
        write_path_witness_contract__validation_refs=[
            "scripts/validate_read_only_worker_runtime_receipt_store_write_path_witness.py"
        ],
        admission_decision__remaining_denied_until_refs=["evidence://live-runtime-runner-registration-witness"],
        admission_decision__blocked_reason_refs=["blocked://runtime-runner/not-registered"],
        evidence_refs=["schemas/read_only_worker_runtime_receipt_store_write_path_witness.schema.json"],
    )

    errors = validator.validate_store_write_path_witness_record(mutated)

    assert any("required_source_receipt_refs missing required ref" in error for error in errors)
    assert any("required_write_path_input_refs missing required ref" in error for error in errors)
    assert any("validation_refs missing required ref" in error for error in errors)
    assert any("remaining_denied_until_refs missing required ref" in error for error in errors)
    assert any("blocked_reason_refs missing required ref" in error for error in errors)
    assert any("evidence_refs missing required ref" in error for error in errors)


def test_store_write_path_witness_rejects_evaluation_and_admission_drift() -> None:
    mutated = validator.build_mutated_store_write_path_witness(
        write_path_evaluation__upstream_schema_binding_witness_validated=False,
        write_path_evaluation__runtime_receipt_candidate_validated=False,
        write_path_evaluation__source_write_path_obligations_preserved=False,
        write_path_evaluation__append_only_policy_required=False,
        write_path_evaluation__idempotency_key_required=False,
        write_path_evaluation__tenant_actor_boundary_required=False,
        write_path_evaluation__output_digest_only_required=False,
        write_path_evaluation__raw_output_retention_allowed=True,
        write_path_evaluation__secret_material_retention_allowed=True,
        write_path_evaluation__receipt_store_writer_registration_performed=True,
        write_path_evaluation__receipt_store_write_path_registered=True,
        write_path_evaluation__receipt_store_append_performed=True,
        write_path_evaluation__runtime_receipt_emitted=True,
        write_path_evaluation__worker_failure_receipt_required_on_error=False,
        write_path_evaluation__effect_reconciliation_required=False,
        write_path_evaluation__mfidel_atomicity_preserved=False,
        admission_decision__decision="RUNTIME_RECEIPT_STORE_WRITE_PATH_REGISTERED",
        admission_decision__receipt_store_write_path_witness_defined=False,
        admission_decision__receipt_store_write_path_registered=True,
        admission_decision__receipt_store_append_admitted=True,
        admission_decision__runtime_receipt_emission_admitted=True,
        admission_decision__runtime_dispatch_admitted=True,
        admission_decision__terminal_closure_allowed=True,
    )

    errors = validator.validate_store_write_path_witness_record(mutated)

    assert any("write_path_evaluation.upstream_schema_binding_witness_validated" in error for error in errors)
    assert any("write_path_evaluation.runtime_receipt_candidate_validated" in error for error in errors)
    assert any("write_path_evaluation.source_write_path_obligations_preserved" in error for error in errors)
    assert any("write_path_evaluation.append_only_policy_required" in error for error in errors)
    assert any("write_path_evaluation.idempotency_key_required" in error for error in errors)
    assert any("write_path_evaluation.tenant_actor_boundary_required" in error for error in errors)
    assert any("write_path_evaluation.output_digest_only_required" in error for error in errors)
    assert any("write_path_evaluation.raw_output_retention_allowed" in error for error in errors)
    assert any("write_path_evaluation.secret_material_retention_allowed" in error for error in errors)
    assert any("write_path_evaluation.receipt_store_writer_registration_performed" in error for error in errors)
    assert any("write_path_evaluation.receipt_store_write_path_registered" in error for error in errors)
    assert any("write_path_evaluation.receipt_store_append_performed" in error for error in errors)
    assert any("write_path_evaluation.runtime_receipt_emitted" in error for error in errors)
    assert any("write_path_evaluation.worker_failure_receipt_required_on_error" in error for error in errors)
    assert any("write_path_evaluation.effect_reconciliation_required" in error for error in errors)
    assert any("write_path_evaluation.mfidel_atomicity_preserved" in error for error in errors)
    assert any("admission_decision.decision" in error for error in errors)
    assert any("admission_decision.receipt_store_write_path_witness_defined" in error for error in errors)
    assert any("admission_decision.receipt_store_write_path_registered" in error for error in errors)
    assert any("admission_decision.receipt_store_append_admitted" in error for error in errors)
    assert any("admission_decision.runtime_receipt_emission_admitted" in error for error in errors)
    assert any("admission_decision.runtime_dispatch_admitted" in error for error in errors)
    assert any("admission_decision.terminal_closure_allowed" in error for error in errors)


def test_store_write_path_witness_rejects_receipt_and_count_drift() -> None:
    mutated = validator.build_mutated_store_write_path_witness(
        receipt_refs__read_only_worker_runtime_receipt_store_write_path_witness_schema="schemas/other.schema.json",
        contract_summary__source_receipt_ref_count=1,
        contract_summary__write_path_input_ref_count=1,
        contract_summary__write_path_obligation_count=1,
        contract_summary__validation_ref_count=1,
        contract_summary__write_path_true_check_count=1,
        contract_summary__write_path_denied_check_count=1,
        contract_summary__remaining_denied_until_ref_count=1,
        contract_summary__blocked_reason_ref_count=1,
        contract_summary__receipt_ref_count=12,
        contract_summary__evidence_ref_count=1,
    )

    errors = validator.validate_store_write_path_witness_record(mutated)

    assert any(
        "receipt_refs.read_only_worker_runtime_receipt_store_write_path_witness_schema" in error
        for error in errors
    )
    assert any("contract_summary.source_receipt_ref_count" in error for error in errors)
    assert any("contract_summary.write_path_input_ref_count" in error for error in errors)
    assert any("contract_summary.write_path_obligation_count" in error for error in errors)
    assert any("contract_summary.validation_ref_count" in error for error in errors)
    assert any("contract_summary.write_path_true_check_count" in error for error in errors)
    assert any("contract_summary.write_path_denied_check_count" in error for error in errors)
    assert any("contract_summary.remaining_denied_until_ref_count" in error for error in errors)
    assert any("contract_summary.blocked_reason_ref_count" in error for error in errors)
    assert any("contract_summary.receipt_ref_count" in error for error in errors)
    assert any("contract_summary.evidence_ref_count" in error for error in errors)


def test_store_write_path_witness_cli_json_accepts_relative_paths(capsys) -> None:
    exit_code = validator.main(
        [
            "--schema",
            "schemas/read_only_worker_runtime_receipt_store_write_path_witness.schema.json",
            "--receipt",
            "examples/read_only_worker_runtime_receipt_store_write_path_witness.foundation.json",
            "--schema-binding-witness",
            "examples/read_only_worker_runtime_receipt_schema_binding_witness.foundation.json",
            "--runtime-receipt-candidate",
            "examples/read_only_worker_runtime_receipt_candidate.foundation.json",
            "--json",
        ]
    )

    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["status"] == "passed"
    assert Path(payload["schema_path"]).as_posix() == (
        "schemas/read_only_worker_runtime_receipt_store_write_path_witness.schema.json"
    )
    assert Path(payload["receipt_path"]).as_posix() == (
        "examples/read_only_worker_runtime_receipt_store_write_path_witness.foundation.json"
    )
    assert Path(payload["schema_binding_witness_path"]).as_posix() == (
        "examples/read_only_worker_runtime_receipt_schema_binding_witness.foundation.json"
    )
    assert Path(payload["runtime_receipt_candidate_path"]).as_posix() == (
        "examples/read_only_worker_runtime_receipt_candidate.foundation.json"
    )
    assert payload["errors"] == []


def test_malformed_store_write_path_witness_payload_reports_errors() -> None:
    schema = validator._load_schema(validator.DEFAULT_SCHEMA_PATH)

    none_errors = validator.validate_store_write_path_witness_record(None, schema)
    list_errors = validator.validate_store_write_path_witness_record([], schema)

    assert any(
        "read-only worker runtime receipt-store write-path witness must be a JSON object" in error
        for error in none_errors
    )
    assert any(
        "read-only worker runtime receipt-store write-path witness must be a JSON object" in error
        for error in list_errors
    )
    assert any("expected object" in error for error in none_errors + list_errors)


def test_sdlc_requirement_and_design_validate_for_store_write_path_witness() -> None:
    requirement_path = Path("examples/sdlc/requirement_runtime_receipt_store_write_path_witness_20260616.json")
    design_path = Path("examples/sdlc/design_runtime_receipt_store_write_path_witness_20260616.json")
    requirement = sdlc_validator.load_json_object(requirement_path, "store write-path witness requirement")
    design = sdlc_validator.load_json_object(design_path, "store write-path witness design")

    requirement_errors = sdlc_validator.validate_artifact_record("requirement", requirement)
    design_errors = sdlc_validator.validate_artifact_record("design_decision", design)

    assert requirement_errors == []
    assert design_errors == []
    assert design["requirement_id"] == requirement["requirement_id"]
    assert "schemas/read_only_worker_runtime_receipt_store_write_path_witness.schema.json" in design["schema_changes"]
    assert "scripts/validate_read_only_worker_runtime_receipt_store_write_path_witness.py" in design["validator_changes"]
    assert "no live worker dispatch" in requirement["non_goals"]
    assert "receipt-store writer registration remains unperformed" in requirement["constraints"]
    assert design["security_model"]["effect_bearing_requires_receipt"] is True
    assert any("run_workspace_governance_checks.py" in command for command in design["test_plan"])
