#!/usr/bin/env python3
"""Validate the Foundation Mode pilot-deferral boundary.

Purpose: keep pilot preparation deferred while pilot execution, participant
invitation, access-channel opening, waitlists, beta, customer access,
personal-data collection, market-validation claims, support-readiness claims,
legal-clearance claims, paid-pilot claims, external publication, and deployment
claims remain blocked.
Governance scope: Foundation Mode, pilot deferral, public-safe planning
witness, private-value exclusion, intake blocking, support-duty blocking,
privacy caution, legal/business restraint, public-claim restraint, and
deployment blocking.
Dependencies: docs/FOUNDATION_PILOT_DEFERRAL_BOUNDARY.md and
examples/foundation_pilot_deferral_witness.awaiting_evidence.json.
Invariants:
  - Validation is read-only.
  - The witness records pilot-deferral planning only.
  - No pilot execution, participant invitation, access-channel opening,
    waitlist, beta, customer access, personal-data collection, market
    validation, support readiness, legal clearance, paid pilot, private value,
    external publication, or deployment claim is allowed.
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
DEFAULT_DOC_PATH = REPO_ROOT / "docs" / "FOUNDATION_PILOT_DEFERRAL_BOUNDARY.md"
DEFAULT_PACKET_PATH = REPO_ROOT / "examples" / "foundation_pilot_deferral_witness.awaiting_evidence.json"

EXPECTED_WITNESS_ID = "foundation_pilot_deferral_witness.awaiting_evidence.v1"
EXPECTED_BLOCKED_CLAIMS = (
    "pilot execution",
    "participant invitation",
    "access channel opening",
    "waitlist opening",
    "beta opening",
    "customer access",
    "personal data collection",
    "market validation",
    "support readiness",
    "legal clearance",
    "paid pilot",
    "external publication",
    "deployment readiness",
)
EXPECTED_SURFACES = (
    ("pilot_purpose_questions", "local_draft", "AwaitingEvidence"),
    ("participant_boundary_questions", "local_draft", "AwaitingEvidence"),
    ("access_channel_questions", "local_draft", "AwaitingEvidence"),
    ("consent_privacy_questions", "local_draft", "AwaitingEvidence"),
    ("support_coverage_questions", "local_draft", "AwaitingEvidence"),
    ("rollback_exit_questions", "local_draft", "AwaitingEvidence"),
    ("success_metric_questions", "local_draft", "AwaitingEvidence"),
    ("legal_terms_questions", "local_draft", "AwaitingEvidence"),
    ("public_claim_questions", "local_draft", "AwaitingEvidence"),
)
EXPECTED_ROOT_KEYS = {
    "access_channel_allowed",
    "beta_allowed",
    "blocked_claims",
    "customer_access_allowed",
    "deployment_allowed",
    "external_publication_allowed",
    "legal_clearance_claimed",
    "market_validation_claimed",
    "next_action",
    "paid_pilot_allowed",
    "participant_invitation_allowed",
    "personal_data_collection_allowed",
    "pilot_deferral_surfaces",
    "pilot_execution_allowed",
    "schema_version",
    "solver_outcome",
    "status",
    "support_ready_claimed",
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
    "Foundation Pilot Deferral Boundary",
    "Witness packet: [`../examples/foundation_pilot_deferral_witness.awaiting_evidence.json`]",
    "Rule: Pilot deferral is a local planning boundary, not a pilot-execution, participant-invitation, access-opening, market-validation, support-readiness, legal-clearance, paid-pilot, publication, or deployment certificate.",
    "No pilot execution, participant invitation, access channel opening, waitlist",
    "pilot_deferral_boundary_state=AwaitingEvidence",
    "pilot_execution_allowed=false",
    "participant_invitation_allowed=false",
    "access_channel_allowed=false",
    "deployment_allowed=false",
    "python scripts/validate_foundation_pilot_deferral_boundary.py",
)
FORBIDDEN_VALUE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("url_value", re.compile(r"https?://", re.IGNORECASE)),
    ("email_value", re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)),
    ("private_path", re.compile(r"\b[A-Za-z]:[\\/]|\\\\", re.IGNORECASE)),
    ("person_assignment", re.compile(r"\b(?:person|participant|customer|user|pilot)[_ -]?(?:name|email|id|ref|value)?\s*=", re.IGNORECASE)),
    ("provider_assignment", re.compile(r"\b(?:provider|account|tenant|project)[_ -]?(?:id|ref|target|value)?\s*=", re.IGNORECASE)),
    ("schedule_assignment", re.compile(r"\b(?:deadline|pilot|launch|schedule|date)[_ -]?(?:at|date|time|value)?\s*=", re.IGNORECASE)),
    ("billing_assignment", re.compile(r"\b(?:billing|payment|card|invoice|subscription|price)[_ -]?(?:id|ref|target|value)?\s*=", re.IGNORECASE)),
    ("intake_assignment", re.compile(r"\b(?:form|waitlist|signup|intake)[_ -]?(?:url|uri|id|ref|value)?\s*=", re.IGNORECASE)),
    ("secret_assignment", re.compile(r"\b(?:password|secret|token|api[_ -]?key|credential)\s*=", re.IGNORECASE)),
)
FORBIDDEN_PROMOTION_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("pilot_ready", re.compile(r"\bpilot\s+(?:is\s+)?ready\b", re.IGNORECASE)),
    ("pilot_open", re.compile(r"\bpilot\s+(?:is\s+)?open\b", re.IGNORECASE)),
    ("pilot_approved", re.compile(r"\bpilot\s+(?:is\s+)?approved\b", re.IGNORECASE)),
    ("participant_invited", re.compile(r"\bparticipant\s+(?:is\s+)?invited\b", re.IGNORECASE)),
    ("access_open", re.compile(r"\baccess\s+(?:is\s+)?open\b", re.IGNORECASE)),
    ("waitlist_open", re.compile(r"\bwaitlist\s+(?:is\s+)?open\b", re.IGNORECASE)),
    ("beta_open", re.compile(r"\bbeta\s+(?:is\s+)?open\b", re.IGNORECASE)),
    ("market_validated", re.compile(r"\bmarket\s+(?:is\s+)?validated\b", re.IGNORECASE)),
    ("support_ready", re.compile(r"\bsupport\s+(?:is\s+)?ready\b", re.IGNORECASE)),
    ("legal_cleared", re.compile(r"\blegal\s+(?:is\s+)?cleared\b", re.IGNORECASE)),
    ("paid_pilot_ready", re.compile(r"\bpaid\s+pilot\s+(?:is\s+)?ready\b", re.IGNORECASE)),
    ("externally_published", re.compile(r"\bexternally\s+published\b", re.IGNORECASE)),
    ("deployment_ready", re.compile(r"\bdeployment\s+(?:is\s+)?ready\b", re.IGNORECASE)),
)


@dataclass(frozen=True, slots=True)
class PilotDeferralFinding:
    """One deterministic pilot-deferral boundary validation finding."""

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


def validate_doc_text(text: str) -> list[PilotDeferralFinding]:
    """Return findings for missing pilot-deferral documentation anchors."""

    findings: list[PilotDeferralFinding] = []
    for phrase in REQUIRED_DOC_PHRASES:
        if phrase not in text:
            findings.append(
                PilotDeferralFinding(
                    "foundation_pilot_deferral_doc_phrase_missing",
                    f"pilot-deferral boundary doc missing required phrase: {phrase}",
                )
            )
    return findings


def validate_packet(payload: dict[str, Any]) -> list[PilotDeferralFinding]:
    """Return findings for pilot-deferral witness drift."""

    findings: list[PilotDeferralFinding] = []
    findings.extend(validate_root_contract(payload))
    findings.extend(validate_pilot_deferral_surfaces(payload.get("pilot_deferral_surfaces")))
    findings.extend(validate_forbidden_value_patterns(payload))
    findings.extend(validate_forbidden_promotion_patterns(payload))
    return findings


def validate_root_contract(payload: dict[str, Any]) -> list[PilotDeferralFinding]:
    """Return findings for root-level pilot-deferral witness drift."""

    findings: list[PilotDeferralFinding] = []
    if set(payload) != EXPECTED_ROOT_KEYS:
        findings.append(
            PilotDeferralFinding(
                "pilot_deferral_root_keys_invalid",
                f"root keys must be: {', '.join(sorted(EXPECTED_ROOT_KEYS))}",
            )
        )
    expected_values = {
        "witness_id": EXPECTED_WITNESS_ID,
        "schema_version": 1,
        "status": "AwaitingEvidence",
        "solver_outcome": "AwaitingEvidence",
        "pilot_execution_allowed": False,
        "participant_invitation_allowed": False,
        "access_channel_allowed": False,
        "waitlist_allowed": False,
        "beta_allowed": False,
        "customer_access_allowed": False,
        "personal_data_collection_allowed": False,
        "market_validation_claimed": False,
        "support_ready_claimed": False,
        "legal_clearance_claimed": False,
        "paid_pilot_allowed": False,
        "external_publication_allowed": False,
        "deployment_allowed": False,
    }
    for key, expected_value in expected_values.items():
        if payload.get(key) != expected_value:
            findings.append(
                PilotDeferralFinding(
                    "pilot_deferral_root_value_invalid",
                    f"{key} must be {expected_value!r}",
                )
            )
    if tuple(payload.get("blocked_claims") or ()) != EXPECTED_BLOCKED_CLAIMS:
        findings.append(
            PilotDeferralFinding(
                "pilot_deferral_blocked_claims_invalid",
                f"blocked_claims must be: {', '.join(EXPECTED_BLOCKED_CLAIMS)}",
            )
        )
    next_action = payload.get("next_action")
    if not isinstance(next_action, str) or "keep pilot deferred" not in next_action:
        findings.append(
            PilotDeferralFinding(
                "pilot_deferral_next_action_invalid",
                "next_action must preserve the pilot deferral boundary",
            )
        )
    return findings


def validate_pilot_deferral_surfaces(pilot_deferral_surfaces: object) -> list[PilotDeferralFinding]:
    """Return findings for pilot-deferral surface witness drift."""

    findings: list[PilotDeferralFinding] = []
    if not isinstance(pilot_deferral_surfaces, list) or not all(
        isinstance(surface, dict) for surface in pilot_deferral_surfaces
    ):
        return [
            PilotDeferralFinding(
                "pilot_deferral_surfaces_invalid",
                "pilot_deferral_surfaces must be a list of objects",
            )
        ]
    observed_surfaces = tuple(
        (surface.get("surface_id"), surface.get("surface_type"), surface.get("state"))
        for surface in pilot_deferral_surfaces
    )
    if observed_surfaces != EXPECTED_SURFACES:
        findings.append(
            PilotDeferralFinding(
                "pilot_deferral_surface_inventory_invalid",
                "pilot-deferral surface inventory does not match the Foundation Mode pilot set",
            )
        )
    surface_ids = [surface.get("surface_id") for surface in pilot_deferral_surfaces]
    if len(set(surface_ids)) != len(surface_ids):
        findings.append(PilotDeferralFinding("pilot_deferral_surface_duplicate", "surface ids must be unique"))
    for surface in pilot_deferral_surfaces:
        surface_id = str(surface.get("surface_id", "<missing>"))
        if set(surface) != EXPECTED_SURFACE_KEYS:
            findings.append(
                PilotDeferralFinding(
                    "pilot_deferral_surface_keys_invalid",
                    f"{surface_id} surface keys must be: {', '.join(sorted(EXPECTED_SURFACE_KEYS))}",
                )
            )
        if surface.get("state") != "AwaitingEvidence":
            findings.append(
                PilotDeferralFinding(
                    "pilot_deferral_surface_state_invalid",
                    f"{surface_id} state must be AwaitingEvidence",
                )
            )
        if surface.get("evidence_ref") != "manual_preparation_pending":
            findings.append(
                PilotDeferralFinding(
                    "pilot_deferral_surface_evidence_invalid",
                    f"{surface_id} evidence_ref must stay manual_preparation_pending in the committed packet",
                )
            )
        if not isinstance(surface.get("public_safe_note"), str) or not surface["public_safe_note"].strip():
            findings.append(
                PilotDeferralFinding(
                    "pilot_deferral_surface_note_invalid",
                    f"{surface_id} public_safe_note must be a non-empty string",
                )
            )
    return findings


def validate_forbidden_value_patterns(payload: dict[str, Any]) -> list[PilotDeferralFinding]:
    """Return findings for participant, access, intake, provider, billing, path, or secret-shaped values."""

    serialized_payload = json.dumps(payload, sort_keys=True)
    findings: list[PilotDeferralFinding] = []
    for rule_id, pattern in FORBIDDEN_VALUE_PATTERNS:
        if pattern.search(serialized_payload):
            findings.append(
                PilotDeferralFinding(
                    "pilot_deferral_forbidden_private_value_pattern",
                    f"pilot-deferral witness contains forbidden value pattern: {rule_id}",
                )
            )
    return findings


def validate_forbidden_promotion_patterns(payload: dict[str, Any]) -> list[PilotDeferralFinding]:
    """Return findings if the witness drifts into pilot readiness or exposure claims."""

    serialized_payload = json.dumps(payload, sort_keys=True)
    findings: list[PilotDeferralFinding] = []
    for rule_id, pattern in FORBIDDEN_PROMOTION_PATTERNS:
        if pattern.search(serialized_payload):
            findings.append(
                PilotDeferralFinding(
                    "pilot_deferral_forbidden_promotion_phrase",
                    f"pilot-deferral witness contains forbidden promotion pattern: {rule_id}",
                )
            )
    return findings


def validate_foundation_pilot_deferral_boundary(
    doc_path: Path = DEFAULT_DOC_PATH,
    packet_path: Path = DEFAULT_PACKET_PATH,
) -> list[PilotDeferralFinding]:
    """Validate the Foundation Mode pilot-deferral boundary artifacts."""

    doc_text = load_text(doc_path, "pilot-deferral boundary doc")
    packet_payload = load_json_object(packet_path, "pilot-deferral witness packet")
    return [
        *validate_doc_text(doc_text),
        *validate_packet(packet_payload),
    ]


def main(argv: list[str] | None = None) -> int:
    """Validate pilot-deferral boundary artifacts and print deterministic status."""

    parser = argparse.ArgumentParser(description="Validate Foundation Mode pilot-deferral boundary artifacts.")
    parser.add_argument("--doc", type=Path, default=DEFAULT_DOC_PATH)
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET_PATH)
    args = parser.parse_args(argv)

    try:
        findings = validate_foundation_pilot_deferral_boundary(args.doc, args.packet)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"[FAIL] foundation_pilot_deferral_load: {exc}", file=sys.stderr)
        print("STATUS: failed", file=sys.stderr)
        return 1

    if findings:
        for finding in findings:
            print(f"[FAIL] {finding.rule_id}: {finding.message}", file=sys.stderr)
        print("STATUS: failed", file=sys.stderr)
        return 1
    print("[PASS] foundation_pilot_deferral_doc")
    print("[PASS] foundation_pilot_deferral_witness")
    print("STATUS: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
