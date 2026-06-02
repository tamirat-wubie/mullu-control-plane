"""Tests for the Foundation Mode source-control boundary validator.

Purpose: prove commit-boundary preparation stays local and does not authorize
staging, commit, push, pull request, release, deployment, or secret publication.
Governance scope: Foundation Mode, source-control hygiene, commit-boundary
preparation, and external-publication blocking.
Dependencies: scripts.validate_foundation_source_control_boundary.
Invariants: the packet keeps all Git effects blocked until explicit user
request and preserves required verification commands.
"""

from __future__ import annotations

from copy import deepcopy
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validate_foundation_source_control_boundary import (  # noqa: E402
    DEFAULT_PACKET_PATH,
    EXPECTED_BOUNDARY_ID,
    EXPECTED_CHANGE_FAMILIES,
    EXPECTED_REQUIRED_CHECKS,
    load_json_object,
    validate_foundation_source_control_boundary,
    validate_packet,
)


def test_foundation_source_control_boundary_artifacts_pass() -> None:
    assert validate_foundation_source_control_boundary() == []


def test_source_control_packet_has_expected_identity_and_blockers() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "source-control packet")

    assert payload["boundary_id"] == EXPECTED_BOUNDARY_ID
    assert tuple(family["family_id"] for family in payload["change_families"]) == EXPECTED_CHANGE_FAMILIES
    assert tuple(payload["required_checks"]) == EXPECTED_REQUIRED_CHECKS
    assert payload["staging_allowed"] is False
    assert payload["commit_allowed"] is False
    assert payload["push_allowed"] is False
    assert payload["pull_request_allowed"] is False
    assert payload["deployment_allowed"] is False


def test_packet_rejects_commit_promotion() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "source-control packet")
    candidate = deepcopy(payload)
    candidate["commit_allowed"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "source_control_root_value_invalid" for finding in findings)


def test_packet_rejects_push_promotion() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "source-control packet")
    candidate = deepcopy(payload)
    candidate["push_allowed"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "source_control_root_value_invalid" for finding in findings)


def test_packet_rejects_missing_required_check() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "source-control packet")
    candidate = deepcopy(payload)
    candidate["required_checks"] = candidate["required_checks"][:-1]

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "source_control_required_checks_invalid" for finding in findings)


def test_packet_rejects_family_state_promotion() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "source-control packet")
    candidate = deepcopy(payload)
    candidate["change_families"][0]["state"] = "ReadyForCommit"

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "source_control_family_state_invalid" for finding in findings)


def test_packet_rejects_publication_phrase() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "source-control packet")
    candidate = deepcopy(payload)
    candidate["change_families"][0]["summary"] = "push allowed after validation"

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "source_control_forbidden_publication_phrase" for finding in findings)
