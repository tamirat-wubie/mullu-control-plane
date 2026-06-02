"""Tests for the Foundation Mode community/network boundary validator.

Purpose: prove community/network preparation stays local and does not authorize
community outreach, social/forum publication, direct messaging, collaborator
recruitment, partnership outreach, mentor requests, public feedback requests,
event participation, contact-list recording, personal-data collection,
external-account use, customer access, external publication, or deployment
claims.
Governance scope: Foundation Mode, solo-operator community posture,
public-safe local questions, private-value exclusion, outside-contact blocking,
publication blocking, and deployment blocking.
Dependencies: scripts.validate_foundation_community_network_boundary.
Invariants: community/network surfaces remain AwaitingEvidence and reject
outside-contact, publication, or private-value drift.
"""

from __future__ import annotations

from copy import deepcopy
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validate_foundation_community_network_boundary import (  # noqa: E402
    DEFAULT_PACKET_PATH,
    EXPECTED_SURFACES,
    EXPECTED_WITNESS_ID,
    load_json_object,
    validate_foundation_community_network_boundary,
    validate_packet,
)


def test_foundation_community_network_boundary_artifacts_pass() -> None:
    assert validate_foundation_community_network_boundary() == []


def test_community_network_witness_has_expected_identity_and_blockers() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "community/network witness")

    assert payload["witness_id"] == EXPECTED_WITNESS_ID
    assert tuple(
        (surface["surface_id"], surface["surface_type"], surface["state"])
        for surface in payload["community_network_surfaces"]
    ) == EXPECTED_SURFACES
    assert payload["community_outreach_allowed"] is False
    assert payload["social_post_publication_allowed"] is False
    assert payload["forum_post_publication_allowed"] is False
    assert payload["direct_message_allowed"] is False
    assert payload["collaborator_recruitment_allowed"] is False
    assert payload["partnership_outreach_allowed"] is False
    assert payload["personal_data_collection_allowed"] is False
    assert payload["external_account_use_allowed"] is False
    assert payload["deployment_allowed"] is False


def test_witness_rejects_outreach_claim() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "community/network witness")
    candidate = deepcopy(payload)
    candidate["community_outreach_allowed"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "community_network_root_value_invalid" for finding in findings)


def test_witness_rejects_publication_claims() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "community/network witness")
    candidate = deepcopy(payload)
    candidate["social_post_publication_allowed"] = True
    candidate["forum_post_publication_allowed"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "community_network_root_value_invalid" for finding in findings)


def test_witness_rejects_relationship_claims() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "community/network witness")
    candidate = deepcopy(payload)
    candidate["collaborator_recruitment_allowed"] = True
    candidate["partnership_outreach_allowed"] = True
    candidate["mentor_request_allowed"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "community_network_root_value_invalid" for finding in findings)


def test_witness_rejects_surface_state_promotion() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "community/network witness")
    candidate = deepcopy(payload)
    candidate["community_network_surfaces"][0]["state"] = "Ready"

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "community_network_surface_inventory_invalid" for finding in findings)
    assert any(finding.rule_id == "community_network_surface_state_invalid" for finding in findings)


def test_witness_rejects_contact_email_or_profile_value() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "community/network witness")
    candidate = deepcopy(payload)
    candidate["community_network_surfaces"][0]["public_safe_note"] = "contact email=person@example.test"

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "community_network_forbidden_private_value_pattern" for finding in findings)


def test_witness_rejects_community_outreach_started_phrase() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "community/network witness")
    candidate = deepcopy(payload)
    candidate["next_action"] = "community outreach has started after this draft"

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "community_network_forbidden_promotion_phrase" for finding in findings)
