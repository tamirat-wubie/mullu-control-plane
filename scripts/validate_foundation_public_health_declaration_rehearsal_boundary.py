#!/usr/bin/env python3
"""Validate the Foundation Mode public health declaration rehearsal boundary.

Purpose: keep issue #330 public health declaration preparation local and
public-safe while public health declaration, deployment status mutation,
declaration receipt writing, endpoint values, approval references, dates,
validation-pass claims, evidence-ledger append, workflow dispatch, artifact
publication, readiness, customer access, money movement, legal/business
claims, publication, and deployment remain blocked.
Governance scope: Foundation Mode, issue #330 public health declaration
rehearsal, public-safe declaration field labels, deployment status mutation
blocking, value exclusion, evidence-ledger append blocking, approval blocking,
publication blocking, and deployment restraint.
Dependencies: docs/FOUNDATION_PUBLIC_HEALTH_DECLARATION_REHEARSAL_BOUNDARY.md
and examples/foundation_public_health_declaration_rehearsal_witness.awaiting_evidence.json.
Invariants:
  - Validation is read-only.
  - The witness records public-safe public health declaration field labels only.
  - No public health declaration, deployment status mutation, declaration
    receipt writing, witness publication claim, public health endpoint value,
    approval reference, audited date, validation-pass claim, endpoint-match
    claim, evidence-ledger append, workflow dispatch, artifact publication,
    readiness claim, customer access, personal data, money movement, legal
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
DEFAULT_DOC_PATH = REPO_ROOT / "docs" / "FOUNDATION_PUBLIC_HEALTH_DECLARATION_REHEARSAL_BOUNDARY.md"
DEFAULT_PACKET_PATH = (
    REPO_ROOT / "examples" / "foundation_public_health_declaration_rehearsal_witness.awaiting_evidence.json"
)

EXPECTED_WITNESS_ID = "foundation_public_health_declaration_rehearsal_witness.awaiting_evidence.v1"
EXPECTED_FIELD_LABELS = (
    "deployment_status_path_label",
    "deployment_witness_path_label",
    "declaration_receipt_path_label",
    "dry_run_flag_label",
    "updated_flag_label",
    "deployment_witness_state_label",
    "public_health_endpoint_label",
    "operator_approval_ref_label",
    "audited_date_label",
    "schema_validation_result_label",
    "closure_validation_result_label",
    "endpoint_match_result_label",
    "evidence_ledger_route_label",
    "operator_reassessment_gate",
)
EXPECTED_BLOCKED_CLAIMS = (
    "public health declaration",
    "deployment status mutation",
    "declaration receipt writing",
    "deployment witness publication claim",
    "deployment witness state value",
    "public health endpoint value",
    "operator approval reference value",
    "audited date value",
    "schema validation pass claim",
    "closure validation pass claim",
    "endpoint match claim",
    "dry run result",
    "status update result",
    "evidence ledger append",
    "workflow dispatch",
    "artifact publication",
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
    "record public-safe public health declaration field labels only; do not "
    "declare public health, mutate deployment status, write declaration "
    "receipts, claim deployment witness publication, record deployment witness "
    "state values, record public health endpoint values, record operator "
    "approval references, record audited dates, claim schema validation pass, "
    "claim closure validation pass, claim endpoint match, record dry-run "
    "results, record status update results, append evidence to a ledger, "
    "dispatch workflows, publish artifacts, claim readiness, open customer "
    "access, collect personal data, move money, claim legal clearance, form a "
    "company, claim patent protection, publish externally, or deploy"
)
EXPECTED_SURFACES = (
    ("deployment_status_path_label", "declaration_field_label", "AwaitingEvidence"),
    ("deployment_witness_path_label", "declaration_field_label", "AwaitingEvidence"),
    ("declaration_receipt_path_label", "declaration_field_label", "AwaitingEvidence"),
    ("dry_run_flag_label", "declaration_field_label", "AwaitingEvidence"),
    ("updated_flag_label", "declaration_field_label", "AwaitingEvidence"),
    ("deployment_witness_state_label", "blocked_external_evidence", "AwaitingEvidence"),
    ("public_health_endpoint_label", "blocked_external_evidence", "AwaitingEvidence"),
    ("operator_approval_ref_label", "blocked_external_evidence", "AwaitingEvidence"),
    ("audited_date_label", "blocked_external_evidence", "AwaitingEvidence"),
    ("schema_validation_result_label", "blocked_external_evidence", "AwaitingEvidence"),
    ("closure_validation_result_label", "blocked_external_evidence", "AwaitingEvidence"),
    ("endpoint_match_result_label", "blocked_external_evidence", "AwaitingEvidence"),
    ("evidence_ledger_route_label", "local_route_label", "AwaitingEvidence"),
    ("operator_reassessment_gate", "local_gate_label", "AwaitingEvidence"),
)
EXPECTED_SURFACE_NOTES = {
    "deployment_status_path_label": "Deployment status path label only; deployment status is not mutated.",
    "deployment_witness_path_label": (
        "Deployment witness path label only; deployment witness publication is not claimed."
    ),
    "declaration_receipt_path_label": (
        "Declaration receipt path label only; declaration receipts are not written."
    ),
    "dry_run_flag_label": "Dry-run flag label only; dry-run results are not recorded.",
    "updated_flag_label": "Updated flag label only; status update results are not recorded.",
    "deployment_witness_state_label": "Deployment witness state label only; state values are not recorded.",
    "public_health_endpoint_label": "Public health endpoint label only; endpoint values are not recorded.",
    "operator_approval_ref_label": (
        "Operator approval reference label only; approval references are not recorded."
    ),
    "audited_date_label": "Audited date label only; dates are not recorded.",
    "schema_validation_result_label": "Schema validation result label only; schema validation pass is not claimed.",
    "closure_validation_result_label": (
        "Closure validation result label only; closure validation pass is not claimed."
    ),
    "endpoint_match_result_label": "Endpoint match result label only; endpoint match is not claimed.",
    "evidence_ledger_route_label": "Evidence ledger route label only; evidence is not appended.",
    "operator_reassessment_gate": (
        "Operator reassessment gate only; public health declaration and deployment are not approved."
    ),
}
EXPECTED_DOC_SURFACE_LABELS = (
    "Deployment status path label",
    "Deployment witness path label",
    "Declaration receipt path label",
    "Dry-run flag label",
    "Updated flag label",
    "Deployment witness state label",
    "Public health endpoint label",
    "Operator approval reference label",
    "Audited date label",
    "Schema validation result label",
    "Closure validation result label",
    "Endpoint match result label",
    "Evidence ledger route label",
    "Operator reassessment gate",
)
EXPECTED_ROOT_KEYS = {
    "artifact_publication_allowed",
    "audited_date_value_recorded",
    "blocked_claims",
    "closure_validation_pass_claimed",
    "company_formation_claimed",
    "customer_access_allowed",
    "declaration_receipt_written",
    "deployment_allowed",
    "deployment_status_mutation_allowed",
    "deployment_witness_publication_claimed",
    "deployment_witness_state_value_recorded",
    "dry_run_result_recorded",
    "endpoint_match_claimed",
    "evidence_ledger_append_allowed",
    "external_publication_allowed",
    "field_labels",
    "legal_clearance_claimed",
    "money_movement_allowed",
    "next_action",
    "operator_approval_ref_value_recorded",
    "patent_claimed",
    "personal_data_collection_allowed",
    "public_health_declared",
    "public_health_endpoint_value_recorded",
    "readiness_claimed",
    "schema_validation_pass_claimed",
    "schema_version",
    "solver_outcome",
    "status",
    "status_update_result_recorded",
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
    "Foundation Public Health Declaration Rehearsal Boundary",
    "Witness packet: [`../examples/foundation_public_health_declaration_rehearsal_witness.awaiting_evidence.json`]",
    "Rule: Public health declaration rehearsal is a local field-label map",
    "No public health declaration, deployment status mutation, declaration receipt",
    "public_health_declaration_rehearsal_state=AwaitingEvidence",
    "public_health_declared=false",
    "deployment_status_mutation_allowed=false",
    "declaration_receipt_written=false",
    "deployment_witness_publication_claimed=false",
    "deployment_witness_state_value_recorded=false",
    "public_health_endpoint_value_recorded=false",
    "operator_approval_ref_value_recorded=false",
    "audited_date_value_recorded=false",
    "schema_validation_pass_claimed=false",
    "closure_validation_pass_claimed=false",
    "endpoint_match_claimed=false",
    "dry_run_result_recorded=false",
    "status_update_result_recorded=false",
    "evidence_ledger_append_allowed=false",
    "workflow_dispatch_allowed=false",
    "artifact_publication_allowed=false",
    "readiness_claimed=false",
    "customer_access_allowed=false",
    "personal_data_collection_allowed=false",
    "money_movement_allowed=false",
    "legal_clearance_claimed=false",
    "company_formation_claimed=false",
    "patent_claimed=false",
    "external_publication_allowed=false",
    "deployment_allowed=false",
    "python scripts/validate_foundation_public_health_declaration_rehearsal_boundary.py",
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
    ("timestamp_value", re.compile(r"\b20\d{2}-\d{2}-\d{2}(?:T\d{2}:\d{2})?", re.IGNORECASE)),
    (
        "assignment",
        re.compile(
            r"\b(?:public[_ -]?health|deployment[_ -]?status|declaration|"
            r"witness|endpoint|gateway|url|approval|operator|audited|date|"
            r"schema|closure|validation|match|dry[_ -]?run|updated|status|"
            r"ledger|workflow|run|artifact|secret|token|api[_ -]?key|"
            r"client[_ -]?secret|password|customer|person|participant|email|"
            r"payment|billing|invoice|legal|company|formation|patent|receipt|"
            r"evidence|report)"
            r"[_ -]?(?:id|name|value|url|target|host|ref|status|text|path|list|"
            r"number|record|address|count|error|time|payload|digest|body)?\s*=",
            re.IGNORECASE,
        ),
    ),
)
FORBIDDEN_PROMOTION_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("public_health_declared", re.compile(r"\bpublic health\s+(?:is\s+)?(?:declared|ready|verified|complete)\b", re.IGNORECASE)),
    ("deployment_status_mutated", re.compile(r"\bdeployment status\s+(?:is\s+)?(?:mutated|updated|ready|verified|complete)\b", re.IGNORECASE)),
    ("declaration_receipt_written", re.compile(r"\bdeclaration receipt\s+(?:is\s+)?(?:written|recorded|ready|verified|complete)\b", re.IGNORECASE)),
    ("witness_published", re.compile(r"\bdeployment witness\s+(?:is\s+)?(?:published|ready|verified|complete)\b", re.IGNORECASE)),
    ("endpoint_recorded", re.compile(r"\bpublic health endpoint\s+(?:is\s+)?(?:recorded|declared|ready|verified)\b", re.IGNORECASE)),
    ("approval_ready", re.compile(r"\boperator approval\s+(?:is\s+)?(?:claimed|ready|verified|complete)\b", re.IGNORECASE)),
    ("schema_pass", re.compile(r"\bschema validation\s+(?:is\s+)?(?:passed|ready|verified|complete)\b", re.IGNORECASE)),
    ("closure_pass", re.compile(r"\bclosure validation\s+(?:is\s+)?(?:passed|ready|verified|complete)\b", re.IGNORECASE)),
    ("endpoint_match_ready", re.compile(r"\bendpoint match\s+(?:is\s+)?(?:claimed|ready|verified|complete)\b", re.IGNORECASE)),
    ("ledger_append_ready", re.compile(r"\bevidence(?:-| )ledger append\s+(?:is\s+)?(?:ready|complete|verified)\b", re.IGNORECASE)),
    ("workflow_dispatched", re.compile(r"\bworkflow\s+(?:is\s+)?(?:dispatched|ready|verified|complete)\b", re.IGNORECASE)),
    ("artifact_published", re.compile(r"\bartifact\s+(?:is\s+)?(?:published|ready|verified)\b", re.IGNORECASE)),
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
class PublicHealthDeclarationRehearsalFinding:
    """One deterministic public health declaration rehearsal validation finding."""

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


def validate_forbidden_values(strings: list[str], artifact_label: str) -> list[PublicHealthDeclarationRehearsalFinding]:
    """Return findings when public artifacts contain values or assignments."""

    findings: list[PublicHealthDeclarationRehearsalFinding] = []
    for value in strings:
        for rule_id, pattern in FORBIDDEN_VALUE_PATTERNS:
            if pattern.search(value):
                findings.append(
                    PublicHealthDeclarationRehearsalFinding(
                        "public_health_declaration_rehearsal_forbidden_value_pattern",
                        f"public health declaration rehearsal {artifact_label} contains forbidden value pattern: {rule_id}",
                    )
                )
    return findings


def validate_forbidden_promotions(
    strings: list[str],
    artifact_label: str,
) -> list[PublicHealthDeclarationRehearsalFinding]:
    """Return findings when public artifacts promote blocked declaration state."""

    findings: list[PublicHealthDeclarationRehearsalFinding] = []
    for value in strings:
        for rule_id, pattern in FORBIDDEN_PROMOTION_PATTERNS:
            if pattern.search(value):
                findings.append(
                    PublicHealthDeclarationRehearsalFinding(
                        "public_health_declaration_rehearsal_forbidden_promotion_phrase",
                        f"public health declaration rehearsal {artifact_label} contains forbidden promotion pattern: {rule_id}",
                    )
                )
    return findings


def validate_doc_text(text: str) -> list[PublicHealthDeclarationRehearsalFinding]:
    """Return findings for public health declaration rehearsal documentation drift."""

    findings: list[PublicHealthDeclarationRehearsalFinding] = []
    for phrase in REQUIRED_DOC_PHRASES:
        if phrase not in text:
            findings.append(
                PublicHealthDeclarationRehearsalFinding(
                    "foundation_public_health_declaration_rehearsal_doc_phrase_missing",
                    f"public health declaration rehearsal doc missing required phrase: {phrase}",
                )
            )
    for label in EXPECTED_FIELD_LABELS:
        if label not in text:
            findings.append(
                PublicHealthDeclarationRehearsalFinding(
                    "foundation_public_health_declaration_rehearsal_doc_label_missing",
                    f"public health declaration rehearsal doc missing field label: {label}",
                )
            )
    for label in EXPECTED_DOC_SURFACE_LABELS:
        if label not in text:
            findings.append(
                PublicHealthDeclarationRehearsalFinding(
                    "foundation_public_health_declaration_rehearsal_doc_surface_missing",
                    f"public health declaration rehearsal doc missing surface label: {label}",
                )
            )
    findings.extend(validate_forbidden_values([text], "doc"))
    findings.extend(validate_forbidden_promotions([text], "doc"))
    return findings


def validate_packet(payload: dict[str, Any]) -> list[PublicHealthDeclarationRehearsalFinding]:
    """Return findings for public health declaration rehearsal witness drift."""

    findings: list[PublicHealthDeclarationRehearsalFinding] = []
    if set(payload) != EXPECTED_ROOT_KEYS:
        findings.append(
            PublicHealthDeclarationRehearsalFinding(
                "public_health_declaration_rehearsal_root_keys_invalid",
                "public health declaration rehearsal witness root keys drifted",
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
        "public_health_declared": False,
        "deployment_status_mutation_allowed": False,
        "declaration_receipt_written": False,
        "deployment_witness_publication_claimed": False,
        "deployment_witness_state_value_recorded": False,
        "public_health_endpoint_value_recorded": False,
        "operator_approval_ref_value_recorded": False,
        "audited_date_value_recorded": False,
        "schema_validation_pass_claimed": False,
        "closure_validation_pass_claimed": False,
        "endpoint_match_claimed": False,
        "dry_run_result_recorded": False,
        "status_update_result_recorded": False,
        "evidence_ledger_append_allowed": False,
        "workflow_dispatch_allowed": False,
        "artifact_publication_allowed": False,
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
                PublicHealthDeclarationRehearsalFinding(
                    "public_health_declaration_rehearsal_root_value_invalid",
                    f"{key} must remain {expected!r}",
                )
            )
    findings.extend(validate_surfaces(payload.get("surfaces")))
    findings.extend(validate_forbidden_values(iter_string_values(payload), "witness"))
    findings.extend(validate_forbidden_promotions(iter_string_values(payload), "witness"))
    return findings


def validate_surfaces(surfaces: object) -> list[PublicHealthDeclarationRehearsalFinding]:
    """Return findings for public health declaration rehearsal surface inventory drift."""

    findings: list[PublicHealthDeclarationRehearsalFinding] = []
    if not isinstance(surfaces, list) or not all(isinstance(surface, dict) for surface in surfaces):
        return [
            PublicHealthDeclarationRehearsalFinding(
                "public_health_declaration_rehearsal_surfaces_invalid",
                "public health declaration rehearsal surfaces must be a list of objects",
            )
        ]
    observed = tuple(
        (surface.get("surface_id"), surface.get("surface_type"), surface.get("state"))
        for surface in surfaces
    )
    if observed != EXPECTED_SURFACES:
        findings.append(
            PublicHealthDeclarationRehearsalFinding(
                "public_health_declaration_rehearsal_surface_inventory_invalid",
                "public health declaration rehearsal surface inventory does not match the Foundation Mode set",
            )
        )
    seen_surface_ids: set[object] = set()
    for surface in surfaces:
        surface_id = surface.get("surface_id")
        if set(surface) != EXPECTED_SURFACE_KEYS:
            findings.append(
                PublicHealthDeclarationRehearsalFinding(
                    "public_health_declaration_rehearsal_surface_keys_invalid",
                    f"{surface_id} surface keys drifted",
                )
            )
        if surface_id in seen_surface_ids:
            findings.append(
                PublicHealthDeclarationRehearsalFinding(
                    "public_health_declaration_rehearsal_surface_duplicate",
                    "surface ids must be unique",
                )
            )
        seen_surface_ids.add(surface_id)
        if surface.get("state") != "AwaitingEvidence":
            findings.append(
                PublicHealthDeclarationRehearsalFinding(
                    "public_health_declaration_rehearsal_surface_state_invalid",
                    f"{surface_id} state must be AwaitingEvidence",
                )
            )
        if surface.get("evidence_ref") != "manual_preparation_pending":
            findings.append(
                PublicHealthDeclarationRehearsalFinding(
                    "public_health_declaration_rehearsal_surface_evidence_invalid",
                    f"{surface_id} evidence_ref must remain manual_preparation_pending",
                )
            )
        expected_note = EXPECTED_SURFACE_NOTES.get(str(surface_id))
        if surface.get("public_safe_note") != expected_note:
            findings.append(
                PublicHealthDeclarationRehearsalFinding(
                    "public_health_declaration_rehearsal_surface_note_invalid",
                    f"{surface_id} public_safe_note drifted",
                )
            )
    return findings


def validate_foundation_public_health_declaration_rehearsal_boundary(
    doc_path: Path = DEFAULT_DOC_PATH,
    packet_path: Path = DEFAULT_PACKET_PATH,
) -> list[PublicHealthDeclarationRehearsalFinding]:
    """Validate the Foundation Mode public health declaration rehearsal artifacts."""

    doc_text = load_text(doc_path, "public health declaration rehearsal boundary doc")
    packet_payload = load_json_object(packet_path, "public health declaration rehearsal witness packet")
    findings: list[PublicHealthDeclarationRehearsalFinding] = []
    findings.extend(validate_doc_text(doc_text))
    findings.extend(validate_packet(packet_payload))
    return findings


def main() -> int:
    """Validate public health declaration rehearsal artifacts and print deterministic status."""

    parser = argparse.ArgumentParser(
        description="Validate Foundation Mode public health declaration rehearsal boundary artifacts."
    )
    parser.add_argument("--doc", type=Path, default=DEFAULT_DOC_PATH)
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET_PATH)
    args = parser.parse_args()
    try:
        findings = validate_foundation_public_health_declaration_rehearsal_boundary(args.doc, args.packet)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"[FAIL] foundation_public_health_declaration_rehearsal_load: {exc}", file=sys.stderr)
        return 2
    if findings:
        for finding in findings:
            print(f"[FAIL] {finding.rule_id}: {finding.message}", file=sys.stderr)
        print("STATUS: failed", file=sys.stderr)
        return 1
    print("[PASS] foundation_public_health_declaration_rehearsal_doc")
    print("[PASS] foundation_public_health_declaration_rehearsal_witness")
    print("STATUS: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
