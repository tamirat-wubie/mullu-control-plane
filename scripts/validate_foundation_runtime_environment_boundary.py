#!/usr/bin/env python3
"""Validate the Foundation Mode runtime/environment boundary.

Purpose: keep runtime and environment preparation local while runtime
verification, workstation verification, dependency-install verification,
database activation, container activation, endpoint activation, cloud runtime,
migration execution, and deployment claims remain blocked.
Governance scope: Foundation Mode, local runtime posture, environment posture,
public-safe planning witness, private-value exclusion, and deployment blocking.
Dependencies: docs/FOUNDATION_RUNTIME_ENVIRONMENT_BOUNDARY.md and
examples/foundation_runtime_environment_witness.awaiting_evidence.json.
Invariants:
  - Validation is read-only.
  - The witness records local runtime/environment planning only.
  - No runtime verification, workstation verification, dependency-install
    verification, database activation, container activation, endpoint
    activation, cloud runtime, migration execution, private value, or
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
DEFAULT_DOC_PATH = REPO_ROOT / "docs" / "FOUNDATION_RUNTIME_ENVIRONMENT_BOUNDARY.md"
DEFAULT_PACKET_PATH = REPO_ROOT / "examples" / "foundation_runtime_environment_witness.awaiting_evidence.json"

EXPECTED_WITNESS_ID = "foundation_runtime_environment_witness.awaiting_evidence.v1"
EXPECTED_BLOCKED_CLAIMS = (
    "local runtime verification",
    "workstation repeatability verification",
    "dependency install verification",
    "database runtime activation",
    "container runtime activation",
    "network endpoint activation",
    "public endpoint publication",
    "cloud runtime activation",
    "migration execution",
    "deployment readiness",
)
EXPECTED_SURFACES = (
    ("runtime_command_inventory", "local_draft", "AwaitingEvidence"),
    ("toolchain_version_questions", "local_draft", "AwaitingEvidence"),
    ("dependency_install_questions", "local_draft", "AwaitingEvidence"),
    ("database_runtime_questions", "local_draft", "AwaitingEvidence"),
    ("container_runtime_questions", "local_draft", "AwaitingEvidence"),
    ("endpoint_exposure_questions", "local_draft", "AwaitingEvidence"),
    ("migration_rollback_questions", "local_draft", "AwaitingEvidence"),
    ("local_verification_checklist", "local_draft", "AwaitingEvidence"),
)
EXPECTED_ROOT_KEYS = {
    "blocked_claims",
    "cloud_runtime_allowed",
    "container_runtime_allowed",
    "database_runtime_allowed",
    "dependency_install_verified",
    "deployment_allowed",
    "local_runtime_verified",
    "migration_execution_allowed",
    "network_endpoint_allowed",
    "next_action",
    "public_endpoint_allowed",
    "runtime_environment_surfaces",
    "schema_version",
    "solver_outcome",
    "status",
    "witness_id",
    "workstation_repeatability_verified",
}
EXPECTED_SURFACE_KEYS = {
    "evidence_ref",
    "public_safe_note",
    "state",
    "surface_id",
    "surface_type",
}
REQUIRED_DOC_PHRASES = (
    "Foundation Runtime Environment Boundary",
    "Witness packet: [`../examples/foundation_runtime_environment_witness.awaiting_evidence.json`]",
    "Rule: Runtime/environment preparation is a local planning boundary, not permission to claim runtime readiness.",
    "No local runtime verification, workstation repeatability verification,",
    "runtime_environment_boundary_state=AwaitingEvidence",
    "local_runtime_verified=false",
    "workstation_repeatability_verified=false",
    "dependency_install_verified=false",
    "deployment_allowed=false",
    "python scripts/validate_foundation_runtime_environment_boundary.py",
)
FORBIDDEN_VALUE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("url_value", re.compile(r"https?://", re.IGNORECASE)),
    ("email_value", re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)),
    ("private_path", re.compile(r"\b[A-Za-z]:[\\/]|\\\\", re.IGNORECASE)),
    ("environment_assignment", re.compile(r"\b[A-Z][A-Z0-9_]{2,}\s*=\s*[^\s,;}]+")),
    ("host_port_value", re.compile(r"\b(?:localhost|127\.0\.0\.1|0\.0\.0\.0|::1):\d{2,5}\b", re.IGNORECASE)),
    ("port_assignment", re.compile(r"\b(?:port|host|endpoint|target|listener)[_ -]?(?:id|value|url|uri|ref)?\s*=", re.IGNORECASE)),
    ("connection_string", re.compile(r"\b(?:postgres|mysql|mongodb|redis|amqp|jdbc):", re.IGNORECASE)),
    ("registry_target", re.compile(r"\b(?:registry|image|container|docker)[_ -]?(?:target|tag|url|uri|ref)?\s*=", re.IGNORECASE)),
    ("cloud_target_assignment", re.compile(r"\b(?:cloud|region|cluster|namespace|project)[_ -]?(?:target|id|ref|value)?\s*=", re.IGNORECASE)),
    ("secret_assignment", re.compile(r"\b(?:password|secret|token|api[_ -]?key)\s*=", re.IGNORECASE)),
)
FORBIDDEN_PROMOTION_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("runtime_ready", re.compile(r"\bruntime[- ]ready\b", re.IGNORECASE)),
    ("runtime_verified", re.compile(r"\bruntime\s+(?:is\s+)?verified\b", re.IGNORECASE)),
    ("workstation_verified", re.compile(r"\bworkstation\s+(?:is\s+)?verified\b", re.IGNORECASE)),
    ("dependency_installed", re.compile(r"\bdependencies\s+(?:are\s+)?installed\b", re.IGNORECASE)),
    ("database_active", re.compile(r"\bdatabase\s+(?:is\s+)?(?:active|running|enabled)\b", re.IGNORECASE)),
    ("container_active", re.compile(r"\bcontainer\s+(?:is\s+)?(?:active|running|enabled)\b", re.IGNORECASE)),
    ("endpoint_active", re.compile(r"\bendpoint\s+(?:is\s+)?(?:active|published|reachable|enabled)\b", re.IGNORECASE)),
    ("cloud_runtime_active", re.compile(r"\bcloud\s+runtime\s+(?:is\s+)?(?:active|enabled|ready)\b", re.IGNORECASE)),
    ("migration_executed", re.compile(r"\bmigration\s+(?:is\s+)?(?:executed|complete|applied)\b", re.IGNORECASE)),
)


@dataclass(frozen=True, slots=True)
class RuntimeEnvironmentFinding:
    """One deterministic runtime/environment boundary validation finding."""

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


def validate_doc_text(text: str) -> list[RuntimeEnvironmentFinding]:
    """Return findings for missing runtime/environment documentation anchors."""

    findings: list[RuntimeEnvironmentFinding] = []
    for phrase in REQUIRED_DOC_PHRASES:
        if phrase not in text:
            findings.append(
                RuntimeEnvironmentFinding(
                    "foundation_runtime_environment_doc_phrase_missing",
                    f"runtime/environment boundary doc missing required phrase: {phrase}",
                )
            )
    return findings


def validate_packet(payload: dict[str, Any]) -> list[RuntimeEnvironmentFinding]:
    """Return findings for runtime/environment witness drift."""

    findings: list[RuntimeEnvironmentFinding] = []
    findings.extend(validate_root_contract(payload))
    findings.extend(validate_runtime_environment_surfaces(payload.get("runtime_environment_surfaces")))
    findings.extend(validate_forbidden_value_patterns(payload))
    findings.extend(validate_forbidden_promotion_patterns(payload))
    return findings


def validate_root_contract(payload: dict[str, Any]) -> list[RuntimeEnvironmentFinding]:
    """Return findings for root-level runtime/environment witness drift."""

    findings: list[RuntimeEnvironmentFinding] = []
    if set(payload) != EXPECTED_ROOT_KEYS:
        findings.append(
            RuntimeEnvironmentFinding(
                "runtime_environment_root_keys_invalid",
                f"root keys must be: {', '.join(sorted(EXPECTED_ROOT_KEYS))}",
            )
        )
    expected_values = {
        "witness_id": EXPECTED_WITNESS_ID,
        "schema_version": 1,
        "status": "AwaitingEvidence",
        "solver_outcome": "AwaitingEvidence",
        "local_runtime_verified": False,
        "workstation_repeatability_verified": False,
        "dependency_install_verified": False,
        "database_runtime_allowed": False,
        "container_runtime_allowed": False,
        "network_endpoint_allowed": False,
        "public_endpoint_allowed": False,
        "cloud_runtime_allowed": False,
        "migration_execution_allowed": False,
        "deployment_allowed": False,
    }
    for key, expected_value in expected_values.items():
        if payload.get(key) != expected_value:
            findings.append(
                RuntimeEnvironmentFinding(
                    "runtime_environment_root_value_invalid",
                    f"{key} must be {expected_value!r}",
                )
            )
    if tuple(payload.get("blocked_claims") or ()) != EXPECTED_BLOCKED_CLAIMS:
        findings.append(
            RuntimeEnvironmentFinding(
                "runtime_environment_blocked_claims_invalid",
                f"blocked_claims must be: {', '.join(EXPECTED_BLOCKED_CLAIMS)}",
            )
        )
    next_action = payload.get("next_action")
    if not isinstance(next_action, str) or "do not start services" not in next_action:
        findings.append(
            RuntimeEnvironmentFinding(
                "runtime_environment_next_action_invalid",
                "next_action must preserve the closed runtime boundary",
            )
        )
    return findings


def validate_runtime_environment_surfaces(runtime_environment_surfaces: object) -> list[RuntimeEnvironmentFinding]:
    """Return findings for runtime/environment surface witness drift."""

    findings: list[RuntimeEnvironmentFinding] = []
    if not isinstance(runtime_environment_surfaces, list) or not all(
        isinstance(surface, dict) for surface in runtime_environment_surfaces
    ):
        return [
            RuntimeEnvironmentFinding(
                "runtime_environment_surfaces_invalid",
                "runtime_environment_surfaces must be a list of objects",
            )
        ]
    observed_surfaces = tuple(
        (surface.get("surface_id"), surface.get("surface_type"), surface.get("state"))
        for surface in runtime_environment_surfaces
    )
    if observed_surfaces != EXPECTED_SURFACES:
        findings.append(
            RuntimeEnvironmentFinding(
                "runtime_environment_surface_inventory_invalid",
                "runtime/environment surface inventory does not match the Foundation Mode runtime set",
            )
        )
    surface_ids = [surface.get("surface_id") for surface in runtime_environment_surfaces]
    if len(set(surface_ids)) != len(surface_ids):
        findings.append(RuntimeEnvironmentFinding("runtime_environment_surface_duplicate", "surface ids must be unique"))
    for surface in runtime_environment_surfaces:
        surface_id = str(surface.get("surface_id", "<missing>"))
        if set(surface) != EXPECTED_SURFACE_KEYS:
            findings.append(
                RuntimeEnvironmentFinding(
                    "runtime_environment_surface_keys_invalid",
                    f"{surface_id} surface keys must be: {', '.join(sorted(EXPECTED_SURFACE_KEYS))}",
                )
            )
        if surface.get("state") != "AwaitingEvidence":
            findings.append(
                RuntimeEnvironmentFinding(
                    "runtime_environment_surface_state_invalid",
                    f"{surface_id} state must be AwaitingEvidence",
                )
            )
        if surface.get("evidence_ref") != "manual_preparation_pending":
            findings.append(
                RuntimeEnvironmentFinding(
                    "runtime_environment_surface_evidence_invalid",
                    f"{surface_id} evidence_ref must stay manual_preparation_pending in the committed packet",
                )
            )
        if not isinstance(surface.get("public_safe_note"), str) or not surface["public_safe_note"].strip():
            findings.append(
                RuntimeEnvironmentFinding(
                    "runtime_environment_surface_note_invalid",
                    f"{surface_id} public_safe_note must be a non-empty string",
                )
            )
    return findings


def validate_forbidden_value_patterns(payload: dict[str, Any]) -> list[RuntimeEnvironmentFinding]:
    """Return findings for endpoint, path, connection, registry, cloud, assignment, or secret-shaped values."""

    serialized_payload = json.dumps(payload, sort_keys=True)
    findings: list[RuntimeEnvironmentFinding] = []
    for rule_id, pattern in FORBIDDEN_VALUE_PATTERNS:
        if pattern.search(serialized_payload):
            findings.append(
                RuntimeEnvironmentFinding(
                    "runtime_environment_forbidden_private_value_pattern",
                    f"runtime/environment witness contains forbidden value pattern: {rule_id}",
                )
            )
    return findings


def validate_forbidden_promotion_patterns(payload: dict[str, Any]) -> list[RuntimeEnvironmentFinding]:
    """Return findings if the witness drifts into runtime/environment readiness claims."""

    serialized_payload = json.dumps(payload, sort_keys=True)
    findings: list[RuntimeEnvironmentFinding] = []
    for rule_id, pattern in FORBIDDEN_PROMOTION_PATTERNS:
        if pattern.search(serialized_payload):
            findings.append(
                RuntimeEnvironmentFinding(
                    "runtime_environment_forbidden_promotion_phrase",
                    f"runtime/environment witness contains forbidden promotion pattern: {rule_id}",
                )
            )
    return findings


def validate_foundation_runtime_environment_boundary(
    doc_path: Path = DEFAULT_DOC_PATH,
    packet_path: Path = DEFAULT_PACKET_PATH,
) -> list[RuntimeEnvironmentFinding]:
    """Validate the Foundation Mode runtime/environment boundary artifacts."""

    doc_text = load_text(doc_path, "runtime/environment boundary doc")
    packet_payload = load_json_object(packet_path, "runtime/environment witness packet")
    return [
        *validate_doc_text(doc_text),
        *validate_packet(packet_payload),
    ]


def main(argv: list[str] | None = None) -> int:
    """Validate runtime/environment boundary artifacts and print deterministic status."""

    parser = argparse.ArgumentParser(description="Validate Foundation Mode runtime/environment boundary artifacts.")
    parser.add_argument("--doc", type=Path, default=DEFAULT_DOC_PATH)
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET_PATH)
    args = parser.parse_args(argv)

    try:
        findings = validate_foundation_runtime_environment_boundary(args.doc, args.packet)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"[FAIL] foundation_runtime_environment_load: {exc}", file=sys.stderr)
        print("STATUS: failed", file=sys.stderr)
        return 1

    if findings:
        for finding in findings:
            print(f"[FAIL] {finding.rule_id}: {finding.message}", file=sys.stderr)
        print("STATUS: failed", file=sys.stderr)
        return 1
    print("[PASS] foundation_runtime_environment_doc")
    print("[PASS] foundation_runtime_environment_witness")
    print("STATUS: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
