"""Tests for the Foundation Mode interface-map boundary validator.

Purpose: prove interface-map preparation stays local and does not authorize
interface-map completeness, interface contract readiness, endpoint readiness,
service binding, event/message readiness, data-flow readiness, trust closure,
integration readiness, runtime readiness, owner approval, test pass, refactor
approval, implementation approval, external publication, or deployment.
Governance scope: Foundation Mode, interface-map surface inventory,
private-value exclusion, and readiness blocking.
Dependencies: scripts.validate_foundation_interface_map_boundary.
Invariants: interface-map surfaces remain AwaitingEvidence and reject readiness
promotion or private-value drift.
"""

from __future__ import annotations

from copy import deepcopy
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validate_foundation_interface_map_boundary import (  # noqa: E402
    DEFAULT_PACKET_PATH,
    EXPECTED_SURFACES,
    EXPECTED_WITNESS_ID,
    load_json_object,
    validate_foundation_interface_map_boundary,
    validate_packet,
)


def test_foundation_interface_map_boundary_artifacts_pass() -> None:
    assert validate_foundation_interface_map_boundary() == []


def test_interface_map_witness_has_expected_identity_and_blockers() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "interface-map witness")

    assert payload["witness_id"] == EXPECTED_WITNESS_ID
    assert tuple(
        (surface["surface_id"], surface["surface_type"], surface["state"])
        for surface in payload["interface_map_surfaces"]
    ) == EXPECTED_SURFACES
    assert payload["interface_map_complete_claimed"] is False
    assert payload["interface_contract_ready_claimed"] is False
    assert payload["endpoint_ready_claimed"] is False
    assert payload["service_binding_claimed"] is False
    assert payload["owner_approval_assigned"] is False
    assert payload["test_pass_claimed"] is False
    assert payload["implementation_approval_allowed"] is False
    assert payload["deployment_allowed"] is False


def test_witness_rejects_interface_map_completeness_claim() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "interface-map witness")
    candidate = deepcopy(payload)
    candidate["interface_map_complete_claimed"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "interface_map_root_value_invalid" for finding in findings)


def test_witness_rejects_endpoint_service_and_integration_readiness() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "interface-map witness")
    candidate = deepcopy(payload)
    candidate["endpoint_ready_claimed"] = True
    candidate["service_binding_claimed"] = True
    candidate["integration_ready_claimed"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "interface_map_root_value_invalid" for finding in findings)


def test_witness_rejects_owner_test_and_implementation_approval() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "interface-map witness")
    candidate = deepcopy(payload)
    candidate["owner_approval_assigned"] = True
    candidate["test_pass_claimed"] = True
    candidate["implementation_approval_allowed"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "interface_map_root_value_invalid" for finding in findings)


def test_witness_rejects_surface_state_promotion() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "interface-map witness")
    candidate = deepcopy(payload)
    candidate["interface_map_surfaces"][0]["state"] = "Ready"

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "interface_map_surface_inventory_invalid" for finding in findings)
    assert any(finding.rule_id == "interface_map_surface_state_invalid" for finding in findings)


def test_witness_rejects_endpoint_secret_or_test_value() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "interface-map witness")
    candidate = deepcopy(payload)
    candidate["interface_map_surfaces"][0]["public_safe_note"] = "endpoint_url=private secret=value test_pass=true"

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "interface_map_forbidden_private_value_pattern" for finding in findings)


def test_witness_rejects_interface_ready_phrase() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "interface-map witness")
    candidate = deepcopy(payload)
    candidate["next_action"] = "interface contract is ready and deployment is ready"

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "interface_map_forbidden_promotion_phrase" for finding in findings)
