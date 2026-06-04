"""Tests for the Foundation Mode pilot-deferral rehearsal validator.

Purpose: prove pilot-deferral rehearsal stays local and does not authorize
pilot execution, participant invitation, access channels, waitlists, signup
paths, customer access, personal-data collection, market validation, support
readiness, legal clearance, paid pilots, payment, money movement, publication,
secrets, or deployment claims.
Governance scope: Foundation Mode, pilot-deferral rehearsal, local stop-rule
drafting, private-value exclusion, intake blocking, support-duty blocking,
legal/business restraint, payment blocking, public-claim restraint, and
deployment blocking.
Dependencies: scripts.validate_foundation_pilot_deferral_rehearsal_boundary.
Invariants: rehearsal surfaces remain AwaitingEvidence and reject private
value drift, execution drift, and promotion drift.
"""

from __future__ import annotations

from copy import deepcopy
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validate_foundation_pilot_deferral_rehearsal_boundary import (  # noqa: E402
    DEFAULT_PACKET_PATH,
    EXPECTED_SURFACES,
    EXPECTED_WITNESS_ID,
    load_json_object,
    validate_foundation_pilot_deferral_rehearsal_boundary,
    validate_packet,
)


def test_foundation_pilot_deferral_rehearsal_boundary_artifacts_pass() -> None:
    assert validate_foundation_pilot_deferral_rehearsal_boundary() == []


def test_pilot_deferral_rehearsal_witness_has_expected_identity_and_blockers() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "pilot-deferral rehearsal witness")

    assert payload["witness_id"] == EXPECTED_WITNESS_ID
    assert tuple(
        (surface["surface_id"], surface["surface_type"], surface["state"])
        for surface in payload["surfaces"]
    ) == EXPECTED_SURFACES
    assert payload["deferral_rehearsal_executed"] is False
    assert payload["pilot_execution_allowed"] is False
    assert payload["participant_invitation_allowed"] is False
    assert payload["access_channel_opening_allowed"] is False
    assert payload["waitlist_opening_allowed"] is False
    assert payload["pilot_signup_open"] is False
    assert payload["customer_access_allowed"] is False
    assert payload["deployment_allowed"] is False


def test_witness_rejects_rehearsal_execution_and_pilot_execution() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "pilot-deferral rehearsal witness")
    candidate = deepcopy(payload)
    candidate["deferral_rehearsal_executed"] = True
    candidate["pilot_execution_allowed"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "pilot_deferral_rehearsal_root_value_invalid" for finding in findings)


def test_witness_rejects_participant_access_waitlist_and_signup_claims() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "pilot-deferral rehearsal witness")
    candidate = deepcopy(payload)
    candidate["participant_invitation_allowed"] = True
    candidate["access_channel_opening_allowed"] = True
    candidate["waitlist_opening_allowed"] = True
    candidate["pilot_signup_open"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "pilot_deferral_rehearsal_root_value_invalid" for finding in findings)


def test_witness_rejects_customer_data_support_legal_payment_and_deployment_claims() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "pilot-deferral rehearsal witness")
    candidate = deepcopy(payload)
    candidate["customer_access_allowed"] = True
    candidate["personal_data_collection_allowed"] = True
    candidate["support_readiness_claimed"] = True
    candidate["legal_clearance_claimed"] = True
    candidate["payment_enabled"] = True
    candidate["money_movement_allowed"] = True
    candidate["deployment_allowed"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "pilot_deferral_rehearsal_root_value_invalid" for finding in findings)


def test_witness_rejects_surface_state_promotion() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "pilot-deferral rehearsal witness")
    candidate = deepcopy(payload)
    candidate["surfaces"][0]["state"] = "Ready"

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "pilot_deferral_rehearsal_surface_inventory_invalid" for finding in findings)
    assert any(finding.rule_id == "pilot_deferral_rehearsal_surface_state_invalid" for finding in findings)


def test_witness_rejects_participant_payment_or_private_value_shape() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "pilot-deferral rehearsal witness")
    candidate = deepcopy(payload)
    candidate["surfaces"][0]["public_safe_note"] = "participant_email=person@example.com; payment_id=private-value"

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "pilot_deferral_rehearsal_forbidden_value_pattern" for finding in findings)


def test_witness_rejects_pilot_promotion_phrase() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "pilot-deferral rehearsal witness")
    candidate = deepcopy(payload)
    candidate["next_action"] = "pilot is ready after this rehearsal"

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "pilot_deferral_rehearsal_forbidden_promotion_phrase" for finding in findings)
