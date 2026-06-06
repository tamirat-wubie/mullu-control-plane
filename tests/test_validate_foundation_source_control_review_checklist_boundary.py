"""Tests for the Foundation Mode source-control review checklist boundary.

Purpose: prove source-control review checklist preparation stays local and does
not authorize checklist completion, scope closure, staging, commit, push, pull
request, release, publication, deployment, customer access, legal clearance,
company formation, patent action, money movement, or secret publication.
Governance scope: Foundation Mode, checklist item inventory, private-value
exclusion, source-control effect blocking, and external-effect blocking.
Dependencies: scripts.validate_foundation_source_control_review_checklist_boundary.
Invariants: checklist items remain AwaitingEvidence and reject effect promotion
or private-value drift.
"""

from __future__ import annotations

from copy import deepcopy
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validate_foundation_source_control_review_checklist_boundary import (  # noqa: E402
    DEFAULT_APPLICATION_PATH,
    DEFAULT_DIRTY_WORKTREE_APPLICATION_PATH,
    DEFAULT_EXTERNAL_ACTION_APPLICATION_PATH,
    DEFAULT_GIT_EFFECT_APPLICATION_PATH,
    DEFAULT_LINE_ENDING_APPLICATION_PATH,
    DEFAULT_NEXT_ACTION_WITNESS_PATH,
    DEFAULT_PACKET_PATH,
    DEFAULT_RUNTIME_SAFETY_APPLICATION_PATH,
    DEFAULT_SECRETS_APPLICATION_PATH,
    DEFAULT_UNRELATED_WORK_APPLICATION_PATH,
    DEFAULT_UNTRACKED_ARTIFACT_APPLICATION_PATH,
    DEFAULT_VALIDATION_RECEIPT_APPLICATION_PATH,
    EXPECTED_APPLICATION_ID,
    EXPECTED_APPLICATION_REVIEW_ITEMS,
    EXPECTED_LINE_ENDING_APPLICATION_ID,
    EXPECTED_LINE_ENDING_CATEGORIES,
    EXPECTED_LINE_ENDING_TRIAGE_ITEMS,
    EXPECTED_NEXT_ACTION_SURFACES,
    EXPECTED_NEXT_ACTION_WITNESS_ID,
    EXPECTED_OBSERVED_CHANGE_CATEGORIES,
    EXPECTED_CHECKLIST_ITEMS,
    EXPECTED_CHECKLIST_NOTE_FRAGMENTS,
    EXPECTED_DIRTY_WORKTREE_APPLICATION_ID,
    EXPECTED_DIRTY_WORKTREE_CATEGORIES,
    EXPECTED_DIRTY_WORKTREE_ITEMS,
    EXPECTED_EXTERNAL_ACTION_APPLICATION_ID,
    EXPECTED_EXTERNAL_ACTION_CATEGORIES,
    EXPECTED_EXTERNAL_ACTION_ITEMS,
    EXPECTED_GIT_EFFECT_APPLICATION_ID,
    EXPECTED_GIT_EFFECT_CATEGORIES,
    EXPECTED_GIT_EFFECT_ITEMS,
    EXPECTED_RUNTIME_SAFETY_APPLICATION_ID,
    EXPECTED_RUNTIME_SAFETY_CATEGORIES,
    EXPECTED_RUNTIME_SAFETY_ITEMS,
    EXPECTED_SECRETS_APPLICATION_ID,
    EXPECTED_SECRETS_CATEGORIES,
    EXPECTED_SECRETS_ITEMS,
    EXPECTED_UNRELATED_WORK_APPLICATION_ID,
    EXPECTED_UNRELATED_WORK_CATEGORIES,
    EXPECTED_UNRELATED_WORK_ITEMS,
    EXPECTED_UNTRACKED_ARTIFACT_APPLICATION_ID,
    EXPECTED_UNTRACKED_ARTIFACT_CATEGORIES,
    EXPECTED_UNTRACKED_ARTIFACT_ITEMS,
    EXPECTED_VALIDATION_RECEIPT_APPLICATION_ID,
    EXPECTED_VALIDATION_RECEIPT_CATEGORIES,
    EXPECTED_VALIDATION_RECEIPT_ITEMS,
    EXPECTED_WITNESS_ID,
    load_json_object,
    validate_application,
    validate_dirty_worktree_application,
    validate_external_action_application,
    validate_foundation_source_control_review_checklist_boundary,
    validate_git_effect_application,
    validate_line_ending_application,
    validate_next_action_witness,
    validate_runtime_safety_application,
    validate_secrets_application,
    validate_packet,
    validate_unrelated_work_application,
    validate_untracked_artifact_application,
    validate_validation_receipt_application,
)


def test_foundation_source_control_review_checklist_boundary_artifacts_pass() -> None:
    assert validate_foundation_source_control_review_checklist_boundary() == []


def test_checklist_witness_has_expected_identity_and_blockers() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "source-control review checklist witness")

    assert payload["witness_id"] == EXPECTED_WITNESS_ID
    assert tuple(
        (item["checklist_id"], item["checklist_type"], item["state"])
        for item in payload["checklist_items"]
    ) == EXPECTED_CHECKLIST_ITEMS
    assert payload["checklist_complete_claimed"] is False
    assert payload["review_scope_closed_claimed"] is False
    assert payload["validation_complete_claimed"] is False
    assert payload["secret_clearance_claimed"] is False
    assert payload["staging_allowed"] is False
    assert payload["commit_allowed"] is False
    assert payload["push_allowed"] is False
    assert payload["pull_request_allowed"] is False
    assert payload["deployment_allowed"] is False
    assert payload["customer_access_allowed"] is False
    assert payload["legal_clearance_claimed"] is False
    assert payload["company_formation_claimed"] is False
    assert payload["patent_action_allowed"] is False
    assert payload["money_action_allowed"] is False
    assert payload["secret_publication_allowed"] is False


def test_checklist_fragments_are_present() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "source-control review checklist witness")
    items = {item["checklist_id"]: item for item in payload["checklist_items"]}

    assert EXPECTED_CHECKLIST_NOTE_FRAGMENTS
    for checklist_id, fragments in EXPECTED_CHECKLIST_NOTE_FRAGMENTS.items():
        assert checklist_id in items
        assert fragments
        assert all(fragment in items[checklist_id]["public_safe_question"] for fragment in fragments)


def test_current_packet_application_has_expected_identity_and_categories() -> None:
    payload = load_json_object(DEFAULT_APPLICATION_PATH, "source-control review checklist current-packet application")

    assert payload["application_id"] == EXPECTED_APPLICATION_ID
    assert tuple(payload["observed_change_categories"]) == EXPECTED_OBSERVED_CHANGE_CATEGORIES
    assert tuple((item["checklist_id"], item["state"]) for item in payload["review_items"]) == EXPECTED_APPLICATION_REVIEW_ITEMS
    assert payload["review_context"]["changed_file_list_recorded"] is False
    assert payload["review_context"]["private_values_recorded"] is False
    assert payload["review_context"]["saved_preflight_receipt_available"] is True
    assert payload["review_context"]["receipt_is_terminal_closure_claimed"] is False
    assert payload["checklist_complete_claimed"] is False
    assert payload["review_scope_closed_claimed"] is False
    assert payload["validation_complete_claimed"] is False
    assert payload["secret_clearance_claimed"] is False
    assert payload["staging_allowed"] is False
    assert payload["commit_allowed"] is False
    assert payload["push_allowed"] is False
    assert payload["pull_request_allowed"] is False
    assert payload["deployment_allowed"] is False
    assert payload["customer_access_allowed"] is False
    assert payload["legal_clearance_claimed"] is False
    assert payload["company_formation_claimed"] is False
    assert payload["patent_action_allowed"] is False
    assert payload["money_action_allowed"] is False
    assert payload["secret_publication_allowed"] is False


def test_validation_receipt_application_has_expected_identity_and_blockers() -> None:
    payload = load_json_object(
        DEFAULT_VALIDATION_RECEIPT_APPLICATION_PATH,
        "source-control validation-receipt current-packet application",
    )

    assert payload["application_id"] == EXPECTED_VALIDATION_RECEIPT_APPLICATION_ID
    assert tuple(payload["application_categories"]) == EXPECTED_VALIDATION_RECEIPT_CATEGORIES
    assert tuple((item["validation_id"], item["state"]) for item in payload["validation_items"]) == EXPECTED_VALIDATION_RECEIPT_ITEMS
    assert payload["saved_receipt_ref"] == ".tmp/workspace-governance-preflight-receipt.json"
    assert payload["validator_ref"] == "scripts/validate_workspace_governance_preflight_receipt.py"
    assert payload["receipt_presence_observed"] is True
    assert payload["receipt_summary_recorded"] is False
    assert payload["check_count_recorded"] is False
    assert payload["failed_check_names_recorded"] is False
    assert payload["check_stdout_recorded"] is False
    assert payload["receipt_content_recorded"] is False
    assert payload["generated_at_recorded"] is False
    assert payload["freshness_claimed"] is False
    assert payload["private_path_recorded"] is False
    assert payload["full_test_pass_claimed"] is False
    assert payload["complete_coverage_claimed"] is False
    assert payload["ci_parity_claimed"] is False
    assert payload["release_readiness_claimed"] is False
    assert payload["deployment_readiness_claimed"] is False
    assert payload["security_clearance_claimed"] is False
    assert payload["secret_clearance_claimed"] is False
    assert payload["customer_readiness_claimed"] is False
    assert payload["legal_clearance_claimed"] is False
    assert payload["performance_readiness_claimed"] is False
    assert payload["flake_free_guarantee_claimed"] is False
    assert payload["terminal_closure_claimed"] is False
    assert payload["staging_allowed"] is False
    assert payload["commit_allowed"] is False
    assert payload["push_allowed"] is False
    assert payload["pull_request_allowed"] is False
    assert payload["external_publication_allowed"] is False
    assert payload["deployment_allowed"] is False


def test_next_action_witness_has_expected_identity_and_blockers() -> None:
    payload = load_json_object(
        DEFAULT_NEXT_ACTION_WITNESS_PATH,
        "source-control next-action witness",
    )

    assert payload["witness_id"] == EXPECTED_NEXT_ACTION_WITNESS_ID
    assert tuple(
        (surface["surface_id"], surface["surface_type"], surface["state"])
        for surface in payload["next_action_surfaces"]
    ) == EXPECTED_NEXT_ACTION_SURFACES
    assert payload["broad_continuation_execution_allowed"] is False
    assert payload["external_action_allowed"] is False
    assert payload["deployment_allowed"] is False
    assert payload["external_publication_allowed"] is False
    assert payload["spending_allowed"] is False
    assert payload["customer_action_allowed"] is False
    assert payload["legal_business_action_allowed"] is False
    assert payload["claim_promotion_allowed"] is False
    assert payload["secret_use_allowed"] is False
    assert payload["credential_use_allowed"] is False
    assert payload["service_activation_allowed"] is False
    assert payload["source_control_publication_allowed"] is False
    assert payload["roadmap_commitment_claimed"] is False
    assert payload["deadline_promise_claimed"] is False


def test_git_effect_application_has_expected_identity_and_blockers() -> None:
    payload = load_json_object(
        DEFAULT_GIT_EFFECT_APPLICATION_PATH,
        "source-control Git-effect stop-rule application",
    )

    assert payload["application_id"] == EXPECTED_GIT_EFFECT_APPLICATION_ID
    assert tuple(payload["effect_categories"]) == EXPECTED_GIT_EFFECT_CATEGORIES
    assert tuple((item["review_id"], item["state"]) for item in payload["review_items"]) == EXPECTED_GIT_EFFECT_ITEMS
    assert payload["approval_claimed"] is False
    assert payload["staging_allowed"] is False
    assert payload["commit_allowed"] is False
    assert payload["push_allowed"] is False
    assert payload["pull_request_allowed"] is False
    assert payload["source_control_publication_allowed"] is False
    assert payload["branch_switch_allowed"] is False
    assert payload["tag_allowed"] is False
    assert payload["release_allowed"] is False
    assert payload["reset_allowed"] is False
    assert payload["checkout_allowed"] is False
    assert payload["revert_allowed"] is False
    assert payload["git_config_change_allowed"] is False
    assert payload["status_output_recorded"] is False
    assert payload["changed_file_list_recorded"] is False
    assert payload["exact_diff_recorded"] is False
    assert payload["private_paths_recorded"] is False
    assert payload["branch_ref_recorded"] is False
    assert payload["commit_ref_recorded"] is False
    assert payload["pull_request_ref_recorded"] is False


def test_external_action_application_has_expected_identity_and_blockers() -> None:
    payload = load_json_object(
        DEFAULT_EXTERNAL_ACTION_APPLICATION_PATH,
        "source-control external-action stop-rule application",
    )

    assert payload["application_id"] == EXPECTED_EXTERNAL_ACTION_APPLICATION_ID
    assert tuple(payload["stop_rule_categories"]) == EXPECTED_EXTERNAL_ACTION_CATEGORIES
    assert tuple((item["review_id"], item["state"]) for item in payload["review_items"]) == EXPECTED_EXTERNAL_ACTION_ITEMS
    assert payload["external_action_allowed"] is False
    assert payload["external_publication_allowed"] is False
    assert payload["deployment_allowed"] is False
    assert payload["deployment_readiness_claimed"] is False
    assert payload["customer_access_allowed"] is False
    assert payload["customer_action_allowed"] is False
    assert payload["customer_identifier_recorded"] is False
    assert payload["legal_clearance_claimed"] is False
    assert payload["legal_action_allowed"] is False
    assert payload["legal_conclusion_recorded"] is False
    assert payload["company_formation_claimed"] is False
    assert payload["company_action_allowed"] is False
    assert payload["company_filing_recorded"] is False
    assert payload["patent_action_allowed"] is False
    assert payload["patent_filing_recorded"] is False
    assert payload["money_action_allowed"] is False
    assert payload["payment_detail_recorded"] is False
    assert payload["secret_publication_allowed"] is False
    assert payload["secret_value_recorded"] is False
    assert payload["external_account_activation_allowed"] is False
    assert payload["service_activation_allowed"] is False
    assert payload["provider_binding_allowed"] is False
    assert payload["provider_id_recorded"] is False
    assert payload["endpoint_target_recorded"] is False
    assert payload["personal_data_collection_allowed"] is False


def test_dirty_worktree_application_has_expected_identity_and_blockers() -> None:
    payload = load_json_object(
        DEFAULT_DIRTY_WORKTREE_APPLICATION_PATH,
        "source-control dirty-worktree snapshot application",
    )

    assert payload["application_id"] == EXPECTED_DIRTY_WORKTREE_APPLICATION_ID
    assert tuple(payload["snapshot_categories"]) == EXPECTED_DIRTY_WORKTREE_CATEGORIES
    assert tuple((item["review_id"], item["state"]) for item in payload["review_items"]) == EXPECTED_DIRTY_WORKTREE_ITEMS
    assert payload["dirty_state_observed"] is True
    assert payload["clean_worktree_claimed"] is False
    assert payload["status_output_recorded"] is False
    assert payload["changed_file_count_recorded"] is False
    assert payload["changed_file_list_recorded"] is False
    assert payload["exact_diff_recorded"] is False
    assert payload["private_paths_recorded"] is False
    assert payload["branch_ref_recorded"] is False
    assert payload["commit_ref_recorded"] is False
    assert payload["pull_request_ref_recorded"] is False
    assert payload["ownership_assigned"] is False
    assert payload["staging_allowed"] is False
    assert payload["commit_allowed"] is False
    assert payload["push_allowed"] is False
    assert payload["pull_request_allowed"] is False
    assert payload["deployment_allowed"] is False
    assert payload["customer_access_allowed"] is False
    assert payload["legal_clearance_claimed"] is False
    assert payload["company_formation_claimed"] is False
    assert payload["patent_action_allowed"] is False
    assert payload["money_action_allowed"] is False
    assert payload["secret_publication_allowed"] is False


def test_line_ending_warning_application_has_expected_identity_and_blockers() -> None:
    payload = load_json_object(DEFAULT_LINE_ENDING_APPLICATION_PATH, "source-control line-ending warning application")

    assert payload["application_id"] == EXPECTED_LINE_ENDING_APPLICATION_ID
    assert tuple(payload["warning_categories"]) == EXPECTED_LINE_ENDING_CATEGORIES
    assert tuple((item["triage_id"], item["state"]) for item in payload["triage_items"]) == EXPECTED_LINE_ENDING_TRIAGE_ITEMS
    assert payload["warning_presence_observed"] is True
    assert payload["warning_count_recorded"] is False
    assert payload["warning_text_recorded"] is False
    assert payload["warning_hidden_claimed"] is False
    assert payload["warning_resolution_claimed"] is False
    assert payload["changed_file_list_recorded"] is False
    assert payload["private_paths_recorded"] is False
    assert payload["line_ending_normalization_allowed"] is False
    assert payload["git_config_change_allowed"] is False
    assert payload["file_rewrite_allowed"] is False
    assert payload["staging_allowed"] is False
    assert payload["commit_allowed"] is False
    assert payload["push_allowed"] is False
    assert payload["pull_request_allowed"] is False
    assert payload["deployment_allowed"] is False
    assert payload["customer_access_allowed"] is False
    assert payload["legal_clearance_claimed"] is False
    assert payload["company_formation_claimed"] is False
    assert payload["patent_action_allowed"] is False
    assert payload["money_action_allowed"] is False
    assert payload["secret_publication_allowed"] is False


def test_untracked_artifact_application_has_expected_identity_and_blockers() -> None:
    payload = load_json_object(
        DEFAULT_UNTRACKED_ARTIFACT_APPLICATION_PATH,
        "source-control untracked artifact application",
    )

    assert payload["application_id"] == EXPECTED_UNTRACKED_ARTIFACT_APPLICATION_ID
    assert tuple(payload["artifact_categories"]) == EXPECTED_UNTRACKED_ARTIFACT_CATEGORIES
    assert tuple((item["review_id"], item["state"]) for item in payload["review_items"]) == EXPECTED_UNTRACKED_ARTIFACT_ITEMS
    assert payload["artifact_presence_observed"] is True
    assert payload["artifact_count_recorded"] is False
    assert payload["artifact_paths_recorded"] is False
    assert payload["changed_file_list_recorded"] is False
    assert payload["private_paths_recorded"] is False
    assert payload["artifact_contents_recorded"] is False
    assert payload["artifact_ownership_closed_claimed"] is False
    assert payload["file_list_publication_allowed"] is False
    assert payload["staging_allowed"] is False
    assert payload["commit_allowed"] is False
    assert payload["push_allowed"] is False
    assert payload["pull_request_allowed"] is False
    assert payload["deployment_allowed"] is False
    assert payload["customer_access_allowed"] is False
    assert payload["legal_clearance_claimed"] is False
    assert payload["company_formation_claimed"] is False
    assert payload["patent_action_allowed"] is False
    assert payload["money_action_allowed"] is False
    assert payload["secret_publication_allowed"] is False


def test_unrelated_work_application_has_expected_identity_and_blockers() -> None:
    payload = load_json_object(
        DEFAULT_UNRELATED_WORK_APPLICATION_PATH,
        "source-control unrelated work preservation application",
    )

    assert payload["application_id"] == EXPECTED_UNRELATED_WORK_APPLICATION_ID
    assert tuple(payload["unrelated_work_categories"]) == EXPECTED_UNRELATED_WORK_CATEGORIES
    assert tuple((item["review_id"], item["state"]) for item in payload["review_items"]) == EXPECTED_UNRELATED_WORK_ITEMS
    assert payload["preservation_required"] is True
    assert payload["unrelated_work_closure_claimed"] is False
    assert payload["prior_work_closure_claimed"] is False
    assert payload["ownership_assigned"] is False
    assert payload["changed_file_list_recorded"] is False
    assert payload["exact_diff_recorded"] is False
    assert payload["private_paths_recorded"] is False
    assert payload["diff_scope_closed_claimed"] is False
    assert payload["user_change_overwrite_allowed"] is False
    assert payload["reset_allowed"] is False
    assert payload["checkout_allowed"] is False
    assert payload["delete_allowed"] is False
    assert payload["move_allowed"] is False
    assert payload["revert_allowed"] is False
    assert payload["staging_allowed"] is False
    assert payload["commit_allowed"] is False
    assert payload["push_allowed"] is False
    assert payload["pull_request_allowed"] is False
    assert payload["deployment_allowed"] is False
    assert payload["customer_access_allowed"] is False
    assert payload["legal_clearance_claimed"] is False
    assert payload["company_formation_claimed"] is False
    assert payload["patent_action_allowed"] is False
    assert payload["money_action_allowed"] is False
    assert payload["secret_publication_allowed"] is False


def test_secrets_application_has_expected_identity_and_blockers() -> None:
    payload = load_json_object(
        DEFAULT_SECRETS_APPLICATION_PATH,
        "source-control secrets/private-value screening application",
    )

    assert payload["application_id"] == EXPECTED_SECRETS_APPLICATION_ID
    assert tuple(payload["observed_screening_categories"]) == EXPECTED_SECRETS_CATEGORIES
    assert tuple((item["surface_id"], item["state"]) for item in payload["screening_items"]) == EXPECTED_SECRETS_ITEMS
    assert payload["screening_context"]["changed_file_list_recorded"] is False
    assert payload["screening_context"]["private_values_recorded"] is False
    assert payload["screening_context"]["secret_value_recorded"] is False
    assert payload["screening_context"]["credential_value_recorded"] is False
    assert payload["screening_context"]["assigned_environment_value_recorded"] is False
    assert payload["screening_context"]["private_path_recorded"] is False
    assert payload["screening_context"]["account_identifier_recorded"] is False
    assert payload["screening_context"]["provider_binding_recorded"] is False
    assert payload["screening_context"]["saved_preflight_receipt_available"] is True
    assert payload["screening_context"]["receipt_is_terminal_closure_claimed"] is False
    assert payload["real_secret_storage_allowed"] is False
    assert payload["credential_activation_allowed"] is False
    assert payload["provider_account_binding_allowed"] is False
    assert payload["api_key_creation_allowed"] is False
    assert payload["oauth_app_creation_allowed"] is False
    assert payload["service_account_creation_allowed"] is False
    assert payload["env_file_commit_allowed"] is False
    assert payload["private_key_storage_allowed"] is False
    assert payload["secret_rotation_claimed"] is False
    assert payload["secret_scan_pass_claimed"] is False
    assert payload["external_call_allowed"] is False
    assert payload["staging_allowed"] is False
    assert payload["commit_allowed"] is False
    assert payload["push_allowed"] is False
    assert payload["pull_request_allowed"] is False
    assert payload["external_publication_allowed"] is False
    assert payload["deployment_allowed"] is False
    assert payload["customer_access_allowed"] is False
    assert payload["legal_clearance_claimed"] is False
    assert payload["company_formation_claimed"] is False
    assert payload["patent_action_allowed"] is False
    assert payload["money_action_allowed"] is False


def test_runtime_safety_application_has_expected_identity_and_blockers() -> None:
    payload = load_json_object(
        DEFAULT_RUNTIME_SAFETY_APPLICATION_PATH,
        "source-control runtime-safety packet application",
    )

    assert payload["application_id"] == EXPECTED_RUNTIME_SAFETY_APPLICATION_ID
    assert tuple(payload["packet_categories"]) == EXPECTED_RUNTIME_SAFETY_CATEGORIES
    assert tuple((item["review_id"], item["state"]) for item in payload["review_items"]) == EXPECTED_RUNTIME_SAFETY_ITEMS
    assert payload["runtime_safety_family_observed"] is True
    assert payload["runtime_completion_claimed"] is False
    assert payload["runtime_readiness_claimed"] is False
    assert payload["adapter_authority_claimed"] is False
    assert payload["provider_binding_claimed"] is False
    assert payload["connector_use_claimed"] is False
    assert payload["endpoint_target_recorded"] is False
    assert payload["secret_use_claimed"] is False
    assert payload["secret_value_recorded"] is False
    assert payload["acceptance_test_harness_complete_claimed"] is False
    assert payload["full_coverage_claimed"] is False
    assert payload["review_scope_closed_claimed"] is False
    assert payload["changed_file_list_recorded"] is False
    assert payload["private_values_recorded"] is False
    assert payload["staging_allowed"] is False
    assert payload["commit_allowed"] is False
    assert payload["push_allowed"] is False
    assert payload["pull_request_allowed"] is False
    assert payload["deployment_allowed"] is False
    assert payload["customer_access_allowed"] is False
    assert payload["legal_clearance_claimed"] is False
    assert payload["company_formation_claimed"] is False
    assert payload["patent_action_allowed"] is False
    assert payload["money_action_allowed"] is False
    assert payload["secret_publication_allowed"] is False


def test_witness_rejects_missing_checklist_fragment() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "source-control review checklist witness")
    candidate = deepcopy(payload)
    candidate["checklist_items"][0]["public_safe_question"] = (
        "Draft dirty worktree questions without claiming checklist completion."
    )

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "source_control_review_checklist_item_question_fragment_missing" for finding in findings)


def test_witness_rejects_completion_scope_and_validation_promotion() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "source-control review checklist witness")
    candidate = deepcopy(payload)
    candidate["checklist_complete_claimed"] = True
    candidate["review_scope_closed_claimed"] = True
    candidate["validation_complete_claimed"] = True
    candidate["secret_clearance_claimed"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "source_control_review_checklist_root_value_invalid" for finding in findings)


def test_witness_rejects_git_and_external_effect_promotion() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "source-control review checklist witness")
    candidate = deepcopy(payload)
    candidate["staging_allowed"] = True
    candidate["commit_allowed"] = True
    candidate["push_allowed"] = True
    candidate["pull_request_allowed"] = True
    candidate["deployment_allowed"] = True
    candidate["customer_access_allowed"] = True
    candidate["patent_action_allowed"] = True
    candidate["money_action_allowed"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "source_control_review_checklist_root_value_invalid" for finding in findings)


def test_witness_rejects_item_state_promotion() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "source-control review checklist witness")
    candidate = deepcopy(payload)
    candidate["checklist_items"][0]["state"] = "Ready"

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "source_control_review_checklist_inventory_invalid" for finding in findings)
    assert any(finding.rule_id == "source_control_review_checklist_item_state_invalid" for finding in findings)


def test_witness_rejects_private_source_control_or_secret_value() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "source-control review checklist witness")
    candidate = deepcopy(payload)
    candidate["checklist_items"][0]["public_safe_question"] = (
        "commit_status=approved customer_id=abc secret=value payment_status=approved"
    )

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "source_control_review_checklist_forbidden_private_value_pattern" for finding in findings)


def test_witness_rejects_effect_promotion_phrase() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "source-control review checklist witness")
    candidate = deepcopy(payload)
    candidate["next_action"] = "checklist is complete and commit is approved"

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "source_control_review_checklist_forbidden_promotion_phrase" for finding in findings)


def test_application_rejects_category_drift() -> None:
    payload = load_json_object(DEFAULT_APPLICATION_PATH, "source-control review checklist current-packet application")
    candidate = deepcopy(payload)
    candidate["observed_change_categories"] = ["source_control_review_checklist_boundary"]

    findings = validate_application(candidate)

    assert findings
    assert any(
        finding.rule_id == "source_control_review_checklist_application_categories_invalid"
        for finding in findings
    )


def test_application_rejects_item_state_promotion() -> None:
    payload = load_json_object(DEFAULT_APPLICATION_PATH, "source-control review checklist current-packet application")
    candidate = deepcopy(payload)
    candidate["review_items"][0]["state"] = "Ready"

    findings = validate_application(candidate)

    assert findings
    assert any(
        finding.rule_id == "source_control_review_checklist_application_inventory_invalid"
        for finding in findings
    )
    assert any(
        finding.rule_id == "source_control_review_checklist_application_item_state_invalid"
        for finding in findings
    )


def test_application_rejects_private_value_and_effect_promotion() -> None:
    payload = load_json_object(DEFAULT_APPLICATION_PATH, "source-control review checklist current-packet application")
    candidate = deepcopy(payload)
    candidate["review_items"][0]["application_note"] = (
        "commit_ref=value customer_id=abc secret=value deployment_status=approved"
    )
    candidate["next_action"] = "commit is approved"

    findings = validate_application(candidate)

    assert findings
    assert any(
        finding.rule_id == "source_control_review_checklist_forbidden_private_value_pattern"
        for finding in findings
    )
    assert any(
        finding.rule_id == "source_control_review_checklist_forbidden_promotion_phrase"
        for finding in findings
    )


def test_validation_receipt_application_rejects_exact_result_and_freshness_claims() -> None:
    payload = load_json_object(
        DEFAULT_VALIDATION_RECEIPT_APPLICATION_PATH,
        "source-control validation-receipt current-packet application",
    )
    candidate = deepcopy(payload)
    candidate["receipt_summary_recorded"] = True
    candidate["check_count_recorded"] = True
    candidate["failed_check_names_recorded"] = True
    candidate["generated_at_recorded"] = True
    candidate["freshness_claimed"] = True

    findings = validate_validation_receipt_application(candidate)

    assert findings
    assert any(
        finding.rule_id == "source_control_review_checklist_validation_receipt_root_value_invalid"
        for finding in findings
    )


def test_validation_receipt_application_rejects_validation_and_git_promotion() -> None:
    payload = load_json_object(
        DEFAULT_VALIDATION_RECEIPT_APPLICATION_PATH,
        "source-control validation-receipt current-packet application",
    )
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
    assert any(
        finding.rule_id == "source_control_review_checklist_validation_receipt_root_value_invalid"
        for finding in findings
    )


def test_validation_receipt_application_rejects_category_and_item_state_drift() -> None:
    payload = load_json_object(
        DEFAULT_VALIDATION_RECEIPT_APPLICATION_PATH,
        "source-control validation-receipt current-packet application",
    )
    candidate = deepcopy(payload)
    candidate["application_categories"] = ["saved_preflight_receipt_presence_category"]
    candidate["validation_items"][0]["state"] = "Ready"

    findings = validate_validation_receipt_application(candidate)

    assert findings
    assert any(
        finding.rule_id == "source_control_review_checklist_validation_receipt_categories_invalid"
        for finding in findings
    )
    assert any(
        finding.rule_id == "source_control_review_checklist_validation_receipt_inventory_invalid"
        for finding in findings
    )
    assert any(
        finding.rule_id == "source_control_review_checklist_validation_receipt_item_state_invalid"
        for finding in findings
    )


def test_validation_receipt_application_rejects_private_value_and_effect_promotion() -> None:
    payload = load_json_object(
        DEFAULT_VALIDATION_RECEIPT_APPLICATION_PATH,
        "source-control validation-receipt current-packet application",
    )
    candidate = deepcopy(payload)
    candidate["validation_items"][0]["application_note"] = (
        "C:/Users/example/private-receipt.json full test suite passed and release is ready"
    )

    findings = validate_validation_receipt_application(candidate)

    assert findings
    assert any(
        finding.rule_id == "source_control_review_checklist_forbidden_private_value_pattern"
        for finding in findings
    )
    assert any(
        finding.rule_id == "source_control_review_checklist_forbidden_promotion_phrase"
        for finding in findings
    )


def test_next_action_witness_rejects_broad_continuation_and_external_effects() -> None:
    payload = load_json_object(
        DEFAULT_NEXT_ACTION_WITNESS_PATH,
        "source-control next-action witness",
    )
    candidate = deepcopy(payload)
    candidate["broad_continuation_execution_allowed"] = True
    candidate["external_action_allowed"] = True
    candidate["deployment_allowed"] = True
    candidate["spending_allowed"] = True
    candidate["source_control_publication_allowed"] = True

    findings = validate_next_action_witness(candidate)

    assert findings
    assert any(
        finding.rule_id == "source_control_review_checklist_next_action_root_value_invalid"
        for finding in findings
    )


def test_next_action_witness_rejects_surface_state_promotion() -> None:
    payload = load_json_object(
        DEFAULT_NEXT_ACTION_WITNESS_PATH,
        "source-control next-action witness",
    )
    candidate = deepcopy(payload)
    candidate["next_action_surfaces"][0]["state"] = "Ready"

    findings = validate_next_action_witness(candidate)

    assert findings
    assert any(
        finding.rule_id == "source_control_review_checklist_next_action_surface_inventory_invalid"
        for finding in findings
    )
    assert any(
        finding.rule_id == "source_control_review_checklist_next_action_surface_state_invalid"
        for finding in findings
    )


def test_next_action_witness_rejects_private_value_and_effect_promotion() -> None:
    payload = load_json_object(
        DEFAULT_NEXT_ACTION_WITNESS_PATH,
        "source-control next-action witness",
    )
    candidate = deepcopy(payload)
    candidate["next_action_surfaces"][0]["public_safe_note"] = "provider_id=private-account token=value"
    candidate["next_action"] = "continue is authorized and deadline is promised"

    findings = validate_next_action_witness(candidate)

    assert findings
    assert any(
        finding.rule_id == "source_control_review_checklist_forbidden_private_value_pattern"
        for finding in findings
    )
    assert any(
        finding.rule_id == "source_control_review_checklist_forbidden_promotion_phrase"
        for finding in findings
    )


def test_git_effect_application_rejects_approval_and_source_control_effects() -> None:
    payload = load_json_object(
        DEFAULT_GIT_EFFECT_APPLICATION_PATH,
        "source-control Git-effect stop-rule application",
    )
    candidate = deepcopy(payload)
    candidate["approval_claimed"] = True
    candidate["staging_allowed"] = True
    candidate["commit_allowed"] = True
    candidate["push_allowed"] = True
    candidate["pull_request_allowed"] = True
    candidate["source_control_publication_allowed"] = True
    candidate["branch_switch_allowed"] = True
    candidate["git_config_change_allowed"] = True

    findings = validate_git_effect_application(candidate)

    assert findings
    assert any(
        finding.rule_id == "source_control_review_checklist_git_effect_root_value_invalid"
        for finding in findings
    )


def test_git_effect_application_rejects_category_and_item_state_drift() -> None:
    payload = load_json_object(
        DEFAULT_GIT_EFFECT_APPLICATION_PATH,
        "source-control Git-effect stop-rule application",
    )
    candidate = deepcopy(payload)
    candidate["effect_categories"] = ["git_effect_stop_rule_category"]
    candidate["review_items"][0]["state"] = "Ready"

    findings = validate_git_effect_application(candidate)

    assert findings
    assert any(
        finding.rule_id == "source_control_review_checklist_git_effect_categories_invalid"
        for finding in findings
    )
    assert any(
        finding.rule_id == "source_control_review_checklist_git_effect_inventory_invalid"
        for finding in findings
    )
    assert any(
        finding.rule_id == "source_control_review_checklist_git_effect_item_state_invalid"
        for finding in findings
    )


def test_git_effect_application_rejects_private_value_and_effect_promotion() -> None:
    payload = load_json_object(
        DEFAULT_GIT_EFFECT_APPLICATION_PATH,
        "source-control Git-effect stop-rule application",
    )
    candidate = deepcopy(payload)
    candidate["review_items"][0]["application_note"] = "commit_ref=value branch_status=approved"
    candidate["next_action"] = "commit is approved"

    findings = validate_git_effect_application(candidate)

    assert findings
    assert any(
        finding.rule_id == "source_control_review_checklist_forbidden_private_value_pattern"
        for finding in findings
    )
    assert any(
        finding.rule_id == "source_control_review_checklist_forbidden_promotion_phrase"
        for finding in findings
    )


def test_external_action_application_rejects_external_effects_and_readiness() -> None:
    payload = load_json_object(
        DEFAULT_EXTERNAL_ACTION_APPLICATION_PATH,
        "source-control external-action stop-rule application",
    )
    candidate = deepcopy(payload)
    candidate["external_action_allowed"] = True
    candidate["external_publication_allowed"] = True
    candidate["deployment_allowed"] = True
    candidate["customer_action_allowed"] = True
    candidate["legal_action_allowed"] = True
    candidate["company_action_allowed"] = True
    candidate["patent_action_allowed"] = True
    candidate["money_action_allowed"] = True
    candidate["secret_publication_allowed"] = True

    findings = validate_external_action_application(candidate)

    assert findings
    assert any(
        finding.rule_id == "source_control_review_checklist_external_action_root_value_invalid"
        for finding in findings
    )


def test_external_action_application_rejects_category_and_item_state_drift() -> None:
    payload = load_json_object(
        DEFAULT_EXTERNAL_ACTION_APPLICATION_PATH,
        "source-control external-action stop-rule application",
    )
    candidate = deepcopy(payload)
    candidate["stop_rule_categories"] = ["external_action_stop_rule_category"]
    candidate["review_items"][0]["state"] = "Ready"

    findings = validate_external_action_application(candidate)

    assert findings
    assert any(
        finding.rule_id == "source_control_review_checklist_external_action_categories_invalid"
        for finding in findings
    )
    assert any(
        finding.rule_id == "source_control_review_checklist_external_action_inventory_invalid"
        for finding in findings
    )
    assert any(
        finding.rule_id == "source_control_review_checklist_external_action_item_state_invalid"
        for finding in findings
    )


def test_external_action_application_rejects_private_value_and_effect_promotion() -> None:
    payload = load_json_object(
        DEFAULT_EXTERNAL_ACTION_APPLICATION_PATH,
        "source-control external-action stop-rule application",
    )
    candidate = deepcopy(payload)
    candidate["review_items"][0]["application_note"] = "customer_id=value endpoint_url=value"
    candidate["next_action"] = "external action is approved and payment action is approved"

    findings = validate_external_action_application(candidate)

    assert findings
    assert any(
        finding.rule_id == "source_control_review_checklist_forbidden_private_value_pattern"
        for finding in findings
    )
    assert any(
        finding.rule_id == "source_control_review_checklist_forbidden_promotion_phrase"
        for finding in findings
    )


def test_dirty_worktree_application_rejects_clean_claim_and_snapshot_publication() -> None:
    payload = load_json_object(
        DEFAULT_DIRTY_WORKTREE_APPLICATION_PATH,
        "source-control dirty-worktree snapshot application",
    )
    candidate = deepcopy(payload)
    candidate["clean_worktree_claimed"] = True
    candidate["status_output_recorded"] = True
    candidate["changed_file_count_recorded"] = True
    candidate["changed_file_list_recorded"] = True
    candidate["exact_diff_recorded"] = True
    candidate["branch_ref_recorded"] = True
    candidate["commit_ref_recorded"] = True
    candidate["pull_request_ref_recorded"] = True
    candidate["ownership_assigned"] = True
    candidate["commit_allowed"] = True

    findings = validate_dirty_worktree_application(candidate)

    assert findings
    assert any(
        finding.rule_id == "source_control_review_checklist_dirty_worktree_root_value_invalid"
        for finding in findings
    )


def test_dirty_worktree_application_rejects_category_and_item_state_drift() -> None:
    payload = load_json_object(
        DEFAULT_DIRTY_WORKTREE_APPLICATION_PATH,
        "source-control dirty-worktree snapshot application",
    )
    candidate = deepcopy(payload)
    candidate["snapshot_categories"] = ["dirty_worktree_present"]
    candidate["review_items"][0]["state"] = "Ready"

    findings = validate_dirty_worktree_application(candidate)

    assert findings
    assert any(
        finding.rule_id == "source_control_review_checklist_dirty_worktree_categories_invalid"
        for finding in findings
    )
    assert any(
        finding.rule_id == "source_control_review_checklist_dirty_worktree_inventory_invalid"
        for finding in findings
    )
    assert any(
        finding.rule_id == "source_control_review_checklist_dirty_worktree_item_state_invalid"
        for finding in findings
    )


def test_dirty_worktree_application_rejects_private_value_and_effect_promotion() -> None:
    payload = load_json_object(
        DEFAULT_DIRTY_WORKTREE_APPLICATION_PATH,
        "source-control dirty-worktree snapshot application",
    )
    candidate = deepcopy(payload)
    candidate["review_items"][0]["application_note"] = "commit_status=approved customer_id=abc secret=value"
    candidate["next_action"] = "commit is approved"

    findings = validate_dirty_worktree_application(candidate)

    assert findings
    assert any(
        finding.rule_id == "source_control_review_checklist_forbidden_private_value_pattern"
        for finding in findings
    )
    assert any(
        finding.rule_id == "source_control_review_checklist_forbidden_promotion_phrase"
        for finding in findings
    )


def test_line_ending_application_rejects_warning_resolution_and_git_effects() -> None:
    payload = load_json_object(DEFAULT_LINE_ENDING_APPLICATION_PATH, "source-control line-ending warning application")
    candidate = deepcopy(payload)
    candidate["warning_resolution_claimed"] = True
    candidate["git_config_change_allowed"] = True
    candidate["file_rewrite_allowed"] = True
    candidate["commit_allowed"] = True

    findings = validate_line_ending_application(candidate)

    assert findings
    assert any(
        finding.rule_id == "source_control_review_checklist_line_ending_root_value_invalid"
        for finding in findings
    )


def test_line_ending_application_rejects_category_and_item_state_drift() -> None:
    payload = load_json_object(DEFAULT_LINE_ENDING_APPLICATION_PATH, "source-control line-ending warning application")
    candidate = deepcopy(payload)
    candidate["warning_categories"] = ["lf_to_crlf_warning_category"]
    candidate["triage_items"][0]["state"] = "Ready"

    findings = validate_line_ending_application(candidate)

    assert findings
    assert any(
        finding.rule_id == "source_control_review_checklist_line_ending_categories_invalid"
        for finding in findings
    )
    assert any(
        finding.rule_id == "source_control_review_checklist_line_ending_inventory_invalid"
        for finding in findings
    )
    assert any(
        finding.rule_id == "source_control_review_checklist_line_ending_item_state_invalid"
        for finding in findings
    )


def test_line_ending_application_rejects_private_value_and_effect_promotion() -> None:
    payload = load_json_object(DEFAULT_LINE_ENDING_APPLICATION_PATH, "source-control line-ending warning application")
    candidate = deepcopy(payload)
    candidate["triage_items"][0]["application_note"] = "commit_status=approved customer_id=abc secret=value"
    candidate["next_action"] = "commit is approved"

    findings = validate_line_ending_application(candidate)

    assert findings
    assert any(
        finding.rule_id == "source_control_review_checklist_forbidden_private_value_pattern"
        for finding in findings
    )
    assert any(
        finding.rule_id == "source_control_review_checklist_forbidden_promotion_phrase"
        for finding in findings
    )


def test_untracked_artifact_application_rejects_closure_and_git_effects() -> None:
    payload = load_json_object(
        DEFAULT_UNTRACKED_ARTIFACT_APPLICATION_PATH,
        "source-control untracked artifact application",
    )
    candidate = deepcopy(payload)
    candidate["artifact_count_recorded"] = True
    candidate["artifact_paths_recorded"] = True
    candidate["changed_file_list_recorded"] = True
    candidate["artifact_ownership_closed_claimed"] = True
    candidate["file_list_publication_allowed"] = True
    candidate["commit_allowed"] = True

    findings = validate_untracked_artifact_application(candidate)

    assert findings
    assert any(
        finding.rule_id == "source_control_review_checklist_untracked_artifact_root_value_invalid"
        for finding in findings
    )


def test_untracked_artifact_application_rejects_category_and_item_state_drift() -> None:
    payload = load_json_object(
        DEFAULT_UNTRACKED_ARTIFACT_APPLICATION_PATH,
        "source-control untracked artifact application",
    )
    candidate = deepcopy(payload)
    candidate["artifact_categories"] = ["new_document_artifact_category"]
    candidate["review_items"][0]["state"] = "Ready"

    findings = validate_untracked_artifact_application(candidate)

    assert findings
    assert any(
        finding.rule_id == "source_control_review_checklist_untracked_artifact_categories_invalid"
        for finding in findings
    )
    assert any(
        finding.rule_id == "source_control_review_checklist_untracked_artifact_inventory_invalid"
        for finding in findings
    )
    assert any(
        finding.rule_id == "source_control_review_checklist_untracked_artifact_item_state_invalid"
        for finding in findings
    )


def test_untracked_artifact_application_rejects_private_value_and_effect_promotion() -> None:
    payload = load_json_object(
        DEFAULT_UNTRACKED_ARTIFACT_APPLICATION_PATH,
        "source-control untracked artifact application",
    )
    candidate = deepcopy(payload)
    candidate["review_items"][0]["application_note"] = "commit_status=approved customer_id=abc secret=value"
    candidate["next_action"] = "commit is approved"

    findings = validate_untracked_artifact_application(candidate)

    assert findings
    assert any(
        finding.rule_id == "source_control_review_checklist_forbidden_private_value_pattern"
        for finding in findings
    )
    assert any(
        finding.rule_id == "source_control_review_checklist_forbidden_promotion_phrase"
        for finding in findings
    )


def test_unrelated_work_application_rejects_closure_and_destructive_effects() -> None:
    payload = load_json_object(
        DEFAULT_UNRELATED_WORK_APPLICATION_PATH,
        "source-control unrelated work preservation application",
    )
    candidate = deepcopy(payload)
    candidate["unrelated_work_closure_claimed"] = True
    candidate["ownership_assigned"] = True
    candidate["changed_file_list_recorded"] = True
    candidate["diff_scope_closed_claimed"] = True
    candidate["user_change_overwrite_allowed"] = True
    candidate["reset_allowed"] = True
    candidate["checkout_allowed"] = True
    candidate["delete_allowed"] = True
    candidate["move_allowed"] = True
    candidate["revert_allowed"] = True
    candidate["commit_allowed"] = True

    findings = validate_unrelated_work_application(candidate)

    assert findings
    assert any(
        finding.rule_id == "source_control_review_checklist_unrelated_work_root_value_invalid"
        for finding in findings
    )


def test_unrelated_work_application_rejects_category_and_item_state_drift() -> None:
    payload = load_json_object(
        DEFAULT_UNRELATED_WORK_APPLICATION_PATH,
        "source-control unrelated work preservation application",
    )
    candidate = deepcopy(payload)
    candidate["unrelated_work_categories"] = ["prior_or_user_work_possible"]
    candidate["review_items"][0]["state"] = "Ready"

    findings = validate_unrelated_work_application(candidate)

    assert findings
    assert any(
        finding.rule_id == "source_control_review_checklist_unrelated_work_categories_invalid"
        for finding in findings
    )
    assert any(
        finding.rule_id == "source_control_review_checklist_unrelated_work_inventory_invalid"
        for finding in findings
    )
    assert any(
        finding.rule_id == "source_control_review_checklist_unrelated_work_item_state_invalid"
        for finding in findings
    )


def test_unrelated_work_application_rejects_private_value_and_effect_promotion() -> None:
    payload = load_json_object(
        DEFAULT_UNRELATED_WORK_APPLICATION_PATH,
        "source-control unrelated work preservation application",
    )
    candidate = deepcopy(payload)
    candidate["review_items"][0]["application_note"] = "commit_status=approved customer_id=abc secret=value"
    candidate["next_action"] = "commit is approved"

    findings = validate_unrelated_work_application(candidate)

    assert findings
    assert any(
        finding.rule_id == "source_control_review_checklist_forbidden_private_value_pattern"
        for finding in findings
    )
    assert any(
        finding.rule_id == "source_control_review_checklist_forbidden_promotion_phrase"
        for finding in findings
    )


def test_secrets_application_rejects_secret_storage_and_git_effects() -> None:
    payload = load_json_object(
        DEFAULT_SECRETS_APPLICATION_PATH,
        "source-control secrets/private-value screening application",
    )
    candidate = deepcopy(payload)
    candidate["real_secret_storage_allowed"] = True
    candidate["credential_activation_allowed"] = True
    candidate["provider_account_binding_allowed"] = True
    candidate["secret_scan_pass_claimed"] = True
    candidate["commit_allowed"] = True

    findings = validate_secrets_application(candidate)

    assert findings
    assert any(
        finding.rule_id == "source_control_review_checklist_secrets_root_value_invalid"
        for finding in findings
    )


def test_secrets_application_rejects_category_and_item_state_drift() -> None:
    payload = load_json_object(
        DEFAULT_SECRETS_APPLICATION_PATH,
        "source-control secrets/private-value screening application",
    )
    candidate = deepcopy(payload)
    candidate["observed_screening_categories"] = ["secret_value_pattern_guard"]
    candidate["screening_items"][0]["state"] = "Ready"

    findings = validate_secrets_application(candidate)

    assert findings
    assert any(
        finding.rule_id == "source_control_review_checklist_secrets_categories_invalid"
        for finding in findings
    )
    assert any(
        finding.rule_id == "source_control_review_checklist_secrets_inventory_invalid"
        for finding in findings
    )
    assert any(
        finding.rule_id == "source_control_review_checklist_secrets_item_state_invalid"
        for finding in findings
    )


def test_secrets_application_rejects_private_value_and_effect_promotion() -> None:
    payload = load_json_object(
        DEFAULT_SECRETS_APPLICATION_PATH,
        "source-control secrets/private-value screening application",
    )
    candidate = deepcopy(payload)
    candidate["screening_items"][0]["application_note"] = "MULLU_SAMPLE_KEY=placeholder token=value"
    candidate["next_action"] = "commit is approved"

    findings = validate_secrets_application(candidate)

    assert findings
    assert any(
        finding.rule_id == "source_control_review_checklist_forbidden_private_value_pattern"
        for finding in findings
    )
    assert any(
        finding.rule_id == "source_control_review_checklist_forbidden_promotion_phrase"
        for finding in findings
    )


def test_runtime_safety_application_rejects_runtime_and_adapter_promotion() -> None:
    payload = load_json_object(
        DEFAULT_RUNTIME_SAFETY_APPLICATION_PATH,
        "source-control runtime-safety packet application",
    )
    candidate = deepcopy(payload)
    candidate["runtime_completion_claimed"] = True
    candidate["runtime_readiness_claimed"] = True
    candidate["adapter_authority_claimed"] = True
    candidate["provider_binding_claimed"] = True
    candidate["connector_use_claimed"] = True
    candidate["endpoint_target_recorded"] = True
    candidate["secret_use_claimed"] = True
    candidate["acceptance_test_harness_complete_claimed"] = True
    candidate["full_coverage_claimed"] = True
    candidate["commit_allowed"] = True

    findings = validate_runtime_safety_application(candidate)

    assert findings
    assert any(
        finding.rule_id == "source_control_review_checklist_runtime_safety_root_value_invalid"
        for finding in findings
    )


def test_runtime_safety_application_rejects_category_and_item_state_drift() -> None:
    payload = load_json_object(
        DEFAULT_RUNTIME_SAFETY_APPLICATION_PATH,
        "source-control runtime-safety packet application",
    )
    candidate = deepcopy(payload)
    candidate["packet_categories"] = ["phi_gps_v3_platform_overlay_category"]
    candidate["review_items"][0]["state"] = "Ready"

    findings = validate_runtime_safety_application(candidate)

    assert findings
    assert any(
        finding.rule_id == "source_control_review_checklist_runtime_safety_categories_invalid"
        for finding in findings
    )
    assert any(
        finding.rule_id == "source_control_review_checklist_runtime_safety_inventory_invalid"
        for finding in findings
    )
    assert any(
        finding.rule_id == "source_control_review_checklist_runtime_safety_item_state_invalid"
        for finding in findings
    )


def test_runtime_safety_application_rejects_private_value_and_effect_promotion() -> None:
    payload = load_json_object(
        DEFAULT_RUNTIME_SAFETY_APPLICATION_PATH,
        "source-control runtime-safety packet application",
    )
    candidate = deepcopy(payload)
    candidate["review_items"][0]["application_note"] = "endpoint_url=value token=value customer_id=abc"
    candidate["next_action"] = "deployment is ready"

    findings = validate_runtime_safety_application(candidate)

    assert findings
    assert any(
        finding.rule_id == "source_control_review_checklist_forbidden_private_value_pattern"
        for finding in findings
    )
    assert any(
        finding.rule_id == "source_control_review_checklist_forbidden_promotion_phrase"
        for finding in findings
    )
