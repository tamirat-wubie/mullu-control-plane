#!/usr/bin/env python3
"""Validate the Foundation Mode runtime witness deferral boundary.

Purpose: keep runtime witness creation, verification, publication, and
readiness promotion blocked until operator-owned evidence exists.
Governance scope: Foundation Mode, issue #330 runtime witness deferral,
signature verification blocking, endpoint probe blocking, runtime conformance
blocking, deployment witness collection blocking, evidence-ledger append
blocking, publication blocking, and deployment restraint.
Dependencies: docs/FOUNDATION_RUNTIME_WITNESS_DEFERRAL_BOUNDARY.md and
examples/foundation_runtime_witness_deferral_witness.awaiting_evidence.json.
Invariants:
  - The witness records public-safe deferral labels only.
  - No witness payloads, signatures, endpoints, secrets, approvals, or readiness claims are recorded.
  - Every runtime witness deferral surface remains AwaitingEvidence.
  - Customer access, money movement, legal/company/patent claims, publication, and deployment remain blocked.
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
DEFAULT_DOC_PATH = REPO_ROOT / "docs" / "FOUNDATION_RUNTIME_WITNESS_DEFERRAL_BOUNDARY.md"
DEFAULT_PACKET_PATH = REPO_ROOT / "examples" / "foundation_runtime_witness_deferral_witness.awaiting_evidence.json"

REQUIRED_ROOT_KEYS = (
    "blocked_claims",
    "customer_access_allowed",
    "deferral_labels",
    "deployment_allowed",
    "deployment_witness_collection_allowed",
    "evidence_ledger_append_allowed",
    "external_publication_allowed",
    "legal_clearance_claimed",
    "company_formation_claimed",
    "money_movement_allowed",
    "next_action",
    "patent_claimed",
    "personal_data_collection_allowed",
    "readiness_claimed",
    "runtime_conformance_claimed",
    "runtime_witness_created",
    "runtime_witness_endpoint_probe_allowed",
    "runtime_witness_payload_recorded",
    "runtime_witness_publication_allowed",
    "runtime_witness_secret_bound",
    "runtime_witness_signature_verified",
    "schema_version",
    "solver_outcome",
    "status",
    "surfaces",
    "witness_id",
)
EXPECTED_ROOT_VALUES = {
    "schema_version": "foundation.runtime_witness_deferral.v1",
    "witness_id": "foundation_runtime_witness_deferral_witness.awaiting_evidence.v1",
    "status": "AwaitingEvidence",
    "solver_outcome": "AwaitingEvidence",
}
FALSE_FLAGS = (
    "customer_access_allowed",
    "deployment_allowed",
    "deployment_witness_collection_allowed",
    "evidence_ledger_append_allowed",
    "external_publication_allowed",
    "legal_clearance_claimed",
    "company_formation_claimed",
    "money_movement_allowed",
    "patent_claimed",
    "personal_data_collection_allowed",
    "readiness_claimed",
    "runtime_conformance_claimed",
    "runtime_witness_created",
    "runtime_witness_endpoint_probe_allowed",
    "runtime_witness_payload_recorded",
    "runtime_witness_publication_allowed",
    "runtime_witness_secret_bound",
    "runtime_witness_signature_verified",
)
DEFERRAL_LABELS = (
    "runtime_witness_creation_gate",
    "runtime_witness_secret_binding_gate",
    "runtime_witness_endpoint_probe_gate",
    "runtime_witness_payload_value_gate",
    "runtime_witness_signature_gate",
    "runtime_witness_publication_gate",
    "runtime_conformance_gate",
    "deployment_witness_collection_gate",
    "evidence_ledger_routing_gate",
    "operator_reassessment_gate",
)
BLOCKED_CLAIMS = (
    "runtime witness creation",
    "runtime witness secret binding",
    "runtime witness endpoint probe",
    "runtime witness payload recording",
    "runtime witness signature verification",
    "runtime witness publication",
    "runtime conformance claim",
    "deployment witness collection",
    "evidence ledger append",
    "readiness claim",
    "customer access",
    "personal data collection",
    "money movement",
    "legal clearance",
    "company formation",
    "patent claim",
    "external publication",
    "deployment readiness",
)
SURFACE_NOTES_BY_ID = {
    "runtime_witness_creation_gate": "Runtime witness creation gate only; no creation is performed or claimed.",
    "runtime_witness_secret_binding_gate": "Runtime witness secret binding gate only; no secret binding is recorded or claimed.",
    "runtime_witness_endpoint_probe_gate": "Runtime witness endpoint probe gate only; no endpoint probe is run or recorded.",
    "runtime_witness_payload_value_gate": "Runtime witness payload value gate only; no witness payload values are recorded.",
    "runtime_witness_signature_gate": "Runtime witness signature gate only; signature verification is not claimed.",
    "runtime_witness_publication_gate": "Runtime witness publication gate only; witness material is not published.",
    "runtime_conformance_gate": "Runtime conformance gate only; runtime conformance is not claimed.",
    "deployment_witness_collection_gate": "Deployment witness collection gate only; deployment witnesses are not collected.",
    "evidence_ledger_routing_gate": "Evidence ledger routing gate only; evidence is not appended to the ledger.",
    "operator_reassessment_gate": "Operator reassessment gate only; readiness and deployment are not approved.",
}
SURFACE_TYPES_BY_ID = {
    "runtime_witness_creation_gate": "blocked_witness_creation_label",
    "runtime_witness_secret_binding_gate": "blocked_secret_binding_label",
    "runtime_witness_endpoint_probe_gate": "blocked_endpoint_probe_label",
    "runtime_witness_payload_value_gate": "blocked_payload_value_label",
    "runtime_witness_signature_gate": "blocked_signature_label",
    "runtime_witness_publication_gate": "blocked_publication_label",
    "runtime_conformance_gate": "blocked_conformance_label",
    "deployment_witness_collection_gate": "blocked_witness_collection_label",
    "evidence_ledger_routing_gate": "blocked_ledger_append_label",
    "operator_reassessment_gate": "local_gate_label",
}
REQUIRED_DOC_PHRASES = (
    "Foundation Runtime Witness Deferral Boundary",
    "Witness packet: [`../examples/foundation_runtime_witness_deferral_witness.awaiting_evidence.json`]",
    "Rule: Runtime witness deferral is a local stop-rule packet",
    "No runtime witness creation, runtime witness secret binding, endpoint probe,",
    "runtime_witness_deferral_state=AwaitingEvidence",
    "runtime_witness_created=false",
    "runtime_witness_secret_bound=false",
    "runtime_witness_endpoint_probe_allowed=false",
    "runtime_witness_payload_recorded=false",
    "runtime_witness_signature_verified=false",
    "runtime_witness_publication_allowed=false",
    "runtime_conformance_claimed=false",
    "deployment_witness_collection_allowed=false",
    "evidence_ledger_append_allowed=false",
    "readiness_claimed=false",
    "customer_access_allowed=false",
    "personal_data_collection_allowed=false",
    "money_movement_allowed=false",
    "legal_clearance_claimed=false",
    "company_formation_claimed=false",
    "patent_claimed=false",
    "external_publication_allowed=false",
    "deployment_allowed=false",
    "python scripts/validate_foundation_runtime_witness_deferral_boundary.py",
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
            r"\b(?:secret|token|key|url|endpoint|host|witness|signature|payload|receipt|approval|env)\w*\s*=",
            re.IGNORECASE,
        ),
    ),
)
FORBIDDEN_PROMOTION_PATTERNS = (
    ("witness_created", re.compile(r"\bruntime witness\s+(?:is\s+)?(?:created|available|healthy)\b", re.IGNORECASE)),
    ("secret_bound", re.compile(r"\bruntime witness secret\s+(?:is\s+)?(?:bound|configured|ready)\b", re.IGNORECASE)),
    ("endpoint_probed", re.compile(r"\bendpoint probe\s+(?:has\s+)?(?:passed|succeeded)\b", re.IGNORECASE)),
    ("payload_recorded", re.compile(r"\bwitness payload\s+(?:is\s+)?recorded\b", re.IGNORECASE)),
    ("signature_verified", re.compile(r"\bsignature\s+(?:is\s+)?verified\b", re.IGNORECASE)),
    ("witness_published", re.compile(r"\bruntime witness\s+(?:is\s+)?published\b", re.IGNORECASE)),
    ("conformance_passed", re.compile(r"\bruntime conformance\s+(?:has\s+)?(?:passed|succeeded)\b", re.IGNORECASE)),
    ("deployment_witness_collected", re.compile(r"\bdeployment witness\s+(?:is\s+)?collected\b", re.IGNORECASE)),
    ("ledger_appended", re.compile(r"\bevidence ledger\s+(?:is\s+)?appended\b", re.IGNORECASE)),
    ("readiness_claim", re.compile(r"\breadiness\s+(?:is\s+)?(?:ready|promoted|approved|complete)\b", re.IGNORECASE)),
    ("deployment_ready", re.compile(r"\bdeployment\s+(?:is\s+)?(?:ready|approved|complete)\b", re.IGNORECASE)),
)


@dataclass(frozen=True)
class Finding:
    """One deterministic runtime witness deferral finding."""

    rule_id: str
    message: str


def load_text(path: Path, artifact_label: str) -> str:
    """Load one UTF-8 text artifact."""

    if not path.exists():
        raise FileNotFoundError(f"missing {artifact_label}: {path}")
    return path.read_text(encoding="utf-8")


def load_json_object(path: Path, artifact_label: str) -> dict[str, Any]:
    """Load one JSON object artifact."""

    if not path.exists():
        raise FileNotFoundError(f"missing {artifact_label}: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{artifact_label} must be a JSON object")
    return payload


def iter_strings(value: object) -> list[str]:
    """Return every string nested under a JSON-like value."""

    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        strings: list[str] = []
        for nested_value in value.values():
            strings.extend(iter_strings(nested_value))
        return strings
    if isinstance(value, list):
        strings: list[str] = []
        for nested_value in value:
            strings.extend(iter_strings(nested_value))
        return strings
    return []


def validate_doc_text(doc_text: str) -> list[Finding]:
    """Return findings for required boundary documentation drift."""

    findings: list[Finding] = []
    for phrase in REQUIRED_DOC_PHRASES:
        if phrase not in doc_text:
            findings.append(Finding("doc_required_phrase", f"doc missing required phrase: {phrase}"))
    return findings


def validate_forbidden_text(payload: dict[str, Any]) -> list[Finding]:
    """Return findings for live values or promotion phrases in the witness."""

    findings: list[Finding] = []
    for text in iter_strings(payload):
        for pattern_name, pattern in FORBIDDEN_VALUE_PATTERNS:
            if pattern.search(text):
                findings.append(Finding("forbidden_value_pattern", f"forbidden value pattern: {pattern_name}"))
        for pattern_name, pattern in FORBIDDEN_PROMOTION_PATTERNS:
            if pattern.search(text):
                findings.append(Finding("forbidden_promotion_pattern", f"forbidden promotion pattern: {pattern_name}"))
    return findings


def validate_packet(payload: dict[str, Any]) -> list[Finding]:
    """Return findings for runtime witness deferral packet drift."""

    findings: list[Finding] = []
    if tuple(payload.keys()) != REQUIRED_ROOT_KEYS:
        findings.append(Finding("witness_root_keys", "witness root keys drifted"))
    for key, expected_value in EXPECTED_ROOT_VALUES.items():
        if payload.get(key) != expected_value:
            findings.append(Finding("witness_root_value", f"{key} must be {expected_value!r}"))
    for flag in FALSE_FLAGS:
        if payload.get(flag) is not False:
            findings.append(Finding("witness_false_flag", f"{flag} must remain false"))
    if tuple(payload.get("deferral_labels", ())) != DEFERRAL_LABELS:
        findings.append(Finding("witness_label_inventory", "deferral label inventory drifted"))
    if tuple(payload.get("blocked_claims", ())) != BLOCKED_CLAIMS:
        findings.append(Finding("witness_blocked_claims", "blocked claims drifted"))
    next_action = payload.get("next_action")
    if not isinstance(next_action, str) or "operator-owned runtime witness" not in next_action:
        findings.append(Finding("witness_next_action", "next_action must preserve runtime witness deferral"))
    findings.extend(validate_surfaces(payload.get("surfaces")))
    findings.extend(validate_forbidden_text(payload))
    return findings


def validate_surfaces(surfaces: object) -> list[Finding]:
    """Return findings for deferral surface inventory and state drift."""

    findings: list[Finding] = []
    if not isinstance(surfaces, list) or not all(isinstance(surface, dict) for surface in surfaces):
        return [Finding("surface_shape", "surfaces must be a list of objects")]
    observed_ids = tuple(surface.get("surface_id") for surface in surfaces)
    if observed_ids != DEFERRAL_LABELS:
        findings.append(Finding("surface_inventory", "surface inventory drifted"))
    for surface in surfaces:
        surface_id = str(surface.get("surface_id", "<missing>"))
        expected_keys = ("public_safe_note", "state", "surface_id", "surface_type")
        if tuple(surface.keys()) != expected_keys:
            findings.append(Finding("surface_keys", f"{surface_id} surface keys drifted"))
        if surface.get("state") != "AwaitingEvidence":
            findings.append(Finding("surface_state", f"{surface_id} must remain AwaitingEvidence"))
        if surface.get("surface_type") != SURFACE_TYPES_BY_ID.get(surface_id):
            findings.append(Finding("surface_type", f"{surface_id} surface type drifted"))
        if surface.get("public_safe_note") != SURFACE_NOTES_BY_ID.get(surface_id):
            findings.append(Finding("surface_note", f"{surface_id} surface note drifted"))
    return findings


def validate_artifacts(
    doc_path: Path = DEFAULT_DOC_PATH,
    packet_path: Path = DEFAULT_PACKET_PATH,
) -> list[Finding]:
    """Validate the runtime witness deferral doc and witness packet."""

    doc_text = load_text(doc_path, "runtime witness deferral doc")
    payload = load_json_object(packet_path, "runtime witness deferral witness")
    return [*validate_doc_text(doc_text), *validate_packet(payload)]


def main(argv: list[str] | None = None) -> int:
    """Run the runtime witness deferral validator."""

    parser = argparse.ArgumentParser(description="Validate Foundation Mode runtime witness deferral artifacts.")
    parser.add_argument("--doc", type=Path, default=DEFAULT_DOC_PATH)
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET_PATH)
    args = parser.parse_args(argv)

    findings = validate_artifacts(args.doc, args.packet)
    if findings:
        for finding in findings:
            print(f"[FAIL] {finding.rule_id}: {finding.message}")
        print("STATUS: failed")
        return 1
    print("[PASS] foundation_runtime_witness_deferral_doc")
    print("[PASS] foundation_runtime_witness_deferral_witness")
    print("STATUS: passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
