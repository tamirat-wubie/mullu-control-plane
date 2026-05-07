"""MIL audit runbook operator checklist validation tests.

Tests: machine-readable MIL audit runbook workflow checklist validation and CLI output.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts.validate_mil_audit_runbook_operator_checklist import (
    main,
    validate_mil_audit_runbook_operator_checklist,
)

CHECKLIST_PATH = Path("examples") / "mil_audit_runbook_operator_checklist.json"


def test_validate_mil_audit_runbook_operator_checklist_accepts_example() -> None:
    result = validate_mil_audit_runbook_operator_checklist()

    assert result.valid is True
    assert result.checklist_id == "mil-audit-runbook-operator-v1"
    assert result.step_count == 5
    assert result.errors == ()


def test_validate_mil_audit_runbook_operator_checklist_rejects_missing_step(tmp_path: Path) -> None:
    checklist_path = tmp_path / "mil_audit_runbook_operator_checklist.json"
    payload = json.loads(CHECKLIST_PATH.read_text(encoding="utf-8"))
    payload["required_commands"] = [
        step for step in payload["required_commands"]
        if step["step_id"] != "admit_persisted_runbook"
    ]
    checklist_path.write_text(json.dumps(payload), encoding="utf-8")

    result = validate_mil_audit_runbook_operator_checklist(checklist_path)

    assert result.valid is False
    assert result.step_count == len(payload["required_commands"])
    assert any("admit_persisted_runbook" in error for error in result.errors)
    assert result.checklist_path == checklist_path


def test_validate_mil_audit_runbook_operator_checklist_rejects_evidence_drift(tmp_path: Path) -> None:
    checklist_path = tmp_path / "mil_audit_runbook_operator_checklist.json"
    payload = json.loads(CHECKLIST_PATH.read_text(encoding="utf-8"))
    for step in payload["required_commands"]:
        if step["step_id"] == "admit_persisted_runbook":
            step["required_evidence"] = [
                item for item in step["required_evidence"]
                if item != "runbook_persisted=true"
            ]
    checklist_path.write_text(json.dumps(payload), encoding="utf-8")

    result = validate_mil_audit_runbook_operator_checklist(checklist_path)

    assert result.valid is False
    assert result.step_count == 5
    assert any("admit_persisted_runbook required_evidence missing" in error for error in result.errors)
    assert any("runbook_persisted=true" in error for error in result.errors)


def test_validate_mil_audit_runbook_operator_checklist_rejects_command_drift(tmp_path: Path) -> None:
    checklist_path = tmp_path / "mil_audit_runbook_operator_checklist.json"
    payload = json.loads(CHECKLIST_PATH.read_text(encoding="utf-8"))
    for step in payload["required_commands"]:
        if step["step_id"] == "read_persisted_runbook":
            step["command"] = "mcoi mil-audit get --json \"$MULLU_MIL_RUNBOOK_ID\""
    checklist_path.write_text(json.dumps(payload), encoding="utf-8")

    result = validate_mil_audit_runbook_operator_checklist(checklist_path)

    assert result.valid is False
    assert result.step_count == 5
    assert any("read_persisted_runbook command missing token" in error for error in result.errors)
    assert any("mcoi mil-audit runbook-get" in error for error in result.errors)


def test_validate_mil_audit_runbook_operator_checklist_cli_outputs_json(capsys) -> None:
    exit_code = main(["--json"])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 0
    assert payload["valid"] is True
    assert payload["checklist_id"] == "mil-audit-runbook-operator-v1"
    assert payload["step_count"] == 5
    assert payload["errors"] == []


def test_validate_mil_audit_runbook_operator_checklist_missing_file_is_bounded(tmp_path: Path) -> None:
    checklist_path = tmp_path / "secret-mil-checklist-path.json"

    result = validate_mil_audit_runbook_operator_checklist(checklist_path)
    serialized_errors = json.dumps(result.errors, sort_keys=True)

    assert result.valid is False
    assert "checklist could not be read" in result.errors
    assert "secret-mil-checklist-path" not in serialized_errors


def test_validate_mil_audit_runbook_operator_checklist_json_parse_error_is_bounded(tmp_path: Path) -> None:
    checklist_path = tmp_path / "mil_audit_runbook_operator_checklist.json"
    checklist_path.write_text('{"checklist_id": "secret-json-token"', encoding="utf-8")

    result = validate_mil_audit_runbook_operator_checklist(checklist_path)
    serialized_errors = json.dumps(result.errors, sort_keys=True)

    assert result.valid is False
    assert "checklist must be JSON" in result.errors
    assert "secret-json-token" not in serialized_errors
