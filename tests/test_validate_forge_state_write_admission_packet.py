"""Forge state-write admission packet validator tests.

Purpose: verify the schema-backed packet validator fails closed on drift from
the deterministic non-mutating Forge admission adapter.
Governance scope: admission packet receipt integrity, stage order, certificate
field order, production denial, and Foundation Mode authority limits.
Dependencies: scripts.validate_forge_state_write_admission_packet.
Invariants:
  - The checked-in fixture matches the deterministic adapter output.
  - Packet drift, receipt overclaim, stage reorder, and certificate drift are
    rejected before governance preflight can pass.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from scripts.validate_forge_state_write_admission_packet import (
    DEFAULT_PACKET,
    DEFAULT_SCHEMA,
    validate_forge_state_write_admission_packet,
)


def test_checked_in_forge_state_write_admission_packet_is_valid() -> None:
    validation, produced_packet = validate_forge_state_write_admission_packet()

    assert validation.ok is True
    assert validation.errors == ()
    assert validation.adapter_id == "forge-state-write-admission.v1"
    assert validation.bridge_ref == "forge_write_spine_bridge.v1"
    assert validation.admission_decision == "allow_prepare_model"
    assert validation.blocked_reason_count == 0
    assert produced_packet["receipt"]["commit_allowed"] is False


def test_validator_rejects_commit_overclaim(tmp_path: Path) -> None:
    packet = _load_packet()
    packet["receipt"]["commit_allowed"] = True
    packet["invariants"]["commit_allowed"] = True
    packet_path = _write_packet(tmp_path, packet)

    validation, _produced_packet = validate_forge_state_write_admission_packet(
        schema_path=DEFAULT_SCHEMA,
        packet_path=packet_path,
    )

    assert validation.ok is False
    assert any("commit_allowed" in error for error in validation.errors)
    assert any("fixture does not match deterministic" in error for error in validation.errors)
    assert validation.admission_decision == "allow_prepare_model"


def test_validator_rejects_stage_reorder(tmp_path: Path) -> None:
    packet = _load_packet()
    stages = packet["request"]["stages"]
    packet["request"]["stages"] = [stages[1], stages[0], *stages[2:]]
    packet_path = _write_packet(tmp_path, packet)

    validation, _produced_packet = validate_forge_state_write_admission_packet(
        schema_path=DEFAULT_SCHEMA,
        packet_path=packet_path,
    )

    assert validation.ok is False
    assert any("stage order drift" in error for error in validation.errors)
    assert any("fixture does not match deterministic" in error for error in validation.errors)


def test_validator_rejects_certificate_field_drift(tmp_path: Path) -> None:
    packet = _load_packet()
    required_fields = packet["request"]["certificate"]["required_fields"]
    packet["request"]["certificate"]["required_fields"] = list(reversed(required_fields))
    packet_path = _write_packet(tmp_path, packet)

    validation, _produced_packet = validate_forge_state_write_admission_packet(
        schema_path=DEFAULT_SCHEMA,
        packet_path=packet_path,
    )

    assert validation.ok is False
    assert any("certificate required field order drift" in error for error in validation.errors)
    assert any("fixture does not match deterministic" in error for error in validation.errors)


def test_validator_rejects_production_authority_claim(tmp_path: Path) -> None:
    packet = _load_packet()
    packet["request"]["service_boundary"]["production_authorized"] = True
    packet["receipt"]["production_authorized"] = True
    packet["invariants"]["production_authorized"] = True
    packet_path = _write_packet(tmp_path, packet)

    validation, _produced_packet = validate_forge_state_write_admission_packet(
        schema_path=DEFAULT_SCHEMA,
        packet_path=packet_path,
    )

    assert validation.ok is False
    assert any("production_authorized" in error for error in validation.errors)
    assert any("fixture does not match deterministic" in error for error in validation.errors)


def _load_packet() -> dict[str, Any]:
    return json.loads(DEFAULT_PACKET.read_text(encoding="utf-8"))


def _write_packet(tmp_path: Path, packet: dict[str, Any]) -> Path:
    packet_path = tmp_path / "forge_state_write_admission_packet.foundation.json"
    packet_path.write_text(json.dumps(packet, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return packet_path
