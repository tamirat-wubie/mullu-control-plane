"""Purpose: verify ReadOnlyWorkerRuntimeReceiptHandoff validation.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_read_only_worker_runtime_receipt_handoff and SDLC validator.
Invariants:
  - Runtime receipt emission handoff does not grant runtime authority.
  - Binding, lease preflight, rehearsal receipt, and console projection remain linked.
  - Future runtime dispatch stays blocked until named evidence exists.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts import validate_read_only_worker_runtime_receipt_handoff as validator
from scripts import validate_sdlc_artifact as sdlc_validator


def test_runtime_receipt_handoff_passes() -> None:
    errors = validator.validate_runtime_receipt_handoff()
    handoff = validator.load_json_object(validator.DEFAULT_HANDOFF_PATH, "ReadOnlyWorkerRuntimeReceiptHandoff")

    assert errors == []
    assert handoff["handoff_version"] == validator.EXPECTED_HANDOFF_VERSION
    assert handoff["selected_worker_path"] == "read_only_repo_inspection"
    assert handoff["authority_scope"]["runtime_dispatch_allowed"] is False
    assert handoff["admission_guards"]["runtime_receipt_emitter_registered"] is False
    assert handoff["handoff_result"]["runtime_dispatch_admitted"] is False
    assert handoff["handoff_result"]["terminal_closure"] is False
    assert validator.validate_handoff_record(handoff) == []


def test_handoff_rejects_authority_drift() -> None:
    mutated = validator.build_mutated_handoff(
        authority_scope__foundation_handoff_only=False,
        authority_scope__runtime_registration_allowed=True,
        authority_scope__dispatch_endpoint_allowed=True,
        authority_scope__runtime_dispatch_allowed=True,
        authority_scope__external_network_allowed=True,
        authority_scope__secret_access_allowed=True,
        authority_scope__filesystem_write_allowed=True,
        authority_scope__connector_authority_allowed=True,
        authority_scope__terminal_closure_allowed=True,
        authority_scope__success_claim_allowed=True,
    )

    errors = validator.validate_handoff_record(mutated)

    assert any("foundation_handoff_only" in error for error in errors)
    assert any("runtime_registration_allowed" in error for error in errors)
    assert any("dispatch_endpoint_allowed" in error for error in errors)
    assert any("runtime_dispatch_allowed" in error for error in errors)
    assert any("external_network_allowed" in error for error in errors)
    assert any("secret_access_allowed" in error for error in errors)
    assert any("filesystem_write_allowed" in error for error in errors)
    assert any("connector_authority_allowed" in error for error in errors)
    assert any("terminal_closure_allowed" in error for error in errors)
    assert any("success_claim_allowed" in error for error in errors)


def test_handoff_rejects_worker_and_state_drift() -> None:
    mutated = validator.build_mutated_handoff(
        selected_worker_path="read_only_search",
        emission_handoff_contract__worker_id="worker_search",
        emission_handoff_contract__capability="read_only_search",
        emission_handoff_contract__operation_family="web_search",
        emission_handoff_contract__handoff_state="AWAITING_RUNTIME_EVIDENCE",
    )

    errors = validator.validate_handoff_record(mutated)

    assert any("selected_worker_path must be read_only_repo_inspection" in error for error in errors)
    assert any("match binding selected_worker_path" in error for error in errors)
    assert any("match preflight selected_worker_path" in error for error in errors)
    assert any("match rehearsal selected_worker_path" in error for error in errors)
    assert any("emission_handoff_contract.worker_id" in error for error in errors)
    assert any("emission_handoff_contract.capability" in error for error in errors)
    assert any("emission_handoff_contract.operation_family" in error for error in errors)
    assert any("handoff_state must be FOUNDATION_HANDOFF_RECORDED" in error for error in errors)


def test_handoff_rejects_missing_required_refs() -> None:
    mutated = validator.build_mutated_handoff(
        emission_handoff_contract__required_source_receipt_refs=[
            "examples/read_only_worker_binding.foundation.json"
        ],
        emission_handoff_contract__required_emission_gate_refs=["gate://runtime-runner-registration"],
        emission_handoff_contract__required_runtime_witness_refs=["witness://runtime-runner/not-registered"],
        emission_handoff_contract__receipt_schema_refs=["schemas/worker_mesh.schema.json"],
        emission_handoff_contract__validation_refs=["scripts/validate_read_only_worker_runtime_receipt_handoff.py"],
        emission_handoff_contract__denied_until_refs=["evidence://runtime-runner-registration"],
        evidence_refs=["schemas/read_only_worker_runtime_receipt_handoff.schema.json"],
    )

    errors = validator.validate_handoff_record(mutated)

    assert any("required_source_receipt_refs missing required ref" in error for error in errors)
    assert any("required_emission_gate_refs missing required ref" in error for error in errors)
    assert any("required_runtime_witness_refs missing required ref" in error for error in errors)
    assert any("receipt_schema_refs missing required ref" in error for error in errors)
    assert any("validation_refs missing required ref" in error for error in errors)
    assert any("denied_until_refs missing required ref" in error for error in errors)
    assert any("evidence_refs missing required ref" in error for error in errors)


def test_handoff_rejects_admission_and_result_drift() -> None:
    mutated = validator.build_mutated_handoff(
        admission_guards__binding_validated=False,
        admission_guards__lease_preflight_validated=False,
        admission_guards__rehearsal_receipt_validated=False,
        admission_guards__console_projection_validated=False,
        admission_guards__runtime_runner_registered=True,
        admission_guards__dispatch_endpoint_registered=True,
        admission_guards__runtime_receipt_emitter_registered=True,
        admission_guards__runtime_receipt_schema_bound=True,
        admission_guards__effect_reconciliation_required=False,
        admission_guards__failure_receipt_required_on_error=False,
        admission_guards__terminal_closure_blocked_until_runtime_receipt=False,
        handoff_result__runtime_dispatch_admitted=True,
        handoff_result__external_effects_observed=True,
        handoff_result__filesystem_writes_observed=True,
        handoff_result__connector_calls_observed=True,
        handoff_result__terminal_closure=True,
        handoff_result__success_claim_allowed=True,
    )

    errors = validator.validate_handoff_record(mutated)

    assert any("admission_guards.binding_validated" in error for error in errors)
    assert any("admission_guards.runtime_runner_registered" in error for error in errors)
    assert any("admission_guards.dispatch_endpoint_registered" in error for error in errors)
    assert any("admission_guards.runtime_receipt_emitter_registered" in error for error in errors)
    assert any("admission_guards.runtime_receipt_schema_bound" in error for error in errors)
    assert any("admission_guards.effect_reconciliation_required" in error for error in errors)
    assert any("admission_guards.failure_receipt_required_on_error" in error for error in errors)
    assert any("handoff_result.runtime_dispatch_admitted" in error for error in errors)
    assert any("handoff_result.external_effects_observed" in error for error in errors)
    assert any("handoff_result.filesystem_writes_observed" in error for error in errors)
    assert any("handoff_result.connector_calls_observed" in error for error in errors)
    assert any("handoff_result.terminal_closure" in error for error in errors)
    assert any("handoff_result.success_claim_allowed" in error for error in errors)


def test_handoff_rejects_receipt_ref_and_count_drift() -> None:
    mutated = validator.build_mutated_handoff(
        receipt_refs__read_only_worker_runtime_receipt_handoff_schema="schemas/other.schema.json",
        receipt_refs__worker_mesh_schema="schemas/other_worker.schema.json",
        contract_summary__source_receipt_ref_count=1,
        contract_summary__emission_gate_ref_count=1,
        contract_summary__runtime_witness_ref_count=1,
        contract_summary__receipt_schema_ref_count=1,
        contract_summary__validation_ref_count=1,
        contract_summary__denied_until_ref_count=1,
        contract_summary__future_emitter_obligation_count=1,
        contract_summary__next_required_evidence_count=1,
        contract_summary__receipt_ref_count=7,
        contract_summary__evidence_ref_count=1,
    )

    errors = validator.validate_handoff_record(mutated)

    assert any("receipt_refs.read_only_worker_runtime_receipt_handoff_schema" in error for error in errors)
    assert any("receipt_refs.worker_mesh_schema" in error for error in errors)
    assert any("contract_summary.source_receipt_ref_count" in error for error in errors)
    assert any("contract_summary.emission_gate_ref_count" in error for error in errors)
    assert any("contract_summary.runtime_witness_ref_count" in error for error in errors)
    assert any("contract_summary.receipt_schema_ref_count" in error for error in errors)
    assert any("contract_summary.validation_ref_count" in error for error in errors)
    assert any("contract_summary.denied_until_ref_count" in error for error in errors)
    assert any("contract_summary.future_emitter_obligation_count" in error for error in errors)
    assert any("contract_summary.next_required_evidence_count" in error for error in errors)
    assert any("contract_summary.receipt_ref_count" in error for error in errors)
    assert any("contract_summary.evidence_ref_count" in error for error in errors)


def test_cli_json_accepts_relative_paths(capsys) -> None:
    exit_code = validator.main(
        [
            "--schema",
            "schemas/read_only_worker_runtime_receipt_handoff.schema.json",
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
    assert Path(payload["schema_path"]).as_posix() == "schemas/read_only_worker_runtime_receipt_handoff.schema.json"
    assert Path(payload["handoff_path"]).as_posix() == "examples/read_only_worker_runtime_receipt_handoff.foundation.json"
    assert Path(payload["rehearsal_path"]).as_posix() == "examples/read_only_worker_rehearsal_receipt.foundation.json"
    assert Path(payload["console_path"]).as_posix() == "examples/personal_assistant_console_read_model.json"
    assert payload["errors"] == []


def test_malformed_handoff_payload_reports_errors() -> None:
    schema = validator._load_schema(validator.DEFAULT_SCHEMA_PATH)

    none_errors = validator.validate_handoff_record(None, schema)
    list_errors = validator.validate_handoff_record([], schema)

    assert any("read-only worker runtime receipt handoff must be a JSON object" in error for error in none_errors)
    assert any("read-only worker runtime receipt handoff must be a JSON object" in error for error in list_errors)
    assert any("expected object" in error for error in none_errors + list_errors)


def test_sdlc_requirement_and_design_validate_for_runtime_receipt_handoff() -> None:
    requirement_path = Path("examples/sdlc/requirement_runtime_receipt_emission_handoff_20260614.json")
    design_path = Path("examples/sdlc/design_runtime_receipt_emission_handoff_20260614.json")
    requirement = sdlc_validator.load_json_object(requirement_path, "runtime receipt handoff requirement")
    design = sdlc_validator.load_json_object(design_path, "runtime receipt handoff design")

    requirement_errors = sdlc_validator.validate_artifact_record("requirement", requirement)
    design_errors = sdlc_validator.validate_artifact_record("design_decision", design)

    assert requirement_errors == []
    assert design_errors == []
    assert design["requirement_id"] == requirement["requirement_id"]
    assert "schemas/read_only_worker_runtime_receipt_handoff.schema.json" in design["schema_changes"]
    assert "scripts/validate_read_only_worker_runtime_receipt_handoff.py" in design["validator_changes"]
    assert "no live worker dispatch" in requirement["non_goals"]
    assert "runtime runner registration remains denied" in requirement["constraints"]
    assert design["security_model"]["effect_bearing_requires_receipt"] is True
    assert any("run_workspace_governance_checks.py" in command for command in design["test_plan"])
