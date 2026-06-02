#!/usr/bin/env python3
"""Validate the Foundation Mode funding/team boundary.

Purpose: keep funding and team preparation local while fundraising, investor
outreach, grant applications, pitch publication, hiring, contractor engagement,
advisor commitments, compensation commitments, equity promises, payroll setup,
budget commitments, company-formation claims, legal-clearance claims, money
movement, external publication, and deployment claims remain blocked.
Governance scope: Foundation Mode, funding posture, team posture, public-safe
planning witness, private-value exclusion, obligation blocking, and deployment
blocking.
Dependencies: docs/FOUNDATION_FUNDING_TEAM_BOUNDARY.md and
examples/foundation_funding_team_witness.awaiting_evidence.json.
Invariants:
  - Validation is read-only.
  - The witness records local funding/team planning only.
  - No outside contact, money movement, hiring, contractor, advisor, payroll,
    equity, budget, legal, company, private value, publication, or deployment
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
DEFAULT_DOC_PATH = REPO_ROOT / "docs" / "FOUNDATION_FUNDING_TEAM_BOUNDARY.md"
DEFAULT_PACKET_PATH = REPO_ROOT / "examples" / "foundation_funding_team_witness.awaiting_evidence.json"

EXPECTED_WITNESS_ID = "foundation_funding_team_witness.awaiting_evidence.v1"
EXPECTED_BLOCKED_CLAIMS = (
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
    "company formation readiness",
    "legal clearance",
    "money movement",
    "external publication",
    "deployment readiness",
)
EXPECTED_SURFACES = (
    ("funding_readiness_questions", "local_draft", "AwaitingEvidence"),
    ("investor_boundary_questions", "local_draft", "AwaitingEvidence"),
    ("grant_program_questions", "local_draft", "AwaitingEvidence"),
    ("pitch_deck_questions", "local_draft", "AwaitingEvidence"),
    ("hiring_role_questions", "local_draft", "AwaitingEvidence"),
    ("contractor_engagement_questions", "local_draft", "AwaitingEvidence"),
    ("advisor_mentor_questions", "local_draft", "AwaitingEvidence"),
    ("compensation_equity_questions", "local_draft", "AwaitingEvidence"),
    ("payroll_budget_questions", "local_draft", "AwaitingEvidence"),
    ("public_recruiting_questions", "local_draft", "AwaitingEvidence"),
)
EXPECTED_ROOT_KEYS = {
    "advisor_commitment_allowed",
    "blocked_claims",
    "budget_commitment_allowed",
    "company_formation_claimed",
    "compensation_commitment_allowed",
    "contractor_engagement_allowed",
    "deployment_allowed",
    "equity_promise_allowed",
    "external_publication_allowed",
    "funding_team_surfaces",
    "fundraising_allowed",
    "grant_application_allowed",
    "hiring_allowed",
    "investor_outreach_allowed",
    "legal_clearance_claimed",
    "money_movement_allowed",
    "next_action",
    "payroll_setup_allowed",
    "pitch_deck_publication_allowed",
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
    "Foundation Funding Team Boundary",
    "Witness packet: [`../examples/foundation_funding_team_witness.awaiting_evidence.json`]",
    "Rule: Funding/team preparation is a local planning boundary, not fundraising, hiring, or team formation.",
    "No fundraising, investor outreach, grant application, pitch publication, hiring,",
    "funding_team_boundary_state=AwaitingEvidence",
    "fundraising_allowed=false",
    "investor_outreach_allowed=false",
    "grant_application_allowed=false",
    "pitch_deck_publication_allowed=false",
    "hiring_allowed=false",
    "contractor_engagement_allowed=false",
    "advisor_commitment_allowed=false",
    "compensation_commitment_allowed=false",
    "equity_promise_allowed=false",
    "payroll_setup_allowed=false",
    "budget_commitment_allowed=false",
    "company_formation_claimed=false",
    "legal_clearance_claimed=false",
    "money_movement_allowed=false",
    "external_publication_allowed=false",
    "deployment_allowed=false",
    "python scripts/validate_foundation_funding_team_boundary.py",
)
FORBIDDEN_VALUE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("url_value", re.compile(r"https?://", re.IGNORECASE)),
    ("email_value", re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)),
    ("private_path", re.compile(r"\b[A-Za-z]:[\\/]|\\\\", re.IGNORECASE)),
    ("currency_amount", re.compile(r"(?:\$|USD\s*)\d+(?:[,\d]*(?:\.\d{2})?)?", re.IGNORECASE)),
    ("investor_assignment", re.compile(r"\binvestor[_ -]?(?:id|name|email|target|list)\s*=", re.IGNORECASE)),
    ("grant_assignment", re.compile(r"\bgrant[_ -]?(?:id|program|application|target)\s*=", re.IGNORECASE)),
    ("job_assignment", re.compile(r"\b(?:job|role|candidate)[_ -]?(?:url|link|id|email)\s*=", re.IGNORECASE)),
    ("payroll_assignment", re.compile(r"\bpayroll[_ -]?(?:provider|account|id)\s*=", re.IGNORECASE)),
    ("equity_assignment", re.compile(r"\bequity[_ -]?(?:percent|share|grant|promise)\s*=", re.IGNORECASE)),
    ("compensation_assignment", re.compile(r"\b(?:salary|rate|compensation)\s*=", re.IGNORECASE)),
    ("secret_assignment", re.compile(r"\b(?:password|secret|token|api[_ -]?key)\s*=", re.IGNORECASE)),
    ("private_key_material", re.compile(r"BEGIN [A-Z ]*PRIVATE KEY")),
)
FORBIDDEN_PROMOTION_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("fundraising_ready", re.compile(r"\bfundraising\s+(?:is\s+)?(?:ready|open|active|launched)\b", re.IGNORECASE)),
    ("funding_secured", re.compile(r"\bfunding\s+(?:is\s+)?secured\b", re.IGNORECASE)),
    ("investor_outreach_started", re.compile(r"\binvestor\s+outreach\s+(?:has\s+)?started\b", re.IGNORECASE)),
    ("grant_submitted", re.compile(r"\bgrant\s+(?:application\s+)?(?:submitted|filed)\b", re.IGNORECASE)),
    ("pitch_published", re.compile(r"\bpitch\s+(?:deck\s+)?(?:published|sent|live)\b", re.IGNORECASE)),
    ("hiring_open", re.compile(r"\bhiring\s+(?:is\s+)?open\b", re.IGNORECASE)),
    ("job_post_live", re.compile(r"\bjob\s+post\s+(?:is\s+)?live\b", re.IGNORECASE)),
    ("contractor_engaged", re.compile(r"\bcontractor\s+(?:is\s+)?engaged\b", re.IGNORECASE)),
    ("advisor_committed", re.compile(r"\badvisor\s+(?:is\s+)?committed\b", re.IGNORECASE)),
    ("compensation_approved", re.compile(r"\bcompensation\s+(?:is\s+)?approved\b", re.IGNORECASE)),
    ("equity_promised", re.compile(r"\bequity\s+(?:is\s+)?promised\b", re.IGNORECASE)),
    (
        "payroll_ready",
        re.compile(
            r"\bpayroll\s+(?:is\s+)?ready\b|\bpayroll\s+(?:setup|set up)\s+(?:complete|ready|active)\b",
            re.IGNORECASE,
        ),
    ),
    ("budget_approved", re.compile(r"\bbudget\s+(?:is\s+)?approved\b", re.IGNORECASE)),
    ("team_ready", re.compile(r"\bteam\s+(?:is\s+)?ready\b", re.IGNORECASE)),
)


@dataclass(frozen=True, slots=True)
class FundingTeamFinding:
    """One deterministic funding/team boundary validation finding."""

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


def validate_doc_text(text: str) -> list[FundingTeamFinding]:
    """Return findings for missing funding/team documentation anchors."""

    findings: list[FundingTeamFinding] = []
    for phrase in REQUIRED_DOC_PHRASES:
        if phrase not in text:
            findings.append(
                FundingTeamFinding(
                    "foundation_funding_team_doc_phrase_missing",
                    f"funding/team boundary doc missing required phrase: {phrase}",
                )
            )
    return findings


def validate_packet(payload: dict[str, Any]) -> list[FundingTeamFinding]:
    """Return findings for funding/team witness drift."""

    findings: list[FundingTeamFinding] = []
    findings.extend(validate_root_contract(payload))
    findings.extend(validate_funding_team_surfaces(payload.get("funding_team_surfaces")))
    findings.extend(validate_forbidden_value_patterns(payload))
    findings.extend(validate_forbidden_promotion_patterns(payload))
    return findings


def validate_root_contract(payload: dict[str, Any]) -> list[FundingTeamFinding]:
    """Return findings for root-level funding/team witness drift."""

    findings: list[FundingTeamFinding] = []
    if set(payload) != EXPECTED_ROOT_KEYS:
        findings.append(
            FundingTeamFinding(
                "funding_team_root_keys_invalid",
                f"root keys must be: {', '.join(sorted(EXPECTED_ROOT_KEYS))}",
            )
        )
    expected_values = {
        "witness_id": EXPECTED_WITNESS_ID,
        "schema_version": 1,
        "status": "AwaitingEvidence",
        "solver_outcome": "AwaitingEvidence",
        "fundraising_allowed": False,
        "investor_outreach_allowed": False,
        "grant_application_allowed": False,
        "pitch_deck_publication_allowed": False,
        "hiring_allowed": False,
        "contractor_engagement_allowed": False,
        "advisor_commitment_allowed": False,
        "compensation_commitment_allowed": False,
        "equity_promise_allowed": False,
        "payroll_setup_allowed": False,
        "budget_commitment_allowed": False,
        "company_formation_claimed": False,
        "legal_clearance_claimed": False,
        "money_movement_allowed": False,
        "external_publication_allowed": False,
        "deployment_allowed": False,
    }
    for key, expected_value in expected_values.items():
        if payload.get(key) != expected_value:
            findings.append(
                FundingTeamFinding(
                    "funding_team_root_value_invalid",
                    f"{key} must be {expected_value!r}",
                )
            )
    if tuple(payload.get("blocked_claims") or ()) != EXPECTED_BLOCKED_CLAIMS:
        findings.append(
            FundingTeamFinding(
                "funding_team_blocked_claims_invalid",
                f"blocked_claims must be: {', '.join(EXPECTED_BLOCKED_CLAIMS)}",
            )
        )
    next_action = payload.get("next_action")
    if not isinstance(next_action, str) or "keep funding and team preparation local" not in next_action:
        findings.append(
            FundingTeamFinding(
                "funding_team_next_action_invalid",
                "next_action must preserve the local funding/team boundary",
            )
        )
    return findings


def validate_funding_team_surfaces(funding_team_surfaces: object) -> list[FundingTeamFinding]:
    """Return findings for funding/team surface witness drift."""

    findings: list[FundingTeamFinding] = []
    if not isinstance(funding_team_surfaces, list) or not all(
        isinstance(surface, dict) for surface in funding_team_surfaces
    ):
        return [
            FundingTeamFinding(
                "funding_team_surfaces_invalid",
                "funding_team_surfaces must be a list of objects",
            )
        ]
    observed_surfaces = tuple(
        (surface.get("surface_id"), surface.get("surface_type"), surface.get("state"))
        for surface in funding_team_surfaces
    )
    if observed_surfaces != EXPECTED_SURFACES:
        findings.append(
            FundingTeamFinding(
                "funding_team_surface_inventory_invalid",
                "funding/team surface inventory does not match the Foundation Mode funding/team set",
            )
        )
    surface_ids = [surface.get("surface_id") for surface in funding_team_surfaces]
    if len(set(surface_ids)) != len(surface_ids):
        findings.append(FundingTeamFinding("funding_team_surface_duplicate", "surface ids must be unique"))
    for surface in funding_team_surfaces:
        surface_id = str(surface.get("surface_id", "<missing>"))
        if set(surface) != EXPECTED_SURFACE_KEYS:
            findings.append(
                FundingTeamFinding(
                    "funding_team_surface_keys_invalid",
                    f"{surface_id} surface keys must be: {', '.join(sorted(EXPECTED_SURFACE_KEYS))}",
                )
            )
        if surface.get("state") != "AwaitingEvidence":
            findings.append(
                FundingTeamFinding(
                    "funding_team_surface_state_invalid",
                    f"{surface_id} state must be AwaitingEvidence",
                )
            )
        if surface.get("evidence_ref") != "manual_preparation_pending":
            findings.append(
                FundingTeamFinding(
                    "funding_team_surface_evidence_invalid",
                    f"{surface_id} evidence_ref must stay manual_preparation_pending in the committed packet",
                )
            )
        if not isinstance(surface.get("public_safe_note"), str) or not surface["public_safe_note"].strip():
            findings.append(
                FundingTeamFinding(
                    "funding_team_surface_note_invalid",
                    f"{surface_id} public_safe_note must be a non-empty string",
                )
            )
    return findings


def validate_forbidden_value_patterns(payload: dict[str, Any]) -> list[FundingTeamFinding]:
    """Return findings for URL, email, money, employment, equity, secret, or private path values."""

    serialized_payload = json.dumps(payload, sort_keys=True)
    findings: list[FundingTeamFinding] = []
    for rule_id, pattern in FORBIDDEN_VALUE_PATTERNS:
        if pattern.search(serialized_payload):
            findings.append(
                FundingTeamFinding(
                    "funding_team_forbidden_private_value_pattern",
                    f"funding/team witness contains forbidden private value pattern: {rule_id}",
                )
            )
    return findings


def validate_forbidden_promotion_patterns(payload: dict[str, Any]) -> list[FundingTeamFinding]:
    """Return findings for funding/team readiness or activation claims."""

    serialized_payload = json.dumps(payload, sort_keys=True)
    findings: list[FundingTeamFinding] = []
    for rule_id, pattern in FORBIDDEN_PROMOTION_PATTERNS:
        if pattern.search(serialized_payload):
            findings.append(
                FundingTeamFinding(
                    "funding_team_forbidden_promotion_phrase",
                    f"funding/team witness contains forbidden promotion phrase: {rule_id}",
                )
            )
    return findings


def validate_foundation_funding_team_boundary(
    doc_path: Path = DEFAULT_DOC_PATH,
    packet_path: Path = DEFAULT_PACKET_PATH,
) -> list[FundingTeamFinding]:
    """Return all funding/team boundary validation findings."""

    doc_text = load_text(doc_path, "funding/team boundary doc")
    payload = load_json_object(packet_path, "funding/team witness")
    findings: list[FundingTeamFinding] = []
    findings.extend(validate_doc_text(doc_text))
    findings.extend(validate_packet(payload))
    return findings


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--doc", type=Path, default=DEFAULT_DOC_PATH)
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET_PATH)
    return parser.parse_args()


def main() -> int:
    """Run the funding/team boundary validator."""

    args = parse_args()
    findings = validate_foundation_funding_team_boundary(args.doc, args.packet)
    if findings:
        for finding in findings:
            print(f"[FAIL] {finding.rule_id}: {finding.message}", file=sys.stderr)
        print("STATUS: failed", file=sys.stderr)
        return 1
    print("[PASS] foundation_funding_team_doc")
    print("[PASS] foundation_funding_team_witness")
    print("STATUS: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
