"""Tests for the Foundation Mode gap-register boundary validator.

Purpose: prove gap-register preparation stays local and does not authorize
register completeness, gap closure, priority closure, owner assignment,
remediation readiness, roadmap commitment, evidence promotion, terminal
closure, test pass, refactor approval, implementation approval, external
publication, or deployment.
Governance scope: Foundation Mode, gap-register surface inventory,
private-value exclusion, and readiness blocking.
Dependencies: scripts.validate_foundation_gap_register_boundary.
Invariants: gap-register surfaces remain AwaitingEvidence and reject readiness
promotion or private-value drift.
"""

from __future__ import annotations

from copy import deepcopy
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validate_foundation_gap_register_boundary import (  # noqa: E402
    DEFAULT_PACKET_PATH,
    EXPECTED_SURFACES,
    EXPECTED_WITNESS_ID,
    load_json_object,
    validate_foundation_gap_register_boundary,
    validate_packet,
)


def test_foundation_gap_register_boundary_artifacts_pass() -> None:
    assert validate_foundation_gap_register_boundary() == []


def test_gap_register_witness_has_expected_identity_and_blockers() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "gap-register witness")

    assert payload["witness_id"] == EXPECTED_WITNESS_ID
    assert tuple(
        (surface["surface_id"], surface["surface_type"], surface["state"])
        for surface in payload["gap_register_surfaces"]
    ) == EXPECTED_SURFACES
    assert payload["gap_register_complete_claimed"] is False
    assert payload["gap_closure_claimed"] is False
    assert payload["gap_priority_closed_claimed"] is False
    assert payload["gap_owner_assigned"] is False
    assert payload["remediation_ready_claimed"] is False
    assert payload["roadmap_commitment_allowed"] is False
    assert payload["implementation_approval_allowed"] is False
    assert payload["deployment_allowed"] is False


def test_witness_rejects_gap_register_completeness_claim() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "gap-register witness")
    candidate = deepcopy(payload)
    candidate["gap_register_complete_claimed"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "gap_register_root_value_invalid" for finding in findings)


def test_witness_rejects_closure_priority_and_owner_assignment() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "gap-register witness")
    candidate = deepcopy(payload)
    candidate["gap_closure_claimed"] = True
    candidate["gap_priority_closed_claimed"] = True
    candidate["gap_owner_assigned"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "gap_register_root_value_invalid" for finding in findings)


def test_witness_rejects_remediation_roadmap_test_and_implementation_approval() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "gap-register witness")
    candidate = deepcopy(payload)
    candidate["remediation_ready_claimed"] = True
    candidate["roadmap_commitment_allowed"] = True
    candidate["test_pass_claimed"] = True
    candidate["implementation_approval_allowed"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "gap_register_root_value_invalid" for finding in findings)


def test_witness_rejects_surface_state_promotion() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "gap-register witness")
    candidate = deepcopy(payload)
    candidate["gap_register_surfaces"][0]["state"] = "Ready"

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "gap_register_surface_inventory_invalid" for finding in findings)
    assert any(finding.rule_id == "gap_register_surface_state_invalid" for finding in findings)


def test_witness_rejects_gap_secret_roadmap_or_test_value() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "gap-register witness")
    candidate = deepcopy(payload)
    candidate["gap_register_surfaces"][0]["public_safe_note"] = (
        "gap_id=private secret=value roadmap_date=tomorrow test_pass=true"
    )

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "gap_register_forbidden_private_value_pattern" for finding in findings)


def test_witness_rejects_gap_closure_phrase() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "gap-register witness")
    candidate = deepcopy(payload)
    candidate["next_action"] = "gap register is complete and deployment is ready"

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "gap_register_forbidden_promotion_phrase" for finding in findings)
