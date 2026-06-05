#!/usr/bin/env python3
"""Validate the Foundation Mode deployment witness artifact-validation rehearsal boundary.

Purpose: keep issue #330 deployment witness artifact-validation preparation
local and public-safe while artifact download, artifact paths, artifact ids,
artifact digests, schema-validation claims, deployment-claim publication,
runtime HMAC verification, conformance HMAC verification, public health
endpoint claims, closure-validation claims, evidence-ledger append, workflow
run claims, operator approval, customer access, personal data, money movement,
legal/business claims, publication, and deployment remain blocked.
Governance scope: Foundation Mode, issue #330 artifact-validation rehearsal,
public-safe validation labels, external evidence blocking, HMAC proof blocking,
endpoint proof blocking, evidence-ledger append blocking, approval blocking,
customer/data blocking, money blocking, legal/business restraint, publication
blocking, and deployment blocking.
Dependencies: docs/FOUNDATION_DEPLOYMENT_WITNESS_ARTIFACT_VALIDATION_REHEARSAL_BOUNDARY.md
and examples/foundation_deployment_witness_artifact_validation_rehearsal_witness.awaiting_evidence.json.
Invariants:
  - Validation is read-only.
  - The witness records public-safe artifact-validation labels and blocked gates only.
  - No artifact download, live artifact path, artifact id, artifact digest,
    schema-validation claim, deployment_claim: published claim, runtime HMAC
    verification, conformance HMAC verification, public health endpoint claim,
    closure-validation claim, evidence-ledger append, workflow run claim,
    operator approval, customer access, personal data, money movement, legal
    clearance, company formation, patent claim, external publication, or
    deployment claim is allowed.
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
DEFAULT_DOC_PATH = (
    REPO_ROOT / "docs" / "FOUNDATION_DEPLOYMENT_WITNESS_ARTIFACT_VALIDATION_REHEARSAL_BOUNDARY.md"
)
DEFAULT_PACKET_PATH = (
    REPO_ROOT
    / "examples"
    / "foundation_deployment_witness_artifact_validation_rehearsal_witness.awaiting_evidence.json"
)

EXPECTED_WITNESS_ID = "foundation_deployment_witness_artifact_validation_rehearsal_witness.awaiting_evidence.v1"
EXPECTED_VALIDATION_LABELS = (
    ".change_assurance/deployment_witness.json",
    "schemas/deployment_witness.schema.json",
    "deployment_claim",
    "published",
    "scripts/validate_deployment_publication_closure.py",
    "tests/test_deployment_witness_schema.py",
    "tests/test_validate_deployment_publication_closure.py",
    "runtime witness HMAC validation gate",
    "runtime conformance HMAC validation gate",
    "public health endpoint match gate",
    "evidence ledger append gate",
    "operator reassessment gate",
)
EXPECTED_BLOCKED_CLAIMS = (
    "artifact download",
    "artifact path value",
    "artifact id value",
    "artifact digest value",
    "schema validation",
    "deployment claim published",
    "runtime HMAC verification",
    "conformance HMAC verification",
    "public health endpoint claim",
    "closure validation",
    "evidence ledger append",
    "workflow run claim",
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
    "record public-safe artifact-validation labels only; do not download "
    "artifacts, record artifact paths, record artifact ids, record artifact "
    "digests, claim schema validation, claim deployment_claim: published, "
    "verify runtime HMAC values, verify conformance HMAC values, claim public "
    "health endpoints, claim closure validation, append evidence ledgers, "
    "claim workflow runs, claim operator approval, open customer access, "
    "collect personal data, move money, claim legal clearance, form a "
    "company, claim patent protection, publish externally, or deploy"
)
EXPECTED_SURFACES = (
    ("artifact_path_label", "artifact_validation_label", "AwaitingEvidence"),
    ("artifact_id_slot", "blocked_external_evidence", "AwaitingEvidence"),
    ("artifact_digest_slot", "blocked_external_evidence", "AwaitingEvidence"),
    ("deployment_witness_schema_label", "artifact_validation_label", "AwaitingEvidence"),
    ("deployment_claim_field_label", "artifact_validation_label", "AwaitingEvidence"),
    ("published_value_gate_label", "blocked_promotion_gate", "AwaitingEvidence"),
    ("runtime_hmac_validation_gate", "blocked_external_evidence", "AwaitingEvidence"),
    ("conformance_hmac_validation_gate", "blocked_external_evidence", "AwaitingEvidence"),
    ("public_health_endpoint_match_gate", "blocked_external_evidence", "AwaitingEvidence"),
    ("closure_validator_label", "artifact_validation_label", "AwaitingEvidence"),
    ("evidence_ledger_route_label", "blocked_external_evidence", "AwaitingEvidence"),
    ("operator_reassessment_gate", "blocked_promotion_gate", "AwaitingEvidence"),
)
EXPECTED_SURFACE_NOTES = {
    "artifact_path_label": "Artifact path label only; live artifact paths are not recorded.",
    "artifact_id_slot": "Artifact id slot only; artifact ids are not recorded.",
    "artifact_digest_slot": "Artifact digest slot only; artifact digests are not recorded.",
    "deployment_witness_schema_label": (
        "Deployment witness schema label only; schema validation pass is not claimed."
    ),
    "deployment_claim_field_label": (
        "Deployment claim field label only; deployment_claim presence is not claimed."
    ),
    "published_value_gate_label": (
        "Published value gate label only; deployment_claim: published is not claimed."
    ),
    "runtime_hmac_validation_gate": (
        "Runtime HMAC validation gate only; runtime HMAC verification is not claimed."
    ),
    "conformance_hmac_validation_gate": (
        "Conformance HMAC validation gate only; conformance HMAC verification is not claimed."
    ),
    "public_health_endpoint_match_gate": (
        "Public health endpoint match gate only; public health endpoint proof is not claimed."
    ),
    "closure_validator_label": "Closure validator label only; closure validation pass is not claimed.",
    "evidence_ledger_route_label": (
        "Evidence ledger route label only; evidence ledger append is not allowed."
    ),
    "operator_reassessment_gate": (
        "Operator reassessment gate only; operator approval, readiness, publication, and deployment remain blocked."
    ),
}
EXPECTED_DOC_SURFACE_LABELS = (
    "Artifact path label",
    "Artifact id slot",
    "Artifact digest slot",
    "Deployment witness schema label",
    "Deployment claim field label",
    "Published value gate label",
    "Runtime HMAC validation gate",
    "Conformance HMAC validation gate",
    "Public health endpoint match gate",
    "Closure validator label",
    "Evidence ledger route label",
    "Operator reassessment gate",
)
EXPECTED_ROOT_KEYS = {
    "artifact_digest_recorded",
    "artifact_download_allowed",
    "artifact_id_recorded",
    "artifact_path_recorded",
    "artifact_schema_validation_claimed",
    "blocked_claims",
    "closure_validation_claimed",
    "company_formation_claimed",
    "conformance_hmac_verified",
    "customer_access_allowed",
    "deployment_allowed",
    "deployment_claim_published_claimed",
    "evidence_ledger_append_allowed",
    "external_publication_allowed",
    "legal_clearance_claimed",
    "money_movement_allowed",
    "next_action",
    "operator_approval_claimed",
    "patent_claimed",
    "personal_data_collection_allowed",
    "public_health_endpoint_claimed",
    "runtime_hmac_verified",
    "schema_version",
    "solver_outcome",
    "status",
    "surfaces",
    "validation_labels",
    "witness_id",
    "workflow_run_claimed",
}
EXPECTED_SURFACE_KEYS = {
    "evidence_ref",
    "public_safe_note",
    "state",
    "surface_id",
    "surface_type",
}
REQUIRED_DOC_PHRASES = (
    "Foundation Deployment Witness Artifact Validation Rehearsal Boundary",
    "Witness packet: [`../examples/foundation_deployment_witness_artifact_validation_rehearsal_witness.awaiting_evidence.json`]",
    "Rule: Deployment witness artifact validation rehearsal is a local map",
    "No artifact download, artifact path value, artifact id value",
    "deployment_witness_artifact_validation_rehearsal_state=AwaitingEvidence",
    "artifact_download_allowed=false",
    "artifact_path_recorded=false",
    "artifact_id_recorded=false",
    "artifact_digest_recorded=false",
    "artifact_schema_validation_claimed=false",
    "deployment_claim_published_claimed=false",
    "runtime_hmac_verified=false",
    "conformance_hmac_verified=false",
    "public_health_endpoint_claimed=false",
    "closure_validation_claimed=false",
    "evidence_ledger_append_allowed=false",
    "workflow_run_claimed=false",
    "operator_approval_claimed=false",
    "customer_access_allowed=false",
    "personal_data_collection_allowed=false",
    "money_movement_allowed=false",
    "legal_clearance_claimed=false",
    "company_formation_claimed=false",
    "patent_claimed=false",
    "external_publication_allowed=false",
    "deployment_allowed=false",
    "python scripts/validate_foundation_deployment_witness_artifact_validation_rehearsal_boundary.py",
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
            r"receipt|evidence|report|operator|digest|hmac|endpoint|health|"
            r"schema|closure)"
            r"[_ -]?(?:id|name|value|url|target|host|ref|status|text|path|"
            r"list|number|digest|hash)?\s*=",
            re.IGNORECASE,
        ),
    ),
)
FORBIDDEN_PROMOTION_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("artifact_downloaded", re.compile(r"\bartifact\s+(?:is\s+)?(?:downloaded|fetched|retrieved)\b", re.IGNORECASE)),
    ("artifact_path_recorded", re.compile(r"\bartifact path\s+(?:is\s+)?(?:recorded|set|ready|verified)\b", re.IGNORECASE)),
    ("artifact_id_recorded", re.compile(r"\bartifact id\s+(?:is\s+)?(?:recorded|set|ready|verified)\b", re.IGNORECASE)),
    ("artifact_digest_recorded", re.compile(r"\bartifact digest\s+(?:is\s+)?(?:recorded|set|ready|verified)\b", re.IGNORECASE)),
    ("schema_validation_passed", re.compile(r"\bschema validation\s+(?:is\s+)?(?:passed|complete|ready|verified)\b", re.IGNORECASE)),
    ("artifact_validated", re.compile(r"\bartifact\s+(?:is\s+)?(?:validated|verified|ready)\b", re.IGNORECASE)),
    ("deployment_claim_published", re.compile(r"\bdeployment_claim:\s*published\s+(?:claimed|ready|verified|observed)\b", re.IGNORECASE)),
    ("runtime_hmac_verified", re.compile(r"\bruntime hmac\s+(?:is\s+)?(?:verified|valid|ready|complete)\b", re.IGNORECASE)),
    ("conformance_hmac_verified", re.compile(r"\bconformance hmac\s+(?:is\s+)?(?:verified|valid|ready|complete)\b", re.IGNORECASE)),
    ("public_health_endpoint_claimed", re.compile(r"\bpublic health endpoint\s+(?:is\s+)?(?:claimed|verified|matched|ready)\b", re.IGNORECASE)),
    ("closure_validation_passed", re.compile(r"\bclosure validation\s+(?:is\s+)?(?:passed|complete|ready|verified)\b", re.IGNORECASE)),
    ("evidence_ledger_appended", re.compile(r"\bevidence ledger\s+(?:is\s+)?(?:appended|updated|ready|verified)\b", re.IGNORECASE)),
    ("workflow_run_ready", re.compile(r"\bworkflow run\s+(?:is\s+)?(?:claimed|ready|verified|complete)\b", re.IGNORECASE)),
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
class DeploymentWitnessArtifactValidationRehearsalFinding:
    """One deterministic deployment witness artifact-validation rehearsal finding."""

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


def validate_doc_text(text: str) -> list[DeploymentWitnessArtifactValidationRehearsalFinding]:
    """Return findings for missing deployment witness artifact-validation doc anchors."""

    findings: list[DeploymentWitnessArtifactValidationRehearsalFinding] = []
    for phrase in REQUIRED_DOC_PHRASES:
        if phrase not in text:
            findings.append(
                DeploymentWitnessArtifactValidationRehearsalFinding(
                    "foundation_deployment_witness_artifact_validation_rehearsal_doc_phrase_missing",
                    f"deployment witness artifact-validation rehearsal doc missing required phrase: {phrase}",
                )
            )
    for validation_label in EXPECTED_VALIDATION_LABELS:
        if validation_label not in text:
            findings.append(
                DeploymentWitnessArtifactValidationRehearsalFinding(
                    "foundation_deployment_witness_artifact_validation_rehearsal_doc_label_missing",
                    f"deployment witness artifact-validation rehearsal doc missing validation label: {validation_label}",
                )
            )
    for surface_label in EXPECTED_DOC_SURFACE_LABELS:
        if surface_label not in text:
            findings.append(
                DeploymentWitnessArtifactValidationRehearsalFinding(
                    "foundation_deployment_witness_artifact_validation_rehearsal_doc_surface_missing",
                    f"deployment witness artifact-validation rehearsal doc missing surface label: {surface_label}",
                )
            )
    findings.extend(validate_forbidden_value_patterns(text, "doc"))
    findings.extend(validate_forbidden_promotion_patterns(text, "doc"))
    return findings


def validate_packet(payload: dict[str, Any]) -> list[DeploymentWitnessArtifactValidationRehearsalFinding]:
    """Return findings for deployment witness artifact-validation rehearsal witness drift."""

    findings: list[DeploymentWitnessArtifactValidationRehearsalFinding] = []
    findings.extend(validate_root_contract(payload))
    findings.extend(validate_surfaces(payload.get("surfaces")))
    findings.extend(validate_forbidden_value_patterns(payload, "witness"))
    findings.extend(validate_forbidden_promotion_patterns(payload, "witness"))
    return findings


def validate_root_contract(
    payload: dict[str, Any],
) -> list[DeploymentWitnessArtifactValidationRehearsalFinding]:
    """Return findings for root-level deployment witness artifact-validation rehearsal drift."""

    findings: list[DeploymentWitnessArtifactValidationRehearsalFinding] = []
    if set(payload) != EXPECTED_ROOT_KEYS:
        findings.append(
            DeploymentWitnessArtifactValidationRehearsalFinding(
                "deployment_witness_artifact_validation_rehearsal_root_keys_invalid",
                f"root keys must be: {', '.join(sorted(EXPECTED_ROOT_KEYS))}",
            )
        )
    expected_values = {
        "witness_id": EXPECTED_WITNESS_ID,
        "schema_version": 1,
        "status": "AwaitingEvidence",
        "solver_outcome": "AwaitingEvidence",
        "artifact_download_allowed": False,
        "artifact_path_recorded": False,
        "artifact_id_recorded": False,
        "artifact_digest_recorded": False,
        "artifact_schema_validation_claimed": False,
        "deployment_claim_published_claimed": False,
        "runtime_hmac_verified": False,
        "conformance_hmac_verified": False,
        "public_health_endpoint_claimed": False,
        "closure_validation_claimed": False,
        "evidence_ledger_append_allowed": False,
        "workflow_run_claimed": False,
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
                DeploymentWitnessArtifactValidationRehearsalFinding(
                    "deployment_witness_artifact_validation_rehearsal_root_value_invalid",
                    f"{key} must be {expected_value!r}",
                )
            )
    if tuple(payload.get("blocked_claims") or ()) != EXPECTED_BLOCKED_CLAIMS:
        findings.append(
            DeploymentWitnessArtifactValidationRehearsalFinding(
                "deployment_witness_artifact_validation_rehearsal_blocked_claims_invalid",
                f"blocked_claims must be: {', '.join(EXPECTED_BLOCKED_CLAIMS)}",
            )
        )
    if tuple(payload.get("validation_labels") or ()) != EXPECTED_VALIDATION_LABELS:
        findings.append(
            DeploymentWitnessArtifactValidationRehearsalFinding(
                "deployment_witness_artifact_validation_rehearsal_validation_labels_invalid",
                f"validation_labels must be: {', '.join(EXPECTED_VALIDATION_LABELS)}",
            )
        )
    if payload.get("next_action") != EXPECTED_NEXT_ACTION:
        findings.append(
            DeploymentWitnessArtifactValidationRehearsalFinding(
                "deployment_witness_artifact_validation_rehearsal_next_action_invalid",
                "next_action must preserve the exact public-safe non-validation handoff",
            )
        )
    return findings


def validate_surfaces(surfaces: object) -> list[DeploymentWitnessArtifactValidationRehearsalFinding]:
    """Return findings for deployment witness artifact-validation rehearsal surface drift."""

    findings: list[DeploymentWitnessArtifactValidationRehearsalFinding] = []
    if not isinstance(surfaces, list) or not all(isinstance(surface, dict) for surface in surfaces):
        return [
            DeploymentWitnessArtifactValidationRehearsalFinding(
                "deployment_witness_artifact_validation_rehearsal_surfaces_invalid",
                "surfaces must be a list",
            )
        ]
    observed_surfaces = tuple(
        (surface.get("surface_id"), surface.get("surface_type"), surface.get("state"))
        for surface in surfaces
    )
    if observed_surfaces != EXPECTED_SURFACES:
        findings.append(
            DeploymentWitnessArtifactValidationRehearsalFinding(
                "deployment_witness_artifact_validation_rehearsal_surface_inventory_invalid",
                "deployment witness artifact-validation rehearsal surface inventory does not match the expected set",
            )
        )
    surface_ids = [surface.get("surface_id") for surface in surfaces]
    if len(set(surface_ids)) != len(surface_ids):
        findings.append(
            DeploymentWitnessArtifactValidationRehearsalFinding(
                "deployment_witness_artifact_validation_rehearsal_surface_duplicate",
                "surface ids must be unique",
            )
        )
    for surface in surfaces:
        surface_id = str(surface.get("surface_id", "<missing>"))
        if set(surface) != EXPECTED_SURFACE_KEYS:
            findings.append(
                DeploymentWitnessArtifactValidationRehearsalFinding(
                    "deployment_witness_artifact_validation_rehearsal_surface_keys_invalid",
                    f"{surface_id} surface keys must be: {', '.join(sorted(EXPECTED_SURFACE_KEYS))}",
                )
            )
        if surface.get("state") != "AwaitingEvidence":
            findings.append(
                DeploymentWitnessArtifactValidationRehearsalFinding(
                    "deployment_witness_artifact_validation_rehearsal_surface_state_invalid",
                    f"{surface_id} state must be AwaitingEvidence",
                )
            )
        if surface.get("evidence_ref") != "manual_preparation_pending":
            findings.append(
                DeploymentWitnessArtifactValidationRehearsalFinding(
                    "deployment_witness_artifact_validation_rehearsal_surface_evidence_invalid",
                    f"{surface_id} evidence_ref must stay manual_preparation_pending",
                )
            )
        if not isinstance(surface.get("public_safe_note"), str) or not surface["public_safe_note"].strip():
            findings.append(
                DeploymentWitnessArtifactValidationRehearsalFinding(
                    "deployment_witness_artifact_validation_rehearsal_surface_note_invalid",
                    f"{surface_id} public_safe_note must be a non-empty string",
                )
            )
        elif surface.get("public_safe_note") != EXPECTED_SURFACE_NOTES.get(surface_id):
            findings.append(
                DeploymentWitnessArtifactValidationRehearsalFinding(
                    "deployment_witness_artifact_validation_rehearsal_surface_note_invalid",
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
) -> list[DeploymentWitnessArtifactValidationRehearsalFinding]:
    """Return findings for live value, private path, or external-action shaped values."""

    serialized_value = serialize_for_pattern_scan(value)
    findings: list[DeploymentWitnessArtifactValidationRehearsalFinding] = []
    for rule_id, pattern in FORBIDDEN_VALUE_PATTERNS:
        if pattern.search(serialized_value):
            findings.append(
                DeploymentWitnessArtifactValidationRehearsalFinding(
                    "deployment_witness_artifact_validation_rehearsal_forbidden_value_pattern",
                    f"deployment witness artifact-validation rehearsal {artifact_label} contains forbidden value pattern: {rule_id}",
                )
            )
    return findings


def validate_forbidden_promotion_patterns(
    value: str | dict[str, Any],
    artifact_label: str,
) -> list[DeploymentWitnessArtifactValidationRehearsalFinding]:
    """Return findings if the witness drifts into artifact, evidence, or deployment claims."""

    serialized_value = serialize_for_pattern_scan(value)
    findings: list[DeploymentWitnessArtifactValidationRehearsalFinding] = []
    for rule_id, pattern in FORBIDDEN_PROMOTION_PATTERNS:
        if pattern.search(serialized_value):
            findings.append(
                DeploymentWitnessArtifactValidationRehearsalFinding(
                    "deployment_witness_artifact_validation_rehearsal_forbidden_promotion_phrase",
                    f"deployment witness artifact-validation rehearsal {artifact_label} contains forbidden promotion pattern: {rule_id}",
                )
            )
    return findings


def validate_foundation_deployment_witness_artifact_validation_rehearsal_boundary(
    doc_path: Path = DEFAULT_DOC_PATH,
    packet_path: Path = DEFAULT_PACKET_PATH,
) -> list[DeploymentWitnessArtifactValidationRehearsalFinding]:
    """Validate the Foundation Mode deployment witness artifact-validation rehearsal artifacts."""

    doc_text = load_text(doc_path, "deployment witness artifact-validation rehearsal boundary doc")
    packet_payload = load_json_object(packet_path, "deployment witness artifact-validation rehearsal witness packet")
    return [
        *validate_doc_text(doc_text),
        *validate_packet(packet_payload),
    ]


def main(argv: list[str] | None = None) -> int:
    """Validate deployment witness artifact-validation rehearsal artifacts."""

    parser = argparse.ArgumentParser(
        description="Validate Foundation Mode deployment witness artifact-validation rehearsal boundary artifacts."
    )
    parser.add_argument("--doc", type=Path, default=DEFAULT_DOC_PATH)
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET_PATH)
    args = parser.parse_args(argv)

    try:
        findings = validate_foundation_deployment_witness_artifact_validation_rehearsal_boundary(
            args.doc,
            args.packet,
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"[FAIL] foundation_deployment_witness_artifact_validation_rehearsal_load: {exc}", file=sys.stderr)
        print("STATUS: failed", file=sys.stderr)
        return 1

    if findings:
        for finding in findings:
            print(f"[FAIL] {finding.rule_id}: {finding.message}", file=sys.stderr)
        print("STATUS: failed", file=sys.stderr)
        return 1
    print("[PASS] foundation_deployment_witness_artifact_validation_rehearsal_doc")
    print("[PASS] foundation_deployment_witness_artifact_validation_rehearsal_witness")
    print("STATUS: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
