#!/usr/bin/env python3
"""Validate the Foundation Mode runtime secret handoff rehearsal boundary.

Purpose: keep issue #330 runtime secret handoff preparation local and
public-safe until operator-owned secret handoff receipts exist.
Governance scope: Foundation Mode, issue #330 runtime witness secret handoff,
runtime conformance secret handoff, deployment witness secret handoff,
secret-value blocking, secret-presence blocking, repository binding blocking,
runtime binding blocking, workflow blocking, publication blocking, and
deployment restraint.
Dependencies: docs/FOUNDATION_RUNTIME_SECRET_HANDOFF_REHEARSAL_BOUNDARY.md
and examples/foundation_runtime_secret_handoff_rehearsal_witness.awaiting_evidence.json.
Invariants:
  - The witness records public-safe runtime secret handoff gate labels only.
  - No secret names, secret values, private paths, bindings, approvals, or readiness claims are recorded.
  - Every runtime secret handoff surface remains AwaitingEvidence.
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
DEFAULT_DOC_PATH = REPO_ROOT / "docs" / "FOUNDATION_RUNTIME_SECRET_HANDOFF_REHEARSAL_BOUNDARY.md"
DEFAULT_PACKET_PATH = REPO_ROOT / "examples" / "foundation_runtime_secret_handoff_rehearsal_witness.awaiting_evidence.json"

REQUIRED_ROOT_KEYS = (
    "schema_version",
    "witness_id",
    "status",
    "solver_outcome",
    "field_labels",
    "blocked_claims",
    "runtime_witness_secret_name_recorded",
    "runtime_conformance_secret_name_recorded",
    "deployment_witness_secret_name_recorded",
    "secret_value_recorded",
    "ignored_local_handoff_path_recorded",
    "secret_manager_target_recorded",
    "operator_identity_recorded",
    "dual_control_verified",
    "secret_presence_attestation_claimed",
    "secret_rotation_claimed",
    "secret_revocation_claimed",
    "workflow_secret_mount_claimed",
    "runtime_env_binding_claimed",
    "preflight_secret_gate_pass_claimed",
    "repository_secret_binding_allowed",
    "runtime_secret_store_binding_allowed",
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
    "schema_version": "foundation.runtime_secret_handoff_rehearsal.v1",
    "witness_id": "foundation_runtime_secret_handoff_rehearsal_witness.awaiting_evidence.v1",
    "status": "AwaitingEvidence",
    "solver_outcome": "AwaitingEvidence",
}
FALSE_FLAGS = (
    "runtime_witness_secret_name_recorded",
    "runtime_conformance_secret_name_recorded",
    "deployment_witness_secret_name_recorded",
    "secret_value_recorded",
    "ignored_local_handoff_path_recorded",
    "secret_manager_target_recorded",
    "operator_identity_recorded",
    "dual_control_verified",
    "secret_presence_attestation_claimed",
    "secret_rotation_claimed",
    "secret_revocation_claimed",
    "workflow_secret_mount_claimed",
    "runtime_env_binding_claimed",
    "preflight_secret_gate_pass_claimed",
    "repository_secret_binding_allowed",
    "runtime_secret_store_binding_allowed",
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
    "runtime_witness_secret_name_label",
    "runtime_conformance_secret_name_label",
    "deployment_witness_secret_name_label",
    "runtime_secret_manager_target_label",
    "ignored_local_handoff_file_label",
    "handoff_operator_identity_label",
    "dual_control_gate_label",
    "secret_value_absence_gate_label",
    "secret_presence_attestation_label",
    "secret_rotation_gate_label",
    "secret_revocation_gate_label",
    "workflow_secret_mount_gate_label",
    "runtime_env_binding_gate_label",
    "preflight_secret_gate_label",
    "operator_reassessment_gate",
)
BLOCKED_CLAIMS = (
    "runtime witness secret name claim",
    "runtime conformance secret name claim",
    "deployment witness secret name claim",
    "secret value",
    "ignored local handoff path",
    "secret manager target",
    "operator identity",
    "dual control verification",
    "secret presence attestation",
    "secret rotation claim",
    "secret revocation claim",
    "workflow secret mount claim",
    "runtime env binding claim",
    "preflight secret gate pass claim",
    "repository secret binding",
    "runtime secret store binding",
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
    "runtime_witness_secret_name_label": "Runtime witness secret-name gate label only; the secret name is not recorded or claimed.",
    "runtime_conformance_secret_name_label": "Runtime conformance secret-name gate label only; the secret name is not recorded or claimed.",
    "deployment_witness_secret_name_label": "Deployment witness secret-name gate label only; the secret name is not recorded or claimed.",
    "runtime_secret_manager_target_label": "Runtime secret-manager target label only; target values are not recorded.",
    "ignored_local_handoff_file_label": "Ignored local handoff file label only; private paths are not recorded.",
    "handoff_operator_identity_label": "Handoff operator identity label only; identities are not recorded.",
    "dual_control_gate_label": "Dual-control gate label only; dual-control proof is not claimed.",
    "secret_value_absence_gate_label": "Secret value absence gate label only; secret values are not recorded.",
    "secret_presence_attestation_label": "Secret presence attestation label only; secret presence is not claimed.",
    "secret_rotation_gate_label": "Secret rotation gate label only; rotation is not claimed.",
    "secret_revocation_gate_label": "Secret revocation gate label only; revocation is not claimed.",
    "workflow_secret_mount_gate_label": "Workflow secret mount gate label only; workflow secret mount is not claimed.",
    "runtime_env_binding_gate_label": "Runtime env binding gate label only; runtime env binding is not claimed.",
    "preflight_secret_gate_label": "Preflight secret gate label only; preflight pass is not claimed.",
    "operator_reassessment_gate": "Operator reassessment gate only; readiness and deployment are not approved.",
}
SURFACE_TYPES_BY_ID = {
    "runtime_witness_secret_name_label": "blocked_secret_name_label",
    "runtime_conformance_secret_name_label": "blocked_secret_name_label",
    "deployment_witness_secret_name_label": "blocked_secret_name_label",
    "runtime_secret_manager_target_label": "blocked_target_label",
    "ignored_local_handoff_file_label": "blocked_private_path_label",
    "handoff_operator_identity_label": "blocked_identity_label",
    "dual_control_gate_label": "local_gate_label",
    "secret_value_absence_gate_label": "local_gate_label",
    "secret_presence_attestation_label": "blocked_presence_label",
    "secret_rotation_gate_label": "local_gate_label",
    "secret_revocation_gate_label": "local_gate_label",
    "workflow_secret_mount_gate_label": "blocked_workflow_mount_label",
    "runtime_env_binding_gate_label": "blocked_runtime_binding_label",
    "preflight_secret_gate_label": "blocked_preflight_label",
    "operator_reassessment_gate": "local_gate_label",
}
REQUIRED_DOC_PHRASES = (
    "Foundation Runtime Secret Handoff Rehearsal Boundary",
    "Witness packet: [`../examples/foundation_runtime_secret_handoff_rehearsal_witness.awaiting_evidence.json`]",
    "Rule: Runtime secret handoff rehearsal is a local gate-label map",
    "No runtime witness secret-name claim, runtime conformance secret-name claim,",
    "runtime_secret_handoff_rehearsal_state=AwaitingEvidence",
    "runtime_witness_secret_name_recorded=false",
    "runtime_conformance_secret_name_recorded=false",
    "deployment_witness_secret_name_recorded=false",
    "secret_value_recorded=false",
    "ignored_local_handoff_path_recorded=false",
    "secret_manager_target_recorded=false",
    "operator_identity_recorded=false",
    "dual_control_verified=false",
    "secret_presence_attestation_claimed=false",
    "secret_rotation_claimed=false",
    "secret_revocation_claimed=false",
    "workflow_secret_mount_claimed=false",
    "runtime_env_binding_claimed=false",
    "preflight_secret_gate_pass_claimed=false",
    "repository_secret_binding_allowed=false",
    "runtime_secret_store_binding_allowed=false",
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
    "python scripts/validate_foundation_runtime_secret_handoff_rehearsal_boundary.py",
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
            r"\b(?:secret|token|key|certificate|path|file|target|operator|workflow|artifact|approval|env)\w*\s*=",
            re.IGNORECASE,
        ),
    ),
)
FORBIDDEN_PROMOTION_PATTERNS = (
    ("secret_present", re.compile(r"\bsecret presence\s+(?:is\s+)?(?:attested|verified|confirmed|claimed)\b", re.IGNORECASE)),
    ("secret_bound", re.compile(r"\bsecret\s+(?:is\s+)?(?:bound|mounted|configured)\b", re.IGNORECASE)),
    ("secret_value_recorded", re.compile(r"\bsecret value\s+(?:is\s+)?recorded\b", re.IGNORECASE)),
    ("workflow_mounted", re.compile(r"\bworkflow secret\s+(?:is\s+)?mounted\b", re.IGNORECASE)),
    ("runtime_bound", re.compile(r"\bruntime env binding\s+(?:is\s+)?(?:ready|verified|complete)\b", re.IGNORECASE)),
    ("preflight_passed", re.compile(r"\bpreflight secret gate\s+(?:has\s+)?passed\b", re.IGNORECASE)),
    ("readiness_claim", re.compile(r"\breadiness\s+(?:is\s+)?(?:ready|promoted|approved|complete)\b", re.IGNORECASE)),
    ("deployment_ready", re.compile(r"\bdeployment\s+(?:is\s+)?(?:ready|approved|complete)\b", re.IGNORECASE)),
)


@dataclass(frozen=True)
class Finding:
    """One deterministic runtime secret handoff rehearsal finding."""

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
    """Validate runtime secret handoff rehearsal artifacts."""

    doc_text = load_text(doc_path, "runtime secret handoff rehearsal boundary doc")
    packet_payload = load_json_object(packet_path, "runtime secret handoff rehearsal witness packet")

    findings: list[Finding] = []
    findings.extend(_validate_doc(doc_text))
    findings.extend(_validate_packet(packet_payload))
    findings.extend(_validate_forbidden_patterns(json.dumps(packet_payload, sort_keys=True), "witness"))
    return findings


def _validate_doc(doc_text: str) -> list[Finding]:
    findings: list[Finding] = []
    for phrase in REQUIRED_DOC_PHRASES:
        if phrase not in doc_text:
            findings.append(Finding("doc_required_phrase", f"runtime secret handoff rehearsal doc missing required phrase: {phrase}"))
    for label in FIELD_LABELS:
        if label not in doc_text:
            findings.append(Finding("doc_field_label", f"runtime secret handoff rehearsal doc missing label: {label}"))
    return findings


def _validate_packet(packet: dict[str, Any]) -> list[Finding]:
    findings: list[Finding] = []
    if tuple(packet.keys()) != REQUIRED_ROOT_KEYS:
        findings.append(Finding("witness_root_keys", "runtime secret handoff rehearsal witness root keys drifted"))
    for key, expected_value in EXPECTED_ROOT_VALUES.items():
        if packet.get(key) != expected_value:
            findings.append(Finding("witness_identity", f"runtime secret handoff rehearsal {key} must be {expected_value!r}"))
    for key in FALSE_FLAGS:
        if packet.get(key) is not False:
            findings.append(Finding("witness_false_flag", f"runtime secret handoff rehearsal {key} must remain false"))
    if tuple(packet.get("field_labels", ())) != FIELD_LABELS:
        findings.append(Finding("witness_field_labels", "runtime secret handoff rehearsal field_labels drifted"))
    if tuple(packet.get("blocked_claims", ())) != BLOCKED_CLAIMS:
        findings.append(Finding("witness_blocked_claims", "runtime secret handoff rehearsal blocked_claims drifted"))
    surfaces = packet.get("surfaces")
    if not isinstance(surfaces, list):
        findings.append(Finding("witness_surfaces_type", "runtime secret handoff rehearsal surfaces must be a list"))
        return findings
    observed_surface_ids: list[str] = []
    for surface in surfaces:
        if not isinstance(surface, dict):
            findings.append(Finding("witness_surface_object", "runtime secret handoff rehearsal surface must be an object"))
            continue
        observed_surface_ids.append(str(surface.get("surface_id")))
        findings.extend(_validate_surface(surface))
    if tuple(observed_surface_ids) != FIELD_LABELS:
        findings.append(Finding("witness_surface_inventory", "runtime secret handoff rehearsal surface inventory drifted"))
    if len(set(observed_surface_ids)) != len(observed_surface_ids):
        findings.append(Finding("witness_surface_duplicate", "runtime secret handoff rehearsal surfaces must not duplicate ids"))
    return findings


def _validate_surface(surface: dict[str, Any]) -> list[Finding]:
    findings: list[Finding] = []
    surface_id = surface.get("surface_id")
    expected_keys = ("surface_id", "surface_type", "state", "evidence_ref", "public_safe_note")
    if tuple(surface.keys()) != expected_keys:
        findings.append(Finding("witness_surface_keys", f"runtime secret handoff rehearsal surface keys drifted: {surface_id}"))
    if surface_id not in SURFACE_NOTES_BY_ID:
        findings.append(Finding("witness_surface_id", f"runtime secret handoff rehearsal surface id is unknown: {surface_id}"))
        return findings
    if surface.get("surface_type") != SURFACE_TYPES_BY_ID[surface_id]:
        findings.append(Finding("witness_surface_type", f"runtime secret handoff rehearsal surface type drifted: {surface_id}"))
    if surface.get("state") != "AwaitingEvidence":
        findings.append(Finding("witness_surface_state", f"runtime secret handoff rehearsal surface must remain AwaitingEvidence: {surface_id}"))
    if surface.get("evidence_ref") != "future_operator_secret_handoff":
        findings.append(Finding("witness_surface_evidence_ref", f"runtime secret handoff rehearsal surface evidence_ref drifted: {surface_id}"))
    if surface.get("public_safe_note") != SURFACE_NOTES_BY_ID[surface_id]:
        findings.append(Finding("witness_surface_note", f"runtime secret handoff rehearsal surface note drifted: {surface_id}"))
    return findings


def _validate_forbidden_patterns(text: str, artifact_label: str) -> list[Finding]:
    findings: list[Finding] = []
    for rule_id, pattern in FORBIDDEN_VALUE_PATTERNS:
        if pattern.search(text):
            findings.append(
                Finding(
                    "forbidden_value_pattern",
                    f"runtime secret handoff rehearsal {artifact_label} contains forbidden value pattern: {rule_id}",
                )
            )
    for rule_id, pattern in FORBIDDEN_PROMOTION_PATTERNS:
        if pattern.search(text):
            findings.append(
                Finding(
                    "forbidden_promotion_pattern",
                    f"runtime secret handoff rehearsal {artifact_label} contains forbidden promotion pattern: {rule_id}",
                )
            )
    return findings


def main(argv: list[str] | None = None) -> int:
    """Validate runtime secret handoff rehearsal artifacts and print status."""

    parser = argparse.ArgumentParser(
        description="Validate Foundation Mode runtime secret handoff rehearsal boundary artifacts."
    )
    parser.add_argument("--doc", type=Path, default=DEFAULT_DOC_PATH)
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET_PATH)
    args = parser.parse_args(argv)

    try:
        findings = validate_artifacts(args.doc, args.packet)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        sys.stderr.write(f"[FAIL] load-runtime-secret-handoff-rehearsal: {exc}\nSTATUS: failed\n")
        return 1
    if findings:
        for finding in findings:
            sys.stderr.write(f"[FAIL] {finding.rule_id}: {finding.message}\n")
        sys.stderr.write("STATUS: failed\n")
        return 1
    sys.stdout.write("[PASS] foundation_runtime_secret_handoff_rehearsal_doc\n")
    sys.stdout.write("[PASS] foundation_runtime_secret_handoff_rehearsal_witness\n")
    sys.stdout.write("STATUS: passed\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
