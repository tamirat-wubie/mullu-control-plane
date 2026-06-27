"""General-agent promotion handoff packet validation tests."""

from __future__ import annotations

import json
from pathlib import Path

import scripts.validate_general_agent_promotion_handoff_packet as handoff_validator
from scripts.validate_general_agent_promotion_handoff_packet import (
    main,
    validate_general_agent_promotion_handoff_packet,
)


PACKET_PATH = Path("examples") / "general_agent_promotion_handoff_packet.json"


def test_validate_promotion_handoff_packet_accepts_example() -> None:
    result = validate_general_agent_promotion_handoff_packet()

    assert result.valid is True
    assert result.packet_id == "general-agent-promotion-handoff-v1"
    assert result.open_blocker_count == 0
    assert result.approval_required_count == 6
    assert result.errors == ()


def test_validate_promotion_handoff_packet_derives_missing_closure_plan(tmp_path: Path) -> None:
    result = validate_general_agent_promotion_handoff_packet(
        closure_plan_path=tmp_path / "missing_general_agent_promotion_closure_plan.json",
    )

    assert result.valid is True
    assert result.open_blocker_count == 0
    assert result.approval_required_count == 6
    assert result.errors == ()


def test_validate_promotion_handoff_packet_derives_blocked_adapter_plan_when_default_evidence_is_closed(
    tmp_path: Path,
    monkeypatch,
) -> None:
    closed_evidence_path = tmp_path / "capability_adapter_evidence.json"
    closed_evidence_path.write_text(
        (Path("examples") / "capability_adapter_evidence_live_closed_20260611.json").read_text(
            encoding="utf-8"
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(handoff_validator, "DEFAULT_ADAPTER_EVIDENCE", closed_evidence_path)

    result = validate_general_agent_promotion_handoff_packet(
        closure_plan_path=tmp_path / "missing_general_agent_promotion_closure_plan.json",
    )

    assert result.valid is True
    assert result.open_blocker_count == 0
    assert result.approval_required_count == 6
    assert result.errors == ()


def test_validate_promotion_handoff_packet_rejects_missing_entry_point(tmp_path: Path) -> None:
    packet_path = tmp_path / "general_agent_promotion_handoff_packet.json"
    payload = json.loads(PACKET_PATH.read_text(encoding="utf-8"))
    payload["entry_points"]["handoff_packet_validator"] = "scripts/unknown.py"
    packet_path.write_text(json.dumps(payload), encoding="utf-8")

    result = validate_general_agent_promotion_handoff_packet(packet_path=packet_path)

    assert result.valid is False
    assert result.open_blocker_count == 0
    assert any("entry_points.handoff_packet_validator" in error for error in result.errors)


def test_validate_promotion_handoff_packet_rejects_missing_adapter_schema_report(
    tmp_path: Path,
) -> None:
    packet_path = tmp_path / "general_agent_promotion_handoff_packet.json"
    payload = json.loads(PACKET_PATH.read_text(encoding="utf-8"))
    payload["required_validation_reports"].remove("capability_adapter_closure_plan_schema_validation ok=true")
    packet_path.write_text(json.dumps(payload), encoding="utf-8")

    result = validate_general_agent_promotion_handoff_packet(packet_path=packet_path)

    assert result.valid is False
    assert result.open_blocker_count == 0
    assert any("required_validation_reports missing" in error for error in result.errors)
    assert any("capability_adapter_closure_plan_schema_validation" in error for error in result.errors)


def test_validate_promotion_handoff_packet_rejects_ready_with_blockers(tmp_path: Path) -> None:
    packet_path = tmp_path / "general_agent_promotion_handoff_packet.json"
    payload = json.loads(PACKET_PATH.read_text(encoding="utf-8"))
    payload["open_blockers"] = ["deployment_upstream_api_gate_not_ready"]
    payload["status"] = "ready_for_final_validation"
    payload["production_promotion"] = "ready"
    packet_path.write_text(json.dumps(payload), encoding="utf-8")

    result = validate_general_agent_promotion_handoff_packet(packet_path=packet_path)

    assert result.valid is False
    assert result.open_blocker_count == 1
    assert any("cannot be ready while open_blockers are present" in error for error in result.errors)


def test_validate_promotion_handoff_packet_rejects_count_drift(tmp_path: Path) -> None:
    packet_path = tmp_path / "general_agent_promotion_handoff_packet.json"
    payload = json.loads(PACKET_PATH.read_text(encoding="utf-8"))
    payload["approval_required_actions"] = 99
    packet_path.write_text(json.dumps(payload), encoding="utf-8")

    result = validate_general_agent_promotion_handoff_packet(packet_path=packet_path)

    assert result.valid is False
    assert result.approval_required_count == 6
    assert any("approval_required_actions must be 6" in error for error in result.errors)
    assert any("approval_required_actions does not match" in error for error in result.errors)


def test_validate_promotion_handoff_packet_rejects_aggregate_count_drift(tmp_path: Path) -> None:
    packet_path = tmp_path / "general_agent_promotion_handoff_packet.json"
    payload = json.loads(PACKET_PATH.read_text(encoding="utf-8"))
    payload["aggregate_closure_actions"] = 99
    packet_path.write_text(json.dumps(payload), encoding="utf-8")

    result = validate_general_agent_promotion_handoff_packet(packet_path=packet_path)

    assert result.valid is False
    assert result.open_blocker_count == 0
    assert any("aggregate_closure_actions must be" in error for error in result.errors)
    assert not any("approval_required_actions does not match" in error for error in result.errors)


def test_validate_promotion_handoff_packet_rejects_capability_count_drift(tmp_path: Path) -> None:
    packet_path = tmp_path / "general_agent_promotion_handoff_packet.json"
    payload = json.loads(PACKET_PATH.read_text(encoding="utf-8"))
    payload["capability_capsules"] = 10
    payload["governed_capabilities"] = 52
    packet_path.write_text(json.dumps(payload), encoding="utf-8")

    result = validate_general_agent_promotion_handoff_packet(packet_path=packet_path)

    assert result.valid is False
    assert result.open_blocker_count == 0
    assert any("capability_capsules must be 13" in error for error in result.errors)
    assert any("governed_capabilities must be 81" in error for error in result.errors)


def test_validate_promotion_handoff_packet_rejects_stale_portfolio_blockers(
    tmp_path: Path,
) -> None:
    packet_path = tmp_path / "general_agent_promotion_handoff_packet.json"
    payload = json.loads(PACKET_PATH.read_text(encoding="utf-8"))
    blockers = payload["approval_required_blockers"]
    blockers.remove("deployment_dns_not_verified")
    blockers.remove("capability_improvement_required:agentic_control.code_change.plan")
    blockers.remove("capability_improvement_required:agentic_control.incident_recovery.plan")
    blockers.extend(
        [
            "voice_dependency_missing:OPENAI_API_KEY",
            "capability_improvement_required:agentic_control.math_algorithm.analyze",
            "capability_improvement_required:agentic_control.mission.define",
        ]
    )
    packet_path.write_text(json.dumps(payload), encoding="utf-8")

    result = validate_general_agent_promotion_handoff_packet(packet_path=packet_path)

    assert result.valid is False
    assert result.approval_required_count == 6
    assert any("approval_required_blockers missing" in error for error in result.errors)
    assert any("approval_required_blockers has unexpected" in error for error in result.errors)


def test_validate_promotion_handoff_packet_cli_outputs_json(capsys) -> None:
    exit_code = main(["--json"])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 0
    assert payload["valid"] is True
    assert payload["packet_id"] == "general-agent-promotion-handoff-v1"
    assert payload["open_blocker_count"] == 0
    assert payload["approval_required_count"] == 6


def test_validate_promotion_handoff_packet_missing_file_error_is_bounded(tmp_path: Path) -> None:
    packet_path = tmp_path / "secret-packet-path.json"

    result = validate_general_agent_promotion_handoff_packet(packet_path=packet_path)
    serialized_errors = json.dumps(result.errors, sort_keys=True)

    assert result.valid is False
    assert "handoff packet could not be read" in result.errors
    assert "secret-packet-path" not in serialized_errors


def test_validate_promotion_handoff_packet_json_parse_error_is_bounded(tmp_path: Path) -> None:
    packet_path = tmp_path / "handoff-packet.json"
    packet_path.write_text('{"packet_id": "secret-json-token"', encoding="utf-8")

    result = validate_general_agent_promotion_handoff_packet(packet_path=packet_path)
    serialized_errors = json.dumps(result.errors, sort_keys=True)

    assert result.valid is False
    assert "handoff packet must be JSON" in result.errors
    assert "secret-json-token" not in serialized_errors


def test_validate_promotion_handoff_packet_rejects_nonfinite_json_constants(tmp_path: Path) -> None:
    packet_path = tmp_path / "handoff-packet.json"
    packet_path.write_text('{"packet_id": "general-agent-promotion-handoff-v1", "score": Infinity}', encoding="utf-8")

    result = validate_general_agent_promotion_handoff_packet(packet_path=packet_path)
    serialized_errors = json.dumps(result.errors, sort_keys=True)

    assert result.valid is False
    assert "handoff packet must be JSON" in result.errors
    assert "Infinity" not in serialized_errors
