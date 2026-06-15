"""Purpose: verify SchedulerWorkerRuntimeReceiptHandoff validation.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_scheduler_worker_runtime_receipt_handoff and SDLC validator.
Invariants:
  - Scheduler-to-worker handoff does not grant runtime authority.
  - Temporal scheduler and distributed lease execution receipt refs remain linked.
  - Future worker invocation stays blocked until named evidence exists.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts import validate_scheduler_worker_runtime_receipt_handoff as validator
from scripts import validate_sdlc_artifact as sdlc_validator


def test_scheduler_worker_runtime_receipt_handoff_passes() -> None:
    errors = validator.validate_scheduler_worker_runtime_receipt_handoff()
    handoff = validator.load_json_object(validator.DEFAULT_HANDOFF_PATH, "SchedulerWorkerRuntimeReceiptHandoff")

    assert errors == []
    assert handoff["handoff_version"] == validator.EXPECTED_HANDOFF_VERSION
    assert handoff["scheduler_receipt_ref"] == validator.EXPECTED_SCHEDULER_REF
    assert handoff["distributed_lease_execution_receipt_ref"] == validator.EXPECTED_DISTRIBUTED_LEASE_EXECUTION_REF
    assert handoff["authority_scope"]["runtime_dispatch_allowed"] is False
    assert handoff["authority_scope"]["worker_invocation_allowed"] is False
    assert handoff["admission_guards"]["runtime_receipt_emitter_registered"] is False
    assert handoff["handoff_result"]["worker_invocation_performed"] is False
    assert handoff["handoff_result"]["terminal_closure"] is False
    assert validator.validate_handoff_record(handoff) == []


def test_handoff_rejects_authority_drift() -> None:
    mutated = validator.build_mutated_handoff(
        authority_scope__foundation_handoff_only=False,
        authority_scope__scheduler_dispatch_allowed=True,
        authority_scope__runtime_dispatch_allowed=True,
        authority_scope__worker_invocation_allowed=True,
        authority_scope__scheduler_mutation_allowed=True,
        authority_scope__lease_backend_call_allowed=True,
        authority_scope__adapter_backend_call_allowed=True,
        authority_scope__external_network_allowed=True,
        authority_scope__secret_access_allowed=True,
        authority_scope__filesystem_write_allowed=True,
        authority_scope__connector_authority_allowed=True,
        authority_scope__terminal_closure_allowed=True,
        authority_scope__success_claim_allowed=True,
    )

    errors = validator.validate_handoff_record(mutated)

    assert any("foundation_handoff_only" in error for error in errors)
    assert any("scheduler_dispatch_allowed" in error for error in errors)
    assert any("runtime_dispatch_allowed" in error for error in errors)
    assert any("worker_invocation_allowed" in error for error in errors)
    assert any("scheduler_mutation_allowed" in error for error in errors)
    assert any("lease_backend_call_allowed" in error for error in errors)
    assert any("adapter_backend_call_allowed" in error for error in errors)
    assert any("external_network_allowed" in error for error in errors)
    assert any("secret_access_allowed" in error for error in errors)
    assert any("filesystem_write_allowed" in error for error in errors)
    assert any("connector_authority_allowed" in error for error in errors)
    assert any("terminal_closure_allowed" in error for error in errors)
    assert any("success_claim_allowed" in error for error in errors)


def test_handoff_rejects_top_level_and_contract_drift() -> None:
    mutated = validator.build_mutated_handoff(
        scheduler_receipt_ref="receipt://temporal-scheduler/wrong",
        distributed_lease_execution_receipt_ref="receipt://distributed-lease-execution/wrong",
        worker_mesh_ref="schemas/other_worker_mesh.schema.json",
        worker_failure_receipt_ref="schemas/other_worker_failure.schema.json",
        scheduler_worker_contract__operation_family="runtime_dispatch",
        scheduler_worker_contract__handoff_state="AWAITING_RUNTIME_EVIDENCE",
    )

    errors = validator.validate_handoff_record(mutated)

    assert any("scheduler_receipt_ref" in error for error in errors)
    assert any("distributed_lease_execution_receipt_ref" in error for error in errors)
    assert any("worker_mesh_ref" in error for error in errors)
    assert any("worker_failure_receipt_ref" in error for error in errors)
    assert any("scheduler_worker_contract.operation_family" in error for error in errors)
    assert any("handoff_state must be FOUNDATION_HANDOFF_RECORDED" in error for error in errors)


def test_handoff_rejects_missing_required_refs() -> None:
    mutated = validator.build_mutated_handoff(
        scheduler_worker_contract__required_source_receipt_refs=["schemas/temporal_scheduler_receipt.schema.json"],
        scheduler_worker_contract__required_admission_gate_refs=["gate://temporal-scheduler-leased"],
        scheduler_worker_contract__required_runtime_witness_refs=["witness://scheduler-dispatch/not-registered"],
        scheduler_worker_contract__receipt_schema_refs=["schemas/scheduler_worker_runtime_receipt_handoff.schema.json"],
        scheduler_worker_contract__validation_refs=["scripts/validate_scheduler_worker_runtime_receipt_handoff.py"],
        scheduler_worker_contract__denied_until_refs=["evidence://temporal-scheduler-runtime-receipt"],
        evidence_refs=["schemas/scheduler_worker_runtime_receipt_handoff.schema.json"],
    )

    errors = validator.validate_handoff_record(mutated)

    assert any("required_source_receipt_refs missing required ref" in error for error in errors)
    assert any("required_admission_gate_refs missing required ref" in error for error in errors)
    assert any("required_runtime_witness_refs missing required ref" in error for error in errors)
    assert any("receipt_schema_refs missing required ref" in error for error in errors)
    assert any("validation_refs missing required ref" in error for error in errors)
    assert any("denied_until_refs missing required ref" in error for error in errors)
    assert any("evidence_refs missing required ref" in error for error in errors)


def test_handoff_rejects_admission_and_result_drift() -> None:
    mutated = validator.build_mutated_handoff(
        admission_guards__temporal_scheduler_receipt_required=False,
        admission_guards__distributed_lease_execution_receipt_required=False,
        admission_guards__worker_mesh_receipt_required=False,
        admission_guards__worker_failure_receipt_required_on_error=False,
        admission_guards__uao_effect_admission_required=False,
        admission_guards__phi_gov_dispatch_authorization_required=False,
        admission_guards__effect_reconciliation_required=False,
        admission_guards__scheduler_dispatch_registered=True,
        admission_guards__runtime_dispatch_registered=True,
        admission_guards__worker_invocation_registered=True,
        admission_guards__runtime_receipt_emitter_registered=True,
        admission_guards__runtime_receipt_schema_bound=True,
        admission_guards__terminal_closure_blocked_until_runtime_receipt=False,
        handoff_result__scheduler_dispatch_performed=True,
        handoff_result__runtime_dispatch_performed=True,
        handoff_result__worker_invocation_performed=True,
        handoff_result__lease_backend_call_performed=True,
        handoff_result__adapter_backend_call_performed=True,
        handoff_result__scheduler_mutation_performed=True,
        handoff_result__external_effects_observed=True,
        handoff_result__filesystem_writes_observed=True,
        handoff_result__connector_calls_observed=True,
        handoff_result__terminal_closure=True,
        handoff_result__success_claim_allowed=True,
    )

    errors = validator.validate_handoff_record(mutated)

    assert any("admission_guards.temporal_scheduler_receipt_required" in error for error in errors)
    assert any("admission_guards.distributed_lease_execution_receipt_required" in error for error in errors)
    assert any("admission_guards.scheduler_dispatch_registered" in error for error in errors)
    assert any("admission_guards.runtime_dispatch_registered" in error for error in errors)
    assert any("admission_guards.worker_invocation_registered" in error for error in errors)
    assert any("admission_guards.runtime_receipt_emitter_registered" in error for error in errors)
    assert any("admission_guards.runtime_receipt_schema_bound" in error for error in errors)
    assert any("handoff_result.scheduler_dispatch_performed" in error for error in errors)
    assert any("handoff_result.runtime_dispatch_performed" in error for error in errors)
    assert any("handoff_result.worker_invocation_performed" in error for error in errors)
    assert any("handoff_result.lease_backend_call_performed" in error for error in errors)
    assert any("handoff_result.adapter_backend_call_performed" in error for error in errors)
    assert any("handoff_result.scheduler_mutation_performed" in error for error in errors)
    assert any("handoff_result.terminal_closure" in error for error in errors)


def test_handoff_rejects_receipt_ref_and_count_drift() -> None:
    mutated = validator.build_mutated_handoff(
        receipt_refs__scheduler_worker_runtime_receipt_handoff_schema="schemas/other.schema.json",
        receipt_refs__temporal_scheduler_receipt_schema="schemas/other_temporal.schema.json",
        receipt_refs__distributed_lease_execution_receipt_schema="schemas/other_lease.schema.json",
        receipt_refs__worker_mesh_schema="schemas/other_worker.schema.json",
        contract_summary__source_receipt_ref_count=1,
        contract_summary__admission_gate_ref_count=1,
        contract_summary__runtime_witness_ref_count=1,
        contract_summary__receipt_schema_ref_count=1,
        contract_summary__validation_ref_count=1,
        contract_summary__denied_until_ref_count=1,
        contract_summary__future_worker_obligation_count=1,
        contract_summary__next_required_evidence_count=1,
        contract_summary__receipt_ref_count=7,
        contract_summary__evidence_ref_count=1,
    )

    errors = validator.validate_handoff_record(mutated)

    assert any("receipt_refs.scheduler_worker_runtime_receipt_handoff_schema" in error for error in errors)
    assert any("receipt_refs.temporal_scheduler_receipt_schema" in error for error in errors)
    assert any("receipt_refs.distributed_lease_execution_receipt_schema" in error for error in errors)
    assert any("receipt_refs.worker_mesh_schema" in error for error in errors)
    assert any("contract_summary.source_receipt_ref_count" in error for error in errors)
    assert any("contract_summary.admission_gate_ref_count" in error for error in errors)
    assert any("contract_summary.runtime_witness_ref_count" in error for error in errors)
    assert any("contract_summary.receipt_schema_ref_count" in error for error in errors)
    assert any("contract_summary.validation_ref_count" in error for error in errors)
    assert any("contract_summary.denied_until_ref_count" in error for error in errors)
    assert any("contract_summary.future_worker_obligation_count" in error for error in errors)
    assert any("contract_summary.next_required_evidence_count" in error for error in errors)
    assert any("contract_summary.receipt_ref_count" in error for error in errors)
    assert any("contract_summary.evidence_ref_count" in error for error in errors)


def test_cli_json_accepts_relative_paths(capsys) -> None:
    exit_code = validator.main(
        [
            "--schema",
            "schemas/scheduler_worker_runtime_receipt_handoff.schema.json",
            "--handoff",
            "examples/scheduler_worker_runtime_receipt_handoff.foundation.json",
            "--json",
        ]
    )

    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["status"] == "passed"
    assert Path(payload["schema_path"]).as_posix() == "schemas/scheduler_worker_runtime_receipt_handoff.schema.json"
    assert Path(payload["handoff_path"]).as_posix() == "examples/scheduler_worker_runtime_receipt_handoff.foundation.json"
    assert payload["errors"] == []


def test_malformed_handoff_payload_reports_errors() -> None:
    schema = validator._load_schema(validator.DEFAULT_SCHEMA_PATH)

    none_errors = validator.validate_handoff_record(None, schema)
    list_errors = validator.validate_handoff_record([], schema)

    assert any("scheduler worker runtime receipt handoff must be a JSON object" in error for error in none_errors)
    assert any("scheduler worker runtime receipt handoff must be a JSON object" in error for error in list_errors)
    assert any("expected object" in error for error in none_errors + list_errors)


def test_sdlc_requirement_and_design_validate_for_scheduler_worker_handoff() -> None:
    requirement_path = Path("examples/sdlc/requirement_scheduler_worker_runtime_receipt_handoff_20260615.json")
    design_path = Path("examples/sdlc/design_scheduler_worker_runtime_receipt_handoff_20260615.json")
    requirement = sdlc_validator.load_json_object(requirement_path, "scheduler worker handoff requirement")
    design = sdlc_validator.load_json_object(design_path, "scheduler worker handoff design")

    requirement_errors = sdlc_validator.validate_artifact_record("requirement", requirement)
    design_errors = sdlc_validator.validate_artifact_record("design_decision", design)

    assert requirement_errors == []
    assert design_errors == []
    assert design["requirement_id"] == requirement["requirement_id"]
    assert "schemas/scheduler_worker_runtime_receipt_handoff.schema.json" in design["schema_changes"]
    assert "scripts/validate_scheduler_worker_runtime_receipt_handoff.py" in design["validator_changes"]
    assert "no live worker dispatch" in requirement["non_goals"]
    assert "scheduler mutation and worker invocation flags must remain false" in requirement["constraints"]
    assert design["security_model"]["effect_bearing_requires_receipt"] is True
    assert any("run_workspace_governance_checks.py" in command for command in design["test_plan"])
