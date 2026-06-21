#!/usr/bin/env python3
"""Validate the Foundation Mode cognitive SGI readiness boundary.

Purpose: keep cognitive SGI readiness work local, deterministic, and
read/simulation-only while achieved-SGI, consciousness, production, customer,
authority, deployment, and unrestricted self-modification claims remain blocked.
Governance scope: Foundation Mode, cognitive SGI readiness surfaces, explicit
blockers, private-value exclusion, ontology-promotion blocking, external-effect
blocking, and readiness-claim blocking.
Dependencies: docs/FOUNDATION_COGNITIVE_SGI_READINESS_BOUNDARY.md and
examples/foundation_cognitive_sgi_readiness_witness.awaiting_evidence.json.
Invariants:
  - Validation is read-only.
  - The witness records local readiness preparation only.
  - No achieved-SGI, consciousness, production, customer, authority,
    deployment, or unrestricted self-modification claim is allowed.
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
DEFAULT_DOC_PATH = REPO_ROOT / "docs" / "FOUNDATION_COGNITIVE_SGI_READINESS_BOUNDARY.md"
DEFAULT_PACKET_PATH = REPO_ROOT / "examples" / "foundation_cognitive_sgi_readiness_witness.awaiting_evidence.json"

EXPECTED_WITNESS_ID = "foundation_cognitive_sgi_readiness_witness.awaiting_evidence.v1"
EXPECTED_BLOCKED_CLAIMS = (
    "achieved SGI",
    "autonomous consciousness",
    "production readiness",
    "customer readiness",
    "public deployment readiness",
    "safety certification",
    "legal authority",
    "medical authority",
    "financial authority",
    "unrestricted self-modification",
)
EXPECTED_SURFACES = (
    ("cross_domain_transfer", "local_read_simulation", "AwaitingEvidence"),
    ("concept_birth", "local_read_simulation", "AwaitingEvidence"),
    ("self_question_generation", "local_read_simulation", "AwaitingEvidence"),
    ("homeostasis_reward_vectors", "local_read_simulation", "AwaitingEvidence"),
    ("governed_autonomy_classification", "local_read_simulation", "AwaitingEvidence"),
    ("blocked_evidence_lanes", "local_read_simulation", "AwaitingEvidence"),
    ("external_effect_boundary", "local_read_simulation", "AwaitingEvidence"),
    ("ontology_promotion_boundary", "local_read_simulation", "AwaitingEvidence"),
)
EXPECTED_ROOT_VALUES = {
    "witness_id": EXPECTED_WITNESS_ID,
    "schema_version": 1,
    "status": "AwaitingEvidence",
    "solver_outcome": "AwaitingEvidence",
    "max_candidate_level": "Level 4 Candidate",
    "achieved_sgi_claimed": False,
    "autonomous_consciousness_claimed": False,
    "production_readiness_claimed": False,
    "customer_readiness_claimed": False,
    "public_deployment_readiness_claimed": False,
    "safety_certification_claimed": False,
    "legal_authority_claimed": False,
    "medical_authority_claimed": False,
    "financial_authority_claimed": False,
    "unrestricted_self_modification_claimed": False,
    "external_effects_allowed": False,
    "ontology_promotion_allowed": False,
    "production_mutation_allowed": False,
}
EXPECTED_ROOT_KEYS = set(EXPECTED_ROOT_VALUES) | {
    "blocked_claims",
    "cognitive_sgi_readiness_surfaces",
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
    "Foundation Cognitive SGI Readiness Boundary",
    "Witness packet: [`../examples/foundation_cognitive_sgi_readiness_witness.awaiting_evidence.json`]",
    "Rule: Cognitive SGI readiness preparation is a local read/simulation boundary",
    "Mullu can be evaluated as a Proto-SGI cognitive architecture candidate through deterministic evidence checks.",
    "cognitive_sgi_readiness_boundary_state=AwaitingEvidence",
    "achieved_sgi_claimed=false",
    "autonomous_consciousness_claimed=false",
    "production_readiness_claimed=false",
    "customer_readiness_claimed=false",
    "public_deployment_readiness_claimed=false",
    "external_effects_allowed=false",
    "ontology_promotion_allowed=false",
    "unrestricted_self_modification_claimed=false",
    "python scripts/validate_foundation_cognitive_sgi_readiness_boundary.py",
)
FORBIDDEN_VALUE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("url_value", re.compile(r"https?://", re.IGNORECASE)),
    ("email_value", re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)),
    ("private_path", re.compile(r"\b[A-Za-z]:[\\/]|\\\\", re.IGNORECASE)),
    (
        "endpoint_or_runtime_assignment",
        re.compile(
            r"\b(?:endpoint|runtime|gateway|production|deploy|deployment)[_ -]?"
            r"(?:id|url|ref|target|value|status)?\s*=",
            re.IGNORECASE,
        ),
    ),
    (
        "customer_or_account_assignment",
        re.compile(
            r"\b(?:customer|pilot|tenant|account|provider|user)[_ -]?"
            r"(?:id|name|email|ref|target|value|status)?\s*=",
            re.IGNORECASE,
        ),
    ),
    (
        "authority_assignment",
        re.compile(
            r"\b(?:legal|medical|financial|safety|authority|certification)[_ -]?"
            r"(?:id|ref|target|value|status|claim)?\s*=",
            re.IGNORECASE,
        ),
    ),
    (
        "secret_assignment",
        re.compile(r"\b(?:password|secret|token|api[_ -]?key|credential|client[_ -]?secret)\s*=", re.IGNORECASE),
    ),
    ("private_key_material", re.compile(r"BEGIN [A-Z ]*PRIVATE KEY")),
)
FORBIDDEN_PROMOTION_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("achieved_sgi", re.compile(r"\bsgi\s+(?:is\s+)?achieved\b", re.IGNORECASE)),
    (
        "consciousness_proven",
        re.compile(r"\b(?:consciousness|autonomous\s+consciousness)\s+(?:is\s+)?(?:proven|verified)\b", re.IGNORECASE),
    ),
    ("production_ready", re.compile(r"\bproduction\s+(?:is\s+)?ready\b", re.IGNORECASE)),
    ("customer_ready", re.compile(r"\bcustomer\s+(?:is\s+)?ready\b", re.IGNORECASE)),
    ("deployment_ready", re.compile(r"\bdeployment\s+(?:is\s+)?ready\b", re.IGNORECASE)),
    ("safety_certified", re.compile(r"\bsafety\s+(?:is\s+)?certified\b", re.IGNORECASE)),
    ("authority_granted", re.compile(r"\b(?:legal|medical|financial)\s+authority\s+(?:is\s+)?granted\b", re.IGNORECASE)),
    (
        "self_modification_unrestricted",
        re.compile(r"\bunrestricted\s+self-modification\s+(?:is\s+)?(?:allowed|enabled)\b", re.IGNORECASE),
    ),
)


@dataclass(frozen=True, slots=True)
class CognitiveSgiReadinessFinding:
    """One deterministic cognitive SGI readiness boundary validation finding."""

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


def validate_doc_text(text: str) -> list[CognitiveSgiReadinessFinding]:
    """Return findings for missing cognitive SGI readiness documentation anchors."""

    return [
        CognitiveSgiReadinessFinding(
            "cognitive_sgi_readiness_doc_phrase_missing",
            f"cognitive SGI readiness boundary doc missing required phrase: {phrase}",
        )
        for phrase in REQUIRED_DOC_PHRASES
        if phrase not in text
    ]


def validate_packet(payload: dict[str, Any]) -> list[CognitiveSgiReadinessFinding]:
    """Return findings for cognitive SGI readiness witness drift."""

    findings: list[CognitiveSgiReadinessFinding] = []
    findings.extend(validate_root_contract(payload))
    findings.extend(validate_readiness_surfaces(payload.get("cognitive_sgi_readiness_surfaces")))
    findings.extend(validate_forbidden_value_patterns(payload))
    findings.extend(validate_forbidden_promotion_patterns(payload))
    return findings


def validate_root_contract(payload: dict[str, Any]) -> list[CognitiveSgiReadinessFinding]:
    """Return findings for root-level cognitive SGI readiness witness drift."""

    findings: list[CognitiveSgiReadinessFinding] = []
    if set(payload) != EXPECTED_ROOT_KEYS:
        findings.append(
            CognitiveSgiReadinessFinding(
                "cognitive_sgi_readiness_root_keys_invalid",
                f"root keys must be: {', '.join(sorted(EXPECTED_ROOT_KEYS))}",
            )
        )
    for key, expected_value in EXPECTED_ROOT_VALUES.items():
        if payload.get(key) != expected_value:
            findings.append(
                CognitiveSgiReadinessFinding(
                    "cognitive_sgi_readiness_root_value_invalid",
                    f"{key} must be {expected_value!r}",
                )
            )
    if tuple(payload.get("blocked_claims") or ()) != EXPECTED_BLOCKED_CLAIMS:
        findings.append(
            CognitiveSgiReadinessFinding(
                "cognitive_sgi_readiness_blocked_claims_invalid",
                f"blocked_claims must be: {', '.join(EXPECTED_BLOCKED_CLAIMS)}",
            )
        )
    next_action = payload.get("next_action")
    if not isinstance(next_action, str) or "keep cognitive SGI readiness local" not in next_action:
        findings.append(
            CognitiveSgiReadinessFinding(
                "cognitive_sgi_readiness_next_action_invalid",
                "next_action must preserve local read/simulation readiness preparation",
            )
        )
    return findings


def validate_readiness_surfaces(surfaces: object) -> list[CognitiveSgiReadinessFinding]:
    """Return findings for cognitive SGI readiness surface drift."""

    if not isinstance(surfaces, list) or not all(isinstance(surface, dict) for surface in surfaces):
        return [
            CognitiveSgiReadinessFinding(
                "cognitive_sgi_readiness_surfaces_invalid",
                "cognitive_sgi_readiness_surfaces must be a list of objects",
            )
        ]
    findings: list[CognitiveSgiReadinessFinding] = []
    observed_surfaces = tuple(
        (surface.get("surface_id"), surface.get("surface_type"), surface.get("state")) for surface in surfaces
    )
    if observed_surfaces != EXPECTED_SURFACES:
        findings.append(
            CognitiveSgiReadinessFinding(
                "cognitive_sgi_readiness_surface_inventory_invalid",
                "cognitive SGI readiness surface inventory does not match the Foundation Mode readiness set",
            )
        )
    surface_ids = [surface.get("surface_id") for surface in surfaces]
    if len(set(surface_ids)) != len(surface_ids):
        findings.append(
            CognitiveSgiReadinessFinding("cognitive_sgi_readiness_surface_duplicate", "surface ids must be unique")
        )
    for surface in surfaces:
        surface_id = str(surface.get("surface_id", "<missing>"))
        if set(surface) != EXPECTED_SURFACE_KEYS:
            findings.append(
                CognitiveSgiReadinessFinding(
                    "cognitive_sgi_readiness_surface_keys_invalid",
                    f"{surface_id} surface keys must be: {', '.join(sorted(EXPECTED_SURFACE_KEYS))}",
                )
            )
        if surface.get("state") != "AwaitingEvidence":
            findings.append(
                CognitiveSgiReadinessFinding(
                    "cognitive_sgi_readiness_surface_state_invalid",
                    f"{surface_id} state must be AwaitingEvidence",
                )
            )
        if surface.get("evidence_ref") != "manual_preparation_pending":
            findings.append(
                CognitiveSgiReadinessFinding(
                    "cognitive_sgi_readiness_surface_evidence_invalid",
                    f"{surface_id} evidence_ref must stay manual_preparation_pending in the committed packet",
                )
            )
        if not isinstance(surface.get("public_safe_note"), str) or not surface["public_safe_note"].strip():
            findings.append(
                CognitiveSgiReadinessFinding(
                    "cognitive_sgi_readiness_surface_note_invalid",
                    f"{surface_id} public_safe_note must be a non-empty string",
                )
            )
    return findings


def validate_forbidden_value_patterns(payload: dict[str, Any]) -> list[CognitiveSgiReadinessFinding]:
    """Return findings for private, endpoint, customer, authority, secret, or deployment-shaped values."""

    serialized_payload = json.dumps(payload, sort_keys=True)
    return [
        CognitiveSgiReadinessFinding(
            "cognitive_sgi_readiness_forbidden_private_value_pattern",
            f"cognitive SGI readiness witness contains forbidden value pattern: {rule_id}",
        )
        for rule_id, pattern in FORBIDDEN_VALUE_PATTERNS
        if pattern.search(serialized_payload)
    ]


def validate_forbidden_promotion_patterns(payload: dict[str, Any]) -> list[CognitiveSgiReadinessFinding]:
    """Return findings if the witness drifts into readiness or authority promotion phrases."""

    serialized_payload = json.dumps(payload, sort_keys=True)
    return [
        CognitiveSgiReadinessFinding(
            "cognitive_sgi_readiness_forbidden_promotion_phrase",
            f"cognitive SGI readiness witness contains forbidden promotion phrase: {rule_id}",
        )
        for rule_id, pattern in FORBIDDEN_PROMOTION_PATTERNS
        if pattern.search(serialized_payload)
    ]


def validate_foundation_cognitive_sgi_readiness_boundary(
    doc_path: Path = DEFAULT_DOC_PATH,
    packet_path: Path = DEFAULT_PACKET_PATH,
) -> list[CognitiveSgiReadinessFinding]:
    """Return all cognitive SGI readiness boundary validation findings."""

    doc_text = load_text(doc_path, "cognitive SGI readiness boundary doc")
    payload = load_json_object(packet_path, "cognitive SGI readiness witness")
    findings: list[CognitiveSgiReadinessFinding] = []
    findings.extend(validate_doc_text(doc_text))
    findings.extend(validate_packet(payload))
    return findings


def main(argv: list[str] | None = None) -> int:
    """Run the cognitive SGI readiness boundary validator."""

    parser = argparse.ArgumentParser(description="Validate Foundation Mode cognitive SGI readiness boundary artifacts.")
    parser.add_argument("--doc", type=Path, default=DEFAULT_DOC_PATH)
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET_PATH)
    args = parser.parse_args(argv)

    try:
        findings = validate_foundation_cognitive_sgi_readiness_boundary(args.doc, args.packet)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"[FAIL] foundation_cognitive_sgi_readiness_load: {exc}", file=sys.stderr)
        print("STATUS: failed", file=sys.stderr)
        return 1

    if findings:
        for finding in findings:
            print(f"[FAIL] {finding.rule_id}: {finding.message}", file=sys.stderr)
        print("STATUS: failed", file=sys.stderr)
        return 1
    print("[PASS] foundation_cognitive_sgi_readiness_doc")
    print("[PASS] foundation_cognitive_sgi_readiness_witness")
    print("STATUS: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
