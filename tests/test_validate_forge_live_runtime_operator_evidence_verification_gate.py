"""Forge live-runtime operator evidence verification gate validator tests.

Purpose: verify submitted operator evidence refs are not treated as verified
evidence or runtime authority.
Governance scope: verification status, source submission binding, authority
denial, promotion denial, signed-receipt population denial, and fixture drift.
Dependencies: scripts.validate_forge_live_runtime_operator_evidence_verification_gate.
Invariants:
  - The Foundation fixture is deterministic and schema-backed.
  - Submitted refs remain unverified until independent verification exists.
  - Runtime, production, commit, external-effect, and terminal closure
    authority remain false.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from gateway.forge_state_write_admission import (
    LIVE_RUNTIME_OPERATOR_REQUIRED_EVIDENCE_CLASSES,
    canonical_hash,
    build_foundation_forge_live_runtime_operator_evidence_verification_gate,
)
from scripts.validate_forge_live_runtime_operator_evidence_verification_gate import (
    DEFAULT_GATE,
    DEFAULT_SCHEMA,
    validate_forge_live_runtime_operator_evidence_verification_gate,
)
from scripts.validate_schemas import _load_schema, _validate_schema_instance


def test_checked_in_forge_live_runtime_operator_evidence_verification_gate_is_valid() -> None:
    validation, produced_gate = validate_forge_live_runtime_operator_evidence_verification_gate()

    assert validation.ok is True
    assert validation.errors == ()
    assert validation.gate_id == "forge-live-runtime-operator-evidence-verification-gate.v1"
    assert validation.verification_status == "blocked_awaiting_operator_evidence_verification"
    assert validation.verification_item_count == 10
    assert validation.verified_ref_count == 0
    assert validation.required_verification_count == 80
    assert produced_gate["promotion_allowed"] is False
    assert produced_gate["signed_receipt_population_allowed"] is False


def test_produced_operator_evidence_verification_gate_matches_schema() -> None:
    gate = build_foundation_forge_live_runtime_operator_evidence_verification_gate()
    errors = _validate_schema_instance(_load_schema(DEFAULT_SCHEMA), gate)

    assert errors == []
    assert gate["verification_mode"] == "operator_evidence_refs_require_independent_verification"
    assert len(gate["verification_items"]) == 10
    assert all(item["verified_ref_count"] == 0 for item in gate["verification_items"])
    assert all(item["all_slots_verified"] is False for item in gate["verification_items"])


def test_validator_accepts_complete_verified_reference_packet(tmp_path: Path) -> None:
    submission_packet = _load_submission_packet()
    _populate_all_submission_refs(submission_packet)
    submission_path = _write_submission_packet(tmp_path, submission_packet)
    gate = _load_gate()
    gate["source_operator_evidence_submission_packet_ref"] = submission_path.name
    gate["source_operator_evidence_submission_packet_hash"] = submission_packet["packet_hash"]
    _populate_all_verification_refs(gate, submission_packet)
    gate_path = _write_gate(tmp_path, gate)

    validation, _produced_gate = validate_forge_live_runtime_operator_evidence_verification_gate(
        schema_path=DEFAULT_SCHEMA,
        gate_path=gate_path,
        submission_packet_path=submission_path,
    )

    assert validation.ok is True
    assert validation.errors == ()
    assert validation.verification_status == "verified_pending_acceptance"
    assert validation.verified_ref_count == 80
    assert validation.required_verification_count == 80


def test_validator_rejects_verification_and_promotion_overclaim(tmp_path: Path) -> None:
    gate = _load_gate()
    gate["all_submitted_refs_verified"] = True
    gate["promotion_allowed"] = True
    gate["signed_receipt_population_allowed"] = True
    gate["runtime_authority_effect"] = True
    gate["secret_values_present"] = True
    gate_path = _write_gate(tmp_path, gate)

    validation, _produced_gate = validate_forge_live_runtime_operator_evidence_verification_gate(
        schema_path=DEFAULT_SCHEMA,
        gate_path=gate_path,
    )

    assert validation.ok is False
    assert any("all_submitted_refs_verified" in error for error in validation.errors)
    assert any("promotion_allowed" in error for error in validation.errors)
    assert any("signed_receipt_population_allowed" in error for error in validation.errors)
    assert any("runtime_authority_effect" in error for error in validation.errors)
    assert any("secret_values_present" in error for error in validation.errors)


def test_validator_rejects_slot_verification_overclaim(tmp_path: Path) -> None:
    gate = _load_gate()
    item = gate["verification_items"][0]
    slot = item["verification_slots"][0]
    slot["source_evidence_ref"] = "evidence://forge/live-runtime/managed-key-custody/operator-approval"
    slot["source_ref_hash"] = "sha256:" + "1" * 64
    slot["verification_ref"] = "proof://forge/live-runtime/managed-key-custody/operator-approval"
    slot["verifier_identity_ref"] = "proof://forge/verifier/local"
    slot["verification_status"] = "verified"
    slot["verification_passed"] = True
    slot["authority_effect"] = True
    item["submitted_ref_count"] = 1
    item["verified_ref_count"] = 1
    item["all_slots_verified"] = True
    item["verification_status"] = "verified"
    gate["submitted_ref_count"] = 1
    gate["verified_ref_count"] = 1
    gate_path = _write_gate(tmp_path, gate)

    validation, _produced_gate = validate_forge_live_runtime_operator_evidence_verification_gate(
        schema_path=DEFAULT_SCHEMA,
        gate_path=gate_path,
    )

    assert validation.ok is False
    assert validation.ok is False
    assert any("managed_key_custody.all_slots_verified mismatch" in error for error in validation.errors)
    assert any("managed_key_custody.verification_status must be blocked_awaiting_submitted_refs" in error for error in validation.errors)
    assert any("operator_approval_ref.source_evidence_ref mismatch" in error for error in validation.errors)
    assert any("operator_approval_ref.source_ref_hash mismatch" in error for error in validation.errors)


def test_validator_rejects_source_submission_hash_drift(tmp_path: Path) -> None:
    gate = _load_gate()
    gate["source_operator_evidence_submission_packet_hash"] = "0" * 64
    gate_path = _write_gate(tmp_path, gate)

    validation, _produced_gate = validate_forge_live_runtime_operator_evidence_verification_gate(
        schema_path=DEFAULT_SCHEMA,
        gate_path=gate_path,
    )

    assert validation.ok is False
    assert any("source_operator_evidence_submission_packet_hash mismatch" in error for error in validation.errors)


def _load_gate() -> dict[str, Any]:
    return json.loads(DEFAULT_GATE.read_text(encoding="utf-8"))


def _load_submission_packet() -> dict[str, Any]:
    submission_path = DEFAULT_GATE.parent / "forge_live_runtime_operator_evidence_submission_packet.foundation.json"
    return json.loads(submission_path.read_text(encoding="utf-8"))


def _write_gate(tmp_path: Path, gate: dict[str, Any]) -> Path:
    gate_path = tmp_path / "forge_live_runtime_operator_evidence_verification_gate.foundation.json"
    gate_path.write_text(json.dumps(gate, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return gate_path


def _write_submission_packet(tmp_path: Path, submission_packet: dict[str, Any]) -> Path:
    submission_path = tmp_path / "forge_live_runtime_operator_evidence_submission_packet.custom.json"
    submission_path.write_text(json.dumps(submission_packet, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return submission_path


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
    payload_for_hash = dict(submission_packet)
    payload_for_hash.pop("packet_hash", None)
    submission_packet["packet_hash"] = canonical_hash(payload_for_hash)


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
