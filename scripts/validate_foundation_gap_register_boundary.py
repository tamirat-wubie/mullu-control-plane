#!/usr/bin/env python3
"""Validate the Foundation Mode gap-register boundary.

Purpose: keep gap-register drafting local and public-safe while register
completeness, gap closure, priority closure, owner assignment, remediation
readiness, roadmap commitment, evidence promotion, terminal closure, test,
refactor, implementation, publication, and deployment claims remain blocked.
Governance scope: Foundation Mode, gap-register surfaces, private-value
exclusion, and readiness blocking.
Dependencies: docs/FOUNDATION_GAP_REGISTER_BOUNDARY.md and
examples/foundation_gap_register_witness.awaiting_evidence.json.
Invariants:
  - Validation is read-only.
  - The witness records gap-register preparation only.
  - No closure, priority, owner, remediation, roadmap, evidence, terminal,
    test, implementation, publication, or deployment claim is allowed.
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
DEFAULT_DOC_PATH = REPO_ROOT / "docs" / "FOUNDATION_GAP_REGISTER_BOUNDARY.md"
DEFAULT_PACKET_PATH = REPO_ROOT / "examples" / "foundation_gap_register_witness.awaiting_evidence.json"

EXPECTED_WITNESS_ID = "foundation_gap_register_witness.awaiting_evidence.v1"
EXPECTED_BLOCKED_CLAIMS = (
    "gap-register completeness",
    "gap closure",
    "priority closure",
    "owner assignment",
    "remediation readiness",
    "roadmap commitment",
    "evidence promotion",
    "terminal closure",
    "test pass",
    "refactor approval",
    "implementation approval",
    "external publication",
    "deployment readiness",
)
EXPECTED_SURFACES = (
    ("architecture_gaps", "local_draft", "AwaitingEvidence"),
    ("module_gaps", "local_draft", "AwaitingEvidence"),
    ("interface_gaps", "local_draft", "AwaitingEvidence"),
    ("dependency_gaps", "local_draft", "AwaitingEvidence"),
    ("invariant_gaps", "local_draft", "AwaitingEvidence"),
    ("hazard_gaps", "local_draft", "AwaitingEvidence"),
    ("proof_reference_gaps", "local_draft", "AwaitingEvidence"),
    ("runtime_gaps", "local_draft", "AwaitingEvidence"),
    ("rollback_gaps", "local_draft", "AwaitingEvidence"),
    ("operator_gaps", "local_draft", "AwaitingEvidence"),
)
EXPECTED_ROOT_KEYS = {
    "blocked_claims",
    "deployment_allowed",
    "evidence_promotion_allowed",
    "external_publication_allowed",
    "gap_closure_claimed",
    "gap_owner_assigned",
    "gap_priority_closed_claimed",
    "gap_register_complete_claimed",
    "gap_register_surfaces",
    "implementation_approval_allowed",
    "next_action",
    "refactor_approval_allowed",
    "remediation_ready_claimed",
    "roadmap_commitment_allowed",
    "schema_version",
    "solver_outcome",
    "status",
    "terminal_closure_claimed",
    "test_pass_claimed",
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
    "Foundation Gap Register Boundary",
    "Witness packet: [`../examples/foundation_gap_register_witness.awaiting_evidence.json`]",
    "Rule: Gap-register preparation is a local planning boundary, not a",
    "No gap-register completeness, gap closure, priority closure, owner",
    "gap_register_boundary_state=AwaitingEvidence",
    "gap_register_complete_claimed=false",
    "gap_closure_claimed=false",
    "gap_priority_closed_claimed=false",
    "gap_owner_assigned=false",
    "remediation_ready_claimed=false",
    "roadmap_commitment_allowed=false",
    "implementation_approval_allowed=false",
    "deployment_allowed=false",
    "python scripts/validate_foundation_gap_register_boundary.py",
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
        "gap_owner_or_roadmap_assignment",
        re.compile(
            r"\b(?:gap|priority|owner|remediation|roadmap)[_ -]?"
            r"(?:id|ref|target|value|status|result|state|approval|date)?\s*=",
            re.IGNORECASE,
        ),
    ),
    (
        "proof_evidence_or_terminal_assignment",
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
    ("gap_register_complete", re.compile(r"\bgap\s+register\s+(?:is\s+)?complete\b", re.IGNORECASE)),
    ("gap_closed", re.compile(r"\bgap\s+(?:is\s+)?closed\b", re.IGNORECASE)),
    ("gap_resolved", re.compile(r"\bgap\s+(?:is\s+)?resolved\b", re.IGNORECASE)),
    ("priority_closed", re.compile(r"\bpriority\s+(?:is\s+)?closed\b", re.IGNORECASE)),
    ("roadmap_committed", re.compile(r"\broadmap\s+(?:is\s+)?committed\b", re.IGNORECASE)),
    ("owner_assigned", re.compile(r"\bowner\s+(?:is\s+)?assigned\b", re.IGNORECASE)),
    ("remediation_ready", re.compile(r"\bremediation\s+(?:is\s+)?ready\b", re.IGNORECASE)),
    ("evidence_promoted", re.compile(r"\bevidence\s+(?:is\s+)?promoted\b", re.IGNORECASE)),
    ("terminal_closure_claimed", re.compile(r"\bterminal\s+closure\s+(?:is\s+)?claimed\b", re.IGNORECASE)),
    ("test_passed", re.compile(r"\btests?\s+(?:have\s+)?passed\b", re.IGNORECASE)),
    ("refactor_approved", re.compile(r"\brefactor\s+(?:is\s+)?approved\b", re.IGNORECASE)),
    ("implementation_approved", re.compile(r"\bimplementation\s+(?:is\s+)?approved\b", re.IGNORECASE)),
    ("published_externally", re.compile(r"\bpublished\s+externally\b", re.IGNORECASE)),
    ("deployment_ready", re.compile(r"\bdeployment\s+(?:is\s+)?ready\b", re.IGNORECASE)),
)


@dataclass(frozen=True, slots=True)
class GapRegisterFinding:
    """One deterministic gap-register validation finding."""

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


def validate_doc_text(text: str) -> list[GapRegisterFinding]:
    """Return findings for missing gap-register documentation anchors."""

    findings: list[GapRegisterFinding] = []
    for phrase in REQUIRED_DOC_PHRASES:
        if phrase not in text:
            findings.append(
                GapRegisterFinding(
                    "foundation_gap_register_doc_phrase_missing",
                    f"gap-register boundary doc missing required phrase: {phrase}",
                )
            )
    return findings


def validate_packet(payload: dict[str, Any]) -> list[GapRegisterFinding]:
    """Return findings for gap-register witness drift."""

    findings: list[GapRegisterFinding] = []
    findings.extend(validate_root_contract(payload))
    findings.extend(validate_gap_register_surfaces(payload.get("gap_register_surfaces")))
    findings.extend(validate_forbidden_value_patterns(payload))
    findings.extend(validate_forbidden_promotion_patterns(payload))
    return findings


def validate_root_contract(payload: dict[str, Any]) -> list[GapRegisterFinding]:
    """Return findings for root-level gap-register witness drift."""

    findings: list[GapRegisterFinding] = []
    if set(payload) != EXPECTED_ROOT_KEYS:
        findings.append(
            GapRegisterFinding(
                "gap_register_root_keys_invalid",
                f"root keys must be: {', '.join(sorted(EXPECTED_ROOT_KEYS))}",
            )
        )
    expected_values = {
        "witness_id": EXPECTED_WITNESS_ID,
        "schema_version": 1,
        "status": "AwaitingEvidence",
        "solver_outcome": "AwaitingEvidence",
        "gap_register_complete_claimed": False,
        "gap_closure_claimed": False,
        "gap_priority_closed_claimed": False,
        "gap_owner_assigned": False,
        "remediation_ready_claimed": False,
        "roadmap_commitment_allowed": False,
        "evidence_promotion_allowed": False,
        "terminal_closure_claimed": False,
        "test_pass_claimed": False,
        "refactor_approval_allowed": False,
        "implementation_approval_allowed": False,
        "external_publication_allowed": False,
        "deployment_allowed": False,
    }
    for key, expected_value in expected_values.items():
        if payload.get(key) != expected_value:
            findings.append(
                GapRegisterFinding(
                    "gap_register_root_value_invalid",
                    f"{key} must be {expected_value!r}",
                )
            )
    if tuple(payload.get("blocked_claims") or ()) != EXPECTED_BLOCKED_CLAIMS:
        findings.append(
            GapRegisterFinding(
                "gap_register_blocked_claims_invalid",
                f"blocked_claims must be: {', '.join(EXPECTED_BLOCKED_CLAIMS)}",
            )
        )
    next_action = payload.get("next_action")
    if not isinstance(next_action, str) or "continue local gap register question drafting" not in next_action:
        findings.append(
            GapRegisterFinding(
                "gap_register_next_action_invalid",
                "next_action must preserve local gap register drafting without readiness promotion",
            )
        )
    return findings


def validate_gap_register_surfaces(gap_register_surfaces: object) -> list[GapRegisterFinding]:
    """Return findings for gap-register surface drift."""

    findings: list[GapRegisterFinding] = []
    if not isinstance(gap_register_surfaces, list) or not all(
        isinstance(surface, dict) for surface in gap_register_surfaces
    ):
        return [
            GapRegisterFinding(
                "gap_register_surfaces_invalid",
                "gap_register_surfaces must be a list of objects",
            )
        ]
    observed_surfaces = tuple(
        (surface.get("surface_id"), surface.get("surface_type"), surface.get("state"))
        for surface in gap_register_surfaces
    )
    if observed_surfaces != EXPECTED_SURFACES:
        findings.append(
            GapRegisterFinding(
                "gap_register_surface_inventory_invalid",
                "gap-register surface inventory does not match the Foundation Mode gap set",
            )
        )
    surface_ids = [surface.get("surface_id") for surface in gap_register_surfaces]
    if len(set(surface_ids)) != len(surface_ids):
        findings.append(GapRegisterFinding("gap_register_surface_duplicate", "surface ids must be unique"))
    for surface in gap_register_surfaces:
        surface_id = str(surface.get("surface_id", "<missing>"))
        if set(surface) != EXPECTED_SURFACE_KEYS:
            findings.append(
                GapRegisterFinding(
                    "gap_register_surface_keys_invalid",
                    f"{surface_id} surface keys must be: {', '.join(sorted(EXPECTED_SURFACE_KEYS))}",
                )
            )
        if surface.get("state") != "AwaitingEvidence":
            findings.append(
                GapRegisterFinding(
                    "gap_register_surface_state_invalid",
                    f"{surface_id} state must be AwaitingEvidence",
                )
            )
        if surface.get("evidence_ref") != "manual_preparation_pending":
            findings.append(
                GapRegisterFinding(
                    "gap_register_surface_evidence_invalid",
                    f"{surface_id} evidence_ref must stay manual_preparation_pending in the committed packet",
                )
            )
        if not isinstance(surface.get("public_safe_note"), str) or not surface["public_safe_note"].strip():
            findings.append(
                GapRegisterFinding(
                    "gap_register_surface_note_invalid",
                    f"{surface_id} public_safe_note must be a non-empty string",
                )
            )
    return findings


def validate_forbidden_value_patterns(payload: dict[str, Any]) -> list[GapRegisterFinding]:
    """Return findings for private, gap, roadmap, evidence, test, or deployment values."""

    serialized_payload = json.dumps(payload, sort_keys=True)
    findings: list[GapRegisterFinding] = []
    for rule_id, pattern in FORBIDDEN_VALUE_PATTERNS:
        if pattern.search(serialized_payload):
            findings.append(
                GapRegisterFinding(
                    "gap_register_forbidden_private_value_pattern",
                    f"gap-register witness contains forbidden value pattern: {rule_id}",
                )
            )
    return findings


def validate_forbidden_promotion_patterns(payload: dict[str, Any]) -> list[GapRegisterFinding]:
    """Return findings if the witness drifts into gap-closure promotion phrases."""

    serialized_payload = json.dumps(payload, sort_keys=True)
    findings: list[GapRegisterFinding] = []
    for rule_id, pattern in FORBIDDEN_PROMOTION_PATTERNS:
        if pattern.search(serialized_payload):
            findings.append(
                GapRegisterFinding(
                    "gap_register_forbidden_promotion_phrase",
                    f"gap-register witness contains forbidden promotion pattern: {rule_id}",
                )
            )
    return findings


def validate_foundation_gap_register_boundary(
    doc_path: Path = DEFAULT_DOC_PATH,
    packet_path: Path = DEFAULT_PACKET_PATH,
) -> list[GapRegisterFinding]:
    """Validate the Foundation Mode gap-register boundary artifacts."""

    doc_text = load_text(doc_path, "gap-register boundary doc")
    packet_payload = load_json_object(packet_path, "gap-register witness packet")
    return [
        *validate_doc_text(doc_text),
        *validate_packet(packet_payload),
    ]


def main(argv: list[str] | None = None) -> int:
    """Validate gap-register artifacts and print deterministic status."""

    parser = argparse.ArgumentParser(description="Validate Foundation Mode gap-register artifacts.")
    parser.add_argument("--doc", type=Path, default=DEFAULT_DOC_PATH)
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET_PATH)
    args = parser.parse_args(argv)

    try:
        findings = validate_foundation_gap_register_boundary(args.doc, args.packet)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"[FAIL] foundation_gap_register_load: {exc}", file=sys.stderr)
        print("STATUS: failed", file=sys.stderr)
        return 1

    if findings:
        for finding in findings:
            print(f"[FAIL] {finding.rule_id}: {finding.message}", file=sys.stderr)
        print("STATUS: failed", file=sys.stderr)
        return 1
    print("[PASS] foundation_gap_register_doc")
    print("[PASS] foundation_gap_register_witness")
    print("STATUS: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
