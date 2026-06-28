"""Forge live-runtime operator evidence acceptance handoff validator tests.

Purpose: verify verified operator evidence can be routed toward acceptance
review without granting runtime, production, commit, external-effect, signed
receipt population, or terminal closure authority.
Governance scope: handoff readiness, source verification binding, authority
denial, signed-receipt population denial, and fixture drift.
Dependencies: scripts.validate_forge_live_runtime_operator_evidence_acceptance_handoff_packet.
Invariants:
  - The Foundation fixture is deterministic and schema-backed.
  - Missing verification blocks acceptance review readiness.
  - Acceptance review readiness does not grant acceptance authority.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from gateway.forge_state_write_admission import (
    LIVE_RUNTIME_OPERATOR_REQUIRED_EVIDENCE_CLASSES,
    canonical_hash,
    build_foundation_forge_live_runtime_operator_evidence_acceptance_handoff_packet,
)
from scripts.validate_forge_live_runtime_operator_evidence_acceptance_handoff_packet import (
    DEFAULT_PACKET,
    DEFAULT_SCHEMA,
    validate_forge_live_runtime_operator_evidence_acceptance_handoff_packet,
)
from scripts.validate_schemas import _load_schema, _validate_schema_instance


def test_checked_in_forge_live_runtime_operator_evidence_acceptance_handoff_packet_is_valid() -> None:
    validation, produced_packet = validate_forge_live_runtime_operator_evidence_acceptance_handoff_packet()

    assert validation.ok is True
    assert validation.errors == ()
    assert validation.packet_id == "forge-live-runtime-operator-evidence-acceptance-handoff-packet.v1"
    assert validation.handoff_status == "blocked_awaiting_verified_operator_evidence"
    assert validation.handoff_item_count == 10
    assert validation.ready_item_count == 0
    assert validation.required_item_count == 10
    assert produced_packet["acceptance_review_allowed"] is False


def test_produced_operator_evidence_acceptance_handoff_packet_matches_schema() -> None:
    packet = build_foundation_forge_live_runtime_operator_evidence_acceptance_handoff_packet()
    errors = _validate_schema_instance(_load_schema(DEFAULT_SCHEMA), packet)

    assert errors == []
    assert packet["handoff_mode"] == "verified_operator_evidence_to_acceptance_review"
    assert len(packet["handoff_items"]) == 10
    assert all(item["ready_for_acceptance_review"] is False for item in packet["handoff_items"])
    assert all(item["acceptance_authority_effect"] is False for item in packet["handoff_items"])
    assert packet["signed_receipt_population_allowed"] is False


def test_validator_accepts_complete_verified_handoff_packet(tmp_path: Path) -> None:
    submission_packet = _load_submission_packet()
    _populate_all_submission_refs(submission_packet)
    submission_path = _write_json(tmp_path, "forge_live_runtime_operator_evidence_submission_packet.custom.json", submission_packet)
    gate = _load_verification_gate()
    gate["source_operator_evidence_submission_packet_ref"] = submission_path.name
    gate["source_operator_evidence_submission_packet_hash"] = submission_packet["packet_hash"]
    _populate_all_verification_refs(gate, submission_packet)
    _refresh_hash(gate, "gate_hash")
    gate_path = _write_json(tmp_path, "forge_live_runtime_operator_evidence_verification_gate.custom.json", gate)
    packet = _load_packet()
    packet["source_operator_evidence_verification_gate_ref"] = gate_path.name
    packet["source_operator_evidence_verification_gate_hash"] = gate["gate_hash"]
    _populate_ready_handoff_items(packet, gate)
    _refresh_hash(packet, "packet_hash")
    packet_path = _write_json(
        tmp_path,
        "forge_live_runtime_operator_evidence_acceptance_handoff_packet.custom.json",
        packet,
    )

    validation, _produced_packet = validate_forge_live_runtime_operator_evidence_acceptance_handoff_packet(
        schema_path=DEFAULT_SCHEMA,
        packet_path=packet_path,
        verification_gate_path=gate_path,
    )

    assert validation.ok is True
    assert validation.errors == ()
    assert validation.handoff_status == "verified_operator_evidence_ready_for_acceptance_review"
    assert validation.ready_item_count == 10
    assert validation.required_item_count == 10


def test_validator_rejects_acceptance_and_runtime_authority_overclaim(tmp_path: Path) -> None:
    packet = _load_packet()
    packet["acceptance_authority_effect"] = True
    packet["signed_receipt_population_allowed"] = True
    packet["runtime_authority_effect"] = True
    packet["secret_values_present"] = True
    packet["disallowed_authority"]["production_authorized"] = True
    packet_path = _write_json(tmp_path, "forge_live_runtime_operator_evidence_acceptance_handoff_packet.foundation.json", packet)

    validation, _produced_packet = validate_forge_live_runtime_operator_evidence_acceptance_handoff_packet(
        schema_path=DEFAULT_SCHEMA,
        packet_path=packet_path,
    )

    assert validation.ok is False
    assert any("acceptance_authority_effect" in error for error in validation.errors)
    assert any("signed_receipt_population_allowed" in error for error in validation.errors)
    assert any("runtime_authority_effect" in error for error in validation.errors)
    assert any("secret_values_present" in error for error in validation.errors)
    assert any("production_authorized" in error for error in validation.errors)


def test_validator_rejects_source_verification_hash_drift(tmp_path: Path) -> None:
    packet = _load_packet()
    packet["source_operator_evidence_verification_gate_hash"] = "0" * 64
    packet_path = _write_json(tmp_path, "forge_live_runtime_operator_evidence_acceptance_handoff_packet.foundation.json", packet)

    validation, _produced_packet = validate_forge_live_runtime_operator_evidence_acceptance_handoff_packet(
        schema_path=DEFAULT_SCHEMA,
        packet_path=packet_path,
    )

    assert validation.ok is False
    assert any("source_operator_evidence_verification_gate_hash mismatch" in error for error in validation.errors)


def test_validator_rejects_partial_ready_overclaim(tmp_path: Path) -> None:
    packet = _load_packet()
    item = packet["handoff_items"][0]
    item["verification_status"] = "verified_pending_acceptance"
    item["verified_ref_count"] = 8
    item["ready_for_acceptance_review"] = True
    item["blocker_reason"] = ""
    packet["ready_item_count"] = 1
    packet["acceptance_review_allowed"] = True
    packet["blocked_reasons"] = packet["blocked_reasons"][1:]
    packet_path = _write_json(tmp_path, "forge_live_runtime_operator_evidence_acceptance_handoff_packet.foundation.json", packet)

    validation, _produced_packet = validate_forge_live_runtime_operator_evidence_acceptance_handoff_packet(
        schema_path=DEFAULT_SCHEMA,
        packet_path=packet_path,
    )

    assert validation.ok is False
    assert any("managed_key_custody.verified_ref_count mismatch" in error for error in validation.errors)
    assert any("managed_key_custody.ready_for_acceptance_review mismatch" in error for error in validation.errors)
    assert any("acceptance_review_allowed mismatch" in error for error in validation.errors)


def _load_packet() -> dict[str, Any]:
    return json.loads(DEFAULT_PACKET.read_text(encoding="utf-8"))


def _load_verification_gate() -> dict[str, Any]:
    gate_path = DEFAULT_PACKET.parent / "forge_live_runtime_operator_evidence_verification_gate.foundation.json"
    return json.loads(gate_path.read_text(encoding="utf-8"))


def _load_submission_packet() -> dict[str, Any]:
    submission_path = DEFAULT_PACKET.parent / "forge_live_runtime_operator_evidence_submission_packet.foundation.json"
    return json.loads(submission_path.read_text(encoding="utf-8"))


def _write_json(tmp_path: Path, filename: str, payload: dict[str, Any]) -> Path:
    output_path = tmp_path / filename
    output_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path


def _populate_all_submission_refs(submission_packet: dict[str, Any]) -> None:
    submitted_ref_count = 0
    for item in submission_packet["submission_items"]:
        for class_index, slot in enumerate(item["submitted_refs"]):
            evidence_class = LIVE_RUNTIME_OPERATOR_REQUIRED_EVIDENCE_CLASSES[class_index]
            slot["submitted"] = True
            slot["evidence_ref"] = (
                f"evidence://forge/live-runtime/{item['evidence_id'].replace('_', '-')}/{evidence_class}"
            )
            slot["ref_hash"] = "sha256:" + f"{submitted_ref_count + 1:064x}"[-64:]
            slot["validation_status"] = "submitted_unverified"
            submitted_ref_count += 1
        item["submitted_ref_count"] = len(LIVE_RUNTIME_OPERATOR_REQUIRED_EVIDENCE_CLASSES)
        item["all_required_refs_present"] = True
        item["submission_status"] = "submitted_for_validation"
    submission_packet["submitted_ref_count"] = submitted_ref_count
    submission_packet["all_required_refs_present"] = True
    submission_packet["submission_status"] = "submitted_for_validation"
    submission_packet["blocked_reasons"] = []
    _refresh_hash(submission_packet, "packet_hash")


def _populate_all_verification_refs(gate: dict[str, Any], submission_packet: dict[str, Any]) -> None:
    source_slots = {
        (item["evidence_id"], slot["evidence_class"]): slot
        for item in submission_packet["submission_items"]
        for slot in item["submitted_refs"]
    }
    verified_ref_count = 0
    for item in gate["verification_items"]:
        for class_index, slot in enumerate(item["verification_slots"]):
            evidence_class = LIVE_RUNTIME_OPERATOR_REQUIRED_EVIDENCE_CLASSES[class_index]
            source_slot = source_slots[(item["evidence_id"], evidence_class)]
            slot["source_evidence_ref"] = source_slot["evidence_ref"]
            slot["source_ref_hash"] = source_slot["ref_hash"]
            slot["verification_ref"] = (
                f"proof://forge/live-runtime/{item['evidence_id'].replace('_', '-')}/{evidence_class}"
            )
            slot["verifier_identity_ref"] = "proof://forge/verifier/local-foundation"
            slot["verification_status"] = "verified"
            slot["verification_passed"] = True
            verified_ref_count += 1
        item["submitted_ref_count"] = len(LIVE_RUNTIME_OPERATOR_REQUIRED_EVIDENCE_CLASSES)
        item["verified_ref_count"] = len(LIVE_RUNTIME_OPERATOR_REQUIRED_EVIDENCE_CLASSES)
        item["all_slots_verified"] = True
        item["verification_status"] = "verified_pending_acceptance"
    gate["submitted_ref_count"] = verified_ref_count
    gate["verified_ref_count"] = verified_ref_count
    gate["all_submitted_refs_verified"] = True
    gate["verification_status"] = "verified_pending_acceptance"
    gate["blocked_reasons"] = []


def _populate_ready_handoff_items(packet: dict[str, Any], gate: dict[str, Any]) -> None:
    verification_by_id = {item["evidence_id"]: item for item in gate["verification_items"]}
    ready_count = 0
    for item in packet["handoff_items"]:
        verification_item = verification_by_id[item["evidence_id"]]
        item["verification_status"] = "verified_pending_acceptance"
        item["verified_ref_count"] = verification_item["verified_ref_count"]
        item["ready_for_acceptance_review"] = True
        item["blocker_reason"] = ""
        ready_count += 1
    packet["handoff_status"] = "verified_operator_evidence_ready_for_acceptance_review"
    packet["ready_item_count"] = ready_count
    packet["all_items_ready_for_acceptance_review"] = True
    packet["acceptance_review_allowed"] = True
    packet["blocked_reasons"] = []


def _refresh_hash(payload: dict[str, Any], hash_field: str) -> None:
    payload_for_hash = dict(payload)
    payload_for_hash.pop(hash_field, None)
    payload[hash_field] = canonical_hash(payload_for_hash)
