"""Tests for the Foundation Mode hazard-map boundary validator.

Purpose: prove hazard-map preparation stays local and does not authorize map
completeness, classification readiness, severity closure, mitigation readiness,
safety review readiness, runtime readiness, owner approval, test pass, refactor
approval, implementation approval, external publication, or deployment.
Governance scope: Foundation Mode, hazard-map surface inventory, private-value
exclusion, and readiness blocking.
Dependencies: scripts.validate_foundation_hazard_map_boundary.
Invariants: hazard-map surfaces remain AwaitingEvidence and reject readiness
promotion or private-value drift.
"""

from __future__ import annotations

from copy import deepcopy
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validate_foundation_hazard_map_boundary import (  # noqa: E402
    DEFAULT_PACKET_PATH,
    EXPECTED_SURFACES,
    EXPECTED_WITNESS_ID,
    load_json_object,
    validate_foundation_hazard_map_boundary,
    validate_packet,
)


def test_foundation_hazard_map_boundary_artifacts_pass() -> None:
    assert validate_foundation_hazard_map_boundary() == []


def test_hazard_map_witness_has_expected_identity_and_blockers() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "hazard-map witness")

    assert payload["witness_id"] == EXPECTED_WITNESS_ID
    assert tuple(
        (surface["surface_id"], surface["surface_type"], surface["state"])
        for surface in payload["hazard_map_surfaces"]
    ) == EXPECTED_SURFACES
    assert payload["hazard_map_complete_claimed"] is False
    assert payload["hazard_classification_ready_claimed"] is False
    assert payload["hazard_severity_closed_claimed"] is False
    assert payload["hazard_mitigation_ready_claimed"] is False
    assert payload["safety_review_ready_claimed"] is False
    assert payload["runtime_hazard_ready_claimed"] is False
    assert payload["implementation_approval_allowed"] is False
    assert payload["deployment_allowed"] is False


def test_witness_rejects_hazard_map_completeness_claim() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "hazard-map witness")
    candidate = deepcopy(payload)
    candidate["hazard_map_complete_claimed"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "hazard_map_root_value_invalid" for finding in findings)


def test_witness_rejects_classification_severity_and_mitigation_readiness() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "hazard-map witness")
    candidate = deepcopy(payload)
    candidate["hazard_classification_ready_claimed"] = True
    candidate["hazard_severity_closed_claimed"] = True
    candidate["hazard_mitigation_ready_claimed"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "hazard_map_root_value_invalid" for finding in findings)


def test_witness_rejects_review_runtime_test_and_implementation_approval() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "hazard-map witness")
    candidate = deepcopy(payload)
    candidate["safety_review_ready_claimed"] = True
    candidate["runtime_hazard_ready_claimed"] = True
    candidate["test_pass_claimed"] = True
    candidate["implementation_approval_allowed"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "hazard_map_root_value_invalid" for finding in findings)


def test_witness_rejects_surface_state_promotion() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "hazard-map witness")
    candidate = deepcopy(payload)
    candidate["hazard_map_surfaces"][0]["state"] = "Ready"

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "hazard_map_surface_inventory_invalid" for finding in findings)
    assert any(finding.rule_id == "hazard_map_surface_state_invalid" for finding in findings)


def test_witness_rejects_hazard_secret_mitigation_or_test_value() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "hazard-map witness")
    candidate = deepcopy(payload)
    candidate["hazard_map_surfaces"][0]["public_safe_note"] = (
        "hazard_id=private secret=value mitigation_status=ready test_pass=true"
    )

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "hazard_map_forbidden_private_value_pattern" for finding in findings)


def test_witness_rejects_hazard_ready_phrase() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "hazard-map witness")
    candidate = deepcopy(payload)
    candidate["next_action"] = "hazard map is complete and deployment is ready"

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "hazard_map_forbidden_promotion_phrase" for finding in findings)
