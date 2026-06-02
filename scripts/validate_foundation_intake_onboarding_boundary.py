#!/usr/bin/env python3
"""Validate the Foundation Mode intake/onboarding boundary.

Purpose: keep intake and onboarding preparation local while active forms,
waitlists, pilot signups, personal data collection, CRM import, outreach,
customer access, paid access, and deployment claims remain blocked.
Governance scope: Foundation Mode, intake posture, onboarding posture,
public-safe planning witness, private-value exclusion, and deployment blocking.
Dependencies: docs/FOUNDATION_INTAKE_ONBOARDING_BOUNDARY.md and
examples/foundation_intake_onboarding_witness.awaiting_evidence.json.
Invariants:
  - Validation is read-only.
  - The witness records local intake planning only.
  - No active form, waitlist, pilot signup, personal data collection, CRM import,
    outreach, onboarding, paid access, customer access, private value, or
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
DEFAULT_DOC_PATH = REPO_ROOT / "docs" / "FOUNDATION_INTAKE_ONBOARDING_BOUNDARY.md"
DEFAULT_PACKET_PATH = REPO_ROOT / "examples" / "foundation_intake_onboarding_witness.awaiting_evidence.json"

EXPECTED_WITNESS_ID = "foundation_intake_onboarding_witness.awaiting_evidence.v1"
EXPECTED_BLOCKED_CLAIMS = (
    "active intake",
    "waitlist activation",
    "pilot signup",
    "customer onboarding",
    "personal data collection",
    "CRM import",
    "outreach campaign",
    "paid access",
    "deployment readiness",
)
EXPECTED_SURFACES = (
    ("future_interest_form_shape", "local_draft", "AwaitingEvidence"),
    ("eligibility_questions", "local_draft", "AwaitingEvidence"),
    ("consent_language_draft", "local_draft", "AwaitingEvidence"),
    ("onboarding_steps_draft", "local_draft", "AwaitingEvidence"),
    ("data_retention_questions", "local_draft", "AwaitingEvidence"),
    ("decline_reply_template", "local_draft", "AwaitingEvidence"),
)
EXPECTED_ROOT_KEYS = {
    "blocked_claims",
    "crm_import_allowed",
    "customer_access_allowed",
    "customer_onboarding_allowed",
    "deployment_allowed",
    "intake_open",
    "intake_surfaces",
    "next_action",
    "outreach_campaign_allowed",
    "paid_access_allowed",
    "pii_collection_allowed",
    "pilot_signup_open",
    "schema_version",
    "solver_outcome",
    "status",
    "waitlist_open",
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
    "Foundation Intake Onboarding Boundary",
    "Witness packet: [`../examples/foundation_intake_onboarding_witness.awaiting_evidence.json`]",
    "Rule: Intake preparation is a local planning boundary, not an active intake channel.",
    "No active intake form, waitlist opening, pilot signup, customer onboarding, PII",
    "intake_onboarding_boundary_state=AwaitingEvidence",
    "intake_open=false",
    "waitlist_open=false",
    "pilot_signup_open=false",
    "pii_collection_allowed=false",
    "python scripts/validate_foundation_intake_onboarding_boundary.py",
)
FORBIDDEN_VALUE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("url_value", re.compile(r"https?://", re.IGNORECASE)),
    ("email_value", re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)),
    ("private_path", re.compile(r"\b[A-Za-z]:[\\/]|\\\\", re.IGNORECASE)),
    ("crm_assignment", re.compile(r"\b(?:crm|hubspot|salesforce|airtable)[_ -]?(?:id|list|target)\s*=", re.IGNORECASE)),
    ("form_link_assignment", re.compile(r"\b(?:form|survey|signup|waitlist)[_ -]?(?:url|link|id)\s*=", re.IGNORECASE)),
    ("secret_assignment", re.compile(r"\b(?:password|secret|token|api[_ -]?key)\s*=", re.IGNORECASE)),
    ("private_key_material", re.compile(r"BEGIN [A-Z ]*PRIVATE KEY")),
)
FORBIDDEN_PROMOTION_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("intake_open", re.compile(r"\bintake\s+(?:is\s+)?open\b", re.IGNORECASE)),
    ("waitlist_open", re.compile(r"\bwaitlist\s+(?:is\s+)?open\b", re.IGNORECASE)),
    ("pilot_signup_live", re.compile(r"\bpilot\s+signup\s+(?:is\s+)?(?:live|open)\b", re.IGNORECASE)),
    ("onboarding_ready", re.compile(r"\bonboarding[- ]ready\b", re.IGNORECASE)),
    ("collecting_pii", re.compile(r"\bcollecting\s+(?:pii|personal data)\b", re.IGNORECASE)),
    ("accepting_users", re.compile(r"\baccepting\s+(?:users|customers)\b", re.IGNORECASE)),
    ("form_live", re.compile(r"\bform\s+(?:is\s+)?live\b", re.IGNORECASE)),
    ("crm_connected", re.compile(r"\bcrm\s+(?:is\s+)?connected\b", re.IGNORECASE)),
)


@dataclass(frozen=True, slots=True)
class IntakeOnboardingFinding:
    """One deterministic intake/onboarding boundary validation finding."""

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


def validate_doc_text(text: str) -> list[IntakeOnboardingFinding]:
    """Return findings for missing intake/onboarding documentation anchors."""

    findings: list[IntakeOnboardingFinding] = []
    for phrase in REQUIRED_DOC_PHRASES:
        if phrase not in text:
            findings.append(
                IntakeOnboardingFinding(
                    "foundation_intake_onboarding_doc_phrase_missing",
                    f"intake/onboarding boundary doc missing required phrase: {phrase}",
                )
            )
    return findings


def validate_packet(payload: dict[str, Any]) -> list[IntakeOnboardingFinding]:
    """Return findings for intake/onboarding witness drift."""

    findings: list[IntakeOnboardingFinding] = []
    findings.extend(validate_root_contract(payload))
    findings.extend(validate_intake_surfaces(payload.get("intake_surfaces")))
    findings.extend(validate_forbidden_value_patterns(payload))
    findings.extend(validate_forbidden_promotion_patterns(payload))
    return findings


def validate_root_contract(payload: dict[str, Any]) -> list[IntakeOnboardingFinding]:
    """Return findings for root-level intake/onboarding witness drift."""

    findings: list[IntakeOnboardingFinding] = []
    if set(payload) != EXPECTED_ROOT_KEYS:
        findings.append(
            IntakeOnboardingFinding(
                "intake_onboarding_root_keys_invalid",
                f"root keys must be: {', '.join(sorted(EXPECTED_ROOT_KEYS))}",
            )
        )
    expected_values = {
        "witness_id": EXPECTED_WITNESS_ID,
        "schema_version": 1,
        "status": "AwaitingEvidence",
        "solver_outcome": "AwaitingEvidence",
        "intake_open": False,
        "waitlist_open": False,
        "pilot_signup_open": False,
        "customer_onboarding_allowed": False,
        "pii_collection_allowed": False,
        "crm_import_allowed": False,
        "outreach_campaign_allowed": False,
        "paid_access_allowed": False,
        "customer_access_allowed": False,
        "deployment_allowed": False,
    }
    for key, expected_value in expected_values.items():
        if payload.get(key) != expected_value:
            findings.append(
                IntakeOnboardingFinding(
                    "intake_onboarding_root_value_invalid",
                    f"{key} must be {expected_value!r}",
                )
            )
    if tuple(payload.get("blocked_claims") or ()) != EXPECTED_BLOCKED_CLAIMS:
        findings.append(
            IntakeOnboardingFinding(
                "intake_onboarding_blocked_claims_invalid",
                f"blocked_claims must be: {', '.join(EXPECTED_BLOCKED_CLAIMS)}",
            )
        )
    next_action = payload.get("next_action")
    if not isinstance(next_action, str) or "do not publish forms" not in next_action:
        findings.append(
            IntakeOnboardingFinding(
                "intake_onboarding_next_action_invalid",
                "next_action must preserve the closed-intake boundary",
            )
        )
    return findings


def validate_intake_surfaces(intake_surfaces: object) -> list[IntakeOnboardingFinding]:
    """Return findings for intake-surface witness drift."""

    findings: list[IntakeOnboardingFinding] = []
    if not isinstance(intake_surfaces, list) or not all(isinstance(surface, dict) for surface in intake_surfaces):
        return [IntakeOnboardingFinding("intake_onboarding_surfaces_invalid", "intake_surfaces must be a list of objects")]
    observed_surfaces = tuple(
        (surface.get("surface_id"), surface.get("surface_type"), surface.get("state"))
        for surface in intake_surfaces
    )
    if observed_surfaces != EXPECTED_SURFACES:
        findings.append(
            IntakeOnboardingFinding(
                "intake_onboarding_surface_inventory_invalid",
                "intake surface inventory does not match the Foundation Mode intake set",
            )
        )
    surface_ids = [surface.get("surface_id") for surface in intake_surfaces]
    if len(set(surface_ids)) != len(surface_ids):
        findings.append(IntakeOnboardingFinding("intake_onboarding_surface_duplicate", "surface ids must be unique"))
    for surface in intake_surfaces:
        surface_id = str(surface.get("surface_id", "<missing>"))
        if set(surface) != EXPECTED_SURFACE_KEYS:
            findings.append(
                IntakeOnboardingFinding(
                    "intake_onboarding_surface_keys_invalid",
                    f"{surface_id} surface keys must be: {', '.join(sorted(EXPECTED_SURFACE_KEYS))}",
                )
            )
        if surface.get("state") != "AwaitingEvidence":
            findings.append(
                IntakeOnboardingFinding(
                    "intake_onboarding_surface_state_invalid",
                    f"{surface_id} state must be AwaitingEvidence",
                )
            )
        if surface.get("evidence_ref") != "manual_preparation_pending":
            findings.append(
                IntakeOnboardingFinding(
                    "intake_onboarding_surface_evidence_invalid",
                    f"{surface_id} evidence_ref must stay manual_preparation_pending in the committed packet",
                )
            )
        if not isinstance(surface.get("public_safe_note"), str) or not surface["public_safe_note"].strip():
            findings.append(
                IntakeOnboardingFinding(
                    "intake_onboarding_surface_note_invalid",
                    f"{surface_id} public_safe_note must be a non-empty string",
                )
            )
    return findings


def validate_forbidden_value_patterns(payload: dict[str, Any]) -> list[IntakeOnboardingFinding]:
    """Return findings for URL, email, CRM, form, secret, or private path values."""

    serialized_payload = json.dumps(payload, sort_keys=True)
    findings: list[IntakeOnboardingFinding] = []
    for rule_id, pattern in FORBIDDEN_VALUE_PATTERNS:
        if pattern.search(serialized_payload):
            findings.append(
                IntakeOnboardingFinding(
                    "intake_onboarding_forbidden_private_value_pattern",
                    f"intake/onboarding witness contains forbidden value pattern: {rule_id}",
                )
            )
    return findings


def validate_forbidden_promotion_patterns(payload: dict[str, Any]) -> list[IntakeOnboardingFinding]:
    """Return findings if the witness drifts into intake/onboarding activation claims."""

    serialized_payload = json.dumps(payload, sort_keys=True)
    findings: list[IntakeOnboardingFinding] = []
    for rule_id, pattern in FORBIDDEN_PROMOTION_PATTERNS:
        if pattern.search(serialized_payload):
            findings.append(
                IntakeOnboardingFinding(
                    "intake_onboarding_forbidden_promotion_phrase",
                    f"intake/onboarding witness contains forbidden promotion pattern: {rule_id}",
                )
            )
    return findings


def validate_foundation_intake_onboarding_boundary(
    doc_path: Path = DEFAULT_DOC_PATH,
    packet_path: Path = DEFAULT_PACKET_PATH,
) -> list[IntakeOnboardingFinding]:
    """Validate the Foundation Mode intake/onboarding boundary artifacts."""

    doc_text = load_text(doc_path, "intake/onboarding boundary doc")
    packet_payload = load_json_object(packet_path, "intake/onboarding witness packet")
    return [
        *validate_doc_text(doc_text),
        *validate_packet(packet_payload),
    ]


def main(argv: list[str] | None = None) -> int:
    """Validate intake/onboarding boundary artifacts and print deterministic status."""

    parser = argparse.ArgumentParser(description="Validate Foundation Mode intake/onboarding boundary artifacts.")
    parser.add_argument("--doc", type=Path, default=DEFAULT_DOC_PATH)
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET_PATH)
    args = parser.parse_args(argv)

    try:
        findings = validate_foundation_intake_onboarding_boundary(args.doc, args.packet)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"[FAIL] foundation_intake_onboarding_load: {exc}", file=sys.stderr)
        print("STATUS: failed", file=sys.stderr)
        return 1

    if findings:
        for finding in findings:
            print(f"[FAIL] {finding.rule_id}: {finding.message}", file=sys.stderr)
        print("STATUS: failed", file=sys.stderr)
        return 1
    print("[PASS] foundation_intake_onboarding_doc")
    print("[PASS] foundation_intake_onboarding_witness")
    print("STATUS: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
