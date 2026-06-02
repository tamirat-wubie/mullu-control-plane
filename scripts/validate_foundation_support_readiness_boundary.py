#!/usr/bin/env python3
"""Validate the Foundation Mode support-readiness boundary.

Purpose: keep support preparation local and public-safe while customer support,
support SLA, incident-response readiness, onboarding, paid support, and
deployment claims remain blocked.
Governance scope: Foundation Mode, support posture, incident-preparation
posture, public-label witness, private-value exclusion, and deployment blocking.
Dependencies: docs/FOUNDATION_SUPPORT_READINESS_BOUNDARY.md and
examples/foundation_support_readiness_witness.awaiting_evidence.json.
Invariants:
  - Validation is read-only.
  - The witness records support preparation only.
  - No customer support opening, SLA, incident readiness, mailbox deliverability,
    onboarding, paid support, customer access, private value, or deployment
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
DEFAULT_DOC_PATH = REPO_ROOT / "docs" / "FOUNDATION_SUPPORT_READINESS_BOUNDARY.md"
DEFAULT_PACKET_PATH = REPO_ROOT / "examples" / "foundation_support_readiness_witness.awaiting_evidence.json"

EXPECTED_WITNESS_ID = "foundation_support_readiness_witness.awaiting_evidence.v1"
EXPECTED_BLOCKED_CLAIMS = (
    "customer support opening",
    "support SLA",
    "incident response readiness",
    "support mailbox deliverability",
    "customer onboarding",
    "paid support",
    "deployment readiness",
)
EXPECTED_SURFACES = (
    ("support_mailbox_label", "mailbox_label", "AwaitingEvidence"),
    ("general_contact_label", "mailbox_label", "AwaitingEvidence"),
    ("support_triage_categories", "local_draft", "AwaitingEvidence"),
    ("incident_runbook_outline", "local_draft", "AwaitingEvidence"),
    ("rollback_contact_path", "local_draft", "AwaitingEvidence"),
    ("support_closure_criteria", "local_draft", "AwaitingEvidence"),
)
EXPECTED_ROOT_KEYS = {
    "blocked_claims",
    "customer_access_allowed",
    "customer_support_open",
    "deployment_allowed",
    "incident_response_ready_claimed",
    "live_support_commitment_allowed",
    "next_action",
    "onboarding_allowed",
    "paid_support_allowed",
    "schema_version",
    "solver_outcome",
    "status",
    "support_mailbox_deliverability_claimed",
    "support_sla_claimed",
    "support_surfaces",
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
    "Foundation Support Readiness Boundary",
    "Witness packet: [`../examples/foundation_support_readiness_witness.awaiting_evidence.json`]",
    "Rule: Support preparation is a local planning boundary, not a customer-support service.",
    "No customer support opening, support SLA, incident-response readiness, support",
    "support_readiness_boundary_state=AwaitingEvidence",
    "customer_support_open=false",
    "support_sla_claimed=false",
    "incident_response_ready_claimed=false",
    "support_mailbox_deliverability_claimed=false",
    "python scripts/validate_foundation_support_readiness_boundary.py",
)
FORBIDDEN_VALUE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("url_value", re.compile(r"https?://", re.IGNORECASE)),
    ("private_path", re.compile(r"\b[A-Za-z]:[\\/]|\\\\", re.IGNORECASE)),
    ("routing_assignment", re.compile(r"\b(?:inbox|mailbox|routing|delegate|forwarding)[_ -]?target\s*=", re.IGNORECASE)),
    ("provider_account_assignment", re.compile(r"\bprovider[_ -]?account[_ -]?id\s*=", re.IGNORECASE)),
    ("secret_assignment", re.compile(r"\b(?:password|secret|token|api[_ -]?key)\s*=", re.IGNORECASE)),
    ("private_key_material", re.compile(r"BEGIN [A-Z ]*PRIVATE KEY")),
)
FORBIDDEN_PROMOTION_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("support_ready", re.compile(r"\bsupport[- ]ready\b", re.IGNORECASE)),
    ("support_open", re.compile(r"\bsupport\s+(?:is\s+)?open\b", re.IGNORECASE)),
    ("incident_ready", re.compile(r"\bincident[- ]response[- ]ready\b", re.IGNORECASE)),
    ("mailbox_verified", re.compile(r"\bmailbox\s+(?:verified|ready|deliverability\s+confirmed)\b", re.IGNORECASE)),
    ("customer_onboarding_open", re.compile(r"\bcustomer\s+onboarding\s+open\b", re.IGNORECASE)),
    ("response_guarantee", re.compile(r"\b(?:guaranteed\s+response|response\s+guarantee|24/7)\b", re.IGNORECASE)),
    ("sla_guarantee", re.compile(r"\bsla\s+(?:guaranteed|ready|active|available)\b", re.IGNORECASE)),
)


@dataclass(frozen=True, slots=True)
class SupportReadinessFinding:
    """One deterministic support-readiness boundary validation finding."""

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


def validate_doc_text(text: str) -> list[SupportReadinessFinding]:
    """Return findings for missing support-readiness documentation anchors."""

    findings: list[SupportReadinessFinding] = []
    for phrase in REQUIRED_DOC_PHRASES:
        if phrase not in text:
            findings.append(
                SupportReadinessFinding(
                    "foundation_support_readiness_doc_phrase_missing",
                    f"support-readiness boundary doc missing required phrase: {phrase}",
                )
            )
    return findings


def validate_packet(payload: dict[str, Any]) -> list[SupportReadinessFinding]:
    """Return findings for support-readiness witness drift."""

    findings: list[SupportReadinessFinding] = []
    findings.extend(validate_root_contract(payload))
    findings.extend(validate_support_surfaces(payload.get("support_surfaces")))
    findings.extend(validate_forbidden_value_patterns(payload))
    findings.extend(validate_forbidden_promotion_patterns(payload))
    return findings


def validate_root_contract(payload: dict[str, Any]) -> list[SupportReadinessFinding]:
    """Return findings for root-level support-readiness witness drift."""

    findings: list[SupportReadinessFinding] = []
    if set(payload) != EXPECTED_ROOT_KEYS:
        findings.append(
            SupportReadinessFinding(
                "support_readiness_root_keys_invalid",
                f"root keys must be: {', '.join(sorted(EXPECTED_ROOT_KEYS))}",
            )
        )
    expected_values = {
        "witness_id": EXPECTED_WITNESS_ID,
        "schema_version": 1,
        "status": "AwaitingEvidence",
        "solver_outcome": "AwaitingEvidence",
        "customer_support_open": False,
        "support_sla_claimed": False,
        "incident_response_ready_claimed": False,
        "support_mailbox_deliverability_claimed": False,
        "onboarding_allowed": False,
        "live_support_commitment_allowed": False,
        "paid_support_allowed": False,
        "customer_access_allowed": False,
        "deployment_allowed": False,
    }
    for key, expected_value in expected_values.items():
        if payload.get(key) != expected_value:
            findings.append(
                SupportReadinessFinding(
                    "support_readiness_root_value_invalid",
                    f"{key} must be {expected_value!r}",
                )
            )
    if tuple(payload.get("blocked_claims") or ()) != EXPECTED_BLOCKED_CLAIMS:
        findings.append(
            SupportReadinessFinding(
                "support_readiness_blocked_claims_invalid",
                f"blocked_claims must be: {', '.join(EXPECTED_BLOCKED_CLAIMS)}",
            )
        )
    next_action = payload.get("next_action")
    if not isinstance(next_action, str) or "do not open support" not in next_action:
        findings.append(
            SupportReadinessFinding(
                "support_readiness_next_action_invalid",
                "next_action must preserve the closed-support boundary",
            )
        )
    return findings


def validate_support_surfaces(support_surfaces: object) -> list[SupportReadinessFinding]:
    """Return findings for support-surface witness drift."""

    findings: list[SupportReadinessFinding] = []
    if not isinstance(support_surfaces, list) or not all(isinstance(surface, dict) for surface in support_surfaces):
        return [SupportReadinessFinding("support_readiness_surfaces_invalid", "support_surfaces must be a list of objects")]
    observed_surfaces = tuple(
        (surface.get("surface_id"), surface.get("surface_type"), surface.get("state"))
        for surface in support_surfaces
    )
    if observed_surfaces != EXPECTED_SURFACES:
        findings.append(
            SupportReadinessFinding(
                "support_readiness_surface_inventory_invalid",
                "support surface inventory does not match the Foundation Mode support set",
            )
        )
    surface_ids = [surface.get("surface_id") for surface in support_surfaces]
    if len(set(surface_ids)) != len(surface_ids):
        findings.append(SupportReadinessFinding("support_readiness_surface_duplicate", "surface ids must be unique"))
    for surface in support_surfaces:
        surface_id = str(surface.get("surface_id", "<missing>"))
        if set(surface) != EXPECTED_SURFACE_KEYS:
            findings.append(
                SupportReadinessFinding(
                    "support_readiness_surface_keys_invalid",
                    f"{surface_id} surface keys must be: {', '.join(sorted(EXPECTED_SURFACE_KEYS))}",
                )
            )
        if surface.get("state") != "AwaitingEvidence":
            findings.append(
                SupportReadinessFinding(
                    "support_readiness_surface_state_invalid",
                    f"{surface_id} state must be AwaitingEvidence",
                )
            )
        if surface.get("evidence_ref") != "manual_preparation_pending":
            findings.append(
                SupportReadinessFinding(
                    "support_readiness_surface_evidence_invalid",
                    f"{surface_id} evidence_ref must stay manual_preparation_pending in the committed packet",
                )
            )
        if not isinstance(surface.get("public_safe_note"), str) or not surface["public_safe_note"].strip():
            findings.append(
                SupportReadinessFinding(
                    "support_readiness_surface_note_invalid",
                    f"{surface_id} public_safe_note must be a non-empty string",
                )
            )
    return findings


def validate_forbidden_value_patterns(payload: dict[str, Any]) -> list[SupportReadinessFinding]:
    """Return findings for private inbox, account, secret, or routing-shaped values."""

    serialized_payload = json.dumps(payload, sort_keys=True)
    findings: list[SupportReadinessFinding] = []
    for rule_id, pattern in FORBIDDEN_VALUE_PATTERNS:
        if pattern.search(serialized_payload):
            findings.append(
                SupportReadinessFinding(
                    "support_readiness_forbidden_private_value_pattern",
                    f"support-readiness witness contains forbidden value pattern: {rule_id}",
                )
            )
    return findings


def validate_forbidden_promotion_patterns(payload: dict[str, Any]) -> list[SupportReadinessFinding]:
    """Return findings if the witness drifts into support-readiness claims."""

    serialized_payload = json.dumps(payload, sort_keys=True)
    findings: list[SupportReadinessFinding] = []
    for rule_id, pattern in FORBIDDEN_PROMOTION_PATTERNS:
        if pattern.search(serialized_payload):
            findings.append(
                SupportReadinessFinding(
                    "support_readiness_forbidden_promotion_phrase",
                    f"support-readiness witness contains forbidden promotion pattern: {rule_id}",
                )
            )
    return findings


def validate_foundation_support_readiness_boundary(
    doc_path: Path = DEFAULT_DOC_PATH,
    packet_path: Path = DEFAULT_PACKET_PATH,
) -> list[SupportReadinessFinding]:
    """Validate the Foundation Mode support-readiness boundary artifacts."""

    doc_text = load_text(doc_path, "support-readiness boundary doc")
    packet_payload = load_json_object(packet_path, "support-readiness witness packet")
    return [
        *validate_doc_text(doc_text),
        *validate_packet(packet_payload),
    ]


def main(argv: list[str] | None = None) -> int:
    """Validate support-readiness boundary artifacts and print deterministic status."""

    parser = argparse.ArgumentParser(description="Validate Foundation Mode support-readiness boundary artifacts.")
    parser.add_argument("--doc", type=Path, default=DEFAULT_DOC_PATH)
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET_PATH)
    args = parser.parse_args(argv)

    try:
        findings = validate_foundation_support_readiness_boundary(args.doc, args.packet)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"[FAIL] foundation_support_readiness_load: {exc}", file=sys.stderr)
        print("STATUS: failed", file=sys.stderr)
        return 1

    if findings:
        for finding in findings:
            print(f"[FAIL] {finding.rule_id}: {finding.message}", file=sys.stderr)
        print("STATUS: failed", file=sys.stderr)
        return 1
    print("[PASS] foundation_support_readiness_doc")
    print("[PASS] foundation_support_readiness_witness")
    print("STATUS: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
