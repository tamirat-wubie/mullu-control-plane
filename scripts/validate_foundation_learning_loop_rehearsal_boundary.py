#!/usr/bin/env python3
"""Validate the Foundation Mode learning-loop rehearsal boundary.

Purpose: keep one local learning-loop rehearsal public-safe while skill
readiness, training completion, certification, paid-course activation, mentor
assignment, hiring readiness, delegation readiness, public tutorial
publication, curriculum completion, production-operation readiness,
customer-support readiness, external-account use, private schedule recording,
private health recording, spending, legal/business action, source-control
publication, and deployment claims remain blocked.
Governance scope: Foundation Mode, local learning-loop rehearsal, topic
selection, local-doc reading, glossary lookup, harmless command practice,
expected-output pairing, public-safe error category recording, validator
pairing, handoff note, next-loop selection, stop-rule rehearsal, private-value
exclusion, and external-action blocking.
Dependencies: docs/FOUNDATION_LEARNING_LOOP_REHEARSAL_BOUNDARY.md and
examples/foundation_learning_loop_rehearsal_witness.awaiting_evidence.json.
Invariants:
  - The witness records public-safe learning-loop rehearsal labels only.
  - Every learning-loop rehearsal surface remains AwaitingEvidence.
  - No skill, training, certification, paid-course, mentor, hiring, delegation, support, publication, external-account, private schedule, private health, spending, legal/business, source-control publication, or deployment claim is accepted.
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
DEFAULT_DOC_PATH = REPO_ROOT / "docs" / "FOUNDATION_LEARNING_LOOP_REHEARSAL_BOUNDARY.md"
DEFAULT_PACKET_PATH = REPO_ROOT / "examples" / "foundation_learning_loop_rehearsal_witness.awaiting_evidence.json"

REQUIRED_ROOT_KEYS = (
    "blocked_claims",
    "certification_claimed",
    "curriculum_completion_claimed",
    "customer_support_readiness_claimed",
    "deferral_labels",
    "delegation_readiness_claimed",
    "deployment_allowed",
    "external_account_use_allowed",
    "hiring_readiness_claimed",
    "legal_business_action_allowed",
    "loop_rehearsal_executed",
    "mentor_assignment_allowed",
    "next_action",
    "paid_course_allowed",
    "private_health_recording_allowed",
    "private_schedule_recording_allowed",
    "production_operation_readiness_claimed",
    "public_tutorial_publication_allowed",
    "schema_version",
    "skill_readiness_claimed",
    "solver_outcome",
    "source_control_publication_allowed",
    "spending_allowed",
    "status",
    "surfaces",
    "training_completion_claimed",
    "witness_id",
)
EXPECTED_ROOT_VALUES = {
    "schema_version": "foundation.learning_loop_rehearsal.v1",
    "witness_id": "foundation_learning_loop_rehearsal_witness.awaiting_evidence.v1",
    "status": "AwaitingEvidence",
    "solver_outcome": "AwaitingEvidence",
}
FALSE_FLAGS = (
    "certification_claimed",
    "curriculum_completion_claimed",
    "customer_support_readiness_claimed",
    "delegation_readiness_claimed",
    "deployment_allowed",
    "external_account_use_allowed",
    "hiring_readiness_claimed",
    "legal_business_action_allowed",
    "loop_rehearsal_executed",
    "mentor_assignment_allowed",
    "paid_course_allowed",
    "private_health_recording_allowed",
    "private_schedule_recording_allowed",
    "production_operation_readiness_claimed",
    "public_tutorial_publication_allowed",
    "skill_readiness_claimed",
    "source_control_publication_allowed",
    "spending_allowed",
    "training_completion_claimed",
)
DEFERRAL_LABELS = (
    "topic_selection_rehearsal",
    "local_doc_reading_rehearsal",
    "glossary_lookup_rehearsal",
    "harmless_command_rehearsal",
    "expected_output_rehearsal",
    "error_category_rehearsal",
    "validator_pairing_rehearsal",
    "handoff_note_rehearsal",
    "next_loop_selection_rehearsal",
    "stop_rule_rehearsal",
)
BLOCKED_CLAIMS = (
    "skill readiness",
    "training completion",
    "certification",
    "paid course activation",
    "mentor assignment",
    "hiring readiness",
    "delegation readiness",
    "public tutorial publication",
    "curriculum completion",
    "production operation readiness",
    "customer support readiness",
    "external account use",
    "private schedule recording",
    "private health recording",
    "spending",
    "legal/business action",
    "source-control publication",
    "deployment readiness",
)
SURFACE_NOTES_BY_ID = {
    "topic_selection_rehearsal": "Topic selection rehearsal only; skill readiness is not claimed.",
    "local_doc_reading_rehearsal": "Local doc reading rehearsal only; training completion is not claimed.",
    "glossary_lookup_rehearsal": "Glossary lookup rehearsal only; curriculum completion is not claimed.",
    "harmless_command_rehearsal": "Harmless command rehearsal only; services, accounts, and deployment state are not mutated.",
    "expected_output_rehearsal": "Expected output rehearsal only; verification closure is not claimed.",
    "error_category_rehearsal": "Error category rehearsal only; private paths, accounts, schedules, health details, and secrets are not recorded.",
    "validator_pairing_rehearsal": "Validator pairing rehearsal only; certification is not claimed.",
    "handoff_note_rehearsal": "Handoff note rehearsal only; support readiness and team coverage are not claimed.",
    "next_loop_selection_rehearsal": "Next loop selection rehearsal only; deadlines and roadmap delivery are not promised.",
    "stop_rule_rehearsal": "Stop-rule rehearsal only; external action, spending, legal/business action, source-control publication, and deployment are not approved.",
}
SURFACE_TYPES_BY_ID = {
    "topic_selection_rehearsal": "local_topic_label",
    "local_doc_reading_rehearsal": "local_doc_label",
    "glossary_lookup_rehearsal": "local_glossary_label",
    "harmless_command_rehearsal": "local_command_label",
    "expected_output_rehearsal": "local_expected_output_label",
    "error_category_rehearsal": "public_safe_error_label",
    "validator_pairing_rehearsal": "local_validator_label",
    "handoff_note_rehearsal": "public_safe_handoff_label",
    "next_loop_selection_rehearsal": "local_next_loop_label",
    "stop_rule_rehearsal": "local_stop_rule_label",
}
REQUIRED_DOC_PHRASES = (
    "Foundation Learning Loop Rehearsal Boundary",
    "Witness packet: [`../examples/foundation_learning_loop_rehearsal_witness.awaiting_evidence.json`]",
    "Rule: Learning-loop rehearsal is a local paper-and-command practice packet",
    "No skill-readiness claim, training-completion claim, certification claim,",
    "learning_loop_rehearsal_boundary_state=AwaitingEvidence",
    "loop_rehearsal_executed=false",
    "skill_readiness_claimed=false",
    "training_completion_claimed=false",
    "certification_claimed=false",
    "paid_course_allowed=false",
    "mentor_assignment_allowed=false",
    "external_account_use_allowed=false",
    "private_schedule_recording_allowed=false",
    "private_health_recording_allowed=false",
    "spending_allowed=false",
    "legal_business_action_allowed=false",
    "source_control_publication_allowed=false",
    "deployment_allowed=false",
    "python scripts/validate_foundation_learning_loop_rehearsal_boundary.py",
)
FORBIDDEN_VALUE_PATTERNS = (
    ("url", re.compile(r"\b(?:https?://|www\.)\S+", re.IGNORECASE)),
    ("email", re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)),
    ("private_path", re.compile(r"(?:[A-Za-z]:\\|/home/|/Users/|\\\\[^\\]+\\)", re.IGNORECASE)),
    ("private_schedule", re.compile(r"\b(?:calendar|schedule|availability|study[_ -]?time)\w*\s*=", re.IGNORECASE)),
    ("private_health", re.compile(r"\b(?:health|medical|fatigue|sleep|illness)\w*\s*=", re.IGNORECASE)),
    ("secret_material", re.compile(r"\b(?:sk|pk|ghp|github_pat|AKIA)[A-Za-z0-9_-]{8,}\b")),
    ("private_key_material", re.compile(r"BEGIN [A-Z ]*PRIVATE KEY")),
    (
        "assignment_shape",
        re.compile(
            r"\b(?:mentor|teacher|tutor|coach|hire|contractor|delegate|account|provider|course|"
            r"subscription|billing|payment|purchase|invoice|certificate|certification|credential|"
            r"customer|support|ticket|sla|commit|push|pull[_ -]?request|release|legal|company|"
            r"patent|tax|terms|secret|token|key|endpoint|deploy|deployment|production)\w*\s*=",
            re.IGNORECASE,
        ),
    ),
)
FORBIDDEN_PROMOTION_PATTERNS = (
    ("skill_ready", re.compile(r"\bskill\s+(?:is\s+)?ready\b", re.IGNORECASE)),
    ("training_complete", re.compile(r"\btraining\s+(?:is\s+)?complete\b", re.IGNORECASE)),
    ("certified", re.compile(r"\bcertified\b", re.IGNORECASE)),
    ("paid_course_activated", re.compile(r"\bpaid\s+course\s+(?:is\s+)?activated\b", re.IGNORECASE)),
    ("mentor_assigned", re.compile(r"\bmentor\s+(?:is\s+)?assigned\b", re.IGNORECASE)),
    ("hiring_ready", re.compile(r"\bhiring\s+(?:is\s+)?ready\b", re.IGNORECASE)),
    ("delegation_ready", re.compile(r"\bdelegation\s+(?:is\s+)?ready\b", re.IGNORECASE)),
    ("tutorial_published", re.compile(r"\btutorial\s+(?:is\s+)?published\b", re.IGNORECASE)),
    ("curriculum_complete", re.compile(r"\bcurriculum\s+(?:is\s+)?complete\b", re.IGNORECASE)),
    ("production_operation_ready", re.compile(r"\bproduction\s+operation\s+(?:is\s+)?ready\b", re.IGNORECASE)),
    ("customer_support_ready", re.compile(r"\bcustomer\s+support\s+(?:is\s+)?ready\b", re.IGNORECASE)),
    ("external_account_ready", re.compile(r"\bexternal\s+account\s+(?:is\s+)?ready\b", re.IGNORECASE)),
    ("spending_approved", re.compile(r"\bspending\s+(?:is\s+)?approved\b", re.IGNORECASE)),
    ("legal_business_ready", re.compile(r"\blegal\s+business\s+(?:is\s+)?ready\b", re.IGNORECASE)),
    ("source_control_published", re.compile(r"\bsource\s+control\s+(?:is\s+)?published\b", re.IGNORECASE)),
    ("deployment_ready", re.compile(r"\bdeployment\s+(?:is\s+)?ready\b", re.IGNORECASE)),
)


@dataclass(frozen=True, slots=True)
class Finding:
    """One deterministic learning-loop rehearsal validation finding."""

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
    """Return findings for learning-loop rehearsal surface inventory and state drift."""

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
    """Return findings for learning-loop rehearsal packet drift."""

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
    if not isinstance(next_action, str) or "learning-loop rehearsal" not in next_action:
        findings.append(Finding("witness_next_action", "next_action must preserve learning-loop rehearsal"))
    findings.extend(validate_surfaces(payload.get("surfaces")))
    findings.extend(validate_forbidden_text(payload))
    return findings


def validate_artifacts(
    doc_path: Path = DEFAULT_DOC_PATH,
    packet_path: Path = DEFAULT_PACKET_PATH,
) -> list[Finding]:
    """Validate the learning-loop rehearsal doc and witness packet."""

    doc_text = load_text(doc_path, "learning-loop rehearsal doc")
    payload = load_json_object(packet_path, "learning-loop rehearsal witness")
    return [*validate_doc_text(doc_text), *validate_packet(payload)]


def main(argv: list[str] | None = None) -> int:
    """Run the learning-loop rehearsal validator."""

    parser = argparse.ArgumentParser(description="Validate Foundation Mode learning-loop rehearsal artifacts.")
    parser.add_argument("--doc", type=Path, default=DEFAULT_DOC_PATH)
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET_PATH)
    args = parser.parse_args(argv)

    try:
        findings = validate_artifacts(args.doc, args.packet)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"[FAIL] foundation_learning_loop_rehearsal_load: {exc}", file=sys.stderr)
        print("STATUS: failed", file=sys.stderr)
        return 1
    if findings:
        for finding in findings:
            print(f"[FAIL] {finding.rule_id}: {finding.message}", file=sys.stderr)
        print("STATUS: failed", file=sys.stderr)
        return 1
    print("[PASS] foundation_learning_loop_rehearsal_doc")
    print("[PASS] foundation_learning_loop_rehearsal_witness")
    print("STATUS: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
