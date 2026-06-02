"""Tests for the Foundation Mode customer-access boundary validator.

Purpose: prove customer-access preparation stays local and does not authorize
customer access, invitations, account creation, onboarding readiness, support
commitments, terms/privacy readiness, personal-data collection, paid access,
pilot access, beta access, waitlists, external publication, or deployment.
Governance scope: Foundation Mode, customer-access posture, public-safe
planning witness, private-value exclusion, personal-data exclusion, access
blocking, and deployment blocking.
Dependencies: scripts.validate_foundation_customer_access_boundary.
Invariants: customer-access surfaces remain AwaitingEvidence and reject
activation, readiness promotion, or private value drift.
"""

from __future__ import annotations

from copy import deepcopy
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validate_foundation_customer_access_boundary import (  # noqa: E402
    DEFAULT_PACKET_PATH,
    EXPECTED_SURFACES,
    EXPECTED_WITNESS_ID,
    load_json_object,
    validate_foundation_customer_access_boundary,
    validate_packet,
)


def test_foundation_customer_access_boundary_artifacts_pass() -> None:
    assert validate_foundation_customer_access_boundary() == []


def test_customer_access_witness_has_expected_identity_and_blockers() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "customer-access witness")

    assert payload["witness_id"] == EXPECTED_WITNESS_ID
    assert tuple(
        (surface["surface_id"], surface["surface_type"], surface["state"])
        for surface in payload["customer_access_surfaces"]
    ) == EXPECTED_SURFACES
    assert payload["customer_access_allowed"] is False
    assert payload["customer_invitation_allowed"] is False
    assert payload["account_creation_allowed"] is False
    assert payload["personal_data_collection_allowed"] is False
    assert payload["waitlist_open"] is False
    assert payload["deployment_allowed"] is False


def test_witness_rejects_customer_access_claim() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "customer-access witness")
    candidate = deepcopy(payload)
    candidate["customer_access_allowed"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "customer_access_root_value_invalid" for finding in findings)


def test_witness_rejects_account_creation_claim() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "customer-access witness")
    candidate = deepcopy(payload)
    candidate["account_creation_allowed"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "customer_access_root_value_invalid" for finding in findings)


def test_witness_rejects_personal_data_collection_claim() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "customer-access witness")
    candidate = deepcopy(payload)
    candidate["personal_data_collection_allowed"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "customer_access_root_value_invalid" for finding in findings)


def test_witness_rejects_surface_state_promotion() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "customer-access witness")
    candidate = deepcopy(payload)
    candidate["customer_access_surfaces"][0]["state"] = "Ready"

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "customer_access_surface_inventory_invalid" for finding in findings)
    assert any(finding.rule_id == "customer_access_surface_state_invalid" for finding in findings)


def test_witness_rejects_invite_link_value() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "customer-access witness")
    candidate = deepcopy(payload)
    candidate["customer_access_surfaces"][0]["public_safe_note"] = "invite_link=https://example.test/invite"

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "customer_access_forbidden_private_value_pattern" for finding in findings)


def test_witness_rejects_customer_access_open_phrase() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "customer-access witness")
    candidate = deepcopy(payload)
    candidate["next_action"] = "customer access is open after this draft"

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "customer_access_forbidden_promotion_phrase" for finding in findings)
