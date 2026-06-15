"""Purpose: verify ReadOnlyWorkerRuntimeReceiptCandidate validation.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_read_only_worker_runtime_receipt_candidate and SDLC validator.
Invariants:
  - Runtime receipt schema binding is not performed by the candidate.
  - Runtime dispatch and runtime receipt emission remain denied.
  - Future failure, effect reconciliation, and terminal-closure guards are explicit.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts import validate_read_only_worker_runtime_receipt_candidate as validator
from scripts import validate_sdlc_artifact as sdlc_validator


def test_runtime_receipt_candidate_passes() -> None:
    errors = validator.validate_runtime_receipt_candidate()
    receipt = validator.load_json_object(validator.DEFAULT_RECEIPT_PATH, "ReadOnlyWorkerRuntimeReceiptCandidate")

    assert errors == []
    assert receipt["receipt_version"] == validator.EXPECTED_RECEIPT_VERSION
    assert receipt["selected_worker_path"] == "read_only_repo_inspection"
    assert receipt["authority_scope"]["foundation_candidate_only"] is True
    assert receipt["authority_scope"]["runtime_receipt_schema_binding_performed"] is False
    assert receipt["authority_scope"]["runtime_receipt_emission_allowed"] is False
    assert receipt["runtime_receipt_candidate_contract"]["candidate_mode"] == "RUNTIME_RECEIPT_CANDIDATE_ONLY"
    assert receipt["candidate_execution_summary"]["execution_state"] == "NOT_EXECUTED_CANDIDATE_ONLY"
    assert receipt["candidate_execution_summary"]["runtime_receipt_emitted"] is False
    assert receipt["candidate_failure_policy"]["worker_failure_receipt_required"] is True
    assert receipt["admission_decision"]["runtime_dispatch_admitted"] is False
    assert validator.validate_runtime_receipt_candidate_record(receipt) == []


def test_runtime_receipt_candidate_rejects_authority_drift() -> None:
    mutated = validator.build_mutated_runtime_receipt_candidate(
        authority_scope__foundation_candidate_only=False,
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

    errors = validator.validate_runtime_receipt_candidate_record(mutated)

    assert any("foundation_candidate_only" in error for error in errors)
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


def test_runtime_receipt_candidate_rejects_contract_drift() -> None:
    mutated = validator.build_mutated_runtime_receipt_candidate(
        selected_worker_path="read_only_search",
        runtime_receipt_candidate_contract__worker_id="worker_search",
        runtime_receipt_candidate_contract__capability="read_only_search",
        runtime_receipt_candidate_contract__operation_family="web_search",
        runtime_receipt_candidate_contract__candidate_mode="LIVE_RUNTIME_RECEIPT",
        runtime_receipt_candidate_contract__source_runner_binding_witness_ref="examples/other.json",
        runtime_receipt_candidate_contract__source_emitter_dry_run_ref="examples/other.json",
    )

    errors = validator.validate_runtime_receipt_candidate_record(mutated)

    assert any("selected_worker_path must be read_only_repo_inspection" in error for error in errors)
    assert any("match runner binding witness" in error for error in errors)
    assert any("match emitter dry-run" in error for error in errors)
    assert any("runtime_receipt_candidate_contract.worker_id" in error for error in errors)
    assert any("runtime_receipt_candidate_contract.capability" in error for error in errors)
    assert any("runtime_receipt_candidate_contract.operation_family" in error for error in errors)
    assert any("runtime_receipt_candidate_contract.candidate_mode" in error for error in errors)
    assert any("source_runner_binding_witness_ref" in error for error in errors)
    assert any("source_emitter_dry_run_ref" in error for error in errors)


def test_runtime_receipt_candidate_rejects_missing_required_refs() -> None:
    mutated = validator.build_mutated_runtime_receipt_candidate(
        runtime_receipt_candidate_contract__required_source_receipt_refs=[
            "examples/read_only_worker_runtime_runner_binding_witness.foundation.json"
        ],
        runtime_receipt_candidate_contract__required_governance_gate_refs=["gate://runtime-runner-registration"],
        runtime_receipt_candidate_contract__required_runtime_evidence_refs=[
            "evidence://live-runtime-runner-registration-witness"
        ],
        runtime_receipt_candidate_contract__validation_refs=[
            "scripts/validate_read_only_worker_runtime_receipt_candidate.py"
        ],
        admission_decision__remaining_denied_until_refs=["evidence://live-runtime-runner-registration-witness"],
        admission_decision__blocked_reason_refs=["blocked://runtime-runner/not-registered"],
        evidence_refs=["schemas/read_only_worker_runtime_receipt_candidate.schema.json"],
    )

    errors = validator.validate_runtime_receipt_candidate_record(mutated)

    assert any("required_source_receipt_refs missing required ref" in error for error in errors)
    assert any("required_governance_gate_refs missing required ref" in error for error in errors)
    assert any("required_runtime_evidence_refs missing required ref" in error for error in errors)
    assert any("validation_refs missing required ref" in error for error in errors)
    assert any("remaining_denied_until_refs missing required ref" in error for error in errors)
    assert any("blocked_reason_refs missing required ref" in error for error in errors)
    assert any("evidence_refs missing required ref" in error for error in errors)


def test_runtime_receipt_candidate_rejects_execution_and_failure_drift() -> None:
    mutated = validator.build_mutated_runtime_receipt_candidate(
        candidate_receipt_envelope__uao_ref_required=False,
        candidate_receipt_envelope__raw_output_policy="RAW_OUTPUT_ALLOWED",
        candidate_execution_summary__execution_state="EXECUTED",
        candidate_execution_summary__runtime_dispatch_started=True,
        candidate_execution_summary__worker_invoked=True,
        candidate_execution_summary__runtime_receipt_emitted=True,
        candidate_execution_summary__worker_mesh_dispatch_receipt_emitted=True,
        candidate_execution_summary__failure_receipt_path_bound=False,
        candidate_execution_summary__effect_reconciliation_required=False,
        candidate_execution_summary__output_digest_only=False,
        candidate_execution_summary__output_digest="sha256:ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff",
        candidate_execution_summary__raw_output_included=True,
        candidate_execution_summary__raw_secret_material_included=True,
        candidate_execution_summary__external_effects_observed=True,
        candidate_execution_summary__filesystem_writes_observed=True,
        candidate_execution_summary__connector_calls_observed=True,
        candidate_execution_summary__terminal_closure=True,
        candidate_execution_summary__success_claim_allowed=True,
        candidate_failure_policy__worker_failure_receipt_required=False,
        candidate_failure_policy__unknown_effects_block_terminal_closure=False,
    )

    errors = validator.validate_runtime_receipt_candidate_record(mutated)

    assert any("candidate_receipt_envelope.uao_ref_required" in error for error in errors)
    assert any("candidate_receipt_envelope.raw_output_policy" in error for error in errors)
    assert any("candidate_execution_summary.execution_state" in error for error in errors)
    assert any("candidate_execution_summary.runtime_dispatch_started" in error for error in errors)
    assert any("candidate_execution_summary.worker_invoked" in error for error in errors)
    assert any("candidate_execution_summary.runtime_receipt_emitted" in error for error in errors)
    assert any("candidate_execution_summary.worker_mesh_dispatch_receipt_emitted" in error for error in errors)
    assert any("candidate_execution_summary.failure_receipt_path_bound" in error for error in errors)
    assert any("candidate_execution_summary.effect_reconciliation_required" in error for error in errors)
    assert any("candidate_execution_summary.output_digest_only" in error for error in errors)
    assert any("candidate_execution_summary.output_digest must match emitter dry-run" in error for error in errors)
    assert any("candidate_execution_summary.raw_output_included" in error for error in errors)
    assert any("candidate_execution_summary.raw_secret_material_included" in error for error in errors)
    assert any("candidate_execution_summary.external_effects_observed" in error for error in errors)
    assert any("candidate_execution_summary.filesystem_writes_observed" in error for error in errors)
    assert any("candidate_execution_summary.connector_calls_observed" in error for error in errors)
    assert any("candidate_execution_summary.terminal_closure" in error for error in errors)
    assert any("candidate_execution_summary.success_claim_allowed" in error for error in errors)
    assert any("candidate_failure_policy.worker_failure_receipt_required" in error for error in errors)
    assert any("candidate_failure_policy.unknown_effects_block_terminal_closure" in error for error in errors)


def test_runtime_receipt_candidate_rejects_admission_and_count_drift() -> None:
    mutated = validator.build_mutated_runtime_receipt_candidate(
        admission_decision__decision="RUNTIME_RECEIPT_CANDIDATE_ADMITTED",
        admission_decision__candidate_defined=False,
        admission_decision__runtime_receipt_schema_bound=True,
        admission_decision__runtime_receipt_emission_admitted=True,
        admission_decision__runtime_dispatch_admitted=True,
        admission_decision__terminal_closure_allowed=True,
        receipt_refs__read_only_worker_runtime_receipt_candidate_schema="schemas/other.schema.json",
        contract_summary__source_receipt_ref_count=1,
        contract_summary__governance_gate_ref_count=1,
        contract_summary__runtime_evidence_ref_count=1,
        contract_summary__candidate_obligation_count=1,
        contract_summary__validation_ref_count=1,
        contract_summary__envelope_required_ref_count=1,
        contract_summary__failure_policy_required_count=1,
        contract_summary__remaining_denied_until_ref_count=1,
        contract_summary__blocked_reason_ref_count=1,
        contract_summary__receipt_ref_count=10,
        contract_summary__evidence_ref_count=1,
    )

    errors = validator.validate_runtime_receipt_candidate_record(mutated)

    assert any("admission_decision.decision" in error for error in errors)
    assert any("admission_decision.candidate_defined" in error for error in errors)
    assert any("admission_decision.runtime_receipt_schema_bound" in error for error in errors)
    assert any("admission_decision.runtime_receipt_emission_admitted" in error for error in errors)
    assert any("admission_decision.runtime_dispatch_admitted" in error for error in errors)
    assert any("admission_decision.terminal_closure_allowed" in error for error in errors)
    assert any("receipt_refs.read_only_worker_runtime_receipt_candidate_schema" in error for error in errors)
    assert any("contract_summary.source_receipt_ref_count" in error for error in errors)
    assert any("contract_summary.governance_gate_ref_count" in error for error in errors)
    assert any("contract_summary.receipt_ref_count" in error for error in errors)


def test_cli_json_accepts_relative_paths(capsys) -> None:
    exit_code = validator.main(
        [
            "--schema",
            "schemas/read_only_worker_runtime_receipt_candidate.schema.json",
            "--receipt",
            "examples/read_only_worker_runtime_receipt_candidate.foundation.json",
            "--runner-binding-witness",
            "examples/read_only_worker_runtime_runner_binding_witness.foundation.json",
            "--emitter-dry-run",
            "examples/read_only_worker_runtime_receipt_emitter_dry_run.foundation.json",
            "--json",
        ]
    )

    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["status"] == "passed"
    assert Path(payload["schema_path"]).as_posix() == "schemas/read_only_worker_runtime_receipt_candidate.schema.json"
    assert Path(payload["receipt_path"]).as_posix() == "examples/read_only_worker_runtime_receipt_candidate.foundation.json"
    assert Path(payload["runner_binding_witness_path"]).as_posix() == (
        "examples/read_only_worker_runtime_runner_binding_witness.foundation.json"
    )
    assert Path(payload["emitter_dry_run_path"]).as_posix() == (
        "examples/read_only_worker_runtime_receipt_emitter_dry_run.foundation.json"
    )
    assert payload["errors"] == []


def test_malformed_runtime_receipt_candidate_payload_reports_errors() -> None:
    schema = validator._load_schema(validator.DEFAULT_SCHEMA_PATH)

    none_errors = validator.validate_runtime_receipt_candidate_record(None, schema)
    list_errors = validator.validate_runtime_receipt_candidate_record([], schema)

    assert any("read-only worker runtime receipt candidate must be a JSON object" in error for error in none_errors)
    assert any("read-only worker runtime receipt candidate must be a JSON object" in error for error in list_errors)
    assert any("expected object" in error for error in none_errors + list_errors)


def test_sdlc_requirement_and_design_validate_for_runtime_receipt_candidate() -> None:
    requirement_path = Path("examples/sdlc/requirement_runtime_receipt_candidate_20260615.json")
    design_path = Path("examples/sdlc/design_runtime_receipt_candidate_20260615.json")
    requirement = sdlc_validator.load_json_object(requirement_path, "runtime receipt candidate requirement")
    design = sdlc_validator.load_json_object(design_path, "runtime receipt candidate design")

    requirement_errors = sdlc_validator.validate_artifact_record("requirement", requirement)
    design_errors = sdlc_validator.validate_artifact_record("design_decision", design)

    assert requirement_errors == []
    assert design_errors == []
    assert design["requirement_id"] == requirement["requirement_id"]
    assert "schemas/read_only_worker_runtime_receipt_candidate.schema.json" in design["schema_changes"]
    assert "scripts/validate_read_only_worker_runtime_receipt_candidate.py" in design["validator_changes"]
    assert "no live worker dispatch" in requirement["non_goals"]
    assert "runtime receipt schema binding remains unperformed" in requirement["constraints"]
    assert design["security_model"]["effect_bearing_requires_receipt"] is True
    assert any("run_workspace_governance_checks.py" in command for command in design["test_plan"])
