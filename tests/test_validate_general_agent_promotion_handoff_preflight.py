"""Tests for general-agent promotion handoff preflight report validation."""

from __future__ import annotations

import json
from pathlib import Path

from scripts.validate_general_agent_promotion_handoff_preflight import (
    main,
    validate_general_agent_promotion_handoff_preflight,
)


def test_validate_handoff_preflight_accepts_ready_report(tmp_path: Path) -> None:
    report_path = tmp_path / "preflight.json"
    report_path.write_text(json.dumps(_ready_report()), encoding="utf-8")

    result = validate_general_agent_promotion_handoff_preflight(report_path=report_path)

    assert result.valid is True
    assert result.ready is True
    assert result.step_count == 9
    assert result.blockers == ()


def test_validate_handoff_preflight_accepts_blocked_missing_environment_report(tmp_path: Path) -> None:
    report_path = tmp_path / "preflight.json"
    report_path.write_text(json.dumps(_blocked_report()), encoding="utf-8")

    result = validate_general_agent_promotion_handoff_preflight(report_path=report_path)

    assert result.valid is True
    assert result.ready is False
    assert "required environment bindings" in result.blockers
    assert "MULLU_GATEWAY_URL" in result.missing_environment_variables


def test_validate_handoff_preflight_require_ready_rejects_blocked_report(tmp_path: Path) -> None:
    report_path = tmp_path / "preflight.json"
    report_path.write_text(json.dumps(_blocked_report()), encoding="utf-8")

    result = validate_general_agent_promotion_handoff_preflight(
        report_path=report_path,
        require_ready=True,
    )

    assert result.valid is False
    assert result.ready is False
    assert any("ready must be true" in error for error in result.errors)


def test_validate_handoff_preflight_rejects_stale_blocker_derivation(tmp_path: Path) -> None:
    report_path = tmp_path / "preflight.json"
    payload = _blocked_report()
    payload["blockers"] = []
    report_path.write_text(json.dumps(payload), encoding="utf-8")

    result = validate_general_agent_promotion_handoff_preflight(report_path=report_path)

    assert result.valid is False
    assert any("blockers must match failed steps" in error for error in result.errors)
    assert any("missing_environment_variables require" in error for error in result.errors)


def test_validate_handoff_preflight_cli_outputs_json(tmp_path: Path, capsys) -> None:
    report_path = tmp_path / "preflight.json"
    report_path.write_text(json.dumps(_ready_report()), encoding="utf-8")

    exit_code = main(["--report", str(report_path), "--json"])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 0
    assert payload["valid"] is True
    assert payload["ready"] is True
    assert payload["step_count"] == 9


def _ready_report() -> dict[str, object]:
    return {
        "blockers": [],
        "checked_at": "2026-05-01T12:00:00+00:00",
        "missing_environment_variables": [],
        "production_ready": False,
        "readiness_level": "pilot-governed-core",
        "ready": True,
        "step_count": 9,
        "steps": [
            {"detail": "valid=true", "name": "operator checklist validation", "passed": True},
            {"detail": "valid=true", "name": "handoff packet validation", "passed": True},
            {"detail": "valid=true", "name": "environment binding contract validation", "passed": True},
            {"detail": "valid=true", "name": "environment binding receipt validation", "passed": True},
            {"detail": "all required environment variables are present", "name": "required environment bindings", "passed": True},
            {"detail": "ok=true action_count=5 approval_required_action_count=2 blocker_count=5", "name": "adapter closure schema validation", "passed": True},
            {"detail": "ok=true action_count=7 approval_required_action_count=4 source_plan_types=['adapter', 'deployment']", "name": "closure plan schema validation", "passed": True},
            {"detail": "ok=true expected_action_count=7 observed_action_count=7 expected_approval_required_count=4 observed_approval_required_count=4", "name": "closure plan drift validation", "passed": True},
            {"detail": "readiness_level=pilot-governed-core capability_count=52 capsule_count=10 production_ready=false", "name": "promotion readiness report", "passed": True},
        ],
    }


def _blocked_report() -> dict[str, object]:
    payload = _ready_report()
    payload["ready"] = False
    payload["blockers"] = ["required environment bindings"]
    payload["missing_environment_variables"] = ["MULLU_GATEWAY_URL"]
    steps = list(payload["steps"])  # type: ignore[arg-type]
    steps[4] = {
        "detail": "missing=['MULLU_GATEWAY_URL']",
        "name": "required environment bindings",
        "passed": False,
    }
    payload["steps"] = steps
    return payload
