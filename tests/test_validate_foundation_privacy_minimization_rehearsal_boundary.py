"""Tests for the Foundation Mode privacy minimization rehearsal validator.

Purpose: prove privacy minimization rehearsal stays local and does not
authorize minimization approval, personal-data collection, storage, consent
capture, retention/deletion approval, privacy notice publication, tracking,
processor activation, legal clearance, customer access, or deployment.
Governance scope: Foundation Mode, privacy minimization rehearsal planning,
local data-category questions, prohibited-field questions, consent exclusion,
retention/deletion draft exclusion, analytics exclusion, processor exclusion,
legal-clearance blocking, customer-access blocking, and deployment blocking.
Dependencies: scripts.validate_foundation_privacy_minimization_rehearsal_boundary.
Invariants: rehearsal surfaces remain AwaitingEvidence and reject private
value drift, execution drift, and readiness promotion drift.
"""

from __future__ import annotations

from copy import deepcopy
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validate_foundation_privacy_minimization_rehearsal_boundary import (  # noqa: E402
    DEFAULT_PACKET_PATH,
    EXPECTED_SURFACES,
    EXPECTED_WITNESS_ID,
    load_json_object,
    validate_foundation_privacy_minimization_rehearsal_boundary,
    validate_packet,
)


def test_foundation_privacy_minimization_rehearsal_boundary_artifacts_pass() -> None:
    assert validate_foundation_privacy_minimization_rehearsal_boundary() == []


def test_privacy_minimization_rehearsal_witness_has_expected_identity_and_blockers() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "privacy minimization rehearsal witness")

    assert payload["witness_id"] == EXPECTED_WITNESS_ID
    assert tuple(
        (surface["surface_id"], surface["surface_type"], surface["state"])
        for surface in payload["surfaces"]
    ) == EXPECTED_SURFACES
    assert payload["minimization_rehearsal_executed"] is False
    assert payload["minimization_policy_approved"] is False
    assert payload["personal_data_collection_allowed"] is False
    assert payload["personal_data_storage_allowed"] is False
    assert payload["processor_activation_allowed"] is False
    assert payload["deployment_allowed"] is False


def test_witness_rejects_minimization_and_personal_data_claims() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "privacy minimization rehearsal witness")
    candidate = deepcopy(payload)
    candidate["minimization_rehearsal_executed"] = True
    candidate["minimization_policy_approved"] = True
    candidate["personal_data_collection_allowed"] = True
    candidate["personal_data_storage_allowed"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "privacy_minimization_rehearsal_root_value_invalid" for finding in findings)


def test_witness_rejects_consent_retention_and_notice_claims() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "privacy minimization rehearsal witness")
    candidate = deepcopy(payload)
    candidate["consent_capture_allowed"] = True
    candidate["retention_deletion_policy_approved"] = True
    candidate["privacy_notice_publication_allowed"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "privacy_minimization_rehearsal_root_value_invalid" for finding in findings)


def test_witness_rejects_tracking_processor_legal_customer_and_deployment() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "privacy minimization rehearsal witness")
    candidate = deepcopy(payload)
    candidate["analytics_tracking_allowed"] = True
    candidate["processor_activation_allowed"] = True
    candidate["legal_clearance_claimed"] = True
    candidate["customer_access_allowed"] = True
    candidate["deployment_allowed"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "privacy_minimization_rehearsal_root_value_invalid" for finding in findings)


def test_witness_rejects_surface_state_promotion() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "privacy minimization rehearsal witness")
    candidate = deepcopy(payload)
    candidate["surfaces"][0]["state"] = "Ready"

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "privacy_minimization_rehearsal_surface_inventory_invalid" for finding in findings)
    assert any(finding.rule_id == "privacy_minimization_rehearsal_surface_state_invalid" for finding in findings)


def test_witness_rejects_personal_data_value_shape() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "privacy minimization rehearsal witness")
    candidate = deepcopy(payload)
    candidate["surfaces"][0]["public_safe_note"] = "name_value=private-person"

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "privacy_minimization_rehearsal_forbidden_value_pattern" for finding in findings)


def test_witness_rejects_privacy_ready_phrase() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "privacy minimization rehearsal witness")
    candidate = deepcopy(payload)
    candidate["next_action"] = "privacy-ready after this draft"

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "privacy_minimization_rehearsal_forbidden_promotion_phrase" for finding in findings)
