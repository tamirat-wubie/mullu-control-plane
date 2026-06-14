"""Purpose: verify ReadOnlyWorkerLeasePreflight validation.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_read_only_worker_lease_preflight and SDLC validator.
Invariants:
  - The read-only worker path requires temporal lease preflight evidence.
  - Runtime dispatch remains denied in Foundation Mode.
  - Fencing token, positive sequence, TrustedClock, worker mesh, and failure
    receipt refs remain mandatory.
  - The SDLC requirement and design artifacts validate.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts import validate_read_only_worker_lease_preflight as validator
from scripts import validate_sdlc_artifact as sdlc_validator


def test_read_only_worker_lease_preflight_passes() -> None:
    errors = validator.validate_preflight()
    preflight = validator.load_json_object(validator.DEFAULT_PREFLIGHT_PATH, "ReadOnlyWorkerLeasePreflight")

    assert errors == []
    assert preflight["preflight_version"] == validator.EXPECTED_PREFLIGHT_VERSION
    assert preflight["selected_worker_path"] == "read_only_repo_inspection"
    assert preflight["authority_scope"]["runtime_dispatch_allowed"] is False
    assert preflight["authority_scope"]["lease_preflight_required"] is True
    assert preflight["dispatch_gate"]["dispatch_admitted"] is False
    assert validator.validate_preflight_record(preflight) == []


def test_preflight_rejects_authority_drift() -> None:
    mutated = validator.build_mutated_preflight(
        authority_scope__runtime_dispatch_allowed=True,
        authority_scope__lease_preflight_required=False,
        authority_scope__external_network_allowed=True,
        authority_scope__secret_access_allowed=True,
        authority_scope__filesystem_write_allowed=True,
        authority_scope__connector_authority_allowed=True,
        authority_scope__terminal_closure_allowed=True,
        authority_scope__raw_output_retention_allowed=True,
    )

    errors = validator.validate_preflight_record(mutated)

    assert any("runtime_dispatch_allowed" in error for error in errors)
    assert any("lease_preflight_required" in error for error in errors)
    assert any("external_network_allowed" in error for error in errors)
    assert any("secret_access_allowed" in error for error in errors)
    assert any("filesystem_write_allowed" in error for error in errors)
    assert any("connector_authority_allowed" in error for error in errors)
    assert any("terminal_closure_allowed" in error for error in errors)
    assert any("raw_output_retention_allowed" in error for error in errors)


def test_preflight_rejects_binding_and_worker_mismatch() -> None:
    mutated = validator.build_mutated_preflight(
        selected_worker_path="read_only_search",
        lease_contract__worker_id="worker_search",
        lease_contract__capability="read_only_search",
        lease_contract__operation_family="web_search",
    )

    errors = validator.validate_preflight_record(mutated)

    assert any("selected_worker_path must be read_only_repo_inspection" in error for error in errors)
    assert any("preflight selected_worker_path must match binding selected_worker_path" in error for error in errors)
    assert any("lease_contract.worker_id" in error for error in errors)
    assert any("lease_contract.capability" in error for error in errors)
    assert any("lease_contract.operation_family" in error for error in errors)


def test_preflight_rejects_missing_temporal_controls() -> None:
    mutated = validator.build_mutated_preflight(
        lease_contract__runtime_clock_ref="wall-clock",
        lease_contract__temporal_lease_window_schema_ref="schemas/other.schema.json",
        lease_contract__fencing_token_required=False,
        lease_contract__positive_sequence_required=False,
    )

    errors = validator.validate_preflight_record(mutated)

    assert any("runtime_clock_ref must bind TrustedClock" in error for error in errors)
    assert any("temporal_lease_window_schema_ref" in error for error in errors)
    assert any("fencing_token_required" in error for error in errors)
    assert any("positive_sequence_required" in error for error in errors)
    assert mutated["lease_contract"]["runtime_clock_ref"] == "wall-clock"


def test_preflight_rejects_nonlocal_resource_patterns() -> None:
    mutated = validator.build_mutated_preflight(
        lease_contract__allowed_resource_patterns=["network://external/*"]
    )
    mutated["contract_summary"]["allowed_resource_pattern_count"] = 1

    errors = validator.validate_preflight_record(mutated)

    assert any("allowed_resource_patterns must stay under repo://local/" in error for error in errors)
    assert mutated["lease_contract"]["allowed_resource_patterns"] == ["network://external/*"]
    assert mutated["authority_scope"]["external_network_allowed"] is False
    assert mutated["contract_summary"]["allowed_resource_pattern_count"] == 1


def test_preflight_rejects_dispatch_gate_drift() -> None:
    mutated = validator.build_mutated_preflight(
        dispatch_gate__dispatch_admitted=True,
        dispatch_gate__foundation_mode=False,
        dispatch_gate__blocked_without_lease_receipt=False,
        dispatch_gate__missing_lease_reason="ignored",
        dispatch_gate__worker_failure_receipt_required_on_failure=False,
        dispatch_gate__terminal_closure_required=False,
        dispatch_gate__required_temporal_statuses=["lease_expiring"],
    )

    errors = validator.validate_preflight_record(mutated)

    assert any("dispatch_gate.dispatch_admitted must be false" in error for error in errors)
    assert any("dispatch_gate.foundation_mode must be true" in error for error in errors)
    assert any("blocked_without_lease_receipt" in error for error in errors)
    assert any("missing_lease_reason" in error for error in errors)
    assert any("worker_failure_receipt_required_on_failure" in error for error in errors)
    assert any("terminal_closure_required" in error for error in errors)
    assert any("required_temporal_statuses must include lease_active" in error for error in errors)


def test_preflight_rejects_receipt_ref_drift() -> None:
    mutated = validator.build_mutated_preflight(
        receipt_refs__temporal_lease_window_receipt_schema="schemas/other.schema.json",
        receipt_refs__worker_failure_receipt_schema="schemas/other_failure.schema.json",
    )

    errors = validator.validate_preflight_record(mutated)

    assert any("receipt_refs.temporal_lease_window_receipt_schema" in error for error in errors)
    assert any("receipt_refs.worker_failure_receipt_schema" in error for error in errors)
    assert mutated["receipt_refs"]["temporal_lease_window_receipt_schema"] == "schemas/other.schema.json"
    assert mutated["receipt_refs"]["worker_failure_receipt_schema"] == "schemas/other_failure.schema.json"


def test_preflight_rejects_count_drift_and_missing_evidence() -> None:
    mutated = validator.build_mutated_preflight(
        contract_summary__allowed_resource_pattern_count=1,
        contract_summary__required_temporal_status_count=2,
        contract_summary__receipt_ref_count=4,
        evidence_refs=["schemas/read_only_worker_lease_preflight.schema.json"],
    )

    errors = validator.validate_preflight_record(mutated)

    assert any("contract_summary.allowed_resource_pattern_count" in error for error in errors)
    assert any("contract_summary.required_temporal_status_count" in error for error in errors)
    assert any("contract_summary.receipt_ref_count" in error for error in errors)
    assert any("contract_summary.evidence_ref_count" in error for error in errors)
    assert any("evidence_refs missing required ref" in error for error in errors)


def test_cli_json_accepts_relative_paths(capsys) -> None:
    exit_code = validator.main(
        [
            "--schema",
            "schemas/read_only_worker_lease_preflight.schema.json",
            "--preflight",
            "examples/read_only_worker_lease_preflight.foundation.json",
            "--binding",
            "examples/read_only_worker_binding.foundation.json",
            "--json",
        ]
    )

    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["status"] == "passed"
    assert Path(payload["schema_path"]).as_posix() == "schemas/read_only_worker_lease_preflight.schema.json"
    assert Path(payload["preflight_path"]).as_posix() == "examples/read_only_worker_lease_preflight.foundation.json"
    assert Path(payload["binding_path"]).as_posix() == "examples/read_only_worker_binding.foundation.json"
    assert payload["errors"] == []


def test_malformed_preflight_payload_reports_errors() -> None:
    schema = validator._load_schema(validator.DEFAULT_SCHEMA_PATH)

    none_errors = validator.validate_preflight_record(None, schema)
    list_errors = validator.validate_preflight_record([], schema)

    assert any("read-only worker lease preflight must be a JSON object" in error for error in none_errors)
    assert any("read-only worker lease preflight must be a JSON object" in error for error in list_errors)
    assert any("expected object" in error for error in none_errors + list_errors)


def test_sdlc_requirement_and_design_validate_for_read_only_worker_lease_preflight() -> None:
    requirement_path = Path("examples/sdlc/requirement_read_only_worker_lease_preflight_20260614.json")
    design_path = Path("examples/sdlc/design_read_only_worker_lease_preflight_20260614.json")
    requirement = sdlc_validator.load_json_object(requirement_path, "ReadOnlyWorkerLeasePreflight requirement")
    design = sdlc_validator.load_json_object(design_path, "ReadOnlyWorkerLeasePreflight design")

    requirement_errors = sdlc_validator.validate_artifact_record("requirement", requirement)
    design_errors = sdlc_validator.validate_artifact_record("design_decision", design)

    assert requirement_errors == []
    assert design_errors == []
    assert design["requirement_id"] == requirement["requirement_id"]
    assert "schemas/read_only_worker_lease_preflight.schema.json" in design["schema_changes"]
    assert "scripts/validate_read_only_worker_lease_preflight.py" in design["validator_changes"]
    assert "no live worker dispatch" in requirement["non_goals"]
    assert "ReadOnlyWorkerLeasePreflight validates against the public JSON schema and Foundation Mode example" in requirement["success_criteria"]
    assert design["security_model"]["effect_bearing_requires_receipt"] is True
    assert any("run_workspace_governance_checks.py" in command for command in design["test_plan"])
