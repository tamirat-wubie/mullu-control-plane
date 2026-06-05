#!/usr/bin/env python3
"""Validate the Foundation Mode deployment upstream API gate rehearsal boundary.

Purpose: keep issue #330 upstream API gate preparation local and public-safe
while upstream readiness, reporter execution, target values, production
dependency values, DNS publication, repository-variable binding, workflow
dispatch, publication, and deployment remain blocked.
Governance scope: Foundation Mode, issue #330 upstream API gate rehearsal,
public-safe gate labels, external-value blocking, upstream reporter blocking,
DNS target-selection blocking, workflow blocking, publication blocking, and
deployment restraint.
Dependencies: docs/FOUNDATION_DEPLOYMENT_UPSTREAM_API_GATE_REHEARSAL_BOUNDARY.md
and examples/foundation_deployment_upstream_api_gate_rehearsal_witness.awaiting_evidence.json.
Invariants:
  - Validation is read-only.
  - The witness records public-safe upstream API gate labels only.
  - No upstream readiness, reporter execution, require-ready pass, target URL
    value, production dependency value, API provisioning, DNS publication, DNS
    target selection, repository-variable binding, workflow dispatch, artifact
    publication, readiness claim, customer access, money movement,
    legal/business claim, external publication, or deployment claim is allowed.
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
DEFAULT_DOC_PATH = REPO_ROOT / "docs" / "FOUNDATION_DEPLOYMENT_UPSTREAM_API_GATE_REHEARSAL_BOUNDARY.md"
DEFAULT_PACKET_PATH = (
    REPO_ROOT / "examples" / "foundation_deployment_upstream_api_gate_rehearsal_witness.awaiting_evidence.json"
)

EXPECTED_WITNESS_ID = "foundation_deployment_upstream_api_gate_rehearsal_witness.awaiting_evidence.v1"
EXPECTED_FIELD_LABELS = (
    "upstream_reporter_command_label",
    "target_gateway_url_label",
    "recovery_witness_gate_label",
    "production_image_gate_label",
    "runtime_host_gate_label",
    "managed_postgres_gate_label",
    "schema_application_gate_label",
    "production_secret_store_gate_label",
    "deploy_env_gate_label",
    "release_preflight_gate_label",
    "persistence_check_gate_label",
    "host_firewall_gate_label",
    "tls_certificate_gate_label",
    "rollback_path_gate_label",
    "private_runtime_witness_gate_label",
    "dns_authority_gate_label",
    "runtime_witness_closure_gate_label",
    "api_provisioning_stop_rule_label",
    "dns_publication_stop_rule_label",
    "operator_reassessment_gate",
)
EXPECTED_BLOCKED_FALSE_FLAGS = (
    "api_provisioning_allowed",
    "artifact_publication_allowed",
    "company_formation_claimed",
    "customer_access_allowed",
    "deployment_allowed",
    "deploy_env_value_recorded",
    "dns_authority_value_recorded",
    "dns_publication_allowed",
    "dns_target_selection_allowed",
    "external_publication_allowed",
    "host_firewall_value_recorded",
    "legal_clearance_claimed",
    "managed_postgres_value_recorded",
    "money_movement_allowed",
    "patent_claimed",
    "persistence_check_value_recorded",
    "personal_data_collection_allowed",
    "private_runtime_witness_value_recorded",
    "production_image_value_recorded",
    "readiness_claimed",
    "release_preflight_value_recorded",
    "repository_variable_binding_allowed",
    "require_ready_pass_claimed",
    "rollback_path_value_recorded",
    "runtime_host_value_recorded",
    "runtime_witness_closure_claimed",
    "schema_application_value_recorded",
    "secret_store_value_recorded",
    "target_gateway_url_value_recorded",
    "tls_certificate_value_recorded",
    "upstream_api_ready_claimed",
    "upstream_reporter_executed",
    "workflow_dispatch_allowed",
)
EXPECTED_BLOCKED_CLAIMS = (
    "upstream API readiness claim",
    "upstream reporter execution claim",
    "require-ready pass claim",
    "target gateway URL value",
    "production image value",
    "runtime host value",
    "managed PostgreSQL value",
    "schema application value",
    "secret store value",
    "deploy env value",
    "release preflight value",
    "persistence check value",
    "host firewall value",
    "TLS certificate value",
    "rollback path value",
    "private runtime witness value",
    "DNS authority value",
    "runtime witness closure claim",
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
EXPECTED_SURFACES = (
    ("upstream_reporter_command_label", "local_gate_label", "AwaitingEvidence"),
    ("target_gateway_url_label", "blocked_external_value", "AwaitingEvidence"),
    ("recovery_witness_gate_label", "blocked_external_evidence", "AwaitingEvidence"),
    ("production_image_gate_label", "blocked_external_value", "AwaitingEvidence"),
    ("runtime_host_gate_label", "blocked_external_value", "AwaitingEvidence"),
    ("managed_postgres_gate_label", "blocked_external_value", "AwaitingEvidence"),
    ("schema_application_gate_label", "blocked_external_evidence", "AwaitingEvidence"),
    ("production_secret_store_gate_label", "blocked_external_value", "AwaitingEvidence"),
    ("deploy_env_gate_label", "blocked_external_evidence", "AwaitingEvidence"),
    ("release_preflight_gate_label", "blocked_external_evidence", "AwaitingEvidence"),
    ("persistence_check_gate_label", "blocked_external_evidence", "AwaitingEvidence"),
    ("host_firewall_gate_label", "blocked_external_evidence", "AwaitingEvidence"),
    ("tls_certificate_gate_label", "blocked_external_value", "AwaitingEvidence"),
    ("rollback_path_gate_label", "blocked_external_evidence", "AwaitingEvidence"),
    ("private_runtime_witness_gate_label", "blocked_external_value", "AwaitingEvidence"),
    ("dns_authority_gate_label", "blocked_external_evidence", "AwaitingEvidence"),
    ("runtime_witness_closure_gate_label", "blocked_external_evidence", "AwaitingEvidence"),
    ("api_provisioning_stop_rule_label", "local_stop_rule", "AwaitingEvidence"),
    ("dns_publication_stop_rule_label", "local_stop_rule", "AwaitingEvidence"),
    ("operator_reassessment_gate", "local_gate_label", "AwaitingEvidence"),
)
EXPECTED_SURFACE_NOTES = {
    "upstream_reporter_command_label": "Upstream reporter command label only; reporter execution is not claimed.",
    "target_gateway_url_label": "Target gateway URL label only; URL values are not recorded.",
    "recovery_witness_gate_label": "Recovery witness gate label only; recovery closure is not claimed.",
    "production_image_gate_label": "Production image gate label only; production image values are not recorded.",
    "runtime_host_gate_label": "Runtime host gate label only; runtime host values are not recorded.",
    "managed_postgres_gate_label": "Managed PostgreSQL gate label only; database values are not recorded.",
    "schema_application_gate_label": "Schema application gate label only; schema application is not claimed.",
    "production_secret_store_gate_label": "Production secret store gate label only; secrets are not recorded or claimed.",
    "deploy_env_gate_label": "Deploy-env gate label only; deploy-env closure is not claimed.",
    "release_preflight_gate_label": "Release preflight gate label only; preflight pass is not claimed.",
    "persistence_check_gate_label": "Persistence check gate label only; persistence proof is not claimed.",
    "host_firewall_gate_label": "Host firewall gate label only; firewall proof is not claimed.",
    "tls_certificate_gate_label": "TLS certificate gate label only; certificate values are not recorded.",
    "rollback_path_gate_label": "Rollback path gate label only; rollback verification is not claimed.",
    "private_runtime_witness_gate_label": "Private runtime witness gate label only; private witness values are not recorded.",
    "dns_authority_gate_label": "DNS authority gate label only; DNS authority is not claimed.",
    "runtime_witness_closure_gate_label": "Runtime witness closure gate label only; witness closure is not claimed.",
    "api_provisioning_stop_rule_label": "API provisioning stop-rule label only; API runtime is not provisioned.",
    "dns_publication_stop_rule_label": (
        "DNS publication stop-rule label only; DNS target selection and publication are not allowed."
    ),
    "operator_reassessment_gate": "Operator reassessment gate only; upstream readiness and deployment are not approved.",
}
EXPECTED_DOC_SURFACE_LABELS = (
    "Upstream reporter command label",
    "Target gateway URL label",
    "Recovery witness gate label",
    "Production image gate label",
    "Runtime host gate label",
    "Managed PostgreSQL gate label",
    "Schema application gate label",
    "Production secret store gate label",
    "Deploy-env gate label",
    "Release preflight gate label",
    "Persistence check gate label",
    "Host firewall gate label",
    "TLS certificate gate label",
    "Rollback path gate label",
    "Private runtime witness gate label",
    "DNS authority gate label",
    "Runtime witness closure gate label",
    "API provisioning stop rule",
    "DNS publication stop rule",
    "Operator reassessment gate",
)
EXPECTED_ROOT_KEYS = {
    "api_provisioning_allowed",
    "artifact_publication_allowed",
    "blocked_claims",
    "company_formation_claimed",
    "customer_access_allowed",
    "deployment_allowed",
    "deploy_env_value_recorded",
    "dns_authority_value_recorded",
    "dns_publication_allowed",
    "dns_target_selection_allowed",
    "external_publication_allowed",
    "field_labels",
    "host_firewall_value_recorded",
    "legal_clearance_claimed",
    "managed_postgres_value_recorded",
    "money_movement_allowed",
    "next_action",
    "patent_claimed",
    "persistence_check_value_recorded",
    "personal_data_collection_allowed",
    "private_runtime_witness_value_recorded",
    "production_image_value_recorded",
    "readiness_claimed",
    "release_preflight_value_recorded",
    "repository_variable_binding_allowed",
    "require_ready_pass_claimed",
    "rollback_path_value_recorded",
    "runtime_host_value_recorded",
    "runtime_witness_closure_claimed",
    "schema_application_value_recorded",
    "schema_version",
    "secret_store_value_recorded",
    "solver_outcome",
    "status",
    "surfaces",
    "target_gateway_url_value_recorded",
    "tls_certificate_value_recorded",
    "upstream_api_ready_claimed",
    "upstream_reporter_executed",
    "witness_id",
    "workflow_dispatch_allowed",
}
EXPECTED_SURFACE_KEYS = {"evidence_ref", "public_safe_note", "state", "surface_id", "surface_type"}
REQUIRED_DOC_PHRASES = (
    "Foundation Deployment Upstream API Gate Rehearsal Boundary",
    "Witness packet: [`../examples/foundation_deployment_upstream_api_gate_rehearsal_witness.awaiting_evidence.json`]",
    "Rule: Deployment upstream API gate rehearsal is a local gate-label map",
    "No upstream API readiness claim, upstream reporter execution claim,",
    "deployment_upstream_api_gate_rehearsal_state=AwaitingEvidence",
    "upstream_api_ready_claimed=false",
    "upstream_reporter_executed=false",
    "require_ready_pass_claimed=false",
    "target_gateway_url_value_recorded=false",
    "production_image_value_recorded=false",
    "runtime_host_value_recorded=false",
    "managed_postgres_value_recorded=false",
    "schema_application_value_recorded=false",
    "secret_store_value_recorded=false",
    "deploy_env_value_recorded=false",
    "release_preflight_value_recorded=false",
    "persistence_check_value_recorded=false",
    "host_firewall_value_recorded=false",
    "tls_certificate_value_recorded=false",
    "rollback_path_value_recorded=false",
    "private_runtime_witness_value_recorded=false",
    "dns_authority_value_recorded=false",
    "runtime_witness_closure_claimed=false",
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
    "python scripts/validate_foundation_deployment_upstream_api_gate_rehearsal_boundary.py",
)
FORBIDDEN_VALUE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("url_value", re.compile(r"https?://", re.IGNORECASE)),
    ("email_value", re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)),
    ("private_path", re.compile(r"\b[A-Za-z]:[\\/]|\\\\", re.IGNORECASE)),
    ("private_key_block", re.compile(r"-----BEGIN\s+(?:RSA\s+|EC\s+|OPENSSH\s+)?PRIVATE\s+KEY-----", re.IGNORECASE)),
    ("ip_value", re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")),
    ("timestamp_value", re.compile(r"\b20\d{2}-\d{2}-\d{2}(?:T\d{2}:\d{2})?", re.IGNORECASE)),
)
FORBIDDEN_PROMOTION_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("upstream_ready", re.compile(r"\bupstream API\s+(?:is\s+)?(?:ready|verified|complete)\b", re.IGNORECASE)),
    ("reporter_executed", re.compile(r"\bupstream reporter\s+(?:is\s+)?(?:executed|run|complete)\b", re.IGNORECASE)),
    ("require_ready_passed", re.compile(r"\brequire-ready\s+(?:is\s+)?(?:passed|ready|complete)\b", re.IGNORECASE)),
    ("dns_selected", re.compile(r"\bDNS target\s+(?:is\s+)?(?:selected|ready|published)\b", re.IGNORECASE)),
    ("api_provisioned", re.compile(r"\bAPI runtime\s+(?:is\s+)?(?:provisioned|ready|live)\b", re.IGNORECASE)),
    (
        "workflow_dispatched",
        re.compile(r"\bworkflow\s+(?:is\s+|was\s+|has\s+been\s+)(?:dispatched|run|ready)\b", re.IGNORECASE),
    ),
    ("artifact_published", re.compile(r"\bartifact\s+(?:is\s+)?(?:published|ready|complete)\b", re.IGNORECASE)),
    ("deployment_ready", re.compile(r"\bdeployment\s+(?:is\s+)?(?:ready|approved|complete)\b", re.IGNORECASE)),
)


@dataclass(frozen=True, slots=True)
class UpstreamApiGateFinding:
    """One deterministic upstream API gate rehearsal validation finding."""

    rule_id: str
    message: str


def load_text(path: Path, artifact_label: str) -> str:
    """Load one required text artifact."""

    if not path.exists():
        raise FileNotFoundError(f"{artifact_label} missing: {path}")
    if not path.is_file():
        raise IsADirectoryError(f"{artifact_label} path is not a file: {path}")
    return path.read_text(encoding="utf-8")


def load_json_object(path: Path, artifact_label: str) -> dict[str, Any]:
    """Load one required JSON object artifact."""

    if not path.exists():
        raise FileNotFoundError(f"{artifact_label} missing: {path}")
    if not path.is_file():
        raise IsADirectoryError(f"{artifact_label} path is not a file: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{artifact_label} must be a JSON object")
    return payload


def validate_doc_text(doc_text: str) -> list[UpstreamApiGateFinding]:
    """Return findings for upstream API gate rehearsal documentation drift."""

    findings: list[UpstreamApiGateFinding] = []
    for phrase in REQUIRED_DOC_PHRASES:
        if phrase not in doc_text:
            findings.append(
                UpstreamApiGateFinding(
                    "foundation_deployment_upstream_api_gate_rehearsal_doc_phrase_missing",
                    f"upstream API gate rehearsal doc missing required phrase: {phrase}",
                )
            )
    for label in EXPECTED_FIELD_LABELS:
        if label not in doc_text:
            findings.append(
                UpstreamApiGateFinding(
                    "foundation_deployment_upstream_api_gate_rehearsal_doc_label_missing",
                    f"upstream API gate rehearsal doc missing field label: {label}",
                )
            )
    for label in EXPECTED_DOC_SURFACE_LABELS:
        if label not in doc_text:
            findings.append(
                UpstreamApiGateFinding(
                    "foundation_deployment_upstream_api_gate_rehearsal_doc_surface_missing",
                    f"upstream API gate rehearsal doc missing surface label: {label}",
                )
            )
    findings.extend(_scan_forbidden_strings(doc_text, "doc"))
    return findings


def validate_packet(payload: dict[str, Any]) -> list[UpstreamApiGateFinding]:
    """Return findings for upstream API gate rehearsal witness drift."""

    findings: list[UpstreamApiGateFinding] = []
    if set(payload) != EXPECTED_ROOT_KEYS:
        findings.append(
            UpstreamApiGateFinding(
                "deployment_upstream_api_gate_rehearsal_root_keys_invalid",
                "upstream API gate rehearsal witness root keys drifted",
            )
        )
    if payload.get("witness_id") != EXPECTED_WITNESS_ID:
        findings.append(
            UpstreamApiGateFinding(
                "deployment_upstream_api_gate_rehearsal_root_value_invalid",
                "upstream API gate rehearsal witness_id drifted",
            )
        )
    for key, expected_value in (
        ("schema_version", 1),
        ("status", "AwaitingEvidence"),
        ("solver_outcome", "AwaitingEvidence"),
    ):
        if payload.get(key) != expected_value:
            findings.append(
                UpstreamApiGateFinding(
                    "deployment_upstream_api_gate_rehearsal_root_value_invalid",
                    f"upstream API gate rehearsal {key} must be {expected_value!r}",
                )
            )
    for key in EXPECTED_BLOCKED_FALSE_FLAGS:
        if payload.get(key) is not False:
            findings.append(
                UpstreamApiGateFinding(
                    "deployment_upstream_api_gate_rehearsal_root_value_invalid",
                    f"upstream API gate rehearsal {key} must remain false",
                )
            )
    if tuple(payload.get("field_labels", ())) != EXPECTED_FIELD_LABELS:
        findings.append(
            UpstreamApiGateFinding(
                "deployment_upstream_api_gate_rehearsal_root_value_invalid",
                "upstream API gate rehearsal field_labels drifted",
            )
        )
    if tuple(payload.get("blocked_claims", ())) != EXPECTED_BLOCKED_CLAIMS:
        findings.append(
            UpstreamApiGateFinding(
                "deployment_upstream_api_gate_rehearsal_root_value_invalid",
                "upstream API gate rehearsal blocked_claims drifted",
            )
        )
    findings.extend(_validate_surfaces(payload.get("surfaces")))
    findings.extend(_scan_forbidden_strings(json.dumps(payload, sort_keys=True), "witness"))
    return findings


def validate_foundation_deployment_upstream_api_gate_rehearsal_boundary(
    doc_path: Path = DEFAULT_DOC_PATH,
    packet_path: Path = DEFAULT_PACKET_PATH,
) -> list[UpstreamApiGateFinding]:
    """Validate the Foundation Mode upstream API gate rehearsal artifacts."""

    doc_text = load_text(doc_path, "deployment upstream API gate rehearsal boundary doc")
    packet_payload = load_json_object(packet_path, "deployment upstream API gate rehearsal witness packet")
    return [*validate_doc_text(doc_text), *validate_packet(packet_payload)]


def _validate_surfaces(surfaces: Any) -> list[UpstreamApiGateFinding]:
    findings: list[UpstreamApiGateFinding] = []
    if not isinstance(surfaces, list):
        return [
            UpstreamApiGateFinding(
                "deployment_upstream_api_gate_rehearsal_surfaces_invalid",
                "upstream API gate rehearsal surfaces must be a list",
            )
        ]
    observed = tuple(
        (
            surface.get("surface_id"),
            surface.get("surface_type"),
            surface.get("state"),
        )
        for surface in surfaces
        if isinstance(surface, dict)
    )
    if observed != EXPECTED_SURFACES:
        findings.append(
            UpstreamApiGateFinding(
                "deployment_upstream_api_gate_rehearsal_surface_inventory_invalid",
                "upstream API gate rehearsal surface inventory does not match the Foundation Mode set",
            )
        )
    seen_surface_ids: set[str] = set()
    for surface in surfaces:
        if not isinstance(surface, dict):
            findings.append(
                UpstreamApiGateFinding(
                    "deployment_upstream_api_gate_rehearsal_surface_keys_invalid",
                    "upstream API gate rehearsal surface must be an object",
                )
            )
            continue
        if set(surface) != EXPECTED_SURFACE_KEYS:
            findings.append(
                UpstreamApiGateFinding(
                    "deployment_upstream_api_gate_rehearsal_surface_keys_invalid",
                    f"upstream API gate rehearsal surface keys drifted: {surface.get('surface_id')}",
                )
            )
        surface_id = str(surface.get("surface_id", ""))
        if surface_id in seen_surface_ids:
            findings.append(
                UpstreamApiGateFinding(
                    "deployment_upstream_api_gate_rehearsal_surface_duplicate",
                    f"upstream API gate rehearsal surface duplicated: {surface_id}",
                )
            )
        seen_surface_ids.add(surface_id)
        if surface.get("state") != "AwaitingEvidence":
            findings.append(
                UpstreamApiGateFinding(
                    "deployment_upstream_api_gate_rehearsal_surface_state_invalid",
                    f"upstream API gate rehearsal surface must remain AwaitingEvidence: {surface_id}",
                )
            )
        if surface.get("evidence_ref") != "manual_preparation_pending":
            findings.append(
                UpstreamApiGateFinding(
                    "deployment_upstream_api_gate_rehearsal_surface_evidence_invalid",
                    f"upstream API gate rehearsal surface evidence_ref drifted: {surface_id}",
                )
            )
        if surface.get("public_safe_note") != EXPECTED_SURFACE_NOTES.get(surface_id):
            findings.append(
                UpstreamApiGateFinding(
                    "deployment_upstream_api_gate_rehearsal_surface_note_invalid",
                    f"upstream API gate rehearsal surface note drifted: {surface_id}",
                )
            )
    return findings


def _scan_forbidden_strings(text: str, artifact_label: str) -> list[UpstreamApiGateFinding]:
    findings: list[UpstreamApiGateFinding] = []
    for rule_id, pattern in FORBIDDEN_VALUE_PATTERNS:
        if pattern.search(text):
            findings.append(
                UpstreamApiGateFinding(
                    "deployment_upstream_api_gate_rehearsal_forbidden_value_pattern",
                    f"upstream API gate rehearsal {artifact_label} contains forbidden value pattern: {rule_id}",
                )
            )
    for rule_id, pattern in FORBIDDEN_PROMOTION_PATTERNS:
        if pattern.search(text):
            findings.append(
                UpstreamApiGateFinding(
                    "deployment_upstream_api_gate_rehearsal_forbidden_promotion_phrase",
                    f"upstream API gate rehearsal {artifact_label} contains forbidden promotion pattern: {rule_id}",
                )
            )
    return findings


def main(argv: list[str] | None = None) -> int:
    """Validate upstream API gate rehearsal artifacts and print deterministic status."""

    parser = argparse.ArgumentParser(
        description="Validate Foundation Mode deployment upstream API gate rehearsal boundary artifacts."
    )
    parser.add_argument("--doc", type=Path, default=DEFAULT_DOC_PATH)
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET_PATH)
    args = parser.parse_args(argv)

    try:
        findings = validate_foundation_deployment_upstream_api_gate_rehearsal_boundary(args.doc, args.packet)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"[FAIL] foundation_deployment_upstream_api_gate_rehearsal_load: {exc}", file=sys.stderr)
        print("STATUS: failed", file=sys.stderr)
        return 1

    if findings:
        for finding in findings:
            print(f"[FAIL] {finding.rule_id}: {finding.message}", file=sys.stderr)
        print("STATUS: failed", file=sys.stderr)
        return 1

    print("[PASS] foundation_deployment_upstream_api_gate_rehearsal_doc")
    print("[PASS] foundation_deployment_upstream_api_gate_rehearsal_witness")
    print("STATUS: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
