#!/usr/bin/env python3
"""Validate the Foundation Mode community/network no-outreach rehearsal boundary.

Purpose: keep community/network no-outreach rehearsal local and public-safe
while outreach, posting, messaging, help requests, collaborator recruitment,
partnership outreach, mentor requests, feedback requests, event participation,
referral requests, contact-list recording, personal-data collection,
external-account use, customer access, external publication, secret material,
and deployment remain blocked.
Governance scope: Foundation Mode, community/network no-outreach rehearsal,
message/post stop rules, relationship-request stop rules, contact-list
exclusion, personal-data exclusion, customer-access blocking,
external-publication blocking, and deployment blocking.
Dependencies: docs/FOUNDATION_COMMUNITY_NETWORK_NO_OUTREACH_REHEARSAL_BOUNDARY.md and
examples/foundation_community_network_no_outreach_rehearsal_witness.awaiting_evidence.json.
Invariants:
  - Validation is read-only.
  - The witness records no-outreach questions only.
  - No outside contact, public post, message, help request, collaborator,
    partner, mentor, feedback request, event, referral, contact list, personal
    data, external account, customer access, publication, secret, or deployment
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
DEFAULT_DOC_PATH = REPO_ROOT / "docs" / "FOUNDATION_COMMUNITY_NETWORK_NO_OUTREACH_REHEARSAL_BOUNDARY.md"
DEFAULT_PACKET_PATH = REPO_ROOT / "examples" / "foundation_community_network_no_outreach_rehearsal_witness.awaiting_evidence.json"

EXPECTED_WITNESS_ID = "foundation_community_network_no_outreach_rehearsal_witness.awaiting_evidence.v1"
EXPECTED_BLOCKED_CLAIMS = (
    "outreach rehearsal execution",
    "community outreach",
    "social post publication",
    "forum post publication",
    "direct messaging",
    "help request",
    "collaborator recruitment",
    "partnership outreach",
    "mentor request",
    "public feedback request",
    "event participation",
    "referral request",
    "contact list recording",
    "personal data collection",
    "external account use",
    "public profile readiness",
    "customer access",
    "external publication",
    "secret material",
    "deployment readiness",
)
EXPECTED_SURFACES = (
    ("audience_boundary_questions", "local_draft", "AwaitingEvidence"),
    ("channel_fit_questions", "local_draft", "AwaitingEvidence"),
    ("help_request_stop_rule", "local_draft", "AwaitingEvidence"),
    ("forum_post_stop_rule", "local_draft", "AwaitingEvidence"),
    ("social_post_stop_rule", "local_draft", "AwaitingEvidence"),
    ("direct_message_stop_rule", "local_draft", "AwaitingEvidence"),
    ("collaborator_stop_rule", "local_draft", "AwaitingEvidence"),
    ("partnership_stop_rule", "local_draft", "AwaitingEvidence"),
    ("mentor_stop_rule", "local_draft", "AwaitingEvidence"),
    ("feedback_stop_rule", "local_draft", "AwaitingEvidence"),
    ("event_referral_stop_rule", "local_draft", "AwaitingEvidence"),
    ("privacy_support_handoff", "local_draft", "AwaitingEvidence"),
)
EXPECTED_ROOT_KEYS = {
    "blocked_claims",
    "collaborator_recruitment_allowed",
    "community_outreach_allowed",
    "contact_list_recorded",
    "customer_access_allowed",
    "deployment_allowed",
    "direct_message_allowed",
    "event_participation_allowed",
    "external_account_use_allowed",
    "external_publication_allowed",
    "forum_post_publication_allowed",
    "help_request_allowed",
    "mentor_request_allowed",
    "next_action",
    "no_outreach_rehearsal_executed",
    "partnership_outreach_allowed",
    "personal_data_collection_allowed",
    "public_feedback_request_allowed",
    "public_profile_claimed",
    "referral_request_allowed",
    "schema_version",
    "secret_material_allowed",
    "social_post_publication_allowed",
    "solver_outcome",
    "status",
    "surfaces",
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
    "Foundation Community Network No-Outreach Rehearsal Boundary",
    "Witness packet: [`../examples/foundation_community_network_no_outreach_rehearsal_witness.awaiting_evidence.json`]",
    "Rule: Community/network no-outreach rehearsal is a local paper exercise",
    "No outreach rehearsal execution, community outreach, social post publication,",
    "community_network_no_outreach_rehearsal_boundary_state=AwaitingEvidence",
    "no_outreach_rehearsal_executed=false",
    "community_outreach_allowed=false",
    "social_post_publication_allowed=false",
    "forum_post_publication_allowed=false",
    "direct_message_allowed=false",
    "help_request_allowed=false",
    "collaborator_recruitment_allowed=false",
    "partnership_outreach_allowed=false",
    "mentor_request_allowed=false",
    "public_feedback_request_allowed=false",
    "event_participation_allowed=false",
    "referral_request_allowed=false",
    "contact_list_recorded=false",
    "personal_data_collection_allowed=false",
    "external_account_use_allowed=false",
    "public_profile_claimed=false",
    "customer_access_allowed=false",
    "external_publication_allowed=false",
    "secret_material_allowed=false",
    "deployment_allowed=false",
    "python scripts/validate_foundation_community_network_no_outreach_rehearsal_boundary.py",
)
FORBIDDEN_VALUE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("url_value", re.compile(r"https?://", re.IGNORECASE)),
    ("email_value", re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)),
    ("social_handle_value", re.compile(r"(?<![\w.])@[A-Za-z0-9_]{2,}")),
    ("private_path", re.compile(r"\b[A-Za-z]:[\\/]|\\\\", re.IGNORECASE)),
    ("private_key_block", re.compile(r"-----BEGIN\s+(?:RSA\s+|EC\s+|OPENSSH\s+)?PRIVATE\s+KEY-----", re.IGNORECASE)),
    (
        "no_outreach_assignment",
        re.compile(
            r"\b(?:contact|person|name|email|handle|profile|intro|referral|dm|"
            r"direct[_ -]?message|message|reply|thread|post|social|forum|"
            r"community|channel|collaborator|partner|partnership|mentor|advisor|"
            r"helper|feedback|survey|event|meetup|conference|registration|"
            r"attendee|account|platform|personal[_ -]?data|pii|customer|user|"
            r"secret|token|api[_ -]?key|client[_ -]?secret)"
            r"[_ -]?(?:id|name|email|url|link|ref|target|value|status|text|list)?\s*=",
            re.IGNORECASE,
        ),
    ),
    (
        "deployment_assignment",
        re.compile(r"\b(?:deploy|deployment|production|staging)[_ -]?(?:target|url|ref|value|status)?\s*=", re.IGNORECASE),
    ),
)
FORBIDDEN_PROMOTION_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("outreach_rehearsal_executed", re.compile(r"\boutreach rehearsal (?:executed|complete|completed)\b", re.IGNORECASE)),
    ("community_outreach_started", re.compile(r"\bcommunity\s+outreach\s+(?:has\s+)?started\b", re.IGNORECASE)),
    ("social_post_published", re.compile(r"\bsocial\s+post\s+(?:is\s+)?(?:published|live)\b", re.IGNORECASE)),
    ("forum_post_published", re.compile(r"\bforum\s+post\s+(?:is\s+)?(?:published|live)\b", re.IGNORECASE)),
    ("message_sent", re.compile(r"\b(?:message|direct\s+message|dm)\s+(?:is\s+)?sent\b", re.IGNORECASE)),
    ("help_request_sent", re.compile(r"\bhelp\s+request\s+(?:is\s+)?sent\b", re.IGNORECASE)),
    ("collaborator_recruited", re.compile(r"\bcollaborator\s+(?:is\s+)?recruited\b", re.IGNORECASE)),
    ("partnership_outreach_started", re.compile(r"\bpartnership\s+outreach\s+(?:has\s+)?started\b", re.IGNORECASE)),
    ("mentor_request_sent", re.compile(r"\bmentor\s+request\s+(?:is\s+)?sent\b", re.IGNORECASE)),
    ("feedback_request_live", re.compile(r"\bfeedback\s+request\s+(?:is\s+)?live\b", re.IGNORECASE)),
    ("event_registered", re.compile(r"\bevent\s+(?:is\s+)?registered\b", re.IGNORECASE)),
    ("referral_requested", re.compile(r"\breferral\s+request\s+(?:is\s+)?sent\b", re.IGNORECASE)),
    ("contact_list_ready", re.compile(r"\bcontact\s+list\s+(?:is\s+)?ready\b", re.IGNORECASE)),
    ("external_account_ready", re.compile(r"\bexternal\s+account\s+(?:is\s+)?ready\b", re.IGNORECASE)),
    ("public_profile_ready", re.compile(r"\bpublic\s+profile\s+(?:is\s+)?ready\b", re.IGNORECASE)),
    ("customer_access_ready", re.compile(r"\bcustomer\s+access\s+(?:is\s+)?ready\b", re.IGNORECASE)),
    ("external_publication_approved", re.compile(r"\bexternal publication (?:allowed|approved|ready)\b", re.IGNORECASE)),
    ("deployment_ready", re.compile(r"\bdeployment\s+(?:is\s+)?ready\b", re.IGNORECASE)),
)


@dataclass(frozen=True, slots=True)
class CommunityNetworkNoOutreachRehearsalFinding:
    """One deterministic community/network no-outreach rehearsal validation finding."""

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


def validate_doc_text(text: str) -> list[CommunityNetworkNoOutreachRehearsalFinding]:
    """Return findings for missing community/network no-outreach rehearsal documentation anchors."""

    findings: list[CommunityNetworkNoOutreachRehearsalFinding] = []
    for phrase in REQUIRED_DOC_PHRASES:
        if phrase not in text:
            findings.append(
                CommunityNetworkNoOutreachRehearsalFinding(
                    "foundation_community_network_no_outreach_rehearsal_doc_phrase_missing",
                    f"community/network no-outreach rehearsal boundary doc missing required phrase: {phrase}",
                )
            )
    return findings


def validate_packet(payload: dict[str, Any]) -> list[CommunityNetworkNoOutreachRehearsalFinding]:
    """Return findings for community/network no-outreach rehearsal witness drift."""

    findings: list[CommunityNetworkNoOutreachRehearsalFinding] = []
    findings.extend(validate_root_contract(payload))
    findings.extend(validate_surfaces(payload.get("surfaces")))
    findings.extend(validate_forbidden_value_patterns(payload))
    findings.extend(validate_forbidden_promotion_patterns(payload))
    return findings


def validate_root_contract(payload: dict[str, Any]) -> list[CommunityNetworkNoOutreachRehearsalFinding]:
    """Return findings for root-level community/network no-outreach rehearsal witness drift."""

    findings: list[CommunityNetworkNoOutreachRehearsalFinding] = []
    if set(payload) != EXPECTED_ROOT_KEYS:
        findings.append(
            CommunityNetworkNoOutreachRehearsalFinding(
                "community_network_no_outreach_rehearsal_root_keys_invalid",
                f"root keys must be: {', '.join(sorted(EXPECTED_ROOT_KEYS))}",
            )
        )
    expected_values = {
        "witness_id": EXPECTED_WITNESS_ID,
        "schema_version": 1,
        "status": "AwaitingEvidence",
        "solver_outcome": "AwaitingEvidence",
        "no_outreach_rehearsal_executed": False,
        "community_outreach_allowed": False,
        "social_post_publication_allowed": False,
        "forum_post_publication_allowed": False,
        "direct_message_allowed": False,
        "help_request_allowed": False,
        "collaborator_recruitment_allowed": False,
        "partnership_outreach_allowed": False,
        "mentor_request_allowed": False,
        "public_feedback_request_allowed": False,
        "event_participation_allowed": False,
        "referral_request_allowed": False,
        "contact_list_recorded": False,
        "personal_data_collection_allowed": False,
        "external_account_use_allowed": False,
        "public_profile_claimed": False,
        "customer_access_allowed": False,
        "external_publication_allowed": False,
        "secret_material_allowed": False,
        "deployment_allowed": False,
    }
    for key, expected_value in expected_values.items():
        if payload.get(key) != expected_value:
            findings.append(
                CommunityNetworkNoOutreachRehearsalFinding(
                    "community_network_no_outreach_rehearsal_root_value_invalid",
                    f"{key} must be {expected_value!r}",
                )
            )
    if tuple(payload.get("blocked_claims") or ()) != EXPECTED_BLOCKED_CLAIMS:
        findings.append(
            CommunityNetworkNoOutreachRehearsalFinding(
                "community_network_no_outreach_rehearsal_blocked_claims_invalid",
                f"blocked_claims must be: {', '.join(EXPECTED_BLOCKED_CLAIMS)}",
            )
        )
    next_action = payload.get("next_action")
    if not isinstance(next_action, str) or "draft local community/network no-outreach questions only" not in next_action:
        findings.append(
            CommunityNetworkNoOutreachRehearsalFinding(
                "community_network_no_outreach_rehearsal_next_action_invalid",
                "next_action must preserve local community/network no-outreach question drafting only",
            )
        )
    return findings


def validate_surfaces(surfaces: object) -> list[CommunityNetworkNoOutreachRehearsalFinding]:
    """Return findings for community/network no-outreach rehearsal surface drift."""

    findings: list[CommunityNetworkNoOutreachRehearsalFinding] = []
    if not isinstance(surfaces, list) or not all(isinstance(surface, dict) for surface in surfaces):
        return [CommunityNetworkNoOutreachRehearsalFinding("community_network_no_outreach_rehearsal_surfaces_invalid", "surfaces must be a list")]
    observed_surfaces = tuple(
        (surface.get("surface_id"), surface.get("surface_type"), surface.get("state"))
        for surface in surfaces
    )
    if observed_surfaces != EXPECTED_SURFACES:
        findings.append(
            CommunityNetworkNoOutreachRehearsalFinding(
                "community_network_no_outreach_rehearsal_surface_inventory_invalid",
                "community/network no-outreach rehearsal surface inventory does not match the expected set",
            )
        )
    surface_ids = [surface.get("surface_id") for surface in surfaces]
    if len(set(surface_ids)) != len(surface_ids):
        findings.append(CommunityNetworkNoOutreachRehearsalFinding("community_network_no_outreach_rehearsal_surface_duplicate", "surface ids must be unique"))
    for surface in surfaces:
        surface_id = str(surface.get("surface_id", "<missing>"))
        if set(surface) != EXPECTED_SURFACE_KEYS:
            findings.append(
                CommunityNetworkNoOutreachRehearsalFinding(
                    "community_network_no_outreach_rehearsal_surface_keys_invalid",
                    f"{surface_id} surface keys must be: {', '.join(sorted(EXPECTED_SURFACE_KEYS))}",
                )
            )
        if surface.get("state") != "AwaitingEvidence":
            findings.append(
                CommunityNetworkNoOutreachRehearsalFinding(
                    "community_network_no_outreach_rehearsal_surface_state_invalid",
                    f"{surface_id} state must be AwaitingEvidence",
                )
            )
        if surface.get("evidence_ref") != "manual_preparation_pending":
            findings.append(
                CommunityNetworkNoOutreachRehearsalFinding(
                    "community_network_no_outreach_rehearsal_surface_evidence_invalid",
                    f"{surface_id} evidence_ref must stay manual_preparation_pending",
                )
            )
        if not isinstance(surface.get("public_safe_note"), str) or not surface["public_safe_note"].strip():
            findings.append(
                CommunityNetworkNoOutreachRehearsalFinding(
                    "community_network_no_outreach_rehearsal_surface_note_invalid",
                    f"{surface_id} public_safe_note must be a non-empty string",
                )
            )
    return findings


def validate_forbidden_value_patterns(payload: dict[str, Any]) -> list[CommunityNetworkNoOutreachRehearsalFinding]:
    """Return findings for contact, account, private, customer, secret, or deployment-shaped values."""

    serialized_payload = json.dumps(payload, sort_keys=True)
    findings: list[CommunityNetworkNoOutreachRehearsalFinding] = []
    for rule_id, pattern in FORBIDDEN_VALUE_PATTERNS:
        if pattern.search(serialized_payload):
            findings.append(
                CommunityNetworkNoOutreachRehearsalFinding(
                    "community_network_no_outreach_rehearsal_forbidden_value_pattern",
                    f"community/network no-outreach rehearsal witness contains forbidden value pattern: {rule_id}",
                )
            )
    return findings


def validate_forbidden_promotion_patterns(payload: dict[str, Any]) -> list[CommunityNetworkNoOutreachRehearsalFinding]:
    """Return findings if the witness drifts into community/network activation claims."""

    serialized_payload = json.dumps(payload, sort_keys=True)
    findings: list[CommunityNetworkNoOutreachRehearsalFinding] = []
    for rule_id, pattern in FORBIDDEN_PROMOTION_PATTERNS:
        if pattern.search(serialized_payload):
            findings.append(
                CommunityNetworkNoOutreachRehearsalFinding(
                    "community_network_no_outreach_rehearsal_forbidden_promotion_phrase",
                    f"community/network no-outreach rehearsal witness contains forbidden promotion pattern: {rule_id}",
                )
            )
    return findings


def validate_foundation_community_network_no_outreach_rehearsal_boundary(
    doc_path: Path = DEFAULT_DOC_PATH,
    packet_path: Path = DEFAULT_PACKET_PATH,
) -> list[CommunityNetworkNoOutreachRehearsalFinding]:
    """Validate the Foundation Mode community/network no-outreach rehearsal boundary artifacts."""

    doc_text = load_text(doc_path, "community/network no-outreach rehearsal boundary doc")
    packet_payload = load_json_object(packet_path, "community/network no-outreach rehearsal witness packet")
    return [
        *validate_doc_text(doc_text),
        *validate_packet(packet_payload),
    ]


def main(argv: list[str] | None = None) -> int:
    """Validate community/network no-outreach rehearsal artifacts and print deterministic status."""

    parser = argparse.ArgumentParser(description="Validate Foundation Mode community/network no-outreach rehearsal boundary artifacts.")
    parser.add_argument("--doc", type=Path, default=DEFAULT_DOC_PATH)
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET_PATH)
    args = parser.parse_args(argv)

    try:
        findings = validate_foundation_community_network_no_outreach_rehearsal_boundary(args.doc, args.packet)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"[FAIL] foundation_community_network_no_outreach_rehearsal_load: {exc}", file=sys.stderr)
        print("STATUS: failed", file=sys.stderr)
        return 1

    if findings:
        for finding in findings:
            print(f"[FAIL] {finding.rule_id}: {finding.message}", file=sys.stderr)
        print("STATUS: failed", file=sys.stderr)
        return 1
    print("[PASS] foundation_community_network_no_outreach_rehearsal_doc")
    print("[PASS] foundation_community_network_no_outreach_rehearsal_witness")
    print("STATUS: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
