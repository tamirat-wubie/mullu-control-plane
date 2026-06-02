"""Tests for the Foundation Mode claim-boundary validator.

Purpose: prove claim-boundary preparation stays local and does not authorize
production-health, endpoint-readiness, customer-readiness, pilot-readiness,
legal-clearance, commercial-readiness, public-launch, compliance-certification,
external-publication, or deployment claims.
Governance scope: Foundation Mode, claim posture, public-copy separation,
private-value exclusion, and deployment blocking.
Dependencies: scripts.validate_foundation_claim_boundary.
Invariants: claim surfaces remain AwaitingEvidence and reject readiness
promotion or private claim drift.
"""

from __future__ import annotations

from copy import deepcopy
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validate_foundation_claim_boundary import (  # noqa: E402
    DEFAULT_PACKET_PATH,
    EXPECTED_SURFACES,
    EXPECTED_WITNESS_ID,
    load_json_object,
    validate_foundation_claim_boundary,
    validate_packet,
)


def test_foundation_claim_boundary_artifacts_pass() -> None:
    assert validate_foundation_claim_boundary() == []


def test_claim_witness_has_expected_identity_and_blockers() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "claim-boundary witness")

    assert payload["witness_id"] == EXPECTED_WITNESS_ID
    assert tuple(
        (surface["surface_id"], surface["surface_type"], surface["state"])
        for surface in payload["claim_surfaces"]
    ) == EXPECTED_SURFACES
    assert payload["production_health_claimed"] is False
    assert payload["endpoint_readiness_claimed"] is False
    assert payload["customer_readiness_claimed"] is False
    assert payload["pilot_readiness_claimed"] is False
    assert payload["legal_clearance_claimed"] is False
    assert payload["public_launch_claimed"] is False
    assert payload["external_publication_allowed"] is False
    assert payload["deployment_allowed"] is False


def test_witness_rejects_production_health_claim() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "claim-boundary witness")
    candidate = deepcopy(payload)
    candidate["production_health_claimed"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "claim_boundary_root_value_invalid" for finding in findings)


def test_witness_rejects_endpoint_readiness_claim() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "claim-boundary witness")
    candidate = deepcopy(payload)
    candidate["endpoint_readiness_claimed"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "claim_boundary_root_value_invalid" for finding in findings)


def test_witness_rejects_public_launch_claim() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "claim-boundary witness")
    candidate = deepcopy(payload)
    candidate["public_launch_claimed"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "claim_boundary_root_value_invalid" for finding in findings)


def test_witness_rejects_surface_state_promotion() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "claim-boundary witness")
    candidate = deepcopy(payload)
    candidate["claim_surfaces"][0]["state"] = "Ready"

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "claim_boundary_surface_inventory_invalid" for finding in findings)
    assert any(finding.rule_id == "claim_boundary_surface_state_invalid" for finding in findings)


def test_witness_rejects_endpoint_target_value() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "claim-boundary witness")
    candidate = deepcopy(payload)
    candidate["claim_surfaces"][0]["public_safe_note"] = "endpoint target=private-runtime"

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "claim_boundary_forbidden_private_value_pattern" for finding in findings)


def test_witness_rejects_production_health_ready_phrase() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "claim-boundary witness")
    candidate = deepcopy(payload)
    candidate["next_action"] = "production health is ready after this draft"

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "claim_boundary_forbidden_promotion_phrase" for finding in findings)
