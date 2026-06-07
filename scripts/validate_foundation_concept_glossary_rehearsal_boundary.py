#!/usr/bin/env python3
"""Validate the Foundation Mode concept glossary rehearsal boundary.

Purpose: keep one local concept glossary rehearsal public-safe while canonical
definition, glossary completeness, concept mastery, technical readiness,
training completion, comprehension proof, public-docs readiness, product
readiness, customer readiness, private-value recording, legal/business action,
spending, money movement, source-control publication, external publication,
and deployment claims remain blocked.
Governance scope: Foundation Mode, local concept glossary rehearsal, term
selection, source-doc reference, plain definition draft, boundary example,
non-goal note, evidence reference, confusion note, cross-link label, validator
pairing, stop-rule rehearsal, private-value exclusion, and external-action
blocking.
Dependencies: docs/FOUNDATION_CONCEPT_GLOSSARY_REHEARSAL_BOUNDARY.md and
examples/foundation_concept_glossary_rehearsal_witness.awaiting_evidence.json.
Invariants:
  - The witness records public-safe concept glossary rehearsal labels only.
  - Every concept glossary rehearsal surface remains AwaitingEvidence.
  - No glossary, mastery, training, comprehension, docs-readiness, product,
    customer, private-value, legal/business, money, source-control,
    publication, or deployment claim is accepted.
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
DEFAULT_DOC_PATH = REPO_ROOT / "docs" / "FOUNDATION_CONCEPT_GLOSSARY_REHEARSAL_BOUNDARY.md"
DEFAULT_PACKET_PATH = REPO_ROOT / "examples" / "foundation_concept_glossary_rehearsal_witness.awaiting_evidence.json"

REQUIRED_ROOT_KEYS = (
    "blocked_claims",
    "canonical_definition_claimed",
    "comprehension_proven",
    "concept_mastery_claimed",
    "customer_readiness_claimed",
    "deferral_labels",
    "deployment_allowed",
    "external_publication_allowed",
    "glossary_complete_claimed",
    "glossary_entry_published",
    "legal_business_action_allowed",
    "money_movement_allowed",
    "next_action",
    "private_value_recording_allowed",
    "product_readiness_claimed",
    "public_docs_readiness_claimed",
    "schema_version",
    "solver_outcome",
    "source_control_publication_allowed",
    "spending_allowed",
    "status",
    "surfaces",
    "technical_readiness_claimed",
    "training_completion_claimed",
    "witness_id",
)
EXPECTED_ROOT_VALUES = {
    "schema_version": "foundation.concept_glossary_rehearsal.v1",
    "witness_id": "foundation_concept_glossary_rehearsal_witness.awaiting_evidence.v1",
    "status": "AwaitingEvidence",
    "solver_outcome": "AwaitingEvidence",
}
FALSE_FLAGS = (
    "canonical_definition_claimed",
    "comprehension_proven",
    "concept_mastery_claimed",
    "customer_readiness_claimed",
    "deployment_allowed",
    "external_publication_allowed",
    "glossary_complete_claimed",
    "glossary_entry_published",
    "legal_business_action_allowed",
    "money_movement_allowed",
    "private_value_recording_allowed",
    "product_readiness_claimed",
    "public_docs_readiness_claimed",
    "source_control_publication_allowed",
    "spending_allowed",
    "technical_readiness_claimed",
    "training_completion_claimed",
)
DEFERRAL_LABELS = (
    "term_selection_rehearsal",
    "source_doc_reference_rehearsal",
    "plain_definition_rehearsal",
    "boundary_example_rehearsal",
    "non_goal_rehearsal",
    "evidence_reference_rehearsal",
    "confusion_note_rehearsal",
    "cross_link_rehearsal",
    "validator_pairing_rehearsal",
    "stop_rule_rehearsal",
)
BLOCKED_CLAIMS = (
    "canonical definition",
    "glossary completeness",
    "concept mastery",
    "technical readiness",
    "training completion",
    "comprehension proof",
    "public docs readiness",
    "product readiness",
    "customer readiness",
    "private value recording",
    "legal/business action",
    "spending",
    "money movement",
    "source-control publication",
    "external publication",
    "deployment readiness",
)
SURFACE_NOTES_BY_ID = {
    "term_selection_rehearsal": "Term selection rehearsal only; concept mastery is not claimed.",
    "source_doc_reference_rehearsal": "Source document reference rehearsal only; private paths and external URLs are not recorded.",
    "plain_definition_rehearsal": "Plain definition rehearsal only; canonical definition is not claimed.",
    "boundary_example_rehearsal": "Boundary example rehearsal only; product behavior is not promised.",
    "non_goal_rehearsal": "Non-goal rehearsal only; limitations remain explicit.",
    "evidence_reference_rehearsal": "Evidence reference rehearsal only; AwaitingEvidence is not promoted to closure.",
    "confusion_note_rehearsal": "Confusion note rehearsal only; private schedule, health, account, and secret values are not recorded.",
    "cross_link_rehearsal": "Cross-link rehearsal only; documentation completeness is not claimed.",
    "validator_pairing_rehearsal": "Validator pairing rehearsal only; training completion and certification are not claimed.",
    "stop_rule_rehearsal": "Stop-rule rehearsal only; publication, source control, legal/business action, spending, customer access, and deployment are not approved.",
}
SURFACE_TYPES_BY_ID = {
    "term_selection_rehearsal": "local_term_label",
    "source_doc_reference_rehearsal": "local_doc_label",
    "plain_definition_rehearsal": "local_definition_label",
    "boundary_example_rehearsal": "local_example_label",
    "non_goal_rehearsal": "local_non_goal_label",
    "evidence_reference_rehearsal": "local_evidence_label",
    "confusion_note_rehearsal": "public_safe_confusion_label",
    "cross_link_rehearsal": "local_link_label",
    "validator_pairing_rehearsal": "local_validator_label",
    "stop_rule_rehearsal": "local_stop_rule_label",
}
REQUIRED_DOC_PHRASES = (
    "Foundation Concept Glossary Rehearsal Boundary",
    "Witness packet: [`../examples/foundation_concept_glossary_rehearsal_witness.awaiting_evidence.json`]",
    "Rule: Concept glossary rehearsal is a local vocabulary clarification packet",
    "No canonical-definition claim, glossary-completeness claim, concept-mastery",
    "concept_glossary_rehearsal_boundary_state=AwaitingEvidence",
    "glossary_entry_published=false",
    "canonical_definition_claimed=false",
    "glossary_complete_claimed=false",
    "concept_mastery_claimed=false",
    "technical_readiness_claimed=false",
    "training_completion_claimed=false",
    "comprehension_proven=false",
    "public_docs_readiness_claimed=false",
    "product_readiness_claimed=false",
    "customer_readiness_claimed=false",
    "private_value_recording_allowed=false",
    "legal_business_action_allowed=false",
    "spending_allowed=false",
    "money_movement_allowed=false",
    "source_control_publication_allowed=false",
    "external_publication_allowed=false",
    "deployment_allowed=false",
    "python scripts/validate_foundation_concept_glossary_rehearsal_boundary.py",
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
            r"\b(?:account|provider|course|subscription|billing|payment|purchase|invoice|"
            r"customer|support|ticket|commit|push|pull[_ -]?request|release|legal|company|"
            r"patent|tax|terms|secret|token|key|endpoint|deploy|deployment|production)\w*\s*=",
            re.IGNORECASE,
        ),
    ),
)
FORBIDDEN_PROMOTION_PATTERNS = (
    ("canonical_definition", re.compile(r"\bcanonical\s+definition\s+(?:is\s+)?(?:ready|complete|approved)\b", re.IGNORECASE)),
    ("glossary_complete", re.compile(r"\bglossary\s+(?:is\s+)?complete\b", re.IGNORECASE)),
    ("concept_mastered", re.compile(r"\bconcept\s+(?:is\s+)?mastered\b", re.IGNORECASE)),
    ("technical_ready", re.compile(r"\btechnical\s+(?:readiness\s+)?(?:is\s+)?ready\b", re.IGNORECASE)),
    ("training_complete", re.compile(r"\btraining\s+(?:is\s+)?complete\b", re.IGNORECASE)),
    ("comprehension_proven", re.compile(r"\bcomprehension\s+(?:is\s+)?proven\b", re.IGNORECASE)),
    ("public_docs_ready", re.compile(r"\bpublic\s+docs\s+(?:are\s+)?ready\b", re.IGNORECASE)),
    ("product_ready", re.compile(r"\bproduct\s+(?:is\s+)?ready\b", re.IGNORECASE)),
    ("customer_ready", re.compile(r"\bcustomer\s+(?:access\s+)?(?:is\s+)?ready\b", re.IGNORECASE)),
    ("published", re.compile(r"\b(?:glossary|docs|entry)\s+(?:is\s+)?published\b", re.IGNORECASE)),
    ("legal_business_ready", re.compile(r"\blegal\s+business\s+(?:is\s+)?ready\b", re.IGNORECASE)),
    ("spending_approved", re.compile(r"\bspending\s+(?:is\s+)?approved\b", re.IGNORECASE)),
    ("source_control_published", re.compile(r"\bsource\s+control\s+(?:is\s+)?published\b", re.IGNORECASE)),
    ("deployment_ready", re.compile(r"\bdeployment\s+(?:is\s+)?ready\b", re.IGNORECASE)),
)


@dataclass(frozen=True, slots=True)
class Finding:
    """One deterministic concept glossary rehearsal validation finding."""

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
    """Return findings for concept glossary rehearsal surface inventory and state drift."""

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
    """Return findings for concept glossary rehearsal packet drift."""

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
    if not isinstance(next_action, str) or "concept glossary rehearsal" not in next_action:
        findings.append(Finding("witness_next_action", "next_action must preserve concept glossary rehearsal"))
    findings.extend(validate_surfaces(payload.get("surfaces")))
    findings.extend(validate_forbidden_text(payload))
    return findings


def validate_artifacts(
    doc_path: Path = DEFAULT_DOC_PATH,
    packet_path: Path = DEFAULT_PACKET_PATH,
) -> list[Finding]:
    """Validate the concept glossary rehearsal doc and witness packet."""

    doc_text = load_text(doc_path, "concept glossary rehearsal doc")
    payload = load_json_object(packet_path, "concept glossary rehearsal witness")
    return [*validate_doc_text(doc_text), *validate_packet(payload)]


def main(argv: list[str] | None = None) -> int:
    """Run the concept glossary rehearsal validator."""

    parser = argparse.ArgumentParser(description="Validate Foundation Mode concept glossary rehearsal artifacts.")
    parser.add_argument("--doc", type=Path, default=DEFAULT_DOC_PATH)
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET_PATH)
    args = parser.parse_args(argv)

    try:
        findings = validate_artifacts(args.doc, args.packet)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"[FAIL] foundation_concept_glossary_rehearsal_load: {exc}", file=sys.stderr)
        print("STATUS: failed", file=sys.stderr)
        return 1
    if findings:
        for finding in findings:
            print(f"[FAIL] {finding.rule_id}: {finding.message}", file=sys.stderr)
        print("STATUS: failed", file=sys.stderr)
        return 1

    print("[PASS] foundation_concept_glossary_rehearsal_doc")
    print("[PASS] foundation_concept_glossary_rehearsal_witness")
    print("STATUS: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
