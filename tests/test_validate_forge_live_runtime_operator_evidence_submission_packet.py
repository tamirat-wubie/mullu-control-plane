"""Forge live-runtime operator evidence submission packet validator tests.

Purpose: verify the Forge live-runtime operator evidence submission packet
admits only redacted evidence references and never grants runtime authority.
Governance scope: submitted evidence refs, secret exclusion, authority denial,
source request binding, fixture drift rejection, and future submitted packets.
Dependencies: scripts.validate_forge_live_runtime_operator_evidence_submission_packet.
Invariants:
  - The Foundation fixture is deterministic and schema-backed.
  - Raw secret values are rejected.
  - Runtime, production, commit, external-effect, and terminal closure
    authority remain false.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from gateway.forge_state_write_admission import (
    LIVE_RUNTIME_OPERATOR_REQUIRED_EVIDENCE_CLASSES,
    REQUIRED_LIVE_RUNTIME_EVIDENCE_IDS,
    build_foundation_forge_live_runtime_operator_evidence_submission_packet,
)
from scripts.validate_forge_live_runtime_operator_evidence_submission_packet import (
    DEFAULT_PACKET,
    DEFAULT_SCHEMA,
    validate_forge_live_runtime_operator_evidence_submission_packet,
)
from scripts.validate_schemas import _load_schema, _validate_schema_instance


def test_checked_in_forge_live_runtime_operator_evidence_submission_packet_is_valid() -> None:
    validation, produced_packet = validate_forge_live_runtime_operator_evidence_submission_packet()

    assert validation.ok is True
    assert validation.errors == ()
    assert validation.packet_id == "forge-live-runtime-operator-evidence-submission-packet.v1"
    assert validation.submission_status == "blocked_awaiting_operator_live_evidence_refs"
    assert validation.submission_item_count == 10
    assert validation.submitted_ref_count == 0
    assert validation.required_ref_count == 80
    assert produced_packet["acceptance_allowed"] is False
    assert produced_packet["secret_values_present"] is False


def test_produced_operator_evidence_submission_packet_matches_schema() -> None:
    packet = build_foundation_forge_live_runtime_operator_evidence_submission_packet()
    errors = _validate_schema_instance(_load_schema(DEFAULT_SCHEMA), packet)

    assert errors == []
    assert packet["submission_mode"] == "operator_live_evidence_ref_intake"
    assert len(packet["submission_items"]) == len(REQUIRED_LIVE_RUNTIME_EVIDENCE_IDS)
    assert all(item["submitted_ref_count"] == 0 for item in packet["submission_items"])
    assert all(item["secret_values_present"] is False for item in packet["submission_items"])


def test_validator_accepts_complete_redacted_reference_submission(tmp_path: Path) -> None:
    packet = _load_packet()
    _populate_all_submission_refs(packet)
    packet_path = _write_packet(tmp_path, packet)

    validation, _produced_packet = validate_forge_live_runtime_operator_evidence_submission_packet(
        schema_path=DEFAULT_SCHEMA,
        packet_path=packet_path,
    )

    assert validation.ok is True
    assert validation.errors == ()
    assert validation.submission_status == "submitted_for_validation"
    assert validation.submitted_ref_count == 80
    assert validation.required_ref_count == 80


def test_validator_rejects_secret_and_authority_overclaim(tmp_path: Path) -> None:
    packet = _load_packet()
    packet["secret_values_present"] = True
    packet["runtime_authority_effect"] = True
    packet["acceptance_allowed"] = True
    packet["disallowed_authority"]["state_write_runtime_registered"] = True
    packet["disallowed_authority"]["production_authorized"] = True
    packet["submission_items"][0]["secret_values_present"] = True
    packet["submission_items"][0]["submitted_refs"][0]["secret_value_present"] = True
    packet_path = _write_packet(tmp_path, packet)

    validation, _produced_packet = validate_forge_live_runtime_operator_evidence_submission_packet(
        schema_path=DEFAULT_SCHEMA,
        packet_path=packet_path,
    )

    assert validation.ok is False
    assert any("secret_values_present" in error for error in validation.errors)
    assert any("runtime_authority_effect" in error for error in validation.errors)
    assert any("acceptance_allowed" in error for error in validation.errors)
    assert any("state_write_runtime_registered" in error for error in validation.errors)
    assert any("production_authorized" in error for error in validation.errors)


def test_validator_rejects_partial_submission_overclaim(tmp_path: Path) -> None:
    packet = _load_packet()
    first_item = packet["submission_items"][0]
    first_slot = first_item["submitted_refs"][0]
    first_slot["submitted"] = True
    first_slot["evidence_ref"] = "evidence://forge/live-runtime/managed-key-custody/operator-approval"
    first_slot["ref_hash"] = "sha256:" + "1" * 64
    first_slot["validation_status"] = "submitted_unverified"
    first_item["submitted_ref_count"] = 8
    first_item["all_required_refs_present"] = True
    first_item["submission_status"] = "submitted_for_validation"
    packet["submitted_ref_count"] = 80
    packet["all_required_refs_present"] = True
    packet["submission_status"] = "submitted_for_validation"
    packet["blocked_reasons"] = []
    packet_path = _write_packet(tmp_path, packet)

    validation, _produced_packet = validate_forge_live_runtime_operator_evidence_submission_packet(
        schema_path=DEFAULT_SCHEMA,
        packet_path=packet_path,
    )

    assert validation.ok is False
    assert any("managed_key_custody.submitted_ref_count mismatch" in error for error in validation.errors)
    assert any("managed_key_custody.all_required_refs_present mismatch" in error for error in validation.errors)
    assert any("submitted_ref_count mismatch" in error for error in validation.errors)
    assert any("submission_status must be blocked_awaiting_operator_live_evidence_refs" in error for error in validation.errors)


def test_validator_rejects_source_request_hash_drift(tmp_path: Path) -> None:
    packet = _load_packet()
    packet["source_operator_evidence_request_hash"] = "0" * 64
    packet_path = _write_packet(tmp_path, packet)

    validation, _produced_packet = validate_forge_live_runtime_operator_evidence_submission_packet(
        schema_path=DEFAULT_SCHEMA,
        packet_path=packet_path,
    )

    assert validation.ok is False
    assert any("source_operator_evidence_request_hash mismatch" in error for error in validation.errors)


def _populate_all_submission_refs(packet: dict[str, Any]) -> None:
    submitted_ref_count = 0
    for item in packet["submission_items"]:
        for class_index, slot in enumerate(item["submitted_refs"]):
            evidence_class = LIVE_RUNTIME_OPERATOR_REQUIRED_EVIDENCE_CLASSES[class_index]
            slot["submitted"] = True
            slot["evidence_ref"] = (
                f"evidence://forge/live-runtime/{item['evidence_id'].replace('_', '-')}/{evidence_class}"
            )
            slot["ref_hash"] = "sha256:" + f"{submitted_ref_count + 1:064x}"[-64:]
            slot["validation_status"] = "submitted_unverified"
            slot["blocker_reason"] = f"{item['evidence_id']}_{evidence_class}_missing"
            submitted_ref_count += 1
        item["submitted_ref_count"] = len(LIVE_RUNTIME_OPERATOR_REQUIRED_EVIDENCE_CLASSES)
        item["all_required_refs_present"] = True
        item["submission_status"] = "submitted_for_validation"
    packet["submitted_ref_count"] = submitted_ref_count
    packet["all_required_refs_present"] = True
    packet["submission_status"] = "submitted_for_validation"
    packet["blocked_reasons"] = []


def _load_packet() -> dict[str, Any]:
    return json.loads(DEFAULT_PACKET.read_text(encoding="utf-8"))


def _write_packet(tmp_path: Path, packet: dict[str, Any]) -> Path:
    packet_path = tmp_path / "forge_live_runtime_operator_evidence_submission_packet.foundation.json"
    packet_path.write_text(json.dumps(packet, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return packet_path
