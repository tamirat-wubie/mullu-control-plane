#!/usr/bin/env python3
"""Validate the Foundation Mode deployment witness evidence ledger routing boundary.

Purpose: keep issue #330 deployment witness evidence ledger routing preparation
local and public-safe while ledger append, live evidence references, evidence
promotion, terminal closure, readiness claims, DNS proof, endpoint proof,
secret-presence claims, workflow run claims, artifact publication, deployment
status approval, operator approval, customer access, personal data, money
movement, legal/business claims, publication, and deployment remain blocked.
Governance scope: Foundation Mode, issue #330 evidence ledger routing,
public-safe route labels, evidence-ledger append blocking, promotion blocking,
external evidence blocking, approval blocking, secret exclusion, customer/data
blocking, money blocking, legal/business restraint, publication blocking, and
deployment blocking.
Dependencies: docs/FOUNDATION_DEPLOYMENT_WITNESS_EVIDENCE_LEDGER_ROUTING_BOUNDARY.md
and examples/foundation_deployment_witness_evidence_ledger_routing_witness.awaiting_evidence.json.
Invariants:
  - Validation is read-only.
  - The witness records public-safe evidence ledger route labels only.
  - No evidence-ledger append, live evidence reference, ledger promotion,
    terminal closure, readiness claim, DNS proof, endpoint proof, secret
    presence claim, workflow run claim, artifact publication, deployment
    status approval, operator approval, customer access, personal data, money
    movement, legal clearance, company formation, patent claim, external
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
DEFAULT_DOC_PATH = REPO_ROOT / "docs" / "FOUNDATION_DEPLOYMENT_WITNESS_EVIDENCE_LEDGER_ROUTING_BOUNDARY.md"
DEFAULT_PACKET_PATH = (
    REPO_ROOT / "examples" / "foundation_deployment_witness_evidence_ledger_routing_witness.awaiting_evidence.json"
)

EXPECTED_WITNESS_ID = "foundation_deployment_witness_evidence_ledger_routing_witness.awaiting_evidence.v1"
EXPECTED_ROUTE_LABELS = (
    "deployment_witness_receipt_to_evidence_ledger_entry",
    "gateway_readiness_report_to_evidence_ledger_entry",
    "closure_plan_receipt_to_evidence_ledger_entry",
    "dns_resolution_receipt_to_evidence_ledger_entry",
    "endpoint_probe_receipt_to_evidence_ledger_entry",
    "runtime_witness_receipt_to_evidence_ledger_entry",
    "runtime_conformance_receipt_to_evidence_ledger_entry",
    "workflow_run_receipt_to_evidence_ledger_entry",
    "artifact_publication_receipt_to_evidence_ledger_entry",
    "deployment_status_approval_to_evidence_ledger_entry",
    "operator_decision_to_evidence_ledger_entry",
    "evidence_ledger_reassessment_gate",
)
EXPECTED_BLOCKED_CLAIMS = (
    "evidence ledger append",
    "live evidence reference",
    "ledger promotion",
    "terminal closure",
    "readiness claim",
    "dns proof",
    "endpoint proof",
    "secret presence claim",
    "workflow run claim",
    "artifact publication",
    "deployment status approval",
    "operator approval",
    "customer access",
    "personal data collection",
    "money movement",
    "legal clearance",
    "company formation",
    "patent claim",
    "external publication",
    "deployment readiness",
)
EXPECTED_NEXT_ACTION = (
    "record public-safe evidence ledger route labels only; do not append live "
    "evidence, record live evidence references, promote the ledger, claim "
    "terminal closure, claim readiness, claim DNS proof, claim endpoint proof, "
    "claim secret presence, claim workflow runs, publish artifacts, claim "
    "deployment status approval, claim operator approval, open customer access, "
    "collect personal data, move money, claim legal clearance, form a company, "
    "claim patent protection, publish externally, or deploy"
)
EXPECTED_SURFACES = (
    ("deployment_witness_receipt_route", "local_route_label", "AwaitingEvidence"),
    ("gateway_readiness_report_route", "local_route_label", "AwaitingEvidence"),
    ("closure_plan_receipt_route", "local_route_label", "AwaitingEvidence"),
    ("dns_resolution_receipt_route", "blocked_external_route", "AwaitingEvidence"),
    ("endpoint_probe_receipt_route", "blocked_external_route", "AwaitingEvidence"),
    ("runtime_witness_receipt_route", "blocked_external_route", "AwaitingEvidence"),
    ("runtime_conformance_receipt_route", "blocked_external_route", "AwaitingEvidence"),
    ("workflow_run_receipt_route", "blocked_external_route", "AwaitingEvidence"),
    ("artifact_publication_receipt_route", "blocked_external_route", "AwaitingEvidence"),
    ("deployment_status_approval_route", "blocked_external_route", "AwaitingEvidence"),
    ("operator_decision_route", "blocked_external_route", "AwaitingEvidence"),
    ("reassessment_gate_route", "local_route_label", "AwaitingEvidence"),
)
EXPECTED_SURFACE_NOTES = {
    "deployment_witness_receipt_route": (
        "Deployment witness receipt route only; live witness evidence is not appended."
    ),
    "gateway_readiness_report_route": (
        "Gateway readiness report route only; readiness report pass is not claimed."
    ),
    "closure_plan_receipt_route": "Closure plan receipt route only; closure approval is not claimed.",
    "dns_resolution_receipt_route": "DNS resolution receipt route only; DNS proof is not claimed.",
    "endpoint_probe_receipt_route": "Endpoint probe receipt route only; endpoint proof is not claimed.",
    "runtime_witness_receipt_route": (
        "Runtime witness receipt route only; runtime witness pass is not claimed."
    ),
    "runtime_conformance_receipt_route": (
        "Runtime conformance receipt route only; runtime conformance pass is not claimed."
    ),
    "workflow_run_receipt_route": "Workflow run receipt route only; workflow execution is not claimed.",
    "artifact_publication_receipt_route": (
        "Artifact publication receipt route only; artifacts are not published or promoted."
    ),
    "deployment_status_approval_route": (
        "Deployment status approval route only; deployment status approval is not claimed."
    ),
    "operator_decision_route": "Operator decision route only; operator approval is not claimed.",
    "reassessment_gate_route": "Reassessment gate route only; ledger promotion is not approved.",
}
EXPECTED_DOC_SURFACE_LABELS = (
    "Deployment witness receipt route",
    "Gateway readiness report route",
    "Closure plan receipt route",
    "DNS resolution receipt route",
    "Endpoint probe receipt route",
    "Runtime witness receipt route",
    "Runtime conformance receipt route",
    "Workflow run receipt route",
    "Artifact publication receipt route",
    "Deployment status approval route",
    "Operator decision route",
    "Reassessment gate route",
)
EXPECTED_ROOT_KEYS = {
    "artifact_publication_allowed",
    "blocked_claims",
    "company_formation_claimed",
    "customer_access_allowed",
    "deployment_allowed",
    "deployment_status_approval_claimed",
    "dns_proof_claimed",
    "endpoint_proof_claimed",
    "evidence_ledger_append_allowed",
    "external_publication_allowed",
    "ledger_promotion_allowed",
    "legal_clearance_claimed",
    "live_evidence_reference_allowed",
    "money_movement_allowed",
    "next_action",
    "operator_approval_claimed",
    "patent_claimed",
    "personal_data_collection_allowed",
    "readiness_claimed",
    "route_labels",
    "schema_version",
    "secret_presence_claimed",
    "solver_outcome",
    "status",
    "surfaces",
    "terminal_closure_claimed",
    "witness_id",
    "workflow_run_claimed",
}
EXPECTED_SURFACE_KEYS = {
    "evidence_ref",
    "public_safe_note",
    "state",
    "surface_id",
    "surface_type",
}
REQUIRED_DOC_PHRASES = (
    "Foundation Deployment Witness Evidence Ledger Routing Boundary",
    "Witness packet: [`../examples/foundation_deployment_witness_evidence_ledger_routing_witness.awaiting_evidence.json`]",
    "Rule: Deployment witness evidence ledger routing is a local route map of future",
    "No evidence-ledger append, live evidence reference, ledger promotion",
    "deployment_witness_evidence_ledger_routing_state=AwaitingEvidence",
    "evidence_ledger_append_allowed=false",
    "live_evidence_reference_allowed=false",
    "ledger_promotion_allowed=false",
    "terminal_closure_claimed=false",
    "readiness_claimed=false",
    "dns_proof_claimed=false",
    "endpoint_proof_claimed=false",
    "secret_presence_claimed=false",
    "workflow_run_claimed=false",
    "artifact_publication_allowed=false",
    "deployment_status_approval_claimed=false",
    "operator_approval_claimed=false",
    "customer_access_allowed=false",
    "personal_data_collection_allowed=false",
    "money_movement_allowed=false",
    "legal_clearance_claimed=false",
    "company_formation_claimed=false",
    "patent_claimed=false",
    "external_publication_allowed=false",
    "deployment_allowed=false",
    "python scripts/validate_foundation_deployment_witness_evidence_ledger_routing_boundary.py",
)
FORBIDDEN_VALUE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("url_value", re.compile(r"https?://", re.IGNORECASE)),
    ("email_value", re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)),
    ("private_path", re.compile(r"\b[A-Za-z]:[\\/]|\\\\", re.IGNORECASE)),
    ("private_key_block", re.compile(r"-----BEGIN\s+(?:RSA\s+|EC\s+|OPENSSH\s+)?PRIVATE\s+KEY-----", re.IGNORECASE)),
    (
        "live_assignment",
        re.compile(
            r"\b(?:secret|token|api[_ -]?key|client[_ -]?secret|password|"
            r"credential|gateway|url|dns|target|host|provider|account|"
            r"repository[_ -]?variable|workflow|run|artifact|deployment|"
            r"environment|env|customer|person|participant|email|payment|"
            r"billing|invoice|legal|company|formation|patent|approval|"
            r"receipt|evidence|report|operator|ledger)"
            r"[_ -]?(?:id|name|value|url|target|host|ref|status|text|path|"
            r"list|number)?\s*=",
            re.IGNORECASE,
        ),
    ),
)
FORBIDDEN_PROMOTION_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("ledger_append_done", re.compile(r"\bevidence ledger append\s+(?:is\s+)?(?:done|complete|ready|verified)\b", re.IGNORECASE)),
    ("live_evidence_reference_ready", re.compile(r"\blive evidence reference\s+(?:is\s+)?(?:recorded|stored|ready|verified)\b", re.IGNORECASE)),
    ("ledger_promoted", re.compile(r"\bledger\s+(?:is\s+)?promoted\b", re.IGNORECASE)),
    ("terminal_closure_complete", re.compile(r"\bterminal closure\s+(?:is\s+)?complete\b", re.IGNORECASE)),
    ("readiness_proven", re.compile(r"\breadiness\s+(?:is\s+)?proven\b", re.IGNORECASE)),
    ("dns_proof_ready", re.compile(r"\bdns proof\s+(?:is\s+)?(?:claimed|ready|verified|available)\b", re.IGNORECASE)),
    ("endpoint_proof_ready", re.compile(r"\bendpoint proof\s+(?:is\s+)?(?:claimed|ready|verified|available)\b", re.IGNORECASE)),
    ("secret_presence_ready", re.compile(r"\bsecret presence\s+(?:is\s+)?(?:claimed|verified|ready)\b", re.IGNORECASE)),
    ("workflow_run_ready", re.compile(r"\bworkflow run\s+(?:is\s+)?(?:claimed|ready|verified|complete)\b", re.IGNORECASE)),
    ("artifact_published", re.compile(r"\bartifact\s+(?:is\s+)?(?:published|ready|verified)\b", re.IGNORECASE)),
    ("status_approved", re.compile(r"\bdeployment status approval\s+(?:is\s+)?(?:claimed|ready|verified|complete)\b", re.IGNORECASE)),
    ("operator_approved", re.compile(r"\boperator approval\s+(?:is\s+)?(?:claimed|ready|verified|complete)\b", re.IGNORECASE)),
    ("deployment_ready", re.compile(r"\bdeployment\s+(?:is\s+)?ready\b", re.IGNORECASE)),
    ("customer_access_ready", re.compile(r"\bcustomer access\s+(?:is\s+)?ready\b", re.IGNORECASE)),
    ("legal_cleared", re.compile(r"\blegal\s+(?:is\s+)?cleared\b", re.IGNORECASE)),
    ("company_formed", re.compile(r"\bcompany\s+(?:is\s+)?formed\b", re.IGNORECASE)),
    ("patent_filed", re.compile(r"\bpatent\s+(?:is\s+)?filed\b", re.IGNORECASE)),
    ("money_movement_allowed", re.compile(r"\bmoney movement\s+(?:is\s+)?allowed\b", re.IGNORECASE)),
    ("external_publication_approved", re.compile(r"\bexternal publication (?:allowed|approved|ready)\b", re.IGNORECASE)),
)


@dataclass(frozen=True, slots=True)
class DeploymentWitnessEvidenceLedgerRoutingFinding:
    """One deterministic deployment witness evidence ledger routing validation finding."""

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


def validate_doc_text(text: str) -> list[DeploymentWitnessEvidenceLedgerRoutingFinding]:
    """Return findings for missing deployment witness evidence ledger routing doc anchors."""

    findings: list[DeploymentWitnessEvidenceLedgerRoutingFinding] = []
    for phrase in REQUIRED_DOC_PHRASES:
        if phrase not in text:
            findings.append(
                DeploymentWitnessEvidenceLedgerRoutingFinding(
                    "foundation_deployment_witness_evidence_ledger_routing_doc_phrase_missing",
                    f"deployment witness evidence ledger routing doc missing required phrase: {phrase}",
                )
            )
    for route_label in EXPECTED_ROUTE_LABELS:
        if route_label not in text:
            findings.append(
                DeploymentWitnessEvidenceLedgerRoutingFinding(
                    "foundation_deployment_witness_evidence_ledger_routing_doc_label_missing",
                    f"deployment witness evidence ledger routing doc missing route label: {route_label}",
                )
            )
    for surface_label in EXPECTED_DOC_SURFACE_LABELS:
        if surface_label not in text:
            findings.append(
                DeploymentWitnessEvidenceLedgerRoutingFinding(
                    "foundation_deployment_witness_evidence_ledger_routing_doc_surface_missing",
                    f"deployment witness evidence ledger routing doc missing surface label: {surface_label}",
                )
            )
    findings.extend(validate_forbidden_value_patterns(text, "doc"))
    findings.extend(validate_forbidden_promotion_patterns(text, "doc"))
    return findings


def validate_packet(payload: dict[str, Any]) -> list[DeploymentWitnessEvidenceLedgerRoutingFinding]:
    """Return findings for deployment witness evidence ledger routing witness drift."""

    findings: list[DeploymentWitnessEvidenceLedgerRoutingFinding] = []
    findings.extend(validate_root_contract(payload))
    findings.extend(validate_surfaces(payload.get("surfaces")))
    findings.extend(validate_forbidden_value_patterns(payload, "witness"))
    findings.extend(validate_forbidden_promotion_patterns(payload, "witness"))
    return findings


def validate_root_contract(payload: dict[str, Any]) -> list[DeploymentWitnessEvidenceLedgerRoutingFinding]:
    """Return findings for root-level deployment witness evidence ledger routing drift."""

    findings: list[DeploymentWitnessEvidenceLedgerRoutingFinding] = []
    if set(payload) != EXPECTED_ROOT_KEYS:
        findings.append(
            DeploymentWitnessEvidenceLedgerRoutingFinding(
                "deployment_witness_evidence_ledger_routing_root_keys_invalid",
                f"root keys must be: {', '.join(sorted(EXPECTED_ROOT_KEYS))}",
            )
        )
    expected_values = {
        "witness_id": EXPECTED_WITNESS_ID,
        "schema_version": 1,
        "status": "AwaitingEvidence",
        "solver_outcome": "AwaitingEvidence",
        "evidence_ledger_append_allowed": False,
        "live_evidence_reference_allowed": False,
        "ledger_promotion_allowed": False,
        "terminal_closure_claimed": False,
        "readiness_claimed": False,
        "dns_proof_claimed": False,
        "endpoint_proof_claimed": False,
        "secret_presence_claimed": False,
        "workflow_run_claimed": False,
        "artifact_publication_allowed": False,
        "deployment_status_approval_claimed": False,
        "operator_approval_claimed": False,
        "customer_access_allowed": False,
        "personal_data_collection_allowed": False,
        "money_movement_allowed": False,
        "legal_clearance_claimed": False,
        "company_formation_claimed": False,
        "patent_claimed": False,
        "external_publication_allowed": False,
        "deployment_allowed": False,
    }
    for key, expected_value in expected_values.items():
        if payload.get(key) != expected_value:
            findings.append(
                DeploymentWitnessEvidenceLedgerRoutingFinding(
                    "deployment_witness_evidence_ledger_routing_root_value_invalid",
                    f"{key} must be {expected_value!r}",
                )
            )
    if tuple(payload.get("blocked_claims") or ()) != EXPECTED_BLOCKED_CLAIMS:
        findings.append(
            DeploymentWitnessEvidenceLedgerRoutingFinding(
                "deployment_witness_evidence_ledger_routing_blocked_claims_invalid",
                f"blocked_claims must be: {', '.join(EXPECTED_BLOCKED_CLAIMS)}",
            )
        )
    if tuple(payload.get("route_labels") or ()) != EXPECTED_ROUTE_LABELS:
        findings.append(
            DeploymentWitnessEvidenceLedgerRoutingFinding(
                "deployment_witness_evidence_ledger_routing_labels_invalid",
                f"route_labels must be: {', '.join(EXPECTED_ROUTE_LABELS)}",
            )
        )
    if payload.get("next_action") != EXPECTED_NEXT_ACTION:
        findings.append(
            DeploymentWitnessEvidenceLedgerRoutingFinding(
                "deployment_witness_evidence_ledger_routing_next_action_invalid",
                "next_action must preserve the exact public-safe no-append routing",
            )
        )
    return findings


def validate_surfaces(surfaces: object) -> list[DeploymentWitnessEvidenceLedgerRoutingFinding]:
    """Return findings for deployment witness evidence ledger routing surface drift."""

    findings: list[DeploymentWitnessEvidenceLedgerRoutingFinding] = []
    if not isinstance(surfaces, list) or not all(isinstance(surface, dict) for surface in surfaces):
        return [
            DeploymentWitnessEvidenceLedgerRoutingFinding(
                "deployment_witness_evidence_ledger_routing_surfaces_invalid",
                "surfaces must be a list",
            )
        ]
    observed_surfaces = tuple(
        (surface.get("surface_id"), surface.get("surface_type"), surface.get("state"))
        for surface in surfaces
    )
    if observed_surfaces != EXPECTED_SURFACES:
        findings.append(
            DeploymentWitnessEvidenceLedgerRoutingFinding(
                "deployment_witness_evidence_ledger_routing_surface_inventory_invalid",
                "deployment witness evidence ledger routing surface inventory does not match the expected set",
            )
        )
    surface_ids = [surface.get("surface_id") for surface in surfaces]
    if len(set(surface_ids)) != len(surface_ids):
        findings.append(
            DeploymentWitnessEvidenceLedgerRoutingFinding(
                "deployment_witness_evidence_ledger_routing_surface_duplicate",
                "surface ids must be unique",
            )
        )
    for surface in surfaces:
        surface_id = str(surface.get("surface_id", "<missing>"))
        if set(surface) != EXPECTED_SURFACE_KEYS:
            findings.append(
                DeploymentWitnessEvidenceLedgerRoutingFinding(
                    "deployment_witness_evidence_ledger_routing_surface_keys_invalid",
                    f"{surface_id} surface keys must be: {', '.join(sorted(EXPECTED_SURFACE_KEYS))}",
                )
            )
        if surface.get("state") != "AwaitingEvidence":
            findings.append(
                DeploymentWitnessEvidenceLedgerRoutingFinding(
                    "deployment_witness_evidence_ledger_routing_surface_state_invalid",
                    f"{surface_id} state must be AwaitingEvidence",
                )
            )
        if surface.get("evidence_ref") != "manual_preparation_pending":
            findings.append(
                DeploymentWitnessEvidenceLedgerRoutingFinding(
                    "deployment_witness_evidence_ledger_routing_surface_evidence_invalid",
                    f"{surface_id} evidence_ref must stay manual_preparation_pending",
                )
            )
        if not isinstance(surface.get("public_safe_note"), str) or not surface["public_safe_note"].strip():
            findings.append(
                DeploymentWitnessEvidenceLedgerRoutingFinding(
                    "deployment_witness_evidence_ledger_routing_surface_note_invalid",
                    f"{surface_id} public_safe_note must be a non-empty string",
                )
            )
        elif surface.get("public_safe_note") != EXPECTED_SURFACE_NOTES.get(surface_id):
            findings.append(
                DeploymentWitnessEvidenceLedgerRoutingFinding(
                    "deployment_witness_evidence_ledger_routing_surface_note_invalid",
                    f"{surface_id} public_safe_note must preserve the expected public-safe boundary text",
                )
            )
    return findings


def serialize_for_pattern_scan(value: str | dict[str, Any]) -> str:
    """Return deterministic text for forbidden-pattern validation."""

    if isinstance(value, str):
        return value
    return json.dumps(value, sort_keys=True)


def validate_forbidden_value_patterns(
    value: str | dict[str, Any],
    artifact_label: str,
) -> list[DeploymentWitnessEvidenceLedgerRoutingFinding]:
    """Return findings for live value, private path, or external-action shaped values."""

    serialized_value = serialize_for_pattern_scan(value)
    findings: list[DeploymentWitnessEvidenceLedgerRoutingFinding] = []
    for rule_id, pattern in FORBIDDEN_VALUE_PATTERNS:
        if pattern.search(serialized_value):
            findings.append(
                DeploymentWitnessEvidenceLedgerRoutingFinding(
                    "deployment_witness_evidence_ledger_routing_forbidden_value_pattern",
                    f"deployment witness evidence ledger routing {artifact_label} contains forbidden value pattern: {rule_id}",
                )
            )
    return findings


def validate_forbidden_promotion_patterns(
    value: str | dict[str, Any],
    artifact_label: str,
) -> list[DeploymentWitnessEvidenceLedgerRoutingFinding]:
    """Return findings if the witness drifts into ledger append, approval, or deployment claims."""

    serialized_value = serialize_for_pattern_scan(value)
    findings: list[DeploymentWitnessEvidenceLedgerRoutingFinding] = []
    for rule_id, pattern in FORBIDDEN_PROMOTION_PATTERNS:
        if pattern.search(serialized_value):
            findings.append(
                DeploymentWitnessEvidenceLedgerRoutingFinding(
                    "deployment_witness_evidence_ledger_routing_forbidden_promotion_phrase",
                    f"deployment witness evidence ledger routing {artifact_label} contains forbidden promotion pattern: {rule_id}",
                )
            )
    return findings


def validate_foundation_deployment_witness_evidence_ledger_routing_boundary(
    doc_path: Path = DEFAULT_DOC_PATH,
    packet_path: Path = DEFAULT_PACKET_PATH,
) -> list[DeploymentWitnessEvidenceLedgerRoutingFinding]:
    """Validate the Foundation Mode deployment witness evidence ledger routing artifacts."""

    doc_text = load_text(doc_path, "deployment witness evidence ledger routing boundary doc")
    packet_payload = load_json_object(packet_path, "deployment witness evidence ledger routing witness packet")
    return [
        *validate_doc_text(doc_text),
        *validate_packet(packet_payload),
    ]


def main(argv: list[str] | None = None) -> int:
    """Validate deployment witness evidence ledger routing artifacts and print deterministic status."""

    parser = argparse.ArgumentParser(
        description="Validate Foundation Mode deployment witness evidence ledger routing boundary artifacts."
    )
    parser.add_argument("--doc", type=Path, default=DEFAULT_DOC_PATH)
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET_PATH)
    args = parser.parse_args(argv)

    try:
        findings = validate_foundation_deployment_witness_evidence_ledger_routing_boundary(args.doc, args.packet)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"[FAIL] foundation_deployment_witness_evidence_ledger_routing_load: {exc}", file=sys.stderr)
        print("STATUS: failed", file=sys.stderr)
        return 1

    if findings:
        for finding in findings:
            print(f"[FAIL] {finding.rule_id}: {finding.message}", file=sys.stderr)
        print("STATUS: failed", file=sys.stderr)
        return 1
    print("[PASS] foundation_deployment_witness_evidence_ledger_routing_doc")
    print("[PASS] foundation_deployment_witness_evidence_ledger_routing_witness")
    print("STATUS: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
