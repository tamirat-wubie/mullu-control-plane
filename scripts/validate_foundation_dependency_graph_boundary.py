#!/usr/bin/env python3
"""Validate the Foundation Mode dependency-graph boundary.

Purpose: keep dependency graph drafting local and public-safe while graph
completeness, dependency contract readiness, import readiness, package install,
version-lock readiness, service dependency binding, provider binding,
vulnerability scan pass, runtime readiness, owner approval, test, refactor,
implementation, publication, and deployment claims remain blocked.
Governance scope: Foundation Mode, dependency-graph surfaces, private-value
exclusion, and readiness blocking.
Dependencies: docs/FOUNDATION_DEPENDENCY_GRAPH_BOUNDARY.md and
examples/foundation_dependency_graph_witness.awaiting_evidence.json.
Invariants:
  - Validation is read-only.
  - The witness records dependency-graph preparation only.
  - No dependency, install, binding, scan, owner, test, approval, publication,
    or deployment claim is allowed.
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
DEFAULT_DOC_PATH = REPO_ROOT / "docs" / "FOUNDATION_DEPENDENCY_GRAPH_BOUNDARY.md"
DEFAULT_PACKET_PATH = REPO_ROOT / "examples" / "foundation_dependency_graph_witness.awaiting_evidence.json"

EXPECTED_WITNESS_ID = "foundation_dependency_graph_witness.awaiting_evidence.v1"
EXPECTED_BLOCKED_CLAIMS = (
    "dependency-graph completeness",
    "dependency contract readiness",
    "import boundary readiness",
    "package install approval",
    "version-lock readiness",
    "service dependency binding",
    "external provider binding",
    "vulnerability scan pass",
    "runtime dependency readiness",
    "owner approval assignment",
    "test pass",
    "refactor approval",
    "implementation approval",
    "external publication",
    "deployment readiness",
)
EXPECTED_SURFACES = (
    ("module_dependencies", "local_draft", "AwaitingEvidence"),
    ("package_dependencies", "local_draft", "AwaitingEvidence"),
    ("runtime_dependencies", "local_draft", "AwaitingEvidence"),
    ("service_dependencies", "local_draft", "AwaitingEvidence"),
    ("provider_dependencies", "local_draft", "AwaitingEvidence"),
    ("data_dependencies", "local_draft", "AwaitingEvidence"),
    ("governance_dependencies", "local_draft", "AwaitingEvidence"),
    ("operator_dependencies", "local_draft", "AwaitingEvidence"),
)
EXPECTED_ROOT_KEYS = {
    "blocked_claims",
    "dependency_contract_ready_claimed",
    "dependency_graph_complete_claimed",
    "dependency_graph_surfaces",
    "deployment_allowed",
    "external_provider_bound",
    "external_publication_allowed",
    "implementation_approval_allowed",
    "import_boundary_ready_claimed",
    "next_action",
    "owner_approval_assigned",
    "package_install_allowed",
    "refactor_approval_allowed",
    "runtime_dependency_ready_claimed",
    "schema_version",
    "service_dependency_bound",
    "solver_outcome",
    "status",
    "test_pass_claimed",
    "version_lock_ready_claimed",
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
    "Foundation Dependency Graph Boundary",
    "Witness packet: [`../examples/foundation_dependency_graph_witness.awaiting_evidence.json`]",
    "Rule: Dependency-graph preparation is a local planning boundary, not a",
    "No dependency-graph completeness, dependency contract readiness, import",
    "dependency_graph_boundary_state=AwaitingEvidence",
    "dependency_graph_complete_claimed=false",
    "dependency_contract_ready_claimed=false",
    "import_boundary_ready_claimed=false",
    "package_install_allowed=false",
    "version_lock_ready_claimed=false",
    "service_dependency_bound=false",
    "external_provider_bound=false",
    "implementation_approval_allowed=false",
    "deployment_allowed=false",
    "python scripts/validate_foundation_dependency_graph_boundary.py",
)
FORBIDDEN_VALUE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("url_value", re.compile(r"https?://", re.IGNORECASE)),
    ("email_value", re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)),
    ("private_path", re.compile(r"\b[A-Za-z]:[\\/]|\\\\", re.IGNORECASE)),
    (
        "endpoint_or_service_assignment",
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
        "package_or_dependency_assignment",
        re.compile(
            r"\b(?:package|dependency|library|import)[_ -]?"
            r"(?:id|name|version|ref|target|value|status)?\s*=",
            re.IGNORECASE,
        ),
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
        "scan_pass_assignment",
        re.compile(r"\b(?:scan|audit|vulnerability)[_ -]?(?:pass|status|result|value)?\s*=", re.IGNORECASE),
    ),
    (
        "implementation_assignment",
        re.compile(
            r"\b(?:implementation|refactor|migration|release)[_ -]?"
            r"(?:id|ref|target|value|status|approval)?\s*=",
            re.IGNORECASE,
        ),
    ),
    (
        "test_pass_assignment",
        re.compile(r"\b(?:test|suite|assertion)[_ -]?(?:pass|status|result|value)?\s*=", re.IGNORECASE),
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
    ("dependency_graph_complete", re.compile(r"\bdependency\s+graph\s+(?:is\s+)?complete\b", re.IGNORECASE)),
    ("dependency_contract_ready", re.compile(r"\bdependency\s+contract\s+(?:is\s+)?ready\b", re.IGNORECASE)),
    ("import_boundary_ready", re.compile(r"\bimport\s+boundary\s+(?:is\s+)?ready\b", re.IGNORECASE)),
    ("package_installed", re.compile(r"\bpackage\s+(?:is\s+)?installed\b", re.IGNORECASE)),
    ("version_lock_ready", re.compile(r"\bversion\s+lock\s+(?:is\s+)?ready\b", re.IGNORECASE)),
    ("service_dependency_bound", re.compile(r"\bservice\s+dependency\s+(?:is\s+)?bound\b", re.IGNORECASE)),
    ("provider_bound", re.compile(r"\bprovider\s+(?:is\s+)?bound\b", re.IGNORECASE)),
    ("vulnerability_scan_passed", re.compile(r"\bvulnerability\s+scan\s+(?:has\s+)?passed\b", re.IGNORECASE)),
    ("runtime_dependency_ready", re.compile(r"\bruntime\s+dependency\s+(?:is\s+)?ready\b", re.IGNORECASE)),
    ("owner_approved", re.compile(r"\bowner\s+(?:is\s+)?approved\b", re.IGNORECASE)),
    ("test_passed", re.compile(r"\btests?\s+(?:have\s+)?passed\b", re.IGNORECASE)),
    ("refactor_approved", re.compile(r"\brefactor\s+(?:is\s+)?approved\b", re.IGNORECASE)),
    ("implementation_approved", re.compile(r"\bimplementation\s+(?:is\s+)?approved\b", re.IGNORECASE)),
    ("published_externally", re.compile(r"\bpublished\s+externally\b", re.IGNORECASE)),
    ("deployment_ready", re.compile(r"\bdeployment\s+(?:is\s+)?ready\b", re.IGNORECASE)),
)


@dataclass(frozen=True, slots=True)
class DependencyGraphFinding:
    """One deterministic dependency-graph validation finding."""

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


def validate_doc_text(text: str) -> list[DependencyGraphFinding]:
    """Return findings for missing dependency-graph documentation anchors."""

    findings: list[DependencyGraphFinding] = []
    for phrase in REQUIRED_DOC_PHRASES:
        if phrase not in text:
            findings.append(
                DependencyGraphFinding(
                    "foundation_dependency_graph_doc_phrase_missing",
                    f"dependency-graph boundary doc missing required phrase: {phrase}",
                )
            )
    return findings


def validate_packet(payload: dict[str, Any]) -> list[DependencyGraphFinding]:
    """Return findings for dependency-graph witness drift."""

    findings: list[DependencyGraphFinding] = []
    findings.extend(validate_root_contract(payload))
    findings.extend(validate_dependency_graph_surfaces(payload.get("dependency_graph_surfaces")))
    findings.extend(validate_forbidden_value_patterns(payload))
    findings.extend(validate_forbidden_promotion_patterns(payload))
    return findings


def validate_root_contract(payload: dict[str, Any]) -> list[DependencyGraphFinding]:
    """Return findings for root-level dependency-graph witness drift."""

    findings: list[DependencyGraphFinding] = []
    if set(payload) != EXPECTED_ROOT_KEYS:
        findings.append(
            DependencyGraphFinding(
                "dependency_graph_root_keys_invalid",
                f"root keys must be: {', '.join(sorted(EXPECTED_ROOT_KEYS))}",
            )
        )
    expected_values = {
        "witness_id": EXPECTED_WITNESS_ID,
        "schema_version": 1,
        "status": "AwaitingEvidence",
        "solver_outcome": "AwaitingEvidence",
        "dependency_graph_complete_claimed": False,
        "dependency_contract_ready_claimed": False,
        "import_boundary_ready_claimed": False,
        "package_install_allowed": False,
        "version_lock_ready_claimed": False,
        "service_dependency_bound": False,
        "external_provider_bound": False,
        "vulnerability_scan_pass_claimed": False,
        "runtime_dependency_ready_claimed": False,
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
                DependencyGraphFinding(
                    "dependency_graph_root_value_invalid",
                    f"{key} must be {expected_value!r}",
                )
            )
    if tuple(payload.get("blocked_claims") or ()) != EXPECTED_BLOCKED_CLAIMS:
        findings.append(
            DependencyGraphFinding(
                "dependency_graph_blocked_claims_invalid",
                f"blocked_claims must be: {', '.join(EXPECTED_BLOCKED_CLAIMS)}",
            )
        )
    next_action = payload.get("next_action")
    if not isinstance(next_action, str) or "continue local dependency graph question drafting" not in next_action:
        findings.append(
            DependencyGraphFinding(
                "dependency_graph_next_action_invalid",
                "next_action must preserve local dependency graph drafting without readiness promotion",
            )
        )
    return findings


def validate_dependency_graph_surfaces(dependency_graph_surfaces: object) -> list[DependencyGraphFinding]:
    """Return findings for dependency-graph surface drift."""

    findings: list[DependencyGraphFinding] = []
    if not isinstance(dependency_graph_surfaces, list) or not all(
        isinstance(surface, dict) for surface in dependency_graph_surfaces
    ):
        return [
            DependencyGraphFinding(
                "dependency_graph_surfaces_invalid",
                "dependency_graph_surfaces must be a list of objects",
            )
        ]
    observed_surfaces = tuple(
        (surface.get("surface_id"), surface.get("surface_type"), surface.get("state"))
        for surface in dependency_graph_surfaces
    )
    if observed_surfaces != EXPECTED_SURFACES:
        findings.append(
            DependencyGraphFinding(
                "dependency_graph_surface_inventory_invalid",
                "dependency-graph surface inventory does not match the Foundation Mode dependency set",
            )
        )
    surface_ids = [surface.get("surface_id") for surface in dependency_graph_surfaces]
    if len(set(surface_ids)) != len(surface_ids):
        findings.append(DependencyGraphFinding("dependency_graph_surface_duplicate", "surface ids must be unique"))
    for surface in dependency_graph_surfaces:
        surface_id = str(surface.get("surface_id", "<missing>"))
        if set(surface) != EXPECTED_SURFACE_KEYS:
            findings.append(
                DependencyGraphFinding(
                    "dependency_graph_surface_keys_invalid",
                    f"{surface_id} surface keys must be: {', '.join(sorted(EXPECTED_SURFACE_KEYS))}",
                )
            )
        if surface.get("state") != "AwaitingEvidence":
            findings.append(
                DependencyGraphFinding(
                    "dependency_graph_surface_state_invalid",
                    f"{surface_id} state must be AwaitingEvidence",
                )
            )
        if surface.get("evidence_ref") != "manual_preparation_pending":
            findings.append(
                DependencyGraphFinding(
                    "dependency_graph_surface_evidence_invalid",
                    f"{surface_id} evidence_ref must stay manual_preparation_pending in the committed packet",
                )
            )
        if not isinstance(surface.get("public_safe_note"), str) or not surface["public_safe_note"].strip():
            findings.append(
                DependencyGraphFinding(
                    "dependency_graph_surface_note_invalid",
                    f"{surface_id} public_safe_note must be a non-empty string",
                )
            )
    return findings


def validate_forbidden_value_patterns(payload: dict[str, Any]) -> list[DependencyGraphFinding]:
    """Return findings for private, dependency, package, provider, scan, test, or deployment values."""

    serialized_payload = json.dumps(payload, sort_keys=True)
    findings: list[DependencyGraphFinding] = []
    for rule_id, pattern in FORBIDDEN_VALUE_PATTERNS:
        if pattern.search(serialized_payload):
            findings.append(
                DependencyGraphFinding(
                    "dependency_graph_forbidden_private_value_pattern",
                    f"dependency-graph witness contains forbidden value pattern: {rule_id}",
                )
            )
    return findings


def validate_forbidden_promotion_patterns(payload: dict[str, Any]) -> list[DependencyGraphFinding]:
    """Return findings if the witness drifts into dependency-readiness promotion phrases."""

    serialized_payload = json.dumps(payload, sort_keys=True)
    findings: list[DependencyGraphFinding] = []
    for rule_id, pattern in FORBIDDEN_PROMOTION_PATTERNS:
        if pattern.search(serialized_payload):
            findings.append(
                DependencyGraphFinding(
                    "dependency_graph_forbidden_promotion_phrase",
                    f"dependency-graph witness contains forbidden promotion pattern: {rule_id}",
                )
            )
    return findings


def validate_foundation_dependency_graph_boundary(
    doc_path: Path = DEFAULT_DOC_PATH,
    packet_path: Path = DEFAULT_PACKET_PATH,
) -> list[DependencyGraphFinding]:
    """Validate the Foundation Mode dependency-graph boundary artifacts."""

    doc_text = load_text(doc_path, "dependency-graph boundary doc")
    packet_payload = load_json_object(packet_path, "dependency-graph witness packet")
    return [
        *validate_doc_text(doc_text),
        *validate_packet(packet_payload),
    ]


def main(argv: list[str] | None = None) -> int:
    """Validate dependency-graph artifacts and print deterministic status."""

    parser = argparse.ArgumentParser(description="Validate Foundation Mode dependency-graph artifacts.")
    parser.add_argument("--doc", type=Path, default=DEFAULT_DOC_PATH)
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET_PATH)
    args = parser.parse_args(argv)

    try:
        findings = validate_foundation_dependency_graph_boundary(args.doc, args.packet)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"[FAIL] foundation_dependency_graph_load: {exc}", file=sys.stderr)
        print("STATUS: failed", file=sys.stderr)
        return 1

    if findings:
        for finding in findings:
            print(f"[FAIL] {finding.rule_id}: {finding.message}", file=sys.stderr)
        print("STATUS: failed", file=sys.stderr)
        return 1
    print("[PASS] foundation_dependency_graph_doc")
    print("[PASS] foundation_dependency_graph_witness")
    print("STATUS: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
