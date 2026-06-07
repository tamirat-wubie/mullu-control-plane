"""Tests for the Foundation Mode concept glossary rehearsal validator.

Purpose: prove concept glossary rehearsal stays local and does not become
canonical definition, mastery, training, comprehension, public-docs, product,
customer, private-value, legal/business, money, source-control publication,
external publication, or deployment evidence.
Governance scope: Foundation Mode, local concept glossary rehearsal,
private-value exclusion, external-action blocking, source-control publication
blocking, legal/business blocking, spending blocking, and deployment blocking.
Dependencies: scripts.validate_foundation_concept_glossary_rehearsal_boundary.
Invariants: only public-safe rehearsal labels are allowed; all concept glossary
surfaces remain AwaitingEvidence; no private values, mastery claims,
publication claims, source-control publication claims, or deployment claims are
accepted.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

from scripts.validate_foundation_concept_glossary_rehearsal_boundary import (
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
    payload = load_json_object(DEFAULT_PACKET_PATH, "concept glossary rehearsal witness")

    assert tuple(payload.keys()) == REQUIRED_ROOT_KEYS
    assert tuple(payload["deferral_labels"]) == DEFERRAL_LABELS
    assert tuple(payload["blocked_claims"]) == BLOCKED_CLAIMS
    assert all(payload[flag] is False for flag in FALSE_FLAGS)
    assert [surface["surface_id"] for surface in payload["surfaces"]] == list(DEFERRAL_LABELS)


def test_false_flag_drift_is_reported(tmp_path: Path) -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "concept glossary rehearsal witness")
    candidate = copy.deepcopy(payload)
    candidate["canonical_definition_claimed"] = True
    candidate["concept_mastery_claimed"] = True
    candidate["external_publication_allowed"] = True
    packet_path = _write_packet(tmp_path, candidate)

    findings = validate_artifacts(packet_path=packet_path)

    assert any("canonical_definition_claimed must remain false" in finding.message for finding in findings)
    assert any("concept_mastery_claimed must remain false" in finding.message for finding in findings)
    assert any(finding.rule_id == "witness_false_flag" for finding in findings)


def test_surface_state_and_note_drift_are_reported(tmp_path: Path) -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "concept glossary rehearsal witness")
    candidate = copy.deepcopy(payload)
    candidate["surfaces"][0]["state"] = "SolvedVerified"
    candidate["surfaces"][0]["public_safe_note"] = "Concept is mastered."
    packet_path = _write_packet(tmp_path, candidate)

    findings = validate_artifacts(packet_path=packet_path)

    assert any("must remain AwaitingEvidence" in finding.message for finding in findings)
    assert any("surface note drifted" in finding.message for finding in findings)
    assert any(finding.rule_id == "forbidden_promotion_pattern" for finding in findings)


def test_forbidden_live_values_are_reported(tmp_path: Path) -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "concept glossary rehearsal witness")
    candidate = copy.deepcopy(payload)
    candidate["surfaces"][6]["public_safe_note"] = (
        "Draft from https://example.test with account_id=real and schedule_slot=private"
    )
    packet_path = _write_packet(tmp_path, candidate)

    findings = validate_artifacts(packet_path=packet_path)

    assert any("forbidden value pattern: url" in finding.message for finding in findings)
    assert any("forbidden value pattern: private_schedule" in finding.message for finding in findings)
    assert any("forbidden value pattern: assignment_shape" in finding.message for finding in findings)


def test_promotion_phrase_is_reported(tmp_path: Path) -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "concept glossary rehearsal witness")
    candidate = copy.deepcopy(payload)
    candidate["surfaces"][8]["public_safe_note"] = "Public docs are ready."
    packet_path = _write_packet(tmp_path, candidate)

    findings = validate_artifacts(packet_path=packet_path)

    assert any("forbidden promotion pattern: public_docs_ready" in finding.message for finding in findings)
    assert any("surface note drifted" in finding.message for finding in findings)
    assert len(findings) >= 2


def test_doc_required_phrase_drift_is_reported(tmp_path: Path) -> None:
    doc_text = load_text(DEFAULT_DOC_PATH, "concept glossary rehearsal doc")
    candidate_text = doc_text.replace(REQUIRED_DOC_PHRASES[0], "Foundation Glossary Draft")
    doc_path = _write_doc(tmp_path, candidate_text)

    findings = validate_artifacts(doc_path=doc_path)

    assert any("doc missing required phrase" in finding.message for finding in findings)
    assert any(finding.rule_id == "doc_required_phrase" for finding in findings)
    assert "Foundation Concept Glossary Rehearsal Boundary" in doc_text


def test_surface_inventory_drift_is_reported(tmp_path: Path) -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "concept glossary rehearsal witness")
    candidate = copy.deepcopy(payload)
    candidate["surfaces"] = candidate["surfaces"][:-1]
    packet_path = _write_packet(tmp_path, candidate)

    findings = validate_artifacts(packet_path=packet_path)

    assert any("surface inventory drifted" in finding.message for finding in findings)
    assert len(candidate["surfaces"]) == len(SURFACE_NOTES_BY_ID) - 1
    assert len(findings) >= 1
