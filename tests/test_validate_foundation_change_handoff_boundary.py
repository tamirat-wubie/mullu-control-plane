"""Tests for the Foundation Mode change-handoff boundary validator.

Purpose: prove change-handoff preparation stays local and does not authorize
review completeness, scope closure, validation completeness, secret clearance,
staging, commit, branch switch, push, pull request, release, revert,
publication, or deployment.
Governance scope: Foundation Mode, change-handoff surface inventory,
private-value exclusion, source-control effect blocking, and readiness blocking.
Dependencies: scripts.validate_foundation_change_handoff_boundary.
Invariants: change-handoff surfaces remain AwaitingEvidence and reject
Git-effect promotion or private-value drift.
"""

from __future__ import annotations

from copy import deepcopy
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validate_foundation_change_handoff_boundary import (  # noqa: E402
    DEFAULT_PACKET_PATH,
    EXPECTED_SURFACE_NOTE_FRAGMENTS,
    EXPECTED_SURFACES,
    EXPECTED_WITNESS_ID,
    load_json_object,
    validate_foundation_change_handoff_boundary,
    validate_packet,
)


def test_foundation_change_handoff_boundary_artifacts_pass() -> None:
    assert validate_foundation_change_handoff_boundary() == []


def test_change_handoff_witness_has_expected_identity_and_blockers() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "change-handoff witness")

    assert payload["witness_id"] == EXPECTED_WITNESS_ID
    assert tuple(
        (surface["surface_id"], surface["surface_type"], surface["state"])
        for surface in payload["change_handoff_surfaces"]
    ) == EXPECTED_SURFACES
    assert payload["change_handoff_complete_claimed"] is False
    assert payload["changed_file_review_complete_claimed"] is False
    assert payload["diff_scope_closed_claimed"] is False
    assert payload["validation_complete_claimed"] is False
    assert payload["secret_clearance_claimed"] is False
    assert payload["deployment_allowed"] is False


def test_runtime_safety_handoff_fragments_are_present() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "change-handoff witness")
    surfaces = {surface["surface_id"]: surface for surface in payload["change_handoff_surfaces"]}

    assert EXPECTED_SURFACE_NOTE_FRAGMENTS
    for surface_id, fragments in EXPECTED_SURFACE_NOTE_FRAGMENTS.items():
        assert surface_id in surfaces
        assert fragments
        assert all(fragment in surfaces[surface_id]["public_safe_note"] for fragment in fragments)


def test_witness_rejects_missing_runtime_safety_handoff_fragment() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "change-handoff witness")
    candidate = deepcopy(payload)
    candidate["change_handoff_surfaces"][0]["public_safe_note"] = (
        "Draft change-family summary questions without claiming handoff completeness."
    )

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "change_handoff_surface_note_fragment_missing" for finding in findings)


def test_witness_rejects_change_handoff_completeness_claim() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "change-handoff witness")
    candidate = deepcopy(payload)
    candidate["change_handoff_complete_claimed"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "change_handoff_root_value_invalid" for finding in findings)


def test_witness_rejects_review_scope_validation_and_secret_clearance() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "change-handoff witness")
    candidate = deepcopy(payload)
    candidate["changed_file_review_complete_claimed"] = True
    candidate["diff_scope_closed_claimed"] = True
    candidate["validation_complete_claimed"] = True
    candidate["secret_clearance_claimed"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "change_handoff_root_value_invalid" for finding in findings)


def test_witness_rejects_git_publication_and_deployment_approval() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "change-handoff witness")
    candidate = deepcopy(payload)
    candidate["staging_allowed"] = True
    candidate["commit_allowed"] = True
    candidate["push_allowed"] = True
    candidate["pull_request_allowed"] = True
    candidate["deployment_allowed"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "change_handoff_root_value_invalid" for finding in findings)


def test_witness_rejects_surface_state_promotion() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "change-handoff witness")
    candidate = deepcopy(payload)
    candidate["change_handoff_surfaces"][0]["state"] = "Ready"

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "change_handoff_surface_inventory_invalid" for finding in findings)
    assert any(finding.rule_id == "change_handoff_surface_state_invalid" for finding in findings)


def test_witness_rejects_secret_commit_or_validation_value() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "change-handoff witness")
    candidate = deepcopy(payload)
    candidate["change_handoff_surfaces"][0]["public_safe_note"] = (
        "commit_status=ready validator_status=passed secret=value"
    )

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "change_handoff_forbidden_private_value_pattern" for finding in findings)


def test_witness_rejects_git_effect_promotion_phrase() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "change-handoff witness")
    candidate = deepcopy(payload)
    candidate["next_action"] = "change handoff is complete and commit is approved"

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "change_handoff_forbidden_promotion_phrase" for finding in findings)
