#!/usr/bin/env python3
"""Validate the Foundation Mode gateway DNS resolution receipt rehearsal boundary.

Purpose: keep issue #330 gateway DNS resolution receipt preparation local and
public-safe while live DNS queries, host values, gateway URLs, resolved
addresses, resolver-error proof, DNS proof, receipt writing, endpoint proof,
repository-variable binding, secret-presence claims, workflow dispatch,
artifact publication, operator approval, readiness claims, customer access,
personal data, money movement, legal/business claims, publication, and
deployment remain blocked.
Governance scope: Foundation Mode, issue #330 DNS resolution receipt rehearsal,
public-safe question labels, live DNS probe blocking, value exclusion,
receipt-writing blocking, approval blocking, money blocking, legal/business
restraint, publication blocking, and deployment blocking.
Dependencies: docs/FOUNDATION_GATEWAY_DNS_RESOLUTION_RECEIPT_REHEARSAL_BOUNDARY.md
and examples/foundation_gateway_dns_resolution_receipt_rehearsal_witness.awaiting_evidence.json.
Invariants:
  - Validation is read-only.
  - The witness records public-safe DNS resolution receipt question labels only.
  - No live DNS query, host value, gateway URL value, resolved address,
    resolver-error proof, DNS resolution proof, DNS receipt writing, endpoint
    reachability proof, repository-variable binding, secret presence claim,
    workflow dispatch, artifact publication, operator approval, readiness
    claim, customer access, personal data, money movement, legal clearance,
    company formation, patent claim, external publication, or deployment claim
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
DEFAULT_DOC_PATH = REPO_ROOT / "docs" / "FOUNDATION_GATEWAY_DNS_RESOLUTION_RECEIPT_REHEARSAL_BOUNDARY.md"
DEFAULT_PACKET_PATH = (
    REPO_ROOT / "examples" / "foundation_gateway_dns_resolution_receipt_rehearsal_witness.awaiting_evidence.json"
)

EXPECTED_WITNESS_ID = "foundation_gateway_dns_resolution_receipt_rehearsal_witness.awaiting_evidence.v1"
EXPECTED_QUESTION_LABELS = (
    "dns_query_scope_question",
    "resolver_context_question",
    "resolved_address_set_question",
    "resolver_error_state_question",
    "ttl_observation_question",
    "receipt_timestamp_question",
    "target_binding_dependency_question",
    "endpoint_preflight_dependency_question",
    "publication_stop_rule_question",
    "operator_reassessment_gate",
)
EXPECTED_BLOCKED_CLAIMS = (
    "live dns query",
    "host value",
    "gateway url value",
    "resolved address",
    "resolver error proof",
    "dns resolution proof",
    "dns receipt writing",
    "endpoint reachability proof",
    "repository variable binding",
    "secret presence claim",
    "workflow dispatch",
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
    "record public-safe DNS resolution receipt question labels only; do not run "
    "live DNS queries, record host values, record gateway URL values, record "
    "resolved addresses, claim resolver error proof, claim DNS resolution proof, "
    "write DNS receipts, claim endpoint reachability proof, bind repository "
    "variables, claim secret presence, dispatch workflows, publish artifacts, "
    "claim operator approval, claim readiness, open customer access, collect "
    "personal data, move money, claim legal clearance, form a company, claim "
    "patent protection, publish externally, or deploy"
)
EXPECTED_SURFACES = (
    ("dns_query_scope_question", "local_question_label", "AwaitingEvidence"),
    ("resolver_context_question", "local_question_label", "AwaitingEvidence"),
    ("resolved_address_set_question", "blocked_external_route", "AwaitingEvidence"),
    ("resolver_error_state_question", "blocked_external_route", "AwaitingEvidence"),
    ("ttl_observation_question", "local_question_label", "AwaitingEvidence"),
    ("receipt_timestamp_question", "local_question_label", "AwaitingEvidence"),
    ("target_binding_dependency_question", "blocked_external_route", "AwaitingEvidence"),
    ("endpoint_preflight_dependency_question", "blocked_external_route", "AwaitingEvidence"),
    ("publication_stop_rule_question", "local_question_label", "AwaitingEvidence"),
    ("operator_reassessment_gate", "local_question_label", "AwaitingEvidence"),
)
EXPECTED_SURFACE_NOTES = {
    "dns_query_scope_question": "DNS query scope question only; live DNS query is not run.",
    "resolver_context_question": "Resolver context question only; resolver output is not recorded.",
    "resolved_address_set_question": "Resolved address set question only; resolved addresses are not recorded.",
    "resolver_error_state_question": "Resolver error state question only; resolver error proof is not claimed.",
    "ttl_observation_question": "TTL observation question only; TTL values are not recorded.",
    "receipt_timestamp_question": "Receipt timestamp question only; timestamps are not recorded.",
    "target_binding_dependency_question": "Target binding dependency question only; target binding is not promoted.",
    "endpoint_preflight_dependency_question": (
        "Endpoint preflight dependency question only; endpoint proof is not claimed."
    ),
    "publication_stop_rule_question": (
        "Publication stop rule question only; DNS receipts and artifacts are not published."
    ),
    "operator_reassessment_gate": "Operator reassessment gate only; DNS proof and deployment are not approved.",
}
EXPECTED_DOC_SURFACE_LABELS = (
    "DNS query scope question",
    "Resolver context question",
    "Resolved address set question",
    "Resolver error state question",
    "TTL observation question",
    "Receipt timestamp question",
    "Target binding dependency question",
    "Endpoint preflight dependency question",
    "Publication stop rule question",
    "Operator reassessment gate",
)
EXPECTED_ROOT_KEYS = {
    "artifact_publication_allowed",
    "blocked_claims",
    "company_formation_claimed",
    "customer_access_allowed",
    "deployment_allowed",
    "dns_receipt_written",
    "dns_resolution_claimed",
    "endpoint_reachability_claimed",
    "external_publication_allowed",
    "gateway_url_recorded",
    "host_value_recorded",
    "legal_clearance_claimed",
    "live_dns_query_allowed",
    "money_movement_allowed",
    "next_action",
    "operator_approval_claimed",
    "patent_claimed",
    "personal_data_collection_allowed",
    "question_labels",
    "readiness_claimed",
    "repository_variable_bound",
    "resolved_address_recorded",
    "resolver_error_proof_claimed",
    "schema_version",
    "secret_presence_claimed",
    "solver_outcome",
    "status",
    "surfaces",
    "witness_id",
    "workflow_dispatch_allowed",
}
EXPECTED_SURFACE_KEYS = {
    "evidence_ref",
    "public_safe_note",
    "state",
    "surface_id",
    "surface_type",
}
REQUIRED_DOC_PHRASES = (
    "Foundation Gateway DNS Resolution Receipt Rehearsal Boundary",
    "Witness packet: [`../examples/foundation_gateway_dns_resolution_receipt_rehearsal_witness.awaiting_evidence.json`]",
    "Rule: Gateway DNS resolution receipt rehearsal is a local question map for a",
    "No live DNS query, host value, gateway URL value, resolved address",
    "gateway_dns_resolution_receipt_rehearsal_state=AwaitingEvidence",
    "live_dns_query_allowed=false",
    "host_value_recorded=false",
    "gateway_url_recorded=false",
    "resolved_address_recorded=false",
    "resolver_error_proof_claimed=false",
    "dns_resolution_claimed=false",
    "dns_receipt_written=false",
    "endpoint_reachability_claimed=false",
    "repository_variable_bound=false",
    "secret_presence_claimed=false",
    "workflow_dispatch_allowed=false",
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
    "python scripts/validate_foundation_gateway_dns_resolution_receipt_rehearsal_boundary.py",
)
FORBIDDEN_VALUE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("url_value", re.compile(r"https?://", re.IGNORECASE)),
    ("email_value", re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)),
    ("private_path", re.compile(r"\b[A-Za-z]:[\\/]|\\\\", re.IGNORECASE)),
    ("private_key_block", re.compile(r"-----BEGIN\s+(?:RSA\s+|EC\s+|OPENSSH\s+)?PRIVATE\s+KEY-----", re.IGNORECASE)),
    (
        "host_value",
        re.compile(
            r"\b(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+(?:com|net|org|io|dev|app|cloud|site)\b",
            re.IGNORECASE,
        ),
    ),
    ("ip_value", re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")),
    ("timestamp_value", re.compile(r"\b20\d{2}-\d{2}-\d{2}T\d{2}:\d{2}", re.IGNORECASE)),
    (
        "live_assignment",
        re.compile(
            r"\b(?:secret|token|api[_ -]?key|client[_ -]?secret|password|"
            r"credential|gateway|url|dns|target|host|provider|account|resolver|"
            r"address|ttl|timestamp|repository[_ -]?variable|variable|workflow|"
            r"run|artifact|deployment|environment|env|customer|person|participant|"
            r"email|payment|billing|invoice|legal|company|formation|patent|"
            r"approval|receipt|evidence|report|operator|ledger)"
            r"[_ -]?(?:id|name|value|url|target|host|ref|status|text|path|"
            r"list|number|record|address|count|error|time)?\s*=",
            re.IGNORECASE,
        ),
    ),
)
FORBIDDEN_PROMOTION_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("live_dns_query_run", re.compile(r"\blive dns quer(?:y|ies)\s+(?:is\s+|are\s+)?(?:run|complete|verified)\b", re.IGNORECASE)),
    ("host_value_recorded", re.compile(r"\bhost value\s+(?:is\s+)?(?:recorded|ready|verified)\b", re.IGNORECASE)),
    ("gateway_url_recorded", re.compile(r"\bgateway url\s+(?:is\s+)?(?:recorded|ready|verified|available)\b", re.IGNORECASE)),
    ("address_recorded", re.compile(r"\bresolved address(?:es)?\s+(?:is\s+|are\s+)?(?:recorded|ready|verified)\b", re.IGNORECASE)),
    ("resolver_error_proved", re.compile(r"\bresolver error proof\s+(?:is\s+)?(?:claimed|ready|verified|complete)\b", re.IGNORECASE)),
    ("dns_resolved", re.compile(r"\bdns resolution\s+(?:is\s+)?(?:proved|verified|ready|complete)\b", re.IGNORECASE)),
    ("dns_receipt_written", re.compile(r"\bdns receipt\s+(?:is\s+)?(?:written|ready|verified|complete)\b", re.IGNORECASE)),
    ("endpoint_reachable", re.compile(r"\bendpoint\s+(?:is\s+)?(?:reachable|verified|ready)\b", re.IGNORECASE)),
    ("repository_variable_bound", re.compile(r"\brepository variable\s+(?:is\s+)?bound\b", re.IGNORECASE)),
    ("secret_presence_ready", re.compile(r"\bsecret presence\s+(?:is\s+)?(?:claimed|verified|ready)\b", re.IGNORECASE)),
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
class GatewayDnsResolutionReceiptRehearsalFinding:
    """One deterministic gateway DNS resolution receipt rehearsal validation finding."""

    rule_id: str
    message: str


def load_text(path: Path, label: str) -> str:
    """Read one UTF-8 text artifact with explicit path errors."""

    if not path.exists():
        raise FileNotFoundError(f"{label} missing: {path}")
    if not path.is_file():
        raise IsADirectoryError(f"{label} is not a file: {path}")
    return path.read_text(encoding="utf-8")


def load_json_object(path: Path, label: str) -> dict[str, Any]:
    """Read one JSON object artifact with explicit shape errors."""

    text = load_text(path, label)
    payload = json.loads(text)
    if not isinstance(payload, dict):
        raise ValueError(f"{label} must be a JSON object")
    return payload


def iter_string_values(value: Any) -> list[str]:
    """Return all string leaves from a JSON-compatible value."""

    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        strings: list[str] = []
        for item in value:
            strings.extend(iter_string_values(item))
        return strings
    if isinstance(value, dict):
        strings = []
        for item in value.values():
            strings.extend(iter_string_values(item))
        return strings
    return []


def validate_forbidden_values(
    strings: list[str],
    artifact_label: str,
) -> list[GatewayDnsResolutionReceiptRehearsalFinding]:
    """Return findings when public artifacts contain live values or assignments."""

    findings: list[GatewayDnsResolutionReceiptRehearsalFinding] = []
    for value in strings:
        for rule_id, pattern in FORBIDDEN_VALUE_PATTERNS:
            if pattern.search(value):
                findings.append(
                    GatewayDnsResolutionReceiptRehearsalFinding(
                        "gateway_dns_resolution_receipt_rehearsal_forbidden_value_pattern",
                        f"gateway DNS resolution receipt rehearsal {artifact_label} contains forbidden value pattern: {rule_id}",
                    )
                )
    return findings


def validate_forbidden_promotions(
    strings: list[str],
    artifact_label: str,
) -> list[GatewayDnsResolutionReceiptRehearsalFinding]:
    """Return findings when public artifacts promote blocked DNS or deployment state."""

    findings: list[GatewayDnsResolutionReceiptRehearsalFinding] = []
    for value in strings:
        for rule_id, pattern in FORBIDDEN_PROMOTION_PATTERNS:
            if pattern.search(value):
                findings.append(
                    GatewayDnsResolutionReceiptRehearsalFinding(
                        "gateway_dns_resolution_receipt_rehearsal_forbidden_promotion_phrase",
                        f"gateway DNS resolution receipt rehearsal {artifact_label} contains forbidden promotion pattern: {rule_id}",
                    )
                )
    return findings


def validate_doc_text(text: str) -> list[GatewayDnsResolutionReceiptRehearsalFinding]:
    """Return findings for gateway DNS resolution receipt rehearsal documentation drift."""

    findings: list[GatewayDnsResolutionReceiptRehearsalFinding] = []
    for phrase in REQUIRED_DOC_PHRASES:
        if phrase not in text:
            findings.append(
                GatewayDnsResolutionReceiptRehearsalFinding(
                    "foundation_gateway_dns_resolution_receipt_rehearsal_doc_phrase_missing",
                    f"gateway DNS resolution receipt rehearsal doc missing required phrase: {phrase}",
                )
            )
    for label in EXPECTED_QUESTION_LABELS:
        if label not in text:
            findings.append(
                GatewayDnsResolutionReceiptRehearsalFinding(
                    "foundation_gateway_dns_resolution_receipt_rehearsal_doc_label_missing",
                    f"gateway DNS resolution receipt rehearsal doc missing question label: {label}",
                )
            )
    for label in EXPECTED_DOC_SURFACE_LABELS:
        if label not in text:
            findings.append(
                GatewayDnsResolutionReceiptRehearsalFinding(
                    "foundation_gateway_dns_resolution_receipt_rehearsal_doc_surface_missing",
                    f"gateway DNS resolution receipt rehearsal doc missing surface label: {label}",
                )
            )
    findings.extend(validate_forbidden_values([text], "doc"))
    findings.extend(validate_forbidden_promotions([text], "doc"))
    return findings


def validate_packet(payload: dict[str, Any]) -> list[GatewayDnsResolutionReceiptRehearsalFinding]:
    """Return findings for gateway DNS resolution receipt rehearsal witness drift."""

    findings: list[GatewayDnsResolutionReceiptRehearsalFinding] = []
    if set(payload) != EXPECTED_ROOT_KEYS:
        findings.append(
            GatewayDnsResolutionReceiptRehearsalFinding(
                "gateway_dns_resolution_receipt_rehearsal_root_keys_invalid",
                "gateway DNS resolution receipt rehearsal witness root keys drifted",
            )
        )
    expected_values: dict[str, Any] = {
        "schema_version": 1,
        "witness_id": EXPECTED_WITNESS_ID,
        "status": "AwaitingEvidence",
        "solver_outcome": "AwaitingEvidence",
        "blocked_claims": list(EXPECTED_BLOCKED_CLAIMS),
        "question_labels": list(EXPECTED_QUESTION_LABELS),
        "next_action": EXPECTED_NEXT_ACTION,
        "live_dns_query_allowed": False,
        "host_value_recorded": False,
        "gateway_url_recorded": False,
        "resolved_address_recorded": False,
        "resolver_error_proof_claimed": False,
        "dns_resolution_claimed": False,
        "dns_receipt_written": False,
        "endpoint_reachability_claimed": False,
        "repository_variable_bound": False,
        "secret_presence_claimed": False,
        "workflow_dispatch_allowed": False,
        "artifact_publication_allowed": False,
        "operator_approval_claimed": False,
        "readiness_claimed": False,
        "customer_access_allowed": False,
        "personal_data_collection_allowed": False,
        "money_movement_allowed": False,
        "legal_clearance_claimed": False,
        "company_formation_claimed": False,
        "patent_claimed": False,
        "external_publication_allowed": False,
        "deployment_allowed": False,
    }
    for key, expected in expected_values.items():
        if payload.get(key) != expected:
            findings.append(
                GatewayDnsResolutionReceiptRehearsalFinding(
                    "gateway_dns_resolution_receipt_rehearsal_root_value_invalid",
                    f"{key} must remain {expected!r}",
                )
            )
    findings.extend(validate_surfaces(payload.get("surfaces")))
    findings.extend(validate_forbidden_values(iter_string_values(payload), "witness"))
    findings.extend(validate_forbidden_promotions(iter_string_values(payload), "witness"))
    return findings


def validate_surfaces(surfaces: object) -> list[GatewayDnsResolutionReceiptRehearsalFinding]:
    """Return findings for rehearsal surface inventory drift."""

    findings: list[GatewayDnsResolutionReceiptRehearsalFinding] = []
    if not isinstance(surfaces, list) or not all(isinstance(surface, dict) for surface in surfaces):
        return [
            GatewayDnsResolutionReceiptRehearsalFinding(
                "gateway_dns_resolution_receipt_rehearsal_surfaces_invalid",
                "gateway DNS resolution receipt rehearsal surfaces must be a list of objects",
            )
        ]
    observed = tuple(
        (surface.get("surface_id"), surface.get("surface_type"), surface.get("state"))
        for surface in surfaces
    )
    if observed != EXPECTED_SURFACES:
        findings.append(
            GatewayDnsResolutionReceiptRehearsalFinding(
                "gateway_dns_resolution_receipt_rehearsal_surface_inventory_invalid",
                "gateway DNS resolution receipt rehearsal surface inventory does not match the Foundation Mode set",
            )
        )
    seen_surface_ids: set[object] = set()
    for surface in surfaces:
        surface_id = surface.get("surface_id")
        if set(surface) != EXPECTED_SURFACE_KEYS:
            findings.append(
                GatewayDnsResolutionReceiptRehearsalFinding(
                    "gateway_dns_resolution_receipt_rehearsal_surface_keys_invalid",
                    f"{surface_id} surface keys drifted",
                )
            )
        if surface_id in seen_surface_ids:
            findings.append(
                GatewayDnsResolutionReceiptRehearsalFinding(
                    "gateway_dns_resolution_receipt_rehearsal_surface_duplicate",
                    "surface ids must be unique",
                )
            )
        seen_surface_ids.add(surface_id)
        if surface.get("state") != "AwaitingEvidence":
            findings.append(
                GatewayDnsResolutionReceiptRehearsalFinding(
                    "gateway_dns_resolution_receipt_rehearsal_surface_state_invalid",
                    f"{surface_id} state must be AwaitingEvidence",
                )
            )
        if surface.get("evidence_ref") != "manual_preparation_pending":
            findings.append(
                GatewayDnsResolutionReceiptRehearsalFinding(
                    "gateway_dns_resolution_receipt_rehearsal_surface_evidence_invalid",
                    f"{surface_id} evidence_ref must remain manual_preparation_pending",
                )
            )
        expected_note = EXPECTED_SURFACE_NOTES.get(str(surface_id))
        if surface.get("public_safe_note") != expected_note:
            findings.append(
                GatewayDnsResolutionReceiptRehearsalFinding(
                    "gateway_dns_resolution_receipt_rehearsal_surface_note_invalid",
                    f"{surface_id} public_safe_note drifted",
                )
            )
    return findings


def validate_foundation_gateway_dns_resolution_receipt_rehearsal_boundary(
    doc_path: Path = DEFAULT_DOC_PATH,
    packet_path: Path = DEFAULT_PACKET_PATH,
) -> list[GatewayDnsResolutionReceiptRehearsalFinding]:
    """Validate the Foundation Mode gateway DNS resolution receipt rehearsal artifacts."""

    doc_text = load_text(doc_path, "gateway DNS resolution receipt rehearsal boundary doc")
    packet_payload = load_json_object(packet_path, "gateway DNS resolution receipt rehearsal witness packet")
    findings: list[GatewayDnsResolutionReceiptRehearsalFinding] = []
    findings.extend(validate_doc_text(doc_text))
    findings.extend(validate_packet(packet_payload))
    return findings


def main() -> int:
    """Validate gateway DNS resolution receipt rehearsal artifacts and print deterministic status."""

    parser = argparse.ArgumentParser(
        description="Validate Foundation Mode gateway DNS resolution receipt rehearsal boundary artifacts."
    )
    parser.add_argument("--doc", type=Path, default=DEFAULT_DOC_PATH)
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET_PATH)
    args = parser.parse_args()
    try:
        findings = validate_foundation_gateway_dns_resolution_receipt_rehearsal_boundary(args.doc, args.packet)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"[FAIL] foundation_gateway_dns_resolution_receipt_rehearsal_load: {exc}", file=sys.stderr)
        return 2
    if findings:
        for finding in findings:
            print(f"[FAIL] {finding.rule_id}: {finding.message}", file=sys.stderr)
        print("STATUS: failed", file=sys.stderr)
        return 1
    print("[PASS] foundation_gateway_dns_resolution_receipt_rehearsal_doc")
    print("[PASS] foundation_gateway_dns_resolution_receipt_rehearsal_witness")
    print("STATUS: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
