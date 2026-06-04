#!/usr/bin/env python3
"""Validate the Foundation Mode operator-readiness boundary.

Purpose: keep solo-operator preparation local while capacity, schedule, skill,
team, hiring, delegation, incident coverage, support coverage, authority, and
deployment readiness claims remain blocked.
Governance scope: Foundation Mode, solo-operator posture, public-safe planning
witness, private-value exclusion, operational-readiness blocking, and
deployment blocking.
Dependencies: docs/FOUNDATION_OPERATOR_READINESS_BOUNDARY.md and
examples/foundation_operator_readiness_witness.awaiting_evidence.json plus the
operator stop-rule packet.
Invariants:
  - Validation is read-only.
  - The witness records local operator-readiness planning only.
  - No capacity verification, schedule readiness, skill readiness, team
    readiness, hiring readiness, delegation readiness, incident coverage,
    support coverage, legal-authority readiness, financial-authority readiness,
    private schedule, private health detail, or deployment claim is allowed.
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
DEFAULT_DOC_PATH = REPO_ROOT / "docs" / "FOUNDATION_OPERATOR_READINESS_BOUNDARY.md"
DEFAULT_PACKET_PATH = REPO_ROOT / "examples" / "foundation_operator_readiness_witness.awaiting_evidence.json"
DEFAULT_STOP_RULE_PATH = REPO_ROOT / "examples" / "foundation_operator_stop_rules.awaiting_evidence.json"

EXPECTED_WITNESS_ID = "foundation_operator_readiness_witness.awaiting_evidence.v1"
EXPECTED_STOP_RULE_ID = "foundation_operator_stop_rules.awaiting_evidence.v1"
EXPECTED_BLOCKED_CLAIMS = (
    "solo operator capacity verification",
    "schedule readiness",
    "skill readiness",
    "team readiness",
    "hiring readiness",
    "delegation readiness",
    "incident coverage readiness",
    "support coverage readiness",
    "legal authority readiness",
    "financial authority readiness",
    "private schedule recording",
    "private health recording",
    "deployment readiness",
)
EXPECTED_SURFACES = (
    ("solo_capacity_questions", "local_draft", "AwaitingEvidence"),
    ("time_budget_questions", "local_draft", "AwaitingEvidence"),
    ("skill_gap_questions", "local_draft", "AwaitingEvidence"),
    ("learning_plan_questions", "local_draft", "AwaitingEvidence"),
    ("decision_authority_questions", "local_draft", "AwaitingEvidence"),
    ("escalation_boundary_questions", "local_draft", "AwaitingEvidence"),
    ("fatigue_stop_rules", "local_draft", "AwaitingEvidence"),
    ("review_cadence_questions", "local_draft", "AwaitingEvidence"),
)
EXPECTED_STOP_RULES = (
    ("scope_expansion_stop", "local_draft", "AwaitingEvidence"),
    ("private_detail_stop", "local_draft", "AwaitingEvidence"),
    ("validation_failure_stop", "local_draft", "AwaitingEvidence"),
    ("external_boundary_stop", "local_draft", "AwaitingEvidence"),
    ("money_legal_stop", "local_draft", "AwaitingEvidence"),
    ("coverage_deployment_stop", "local_draft", "AwaitingEvidence"),
)
EXPECTED_ROOT_KEYS = {
    "blocked_claims",
    "delegation_ready_claimed",
    "deployment_allowed",
    "financial_authority_ready_claimed",
    "hiring_ready_claimed",
    "incident_coverage_ready_claimed",
    "legal_authority_ready_claimed",
    "next_action",
    "operator_capacity_verified",
    "operator_readiness_surfaces",
    "private_health_recording_allowed",
    "private_schedule_recording_allowed",
    "schedule_readiness_claimed",
    "schema_version",
    "skill_readiness_claimed",
    "solver_outcome",
    "status",
    "support_coverage_ready_claimed",
    "team_readiness_claimed",
    "witness_id",
}
EXPECTED_STOP_RULE_ROOT_KEYS = {
    "blocked_claims",
    "delegation_ready_claimed",
    "deployment_allowed",
    "financial_authority_ready_claimed",
    "hiring_ready_claimed",
    "incident_coverage_ready_claimed",
    "legal_authority_ready_claimed",
    "next_action",
    "operator_capacity_verified",
    "private_health_recording_allowed",
    "private_schedule_recording_allowed",
    "schema_version",
    "skill_readiness_claimed",
    "solver_outcome",
    "status",
    "stop_rule_id",
    "stop_rule_scope",
    "stop_rules",
    "support_coverage_ready_claimed",
    "team_readiness_claimed",
}
EXPECTED_SURFACE_KEYS = {
    "evidence_ref",
    "public_safe_note",
    "state",
    "surface_id",
    "surface_type",
}
EXPECTED_STOP_RULE_KEYS = {
    "evidence_ref",
    "public_safe_note",
    "state",
    "stop_id",
    "stop_type",
}
REQUIRED_DOC_PHRASES = (
    "Foundation Operator Readiness Boundary",
    "Witness packet: [`../examples/foundation_operator_readiness_witness.awaiting_evidence.json`]",
    "Stop-rule packet: [`../examples/foundation_operator_stop_rules.awaiting_evidence.json`]",
    "Rule: Operator-readiness preparation is a local planning boundary, not",
    "No solo-operator capacity verification, schedule-readiness claim,",
    "operator_readiness_boundary_state=AwaitingEvidence",
    "operator_stop_rules_state=AwaitingEvidence",
    "operator_capacity_verified=false",
    "schedule_readiness_claimed=false",
    "team_readiness_claimed=false",
    "deployment_allowed=false",
    "python scripts/validate_foundation_operator_readiness_boundary.py",
)
FORBIDDEN_VALUE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("url_value", re.compile(r"https?://", re.IGNORECASE)),
    ("email_value", re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)),
    ("private_path", re.compile(r"\b[A-Za-z]:[\\/]|\\\\", re.IGNORECASE)),
    (
        "private_schedule_assignment",
        re.compile(r"\b(?:schedule|availability|calendar|time)[_ -]?(?:target|value|slot|ref)?\s*=", re.IGNORECASE),
    ),
    (
        "private_health_assignment",
        re.compile(r"\b(?:health|medical|fatigue|sleep|illness)[_ -]?(?:target|value|status|ref)?\s*=", re.IGNORECASE),
    ),
    (
        "team_target_assignment",
        re.compile(r"\b(?:team|member|hire|hiring|contractor)[_ -]?(?:target|id|ref|value)?\s*=", re.IGNORECASE),
    ),
    (
        "delegation_target_assignment",
        re.compile(r"\b(?:delegate|delegation|assignee)[_ -]?(?:target|id|ref|value)?\s*=", re.IGNORECASE),
    ),
    (
        "coverage_target_assignment",
        re.compile(r"\b(?:incident|support|coverage|sla)[_ -]?(?:target|id|ref|value)?\s*=", re.IGNORECASE),
    ),
    (
        "authority_target_assignment",
        re.compile(r"\b(?:legal|financial|authority)[_ -]?(?:target|id|ref|value)?\s*=", re.IGNORECASE),
    ),
)
FORBIDDEN_PROMOTION_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("operator_ready", re.compile(r"\boperator\s+(?:is\s+)?ready\b", re.IGNORECASE)),
    ("capacity_verified", re.compile(r"\bcapacity\s+(?:is\s+)?verified\b", re.IGNORECASE)),
    ("schedule_ready", re.compile(r"\bschedule\s+(?:is\s+)?ready\b", re.IGNORECASE)),
    ("skill_ready", re.compile(r"\bskill\s+(?:is\s+)?ready\b", re.IGNORECASE)),
    ("team_ready", re.compile(r"\bteam\s+(?:is\s+)?ready\b", re.IGNORECASE)),
    ("hiring_ready", re.compile(r"\bhiring\s+(?:is\s+)?ready\b", re.IGNORECASE)),
    ("delegation_ready", re.compile(r"\bdelegation\s+(?:is\s+)?ready\b", re.IGNORECASE)),
    ("incident_coverage_ready", re.compile(r"\bincident\s+coverage\s+(?:is\s+)?ready\b", re.IGNORECASE)),
    ("support_coverage_ready", re.compile(r"\bsupport\s+coverage\s+(?:is\s+)?ready\b", re.IGNORECASE)),
    ("legal_authority_ready", re.compile(r"\blegal\s+authority\s+(?:is\s+)?ready\b", re.IGNORECASE)),
    ("financial_authority_ready", re.compile(r"\bfinancial\s+authority\s+(?:is\s+)?ready\b", re.IGNORECASE)),
    ("deployment_ready", re.compile(r"\bdeployment\s+(?:is\s+)?ready\b", re.IGNORECASE)),
)


@dataclass(frozen=True, slots=True)
class OperatorReadinessFinding:
    """One deterministic operator-readiness boundary validation finding."""

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


def validate_doc_text(text: str) -> list[OperatorReadinessFinding]:
    """Return findings for missing operator-readiness documentation anchors."""

    findings: list[OperatorReadinessFinding] = []
    for phrase in REQUIRED_DOC_PHRASES:
        if phrase not in text:
            findings.append(
                OperatorReadinessFinding(
                    "foundation_operator_readiness_doc_phrase_missing",
                    f"operator-readiness boundary doc missing required phrase: {phrase}",
                )
            )
    return findings


def validate_packet(payload: dict[str, Any]) -> list[OperatorReadinessFinding]:
    """Return findings for operator-readiness witness drift."""

    findings: list[OperatorReadinessFinding] = []
    findings.extend(validate_root_contract(payload))
    findings.extend(validate_operator_readiness_surfaces(payload.get("operator_readiness_surfaces")))
    findings.extend(validate_forbidden_value_patterns(payload))
    findings.extend(validate_forbidden_promotion_patterns(payload))
    return findings


def validate_stop_rule_packet(payload: dict[str, Any]) -> list[OperatorReadinessFinding]:
    """Return findings for operator stop-rule packet drift."""

    findings: list[OperatorReadinessFinding] = []
    findings.extend(validate_stop_rule_root_contract(payload))
    findings.extend(validate_stop_rules(payload.get("stop_rules")))
    findings.extend(validate_forbidden_value_patterns(payload))
    findings.extend(validate_forbidden_promotion_patterns(payload))
    return findings


def validate_root_contract(payload: dict[str, Any]) -> list[OperatorReadinessFinding]:
    """Return findings for root-level operator-readiness witness drift."""

    findings: list[OperatorReadinessFinding] = []
    if set(payload) != EXPECTED_ROOT_KEYS:
        findings.append(
            OperatorReadinessFinding(
                "operator_readiness_root_keys_invalid",
                f"root keys must be: {', '.join(sorted(EXPECTED_ROOT_KEYS))}",
            )
        )
    expected_values = {
        "witness_id": EXPECTED_WITNESS_ID,
        "schema_version": 1,
        "status": "AwaitingEvidence",
        "solver_outcome": "AwaitingEvidence",
        "operator_capacity_verified": False,
        "schedule_readiness_claimed": False,
        "skill_readiness_claimed": False,
        "team_readiness_claimed": False,
        "hiring_ready_claimed": False,
        "delegation_ready_claimed": False,
        "incident_coverage_ready_claimed": False,
        "support_coverage_ready_claimed": False,
        "legal_authority_ready_claimed": False,
        "financial_authority_ready_claimed": False,
        "private_schedule_recording_allowed": False,
        "private_health_recording_allowed": False,
        "deployment_allowed": False,
    }
    for key, expected_value in expected_values.items():
        if payload.get(key) != expected_value:
            findings.append(
                OperatorReadinessFinding(
                    "operator_readiness_root_value_invalid",
                    f"{key} must be {expected_value!r}",
                )
            )
    if tuple(payload.get("blocked_claims") or ()) != EXPECTED_BLOCKED_CLAIMS:
        findings.append(
            OperatorReadinessFinding(
                "operator_readiness_blocked_claims_invalid",
                f"blocked_claims must be: {', '.join(EXPECTED_BLOCKED_CLAIMS)}",
            )
        )
    next_action = payload.get("next_action")
    if not isinstance(next_action, str) or "do not claim capacity" not in next_action:
        findings.append(
            OperatorReadinessFinding(
                "operator_readiness_next_action_invalid",
                "next_action must preserve the closed operator-readiness boundary",
            )
        )
    return findings


def validate_stop_rule_root_contract(payload: dict[str, Any]) -> list[OperatorReadinessFinding]:
    """Return findings for root-level operator stop-rule packet drift."""

    findings: list[OperatorReadinessFinding] = []
    if set(payload) != EXPECTED_STOP_RULE_ROOT_KEYS:
        findings.append(
            OperatorReadinessFinding(
                "operator_stop_rule_root_keys_invalid",
                f"root keys must be: {', '.join(sorted(EXPECTED_STOP_RULE_ROOT_KEYS))}",
            )
        )
    expected_values = {
        "stop_rule_id": EXPECTED_STOP_RULE_ID,
        "schema_version": 1,
        "status": "AwaitingEvidence",
        "solver_outcome": "AwaitingEvidence",
        "operator_capacity_verified": False,
        "skill_readiness_claimed": False,
        "team_readiness_claimed": False,
        "hiring_ready_claimed": False,
        "delegation_ready_claimed": False,
        "incident_coverage_ready_claimed": False,
        "support_coverage_ready_claimed": False,
        "legal_authority_ready_claimed": False,
        "financial_authority_ready_claimed": False,
        "private_schedule_recording_allowed": False,
        "private_health_recording_allowed": False,
        "deployment_allowed": False,
    }
    for key, expected_value in expected_values.items():
        if payload.get(key) != expected_value:
            findings.append(
                OperatorReadinessFinding(
                    "operator_stop_rule_root_value_invalid",
                    f"{key} must be {expected_value!r}",
                )
            )
    if tuple(payload.get("blocked_claims") or ()) != EXPECTED_BLOCKED_CLAIMS:
        findings.append(
            OperatorReadinessFinding(
                "operator_stop_rule_blocked_claims_invalid",
                f"blocked_claims must be: {', '.join(EXPECTED_BLOCKED_CLAIMS)}",
            )
        )
    stop_rule_scope = payload.get("stop_rule_scope")
    if not isinstance(stop_rule_scope, str) or "public-safe local stop rules" not in stop_rule_scope:
        findings.append(
            OperatorReadinessFinding(
                "operator_stop_rule_scope_invalid",
                "stop_rule_scope must preserve public-safe local stop rules",
            )
        )
    next_action = payload.get("next_action")
    if not isinstance(next_action, str) or "do not claim capacity" not in next_action:
        findings.append(
            OperatorReadinessFinding(
                "operator_stop_rule_next_action_invalid",
                "next_action must keep stop rules from promoting operator readiness",
            )
        )
    return findings


def validate_operator_readiness_surfaces(operator_readiness_surfaces: object) -> list[OperatorReadinessFinding]:
    """Return findings for operator-readiness surface witness drift."""

    findings: list[OperatorReadinessFinding] = []
    if not isinstance(operator_readiness_surfaces, list) or not all(
        isinstance(surface, dict) for surface in operator_readiness_surfaces
    ):
        return [
            OperatorReadinessFinding(
                "operator_readiness_surfaces_invalid",
                "operator_readiness_surfaces must be a list of objects",
            )
        ]
    observed_surfaces = tuple(
        (surface.get("surface_id"), surface.get("surface_type"), surface.get("state"))
        for surface in operator_readiness_surfaces
    )
    if observed_surfaces != EXPECTED_SURFACES:
        findings.append(
            OperatorReadinessFinding(
                "operator_readiness_surface_inventory_invalid",
                "operator-readiness surface inventory does not match the Foundation Mode operator set",
            )
        )
    surface_ids = [surface.get("surface_id") for surface in operator_readiness_surfaces]
    if len(set(surface_ids)) != len(surface_ids):
        findings.append(OperatorReadinessFinding("operator_readiness_surface_duplicate", "surface ids must be unique"))
    for surface in operator_readiness_surfaces:
        surface_id = str(surface.get("surface_id", "<missing>"))
        if set(surface) != EXPECTED_SURFACE_KEYS:
            findings.append(
                OperatorReadinessFinding(
                    "operator_readiness_surface_keys_invalid",
                    f"{surface_id} surface keys must be: {', '.join(sorted(EXPECTED_SURFACE_KEYS))}",
                )
            )
        if surface.get("state") != "AwaitingEvidence":
            findings.append(
                OperatorReadinessFinding(
                    "operator_readiness_surface_state_invalid",
                    f"{surface_id} state must be AwaitingEvidence",
                )
            )
        if surface.get("evidence_ref") != "manual_preparation_pending":
            findings.append(
                OperatorReadinessFinding(
                    "operator_readiness_surface_evidence_invalid",
                    f"{surface_id} evidence_ref must stay manual_preparation_pending in the committed packet",
                )
            )
        if not isinstance(surface.get("public_safe_note"), str) or not surface["public_safe_note"].strip():
            findings.append(
                OperatorReadinessFinding(
                    "operator_readiness_surface_note_invalid",
                    f"{surface_id} public_safe_note must be a non-empty string",
                )
            )
    return findings


def validate_stop_rules(stop_rules: object) -> list[OperatorReadinessFinding]:
    """Return findings for operator stop-rule inventory drift."""

    findings: list[OperatorReadinessFinding] = []
    if not isinstance(stop_rules, list) or not all(isinstance(stop_rule, dict) for stop_rule in stop_rules):
        return [
            OperatorReadinessFinding(
                "operator_stop_rules_invalid",
                "stop_rules must be a list of objects",
            )
        ]
    observed_stop_rules = tuple(
        (stop_rule.get("stop_id"), stop_rule.get("stop_type"), stop_rule.get("state"))
        for stop_rule in stop_rules
    )
    if observed_stop_rules != EXPECTED_STOP_RULES:
        findings.append(
            OperatorReadinessFinding(
                "operator_stop_rule_inventory_invalid",
                "operator stop-rule inventory does not match the Foundation Mode stop set",
            )
        )
    stop_ids = [stop_rule.get("stop_id") for stop_rule in stop_rules]
    if len(set(stop_ids)) != len(stop_ids):
        findings.append(OperatorReadinessFinding("operator_stop_rule_duplicate", "stop ids must be unique"))
    for stop_rule in stop_rules:
        stop_id = str(stop_rule.get("stop_id", "<missing>"))
        if set(stop_rule) != EXPECTED_STOP_RULE_KEYS:
            findings.append(
                OperatorReadinessFinding(
                    "operator_stop_rule_keys_invalid",
                    f"{stop_id} stop rule keys must be: {', '.join(sorted(EXPECTED_STOP_RULE_KEYS))}",
                )
            )
        if stop_rule.get("state") != "AwaitingEvidence":
            findings.append(
                OperatorReadinessFinding(
                    "operator_stop_rule_state_invalid",
                    f"{stop_id} state must be AwaitingEvidence",
                )
            )
        if stop_rule.get("evidence_ref") != "manual_preparation_pending":
            findings.append(
                OperatorReadinessFinding(
                    "operator_stop_rule_evidence_invalid",
                    f"{stop_id} evidence_ref must stay manual_preparation_pending in the committed packet",
                )
            )
        if not isinstance(stop_rule.get("public_safe_note"), str) or not stop_rule["public_safe_note"].strip():
            findings.append(
                OperatorReadinessFinding(
                    "operator_stop_rule_note_invalid",
                    f"{stop_id} public_safe_note must be a non-empty string",
                )
            )
    return findings


def validate_forbidden_value_patterns(payload: dict[str, Any]) -> list[OperatorReadinessFinding]:
    """Return findings for private schedule, health, team, coverage, or authority-shaped values."""

    serialized_payload = json.dumps(payload, sort_keys=True)
    findings: list[OperatorReadinessFinding] = []
    for rule_id, pattern in FORBIDDEN_VALUE_PATTERNS:
        if pattern.search(serialized_payload):
            findings.append(
                OperatorReadinessFinding(
                    "operator_readiness_forbidden_private_value_pattern",
                    f"operator-readiness witness contains forbidden value pattern: {rule_id}",
                )
            )
    return findings


def validate_forbidden_promotion_patterns(payload: dict[str, Any]) -> list[OperatorReadinessFinding]:
    """Return findings if the witness drifts into operational-readiness claims."""

    serialized_payload = json.dumps(payload, sort_keys=True)
    findings: list[OperatorReadinessFinding] = []
    for rule_id, pattern in FORBIDDEN_PROMOTION_PATTERNS:
        if pattern.search(serialized_payload):
            findings.append(
                OperatorReadinessFinding(
                    "operator_readiness_forbidden_promotion_phrase",
                    f"operator-readiness witness contains forbidden promotion pattern: {rule_id}",
                )
            )
    return findings


def validate_foundation_operator_readiness_boundary(
    doc_path: Path = DEFAULT_DOC_PATH,
    packet_path: Path = DEFAULT_PACKET_PATH,
    stop_rule_path: Path = DEFAULT_STOP_RULE_PATH,
) -> list[OperatorReadinessFinding]:
    """Validate the Foundation Mode operator-readiness boundary artifacts."""

    doc_text = load_text(doc_path, "operator-readiness boundary doc")
    packet_payload = load_json_object(packet_path, "operator-readiness witness packet")
    stop_rule_payload = load_json_object(stop_rule_path, "operator stop-rule packet")
    return [
        *validate_doc_text(doc_text),
        *validate_packet(packet_payload),
        *validate_stop_rule_packet(stop_rule_payload),
    ]


def main(argv: list[str] | None = None) -> int:
    """Validate operator-readiness boundary artifacts and print deterministic status."""

    parser = argparse.ArgumentParser(description="Validate Foundation Mode operator-readiness boundary artifacts.")
    parser.add_argument("--doc", type=Path, default=DEFAULT_DOC_PATH)
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET_PATH)
    parser.add_argument("--stop-rules", type=Path, default=DEFAULT_STOP_RULE_PATH)
    args = parser.parse_args(argv)

    try:
        findings = validate_foundation_operator_readiness_boundary(args.doc, args.packet, args.stop_rules)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"[FAIL] foundation_operator_readiness_load: {exc}", file=sys.stderr)
        print("STATUS: failed", file=sys.stderr)
        return 1

    if findings:
        for finding in findings:
            print(f"[FAIL] {finding.rule_id}: {finding.message}", file=sys.stderr)
        print("STATUS: failed", file=sys.stderr)
        return 1
    print("[PASS] foundation_operator_readiness_doc")
    print("[PASS] foundation_operator_readiness_witness")
    print("[PASS] foundation_operator_stop_rules")
    print("STATUS: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
