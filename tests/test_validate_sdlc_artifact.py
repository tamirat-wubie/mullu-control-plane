"""Purpose: verify governed SDLC artifact validation.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, PRS]
Dependencies: scripts.validate_sdlc_artifact.
Invariants:
  - SDLC docs, schemas, and examples validate as one linked chain.
  - Raw private reasoning fields are rejected.
  - Cross-artifact drift is reported explicitly.
"""

from __future__ import annotations

import copy
import io
import json
from contextlib import redirect_stdout
from pathlib import Path

import pytest

from scripts import validate_sdlc_artifact as validator


def test_current_sdlc_contract_passes() -> None:
    errors = validator.validate_contract()
    records = validator.load_example_records()

    assert errors == []
    assert len(records) == 9
    assert all(spec.schema_path.exists() for spec in validator.ARTIFACT_SPECS)
    assert all(spec.example_path.exists() for spec in validator.ARTIFACT_SPECS)
    assert "scripts/validate_sdlc_pr_enforcement.py" in validator.REQUIRED_VALIDATORS


def test_schema_artifacts_have_expected_identity() -> None:
    for spec in validator.ARTIFACT_SPECS:
        schema = validator._load_schema(spec.schema_path)
        errors = validator.validate_schema_artifact(schema, spec)

        assert errors == []
        assert schema["$id"] == spec.schema_id
        assert schema["title"] == spec.title
        assert schema["additionalProperties"] is False


def test_example_chain_links_all_lifecycle_artifacts() -> None:
    records = validator.load_example_records()
    errors = validator.validate_example_chain(records)

    assert errors == []
    assert records["requirement"]["request_id"] == records["change_request"]["request_id"]
    assert records["work_plan"]["design_id"] == records["design_decision"]["design_id"]
    assert records["deployment_candidate"]["release_id"] == records["release_candidate"]["release_id"]


def test_raw_private_reasoning_field_is_rejected() -> None:
    records = validator.load_example_records()
    invalid_design = copy.deepcopy(records["design_decision"])
    invalid_design["raw_chain_of_thought"] = "private reasoning must not be serialized"

    errors = validator.validate_artifact_record("design_decision", invalid_design)

    assert any("raw_chain_of_thought is prohibited" in error for error in errors)
    assert len(errors) >= 1
    assert invalid_design["design_id"] == "sdlc_design_uao_validator_001"


def test_cross_artifact_request_drift_is_rejected() -> None:
    records = validator.load_example_records()
    invalid_records = copy.deepcopy(records)
    invalid_records["requirement"]["request_id"] = "wrong_request"

    errors = validator.validate_example_chain(invalid_records)

    assert "example_chain: requirement.request_id must match change request" in errors
    assert len(errors) >= 1
    assert invalid_records["change_request"]["request_id"] == "sdlc_req_uao_validator_001"


def test_work_plan_rejects_future_dependency_and_missing_validator() -> None:
    work_plan = copy.deepcopy(validator.load_example_records()["work_plan"])
    work_plan["steps"][0]["depends_on"] = [2]
    work_plan["required_validators"] = [
        item
        for item in work_plan["required_validators"]
        if item != "scripts/validate_sdlc_state_machine.py"
    ]

    errors = validator.validate_artifact_record("work_plan", work_plan)

    assert any("dependency 2 must be earlier" in error for error in errors)
    assert any("missing required validators" in error for error in errors)
    assert len(errors) >= 2


def test_design_and_verification_require_pr_enforcement_validator() -> None:
    records = validator.load_example_records()
    invalid_design = copy.deepcopy(records["design_decision"])
    invalid_verification = copy.deepcopy(records["verification_receipt"])
    invalid_design["validator_changes"] = [
        item
        for item in invalid_design["validator_changes"]
        if item != "scripts/validate_sdlc_pr_enforcement.py"
    ]
    invalid_verification["commands"] = [
        item
        for item in invalid_verification["commands"]
        if item["name"] != "sdlc_pr_enforcement_validation"
    ]
    invalid_verification["validator_outputs"] = [
        item
        for item in invalid_verification["validator_outputs"]
        if item["name"] != "sdlc_pr_enforcement_validation"
    ]

    design_errors = validator.validate_artifact_record("design_decision", invalid_design)
    verification_errors = validator.validate_artifact_record("verification_receipt", invalid_verification)

    assert any("design_decision: missing required validators" in error for error in design_errors)
    assert any("verification_receipt: missing command sdlc_pr_enforcement_validation" in error for error in verification_errors)
    assert any("verification_receipt: missing validator outputs" in error for error in verification_errors)
    assert len(design_errors) + len(verification_errors) >= 3


def test_cli_json_receipt_reports_passed_contract() -> None:
    stdout_buffer = io.StringIO()

    with redirect_stdout(stdout_buffer):
        exit_code = validator.main(["--json"])

    report = json.loads(stdout_buffer.getvalue())
    assert exit_code == 0
    assert report["receipt_id"] == "sdlc_artifact_validation_receipt"
    assert report["terminal_closure_required"] is True
    assert report["receipt_is_not_terminal_closure"] is True
    assert report["valid"] is True
    assert report["status"] == "passed"
    assert report["error_count"] == 0


def test_load_json_object_rejects_non_object_json(tmp_path: Path) -> None:
    payload_path = tmp_path / "invalid-sdlc.json"
    payload_path.write_text(json.dumps(["not", "object"]), encoding="utf-8")

    with pytest.raises(ValueError):
        validator.load_json_object(payload_path, "payload")

    assert payload_path.exists()
    assert payload_path.suffix == ".json"
