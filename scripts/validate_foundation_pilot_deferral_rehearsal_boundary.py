#!/usr/bin/env python3
"""Validate the Foundation Mode pilot-deferral rehearsal boundary.

Purpose: keep pilot-deferral rehearsal local and public-safe while pilot
execution, participant invitation, access-channel opening, waitlist/signup
opening, customer access, personal-data collection, market-validation claims,
support-readiness claims, legal-clearance claims, paid-pilot claims, payment,
money movement, external publication, secret material, and deployment remain
blocked.
Governance scope: Foundation Mode, pilot-deferral rehearsal, local stop-rule
drafting, participant-boundary blocking, access-channel blocking, data
collection blocking, support-duty blocking, legal/business restraint, payment
blocking, public-claim restraint, secret exclusion, and deployment blocking.
Dependencies: docs/FOUNDATION_PILOT_DEFERRAL_REHEARSAL_BOUNDARY.md and
examples/foundation_pilot_deferral_rehearsal_witness.awaiting_evidence.json.
Invariants:
  - Validation is read-only.
  - The witness records local pilot-deferral rehearsal questions only.
  - No pilot, invitation, access channel, waitlist, signup, customer access,
    personal data, market validation, support readiness, legal clearance, paid
    pilot, payment, money movement, publication, secret material, or deployment
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
DEFAULT_DOC_PATH = REPO_ROOT / "docs" / "FOUNDATION_PILOT_DEFERRAL_REHEARSAL_BOUNDARY.md"
DEFAULT_PACKET_PATH = REPO_ROOT / "examples" / "foundation_pilot_deferral_rehearsal_witness.awaiting_evidence.json"

EXPECTED_WITNESS_ID = "foundation_pilot_deferral_rehearsal_witness.awaiting_evidence.v1"
EXPECTED_BLOCKED_CLAIMS = (
    "pilot deferral rehearsal execution",
    "pilot execution",
    "participant invitation",
    "access channel opening",
    "waitlist opening",
    "pilot signup opening",
    "customer access",
    "personal data collection",
    "market validation",
    "support readiness",
    "legal clearance",
    "paid pilot",
    "payment enablement",
    "money movement",
    "external publication",
    "secret material",
    "deployment readiness",
)
EXPECTED_SURFACES = (
    ("pilot_purpose_deferral_questions", "local_draft", "AwaitingEvidence"),
    ("participant_boundary_stop_rule", "local_draft", "AwaitingEvidence"),
    ("access_channel_stop_rule", "local_draft", "AwaitingEvidence"),
    ("waitlist_signup_stop_rule", "local_draft", "AwaitingEvidence"),
    ("data_collection_stop_rule", "local_draft", "AwaitingEvidence"),
    ("support_obligation_stop_rule", "local_draft", "AwaitingEvidence"),
    ("legal_business_stop_rule", "local_draft", "AwaitingEvidence"),
    ("paid_pilot_stop_rule", "local_draft", "AwaitingEvidence"),
    ("success_metric_stop_rule", "local_draft", "AwaitingEvidence"),
    ("rollback_recovery_stop_rule", "local_draft", "AwaitingEvidence"),
    ("public_claim_stop_rule", "local_draft", "AwaitingEvidence"),
    ("reassessment_handoff", "local_draft", "AwaitingEvidence"),
)
EXPECTED_ROOT_KEYS = {
    "access_channel_opening_allowed",
    "blocked_claims",
    "customer_access_allowed",
    "deployment_allowed",
    "deferral_rehearsal_executed",
    "external_publication_allowed",
    "legal_clearance_claimed",
    "market_validation_claimed",
    "money_movement_allowed",
    "next_action",
    "paid_pilot_allowed",
    "participant_invitation_allowed",
    "payment_enabled",
    "personal_data_collection_allowed",
    "pilot_execution_allowed",
    "pilot_signup_open",
    "schema_version",
    "secret_material_allowed",
    "solver_outcome",
    "status",
    "support_readiness_claimed",
    "surfaces",
    "waitlist_opening_allowed",
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
    "Foundation Pilot Deferral Rehearsal Boundary",
    "Witness packet: [`../examples/foundation_pilot_deferral_rehearsal_witness.awaiting_evidence.json`]",
    "Rule: Pilot-deferral rehearsal is a local paper exercise",
    "No pilot deferral rehearsal execution, pilot execution, participant invitation,",
    "pilot_deferral_rehearsal_boundary_state=AwaitingEvidence",
    "deferral_rehearsal_executed=false",
    "pilot_execution_allowed=false",
    "participant_invitation_allowed=false",
    "access_channel_opening_allowed=false",
    "waitlist_opening_allowed=false",
    "pilot_signup_open=false",
    "customer_access_allowed=false",
    "personal_data_collection_allowed=false",
    "market_validation_claimed=false",
    "support_readiness_claimed=false",
    "legal_clearance_claimed=false",
    "paid_pilot_allowed=false",
    "payment_enabled=false",
    "money_movement_allowed=false",
    "external_publication_allowed=false",
    "secret_material_allowed=false",
    "deployment_allowed=false",
    "python scripts/validate_foundation_pilot_deferral_rehearsal_boundary.py",
)
FORBIDDEN_VALUE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("url_value", re.compile(r"https?://", re.IGNORECASE)),
    ("email_value", re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)),
    ("private_path", re.compile(r"\b[A-Za-z]:[\\/]|\\\\", re.IGNORECASE)),
    ("private_key_block", re.compile(r"-----BEGIN\s+(?:RSA\s+|EC\s+|OPENSSH\s+)?PRIVATE\s+KEY-----", re.IGNORECASE)),
    (
        "pilot_rehearsal_assignment",
        re.compile(
            r"\b(?:person|participant|customer|user|pilot|waitlist|signup|"
            r"form|intake|contact|name|email|profile|account|tenant|project|"
            r"provider|support|billing|payment|card|invoice|price|deadline|"
            r"schedule|date|legal|company|secret|token|api[_ -]?key|"
            r"client[_ -]?secret)"
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
    (
        "pilot_deferral_rehearsal_executed",
        re.compile(r"\bpilot deferral rehearsal (?:executed|complete|completed)\b", re.IGNORECASE),
    ),
    ("pilot_ready", re.compile(r"\bpilot\s+(?:is\s+)?ready\b", re.IGNORECASE)),
    ("pilot_open", re.compile(r"\bpilot\s+(?:is\s+)?open\b", re.IGNORECASE)),
    ("pilot_approved", re.compile(r"\bpilot\s+(?:is\s+)?approved\b", re.IGNORECASE)),
    ("pilot_access_open", re.compile(r"\bpilot access\s+(?:is\s+)?open\b", re.IGNORECASE)),
    ("waitlist_open", re.compile(r"\bwaitlist\s+(?:is\s+)?open\b", re.IGNORECASE)),
    ("signup_open", re.compile(r"\bsignup\s+(?:is\s+)?open\b", re.IGNORECASE)),
    ("participant_invited", re.compile(r"\bparticipant\s+(?:is\s+)?invited\b", re.IGNORECASE)),
    ("customer_access_open", re.compile(r"\bcustomer access\s+(?:is\s+)?(?:open|ready)\b", re.IGNORECASE)),
    (
        "market_validation_complete",
        re.compile(r"\bmarket validation\s+(?:is\s+)?(?:complete|completed)\b", re.IGNORECASE),
    ),
    ("support_ready", re.compile(r"\bsupport\s+(?:is\s+)?ready\b", re.IGNORECASE)),
    (
        "legal_clearance_approved",
        re.compile(r"\blegal clearance\s+(?:is\s+)?(?:approved|complete|completed)\b", re.IGNORECASE),
    ),
    ("paid_pilot_ready", re.compile(r"\bpaid pilot\s+(?:is\s+)?(?:ready|open)\b", re.IGNORECASE)),
    ("payment_enabled", re.compile(r"\bpayment\s+(?:is\s+)?enabled\b", re.IGNORECASE)),
    ("money_movement_allowed", re.compile(r"\bmoney movement\s+(?:is\s+)?allowed\b", re.IGNORECASE)),
    ("external_publication_approved", re.compile(r"\bexternal publication (?:allowed|approved|ready)\b", re.IGNORECASE)),
    ("deployment_ready", re.compile(r"\bdeployment\s+(?:is\s+)?ready\b", re.IGNORECASE)),
)


@dataclass(frozen=True, slots=True)
class PilotDeferralRehearsalFinding:
    """One deterministic pilot-deferral rehearsal validation finding."""

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


def validate_doc_text(text: str) -> list[PilotDeferralRehearsalFinding]:
    """Return findings for missing pilot-deferral rehearsal documentation anchors."""

    findings: list[PilotDeferralRehearsalFinding] = []
    for phrase in REQUIRED_DOC_PHRASES:
        if phrase not in text:
            findings.append(
                PilotDeferralRehearsalFinding(
                    "foundation_pilot_deferral_rehearsal_doc_phrase_missing",
                    f"pilot-deferral rehearsal boundary doc missing required phrase: {phrase}",
                )
            )
    return findings


def validate_packet(payload: dict[str, Any]) -> list[PilotDeferralRehearsalFinding]:
    """Return findings for pilot-deferral rehearsal witness drift."""

    findings: list[PilotDeferralRehearsalFinding] = []
    findings.extend(validate_root_contract(payload))
    findings.extend(validate_surfaces(payload.get("surfaces")))
    findings.extend(validate_forbidden_value_patterns(payload))
    findings.extend(validate_forbidden_promotion_patterns(payload))
    return findings


def validate_root_contract(payload: dict[str, Any]) -> list[PilotDeferralRehearsalFinding]:
    """Return findings for root-level pilot-deferral rehearsal witness drift."""

    findings: list[PilotDeferralRehearsalFinding] = []
    if set(payload) != EXPECTED_ROOT_KEYS:
        findings.append(
            PilotDeferralRehearsalFinding(
                "pilot_deferral_rehearsal_root_keys_invalid",
                f"root keys must be: {', '.join(sorted(EXPECTED_ROOT_KEYS))}",
            )
        )
    expected_values = {
        "witness_id": EXPECTED_WITNESS_ID,
        "schema_version": 1,
        "status": "AwaitingEvidence",
        "solver_outcome": "AwaitingEvidence",
        "deferral_rehearsal_executed": False,
        "pilot_execution_allowed": False,
        "participant_invitation_allowed": False,
        "access_channel_opening_allowed": False,
        "waitlist_opening_allowed": False,
        "pilot_signup_open": False,
        "customer_access_allowed": False,
        "personal_data_collection_allowed": False,
        "market_validation_claimed": False,
        "support_readiness_claimed": False,
        "legal_clearance_claimed": False,
        "paid_pilot_allowed": False,
        "payment_enabled": False,
        "money_movement_allowed": False,
        "external_publication_allowed": False,
        "secret_material_allowed": False,
        "deployment_allowed": False,
    }
    for key, expected_value in expected_values.items():
        if payload.get(key) != expected_value:
            findings.append(
                PilotDeferralRehearsalFinding(
                    "pilot_deferral_rehearsal_root_value_invalid",
                    f"{key} must be {expected_value!r}",
                )
            )
    if tuple(payload.get("blocked_claims") or ()) != EXPECTED_BLOCKED_CLAIMS:
        findings.append(
            PilotDeferralRehearsalFinding(
                "pilot_deferral_rehearsal_blocked_claims_invalid",
                f"blocked_claims must be: {', '.join(EXPECTED_BLOCKED_CLAIMS)}",
            )
        )
    next_action = payload.get("next_action")
    if not isinstance(next_action, str) or "draft local pilot-deferral rehearsal questions only" not in next_action:
        findings.append(
            PilotDeferralRehearsalFinding(
                "pilot_deferral_rehearsal_next_action_invalid",
                "next_action must preserve local pilot-deferral rehearsal question drafting only",
            )
        )
    return findings


def validate_surfaces(surfaces: object) -> list[PilotDeferralRehearsalFinding]:
    """Return findings for pilot-deferral rehearsal surface witness drift."""

    findings: list[PilotDeferralRehearsalFinding] = []
    if not isinstance(surfaces, list) or not all(isinstance(surface, dict) for surface in surfaces):
        return [PilotDeferralRehearsalFinding("pilot_deferral_rehearsal_surfaces_invalid", "surfaces must be a list")]
    observed_surfaces = tuple(
        (surface.get("surface_id"), surface.get("surface_type"), surface.get("state"))
        for surface in surfaces
    )
    if observed_surfaces != EXPECTED_SURFACES:
        findings.append(
            PilotDeferralRehearsalFinding(
                "pilot_deferral_rehearsal_surface_inventory_invalid",
                "pilot-deferral rehearsal surface inventory does not match the expected set",
            )
        )
    surface_ids = [surface.get("surface_id") for surface in surfaces]
    if len(set(surface_ids)) != len(surface_ids):
        findings.append(PilotDeferralRehearsalFinding("pilot_deferral_rehearsal_surface_duplicate", "surface ids must be unique"))
    for surface in surfaces:
        surface_id = str(surface.get("surface_id", "<missing>"))
        if set(surface) != EXPECTED_SURFACE_KEYS:
            findings.append(
                PilotDeferralRehearsalFinding(
                    "pilot_deferral_rehearsal_surface_keys_invalid",
                    f"{surface_id} surface keys must be: {', '.join(sorted(EXPECTED_SURFACE_KEYS))}",
                )
            )
        if surface.get("state") != "AwaitingEvidence":
            findings.append(
                PilotDeferralRehearsalFinding(
                    "pilot_deferral_rehearsal_surface_state_invalid",
                    f"{surface_id} state must be AwaitingEvidence",
                )
            )
        if surface.get("evidence_ref") != "manual_preparation_pending":
            findings.append(
                PilotDeferralRehearsalFinding(
                    "pilot_deferral_rehearsal_surface_evidence_invalid",
                    f"{surface_id} evidence_ref must stay manual_preparation_pending",
                )
            )
        if not isinstance(surface.get("public_safe_note"), str) or not surface["public_safe_note"].strip():
            findings.append(
                PilotDeferralRehearsalFinding(
                    "pilot_deferral_rehearsal_surface_note_invalid",
                    f"{surface_id} public_safe_note must be a non-empty string",
                )
            )
    return findings


def validate_forbidden_value_patterns(payload: dict[str, Any]) -> list[PilotDeferralRehearsalFinding]:
    """Return findings for participant, account, billing, private, secret, or deployment-shaped values."""

    serialized_payload = json.dumps(payload, sort_keys=True)
    findings: list[PilotDeferralRehearsalFinding] = []
    for rule_id, pattern in FORBIDDEN_VALUE_PATTERNS:
        if pattern.search(serialized_payload):
            findings.append(
                PilotDeferralRehearsalFinding(
                    "pilot_deferral_rehearsal_forbidden_value_pattern",
                    f"pilot-deferral rehearsal witness contains forbidden value pattern: {rule_id}",
                )
            )
    return findings


def validate_forbidden_promotion_patterns(payload: dict[str, Any]) -> list[PilotDeferralRehearsalFinding]:
    """Return findings if the witness drifts into pilot or exposure claims."""

    serialized_payload = json.dumps(payload, sort_keys=True)
    findings: list[PilotDeferralRehearsalFinding] = []
    for rule_id, pattern in FORBIDDEN_PROMOTION_PATTERNS:
        if pattern.search(serialized_payload):
            findings.append(
                PilotDeferralRehearsalFinding(
                    "pilot_deferral_rehearsal_forbidden_promotion_phrase",
                    f"pilot-deferral rehearsal witness contains forbidden promotion pattern: {rule_id}",
                )
            )
    return findings


def validate_foundation_pilot_deferral_rehearsal_boundary(
    doc_path: Path = DEFAULT_DOC_PATH,
    packet_path: Path = DEFAULT_PACKET_PATH,
) -> list[PilotDeferralRehearsalFinding]:
    """Validate the Foundation Mode pilot-deferral rehearsal boundary artifacts."""

    doc_text = load_text(doc_path, "pilot-deferral rehearsal boundary doc")
    packet_payload = load_json_object(packet_path, "pilot-deferral rehearsal witness packet")
    return [
        *validate_doc_text(doc_text),
        *validate_packet(packet_payload),
    ]


def main(argv: list[str] | None = None) -> int:
    """Validate pilot-deferral rehearsal artifacts and print deterministic status."""

    parser = argparse.ArgumentParser(description="Validate Foundation Mode pilot-deferral rehearsal boundary artifacts.")
    parser.add_argument("--doc", type=Path, default=DEFAULT_DOC_PATH)
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET_PATH)
    args = parser.parse_args(argv)

    try:
        findings = validate_foundation_pilot_deferral_rehearsal_boundary(args.doc, args.packet)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"[FAIL] foundation_pilot_deferral_rehearsal_load: {exc}", file=sys.stderr)
        print("STATUS: failed", file=sys.stderr)
        return 1

    if findings:
        for finding in findings:
            print(f"[FAIL] {finding.rule_id}: {finding.message}", file=sys.stderr)
        print("STATUS: failed", file=sys.stderr)
        return 1
    print("[PASS] foundation_pilot_deferral_rehearsal_doc")
    print("[PASS] foundation_pilot_deferral_rehearsal_witness")
    print("STATUS: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
