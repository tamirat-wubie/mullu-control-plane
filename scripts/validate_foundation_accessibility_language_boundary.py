#!/usr/bin/env python3
"""Validate the Foundation Mode accessibility/language boundary.

Purpose: keep accessibility and language preparation local while accessibility
compliance, WCAG conformance, screen-reader verification, keyboard-navigation
verification, mobile accessibility, contrast compliance, translation readiness,
localization readiness, Mfidel support, Amharic support, user testing,
publication, customer access, and deployment claims remain blocked.
Governance scope: Foundation Mode, public-safe accessibility/language
questions, Mfidel atomicity preservation, private-value exclusion,
customer-access blocking, publication blocking, and deployment blocking.
Dependencies: docs/FOUNDATION_ACCESSIBILITY_LANGUAGE_BOUNDARY.md and
examples/foundation_accessibility_language_witness.awaiting_evidence.json.
Invariants:
  - Validation is read-only.
  - The witness records local accessibility/language planning only.
  - No accessibility compliance, language support, user testing, personal data,
    customer access, publication, or deployment claim is allowed.
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
DEFAULT_DOC_PATH = REPO_ROOT / "docs" / "FOUNDATION_ACCESSIBILITY_LANGUAGE_BOUNDARY.md"
DEFAULT_PACKET_PATH = REPO_ROOT / "examples" / "foundation_accessibility_language_witness.awaiting_evidence.json"

EXPECTED_WITNESS_ID = "foundation_accessibility_language_witness.awaiting_evidence.v1"
EXPECTED_BLOCKED_CLAIMS = (
    "accessibility compliance",
    "WCAG conformance",
    "screen-reader verification",
    "keyboard-navigation verification",
    "mobile-accessibility verification",
    "contrast compliance",
    "translation readiness",
    "localization readiness",
    "Mfidel support",
    "Amharic support",
    "public accessibility statement",
    "external user testing",
    "personal data collection",
    "customer access",
    "external publication",
    "deployment readiness",
)
EXPECTED_SURFACES = (
    ("reading_level_questions", "local_draft", "AwaitingEvidence"),
    ("glossary_access_questions", "local_draft", "AwaitingEvidence"),
    ("keyboard_navigation_questions", "local_draft", "AwaitingEvidence"),
    ("screen_reader_questions", "local_draft", "AwaitingEvidence"),
    ("contrast_layout_questions", "local_draft", "AwaitingEvidence"),
    ("mobile_responsiveness_questions", "local_draft", "AwaitingEvidence"),
    ("translation_scope_questions", "local_draft", "AwaitingEvidence"),
    ("localization_claim_questions", "local_draft", "AwaitingEvidence"),
    ("mfidel_atomicity_questions", "local_draft", "AwaitingEvidence"),
    ("public_accessibility_statement_questions", "local_draft", "AwaitingEvidence"),
)
EXPECTED_ROOT_KEYS = {
    "accessibility_compliance_claimed",
    "accessibility_language_surfaces",
    "amharic_support_claimed",
    "blocked_claims",
    "contrast_compliance_claimed",
    "customer_access_allowed",
    "deployment_allowed",
    "external_publication_allowed",
    "external_user_testing_allowed",
    "keyboard_navigation_verified",
    "localization_readiness_claimed",
    "mfidel_support_claimed",
    "mobile_accessibility_verified",
    "next_action",
    "personal_data_collection_allowed",
    "public_accessibility_statement_allowed",
    "schema_version",
    "screen_reader_verified",
    "solver_outcome",
    "status",
    "translation_readiness_claimed",
    "wcag_conformance_claimed",
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
    "Foundation Accessibility Language Boundary",
    "Witness packet: [`../examples/foundation_accessibility_language_witness.awaiting_evidence.json`]",
    "Rule: Accessibility/language preparation is a local planning boundary, not an accessibility-compliance, translation-readiness, localization-readiness, language-support, user-testing, publication, or deployment certificate.",
    "No accessibility compliance, WCAG conformance, screen-reader verification,",
    "accessibility_language_boundary_state=AwaitingEvidence",
    "accessibility_compliance_claimed=false",
    "wcag_conformance_claimed=false",
    "screen_reader_verified=false",
    "keyboard_navigation_verified=false",
    "mobile_accessibility_verified=false",
    "contrast_compliance_claimed=false",
    "translation_readiness_claimed=false",
    "localization_readiness_claimed=false",
    "mfidel_support_claimed=false",
    "amharic_support_claimed=false",
    "public_accessibility_statement_allowed=false",
    "external_user_testing_allowed=false",
    "personal_data_collection_allowed=false",
    "customer_access_allowed=false",
    "external_publication_allowed=false",
    "deployment_allowed=false",
    "python scripts/validate_foundation_accessibility_language_boundary.py",
)
FORBIDDEN_VALUE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("url_value", re.compile(r"https?://", re.IGNORECASE)),
    ("email_value", re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)),
    ("private_path", re.compile(r"\b[A-Za-z]:[\\/]|\\\\", re.IGNORECASE)),
    (
        "user_test_assignment",
        re.compile(r"\b(?:tester|participant|user|screen[_ -]?reader|device|assistive[_ -]?technology)[_ -]?(?:id|name|email|url|ref|target|value|status)?\s*=", re.IGNORECASE),
    ),
    (
        "accessibility_assignment",
        re.compile(r"\b(?:wcag|a11y|accessibility|contrast|keyboard|focus|mobile)[_ -]?(?:score|level|result|value|status|target)?\s*=", re.IGNORECASE),
    ),
    (
        "language_assignment",
        re.compile(r"\b(?:translation|localization|locale|language|amharic|mfidel)[_ -]?(?:id|url|value|status|target|text)?\s*=", re.IGNORECASE),
    ),
    (
        "account_assignment",
        re.compile(r"\b(?:account|provider|service)[_ -]?(?:id|url|ref|target|value|status)?\s*=", re.IGNORECASE),
    ),
    (
        "secret_assignment",
        re.compile(r"\b(?:password|secret|token|api[_ -]?key|client[_ -]?secret)\s*=", re.IGNORECASE),
    ),
    ("private_key_material", re.compile(r"BEGIN [A-Z ]*PRIVATE KEY")),
)
FORBIDDEN_PROMOTION_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("accessibility_compliant", re.compile(r"\baccessibility\s+(?:is\s+)?(?:compliant|certified|verified)\b", re.IGNORECASE)),
    ("wcag_conformant", re.compile(r"\bWCAG\s+(?:is\s+)?(?:conformant|compliant|verified)\b", re.IGNORECASE)),
    ("screen_reader_verified", re.compile(r"\bscreen[- ]reader\s+(?:is\s+)?verified\b", re.IGNORECASE)),
    ("keyboard_verified", re.compile(r"\bkeyboard\s+(?:navigation\s+)?(?:is\s+)?verified\b", re.IGNORECASE)),
    ("mobile_accessibility_verified", re.compile(r"\bmobile\s+accessibility\s+(?:is\s+)?verified\b", re.IGNORECASE)),
    ("contrast_compliant", re.compile(r"\bcontrast\s+(?:is\s+)?(?:compliant|verified)\b", re.IGNORECASE)),
    ("translation_ready", re.compile(r"\btranslation\s+(?:is\s+)?ready\b", re.IGNORECASE)),
    ("localization_ready", re.compile(r"\blocalization\s+(?:is\s+)?ready\b", re.IGNORECASE)),
    ("mfidel_support_ready", re.compile(r"\bMfidel\s+support\s+(?:is\s+)?(?:ready|complete)\b", re.IGNORECASE)),
    ("amharic_support_ready", re.compile(r"\bAmharic\s+support\s+(?:is\s+)?(?:ready|complete)\b", re.IGNORECASE)),
    ("accessibility_statement_published", re.compile(r"\baccessibility\s+statement\s+(?:is\s+)?published\b", re.IGNORECASE)),
    ("user_testing_complete", re.compile(r"\buser\s+testing\s+(?:is\s+)?(?:complete|completed|done)\b", re.IGNORECASE)),
    ("customer_access_ready", re.compile(r"\bcustomer\s+access\s+(?:is\s+)?ready\b", re.IGNORECASE)),
    ("deployment_ready", re.compile(r"\bdeployment\s+(?:is\s+)?ready\b", re.IGNORECASE)),
)


@dataclass(frozen=True, slots=True)
class AccessibilityLanguageFinding:
    """One deterministic accessibility/language boundary validation finding."""

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


def validate_doc_text(text: str) -> list[AccessibilityLanguageFinding]:
    """Return findings for missing accessibility/language documentation anchors."""

    findings: list[AccessibilityLanguageFinding] = []
    for phrase in REQUIRED_DOC_PHRASES:
        if phrase not in text:
            findings.append(
                AccessibilityLanguageFinding(
                    "foundation_accessibility_language_doc_phrase_missing",
                    f"accessibility/language boundary doc missing required phrase: {phrase}",
                )
            )
    return findings


def validate_packet(payload: dict[str, Any]) -> list[AccessibilityLanguageFinding]:
    """Return findings for accessibility/language witness drift."""

    findings: list[AccessibilityLanguageFinding] = []
    findings.extend(validate_root_contract(payload))
    findings.extend(validate_accessibility_language_surfaces(payload.get("accessibility_language_surfaces")))
    findings.extend(validate_forbidden_value_patterns(payload))
    findings.extend(validate_forbidden_promotion_patterns(payload))
    return findings


def validate_root_contract(payload: dict[str, Any]) -> list[AccessibilityLanguageFinding]:
    """Return findings for root-level accessibility/language witness drift."""

    findings: list[AccessibilityLanguageFinding] = []
    if set(payload) != EXPECTED_ROOT_KEYS:
        findings.append(
            AccessibilityLanguageFinding(
                "accessibility_language_root_keys_invalid",
                f"root keys must be: {', '.join(sorted(EXPECTED_ROOT_KEYS))}",
            )
        )
    expected_values = {
        "witness_id": EXPECTED_WITNESS_ID,
        "schema_version": 1,
        "status": "AwaitingEvidence",
        "solver_outcome": "AwaitingEvidence",
        "accessibility_compliance_claimed": False,
        "wcag_conformance_claimed": False,
        "screen_reader_verified": False,
        "keyboard_navigation_verified": False,
        "mobile_accessibility_verified": False,
        "contrast_compliance_claimed": False,
        "translation_readiness_claimed": False,
        "localization_readiness_claimed": False,
        "mfidel_support_claimed": False,
        "amharic_support_claimed": False,
        "public_accessibility_statement_allowed": False,
        "external_user_testing_allowed": False,
        "personal_data_collection_allowed": False,
        "customer_access_allowed": False,
        "external_publication_allowed": False,
        "deployment_allowed": False,
    }
    for key, expected_value in expected_values.items():
        if payload.get(key) != expected_value:
            findings.append(
                AccessibilityLanguageFinding(
                    "accessibility_language_root_value_invalid",
                    f"{key} must be {expected_value!r}",
                )
            )
    if tuple(payload.get("blocked_claims") or ()) != EXPECTED_BLOCKED_CLAIMS:
        findings.append(
            AccessibilityLanguageFinding(
                "accessibility_language_blocked_claims_invalid",
                f"blocked_claims must be: {', '.join(EXPECTED_BLOCKED_CLAIMS)}",
            )
        )
    next_action = payload.get("next_action")
    if not isinstance(next_action, str) or "keep accessibility and language preparation local" not in next_action:
        findings.append(
            AccessibilityLanguageFinding(
                "accessibility_language_next_action_invalid",
                "next_action must preserve the local accessibility/language boundary",
            )
        )
    return findings


def validate_accessibility_language_surfaces(
    accessibility_language_surfaces: object,
) -> list[AccessibilityLanguageFinding]:
    """Return findings for accessibility/language surface witness drift."""

    findings: list[AccessibilityLanguageFinding] = []
    if not isinstance(accessibility_language_surfaces, list) or not all(
        isinstance(surface, dict) for surface in accessibility_language_surfaces
    ):
        return [
            AccessibilityLanguageFinding(
                "accessibility_language_surfaces_invalid",
                "accessibility_language_surfaces must be a list of objects",
            )
        ]
    observed_surfaces = tuple(
        (surface.get("surface_id"), surface.get("surface_type"), surface.get("state"))
        for surface in accessibility_language_surfaces
    )
    if observed_surfaces != EXPECTED_SURFACES:
        findings.append(
            AccessibilityLanguageFinding(
                "accessibility_language_surface_inventory_invalid",
                "accessibility/language surface inventory does not match the Foundation Mode set",
            )
        )
    surface_ids = [surface.get("surface_id") for surface in accessibility_language_surfaces]
    if len(set(surface_ids)) != len(surface_ids):
        findings.append(AccessibilityLanguageFinding("accessibility_language_surface_duplicate", "surface ids must be unique"))
    for surface in accessibility_language_surfaces:
        surface_id = str(surface.get("surface_id", "<missing>"))
        if set(surface) != EXPECTED_SURFACE_KEYS:
            findings.append(
                AccessibilityLanguageFinding(
                    "accessibility_language_surface_keys_invalid",
                    f"{surface_id} surface keys must be: {', '.join(sorted(EXPECTED_SURFACE_KEYS))}",
                )
            )
        if surface.get("state") != "AwaitingEvidence":
            findings.append(
                AccessibilityLanguageFinding(
                    "accessibility_language_surface_state_invalid",
                    f"{surface_id} state must be AwaitingEvidence",
                )
            )
        if surface.get("evidence_ref") != "manual_preparation_pending":
            findings.append(
                AccessibilityLanguageFinding(
                    "accessibility_language_surface_evidence_invalid",
                    f"{surface_id} evidence_ref must stay manual_preparation_pending in the committed packet",
                )
            )
        if not isinstance(surface.get("public_safe_note"), str) or not surface["public_safe_note"].strip():
            findings.append(
                AccessibilityLanguageFinding(
                    "accessibility_language_surface_note_invalid",
                    f"{surface_id} public_safe_note must be a non-empty string",
                )
            )
    return findings


def validate_forbidden_value_patterns(payload: dict[str, Any]) -> list[AccessibilityLanguageFinding]:
    """Return findings for private, accessibility, language, account, or secret-shaped values."""

    serialized_payload = json.dumps(payload, sort_keys=True)
    findings: list[AccessibilityLanguageFinding] = []
    for rule_id, pattern in FORBIDDEN_VALUE_PATTERNS:
        if pattern.search(serialized_payload):
            findings.append(
                AccessibilityLanguageFinding(
                    "accessibility_language_forbidden_private_value_pattern",
                    f"accessibility/language witness contains forbidden private value pattern: {rule_id}",
                )
            )
    return findings


def validate_forbidden_promotion_patterns(payload: dict[str, Any]) -> list[AccessibilityLanguageFinding]:
    """Return findings for accessibility/language verification or readiness claims."""

    serialized_payload = json.dumps(payload, sort_keys=True)
    findings: list[AccessibilityLanguageFinding] = []
    for rule_id, pattern in FORBIDDEN_PROMOTION_PATTERNS:
        if pattern.search(serialized_payload):
            findings.append(
                AccessibilityLanguageFinding(
                    "accessibility_language_forbidden_promotion_phrase",
                    f"accessibility/language witness contains forbidden promotion phrase: {rule_id}",
                )
            )
    return findings


def validate_foundation_accessibility_language_boundary(
    doc_path: Path = DEFAULT_DOC_PATH,
    packet_path: Path = DEFAULT_PACKET_PATH,
) -> list[AccessibilityLanguageFinding]:
    """Return all accessibility/language boundary validation findings."""

    doc_text = load_text(doc_path, "accessibility/language boundary doc")
    payload = load_json_object(packet_path, "accessibility/language witness")
    findings: list[AccessibilityLanguageFinding] = []
    findings.extend(validate_doc_text(doc_text))
    findings.extend(validate_packet(payload))
    return findings


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--doc", type=Path, default=DEFAULT_DOC_PATH)
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET_PATH)
    return parser.parse_args()


def main() -> int:
    """Run the accessibility/language boundary validator."""

    args = parse_args()
    findings = validate_foundation_accessibility_language_boundary(args.doc, args.packet)
    if findings:
        for finding in findings:
            print(f"[FAIL] {finding.rule_id}: {finding.message}", file=sys.stderr)
        print("STATUS: failed", file=sys.stderr)
        return 1
    print("[PASS] foundation_accessibility_language_doc")
    print("[PASS] foundation_accessibility_language_witness")
    print("STATUS: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
