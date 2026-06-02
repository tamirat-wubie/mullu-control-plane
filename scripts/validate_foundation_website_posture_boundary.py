#!/usr/bin/env python3
"""Validate the Foundation Mode website-posture boundary.

Purpose: keep website-posture preparation local and public-safe while website
mutation, external publication, access invitation, waitlist, beta, pilot signup,
customer intake, production-runtime, endpoint-readiness, paid-launch, and
deployment claims remain blocked.
Governance scope: Foundation Mode, static website copy, product-route copy,
proof-route copy, access-language scans, public-naming alignment,
website-evidence receipts, private-value exclusion, and deployment blocking.
Dependencies: docs/FOUNDATION_WEBSITE_POSTURE_BOUNDARY.md and
examples/foundation_website_posture_witness.awaiting_evidence.json.
Invariants:
  - Validation is read-only.
  - The witness records website-posture preparation only.
  - No website mutation, publication, access invitation, waitlist, beta, pilot,
    customer intake, production-runtime, endpoint-readiness, paid-launch, or
    deployment claim is allowed.
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
DEFAULT_DOC_PATH = REPO_ROOT / "docs" / "FOUNDATION_WEBSITE_POSTURE_BOUNDARY.md"
DEFAULT_PACKET_PATH = REPO_ROOT / "examples" / "foundation_website_posture_witness.awaiting_evidence.json"

EXPECTED_WITNESS_ID = "foundation_website_posture_witness.awaiting_evidence.v1"
EXPECTED_BLOCKED_CLAIMS = (
    "website mutation",
    "external website publication",
    "access invitation",
    "waitlist opening",
    "beta invitation",
    "pilot signup",
    "customer intake",
    "production runtime claim",
    "endpoint readiness",
    "paid launch",
    "deployment readiness",
)
EXPECTED_SURFACES = (
    ("static_homepage_copy", "local_draft", "AwaitingEvidence"),
    ("product_route_copy", "local_draft", "AwaitingEvidence"),
    ("proof_route_copy", "local_draft", "AwaitingEvidence"),
    ("access_language_scan", "local_draft", "AwaitingEvidence"),
    ("waitlist_beta_language_scan", "local_draft", "AwaitingEvidence"),
    ("runtime_endpoint_language_scan", "local_draft", "AwaitingEvidence"),
    ("public_naming_alignment", "local_draft", "AwaitingEvidence"),
    ("website_evidence_receipts", "local_draft", "AwaitingEvidence"),
)
EXPECTED_ROOT_KEYS = {
    "access_invitation_allowed",
    "beta_invitation_allowed",
    "blocked_claims",
    "customer_intake_allowed",
    "deployment_allowed",
    "endpoint_readiness_claimed",
    "external_publication_allowed",
    "next_action",
    "paid_launch_allowed",
    "pilot_signup_allowed",
    "production_runtime_claimed",
    "schema_version",
    "solver_outcome",
    "status",
    "website_mutation_allowed",
    "website_surfaces",
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
    "Foundation Website Posture Boundary",
    "Witness packet: [`../examples/foundation_website_posture_witness.awaiting_evidence.json`]",
    "Rule: Website-posture preparation is a local planning boundary, not a website publication or access-opening certificate.",
    "No website mutation, external website publication, access invitation, waitlist",
    "website_posture_boundary_state=AwaitingEvidence",
    "website_mutation_allowed=false",
    "access_invitation_allowed=false",
    "waitlist_open=false",
    "external_publication_allowed=false",
    "deployment_allowed=false",
    "python scripts/validate_foundation_website_posture_boundary.py",
)
FORBIDDEN_VALUE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("url_value", re.compile(r"https?://", re.IGNORECASE)),
    ("email_value", re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)),
    ("mailto_value", re.compile(r"\bmailto:", re.IGNORECASE)),
    ("private_path", re.compile(r"\b[A-Za-z]:[\\/]|\\\\", re.IGNORECASE)),
    ("route_target_assignment", re.compile(r"\b(?:route|site|page|path)[_ -]?(?:url|target|ref|value)\s*=", re.IGNORECASE)),
    ("access_target_assignment", re.compile(r"\b(?:access|intake|signup|contact)[_ -]?(?:url|target|email|ref|value)\s*=", re.IGNORECASE)),
    ("waitlist_target_assignment", re.compile(r"\b(?:waitlist|beta|pilot)[_ -]?(?:url|target|form|ref|value)\s*=", re.IGNORECASE)),
    ("deployment_target_assignment", re.compile(r"\b(?:deploy|deployment|endpoint|runtime)[_ -]?(?:url|target|id|ref|value)\s*=", re.IGNORECASE)),
    ("account_assignment", re.compile(r"\b(?:account|tenant|provider|project)[_ -]?(?:id|ref|target|value)\s*=", re.IGNORECASE)),
    ("secret_assignment", re.compile(r"\b(?:password|secret|token|api[_ -]?key)\s*=", re.IGNORECASE)),
    ("private_key_material", re.compile(r"BEGIN [A-Z ]*PRIVATE KEY")),
)
FORBIDDEN_PROMOTION_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("website_published", re.compile(r"\bwebsite\s+(?:is\s+)?published\b", re.IGNORECASE)),
    ("request_access", re.compile(r"\brequest\s+access\b", re.IGNORECASE)),
    ("join_waitlist", re.compile(r"\bjoin\s+(?:the\s+)?waitlist\b", re.IGNORECASE)),
    ("waitlist_open", re.compile(r"\bwaitlist\s+(?:is\s+)?open\b", re.IGNORECASE)),
    ("beta_open", re.compile(r"\bbeta\s+(?:is\s+)?open\b", re.IGNORECASE)),
    ("pilot_signup_open", re.compile(r"\bpilot\s+signup\s+(?:is\s+)?open\b", re.IGNORECASE)),
    ("customer_intake_open", re.compile(r"\bcustomer\s+intake\s+(?:is\s+)?open\b", re.IGNORECASE)),
    ("production_runtime_ready", re.compile(r"\bproduction\s+runtime\s+(?:is\s+)?ready\b", re.IGNORECASE)),
    ("endpoint_ready", re.compile(r"\bendpoint\s+(?:is\s+)?ready\b", re.IGNORECASE)),
    ("paid_launch_ready", re.compile(r"\bpaid\s+launch\s+(?:is\s+)?ready\b", re.IGNORECASE)),
    ("deployment_ready", re.compile(r"\bdeployment\s+(?:is\s+)?ready\b", re.IGNORECASE)),
)


@dataclass(frozen=True, slots=True)
class WebsitePostureFinding:
    """One deterministic website-posture boundary validation finding."""

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


def validate_doc_text(text: str) -> list[WebsitePostureFinding]:
    """Return findings for missing website-posture documentation anchors."""

    findings: list[WebsitePostureFinding] = []
    for phrase in REQUIRED_DOC_PHRASES:
        if phrase not in text:
            findings.append(
                WebsitePostureFinding(
                    "foundation_website_posture_doc_phrase_missing",
                    f"website-posture boundary doc missing required phrase: {phrase}",
                )
            )
    return findings


def validate_packet(payload: dict[str, Any]) -> list[WebsitePostureFinding]:
    """Return findings for website-posture witness drift."""

    findings: list[WebsitePostureFinding] = []
    findings.extend(validate_root_contract(payload))
    findings.extend(validate_website_surfaces(payload.get("website_surfaces")))
    findings.extend(validate_forbidden_value_patterns(payload))
    findings.extend(validate_forbidden_promotion_patterns(payload))
    return findings


def validate_root_contract(payload: dict[str, Any]) -> list[WebsitePostureFinding]:
    """Return findings for root-level website-posture witness drift."""

    findings: list[WebsitePostureFinding] = []
    if set(payload) != EXPECTED_ROOT_KEYS:
        findings.append(
            WebsitePostureFinding(
                "website_posture_root_keys_invalid",
                f"root keys must be: {', '.join(sorted(EXPECTED_ROOT_KEYS))}",
            )
        )
    expected_values = {
        "witness_id": EXPECTED_WITNESS_ID,
        "schema_version": 1,
        "status": "AwaitingEvidence",
        "solver_outcome": "AwaitingEvidence",
        "website_mutation_allowed": False,
        "external_publication_allowed": False,
        "access_invitation_allowed": False,
        "waitlist_open": False,
        "beta_invitation_allowed": False,
        "pilot_signup_allowed": False,
        "customer_intake_allowed": False,
        "production_runtime_claimed": False,
        "endpoint_readiness_claimed": False,
        "paid_launch_allowed": False,
        "deployment_allowed": False,
    }
    for key, expected_value in expected_values.items():
        if payload.get(key) != expected_value:
            findings.append(
                WebsitePostureFinding(
                    "website_posture_root_value_invalid",
                    f"{key} must be {expected_value!r}",
                )
            )
    if tuple(payload.get("blocked_claims") or ()) != EXPECTED_BLOCKED_CLAIMS:
        findings.append(
            WebsitePostureFinding(
                "website_posture_blocked_claims_invalid",
                f"blocked_claims must be: {', '.join(EXPECTED_BLOCKED_CLAIMS)}",
            )
        )
    next_action = payload.get("next_action")
    if not isinstance(next_action, str) or "do not mutate website" not in next_action:
        findings.append(
            WebsitePostureFinding(
                "website_posture_next_action_invalid",
                "next_action must preserve the website-posture boundary",
            )
        )
    return findings


def validate_website_surfaces(website_surfaces: object) -> list[WebsitePostureFinding]:
    """Return findings for website-surface witness drift."""

    findings: list[WebsitePostureFinding] = []
    if not isinstance(website_surfaces, list) or not all(isinstance(surface, dict) for surface in website_surfaces):
        return [WebsitePostureFinding("website_posture_surfaces_invalid", "website_surfaces must be a list of objects")]
    observed_surfaces = tuple(
        (surface.get("surface_id"), surface.get("surface_type"), surface.get("state"))
        for surface in website_surfaces
    )
    if observed_surfaces != EXPECTED_SURFACES:
        findings.append(
            WebsitePostureFinding(
                "website_posture_surface_inventory_invalid",
                "website surface inventory does not match the Foundation Mode website set",
            )
        )
    surface_ids = [surface.get("surface_id") for surface in website_surfaces]
    if len(set(surface_ids)) != len(surface_ids):
        findings.append(WebsitePostureFinding("website_posture_surface_duplicate", "surface ids must be unique"))
    for surface in website_surfaces:
        surface_id = str(surface.get("surface_id", "<missing>"))
        if set(surface) != EXPECTED_SURFACE_KEYS:
            findings.append(
                WebsitePostureFinding(
                    "website_posture_surface_keys_invalid",
                    f"{surface_id} surface keys must be: {', '.join(sorted(EXPECTED_SURFACE_KEYS))}",
                )
            )
        if surface.get("state") != "AwaitingEvidence":
            findings.append(
                WebsitePostureFinding(
                    "website_posture_surface_state_invalid",
                    f"{surface_id} state must be AwaitingEvidence",
                )
            )
        if surface.get("evidence_ref") != "manual_preparation_pending":
            findings.append(
                WebsitePostureFinding(
                    "website_posture_surface_evidence_invalid",
                    f"{surface_id} evidence_ref must stay manual_preparation_pending in the committed packet",
                )
            )
        if not isinstance(surface.get("public_safe_note"), str) or not surface["public_safe_note"].strip():
            findings.append(
                WebsitePostureFinding(
                    "website_posture_surface_note_invalid",
                    f"{surface_id} public_safe_note must be a non-empty string",
                )
            )
    return findings


def validate_forbidden_value_patterns(payload: dict[str, Any]) -> list[WebsitePostureFinding]:
    """Return findings for private, route, access, publication, or deployment-shaped values."""

    serialized_payload = json.dumps(payload, sort_keys=True)
    findings: list[WebsitePostureFinding] = []
    for rule_id, pattern in FORBIDDEN_VALUE_PATTERNS:
        if pattern.search(serialized_payload):
            findings.append(
                WebsitePostureFinding(
                    "website_posture_forbidden_private_value_pattern",
                    f"website-posture witness contains forbidden value pattern: {rule_id}",
                )
            )
    return findings


def validate_forbidden_promotion_patterns(payload: dict[str, Any]) -> list[WebsitePostureFinding]:
    """Return findings if the witness drifts into website-promotion phrases."""

    serialized_payload = json.dumps(payload, sort_keys=True)
    findings: list[WebsitePostureFinding] = []
    for rule_id, pattern in FORBIDDEN_PROMOTION_PATTERNS:
        if pattern.search(serialized_payload):
            findings.append(
                WebsitePostureFinding(
                    "website_posture_forbidden_promotion_phrase",
                    f"website-posture witness contains forbidden promotion pattern: {rule_id}",
                )
            )
    return findings


def validate_foundation_website_posture_boundary(
    doc_path: Path = DEFAULT_DOC_PATH,
    packet_path: Path = DEFAULT_PACKET_PATH,
) -> list[WebsitePostureFinding]:
    """Validate the Foundation Mode website-posture boundary artifacts."""

    doc_text = load_text(doc_path, "website-posture boundary doc")
    packet_payload = load_json_object(packet_path, "website-posture witness packet")
    return [
        *validate_doc_text(doc_text),
        *validate_packet(packet_payload),
    ]


def main(argv: list[str] | None = None) -> int:
    """Validate website-posture boundary artifacts and print deterministic status."""

    parser = argparse.ArgumentParser(description="Validate Foundation Mode website-posture boundary artifacts.")
    parser.add_argument("--doc", type=Path, default=DEFAULT_DOC_PATH)
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET_PATH)
    args = parser.parse_args(argv)

    try:
        findings = validate_foundation_website_posture_boundary(args.doc, args.packet)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"[FAIL] foundation_website_posture_load: {exc}", file=sys.stderr)
        print("STATUS: failed", file=sys.stderr)
        return 1

    if findings:
        for finding in findings:
            print(f"[FAIL] {finding.rule_id}: {finding.message}", file=sys.stderr)
        print("STATUS: failed", file=sys.stderr)
        return 1
    print("[PASS] foundation_website_posture_doc")
    print("[PASS] foundation_website_posture_witness")
    print("STATUS: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
