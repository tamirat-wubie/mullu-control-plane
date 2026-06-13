"""Tests for general-agent promotion handoff preflight report validation."""

from __future__ import annotations

import json
from pathlib import Path

from scripts.validate_general_agent_promotion_handoff_preflight import (
    main,
    validate_general_agent_promotion_handoff_preflight,
)


def test_validate_handoff_preflight_accepts_handoff_ready_report(tmp_path: Path) -> None:
    report_path = tmp_path / "preflight.json"
    report_path.write_text(json.dumps(_ready_report()), encoding="utf-8")

    result = validate_general_agent_promotion_handoff_preflight(report_path=report_path)

    assert result.valid is True
    assert result.ready is True
    assert result.step_count == 10
    assert result.blockers == ()
    assert result.environment_binding_action_count == 0


def test_validate_handoff_preflight_accepts_blocked_missing_environment_report(tmp_path: Path) -> None:
    report_path = tmp_path / "preflight.json"
    report_path.write_text(json.dumps(_blocked_report()), encoding="utf-8")

    result = validate_general_agent_promotion_handoff_preflight(report_path=report_path)

    assert result.valid is True
    assert result.ready is False
    assert "required environment bindings" in result.blockers
    assert "MULLU_GATEWAY_URL" in result.missing_environment_variables
    assert result.environment_binding_action_count == 1


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


def test_validate_handoff_preflight_rejects_missing_environment_action(tmp_path: Path) -> None:
    report_path = tmp_path / "preflight.json"
    payload = _blocked_report()
    payload["environment_binding_actions"] = []
    report_path.write_text(json.dumps(payload), encoding="utf-8")

    result = validate_general_agent_promotion_handoff_preflight(report_path=report_path)

    assert result.valid is False
    assert any("environment_binding_actions names must match" in error for error in result.errors)


def test_validate_handoff_preflight_rejects_duplicate_missing_environment_names(tmp_path: Path) -> None:
    report_path = tmp_path / "preflight.json"
    payload = _blocked_report()
    payload["missing_environment_variables"] = ["MULLU_GATEWAY_URL", "MULLU_GATEWAY_URL"]
    actions = list(payload["environment_binding_actions"])  # type: ignore[arg-type]
    actions.append(dict(actions[0]))  # type: ignore[arg-type]
    payload["environment_binding_actions"] = actions
    report_path.write_text(json.dumps(payload), encoding="utf-8")

    result = validate_general_agent_promotion_handoff_preflight(report_path=report_path)

    assert result.valid is False
    assert any("missing_environment_variables entries must be unique" in error for error in result.errors)
    assert any("environment_binding_actions names entries must be unique" in error for error in result.errors)


def test_validate_handoff_preflight_rejects_duplicate_action_names_even_when_missing_names_are_unique(
    tmp_path: Path,
) -> None:
    report_path = tmp_path / "preflight.json"
    payload = _blocked_report()
    actions = list(payload["environment_binding_actions"])  # type: ignore[arg-type]
    actions.append(dict(actions[0]))  # type: ignore[arg-type]
    payload["environment_binding_actions"] = actions
    report_path.write_text(json.dumps(payload), encoding="utf-8")

    result = validate_general_agent_promotion_handoff_preflight(report_path=report_path)

    assert result.valid is False
    assert any("environment_binding_actions names entries must be unique" in error for error in result.errors)
    assert any("environment_binding_actions names must match" in error for error in result.errors)


def test_validate_handoff_preflight_rejects_serialized_environment_value(tmp_path: Path) -> None:
    report_path = tmp_path / "preflight.json"
    payload = _blocked_report()
    actions = list(payload["environment_binding_actions"])  # type: ignore[arg-type]
    actions[0]["value"] = "do-not-serialize"  # type: ignore[index]
    payload["environment_binding_actions"] = actions
    report_path.write_text(json.dumps(payload), encoding="utf-8")

    result = validate_general_agent_promotion_handoff_preflight(report_path=report_path)

    assert result.valid is False
    assert any("must not carry serialized values" in error for error in result.errors)


def test_validate_handoff_preflight_rejects_environment_action_contract_drift(tmp_path: Path) -> None:
    report_path = tmp_path / "preflight.json"
    payload = _blocked_report()
    actions = list(payload["environment_binding_actions"])  # type: ignore[arg-type]
    actions[0]["risk"] = "medium"  # type: ignore[index]
    payload["environment_binding_actions"] = actions
    report_path.write_text(json.dumps(payload), encoding="utf-8")

    result = validate_general_agent_promotion_handoff_preflight(report_path=report_path)

    assert result.valid is False
    assert any("MULLU_GATEWAY_URL risk must match environment binding contract" in error for error in result.errors)


def test_validate_handoff_preflight_rejects_environment_action_workflow_drift(tmp_path: Path) -> None:
    report_path = tmp_path / "preflight.json"
    payload = _blocked_report()
    actions = list(payload["environment_binding_actions"])  # type: ignore[arg-type]
    actions[0]["required_for"] = ["handoff_preflight"]  # type: ignore[index]
    payload["environment_binding_actions"] = actions
    report_path.write_text(json.dumps(payload), encoding="utf-8")

    result = validate_general_agent_promotion_handoff_preflight(report_path=report_path)

    assert result.valid is False
    assert any("MULLU_GATEWAY_URL required_for must match environment binding contract" in error for error in result.errors)


def test_validate_handoff_preflight_cli_outputs_json(tmp_path: Path, capsys) -> None:
    report_path = tmp_path / "preflight.json"
    report_path.write_text(json.dumps(_ready_report()), encoding="utf-8")

    exit_code = main(["--report", str(report_path), "--json"])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 0
    assert payload["valid"] is True
    assert payload["ready"] is True
    assert payload["step_count"] == 10
    assert payload["environment_binding_action_count"] == 0


def test_validate_handoff_preflight_missing_file_error_is_bounded(tmp_path: Path) -> None:
    report_path = tmp_path / "secret-preflight-path.json"

    result = validate_general_agent_promotion_handoff_preflight(report_path=report_path)
    serialized_errors = json.dumps(result.errors, sort_keys=True)

    assert result.valid is False
    assert "preflight report could not be read" in result.errors
    assert "secret-preflight-path" not in serialized_errors


def test_validate_handoff_preflight_json_parse_error_is_bounded(tmp_path: Path) -> None:
    report_path = tmp_path / "preflight.json"
    report_path.write_text('{"readiness_level": "secret-json-token"', encoding="utf-8")

    result = validate_general_agent_promotion_handoff_preflight(report_path=report_path)
    serialized = json.dumps(result.as_dict(), sort_keys=True)

    assert result.valid is False
    assert "preflight report must be JSON" in result.errors
    assert "secret-json-token" not in serialized


def test_validate_handoff_preflight_rejects_nonfinite_json_constants(tmp_path: Path) -> None:
    report_path = tmp_path / "preflight.json"
    report_path.write_text('{"ready": true, "step_count": Infinity}', encoding="utf-8")

    result = validate_general_agent_promotion_handoff_preflight(report_path=report_path)
    serialized = json.dumps(result.as_dict(), sort_keys=True)

    assert result.valid is False
    assert "preflight report must be JSON" in result.errors
    assert "Infinity" not in serialized


def _ready_report() -> dict[str, object]:
    return {
        "blockers": [],
        "checked_at": "2026-05-01T12:00:00+00:00",
        "missing_environment_variables": [],
        "environment_binding_actions": [],
        "production_ready": True,
        "readiness_level": "production-general-agent",
        "ready": True,
        "step_count": 10,
        "steps": [
            {"detail": "valid=true", "name": "operator checklist validation", "passed": True},
            {"detail": "valid=true", "name": "handoff packet validation", "passed": True},
            {
                "detail": "conditional responsibility debt blockers present",
                "name": "conditional responsibility debt blockers",
                "passed": True,
            },
            {"detail": "valid=true", "name": "environment binding contract validation", "passed": True},
            {"detail": "valid=true", "name": "environment binding receipt validation", "passed": True},
            {"detail": "all required environment variables are present", "name": "required environment bindings", "passed": True},
            {"detail": "ok=true action_count=0 approval_required_action_count=0 blocker_count=0", "name": "adapter closure schema validation", "passed": True},
            {"detail": "ok=true action_count=6 approval_required_action_count=6 source_plan_types=['deployment', 'portfolio']", "name": "closure plan schema validation", "passed": True},
            {"detail": "ok=true expected_action_count=6 observed_action_count=6 expected_approval_required_count=6 observed_approval_required_count=6", "name": "closure plan drift validation", "passed": True},
            {"detail": "readiness_level=production-general-agent capability_count=80 capsule_count=13 production_ready=true", "name": "promotion readiness report", "passed": True},
        ],
    }


def _blocked_report() -> dict[str, object]:
    payload = _ready_report()
    payload["ready"] = False
    payload["blockers"] = ["required environment bindings"]
    payload["missing_environment_variables"] = ["MULLU_GATEWAY_URL"]
    payload["environment_binding_actions"] = [
        {
            "name": "MULLU_GATEWAY_URL",
            "binding_kind": "url",
            "risk": "high",
            "approval_required": False,
            "required_for": [
                "deployment_witness_publication",
                "public_health_declaration",
                "handoff_preflight",
            ],
            "receipt_projection": "name_and_presence_only",
            "verification_command": (
                "Bind the environment variable in the operator runtime without printing or serializing its value, "
                "then run: python scripts\\emit_general_agent_promotion_environment_binding_receipt.py "
                "--output .change_assurance\\general_agent_promotion_environment_binding_receipt.json --json "
                "&& python scripts\\validate_general_agent_promotion_environment_binding_receipt.py "
                "--receipt .change_assurance\\general_agent_promotion_environment_binding_receipt.json "
                "--require-ready --json"
            ),
        }
    ]
    steps = list(payload["steps"])  # type: ignore[arg-type]
    steps[5] = {
        "detail": "missing=['MULLU_GATEWAY_URL']",
        "name": "required environment bindings",
        "passed": False,
    }
    payload["steps"] = steps
    return payload
