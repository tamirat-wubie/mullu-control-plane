#!/usr/bin/env python3
"""Validate the Foundation Mode decision-journal boundary.

Purpose: keep decision-journal preparation local and public-safe while
decision-execution, irreversible-action, roadmap-commitment, deadline-promise,
authority-delegation, customer-commitment, legal-authority, company-action,
patent-filing, spending, external-publication, and deployment claims remain
blocked.
Governance scope: Foundation Mode, decision context, assumption snapshot,
option set, constraint check, evidence references, risk stop rule, review
cadence, next-action selection, private-value exclusion, and external-commitment
blocking.
Dependencies: docs/FOUNDATION_DECISION_JOURNAL_BOUNDARY.md and
examples/foundation_decision_journal_witness.awaiting_evidence.json.
Invariants:
  - Validation is read-only.
  - The witness records decision-journal preparation only.
  - No decision-execution, irreversible-action, roadmap-commitment,
    deadline-promise, authority-delegation, customer-commitment,
    legal-authority, company-action, patent-filing, spending,
    external-publication, or deployment claim is allowed.
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
DEFAULT_DOC_PATH = REPO_ROOT / "docs" / "FOUNDATION_DECISION_JOURNAL_BOUNDARY.md"
DEFAULT_PACKET_PATH = REPO_ROOT / "examples" / "foundation_decision_journal_witness.awaiting_evidence.json"

EXPECTED_WITNESS_ID = "foundation_decision_journal_witness.awaiting_evidence.v1"
EXPECTED_BLOCKED_CLAIMS = (
    "decision execution",
    "irreversible action",
    "roadmap commitment",
    "deadline promise",
    "authority delegation",
    "customer commitment",
    "legal authority",
    "company action",
    "patent filing",
    "spending",
    "external publication",
    "deployment readiness",
)
EXPECTED_SURFACES = (
    ("decision_context", "local_draft", "AwaitingEvidence"),
    ("assumption_snapshot", "local_draft", "AwaitingEvidence"),
    ("option_set", "local_draft", "AwaitingEvidence"),
    ("constraint_check", "local_draft", "AwaitingEvidence"),
    ("evidence_references", "local_draft", "AwaitingEvidence"),
    ("risk_stop_rule", "local_draft", "AwaitingEvidence"),
    ("review_cadence", "local_draft", "AwaitingEvidence"),
    ("next_action_selection", "local_draft", "AwaitingEvidence"),
)
EXPECTED_ROOT_KEYS = {
    "authority_delegation_claimed",
    "blocked_claims",
    "company_action_allowed",
    "customer_commitment_claimed",
    "deadline_promise_claimed",
    "decision_execution_allowed",
    "decision_surfaces",
    "deployment_allowed",
    "external_publication_allowed",
    "irreversible_action_allowed",
    "legal_authority_claimed",
    "next_action",
    "patent_filing_allowed",
    "roadmap_commitment_claimed",
    "schema_version",
    "solver_outcome",
    "spending_allowed",
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
    "Foundation Decision Journal Boundary",
    "Witness packet: [`../examples/foundation_decision_journal_witness.awaiting_evidence.json`]",
    "Rule: Decision-journal preparation is a local planning boundary, not a decision-execution, commitment, authority, legal, company, patent, spending, publication, or deployment certificate.",
    "No decision execution, irreversible action, roadmap commitment, deadline",
    "decision_journal_boundary_state=AwaitingEvidence",
    "decision_execution_allowed=false",
    "irreversible_action_allowed=false",
    "roadmap_commitment_claimed=false",
    "deadline_promise_claimed=false",
    "spending_allowed=false",
    "deployment_allowed=false",
    "python scripts/validate_foundation_decision_journal_boundary.py",
)
FORBIDDEN_VALUE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("url_value", re.compile(r"https?://", re.IGNORECASE)),
    ("email_value", re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)),
    ("private_path", re.compile(r"\b[A-Za-z]:[\\/]|\\\\", re.IGNORECASE)),
    ("private_schedule_assignment", re.compile(r"\b(?:private[_ -]?schedule|private[_ -]?health|deadline[_ -]?at|delivery[_ -]?date)\s*=", re.IGNORECASE)),
    ("provider_assignment", re.compile(r"\b(?:provider|account|tenant|project)[_ -]?(?:id|ref|target|value)\s*=", re.IGNORECASE)),
    ("reviewer_assignment", re.compile(r"\b(?:reviewer|attorney|auditor)[_ -]?(?:id|name|email|ref|value)\s*=", re.IGNORECASE)),
    ("customer_assignment", re.compile(r"\b(?:customer|pilot|user)[_ -]?(?:id|name|email|ref|value)\s*=", re.IGNORECASE)),
    ("secret_assignment", re.compile(r"\b(?:password|secret|token|api[_ -]?key)\s*=", re.IGNORECASE)),
    ("private_key_material", re.compile(r"BEGIN [A-Z ]*PRIVATE KEY")),
)
FORBIDDEN_PROMOTION_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("decision_executed", re.compile(r"\bdecision\s+(?:is\s+)?executed\b", re.IGNORECASE)),
    ("irreversible_action_approved", re.compile(r"\birreversible\s+action\s+(?:is\s+)?approved\b", re.IGNORECASE)),
    ("roadmap_committed", re.compile(r"\broadmap\s+(?:is\s+)?committed\b", re.IGNORECASE)),
    ("deadline_promised", re.compile(r"\bdeadline\s+(?:is\s+)?promised\b", re.IGNORECASE)),
    ("authority_delegated", re.compile(r"\bauthority\s+(?:is\s+)?delegated\b", re.IGNORECASE)),
    ("customer_committed", re.compile(r"\bcustomer\s+commitment\s+(?:is\s+)?made\b", re.IGNORECASE)),
    ("legal_authority_granted", re.compile(r"\blegal\s+authority\s+(?:is\s+)?granted\b", re.IGNORECASE)),
    ("company_action_authorized", re.compile(r"\bcompany\s+action\s+(?:is\s+)?authorized\b", re.IGNORECASE)),
    ("patent_filing_ready", re.compile(r"\bpatent\s+filing\s+(?:is\s+)?ready\b", re.IGNORECASE)),
    ("spending_approved", re.compile(r"\bspending\s+(?:is\s+)?approved\b", re.IGNORECASE)),
    ("published_externally", re.compile(r"\bpublished\s+externally\b", re.IGNORECASE)),
    ("deployment_ready", re.compile(r"\bdeployment\s+(?:is\s+)?ready\b", re.IGNORECASE)),
)


@dataclass(frozen=True, slots=True)
class DecisionJournalFinding:
    """One deterministic decision-journal boundary validation finding."""

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
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{label} must be a JSON object")
    return payload


def validate_doc_text(text: str) -> list[DecisionJournalFinding]:
    """Return findings for missing decision-journal documentation anchors."""

    findings: list[DecisionJournalFinding] = []
    for phrase in REQUIRED_DOC_PHRASES:
        if phrase not in text:
            findings.append(
                DecisionJournalFinding(
                    "foundation_decision_journal_doc_phrase_missing",
                    f"decision-journal boundary doc missing required phrase: {phrase}",
                )
            )
    return findings


def validate_packet(payload: dict[str, Any]) -> list[DecisionJournalFinding]:
    """Return findings for decision-journal witness drift."""

    findings: list[DecisionJournalFinding] = []
    findings.extend(validate_root_contract(payload))
    findings.extend(validate_decision_surfaces(payload.get("decision_surfaces")))
    findings.extend(validate_forbidden_value_patterns(payload))
    findings.extend(validate_forbidden_promotion_patterns(payload))
    return findings


def validate_root_contract(payload: dict[str, Any]) -> list[DecisionJournalFinding]:
    """Return findings for root-level decision-journal witness drift."""

    findings: list[DecisionJournalFinding] = []
    if set(payload) != EXPECTED_ROOT_KEYS:
        findings.append(
            DecisionJournalFinding(
                "decision_journal_root_keys_invalid",
                f"root keys must be: {', '.join(sorted(EXPECTED_ROOT_KEYS))}",
            )
        )
    expected_values = {
        "witness_id": EXPECTED_WITNESS_ID,
        "schema_version": 1,
        "status": "AwaitingEvidence",
        "solver_outcome": "AwaitingEvidence",
        "decision_execution_allowed": False,
        "irreversible_action_allowed": False,
        "roadmap_commitment_claimed": False,
        "deadline_promise_claimed": False,
        "authority_delegation_claimed": False,
        "customer_commitment_claimed": False,
        "legal_authority_claimed": False,
        "company_action_allowed": False,
        "patent_filing_allowed": False,
        "spending_allowed": False,
        "external_publication_allowed": False,
        "deployment_allowed": False,
    }
    for key, expected_value in expected_values.items():
        if payload.get(key) != expected_value:
            findings.append(
                DecisionJournalFinding(
                    "decision_journal_root_value_invalid",
                    f"{key} must be {expected_value!r}",
                )
            )
    if tuple(payload.get("blocked_claims") or ()) != EXPECTED_BLOCKED_CLAIMS:
        findings.append(
            DecisionJournalFinding(
                "decision_journal_blocked_claims_invalid",
                f"blocked_claims must be: {', '.join(EXPECTED_BLOCKED_CLAIMS)}",
            )
        )
    next_action = payload.get("next_action")
    if not isinstance(next_action, str) or "do not execute decisions" not in next_action:
        findings.append(
            DecisionJournalFinding(
                "decision_journal_next_action_invalid",
                "next_action must preserve the decision-journal boundary",
            )
        )
    return findings


def validate_decision_surfaces(decision_surfaces: object) -> list[DecisionJournalFinding]:
    """Return findings for decision-journal surface drift."""

    findings: list[DecisionJournalFinding] = []
    if not isinstance(decision_surfaces, list) or not all(isinstance(surface, dict) for surface in decision_surfaces):
        return [DecisionJournalFinding("decision_journal_surfaces_invalid", "decision_surfaces must be a list of objects")]
    observed_surfaces = tuple(
        (surface.get("surface_id"), surface.get("surface_type"), surface.get("state"))
        for surface in decision_surfaces
    )
    if observed_surfaces != EXPECTED_SURFACES:
        findings.append(
            DecisionJournalFinding(
                "decision_journal_surface_inventory_invalid",
                "decision surface inventory does not match the Foundation Mode decision set",
            )
        )
    surface_ids = [surface.get("surface_id") for surface in decision_surfaces]
    if len(set(surface_ids)) != len(surface_ids):
        findings.append(DecisionJournalFinding("decision_journal_surface_duplicate", "surface ids must be unique"))
    for surface in decision_surfaces:
        surface_id = str(surface.get("surface_id", "<missing>"))
        if set(surface) != EXPECTED_SURFACE_KEYS:
            findings.append(
                DecisionJournalFinding(
                    "decision_journal_surface_keys_invalid",
                    f"{surface_id} surface keys must be: {', '.join(sorted(EXPECTED_SURFACE_KEYS))}",
                )
            )
        if surface.get("state") != "AwaitingEvidence":
            findings.append(
                DecisionJournalFinding(
                    "decision_journal_surface_state_invalid",
                    f"{surface_id} state must be AwaitingEvidence",
                )
            )
        if surface.get("evidence_ref") != "manual_preparation_pending":
            findings.append(
                DecisionJournalFinding(
                    "decision_journal_surface_evidence_invalid",
                    f"{surface_id} evidence_ref must stay manual_preparation_pending in the committed packet",
                )
            )
        if not isinstance(surface.get("public_safe_note"), str) or not surface["public_safe_note"].strip():
            findings.append(
                DecisionJournalFinding(
                    "decision_journal_surface_note_invalid",
                    f"{surface_id} public_safe_note must be a non-empty string",
                )
            )
    return findings


def validate_forbidden_value_patterns(payload: dict[str, Any]) -> list[DecisionJournalFinding]:
    """Return findings for private, schedule, customer, provider, reviewer, or secret-shaped values."""

    serialized_payload = json.dumps(payload, sort_keys=True)
    findings: list[DecisionJournalFinding] = []
    for rule_id, pattern in FORBIDDEN_VALUE_PATTERNS:
        if pattern.search(serialized_payload):
            findings.append(
                DecisionJournalFinding(
                    "decision_journal_forbidden_private_value_pattern",
                    f"decision-journal witness contains forbidden value pattern: {rule_id}",
                )
            )
    return findings


def validate_forbidden_promotion_patterns(payload: dict[str, Any]) -> list[DecisionJournalFinding]:
    """Return findings if the witness drifts into decision-promotion phrases."""

    serialized_payload = json.dumps(payload, sort_keys=True)
    findings: list[DecisionJournalFinding] = []
    for rule_id, pattern in FORBIDDEN_PROMOTION_PATTERNS:
        if pattern.search(serialized_payload):
            findings.append(
                DecisionJournalFinding(
                    "decision_journal_forbidden_promotion_phrase",
                    f"decision-journal witness contains forbidden promotion pattern: {rule_id}",
                )
            )
    return findings


def validate_foundation_decision_journal_boundary(
    doc_path: Path = DEFAULT_DOC_PATH,
    packet_path: Path = DEFAULT_PACKET_PATH,
) -> list[DecisionJournalFinding]:
    """Validate the Foundation Mode decision-journal boundary artifacts."""

    doc_text = load_text(doc_path, "decision-journal boundary doc")
    packet_payload = load_json_object(packet_path, "decision-journal witness packet")
    return [
        *validate_doc_text(doc_text),
        *validate_packet(packet_payload),
    ]


def main(argv: list[str] | None = None) -> int:
    """Validate decision-journal boundary artifacts and print deterministic status."""

    parser = argparse.ArgumentParser(description="Validate Foundation Mode decision-journal boundary artifacts.")
    parser.add_argument("--doc", type=Path, default=DEFAULT_DOC_PATH)
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET_PATH)
    args = parser.parse_args(argv)

    try:
        findings = validate_foundation_decision_journal_boundary(args.doc, args.packet)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"[FAIL] foundation_decision_journal_load: {exc}", file=sys.stderr)
        print("STATUS: failed", file=sys.stderr)
        return 1

    if findings:
        for finding in findings:
            print(f"[FAIL] {finding.rule_id}: {finding.message}", file=sys.stderr)
        print("STATUS: failed", file=sys.stderr)
        return 1
    print("[PASS] foundation_decision_journal_doc")
    print("[PASS] foundation_decision_journal_witness")
    print("STATUS: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
