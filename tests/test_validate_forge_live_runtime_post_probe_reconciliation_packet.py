"""Forge live-runtime post-probe reconciliation packet validator tests.

Purpose: verify approved probe outputs remain required before signed evidence
receipt updates can be reconciled.
Governance scope: approved probe output presence, signed receipt update
admission, runtime authority denial, source probe packet binding, and fixture
drift rejection.
Dependencies: scripts.validate_forge_live_runtime_post_probe_reconciliation_packet.
Invariants:
  - The Foundation fixture is deterministic and schema-backed.
  - Probe outputs remain absent.
  - Signed receipt updates remain blocked.
  - Runtime, production, commit, external-effect, and terminal closure
    authority remain false.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from gateway.forge_state_write_admission import (
    build_foundation_forge_live_runtime_post_probe_reconciliation_packet,
)
from scripts.validate_forge_live_runtime_post_probe_reconciliation_packet import (
    DEFAULT_PACKET,
    DEFAULT_SCHEMA,
    validate_forge_live_runtime_post_probe_reconciliation_packet,
)
from scripts.validate_schemas import _load_schema, _validate_schema_instance


def test_checked_in_forge_live_runtime_post_probe_reconciliation_packet_is_valid() -> None:
    validation, produced_packet = validate_forge_live_runtime_post_probe_reconciliation_packet()

    assert validation.ok is True
    assert validation.errors == ()
    assert validation.packet_id == "forge-live-runtime-post-probe-reconciliation-packet.v1"
    assert validation.reconciliation_status == "blocked_awaiting_approved_probe_outputs"
    assert validation.reconciliation_item_count == 10
    assert validation.blocked_reason_count == 10
    assert produced_packet["solver_outcome"] == "AwaitingEvidence"
    assert produced_packet["probe_outputs_present"] is False
    assert produced_packet["signed_receipt_updates_allowed"] is False


def test_produced_post_probe_reconciliation_packet_matches_schema() -> None:
    packet = build_foundation_forge_live_runtime_post_probe_reconciliation_packet()
    errors = _validate_schema_instance(_load_schema(DEFAULT_SCHEMA), packet)

    assert errors == []
    assert packet["reconciliation_mode"] == "approved_probe_output_reconciliation_required"
    assert len(packet["reconciliation_items"]) == 10
    assert all(item["probe_output_status"] == "missing" for item in packet["reconciliation_items"])
    assert all(item["signed_receipt_update_status"] == "blocked" for item in packet["reconciliation_items"])


def test_validator_rejects_probe_output_overclaim(tmp_path: Path) -> None:
    packet = _load_packet()
    item = packet["reconciliation_items"][0]
    item["probe_output_status"] = "present"
    item["probe_output_ref"] = "probe-output://forge/live-runtime/managed-key-custody"
    item["probe_output_hash"] = "a" * 64
    packet_path = _write_packet(tmp_path, packet)

    validation, _produced_packet = validate_forge_live_runtime_post_probe_reconciliation_packet(
        schema_path=DEFAULT_SCHEMA,
        packet_path=packet_path,
    )

    assert validation.ok is False
    assert any("managed_key_custody.probe_output_status" in error for error in validation.errors)
    assert any("managed_key_custody.probe_output_ref" in error for error in validation.errors)
    assert any("managed_key_custody.probe_output_hash" in error for error in validation.errors)


def test_validator_rejects_signed_receipt_update_overclaim(tmp_path: Path) -> None:
    packet = _load_packet()
    item = packet["reconciliation_items"][0]
    item["signed_receipt_update_status"] = "ready"
    item["signed_receipt_update_ref"] = "receipt-update://forge/live-runtime/managed-key-custody"
    item["reconciliation_status"] = "ready"
    packet_path = _write_packet(tmp_path, packet)

    validation, _produced_packet = validate_forge_live_runtime_post_probe_reconciliation_packet(
        schema_path=DEFAULT_SCHEMA,
        packet_path=packet_path,
    )

    assert validation.ok is False
    assert any("managed_key_custody.signed_receipt_update_status" in error for error in validation.errors)
    assert any("managed_key_custody.signed_receipt_update_ref" in error for error in validation.errors)
    assert any("managed_key_custody.reconciliation_status" in error for error in validation.errors)


def test_validator_rejects_top_level_reconciliation_overclaim(tmp_path: Path) -> None:
    packet = _load_packet()
    packet["probe_outputs_present"] = True
    packet["signed_receipt_updates_allowed"] = True
    packet["runtime_authority_effect"] = True
    packet_path = _write_packet(tmp_path, packet)

    validation, _produced_packet = validate_forge_live_runtime_post_probe_reconciliation_packet(
        schema_path=DEFAULT_SCHEMA,
        packet_path=packet_path,
    )

    assert validation.ok is False
    assert any("probe_outputs_present" in error for error in validation.errors)
    assert any("signed_receipt_updates_allowed" in error for error in validation.errors)
    assert any("runtime_authority_effect" in error for error in validation.errors)


def test_validator_rejects_runtime_authority_overclaim(tmp_path: Path) -> None:
    packet = _load_packet()
    packet["disallowed_authority"]["live_runtime_authorized"] = True
    packet["disallowed_authority"]["commit_allowed"] = True
    packet["disallowed_authority"]["terminal_closure"] = True
    packet_path = _write_packet(tmp_path, packet)

    validation, _produced_packet = validate_forge_live_runtime_post_probe_reconciliation_packet(
        schema_path=DEFAULT_SCHEMA,
        packet_path=packet_path,
    )

    assert validation.ok is False
    assert any("live_runtime_authorized" in error for error in validation.errors)
    assert any("commit_allowed" in error for error in validation.errors)
    assert any("terminal_closure" in error for error in validation.errors)


def test_validator_rejects_order_and_blocker_drift(tmp_path: Path) -> None:
    packet = _load_packet()
    items = packet["reconciliation_items"]
    packet["reconciliation_items"] = [items[1], items[0], *items[2:]]
    packet["blocked_reasons"] = packet["blocked_reasons"][1:]
    packet_path = _write_packet(tmp_path, packet)

    validation, _produced_packet = validate_forge_live_runtime_post_probe_reconciliation_packet(
        schema_path=DEFAULT_SCHEMA,
        packet_path=packet_path,
    )

    assert validation.ok is False
    assert any("reconciliation_items order drift" in error for error in validation.errors)
    assert any("blocked_reasons drift" in error for error in validation.errors)
    assert any("fixture does not match deterministic" in error for error in validation.errors)


def test_validator_rejects_source_approved_probe_output_packet_hash_drift(tmp_path: Path) -> None:
    packet = _load_packet()
    packet["source_approved_probe_output_packet_hash"] = "0" * 64
    packet_path = _write_packet(tmp_path, packet)

    validation, _produced_packet = validate_forge_live_runtime_post_probe_reconciliation_packet(
        schema_path=DEFAULT_SCHEMA,
        packet_path=packet_path,
    )

    assert validation.ok is False
    assert any("source_approved_probe_output_packet_hash mismatch" in error for error in validation.errors)
    assert any("fixture does not match deterministic" in error for error in validation.errors)


def _load_packet() -> dict[str, Any]:
    return json.loads(DEFAULT_PACKET.read_text(encoding="utf-8"))


def _write_packet(tmp_path: Path, packet: dict[str, Any]) -> Path:
    packet_path = tmp_path / "forge_live_runtime_post_probe_reconciliation_packet.foundation.json"
    packet_path.write_text(json.dumps(packet, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return packet_path
