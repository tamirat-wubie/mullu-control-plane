"""Tests for the Foundation Mode deployment-deferral boundary validator.

Purpose: prove deployment deferral stays local and does not authorize
deployment approval, cloud activation, public endpoints, production health,
runtime readiness, customer access, spending, credential use, secret use,
migration execution, DNS mutation, external publication, or deployment claims.
Governance scope: Foundation Mode, deployment deferral, public-safe planning
witness, private-value exclusion, exposure blocking, cost blocking, credential
blocking, customer-access blocking, and deployment blocking.
Dependencies: scripts.validate_foundation_deployment_deferral_boundary.
Invariants: deployment-deferral surfaces remain AwaitingEvidence and reject
readiness promotion or private value drift.
"""

from __future__ import annotations

from copy import deepcopy
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validate_foundation_deployment_deferral_boundary import (  # noqa: E402
    DEFAULT_PACKET_PATH,
    EXPECTED_SURFACES,
    EXPECTED_WITNESS_ID,
    load_json_object,
    validate_foundation_deployment_deferral_boundary,
    validate_packet,
)


def test_foundation_deployment_deferral_boundary_artifacts_pass() -> None:
    assert validate_foundation_deployment_deferral_boundary() == []


def test_deployment_deferral_witness_has_expected_identity_and_blockers() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "deployment-deferral witness")

    assert payload["witness_id"] == EXPECTED_WITNESS_ID
    assert tuple(
        (surface["surface_id"], surface["surface_type"], surface["state"])
        for surface in payload["deployment_deferral_surfaces"]
    ) == EXPECTED_SURFACES
    assert payload["deployment_plan_approved"] is False
    assert payload["cloud_activation_allowed"] is False
    assert payload["public_endpoint_allowed"] is False
    assert payload["production_health_claimed"] is False
    assert payload["customer_access_allowed"] is False
    assert payload["deployment_allowed"] is False


def test_witness_rejects_deployment_plan_approval() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "deployment-deferral witness")
    candidate = deepcopy(payload)
    candidate["deployment_plan_approved"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "deployment_deferral_root_value_invalid" for finding in findings)


def test_witness_rejects_cloud_or_endpoint_activation() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "deployment-deferral witness")
    candidate = deepcopy(payload)
    candidate["cloud_activation_allowed"] = True
    candidate["public_endpoint_allowed"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "deployment_deferral_root_value_invalid" for finding in findings)


def test_witness_rejects_customer_access_and_spending() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "deployment-deferral witness")
    candidate = deepcopy(payload)
    candidate["customer_access_allowed"] = True
    candidate["spending_allowed"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "deployment_deferral_root_value_invalid" for finding in findings)


def test_witness_rejects_surface_state_promotion() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "deployment-deferral witness")
    candidate = deepcopy(payload)
    candidate["deployment_deferral_surfaces"][0]["state"] = "Ready"

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "deployment_deferral_surface_inventory_invalid" for finding in findings)
    assert any(finding.rule_id == "deployment_deferral_surface_state_invalid" for finding in findings)


def test_witness_rejects_endpoint_or_provider_value() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "deployment-deferral witness")
    candidate = deepcopy(payload)
    candidate["deployment_deferral_surfaces"][0]["public_safe_note"] = "provider_id=prod; endpoint=https://example.com"

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "deployment_deferral_forbidden_private_value_pattern" for finding in findings)


def test_witness_rejects_deployment_ready_phrase() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "deployment-deferral witness")
    candidate = deepcopy(payload)
    candidate["next_action"] = "deployment is ready after this draft"

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "deployment_deferral_forbidden_promotion_phrase" for finding in findings)
