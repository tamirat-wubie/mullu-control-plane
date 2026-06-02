#!/usr/bin/env python3
"""Validate the Foundation Mode hazard-map boundary.

Purpose: keep hazard map drafting local and public-safe while map completeness,
classification readiness, severity closure, mitigation readiness, safety review
readiness, runtime readiness, owner approval, test, refactor, implementation,
publication, and deployment claims remain blocked.
Governance scope: Foundation Mode, hazard-map surfaces, private-value
exclusion, and readiness blocking.
Dependencies: docs/FOUNDATION_HAZARD_MAP_BOUNDARY.md and
examples/foundation_hazard_map_witness.awaiting_evidence.json.
Invariants:
  - Validation is read-only.
  - The witness records hazard-map preparation only.
  - No classification, mitigation, review, owner, test, approval, publication,
    or deployment claim is allowed.
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
DEFAULT_DOC_PATH = REPO_ROOT / "docs" / "FOUNDATION_HAZARD_MAP_BOUNDARY.md"
DEFAULT_PACKET_PATH = REPO_ROOT / "examples" / "foundation_hazard_map_witness.awaiting_evidence.json"

EXPECTED_WITNESS_ID = "foundation_hazard_map_witness.awaiting_evidence.v1"
EXPECTED_BLOCKED_CLAIMS = (
    "hazard-map completeness",
    "hazard classification readiness",
    "hazard severity closure",
    "mitigation readiness",
    "safety review readiness",
    "runtime hazard readiness",
    "owner approval assignment",
    "test pass",
    "refactor approval",
    "implementation approval",
    "external publication",
    "deployment readiness",
)
EXPECTED_SURFACES = (
    ("safety_hazards", "local_draft", "AwaitingEvidence"),
    ("runtime_hazards", "local_draft", "AwaitingEvidence"),
    ("data_hazards", "local_draft", "AwaitingEvidence"),
    ("dependency_hazards", "local_draft", "AwaitingEvidence"),
    ("interface_hazards", "local_draft", "AwaitingEvidence"),
    ("governance_hazards", "local_draft", "AwaitingEvidence"),
    ("evidence_hazards", "local_draft", "AwaitingEvidence"),
    ("rollback_hazards", "local_draft", "AwaitingEvidence"),
    ("operator_hazards", "local_draft", "AwaitingEvidence"),
)
EXPECTED_ROOT_KEYS = {
    "blocked_claims",
    "deployment_allowed",
    "external_publication_allowed",
    "hazard_classification_ready_claimed",
    "hazard_map_complete_claimed",
    "hazard_map_surfaces",
    "hazard_mitigation_ready_claimed",
    "hazard_severity_closed_claimed",
    "implementation_approval_allowed",
    "next_action",
    "owner_approval_assigned",
    "refactor_approval_allowed",
    "runtime_hazard_ready_claimed",
    "safety_review_ready_claimed",
    "schema_version",
    "solver_outcome",
    "status",
    "test_pass_claimed",
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
    "Foundation Hazard Map Boundary",
    "Witness packet: [`../examples/foundation_hazard_map_witness.awaiting_evidence.json`]",
    "Rule: Hazard-map preparation is a local planning boundary, not a",
    "No hazard-map completeness, hazard classification readiness, hazard severity",
    "hazard_map_boundary_state=AwaitingEvidence",
    "hazard_map_complete_claimed=false",
    "hazard_classification_ready_claimed=false",
    "hazard_severity_closed_claimed=false",
    "hazard_mitigation_ready_claimed=false",
    "safety_review_ready_claimed=false",
    "runtime_hazard_ready_claimed=false",
    "implementation_approval_allowed=false",
    "deployment_allowed=false",
    "python scripts/validate_foundation_hazard_map_boundary.py",
)
FORBIDDEN_VALUE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("url_value", re.compile(r"https?://", re.IGNORECASE)),
    ("email_value", re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)),
    ("private_path", re.compile(r"\b[A-Za-z]:[\\/]|\\\\", re.IGNORECASE)),
    (
        "endpoint_or_runtime_assignment",
        re.compile(
            r"\b(?:endpoint|service|server|runtime|database|container)[_ -]?"
            r"(?:id|url|ref|target|value|status)?\s*=",
            re.IGNORECASE,
        ),
    ),
    (
        "account_or_provider_assignment",
        re.compile(
            r"\b(?:account|provider|tenant|project|cloud)[_ -]?"
            r"(?:id|ref|target|value|status)?\s*=",
            re.IGNORECASE,
        ),
    ),
    (
        "hazard_or_mitigation_assignment",
        re.compile(
            r"\b(?:hazard|classification|severity|mitigation|safety[_ -]?review|incident)[_ -]?"
            r"(?:id|ref|target|value|status|result|state)?\s*=",
            re.IGNORECASE,
        ),
    ),
    (
        "test_pass_assignment",
        re.compile(r"\b(?:test|suite|assertion)[_ -]?(?:pass|status|result|value)?\s*=", re.IGNORECASE),
    ),
    (
        "customer_assignment",
        re.compile(
            r"\b(?:customer|pilot|participant|user)[_ -]?"
            r"(?:id|name|email|ref|target|value)?\s*=",
            re.IGNORECASE,
        ),
    ),
    (
        "secret_assignment",
        re.compile(r"\b(?:password|secret|token|api[_ -]?key|credential|client[_ -]?secret)\s*=", re.IGNORECASE),
    ),
    ("private_key_material", re.compile(r"BEGIN [A-Z ]*PRIVATE KEY")),
    (
        "implementation_assignment",
        re.compile(
            r"\b(?:implementation|refactor|migration|release)[_ -]?"
            r"(?:id|ref|target|value|status|approval)?\s*=",
            re.IGNORECASE,
        ),
    ),
    (
        "publication_or_deployment_assignment",
        re.compile(
            r"\b(?:publish|publication|deploy|deployment|production)[_ -]?"
            r"(?:id|url|ref|target|value|status)?\s*=",
            re.IGNORECASE,
        ),
    ),
)
FORBIDDEN_PROMOTION_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("hazard_map_complete", re.compile(r"\bhazard\s+map\s+(?:is\s+)?complete\b", re.IGNORECASE)),
    (
        "hazard_classification_ready",
        re.compile(r"\bhazard\s+classification\s+(?:is\s+)?ready\b", re.IGNORECASE),
    ),
    ("hazard_severity_closed", re.compile(r"\bhazard\s+severity\s+(?:is\s+)?closed\b", re.IGNORECASE)),
    ("mitigation_ready", re.compile(r"\bmitigation\s+(?:is\s+)?ready\b", re.IGNORECASE)),
    ("safety_review_ready", re.compile(r"\bsafety\s+review\s+(?:is\s+)?ready\b", re.IGNORECASE)),
    ("runtime_hazard_ready", re.compile(r"\bruntime\s+hazard\s+(?:is\s+)?ready\b", re.IGNORECASE)),
    ("owner_approved", re.compile(r"\bowner\s+(?:is\s+)?approved\b", re.IGNORECASE)),
    ("test_passed", re.compile(r"\btests?\s+(?:have\s+)?passed\b", re.IGNORECASE)),
    ("refactor_approved", re.compile(r"\brefactor\s+(?:is\s+)?approved\b", re.IGNORECASE)),
    ("implementation_approved", re.compile(r"\bimplementation\s+(?:is\s+)?approved\b", re.IGNORECASE)),
    ("published_externally", re.compile(r"\bpublished\s+externally\b", re.IGNORECASE)),
    ("deployment_ready", re.compile(r"\bdeployment\s+(?:is\s+)?ready\b", re.IGNORECASE)),
)


@dataclass(frozen=True, slots=True)
class HazardMapFinding:
    """One deterministic hazard-map validation finding."""

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


def validate_doc_text(text: str) -> list[HazardMapFinding]:
    """Return findings for missing hazard-map documentation anchors."""

    findings: list[HazardMapFinding] = []
    for phrase in REQUIRED_DOC_PHRASES:
        if phrase not in text:
            findings.append(
                HazardMapFinding(
                    "foundation_hazard_map_doc_phrase_missing",
                    f"hazard-map boundary doc missing required phrase: {phrase}",
                )
            )
    return findings


def validate_packet(payload: dict[str, Any]) -> list[HazardMapFinding]:
    """Return findings for hazard-map witness drift."""

    findings: list[HazardMapFinding] = []
    findings.extend(validate_root_contract(payload))
    findings.extend(validate_hazard_map_surfaces(payload.get("hazard_map_surfaces")))
    findings.extend(validate_forbidden_value_patterns(payload))
    findings.extend(validate_forbidden_promotion_patterns(payload))
    return findings


def validate_root_contract(payload: dict[str, Any]) -> list[HazardMapFinding]:
    """Return findings for root-level hazard-map witness drift."""

    findings: list[HazardMapFinding] = []
    if set(payload) != EXPECTED_ROOT_KEYS:
        findings.append(
            HazardMapFinding(
                "hazard_map_root_keys_invalid",
                f"root keys must be: {', '.join(sorted(EXPECTED_ROOT_KEYS))}",
            )
        )
    expected_values = {
        "witness_id": EXPECTED_WITNESS_ID,
        "schema_version": 1,
        "status": "AwaitingEvidence",
        "solver_outcome": "AwaitingEvidence",
        "hazard_map_complete_claimed": False,
        "hazard_classification_ready_claimed": False,
        "hazard_severity_closed_claimed": False,
        "hazard_mitigation_ready_claimed": False,
        "safety_review_ready_claimed": False,
        "runtime_hazard_ready_claimed": False,
        "owner_approval_assigned": False,
        "test_pass_claimed": False,
        "refactor_approval_allowed": False,
        "implementation_approval_allowed": False,
        "external_publication_allowed": False,
        "deployment_allowed": False,
    }
    for key, expected_value in expected_values.items():
        if payload.get(key) != expected_value:
            findings.append(
                HazardMapFinding(
                    "hazard_map_root_value_invalid",
                    f"{key} must be {expected_value!r}",
                )
            )
    if tuple(payload.get("blocked_claims") or ()) != EXPECTED_BLOCKED_CLAIMS:
        findings.append(
            HazardMapFinding(
                "hazard_map_blocked_claims_invalid",
                f"blocked_claims must be: {', '.join(EXPECTED_BLOCKED_CLAIMS)}",
            )
        )
    next_action = payload.get("next_action")
    if not isinstance(next_action, str) or "continue local hazard map question drafting" not in next_action:
        findings.append(
            HazardMapFinding(
                "hazard_map_next_action_invalid",
                "next_action must preserve local hazard map drafting without readiness promotion",
            )
        )
    return findings


def validate_hazard_map_surfaces(hazard_map_surfaces: object) -> list[HazardMapFinding]:
    """Return findings for hazard-map surface drift."""

    findings: list[HazardMapFinding] = []
    if not isinstance(hazard_map_surfaces, list) or not all(isinstance(surface, dict) for surface in hazard_map_surfaces):
        return [
            HazardMapFinding(
                "hazard_map_surfaces_invalid",
                "hazard_map_surfaces must be a list of objects",
            )
        ]
    observed_surfaces = tuple(
        (surface.get("surface_id"), surface.get("surface_type"), surface.get("state"))
        for surface in hazard_map_surfaces
    )
    if observed_surfaces != EXPECTED_SURFACES:
        findings.append(
            HazardMapFinding(
                "hazard_map_surface_inventory_invalid",
                "hazard-map surface inventory does not match the Foundation Mode hazard set",
            )
        )
    surface_ids = [surface.get("surface_id") for surface in hazard_map_surfaces]
    if len(set(surface_ids)) != len(surface_ids):
        findings.append(HazardMapFinding("hazard_map_surface_duplicate", "surface ids must be unique"))
    for surface in hazard_map_surfaces:
        surface_id = str(surface.get("surface_id", "<missing>"))
        if set(surface) != EXPECTED_SURFACE_KEYS:
            findings.append(
                HazardMapFinding(
                    "hazard_map_surface_keys_invalid",
                    f"{surface_id} surface keys must be: {', '.join(sorted(EXPECTED_SURFACE_KEYS))}",
                )
            )
        if surface.get("state") != "AwaitingEvidence":
            findings.append(
                HazardMapFinding(
                    "hazard_map_surface_state_invalid",
                    f"{surface_id} state must be AwaitingEvidence",
                )
            )
        if surface.get("evidence_ref") != "manual_preparation_pending":
            findings.append(
                HazardMapFinding(
                    "hazard_map_surface_evidence_invalid",
                    f"{surface_id} evidence_ref must stay manual_preparation_pending in the committed packet",
                )
            )
        if not isinstance(surface.get("public_safe_note"), str) or not surface["public_safe_note"].strip():
            findings.append(
                HazardMapFinding(
                    "hazard_map_surface_note_invalid",
                    f"{surface_id} public_safe_note must be a non-empty string",
                )
            )
    return findings


def validate_forbidden_value_patterns(payload: dict[str, Any]) -> list[HazardMapFinding]:
    """Return findings for private, hazard, mitigation, test, or deployment values."""

    serialized_payload = json.dumps(payload, sort_keys=True)
    findings: list[HazardMapFinding] = []
    for rule_id, pattern in FORBIDDEN_VALUE_PATTERNS:
        if pattern.search(serialized_payload):
            findings.append(
                HazardMapFinding(
                    "hazard_map_forbidden_private_value_pattern",
                    f"hazard-map witness contains forbidden value pattern: {rule_id}",
                )
            )
    return findings


def validate_forbidden_promotion_patterns(payload: dict[str, Any]) -> list[HazardMapFinding]:
    """Return findings if the witness drifts into hazard-readiness promotion phrases."""

    serialized_payload = json.dumps(payload, sort_keys=True)
    findings: list[HazardMapFinding] = []
    for rule_id, pattern in FORBIDDEN_PROMOTION_PATTERNS:
        if pattern.search(serialized_payload):
            findings.append(
                HazardMapFinding(
                    "hazard_map_forbidden_promotion_phrase",
                    f"hazard-map witness contains forbidden promotion pattern: {rule_id}",
                )
            )
    return findings


def validate_foundation_hazard_map_boundary(
    doc_path: Path = DEFAULT_DOC_PATH,
    packet_path: Path = DEFAULT_PACKET_PATH,
) -> list[HazardMapFinding]:
    """Validate the Foundation Mode hazard-map boundary artifacts."""

    doc_text = load_text(doc_path, "hazard-map boundary doc")
    packet_payload = load_json_object(packet_path, "hazard-map witness packet")
    return [
        *validate_doc_text(doc_text),
        *validate_packet(packet_payload),
    ]


def main(argv: list[str] | None = None) -> int:
    """Validate hazard-map artifacts and print deterministic status."""

    parser = argparse.ArgumentParser(description="Validate Foundation Mode hazard-map artifacts.")
    parser.add_argument("--doc", type=Path, default=DEFAULT_DOC_PATH)
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET_PATH)
    args = parser.parse_args(argv)

    try:
        findings = validate_foundation_hazard_map_boundary(args.doc, args.packet)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"[FAIL] foundation_hazard_map_load: {exc}", file=sys.stderr)
        print("STATUS: failed", file=sys.stderr)
        return 1

    if findings:
        for finding in findings:
            print(f"[FAIL] {finding.rule_id}: {finding.message}", file=sys.stderr)
        print("STATUS: failed", file=sys.stderr)
        return 1
    print("[PASS] foundation_hazard_map_doc")
    print("[PASS] foundation_hazard_map_witness")
    print("STATUS: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
