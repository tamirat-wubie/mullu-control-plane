"""Tests for the Foundation Mode test-evidence boundary validator.

Purpose: prove test-evidence preparation stays local and does not authorize
full-test pass, complete coverage, CI parity, release readiness, security
clearance, secret clearance, customer readiness, legal clearance, terminal
closure, external publication, or deployment.
Governance scope: Foundation Mode, test-evidence surface inventory,
private-value exclusion, validation-scope blocking, and readiness blocking.
Dependencies: scripts.validate_foundation_test_evidence_boundary.
Invariants: test-evidence surfaces remain AwaitingEvidence and reject broad
validation promotion or private-value drift.
"""

from __future__ import annotations

from copy import deepcopy
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validate_foundation_test_evidence_boundary import (  # noqa: E402
    DEFAULT_GAP_WARNING_PATH,
    DEFAULT_PACKET_PATH,
    DEFAULT_ROUTING_PATH,
    DEFAULT_VALIDATION_RECEIPT_PATH,
    EXPECTED_GAP_WARNING_ENTRIES,
    EXPECTED_GAP_WARNING_ID,
    EXPECTED_RECEIPT_ROUTES,
    EXPECTED_ROUTING_ID,
    EXPECTED_SURFACE_NOTE_FRAGMENTS,
    EXPECTED_SURFACES,
    EXPECTED_VALIDATION_RECEIPT_APPLICATION_ID,
    EXPECTED_VALIDATION_RECEIPT_CATEGORIES,
    EXPECTED_VALIDATION_RECEIPT_ITEMS,
    EXPECTED_WITNESS_ID,
    load_json_object,
    validate_foundation_test_evidence_boundary,
    validate_gap_warning_packet,
    validate_packet,
    validate_receipt_routing_packet,
    validate_validation_receipt_application,
)


def test_foundation_test_evidence_boundary_artifacts_pass() -> None:
    assert validate_foundation_test_evidence_boundary() == []


def test_test_evidence_witness_has_expected_identity_and_blockers() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "test-evidence witness")

    assert payload["witness_id"] == EXPECTED_WITNESS_ID
    assert tuple(
        (surface["surface_id"], surface["surface_type"], surface["state"])
        for surface in payload["test_evidence_surfaces"]
    ) == EXPECTED_SURFACES
    assert payload["full_test_pass_claimed"] is False
    assert payload["complete_coverage_claimed"] is False
    assert payload["ci_parity_claimed"] is False
    assert payload["release_readiness_claimed"] is False
    assert payload["terminal_closure_claimed"] is False
    assert payload["deployment_allowed"] is False


def test_runtime_safety_test_evidence_fragments_are_present() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "test-evidence witness")
    surfaces = {surface["surface_id"]: surface for surface in payload["test_evidence_surfaces"]}

    assert EXPECTED_SURFACE_NOTE_FRAGMENTS
    for surface_id, fragments in EXPECTED_SURFACE_NOTE_FRAGMENTS.items():
        assert surface_id in surfaces
        assert fragments
        assert all(fragment in surfaces[surface_id]["public_safe_note"] for fragment in fragments)


def test_witness_rejects_missing_runtime_safety_test_evidence_fragment() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "test-evidence witness")
    candidate = deepcopy(payload)
    candidate["test_evidence_surfaces"][0]["public_safe_note"] = (
        "Draft focused-validator questions without claiming full-test pass."
    )

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "test_evidence_surface_note_fragment_missing" for finding in findings)


def test_receipt_routing_has_expected_identity_and_routes() -> None:
    payload = load_json_object(DEFAULT_ROUTING_PATH, "test receipt routing")

    assert payload["route_id"] == EXPECTED_ROUTING_ID
    assert tuple(
        (
            route["route_id"],
            route["surface_id"],
            route["receipt_ref"],
            route["verification_ref"],
            route["blocked_promotion"],
            route["state"],
        )
        for route in payload["receipt_routes"]
    ) == EXPECTED_RECEIPT_ROUTES
    assert payload["full_test_pass_claimed"] is False
    assert payload["release_readiness_claimed"] is False
    assert payload["terminal_closure_claimed"] is False
    assert payload["deployment_allowed"] is False


def test_gap_warning_register_has_expected_identity_and_entries() -> None:
    payload = load_json_object(DEFAULT_GAP_WARNING_PATH, "test gap warning register")

    assert payload["gap_warning_id"] == EXPECTED_GAP_WARNING_ID
    assert tuple(
        (
            entry["entry_id"],
            entry["surface_id"],
            entry["entry_type"],
            entry["evidence_ref"],
            entry["blocked_claim"],
            entry["state"],
        )
        for entry in payload["gap_warning_entries"]
    ) == EXPECTED_GAP_WARNING_ENTRIES
    assert payload["complete_coverage_claimed"] is False
    assert payload["ci_parity_claimed"] is False
    assert payload["release_readiness_claimed"] is False
    assert payload["deployment_allowed"] is False


def test_validation_receipt_current_packet_has_expected_identity_and_blockers() -> None:
    payload = load_json_object(DEFAULT_VALIDATION_RECEIPT_PATH, "validation receipt current packet")

    assert payload["application_id"] == EXPECTED_VALIDATION_RECEIPT_APPLICATION_ID
    assert tuple(payload["application_categories"]) == EXPECTED_VALIDATION_RECEIPT_CATEGORIES
    assert tuple(item["validation_id"] for item in payload["validation_items"]) == EXPECTED_VALIDATION_RECEIPT_ITEMS
    assert payload["saved_receipt_ref"] == ".tmp/workspace-governance-preflight-receipt.json"
    assert payload["validator_ref"] == "scripts/validate_workspace_governance_preflight_receipt.py"
    assert payload["receipt_presence_observed"] is True
    assert payload["receipt_summary_recorded"] is False
    assert payload["check_count_recorded"] is False
    assert payload["failed_check_names_recorded"] is False
    assert payload["terminal_closure_claimed"] is False
    assert payload["staging_allowed"] is False
    assert payload["deployment_allowed"] is False


def test_witness_rejects_full_test_and_coverage_claims() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "test-evidence witness")
    candidate = deepcopy(payload)
    candidate["full_test_pass_claimed"] = True
    candidate["complete_coverage_claimed"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "test_evidence_root_value_invalid" for finding in findings)


def test_witness_rejects_ci_release_and_terminal_closure_claims() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "test-evidence witness")
    candidate = deepcopy(payload)
    candidate["ci_parity_claimed"] = True
    candidate["release_readiness_claimed"] = True
    candidate["terminal_closure_claimed"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "test_evidence_root_value_invalid" for finding in findings)


def test_witness_rejects_security_customer_legal_and_deployment_claims() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "test-evidence witness")
    candidate = deepcopy(payload)
    candidate["security_clearance_claimed"] = True
    candidate["secret_clearance_claimed"] = True
    candidate["customer_readiness_claimed"] = True
    candidate["legal_clearance_claimed"] = True
    candidate["deployment_allowed"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "test_evidence_root_value_invalid" for finding in findings)


def test_witness_rejects_surface_state_promotion() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "test-evidence witness")
    candidate = deepcopy(payload)
    candidate["test_evidence_surfaces"][0]["state"] = "Ready"

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "test_evidence_surface_inventory_invalid" for finding in findings)
    assert any(finding.rule_id == "test_evidence_surface_state_invalid" for finding in findings)


def test_witness_rejects_private_test_or_deployment_values() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "test-evidence witness")
    candidate = deepcopy(payload)
    candidate["test_evidence_surfaces"][0]["public_safe_note"] = (
        "pytest_status=passed customer_id=abc endpoint_url=value"
    )

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "test_evidence_forbidden_private_value_pattern" for finding in findings)


def test_witness_rejects_broad_test_promotion_phrase() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "test-evidence witness")
    candidate = deepcopy(payload)
    candidate["next_action"] = "full test suite passed and release is ready"

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "test_evidence_forbidden_promotion_phrase" for finding in findings)


def test_receipt_routing_rejects_route_state_promotion() -> None:
    payload = load_json_object(DEFAULT_ROUTING_PATH, "test receipt routing")
    candidate = deepcopy(payload)
    candidate["receipt_routes"][0]["state"] = "Ready"

    findings = validate_receipt_routing_packet(candidate)

    assert findings
    assert any(finding.rule_id == "test_receipt_route_inventory_invalid" for finding in findings)
    assert any(finding.rule_id == "test_receipt_route_state_invalid" for finding in findings)


def test_receipt_routing_rejects_private_receipt_ref() -> None:
    payload = load_json_object(DEFAULT_ROUTING_PATH, "test receipt routing")
    candidate = deepcopy(payload)
    candidate["receipt_routes"][0]["receipt_ref"] = "C:/Users/example/private-receipt.json"

    findings = validate_receipt_routing_packet(candidate)

    assert findings
    assert any(finding.rule_id == "test_receipt_route_inventory_invalid" for finding in findings)
    assert any(finding.rule_id == "test_receipt_route_receipt_ref_invalid" for finding in findings)
    assert any(finding.rule_id == "test_evidence_forbidden_private_value_pattern" for finding in findings)


def test_receipt_routing_rejects_unowned_verification_ref() -> None:
    payload = load_json_object(DEFAULT_ROUTING_PATH, "test receipt routing")
    candidate = deepcopy(payload)
    candidate["receipt_routes"][0]["verification_ref"] = "../outside-validator.py"

    findings = validate_receipt_routing_packet(candidate)

    assert findings
    assert any(finding.rule_id == "test_receipt_route_inventory_invalid" for finding in findings)
    assert any(finding.rule_id == "test_receipt_route_verification_ref_invalid" for finding in findings)


def test_receipt_routing_rejects_release_promotion_phrase() -> None:
    payload = load_json_object(DEFAULT_ROUTING_PATH, "test receipt routing")
    candidate = deepcopy(payload)
    candidate["next_action"] = "full test suite passed and release is ready"

    findings = validate_receipt_routing_packet(candidate)

    assert findings
    assert any(finding.rule_id == "test_receipt_routing_next_action_invalid" for finding in findings)
    assert any(finding.rule_id == "test_evidence_forbidden_promotion_phrase" for finding in findings)


def test_gap_warning_register_rejects_entry_state_promotion() -> None:
    payload = load_json_object(DEFAULT_GAP_WARNING_PATH, "test gap warning register")
    candidate = deepcopy(payload)
    candidate["gap_warning_entries"][0]["state"] = "Ready"

    findings = validate_gap_warning_packet(candidate)

    assert findings
    assert any(finding.rule_id == "test_gap_warning_entry_inventory_invalid" for finding in findings)
    assert any(finding.rule_id == "test_gap_warning_entry_state_invalid" for finding in findings)


def test_gap_warning_register_rejects_private_evidence_ref() -> None:
    payload = load_json_object(DEFAULT_GAP_WARNING_PATH, "test gap warning register")
    candidate = deepcopy(payload)
    candidate["gap_warning_entries"][0]["evidence_ref"] = "C:/Users/example/private-gap.json"

    findings = validate_gap_warning_packet(candidate)

    assert findings
    assert any(finding.rule_id == "test_gap_warning_entry_inventory_invalid" for finding in findings)
    assert any(finding.rule_id == "test_gap_warning_entry_evidence_ref_invalid" for finding in findings)
    assert any(finding.rule_id == "test_evidence_forbidden_private_value_pattern" for finding in findings)


def test_gap_warning_register_rejects_duplicate_entries() -> None:
    payload = load_json_object(DEFAULT_GAP_WARNING_PATH, "test gap warning register")
    candidate = deepcopy(payload)
    candidate["gap_warning_entries"][1]["entry_id"] = candidate["gap_warning_entries"][0]["entry_id"]

    findings = validate_gap_warning_packet(candidate)

    assert findings
    assert any(finding.rule_id == "test_gap_warning_entry_inventory_invalid" for finding in findings)
    assert any(finding.rule_id == "test_gap_warning_entry_duplicate" for finding in findings)


def test_gap_warning_register_rejects_coverage_promotion_phrase() -> None:
    payload = load_json_object(DEFAULT_GAP_WARNING_PATH, "test gap warning register")
    candidate = deepcopy(payload)
    candidate["next_action"] = "coverage is complete and release is ready"

    findings = validate_gap_warning_packet(candidate)

    assert findings
    assert any(finding.rule_id == "test_gap_warning_next_action_invalid" for finding in findings)
    assert any(finding.rule_id == "test_evidence_forbidden_promotion_phrase" for finding in findings)


def test_validation_receipt_application_rejects_exact_result_and_freshness_claims() -> None:
    payload = load_json_object(DEFAULT_VALIDATION_RECEIPT_PATH, "validation receipt current packet")
    candidate = deepcopy(payload)
    candidate["receipt_summary_recorded"] = True
    candidate["check_count_recorded"] = True
    candidate["failed_check_names_recorded"] = True
    candidate["generated_at_recorded"] = True
    candidate["freshness_claimed"] = True

    findings = validate_validation_receipt_application(candidate)

    assert findings
    assert any(finding.rule_id == "validation_receipt_root_value_invalid" for finding in findings)


def test_validation_receipt_application_rejects_validation_and_git_promotion() -> None:
    payload = load_json_object(DEFAULT_VALIDATION_RECEIPT_PATH, "validation receipt current packet")
    candidate = deepcopy(payload)
    candidate["full_test_pass_claimed"] = True
    candidate["release_readiness_claimed"] = True
    candidate["terminal_closure_claimed"] = True
    candidate["staging_allowed"] = True
    candidate["commit_allowed"] = True
    candidate["push_allowed"] = True
    candidate["pull_request_allowed"] = True

    findings = validate_validation_receipt_application(candidate)

    assert findings
    assert any(finding.rule_id == "validation_receipt_root_value_invalid" for finding in findings)


def test_validation_receipt_application_rejects_category_and_item_state_drift() -> None:
    payload = load_json_object(DEFAULT_VALIDATION_RECEIPT_PATH, "validation receipt current packet")
    candidate = deepcopy(payload)
    candidate["application_categories"][0] = "live_receipt_summary"
    candidate["validation_items"][0]["state"] = "Ready"

    findings = validate_validation_receipt_application(candidate)

    assert findings
    assert any(finding.rule_id == "validation_receipt_categories_invalid" for finding in findings)
    assert any(finding.rule_id == "validation_receipt_item_state_invalid" for finding in findings)


def test_validation_receipt_application_rejects_private_path_and_promotion_phrase() -> None:
    payload = load_json_object(DEFAULT_VALIDATION_RECEIPT_PATH, "validation receipt current packet")
    candidate = deepcopy(payload)
    candidate["validation_items"][0]["application_note"] = (
        "C:/Users/example/private-receipt.json full test suite passed and release is ready"
    )

    findings = validate_validation_receipt_application(candidate)

    assert findings
    assert any(finding.rule_id == "test_evidence_forbidden_private_value_pattern" for finding in findings)
    assert any(finding.rule_id == "test_evidence_forbidden_promotion_phrase" for finding in findings)
