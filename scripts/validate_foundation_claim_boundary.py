#!/usr/bin/env python3
"""Validate the Foundation Mode claim boundary.

Purpose: keep claim separation local and public-safe while production-health,
endpoint-readiness, customer-readiness, pilot-readiness, legal-clearance,
commercial-readiness, public-launch, compliance-certification,
external-publication, and deployment claims remain blocked.
Governance scope: Foundation Mode, claim posture, repository-proof claims,
public-copy claims, runtime-proof claims, legal/business claims,
customer/pilot claims, private-value exclusion, and deployment blocking.
Dependencies: docs/FOUNDATION_CLAIM_BOUNDARY.md and
examples/foundation_claim_boundary_witness.awaiting_evidence.json.
Invariants:
  - Validation is read-only.
  - The witness records claim-boundary preparation only.
  - No production health, endpoint readiness, customer readiness, pilot
    readiness, legal clearance, commercial readiness, public launch,
    compliance certification, external publication, or deployment claim is
    allowed.
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
DEFAULT_DOC_PATH = REPO_ROOT / "docs" / "FOUNDATION_CLAIM_BOUNDARY.md"
DEFAULT_PACKET_PATH = REPO_ROOT / "examples" / "foundation_claim_boundary_witness.awaiting_evidence.json"

EXPECTED_WITNESS_ID = "foundation_claim_boundary_witness.awaiting_evidence.v1"
EXPECTED_BLOCKED_CLAIMS = (
    "production health",
    "endpoint readiness",
    "customer readiness",
    "pilot readiness",
    "legal clearance",
    "commercial readiness",
    "public launch",
    "compliance certification",
    "external publication",
    "deployment readiness",
)
EXPECTED_SURFACES = (
    ("repository_proof_claims", "local_draft", "AwaitingEvidence"),
    ("public_copy_claims", "local_draft", "AwaitingEvidence"),
    ("runtime_proof_claims", "local_draft", "AwaitingEvidence"),
    ("legal_business_claims", "local_draft", "AwaitingEvidence"),
    ("customer_pilot_claims", "local_draft", "AwaitingEvidence"),
    ("deployment_claims", "local_draft", "AwaitingEvidence"),
    ("evidence_promotion_questions", "local_draft", "AwaitingEvidence"),
    ("claim_review_handoff", "local_draft", "AwaitingEvidence"),
)
EXPECTED_ROOT_KEYS = {
    "blocked_claims",
    "claim_surfaces",
    "commercial_readiness_claimed",
    "compliance_certification_claimed",
    "customer_readiness_claimed",
    "deployment_allowed",
    "endpoint_readiness_claimed",
    "external_publication_allowed",
    "legal_clearance_claimed",
    "next_action",
    "pilot_readiness_claimed",
    "production_health_claimed",
    "public_launch_claimed",
    "schema_version",
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
    "Foundation Claim Boundary",
    "Witness packet: [`../examples/foundation_claim_boundary_witness.awaiting_evidence.json`]",
    "Rule: Claim-boundary preparation is a local planning boundary, not a claim-promotion certificate.",
    "No production-health claim, endpoint-readiness claim, customer-readiness claim,",
    "claim_boundary_state=AwaitingEvidence",
    "production_health_claimed=false",
    "endpoint_readiness_claimed=false",
    "customer_readiness_claimed=false",
    "external_publication_allowed=false",
    "deployment_allowed=false",
    "python scripts/validate_foundation_claim_boundary.py",
)
FORBIDDEN_VALUE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("url_value", re.compile(r"https?://", re.IGNORECASE)),
    ("email_value", re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)),
    ("private_path", re.compile(r"\b[A-Za-z]:[\\/]|\\\\", re.IGNORECASE)),
    ("endpoint_assignment", re.compile(r"\b(?:endpoint|health|runtime|gateway)[_ -]?(?:url|target|id|ref|value)\s*=", re.IGNORECASE)),
    ("customer_assignment", re.compile(r"\b(?:customer|pilot|waitlist|lead)[_ -]?(?:id|email|target|ref|value)\s*=", re.IGNORECASE)),
    ("legal_assignment", re.compile(r"\b(?:legal|trademark|patent|company|tax)[_ -]?(?:status|id|ref|value)\s*=", re.IGNORECASE)),
    ("compliance_assignment", re.compile(r"\b(?:compliance|certification|audit)[_ -]?(?:status|id|ref|value)\s*=", re.IGNORECASE)),
    ("deployment_assignment", re.compile(r"\b(?:deploy|deployment|cluster|region)[_ -]?(?:url|target|id|ref|value)\s*=", re.IGNORECASE)),
    ("account_assignment", re.compile(r"\b(?:account|tenant|provider|project)[_ -]?(?:id|ref|target|value)\s*=", re.IGNORECASE)),
    ("secret_assignment", re.compile(r"\b(?:password|secret|token|api[_ -]?key)\s*=", re.IGNORECASE)),
    ("private_key_material", re.compile(r"BEGIN [A-Z ]*PRIVATE KEY")),
)
FORBIDDEN_PROMOTION_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("production_health_ready", re.compile(r"\bproduction\s+health\s+(?:is\s+)?(?:ready|verified|passing)\b", re.IGNORECASE)),
    ("endpoint_ready", re.compile(r"\bendpoint\s+(?:is\s+)?ready\b", re.IGNORECASE)),
    ("customer_ready", re.compile(r"\bcustomer\s+(?:is\s+)?ready\b", re.IGNORECASE)),
    ("pilot_ready", re.compile(r"\bpilot\s+(?:is\s+)?ready\b", re.IGNORECASE)),
    ("legally_cleared", re.compile(r"\blegally\s+cleared\b", re.IGNORECASE)),
    ("commercial_ready", re.compile(r"\bcommercial(?:ly)?\s+(?:is\s+)?ready\b", re.IGNORECASE)),
    ("public_launch_ready", re.compile(r"\bpublic\s+launch\s+(?:is\s+)?ready\b", re.IGNORECASE)),
    ("compliance_certified", re.compile(r"\bcompliance\s+(?:is\s+)?certified\b", re.IGNORECASE)),
    ("externally_published", re.compile(r"\bexternally\s+published\b", re.IGNORECASE)),
    ("deployment_ready", re.compile(r"\bdeployment\s+(?:is\s+)?ready\b", re.IGNORECASE)),
)


@dataclass(frozen=True, slots=True)
class ClaimBoundaryFinding:
    """One deterministic claim-boundary validation finding."""

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
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{label} must be a JSON object")
    return payload


def validate_doc_text(text: str) -> list[ClaimBoundaryFinding]:
    """Return findings for missing claim-boundary documentation anchors."""

    findings: list[ClaimBoundaryFinding] = []
    for phrase in REQUIRED_DOC_PHRASES:
        if phrase not in text:
            findings.append(
                ClaimBoundaryFinding(
                    "foundation_claim_boundary_doc_phrase_missing",
                    f"claim boundary doc missing required phrase: {phrase}",
                )
            )
    return findings


def validate_packet(payload: dict[str, Any]) -> list[ClaimBoundaryFinding]:
    """Return findings for claim-boundary witness drift."""

    findings: list[ClaimBoundaryFinding] = []
    findings.extend(validate_root_contract(payload))
    findings.extend(validate_claim_surfaces(payload.get("claim_surfaces")))
    findings.extend(validate_forbidden_value_patterns(payload))
    findings.extend(validate_forbidden_promotion_patterns(payload))
    return findings


def validate_root_contract(payload: dict[str, Any]) -> list[ClaimBoundaryFinding]:
    """Return findings for root-level claim-boundary witness drift."""

    findings: list[ClaimBoundaryFinding] = []
    if set(payload) != EXPECTED_ROOT_KEYS:
        findings.append(
            ClaimBoundaryFinding(
                "claim_boundary_root_keys_invalid",
                f"root keys must be: {', '.join(sorted(EXPECTED_ROOT_KEYS))}",
            )
        )
    expected_values = {
        "witness_id": EXPECTED_WITNESS_ID,
        "schema_version": 1,
        "status": "AwaitingEvidence",
        "solver_outcome": "AwaitingEvidence",
        "production_health_claimed": False,
        "endpoint_readiness_claimed": False,
        "customer_readiness_claimed": False,
        "pilot_readiness_claimed": False,
        "legal_clearance_claimed": False,
        "commercial_readiness_claimed": False,
        "public_launch_claimed": False,
        "compliance_certification_claimed": False,
        "external_publication_allowed": False,
        "deployment_allowed": False,
    }
    for key, expected_value in expected_values.items():
        if payload.get(key) != expected_value:
            findings.append(
                ClaimBoundaryFinding(
                    "claim_boundary_root_value_invalid",
                    f"{key} must be {expected_value!r}",
                )
            )
    if tuple(payload.get("blocked_claims") or ()) != EXPECTED_BLOCKED_CLAIMS:
        findings.append(
            ClaimBoundaryFinding(
                "claim_boundary_blocked_claims_invalid",
                f"blocked_claims must be: {', '.join(EXPECTED_BLOCKED_CLAIMS)}",
            )
        )
    next_action = payload.get("next_action")
    if not isinstance(next_action, str) or "do not claim production health" not in next_action:
        findings.append(
            ClaimBoundaryFinding(
                "claim_boundary_next_action_invalid",
                "next_action must preserve the claim-promotion boundary",
            )
        )
    return findings


def validate_claim_surfaces(claim_surfaces: object) -> list[ClaimBoundaryFinding]:
    """Return findings for claim-surface witness drift."""

    findings: list[ClaimBoundaryFinding] = []
    if not isinstance(claim_surfaces, list) or not all(isinstance(surface, dict) for surface in claim_surfaces):
        return [ClaimBoundaryFinding("claim_boundary_surfaces_invalid", "claim_surfaces must be a list of objects")]
    observed_surfaces = tuple(
        (surface.get("surface_id"), surface.get("surface_type"), surface.get("state"))
        for surface in claim_surfaces
    )
    if observed_surfaces != EXPECTED_SURFACES:
        findings.append(
            ClaimBoundaryFinding(
                "claim_boundary_surface_inventory_invalid",
                "claim surface inventory does not match the Foundation Mode claim set",
            )
        )
    surface_ids = [surface.get("surface_id") for surface in claim_surfaces]
    if len(set(surface_ids)) != len(surface_ids):
        findings.append(ClaimBoundaryFinding("claim_boundary_surface_duplicate", "surface ids must be unique"))
    for surface in claim_surfaces:
        surface_id = str(surface.get("surface_id", "<missing>"))
        if set(surface) != EXPECTED_SURFACE_KEYS:
            findings.append(
                ClaimBoundaryFinding(
                    "claim_boundary_surface_keys_invalid",
                    f"{surface_id} surface keys must be: {', '.join(sorted(EXPECTED_SURFACE_KEYS))}",
                )
            )
        if surface.get("state") != "AwaitingEvidence":
            findings.append(
                ClaimBoundaryFinding(
                    "claim_boundary_surface_state_invalid",
                    f"{surface_id} state must be AwaitingEvidence",
                )
            )
        if surface.get("evidence_ref") != "manual_preparation_pending":
            findings.append(
                ClaimBoundaryFinding(
                    "claim_boundary_surface_evidence_invalid",
                    f"{surface_id} evidence_ref must stay manual_preparation_pending in the committed packet",
                )
            )
        if not isinstance(surface.get("public_safe_note"), str) or not surface["public_safe_note"].strip():
            findings.append(
                ClaimBoundaryFinding(
                    "claim_boundary_surface_note_invalid",
                    f"{surface_id} public_safe_note must be a non-empty string",
                )
            )
    return findings


def validate_forbidden_value_patterns(payload: dict[str, Any]) -> list[ClaimBoundaryFinding]:
    """Return findings for private, endpoint, legal, customer, or deployment-shaped values."""

    serialized_payload = json.dumps(payload, sort_keys=True)
    findings: list[ClaimBoundaryFinding] = []
    for rule_id, pattern in FORBIDDEN_VALUE_PATTERNS:
        if pattern.search(serialized_payload):
            findings.append(
                ClaimBoundaryFinding(
                    "claim_boundary_forbidden_private_value_pattern",
                    f"claim-boundary witness contains forbidden value pattern: {rule_id}",
                )
            )
    return findings


def validate_forbidden_promotion_patterns(payload: dict[str, Any]) -> list[ClaimBoundaryFinding]:
    """Return findings if the witness drifts into claim-promotion phrases."""

    serialized_payload = json.dumps(payload, sort_keys=True)
    findings: list[ClaimBoundaryFinding] = []
    for rule_id, pattern in FORBIDDEN_PROMOTION_PATTERNS:
        if pattern.search(serialized_payload):
            findings.append(
                ClaimBoundaryFinding(
                    "claim_boundary_forbidden_promotion_phrase",
                    f"claim-boundary witness contains forbidden promotion pattern: {rule_id}",
                )
            )
    return findings


def validate_foundation_claim_boundary(
    doc_path: Path = DEFAULT_DOC_PATH,
    packet_path: Path = DEFAULT_PACKET_PATH,
) -> list[ClaimBoundaryFinding]:
    """Validate the Foundation Mode claim-boundary artifacts."""

    doc_text = load_text(doc_path, "claim boundary doc")
    packet_payload = load_json_object(packet_path, "claim-boundary witness packet")
    return [
        *validate_doc_text(doc_text),
        *validate_packet(packet_payload),
    ]


def main(argv: list[str] | None = None) -> int:
    """Validate claim-boundary artifacts and print deterministic status."""

    parser = argparse.ArgumentParser(description="Validate Foundation Mode claim-boundary artifacts.")
    parser.add_argument("--doc", type=Path, default=DEFAULT_DOC_PATH)
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET_PATH)
    args = parser.parse_args(argv)

    try:
        findings = validate_foundation_claim_boundary(args.doc, args.packet)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"[FAIL] foundation_claim_boundary_load: {exc}", file=sys.stderr)
        print("STATUS: failed", file=sys.stderr)
        return 1

    if findings:
        for finding in findings:
            print(f"[FAIL] {finding.rule_id}: {finding.message}", file=sys.stderr)
        print("STATUS: failed", file=sys.stderr)
        return 1
    print("[PASS] foundation_claim_boundary_doc")
    print("[PASS] foundation_claim_boundary_witness")
    print("STATUS: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
