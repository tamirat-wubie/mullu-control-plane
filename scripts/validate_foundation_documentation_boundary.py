#!/usr/bin/env python3
"""Validate the Foundation Mode documentation boundary.

Purpose: keep documentation preparation local and public-safe while
documentation-complete, canonical-docs, public-launch, customer-readiness,
deployment-readiness, legal-clearance, commercial-readiness, private-fact,
external-publication, and deployment claims remain blocked.
Governance scope: Foundation Mode, documentation posture, source-of-truth map,
plain-language status, public-copy alignment, evidence indexing,
private-value exclusion, and deployment blocking.
Dependencies: docs/FOUNDATION_DOCUMENTATION_BOUNDARY.md and
examples/foundation_documentation_witness.awaiting_evidence.json.
Invariants:
  - Validation is read-only.
  - The witness records documentation preparation only.
  - No documentation completeness, canonical-docs, public-launch,
    customer-readiness, deployment-readiness, legal-clearance,
    commercial-readiness, private-fact, external-publication, or deployment
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
DEFAULT_DOC_PATH = REPO_ROOT / "docs" / "FOUNDATION_DOCUMENTATION_BOUNDARY.md"
DEFAULT_PACKET_PATH = REPO_ROOT / "examples" / "foundation_documentation_witness.awaiting_evidence.json"

EXPECTED_WITNESS_ID = "foundation_documentation_witness.awaiting_evidence.v1"
EXPECTED_BLOCKED_CLAIMS = (
    "documentation completeness",
    "canonical docs",
    "public launch copy",
    "customer-ready copy",
    "deployment readiness",
    "legal clearance",
    "commercial readiness",
    "private fact recording",
    "external publication",
    "deployment readiness",
)
EXPECTED_SURFACES = (
    ("source_of_truth_map", "local_draft", "AwaitingEvidence"),
    ("plain_language_status", "local_draft", "AwaitingEvidence"),
    ("glossary_questions", "local_draft", "AwaitingEvidence"),
    ("prerequisite_cross_links", "local_draft", "AwaitingEvidence"),
    ("public_copy_alignment", "local_draft", "AwaitingEvidence"),
    ("evidence_index", "local_draft", "AwaitingEvidence"),
    ("update_cadence", "local_draft", "AwaitingEvidence"),
    ("reviewer_handoff", "local_draft", "AwaitingEvidence"),
)
EXPECTED_ROOT_KEYS = {
    "blocked_claims",
    "canonical_docs_claimed",
    "commercial_readiness_claimed",
    "customer_ready_copy_claimed",
    "deployment_allowed",
    "deployment_readiness_claimed",
    "documentation_complete_claimed",
    "documentation_surfaces",
    "external_publication_allowed",
    "legal_clearance_claimed",
    "next_action",
    "private_fact_recording_allowed",
    "public_launch_copy_claimed",
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
    "Foundation Documentation Boundary",
    "Witness packet: [`../examples/foundation_documentation_witness.awaiting_evidence.json`]",
    "Rule: Documentation preparation is a local planning boundary, not a readiness certificate.",
    "No documentation completeness claim, canonical-docs claim, public-launch copy",
    "documentation_boundary_state=AwaitingEvidence",
    "documentation_complete_claimed=false",
    "canonical_docs_claimed=false",
    "public_launch_copy_claimed=false",
    "external_publication_allowed=false",
    "deployment_allowed=false",
    "python scripts/validate_foundation_documentation_boundary.py",
)
FORBIDDEN_VALUE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("url_value", re.compile(r"https?://", re.IGNORECASE)),
    ("email_value", re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)),
    ("private_path", re.compile(r"\b[A-Za-z]:[\\/]|\\\\", re.IGNORECASE)),
    ("account_assignment", re.compile(r"\b(?:account|tenant|provider|project)[_ -]?(?:id|ref|target|value)\s*=", re.IGNORECASE)),
    ("secret_assignment", re.compile(r"\b(?:password|secret|token|api[_ -]?key)\s*=", re.IGNORECASE)),
    ("private_key_material", re.compile(r"BEGIN [A-Z ]*PRIVATE KEY")),
    ("launch_target_assignment", re.compile(r"\b(?:launch|publish|site|domain)[_ -]?(?:url|target|ref|value)\s*=", re.IGNORECASE)),
    ("customer_target_assignment", re.compile(r"\b(?:customer|pilot|waitlist|lead)[_ -]?(?:id|email|target|ref|value)\s*=", re.IGNORECASE)),
    ("deployment_target_assignment", re.compile(r"\b(?:deploy|endpoint|runtime|cluster)[_ -]?(?:url|target|id|ref|value)\s*=", re.IGNORECASE)),
)
FORBIDDEN_PROMOTION_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("documentation_complete", re.compile(r"\bdocumentation\s+(?:is\s+)?complete\b", re.IGNORECASE)),
    ("docs_canonical", re.compile(r"\bdocs\s+(?:are\s+)?canonical\b", re.IGNORECASE)),
    ("launch_copy_ready", re.compile(r"\b(?:launch|public)\s+copy\s+(?:is\s+)?ready\b", re.IGNORECASE)),
    ("customer_ready", re.compile(r"\bcustomer\s+(?:is\s+)?ready\b", re.IGNORECASE)),
    ("deployment_ready", re.compile(r"\bdeployment[- ]ready\b", re.IGNORECASE)),
    ("legally_cleared", re.compile(r"\blegally\s+cleared\b", re.IGNORECASE)),
    ("commercial_ready", re.compile(r"\bcommercial(?:ly)?[- ]ready\b", re.IGNORECASE)),
    ("externally_published", re.compile(r"\bexternally\s+published\b", re.IGNORECASE)),
)


@dataclass(frozen=True, slots=True)
class DocumentationFinding:
    """One deterministic documentation boundary validation finding."""

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


def validate_doc_text(text: str) -> list[DocumentationFinding]:
    """Return findings for missing documentation-boundary anchors."""

    findings: list[DocumentationFinding] = []
    for phrase in REQUIRED_DOC_PHRASES:
        if phrase not in text:
            findings.append(
                DocumentationFinding(
                    "foundation_documentation_doc_phrase_missing",
                    f"documentation boundary doc missing required phrase: {phrase}",
                )
            )
    return findings


def validate_packet(payload: dict[str, Any]) -> list[DocumentationFinding]:
    """Return findings for documentation witness drift."""

    findings: list[DocumentationFinding] = []
    findings.extend(validate_root_contract(payload))
    findings.extend(validate_documentation_surfaces(payload.get("documentation_surfaces")))
    findings.extend(validate_forbidden_value_patterns(payload))
    findings.extend(validate_forbidden_promotion_patterns(payload))
    return findings


def validate_root_contract(payload: dict[str, Any]) -> list[DocumentationFinding]:
    """Return findings for root-level documentation witness drift."""

    findings: list[DocumentationFinding] = []
    if set(payload) != EXPECTED_ROOT_KEYS:
        findings.append(
            DocumentationFinding(
                "documentation_root_keys_invalid",
                f"root keys must be: {', '.join(sorted(EXPECTED_ROOT_KEYS))}",
            )
        )
    expected_values = {
        "witness_id": EXPECTED_WITNESS_ID,
        "schema_version": 1,
        "status": "AwaitingEvidence",
        "solver_outcome": "AwaitingEvidence",
        "documentation_complete_claimed": False,
        "canonical_docs_claimed": False,
        "public_launch_copy_claimed": False,
        "customer_ready_copy_claimed": False,
        "deployment_readiness_claimed": False,
        "legal_clearance_claimed": False,
        "commercial_readiness_claimed": False,
        "private_fact_recording_allowed": False,
        "external_publication_allowed": False,
        "deployment_allowed": False,
    }
    for key, expected_value in expected_values.items():
        if payload.get(key) != expected_value:
            findings.append(
                DocumentationFinding(
                    "documentation_root_value_invalid",
                    f"{key} must be {expected_value!r}",
                )
            )
    if tuple(payload.get("blocked_claims") or ()) != EXPECTED_BLOCKED_CLAIMS:
        findings.append(
            DocumentationFinding(
                "documentation_blocked_claims_invalid",
                f"blocked_claims must be: {', '.join(EXPECTED_BLOCKED_CLAIMS)}",
            )
        )
    next_action = payload.get("next_action")
    if not isinstance(next_action, str) or "do not claim documentation completeness" not in next_action:
        findings.append(
            DocumentationFinding(
                "documentation_next_action_invalid",
                "next_action must preserve the documentation-readiness boundary",
            )
        )
    return findings


def validate_documentation_surfaces(documentation_surfaces: object) -> list[DocumentationFinding]:
    """Return findings for documentation-surface witness drift."""

    findings: list[DocumentationFinding] = []
    if not isinstance(documentation_surfaces, list) or not all(isinstance(surface, dict) for surface in documentation_surfaces):
        return [DocumentationFinding("documentation_surfaces_invalid", "documentation_surfaces must be a list of objects")]
    observed_surfaces = tuple(
        (surface.get("surface_id"), surface.get("surface_type"), surface.get("state"))
        for surface in documentation_surfaces
    )
    if observed_surfaces != EXPECTED_SURFACES:
        findings.append(
            DocumentationFinding(
                "documentation_surface_inventory_invalid",
                "documentation surface inventory does not match the Foundation Mode documentation set",
            )
        )
    surface_ids = [surface.get("surface_id") for surface in documentation_surfaces]
    if len(set(surface_ids)) != len(surface_ids):
        findings.append(DocumentationFinding("documentation_surface_duplicate", "surface ids must be unique"))
    for surface in documentation_surfaces:
        surface_id = str(surface.get("surface_id", "<missing>"))
        if set(surface) != EXPECTED_SURFACE_KEYS:
            findings.append(
                DocumentationFinding(
                    "documentation_surface_keys_invalid",
                    f"{surface_id} surface keys must be: {', '.join(sorted(EXPECTED_SURFACE_KEYS))}",
                )
            )
        if surface.get("state") != "AwaitingEvidence":
            findings.append(
                DocumentationFinding(
                    "documentation_surface_state_invalid",
                    f"{surface_id} state must be AwaitingEvidence",
                )
            )
        if surface.get("evidence_ref") != "manual_preparation_pending":
            findings.append(
                DocumentationFinding(
                    "documentation_surface_evidence_invalid",
                    f"{surface_id} evidence_ref must stay manual_preparation_pending in the committed packet",
                )
            )
        if not isinstance(surface.get("public_safe_note"), str) or not surface["public_safe_note"].strip():
            findings.append(
                DocumentationFinding(
                    "documentation_surface_note_invalid",
                    f"{surface_id} public_safe_note must be a non-empty string",
                )
            )
    return findings


def validate_forbidden_value_patterns(payload: dict[str, Any]) -> list[DocumentationFinding]:
    """Return findings for private, external, or launch-shaped witness values."""

    serialized_payload = json.dumps(payload, sort_keys=True)
    findings: list[DocumentationFinding] = []
    for rule_id, pattern in FORBIDDEN_VALUE_PATTERNS:
        if pattern.search(serialized_payload):
            findings.append(
                DocumentationFinding(
                    "documentation_forbidden_private_value_pattern",
                    f"documentation witness contains forbidden value pattern: {rule_id}",
                )
            )
    return findings


def validate_forbidden_promotion_patterns(payload: dict[str, Any]) -> list[DocumentationFinding]:
    """Return findings if the witness drifts into documentation-readiness claims."""

    serialized_payload = json.dumps(payload, sort_keys=True)
    findings: list[DocumentationFinding] = []
    for rule_id, pattern in FORBIDDEN_PROMOTION_PATTERNS:
        if pattern.search(serialized_payload):
            findings.append(
                DocumentationFinding(
                    "documentation_forbidden_promotion_phrase",
                    f"documentation witness contains forbidden promotion pattern: {rule_id}",
                )
            )
    return findings


def validate_foundation_documentation_boundary(
    doc_path: Path = DEFAULT_DOC_PATH,
    packet_path: Path = DEFAULT_PACKET_PATH,
) -> list[DocumentationFinding]:
    """Validate the Foundation Mode documentation boundary artifacts."""

    doc_text = load_text(doc_path, "documentation boundary doc")
    packet_payload = load_json_object(packet_path, "documentation witness packet")
    return [
        *validate_doc_text(doc_text),
        *validate_packet(packet_payload),
    ]


def main(argv: list[str] | None = None) -> int:
    """Validate documentation boundary artifacts and print deterministic status."""

    parser = argparse.ArgumentParser(description="Validate Foundation Mode documentation boundary artifacts.")
    parser.add_argument("--doc", type=Path, default=DEFAULT_DOC_PATH)
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET_PATH)
    args = parser.parse_args(argv)

    try:
        findings = validate_foundation_documentation_boundary(args.doc, args.packet)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"[FAIL] foundation_documentation_load: {exc}", file=sys.stderr)
        print("STATUS: failed", file=sys.stderr)
        return 1

    if findings:
        for finding in findings:
            print(f"[FAIL] {finding.rule_id}: {finding.message}", file=sys.stderr)
        print("STATUS: failed", file=sys.stderr)
        return 1
    print("[PASS] foundation_documentation_doc")
    print("[PASS] foundation_documentation_witness")
    print("STATUS: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
