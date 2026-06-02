"""Tests for the Foundation Mode learning-path boundary validator.

Purpose: prove solo learning preparation stays local and does not authorize
skill readiness, training completion, certification, paid-course activation,
mentor assignment, hiring readiness, delegation readiness, public tutorial
publication, curriculum completion, production-operation readiness,
customer-support readiness, external account use, or deployment readiness.
Governance scope: Foundation Mode, learning goal inventory, glossary loop,
command practice, reading queue, local exercise design, error log,
verification habit, help-request boundary, private-value exclusion, and
readiness blocking.
Dependencies: scripts.validate_foundation_learning_path_boundary.
Invariants: learning-path surfaces remain AwaitingEvidence and reject
readiness promotion or private-value drift.
"""

from __future__ import annotations

from copy import deepcopy
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validate_foundation_learning_path_boundary import (  # noqa: E402
    DEFAULT_PACKET_PATH,
    EXPECTED_SURFACES,
    EXPECTED_WITNESS_ID,
    load_json_object,
    validate_foundation_learning_path_boundary,
    validate_packet,
)


def test_foundation_learning_path_boundary_artifacts_pass() -> None:
    assert validate_foundation_learning_path_boundary() == []


def test_learning_path_witness_has_expected_identity_and_blockers() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "learning-path witness")

    assert payload["witness_id"] == EXPECTED_WITNESS_ID
    assert tuple(
        (surface["surface_id"], surface["surface_type"], surface["state"])
        for surface in payload["learning_path_surfaces"]
    ) == EXPECTED_SURFACES
    assert payload["skill_readiness_claimed"] is False
    assert payload["training_completion_claimed"] is False
    assert payload["certification_claimed"] is False
    assert payload["paid_course_allowed"] is False
    assert payload["mentor_assignment_allowed"] is False
    assert payload["external_account_use_allowed"] is False
    assert payload["deployment_allowed"] is False


def test_witness_rejects_skill_readiness_claim() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "learning-path witness")
    candidate = deepcopy(payload)
    candidate["skill_readiness_claimed"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "learning_path_root_value_invalid" for finding in findings)


def test_witness_rejects_certification_and_completion_claims() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "learning-path witness")
    candidate = deepcopy(payload)
    candidate["certification_claimed"] = True
    candidate["curriculum_completion_claimed"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "learning_path_root_value_invalid" for finding in findings)


def test_witness_rejects_paid_course_and_mentor_assignment() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "learning-path witness")
    candidate = deepcopy(payload)
    candidate["paid_course_allowed"] = True
    candidate["mentor_assignment_allowed"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "learning_path_root_value_invalid" for finding in findings)


def test_witness_rejects_surface_state_promotion() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "learning-path witness")
    candidate = deepcopy(payload)
    candidate["learning_path_surfaces"][0]["state"] = "Ready"

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "learning_path_surface_inventory_invalid" for finding in findings)
    assert any(finding.rule_id == "learning_path_surface_state_invalid" for finding in findings)


def test_witness_rejects_private_account_or_certificate_value() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "learning-path witness")
    candidate = deepcopy(payload)
    candidate["learning_path_surfaces"][0]["public_safe_note"] = "account_id=private certificate_id=secret"

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "learning_path_forbidden_private_value_pattern" for finding in findings)


def test_witness_rejects_skill_ready_phrase() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "learning-path witness")
    candidate = deepcopy(payload)
    candidate["next_action"] = "skill is ready and training is complete"

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "learning_path_forbidden_promotion_phrase" for finding in findings)
