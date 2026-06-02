"""Tests for the Foundation Mode market-research boundary validator.

Purpose: prove market-research preparation stays local and does not authorize
customer research, surveys, waitlists, outreach, market validation,
product-market-fit, competitor superiority, pricing claims, investor material,
personal-data collection, customer access, money movement, publication, or
deployment claims.
Governance scope: Foundation Mode, public-safe market-research posture,
private-value exclusion, customer-research blocking, publication blocking, and
deployment blocking.
Dependencies: scripts.validate_foundation_market_research_boundary.
Invariants: market-research surfaces remain AwaitingEvidence and reject
customer, pricing, investor, publication, or private-value drift.
"""

from __future__ import annotations

from copy import deepcopy
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validate_foundation_market_research_boundary import (  # noqa: E402
    DEFAULT_PACKET_PATH,
    EXPECTED_SURFACES,
    EXPECTED_WITNESS_ID,
    load_json_object,
    validate_foundation_market_research_boundary,
    validate_packet,
)


def test_foundation_market_research_boundary_artifacts_pass() -> None:
    assert validate_foundation_market_research_boundary() == []


def test_market_research_witness_has_expected_identity_and_blockers() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "market-research witness")

    assert payload["witness_id"] == EXPECTED_WITNESS_ID
    assert tuple(
        (surface["surface_id"], surface["surface_type"], surface["state"])
        for surface in payload["market_research_surfaces"]
    ) == EXPECTED_SURFACES
    assert payload["customer_research_allowed"] is False
    assert payload["survey_publication_allowed"] is False
    assert payload["waitlist_allowed"] is False
    assert payload["market_validation_claimed"] is False
    assert payload["product_market_fit_claimed"] is False
    assert payload["competitor_superiority_claimed"] is False
    assert payload["pricing_claim_allowed"] is False
    assert payload["investor_material_allowed"] is False
    assert payload["personal_data_collection_allowed"] is False
    assert payload["customer_access_allowed"] is False
    assert payload["money_movement_allowed"] is False
    assert payload["deployment_allowed"] is False


def test_witness_rejects_customer_research_and_survey_claims() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "market-research witness")
    candidate = deepcopy(payload)
    candidate["customer_research_allowed"] = True
    candidate["survey_publication_allowed"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "market_research_root_value_invalid" for finding in findings)
    assert not any(finding.rule_id == "market_research_surface_state_invalid" for finding in findings)


def test_witness_rejects_market_validation_claims() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "market-research witness")
    candidate = deepcopy(payload)
    candidate["market_validation_claimed"] = True
    candidate["product_market_fit_claimed"] = True
    candidate["market_size_claimed"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "market_research_root_value_invalid" for finding in findings)
    assert candidate["market_validation_claimed"] is True


def test_witness_rejects_surface_state_promotion() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "market-research witness")
    candidate = deepcopy(payload)
    candidate["market_research_surfaces"][0]["state"] = "Ready"

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "market_research_surface_inventory_invalid" for finding in findings)
    assert any(finding.rule_id == "market_research_surface_state_invalid" for finding in findings)


def test_witness_rejects_contact_or_competitor_value() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "market-research witness")
    candidate = deepcopy(payload)
    candidate["market_research_surfaces"][3]["public_safe_note"] = "competitor_name=example platform"

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "market_research_forbidden_private_value_pattern" for finding in findings)
    assert not any(finding.rule_id == "market_research_root_value_invalid" for finding in findings)


def test_witness_rejects_pricing_or_investor_value() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "market-research witness")
    candidate = deepcopy(payload)
    candidate["market_research_surfaces"][5]["public_safe_note"] = "price_amount=10 and investor_name=example"

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "market_research_forbidden_private_value_pattern" for finding in findings)
    assert len(findings) >= 1


def test_witness_rejects_market_validation_phrase() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "market-research witness")
    candidate = deepcopy(payload)
    candidate["next_action"] = "market is validated after this draft"

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "market_research_forbidden_promotion_phrase" for finding in findings)
    assert any(finding.rule_id == "market_research_next_action_invalid" for finding in findings)
