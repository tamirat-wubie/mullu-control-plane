"""Forge live-runtime approved probe output packet validator tests.

Purpose: verify approved live probe outputs remain absent until operator
approval, dependency evidence, recovery evidence, isolation evidence, and a
signed receipt writer exist.
Governance scope: approved probe output intake, signed receipt population
denial, runtime authority denial, source probe admission binding, and fixture
drift rejection.
Dependencies: scripts.validate_forge_live_runtime_approved_probe_output_packet.
Invariants:
  - The Foundation fixture is deterministic and schema-backed.
  - Approved probe outputs remain absent.
  - Signed receipt population remains disallowed.
  - Runtime, production, commit, external-effect, and terminal closure
    authority remain false.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from gateway.forge_state_write_admission import build_foundation_forge_live_runtime_approved_probe_output_packet
from scripts.validate_forge_live_runtime_approved_probe_output_packet import (
    DEFAULT_PACKET,
    DEFAULT_SCHEMA,
    validate_forge_live_runtime_approved_probe_output_packet,
)
from scripts.validate_schemas import _load_schema, _validate_schema_instance


def test_checked_in_forge_live_runtime_approved_probe_output_packet_is_valid() -> None:
    validation, produced_packet = validate_forge_live_runtime_approved_probe_output_packet()

    assert validation.ok is True
    assert validation.errors == ()
    assert validation.packet_id == "forge-live-runtime-approved-probe-output-packet.v1"
    assert validation.output_intake_status == "blocked_awaiting_approved_probe_outputs"
    assert validation.probe_output_count == 10
    assert validation.blocked_reason_count == 10
    assert produced_packet["approved_probe_outputs_present"] is False
    assert produced_packet["signed_receipt_population_allowed"] is False
    assert produced_packet["runtime_authority_effect"] is False


def test_produced_approved_probe_output_packet_matches_schema() -> None:
    packet = build_foundation_forge_live_runtime_approved_probe_output_packet()
    errors = _validate_schema_instance(_load_schema(DEFAULT_SCHEMA), packet)

    assert errors == []
    assert packet["output_intake_mode"] == "approved_probe_outputs_required"
    assert len(packet["probe_outputs"]) == 10
    assert all(item["output_status"] == "missing" for item in packet["probe_outputs"])
    assert all(item["verification_status"] == "not_verified" for item in packet["probe_outputs"])


def test_validator_rejects_probe_output_presence_overclaim(tmp_path: Path) -> None:
    packet = _load_packet()
    item = packet["probe_outputs"][0]
    item["approved_probe_output_ref"] = "probe-output://forge/live-runtime/managed-key-custody"
    item["approved_probe_output_hash"] = "a" * 64
    item["output_status"] = "present"
    packet_path = _write_packet(tmp_path, packet)

    validation, _produced_packet = validate_forge_live_runtime_approved_probe_output_packet(
        schema_path=DEFAULT_SCHEMA,
        packet_path=packet_path,
    )

    assert validation.ok is False
    assert any("managed_key_custody.approved_probe_output_ref" in error for error in validation.errors)
    assert any("managed_key_custody.approved_probe_output_hash" in error for error in validation.errors)
    assert any("managed_key_custody.output_status" in error for error in validation.errors)


def test_validator_rejects_required_evidence_ref_overclaim(tmp_path: Path) -> None:
    packet = _load_packet()
    item = packet["probe_outputs"][0]
    item["operator_approval_ref"] = "approval://forge/live-runtime/managed-key-custody"
    item["dependency_or_credential_probe_output_ref"] = "dependency-probe://forge/live-runtime/managed-key-custody"
    item["recovery_or_revocation_output_ref"] = "recovery://forge/live-runtime/managed-key-custody"
    item["sandbox_or_isolation_evidence_ref"] = "sandbox://forge/live-runtime/managed-key-custody"
    item["signed_receipt_writer_ref"] = "receipt-writer://forge/live-runtime/managed-key-custody"
    packet_path = _write_packet(tmp_path, packet)

    validation, _produced_packet = validate_forge_live_runtime_approved_probe_output_packet(
        schema_path=DEFAULT_SCHEMA,
        packet_path=packet_path,
    )

    assert validation.ok is False
    assert any("managed_key_custody.operator_approval_ref" in error for error in validation.errors)
    assert any("managed_key_custody.dependency_or_credential_probe_output_ref" in error for error in validation.errors)
    assert any("managed_key_custody.recovery_or_revocation_output_ref" in error for error in validation.errors)
    assert any("managed_key_custody.signed_receipt_writer_ref" in error for error in validation.errors)


def test_validator_rejects_top_level_output_intake_overclaim(tmp_path: Path) -> None:
    packet = _load_packet()
    packet["approved_probe_outputs_present"] = True
    packet["signed_receipt_population_allowed"] = True
    packet["runtime_authority_effect"] = True
    packet_path = _write_packet(tmp_path, packet)

    validation, _produced_packet = validate_forge_live_runtime_approved_probe_output_packet(
        schema_path=DEFAULT_SCHEMA,
        packet_path=packet_path,
    )

    assert validation.ok is False
    assert any("approved_probe_outputs_present" in error for error in validation.errors)
    assert any("signed_receipt_population_allowed" in error for error in validation.errors)
    assert any("runtime_authority_effect" in error for error in validation.errors)


def test_validator_rejects_runtime_authority_overclaim(tmp_path: Path) -> None:
    packet = _load_packet()
    packet["disallowed_authority"]["state_write_runtime_registered"] = True
    packet["disallowed_authority"]["commit_allowed"] = True
    packet["disallowed_authority"]["terminal_closure"] = True
    packet_path = _write_packet(tmp_path, packet)

    validation, _produced_packet = validate_forge_live_runtime_approved_probe_output_packet(
        schema_path=DEFAULT_SCHEMA,
        packet_path=packet_path,
    )

    assert validation.ok is False
    assert any("state_write_runtime_registered" in error for error in validation.errors)
    assert any("commit_allowed" in error for error in validation.errors)
    assert any("terminal_closure" in error for error in validation.errors)


def test_validator_rejects_order_and_blocker_drift(tmp_path: Path) -> None:
    packet = _load_packet()
    items = packet["probe_outputs"]
    packet["probe_outputs"] = [items[1], items[0], *items[2:]]
    packet["blocked_reasons"] = packet["blocked_reasons"][1:]
    packet_path = _write_packet(tmp_path, packet)

    validation, _produced_packet = validate_forge_live_runtime_approved_probe_output_packet(
        schema_path=DEFAULT_SCHEMA,
        packet_path=packet_path,
    )

    assert validation.ok is False
    assert any("probe_outputs order drift" in error for error in validation.errors)
    assert any("blocked_reasons drift" in error for error in validation.errors)
    assert any("fixture does not match deterministic" in error for error in validation.errors)


def test_validator_rejects_source_probe_admission_packet_hash_drift(tmp_path: Path) -> None:
    packet = _load_packet()
    packet["source_probe_admission_packet_hash"] = "0" * 64
    packet_path = _write_packet(tmp_path, packet)

    validation, _produced_packet = validate_forge_live_runtime_approved_probe_output_packet(
        schema_path=DEFAULT_SCHEMA,
        packet_path=packet_path,
    )

    assert validation.ok is False
    assert any("source_probe_admission_packet_hash mismatch" in error for error in validation.errors)
    assert any("fixture does not match deterministic" in error for error in validation.errors)


def _load_packet() -> dict[str, Any]:
    return json.loads(DEFAULT_PACKET.read_text(encoding="utf-8"))


def _write_packet(tmp_path: Path, packet: dict[str, Any]) -> Path:
    packet_path = tmp_path / "forge_live_runtime_approved_probe_output_packet.foundation.json"
    packet_path.write_text(json.dumps(packet, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return packet_path
