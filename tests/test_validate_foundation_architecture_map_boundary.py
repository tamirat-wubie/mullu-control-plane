"""Tests for the Foundation Mode architecture-map boundary validator.

Purpose: prove architecture-map preparation stays local and does not authorize
architecture completeness, module inventory completeness, interface readiness,
dependency graph readiness, invariant closure, hazard closure, proof coverage
closure, integration readiness, runtime readiness, refactor approval,
implementation approval, external publication, or deployment readiness.
Governance scope: Foundation Mode, system boundary inventory, module inventory,
interface map, dependency graph, invariant map, hazard map, proof-reference map,
gap register, private-value exclusion, and readiness blocking.
Dependencies: scripts.validate_foundation_architecture_map_boundary.
Invariants: architecture-map surfaces remain AwaitingEvidence and reject
readiness promotion or private-value drift.
"""

from __future__ import annotations

from copy import deepcopy
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validate_foundation_architecture_map_boundary import (  # noqa: E402
    DEFAULT_PACKET_PATH,
    EXPECTED_SURFACES,
    EXPECTED_WITNESS_ID,
    load_json_object,
    validate_foundation_architecture_map_boundary,
    validate_packet,
)


def test_foundation_architecture_map_boundary_artifacts_pass() -> None:
    assert validate_foundation_architecture_map_boundary() == []


def test_architecture_map_witness_has_expected_identity_and_blockers() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "architecture-map witness")

    assert payload["witness_id"] == EXPECTED_WITNESS_ID
    assert tuple(
        (surface["surface_id"], surface["surface_type"], surface["state"])
        for surface in payload["architecture_map_surfaces"]
    ) == EXPECTED_SURFACES
    assert payload["architecture_complete_claimed"] is False
    assert payload["module_inventory_complete_claimed"] is False
    assert payload["interface_contract_ready_claimed"] is False
    assert payload["dependency_graph_ready_claimed"] is False
    assert payload["implementation_approval_allowed"] is False
    assert payload["deployment_allowed"] is False


def test_witness_rejects_architecture_completeness_claim() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "architecture-map witness")
    candidate = deepcopy(payload)
    candidate["architecture_complete_claimed"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "architecture_map_root_value_invalid" for finding in findings)


def test_witness_rejects_interface_and_dependency_readiness() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "architecture-map witness")
    candidate = deepcopy(payload)
    candidate["interface_contract_ready_claimed"] = True
    candidate["dependency_graph_ready_claimed"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "architecture_map_root_value_invalid" for finding in findings)


def test_witness_rejects_refactor_and_implementation_approval() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "architecture-map witness")
    candidate = deepcopy(payload)
    candidate["refactor_approval_allowed"] = True
    candidate["implementation_approval_allowed"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "architecture_map_root_value_invalid" for finding in findings)


def test_witness_rejects_surface_state_promotion() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "architecture-map witness")
    candidate = deepcopy(payload)
    candidate["architecture_map_surfaces"][0]["state"] = "Ready"

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "architecture_map_surface_inventory_invalid" for finding in findings)
    assert any(finding.rule_id == "architecture_map_surface_state_invalid" for finding in findings)


def test_witness_rejects_endpoint_or_secret_value() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "architecture-map witness")
    candidate = deepcopy(payload)
    candidate["architecture_map_surfaces"][0]["public_safe_note"] = "endpoint_url=private secret=value"

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "architecture_map_forbidden_private_value_pattern" for finding in findings)


def test_witness_rejects_architecture_ready_phrase() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "architecture-map witness")
    candidate = deepcopy(payload)
    candidate["next_action"] = "architecture is complete and deployment is ready"

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "architecture_map_forbidden_promotion_phrase" for finding in findings)
