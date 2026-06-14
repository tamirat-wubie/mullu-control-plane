"""Purpose: verify ReadOnlyWorkerRehearsalReceipt validation.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_read_only_worker_rehearsal_receipt and SDLC validator.
Invariants:
  - Local rehearsal records evidence without runtime dispatch authority.
  - Network, secrets, filesystem writes, connector calls, raw output retention,
    and terminal closure remain denied.
  - The SDLC requirement and design artifacts validate.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts import validate_read_only_worker_rehearsal_receipt as validator
from scripts import validate_sdlc_artifact as sdlc_validator


def test_read_only_worker_rehearsal_receipt_passes() -> None:
    errors = validator.validate_rehearsal_receipt()
    receipt = validator.load_json_object(validator.DEFAULT_RECEIPT_PATH, "ReadOnlyWorkerRehearsalReceipt")

    assert errors == []
    assert receipt["receipt_version"] == validator.EXPECTED_RECEIPT_VERSION
    assert receipt["selected_worker_path"] == "read_only_repo_inspection"
    assert receipt["authority_scope"]["local_rehearsal_only"] is True
    assert receipt["authority_scope"]["runtime_dispatch_allowed"] is False
    assert receipt["rehearsal_contract"]["dispatch_admitted"] is False
    assert receipt["rehearsal_result"]["terminal_closure"] is False
    assert validator.validate_rehearsal_record(receipt) == []


def test_rehearsal_rejects_authority_drift() -> None:
    mutated = validator.build_mutated_rehearsal(
        authority_scope__local_rehearsal_only=False,
        authority_scope__runtime_dispatch_allowed=True,
        authority_scope__lease_preflight_required=False,
        authority_scope__external_network_allowed=True,
        authority_scope__secret_access_allowed=True,
        authority_scope__filesystem_write_allowed=True,
        authority_scope__connector_authority_allowed=True,
        authority_scope__terminal_closure_allowed=True,
        authority_scope__raw_output_retention_allowed=True,
    )

    errors = validator.validate_rehearsal_record(mutated)

    assert any("local_rehearsal_only" in error for error in errors)
    assert any("runtime_dispatch_allowed" in error for error in errors)
    assert any("lease_preflight_required" in error for error in errors)
    assert any("external_network_allowed" in error for error in errors)
    assert any("secret_access_allowed" in error for error in errors)
    assert any("filesystem_write_allowed" in error for error in errors)
    assert any("connector_authority_allowed" in error for error in errors)
    assert any("terminal_closure_allowed" in error for error in errors)
    assert any("raw_output_retention_allowed" in error for error in errors)


def test_rehearsal_rejects_worker_and_preflight_mismatch() -> None:
    mutated = validator.build_mutated_rehearsal(
        selected_worker_path="read_only_search",
        rehearsal_contract__worker_id="worker_search",
        rehearsal_contract__capability="read_only_search",
        rehearsal_contract__operation_family="web_search",
    )

    errors = validator.validate_rehearsal_record(mutated)

    assert any("selected_worker_path must be read_only_repo_inspection" in error for error in errors)
    assert any("match binding selected_worker_path" in error for error in errors)
    assert any("match preflight selected_worker_path" in error for error in errors)
    assert any("rehearsal_contract.worker_id" in error for error in errors)
    assert any("rehearsal_contract.capability" in error for error in errors)
    assert any("rehearsal_contract.operation_family" in error for error in errors)


def test_rehearsal_rejects_dispatch_and_mode_drift() -> None:
    mutated = validator.build_mutated_rehearsal(
        rehearsal_contract__rehearsal_mode="LIVE_RUN",
        rehearsal_contract__dispatch_admitted=True,
        rehearsal_contract__filesystem_snapshot_required=False,
    )

    errors = validator.validate_rehearsal_record(mutated)

    assert any("rehearsal_mode must be LOCAL_DRY_RUN" in error for error in errors)
    assert any("dispatch_admitted must be false" in error for error in errors)
    assert any("filesystem_snapshot_required must be true" in error for error in errors)
    assert mutated["rehearsal_contract"]["rehearsal_mode"] == "LIVE_RUN"


def test_rehearsal_rejects_nonlocal_resource_and_evidence_refs() -> None:
    mutated = validator.build_mutated_rehearsal(
        rehearsal_contract__allowed_resource_refs=["network://external/*"],
        rehearsal_result__inspected_resource_refs=["repo://other/docs"],
        rehearsal_result__observed_evidence_refs=["evidence://external/path"],
    )
    mutated["contract_summary"]["allowed_resource_ref_count"] = 1
    mutated["contract_summary"]["inspected_resource_ref_count"] = 1
    mutated["contract_summary"]["observed_evidence_ref_count"] = 1

    errors = validator.validate_rehearsal_record(mutated)

    assert any("allowed_resource_refs must stay under repo://local/" in error for error in errors)
    assert any("inspected_resource_refs must stay under repo://local/" in error for error in errors)
    assert any("observed_evidence_refs must be local path-hash evidence" in error for error in errors)
    assert mutated["rehearsal_contract"]["allowed_resource_refs"] == ["network://external/*"]


def test_rehearsal_rejects_missing_forbidden_effect_and_preflight_refs() -> None:
    mutated = validator.build_mutated_rehearsal(
        rehearsal_contract__forbidden_effect_refs=["network://*"],
        rehearsal_contract__required_preflight_refs=["examples/read_only_worker_binding.foundation.json"],
    )
    mutated["contract_summary"]["forbidden_effect_ref_count"] = 1
    mutated["contract_summary"]["required_preflight_ref_count"] = 1

    errors = validator.validate_rehearsal_record(mutated)

    assert any("forbidden_effect_refs missing required ref: connector-call://*" in error for error in errors)
    assert any("forbidden_effect_refs missing required ref: filesystem-write://*" in error for error in errors)
    assert any("forbidden_effect_refs missing required ref: terminal-closure://*" in error for error in errors)
    assert any("required_preflight_refs missing required ref" in error for error in errors)


def test_rehearsal_rejects_effect_and_success_claim_drift() -> None:
    mutated = validator.build_mutated_rehearsal(
        rehearsal_result__raw_output_included=True,
        rehearsal_result__raw_secret_material_included=True,
        rehearsal_result__external_effects_observed=True,
        rehearsal_result__filesystem_writes_observed=True,
        rehearsal_result__connector_calls_observed=True,
        rehearsal_result__terminal_closure=True,
        rehearsal_result__success_claim_allowed=True,
    )

    errors = validator.validate_rehearsal_record(mutated)

    assert any("raw_output_included must be false" in error for error in errors)
    assert any("raw_secret_material_included must be false" in error for error in errors)
    assert any("external_effects_observed must be false" in error for error in errors)
    assert any("filesystem_writes_observed must be false" in error for error in errors)
    assert any("connector_calls_observed must be false" in error for error in errors)
    assert any("terminal_closure must be false" in error for error in errors)
    assert any("success_claim_allowed must be false" in error for error in errors)


def test_rehearsal_rejects_receipt_ref_drift() -> None:
    mutated = validator.build_mutated_rehearsal(
        receipt_refs__read_only_worker_rehearsal_receipt_schema="schemas/other.schema.json",
        receipt_refs__worker_failure_receipt_schema="schemas/other_failure.schema.json",
    )

    errors = validator.validate_rehearsal_record(mutated)

    assert any("receipt_refs.read_only_worker_rehearsal_receipt_schema" in error for error in errors)
    assert any("receipt_refs.worker_failure_receipt_schema" in error for error in errors)
    assert mutated["receipt_refs"]["read_only_worker_rehearsal_receipt_schema"] == "schemas/other.schema.json"
    assert mutated["receipt_refs"]["worker_failure_receipt_schema"] == "schemas/other_failure.schema.json"


def test_rehearsal_rejects_count_drift_and_missing_evidence() -> None:
    mutated = validator.build_mutated_rehearsal(
        contract_summary__allowed_resource_ref_count=1,
        contract_summary__forbidden_effect_ref_count=1,
        contract_summary__required_preflight_ref_count=1,
        contract_summary__verification_ref_count=1,
        contract_summary__inspected_resource_ref_count=1,
        contract_summary__observed_evidence_ref_count=1,
        contract_summary__receipt_ref_count=5,
        evidence_refs=["schemas/read_only_worker_rehearsal_receipt.schema.json"],
    )

    errors = validator.validate_rehearsal_record(mutated)

    assert any("contract_summary.allowed_resource_ref_count" in error for error in errors)
    assert any("contract_summary.forbidden_effect_ref_count" in error for error in errors)
    assert any("contract_summary.required_preflight_ref_count" in error for error in errors)
    assert any("contract_summary.verification_ref_count" in error for error in errors)
    assert any("contract_summary.inspected_resource_ref_count" in error for error in errors)
    assert any("contract_summary.observed_evidence_ref_count" in error for error in errors)
    assert any("contract_summary.receipt_ref_count" in error for error in errors)
    assert any("contract_summary.evidence_ref_count" in error for error in errors)
    assert any("evidence_refs missing required ref" in error for error in errors)


def test_cli_json_accepts_relative_paths(capsys) -> None:
    exit_code = validator.main(
        [
            "--schema",
            "schemas/read_only_worker_rehearsal_receipt.schema.json",
            "--receipt",
            "examples/read_only_worker_rehearsal_receipt.foundation.json",
            "--binding",
            "examples/read_only_worker_binding.foundation.json",
            "--preflight",
            "examples/read_only_worker_lease_preflight.foundation.json",
            "--json",
        ]
    )

    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["status"] == "passed"
    assert Path(payload["schema_path"]).as_posix() == "schemas/read_only_worker_rehearsal_receipt.schema.json"
    assert Path(payload["receipt_path"]).as_posix() == "examples/read_only_worker_rehearsal_receipt.foundation.json"
    assert Path(payload["binding_path"]).as_posix() == "examples/read_only_worker_binding.foundation.json"
    assert Path(payload["preflight_path"]).as_posix() == "examples/read_only_worker_lease_preflight.foundation.json"
    assert payload["errors"] == []


def test_malformed_rehearsal_payload_reports_errors() -> None:
    schema = validator._load_schema(validator.DEFAULT_SCHEMA_PATH)

    none_errors = validator.validate_rehearsal_record(None, schema)
    list_errors = validator.validate_rehearsal_record([], schema)

    assert any("read-only worker rehearsal receipt must be a JSON object" in error for error in none_errors)
    assert any("read-only worker rehearsal receipt must be a JSON object" in error for error in list_errors)
    assert any("expected object" in error for error in none_errors + list_errors)


def test_sdlc_requirement_and_design_validate_for_read_only_worker_rehearsal_receipt() -> None:
    requirement_path = Path("examples/sdlc/requirement_read_only_worker_rehearsal_receipt_20260614.json")
    design_path = Path("examples/sdlc/design_read_only_worker_rehearsal_receipt_20260614.json")
    requirement = sdlc_validator.load_json_object(requirement_path, "ReadOnlyWorkerRehearsalReceipt requirement")
    design = sdlc_validator.load_json_object(design_path, "ReadOnlyWorkerRehearsalReceipt design")

    requirement_errors = sdlc_validator.validate_artifact_record("requirement", requirement)
    design_errors = sdlc_validator.validate_artifact_record("design_decision", design)

    assert requirement_errors == []
    assert design_errors == []
    assert design["requirement_id"] == requirement["requirement_id"]
    assert "schemas/read_only_worker_rehearsal_receipt.schema.json" in design["schema_changes"]
    assert "scripts/validate_read_only_worker_rehearsal_receipt.py" in design["validator_changes"]
    assert "no live worker dispatch" in requirement["non_goals"]
    assert "ReadOnlyWorkerRehearsalReceipt validates against the public JSON schema and Foundation Mode example" in requirement["success_criteria"]
    assert design["security_model"]["effect_bearing_requires_receipt"] is True
    assert any("run_workspace_governance_checks.py" in command for command in design["test_plan"])
