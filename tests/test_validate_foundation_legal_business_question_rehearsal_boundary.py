"""Tests for the Foundation Mode legal/business question rehearsal validator.

Purpose: prove legal/business question rehearsal stays local and does not
authorize legal conclusions, qualified review completion, formation, filings,
tax readiness, terms/privacy readiness, team commitments, paid launch, payment
processing, money movement, customer access, publication, private reviewer
material, or deployment.
Governance scope: Foundation Mode, local legal/business question rehearsal,
qualified-review gating, claim blocking, private-material exclusion,
paid-launch blocking, money-movement blocking, customer-access blocking,
external-publication blocking, and deployment blocking.
Dependencies: scripts.validate_foundation_legal_business_question_rehearsal_boundary.
Invariants: rehearsal surfaces remain AwaitingEvidence and reject private
value drift, execution drift, and readiness-promotion drift.
"""

from __future__ import annotations

from copy import deepcopy
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validate_foundation_legal_business_question_rehearsal_boundary import (  # noqa: E402
    DEFAULT_PACKET_PATH,
    EXPECTED_SURFACES,
    EXPECTED_WITNESS_ID,
    load_json_object,
    validate_foundation_legal_business_question_rehearsal_boundary,
    validate_packet,
)


def test_foundation_legal_business_question_rehearsal_boundary_artifacts_pass() -> None:
    assert validate_foundation_legal_business_question_rehearsal_boundary() == []


def test_legal_business_question_rehearsal_witness_has_expected_identity_and_blockers() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "legal/business question rehearsal witness")

    assert payload["witness_id"] == EXPECTED_WITNESS_ID
    assert tuple(
        (surface["surface_id"], surface["surface_type"], surface["state"])
        for surface in payload["surfaces"]
    ) == EXPECTED_SURFACES
    assert payload["question_rehearsal_executed"] is False
    assert payload["legal_conclusion_claimed"] is False
    assert payload["legal_clearance_claimed"] is False
    assert payload["qualified_review_completed"] is False
    assert payload["company_formation_allowed"] is False
    assert payload["paid_launch_allowed"] is False
    assert payload["money_movement_allowed"] is False
    assert payload["customer_access_allowed"] is False
    assert payload["deployment_allowed"] is False


def test_witness_rejects_legal_conclusion_and_review_claims() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "legal/business question rehearsal witness")
    candidate = deepcopy(payload)
    candidate["question_rehearsal_executed"] = True
    candidate["legal_conclusion_claimed"] = True
    candidate["legal_clearance_claimed"] = True
    candidate["qualified_review_completed"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "legal_business_question_rehearsal_root_value_invalid" for finding in findings)


def test_witness_rejects_company_filing_tax_terms_and_compliance_claims() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "legal/business question rehearsal witness")
    candidate = deepcopy(payload)
    candidate["company_formation_allowed"] = True
    candidate["company_readiness_claimed"] = True
    candidate["patent_filing_allowed"] = True
    candidate["patent_protection_claimed"] = True
    candidate["trademark_clearance_claimed"] = True
    candidate["tax_readiness_claimed"] = True
    candidate["terms_privacy_readiness_claimed"] = True
    candidate["compliance_clearance_claimed"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "legal_business_question_rehearsal_root_value_invalid" for finding in findings)


def test_witness_rejects_team_payment_customer_publication_secret_and_deployment_claims() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "legal/business question rehearsal witness")
    candidate = deepcopy(payload)
    candidate["contractor_team_commitment_allowed"] = True
    candidate["paid_launch_allowed"] = True
    candidate["payment_processing_allowed"] = True
    candidate["money_movement_allowed"] = True
    candidate["customer_access_allowed"] = True
    candidate["external_publication_allowed"] = True
    candidate["secret_or_private_reviewer_material_allowed"] = True
    candidate["deployment_allowed"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "legal_business_question_rehearsal_root_value_invalid" for finding in findings)


def test_witness_rejects_surface_state_promotion() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "legal/business question rehearsal witness")
    candidate = deepcopy(payload)
    candidate["surfaces"][0]["state"] = "Ready"

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "legal_business_question_rehearsal_surface_inventory_invalid" for finding in findings)
    assert any(finding.rule_id == "legal_business_question_rehearsal_surface_state_invalid" for finding in findings)


def test_witness_rejects_private_value_shape() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "legal/business question rehearsal witness")
    candidate = deepcopy(payload)
    candidate["surfaces"][0]["public_safe_note"] = "reviewer_id=private-reviewer"

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "legal_business_question_rehearsal_forbidden_value_pattern" for finding in findings)


def test_witness_rejects_legal_business_promotion_phrase() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "legal/business question rehearsal witness")
    candidate = deepcopy(payload)
    candidate["next_action"] = "legal clearance approved"

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "legal_business_question_rehearsal_forbidden_promotion_phrase" for finding in findings)
