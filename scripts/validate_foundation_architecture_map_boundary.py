#!/usr/bin/env python3
"""Validate the Foundation Mode architecture-map boundary.

Purpose: keep architecture mapping local and public-safe while architecture
completeness, module inventory completeness, interface readiness, dependency
graph readiness, invariant closure, hazard closure, proof coverage closure,
integration readiness, runtime readiness, refactor approval, implementation
approval, publication, and deployment readiness claims remain blocked.
Governance scope: Foundation Mode, system boundary inventory, module inventory,
interface map, dependency graph, invariant map, hazard map, proof-reference
map, gap register, private-value exclusion, and readiness blocking.
Dependencies: docs/FOUNDATION_ARCHITECTURE_MAP_BOUNDARY.md and
examples/foundation_architecture_map_witness.awaiting_evidence.json.
Invariants:
  - Validation is read-only.
  - The witness records architecture-map preparation only.
  - No completeness, readiness, closure, approval, publication, or deployment
    claim is allowed.
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
DEFAULT_DOC_PATH = REPO_ROOT / "docs" / "FOUNDATION_ARCHITECTURE_MAP_BOUNDARY.md"
DEFAULT_PACKET_PATH = REPO_ROOT / "examples" / "foundation_architecture_map_witness.awaiting_evidence.json"

EXPECTED_WITNESS_ID = "foundation_architecture_map_witness.awaiting_evidence.v1"
EXPECTED_BLOCKED_CLAIMS = (
    "architecture completeness",
    "module inventory completeness",
    "interface contract readiness",
    "dependency graph readiness",
    "invariant closure",
    "hazard closure",
    "proof coverage closure",
    "integration readiness",
    "runtime readiness",
    "refactor approval",
    "implementation approval",
    "external publication",
    "deployment readiness",
)
EXPECTED_SURFACES = (
    ("system_boundary_inventory", "local_draft", "AwaitingEvidence"),
    ("module_inventory", "local_draft", "AwaitingEvidence"),
    ("interface_map", "local_draft", "AwaitingEvidence"),
    ("dependency_graph", "local_draft", "AwaitingEvidence"),
    ("invariant_map", "local_draft", "AwaitingEvidence"),
    ("hazard_map", "local_draft", "AwaitingEvidence"),
    ("proof_reference_map", "local_draft", "AwaitingEvidence"),
    ("gap_register", "local_draft", "AwaitingEvidence"),
)
EXPECTED_ROOT_KEYS = {
    "architecture_complete_claimed",
    "architecture_map_surfaces",
    "blocked_claims",
    "dependency_graph_ready_claimed",
    "deployment_allowed",
    "external_publication_allowed",
    "hazard_closure_claimed",
    "implementation_approval_allowed",
    "integration_readiness_claimed",
    "interface_contract_ready_claimed",
    "invariant_closure_claimed",
    "module_inventory_complete_claimed",
    "next_action",
    "proof_coverage_closure_claimed",
    "refactor_approval_allowed",
    "runtime_readiness_claimed",
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
    "Foundation Architecture Map Boundary",
    "Witness packet: [`../examples/foundation_architecture_map_witness.awaiting_evidence.json`]",
    "Rule: Architecture-map preparation is a local planning boundary, not an",
    "No architecture-completeness claim, module-inventory completeness claim,",
    "architecture_map_boundary_state=AwaitingEvidence",
    "architecture_complete_claimed=false",
    "module_inventory_complete_claimed=false",
    "interface_contract_ready_claimed=false",
    "dependency_graph_ready_claimed=false",
    "implementation_approval_allowed=false",
    "deployment_allowed=false",
    "python scripts/validate_foundation_architecture_map_boundary.py",
)
FORBIDDEN_VALUE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("url_value", re.compile(r"https?://", re.IGNORECASE)),
    ("email_value", re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)),
    ("private_path", re.compile(r"\b[A-Za-z]:[\\/]|\\\\", re.IGNORECASE)),
    (
        "endpoint_or_service_assignment",
        re.compile(r"\b(?:endpoint|service|server|runtime|database|container)[_ -]?(?:id|url|ref|target|value|status)?\s*=", re.IGNORECASE),
    ),
    (
        "account_or_provider_assignment",
        re.compile(r"\b(?:account|provider|tenant|project|cloud)[_ -]?(?:id|ref|target|value|status)?\s*=", re.IGNORECASE),
    ),
    (
        "customer_assignment",
        re.compile(r"\b(?:customer|pilot|participant|user)[_ -]?(?:id|name|email|ref|target|value)?\s*=", re.IGNORECASE),
    ),
    (
        "secret_assignment",
        re.compile(r"\b(?:password|secret|token|api[_ -]?key|credential|client[_ -]?secret)\s*=", re.IGNORECASE),
    ),
    ("private_key_material", re.compile(r"BEGIN [A-Z ]*PRIVATE KEY")),
    (
        "implementation_assignment",
        re.compile(r"\b(?:implementation|refactor|migration|release)[_ -]?(?:id|ref|target|value|status|approval)?\s*=", re.IGNORECASE),
    ),
    (
        "publication_or_deployment_assignment",
        re.compile(r"\b(?:publish|publication|deploy|deployment|production)[_ -]?(?:id|url|ref|target|value|status)?\s*=", re.IGNORECASE),
    ),
)
FORBIDDEN_PROMOTION_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("architecture_complete", re.compile(r"\barchitecture\s+(?:is\s+)?complete\b", re.IGNORECASE)),
    ("module_inventory_complete", re.compile(r"\bmodule\s+inventory\s+(?:is\s+)?complete\b", re.IGNORECASE)),
    ("interface_ready", re.compile(r"\binterface\s+(?:contract\s+)?(?:is\s+)?ready\b", re.IGNORECASE)),
    ("dependency_graph_ready", re.compile(r"\bdependency\s+graph\s+(?:is\s+)?ready\b", re.IGNORECASE)),
    ("invariant_closed", re.compile(r"\binvariant\s+(?:closure\s+)?(?:is\s+)?closed\b", re.IGNORECASE)),
    ("hazard_closed", re.compile(r"\bhazard\s+(?:closure\s+)?(?:is\s+)?closed\b", re.IGNORECASE)),
    ("proof_coverage_closed", re.compile(r"\bproof\s+coverage\s+(?:is\s+)?closed\b", re.IGNORECASE)),
    ("integration_ready", re.compile(r"\bintegration\s+(?:is\s+)?ready\b", re.IGNORECASE)),
    ("runtime_ready", re.compile(r"\bruntime\s+(?:is\s+)?ready\b", re.IGNORECASE)),
    ("refactor_approved", re.compile(r"\brefactor\s+(?:is\s+)?approved\b", re.IGNORECASE)),
    ("implementation_approved", re.compile(r"\bimplementation\s+(?:is\s+)?approved\b", re.IGNORECASE)),
    ("published_externally", re.compile(r"\bpublished\s+externally\b", re.IGNORECASE)),
    ("deployment_ready", re.compile(r"\bdeployment\s+(?:is\s+)?ready\b", re.IGNORECASE)),
)


@dataclass(frozen=True, slots=True)
class ArchitectureMapFinding:
    """One deterministic architecture-map boundary validation finding."""

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


def validate_doc_text(text: str) -> list[ArchitectureMapFinding]:
    """Return findings for missing architecture-map documentation anchors."""

    findings: list[ArchitectureMapFinding] = []
    for phrase in REQUIRED_DOC_PHRASES:
        if phrase not in text:
            findings.append(
                ArchitectureMapFinding(
                    "foundation_architecture_map_doc_phrase_missing",
                    f"architecture-map boundary doc missing required phrase: {phrase}",
                )
            )
    return findings


def validate_packet(payload: dict[str, Any]) -> list[ArchitectureMapFinding]:
    """Return findings for architecture-map witness drift."""

    findings: list[ArchitectureMapFinding] = []
    findings.extend(validate_root_contract(payload))
    findings.extend(validate_architecture_map_surfaces(payload.get("architecture_map_surfaces")))
    findings.extend(validate_forbidden_value_patterns(payload))
    findings.extend(validate_forbidden_promotion_patterns(payload))
    return findings


def validate_root_contract(payload: dict[str, Any]) -> list[ArchitectureMapFinding]:
    """Return findings for root-level architecture-map witness drift."""

    findings: list[ArchitectureMapFinding] = []
    if set(payload) != EXPECTED_ROOT_KEYS:
        findings.append(
            ArchitectureMapFinding(
                "architecture_map_root_keys_invalid",
                f"root keys must be: {', '.join(sorted(EXPECTED_ROOT_KEYS))}",
            )
        )
    expected_values = {
        "witness_id": EXPECTED_WITNESS_ID,
        "schema_version": 1,
        "status": "AwaitingEvidence",
        "solver_outcome": "AwaitingEvidence",
        "architecture_complete_claimed": False,
        "module_inventory_complete_claimed": False,
        "interface_contract_ready_claimed": False,
        "dependency_graph_ready_claimed": False,
        "invariant_closure_claimed": False,
        "hazard_closure_claimed": False,
        "proof_coverage_closure_claimed": False,
        "integration_readiness_claimed": False,
        "runtime_readiness_claimed": False,
        "refactor_approval_allowed": False,
        "implementation_approval_allowed": False,
        "external_publication_allowed": False,
        "deployment_allowed": False,
    }
    for key, expected_value in expected_values.items():
        if payload.get(key) != expected_value:
            findings.append(
                ArchitectureMapFinding(
                    "architecture_map_root_value_invalid",
                    f"{key} must be {expected_value!r}",
                )
            )
    if tuple(payload.get("blocked_claims") or ()) != EXPECTED_BLOCKED_CLAIMS:
        findings.append(
            ArchitectureMapFinding(
                "architecture_map_blocked_claims_invalid",
                f"blocked_claims must be: {', '.join(EXPECTED_BLOCKED_CLAIMS)}",
            )
        )
    next_action = payload.get("next_action")
    if not isinstance(next_action, str) or "continue local architecture mapping" not in next_action:
        findings.append(
            ArchitectureMapFinding(
                "architecture_map_next_action_invalid",
                "next_action must preserve local architecture mapping without readiness promotion",
            )
        )
    return findings


def validate_architecture_map_surfaces(architecture_map_surfaces: object) -> list[ArchitectureMapFinding]:
    """Return findings for architecture-map surface drift."""

    findings: list[ArchitectureMapFinding] = []
    if not isinstance(architecture_map_surfaces, list) or not all(
        isinstance(surface, dict) for surface in architecture_map_surfaces
    ):
        return [
            ArchitectureMapFinding(
                "architecture_map_surfaces_invalid",
                "architecture_map_surfaces must be a list of objects",
            )
        ]
    observed_surfaces = tuple(
        (surface.get("surface_id"), surface.get("surface_type"), surface.get("state"))
        for surface in architecture_map_surfaces
    )
    if observed_surfaces != EXPECTED_SURFACES:
        findings.append(
            ArchitectureMapFinding(
                "architecture_map_surface_inventory_invalid",
                "architecture-map surface inventory does not match the Foundation Mode architecture set",
            )
        )
    surface_ids = [surface.get("surface_id") for surface in architecture_map_surfaces]
    if len(set(surface_ids)) != len(surface_ids):
        findings.append(ArchitectureMapFinding("architecture_map_surface_duplicate", "surface ids must be unique"))
    for surface in architecture_map_surfaces:
        surface_id = str(surface.get("surface_id", "<missing>"))
        if set(surface) != EXPECTED_SURFACE_KEYS:
            findings.append(
                ArchitectureMapFinding(
                    "architecture_map_surface_keys_invalid",
                    f"{surface_id} surface keys must be: {', '.join(sorted(EXPECTED_SURFACE_KEYS))}",
                )
            )
        if surface.get("state") != "AwaitingEvidence":
            findings.append(
                ArchitectureMapFinding(
                    "architecture_map_surface_state_invalid",
                    f"{surface_id} state must be AwaitingEvidence",
                )
            )
        if surface.get("evidence_ref") != "manual_preparation_pending":
            findings.append(
                ArchitectureMapFinding(
                    "architecture_map_surface_evidence_invalid",
                    f"{surface_id} evidence_ref must stay manual_preparation_pending in the committed packet",
                )
            )
        if not isinstance(surface.get("public_safe_note"), str) or not surface["public_safe_note"].strip():
            findings.append(
                ArchitectureMapFinding(
                    "architecture_map_surface_note_invalid",
                    f"{surface_id} public_safe_note must be a non-empty string",
                )
            )
    return findings


def validate_forbidden_value_patterns(payload: dict[str, Any]) -> list[ArchitectureMapFinding]:
    """Return findings for private, endpoint, account, customer, secret, service, or deployment-shaped values."""

    serialized_payload = json.dumps(payload, sort_keys=True)
    findings: list[ArchitectureMapFinding] = []
    for rule_id, pattern in FORBIDDEN_VALUE_PATTERNS:
        if pattern.search(serialized_payload):
            findings.append(
                ArchitectureMapFinding(
                    "architecture_map_forbidden_private_value_pattern",
                    f"architecture-map witness contains forbidden value pattern: {rule_id}",
                )
            )
    return findings


def validate_forbidden_promotion_patterns(payload: dict[str, Any]) -> list[ArchitectureMapFinding]:
    """Return findings if the witness drifts into architecture-readiness promotion phrases."""

    serialized_payload = json.dumps(payload, sort_keys=True)
    findings: list[ArchitectureMapFinding] = []
    for rule_id, pattern in FORBIDDEN_PROMOTION_PATTERNS:
        if pattern.search(serialized_payload):
            findings.append(
                ArchitectureMapFinding(
                    "architecture_map_forbidden_promotion_phrase",
                    f"architecture-map witness contains forbidden promotion pattern: {rule_id}",
                )
            )
    return findings


def validate_foundation_architecture_map_boundary(
    doc_path: Path = DEFAULT_DOC_PATH,
    packet_path: Path = DEFAULT_PACKET_PATH,
) -> list[ArchitectureMapFinding]:
    """Validate the Foundation Mode architecture-map boundary artifacts."""

    doc_text = load_text(doc_path, "architecture-map boundary doc")
    packet_payload = load_json_object(packet_path, "architecture-map witness packet")
    return [
        *validate_doc_text(doc_text),
        *validate_packet(packet_payload),
    ]


def main(argv: list[str] | None = None) -> int:
    """Validate architecture-map boundary artifacts and print deterministic status."""

    parser = argparse.ArgumentParser(description="Validate Foundation Mode architecture-map boundary artifacts.")
    parser.add_argument("--doc", type=Path, default=DEFAULT_DOC_PATH)
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET_PATH)
    args = parser.parse_args(argv)

    try:
        findings = validate_foundation_architecture_map_boundary(args.doc, args.packet)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"[FAIL] foundation_architecture_map_load: {exc}", file=sys.stderr)
        print("STATUS: failed", file=sys.stderr)
        return 1

    if findings:
        for finding in findings:
            print(f"[FAIL] {finding.rule_id}: {finding.message}", file=sys.stderr)
        print("STATUS: failed", file=sys.stderr)
        return 1
    print("[PASS] foundation_architecture_map_doc")
    print("[PASS] foundation_architecture_map_witness")
    print("STATUS: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
