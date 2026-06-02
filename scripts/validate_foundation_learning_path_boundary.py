#!/usr/bin/env python3
"""Validate the Foundation Mode learning-path boundary.

Purpose: keep solo learning local and public-safe while skill readiness,
training completion, certification, paid-course activation, mentor assignment,
hiring readiness, delegation readiness, public tutorial publication,
curriculum completion, production-operation readiness, customer-support
readiness, external account use, and deployment readiness claims remain
blocked.
Governance scope: Foundation Mode, learning goal inventory, glossary loop,
command practice, reading queue, local exercise design, error log, verification
habit, help-request boundary, private-value exclusion, and readiness blocking.
Dependencies: docs/FOUNDATION_LEARNING_PATH_BOUNDARY.md and
examples/foundation_learning_path_witness.awaiting_evidence.json.
Invariants:
  - Validation is read-only.
  - The witness records learning-path preparation only.
  - No skill-readiness, training-completion, certification, paid-course,
    mentor, hiring, delegation, public tutorial, curriculum-completion,
    production-operation, customer-support, external-account, or deployment
    claim is allowed.
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
DEFAULT_DOC_PATH = REPO_ROOT / "docs" / "FOUNDATION_LEARNING_PATH_BOUNDARY.md"
DEFAULT_PACKET_PATH = REPO_ROOT / "examples" / "foundation_learning_path_witness.awaiting_evidence.json"

EXPECTED_WITNESS_ID = "foundation_learning_path_witness.awaiting_evidence.v1"
EXPECTED_BLOCKED_CLAIMS = (
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
    "deployment readiness",
)
EXPECTED_SURFACES = (
    ("learning_goal_inventory", "local_draft", "AwaitingEvidence"),
    ("glossary_loop", "local_draft", "AwaitingEvidence"),
    ("command_practice_loop", "local_draft", "AwaitingEvidence"),
    ("reading_queue", "local_draft", "AwaitingEvidence"),
    ("local_exercise_design", "local_draft", "AwaitingEvidence"),
    ("error_log", "local_draft", "AwaitingEvidence"),
    ("verification_habit", "local_draft", "AwaitingEvidence"),
    ("help_request_boundary", "local_draft", "AwaitingEvidence"),
)
EXPECTED_ROOT_KEYS = {
    "blocked_claims",
    "certification_claimed",
    "curriculum_completion_claimed",
    "customer_support_readiness_claimed",
    "delegation_readiness_claimed",
    "deployment_allowed",
    "external_account_use_allowed",
    "hiring_readiness_claimed",
    "learning_path_surfaces",
    "mentor_assignment_allowed",
    "next_action",
    "paid_course_allowed",
    "production_operation_readiness_claimed",
    "public_tutorial_publication_allowed",
    "schema_version",
    "skill_readiness_claimed",
    "solver_outcome",
    "status",
    "training_completion_claimed",
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
    "Foundation Learning Path Boundary",
    "Witness packet: [`../examples/foundation_learning_path_witness.awaiting_evidence.json`]",
    "Rule: Learning-path preparation is a local planning boundary, not a skill,",
    "No skill-readiness claim, training-completion claim, certification claim,",
    "learning_path_boundary_state=AwaitingEvidence",
    "skill_readiness_claimed=false",
    "training_completion_claimed=false",
    "certification_claimed=false",
    "paid_course_allowed=false",
    "mentor_assignment_allowed=false",
    "external_account_use_allowed=false",
    "deployment_allowed=false",
    "python scripts/validate_foundation_learning_path_boundary.py",
)
FORBIDDEN_VALUE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("url_value", re.compile(r"https?://", re.IGNORECASE)),
    ("email_value", re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)),
    ("private_path", re.compile(r"\b[A-Za-z]:[\\/]|\\\\", re.IGNORECASE)),
    (
        "private_schedule_assignment",
        re.compile(r"\b(?:schedule|calendar|study[_ -]?time|availability)[_ -]?(?:id|ref|target|value|status)?\s*=", re.IGNORECASE),
    ),
    (
        "person_assignment",
        re.compile(r"\b(?:mentor|teacher|tutor|coach|helper|hire|contractor|delegate)[_ -]?(?:id|name|email|ref|target|value)?\s*=", re.IGNORECASE),
    ),
    (
        "account_or_provider_assignment",
        re.compile(r"\b(?:account|provider|course|platform|subscription)[_ -]?(?:id|ref|target|value|status)?\s*=", re.IGNORECASE),
    ),
    (
        "paid_course_assignment",
        re.compile(r"\b(?:payment|billing|purchase|invoice|paid[_ -]?course|course[_ -]?purchase)[_ -]?(?:id|ref|target|value|status)?\s*=", re.IGNORECASE),
    ),
    (
        "certificate_assignment",
        re.compile(r"\b(?:certificate|certification|credential)[_ -]?(?:id|ref|target|value|status)?\s*=", re.IGNORECASE),
    ),
    (
        "secret_assignment",
        re.compile(r"\b(?:password|secret|token|api[_ -]?key|client[_ -]?secret)\s*=", re.IGNORECASE),
    ),
    ("private_key_material", re.compile(r"BEGIN [A-Z ]*PRIVATE KEY")),
    (
        "customer_or_support_assignment",
        re.compile(r"\b(?:customer|support|sla|ticket|user)[_ -]?(?:id|name|email|ref|target|value|status)?\s*=", re.IGNORECASE),
    ),
    (
        "publication_assignment",
        re.compile(r"\b(?:publish|tutorial|blog|video|course)[_ -]?(?:id|url|ref|target|value|status)?\s*=", re.IGNORECASE),
    ),
    (
        "service_or_deployment_assignment",
        re.compile(r"\b(?:service|server|endpoint|runtime|deploy|deployment|production)[_ -]?(?:id|url|ref|target|value|status)?\s*=", re.IGNORECASE),
    ),
)
FORBIDDEN_PROMOTION_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("skill_ready", re.compile(r"\bskill\s+(?:is\s+)?ready\b", re.IGNORECASE)),
    ("training_complete", re.compile(r"\btraining\s+(?:is\s+)?complete\b", re.IGNORECASE)),
    ("certified", re.compile(r"\bcertified\b", re.IGNORECASE)),
    ("course_activated", re.compile(r"\bpaid\s+course\s+(?:is\s+)?activated\b", re.IGNORECASE)),
    ("mentor_assigned", re.compile(r"\bmentor\s+(?:is\s+)?assigned\b", re.IGNORECASE)),
    ("hiring_ready", re.compile(r"\bhiring\s+(?:is\s+)?ready\b", re.IGNORECASE)),
    ("delegation_ready", re.compile(r"\bdelegation\s+(?:is\s+)?ready\b", re.IGNORECASE)),
    ("tutorial_published", re.compile(r"\btutorial\s+(?:is\s+)?published\b", re.IGNORECASE)),
    ("curriculum_complete", re.compile(r"\bcurriculum\s+(?:is\s+)?complete\b", re.IGNORECASE)),
    ("production_operation_ready", re.compile(r"\bproduction\s+operation\s+(?:is\s+)?ready\b", re.IGNORECASE)),
    ("customer_support_ready", re.compile(r"\bcustomer\s+support\s+(?:is\s+)?ready\b", re.IGNORECASE)),
    ("external_account_ready", re.compile(r"\bexternal\s+account\s+(?:is\s+)?ready\b", re.IGNORECASE)),
    ("deployment_ready", re.compile(r"\bdeployment\s+(?:is\s+)?ready\b", re.IGNORECASE)),
)


@dataclass(frozen=True, slots=True)
class LearningPathFinding:
    """One deterministic learning-path boundary validation finding."""

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


def validate_doc_text(text: str) -> list[LearningPathFinding]:
    """Return findings for missing learning-path documentation anchors."""

    findings: list[LearningPathFinding] = []
    for phrase in REQUIRED_DOC_PHRASES:
        if phrase not in text:
            findings.append(
                LearningPathFinding(
                    "foundation_learning_path_doc_phrase_missing",
                    f"learning-path boundary doc missing required phrase: {phrase}",
                )
            )
    return findings


def validate_packet(payload: dict[str, Any]) -> list[LearningPathFinding]:
    """Return findings for learning-path witness drift."""

    findings: list[LearningPathFinding] = []
    findings.extend(validate_root_contract(payload))
    findings.extend(validate_learning_path_surfaces(payload.get("learning_path_surfaces")))
    findings.extend(validate_forbidden_value_patterns(payload))
    findings.extend(validate_forbidden_promotion_patterns(payload))
    return findings


def validate_root_contract(payload: dict[str, Any]) -> list[LearningPathFinding]:
    """Return findings for root-level learning-path witness drift."""

    findings: list[LearningPathFinding] = []
    if set(payload) != EXPECTED_ROOT_KEYS:
        findings.append(
            LearningPathFinding(
                "learning_path_root_keys_invalid",
                f"root keys must be: {', '.join(sorted(EXPECTED_ROOT_KEYS))}",
            )
        )
    expected_values = {
        "witness_id": EXPECTED_WITNESS_ID,
        "schema_version": 1,
        "status": "AwaitingEvidence",
        "solver_outcome": "AwaitingEvidence",
        "skill_readiness_claimed": False,
        "training_completion_claimed": False,
        "certification_claimed": False,
        "paid_course_allowed": False,
        "mentor_assignment_allowed": False,
        "hiring_readiness_claimed": False,
        "delegation_readiness_claimed": False,
        "public_tutorial_publication_allowed": False,
        "curriculum_completion_claimed": False,
        "production_operation_readiness_claimed": False,
        "customer_support_readiness_claimed": False,
        "external_account_use_allowed": False,
        "deployment_allowed": False,
    }
    for key, expected_value in expected_values.items():
        if payload.get(key) != expected_value:
            findings.append(
                LearningPathFinding(
                    "learning_path_root_value_invalid",
                    f"{key} must be {expected_value!r}",
                )
            )
    if tuple(payload.get("blocked_claims") or ()) != EXPECTED_BLOCKED_CLAIMS:
        findings.append(
            LearningPathFinding(
                "learning_path_blocked_claims_invalid",
                f"blocked_claims must be: {', '.join(EXPECTED_BLOCKED_CLAIMS)}",
            )
        )
    next_action = payload.get("next_action")
    if not isinstance(next_action, str) or "continue local learning loops" not in next_action:
        findings.append(
            LearningPathFinding(
                "learning_path_next_action_invalid",
                "next_action must preserve local learning loops without readiness promotion",
            )
        )
    return findings


def validate_learning_path_surfaces(learning_path_surfaces: object) -> list[LearningPathFinding]:
    """Return findings for learning-path surface drift."""

    findings: list[LearningPathFinding] = []
    if not isinstance(learning_path_surfaces, list) or not all(
        isinstance(surface, dict) for surface in learning_path_surfaces
    ):
        return [LearningPathFinding("learning_path_surfaces_invalid", "learning_path_surfaces must be a list of objects")]
    observed_surfaces = tuple(
        (surface.get("surface_id"), surface.get("surface_type"), surface.get("state"))
        for surface in learning_path_surfaces
    )
    if observed_surfaces != EXPECTED_SURFACES:
        findings.append(
            LearningPathFinding(
                "learning_path_surface_inventory_invalid",
                "learning-path surface inventory does not match the Foundation Mode learning set",
            )
        )
    surface_ids = [surface.get("surface_id") for surface in learning_path_surfaces]
    if len(set(surface_ids)) != len(surface_ids):
        findings.append(LearningPathFinding("learning_path_surface_duplicate", "surface ids must be unique"))
    for surface in learning_path_surfaces:
        surface_id = str(surface.get("surface_id", "<missing>"))
        if set(surface) != EXPECTED_SURFACE_KEYS:
            findings.append(
                LearningPathFinding(
                    "learning_path_surface_keys_invalid",
                    f"{surface_id} surface keys must be: {', '.join(sorted(EXPECTED_SURFACE_KEYS))}",
                )
            )
        if surface.get("state") != "AwaitingEvidence":
            findings.append(
                LearningPathFinding(
                    "learning_path_surface_state_invalid",
                    f"{surface_id} state must be AwaitingEvidence",
                )
            )
        if surface.get("evidence_ref") != "manual_preparation_pending":
            findings.append(
                LearningPathFinding(
                    "learning_path_surface_evidence_invalid",
                    f"{surface_id} evidence_ref must stay manual_preparation_pending in the committed packet",
                )
            )
        if not isinstance(surface.get("public_safe_note"), str) or not surface["public_safe_note"].strip():
            findings.append(
                LearningPathFinding(
                    "learning_path_surface_note_invalid",
                    f"{surface_id} public_safe_note must be a non-empty string",
                )
            )
    return findings


def validate_forbidden_value_patterns(payload: dict[str, Any]) -> list[LearningPathFinding]:
    """Return findings for private, paid, person, account, customer, support, or deployment-shaped values."""

    serialized_payload = json.dumps(payload, sort_keys=True)
    findings: list[LearningPathFinding] = []
    for rule_id, pattern in FORBIDDEN_VALUE_PATTERNS:
        if pattern.search(serialized_payload):
            findings.append(
                LearningPathFinding(
                    "learning_path_forbidden_private_value_pattern",
                    f"learning-path witness contains forbidden value pattern: {rule_id}",
                )
            )
    return findings


def validate_forbidden_promotion_patterns(payload: dict[str, Any]) -> list[LearningPathFinding]:
    """Return findings if the witness drifts into learning-readiness promotion phrases."""

    serialized_payload = json.dumps(payload, sort_keys=True)
    findings: list[LearningPathFinding] = []
    for rule_id, pattern in FORBIDDEN_PROMOTION_PATTERNS:
        if pattern.search(serialized_payload):
            findings.append(
                LearningPathFinding(
                    "learning_path_forbidden_promotion_phrase",
                    f"learning-path witness contains forbidden promotion pattern: {rule_id}",
                )
            )
    return findings


def validate_foundation_learning_path_boundary(
    doc_path: Path = DEFAULT_DOC_PATH,
    packet_path: Path = DEFAULT_PACKET_PATH,
) -> list[LearningPathFinding]:
    """Validate the Foundation Mode learning-path boundary artifacts."""

    doc_text = load_text(doc_path, "learning-path boundary doc")
    packet_payload = load_json_object(packet_path, "learning-path witness packet")
    return [
        *validate_doc_text(doc_text),
        *validate_packet(packet_payload),
    ]


def main(argv: list[str] | None = None) -> int:
    """Validate learning-path boundary artifacts and print deterministic status."""

    parser = argparse.ArgumentParser(description="Validate Foundation Mode learning-path boundary artifacts.")
    parser.add_argument("--doc", type=Path, default=DEFAULT_DOC_PATH)
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET_PATH)
    args = parser.parse_args(argv)

    try:
        findings = validate_foundation_learning_path_boundary(args.doc, args.packet)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"[FAIL] foundation_learning_path_load: {exc}", file=sys.stderr)
        print("STATUS: failed", file=sys.stderr)
        return 1

    if findings:
        for finding in findings:
            print(f"[FAIL] {finding.rule_id}: {finding.message}", file=sys.stderr)
        print("STATUS: failed", file=sys.stderr)
        return 1
    print("[PASS] foundation_learning_path_doc")
    print("[PASS] foundation_learning_path_witness")
    print("STATUS: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
