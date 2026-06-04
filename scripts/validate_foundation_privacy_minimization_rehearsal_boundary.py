#!/usr/bin/env python3
"""Validate the Foundation Mode privacy minimization rehearsal boundary.

Purpose: keep privacy minimization rehearsal local and public-safe while
personal-data collection, storage, consent capture, retention/deletion
approval, privacy notice publication, tracking, processor activation, legal
clearance, customer access, and deployment remain blocked.
Governance scope: Foundation Mode, privacy minimization rehearsal planning,
local data-category questions, prohibited-field questions, consent exclusion,
retention/deletion draft exclusion, analytics exclusion, processor exclusion,
legal-clearance blocking, customer-access blocking, and deployment blocking.
Dependencies: docs/FOUNDATION_PRIVACY_MINIMIZATION_REHEARSAL_BOUNDARY.md and
examples/foundation_privacy_minimization_rehearsal_witness.awaiting_evidence.json.
Invariants:
  - Validation is read-only.
  - The witness records privacy minimization rehearsal planning only.
  - No minimization approval, personal-data, consent capture, retention,
    deletion, privacy publication, tracking, processor, legal-clearance,
    customer-access, or deployment claim is allowed.
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
DEFAULT_DOC_PATH = REPO_ROOT / "docs" / "FOUNDATION_PRIVACY_MINIMIZATION_REHEARSAL_BOUNDARY.md"
DEFAULT_PACKET_PATH = REPO_ROOT / "examples" / "foundation_privacy_minimization_rehearsal_witness.awaiting_evidence.json"

EXPECTED_WITNESS_ID = "foundation_privacy_minimization_rehearsal_witness.awaiting_evidence.v1"
EXPECTED_BLOCKED_CLAIMS = (
    "minimization approval",
    "personal-data collection",
    "personal-data storage",
    "consent capture",
    "retention/deletion approval",
    "privacy notice publication",
    "analytics tracking",
    "processor activation",
    "legal clearance",
    "customer access",
    "deployment readiness",
)
EXPECTED_SURFACES = (
    ("fictional_data_categories", "local_draft", "AwaitingEvidence"),
    ("prohibited_field_list", "local_draft", "AwaitingEvidence"),
    ("minimization_rule_questions", "local_draft", "AwaitingEvidence"),
    ("consent_stop_rule", "local_draft", "AwaitingEvidence"),
    ("retention_deletion_stop_rule", "local_draft", "AwaitingEvidence"),
    ("tracking_stop_rule", "local_draft", "AwaitingEvidence"),
    ("processor_stop_rule", "local_draft", "AwaitingEvidence"),
    ("subject_request_stop_rule", "local_draft", "AwaitingEvidence"),
    ("handoff_note", "local_draft", "AwaitingEvidence"),
)
EXPECTED_ROOT_KEYS = {
    "analytics_tracking_allowed",
    "blocked_claims",
    "consent_capture_allowed",
    "customer_access_allowed",
    "deployment_allowed",
    "legal_clearance_claimed",
    "minimization_policy_approved",
    "minimization_rehearsal_executed",
    "next_action",
    "personal_data_collection_allowed",
    "personal_data_storage_allowed",
    "privacy_notice_publication_allowed",
    "processor_activation_allowed",
    "retention_deletion_policy_approved",
    "schema_version",
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
    "Foundation Privacy Minimization Rehearsal Boundary",
    "Witness packet: [`../examples/foundation_privacy_minimization_rehearsal_witness.awaiting_evidence.json`]",
    "Rule: Privacy minimization rehearsal is a local paper exercise, not permission",
    "No minimization approval, personal-data collection, personal-data storage,",
    "privacy_minimization_rehearsal_boundary_state=AwaitingEvidence",
    "minimization_rehearsal_executed=false",
    "minimization_policy_approved=false",
    "personal_data_collection_allowed=false",
    "personal_data_storage_allowed=false",
    "processor_activation_allowed=false",
    "deployment_allowed=false",
    "python scripts/validate_foundation_privacy_minimization_rehearsal_boundary.py",
)
FORBIDDEN_VALUE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("url_value", re.compile(r"https?://", re.IGNORECASE)),
    ("email_value", re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)),
    ("private_path", re.compile(r"\b[A-Za-z]:[\\/]|\\\\", re.IGNORECASE)),
    (
        "personal_data_assignment",
        re.compile(r"\b(?:name|phone|address|ssn|dob|birthdate|customer|user|person|contact)[_ -]?(?:value|record|id|data|email)?\s*=", re.IGNORECASE),
    ),
    (
        "account_assignment",
        re.compile(r"\b(?:account|tenant|profile|identity)[_ -]?(?:id|ref|target|value)?\s*=", re.IGNORECASE),
    ),
    (
        "tracking_assignment",
        re.compile(r"\b(?:cookie|pixel|tag|tracking|analytics|telemetry)[_ -]?(?:id|target|value|status)?\s*=", re.IGNORECASE),
    ),
    (
        "processor_assignment",
        re.compile(r"\b(?:processor|vendor|crm|subprocessor)[_ -]?(?:account|id|target|value|status)?\s*=", re.IGNORECASE),
    ),
    (
        "consent_retention_assignment",
        re.compile(r"\b(?:consent|retention|deletion|subject[_ -]?request)[_ -]?(?:id|ref|target|value|status|workflow)?\s*=", re.IGNORECASE),
    ),
    (
        "customer_access_assignment",
        re.compile(r"\b(?:customer[_ -]?access|access[_ -]?channel)[_ -]?(?:id|ref|target|value|status)?\s*=", re.IGNORECASE),
    ),
    (
        "deployment_assignment",
        re.compile(r"\b(?:deploy|deployment|production|staging)[_ -]?(?:target|url|ref|value|status)?\s*=", re.IGNORECASE),
    ),
)
FORBIDDEN_PROMOTION_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("privacy_ready", re.compile(r"\bprivacy[- ]ready\b", re.IGNORECASE)),
    ("minimization_approved", re.compile(r"\bminimization\s+(?:policy\s+)?approved\b", re.IGNORECASE)),
    ("collecting_personal_data", re.compile(r"\bcollecting\s+personal\s+data\b", re.IGNORECASE)),
    ("storing_personal_data", re.compile(r"\bstoring\s+personal\s+data\b", re.IGNORECASE)),
    ("consent_ready", re.compile(r"\bconsent\s+(?:capture\s+)?(?:is\s+)?ready\b", re.IGNORECASE)),
    ("retention_ready", re.compile(r"\bretention\s+(?:is\s+)?ready\b", re.IGNORECASE)),
    ("deletion_ready", re.compile(r"\bdeletion\s+(?:is\s+)?ready\b", re.IGNORECASE)),
    ("processor_ready", re.compile(r"\bprocessor\s+(?:is\s+)?ready\b", re.IGNORECASE)),
    ("tracking_ready", re.compile(r"\btracking\s+(?:is\s+)?ready\b", re.IGNORECASE)),
    ("customer_access_open", re.compile(r"\bcustomer\s+access\s+(?:is\s+)?open\b", re.IGNORECASE)),
    ("deployment_ready", re.compile(r"\bdeployment\s+(?:is\s+)?ready\b", re.IGNORECASE)),
)


@dataclass(frozen=True, slots=True)
class PrivacyMinimizationRehearsalFinding:
    """One deterministic privacy minimization rehearsal validation finding."""

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


def validate_doc_text(text: str) -> list[PrivacyMinimizationRehearsalFinding]:
    """Return findings for missing privacy minimization documentation anchors."""

    findings: list[PrivacyMinimizationRehearsalFinding] = []
    for phrase in REQUIRED_DOC_PHRASES:
        if phrase not in text:
            findings.append(
                PrivacyMinimizationRehearsalFinding(
                    "foundation_privacy_minimization_rehearsal_doc_phrase_missing",
                    f"privacy minimization rehearsal boundary doc missing required phrase: {phrase}",
                )
            )
    return findings


def validate_packet(payload: dict[str, Any]) -> list[PrivacyMinimizationRehearsalFinding]:
    """Return findings for privacy minimization rehearsal witness drift."""

    findings: list[PrivacyMinimizationRehearsalFinding] = []
    findings.extend(validate_root_contract(payload))
    findings.extend(validate_surfaces(payload.get("surfaces")))
    findings.extend(validate_forbidden_value_patterns(payload))
    findings.extend(validate_forbidden_promotion_patterns(payload))
    return findings


def validate_root_contract(payload: dict[str, Any]) -> list[PrivacyMinimizationRehearsalFinding]:
    """Return findings for root-level privacy minimization witness drift."""

    findings: list[PrivacyMinimizationRehearsalFinding] = []
    if set(payload) != EXPECTED_ROOT_KEYS:
        findings.append(
            PrivacyMinimizationRehearsalFinding(
                "privacy_minimization_rehearsal_root_keys_invalid",
                f"root keys must be: {', '.join(sorted(EXPECTED_ROOT_KEYS))}",
            )
        )
    expected_values = {
        "witness_id": EXPECTED_WITNESS_ID,
        "schema_version": 1,
        "status": "AwaitingEvidence",
        "solver_outcome": "AwaitingEvidence",
        "minimization_rehearsal_executed": False,
        "minimization_policy_approved": False,
        "personal_data_collection_allowed": False,
        "personal_data_storage_allowed": False,
        "consent_capture_allowed": False,
        "retention_deletion_policy_approved": False,
        "privacy_notice_publication_allowed": False,
        "analytics_tracking_allowed": False,
        "processor_activation_allowed": False,
        "legal_clearance_claimed": False,
        "customer_access_allowed": False,
        "deployment_allowed": False,
    }
    for key, expected_value in expected_values.items():
        if payload.get(key) != expected_value:
            findings.append(
                PrivacyMinimizationRehearsalFinding(
                    "privacy_minimization_rehearsal_root_value_invalid",
                    f"{key} must be {expected_value!r}",
                )
            )
    if tuple(payload.get("blocked_claims") or ()) != EXPECTED_BLOCKED_CLAIMS:
        findings.append(
            PrivacyMinimizationRehearsalFinding(
                "privacy_minimization_rehearsal_blocked_claims_invalid",
                f"blocked_claims must be: {', '.join(EXPECTED_BLOCKED_CLAIMS)}",
            )
        )
    next_action = payload.get("next_action")
    if not isinstance(next_action, str) or "draft fictional local privacy minimization questions only" not in next_action:
        findings.append(
            PrivacyMinimizationRehearsalFinding(
                "privacy_minimization_rehearsal_next_action_invalid",
                "next_action must preserve fictional local privacy minimization planning only",
            )
        )
    return findings


def validate_surfaces(surfaces: object) -> list[PrivacyMinimizationRehearsalFinding]:
    """Return findings for privacy minimization rehearsal surface drift."""

    findings: list[PrivacyMinimizationRehearsalFinding] = []
    if not isinstance(surfaces, list) or not all(isinstance(surface, dict) for surface in surfaces):
        return [PrivacyMinimizationRehearsalFinding("privacy_minimization_rehearsal_surfaces_invalid", "surfaces must be a list")]
    observed_surfaces = tuple(
        (surface.get("surface_id"), surface.get("surface_type"), surface.get("state"))
        for surface in surfaces
    )
    if observed_surfaces != EXPECTED_SURFACES:
        findings.append(
            PrivacyMinimizationRehearsalFinding(
                "privacy_minimization_rehearsal_surface_inventory_invalid",
                "privacy minimization rehearsal surface inventory does not match the expected set",
            )
        )
    surface_ids = [surface.get("surface_id") for surface in surfaces]
    if len(set(surface_ids)) != len(surface_ids):
        findings.append(PrivacyMinimizationRehearsalFinding("privacy_minimization_rehearsal_surface_duplicate", "surface ids must be unique"))
    for surface in surfaces:
        surface_id = str(surface.get("surface_id", "<missing>"))
        if set(surface) != EXPECTED_SURFACE_KEYS:
            findings.append(
                PrivacyMinimizationRehearsalFinding(
                    "privacy_minimization_rehearsal_surface_keys_invalid",
                    f"{surface_id} surface keys must be: {', '.join(sorted(EXPECTED_SURFACE_KEYS))}",
                )
            )
        if surface.get("state") != "AwaitingEvidence":
            findings.append(
                PrivacyMinimizationRehearsalFinding(
                    "privacy_minimization_rehearsal_surface_state_invalid",
                    f"{surface_id} state must be AwaitingEvidence",
                )
            )
        if surface.get("evidence_ref") != "manual_preparation_pending":
            findings.append(
                PrivacyMinimizationRehearsalFinding(
                    "privacy_minimization_rehearsal_surface_evidence_invalid",
                    f"{surface_id} evidence_ref must stay manual_preparation_pending",
                )
            )
        if not isinstance(surface.get("public_safe_note"), str) or not surface["public_safe_note"].strip():
            findings.append(
                PrivacyMinimizationRehearsalFinding(
                    "privacy_minimization_rehearsal_surface_note_invalid",
                    f"{surface_id} public_safe_note must be a non-empty string",
                )
            )
    return findings


def validate_forbidden_value_patterns(payload: dict[str, Any]) -> list[PrivacyMinimizationRehearsalFinding]:
    """Return findings for personal-data, account, tracking, processor, consent, access, or deployment-shaped values."""

    serialized_payload = json.dumps(payload, sort_keys=True)
    findings: list[PrivacyMinimizationRehearsalFinding] = []
    for rule_id, pattern in FORBIDDEN_VALUE_PATTERNS:
        if pattern.search(serialized_payload):
            findings.append(
                PrivacyMinimizationRehearsalFinding(
                    "privacy_minimization_rehearsal_forbidden_value_pattern",
                    f"privacy minimization rehearsal witness contains forbidden value pattern: {rule_id}",
                )
            )
    return findings


def validate_forbidden_promotion_patterns(payload: dict[str, Any]) -> list[PrivacyMinimizationRehearsalFinding]:
    """Return findings if the witness drifts into privacy/data readiness claims."""

    serialized_payload = json.dumps(payload, sort_keys=True)
    findings: list[PrivacyMinimizationRehearsalFinding] = []
    for rule_id, pattern in FORBIDDEN_PROMOTION_PATTERNS:
        if pattern.search(serialized_payload):
            findings.append(
                PrivacyMinimizationRehearsalFinding(
                    "privacy_minimization_rehearsal_forbidden_promotion_phrase",
                    f"privacy minimization rehearsal witness contains forbidden promotion pattern: {rule_id}",
                )
            )
    return findings


def validate_foundation_privacy_minimization_rehearsal_boundary(
    doc_path: Path = DEFAULT_DOC_PATH,
    packet_path: Path = DEFAULT_PACKET_PATH,
) -> list[PrivacyMinimizationRehearsalFinding]:
    """Validate the Foundation Mode privacy minimization rehearsal boundary artifacts."""

    doc_text = load_text(doc_path, "privacy minimization rehearsal boundary doc")
    packet_payload = load_json_object(packet_path, "privacy minimization rehearsal witness packet")
    return [
        *validate_doc_text(doc_text),
        *validate_packet(packet_payload),
    ]


def main(argv: list[str] | None = None) -> int:
    """Validate privacy minimization rehearsal artifacts and print deterministic status."""

    parser = argparse.ArgumentParser(description="Validate Foundation Mode privacy minimization rehearsal boundary artifacts.")
    parser.add_argument("--doc", type=Path, default=DEFAULT_DOC_PATH)
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET_PATH)
    args = parser.parse_args(argv)

    try:
        findings = validate_foundation_privacy_minimization_rehearsal_boundary(args.doc, args.packet)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"[FAIL] foundation_privacy_minimization_rehearsal_load: {exc}", file=sys.stderr)
        print("STATUS: failed", file=sys.stderr)
        return 1

    if findings:
        for finding in findings:
            print(f"[FAIL] {finding.rule_id}: {finding.message}", file=sys.stderr)
        print("STATUS: failed", file=sys.stderr)
        return 1
    print("[PASS] foundation_privacy_minimization_rehearsal_doc")
    print("[PASS] foundation_privacy_minimization_rehearsal_witness")
    print("STATUS: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
