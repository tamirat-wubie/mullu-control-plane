"""Tests for Personal Assistant approval review packet validation.

Purpose: prove approval proposal review packets are schema-backed, no-effect,
and bounded to operator review.
Governance scope: approval review packet schema, authority denial, evidence
binding, and private payload rejection.
Dependencies: scripts.validate_personal_assistant_approval_review_packet.
Invariants:
  - Review packets do not enqueue, approve, or execute actions.
  - Required operator checks and authority denials remain explicit.
  - Raw private payloads and secret-like values are rejected.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

from scripts.validate_personal_assistant_approval_review_packet import (
    DEFAULT_PACKET,
    validate_personal_assistant_approval_review_packet,
)


def test_personal_assistant_approval_review_packet_fixture_validates() -> None:
    validation = validate_personal_assistant_approval_review_packet()

    assert validation.valid is True
    assert validation.packet_path == "examples/personal_assistant_approval_review_packet.json"
    assert validation.review_packet_id == "pa_approval_review_approval_review_packet_001"
    assert validation.solver_outcome == "SolvedVerified"
    assert validation.errors == ()
    packet = _load_fixture()
    assert len(packet["source_closure_refs"]) == 2
    assert packet["metadata"]["source_closure_binding"] == "digest_verified_closed_packets"
    assert packet["metadata"]["source_payloads_serialized"] is False


def test_personal_assistant_approval_review_packet_rejects_authority_drift(tmp_path: Path) -> None:
    packet = _load_fixture()
    packet["effect_boundary"]["execution_allowed"] = True
    packet["effect_boundary"]["approval_enqueued"] = True
    packet["metadata"]["review_packet_is_execution"] = True
    packet["authority_denials"] = [
        denial for denial in packet["authority_denials"] if denial["authority"] != "approval_enqueue"
    ]
    candidate = tmp_path / "unsafe_approval_review_packet.json"
    candidate.write_text(json.dumps(packet), encoding="utf-8")

    validation = validate_personal_assistant_approval_review_packet(packet_path=candidate)

    assert validation.valid is False
    assert "effect_boundary.execution_allowed must be false" in validation.errors
    assert "effect_boundary.approval_enqueued must be false" in validation.errors
    assert "metadata.review_packet_is_execution must be false" in validation.errors
    assert "authority_denials missing approval_enqueue" in validation.errors


def test_personal_assistant_approval_review_packet_rejects_missing_evidence_and_checks(tmp_path: Path) -> None:
    packet = _load_fixture()
    packet["evidence_refs"] = []
    packet["forbidden_without_approval"] = []
    packet["required_operator_checks"] = ["confirm_request_identity"]
    candidate = tmp_path / "incomplete_approval_review_packet.json"
    candidate.write_text(json.dumps(packet), encoding="utf-8")

    validation = validate_personal_assistant_approval_review_packet(packet_path=candidate)

    assert validation.valid is False
    assert any("evidence_refs" in error for error in validation.errors)
    assert any("forbidden_without_approval" in error for error in validation.errors)
    assert "required_operator_checks must contain the base review checks" in validation.errors
    assert validation.solver_outcome == "GovernanceBlocked"


def test_personal_assistant_approval_review_packet_rejects_source_digest_drift(tmp_path: Path) -> None:
    packet = _load_fixture()
    packet["source_closure_refs"][0]["source_sha256"] = "0" * 64
    packet["metadata"]["all_source_closure_refs_bound"] = False
    candidate = tmp_path / "digest_drift_approval_review_packet.json"
    candidate.write_text(json.dumps(packet), encoding="utf-8")

    validation = validate_personal_assistant_approval_review_packet(packet_path=candidate)

    assert validation.valid is False
    assert "source_closure_refs[0].source_sha256 does not match source file" in validation.errors
    assert "metadata.all_source_closure_refs_bound must be true" in validation.errors
    assert validation.solver_outcome == "GovernanceBlocked"


def test_personal_assistant_approval_review_packet_rejects_unclosed_source_reference(tmp_path: Path) -> None:
    packet = _load_fixture()
    packet["source_closure_refs"][1]["closure_field"] = "missing_foundation_closure"
    packet["source_closure_refs"][1]["closed"] = False
    packet["source_closure_refs"][1]["payload_digest_only"] = False
    candidate = tmp_path / "unclosed_source_approval_review_packet.json"
    candidate.write_text(json.dumps(packet), encoding="utf-8")

    validation = validate_personal_assistant_approval_review_packet(packet_path=candidate)

    assert validation.valid is False
    assert any("closure_field must be foundation_closure_packet_closed" in error for error in validation.errors)
    assert "source_closure_refs[1].closed must be true" in validation.errors
    assert "source_closure_refs[1].payload_digest_only must be true" in validation.errors


def test_personal_assistant_approval_review_packet_rejects_raw_payload_and_secret(tmp_path: Path) -> None:
    packet = _load_fixture()
    packet["proposed_actions"][0]["raw_connector_payload"] = {"message_body": "private"}
    packet["metadata"]["operator_note"] = "Bearer secret-token-value"
    candidate = tmp_path / "private_approval_review_packet.json"
    candidate.write_text(json.dumps(packet), encoding="utf-8")

    validation = validate_personal_assistant_approval_review_packet(packet_path=candidate)

    assert validation.valid is False
    assert any("raw_connector_payload" in error for error in validation.errors)
    assert any("secret-like value" in error for error in validation.errors)
    assert not any("message_body" in error for error in validation.errors)


def _load_fixture() -> dict[str, object]:
    return copy.deepcopy(json.loads(DEFAULT_PACKET.read_text(encoding="utf-8")))
