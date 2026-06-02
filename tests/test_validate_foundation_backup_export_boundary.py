"""Tests for the Foundation Mode backup/export boundary validator.

Purpose: prove backup/export preparation stays local and does not authorize
backup execution, cloud backup, external export, public archive, private path
recording, secret export, personal-data export, deletion operation,
restore-readiness, or deployment claims.
Governance scope: Foundation Mode, local backup/export posture, redaction
posture, retention/deletion caution, public-safe planning witness, private-value
exclusion, and deployment blocking.
Dependencies: scripts.validate_foundation_backup_export_boundary.
Invariants: backup/export surfaces remain AwaitingEvidence and reject readiness
promotion or private value drift.
"""

from __future__ import annotations

from copy import deepcopy
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validate_foundation_backup_export_boundary import (  # noqa: E402
    DEFAULT_PACKET_PATH,
    EXPECTED_SURFACES,
    EXPECTED_WITNESS_ID,
    load_json_object,
    validate_foundation_backup_export_boundary,
    validate_packet,
)


def test_foundation_backup_export_boundary_artifacts_pass() -> None:
    assert validate_foundation_backup_export_boundary() == []


def test_backup_export_witness_has_expected_identity_and_blockers() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "backup/export witness")

    assert payload["witness_id"] == EXPECTED_WITNESS_ID
    assert tuple(
        (surface["surface_id"], surface["surface_type"], surface["state"])
        for surface in payload["backup_export_surfaces"]
    ) == EXPECTED_SURFACES
    assert payload["backup_execution_allowed"] is False
    assert payload["cloud_backup_allowed"] is False
    assert payload["external_export_allowed"] is False
    assert payload["public_archive_allowed"] is False
    assert payload["secret_export_allowed"] is False
    assert payload["deployment_allowed"] is False


def test_witness_rejects_backup_execution_claim() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "backup/export witness")
    candidate = deepcopy(payload)
    candidate["backup_execution_allowed"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "backup_export_root_value_invalid" for finding in findings)


def test_witness_rejects_cloud_backup_claim() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "backup/export witness")
    candidate = deepcopy(payload)
    candidate["cloud_backup_allowed"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "backup_export_root_value_invalid" for finding in findings)


def test_witness_rejects_external_export_or_public_archive_claim() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "backup/export witness")
    candidate = deepcopy(payload)
    candidate["external_export_allowed"] = True
    candidate["public_archive_allowed"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "backup_export_root_value_invalid" for finding in findings)


def test_witness_rejects_surface_state_promotion() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "backup/export witness")
    candidate = deepcopy(payload)
    candidate["backup_export_surfaces"][0]["state"] = "Ready"

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "backup_export_surface_inventory_invalid" for finding in findings)
    assert any(finding.rule_id == "backup_export_surface_state_invalid" for finding in findings)


def test_witness_rejects_private_path_and_export_target_shape() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "backup/export witness")
    candidate = deepcopy(payload)
    candidate["backup_export_surfaces"][0]["public_safe_note"] = "path=C:\\private\\backup"

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "backup_export_forbidden_private_value_pattern" for finding in findings)


def test_witness_rejects_backup_ready_phrase() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "backup/export witness")
    candidate = deepcopy(payload)
    candidate["next_action"] = "backup is ready after this draft"

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "backup_export_forbidden_promotion_phrase" for finding in findings)
