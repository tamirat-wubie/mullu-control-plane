"""Forge live-runtime probe admission packet validator tests.

Purpose: verify live probes stay blocked until operator approval and all
bounded live-evidence inputs exist.
Governance scope: operator approval, probe execution, signed receipt
population, external-effect denial, source signed receipt binding, and fixture
drift rejection.
Dependencies: scripts.validate_forge_live_runtime_probe_admission_packet.
Invariants:
  - The Foundation fixture is deterministic and schema-backed.
  - Probe execution remains blocked.
  - External effects are not requested.
  - Signed receipt population remains disallowed.
  - Runtime, production, commit, external-effect, and terminal closure
    authority remain false.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from gateway.forge_state_write_admission import build_foundation_forge_live_runtime_probe_admission_packet
from scripts.validate_forge_live_runtime_probe_admission_packet import (
    DEFAULT_PACKET,
    DEFAULT_SCHEMA,
    validate_forge_live_runtime_probe_admission_packet,
)
from scripts.validate_schemas import _load_schema, _validate_schema_instance


def test_checked_in_forge_live_runtime_probe_admission_packet_is_valid() -> None:
    validation, produced_packet = validate_forge_live_runtime_probe_admission_packet()

    assert validation.ok is True
    assert validation.errors == ()
    assert validation.packet_id == "forge-live-runtime-probe-admission-packet.v1"
    assert validation.admission_status == "blocked_awaiting_operator_approval"
    assert validation.probe_item_count == 10
    assert validation.blocked_reason_count == 10
    assert produced_packet["solver_outcome"] == "AwaitingEvidence"
    assert produced_packet["disallowed_authority"]["commit_allowed"] is False


def test_produced_probe_admission_packet_matches_schema() -> None:
    packet = build_foundation_forge_live_runtime_probe_admission_packet()
    errors = _validate_schema_instance(_load_schema(DEFAULT_SCHEMA), packet)

    assert errors == []
    assert packet["admission_mode"] == "operator_approved_live_probe_required"
    assert len(packet["probe_items"]) == 10
    assert all(item["probe_execution_allowed"] is False for item in packet["probe_items"])
    assert all(item["external_effects_requested"] is False for item in packet["probe_items"])


def test_validator_rejects_operator_approval_and_execution_overclaim(tmp_path: Path) -> None:
    packet = _load_packet()
    item = packet["probe_items"][0]
    item["operator_approval_status"] = "approved"
    item["probe_admission_status"] = "admitted"
    item["probe_execution_allowed"] = True
    packet_path = _write_packet(tmp_path, packet)

    validation, _produced_packet = validate_forge_live_runtime_probe_admission_packet(
        schema_path=DEFAULT_SCHEMA,
        packet_path=packet_path,
    )

    assert validation.ok is False
    assert any("managed_key_custody.operator_approval_status" in error for error in validation.errors)
    assert any("managed_key_custody.probe_admission_status" in error for error in validation.errors)
    assert any("managed_key_custody.probe_execution_allowed" in error for error in validation.errors)


def test_validator_rejects_external_effect_and_population_overclaim(tmp_path: Path) -> None:
    packet = _load_packet()
    item = packet["probe_items"][0]
    item["external_effects_requested"] = True
    item["signed_receipt_population_allowed"] = True
    item["authority_effect"] = True
    packet_path = _write_packet(tmp_path, packet)

    validation, _produced_packet = validate_forge_live_runtime_probe_admission_packet(
        schema_path=DEFAULT_SCHEMA,
        packet_path=packet_path,
    )

    assert validation.ok is False
    assert any("managed_key_custody.external_effects_requested" in error for error in validation.errors)
    assert any("managed_key_custody.signed_receipt_population_allowed" in error for error in validation.errors)
    assert any("managed_key_custody.authority_effect" in error for error in validation.errors)


def test_validator_rejects_required_input_drift(tmp_path: Path) -> None:
    packet = _load_packet()
    packet["probe_items"][0]["required_inputs"] = ["operator_approval"]
    packet_path = _write_packet(tmp_path, packet)

    validation, _produced_packet = validate_forge_live_runtime_probe_admission_packet(
        schema_path=DEFAULT_SCHEMA,
        packet_path=packet_path,
    )

    assert validation.ok is False
    assert any("managed_key_custody.required_inputs" in error for error in validation.errors)
    assert any("fixture does not match deterministic" in error for error in validation.errors)


def test_validator_rejects_runtime_authority_overclaim(tmp_path: Path) -> None:
    packet = _load_packet()
    packet["disallowed_authority"]["state_write_runtime_registered"] = True
    packet["disallowed_authority"]["commit_allowed"] = True
    packet["disallowed_authority"]["terminal_closure"] = True
    packet_path = _write_packet(tmp_path, packet)

    validation, _produced_packet = validate_forge_live_runtime_probe_admission_packet(
        schema_path=DEFAULT_SCHEMA,
        packet_path=packet_path,
    )

    assert validation.ok is False
    assert any("state_write_runtime_registered" in error for error in validation.errors)
    assert any("commit_allowed" in error for error in validation.errors)
    assert any("terminal_closure" in error for error in validation.errors)


def test_validator_rejects_order_and_blocker_drift(tmp_path: Path) -> None:
    packet = _load_packet()
    items = packet["probe_items"]
    packet["probe_items"] = [items[1], items[0], *items[2:]]
    packet["blocked_reasons"] = packet["blocked_reasons"][1:]
    packet_path = _write_packet(tmp_path, packet)

    validation, _produced_packet = validate_forge_live_runtime_probe_admission_packet(
        schema_path=DEFAULT_SCHEMA,
        packet_path=packet_path,
    )

    assert validation.ok is False
    assert any("probe_items order drift" in error for error in validation.errors)
    assert any("blocked_reasons drift" in error for error in validation.errors)
    assert any("fixture does not match deterministic" in error for error in validation.errors)


def test_validator_rejects_source_signed_receipt_hash_drift(tmp_path: Path) -> None:
    packet = _load_packet()
    packet["source_signed_evidence_receipt_hash"] = "0" * 64
    packet_path = _write_packet(tmp_path, packet)

    validation, _produced_packet = validate_forge_live_runtime_probe_admission_packet(
        schema_path=DEFAULT_SCHEMA,
        packet_path=packet_path,
    )

    assert validation.ok is False
    assert any("source_signed_evidence_receipt_hash mismatch" in error for error in validation.errors)
    assert any("fixture does not match deterministic" in error for error in validation.errors)


def _load_packet() -> dict[str, Any]:
    return json.loads(DEFAULT_PACKET.read_text(encoding="utf-8"))


def _write_packet(tmp_path: Path, packet: dict[str, Any]) -> Path:
    packet_path = tmp_path / "forge_live_runtime_probe_admission_packet.foundation.json"
    packet_path.write_text(json.dumps(packet, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return packet_path
