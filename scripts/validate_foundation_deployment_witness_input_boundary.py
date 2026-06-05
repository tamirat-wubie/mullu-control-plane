#!/usr/bin/env python3
"""Validate the Foundation Mode deployment witness input boundary.

Purpose: keep issue #330 deployment witness input preparation local and
public-safe while live values, repository variable binding, DNS mutation,
endpoint readiness claims, workflow dispatch, artifact publication, deployment
status promotion, customer access, personal data, money movement,
legal/business claims, publication, and deployment remain blocked.
Governance scope: Foundation Mode, issue #330 input inventory, public-safe
secret and variable names, endpoint contract labels, external-action blocking,
secret exclusion, customer/data blocking, money blocking, legal/business
restraint, publication blocking, and deployment blocking.
Dependencies: docs/FOUNDATION_DEPLOYMENT_WITNESS_INPUT_BOUNDARY.md and
examples/foundation_deployment_witness_input_witness.awaiting_evidence.json.
Invariants:
  - Validation is read-only.
  - The witness records public-safe input names and endpoint labels only.
  - No live URL, environment value, secret value, repository variable value,
    DNS mutation, endpoint reachability, workflow dispatch, artifact
    publication, deployment status promotion, customer access, personal data,
    money movement, legal clearance, company formation, patent claim,
    external publication, or deployment claim is allowed.
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
DEFAULT_DOC_PATH = REPO_ROOT / "docs" / "FOUNDATION_DEPLOYMENT_WITNESS_INPUT_BOUNDARY.md"
DEFAULT_PACKET_PATH = REPO_ROOT / "examples" / "foundation_deployment_witness_input_witness.awaiting_evidence.json"

EXPECTED_WITNESS_ID = "foundation_deployment_witness_input_witness.awaiting_evidence.v1"
EXPECTED_PUBLIC_SAFE_NAMES = (
    "MULLU_RUNTIME_WITNESS_SECRET",
    "MULLU_RUNTIME_CONFORMANCE_SECRET",
    "MULLU_GATEWAY_URL",
    "MULLU_EXPECTED_RUNTIME_ENV",
)
EXPECTED_ENDPOINT_LABELS = (
    "/health",
    "/gateway/witness",
    "/runtime/conformance",
)
EXPECTED_BLOCKED_CLAIMS = (
    "secret value",
    "repository variable value",
    "dns mutation",
    "endpoint reachability",
    "workflow dispatch",
    "witness artifact publication",
    "deployment status promotion",
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
    "record public-safe input names only; do not collect secret values, bind "
    "repository variables, mutate DNS, claim endpoint reachability, dispatch "
    "workflows, publish witness artifacts, promote deployment status, open "
    "customer access, collect personal data, move money, claim legal clearance, "
    "form a company, claim patent protection, publish externally, or deploy"
)
EXPECTED_SURFACES = (
    ("runtime_witness_secret_name", "public_safe_name", "AwaitingEvidence"),
    ("runtime_conformance_secret_name", "public_safe_name", "AwaitingEvidence"),
    ("gateway_url_variable_name", "public_safe_name", "AwaitingEvidence"),
    ("expected_runtime_env_variable_name", "public_safe_name", "AwaitingEvidence"),
    ("health_endpoint_contract", "endpoint_contract", "AwaitingEvidence"),
    ("gateway_witness_endpoint_contract", "endpoint_contract", "AwaitingEvidence"),
    ("runtime_conformance_endpoint_contract", "endpoint_contract", "AwaitingEvidence"),
    ("repository_variable_binding_gate", "blocked_gate", "AwaitingEvidence"),
    ("workflow_dispatch_gate", "blocked_gate", "AwaitingEvidence"),
    ("artifact_publication_gate", "blocked_gate", "AwaitingEvidence"),
    ("deployment_status_claim_gate", "blocked_gate", "AwaitingEvidence"),
    ("operator_handoff", "blocked_gate", "AwaitingEvidence"),
)
EXPECTED_SURFACE_NOTES = {
    "runtime_witness_secret_name": (
        "Runtime witness secret name only; the secret value remains outside "
        "Git and is not collected."
    ),
    "runtime_conformance_secret_name": (
        "Runtime conformance secret name only; the secret value remains outside "
        "Git and is not collected."
    ),
    "gateway_url_variable_name": (
        "Gateway URL variable name only; the live gateway URL value remains "
        "unavailable."
    ),
    "expected_runtime_env_variable_name": (
        "Expected runtime environment variable name only; no live environment "
        "value is selected or bound."
    ),
    "health_endpoint_contract": (
        "Health endpoint path contract only; endpoint reachability and public "
        "health are not claimed."
    ),
    "gateway_witness_endpoint_contract": (
        "Gateway witness endpoint path contract only; witness fields, HMAC pass, "
        "and artifact publication are not claimed."
    ),
    "runtime_conformance_endpoint_contract": (
        "Runtime conformance endpoint path contract only; conformance fields and "
        "HMAC pass are not claimed."
    ),
    "repository_variable_binding_gate": (
        "Repository variable binding gate only; no repository variable is "
        "created, updated, or verified."
    ),
    "workflow_dispatch_gate": (
        "Workflow dispatch gate only; deployment witness and gateway publication "
        "workflows are not dispatched."
    ),
    "artifact_publication_gate": (
        "Artifact publication gate only; published deployment witness artifacts "
        "and promotion remain blocked."
    ),
    "deployment_status_claim_gate": (
        "Deployment status claim gate only; deployment status is not promoted to "
        "healthy or published."
    ),
    "operator_handoff": (
        "Operator handoff only; live DNS, runtime, provider, money, secret, "
        "legal, publication, and deployment action remain external."
    ),
}
EXPECTED_DOC_SURFACE_LABELS = (
    "Runtime witness secret name",
    "Runtime conformance secret name",
    "Gateway URL variable name",
    "Expected runtime environment variable name",
    "Health endpoint contract",
    "Gateway witness endpoint contract",
    "Runtime conformance endpoint contract",
    "Repository variable binding gate",
    "Workflow dispatch gate",
    "Artifact publication gate",
    "Deployment status claim gate",
    "Operator handoff",
)
EXPECTED_ROOT_KEYS = {
    "blocked_claims",
    "company_formation_claimed",
    "customer_access_allowed",
    "deployment_allowed",
    "deployment_status_promotion_allowed",
    "dns_mutation_allowed",
    "endpoint_labels",
    "endpoint_reachability_claimed",
    "expected_runtime_env_value_allowed",
    "external_publication_allowed",
    "gateway_url_value_allowed",
    "legal_clearance_claimed",
    "money_movement_allowed",
    "next_action",
    "patent_claimed",
    "personal_data_collection_allowed",
    "public_safe_names",
    "repository_variable_binding_allowed",
    "runtime_conformance_secret_value_allowed",
    "runtime_witness_secret_value_allowed",
    "schema_version",
    "solver_outcome",
    "status",
    "surfaces",
    "witness_artifact_publication_allowed",
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
    "Foundation Deployment Witness Input Boundary",
    "Witness packet: [`../examples/foundation_deployment_witness_input_witness.awaiting_evidence.json`]",
    "Rule: Deployment witness inputs are local placeholders only.",
    "No secret value, repository variable value, DNS mutation",
    "deployment_witness_input_state=AwaitingEvidence",
    "runtime_witness_secret_value_allowed=false",
    "runtime_conformance_secret_value_allowed=false",
    "gateway_url_value_allowed=false",
    "expected_runtime_env_value_allowed=false",
    "repository_variable_binding_allowed=false",
    "dns_mutation_allowed=false",
    "endpoint_reachability_claimed=false",
    "workflow_dispatch_allowed=false",
    "witness_artifact_publication_allowed=false",
    "deployment_status_promotion_allowed=false",
    "customer_access_allowed=false",
    "personal_data_collection_allowed=false",
    "money_movement_allowed=false",
    "legal_clearance_claimed=false",
    "company_formation_claimed=false",
    "patent_claimed=false",
    "external_publication_allowed=false",
    "deployment_allowed=false",
    "python scripts/validate_foundation_deployment_witness_input_boundary.py",
)
FORBIDDEN_VALUE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("url_value", re.compile(r"https?://", re.IGNORECASE)),
    ("email_value", re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)),
    ("private_path", re.compile(r"\b[A-Za-z]:[\\/]|\\\\", re.IGNORECASE)),
    ("private_key_block", re.compile(r"-----BEGIN\s+(?:RSA\s+|EC\s+|OPENSSH\s+)?PRIVATE\s+KEY-----", re.IGNORECASE)),
    (
        "live_assignment",
        re.compile(
            r"\b(?:secret|token|api[_ -]?key|client[_ -]?secret|password|"
            r"credential|gateway|url|dns|target|host|provider|account|"
            r"repository[_ -]?variable|workflow|run|artifact|deployment|"
            r"environment|env|customer|person|participant|email|payment|"
            r"billing|invoice|legal|company|formation|patent)"
            r"[_ -]?(?:id|name|value|url|target|host|ref|status|text|path|"
            r"list|number)?\s*=",
            re.IGNORECASE,
        ),
    ),
)
FORBIDDEN_PROMOTION_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("secret_value_available", re.compile(r"\bsecret value\s+(?:is\s+)?(?:available|stored|configured|verified)\b", re.IGNORECASE)),
    ("variable_bound", re.compile(r"\brepository variable\s+(?:is\s+)?(?:bound|set|configured|verified)\b", re.IGNORECASE)),
    ("dns_ready", re.compile(r"\bdns\s+(?:is\s+)?(?:ready|verified|published|configured|resolves)\b", re.IGNORECASE)),
    ("endpoint_reachable", re.compile(r"\bendpoint\s+(?:is\s+)?(?:reachable|healthy|ready|verified)\b", re.IGNORECASE)),
    ("workflow_dispatched", re.compile(r"\bworkflow\s+(?:is\s+)?(?:dispatched|run|started|completed)\b", re.IGNORECASE)),
    ("artifact_published", re.compile(r"\bwitness artifact\s+(?:is\s+)?(?:published|ready|verified)\b", re.IGNORECASE)),
    ("status_promoted", re.compile(r"\bdeployment status\s+(?:is\s+)?(?:promoted|healthy|published)\b", re.IGNORECASE)),
    ("deployment_ready", re.compile(r"\bdeployment\s+(?:is\s+)?ready\b", re.IGNORECASE)),
    ("customer_access_ready", re.compile(r"\bcustomer access\s+(?:is\s+)?ready\b", re.IGNORECASE)),
    ("legal_cleared", re.compile(r"\blegal\s+(?:is\s+)?cleared\b", re.IGNORECASE)),
    ("company_formed", re.compile(r"\bcompany\s+(?:is\s+)?formed\b", re.IGNORECASE)),
    ("patent_filed", re.compile(r"\bpatent\s+(?:is\s+)?filed\b", re.IGNORECASE)),
    ("money_movement_allowed", re.compile(r"\bmoney movement\s+(?:is\s+)?allowed\b", re.IGNORECASE)),
    ("external_publication_approved", re.compile(r"\bexternal publication (?:allowed|approved|ready)\b", re.IGNORECASE)),
)


@dataclass(frozen=True, slots=True)
class DeploymentWitnessInputFinding:
    """One deterministic deployment witness input validation finding."""

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


def validate_doc_text(text: str) -> list[DeploymentWitnessInputFinding]:
    """Return findings for missing deployment witness input documentation anchors."""

    findings: list[DeploymentWitnessInputFinding] = []
    for phrase in REQUIRED_DOC_PHRASES:
        if phrase not in text:
            findings.append(
                DeploymentWitnessInputFinding(
                    "foundation_deployment_witness_input_doc_phrase_missing",
                    f"deployment witness input boundary doc missing required phrase: {phrase}",
                )
            )
    for public_safe_name in EXPECTED_PUBLIC_SAFE_NAMES:
        if public_safe_name not in text:
            findings.append(
                DeploymentWitnessInputFinding(
                    "foundation_deployment_witness_input_doc_name_missing",
                    f"deployment witness input boundary doc missing public-safe name: {public_safe_name}",
                )
            )
    for endpoint_label in EXPECTED_ENDPOINT_LABELS:
        if endpoint_label not in text:
            findings.append(
                DeploymentWitnessInputFinding(
                    "foundation_deployment_witness_input_doc_endpoint_missing",
                    f"deployment witness input boundary doc missing endpoint label: {endpoint_label}",
                )
            )
    for surface_label in EXPECTED_DOC_SURFACE_LABELS:
        if surface_label not in text:
            findings.append(
                DeploymentWitnessInputFinding(
                    "foundation_deployment_witness_input_doc_surface_missing",
                    f"deployment witness input boundary doc missing surface label: {surface_label}",
                )
            )
    findings.extend(validate_forbidden_value_patterns(text, "doc"))
    findings.extend(validate_forbidden_promotion_patterns(text, "doc"))
    return findings


def validate_packet(payload: dict[str, Any]) -> list[DeploymentWitnessInputFinding]:
    """Return findings for deployment witness input witness drift."""

    findings: list[DeploymentWitnessInputFinding] = []
    findings.extend(validate_root_contract(payload))
    findings.extend(validate_surfaces(payload.get("surfaces")))
    findings.extend(validate_forbidden_value_patterns(payload, "witness"))
    findings.extend(validate_forbidden_promotion_patterns(payload, "witness"))
    return findings


def validate_root_contract(payload: dict[str, Any]) -> list[DeploymentWitnessInputFinding]:
    """Return findings for root-level deployment witness input witness drift."""

    findings: list[DeploymentWitnessInputFinding] = []
    if set(payload) != EXPECTED_ROOT_KEYS:
        findings.append(
            DeploymentWitnessInputFinding(
                "deployment_witness_input_root_keys_invalid",
                f"root keys must be: {', '.join(sorted(EXPECTED_ROOT_KEYS))}",
            )
        )
    expected_values = {
        "witness_id": EXPECTED_WITNESS_ID,
        "schema_version": 1,
        "status": "AwaitingEvidence",
        "solver_outcome": "AwaitingEvidence",
        "runtime_witness_secret_value_allowed": False,
        "runtime_conformance_secret_value_allowed": False,
        "gateway_url_value_allowed": False,
        "expected_runtime_env_value_allowed": False,
        "repository_variable_binding_allowed": False,
        "dns_mutation_allowed": False,
        "endpoint_reachability_claimed": False,
        "workflow_dispatch_allowed": False,
        "witness_artifact_publication_allowed": False,
        "deployment_status_promotion_allowed": False,
        "customer_access_allowed": False,
        "personal_data_collection_allowed": False,
        "money_movement_allowed": False,
        "legal_clearance_claimed": False,
        "company_formation_claimed": False,
        "patent_claimed": False,
        "external_publication_allowed": False,
        "deployment_allowed": False,
    }
    for key, expected_value in expected_values.items():
        if payload.get(key) != expected_value:
            findings.append(
                DeploymentWitnessInputFinding(
                    "deployment_witness_input_root_value_invalid",
                    f"{key} must be {expected_value!r}",
                )
            )
    if tuple(payload.get("blocked_claims") or ()) != EXPECTED_BLOCKED_CLAIMS:
        findings.append(
            DeploymentWitnessInputFinding(
                "deployment_witness_input_blocked_claims_invalid",
                f"blocked_claims must be: {', '.join(EXPECTED_BLOCKED_CLAIMS)}",
            )
        )
    if tuple(payload.get("public_safe_names") or ()) != EXPECTED_PUBLIC_SAFE_NAMES:
        findings.append(
            DeploymentWitnessInputFinding(
                "deployment_witness_input_public_safe_names_invalid",
                f"public_safe_names must be: {', '.join(EXPECTED_PUBLIC_SAFE_NAMES)}",
            )
        )
    if tuple(payload.get("endpoint_labels") or ()) != EXPECTED_ENDPOINT_LABELS:
        findings.append(
            DeploymentWitnessInputFinding(
                "deployment_witness_input_endpoint_labels_invalid",
                f"endpoint_labels must be: {', '.join(EXPECTED_ENDPOINT_LABELS)}",
            )
        )
    if payload.get("next_action") != EXPECTED_NEXT_ACTION:
        findings.append(
            DeploymentWitnessInputFinding(
                "deployment_witness_input_next_action_invalid",
                "next_action must preserve the exact public-safe non-promotion handoff",
            )
        )
    return findings


def validate_surfaces(surfaces: object) -> list[DeploymentWitnessInputFinding]:
    """Return findings for deployment witness input surface witness drift."""

    findings: list[DeploymentWitnessInputFinding] = []
    if not isinstance(surfaces, list) or not all(isinstance(surface, dict) for surface in surfaces):
        return [DeploymentWitnessInputFinding("deployment_witness_input_surfaces_invalid", "surfaces must be a list")]
    observed_surfaces = tuple(
        (surface.get("surface_id"), surface.get("surface_type"), surface.get("state"))
        for surface in surfaces
    )
    if observed_surfaces != EXPECTED_SURFACES:
        findings.append(
            DeploymentWitnessInputFinding(
                "deployment_witness_input_surface_inventory_invalid",
                "deployment witness input surface inventory does not match the expected set",
            )
        )
    surface_ids = [surface.get("surface_id") for surface in surfaces]
    if len(set(surface_ids)) != len(surface_ids):
        findings.append(DeploymentWitnessInputFinding("deployment_witness_input_surface_duplicate", "surface ids must be unique"))
    for surface in surfaces:
        surface_id = str(surface.get("surface_id", "<missing>"))
        if set(surface) != EXPECTED_SURFACE_KEYS:
            findings.append(
                DeploymentWitnessInputFinding(
                    "deployment_witness_input_surface_keys_invalid",
                    f"{surface_id} surface keys must be: {', '.join(sorted(EXPECTED_SURFACE_KEYS))}",
                )
            )
        if surface.get("state") != "AwaitingEvidence":
            findings.append(
                DeploymentWitnessInputFinding(
                    "deployment_witness_input_surface_state_invalid",
                    f"{surface_id} state must be AwaitingEvidence",
                )
            )
        if surface.get("evidence_ref") != "manual_preparation_pending":
            findings.append(
                DeploymentWitnessInputFinding(
                    "deployment_witness_input_surface_evidence_invalid",
                    f"{surface_id} evidence_ref must stay manual_preparation_pending",
                )
            )
        if not isinstance(surface.get("public_safe_note"), str) or not surface["public_safe_note"].strip():
            findings.append(
                DeploymentWitnessInputFinding(
                    "deployment_witness_input_surface_note_invalid",
                    f"{surface_id} public_safe_note must be a non-empty string",
                )
            )
        elif surface.get("public_safe_note") != EXPECTED_SURFACE_NOTES.get(surface_id):
            findings.append(
                DeploymentWitnessInputFinding(
                    "deployment_witness_input_surface_note_invalid",
                    f"{surface_id} public_safe_note must preserve the expected public-safe boundary text",
                )
            )
    return findings


def serialize_for_pattern_scan(value: str | dict[str, Any]) -> str:
    """Return deterministic text for forbidden-pattern validation."""

    if isinstance(value, str):
        return value
    return json.dumps(value, sort_keys=True)


def validate_forbidden_value_patterns(
    value: str | dict[str, Any],
    artifact_label: str,
) -> list[DeploymentWitnessInputFinding]:
    """Return findings for live value, private path, or external-action shaped values."""

    serialized_value = serialize_for_pattern_scan(value)
    findings: list[DeploymentWitnessInputFinding] = []
    for rule_id, pattern in FORBIDDEN_VALUE_PATTERNS:
        if pattern.search(serialized_value):
            findings.append(
                DeploymentWitnessInputFinding(
                    "deployment_witness_input_forbidden_value_pattern",
                    f"deployment witness input {artifact_label} contains forbidden value pattern: {rule_id}",
                )
            )
    return findings


def validate_forbidden_promotion_patterns(
    value: str | dict[str, Any],
    artifact_label: str,
) -> list[DeploymentWitnessInputFinding]:
    """Return findings if the witness drifts into readiness or publication claims."""

    serialized_value = serialize_for_pattern_scan(value)
    findings: list[DeploymentWitnessInputFinding] = []
    for rule_id, pattern in FORBIDDEN_PROMOTION_PATTERNS:
        if pattern.search(serialized_value):
            findings.append(
                DeploymentWitnessInputFinding(
                    "deployment_witness_input_forbidden_promotion_phrase",
                    f"deployment witness input {artifact_label} contains forbidden promotion pattern: {rule_id}",
                )
            )
    return findings


def validate_foundation_deployment_witness_input_boundary(
    doc_path: Path = DEFAULT_DOC_PATH,
    packet_path: Path = DEFAULT_PACKET_PATH,
) -> list[DeploymentWitnessInputFinding]:
    """Validate the Foundation Mode deployment witness input boundary artifacts."""

    doc_text = load_text(doc_path, "deployment witness input boundary doc")
    packet_payload = load_json_object(packet_path, "deployment witness input witness packet")
    return [
        *validate_doc_text(doc_text),
        *validate_packet(packet_payload),
    ]


def main(argv: list[str] | None = None) -> int:
    """Validate deployment witness input artifacts and print deterministic status."""

    parser = argparse.ArgumentParser(description="Validate Foundation Mode deployment witness input boundary artifacts.")
    parser.add_argument("--doc", type=Path, default=DEFAULT_DOC_PATH)
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET_PATH)
    args = parser.parse_args(argv)

    try:
        findings = validate_foundation_deployment_witness_input_boundary(args.doc, args.packet)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"[FAIL] foundation_deployment_witness_input_load: {exc}", file=sys.stderr)
        print("STATUS: failed", file=sys.stderr)
        return 1

    if findings:
        for finding in findings:
            print(f"[FAIL] {finding.rule_id}: {finding.message}", file=sys.stderr)
        print("STATUS: failed", file=sys.stderr)
        return 1
    print("[PASS] foundation_deployment_witness_input_doc")
    print("[PASS] foundation_deployment_witness_input_witness")
    print("STATUS: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
