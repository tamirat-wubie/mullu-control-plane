#!/usr/bin/env python3
"""Validate the Foundation Mode deployment witness evidence handoff boundary.

Purpose: keep issue #330 deployment witness evidence handoff preparation local
and public-safe while live receipts, live URL values, DNS proof, endpoint
proof, secret-presence claims, repository variable binding, workflow run
claims, artifact publication, deployment status approval, operator approval,
customer access, personal data, money movement, legal/business claims,
publication, and deployment remain blocked.
Governance scope: Foundation Mode, issue #330 evidence handoff, public-safe
slot labels, external evidence blocking, approval blocking, secret exclusion,
customer/data blocking, money blocking, legal/business restraint, publication
blocking, and deployment blocking.
Dependencies: docs/FOUNDATION_DEPLOYMENT_WITNESS_EVIDENCE_HANDOFF_BOUNDARY.md
and examples/foundation_deployment_witness_evidence_handoff_witness.awaiting_evidence.json.
Invariants:
  - Validation is read-only.
  - The witness records public-safe evidence handoff slots only.
  - No live evidence receipt, live URL value, DNS proof, endpoint proof, secret
    presence claim, repository variable binding, workflow run claim, witness
    artifact publication, deployment status approval, operator approval,
    customer access, personal data, money movement, legal clearance, company
    formation, patent claim, external publication, or deployment claim is
    allowed.
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
DEFAULT_DOC_PATH = REPO_ROOT / "docs" / "FOUNDATION_DEPLOYMENT_WITNESS_EVIDENCE_HANDOFF_BOUNDARY.md"
DEFAULT_PACKET_PATH = (
    REPO_ROOT / "examples" / "foundation_deployment_witness_evidence_handoff_witness.awaiting_evidence.json"
)

EXPECTED_WITNESS_ID = "foundation_deployment_witness_evidence_handoff_witness.awaiting_evidence.v1"
EXPECTED_HANDOFF_LABELS = (
    "deployment_witness_receipt",
    "gateway_publication_readiness_report",
    "deployment_publication_closure_plan",
    "dns_resolution_receipt",
    "endpoint_probe_receipt",
    "runtime_witness_receipt",
    "runtime_conformance_receipt",
    "workflow_run_receipt",
    "artifact_publication_receipt",
    "deployment_status_approval",
    "operator_decision",
)
EXPECTED_BLOCKED_CLAIMS = (
    "live evidence receipt",
    "live gateway url value",
    "dns proof",
    "endpoint proof",
    "secret presence claim",
    "repository variable binding",
    "workflow run claim",
    "witness artifact publication",
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
    "record public-safe evidence slot names only; do not collect live receipts, "
    "record live gateway URL values, claim DNS proof, claim endpoint proof, "
    "claim secret presence, bind repository variables, claim workflow runs, "
    "publish witness artifacts, claim deployment status approval, claim "
    "operator approval, open customer access, collect personal data, move "
    "money, claim legal clearance, form a company, claim patent protection, "
    "publish externally, or deploy"
)
EXPECTED_SURFACES = (
    ("deployment_witness_receipt_slot", "evidence_handoff_slot", "AwaitingEvidence"),
    ("gateway_readiness_report_slot", "evidence_handoff_slot", "AwaitingEvidence"),
    ("closure_plan_receipt_slot", "evidence_handoff_slot", "AwaitingEvidence"),
    ("dns_resolution_receipt_slot", "blocked_external_evidence", "AwaitingEvidence"),
    ("endpoint_probe_receipt_slot", "blocked_external_evidence", "AwaitingEvidence"),
    ("runtime_witness_receipt_slot", "blocked_external_evidence", "AwaitingEvidence"),
    ("runtime_conformance_receipt_slot", "blocked_external_evidence", "AwaitingEvidence"),
    ("workflow_run_receipt_slot", "blocked_external_evidence", "AwaitingEvidence"),
    ("artifact_publication_receipt_slot", "blocked_external_evidence", "AwaitingEvidence"),
    ("deployment_status_approval_slot", "blocked_external_evidence", "AwaitingEvidence"),
    ("operator_decision_slot", "blocked_external_evidence", "AwaitingEvidence"),
    ("evidence_ledger_entry_slot", "local_reference", "AwaitingEvidence"),
)
EXPECTED_SURFACE_NOTES = {
    "deployment_witness_receipt_slot": (
        "Deployment witness receipt slot only; live witness receipts are not recorded."
    ),
    "gateway_readiness_report_slot": (
        "Gateway readiness report slot only; readiness report pass is not claimed."
    ),
    "closure_plan_receipt_slot": "Closure plan receipt slot only; closure approval is not claimed.",
    "dns_resolution_receipt_slot": "DNS resolution receipt slot only; DNS proof is not claimed.",
    "endpoint_probe_receipt_slot": "Endpoint probe receipt slot only; endpoint proof is not claimed.",
    "runtime_witness_receipt_slot": (
        "Runtime witness receipt slot only; runtime witness pass is not claimed."
    ),
    "runtime_conformance_receipt_slot": (
        "Runtime conformance receipt slot only; runtime conformance pass is not claimed."
    ),
    "workflow_run_receipt_slot": "Workflow run receipt slot only; workflow execution is not claimed.",
    "artifact_publication_receipt_slot": (
        "Artifact publication receipt slot only; witness artifacts are not published or promoted."
    ),
    "deployment_status_approval_slot": (
        "Deployment status approval slot only; deployment status approval is not claimed."
    ),
    "operator_decision_slot": "Operator decision slot only; operator approval is not claimed.",
    "evidence_ledger_entry_slot": (
        "Evidence ledger entry slot only; local ledger entries are not live evidence."
    ),
}
EXPECTED_DOC_SURFACE_LABELS = (
    "Deployment witness receipt slot",
    "Gateway readiness report slot",
    "Closure plan receipt slot",
    "DNS resolution receipt slot",
    "Endpoint probe receipt slot",
    "Runtime witness receipt slot",
    "Runtime conformance receipt slot",
    "Workflow run receipt slot",
    "Artifact publication receipt slot",
    "Deployment status approval slot",
    "Operator decision slot",
    "Evidence ledger entry slot",
)
EXPECTED_ROOT_KEYS = {
    "blocked_claims",
    "company_formation_claimed",
    "customer_access_allowed",
    "deployment_allowed",
    "deployment_status_approval_claimed",
    "dns_proof_claimed",
    "endpoint_proof_claimed",
    "evidence_handoff_labels",
    "external_publication_allowed",
    "legal_clearance_claimed",
    "live_evidence_receipt_recorded",
    "live_gateway_url_value_allowed",
    "money_movement_allowed",
    "next_action",
    "operator_approval_claimed",
    "patent_claimed",
    "personal_data_collection_allowed",
    "repository_variable_binding_allowed",
    "schema_version",
    "secret_presence_claimed",
    "solver_outcome",
    "status",
    "surfaces",
    "witness_artifact_publication_allowed",
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
    "Foundation Deployment Witness Evidence Handoff Boundary",
    "Witness packet: [`../examples/foundation_deployment_witness_evidence_handoff_witness.awaiting_evidence.json`]",
    "Rule: Deployment witness evidence handoff is a local list of future evidence",
    "No live evidence receipt, live URL value, DNS proof",
    "deployment_witness_evidence_handoff_state=AwaitingEvidence",
    "live_evidence_receipt_recorded=false",
    "live_gateway_url_value_allowed=false",
    "dns_proof_claimed=false",
    "endpoint_proof_claimed=false",
    "secret_presence_claimed=false",
    "repository_variable_binding_allowed=false",
    "workflow_run_claimed=false",
    "witness_artifact_publication_allowed=false",
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
    "python scripts/validate_foundation_deployment_witness_evidence_handoff_boundary.py",
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
            r"receipt|evidence|report|operator)"
            r"[_ -]?(?:id|name|value|url|target|host|ref|status|text|path|"
            r"list|number)?\s*=",
            re.IGNORECASE,
        ),
    ),
)
FORBIDDEN_PROMOTION_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("live_evidence_recorded", re.compile(r"\blive evidence receipt\s+(?:is\s+)?(?:recorded|stored|ready|verified)\b", re.IGNORECASE)),
    ("dns_proof_ready", re.compile(r"\bdns proof\s+(?:is\s+)?(?:claimed|ready|verified|available)\b", re.IGNORECASE)),
    ("endpoint_proof_ready", re.compile(r"\bendpoint proof\s+(?:is\s+)?(?:claimed|ready|verified|available)\b", re.IGNORECASE)),
    ("secret_presence_ready", re.compile(r"\bsecret presence\s+(?:is\s+)?(?:claimed|verified|ready)\b", re.IGNORECASE)),
    ("variable_bound", re.compile(r"\brepository variable\s+(?:is\s+)?(?:bound|set|configured|verified)\b", re.IGNORECASE)),
    ("workflow_run_ready", re.compile(r"\bworkflow run\s+(?:is\s+)?(?:claimed|ready|verified|complete)\b", re.IGNORECASE)),
    ("artifact_published", re.compile(r"\bwitness artifact\s+(?:is\s+)?(?:published|ready|verified)\b", re.IGNORECASE)),
    ("status_approved", re.compile(r"\bdeployment status approval\s+(?:is\s+)?(?:claimed|ready|verified|complete)\b", re.IGNORECASE)),
    ("operator_approved", re.compile(r"\boperator approval\s+(?:is\s+)?(?:claimed|ready|verified|complete)\b", re.IGNORECASE)),
    ("evidence_promoted", re.compile(r"\bevidence\s+(?:is\s+)?promoted\b", re.IGNORECASE)),
    ("deployment_ready", re.compile(r"\bdeployment\s+(?:is\s+)?ready\b", re.IGNORECASE)),
    ("customer_access_ready", re.compile(r"\bcustomer access\s+(?:is\s+)?ready\b", re.IGNORECASE)),
    ("legal_cleared", re.compile(r"\blegal\s+(?:is\s+)?cleared\b", re.IGNORECASE)),
    ("company_formed", re.compile(r"\bcompany\s+(?:is\s+)?formed\b", re.IGNORECASE)),
    ("patent_filed", re.compile(r"\bpatent\s+(?:is\s+)?filed\b", re.IGNORECASE)),
    ("money_movement_allowed", re.compile(r"\bmoney movement\s+(?:is\s+)?allowed\b", re.IGNORECASE)),
    ("external_publication_approved", re.compile(r"\bexternal publication (?:allowed|approved|ready)\b", re.IGNORECASE)),
)


@dataclass(frozen=True, slots=True)
class DeploymentWitnessEvidenceHandoffFinding:
    """One deterministic deployment witness evidence handoff validation finding."""

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


def validate_doc_text(text: str) -> list[DeploymentWitnessEvidenceHandoffFinding]:
    """Return findings for missing deployment witness evidence handoff doc anchors."""

    findings: list[DeploymentWitnessEvidenceHandoffFinding] = []
    for phrase in REQUIRED_DOC_PHRASES:
        if phrase not in text:
            findings.append(
                DeploymentWitnessEvidenceHandoffFinding(
                    "foundation_deployment_witness_evidence_handoff_doc_phrase_missing",
                    f"deployment witness evidence handoff doc missing required phrase: {phrase}",
                )
            )
    for handoff_label in EXPECTED_HANDOFF_LABELS:
        if handoff_label not in text:
            findings.append(
                DeploymentWitnessEvidenceHandoffFinding(
                    "foundation_deployment_witness_evidence_handoff_doc_label_missing",
                    f"deployment witness evidence handoff doc missing handoff label: {handoff_label}",
                )
            )
    for surface_label in EXPECTED_DOC_SURFACE_LABELS:
        if surface_label not in text:
            findings.append(
                DeploymentWitnessEvidenceHandoffFinding(
                    "foundation_deployment_witness_evidence_handoff_doc_surface_missing",
                    f"deployment witness evidence handoff doc missing surface label: {surface_label}",
                )
            )
    findings.extend(validate_forbidden_value_patterns(text, "doc"))
    findings.extend(validate_forbidden_promotion_patterns(text, "doc"))
    return findings


def validate_packet(payload: dict[str, Any]) -> list[DeploymentWitnessEvidenceHandoffFinding]:
    """Return findings for deployment witness evidence handoff witness drift."""

    findings: list[DeploymentWitnessEvidenceHandoffFinding] = []
    findings.extend(validate_root_contract(payload))
    findings.extend(validate_surfaces(payload.get("surfaces")))
    findings.extend(validate_forbidden_value_patterns(payload, "witness"))
    findings.extend(validate_forbidden_promotion_patterns(payload, "witness"))
    return findings


def validate_root_contract(payload: dict[str, Any]) -> list[DeploymentWitnessEvidenceHandoffFinding]:
    """Return findings for root-level deployment witness evidence handoff drift."""

    findings: list[DeploymentWitnessEvidenceHandoffFinding] = []
    if set(payload) != EXPECTED_ROOT_KEYS:
        findings.append(
            DeploymentWitnessEvidenceHandoffFinding(
                "deployment_witness_evidence_handoff_root_keys_invalid",
                f"root keys must be: {', '.join(sorted(EXPECTED_ROOT_KEYS))}",
            )
        )
    expected_values = {
        "witness_id": EXPECTED_WITNESS_ID,
        "schema_version": 1,
        "status": "AwaitingEvidence",
        "solver_outcome": "AwaitingEvidence",
        "live_evidence_receipt_recorded": False,
        "live_gateway_url_value_allowed": False,
        "dns_proof_claimed": False,
        "endpoint_proof_claimed": False,
        "secret_presence_claimed": False,
        "repository_variable_binding_allowed": False,
        "workflow_run_claimed": False,
        "witness_artifact_publication_allowed": False,
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
                DeploymentWitnessEvidenceHandoffFinding(
                    "deployment_witness_evidence_handoff_root_value_invalid",
                    f"{key} must be {expected_value!r}",
                )
            )
    if tuple(payload.get("blocked_claims") or ()) != EXPECTED_BLOCKED_CLAIMS:
        findings.append(
            DeploymentWitnessEvidenceHandoffFinding(
                "deployment_witness_evidence_handoff_blocked_claims_invalid",
                f"blocked_claims must be: {', '.join(EXPECTED_BLOCKED_CLAIMS)}",
            )
        )
    if tuple(payload.get("evidence_handoff_labels") or ()) != EXPECTED_HANDOFF_LABELS:
        findings.append(
            DeploymentWitnessEvidenceHandoffFinding(
                "deployment_witness_evidence_handoff_labels_invalid",
                f"evidence_handoff_labels must be: {', '.join(EXPECTED_HANDOFF_LABELS)}",
            )
        )
    if payload.get("next_action") != EXPECTED_NEXT_ACTION:
        findings.append(
            DeploymentWitnessEvidenceHandoffFinding(
                "deployment_witness_evidence_handoff_next_action_invalid",
                "next_action must preserve the exact public-safe non-collection handoff",
            )
        )
    return findings


def validate_surfaces(surfaces: object) -> list[DeploymentWitnessEvidenceHandoffFinding]:
    """Return findings for deployment witness evidence handoff surface drift."""

    findings: list[DeploymentWitnessEvidenceHandoffFinding] = []
    if not isinstance(surfaces, list) or not all(isinstance(surface, dict) for surface in surfaces):
        return [
            DeploymentWitnessEvidenceHandoffFinding(
                "deployment_witness_evidence_handoff_surfaces_invalid",
                "surfaces must be a list",
            )
        ]
    observed_surfaces = tuple(
        (surface.get("surface_id"), surface.get("surface_type"), surface.get("state"))
        for surface in surfaces
    )
    if observed_surfaces != EXPECTED_SURFACES:
        findings.append(
            DeploymentWitnessEvidenceHandoffFinding(
                "deployment_witness_evidence_handoff_surface_inventory_invalid",
                "deployment witness evidence handoff surface inventory does not match the expected set",
            )
        )
    surface_ids = [surface.get("surface_id") for surface in surfaces]
    if len(set(surface_ids)) != len(surface_ids):
        findings.append(
            DeploymentWitnessEvidenceHandoffFinding(
                "deployment_witness_evidence_handoff_surface_duplicate",
                "surface ids must be unique",
            )
        )
    for surface in surfaces:
        surface_id = str(surface.get("surface_id", "<missing>"))
        if set(surface) != EXPECTED_SURFACE_KEYS:
            findings.append(
                DeploymentWitnessEvidenceHandoffFinding(
                    "deployment_witness_evidence_handoff_surface_keys_invalid",
                    f"{surface_id} surface keys must be: {', '.join(sorted(EXPECTED_SURFACE_KEYS))}",
                )
            )
        if surface.get("state") != "AwaitingEvidence":
            findings.append(
                DeploymentWitnessEvidenceHandoffFinding(
                    "deployment_witness_evidence_handoff_surface_state_invalid",
                    f"{surface_id} state must be AwaitingEvidence",
                )
            )
        if surface.get("evidence_ref") != "manual_preparation_pending":
            findings.append(
                DeploymentWitnessEvidenceHandoffFinding(
                    "deployment_witness_evidence_handoff_surface_evidence_invalid",
                    f"{surface_id} evidence_ref must stay manual_preparation_pending",
                )
            )
        if not isinstance(surface.get("public_safe_note"), str) or not surface["public_safe_note"].strip():
            findings.append(
                DeploymentWitnessEvidenceHandoffFinding(
                    "deployment_witness_evidence_handoff_surface_note_invalid",
                    f"{surface_id} public_safe_note must be a non-empty string",
                )
            )
        elif surface.get("public_safe_note") != EXPECTED_SURFACE_NOTES.get(surface_id):
            findings.append(
                DeploymentWitnessEvidenceHandoffFinding(
                    "deployment_witness_evidence_handoff_surface_note_invalid",
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
) -> list[DeploymentWitnessEvidenceHandoffFinding]:
    """Return findings for live value, private path, or external-action shaped values."""

    serialized_value = serialize_for_pattern_scan(value)
    findings: list[DeploymentWitnessEvidenceHandoffFinding] = []
    for rule_id, pattern in FORBIDDEN_VALUE_PATTERNS:
        if pattern.search(serialized_value):
            findings.append(
                DeploymentWitnessEvidenceHandoffFinding(
                    "deployment_witness_evidence_handoff_forbidden_value_pattern",
                    f"deployment witness evidence handoff {artifact_label} contains forbidden value pattern: {rule_id}",
                )
            )
    return findings


def validate_forbidden_promotion_patterns(
    value: str | dict[str, Any],
    artifact_label: str,
) -> list[DeploymentWitnessEvidenceHandoffFinding]:
    """Return findings if the witness drifts into evidence, approval, or deployment claims."""

    serialized_value = serialize_for_pattern_scan(value)
    findings: list[DeploymentWitnessEvidenceHandoffFinding] = []
    for rule_id, pattern in FORBIDDEN_PROMOTION_PATTERNS:
        if pattern.search(serialized_value):
            findings.append(
                DeploymentWitnessEvidenceHandoffFinding(
                    "deployment_witness_evidence_handoff_forbidden_promotion_phrase",
                    f"deployment witness evidence handoff {artifact_label} contains forbidden promotion pattern: {rule_id}",
                )
            )
    return findings


def validate_foundation_deployment_witness_evidence_handoff_boundary(
    doc_path: Path = DEFAULT_DOC_PATH,
    packet_path: Path = DEFAULT_PACKET_PATH,
) -> list[DeploymentWitnessEvidenceHandoffFinding]:
    """Validate the Foundation Mode deployment witness evidence handoff artifacts."""

    doc_text = load_text(doc_path, "deployment witness evidence handoff boundary doc")
    packet_payload = load_json_object(packet_path, "deployment witness evidence handoff witness packet")
    return [
        *validate_doc_text(doc_text),
        *validate_packet(packet_payload),
    ]


def main(argv: list[str] | None = None) -> int:
    """Validate deployment witness evidence handoff artifacts and print deterministic status."""

    parser = argparse.ArgumentParser(
        description="Validate Foundation Mode deployment witness evidence handoff boundary artifacts."
    )
    parser.add_argument("--doc", type=Path, default=DEFAULT_DOC_PATH)
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET_PATH)
    args = parser.parse_args(argv)

    try:
        findings = validate_foundation_deployment_witness_evidence_handoff_boundary(args.doc, args.packet)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"[FAIL] foundation_deployment_witness_evidence_handoff_load: {exc}", file=sys.stderr)
        print("STATUS: failed", file=sys.stderr)
        return 1

    if findings:
        for finding in findings:
            print(f"[FAIL] {finding.rule_id}: {finding.message}", file=sys.stderr)
        print("STATUS: failed", file=sys.stderr)
        return 1
    print("[PASS] foundation_deployment_witness_evidence_handoff_doc")
    print("[PASS] foundation_deployment_witness_evidence_handoff_witness")
    print("STATUS: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
