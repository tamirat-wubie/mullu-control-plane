#!/usr/bin/env python3
"""Validate the Foundation Mode security-baseline boundary.

Purpose: keep security-baseline preparation local while scan-pass, dependency
audit, threat-model approval, access-control verification, data-exposure
approval, supply-chain approval, compliance certification, customer-security,
and deployment claims remain blocked.
Governance scope: Foundation Mode, local security posture, public-safe planning
witness, private-value exclusion, security-readiness blocking, and deployment
blocking.
Dependencies: docs/FOUNDATION_SECURITY_BASELINE_BOUNDARY.md and
examples/foundation_security_baseline_witness.awaiting_evidence.json.
Invariants:
  - Validation is read-only.
  - The witness records local security-baseline planning only.
  - No security baseline verification, scan-pass claim, dependency-audit pass,
    threat-model approval, access-control verification, data-exposure approval,
    supply-chain approval, compliance certification, customer-security
    readiness, private value, or deployment claim is allowed.
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
DEFAULT_DOC_PATH = REPO_ROOT / "docs" / "FOUNDATION_SECURITY_BASELINE_BOUNDARY.md"
DEFAULT_PACKET_PATH = REPO_ROOT / "examples" / "foundation_security_baseline_witness.awaiting_evidence.json"

EXPECTED_WITNESS_ID = "foundation_security_baseline_witness.awaiting_evidence.v1"
EXPECTED_BLOCKED_CLAIMS = (
    "security baseline verification",
    "secret scan pass",
    "vulnerability scan pass",
    "dependency audit pass",
    "approved threat model",
    "access control verification",
    "approved data exposure review",
    "approved supply chain review",
    "compliance certification",
    "customer security readiness",
    "deployment readiness",
)
EXPECTED_SURFACES = (
    ("security_scope_inventory", "local_draft", "AwaitingEvidence"),
    ("threat_model_questions", "local_draft", "AwaitingEvidence"),
    ("dependency_audit_questions", "local_draft", "AwaitingEvidence"),
    ("static_scan_questions", "local_draft", "AwaitingEvidence"),
    ("access_control_questions", "local_draft", "AwaitingEvidence"),
    ("data_exposure_questions", "local_draft", "AwaitingEvidence"),
    ("supply_chain_questions", "local_draft", "AwaitingEvidence"),
    ("security_review_readiness_questions", "local_draft", "AwaitingEvidence"),
)
EXPECTED_ROOT_KEYS = {
    "access_control_verified",
    "blocked_claims",
    "compliance_certification_claimed",
    "customer_security_ready_claimed",
    "data_exposure_review_approved",
    "dependency_audit_pass_claimed",
    "deployment_allowed",
    "next_action",
    "schema_version",
    "secret_scan_pass_claimed",
    "security_baseline_surfaces",
    "security_baseline_verified",
    "solver_outcome",
    "status",
    "supply_chain_review_approved",
    "threat_model_approved",
    "vulnerability_scan_pass_claimed",
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
    "Foundation Security Baseline Boundary",
    "Witness packet: [`../examples/foundation_security_baseline_witness.awaiting_evidence.json`]",
    "Rule: Security-baseline preparation is a local planning boundary, not",
    "No security baseline verification, secret scan pass, vulnerability scan pass,",
    "security_baseline_boundary_state=AwaitingEvidence",
    "security_baseline_verified=false",
    "secret_scan_pass_claimed=false",
    "vulnerability_scan_pass_claimed=false",
    "deployment_allowed=false",
    "python scripts/validate_foundation_security_baseline_boundary.py",
)
FORBIDDEN_VALUE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("url_value", re.compile(r"https?://", re.IGNORECASE)),
    ("email_value", re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)),
    ("private_path", re.compile(r"\b[A-Za-z]:[\\/]|\\\\", re.IGNORECASE)),
    ("secret_assignment", re.compile(r"\b(?:password|secret|token|api[_ -]?key)\s*=", re.IGNORECASE)),
    (
        "scanner_target_assignment",
        re.compile(
            r"\b(?:scan|scanner|sast|dast|vuln|vulnerability)[_ -]?(?:target|url|path|scope|id|ref)?\s*=",
            re.IGNORECASE,
        ),
    ),
    (
        "dependency_target_assignment",
        re.compile(r"\b(?:dependency|lockfile|sbom)[_ -]?(?:target|path|url|id|ref)?\s*=", re.IGNORECASE),
    ),
    (
        "access_target_assignment",
        re.compile(r"\b(?:actor|role|tenant|approval)[_ -]?(?:target|id|ref|value)?\s*=", re.IGNORECASE),
    ),
    (
        "compliance_target_assignment",
        re.compile(r"\b(?:compliance|certification|audit)[_ -]?(?:target|id|ref|value)?\s*=", re.IGNORECASE),
    ),
    (
        "finding_target_assignment",
        re.compile(r"\b(?:finding|risk|issue)[_ -]?(?:target|id|ref|value)?\s*=", re.IGNORECASE),
    ),
)
FORBIDDEN_PROMOTION_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("security_ready", re.compile(r"\bsecurity\s+(?:is\s+)?ready\b", re.IGNORECASE)),
    ("security_baseline_verified", re.compile(r"\bsecurity\s+baseline\s+(?:is\s+)?verified\b", re.IGNORECASE)),
    ("secret_scan_passed", re.compile(r"\bsecret\s+scan\s+(?:is\s+)?passed\b", re.IGNORECASE)),
    ("vulnerability_scan_passed", re.compile(r"\bvulnerability\s+scan\s+(?:is\s+)?passed\b", re.IGNORECASE)),
    ("dependency_audit_passed", re.compile(r"\bdependency\s+audit\s+(?:is\s+)?passed\b", re.IGNORECASE)),
    ("threat_model_approved", re.compile(r"\bthreat\s+model\s+(?:is\s+)?approved\b", re.IGNORECASE)),
    ("access_control_verified", re.compile(r"\baccess\s+control\s+(?:is\s+)?verified\b", re.IGNORECASE)),
    (
        "data_exposure_review_approved",
        re.compile(r"\bdata\s+exposure\s+review\s+(?:is\s+)?approved\b", re.IGNORECASE),
    ),
    (
        "supply_chain_review_approved",
        re.compile(r"\bsupply\s+chain\s+review\s+(?:is\s+)?approved\b", re.IGNORECASE),
    ),
    ("compliance_certified", re.compile(r"\bcompliance\s+(?:is\s+)?certified\b", re.IGNORECASE)),
    ("customer_security_ready", re.compile(r"\bcustomer\s+security\s+(?:is\s+)?ready\b", re.IGNORECASE)),
    ("deployment_ready", re.compile(r"\bdeployment\s+(?:is\s+)?ready\b", re.IGNORECASE)),
)


@dataclass(frozen=True, slots=True)
class SecurityBaselineFinding:
    """One deterministic security-baseline boundary validation finding."""

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


def validate_doc_text(text: str) -> list[SecurityBaselineFinding]:
    """Return findings for missing security-baseline documentation anchors."""

    findings: list[SecurityBaselineFinding] = []
    for phrase in REQUIRED_DOC_PHRASES:
        if phrase not in text:
            findings.append(
                SecurityBaselineFinding(
                    "foundation_security_baseline_doc_phrase_missing",
                    f"security-baseline boundary doc missing required phrase: {phrase}",
                )
            )
    return findings


def validate_packet(payload: dict[str, Any]) -> list[SecurityBaselineFinding]:
    """Return findings for security-baseline witness drift."""

    findings: list[SecurityBaselineFinding] = []
    findings.extend(validate_root_contract(payload))
    findings.extend(validate_security_baseline_surfaces(payload.get("security_baseline_surfaces")))
    findings.extend(validate_forbidden_value_patterns(payload))
    findings.extend(validate_forbidden_promotion_patterns(payload))
    return findings


def validate_root_contract(payload: dict[str, Any]) -> list[SecurityBaselineFinding]:
    """Return findings for root-level security-baseline witness drift."""

    findings: list[SecurityBaselineFinding] = []
    if set(payload) != EXPECTED_ROOT_KEYS:
        findings.append(
            SecurityBaselineFinding(
                "security_baseline_root_keys_invalid",
                f"root keys must be: {', '.join(sorted(EXPECTED_ROOT_KEYS))}",
            )
        )
    expected_values = {
        "witness_id": EXPECTED_WITNESS_ID,
        "schema_version": 1,
        "status": "AwaitingEvidence",
        "solver_outcome": "AwaitingEvidence",
        "security_baseline_verified": False,
        "secret_scan_pass_claimed": False,
        "vulnerability_scan_pass_claimed": False,
        "dependency_audit_pass_claimed": False,
        "threat_model_approved": False,
        "access_control_verified": False,
        "data_exposure_review_approved": False,
        "supply_chain_review_approved": False,
        "compliance_certification_claimed": False,
        "customer_security_ready_claimed": False,
        "deployment_allowed": False,
    }
    for key, expected_value in expected_values.items():
        if payload.get(key) != expected_value:
            findings.append(
                SecurityBaselineFinding(
                    "security_baseline_root_value_invalid",
                    f"{key} must be {expected_value!r}",
                )
            )
    if tuple(payload.get("blocked_claims") or ()) != EXPECTED_BLOCKED_CLAIMS:
        findings.append(
            SecurityBaselineFinding(
                "security_baseline_blocked_claims_invalid",
                f"blocked_claims must be: {', '.join(EXPECTED_BLOCKED_CLAIMS)}",
            )
        )
    next_action = payload.get("next_action")
    if not isinstance(next_action, str) or "do not claim scan pass" not in next_action:
        findings.append(
            SecurityBaselineFinding(
                "security_baseline_next_action_invalid",
                "next_action must preserve the closed security-baseline boundary",
            )
        )
    return findings


def validate_security_baseline_surfaces(security_baseline_surfaces: object) -> list[SecurityBaselineFinding]:
    """Return findings for security-baseline surface witness drift."""

    findings: list[SecurityBaselineFinding] = []
    if not isinstance(security_baseline_surfaces, list) or not all(
        isinstance(surface, dict) for surface in security_baseline_surfaces
    ):
        return [
            SecurityBaselineFinding(
                "security_baseline_surfaces_invalid",
                "security_baseline_surfaces must be a list of objects",
            )
        ]
    observed_surfaces = tuple(
        (surface.get("surface_id"), surface.get("surface_type"), surface.get("state"))
        for surface in security_baseline_surfaces
    )
    if observed_surfaces != EXPECTED_SURFACES:
        findings.append(
            SecurityBaselineFinding(
                "security_baseline_surface_inventory_invalid",
                "security-baseline surface inventory does not match the Foundation Mode security set",
            )
        )
    surface_ids = [surface.get("surface_id") for surface in security_baseline_surfaces]
    if len(set(surface_ids)) != len(surface_ids):
        findings.append(SecurityBaselineFinding("security_baseline_surface_duplicate", "surface ids must be unique"))
    for surface in security_baseline_surfaces:
        surface_id = str(surface.get("surface_id", "<missing>"))
        if set(surface) != EXPECTED_SURFACE_KEYS:
            findings.append(
                SecurityBaselineFinding(
                    "security_baseline_surface_keys_invalid",
                    f"{surface_id} surface keys must be: {', '.join(sorted(EXPECTED_SURFACE_KEYS))}",
                )
            )
        if surface.get("state") != "AwaitingEvidence":
            findings.append(
                SecurityBaselineFinding(
                    "security_baseline_surface_state_invalid",
                    f"{surface_id} state must be AwaitingEvidence",
                )
            )
        if surface.get("evidence_ref") != "manual_preparation_pending":
            findings.append(
                SecurityBaselineFinding(
                    "security_baseline_surface_evidence_invalid",
                    f"{surface_id} evidence_ref must stay manual_preparation_pending in the committed packet",
                )
            )
        if not isinstance(surface.get("public_safe_note"), str) or not surface["public_safe_note"].strip():
            findings.append(
                SecurityBaselineFinding(
                    "security_baseline_surface_note_invalid",
                    f"{surface_id} public_safe_note must be a non-empty string",
                )
            )
    return findings


def validate_forbidden_value_patterns(payload: dict[str, Any]) -> list[SecurityBaselineFinding]:
    """Return findings for private target, scanner, dependency, access, or compliance-shaped values."""

    serialized_payload = json.dumps(payload, sort_keys=True)
    findings: list[SecurityBaselineFinding] = []
    for rule_id, pattern in FORBIDDEN_VALUE_PATTERNS:
        if pattern.search(serialized_payload):
            findings.append(
                SecurityBaselineFinding(
                    "security_baseline_forbidden_private_value_pattern",
                    f"security-baseline witness contains forbidden value pattern: {rule_id}",
                )
            )
    return findings


def validate_forbidden_promotion_patterns(payload: dict[str, Any]) -> list[SecurityBaselineFinding]:
    """Return findings if the witness drifts into security-readiness claims."""

    serialized_payload = json.dumps(payload, sort_keys=True)
    findings: list[SecurityBaselineFinding] = []
    for rule_id, pattern in FORBIDDEN_PROMOTION_PATTERNS:
        if pattern.search(serialized_payload):
            findings.append(
                SecurityBaselineFinding(
                    "security_baseline_forbidden_promotion_phrase",
                    f"security-baseline witness contains forbidden promotion pattern: {rule_id}",
                )
            )
    return findings


def validate_foundation_security_baseline_boundary(
    doc_path: Path = DEFAULT_DOC_PATH,
    packet_path: Path = DEFAULT_PACKET_PATH,
) -> list[SecurityBaselineFinding]:
    """Validate the Foundation Mode security-baseline boundary artifacts."""

    doc_text = load_text(doc_path, "security-baseline boundary doc")
    packet_payload = load_json_object(packet_path, "security-baseline witness packet")
    return [
        *validate_doc_text(doc_text),
        *validate_packet(packet_payload),
    ]


def main(argv: list[str] | None = None) -> int:
    """Validate security-baseline boundary artifacts and print deterministic status."""

    parser = argparse.ArgumentParser(description="Validate Foundation Mode security-baseline boundary artifacts.")
    parser.add_argument("--doc", type=Path, default=DEFAULT_DOC_PATH)
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET_PATH)
    args = parser.parse_args(argv)

    try:
        findings = validate_foundation_security_baseline_boundary(args.doc, args.packet)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"[FAIL] foundation_security_baseline_load: {exc}", file=sys.stderr)
        print("STATUS: failed", file=sys.stderr)
        return 1

    if findings:
        for finding in findings:
            print(f"[FAIL] {finding.rule_id}: {finding.message}", file=sys.stderr)
        print("STATUS: failed", file=sys.stderr)
        return 1
    print("[PASS] foundation_security_baseline_doc")
    print("[PASS] foundation_security_baseline_witness")
    print("STATUS: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
