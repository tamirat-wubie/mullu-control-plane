#!/usr/bin/env python3
"""Validate the Foundation Mode solo daily loop boundary.

Purpose: keep one-person daily progression local, public-safe, and evidence
bound while private schedule recording, productivity claims, external action,
spending, legal/business action, source-control publication, and deployment
claims remain blocked.
Governance scope: Foundation Mode, solo daily triage, one-task selection,
prerequisite alignment, local evidence capture, validation checkpoints, stop
conditions, handoff notes, carryover notes, private-value exclusion, and
external-action blocking.
Dependencies: docs/FOUNDATION_SOLO_DAILY_LOOP_BOUNDARY.md and
examples/foundation_solo_daily_loop_witness.awaiting_evidence.json.
Invariants:
  - Validation is read-only.
  - The witness records local daily-loop preparation only.
  - No productivity readiness, schedule readiness, private calendar, private
    health, completion guarantee, team coverage, support coverage, roadmap,
    deadline, external action, spending, legal/business action, secret use,
    credential use, source-control publication, or deployment claim is allowed.
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
DEFAULT_DOC_PATH = REPO_ROOT / "docs" / "FOUNDATION_SOLO_DAILY_LOOP_BOUNDARY.md"
DEFAULT_PACKET_PATH = REPO_ROOT / "examples" / "foundation_solo_daily_loop_witness.awaiting_evidence.json"

EXPECTED_WITNESS_ID = "foundation_solo_daily_loop_witness.awaiting_evidence.v1"
EXPECTED_BLOCKED_CLAIMS = (
    "daily productivity readiness",
    "schedule readiness",
    "private calendar recording",
    "private health tracking",
    "task-completion guarantee",
    "team coverage",
    "support coverage",
    "roadmap commitment",
    "deadline promise",
    "external action",
    "spending",
    "legal/business action",
    "secret use",
    "credential use",
    "source-control publication",
    "deployment readiness",
)
EXPECTED_SURFACES = (
    ("session_intake", "local_draft", "AwaitingEvidence"),
    ("one_task_selection", "local_draft", "AwaitingEvidence"),
    ("prerequisite_alignment", "local_draft", "AwaitingEvidence"),
    ("risk_and_stop_check", "local_draft", "AwaitingEvidence"),
    ("local_evidence_capture", "local_draft", "AwaitingEvidence"),
    ("validation_checkpoint", "local_draft", "AwaitingEvidence"),
    ("handoff_note", "local_draft", "AwaitingEvidence"),
    ("carryover_note", "local_draft", "AwaitingEvidence"),
)
EXPECTED_ROOT_KEYS = {
    "blocked_claims",
    "credential_use_allowed",
    "daily_productivity_readiness_claimed",
    "deadline_promise_claimed",
    "deployment_allowed",
    "external_action_allowed",
    "legal_business_action_allowed",
    "next_action",
    "private_calendar_recording_allowed",
    "private_health_tracking_allowed",
    "roadmap_commitment_claimed",
    "schedule_readiness_claimed",
    "schema_version",
    "secret_use_allowed",
    "solo_daily_loop_surfaces",
    "solver_outcome",
    "source_control_publication_allowed",
    "spending_allowed",
    "status",
    "support_coverage_claimed",
    "task_completion_guaranteed",
    "team_coverage_claimed",
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
    "Foundation Solo Daily Loop Boundary",
    "Witness packet: [`../examples/foundation_solo_daily_loop_witness.awaiting_evidence.json`]",
    "Rule: Solo daily loop preparation is a public-safe local planning boundary, not",
    "No daily productivity readiness, schedule-readiness claim, private calendar",
    "solo_daily_loop_boundary_state=AwaitingEvidence",
    "daily_productivity_readiness_claimed=false",
    "schedule_readiness_claimed=false",
    "private_calendar_recording_allowed=false",
    "private_health_tracking_allowed=false",
    "task_completion_guaranteed=false",
    "source_control_publication_allowed=false",
    "deployment_allowed=false",
    "python scripts/validate_foundation_solo_daily_loop_boundary.py",
)
FORBIDDEN_VALUE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("url_value", re.compile(r"https?://", re.IGNORECASE)),
    ("email_value", re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)),
    ("private_path", re.compile(r"\b[A-Za-z]:[\\/]|\\\\", re.IGNORECASE)),
    (
        "private_calendar_assignment",
        re.compile(r"\b(?:calendar|schedule|availability|time)[_ -]?(?:target|value|slot|ref)?\s*=", re.IGNORECASE),
    ),
    (
        "private_health_assignment",
        re.compile(r"\b(?:health|medical|fatigue|sleep|illness)[_ -]?(?:target|value|status|ref)?\s*=", re.IGNORECASE),
    ),
    (
        "customer_assignment",
        re.compile(r"\b(?:customer|pilot|participant|user)[_ -]?(?:id|name|email|ref|value|target)?\s*=", re.IGNORECASE),
    ),
    (
        "provider_assignment",
        re.compile(r"\b(?:provider|account|tenant|project|dns|domain)[_ -]?(?:id|ref|target|value)?\s*=", re.IGNORECASE),
    ),
    (
        "secret_or_credential_assignment",
        re.compile(r"\b(?:password|secret|token|api[_ -]?key|credential|client[_ -]?secret)\s*=", re.IGNORECASE),
    ),
    ("private_key_material", re.compile(r"BEGIN [A-Z ]*PRIVATE KEY")),
    (
        "deployment_assignment",
        re.compile(r"\b(?:deploy|deployment|production|staging)[_ -]?(?:target|url|ref|value|status)?\s*=", re.IGNORECASE),
    ),
    (
        "spending_assignment",
        re.compile(r"\b(?:budget|billing|payment|invoice|purchase|spend|subscription)[_ -]?(?:id|ref|target|value|status)?\s*=", re.IGNORECASE),
    ),
    (
        "legal_assignment",
        re.compile(r"\b(?:legal|company|patent|trademark|tax|terms)[_ -]?(?:id|ref|target|value|status)?\s*=", re.IGNORECASE),
    ),
    (
        "source_control_assignment",
        re.compile(r"\b(?:commit|push|pull[_ -]?request|release)[_ -]?(?:id|ref|target|value|status)?\s*=", re.IGNORECASE),
    ),
    (
        "roadmap_or_deadline_assignment",
        re.compile(r"\b(?:roadmap|deadline|delivery[_ -]?date|launch[_ -]?date)[_ -]?(?:id|ref|target|value|status)?\s*=", re.IGNORECASE),
    ),
)
FORBIDDEN_PROMOTION_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("daily_loop_ready", re.compile(r"\bdaily\s+loop\s+(?:is\s+)?ready\b", re.IGNORECASE)),
    ("productivity_ready", re.compile(r"\bproductivity\s+(?:is\s+)?ready\b", re.IGNORECASE)),
    ("schedule_ready", re.compile(r"\bschedule\s+(?:is\s+)?ready\b", re.IGNORECASE)),
    ("task_completion_guaranteed", re.compile(r"\btask\s+completion\s+(?:is\s+)?guaranteed\b", re.IGNORECASE)),
    ("team_coverage_ready", re.compile(r"\bteam\s+coverage\s+(?:is\s+)?ready\b", re.IGNORECASE)),
    ("support_coverage_ready", re.compile(r"\bsupport\s+coverage\s+(?:is\s+)?ready\b", re.IGNORECASE)),
    ("roadmap_committed", re.compile(r"\broadmap\s+(?:is\s+)?committed\b", re.IGNORECASE)),
    ("deadline_promised", re.compile(r"\bdeadline\s+(?:is\s+)?promised\b", re.IGNORECASE)),
    ("external_action_approved", re.compile(r"\bexternal\s+action\s+(?:is\s+)?approved\b", re.IGNORECASE)),
    ("spending_approved", re.compile(r"\bspending\s+(?:is\s+)?approved\b", re.IGNORECASE)),
    ("legal_business_ready", re.compile(r"\blegal\s+business\s+(?:is\s+)?ready\b", re.IGNORECASE)),
    ("source_control_published", re.compile(r"\bsource\s+control\s+(?:is\s+)?published\b", re.IGNORECASE)),
    ("deployment_ready", re.compile(r"\bdeployment\s+(?:is\s+)?ready\b", re.IGNORECASE)),
)


@dataclass(frozen=True, slots=True)
class SoloDailyLoopFinding:
    """One deterministic solo daily loop boundary validation finding."""

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


def validate_doc_text(text: str) -> list[SoloDailyLoopFinding]:
    """Return findings for missing solo daily loop documentation anchors."""

    findings: list[SoloDailyLoopFinding] = []
    for phrase in REQUIRED_DOC_PHRASES:
        if phrase not in text:
            findings.append(
                SoloDailyLoopFinding(
                    "foundation_solo_daily_loop_doc_phrase_missing",
                    f"solo daily loop boundary doc missing required phrase: {phrase}",
                )
            )
    return findings


def validate_packet(payload: dict[str, Any]) -> list[SoloDailyLoopFinding]:
    """Return findings for solo daily loop witness drift."""

    findings: list[SoloDailyLoopFinding] = []
    findings.extend(validate_root_contract(payload))
    findings.extend(validate_solo_daily_loop_surfaces(payload.get("solo_daily_loop_surfaces")))
    findings.extend(validate_forbidden_value_patterns(payload))
    findings.extend(validate_forbidden_promotion_patterns(payload))
    return findings


def validate_root_contract(payload: dict[str, Any]) -> list[SoloDailyLoopFinding]:
    """Return findings for root-level solo daily loop witness drift."""

    findings: list[SoloDailyLoopFinding] = []
    if set(payload) != EXPECTED_ROOT_KEYS:
        findings.append(
            SoloDailyLoopFinding(
                "solo_daily_loop_root_keys_invalid",
                f"root keys must be: {', '.join(sorted(EXPECTED_ROOT_KEYS))}",
            )
        )
    expected_values = {
        "witness_id": EXPECTED_WITNESS_ID,
        "schema_version": 1,
        "status": "AwaitingEvidence",
        "solver_outcome": "AwaitingEvidence",
        "daily_productivity_readiness_claimed": False,
        "schedule_readiness_claimed": False,
        "private_calendar_recording_allowed": False,
        "private_health_tracking_allowed": False,
        "task_completion_guaranteed": False,
        "team_coverage_claimed": False,
        "support_coverage_claimed": False,
        "roadmap_commitment_claimed": False,
        "deadline_promise_claimed": False,
        "external_action_allowed": False,
        "spending_allowed": False,
        "legal_business_action_allowed": False,
        "secret_use_allowed": False,
        "credential_use_allowed": False,
        "source_control_publication_allowed": False,
        "deployment_allowed": False,
    }
    for key, expected_value in expected_values.items():
        if payload.get(key) != expected_value:
            findings.append(
                SoloDailyLoopFinding(
                    "solo_daily_loop_root_value_invalid",
                    f"{key} must be {expected_value!r}",
                )
            )
    if tuple(payload.get("blocked_claims") or ()) != EXPECTED_BLOCKED_CLAIMS:
        findings.append(
            SoloDailyLoopFinding(
                "solo_daily_loop_blocked_claims_invalid",
                f"blocked_claims must be: {', '.join(EXPECTED_BLOCKED_CLAIMS)}",
            )
        )
    next_action = payload.get("next_action")
    if not isinstance(next_action, str) or "pick one local-safe task" not in next_action:
        findings.append(
            SoloDailyLoopFinding(
                "solo_daily_loop_next_action_invalid",
                "next_action must preserve one local-safe daily-loop task selection",
            )
        )
    return findings


def validate_solo_daily_loop_surfaces(surfaces: object) -> list[SoloDailyLoopFinding]:
    """Return findings for solo daily loop surface drift."""

    findings: list[SoloDailyLoopFinding] = []
    if not isinstance(surfaces, list) or not all(isinstance(surface, dict) for surface in surfaces):
        return [SoloDailyLoopFinding("solo_daily_loop_surfaces_invalid", "surfaces must be a list of objects")]
    observed_surfaces = tuple(
        (surface.get("surface_id"), surface.get("surface_type"), surface.get("state"))
        for surface in surfaces
    )
    if observed_surfaces != EXPECTED_SURFACES:
        findings.append(
            SoloDailyLoopFinding(
                "solo_daily_loop_surface_inventory_invalid",
                "solo daily loop surface inventory does not match the Foundation Mode loop set",
            )
        )
    surface_ids = [surface.get("surface_id") for surface in surfaces]
    if len(set(surface_ids)) != len(surface_ids):
        findings.append(SoloDailyLoopFinding("solo_daily_loop_surface_duplicate", "surface ids must be unique"))
    for surface in surfaces:
        surface_id = str(surface.get("surface_id", "<missing>"))
        if set(surface) != EXPECTED_SURFACE_KEYS:
            findings.append(
                SoloDailyLoopFinding(
                    "solo_daily_loop_surface_keys_invalid",
                    f"{surface_id} surface keys must be: {', '.join(sorted(EXPECTED_SURFACE_KEYS))}",
                )
            )
        if surface.get("state") != "AwaitingEvidence":
            findings.append(
                SoloDailyLoopFinding(
                    "solo_daily_loop_surface_state_invalid",
                    f"{surface_id} state must be AwaitingEvidence",
                )
            )
        if surface.get("evidence_ref") != "manual_preparation_pending":
            findings.append(
                SoloDailyLoopFinding(
                    "solo_daily_loop_surface_evidence_invalid",
                    f"{surface_id} evidence_ref must stay manual_preparation_pending in the committed packet",
                )
            )
        if not isinstance(surface.get("public_safe_note"), str) or not surface["public_safe_note"].strip():
            findings.append(
                SoloDailyLoopFinding(
                    "solo_daily_loop_surface_note_invalid",
                    f"{surface_id} public_safe_note must be a non-empty string",
                )
            )
    return findings


def validate_forbidden_value_patterns(payload: dict[str, Any]) -> list[SoloDailyLoopFinding]:
    """Return findings for external, private, account, secret, or commitment-shaped values."""

    serialized_payload = json.dumps(payload, sort_keys=True)
    findings: list[SoloDailyLoopFinding] = []
    for rule_id, pattern in FORBIDDEN_VALUE_PATTERNS:
        if pattern.search(serialized_payload):
            findings.append(
                SoloDailyLoopFinding(
                    "solo_daily_loop_forbidden_private_value_pattern",
                    f"solo daily loop witness contains forbidden value pattern: {rule_id}",
                )
            )
    return findings


def validate_forbidden_promotion_patterns(payload: dict[str, Any]) -> list[SoloDailyLoopFinding]:
    """Return findings if the witness drifts into readiness-promotion phrases."""

    serialized_payload = json.dumps(payload, sort_keys=True)
    findings: list[SoloDailyLoopFinding] = []
    for rule_id, pattern in FORBIDDEN_PROMOTION_PATTERNS:
        if pattern.search(serialized_payload):
            findings.append(
                SoloDailyLoopFinding(
                    "solo_daily_loop_forbidden_promotion_phrase",
                    f"solo daily loop witness contains forbidden promotion pattern: {rule_id}",
                )
            )
    return findings


def validate_foundation_solo_daily_loop_boundary(
    doc_path: Path = DEFAULT_DOC_PATH,
    packet_path: Path = DEFAULT_PACKET_PATH,
) -> list[SoloDailyLoopFinding]:
    """Validate the Foundation Mode solo daily loop boundary artifacts."""

    doc_text = load_text(doc_path, "solo daily loop boundary doc")
    packet_payload = load_json_object(packet_path, "solo daily loop witness packet")
    return [
        *validate_doc_text(doc_text),
        *validate_packet(packet_payload),
    ]


def main(argv: list[str] | None = None) -> int:
    """Validate solo daily loop boundary artifacts and print deterministic status."""

    parser = argparse.ArgumentParser(description="Validate Foundation Mode solo daily loop boundary artifacts.")
    parser.add_argument("--doc", type=Path, default=DEFAULT_DOC_PATH)
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET_PATH)
    args = parser.parse_args(argv)

    try:
        findings = validate_foundation_solo_daily_loop_boundary(args.doc, args.packet)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"[FAIL] foundation_solo_daily_loop_load: {exc}", file=sys.stderr)
        print("STATUS: failed", file=sys.stderr)
        return 1

    if findings:
        for finding in findings:
            print(f"[FAIL] {finding.rule_id}: {finding.message}", file=sys.stderr)
        print("STATUS: failed", file=sys.stderr)
        return 1
    print("[PASS] foundation_solo_daily_loop_doc")
    print("[PASS] foundation_solo_daily_loop_witness")
    print("STATUS: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
