#!/usr/bin/env python3
"""Validate the Foundation Mode customer-access policy rehearsal boundary.

Purpose: keep customer-access policy rehearsal local and public-safe while
access approval, invitations, accounts, tenants, login routes, support
commitments, terms/privacy readiness, personal-data collection, paid access,
pilot/beta/waitlist access, external publication, and deployment remain
blocked.
Governance scope: Foundation Mode, customer-access policy rehearsal planning,
local eligibility and denial criteria, invitation exclusion, account and tenant
exclusion, login route exclusion, support-duty blocking, terms/privacy
blocking, personal-data exclusion, paid-access blocking, pilot/beta/waitlist
blocking, external-publication restraint, and deployment blocking.
Dependencies: docs/FOUNDATION_CUSTOMER_ACCESS_POLICY_REHEARSAL_BOUNDARY.md and
examples/foundation_customer_access_policy_rehearsal_witness.awaiting_evidence.json.
Invariants:
  - Validation is read-only.
  - The witness records customer-access policy rehearsal planning only.
  - No access approval, invitation, account, tenant, login route, support
    commitment, terms/privacy readiness, personal-data, paid-access,
    pilot/beta/waitlist, external-publication, or deployment claim is allowed.
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
DEFAULT_DOC_PATH = REPO_ROOT / "docs" / "FOUNDATION_CUSTOMER_ACCESS_POLICY_REHEARSAL_BOUNDARY.md"
DEFAULT_PACKET_PATH = REPO_ROOT / "examples" / "foundation_customer_access_policy_rehearsal_witness.awaiting_evidence.json"

EXPECTED_WITNESS_ID = "foundation_customer_access_policy_rehearsal_witness.awaiting_evidence.v1"
EXPECTED_BLOCKED_CLAIMS = (
    "access-policy approval",
    "customer access opening",
    "customer invitation",
    "account creation",
    "tenant provisioning",
    "login route publication",
    "support commitment",
    "terms/privacy readiness",
    "personal-data collection",
    "paid access",
    "pilot/beta/waitlist access",
    "external publication",
    "deployment readiness",
)
EXPECTED_SURFACES = (
    ("entry_criteria_questions", "local_draft", "AwaitingEvidence"),
    ("denial_criteria_questions", "local_draft", "AwaitingEvidence"),
    ("pause_stop_rules", "local_draft", "AwaitingEvidence"),
    ("account_tenant_boundary", "local_draft", "AwaitingEvidence"),
    ("invitation_boundary", "local_draft", "AwaitingEvidence"),
    ("support_duty_boundary", "local_draft", "AwaitingEvidence"),
    ("terms_privacy_boundary", "local_draft", "AwaitingEvidence"),
    ("data_payment_boundary", "local_draft", "AwaitingEvidence"),
    ("publication_deployment_boundary", "local_draft", "AwaitingEvidence"),
    ("handoff_note", "local_draft", "AwaitingEvidence"),
)
EXPECTED_ROOT_KEYS = {
    "access_policy_approved",
    "access_policy_rehearsal_executed",
    "account_creation_allowed",
    "blocked_claims",
    "customer_access_allowed",
    "customer_invitation_allowed",
    "deployment_allowed",
    "external_publication_allowed",
    "login_route_publication_allowed",
    "next_action",
    "paid_access_allowed",
    "personal_data_collection_allowed",
    "pilot_beta_waitlist_access_allowed",
    "schema_version",
    "solver_outcome",
    "status",
    "support_commitment_allowed",
    "surfaces",
    "tenant_provisioning_allowed",
    "terms_privacy_ready_claimed",
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
    "Foundation Customer Access Policy Rehearsal Boundary",
    "Witness packet: [`../examples/foundation_customer_access_policy_rehearsal_witness.awaiting_evidence.json`]",
    "Rule: Customer access policy rehearsal is a local paper exercise, not an access",
    "No access-policy approval, customer access opening, customer invitation",
    "customer_access_policy_rehearsal_boundary_state=AwaitingEvidence",
    "access_policy_rehearsal_executed=false",
    "access_policy_approved=false",
    "customer_access_allowed=false",
    "account_creation_allowed=false",
    "tenant_provisioning_allowed=false",
    "personal_data_collection_allowed=false",
    "deployment_allowed=false",
    "python scripts/validate_foundation_customer_access_policy_rehearsal_boundary.py",
)
FORBIDDEN_VALUE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("url_value", re.compile(r"https?://", re.IGNORECASE)),
    ("email_value", re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)),
    ("private_path", re.compile(r"\b[A-Za-z]:[\\/]|\\\\", re.IGNORECASE)),
    (
        "account_assignment",
        re.compile(r"\b(?:account|tenant|login|identity)[_ -]?(?:id|ref|target|value|url|link)?\s*=", re.IGNORECASE),
    ),
    (
        "invite_assignment",
        re.compile(r"\b(?:invite|invitation|access[_ -]?link|signup)[_ -]?(?:id|url|link|target|value)?\s*=", re.IGNORECASE),
    ),
    (
        "customer_personal_assignment",
        re.compile(r"\b(?:customer|user|participant|payer|personal)[_ -]?(?:id|email|name|data|ref|value)?\s*=", re.IGNORECASE),
    ),
    (
        "support_assignment",
        re.compile(r"\b(?:support|sla|response|incident)[_ -]?(?:id|ref|target|value|status|window)?\s*=", re.IGNORECASE),
    ),
    (
        "terms_privacy_assignment",
        re.compile(r"\b(?:terms|privacy|legal|consent)[_ -]?(?:id|ref|target|value|status)?\s*=", re.IGNORECASE),
    ),
    (
        "payment_assignment",
        re.compile(r"\b(?:payment|card|invoice|subscription|billing|charge)[_ -]?(?:id|ref|target|value|status)?\s*=", re.IGNORECASE),
    ),
    (
        "publication_assignment",
        re.compile(r"\b(?:publication|public|offer)[_ -]?(?:url|link|target|value|status)?\s*=", re.IGNORECASE),
    ),
    (
        "deployment_assignment",
        re.compile(r"\b(?:deploy|deployment|production|staging)[_ -]?(?:target|url|ref|value|status)?\s*=", re.IGNORECASE),
    ),
)
FORBIDDEN_PROMOTION_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("access_policy_approved", re.compile(r"\baccess\s+policy\s+(?:is\s+)?approved\b", re.IGNORECASE)),
    ("customer_access_open", re.compile(r"\bcustomer\s+access\s+(?:is\s+)?open\b", re.IGNORECASE)),
    ("customers_invited", re.compile(r"\bcustomers?\s+(?:are\s+)?invited\b", re.IGNORECASE)),
    ("accounts_created", re.compile(r"\baccounts?\s+(?:are\s+)?created\b", re.IGNORECASE)),
    ("tenant_ready", re.compile(r"\btenant\s+(?:is\s+)?ready\b", re.IGNORECASE)),
    ("login_ready", re.compile(r"\blogin\s+(?:is\s+)?ready\b", re.IGNORECASE)),
    ("support_committed", re.compile(r"\bsupport\s+(?:is\s+)?committed\b", re.IGNORECASE)),
    ("terms_ready", re.compile(r"\bterms\s+(?:are\s+)?ready\b", re.IGNORECASE)),
    ("privacy_ready", re.compile(r"\bprivacy\s+(?:is\s+)?ready\b", re.IGNORECASE)),
    ("collecting_personal_data", re.compile(r"\bcollecting\s+personal\s+data\b", re.IGNORECASE)),
    ("paid_access_open", re.compile(r"\bpaid\s+access\s+(?:is\s+)?open\b", re.IGNORECASE)),
    ("pilot_beta_waitlist_open", re.compile(r"\b(?:pilot|beta|waitlist)\s+access\s+(?:is\s+)?open\b", re.IGNORECASE)),
    ("external_publication_ready", re.compile(r"\bexternal\s+publication\s+(?:is\s+)?ready\b", re.IGNORECASE)),
    ("deployment_ready", re.compile(r"\bdeployment\s+(?:is\s+)?ready\b", re.IGNORECASE)),
)


@dataclass(frozen=True, slots=True)
class CustomerAccessPolicyRehearsalFinding:
    """One deterministic customer-access policy rehearsal validation finding."""

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


def validate_doc_text(text: str) -> list[CustomerAccessPolicyRehearsalFinding]:
    """Return findings for missing customer-access policy documentation anchors."""

    findings: list[CustomerAccessPolicyRehearsalFinding] = []
    for phrase in REQUIRED_DOC_PHRASES:
        if phrase not in text:
            findings.append(
                CustomerAccessPolicyRehearsalFinding(
                    "foundation_customer_access_policy_rehearsal_doc_phrase_missing",
                    f"customer-access policy rehearsal boundary doc missing required phrase: {phrase}",
                )
            )
    return findings


def validate_packet(payload: dict[str, Any]) -> list[CustomerAccessPolicyRehearsalFinding]:
    """Return findings for customer-access policy rehearsal witness drift."""

    findings: list[CustomerAccessPolicyRehearsalFinding] = []
    findings.extend(validate_root_contract(payload))
    findings.extend(validate_surfaces(payload.get("surfaces")))
    findings.extend(validate_forbidden_value_patterns(payload))
    findings.extend(validate_forbidden_promotion_patterns(payload))
    return findings


def validate_root_contract(payload: dict[str, Any]) -> list[CustomerAccessPolicyRehearsalFinding]:
    """Return findings for root-level customer-access policy witness drift."""

    findings: list[CustomerAccessPolicyRehearsalFinding] = []
    if set(payload) != EXPECTED_ROOT_KEYS:
        findings.append(
            CustomerAccessPolicyRehearsalFinding(
                "customer_access_policy_rehearsal_root_keys_invalid",
                f"root keys must be: {', '.join(sorted(EXPECTED_ROOT_KEYS))}",
            )
        )
    expected_values = {
        "witness_id": EXPECTED_WITNESS_ID,
        "schema_version": 1,
        "status": "AwaitingEvidence",
        "solver_outcome": "AwaitingEvidence",
        "access_policy_rehearsal_executed": False,
        "access_policy_approved": False,
        "customer_access_allowed": False,
        "customer_invitation_allowed": False,
        "account_creation_allowed": False,
        "tenant_provisioning_allowed": False,
        "login_route_publication_allowed": False,
        "support_commitment_allowed": False,
        "terms_privacy_ready_claimed": False,
        "personal_data_collection_allowed": False,
        "paid_access_allowed": False,
        "pilot_beta_waitlist_access_allowed": False,
        "external_publication_allowed": False,
        "deployment_allowed": False,
    }
    for key, expected_value in expected_values.items():
        if payload.get(key) != expected_value:
            findings.append(
                CustomerAccessPolicyRehearsalFinding(
                    "customer_access_policy_rehearsal_root_value_invalid",
                    f"{key} must be {expected_value!r}",
                )
            )
    if tuple(payload.get("blocked_claims") or ()) != EXPECTED_BLOCKED_CLAIMS:
        findings.append(
            CustomerAccessPolicyRehearsalFinding(
                "customer_access_policy_rehearsal_blocked_claims_invalid",
                f"blocked_claims must be: {', '.join(EXPECTED_BLOCKED_CLAIMS)}",
            )
        )
    next_action = payload.get("next_action")
    if not isinstance(next_action, str) or "draft fictional local customer-access policy rules only" not in next_action:
        findings.append(
            CustomerAccessPolicyRehearsalFinding(
                "customer_access_policy_rehearsal_next_action_invalid",
                "next_action must preserve fictional local customer-access policy planning only",
            )
        )
    return findings


def validate_surfaces(surfaces: object) -> list[CustomerAccessPolicyRehearsalFinding]:
    """Return findings for customer-access policy rehearsal surface drift."""

    findings: list[CustomerAccessPolicyRehearsalFinding] = []
    if not isinstance(surfaces, list) or not all(isinstance(surface, dict) for surface in surfaces):
        return [CustomerAccessPolicyRehearsalFinding("customer_access_policy_rehearsal_surfaces_invalid", "surfaces must be a list")]
    observed_surfaces = tuple(
        (surface.get("surface_id"), surface.get("surface_type"), surface.get("state"))
        for surface in surfaces
    )
    if observed_surfaces != EXPECTED_SURFACES:
        findings.append(
            CustomerAccessPolicyRehearsalFinding(
                "customer_access_policy_rehearsal_surface_inventory_invalid",
                "customer-access policy rehearsal surface inventory does not match the expected set",
            )
        )
    surface_ids = [surface.get("surface_id") for surface in surfaces]
    if len(set(surface_ids)) != len(surface_ids):
        findings.append(CustomerAccessPolicyRehearsalFinding("customer_access_policy_rehearsal_surface_duplicate", "surface ids must be unique"))
    for surface in surfaces:
        surface_id = str(surface.get("surface_id", "<missing>"))
        if set(surface) != EXPECTED_SURFACE_KEYS:
            findings.append(
                CustomerAccessPolicyRehearsalFinding(
                    "customer_access_policy_rehearsal_surface_keys_invalid",
                    f"{surface_id} surface keys must be: {', '.join(sorted(EXPECTED_SURFACE_KEYS))}",
                )
            )
        if surface.get("state") != "AwaitingEvidence":
            findings.append(
                CustomerAccessPolicyRehearsalFinding(
                    "customer_access_policy_rehearsal_surface_state_invalid",
                    f"{surface_id} state must be AwaitingEvidence",
                )
            )
        if surface.get("evidence_ref") != "manual_preparation_pending":
            findings.append(
                CustomerAccessPolicyRehearsalFinding(
                    "customer_access_policy_rehearsal_surface_evidence_invalid",
                    f"{surface_id} evidence_ref must stay manual_preparation_pending",
                )
            )
        if not isinstance(surface.get("public_safe_note"), str) or not surface["public_safe_note"].strip():
            findings.append(
                CustomerAccessPolicyRehearsalFinding(
                    "customer_access_policy_rehearsal_surface_note_invalid",
                    f"{surface_id} public_safe_note must be a non-empty string",
                )
            )
    return findings


def validate_forbidden_value_patterns(payload: dict[str, Any]) -> list[CustomerAccessPolicyRehearsalFinding]:
    """Return findings for account, tenant, invite, customer, support, payment, publication, or deployment-shaped values."""

    serialized_payload = json.dumps(payload, sort_keys=True)
    findings: list[CustomerAccessPolicyRehearsalFinding] = []
    for rule_id, pattern in FORBIDDEN_VALUE_PATTERNS:
        if pattern.search(serialized_payload):
            findings.append(
                CustomerAccessPolicyRehearsalFinding(
                    "customer_access_policy_rehearsal_forbidden_value_pattern",
                    f"customer-access policy rehearsal witness contains forbidden value pattern: {rule_id}",
                )
            )
    return findings


def validate_forbidden_promotion_patterns(payload: dict[str, Any]) -> list[CustomerAccessPolicyRehearsalFinding]:
    """Return findings if the witness drifts into customer-access readiness claims."""

    serialized_payload = json.dumps(payload, sort_keys=True)
    findings: list[CustomerAccessPolicyRehearsalFinding] = []
    for rule_id, pattern in FORBIDDEN_PROMOTION_PATTERNS:
        if pattern.search(serialized_payload):
            findings.append(
                CustomerAccessPolicyRehearsalFinding(
                    "customer_access_policy_rehearsal_forbidden_promotion_phrase",
                    f"customer-access policy rehearsal witness contains forbidden promotion pattern: {rule_id}",
                )
            )
    return findings


def validate_foundation_customer_access_policy_rehearsal_boundary(
    doc_path: Path = DEFAULT_DOC_PATH,
    packet_path: Path = DEFAULT_PACKET_PATH,
) -> list[CustomerAccessPolicyRehearsalFinding]:
    """Validate the Foundation Mode customer-access policy rehearsal boundary artifacts."""

    doc_text = load_text(doc_path, "customer-access policy rehearsal boundary doc")
    packet_payload = load_json_object(packet_path, "customer-access policy rehearsal witness packet")
    return [
        *validate_doc_text(doc_text),
        *validate_packet(packet_payload),
    ]


def main(argv: list[str] | None = None) -> int:
    """Validate customer-access policy rehearsal artifacts and print deterministic status."""

    parser = argparse.ArgumentParser(description="Validate Foundation Mode customer-access policy rehearsal boundary artifacts.")
    parser.add_argument("--doc", type=Path, default=DEFAULT_DOC_PATH)
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET_PATH)
    args = parser.parse_args(argv)

    try:
        findings = validate_foundation_customer_access_policy_rehearsal_boundary(args.doc, args.packet)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"[FAIL] foundation_customer_access_policy_rehearsal_load: {exc}", file=sys.stderr)
        print("STATUS: failed", file=sys.stderr)
        return 1

    if findings:
        for finding in findings:
            print(f"[FAIL] {finding.rule_id}: {finding.message}", file=sys.stderr)
        print("STATUS: failed", file=sys.stderr)
        return 1
    print("[PASS] foundation_customer_access_policy_rehearsal_doc")
    print("[PASS] foundation_customer_access_policy_rehearsal_witness")
    print("STATUS: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
