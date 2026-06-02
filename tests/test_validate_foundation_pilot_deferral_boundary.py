"""Tests for the Foundation Mode pilot-deferral boundary validator.

Purpose: prove pilot deferral stays local and does not authorize pilot
execution, participant invitation, access channels, waitlists, beta, customer
access, personal-data collection, market validation, support readiness, legal
clearance, paid pilots, external publication, or deployment claims.
Governance scope: Foundation Mode, pilot deferral, public-safe planning
witness, private-value exclusion, intake blocking, support-duty blocking,
privacy caution, legal/business restraint, public-claim restraint, and
deployment blocking.
Dependencies: scripts.validate_foundation_pilot_deferral_boundary.
Invariants: pilot-deferral surfaces remain AwaitingEvidence and reject
readiness promotion or private value drift.
"""

from __future__ import annotations

from copy import deepcopy
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validate_foundation_pilot_deferral_boundary import (  # noqa: E402
    DEFAULT_PACKET_PATH,
    EXPECTED_SURFACES,
    EXPECTED_WITNESS_ID,
    load_json_object,
    validate_foundation_pilot_deferral_boundary,
    validate_packet,
)


def test_foundation_pilot_deferral_boundary_artifacts_pass() -> None:
    assert validate_foundation_pilot_deferral_boundary() == []


def test_pilot_deferral_witness_has_expected_identity_and_blockers() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "pilot-deferral witness")

    assert payload["witness_id"] == EXPECTED_WITNESS_ID
    assert tuple(
        (surface["surface_id"], surface["surface_type"], surface["state"])
        for surface in payload["pilot_deferral_surfaces"]
    ) == EXPECTED_SURFACES
    assert payload["pilot_execution_allowed"] is False
    assert payload["participant_invitation_allowed"] is False
    assert payload["access_channel_allowed"] is False
    assert payload["customer_access_allowed"] is False
    assert payload["market_validation_claimed"] is False
    assert payload["deployment_allowed"] is False


def test_witness_rejects_pilot_execution() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "pilot-deferral witness")
    candidate = deepcopy(payload)
    candidate["pilot_execution_allowed"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "pilot_deferral_root_value_invalid" for finding in findings)


def test_witness_rejects_access_opening() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "pilot-deferral witness")
    candidate = deepcopy(payload)
    candidate["participant_invitation_allowed"] = True
    candidate["access_channel_allowed"] = True
    candidate["waitlist_allowed"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "pilot_deferral_root_value_invalid" for finding in findings)


def test_witness_rejects_market_or_support_claim() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "pilot-deferral witness")
    candidate = deepcopy(payload)
    candidate["market_validation_claimed"] = True
    candidate["support_ready_claimed"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "pilot_deferral_root_value_invalid" for finding in findings)


def test_witness_rejects_surface_state_promotion() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "pilot-deferral witness")
    candidate = deepcopy(payload)
    candidate["pilot_deferral_surfaces"][0]["state"] = "Ready"

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "pilot_deferral_surface_inventory_invalid" for finding in findings)
    assert any(finding.rule_id == "pilot_deferral_surface_state_invalid" for finding in findings)


def test_witness_rejects_participant_or_intake_value() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "pilot-deferral witness")
    candidate = deepcopy(payload)
    candidate["pilot_deferral_surfaces"][0]["public_safe_note"] = "participant_email=person@example.com; form_url=https://example.com"

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "pilot_deferral_forbidden_private_value_pattern" for finding in findings)


def test_witness_rejects_pilot_ready_phrase() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "pilot-deferral witness")
    candidate = deepcopy(payload)
    candidate["next_action"] = "pilot is ready after this draft"

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "pilot_deferral_forbidden_promotion_phrase" for finding in findings)
