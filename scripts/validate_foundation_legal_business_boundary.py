#!/usr/bin/env python3
"""Validate the Foundation Mode legal and business question boundary.

Purpose: keep legal and business preparation question-only until qualified
review or signed witness evidence promotes a specific item.
Governance scope: Foundation Mode, legal/business pre-clearance, claim blocking,
qualified-review gating, paid-launch blocking, and money-movement blocking.
Dependencies: docs/FOUNDATION_LEGAL_BUSINESS_BOUNDARY.md and
examples/foundation_legal_business_questions.awaiting_review.json.
Invariants:
  - Validation is read-only.
  - The question packet is not a legal conclusion.
  - Legal, company, patent, trademark, tax, terms, paid-launch, and
    money-movement readiness claims remain blocked.
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
DEFAULT_DOC_PATH = REPO_ROOT / "docs" / "FOUNDATION_LEGAL_BUSINESS_BOUNDARY.md"
DEFAULT_PACKET_PATH = REPO_ROOT / "examples" / "foundation_legal_business_questions.awaiting_review.json"

EXPECTED_PACKET_ID = "foundation_legal_business_questions.awaiting_review.v1"
EXPECTED_DOMAIN_IDS = (
    "ownership_invention_record",
    "public_name_trademark",
    "company_formation",
    "tax_accounting",
    "terms_privacy",
    "patent_invention_boundary",
    "data_compliance",
    "finance_payments",
    "contractor_team",
    "support_liability",
)
EXPECTED_ROOT_KEYS = {
    "company_ready_claimed",
    "customer_terms_ready_claimed",
    "domains",
    "legal_clearance_claimed",
    "money_movement_allowed",
    "next_action",
    "packet_id",
    "paid_launch_allowed",
    "patent_protection_claimed",
    "qualified_review_required",
    "schema_version",
    "solver_outcome",
    "status",
    "tax_readiness_claimed",
    "trademark_clearance_claimed",
}
EXPECTED_DOMAIN_KEYS = {
    "blocked_claims",
    "current_state",
    "domain_id",
    "evidence_to_collect",
    "public_safe_note",
    "qualified_reviewer_type",
    "questions",
}
REQUIRED_DOC_PHRASES = (
    "Foundation Legal Business Boundary",
    "Question packet: [`../examples/foundation_legal_business_questions.awaiting_review.json`]",
    "Rule: Legal and business readiness stays `AwaitingEvidence` until qualified",
    "No legal clearance, company readiness, patent protection, trademark clearance,",
    "qualified_review_required=true",
    "paid_launch_allowed=false",
    "money_movement_allowed=false",
    "python scripts/validate_foundation_legal_business_boundary.py",
)
FORBIDDEN_PACKET_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("ready_claim_sentence", re.compile(r"\b(?:is|are)\s+(?:ready|cleared|protected|allowed)\b", re.IGNORECASE)),
    ("legal_clearance_complete", re.compile(r"\blegal clearance (?:complete|granted|approved)\b", re.IGNORECASE)),
    ("patent_protected", re.compile(r"\bpatent protected\b", re.IGNORECASE)),
    ("trademark_cleared", re.compile(r"\btrademark cleared\b", re.IGNORECASE)),
    ("paid_launch_authorized", re.compile(r"\bpaid launch (?:authorized|approved|allowed)\b", re.IGNORECASE)),
    ("money_movement_authorized", re.compile(r"\bmoney movement (?:authorized|approved|allowed)\b", re.IGNORECASE)),
)


@dataclass(frozen=True, slots=True)
class LegalBusinessFinding:
    """One deterministic legal/business boundary validation finding."""

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


def validate_doc_text(text: str) -> list[LegalBusinessFinding]:
    """Return findings for missing legal/business documentation anchors."""

    findings: list[LegalBusinessFinding] = []
    for phrase in REQUIRED_DOC_PHRASES:
        if phrase not in text:
            findings.append(
                LegalBusinessFinding(
                    "foundation_legal_business_doc_phrase_missing",
                    f"legal/business boundary doc missing required phrase: {phrase}",
                )
            )
    return findings


def validate_packet(payload: dict[str, Any]) -> list[LegalBusinessFinding]:
    """Return findings for legal/business question packet drift."""

    findings: list[LegalBusinessFinding] = []
    findings.extend(validate_root_contract(payload))
    findings.extend(validate_domain_contract(payload.get("domains")))
    findings.extend(validate_forbidden_packet_patterns(payload))
    return findings


def validate_root_contract(payload: dict[str, Any]) -> list[LegalBusinessFinding]:
    """Return findings for root-level legal/business packet drift."""

    findings: list[LegalBusinessFinding] = []
    if set(payload) != EXPECTED_ROOT_KEYS:
        findings.append(
            LegalBusinessFinding(
                "legal_business_root_keys_invalid",
                f"root keys must be: {', '.join(sorted(EXPECTED_ROOT_KEYS))}",
            )
        )
    expected_values = {
        "packet_id": EXPECTED_PACKET_ID,
        "schema_version": 1,
        "status": "AwaitingEvidence",
        "solver_outcome": "AwaitingEvidence",
        "qualified_review_required": True,
        "legal_clearance_claimed": False,
        "company_ready_claimed": False,
        "patent_protection_claimed": False,
        "trademark_clearance_claimed": False,
        "tax_readiness_claimed": False,
        "customer_terms_ready_claimed": False,
        "paid_launch_allowed": False,
        "money_movement_allowed": False,
    }
    for key, expected_value in expected_values.items():
        if payload.get(key) != expected_value:
            findings.append(
                LegalBusinessFinding(
                    "legal_business_root_value_invalid",
                    f"{key} must be {expected_value!r}",
                )
            )
    next_action = payload.get("next_action")
    if not isinstance(next_action, str) or "qualified review" not in next_action:
        findings.append(
            LegalBusinessFinding(
                "legal_business_next_action_invalid",
                "next_action must preserve qualified-review gating",
            )
        )
    return findings


def validate_domain_contract(domains: object) -> list[LegalBusinessFinding]:
    """Return findings for legal/business domain packet drift."""

    findings: list[LegalBusinessFinding] = []
    if not isinstance(domains, list) or not all(isinstance(domain, dict) for domain in domains):
        return [LegalBusinessFinding("legal_business_domains_invalid", "domains must be a list of objects")]
    observed_domain_ids = tuple(domain.get("domain_id") for domain in domains)
    if observed_domain_ids != EXPECTED_DOMAIN_IDS:
        findings.append(
            LegalBusinessFinding(
                "legal_business_domain_ids_invalid",
                f"domain ids must be: {', '.join(EXPECTED_DOMAIN_IDS)}",
            )
        )
    if len(set(observed_domain_ids)) != len(observed_domain_ids):
        findings.append(LegalBusinessFinding("legal_business_domain_duplicate", "domain ids must be unique"))
    for domain in domains:
        domain_id = str(domain.get("domain_id", "<missing>"))
        if set(domain) != EXPECTED_DOMAIN_KEYS:
            findings.append(
                LegalBusinessFinding(
                    "legal_business_domain_keys_invalid",
                    f"{domain_id} domain keys must be: {', '.join(sorted(EXPECTED_DOMAIN_KEYS))}",
                )
            )
        if domain.get("current_state") != "AwaitingEvidence":
            findings.append(
                LegalBusinessFinding(
                    "legal_business_domain_state_invalid",
                    f"{domain_id} current_state must be AwaitingEvidence",
                )
            )
        for field_name in ("blocked_claims", "evidence_to_collect", "questions"):
            values = domain.get(field_name)
            if not isinstance(values, list) or len(values) < 2 or not all(isinstance(value, str) and value for value in values):
                findings.append(
                    LegalBusinessFinding(
                        "legal_business_domain_list_invalid",
                        f"{domain_id} {field_name} must contain at least two non-empty strings",
                    )
                )
        for field_name in ("public_safe_note", "qualified_reviewer_type"):
            if not isinstance(domain.get(field_name), str) or not domain[field_name].strip():
                findings.append(
                    LegalBusinessFinding(
                        "legal_business_domain_text_invalid",
                        f"{domain_id} {field_name} must be a non-empty string",
                    )
                )
    return findings


def validate_forbidden_packet_patterns(payload: dict[str, Any]) -> list[LegalBusinessFinding]:
    """Return findings if the packet text drifts into readiness claims."""

    serialized_payload = json.dumps(payload, sort_keys=True)
    findings: list[LegalBusinessFinding] = []
    for rule_id, pattern in FORBIDDEN_PACKET_PATTERNS:
        if pattern.search(serialized_payload):
            findings.append(
                LegalBusinessFinding(
                    "legal_business_forbidden_readiness_phrase",
                    f"question packet contains forbidden readiness pattern: {rule_id}",
                )
            )
    return findings


def validate_foundation_legal_business_boundary(
    doc_path: Path = DEFAULT_DOC_PATH,
    packet_path: Path = DEFAULT_PACKET_PATH,
) -> list[LegalBusinessFinding]:
    """Validate the Foundation Mode legal/business boundary artifacts."""

    doc_text = load_text(doc_path, "legal/business boundary doc")
    packet_payload = load_json_object(packet_path, "legal/business question packet")
    return [
        *validate_doc_text(doc_text),
        *validate_packet(packet_payload),
    ]


def main(argv: list[str] | None = None) -> int:
    """Validate legal/business boundary artifacts and print deterministic status."""

    parser = argparse.ArgumentParser(description="Validate Foundation Mode legal/business boundary artifacts.")
    parser.add_argument("--doc", type=Path, default=DEFAULT_DOC_PATH)
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET_PATH)
    args = parser.parse_args(argv)

    try:
        findings = validate_foundation_legal_business_boundary(args.doc, args.packet)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"[FAIL] foundation_legal_business_load: {exc}", file=sys.stderr)
        print("STATUS: failed", file=sys.stderr)
        return 1

    if findings:
        for finding in findings:
            print(f"[FAIL] {finding.rule_id}: {finding.message}", file=sys.stderr)
        print("STATUS: failed", file=sys.stderr)
        return 1
    print("[PASS] foundation_legal_business_doc")
    print("[PASS] foundation_legal_business_packet")
    print("STATUS: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
