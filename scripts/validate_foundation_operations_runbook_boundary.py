#!/usr/bin/env python3
"""Validate the Foundation Mode operations/runbook boundary.

Purpose: keep operations and runbook preparation local while runbook execution,
incident-response readiness, monitoring readiness, alerting readiness, on-call
readiness, SLO readiness, recovery readiness, operational graph completeness,
MIL runbook admission readiness, customer-support operations, publication, and
deployment claims remain blocked.
Governance scope: Foundation Mode, operations/runbook questions, private-value
exclusion, customer-support blocking, publication blocking, and deployment
blocking.
Dependencies: docs/FOUNDATION_OPERATIONS_RUNBOOK_BOUNDARY.md and
examples/foundation_operations_runbook_witness.awaiting_evidence.json.
Invariants:
  - Validation is read-only.
  - The witness records local operations/runbook planning only.
  - No operational readiness, customer-support, publication, or deployment
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
DEFAULT_DOC_PATH = REPO_ROOT / "docs" / "FOUNDATION_OPERATIONS_RUNBOOK_BOUNDARY.md"
DEFAULT_PACKET_PATH = REPO_ROOT / "examples" / "foundation_operations_runbook_witness.awaiting_evidence.json"

EXPECTED_WITNESS_ID = "foundation_operations_runbook_witness.awaiting_evidence.v1"
EXPECTED_BLOCKED_CLAIMS = (
    "runbook execution",
    "incident-response readiness",
    "monitoring readiness",
    "alerting readiness",
    "on-call readiness",
    "SLO or error-budget readiness",
    "recovery readiness",
    "operational graph completeness",
    "MIL runbook admission readiness",
    "customer-support operations",
    "external publication",
    "deployment readiness",
)
EXPECTED_SURFACES = (
    ("runbook_inventory_questions", "local_draft", "AwaitingEvidence"),
    ("procedure_dry_run_questions", "local_draft", "AwaitingEvidence"),
    ("incident_response_questions", "local_draft", "AwaitingEvidence"),
    ("monitoring_alert_questions", "local_draft", "AwaitingEvidence"),
    ("on_call_escalation_questions", "local_draft", "AwaitingEvidence"),
    ("slo_error_budget_questions", "local_draft", "AwaitingEvidence"),
    ("rollback_recovery_questions", "local_draft", "AwaitingEvidence"),
    ("operational_graph_questions", "local_draft", "AwaitingEvidence"),
    ("mil_audit_runbook_questions", "local_draft", "AwaitingEvidence"),
    ("evidence_promotion_questions", "local_draft", "AwaitingEvidence"),
)
EXPECTED_ROOT_KEYS = {
    "alerting_ready",
    "blocked_claims",
    "customer_support_operations_allowed",
    "deployment_allowed",
    "external_publication_allowed",
    "incident_response_ready",
    "mil_runbook_admission_ready",
    "monitoring_ready",
    "next_action",
    "on_call_ready",
    "operational_graph_complete",
    "operations_runbook_claimed",
    "operations_runbook_surfaces",
    "recovery_ready",
    "runbook_execution_allowed",
    "schema_version",
    "slo_claimed",
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
    "Foundation Operations Runbook Boundary",
    "Witness packet: [`../examples/foundation_operations_runbook_witness.awaiting_evidence.json`]",
    "Rule: Operations/runbook preparation is a local planning boundary, not a runbook-execution, incident-response, monitoring, on-call, SLO, recovery-readiness, customer-support, publication, or deployment certificate.",
    "No runbook execution, incident-response readiness, monitoring readiness,",
    "operations_runbook_boundary_state=AwaitingEvidence",
    "operations_runbook_claimed=false",
    "runbook_execution_allowed=false",
    "incident_response_ready=false",
    "monitoring_ready=false",
    "alerting_ready=false",
    "on_call_ready=false",
    "slo_claimed=false",
    "recovery_ready=false",
    "operational_graph_complete=false",
    "mil_runbook_admission_ready=false",
    "customer_support_operations_allowed=false",
    "external_publication_allowed=false",
    "deployment_allowed=false",
    "python scripts/validate_foundation_operations_runbook_boundary.py",
)
FORBIDDEN_VALUE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("url_value", re.compile(r"https?://", re.IGNORECASE)),
    ("email_value", re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)),
    ("private_path", re.compile(r"\b[A-Za-z]:[\\/]|\\\\", re.IGNORECASE)),
    (
        "operations_assignment",
        re.compile(
            r"\b(?:runbook|incident|monitor|alert|pager|on[_ -]?call|slo|recovery|rollback|customer|provider|service)[_ -]?(?:id|url|email|target|value|status|route|path)?\s*=",
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
    ("runbook_execution_ready", re.compile(r"\brunbook\s+(?:execution\s+)?(?:is\s+)?(?:ready|verified|allowed)\b", re.IGNORECASE)),
    ("incident_response_ready", re.compile(r"\bincident[- ]response\s+(?:is\s+)?ready\b", re.IGNORECASE)),
    ("monitoring_ready", re.compile(r"\bmonitoring\s+(?:is\s+)?(?:ready|live|verified)\b", re.IGNORECASE)),
    ("alerting_ready", re.compile(r"\balerting\s+(?:is\s+)?(?:ready|live|verified)\b", re.IGNORECASE)),
    ("on_call_ready", re.compile(r"\bon[- ]call\s+(?:is\s+)?ready\b", re.IGNORECASE)),
    ("slo_ready", re.compile(r"\b(?:SLO|error[- ]budget)\s+(?:is\s+)?(?:ready|active|verified)\b", re.IGNORECASE)),
    ("recovery_ready", re.compile(r"\brecovery\s+(?:is\s+)?(?:ready|verified)\b", re.IGNORECASE)),
    ("operational_graph_complete", re.compile(r"\boperational\s+graph\s+(?:is\s+)?complete\b", re.IGNORECASE)),
    ("mil_runbook_ready", re.compile(r"\bMIL\s+runbook\s+admission\s+(?:is\s+)?ready\b", re.IGNORECASE)),
    ("customer_support_ready", re.compile(r"\bcustomer[- ]support\s+operations\s+(?:are\s+)?ready\b", re.IGNORECASE)),
    ("deployment_ready", re.compile(r"\bdeployment\s+(?:is\s+)?ready\b", re.IGNORECASE)),
)


@dataclass(frozen=True, slots=True)
class OperationsRunbookFinding:
    """One deterministic operations/runbook boundary validation finding."""

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


def validate_doc_text(text: str) -> list[OperationsRunbookFinding]:
    """Return findings for missing operations/runbook documentation anchors."""

    findings: list[OperationsRunbookFinding] = []
    for phrase in REQUIRED_DOC_PHRASES:
        if phrase not in text:
            findings.append(
                OperationsRunbookFinding(
                    "foundation_operations_runbook_doc_phrase_missing",
                    f"operations/runbook boundary doc missing required phrase: {phrase}",
                )
            )
    return findings


def validate_packet(payload: dict[str, Any]) -> list[OperationsRunbookFinding]:
    """Return findings for operations/runbook witness drift."""

    findings: list[OperationsRunbookFinding] = []
    findings.extend(validate_root_contract(payload))
    findings.extend(validate_operations_runbook_surfaces(payload.get("operations_runbook_surfaces")))
    findings.extend(validate_forbidden_value_patterns(payload))
    findings.extend(validate_forbidden_promotion_patterns(payload))
    return findings


def validate_root_contract(payload: dict[str, Any]) -> list[OperationsRunbookFinding]:
    """Return findings for root-level operations/runbook witness drift."""

    findings: list[OperationsRunbookFinding] = []
    if set(payload) != EXPECTED_ROOT_KEYS:
        findings.append(
            OperationsRunbookFinding(
                "operations_runbook_root_keys_invalid",
                f"root keys must be: {', '.join(sorted(EXPECTED_ROOT_KEYS))}",
            )
        )
    expected_values = {
        "witness_id": EXPECTED_WITNESS_ID,
        "schema_version": 1,
        "status": "AwaitingEvidence",
        "solver_outcome": "AwaitingEvidence",
        "operations_runbook_claimed": False,
        "runbook_execution_allowed": False,
        "incident_response_ready": False,
        "monitoring_ready": False,
        "alerting_ready": False,
        "on_call_ready": False,
        "slo_claimed": False,
        "recovery_ready": False,
        "operational_graph_complete": False,
        "mil_runbook_admission_ready": False,
        "customer_support_operations_allowed": False,
        "external_publication_allowed": False,
        "deployment_allowed": False,
    }
    for key, expected_value in expected_values.items():
        if payload.get(key) != expected_value:
            findings.append(
                OperationsRunbookFinding(
                    "operations_runbook_root_value_invalid",
                    f"{key} must be {expected_value!r}",
                )
            )
    if tuple(payload.get("blocked_claims") or ()) != EXPECTED_BLOCKED_CLAIMS:
        findings.append(
            OperationsRunbookFinding(
                "operations_runbook_blocked_claims_invalid",
                f"blocked_claims must be: {', '.join(EXPECTED_BLOCKED_CLAIMS)}",
            )
        )
    next_action = payload.get("next_action")
    if not isinstance(next_action, str) or "keep operations and runbook preparation local" not in next_action:
        findings.append(
            OperationsRunbookFinding(
                "operations_runbook_next_action_invalid",
                "next_action must preserve the local operations/runbook boundary",
            )
        )
    return findings


def validate_operations_runbook_surfaces(
    operations_runbook_surfaces: object,
) -> list[OperationsRunbookFinding]:
    """Return findings for operations/runbook surface witness drift."""

    findings: list[OperationsRunbookFinding] = []
    if not isinstance(operations_runbook_surfaces, list) or not all(
        isinstance(surface, dict) for surface in operations_runbook_surfaces
    ):
        return [
            OperationsRunbookFinding(
                "operations_runbook_surfaces_invalid",
                "operations_runbook_surfaces must be a list of objects",
            )
        ]
    observed_surfaces = tuple(
        (surface.get("surface_id"), surface.get("surface_type"), surface.get("state"))
        for surface in operations_runbook_surfaces
    )
    if observed_surfaces != EXPECTED_SURFACES:
        findings.append(
            OperationsRunbookFinding(
                "operations_runbook_surface_inventory_invalid",
                "operations/runbook surface inventory does not match the Foundation Mode set",
            )
        )
    surface_ids = [surface.get("surface_id") for surface in operations_runbook_surfaces]
    if len(set(surface_ids)) != len(surface_ids):
        findings.append(OperationsRunbookFinding("operations_runbook_surface_duplicate", "surface ids must be unique"))
    for surface in operations_runbook_surfaces:
        surface_id = str(surface.get("surface_id", "<missing>"))
        if set(surface) != EXPECTED_SURFACE_KEYS:
            findings.append(
                OperationsRunbookFinding(
                    "operations_runbook_surface_keys_invalid",
                    f"{surface_id} surface keys must be: {', '.join(sorted(EXPECTED_SURFACE_KEYS))}",
                )
            )
        if surface.get("state") != "AwaitingEvidence":
            findings.append(
                OperationsRunbookFinding(
                    "operations_runbook_surface_state_invalid",
                    f"{surface_id} state must be AwaitingEvidence",
                )
            )
        if surface.get("evidence_ref") != "manual_preparation_pending":
            findings.append(
                OperationsRunbookFinding(
                    "operations_runbook_surface_evidence_invalid",
                    f"{surface_id} evidence_ref must stay manual_preparation_pending in the committed packet",
                )
            )
        if not isinstance(surface.get("public_safe_note"), str) or not surface["public_safe_note"].strip():
            findings.append(
                OperationsRunbookFinding(
                    "operations_runbook_surface_note_invalid",
                    f"{surface_id} public_safe_note must be a non-empty string",
                )
            )
    return findings


def validate_forbidden_value_patterns(payload: dict[str, Any]) -> list[OperationsRunbookFinding]:
    """Return findings for private, operational, account, or secret-shaped values."""

    serialized_payload = json.dumps(payload, sort_keys=True)
    findings: list[OperationsRunbookFinding] = []
    for rule_id, pattern in FORBIDDEN_VALUE_PATTERNS:
        if pattern.search(serialized_payload):
            findings.append(
                OperationsRunbookFinding(
                    "operations_runbook_forbidden_private_value_pattern",
                    f"operations/runbook witness contains forbidden private value pattern: {rule_id}",
                )
            )
    return findings


def validate_forbidden_promotion_patterns(payload: dict[str, Any]) -> list[OperationsRunbookFinding]:
    """Return findings for operations/runbook verification or readiness claims."""

    serialized_payload = json.dumps(payload, sort_keys=True)
    findings: list[OperationsRunbookFinding] = []
    for rule_id, pattern in FORBIDDEN_PROMOTION_PATTERNS:
        if pattern.search(serialized_payload):
            findings.append(
                OperationsRunbookFinding(
                    "operations_runbook_forbidden_promotion_phrase",
                    f"operations/runbook witness contains forbidden promotion phrase: {rule_id}",
                )
            )
    return findings


def validate_foundation_operations_runbook_boundary(
    doc_path: Path = DEFAULT_DOC_PATH,
    packet_path: Path = DEFAULT_PACKET_PATH,
) -> list[OperationsRunbookFinding]:
    """Return all operations/runbook boundary validation findings."""

    doc_text = load_text(doc_path, "operations/runbook boundary doc")
    payload = load_json_object(packet_path, "operations/runbook witness")
    findings: list[OperationsRunbookFinding] = []
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
    """Run the operations/runbook boundary validator."""

    args = parse_args()
    findings = validate_foundation_operations_runbook_boundary(args.doc, args.packet)
    if findings:
        for finding in findings:
            print(f"[FAIL] {finding.rule_id}: {finding.message}", file=sys.stderr)
        print("STATUS: failed", file=sys.stderr)
        return 1
    print("[PASS] foundation_operations_runbook_doc")
    print("[PASS] foundation_operations_runbook_witness")
    print("STATUS: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
