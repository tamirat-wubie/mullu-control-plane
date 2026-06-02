"""Tests for the Foundation Mode runtime/environment boundary validator.

Purpose: prove runtime/environment preparation stays local and does not
authorize runtime verification, dependency-install verification, database
activation, container activation, endpoint activation, cloud runtime, migration
execution, or deployment claims.
Governance scope: Foundation Mode, local runtime posture, environment posture,
public-safe planning witness, private-value exclusion, and deployment blocking.
Dependencies: scripts.validate_foundation_runtime_environment_boundary.
Invariants: runtime/environment surfaces remain AwaitingEvidence and reject
readiness promotion or private value drift.
"""

from __future__ import annotations

from copy import deepcopy
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validate_foundation_runtime_environment_boundary import (  # noqa: E402
    DEFAULT_PACKET_PATH,
    EXPECTED_SURFACES,
    EXPECTED_WITNESS_ID,
    load_json_object,
    validate_foundation_runtime_environment_boundary,
    validate_packet,
)


def test_foundation_runtime_environment_boundary_artifacts_pass() -> None:
    assert validate_foundation_runtime_environment_boundary() == []


def test_runtime_environment_witness_has_expected_identity_and_blockers() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "runtime/environment witness")

    assert payload["witness_id"] == EXPECTED_WITNESS_ID
    assert tuple(
        (surface["surface_id"], surface["surface_type"], surface["state"])
        for surface in payload["runtime_environment_surfaces"]
    ) == EXPECTED_SURFACES
    assert payload["local_runtime_verified"] is False
    assert payload["workstation_repeatability_verified"] is False
    assert payload["dependency_install_verified"] is False
    assert payload["database_runtime_allowed"] is False
    assert payload["network_endpoint_allowed"] is False
    assert payload["deployment_allowed"] is False


def test_witness_rejects_local_runtime_verification_claim() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "runtime/environment witness")
    candidate = deepcopy(payload)
    candidate["local_runtime_verified"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "runtime_environment_root_value_invalid" for finding in findings)


def test_witness_rejects_database_runtime_claim() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "runtime/environment witness")
    candidate = deepcopy(payload)
    candidate["database_runtime_allowed"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "runtime_environment_root_value_invalid" for finding in findings)


def test_witness_rejects_endpoint_activation_claim() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "runtime/environment witness")
    candidate = deepcopy(payload)
    candidate["network_endpoint_allowed"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "runtime_environment_root_value_invalid" for finding in findings)


def test_witness_rejects_surface_state_promotion() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "runtime/environment witness")
    candidate = deepcopy(payload)
    candidate["runtime_environment_surfaces"][0]["state"] = "Ready"

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "runtime_environment_surface_inventory_invalid" for finding in findings)
    assert any(finding.rule_id == "runtime_environment_surface_state_invalid" for finding in findings)


def test_witness_rejects_endpoint_value() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "runtime/environment witness")
    candidate = deepcopy(payload)
    candidate["runtime_environment_surfaces"][0]["public_safe_note"] = "local target 127.0.0.1:8080"

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "runtime_environment_forbidden_private_value_pattern" for finding in findings)


def test_witness_rejects_runtime_ready_phrase() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "runtime/environment witness")
    candidate = deepcopy(payload)
    candidate["next_action"] = "runtime-ready after this draft"

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "runtime_environment_forbidden_promotion_phrase" for finding in findings)
