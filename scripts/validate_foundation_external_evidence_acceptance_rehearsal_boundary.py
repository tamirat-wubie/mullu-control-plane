#!/usr/bin/env python3
"""Validate the Foundation Mode external evidence acceptance rehearsal boundary.

Purpose: keep issue #330 external evidence acceptance preparation local and
public-safe until operator-owned evidence receipts exist.
Governance scope: Foundation Mode, issue #330 external evidence acceptance,
source/owner/redaction/freshness/custody/schema/replay gates, ledger blocking,
readiness blocking, publication blocking, and deployment restraint.
Dependencies: docs/FOUNDATION_EXTERNAL_EVIDENCE_ACCEPTANCE_REHEARSAL_BOUNDARY.md
and examples/foundation_external_evidence_acceptance_rehearsal_witness.awaiting_evidence.json.
Invariants:
  - The witness records public-safe evidence acceptance gate labels only.
  - No live evidence values, receipts, approvals, or readiness claims are recorded.
  - Every evidence acceptance surface remains AwaitingEvidence.
  - Ledger append, readiness promotion, customer access, money movement,
    legal/company/patent claims, publication, and deployment remain blocked.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DOC_PATH = REPO_ROOT / "docs" / "FOUNDATION_EXTERNAL_EVIDENCE_ACCEPTANCE_REHEARSAL_BOUNDARY.md"
DEFAULT_PACKET_PATH = (
    REPO_ROOT / "examples" / "foundation_external_evidence_acceptance_rehearsal_witness.awaiting_evidence.json"
)

REQUIRED_ROOT_KEYS = (
    "schema_version",
    "witness_id",
    "status",
    "solver_outcome",
    "field_labels",
    "blocked_claims",
    "external_evidence_collected",
    "source_authority_verified",
    "evidence_owner_verified",
    "redaction_pass_claimed",
    "freshness_pass_claimed",
    "chain_of_custody_verified",
    "schema_validation_pass_claimed",
    "contradiction_check_pass_claimed",
    "replay_pass_claimed",
    "acceptance_decision_recorded",
    "rejection_decision_recorded",
    "ledger_append_allowed",
    "readiness_promotion_allowed",
    "api_provisioning_allowed",
    "dns_publication_allowed",
    "workflow_dispatch_allowed",
    "artifact_publication_allowed",
    "public_health_declaration_allowed",
    "deployment_witness_publication_allowed",
    "customer_access_allowed",
    "personal_data_collection_allowed",
    "money_movement_allowed",
    "legal_clearance_claimed",
    "company_formation_claimed",
    "patent_claimed",
    "external_publication_allowed",
    "deployment_allowed",
    "surfaces",
    "next_action",
)
EXPECTED_ROOT_VALUES = {
    "schema_version": "foundation.external_evidence_acceptance_rehearsal.v1",
    "witness_id": "foundation_external_evidence_acceptance_rehearsal_witness.awaiting_evidence.v1",
    "status": "AwaitingEvidence",
    "solver_outcome": "AwaitingEvidence",
}
FALSE_FLAGS = (
    "external_evidence_collected",
    "source_authority_verified",
    "evidence_owner_verified",
    "redaction_pass_claimed",
    "freshness_pass_claimed",
    "chain_of_custody_verified",
    "schema_validation_pass_claimed",
    "contradiction_check_pass_claimed",
    "replay_pass_claimed",
    "acceptance_decision_recorded",
    "rejection_decision_recorded",
    "ledger_append_allowed",
    "readiness_promotion_allowed",
    "api_provisioning_allowed",
    "dns_publication_allowed",
    "workflow_dispatch_allowed",
    "artifact_publication_allowed",
    "public_health_declaration_allowed",
    "deployment_witness_publication_allowed",
    "customer_access_allowed",
    "personal_data_collection_allowed",
    "money_movement_allowed",
    "legal_clearance_claimed",
    "company_formation_claimed",
    "patent_claimed",
    "external_publication_allowed",
    "deployment_allowed",
)
FIELD_LABELS = (
    "evidence_source_boundary_label",
    "evidence_classification_label",
    "evidence_owner_label",
    "evidence_redaction_gate_label",
    "evidence_value_absence_gate_label",
    "evidence_freshness_gate_label",
    "evidence_chain_of_custody_label",
    "evidence_schema_validation_label",
    "evidence_contradiction_check_label",
    "evidence_replay_requirement_label",
    "evidence_rejection_reason_label",
    "evidence_acceptance_decision_label",
    "ledger_append_gate_label",
    "readiness_promotion_gate_label",
    "operator_reassessment_gate",
)
BLOCKED_CLAIMS = (
    "external evidence collection",
    "source authority verification",
    "evidence owner verification",
    "redaction pass claim",
    "freshness pass claim",
    "chain of custody verification",
    "schema validation pass claim",
    "contradiction check pass claim",
    "replay pass claim",
    "acceptance decision",
    "rejection decision",
    "ledger append",
    "readiness promotion",
    "API provisioning",
    "DNS publication",
    "workflow dispatch",
    "artifact publication",
    "public health declaration",
    "deployment witness publication",
    "customer access",
    "personal data collection",
    "money movement",
    "legal clearance",
    "company formation",
    "patent claim",
    "external publication",
    "deployment readiness",
)
SURFACE_TYPES_BY_ID = {
    "evidence_source_boundary_label": "local_acceptance_gate",
    "evidence_classification_label": "local_acceptance_gate",
    "evidence_owner_label": "local_acceptance_gate",
    "evidence_redaction_gate_label": "local_acceptance_gate",
    "evidence_value_absence_gate_label": "local_acceptance_gate",
    "evidence_freshness_gate_label": "local_acceptance_gate",
    "evidence_chain_of_custody_label": "local_acceptance_gate",
    "evidence_schema_validation_label": "local_acceptance_gate",
    "evidence_contradiction_check_label": "local_acceptance_gate",
    "evidence_replay_requirement_label": "local_acceptance_gate",
    "evidence_rejection_reason_label": "blocked_decision_label",
    "evidence_acceptance_decision_label": "blocked_decision_label",
    "ledger_append_gate_label": "blocked_effect_gate",
    "readiness_promotion_gate_label": "blocked_promotion_gate",
    "operator_reassessment_gate": "local_gate_label",
}
SURFACE_NOTES_BY_ID = {
    "evidence_source_boundary_label": "Source-boundary review label only; source authority is not verified.",
    "evidence_classification_label": "Evidence-classification label only; live evidence is not classified.",
    "evidence_owner_label": "Evidence-owner review label only; ownership is not verified.",
    "evidence_redaction_gate_label": "Redaction gate label only; redaction pass is not claimed.",
    "evidence_value_absence_gate_label": "Value-absence gate label only; live values are not recorded.",
    "evidence_freshness_gate_label": "Freshness gate label only; freshness pass is not claimed.",
    "evidence_chain_of_custody_label": "Chain-of-custody gate label only; custody proof is not claimed.",
    "evidence_schema_validation_label": "Schema-validation gate label only; schema pass is not claimed.",
    "evidence_contradiction_check_label": "Contradiction-check gate label only; contradiction clearance is not claimed.",
    "evidence_replay_requirement_label": "Replay requirement label only; replay pass is not claimed.",
    "evidence_rejection_reason_label": "Rejection-reason label only; no final rejection decision is recorded.",
    "evidence_acceptance_decision_label": "Acceptance-decision label only; no acceptance decision is recorded.",
    "ledger_append_gate_label": "Ledger append gate label only; evidence is not appended.",
    "readiness_promotion_gate_label": "Readiness-promotion gate label only; readiness is not promoted.",
    "operator_reassessment_gate": "Operator reassessment gate only; readiness and deployment are not approved.",
}
REQUIRED_DOC_PHRASES = (
    "Foundation External Evidence Acceptance Rehearsal Boundary",
    "Witness packet: [`../examples/foundation_external_evidence_acceptance_rehearsal_witness.awaiting_evidence.json`]",
    "Rule: External evidence acceptance rehearsal is a local gate-label map",
    "No external evidence collection, source-authority verification claim,",
    "external_evidence_acceptance_rehearsal_state=AwaitingEvidence",
    "external_evidence_collected=false",
    "source_authority_verified=false",
    "evidence_owner_verified=false",
    "redaction_pass_claimed=false",
    "freshness_pass_claimed=false",
    "chain_of_custody_verified=false",
    "schema_validation_pass_claimed=false",
    "contradiction_check_pass_claimed=false",
    "replay_pass_claimed=false",
    "acceptance_decision_recorded=false",
    "rejection_decision_recorded=false",
    "ledger_append_allowed=false",
    "readiness_promotion_allowed=false",
    "api_provisioning_allowed=false",
    "dns_publication_allowed=false",
    "workflow_dispatch_allowed=false",
    "artifact_publication_allowed=false",
    "public_health_declaration_allowed=false",
    "deployment_witness_publication_allowed=false",
    "customer_access_allowed=false",
    "personal_data_collection_allowed=false",
    "money_movement_allowed=false",
    "legal_clearance_claimed=false",
    "company_formation_claimed=false",
    "patent_claimed=false",
    "external_publication_allowed=false",
    "deployment_allowed=false",
    "python scripts/validate_foundation_external_evidence_acceptance_rehearsal_boundary.py",
)
FORBIDDEN_VALUE_PATTERNS = (
    ("url", re.compile(r"\b(?:https?://|www\.)\S+", re.IGNORECASE)),
    ("email", re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)),
    ("ip_address", re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")),
    ("timestamp", re.compile(r"\b20\d{2}-\d{2}-\d{2}[T ][0-2]\d:[0-5]\d")),
    ("private_path", re.compile(r"(?:[A-Za-z]:\\|/home/|/Users/|\\\\[^\\]+\\)", re.IGNORECASE)),
    ("secret_material", re.compile(r"\b(?:sk|pk|ghp|github_pat|AKIA)[A-Za-z0-9_-]{8,}\b")),
    ("hash_like_value", re.compile(r"\b[a-f0-9]{32,}\b", re.IGNORECASE)),
    (
        "assignment_shape",
        re.compile(
            r"\b(?:url|host|ip|receipt|hash|secret|token|key|certificate|approval|artifact)\w*\s*=",
            re.IGNORECASE,
        ),
    ),
)
FORBIDDEN_PROMOTION_PATTERNS = (
    ("source_authority_verified", re.compile(r"\bsource authority\s+(?:is\s+)?verified\b", re.IGNORECASE)),
    ("evidence_owner_verified", re.compile(r"\bevidence owner\s+(?:is\s+)?verified\b", re.IGNORECASE)),
    ("redaction_passed", re.compile(r"\bredaction\s+(?:is\s+)?(?:passed|complete|verified)\b", re.IGNORECASE)),
    ("freshness_passed", re.compile(r"\bfreshness\s+(?:is\s+)?(?:passed|complete|verified)\b", re.IGNORECASE)),
    ("custody_verified", re.compile(r"\bchain of custody\s+(?:is\s+)?verified\b", re.IGNORECASE)),
    ("schema_passed", re.compile(r"\bschema validation\s+(?:is\s+)?(?:passed|complete|verified)\b", re.IGNORECASE)),
    ("replay_passed", re.compile(r"\breplay\s+(?:is\s+)?(?:passed|complete|verified)\b", re.IGNORECASE)),
    ("evidence_accepted", re.compile(r"\bexternal evidence\s+(?:is\s+)?accepted\b", re.IGNORECASE)),
    ("evidence_rejected", re.compile(r"\bexternal evidence\s+(?:is\s+)?rejected\b", re.IGNORECASE)),
    ("ledger_appended", re.compile(r"\bledger\s+(?:is\s+)?(?:appended|updated|written)\b", re.IGNORECASE)),
    ("readiness_promoted", re.compile(r"\breadiness\s+(?:is\s+)?(?:promoted|approved|complete)\b", re.IGNORECASE)),
    ("deployment_ready", re.compile(r"\bdeployment\s+(?:is\s+)?(?:ready|approved|complete)\b", re.IGNORECASE)),
)


@dataclass(frozen=True)
class Finding:
    """One deterministic external evidence acceptance rehearsal finding."""

    rule_id: str
    message: str


def load_text(path: Path, artifact_label: str) -> str:
    """Load one UTF-8 text artifact."""

    if not path.exists():
        raise FileNotFoundError(f"missing {artifact_label}: {path}")
    if not path.is_file():
        raise IsADirectoryError(f"{artifact_label} path is not a file: {path}")
    return path.read_text(encoding="utf-8-sig")


def load_json_object(path: Path, artifact_label: str) -> dict[str, Any]:
    """Load one JSON object artifact."""

    if not path.exists():
        raise FileNotFoundError(f"missing {artifact_label}: {path}")
    if not path.is_file():
        raise IsADirectoryError(f"{artifact_label} path is not a file: {path}")
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError(f"{artifact_label} must be a JSON object")
    return payload


def _iter_string_values(value: Any) -> list[str]:
    """Return every string nested in one JSON-compatible value."""

    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        strings: list[str] = []
        for nested_value in value.values():
            strings.extend(_iter_string_values(nested_value))
        return strings
    if isinstance(value, list):
        strings = []
        for item in value:
            strings.extend(_iter_string_values(item))
        return strings
    return []


def _validate_doc(text: str) -> list[Finding]:
    findings: list[Finding] = []
    for phrase in REQUIRED_DOC_PHRASES:
        if phrase not in text:
            findings.append(Finding("doc_required_phrase", f"doc missing required phrase: {phrase}"))
    for pattern_id, pattern in FORBIDDEN_PROMOTION_PATTERNS:
        if pattern.search(text):
            findings.append(Finding("forbidden_promotion_pattern", f"forbidden promotion pattern: {pattern_id}"))
    return findings


def _validate_packet(payload: dict[str, Any]) -> list[Finding]:
    findings: list[Finding] = []
    if tuple(payload.keys()) != REQUIRED_ROOT_KEYS:
        findings.append(Finding("witness_root_keys", "witness root keys drifted"))
    for key, expected_value in EXPECTED_ROOT_VALUES.items():
        if payload.get(key) != expected_value:
            findings.append(Finding("witness_root_value", f"{key} must be {expected_value!r}"))
    for flag in FALSE_FLAGS:
        if payload.get(flag) is not False:
            findings.append(Finding("witness_false_flag", f"{flag} must remain false"))
    if tuple(payload.get("field_labels", ())) != FIELD_LABELS:
        findings.append(Finding("field_labels", "field label inventory drifted"))
    if tuple(payload.get("blocked_claims", ())) != BLOCKED_CLAIMS:
        findings.append(Finding("blocked_claims", "blocked claim inventory drifted"))
    findings.extend(_validate_surfaces(payload.get("surfaces")))
    findings.extend(_validate_forbidden_strings(payload))
    return findings


def _validate_surfaces(value: Any) -> list[Finding]:
    findings: list[Finding] = []
    if not isinstance(value, list):
        return [Finding("surface_inventory", "surfaces must be a list")]
    surface_ids = [surface.get("surface_id") for surface in value if isinstance(surface, dict)]
    if surface_ids != list(FIELD_LABELS):
        findings.append(Finding("surface_inventory", "surface inventory drifted"))
    for surface in value:
        if not isinstance(surface, dict):
            findings.append(Finding("surface_shape", "surface must be an object"))
            continue
        surface_id = surface.get("surface_id")
        if surface_id not in SURFACE_NOTES_BY_ID:
            findings.append(Finding("surface_id", f"unexpected surface id: {surface_id!r}"))
            continue
        if surface.get("surface_type") != SURFACE_TYPES_BY_ID[surface_id]:
            findings.append(Finding("surface_type", f"{surface_id} surface type drifted"))
        if surface.get("state") != "AwaitingEvidence":
            findings.append(Finding("surface_state", f"{surface_id} must remain AwaitingEvidence"))
        if surface.get("evidence_ref") != "future_operator_evidence_review":
            findings.append(Finding("surface_evidence_ref", f"{surface_id} evidence ref drifted"))
        if surface.get("public_safe_note") != SURFACE_NOTES_BY_ID[surface_id]:
            findings.append(Finding("surface_note", f"{surface_id} surface note drifted"))
    return findings


def _validate_forbidden_strings(payload: dict[str, Any]) -> list[Finding]:
    findings: list[Finding] = []
    for text in _iter_string_values(payload):
        for pattern_id, pattern in FORBIDDEN_VALUE_PATTERNS:
            if pattern.search(text):
                findings.append(Finding("forbidden_value_pattern", f"forbidden value pattern: {pattern_id}"))
        for pattern_id, pattern in FORBIDDEN_PROMOTION_PATTERNS:
            if pattern.search(text):
                findings.append(Finding("forbidden_promotion_pattern", f"forbidden promotion pattern: {pattern_id}"))
    return findings


def validate_artifacts(
    doc_path: Path = DEFAULT_DOC_PATH,
    packet_path: Path = DEFAULT_PACKET_PATH,
) -> list[Finding]:
    """Validate the external evidence acceptance rehearsal doc and witness."""

    findings: list[Finding] = []
    findings.extend(_validate_doc(load_text(doc_path, "external evidence acceptance rehearsal doc")))
    findings.extend(_validate_packet(load_json_object(packet_path, "external evidence acceptance rehearsal witness")))
    return findings


def validate_foundation_external_evidence_acceptance_rehearsal_boundary() -> list[Finding]:
    """Validate default external evidence acceptance rehearsal artifacts."""

    return validate_artifacts()


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for external evidence acceptance rehearsal validation."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--doc", type=Path, default=DEFAULT_DOC_PATH)
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET_PATH)
    args = parser.parse_args(argv)

    findings = validate_artifacts(doc_path=args.doc, packet_path=args.packet)
    if findings:
        for finding in findings:
            print(f"[FAIL] {finding.rule_id}: {finding.message}")
        print("STATUS: failed")
        return 1
    print("[PASS] foundation_external_evidence_acceptance_rehearsal_doc")
    print("[PASS] foundation_external_evidence_acceptance_rehearsal_witness")
    print("STATUS: passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
