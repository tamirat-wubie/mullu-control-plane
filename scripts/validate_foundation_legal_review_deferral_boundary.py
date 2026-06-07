#!/usr/bin/env python3
"""Validate the Foundation Mode legal-review deferral boundary.

Purpose: keep legal review completion, legal conclusions, clearance, formation,
filings, tax readiness, terms/privacy readiness, compliance clearance,
contractor agreements, paid launch, payment processing, customer access,
personal-data collection, money movement, external publication, and deployment
blocked until qualified outside evidence exists.
Governance scope: Foundation Mode, local legal-review deferral,
qualified-review gating, claim blocking, private-material exclusion,
payment blocking, customer-access blocking, publication blocking, and
deployment blocking.
Dependencies: docs/FOUNDATION_LEGAL_REVIEW_DEFERRAL_BOUNDARY.md and
examples/foundation_legal_review_deferral_witness.awaiting_evidence.json.
Invariants:
  - The witness records public-safe deferral labels only.
  - No reviewer identities, legal conclusions, filings, accounts, payments, customer data, or readiness claims are recorded.
  - Every legal-review deferral surface remains AwaitingEvidence.
  - Formation, money movement, publication, and deployment remain blocked.
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
DEFAULT_DOC_PATH = REPO_ROOT / "docs" / "FOUNDATION_LEGAL_REVIEW_DEFERRAL_BOUNDARY.md"
DEFAULT_PACKET_PATH = REPO_ROOT / "examples" / "foundation_legal_review_deferral_witness.awaiting_evidence.json"

REQUIRED_ROOT_KEYS = (
    "blocked_claims",
    "company_formation_allowed",
    "compliance_clearance_claimed",
    "contractor_agreement_allowed",
    "customer_access_allowed",
    "deferral_labels",
    "deployment_allowed",
    "external_publication_allowed",
    "legal_clearance_claimed",
    "legal_conclusion_recorded",
    "legal_review_complete_claimed",
    "money_movement_allowed",
    "next_action",
    "paid_launch_allowed",
    "patent_protection_claimed",
    "payment_processing_allowed",
    "personal_data_collection_allowed",
    "qualified_reviewer_identity_recorded",
    "schema_version",
    "solver_outcome",
    "status",
    "surfaces",
    "tax_readiness_claimed",
    "terms_privacy_approved",
    "trademark_clearance_claimed",
    "witness_id",
)
EXPECTED_ROOT_VALUES = {
    "schema_version": "foundation.legal_review_deferral.v1",
    "witness_id": "foundation_legal_review_deferral_witness.awaiting_evidence.v1",
    "status": "AwaitingEvidence",
    "solver_outcome": "AwaitingEvidence",
}
FALSE_FLAGS = (
    "company_formation_allowed",
    "compliance_clearance_claimed",
    "contractor_agreement_allowed",
    "customer_access_allowed",
    "deployment_allowed",
    "external_publication_allowed",
    "legal_clearance_claimed",
    "legal_conclusion_recorded",
    "legal_review_complete_claimed",
    "money_movement_allowed",
    "paid_launch_allowed",
    "patent_protection_claimed",
    "payment_processing_allowed",
    "personal_data_collection_allowed",
    "qualified_reviewer_identity_recorded",
    "tax_readiness_claimed",
    "terms_privacy_approved",
    "trademark_clearance_claimed",
)
DEFERRAL_LABELS = (
    "qualified_review_scope_gate",
    "reviewer_identity_privacy_gate",
    "legal_conclusion_gate",
    "legal_clearance_gate",
    "trademark_clearance_gate",
    "patent_protection_gate",
    "company_formation_gate",
    "tax_readiness_gate",
    "terms_privacy_gate",
    "compliance_clearance_gate",
    "contractor_agreement_gate",
    "paid_launch_gate",
    "payment_processing_gate",
    "customer_data_gate",
    "publication_deployment_gate",
    "operator_reassessment_gate",
)
BLOCKED_CLAIMS = (
    "legal review completion",
    "qualified reviewer identity recording",
    "legal conclusion",
    "legal clearance",
    "trademark clearance",
    "patent protection",
    "company formation",
    "tax readiness",
    "terms/privacy approval",
    "compliance clearance",
    "contractor agreement",
    "paid launch",
    "payment processing",
    "customer access",
    "personal data collection",
    "money movement",
    "external publication",
    "deployment readiness",
)
SURFACE_NOTES_BY_ID = {
    "qualified_review_scope_gate": "Qualified review scope gate only; review scope closure is not claimed.",
    "reviewer_identity_privacy_gate": "Reviewer identity privacy gate only; reviewer identity is not recorded.",
    "legal_conclusion_gate": "Legal conclusion gate only; legal conclusions are not recorded or claimed.",
    "legal_clearance_gate": "Legal clearance gate only; legal clearance is not claimed.",
    "trademark_clearance_gate": "Trademark clearance gate only; trademark clearance is not claimed.",
    "patent_protection_gate": "Patent protection gate only; patent protection is not claimed.",
    "company_formation_gate": "Company formation gate only; company formation is not performed or claimed.",
    "tax_readiness_gate": "Tax readiness gate only; tax readiness is not claimed.",
    "terms_privacy_gate": "Terms/privacy gate only; terms and privacy readiness are not claimed.",
    "compliance_clearance_gate": "Compliance clearance gate only; compliance clearance is not claimed.",
    "contractor_agreement_gate": "Contractor agreement gate only; contractor agreements are not allowed.",
    "paid_launch_gate": "Paid launch gate only; paid launch is not allowed.",
    "payment_processing_gate": "Payment processing gate only; payment processing is not allowed.",
    "customer_data_gate": "Customer data gate only; customer access and personal data collection are not allowed.",
    "publication_deployment_gate": "Publication/deployment gate only; external publication and deployment are not allowed.",
    "operator_reassessment_gate": "Operator reassessment gate only; legal/business promotion is not approved.",
}
SURFACE_TYPES_BY_ID = {
    "qualified_review_scope_gate": "blocked_review_scope_label",
    "reviewer_identity_privacy_gate": "blocked_reviewer_identity_label",
    "legal_conclusion_gate": "blocked_conclusion_label",
    "legal_clearance_gate": "blocked_legal_clearance_label",
    "trademark_clearance_gate": "blocked_trademark_clearance_label",
    "patent_protection_gate": "blocked_patent_protection_label",
    "company_formation_gate": "blocked_company_formation_label",
    "tax_readiness_gate": "blocked_tax_readiness_label",
    "terms_privacy_gate": "blocked_terms_privacy_label",
    "compliance_clearance_gate": "blocked_compliance_clearance_label",
    "contractor_agreement_gate": "blocked_contractor_agreement_label",
    "paid_launch_gate": "blocked_paid_launch_label",
    "payment_processing_gate": "blocked_payment_processing_label",
    "customer_data_gate": "blocked_customer_data_label",
    "publication_deployment_gate": "blocked_publication_deployment_label",
    "operator_reassessment_gate": "local_gate_label",
}
REQUIRED_DOC_PHRASES = (
    "Foundation Legal Review Deferral Boundary",
    "Witness packet: [`../examples/foundation_legal_review_deferral_witness.awaiting_evidence.json`]",
    "Rule: Legal-review deferral is a local stop-rule packet",
    "No legal review completion claim, qualified reviewer identity recording, legal",
    "legal_review_deferral_state=AwaitingEvidence",
    "legal_review_complete_claimed=false",
    "qualified_reviewer_identity_recorded=false",
    "legal_conclusion_recorded=false",
    "legal_clearance_claimed=false",
    "trademark_clearance_claimed=false",
    "patent_protection_claimed=false",
    "company_formation_allowed=false",
    "tax_readiness_claimed=false",
    "terms_privacy_approved=false",
    "compliance_clearance_claimed=false",
    "contractor_agreement_allowed=false",
    "paid_launch_allowed=false",
    "payment_processing_allowed=false",
    "customer_access_allowed=false",
    "personal_data_collection_allowed=false",
    "money_movement_allowed=false",
    "external_publication_allowed=false",
    "deployment_allowed=false",
    "python scripts/validate_foundation_legal_review_deferral_boundary.py",
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
            r"\b(?:reviewer|counsel|lawyer|attorney|legal|conclusion|clearance|trademark|patent|"
            r"company|entity|formation|filing|tax|ein|terms|privacy|compliance|contractor|"
            r"payment|customer|tenant|secret|token|key|url|endpoint)\w*\s*=",
            re.IGNORECASE,
        ),
    ),
)
FORBIDDEN_PROMOTION_PATTERNS = (
    ("legal_review_complete", re.compile(r"\blegal review\s+(?:is\s+)?(?:complete|completed|approved)\b", re.IGNORECASE)),
    ("qualified_review_complete", re.compile(r"\bqualified review\s+(?:is\s+)?(?:complete|completed|approved)\b", re.IGNORECASE)),
    ("legal_conclusion_reached", re.compile(r"\blegal conclusion\s+(?:is\s+)?(?:reached|made|approved)\b", re.IGNORECASE)),
    ("legal_clearance_approved", re.compile(r"\blegal clearance\s+(?:is\s+)?(?:complete|granted|approved|secured)\b", re.IGNORECASE)),
    ("trademark_cleared", re.compile(r"\btrademark\s+(?:is\s+)?(?:cleared|approved|secured)\b", re.IGNORECASE)),
    ("patent_protected", re.compile(r"\bpatent\s+(?:is\s+)?(?:filed|submitted|protected|approved|secured)\b", re.IGNORECASE)),
    ("company_formed", re.compile(r"\b(?:company|entity)\s+(?:is\s+)?(?:formed|created|registered)\b", re.IGNORECASE)),
    ("tax_ready", re.compile(r"\btax\s+(?:is\s+)?(?:ready|approved|cleared)\b", re.IGNORECASE)),
    ("terms_privacy_ready", re.compile(r"\b(?:terms|privacy)\s+(?:is\s+|are\s+)?(?:ready|approved|cleared)\b", re.IGNORECASE)),
    ("compliance_cleared", re.compile(r"\bcompliance\s+(?:is\s+)?(?:cleared|approved|ready)\b", re.IGNORECASE)),
    ("contractor_allowed", re.compile(r"\bcontractor\s+(?:is\s+)?(?:allowed|approved|ready)\b", re.IGNORECASE)),
    ("paid_launch_open", re.compile(r"\bpaid launch\s+(?:is\s+)?(?:open|allowed|approved|ready)\b", re.IGNORECASE)),
    ("payment_enabled", re.compile(r"\bpayment processing\s+(?:is\s+)?(?:enabled|allowed|approved|ready)\b", re.IGNORECASE)),
    ("customer_access_open", re.compile(r"\bcustomer access\s+(?:is\s+)?(?:open|allowed|approved|ready)\b", re.IGNORECASE)),
    ("external_publication_approved", re.compile(r"\bexternal publication\s+(?:is\s+)?(?:allowed|approved|ready)\b", re.IGNORECASE)),
    ("deployment_ready", re.compile(r"\bdeployment\s+(?:is\s+)?(?:ready|approved|complete)\b", re.IGNORECASE)),
)


@dataclass(frozen=True, slots=True)
class Finding:
    """One deterministic legal-review deferral validation finding."""

    rule_id: str
    message: str


def load_text(path: Path, artifact_label: str) -> str:
    """Load one UTF-8 text artifact with explicit existence errors."""

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
    """Return findings for legal-review deferral surface inventory and state drift."""

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
    """Return findings for legal-review deferral packet drift."""

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
    if not isinstance(next_action, str) or "qualified review" not in next_action:
        findings.append(Finding("witness_next_action", "next_action must preserve legal-review deferral"))
    findings.extend(validate_surfaces(payload.get("surfaces")))
    findings.extend(validate_forbidden_text(payload))
    return findings


def validate_artifacts(
    doc_path: Path = DEFAULT_DOC_PATH,
    packet_path: Path = DEFAULT_PACKET_PATH,
) -> list[Finding]:
    """Validate the legal-review deferral doc and witness packet."""

    doc_text = load_text(doc_path, "legal-review deferral doc")
    payload = load_json_object(packet_path, "legal-review deferral witness")
    return [*validate_doc_text(doc_text), *validate_packet(payload)]


def main(argv: list[str] | None = None) -> int:
    """Run the legal-review deferral validator."""

    parser = argparse.ArgumentParser(description="Validate Foundation Mode legal-review deferral artifacts.")
    parser.add_argument("--doc", type=Path, default=DEFAULT_DOC_PATH)
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET_PATH)
    args = parser.parse_args(argv)

    try:
        findings = validate_artifacts(args.doc, args.packet)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"[FAIL] foundation_legal_review_deferral_load: {exc}", file=sys.stderr)
        print("STATUS: failed", file=sys.stderr)
        return 1
    if findings:
        for finding in findings:
            print(f"[FAIL] {finding.rule_id}: {finding.message}", file=sys.stderr)
        print("STATUS: failed", file=sys.stderr)
        return 1
    print("[PASS] foundation_legal_review_deferral_doc")
    print("[PASS] foundation_legal_review_deferral_witness")
    print("STATUS: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
