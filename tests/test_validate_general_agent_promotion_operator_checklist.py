"""General-agent promotion operator checklist validation tests."""

from __future__ import annotations

import json
from pathlib import Path

from scripts.validate_general_agent_promotion_operator_checklist import (
    main,
    validate_general_agent_promotion_operator_checklist,
)


CHECKLIST_PATH = Path("examples") / "general_agent_promotion_operator_checklist.json"


def test_validate_promotion_operator_checklist_accepts_example() -> None:
    result = validate_general_agent_promotion_operator_checklist()

    assert result.valid is True
    assert result.checklist_id == "general-agent-promotion-operator-v1"
    assert result.step_count == 9
    assert result.errors == ()


def test_validate_promotion_operator_checklist_rejects_missing_approval_blocker(tmp_path: Path) -> None:
    checklist_path = tmp_path / "promotion_operator_checklist.json"
    payload = json.loads(CHECKLIST_PATH.read_text(encoding="utf-8"))
    payload["approval_required_blockers"].remove("production_health_not_declared")
    checklist_path.write_text(json.dumps(payload), encoding="utf-8")

    result = validate_general_agent_promotion_operator_checklist(checklist_path)

    assert result.valid is False
    assert any("approval_required_blockers missing" in error for error in result.errors)
    assert any("production_health_not_declared" in error for error in result.errors)


def test_validate_promotion_operator_checklist_rejects_command_drift(tmp_path: Path) -> None:
    checklist_path = tmp_path / "promotion_operator_checklist.json"
    payload = json.loads(CHECKLIST_PATH.read_text(encoding="utf-8"))
    for step in payload["required_commands"]:
        if step["step_id"] == "validate_aggregate_closure_plan":
            step["command"] = "python scripts\\plan_general_agent_promotion_closure.py"
    checklist_path.write_text(json.dumps(payload), encoding="utf-8")

    result = validate_general_agent_promotion_operator_checklist(checklist_path)

    assert result.valid is False
    assert any("validate_general_agent_promotion_closure_plan_schema.py" in error for error in result.errors)
    assert any("validate_general_agent_promotion_closure_plan.py" in error for error in result.errors)
    assert any("--strict" in error for error in result.errors)


def test_validate_promotion_operator_checklist_cli_outputs_json(capsys) -> None:
    exit_code = main(["--json"])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 0
    assert payload["valid"] is True
    assert payload["checklist_id"] == "general-agent-promotion-operator-v1"
    assert payload["step_count"] == 9
    assert payload["errors"] == []


def test_validate_promotion_operator_checklist_rejects_missing_adapter_schema_gate(
    tmp_path: Path,
) -> None:
    checklist_path = tmp_path / "promotion_operator_checklist.json"
    payload = json.loads(CHECKLIST_PATH.read_text(encoding="utf-8"))
    payload["required_commands"] = [
        step for step in payload["required_commands"] if step["step_id"] != "validate_adapter_closure_plan_schema"
    ]
    checklist_path.write_text(json.dumps(payload), encoding="utf-8")

    result = validate_general_agent_promotion_operator_checklist(checklist_path)

    assert result.valid is False
    assert any("required_commands missing steps" in error for error in result.errors)
    assert any("validate_adapter_closure_plan_schema" in error for error in result.errors)
