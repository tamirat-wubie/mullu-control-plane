#!/usr/bin/env python3
"""Validate the Foundation Mode local release-packet rehearsal boundary.

Purpose: keep one local release-packet rehearsal public-safe while release
publication, release readiness, tag creation, GitHub release creation,
changelog publication, artifact publication, source-control publication,
external publication, deployment, customer access, legal clearance, company
formation, patent action, money movement, secret publication, and private-value
recording remain blocked.
Governance scope: Foundation Mode, local release-packet rehearsal, evidence
labels, validator summary labels, test summary labels, diff hygiene labels,
risk and rollback labels, public-claim review labels, version-label questions,
operator review gates, stop-rule rehearsal, private-value exclusion, and
external-action blocking.
Dependencies:
docs/FOUNDATION_LOCAL_RELEASE_PACKET_REHEARSAL_BOUNDARY.md and
examples/foundation_local_release_packet_rehearsal_witness.awaiting_evidence.json.
Invariants:
  - The witness records public-safe release-packet rehearsal labels only.
  - Every release-packet rehearsal surface remains AwaitingEvidence.
  - No release, publication, deployment, customer, legal, company, patent,
    money, secret, or private-value claim is accepted.
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
DEFAULT_DOC_PATH = REPO_ROOT / "docs" / "FOUNDATION_LOCAL_RELEASE_PACKET_REHEARSAL_BOUNDARY.md"
DEFAULT_PACKET_PATH = (
    REPO_ROOT / "examples" / "foundation_local_release_packet_rehearsal_witness.awaiting_evidence.json"
)

REQUIRED_ROOT_KEYS = (
    "artifact_publication_allowed",
    "blocked_claims",
    "changelog_publication_allowed",
    "company_formation_claimed",
    "customer_access_allowed",
    "deferral_labels",
    "deployment_allowed",
    "external_publication_allowed",
    "github_release_allowed",
    "legal_clearance_claimed",
    "money_movement_allowed",
    "next_action",
    "patent_action_allowed",
    "private_value_recording_allowed",
    "release_packet_published",
    "release_readiness_claimed",
    "schema_version",
    "secret_publication_allowed",
    "solver_outcome",
    "source_control_publication_allowed",
    "status",
    "surfaces",
    "tag_creation_allowed",
    "version_label_selected",
    "witness_id",
)
EXPECTED_ROOT_VALUES = {
    "schema_version": "foundation.local_release_packet_rehearsal.v1",
    "witness_id": "foundation_local_release_packet_rehearsal_witness.awaiting_evidence.v1",
    "status": "AwaitingEvidence",
    "solver_outcome": "AwaitingEvidence",
}
FALSE_FLAGS = (
    "artifact_publication_allowed",
    "changelog_publication_allowed",
    "company_formation_claimed",
    "customer_access_allowed",
    "deployment_allowed",
    "external_publication_allowed",
    "github_release_allowed",
    "legal_clearance_claimed",
    "money_movement_allowed",
    "patent_action_allowed",
    "private_value_recording_allowed",
    "release_packet_published",
    "release_readiness_claimed",
    "secret_publication_allowed",
    "source_control_publication_allowed",
    "tag_creation_allowed",
    "version_label_selected",
)
DEFERRAL_LABELS = (
    "change_family_inventory_rehearsal",
    "evidence_reference_bundle_rehearsal",
    "validator_result_summary_rehearsal",
    "test_result_summary_rehearsal",
    "diff_hygiene_summary_rehearsal",
    "risk_and_rollback_note_rehearsal",
    "public_claim_review_rehearsal",
    "version_label_rehearsal",
    "operator_review_gate_rehearsal",
    "stop_rule_rehearsal",
)
BLOCKED_CLAIMS = (
    "release packet publication",
    "release readiness",
    "version label selection",
    "tag creation",
    "GitHub release creation",
    "changelog publication",
    "artifact publication",
    "source-control publication",
    "external publication",
    "deployment readiness",
    "customer access",
    "legal clearance",
    "company formation",
    "patent action",
    "money movement",
    "secret publication",
    "private value recording",
)
SURFACE_NOTES_BY_ID = {
    "change_family_inventory_rehearsal": "Change-family inventory rehearsal only; release scope closure is not claimed.",
    "evidence_reference_bundle_rehearsal": "Evidence-reference bundle rehearsal only; receipt contents, private paths, refs, and artifacts are not copied.",
    "validator_result_summary_rehearsal": "Validator-result summary rehearsal only; full preflight closure and CI parity are not claimed.",
    "test_result_summary_rehearsal": "Test-result summary rehearsal only; complete coverage and flake-free status are not claimed.",
    "diff_hygiene_summary_rehearsal": "Diff-hygiene summary rehearsal only; staging, commit, push, tag creation, and publication are not approved.",
    "risk_and_rollback_note_rehearsal": "Risk and rollback note rehearsal only; rollback execution and release execution are not approved.",
    "public_claim_review_rehearsal": "Public-claim review rehearsal only; public claims and customer access are not approved.",
    "version_label_rehearsal": "Version-label rehearsal only; no real version, tag, or release id is selected.",
    "operator_review_gate_rehearsal": "Operator-review gate rehearsal only; approval and readiness are not claimed.",
    "stop_rule_rehearsal": "Stop-rule rehearsal only; publication, deployment, money movement, legal or company action, patent action, customer access, source control, and secret handling are not approved.",
}
SURFACE_TYPES_BY_ID = {
    "change_family_inventory_rehearsal": "local_change_family_label",
    "evidence_reference_bundle_rehearsal": "local_evidence_bundle_label",
    "validator_result_summary_rehearsal": "local_validator_summary_label",
    "test_result_summary_rehearsal": "local_test_summary_label",
    "diff_hygiene_summary_rehearsal": "local_diff_hygiene_label",
    "risk_and_rollback_note_rehearsal": "local_risk_rollback_label",
    "public_claim_review_rehearsal": "local_public_claim_label",
    "version_label_rehearsal": "local_version_label",
    "operator_review_gate_rehearsal": "local_operator_review_label",
    "stop_rule_rehearsal": "local_stop_rule_label",
}
REQUIRED_DOC_PHRASES = (
    "Foundation Local Release Packet Rehearsal Boundary",
    "Witness packet: [`../examples/foundation_local_release_packet_rehearsal_witness.awaiting_evidence.json`]",
    "Rule: Local release-packet rehearsal is a private Foundation Mode planning",
    "No release-packet publication, release-readiness claim, tag creation, GitHub",
    "local_release_packet_rehearsal_boundary_state=AwaitingEvidence",
    "release_packet_published=false",
    "release_readiness_claimed=false",
    "version_label_selected=false",
    "tag_creation_allowed=false",
    "github_release_allowed=false",
    "changelog_publication_allowed=false",
    "artifact_publication_allowed=false",
    "source_control_publication_allowed=false",
    "external_publication_allowed=false",
    "deployment_allowed=false",
    "customer_access_allowed=false",
    "legal_clearance_claimed=false",
    "company_formation_claimed=false",
    "patent_action_allowed=false",
    "money_movement_allowed=false",
    "secret_publication_allowed=false",
    "private_value_recording_allowed=false",
    "python scripts/validate_foundation_local_release_packet_rehearsal_boundary.py",
)
FORBIDDEN_VALUE_PATTERNS = (
    ("url", re.compile(r"\b(?:https?://|www\.)\S+", re.IGNORECASE)),
    ("email", re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)),
    ("private_path", re.compile(r"(?:[A-Za-z]:\\|/home/|/Users/|\\\\[^\\]+\\)", re.IGNORECASE)),
    ("commit_sha", re.compile(r"\b[0-9a-f]{12,40}\b", re.IGNORECASE)),
    ("tag_value", re.compile(r"\bv?\d+\.\d+(?:\.\d+)?(?:[-+][A-Za-z0-9_.-]+)?\b")),
    ("secret_material", re.compile(r"\b(?:sk|pk|ghp|github_pat|AKIA)[A-Za-z0-9_-]{8,}\b")),
    ("private_key_material", re.compile(r"BEGIN [A-Z ]*PRIVATE KEY")),
    (
        "assignment_shape",
        re.compile(
            r"\b(?:branch|commit|tag|release|artifact|url|endpoint|account|provider|customer|"
            r"payment|invoice|legal|company|patent|tax|secret|token|key|deploy|deployment|"
            r"production)\w*\s*=",
            re.IGNORECASE,
        ),
    ),
)
FORBIDDEN_PROMOTION_PATTERNS = (
    ("release_packet_published", re.compile(r"\brelease\s+packet\s+(?:is\s+)?published\b", re.IGNORECASE)),
    ("release_ready", re.compile(r"\brelease\s+(?:is\s+)?ready\b", re.IGNORECASE)),
    ("version_selected", re.compile(r"\bversion\s+(?:is\s+)?selected\b", re.IGNORECASE)),
    ("tag_created", re.compile(r"\btag\s+(?:is\s+)?created\b", re.IGNORECASE)),
    ("github_release_created", re.compile(r"\bgithub\s+release\s+(?:is\s+)?created\b", re.IGNORECASE)),
    ("artifact_published", re.compile(r"\bartifact\s+(?:is\s+)?published\b", re.IGNORECASE)),
    ("source_control_published", re.compile(r"\bsource\s+control\s+(?:is\s+)?published\b", re.IGNORECASE)),
    ("deployment_ready", re.compile(r"\bdeployment\s+(?:is\s+)?ready\b", re.IGNORECASE)),
    ("customer_access_ready", re.compile(r"\bcustomer\s+access\s+(?:is\s+)?ready\b", re.IGNORECASE)),
    ("legal_clearance", re.compile(r"\blegal\s+clearance\s+(?:is\s+)?(?:ready|complete|approved)\b", re.IGNORECASE)),
    ("company_formed", re.compile(r"\bcompany\s+(?:is\s+)?formed\b", re.IGNORECASE)),
    ("patent_filed", re.compile(r"\bpatent\s+(?:is\s+)?filed\b", re.IGNORECASE)),
    ("money_moved", re.compile(r"\bmoney\s+(?:is\s+)?moved\b", re.IGNORECASE)),
    ("secret_cleared", re.compile(r"\bsecret\s+(?:is\s+)?cleared\b", re.IGNORECASE)),
)


@dataclass(frozen=True, slots=True)
class Finding:
    """One deterministic local release-packet rehearsal validation finding."""

    rule_id: str
    message: str


def load_text(path: Path, artifact_label: str) -> str:
    """Load one UTF-8 text artifact with explicit path errors."""

    if not path.exists():
        raise FileNotFoundError(f"missing {artifact_label}: {path}")
    if not path.is_file():
        raise IsADirectoryError(f"{artifact_label} path is not a file: {path}")
    return path.read_text(encoding="utf-8")


def load_json_object(path: Path, artifact_label: str) -> dict[str, Any]:
    """Load one JSON object artifact with explicit type errors."""

    if not path.exists():
        raise FileNotFoundError(f"missing {artifact_label}: {path}")
    if not path.is_file():
        raise IsADirectoryError(f"{artifact_label} path is not a file: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{artifact_label} must be a JSON object")
    return payload


def iter_strings(value: object) -> list[str]:
    """Return every string nested under a JSON-like value."""

    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        strings: list[str] = []
        for nested_value in value.values():
            strings.extend(iter_strings(nested_value))
        return strings
    if isinstance(value, list):
        strings: list[str] = []
        for nested_value in value:
            strings.extend(iter_strings(nested_value))
        return strings
    return []


def validate_doc_text(doc_text: str) -> list[Finding]:
    """Return findings for required boundary documentation drift."""

    findings: list[Finding] = []
    for phrase in REQUIRED_DOC_PHRASES:
        if phrase not in doc_text:
            findings.append(Finding("doc_required_phrase", f"doc missing required phrase: {phrase}"))
    return findings


def validate_witness_shape(payload: dict[str, Any]) -> list[Finding]:
    """Return findings for release-packet rehearsal witness shape drift."""

    findings: list[Finding] = []
    if tuple(payload.keys()) != REQUIRED_ROOT_KEYS:
        findings.append(Finding("witness_root_keys", "witness root keys drifted"))
    for key, expected_value in EXPECTED_ROOT_VALUES.items():
        if payload.get(key) != expected_value:
            findings.append(Finding("witness_root_value", f"{key} must equal {expected_value!r}"))
    for flag in FALSE_FLAGS:
        if payload.get(flag) is not False:
            findings.append(Finding("witness_false_flag", f"{flag} must remain false"))
    if tuple(payload.get("deferral_labels", ())) != DEFERRAL_LABELS:
        findings.append(Finding("witness_deferral_labels", "deferral labels drifted"))
    if tuple(payload.get("blocked_claims", ())) != BLOCKED_CLAIMS:
        findings.append(Finding("witness_blocked_claims", "blocked claims drifted"))
    surfaces = payload.get("surfaces")
    if not isinstance(surfaces, list):
        return [*findings, Finding("witness_surfaces", "surfaces must be a list")]
    surface_ids = [surface.get("surface_id") for surface in surfaces if isinstance(surface, dict)]
    if surface_ids != list(DEFERRAL_LABELS):
        findings.append(Finding("surface_inventory", "surface inventory drifted"))
    for surface in surfaces:
        if not isinstance(surface, dict):
            findings.append(Finding("surface_shape", "each surface must be an object"))
            continue
        surface_id = surface.get("surface_id")
        if surface.get("state") != "AwaitingEvidence":
            findings.append(Finding("surface_state", f"{surface_id} must remain AwaitingEvidence"))
        if surface.get("surface_type") != SURFACE_TYPES_BY_ID.get(str(surface_id)):
            findings.append(Finding("surface_type", f"{surface_id} surface type drifted"))
        if surface.get("public_safe_note") != SURFACE_NOTES_BY_ID.get(str(surface_id)):
            findings.append(Finding("surface_note", f"{surface_id} surface note drifted"))
    return findings


def validate_no_forbidden_text(payload: dict[str, Any]) -> list[Finding]:
    """Return findings for private values or promotion phrases in the witness."""

    findings: list[Finding] = []
    for text_value in iter_strings(payload):
        for pattern_name, pattern in FORBIDDEN_VALUE_PATTERNS:
            if pattern.search(text_value):
                findings.append(Finding("forbidden_value_pattern", f"forbidden value pattern: {pattern_name}"))
        for pattern_name, pattern in FORBIDDEN_PROMOTION_PATTERNS:
            if pattern.search(text_value):
                findings.append(Finding("forbidden_promotion_pattern", f"forbidden promotion pattern: {pattern_name}"))
    return findings


def validate_artifacts(doc_path: Path = DEFAULT_DOC_PATH, packet_path: Path = DEFAULT_PACKET_PATH) -> list[Finding]:
    """Validate the local release-packet rehearsal doc and witness."""

    doc_text = load_text(doc_path, "local release-packet rehearsal doc")
    payload = load_json_object(packet_path, "local release-packet rehearsal witness")
    return [
        *validate_doc_text(doc_text),
        *validate_witness_shape(payload),
        *validate_no_forbidden_text(payload),
    ]


def build_arg_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--doc", type=Path, default=DEFAULT_DOC_PATH)
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET_PATH)
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run local release-packet rehearsal boundary validation."""

    args = build_arg_parser().parse_args(argv)
    try:
        findings = validate_artifacts(doc_path=args.doc, packet_path=args.packet)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        sys.stderr.write(f"[FAIL] foundation_local_release_packet_rehearsal_load: {exc}\n")
        return 1
    if findings:
        for finding in findings:
            sys.stderr.write(f"[FAIL] {finding.rule_id}: {finding.message}\n")
        sys.stderr.write("STATUS: failed\n")
        return 1
    sys.stdout.write("[PASS] foundation_local_release_packet_rehearsal_doc\n")
    sys.stdout.write("[PASS] foundation_local_release_packet_rehearsal_witness\n")
    sys.stdout.write("STATUS: passed\n")
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry point.
    raise SystemExit(main())
