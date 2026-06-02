#!/usr/bin/env python3
"""Validate the Foundation Mode interface-map boundary.

Purpose: keep interface mapping local and public-safe while interface-map
completeness, interface contract readiness, endpoint readiness, service
binding, event/message readiness, data-flow readiness, trust closure,
integration readiness, runtime readiness, owner approval, test, refactor,
implementation, publication, and deployment claims remain blocked.
Governance scope: Foundation Mode, interface-map surfaces, private-value
exclusion, and readiness blocking.
Dependencies: docs/FOUNDATION_INTERFACE_MAP_BOUNDARY.md and
examples/foundation_interface_map_witness.awaiting_evidence.json.
Invariants:
  - Validation is read-only.
  - The witness records interface-map preparation only.
  - No interface, endpoint, service, owner, test, approval, publication, or
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
DEFAULT_DOC_PATH = REPO_ROOT / "docs" / "FOUNDATION_INTERFACE_MAP_BOUNDARY.md"
DEFAULT_PACKET_PATH = REPO_ROOT / "examples" / "foundation_interface_map_witness.awaiting_evidence.json"

EXPECTED_WITNESS_ID = "foundation_interface_map_witness.awaiting_evidence.v1"
EXPECTED_BLOCKED_CLAIMS = (
    "interface-map completeness",
    "interface contract readiness",
    "endpoint readiness",
    "service binding",
    "event/message readiness",
    "data-flow readiness",
    "trust boundary closure",
    "integration readiness",
    "runtime readiness",
    "owner approval assignment",
    "test pass",
    "refactor approval",
    "implementation approval",
    "external publication",
    "deployment readiness",
)
EXPECTED_SURFACES = (
    ("component_interfaces", "local_draft", "AwaitingEvidence"),
    ("product_control_plane_interfaces", "local_draft", "AwaitingEvidence"),
    ("control_plane_gateway_interfaces", "local_draft", "AwaitingEvidence"),
    ("gateway_runtime_interfaces", "local_draft", "AwaitingEvidence"),
    ("runtime_governance_interfaces", "local_draft", "AwaitingEvidence"),
    ("governance_evidence_interfaces", "local_draft", "AwaitingEvidence"),
    ("data_flow_interfaces", "local_draft", "AwaitingEvidence"),
    ("operator_handoff_interfaces", "local_draft", "AwaitingEvidence"),
)
EXPECTED_ROOT_KEYS = {
    "blocked_claims",
    "data_flow_ready_claimed",
    "deployment_allowed",
    "endpoint_ready_claimed",
    "event_message_ready_claimed",
    "external_publication_allowed",
    "implementation_approval_allowed",
    "interface_contract_ready_claimed",
    "interface_map_complete_claimed",
    "interface_map_surfaces",
    "integration_ready_claimed",
    "next_action",
    "owner_approval_assigned",
    "refactor_approval_allowed",
    "runtime_ready_claimed",
    "schema_version",
    "service_binding_claimed",
    "solver_outcome",
    "status",
    "test_pass_claimed",
    "trust_boundary_closed_claimed",
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
    "Foundation Interface Map Boundary",
    "Witness packet: [`../examples/foundation_interface_map_witness.awaiting_evidence.json`]",
    "Rule: Interface-map preparation is a local planning boundary, not an",
    "No interface-map completeness, interface contract readiness, endpoint",
    "interface_map_boundary_state=AwaitingEvidence",
    "interface_map_complete_claimed=false",
    "interface_contract_ready_claimed=false",
    "endpoint_ready_claimed=false",
    "service_binding_claimed=false",
    "integration_ready_claimed=false",
    "implementation_approval_allowed=false",
    "deployment_allowed=false",
    "python scripts/validate_foundation_interface_map_boundary.py",
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
    ("interface_map_complete", re.compile(r"\binterface\s+map\s+(?:is\s+)?complete\b", re.IGNORECASE)),
    ("interface_contract_ready", re.compile(r"\binterface\s+contract\s+(?:is\s+)?ready\b", re.IGNORECASE)),
    ("endpoint_ready", re.compile(r"\bendpoint\s+(?:is\s+)?ready\b", re.IGNORECASE)),
    ("service_bound", re.compile(r"\bservice\s+(?:is\s+)?bound\b", re.IGNORECASE)),
    ("event_message_ready", re.compile(r"\bevent\s+or\s+message\s+(?:is\s+)?ready\b", re.IGNORECASE)),
    ("data_flow_ready", re.compile(r"\bdata\s+flow\s+(?:is\s+)?ready\b", re.IGNORECASE)),
    ("trust_closed", re.compile(r"\btrust\s+boundary\s+(?:is\s+)?closed\b", re.IGNORECASE)),
    ("integration_ready", re.compile(r"\bintegration\s+(?:is\s+)?ready\b", re.IGNORECASE)),
    ("runtime_ready", re.compile(r"\bruntime\s+(?:is\s+)?ready\b", re.IGNORECASE)),
    ("owner_approved", re.compile(r"\bowner\s+(?:is\s+)?approved\b", re.IGNORECASE)),
    ("test_passed", re.compile(r"\btests?\s+(?:have\s+)?passed\b", re.IGNORECASE)),
    ("refactor_approved", re.compile(r"\brefactor\s+(?:is\s+)?approved\b", re.IGNORECASE)),
    ("implementation_approved", re.compile(r"\bimplementation\s+(?:is\s+)?approved\b", re.IGNORECASE)),
    ("published_externally", re.compile(r"\bpublished\s+externally\b", re.IGNORECASE)),
    ("deployment_ready", re.compile(r"\bdeployment\s+(?:is\s+)?ready\b", re.IGNORECASE)),
)


@dataclass(frozen=True, slots=True)
class InterfaceMapFinding:
    """One deterministic interface-map validation finding."""

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


def validate_doc_text(text: str) -> list[InterfaceMapFinding]:
    """Return findings for missing interface-map documentation anchors."""

    findings: list[InterfaceMapFinding] = []
    for phrase in REQUIRED_DOC_PHRASES:
        if phrase not in text:
            findings.append(
                InterfaceMapFinding(
                    "foundation_interface_map_doc_phrase_missing",
                    f"interface-map boundary doc missing required phrase: {phrase}",
                )
            )
    return findings


def validate_packet(payload: dict[str, Any]) -> list[InterfaceMapFinding]:
    """Return findings for interface-map witness drift."""

    findings: list[InterfaceMapFinding] = []
    findings.extend(validate_root_contract(payload))
    findings.extend(validate_interface_map_surfaces(payload.get("interface_map_surfaces")))
    findings.extend(validate_forbidden_value_patterns(payload))
    findings.extend(validate_forbidden_promotion_patterns(payload))
    return findings


def validate_root_contract(payload: dict[str, Any]) -> list[InterfaceMapFinding]:
    """Return findings for root-level interface-map witness drift."""

    findings: list[InterfaceMapFinding] = []
    if set(payload) != EXPECTED_ROOT_KEYS:
        findings.append(
            InterfaceMapFinding(
                "interface_map_root_keys_invalid",
                f"root keys must be: {', '.join(sorted(EXPECTED_ROOT_KEYS))}",
            )
        )
    expected_values = {
        "witness_id": EXPECTED_WITNESS_ID,
        "schema_version": 1,
        "status": "AwaitingEvidence",
        "solver_outcome": "AwaitingEvidence",
        "interface_map_complete_claimed": False,
        "interface_contract_ready_claimed": False,
        "endpoint_ready_claimed": False,
        "service_binding_claimed": False,
        "event_message_ready_claimed": False,
        "data_flow_ready_claimed": False,
        "trust_boundary_closed_claimed": False,
        "integration_ready_claimed": False,
        "runtime_ready_claimed": False,
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
                InterfaceMapFinding(
                    "interface_map_root_value_invalid",
                    f"{key} must be {expected_value!r}",
                )
            )
    if tuple(payload.get("blocked_claims") or ()) != EXPECTED_BLOCKED_CLAIMS:
        findings.append(
            InterfaceMapFinding(
                "interface_map_blocked_claims_invalid",
                f"blocked_claims must be: {', '.join(EXPECTED_BLOCKED_CLAIMS)}",
            )
        )
    next_action = payload.get("next_action")
    if not isinstance(next_action, str) or "continue local interface map question drafting" not in next_action:
        findings.append(
            InterfaceMapFinding(
                "interface_map_next_action_invalid",
                "next_action must preserve local interface map drafting without readiness promotion",
            )
        )
    return findings


def validate_interface_map_surfaces(interface_map_surfaces: object) -> list[InterfaceMapFinding]:
    """Return findings for interface-map surface drift."""

    findings: list[InterfaceMapFinding] = []
    if not isinstance(interface_map_surfaces, list) or not all(
        isinstance(surface, dict) for surface in interface_map_surfaces
    ):
        return [
            InterfaceMapFinding(
                "interface_map_surfaces_invalid",
                "interface_map_surfaces must be a list of objects",
            )
        ]
    observed_surfaces = tuple(
        (surface.get("surface_id"), surface.get("surface_type"), surface.get("state"))
        for surface in interface_map_surfaces
    )
    if observed_surfaces != EXPECTED_SURFACES:
        findings.append(
            InterfaceMapFinding(
                "interface_map_surface_inventory_invalid",
                "interface-map surface inventory does not match the Foundation Mode interface set",
            )
        )
    surface_ids = [surface.get("surface_id") for surface in interface_map_surfaces]
    if len(set(surface_ids)) != len(surface_ids):
        findings.append(InterfaceMapFinding("interface_map_surface_duplicate", "surface ids must be unique"))
    for surface in interface_map_surfaces:
        surface_id = str(surface.get("surface_id", "<missing>"))
        if set(surface) != EXPECTED_SURFACE_KEYS:
            findings.append(
                InterfaceMapFinding(
                    "interface_map_surface_keys_invalid",
                    f"{surface_id} surface keys must be: {', '.join(sorted(EXPECTED_SURFACE_KEYS))}",
                )
            )
        if surface.get("state") != "AwaitingEvidence":
            findings.append(
                InterfaceMapFinding(
                    "interface_map_surface_state_invalid",
                    f"{surface_id} state must be AwaitingEvidence",
                )
            )
        if surface.get("evidence_ref") != "manual_preparation_pending":
            findings.append(
                InterfaceMapFinding(
                    "interface_map_surface_evidence_invalid",
                    f"{surface_id} evidence_ref must stay manual_preparation_pending in the committed packet",
                )
            )
        if not isinstance(surface.get("public_safe_note"), str) or not surface["public_safe_note"].strip():
            findings.append(
                InterfaceMapFinding(
                    "interface_map_surface_note_invalid",
                    f"{surface_id} public_safe_note must be a non-empty string",
                )
            )
    return findings


def validate_forbidden_value_patterns(payload: dict[str, Any]) -> list[InterfaceMapFinding]:
    """Return findings for private, endpoint, account, customer, secret, service, test, or deployment values."""

    serialized_payload = json.dumps(payload, sort_keys=True)
    findings: list[InterfaceMapFinding] = []
    for rule_id, pattern in FORBIDDEN_VALUE_PATTERNS:
        if pattern.search(serialized_payload):
            findings.append(
                InterfaceMapFinding(
                    "interface_map_forbidden_private_value_pattern",
                    f"interface-map witness contains forbidden value pattern: {rule_id}",
                )
            )
    return findings


def validate_forbidden_promotion_patterns(payload: dict[str, Any]) -> list[InterfaceMapFinding]:
    """Return findings if the witness drifts into interface-readiness promotion phrases."""

    serialized_payload = json.dumps(payload, sort_keys=True)
    findings: list[InterfaceMapFinding] = []
    for rule_id, pattern in FORBIDDEN_PROMOTION_PATTERNS:
        if pattern.search(serialized_payload):
            findings.append(
                InterfaceMapFinding(
                    "interface_map_forbidden_promotion_phrase",
                    f"interface-map witness contains forbidden promotion pattern: {rule_id}",
                )
            )
    return findings


def validate_foundation_interface_map_boundary(
    doc_path: Path = DEFAULT_DOC_PATH,
    packet_path: Path = DEFAULT_PACKET_PATH,
) -> list[InterfaceMapFinding]:
    """Validate the Foundation Mode interface-map boundary artifacts."""

    doc_text = load_text(doc_path, "interface-map boundary doc")
    packet_payload = load_json_object(packet_path, "interface-map witness packet")
    return [
        *validate_doc_text(doc_text),
        *validate_packet(packet_payload),
    ]


def main(argv: list[str] | None = None) -> int:
    """Validate interface-map artifacts and print deterministic status."""

    parser = argparse.ArgumentParser(description="Validate Foundation Mode interface-map artifacts.")
    parser.add_argument("--doc", type=Path, default=DEFAULT_DOC_PATH)
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET_PATH)
    args = parser.parse_args(argv)

    try:
        findings = validate_foundation_interface_map_boundary(args.doc, args.packet)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"[FAIL] foundation_interface_map_load: {exc}", file=sys.stderr)
        print("STATUS: failed", file=sys.stderr)
        return 1

    if findings:
        for finding in findings:
            print(f"[FAIL] {finding.rule_id}: {finding.message}", file=sys.stderr)
        print("STATUS: failed", file=sys.stderr)
        return 1
    print("[PASS] foundation_interface_map_doc")
    print("[PASS] foundation_interface_map_witness")
    print("STATUS: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
