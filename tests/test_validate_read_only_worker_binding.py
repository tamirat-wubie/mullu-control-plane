"""Purpose: verify ReadOnlyWorkerBinding validation.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_read_only_worker_binding and SDLC validator.
Invariants:
  - The first worker path is local read-only repo inspection.
  - Runtime dispatch, network, secrets, writes, connector authority, raw output,
    and terminal closure remain denied.
  - WorkerFailureReceipt is mandatory before runtime admission.
  - The SDLC requirement and design artifacts validate.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts import validate_read_only_worker_binding as validator
from scripts import validate_sdlc_artifact as sdlc_validator


def test_read_only_worker_binding_passes() -> None:
    errors = validator.validate_binding()
    binding = validator.load_json_object(validator.DEFAULT_BINDING_PATH, "ReadOnlyWorkerBinding")

    assert errors == []
    assert binding["binding_version"] == validator.EXPECTED_BINDING_VERSION
    assert binding["selected_worker_path"] == "read_only_repo_inspection"
    assert binding["authority_scope"]["runtime_dispatch_allowed"] is False
    assert "schemas/worker_failure_receipt.schema.json" in binding["worker_contract"]["receipt_schema_refs"]
    assert validator.validate_binding_record(binding) == []


def test_binding_rejects_authority_drift() -> None:
    mutated = validator.build_mutated_binding(
        authority_scope__runtime_dispatch_allowed=True,
        authority_scope__external_network_allowed=True,
        authority_scope__secret_access_allowed=True,
        authority_scope__filesystem_write_allowed=True,
        authority_scope__connector_authority_allowed=True,
        authority_scope__terminal_closure_allowed=True,
        authority_scope__raw_output_retention_allowed=True,
    )

    errors = validator.validate_binding_record(mutated)

    assert any("runtime_dispatch_allowed" in error for error in errors)
    assert any("external_network_allowed" in error for error in errors)
    assert any("secret_access_allowed" in error for error in errors)
    assert any("filesystem_write_allowed" in error for error in errors)
    assert any("connector_authority_allowed" in error for error in errors)
    assert any("terminal_closure_allowed" in error for error in errors)
    assert any("raw_output_retention_allowed" in error for error in errors)


def test_binding_rejects_wrong_worker_path() -> None:
    mutated = validator.build_mutated_binding(
        selected_worker_path="read_only_web_search",
        worker_contract__worker_id="worker_external_search",
        worker_contract__capability="read_only_search",
        worker_contract__operation_family="web_search",
    )

    errors = validator.validate_binding_record(mutated)

    assert any("selected_worker_path must be read_only_repo_inspection" in error for error in errors)
    assert any("worker_contract.worker_id" in error for error in errors)
    assert any("worker_contract.capability" in error for error in errors)
    assert any("worker_contract.operation_family" in error for error in errors)


def test_binding_rejects_network_allowlist() -> None:
    mutated = validator.build_mutated_binding(worker_contract__network_allowlist=["https://example.invalid"])
    mutated["contract_summary"]["network_allowlist_count"] = 1

    errors = validator.validate_binding_record(mutated)

    assert any("network_allowlist" in error for error in errors)
    assert mutated["worker_contract"]["network_allowlist"] == ["https://example.invalid"]
    assert mutated["contract_summary"]["network_allowlist_count"] == 1
    assert mutated["authority_scope"]["external_network_allowed"] is False


def test_binding_rejects_missing_receipt_schema_refs() -> None:
    mutated = validator.build_mutated_binding(worker_contract__receipt_schema_refs=["schemas/worker_mesh.schema.json"])
    mutated["contract_summary"]["receipt_schema_count"] = 1

    errors = validator.validate_binding_record(mutated)

    assert any("receipt_schema_refs missing required ref: schemas/worker_failure_receipt.schema.json" in error for error in errors)
    assert "schemas/worker_mesh.schema.json" in mutated["worker_contract"]["receipt_schema_refs"]
    assert "schemas/worker_failure_receipt.schema.json" not in mutated["worker_contract"]["receipt_schema_refs"]
    assert mutated["contract_summary"]["receipt_schema_count"] == 1


def test_binding_rejects_forbidden_output_as_allowed() -> None:
    mutated = validator.build_mutated_binding(
        worker_contract__allowed_output_refs=[
            "receipt://worker-dispatch/*",
            "filesystem-write://tmp/path"
        ]
    )
    mutated["contract_summary"]["allowed_output_count"] = 2

    errors = validator.validate_binding_record(mutated)

    assert any("allowed_output_refs contains forbidden effect ref" in error for error in errors)
    assert mutated["worker_contract"]["allowed_output_refs"][1] == "filesystem-write://tmp/path"
    assert "filesystem-write://*" in mutated["worker_contract"]["forbidden_output_refs"]
    assert mutated["authority_scope"]["filesystem_write_allowed"] is False


def test_binding_rejects_missing_forbidden_boundaries() -> None:
    mutated = validator.build_mutated_binding(
        worker_contract__forbidden_input_refs=["secret://*"],
        worker_contract__forbidden_output_refs=["secret://*"],
    )
    mutated["contract_summary"]["forbidden_input_count"] = 1
    mutated["contract_summary"]["forbidden_output_count"] = 1

    errors = validator.validate_binding_record(mutated)

    assert any("forbidden_input_refs missing forbidden boundary prefix: network://" in error for error in errors)
    assert any("forbidden_input_refs missing forbidden boundary prefix: tenant://other" in error for error in errors)
    assert any("forbidden_output_refs missing forbidden boundary prefix: raw-output://" in error for error in errors)
    assert any("forbidden_output_refs missing forbidden boundary prefix: external-request://" in error for error in errors)
    assert any("forbidden_output_refs missing forbidden boundary prefix: filesystem-write://" in error for error in errors)


def test_binding_rejects_count_drift() -> None:
    mutated = validator.build_mutated_binding(
        contract_summary__allowed_input_count=1,
        contract_summary__verification_ref_count=1,
        contract_summary__recovery_ref_count=0,
    )

    errors = validator.validate_binding_record(mutated)

    assert any("allowed_input_count" in error for error in errors)
    assert any("verification_ref_count" in error for error in errors)
    assert any("recovery_ref_count" in error for error in errors)
    assert len(mutated["worker_contract"]["allowed_input_refs"]) == 3


def test_cli_json_accepts_relative_paths(capsys) -> None:
    exit_code = validator.main(
        [
            "--schema",
            "schemas/read_only_worker_binding.schema.json",
            "--binding",
            "examples/read_only_worker_binding.foundation.json",
            "--json",
        ]
    )

    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["status"] == "passed"
    assert Path(payload["schema_path"]).as_posix() == "schemas/read_only_worker_binding.schema.json"
    assert Path(payload["binding_path"]).as_posix() == "examples/read_only_worker_binding.foundation.json"
    assert payload["errors"] == []


def test_malformed_binding_payload_reports_errors() -> None:
    schema = validator._load_schema(validator.DEFAULT_SCHEMA_PATH)

    none_errors = validator.validate_binding_record(None, schema)
    list_errors = validator.validate_binding_record([], schema)

    assert any("read-only worker binding must be a JSON object" in error for error in none_errors)
    assert any("read-only worker binding must be a JSON object" in error for error in list_errors)
    assert any("expected object" in error for error in none_errors + list_errors)


def test_sdlc_requirement_and_design_validate_for_read_only_worker_binding() -> None:
    requirement_path = Path("examples/sdlc/requirement_read_only_worker_binding_20260614.json")
    design_path = Path("examples/sdlc/design_read_only_worker_binding_20260614.json")
    requirement = sdlc_validator.load_json_object(requirement_path, "ReadOnlyWorkerBinding requirement")
    design = sdlc_validator.load_json_object(design_path, "ReadOnlyWorkerBinding design")

    requirement_errors = sdlc_validator.validate_artifact_record("requirement", requirement)
    design_errors = sdlc_validator.validate_artifact_record("design_decision", design)

    assert requirement_errors == []
    assert design_errors == []
    assert design["requirement_id"] == requirement["requirement_id"]
    assert "schemas/read_only_worker_binding.schema.json" in design["schema_changes"]
    assert "scripts/validate_read_only_worker_binding.py" in design["validator_changes"]
    assert "no live worker dispatch" in requirement["non_goals"]
    assert "ReadOnlyWorkerBinding selects read_only_repo_inspection as the first worker path" in requirement["success_criteria"]
    assert design["security_model"]["effect_bearing_requires_receipt"] is True
    assert any("run_workspace_governance_checks.py" in command for command in design["test_plan"])
