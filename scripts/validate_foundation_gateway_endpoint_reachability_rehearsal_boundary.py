#!/usr/bin/env python3
"""Validate the Foundation Mode gateway endpoint reachability rehearsal boundary.

Purpose: keep issue #330 gateway endpoint reachability preparation local and
public-safe while endpoint probes, gateway URLs, response evidence,
deployment witness collection, public-health declarations, workflow dispatch,
artifact publication, approval, readiness, customer access, money movement,
legal/business claims, publication, and deployment remain blocked.
Governance scope: Foundation Mode, issue #330 endpoint reachability rehearsal,
public-safe question labels, endpoint probe blocking, value exclusion,
witness-collection blocking, approval blocking, publication blocking, and
deployment restraint.
Dependencies: docs/FOUNDATION_GATEWAY_ENDPOINT_REACHABILITY_REHEARSAL_BOUNDARY.md
and examples/foundation_gateway_endpoint_reachability_rehearsal_witness.awaiting_evidence.json.
Invariants:
  - Validation is read-only.
  - The witness records public-safe endpoint reachability question labels only.
  - No endpoint probe, gateway URL value, HTTP status value, response
    digest, response body, runtime witness payload, conformance payload,
    production/capability/audit/proof payload, deployment witness collection,
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
DEFAULT_DOC_PATH = REPO_ROOT / "docs" / "FOUNDATION_GATEWAY_ENDPOINT_REACHABILITY_REHEARSAL_BOUNDARY.md"
DEFAULT_PACKET_PATH = (
    REPO_ROOT / "examples" / "foundation_gateway_endpoint_reachability_rehearsal_witness.awaiting_evidence.json"
)

EXPECTED_WITNESS_ID = "foundation_gateway_endpoint_reachability_rehearsal_witness.awaiting_evidence.v1"
EXPECTED_QUESTION_LABELS = (
    "health_endpoint_probe_question",
    "gateway_witness_endpoint_question",
    "runtime_conformance_endpoint_question",
    "endpoint_http_status_question",
    "endpoint_response_digest_question",
    "endpoint_body_shape_question",
    "production_evidence_dependency_question",
    "capability_evidence_dependency_question",
    "audit_proof_dependency_question",
    "publication_stop_rule_question",
    "operator_reassessment_gate",
)
EXPECTED_BLOCKED_CLAIMS = (
    "endpoint probe",
    "gateway url value",
    "http status value",
    "response digest",
    "response body",
    "runtime witness payload",
    "runtime conformance payload",
    "production evidence payload",
    "capability evidence payload",
    "audit verification payload",
    "proof verification payload",
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
    "record public-safe gateway endpoint reachability question labels only; "
    "do not probe endpoints, record gateway URL values, record endpoint "
    "response bodies, record HTTP status values, record response digests, "
    "claim health proof, claim gateway witness proof, claim runtime "
    "conformance proof, collect deployment witnesses, claim public health "
    "declaration, claim secret presence, dispatch workflows, publish "
    "artifacts, claim operator approval, claim readiness, open customer "
    "access, collect personal data, move money, claim legal clearance, form "
    "a company, claim patent protection, publish externally, or deploy"
)
EXPECTED_SURFACES = (
    ("health_endpoint_probe_question", "local_question_label", "AwaitingEvidence"),
    ("gateway_witness_endpoint_question", "local_question_label", "AwaitingEvidence"),
    ("runtime_conformance_endpoint_question", "local_question_label", "AwaitingEvidence"),
    ("endpoint_http_status_question", "blocked_external_evidence", "AwaitingEvidence"),
    ("endpoint_response_digest_question", "blocked_external_evidence", "AwaitingEvidence"),
    ("endpoint_body_shape_question", "blocked_external_evidence", "AwaitingEvidence"),
    ("production_evidence_dependency_question", "blocked_external_evidence", "AwaitingEvidence"),
    ("capability_evidence_dependency_question", "blocked_external_evidence", "AwaitingEvidence"),
    ("audit_proof_dependency_question", "blocked_external_evidence", "AwaitingEvidence"),
    ("publication_stop_rule_question", "local_question_label", "AwaitingEvidence"),
    ("operator_reassessment_gate", "local_question_label", "AwaitingEvidence"),
)
EXPECTED_SURFACE_NOTES = {
    "health_endpoint_probe_question": "Health endpoint probe question only; endpoint probes are not run.",
    "gateway_witness_endpoint_question": (
        "Gateway witness endpoint question only; gateway witness payloads are not collected."
    ),
    "runtime_conformance_endpoint_question": (
        "Runtime conformance endpoint question only; runtime conformance payloads are not collected."
    ),
    "endpoint_http_status_question": "Endpoint HTTP status question only; HTTP status values are not recorded.",
    "endpoint_response_digest_question": (
        "Endpoint response digest question only; response digests are not recorded."
    ),
    "endpoint_body_shape_question": "Endpoint body shape question only; response bodies are not recorded.",
    "production_evidence_dependency_question": (
        "Production evidence dependency question only; production evidence payloads are not collected."
    ),
    "capability_evidence_dependency_question": (
        "Capability evidence dependency question only; capability evidence payloads are not collected."
    ),
    "audit_proof_dependency_question": "Audit proof dependency question only; audit and proof payloads are not collected.",
    "publication_stop_rule_question": (
        "Publication stop rule question only; endpoint receipts and artifacts are not published."
    ),
    "operator_reassessment_gate": "Operator reassessment gate only; endpoint proof and deployment are not approved.",
}
EXPECTED_DOC_SURFACE_LABELS = (
    "Health endpoint probe question",
    "Gateway witness endpoint question",
    "Runtime conformance endpoint question",
    "Endpoint HTTP status question",
    "Endpoint response digest question",
    "Endpoint body shape question",
    "Production evidence dependency question",
    "Capability evidence dependency question",
    "Audit proof dependency question",
    "Publication stop rule question",
    "Operator reassessment gate",
)
EXPECTED_ROOT_KEYS = {
    "artifact_publication_allowed",
    "audit_verification_payload_recorded",
    "blocked_claims",
    "capability_evidence_payload_recorded",
    "company_formation_claimed",
    "customer_access_allowed",
    "deployment_allowed",
    "deployment_witness_collected",
    "external_publication_allowed",
    "gateway_url_recorded",
    "http_status_recorded",
    "legal_clearance_claimed",
    "live_endpoint_probe_allowed",
    "money_movement_allowed",
    "next_action",
    "operator_approval_claimed",
    "patent_claimed",
    "personal_data_collection_allowed",
    "production_evidence_payload_recorded",
    "proof_verification_payload_recorded",
    "public_health_declared",
    "question_labels",
    "readiness_claimed",
    "response_body_recorded",
    "response_digest_recorded",
    "runtime_conformance_payload_recorded",
    "runtime_witness_payload_recorded",
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
    "Foundation Gateway Endpoint Reachability Rehearsal Boundary",
    "Witness packet: [`../examples/foundation_gateway_endpoint_reachability_rehearsal_witness.awaiting_evidence.json`]",
    "Rule: Gateway endpoint reachability rehearsal is a local question map for a",
    "No endpoint probe, gateway URL value, HTTP status value, response digest",
    "gateway_endpoint_reachability_rehearsal_state=AwaitingEvidence",
    "live_endpoint_probe_allowed=false",
    "gateway_url_recorded=false",
    "http_status_recorded=false",
    "response_digest_recorded=false",
    "response_body_recorded=false",
    "runtime_witness_payload_recorded=false",
    "runtime_conformance_payload_recorded=false",
    "production_evidence_payload_recorded=false",
    "capability_evidence_payload_recorded=false",
    "audit_verification_payload_recorded=false",
    "proof_verification_payload_recorded=false",
    "deployment_witness_collected=false",
    "public_health_declared=false",
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
    "python scripts/validate_foundation_gateway_endpoint_reachability_rehearsal_boundary.py",
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
            r"\b(?:endpoint|gateway|url|http[_ -]?status|status|response|"
            r"digest|body|witness|conformance|production|capability|audit|"
            r"proof|secret|token|api[_ -]?key|client[_ -]?secret|password|"
            r"workflow|run|artifact|deployment|health|customer|person|"
            r"participant|email|payment|billing|invoice|legal|company|"
            r"formation|patent|approval|receipt|evidence|report|operator)"
            r"[_ -]?(?:id|name|value|url|target|host|ref|status|text|path|"
            r"list|number|record|address|count|error|time|payload|digest|body)?\s*=",
            re.IGNORECASE,
        ),
    ),
)
FORBIDDEN_PROMOTION_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("live_endpoint_probe_run", re.compile(r"\bendpoint probes?\s+(?:is\s+|are\s+)?(?:run|complete|verified)\b", re.IGNORECASE)),
    ("gateway_url_recorded", re.compile(r"\bgateway url\s+(?:is\s+)?(?:recorded|ready|verified|available)\b", re.IGNORECASE)),
    ("http_status_recorded", re.compile(r"\bhttp status\s+(?:is\s+)?(?:recorded|ready|verified)\b", re.IGNORECASE)),
    ("response_digest_recorded", re.compile(r"\bresponse digest\s+(?:is\s+)?(?:recorded|ready|verified)\b", re.IGNORECASE)),
    ("response_body_recorded", re.compile(r"\bresponse bod(?:y|ies)\s+(?:is\s+|are\s+)?(?:recorded|ready|verified)\b", re.IGNORECASE)),
    ("endpoint_reachable", re.compile(r"\bendpoint\s+(?:is\s+)?(?:reachable|verified|ready)\b", re.IGNORECASE)),
    ("witness_collected", re.compile(r"\bdeployment witness\s+(?:is\s+)?(?:collected|ready|verified|complete)\b", re.IGNORECASE)),
    ("public_health_declared", re.compile(r"\bpublic health\s+(?:is\s+)?(?:declared|ready|verified|complete)\b", re.IGNORECASE)),
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
class GatewayEndpointReachabilityRehearsalFinding:
    """One deterministic gateway endpoint reachability rehearsal validation finding."""

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
) -> list[GatewayEndpointReachabilityRehearsalFinding]:
    """Return findings when public artifacts contain live values or assignments."""

    findings: list[GatewayEndpointReachabilityRehearsalFinding] = []
    for value in strings:
        for rule_id, pattern in FORBIDDEN_VALUE_PATTERNS:
            if pattern.search(value):
                findings.append(
                    GatewayEndpointReachabilityRehearsalFinding(
                        "gateway_endpoint_reachability_rehearsal_forbidden_value_pattern",
                        f"gateway endpoint reachability rehearsal {artifact_label} contains forbidden value pattern: {rule_id}",
                    )
                )
    return findings


def validate_forbidden_promotions(
    strings: list[str],
    artifact_label: str,
) -> list[GatewayEndpointReachabilityRehearsalFinding]:
    """Return findings when public artifacts promote blocked endpoint or deployment state."""

    findings: list[GatewayEndpointReachabilityRehearsalFinding] = []
    for value in strings:
        for rule_id, pattern in FORBIDDEN_PROMOTION_PATTERNS:
            if pattern.search(value):
                findings.append(
                    GatewayEndpointReachabilityRehearsalFinding(
                        "gateway_endpoint_reachability_rehearsal_forbidden_promotion_phrase",
                        f"gateway endpoint reachability rehearsal {artifact_label} contains forbidden promotion pattern: {rule_id}",
                    )
                )
    return findings


def validate_doc_text(text: str) -> list[GatewayEndpointReachabilityRehearsalFinding]:
    """Return findings for gateway endpoint reachability rehearsal documentation drift."""

    findings: list[GatewayEndpointReachabilityRehearsalFinding] = []
    for phrase in REQUIRED_DOC_PHRASES:
        if phrase not in text:
            findings.append(
                GatewayEndpointReachabilityRehearsalFinding(
                    "foundation_gateway_endpoint_reachability_rehearsal_doc_phrase_missing",
                    f"gateway endpoint reachability rehearsal doc missing required phrase: {phrase}",
                )
            )
    for label in EXPECTED_QUESTION_LABELS:
        if label not in text:
            findings.append(
                GatewayEndpointReachabilityRehearsalFinding(
                    "foundation_gateway_endpoint_reachability_rehearsal_doc_label_missing",
                    f"gateway endpoint reachability rehearsal doc missing question label: {label}",
                )
            )
    for label in EXPECTED_DOC_SURFACE_LABELS:
        if label not in text:
            findings.append(
                GatewayEndpointReachabilityRehearsalFinding(
                    "foundation_gateway_endpoint_reachability_rehearsal_doc_surface_missing",
                    f"gateway endpoint reachability rehearsal doc missing surface label: {label}",
                )
            )
    findings.extend(validate_forbidden_values([text], "doc"))
    findings.extend(validate_forbidden_promotions([text], "doc"))
    return findings


def validate_packet(payload: dict[str, Any]) -> list[GatewayEndpointReachabilityRehearsalFinding]:
    """Return findings for gateway endpoint reachability rehearsal witness drift."""

    findings: list[GatewayEndpointReachabilityRehearsalFinding] = []
    if set(payload) != EXPECTED_ROOT_KEYS:
        findings.append(
            GatewayEndpointReachabilityRehearsalFinding(
                "gateway_endpoint_reachability_rehearsal_root_keys_invalid",
                "gateway endpoint reachability rehearsal witness root keys drifted",
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
        "live_endpoint_probe_allowed": False,
        "gateway_url_recorded": False,
        "http_status_recorded": False,
        "response_digest_recorded": False,
        "response_body_recorded": False,
        "runtime_witness_payload_recorded": False,
        "runtime_conformance_payload_recorded": False,
        "production_evidence_payload_recorded": False,
        "capability_evidence_payload_recorded": False,
        "audit_verification_payload_recorded": False,
        "proof_verification_payload_recorded": False,
        "deployment_witness_collected": False,
        "public_health_declared": False,
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
                GatewayEndpointReachabilityRehearsalFinding(
                    "gateway_endpoint_reachability_rehearsal_root_value_invalid",
                    f"{key} must remain {expected!r}",
                )
            )
    findings.extend(validate_surfaces(payload.get("surfaces")))
    findings.extend(validate_forbidden_values(iter_string_values(payload), "witness"))
    findings.extend(validate_forbidden_promotions(iter_string_values(payload), "witness"))
    return findings


def validate_surfaces(surfaces: object) -> list[GatewayEndpointReachabilityRehearsalFinding]:
    """Return findings for rehearsal surface inventory drift."""

    findings: list[GatewayEndpointReachabilityRehearsalFinding] = []
    if not isinstance(surfaces, list) or not all(isinstance(surface, dict) for surface in surfaces):
        return [
            GatewayEndpointReachabilityRehearsalFinding(
                "gateway_endpoint_reachability_rehearsal_surfaces_invalid",
                "gateway endpoint reachability rehearsal surfaces must be a list of objects",
            )
        ]
    observed = tuple(
        (surface.get("surface_id"), surface.get("surface_type"), surface.get("state"))
        for surface in surfaces
    )
    if observed != EXPECTED_SURFACES:
        findings.append(
            GatewayEndpointReachabilityRehearsalFinding(
                "gateway_endpoint_reachability_rehearsal_surface_inventory_invalid",
                "gateway endpoint reachability rehearsal surface inventory does not match the Foundation Mode set",
            )
        )
    seen_surface_ids: set[object] = set()
    for surface in surfaces:
        surface_id = surface.get("surface_id")
        if set(surface) != EXPECTED_SURFACE_KEYS:
            findings.append(
                GatewayEndpointReachabilityRehearsalFinding(
                    "gateway_endpoint_reachability_rehearsal_surface_keys_invalid",
                    f"{surface_id} surface keys drifted",
                )
            )
        if surface_id in seen_surface_ids:
            findings.append(
                GatewayEndpointReachabilityRehearsalFinding(
                    "gateway_endpoint_reachability_rehearsal_surface_duplicate",
                    "surface ids must be unique",
                )
            )
        seen_surface_ids.add(surface_id)
        if surface.get("state") != "AwaitingEvidence":
            findings.append(
                GatewayEndpointReachabilityRehearsalFinding(
                    "gateway_endpoint_reachability_rehearsal_surface_state_invalid",
                    f"{surface_id} state must be AwaitingEvidence",
                )
            )
        if surface.get("evidence_ref") != "manual_preparation_pending":
            findings.append(
                GatewayEndpointReachabilityRehearsalFinding(
                    "gateway_endpoint_reachability_rehearsal_surface_evidence_invalid",
                    f"{surface_id} evidence_ref must remain manual_preparation_pending",
                )
            )
        expected_note = EXPECTED_SURFACE_NOTES.get(str(surface_id))
        if surface.get("public_safe_note") != expected_note:
            findings.append(
                GatewayEndpointReachabilityRehearsalFinding(
                    "gateway_endpoint_reachability_rehearsal_surface_note_invalid",
                    f"{surface_id} public_safe_note drifted",
                )
            )
    return findings


def validate_foundation_gateway_endpoint_reachability_rehearsal_boundary(
    doc_path: Path = DEFAULT_DOC_PATH,
    packet_path: Path = DEFAULT_PACKET_PATH,
) -> list[GatewayEndpointReachabilityRehearsalFinding]:
    """Validate the Foundation Mode gateway endpoint reachability rehearsal artifacts."""

    doc_text = load_text(doc_path, "gateway endpoint reachability rehearsal boundary doc")
    packet_payload = load_json_object(packet_path, "gateway endpoint reachability rehearsal witness packet")
    findings: list[GatewayEndpointReachabilityRehearsalFinding] = []
    findings.extend(validate_doc_text(doc_text))
    findings.extend(validate_packet(packet_payload))
    return findings


def main() -> int:
    """Validate gateway endpoint reachability rehearsal artifacts and print deterministic status."""

    parser = argparse.ArgumentParser(
        description="Validate Foundation Mode gateway endpoint reachability rehearsal boundary artifacts."
    )
    parser.add_argument("--doc", type=Path, default=DEFAULT_DOC_PATH)
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET_PATH)
    args = parser.parse_args()
    try:
        findings = validate_foundation_gateway_endpoint_reachability_rehearsal_boundary(args.doc, args.packet)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"[FAIL] foundation_gateway_endpoint_reachability_rehearsal_load: {exc}", file=sys.stderr)
        return 2
    if findings:
        for finding in findings:
            print(f"[FAIL] {finding.rule_id}: {finding.message}", file=sys.stderr)
        print("STATUS: failed", file=sys.stderr)
        return 1
    print("[PASS] foundation_gateway_endpoint_reachability_rehearsal_doc")
    print("[PASS] foundation_gateway_endpoint_reachability_rehearsal_witness")
    print("STATUS: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
