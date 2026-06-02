"""Tests for the Foundation Mode intake/onboarding boundary validator.

Purpose: prove intake preparation stays local and does not authorize active
forms, waitlists, pilot signup, personal data collection, CRM import, outreach,
onboarding, paid access, customer access, or deployment claims.
Governance scope: Foundation Mode, intake posture, onboarding posture,
public-safe planning witness, private-value exclusion, and deployment blocking.
Dependencies: scripts.validate_foundation_intake_onboarding_boundary.
Invariants: intake surfaces remain AwaitingEvidence and reject activation or
private value drift.
"""

from __future__ import annotations

from copy import deepcopy
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validate_foundation_intake_onboarding_boundary import (  # noqa: E402
    DEFAULT_PACKET_PATH,
    EXPECTED_SURFACES,
    EXPECTED_WITNESS_ID,
    load_json_object,
    validate_foundation_intake_onboarding_boundary,
    validate_packet,
)


def test_foundation_intake_onboarding_boundary_artifacts_pass() -> None:
    assert validate_foundation_intake_onboarding_boundary() == []


def test_intake_onboarding_witness_has_expected_identity_and_blockers() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "intake/onboarding witness")

    assert payload["witness_id"] == EXPECTED_WITNESS_ID
    assert tuple(
        (surface["surface_id"], surface["surface_type"], surface["state"])
        for surface in payload["intake_surfaces"]
    ) == EXPECTED_SURFACES
    assert payload["intake_open"] is False
    assert payload["waitlist_open"] is False
    assert payload["pilot_signup_open"] is False
    assert payload["pii_collection_allowed"] is False
    assert payload["customer_access_allowed"] is False
    assert payload["deployment_allowed"] is False


def test_witness_rejects_intake_opening_claim() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "intake/onboarding witness")
    candidate = deepcopy(payload)
    candidate["intake_open"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "intake_onboarding_root_value_invalid" for finding in findings)


def test_witness_rejects_waitlist_opening_claim() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "intake/onboarding witness")
    candidate = deepcopy(payload)
    candidate["waitlist_open"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "intake_onboarding_root_value_invalid" for finding in findings)


def test_witness_rejects_personal_data_collection_claim() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "intake/onboarding witness")
    candidate = deepcopy(payload)
    candidate["pii_collection_allowed"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "intake_onboarding_root_value_invalid" for finding in findings)


def test_witness_rejects_surface_state_promotion() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "intake/onboarding witness")
    candidate = deepcopy(payload)
    candidate["intake_surfaces"][0]["state"] = "Ready"

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "intake_onboarding_surface_inventory_invalid" for finding in findings)
    assert any(finding.rule_id == "intake_onboarding_surface_state_invalid" for finding in findings)


def test_witness_rejects_form_url_value() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "intake/onboarding witness")
    candidate = deepcopy(payload)
    candidate["intake_surfaces"][0]["public_safe_note"] = "form url=https://example.test/intake"

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "intake_onboarding_forbidden_private_value_pattern" for finding in findings)


def test_witness_rejects_intake_open_phrase() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "intake/onboarding witness")
    candidate = deepcopy(payload)
    candidate["next_action"] = "intake is open after this draft"

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "intake_onboarding_forbidden_promotion_phrase" for finding in findings)
