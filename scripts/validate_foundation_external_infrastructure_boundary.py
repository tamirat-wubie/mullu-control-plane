#!/usr/bin/env python3
"""Validate the Foundation Mode external-infrastructure boundary.

Purpose: keep external infrastructure drafting local and public-safe while DNS,
runtime, database, secret-placement, TLS, firewall, rollback, endpoint,
workflow, paid infrastructure, customer, publication, and deployment claims
remain blocked.
Governance scope: Foundation Mode, issue #330 prerequisite surfaces,
private-value exclusion, external-effect blocking, and readiness blocking.
Dependencies: docs/FOUNDATION_EXTERNAL_INFRASTRUCTURE_BOUNDARY.md and
examples/foundation_external_infrastructure_witness.awaiting_evidence.json.
Invariants:
  - Validation is read-only.
  - The witness records external-infrastructure preparation only.
  - DNS mutation, runtime provisioning, secret placement, workflow dispatch,
    paid infrastructure, customer access, publication, and deployment remain
    blocked.
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
DEFAULT_DOC_PATH = REPO_ROOT / "docs" / "FOUNDATION_EXTERNAL_INFRASTRUCTURE_BOUNDARY.md"
DEFAULT_PACKET_PATH = REPO_ROOT / "examples" / "foundation_external_infrastructure_witness.awaiting_evidence.json"

EXPECTED_WITNESS_ID = "foundation_external_infrastructure_witness.awaiting_evidence.v1"
EXPECTED_BLOCKED_CLAIMS = (
    "external-infrastructure completeness",
    "DNS authority verification",
    "DNS target binding",
    "DNS mutation",
    "runtime host provisioning",
    "managed database provisioning",
    "secret placement verification",
    "TLS readiness",
    "firewall readiness",
    "rollback verification",
    "endpoint reachability",
    "repository variable binding",
    "workflow dispatch",
    "paid infrastructure activation",
    "customer access",
    "external publication",
    "deployment readiness",
)
EXPECTED_SURFACES = (
    ("dns_authority_questions", "local_draft", "AwaitingEvidence"),
    ("gateway_dns_target_questions", "local_draft", "AwaitingEvidence"),
    ("runtime_host_questions", "local_draft", "AwaitingEvidence"),
    ("managed_database_questions", "local_draft", "AwaitingEvidence"),
    ("secret_manager_questions", "local_draft", "AwaitingEvidence"),
    ("tls_certificate_questions", "local_draft", "AwaitingEvidence"),
    ("firewall_network_questions", "local_draft", "AwaitingEvidence"),
    ("rollback_path_questions", "local_draft", "AwaitingEvidence"),
    ("private_runtime_witness_questions", "local_draft", "AwaitingEvidence"),
    ("repository_variable_questions", "local_draft", "AwaitingEvidence"),
    ("endpoint_reachability_questions", "local_draft", "AwaitingEvidence"),
    ("workflow_dispatch_questions", "local_draft", "AwaitingEvidence"),
)
EXPECTED_ROOT_KEYS = {
    "blocked_claims",
    "customer_access_allowed",
    "deployment_allowed",
    "dns_authority_verified",
    "dns_mutation_allowed",
    "dns_target_bound",
    "endpoint_reachability_claimed",
    "external_infrastructure_complete_claimed",
    "external_infrastructure_surfaces",
    "external_publication_allowed",
    "firewall_ready_claimed",
    "issue_ref",
    "issue_state",
    "managed_database_provisioned",
    "next_action",
    "paid_infrastructure_allowed",
    "repository_variable_binding_allowed",
    "rollback_verified",
    "runtime_host_provisioned",
    "schema_version",
    "secret_placement_verified",
    "solver_outcome",
    "status",
    "tls_ready_claimed",
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
    "Foundation External Infrastructure Boundary",
    "Witness packet: [`../examples/foundation_external_infrastructure_witness.awaiting_evidence.json`]",
    "Rule: External-infrastructure preparation is a local planning boundary, not an",
    "No external-infrastructure completeness, DNS authority verification, DNS target",
    "external_infrastructure_boundary_state=AwaitingEvidence",
    "external_infrastructure_complete_claimed=false",
    "dns_authority_verified=false",
    "dns_target_bound=false",
    "dns_mutation_allowed=false",
    "runtime_host_provisioned=false",
    "managed_database_provisioned=false",
    "secret_placement_verified=false",
    "endpoint_reachability_claimed=false",
    "repository_variable_binding_allowed=false",
    "workflow_dispatch_allowed=false",
    "paid_infrastructure_allowed=false",
    "deployment_allowed=false",
    "python scripts/validate_foundation_external_infrastructure_boundary.py",
)
FORBIDDEN_VALUE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("url_value", re.compile(r"https?://", re.IGNORECASE)),
    ("email_value", re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)),
    ("private_path", re.compile(r"\b[A-Za-z]:[\\/]|\\\\", re.IGNORECASE)),
    (
        "dns_or_gateway_assignment",
        re.compile(
            r"\b(?:dns|gateway|host|hostname|target|record|provider|domain)[_ -]?"
            r"(?:id|url|ref|target|value|status|address|record)?\s*=",
            re.IGNORECASE,
        ),
    ),
    (
        "runtime_or_database_assignment",
        re.compile(
            r"\b(?:runtime|server|cluster|container|database|postgres|db)[_ -]?"
            r"(?:id|url|ref|target|value|status|address|dsn)?\s*=",
            re.IGNORECASE,
        ),
    ),
    (
        "account_or_provider_assignment",
        re.compile(
            r"\b(?:account|provider|tenant|project|cloud)[_ -]?"
            r"(?:id|ref|target|value|status)?\s*=",
            re.IGNORECASE,
        ),
    ),
    (
        "secret_assignment",
        re.compile(r"\b(?:password|secret|token|api[_ -]?key|credential|client[_ -]?secret)\s*=", re.IGNORECASE),
    ),
    ("private_key_material", re.compile(r"BEGIN [A-Z ]*PRIVATE KEY")),
    (
        "workflow_or_publication_assignment",
        re.compile(
            r"\b(?:workflow|dispatch|publish|publication|deploy|deployment|production)[_ -]?"
            r"(?:id|url|ref|target|value|status|run)?\s*=",
            re.IGNORECASE,
        ),
    ),
    (
        "customer_assignment",
        re.compile(
            r"\b(?:customer|pilot|participant|user)[_ -]?"
            r"(?:id|name|email|ref|target|value)?\s*=",
            re.IGNORECASE,
        ),
    ),
)
FORBIDDEN_PROMOTION_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("external_infrastructure_complete", re.compile(r"\bexternal infrastructure\s+(?:is\s+)?complete\b", re.IGNORECASE)),
    ("dns_ready", re.compile(r"\bdns\s+(?:is\s+)?ready\b", re.IGNORECASE)),
    ("dns_bound", re.compile(r"\bdns\s+target\s+(?:is\s+)?bound\b", re.IGNORECASE)),
    ("runtime_host_provisioned", re.compile(r"\bruntime\s+host\s+(?:is\s+)?provisioned\b", re.IGNORECASE)),
    ("database_provisioned", re.compile(r"\bdatabase\s+(?:is\s+)?provisioned\b", re.IGNORECASE)),
    ("secret_placement_verified", re.compile(r"\bsecret\s+placement\s+(?:is\s+)?verified\b", re.IGNORECASE)),
    ("tls_ready", re.compile(r"\btls\s+(?:is\s+)?ready\b", re.IGNORECASE)),
    ("firewall_ready", re.compile(r"\bfirewall\s+(?:is\s+)?ready\b", re.IGNORECASE)),
    ("rollback_verified", re.compile(r"\brollback\s+(?:is\s+)?verified\b", re.IGNORECASE)),
    ("endpoint_reachable", re.compile(r"\bendpoint\s+(?:is\s+)?reachable\b", re.IGNORECASE)),
    ("workflow_dispatched", re.compile(r"\bworkflow\s+(?:is\s+)?dispatched\b", re.IGNORECASE)),
    ("deployment_ready", re.compile(r"\bdeployment\s+(?:is\s+)?ready\b", re.IGNORECASE)),
    ("published_externally", re.compile(r"\bpublished\s+externally\b", re.IGNORECASE)),
)


@dataclass(frozen=True, slots=True)
class ExternalInfrastructureFinding:
    """One deterministic external-infrastructure validation finding."""

    rule_id: str
    message: str


def load_text(path: Path, label: str) -> str:
    """Load one text artifact with explicit path errors."""

    if not path.exists():
        raise FileNotFoundError(f"missing {label}: {path}")
    if not path.is_file():
        raise IsADirectoryError(f"{label} path is not a file: {path}")
    return path.read_text(encoding="utf-8")


def load_json_object(path: Path, label: str) -> dict[str, Any]:
    """Load one JSON object with explicit path and type errors."""

    if not path.exists():
        raise FileNotFoundError(f"missing {label}: {path}")
    if not path.is_file():
        raise IsADirectoryError(f"{label} path is not a file: {path}")
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError(f"{label} must be a JSON object")
    return payload


def validate_doc_text(text: str) -> list[ExternalInfrastructureFinding]:
    """Return findings for missing external-infrastructure documentation anchors."""

    findings: list[ExternalInfrastructureFinding] = []
    for phrase in REQUIRED_DOC_PHRASES:
        if phrase not in text:
            findings.append(
                ExternalInfrastructureFinding(
                    "foundation_external_infrastructure_doc_phrase_missing",
                    f"external-infrastructure boundary doc missing required phrase: {phrase}",
                )
            )
    return findings


def validate_packet(payload: dict[str, Any]) -> list[ExternalInfrastructureFinding]:
    """Return findings for external-infrastructure witness drift."""

    findings: list[ExternalInfrastructureFinding] = []
    findings.extend(validate_root_contract(payload))
    findings.extend(validate_external_infrastructure_surfaces(payload.get("external_infrastructure_surfaces")))
    findings.extend(validate_forbidden_value_patterns(payload))
    findings.extend(validate_forbidden_promotion_patterns(payload))
    return findings


def validate_root_contract(payload: dict[str, Any]) -> list[ExternalInfrastructureFinding]:
    """Return findings for root-level external-infrastructure witness drift."""

    findings: list[ExternalInfrastructureFinding] = []
    if set(payload) != EXPECTED_ROOT_KEYS:
        findings.append(
            ExternalInfrastructureFinding(
                "external_infrastructure_root_keys_invalid",
                f"root keys must be: {', '.join(sorted(EXPECTED_ROOT_KEYS))}",
            )
        )
    expected_values = {
        "witness_id": EXPECTED_WITNESS_ID,
        "schema_version": 1,
        "status": "AwaitingEvidence",
        "solver_outcome": "AwaitingEvidence",
        "issue_ref": "github_issue_330",
        "issue_state": "AwaitingEvidence",
        "external_infrastructure_complete_claimed": False,
        "dns_authority_verified": False,
        "dns_target_bound": False,
        "dns_mutation_allowed": False,
        "runtime_host_provisioned": False,
        "managed_database_provisioned": False,
        "secret_placement_verified": False,
        "tls_ready_claimed": False,
        "firewall_ready_claimed": False,
        "rollback_verified": False,
        "endpoint_reachability_claimed": False,
        "repository_variable_binding_allowed": False,
        "workflow_dispatch_allowed": False,
        "paid_infrastructure_allowed": False,
        "customer_access_allowed": False,
        "external_publication_allowed": False,
        "deployment_allowed": False,
    }
    for key, expected_value in expected_values.items():
        if payload.get(key) != expected_value:
            findings.append(
                ExternalInfrastructureFinding(
                    "external_infrastructure_root_value_invalid",
                    f"{key} must be {expected_value!r}",
                )
            )
    if tuple(payload.get("blocked_claims") or ()) != EXPECTED_BLOCKED_CLAIMS:
        findings.append(
            ExternalInfrastructureFinding(
                "external_infrastructure_blocked_claims_invalid",
                f"blocked_claims must be: {', '.join(EXPECTED_BLOCKED_CLAIMS)}",
            )
        )
    next_action = payload.get("next_action")
    if not isinstance(next_action, str) or "continue external infrastructure question drafting" not in next_action:
        findings.append(
            ExternalInfrastructureFinding(
                "external_infrastructure_next_action_invalid",
                "next_action must preserve local external-infrastructure drafting without effect promotion",
            )
        )
    return findings


def validate_external_infrastructure_surfaces(
    external_infrastructure_surfaces: object,
) -> list[ExternalInfrastructureFinding]:
    """Return findings for external-infrastructure surface drift."""

    findings: list[ExternalInfrastructureFinding] = []
    if not isinstance(external_infrastructure_surfaces, list) or not all(
        isinstance(surface, dict) for surface in external_infrastructure_surfaces
    ):
        return [
            ExternalInfrastructureFinding(
                "external_infrastructure_surfaces_invalid",
                "external_infrastructure_surfaces must be a list of objects",
            )
        ]
    observed_surfaces = tuple(
        (surface.get("surface_id"), surface.get("surface_type"), surface.get("state"))
        for surface in external_infrastructure_surfaces
    )
    if observed_surfaces != EXPECTED_SURFACES:
        findings.append(
            ExternalInfrastructureFinding(
                "external_infrastructure_surface_inventory_invalid",
                "external-infrastructure surface inventory does not match the Foundation Mode external-infrastructure set",
            )
        )
    surface_ids = [surface.get("surface_id") for surface in external_infrastructure_surfaces]
    if len(set(surface_ids)) != len(surface_ids):
        findings.append(
            ExternalInfrastructureFinding(
                "external_infrastructure_surface_duplicate",
                "surface ids must be unique",
            )
        )
    for surface in external_infrastructure_surfaces:
        surface_id = str(surface.get("surface_id", "<missing>"))
        if set(surface) != EXPECTED_SURFACE_KEYS:
            findings.append(
                ExternalInfrastructureFinding(
                    "external_infrastructure_surface_keys_invalid",
                    f"{surface_id} surface keys must be: {', '.join(sorted(EXPECTED_SURFACE_KEYS))}",
                )
            )
        if surface.get("state") != "AwaitingEvidence":
            findings.append(
                ExternalInfrastructureFinding(
                    "external_infrastructure_surface_state_invalid",
                    f"{surface_id} state must be AwaitingEvidence",
                )
            )
        if surface.get("evidence_ref") != "manual_preparation_pending":
            findings.append(
                ExternalInfrastructureFinding(
                    "external_infrastructure_surface_evidence_invalid",
                    f"{surface_id} evidence_ref must stay manual_preparation_pending in the committed packet",
                )
            )
        if not isinstance(surface.get("public_safe_note"), str) or not surface["public_safe_note"].strip():
            findings.append(
                ExternalInfrastructureFinding(
                    "external_infrastructure_surface_note_invalid",
                    f"{surface_id} public_safe_note must be a non-empty string",
                )
            )
    return findings


def validate_forbidden_value_patterns(payload: dict[str, Any]) -> list[ExternalInfrastructureFinding]:
    """Return findings for private or effect-bearing external-infrastructure values."""

    serialized_payload = json.dumps(payload, sort_keys=True)
    findings: list[ExternalInfrastructureFinding] = []
    for rule_id, pattern in FORBIDDEN_VALUE_PATTERNS:
        if pattern.search(serialized_payload):
            findings.append(
                ExternalInfrastructureFinding(
                    "external_infrastructure_forbidden_private_value_pattern",
                    f"external-infrastructure witness contains forbidden value pattern: {rule_id}",
                )
            )
    return findings


def validate_forbidden_promotion_patterns(payload: dict[str, Any]) -> list[ExternalInfrastructureFinding]:
    """Return findings if the witness drifts into readiness promotion phrases."""

    serialized_payload = json.dumps(payload, sort_keys=True)
    findings: list[ExternalInfrastructureFinding] = []
    for rule_id, pattern in FORBIDDEN_PROMOTION_PATTERNS:
        if pattern.search(serialized_payload):
            findings.append(
                ExternalInfrastructureFinding(
                    "external_infrastructure_forbidden_promotion_phrase",
                    f"external-infrastructure witness contains forbidden promotion pattern: {rule_id}",
                )
            )
    return findings


def validate_foundation_external_infrastructure_boundary(
    doc_path: Path = DEFAULT_DOC_PATH,
    packet_path: Path = DEFAULT_PACKET_PATH,
) -> list[ExternalInfrastructureFinding]:
    """Validate the Foundation Mode external-infrastructure boundary artifacts."""

    doc_text = load_text(doc_path, "external-infrastructure boundary doc")
    packet_payload = load_json_object(packet_path, "external-infrastructure witness packet")
    return [
        *validate_doc_text(doc_text),
        *validate_packet(packet_payload),
    ]


def main(argv: list[str] | None = None) -> int:
    """Validate external-infrastructure artifacts and print deterministic status."""

    parser = argparse.ArgumentParser(description="Validate Foundation Mode external-infrastructure artifacts.")
    parser.add_argument("--doc", type=Path, default=DEFAULT_DOC_PATH)
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET_PATH)
    args = parser.parse_args(argv)

    try:
        findings = validate_foundation_external_infrastructure_boundary(args.doc, args.packet)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"[FAIL] foundation_external_infrastructure_load: {exc}", file=sys.stderr)
        print("STATUS: failed", file=sys.stderr)
        return 1

    if findings:
        for finding in findings:
            print(f"[FAIL] {finding.rule_id}: {finding.message}", file=sys.stderr)
        print("STATUS: failed", file=sys.stderr)
        return 1
    print("[PASS] foundation_external_infrastructure_doc")
    print("[PASS] foundation_external_infrastructure_witness")
    print("STATUS: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
