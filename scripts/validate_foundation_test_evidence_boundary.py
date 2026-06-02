#!/usr/bin/env python3
"""Validate the Foundation Mode test-evidence boundary.

Purpose: keep validation evidence local and scope-bound while full-test pass,
complete coverage, CI parity, release readiness, deployment readiness, security
clearance, secret clearance, customer readiness, legal clearance, performance
readiness, flake-free, terminal-closure, external-publication, and deployment
claims remain blocked.
Governance scope: Foundation Mode, test-evidence surfaces, private-value
exclusion, validation-scope blocking, and readiness blocking.
Dependencies: docs/FOUNDATION_TEST_EVIDENCE_BOUNDARY.md and
examples/foundation_test_evidence_witness.awaiting_evidence.json.
Invariants:
  - Validation is read-only.
  - The witness records test-evidence preparation only.
  - Passing focused checks cannot become broad readiness, release, customer,
    legal, publication, or deployment claims.
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
DEFAULT_DOC_PATH = REPO_ROOT / "docs" / "FOUNDATION_TEST_EVIDENCE_BOUNDARY.md"
DEFAULT_PACKET_PATH = REPO_ROOT / "examples" / "foundation_test_evidence_witness.awaiting_evidence.json"

EXPECTED_WITNESS_ID = "foundation_test_evidence_witness.awaiting_evidence.v1"
EXPECTED_BLOCKED_CLAIMS = (
    "full-test pass",
    "complete coverage",
    "CI parity",
    "release readiness",
    "deployment readiness",
    "security clearance",
    "secret clearance",
    "customer readiness",
    "legal clearance",
    "performance readiness",
    "flake-free guarantee",
    "terminal closure",
    "external publication",
    "deployment readiness",
)
EXPECTED_SURFACES = (
    ("focused_validator_questions", "local_draft", "AwaitingEvidence"),
    ("targeted_pytest_questions", "local_draft", "AwaitingEvidence"),
    ("full_preflight_questions", "local_draft", "AwaitingEvidence"),
    ("receipt_validation_questions", "local_draft", "AwaitingEvidence"),
    ("diff_hygiene_questions", "local_draft", "AwaitingEvidence"),
    ("failure_case_questions", "local_draft", "AwaitingEvidence"),
    ("warning_triage_questions", "local_draft", "AwaitingEvidence"),
    ("coverage_gap_questions", "local_draft", "AwaitingEvidence"),
    ("reproducibility_questions", "local_draft", "AwaitingEvidence"),
    ("non_terminal_closure_questions", "local_draft", "AwaitingEvidence"),
)
EXPECTED_ROOT_KEYS = {
    "blocked_claims",
    "ci_parity_claimed",
    "complete_coverage_claimed",
    "customer_readiness_claimed",
    "deployment_allowed",
    "deployment_readiness_claimed",
    "external_publication_allowed",
    "flake_free_guarantee_claimed",
    "full_test_pass_claimed",
    "legal_clearance_claimed",
    "next_action",
    "performance_readiness_claimed",
    "release_readiness_claimed",
    "schema_version",
    "secret_clearance_claimed",
    "security_clearance_claimed",
    "solver_outcome",
    "status",
    "terminal_closure_claimed",
    "test_evidence_surfaces",
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
    "Foundation Test Evidence Boundary",
    "Witness packet: [`../examples/foundation_test_evidence_witness.awaiting_evidence.json`]",
    "Rule: Test-evidence preparation is a local planning boundary, not a full-test",
    "No full-test-pass, complete-coverage, CI-parity, release-readiness",
    "test_evidence_boundary_state=AwaitingEvidence",
    "full_test_pass_claimed=false",
    "complete_coverage_claimed=false",
    "ci_parity_claimed=false",
    "release_readiness_claimed=false",
    "deployment_readiness_claimed=false",
    "security_clearance_claimed=false",
    "secret_clearance_claimed=false",
    "customer_readiness_claimed=false",
    "legal_clearance_claimed=false",
    "terminal_closure_claimed=false",
    "external_publication_allowed=false",
    "deployment_allowed=false",
    "python scripts/validate_foundation_test_evidence_boundary.py",
)
FORBIDDEN_VALUE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("url_value", re.compile(r"https?://", re.IGNORECASE)),
    ("email_value", re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)),
    ("private_path", re.compile(r"\b[A-Za-z]:[\\/]|\\\\", re.IGNORECASE)),
    ("source_control_assignment", re.compile(r"\b(?:branch|commit|pull[_ -]?request|release)[_ -]?(?:id|ref|target|value)\s*=", re.IGNORECASE)),
    ("test_result_assignment", re.compile(r"\b(?:test|pytest|coverage|ci|suite)[_ -]?(?:pass|status|result|value)\s*=", re.IGNORECASE)),
    ("secret_assignment", re.compile(r"\b(?:password|secret|token|api[_ -]?key|credential)\s*=", re.IGNORECASE)),
    ("private_key_material", re.compile(r"BEGIN [A-Z ]*PRIVATE KEY")),
    ("customer_assignment", re.compile(r"\b(?:customer|pilot|participant|user)[_ -]?(?:id|email|target|ref|value)\s*=", re.IGNORECASE)),
    ("deployment_assignment", re.compile(r"\b(?:deploy|endpoint|runtime|cluster|production)[_ -]?(?:url|target|id|ref|value)\s*=", re.IGNORECASE)),
)
FORBIDDEN_PROMOTION_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("full_test_passed", re.compile(r"\bfull\s+test(?:s)?\s+(?:suite\s+)?(?:passed|pass)\b", re.IGNORECASE)),
    ("coverage_complete", re.compile(r"\bcoverage\s+is\s+complete\b", re.IGNORECASE)),
    ("ci_parity", re.compile(r"\bCI\s+parity\s+(?:is\s+)?(?:proven|claimed|complete)\b", re.IGNORECASE)),
    ("release_ready", re.compile(r"\brelease\s+(?:is\s+)?ready\b", re.IGNORECASE)),
    ("deployment_ready", re.compile(r"\bdeployment\s+(?:is\s+)?ready\b", re.IGNORECASE)),
    ("security_clear", re.compile(r"\bsecurity\s+(?:is\s+)?clear(?:ed)?\b", re.IGNORECASE)),
    ("secret_clear", re.compile(r"\bsecrets?\s+(?:are\s+)?clear(?:ed)?\b", re.IGNORECASE)),
    ("customer_ready", re.compile(r"\bcustomer\s+(?:is\s+)?ready\b", re.IGNORECASE)),
    ("legal_clear", re.compile(r"\blegal\s+clearance\s+(?:is\s+)?(?:complete|granted)\b", re.IGNORECASE)),
    ("performance_ready", re.compile(r"\bperformance\s+(?:is\s+)?ready\b", re.IGNORECASE)),
    ("flake_free", re.compile(r"\bflake[- ]free\s+(?:is\s+)?guaranteed\b", re.IGNORECASE)),
    ("terminal_closure", re.compile(r"\bterminal\s+closure\s+(?:is\s+)?claimed\b", re.IGNORECASE)),
    ("externally_published", re.compile(r"\bexternally\s+published\b", re.IGNORECASE)),
)


@dataclass(frozen=True, slots=True)
class TestEvidenceFinding:
    """One deterministic test-evidence boundary validation finding."""

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


def validate_doc_text(text: str) -> list[TestEvidenceFinding]:
    """Return findings for missing test-evidence documentation anchors."""

    findings: list[TestEvidenceFinding] = []
    for phrase in REQUIRED_DOC_PHRASES:
        if phrase not in text:
            findings.append(
                TestEvidenceFinding(
                    "foundation_test_evidence_doc_phrase_missing",
                    f"test-evidence boundary doc missing required phrase: {phrase}",
                )
            )
    return findings


def validate_packet(payload: dict[str, Any]) -> list[TestEvidenceFinding]:
    """Return findings for test-evidence witness drift."""

    findings: list[TestEvidenceFinding] = []
    findings.extend(validate_root_contract(payload))
    findings.extend(validate_test_evidence_surfaces(payload.get("test_evidence_surfaces")))
    findings.extend(validate_forbidden_value_patterns(payload))
    findings.extend(validate_forbidden_promotion_patterns(payload))
    return findings


def validate_root_contract(payload: dict[str, Any]) -> list[TestEvidenceFinding]:
    """Return findings for root-level test-evidence witness drift."""

    findings: list[TestEvidenceFinding] = []
    if set(payload) != EXPECTED_ROOT_KEYS:
        findings.append(
            TestEvidenceFinding(
                "test_evidence_root_keys_invalid",
                f"root keys must be: {', '.join(sorted(EXPECTED_ROOT_KEYS))}",
            )
        )
    expected_values = {
        "witness_id": EXPECTED_WITNESS_ID,
        "schema_version": 1,
        "status": "AwaitingEvidence",
        "solver_outcome": "AwaitingEvidence",
        "full_test_pass_claimed": False,
        "complete_coverage_claimed": False,
        "ci_parity_claimed": False,
        "release_readiness_claimed": False,
        "deployment_readiness_claimed": False,
        "security_clearance_claimed": False,
        "secret_clearance_claimed": False,
        "customer_readiness_claimed": False,
        "legal_clearance_claimed": False,
        "performance_readiness_claimed": False,
        "flake_free_guarantee_claimed": False,
        "terminal_closure_claimed": False,
        "external_publication_allowed": False,
        "deployment_allowed": False,
    }
    for key, expected_value in expected_values.items():
        if payload.get(key) != expected_value:
            findings.append(
                TestEvidenceFinding(
                    "test_evidence_root_value_invalid",
                    f"{key} must be {expected_value!r}",
                )
            )
    if tuple(payload.get("blocked_claims") or ()) != EXPECTED_BLOCKED_CLAIMS:
        findings.append(
            TestEvidenceFinding(
                "test_evidence_blocked_claims_invalid",
                f"blocked_claims must be: {', '.join(EXPECTED_BLOCKED_CLAIMS)}",
            )
        )
    next_action = payload.get("next_action")
    if not isinstance(next_action, str) or "continue local test-evidence question drafting" not in next_action:
        findings.append(
            TestEvidenceFinding(
                "test_evidence_next_action_invalid",
                "next_action must preserve local test-evidence drafting without readiness promotion",
            )
        )
    return findings


def validate_test_evidence_surfaces(test_evidence_surfaces: object) -> list[TestEvidenceFinding]:
    """Return findings for test-evidence surface drift."""

    findings: list[TestEvidenceFinding] = []
    if not isinstance(test_evidence_surfaces, list) or not all(isinstance(surface, dict) for surface in test_evidence_surfaces):
        return [TestEvidenceFinding("test_evidence_surfaces_invalid", "test_evidence_surfaces must be a list of objects")]
    observed_surfaces = tuple(
        (surface.get("surface_id"), surface.get("surface_type"), surface.get("state"))
        for surface in test_evidence_surfaces
    )
    if observed_surfaces != EXPECTED_SURFACES:
        findings.append(
            TestEvidenceFinding(
                "test_evidence_surface_inventory_invalid",
                "test-evidence surface inventory does not match the Foundation Mode test-evidence set",
            )
        )
    surface_ids = [surface.get("surface_id") for surface in test_evidence_surfaces]
    if len(set(surface_ids)) != len(surface_ids):
        findings.append(TestEvidenceFinding("test_evidence_surface_duplicate", "surface ids must be unique"))
    for surface in test_evidence_surfaces:
        surface_id = str(surface.get("surface_id", "<missing>"))
        if set(surface) != EXPECTED_SURFACE_KEYS:
            findings.append(
                TestEvidenceFinding(
                    "test_evidence_surface_keys_invalid",
                    f"{surface_id} surface keys must be: {', '.join(sorted(EXPECTED_SURFACE_KEYS))}",
                )
            )
        if surface.get("state") != "AwaitingEvidence":
            findings.append(
                TestEvidenceFinding(
                    "test_evidence_surface_state_invalid",
                    f"{surface_id} state must be AwaitingEvidence",
                )
            )
        if surface.get("evidence_ref") != "manual_preparation_pending":
            findings.append(
                TestEvidenceFinding(
                    "test_evidence_surface_evidence_invalid",
                    f"{surface_id} evidence_ref must stay manual_preparation_pending in the committed packet",
                )
            )
        if not isinstance(surface.get("public_safe_note"), str) or not surface["public_safe_note"].strip():
            findings.append(
                TestEvidenceFinding(
                    "test_evidence_surface_note_invalid",
                    f"{surface_id} public_safe_note must be a non-empty string",
                )
            )
    return findings


def validate_forbidden_value_patterns(payload: dict[str, Any]) -> list[TestEvidenceFinding]:
    """Return findings for private, test-result, source-control, customer, or deployment values."""

    serialized_payload = json.dumps(payload, sort_keys=True)
    findings: list[TestEvidenceFinding] = []
    for rule_id, pattern in FORBIDDEN_VALUE_PATTERNS:
        if pattern.search(serialized_payload):
            findings.append(
                TestEvidenceFinding(
                    "test_evidence_forbidden_private_value_pattern",
                    f"test-evidence witness contains forbidden value pattern: {rule_id}",
                )
            )
    return findings


def validate_forbidden_promotion_patterns(payload: dict[str, Any]) -> list[TestEvidenceFinding]:
    """Return findings if the witness drifts into broad validation promotion."""

    serialized_payload = json.dumps(payload, sort_keys=True)
    findings: list[TestEvidenceFinding] = []
    for rule_id, pattern in FORBIDDEN_PROMOTION_PATTERNS:
        if pattern.search(serialized_payload):
            findings.append(
                TestEvidenceFinding(
                    "test_evidence_forbidden_promotion_phrase",
                    f"test-evidence witness contains forbidden promotion pattern: {rule_id}",
                )
            )
    return findings


def validate_foundation_test_evidence_boundary(
    doc_path: Path = DEFAULT_DOC_PATH,
    packet_path: Path = DEFAULT_PACKET_PATH,
) -> list[TestEvidenceFinding]:
    """Validate the Foundation Mode test-evidence boundary artifacts."""

    doc_text = load_text(doc_path, "test-evidence boundary doc")
    packet_payload = load_json_object(packet_path, "test-evidence witness packet")
    return [
        *validate_doc_text(doc_text),
        *validate_packet(packet_payload),
    ]


def main(argv: list[str] | None = None) -> int:
    """Validate test-evidence artifacts and print deterministic status."""

    parser = argparse.ArgumentParser(description="Validate Foundation Mode test-evidence artifacts.")
    parser.add_argument("--doc", type=Path, default=DEFAULT_DOC_PATH)
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET_PATH)
    args = parser.parse_args(argv)

    try:
        findings = validate_foundation_test_evidence_boundary(args.doc, args.packet)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"[FAIL] foundation_test_evidence_load: {exc}", file=sys.stderr)
        print("STATUS: failed", file=sys.stderr)
        return 1

    if findings:
        for finding in findings:
            print(f"[FAIL] {finding.rule_id}: {finding.message}", file=sys.stderr)
        print("STATUS: failed", file=sys.stderr)
        return 1
    print("[PASS] foundation_test_evidence_doc")
    print("[PASS] foundation_test_evidence_witness")
    print("STATUS: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
