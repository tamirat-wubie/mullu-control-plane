#!/usr/bin/env python3
"""Validate the Foundation Mode privacy/data boundary.

Purpose: keep privacy and data-retention preparation local while personal-data
collection, storage, consent capture, tracking, processor activation, policy
publication, customer access, and deployment claims remain blocked.
Governance scope: Foundation Mode, privacy posture, data-retention posture,
public-safe planning witness, private-value exclusion, and deployment blocking.
Dependencies: docs/FOUNDATION_PRIVACY_DATA_BOUNDARY.md and
examples/foundation_privacy_data_witness.awaiting_evidence.json.
Invariants:
  - Validation is read-only.
  - The witness records local privacy/data planning only.
  - No personal-data collection, storage, consent capture, tracking, processor
    activation, policy publication, private value, customer access, or
    deployment claim is allowed.
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
DEFAULT_DOC_PATH = REPO_ROOT / "docs" / "FOUNDATION_PRIVACY_DATA_BOUNDARY.md"
DEFAULT_PACKET_PATH = REPO_ROOT / "examples" / "foundation_privacy_data_witness.awaiting_evidence.json"

EXPECTED_WITNESS_ID = "foundation_privacy_data_witness.awaiting_evidence.v1"
EXPECTED_BLOCKED_CLAIMS = (
    "personal-data collection",
    "personal-data storage",
    "retention policy approval",
    "deletion policy approval",
    "consent capture",
    "analytics tracking",
    "third-party processor activation",
    "privacy notice publication",
    "legal clearance",
    "customer access",
    "deployment readiness",
)
EXPECTED_SURFACES = (
    ("data_classification_draft", "local_draft", "AwaitingEvidence"),
    ("consent_questions", "local_draft", "AwaitingEvidence"),
    ("retention_deletion_questions", "local_draft", "AwaitingEvidence"),
    ("privacy_notice_questions", "local_draft", "AwaitingEvidence"),
    ("processor_inventory_draft", "local_draft", "AwaitingEvidence"),
    ("analytics_tracking_questions", "local_draft", "AwaitingEvidence"),
    ("subject_request_questions", "local_draft", "AwaitingEvidence"),
    ("data_minimization_checklist", "local_draft", "AwaitingEvidence"),
)
EXPECTED_ROOT_KEYS = {
    "analytics_tracking_allowed",
    "blocked_claims",
    "consent_capture_allowed",
    "customer_access_allowed",
    "deletion_policy_approved",
    "deployment_allowed",
    "legal_clearance_claimed",
    "next_action",
    "personal_data_collection_allowed",
    "personal_data_storage_allowed",
    "privacy_notice_published",
    "privacy_surfaces",
    "retention_policy_approved",
    "schema_version",
    "solver_outcome",
    "status",
    "third_party_processor_allowed",
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
    "Foundation Privacy Data Boundary",
    "Witness packet: [`../examples/foundation_privacy_data_witness.awaiting_evidence.json`]",
    "Rule: Privacy/data preparation is a local planning boundary, not permission to handle personal data.",
    "No personal-data collection, personal-data storage, retention-policy approval,",
    "privacy_data_boundary_state=AwaitingEvidence",
    "personal_data_collection_allowed=false",
    "personal_data_storage_allowed=false",
    "retention_policy_approved=false",
    "privacy_notice_published=false",
    "python scripts/validate_foundation_privacy_data_boundary.py",
)
FORBIDDEN_VALUE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("url_value", re.compile(r"https?://", re.IGNORECASE)),
    ("email_value", re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)),
    ("private_path", re.compile(r"\b[A-Za-z]:[\\/]|\\\\", re.IGNORECASE)),
    ("personal_data_assignment", re.compile(r"\b(?:name|phone|address|ssn|dob|birthdate|customer|user)[_ -]?(?:value|record|id)?\s*=", re.IGNORECASE)),
    ("processor_account_assignment", re.compile(r"\b(?:processor|vendor|analytics|crm)[_ -]?(?:account|id|target)\s*=", re.IGNORECASE)),
    ("tracking_assignment", re.compile(r"\b(?:cookie|pixel|tag|tracking)[_ -]?(?:id|target|value)?\s*=", re.IGNORECASE)),
    ("secret_assignment", re.compile(r"\b(?:password|secret|token|api[_ -]?key)\s*=", re.IGNORECASE)),
    ("private_key_material", re.compile(r"BEGIN [A-Z ]*PRIVATE KEY")),
)
FORBIDDEN_PROMOTION_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("privacy_ready", re.compile(r"\bprivacy[- ]ready\b", re.IGNORECASE)),
    ("retention_approved", re.compile(r"\bretention\s+(?:policy\s+)?approved\b", re.IGNORECASE)),
    ("deletion_approved", re.compile(r"\bdeletion\s+(?:policy\s+)?approved\b", re.IGNORECASE)),
    ("collecting_personal_data", re.compile(r"\bcollecting\s+personal\s+data\b", re.IGNORECASE)),
    ("storing_personal_data", re.compile(r"\bstoring\s+personal\s+data\b", re.IGNORECASE)),
    ("consent_capture_live", re.compile(r"\bconsent\s+capture\s+(?:is\s+)?(?:live|enabled|active)\b", re.IGNORECASE)),
    ("privacy_notice_published", re.compile(r"\bprivacy\s+notice\s+published\b", re.IGNORECASE)),
    ("processor_active", re.compile(r"\bprocessor\s+(?:is\s+)?(?:active|enabled|approved)\b", re.IGNORECASE)),
    ("tracking_enabled", re.compile(r"\btracking\s+(?:is\s+)?enabled\b", re.IGNORECASE)),
)


@dataclass(frozen=True, slots=True)
class PrivacyDataFinding:
    """One deterministic privacy/data boundary validation finding."""

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
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{label} must be a JSON object")
    return payload


def validate_doc_text(text: str) -> list[PrivacyDataFinding]:
    """Return findings for missing privacy/data documentation anchors."""

    findings: list[PrivacyDataFinding] = []
    for phrase in REQUIRED_DOC_PHRASES:
        if phrase not in text:
            findings.append(
                PrivacyDataFinding(
                    "foundation_privacy_data_doc_phrase_missing",
                    f"privacy/data boundary doc missing required phrase: {phrase}",
                )
            )
    return findings


def validate_packet(payload: dict[str, Any]) -> list[PrivacyDataFinding]:
    """Return findings for privacy/data witness drift."""

    findings: list[PrivacyDataFinding] = []
    findings.extend(validate_root_contract(payload))
    findings.extend(validate_privacy_surfaces(payload.get("privacy_surfaces")))
    findings.extend(validate_forbidden_value_patterns(payload))
    findings.extend(validate_forbidden_promotion_patterns(payload))
    return findings


def validate_root_contract(payload: dict[str, Any]) -> list[PrivacyDataFinding]:
    """Return findings for root-level privacy/data witness drift."""

    findings: list[PrivacyDataFinding] = []
    if set(payload) != EXPECTED_ROOT_KEYS:
        findings.append(
            PrivacyDataFinding(
                "privacy_data_root_keys_invalid",
                f"root keys must be: {', '.join(sorted(EXPECTED_ROOT_KEYS))}",
            )
        )
    expected_values = {
        "witness_id": EXPECTED_WITNESS_ID,
        "schema_version": 1,
        "status": "AwaitingEvidence",
        "solver_outcome": "AwaitingEvidence",
        "personal_data_collection_allowed": False,
        "personal_data_storage_allowed": False,
        "retention_policy_approved": False,
        "deletion_policy_approved": False,
        "privacy_notice_published": False,
        "consent_capture_allowed": False,
        "analytics_tracking_allowed": False,
        "third_party_processor_allowed": False,
        "legal_clearance_claimed": False,
        "customer_access_allowed": False,
        "deployment_allowed": False,
    }
    for key, expected_value in expected_values.items():
        if payload.get(key) != expected_value:
            findings.append(
                PrivacyDataFinding(
                    "privacy_data_root_value_invalid",
                    f"{key} must be {expected_value!r}",
                )
            )
    if tuple(payload.get("blocked_claims") or ()) != EXPECTED_BLOCKED_CLAIMS:
        findings.append(
            PrivacyDataFinding(
                "privacy_data_blocked_claims_invalid",
                f"blocked_claims must be: {', '.join(EXPECTED_BLOCKED_CLAIMS)}",
            )
        )
    next_action = payload.get("next_action")
    if not isinstance(next_action, str) or "do not collect" not in next_action:
        findings.append(
            PrivacyDataFinding(
                "privacy_data_next_action_invalid",
                "next_action must preserve the closed personal-data boundary",
            )
        )
    return findings


def validate_privacy_surfaces(privacy_surfaces: object) -> list[PrivacyDataFinding]:
    """Return findings for privacy/data surface witness drift."""

    findings: list[PrivacyDataFinding] = []
    if not isinstance(privacy_surfaces, list) or not all(isinstance(surface, dict) for surface in privacy_surfaces):
        return [PrivacyDataFinding("privacy_data_surfaces_invalid", "privacy_surfaces must be a list of objects")]
    observed_surfaces = tuple(
        (surface.get("surface_id"), surface.get("surface_type"), surface.get("state"))
        for surface in privacy_surfaces
    )
    if observed_surfaces != EXPECTED_SURFACES:
        findings.append(
            PrivacyDataFinding(
                "privacy_data_surface_inventory_invalid",
                "privacy/data surface inventory does not match the Foundation Mode privacy set",
            )
        )
    surface_ids = [surface.get("surface_id") for surface in privacy_surfaces]
    if len(set(surface_ids)) != len(surface_ids):
        findings.append(PrivacyDataFinding("privacy_data_surface_duplicate", "surface ids must be unique"))
    for surface in privacy_surfaces:
        surface_id = str(surface.get("surface_id", "<missing>"))
        if set(surface) != EXPECTED_SURFACE_KEYS:
            findings.append(
                PrivacyDataFinding(
                    "privacy_data_surface_keys_invalid",
                    f"{surface_id} surface keys must be: {', '.join(sorted(EXPECTED_SURFACE_KEYS))}",
                )
            )
        if surface.get("state") != "AwaitingEvidence":
            findings.append(
                PrivacyDataFinding(
                    "privacy_data_surface_state_invalid",
                    f"{surface_id} state must be AwaitingEvidence",
                )
            )
        if surface.get("evidence_ref") != "manual_preparation_pending":
            findings.append(
                PrivacyDataFinding(
                    "privacy_data_surface_evidence_invalid",
                    f"{surface_id} evidence_ref must stay manual_preparation_pending in the committed packet",
                )
            )
        if not isinstance(surface.get("public_safe_note"), str) or not surface["public_safe_note"].strip():
            findings.append(
                PrivacyDataFinding(
                    "privacy_data_surface_note_invalid",
                    f"{surface_id} public_safe_note must be a non-empty string",
                )
            )
    return findings


def validate_forbidden_value_patterns(payload: dict[str, Any]) -> list[PrivacyDataFinding]:
    """Return findings for personal-data, URL, email, account, tracking, or secret-shaped values."""

    serialized_payload = json.dumps(payload, sort_keys=True)
    findings: list[PrivacyDataFinding] = []
    for rule_id, pattern in FORBIDDEN_VALUE_PATTERNS:
        if pattern.search(serialized_payload):
            findings.append(
                PrivacyDataFinding(
                    "privacy_data_forbidden_private_value_pattern",
                    f"privacy/data witness contains forbidden value pattern: {rule_id}",
                )
            )
    return findings


def validate_forbidden_promotion_patterns(payload: dict[str, Any]) -> list[PrivacyDataFinding]:
    """Return findings if the witness drifts into privacy/data readiness claims."""

    serialized_payload = json.dumps(payload, sort_keys=True)
    findings: list[PrivacyDataFinding] = []
    for rule_id, pattern in FORBIDDEN_PROMOTION_PATTERNS:
        if pattern.search(serialized_payload):
            findings.append(
                PrivacyDataFinding(
                    "privacy_data_forbidden_promotion_phrase",
                    f"privacy/data witness contains forbidden promotion pattern: {rule_id}",
                )
            )
    return findings


def validate_foundation_privacy_data_boundary(
    doc_path: Path = DEFAULT_DOC_PATH,
    packet_path: Path = DEFAULT_PACKET_PATH,
) -> list[PrivacyDataFinding]:
    """Validate the Foundation Mode privacy/data boundary artifacts."""

    doc_text = load_text(doc_path, "privacy/data boundary doc")
    packet_payload = load_json_object(packet_path, "privacy/data witness packet")
    return [
        *validate_doc_text(doc_text),
        *validate_packet(packet_payload),
    ]


def main(argv: list[str] | None = None) -> int:
    """Validate privacy/data boundary artifacts and print deterministic status."""

    parser = argparse.ArgumentParser(description="Validate Foundation Mode privacy/data boundary artifacts.")
    parser.add_argument("--doc", type=Path, default=DEFAULT_DOC_PATH)
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET_PATH)
    args = parser.parse_args(argv)

    try:
        findings = validate_foundation_privacy_data_boundary(args.doc, args.packet)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"[FAIL] foundation_privacy_data_load: {exc}", file=sys.stderr)
        print("STATUS: failed", file=sys.stderr)
        return 1

    if findings:
        for finding in findings:
            print(f"[FAIL] {finding.rule_id}: {finding.message}", file=sys.stderr)
        print("STATUS: failed", file=sys.stderr)
        return 1
    print("[PASS] foundation_privacy_data_doc")
    print("[PASS] foundation_privacy_data_witness")
    print("STATUS: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
