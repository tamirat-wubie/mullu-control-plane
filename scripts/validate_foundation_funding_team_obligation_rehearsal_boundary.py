#!/usr/bin/env python3
"""Validate the Foundation Mode funding/team obligation rehearsal boundary.

Purpose: keep funding/team obligation rehearsal local and public-safe while
fundraising, investor outreach, grants, pitch publication, hiring, contractors,
advisors, compensation, equity, payroll, budget commitment, spending, company
or legal claims, customer access, contact-list storage, money movement,
external publication, secret material, and deployment remain blocked.
Governance scope: Foundation Mode, funding/team obligation rehearsal,
public-safe local planning, contact-list exclusion, obligation blocking,
money-movement blocking, legal/company blocking, customer-access blocking,
external-publication blocking, and deployment blocking.
Dependencies: docs/FOUNDATION_FUNDING_TEAM_OBLIGATION_REHEARSAL_BOUNDARY.md and
examples/foundation_funding_team_obligation_rehearsal_witness.awaiting_evidence.json.
Invariants:
  - Validation is read-only.
  - The witness records obligation questions only.
  - No funding, team, outside contact, hiring, contractor, advisor, payroll,
    equity, budget, spending, legal, company, customer, private value,
    publication, or deployment claim is allowed.
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
DEFAULT_DOC_PATH = REPO_ROOT / "docs" / "FOUNDATION_FUNDING_TEAM_OBLIGATION_REHEARSAL_BOUNDARY.md"
DEFAULT_PACKET_PATH = REPO_ROOT / "examples" / "foundation_funding_team_obligation_rehearsal_witness.awaiting_evidence.json"

EXPECTED_WITNESS_ID = "foundation_funding_team_obligation_rehearsal_witness.awaiting_evidence.v1"
EXPECTED_BLOCKED_CLAIMS = (
    "funding readiness",
    "team readiness",
    "fundraising",
    "investor outreach",
    "grant application",
    "pitch publication",
    "hiring",
    "contractor engagement",
    "advisor commitment",
    "compensation commitment",
    "equity promise",
    "payroll setup",
    "budget commitment",
    "spending",
    "company formation readiness",
    "legal clearance",
    "customer access",
    "contact-list storage",
    "money movement",
    "external publication",
    "secret material",
    "deployment readiness",
)
EXPECTED_SURFACES = (
    ("solo_capacity_obligation_questions", "local_draft", "AwaitingEvidence"),
    ("funding_readiness_obligation_questions", "local_draft", "AwaitingEvidence"),
    ("investor_outreach_obligation_questions", "local_draft", "AwaitingEvidence"),
    ("grant_obligation_questions", "local_draft", "AwaitingEvidence"),
    ("pitch_publication_obligation_questions", "local_draft", "AwaitingEvidence"),
    ("hiring_obligation_questions", "local_draft", "AwaitingEvidence"),
    ("contractor_obligation_questions", "local_draft", "AwaitingEvidence"),
    ("advisor_obligation_questions", "local_draft", "AwaitingEvidence"),
    ("compensation_equity_obligation_questions", "local_draft", "AwaitingEvidence"),
    ("payroll_budget_obligation_questions", "local_draft", "AwaitingEvidence"),
    ("public_recruiting_stop_rule", "local_draft", "AwaitingEvidence"),
    ("legal_company_handoff", "local_draft", "AwaitingEvidence"),
)
EXPECTED_ROOT_KEYS = {
    "advisor_commitment_allowed",
    "blocked_claims",
    "budget_commitment_allowed",
    "company_formation_claimed",
    "compensation_commitment_allowed",
    "contact_list_storage_allowed",
    "contractor_engagement_allowed",
    "customer_access_allowed",
    "deployment_allowed",
    "equity_promise_allowed",
    "external_publication_allowed",
    "funding_readiness_claimed",
    "fundraising_allowed",
    "grant_application_allowed",
    "hiring_allowed",
    "investor_outreach_allowed",
    "legal_clearance_claimed",
    "money_movement_allowed",
    "next_action",
    "obligation_rehearsal_executed",
    "payroll_setup_allowed",
    "pitch_publication_allowed",
    "schema_version",
    "secret_material_allowed",
    "solver_outcome",
    "spending_allowed",
    "status",
    "surfaces",
    "team_readiness_claimed",
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
    "Foundation Funding Team Obligation Rehearsal Boundary",
    "Witness packet: [`../examples/foundation_funding_team_obligation_rehearsal_witness.awaiting_evidence.json`]",
    "Rule: Funding/team obligation rehearsal is a local paper exercise",
    "No funding readiness, team readiness, fundraising, investor outreach, grant",
    "funding_team_obligation_rehearsal_boundary_state=AwaitingEvidence",
    "obligation_rehearsal_executed=false",
    "funding_readiness_claimed=false",
    "team_readiness_claimed=false",
    "fundraising_allowed=false",
    "investor_outreach_allowed=false",
    "grant_application_allowed=false",
    "pitch_publication_allowed=false",
    "hiring_allowed=false",
    "contractor_engagement_allowed=false",
    "advisor_commitment_allowed=false",
    "compensation_commitment_allowed=false",
    "equity_promise_allowed=false",
    "payroll_setup_allowed=false",
    "budget_commitment_allowed=false",
    "spending_allowed=false",
    "company_formation_claimed=false",
    "legal_clearance_claimed=false",
    "customer_access_allowed=false",
    "contact_list_storage_allowed=false",
    "money_movement_allowed=false",
    "external_publication_allowed=false",
    "secret_material_allowed=false",
    "deployment_allowed=false",
    "python scripts/validate_foundation_funding_team_obligation_rehearsal_boundary.py",
)
FORBIDDEN_VALUE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("url_value", re.compile(r"https?://", re.IGNORECASE)),
    ("email_value", re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)),
    ("private_path", re.compile(r"\b[A-Za-z]:[\\/]|\\\\", re.IGNORECASE)),
    ("currency_amount", re.compile(r"(?:\$|USD\s*)\d+(?:[,\d]*(?:\.\d{2})?)?", re.IGNORECASE)),
    ("private_key_block", re.compile(r"-----BEGIN\s+(?:RSA\s+|EC\s+|OPENSSH\s+)?PRIVATE\s+KEY-----", re.IGNORECASE)),
    (
        "obligation_assignment",
        re.compile(
            r"\b(?:investor|contact|grant|application|pitch|deck|job|role|candidate|"
            r"contractor|vendor|advisor|mentor|payroll|equity|salary|rate|"
            r"compensation|payment|invoice|budget|account|tenant|secret|token|"
            r"api[_ -]?key|private[_ -]?key)"
            r"[_ -]?(?:id|name|email|target|list|url|link|program|application|"
            r"provider|account|percent|share|grant|promise|amount|status|value)?\s*=",
            re.IGNORECASE,
        ),
    ),
    (
        "deployment_assignment",
        re.compile(r"\b(?:deploy|deployment|production|staging)[_ -]?(?:target|url|ref|value|status)?\s*=", re.IGNORECASE),
    ),
)
FORBIDDEN_PROMOTION_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("funding_ready", re.compile(r"\bfunding\s+(?:is\s+)?(?:ready|secured|approved)\b", re.IGNORECASE)),
    ("team_ready", re.compile(r"\bteam\s+(?:is\s+)?ready\b", re.IGNORECASE)),
    ("fundraising_ready", re.compile(r"\bfundraising\s+(?:is\s+)?(?:ready|open|active|launched)\b", re.IGNORECASE)),
    ("investor_outreach_started", re.compile(r"\binvestor\s+outreach\s+(?:has\s+)?started\b", re.IGNORECASE)),
    ("contact_list_ready", re.compile(r"\bcontact\s+list\s+(?:is\s+)?ready\b", re.IGNORECASE)),
    ("grant_submitted", re.compile(r"\bgrant\s+(?:application\s+)?(?:submitted|filed|approved)\b", re.IGNORECASE)),
    ("pitch_published", re.compile(r"\bpitch\s+(?:deck\s+)?(?:published|sent|live)\b", re.IGNORECASE)),
    ("hiring_open", re.compile(r"\bhiring\s+(?:is\s+)?open\b", re.IGNORECASE)),
    ("job_post_live", re.compile(r"\bjob\s+post\s+(?:is\s+)?live\b", re.IGNORECASE)),
    ("contractor_engaged", re.compile(r"\bcontractor\s+(?:is\s+)?engaged\b", re.IGNORECASE)),
    ("advisor_committed", re.compile(r"\badvisor\s+(?:is\s+)?committed\b", re.IGNORECASE)),
    ("compensation_approved", re.compile(r"\bcompensation\s+(?:is\s+)?approved\b", re.IGNORECASE)),
    ("equity_promised", re.compile(r"\bequity\s+(?:is\s+)?promised\b", re.IGNORECASE)),
    ("payroll_ready", re.compile(r"\bpayroll\s+(?:is\s+)?(?:ready|active|complete)\b", re.IGNORECASE)),
    ("budget_approved", re.compile(r"\bbudget\s+(?:is\s+)?approved\b", re.IGNORECASE)),
    ("spending_allowed", re.compile(r"\bspending\s+(?:is\s+)?allowed\b", re.IGNORECASE)),
    ("company_ready", re.compile(r"\bcompany\s+(?:is\s+)?ready\b", re.IGNORECASE)),
    ("legal_clearance_approved", re.compile(r"\blegal clearance (?:complete|granted|approved|secured)\b", re.IGNORECASE)),
    ("customer_access_open", re.compile(r"\bcustomer access (?:open|allowed|ready)\b", re.IGNORECASE)),
    ("money_movement_allowed", re.compile(r"\bmoney movement (?:allowed|approved|ready)\b", re.IGNORECASE)),
    ("external_publication_approved", re.compile(r"\bexternal publication (?:allowed|approved|ready)\b", re.IGNORECASE)),
    ("deployment_ready", re.compile(r"\bdeployment\s+(?:is\s+)?ready\b", re.IGNORECASE)),
)


@dataclass(frozen=True, slots=True)
class FundingTeamObligationRehearsalFinding:
    """One deterministic funding/team obligation rehearsal validation finding."""

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


def validate_doc_text(text: str) -> list[FundingTeamObligationRehearsalFinding]:
    """Return findings for missing funding/team obligation rehearsal documentation anchors."""

    findings: list[FundingTeamObligationRehearsalFinding] = []
    for phrase in REQUIRED_DOC_PHRASES:
        if phrase not in text:
            findings.append(
                FundingTeamObligationRehearsalFinding(
                    "foundation_funding_team_obligation_rehearsal_doc_phrase_missing",
                    f"funding/team obligation rehearsal boundary doc missing required phrase: {phrase}",
                )
            )
    return findings


def validate_packet(payload: dict[str, Any]) -> list[FundingTeamObligationRehearsalFinding]:
    """Return findings for funding/team obligation rehearsal witness drift."""

    findings: list[FundingTeamObligationRehearsalFinding] = []
    findings.extend(validate_root_contract(payload))
    findings.extend(validate_surfaces(payload.get("surfaces")))
    findings.extend(validate_forbidden_value_patterns(payload))
    findings.extend(validate_forbidden_promotion_patterns(payload))
    return findings


def validate_root_contract(payload: dict[str, Any]) -> list[FundingTeamObligationRehearsalFinding]:
    """Return findings for root-level funding/team obligation rehearsal witness drift."""

    findings: list[FundingTeamObligationRehearsalFinding] = []
    if set(payload) != EXPECTED_ROOT_KEYS:
        findings.append(
            FundingTeamObligationRehearsalFinding(
                "funding_team_obligation_rehearsal_root_keys_invalid",
                f"root keys must be: {', '.join(sorted(EXPECTED_ROOT_KEYS))}",
            )
        )
    expected_values = {
        "witness_id": EXPECTED_WITNESS_ID,
        "schema_version": 1,
        "status": "AwaitingEvidence",
        "solver_outcome": "AwaitingEvidence",
        "obligation_rehearsal_executed": False,
        "funding_readiness_claimed": False,
        "team_readiness_claimed": False,
        "fundraising_allowed": False,
        "investor_outreach_allowed": False,
        "grant_application_allowed": False,
        "pitch_publication_allowed": False,
        "hiring_allowed": False,
        "contractor_engagement_allowed": False,
        "advisor_commitment_allowed": False,
        "compensation_commitment_allowed": False,
        "equity_promise_allowed": False,
        "payroll_setup_allowed": False,
        "budget_commitment_allowed": False,
        "spending_allowed": False,
        "company_formation_claimed": False,
        "legal_clearance_claimed": False,
        "customer_access_allowed": False,
        "contact_list_storage_allowed": False,
        "money_movement_allowed": False,
        "external_publication_allowed": False,
        "secret_material_allowed": False,
        "deployment_allowed": False,
    }
    for key, expected_value in expected_values.items():
        if payload.get(key) != expected_value:
            findings.append(
                FundingTeamObligationRehearsalFinding(
                    "funding_team_obligation_rehearsal_root_value_invalid",
                    f"{key} must be {expected_value!r}",
                )
            )
    if tuple(payload.get("blocked_claims") or ()) != EXPECTED_BLOCKED_CLAIMS:
        findings.append(
            FundingTeamObligationRehearsalFinding(
                "funding_team_obligation_rehearsal_blocked_claims_invalid",
                f"blocked_claims must be: {', '.join(EXPECTED_BLOCKED_CLAIMS)}",
            )
        )
    next_action = payload.get("next_action")
    if not isinstance(next_action, str) or "draft local funding/team obligation questions only" not in next_action:
        findings.append(
            FundingTeamObligationRehearsalFinding(
                "funding_team_obligation_rehearsal_next_action_invalid",
                "next_action must preserve local funding/team obligation question drafting only",
            )
        )
    return findings


def validate_surfaces(surfaces: object) -> list[FundingTeamObligationRehearsalFinding]:
    """Return findings for funding/team obligation rehearsal surface drift."""

    findings: list[FundingTeamObligationRehearsalFinding] = []
    if not isinstance(surfaces, list) or not all(isinstance(surface, dict) for surface in surfaces):
        return [FundingTeamObligationRehearsalFinding("funding_team_obligation_rehearsal_surfaces_invalid", "surfaces must be a list")]
    observed_surfaces = tuple(
        (surface.get("surface_id"), surface.get("surface_type"), surface.get("state"))
        for surface in surfaces
    )
    if observed_surfaces != EXPECTED_SURFACES:
        findings.append(
            FundingTeamObligationRehearsalFinding(
                "funding_team_obligation_rehearsal_surface_inventory_invalid",
                "funding/team obligation rehearsal surface inventory does not match the expected set",
            )
        )
    surface_ids = [surface.get("surface_id") for surface in surfaces]
    if len(set(surface_ids)) != len(surface_ids):
        findings.append(FundingTeamObligationRehearsalFinding("funding_team_obligation_rehearsal_surface_duplicate", "surface ids must be unique"))
    for surface in surfaces:
        surface_id = str(surface.get("surface_id", "<missing>"))
        if set(surface) != EXPECTED_SURFACE_KEYS:
            findings.append(
                FundingTeamObligationRehearsalFinding(
                    "funding_team_obligation_rehearsal_surface_keys_invalid",
                    f"{surface_id} surface keys must be: {', '.join(sorted(EXPECTED_SURFACE_KEYS))}",
                )
            )
        if surface.get("state") != "AwaitingEvidence":
            findings.append(
                FundingTeamObligationRehearsalFinding(
                    "funding_team_obligation_rehearsal_surface_state_invalid",
                    f"{surface_id} state must be AwaitingEvidence",
                )
            )
        if surface.get("evidence_ref") != "manual_preparation_pending":
            findings.append(
                FundingTeamObligationRehearsalFinding(
                    "funding_team_obligation_rehearsal_surface_evidence_invalid",
                    f"{surface_id} evidence_ref must stay manual_preparation_pending",
                )
            )
        if not isinstance(surface.get("public_safe_note"), str) or not surface["public_safe_note"].strip():
            findings.append(
                FundingTeamObligationRehearsalFinding(
                    "funding_team_obligation_rehearsal_surface_note_invalid",
                    f"{surface_id} public_safe_note must be a non-empty string",
                )
            )
    return findings


def validate_forbidden_value_patterns(payload: dict[str, Any]) -> list[FundingTeamObligationRehearsalFinding]:
    """Return findings for outside-contact, money, employment, equity, account, secret, or deployment-shaped values."""

    serialized_payload = json.dumps(payload, sort_keys=True)
    findings: list[FundingTeamObligationRehearsalFinding] = []
    for rule_id, pattern in FORBIDDEN_VALUE_PATTERNS:
        if pattern.search(serialized_payload):
            findings.append(
                FundingTeamObligationRehearsalFinding(
                    "funding_team_obligation_rehearsal_forbidden_value_pattern",
                    f"funding/team obligation rehearsal witness contains forbidden value pattern: {rule_id}",
                )
            )
    return findings


def validate_forbidden_promotion_patterns(payload: dict[str, Any]) -> list[FundingTeamObligationRehearsalFinding]:
    """Return findings if the witness drifts into funding/team readiness or activation claims."""

    serialized_payload = json.dumps(payload, sort_keys=True)
    findings: list[FundingTeamObligationRehearsalFinding] = []
    for rule_id, pattern in FORBIDDEN_PROMOTION_PATTERNS:
        if pattern.search(serialized_payload):
            findings.append(
                FundingTeamObligationRehearsalFinding(
                    "funding_team_obligation_rehearsal_forbidden_promotion_phrase",
                    f"funding/team obligation rehearsal witness contains forbidden promotion pattern: {rule_id}",
                )
            )
    return findings


def validate_foundation_funding_team_obligation_rehearsal_boundary(
    doc_path: Path = DEFAULT_DOC_PATH,
    packet_path: Path = DEFAULT_PACKET_PATH,
) -> list[FundingTeamObligationRehearsalFinding]:
    """Validate the Foundation Mode funding/team obligation rehearsal boundary artifacts."""

    doc_text = load_text(doc_path, "funding/team obligation rehearsal boundary doc")
    packet_payload = load_json_object(packet_path, "funding/team obligation rehearsal witness packet")
    return [
        *validate_doc_text(doc_text),
        *validate_packet(packet_payload),
    ]


def main(argv: list[str] | None = None) -> int:
    """Validate funding/team obligation rehearsal artifacts and print deterministic status."""

    parser = argparse.ArgumentParser(description="Validate Foundation Mode funding/team obligation rehearsal boundary artifacts.")
    parser.add_argument("--doc", type=Path, default=DEFAULT_DOC_PATH)
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET_PATH)
    args = parser.parse_args(argv)

    try:
        findings = validate_foundation_funding_team_obligation_rehearsal_boundary(args.doc, args.packet)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"[FAIL] foundation_funding_team_obligation_rehearsal_load: {exc}", file=sys.stderr)
        print("STATUS: failed", file=sys.stderr)
        return 1

    if findings:
        for finding in findings:
            print(f"[FAIL] {finding.rule_id}: {finding.message}", file=sys.stderr)
        print("STATUS: failed", file=sys.stderr)
        return 1
    print("[PASS] foundation_funding_team_obligation_rehearsal_doc")
    print("[PASS] foundation_funding_team_obligation_rehearsal_witness")
    print("STATUS: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
