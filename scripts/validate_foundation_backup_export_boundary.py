#!/usr/bin/env python3
"""Validate the Foundation Mode backup/export boundary.

Purpose: keep backup/export preparation local while backup execution, cloud
backup, external export, public archive, private path recording, secret export,
personal-data export, deletion operation, restore-readiness, and deployment
claims remain blocked.
Governance scope: Foundation Mode, local backup/export posture, redaction
posture, retention/deletion caution, public-safe planning witness, private-value
exclusion, and deployment blocking.
Dependencies: docs/FOUNDATION_BACKUP_EXPORT_BOUNDARY.md and
examples/foundation_backup_export_witness.awaiting_evidence.json.
Invariants:
  - Validation is read-only.
  - The witness records local backup/export planning only.
  - No backup execution, cloud backup, external export, public archive, private
    path recording, secret export, personal-data export, deletion operation,
    restore-readiness, private value, or deployment claim is allowed.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
import re
import sys
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DOC_PATH = REPO_ROOT / "docs" / "FOUNDATION_BACKUP_EXPORT_BOUNDARY.md"
DEFAULT_PACKET_PATH = REPO_ROOT / "examples" / "foundation_backup_export_witness.awaiting_evidence.json"

EXPECTED_WITNESS_ID = "foundation_backup_export_witness.awaiting_evidence.v1"
EXPECTED_BLOCKED_CLAIMS = (
    "backup execution",
    "cloud backup activation",
    "external export",
    "public archive publication",
    "private path recording",
    "secret export",
    "personal data export",
    "deletion operation",
    "restore readiness",
    "deployment readiness",
)
EXPECTED_SURFACES = (
    ("backup_inventory_draft", "local_draft", "AwaitingEvidence"),
    ("export_scope_questions", "local_draft", "AwaitingEvidence"),
    ("local_archive_questions", "local_draft", "AwaitingEvidence"),
    ("restore_drill_questions", "local_draft", "AwaitingEvidence"),
    ("redaction_checklist", "local_draft", "AwaitingEvidence"),
    ("retention_snapshot_questions", "local_draft", "AwaitingEvidence"),
    ("deletion_recovery_questions", "local_draft", "AwaitingEvidence"),
    ("handoff_bundle_questions", "local_draft", "AwaitingEvidence"),
)
EXPECTED_ROOT_KEYS = {
    "backup_execution_allowed",
    "backup_export_surfaces",
    "blocked_claims",
    "cloud_backup_allowed",
    "deletion_operation_allowed",
    "deployment_allowed",
    "external_export_allowed",
    "next_action",
    "personal_data_export_allowed",
    "private_path_recording_allowed",
    "public_archive_allowed",
    "restore_readiness_claimed",
    "schema_version",
    "secret_export_allowed",
    "solver_outcome",
    "status",
    "witness_id",
}
EXPECTED_SURFACE_KEYS = {
    "evidence_ref",
    "public_safe_note",
    "state",
    "surface_id",
    "surface_type",
}
REQUIRED_DOC_PHRASES = (
    "Foundation Backup Export Boundary",
    "Witness packet: [`../examples/foundation_backup_export_witness.awaiting_evidence.json`]",
    "Rule: Backup/export preparation is a local planning boundary, not permission to move repository or private data.",
    "No backup execution, cloud backup activation, external export, public archive",
    "backup_export_boundary_state=AwaitingEvidence",
    "backup_execution_allowed=false",
    "cloud_backup_allowed=false",
    "external_export_allowed=false",
    "deployment_allowed=false",
    "python scripts/validate_foundation_backup_export_boundary.py",
)
FORBIDDEN_VALUE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("url_value", re.compile(r"https?://", re.IGNORECASE)),
    ("email_value", re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)),
    ("private_path", re.compile(r"\b[A-Za-z]:[\\/]|\\\\", re.IGNORECASE)),
    ("secret_assignment", re.compile(r"\b(?:password|secret|token|api[_ -]?key)\s*=", re.IGNORECASE)),
    (
        "archive_target_assignment",
        re.compile(r"\b(?:archive|backup|export|bundle|target|path)[_ -]?(?:target|path|dir|url|uri|ref)?\s*=", re.IGNORECASE),
    ),
    (
        "cloud_storage_target_assignment",
        re.compile(r"\b(?:bucket|drive|s3|gcs|blob|storage|cloud)[_ -]?(?:target|id|ref|path|url|uri)?\s*=", re.IGNORECASE),
    ),
    (
        "deletion_target_assignment",
        re.compile(r"\b(?:delete|deletion|remove|purge)[_ -]?(?:target|path|id|ref)?\s*=", re.IGNORECASE),
    ),
    (
        "personal_data_assignment",
        re.compile(r"\b(?:person|personal|pii|user|customer)[_ -]?(?:data|record|email|name|id)?\s*=", re.IGNORECASE),
    ),
)
FORBIDDEN_PROMOTION_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("backup_ready", re.compile(r"\bbackup\s+(?:is\s+)?ready\b", re.IGNORECASE)),
    ("backup_complete", re.compile(r"\bbackup\s+(?:is\s+)?complete\b", re.IGNORECASE)),
    ("cloud_backup_active", re.compile(r"\bcloud\s+backup\s+(?:is\s+)?(?:active|enabled|ready)\b", re.IGNORECASE)),
    ("export_complete", re.compile(r"\bexport\s+(?:is\s+)?complete\b", re.IGNORECASE)),
    ("public_archive_published", re.compile(r"\bpublic\s+archive\s+(?:is\s+)?published\b", re.IGNORECASE)),
    ("restore_ready", re.compile(r"\brestore\s+(?:is\s+)?ready\b", re.IGNORECASE)),
    ("restore_verified", re.compile(r"\brestore\s+(?:is\s+)?verified\b", re.IGNORECASE)),
    ("deletion_complete", re.compile(r"\bdeletion\s+(?:is\s+)?complete\b", re.IGNORECASE)),
    ("handoff_bundle_published", re.compile(r"\bhandoff\s+bundle\s+(?:is\s+)?published\b", re.IGNORECASE)),
    ("deployment_ready", re.compile(r"\bdeployment\s+(?:is\s+)?ready\b", re.IGNORECASE)),
)


@dataclass(frozen=True, slots=True)
class BackupExportFinding:
    """One deterministic backup/export boundary validation finding."""

    rule_id: str
    message: str


def load_text(path: Path, label: str) -> str:
    """Load one text artifact with explicit path errors."""

    if not path.exists():
        raise FileNotFoundError(f"missing {label}: {path}")
    if not path.is_file():
        raise IsADirectoryError(f"{label} path is not a file: {path}")
    return path.read_text(encoding="utf-8")


def load_json_object(path: Path, label: str) -> dict[str, Any]:
    """Load one JSON object with explicit path and type errors."""

    if not path.exists():
        raise FileNotFoundError(f"missing {label}: {path}")
    if not path.is_file():
        raise IsADirectoryError(f"{label} path is not a file: {path}")
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError(f"{label} must be a JSON object")
    return payload


def validate_doc_text(text: str) -> list[BackupExportFinding]:
    """Return findings for missing backup/export documentation anchors."""

    findings: list[BackupExportFinding] = []
    for phrase in REQUIRED_DOC_PHRASES:
        if phrase not in text:
            findings.append(
                BackupExportFinding(
                    "foundation_backup_export_doc_phrase_missing",
                    f"backup/export boundary doc missing required phrase: {phrase}",
                )
            )
    return findings


def validate_packet(payload: dict[str, Any]) -> list[BackupExportFinding]:
    """Return findings for backup/export witness drift."""

    findings: list[BackupExportFinding] = []
    findings.extend(validate_root_contract(payload))
    findings.extend(validate_backup_export_surfaces(payload.get("backup_export_surfaces")))
    findings.extend(validate_forbidden_value_patterns(payload))
    findings.extend(validate_forbidden_promotion_patterns(payload))
    return findings


def validate_root_contract(payload: dict[str, Any]) -> list[BackupExportFinding]:
    """Return findings for root-level backup/export witness drift."""

    findings: list[BackupExportFinding] = []
    if set(payload) != EXPECTED_ROOT_KEYS:
        findings.append(
            BackupExportFinding(
                "backup_export_root_keys_invalid",
                f"root keys must be: {', '.join(sorted(EXPECTED_ROOT_KEYS))}",
            )
        )
    expected_values = {
        "witness_id": EXPECTED_WITNESS_ID,
        "schema_version": 1,
        "status": "AwaitingEvidence",
        "solver_outcome": "AwaitingEvidence",
        "backup_execution_allowed": False,
        "cloud_backup_allowed": False,
        "external_export_allowed": False,
        "public_archive_allowed": False,
        "private_path_recording_allowed": False,
        "secret_export_allowed": False,
        "personal_data_export_allowed": False,
        "deletion_operation_allowed": False,
        "restore_readiness_claimed": False,
        "deployment_allowed": False,
    }
    for key, expected_value in expected_values.items():
        if payload.get(key) != expected_value:
            findings.append(
                BackupExportFinding(
                    "backup_export_root_value_invalid",
                    f"{key} must be {expected_value!r}",
                )
            )
    if tuple(payload.get("blocked_claims") or ()) != EXPECTED_BLOCKED_CLAIMS:
        findings.append(
            BackupExportFinding(
                "backup_export_blocked_claims_invalid",
                f"blocked_claims must be: {', '.join(EXPECTED_BLOCKED_CLAIMS)}",
            )
        )
    next_action = payload.get("next_action")
    if not isinstance(next_action, str) or "do not run backups" not in next_action:
        findings.append(
            BackupExportFinding(
                "backup_export_next_action_invalid",
                "next_action must preserve the closed backup/export boundary",
            )
        )
    return findings


def validate_backup_export_surfaces(backup_export_surfaces: object) -> list[BackupExportFinding]:
    """Return findings for backup/export surface witness drift."""

    findings: list[BackupExportFinding] = []
    if not isinstance(backup_export_surfaces, list) or not all(
        isinstance(surface, dict) for surface in backup_export_surfaces
    ):
        return [
            BackupExportFinding(
                "backup_export_surfaces_invalid",
                "backup_export_surfaces must be a list of objects",
            )
        ]
    observed_surfaces = tuple(
        (surface.get("surface_id"), surface.get("surface_type"), surface.get("state"))
        for surface in backup_export_surfaces
    )
    if observed_surfaces != EXPECTED_SURFACES:
        findings.append(
            BackupExportFinding(
                "backup_export_surface_inventory_invalid",
                "backup/export surface inventory does not match the Foundation Mode backup/export set",
            )
        )
    surface_ids = [surface.get("surface_id") for surface in backup_export_surfaces]
    if len(set(surface_ids)) != len(surface_ids):
        findings.append(BackupExportFinding("backup_export_surface_duplicate", "surface ids must be unique"))
    for surface in backup_export_surfaces:
        surface_id = str(surface.get("surface_id", "<missing>"))
        if set(surface) != EXPECTED_SURFACE_KEYS:
            findings.append(
                BackupExportFinding(
                    "backup_export_surface_keys_invalid",
                    f"{surface_id} surface keys must be: {', '.join(sorted(EXPECTED_SURFACE_KEYS))}",
                )
            )
        if surface.get("state") != "AwaitingEvidence":
            findings.append(
                BackupExportFinding(
                    "backup_export_surface_state_invalid",
                    f"{surface_id} state must be AwaitingEvidence",
                )
            )
        if surface.get("evidence_ref") != "manual_preparation_pending":
            findings.append(
                BackupExportFinding(
                    "backup_export_surface_evidence_invalid",
                    f"{surface_id} evidence_ref must stay manual_preparation_pending in the committed packet",
                )
            )
        if not isinstance(surface.get("public_safe_note"), str) or not surface["public_safe_note"].strip():
            findings.append(
                BackupExportFinding(
                    "backup_export_surface_note_invalid",
                    f"{surface_id} public_safe_note must be a non-empty string",
                )
            )
    return findings


def validate_forbidden_value_patterns(payload: dict[str, Any]) -> list[BackupExportFinding]:
    """Return findings for private path, target, secret, personal-data, or storage-shaped values."""

    serialized_payload = json.dumps(payload, sort_keys=True)
    findings: list[BackupExportFinding] = []
    for rule_id, pattern in FORBIDDEN_VALUE_PATTERNS:
        if pattern.search(serialized_payload):
            findings.append(
                BackupExportFinding(
                    "backup_export_forbidden_private_value_pattern",
                    f"backup/export witness contains forbidden value pattern: {rule_id}",
                )
            )
    return findings


def validate_forbidden_promotion_patterns(payload: dict[str, Any]) -> list[BackupExportFinding]:
    """Return findings if the witness drifts into backup/export readiness claims."""

    serialized_payload = json.dumps(payload, sort_keys=True)
    findings: list[BackupExportFinding] = []
    for rule_id, pattern in FORBIDDEN_PROMOTION_PATTERNS:
        if pattern.search(serialized_payload):
            findings.append(
                BackupExportFinding(
                    "backup_export_forbidden_promotion_phrase",
                    f"backup/export witness contains forbidden promotion pattern: {rule_id}",
                )
            )
    return findings


def validate_foundation_backup_export_boundary(
    doc_path: Path = DEFAULT_DOC_PATH,
    packet_path: Path = DEFAULT_PACKET_PATH,
) -> list[BackupExportFinding]:
    """Validate the Foundation Mode backup/export boundary artifacts."""

    doc_text = load_text(doc_path, "backup/export boundary doc")
    packet_payload = load_json_object(packet_path, "backup/export witness packet")
    return [
        *validate_doc_text(doc_text),
        *validate_packet(packet_payload),
    ]


def main(argv: list[str] | None = None) -> int:
    """Validate backup/export boundary artifacts and print deterministic status."""

    parser = argparse.ArgumentParser(description="Validate Foundation Mode backup/export boundary artifacts.")
    parser.add_argument("--doc", type=Path, default=DEFAULT_DOC_PATH)
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET_PATH)
    args = parser.parse_args(argv)

    try:
        findings = validate_foundation_backup_export_boundary(args.doc, args.packet)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"[FAIL] foundation_backup_export_load: {exc}", file=sys.stderr)
        print("STATUS: failed", file=sys.stderr)
        return 1

    if findings:
        for finding in findings:
            print(f"[FAIL] {finding.rule_id}: {finding.message}", file=sys.stderr)
        print("STATUS: failed", file=sys.stderr)
        return 1
    print("[PASS] foundation_backup_export_doc")
    print("[PASS] foundation_backup_export_witness")
    print("STATUS: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
