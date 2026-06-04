"""Tests for the Foundation Mode solo daily loop boundary validator.

Purpose: prove solo daily loop preparation stays local and does not authorize
private schedule recording, productivity claims, external action, spending,
legal/business action, source-control publication, or deployment claims.
Governance scope: Foundation Mode, solo daily triage, one-task selection,
prerequisite alignment, public-safe evidence capture, validation checkpoints,
stop conditions, handoff notes, carryover notes, and external-action blocking.
Dependencies: scripts.validate_foundation_solo_daily_loop_boundary.
Invariants: solo daily loop surfaces remain AwaitingEvidence and reject
readiness promotion or private value drift.
"""

from __future__ import annotations

from copy import deepcopy
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validate_foundation_solo_daily_loop_boundary import (  # noqa: E402
    DEFAULT_PACKET_PATH,
    EXPECTED_SURFACES,
    EXPECTED_WITNESS_ID,
    load_json_object,
    validate_foundation_solo_daily_loop_boundary,
    validate_packet,
)


def test_foundation_solo_daily_loop_boundary_artifacts_pass() -> None:
    assert validate_foundation_solo_daily_loop_boundary() == []


def test_solo_daily_loop_witness_has_expected_identity_and_blockers() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "solo daily loop witness")

    assert payload["witness_id"] == EXPECTED_WITNESS_ID
    assert tuple(
        (surface["surface_id"], surface["surface_type"], surface["state"])
        for surface in payload["solo_daily_loop_surfaces"]
    ) == EXPECTED_SURFACES
    assert payload["daily_productivity_readiness_claimed"] is False
    assert payload["schedule_readiness_claimed"] is False
    assert payload["private_calendar_recording_allowed"] is False
    assert payload["private_health_tracking_allowed"] is False
    assert payload["task_completion_guaranteed"] is False
    assert payload["support_coverage_claimed"] is False
    assert payload["source_control_publication_allowed"] is False
    assert payload["deployment_allowed"] is False


def test_witness_rejects_productivity_and_completion_claims() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "solo daily loop witness")
    candidate = deepcopy(payload)
    candidate["daily_productivity_readiness_claimed"] = True
    candidate["task_completion_guaranteed"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "solo_daily_loop_root_value_invalid" for finding in findings)


def test_witness_rejects_private_calendar_and_health_recording() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "solo daily loop witness")
    candidate = deepcopy(payload)
    candidate["private_calendar_recording_allowed"] = True
    candidate["private_health_tracking_allowed"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "solo_daily_loop_root_value_invalid" for finding in findings)


def test_witness_rejects_support_and_team_coverage_claims() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "solo daily loop witness")
    candidate = deepcopy(payload)
    candidate["support_coverage_claimed"] = True
    candidate["team_coverage_claimed"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "solo_daily_loop_root_value_invalid" for finding in findings)


def test_witness_rejects_surface_state_promotion() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "solo daily loop witness")
    candidate = deepcopy(payload)
    candidate["solo_daily_loop_surfaces"][0]["state"] = "Ready"

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "solo_daily_loop_surface_inventory_invalid" for finding in findings)
    assert any(finding.rule_id == "solo_daily_loop_surface_state_invalid" for finding in findings)


def test_witness_rejects_private_schedule_shape() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "solo daily loop witness")
    candidate = deepcopy(payload)
    candidate["solo_daily_loop_surfaces"][0]["public_safe_note"] = "schedule=value health_status=private"

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "solo_daily_loop_forbidden_private_value_pattern" for finding in findings)


def test_witness_rejects_secret_and_credential_shape() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "solo daily loop witness")
    candidate = deepcopy(payload)
    candidate["solo_daily_loop_surfaces"][4]["public_safe_note"] = "token=private credential"

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "solo_daily_loop_forbidden_private_value_pattern" for finding in findings)


def test_witness_rejects_deployment_and_spending_claims() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "solo daily loop witness")
    candidate = deepcopy(payload)
    candidate["deployment_allowed"] = True
    candidate["spending_allowed"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "solo_daily_loop_root_value_invalid" for finding in findings)


def test_witness_rejects_readiness_promotion_phrase() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "solo daily loop witness")
    candidate = deepcopy(payload)
    candidate["next_action"] = "daily loop is ready for all work"

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "solo_daily_loop_forbidden_promotion_phrase" for finding in findings)
