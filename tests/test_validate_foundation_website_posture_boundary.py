"""Tests for the Foundation Mode website-posture boundary validator.

Purpose: prove website-posture preparation stays local and does not authorize
website mutation, external publication, access invitation, waitlist, beta,
pilot signup, customer intake, production-runtime, endpoint-readiness,
paid-launch, or deployment claims.
Governance scope: Foundation Mode, static website copy, product-route copy,
proof-route copy, public-naming alignment, private-value exclusion, and
deployment blocking.
Dependencies: scripts.validate_foundation_website_posture_boundary.
Invariants: website surfaces remain AwaitingEvidence and reject promotion or
private publication drift.
"""

from __future__ import annotations

from copy import deepcopy
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validate_foundation_website_posture_boundary import (  # noqa: E402
    DEFAULT_PACKET_PATH,
    EXPECTED_SURFACES,
    EXPECTED_WITNESS_ID,
    load_json_object,
    validate_foundation_website_posture_boundary,
    validate_packet,
)


def test_foundation_website_posture_boundary_artifacts_pass() -> None:
    assert validate_foundation_website_posture_boundary() == []


def test_website_posture_witness_has_expected_identity_and_blockers() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "website-posture witness")

    assert payload["witness_id"] == EXPECTED_WITNESS_ID
    assert tuple(
        (surface["surface_id"], surface["surface_type"], surface["state"])
        for surface in payload["website_surfaces"]
    ) == EXPECTED_SURFACES
    assert payload["website_mutation_allowed"] is False
    assert payload["external_publication_allowed"] is False
    assert payload["access_invitation_allowed"] is False
    assert payload["waitlist_open"] is False
    assert payload["beta_invitation_allowed"] is False
    assert payload["production_runtime_claimed"] is False
    assert payload["endpoint_readiness_claimed"] is False
    assert payload["deployment_allowed"] is False


def test_witness_rejects_website_mutation_allowance() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "website-posture witness")
    candidate = deepcopy(payload)
    candidate["website_mutation_allowed"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "website_posture_root_value_invalid" for finding in findings)


def test_witness_rejects_access_invitation_allowance() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "website-posture witness")
    candidate = deepcopy(payload)
    candidate["access_invitation_allowed"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "website_posture_root_value_invalid" for finding in findings)


def test_witness_rejects_waitlist_opening() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "website-posture witness")
    candidate = deepcopy(payload)
    candidate["waitlist_open"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "website_posture_root_value_invalid" for finding in findings)


def test_witness_rejects_surface_state_promotion() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "website-posture witness")
    candidate = deepcopy(payload)
    candidate["website_surfaces"][0]["state"] = "Ready"

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "website_posture_surface_inventory_invalid" for finding in findings)
    assert any(finding.rule_id == "website_posture_surface_state_invalid" for finding in findings)


def test_witness_rejects_route_target_value() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "website-posture witness")
    candidate = deepcopy(payload)
    candidate["website_surfaces"][0]["public_safe_note"] = "route target=private-route"

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "website_posture_forbidden_private_value_pattern" for finding in findings)


def test_witness_rejects_request_access_phrase() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "website-posture witness")
    candidate = deepcopy(payload)
    candidate["next_action"] = "request access after this draft"

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "website_posture_forbidden_promotion_phrase" for finding in findings)
