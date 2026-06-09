"""Purpose: verify holistic loop read-model contract validation.
Governance scope: schema shape, current report validation, blocker/status
    consistency, and non-terminal closure fields.
Dependencies: scripts.validate_holistic_loop_read_model.
Invariants:
  - Current report output validates.
  - Count and blocker contradictions are rejected.
  - Closed or verified loops cannot carry missing evidence.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from scripts import validate_holistic_loop_read_model as validator


def test_current_holistic_loop_read_model_contract_passes() -> None:
    errors = validator.validate_contract()
    report = validator.build_report()
    schema = validator.load_json_object(validator.DEFAULT_SCHEMA_PATH, "schema")

    assert errors == []
    assert schema["title"] == "Holistic Loop Read Model"
    assert report["report_id"] == "holistic_loop_read_model"
    assert report["report_is_not_terminal_closure"] is True
    assert report["terminal_closure_required"] is True


def test_schema_rejects_missing_required_loop_field() -> None:
    schema = validator.load_json_object(validator.DEFAULT_SCHEMA_PATH, "schema")
    invalid_schema = copy.deepcopy(schema)
    invalid_schema["$defs"]["loop_summary"]["required"] = [
        field for field in invalid_schema["$defs"]["loop_summary"]["required"] if field != "open_blockers"
    ]

    errors = validator.validate_schema_artifact(invalid_schema)

    assert any("schema missing required loop field: open_blockers" in error for error in errors)
    assert "open_blockers" not in invalid_schema["$defs"]["loop_summary"]["required"]
    assert len(errors) >= 1


def test_blocked_count_mismatch_is_reported() -> None:
    report = validator.build_report()
    invalid_report = copy.deepcopy(report)
    invalid_report["blocked_count"] = 0

    errors = validator.validate_report(invalid_report)

    assert "blocked_count does not match loop blockers" in errors
    assert invalid_report["blocked_count"] == 0
    assert report["blocked_count"] == 4


def test_status_mismatch_is_reported() -> None:
    report = validator.build_report()
    invalid_report = copy.deepcopy(report)
    invalid_report["status"] = "verified"

    errors = validator.validate_report(invalid_report)

    assert any("report status must be blocked" in error for error in errors)
    assert invalid_report["status"] == "verified"
    assert invalid_report["blocked_count"] == report["blocked_count"]


def test_missing_evidence_requires_matching_blocker() -> None:
    report = validator.build_report()
    invalid_report = copy.deepcopy(report)
    invalid_report["loops"][0]["open_blockers"] = []

    errors = validator.validate_report(invalid_report)

    assert any("missing evidence lacks blocker" in error for error in errors)
    assert invalid_report["loops"][0]["missing_evidence"]
    assert invalid_report["loops"][0]["open_blockers"] == []


def test_verified_loop_cannot_miss_evidence() -> None:
    report = validator.build_report()
    invalid_report = copy.deepcopy(report)
    invalid_report["loops"][0]["status"] = "verified"

    errors = validator.validate_report(invalid_report)

    assert any("verified or closed loop cannot miss evidence" in error for error in errors)
    assert invalid_report["loops"][0]["status"] == "verified"
    assert invalid_report["loops"][0]["missing_evidence"]


def test_unexpected_report_field_is_reported() -> None:
    report = validator.build_report()
    invalid_report = copy.deepcopy(report)
    invalid_report["extra"] = "forbidden"

    errors = validator.validate_report(invalid_report)

    assert "report has unexpected field: extra" in errors
    assert invalid_report["extra"] == "forbidden"
    assert len(errors) >= 1


def test_cli_passes(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = validator.main([])
    streams = capsys.readouterr()

    assert exit_code == 0
    assert "[PASS] holistic_loop_read_model_current_output" in streams.out
    assert streams.err == ""


def test_load_json_object_rejects_non_object_json(tmp_path: Path) -> None:
    json_path = tmp_path / "payload.json"
    json_path.write_text(json.dumps(["not", "object"]), encoding="utf-8")

    with pytest.raises(ValueError):
        validator.load_json_object(json_path, "payload")

    assert json_path.exists()
    assert json_path.name == "payload.json"
