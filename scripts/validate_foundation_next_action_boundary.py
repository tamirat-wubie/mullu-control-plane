#!/usr/bin/env python3
"""Validate the Foundation Mode next-action boundary.

Purpose: keep broad continuation requests local, atomic, and public-safe while
external action, deployment, publication, spending, customer action,
legal/business action, claim promotion, secret use, credential use, service
activation, source-control publication, roadmap commitment, and deadline
promise remain blocked.
Governance scope: Foundation Mode, continuation triage, smallest prerequisite
selection, dependency checks, local edit scope, verification planning, stop
rules, receipt planning, handoff summaries, private-value exclusion, and
external-action blocking.
Dependencies: docs/FOUNDATION_NEXT_ACTION_BOUNDARY.md and
examples/foundation_next_action_witness.awaiting_evidence.json.
Invariants:
  - Validation is read-only.
  - The witness records next-action preparation only.
  - No broad continuation execution, external action, deployment, publication,
    spending, customer action, legal/business action, claim promotion, secret
    use, credential use, service activation, source-control publication,
    roadmap commitment, or deadline promise is allowed.
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
DEFAULT_DOC_PATH = REPO_ROOT / "docs" / "FOUNDATION_NEXT_ACTION_BOUNDARY.md"
DEFAULT_PACKET_PATH = REPO_ROOT / "examples" / "foundation_next_action_witness.awaiting_evidence.json"

EXPECTED_WITNESS_ID = "foundation_next_action_witness.awaiting_evidence.v1"
EXPECTED_BLOCKED_CLAIMS = (
    "broad continuation execution",
    "external action",
    "deployment readiness",
    "external publication",
    "spending",
    "customer action",
    "legal/business action",
    "claim promotion",
    "secret use",
    "credential use",
    "service activation",
    "source-control publication",
    "roadmap commitment",
    "deadline promise",
)
EXPECTED_SURFACES = (
    ("continue_request_triage", "local_draft", "AwaitingEvidence"),
    ("smallest_prerequisite_selection", "local_draft", "AwaitingEvidence"),
    ("dependency_check", "local_draft", "AwaitingEvidence"),
    ("local_edit_scope", "local_draft", "AwaitingEvidence"),
    ("verification_plan", "local_draft", "AwaitingEvidence"),
    ("stop_rule", "local_draft", "AwaitingEvidence"),
    ("evidence_receipt_plan", "local_draft", "AwaitingEvidence"),
    ("handoff_summary", "local_draft", "AwaitingEvidence"),
)
EXPECTED_ROOT_KEYS = {
    "blocked_claims",
    "broad_continuation_execution_allowed",
    "claim_promotion_allowed",
    "credential_use_allowed",
    "customer_action_allowed",
    "deadline_promise_claimed",
    "deployment_allowed",
    "external_action_allowed",
    "external_publication_allowed",
    "legal_business_action_allowed",
    "next_action",
    "next_action_surfaces",
    "roadmap_commitment_claimed",
    "schema_version",
    "secret_use_allowed",
    "service_activation_allowed",
    "solver_outcome",
    "source_control_publication_allowed",
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
    "Foundation Next Action Boundary",
    "Witness packet: [`../examples/foundation_next_action_witness.awaiting_evidence.json`]",
    "Rule: Next-action preparation is a local continuation boundary, not permission",
    "No broad continuation execution, external action, deployment, external",
    "next_action_boundary_state=AwaitingEvidence",
    "broad_continuation_execution_allowed=false",
    "external_action_allowed=false",
    "deployment_allowed=false",
    "spending_allowed=false",
    "source_control_publication_allowed=false",
    "deadline_promise_claimed=false",
    "python scripts/validate_foundation_next_action_boundary.py",
)
FORBIDDEN_VALUE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("url_value", re.compile(r"https?://", re.IGNORECASE)),
    ("email_value", re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)),
    ("private_path", re.compile(r"\b[A-Za-z]:[\\/]|\\\\", re.IGNORECASE)),
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
        "service_assignment",
        re.compile(r"\b(?:service|server|endpoint|runtime|database|container)[_ -]?(?:id|url|ref|target|value|status)?\s*=", re.IGNORECASE),
    ),
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
        "git_publication_assignment",
        re.compile(r"\b(?:commit|push|pull[_ -]?request|release)[_ -]?(?:id|ref|target|value|status)?\s*=", re.IGNORECASE),
    ),
    (
        "roadmap_or_deadline_assignment",
        re.compile(r"\b(?:roadmap|deadline|delivery[_ -]?date|launch[_ -]?date)[_ -]?(?:id|ref|target|value|status)?\s*=", re.IGNORECASE),
    ),
)
FORBIDDEN_PROMOTION_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("continue_authorized", re.compile(r"\bcontinue\s+(?:is\s+)?authorized\b", re.IGNORECASE)),
    ("broad_execution_allowed", re.compile(r"\bbroad\s+execution\s+(?:is\s+)?allowed\b", re.IGNORECASE)),
    ("external_action_approved", re.compile(r"\bexternal\s+action\s+(?:is\s+)?approved\b", re.IGNORECASE)),
    ("deployment_ready", re.compile(r"\bdeployment\s+(?:is\s+)?ready\b", re.IGNORECASE)),
    ("published_externally", re.compile(r"\bpublished\s+externally\b", re.IGNORECASE)),
    ("spending_approved", re.compile(r"\bspending\s+(?:is\s+)?approved\b", re.IGNORECASE)),
    ("customer_action_open", re.compile(r"\bcustomer\s+action\s+(?:is\s+)?open\b", re.IGNORECASE)),
    ("legal_business_ready", re.compile(r"\blegal\s+business\s+(?:is\s+)?ready\b", re.IGNORECASE)),
    ("claim_promoted", re.compile(r"\bclaim\s+(?:is\s+)?promoted\b", re.IGNORECASE)),
    ("credential_use_ready", re.compile(r"\bcredential\s+use\s+(?:is\s+)?ready\b", re.IGNORECASE)),
    ("service_active", re.compile(r"\bservice\s+(?:is\s+)?active\b", re.IGNORECASE)),
    ("source_control_published", re.compile(r"\bsource\s+control\s+(?:is\s+)?published\b", re.IGNORECASE)),
    ("roadmap_committed", re.compile(r"\broadmap\s+(?:is\s+)?committed\b", re.IGNORECASE)),
    ("deadline_promised", re.compile(r"\bdeadline\s+(?:is\s+)?promised\b", re.IGNORECASE)),
)


@dataclass(frozen=True, slots=True)
class NextActionFinding:
    """One deterministic next-action boundary validation finding."""

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
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{label} must be a JSON object")
    return payload


def validate_doc_text(text: str) -> list[NextActionFinding]:
    """Return findings for missing next-action documentation anchors."""

    findings: list[NextActionFinding] = []
    for phrase in REQUIRED_DOC_PHRASES:
        if phrase not in text:
            findings.append(
                NextActionFinding(
                    "foundation_next_action_doc_phrase_missing",
                    f"next-action boundary doc missing required phrase: {phrase}",
                )
            )
    return findings


def validate_packet(payload: dict[str, Any]) -> list[NextActionFinding]:
    """Return findings for next-action witness drift."""

    findings: list[NextActionFinding] = []
    findings.extend(validate_root_contract(payload))
    findings.extend(validate_next_action_surfaces(payload.get("next_action_surfaces")))
    findings.extend(validate_forbidden_value_patterns(payload))
    findings.extend(validate_forbidden_promotion_patterns(payload))
    return findings


def validate_root_contract(payload: dict[str, Any]) -> list[NextActionFinding]:
    """Return findings for root-level next-action witness drift."""

    findings: list[NextActionFinding] = []
    if set(payload) != EXPECTED_ROOT_KEYS:
        findings.append(
            NextActionFinding(
                "next_action_root_keys_invalid",
                f"root keys must be: {', '.join(sorted(EXPECTED_ROOT_KEYS))}",
            )
        )
    expected_values = {
        "witness_id": EXPECTED_WITNESS_ID,
        "schema_version": 1,
        "status": "AwaitingEvidence",
        "solver_outcome": "AwaitingEvidence",
        "broad_continuation_execution_allowed": False,
        "external_action_allowed": False,
        "deployment_allowed": False,
        "external_publication_allowed": False,
        "spending_allowed": False,
        "customer_action_allowed": False,
        "legal_business_action_allowed": False,
        "claim_promotion_allowed": False,
        "secret_use_allowed": False,
        "credential_use_allowed": False,
        "service_activation_allowed": False,
        "source_control_publication_allowed": False,
        "roadmap_commitment_claimed": False,
        "deadline_promise_claimed": False,
    }
    for key, expected_value in expected_values.items():
        if payload.get(key) != expected_value:
            findings.append(
                NextActionFinding(
                    "next_action_root_value_invalid",
                    f"{key} must be {expected_value!r}",
                )
            )
    if tuple(payload.get("blocked_claims") or ()) != EXPECTED_BLOCKED_CLAIMS:
        findings.append(
            NextActionFinding(
                "next_action_blocked_claims_invalid",
                f"blocked_claims must be: {', '.join(EXPECTED_BLOCKED_CLAIMS)}",
            )
        )
    next_action = payload.get("next_action")
    if not isinstance(next_action, str) or "choosing one local-safe prerequisite" not in next_action:
        findings.append(
            NextActionFinding(
                "next_action_next_action_invalid",
                "next_action must preserve one local-safe prerequisite selection",
            )
        )
    return findings


def validate_next_action_surfaces(next_action_surfaces: object) -> list[NextActionFinding]:
    """Return findings for next-action surface drift."""

    findings: list[NextActionFinding] = []
    if not isinstance(next_action_surfaces, list) or not all(isinstance(surface, dict) for surface in next_action_surfaces):
        return [NextActionFinding("next_action_surfaces_invalid", "next_action_surfaces must be a list of objects")]
    observed_surfaces = tuple(
        (surface.get("surface_id"), surface.get("surface_type"), surface.get("state"))
        for surface in next_action_surfaces
    )
    if observed_surfaces != EXPECTED_SURFACES:
        findings.append(
            NextActionFinding(
                "next_action_surface_inventory_invalid",
                "next-action surface inventory does not match the Foundation Mode continuation set",
            )
        )
    surface_ids = [surface.get("surface_id") for surface in next_action_surfaces]
    if len(set(surface_ids)) != len(surface_ids):
        findings.append(NextActionFinding("next_action_surface_duplicate", "surface ids must be unique"))
    for surface in next_action_surfaces:
        surface_id = str(surface.get("surface_id", "<missing>"))
        if set(surface) != EXPECTED_SURFACE_KEYS:
            findings.append(
                NextActionFinding(
                    "next_action_surface_keys_invalid",
                    f"{surface_id} surface keys must be: {', '.join(sorted(EXPECTED_SURFACE_KEYS))}",
                )
            )
        if surface.get("state") != "AwaitingEvidence":
            findings.append(
                NextActionFinding(
                    "next_action_surface_state_invalid",
                    f"{surface_id} state must be AwaitingEvidence",
                )
            )
        if surface.get("evidence_ref") != "manual_preparation_pending":
            findings.append(
                NextActionFinding(
                    "next_action_surface_evidence_invalid",
                    f"{surface_id} evidence_ref must stay manual_preparation_pending in the committed packet",
                )
            )
        if not isinstance(surface.get("public_safe_note"), str) or not surface["public_safe_note"].strip():
            findings.append(
                NextActionFinding(
                    "next_action_surface_note_invalid",
                    f"{surface_id} public_safe_note must be a non-empty string",
                )
            )
    return findings


def validate_forbidden_value_patterns(payload: dict[str, Any]) -> list[NextActionFinding]:
    """Return findings for external, private, customer, provider, account, secret, or commitment-shaped values."""

    serialized_payload = json.dumps(payload, sort_keys=True)
    findings: list[NextActionFinding] = []
    for rule_id, pattern in FORBIDDEN_VALUE_PATTERNS:
        if pattern.search(serialized_payload):
            findings.append(
                NextActionFinding(
                    "next_action_forbidden_private_value_pattern",
                    f"next-action witness contains forbidden value pattern: {rule_id}",
                )
            )
    return findings


def validate_forbidden_promotion_patterns(payload: dict[str, Any]) -> list[NextActionFinding]:
    """Return findings if the witness drifts into continuation-promotion phrases."""

    serialized_payload = json.dumps(payload, sort_keys=True)
    findings: list[NextActionFinding] = []
    for rule_id, pattern in FORBIDDEN_PROMOTION_PATTERNS:
        if pattern.search(serialized_payload):
            findings.append(
                NextActionFinding(
                    "next_action_forbidden_promotion_phrase",
                    f"next-action witness contains forbidden promotion pattern: {rule_id}",
                )
            )
    return findings


def validate_foundation_next_action_boundary(
    doc_path: Path = DEFAULT_DOC_PATH,
    packet_path: Path = DEFAULT_PACKET_PATH,
) -> list[NextActionFinding]:
    """Validate the Foundation Mode next-action boundary artifacts."""

    doc_text = load_text(doc_path, "next-action boundary doc")
    packet_payload = load_json_object(packet_path, "next-action witness packet")
    return [
        *validate_doc_text(doc_text),
        *validate_packet(packet_payload),
    ]


def main(argv: list[str] | None = None) -> int:
    """Validate next-action boundary artifacts and print deterministic status."""

    parser = argparse.ArgumentParser(description="Validate Foundation Mode next-action boundary artifacts.")
    parser.add_argument("--doc", type=Path, default=DEFAULT_DOC_PATH)
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET_PATH)
    args = parser.parse_args(argv)

    try:
        findings = validate_foundation_next_action_boundary(args.doc, args.packet)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"[FAIL] foundation_next_action_load: {exc}", file=sys.stderr)
        print("STATUS: failed", file=sys.stderr)
        return 1

    if findings:
        for finding in findings:
            print(f"[FAIL] {finding.rule_id}: {finding.message}", file=sys.stderr)
        print("STATUS: failed", file=sys.stderr)
        return 1
    print("[PASS] foundation_next_action_doc")
    print("[PASS] foundation_next_action_witness")
    print("STATUS: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
