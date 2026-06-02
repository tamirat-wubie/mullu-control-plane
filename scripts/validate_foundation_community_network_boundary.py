#!/usr/bin/env python3
"""Validate the Foundation Mode community/network boundary.

Purpose: keep community and network preparation local while community
outreach, social/forum publication, direct messaging, collaborator recruitment,
partnership outreach, mentor requests, public feedback requests, event
participation, contact-list recording, personal-data collection,
external-account use, customer access, external publication, and deployment
claims remain blocked.
Governance scope: Foundation Mode, solo-operator community posture,
public-safe local questions, private-value exclusion, outside-contact blocking,
publication blocking, customer-access blocking, and deployment blocking.
Dependencies: docs/FOUNDATION_COMMUNITY_NETWORK_BOUNDARY.md and
examples/foundation_community_network_witness.awaiting_evidence.json.
Invariants:
  - Validation is read-only.
  - The witness records local community/network planning only.
  - No outside contact, public post, message, collaborator, partner, mentor,
    feedback request, event, contact list, personal data, external account,
    customer access, publication, or deployment claim is allowed.
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
DEFAULT_DOC_PATH = REPO_ROOT / "docs" / "FOUNDATION_COMMUNITY_NETWORK_BOUNDARY.md"
DEFAULT_PACKET_PATH = REPO_ROOT / "examples" / "foundation_community_network_witness.awaiting_evidence.json"

EXPECTED_WITNESS_ID = "foundation_community_network_witness.awaiting_evidence.v1"
EXPECTED_BLOCKED_CLAIMS = (
    "community outreach",
    "social post publication",
    "forum post publication",
    "direct messaging",
    "collaborator recruitment",
    "partnership outreach",
    "mentor request",
    "public feedback request",
    "event participation",
    "contact list recording",
    "personal data collection",
    "external account use",
    "public profile readiness",
    "customer access",
    "external publication",
    "deployment readiness",
)
EXPECTED_SURFACES = (
    ("personal_network_questions", "local_draft", "AwaitingEvidence"),
    ("community_channel_questions", "local_draft", "AwaitingEvidence"),
    ("help_request_draft_questions", "local_draft", "AwaitingEvidence"),
    ("forum_post_questions", "local_draft", "AwaitingEvidence"),
    ("social_post_questions", "local_draft", "AwaitingEvidence"),
    ("collaborator_boundary_questions", "local_draft", "AwaitingEvidence"),
    ("partnership_boundary_questions", "local_draft", "AwaitingEvidence"),
    ("mentor_request_questions", "local_draft", "AwaitingEvidence"),
    ("public_feedback_questions", "local_draft", "AwaitingEvidence"),
    ("event_referral_questions", "local_draft", "AwaitingEvidence"),
)
EXPECTED_ROOT_KEYS = {
    "blocked_claims",
    "collaborator_recruitment_allowed",
    "community_network_surfaces",
    "community_outreach_allowed",
    "contact_list_recorded",
    "customer_access_allowed",
    "deployment_allowed",
    "direct_message_allowed",
    "event_participation_allowed",
    "external_account_use_allowed",
    "external_publication_allowed",
    "forum_post_publication_allowed",
    "mentor_request_allowed",
    "next_action",
    "partnership_outreach_allowed",
    "personal_data_collection_allowed",
    "public_feedback_request_allowed",
    "public_profile_claimed",
    "schema_version",
    "social_post_publication_allowed",
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
    "Foundation Community Network Boundary",
    "Witness packet: [`../examples/foundation_community_network_witness.awaiting_evidence.json`]",
    "Rule: Community/network preparation is a local planning boundary, not outreach, recruiting, public feedback, partnership, or publication.",
    "No community outreach, social post publication, forum post publication, direct",
    "community_network_boundary_state=AwaitingEvidence",
    "community_outreach_allowed=false",
    "social_post_publication_allowed=false",
    "forum_post_publication_allowed=false",
    "direct_message_allowed=false",
    "collaborator_recruitment_allowed=false",
    "partnership_outreach_allowed=false",
    "mentor_request_allowed=false",
    "public_feedback_request_allowed=false",
    "event_participation_allowed=false",
    "contact_list_recorded=false",
    "personal_data_collection_allowed=false",
    "external_account_use_allowed=false",
    "public_profile_claimed=false",
    "customer_access_allowed=false",
    "external_publication_allowed=false",
    "deployment_allowed=false",
    "python scripts/validate_foundation_community_network_boundary.py",
)
FORBIDDEN_VALUE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("url_value", re.compile(r"https?://", re.IGNORECASE)),
    ("email_value", re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)),
    ("social_handle_value", re.compile(r"(?<![\w.])@[A-Za-z0-9_]{2,}")),
    ("private_path", re.compile(r"\b[A-Za-z]:[\\/]|\\\\", re.IGNORECASE)),
    (
        "contact_assignment",
        re.compile(r"\b(?:contact|person|name|email|handle|profile|intro|referral)[_ -]?(?:id|name|email|url|ref|target|value|status)?\s*=", re.IGNORECASE),
    ),
    (
        "message_assignment",
        re.compile(r"\b(?:dm|direct[_ -]?message|message|reply|thread)[_ -]?(?:id|url|ref|target|value|status)?\s*=", re.IGNORECASE),
    ),
    (
        "post_assignment",
        re.compile(r"\b(?:post|social|forum|community|channel)[_ -]?(?:id|url|ref|target|value|status)?\s*=", re.IGNORECASE),
    ),
    (
        "relationship_assignment",
        re.compile(r"\b(?:collaborator|partner|partnership|mentor|advisor|helper)[_ -]?(?:id|name|email|ref|target|value|status)?\s*=", re.IGNORECASE),
    ),
    (
        "event_assignment",
        re.compile(r"\b(?:event|meetup|conference|registration|attendee)[_ -]?(?:id|url|ref|target|value|status)?\s*=", re.IGNORECASE),
    ),
    (
        "account_assignment",
        re.compile(r"\b(?:account|profile|platform)[_ -]?(?:id|url|ref|target|value|status)?\s*=", re.IGNORECASE),
    ),
    (
        "personal_data_assignment",
        re.compile(r"\b(?:personal[_ -]?data|pii|survey|feedback|customer|user)[_ -]?(?:id|name|email|ref|target|value|status)?\s*=", re.IGNORECASE),
    ),
    (
        "secret_assignment",
        re.compile(r"\b(?:password|secret|token|api[_ -]?key|client[_ -]?secret)\s*=", re.IGNORECASE),
    ),
    ("private_key_material", re.compile(r"BEGIN [A-Z ]*PRIVATE KEY")),
)
FORBIDDEN_PROMOTION_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("community_outreach_started", re.compile(r"\bcommunity\s+outreach\s+(?:has\s+)?started\b", re.IGNORECASE)),
    ("social_post_published", re.compile(r"\bsocial\s+post\s+(?:is\s+)?(?:published|live)\b", re.IGNORECASE)),
    ("forum_post_published", re.compile(r"\bforum\s+post\s+(?:is\s+)?(?:published|live)\b", re.IGNORECASE)),
    ("message_sent", re.compile(r"\b(?:message|direct\s+message|dm)\s+(?:is\s+)?sent\b", re.IGNORECASE)),
    ("collaborator_recruited", re.compile(r"\bcollaborator\s+(?:is\s+)?recruited\b", re.IGNORECASE)),
    ("partnership_outreach_started", re.compile(r"\bpartnership\s+outreach\s+(?:has\s+)?started\b", re.IGNORECASE)),
    ("mentor_request_sent", re.compile(r"\bmentor\s+request\s+(?:is\s+)?sent\b", re.IGNORECASE)),
    ("feedback_request_live", re.compile(r"\bfeedback\s+request\s+(?:is\s+)?live\b", re.IGNORECASE)),
    ("event_registered", re.compile(r"\bevent\s+(?:is\s+)?registered\b", re.IGNORECASE)),
    ("contact_list_ready", re.compile(r"\bcontact\s+list\s+(?:is\s+)?ready\b", re.IGNORECASE)),
    ("external_account_ready", re.compile(r"\bexternal\s+account\s+(?:is\s+)?ready\b", re.IGNORECASE)),
    ("customer_access_ready", re.compile(r"\bcustomer\s+access\s+(?:is\s+)?ready\b", re.IGNORECASE)),
    ("deployment_ready", re.compile(r"\bdeployment\s+(?:is\s+)?ready\b", re.IGNORECASE)),
)


@dataclass(frozen=True, slots=True)
class CommunityNetworkFinding:
    """One deterministic community/network boundary validation finding."""

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


def validate_doc_text(text: str) -> list[CommunityNetworkFinding]:
    """Return findings for missing community/network documentation anchors."""

    findings: list[CommunityNetworkFinding] = []
    for phrase in REQUIRED_DOC_PHRASES:
        if phrase not in text:
            findings.append(
                CommunityNetworkFinding(
                    "foundation_community_network_doc_phrase_missing",
                    f"community/network boundary doc missing required phrase: {phrase}",
                )
            )
    return findings


def validate_packet(payload: dict[str, Any]) -> list[CommunityNetworkFinding]:
    """Return findings for community/network witness drift."""

    findings: list[CommunityNetworkFinding] = []
    findings.extend(validate_root_contract(payload))
    findings.extend(validate_community_network_surfaces(payload.get("community_network_surfaces")))
    findings.extend(validate_forbidden_value_patterns(payload))
    findings.extend(validate_forbidden_promotion_patterns(payload))
    return findings


def validate_root_contract(payload: dict[str, Any]) -> list[CommunityNetworkFinding]:
    """Return findings for root-level community/network witness drift."""

    findings: list[CommunityNetworkFinding] = []
    if set(payload) != EXPECTED_ROOT_KEYS:
        findings.append(
            CommunityNetworkFinding(
                "community_network_root_keys_invalid",
                f"root keys must be: {', '.join(sorted(EXPECTED_ROOT_KEYS))}",
            )
        )
    expected_values = {
        "witness_id": EXPECTED_WITNESS_ID,
        "schema_version": 1,
        "status": "AwaitingEvidence",
        "solver_outcome": "AwaitingEvidence",
        "community_outreach_allowed": False,
        "social_post_publication_allowed": False,
        "forum_post_publication_allowed": False,
        "direct_message_allowed": False,
        "collaborator_recruitment_allowed": False,
        "partnership_outreach_allowed": False,
        "mentor_request_allowed": False,
        "public_feedback_request_allowed": False,
        "event_participation_allowed": False,
        "contact_list_recorded": False,
        "personal_data_collection_allowed": False,
        "external_account_use_allowed": False,
        "public_profile_claimed": False,
        "customer_access_allowed": False,
        "external_publication_allowed": False,
        "deployment_allowed": False,
    }
    for key, expected_value in expected_values.items():
        if payload.get(key) != expected_value:
            findings.append(
                CommunityNetworkFinding(
                    "community_network_root_value_invalid",
                    f"{key} must be {expected_value!r}",
                )
            )
    if tuple(payload.get("blocked_claims") or ()) != EXPECTED_BLOCKED_CLAIMS:
        findings.append(
            CommunityNetworkFinding(
                "community_network_blocked_claims_invalid",
                f"blocked_claims must be: {', '.join(EXPECTED_BLOCKED_CLAIMS)}",
            )
        )
    next_action = payload.get("next_action")
    if not isinstance(next_action, str) or "keep community and network preparation local" not in next_action:
        findings.append(
            CommunityNetworkFinding(
                "community_network_next_action_invalid",
                "next_action must preserve the local community/network boundary",
            )
        )
    return findings


def validate_community_network_surfaces(community_network_surfaces: object) -> list[CommunityNetworkFinding]:
    """Return findings for community/network surface witness drift."""

    findings: list[CommunityNetworkFinding] = []
    if not isinstance(community_network_surfaces, list) or not all(
        isinstance(surface, dict) for surface in community_network_surfaces
    ):
        return [
            CommunityNetworkFinding(
                "community_network_surfaces_invalid",
                "community_network_surfaces must be a list of objects",
            )
        ]
    observed_surfaces = tuple(
        (surface.get("surface_id"), surface.get("surface_type"), surface.get("state"))
        for surface in community_network_surfaces
    )
    if observed_surfaces != EXPECTED_SURFACES:
        findings.append(
            CommunityNetworkFinding(
                "community_network_surface_inventory_invalid",
                "community/network surface inventory does not match the Foundation Mode community/network set",
            )
        )
    surface_ids = [surface.get("surface_id") for surface in community_network_surfaces]
    if len(set(surface_ids)) != len(surface_ids):
        findings.append(CommunityNetworkFinding("community_network_surface_duplicate", "surface ids must be unique"))
    for surface in community_network_surfaces:
        surface_id = str(surface.get("surface_id", "<missing>"))
        if set(surface) != EXPECTED_SURFACE_KEYS:
            findings.append(
                CommunityNetworkFinding(
                    "community_network_surface_keys_invalid",
                    f"{surface_id} surface keys must be: {', '.join(sorted(EXPECTED_SURFACE_KEYS))}",
                )
            )
        if surface.get("state") != "AwaitingEvidence":
            findings.append(
                CommunityNetworkFinding(
                    "community_network_surface_state_invalid",
                    f"{surface_id} state must be AwaitingEvidence",
                )
            )
        if surface.get("evidence_ref") != "manual_preparation_pending":
            findings.append(
                CommunityNetworkFinding(
                    "community_network_surface_evidence_invalid",
                    f"{surface_id} evidence_ref must stay manual_preparation_pending in the committed packet",
                )
            )
        if not isinstance(surface.get("public_safe_note"), str) or not surface["public_safe_note"].strip():
            findings.append(
                CommunityNetworkFinding(
                    "community_network_surface_note_invalid",
                    f"{surface_id} public_safe_note must be a non-empty string",
                )
            )
    return findings


def validate_forbidden_value_patterns(payload: dict[str, Any]) -> list[CommunityNetworkFinding]:
    """Return findings for contact, account, private, customer, secret, or deployment-shaped values."""

    serialized_payload = json.dumps(payload, sort_keys=True)
    findings: list[CommunityNetworkFinding] = []
    for rule_id, pattern in FORBIDDEN_VALUE_PATTERNS:
        if pattern.search(serialized_payload):
            findings.append(
                CommunityNetworkFinding(
                    "community_network_forbidden_private_value_pattern",
                    f"community/network witness contains forbidden private value pattern: {rule_id}",
                )
            )
    return findings


def validate_forbidden_promotion_patterns(payload: dict[str, Any]) -> list[CommunityNetworkFinding]:
    """Return findings for community/network activation or readiness claims."""

    serialized_payload = json.dumps(payload, sort_keys=True)
    findings: list[CommunityNetworkFinding] = []
    for rule_id, pattern in FORBIDDEN_PROMOTION_PATTERNS:
        if pattern.search(serialized_payload):
            findings.append(
                CommunityNetworkFinding(
                    "community_network_forbidden_promotion_phrase",
                    f"community/network witness contains forbidden promotion phrase: {rule_id}",
                )
            )
    return findings


def validate_foundation_community_network_boundary(
    doc_path: Path = DEFAULT_DOC_PATH,
    packet_path: Path = DEFAULT_PACKET_PATH,
) -> list[CommunityNetworkFinding]:
    """Return all community/network boundary validation findings."""

    doc_text = load_text(doc_path, "community/network boundary doc")
    payload = load_json_object(packet_path, "community/network witness")
    findings: list[CommunityNetworkFinding] = []
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
    """Run the community/network boundary validator."""

    args = parse_args()
    findings = validate_foundation_community_network_boundary(args.doc, args.packet)
    if findings:
        for finding in findings:
            print(f"[FAIL] {finding.rule_id}: {finding.message}", file=sys.stderr)
        print("STATUS: failed", file=sys.stderr)
        return 1
    print("[PASS] foundation_community_network_doc")
    print("[PASS] foundation_community_network_witness")
    print("STATUS: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
