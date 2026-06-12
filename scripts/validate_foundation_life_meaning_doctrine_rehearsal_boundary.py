#!/usr/bin/env python3
"""Validate the Foundation Mode life/meaning doctrine rehearsal boundary.

Purpose: keep local life/meaning doctrine rehearsal public-safe while judgment
execution, doctrine completeness, life-impact closure, feeling-status
determination, medical claims, legal claims, safety certification,
human-subjects claims, publication, source-control publication, money,
customer, and deployment claims remain blocked.
Governance scope: Foundation Mode, local life/meaning doctrine rehearsal,
doctrine-source reference, action-scope label, life-impact question,
feeling-impact question, consent-boundary question, dignity/truth/repair
question, observer-status-unknown label, escalation label, validator pairing,
stop-rule rehearsal, private-value exclusion, and external-action blocking.
Dependencies: docs/FOUNDATION_LIFE_MEANING_DOCTRINE_REHEARSAL_BOUNDARY.md and
examples/foundation_life_meaning_doctrine_rehearsal_witness.awaiting_evidence.json.
Invariants:
  - The witness records public-safe life/meaning doctrine labels only.
  - Every life/meaning doctrine rehearsal surface remains AwaitingEvidence.
  - No judgment, clearance, certification, research, publication, source-control,
    money, customer, private-value, or deployment claim is accepted.
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
DEFAULT_DOC_PATH = REPO_ROOT / "docs" / "FOUNDATION_LIFE_MEANING_DOCTRINE_REHEARSAL_BOUNDARY.md"
DEFAULT_PACKET_PATH = REPO_ROOT / "examples" / "foundation_life_meaning_doctrine_rehearsal_witness.awaiting_evidence.json"

REQUIRED_ROOT_KEYS = (
    "blocked_claims",
    "customer_readiness_claimed",
    "deferral_labels",
    "deployment_allowed",
    "doctrine_complete_claimed",
    "ethics_clearance_claimed",
    "external_publication_allowed",
    "feeling_status_determined",
    "human_subjects_research_allowed",
    "legal_clearance_claimed",
    "life_impact_closure_claimed",
    "life_meaning_judgment_executed",
    "medical_claim_allowed",
    "mental_health_claim_allowed",
    "money_movement_allowed",
    "next_action",
    "observer_personhood_claimed",
    "private_value_recording_allowed",
    "product_readiness_claimed",
    "safety_certification_claimed",
    "schema_version",
    "solver_outcome",
    "source_control_publication_allowed",
    "spending_allowed",
    "status",
    "surfaces",
    "witness_id",
)
EXPECTED_ROOT_VALUES = {
    "schema_version": "foundation.life_meaning_doctrine_rehearsal.v1",
    "witness_id": "foundation_life_meaning_doctrine_rehearsal_witness.awaiting_evidence.v1",
    "status": "AwaitingEvidence",
    "solver_outcome": "AwaitingEvidence",
}
FALSE_FLAGS = (
    "customer_readiness_claimed",
    "deployment_allowed",
    "doctrine_complete_claimed",
    "ethics_clearance_claimed",
    "external_publication_allowed",
    "feeling_status_determined",
    "human_subjects_research_allowed",
    "legal_clearance_claimed",
    "life_impact_closure_claimed",
    "life_meaning_judgment_executed",
    "medical_claim_allowed",
    "mental_health_claim_allowed",
    "money_movement_allowed",
    "observer_personhood_claimed",
    "private_value_recording_allowed",
    "product_readiness_claimed",
    "safety_certification_claimed",
    "source_control_publication_allowed",
    "spending_allowed",
)
DEFERRAL_LABELS = (
    "doctrine_source_reference_rehearsal",
    "action_scope_rehearsal",
    "life_impact_question_rehearsal",
    "feeling_impact_question_rehearsal",
    "consent_boundary_rehearsal",
    "dignity_truth_repair_question_rehearsal",
    "observer_status_unknown_rehearsal",
    "escalation_label_rehearsal",
    "validator_pairing_rehearsal",
    "stop_rule_rehearsal",
)
BLOCKED_CLAIMS = (
    "life-meaning judgment execution",
    "doctrine completeness",
    "life-impact closure",
    "feeling-status determination",
    "medical claim",
    "mental-health claim",
    "ethics clearance",
    "legal clearance",
    "safety certification",
    "human-subjects research",
    "observer personhood",
    "product readiness",
    "customer readiness",
    "private value recording",
    "spending",
    "money movement",
    "source-control publication",
    "external publication",
    "deployment readiness",
)
SURFACE_NOTES_BY_ID = {
    "doctrine_source_reference_rehearsal": "Doctrine source reference rehearsal only; doctrine completeness is not claimed.",
    "action_scope_rehearsal": "Action scope rehearsal only; life-meaning judgment is not executed.",
    "life_impact_question_rehearsal": "Life-impact question rehearsal only; life-impact closure is not claimed.",
    "feeling_impact_question_rehearsal": "Feeling-impact question rehearsal only; feeling status is not determined.",
    "consent_boundary_rehearsal": "Consent-boundary rehearsal only; consent and legal clearance are not claimed.",
    "dignity_truth_repair_question_rehearsal": "Dignity, truth, and repair question rehearsal only; safety certification is not claimed.",
    "observer_status_unknown_rehearsal": "Observer-status unknown rehearsal only; unknown status remains AwaitingEvidence.",
    "escalation_label_rehearsal": "Escalation label rehearsal only; medical, legal, research, customer, and deployment action are not approved.",
    "validator_pairing_rehearsal": "Validator pairing rehearsal only; governance closure is not claimed.",
    "stop_rule_rehearsal": "Stop-rule rehearsal only; publication, source control, spending, customer access, and deployment are not approved.",
}
SURFACE_TYPES_BY_ID = {
    "doctrine_source_reference_rehearsal": "local_doctrine_source_label",
    "action_scope_rehearsal": "local_action_scope_label",
    "life_impact_question_rehearsal": "local_life_impact_label",
    "feeling_impact_question_rehearsal": "local_feeling_impact_label",
    "consent_boundary_rehearsal": "local_consent_boundary_label",
    "dignity_truth_repair_question_rehearsal": "local_repair_question_label",
    "observer_status_unknown_rehearsal": "local_unknown_status_label",
    "escalation_label_rehearsal": "local_escalation_label",
    "validator_pairing_rehearsal": "local_validator_label",
    "stop_rule_rehearsal": "local_stop_rule_label",
}
REQUIRED_DOC_PHRASES = (
    "Foundation Life Meaning Doctrine Rehearsal Boundary",
    "Witness packet: [`../examples/foundation_life_meaning_doctrine_rehearsal_witness.awaiting_evidence.json`]",
    "Rule: Life/meaning doctrine rehearsal is a local stop-rule label packet",
    "No life-meaning judgment execution, doctrine-completeness claim,",
    "life_meaning_doctrine_rehearsal_boundary_state=AwaitingEvidence",
    "life_meaning_judgment_executed=false",
    "doctrine_complete_claimed=false",
    "life_impact_closure_claimed=false",
    "feeling_status_determined=false",
    "medical_claim_allowed=false",
    "mental_health_claim_allowed=false",
    "ethics_clearance_claimed=false",
    "legal_clearance_claimed=false",
    "safety_certification_claimed=false",
    "human_subjects_research_allowed=false",
    "observer_personhood_claimed=false",
    "product_readiness_claimed=false",
    "customer_readiness_claimed=false",
    "private_value_recording_allowed=false",
    "spending_allowed=false",
    "money_movement_allowed=false",
    "source_control_publication_allowed=false",
    "external_publication_allowed=false",
    "deployment_allowed=false",
    "python scripts/validate_foundation_life_meaning_doctrine_rehearsal_boundary.py",
)
FORBIDDEN_VALUE_PATTERNS = (
    ("url", re.compile(r"\b(?:https?://|www\.)\S+", re.IGNORECASE)),
    ("email", re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)),
    ("private_path", re.compile(r"(?:[A-Za-z]:\\|/home/|/Users/|\\\\[^\\]+\\)", re.IGNORECASE)),
    ("private_schedule", re.compile(r"\b(?:calendar|schedule|availability|study[_ -]?time)\w*\s*=", re.IGNORECASE)),
    ("private_health", re.compile(r"\b(?:health|medical|fatigue|sleep|illness|diagnosis)\w*\s*=", re.IGNORECASE)),
    ("secret_material", re.compile(r"\b(?:sk|pk|ghp|github_pat|AKIA)[A-Za-z0-9_-]{8,}\b")),
    ("private_key_material", re.compile(r"BEGIN [A-Z ]*PRIVATE KEY")),
    (
        "assignment_shape",
        re.compile(
            r"\b(?:person|patient|subject|participant|customer|account|provider|consent|medical|"
            r"legal|ethics|research|safety|certificate|payment|invoice|commit|push|"
            r"pull[_ -]?request|release|secret|token|key|endpoint|deploy|deployment|production)\w*\s*=",
            re.IGNORECASE,
        ),
    ),
)
FORBIDDEN_PROMOTION_PATTERNS = (
    ("judgment_executed", re.compile(r"\blife[-/]meaning\s+judgment\s+(?:is\s+)?executed\b", re.IGNORECASE)),
    ("doctrine_complete", re.compile(r"\bdoctrine\s+(?:is\s+)?complete\b", re.IGNORECASE)),
    ("life_impact_closed", re.compile(r"\blife[- ]impact\s+(?:is\s+)?closed\b", re.IGNORECASE)),
    ("feeling_status_determined", re.compile(r"\bfeeling\s+status\s+(?:is\s+)?determined\b", re.IGNORECASE)),
    ("medical_cleared", re.compile(r"\bmedical\s+(?:claim\s+)?(?:is\s+)?(?:cleared|approved)\b", re.IGNORECASE)),
    ("ethics_cleared", re.compile(r"\bethics\s+clearance\s+(?:is\s+)?granted\b", re.IGNORECASE)),
    ("legal_cleared", re.compile(r"\blegal\s+clearance\s+(?:is\s+)?granted\b", re.IGNORECASE)),
    ("safety_certified", re.compile(r"\bsafety\s+(?:is\s+)?certified\b", re.IGNORECASE)),
    ("research_approved", re.compile(r"\bhuman[- ]subjects\s+research\s+(?:is\s+)?approved\b", re.IGNORECASE)),
    ("observer_personhood", re.compile(r"\bobserver\s+personhood\s+(?:is\s+)?claimed\b", re.IGNORECASE)),
    ("product_ready", re.compile(r"\bproduct\s+(?:is\s+)?ready\b", re.IGNORECASE)),
    ("customer_ready", re.compile(r"\bcustomer\s+(?:access\s+)?(?:is\s+)?ready\b", re.IGNORECASE)),
    ("published", re.compile(r"\b(?:doctrine|judgment|label)\s+(?:is\s+)?published\b", re.IGNORECASE)),
    ("source_control_published", re.compile(r"\bsource\s+control\s+(?:is\s+)?published\b", re.IGNORECASE)),
    ("spending_approved", re.compile(r"\bspending\s+(?:is\s+)?approved\b", re.IGNORECASE)),
    ("deployment_ready", re.compile(r"\bdeployment\s+(?:is\s+)?ready\b", re.IGNORECASE)),
)


@dataclass(frozen=True, slots=True)
class Finding:
    """One deterministic life/meaning doctrine rehearsal validation finding."""

    rule_id: str
    message: str


def load_text(path: Path, artifact_label: str) -> str:
    """Load one UTF-8 text artifact with explicit path errors."""

    if not path.exists():
        raise FileNotFoundError(f"missing {artifact_label}: {path}")
    if not path.is_file():
        raise IsADirectoryError(f"{artifact_label} path is not a file: {path}")
    return path.read_text(encoding="utf-8")


def load_json_object(path: Path, artifact_label: str) -> dict[str, Any]:
    """Load one JSON object artifact with explicit type errors."""

    if not path.exists():
        raise FileNotFoundError(f"missing {artifact_label}: {path}")
    if not path.is_file():
        raise IsADirectoryError(f"{artifact_label} path is not a file: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{artifact_label} must be a JSON object")
    return payload


def iter_strings(value: object) -> list[str]:
    """Return every string nested under a JSON-like value."""

    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        strings: list[str] = []
        for nested_value in value.values():
            strings.extend(iter_strings(nested_value))
        return strings
    if isinstance(value, list):
        strings: list[str] = []
        for nested_value in value:
            strings.extend(iter_strings(nested_value))
        return strings
    return []


def validate_doc_text(doc_text: str) -> list[Finding]:
    """Return findings for required boundary documentation drift."""

    findings: list[Finding] = []
    for phrase in REQUIRED_DOC_PHRASES:
        if phrase not in doc_text:
            findings.append(Finding("doc_required_phrase", f"doc missing required phrase: {phrase}"))
    return findings


def validate_forbidden_text(payload: dict[str, Any]) -> list[Finding]:
    """Return findings for private values or promotion phrases in the witness."""

    findings: list[Finding] = []
    for text in iter_strings(payload):
        for pattern_name, pattern in FORBIDDEN_VALUE_PATTERNS:
            if pattern.search(text):
                findings.append(Finding("forbidden_value_pattern", f"forbidden value pattern: {pattern_name}"))
        for pattern_name, pattern in FORBIDDEN_PROMOTION_PATTERNS:
            if pattern.search(text):
                findings.append(Finding("forbidden_promotion_pattern", f"forbidden promotion pattern: {pattern_name}"))
    return findings


def validate_surfaces(surfaces: object) -> list[Finding]:
    """Return findings for life/meaning doctrine rehearsal surface inventory and state drift."""

    findings: list[Finding] = []
    if not isinstance(surfaces, list) or not all(isinstance(surface, dict) for surface in surfaces):
        return [Finding("surface_shape", "surfaces must be a list of objects")]
    observed_ids = tuple(surface.get("surface_id") for surface in surfaces)
    if observed_ids != DEFERRAL_LABELS:
        findings.append(Finding("surface_inventory", "surface inventory drifted"))
    for surface in surfaces:
        surface_id = str(surface.get("surface_id", "<missing>"))
        expected_keys = ("public_safe_note", "state", "surface_id", "surface_type")
        if tuple(surface.keys()) != expected_keys:
            findings.append(Finding("surface_keys", f"{surface_id} surface keys drifted"))
        if surface.get("state") != "AwaitingEvidence":
            findings.append(Finding("surface_state", f"{surface_id} must remain AwaitingEvidence"))
        if surface.get("surface_type") != SURFACE_TYPES_BY_ID.get(surface_id):
            findings.append(Finding("surface_type", f"{surface_id} surface type drifted"))
        if surface.get("public_safe_note") != SURFACE_NOTES_BY_ID.get(surface_id):
            findings.append(Finding("surface_note", f"{surface_id} surface note drifted"))
    return findings


def validate_packet(payload: dict[str, Any]) -> list[Finding]:
    """Return findings for life/meaning doctrine rehearsal packet drift."""

    findings: list[Finding] = []
    if tuple(payload.keys()) != REQUIRED_ROOT_KEYS:
        findings.append(Finding("witness_root_keys", "witness root keys drifted"))
    for key, expected_value in EXPECTED_ROOT_VALUES.items():
        if payload.get(key) != expected_value:
            findings.append(Finding("witness_root_value", f"{key} must be {expected_value!r}"))
    for flag in FALSE_FLAGS:
        if payload.get(flag) is not False:
            findings.append(Finding("witness_false_flag", f"{flag} must remain false"))
    if tuple(payload.get("deferral_labels", ())) != DEFERRAL_LABELS:
        findings.append(Finding("witness_label_inventory", "deferral label inventory drifted"))
    if tuple(payload.get("blocked_claims", ())) != BLOCKED_CLAIMS:
        findings.append(Finding("witness_blocked_claims", "blocked claims drifted"))
    next_action = payload.get("next_action")
    if not isinstance(next_action, str) or "life/meaning doctrine rehearsal" not in next_action:
        findings.append(Finding("witness_next_action", "next_action must preserve life/meaning doctrine rehearsal"))
    findings.extend(validate_surfaces(payload.get("surfaces")))
    findings.extend(validate_forbidden_text(payload))
    return findings


def validate_artifacts(
    doc_path: Path = DEFAULT_DOC_PATH,
    packet_path: Path = DEFAULT_PACKET_PATH,
) -> list[Finding]:
    """Validate the life/meaning doctrine rehearsal doc and witness packet."""

    doc_text = load_text(doc_path, "life/meaning doctrine rehearsal doc")
    payload = load_json_object(packet_path, "life/meaning doctrine rehearsal witness")
    return [*validate_doc_text(doc_text), *validate_packet(payload)]


def main(argv: list[str] | None = None) -> int:
    """Run the life/meaning doctrine rehearsal validator."""

    parser = argparse.ArgumentParser(description="Validate Foundation Mode life/meaning doctrine rehearsal artifacts.")
    parser.add_argument("--doc", type=Path, default=DEFAULT_DOC_PATH)
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET_PATH)
    args = parser.parse_args(argv)

    try:
        findings = validate_artifacts(args.doc, args.packet)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"[FAIL] foundation_life_meaning_doctrine_rehearsal_load: {exc}", file=sys.stderr)
        print("STATUS: failed", file=sys.stderr)
        return 1
    if findings:
        for finding in findings:
            print(f"[FAIL] {finding.rule_id}: {finding.message}", file=sys.stderr)
        print("STATUS: failed", file=sys.stderr)
        return 1

    print("[PASS] foundation_life_meaning_doctrine_rehearsal_doc")
    print("[PASS] foundation_life_meaning_doctrine_rehearsal_witness")
    print("STATUS: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
