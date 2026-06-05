"""Tests for the Foundation Mode source-control boundary validator.

Purpose: prove commit-boundary preparation stays local and does not authorize
staging, commit, push, pull request, release, deployment, or secret publication.
Governance scope: Foundation Mode, source-control hygiene, commit-boundary
preparation, and external-publication blocking.
Dependencies: scripts.validate_foundation_source_control_boundary.
Invariants: the packet keeps all Git effects blocked until explicit user
request and preserves required verification commands.
"""

from __future__ import annotations

from copy import deepcopy
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validate_foundation_source_control_boundary import (  # noqa: E402
    DEFAULT_PACKET_PATH,
    DOC_ONLY_CHANGE_FAMILIES,
    EXPECTED_BOUNDARY_ID,
    EXPECTED_CHANGE_FAMILIES,
    EXPECTED_PREFLIGHT_FAMILY_COVERAGE,
    EXPECTED_REQUIRED_CHECKS,
    load_json_object,
    validate_foundation_source_control_boundary,
    validate_packet,
)
from scripts.run_workspace_governance_checks import build_check_commands  # noqa: E402


def test_foundation_source_control_boundary_artifacts_pass() -> None:
    assert validate_foundation_source_control_boundary() == []


def test_source_control_packet_has_expected_identity_and_blockers() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "source-control packet")

    assert payload["boundary_id"] == EXPECTED_BOUNDARY_ID
    assert tuple(family["family_id"] for family in payload["change_families"]) == EXPECTED_CHANGE_FAMILIES
    assert tuple(payload["required_checks"]) == EXPECTED_REQUIRED_CHECKS
    assert payload["staging_allowed"] is False
    assert payload["commit_allowed"] is False
    assert payload["push_allowed"] is False
    assert payload["pull_request_allowed"] is False
    assert payload["deployment_allowed"] is False


def test_required_checks_cover_current_foundation_preflight_commands() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "source-control packet")
    required_checks = tuple(payload["required_checks"])
    foundation_preflight_checks = tuple(
        " ".join(("python", *command.args[1:]))
        for command in build_check_commands("python")
        if command.name == "foundation_mode" or command.name.startswith("foundation_")
    )
    full_preflight_command = (
        "python scripts/run_workspace_governance_checks.py --json "
        "--receipt-path .tmp/workspace-governance-preflight-receipt.json"
    )
    full_preflight_index = required_checks.index(full_preflight_command)

    assert foundation_preflight_checks
    assert required_checks[: len(foundation_preflight_checks)] == foundation_preflight_checks
    assert full_preflight_index == len(foundation_preflight_checks)


def test_change_families_cover_foundation_preflight_boundaries_except_self() -> None:
    missing_families = tuple(family for family in EXPECTED_PREFLIGHT_FAMILY_COVERAGE if family not in EXPECTED_CHANGE_FAMILIES)
    extra_families = tuple(
        family
        for family in EXPECTED_CHANGE_FAMILIES
        if family not in EXPECTED_PREFLIGHT_FAMILY_COVERAGE and family not in DOC_ONLY_CHANGE_FAMILIES
    )

    assert EXPECTED_PREFLIGHT_FAMILY_COVERAGE
    assert missing_families == ()
    assert extra_families == ()
    assert "source_control_boundary" not in EXPECTED_CHANGE_FAMILIES


def test_deployment_witness_change_families_cover_required_chain() -> None:
    expected_chain = (
        "deployment_witness_input_boundary",
        "deployment_witness_preflight_rehearsal_boundary",
        "deployment_witness_dispatch_rehearsal_boundary",
        "deployment_witness_artifact_validation_rehearsal_boundary",
        "deployment_witness_evidence_handoff_boundary",
        "deployment_witness_evidence_ledger_routing_boundary",
    )

    assert all(family in EXPECTED_CHANGE_FAMILIES for family in expected_chain)
    assert tuple(
        family for family in EXPECTED_CHANGE_FAMILIES if family.startswith("deployment_witness_")
    ) == expected_chain


def test_external_deployment_change_families_cover_required_chain() -> None:
    expected_chain = (
        "deployment_deferral_boundary",
        "external_infrastructure_boundary",
        "runtime_secret_handoff_rehearsal_boundary",
        "production_dependency_evidence_rehearsal_boundary",
        "external_evidence_acceptance_rehearsal_boundary",
        "deployment_upstream_api_gate_rehearsal_boundary",
        "gateway_dns_target_binding_rehearsal_boundary",
        "gateway_dns_publication_rehearsal_boundary",
        "gateway_dns_resolution_receipt_rehearsal_boundary",
        "gateway_endpoint_reachability_rehearsal_boundary",
        "gateway_endpoint_evidence_receipt_rehearsal_boundary",
        "public_health_declaration_rehearsal_boundary",
    )

    assert all(family in EXPECTED_CHANGE_FAMILIES for family in expected_chain)
    assert tuple(
        family
        for family in EXPECTED_CHANGE_FAMILIES
        if family.startswith(("deployment_", "external_", "runtime_secret_", "production_", "gateway_", "public_health_"))
    ) == expected_chain + (
        "deployment_witness_input_boundary",
        "deployment_witness_preflight_rehearsal_boundary",
        "deployment_witness_dispatch_rehearsal_boundary",
        "deployment_witness_artifact_validation_rehearsal_boundary",
        "deployment_witness_evidence_handoff_boundary",
        "deployment_witness_evidence_ledger_routing_boundary",
    )


def test_packet_rejects_commit_promotion() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "source-control packet")
    candidate = deepcopy(payload)
    candidate["commit_allowed"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "source_control_root_value_invalid" for finding in findings)


def test_packet_rejects_push_promotion() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "source-control packet")
    candidate = deepcopy(payload)
    candidate["push_allowed"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "source_control_root_value_invalid" for finding in findings)


def test_packet_rejects_missing_required_check() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "source-control packet")
    candidate = deepcopy(payload)
    candidate["required_checks"] = candidate["required_checks"][:-1]

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "source_control_required_checks_invalid" for finding in findings)


def test_packet_rejects_missing_preflight_family_coverage() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "source-control packet")
    candidate = deepcopy(payload)
    candidate["change_families"] = [
        family for family in candidate["change_families"] if family["family_id"] != "solo_daily_loop_boundary"
    ]

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "source_control_family_ids_invalid" for finding in findings)
    assert any(finding.rule_id == "source_control_preflight_family_coverage_missing" for finding in findings)


def test_packet_rejects_family_state_promotion() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "source-control packet")
    candidate = deepcopy(payload)
    candidate["change_families"][0]["state"] = "ReadyForCommit"

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "source_control_family_state_invalid" for finding in findings)


def test_packet_rejects_duplicate_family_evidence() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "source-control packet")
    candidate = deepcopy(payload)
    candidate["change_families"][0]["required_evidence"].append(
        candidate["change_families"][0]["required_evidence"][0]
    )

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "source_control_family_evidence_duplicate" for finding in findings)


def test_packet_rejects_publication_phrase() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "source-control packet")
    candidate = deepcopy(payload)
    candidate["change_families"][0]["summary"] = "push allowed after validation"

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "source_control_forbidden_publication_phrase" for finding in findings)
