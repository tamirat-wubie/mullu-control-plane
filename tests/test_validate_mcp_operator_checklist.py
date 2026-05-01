"""MCP operator checklist validation tests.

Tests: machine-readable MCP handoff checklist validation and CLI output.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts.validate_mcp_operator_checklist import (
    main,
    validate_mcp_operator_checklist,
)


def test_validate_mcp_operator_checklist_accepts_example() -> None:
    result = validate_mcp_operator_checklist()

    assert result.valid is True
    assert result.checklist_id == "mcp-operator-handoff-v1"
    assert result.step_count == 6
    assert result.errors == ()


def test_validate_mcp_operator_checklist_rejects_missing_required_step(tmp_path: Path) -> None:
    checklist_path = tmp_path / "mcp_operator_handoff_checklist.json"
    payload = json.loads(Path("examples/mcp_operator_handoff_checklist.json").read_text(encoding="utf-8"))
    payload["required_commands"] = [
        step for step in payload["required_commands"]
        if step["step_id"] != "run_deployment_preflight"
    ]
    checklist_path.write_text(json.dumps(payload), encoding="utf-8")

    result = validate_mcp_operator_checklist(checklist_path)

    assert result.valid is False
    assert result.step_count == len(payload["required_commands"])
    assert any("run_deployment_preflight" in error for error in result.errors)
    assert result.checklist_path == checklist_path


def test_validate_mcp_operator_checklist_cli_outputs_json(capsys) -> None:
    exit_code = main(["--json"])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 0
    assert payload["valid"] is True
    assert payload["checklist_id"] == "mcp-operator-handoff-v1"
    assert payload["step_count"] == 6
    assert payload["errors"] == []


def test_validate_mcp_operator_checklist_cli_fails_invalid(tmp_path: Path, capsys) -> None:
    checklist_path = tmp_path / "invalid_checklist.json"
    checklist_path.write_text(json.dumps({"schema_version": 1}), encoding="utf-8")

    exit_code = main(["--checklist", str(checklist_path)])
    captured = capsys.readouterr()

    assert exit_code == 2
    assert "error:" in captured.out
    assert "checklist_id must be mcp-operator-handoff-v1" in captured.out
    assert captured.err == ""


def test_validate_mcp_operator_checklist_rejects_missing_step_evidence(tmp_path: Path) -> None:
    checklist_path = tmp_path / "mcp_operator_handoff_checklist.json"
    payload = json.loads(Path("examples/mcp_operator_handoff_checklist.json").read_text(encoding="utf-8"))
    for step in payload["required_commands"]:
        if step["step_id"] == "collect_runtime_conformance":
            step["required_evidence"] = [
                item for item in step["required_evidence"]
                if item != "capability_plan_bundle_canary_passed=true"
            ]
    checklist_path.write_text(json.dumps(payload), encoding="utf-8")

    result = validate_mcp_operator_checklist(checklist_path)

    assert result.valid is False
    assert result.step_count == 6
    assert any("collect_runtime_conformance required_evidence missing" in error for error in result.errors)
    assert any("capability_plan_bundle_canary_passed=true" in error for error in result.errors)


def test_validate_mcp_operator_checklist_rejects_command_token_drift(tmp_path: Path) -> None:
    checklist_path = tmp_path / "mcp_operator_handoff_checklist.json"
    payload = json.loads(Path("examples/mcp_operator_handoff_checklist.json").read_text(encoding="utf-8"))
    for step in payload["required_commands"]:
        if step["step_id"] == "inspect_mcp_execution_evidence_bundle":
            step["command"] = "curl \"$MULLU_GATEWAY_URL/mcp/operator/read-model\""
    checklist_path.write_text(json.dumps(payload), encoding="utf-8")

    result = validate_mcp_operator_checklist(checklist_path)

    assert result.valid is False
    assert result.step_count == 6
    assert any("inspect_mcp_execution_evidence_bundle command missing token" in error for error in result.errors)
    assert any("/mcp/operator/evidence-bundles/" in error for error in result.errors)
