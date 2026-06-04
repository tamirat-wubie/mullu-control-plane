#!/usr/bin/env python3
"""Validate the Foundation Mode legal/business question rehearsal boundary.

Purpose: keep legal/business question rehearsal local and public-safe while
legal conclusions, qualified review completion, company formation, filings,
tax readiness, terms/privacy readiness, team commitments, paid launch, payment
processing, money movement, customer access, external publication, private
reviewer material, and deployment remain blocked.
Governance scope: Foundation Mode, local legal/business preparation,
qualified-review gating, claim blocking, private-material exclusion,
customer-access blocking, paid-launch blocking, money-movement blocking,
external-publication blocking, and deployment blocking.
Dependencies: docs/FOUNDATION_LEGAL_BUSINESS_QUESTION_REHEARSAL_BOUNDARY.md and
examples/foundation_legal_business_question_rehearsal_witness.awaiting_evidence.json.
Invariants:
  - Validation is read-only.
  - The witness records question organization only.
  - No legal conclusion, legal clearance, review completion, formation, filing,
    tax, terms/privacy, compliance, team, payment, money, customer, publication,
    private reviewer material, or deployment claim is allowed.
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
DEFAULT_DOC_PATH = REPO_ROOT / "docs" / "FOUNDATION_LEGAL_BUSINESS_QUESTION_REHEARSAL_BOUNDARY.md"
DEFAULT_PACKET_PATH = REPO_ROOT / "examples" / "foundation_legal_business_question_rehearsal_witness.awaiting_evidence.json"

EXPECTED_WITNESS_ID = "foundation_legal_business_question_rehearsal_witness.awaiting_evidence.v1"
EXPECTED_BLOCKED_CLAIMS = (
    "legal conclusion",
    "legal clearance",
    "qualified review completion",
    "company formation",
    "company readiness",
    "patent filing",
    "patent protection",
    "trademark clearance",
    "tax readiness",
    "terms/privacy readiness",
    "compliance clearance",
    "contractor/team commitment",
    "paid launch",
    "payment processing",
    "money movement",
    "customer access",
    "external publication",
    "secret/private reviewer material",
    "deployment readiness",
)
EXPECTED_SURFACES = (
    ("ownership_invention_questions", "local_draft", "AwaitingEvidence"),
    ("naming_trademark_questions", "local_draft", "AwaitingEvidence"),
    ("formation_timing_questions", "local_draft", "AwaitingEvidence"),
    ("tax_accounting_questions", "local_draft", "AwaitingEvidence"),
    ("terms_privacy_questions", "local_draft", "AwaitingEvidence"),
    ("patent_invention_questions", "local_draft", "AwaitingEvidence"),
    ("compliance_data_questions", "local_draft", "AwaitingEvidence"),
    ("finance_payment_questions", "local_draft", "AwaitingEvidence"),
    ("contractor_team_questions", "local_draft", "AwaitingEvidence"),
    ("support_liability_questions", "local_draft", "AwaitingEvidence"),
    ("qualified_review_handoff", "local_draft", "AwaitingEvidence"),
)
EXPECTED_ROOT_KEYS = {
    "blocked_claims",
    "company_formation_allowed",
    "company_readiness_claimed",
    "compliance_clearance_claimed",
    "contractor_team_commitment_allowed",
    "customer_access_allowed",
    "deployment_allowed",
    "external_publication_allowed",
    "legal_clearance_claimed",
    "legal_conclusion_claimed",
    "money_movement_allowed",
    "next_action",
    "paid_launch_allowed",
    "patent_filing_allowed",
    "patent_protection_claimed",
    "payment_processing_allowed",
    "qualified_review_completed",
    "question_rehearsal_executed",
    "schema_version",
    "secret_or_private_reviewer_material_allowed",
    "solver_outcome",
    "status",
    "surfaces",
    "tax_readiness_claimed",
    "terms_privacy_readiness_claimed",
    "trademark_clearance_claimed",
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
    "Foundation Legal Business Question Rehearsal Boundary",
    "Witness packet: [`../examples/foundation_legal_business_question_rehearsal_witness.awaiting_evidence.json`]",
    "Rule: Legal/business question rehearsal is a local paper exercise",
    "No legal conclusion, legal clearance, qualified review completion,",
    "legal_business_question_rehearsal_boundary_state=AwaitingEvidence",
    "question_rehearsal_executed=false",
    "legal_conclusion_claimed=false",
    "legal_clearance_claimed=false",
    "company_formation_allowed=false",
    "paid_launch_allowed=false",
    "money_movement_allowed=false",
    "customer_access_allowed=false",
    "deployment_allowed=false",
    "python scripts/validate_foundation_legal_business_question_rehearsal_boundary.py",
)
FORBIDDEN_VALUE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("url_value", re.compile(r"https?://", re.IGNORECASE)),
    ("email_value", re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)),
    ("private_path", re.compile(r"\b[A-Za-z]:[\\/]|\\\\", re.IGNORECASE)),
    ("private_key_block", re.compile(r"-----BEGIN\s+(?:RSA\s+|EC\s+|OPENSSH\s+)?PRIVATE\s+KEY-----", re.IGNORECASE)),
    (
        "legal_business_assignment",
        re.compile(
            r"\b(?:account|reviewer|counsel|legal|company|entity|formation|filing|"
            r"patent|trademark|tax|ein|payment|customer|tenant|secret|private[_ -]?key)"
            r"[_ -]?(?:id|number|ref|target|value|status|token|name|application)?\s*=",
            re.IGNORECASE,
        ),
    ),
    (
        "deployment_assignment",
        re.compile(r"\b(?:deploy|deployment|production|staging)[_ -]?(?:target|url|ref|value|status)?\s*=", re.IGNORECASE),
    ),
)
FORBIDDEN_PROMOTION_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("legal_conclusion_reached", re.compile(r"\blegal conclusion (?:reached|made|approved)\b", re.IGNORECASE)),
    ("legal_clearance_approved", re.compile(r"\blegal clearance (?:complete|granted|approved|secured)\b", re.IGNORECASE)),
    ("qualified_review_complete", re.compile(r"\bqualified review (?:complete|completed|approved)\b", re.IGNORECASE)),
    ("company_formed", re.compile(r"\b(?:company|entity) (?:formed|created|registered)\b", re.IGNORECASE)),
    ("company_ready", re.compile(r"\bcompany (?:is )?ready\b", re.IGNORECASE)),
    ("patent_filed", re.compile(r"\bpatent (?:filed|submitted|protected|approved)\b", re.IGNORECASE)),
    ("trademark_cleared", re.compile(r"\btrademark (?:cleared|approved|secured)\b", re.IGNORECASE)),
    ("tax_ready", re.compile(r"\btax (?:is )?ready\b", re.IGNORECASE)),
    ("terms_ready", re.compile(r"\bterms (?:are |is )?ready\b", re.IGNORECASE)),
    ("privacy_ready", re.compile(r"\bprivacy (?:is )?ready\b", re.IGNORECASE)),
    ("compliance_cleared", re.compile(r"\bcompliance (?:cleared|approved|ready)\b", re.IGNORECASE)),
    ("contractor_team_ready", re.compile(r"\b(?:contractor|team) (?:is )?ready\b", re.IGNORECASE)),
    ("paid_launch_open", re.compile(r"\bpaid launch (?:open|allowed|approved|ready)\b", re.IGNORECASE)),
    ("money_movement_allowed", re.compile(r"\bmoney movement (?:allowed|approved|ready)\b", re.IGNORECASE)),
    ("customer_access_open", re.compile(r"\bcustomer access (?:open|allowed|ready)\b", re.IGNORECASE)),
    ("external_publication_approved", re.compile(r"\bexternal publication (?:allowed|approved|ready)\b", re.IGNORECASE)),
    ("deployment_ready", re.compile(r"\bdeployment (?:is )?ready\b", re.IGNORECASE)),
)


@dataclass(frozen=True, slots=True)
class LegalBusinessQuestionRehearsalFinding:
    """One deterministic legal/business question rehearsal validation finding."""

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


def validate_doc_text(text: str) -> list[LegalBusinessQuestionRehearsalFinding]:
    """Return findings for missing legal/business question rehearsal documentation anchors."""

    findings: list[LegalBusinessQuestionRehearsalFinding] = []
    for phrase in REQUIRED_DOC_PHRASES:
        if phrase not in text:
            findings.append(
                LegalBusinessQuestionRehearsalFinding(
                    "foundation_legal_business_question_rehearsal_doc_phrase_missing",
                    f"legal/business question rehearsal boundary doc missing required phrase: {phrase}",
                )
            )
    return findings


def validate_packet(payload: dict[str, Any]) -> list[LegalBusinessQuestionRehearsalFinding]:
    """Return findings for legal/business question rehearsal witness drift."""

    findings: list[LegalBusinessQuestionRehearsalFinding] = []
    findings.extend(validate_root_contract(payload))
    findings.extend(validate_surfaces(payload.get("surfaces")))
    findings.extend(validate_forbidden_value_patterns(payload))
    findings.extend(validate_forbidden_promotion_patterns(payload))
    return findings


def validate_root_contract(payload: dict[str, Any]) -> list[LegalBusinessQuestionRehearsalFinding]:
    """Return findings for root-level legal/business question rehearsal witness drift."""

    findings: list[LegalBusinessQuestionRehearsalFinding] = []
    if set(payload) != EXPECTED_ROOT_KEYS:
        findings.append(
            LegalBusinessQuestionRehearsalFinding(
                "legal_business_question_rehearsal_root_keys_invalid",
                f"root keys must be: {', '.join(sorted(EXPECTED_ROOT_KEYS))}",
            )
        )
    expected_values = {
        "witness_id": EXPECTED_WITNESS_ID,
        "schema_version": 1,
        "status": "AwaitingEvidence",
        "solver_outcome": "AwaitingEvidence",
        "question_rehearsal_executed": False,
        "legal_conclusion_claimed": False,
        "legal_clearance_claimed": False,
        "qualified_review_completed": False,
        "company_formation_allowed": False,
        "company_readiness_claimed": False,
        "patent_filing_allowed": False,
        "patent_protection_claimed": False,
        "trademark_clearance_claimed": False,
        "tax_readiness_claimed": False,
        "terms_privacy_readiness_claimed": False,
        "compliance_clearance_claimed": False,
        "contractor_team_commitment_allowed": False,
        "paid_launch_allowed": False,
        "payment_processing_allowed": False,
        "money_movement_allowed": False,
        "customer_access_allowed": False,
        "external_publication_allowed": False,
        "secret_or_private_reviewer_material_allowed": False,
        "deployment_allowed": False,
    }
    for key, expected_value in expected_values.items():
        if payload.get(key) != expected_value:
            findings.append(
                LegalBusinessQuestionRehearsalFinding(
                    "legal_business_question_rehearsal_root_value_invalid",
                    f"{key} must be {expected_value!r}",
                )
            )
    if tuple(payload.get("blocked_claims") or ()) != EXPECTED_BLOCKED_CLAIMS:
        findings.append(
            LegalBusinessQuestionRehearsalFinding(
                "legal_business_question_rehearsal_blocked_claims_invalid",
                f"blocked_claims must be: {', '.join(EXPECTED_BLOCKED_CLAIMS)}",
            )
        )
    next_action = payload.get("next_action")
    if not isinstance(next_action, str) or "draft public-safe local legal/business question categories only" not in next_action:
        findings.append(
            LegalBusinessQuestionRehearsalFinding(
                "legal_business_question_rehearsal_next_action_invalid",
                "next_action must preserve local public-safe legal/business question drafting only",
            )
        )
    return findings


def validate_surfaces(surfaces: object) -> list[LegalBusinessQuestionRehearsalFinding]:
    """Return findings for legal/business question rehearsal surface drift."""

    findings: list[LegalBusinessQuestionRehearsalFinding] = []
    if not isinstance(surfaces, list) or not all(isinstance(surface, dict) for surface in surfaces):
        return [LegalBusinessQuestionRehearsalFinding("legal_business_question_rehearsal_surfaces_invalid", "surfaces must be a list")]
    observed_surfaces = tuple(
        (surface.get("surface_id"), surface.get("surface_type"), surface.get("state"))
        for surface in surfaces
    )
    if observed_surfaces != EXPECTED_SURFACES:
        findings.append(
            LegalBusinessQuestionRehearsalFinding(
                "legal_business_question_rehearsal_surface_inventory_invalid",
                "legal/business question rehearsal surface inventory does not match the expected set",
            )
        )
    surface_ids = [surface.get("surface_id") for surface in surfaces]
    if len(set(surface_ids)) != len(surface_ids):
        findings.append(LegalBusinessQuestionRehearsalFinding("legal_business_question_rehearsal_surface_duplicate", "surface ids must be unique"))
    for surface in surfaces:
        surface_id = str(surface.get("surface_id", "<missing>"))
        if set(surface) != EXPECTED_SURFACE_KEYS:
            findings.append(
                LegalBusinessQuestionRehearsalFinding(
                    "legal_business_question_rehearsal_surface_keys_invalid",
                    f"{surface_id} surface keys must be: {', '.join(sorted(EXPECTED_SURFACE_KEYS))}",
                )
            )
        if surface.get("state") != "AwaitingEvidence":
            findings.append(
                LegalBusinessQuestionRehearsalFinding(
                    "legal_business_question_rehearsal_surface_state_invalid",
                    f"{surface_id} state must be AwaitingEvidence",
                )
            )
        if surface.get("evidence_ref") != "manual_preparation_pending":
            findings.append(
                LegalBusinessQuestionRehearsalFinding(
                    "legal_business_question_rehearsal_surface_evidence_invalid",
                    f"{surface_id} evidence_ref must stay manual_preparation_pending",
                )
            )
        if not isinstance(surface.get("public_safe_note"), str) or not surface["public_safe_note"].strip():
            findings.append(
                LegalBusinessQuestionRehearsalFinding(
                    "legal_business_question_rehearsal_surface_note_invalid",
                    f"{surface_id} public_safe_note must be a non-empty string",
                )
            )
    return findings


def validate_forbidden_value_patterns(payload: dict[str, Any]) -> list[LegalBusinessQuestionRehearsalFinding]:
    """Return findings for reviewer, filing, account, customer, secret, payment, or deployment-shaped values."""

    serialized_payload = json.dumps(payload, sort_keys=True)
    findings: list[LegalBusinessQuestionRehearsalFinding] = []
    for rule_id, pattern in FORBIDDEN_VALUE_PATTERNS:
        if pattern.search(serialized_payload):
            findings.append(
                LegalBusinessQuestionRehearsalFinding(
                    "legal_business_question_rehearsal_forbidden_value_pattern",
                    f"legal/business question rehearsal witness contains forbidden value pattern: {rule_id}",
                )
            )
    return findings


def validate_forbidden_promotion_patterns(payload: dict[str, Any]) -> list[LegalBusinessQuestionRehearsalFinding]:
    """Return findings if the witness drifts into legal/business readiness claims."""

    serialized_payload = json.dumps(payload, sort_keys=True)
    findings: list[LegalBusinessQuestionRehearsalFinding] = []
    for rule_id, pattern in FORBIDDEN_PROMOTION_PATTERNS:
        if pattern.search(serialized_payload):
            findings.append(
                LegalBusinessQuestionRehearsalFinding(
                    "legal_business_question_rehearsal_forbidden_promotion_phrase",
                    f"legal/business question rehearsal witness contains forbidden promotion pattern: {rule_id}",
                )
            )
    return findings


def validate_foundation_legal_business_question_rehearsal_boundary(
    doc_path: Path = DEFAULT_DOC_PATH,
    packet_path: Path = DEFAULT_PACKET_PATH,
) -> list[LegalBusinessQuestionRehearsalFinding]:
    """Validate the Foundation Mode legal/business question rehearsal boundary artifacts."""

    doc_text = load_text(doc_path, "legal/business question rehearsal boundary doc")
    packet_payload = load_json_object(packet_path, "legal/business question rehearsal witness packet")
    return [
        *validate_doc_text(doc_text),
        *validate_packet(packet_payload),
    ]


def main(argv: list[str] | None = None) -> int:
    """Validate legal/business question rehearsal artifacts and print deterministic status."""

    parser = argparse.ArgumentParser(description="Validate Foundation Mode legal/business question rehearsal boundary artifacts.")
    parser.add_argument("--doc", type=Path, default=DEFAULT_DOC_PATH)
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET_PATH)
    args = parser.parse_args(argv)

    try:
        findings = validate_foundation_legal_business_question_rehearsal_boundary(args.doc, args.packet)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"[FAIL] foundation_legal_business_question_rehearsal_load: {exc}", file=sys.stderr)
        print("STATUS: failed", file=sys.stderr)
        return 1

    if findings:
        for finding in findings:
            print(f"[FAIL] {finding.rule_id}: {finding.message}", file=sys.stderr)
        print("STATUS: failed", file=sys.stderr)
        return 1
    print("[PASS] foundation_legal_business_question_rehearsal_doc")
    print("[PASS] foundation_legal_business_question_rehearsal_witness")
    print("STATUS: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
