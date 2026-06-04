"""Tests for the Foundation Mode private recovery rehearsal boundary validator.

Purpose: prove recovery rehearsal preparation stays public-safe and does not
authorize private recovery material, credential use, backup, restore, provider,
billing, deletion, customer-data, personal-data, or deployment actions.
Governance scope: Foundation Mode, private recovery rehearsal planning,
dry-run scope, public-safe checklist evidence, private-material exclusion,
credential-use blocking, backup/restore blocking, provider-access blocking,
deletion blocking, billing blocking, and deployment blocking.
Dependencies: scripts.validate_foundation_private_recovery_rehearsal_boundary.
Invariants: rehearsal surfaces remain AwaitingEvidence and reject private value
drift, execution drift, and readiness promotion drift.
"""

from __future__ import annotations

from copy import deepcopy
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validate_foundation_private_recovery_rehearsal_boundary import (  # noqa: E402
    DEFAULT_PACKET_PATH,
    EXPECTED_SURFACES,
    EXPECTED_WITNESS_ID,
    load_json_object,
    validate_foundation_private_recovery_rehearsal_boundary,
    validate_packet,
)


def test_foundation_private_recovery_rehearsal_boundary_artifacts_pass() -> None:
    assert validate_foundation_private_recovery_rehearsal_boundary() == []


def test_rehearsal_witness_has_expected_identity_and_blockers() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "private recovery rehearsal witness")

    assert payload["witness_id"] == EXPECTED_WITNESS_ID
    assert tuple(
        (surface["surface_id"], surface["surface_type"], surface["state"])
        for surface in payload["surfaces"]
    ) == EXPECTED_SURFACES
    assert payload["recovery_rehearsal_executed"] is False
    assert payload["private_recovery_material_recording_allowed"] is False
    assert payload["credential_use_allowed"] is False
    assert payload["secret_use_allowed"] is False
    assert payload["backup_execution_allowed"] is False
    assert payload["restore_execution_allowed"] is False
    assert payload["provider_account_access_allowed"] is False
    assert payload["deployment_allowed"] is False


def test_witness_rejects_rehearsal_and_restore_execution() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "private recovery rehearsal witness")
    candidate = deepcopy(payload)
    candidate["recovery_rehearsal_executed"] = True
    candidate["restore_execution_allowed"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "private_recovery_rehearsal_root_value_invalid" for finding in findings)


def test_witness_rejects_private_material_and_secret_use() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "private recovery rehearsal witness")
    candidate = deepcopy(payload)
    candidate["private_recovery_material_recording_allowed"] = True
    candidate["secret_use_allowed"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "private_recovery_rehearsal_root_value_invalid" for finding in findings)


def test_witness_rejects_backup_provider_and_billing_actions() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "private recovery rehearsal witness")
    candidate = deepcopy(payload)
    candidate["backup_execution_allowed"] = True
    candidate["provider_account_access_allowed"] = True
    candidate["billing_action_allowed"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "private_recovery_rehearsal_root_value_invalid" for finding in findings)


def test_witness_rejects_customer_personal_data_and_deployment_actions() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "private recovery rehearsal witness")
    candidate = deepcopy(payload)
    candidate["customer_data_handling_allowed"] = True
    candidate["personal_data_handling_allowed"] = True
    candidate["deployment_allowed"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "private_recovery_rehearsal_root_value_invalid" for finding in findings)


def test_witness_rejects_surface_state_promotion() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "private recovery rehearsal witness")
    candidate = deepcopy(payload)
    candidate["surfaces"][0]["state"] = "Ready"

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "private_recovery_rehearsal_surface_inventory_invalid" for finding in findings)
    assert any(finding.rule_id == "private_recovery_rehearsal_surface_state_invalid" for finding in findings)


def test_witness_rejects_private_path_shape() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "private recovery rehearsal witness")
    candidate = deepcopy(payload)
    candidate["surfaces"][1]["public_safe_note"] = "restore_path=C:/private/recovery"

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "private_recovery_rehearsal_forbidden_value_pattern" for finding in findings)


def test_witness_rejects_recovery_code_shape() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "private recovery rehearsal witness")
    candidate = deepcopy(payload)
    candidate["surfaces"][1]["public_safe_note"] = "recovery_code=do-not-store"

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "private_recovery_rehearsal_forbidden_value_pattern" for finding in findings)


def test_witness_rejects_restore_ready_phrase() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "private recovery rehearsal witness")
    candidate = deepcopy(payload)
    candidate["next_action"] = "restore is ready after this rehearsal"

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "private_recovery_rehearsal_forbidden_promotion_phrase" for finding in findings)
