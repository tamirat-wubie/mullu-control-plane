"""Tests for the Foundation Mode diff-review boundary validator.

Purpose: prove diff-review preparation stays local and does not authorize
review completeness, scope closure, ownership assignment, staging, commit,
branch switch, push, pull request, release, revert, test pass, secret
publication, source-control publication, external publication, or deployment.
Governance scope: Foundation Mode, diff-review surface inventory,
private-value exclusion, source-control effect blocking, and readiness blocking.
Dependencies: scripts.validate_foundation_diff_review_boundary.
Invariants: diff-review surfaces remain AwaitingEvidence and reject Git-effect
promotion or private-value drift.
"""

from __future__ import annotations

from copy import deepcopy
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validate_foundation_diff_review_boundary import (  # noqa: E402
    DEFAULT_PACKET_PATH,
    EXPECTED_SURFACE_NOTE_FRAGMENTS,
    EXPECTED_SURFACES,
    EXPECTED_WITNESS_ID,
    load_json_object,
    validate_foundation_diff_review_boundary,
    validate_packet,
)


def test_foundation_diff_review_boundary_artifacts_pass() -> None:
    assert validate_foundation_diff_review_boundary() == []


def test_diff_review_witness_has_expected_identity_and_blockers() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "diff-review witness")

    assert payload["witness_id"] == EXPECTED_WITNESS_ID
    assert tuple(
        (surface["surface_id"], surface["surface_type"], surface["state"])
        for surface in payload["diff_review_surfaces"]
    ) == EXPECTED_SURFACES
    assert payload["diff_review_complete_claimed"] is False
    assert payload["diff_scope_closed_claimed"] is False
    assert payload["diff_ownership_assigned"] is False
    assert payload["staging_allowed"] is False
    assert payload["commit_allowed"] is False
    assert payload["push_allowed"] is False
    assert payload["pull_request_allowed"] is False
    assert payload["deployment_allowed"] is False


def test_runtime_safety_diff_review_fragments_are_present() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "diff-review witness")
    surfaces = {surface["surface_id"]: surface for surface in payload["diff_review_surfaces"]}

    assert EXPECTED_SURFACE_NOTE_FRAGMENTS
    for surface_id, fragments in EXPECTED_SURFACE_NOTE_FRAGMENTS.items():
        assert surface_id in surfaces
        assert fragments
        assert all(fragment in surfaces[surface_id]["public_safe_note"] for fragment in fragments)


def test_witness_rejects_missing_runtime_safety_diff_review_fragment() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "diff-review witness")
    candidate = deepcopy(payload)
    candidate["diff_review_surfaces"][0]["public_safe_note"] = (
        "Draft changed-file inventory questions without claiming diff-review completeness."
    )

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "diff_review_surface_note_fragment_missing" for finding in findings)


def test_witness_rejects_diff_review_completeness_claim() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "diff-review witness")
    candidate = deepcopy(payload)
    candidate["diff_review_complete_claimed"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "diff_review_root_value_invalid" for finding in findings)


def test_witness_rejects_scope_ownership_and_git_effect_approval() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "diff-review witness")
    candidate = deepcopy(payload)
    candidate["diff_scope_closed_claimed"] = True
    candidate["diff_ownership_assigned"] = True
    candidate["staging_allowed"] = True
    candidate["commit_allowed"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "diff_review_root_value_invalid" for finding in findings)


def test_witness_rejects_push_pull_request_release_and_revert_approval() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "diff-review witness")
    candidate = deepcopy(payload)
    candidate["push_allowed"] = True
    candidate["pull_request_allowed"] = True
    candidate["release_allowed"] = True
    candidate["revert_allowed"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "diff_review_root_value_invalid" for finding in findings)


def test_witness_rejects_surface_state_promotion() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "diff-review witness")
    candidate = deepcopy(payload)
    candidate["diff_review_surfaces"][0]["state"] = "Ready"

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "diff_review_surface_inventory_invalid" for finding in findings)
    assert any(finding.rule_id == "diff_review_surface_state_invalid" for finding in findings)


def test_witness_rejects_diff_secret_commit_or_test_value() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "diff-review witness")
    candidate = deepcopy(payload)
    candidate["diff_review_surfaces"][0]["public_safe_note"] = (
        "diff_id=private secret=value commit_status=ready test_pass=true"
    )

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "diff_review_forbidden_private_value_pattern" for finding in findings)


def test_witness_rejects_git_effect_promotion_phrase() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "diff-review witness")
    candidate = deepcopy(payload)
    candidate["next_action"] = "diff review is complete and commit is approved"

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "diff_review_forbidden_promotion_phrase" for finding in findings)
