"""Tests for the Foundation Mode system-boundary inventory boundary validator.

Purpose: prove system-boundary inventory preparation stays local and does not
authorize inventory completeness, ownership closure, trust closure, tenant
readiness, data classification closure, endpoint readiness, service binding,
integration readiness, runtime readiness, exposure approval, implementation
approval, external publication, or deployment readiness.
Governance scope: Foundation Mode, boundary surface inventory, private-value
exclusion, and readiness blocking.
Dependencies: scripts.validate_foundation_system_boundary_inventory_boundary.
Invariants: system-boundary inventory surfaces remain AwaitingEvidence and
reject readiness promotion or private-value drift.
"""

from __future__ import annotations

from copy import deepcopy
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validate_foundation_system_boundary_inventory_boundary import (  # noqa: E402
    DEFAULT_PACKET_PATH,
    EXPECTED_SURFACES,
    EXPECTED_WITNESS_ID,
    load_json_object,
    validate_foundation_system_boundary_inventory_boundary,
    validate_packet,
)


def test_foundation_system_boundary_inventory_boundary_artifacts_pass() -> None:
    assert validate_foundation_system_boundary_inventory_boundary() == []


def test_system_boundary_inventory_witness_has_expected_identity_and_blockers() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "system-boundary inventory witness")

    assert payload["witness_id"] == EXPECTED_WITNESS_ID
    assert tuple(
        (surface["surface_id"], surface["surface_type"], surface["state"])
        for surface in payload["system_boundary_inventory_surfaces"]
    ) == EXPECTED_SURFACES
    assert payload["system_boundary_inventory_complete_claimed"] is False
    assert payload["ownership_boundary_closed_claimed"] is False
    assert payload["trust_boundary_closed_claimed"] is False
    assert payload["tenant_boundary_ready_claimed"] is False
    assert payload["implementation_approval_allowed"] is False
    assert payload["deployment_allowed"] is False


def test_witness_rejects_inventory_completeness_claim() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "system-boundary inventory witness")
    candidate = deepcopy(payload)
    candidate["system_boundary_inventory_complete_claimed"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "system_boundary_inventory_root_value_invalid" for finding in findings)


def test_witness_rejects_trust_tenant_and_data_readiness() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "system-boundary inventory witness")
    candidate = deepcopy(payload)
    candidate["trust_boundary_closed_claimed"] = True
    candidate["tenant_boundary_ready_claimed"] = True
    candidate["data_boundary_classification_closed_claimed"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "system_boundary_inventory_root_value_invalid" for finding in findings)


def test_witness_rejects_service_exposure_and_implementation_approval() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "system-boundary inventory witness")
    candidate = deepcopy(payload)
    candidate["service_boundary_binding_allowed"] = True
    candidate["exposure_approval_allowed"] = True
    candidate["implementation_approval_allowed"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "system_boundary_inventory_root_value_invalid" for finding in findings)


def test_witness_rejects_surface_state_promotion() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "system-boundary inventory witness")
    candidate = deepcopy(payload)
    candidate["system_boundary_inventory_surfaces"][0]["state"] = "Ready"

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "system_boundary_inventory_surface_inventory_invalid" for finding in findings)
    assert any(finding.rule_id == "system_boundary_inventory_surface_state_invalid" for finding in findings)


def test_witness_rejects_endpoint_or_secret_value() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "system-boundary inventory witness")
    candidate = deepcopy(payload)
    candidate["system_boundary_inventory_surfaces"][0]["public_safe_note"] = "endpoint_url=private secret=value"

    findings = validate_packet(candidate)

    assert findings
    assert any(
        finding.rule_id == "system_boundary_inventory_forbidden_private_value_pattern" for finding in findings
    )


def test_witness_rejects_boundary_ready_phrase() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "system-boundary inventory witness")
    candidate = deepcopy(payload)
    candidate["next_action"] = "system boundary inventory complete and deployment is ready"

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "system_boundary_inventory_forbidden_promotion_phrase" for finding in findings)
