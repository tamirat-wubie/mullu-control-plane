"""General-agent promotion handoff packet validation tests."""

from __future__ import annotations

import json
from pathlib import Path

from scripts.validate_general_agent_promotion_handoff_packet import (
    main,
    validate_general_agent_promotion_handoff_packet,
)


PACKET_PATH = Path("examples") / "general_agent_promotion_handoff_packet.json"


def test_validate_promotion_handoff_packet_accepts_example() -> None:
    result = validate_general_agent_promotion_handoff_packet()

    assert result.valid is True
    assert result.packet_id == "general-agent-promotion-handoff-v1"
    assert result.open_blocker_count == 6
    assert result.approval_required_count == 4
    assert result.errors == ()


def test_validate_promotion_handoff_packet_rejects_missing_entry_point(tmp_path: Path) -> None:
    packet_path = tmp_path / "general_agent_promotion_handoff_packet.json"
    payload = json.loads(PACKET_PATH.read_text(encoding="utf-8"))
    payload["entry_points"]["handoff_packet_validator"] = "scripts/unknown.py"
    packet_path.write_text(json.dumps(payload), encoding="utf-8")

    result = validate_general_agent_promotion_handoff_packet(packet_path=packet_path)

    assert result.valid is False
    assert result.open_blocker_count == 6
    assert any("entry_points.handoff_packet_validator" in error for error in result.errors)


def test_validate_promotion_handoff_packet_rejects_ready_with_blockers(tmp_path: Path) -> None:
    packet_path = tmp_path / "general_agent_promotion_handoff_packet.json"
    payload = json.loads(PACKET_PATH.read_text(encoding="utf-8"))
    payload["production_promotion"] = "ready"
    packet_path.write_text(json.dumps(payload), encoding="utf-8")

    result = validate_general_agent_promotion_handoff_packet(packet_path=packet_path)

    assert result.valid is False
    assert result.open_blocker_count == 6
    assert any("production_promotion must be 'blocked'" in error for error in result.errors)
    assert any("cannot be ready while open_blockers are present" in error for error in result.errors)


def test_validate_promotion_handoff_packet_rejects_count_drift(tmp_path: Path) -> None:
    packet_path = tmp_path / "general_agent_promotion_handoff_packet.json"
    payload = json.loads(PACKET_PATH.read_text(encoding="utf-8"))
    payload["approval_required_actions"] = 99
    packet_path.write_text(json.dumps(payload), encoding="utf-8")

    result = validate_general_agent_promotion_handoff_packet(packet_path=packet_path)

    assert result.valid is False
    assert result.approval_required_count == 4
    assert any("approval_required_actions must be 4" in error for error in result.errors)
    assert any("approval_required_actions does not match" in error for error in result.errors)


def test_validate_promotion_handoff_packet_cli_outputs_json(capsys) -> None:
    exit_code = main(["--json"])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 0
    assert payload["valid"] is True
    assert payload["packet_id"] == "general-agent-promotion-handoff-v1"
    assert payload["open_blocker_count"] == 6
    assert payload["approval_required_count"] == 4
