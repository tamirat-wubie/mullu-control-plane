#!/usr/bin/env python3
"""Validate the Foundation Mode private recovery rehearsal boundary.

Purpose: keep recovery rehearsal preparation public-safe while backup, restore,
credential, provider, billing, deletion, customer-data, personal-data, and
deployment actions remain blocked.
Governance scope: Foundation Mode, private recovery rehearsal planning,
dry-run scope, public-safe checklist evidence, recovery-material exclusion,
credential-use blocking, backup/restore blocking, provider-access blocking,
deletion blocking, billing blocking, and deployment blocking.
Dependencies: docs/FOUNDATION_PRIVATE_RECOVERY_REHEARSAL_BOUNDARY.md and
examples/foundation_private_recovery_rehearsal_witness.awaiting_evidence.json.
Invariants:
  - Validation is read-only.
  - The witness records recovery rehearsal planning only.
  - No rehearsal execution, private recovery material, credential use, secret
    use, backup execution, restore execution, cloud sync, external export,
    deletion, provider access, billing action, customer-data handling,
    personal-data handling, restore-readiness, or deployment claim is allowed.
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
DEFAULT_DOC_PATH = REPO_ROOT / "docs" / "FOUNDATION_PRIVATE_RECOVERY_REHEARSAL_BOUNDARY.md"
DEFAULT_PACKET_PATH = REPO_ROOT / "examples" / "foundation_private_recovery_rehearsal_witness.awaiting_evidence.json"

EXPECTED_WITNESS_ID = "foundation_private_recovery_rehearsal_witness.awaiting_evidence.v1"
EXPECTED_BLOCKED_CLAIMS = (
    "recovery rehearsal execution",
    "private recovery material recording",
    "credential use",
    "secret use",
    "backup execution",
    "restore execution",
    "cloud sync",
    "external export",
    "deletion operation",
    "provider account access",
    "billing action",
    "customer-data handling",
    "personal-data handling",
    "restore readiness",
    "deployment readiness",
)
EXPECTED_SURFACES = (
    ("rehearsal_scope", "local_draft", "AwaitingEvidence"),
    ("public_safe_inventory_check", "local_draft", "AwaitingEvidence"),
    ("private_material_exclusion", "local_draft", "AwaitingEvidence"),
    ("credential_use_stop", "local_draft", "AwaitingEvidence"),
    ("backup_restore_dry_run_questions", "local_draft", "AwaitingEvidence"),
    ("failure_mode_questions", "local_draft", "AwaitingEvidence"),
    ("receipt_questions", "local_draft", "AwaitingEvidence"),
    ("handoff_questions", "local_draft", "AwaitingEvidence"),
)
EXPECTED_ROOT_KEYS = {
    "backup_execution_allowed",
    "billing_action_allowed",
    "blocked_claims",
    "cloud_sync_allowed",
    "credential_use_allowed",
    "customer_data_handling_allowed",
    "deletion_operation_allowed",
    "deployment_allowed",
    "external_export_allowed",
    "next_action",
    "personal_data_handling_allowed",
    "private_recovery_material_recording_allowed",
    "provider_account_access_allowed",
    "recovery_rehearsal_executed",
    "restore_execution_allowed",
    "restore_readiness_claimed",
    "schema_version",
    "secret_use_allowed",
    "solver_outcome",
    "status",
    "surfaces",
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
    "Foundation Private Recovery Rehearsal Boundary",
    "Witness packet: [`../examples/foundation_private_recovery_rehearsal_witness.awaiting_evidence.json`]",
    "Rule: Private recovery rehearsal preparation is a local dry-run planning",
    "No recovery rehearsal execution, private recovery material recording,",
    "private_recovery_rehearsal_boundary_state=AwaitingEvidence",
    "recovery_rehearsal_executed=false",
    "private_recovery_material_recording_allowed=false",
    "credential_use_allowed=false",
    "backup_execution_allowed=false",
    "restore_execution_allowed=false",
    "restore_readiness_claimed=false",
    "deployment_allowed=false",
    "python scripts/validate_foundation_private_recovery_rehearsal_boundary.py",
)
FORBIDDEN_VALUE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("url_value", re.compile(r"https?://", re.IGNORECASE)),
    ("email_value", re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)),
    ("private_path", re.compile(r"\b[A-Za-z]:[\\/]|\\\\", re.IGNORECASE)),
    (
        "recovery_code_assignment",
        re.compile(r"\b(?:recovery[_ -]?code|backup[_ -]?code|mfa[_ -]?code)\s*=", re.IGNORECASE),
    ),
    (
        "secret_or_credential_assignment",
        re.compile(r"\b(?:password|secret|token|api[_ -]?key|credential|client[_ -]?secret)\s*=", re.IGNORECASE),
    ),
    ("private_key_material", re.compile(r"BEGIN [A-Z ]*PRIVATE KEY")),
    (
        "provider_account_assignment",
        re.compile(r"\b(?:provider|account|tenant|project|dns|domain)[_ -]?(?:id|ref|target|value)?\s*=", re.IGNORECASE),
    ),
    (
        "backup_restore_target_assignment",
        re.compile(r"\b(?:backup|restore|archive|export|sync)[_ -]?(?:target|path|url|ref|value|status)?\s*=", re.IGNORECASE),
    ),
    (
        "deletion_target_assignment",
        re.compile(r"\b(?:delete|deletion|remove|purge)[_ -]?(?:target|path|ref|value|status)?\s*=", re.IGNORECASE),
    ),
    (
        "billing_assignment",
        re.compile(r"\b(?:billing|payment|invoice|card|subscription)[_ -]?(?:id|ref|target|value|status)?\s*=", re.IGNORECASE),
    ),
    (
        "customer_data_assignment",
        re.compile(r"\b(?:customer|personal|person|participant|user)[_ -]?(?:data|id|name|email|ref|value|target)?\s*=", re.IGNORECASE),
    ),
    (
        "deployment_assignment",
        re.compile(r"\b(?:deploy|deployment|production|staging)[_ -]?(?:target|url|ref|value|status)?\s*=", re.IGNORECASE),
    ),
)
FORBIDDEN_PROMOTION_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("rehearsal_executed", re.compile(r"\brehearsal\s+(?:is\s+)?executed\b", re.IGNORECASE)),
    ("recovery_ready", re.compile(r"\brecovery\s+(?:is\s+)?ready\b", re.IGNORECASE)),
    ("restore_ready", re.compile(r"\brestore\s+(?:is\s+)?ready\b", re.IGNORECASE)),
    ("backup_ready", re.compile(r"\bbackup\s+(?:is\s+)?ready\b", re.IGNORECASE)),
    ("provider_ready", re.compile(r"\bprovider\s+(?:is\s+)?ready\b", re.IGNORECASE)),
    ("billing_ready", re.compile(r"\bbilling\s+(?:is\s+)?ready\b", re.IGNORECASE)),
    ("customer_data_ready", re.compile(r"\bcustomer\s+data\s+(?:is\s+)?ready\b", re.IGNORECASE)),
    ("personal_data_ready", re.compile(r"\bpersonal\s+data\s+(?:is\s+)?ready\b", re.IGNORECASE)),
    ("deployment_ready", re.compile(r"\bdeployment\s+(?:is\s+)?ready\b", re.IGNORECASE)),
)


@dataclass(frozen=True, slots=True)
class PrivateRecoveryRehearsalFinding:
    """One deterministic private recovery rehearsal validation finding."""

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


def validate_doc_text(text: str) -> list[PrivateRecoveryRehearsalFinding]:
    """Return findings for missing private recovery rehearsal documentation anchors."""

    findings: list[PrivateRecoveryRehearsalFinding] = []
    for phrase in REQUIRED_DOC_PHRASES:
        if phrase not in text:
            findings.append(
                PrivateRecoveryRehearsalFinding(
                    "foundation_private_recovery_rehearsal_doc_phrase_missing",
                    f"private recovery rehearsal boundary doc missing required phrase: {phrase}",
                )
            )
    return findings


def validate_packet(payload: dict[str, Any]) -> list[PrivateRecoveryRehearsalFinding]:
    """Return findings for private recovery rehearsal witness drift."""

    findings: list[PrivateRecoveryRehearsalFinding] = []
    findings.extend(validate_root_contract(payload))
    findings.extend(validate_surfaces(payload.get("surfaces")))
    findings.extend(validate_forbidden_value_patterns(payload))
    findings.extend(validate_forbidden_promotion_patterns(payload))
    return findings


def validate_root_contract(payload: dict[str, Any]) -> list[PrivateRecoveryRehearsalFinding]:
    """Return findings for root-level private recovery rehearsal witness drift."""

    findings: list[PrivateRecoveryRehearsalFinding] = []
    if set(payload) != EXPECTED_ROOT_KEYS:
        findings.append(
            PrivateRecoveryRehearsalFinding(
                "private_recovery_rehearsal_root_keys_invalid",
                f"root keys must be: {', '.join(sorted(EXPECTED_ROOT_KEYS))}",
            )
        )
    expected_values = {
        "witness_id": EXPECTED_WITNESS_ID,
        "schema_version": 1,
        "status": "AwaitingEvidence",
        "solver_outcome": "AwaitingEvidence",
        "recovery_rehearsal_executed": False,
        "private_recovery_material_recording_allowed": False,
        "credential_use_allowed": False,
        "secret_use_allowed": False,
        "backup_execution_allowed": False,
        "restore_execution_allowed": False,
        "cloud_sync_allowed": False,
        "external_export_allowed": False,
        "deletion_operation_allowed": False,
        "provider_account_access_allowed": False,
        "billing_action_allowed": False,
        "customer_data_handling_allowed": False,
        "personal_data_handling_allowed": False,
        "restore_readiness_claimed": False,
        "deployment_allowed": False,
    }
    for key, expected_value in expected_values.items():
        if payload.get(key) != expected_value:
            findings.append(
                PrivateRecoveryRehearsalFinding(
                    "private_recovery_rehearsal_root_value_invalid",
                    f"{key} must be {expected_value!r}",
                )
            )
    if tuple(payload.get("blocked_claims") or ()) != EXPECTED_BLOCKED_CLAIMS:
        findings.append(
            PrivateRecoveryRehearsalFinding(
                "private_recovery_rehearsal_blocked_claims_invalid",
                f"blocked_claims must be: {', '.join(EXPECTED_BLOCKED_CLAIMS)}",
            )
        )
    next_action = payload.get("next_action")
    if not isinstance(next_action, str) or "draft public-safe recovery rehearsal questions only" not in next_action:
        findings.append(
            PrivateRecoveryRehearsalFinding(
                "private_recovery_rehearsal_next_action_invalid",
                "next_action must preserve public-safe rehearsal planning only",
            )
        )
    return findings


def validate_surfaces(surfaces: object) -> list[PrivateRecoveryRehearsalFinding]:
    """Return findings for private recovery rehearsal surface drift."""

    findings: list[PrivateRecoveryRehearsalFinding] = []
    if not isinstance(surfaces, list) or not all(isinstance(surface, dict) for surface in surfaces):
        return [
            PrivateRecoveryRehearsalFinding(
                "private_recovery_rehearsal_surfaces_invalid",
                "surfaces must be a list of objects",
            )
        ]
    observed_surfaces = tuple(
        (surface.get("surface_id"), surface.get("surface_type"), surface.get("state"))
        for surface in surfaces
    )
    if observed_surfaces != EXPECTED_SURFACES:
        findings.append(
            PrivateRecoveryRehearsalFinding(
                "private_recovery_rehearsal_surface_inventory_invalid",
                "private recovery rehearsal surface inventory does not match the expected set",
            )
        )
    surface_ids = [surface.get("surface_id") for surface in surfaces]
    if len(set(surface_ids)) != len(surface_ids):
        findings.append(
            PrivateRecoveryRehearsalFinding("private_recovery_rehearsal_surface_duplicate", "surface ids must be unique")
        )
    for surface in surfaces:
        surface_id = str(surface.get("surface_id", "<missing>"))
        if set(surface) != EXPECTED_SURFACE_KEYS:
            findings.append(
                PrivateRecoveryRehearsalFinding(
                    "private_recovery_rehearsal_surface_keys_invalid",
                    f"{surface_id} surface keys must be: {', '.join(sorted(EXPECTED_SURFACE_KEYS))}",
                )
            )
        if surface.get("state") != "AwaitingEvidence":
            findings.append(
                PrivateRecoveryRehearsalFinding(
                    "private_recovery_rehearsal_surface_state_invalid",
                    f"{surface_id} state must be AwaitingEvidence",
                )
            )
        if surface.get("evidence_ref") != "manual_preparation_pending":
            findings.append(
                PrivateRecoveryRehearsalFinding(
                    "private_recovery_rehearsal_surface_evidence_invalid",
                    f"{surface_id} evidence_ref must stay manual_preparation_pending",
                )
            )
        if not isinstance(surface.get("public_safe_note"), str) or not surface["public_safe_note"].strip():
            findings.append(
                PrivateRecoveryRehearsalFinding(
                    "private_recovery_rehearsal_surface_note_invalid",
                    f"{surface_id} public_safe_note must be a non-empty string",
                )
            )
    return findings


def validate_forbidden_value_patterns(payload: dict[str, Any]) -> list[PrivateRecoveryRehearsalFinding]:
    """Return findings for private, provider, backup, restore, deletion, billing, or deployment-shaped values."""

    serialized_payload = json.dumps(payload, sort_keys=True)
    findings: list[PrivateRecoveryRehearsalFinding] = []
    for rule_id, pattern in FORBIDDEN_VALUE_PATTERNS:
        if pattern.search(serialized_payload):
            findings.append(
                PrivateRecoveryRehearsalFinding(
                    "private_recovery_rehearsal_forbidden_value_pattern",
                    f"private recovery rehearsal witness contains forbidden value pattern: {rule_id}",
                )
            )
    return findings


def validate_forbidden_promotion_patterns(payload: dict[str, Any]) -> list[PrivateRecoveryRehearsalFinding]:
    """Return findings if the witness drifts into rehearsal or readiness claims."""

    serialized_payload = json.dumps(payload, sort_keys=True)
    findings: list[PrivateRecoveryRehearsalFinding] = []
    for rule_id, pattern in FORBIDDEN_PROMOTION_PATTERNS:
        if pattern.search(serialized_payload):
            findings.append(
                PrivateRecoveryRehearsalFinding(
                    "private_recovery_rehearsal_forbidden_promotion_phrase",
                    f"private recovery rehearsal witness contains forbidden promotion pattern: {rule_id}",
                )
            )
    return findings


def validate_foundation_private_recovery_rehearsal_boundary(
    doc_path: Path = DEFAULT_DOC_PATH,
    packet_path: Path = DEFAULT_PACKET_PATH,
) -> list[PrivateRecoveryRehearsalFinding]:
    """Validate the Foundation Mode private recovery rehearsal boundary artifacts."""

    doc_text = load_text(doc_path, "private recovery rehearsal boundary doc")
    packet_payload = load_json_object(packet_path, "private recovery rehearsal witness packet")
    return [
        *validate_doc_text(doc_text),
        *validate_packet(packet_payload),
    ]


def main(argv: list[str] | None = None) -> int:
    """Validate private recovery rehearsal boundary artifacts and print deterministic status."""

    parser = argparse.ArgumentParser(description="Validate Foundation Mode private recovery rehearsal boundary artifacts.")
    parser.add_argument("--doc", type=Path, default=DEFAULT_DOC_PATH)
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET_PATH)
    args = parser.parse_args(argv)

    try:
        findings = validate_foundation_private_recovery_rehearsal_boundary(args.doc, args.packet)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"[FAIL] foundation_private_recovery_rehearsal_load: {exc}", file=sys.stderr)
        print("STATUS: failed", file=sys.stderr)
        return 1

    if findings:
        for finding in findings:
            print(f"[FAIL] {finding.rule_id}: {finding.message}", file=sys.stderr)
        print("STATUS: failed", file=sys.stderr)
        return 1
    print("[PASS] foundation_private_recovery_rehearsal_doc")
    print("[PASS] foundation_private_recovery_rehearsal_witness")
    print("STATUS: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
