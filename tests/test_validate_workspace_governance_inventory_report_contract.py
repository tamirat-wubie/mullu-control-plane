"""Purpose: verify workspace governance inventory report contract validation.
Governance scope: [OCE, RAG, CDCV, UWMA, PRS]
Dependencies: scripts.validate_workspace_governance_inventory_report_contract.
Invariants:
  - The schema artifact carries all required report and artifact fields.
  - Current inventory reporter output matches the schema-level contract.
  - Contradictory count and status evidence is rejected.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from scripts import validate_workspace_governance_inventory_report_contract as validator


def test_current_inventory_report_contract_passes() -> None:
    errors = validator.validate_contract()
    report = validator.build_current_report()
    schema = validator.load_json_object(validator.DEFAULT_SCHEMA_PATH, "schema")

    assert errors == []
    assert schema["title"] == "Workspace Governance Inventory Report"
    assert report["report_id"] == "workspace_governance_inventory"
    assert report["report_is_not_terminal_closure"] is True
    assert report["terminal_closure_required"] is True


def test_schema_artifact_rejects_missing_required_artifact_field() -> None:
    schema = validator.load_json_object(validator.DEFAULT_SCHEMA_PATH, "schema")
    invalid_schema = copy.deepcopy(schema)
    invalid_schema["$defs"]["inventory_artifact"]["required"] = [
        field for field in invalid_schema["$defs"]["inventory_artifact"]["required"] if field != "issue"
    ]

    errors = validator.validate_schema_artifact(invalid_schema)

    assert any("schema missing required artifact field: issue" in error for error in errors)
    assert "issue" not in invalid_schema["$defs"]["inventory_artifact"]["required"]
    assert len(errors) >= 1


def test_artifact_count_mismatch_is_reported() -> None:
    report = validator.build_current_report()
    invalid_report = copy.deepcopy(report)
    invalid_report["artifact_count"] += 1

    errors = validator.validate_report(invalid_report)

    assert "artifact_count does not match artifacts length" in errors
    assert invalid_report["artifact_count"] == report["artifact_count"] + 1
    assert len(errors) >= 1


def test_status_mismatch_is_reported() -> None:
    report = validator.build_current_report()
    invalid_report = copy.deepcopy(report)
    invalid_report["status"] = "failed"

    errors = validator.validate_report(invalid_report)

    assert any("report status must be passed" in error for error in errors)
    assert invalid_report["status"] == "failed"
    assert invalid_report["missing_count"] == 0


def test_missing_artifact_issue_is_required() -> None:
    report = validator.build_current_report()
    invalid_report = copy.deepcopy(report)
    invalid_report["artifacts"][0]["exists"] = False
    invalid_report["artifacts"][0]["issue"] = None
    invalid_report["artifacts"][0]["size_bytes"] = None
    invalid_report["missing_count"] = 1
    invalid_report["issue_count"] = 0
    invalid_report["status"] = "failed"

    errors = validator.validate_report(invalid_report)

    assert any("missing artifact must include issue" in error for error in errors)
    assert invalid_report["artifacts"][0]["exists"] is False
    assert invalid_report["status"] == "failed"


def test_unexpected_report_field_is_reported() -> None:
    report = validator.build_current_report()
    invalid_report = copy.deepcopy(report)
    invalid_report["sha256"] = "forbidden"

    errors = validator.validate_report(invalid_report)

    assert "report has unexpected field: sha256" in errors
    assert invalid_report["sha256"] == "forbidden"
    assert len(errors) >= 1


def test_cli_passes(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = validator.main([])
    streams = capsys.readouterr()

    assert exit_code == 0
    assert "[PASS] workspace_governance_inventory_report_current_output" in streams.out
    assert streams.err == ""


def test_load_json_object_rejects_non_object_json(tmp_path: Path) -> None:
    json_path = tmp_path / "payload.json"
    json_path.write_text(json.dumps(["not", "object"]), encoding="utf-8")

    with pytest.raises(ValueError):
        validator.load_json_object(json_path, "payload")

    assert json_path.exists()
    assert json_path.name == "payload.json"
