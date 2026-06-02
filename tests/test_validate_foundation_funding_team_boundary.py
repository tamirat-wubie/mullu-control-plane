"""Tests for the Foundation Mode funding/team boundary validator.

Purpose: prove funding/team preparation stays local and does not authorize
fundraising, investor outreach, grants, pitch publication, hiring, contractor
engagement, advisor commitments, compensation, equity, payroll, budget
commitments, money movement, external publication, or deployment claims.
Governance scope: Foundation Mode, funding posture, team posture, public-safe
planning witness, private-value exclusion, and obligation blocking.
Dependencies: scripts.validate_foundation_funding_team_boundary.
Invariants: funding/team surfaces remain AwaitingEvidence and reject outside
obligation or private value drift.
"""

from __future__ import annotations

from copy import deepcopy
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validate_foundation_funding_team_boundary import (  # noqa: E402
    DEFAULT_PACKET_PATH,
    EXPECTED_SURFACES,
    EXPECTED_WITNESS_ID,
    load_json_object,
    validate_foundation_funding_team_boundary,
    validate_packet,
)


def test_foundation_funding_team_boundary_artifacts_pass() -> None:
    assert validate_foundation_funding_team_boundary() == []


def test_funding_team_witness_has_expected_identity_and_blockers() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "funding/team witness")

    assert payload["witness_id"] == EXPECTED_WITNESS_ID
    assert tuple(
        (surface["surface_id"], surface["surface_type"], surface["state"])
        for surface in payload["funding_team_surfaces"]
    ) == EXPECTED_SURFACES
    assert payload["fundraising_allowed"] is False
    assert payload["investor_outreach_allowed"] is False
    assert payload["hiring_allowed"] is False
    assert payload["contractor_engagement_allowed"] is False
    assert payload["equity_promise_allowed"] is False
    assert payload["money_movement_allowed"] is False
    assert payload["deployment_allowed"] is False


def test_witness_rejects_fundraising_claim() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "funding/team witness")
    candidate = deepcopy(payload)
    candidate["fundraising_allowed"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "funding_team_root_value_invalid" for finding in findings)


def test_witness_rejects_hiring_claim() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "funding/team witness")
    candidate = deepcopy(payload)
    candidate["hiring_allowed"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "funding_team_root_value_invalid" for finding in findings)


def test_witness_rejects_equity_promise_claim() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "funding/team witness")
    candidate = deepcopy(payload)
    candidate["equity_promise_allowed"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "funding_team_root_value_invalid" for finding in findings)


def test_witness_rejects_surface_state_promotion() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "funding/team witness")
    candidate = deepcopy(payload)
    candidate["funding_team_surfaces"][0]["state"] = "Ready"

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "funding_team_surface_inventory_invalid" for finding in findings)
    assert any(finding.rule_id == "funding_team_surface_state_invalid" for finding in findings)


def test_witness_rejects_investor_email_value() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "funding/team witness")
    candidate = deepcopy(payload)
    candidate["funding_team_surfaces"][0]["public_safe_note"] = "investor email=person@example.test"

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "funding_team_forbidden_private_value_pattern" for finding in findings)


def test_witness_rejects_fundraising_ready_phrase() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "funding/team witness")
    candidate = deepcopy(payload)
    candidate["next_action"] = "fundraising is ready after this draft"

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "funding_team_forbidden_promotion_phrase" for finding in findings)
