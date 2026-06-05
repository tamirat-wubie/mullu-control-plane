#!/usr/bin/env python3
"""Validate the Foundation Mode gateway endpoint evidence receipt rehearsal boundary.

Purpose: keep issue #330 endpoint evidence receipt-shape preparation local and
public-safe while endpoint probes, gateway and endpoint URLs, response evidence,
timestamps, collector identities, evidence-ledger append, deployment witness
collection, public-health declarations, workflow dispatch, artifact
publication, approval, readiness, customer access, money movement,
legal/business claims, publication, and deployment remain blocked.
Governance scope: Foundation Mode, issue #330 endpoint evidence receipt
rehearsal, public-safe receipt field labels, endpoint probe blocking, value
exclusion, evidence-ledger append blocking, approval blocking, publication
blocking, and deployment restraint.
Dependencies:
docs/FOUNDATION_GATEWAY_ENDPOINT_EVIDENCE_RECEIPT_REHEARSAL_BOUNDARY.md and
examples/foundation_gateway_endpoint_evidence_receipt_rehearsal_witness.awaiting_evidence.json.
Invariants:
  - Validation is read-only.
  - The witness records public-safe endpoint evidence receipt field labels only.
  - No endpoint probe, gateway URL value, endpoint URL value, HTTP status
    value, response digest, response body, timestamp, collector identity,
    runtime witness payload, conformance payload, production/capability/audit/
    proof payload, evidence-ledger append, deployment witness collection,
    public health declaration, secret presence claim, workflow dispatch,
    artifact publication, operator approval, readiness claim, customer access,
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
DEFAULT_DOC_PATH = REPO_ROOT / "docs" / "FOUNDATION_GATEWAY_ENDPOINT_EVIDENCE_RECEIPT_REHEARSAL_BOUNDARY.md"
DEFAULT_PACKET_PATH = (
    REPO_ROOT
    / "examples"
    / "foundation_gateway_endpoint_evidence_receipt_rehearsal_witness.awaiting_evidence.json"
)

EXPECTED_WITNESS_ID = "foundation_gateway_endpoint_evidence_receipt_rehearsal_witness.awaiting_evidence.v1"
EXPECTED_FIELD_LABELS = (
    "endpoint_evidence_receipt_id_label",
    "endpoint_evidence_source_boundary_label",
    "health_endpoint_observation_slot",
    "gateway_witness_observation_slot",
    "runtime_conformance_observation_slot",
    "endpoint_http_status_slot",
    "endpoint_response_digest_slot",
    "endpoint_body_schema_slot",
    "endpoint_collection_time_slot",
    "endpoint_collector_identity_slot",
    "endpoint_redaction_note_slot",
    "endpoint_validation_result_slot",
    "endpoint_evidence_ledger_route_slot",
    "operator_reassessment_gate",
)
EXPECTED_BLOCKED_CLAIMS = (
    "endpoint probe",
    "gateway url value",
    "endpoint url value",
    "http status value",
    "response digest value",
    "response body value",
    "collection timestamp value",
    "collector identity value",
    "runtime witness payload",
    "runtime conformance payload",
    "production evidence payload",
    "capability evidence payload",
    "audit verification payload",
    "proof verification payload",
    "evidence ledger append",
    "deployment witness collection",
    "public health declaration",
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
    "record public-safe gateway endpoint evidence receipt field labels only; "
    "do not probe endpoints, record gateway URL values, record endpoint URL "
    "values, record HTTP status values, record response digests, record "
    "response bodies, record collection timestamps, record collector "
    "identities, claim health proof, claim gateway witness proof, claim "
    "runtime conformance proof, append evidence to a ledger, collect "
    "deployment witnesses, declare public health, claim secret presence, "
    "dispatch workflows, publish artifacts, claim operator approval, claim "
    "readiness, open customer access, collect personal data, move money, "
    "claim legal clearance, form a company, claim patent protection, publish "
    "externally, or deploy"
)
EXPECTED_SURFACES = (
    ("endpoint_evidence_receipt_id_label", "receipt_field_label", "AwaitingEvidence"),
    ("endpoint_evidence_source_boundary_label", "receipt_field_label", "AwaitingEvidence"),
    ("health_endpoint_observation_slot", "blocked_external_evidence", "AwaitingEvidence"),
    ("gateway_witness_observation_slot", "blocked_external_evidence", "AwaitingEvidence"),
    ("runtime_conformance_observation_slot", "blocked_external_evidence", "AwaitingEvidence"),
    ("endpoint_http_status_slot", "blocked_external_evidence", "AwaitingEvidence"),
    ("endpoint_response_digest_slot", "blocked_external_evidence", "AwaitingEvidence"),
    ("endpoint_body_schema_slot", "blocked_external_evidence", "AwaitingEvidence"),
    ("endpoint_collection_time_slot", "blocked_external_evidence", "AwaitingEvidence"),
    ("endpoint_collector_identity_slot", "blocked_external_evidence", "AwaitingEvidence"),
    ("endpoint_redaction_note_slot", "receipt_field_label", "AwaitingEvidence"),
    ("endpoint_validation_result_slot", "blocked_external_evidence", "AwaitingEvidence"),
    ("endpoint_evidence_ledger_route_slot", "local_route_label", "AwaitingEvidence"),
    ("operator_reassessment_gate", "local_gate_label", "AwaitingEvidence"),
)
EXPECTED_SURFACE_NOTES = {
    "endpoint_evidence_receipt_id_label": (
        "Endpoint evidence receipt id label only; receipt ids are not assigned."
    ),
    "endpoint_evidence_source_boundary_label": (
        "Endpoint evidence source boundary label only; source proof is not claimed."
    ),
    "health_endpoint_observation_slot": "Health endpoint observation slot only; observations are not recorded.",
    "gateway_witness_observation_slot": (
        "Gateway witness observation slot only; gateway witness payloads are not recorded."
    ),
    "runtime_conformance_observation_slot": (
        "Runtime conformance observation slot only; runtime conformance payloads are not recorded."
    ),
    "endpoint_http_status_slot": "Endpoint HTTP status slot only; HTTP status values are not recorded.",
    "endpoint_response_digest_slot": "Endpoint response digest slot only; response digests are not recorded.",
    "endpoint_body_schema_slot": "Endpoint body schema slot only; response bodies are not recorded.",
    "endpoint_collection_time_slot": "Endpoint collection time slot only; timestamps are not recorded.",
    "endpoint_collector_identity_slot": (
        "Endpoint collector identity slot only; collector identities are not recorded."
    ),
    "endpoint_redaction_note_slot": "Endpoint redaction note slot only; sensitive values are not stored.",
    "endpoint_validation_result_slot": "Endpoint validation result slot only; validation pass is not claimed.",
    "endpoint_evidence_ledger_route_slot": "Endpoint evidence ledger route slot only; evidence is not appended.",
    "operator_reassessment_gate": "Operator reassessment gate only; endpoint proof and deployment are not approved.",
}
EXPECTED_DOC_SURFACE_LABELS = (
    "Endpoint evidence receipt id label",
    "Source boundary label",
    "Health endpoint observation slot",
    "Gateway witness observation slot",
    "Runtime conformance observation slot",
    "Endpoint HTTP status slot",
    "Endpoint response digest slot",
    "Endpoint body schema slot",
    "Endpoint collection time slot",
    "Endpoint collector identity slot",
    "Endpoint redaction note slot",
    "Endpoint validation result slot",
    "Endpoint evidence ledger route slot",
    "Operator reassessment gate",
)
EXPECTED_ROOT_KEYS = {
    "artifact_publication_allowed",
    "audit_verification_payload_allowed",
    "blocked_claims",
    "capability_evidence_payload_allowed",
    "collection_timestamp_value_allowed",
    "collector_identity_value_allowed",
    "company_formation_claimed",
    "customer_access_allowed",
    "deployment_allowed",
    "deployment_witness_collection_allowed",
    "endpoint_probe_allowed",
    "endpoint_url_value_allowed",
    "evidence_ledger_append_allowed",
    "external_publication_allowed",
    "field_labels",
    "gateway_url_value_allowed",
    "http_status_value_allowed",
    "legal_clearance_claimed",
    "money_movement_allowed",
    "next_action",
    "operator_approval_claimed",
    "patent_claimed",
    "personal_data_collection_allowed",
    "production_evidence_payload_allowed",
    "proof_verification_payload_allowed",
    "public_health_declaration_allowed",
    "readiness_claimed",
    "response_body_value_allowed",
    "response_digest_value_allowed",
    "runtime_conformance_payload_allowed",
    "runtime_witness_payload_allowed",
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
    "Foundation Gateway Endpoint Evidence Receipt Rehearsal Boundary",
    "Witness packet: [`../examples/foundation_gateway_endpoint_evidence_receipt_rehearsal_witness.awaiting_evidence.json`]",
    "Rule: Gateway endpoint evidence receipt rehearsal is a local receipt field",
    "No endpoint probe, gateway URL value, endpoint URL value, HTTP status value",
    "gateway_endpoint_evidence_receipt_rehearsal_state=AwaitingEvidence",
    "endpoint_probe_allowed=false",
    "gateway_url_value_allowed=false",
    "endpoint_url_value_allowed=false",
    "http_status_value_allowed=false",
    "response_digest_value_allowed=false",
    "response_body_value_allowed=false",
    "collection_timestamp_value_allowed=false",
    "collector_identity_value_allowed=false",
    "runtime_witness_payload_allowed=false",
    "runtime_conformance_payload_allowed=false",
    "production_evidence_payload_allowed=false",
    "capability_evidence_payload_allowed=false",
    "audit_verification_payload_allowed=false",
    "proof_verification_payload_allowed=false",
    "evidence_ledger_append_allowed=false",
    "deployment_witness_collection_allowed=false",
    "public_health_declaration_allowed=false",
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
    "python scripts/validate_foundation_gateway_endpoint_evidence_receipt_rehearsal_boundary.py",
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
        "assignment",
        re.compile(
            r"\b(?:endpoint|gateway|url|http[_ -]?status|status|response|"
            r"digest|body|timestamp|collector|identity|witness|conformance|"
            r"production|capability|audit|proof|secret|token|api[_ -]?key|"
            r"client[_ -]?secret|password|workflow|run|artifact|deployment|"
            r"health|ledger|customer|person|participant|email|payment|billing|"
            r"invoice|legal|company|formation|patent|approval|receipt|evidence|"
            r"report|operator)"
            r"[_ -]?(?:id|name|value|url|target|host|ref|status|text|path|list|"
            r"number|record|address|count|error|time|payload|digest|body)?\s*=",
            re.IGNORECASE,
        ),
    ),
)
FORBIDDEN_PROMOTION_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("endpoint_evidence_recorded", re.compile(r"\bendpoint evidence\s+(?:is\s+)?(?:recorded|stored|ready|verified)\b", re.IGNORECASE)),
    ("endpoint_receipt_ready", re.compile(r"\bendpoint evidence receipt\s+(?:is\s+)?(?:ready|verified|complete|published)\b", re.IGNORECASE)),
    ("endpoint_probe_run", re.compile(r"\bendpoint probes?\s+(?:is\s+|are\s+)?(?:run|complete|verified)\b", re.IGNORECASE)),
    ("gateway_url_recorded", re.compile(r"\bgateway url\s+(?:is\s+)?(?:recorded|ready|verified|available)\b", re.IGNORECASE)),
    ("http_status_recorded", re.compile(r"\bhttp status\s+(?:is\s+)?(?:recorded|ready|verified)\b", re.IGNORECASE)),
    ("response_digest_recorded", re.compile(r"\bresponse digest\s+(?:is\s+)?(?:recorded|ready|verified)\b", re.IGNORECASE)),
    ("response_body_recorded", re.compile(r"\bresponse bod(?:y|ies)\s+(?:is\s+|are\s+)?(?:recorded|ready|verified)\b", re.IGNORECASE)),
    ("ledger_append_ready", re.compile(r"\bevidence(?:-| )ledger append\s+(?:is\s+)?(?:ready|complete|verified)\b", re.IGNORECASE)),
    ("public_health_declared", re.compile(r"\bpublic health\s+(?:is\s+)?(?:declared|ready|verified|complete)\b", re.IGNORECASE)),
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
class GatewayEndpointEvidenceReceiptRehearsalFinding:
    """One deterministic endpoint evidence receipt rehearsal validation finding."""

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

    payload = json.loads(load_text(path, label))
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
) -> list[GatewayEndpointEvidenceReceiptRehearsalFinding]:
    """Return findings when public artifacts contain values or assignments."""

    findings: list[GatewayEndpointEvidenceReceiptRehearsalFinding] = []
    for value in strings:
        for rule_id, pattern in FORBIDDEN_VALUE_PATTERNS:
            if pattern.search(value):
                findings.append(
                    GatewayEndpointEvidenceReceiptRehearsalFinding(
                        "gateway_endpoint_evidence_receipt_rehearsal_forbidden_value_pattern",
                        f"gateway endpoint evidence receipt rehearsal {artifact_label} contains forbidden value pattern: {rule_id}",
                    )
                )
    return findings


def validate_forbidden_promotions(
    strings: list[str],
    artifact_label: str,
) -> list[GatewayEndpointEvidenceReceiptRehearsalFinding]:
    """Return findings when public artifacts promote blocked endpoint evidence state."""

    findings: list[GatewayEndpointEvidenceReceiptRehearsalFinding] = []
    for value in strings:
        for rule_id, pattern in FORBIDDEN_PROMOTION_PATTERNS:
            if pattern.search(value):
                findings.append(
                    GatewayEndpointEvidenceReceiptRehearsalFinding(
                        "gateway_endpoint_evidence_receipt_rehearsal_forbidden_promotion_phrase",
                        f"gateway endpoint evidence receipt rehearsal {artifact_label} contains forbidden promotion pattern: {rule_id}",
                    )
                )
    return findings


def validate_doc_text(text: str) -> list[GatewayEndpointEvidenceReceiptRehearsalFinding]:
    """Return findings for endpoint evidence receipt rehearsal documentation drift."""

    findings: list[GatewayEndpointEvidenceReceiptRehearsalFinding] = []
    for phrase in REQUIRED_DOC_PHRASES:
        if phrase not in text:
            findings.append(
                GatewayEndpointEvidenceReceiptRehearsalFinding(
                    "foundation_gateway_endpoint_evidence_receipt_rehearsal_doc_phrase_missing",
                    f"gateway endpoint evidence receipt rehearsal doc missing required phrase: {phrase}",
                )
            )
    for label in EXPECTED_FIELD_LABELS:
        if label not in text:
            findings.append(
                GatewayEndpointEvidenceReceiptRehearsalFinding(
                    "foundation_gateway_endpoint_evidence_receipt_rehearsal_doc_label_missing",
                    f"gateway endpoint evidence receipt rehearsal doc missing field label: {label}",
                )
            )
    for label in EXPECTED_DOC_SURFACE_LABELS:
        if label not in text:
            findings.append(
                GatewayEndpointEvidenceReceiptRehearsalFinding(
                    "foundation_gateway_endpoint_evidence_receipt_rehearsal_doc_surface_missing",
                    f"gateway endpoint evidence receipt rehearsal doc missing surface label: {label}",
                )
            )
    findings.extend(validate_forbidden_values([text], "doc"))
    findings.extend(validate_forbidden_promotions([text], "doc"))
    return findings


def validate_packet(payload: dict[str, Any]) -> list[GatewayEndpointEvidenceReceiptRehearsalFinding]:
    """Return findings for endpoint evidence receipt rehearsal witness drift."""

    findings: list[GatewayEndpointEvidenceReceiptRehearsalFinding] = []
    if set(payload) != EXPECTED_ROOT_KEYS:
        findings.append(
            GatewayEndpointEvidenceReceiptRehearsalFinding(
                "gateway_endpoint_evidence_receipt_rehearsal_root_keys_invalid",
                "gateway endpoint evidence receipt rehearsal witness root keys drifted",
            )
        )
    expected_values: dict[str, Any] = {
        "schema_version": 1,
        "witness_id": EXPECTED_WITNESS_ID,
        "status": "AwaitingEvidence",
        "solver_outcome": "AwaitingEvidence",
        "blocked_claims": list(EXPECTED_BLOCKED_CLAIMS),
        "field_labels": list(EXPECTED_FIELD_LABELS),
        "next_action": EXPECTED_NEXT_ACTION,
        "endpoint_probe_allowed": False,
        "gateway_url_value_allowed": False,
        "endpoint_url_value_allowed": False,
        "http_status_value_allowed": False,
        "response_digest_value_allowed": False,
        "response_body_value_allowed": False,
        "collection_timestamp_value_allowed": False,
        "collector_identity_value_allowed": False,
        "runtime_witness_payload_allowed": False,
        "runtime_conformance_payload_allowed": False,
        "production_evidence_payload_allowed": False,
        "capability_evidence_payload_allowed": False,
        "audit_verification_payload_allowed": False,
        "proof_verification_payload_allowed": False,
        "evidence_ledger_append_allowed": False,
        "deployment_witness_collection_allowed": False,
        "public_health_declaration_allowed": False,
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
                GatewayEndpointEvidenceReceiptRehearsalFinding(
                    "gateway_endpoint_evidence_receipt_rehearsal_root_value_invalid",
                    f"{key} must remain {expected!r}",
                )
            )
    findings.extend(validate_surfaces(payload.get("surfaces")))
    findings.extend(validate_forbidden_values(iter_string_values(payload), "witness"))
    findings.extend(validate_forbidden_promotions(iter_string_values(payload), "witness"))
    return findings


def validate_surfaces(surfaces: object) -> list[GatewayEndpointEvidenceReceiptRehearsalFinding]:
    """Return findings for endpoint evidence receipt rehearsal surface inventory drift."""

    findings: list[GatewayEndpointEvidenceReceiptRehearsalFinding] = []
    if not isinstance(surfaces, list) or not all(isinstance(surface, dict) for surface in surfaces):
        return [
            GatewayEndpointEvidenceReceiptRehearsalFinding(
                "gateway_endpoint_evidence_receipt_rehearsal_surfaces_invalid",
                "gateway endpoint evidence receipt rehearsal surfaces must be a list of objects",
            )
        ]
    observed = tuple(
        (surface.get("surface_id"), surface.get("surface_type"), surface.get("state"))
        for surface in surfaces
    )
    if observed != EXPECTED_SURFACES:
        findings.append(
            GatewayEndpointEvidenceReceiptRehearsalFinding(
                "gateway_endpoint_evidence_receipt_rehearsal_surface_inventory_invalid",
                "gateway endpoint evidence receipt rehearsal surface inventory does not match the Foundation Mode set",
            )
        )
    seen_surface_ids: set[object] = set()
    for surface in surfaces:
        surface_id = surface.get("surface_id")
        if set(surface) != EXPECTED_SURFACE_KEYS:
            findings.append(
                GatewayEndpointEvidenceReceiptRehearsalFinding(
                    "gateway_endpoint_evidence_receipt_rehearsal_surface_keys_invalid",
                    f"{surface_id} surface keys drifted",
                )
            )
        if surface_id in seen_surface_ids:
            findings.append(
                GatewayEndpointEvidenceReceiptRehearsalFinding(
                    "gateway_endpoint_evidence_receipt_rehearsal_surface_duplicate",
                    "surface ids must be unique",
                )
            )
        seen_surface_ids.add(surface_id)
        if surface.get("state") != "AwaitingEvidence":
            findings.append(
                GatewayEndpointEvidenceReceiptRehearsalFinding(
                    "gateway_endpoint_evidence_receipt_rehearsal_surface_state_invalid",
                    f"{surface_id} state must be AwaitingEvidence",
                )
            )
        if surface.get("evidence_ref") != "manual_preparation_pending":
            findings.append(
                GatewayEndpointEvidenceReceiptRehearsalFinding(
                    "gateway_endpoint_evidence_receipt_rehearsal_surface_evidence_invalid",
                    f"{surface_id} evidence_ref must remain manual_preparation_pending",
                )
            )
        expected_note = EXPECTED_SURFACE_NOTES.get(str(surface_id))
        if surface.get("public_safe_note") != expected_note:
            findings.append(
                GatewayEndpointEvidenceReceiptRehearsalFinding(
                    "gateway_endpoint_evidence_receipt_rehearsal_surface_note_invalid",
                    f"{surface_id} public_safe_note drifted",
                )
            )
    return findings


def validate_foundation_gateway_endpoint_evidence_receipt_rehearsal_boundary(
    doc_path: Path = DEFAULT_DOC_PATH,
    packet_path: Path = DEFAULT_PACKET_PATH,
) -> list[GatewayEndpointEvidenceReceiptRehearsalFinding]:
    """Validate the Foundation Mode gateway endpoint evidence receipt rehearsal artifacts."""

    doc_text = load_text(doc_path, "gateway endpoint evidence receipt rehearsal boundary doc")
    packet_payload = load_json_object(packet_path, "gateway endpoint evidence receipt rehearsal witness packet")
    findings: list[GatewayEndpointEvidenceReceiptRehearsalFinding] = []
    findings.extend(validate_doc_text(doc_text))
    findings.extend(validate_packet(packet_payload))
    return findings


def main() -> int:
    """Validate endpoint evidence receipt rehearsal artifacts and print deterministic status."""

    parser = argparse.ArgumentParser(
        description="Validate Foundation Mode gateway endpoint evidence receipt rehearsal boundary artifacts."
    )
    parser.add_argument("--doc", type=Path, default=DEFAULT_DOC_PATH)
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET_PATH)
    args = parser.parse_args()
    try:
        findings = validate_foundation_gateway_endpoint_evidence_receipt_rehearsal_boundary(args.doc, args.packet)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"[FAIL] foundation_gateway_endpoint_evidence_receipt_rehearsal_load: {exc}", file=sys.stderr)
        return 2
    if findings:
        for finding in findings:
            print(f"[FAIL] {finding.rule_id}: {finding.message}", file=sys.stderr)
        print("STATUS: failed", file=sys.stderr)
        return 1
    print("[PASS] foundation_gateway_endpoint_evidence_receipt_rehearsal_doc")
    print("[PASS] foundation_gateway_endpoint_evidence_receipt_rehearsal_witness")
    print("STATUS: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
