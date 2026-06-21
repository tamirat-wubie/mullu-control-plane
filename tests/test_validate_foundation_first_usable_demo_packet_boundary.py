from __future__ import annotations

import copy
import json
from pathlib import Path

from scripts.validate_first_usable_demo_packet import (
    DEFAULT_PACKET,
    validate_first_usable_demo_packet,
)


def _load_default_packet() -> dict:
    return json.loads(DEFAULT_PACKET.read_text(encoding="utf-8"))


def _write_packet(tmp_path: Path, packet: dict) -> Path:
    packet_path = tmp_path / "first_usable_demo_packet.json"
    packet_path.write_text(json.dumps(packet, indent=2, sort_keys=True), encoding="utf-8")
    return packet_path


def test_default_first_usable_demo_packet_validates() -> None:
    validation = validate_first_usable_demo_packet()

    assert validation.valid, validation.errors
    assert validation.packet_id == "first_usable_demo_packet_v1"
    assert validation.solver_outcome == "SolvedVerified"


def test_validator_rejects_execution_authority(tmp_path: Path) -> None:
    packet = _load_default_packet()
    packet["current_authority"] = copy.deepcopy(packet["current_authority"])
    packet["current_authority"]["execution_allowed"] = True

    validation = validate_first_usable_demo_packet(packet_path=_write_packet(tmp_path, packet))

    assert not validation.valid
    assert "current_authority.execution_allowed must be false" in validation.errors


def test_validator_rejects_live_connector_readiness_claim(tmp_path: Path) -> None:
    packet = _load_default_packet()
    packet["readiness_index"] = copy.deepcopy(packet["readiness_index"])
    packet["readiness_index"]["live_connector"] = "ready"

    validation = validate_first_usable_demo_packet(packet_path=_write_packet(tmp_path, packet))

    assert not validation.valid
    assert "readiness_index.live_connector must remain blocked" in validation.errors


def test_validator_rejects_secret_like_values(tmp_path: Path) -> None:
    packet = _load_default_packet()
    packet["next_safe_actions"] = list(packet["next_safe_actions"])
    packet["next_safe_actions"].append("Bearer secret-worker-key-value")

    validation = validate_first_usable_demo_packet(packet_path=_write_packet(tmp_path, packet))

    assert not validation.valid
    assert any(error.endswith("contains secret-like value") for error in validation.errors)
