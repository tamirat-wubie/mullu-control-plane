"""Tests for the Foundation Mode legal/business boundary validator.

Purpose: prove legal and business preparation remains question-only until
qualified review or signed witness evidence promotes a specific item.
Governance scope: Foundation Mode, legal/business pre-clearance, claim blocking,
paid-launch blocking, and money-movement blocking.
Dependencies: scripts.validate_foundation_legal_business_boundary.
Invariants: the question packet keeps readiness claims false and rejects
readiness-promotion drift.
"""

from __future__ import annotations

from copy import deepcopy
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validate_foundation_legal_business_boundary import (  # noqa: E402
    DEFAULT_PACKET_PATH,
    EXPECTED_DOMAIN_IDS,
    EXPECTED_PACKET_ID,
    load_json_object,
    validate_foundation_legal_business_boundary,
    validate_packet,
)


def test_foundation_legal_business_boundary_artifacts_pass() -> None:
    assert validate_foundation_legal_business_boundary() == []


def test_question_packet_has_expected_identity_and_blockers() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "legal/business packet")

    assert payload["packet_id"] == EXPECTED_PACKET_ID
    assert tuple(domain["domain_id"] for domain in payload["domains"]) == EXPECTED_DOMAIN_IDS
    assert payload["legal_clearance_claimed"] is False
    assert payload["company_ready_claimed"] is False
    assert payload["patent_protection_claimed"] is False
    assert payload["paid_launch_allowed"] is False
    assert payload["money_movement_allowed"] is False


def test_packet_rejects_legal_clearance_promotion() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "legal/business packet")
    candidate = deepcopy(payload)
    candidate["legal_clearance_claimed"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "legal_business_root_value_invalid" for finding in findings)


def test_packet_rejects_paid_launch_promotion() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "legal/business packet")
    candidate = deepcopy(payload)
    candidate["paid_launch_allowed"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "legal_business_root_value_invalid" for finding in findings)


def test_packet_rejects_domain_state_promotion() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "legal/business packet")
    candidate = deepcopy(payload)
    candidate["domains"][0]["current_state"] = "ReadyForReview"

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "legal_business_domain_state_invalid" for finding in findings)


def test_packet_rejects_missing_question_area() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "legal/business packet")
    candidate = deepcopy(payload)
    candidate["domains"] = [
        domain for domain in candidate["domains"] if domain["domain_id"] != "tax_accounting"
    ]

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "legal_business_domain_ids_invalid" for finding in findings)


def test_packet_rejects_readiness_phrase() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "legal/business packet")
    candidate = deepcopy(payload)
    candidate["domains"][0]["public_safe_note"] = "Legal clearance approved."

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "legal_business_forbidden_readiness_phrase" for finding in findings)
