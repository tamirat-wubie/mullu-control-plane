"""Tests for the Foundation Mode external-infrastructure boundary validator.

Purpose: prove external-infrastructure preparation stays local and does not
authorize DNS mutation, runtime provisioning, secret placement, endpoint
publication, workflow dispatch, paid infrastructure, customer access,
publication, or deployment.
Governance scope: Foundation Mode, issue #330 prerequisite surfaces,
private-value exclusion, external-effect blocking, and readiness blocking.
Dependencies: scripts.validate_foundation_external_infrastructure_boundary.
Invariants: external-infrastructure surfaces remain AwaitingEvidence and reject
readiness promotion or private-value drift.
"""

from __future__ import annotations

from copy import deepcopy
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validate_foundation_external_infrastructure_boundary import (  # noqa: E402
    DEFAULT_PACKET_PATH,
    EXPECTED_SURFACES,
    EXPECTED_WITNESS_ID,
    load_json_object,
    validate_foundation_external_infrastructure_boundary,
    validate_packet,
)


def test_foundation_external_infrastructure_boundary_artifacts_pass() -> None:
    assert validate_foundation_external_infrastructure_boundary() == []


def test_external_infrastructure_witness_has_expected_identity_and_blockers() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "external-infrastructure witness")

    assert payload["witness_id"] == EXPECTED_WITNESS_ID
    assert tuple(
        (surface["surface_id"], surface["surface_type"], surface["state"])
        for surface in payload["external_infrastructure_surfaces"]
    ) == EXPECTED_SURFACES
    assert payload["external_infrastructure_complete_claimed"] is False
    assert payload["dns_authority_verified"] is False
    assert payload["dns_target_bound"] is False
    assert payload["dns_mutation_allowed"] is False
    assert payload["workflow_dispatch_allowed"] is False
    assert payload["deployment_allowed"] is False


def test_witness_rejects_external_infrastructure_completion_claim() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "external-infrastructure witness")
    candidate = deepcopy(payload)
    candidate["external_infrastructure_complete_claimed"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "external_infrastructure_root_value_invalid" for finding in findings)


def test_witness_rejects_dns_runtime_database_and_secret_promotion() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "external-infrastructure witness")
    candidate = deepcopy(payload)
    candidate["dns_authority_verified"] = True
    candidate["runtime_host_provisioned"] = True
    candidate["managed_database_provisioned"] = True
    candidate["secret_placement_verified"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "external_infrastructure_root_value_invalid" for finding in findings)


def test_witness_rejects_workflow_publication_customer_and_deployment_approval() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "external-infrastructure witness")
    candidate = deepcopy(payload)
    candidate["workflow_dispatch_allowed"] = True
    candidate["external_publication_allowed"] = True
    candidate["customer_access_allowed"] = True
    candidate["deployment_allowed"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "external_infrastructure_root_value_invalid" for finding in findings)


def test_witness_rejects_surface_state_promotion() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "external-infrastructure witness")
    candidate = deepcopy(payload)
    candidate["external_infrastructure_surfaces"][0]["state"] = "Ready"

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "external_infrastructure_surface_inventory_invalid" for finding in findings)
    assert any(finding.rule_id == "external_infrastructure_surface_state_invalid" for finding in findings)


def test_witness_rejects_secret_dns_or_database_value() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "external-infrastructure witness")
    candidate = deepcopy(payload)
    candidate["external_infrastructure_surfaces"][0]["public_safe_note"] = (
        "dns_target=value provider_id=value secret=value database_url=value"
    )

    findings = validate_packet(candidate)

    assert findings
    assert any(
        finding.rule_id == "external_infrastructure_forbidden_private_value_pattern"
        for finding in findings
    )


def test_witness_rejects_readiness_promotion_phrase() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "external-infrastructure witness")
    candidate = deepcopy(payload)
    candidate["next_action"] = "external infrastructure is complete and workflow is dispatched"

    findings = validate_packet(candidate)

    assert findings
    assert any(
        finding.rule_id == "external_infrastructure_forbidden_promotion_phrase"
        for finding in findings
    )
