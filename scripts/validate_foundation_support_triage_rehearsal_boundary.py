#!/usr/bin/env python3
"""Validate the Foundation Mode support triage rehearsal boundary.

Purpose: keep support triage rehearsal local and public-safe while customer
support, inbound messages, tickets, inbox routing, customer data, personal data,
response commitments, support tooling, paid support, and deployment remain
blocked.
Governance scope: Foundation Mode, support triage rehearsal planning, local
sample categorization, public-safe issue-shape notes, inbox/routing exclusion,
customer-data exclusion, response-commitment blocking, support-tool blocking,
onboarding blocking, paid-support blocking, and deployment blocking.
Dependencies: docs/FOUNDATION_SUPPORT_TRIAGE_REHEARSAL_BOUNDARY.md and
examples/foundation_support_triage_rehearsal_witness.awaiting_evidence.json.
Invariants:
  - Validation is read-only.
  - The witness records support triage rehearsal planning only.
  - No support opening, inbound message, ticket, routing, customer-data,
    personal-data, response-time, SLA, incident-readiness, support-tool,
    onboarding, paid-support, or deployment claim is allowed.
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
DEFAULT_DOC_PATH = REPO_ROOT / "docs" / "FOUNDATION_SUPPORT_TRIAGE_REHEARSAL_BOUNDARY.md"
DEFAULT_PACKET_PATH = REPO_ROOT / "examples" / "foundation_support_triage_rehearsal_witness.awaiting_evidence.json"

EXPECTED_WITNESS_ID = "foundation_support_triage_rehearsal_witness.awaiting_evidence.v1"
EXPECTED_BLOCKED_CLAIMS = (
    "support triage execution",
    "customer support opening",
    "inbound message acceptance",
    "support ticket creation",
    "inbox routing",
    "customer-data handling",
    "personal-data handling",
    "response-time promise",
    "support SLA",
    "incident response readiness",
    "support-tool activation",
    "onboarding",
    "paid support",
    "deployment readiness",
)
EXPECTED_SURFACES = (
    ("fictional_request_categories", "local_draft", "AwaitingEvidence"),
    ("severity_labels", "local_draft", "AwaitingEvidence"),
    ("triage_decision_rules", "local_draft", "AwaitingEvidence"),
    ("privacy_stop_rule", "local_draft", "AwaitingEvidence"),
    ("billing_stop_rule", "local_draft", "AwaitingEvidence"),
    ("legal_stop_rule", "local_draft", "AwaitingEvidence"),
    ("tooling_stop_rule", "local_draft", "AwaitingEvidence"),
    ("handoff_note", "local_draft", "AwaitingEvidence"),
)
EXPECTED_ROOT_KEYS = {
    "blocked_claims",
    "customer_data_handling_allowed",
    "customer_support_open",
    "deployment_allowed",
    "inbound_message_acceptance_allowed",
    "inbox_routing_allowed",
    "incident_response_ready_claimed",
    "next_action",
    "onboarding_allowed",
    "paid_support_allowed",
    "personal_data_handling_allowed",
    "response_time_promise_claimed",
    "schema_version",
    "solver_outcome",
    "status",
    "support_sla_claimed",
    "support_ticket_creation_allowed",
    "support_tool_activation_allowed",
    "support_triage_executed",
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
    "Foundation Support Triage Rehearsal Boundary",
    "Witness packet: [`../examples/foundation_support_triage_rehearsal_witness.awaiting_evidence.json`]",
    "Rule: Support triage rehearsal is a local paper exercise, not a customer-support",
    "No support triage execution, customer support opening, inbound message",
    "support_triage_rehearsal_boundary_state=AwaitingEvidence",
    "support_triage_executed=false",
    "customer_support_open=false",
    "inbound_message_acceptance_allowed=false",
    "support_ticket_creation_allowed=false",
    "customer_data_handling_allowed=false",
    "response_time_promise_claimed=false",
    "deployment_allowed=false",
    "python scripts/validate_foundation_support_triage_rehearsal_boundary.py",
)
FORBIDDEN_VALUE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("url_value", re.compile(r"https?://", re.IGNORECASE)),
    ("email_value", re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)),
    ("private_path", re.compile(r"\b[A-Za-z]:[\\/]|\\\\", re.IGNORECASE)),
    (
        "inbox_routing_assignment",
        re.compile(r"\b(?:inbox|mailbox|routing|delegate|forwarding)[_ -]?(?:target|id|ref|value)?\s*=", re.IGNORECASE),
    ),
    (
        "ticket_assignment",
        re.compile(r"\b(?:ticket|case|incident)[_ -]?(?:id|ref|target|value|status)?\s*=", re.IGNORECASE),
    ),
    (
        "customer_personal_assignment",
        re.compile(r"\b(?:customer|personal|person|participant|user)[_ -]?(?:data|id|name|email|ref|value|target)?\s*=", re.IGNORECASE),
    ),
    (
        "response_window_assignment",
        re.compile(r"\b(?:response|sla|service[_ -]?level)[_ -]?(?:time|window|target|value|status)?\s*=", re.IGNORECASE),
    ),
    (
        "billing_assignment",
        re.compile(r"\b(?:billing|payment|refund|invoice|charge)[_ -]?(?:id|ref|target|value|status)?\s*=", re.IGNORECASE),
    ),
    (
        "legal_assignment",
        re.compile(r"\b(?:legal|terms|policy|contract)[_ -]?(?:id|ref|target|value|status)?\s*=", re.IGNORECASE),
    ),
    (
        "support_tool_assignment",
        re.compile(r"\b(?:helpdesk|support[_ -]?tool|crm|service[_ -]?account)[_ -]?(?:id|ref|target|value|status)?\s*=", re.IGNORECASE),
    ),
    (
        "onboarding_assignment",
        re.compile(r"\b(?:onboarding|invite|account)[_ -]?(?:id|ref|target|value|status)?\s*=", re.IGNORECASE),
    ),
    (
        "deployment_assignment",
        re.compile(r"\b(?:deploy|deployment|production|staging)[_ -]?(?:target|url|ref|value|status)?\s*=", re.IGNORECASE),
    ),
)
FORBIDDEN_PROMOTION_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("support_triage_ready", re.compile(r"\bsupport\s+triage\s+(?:is\s+)?ready\b", re.IGNORECASE)),
    ("support_ready", re.compile(r"\bsupport[- ]ready\b", re.IGNORECASE)),
    ("support_open", re.compile(r"\bsupport\s+(?:is\s+)?open\b", re.IGNORECASE)),
    ("ticketing_ready", re.compile(r"\bticketing\s+(?:is\s+)?ready\b", re.IGNORECASE)),
    ("mailbox_ready", re.compile(r"\bmailbox\s+(?:is\s+)?ready\b", re.IGNORECASE)),
    ("incident_ready", re.compile(r"\bincident[- ]response[- ]ready\b", re.IGNORECASE)),
    ("sla_ready", re.compile(r"\bsla\s+(?:is\s+)?ready\b", re.IGNORECASE)),
    ("response_guaranteed", re.compile(r"\bresponse\s+(?:is\s+)?guaranteed\b", re.IGNORECASE)),
    ("onboarding_open", re.compile(r"\bonboarding\s+(?:is\s+)?open\b", re.IGNORECASE)),
    ("paid_support_ready", re.compile(r"\bpaid\s+support\s+(?:is\s+)?ready\b", re.IGNORECASE)),
    ("customer_access_open", re.compile(r"\bcustomer\s+access\s+(?:is\s+)?open\b", re.IGNORECASE)),
    ("deployment_ready", re.compile(r"\bdeployment\s+(?:is\s+)?ready\b", re.IGNORECASE)),
)


@dataclass(frozen=True, slots=True)
class SupportTriageRehearsalFinding:
    """One deterministic support triage rehearsal validation finding."""

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


def validate_doc_text(text: str) -> list[SupportTriageRehearsalFinding]:
    """Return findings for missing support triage rehearsal documentation anchors."""

    findings: list[SupportTriageRehearsalFinding] = []
    for phrase in REQUIRED_DOC_PHRASES:
        if phrase not in text:
            findings.append(
                SupportTriageRehearsalFinding(
                    "foundation_support_triage_rehearsal_doc_phrase_missing",
                    f"support triage rehearsal boundary doc missing required phrase: {phrase}",
                )
            )
    return findings


def validate_packet(payload: dict[str, Any]) -> list[SupportTriageRehearsalFinding]:
    """Return findings for support triage rehearsal witness drift."""

    findings: list[SupportTriageRehearsalFinding] = []
    findings.extend(validate_root_contract(payload))
    findings.extend(validate_surfaces(payload.get("surfaces")))
    findings.extend(validate_forbidden_value_patterns(payload))
    findings.extend(validate_forbidden_promotion_patterns(payload))
    return findings


def validate_root_contract(payload: dict[str, Any]) -> list[SupportTriageRehearsalFinding]:
    """Return findings for root-level support triage rehearsal witness drift."""

    findings: list[SupportTriageRehearsalFinding] = []
    if set(payload) != EXPECTED_ROOT_KEYS:
        findings.append(
            SupportTriageRehearsalFinding(
                "support_triage_rehearsal_root_keys_invalid",
                f"root keys must be: {', '.join(sorted(EXPECTED_ROOT_KEYS))}",
            )
        )
    expected_values = {
        "witness_id": EXPECTED_WITNESS_ID,
        "schema_version": 1,
        "status": "AwaitingEvidence",
        "solver_outcome": "AwaitingEvidence",
        "support_triage_executed": False,
        "customer_support_open": False,
        "inbound_message_acceptance_allowed": False,
        "support_ticket_creation_allowed": False,
        "inbox_routing_allowed": False,
        "customer_data_handling_allowed": False,
        "personal_data_handling_allowed": False,
        "response_time_promise_claimed": False,
        "support_sla_claimed": False,
        "incident_response_ready_claimed": False,
        "support_tool_activation_allowed": False,
        "onboarding_allowed": False,
        "paid_support_allowed": False,
        "deployment_allowed": False,
    }
    for key, expected_value in expected_values.items():
        if payload.get(key) != expected_value:
            findings.append(
                SupportTriageRehearsalFinding(
                    "support_triage_rehearsal_root_value_invalid",
                    f"{key} must be {expected_value!r}",
                )
            )
    if tuple(payload.get("blocked_claims") or ()) != EXPECTED_BLOCKED_CLAIMS:
        findings.append(
            SupportTriageRehearsalFinding(
                "support_triage_rehearsal_blocked_claims_invalid",
                f"blocked_claims must be: {', '.join(EXPECTED_BLOCKED_CLAIMS)}",
            )
        )
    next_action = payload.get("next_action")
    if not isinstance(next_action, str) or "draft fictional local support triage categories only" not in next_action:
        findings.append(
            SupportTriageRehearsalFinding(
                "support_triage_rehearsal_next_action_invalid",
                "next_action must preserve fictional local support triage planning only",
            )
        )
    return findings


def validate_surfaces(surfaces: object) -> list[SupportTriageRehearsalFinding]:
    """Return findings for support triage rehearsal surface drift."""

    findings: list[SupportTriageRehearsalFinding] = []
    if not isinstance(surfaces, list) or not all(isinstance(surface, dict) for surface in surfaces):
        return [SupportTriageRehearsalFinding("support_triage_rehearsal_surfaces_invalid", "surfaces must be a list")]
    observed_surfaces = tuple(
        (surface.get("surface_id"), surface.get("surface_type"), surface.get("state"))
        for surface in surfaces
    )
    if observed_surfaces != EXPECTED_SURFACES:
        findings.append(
            SupportTriageRehearsalFinding(
                "support_triage_rehearsal_surface_inventory_invalid",
                "support triage rehearsal surface inventory does not match the expected set",
            )
        )
    surface_ids = [surface.get("surface_id") for surface in surfaces]
    if len(set(surface_ids)) != len(surface_ids):
        findings.append(SupportTriageRehearsalFinding("support_triage_rehearsal_surface_duplicate", "surface ids must be unique"))
    for surface in surfaces:
        surface_id = str(surface.get("surface_id", "<missing>"))
        if set(surface) != EXPECTED_SURFACE_KEYS:
            findings.append(
                SupportTriageRehearsalFinding(
                    "support_triage_rehearsal_surface_keys_invalid",
                    f"{surface_id} surface keys must be: {', '.join(sorted(EXPECTED_SURFACE_KEYS))}",
                )
            )
        if surface.get("state") != "AwaitingEvidence":
            findings.append(
                SupportTriageRehearsalFinding(
                    "support_triage_rehearsal_surface_state_invalid",
                    f"{surface_id} state must be AwaitingEvidence",
                )
            )
        if surface.get("evidence_ref") != "manual_preparation_pending":
            findings.append(
                SupportTriageRehearsalFinding(
                    "support_triage_rehearsal_surface_evidence_invalid",
                    f"{surface_id} evidence_ref must stay manual_preparation_pending",
                )
            )
        if not isinstance(surface.get("public_safe_note"), str) or not surface["public_safe_note"].strip():
            findings.append(
                SupportTriageRehearsalFinding(
                    "support_triage_rehearsal_surface_note_invalid",
                    f"{surface_id} public_safe_note must be a non-empty string",
                )
            )
    return findings


def validate_forbidden_value_patterns(payload: dict[str, Any]) -> list[SupportTriageRehearsalFinding]:
    """Return findings for inbox, ticket, customer, response, support tool, or deployment-shaped values."""

    serialized_payload = json.dumps(payload, sort_keys=True)
    findings: list[SupportTriageRehearsalFinding] = []
    for rule_id, pattern in FORBIDDEN_VALUE_PATTERNS:
        if pattern.search(serialized_payload):
            findings.append(
                SupportTriageRehearsalFinding(
                    "support_triage_rehearsal_forbidden_value_pattern",
                    f"support triage rehearsal witness contains forbidden value pattern: {rule_id}",
                )
            )
    return findings


def validate_forbidden_promotion_patterns(payload: dict[str, Any]) -> list[SupportTriageRehearsalFinding]:
    """Return findings if the witness drifts into support readiness claims."""

    serialized_payload = json.dumps(payload, sort_keys=True)
    findings: list[SupportTriageRehearsalFinding] = []
    for rule_id, pattern in FORBIDDEN_PROMOTION_PATTERNS:
        if pattern.search(serialized_payload):
            findings.append(
                SupportTriageRehearsalFinding(
                    "support_triage_rehearsal_forbidden_promotion_phrase",
                    f"support triage rehearsal witness contains forbidden promotion pattern: {rule_id}",
                )
            )
    return findings


def validate_foundation_support_triage_rehearsal_boundary(
    doc_path: Path = DEFAULT_DOC_PATH,
    packet_path: Path = DEFAULT_PACKET_PATH,
) -> list[SupportTriageRehearsalFinding]:
    """Validate the Foundation Mode support triage rehearsal boundary artifacts."""

    doc_text = load_text(doc_path, "support triage rehearsal boundary doc")
    packet_payload = load_json_object(packet_path, "support triage rehearsal witness packet")
    return [
        *validate_doc_text(doc_text),
        *validate_packet(packet_payload),
    ]


def main(argv: list[str] | None = None) -> int:
    """Validate support triage rehearsal boundary artifacts and print deterministic status."""

    parser = argparse.ArgumentParser(description="Validate Foundation Mode support triage rehearsal boundary artifacts.")
    parser.add_argument("--doc", type=Path, default=DEFAULT_DOC_PATH)
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET_PATH)
    args = parser.parse_args(argv)

    try:
        findings = validate_foundation_support_triage_rehearsal_boundary(args.doc, args.packet)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"[FAIL] foundation_support_triage_rehearsal_load: {exc}", file=sys.stderr)
        print("STATUS: failed", file=sys.stderr)
        return 1

    if findings:
        for finding in findings:
            print(f"[FAIL] {finding.rule_id}: {finding.message}", file=sys.stderr)
        print("STATUS: failed", file=sys.stderr)
        return 1
    print("[PASS] foundation_support_triage_rehearsal_doc")
    print("[PASS] foundation_support_triage_rehearsal_witness")
    print("STATUS: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
