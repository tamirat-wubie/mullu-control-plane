#!/usr/bin/env python3
"""Validate the Foundation Mode patent/disclosure deferral boundary.

Purpose: keep patent filing, patent protection, invention finality, authorship
finality, ownership finality, prior-art conclusions, novelty, patentability,
disclosure approval, publication, secret/trade-secret protection claims, legal
clearance, company formation, paid launch, money movement, customer access, and
deployment blocked.
Governance scope: Foundation Mode, local patent/disclosure deferral,
invention-boundary blocking, disclosure/publication blocking, private-value
exclusion, legal/company blocking, payment blocking, customer-access blocking,
and deployment blocking.
Dependencies: docs/FOUNDATION_PATENT_DISCLOSURE_DEFERRAL_BOUNDARY.md and
examples/foundation_patent_disclosure_deferral_witness.awaiting_evidence.json.
Invariants:
  - The witness records public-safe deferral labels only.
  - No filing values, invention records, inventor identities, ownership records, prior-art conclusions, novelty or patentability opinions, disclosure approvals, publication receipts, secrecy claims, or readiness claims are recorded.
  - Every patent/disclosure deferral surface remains AwaitingEvidence.
  - Publication, money movement, customer access, legal/company promotion, and deployment remain blocked.
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
DEFAULT_DOC_PATH = REPO_ROOT / "docs" / "FOUNDATION_PATENT_DISCLOSURE_DEFERRAL_BOUNDARY.md"
DEFAULT_PACKET_PATH = REPO_ROOT / "examples" / "foundation_patent_disclosure_deferral_witness.awaiting_evidence.json"

REQUIRED_ROOT_KEYS = (
    "blocked_claims",
    "company_formation_claimed",
    "customer_access_allowed",
    "deferral_labels",
    "deployment_allowed",
    "disclosure_approval_claimed",
    "external_publication_allowed",
    "invention_authorship_final_claimed",
    "invention_boundary_final_claimed",
    "legal_clearance_claimed",
    "money_movement_allowed",
    "next_action",
    "novelty_claimed",
    "ownership_claim_finalized",
    "paid_launch_allowed",
    "patent_filing_allowed",
    "patent_protection_claimed",
    "patentability_claimed",
    "prior_art_conclusion_recorded",
    "public_research_publication_allowed",
    "schema_version",
    "secret_or_trade_secret_protection_claimed",
    "solver_outcome",
    "status",
    "surfaces",
    "witness_id",
)
EXPECTED_ROOT_VALUES = {
    "schema_version": "foundation.patent_disclosure_deferral.v1",
    "witness_id": "foundation_patent_disclosure_deferral_witness.awaiting_evidence.v1",
    "status": "AwaitingEvidence",
    "solver_outcome": "AwaitingEvidence",
}
FALSE_FLAGS = (
    "company_formation_claimed",
    "customer_access_allowed",
    "deployment_allowed",
    "disclosure_approval_claimed",
    "external_publication_allowed",
    "invention_authorship_final_claimed",
    "invention_boundary_final_claimed",
    "legal_clearance_claimed",
    "money_movement_allowed",
    "novelty_claimed",
    "ownership_claim_finalized",
    "paid_launch_allowed",
    "patent_filing_allowed",
    "patent_protection_claimed",
    "patentability_claimed",
    "prior_art_conclusion_recorded",
    "public_research_publication_allowed",
    "secret_or_trade_secret_protection_claimed",
)
DEFERRAL_LABELS = (
    "patent_filing_gate",
    "patent_protection_gate",
    "invention_boundary_gate",
    "invention_authorship_gate",
    "ownership_claim_gate",
    "prior_art_review_gate",
    "novelty_claim_gate",
    "patentability_claim_gate",
    "disclosure_approval_gate",
    "public_research_publication_gate",
    "external_publication_gate",
    "secret_protection_claim_gate",
    "legal_clearance_gate",
    "company_formation_gate",
    "paid_launch_gate",
    "money_movement_gate",
    "customer_access_gate",
    "deployment_gate",
    "operator_reassessment_gate",
)
BLOCKED_CLAIMS = (
    "patent filing",
    "patent protection",
    "invention-boundary finality",
    "invention authorship finality",
    "ownership finality",
    "prior-art conclusion",
    "novelty claim",
    "patentability claim",
    "disclosure approval",
    "public research publication",
    "external publication",
    "secret/trade-secret protection",
    "legal clearance",
    "company formation",
    "paid launch",
    "money movement",
    "customer access",
    "deployment readiness",
)
SURFACE_NOTES_BY_ID = {
    "patent_filing_gate": "Patent filing gate only; patent filing is not allowed or claimed.",
    "patent_protection_gate": "Patent protection gate only; patent protection is not claimed.",
    "invention_boundary_gate": "Invention boundary gate only; invention-boundary finality is not claimed.",
    "invention_authorship_gate": "Invention authorship gate only; invention authorship finality is not claimed.",
    "ownership_claim_gate": "Ownership claim gate only; ownership finality is not claimed.",
    "prior_art_review_gate": "Prior-art review gate only; prior-art conclusions are not recorded or claimed.",
    "novelty_claim_gate": "Novelty claim gate only; novelty is not claimed.",
    "patentability_claim_gate": "Patentability claim gate only; patentability is not claimed.",
    "disclosure_approval_gate": "Disclosure approval gate only; disclosure approval is not claimed.",
    "public_research_publication_gate": "Public research publication gate only; public research publication is not allowed.",
    "external_publication_gate": "External publication gate only; external publication is not allowed.",
    "secret_protection_claim_gate": "Secret protection claim gate only; secret or trade-secret protection is not claimed.",
    "legal_clearance_gate": "Legal clearance gate only; legal clearance is not claimed.",
    "company_formation_gate": "Company formation gate only; company formation is not performed or claimed.",
    "paid_launch_gate": "Paid launch gate only; paid launch is not allowed.",
    "money_movement_gate": "Money movement gate only; money movement is not allowed.",
    "customer_access_gate": "Customer access gate only; customer access is not allowed.",
    "deployment_gate": "Deployment gate only; deployment is not allowed.",
    "operator_reassessment_gate": "Operator reassessment gate only; patent/disclosure promotion is not approved.",
}
SURFACE_TYPES_BY_ID = {
    "patent_filing_gate": "blocked_patent_filing_label",
    "patent_protection_gate": "blocked_patent_protection_label",
    "invention_boundary_gate": "blocked_invention_boundary_label",
    "invention_authorship_gate": "blocked_invention_authorship_label",
    "ownership_claim_gate": "blocked_ownership_claim_label",
    "prior_art_review_gate": "blocked_prior_art_review_label",
    "novelty_claim_gate": "blocked_novelty_claim_label",
    "patentability_claim_gate": "blocked_patentability_claim_label",
    "disclosure_approval_gate": "blocked_disclosure_approval_label",
    "public_research_publication_gate": "blocked_public_research_publication_label",
    "external_publication_gate": "blocked_external_publication_label",
    "secret_protection_claim_gate": "blocked_secret_protection_claim_label",
    "legal_clearance_gate": "blocked_legal_clearance_label",
    "company_formation_gate": "blocked_company_formation_label",
    "paid_launch_gate": "blocked_paid_launch_label",
    "money_movement_gate": "blocked_money_movement_label",
    "customer_access_gate": "blocked_customer_access_label",
    "deployment_gate": "blocked_deployment_label",
    "operator_reassessment_gate": "local_gate_label",
}
REQUIRED_DOC_PHRASES = (
    "Foundation Patent Disclosure Deferral Boundary",
    "Witness packet: [`../examples/foundation_patent_disclosure_deferral_witness.awaiting_evidence.json`]",
    "Rule: Patent/disclosure deferral is a local stop-rule packet",
    "No patent filing, patent protection claim, invention-boundary finality,",
    "patent_disclosure_deferral_state=AwaitingEvidence",
    "patent_filing_allowed=false",
    "patent_protection_claimed=false",
    "invention_boundary_final_claimed=false",
    "invention_authorship_final_claimed=false",
    "ownership_claim_finalized=false",
    "prior_art_conclusion_recorded=false",
    "novelty_claimed=false",
    "patentability_claimed=false",
    "disclosure_approval_claimed=false",
    "public_research_publication_allowed=false",
    "external_publication_allowed=false",
    "secret_or_trade_secret_protection_claimed=false",
    "legal_clearance_claimed=false",
    "company_formation_claimed=false",
    "paid_launch_allowed=false",
    "money_movement_allowed=false",
    "customer_access_allowed=false",
    "deployment_allowed=false",
    "python scripts/validate_foundation_patent_disclosure_deferral_boundary.py",
)
FORBIDDEN_VALUE_PATTERNS = (
    ("url", re.compile(r"\b(?:https?://|www\.)\S+", re.IGNORECASE)),
    ("email", re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)),
    ("ip_address", re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")),
    ("timestamp", re.compile(r"\b20\d{2}-\d{2}-\d{2}[T ][0-2]\d:[0-5]\d")),
    ("private_path", re.compile(r"(?:[A-Za-z]:\\|/home/|/Users/|\\\\[^\\]+\\)", re.IGNORECASE)),
    ("secret_material", re.compile(r"\b(?:sk|pk|ghp|github_pat|AKIA)[A-Za-z0-9_-]{8,}\b")),
    ("hash_like_value", re.compile(r"\b[a-f0-9]{32,}\b", re.IGNORECASE)),
    (
        "assignment_shape",
        re.compile(
            r"\b(?:patent|application|filing|invention|inventor|author|ownership|prior[_ -]?art|"
            r"novelty|patentability|disclosure|publication|secret|trade[_ -]?secret|legal|"
            r"company|customer|deployment|tenant|token|key|url|endpoint)\w*\s*=",
            re.IGNORECASE,
        ),
    ),
)
FORBIDDEN_PROMOTION_PATTERNS = (
    ("patent_filed", re.compile(r"\bpatent\s+(?:is\s+)?(?:filed|submitted|approved|secured)\b", re.IGNORECASE)),
    ("patent_protected", re.compile(r"\bpatent\s+(?:is\s+)?(?:protected|approved|secured)\b", re.IGNORECASE)),
    ("patent_protection_secured", re.compile(r"\bpatent protection\s+(?:is\s+)?(?:approved|secured)\b", re.IGNORECASE)),
    ("invention_boundary_final", re.compile(r"\binvention boundary\s+(?:is\s+)?final\b", re.IGNORECASE)),
    ("invention_authorship_final", re.compile(r"\binvention authorship\s+(?:is\s+)?final\b", re.IGNORECASE)),
    ("ownership_finalized", re.compile(r"\bownership\s+(?:is\s+)?finalized\b", re.IGNORECASE)),
    ("prior_art_cleared", re.compile(r"\bprior[- ]art\s+(?:is\s+)?(?:cleared|review complete)\b", re.IGNORECASE)),
    ("novelty_confirmed", re.compile(r"\bnovelty\s+(?:is\s+)?confirmed\b", re.IGNORECASE)),
    ("patentability_confirmed", re.compile(r"\bpatentability\s+(?:is\s+)?confirmed\b", re.IGNORECASE)),
    ("disclosure_approved", re.compile(r"\bdisclosure\s+(?:is\s+)?approved\b", re.IGNORECASE)),
    ("research_published", re.compile(r"\bresearch\s+(?:is\s+)?published\b", re.IGNORECASE)),
    ("external_publication_approved", re.compile(r"\bexternal publication\s+(?:is\s+)?(?:approved|ready|allowed)\b", re.IGNORECASE)),
    ("trade_secret_protected", re.compile(r"\btrade[- ]secret\s+(?:is\s+)?protected\b", re.IGNORECASE)),
    ("legal_clearance_approved", re.compile(r"\blegal clearance\s+(?:is\s+)?(?:approved|granted|secured)\b", re.IGNORECASE)),
    ("company_formed", re.compile(r"\bcompany\s+(?:is\s+)?formed\b", re.IGNORECASE)),
    ("paid_launch_open", re.compile(r"\bpaid launch\s+(?:is\s+)?(?:open|approved|ready)\b", re.IGNORECASE)),
    ("money_movement_allowed", re.compile(r"\bmoney movement\s+(?:is\s+)?(?:allowed|approved|ready)\b", re.IGNORECASE)),
    ("customer_access_open", re.compile(r"\bcustomer access\s+(?:is\s+)?(?:open|allowed|ready)\b", re.IGNORECASE)),
    ("deployment_ready", re.compile(r"\bdeployment\s+(?:is\s+)?(?:ready|approved|complete)\b", re.IGNORECASE)),
)


@dataclass(frozen=True, slots=True)
class Finding:
    """One deterministic patent/disclosure deferral validation finding."""

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
    """Return findings for patent/disclosure deferral surface inventory and state drift."""

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
    """Return findings for patent/disclosure deferral packet drift."""

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
    if not isinstance(next_action, str) or "patent/disclosure deferral" not in next_action:
        findings.append(Finding("witness_next_action", "next_action must preserve patent/disclosure deferral"))
    findings.extend(validate_surfaces(payload.get("surfaces")))
    findings.extend(validate_forbidden_text(payload))
    return findings


def validate_artifacts(
    doc_path: Path = DEFAULT_DOC_PATH,
    packet_path: Path = DEFAULT_PACKET_PATH,
) -> list[Finding]:
    """Validate the patent/disclosure deferral doc and witness packet."""

    doc_text = load_text(doc_path, "patent/disclosure deferral doc")
    payload = load_json_object(packet_path, "patent/disclosure deferral witness")
    return [*validate_doc_text(doc_text), *validate_packet(payload)]


def main(argv: list[str] | None = None) -> int:
    """Run the patent/disclosure deferral validator."""

    parser = argparse.ArgumentParser(description="Validate Foundation Mode patent/disclosure deferral artifacts.")
    parser.add_argument("--doc", type=Path, default=DEFAULT_DOC_PATH)
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET_PATH)
    args = parser.parse_args(argv)

    try:
        findings = validate_artifacts(args.doc, args.packet)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"[FAIL] foundation_patent_disclosure_deferral_load: {exc}", file=sys.stderr)
        print("STATUS: failed", file=sys.stderr)
        return 1
    if findings:
        for finding in findings:
            print(f"[FAIL] {finding.rule_id}: {finding.message}", file=sys.stderr)
        print("STATUS: failed", file=sys.stderr)
        return 1
    print("[PASS] foundation_patent_disclosure_deferral_doc")
    print("[PASS] foundation_patent_disclosure_deferral_witness")
    print("STATUS: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
