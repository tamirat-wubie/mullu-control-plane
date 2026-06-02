#!/usr/bin/env python3
"""Validate the Foundation Mode diff-review boundary.

Purpose: keep diff-review drafting local and public-safe while review
completeness, scope closure, ownership assignment, staging, commit, branch,
push, pull request, release, revert, test, publication, and deployment claims
remain blocked.
Governance scope: Foundation Mode, diff-review surfaces, private-value
exclusion, source-control effect blocking, and readiness blocking.
Dependencies: docs/FOUNDATION_DIFF_REVIEW_BOUNDARY.md and
examples/foundation_diff_review_witness.awaiting_evidence.json.
Invariants:
  - Validation is read-only.
  - The witness records diff-review preparation only.
  - No staging, commit, branch switch, push, pull request, release, revert,
    publication, or deployment claim is allowed.
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
DEFAULT_DOC_PATH = REPO_ROOT / "docs" / "FOUNDATION_DIFF_REVIEW_BOUNDARY.md"
DEFAULT_PACKET_PATH = REPO_ROOT / "examples" / "foundation_diff_review_witness.awaiting_evidence.json"

EXPECTED_WITNESS_ID = "foundation_diff_review_witness.awaiting_evidence.v1"
EXPECTED_BLOCKED_CLAIMS = (
    "diff-review completeness",
    "diff scope closure",
    "diff ownership assignment",
    "staging approval",
    "commit approval",
    "branch switch approval",
    "push approval",
    "pull request approval",
    "release readiness",
    "revert approval",
    "test pass",
    "secret publication",
    "source-control publication",
    "external publication",
    "deployment readiness",
)
EXPECTED_SURFACES = (
    ("changed_file_inventory_questions", "local_draft", "AwaitingEvidence"),
    ("untracked_file_inventory_questions", "local_draft", "AwaitingEvidence"),
    ("unrelated_change_classification", "local_draft", "AwaitingEvidence"),
    ("agent_change_scope_questions", "local_draft", "AwaitingEvidence"),
    ("user_change_preservation_questions", "local_draft", "AwaitingEvidence"),
    ("validation_summary_questions", "local_draft", "AwaitingEvidence"),
    ("secret_drift_questions", "local_draft", "AwaitingEvidence"),
    ("staging_commit_questions", "local_draft", "AwaitingEvidence"),
    ("rollback_revert_questions", "local_draft", "AwaitingEvidence"),
    ("handoff_summary_questions", "local_draft", "AwaitingEvidence"),
)
EXPECTED_ROOT_KEYS = {
    "blocked_claims",
    "branch_switch_allowed",
    "commit_allowed",
    "deployment_allowed",
    "diff_ownership_assigned",
    "diff_review_complete_claimed",
    "diff_review_surfaces",
    "diff_scope_closed_claimed",
    "external_publication_allowed",
    "next_action",
    "pull_request_allowed",
    "push_allowed",
    "release_allowed",
    "revert_allowed",
    "schema_version",
    "secret_publication_allowed",
    "solver_outcome",
    "source_control_publication_allowed",
    "staging_allowed",
    "status",
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
    "Foundation Diff Review Boundary",
    "Witness packet: [`../examples/foundation_diff_review_witness.awaiting_evidence.json`]",
    "Rule: Diff-review preparation is a local planning boundary, not a",
    "No diff-review completeness, diff scope closure, ownership assignment, staging",
    "diff_review_boundary_state=AwaitingEvidence",
    "diff_review_complete_claimed=false",
    "diff_scope_closed_claimed=false",
    "diff_ownership_assigned=false",
    "staging_allowed=false",
    "commit_allowed=false",
    "push_allowed=false",
    "pull_request_allowed=false",
    "source_control_publication_allowed=false",
    "deployment_allowed=false",
    "python scripts/validate_foundation_diff_review_boundary.py",
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
        "diff_or_source_control_assignment",
        re.compile(
            r"\b(?:diff|file|path|stage|staging|commit|branch|push|pull[_ -]?request|release|revert)[_ -]?"
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
        "publication_or_deployment_assignment",
        re.compile(
            r"\b(?:publish|publication|deploy|deployment|production)[_ -]?"
            r"(?:id|url|ref|target|value|status)?\s*=",
            re.IGNORECASE,
        ),
    ),
)
FORBIDDEN_PROMOTION_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("diff_review_complete", re.compile(r"\bdiff\s+review\s+(?:is\s+)?complete\b", re.IGNORECASE)),
    ("diff_scope_closed", re.compile(r"\bdiff\s+scope\s+(?:is\s+)?closed\b", re.IGNORECASE)),
    ("owner_assigned", re.compile(r"\bowner\s+(?:is\s+)?assigned\b", re.IGNORECASE)),
    ("staging_approved", re.compile(r"\bstaging\s+(?:is\s+)?approved\b", re.IGNORECASE)),
    ("commit_approved", re.compile(r"\bcommit\s+(?:is\s+)?approved\b", re.IGNORECASE)),
    ("branch_switch_approved", re.compile(r"\bbranch\s+switch\s+(?:is\s+)?approved\b", re.IGNORECASE)),
    ("push_approved", re.compile(r"\bpush\s+(?:is\s+)?approved\b", re.IGNORECASE)),
    ("pull_request_approved", re.compile(r"\bpull\s+request\s+(?:is\s+)?approved\b", re.IGNORECASE)),
    ("release_ready", re.compile(r"\brelease\s+(?:is\s+)?ready\b", re.IGNORECASE)),
    ("revert_approved", re.compile(r"\brevert\s+(?:is\s+)?approved\b", re.IGNORECASE)),
    ("test_passed", re.compile(r"\btests?\s+(?:have\s+)?passed\b", re.IGNORECASE)),
    ("source_control_published", re.compile(r"\bsource\s+control\s+(?:is\s+)?published\b", re.IGNORECASE)),
    ("published_externally", re.compile(r"\bpublished\s+externally\b", re.IGNORECASE)),
    ("deployment_ready", re.compile(r"\bdeployment\s+(?:is\s+)?ready\b", re.IGNORECASE)),
)


@dataclass(frozen=True, slots=True)
class DiffReviewFinding:
    """One deterministic diff-review validation finding."""

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


def validate_doc_text(text: str) -> list[DiffReviewFinding]:
    """Return findings for missing diff-review documentation anchors."""

    findings: list[DiffReviewFinding] = []
    for phrase in REQUIRED_DOC_PHRASES:
        if phrase not in text:
            findings.append(
                DiffReviewFinding(
                    "foundation_diff_review_doc_phrase_missing",
                    f"diff-review boundary doc missing required phrase: {phrase}",
                )
            )
    return findings


def validate_packet(payload: dict[str, Any]) -> list[DiffReviewFinding]:
    """Return findings for diff-review witness drift."""

    findings: list[DiffReviewFinding] = []
    findings.extend(validate_root_contract(payload))
    findings.extend(validate_diff_review_surfaces(payload.get("diff_review_surfaces")))
    findings.extend(validate_forbidden_value_patterns(payload))
    findings.extend(validate_forbidden_promotion_patterns(payload))
    return findings


def validate_root_contract(payload: dict[str, Any]) -> list[DiffReviewFinding]:
    """Return findings for root-level diff-review witness drift."""

    findings: list[DiffReviewFinding] = []
    if set(payload) != EXPECTED_ROOT_KEYS:
        findings.append(
            DiffReviewFinding(
                "diff_review_root_keys_invalid",
                f"root keys must be: {', '.join(sorted(EXPECTED_ROOT_KEYS))}",
            )
        )
    expected_values = {
        "witness_id": EXPECTED_WITNESS_ID,
        "schema_version": 1,
        "status": "AwaitingEvidence",
        "solver_outcome": "AwaitingEvidence",
        "diff_review_complete_claimed": False,
        "diff_scope_closed_claimed": False,
        "diff_ownership_assigned": False,
        "staging_allowed": False,
        "commit_allowed": False,
        "branch_switch_allowed": False,
        "push_allowed": False,
        "pull_request_allowed": False,
        "release_allowed": False,
        "revert_allowed": False,
        "test_pass_claimed": False,
        "secret_publication_allowed": False,
        "source_control_publication_allowed": False,
        "external_publication_allowed": False,
        "deployment_allowed": False,
    }
    for key, expected_value in expected_values.items():
        if payload.get(key) != expected_value:
            findings.append(
                DiffReviewFinding(
                    "diff_review_root_value_invalid",
                    f"{key} must be {expected_value!r}",
                )
            )
    if tuple(payload.get("blocked_claims") or ()) != EXPECTED_BLOCKED_CLAIMS:
        findings.append(
            DiffReviewFinding(
                "diff_review_blocked_claims_invalid",
                f"blocked_claims must be: {', '.join(EXPECTED_BLOCKED_CLAIMS)}",
            )
        )
    next_action = payload.get("next_action")
    if not isinstance(next_action, str) or "continue local diff review question drafting" not in next_action:
        findings.append(
            DiffReviewFinding(
                "diff_review_next_action_invalid",
                "next_action must preserve local diff review drafting without Git effect promotion",
            )
        )
    return findings


def validate_diff_review_surfaces(diff_review_surfaces: object) -> list[DiffReviewFinding]:
    """Return findings for diff-review surface drift."""

    findings: list[DiffReviewFinding] = []
    if not isinstance(diff_review_surfaces, list) or not all(
        isinstance(surface, dict) for surface in diff_review_surfaces
    ):
        return [
            DiffReviewFinding(
                "diff_review_surfaces_invalid",
                "diff_review_surfaces must be a list of objects",
            )
        ]
    observed_surfaces = tuple(
        (surface.get("surface_id"), surface.get("surface_type"), surface.get("state"))
        for surface in diff_review_surfaces
    )
    if observed_surfaces != EXPECTED_SURFACES:
        findings.append(
            DiffReviewFinding(
                "diff_review_surface_inventory_invalid",
                "diff-review surface inventory does not match the Foundation Mode diff-review set",
            )
        )
    surface_ids = [surface.get("surface_id") for surface in diff_review_surfaces]
    if len(set(surface_ids)) != len(surface_ids):
        findings.append(DiffReviewFinding("diff_review_surface_duplicate", "surface ids must be unique"))
    for surface in diff_review_surfaces:
        surface_id = str(surface.get("surface_id", "<missing>"))
        if set(surface) != EXPECTED_SURFACE_KEYS:
            findings.append(
                DiffReviewFinding(
                    "diff_review_surface_keys_invalid",
                    f"{surface_id} surface keys must be: {', '.join(sorted(EXPECTED_SURFACE_KEYS))}",
                )
            )
        if surface.get("state") != "AwaitingEvidence":
            findings.append(
                DiffReviewFinding(
                    "diff_review_surface_state_invalid",
                    f"{surface_id} state must be AwaitingEvidence",
                )
            )
        if surface.get("evidence_ref") != "manual_preparation_pending":
            findings.append(
                DiffReviewFinding(
                    "diff_review_surface_evidence_invalid",
                    f"{surface_id} evidence_ref must stay manual_preparation_pending in the committed packet",
                )
            )
        if not isinstance(surface.get("public_safe_note"), str) or not surface["public_safe_note"].strip():
            findings.append(
                DiffReviewFinding(
                    "diff_review_surface_note_invalid",
                    f"{surface_id} public_safe_note must be a non-empty string",
                )
            )
    return findings


def validate_forbidden_value_patterns(payload: dict[str, Any]) -> list[DiffReviewFinding]:
    """Return findings for private, diff, source-control, test, or deployment values."""

    serialized_payload = json.dumps(payload, sort_keys=True)
    findings: list[DiffReviewFinding] = []
    for rule_id, pattern in FORBIDDEN_VALUE_PATTERNS:
        if pattern.search(serialized_payload):
            findings.append(
                DiffReviewFinding(
                    "diff_review_forbidden_private_value_pattern",
                    f"diff-review witness contains forbidden value pattern: {rule_id}",
                )
            )
    return findings


def validate_forbidden_promotion_patterns(payload: dict[str, Any]) -> list[DiffReviewFinding]:
    """Return findings if the witness drifts into Git-effect promotion phrases."""

    serialized_payload = json.dumps(payload, sort_keys=True)
    findings: list[DiffReviewFinding] = []
    for rule_id, pattern in FORBIDDEN_PROMOTION_PATTERNS:
        if pattern.search(serialized_payload):
            findings.append(
                DiffReviewFinding(
                    "diff_review_forbidden_promotion_phrase",
                    f"diff-review witness contains forbidden promotion pattern: {rule_id}",
                )
            )
    return findings


def validate_foundation_diff_review_boundary(
    doc_path: Path = DEFAULT_DOC_PATH,
    packet_path: Path = DEFAULT_PACKET_PATH,
) -> list[DiffReviewFinding]:
    """Validate the Foundation Mode diff-review boundary artifacts."""

    doc_text = load_text(doc_path, "diff-review boundary doc")
    packet_payload = load_json_object(packet_path, "diff-review witness packet")
    return [
        *validate_doc_text(doc_text),
        *validate_packet(packet_payload),
    ]


def main(argv: list[str] | None = None) -> int:
    """Validate diff-review artifacts and print deterministic status."""

    parser = argparse.ArgumentParser(description="Validate Foundation Mode diff-review artifacts.")
    parser.add_argument("--doc", type=Path, default=DEFAULT_DOC_PATH)
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET_PATH)
    args = parser.parse_args(argv)

    try:
        findings = validate_foundation_diff_review_boundary(args.doc, args.packet)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"[FAIL] foundation_diff_review_load: {exc}", file=sys.stderr)
        print("STATUS: failed", file=sys.stderr)
        return 1

    if findings:
        for finding in findings:
            print(f"[FAIL] {finding.rule_id}: {finding.message}", file=sys.stderr)
        print("STATUS: failed", file=sys.stderr)
        return 1
    print("[PASS] foundation_diff_review_doc")
    print("[PASS] foundation_diff_review_witness")
    print("STATUS: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
