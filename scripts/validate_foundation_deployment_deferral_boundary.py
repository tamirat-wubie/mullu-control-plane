#!/usr/bin/env python3
"""Validate the Foundation Mode deployment-deferral boundary.

Purpose: keep deployment deferred while deployment-plan approval, cloud
activation, public endpoint publication, production-health claims, runtime
readiness, customer access, spending, credential use, secret use, migration
execution, DNS mutation, external publication, and deployment claims remain
blocked.
Governance scope: Foundation Mode, deployment deferral, public-safe planning
witness, private-value exclusion, exposure blocking, cost blocking, credential
blocking, customer-access blocking, and deployment blocking.
Dependencies: docs/FOUNDATION_DEPLOYMENT_DEFERRAL_BOUNDARY.md and
examples/foundation_deployment_deferral_witness.awaiting_evidence.json.
Invariants:
  - Validation is read-only.
  - The witness records deployment-deferral planning only.
  - No deployment approval, cloud activation, public endpoint, production
    health, runtime readiness, customer access, spending, credential use,
    secret use, migration execution, DNS mutation, private value, external
    publication, or deployment claim is allowed.
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
DEFAULT_DOC_PATH = REPO_ROOT / "docs" / "FOUNDATION_DEPLOYMENT_DEFERRAL_BOUNDARY.md"
DEFAULT_PACKET_PATH = REPO_ROOT / "examples" / "foundation_deployment_deferral_witness.awaiting_evidence.json"

EXPECTED_WITNESS_ID = "foundation_deployment_deferral_witness.awaiting_evidence.v1"
EXPECTED_BLOCKED_CLAIMS = (
    "deployment plan approval",
    "cloud activation",
    "public endpoint publication",
    "production health",
    "runtime readiness",
    "customer access",
    "spending authorization",
    "credential use",
    "secret use",
    "migration execution",
    "DNS mutation",
    "external publication",
    "deployment readiness",
)
EXPECTED_SURFACES = (
    ("deployment_prerequisite_map", "local_draft", "AwaitingEvidence"),
    ("hosting_cloud_questions", "local_draft", "AwaitingEvidence"),
    ("endpoint_exposure_questions", "local_draft", "AwaitingEvidence"),
    ("runtime_health_questions", "local_draft", "AwaitingEvidence"),
    ("rollback_recovery_questions", "local_draft", "AwaitingEvidence"),
    ("cost_billing_questions", "local_draft", "AwaitingEvidence"),
    ("credential_secret_questions", "local_draft", "AwaitingEvidence"),
    ("customer_support_questions", "local_draft", "AwaitingEvidence"),
    ("publication_questions", "local_draft", "AwaitingEvidence"),
)
EXPECTED_ROOT_KEYS = {
    "blocked_claims",
    "cloud_activation_allowed",
    "credential_use_allowed",
    "customer_access_allowed",
    "deployment_allowed",
    "deployment_deferral_surfaces",
    "deployment_plan_approved",
    "dns_mutation_allowed",
    "external_publication_allowed",
    "migration_execution_allowed",
    "next_action",
    "production_health_claimed",
    "public_endpoint_allowed",
    "runtime_readiness_claimed",
    "schema_version",
    "secret_use_allowed",
    "solver_outcome",
    "spending_allowed",
    "status",
    "witness_id",
}
EXPECTED_SURFACE_KEYS = {
    "evidence_ref",
    "public_safe_note",
    "state",
    "surface_id",
    "surface_type",
}
REQUIRED_DOC_PHRASES = (
    "Foundation Deployment Deferral Boundary",
    "Witness packet: [`../examples/foundation_deployment_deferral_witness.awaiting_evidence.json`]",
    "Rule: Deployment deferral is a local planning boundary, not a deployment plan, production-health certificate, customer-access approval, spending approval, credential-use approval, publication approval, or readiness certificate.",
    "No deployment plan approval, cloud activation, public endpoint, production",
    "deployment_deferral_boundary_state=AwaitingEvidence",
    "deployment_plan_approved=false",
    "cloud_activation_allowed=false",
    "public_endpoint_allowed=false",
    "deployment_allowed=false",
    "python scripts/validate_foundation_deployment_deferral_boundary.py",
)
FORBIDDEN_VALUE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("url_value", re.compile(r"https?://", re.IGNORECASE)),
    ("email_value", re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)),
    ("private_path", re.compile(r"\b[A-Za-z]:[\\/]|\\\\", re.IGNORECASE)),
    ("host_port_value", re.compile(r"\b(?:localhost|127\.0\.0\.1|0\.0\.0\.0|::1):\d{2,5}\b", re.IGNORECASE)),
    ("dns_target_assignment", re.compile(r"\b(?:dns|domain|route|host|endpoint)[_ -]?(?:target|value|url|uri|ref)?\s*=", re.IGNORECASE)),
    ("provider_assignment", re.compile(r"\b(?:provider|account|tenant|project|region|cluster)[_ -]?(?:id|ref|target|value)?\s*=", re.IGNORECASE)),
    ("billing_assignment", re.compile(r"\b(?:billing|payment|card|invoice|subscription)[_ -]?(?:id|ref|target|value)?\s*=", re.IGNORECASE)),
    ("customer_assignment", re.compile(r"\b(?:customer|pilot|tenant|user)[_ -]?(?:id|email|name|ref|value)?\s*=", re.IGNORECASE)),
    ("schedule_assignment", re.compile(r"\b(?:deadline|launch|deploy|schedule|date)[_ -]?(?:at|date|time|value)?\s*=", re.IGNORECASE)),
    ("secret_assignment", re.compile(r"\b(?:password|secret|token|api[_ -]?key|credential)\s*=", re.IGNORECASE)),
)
FORBIDDEN_PROMOTION_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("deployment_ready", re.compile(r"\bdeployment\s+(?:is\s+)?ready\b", re.IGNORECASE)),
    ("deployment_approved", re.compile(r"\bdeployment\s+(?:is\s+)?approved\b", re.IGNORECASE)),
    ("deployment_scheduled", re.compile(r"\bdeployment\s+(?:is\s+)?scheduled\b", re.IGNORECASE)),
    ("cloud_active", re.compile(r"\bcloud\s+(?:is\s+)?(?:active|enabled|ready)\b", re.IGNORECASE)),
    ("public_endpoint_live", re.compile(r"\bpublic\s+endpoint\s+(?:is\s+)?(?:live|published|ready|reachable)\b", re.IGNORECASE)),
    ("production_healthy", re.compile(r"\bproduction\s+(?:is\s+)?(?:healthy|ready|live)\b", re.IGNORECASE)),
    ("runtime_ready", re.compile(r"\bruntime\s+(?:is\s+)?ready\b", re.IGNORECASE)),
    ("customer_access_open", re.compile(r"\bcustomer\s+access\s+(?:is\s+)?open\b", re.IGNORECASE)),
    ("paid_launch_ready", re.compile(r"\bpaid\s+launch\s+(?:is\s+)?ready\b", re.IGNORECASE)),
    ("externally_published", re.compile(r"\bexternally\s+published\b", re.IGNORECASE)),
)


@dataclass(frozen=True, slots=True)
class DeploymentDeferralFinding:
    """One deterministic deployment-deferral boundary validation finding."""

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


def validate_doc_text(text: str) -> list[DeploymentDeferralFinding]:
    """Return findings for missing deployment-deferral documentation anchors."""

    findings: list[DeploymentDeferralFinding] = []
    for phrase in REQUIRED_DOC_PHRASES:
        if phrase not in text:
            findings.append(
                DeploymentDeferralFinding(
                    "foundation_deployment_deferral_doc_phrase_missing",
                    f"deployment-deferral boundary doc missing required phrase: {phrase}",
                )
            )
    return findings


def validate_packet(payload: dict[str, Any]) -> list[DeploymentDeferralFinding]:
    """Return findings for deployment-deferral witness drift."""

    findings: list[DeploymentDeferralFinding] = []
    findings.extend(validate_root_contract(payload))
    findings.extend(validate_deployment_deferral_surfaces(payload.get("deployment_deferral_surfaces")))
    findings.extend(validate_forbidden_value_patterns(payload))
    findings.extend(validate_forbidden_promotion_patterns(payload))
    return findings


def validate_root_contract(payload: dict[str, Any]) -> list[DeploymentDeferralFinding]:
    """Return findings for root-level deployment-deferral witness drift."""

    findings: list[DeploymentDeferralFinding] = []
    if set(payload) != EXPECTED_ROOT_KEYS:
        findings.append(
            DeploymentDeferralFinding(
                "deployment_deferral_root_keys_invalid",
                f"root keys must be: {', '.join(sorted(EXPECTED_ROOT_KEYS))}",
            )
        )
    expected_values = {
        "witness_id": EXPECTED_WITNESS_ID,
        "schema_version": 1,
        "status": "AwaitingEvidence",
        "solver_outcome": "AwaitingEvidence",
        "deployment_plan_approved": False,
        "cloud_activation_allowed": False,
        "public_endpoint_allowed": False,
        "production_health_claimed": False,
        "runtime_readiness_claimed": False,
        "customer_access_allowed": False,
        "spending_allowed": False,
        "credential_use_allowed": False,
        "secret_use_allowed": False,
        "migration_execution_allowed": False,
        "dns_mutation_allowed": False,
        "external_publication_allowed": False,
        "deployment_allowed": False,
    }
    for key, expected_value in expected_values.items():
        if payload.get(key) != expected_value:
            findings.append(
                DeploymentDeferralFinding(
                    "deployment_deferral_root_value_invalid",
                    f"{key} must be {expected_value!r}",
                )
            )
    if tuple(payload.get("blocked_claims") or ()) != EXPECTED_BLOCKED_CLAIMS:
        findings.append(
            DeploymentDeferralFinding(
                "deployment_deferral_blocked_claims_invalid",
                f"blocked_claims must be: {', '.join(EXPECTED_BLOCKED_CLAIMS)}",
            )
        )
    next_action = payload.get("next_action")
    if not isinstance(next_action, str) or "keep deployment deferred" not in next_action:
        findings.append(
            DeploymentDeferralFinding(
                "deployment_deferral_next_action_invalid",
                "next_action must preserve the deployment deferral boundary",
            )
        )
    return findings


def validate_deployment_deferral_surfaces(
    deployment_deferral_surfaces: object,
) -> list[DeploymentDeferralFinding]:
    """Return findings for deployment-deferral surface witness drift."""

    findings: list[DeploymentDeferralFinding] = []
    if not isinstance(deployment_deferral_surfaces, list) or not all(
        isinstance(surface, dict) for surface in deployment_deferral_surfaces
    ):
        return [
            DeploymentDeferralFinding(
                "deployment_deferral_surfaces_invalid",
                "deployment_deferral_surfaces must be a list of objects",
            )
        ]
    observed_surfaces = tuple(
        (surface.get("surface_id"), surface.get("surface_type"), surface.get("state"))
        for surface in deployment_deferral_surfaces
    )
    if observed_surfaces != EXPECTED_SURFACES:
        findings.append(
            DeploymentDeferralFinding(
                "deployment_deferral_surface_inventory_invalid",
                "deployment-deferral surface inventory does not match the Foundation Mode deployment set",
            )
        )
    surface_ids = [surface.get("surface_id") for surface in deployment_deferral_surfaces]
    if len(set(surface_ids)) != len(surface_ids):
        findings.append(DeploymentDeferralFinding("deployment_deferral_surface_duplicate", "surface ids must be unique"))
    for surface in deployment_deferral_surfaces:
        surface_id = str(surface.get("surface_id", "<missing>"))
        if set(surface) != EXPECTED_SURFACE_KEYS:
            findings.append(
                DeploymentDeferralFinding(
                    "deployment_deferral_surface_keys_invalid",
                    f"{surface_id} surface keys must be: {', '.join(sorted(EXPECTED_SURFACE_KEYS))}",
                )
            )
        if surface.get("state") != "AwaitingEvidence":
            findings.append(
                DeploymentDeferralFinding(
                    "deployment_deferral_surface_state_invalid",
                    f"{surface_id} state must be AwaitingEvidence",
                )
            )
        if surface.get("evidence_ref") != "manual_preparation_pending":
            findings.append(
                DeploymentDeferralFinding(
                    "deployment_deferral_surface_evidence_invalid",
                    f"{surface_id} evidence_ref must stay manual_preparation_pending in the committed packet",
                )
            )
        if not isinstance(surface.get("public_safe_note"), str) or not surface["public_safe_note"].strip():
            findings.append(
                DeploymentDeferralFinding(
                    "deployment_deferral_surface_note_invalid",
                    f"{surface_id} public_safe_note must be a non-empty string",
                )
            )
    return findings


def validate_forbidden_value_patterns(payload: dict[str, Any]) -> list[DeploymentDeferralFinding]:
    """Return findings for endpoint, provider, customer, schedule, billing, path, or secret-shaped values."""

    serialized_payload = json.dumps(payload, sort_keys=True)
    findings: list[DeploymentDeferralFinding] = []
    for rule_id, pattern in FORBIDDEN_VALUE_PATTERNS:
        if pattern.search(serialized_payload):
            findings.append(
                DeploymentDeferralFinding(
                    "deployment_deferral_forbidden_private_value_pattern",
                    f"deployment-deferral witness contains forbidden value pattern: {rule_id}",
                )
            )
    return findings


def validate_forbidden_promotion_patterns(payload: dict[str, Any]) -> list[DeploymentDeferralFinding]:
    """Return findings if the witness drifts into deployment readiness or exposure claims."""

    serialized_payload = json.dumps(payload, sort_keys=True)
    findings: list[DeploymentDeferralFinding] = []
    for rule_id, pattern in FORBIDDEN_PROMOTION_PATTERNS:
        if pattern.search(serialized_payload):
            findings.append(
                DeploymentDeferralFinding(
                    "deployment_deferral_forbidden_promotion_phrase",
                    f"deployment-deferral witness contains forbidden promotion pattern: {rule_id}",
                )
            )
    return findings


def validate_foundation_deployment_deferral_boundary(
    doc_path: Path = DEFAULT_DOC_PATH,
    packet_path: Path = DEFAULT_PACKET_PATH,
) -> list[DeploymentDeferralFinding]:
    """Validate the Foundation Mode deployment-deferral boundary artifacts."""

    doc_text = load_text(doc_path, "deployment-deferral boundary doc")
    packet_payload = load_json_object(packet_path, "deployment-deferral witness packet")
    return [
        *validate_doc_text(doc_text),
        *validate_packet(packet_payload),
    ]


def main(argv: list[str] | None = None) -> int:
    """Validate deployment-deferral boundary artifacts and print deterministic status."""

    parser = argparse.ArgumentParser(description="Validate Foundation Mode deployment-deferral boundary artifacts.")
    parser.add_argument("--doc", type=Path, default=DEFAULT_DOC_PATH)
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET_PATH)
    args = parser.parse_args(argv)

    try:
        findings = validate_foundation_deployment_deferral_boundary(args.doc, args.packet)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"[FAIL] foundation_deployment_deferral_load: {exc}", file=sys.stderr)
        print("STATUS: failed", file=sys.stderr)
        return 1

    if findings:
        for finding in findings:
            print(f"[FAIL] {finding.rule_id}: {finding.message}", file=sys.stderr)
        print("STATUS: failed", file=sys.stderr)
        return 1
    print("[PASS] foundation_deployment_deferral_doc")
    print("[PASS] foundation_deployment_deferral_witness")
    print("STATUS: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
