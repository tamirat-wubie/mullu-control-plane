#!/usr/bin/env python3
"""Validate the Foundation Mode proof-reference boundary.

Purpose: keep proof-reference drafting local and public-safe while reference
completeness, proof coverage closure, evidence promotion, terminal closure,
verification pass, proof approval, runtime readiness, owner approval, test,
refactor, implementation, publication, and deployment claims remain blocked.
Governance scope: Foundation Mode, proof-reference surfaces, private-value
exclusion, and readiness blocking.
Dependencies: docs/FOUNDATION_PROOF_REFERENCE_BOUNDARY.md and
examples/foundation_proof_reference_witness.awaiting_evidence.json.
Invariants:
  - Validation is read-only.
  - The witness records proof-reference preparation only.
  - No coverage, evidence, verification, terminal, approval, test,
    implementation, publication, or deployment claim is allowed.
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
DEFAULT_DOC_PATH = REPO_ROOT / "docs" / "FOUNDATION_PROOF_REFERENCE_BOUNDARY.md"
DEFAULT_PACKET_PATH = REPO_ROOT / "examples" / "foundation_proof_reference_witness.awaiting_evidence.json"

EXPECTED_WITNESS_ID = "foundation_proof_reference_witness.awaiting_evidence.v1"
EXPECTED_BLOCKED_CLAIMS = (
    "proof-reference completeness",
    "proof coverage closure",
    "evidence promotion",
    "terminal closure",
    "verification pass",
    "proof approval assignment",
    "runtime proof readiness",
    "owner approval assignment",
    "test pass",
    "refactor approval",
    "implementation approval",
    "external publication",
    "deployment readiness",
)
EXPECTED_SURFACES = (
    ("architecture_proof_references", "local_draft", "AwaitingEvidence"),
    ("module_proof_references", "local_draft", "AwaitingEvidence"),
    ("interface_proof_references", "local_draft", "AwaitingEvidence"),
    ("dependency_proof_references", "local_draft", "AwaitingEvidence"),
    ("invariant_proof_references", "local_draft", "AwaitingEvidence"),
    ("hazard_proof_references", "local_draft", "AwaitingEvidence"),
    ("runtime_proof_references", "local_draft", "AwaitingEvidence"),
    ("rollback_proof_references", "local_draft", "AwaitingEvidence"),
    ("operator_proof_references", "local_draft", "AwaitingEvidence"),
)
EXPECTED_ROOT_KEYS = {
    "blocked_claims",
    "deployment_allowed",
    "evidence_promotion_allowed",
    "external_publication_allowed",
    "implementation_approval_allowed",
    "next_action",
    "owner_approval_assigned",
    "proof_approval_assigned",
    "proof_coverage_closed_claimed",
    "proof_reference_complete_claimed",
    "proof_reference_surfaces",
    "refactor_approval_allowed",
    "runtime_proof_ready_claimed",
    "schema_version",
    "solver_outcome",
    "status",
    "terminal_closure_claimed",
    "test_pass_claimed",
    "verification_pass_claimed",
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
    "Foundation Proof Reference Boundary",
    "Witness packet: [`../examples/foundation_proof_reference_witness.awaiting_evidence.json`]",
    "Rule: Proof-reference preparation is a local planning boundary, not a",
    "No proof-reference completeness, proof coverage closure, evidence",
    "proof_reference_boundary_state=AwaitingEvidence",
    "proof_reference_complete_claimed=false",
    "proof_coverage_closed_claimed=false",
    "evidence_promotion_allowed=false",
    "terminal_closure_claimed=false",
    "verification_pass_claimed=false",
    "proof_approval_assigned=false",
    "runtime_proof_ready_claimed=false",
    "implementation_approval_allowed=false",
    "deployment_allowed=false",
    "python scripts/validate_foundation_proof_reference_boundary.py",
)
FORBIDDEN_VALUE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("url_value", re.compile(r"https?://", re.IGNORECASE)),
    ("email_value", re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)),
    ("private_path", re.compile(r"\b[A-Za-z]:[\\/]|\\\\", re.IGNORECASE)),
    (
        "endpoint_or_runtime_assignment",
        re.compile(
            r"\b(?:endpoint|service|server|runtime|database|container)[_ -]?"
            r"(?:id|url|ref|target|value|status)?\s*=",
            re.IGNORECASE,
        ),
    ),
    (
        "account_or_provider_assignment",
        re.compile(
            r"\b(?:account|provider|tenant|project|cloud)[_ -]?"
            r"(?:id|ref|target|value|status)?\s*=",
            re.IGNORECASE,
        ),
    ),
    (
        "proof_evidence_or_verification_assignment",
        re.compile(
            r"\b(?:proof|evidence|receipt|verification|terminal[_ -]?closure)[_ -]?"
            r"(?:id|ref|target|value|status|result|state|approval)?\s*=",
            re.IGNORECASE,
        ),
    ),
    (
        "test_pass_assignment",
        re.compile(r"\b(?:test|suite|assertion)[_ -]?(?:pass|status|result|value)?\s*=", re.IGNORECASE),
    ),
    (
        "customer_assignment",
        re.compile(
            r"\b(?:customer|pilot|participant|user)[_ -]?"
            r"(?:id|name|email|ref|target|value)?\s*=",
            re.IGNORECASE,
        ),
    ),
    (
        "secret_assignment",
        re.compile(r"\b(?:password|secret|token|api[_ -]?key|credential|client[_ -]?secret)\s*=", re.IGNORECASE),
    ),
    ("private_key_material", re.compile(r"BEGIN [A-Z ]*PRIVATE KEY")),
    (
        "implementation_assignment",
        re.compile(
            r"\b(?:implementation|refactor|migration|release)[_ -]?"
            r"(?:id|ref|target|value|status|approval)?\s*=",
            re.IGNORECASE,
        ),
    ),
    (
        "publication_or_deployment_assignment",
        re.compile(
            r"\b(?:publish|publication|deploy|deployment|production)[_ -]?"
            r"(?:id|url|ref|target|value|status)?\s*=",
            re.IGNORECASE,
        ),
    ),
)
FORBIDDEN_PROMOTION_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("proof_reference_complete", re.compile(r"\bproof\s+reference\s+(?:is\s+)?complete\b", re.IGNORECASE)),
    ("proof_coverage_closed", re.compile(r"\bproof\s+coverage\s+(?:is\s+)?closed\b", re.IGNORECASE)),
    ("evidence_promoted", re.compile(r"\bevidence\s+(?:is\s+)?promoted\b", re.IGNORECASE)),
    ("terminal_closure_claimed", re.compile(r"\bterminal\s+closure\s+(?:is\s+)?claimed\b", re.IGNORECASE)),
    ("verification_passed", re.compile(r"\bverification\s+has\s+passed\b", re.IGNORECASE)),
    ("proof_approved", re.compile(r"\bproof\s+(?:is\s+)?approved\b", re.IGNORECASE)),
    ("runtime_proof_ready", re.compile(r"\bruntime\s+proof\s+(?:is\s+)?ready\b", re.IGNORECASE)),
    ("owner_approved", re.compile(r"\bowner\s+(?:is\s+)?approved\b", re.IGNORECASE)),
    ("test_passed", re.compile(r"\btests?\s+(?:have\s+)?passed\b", re.IGNORECASE)),
    ("refactor_approved", re.compile(r"\brefactor\s+(?:is\s+)?approved\b", re.IGNORECASE)),
    ("implementation_approved", re.compile(r"\bimplementation\s+(?:is\s+)?approved\b", re.IGNORECASE)),
    ("published_externally", re.compile(r"\bpublished\s+externally\b", re.IGNORECASE)),
    ("deployment_ready", re.compile(r"\bdeployment\s+(?:is\s+)?ready\b", re.IGNORECASE)),
)


@dataclass(frozen=True, slots=True)
class ProofReferenceFinding:
    """One deterministic proof-reference validation finding."""

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


def validate_doc_text(text: str) -> list[ProofReferenceFinding]:
    """Return findings for missing proof-reference documentation anchors."""

    findings: list[ProofReferenceFinding] = []
    for phrase in REQUIRED_DOC_PHRASES:
        if phrase not in text:
            findings.append(
                ProofReferenceFinding(
                    "foundation_proof_reference_doc_phrase_missing",
                    f"proof-reference boundary doc missing required phrase: {phrase}",
                )
            )
    return findings


def validate_packet(payload: dict[str, Any]) -> list[ProofReferenceFinding]:
    """Return findings for proof-reference witness drift."""

    findings: list[ProofReferenceFinding] = []
    findings.extend(validate_root_contract(payload))
    findings.extend(validate_proof_reference_surfaces(payload.get("proof_reference_surfaces")))
    findings.extend(validate_forbidden_value_patterns(payload))
    findings.extend(validate_forbidden_promotion_patterns(payload))
    return findings


def validate_root_contract(payload: dict[str, Any]) -> list[ProofReferenceFinding]:
    """Return findings for root-level proof-reference witness drift."""

    findings: list[ProofReferenceFinding] = []
    if set(payload) != EXPECTED_ROOT_KEYS:
        findings.append(
            ProofReferenceFinding(
                "proof_reference_root_keys_invalid",
                f"root keys must be: {', '.join(sorted(EXPECTED_ROOT_KEYS))}",
            )
        )
    expected_values = {
        "witness_id": EXPECTED_WITNESS_ID,
        "schema_version": 1,
        "status": "AwaitingEvidence",
        "solver_outcome": "AwaitingEvidence",
        "proof_reference_complete_claimed": False,
        "proof_coverage_closed_claimed": False,
        "evidence_promotion_allowed": False,
        "terminal_closure_claimed": False,
        "verification_pass_claimed": False,
        "proof_approval_assigned": False,
        "runtime_proof_ready_claimed": False,
        "owner_approval_assigned": False,
        "test_pass_claimed": False,
        "refactor_approval_allowed": False,
        "implementation_approval_allowed": False,
        "external_publication_allowed": False,
        "deployment_allowed": False,
    }
    for key, expected_value in expected_values.items():
        if payload.get(key) != expected_value:
            findings.append(
                ProofReferenceFinding(
                    "proof_reference_root_value_invalid",
                    f"{key} must be {expected_value!r}",
                )
            )
    if tuple(payload.get("blocked_claims") or ()) != EXPECTED_BLOCKED_CLAIMS:
        findings.append(
            ProofReferenceFinding(
                "proof_reference_blocked_claims_invalid",
                f"blocked_claims must be: {', '.join(EXPECTED_BLOCKED_CLAIMS)}",
            )
        )
    next_action = payload.get("next_action")
    if not isinstance(next_action, str) or "continue local proof reference question drafting" not in next_action:
        findings.append(
            ProofReferenceFinding(
                "proof_reference_next_action_invalid",
                "next_action must preserve local proof reference drafting without readiness promotion",
            )
        )
    return findings


def validate_proof_reference_surfaces(proof_reference_surfaces: object) -> list[ProofReferenceFinding]:
    """Return findings for proof-reference surface drift."""

    findings: list[ProofReferenceFinding] = []
    if not isinstance(proof_reference_surfaces, list) or not all(
        isinstance(surface, dict) for surface in proof_reference_surfaces
    ):
        return [
            ProofReferenceFinding(
                "proof_reference_surfaces_invalid",
                "proof_reference_surfaces must be a list of objects",
            )
        ]
    observed_surfaces = tuple(
        (surface.get("surface_id"), surface.get("surface_type"), surface.get("state"))
        for surface in proof_reference_surfaces
    )
    if observed_surfaces != EXPECTED_SURFACES:
        findings.append(
            ProofReferenceFinding(
                "proof_reference_surface_inventory_invalid",
                "proof-reference surface inventory does not match the Foundation Mode proof-reference set",
            )
        )
    surface_ids = [surface.get("surface_id") for surface in proof_reference_surfaces]
    if len(set(surface_ids)) != len(surface_ids):
        findings.append(ProofReferenceFinding("proof_reference_surface_duplicate", "surface ids must be unique"))
    for surface in proof_reference_surfaces:
        surface_id = str(surface.get("surface_id", "<missing>"))
        if set(surface) != EXPECTED_SURFACE_KEYS:
            findings.append(
                ProofReferenceFinding(
                    "proof_reference_surface_keys_invalid",
                    f"{surface_id} surface keys must be: {', '.join(sorted(EXPECTED_SURFACE_KEYS))}",
                )
            )
        if surface.get("state") != "AwaitingEvidence":
            findings.append(
                ProofReferenceFinding(
                    "proof_reference_surface_state_invalid",
                    f"{surface_id} state must be AwaitingEvidence",
                )
            )
        if surface.get("evidence_ref") != "manual_preparation_pending":
            findings.append(
                ProofReferenceFinding(
                    "proof_reference_surface_evidence_invalid",
                    f"{surface_id} evidence_ref must stay manual_preparation_pending in the committed packet",
                )
            )
        if not isinstance(surface.get("public_safe_note"), str) or not surface["public_safe_note"].strip():
            findings.append(
                ProofReferenceFinding(
                    "proof_reference_surface_note_invalid",
                    f"{surface_id} public_safe_note must be a non-empty string",
                )
            )
    return findings


def validate_forbidden_value_patterns(payload: dict[str, Any]) -> list[ProofReferenceFinding]:
    """Return findings for private, proof, evidence, verification, test, or deployment values."""

    serialized_payload = json.dumps(payload, sort_keys=True)
    findings: list[ProofReferenceFinding] = []
    for rule_id, pattern in FORBIDDEN_VALUE_PATTERNS:
        if pattern.search(serialized_payload):
            findings.append(
                ProofReferenceFinding(
                    "proof_reference_forbidden_private_value_pattern",
                    f"proof-reference witness contains forbidden value pattern: {rule_id}",
                )
            )
    return findings


def validate_forbidden_promotion_patterns(payload: dict[str, Any]) -> list[ProofReferenceFinding]:
    """Return findings if the witness drifts into proof-readiness promotion phrases."""

    serialized_payload = json.dumps(payload, sort_keys=True)
    findings: list[ProofReferenceFinding] = []
    for rule_id, pattern in FORBIDDEN_PROMOTION_PATTERNS:
        if pattern.search(serialized_payload):
            findings.append(
                ProofReferenceFinding(
                    "proof_reference_forbidden_promotion_phrase",
                    f"proof-reference witness contains forbidden promotion pattern: {rule_id}",
                )
            )
    return findings


def validate_foundation_proof_reference_boundary(
    doc_path: Path = DEFAULT_DOC_PATH,
    packet_path: Path = DEFAULT_PACKET_PATH,
) -> list[ProofReferenceFinding]:
    """Validate the Foundation Mode proof-reference boundary artifacts."""

    doc_text = load_text(doc_path, "proof-reference boundary doc")
    packet_payload = load_json_object(packet_path, "proof-reference witness packet")
    return [
        *validate_doc_text(doc_text),
        *validate_packet(packet_payload),
    ]


def main(argv: list[str] | None = None) -> int:
    """Validate proof-reference artifacts and print deterministic status."""

    parser = argparse.ArgumentParser(description="Validate Foundation Mode proof-reference artifacts.")
    parser.add_argument("--doc", type=Path, default=DEFAULT_DOC_PATH)
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET_PATH)
    args = parser.parse_args(argv)

    try:
        findings = validate_foundation_proof_reference_boundary(args.doc, args.packet)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"[FAIL] foundation_proof_reference_load: {exc}", file=sys.stderr)
        print("STATUS: failed", file=sys.stderr)
        return 1

    if findings:
        for finding in findings:
            print(f"[FAIL] {finding.rule_id}: {finding.message}", file=sys.stderr)
        print("STATUS: failed", file=sys.stderr)
        return 1
    print("[PASS] foundation_proof_reference_doc")
    print("[PASS] foundation_proof_reference_witness")
    print("STATUS: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
