#!/usr/bin/env python3
"""Validate the Foundation Mode agentic-management boundary.

Purpose: keep agentic-management preparation local while autonomous management,
task execution, delegation activation, scheduling commitments, resource
allocation, budget commitments, approval bypass, customer commitments,
money movement, publication, and deployment claims remain blocked.
Governance scope: Foundation Mode, public-safe management-control questions,
private-value exclusion, approval-bypass blocking, money-movement blocking,
publication blocking, and deployment blocking.
Dependencies: docs/FOUNDATION_AGENTIC_MANAGEMENT_BOUNDARY.md and
examples/foundation_agentic_management_witness.awaiting_evidence.json.
Invariants:
  - Validation is read-only.
  - The witness records local agentic-management planning only.
  - No management authority, task execution, delegation, schedule, allocation,
    approval-bypass, customer, money-movement, publication, or deployment claim
    is allowed.
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
DEFAULT_DOC_PATH = REPO_ROOT / "docs" / "FOUNDATION_AGENTIC_MANAGEMENT_BOUNDARY.md"
DEFAULT_PACKET_PATH = REPO_ROOT / "examples" / "foundation_agentic_management_witness.awaiting_evidence.json"

EXPECTED_WITNESS_ID = "foundation_agentic_management_witness.awaiting_evidence.v1"
EXPECTED_BLOCKED_CLAIMS = (
    "autonomous management authority",
    "task execution authority",
    "delegation activation",
    "scheduling commitment",
    "resource allocation approval",
    "budget commitment",
    "final priority claim",
    "approval bypass",
    "live monitoring claim",
    "operator replacement claim",
    "customer commitment",
    "money movement",
    "external publication",
    "deployment readiness",
)
EXPECTED_SURFACES = (
    ("goal_intake_questions", "local_draft", "AwaitingEvidence"),
    ("plan_decomposition_questions", "local_draft", "AwaitingEvidence"),
    ("delegation_questions", "local_draft", "AwaitingEvidence"),
    ("schedule_queue_questions", "local_draft", "AwaitingEvidence"),
    ("resource_budget_questions", "local_draft", "AwaitingEvidence"),
    ("priority_tradeoff_questions", "local_draft", "AwaitingEvidence"),
    ("escalation_approval_questions", "local_draft", "AwaitingEvidence"),
    ("progress_receipt_questions", "local_draft", "AwaitingEvidence"),
    ("rollback_recovery_questions", "local_draft", "AwaitingEvidence"),
    ("performance_review_questions", "local_draft", "AwaitingEvidence"),
)
EXPECTED_ROOT_VALUES = {
    "witness_id": EXPECTED_WITNESS_ID,
    "schema_version": 1,
    "status": "AwaitingEvidence",
    "solver_outcome": "AwaitingEvidence",
    "agentic_management_claimed": False,
    "autonomous_management_authority_claimed": False,
    "task_execution_authority_allowed": False,
    "delegation_activation_allowed": False,
    "scheduling_commitment_allowed": False,
    "resource_allocation_approved": False,
    "budget_commitment_allowed": False,
    "priority_final_claimed": False,
    "approval_bypass_allowed": False,
    "live_monitoring_claimed": False,
    "operator_replacement_claimed": False,
    "customer_commitment_allowed": False,
    "money_movement_allowed": False,
    "external_publication_allowed": False,
    "deployment_allowed": False,
}
EXPECTED_ROOT_KEYS = set(EXPECTED_ROOT_VALUES) | {
    "agentic_management_surfaces",
    "blocked_claims",
    "next_action",
}
EXPECTED_SURFACE_KEYS = {
    "evidence_ref",
    "public_safe_note",
    "state",
    "surface_id",
    "surface_type",
}
REQUIRED_DOC_PHRASES = (
    "Foundation Agentic Management Boundary",
    "Witness packet: [`../examples/foundation_agentic_management_witness.awaiting_evidence.json`]",
    "Rule: Agentic-management preparation is a local planning boundary, not an autonomous-management, task-execution, delegation, scheduling, resource-allocation, approval-bypass, customer, money-movement, publication, or deployment certificate.",
    "No autonomous management authority, task execution authority, delegation",
    "agentic_management_boundary_state=AwaitingEvidence",
    "agentic_management_claimed=false",
    "autonomous_management_authority_claimed=false",
    "task_execution_authority_allowed=false",
    "delegation_activation_allowed=false",
    "scheduling_commitment_allowed=false",
    "resource_allocation_approved=false",
    "budget_commitment_allowed=false",
    "priority_final_claimed=false",
    "approval_bypass_allowed=false",
    "live_monitoring_claimed=false",
    "operator_replacement_claimed=false",
    "customer_commitment_allowed=false",
    "money_movement_allowed=false",
    "external_publication_allowed=false",
    "deployment_allowed=false",
    "python scripts/validate_foundation_agentic_management_boundary.py",
)
FORBIDDEN_VALUE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("url_value", re.compile(r"https?://", re.IGNORECASE)),
    ("email_value", re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)),
    ("private_path", re.compile(r"\b[A-Za-z]:[\\/]|\\\\", re.IGNORECASE)),
    (
        "management_assignment",
        re.compile(
            r"\b(?:worker|agent|task|schedule|queue|budget|resource|customer|provider|account)[_ -]?(?:id|url|email|target|value|status|owner|route|path)?\s*=",
            re.IGNORECASE,
        ),
    ),
    (
        "secret_assignment",
        re.compile(r"\b(?:password|secret|token|api[_ -]?key|client[_ -]?secret)\s*=", re.IGNORECASE),
    ),
    ("private_key_material", re.compile(r"BEGIN [A-Z ]*PRIVATE KEY")),
)
FORBIDDEN_PROMOTION_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("management_authority_ready", re.compile(r"\bautonomous management\s+(?:is\s+)?(?:ready|approved|allowed)\b", re.IGNORECASE)),
    ("task_execution_ready", re.compile(r"\btask execution\s+(?:is\s+)?(?:ready|approved|allowed)\b", re.IGNORECASE)),
    ("delegation_ready", re.compile(r"\bdelegation\s+(?:is\s+)?(?:active|ready|approved|allowed)\b", re.IGNORECASE)),
    ("schedule_committed", re.compile(r"\bschedul(?:e|ing)\s+(?:is\s+)?(?:committed|final|promised|guaranteed)\b", re.IGNORECASE)),
    ("resource_allocation_ready", re.compile(r"\bresource allocation\s+(?:is\s+)?(?:approved|ready|allowed)\b", re.IGNORECASE)),
    ("budget_ready", re.compile(r"\bbudget\s+(?:is\s+)?(?:committed|approved|ready)\b", re.IGNORECASE)),
    ("approval_bypass_ready", re.compile(r"\bapproval bypass\s+(?:is\s+)?(?:allowed|approved|ready)\b", re.IGNORECASE)),
    ("live_monitoring_ready", re.compile(r"\blive monitoring\s+(?:is\s+)?(?:ready|active|verified)\b", re.IGNORECASE)),
    ("operator_replaced", re.compile(r"\boperator\s+(?:replacement|replaced)\s+(?:is\s+)?(?:ready|approved|complete)\b", re.IGNORECASE)),
    ("customer_commitment_ready", re.compile(r"\bcustomer commitment\s+(?:is\s+)?(?:ready|approved)\b", re.IGNORECASE)),
    ("money_movement_ready", re.compile(r"\bmoney movement\s+(?:is\s+)?(?:ready|approved|allowed)\b", re.IGNORECASE)),
    ("deployment_ready", re.compile(r"\bdeployment\s+(?:is\s+)?ready\b", re.IGNORECASE)),
)


@dataclass(frozen=True, slots=True)
class AgenticManagementFinding:
    """One deterministic agentic-management boundary validation finding."""

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


def validate_doc_text(text: str) -> list[AgenticManagementFinding]:
    """Return findings for missing agentic-management documentation anchors."""

    return [
        AgenticManagementFinding(
            "foundation_agentic_management_doc_phrase_missing",
            f"agentic-management boundary doc missing required phrase: {phrase}",
        )
        for phrase in REQUIRED_DOC_PHRASES
        if phrase not in text
    ]


def validate_packet(payload: dict[str, Any]) -> list[AgenticManagementFinding]:
    """Return findings for agentic-management witness drift."""

    findings: list[AgenticManagementFinding] = []
    findings.extend(validate_root_contract(payload))
    findings.extend(validate_agentic_management_surfaces(payload.get("agentic_management_surfaces")))
    findings.extend(validate_forbidden_value_patterns(payload))
    findings.extend(validate_forbidden_promotion_patterns(payload))
    return findings


def validate_root_contract(payload: dict[str, Any]) -> list[AgenticManagementFinding]:
    """Return findings for root-level agentic-management witness drift."""

    findings: list[AgenticManagementFinding] = []
    if set(payload) != EXPECTED_ROOT_KEYS:
        findings.append(
            AgenticManagementFinding(
                "agentic_management_root_keys_invalid",
                f"root keys must be: {', '.join(sorted(EXPECTED_ROOT_KEYS))}",
            )
        )
    for key, expected_value in EXPECTED_ROOT_VALUES.items():
        if payload.get(key) != expected_value:
            findings.append(
                AgenticManagementFinding(
                    "agentic_management_root_value_invalid",
                    f"{key} must be {expected_value!r}",
                )
            )
    if tuple(payload.get("blocked_claims") or ()) != EXPECTED_BLOCKED_CLAIMS:
        findings.append(
            AgenticManagementFinding(
                "agentic_management_blocked_claims_invalid",
                f"blocked_claims must be: {', '.join(EXPECTED_BLOCKED_CLAIMS)}",
            )
        )
    next_action = payload.get("next_action")
    if not isinstance(next_action, str) or "keep agentic-management work local" not in next_action:
        findings.append(
            AgenticManagementFinding(
                "agentic_management_next_action_invalid",
                "next_action must preserve the local agentic-management boundary",
            )
        )
    return findings


def validate_agentic_management_surfaces(surfaces: object) -> list[AgenticManagementFinding]:
    """Return findings for agentic-management surface witness drift."""

    if not isinstance(surfaces, list) or not all(isinstance(surface, dict) for surface in surfaces):
        return [
            AgenticManagementFinding(
                "agentic_management_surfaces_invalid",
                "agentic_management_surfaces must be a list of objects",
            )
        ]
    findings: list[AgenticManagementFinding] = []
    observed_surfaces = tuple(
        (surface.get("surface_id"), surface.get("surface_type"), surface.get("state")) for surface in surfaces
    )
    if observed_surfaces != EXPECTED_SURFACES:
        findings.append(
            AgenticManagementFinding(
                "agentic_management_surface_inventory_invalid",
                "agentic-management surface inventory does not match the Foundation Mode management-control set",
            )
        )
    surface_ids = [surface.get("surface_id") for surface in surfaces]
    if len(set(surface_ids)) != len(surface_ids):
        findings.append(AgenticManagementFinding("agentic_management_surface_duplicate", "surface ids must be unique"))
    for surface in surfaces:
        surface_id = str(surface.get("surface_id", "<missing>"))
        if set(surface) != EXPECTED_SURFACE_KEYS:
            findings.append(
                AgenticManagementFinding(
                    "agentic_management_surface_keys_invalid",
                    f"{surface_id} surface keys must be: {', '.join(sorted(EXPECTED_SURFACE_KEYS))}",
                )
            )
        if surface.get("state") != "AwaitingEvidence":
            findings.append(
                AgenticManagementFinding(
                    "agentic_management_surface_state_invalid",
                    f"{surface_id} state must be AwaitingEvidence",
                )
            )
        if surface.get("evidence_ref") != "manual_preparation_pending":
            findings.append(
                AgenticManagementFinding(
                    "agentic_management_surface_evidence_invalid",
                    f"{surface_id} evidence_ref must stay manual_preparation_pending in the committed packet",
                )
            )
        if not isinstance(surface.get("public_safe_note"), str) or not surface["public_safe_note"].strip():
            findings.append(
                AgenticManagementFinding(
                    "agentic_management_surface_note_invalid",
                    f"{surface_id} public_safe_note must be a non-empty string",
                )
            )
    return findings


def validate_forbidden_value_patterns(payload: dict[str, Any]) -> list[AgenticManagementFinding]:
    """Return findings for private, worker, schedule, budget, account, or secret-shaped values."""

    serialized_payload = json.dumps(payload, sort_keys=True)
    return [
        AgenticManagementFinding(
            "agentic_management_forbidden_private_value_pattern",
            f"agentic-management witness contains forbidden private value pattern: {rule_id}",
        )
        for rule_id, pattern in FORBIDDEN_VALUE_PATTERNS
        if pattern.search(serialized_payload)
    ]


def validate_forbidden_promotion_patterns(payload: dict[str, Any]) -> list[AgenticManagementFinding]:
    """Return findings for agentic-management authority or readiness claims."""

    serialized_payload = json.dumps(payload, sort_keys=True)
    return [
        AgenticManagementFinding(
            "agentic_management_forbidden_promotion_phrase",
            f"agentic-management witness contains forbidden promotion phrase: {rule_id}",
        )
        for rule_id, pattern in FORBIDDEN_PROMOTION_PATTERNS
        if pattern.search(serialized_payload)
    ]


def validate_foundation_agentic_management_boundary(
    doc_path: Path = DEFAULT_DOC_PATH,
    packet_path: Path = DEFAULT_PACKET_PATH,
) -> list[AgenticManagementFinding]:
    """Return all agentic-management boundary validation findings."""

    doc_text = load_text(doc_path, "agentic-management boundary doc")
    payload = load_json_object(packet_path, "agentic-management witness")
    findings: list[AgenticManagementFinding] = []
    findings.extend(validate_doc_text(doc_text))
    findings.extend(validate_packet(payload))
    return findings


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--doc", type=Path, default=DEFAULT_DOC_PATH)
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET_PATH)
    return parser.parse_args()


def main() -> int:
    """Run the agentic-management boundary validator."""

    args = parse_args()
    findings = validate_foundation_agentic_management_boundary(args.doc, args.packet)
    if findings:
        for finding in findings:
            print(f"[FAIL] {finding.rule_id}: {finding.message}", file=sys.stderr)
        print("STATUS: failed", file=sys.stderr)
        return 1
    print("[PASS] foundation_agentic_management_doc")
    print("[PASS] foundation_agentic_management_witness")
    print("STATUS: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
