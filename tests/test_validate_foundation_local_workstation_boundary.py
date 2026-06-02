"""Tests for the Foundation Mode local-workstation boundary validator.

Purpose: prove local-workstation preparation stays local and does not authorize
workstation, toolchain, dependency-install, environment, service, full-test,
cloud, private path, or deployment claims.
Governance scope: Foundation Mode, local workstation posture, public-safe
planning witness, private-value exclusion, workstation-repeatability blocking,
and deployment blocking.
Dependencies: scripts.validate_foundation_local_workstation_boundary.
Invariants: local-workstation surfaces remain AwaitingEvidence and reject
readiness promotion or private value drift.
"""

from __future__ import annotations

from copy import deepcopy
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validate_foundation_local_workstation_boundary import (  # noqa: E402
    DEFAULT_PACKET_PATH,
    EXPECTED_SURFACES,
    EXPECTED_WITNESS_ID,
    load_json_object,
    validate_foundation_local_workstation_boundary,
    validate_packet,
)


def test_foundation_local_workstation_boundary_artifacts_pass() -> None:
    assert validate_foundation_local_workstation_boundary() == []


def test_local_workstation_witness_has_expected_identity_and_blockers() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "local-workstation witness")

    assert payload["witness_id"] == EXPECTED_WITNESS_ID
    assert tuple(
        (surface["surface_id"], surface["surface_type"], surface["state"])
        for surface in payload["local_workstation_surfaces"]
    ) == EXPECTED_SURFACES
    assert payload["local_workstation_verified"] is False
    assert payload["python_toolchain_verified"] is False
    assert payload["dependency_install_allowed"] is False
    assert payload["service_start_allowed"] is False
    assert payload["full_test_suite_pass_claimed"] is False
    assert payload["deployment_allowed"] is False


def test_witness_rejects_workstation_verification_claim() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "local-workstation witness")
    candidate = deepcopy(payload)
    candidate["local_workstation_verified"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "local_workstation_root_value_invalid" for finding in findings)


def test_witness_rejects_toolchain_verification_claims() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "local-workstation witness")
    candidate = deepcopy(payload)
    candidate["python_toolchain_verified"] = True
    candidate["node_toolchain_verified"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "local_workstation_root_value_invalid" for finding in findings)


def test_witness_rejects_install_and_service_claims() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "local-workstation witness")
    candidate = deepcopy(payload)
    candidate["dependency_install_allowed"] = True
    candidate["service_start_allowed"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "local_workstation_root_value_invalid" for finding in findings)


def test_witness_rejects_surface_state_promotion() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "local-workstation witness")
    candidate = deepcopy(payload)
    candidate["local_workstation_surfaces"][0]["state"] = "Ready"

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "local_workstation_surface_inventory_invalid" for finding in findings)
    assert any(finding.rule_id == "local_workstation_surface_state_invalid" for finding in findings)


def test_witness_rejects_private_environment_assignment_shape() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "local-workstation witness")
    candidate = deepcopy(payload)
    candidate["local_workstation_surfaces"][0]["public_safe_note"] = "PYTHONPATH=C:\\private\\repo"

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "local_workstation_forbidden_private_value_pattern" for finding in findings)


def test_witness_rejects_workstation_ready_phrase() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "local-workstation witness")
    candidate = deepcopy(payload)
    candidate["next_action"] = "workstation is ready after this draft"

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "local_workstation_forbidden_promotion_phrase" for finding in findings)
