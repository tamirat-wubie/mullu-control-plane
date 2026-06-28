"""Forge live-runtime evidence collection packet validator tests.

Purpose: verify the Forge live-runtime evidence collection packet remains
local-only planning evidence and cannot claim runtime authority or collected
evidence.
Governance scope: evidence collection status, readiness gate binding,
production authority denial, commit denial, external-effect denial, and fixture
drift rejection.
Dependencies: scripts.validate_forge_live_runtime_evidence_collection_packet.
Invariants:
  - The Foundation fixture is deterministic and schema-backed.
  - Evidence remains not collected.
  - Runtime, production, commit, external-effect, and terminal closure
    authority remain false.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from gateway.forge_state_write_admission import build_foundation_forge_live_runtime_evidence_collection_packet
from scripts.validate_forge_live_runtime_evidence_collection_packet import (
    DEFAULT_PACKET,
    DEFAULT_SCHEMA,
    validate_forge_live_runtime_evidence_collection_packet,
)
from scripts.validate_schemas import _load_schema, _validate_schema_instance


def test_checked_in_forge_live_runtime_evidence_collection_packet_is_valid() -> None:
    validation, produced_packet = validate_forge_live_runtime_evidence_collection_packet()

    assert validation.ok is True
    assert validation.errors == ()
    assert validation.packet_id == "forge-live-runtime-evidence-collection-packet.v1"
    assert validation.collection_status == "not_started"
    assert validation.evidence_count == 10
    assert validation.blocked_reason_count == 10
    assert produced_packet["disallowed_authority"]["commit_allowed"] is False
    assert produced_packet["disallowed_authority"]["state_write_runtime_registered"] is False


def test_produced_evidence_collection_packet_matches_schema() -> None:
    packet = build_foundation_forge_live_runtime_evidence_collection_packet()
    errors = _validate_schema_instance(_load_schema(DEFAULT_SCHEMA), packet)

    assert errors == []
    assert packet["solver_outcome"] == "AwaitingEvidence"
    assert packet["collection_status"] == "not_started"
    assert all(item["collection_status"] == "not_collected" for item in packet["evidence_items"])
    assert all(item["collected"] is False for item in packet["evidence_items"])


def test_validator_rejects_collected_evidence_overclaim(tmp_path: Path) -> None:
    packet = _load_packet()
    packet["evidence_items"][0]["collection_status"] = "collected"
    packet["evidence_items"][0]["collected"] = True
    packet_path = _write_packet(tmp_path, packet)

    validation, _produced_packet = validate_forge_live_runtime_evidence_collection_packet(
        schema_path=DEFAULT_SCHEMA,
        packet_path=packet_path,
    )

    assert validation.ok is False
    assert any("managed_key_custody.collection_status" in error for error in validation.errors)
    assert any("managed_key_custody.collected" in error for error in validation.errors)
    assert any("fixture does not match deterministic" in error for error in validation.errors)


def test_validator_rejects_runtime_authority_overclaim(tmp_path: Path) -> None:
    packet = _load_packet()
    packet["disallowed_authority"]["state_write_runtime_registered"] = True
    packet["disallowed_authority"]["commit_allowed"] = True
    packet["disallowed_authority"]["terminal_closure"] = True
    packet_path = _write_packet(tmp_path, packet)

    validation, _produced_packet = validate_forge_live_runtime_evidence_collection_packet(
        schema_path=DEFAULT_SCHEMA,
        packet_path=packet_path,
    )

    assert validation.ok is False
    assert any("state_write_runtime_registered" in error for error in validation.errors)
    assert any("commit_allowed" in error for error in validation.errors)
    assert any("terminal_closure" in error for error in validation.errors)


def test_validator_rejects_evidence_order_and_blocker_drift(tmp_path: Path) -> None:
    packet = _load_packet()
    evidence_items = packet["evidence_items"]
    packet["evidence_items"] = [evidence_items[1], evidence_items[0], *evidence_items[2:]]
    packet["blocked_reasons"] = packet["blocked_reasons"][1:]
    packet_path = _write_packet(tmp_path, packet)

    validation, _produced_packet = validate_forge_live_runtime_evidence_collection_packet(
        schema_path=DEFAULT_SCHEMA,
        packet_path=packet_path,
    )

    assert validation.ok is False
    assert any("evidence_items order drift" in error for error in validation.errors)
    assert any("blocked_reasons drift" in error for error in validation.errors)
    assert any("fixture does not match deterministic" in error for error in validation.errors)


def test_validator_rejects_source_readiness_gate_hash_drift(tmp_path: Path) -> None:
    packet = _load_packet()
    packet["source_readiness_gate_hash"] = "0" * 64
    packet_path = _write_packet(tmp_path, packet)

    validation, _produced_packet = validate_forge_live_runtime_evidence_collection_packet(
        schema_path=DEFAULT_SCHEMA,
        packet_path=packet_path,
    )

    assert validation.ok is False
    assert any("source_readiness_gate_hash mismatch" in error for error in validation.errors)
    assert any("fixture does not match deterministic" in error for error in validation.errors)


def _load_packet() -> dict[str, Any]:
    return json.loads(DEFAULT_PACKET.read_text(encoding="utf-8"))


def _write_packet(tmp_path: Path, packet: dict[str, Any]) -> Path:
    packet_path = tmp_path / "forge_live_runtime_evidence_collection_packet.foundation.json"
    packet_path.write_text(json.dumps(packet, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return packet_path
