#!/usr/bin/env python3
"""Validate the Foundation Mode local-workstation boundary.

Purpose: keep local-workstation preparation public-safe while machine,
toolchain, dependency-install, environment, service, full-test, cloud, and
deployment readiness claims remain blocked.
Governance scope: Foundation Mode, local workstation posture, public-safe
planning witness, private-value exclusion, workstation-repeatability blocking,
and deployment blocking.
Dependencies: docs/FOUNDATION_LOCAL_WORKSTATION_BOUNDARY.md and
examples/foundation_local_workstation_witness.awaiting_evidence.json.
Invariants:
  - Validation is read-only.
  - The witness records local workstation planning only.
  - No workstation verification, toolchain verification, dependency install,
    environment mutation, privileged command, service start, full-test-suite
    pass, cloud dependency, private path, or deployment claim is allowed.
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
DEFAULT_DOC_PATH = REPO_ROOT / "docs" / "FOUNDATION_LOCAL_WORKSTATION_BOUNDARY.md"
DEFAULT_PACKET_PATH = REPO_ROOT / "examples" / "foundation_local_workstation_witness.awaiting_evidence.json"

EXPECTED_WITNESS_ID = "foundation_local_workstation_witness.awaiting_evidence.v1"
EXPECTED_BLOCKED_CLAIMS = (
    "local workstation verification",
    "Python toolchain verification",
    "Node toolchain verification",
    "Rust toolchain verification",
    "dependency install authorization",
    "environment mutation",
    "privileged command",
    "service start",
    "full test suite pass",
    "cloud dependency",
    "private path recording",
    "deployment readiness",
)
EXPECTED_SURFACES = (
    ("local_command_inventory", "local_draft", "AwaitingEvidence"),
    ("toolchain_version_questions", "local_draft", "AwaitingEvidence"),
    ("shell_profile_questions", "local_draft", "AwaitingEvidence"),
    ("dependency_install_questions", "local_draft", "AwaitingEvidence"),
    ("test_command_questions", "local_draft", "AwaitingEvidence"),
    ("environment_variable_questions", "local_draft", "AwaitingEvidence"),
    ("permission_boundary_questions", "local_draft", "AwaitingEvidence"),
    ("local_receipt_questions", "local_draft", "AwaitingEvidence"),
)
EXPECTED_ROOT_KEYS = {
    "blocked_claims",
    "cloud_dependency_allowed",
    "dependency_install_allowed",
    "deployment_allowed",
    "environment_mutation_allowed",
    "full_test_suite_pass_claimed",
    "local_workstation_surfaces",
    "local_workstation_verified",
    "next_action",
    "node_toolchain_verified",
    "private_path_recording_allowed",
    "privileged_command_allowed",
    "python_toolchain_verified",
    "rust_toolchain_verified",
    "schema_version",
    "service_start_allowed",
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
    "Foundation Local Workstation Boundary",
    "Witness packet: [`../examples/foundation_local_workstation_witness.awaiting_evidence.json`]",
    "Rule: Local-workstation preparation is a local planning boundary, not",
    "No local workstation verification, Python toolchain verification, Node",
    "local_workstation_boundary_state=AwaitingEvidence",
    "local_workstation_verified=false",
    "python_toolchain_verified=false",
    "dependency_install_allowed=false",
    "deployment_allowed=false",
    "python scripts/validate_foundation_local_workstation_boundary.py",
)
FORBIDDEN_VALUE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("url_value", re.compile(r"https?://", re.IGNORECASE)),
    ("email_value", re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)),
    ("private_path", re.compile(r"\b[A-Za-z]:[\\/]|\\\\", re.IGNORECASE)),
    ("environment_assignment", re.compile(r"\b[A-Z][A-Z0-9_]{2,}\s*=\s*[^\s,;}]+")),
    (
        "toolchain_target_assignment",
        re.compile(r"\b(?:python|node|rust|cargo|npm|pip)[_ -]?(?:target|path|version|ref|value)?\s*=", re.IGNORECASE),
    ),
    (
        "install_target_assignment",
        re.compile(r"\b(?:install|dependency|package)[_ -]?(?:target|path|url|id|ref)?\s*=", re.IGNORECASE),
    ),
    (
        "shell_profile_assignment",
        re.compile(r"\b(?:shell|profile|path)[_ -]?(?:target|path|value|ref)?\s*=", re.IGNORECASE),
    ),
    (
        "command_target_assignment",
        re.compile(r"\b(?:command|cmd|script)[_ -]?(?:target|path|value|ref)?\s*=", re.IGNORECASE),
    ),
    (
        "service_target_assignment",
        re.compile(r"\b(?:service|server|listener|port)[_ -]?(?:target|id|ref|value)?\s*=", re.IGNORECASE),
    ),
    (
        "cloud_target_assignment",
        re.compile(r"\b(?:cloud|region|cluster|bucket|project)[_ -]?(?:target|id|ref|value)?\s*=", re.IGNORECASE),
    ),
)
FORBIDDEN_PROMOTION_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("workstation_ready", re.compile(r"\bworkstation\s+(?:is\s+)?ready\b", re.IGNORECASE)),
    ("workstation_verified", re.compile(r"\bworkstation\s+(?:is\s+)?verified\b", re.IGNORECASE)),
    ("toolchain_verified", re.compile(r"\btoolchain\s+(?:is\s+)?verified\b", re.IGNORECASE)),
    ("dependencies_installed", re.compile(r"\bdependencies\s+(?:are\s+)?installed\b", re.IGNORECASE)),
    ("test_suite_passed", re.compile(r"\btest\s+suite\s+(?:is\s+)?passed\b", re.IGNORECASE)),
    ("environment_configured", re.compile(r"\benvironment\s+(?:is\s+)?configured\b", re.IGNORECASE)),
    ("privileged_access_ready", re.compile(r"\bprivileged\s+access\s+(?:is\s+)?ready\b", re.IGNORECASE)),
    ("service_started", re.compile(r"\bservice\s+(?:is\s+)?started\b", re.IGNORECASE)),
    ("cloud_dependency_ready", re.compile(r"\bcloud\s+dependency\s+(?:is\s+)?ready\b", re.IGNORECASE)),
    ("deployment_ready", re.compile(r"\bdeployment\s+(?:is\s+)?ready\b", re.IGNORECASE)),
)


@dataclass(frozen=True, slots=True)
class LocalWorkstationFinding:
    """One deterministic local-workstation boundary validation finding."""

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


def validate_doc_text(text: str) -> list[LocalWorkstationFinding]:
    """Return findings for missing local-workstation documentation anchors."""

    findings: list[LocalWorkstationFinding] = []
    for phrase in REQUIRED_DOC_PHRASES:
        if phrase not in text:
            findings.append(
                LocalWorkstationFinding(
                    "foundation_local_workstation_doc_phrase_missing",
                    f"local-workstation boundary doc missing required phrase: {phrase}",
                )
            )
    return findings


def validate_packet(payload: dict[str, Any]) -> list[LocalWorkstationFinding]:
    """Return findings for local-workstation witness drift."""

    findings: list[LocalWorkstationFinding] = []
    findings.extend(validate_root_contract(payload))
    findings.extend(validate_local_workstation_surfaces(payload.get("local_workstation_surfaces")))
    findings.extend(validate_forbidden_value_patterns(payload))
    findings.extend(validate_forbidden_promotion_patterns(payload))
    return findings


def validate_root_contract(payload: dict[str, Any]) -> list[LocalWorkstationFinding]:
    """Return findings for root-level local-workstation witness drift."""

    findings: list[LocalWorkstationFinding] = []
    if set(payload) != EXPECTED_ROOT_KEYS:
        findings.append(
            LocalWorkstationFinding(
                "local_workstation_root_keys_invalid",
                f"root keys must be: {', '.join(sorted(EXPECTED_ROOT_KEYS))}",
            )
        )
    expected_values = {
        "witness_id": EXPECTED_WITNESS_ID,
        "schema_version": 1,
        "status": "AwaitingEvidence",
        "solver_outcome": "AwaitingEvidence",
        "local_workstation_verified": False,
        "python_toolchain_verified": False,
        "node_toolchain_verified": False,
        "rust_toolchain_verified": False,
        "dependency_install_allowed": False,
        "environment_mutation_allowed": False,
        "privileged_command_allowed": False,
        "service_start_allowed": False,
        "full_test_suite_pass_claimed": False,
        "cloud_dependency_allowed": False,
        "private_path_recording_allowed": False,
        "deployment_allowed": False,
    }
    for key, expected_value in expected_values.items():
        if payload.get(key) != expected_value:
            findings.append(
                LocalWorkstationFinding(
                    "local_workstation_root_value_invalid",
                    f"{key} must be {expected_value!r}",
                )
            )
    if tuple(payload.get("blocked_claims") or ()) != EXPECTED_BLOCKED_CLAIMS:
        findings.append(
            LocalWorkstationFinding(
                "local_workstation_blocked_claims_invalid",
                f"blocked_claims must be: {', '.join(EXPECTED_BLOCKED_CLAIMS)}",
            )
        )
    next_action = payload.get("next_action")
    if not isinstance(next_action, str) or "do not claim workstation" not in next_action:
        findings.append(
            LocalWorkstationFinding(
                "local_workstation_next_action_invalid",
                "next_action must preserve the closed local-workstation boundary",
            )
        )
    return findings


def validate_local_workstation_surfaces(local_workstation_surfaces: object) -> list[LocalWorkstationFinding]:
    """Return findings for local-workstation surface witness drift."""

    findings: list[LocalWorkstationFinding] = []
    if not isinstance(local_workstation_surfaces, list) or not all(
        isinstance(surface, dict) for surface in local_workstation_surfaces
    ):
        return [
            LocalWorkstationFinding(
                "local_workstation_surfaces_invalid",
                "local_workstation_surfaces must be a list of objects",
            )
        ]
    observed_surfaces = tuple(
        (surface.get("surface_id"), surface.get("surface_type"), surface.get("state"))
        for surface in local_workstation_surfaces
    )
    if observed_surfaces != EXPECTED_SURFACES:
        findings.append(
            LocalWorkstationFinding(
                "local_workstation_surface_inventory_invalid",
                "local-workstation surface inventory does not match the Foundation Mode workstation set",
            )
        )
    surface_ids = [surface.get("surface_id") for surface in local_workstation_surfaces]
    if len(set(surface_ids)) != len(surface_ids):
        findings.append(LocalWorkstationFinding("local_workstation_surface_duplicate", "surface ids must be unique"))
    for surface in local_workstation_surfaces:
        surface_id = str(surface.get("surface_id", "<missing>"))
        if set(surface) != EXPECTED_SURFACE_KEYS:
            findings.append(
                LocalWorkstationFinding(
                    "local_workstation_surface_keys_invalid",
                    f"{surface_id} surface keys must be: {', '.join(sorted(EXPECTED_SURFACE_KEYS))}",
                )
            )
        if surface.get("state") != "AwaitingEvidence":
            findings.append(
                LocalWorkstationFinding(
                    "local_workstation_surface_state_invalid",
                    f"{surface_id} state must be AwaitingEvidence",
                )
            )
        if surface.get("evidence_ref") != "manual_preparation_pending":
            findings.append(
                LocalWorkstationFinding(
                    "local_workstation_surface_evidence_invalid",
                    f"{surface_id} evidence_ref must stay manual_preparation_pending in the committed packet",
                )
            )
        if not isinstance(surface.get("public_safe_note"), str) or not surface["public_safe_note"].strip():
            findings.append(
                LocalWorkstationFinding(
                    "local_workstation_surface_note_invalid",
                    f"{surface_id} public_safe_note must be a non-empty string",
                )
            )
    return findings


def validate_forbidden_value_patterns(payload: dict[str, Any]) -> list[LocalWorkstationFinding]:
    """Return findings for private path, environment, install, command, service, or cloud-shaped values."""

    serialized_payload = json.dumps(payload, sort_keys=True)
    findings: list[LocalWorkstationFinding] = []
    for rule_id, pattern in FORBIDDEN_VALUE_PATTERNS:
        if pattern.search(serialized_payload):
            findings.append(
                LocalWorkstationFinding(
                    "local_workstation_forbidden_private_value_pattern",
                    f"local-workstation witness contains forbidden value pattern: {rule_id}",
                )
            )
    return findings


def validate_forbidden_promotion_patterns(payload: dict[str, Any]) -> list[LocalWorkstationFinding]:
    """Return findings if the witness drifts into workstation-readiness claims."""

    serialized_payload = json.dumps(payload, sort_keys=True)
    findings: list[LocalWorkstationFinding] = []
    for rule_id, pattern in FORBIDDEN_PROMOTION_PATTERNS:
        if pattern.search(serialized_payload):
            findings.append(
                LocalWorkstationFinding(
                    "local_workstation_forbidden_promotion_phrase",
                    f"local-workstation witness contains forbidden promotion pattern: {rule_id}",
                )
            )
    return findings


def validate_foundation_local_workstation_boundary(
    doc_path: Path = DEFAULT_DOC_PATH,
    packet_path: Path = DEFAULT_PACKET_PATH,
) -> list[LocalWorkstationFinding]:
    """Validate the Foundation Mode local-workstation boundary artifacts."""

    doc_text = load_text(doc_path, "local-workstation boundary doc")
    packet_payload = load_json_object(packet_path, "local-workstation witness packet")
    return [
        *validate_doc_text(doc_text),
        *validate_packet(packet_payload),
    ]


def main(argv: list[str] | None = None) -> int:
    """Validate local-workstation boundary artifacts and print deterministic status."""

    parser = argparse.ArgumentParser(description="Validate Foundation Mode local-workstation boundary artifacts.")
    parser.add_argument("--doc", type=Path, default=DEFAULT_DOC_PATH)
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET_PATH)
    args = parser.parse_args(argv)

    try:
        findings = validate_foundation_local_workstation_boundary(args.doc, args.packet)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"[FAIL] foundation_local_workstation_load: {exc}", file=sys.stderr)
        print("STATUS: failed", file=sys.stderr)
        return 1

    if findings:
        for finding in findings:
            print(f"[FAIL] {finding.rule_id}: {finding.message}", file=sys.stderr)
        print("STATUS: failed", file=sys.stderr)
        return 1
    print("[PASS] foundation_local_workstation_doc")
    print("[PASS] foundation_local_workstation_witness")
    print("STATUS: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
