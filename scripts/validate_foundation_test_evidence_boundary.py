#!/usr/bin/env python3
"""Validate the Foundation Mode test-evidence boundary.

Purpose: keep validation evidence local and scope-bound while full-test pass,
complete coverage, CI parity, release readiness, deployment readiness, security
clearance, secret clearance, customer readiness, legal clearance, performance
readiness, flake-free, terminal-closure, external-publication, and deployment
claims remain blocked.
Governance scope: Foundation Mode, test-evidence surfaces, receipt routing,
warning and coverage-gap registration, private-value exclusion,
validation-scope blocking, and readiness blocking.
Dependencies: docs/FOUNDATION_TEST_EVIDENCE_BOUNDARY.md,
examples/foundation_test_evidence_witness.awaiting_evidence.json, and
examples/foundation_test_receipt_routing.awaiting_evidence.json, and
examples/foundation_test_gap_warning_register.awaiting_evidence.json.
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
DEFAULT_ROUTING_PATH = REPO_ROOT / "examples" / "foundation_test_receipt_routing.awaiting_evidence.json"
DEFAULT_GAP_WARNING_PATH = REPO_ROOT / "examples" / "foundation_test_gap_warning_register.awaiting_evidence.json"

EXPECTED_WITNESS_ID = "foundation_test_evidence_witness.awaiting_evidence.v1"
EXPECTED_ROUTING_ID = "foundation_test_receipt_routing.awaiting_evidence.v1"
EXPECTED_GAP_WARNING_ID = "foundation_test_gap_warning_register.awaiting_evidence.v1"
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
EXPECTED_RECEIPT_ROUTES = (
    ("focused_validator_receipt_route", "focused_validator_questions", "local_cli_summary_pending", "scripts/validate_foundation_test_evidence_boundary.py", "full-test pass", "AwaitingEvidence"),
    ("targeted_pytest_receipt_route", "targeted_pytest_questions", "local_cli_summary_pending", "tests/test_validate_foundation_test_evidence_boundary.py", "complete coverage", "AwaitingEvidence"),
    ("full_preflight_receipt_route", "full_preflight_questions", ".tmp/workspace-governance-preflight-receipt.json", "scripts/run_workspace_governance_checks.py", "release readiness", "AwaitingEvidence"),
    ("receipt_validation_receipt_route", "receipt_validation_questions", ".tmp/workspace-governance-preflight-receipt.json", "scripts/validate_workspace_governance_preflight_receipt.py", "terminal closure", "AwaitingEvidence"),
    ("diff_hygiene_receipt_route", "diff_hygiene_questions", "local_cli_summary_pending", "git diff --check", "secret clearance", "AwaitingEvidence"),
    ("failure_case_receipt_route", "failure_case_questions", "local_cli_summary_pending", "tests/test_validate_foundation_test_evidence_boundary.py", "flake-free guarantee", "AwaitingEvidence"),
    ("warning_triage_receipt_route", "warning_triage_questions", "local_cli_summary_pending", "local_operator_review_pending", "warning-free claim", "AwaitingEvidence"),
    ("coverage_gap_receipt_route", "coverage_gap_questions", "local_gap_summary_pending", "local_operator_review_pending", "complete coverage", "AwaitingEvidence"),
    ("reproducibility_receipt_route", "reproducibility_questions", "local_replay_summary_pending", "local_operator_replay_pending", "CI parity", "AwaitingEvidence"),
    ("non_terminal_closure_receipt_route", "non_terminal_closure_questions", "local_closure_summary_pending", "docs/FOUNDATION_TEST_EVIDENCE_BOUNDARY.md", "terminal closure", "AwaitingEvidence"),
)
EXPECTED_ROUTING_ROOT_KEYS = {
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
    "receipt_routes",
    "release_readiness_claimed",
    "route_id",
    "schema_version",
    "secret_clearance_claimed",
    "security_clearance_claimed",
    "solver_outcome",
    "status",
    "terminal_closure_claimed",
}
EXPECTED_RECEIPT_ROUTE_KEYS = {
    "blocked_promotion",
    "public_safe_note",
    "receipt_ref",
    "route_id",
    "state",
    "surface_id",
    "verification_ref",
}
ALLOWED_RECEIPT_REFS = {
    ".tmp/workspace-governance-preflight-receipt.json",
    "local_cli_summary_pending",
    "local_closure_summary_pending",
    "local_gap_summary_pending",
    "local_replay_summary_pending",
}
ALLOWED_VERIFICATION_REFS = {
    "git diff --check",
    "local_operator_replay_pending",
    "local_operator_review_pending",
}
EXPECTED_GAP_WARNING_ENTRIES = (
    ("focused_validator_scope_gap", "focused_validator_questions", "coverage_gap", "local_gap_summary_pending", "full-test pass", "AwaitingEvidence"),
    ("targeted_pytest_scope_gap", "targeted_pytest_questions", "coverage_gap", "local_gap_summary_pending", "complete coverage", "AwaitingEvidence"),
    ("full_preflight_scope_gap", "full_preflight_questions", "coverage_gap", "local_gap_summary_pending", "release readiness", "AwaitingEvidence"),
    ("warning_triage_unresolved_gap", "warning_triage_questions", "warning_triage", "local_warning_summary_pending", "warning-free claim", "AwaitingEvidence"),
    ("diff_hygiene_warning_gap", "diff_hygiene_questions", "warning_triage", "local_warning_summary_pending", "secret clearance", "AwaitingEvidence"),
    ("coverage_gap_explicit", "coverage_gap_questions", "coverage_gap", "local_gap_summary_pending", "complete coverage", "AwaitingEvidence"),
    ("reproducibility_replay_gap", "reproducibility_questions", "replay_gap", "local_replay_summary_pending", "CI parity", "AwaitingEvidence"),
    ("non_terminal_closure_gap", "non_terminal_closure_questions", "closure_gap", "local_closure_summary_pending", "terminal closure", "AwaitingEvidence"),
)
EXPECTED_GAP_WARNING_ROOT_KEYS = {
    "blocked_claims",
    "ci_parity_claimed",
    "complete_coverage_claimed",
    "customer_readiness_claimed",
    "deployment_allowed",
    "deployment_readiness_claimed",
    "external_publication_allowed",
    "flake_free_guarantee_claimed",
    "full_test_pass_claimed",
    "gap_warning_entries",
    "gap_warning_id",
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
}
EXPECTED_GAP_WARNING_ENTRY_KEYS = {
    "blocked_claim",
    "entry_id",
    "entry_type",
    "evidence_ref",
    "public_safe_note",
    "state",
    "surface_id",
}
ALLOWED_GAP_WARNING_EVIDENCE_REFS = {
    "local_closure_summary_pending",
    "local_gap_summary_pending",
    "local_replay_summary_pending",
    "local_warning_summary_pending",
}
REQUIRED_DOC_PHRASES = (
    "Foundation Test Evidence Boundary",
    "Witness packet: [`../examples/foundation_test_evidence_witness.awaiting_evidence.json`]",
    "Receipt routing packet: [`../examples/foundation_test_receipt_routing.awaiting_evidence.json`]",
    "Gap/warning register packet: [`../examples/foundation_test_gap_warning_register.awaiting_evidence.json`]",
    "Rule: Test-evidence preparation is a local planning boundary, not a full-test",
    "No full-test-pass, complete-coverage, CI-parity, release-readiness",
    "test_evidence_boundary_state=AwaitingEvidence",
    "receipt_routing_state=AwaitingEvidence",
    "gap_warning_register_state=AwaitingEvidence",
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
    "Full preflight | `.tmp/workspace-governance-preflight-receipt.json` | `scripts/run_workspace_governance_checks.py` | release readiness",
    "Receipt validation | `.tmp/workspace-governance-preflight-receipt.json` | `scripts/validate_workspace_governance_preflight_receipt.py` | terminal closure",
    "Warning triage unresolved gap | `local_warning_summary_pending` | warning-free claim | `AwaitingEvidence`",
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


def validate_receipt_routing_packet(payload: dict[str, Any]) -> list[TestEvidenceFinding]:
    """Return findings for test-evidence receipt-routing drift."""

    findings: list[TestEvidenceFinding] = []
    findings.extend(validate_routing_root_contract(payload))
    findings.extend(validate_receipt_routes(payload.get("receipt_routes")))
    findings.extend(validate_forbidden_value_patterns(payload))
    findings.extend(validate_forbidden_promotion_patterns(payload))
    return findings


def validate_gap_warning_packet(payload: dict[str, Any]) -> list[TestEvidenceFinding]:
    """Return findings for test-evidence warning and coverage-gap drift."""

    findings: list[TestEvidenceFinding] = []
    findings.extend(validate_gap_warning_root_contract(payload))
    findings.extend(validate_gap_warning_entries(payload.get("gap_warning_entries")))
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


def validate_routing_root_contract(payload: dict[str, Any]) -> list[TestEvidenceFinding]:
    """Return findings for root-level receipt-routing drift."""

    findings: list[TestEvidenceFinding] = []
    if set(payload) != EXPECTED_ROUTING_ROOT_KEYS:
        findings.append(
            TestEvidenceFinding(
                "test_receipt_routing_root_keys_invalid",
                f"root keys must be: {', '.join(sorted(EXPECTED_ROUTING_ROOT_KEYS))}",
            )
        )
    expected_values = {
        "route_id": EXPECTED_ROUTING_ID,
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
                    "test_receipt_routing_root_value_invalid",
                    f"{key} must be {expected_value!r}",
                )
            )
    if tuple(payload.get("blocked_claims") or ()) != EXPECTED_BLOCKED_CLAIMS:
        findings.append(
            TestEvidenceFinding(
                "test_receipt_routing_blocked_claims_invalid",
                f"blocked_claims must be: {', '.join(EXPECTED_BLOCKED_CLAIMS)}",
            )
        )
    next_action = payload.get("next_action")
    if not isinstance(next_action, str) or "keep receipt routing local and scoped" not in next_action:
        findings.append(
            TestEvidenceFinding(
                "test_receipt_routing_next_action_invalid",
                "next_action must preserve local scoped receipt routing",
            )
        )
    return findings


def validate_receipt_routes(receipt_routes: object) -> list[TestEvidenceFinding]:
    """Return findings for receipt-route inventory and reference drift."""

    findings: list[TestEvidenceFinding] = []
    if not isinstance(receipt_routes, list) or not all(isinstance(route, dict) for route in receipt_routes):
        return [TestEvidenceFinding("test_receipt_routes_invalid", "receipt_routes must be a list of objects")]
    observed_routes = tuple(
        (
            route.get("route_id"),
            route.get("surface_id"),
            route.get("receipt_ref"),
            route.get("verification_ref"),
            route.get("blocked_promotion"),
            route.get("state"),
        )
        for route in receipt_routes
    )
    if observed_routes != EXPECTED_RECEIPT_ROUTES:
        findings.append(
            TestEvidenceFinding(
                "test_receipt_route_inventory_invalid",
                "receipt-route inventory does not match the Foundation Mode test-evidence routing set",
            )
        )
    route_ids = [route.get("route_id") for route in receipt_routes]
    if len(set(route_ids)) != len(route_ids):
        findings.append(TestEvidenceFinding("test_receipt_route_duplicate", "route ids must be unique"))
    for route in receipt_routes:
        route_id = str(route.get("route_id", "<missing>"))
        if set(route) != EXPECTED_RECEIPT_ROUTE_KEYS:
            findings.append(
                TestEvidenceFinding(
                    "test_receipt_route_keys_invalid",
                    f"{route_id} route keys must be: {', '.join(sorted(EXPECTED_RECEIPT_ROUTE_KEYS))}",
                )
            )
        if route.get("state") != "AwaitingEvidence":
            findings.append(
                TestEvidenceFinding(
                    "test_receipt_route_state_invalid",
                    f"{route_id} state must be AwaitingEvidence",
                )
            )
        receipt_ref = route.get("receipt_ref")
        if not isinstance(receipt_ref, str) or receipt_ref not in ALLOWED_RECEIPT_REFS:
            findings.append(
                TestEvidenceFinding(
                    "test_receipt_route_receipt_ref_invalid",
                    f"{route_id} receipt_ref must be a governed local receipt reference",
                )
            )
        verification_ref = route.get("verification_ref")
        if not isinstance(verification_ref, str) or not is_allowed_verification_ref(verification_ref):
            findings.append(
                TestEvidenceFinding(
                    "test_receipt_route_verification_ref_invalid",
                    f"{route_id} verification_ref must be a public repository path or governed local review placeholder",
                )
            )
        if not isinstance(route.get("blocked_promotion"), str) or not route["blocked_promotion"].strip():
            findings.append(
                TestEvidenceFinding(
                    "test_receipt_route_blocked_promotion_invalid",
                    f"{route_id} blocked_promotion must be a non-empty string",
                )
            )
        if not isinstance(route.get("public_safe_note"), str) or not route["public_safe_note"].strip():
            findings.append(
                TestEvidenceFinding(
                    "test_receipt_route_note_invalid",
                    f"{route_id} public_safe_note must be a non-empty string",
                )
            )
    return findings


def is_allowed_verification_ref(verification_ref: str) -> bool:
    """Return whether a verification reference is public-safe and local."""

    if verification_ref in ALLOWED_VERIFICATION_REFS:
        return True
    if "\\" in verification_ref or "://" in verification_ref:
        return False
    verification_path = Path(verification_ref)
    if verification_path.is_absolute() or ".." in verification_path.parts:
        return False
    return (REPO_ROOT / verification_path).exists()


def validate_gap_warning_root_contract(payload: dict[str, Any]) -> list[TestEvidenceFinding]:
    """Return findings for root-level warning and coverage-gap register drift."""

    findings: list[TestEvidenceFinding] = []
    if set(payload) != EXPECTED_GAP_WARNING_ROOT_KEYS:
        findings.append(
            TestEvidenceFinding(
                "test_gap_warning_root_keys_invalid",
                f"root keys must be: {', '.join(sorted(EXPECTED_GAP_WARNING_ROOT_KEYS))}",
            )
        )
    expected_values = {
        "gap_warning_id": EXPECTED_GAP_WARNING_ID,
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
                    "test_gap_warning_root_value_invalid",
                    f"{key} must be {expected_value!r}",
                )
            )
    if tuple(payload.get("blocked_claims") or ()) != EXPECTED_BLOCKED_CLAIMS:
        findings.append(
            TestEvidenceFinding(
                "test_gap_warning_blocked_claims_invalid",
                f"blocked_claims must be: {', '.join(EXPECTED_BLOCKED_CLAIMS)}",
            )
        )
    next_action = payload.get("next_action")
    if not isinstance(next_action, str) or "keep warning and coverage gaps visible" not in next_action:
        findings.append(
            TestEvidenceFinding(
                "test_gap_warning_next_action_invalid",
                "next_action must preserve local warning and coverage-gap visibility",
            )
        )
    return findings


def validate_gap_warning_entries(gap_warning_entries: object) -> list[TestEvidenceFinding]:
    """Return findings for warning and coverage-gap entry drift."""

    findings: list[TestEvidenceFinding] = []
    if not isinstance(gap_warning_entries, list) or not all(isinstance(entry, dict) for entry in gap_warning_entries):
        return [TestEvidenceFinding("test_gap_warning_entries_invalid", "gap_warning_entries must be a list of objects")]
    observed_entries = tuple(
        (
            entry.get("entry_id"),
            entry.get("surface_id"),
            entry.get("entry_type"),
            entry.get("evidence_ref"),
            entry.get("blocked_claim"),
            entry.get("state"),
        )
        for entry in gap_warning_entries
    )
    if observed_entries != EXPECTED_GAP_WARNING_ENTRIES:
        findings.append(
            TestEvidenceFinding(
                "test_gap_warning_entry_inventory_invalid",
                "gap-warning inventory does not match the Foundation Mode test-evidence gap set",
            )
        )
    entry_ids = [entry.get("entry_id") for entry in gap_warning_entries]
    if len(set(entry_ids)) != len(entry_ids):
        findings.append(TestEvidenceFinding("test_gap_warning_entry_duplicate", "entry ids must be unique"))
    for entry in gap_warning_entries:
        entry_id = str(entry.get("entry_id", "<missing>"))
        if set(entry) != EXPECTED_GAP_WARNING_ENTRY_KEYS:
            findings.append(
                TestEvidenceFinding(
                    "test_gap_warning_entry_keys_invalid",
                    f"{entry_id} entry keys must be: {', '.join(sorted(EXPECTED_GAP_WARNING_ENTRY_KEYS))}",
                )
            )
        if entry.get("state") != "AwaitingEvidence":
            findings.append(
                TestEvidenceFinding(
                    "test_gap_warning_entry_state_invalid",
                    f"{entry_id} state must be AwaitingEvidence",
                )
            )
        evidence_ref = entry.get("evidence_ref")
        if not isinstance(evidence_ref, str) or evidence_ref not in ALLOWED_GAP_WARNING_EVIDENCE_REFS:
            findings.append(
                TestEvidenceFinding(
                    "test_gap_warning_entry_evidence_ref_invalid",
                    f"{entry_id} evidence_ref must be a governed local gap or warning reference",
                )
            )
        if not isinstance(entry.get("blocked_claim"), str) or not entry["blocked_claim"].strip():
            findings.append(
                TestEvidenceFinding(
                    "test_gap_warning_entry_blocked_claim_invalid",
                    f"{entry_id} blocked_claim must be a non-empty string",
                )
            )
        if not isinstance(entry.get("public_safe_note"), str) or not entry["public_safe_note"].strip():
            findings.append(
                TestEvidenceFinding(
                    "test_gap_warning_entry_note_invalid",
                    f"{entry_id} public_safe_note must be a non-empty string",
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
    routing_path: Path = DEFAULT_ROUTING_PATH,
    gap_warning_path: Path = DEFAULT_GAP_WARNING_PATH,
) -> list[TestEvidenceFinding]:
    """Validate the Foundation Mode test-evidence boundary artifacts."""

    doc_text = load_text(doc_path, "test-evidence boundary doc")
    packet_payload = load_json_object(packet_path, "test-evidence witness packet")
    routing_payload = load_json_object(routing_path, "test-evidence receipt routing packet")
    gap_warning_payload = load_json_object(gap_warning_path, "test-evidence gap warning packet")
    return [
        *validate_doc_text(doc_text),
        *validate_packet(packet_payload),
        *validate_receipt_routing_packet(routing_payload),
        *validate_gap_warning_packet(gap_warning_payload),
    ]


def main(argv: list[str] | None = None) -> int:
    """Validate test-evidence artifacts and print deterministic status."""

    parser = argparse.ArgumentParser(description="Validate Foundation Mode test-evidence artifacts.")
    parser.add_argument("--doc", type=Path, default=DEFAULT_DOC_PATH)
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET_PATH)
    parser.add_argument("--routing", type=Path, default=DEFAULT_ROUTING_PATH)
    parser.add_argument("--gap-warning", type=Path, default=DEFAULT_GAP_WARNING_PATH)
    args = parser.parse_args(argv)

    try:
        findings = validate_foundation_test_evidence_boundary(args.doc, args.packet, args.routing, args.gap_warning)
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
    print("[PASS] foundation_test_receipt_routing")
    print("[PASS] foundation_test_gap_warning_register")
    print("STATUS: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
