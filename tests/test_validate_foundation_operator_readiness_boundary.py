"""Tests for the Foundation Mode operator-readiness boundary validator.

Purpose: prove operator-readiness preparation stays local and does not
authorize capacity, schedule, skill, team, hiring, delegation, incident
coverage, support coverage, authority, private schedule, private health, or
deployment claims.
Governance scope: Foundation Mode, solo-operator posture, public-safe planning
witness, private-value exclusion, operational-readiness blocking, and deployment
blocking.
Dependencies: scripts.validate_foundation_operator_readiness_boundary.
Invariants: operator-readiness surfaces remain AwaitingEvidence and reject
readiness promotion or private value drift.
"""

from __future__ import annotations

from copy import deepcopy
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validate_foundation_operator_readiness_boundary import (  # noqa: E402
    DEFAULT_PACKET_PATH,
    EXPECTED_SURFACES,
    EXPECTED_WITNESS_ID,
    load_json_object,
    validate_foundation_operator_readiness_boundary,
    validate_packet,
)


def test_foundation_operator_readiness_boundary_artifacts_pass() -> None:
    assert validate_foundation_operator_readiness_boundary() == []


def test_operator_readiness_witness_has_expected_identity_and_blockers() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "operator-readiness witness")

    assert payload["witness_id"] == EXPECTED_WITNESS_ID
    assert tuple(
        (surface["surface_id"], surface["surface_type"], surface["state"])
        for surface in payload["operator_readiness_surfaces"]
    ) == EXPECTED_SURFACES
    assert payload["operator_capacity_verified"] is False
    assert payload["schedule_readiness_claimed"] is False
    assert payload["team_readiness_claimed"] is False
    assert payload["hiring_ready_claimed"] is False
    assert payload["support_coverage_ready_claimed"] is False
    assert payload["deployment_allowed"] is False


def test_witness_rejects_operator_capacity_claim() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "operator-readiness witness")
    candidate = deepcopy(payload)
    candidate["operator_capacity_verified"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "operator_readiness_root_value_invalid" for finding in findings)


def test_witness_rejects_team_and_hiring_claims() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "operator-readiness witness")
    candidate = deepcopy(payload)
    candidate["team_readiness_claimed"] = True
    candidate["hiring_ready_claimed"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "operator_readiness_root_value_invalid" for finding in findings)


def test_witness_rejects_support_and_authority_claims() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "operator-readiness witness")
    candidate = deepcopy(payload)
    candidate["support_coverage_ready_claimed"] = True
    candidate["legal_authority_ready_claimed"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "operator_readiness_root_value_invalid" for finding in findings)


def test_witness_rejects_surface_state_promotion() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "operator-readiness witness")
    candidate = deepcopy(payload)
    candidate["operator_readiness_surfaces"][0]["state"] = "Ready"

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "operator_readiness_surface_inventory_invalid" for finding in findings)
    assert any(finding.rule_id == "operator_readiness_surface_state_invalid" for finding in findings)


def test_witness_rejects_private_schedule_shape() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "operator-readiness witness")
    candidate = deepcopy(payload)
    candidate["operator_readiness_surfaces"][0]["public_safe_note"] = "schedule=private calendar value"

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "operator_readiness_forbidden_private_value_pattern" for finding in findings)


def test_witness_rejects_operator_ready_phrase() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "operator-readiness witness")
    candidate = deepcopy(payload)
    candidate["next_action"] = "operator is ready after this draft"

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "operator_readiness_forbidden_promotion_phrase" for finding in findings)
