#!/usr/bin/env python3
"""Validate the Foundation Mode module-inventory boundary.

Purpose: keep module inventory mapping local and public-safe while module
inventory completeness, ownership assignment, contract readiness, interface
readiness, dependency readiness, integration readiness, runtime readiness,
refactor approval, implementation approval, publication, and deployment claims
remain blocked.
Governance scope: Foundation Mode, product modules, control-plane modules,
gateway modules, runtime modules, governance modules, evidence modules, data
modules, operator modules, private-value exclusion, and readiness blocking.
Dependencies: docs/FOUNDATION_MODULE_INVENTORY_BOUNDARY.md and
examples/foundation_module_inventory_witness.awaiting_evidence.json.
Invariants:
  - Validation is read-only.
  - The witness records module-inventory preparation only.
  - No completeness, ownership, contract, readiness, approval, publication, or
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
DEFAULT_DOC_PATH = REPO_ROOT / "docs" / "FOUNDATION_MODULE_INVENTORY_BOUNDARY.md"
DEFAULT_PACKET_PATH = REPO_ROOT / "examples" / "foundation_module_inventory_witness.awaiting_evidence.json"

EXPECTED_WITNESS_ID = "foundation_module_inventory_witness.awaiting_evidence.v1"
EXPECTED_BLOCKED_CLAIMS = (
    "module inventory completeness",
    "module ownership assignment",
    "module contract readiness",
    "interface readiness",
    "dependency readiness",
    "integration readiness",
    "runtime readiness",
    "refactor approval",
    "implementation approval",
    "external publication",
    "deployment readiness",
)
EXPECTED_SURFACES = (
    ("product_modules", "local_draft", "AwaitingEvidence"),
    ("control_plane_modules", "local_draft", "AwaitingEvidence"),
    ("gateway_modules", "local_draft", "AwaitingEvidence"),
    ("runtime_modules", "local_draft", "AwaitingEvidence"),
    ("governance_modules", "local_draft", "AwaitingEvidence"),
    ("evidence_modules", "local_draft", "AwaitingEvidence"),
    ("data_modules", "local_draft", "AwaitingEvidence"),
    ("operator_modules", "local_draft", "AwaitingEvidence"),
)
EXPECTED_ROOT_KEYS = {
    "blocked_claims",
    "dependency_ready_claimed",
    "deployment_allowed",
    "external_publication_allowed",
    "implementation_approval_allowed",
    "integration_ready_claimed",
    "interface_ready_claimed",
    "module_contract_ready_claimed",
    "module_inventory_complete_claimed",
    "module_inventory_surfaces",
    "module_ownership_assigned",
    "next_action",
    "refactor_approval_allowed",
    "runtime_ready_claimed",
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
    "Foundation Module Inventory Boundary",
    "Witness packet: [`../examples/foundation_module_inventory_witness.awaiting_evidence.json`]",
    "Rule: Module-inventory preparation is a local planning boundary, not a module-inventory-completion",
    "No module inventory completeness, module ownership assignment, module contract",
    "module_inventory_boundary_state=AwaitingEvidence",
    "module_inventory_complete_claimed=false",
    "module_ownership_assigned=false",
    "module_contract_ready_claimed=false",
    "implementation_approval_allowed=false",
    "deployment_allowed=false",
    "python scripts/validate_foundation_module_inventory_boundary.py",
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
        "publication_or_deployment_assignment",
        re.compile(
            r"\b(?:publish|publication|deploy|deployment|production)[_ -]?"
            r"(?:id|url|ref|target|value|status)?\s*=",
            re.IGNORECASE,
        ),
    ),
)
FORBIDDEN_PROMOTION_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("inventory_complete", re.compile(r"\bmodule\s+inventory\s+(?:is\s+)?complete\b", re.IGNORECASE)),
    ("ownership_assigned", re.compile(r"\bmodule\s+ownership\s+(?:is\s+)?assigned\b", re.IGNORECASE)),
    ("contract_ready", re.compile(r"\bmodule\s+contract\s+(?:is\s+)?ready\b", re.IGNORECASE)),
    ("interface_ready", re.compile(r"\binterface\s+(?:is\s+)?ready\b", re.IGNORECASE)),
    ("dependency_ready", re.compile(r"\bdependency\s+(?:is\s+)?ready\b", re.IGNORECASE)),
    ("integration_ready", re.compile(r"\bintegration\s+(?:is\s+)?ready\b", re.IGNORECASE)),
    ("runtime_ready", re.compile(r"\bruntime\s+(?:is\s+)?ready\b", re.IGNORECASE)),
    ("refactor_approved", re.compile(r"\brefactor\s+(?:is\s+)?approved\b", re.IGNORECASE)),
    ("implementation_approved", re.compile(r"\bimplementation\s+(?:is\s+)?approved\b", re.IGNORECASE)),
    ("published_externally", re.compile(r"\bpublished\s+externally\b", re.IGNORECASE)),
    ("deployment_ready", re.compile(r"\bdeployment\s+(?:is\s+)?ready\b", re.IGNORECASE)),
)


@dataclass(frozen=True, slots=True)
class ModuleInventoryFinding:
    """One deterministic module-inventory validation finding."""

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


def validate_doc_text(text: str) -> list[ModuleInventoryFinding]:
    """Return findings for missing module-inventory documentation anchors."""

    findings: list[ModuleInventoryFinding] = []
    for phrase in REQUIRED_DOC_PHRASES:
        if phrase not in text:
            findings.append(
                ModuleInventoryFinding(
                    "foundation_module_inventory_doc_phrase_missing",
                    f"module-inventory boundary doc missing required phrase: {phrase}",
                )
            )
    return findings


def validate_packet(payload: dict[str, Any]) -> list[ModuleInventoryFinding]:
    """Return findings for module-inventory witness drift."""

    findings: list[ModuleInventoryFinding] = []
    findings.extend(validate_root_contract(payload))
    findings.extend(validate_module_inventory_surfaces(payload.get("module_inventory_surfaces")))
    findings.extend(validate_forbidden_value_patterns(payload))
    findings.extend(validate_forbidden_promotion_patterns(payload))
    return findings


def validate_root_contract(payload: dict[str, Any]) -> list[ModuleInventoryFinding]:
    """Return findings for root-level module-inventory witness drift."""

    findings: list[ModuleInventoryFinding] = []
    if set(payload) != EXPECTED_ROOT_KEYS:
        findings.append(
            ModuleInventoryFinding(
                "module_inventory_root_keys_invalid",
                f"root keys must be: {', '.join(sorted(EXPECTED_ROOT_KEYS))}",
            )
        )
    expected_values = {
        "witness_id": EXPECTED_WITNESS_ID,
        "schema_version": 1,
        "status": "AwaitingEvidence",
        "solver_outcome": "AwaitingEvidence",
        "module_inventory_complete_claimed": False,
        "module_ownership_assigned": False,
        "module_contract_ready_claimed": False,
        "interface_ready_claimed": False,
        "dependency_ready_claimed": False,
        "integration_ready_claimed": False,
        "runtime_ready_claimed": False,
        "refactor_approval_allowed": False,
        "implementation_approval_allowed": False,
        "external_publication_allowed": False,
        "deployment_allowed": False,
    }
    for key, expected_value in expected_values.items():
        if payload.get(key) != expected_value:
            findings.append(
                ModuleInventoryFinding(
                    "module_inventory_root_value_invalid",
                    f"{key} must be {expected_value!r}",
                )
            )
    if tuple(payload.get("blocked_claims") or ()) != EXPECTED_BLOCKED_CLAIMS:
        findings.append(
            ModuleInventoryFinding(
                "module_inventory_blocked_claims_invalid",
                f"blocked_claims must be: {', '.join(EXPECTED_BLOCKED_CLAIMS)}",
            )
        )
    next_action = payload.get("next_action")
    if not isinstance(next_action, str) or "continue local module inventory mapping" not in next_action:
        findings.append(
            ModuleInventoryFinding(
                "module_inventory_next_action_invalid",
                "next_action must preserve local module inventory mapping without readiness promotion",
            )
        )
    return findings


def validate_module_inventory_surfaces(module_inventory_surfaces: object) -> list[ModuleInventoryFinding]:
    """Return findings for module-inventory surface drift."""

    findings: list[ModuleInventoryFinding] = []
    if not isinstance(module_inventory_surfaces, list) or not all(
        isinstance(surface, dict) for surface in module_inventory_surfaces
    ):
        return [
            ModuleInventoryFinding(
                "module_inventory_surfaces_invalid",
                "module_inventory_surfaces must be a list of objects",
            )
        ]
    observed_surfaces = tuple(
        (surface.get("surface_id"), surface.get("surface_type"), surface.get("state"))
        for surface in module_inventory_surfaces
    )
    if observed_surfaces != EXPECTED_SURFACES:
        findings.append(
            ModuleInventoryFinding(
                "module_inventory_surface_inventory_invalid",
                "module-inventory surface inventory does not match the Foundation Mode module set",
            )
        )
    surface_ids = [surface.get("surface_id") for surface in module_inventory_surfaces]
    if len(set(surface_ids)) != len(surface_ids):
        findings.append(ModuleInventoryFinding("module_inventory_surface_duplicate", "surface ids must be unique"))
    for surface in module_inventory_surfaces:
        surface_id = str(surface.get("surface_id", "<missing>"))
        if set(surface) != EXPECTED_SURFACE_KEYS:
            findings.append(
                ModuleInventoryFinding(
                    "module_inventory_surface_keys_invalid",
                    f"{surface_id} surface keys must be: {', '.join(sorted(EXPECTED_SURFACE_KEYS))}",
                )
            )
        if surface.get("state") != "AwaitingEvidence":
            findings.append(
                ModuleInventoryFinding(
                    "module_inventory_surface_state_invalid",
                    f"{surface_id} state must be AwaitingEvidence",
                )
            )
        if surface.get("evidence_ref") != "manual_preparation_pending":
            findings.append(
                ModuleInventoryFinding(
                    "module_inventory_surface_evidence_invalid",
                    f"{surface_id} evidence_ref must stay manual_preparation_pending in the committed packet",
                )
            )
        if not isinstance(surface.get("public_safe_note"), str) or not surface["public_safe_note"].strip():
            findings.append(
                ModuleInventoryFinding(
                    "module_inventory_surface_note_invalid",
                    f"{surface_id} public_safe_note must be a non-empty string",
                )
            )
    return findings


def validate_forbidden_value_patterns(payload: dict[str, Any]) -> list[ModuleInventoryFinding]:
    """Return findings for private, endpoint, account, customer, secret, service, or deployment-shaped values."""

    serialized_payload = json.dumps(payload, sort_keys=True)
    findings: list[ModuleInventoryFinding] = []
    for rule_id, pattern in FORBIDDEN_VALUE_PATTERNS:
        if pattern.search(serialized_payload):
            findings.append(
                ModuleInventoryFinding(
                    "module_inventory_forbidden_private_value_pattern",
                    f"module-inventory witness contains forbidden value pattern: {rule_id}",
                )
            )
    return findings


def validate_forbidden_promotion_patterns(payload: dict[str, Any]) -> list[ModuleInventoryFinding]:
    """Return findings if the witness drifts into module-readiness promotion phrases."""

    serialized_payload = json.dumps(payload, sort_keys=True)
    findings: list[ModuleInventoryFinding] = []
    for rule_id, pattern in FORBIDDEN_PROMOTION_PATTERNS:
        if pattern.search(serialized_payload):
            findings.append(
                ModuleInventoryFinding(
                    "module_inventory_forbidden_promotion_phrase",
                    f"module-inventory witness contains forbidden promotion pattern: {rule_id}",
                )
            )
    return findings


def validate_foundation_module_inventory_boundary(
    doc_path: Path = DEFAULT_DOC_PATH,
    packet_path: Path = DEFAULT_PACKET_PATH,
) -> list[ModuleInventoryFinding]:
    """Validate the Foundation Mode module-inventory boundary artifacts."""

    doc_text = load_text(doc_path, "module-inventory boundary doc")
    packet_payload = load_json_object(packet_path, "module-inventory witness packet")
    return [
        *validate_doc_text(doc_text),
        *validate_packet(packet_payload),
    ]


def main(argv: list[str] | None = None) -> int:
    """Validate module-inventory artifacts and print deterministic status."""

    parser = argparse.ArgumentParser(description="Validate Foundation Mode module-inventory artifacts.")
    parser.add_argument("--doc", type=Path, default=DEFAULT_DOC_PATH)
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET_PATH)
    args = parser.parse_args(argv)

    try:
        findings = validate_foundation_module_inventory_boundary(args.doc, args.packet)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"[FAIL] foundation_module_inventory_load: {exc}", file=sys.stderr)
        print("STATUS: failed", file=sys.stderr)
        return 1

    if findings:
        for finding in findings:
            print(f"[FAIL] {finding.rule_id}: {finding.message}", file=sys.stderr)
        print("STATUS: failed", file=sys.stderr)
        return 1
    print("[PASS] foundation_module_inventory_doc")
    print("[PASS] foundation_module_inventory_witness")
    print("STATUS: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
