"""Purpose: verify ReadOnlyWorkerRuntimeRunnerRegistrationWitness validation.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_read_only_worker_runtime_runner_registration_witness and SDLC validator.
Invariants:
  - Live runner registration witness is defined but no runner is registered.
  - Runner registry writes, dispatch endpoint registration, runtime dispatch,
    and runtime receipt emission remain unperformed.
  - Future dispatch remains blocked until operator approval and live evidence exist.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts import validate_read_only_worker_runtime_runner_registration_witness as validator
from scripts import validate_sdlc_artifact as sdlc_validator


def test_runner_registration_witness_passes() -> None:
    errors = validator.validate_runner_registration_witness()
    receipt = validator.load_json_object(
        validator.DEFAULT_RECEIPT_PATH,
        "ReadOnlyWorkerRuntimeRunnerRegistrationWitness",
    )

    assert errors == []
    assert receipt["receipt_version"] == validator.EXPECTED_RECEIPT_VERSION
    assert receipt["selected_worker_path"] == "read_only_repo_inspection"
    assert receipt["authority_scope"]["live_runner_registration_witness_defined"] is True
    assert receipt["authority_scope"]["runtime_runner_registration_performed"] is False
    assert receipt["authority_scope"]["runner_registry_write_performed"] is False
    assert receipt["authority_scope"]["runtime_dispatch_allowed"] is False
    assert receipt["runner_registration_witness_contract"]["witness_mode"] == "LIVE_RUNNER_REGISTRATION_WITNESS_ONLY"
    assert receipt["registration_evaluation"]["upstream_store_write_path_witness_validated"] is True
    assert receipt["admission_decision"]["runtime_dispatch_admitted"] is False
    assert validator.validate_runner_registration_witness_record(receipt) == []


def test_runner_registration_witness_rejects_authority_drift() -> None:
    mutated = validator.build_mutated_runner_registration_witness(
        authority_scope__foundation_witness_only=False,
        authority_scope__live_runner_registration_witness_defined=False,
        authority_scope__runtime_runner_registration_performed=True,
        authority_scope__runner_registry_write_performed=True,
        authority_scope__dispatch_endpoint_registration_performed=True,
        authority_scope__runtime_receipt_emitter_registration_performed=True,
        authority_scope__runtime_receipt_schema_binding_performed=True,
        authority_scope__receipt_store_write_path_registered=True,
        authority_scope__runtime_dispatch_allowed=True,
        authority_scope__runtime_receipt_emission_allowed=True,
        authority_scope__external_network_allowed=True,
        authority_scope__secret_access_allowed=True,
        authority_scope__filesystem_write_allowed=True,
        authority_scope__connector_authority_allowed=True,
        authority_scope__terminal_closure_allowed=True,
        authority_scope__success_claim_allowed=True,
    )

    errors = validator.validate_runner_registration_witness_record(mutated)

    assert any("foundation_witness_only" in error for error in errors)
    assert any("live_runner_registration_witness_defined" in error for error in errors)
    assert any("runtime_runner_registration_performed" in error for error in errors)
    assert any("runner_registry_write_performed" in error for error in errors)
    assert any("dispatch_endpoint_registration_performed" in error for error in errors)
    assert any("runtime_receipt_emitter_registration_performed" in error for error in errors)
    assert any("runtime_receipt_schema_binding_performed" in error for error in errors)
    assert any("receipt_store_write_path_registered" in error for error in errors)
    assert any("runtime_dispatch_allowed" in error for error in errors)
    assert any("runtime_receipt_emission_allowed" in error for error in errors)
    assert any("external_network_allowed" in error for error in errors)
    assert any("secret_access_allowed" in error for error in errors)
    assert any("filesystem_write_allowed" in error for error in errors)
    assert any("connector_authority_allowed" in error for error in errors)
    assert any("terminal_closure_allowed" in error for error in errors)
    assert any("success_claim_allowed" in error for error in errors)


def test_runner_registration_witness_rejects_contract_drift() -> None:
    mutated = validator.build_mutated_runner_registration_witness(
        selected_worker_path="read_only_search",
        runner_registration_witness_contract__worker_id="worker_search",
        runner_registration_witness_contract__capability="read_only_search",
        runner_registration_witness_contract__operation_family="web_search",
        runner_registration_witness_contract__witness_mode="LIVE_RUNNER_REGISTRATION",
        runner_registration_witness_contract__runtime_receipt_kind="worker_mesh_dispatch_receipt",
        runner_registration_witness_contract__source_runner_binding_witness_ref="examples/other.json",
        runner_registration_witness_contract__source_store_write_path_witness_ref="examples/other-store.json",
        runner_registration_witness_contract__target_runner_registration_ref="runtime://runner/live",
        runner_registration_witness_contract__runner_profile="WRITE_ENABLED_RUNNER",
    )

    errors = validator.validate_runner_registration_witness_record(mutated)

    assert any("selected_worker_path must be read_only_repo_inspection" in error for error in errors)
    assert any("match runner binding witness" in error for error in errors)
    assert any("match receipt-store write-path witness" in error for error in errors)
    assert any("runner_registration_witness_contract.worker_id" in error for error in errors)
    assert any("runner_registration_witness_contract.capability" in error for error in errors)
    assert any("runner_registration_witness_contract.operation_family" in error for error in errors)
    assert any("runner_registration_witness_contract.witness_mode" in error for error in errors)
    assert any("runner_registration_witness_contract.runtime_receipt_kind" in error for error in errors)
    assert any("source_runner_binding_witness_ref" in error for error in errors)
    assert any("source_store_write_path_witness_ref" in error for error in errors)
    assert any("target_runner_registration_ref" in error for error in errors)
    assert any("runner_profile" in error for error in errors)


def test_runner_registration_witness_rejects_missing_required_refs() -> None:
    mutated = validator.build_mutated_runner_registration_witness(
        runner_registration_witness_contract__required_source_receipt_refs=[
            "examples/read_only_worker_runtime_runner_binding_witness.foundation.json"
        ],
        runner_registration_witness_contract__required_registration_input_refs=[
            "evidence://operator-approval/live-runner-registration"
        ],
        runner_registration_witness_contract__validation_refs=[
            "scripts/validate_read_only_worker_runtime_runner_registration_witness.py"
        ],
        admission_decision__remaining_denied_until_refs=[
            "evidence://operator-approval/live-runner-registration"
        ],
        admission_decision__blocked_reason_refs=[
            "blocked://runtime-runner/not-registered"
        ],
        evidence_refs=["schemas/read_only_worker_runtime_runner_registration_witness.schema.json"],
    )

    errors = validator.validate_runner_registration_witness_record(mutated)

    assert any("required_source_receipt_refs missing required ref" in error for error in errors)
    assert any("required_registration_input_refs missing required ref" in error for error in errors)
    assert any("validation_refs missing required ref" in error for error in errors)
    assert any("remaining_denied_until_refs missing required ref" in error for error in errors)
    assert any("blocked_reason_refs missing required ref" in error for error in errors)
    assert any("evidence_refs missing required ref" in error for error in errors)


def test_runner_registration_witness_rejects_evaluation_and_admission_drift() -> None:
    mutated = validator.build_mutated_runner_registration_witness(
        registration_evaluation__upstream_runner_binding_witness_validated=False,
        registration_evaluation__upstream_store_write_path_witness_validated=False,
        registration_evaluation__source_registration_obligations_preserved=False,
        registration_evaluation__tenant_actor_boundary_required=False,
        registration_evaluation__runner_identity_digest_required=False,
        registration_evaluation__capability_scope_required=False,
        registration_evaluation__temporal_lease_required_before_dispatch=False,
        registration_evaluation__uao_admission_required_before_dispatch=False,
        registration_evaluation__phi_gov_authorization_required_before_dispatch=False,
        registration_evaluation__worker_failure_receipt_required_on_error=False,
        registration_evaluation__effect_reconciliation_required=False,
        registration_evaluation__mfidel_atomicity_preserved=False,
        registration_evaluation__runtime_runner_registration_performed=True,
        registration_evaluation__runner_registry_write_performed=True,
        registration_evaluation__dispatch_endpoint_registration_performed=True,
        registration_evaluation__runtime_dispatch_allowed=True,
        registration_evaluation__runtime_receipt_emitted=True,
        admission_decision__decision="LIVE_RUNTIME_RUNNER_REGISTRATION_ADMITTED",
        admission_decision__runner_registration_witness_defined=False,
        admission_decision__runtime_runner_registered=True,
        admission_decision__dispatch_endpoint_registered=True,
        admission_decision__runtime_dispatch_admitted=True,
        admission_decision__runtime_receipt_emission_admitted=True,
        admission_decision__terminal_closure_allowed=True,
    )

    errors = validator.validate_runner_registration_witness_record(mutated)

    assert any("registration_evaluation.upstream_runner_binding_witness_validated" in error for error in errors)
    assert any("registration_evaluation.upstream_store_write_path_witness_validated" in error for error in errors)
    assert any("registration_evaluation.runner_identity_digest_required" in error for error in errors)
    assert any("registration_evaluation.runtime_runner_registration_performed" in error for error in errors)
    assert any("registration_evaluation.runner_registry_write_performed" in error for error in errors)
    assert any("registration_evaluation.runtime_dispatch_allowed" in error for error in errors)
    assert any("admission_decision.decision" in error for error in errors)
    assert any("admission_decision.runner_registration_witness_defined" in error for error in errors)
    assert any("admission_decision.runtime_runner_registered" in error for error in errors)
    assert any("admission_decision.runtime_dispatch_admitted" in error for error in errors)
    assert any("admission_decision.terminal_closure_allowed" in error for error in errors)


def test_runner_registration_witness_rejects_receipt_ref_and_count_drift() -> None:
    mutated = validator.build_mutated_runner_registration_witness(
        receipt_refs__read_only_worker_runtime_runner_registration_witness_schema="schemas/other.schema.json",
        contract_summary__source_receipt_ref_count=1,
        contract_summary__registration_input_ref_count=1,
        contract_summary__registration_obligation_count=1,
        contract_summary__validation_ref_count=1,
        contract_summary__registration_true_check_count=1,
        contract_summary__registration_denied_check_count=1,
        contract_summary__remaining_denied_until_ref_count=1,
        contract_summary__blocked_reason_ref_count=1,
        contract_summary__receipt_ref_count=13,
        contract_summary__evidence_ref_count=1,
    )

    errors = validator.validate_runner_registration_witness_record(mutated)

    assert any("receipt_refs.read_only_worker_runtime_runner_registration_witness_schema" in error for error in errors)
    assert any("contract_summary.source_receipt_ref_count" in error for error in errors)
    assert any("contract_summary.registration_input_ref_count" in error for error in errors)
    assert any("contract_summary.registration_obligation_count" in error for error in errors)
    assert any("contract_summary.validation_ref_count" in error for error in errors)
    assert any("contract_summary.registration_true_check_count" in error for error in errors)
    assert any("contract_summary.registration_denied_check_count" in error for error in errors)
    assert any("contract_summary.receipt_ref_count" in error for error in errors)
    assert any("contract_summary.evidence_ref_count" in error for error in errors)


def test_cli_json_accepts_relative_paths(capsys) -> None:
    exit_code = validator.main(
        [
            "--schema",
            "schemas/read_only_worker_runtime_runner_registration_witness.schema.json",
            "--receipt",
            "examples/read_only_worker_runtime_runner_registration_witness.foundation.json",
            "--store-write-path-witness",
            "examples/read_only_worker_runtime_receipt_store_write_path_witness.foundation.json",
            "--runner-binding-witness",
            "examples/read_only_worker_runtime_runner_binding_witness.foundation.json",
            "--json",
        ]
    )

    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["status"] == "passed"
    assert Path(payload["schema_path"]).as_posix() == "schemas/read_only_worker_runtime_runner_registration_witness.schema.json"
    assert Path(payload["receipt_path"]).as_posix() == "examples/read_only_worker_runtime_runner_registration_witness.foundation.json"
    assert Path(payload["store_write_path_witness_path"]).as_posix() == (
        "examples/read_only_worker_runtime_receipt_store_write_path_witness.foundation.json"
    )
    assert Path(payload["runner_binding_witness_path"]).as_posix() == (
        "examples/read_only_worker_runtime_runner_binding_witness.foundation.json"
    )
    assert payload["errors"] == []


def test_malformed_runner_registration_witness_payload_reports_errors() -> None:
    schema = validator._load_schema(validator.DEFAULT_SCHEMA_PATH)

    none_errors = validator.validate_runner_registration_witness_record(None, schema)
    list_errors = validator.validate_runner_registration_witness_record([], schema)

    assert any("read-only worker runtime runner registration witness must be a JSON object" in error for error in none_errors)
    assert any("read-only worker runtime runner registration witness must be a JSON object" in error for error in list_errors)
    assert any("expected object" in error for error in none_errors + list_errors)


def test_sdlc_requirement_and_design_validate_for_runner_registration_witness() -> None:
    requirement_path = Path("examples/sdlc/requirement_runtime_runner_registration_witness_20260616.json")
    design_path = Path("examples/sdlc/design_runtime_runner_registration_witness_20260616.json")
    requirement = sdlc_validator.load_json_object(requirement_path, "runner registration witness requirement")
    design = sdlc_validator.load_json_object(design_path, "runner registration witness design")

    requirement_errors = sdlc_validator.validate_artifact_record("requirement", requirement)
    design_errors = sdlc_validator.validate_artifact_record("design_decision", design)

    assert requirement_errors == []
    assert design_errors == []
    assert design["requirement_id"] == requirement["requirement_id"]
    assert "schemas/read_only_worker_runtime_runner_registration_witness.schema.json" in design["schema_changes"]
    assert "scripts/validate_read_only_worker_runtime_runner_registration_witness.py" in design["validator_changes"]
    assert "no live worker dispatch" in requirement["non_goals"]
    assert "runtime runner registration remains unperformed" in requirement["constraints"]
    assert design["security_model"]["effect_bearing_requires_receipt"] is True
    assert any("run_workspace_governance_checks.py" in command for command in design["test_plan"])
