#!/usr/bin/env python3
"""Validate the Foundation Mode intake questionnaire rehearsal boundary.

Purpose: keep intake questionnaire rehearsal local and public-safe while form
publication, waitlists, pilot signups, personal-data collection, CRM import,
outreach, customer onboarding, customer access, payment collection,
legal/privacy readiness claims, and deployment remain blocked.
Governance scope: Foundation Mode, intake questionnaire rehearsal planning,
fictional local field categories, collection exclusion, CRM exclusion,
outreach exclusion, customer-access blocking, payment blocking, and deployment
blocking.
Dependencies: docs/FOUNDATION_INTAKE_QUESTIONNAIRE_REHEARSAL_BOUNDARY.md and
examples/foundation_intake_questionnaire_rehearsal_witness.awaiting_evidence.json.
Invariants:
  - Validation is read-only.
  - The witness records intake questionnaire rehearsal planning only.
  - No active form, publication, waitlist, signup, personal-data, CRM,
    outreach, onboarding, customer-access, payment, legal/privacy-readiness, or
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
DEFAULT_DOC_PATH = REPO_ROOT / "docs" / "FOUNDATION_INTAKE_QUESTIONNAIRE_REHEARSAL_BOUNDARY.md"
DEFAULT_PACKET_PATH = REPO_ROOT / "examples" / "foundation_intake_questionnaire_rehearsal_witness.awaiting_evidence.json"

EXPECTED_WITNESS_ID = "foundation_intake_questionnaire_rehearsal_witness.awaiting_evidence.v1"
EXPECTED_BLOCKED_CLAIMS = (
    "questionnaire execution",
    "active intake form",
    "form publication",
    "waitlist opening",
    "pilot signup",
    "personal-data collection",
    "CRM import",
    "outreach campaign",
    "customer onboarding",
    "customer access",
    "payment collection",
    "legal/privacy readiness",
    "deployment readiness",
)
EXPECTED_SURFACES = (
    ("fictional_field_categories", "local_draft", "AwaitingEvidence"),
    ("eligibility_prompt_shape", "local_draft", "AwaitingEvidence"),
    ("consent_boundary_questions", "local_draft", "AwaitingEvidence"),
    ("privacy_minimization_questions", "local_draft", "AwaitingEvidence"),
    ("retention_deletion_questions", "local_draft", "AwaitingEvidence"),
    ("disqualification_reply_shape", "local_draft", "AwaitingEvidence"),
    ("operator_review_gate", "local_draft", "AwaitingEvidence"),
    ("handoff_note", "local_draft", "AwaitingEvidence"),
)
EXPECTED_ROOT_KEYS = {
    "active_intake_form_exists",
    "blocked_claims",
    "crm_import_allowed",
    "customer_access_allowed",
    "customer_onboarding_allowed",
    "deployment_allowed",
    "form_publication_allowed",
    "legal_privacy_readiness_claimed",
    "next_action",
    "outreach_campaign_allowed",
    "payment_collection_allowed",
    "personal_data_collection_allowed",
    "pilot_signup_open",
    "questionnaire_rehearsal_executed",
    "schema_version",
    "solver_outcome",
    "status",
    "surfaces",
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
    "Foundation Intake Questionnaire Rehearsal Boundary",
    "Witness packet: [`../examples/foundation_intake_questionnaire_rehearsal_witness.awaiting_evidence.json`]",
    "Rule: Intake questionnaire rehearsal is a local paper exercise, not an intake",
    "No questionnaire execution, active intake form, form publication, waitlist",
    "intake_questionnaire_rehearsal_boundary_state=AwaitingEvidence",
    "questionnaire_rehearsal_executed=false",
    "active_intake_form_exists=false",
    "form_publication_allowed=false",
    "waitlist_open=false",
    "personal_data_collection_allowed=false",
    "deployment_allowed=false",
    "python scripts/validate_foundation_intake_questionnaire_rehearsal_boundary.py",
)
FORBIDDEN_VALUE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("url_value", re.compile(r"https?://", re.IGNORECASE)),
    ("email_value", re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)),
    ("private_path", re.compile(r"\b[A-Za-z]:[\\/]|\\\\", re.IGNORECASE)),
    (
        "form_link_assignment",
        re.compile(r"\b(?:form|survey|signup|waitlist)[_ -]?(?:url|link|id|target|value)\s*=", re.IGNORECASE),
    ),
    (
        "crm_assignment",
        re.compile(r"\b(?:crm|hubspot|salesforce|airtable|contact)[_ -]?(?:id|list|target|value)\s*=", re.IGNORECASE),
    ),
    (
        "personal_data_assignment",
        re.compile(r"\b(?:personal|person|participant|customer|user)[_ -]?(?:data|name|email|id|ref|value)\s*=", re.IGNORECASE),
    ),
    (
        "payment_assignment",
        re.compile(r"\b(?:payment|billing|invoice|charge|checkout)[_ -]?(?:id|ref|target|value|status)\s*=", re.IGNORECASE),
    ),
    (
        "legal_privacy_assignment",
        re.compile(r"\b(?:legal|privacy|consent|terms)[_ -]?(?:id|ref|target|value|status)\s*=", re.IGNORECASE),
    ),
    (
        "onboarding_assignment",
        re.compile(r"\b(?:onboarding|invite|account)[_ -]?(?:id|ref|target|value|status)\s*=", re.IGNORECASE),
    ),
    (
        "deployment_assignment",
        re.compile(r"\b(?:deploy|deployment|production|staging)[_ -]?(?:target|url|ref|value|status)\s*=", re.IGNORECASE),
    ),
)
FORBIDDEN_PROMOTION_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("questionnaire_ready", re.compile(r"\bquestionnaire\s+(?:is\s+)?ready\b", re.IGNORECASE)),
    ("intake_ready", re.compile(r"\bintake[- ]ready\b", re.IGNORECASE)),
    ("intake_open", re.compile(r"\bintake\s+(?:is\s+)?open\b", re.IGNORECASE)),
    ("form_live", re.compile(r"\bform\s+(?:is\s+)?(?:live|published|ready)\b", re.IGNORECASE)),
    ("waitlist_open", re.compile(r"\bwaitlist\s+(?:is\s+)?open\b", re.IGNORECASE)),
    ("pilot_signup_live", re.compile(r"\bpilot\s+signup\s+(?:is\s+)?(?:live|open)\b", re.IGNORECASE)),
    ("collecting_personal_data", re.compile(r"\bcollecting\s+personal\s+data\b", re.IGNORECASE)),
    ("crm_connected", re.compile(r"\bcrm\s+(?:is\s+)?connected\b", re.IGNORECASE)),
    ("onboarding_ready", re.compile(r"\bonboarding[- ]ready\b", re.IGNORECASE)),
    ("customer_access_open", re.compile(r"\bcustomer\s+access\s+(?:is\s+)?open\b", re.IGNORECASE)),
    ("payment_ready", re.compile(r"\bpayment\s+(?:is\s+)?ready\b", re.IGNORECASE)),
    ("legal_privacy_ready", re.compile(r"\blegal/privacy\s+(?:is\s+)?ready\b", re.IGNORECASE)),
    ("deployment_ready", re.compile(r"\bdeployment\s+(?:is\s+)?ready\b", re.IGNORECASE)),
)


@dataclass(frozen=True, slots=True)
class IntakeQuestionnaireRehearsalFinding:
    """One deterministic intake questionnaire rehearsal validation finding."""

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


def validate_doc_text(text: str) -> list[IntakeQuestionnaireRehearsalFinding]:
    """Return findings for missing intake questionnaire documentation anchors."""

    findings: list[IntakeQuestionnaireRehearsalFinding] = []
    for phrase in REQUIRED_DOC_PHRASES:
        if phrase not in text:
            findings.append(
                IntakeQuestionnaireRehearsalFinding(
                    "foundation_intake_questionnaire_rehearsal_doc_phrase_missing",
                    f"intake questionnaire rehearsal boundary doc missing required phrase: {phrase}",
                )
            )
    return findings


def validate_packet(payload: dict[str, Any]) -> list[IntakeQuestionnaireRehearsalFinding]:
    """Return findings for intake questionnaire rehearsal witness drift."""

    findings: list[IntakeQuestionnaireRehearsalFinding] = []
    findings.extend(validate_root_contract(payload))
    findings.extend(validate_surfaces(payload.get("surfaces")))
    findings.extend(validate_forbidden_value_patterns(payload))
    findings.extend(validate_forbidden_promotion_patterns(payload))
    return findings


def validate_root_contract(payload: dict[str, Any]) -> list[IntakeQuestionnaireRehearsalFinding]:
    """Return findings for root-level intake questionnaire witness drift."""

    findings: list[IntakeQuestionnaireRehearsalFinding] = []
    if set(payload) != EXPECTED_ROOT_KEYS:
        findings.append(
            IntakeQuestionnaireRehearsalFinding(
                "intake_questionnaire_rehearsal_root_keys_invalid",
                f"root keys must be: {', '.join(sorted(EXPECTED_ROOT_KEYS))}",
            )
        )
    expected_values = {
        "witness_id": EXPECTED_WITNESS_ID,
        "schema_version": 1,
        "status": "AwaitingEvidence",
        "solver_outcome": "AwaitingEvidence",
        "questionnaire_rehearsal_executed": False,
        "active_intake_form_exists": False,
        "form_publication_allowed": False,
        "waitlist_open": False,
        "pilot_signup_open": False,
        "personal_data_collection_allowed": False,
        "crm_import_allowed": False,
        "outreach_campaign_allowed": False,
        "customer_onboarding_allowed": False,
        "customer_access_allowed": False,
        "payment_collection_allowed": False,
        "legal_privacy_readiness_claimed": False,
        "deployment_allowed": False,
    }
    for key, expected_value in expected_values.items():
        if payload.get(key) != expected_value:
            findings.append(
                IntakeQuestionnaireRehearsalFinding(
                    "intake_questionnaire_rehearsal_root_value_invalid",
                    f"{key} must be {expected_value!r}",
                )
            )
    if tuple(payload.get("blocked_claims") or ()) != EXPECTED_BLOCKED_CLAIMS:
        findings.append(
            IntakeQuestionnaireRehearsalFinding(
                "intake_questionnaire_rehearsal_blocked_claims_invalid",
                f"blocked_claims must be: {', '.join(EXPECTED_BLOCKED_CLAIMS)}",
            )
        )
    next_action = payload.get("next_action")
    if not isinstance(next_action, str) or "draft fictional local intake questionnaire fields only" not in next_action:
        findings.append(
            IntakeQuestionnaireRehearsalFinding(
                "intake_questionnaire_rehearsal_next_action_invalid",
                "next_action must preserve fictional local questionnaire planning only",
            )
        )
    return findings


def validate_surfaces(surfaces: object) -> list[IntakeQuestionnaireRehearsalFinding]:
    """Return findings for intake questionnaire rehearsal surface drift."""

    findings: list[IntakeQuestionnaireRehearsalFinding] = []
    if not isinstance(surfaces, list) or not all(isinstance(surface, dict) for surface in surfaces):
        return [IntakeQuestionnaireRehearsalFinding("intake_questionnaire_rehearsal_surfaces_invalid", "surfaces must be a list")]
    observed_surfaces = tuple(
        (surface.get("surface_id"), surface.get("surface_type"), surface.get("state"))
        for surface in surfaces
    )
    if observed_surfaces != EXPECTED_SURFACES:
        findings.append(
            IntakeQuestionnaireRehearsalFinding(
                "intake_questionnaire_rehearsal_surface_inventory_invalid",
                "intake questionnaire rehearsal surface inventory does not match the expected set",
            )
        )
    surface_ids = [surface.get("surface_id") for surface in surfaces]
    if len(set(surface_ids)) != len(surface_ids):
        findings.append(IntakeQuestionnaireRehearsalFinding("intake_questionnaire_rehearsal_surface_duplicate", "surface ids must be unique"))
    for surface in surfaces:
        surface_id = str(surface.get("surface_id", "<missing>"))
        if set(surface) != EXPECTED_SURFACE_KEYS:
            findings.append(
                IntakeQuestionnaireRehearsalFinding(
                    "intake_questionnaire_rehearsal_surface_keys_invalid",
                    f"{surface_id} surface keys must be: {', '.join(sorted(EXPECTED_SURFACE_KEYS))}",
                )
            )
        if surface.get("state") != "AwaitingEvidence":
            findings.append(
                IntakeQuestionnaireRehearsalFinding(
                    "intake_questionnaire_rehearsal_surface_state_invalid",
                    f"{surface_id} state must be AwaitingEvidence",
                )
            )
        if surface.get("evidence_ref") != "manual_preparation_pending":
            findings.append(
                IntakeQuestionnaireRehearsalFinding(
                    "intake_questionnaire_rehearsal_surface_evidence_invalid",
                    f"{surface_id} evidence_ref must stay manual_preparation_pending",
                )
            )
        if not isinstance(surface.get("public_safe_note"), str) or not surface["public_safe_note"].strip():
            findings.append(
                IntakeQuestionnaireRehearsalFinding(
                    "intake_questionnaire_rehearsal_surface_note_invalid",
                    f"{surface_id} public_safe_note must be a non-empty string",
                )
            )
    return findings


def validate_forbidden_value_patterns(payload: dict[str, Any]) -> list[IntakeQuestionnaireRehearsalFinding]:
    """Return findings for form, CRM, personal-data, payment, legal, or deployment-shaped values."""

    serialized_payload = json.dumps(payload, sort_keys=True)
    findings: list[IntakeQuestionnaireRehearsalFinding] = []
    for rule_id, pattern in FORBIDDEN_VALUE_PATTERNS:
        if pattern.search(serialized_payload):
            findings.append(
                IntakeQuestionnaireRehearsalFinding(
                    "intake_questionnaire_rehearsal_forbidden_value_pattern",
                    f"intake questionnaire rehearsal witness contains forbidden value pattern: {rule_id}",
                )
            )
    return findings


def validate_forbidden_promotion_patterns(payload: dict[str, Any]) -> list[IntakeQuestionnaireRehearsalFinding]:
    """Return findings if the witness drifts into intake or onboarding readiness claims."""

    serialized_payload = json.dumps(payload, sort_keys=True)
    findings: list[IntakeQuestionnaireRehearsalFinding] = []
    for rule_id, pattern in FORBIDDEN_PROMOTION_PATTERNS:
        if pattern.search(serialized_payload):
            findings.append(
                IntakeQuestionnaireRehearsalFinding(
                    "intake_questionnaire_rehearsal_forbidden_promotion_phrase",
                    f"intake questionnaire rehearsal witness contains forbidden promotion pattern: {rule_id}",
                )
            )
    return findings


def validate_foundation_intake_questionnaire_rehearsal_boundary(
    doc_path: Path = DEFAULT_DOC_PATH,
    packet_path: Path = DEFAULT_PACKET_PATH,
) -> list[IntakeQuestionnaireRehearsalFinding]:
    """Validate the Foundation Mode intake questionnaire rehearsal boundary artifacts."""

    doc_text = load_text(doc_path, "intake questionnaire rehearsal boundary doc")
    packet_payload = load_json_object(packet_path, "intake questionnaire rehearsal witness packet")
    return [
        *validate_doc_text(doc_text),
        *validate_packet(packet_payload),
    ]


def main(argv: list[str] | None = None) -> int:
    """Validate intake questionnaire rehearsal artifacts and print deterministic status."""

    parser = argparse.ArgumentParser(description="Validate Foundation Mode intake questionnaire rehearsal boundary artifacts.")
    parser.add_argument("--doc", type=Path, default=DEFAULT_DOC_PATH)
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET_PATH)
    args = parser.parse_args(argv)

    try:
        findings = validate_foundation_intake_questionnaire_rehearsal_boundary(args.doc, args.packet)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"[FAIL] foundation_intake_questionnaire_rehearsal_load: {exc}", file=sys.stderr)
        print("STATUS: failed", file=sys.stderr)
        return 1

    if findings:
        for finding in findings:
            print(f"[FAIL] {finding.rule_id}: {finding.message}", file=sys.stderr)
        print("STATUS: failed", file=sys.stderr)
        return 1
    print("[PASS] foundation_intake_questionnaire_rehearsal_doc")
    print("[PASS] foundation_intake_questionnaire_rehearsal_witness")
    print("STATUS: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
