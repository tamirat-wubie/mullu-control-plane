"""Tests for the Foundation Mode capability-roadmap boundary validator.

Purpose: prove capability-roadmap preparation stays local and does not
authorize capability availability, roadmap commitments, delivery promises,
dependency activation, customer commitments, pilot commitments, support
commitments, pricing commitments, money movement, publication, or deployment.
Governance scope: Foundation Mode, public-safe roadmap posture,
private-value exclusion, roadmap-commitment blocking, publication blocking,
money-movement blocking, and deployment blocking.
Dependencies: scripts.validate_foundation_capability_roadmap_boundary.
Invariants: capability-roadmap surfaces remain AwaitingEvidence and reject
availability, roadmap, delivery, customer, pricing, publication, or
private-value drift.
"""

from __future__ import annotations

from copy import deepcopy
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validate_foundation_capability_roadmap_boundary import (  # noqa: E402
    DEFAULT_PACKET_PATH,
    EXPECTED_SURFACES,
    EXPECTED_WITNESS_ID,
    load_json_object,
    validate_foundation_capability_roadmap_boundary,
    validate_packet,
)


def test_foundation_capability_roadmap_boundary_artifacts_pass() -> None:
    assert validate_foundation_capability_roadmap_boundary() == []


def test_capability_roadmap_witness_has_expected_identity_and_blockers() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "capability-roadmap witness")

    assert payload["witness_id"] == EXPECTED_WITNESS_ID
    assert tuple(
        (surface["surface_id"], surface["surface_type"], surface["state"])
        for surface in payload["capability_roadmap_surfaces"]
    ) == EXPECTED_SURFACES
    assert payload["capability_inventory_complete_claimed"] is False
    assert payload["capability_availability_claimed"] is False
    assert payload["roadmap_commitment_claimed"] is False
    assert payload["delivery_date_promised"] is False
    assert payload["dependency_activation_allowed"] is False
    assert payload["customer_commitment_allowed"] is False
    assert payload["pilot_commitment_allowed"] is False
    assert payload["support_commitment_allowed"] is False
    assert payload["pricing_commitment_allowed"] is False
    assert payload["money_movement_allowed"] is False
    assert payload["deployment_allowed"] is False


def test_witness_rejects_capability_availability_claims() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "capability-roadmap witness")
    candidate = deepcopy(payload)
    candidate["capability_inventory_complete_claimed"] = True
    candidate["capability_availability_claimed"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "capability_roadmap_root_value_invalid" for finding in findings)
    assert not any(finding.rule_id == "capability_roadmap_surface_state_invalid" for finding in findings)


def test_witness_rejects_roadmap_commitment_claims() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "capability-roadmap witness")
    candidate = deepcopy(payload)
    candidate["roadmap_commitment_claimed"] = True
    candidate["delivery_date_promised"] = True
    candidate["sequencing_final_claimed"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "capability_roadmap_root_value_invalid" for finding in findings)
    assert candidate["delivery_date_promised"] is True


def test_witness_rejects_surface_state_promotion() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "capability-roadmap witness")
    candidate = deepcopy(payload)
    candidate["capability_roadmap_surfaces"][0]["state"] = "Ready"

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "capability_roadmap_surface_inventory_invalid" for finding in findings)
    assert any(finding.rule_id == "capability_roadmap_surface_state_invalid" for finding in findings)


def test_witness_rejects_customer_or_roadmap_value() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "capability-roadmap witness")
    candidate = deepcopy(payload)
    candidate["capability_roadmap_surfaces"][0]["public_safe_note"] = "customer_id=123 roadmap_target=august"

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "capability_roadmap_forbidden_private_value_pattern" for finding in findings)
    assert not any(finding.rule_id == "capability_roadmap_root_value_invalid" for finding in findings)


def test_witness_rejects_roadmap_promotion_phrase() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "capability-roadmap witness")
    candidate = deepcopy(payload)
    candidate["next_action"] = "roadmap is committed after this draft"

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "capability_roadmap_forbidden_promotion_phrase" for finding in findings)
    assert any(finding.rule_id == "capability_roadmap_next_action_invalid" for finding in findings)
