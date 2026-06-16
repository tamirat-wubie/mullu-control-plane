"""Purpose: verify ReadOnlyWorkerRuntimeReceiptSchemaBindingWitness validation.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_read_only_worker_runtime_receipt_schema_binding_witness and SDLC validator.
Invariants:
  - Runtime receipt schema binding is not performed by the witness.
  - Runtime dispatch and runtime receipt emission remain denied.
  - Future failure, effect reconciliation, receipt-store, and terminal-closure guards are explicit.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts import validate_read_only_worker_runtime_receipt_schema_binding_witness as validator
from scripts import validate_sdlc_artifact as sdlc_validator


def test_schema_binding_witness_passes() -> None:
    errors = validator.validate_schema_binding_witness()
    receipt = validator.load_json_object(validator.DEFAULT_RECEIPT_PATH, "schema binding witness")

    assert errors == []
    assert receipt["receipt_version"] == validator.EXPECTED_RECEIPT_VERSION
    assert receipt["selected_worker_path"] == "read_only_repo_inspection"
    assert receipt["authority_scope"]["foundation_witness_only"] is True
    assert receipt["authority_scope"]["runtime_receipt_schema_binding_performed"] is False
    assert receipt["authority_scope"]["runtime_receipt_schema_registry_write_performed"] is False
    assert receipt["schema_binding_witness_contract"]["witness_mode"] == "SCHEMA_BINDING_WITNESS_ONLY"
    assert receipt["schema_binding_witness_contract"]["source_candidate_schema_ref"] == (
        "schemas/read_only_worker_runtime_receipt_candidate.schema.json"
    )
    assert receipt["binding_evaluation"]["candidate_schema_validated"] is True
    assert receipt["binding_evaluation"]["runtime_receipt_emitted"] is False
    assert receipt["admission_decision"]["runtime_dispatch_admitted"] is False
    assert receipt["admission_decision"]["terminal_closure_allowed"] is False
    assert validator.validate_schema_binding_witness_record(receipt) == []


def test_schema_binding_witness_rejects_authority_drift() -> None:
    mutated = validator.build_mutated_schema_binding_witness(
        authority_scope__foundation_witness_only=False,
        authority_scope__runtime_runner_registration_performed=True,
        authority_scope__dispatch_endpoint_registration_performed=True,
        authority_scope__runtime_receipt_emitter_registration_performed=True,
        authority_scope__runtime_receipt_schema_binding_performed=True,
        authority_scope__runtime_receipt_schema_registry_write_performed=True,
        authority_scope__runtime_dispatch_allowed=True,
        authority_scope__runtime_receipt_emission_allowed=True,
        authority_scope__external_network_allowed=True,
        authority_scope__secret_access_allowed=True,
        authority_scope__filesystem_write_allowed=True,
        authority_scope__connector_authority_allowed=True,
        authority_scope__terminal_closure_allowed=True,
        authority_scope__success_claim_allowed=True,
    )

    errors = validator.validate_schema_binding_witness_record(mutated)

    assert any("foundation_witness_only" in error for error in errors)
    assert any("runtime_runner_registration_performed" in error for error in errors)
    assert any("dispatch_endpoint_registration_performed" in error for error in errors)
    assert any("runtime_receipt_emitter_registration_performed" in error for error in errors)
    assert any("runtime_receipt_schema_binding_performed" in error for error in errors)
    assert any("runtime_receipt_schema_registry_write_performed" in error for error in errors)
    assert any("runtime_dispatch_allowed" in error for error in errors)
    assert any("runtime_receipt_emission_allowed" in error for error in errors)
    assert any("external_network_allowed" in error for error in errors)
    assert any("secret_access_allowed" in error for error in errors)
    assert any("filesystem_write_allowed" in error for error in errors)
    assert any("connector_authority_allowed" in error for error in errors)
    assert any("terminal_closure_allowed" in error for error in errors)
    assert any("success_claim_allowed" in error for error in errors)


def test_schema_binding_witness_rejects_contract_drift() -> None:
    mutated = validator.build_mutated_schema_binding_witness(
        selected_worker_path="read_only_search",
        schema_binding_witness_contract__worker_id="worker_search",
        schema_binding_witness_contract__capability="read_only_search",
        schema_binding_witness_contract__operation_family="web_search",
        schema_binding_witness_contract__witness_mode="LIVE_SCHEMA_BINDING",
        schema_binding_witness_contract__runtime_receipt_kind="runtime_receipt",
        schema_binding_witness_contract__source_runtime_receipt_candidate_ref="examples/other.json",
        schema_binding_witness_contract__source_candidate_schema_ref="schemas/other.schema.json",
        schema_binding_witness_contract__target_runtime_receipt_schema_ref="schema://live",
    )

    errors = validator.validate_schema_binding_witness_record(mutated)

    assert any("selected_worker_path must be read_only_repo_inspection" in error for error in errors)
    assert any("match runtime receipt candidate" in error for error in errors)
    assert any("schema_binding_witness_contract.worker_id" in error for error in errors)
    assert any("schema_binding_witness_contract.capability" in error for error in errors)
    assert any("schema_binding_witness_contract.operation_family" in error for error in errors)
    assert any("schema_binding_witness_contract.witness_mode" in error for error in errors)
    assert any("schema_binding_witness_contract.runtime_receipt_kind" in error for error in errors)
    assert any("source_runtime_receipt_candidate_ref" in error for error in errors)
    assert any("source_candidate_schema_ref" in error for error in errors)
    assert any("target_runtime_receipt_schema_ref" in error for error in errors)


def test_schema_binding_witness_rejects_missing_required_refs() -> None:
    mutated = validator.build_mutated_schema_binding_witness(
        schema_binding_witness_contract__required_source_receipt_refs=[
            "examples/read_only_worker_runtime_receipt_candidate.foundation.json"
        ],
        schema_binding_witness_contract__required_schema_binding_input_refs=[
            "schema://read-only-worker-runtime-receipt-candidate"
        ],
        schema_binding_witness_contract__validation_refs=[
            "scripts/validate_read_only_worker_runtime_receipt_schema_binding_witness.py"
        ],
        admission_decision__remaining_denied_until_refs=["evidence://live-runtime-runner-registration-witness"],
        admission_decision__blocked_reason_refs=["blocked://runtime-runner/not-registered"],
        evidence_refs=["schemas/read_only_worker_runtime_receipt_schema_binding_witness.schema.json"],
    )

    errors = validator.validate_schema_binding_witness_record(mutated)

    assert any("required_source_receipt_refs missing required ref" in error for error in errors)
    assert any("required_schema_binding_input_refs missing required ref" in error for error in errors)
    assert any("validation_refs missing required ref" in error for error in errors)
    assert any("remaining_denied_until_refs missing required ref" in error for error in errors)
    assert any("blocked_reason_refs missing required ref" in error for error in errors)
    assert any("evidence_refs missing required ref" in error for error in errors)


def test_schema_binding_witness_rejects_binding_and_admission_drift() -> None:
    mutated = validator.build_mutated_schema_binding_witness(
        binding_evaluation__candidate_schema_validated=False,
        binding_evaluation__candidate_example_validated=False,
        binding_evaluation__upstream_runner_binding_witness_validated=False,
        binding_evaluation__upstream_emitter_dry_run_validated=False,
        binding_evaluation__source_candidate_obligations_preserved=False,
        binding_evaluation__runtime_receipt_schema_binding_performed=True,
        binding_evaluation__runtime_receipt_schema_registry_write_performed=True,
        binding_evaluation__runtime_receipt_emitted=True,
        binding_evaluation__raw_output_policy="RAW_OUTPUT_ALLOWED",
        binding_evaluation__worker_failure_receipt_required_on_error=False,
        binding_evaluation__effect_reconciliation_required=False,
        binding_evaluation__mfidel_atomicity_preserved=False,
        admission_decision__decision="RUNTIME_RECEIPT_SCHEMA_BOUND",
        admission_decision__schema_binding_witness_defined=False,
        admission_decision__runtime_receipt_schema_bound=True,
        admission_decision__runtime_receipt_emission_admitted=True,
        admission_decision__runtime_dispatch_admitted=True,
        admission_decision__terminal_closure_allowed=True,
    )

    errors = validator.validate_schema_binding_witness_record(mutated)

    assert any("binding_evaluation.candidate_schema_validated" in error for error in errors)
    assert any("binding_evaluation.candidate_example_validated" in error for error in errors)
    assert any("binding_evaluation.upstream_runner_binding_witness_validated" in error for error in errors)
    assert any("binding_evaluation.upstream_emitter_dry_run_validated" in error for error in errors)
    assert any("binding_evaluation.source_candidate_obligations_preserved" in error for error in errors)
    assert any("binding_evaluation.runtime_receipt_schema_binding_performed" in error for error in errors)
    assert any("binding_evaluation.runtime_receipt_schema_registry_write_performed" in error for error in errors)
    assert any("binding_evaluation.runtime_receipt_emitted" in error for error in errors)
    assert any("binding_evaluation.raw_output_policy" in error for error in errors)
    assert any("binding_evaluation.worker_failure_receipt_required_on_error" in error for error in errors)
    assert any("binding_evaluation.effect_reconciliation_required" in error for error in errors)
    assert any("binding_evaluation.mfidel_atomicity_preserved" in error for error in errors)
    assert any("admission_decision.decision" in error for error in errors)
    assert any("admission_decision.schema_binding_witness_defined" in error for error in errors)
    assert any("admission_decision.runtime_receipt_schema_bound" in error for error in errors)
    assert any("admission_decision.runtime_receipt_emission_admitted" in error for error in errors)
    assert any("admission_decision.runtime_dispatch_admitted" in error for error in errors)
    assert any("admission_decision.terminal_closure_allowed" in error for error in errors)


def test_schema_binding_witness_rejects_receipt_and_count_drift() -> None:
    mutated = validator.build_mutated_schema_binding_witness(
        receipt_refs__read_only_worker_runtime_receipt_schema_binding_witness_schema="schemas/other.schema.json",
        contract_summary__source_receipt_ref_count=1,
        contract_summary__schema_binding_input_ref_count=1,
        contract_summary__schema_binding_obligation_count=1,
        contract_summary__validation_ref_count=1,
        contract_summary__binding_true_check_count=1,
        contract_summary__remaining_denied_until_ref_count=1,
        contract_summary__blocked_reason_ref_count=1,
        contract_summary__receipt_ref_count=11,
        contract_summary__evidence_ref_count=1,
    )

    errors = validator.validate_schema_binding_witness_record(mutated)

    assert any("receipt_refs.read_only_worker_runtime_receipt_schema_binding_witness_schema" in error for error in errors)
    assert any("contract_summary.source_receipt_ref_count" in error for error in errors)
    assert any("contract_summary.schema_binding_input_ref_count" in error for error in errors)
    assert any("contract_summary.schema_binding_obligation_count" in error for error in errors)
    assert any("contract_summary.validation_ref_count" in error for error in errors)
    assert any("contract_summary.binding_true_check_count" in error for error in errors)
    assert any("contract_summary.remaining_denied_until_ref_count" in error for error in errors)
    assert any("contract_summary.blocked_reason_ref_count" in error for error in errors)
    assert any("contract_summary.receipt_ref_count" in error for error in errors)
    assert any("contract_summary.evidence_ref_count" in error for error in errors)


def test_schema_binding_witness_cli_json_accepts_relative_paths(capsys) -> None:
    exit_code = validator.main(
        [
            "--schema",
            "schemas/read_only_worker_runtime_receipt_schema_binding_witness.schema.json",
            "--receipt",
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
        "schemas/read_only_worker_runtime_receipt_schema_binding_witness.schema.json"
    )
    assert Path(payload["receipt_path"]).as_posix() == (
        "examples/read_only_worker_runtime_receipt_schema_binding_witness.foundation.json"
    )
    assert Path(payload["runtime_receipt_candidate_path"]).as_posix() == (
        "examples/read_only_worker_runtime_receipt_candidate.foundation.json"
    )
    assert payload["errors"] == []


def test_malformed_schema_binding_witness_payload_reports_errors() -> None:
    schema = validator._load_schema(validator.DEFAULT_SCHEMA_PATH)

    none_errors = validator.validate_schema_binding_witness_record(None, schema)
    list_errors = validator.validate_schema_binding_witness_record([], schema)

    assert any("read-only worker runtime receipt schema-binding witness must be a JSON object" in error for error in none_errors)
    assert any("read-only worker runtime receipt schema-binding witness must be a JSON object" in error for error in list_errors)
    assert any("expected object" in error for error in none_errors + list_errors)


def test_sdlc_requirement_and_design_validate_for_schema_binding_witness() -> None:
    requirement_path = Path("examples/sdlc/requirement_runtime_receipt_schema_binding_witness_20260615.json")
    design_path = Path("examples/sdlc/design_runtime_receipt_schema_binding_witness_20260615.json")
    requirement = sdlc_validator.load_json_object(requirement_path, "schema binding witness requirement")
    design = sdlc_validator.load_json_object(design_path, "schema binding witness design")

    requirement_errors = sdlc_validator.validate_artifact_record("requirement", requirement)
    design_errors = sdlc_validator.validate_artifact_record("design_decision", design)

    assert requirement_errors == []
    assert design_errors == []
    assert design["requirement_id"] == requirement["requirement_id"]
    assert "schemas/read_only_worker_runtime_receipt_schema_binding_witness.schema.json" in design["schema_changes"]
    assert "scripts/validate_read_only_worker_runtime_receipt_schema_binding_witness.py" in design["validator_changes"]
    assert "no live worker dispatch" in requirement["non_goals"]
    assert "runtime receipt schema binding remains unperformed" in requirement["constraints"]
    assert design["security_model"]["effect_bearing_requires_receipt"] is True
    assert any("run_workspace_governance_checks.py" in command for command in design["test_plan"])
