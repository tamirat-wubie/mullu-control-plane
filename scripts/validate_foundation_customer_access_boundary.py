#!/usr/bin/env python3
"""Validate the Foundation Mode customer-access boundary.

Purpose: keep customer-access preparation local while customer access,
invitations, account creation, access channels, onboarding readiness, support
commitments, terms/privacy readiness, personal-data collection, paid access,
pilot access, beta access, waitlists, external publication, and deployment
claims remain blocked.
Governance scope: Foundation Mode, customer-access posture, public-safe
planning witness, private-value exclusion, personal-data exclusion, access
blocking, and deployment blocking.
Dependencies: docs/FOUNDATION_CUSTOMER_ACCESS_BOUNDARY.md and
examples/foundation_customer_access_witness.awaiting_evidence.json.
Invariants:
  - Validation is read-only.
  - The witness records local customer-access planning only.
  - No invitation, account creation, access channel, onboarding, support duty,
    terms/privacy readiness, personal-data collection, paid access, pilot/beta
    access, waitlist, private value, external publication, or deployment claim
    is allowed.
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
DEFAULT_DOC_PATH = REPO_ROOT / "docs" / "FOUNDATION_CUSTOMER_ACCESS_BOUNDARY.md"
DEFAULT_PACKET_PATH = REPO_ROOT / "examples" / "foundation_customer_access_witness.awaiting_evidence.json"

EXPECTED_WITNESS_ID = "foundation_customer_access_witness.awaiting_evidence.v1"
EXPECTED_BLOCKED_CLAIMS = (
    "customer access opening",
    "customer invitation",
    "account creation",
    "onboarding readiness",
    "support commitment",
    "terms/privacy readiness",
    "personal data collection",
    "paid access",
    "pilot access",
    "beta access",
    "waitlist opening",
    "external publication",
    "deployment readiness",
)
EXPECTED_SURFACES = (
    ("access_policy_questions", "local_draft", "AwaitingEvidence"),
    ("eligibility_boundary_questions", "local_draft", "AwaitingEvidence"),
    ("account_creation_questions", "local_draft", "AwaitingEvidence"),
    ("invitation_flow_questions", "local_draft", "AwaitingEvidence"),
    ("support_duty_questions", "local_draft", "AwaitingEvidence"),
    ("terms_privacy_questions", "local_draft", "AwaitingEvidence"),
    ("data_handling_questions", "local_draft", "AwaitingEvidence"),
    ("rollback_exit_questions", "local_draft", "AwaitingEvidence"),
    ("payment_exposure_questions", "local_draft", "AwaitingEvidence"),
    ("public_claim_questions", "local_draft", "AwaitingEvidence"),
)
EXPECTED_ROOT_KEYS = {
    "access_channel_open_allowed",
    "account_creation_allowed",
    "beta_access_allowed",
    "blocked_claims",
    "customer_access_allowed",
    "customer_access_surfaces",
    "customer_invitation_allowed",
    "deployment_allowed",
    "external_publication_allowed",
    "next_action",
    "onboarding_ready_claimed",
    "paid_access_allowed",
    "personal_data_collection_allowed",
    "pilot_access_allowed",
    "schema_version",
    "solver_outcome",
    "status",
    "support_commitment_allowed",
    "terms_privacy_ready_claimed",
    "waitlist_open",
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
    "Foundation Customer Access Boundary",
    "Witness packet: [`../examples/foundation_customer_access_witness.awaiting_evidence.json`]",
    "Rule: Customer-access preparation is a local planning boundary, not an access approval.",
    "No customer access opening, customer invitation, account creation, access-channel",
    "customer_access_boundary_state=AwaitingEvidence",
    "customer_access_allowed=false",
    "customer_invitation_allowed=false",
    "account_creation_allowed=false",
    "personal_data_collection_allowed=false",
    "deployment_allowed=false",
    "python scripts/validate_foundation_customer_access_boundary.py",
)
FORBIDDEN_VALUE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("url_value", re.compile(r"https?://", re.IGNORECASE)),
    ("email_value", re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)),
    ("private_path", re.compile(r"\b[A-Za-z]:[\\/]|\\\\", re.IGNORECASE)),
    ("account_assignment", re.compile(r"\b(?:account|tenant|login|identity)[_ -]?(?:id|ref|target|value)?\s*=", re.IGNORECASE)),
    ("invite_assignment", re.compile(r"\b(?:invite|invitation|access[_ -]?link|signup)[_ -]?(?:id|url|link|target|value)?\s*=", re.IGNORECASE)),
    ("customer_assignment", re.compile(r"\b(?:customer|user|participant|payer)[_ -]?(?:id|email|name|ref|value)?\s*=", re.IGNORECASE)),
    ("form_link_assignment", re.compile(r"\b(?:form|survey|waitlist|beta|pilot)[_ -]?(?:url|link|id|target)\s*=", re.IGNORECASE)),
    ("payment_assignment", re.compile(r"\b(?:payment|card|invoice|subscription|billing)[_ -]?(?:id|ref|target|value)?\s*=", re.IGNORECASE)),
    ("secret_assignment", re.compile(r"\b(?:password|secret|token|api[_ -]?key|credential)\s*=", re.IGNORECASE)),
    ("private_key_material", re.compile(r"BEGIN [A-Z ]*PRIVATE KEY")),
)
FORBIDDEN_PROMOTION_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("customer_access_open", re.compile(r"\bcustomer\s+access\s+(?:is\s+)?open\b", re.IGNORECASE)),
    ("customers_invited", re.compile(r"\bcustomers?\s+(?:are\s+)?invited\b", re.IGNORECASE)),
    ("accounts_created", re.compile(r"\baccounts?\s+(?:are\s+)?created\b", re.IGNORECASE)),
    ("access_channel_open", re.compile(r"\baccess\s+channel\s+(?:is\s+)?open\b", re.IGNORECASE)),
    ("onboarding_ready", re.compile(r"\bonboarding\s+(?:is\s+)?ready\b", re.IGNORECASE)),
    ("support_committed", re.compile(r"\bsupport\s+(?:is\s+)?committed\b", re.IGNORECASE)),
    ("terms_ready", re.compile(r"\bterms\s+(?:are\s+)?ready\b", re.IGNORECASE)),
    ("privacy_ready", re.compile(r"\bprivacy\s+(?:is\s+)?ready\b", re.IGNORECASE)),
    ("collecting_personal_data", re.compile(r"\bcollecting\s+personal\s+data\b", re.IGNORECASE)),
    ("paid_access_open", re.compile(r"\bpaid\s+access\s+(?:is\s+)?open\b", re.IGNORECASE)),
    ("pilot_access_open", re.compile(r"\bpilot\s+access\s+(?:is\s+)?open\b", re.IGNORECASE)),
    ("beta_access_open", re.compile(r"\bbeta\s+access\s+(?:is\s+)?open\b", re.IGNORECASE)),
    ("waitlist_open", re.compile(r"\bwaitlist\s+(?:is\s+)?open\b", re.IGNORECASE)),
)


@dataclass(frozen=True, slots=True)
class CustomerAccessFinding:
    """One deterministic customer-access boundary validation finding."""

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


def validate_doc_text(text: str) -> list[CustomerAccessFinding]:
    """Return findings for missing customer-access documentation anchors."""

    findings: list[CustomerAccessFinding] = []
    for phrase in REQUIRED_DOC_PHRASES:
        if phrase not in text:
            findings.append(
                CustomerAccessFinding(
                    "foundation_customer_access_doc_phrase_missing",
                    f"customer-access boundary doc missing required phrase: {phrase}",
                )
            )
    return findings


def validate_packet(payload: dict[str, Any]) -> list[CustomerAccessFinding]:
    """Return findings for customer-access witness drift."""

    findings: list[CustomerAccessFinding] = []
    findings.extend(validate_root_contract(payload))
    findings.extend(validate_customer_access_surfaces(payload.get("customer_access_surfaces")))
    findings.extend(validate_forbidden_value_patterns(payload))
    findings.extend(validate_forbidden_promotion_patterns(payload))
    return findings


def validate_root_contract(payload: dict[str, Any]) -> list[CustomerAccessFinding]:
    """Return findings for root-level customer-access witness drift."""

    findings: list[CustomerAccessFinding] = []
    if set(payload) != EXPECTED_ROOT_KEYS:
        findings.append(
            CustomerAccessFinding(
                "customer_access_root_keys_invalid",
                f"root keys must be: {', '.join(sorted(EXPECTED_ROOT_KEYS))}",
            )
        )
    expected_values = {
        "witness_id": EXPECTED_WITNESS_ID,
        "schema_version": 1,
        "status": "AwaitingEvidence",
        "solver_outcome": "AwaitingEvidence",
        "customer_access_allowed": False,
        "customer_invitation_allowed": False,
        "account_creation_allowed": False,
        "access_channel_open_allowed": False,
        "onboarding_ready_claimed": False,
        "support_commitment_allowed": False,
        "terms_privacy_ready_claimed": False,
        "personal_data_collection_allowed": False,
        "paid_access_allowed": False,
        "pilot_access_allowed": False,
        "beta_access_allowed": False,
        "waitlist_open": False,
        "external_publication_allowed": False,
        "deployment_allowed": False,
    }
    for key, expected_value in expected_values.items():
        if payload.get(key) != expected_value:
            findings.append(
                CustomerAccessFinding(
                    "customer_access_root_value_invalid",
                    f"{key} must be {expected_value!r}",
                )
            )
    if tuple(payload.get("blocked_claims") or ()) != EXPECTED_BLOCKED_CLAIMS:
        findings.append(
            CustomerAccessFinding(
                "customer_access_blocked_claims_invalid",
                f"blocked_claims must be: {', '.join(EXPECTED_BLOCKED_CLAIMS)}",
            )
        )
    next_action = payload.get("next_action")
    if not isinstance(next_action, str) or "keep customer access closed" not in next_action:
        findings.append(
            CustomerAccessFinding(
                "customer_access_next_action_invalid",
                "next_action must preserve the closed customer-access boundary",
            )
        )
    return findings


def validate_customer_access_surfaces(
    customer_access_surfaces: object,
) -> list[CustomerAccessFinding]:
    """Return findings for customer-access surface witness drift."""

    findings: list[CustomerAccessFinding] = []
    if not isinstance(customer_access_surfaces, list) or not all(
        isinstance(surface, dict) for surface in customer_access_surfaces
    ):
        return [
            CustomerAccessFinding(
                "customer_access_surfaces_invalid",
                "customer_access_surfaces must be a list of objects",
            )
        ]
    observed_surfaces = tuple(
        (surface.get("surface_id"), surface.get("surface_type"), surface.get("state"))
        for surface in customer_access_surfaces
    )
    if observed_surfaces != EXPECTED_SURFACES:
        findings.append(
            CustomerAccessFinding(
                "customer_access_surface_inventory_invalid",
                "customer-access surface inventory does not match the Foundation Mode access set",
            )
        )
    surface_ids = [surface.get("surface_id") for surface in customer_access_surfaces]
    if len(set(surface_ids)) != len(surface_ids):
        findings.append(CustomerAccessFinding("customer_access_surface_duplicate", "surface ids must be unique"))
    for surface in customer_access_surfaces:
        surface_id = str(surface.get("surface_id", "<missing>"))
        if set(surface) != EXPECTED_SURFACE_KEYS:
            findings.append(
                CustomerAccessFinding(
                    "customer_access_surface_keys_invalid",
                    f"{surface_id} surface keys must be: {', '.join(sorted(EXPECTED_SURFACE_KEYS))}",
                )
            )
        if surface.get("state") != "AwaitingEvidence":
            findings.append(
                CustomerAccessFinding(
                    "customer_access_surface_state_invalid",
                    f"{surface_id} state must be AwaitingEvidence",
                )
            )
        if surface.get("evidence_ref") != "manual_preparation_pending":
            findings.append(
                CustomerAccessFinding(
                    "customer_access_surface_evidence_invalid",
                    f"{surface_id} evidence_ref must stay manual_preparation_pending in the committed packet",
                )
            )
        if not isinstance(surface.get("public_safe_note"), str) or not surface["public_safe_note"].strip():
            findings.append(
                CustomerAccessFinding(
                    "customer_access_surface_note_invalid",
                    f"{surface_id} public_safe_note must be a non-empty string",
                )
            )
    return findings


def validate_forbidden_value_patterns(payload: dict[str, Any]) -> list[CustomerAccessFinding]:
    """Return findings for URL, email, account, invite, customer, payment, path, or secret-shaped values."""

    serialized_payload = json.dumps(payload, sort_keys=True)
    findings: list[CustomerAccessFinding] = []
    for rule_id, pattern in FORBIDDEN_VALUE_PATTERNS:
        if pattern.search(serialized_payload):
            findings.append(
                CustomerAccessFinding(
                    "customer_access_forbidden_private_value_pattern",
                    f"customer-access witness contains forbidden value pattern: {rule_id}",
                )
            )
    return findings


def validate_forbidden_promotion_patterns(payload: dict[str, Any]) -> list[CustomerAccessFinding]:
    """Return findings if the witness drifts into customer-access readiness claims."""

    serialized_payload = json.dumps(payload, sort_keys=True)
    findings: list[CustomerAccessFinding] = []
    for rule_id, pattern in FORBIDDEN_PROMOTION_PATTERNS:
        if pattern.search(serialized_payload):
            findings.append(
                CustomerAccessFinding(
                    "customer_access_forbidden_promotion_phrase",
                    f"customer-access witness contains forbidden promotion pattern: {rule_id}",
                )
            )
    return findings


def validate_foundation_customer_access_boundary(
    doc_path: Path = DEFAULT_DOC_PATH,
    packet_path: Path = DEFAULT_PACKET_PATH,
) -> list[CustomerAccessFinding]:
    """Validate the Foundation Mode customer-access boundary artifacts."""

    doc_text = load_text(doc_path, "customer-access boundary doc")
    packet_payload = load_json_object(packet_path, "customer-access witness packet")
    return [
        *validate_doc_text(doc_text),
        *validate_packet(packet_payload),
    ]


def main(argv: list[str] | None = None) -> int:
    """Validate customer-access boundary artifacts and print deterministic status."""

    parser = argparse.ArgumentParser(description="Validate Foundation Mode customer-access boundary artifacts.")
    parser.add_argument("--doc", type=Path, default=DEFAULT_DOC_PATH)
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET_PATH)
    args = parser.parse_args(argv)

    try:
        findings = validate_foundation_customer_access_boundary(args.doc, args.packet)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"[FAIL] foundation_customer_access_load: {exc}", file=sys.stderr)
        print("STATUS: failed", file=sys.stderr)
        return 1

    if findings:
        for finding in findings:
            print(f"[FAIL] {finding.rule_id}: {finding.message}", file=sys.stderr)
        print("STATUS: failed", file=sys.stderr)
        return 1
    print("[PASS] foundation_customer_access_doc")
    print("[PASS] foundation_customer_access_witness")
    print("STATUS: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
