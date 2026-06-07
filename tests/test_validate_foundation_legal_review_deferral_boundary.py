"""Tests for the Foundation Mode legal-review deferral validator.

Purpose: prove legal-review deferral stays local and does not become legal
review completion, clearance, formation, filing, payment, customer-access,
publication, or deployment evidence.
Governance scope: Foundation Mode, local legal-review deferral,
qualified-review gating, claim blocking, private-material exclusion,
payment blocking, customer-access blocking, publication blocking, and
deployment blocking.
Dependencies: scripts.validate_foundation_legal_review_deferral_boundary.
Invariants: only public-safe deferral labels are allowed; all legal-review
surfaces remain AwaitingEvidence; no reviewer identities, conclusions, filings,
accounts, payments, customer data, readiness claims, or deployment claims are
accepted.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

from scripts.validate_foundation_legal_review_deferral_boundary import (
    BLOCKED_CLAIMS,
    DEFAULT_DOC_PATH,
    DEFAULT_PACKET_PATH,
    DEFERRAL_LABELS,
    FALSE_FLAGS,
    REQUIRED_DOC_PHRASES,
    REQUIRED_ROOT_KEYS,
    SURFACE_NOTES_BY_ID,
    load_json_object,
    load_text,
    validate_artifacts,
)


def _write_packet(tmp_path: Path, payload: dict[str, object]) -> Path:
    packet_path = tmp_path / "candidate.json"
    packet_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return packet_path


def _write_doc(tmp_path: Path, text: str) -> Path:
    doc_path = tmp_path / "candidate.md"
    doc_path.write_text(text, encoding="utf-8")
    return doc_path


def test_default_artifacts_pass() -> None:
    findings = validate_artifacts()

    assert findings == []
    assert DEFAULT_DOC_PATH.exists()
    assert DEFAULT_PACKET_PATH.exists()


def test_witness_contract_matches_expected_labels_and_claims() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "legal-review deferral witness")

    assert tuple(payload.keys()) == REQUIRED_ROOT_KEYS
    assert tuple(payload["deferral_labels"]) == DEFERRAL_LABELS
    assert tuple(payload["blocked_claims"]) == BLOCKED_CLAIMS
    assert all(payload[flag] is False for flag in FALSE_FLAGS)
    assert [surface["surface_id"] for surface in payload["surfaces"]] == list(DEFERRAL_LABELS)


def test_false_flag_drift_is_reported(tmp_path: Path) -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "legal-review deferral witness")
    candidate = copy.deepcopy(payload)
    candidate["legal_review_complete_claimed"] = True
    candidate["legal_conclusion_recorded"] = True
    candidate["legal_clearance_claimed"] = True
    packet_path = _write_packet(tmp_path, candidate)

    findings = validate_artifacts(packet_path=packet_path)

    assert any("legal_review_complete_claimed must remain false" in finding.message for finding in findings)
    assert any("legal_conclusion_recorded must remain false" in finding.message for finding in findings)
    assert any(finding.rule_id == "witness_false_flag" for finding in findings)


def test_surface_state_and_note_drift_are_reported(tmp_path: Path) -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "legal-review deferral witness")
    candidate = copy.deepcopy(payload)
    candidate["surfaces"][2]["state"] = "SolvedVerified"
    candidate["surfaces"][2]["public_safe_note"] = "Legal conclusion reached."
    packet_path = _write_packet(tmp_path, candidate)

    findings = validate_artifacts(packet_path=packet_path)

    assert any("must remain AwaitingEvidence" in finding.message for finding in findings)
    assert any("surface note drifted" in finding.message for finding in findings)
    assert any(finding.rule_id == "forbidden_promotion_pattern" for finding in findings)


def test_forbidden_live_values_are_reported(tmp_path: Path) -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "legal-review deferral witness")
    candidate = copy.deepcopy(payload)
    candidate["surfaces"][1]["public_safe_note"] = (
        "Reviewer record at https://example.test with reviewer_id=private-reviewer and hash "
        "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    )
    packet_path = _write_packet(tmp_path, candidate)

    findings = validate_artifacts(packet_path=packet_path)

    assert any("forbidden value pattern: url" in finding.message for finding in findings)
    assert any("forbidden value pattern: assignment_shape" in finding.message for finding in findings)
    assert any("forbidden value pattern: hash_like_value" in finding.message for finding in findings)


def test_promotion_phrase_is_reported(tmp_path: Path) -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "legal-review deferral witness")
    candidate = copy.deepcopy(payload)
    candidate["surfaces"][3]["public_safe_note"] = "Legal clearance approved."
    packet_path = _write_packet(tmp_path, candidate)

    findings = validate_artifacts(packet_path=packet_path)

    assert any("forbidden promotion pattern: legal_clearance_approved" in finding.message for finding in findings)
    assert any("surface note drifted" in finding.message for finding in findings)
    assert len(findings) >= 2


def test_doc_required_phrase_drift_is_reported(tmp_path: Path) -> None:
    doc_text = load_text(DEFAULT_DOC_PATH, "legal-review deferral doc")
    candidate_text = doc_text.replace(REQUIRED_DOC_PHRASES[0], "Foundation Legal Review Draft")
    doc_path = _write_doc(tmp_path, candidate_text)

    findings = validate_artifacts(doc_path=doc_path)

    assert any("doc missing required phrase" in finding.message for finding in findings)
    assert any(finding.rule_id == "doc_required_phrase" for finding in findings)
    assert "Foundation Legal Review Deferral Boundary" in doc_text


def test_surface_inventory_drift_is_reported(tmp_path: Path) -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "legal-review deferral witness")
    candidate = copy.deepcopy(payload)
    candidate["surfaces"] = candidate["surfaces"][:-1]
    packet_path = _write_packet(tmp_path, candidate)

    findings = validate_artifacts(packet_path=packet_path)

    assert any("surface inventory drifted" in finding.message for finding in findings)
    assert len(candidate["surfaces"]) == len(SURFACE_NOTES_BY_ID) - 1
    assert len(findings) >= 1
