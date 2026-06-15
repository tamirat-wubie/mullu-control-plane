"""Purpose: verify ReadOnlyWorkerRuntimeReceiptEmitterDryRun validation.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_read_only_worker_runtime_receipt_emitter_dry_run and SDLC validator.
Invariants:
  - Runtime receipt emitter dry-run does not grant runtime authority.
  - Binding, lease preflight, rehearsal receipt, handoff, and console projection remain linked.
  - Future runtime dispatch stays blocked until named runtime evidence exists.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts import validate_read_only_worker_runtime_receipt_emitter_dry_run as validator
from scripts import validate_sdlc_artifact as sdlc_validator


def test_runtime_receipt_emitter_dry_run_passes() -> None:
    errors = validator.validate_emitter_dry_run()
    receipt = validator.load_json_object(validator.DEFAULT_RECEIPT_PATH, "ReadOnlyWorkerRuntimeReceiptEmitterDryRun")

    assert errors == []
    assert receipt["receipt_version"] == validator.EXPECTED_RECEIPT_VERSION
    assert receipt["selected_worker_path"] == "read_only_repo_inspection"
    assert receipt["authority_scope"]["runtime_dispatch_allowed"] is False
    assert receipt["authority_scope"]["runtime_receipt_emitter_registration_allowed"] is False
    assert receipt["simulated_emission_result"]["runtime_receipt_emitted"] is False
    assert receipt["admission_decision"]["runtime_dispatch_admitted"] is False
    assert validator.validate_emitter_dry_run_record(receipt) == []


def test_emitter_dry_run_rejects_authority_drift() -> None:
    mutated = validator.build_mutated_emitter_dry_run(
        authority_scope__foundation_dry_run_only=False,
        authority_scope__runtime_runner_registration_allowed=True,
        authority_scope__dispatch_endpoint_registration_allowed=True,
        authority_scope__runtime_receipt_emitter_registration_allowed=True,
        authority_scope__runtime_receipt_schema_binding_allowed=True,
        authority_scope__runtime_dispatch_allowed=True,
        authority_scope__external_network_allowed=True,
        authority_scope__secret_access_allowed=True,
        authority_scope__filesystem_write_allowed=True,
        authority_scope__connector_authority_allowed=True,
        authority_scope__terminal_closure_allowed=True,
        authority_scope__success_claim_allowed=True,
    )

    errors = validator.validate_emitter_dry_run_record(mutated)

    assert any("foundation_dry_run_only" in error for error in errors)
    assert any("runtime_runner_registration_allowed" in error for error in errors)
    assert any("dispatch_endpoint_registration_allowed" in error for error in errors)
    assert any("runtime_receipt_emitter_registration_allowed" in error for error in errors)
    assert any("runtime_receipt_schema_binding_allowed" in error for error in errors)
    assert any("runtime_dispatch_allowed" in error for error in errors)
    assert any("external_network_allowed" in error for error in errors)
    assert any("secret_access_allowed" in error for error in errors)
    assert any("filesystem_write_allowed" in error for error in errors)
    assert any("connector_authority_allowed" in error for error in errors)
    assert any("terminal_closure_allowed" in error for error in errors)
    assert any("success_claim_allowed" in error for error in errors)


def test_emitter_dry_run_rejects_worker_and_contract_drift() -> None:
    mutated = validator.build_mutated_emitter_dry_run(
        selected_worker_path="read_only_search",
        dry_run_contract__worker_id="worker_search",
        dry_run_contract__capability="read_only_search",
        dry_run_contract__operation_family="web_search",
        dry_run_contract__dry_run_mode="LIVE_EMITTER",
        dry_run_contract__source_handoff_ref="examples/other_handoff.json",
    )

    errors = validator.validate_emitter_dry_run_record(mutated)

    assert any("selected_worker_path must be read_only_repo_inspection" in error for error in errors)
    assert any("match handoff selected_worker_path" in error for error in errors)
    assert any("dry_run_contract.worker_id" in error for error in errors)
    assert any("dry_run_contract.capability" in error for error in errors)
    assert any("dry_run_contract.operation_family" in error for error in errors)
    assert any("dry_run_contract.dry_run_mode" in error for error in errors)
    assert any("dry_run_contract.source_handoff_ref" in error for error in errors)


def test_emitter_dry_run_rejects_missing_required_refs() -> None:
    mutated = validator.build_mutated_emitter_dry_run(
        dry_run_contract__required_source_receipt_refs=[
            "examples/read_only_worker_runtime_receipt_handoff.foundation.json"
        ],
        dry_run_contract__required_runtime_gate_refs=["gate://runtime-runner-registration"],
        dry_run_contract__required_runtime_witness_refs=["witness://runtime-runner/not-registered"],
        dry_run_contract__validation_refs=["scripts/validate_read_only_worker_runtime_receipt_emitter_dry_run.py"],
        admission_decision__remaining_denied_until_refs=["evidence://runtime-runner-registration"],
        admission_decision__blocked_reason_refs=["blocked://runtime-runner/not-registered"],
        evidence_refs=["schemas/read_only_worker_runtime_receipt_emitter_dry_run.schema.json"],
    )

    errors = validator.validate_emitter_dry_run_record(mutated)

    assert any("required_source_receipt_refs missing required ref" in error for error in errors)
    assert any("required_runtime_gate_refs missing required ref" in error for error in errors)
    assert any("required_runtime_witness_refs missing required ref" in error for error in errors)
    assert any("validation_refs missing required ref" in error for error in errors)
    assert any("remaining_denied_until_refs missing required ref" in error for error in errors)
    assert any("blocked_reason_refs missing required ref" in error for error in errors)
    assert any("evidence_refs missing required ref" in error for error in errors)


def test_emitter_dry_run_rejects_result_and_admission_drift() -> None:
    mutated = validator.build_mutated_emitter_dry_run(
        simulated_emission_result__result_state="RUNTIME_RECEIPT_EMITTED",
        simulated_emission_result__simulated_receipt_kind="worker_mesh_dispatch_receipt",
        simulated_emission_result__dry_run_receipt_recorded=False,
        simulated_emission_result__runtime_receipt_emitted=True,
        simulated_emission_result__worker_mesh_dispatch_receipt_emitted=True,
        simulated_emission_result__failure_receipt_path_bound=False,
        simulated_emission_result__effect_reconciliation_required=False,
        simulated_emission_result__raw_output_included=True,
        simulated_emission_result__raw_secret_material_included=True,
        simulated_emission_result__external_effects_observed=True,
        simulated_emission_result__filesystem_writes_observed=True,
        simulated_emission_result__connector_calls_observed=True,
        simulated_emission_result__terminal_closure=True,
        simulated_emission_result__success_claim_allowed=True,
        admission_decision__decision="DISPATCH_ADMITTED",
        admission_decision__runtime_dispatch_admitted=True,
        admission_decision__terminal_closure_allowed=True,
    )

    errors = validator.validate_emitter_dry_run_record(mutated)

    assert any("simulated_emission_result.result_state" in error for error in errors)
    assert any("simulated_emission_result.simulated_receipt_kind" in error for error in errors)
    assert any("simulated_emission_result.dry_run_receipt_recorded" in error for error in errors)
    assert any("simulated_emission_result.runtime_receipt_emitted" in error for error in errors)
    assert any("simulated_emission_result.worker_mesh_dispatch_receipt_emitted" in error for error in errors)
    assert any("simulated_emission_result.failure_receipt_path_bound" in error for error in errors)
    assert any("simulated_emission_result.effect_reconciliation_required" in error for error in errors)
    assert any("simulated_emission_result.raw_output_included" in error for error in errors)
    assert any("simulated_emission_result.raw_secret_material_included" in error for error in errors)
    assert any("simulated_emission_result.external_effects_observed" in error for error in errors)
    assert any("simulated_emission_result.filesystem_writes_observed" in error for error in errors)
    assert any("simulated_emission_result.connector_calls_observed" in error for error in errors)
    assert any("simulated_emission_result.terminal_closure" in error for error in errors)
    assert any("simulated_emission_result.success_claim_allowed" in error for error in errors)
    assert any("admission_decision.decision" in error for error in errors)
    assert any("admission_decision.runtime_dispatch_admitted" in error for error in errors)
    assert any("admission_decision.terminal_closure_allowed" in error for error in errors)


def test_emitter_dry_run_rejects_receipt_ref_and_count_drift() -> None:
    mutated = validator.build_mutated_emitter_dry_run(
        receipt_refs__read_only_worker_runtime_receipt_emitter_dry_run_schema="schemas/other.schema.json",
        receipt_refs__worker_mesh_schema="schemas/other_worker.schema.json",
        contract_summary__source_receipt_ref_count=1,
        contract_summary__runtime_gate_ref_count=1,
        contract_summary__runtime_witness_ref_count=1,
        contract_summary__emission_obligation_count=1,
        contract_summary__validation_ref_count=1,
        contract_summary__remaining_denied_until_ref_count=1,
        contract_summary__blocked_reason_ref_count=1,
        contract_summary__receipt_ref_count=8,
        contract_summary__evidence_ref_count=1,
    )

    errors = validator.validate_emitter_dry_run_record(mutated)

    assert any("receipt_refs.read_only_worker_runtime_receipt_emitter_dry_run_schema" in error for error in errors)
    assert any("receipt_refs.worker_mesh_schema" in error for error in errors)
    assert any("contract_summary.source_receipt_ref_count" in error for error in errors)
    assert any("contract_summary.runtime_gate_ref_count" in error for error in errors)
    assert any("contract_summary.runtime_witness_ref_count" in error for error in errors)
    assert any("contract_summary.emission_obligation_count" in error for error in errors)
    assert any("contract_summary.validation_ref_count" in error for error in errors)
    assert any("contract_summary.remaining_denied_until_ref_count" in error for error in errors)
    assert any("contract_summary.blocked_reason_ref_count" in error for error in errors)
    assert any("contract_summary.receipt_ref_count" in error for error in errors)
    assert any("contract_summary.evidence_ref_count" in error for error in errors)


def test_cli_json_accepts_relative_paths(capsys) -> None:
    exit_code = validator.main(
        [
            "--schema",
            "schemas/read_only_worker_runtime_receipt_emitter_dry_run.schema.json",
            "--receipt",
            "examples/read_only_worker_runtime_receipt_emitter_dry_run.foundation.json",
            "--handoff",
            "examples/read_only_worker_runtime_receipt_handoff.foundation.json",
            "--binding",
            "examples/read_only_worker_binding.foundation.json",
            "--preflight",
            "examples/read_only_worker_lease_preflight.foundation.json",
            "--rehearsal",
            "examples/read_only_worker_rehearsal_receipt.foundation.json",
            "--console",
            "examples/personal_assistant_console_read_model.json",
            "--json",
        ]
    )

    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["status"] == "passed"
    assert Path(payload["schema_path"]).as_posix() == "schemas/read_only_worker_runtime_receipt_emitter_dry_run.schema.json"
    assert Path(payload["receipt_path"]).as_posix() == "examples/read_only_worker_runtime_receipt_emitter_dry_run.foundation.json"
    assert Path(payload["handoff_path"]).as_posix() == "examples/read_only_worker_runtime_receipt_handoff.foundation.json"
    assert payload["errors"] == []


def test_malformed_emitter_dry_run_payload_reports_errors() -> None:
    schema = validator._load_schema(validator.DEFAULT_SCHEMA_PATH)

    none_errors = validator.validate_emitter_dry_run_record(None, schema)
    list_errors = validator.validate_emitter_dry_run_record([], schema)

    assert any("read-only worker runtime receipt emitter dry-run must be a JSON object" in error for error in none_errors)
    assert any("read-only worker runtime receipt emitter dry-run must be a JSON object" in error for error in list_errors)
    assert any("expected object" in error for error in none_errors + list_errors)


def test_sdlc_requirement_and_design_validate_for_runtime_receipt_emitter_dry_run() -> None:
    requirement_path = Path("examples/sdlc/requirement_runtime_receipt_emitter_dry_run_20260614.json")
    design_path = Path("examples/sdlc/design_runtime_receipt_emitter_dry_run_20260614.json")
    requirement = sdlc_validator.load_json_object(requirement_path, "runtime receipt emitter dry-run requirement")
    design = sdlc_validator.load_json_object(design_path, "runtime receipt emitter dry-run design")

    requirement_errors = sdlc_validator.validate_artifact_record("requirement", requirement)
    design_errors = sdlc_validator.validate_artifact_record("design_decision", design)

    assert requirement_errors == []
    assert design_errors == []
    assert design["requirement_id"] == requirement["requirement_id"]
    assert "schemas/read_only_worker_runtime_receipt_emitter_dry_run.schema.json" in design["schema_changes"]
    assert "scripts/validate_read_only_worker_runtime_receipt_emitter_dry_run.py" in design["validator_changes"]
    assert "no live worker dispatch" in requirement["non_goals"]
    assert "runtime receipt emitter registration remains denied" in requirement["constraints"]
    assert design["security_model"]["effect_bearing_requires_receipt"] is True
    assert any("run_workspace_governance_checks.py" in command for command in design["test_plan"])
