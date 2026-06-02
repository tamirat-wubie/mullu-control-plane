"""Tests for the Foundation Mode privacy/data boundary validator.

Purpose: prove privacy/data preparation stays local and does not authorize
personal-data collection, storage, consent capture, tracking, processor
activation, policy publication, customer access, legal clearance, or deployment
claims.
Governance scope: Foundation Mode, privacy posture, data-retention posture,
public-safe planning witness, private-value exclusion, and deployment blocking.
Dependencies: scripts.validate_foundation_privacy_data_boundary.
Invariants: privacy/data surfaces remain AwaitingEvidence and reject readiness
promotion or private value drift.
"""

from __future__ import annotations

from copy import deepcopy
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validate_foundation_privacy_data_boundary import (  # noqa: E402
    DEFAULT_PACKET_PATH,
    EXPECTED_SURFACES,
    EXPECTED_WITNESS_ID,
    load_json_object,
    validate_foundation_privacy_data_boundary,
    validate_packet,
)


def test_foundation_privacy_data_boundary_artifacts_pass() -> None:
    assert validate_foundation_privacy_data_boundary() == []


def test_privacy_data_witness_has_expected_identity_and_blockers() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "privacy/data witness")

    assert payload["witness_id"] == EXPECTED_WITNESS_ID
    assert tuple(
        (surface["surface_id"], surface["surface_type"], surface["state"])
        for surface in payload["privacy_surfaces"]
    ) == EXPECTED_SURFACES
    assert payload["personal_data_collection_allowed"] is False
    assert payload["personal_data_storage_allowed"] is False
    assert payload["retention_policy_approved"] is False
    assert payload["privacy_notice_published"] is False
    assert payload["customer_access_allowed"] is False
    assert payload["deployment_allowed"] is False


def test_witness_rejects_personal_data_collection_claim() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "privacy/data witness")
    candidate = deepcopy(payload)
    candidate["personal_data_collection_allowed"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "privacy_data_root_value_invalid" for finding in findings)


def test_witness_rejects_storage_claim() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "privacy/data witness")
    candidate = deepcopy(payload)
    candidate["personal_data_storage_allowed"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "privacy_data_root_value_invalid" for finding in findings)


def test_witness_rejects_retention_policy_promotion() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "privacy/data witness")
    candidate = deepcopy(payload)
    candidate["retention_policy_approved"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "privacy_data_root_value_invalid" for finding in findings)


def test_witness_rejects_surface_state_promotion() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "privacy/data witness")
    candidate = deepcopy(payload)
    candidate["privacy_surfaces"][0]["state"] = "Ready"

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "privacy_data_surface_inventory_invalid" for finding in findings)
    assert any(finding.rule_id == "privacy_data_surface_state_invalid" for finding in findings)


def test_witness_rejects_email_value() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "privacy/data witness")
    candidate = deepcopy(payload)
    candidate["privacy_surfaces"][0]["public_safe_note"] = "customer record=support@example.test"

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "privacy_data_forbidden_private_value_pattern" for finding in findings)


def test_witness_rejects_privacy_ready_phrase() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "privacy/data witness")
    candidate = deepcopy(payload)
    candidate["next_action"] = "privacy-ready after this draft"

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "privacy_data_forbidden_promotion_phrase" for finding in findings)
