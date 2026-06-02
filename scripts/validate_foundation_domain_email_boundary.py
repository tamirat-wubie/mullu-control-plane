#!/usr/bin/env python3
"""Validate the Foundation Mode domain/email public-safe boundary.

Purpose: keep domain and email preparation limited to public labels while DNS
mutation, endpoint readiness, email deliverability, provider-private values, and
deployment remain blocked.
Governance scope: Foundation Mode, domain/email posture, public-label witness,
provider-private exclusion, DNS mutation blocking, and deployment blocking.
Dependencies: docs/FOUNDATION_DOMAIN_EMAIL_BOUNDARY.md and
examples/foundation_domain_email_witness.awaiting_evidence.json.
Invariants:
  - Validation is read-only.
  - The witness records public labels only.
  - No DNS mutation, endpoint readiness, email deliverability, provider account,
    private DNS target, secret, or deployment claim is allowed.
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
DEFAULT_DOC_PATH = REPO_ROOT / "docs" / "FOUNDATION_DOMAIN_EMAIL_BOUNDARY.md"
DEFAULT_PACKET_PATH = REPO_ROOT / "examples" / "foundation_domain_email_witness.awaiting_evidence.json"

EXPECTED_WITNESS_ID = "foundation_domain_email_witness.awaiting_evidence.v1"
EXPECTED_SURFACES = (
    ("apex_website_domain", "domain", "mullusi.com"),
    ("alternate_website_domain", "domain", "www.mullusi.io"),
    ("api_subdomain", "subdomain", "api.mullusi.com"),
    ("docs_subdomain", "subdomain", "docs.mullusi.com"),
    ("learn_subdomain", "subdomain", "learn.mullusi.com"),
    ("dashboard_subdomain", "subdomain", "dashboard.mullusi.com"),
    ("sandbox_subdomain", "subdomain", "sandbox.mullusi.com"),
    ("testbed_subdomain", "subdomain", "testbed.mullusi.com"),
    ("metrics_subdomain", "subdomain", "metrics.mullusi.com"),
    ("graphs_subdomain", "subdomain", "graphs.mullusi.com"),
    ("email_domain", "email_domain", "mullusi.com"),
    ("mailbox_tamirat", "mailbox", "tamirat@mullusi.com"),
    ("mailbox_research", "mailbox", "research@mullusi.com"),
    ("mailbox_hello", "mailbox", "hello@mullusi.com"),
    ("mailbox_support", "mailbox", "support@mullusi.com"),
)
EXPECTED_ROOT_KEYS = {
    "api_dns_publication_allowed",
    "deployment_allowed",
    "dns_mutation_allowed",
    "email_deliverability_claimed",
    "endpoint_readiness_claimed",
    "next_action",
    "private_dns_targets_stored_in_git",
    "provider_account_ids_stored_in_git",
    "public_surfaces",
    "schema_version",
    "secret_values_stored_in_git",
    "solver_outcome",
    "status",
    "witness_id",
}
EXPECTED_SURFACE_KEYS = {
    "evidence_ref",
    "label",
    "public_safe_note",
    "state",
    "surface_id",
    "surface_type",
}
REQUIRED_DOC_PHRASES = (
    "Foundation Domain Email Boundary",
    "Witness packet: [`../examples/foundation_domain_email_witness.awaiting_evidence.json`]",
    "Rule: Public identity labels may be recorded, but DNS/email readiness remains",
    "No provider account IDs, private DNS target values, admin-console details,",
    "domain_email_boundary_state=AwaitingEvidence",
    "dns_mutation_allowed=false",
    "api_dns_publication_allowed=false",
    "endpoint_readiness_claimed=false",
    "email_deliverability_claimed=false",
    "python scripts/validate_foundation_domain_email_boundary.py",
)
FORBIDDEN_VALUE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("url_value", re.compile(r"https?://", re.IGNORECASE)),
    ("ipv4_target", re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")),
    ("provider_account_assignment", re.compile(r"\bprovider[_ -]?account[_ -]?id\s*=", re.IGNORECASE)),
    ("dns_target_assignment", re.compile(r"\b(?:dns|origin|gateway)[_ -]?target\s*=", re.IGNORECASE)),
    ("secret_assignment", re.compile(r"\b(?:password|secret|token|api[_ -]?key)\s*=", re.IGNORECASE)),
    ("private_key_material", re.compile(r"BEGIN [A-Z ]*PRIVATE KEY")),
)


@dataclass(frozen=True, slots=True)
class DomainEmailFinding:
    """One deterministic domain/email boundary validation finding."""

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


def validate_doc_text(text: str) -> list[DomainEmailFinding]:
    """Return findings for missing domain/email documentation anchors."""

    findings: list[DomainEmailFinding] = []
    for phrase in REQUIRED_DOC_PHRASES:
        if phrase not in text:
            findings.append(
                DomainEmailFinding(
                    "foundation_domain_email_doc_phrase_missing",
                    f"domain/email boundary doc missing required phrase: {phrase}",
                )
            )
    return findings


def validate_packet(payload: dict[str, Any]) -> list[DomainEmailFinding]:
    """Return findings for domain/email witness drift."""

    findings: list[DomainEmailFinding] = []
    findings.extend(validate_root_contract(payload))
    findings.extend(validate_surfaces(payload.get("public_surfaces")))
    findings.extend(validate_forbidden_value_patterns(payload))
    return findings


def validate_root_contract(payload: dict[str, Any]) -> list[DomainEmailFinding]:
    """Return findings for root-level domain/email witness drift."""

    findings: list[DomainEmailFinding] = []
    if set(payload) != EXPECTED_ROOT_KEYS:
        findings.append(
            DomainEmailFinding(
                "domain_email_root_keys_invalid",
                f"root keys must be: {', '.join(sorted(EXPECTED_ROOT_KEYS))}",
            )
        )
    expected_values = {
        "witness_id": EXPECTED_WITNESS_ID,
        "schema_version": 1,
        "status": "AwaitingEvidence",
        "solver_outcome": "AwaitingEvidence",
        "dns_mutation_allowed": False,
        "api_dns_publication_allowed": False,
        "endpoint_readiness_claimed": False,
        "email_deliverability_claimed": False,
        "provider_account_ids_stored_in_git": False,
        "private_dns_targets_stored_in_git": False,
        "secret_values_stored_in_git": False,
        "deployment_allowed": False,
    }
    for key, expected_value in expected_values.items():
        if payload.get(key) != expected_value:
            findings.append(
                DomainEmailFinding(
                    "domain_email_root_value_invalid",
                    f"{key} must be {expected_value!r}",
                )
            )
    next_action = payload.get("next_action")
    if not isinstance(next_action, str) or "do not store provider-private values in Git" not in next_action:
        findings.append(
            DomainEmailFinding(
                "domain_email_next_action_invalid",
                "next_action must preserve the provider-private exclusion",
            )
        )
    return findings


def validate_surfaces(public_surfaces: object) -> list[DomainEmailFinding]:
    """Return findings for public surface witness drift."""

    findings: list[DomainEmailFinding] = []
    if not isinstance(public_surfaces, list) or not all(isinstance(surface, dict) for surface in public_surfaces):
        return [DomainEmailFinding("domain_email_surfaces_invalid", "public_surfaces must be a list of objects")]
    observed_surfaces = tuple(
        (surface.get("surface_id"), surface.get("surface_type"), surface.get("label"))
        for surface in public_surfaces
    )
    if observed_surfaces != EXPECTED_SURFACES:
        findings.append(
            DomainEmailFinding(
                "domain_email_surface_inventory_invalid",
                "public surface inventory does not match the Foundation Mode public-label set",
            )
        )
    surface_ids = [surface.get("surface_id") for surface in public_surfaces]
    if len(set(surface_ids)) != len(surface_ids):
        findings.append(DomainEmailFinding("domain_email_surface_duplicate", "surface ids must be unique"))
    for surface in public_surfaces:
        surface_id = str(surface.get("surface_id", "<missing>"))
        if set(surface) != EXPECTED_SURFACE_KEYS:
            findings.append(
                DomainEmailFinding(
                    "domain_email_surface_keys_invalid",
                    f"{surface_id} surface keys must be: {', '.join(sorted(EXPECTED_SURFACE_KEYS))}",
                )
            )
        if surface.get("state") != "AwaitingEvidence":
            findings.append(
                DomainEmailFinding(
                    "domain_email_surface_state_invalid",
                    f"{surface_id} state must be AwaitingEvidence",
                )
            )
        if surface.get("evidence_ref") != "manual_verification_pending":
            findings.append(
                DomainEmailFinding(
                    "domain_email_surface_evidence_invalid",
                    f"{surface_id} evidence_ref must stay manual_verification_pending in the committed packet",
                )
            )
        if not isinstance(surface.get("public_safe_note"), str) or not surface["public_safe_note"].strip():
            findings.append(
                DomainEmailFinding(
                    "domain_email_surface_note_invalid",
                    f"{surface_id} public_safe_note must be a non-empty string",
                )
            )
    return findings


def validate_forbidden_value_patterns(payload: dict[str, Any]) -> list[DomainEmailFinding]:
    """Return findings for URL, DNS target, provider id, secret, or key-shaped values."""

    serialized_payload = json.dumps(payload, sort_keys=True)
    findings: list[DomainEmailFinding] = []
    for rule_id, pattern in FORBIDDEN_VALUE_PATTERNS:
        if pattern.search(serialized_payload):
            findings.append(
                DomainEmailFinding(
                    "domain_email_forbidden_private_value_pattern",
                    f"domain/email witness contains forbidden value pattern: {rule_id}",
                )
            )
    return findings


def validate_foundation_domain_email_boundary(
    doc_path: Path = DEFAULT_DOC_PATH,
    packet_path: Path = DEFAULT_PACKET_PATH,
) -> list[DomainEmailFinding]:
    """Validate the Foundation Mode domain/email boundary artifacts."""

    doc_text = load_text(doc_path, "domain/email boundary doc")
    packet_payload = load_json_object(packet_path, "domain/email witness packet")
    return [
        *validate_doc_text(doc_text),
        *validate_packet(packet_payload),
    ]


def main(argv: list[str] | None = None) -> int:
    """Validate domain/email boundary artifacts and print deterministic status."""

    parser = argparse.ArgumentParser(description="Validate Foundation Mode domain/email boundary artifacts.")
    parser.add_argument("--doc", type=Path, default=DEFAULT_DOC_PATH)
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET_PATH)
    args = parser.parse_args(argv)

    try:
        findings = validate_foundation_domain_email_boundary(args.doc, args.packet)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"[FAIL] foundation_domain_email_load: {exc}", file=sys.stderr)
        print("STATUS: failed", file=sys.stderr)
        return 1

    if findings:
        for finding in findings:
            print(f"[FAIL] {finding.rule_id}: {finding.message}", file=sys.stderr)
        print("STATUS: failed", file=sys.stderr)
        return 1
    print("[PASS] foundation_domain_email_doc")
    print("[PASS] foundation_domain_email_witness")
    print("STATUS: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
