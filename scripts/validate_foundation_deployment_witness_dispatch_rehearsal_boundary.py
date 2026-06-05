#!/usr/bin/env python3
"""Validate the Foundation Mode deployment witness dispatch rehearsal boundary.

Purpose: keep issue #330 manual workflow dispatch preparation local and
public-safe while workflow dispatch, GitHub mutation, live gateway URL values,
expected-environment values, workflow refs, run ids, dispatch receipts, secret
handling, repository variable binding, artifact publication, deployment claim
publication, deployment status promotion, operator approval, customer access,
personal data, money movement, legal/business claims, publication, and
deployment remain blocked.
Governance scope: Foundation Mode, issue #330 dispatch rehearsal, public-safe
dispatch labels, external-action blocking, secret exclusion, customer/data
blocking, money blocking, legal/business restraint, publication blocking, and
deployment blocking.
Dependencies: docs/FOUNDATION_DEPLOYMENT_WITNESS_DISPATCH_REHEARSAL_BOUNDARY.md
and examples/foundation_deployment_witness_dispatch_rehearsal_witness.awaiting_evidence.json.
Invariants:
  - Validation is read-only.
  - The witness records public-safe dispatch labels and blocked gates only.
  - No workflow dispatch, GitHub API mutation, manual workflow execution, live
    gateway URL value, expected-environment value, workflow ref value, workflow
    run id, dispatch receipt, secret value, secret presence claim, repository
    variable binding, workflow run claim, artifact publication, deployment
    claim publication, deployment status promotion, operator approval, customer
    access, personal data, money movement, legal clearance, company formation,
    patent claim, external publication, or deployment claim is allowed.
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
DEFAULT_DOC_PATH = REPO_ROOT / "docs" / "FOUNDATION_DEPLOYMENT_WITNESS_DISPATCH_REHEARSAL_BOUNDARY.md"
DEFAULT_PACKET_PATH = (
    REPO_ROOT / "examples" / "foundation_deployment_witness_dispatch_rehearsal_witness.awaiting_evidence.json"
)

EXPECTED_WITNESS_ID = "foundation_deployment_witness_dispatch_rehearsal_witness.awaiting_evidence.v1"
EXPECTED_DISPATCH_LABELS = (
    "scripts/dispatch_deployment_witness.py",
    ".github/workflows/deployment-witness.yml",
    "Deployment Witness Collection",
    "gateway_url",
    "expected_environment",
    "MULLU_GATEWAY_URL",
    "MULLU_EXPECTED_RUNTIME_ENV",
    "schemas/deployment_witness.schema.json",
    "scripts/validate_deployment_publication_closure.py",
)
EXPECTED_BLOCKED_CLAIMS = (
    "workflow dispatch",
    "GitHub API mutation",
    "manual workflow execution",
    "live gateway url value",
    "expected environment value",
    "workflow ref value",
    "workflow run id",
    "dispatch receipt",
    "secret value",
    "secret presence claim",
    "repository variable binding",
    "workflow run claim",
    "artifact publication",
    "deployment claim published",
    "deployment status promotion",
    "operator approval",
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
    "record public-safe dispatch labels only; do not dispatch workflows, "
    "mutate GitHub state, run manual workflow execution, record live gateway "
    "URL values, record expected-environment values, record workflow refs, "
    "record workflow run ids, record dispatch receipts, handle secret values, "
    "claim secret presence, bind repository variables, claim workflow runs, "
    "publish artifacts, claim deployment_claim: published, promote deployment "
    "status, claim operator approval, open customer access, collect personal "
    "data, move money, claim legal clearance, form a company, claim patent "
    "protection, publish externally, or deploy"
)
EXPECTED_SURFACES = (
    ("preflight_dependency_label", "dispatch_rehearsal_label", "AwaitingEvidence"),
    ("workflow_file_label", "dispatch_rehearsal_label", "AwaitingEvidence"),
    ("workflow_name_label", "dispatch_rehearsal_label", "AwaitingEvidence"),
    ("gateway_url_input_label", "dispatch_rehearsal_label", "AwaitingEvidence"),
    ("expected_environment_input_label", "dispatch_rehearsal_label", "AwaitingEvidence"),
    ("repository_variable_dependency_label", "blocked_external_dependency", "AwaitingEvidence"),
    ("secret_dependency_label", "blocked_external_dependency", "AwaitingEvidence"),
    ("manual_dispatch_command_label", "blocked_external_action", "AwaitingEvidence"),
    ("dispatch_receipt_slot", "blocked_external_evidence", "AwaitingEvidence"),
    ("workflow_run_receipt_slot", "blocked_external_evidence", "AwaitingEvidence"),
    ("artifact_validation_dependency_label", "blocked_external_evidence", "AwaitingEvidence"),
    ("deployment_claim_publication_gate", "blocked_promotion_gate", "AwaitingEvidence"),
    ("operator_reassessment_gate", "blocked_promotion_gate", "AwaitingEvidence"),
)
EXPECTED_SURFACE_NOTES = {
    "preflight_dependency_label": "Preflight dependency label only; preflight pass is not claimed.",
    "workflow_file_label": "Workflow file label only; GitHub workflow APIs are not called.",
    "workflow_name_label": "Workflow name label only; workflow lookup and execution are not claimed.",
    "gateway_url_input_label": "Gateway URL input label only; live gateway URL values are not recorded.",
    "expected_environment_input_label": (
        "Expected environment input label only; environment values are not recorded."
    ),
    "repository_variable_dependency_label": (
        "Repository variable dependency label only; variables are not bound, verified, or updated."
    ),
    "secret_dependency_label": "Secret dependency label only; secret values and presence claims remain external.",
    "manual_dispatch_command_label": "Manual dispatch command label only; workflow dispatch is not executed.",
    "dispatch_receipt_slot": "Dispatch receipt slot only; dispatch receipts are not recorded.",
    "workflow_run_receipt_slot": (
        "Workflow run receipt slot only; run ids and workflow run claims are not recorded."
    ),
    "artifact_validation_dependency_label": (
        "Artifact validation dependency label only; artifact schema and closure passes are not claimed."
    ),
    "deployment_claim_publication_gate": (
        "Deployment-claim publication gate only; deployment_claim: published is not claimed."
    ),
    "operator_reassessment_gate": (
        "Operator reassessment gate only; operator approval, readiness, publication, and deployment remain blocked."
    ),
}
EXPECTED_DOC_SURFACE_LABELS = (
    "Preflight dependency label",
    "Workflow file label",
    "Workflow name label",
    "Gateway URL input label",
    "Expected environment input label",
    "Repository variable dependency label",
    "Secret dependency label",
    "Manual dispatch command label",
    "Dispatch receipt slot",
    "Workflow run receipt slot",
    "Artifact validation dependency label",
    "Deployment-claim publication gate",
    "Operator reassessment gate",
)
EXPECTED_ROOT_KEYS = {
    "artifact_publication_allowed",
    "blocked_claims",
    "company_formation_claimed",
    "customer_access_allowed",
    "deployment_allowed",
    "deployment_claim_published_claimed",
    "deployment_status_promotion_allowed",
    "dispatch_labels",
    "dispatch_receipt_recorded",
    "expected_environment_value_recorded",
    "external_publication_allowed",
    "gateway_url_value_allowed",
    "github_api_mutation_allowed",
    "legal_clearance_claimed",
    "manual_workflow_execution_allowed",
    "money_movement_allowed",
    "next_action",
    "operator_approval_claimed",
    "patent_claimed",
    "personal_data_collection_allowed",
    "repository_variable_binding_allowed",
    "schema_version",
    "secret_presence_claimed",
    "secret_value_allowed",
    "solver_outcome",
    "status",
    "surfaces",
    "workflow_dispatch_allowed",
    "workflow_ref_value_recorded",
    "workflow_run_claimed",
    "workflow_run_id_recorded",
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
    "Foundation Deployment Witness Dispatch Rehearsal Boundary",
    "Witness packet: [`../examples/foundation_deployment_witness_dispatch_rehearsal_witness.awaiting_evidence.json`]",
    "Rule: Dispatch rehearsal is a local stop-rule map",
    "No workflow dispatch, GitHub API mutation, manual workflow execution",
    "deployment_witness_dispatch_rehearsal_state=AwaitingEvidence",
    "workflow_dispatch_allowed=false",
    "github_api_mutation_allowed=false",
    "manual_workflow_execution_allowed=false",
    "gateway_url_value_allowed=false",
    "expected_environment_value_recorded=false",
    "workflow_ref_value_recorded=false",
    "workflow_run_id_recorded=false",
    "dispatch_receipt_recorded=false",
    "secret_value_allowed=false",
    "secret_presence_claimed=false",
    "repository_variable_binding_allowed=false",
    "workflow_run_claimed=false",
    "artifact_publication_allowed=false",
    "deployment_claim_published_claimed=false",
    "deployment_status_promotion_allowed=false",
    "operator_approval_claimed=false",
    "customer_access_allowed=false",
    "personal_data_collection_allowed=false",
    "money_movement_allowed=false",
    "legal_clearance_claimed=false",
    "company_formation_claimed=false",
    "patent_claimed=false",
    "external_publication_allowed=false",
    "deployment_allowed=false",
    "python scripts/validate_foundation_deployment_witness_dispatch_rehearsal_boundary.py",
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
            r"billing|invoice|legal|company|formation|patent|approval|"
            r"receipt|evidence|operator|ref)"
            r"[_ -]?(?:id|name|value|url|target|host|ref|status|text|path|"
            r"list|number)?\s*=",
            re.IGNORECASE,
        ),
    ),
)
FORBIDDEN_PROMOTION_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "workflow_dispatched",
        re.compile(r"\bworkflow\s+(?:is\s+)?(?:dispatched|started|completed)\b|\bworkflow\s+is\s+run\b", re.IGNORECASE),
    ),
    ("github_mutated", re.compile(r"\bgithub api mutation\s+(?:is\s+)?(?:done|complete|ready|verified)\b", re.IGNORECASE)),
    ("manual_workflow_run", re.compile(r"\bmanual workflow\s+(?:is\s+)?(?:run|executed|complete)\b", re.IGNORECASE)),
    ("gateway_url_available", re.compile(r"\bgateway url\s+(?:is\s+)?(?:available|set|verified|ready)\b", re.IGNORECASE)),
    ("expected_environment_set", re.compile(r"\bexpected environment\s+(?:is\s+)?(?:set|verified|ready)\b", re.IGNORECASE)),
    ("workflow_ref_recorded", re.compile(r"\bworkflow ref\s+(?:is\s+)?(?:recorded|set|verified)\b", re.IGNORECASE)),
    ("workflow_run_claimed", re.compile(r"\bworkflow run\s+(?:is\s+)?(?:claimed|ready|verified|complete)\b", re.IGNORECASE)),
    ("dispatch_receipt_recorded", re.compile(r"\bdispatch receipt\s+(?:is\s+)?(?:recorded|ready|verified)\b", re.IGNORECASE)),
    ("secret_presence_ready", re.compile(r"\bsecret presence\s+(?:is\s+)?(?:claimed|verified|ready)\b", re.IGNORECASE)),
    ("variable_bound", re.compile(r"\brepository variable\s+(?:is\s+)?(?:bound|set|configured|verified)\b", re.IGNORECASE)),
    ("artifact_published", re.compile(r"\bartifact\s+(?:is\s+)?(?:published|ready|verified|uploaded)\b", re.IGNORECASE)),
    ("deployment_claim_published", re.compile(r"\bdeployment_claim:\s*published\s+(?:claimed|ready|verified)\b", re.IGNORECASE)),
    ("status_promoted", re.compile(r"\bdeployment status\s+(?:is\s+)?(?:promoted|healthy|published)\b", re.IGNORECASE)),
    ("operator_approved", re.compile(r"\boperator approval\s+(?:is\s+)?(?:claimed|ready|verified|complete)\b", re.IGNORECASE)),
    ("deployment_ready", re.compile(r"\bdeployment\s+(?:is\s+)?ready\b", re.IGNORECASE)),
    ("customer_access_ready", re.compile(r"\bcustomer access\s+(?:is\s+)?ready\b", re.IGNORECASE)),
    ("legal_cleared", re.compile(r"\blegal\s+(?:is\s+)?cleared\b", re.IGNORECASE)),
    ("company_formed", re.compile(r"\bcompany\s+(?:is\s+)?formed\b", re.IGNORECASE)),
    ("patent_filed", re.compile(r"\bpatent\s+(?:is\s+)?filed\b", re.IGNORECASE)),
    ("money_movement_allowed", re.compile(r"\bmoney movement\s+(?:is\s+)?allowed\b", re.IGNORECASE)),
    ("external_publication_approved", re.compile(r"\bexternal publication (?:allowed|approved|ready)\b", re.IGNORECASE)),
)


@dataclass(frozen=True, slots=True)
class DeploymentWitnessDispatchRehearsalFinding:
    """One deterministic deployment witness dispatch rehearsal validation finding."""

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


def validate_doc_text(text: str) -> list[DeploymentWitnessDispatchRehearsalFinding]:
    """Return findings for missing deployment witness dispatch rehearsal doc anchors."""

    findings: list[DeploymentWitnessDispatchRehearsalFinding] = []
    for phrase in REQUIRED_DOC_PHRASES:
        if phrase not in text:
            findings.append(
                DeploymentWitnessDispatchRehearsalFinding(
                    "foundation_deployment_witness_dispatch_rehearsal_doc_phrase_missing",
                    f"deployment witness dispatch rehearsal doc missing required phrase: {phrase}",
                )
            )
    for dispatch_label in EXPECTED_DISPATCH_LABELS:
        if dispatch_label not in text:
            findings.append(
                DeploymentWitnessDispatchRehearsalFinding(
                    "foundation_deployment_witness_dispatch_rehearsal_doc_label_missing",
                    f"deployment witness dispatch rehearsal doc missing dispatch label: {dispatch_label}",
                )
            )
    for surface_label in EXPECTED_DOC_SURFACE_LABELS:
        if surface_label not in text:
            findings.append(
                DeploymentWitnessDispatchRehearsalFinding(
                    "foundation_deployment_witness_dispatch_rehearsal_doc_surface_missing",
                    f"deployment witness dispatch rehearsal doc missing surface label: {surface_label}",
                )
            )
    findings.extend(validate_forbidden_value_patterns(text, "doc"))
    findings.extend(validate_forbidden_promotion_patterns(text, "doc"))
    return findings


def validate_packet(payload: dict[str, Any]) -> list[DeploymentWitnessDispatchRehearsalFinding]:
    """Return findings for deployment witness dispatch rehearsal witness drift."""

    findings: list[DeploymentWitnessDispatchRehearsalFinding] = []
    findings.extend(validate_root_contract(payload))
    findings.extend(validate_surfaces(payload.get("surfaces")))
    findings.extend(validate_forbidden_value_patterns(payload, "witness"))
    findings.extend(validate_forbidden_promotion_patterns(payload, "witness"))
    return findings


def validate_root_contract(payload: dict[str, Any]) -> list[DeploymentWitnessDispatchRehearsalFinding]:
    """Return findings for root-level deployment witness dispatch rehearsal drift."""

    findings: list[DeploymentWitnessDispatchRehearsalFinding] = []
    if set(payload) != EXPECTED_ROOT_KEYS:
        findings.append(
            DeploymentWitnessDispatchRehearsalFinding(
                "deployment_witness_dispatch_rehearsal_root_keys_invalid",
                f"root keys must be: {', '.join(sorted(EXPECTED_ROOT_KEYS))}",
            )
        )
    expected_values = {
        "witness_id": EXPECTED_WITNESS_ID,
        "schema_version": 1,
        "status": "AwaitingEvidence",
        "solver_outcome": "AwaitingEvidence",
        "workflow_dispatch_allowed": False,
        "github_api_mutation_allowed": False,
        "manual_workflow_execution_allowed": False,
        "gateway_url_value_allowed": False,
        "expected_environment_value_recorded": False,
        "workflow_ref_value_recorded": False,
        "workflow_run_id_recorded": False,
        "dispatch_receipt_recorded": False,
        "secret_value_allowed": False,
        "secret_presence_claimed": False,
        "repository_variable_binding_allowed": False,
        "workflow_run_claimed": False,
        "artifact_publication_allowed": False,
        "deployment_claim_published_claimed": False,
        "deployment_status_promotion_allowed": False,
        "operator_approval_claimed": False,
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
                DeploymentWitnessDispatchRehearsalFinding(
                    "deployment_witness_dispatch_rehearsal_root_value_invalid",
                    f"{key} must be {expected_value!r}",
                )
            )
    if tuple(payload.get("blocked_claims") or ()) != EXPECTED_BLOCKED_CLAIMS:
        findings.append(
            DeploymentWitnessDispatchRehearsalFinding(
                "deployment_witness_dispatch_rehearsal_blocked_claims_invalid",
                f"blocked_claims must be: {', '.join(EXPECTED_BLOCKED_CLAIMS)}",
            )
        )
    if tuple(payload.get("dispatch_labels") or ()) != EXPECTED_DISPATCH_LABELS:
        findings.append(
            DeploymentWitnessDispatchRehearsalFinding(
                "deployment_witness_dispatch_rehearsal_dispatch_labels_invalid",
                f"dispatch_labels must be: {', '.join(EXPECTED_DISPATCH_LABELS)}",
            )
        )
    if payload.get("next_action") != EXPECTED_NEXT_ACTION:
        findings.append(
            DeploymentWitnessDispatchRehearsalFinding(
                "deployment_witness_dispatch_rehearsal_next_action_invalid",
                "next_action must preserve the exact public-safe non-dispatch handoff",
            )
        )
    return findings


def validate_surfaces(surfaces: object) -> list[DeploymentWitnessDispatchRehearsalFinding]:
    """Return findings for deployment witness dispatch rehearsal surface drift."""

    findings: list[DeploymentWitnessDispatchRehearsalFinding] = []
    if not isinstance(surfaces, list) or not all(isinstance(surface, dict) for surface in surfaces):
        return [
            DeploymentWitnessDispatchRehearsalFinding(
                "deployment_witness_dispatch_rehearsal_surfaces_invalid",
                "surfaces must be a list",
            )
        ]
    observed_surfaces = tuple(
        (surface.get("surface_id"), surface.get("surface_type"), surface.get("state"))
        for surface in surfaces
    )
    if observed_surfaces != EXPECTED_SURFACES:
        findings.append(
            DeploymentWitnessDispatchRehearsalFinding(
                "deployment_witness_dispatch_rehearsal_surface_inventory_invalid",
                "deployment witness dispatch rehearsal surface inventory does not match the expected set",
            )
        )
    surface_ids = [surface.get("surface_id") for surface in surfaces]
    if len(set(surface_ids)) != len(surface_ids):
        findings.append(
            DeploymentWitnessDispatchRehearsalFinding(
                "deployment_witness_dispatch_rehearsal_surface_duplicate",
                "surface ids must be unique",
            )
        )
    for surface in surfaces:
        surface_id = str(surface.get("surface_id", "<missing>"))
        if set(surface) != EXPECTED_SURFACE_KEYS:
            findings.append(
                DeploymentWitnessDispatchRehearsalFinding(
                    "deployment_witness_dispatch_rehearsal_surface_keys_invalid",
                    f"{surface_id} surface keys must be: {', '.join(sorted(EXPECTED_SURFACE_KEYS))}",
                )
            )
        if surface.get("state") != "AwaitingEvidence":
            findings.append(
                DeploymentWitnessDispatchRehearsalFinding(
                    "deployment_witness_dispatch_rehearsal_surface_state_invalid",
                    f"{surface_id} state must be AwaitingEvidence",
                )
            )
        if surface.get("evidence_ref") != "manual_preparation_pending":
            findings.append(
                DeploymentWitnessDispatchRehearsalFinding(
                    "deployment_witness_dispatch_rehearsal_surface_evidence_invalid",
                    f"{surface_id} evidence_ref must stay manual_preparation_pending",
                )
            )
        if not isinstance(surface.get("public_safe_note"), str) or not surface["public_safe_note"].strip():
            findings.append(
                DeploymentWitnessDispatchRehearsalFinding(
                    "deployment_witness_dispatch_rehearsal_surface_note_invalid",
                    f"{surface_id} public_safe_note must be a non-empty string",
                )
            )
        elif surface.get("public_safe_note") != EXPECTED_SURFACE_NOTES.get(surface_id):
            findings.append(
                DeploymentWitnessDispatchRehearsalFinding(
                    "deployment_witness_dispatch_rehearsal_surface_note_invalid",
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
) -> list[DeploymentWitnessDispatchRehearsalFinding]:
    """Return findings for live value, private path, or external-action shaped values."""

    serialized_value = serialize_for_pattern_scan(value)
    findings: list[DeploymentWitnessDispatchRehearsalFinding] = []
    for rule_id, pattern in FORBIDDEN_VALUE_PATTERNS:
        if pattern.search(serialized_value):
            findings.append(
                DeploymentWitnessDispatchRehearsalFinding(
                    "deployment_witness_dispatch_rehearsal_forbidden_value_pattern",
                    f"deployment witness dispatch rehearsal {artifact_label} contains forbidden value pattern: {rule_id}",
                )
            )
    return findings


def validate_forbidden_promotion_patterns(
    value: str | dict[str, Any],
    artifact_label: str,
) -> list[DeploymentWitnessDispatchRehearsalFinding]:
    """Return findings if the witness drifts into dispatch or publication claims."""

    serialized_value = serialize_for_pattern_scan(value)
    findings: list[DeploymentWitnessDispatchRehearsalFinding] = []
    for rule_id, pattern in FORBIDDEN_PROMOTION_PATTERNS:
        if pattern.search(serialized_value):
            findings.append(
                DeploymentWitnessDispatchRehearsalFinding(
                    "deployment_witness_dispatch_rehearsal_forbidden_promotion_phrase",
                    f"deployment witness dispatch rehearsal {artifact_label} contains forbidden promotion pattern: {rule_id}",
                )
            )
    return findings


def validate_foundation_deployment_witness_dispatch_rehearsal_boundary(
    doc_path: Path = DEFAULT_DOC_PATH,
    packet_path: Path = DEFAULT_PACKET_PATH,
) -> list[DeploymentWitnessDispatchRehearsalFinding]:
    """Validate the Foundation Mode deployment witness dispatch rehearsal artifacts."""

    doc_text = load_text(doc_path, "deployment witness dispatch rehearsal boundary doc")
    packet_payload = load_json_object(packet_path, "deployment witness dispatch rehearsal witness packet")
    return [
        *validate_doc_text(doc_text),
        *validate_packet(packet_payload),
    ]


def main(argv: list[str] | None = None) -> int:
    """Validate deployment witness dispatch rehearsal artifacts and print deterministic status."""

    parser = argparse.ArgumentParser(
        description="Validate Foundation Mode deployment witness dispatch rehearsal boundary artifacts."
    )
    parser.add_argument("--doc", type=Path, default=DEFAULT_DOC_PATH)
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET_PATH)
    args = parser.parse_args(argv)

    try:
        findings = validate_foundation_deployment_witness_dispatch_rehearsal_boundary(args.doc, args.packet)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"[FAIL] foundation_deployment_witness_dispatch_rehearsal_load: {exc}", file=sys.stderr)
        print("STATUS: failed", file=sys.stderr)
        return 1

    if findings:
        for finding in findings:
            print(f"[FAIL] {finding.rule_id}: {finding.message}", file=sys.stderr)
        print("STATUS: failed", file=sys.stderr)
        return 1
    print("[PASS] foundation_deployment_witness_dispatch_rehearsal_doc")
    print("[PASS] foundation_deployment_witness_dispatch_rehearsal_witness")
    print("STATUS: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
