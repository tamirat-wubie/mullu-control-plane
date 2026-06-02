#!/usr/bin/env python3
"""Validate the Foundation Mode plain-language status boundary.

Purpose: keep non-technical product explanation local and public-safe while
plain-language completeness, comprehension proof, product readiness, capability
availability, real-task execution readiness, customer readiness, public launch,
legal clearance, commercial readiness, paid use, money movement, canonical
docs, external publication, and deployment claims remain blocked.
Governance scope: Foundation Mode, plain-language status surfaces,
plain-English overview posture, private-value exclusion, and readiness blocking.
Dependencies: docs/FOUNDATION_PLAIN_LANGUAGE_STATUS_BOUNDARY.md,
docs/explain/PLAIN_ENGLISH.md, and
examples/foundation_plain_language_status_witness.awaiting_evidence.json.
Invariants:
  - Validation is read-only.
  - The witness records plain-language status preparation only.
  - The plain-English overview separates current Foundation Mode from future
    governed capability.
  - No readiness, customer, legal, paid-use, money-movement, publication, or
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
DEFAULT_DOC_PATH = REPO_ROOT / "docs" / "FOUNDATION_PLAIN_LANGUAGE_STATUS_BOUNDARY.md"
DEFAULT_PACKET_PATH = REPO_ROOT / "examples" / "foundation_plain_language_status_witness.awaiting_evidence.json"
DEFAULT_PLAIN_DOC_PATH = REPO_ROOT / "docs" / "explain" / "PLAIN_ENGLISH.md"

EXPECTED_WITNESS_ID = "foundation_plain_language_status_witness.awaiting_evidence.v1"
EXPECTED_BLOCKED_CLAIMS = (
    "plain-language completeness",
    "non-technical comprehension proof",
    "product readiness",
    "capability availability",
    "real-task execution readiness",
    "customer readiness",
    "public launch copy",
    "legal clearance",
    "commercial readiness",
    "paid-use readiness",
    "money-movement readiness",
    "canonical docs",
    "external publication",
    "deployment readiness",
)
EXPECTED_SURFACES = (
    ("current_posture_summary_questions", "local_draft", "AwaitingEvidence"),
    ("capability_status_separation_questions", "local_draft", "AwaitingEvidence"),
    ("nontechnical_reader_questions", "local_draft", "AwaitingEvidence"),
    ("analogy_safety_questions", "local_draft", "AwaitingEvidence"),
    ("next_step_routing_questions", "local_draft", "AwaitingEvidence"),
    ("glossary_gap_questions", "local_draft", "AwaitingEvidence"),
    ("public_claim_language_questions", "local_draft", "AwaitingEvidence"),
    ("evidence_reference_questions", "local_draft", "AwaitingEvidence"),
    ("limitation_plain_words_questions", "local_draft", "AwaitingEvidence"),
    ("operator_confusion_questions", "local_draft", "AwaitingEvidence"),
)
EXPECTED_ROOT_KEYS = {
    "blocked_claims",
    "canonical_docs_claimed",
    "capability_availability_claimed",
    "commercial_readiness_claimed",
    "customer_readiness_claimed",
    "deployment_allowed",
    "external_publication_allowed",
    "legal_clearance_claimed",
    "money_movement_ready_claimed",
    "next_action",
    "nontechnical_comprehension_proven",
    "paid_use_ready_claimed",
    "plain_language_complete_claimed",
    "plain_language_surfaces",
    "product_readiness_claimed",
    "public_launch_copy_claimed",
    "real_task_execution_ready",
    "schema_version",
    "solver_outcome",
    "status",
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
    "Foundation Plain-Language Status Boundary",
    "Witness packet: [`../examples/foundation_plain_language_status_witness.awaiting_evidence.json`]",
    "Rule: Plain-language status preparation is a local planning boundary, not a",
    "No plain-language completeness, non-technical comprehension proof, product",
    "plain_language_status_boundary_state=AwaitingEvidence",
    "plain_language_complete_claimed=false",
    "nontechnical_comprehension_proven=false",
    "product_readiness_claimed=false",
    "capability_availability_claimed=false",
    "real_task_execution_ready=false",
    "customer_readiness_claimed=false",
    "public_launch_copy_claimed=false",
    "legal_clearance_claimed=false",
    "commercial_readiness_claimed=false",
    "paid_use_ready_claimed=false",
    "money_movement_ready_claimed=false",
    "canonical_docs_claimed=false",
    "external_publication_allowed=false",
    "deployment_allowed=false",
    "python scripts/validate_foundation_plain_language_status_boundary.py",
)
REQUIRED_PLAIN_DOC_PHRASES = (
    "Current foundation posture",
    "[Foundation Mode](../FOUNDATION_MODE.md)",
    "[Foundation Plain-Language Status Boundary](../FOUNDATION_PLAIN_LANGUAGE_STATUS_BOUNDARY.md)",
    "future governed",
    "The safe work now is local proof",
    "Nothing on this page claims public launch, customer access, legal clearance,",
    "Those are product-direction examples, not current customer access claims.",
    "Foundation Mode keeps them local until the required witnesses exist.",
)
FORBIDDEN_VALUE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("url_value", re.compile(r"https?://", re.IGNORECASE)),
    ("email_value", re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)),
    ("private_path", re.compile(r"\b[A-Za-z]:[\\/]|\\\\", re.IGNORECASE)),
    ("account_assignment", re.compile(r"\b(?:account|tenant|provider|project)[_ -]?(?:id|ref|target|value)\s*=", re.IGNORECASE)),
    ("secret_assignment", re.compile(r"\b(?:password|secret|token|api[_ -]?key|credential)\s*=", re.IGNORECASE)),
    ("private_key_material", re.compile(r"BEGIN [A-Z ]*PRIVATE KEY")),
    ("source_control_assignment", re.compile(r"\b(?:branch|commit|pull[_ -]?request|release)[_ -]?(?:id|ref|target|value)\s*=", re.IGNORECASE)),
    ("launch_target_assignment", re.compile(r"\b(?:launch|publish|site|domain)[_ -]?(?:url|target|ref|value)\s*=", re.IGNORECASE)),
    ("customer_assignment", re.compile(r"\b(?:customer|pilot|participant|waitlist|lead)[_ -]?(?:id|email|target|ref|value)\s*=", re.IGNORECASE)),
    ("money_assignment", re.compile(r"\b(?:payment|invoice|money|budget|billing)[_ -]?(?:id|amount|target|value|status)\s*=", re.IGNORECASE)),
    ("deployment_assignment", re.compile(r"\b(?:deploy|endpoint|runtime|cluster|production)[_ -]?(?:url|target|id|ref|value)\s*=", re.IGNORECASE)),
)
FORBIDDEN_PROMOTION_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("plain_language_complete", re.compile(r"\bplain[- ]language\s+(?:status\s+)?(?:is\s+)?complete\b", re.IGNORECASE)),
    ("comprehension_proven", re.compile(r"\bnon[- ]technical\s+comprehension\s+(?:is\s+)?proven\b", re.IGNORECASE)),
    ("product_ready", re.compile(r"\bproduct\s+(?:is\s+)?ready\b", re.IGNORECASE)),
    ("capability_available", re.compile(r"\bcapabilit(?:y|ies)\s+(?:is|are)\s+available\b", re.IGNORECASE)),
    ("real_task_ready", re.compile(r"\breal[- ]task\s+execution\s+(?:is\s+)?ready\b", re.IGNORECASE)),
    ("customer_ready", re.compile(r"\bcustomer\s+(?:access\s+)?(?:is\s+)?ready\b", re.IGNORECASE)),
    ("public_launch_ready", re.compile(r"\bpublic\s+launch\s+(?:is\s+)?ready\b", re.IGNORECASE)),
    ("legally_cleared", re.compile(r"\b(?:is|are)\s+legally\s+cleared\b|\blegal\s+clearance\s+(?:is\s+)?granted\b", re.IGNORECASE)),
    ("commercial_ready", re.compile(r"\b(?:is|are)\s+commercial(?:ly)?[- ]ready\b", re.IGNORECASE)),
    ("paid_use_ready", re.compile(r"\bpaid[- ]use\s+is\s+ready\b", re.IGNORECASE)),
    ("money_movement_ready", re.compile(r"\bmoney\s+movement\s+(?:is\s+)?ready\b", re.IGNORECASE)),
    ("docs_canonical", re.compile(r"\bdocs\s+are\s+canonical\b", re.IGNORECASE)),
    ("externally_published", re.compile(r"\b(?:is|are)\s+externally\s+published\b", re.IGNORECASE)),
    ("deployment_ready", re.compile(r"\bdeployment\s+is\s+ready\b", re.IGNORECASE)),
    ("production_live", re.compile(r"\bproduction\s+(?:runtime\s+)?(?:is\s+)?live\b", re.IGNORECASE)),
)


@dataclass(frozen=True, slots=True)
class PlainLanguageStatusFinding:
    """One deterministic plain-language status validation finding."""

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


def validate_doc_text(text: str) -> list[PlainLanguageStatusFinding]:
    """Return findings for missing plain-language boundary anchors."""

    findings: list[PlainLanguageStatusFinding] = []
    for phrase in REQUIRED_DOC_PHRASES:
        if phrase not in text:
            findings.append(
                PlainLanguageStatusFinding(
                    "foundation_plain_language_status_doc_phrase_missing",
                    f"plain-language status boundary doc missing required phrase: {phrase}",
                )
            )
    findings.extend(validate_forbidden_promotion_text(text, "plain_language_status_doc"))
    return findings


def validate_plain_overview_text(text: str) -> list[PlainLanguageStatusFinding]:
    """Return findings for plain-English overview drift."""

    findings: list[PlainLanguageStatusFinding] = []
    for phrase in REQUIRED_PLAIN_DOC_PHRASES:
        if phrase not in text:
            findings.append(
                PlainLanguageStatusFinding(
                    "plain_english_overview_phrase_missing",
                    f"plain-English overview missing required phrase: {phrase}",
                )
            )
    findings.extend(validate_forbidden_promotion_text(text, "plain_english_overview"))
    return findings


def validate_packet(payload: dict[str, Any]) -> list[PlainLanguageStatusFinding]:
    """Return findings for plain-language status witness drift."""

    findings: list[PlainLanguageStatusFinding] = []
    findings.extend(validate_root_contract(payload))
    findings.extend(validate_plain_language_surfaces(payload.get("plain_language_surfaces")))
    findings.extend(validate_forbidden_value_patterns(payload))
    findings.extend(validate_forbidden_promotion_text(json.dumps(payload, sort_keys=True), "plain_language_status_witness"))
    return findings


def validate_root_contract(payload: dict[str, Any]) -> list[PlainLanguageStatusFinding]:
    """Return findings for root-level plain-language status witness drift."""

    findings: list[PlainLanguageStatusFinding] = []
    if set(payload) != EXPECTED_ROOT_KEYS:
        findings.append(
            PlainLanguageStatusFinding(
                "plain_language_status_root_keys_invalid",
                f"root keys must be: {', '.join(sorted(EXPECTED_ROOT_KEYS))}",
            )
        )
    expected_values = {
        "witness_id": EXPECTED_WITNESS_ID,
        "schema_version": 1,
        "status": "AwaitingEvidence",
        "solver_outcome": "AwaitingEvidence",
        "plain_language_complete_claimed": False,
        "nontechnical_comprehension_proven": False,
        "product_readiness_claimed": False,
        "capability_availability_claimed": False,
        "real_task_execution_ready": False,
        "customer_readiness_claimed": False,
        "public_launch_copy_claimed": False,
        "legal_clearance_claimed": False,
        "commercial_readiness_claimed": False,
        "paid_use_ready_claimed": False,
        "money_movement_ready_claimed": False,
        "canonical_docs_claimed": False,
        "external_publication_allowed": False,
        "deployment_allowed": False,
    }
    for key, expected_value in expected_values.items():
        if payload.get(key) != expected_value:
            findings.append(
                PlainLanguageStatusFinding(
                    "plain_language_status_root_value_invalid",
                    f"{key} must be {expected_value!r}",
                )
            )
    if tuple(payload.get("blocked_claims") or ()) != EXPECTED_BLOCKED_CLAIMS:
        findings.append(
            PlainLanguageStatusFinding(
                "plain_language_status_blocked_claims_invalid",
                f"blocked_claims must be: {', '.join(EXPECTED_BLOCKED_CLAIMS)}",
            )
        )
    next_action = payload.get("next_action")
    if not isinstance(next_action, str) or "continue plain-language status drafting" not in next_action:
        findings.append(
            PlainLanguageStatusFinding(
                "plain_language_status_next_action_invalid",
                "next_action must preserve local plain-language status drafting",
            )
        )
    return findings


def validate_plain_language_surfaces(plain_language_surfaces: object) -> list[PlainLanguageStatusFinding]:
    """Return findings for plain-language surface drift."""

    findings: list[PlainLanguageStatusFinding] = []
    if not isinstance(plain_language_surfaces, list) or not all(
        isinstance(surface, dict) for surface in plain_language_surfaces
    ):
        return [
            PlainLanguageStatusFinding(
                "plain_language_status_surfaces_invalid",
                "plain_language_surfaces must be a list of objects",
            )
        ]
    observed_surfaces = tuple(
        (surface.get("surface_id"), surface.get("surface_type"), surface.get("state"))
        for surface in plain_language_surfaces
    )
    if observed_surfaces != EXPECTED_SURFACES:
        findings.append(
            PlainLanguageStatusFinding(
                "plain_language_status_surface_inventory_invalid",
                "plain-language surface inventory does not match the Foundation Mode set",
            )
        )
    surface_ids = [surface.get("surface_id") for surface in plain_language_surfaces]
    if len(set(surface_ids)) != len(surface_ids):
        findings.append(PlainLanguageStatusFinding("plain_language_status_surface_duplicate", "surface ids must be unique"))
    for surface in plain_language_surfaces:
        surface_id = str(surface.get("surface_id", "<missing>"))
        if set(surface) != EXPECTED_SURFACE_KEYS:
            findings.append(
                PlainLanguageStatusFinding(
                    "plain_language_status_surface_keys_invalid",
                    f"{surface_id} surface keys must be: {', '.join(sorted(EXPECTED_SURFACE_KEYS))}",
                )
            )
        if surface.get("state") != "AwaitingEvidence":
            findings.append(
                PlainLanguageStatusFinding(
                    "plain_language_status_surface_state_invalid",
                    f"{surface_id} state must be AwaitingEvidence",
                )
            )
        if surface.get("evidence_ref") != "manual_preparation_pending":
            findings.append(
                PlainLanguageStatusFinding(
                    "plain_language_status_surface_evidence_invalid",
                    f"{surface_id} evidence_ref must stay manual_preparation_pending in the committed packet",
                )
            )
        if not isinstance(surface.get("public_safe_note"), str) or not surface["public_safe_note"].strip():
            findings.append(
                PlainLanguageStatusFinding(
                    "plain_language_status_surface_note_invalid",
                    f"{surface_id} public_safe_note must be a non-empty string",
                )
            )
    return findings


def validate_forbidden_value_patterns(payload: dict[str, Any]) -> list[PlainLanguageStatusFinding]:
    """Return findings for private, customer, money, source-control, or deployment-shaped values."""

    serialized_payload = json.dumps(payload, sort_keys=True)
    findings: list[PlainLanguageStatusFinding] = []
    for rule_id, pattern in FORBIDDEN_VALUE_PATTERNS:
        if pattern.search(serialized_payload):
            findings.append(
                PlainLanguageStatusFinding(
                    "plain_language_status_forbidden_private_value_pattern",
                    f"plain-language status witness contains forbidden value pattern: {rule_id}",
                )
            )
    return findings


def validate_forbidden_promotion_text(text: str, source_label: str) -> list[PlainLanguageStatusFinding]:
    """Return findings if text drifts into readiness or external-publication claims."""

    findings: list[PlainLanguageStatusFinding] = []
    for rule_id, pattern in FORBIDDEN_PROMOTION_PATTERNS:
        if pattern.search(text):
            findings.append(
                PlainLanguageStatusFinding(
                    "plain_language_status_forbidden_promotion_phrase",
                    f"{source_label} contains forbidden promotion pattern: {rule_id}",
                )
            )
    return findings


def validate_foundation_plain_language_status_boundary(
    doc_path: Path = DEFAULT_DOC_PATH,
    packet_path: Path = DEFAULT_PACKET_PATH,
    plain_doc_path: Path = DEFAULT_PLAIN_DOC_PATH,
) -> list[PlainLanguageStatusFinding]:
    """Validate the Foundation Mode plain-language status boundary artifacts."""

    doc_text = load_text(doc_path, "plain-language status boundary doc")
    packet_payload = load_json_object(packet_path, "plain-language status witness packet")
    plain_doc_text = load_text(plain_doc_path, "plain-English overview")
    return [
        *validate_doc_text(doc_text),
        *validate_packet(packet_payload),
        *validate_plain_overview_text(plain_doc_text),
    ]


def main(argv: list[str] | None = None) -> int:
    """Validate plain-language status artifacts and print deterministic status."""

    parser = argparse.ArgumentParser(description="Validate Foundation Mode plain-language status artifacts.")
    parser.add_argument("--doc", type=Path, default=DEFAULT_DOC_PATH)
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET_PATH)
    parser.add_argument("--plain-doc", type=Path, default=DEFAULT_PLAIN_DOC_PATH)
    args = parser.parse_args(argv)

    try:
        findings = validate_foundation_plain_language_status_boundary(args.doc, args.packet, args.plain_doc)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"[FAIL] foundation_plain_language_status_load: {exc}", file=sys.stderr)
        print("STATUS: failed", file=sys.stderr)
        return 1

    if findings:
        for finding in findings:
            print(f"[FAIL] {finding.rule_id}: {finding.message}", file=sys.stderr)
        print("STATUS: failed", file=sys.stderr)
        return 1
    print("[PASS] foundation_plain_language_status_doc")
    print("[PASS] foundation_plain_language_status_witness")
    print("[PASS] foundation_plain_english_overview")
    print("STATUS: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
