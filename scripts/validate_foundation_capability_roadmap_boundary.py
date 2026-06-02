#!/usr/bin/env python3
"""Validate the Foundation Mode capability-roadmap boundary.

Purpose: keep capability-roadmap preparation local while capability inventory,
capability availability, roadmap commitment, delivery-date, dependency
activation, customer, pilot, support, pricing, money-movement, publication,
and deployment claims remain blocked.
Governance scope: Foundation Mode, public-safe capability-roadmap questions,
private-value exclusion, roadmap-commitment blocking, publication blocking,
money-movement blocking, and deployment blocking.
Dependencies: docs/FOUNDATION_CAPABILITY_ROADMAP_BOUNDARY.md and
examples/foundation_capability_roadmap_witness.awaiting_evidence.json.
Invariants:
  - Validation is read-only.
  - The witness records local capability-roadmap planning only.
  - No capability availability, roadmap, delivery, customer, pilot, support,
    pricing, money-movement, publication, or deployment claim is allowed.
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
DEFAULT_DOC_PATH = REPO_ROOT / "docs" / "FOUNDATION_CAPABILITY_ROADMAP_BOUNDARY.md"
DEFAULT_PACKET_PATH = REPO_ROOT / "examples" / "foundation_capability_roadmap_witness.awaiting_evidence.json"

EXPECTED_WITNESS_ID = "foundation_capability_roadmap_witness.awaiting_evidence.v1"
EXPECTED_BLOCKED_CLAIMS = (
    "capability inventory completeness",
    "capability availability",
    "roadmap commitment",
    "delivery-date promise",
    "final sequencing",
    "dependency activation",
    "public roadmap",
    "customer commitment",
    "pilot commitment",
    "support commitment",
    "pricing commitment",
    "money movement",
    "external publication",
    "deployment readiness",
)
EXPECTED_SURFACES = (
    ("capability_family_questions", "local_draft", "AwaitingEvidence"),
    ("capability_readiness_questions", "local_draft", "AwaitingEvidence"),
    ("sequencing_questions", "local_draft", "AwaitingEvidence"),
    ("dependency_questions", "local_draft", "AwaitingEvidence"),
    ("evidence_gate_questions", "local_draft", "AwaitingEvidence"),
    ("user_value_questions", "local_draft", "AwaitingEvidence"),
    ("support_load_questions", "local_draft", "AwaitingEvidence"),
    ("pricing_exposure_questions", "local_draft", "AwaitingEvidence"),
    ("public_claim_questions", "local_draft", "AwaitingEvidence"),
    ("evolution_review_questions", "local_draft", "AwaitingEvidence"),
)
EXPECTED_ROOT_VALUES = {
    "witness_id": EXPECTED_WITNESS_ID,
    "schema_version": 1,
    "status": "AwaitingEvidence",
    "solver_outcome": "AwaitingEvidence",
    "capability_inventory_complete_claimed": False,
    "capability_availability_claimed": False,
    "roadmap_commitment_claimed": False,
    "delivery_date_promised": False,
    "sequencing_final_claimed": False,
    "dependency_activation_allowed": False,
    "public_roadmap_allowed": False,
    "customer_commitment_allowed": False,
    "pilot_commitment_allowed": False,
    "support_commitment_allowed": False,
    "pricing_commitment_allowed": False,
    "money_movement_allowed": False,
    "external_publication_allowed": False,
    "deployment_allowed": False,
}
EXPECTED_ROOT_KEYS = set(EXPECTED_ROOT_VALUES) | {
    "blocked_claims",
    "capability_roadmap_surfaces",
    "next_action",
}
EXPECTED_SURFACE_KEYS = {
    "evidence_ref",
    "public_safe_note",
    "state",
    "surface_id",
    "surface_type",
}
REQUIRED_DOC_PHRASES = (
    "Foundation Capability Roadmap Boundary",
    "Witness packet: [`../examples/foundation_capability_roadmap_witness.awaiting_evidence.json`]",
    "Rule: Capability-roadmap preparation is a local planning boundary, not a capability-availability, roadmap-commitment, delivery-date, customer, pilot, support, pricing, publication, money-movement, or deployment certificate.",
    "No capability inventory completeness, capability availability, roadmap",
    "capability_roadmap_boundary_state=AwaitingEvidence",
    "capability_inventory_complete_claimed=false",
    "capability_availability_claimed=false",
    "roadmap_commitment_claimed=false",
    "delivery_date_promised=false",
    "sequencing_final_claimed=false",
    "dependency_activation_allowed=false",
    "public_roadmap_allowed=false",
    "customer_commitment_allowed=false",
    "pilot_commitment_allowed=false",
    "support_commitment_allowed=false",
    "pricing_commitment_allowed=false",
    "money_movement_allowed=false",
    "external_publication_allowed=false",
    "deployment_allowed=false",
    "python scripts/validate_foundation_capability_roadmap_boundary.py",
)
FORBIDDEN_VALUE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("url_value", re.compile(r"https?://", re.IGNORECASE)),
    ("email_value", re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)),
    ("private_path", re.compile(r"\b[A-Za-z]:[\\/]|\\\\", re.IGNORECASE)),
    (
        "customer_assignment",
        re.compile(r"\b(?:customer|pilot|tenant|user|account|provider)[_ -]?(?:id|name|email|url|ref|target|value|status)?\s*=", re.IGNORECASE),
    ),
    (
        "roadmap_assignment",
        re.compile(r"\b(?:roadmap|deadline|sequence|dependency|capability|feature)[_ -]?(?:id|url|date|target|value|status|owner)?\s*=", re.IGNORECASE),
    ),
    (
        "pricing_assignment",
        re.compile(r"\b(?:price|pricing|payment|invoice|offer)[_ -]?(?:id|url|amount|value|status)?\s*=", re.IGNORECASE),
    ),
    (
        "secret_assignment",
        re.compile(r"\b(?:password|secret|token|api[_ -]?key|client[_ -]?secret)\s*=", re.IGNORECASE),
    ),
    ("private_key_material", re.compile(r"BEGIN [A-Z ]*PRIVATE KEY")),
)
FORBIDDEN_PROMOTION_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("capability_available", re.compile(r"\bcapabilit(?:y|ies)\s+(?:is|are)\s+(?:available|ready|complete)\b", re.IGNORECASE)),
    ("roadmap_committed", re.compile(r"\broadmap\s+(?:is\s+)?(?:committed|final|published|ready)\b", re.IGNORECASE)),
    ("delivery_promised", re.compile(r"\bdelivery\s+(?:date\s+)?(?:is\s+)?(?:promised|scheduled|guaranteed)\b", re.IGNORECASE)),
    ("dependency_active", re.compile(r"\bdependency\s+(?:is\s+)?(?:active|activated|ready)\b", re.IGNORECASE)),
    ("customer_commitment_ready", re.compile(r"\bcustomer\s+commitment\s+(?:is\s+)?(?:ready|approved)\b", re.IGNORECASE)),
    ("pilot_commitment_ready", re.compile(r"\bpilot\s+commitment\s+(?:is\s+)?(?:ready|approved)\b", re.IGNORECASE)),
    ("pricing_ready", re.compile(r"\bpricing\s+(?:is\s+)?ready\b", re.IGNORECASE)),
    ("deployment_ready", re.compile(r"\bdeployment\s+(?:is\s+)?ready\b", re.IGNORECASE)),
)


@dataclass(frozen=True, slots=True)
class CapabilityRoadmapFinding:
    """One deterministic capability-roadmap boundary validation finding."""

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


def validate_doc_text(text: str) -> list[CapabilityRoadmapFinding]:
    """Return findings for missing capability-roadmap documentation anchors."""

    return [
        CapabilityRoadmapFinding(
            "foundation_capability_roadmap_doc_phrase_missing",
            f"capability-roadmap boundary doc missing required phrase: {phrase}",
        )
        for phrase in REQUIRED_DOC_PHRASES
        if phrase not in text
    ]


def validate_packet(payload: dict[str, Any]) -> list[CapabilityRoadmapFinding]:
    """Return findings for capability-roadmap witness drift."""

    findings: list[CapabilityRoadmapFinding] = []
    findings.extend(validate_root_contract(payload))
    findings.extend(validate_capability_roadmap_surfaces(payload.get("capability_roadmap_surfaces")))
    findings.extend(validate_forbidden_value_patterns(payload))
    findings.extend(validate_forbidden_promotion_patterns(payload))
    return findings


def validate_root_contract(payload: dict[str, Any]) -> list[CapabilityRoadmapFinding]:
    """Return findings for root-level capability-roadmap witness drift."""

    findings: list[CapabilityRoadmapFinding] = []
    if set(payload) != EXPECTED_ROOT_KEYS:
        findings.append(
            CapabilityRoadmapFinding(
                "capability_roadmap_root_keys_invalid",
                f"root keys must be: {', '.join(sorted(EXPECTED_ROOT_KEYS))}",
            )
        )
    for key, expected_value in EXPECTED_ROOT_VALUES.items():
        if payload.get(key) != expected_value:
            findings.append(
                CapabilityRoadmapFinding(
                    "capability_roadmap_root_value_invalid",
                    f"{key} must be {expected_value!r}",
                )
            )
    if tuple(payload.get("blocked_claims") or ()) != EXPECTED_BLOCKED_CLAIMS:
        findings.append(
            CapabilityRoadmapFinding(
                "capability_roadmap_blocked_claims_invalid",
                f"blocked_claims must be: {', '.join(EXPECTED_BLOCKED_CLAIMS)}",
            )
        )
    next_action = payload.get("next_action")
    if not isinstance(next_action, str) or "keep capability-roadmap work local" not in next_action:
        findings.append(
            CapabilityRoadmapFinding(
                "capability_roadmap_next_action_invalid",
                "next_action must preserve the local capability-roadmap boundary",
            )
        )
    return findings


def validate_capability_roadmap_surfaces(surfaces: object) -> list[CapabilityRoadmapFinding]:
    """Return findings for capability-roadmap surface witness drift."""

    if not isinstance(surfaces, list) or not all(isinstance(surface, dict) for surface in surfaces):
        return [
            CapabilityRoadmapFinding(
                "capability_roadmap_surfaces_invalid",
                "capability_roadmap_surfaces must be a list of objects",
            )
        ]
    findings: list[CapabilityRoadmapFinding] = []
    observed_surfaces = tuple(
        (surface.get("surface_id"), surface.get("surface_type"), surface.get("state")) for surface in surfaces
    )
    if observed_surfaces != EXPECTED_SURFACES:
        findings.append(
            CapabilityRoadmapFinding(
                "capability_roadmap_surface_inventory_invalid",
                "capability-roadmap surface inventory does not match the Foundation Mode capability-roadmap set",
            )
        )
    surface_ids = [surface.get("surface_id") for surface in surfaces]
    if len(set(surface_ids)) != len(surface_ids):
        findings.append(CapabilityRoadmapFinding("capability_roadmap_surface_duplicate", "surface ids must be unique"))
    for surface in surfaces:
        surface_id = str(surface.get("surface_id", "<missing>"))
        if set(surface) != EXPECTED_SURFACE_KEYS:
            findings.append(
                CapabilityRoadmapFinding(
                    "capability_roadmap_surface_keys_invalid",
                    f"{surface_id} surface keys must be: {', '.join(sorted(EXPECTED_SURFACE_KEYS))}",
                )
            )
        if surface.get("state") != "AwaitingEvidence":
            findings.append(
                CapabilityRoadmapFinding(
                    "capability_roadmap_surface_state_invalid",
                    f"{surface_id} state must be AwaitingEvidence",
                )
            )
        if surface.get("evidence_ref") != "manual_preparation_pending":
            findings.append(
                CapabilityRoadmapFinding(
                    "capability_roadmap_surface_evidence_invalid",
                    f"{surface_id} evidence_ref must stay manual_preparation_pending in the committed packet",
                )
            )
        if not isinstance(surface.get("public_safe_note"), str) or not surface["public_safe_note"].strip():
            findings.append(
                CapabilityRoadmapFinding(
                    "capability_roadmap_surface_note_invalid",
                    f"{surface_id} public_safe_note must be a non-empty string",
                )
            )
    return findings


def validate_forbidden_value_patterns(payload: dict[str, Any]) -> list[CapabilityRoadmapFinding]:
    """Return findings for private, roadmap, customer, pricing, or secret-shaped values."""

    serialized_payload = json.dumps(payload, sort_keys=True)
    return [
        CapabilityRoadmapFinding(
            "capability_roadmap_forbidden_private_value_pattern",
            f"capability-roadmap witness contains forbidden private value pattern: {rule_id}",
        )
        for rule_id, pattern in FORBIDDEN_VALUE_PATTERNS
        if pattern.search(serialized_payload)
    ]


def validate_forbidden_promotion_patterns(payload: dict[str, Any]) -> list[CapabilityRoadmapFinding]:
    """Return findings for capability-roadmap activation or readiness claims."""

    serialized_payload = json.dumps(payload, sort_keys=True)
    return [
        CapabilityRoadmapFinding(
            "capability_roadmap_forbidden_promotion_phrase",
            f"capability-roadmap witness contains forbidden promotion phrase: {rule_id}",
        )
        for rule_id, pattern in FORBIDDEN_PROMOTION_PATTERNS
        if pattern.search(serialized_payload)
    ]


def validate_foundation_capability_roadmap_boundary(
    doc_path: Path = DEFAULT_DOC_PATH,
    packet_path: Path = DEFAULT_PACKET_PATH,
) -> list[CapabilityRoadmapFinding]:
    """Return all capability-roadmap boundary validation findings."""

    doc_text = load_text(doc_path, "capability-roadmap boundary doc")
    payload = load_json_object(packet_path, "capability-roadmap witness")
    findings: list[CapabilityRoadmapFinding] = []
    findings.extend(validate_doc_text(doc_text))
    findings.extend(validate_packet(payload))
    return findings


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--doc", type=Path, default=DEFAULT_DOC_PATH)
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET_PATH)
    return parser.parse_args()


def main() -> int:
    """Run the capability-roadmap boundary validator."""

    args = parse_args()
    findings = validate_foundation_capability_roadmap_boundary(args.doc, args.packet)
    if findings:
        for finding in findings:
            print(f"[FAIL] {finding.rule_id}: {finding.message}", file=sys.stderr)
        print("STATUS: failed", file=sys.stderr)
        return 1
    print("[PASS] foundation_capability_roadmap_doc")
    print("[PASS] foundation_capability_roadmap_witness")
    print("STATUS: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
