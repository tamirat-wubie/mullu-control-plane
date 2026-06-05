#!/usr/bin/env python3
"""Validate the Foundation Mode gateway DNS target binding rehearsal boundary.

Purpose: keep issue #330 gateway DNS target binding preparation local and
public-safe while live targets, gateway URLs, provider accounts, repository
variable binding, DNS publication, DNS proof, endpoint proof, secret-presence
claims, workflow dispatch, artifact publication, operator approval, readiness
claims, customer access, personal data, money movement, legal/business claims,
publication, and deployment remain blocked.
Governance scope: Foundation Mode, issue #330 DNS target binding rehearsal,
public-safe question labels, provider/account exclusion, repository-variable
binding blocking, DNS publication blocking, secret exclusion, approval blocking,
money blocking, legal/business restraint, publication blocking, and deployment
blocking.
Dependencies: docs/FOUNDATION_GATEWAY_DNS_TARGET_BINDING_REHEARSAL_BOUNDARY.md
and examples/foundation_gateway_dns_target_binding_rehearsal_witness.awaiting_evidence.json.
Invariants:
  - Validation is read-only.
  - The witness records public-safe DNS target binding question labels only.
  - No live DNS target value, gateway URL value, provider account value,
    repository-variable binding, DNS record publication, DNS resolution proof,
    endpoint reachability proof, secret presence claim, workflow dispatch,
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
DEFAULT_DOC_PATH = REPO_ROOT / "docs" / "FOUNDATION_GATEWAY_DNS_TARGET_BINDING_REHEARSAL_BOUNDARY.md"
DEFAULT_PACKET_PATH = (
    REPO_ROOT / "examples" / "foundation_gateway_dns_target_binding_rehearsal_witness.awaiting_evidence.json"
)

EXPECTED_WITNESS_ID = "foundation_gateway_dns_target_binding_rehearsal_witness.awaiting_evidence.v1"
EXPECTED_QUESTION_LABELS = (
    "dns_target_candidate_label",
    "record_type_candidate_label",
    "dns_provider_boundary_label",
    "repository_variable_binding_question",
    "gateway_url_binding_question",
    "expected_environment_binding_question",
    "dns_resolution_receipt_question",
    "endpoint_preflight_receipt_question",
    "runtime_secret_handoff_question",
    "operator_reassessment_gate",
)
EXPECTED_BLOCKED_CLAIMS = (
    "live dns target value",
    "gateway url value",
    "provider account value",
    "repository variable binding",
    "dns record publication",
    "dns resolution proof",
    "endpoint reachability proof",
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
    "record public-safe DNS target binding question labels only; do not record "
    "live DNS targets, gateway URL values, provider account values, bind "
    "repository variables, publish DNS records, claim DNS resolution proof, "
    "claim endpoint reachability proof, claim secret presence, dispatch "
    "workflows, publish artifacts, claim operator approval, claim readiness, "
    "open customer access, collect personal data, move money, claim legal "
    "clearance, form a company, claim patent protection, publish externally, "
    "or deploy"
)
EXPECTED_SURFACES = (
    ("dns_target_candidate_question", "local_question_label", "AwaitingEvidence"),
    ("record_type_candidate_question", "local_question_label", "AwaitingEvidence"),
    ("provider_boundary_question", "local_question_label", "AwaitingEvidence"),
    ("repository_variable_binding_question", "blocked_external_route", "AwaitingEvidence"),
    ("gateway_url_binding_question", "blocked_external_route", "AwaitingEvidence"),
    ("expected_environment_binding_question", "local_question_label", "AwaitingEvidence"),
    ("dns_resolution_receipt_question", "blocked_external_route", "AwaitingEvidence"),
    ("endpoint_preflight_receipt_question", "blocked_external_route", "AwaitingEvidence"),
    ("runtime_secret_handoff_question", "blocked_external_route", "AwaitingEvidence"),
    ("operator_reassessment_gate", "local_question_label", "AwaitingEvidence"),
)
EXPECTED_SURFACE_NOTES = {
    "dns_target_candidate_question": "DNS target candidate question only; live target value is not recorded.",
    "record_type_candidate_question": "Record type candidate question only; DNS record publication is not allowed.",
    "provider_boundary_question": "Provider boundary question only; provider account values are not recorded.",
    "repository_variable_binding_question": (
        "Repository variable binding question only; repository variables are not bound."
    ),
    "gateway_url_binding_question": "Gateway URL binding question only; live URL value is not recorded.",
    "expected_environment_binding_question": (
        "Expected environment binding question only; environment readiness is not claimed."
    ),
    "dns_resolution_receipt_question": "DNS resolution receipt question only; DNS proof is not claimed.",
    "endpoint_preflight_receipt_question": "Endpoint preflight receipt question only; endpoint proof is not claimed.",
    "runtime_secret_handoff_question": "Runtime secret handoff question only; secret presence is not claimed.",
    "operator_reassessment_gate": (
        "Operator reassessment gate only; DNS publication and deployment are not approved."
    ),
}
EXPECTED_DOC_SURFACE_LABELS = (
    "DNS target candidate question",
    "Record type candidate question",
    "Provider boundary question",
    "Repository variable binding question",
    "Gateway URL binding question",
    "Expected environment binding question",
    "DNS resolution receipt question",
    "Endpoint preflight receipt question",
    "Runtime secret handoff question",
    "Operator reassessment gate",
)
EXPECTED_ROOT_KEYS = {
    "artifact_publication_allowed",
    "blocked_claims",
    "candidate_target_value_recorded",
    "company_formation_claimed",
    "customer_access_allowed",
    "deployment_allowed",
    "dns_record_published",
    "dns_resolution_claimed",
    "endpoint_reachability_claimed",
    "external_publication_allowed",
    "gateway_url_recorded",
    "legal_clearance_claimed",
    "money_movement_allowed",
    "next_action",
    "operator_approval_claimed",
    "patent_claimed",
    "personal_data_collection_allowed",
    "provider_account_recorded",
    "question_labels",
    "readiness_claimed",
    "repository_variable_bound",
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
    "Foundation Gateway DNS Target Binding Rehearsal Boundary",
    "Witness packet: [`../examples/foundation_gateway_dns_target_binding_rehearsal_witness.awaiting_evidence.json`]",
    "Rule: Gateway DNS target binding rehearsal is a local question map for a later",
    "No live DNS target value, gateway URL value, provider account value",
    "gateway_dns_target_binding_rehearsal_state=AwaitingEvidence",
    "candidate_target_value_recorded=false",
    "gateway_url_recorded=false",
    "provider_account_recorded=false",
    "repository_variable_bound=false",
    "dns_record_published=false",
    "dns_resolution_claimed=false",
    "endpoint_reachability_claimed=false",
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
    "MULLU_GATEWAY_DNS_TARGET",
    "MULLU_GATEWAY_URL",
    "MULLU_EXPECTED_RUNTIME_ENV",
    "python scripts/validate_foundation_gateway_dns_target_binding_rehearsal_boundary.py",
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
    (
        "live_assignment",
        re.compile(
            r"\b(?:secret|token|api[_ -]?key|client[_ -]?secret|password|"
            r"credential|gateway|url|dns|target|host|provider|account|"
            r"repository[_ -]?variable|variable|workflow|run|artifact|"
            r"deployment|environment|env|customer|person|participant|email|"
            r"payment|billing|invoice|legal|company|formation|patent|approval|"
            r"receipt|evidence|report|operator|ledger)"
            r"[_ -]?(?:id|name|value|url|target|host|ref|status|text|path|"
            r"list|number|record)?\s*=",
            re.IGNORECASE,
        ),
    ),
)
FORBIDDEN_PROMOTION_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("target_selected", re.compile(r"\bdns target\s+(?:is\s+)?(?:selected|bound|ready|verified)\b", re.IGNORECASE)),
    ("gateway_url_bound", re.compile(r"\bgateway url\s+(?:is\s+)?(?:bound|ready|verified|available)\b", re.IGNORECASE)),
    ("provider_account_ready", re.compile(r"\bprovider account\s+(?:is\s+)?(?:ready|verified|bound)\b", re.IGNORECASE)),
    ("repository_variable_bound", re.compile(r"\brepository variable\s+(?:is\s+)?bound\b", re.IGNORECASE)),
    ("dns_published", re.compile(r"\bdns record\s+(?:is\s+)?(?:published|ready|verified)\b", re.IGNORECASE)),
    ("dns_resolved", re.compile(r"\bdns resolution\s+(?:is\s+)?(?:proved|verified|ready|complete)\b", re.IGNORECASE)),
    ("endpoint_reachable", re.compile(r"\bendpoint\s+(?:is\s+)?(?:reachable|verified|ready)\b", re.IGNORECASE)),
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
class GatewayDnsTargetBindingRehearsalFinding:
    """One deterministic gateway DNS target binding rehearsal validation finding."""

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
) -> list[GatewayDnsTargetBindingRehearsalFinding]:
    """Return findings when public artifacts contain live values or assignments."""

    findings: list[GatewayDnsTargetBindingRehearsalFinding] = []
    for value in strings:
        for rule_id, pattern in FORBIDDEN_VALUE_PATTERNS:
            if pattern.search(value):
                findings.append(
                    GatewayDnsTargetBindingRehearsalFinding(
                        "gateway_dns_target_binding_rehearsal_forbidden_value_pattern",
                        f"gateway DNS target binding rehearsal {artifact_label} contains forbidden value pattern: {rule_id}",
                    )
                )
    return findings


def validate_forbidden_promotions(
    strings: list[str],
    artifact_label: str,
) -> list[GatewayDnsTargetBindingRehearsalFinding]:
    """Return findings when public artifacts promote blocked DNS or deployment state."""

    findings: list[GatewayDnsTargetBindingRehearsalFinding] = []
    for value in strings:
        for rule_id, pattern in FORBIDDEN_PROMOTION_PATTERNS:
            if pattern.search(value):
                findings.append(
                    GatewayDnsTargetBindingRehearsalFinding(
                        "gateway_dns_target_binding_rehearsal_forbidden_promotion_phrase",
                        f"gateway DNS target binding rehearsal {artifact_label} contains forbidden promotion pattern: {rule_id}",
                    )
                )
    return findings


def validate_doc_text(text: str) -> list[GatewayDnsTargetBindingRehearsalFinding]:
    """Return findings for gateway DNS target binding rehearsal documentation drift."""

    findings: list[GatewayDnsTargetBindingRehearsalFinding] = []
    for phrase in REQUIRED_DOC_PHRASES:
        if phrase not in text:
            findings.append(
                GatewayDnsTargetBindingRehearsalFinding(
                    "foundation_gateway_dns_target_binding_rehearsal_doc_phrase_missing",
                    f"gateway DNS target binding rehearsal doc missing required phrase: {phrase}",
                )
            )
    for label in EXPECTED_QUESTION_LABELS:
        if label not in text:
            findings.append(
                GatewayDnsTargetBindingRehearsalFinding(
                    "foundation_gateway_dns_target_binding_rehearsal_doc_label_missing",
                    f"gateway DNS target binding rehearsal doc missing question label: {label}",
                )
            )
    for label in EXPECTED_DOC_SURFACE_LABELS:
        if label not in text:
            findings.append(
                GatewayDnsTargetBindingRehearsalFinding(
                    "foundation_gateway_dns_target_binding_rehearsal_doc_surface_missing",
                    f"gateway DNS target binding rehearsal doc missing surface label: {label}",
                )
            )
    findings.extend(validate_forbidden_values([text], "doc"))
    findings.extend(validate_forbidden_promotions([text], "doc"))
    return findings


def validate_packet(payload: dict[str, Any]) -> list[GatewayDnsTargetBindingRehearsalFinding]:
    """Return findings for gateway DNS target binding rehearsal witness drift."""

    findings: list[GatewayDnsTargetBindingRehearsalFinding] = []
    if set(payload) != EXPECTED_ROOT_KEYS:
        findings.append(
            GatewayDnsTargetBindingRehearsalFinding(
                "gateway_dns_target_binding_rehearsal_root_keys_invalid",
                "gateway DNS target binding rehearsal witness root keys drifted",
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
        "candidate_target_value_recorded": False,
        "gateway_url_recorded": False,
        "provider_account_recorded": False,
        "repository_variable_bound": False,
        "dns_record_published": False,
        "dns_resolution_claimed": False,
        "endpoint_reachability_claimed": False,
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
                GatewayDnsTargetBindingRehearsalFinding(
                    "gateway_dns_target_binding_rehearsal_root_value_invalid",
                    f"{key} must remain {expected!r}",
                )
            )
    findings.extend(validate_surfaces(payload.get("surfaces")))
    findings.extend(validate_forbidden_values(iter_string_values(payload), "witness"))
    findings.extend(validate_forbidden_promotions(iter_string_values(payload), "witness"))
    return findings


def validate_surfaces(surfaces: object) -> list[GatewayDnsTargetBindingRehearsalFinding]:
    """Return findings for rehearsal surface inventory drift."""

    findings: list[GatewayDnsTargetBindingRehearsalFinding] = []
    if not isinstance(surfaces, list) or not all(isinstance(surface, dict) for surface in surfaces):
        return [
            GatewayDnsTargetBindingRehearsalFinding(
                "gateway_dns_target_binding_rehearsal_surfaces_invalid",
                "gateway DNS target binding rehearsal surfaces must be a list of objects",
            )
        ]
    observed = tuple(
        (surface.get("surface_id"), surface.get("surface_type"), surface.get("state"))
        for surface in surfaces
    )
    if observed != EXPECTED_SURFACES:
        findings.append(
            GatewayDnsTargetBindingRehearsalFinding(
                "gateway_dns_target_binding_rehearsal_surface_inventory_invalid",
                "gateway DNS target binding rehearsal surface inventory does not match the Foundation Mode set",
            )
        )
    seen_surface_ids: set[object] = set()
    for surface in surfaces:
        surface_id = surface.get("surface_id")
        if set(surface) != EXPECTED_SURFACE_KEYS:
            findings.append(
                GatewayDnsTargetBindingRehearsalFinding(
                    "gateway_dns_target_binding_rehearsal_surface_keys_invalid",
                    f"{surface_id} surface keys drifted",
                )
            )
        if surface_id in seen_surface_ids:
            findings.append(
                GatewayDnsTargetBindingRehearsalFinding(
                    "gateway_dns_target_binding_rehearsal_surface_duplicate",
                    "surface ids must be unique",
                )
            )
        seen_surface_ids.add(surface_id)
        if surface.get("state") != "AwaitingEvidence":
            findings.append(
                GatewayDnsTargetBindingRehearsalFinding(
                    "gateway_dns_target_binding_rehearsal_surface_state_invalid",
                    f"{surface_id} state must be AwaitingEvidence",
                )
            )
        if surface.get("evidence_ref") != "manual_preparation_pending":
            findings.append(
                GatewayDnsTargetBindingRehearsalFinding(
                    "gateway_dns_target_binding_rehearsal_surface_evidence_invalid",
                    f"{surface_id} evidence_ref must remain manual_preparation_pending",
                )
            )
        expected_note = EXPECTED_SURFACE_NOTES.get(str(surface_id))
        if surface.get("public_safe_note") != expected_note:
            findings.append(
                GatewayDnsTargetBindingRehearsalFinding(
                    "gateway_dns_target_binding_rehearsal_surface_note_invalid",
                    f"{surface_id} public_safe_note drifted",
                )
            )
    return findings


def validate_foundation_gateway_dns_target_binding_rehearsal_boundary(
    doc_path: Path = DEFAULT_DOC_PATH,
    packet_path: Path = DEFAULT_PACKET_PATH,
) -> list[GatewayDnsTargetBindingRehearsalFinding]:
    """Validate the Foundation Mode gateway DNS target binding rehearsal artifacts."""

    doc_text = load_text(doc_path, "gateway DNS target binding rehearsal boundary doc")
    packet_payload = load_json_object(packet_path, "gateway DNS target binding rehearsal witness packet")
    findings: list[GatewayDnsTargetBindingRehearsalFinding] = []
    findings.extend(validate_doc_text(doc_text))
    findings.extend(validate_packet(packet_payload))
    return findings


def main() -> int:
    """Validate gateway DNS target binding rehearsal artifacts and print deterministic status."""

    parser = argparse.ArgumentParser(
        description="Validate Foundation Mode gateway DNS target binding rehearsal boundary artifacts."
    )
    parser.add_argument("--doc", type=Path, default=DEFAULT_DOC_PATH)
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET_PATH)
    args = parser.parse_args()
    try:
        findings = validate_foundation_gateway_dns_target_binding_rehearsal_boundary(args.doc, args.packet)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"[FAIL] foundation_gateway_dns_target_binding_rehearsal_load: {exc}", file=sys.stderr)
        return 2
    if findings:
        for finding in findings:
            print(f"[FAIL] {finding.rule_id}: {finding.message}", file=sys.stderr)
        print("STATUS: failed", file=sys.stderr)
        return 1
    print("[PASS] foundation_gateway_dns_target_binding_rehearsal_doc")
    print("[PASS] foundation_gateway_dns_target_binding_rehearsal_witness")
    print("STATUS: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
