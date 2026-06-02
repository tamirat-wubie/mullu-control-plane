#!/usr/bin/env python3
"""Validate the Foundation Mode market-research boundary.

Purpose: keep market-research and comparison preparation local while customer
research, surveys, waitlists, outreach, market validation, product-market-fit,
pricing, public-offer, investor, personal-data, customer-access,
money-movement, publication, and deployment claims remain blocked.
Governance scope: Foundation Mode, public-safe market-research questions,
comparison planning, private-value exclusion, customer-research blocking,
publication blocking, money-movement blocking, and deployment blocking.
Dependencies: docs/FOUNDATION_MARKET_RESEARCH_BOUNDARY.md and
examples/foundation_market_research_witness.awaiting_evidence.json.
Invariants:
  - Validation is read-only.
  - The witness records local market-research planning only.
  - No customer research, survey, waitlist, outreach, market validation,
    product-market-fit, competitor superiority, pricing, investor material,
    personal data, customer access, money movement, publication, or deployment
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
DEFAULT_DOC_PATH = REPO_ROOT / "docs" / "FOUNDATION_MARKET_RESEARCH_BOUNDARY.md"
DEFAULT_PACKET_PATH = REPO_ROOT / "examples" / "foundation_market_research_witness.awaiting_evidence.json"

EXPECTED_WITNESS_ID = "foundation_market_research_witness.awaiting_evidence.v1"
EXPECTED_BLOCKED_CLAIMS = (
    "customer research",
    "survey publication",
    "waitlist opening",
    "outreach",
    "market validation",
    "product-market fit",
    "market category readiness",
    "market size validation",
    "competitor superiority",
    "public benchmark",
    "pricing readiness",
    "public offer",
    "paid research",
    "investor material",
    "personal data collection",
    "customer access",
    "money movement",
    "external publication",
    "deployment readiness",
)
EXPECTED_SURFACES = (
    ("problem_hypothesis_questions", "local_draft", "AwaitingEvidence"),
    ("target_user_questions", "local_draft", "AwaitingEvidence"),
    ("market_category_questions", "local_draft", "AwaitingEvidence"),
    ("competitor_inventory_questions", "local_draft", "AwaitingEvidence"),
    ("differentiation_questions", "local_draft", "AwaitingEvidence"),
    ("pricing_assumption_questions", "local_draft", "AwaitingEvidence"),
    ("validation_plan_questions", "local_draft", "AwaitingEvidence"),
    ("public_claim_review_questions", "local_draft", "AwaitingEvidence"),
    ("risk_obligation_questions", "local_draft", "AwaitingEvidence"),
    ("evidence_promotion_questions", "local_draft", "AwaitingEvidence"),
)
EXPECTED_ROOT_KEYS = {
    "blocked_claims",
    "competitor_superiority_claimed",
    "customer_access_allowed",
    "customer_research_allowed",
    "deployment_allowed",
    "external_publication_allowed",
    "investor_material_allowed",
    "market_category_claimed",
    "market_research_surfaces",
    "market_size_claimed",
    "market_validation_claimed",
    "money_movement_allowed",
    "next_action",
    "outreach_allowed",
    "paid_research_allowed",
    "personal_data_collection_allowed",
    "pricing_claim_allowed",
    "product_market_fit_claimed",
    "public_benchmark_claimed",
    "public_offer_allowed",
    "schema_version",
    "solver_outcome",
    "status",
    "survey_publication_allowed",
    "waitlist_allowed",
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
    "Foundation Market Research Boundary",
    "Witness packet: [`../examples/foundation_market_research_witness.awaiting_evidence.json`]",
    "Rule: Market-research preparation is a local planning boundary, not customer research, product-market validation, competitor superiority, pricing readiness, public offer, investor material, or deployment evidence.",
    "No customer research, survey publication, waitlist opening, outreach, market",
    "market_research_boundary_state=AwaitingEvidence",
    "customer_research_allowed=false",
    "survey_publication_allowed=false",
    "waitlist_allowed=false",
    "outreach_allowed=false",
    "market_validation_claimed=false",
    "product_market_fit_claimed=false",
    "market_category_claimed=false",
    "market_size_claimed=false",
    "competitor_superiority_claimed=false",
    "public_benchmark_claimed=false",
    "pricing_claim_allowed=false",
    "public_offer_allowed=false",
    "paid_research_allowed=false",
    "investor_material_allowed=false",
    "personal_data_collection_allowed=false",
    "customer_access_allowed=false",
    "money_movement_allowed=false",
    "external_publication_allowed=false",
    "deployment_allowed=false",
    "python scripts/validate_foundation_market_research_boundary.py",
)
FORBIDDEN_VALUE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("url_value", re.compile(r"https?://", re.IGNORECASE)),
    ("email_value", re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)),
    ("private_path", re.compile(r"\b[A-Za-z]:[\\/]|\\\\", re.IGNORECASE)),
    (
        "person_assignment",
        re.compile(r"\b(?:person|name|email|contact|respondent|interviewee|participant)[_ -]?(?:id|name|email|url|ref|target|value|status)?\s*=", re.IGNORECASE),
    ),
    (
        "account_assignment",
        re.compile(r"\b(?:account|profile|platform|provider)[_ -]?(?:id|url|ref|target|value|status)?\s*=", re.IGNORECASE),
    ),
    (
        "survey_assignment",
        re.compile(r"\b(?:survey|interview|feedback|response|waitlist|beta|signup)[_ -]?(?:id|url|ref|target|value|status)?\s*=", re.IGNORECASE),
    ),
    (
        "competitor_assignment",
        re.compile(r"\b(?:competitor|benchmark|market|category)[_ -]?(?:id|url|name|score|rank|target|value|status)?\s*=", re.IGNORECASE),
    ),
    (
        "pricing_assignment",
        re.compile(r"\b(?:price|pricing|package|checkout|payment|invoice|offer)[_ -]?(?:id|url|amount|value|status)?\s*=", re.IGNORECASE),
    ),
    (
        "investor_assignment",
        re.compile(r"\b(?:investor|pitch|deck|fund|grant)[_ -]?(?:id|url|name|target|value|status)?\s*=", re.IGNORECASE),
    ),
    (
        "secret_assignment",
        re.compile(r"\b(?:password|secret|token|api[_ -]?key|client[_ -]?secret)\s*=", re.IGNORECASE),
    ),
    ("private_key_material", re.compile(r"BEGIN [A-Z ]*PRIVATE KEY")),
)
FORBIDDEN_PROMOTION_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("customer_research_completed", re.compile(r"\bcustomer\s+research\s+(?:is\s+)?(?:done|complete|completed)\b", re.IGNORECASE)),
    ("survey_live", re.compile(r"\bsurvey\s+(?:is\s+)?(?:live|published|open)\b", re.IGNORECASE)),
    ("waitlist_open", re.compile(r"\bwaitlist\s+(?:is\s+)?open\b", re.IGNORECASE)),
    ("outreach_started", re.compile(r"\boutreach\s+(?:has\s+)?started\b", re.IGNORECASE)),
    ("market_validated", re.compile(r"\bmarket\s+(?:is\s+)?validated\b", re.IGNORECASE)),
    ("product_market_fit", re.compile(r"\bproduct[- ]market\s+fit\s+(?:is\s+)?(?:validated|achieved|proven)\b", re.IGNORECASE)),
    ("market_size_validated", re.compile(r"\bmarket\s+size\s+(?:is\s+)?validated\b", re.IGNORECASE)),
    ("competitor_superior", re.compile(r"\b(?:competitor|competition)\s+(?:is\s+)?(?:beaten|outperformed)\b", re.IGNORECASE)),
    ("benchmark_passed", re.compile(r"\bbenchmark\s+(?:is\s+)?(?:passed|won|validated)\b", re.IGNORECASE)),
    ("pricing_ready", re.compile(r"\bpricing\s+(?:is\s+)?ready\b", re.IGNORECASE)),
    ("public_offer_live", re.compile(r"\bpublic\s+offer\s+(?:is\s+)?(?:live|published|ready)\b", re.IGNORECASE)),
    ("investor_material_ready", re.compile(r"\binvestor\s+material\s+(?:is\s+)?ready\b", re.IGNORECASE)),
    ("customer_access_ready", re.compile(r"\bcustomer\s+access\s+(?:is\s+)?ready\b", re.IGNORECASE)),
    ("deployment_ready", re.compile(r"\bdeployment\s+(?:is\s+)?ready\b", re.IGNORECASE)),
)


@dataclass(frozen=True, slots=True)
class MarketResearchFinding:
    """One deterministic market-research boundary validation finding."""

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


def validate_doc_text(text: str) -> list[MarketResearchFinding]:
    """Return findings for missing market-research documentation anchors."""

    findings: list[MarketResearchFinding] = []
    for phrase in REQUIRED_DOC_PHRASES:
        if phrase not in text:
            findings.append(
                MarketResearchFinding(
                    "foundation_market_research_doc_phrase_missing",
                    f"market-research boundary doc missing required phrase: {phrase}",
                )
            )
    return findings


def validate_packet(payload: dict[str, Any]) -> list[MarketResearchFinding]:
    """Return findings for market-research witness drift."""

    findings: list[MarketResearchFinding] = []
    findings.extend(validate_root_contract(payload))
    findings.extend(validate_market_research_surfaces(payload.get("market_research_surfaces")))
    findings.extend(validate_forbidden_value_patterns(payload))
    findings.extend(validate_forbidden_promotion_patterns(payload))
    return findings


def validate_root_contract(payload: dict[str, Any]) -> list[MarketResearchFinding]:
    """Return findings for root-level market-research witness drift."""

    findings: list[MarketResearchFinding] = []
    if set(payload) != EXPECTED_ROOT_KEYS:
        findings.append(
            MarketResearchFinding(
                "market_research_root_keys_invalid",
                f"root keys must be: {', '.join(sorted(EXPECTED_ROOT_KEYS))}",
            )
        )
    expected_values = {
        "witness_id": EXPECTED_WITNESS_ID,
        "schema_version": 1,
        "status": "AwaitingEvidence",
        "solver_outcome": "AwaitingEvidence",
        "customer_research_allowed": False,
        "survey_publication_allowed": False,
        "waitlist_allowed": False,
        "outreach_allowed": False,
        "market_validation_claimed": False,
        "product_market_fit_claimed": False,
        "market_category_claimed": False,
        "market_size_claimed": False,
        "competitor_superiority_claimed": False,
        "public_benchmark_claimed": False,
        "pricing_claim_allowed": False,
        "public_offer_allowed": False,
        "paid_research_allowed": False,
        "investor_material_allowed": False,
        "personal_data_collection_allowed": False,
        "customer_access_allowed": False,
        "money_movement_allowed": False,
        "external_publication_allowed": False,
        "deployment_allowed": False,
    }
    for key, expected_value in expected_values.items():
        if payload.get(key) != expected_value:
            findings.append(
                MarketResearchFinding(
                    "market_research_root_value_invalid",
                    f"{key} must be {expected_value!r}",
                )
            )
    if tuple(payload.get("blocked_claims") or ()) != EXPECTED_BLOCKED_CLAIMS:
        findings.append(
            MarketResearchFinding(
                "market_research_blocked_claims_invalid",
                f"blocked_claims must be: {', '.join(EXPECTED_BLOCKED_CLAIMS)}",
            )
        )
    next_action = payload.get("next_action")
    if not isinstance(next_action, str) or "keep market research preparation local" not in next_action:
        findings.append(
            MarketResearchFinding(
                "market_research_next_action_invalid",
                "next_action must preserve the local market-research boundary",
            )
        )
    return findings


def validate_market_research_surfaces(market_research_surfaces: object) -> list[MarketResearchFinding]:
    """Return findings for market-research surface witness drift."""

    findings: list[MarketResearchFinding] = []
    if not isinstance(market_research_surfaces, list) or not all(
        isinstance(surface, dict) for surface in market_research_surfaces
    ):
        return [
            MarketResearchFinding(
                "market_research_surfaces_invalid",
                "market_research_surfaces must be a list of objects",
            )
        ]
    observed_surfaces = tuple(
        (surface.get("surface_id"), surface.get("surface_type"), surface.get("state"))
        for surface in market_research_surfaces
    )
    if observed_surfaces != EXPECTED_SURFACES:
        findings.append(
            MarketResearchFinding(
                "market_research_surface_inventory_invalid",
                "market-research surface inventory does not match the Foundation Mode market-research set",
            )
        )
    surface_ids = [surface.get("surface_id") for surface in market_research_surfaces]
    if len(set(surface_ids)) != len(surface_ids):
        findings.append(MarketResearchFinding("market_research_surface_duplicate", "surface ids must be unique"))
    for surface in market_research_surfaces:
        surface_id = str(surface.get("surface_id", "<missing>"))
        if set(surface) != EXPECTED_SURFACE_KEYS:
            findings.append(
                MarketResearchFinding(
                    "market_research_surface_keys_invalid",
                    f"{surface_id} surface keys must be: {', '.join(sorted(EXPECTED_SURFACE_KEYS))}",
                )
            )
        if surface.get("state") != "AwaitingEvidence":
            findings.append(
                MarketResearchFinding(
                    "market_research_surface_state_invalid",
                    f"{surface_id} state must be AwaitingEvidence",
                )
            )
        if surface.get("evidence_ref") != "manual_preparation_pending":
            findings.append(
                MarketResearchFinding(
                    "market_research_surface_evidence_invalid",
                    f"{surface_id} evidence_ref must stay manual_preparation_pending in the committed packet",
                )
            )
        if not isinstance(surface.get("public_safe_note"), str) or not surface["public_safe_note"].strip():
            findings.append(
                MarketResearchFinding(
                    "market_research_surface_note_invalid",
                    f"{surface_id} public_safe_note must be a non-empty string",
                )
            )
    return findings


def validate_forbidden_value_patterns(payload: dict[str, Any]) -> list[MarketResearchFinding]:
    """Return findings for private, customer, pricing, investor, secret, or deployment-shaped values."""

    serialized_payload = json.dumps(payload, sort_keys=True)
    findings: list[MarketResearchFinding] = []
    for rule_id, pattern in FORBIDDEN_VALUE_PATTERNS:
        if pattern.search(serialized_payload):
            findings.append(
                MarketResearchFinding(
                    "market_research_forbidden_private_value_pattern",
                    f"market-research witness contains forbidden private value pattern: {rule_id}",
                )
            )
    return findings


def validate_forbidden_promotion_patterns(payload: dict[str, Any]) -> list[MarketResearchFinding]:
    """Return findings for market-research activation or readiness claims."""

    serialized_payload = json.dumps(payload, sort_keys=True)
    findings: list[MarketResearchFinding] = []
    for rule_id, pattern in FORBIDDEN_PROMOTION_PATTERNS:
        if pattern.search(serialized_payload):
            findings.append(
                MarketResearchFinding(
                    "market_research_forbidden_promotion_phrase",
                    f"market-research witness contains forbidden promotion phrase: {rule_id}",
                )
            )
    return findings


def validate_foundation_market_research_boundary(
    doc_path: Path = DEFAULT_DOC_PATH,
    packet_path: Path = DEFAULT_PACKET_PATH,
) -> list[MarketResearchFinding]:
    """Return all market-research boundary validation findings."""

    doc_text = load_text(doc_path, "market-research boundary doc")
    payload = load_json_object(packet_path, "market-research witness")
    findings: list[MarketResearchFinding] = []
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
    """Run the market-research boundary validator."""

    args = parse_args()
    findings = validate_foundation_market_research_boundary(args.doc, args.packet)
    if findings:
        for finding in findings:
            print(f"[FAIL] {finding.rule_id}: {finding.message}", file=sys.stderr)
        print("STATUS: failed", file=sys.stderr)
        return 1
    print("[PASS] foundation_market_research_doc")
    print("[PASS] foundation_market_research_witness")
    print("STATUS: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
