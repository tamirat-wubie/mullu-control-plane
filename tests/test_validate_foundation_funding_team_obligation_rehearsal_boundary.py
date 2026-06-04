"""Tests for the Foundation Mode funding/team obligation rehearsal validator.

Purpose: prove funding/team obligation rehearsal stays local and does not
authorize funding readiness, team readiness, fundraising, outreach, grants,
pitch publication, hiring, contractors, advisors, compensation, equity,
payroll, budgets, spending, company/legal claims, customer access,
contact-list storage, money movement, publication, secrets, or deployment.
Governance scope: Foundation Mode, funding/team obligation rehearsal,
public-safe local planning, contact-list exclusion, obligation blocking,
money-movement blocking, customer-access blocking, and deployment blocking.
Dependencies: scripts.validate_foundation_funding_team_obligation_rehearsal_boundary.
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

from scripts.validate_foundation_funding_team_obligation_rehearsal_boundary import (  # noqa: E402
    DEFAULT_PACKET_PATH,
    EXPECTED_SURFACES,
    EXPECTED_WITNESS_ID,
    load_json_object,
    validate_foundation_funding_team_obligation_rehearsal_boundary,
    validate_packet,
)


def test_foundation_funding_team_obligation_rehearsal_boundary_artifacts_pass() -> None:
    assert validate_foundation_funding_team_obligation_rehearsal_boundary() == []


def test_obligation_rehearsal_witness_has_expected_identity_and_blockers() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "funding/team obligation rehearsal witness")

    assert payload["witness_id"] == EXPECTED_WITNESS_ID
    assert tuple(
        (surface["surface_id"], surface["surface_type"], surface["state"])
        for surface in payload["surfaces"]
    ) == EXPECTED_SURFACES
    assert payload["obligation_rehearsal_executed"] is False
    assert payload["funding_readiness_claimed"] is False
    assert payload["team_readiness_claimed"] is False
    assert payload["fundraising_allowed"] is False
    assert payload["investor_outreach_allowed"] is False
    assert payload["hiring_allowed"] is False
    assert payload["money_movement_allowed"] is False
    assert payload["deployment_allowed"] is False


def test_witness_rejects_readiness_and_rehearsal_execution_claims() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "funding/team obligation rehearsal witness")
    candidate = deepcopy(payload)
    candidate["obligation_rehearsal_executed"] = True
    candidate["funding_readiness_claimed"] = True
    candidate["team_readiness_claimed"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "funding_team_obligation_rehearsal_root_value_invalid" for finding in findings)


def test_witness_rejects_outreach_grant_pitch_hiring_and_contractor_claims() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "funding/team obligation rehearsal witness")
    candidate = deepcopy(payload)
    candidate["fundraising_allowed"] = True
    candidate["investor_outreach_allowed"] = True
    candidate["grant_application_allowed"] = True
    candidate["pitch_publication_allowed"] = True
    candidate["hiring_allowed"] = True
    candidate["contractor_engagement_allowed"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "funding_team_obligation_rehearsal_root_value_invalid" for finding in findings)


def test_witness_rejects_advisor_compensation_equity_payroll_budget_and_spending_claims() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "funding/team obligation rehearsal witness")
    candidate = deepcopy(payload)
    candidate["advisor_commitment_allowed"] = True
    candidate["compensation_commitment_allowed"] = True
    candidate["equity_promise_allowed"] = True
    candidate["payroll_setup_allowed"] = True
    candidate["budget_commitment_allowed"] = True
    candidate["spending_allowed"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "funding_team_obligation_rehearsal_root_value_invalid" for finding in findings)


def test_witness_rejects_company_legal_customer_contact_money_publication_secret_and_deployment_claims() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "funding/team obligation rehearsal witness")
    candidate = deepcopy(payload)
    candidate["company_formation_claimed"] = True
    candidate["legal_clearance_claimed"] = True
    candidate["customer_access_allowed"] = True
    candidate["contact_list_storage_allowed"] = True
    candidate["money_movement_allowed"] = True
    candidate["external_publication_allowed"] = True
    candidate["secret_material_allowed"] = True
    candidate["deployment_allowed"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "funding_team_obligation_rehearsal_root_value_invalid" for finding in findings)


def test_witness_rejects_surface_state_promotion() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "funding/team obligation rehearsal witness")
    candidate = deepcopy(payload)
    candidate["surfaces"][0]["state"] = "Ready"

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "funding_team_obligation_rehearsal_surface_inventory_invalid" for finding in findings)
    assert any(finding.rule_id == "funding_team_obligation_rehearsal_surface_state_invalid" for finding in findings)


def test_witness_rejects_private_contact_value_shape() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "funding/team obligation rehearsal witness")
    candidate = deepcopy(payload)
    candidate["surfaces"][0]["public_safe_note"] = "contact_list=private-investors"

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "funding_team_obligation_rehearsal_forbidden_value_pattern" for finding in findings)


def test_witness_rejects_funding_team_promotion_phrase() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "funding/team obligation rehearsal witness")
    candidate = deepcopy(payload)
    candidate["next_action"] = "fundraising is ready"

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "funding_team_obligation_rehearsal_forbidden_promotion_phrase" for finding in findings)
