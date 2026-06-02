#!/usr/bin/env python3
"""Validate the Foundation Mode research-notebook boundary.

Purpose: keep conceptual research preparation local and public-safe while
patent-protection, trade-secret-protection, scientific-validation,
physical-world-validation, market-validation, customer, publication,
paid-launch, secret-evidence, and deployment claims remain blocked.
Governance scope: Foundation Mode, concept notes, assumption register,
prior-art questions, proof-status mapping, experiment boundary,
authorship-lineage notes, public-claim language, private-value exclusion, and
deployment blocking.
Dependencies: docs/FOUNDATION_RESEARCH_NOTEBOOK_BOUNDARY.md and
examples/foundation_research_notebook_witness.awaiting_evidence.json.
Invariants:
  - Validation is read-only.
  - The witness records research-notebook preparation only.
  - No patent-protection, trade-secret-protection, scientific-validation,
    physical-world-validation, market-validation, customer, external
    publication, paid-launch, secret-evidence, or deployment claim is allowed.
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
DEFAULT_DOC_PATH = REPO_ROOT / "docs" / "FOUNDATION_RESEARCH_NOTEBOOK_BOUNDARY.md"
DEFAULT_PACKET_PATH = REPO_ROOT / "examples" / "foundation_research_notebook_witness.awaiting_evidence.json"

EXPECTED_WITNESS_ID = "foundation_research_notebook_witness.awaiting_evidence.v1"
EXPECTED_BLOCKED_CLAIMS = (
    "patent protection",
    "trade-secret protection",
    "scientific validation",
    "physical-world validation",
    "market validation",
    "customer claim",
    "external publication",
    "paid launch",
    "secret evidence",
    "deployment readiness",
)
EXPECTED_SURFACES = (
    ("concept_inventory", "local_draft", "AwaitingEvidence"),
    ("assumption_register", "local_draft", "AwaitingEvidence"),
    ("prior_art_question_list", "local_draft", "AwaitingEvidence"),
    ("proof_status_map", "local_draft", "AwaitingEvidence"),
    ("experiment_boundary", "local_draft", "AwaitingEvidence"),
    ("evidence_promotion_questions", "local_draft", "AwaitingEvidence"),
    ("authorship_lineage_notes", "local_draft", "AwaitingEvidence"),
    ("public_claim_language", "local_draft", "AwaitingEvidence"),
)
EXPECTED_ROOT_KEYS = {
    "blocked_claims",
    "customer_claim_allowed",
    "deployment_allowed",
    "external_publication_allowed",
    "market_validation_claimed",
    "next_action",
    "paid_launch_allowed",
    "patent_protection_claimed",
    "physical_world_validation_claimed",
    "research_surfaces",
    "schema_version",
    "scientific_validation_claimed",
    "secret_evidence_claimed",
    "solver_outcome",
    "status",
    "trade_secret_protection_claimed",
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
    "Foundation Research Notebook Boundary",
    "Witness packet: [`../examples/foundation_research_notebook_witness.awaiting_evidence.json`]",
    "Rule: Research-notebook preparation is a local planning boundary, not a patent, secrecy, validation, publication, market, or deployment certificate.",
    "No patent protection, trade-secret protection, scientific validation,",
    "research_notebook_boundary_state=AwaitingEvidence",
    "patent_protection_claimed=false",
    "trade_secret_protection_claimed=false",
    "scientific_validation_claimed=false",
    "secret_evidence_claimed=false",
    "deployment_allowed=false",
    "python scripts/validate_foundation_research_notebook_boundary.py",
)
FORBIDDEN_VALUE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("url_value", re.compile(r"https?://", re.IGNORECASE)),
    ("email_value", re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)),
    ("private_path", re.compile(r"\b[A-Za-z]:[\\/]|\\\\", re.IGNORECASE)),
    ("reviewer_assignment", re.compile(r"\b(?:reviewer|attorney|examiner)[_ -]?(?:id|name|email|ref|value)\s*=", re.IGNORECASE)),
    ("provider_assignment", re.compile(r"\b(?:provider|account|tenant|project)[_ -]?(?:id|ref|target|value)\s*=", re.IGNORECASE)),
    ("confidential_assignment", re.compile(r"\b(?:confidential|trade[_ -]?secret|secret[_ -]?evidence)[_ -]?(?:id|ref|value|path)\s*=", re.IGNORECASE)),
    ("patent_filing_assignment", re.compile(r"\b(?:patent|filing|application)[_ -]?(?:id|number|ref|value)\s*=", re.IGNORECASE)),
    ("secret_assignment", re.compile(r"\b(?:password|secret|token|api[_ -]?key)\s*=", re.IGNORECASE)),
    ("private_key_material", re.compile(r"BEGIN [A-Z ]*PRIVATE KEY")),
)
FORBIDDEN_PROMOTION_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("patent_protected", re.compile(r"\bpatent\s+protected\b", re.IGNORECASE)),
    ("trade_secret_protected", re.compile(r"\btrade[- ]secret\s+protected\b", re.IGNORECASE)),
    ("research_validated", re.compile(r"\bresearch\s+(?:is\s+)?validated\b", re.IGNORECASE)),
    ("scientific_validation_complete", re.compile(r"\bscientific\s+validation\s+(?:is\s+)?complete\b", re.IGNORECASE)),
    ("physical_validation_complete", re.compile(r"\bphysical[- ]world\s+validation\s+(?:is\s+)?complete\b", re.IGNORECASE)),
    ("market_validated", re.compile(r"\bmarket\s+(?:is\s+)?validated\b", re.IGNORECASE)),
    ("customer_validated", re.compile(r"\bcustomer\s+(?:is\s+)?validated\b", re.IGNORECASE)),
    ("publication_ready", re.compile(r"\bpublication\s+(?:is\s+)?ready\b", re.IGNORECASE)),
    ("published_externally", re.compile(r"\bpublished\s+externally\b", re.IGNORECASE)),
    ("secret_evidence_exists", re.compile(r"\bsecret\s+evidence\s+(?:exists|is\s+confirmed)\b", re.IGNORECASE)),
    ("deployment_ready", re.compile(r"\bdeployment\s+(?:is\s+)?ready\b", re.IGNORECASE)),
)


@dataclass(frozen=True, slots=True)
class ResearchNotebookFinding:
    """One deterministic research-notebook boundary validation finding."""

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


def validate_doc_text(text: str) -> list[ResearchNotebookFinding]:
    """Return findings for missing research-notebook documentation anchors."""

    findings: list[ResearchNotebookFinding] = []
    for phrase in REQUIRED_DOC_PHRASES:
        if phrase not in text:
            findings.append(
                ResearchNotebookFinding(
                    "foundation_research_notebook_doc_phrase_missing",
                    f"research-notebook boundary doc missing required phrase: {phrase}",
                )
            )
    return findings


def validate_packet(payload: dict[str, Any]) -> list[ResearchNotebookFinding]:
    """Return findings for research-notebook witness drift."""

    findings: list[ResearchNotebookFinding] = []
    findings.extend(validate_root_contract(payload))
    findings.extend(validate_research_surfaces(payload.get("research_surfaces")))
    findings.extend(validate_forbidden_value_patterns(payload))
    findings.extend(validate_forbidden_promotion_patterns(payload))
    return findings


def validate_root_contract(payload: dict[str, Any]) -> list[ResearchNotebookFinding]:
    """Return findings for root-level research-notebook witness drift."""

    findings: list[ResearchNotebookFinding] = []
    if set(payload) != EXPECTED_ROOT_KEYS:
        findings.append(
            ResearchNotebookFinding(
                "research_notebook_root_keys_invalid",
                f"root keys must be: {', '.join(sorted(EXPECTED_ROOT_KEYS))}",
            )
        )
    expected_values = {
        "witness_id": EXPECTED_WITNESS_ID,
        "schema_version": 1,
        "status": "AwaitingEvidence",
        "solver_outcome": "AwaitingEvidence",
        "patent_protection_claimed": False,
        "trade_secret_protection_claimed": False,
        "scientific_validation_claimed": False,
        "physical_world_validation_claimed": False,
        "market_validation_claimed": False,
        "customer_claim_allowed": False,
        "external_publication_allowed": False,
        "paid_launch_allowed": False,
        "secret_evidence_claimed": False,
        "deployment_allowed": False,
    }
    for key, expected_value in expected_values.items():
        if payload.get(key) != expected_value:
            findings.append(
                ResearchNotebookFinding(
                    "research_notebook_root_value_invalid",
                    f"{key} must be {expected_value!r}",
                )
            )
    if tuple(payload.get("blocked_claims") or ()) != EXPECTED_BLOCKED_CLAIMS:
        findings.append(
            ResearchNotebookFinding(
                "research_notebook_blocked_claims_invalid",
                f"blocked_claims must be: {', '.join(EXPECTED_BLOCKED_CLAIMS)}",
            )
        )
    next_action = payload.get("next_action")
    if not isinstance(next_action, str) or "do not claim patent protection" not in next_action:
        findings.append(
            ResearchNotebookFinding(
                "research_notebook_next_action_invalid",
                "next_action must preserve the research-notebook boundary",
            )
        )
    return findings


def validate_research_surfaces(research_surfaces: object) -> list[ResearchNotebookFinding]:
    """Return findings for research-surface witness drift."""

    findings: list[ResearchNotebookFinding] = []
    if not isinstance(research_surfaces, list) or not all(isinstance(surface, dict) for surface in research_surfaces):
        return [ResearchNotebookFinding("research_notebook_surfaces_invalid", "research_surfaces must be a list of objects")]
    observed_surfaces = tuple(
        (surface.get("surface_id"), surface.get("surface_type"), surface.get("state"))
        for surface in research_surfaces
    )
    if observed_surfaces != EXPECTED_SURFACES:
        findings.append(
            ResearchNotebookFinding(
                "research_notebook_surface_inventory_invalid",
                "research surface inventory does not match the Foundation Mode research set",
            )
        )
    surface_ids = [surface.get("surface_id") for surface in research_surfaces]
    if len(set(surface_ids)) != len(surface_ids):
        findings.append(ResearchNotebookFinding("research_notebook_surface_duplicate", "surface ids must be unique"))
    for surface in research_surfaces:
        surface_id = str(surface.get("surface_id", "<missing>"))
        if set(surface) != EXPECTED_SURFACE_KEYS:
            findings.append(
                ResearchNotebookFinding(
                    "research_notebook_surface_keys_invalid",
                    f"{surface_id} surface keys must be: {', '.join(sorted(EXPECTED_SURFACE_KEYS))}",
                )
            )
        if surface.get("state") != "AwaitingEvidence":
            findings.append(
                ResearchNotebookFinding(
                    "research_notebook_surface_state_invalid",
                    f"{surface_id} state must be AwaitingEvidence",
                )
            )
        if surface.get("evidence_ref") != "manual_preparation_pending":
            findings.append(
                ResearchNotebookFinding(
                    "research_notebook_surface_evidence_invalid",
                    f"{surface_id} evidence_ref must stay manual_preparation_pending in the committed packet",
                )
            )
        if not isinstance(surface.get("public_safe_note"), str) or not surface["public_safe_note"].strip():
            findings.append(
                ResearchNotebookFinding(
                    "research_notebook_surface_note_invalid",
                    f"{surface_id} public_safe_note must be a non-empty string",
                )
            )
    return findings


def validate_forbidden_value_patterns(payload: dict[str, Any]) -> list[ResearchNotebookFinding]:
    """Return findings for private, reviewer, filing, provider, or secret-shaped values."""

    serialized_payload = json.dumps(payload, sort_keys=True)
    findings: list[ResearchNotebookFinding] = []
    for rule_id, pattern in FORBIDDEN_VALUE_PATTERNS:
        if pattern.search(serialized_payload):
            findings.append(
                ResearchNotebookFinding(
                    "research_notebook_forbidden_private_value_pattern",
                    f"research-notebook witness contains forbidden value pattern: {rule_id}",
                )
            )
    return findings


def validate_forbidden_promotion_patterns(payload: dict[str, Any]) -> list[ResearchNotebookFinding]:
    """Return findings if the witness drifts into research-promotion phrases."""

    serialized_payload = json.dumps(payload, sort_keys=True)
    findings: list[ResearchNotebookFinding] = []
    for rule_id, pattern in FORBIDDEN_PROMOTION_PATTERNS:
        if pattern.search(serialized_payload):
            findings.append(
                ResearchNotebookFinding(
                    "research_notebook_forbidden_promotion_phrase",
                    f"research-notebook witness contains forbidden promotion pattern: {rule_id}",
                )
            )
    return findings


def validate_foundation_research_notebook_boundary(
    doc_path: Path = DEFAULT_DOC_PATH,
    packet_path: Path = DEFAULT_PACKET_PATH,
) -> list[ResearchNotebookFinding]:
    """Validate the Foundation Mode research-notebook boundary artifacts."""

    doc_text = load_text(doc_path, "research-notebook boundary doc")
    packet_payload = load_json_object(packet_path, "research-notebook witness packet")
    return [
        *validate_doc_text(doc_text),
        *validate_packet(packet_payload),
    ]


def main(argv: list[str] | None = None) -> int:
    """Validate research-notebook boundary artifacts and print deterministic status."""

    parser = argparse.ArgumentParser(description="Validate Foundation Mode research-notebook boundary artifacts.")
    parser.add_argument("--doc", type=Path, default=DEFAULT_DOC_PATH)
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET_PATH)
    args = parser.parse_args(argv)

    try:
        findings = validate_foundation_research_notebook_boundary(args.doc, args.packet)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"[FAIL] foundation_research_notebook_load: {exc}", file=sys.stderr)
        print("STATUS: failed", file=sys.stderr)
        return 1

    if findings:
        for finding in findings:
            print(f"[FAIL] {finding.rule_id}: {finding.message}", file=sys.stderr)
        print("STATUS: failed", file=sys.stderr)
        return 1
    print("[PASS] foundation_research_notebook_doc")
    print("[PASS] foundation_research_notebook_witness")
    print("STATUS: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
