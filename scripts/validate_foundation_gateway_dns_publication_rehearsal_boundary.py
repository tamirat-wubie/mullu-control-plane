#!/usr/bin/env python3
"""Validate the Foundation Mode gateway DNS publication rehearsal boundary.

Purpose: keep issue #330 gateway DNS publication preparation local and
public-safe while DNS provider accounts, zones, records, TTL values, DNS
mutation, repository-variable binding, workflow dispatch, proof claims,
approval, readiness, external publication, and deployment remain blocked.
Governance scope: Foundation Mode, issue #330 DNS publication rehearsal,
public-safe gate labels, DNS mutation blocking, proof blocking, approval
blocking, money blocking, legal/business restraint, publication blocking, and
deployment blocking.
Dependencies: docs/FOUNDATION_GATEWAY_DNS_PUBLICATION_REHEARSAL_BOUNDARY.md
and examples/foundation_gateway_dns_publication_rehearsal_witness.awaiting_evidence.json.
Invariants:
  - Validation is read-only.
  - The witness records public-safe DNS publication gate labels only.
  - No DNS provider account value, DNS zone value, DNS record name, DNS record
    type, DNS record value, TTL value, DNS mutation, repository-variable
    binding, workflow dispatch, propagation proof, rollback proof, DNS proof,
    endpoint proof, artifact publication, approval, readiness, customer access,
    personal data, money movement, legal clearance, company formation, patent
    claim, external publication, or deployment claim is allowed.
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
DEFAULT_DOC_PATH = REPO_ROOT / "docs" / "FOUNDATION_GATEWAY_DNS_PUBLICATION_REHEARSAL_BOUNDARY.md"
DEFAULT_PACKET_PATH = (
    REPO_ROOT / "examples" / "foundation_gateway_dns_publication_rehearsal_witness.awaiting_evidence.json"
)

EXPECTED_WITNESS_ID = "foundation_gateway_dns_publication_rehearsal_witness.awaiting_evidence.v1"
EXPECTED_QUESTION_LABELS = (
    "target_binding_receipt_dependency_label",
    "dns_provider_boundary_label",
    "dns_zone_boundary_label",
    "record_name_publication_label",
    "record_type_publication_label",
    "record_value_publication_label",
    "ttl_publication_label",
    "pre_publication_require_ready_gate_label",
    "dry_run_publication_command_label",
    "post_publication_resolution_gate_label",
    "dns_rollback_label",
    "operator_reassessment_gate",
)
EXPECTED_BLOCKED_CLAIMS = (
    "dns provider account value",
    "dns zone value",
    "dns record name value",
    "dns record type value",
    "dns record value",
    "ttl value",
    "dns mutation",
    "repository variable binding",
    "workflow dispatch",
    "dns propagation proof",
    "dns rollback proof",
    "dns resolution proof",
    "endpoint reachability proof",
    "artifact publication",
    "operator approval",
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
EXPECTED_NEXT_ACTION = (
    "record public-safe DNS publication rehearsal gate labels only; do not "
    "record provider accounts, DNS zones, record names, record types, record "
    "values, TTL values, mutate DNS, bind repository variables, dispatch "
    "workflows, claim propagation proof, claim rollback proof, claim DNS "
    "resolution proof, claim endpoint reachability proof, publish artifacts, "
    "claim operator approval, claim readiness, open customer access, collect "
    "personal data, move money, claim legal clearance, form a company, claim "
    "patent protection, publish externally, or deploy"
)
EXPECTED_SURFACES = (
    ("target_binding_dependency_label", "blocked_external_route", "AwaitingEvidence"),
    ("dns_provider_boundary_label", "local_gate_label", "AwaitingEvidence"),
    ("dns_zone_boundary_label", "local_gate_label", "AwaitingEvidence"),
    ("record_name_publication_label", "local_gate_label", "AwaitingEvidence"),
    ("record_type_publication_label", "local_gate_label", "AwaitingEvidence"),
    ("record_value_publication_label", "local_gate_label", "AwaitingEvidence"),
    ("ttl_publication_label", "local_gate_label", "AwaitingEvidence"),
    ("pre_publication_require_ready_gate_label", "blocked_external_route", "AwaitingEvidence"),
    ("dry_run_publication_command_label", "local_gate_label", "AwaitingEvidence"),
    ("post_publication_resolution_gate_label", "blocked_external_route", "AwaitingEvidence"),
    ("dns_rollback_label", "blocked_external_route", "AwaitingEvidence"),
    ("operator_reassessment_gate", "local_gate_label", "AwaitingEvidence"),
)
EXPECTED_SURFACE_NOTES = {
    "target_binding_dependency_label": "Target-binding dependency label only; target binding is not promoted.",
    "dns_provider_boundary_label": "DNS provider boundary label only; provider account values are not recorded.",
    "dns_zone_boundary_label": "DNS zone boundary label only; zone values are not recorded.",
    "record_name_publication_label": "Record-name publication label only; record names are not recorded.",
    "record_type_publication_label": "Record-type publication label only; record types are not recorded.",
    "record_value_publication_label": "Record-value publication label only; record values are not recorded.",
    "ttl_publication_label": "TTL publication label only; TTL values are not recorded.",
    "pre_publication_require_ready_gate_label": "Pre-publication require-ready gate label only; publication is not approved.",
    "dry_run_publication_command_label": "Dry-run publication command label only; DNS mutation is not allowed.",
    "post_publication_resolution_gate_label": "Post-publication resolution gate label only; DNS proof is not claimed.",
    "dns_rollback_label": "DNS rollback label only; rollback proof is not claimed.",
    "operator_reassessment_gate": "Operator reassessment gate only; DNS publication and deployment are not approved.",
}
EXPECTED_DOC_SURFACE_LABELS = (
    "Target-binding dependency label",
    "Provider boundary label",
    "Zone boundary label",
    "Record-name publication label",
    "Record-type publication label",
    "Record-value publication label",
    "TTL publication label",
    "Require-ready gate label",
    "Dry-run publication command label",
    "Post-publication resolution gate label",
    "DNS rollback label",
    "Operator reassessment gate",
)
EXPECTED_ROOT_KEYS = {
    "artifact_publication_allowed",
    "blocked_claims",
    "company_formation_claimed",
    "customer_access_allowed",
    "deployment_allowed",
    "dns_mutation_allowed",
    "dns_propagation_claimed",
    "dns_provider_account_recorded",
    "dns_record_name_recorded",
    "dns_record_type_value_recorded",
    "dns_record_value_recorded",
    "dns_resolution_claimed",
    "dns_rollback_claimed",
    "dns_zone_value_recorded",
    "endpoint_reachability_claimed",
    "external_publication_allowed",
    "legal_clearance_claimed",
    "money_movement_allowed",
    "next_action",
    "operator_approval_claimed",
    "patent_claimed",
    "personal_data_collection_allowed",
    "question_labels",
    "readiness_claimed",
    "repository_variable_bound",
    "schema_version",
    "solver_outcome",
    "status",
    "surfaces",
    "ttl_value_recorded",
    "witness_id",
    "workflow_dispatch_allowed",
}
EXPECTED_FALSE_FIELDS = (
    "artifact_publication_allowed",
    "company_formation_claimed",
    "customer_access_allowed",
    "deployment_allowed",
    "dns_mutation_allowed",
    "dns_propagation_claimed",
    "dns_provider_account_recorded",
    "dns_record_name_recorded",
    "dns_record_type_value_recorded",
    "dns_record_value_recorded",
    "dns_resolution_claimed",
    "dns_rollback_claimed",
    "dns_zone_value_recorded",
    "endpoint_reachability_claimed",
    "external_publication_allowed",
    "legal_clearance_claimed",
    "money_movement_allowed",
    "operator_approval_claimed",
    "patent_claimed",
    "personal_data_collection_allowed",
    "readiness_claimed",
    "repository_variable_bound",
    "ttl_value_recorded",
    "workflow_dispatch_allowed",
)
EXPECTED_SURFACE_KEYS = {
    "evidence_ref",
    "public_safe_note",
    "state",
    "surface_id",
    "surface_type",
}
REQUIRED_DOC_PHRASES = (
    "Foundation Gateway DNS Publication Rehearsal Boundary",
    "Witness packet: [`../examples/foundation_gateway_dns_publication_rehearsal_witness.awaiting_evidence.json`]",
    "Rule: Gateway DNS publication rehearsal is a local stop-rule map for a later",
    "No DNS provider account value, DNS zone value, DNS record name value, DNS",
    "gateway_dns_publication_rehearsal_state=AwaitingEvidence",
    "dns_provider_account_recorded=false",
    "dns_zone_value_recorded=false",
    "dns_record_name_recorded=false",
    "dns_record_type_value_recorded=false",
    "dns_record_value_recorded=false",
    "ttl_value_recorded=false",
    "dns_mutation_allowed=false",
    "repository_variable_bound=false",
    "workflow_dispatch_allowed=false",
    "dns_propagation_claimed=false",
    "dns_rollback_claimed=false",
    "dns_resolution_claimed=false",
    "endpoint_reachability_claimed=false",
    "artifact_publication_allowed=false",
    "operator_approval_claimed=false",
    "readiness_claimed=false",
    "customer_access_allowed=false",
    "personal_data_collection_allowed=false",
    "money_movement_allowed=false",
    "legal_clearance_claimed=false",
    "company_formation_claimed=false",
    "patent_claimed=false",
    "external_publication_allowed=false",
    "deployment_allowed=false",
    "MULLU_GATEWAY_DNS_TARGET",
    "MULLU_GATEWAY_URL",
    "MULLU_EXPECTED_RUNTIME_ENV",
    "python scripts/validate_foundation_gateway_dns_publication_rehearsal_boundary.py",
)
FORBIDDEN_VALUE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("url_value", re.compile(r"https?://", re.IGNORECASE)),
    ("email_value", re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)),
    ("private_path", re.compile(r"\b[A-Za-z]:[\\/]|\\\\", re.IGNORECASE)),
    ("private_key_block", re.compile(r"-----BEGIN\s+(?:RSA\s+|EC\s+|OPENSSH\s+)?PRIVATE\s+KEY-----", re.IGNORECASE)),
    ("ip_value", re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")),
    (
        "host_value",
        re.compile(
            r"\b(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+(?:com|net|org|io|dev|app|cloud|site)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "live_assignment",
        re.compile(
            r"\b(?:secret|token|api[_ -]?key|client[_ -]?secret|password|"
            r"credential|gateway|url|dns|target|host|provider|account|zone|"
            r"record|ttl|repository[_ -]?variable|variable|workflow|run|"
            r"artifact|deployment|environment|env|customer|person|"
            r"participant|email|payment|billing|invoice|legal|company|"
            r"formation|patent|approval|receipt|evidence|report|operator|"
            r"ledger)[_ -]?(?:id|name|value|url|target|host|ref|status|text|"
            r"path|list|number|record|type|ttl)?\s*=",
            re.IGNORECASE,
        ),
    ),
)
FORBIDDEN_PROMOTION_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("dns_mutated", re.compile(r"\bdns\s+(?:is\s+)?(?:mutated|changed|updated)\b", re.IGNORECASE)),
    ("record_published", re.compile(r"\bdns record\s+(?:is\s+)?(?:published|ready|verified)\b", re.IGNORECASE)),
    ("propagation_proved", re.compile(r"\bpropagation\s+(?:is\s+)?(?:proved|verified|ready|complete)\b", re.IGNORECASE)),
    ("rollback_proved", re.compile(r"\brollback\s+(?:is\s+)?(?:proved|verified|ready|complete)\b", re.IGNORECASE)),
    ("dns_resolved", re.compile(r"\bdns resolution\s+(?:is\s+)?(?:proved|verified|ready|complete)\b", re.IGNORECASE)),
    ("endpoint_reachable", re.compile(r"\bendpoint\s+(?:is\s+)?(?:reachable|verified|ready)\b", re.IGNORECASE)),
    ("workflow_dispatched", re.compile(r"\bworkflow\s+(?:is\s+)?(?:dispatched|ready|verified|complete)\b", re.IGNORECASE)),
    ("artifact_published", re.compile(r"\bartifact\s+(?:is\s+)?(?:published|ready|verified)\b", re.IGNORECASE)),
    ("operator_approved", re.compile(r"\boperator approval\s+(?:is\s+)?(?:claimed|ready|verified|complete)\b", re.IGNORECASE)),
    ("readiness_proven", re.compile(r"\breadiness\s+(?:is\s+)?proven\b", re.IGNORECASE)),
    ("deployment_ready", re.compile(r"\bdeployment\s+(?:is\s+)?ready\b", re.IGNORECASE)),
    ("customer_access_ready", re.compile(r"\bcustomer access\s+(?:is\s+)?ready\b", re.IGNORECASE)),
    ("legal_cleared", re.compile(r"\blegal\s+(?:is\s+)?cleared\b", re.IGNORECASE)),
    ("company_formed", re.compile(r"\bcompany\s+(?:is\s+)?formed\b", re.IGNORECASE)),
    ("patent_filed", re.compile(r"\bpatent\s+(?:is\s+)?filed\b", re.IGNORECASE)),
    ("money_movement_allowed", re.compile(r"\bmoney movement\s+(?:is\s+)?allowed\b", re.IGNORECASE)),
    ("external_publication_approved", re.compile(r"\bexternal publication (?:allowed|approved|ready)\b", re.IGNORECASE)),
)


@dataclass(frozen=True, slots=True)
class GatewayDnsPublicationRehearsalFinding:
    """One deterministic gateway DNS publication rehearsal validation finding."""

    rule_id: str
    message: str


def load_text(path: Path, label: str) -> str:
    """Read one UTF-8 text artifact with explicit path errors."""

    if not path.exists():
        raise FileNotFoundError(f"missing {label}: {path}")
    if not path.is_file():
        raise IsADirectoryError(f"{label} path is not a file: {path}")
    return path.read_text(encoding="utf-8")


def load_json_object(path: Path, label: str) -> dict[str, Any]:
    """Read one JSON object artifact with explicit shape errors."""

    payload = json.loads(load_text(path, label))
    if not isinstance(payload, dict):
        raise ValueError(f"{label} must be a JSON object")
    return payload


def _flatten_strings(value: Any) -> tuple[str, ...]:
    """Return all string leaves from a JSON-like structure."""

    if isinstance(value, str):
        return (value,)
    if isinstance(value, dict):
        strings: list[str] = []
        for key, nested in value.items():
            strings.extend(_flatten_strings(key))
            strings.extend(_flatten_strings(nested))
        return tuple(strings)
    if isinstance(value, list):
        strings = []
        for nested in value:
            strings.extend(_flatten_strings(nested))
        return tuple(strings)
    return ()


def _find_forbidden_text(text: str, prefix: str) -> list[GatewayDnsPublicationRehearsalFinding]:
    """Return findings for live values or promotion phrases in one text blob."""

    findings: list[GatewayDnsPublicationRehearsalFinding] = []
    for pattern_id, pattern in FORBIDDEN_VALUE_PATTERNS:
        if pattern.search(text):
            findings.append(
                GatewayDnsPublicationRehearsalFinding(
                    f"{prefix}_forbidden_value_pattern",
                    f"forbidden value pattern detected: {pattern_id}",
                )
            )
    for pattern_id, pattern in FORBIDDEN_PROMOTION_PATTERNS:
        if pattern.search(text):
            findings.append(
                GatewayDnsPublicationRehearsalFinding(
                    f"{prefix}_forbidden_promotion_phrase",
                    f"forbidden promotion phrase detected: {pattern_id}",
                )
            )
    return findings


def validate_doc_text(doc_text: str) -> list[GatewayDnsPublicationRehearsalFinding]:
    """Validate the DNS publication rehearsal boundary document text."""

    findings: list[GatewayDnsPublicationRehearsalFinding] = []
    for phrase in REQUIRED_DOC_PHRASES:
        if phrase not in doc_text:
            findings.append(
                GatewayDnsPublicationRehearsalFinding(
                    "foundation_gateway_dns_publication_rehearsal_doc_phrase_missing",
                    f"missing required document phrase: {phrase}",
                )
            )
    for question_label in EXPECTED_QUESTION_LABELS:
        if question_label not in doc_text:
            findings.append(
                GatewayDnsPublicationRehearsalFinding(
                    "foundation_gateway_dns_publication_rehearsal_doc_question_missing",
                    f"missing document question label: {question_label}",
                )
            )
    for surface_label in EXPECTED_DOC_SURFACE_LABELS:
        if surface_label not in doc_text:
            findings.append(
                GatewayDnsPublicationRehearsalFinding(
                    "foundation_gateway_dns_publication_rehearsal_doc_surface_missing",
                    f"missing document surface label: {surface_label}",
                )
            )
    findings.extend(_find_forbidden_text(doc_text, "gateway_dns_publication_rehearsal"))
    return findings


def validate_packet(payload: dict[str, Any]) -> list[GatewayDnsPublicationRehearsalFinding]:
    """Validate the DNS publication rehearsal witness packet."""

    findings: list[GatewayDnsPublicationRehearsalFinding] = []
    observed_root_keys = set(payload)
    if observed_root_keys != EXPECTED_ROOT_KEYS:
        findings.append(
            GatewayDnsPublicationRehearsalFinding(
                "gateway_dns_publication_rehearsal_root_keys_invalid",
                "witness root keys must match the DNS publication rehearsal contract",
            )
        )
    if payload.get("witness_id") != EXPECTED_WITNESS_ID:
        findings.append(
            GatewayDnsPublicationRehearsalFinding(
                "gateway_dns_publication_rehearsal_identity_invalid",
                "witness_id must identify the DNS publication rehearsal witness",
            )
        )
    if payload.get("schema_version") != 1:
        findings.append(
            GatewayDnsPublicationRehearsalFinding(
                "gateway_dns_publication_rehearsal_schema_invalid",
                "schema_version must be 1",
            )
        )
    if payload.get("status") != "AwaitingEvidence" or payload.get("solver_outcome") != "AwaitingEvidence":
        findings.append(
            GatewayDnsPublicationRehearsalFinding(
                "gateway_dns_publication_rehearsal_status_invalid",
                "status and solver_outcome must remain AwaitingEvidence",
            )
        )
    if tuple(payload.get("blocked_claims", ())) != EXPECTED_BLOCKED_CLAIMS:
        findings.append(
            GatewayDnsPublicationRehearsalFinding(
                "gateway_dns_publication_rehearsal_root_value_invalid",
                "blocked_claims must preserve the DNS publication blocked-claim contract",
            )
        )
    if tuple(payload.get("question_labels", ())) != EXPECTED_QUESTION_LABELS:
        findings.append(
            GatewayDnsPublicationRehearsalFinding(
                "gateway_dns_publication_rehearsal_root_value_invalid",
                "question_labels must preserve the DNS publication gate-label contract",
            )
        )
    if payload.get("next_action") != EXPECTED_NEXT_ACTION:
        findings.append(
            GatewayDnsPublicationRehearsalFinding(
                "gateway_dns_publication_rehearsal_root_value_invalid",
                "next_action must remain the public-safe DNS publication rehearsal instruction",
            )
        )
    for field_name in EXPECTED_FALSE_FIELDS:
        if payload.get(field_name) is not False:
            findings.append(
                GatewayDnsPublicationRehearsalFinding(
                    "gateway_dns_publication_rehearsal_root_value_invalid",
                    f"{field_name} must be false",
                )
            )

    surfaces = payload.get("surfaces")
    if not isinstance(surfaces, list):
        findings.append(
            GatewayDnsPublicationRehearsalFinding(
                "gateway_dns_publication_rehearsal_surface_inventory_invalid",
                "surfaces must be a list",
            )
        )
        return findings

    observed_surfaces: list[tuple[str, str, str]] = []
    for surface in surfaces:
        if not isinstance(surface, dict):
            findings.append(
                GatewayDnsPublicationRehearsalFinding(
                    "gateway_dns_publication_rehearsal_surface_inventory_invalid",
                    "surface entries must be objects",
                )
            )
            continue
        if set(surface) != EXPECTED_SURFACE_KEYS:
            findings.append(
                GatewayDnsPublicationRehearsalFinding(
                    "gateway_dns_publication_rehearsal_surface_keys_invalid",
                    "surface keys must match the DNS publication rehearsal contract",
                )
            )
        surface_id = surface.get("surface_id")
        surface_type = surface.get("surface_type")
        surface_state = surface.get("state")
        if isinstance(surface_id, str) and isinstance(surface_type, str) and isinstance(surface_state, str):
            observed_surfaces.append((surface_id, surface_type, surface_state))
        if surface_state != "AwaitingEvidence":
            findings.append(
                GatewayDnsPublicationRehearsalFinding(
                    "gateway_dns_publication_rehearsal_surface_state_invalid",
                    f"surface must remain AwaitingEvidence: {surface_id}",
                )
            )
        if surface.get("evidence_ref") != "manual_preparation_pending":
            findings.append(
                GatewayDnsPublicationRehearsalFinding(
                    "gateway_dns_publication_rehearsal_surface_evidence_invalid",
                    f"surface evidence_ref must remain manual_preparation_pending: {surface_id}",
                )
            )
        if surface.get("public_safe_note") != EXPECTED_SURFACE_NOTES.get(str(surface_id)):
            findings.append(
                GatewayDnsPublicationRehearsalFinding(
                    "gateway_dns_publication_rehearsal_surface_note_invalid",
                    f"surface note drifted: {surface_id}",
                )
            )
    if tuple(observed_surfaces) != EXPECTED_SURFACES:
        findings.append(
            GatewayDnsPublicationRehearsalFinding(
                "gateway_dns_publication_rehearsal_surface_inventory_invalid",
                "surface inventory must preserve the DNS publication rehearsal order",
            )
        )

    joined_strings = "\n".join(_flatten_strings(payload))
    findings.extend(_find_forbidden_text(joined_strings, "gateway_dns_publication_rehearsal"))
    return findings


def validate_foundation_gateway_dns_publication_rehearsal_boundary(
    *,
    doc_path: Path = DEFAULT_DOC_PATH,
    packet_path: Path = DEFAULT_PACKET_PATH,
) -> list[GatewayDnsPublicationRehearsalFinding]:
    """Validate both DNS publication rehearsal artifacts."""

    findings = validate_doc_text(load_text(doc_path, "gateway DNS publication rehearsal doc"))
    findings.extend(validate_packet(load_json_object(packet_path, "gateway DNS publication rehearsal witness")))
    return findings


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--doc", type=Path, default=DEFAULT_DOC_PATH)
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET_PATH)
    return parser.parse_args()


def main() -> int:
    """Run validation and emit deterministic status lines."""

    args = parse_args()
    try:
        findings = validate_foundation_gateway_dns_publication_rehearsal_boundary(
            doc_path=args.doc,
            packet_path=args.packet,
        )
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        sys.stderr.write(f"[FAIL] foundation_gateway_dns_publication_rehearsal_io: {exc}\n")
        sys.stderr.write("STATUS: failed\n")
        return 1
    if findings:
        for finding in findings:
            sys.stderr.write(f"[FAIL] {finding.rule_id}: {finding.message}\n")
        sys.stderr.write("STATUS: failed\n")
        return 1
    sys.stdout.write("[PASS] foundation_gateway_dns_publication_rehearsal_doc\n")
    sys.stdout.write("[PASS] foundation_gateway_dns_publication_rehearsal_witness\n")
    sys.stdout.write("STATUS: passed\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
