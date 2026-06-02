"""Tests for the Foundation Mode support-readiness boundary validator.

Purpose: prove support preparation stays local and does not authorize customer
support, SLA, incident-response readiness, onboarding, paid support, customer
access, private-value storage, or deployment claims.
Governance scope: Foundation Mode, support posture, incident-preparation
posture, public-label witness, private-value exclusion, and deployment blocking.
Dependencies: scripts.validate_foundation_support_readiness_boundary.
Invariants: support surfaces remain AwaitingEvidence and reject readiness
promotion or private routing drift.
"""

from __future__ import annotations

from copy import deepcopy
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validate_foundation_support_readiness_boundary import (  # noqa: E402
    DEFAULT_PACKET_PATH,
    EXPECTED_SURFACES,
    EXPECTED_WITNESS_ID,
    load_json_object,
    validate_foundation_support_readiness_boundary,
    validate_packet,
)


def test_foundation_support_readiness_boundary_artifacts_pass() -> None:
    assert validate_foundation_support_readiness_boundary() == []


def test_support_readiness_witness_has_expected_identity_and_blockers() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "support-readiness witness")

    assert payload["witness_id"] == EXPECTED_WITNESS_ID
    assert tuple(
        (surface["surface_id"], surface["surface_type"], surface["state"])
        for surface in payload["support_surfaces"]
    ) == EXPECTED_SURFACES
    assert payload["customer_support_open"] is False
    assert payload["support_sla_claimed"] is False
    assert payload["incident_response_ready_claimed"] is False
    assert payload["support_mailbox_deliverability_claimed"] is False
    assert payload["customer_access_allowed"] is False
    assert payload["deployment_allowed"] is False


def test_witness_rejects_support_opening_claim() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "support-readiness witness")
    candidate = deepcopy(payload)
    candidate["customer_support_open"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "support_readiness_root_value_invalid" for finding in findings)


def test_witness_rejects_sla_claim() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "support-readiness witness")
    candidate = deepcopy(payload)
    candidate["support_sla_claimed"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "support_readiness_root_value_invalid" for finding in findings)


def test_witness_rejects_incident_readiness_claim() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "support-readiness witness")
    candidate = deepcopy(payload)
    candidate["incident_response_ready_claimed"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "support_readiness_root_value_invalid" for finding in findings)


def test_witness_rejects_surface_state_promotion() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "support-readiness witness")
    candidate = deepcopy(payload)
    candidate["support_surfaces"][0]["state"] = "Ready"

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "support_readiness_surface_inventory_invalid" for finding in findings)
    assert any(finding.rule_id == "support_readiness_surface_state_invalid" for finding in findings)


def test_witness_rejects_private_routing_value() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "support-readiness witness")
    candidate = deepcopy(payload)
    candidate["support_surfaces"][0]["public_safe_note"] = "mailbox target=private-inbox-id"

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "support_readiness_forbidden_private_value_pattern" for finding in findings)


def test_witness_rejects_support_ready_phrase() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "support-readiness witness")
    candidate = deepcopy(payload)
    candidate["next_action"] = "support-ready after this draft"

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "support_readiness_forbidden_promotion_phrase" for finding in findings)
