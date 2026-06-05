#!/usr/bin/env python3
"""Validate the Foundation Mode production dependency evidence rehearsal boundary.

Purpose: keep issue #330 production dependency evidence preparation local and
public-safe until operator-owned dependency receipts exist.
Governance scope: Foundation Mode, issue #330 production dependency evidence,
external evidence blocking, readiness blocking, publication blocking, and
deployment restraint.
Dependencies: docs/FOUNDATION_PRODUCTION_DEPENDENCY_EVIDENCE_REHEARSAL_BOUNDARY.md
and examples/foundation_production_dependency_evidence_rehearsal_witness.awaiting_evidence.json.
Invariants:
  - The witness records public-safe production dependency evidence labels only.
  - No live dependency values, evidence receipts, approvals, or readiness claims are recorded.
  - Every dependency evidence surface remains AwaitingEvidence.
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
DEFAULT_DOC_PATH = REPO_ROOT / "docs" / "FOUNDATION_PRODUCTION_DEPENDENCY_EVIDENCE_REHEARSAL_BOUNDARY.md"
DEFAULT_PACKET_PATH = (
    REPO_ROOT / "examples" / "foundation_production_dependency_evidence_rehearsal_witness.awaiting_evidence.json"
)

REQUIRED_ROOT_KEYS = (
    "schema_version",
    "witness_id",
    "status",
    "solver_outcome",
    "field_labels",
    "blocked_claims",
    "recovery_witness_closed_claimed",
    "production_image_value_recorded",
    "runtime_host_value_recorded",
    "managed_postgres_value_recorded",
    "schema_application_claimed",
    "secret_store_value_recorded",
    "deploy_env_value_recorded",
    "release_preflight_pass_claimed",
    "persistence_check_pass_claimed",
    "host_firewall_pass_claimed",
    "tls_certificate_value_recorded",
    "rollback_path_verified",
    "private_runtime_witness_value_recorded",
    "dns_authority_verified",
    "runtime_witness_registry_closure_claimed",
    "external_evidence_collected",
    "api_provisioning_allowed",
    "dns_publication_allowed",
    "dns_target_selection_allowed",
    "repository_variable_binding_allowed",
    "workflow_dispatch_allowed",
    "artifact_publication_allowed",
    "readiness_claimed",
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
    "schema_version": "foundation.production_dependency_evidence_rehearsal.v1",
    "witness_id": "foundation_production_dependency_evidence_rehearsal_witness.awaiting_evidence.v1",
    "status": "AwaitingEvidence",
    "solver_outcome": "AwaitingEvidence",
}
FALSE_FLAGS = (
    "recovery_witness_closed_claimed",
    "production_image_value_recorded",
    "runtime_host_value_recorded",
    "managed_postgres_value_recorded",
    "schema_application_claimed",
    "secret_store_value_recorded",
    "deploy_env_value_recorded",
    "release_preflight_pass_claimed",
    "persistence_check_pass_claimed",
    "host_firewall_pass_claimed",
    "tls_certificate_value_recorded",
    "rollback_path_verified",
    "private_runtime_witness_value_recorded",
    "dns_authority_verified",
    "runtime_witness_registry_closure_claimed",
    "external_evidence_collected",
    "api_provisioning_allowed",
    "dns_publication_allowed",
    "dns_target_selection_allowed",
    "repository_variable_binding_allowed",
    "workflow_dispatch_allowed",
    "artifact_publication_allowed",
    "readiness_claimed",
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
    "recovery_witness_gate_label",
    "production_image_evidence_label",
    "runtime_host_evidence_label",
    "managed_postgres_evidence_label",
    "schema_application_evidence_label",
    "production_secret_store_evidence_label",
    "deploy_env_evidence_label",
    "release_preflight_evidence_label",
    "persistence_check_evidence_label",
    "host_firewall_evidence_label",
    "tls_certificate_evidence_label",
    "rollback_path_evidence_label",
    "private_runtime_witness_evidence_label",
    "dns_authority_evidence_label",
    "runtime_witness_registry_closure_label",
    "operator_reassessment_gate",
)
BLOCKED_CLAIMS = (
    "recovery witness closure claim",
    "production image value",
    "runtime host value",
    "managed PostgreSQL value",
    "schema application claim",
    "secret store value",
    "deploy env value",
    "release preflight pass claim",
    "persistence check pass claim",
    "host firewall pass claim",
    "TLS certificate value",
    "rollback path verification claim",
    "private runtime witness value",
    "DNS authority verification claim",
    "runtime witness registry closure claim",
    "external evidence collection",
    "API provisioning",
    "DNS publication",
    "DNS target selection",
    "repository variable binding",
    "workflow dispatch",
    "artifact publication",
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
    "recovery_witness_gate_label": "Recovery witness gate label only; recovery closure is not claimed.",
    "production_image_evidence_label": "Production image evidence label only; image values are not recorded.",
    "runtime_host_evidence_label": "Runtime host evidence label only; host values are not recorded.",
    "managed_postgres_evidence_label": "Managed PostgreSQL evidence label only; database values are not recorded.",
    "schema_application_evidence_label": "Schema application evidence label only; schema application is not claimed.",
    "production_secret_store_evidence_label": "Production secret store evidence label only; secrets are not recorded or claimed.",
    "deploy_env_evidence_label": "Deploy-env evidence label only; environment values are not recorded.",
    "release_preflight_evidence_label": "Release preflight evidence label only; preflight pass is not claimed.",
    "persistence_check_evidence_label": "Persistence check evidence label only; persistence proof is not claimed.",
    "host_firewall_evidence_label": "Host firewall evidence label only; firewall proof is not claimed.",
    "tls_certificate_evidence_label": "TLS certificate evidence label only; certificate values are not recorded.",
    "rollback_path_evidence_label": "Rollback path evidence label only; rollback verification is not claimed.",
    "private_runtime_witness_evidence_label": "Private runtime witness evidence label only; private witness material is not recorded.",
    "dns_authority_evidence_label": "DNS authority evidence label only; DNS authority is not claimed.",
    "runtime_witness_registry_closure_label": "Runtime witness registry closure label only; registry closure is not claimed.",
    "operator_reassessment_gate": "Operator reassessment gate only; dependency readiness and deployment are not approved.",
}
SURFACE_TYPES_BY_ID = {
    "recovery_witness_gate_label": "blocked_external_evidence",
    "production_image_evidence_label": "blocked_external_value",
    "runtime_host_evidence_label": "blocked_external_value",
    "managed_postgres_evidence_label": "blocked_external_value",
    "schema_application_evidence_label": "blocked_external_evidence",
    "production_secret_store_evidence_label": "blocked_external_value",
    "deploy_env_evidence_label": "blocked_external_value",
    "release_preflight_evidence_label": "blocked_external_evidence",
    "persistence_check_evidence_label": "blocked_external_evidence",
    "host_firewall_evidence_label": "blocked_external_evidence",
    "tls_certificate_evidence_label": "blocked_external_value",
    "rollback_path_evidence_label": "blocked_external_evidence",
    "private_runtime_witness_evidence_label": "blocked_external_value",
    "dns_authority_evidence_label": "blocked_external_evidence",
    "runtime_witness_registry_closure_label": "blocked_external_evidence",
    "operator_reassessment_gate": "local_gate_label",
}
REQUIRED_DOC_PHRASES = (
    "Foundation Production Dependency Evidence Rehearsal Boundary",
    "Witness packet: [`../examples/foundation_production_dependency_evidence_rehearsal_witness.awaiting_evidence.json`]",
    "Rule: Production dependency evidence rehearsal is a local evidence-label map",
    "No recovery witness closure claim, production image value, runtime host value,",
    "production_dependency_evidence_rehearsal_state=AwaitingEvidence",
    "recovery_witness_closed_claimed=false",
    "production_image_value_recorded=false",
    "runtime_host_value_recorded=false",
    "managed_postgres_value_recorded=false",
    "schema_application_claimed=false",
    "secret_store_value_recorded=false",
    "deploy_env_value_recorded=false",
    "release_preflight_pass_claimed=false",
    "persistence_check_pass_claimed=false",
    "host_firewall_pass_claimed=false",
    "tls_certificate_value_recorded=false",
    "rollback_path_verified=false",
    "private_runtime_witness_value_recorded=false",
    "dns_authority_verified=false",
    "runtime_witness_registry_closure_claimed=false",
    "external_evidence_collected=false",
    "api_provisioning_allowed=false",
    "dns_publication_allowed=false",
    "dns_target_selection_allowed=false",
    "repository_variable_binding_allowed=false",
    "workflow_dispatch_allowed=false",
    "artifact_publication_allowed=false",
    "readiness_claimed=false",
    "customer_access_allowed=false",
    "personal_data_collection_allowed=false",
    "money_movement_allowed=false",
    "legal_clearance_claimed=false",
    "company_formation_claimed=false",
    "patent_claimed=false",
    "external_publication_allowed=false",
    "deployment_allowed=false",
    "python scripts/validate_foundation_production_dependency_evidence_rehearsal_boundary.py",
)
FORBIDDEN_VALUE_PATTERNS = (
    ("url", re.compile(r"\b(?:https?://|www\.)\S+", re.IGNORECASE)),
    ("email", re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)),
    ("ip_address", re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")),
    ("timestamp", re.compile(r"\b20\d{2}-\d{2}-\d{2}[T ][0-2]\d:[0-5]\d")),
    ("private_path", re.compile(r"(?:[A-Za-z]:\\|/home/|/Users/|\\\\[^\\]+\\)", re.IGNORECASE)),
    ("secret_material", re.compile(r"\b(?:sk|pk|ghp|github_pat|AKIA)[A-Za-z0-9_-]{8,}\b")),
    (
        "assignment_shape",
        re.compile(
            r"\b(?:url|host|image|database|postgres|secret|token|key|certificate|dns|workflow|artifact)\w*\s*=",
            re.IGNORECASE,
        ),
    ),
)
FORBIDDEN_PROMOTION_PATTERNS = (
    ("dependency_ready", re.compile(r"\bproduction dependenc(?:y|ies)\s+(?:is|are)\s+(?:ready|verified|complete)\b", re.IGNORECASE)),
    ("recovery_closed", re.compile(r"\brecovery witness\s+(?:is\s+)?(?:closed|verified|complete)\b", re.IGNORECASE)),
    ("runtime_ready", re.compile(r"\bruntime host\s+(?:is\s+)?(?:ready|verified|provisioned|complete)\b", re.IGNORECASE)),
    ("database_ready", re.compile(r"\bmanaged PostgreSQL\s+(?:is\s+)?(?:ready|verified|provisioned|complete)\b", re.IGNORECASE)),
    ("secret_store_ready", re.compile(r"\bsecret store\s+(?:is\s+)?(?:ready|verified|provisioned|complete)\b", re.IGNORECASE)),
    ("tls_ready", re.compile(r"\bTLS certificate\s+(?:is\s+)?(?:ready|verified|issued|complete)\b", re.IGNORECASE)),
    ("dns_authority_ready", re.compile(r"\bDNS authority\s+(?:is\s+)?(?:ready|verified|complete)\b", re.IGNORECASE)),
    ("deployment_ready", re.compile(r"\bdeployment\s+(?:is\s+)?(?:ready|approved|complete)\b", re.IGNORECASE)),
)


@dataclass(frozen=True)
class Finding:
    """One deterministic production dependency evidence rehearsal finding."""

    rule_id: str
    message: str


def load_text(path: Path, artifact_label: str) -> str:
    """Load one UTF-8 text artifact."""

    if not path.exists():
        raise FileNotFoundError(f"missing {artifact_label}: {path}")
    if not path.is_file():
        raise IsADirectoryError(f"{artifact_label} is not a file: {path}")
    return path.read_text(encoding="utf-8-sig")


def load_json_object(path: Path, artifact_label: str) -> dict[str, Any]:
    """Load one JSON object artifact."""

    payload = json.loads(load_text(path, artifact_label))
    if not isinstance(payload, dict):
        raise ValueError(f"{artifact_label} must be a JSON object")
    return payload


def validate_artifacts(doc_path: Path = DEFAULT_DOC_PATH, packet_path: Path = DEFAULT_PACKET_PATH) -> list[Finding]:
    """Validate the production dependency evidence rehearsal artifacts."""

    doc_text = load_text(doc_path, "production dependency evidence rehearsal boundary doc")
    packet_payload = load_json_object(packet_path, "production dependency evidence rehearsal witness packet")

    findings: list[Finding] = []
    findings.extend(_validate_doc(doc_text))
    findings.extend(_validate_packet(packet_payload))
    findings.extend(_validate_forbidden_patterns(json.dumps(packet_payload, sort_keys=True), "witness"))
    return findings


def _validate_doc(doc_text: str) -> list[Finding]:
    findings: list[Finding] = []
    for phrase in REQUIRED_DOC_PHRASES:
        if phrase not in doc_text:
            findings.append(
                Finding("doc_required_phrase", f"production dependency evidence rehearsal doc missing required phrase: {phrase}")
            )
    for label in FIELD_LABELS:
        if label not in doc_text:
            findings.append(Finding("doc_field_label", f"production dependency evidence rehearsal doc missing label: {label}"))
    return findings


def _validate_packet(packet: dict[str, Any]) -> list[Finding]:
    findings: list[Finding] = []
    if tuple(packet.keys()) != REQUIRED_ROOT_KEYS:
        findings.append(Finding("witness_root_keys", "production dependency evidence rehearsal witness root keys drifted"))
    for key, expected_value in EXPECTED_ROOT_VALUES.items():
        if packet.get(key) != expected_value:
            findings.append(Finding("witness_identity", f"production dependency evidence rehearsal {key} must be {expected_value!r}"))
    for key in FALSE_FLAGS:
        if packet.get(key) is not False:
            findings.append(Finding("witness_false_flag", f"production dependency evidence rehearsal {key} must remain false"))
    if tuple(packet.get("field_labels", ())) != FIELD_LABELS:
        findings.append(Finding("witness_field_labels", "production dependency evidence rehearsal field_labels drifted"))
    if tuple(packet.get("blocked_claims", ())) != BLOCKED_CLAIMS:
        findings.append(Finding("witness_blocked_claims", "production dependency evidence rehearsal blocked_claims drifted"))
    surfaces = packet.get("surfaces")
    if not isinstance(surfaces, list):
        findings.append(Finding("witness_surfaces_type", "production dependency evidence rehearsal surfaces must be a list"))
        return findings
    observed_surface_ids: list[str] = []
    for index, surface in enumerate(surfaces):
        if not isinstance(surface, dict):
            findings.append(Finding("witness_surface_object", f"production dependency evidence rehearsal surface {index} must be an object"))
            continue
        observed_surface_ids.append(str(surface.get("surface_id")))
        findings.extend(_validate_surface(surface, index))
    if tuple(observed_surface_ids) != FIELD_LABELS:
        findings.append(
            Finding("witness_surface_inventory", "production dependency evidence rehearsal surface inventory drifted")
        )
    if len(set(observed_surface_ids)) != len(observed_surface_ids):
        findings.append(Finding("witness_surface_duplicate", "production dependency evidence rehearsal surfaces must not duplicate ids"))
    return findings


def _validate_surface(surface: dict[str, Any], index: int) -> list[Finding]:
    findings: list[Finding] = []
    surface_id = surface.get("surface_id")
    expected_keys = ("surface_id", "surface_type", "state", "evidence_ref", "public_safe_note")
    if tuple(surface.keys()) != expected_keys:
        findings.append(Finding("witness_surface_keys", f"production dependency evidence rehearsal surface keys drifted: {surface_id}"))
    if surface_id not in SURFACE_NOTES_BY_ID:
        findings.append(Finding("witness_surface_id", f"production dependency evidence rehearsal surface id is unknown: {surface_id}"))
        return findings
    if surface.get("surface_type") != SURFACE_TYPES_BY_ID[surface_id]:
        findings.append(Finding("witness_surface_type", f"production dependency evidence rehearsal surface type drifted: {surface_id}"))
    if surface.get("state") != "AwaitingEvidence":
        findings.append(Finding("witness_surface_state", f"production dependency evidence rehearsal surface must remain AwaitingEvidence: {surface_id}"))
    if surface.get("evidence_ref") != "future_operator_receipt":
        findings.append(Finding("witness_surface_evidence_ref", f"production dependency evidence rehearsal surface evidence_ref drifted: {surface_id}"))
    if surface.get("public_safe_note") != SURFACE_NOTES_BY_ID[surface_id]:
        findings.append(Finding("witness_surface_note", f"production dependency evidence rehearsal surface note drifted: {surface_id}"))
    return findings


def _validate_forbidden_patterns(text: str, artifact_label: str) -> list[Finding]:
    findings: list[Finding] = []
    for rule_id, pattern in FORBIDDEN_VALUE_PATTERNS:
        if pattern.search(text):
            findings.append(
                Finding(
                    "forbidden_value_pattern",
                    f"production dependency evidence rehearsal {artifact_label} contains forbidden value pattern: {rule_id}",
                )
            )
    for rule_id, pattern in FORBIDDEN_PROMOTION_PATTERNS:
        if pattern.search(text):
            findings.append(
                Finding(
                    "forbidden_promotion_pattern",
                    f"production dependency evidence rehearsal {artifact_label} contains forbidden promotion pattern: {rule_id}",
                )
            )
    return findings


def main(argv: list[str] | None = None) -> int:
    """Validate production dependency evidence rehearsal artifacts and print status."""

    parser = argparse.ArgumentParser(
        description="Validate Foundation Mode production dependency evidence rehearsal boundary artifacts."
    )
    parser.add_argument("--doc", type=Path, default=DEFAULT_DOC_PATH)
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET_PATH)
    args = parser.parse_args(argv)

    try:
        findings = validate_artifacts(args.doc, args.packet)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        sys.stderr.write(f"[FAIL] load-production-dependency-evidence-rehearsal: {exc}\nSTATUS: failed\n")
        return 1
    if findings:
        for finding in findings:
            sys.stderr.write(f"[FAIL] {finding.rule_id}: {finding.message}\n")
        sys.stderr.write("STATUS: failed\n")
        return 1
    sys.stdout.write("[PASS] foundation_production_dependency_evidence_rehearsal_doc\n")
    sys.stdout.write("[PASS] foundation_production_dependency_evidence_rehearsal_witness\n")
    sys.stdout.write("STATUS: passed\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
