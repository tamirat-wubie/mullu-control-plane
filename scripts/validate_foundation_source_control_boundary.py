#!/usr/bin/env python3
"""Validate the Foundation Mode source-control boundary.

Purpose: keep commit preparation explicit while staging, commit, push, pull
request, release, deployment, and secret publication remain blocked until the
user explicitly requests the next Git action.
Governance scope: Foundation Mode, source-control hygiene, commit-boundary
preparation, no external publication, no deployment claim, and no secret drift.
Dependencies: docs/FOUNDATION_SOURCE_CONTROL_BOUNDARY.md and
examples/foundation_source_control_boundary.awaiting_commit.json.
Invariants:
  - Validation is read-only.
  - The packet prepares a commit boundary but does not authorize Git effects.
  - Staging, commit, push, pull request, release, deployment, and secret
    publication remain blocked.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
import re
import sys
from typing import Any

try:
    from run_workspace_governance_checks import build_check_commands
except ModuleNotFoundError:  # pragma: no cover - exercised when imported as package.
    from scripts.run_workspace_governance_checks import build_check_commands


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DOC_PATH = REPO_ROOT / "docs" / "FOUNDATION_SOURCE_CONTROL_BOUNDARY.md"
DEFAULT_PACKET_PATH = REPO_ROOT / "examples" / "foundation_source_control_boundary.awaiting_commit.json"

EXPECTED_BOUNDARY_ID = "foundation_source_control_boundary.awaiting_commit.v1"
EXPECTED_CHANGE_FAMILIES = (
    "foundation_posture",
    "source_control_review_checklist_boundary",
    "local_release_packet_rehearsal_boundary",
    "python_dependency_visibility_rehearsal_boundary",
    "operator_readiness_boundary",
    "solo_daily_loop_boundary",
    "learning_path_boundary",
    "learning_loop_rehearsal_boundary",
    "concept_glossary_rehearsal_boundary",
    "life_meaning_doctrine_rehearsal_boundary",
    "architecture_map_boundary",
    "system_boundary_inventory_boundary",
    "module_inventory_boundary",
    "component_contract_boundary",
    "interface_map_boundary",
    "dependency_graph_boundary",
    "invariant_map_boundary",
    "hazard_map_boundary",
    "proof_reference_boundary",
    "gap_register_boundary",
    "diff_review_boundary",
    "change_handoff_boundary",
    "local_workstation_boundary",
    "documentation_boundary",
    "plain_language_status_boundary",
    "accessibility_language_boundary",
    "capability_roadmap_boundary",
    "agentic_management_boundary",
    "operations_runbook_boundary",
    "claim_boundary",
    "website_posture_boundary",
    "research_notebook_boundary",
    "evidence_ledger_boundary",
    "decision_journal_boundary",
    "next_action_boundary",
    "local_proof_thread",
    "test_evidence_boundary",
    "private_recovery_boundary",
    "private_recovery_rehearsal_boundary",
    "secrets_credentials_boundary",
    "security_baseline_boundary",
    "cost_budget_boundary",
    "payment_provider_boundary",
    "runtime_environment_boundary",
    "backup_export_boundary",
    "deployment_deferral_boundary",
    "external_infrastructure_boundary",
    "runtime_secret_handoff_rehearsal_boundary",
    "runtime_witness_deferral_boundary",
    "production_dependency_evidence_rehearsal_boundary",
    "external_evidence_acceptance_rehearsal_boundary",
    "deployment_upstream_api_gate_rehearsal_boundary",
    "gateway_dns_target_binding_rehearsal_boundary",
    "gateway_dns_publication_rehearsal_boundary",
    "gateway_dns_resolution_receipt_rehearsal_boundary",
    "gateway_endpoint_reachability_rehearsal_boundary",
    "gateway_endpoint_evidence_receipt_rehearsal_boundary",
    "public_health_declaration_rehearsal_boundary",
    "deployment_witness_input_boundary",
    "deployment_witness_preflight_rehearsal_boundary",
    "deployment_witness_dispatch_rehearsal_boundary",
    "deployment_witness_artifact_validation_rehearsal_boundary",
    "deployment_witness_evidence_handoff_boundary",
    "deployment_witness_evidence_ledger_routing_boundary",
    "domain_email_boundary",
    "legal_business_boundary",
    "legal_business_question_rehearsal_boundary",
    "legal_review_deferral_boundary",
    "company_formation_deferral_boundary",
    "patent_disclosure_deferral_boundary",
    "product_scope_boundary",
    "market_research_boundary",
    "pilot_deferral_boundary",
    "pilot_deferral_rehearsal_boundary",
    "reassessment_gate_boundary",
    "support_readiness_boundary",
    "support_triage_rehearsal_boundary",
    "intake_onboarding_boundary",
    "intake_questionnaire_rehearsal_boundary",
    "customer_access_boundary",
    "customer_access_policy_rehearsal_boundary",
    "github_app_token_format_boundary",
    "public_ci_window_boundary",
    "privacy_data_boundary",
    "privacy_minimization_rehearsal_boundary",
    "funding_team_boundary",
    "funding_team_obligation_rehearsal_boundary",
    "community_network_boundary",
    "community_network_no_outreach_rehearsal_boundary",
    "public_claim_alignment",
    "phi_gps_v3_runtime_safety_packet",
    "governance_preflight_wiring",
)
DOC_ONLY_CHANGE_FAMILIES = (
    "public_claim_alignment",
    "phi_gps_v3_runtime_safety_packet",
    "governance_preflight_wiring",
)


def _command_to_display(args: tuple[str, ...]) -> str:
    """Render a preflight command with the portable `python` executable label."""

    return " ".join(("python", *args[1:]))


def _build_expected_required_checks() -> tuple[str, ...]:
    """Return source-control checks from the canonical Foundation preflight order."""

    foundation_checks = tuple(
        _command_to_display(command.args)
        for command in build_check_commands("python")
        if command.name == "foundation_mode" or command.name.startswith("foundation_")
    )
    return (
        *foundation_checks,
        "python scripts/run_workspace_governance_checks.py --json --receipt-path .tmp/workspace-governance-preflight-receipt.json",
        "python scripts/validate_workspace_governance_preflight_receipt.py --receipt .tmp/workspace-governance-preflight-receipt.json",
        "git diff --check",
        "git status --short",
    )


def _build_expected_preflight_family_coverage() -> tuple[str, ...]:
    """Return Foundation preflight families that must be represented in the packet."""

    return tuple(
        "foundation_posture" if command.name == "foundation_mode" else command.name.removeprefix("foundation_")
        for command in build_check_commands("python")
        if command.name == "foundation_mode"
        or (command.name.startswith("foundation_") and command.name != "foundation_source_control_boundary")
    )


EXPECTED_REQUIRED_CHECKS = _build_expected_required_checks()
EXPECTED_PREFLIGHT_FAMILY_COVERAGE = _build_expected_preflight_family_coverage()
EXPECTED_ROOT_KEYS = {
    "boundary_id",
    "change_families",
    "commit_allowed",
    "commit_message_candidate",
    "commit_state",
    "deployment_allowed",
    "external_publication_allowed",
    "next_action",
    "pull_request_allowed",
    "push_allowed",
    "release_allowed",
    "required_checks",
    "rollback_note",
    "schema_version",
    "secret_publication_allowed",
    "solver_outcome",
    "staging_allowed",
    "status",
}
EXPECTED_FAMILY_KEYS = {
    "family_id",
    "required_evidence",
    "state",
    "summary",
}
REQUIRED_DOC_PHRASES = (
    "Foundation Source Control Boundary",
    "Boundary packet: [`../examples/foundation_source_control_boundary.awaiting_commit.json`]",
    "Rule: Commit readiness is prepared locally, but commit execution requires an",
    "No staging, commit, push, pull request, release, deployment, customer access, or",
    "Solo daily loop | Local solo-loop",
    "source_control_boundary_state=AwaitingEvidence",
    "commit_state=AwaitingCommit",
    "staging_allowed=false",
    "commit_allowed=false",
    "push_allowed=false",
    "pull_request_allowed=false",
    "Change handoff | Local change-family",
    "Plain-language status | Local current-posture",
    "Accessibility/language | Local reading-level",
    "Capability roadmap | Local capability-family",
    "Agentic management | Local goal-intake",
    "Operations/runbook | Local runbook-inventory",
    "Test evidence | Local focused-validator",
    "Payment provider | Local provider-selection",
    "Market research | Local problem",
    "Runtime secret handoff rehearsal | Local runtime-secret-handoff",
    "Runtime witness deferral | Local runtime-witness-deferral",
    "Production dependency evidence rehearsal | Local production-dependency",
    "External evidence acceptance rehearsal | Local evidence-acceptance",
    "Deployment upstream API gate rehearsal | Local upstream-API",
    "Gateway DNS target binding rehearsal | Local DNS-target-binding",
    "Gateway DNS publication rehearsal | Local DNS-publication",
    "Gateway DNS resolution receipt rehearsal | Local DNS-resolution",
    "Gateway endpoint reachability rehearsal | Local endpoint-reachability",
    "Gateway endpoint evidence receipt rehearsal | Local endpoint-evidence",
    "Public health declaration rehearsal | Local public-health",
    "Deployment witness input | Local deployment-witness-input",
    "Deployment witness preflight rehearsal | Local deployment-witness-preflight",
    "Deployment witness dispatch rehearsal | Local workflow-dispatch",
    "Deployment witness artifact validation rehearsal | Local artifact-validation",
    "Deployment witness evidence handoff | Local evidence-handoff",
    "Deployment witness evidence ledger routing | Local evidence-ledger-routing",
    "Private recovery rehearsal | Local recovery-rehearsal",
    "Learning-loop rehearsal | Local learning-loop",
    "Concept glossary rehearsal | Local concept-glossary",
    "Life/meaning doctrine rehearsal | Local life-meaning-doctrine",
    "Legal/business question rehearsal | Local legal-question",
    "Legal-review deferral | Local legal-review-deferral",
    "Company-formation deferral | Local company-formation-deferral",
    "Patent/disclosure deferral | Local patent-disclosure-deferral",
    "Pilot deferral rehearsal | Local pilot-stop-rule",
    "Reassessment gate | Local reassessment",
    "Support triage rehearsal | Local support-triage",
    "Intake questionnaire rehearsal | Local intake-questionnaire",
    "Customer access | Local access-policy",
    "Customer-access policy rehearsal | Local access-rule",
    "GitHub App token format | Local token-format",
    "Privacy minimization rehearsal | Local minimization",
    "Funding/team | Local funding-readiness",
    "Funding/team obligation rehearsal | Local obligation",
    "Community/network | Local relationship",
    "Community/network no-outreach rehearsal | Local no-outreach",
    "python scripts/validate_foundation_source_control_boundary.py",
    "Phi-GPS v3 runtime safety packet | Local Phi-GPS compiler",
    "Source-control review checklist | Local review-checklist",
    "Local release-packet rehearsal | Local release-packet",
)
FORBIDDEN_PACKET_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("publication_authorized", re.compile(r"\b(?:push|publish|publication|pull request|release)\s+(?:allowed|authorized|ready)\b", re.IGNORECASE)),
    ("deployment_authorized", re.compile(r"\bdeployment\s+(?:allowed|authorized|ready)\b", re.IGNORECASE)),
    ("secret_publication_authorized", re.compile(r"\bsecret publication\s+(?:allowed|authorized|ready)\b", re.IGNORECASE)),
)


@dataclass(frozen=True, slots=True)
class SourceControlFinding:
    """One deterministic source-control boundary validation finding."""

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


def validate_doc_text(text: str) -> list[SourceControlFinding]:
    """Return findings for missing source-control documentation anchors."""

    findings: list[SourceControlFinding] = []
    for phrase in REQUIRED_DOC_PHRASES:
        if phrase not in text:
            findings.append(
                SourceControlFinding(
                    "foundation_source_control_doc_phrase_missing",
                    f"source-control boundary doc missing required phrase: {phrase}",
                )
            )
    for command in EXPECTED_REQUIRED_CHECKS:
        if command not in text:
            findings.append(
                SourceControlFinding(
                    "foundation_source_control_doc_required_check_missing",
                    f"source-control boundary doc missing required check: {command}",
                )
            )
    return findings


def validate_packet(payload: dict[str, Any]) -> list[SourceControlFinding]:
    """Return findings for source-control packet drift."""

    findings: list[SourceControlFinding] = []
    findings.extend(validate_root_contract(payload))
    findings.extend(validate_change_families(payload.get("change_families")))
    findings.extend(validate_required_checks(payload.get("required_checks")))
    findings.extend(validate_forbidden_packet_patterns(payload))
    return findings


def validate_root_contract(payload: dict[str, Any]) -> list[SourceControlFinding]:
    """Return findings for root-level source-control packet drift."""

    findings: list[SourceControlFinding] = []
    if set(payload) != EXPECTED_ROOT_KEYS:
        findings.append(
            SourceControlFinding(
                "source_control_root_keys_invalid",
                f"root keys must be: {', '.join(sorted(EXPECTED_ROOT_KEYS))}",
            )
        )
    expected_values = {
        "boundary_id": EXPECTED_BOUNDARY_ID,
        "schema_version": 1,
        "status": "AwaitingEvidence",
        "solver_outcome": "AwaitingEvidence",
        "commit_state": "AwaitingCommit",
        "staging_allowed": False,
        "commit_allowed": False,
        "push_allowed": False,
        "pull_request_allowed": False,
        "release_allowed": False,
        "deployment_allowed": False,
        "external_publication_allowed": False,
        "secret_publication_allowed": False,
    }
    for key, expected_value in expected_values.items():
        if payload.get(key) != expected_value:
            findings.append(
                SourceControlFinding(
                    "source_control_root_value_invalid",
                    f"{key} must be {expected_value!r}",
                )
            )
    commit_message = payload.get("commit_message_candidate")
    if not isinstance(commit_message, str) or not re.fullmatch(r"[a-z]+\(foundation\): .{1,50}", commit_message):
        findings.append(
            SourceControlFinding(
                "source_control_commit_message_invalid",
                "commit_message_candidate must use a governed foundation-scoped subject",
            )
        )
    next_action = payload.get("next_action")
    if not isinstance(next_action, str) or "explicit user request" not in next_action:
        findings.append(
            SourceControlFinding(
                "source_control_next_action_invalid",
                "next_action must require an explicit user request",
            )
        )
    rollback_note = payload.get("rollback_note")
    if not isinstance(rollback_note, str) or "revert commit" not in rollback_note:
        findings.append(
            SourceControlFinding(
                "source_control_rollback_note_invalid",
                "rollback_note must name the post-commit revert path",
            )
        )
    return findings


def validate_change_families(change_families: object) -> list[SourceControlFinding]:
    """Return findings for change-family packet drift."""

    findings: list[SourceControlFinding] = []
    if not isinstance(change_families, list) or not all(isinstance(family, dict) for family in change_families):
        return [SourceControlFinding("source_control_change_families_invalid", "change_families must be a list of objects")]
    observed_family_ids = tuple(family.get("family_id") for family in change_families)
    if observed_family_ids != EXPECTED_CHANGE_FAMILIES:
        findings.append(
            SourceControlFinding(
                "source_control_family_ids_invalid",
                f"family ids must be: {', '.join(EXPECTED_CHANGE_FAMILIES)}",
            )
        )
    missing_preflight_families = tuple(
        family_id for family_id in EXPECTED_PREFLIGHT_FAMILY_COVERAGE if family_id not in observed_family_ids
    )
    unexpected_non_preflight_families = tuple(
        family_id
        for family_id in observed_family_ids
        if family_id not in EXPECTED_PREFLIGHT_FAMILY_COVERAGE and family_id not in DOC_ONLY_CHANGE_FAMILIES
    )
    if missing_preflight_families:
        findings.append(
            SourceControlFinding(
                "source_control_preflight_family_coverage_missing",
                f"preflight families missing from source-control packet: {', '.join(missing_preflight_families)}",
            )
        )
    if unexpected_non_preflight_families:
        findings.append(
            SourceControlFinding(
                "source_control_preflight_family_coverage_unexpected",
                f"families are neither preflight-derived nor documented doc-only exceptions: {', '.join(unexpected_non_preflight_families)}",
            )
        )
    if len(set(observed_family_ids)) != len(observed_family_ids):
        findings.append(SourceControlFinding("source_control_family_duplicate", "family ids must be unique"))
    for family in change_families:
        family_id = str(family.get("family_id", "<missing>"))
        if set(family) != EXPECTED_FAMILY_KEYS:
            findings.append(
                SourceControlFinding(
                    "source_control_family_keys_invalid",
                    f"{family_id} family keys must be: {', '.join(sorted(EXPECTED_FAMILY_KEYS))}",
                )
            )
        if family.get("state") != "AwaitingEvidence":
            findings.append(
                SourceControlFinding(
                    "source_control_family_state_invalid",
                    f"{family_id} state must be AwaitingEvidence",
                )
            )
        required_evidence = family.get("required_evidence")
        if not isinstance(required_evidence, list) or len(required_evidence) < 3:
            findings.append(
                SourceControlFinding(
                    "source_control_family_evidence_invalid",
                    f"{family_id} required_evidence must contain at least three paths",
                )
            )
        elif not all(isinstance(path, str) and path and not path.startswith(".tmp") for path in required_evidence):
            findings.append(
                SourceControlFinding(
                    "source_control_family_evidence_invalid",
                    f"{family_id} required_evidence must contain public repository paths only",
                )
            )
        elif len(set(required_evidence)) != len(required_evidence):
            findings.append(
                SourceControlFinding(
                    "source_control_family_evidence_duplicate",
                    f"{family_id} required_evidence paths must be unique",
                )
            )
        if not isinstance(family.get("summary"), str) or not family["summary"].strip():
            findings.append(
                SourceControlFinding(
                    "source_control_family_summary_invalid",
                    f"{family_id} summary must be non-empty",
                )
            )
    return findings


def validate_required_checks(required_checks: object) -> list[SourceControlFinding]:
    """Return findings when required source-control checks drift."""

    if tuple(required_checks or ()) != EXPECTED_REQUIRED_CHECKS:
        return [
            SourceControlFinding(
                "source_control_required_checks_invalid",
                f"required_checks must be: {', '.join(EXPECTED_REQUIRED_CHECKS)}",
            )
        ]
    return []


def validate_forbidden_packet_patterns(payload: dict[str, Any]) -> list[SourceControlFinding]:
    """Return findings if the packet text drifts into publication readiness."""

    serialized_payload = json.dumps(payload, sort_keys=True)
    findings: list[SourceControlFinding] = []
    for rule_id, pattern in FORBIDDEN_PACKET_PATTERNS:
        if pattern.search(serialized_payload):
            findings.append(
                SourceControlFinding(
                    "source_control_forbidden_publication_phrase",
                    f"source-control packet contains forbidden readiness pattern: {rule_id}",
                )
            )
    return findings


def validate_foundation_source_control_boundary(
    doc_path: Path = DEFAULT_DOC_PATH,
    packet_path: Path = DEFAULT_PACKET_PATH,
) -> list[SourceControlFinding]:
    """Validate the Foundation Mode source-control boundary artifacts."""

    doc_text = load_text(doc_path, "source-control boundary doc")
    packet_payload = load_json_object(packet_path, "source-control boundary packet")
    return [
        *validate_doc_text(doc_text),
        *validate_packet(packet_payload),
    ]


def main(argv: list[str] | None = None) -> int:
    """Validate source-control boundary artifacts and print deterministic status."""

    parser = argparse.ArgumentParser(description="Validate Foundation Mode source-control boundary artifacts.")
    parser.add_argument("--doc", type=Path, default=DEFAULT_DOC_PATH)
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET_PATH)
    args = parser.parse_args(argv)

    try:
        findings = validate_foundation_source_control_boundary(args.doc, args.packet)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"[FAIL] foundation_source_control_load: {exc}", file=sys.stderr)
        print("STATUS: failed", file=sys.stderr)
        return 1

    if findings:
        for finding in findings:
            print(f"[FAIL] {finding.rule_id}: {finding.message}", file=sys.stderr)
        print("STATUS: failed", file=sys.stderr)
        return 1
    print("[PASS] foundation_source_control_doc")
    print("[PASS] foundation_source_control_packet")
    print("STATUS: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
