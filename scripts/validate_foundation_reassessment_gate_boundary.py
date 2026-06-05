#!/usr/bin/env python3
"""Validate the Foundation Mode reassessment gate boundary.

Purpose: keep reassessment local and public-safe while approval, prerequisite
promotion, deployment start, pilot start, external action, customer access,
personal-data collection, legal-clearance claims, company-formation claims,
patent claims, money movement, secret material, external publication, and
deployment remain blocked.
Governance scope: Foundation Mode, local reassessment, non-promotion handoff,
deployment-start blocking, pilot-start blocking, customer/data blocking,
legal/business restraint, money blocking, secret exclusion, publication
blocking, and deployment blocking.
Dependencies: docs/FOUNDATION_REASSESSMENT_GATE_BOUNDARY.md and
examples/foundation_reassessment_gate_witness.awaiting_evidence.json.
Invariants:
  - Validation is read-only.
  - The witness records local reassessment questions only.
  - No approval, promotion, deployment start, pilot start, external action,
    customer access, personal data, legal clearance, company formation, patent
    claim, money movement, secret material, publication, or deployment claim is
    allowed.
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
DEFAULT_DOC_PATH = REPO_ROOT / "docs" / "FOUNDATION_REASSESSMENT_GATE_BOUNDARY.md"
DEFAULT_PACKET_PATH = REPO_ROOT / "examples" / "foundation_reassessment_gate_witness.awaiting_evidence.json"

EXPECTED_WITNESS_ID = "foundation_reassessment_gate_witness.awaiting_evidence.v1"
EXPECTED_BLOCKED_CLAIMS = (
    "reassessment approval",
    "prerequisite promotion",
    "deployment start",
    "pilot start",
    "external action",
    "customer access",
    "personal data collection",
    "legal clearance",
    "company formation",
    "patent claim",
    "money movement",
    "secret material",
    "external publication",
    "deployment readiness",
)
EXPECTED_NEXT_ACTION = (
    "choose one local prerequisite only; do not approve reassessment, promote "
    "evidence, start deployment prerequisites, advance pilot prerequisites, "
    "contact people, collect personal data, claim legal clearance, form a "
    "company, claim patent protection, move money, store secret material, "
    "publish externally, or deploy"
)
EXPECTED_SURFACES = (
    ("deployment_start_question", "local_draft", "AwaitingEvidence"),
    ("pilot_start_question", "local_draft", "AwaitingEvidence"),
    ("evidence_gap_review", "local_draft", "AwaitingEvidence"),
    ("operator_capacity_check", "local_draft", "AwaitingEvidence"),
    ("risk_stop_rule", "local_draft", "AwaitingEvidence"),
    ("external_boundary_check", "local_draft", "AwaitingEvidence"),
    ("legal_business_stop_rule", "local_draft", "AwaitingEvidence"),
    ("money_secret_stop_rule", "local_draft", "AwaitingEvidence"),
    ("customer_data_stop_rule", "local_draft", "AwaitingEvidence"),
    ("rollback_recovery_check", "local_draft", "AwaitingEvidence"),
    ("next_local_prerequisite_selection", "local_draft", "AwaitingEvidence"),
    ("non_promotion_handoff", "local_draft", "AwaitingEvidence"),
)
EXPECTED_SURFACE_NOTES = {
    "deployment_start_question": (
        "Deployment-start question only; deployment prerequisites remain "
        "deferred and runtime exposure remains blocked."
    ),
    "pilot_start_question": (
        "Pilot-start question only; pilot prerequisites remain deferred and "
        "participant access remains closed."
    ),
    "evidence_gap_review": "Evidence-gap review only; no evidence is promoted and no closure is claimed.",
    "operator_capacity_check": (
        "Operator-capacity check only; no schedule, team, support, or incident "
        "coverage is claimed."
    ),
    "risk_stop_rule": "Risk stop-rule questions only; irreversible external action remains blocked.",
    "external_boundary_check": (
        "External-boundary questions only; no DNS, runtime, provider, workflow, "
        "or service activation is allowed."
    ),
    "legal_business_stop_rule": (
        "Legal/business stop-rule questions only; no legal clearance, company "
        "formation, filing, or patent claim is recorded."
    ),
    "money_secret_stop_rule": (
        "Money/secret stop-rule questions only; no payment method, spend, money "
        "movement, credential, or secret material is recorded."
    ),
    "customer_data_stop_rule": (
        "Customer/data stop-rule questions only; no customer access, intake, "
        "participant access, or personal data is opened."
    ),
    "rollback_recovery_check": (
        "Rollback/recovery check only; no recovery, incident, or restore "
        "readiness is claimed."
    ),
    "next_local_prerequisite_selection": (
        "Next-local-prerequisite selection only; roadmap, deadline, broad "
        "execution, and external action remain blocked."
    ),
    "non_promotion_handoff": (
        "Non-promotion handoff only; reassessment remains AwaitingEvidence and "
        "does not become approval."
    ),
}
EXPECTED_DOC_SURFACE_LABELS = (
    "Deployment start question",
    "Pilot start question",
    "Evidence gap review",
    "Operator capacity check",
    "Risk stop rule",
    "External boundary check",
    "Legal/business stop rule",
    "Money/secret stop rule",
    "Customer/data stop rule",
    "Rollback/recovery check",
    "Next local prerequisite selection",
    "Non-promotion handoff",
)
EXPECTED_ROOT_KEYS = {
    "blocked_claims",
    "company_formation_claimed",
    "customer_access_allowed",
    "deployment_allowed",
    "deployment_start_allowed",
    "external_action_allowed",
    "external_publication_allowed",
    "legal_clearance_claimed",
    "money_movement_allowed",
    "next_action",
    "patent_claimed",
    "personal_data_collection_allowed",
    "pilot_start_allowed",
    "prerequisite_promotion_allowed",
    "reassessment_approved",
    "schema_version",
    "secret_material_allowed",
    "solver_outcome",
    "status",
    "surfaces",
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
    "Foundation Reassessment Gate Boundary",
    "Witness packet: [`../examples/foundation_reassessment_gate_witness.awaiting_evidence.json`]",
    "Rule: Reassessment is a local gate",
    "No reassessment approval, prerequisite promotion, deployment start, pilot",
    "reassessment_gate_state=AwaitingEvidence",
    "reassessment_approved=false",
    "prerequisite_promotion_allowed=false",
    "deployment_start_allowed=false",
    "pilot_start_allowed=false",
    "external_action_allowed=false",
    "customer_access_allowed=false",
    "personal_data_collection_allowed=false",
    "legal_clearance_claimed=false",
    "company_formation_claimed=false",
    "patent_claimed=false",
    "money_movement_allowed=false",
    "secret_material_allowed=false",
    "external_publication_allowed=false",
    "deployment_allowed=false",
    "python scripts/validate_foundation_reassessment_gate_boundary.py",
)
FORBIDDEN_VALUE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("url_value", re.compile(r"https?://", re.IGNORECASE)),
    ("email_value", re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)),
    ("private_path", re.compile(r"\b[A-Za-z]:[\\/]|\\\\", re.IGNORECASE)),
    ("private_key_block", re.compile(r"-----BEGIN\s+(?:RSA\s+|EC\s+|OPENSSH\s+)?PRIVATE\s+KEY-----", re.IGNORECASE)),
    (
        "reassessment_assignment",
        re.compile(
            r"\b(?:approval|approved|person|participant|customer|user|pilot|"
            r"deployment|runtime|dns|provider|account|tenant|project|workflow|"
            r"schedule|deadline|date|legal|company|formation|filing|patent|"
            r"payment|billing|card|invoice|price|money|secret|token|api[_ -]?key|"
            r"client[_ -]?secret)"
            r"[_ -]?(?:id|name|email|url|link|ref|target|value|status|text|list)?\s*=",
            re.IGNORECASE,
        ),
    ),
)
FORBIDDEN_PROMOTION_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("reassessment_approved", re.compile(r"\breassessment\s+(?:is\s+)?approved\b", re.IGNORECASE)),
    ("prerequisite_promoted", re.compile(r"\bprerequisite\s+(?:is\s+)?promoted\b", re.IGNORECASE)),
    ("deployment_can_start", re.compile(r"\bdeployment\s+(?:can|may|should)\s+start\b", re.IGNORECASE)),
    ("deployment_ready", re.compile(r"\bdeployment\s+(?:is\s+)?ready\b", re.IGNORECASE)),
    ("pilot_can_start", re.compile(r"\bpilot\s+(?:can|may|should)\s+start\b", re.IGNORECASE)),
    ("pilot_ready", re.compile(r"\bpilot\s+(?:is\s+)?ready\b", re.IGNORECASE)),
    ("external_action_approved", re.compile(r"\bexternal action\s+(?:is\s+)?approved\b", re.IGNORECASE)),
    ("customer_access_ready", re.compile(r"\bcustomer access\s+(?:is\s+)?ready\b", re.IGNORECASE)),
    ("legal_cleared", re.compile(r"\blegal\s+(?:is\s+)?cleared\b", re.IGNORECASE)),
    ("company_formed", re.compile(r"\bcompany\s+(?:is\s+)?formed\b", re.IGNORECASE)),
    ("patent_filed", re.compile(r"\bpatent\s+(?:is\s+)?filed\b", re.IGNORECASE)),
    ("money_movement_allowed", re.compile(r"\bmoney movement\s+(?:is\s+)?allowed\b", re.IGNORECASE)),
    ("external_publication_approved", re.compile(r"\bexternal publication (?:allowed|approved|ready)\b", re.IGNORECASE)),
)


@dataclass(frozen=True, slots=True)
class ReassessmentGateFinding:
    """One deterministic reassessment gate validation finding."""

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


def validate_doc_text(text: str) -> list[ReassessmentGateFinding]:
    """Return findings for missing reassessment gate documentation anchors."""

    findings: list[ReassessmentGateFinding] = []
    for phrase in REQUIRED_DOC_PHRASES:
        if phrase not in text:
            findings.append(
                ReassessmentGateFinding(
                    "foundation_reassessment_gate_doc_phrase_missing",
                    f"reassessment gate boundary doc missing required phrase: {phrase}",
                )
            )
    for surface_label in EXPECTED_DOC_SURFACE_LABELS:
        if surface_label not in text:
            findings.append(
                ReassessmentGateFinding(
                    "foundation_reassessment_gate_doc_surface_missing",
                    f"reassessment gate boundary doc missing surface label: {surface_label}",
                )
            )
    findings.extend(validate_forbidden_value_patterns(text, "doc"))
    findings.extend(validate_forbidden_promotion_patterns(text, "doc"))
    return findings


def validate_packet(payload: dict[str, Any]) -> list[ReassessmentGateFinding]:
    """Return findings for reassessment gate witness drift."""

    findings: list[ReassessmentGateFinding] = []
    findings.extend(validate_root_contract(payload))
    findings.extend(validate_surfaces(payload.get("surfaces")))
    findings.extend(validate_forbidden_value_patterns(payload, "witness"))
    findings.extend(validate_forbidden_promotion_patterns(payload, "witness"))
    return findings


def validate_root_contract(payload: dict[str, Any]) -> list[ReassessmentGateFinding]:
    """Return findings for root-level reassessment gate witness drift."""

    findings: list[ReassessmentGateFinding] = []
    if set(payload) != EXPECTED_ROOT_KEYS:
        findings.append(
            ReassessmentGateFinding(
                "reassessment_gate_root_keys_invalid",
                f"root keys must be: {', '.join(sorted(EXPECTED_ROOT_KEYS))}",
            )
        )
    expected_values = {
        "witness_id": EXPECTED_WITNESS_ID,
        "schema_version": 1,
        "status": "AwaitingEvidence",
        "solver_outcome": "AwaitingEvidence",
        "reassessment_approved": False,
        "prerequisite_promotion_allowed": False,
        "deployment_start_allowed": False,
        "pilot_start_allowed": False,
        "external_action_allowed": False,
        "customer_access_allowed": False,
        "personal_data_collection_allowed": False,
        "legal_clearance_claimed": False,
        "company_formation_claimed": False,
        "patent_claimed": False,
        "money_movement_allowed": False,
        "secret_material_allowed": False,
        "external_publication_allowed": False,
        "deployment_allowed": False,
    }
    for key, expected_value in expected_values.items():
        if payload.get(key) != expected_value:
            findings.append(
                ReassessmentGateFinding(
                    "reassessment_gate_root_value_invalid",
                    f"{key} must be {expected_value!r}",
                )
            )
    if tuple(payload.get("blocked_claims") or ()) != EXPECTED_BLOCKED_CLAIMS:
        findings.append(
            ReassessmentGateFinding(
                "reassessment_gate_blocked_claims_invalid",
                f"blocked_claims must be: {', '.join(EXPECTED_BLOCKED_CLAIMS)}",
            )
        )
    if payload.get("next_action") != EXPECTED_NEXT_ACTION:
        findings.append(
            ReassessmentGateFinding(
                "reassessment_gate_next_action_invalid",
                "next_action must preserve the exact local-only non-promotion handoff",
            )
        )
    return findings


def validate_surfaces(surfaces: object) -> list[ReassessmentGateFinding]:
    """Return findings for reassessment gate surface witness drift."""

    findings: list[ReassessmentGateFinding] = []
    if not isinstance(surfaces, list) or not all(isinstance(surface, dict) for surface in surfaces):
        return [ReassessmentGateFinding("reassessment_gate_surfaces_invalid", "surfaces must be a list")]
    observed_surfaces = tuple(
        (surface.get("surface_id"), surface.get("surface_type"), surface.get("state"))
        for surface in surfaces
    )
    if observed_surfaces != EXPECTED_SURFACES:
        findings.append(
            ReassessmentGateFinding(
                "reassessment_gate_surface_inventory_invalid",
                "reassessment gate surface inventory does not match the expected set",
            )
        )
    surface_ids = [surface.get("surface_id") for surface in surfaces]
    if len(set(surface_ids)) != len(surface_ids):
        findings.append(ReassessmentGateFinding("reassessment_gate_surface_duplicate", "surface ids must be unique"))
    for surface in surfaces:
        surface_id = str(surface.get("surface_id", "<missing>"))
        if set(surface) != EXPECTED_SURFACE_KEYS:
            findings.append(
                ReassessmentGateFinding(
                    "reassessment_gate_surface_keys_invalid",
                    f"{surface_id} surface keys must be: {', '.join(sorted(EXPECTED_SURFACE_KEYS))}",
                )
            )
        if surface.get("state") != "AwaitingEvidence":
            findings.append(
                ReassessmentGateFinding(
                    "reassessment_gate_surface_state_invalid",
                    f"{surface_id} state must be AwaitingEvidence",
                )
            )
        if surface.get("evidence_ref") != "manual_preparation_pending":
            findings.append(
                ReassessmentGateFinding(
                    "reassessment_gate_surface_evidence_invalid",
                    f"{surface_id} evidence_ref must stay manual_preparation_pending",
                )
            )
        if not isinstance(surface.get("public_safe_note"), str) or not surface["public_safe_note"].strip():
            findings.append(
                ReassessmentGateFinding(
                    "reassessment_gate_surface_note_invalid",
                    f"{surface_id} public_safe_note must be a non-empty string",
                )
            )
        elif surface.get("public_safe_note") != EXPECTED_SURFACE_NOTES.get(surface_id):
            findings.append(
                ReassessmentGateFinding(
                    "reassessment_gate_surface_note_invalid",
                    f"{surface_id} public_safe_note must preserve the expected local-only boundary text",
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
) -> list[ReassessmentGateFinding]:
    """Return findings for private, legal, payment, secret, or deployment-shaped values."""

    serialized_value = serialize_for_pattern_scan(value)
    findings: list[ReassessmentGateFinding] = []
    for rule_id, pattern in FORBIDDEN_VALUE_PATTERNS:
        if pattern.search(serialized_value):
            findings.append(
                ReassessmentGateFinding(
                    "reassessment_gate_forbidden_value_pattern",
                    f"reassessment gate {artifact_label} contains forbidden value pattern: {rule_id}",
                )
            )
    return findings


def validate_forbidden_promotion_patterns(
    value: str | dict[str, Any],
    artifact_label: str,
) -> list[ReassessmentGateFinding]:
    """Return findings if the witness drifts into approval or exposure claims."""

    serialized_value = serialize_for_pattern_scan(value)
    findings: list[ReassessmentGateFinding] = []
    for rule_id, pattern in FORBIDDEN_PROMOTION_PATTERNS:
        if pattern.search(serialized_value):
            findings.append(
                ReassessmentGateFinding(
                    "reassessment_gate_forbidden_promotion_phrase",
                    f"reassessment gate {artifact_label} contains forbidden promotion pattern: {rule_id}",
                )
            )
    return findings


def validate_foundation_reassessment_gate_boundary(
    doc_path: Path = DEFAULT_DOC_PATH,
    packet_path: Path = DEFAULT_PACKET_PATH,
) -> list[ReassessmentGateFinding]:
    """Validate the Foundation Mode reassessment gate boundary artifacts."""

    doc_text = load_text(doc_path, "reassessment gate boundary doc")
    packet_payload = load_json_object(packet_path, "reassessment gate witness packet")
    return [
        *validate_doc_text(doc_text),
        *validate_packet(packet_payload),
    ]


def main(argv: list[str] | None = None) -> int:
    """Validate reassessment gate artifacts and print deterministic status."""

    parser = argparse.ArgumentParser(description="Validate Foundation Mode reassessment gate boundary artifacts.")
    parser.add_argument("--doc", type=Path, default=DEFAULT_DOC_PATH)
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET_PATH)
    args = parser.parse_args(argv)

    try:
        findings = validate_foundation_reassessment_gate_boundary(args.doc, args.packet)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"[FAIL] foundation_reassessment_gate_load: {exc}", file=sys.stderr)
        print("STATUS: failed", file=sys.stderr)
        return 1

    if findings:
        for finding in findings:
            print(f"[FAIL] {finding.rule_id}: {finding.message}", file=sys.stderr)
        print("STATUS: failed", file=sys.stderr)
        return 1
    print("[PASS] foundation_reassessment_gate_doc")
    print("[PASS] foundation_reassessment_gate_witness")
    print("STATUS: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
