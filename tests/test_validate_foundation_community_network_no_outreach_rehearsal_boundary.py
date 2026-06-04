"""Tests for the Foundation Mode community/network no-outreach rehearsal validator.

Purpose: prove no-outreach rehearsal stays local and does not authorize
outreach, posting, messaging, help requests, collaborator recruitment,
partnership outreach, mentor requests, feedback requests, event participation,
referral requests, contact lists, personal-data collection, external-account
use, customer access, publication, secrets, or deployment.
Governance scope: Foundation Mode, community/network no-outreach rehearsal,
message/post stop rules, relationship-request stop rules, contact-list
exclusion, personal-data exclusion, customer-access blocking, and deployment
blocking.
Dependencies: scripts.validate_foundation_community_network_no_outreach_rehearsal_boundary.
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

from scripts.validate_foundation_community_network_no_outreach_rehearsal_boundary import (  # noqa: E402
    DEFAULT_PACKET_PATH,
    EXPECTED_SURFACES,
    EXPECTED_WITNESS_ID,
    load_json_object,
    validate_foundation_community_network_no_outreach_rehearsal_boundary,
    validate_packet,
)


def test_foundation_community_network_no_outreach_rehearsal_boundary_artifacts_pass() -> None:
    assert validate_foundation_community_network_no_outreach_rehearsal_boundary() == []


def test_no_outreach_rehearsal_witness_has_expected_identity_and_blockers() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "community/network no-outreach rehearsal witness")

    assert payload["witness_id"] == EXPECTED_WITNESS_ID
    assert tuple(
        (surface["surface_id"], surface["surface_type"], surface["state"])
        for surface in payload["surfaces"]
    ) == EXPECTED_SURFACES
    assert payload["no_outreach_rehearsal_executed"] is False
    assert payload["community_outreach_allowed"] is False
    assert payload["social_post_publication_allowed"] is False
    assert payload["forum_post_publication_allowed"] is False
    assert payload["direct_message_allowed"] is False
    assert payload["contact_list_recorded"] is False
    assert payload["personal_data_collection_allowed"] is False
    assert payload["customer_access_allowed"] is False
    assert payload["deployment_allowed"] is False


def test_witness_rejects_rehearsal_outreach_post_and_message_claims() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "community/network no-outreach rehearsal witness")
    candidate = deepcopy(payload)
    candidate["no_outreach_rehearsal_executed"] = True
    candidate["community_outreach_allowed"] = True
    candidate["social_post_publication_allowed"] = True
    candidate["forum_post_publication_allowed"] = True
    candidate["direct_message_allowed"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "community_network_no_outreach_rehearsal_root_value_invalid" for finding in findings)


def test_witness_rejects_relationship_feedback_event_and_referral_claims() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "community/network no-outreach rehearsal witness")
    candidate = deepcopy(payload)
    candidate["help_request_allowed"] = True
    candidate["collaborator_recruitment_allowed"] = True
    candidate["partnership_outreach_allowed"] = True
    candidate["mentor_request_allowed"] = True
    candidate["public_feedback_request_allowed"] = True
    candidate["event_participation_allowed"] = True
    candidate["referral_request_allowed"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "community_network_no_outreach_rehearsal_root_value_invalid" for finding in findings)


def test_witness_rejects_contact_account_customer_publication_secret_and_deployment_claims() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "community/network no-outreach rehearsal witness")
    candidate = deepcopy(payload)
    candidate["contact_list_recorded"] = True
    candidate["personal_data_collection_allowed"] = True
    candidate["external_account_use_allowed"] = True
    candidate["public_profile_claimed"] = True
    candidate["customer_access_allowed"] = True
    candidate["external_publication_allowed"] = True
    candidate["secret_material_allowed"] = True
    candidate["deployment_allowed"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "community_network_no_outreach_rehearsal_root_value_invalid" for finding in findings)


def test_witness_rejects_surface_state_promotion() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "community/network no-outreach rehearsal witness")
    candidate = deepcopy(payload)
    candidate["surfaces"][0]["state"] = "Ready"

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "community_network_no_outreach_rehearsal_surface_inventory_invalid" for finding in findings)
    assert any(finding.rule_id == "community_network_no_outreach_rehearsal_surface_state_invalid" for finding in findings)


def test_witness_rejects_private_contact_value_shape() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "community/network no-outreach rehearsal witness")
    candidate = deepcopy(payload)
    candidate["surfaces"][0]["public_safe_note"] = "contact_list=private-people"

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "community_network_no_outreach_rehearsal_forbidden_value_pattern" for finding in findings)


def test_witness_rejects_outreach_promotion_phrase() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "community/network no-outreach rehearsal witness")
    candidate = deepcopy(payload)
    candidate["next_action"] = "community outreach has started"

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "community_network_no_outreach_rehearsal_forbidden_promotion_phrase" for finding in findings)
