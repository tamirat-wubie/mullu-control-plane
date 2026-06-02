"""Tests for the Foundation Mode component-contract boundary validator.

Purpose: prove component-contract preparation stays local and does not
authorize input readiness, output readiness, error readiness, evidence
readiness, state readiness, dependency readiness, owner approval, test pass,
refactor approval, implementation approval, external publication, or deployment.
Governance scope: Foundation Mode, component-contract surface inventory,
private-value exclusion, and readiness blocking.
Dependencies: scripts.validate_foundation_component_contract_boundary.
Invariants: component-contract surfaces remain AwaitingEvidence and reject
readiness promotion or private-value drift.
"""

from __future__ import annotations

from copy import deepcopy
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validate_foundation_component_contract_boundary import (  # noqa: E402
    DEFAULT_PACKET_PATH,
    EXPECTED_SURFACES,
    EXPECTED_WITNESS_ID,
    load_json_object,
    validate_foundation_component_contract_boundary,
    validate_packet,
)


def test_foundation_component_contract_boundary_artifacts_pass() -> None:
    assert validate_foundation_component_contract_boundary() == []


def test_component_contract_witness_has_expected_identity_and_blockers() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "component-contract witness")

    assert payload["witness_id"] == EXPECTED_WITNESS_ID
    assert tuple(
        (surface["surface_id"], surface["surface_type"], surface["state"])
        for surface in payload["component_contract_surfaces"]
    ) == EXPECTED_SURFACES
    assert payload["component_contract_ready_claimed"] is False
    assert payload["input_contract_ready_claimed"] is False
    assert payload["output_contract_ready_claimed"] is False
    assert payload["owner_approval_assigned"] is False
    assert payload["test_pass_claimed"] is False
    assert payload["implementation_approval_allowed"] is False
    assert payload["deployment_allowed"] is False


def test_witness_rejects_component_contract_readiness_claim() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "component-contract witness")
    candidate = deepcopy(payload)
    candidate["component_contract_ready_claimed"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "component_contract_root_value_invalid" for finding in findings)


def test_witness_rejects_input_output_and_error_readiness() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "component-contract witness")
    candidate = deepcopy(payload)
    candidate["input_contract_ready_claimed"] = True
    candidate["output_contract_ready_claimed"] = True
    candidate["error_contract_ready_claimed"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "component_contract_root_value_invalid" for finding in findings)


def test_witness_rejects_owner_test_and_implementation_approval() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "component-contract witness")
    candidate = deepcopy(payload)
    candidate["owner_approval_assigned"] = True
    candidate["test_pass_claimed"] = True
    candidate["implementation_approval_allowed"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "component_contract_root_value_invalid" for finding in findings)


def test_witness_rejects_surface_state_promotion() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "component-contract witness")
    candidate = deepcopy(payload)
    candidate["component_contract_surfaces"][0]["state"] = "Ready"

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "component_contract_surface_inventory_invalid" for finding in findings)
    assert any(finding.rule_id == "component_contract_surface_state_invalid" for finding in findings)


def test_witness_rejects_endpoint_secret_or_test_value() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "component-contract witness")
    candidate = deepcopy(payload)
    candidate["component_contract_surfaces"][0]["public_safe_note"] = "endpoint_url=private secret=value test_pass=true"

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "component_contract_forbidden_private_value_pattern" for finding in findings)


def test_witness_rejects_contract_ready_phrase() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "component-contract witness")
    candidate = deepcopy(payload)
    candidate["next_action"] = "component contract is ready and deployment is ready"

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "component_contract_forbidden_promotion_phrase" for finding in findings)
