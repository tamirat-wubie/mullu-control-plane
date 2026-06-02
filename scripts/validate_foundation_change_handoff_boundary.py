#!/usr/bin/env python3
"""Validate the Foundation Mode change-handoff boundary.

Purpose: keep change-handoff drafting local and public-safe while review
completeness, scope closure, ownership, validation completeness, secret
clearance, staging, commit, branch, push, pull request, release, revert,
publication, and deployment claims remain blocked.
Governance scope: Foundation Mode, change-handoff surfaces, private-value
exclusion, source-control effect blocking, and readiness blocking.
Dependencies: docs/FOUNDATION_CHANGE_HANDOFF_BOUNDARY.md and
examples/foundation_change_handoff_witness.awaiting_evidence.json.
Invariants:
  - Validation is read-only.
  - The witness records handoff preparation only.
  - Staging, commit, push, pull request, release, revert, publication, and
    deployment remain blocked.
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
DEFAULT_DOC_PATH = REPO_ROOT / "docs" / "FOUNDATION_CHANGE_HANDOFF_BOUNDARY.md"
DEFAULT_PACKET_PATH = REPO_ROOT / "examples" / "foundation_change_handoff_witness.awaiting_evidence.json"

EXPECTED_WITNESS_ID = "foundation_change_handoff_witness.awaiting_evidence.v1"
EXPECTED_BLOCKED_CLAIMS = (
    "change-handoff completeness",
    "changed-file review completeness",
    "diff scope closure",
    "change ownership assignment",
    "validation completeness",
    "secret clearance",
    "staging approval",
    "commit approval",
    "branch switch approval",
    "push approval",
    "pull request approval",
    "release readiness",
    "revert approval",
    "source-control publication",
    "external publication",
    "deployment readiness",
)
EXPECTED_SURFACES = (
    ("change_family_summary_questions", "local_draft", "AwaitingEvidence"),
    ("constructive_delta_questions", "local_draft", "AwaitingEvidence"),
    ("fracture_delta_questions", "local_draft", "AwaitingEvidence"),
    ("unrelated_change_questions", "local_draft", "AwaitingEvidence"),
    ("user_change_preservation_questions", "local_draft", "AwaitingEvidence"),
    ("validation_evidence_questions", "local_draft", "AwaitingEvidence"),
    ("secret_drift_questions", "local_draft", "AwaitingEvidence"),
    ("rollback_revert_questions", "local_draft", "AwaitingEvidence"),
    ("next_action_questions", "local_draft", "AwaitingEvidence"),
    ("operator_handoff_questions", "local_draft", "AwaitingEvidence"),
)
EXPECTED_ROOT_KEYS = {
    "blocked_claims",
    "branch_switch_allowed",
    "change_handoff_complete_claimed",
    "change_handoff_surfaces",
    "change_ownership_assigned",
    "changed_file_review_complete_claimed",
    "commit_allowed",
    "deployment_allowed",
    "diff_scope_closed_claimed",
    "external_publication_allowed",
    "next_action",
    "pull_request_allowed",
    "push_allowed",
    "release_allowed",
    "revert_allowed",
    "schema_version",
    "secret_clearance_claimed",
    "solver_outcome",
    "source_control_publication_allowed",
    "staging_allowed",
    "status",
    "validation_complete_claimed",
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
    "Foundation Change Handoff Boundary",
    "Witness packet: [`../examples/foundation_change_handoff_witness.awaiting_evidence.json`]",
    "Rule: Change-handoff preparation is a local planning boundary, not a",
    "No change-handoff completeness, changed-file review completeness, diff scope",
    "change_handoff_boundary_state=AwaitingEvidence",
    "change_handoff_complete_claimed=false",
    "changed_file_review_complete_claimed=false",
    "diff_scope_closed_claimed=false",
    "change_ownership_assigned=false",
    "validation_complete_claimed=false",
    "secret_clearance_claimed=false",
    "staging_allowed=false",
    "commit_allowed=false",
    "push_allowed=false",
    "pull_request_allowed=false",
    "source_control_publication_allowed=false",
    "deployment_allowed=false",
    "python scripts/validate_foundation_change_handoff_boundary.py",
)
FORBIDDEN_VALUE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("url_value", re.compile(r"https?://", re.IGNORECASE)),
    ("email_value", re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)),
    ("private_path", re.compile(r"\b[A-Za-z]:[\\/]|\\\\", re.IGNORECASE)),
    (
        "source_control_assignment",
        re.compile(
            r"\b(?:file|path|diff|stage|staging|commit|branch|push|pull[_ -]?request|release|revert)[_ -]?"
            r"(?:id|ref|target|value|status|result|state|approval)?\s*=",
            re.IGNORECASE,
        ),
    ),
    (
        "validation_assignment",
        re.compile(r"\b(?:test|suite|assertion|validator)[_ -]?(?:pass|status|result|value)?\s*=", re.IGNORECASE),
    ),
    (
        "secret_assignment",
        re.compile(r"\b(?:password|secret|token|api[_ -]?key|credential|client[_ -]?secret)\s*=", re.IGNORECASE),
    ),
    ("private_key_material", re.compile(r"BEGIN [A-Z ]*PRIVATE KEY")),
    (
        "customer_assignment",
        re.compile(
            r"\b(?:customer|pilot|participant|user)[_ -]?"
            r"(?:id|name|email|ref|target|value)?\s*=",
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
    ("handoff_complete", re.compile(r"\bchange\s+handoff\s+(?:is\s+)?complete\b", re.IGNORECASE)),
    ("review_complete", re.compile(r"\bchanged[- ]file\s+review\s+(?:is\s+)?complete\b", re.IGNORECASE)),
    ("diff_scope_closed", re.compile(r"\bdiff\s+scope\s+(?:is\s+)?closed\b", re.IGNORECASE)),
    ("ownership_assigned", re.compile(r"\bownership\s+(?:is\s+)?assigned\b", re.IGNORECASE)),
    ("validation_complete", re.compile(r"\bvalidation\s+(?:is\s+)?complete\b", re.IGNORECASE)),
    ("secret_clear", re.compile(r"\bsecrets?\s+(?:are\s+)?clear\b", re.IGNORECASE)),
    ("staging_approved", re.compile(r"\bstaging\s+(?:is\s+)?approved\b", re.IGNORECASE)),
    ("commit_approved", re.compile(r"\bcommit\s+(?:is\s+)?approved\b", re.IGNORECASE)),
    ("push_approved", re.compile(r"\bpush\s+(?:is\s+)?approved\b", re.IGNORECASE)),
    ("pull_request_approved", re.compile(r"\bpull\s+request\s+(?:is\s+)?approved\b", re.IGNORECASE)),
    ("release_ready", re.compile(r"\brelease\s+(?:is\s+)?ready\b", re.IGNORECASE)),
    ("revert_approved", re.compile(r"\brevert\s+(?:is\s+)?approved\b", re.IGNORECASE)),
    ("deployment_ready", re.compile(r"\bdeployment\s+(?:is\s+)?ready\b", re.IGNORECASE)),
)


@dataclass(frozen=True, slots=True)
class ChangeHandoffFinding:
    """One deterministic change-handoff validation finding."""

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


def validate_doc_text(text: str) -> list[ChangeHandoffFinding]:
    """Return findings for missing change-handoff documentation anchors."""

    findings: list[ChangeHandoffFinding] = []
    for phrase in REQUIRED_DOC_PHRASES:
        if phrase not in text:
            findings.append(
                ChangeHandoffFinding(
                    "foundation_change_handoff_doc_phrase_missing",
                    f"change-handoff boundary doc missing required phrase: {phrase}",
                )
            )
    return findings


def validate_packet(payload: dict[str, Any]) -> list[ChangeHandoffFinding]:
    """Return findings for change-handoff witness drift."""

    findings: list[ChangeHandoffFinding] = []
    findings.extend(validate_root_contract(payload))
    findings.extend(validate_change_handoff_surfaces(payload.get("change_handoff_surfaces")))
    findings.extend(validate_forbidden_value_patterns(payload))
    findings.extend(validate_forbidden_promotion_patterns(payload))
    return findings


def validate_root_contract(payload: dict[str, Any]) -> list[ChangeHandoffFinding]:
    """Return findings for root-level change-handoff witness drift."""

    findings: list[ChangeHandoffFinding] = []
    if set(payload) != EXPECTED_ROOT_KEYS:
        findings.append(
            ChangeHandoffFinding(
                "change_handoff_root_keys_invalid",
                f"root keys must be: {', '.join(sorted(EXPECTED_ROOT_KEYS))}",
            )
        )
    expected_values = {
        "witness_id": EXPECTED_WITNESS_ID,
        "schema_version": 1,
        "status": "AwaitingEvidence",
        "solver_outcome": "AwaitingEvidence",
        "change_handoff_complete_claimed": False,
        "changed_file_review_complete_claimed": False,
        "diff_scope_closed_claimed": False,
        "change_ownership_assigned": False,
        "validation_complete_claimed": False,
        "secret_clearance_claimed": False,
        "staging_allowed": False,
        "commit_allowed": False,
        "branch_switch_allowed": False,
        "push_allowed": False,
        "pull_request_allowed": False,
        "release_allowed": False,
        "revert_allowed": False,
        "source_control_publication_allowed": False,
        "external_publication_allowed": False,
        "deployment_allowed": False,
    }
    for key, expected_value in expected_values.items():
        if payload.get(key) != expected_value:
            findings.append(
                ChangeHandoffFinding(
                    "change_handoff_root_value_invalid",
                    f"{key} must be {expected_value!r}",
                )
            )
    if tuple(payload.get("blocked_claims") or ()) != EXPECTED_BLOCKED_CLAIMS:
        findings.append(
            ChangeHandoffFinding(
                "change_handoff_blocked_claims_invalid",
                f"blocked_claims must be: {', '.join(EXPECTED_BLOCKED_CLAIMS)}",
            )
        )
    next_action = payload.get("next_action")
    if not isinstance(next_action, str) or "continue local change handoff question drafting" not in next_action:
        findings.append(
            ChangeHandoffFinding(
                "change_handoff_next_action_invalid",
                "next_action must preserve local handoff drafting without Git effect promotion",
            )
        )
    return findings


def validate_change_handoff_surfaces(change_handoff_surfaces: object) -> list[ChangeHandoffFinding]:
    """Return findings for change-handoff surface drift."""

    findings: list[ChangeHandoffFinding] = []
    if not isinstance(change_handoff_surfaces, list) or not all(
        isinstance(surface, dict) for surface in change_handoff_surfaces
    ):
        return [
            ChangeHandoffFinding(
                "change_handoff_surfaces_invalid",
                "change_handoff_surfaces must be a list of objects",
            )
        ]
    observed_surfaces = tuple(
        (surface.get("surface_id"), surface.get("surface_type"), surface.get("state"))
        for surface in change_handoff_surfaces
    )
    if observed_surfaces != EXPECTED_SURFACES:
        findings.append(
            ChangeHandoffFinding(
                "change_handoff_surface_inventory_invalid",
                "change-handoff surface inventory does not match the Foundation Mode change-handoff set",
            )
        )
    surface_ids = [surface.get("surface_id") for surface in change_handoff_surfaces]
    if len(set(surface_ids)) != len(surface_ids):
        findings.append(ChangeHandoffFinding("change_handoff_surface_duplicate", "surface ids must be unique"))
    for surface in change_handoff_surfaces:
        surface_id = str(surface.get("surface_id", "<missing>"))
        if set(surface) != EXPECTED_SURFACE_KEYS:
            findings.append(
                ChangeHandoffFinding(
                    "change_handoff_surface_keys_invalid",
                    f"{surface_id} surface keys must be: {', '.join(sorted(EXPECTED_SURFACE_KEYS))}",
                )
            )
        if surface.get("state") != "AwaitingEvidence":
            findings.append(
                ChangeHandoffFinding(
                    "change_handoff_surface_state_invalid",
                    f"{surface_id} state must be AwaitingEvidence",
                )
            )
        if surface.get("evidence_ref") != "manual_preparation_pending":
            findings.append(
                ChangeHandoffFinding(
                    "change_handoff_surface_evidence_invalid",
                    f"{surface_id} evidence_ref must stay manual_preparation_pending in the committed packet",
                )
            )
        if not isinstance(surface.get("public_safe_note"), str) or not surface["public_safe_note"].strip():
            findings.append(
                ChangeHandoffFinding(
                    "change_handoff_surface_note_invalid",
                    f"{surface_id} public_safe_note must be a non-empty string",
                )
            )
    return findings


def validate_forbidden_value_patterns(payload: dict[str, Any]) -> list[ChangeHandoffFinding]:
    """Return findings for private, source-control, or deployment values."""

    serialized_payload = json.dumps(payload, sort_keys=True)
    findings: list[ChangeHandoffFinding] = []
    for rule_id, pattern in FORBIDDEN_VALUE_PATTERNS:
        if pattern.search(serialized_payload):
            findings.append(
                ChangeHandoffFinding(
                    "change_handoff_forbidden_private_value_pattern",
                    f"change-handoff witness contains forbidden value pattern: {rule_id}",
                )
            )
    return findings


def validate_forbidden_promotion_patterns(payload: dict[str, Any]) -> list[ChangeHandoffFinding]:
    """Return findings if the witness drifts into Git-effect promotion phrases."""

    serialized_payload = json.dumps(payload, sort_keys=True)
    findings: list[ChangeHandoffFinding] = []
    for rule_id, pattern in FORBIDDEN_PROMOTION_PATTERNS:
        if pattern.search(serialized_payload):
            findings.append(
                ChangeHandoffFinding(
                    "change_handoff_forbidden_promotion_phrase",
                    f"change-handoff witness contains forbidden promotion pattern: {rule_id}",
                )
            )
    return findings


def validate_foundation_change_handoff_boundary(
    doc_path: Path = DEFAULT_DOC_PATH,
    packet_path: Path = DEFAULT_PACKET_PATH,
) -> list[ChangeHandoffFinding]:
    """Validate the Foundation Mode change-handoff boundary artifacts."""

    doc_text = load_text(doc_path, "change-handoff boundary doc")
    packet_payload = load_json_object(packet_path, "change-handoff witness packet")
    return [
        *validate_doc_text(doc_text),
        *validate_packet(packet_payload),
    ]


def main(argv: list[str] | None = None) -> int:
    """Validate change-handoff artifacts and print deterministic status."""

    parser = argparse.ArgumentParser(description="Validate Foundation Mode change-handoff artifacts.")
    parser.add_argument("--doc", type=Path, default=DEFAULT_DOC_PATH)
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET_PATH)
    args = parser.parse_args(argv)

    try:
        findings = validate_foundation_change_handoff_boundary(args.doc, args.packet)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"[FAIL] foundation_change_handoff_load: {exc}", file=sys.stderr)
        print("STATUS: failed", file=sys.stderr)
        return 1

    if findings:
        for finding in findings:
            print(f"[FAIL] {finding.rule_id}: {finding.message}", file=sys.stderr)
        print("STATUS: failed", file=sys.stderr)
        return 1
    print("[PASS] foundation_change_handoff_doc")
    print("[PASS] foundation_change_handoff_witness")
    print("STATUS: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
