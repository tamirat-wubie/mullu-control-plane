#!/usr/bin/env python3
"""Validate the Foundation Mode evidence-ledger boundary.

Purpose: keep evidence-ledger preparation local and public-safe while evidence
promotion, terminal-closure, readiness, legal-clearance, patent-protection,
customer-readiness, paid-launch, secret-evidence, external-publication, and
deployment claims remain blocked.
Governance scope: Foundation Mode, local evidence index, witness references,
validator references, test references, receipt references, source-control
packet references, readiness snapshot references, public-copy routing,
private-value exclusion, and claim-promotion blocking.
Dependencies: docs/FOUNDATION_EVIDENCE_LEDGER_BOUNDARY.md and
examples/foundation_evidence_ledger_witness.awaiting_evidence.json.
Invariants:
  - Validation is read-only.
  - The witness records evidence-ledger preparation only.
  - No evidence-promotion, terminal-closure, readiness, legal-clearance,
    patent-protection, customer-readiness, paid-launch, secret-evidence,
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
DEFAULT_DOC_PATH = REPO_ROOT / "docs" / "FOUNDATION_EVIDENCE_LEDGER_BOUNDARY.md"
DEFAULT_PACKET_PATH = REPO_ROOT / "examples" / "foundation_evidence_ledger_witness.awaiting_evidence.json"

EXPECTED_WITNESS_ID = "foundation_evidence_ledger_witness.awaiting_evidence.v1"
EXPECTED_BLOCKED_CLAIMS = (
    "evidence promotion",
    "terminal closure",
    "readiness claim",
    "legal clearance",
    "patent protection",
    "customer readiness",
    "paid launch",
    "secret evidence",
    "external publication",
    "deployment readiness",
)
EXPECTED_ENTRIES = (
    ("foundation_boundary_docs", "local_reference", "AwaitingEvidence"),
    ("foundation_witness_packets", "local_reference", "AwaitingEvidence"),
    ("foundation_validators", "local_reference", "AwaitingEvidence"),
    ("foundation_tests", "local_reference", "AwaitingEvidence"),
    ("governance_preflight_receipt", "local_reference", "AwaitingEvidence"),
    ("source_control_packet", "local_reference", "AwaitingEvidence"),
    ("readiness_snapshot", "local_reference", "AwaitingEvidence"),
    ("public_copy_routing", "local_reference", "AwaitingEvidence"),
)
EXPECTED_ROOT_KEYS = {
    "blocked_claims",
    "customer_readiness_claimed",
    "deployment_allowed",
    "evidence_ledger_entries",
    "evidence_promotion_allowed",
    "external_publication_allowed",
    "legal_clearance_claimed",
    "next_action",
    "paid_launch_allowed",
    "patent_protection_claimed",
    "readiness_claimed",
    "schema_version",
    "secret_evidence_recorded",
    "solver_outcome",
    "status",
    "terminal_closure_claimed",
    "witness_id",
}
EXPECTED_ENTRY_KEYS = {
    "entry_id",
    "entry_type",
    "evidence_ref",
    "public_safe_note",
    "state",
}
REQUIRED_DOC_PHRASES = (
    "Foundation Evidence Ledger Boundary",
    "Witness packet: [`../examples/foundation_evidence_ledger_witness.awaiting_evidence.json`]",
    "Rule: Evidence-ledger preparation is a local planning boundary, not a terminal-closure, readiness, legal, patent, customer, publication, paid-launch, secret-evidence, or deployment certificate.",
    "No terminal closure, readiness promotion, legal clearance, patent protection,",
    "evidence_ledger_boundary_state=AwaitingEvidence",
    "evidence_promotion_allowed=false",
    "terminal_closure_claimed=false",
    "readiness_claimed=false",
    "secret_evidence_recorded=false",
    "deployment_allowed=false",
    "python scripts/validate_foundation_evidence_ledger_boundary.py",
)
FORBIDDEN_VALUE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("url_value", re.compile(r"https?://", re.IGNORECASE)),
    ("email_value", re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)),
    ("private_path", re.compile(r"\b[A-Za-z]:[\\/]|\\\\", re.IGNORECASE)),
    ("provider_assignment", re.compile(r"\b(?:provider|account|tenant|project)[_ -]?(?:id|ref|target|value)\s*=", re.IGNORECASE)),
    ("reviewer_assignment", re.compile(r"\b(?:reviewer|attorney|auditor)[_ -]?(?:id|name|email|ref|value)\s*=", re.IGNORECASE)),
    ("customer_assignment", re.compile(r"\b(?:customer|pilot|user)[_ -]?(?:id|name|email|ref|value)\s*=", re.IGNORECASE)),
    ("secret_evidence_assignment", re.compile(r"\b(?:secret[_ -]?evidence|confidential|private[_ -]?evidence)[_ -]?(?:id|ref|value|path)\s*=", re.IGNORECASE)),
    ("secret_assignment", re.compile(r"\b(?:password|secret|token|api[_ -]?key)\s*=", re.IGNORECASE)),
    ("private_key_material", re.compile(r"BEGIN [A-Z ]*PRIVATE KEY")),
)
FORBIDDEN_PROMOTION_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("evidence_promoted", re.compile(r"\bevidence\s+(?:is\s+)?promoted\b", re.IGNORECASE)),
    ("terminal_closure_complete", re.compile(r"\bterminal\s+closure\s+(?:is\s+)?complete\b", re.IGNORECASE)),
    ("readiness_proven", re.compile(r"\breadiness\s+(?:is\s+)?proven\b", re.IGNORECASE)),
    ("legal_clearance_complete", re.compile(r"\blegal\s+clearance\s+(?:is\s+)?complete\b", re.IGNORECASE)),
    ("patent_protected", re.compile(r"\bpatent\s+protected\b", re.IGNORECASE)),
    ("customer_ready", re.compile(r"\bcustomer\s+ready\b", re.IGNORECASE)),
    ("paid_launch_ready", re.compile(r"\bpaid\s+launch\s+(?:is\s+)?ready\b", re.IGNORECASE)),
    ("secret_evidence_exists", re.compile(r"\bsecret\s+evidence\s+(?:exists|is\s+confirmed)\b", re.IGNORECASE)),
    ("published_externally", re.compile(r"\bpublished\s+externally\b", re.IGNORECASE)),
    ("deployment_ready", re.compile(r"\bdeployment\s+(?:is\s+)?ready\b", re.IGNORECASE)),
)


@dataclass(frozen=True, slots=True)
class EvidenceLedgerFinding:
    """One deterministic evidence-ledger boundary validation finding."""

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


def validate_doc_text(text: str) -> list[EvidenceLedgerFinding]:
    """Return findings for missing evidence-ledger documentation anchors."""

    findings: list[EvidenceLedgerFinding] = []
    for phrase in REQUIRED_DOC_PHRASES:
        if phrase not in text:
            findings.append(
                EvidenceLedgerFinding(
                    "foundation_evidence_ledger_doc_phrase_missing",
                    f"evidence-ledger boundary doc missing required phrase: {phrase}",
                )
            )
    return findings


def validate_packet(payload: dict[str, Any]) -> list[EvidenceLedgerFinding]:
    """Return findings for evidence-ledger witness drift."""

    findings: list[EvidenceLedgerFinding] = []
    findings.extend(validate_root_contract(payload))
    findings.extend(validate_evidence_entries(payload.get("evidence_ledger_entries")))
    findings.extend(validate_forbidden_value_patterns(payload))
    findings.extend(validate_forbidden_promotion_patterns(payload))
    return findings


def validate_root_contract(payload: dict[str, Any]) -> list[EvidenceLedgerFinding]:
    """Return findings for root-level evidence-ledger witness drift."""

    findings: list[EvidenceLedgerFinding] = []
    if set(payload) != EXPECTED_ROOT_KEYS:
        findings.append(
            EvidenceLedgerFinding(
                "evidence_ledger_root_keys_invalid",
                f"root keys must be: {', '.join(sorted(EXPECTED_ROOT_KEYS))}",
            )
        )
    expected_values = {
        "witness_id": EXPECTED_WITNESS_ID,
        "schema_version": 1,
        "status": "AwaitingEvidence",
        "solver_outcome": "AwaitingEvidence",
        "evidence_promotion_allowed": False,
        "terminal_closure_claimed": False,
        "readiness_claimed": False,
        "legal_clearance_claimed": False,
        "patent_protection_claimed": False,
        "customer_readiness_claimed": False,
        "paid_launch_allowed": False,
        "secret_evidence_recorded": False,
        "external_publication_allowed": False,
        "deployment_allowed": False,
    }
    for key, expected_value in expected_values.items():
        if payload.get(key) != expected_value:
            findings.append(
                EvidenceLedgerFinding(
                    "evidence_ledger_root_value_invalid",
                    f"{key} must be {expected_value!r}",
                )
            )
    if tuple(payload.get("blocked_claims") or ()) != EXPECTED_BLOCKED_CLAIMS:
        findings.append(
            EvidenceLedgerFinding(
                "evidence_ledger_blocked_claims_invalid",
                f"blocked_claims must be: {', '.join(EXPECTED_BLOCKED_CLAIMS)}",
            )
        )
    next_action = payload.get("next_action")
    if not isinstance(next_action, str) or "do not promote evidence" not in next_action:
        findings.append(
            EvidenceLedgerFinding(
                "evidence_ledger_next_action_invalid",
                "next_action must preserve the evidence-ledger boundary",
            )
        )
    return findings


def validate_evidence_entries(evidence_entries: object) -> list[EvidenceLedgerFinding]:
    """Return findings for evidence-ledger entry drift."""

    findings: list[EvidenceLedgerFinding] = []
    if not isinstance(evidence_entries, list) or not all(isinstance(entry, dict) for entry in evidence_entries):
        return [EvidenceLedgerFinding("evidence_ledger_entries_invalid", "evidence_ledger_entries must be a list of objects")]
    observed_entries = tuple(
        (entry.get("entry_id"), entry.get("entry_type"), entry.get("state"))
        for entry in evidence_entries
    )
    if observed_entries != EXPECTED_ENTRIES:
        findings.append(
            EvidenceLedgerFinding(
                "evidence_ledger_entry_inventory_invalid",
                "evidence-ledger entry inventory does not match the Foundation Mode evidence set",
            )
        )
    entry_ids = [entry.get("entry_id") for entry in evidence_entries]
    if len(set(entry_ids)) != len(entry_ids):
        findings.append(EvidenceLedgerFinding("evidence_ledger_entry_duplicate", "entry ids must be unique"))
    for entry in evidence_entries:
        entry_id = str(entry.get("entry_id", "<missing>"))
        if set(entry) != EXPECTED_ENTRY_KEYS:
            findings.append(
                EvidenceLedgerFinding(
                    "evidence_ledger_entry_keys_invalid",
                    f"{entry_id} entry keys must be: {', '.join(sorted(EXPECTED_ENTRY_KEYS))}",
                )
            )
        if entry.get("state") != "AwaitingEvidence":
            findings.append(
                EvidenceLedgerFinding(
                    "evidence_ledger_entry_state_invalid",
                    f"{entry_id} state must be AwaitingEvidence",
                )
            )
        if entry.get("evidence_ref") != "manual_preparation_pending":
            findings.append(
                EvidenceLedgerFinding(
                    "evidence_ledger_entry_evidence_invalid",
                    f"{entry_id} evidence_ref must stay manual_preparation_pending in the committed packet",
                )
            )
        if not isinstance(entry.get("public_safe_note"), str) or not entry["public_safe_note"].strip():
            findings.append(
                EvidenceLedgerFinding(
                    "evidence_ledger_entry_note_invalid",
                    f"{entry_id} public_safe_note must be a non-empty string",
                )
            )
    return findings


def validate_forbidden_value_patterns(payload: dict[str, Any]) -> list[EvidenceLedgerFinding]:
    """Return findings for private, provider, customer, reviewer, or secret-shaped values."""

    serialized_payload = json.dumps(payload, sort_keys=True)
    findings: list[EvidenceLedgerFinding] = []
    for rule_id, pattern in FORBIDDEN_VALUE_PATTERNS:
        if pattern.search(serialized_payload):
            findings.append(
                EvidenceLedgerFinding(
                    "evidence_ledger_forbidden_private_value_pattern",
                    f"evidence-ledger witness contains forbidden value pattern: {rule_id}",
                )
            )
    return findings


def validate_forbidden_promotion_patterns(payload: dict[str, Any]) -> list[EvidenceLedgerFinding]:
    """Return findings if the witness drifts into evidence-promotion phrases."""

    serialized_payload = json.dumps(payload, sort_keys=True)
    findings: list[EvidenceLedgerFinding] = []
    for rule_id, pattern in FORBIDDEN_PROMOTION_PATTERNS:
        if pattern.search(serialized_payload):
            findings.append(
                EvidenceLedgerFinding(
                    "evidence_ledger_forbidden_promotion_phrase",
                    f"evidence-ledger witness contains forbidden promotion pattern: {rule_id}",
                )
            )
    return findings


def validate_foundation_evidence_ledger_boundary(
    doc_path: Path = DEFAULT_DOC_PATH,
    packet_path: Path = DEFAULT_PACKET_PATH,
) -> list[EvidenceLedgerFinding]:
    """Validate the Foundation Mode evidence-ledger boundary artifacts."""

    doc_text = load_text(doc_path, "evidence-ledger boundary doc")
    packet_payload = load_json_object(packet_path, "evidence-ledger witness packet")
    return [
        *validate_doc_text(doc_text),
        *validate_packet(packet_payload),
    ]


def main(argv: list[str] | None = None) -> int:
    """Validate evidence-ledger boundary artifacts and print deterministic status."""

    parser = argparse.ArgumentParser(description="Validate Foundation Mode evidence-ledger boundary artifacts.")
    parser.add_argument("--doc", type=Path, default=DEFAULT_DOC_PATH)
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET_PATH)
    args = parser.parse_args(argv)

    try:
        findings = validate_foundation_evidence_ledger_boundary(args.doc, args.packet)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"[FAIL] foundation_evidence_ledger_load: {exc}", file=sys.stderr)
        print("STATUS: failed", file=sys.stderr)
        return 1

    if findings:
        for finding in findings:
            print(f"[FAIL] {finding.rule_id}: {finding.message}", file=sys.stderr)
        print("STATUS: failed", file=sys.stderr)
        return 1
    print("[PASS] foundation_evidence_ledger_doc")
    print("[PASS] foundation_evidence_ledger_witness")
    print("STATUS: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
