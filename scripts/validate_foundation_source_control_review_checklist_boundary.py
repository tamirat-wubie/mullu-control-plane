#!/usr/bin/env python3
"""Validate the Foundation Mode source-control review checklist boundary.

Purpose: keep source-control review checklist drafting local and public-safe
while checklist completion, review-scope closure, validation completeness,
secret clearance, Git effects, external publication, deployment, customer
access, legal clearance, company formation, patent action, money movement, and
secret publication remain blocked.
Governance scope: Foundation Mode, source-control review checklist items,
private-value exclusion, source-control effect blocking, external-effect
blocking, and readiness blocking.
Dependencies: docs/FOUNDATION_SOURCE_CONTROL_REVIEW_CHECKLIST_BOUNDARY.md,
examples/foundation_source_control_review_checklist_witness.awaiting_evidence.json,
examples/foundation_source_control_review_checklist_current_packet.awaiting_evidence.json,
examples/foundation_dirty_worktree_snapshot_current_packet.awaiting_evidence.json,
examples/foundation_git_effect_stop_rule_current_packet.awaiting_evidence.json,
examples/foundation_external_action_stop_rule_current_packet.awaiting_evidence.json,
examples/foundation_validation_receipt_current_packet.awaiting_evidence.json,
examples/foundation_line_ending_warning_current_packet.awaiting_evidence.json,
examples/foundation_untracked_artifact_current_packet.awaiting_evidence.json,
examples/foundation_unrelated_work_preservation_current_packet.awaiting_evidence.json,
examples/foundation_secrets_credentials_current_packet.awaiting_evidence.json,
and examples/foundation_runtime_safety_current_packet.awaiting_evidence.json.
Invariants:
  - Validation is read-only.
  - The witness records checklist preparation only.
  - No Git, external publication, deployment, customer, legal, company, patent,
    money, or secret-publication action is authorized.
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
DEFAULT_DOC_PATH = REPO_ROOT / "docs" / "FOUNDATION_SOURCE_CONTROL_REVIEW_CHECKLIST_BOUNDARY.md"
DEFAULT_PACKET_PATH = REPO_ROOT / "examples" / "foundation_source_control_review_checklist_witness.awaiting_evidence.json"
DEFAULT_APPLICATION_PATH = (
    REPO_ROOT / "examples" / "foundation_source_control_review_checklist_current_packet.awaiting_evidence.json"
)
DEFAULT_VALIDATION_RECEIPT_APPLICATION_PATH = (
    REPO_ROOT / "examples" / "foundation_validation_receipt_current_packet.awaiting_evidence.json"
)
DEFAULT_NEXT_ACTION_WITNESS_PATH = REPO_ROOT / "examples" / "foundation_next_action_witness.awaiting_evidence.json"
DEFAULT_GIT_EFFECT_APPLICATION_PATH = (
    REPO_ROOT / "examples" / "foundation_git_effect_stop_rule_current_packet.awaiting_evidence.json"
)
DEFAULT_EXTERNAL_ACTION_APPLICATION_PATH = (
    REPO_ROOT / "examples" / "foundation_external_action_stop_rule_current_packet.awaiting_evidence.json"
)
DEFAULT_DIRTY_WORKTREE_APPLICATION_PATH = (
    REPO_ROOT / "examples" / "foundation_dirty_worktree_snapshot_current_packet.awaiting_evidence.json"
)
DEFAULT_LINE_ENDING_APPLICATION_PATH = (
    REPO_ROOT / "examples" / "foundation_line_ending_warning_current_packet.awaiting_evidence.json"
)
DEFAULT_UNTRACKED_ARTIFACT_APPLICATION_PATH = (
    REPO_ROOT / "examples" / "foundation_untracked_artifact_current_packet.awaiting_evidence.json"
)
DEFAULT_UNRELATED_WORK_APPLICATION_PATH = (
    REPO_ROOT / "examples" / "foundation_unrelated_work_preservation_current_packet.awaiting_evidence.json"
)
DEFAULT_SECRETS_APPLICATION_PATH = (
    REPO_ROOT / "examples" / "foundation_secrets_credentials_current_packet.awaiting_evidence.json"
)
DEFAULT_RUNTIME_SAFETY_APPLICATION_PATH = (
    REPO_ROOT / "examples" / "foundation_runtime_safety_current_packet.awaiting_evidence.json"
)

EXPECTED_WITNESS_ID = "foundation_source_control_review_checklist_witness.awaiting_evidence.v1"
EXPECTED_APPLICATION_ID = "foundation_source_control_review_checklist_current_packet.awaiting_evidence.v1"
EXPECTED_VALIDATION_RECEIPT_APPLICATION_ID = "foundation_validation_receipt_current_packet.awaiting_evidence.v1"
EXPECTED_NEXT_ACTION_WITNESS_ID = "foundation_next_action_witness.awaiting_evidence.v1"
EXPECTED_GIT_EFFECT_APPLICATION_ID = "foundation_git_effect_stop_rule_current_packet.awaiting_evidence.v1"
EXPECTED_EXTERNAL_ACTION_APPLICATION_ID = "foundation_external_action_stop_rule_current_packet.awaiting_evidence.v1"
EXPECTED_DIRTY_WORKTREE_APPLICATION_ID = "foundation_dirty_worktree_snapshot_current_packet.awaiting_evidence.v1"
EXPECTED_LINE_ENDING_APPLICATION_ID = "foundation_line_ending_warning_current_packet.awaiting_evidence.v1"
EXPECTED_UNTRACKED_ARTIFACT_APPLICATION_ID = "foundation_untracked_artifact_current_packet.awaiting_evidence.v1"
EXPECTED_UNRELATED_WORK_APPLICATION_ID = "foundation_unrelated_work_preservation_current_packet.awaiting_evidence.v1"
EXPECTED_SECRETS_APPLICATION_ID = "foundation_secrets_credentials_current_packet.awaiting_evidence.v1"
EXPECTED_RUNTIME_SAFETY_APPLICATION_ID = "foundation_runtime_safety_current_packet.awaiting_evidence.v1"
EXPECTED_BLOCKED_CLAIMS = (
    "checklist completion",
    "review-scope closure",
    "validation completeness",
    "secret clearance",
    "staging approval",
    "commit approval",
    "push approval",
    "pull request approval",
    "release readiness",
    "external publication",
    "deployment readiness",
    "customer access",
    "legal clearance",
    "company formation",
    "patent action",
    "money movement",
    "secret publication",
)
EXPECTED_CHECKLIST_ITEMS = (
    ("dirty_worktree_snapshot_review", "local_review", "AwaitingEvidence"),
    ("runtime_safety_packet_family_review", "local_review", "AwaitingEvidence"),
    ("unrelated_or_prior_work_review", "local_review", "AwaitingEvidence"),
    ("untracked_artifact_review", "local_review", "AwaitingEvidence"),
    ("validation_receipt_review", "local_review", "AwaitingEvidence"),
    ("secret_private_value_review", "local_review", "AwaitingEvidence"),
    ("line_ending_warning_review", "local_review", "AwaitingEvidence"),
    ("git_effect_stop_rule_review", "local_review", "AwaitingEvidence"),
    ("external_action_stop_rule_review", "local_review", "AwaitingEvidence"),
    ("next_action_review", "local_review", "AwaitingEvidence"),
)
EXPECTED_CHECKLIST_NOTE_FRAGMENTS = {
    "dirty_worktree_snapshot_review": (
        "dirty worktree snapshot review questions",
        "without claiming checklist completion",
    ),
    "runtime_safety_packet_family_review": (
        "runtime-safety packet family review questions",
        "without claiming review-scope closure",
    ),
    "unrelated_or_prior_work_review": (
        "user or prior work separation questions",
        "without reverting unrelated work",
    ),
    "untracked_artifact_review": (
        "validator and test artifact review questions",
        "without staging untracked files",
    ),
    "validation_receipt_review": (
        "saved governance receipt review questions",
        "without claiming validation completeness",
    ),
    "secret_private_value_review": (
        "secret-shaped or private value screening questions",
        "without claiming secret clearance",
    ),
    "line_ending_warning_review": (
        "CRLF warning triage questions",
        "without hiding warnings",
    ),
    "git_effect_stop_rule_review": (
        "staging, commit, push, and pull request stop-rule questions",
        "without authorizing Git effects",
    ),
    "external_action_stop_rule_review": (
        "customer, legal, company, patent, money, secret, publication, and deployment action stop-rule questions",
        "without authorizing external effects",
    ),
    "next_action_review": (
        "next bounded local action questions",
        "without release or deployment promotion",
    ),
}
EXPECTED_ROOT_KEYS = {
    "blocked_claims",
    "checklist_complete_claimed",
    "checklist_items",
    "commit_allowed",
    "company_formation_claimed",
    "customer_access_allowed",
    "deployment_allowed",
    "external_publication_allowed",
    "legal_clearance_claimed",
    "money_action_allowed",
    "next_action",
    "patent_action_allowed",
    "pull_request_allowed",
    "push_allowed",
    "release_allowed",
    "review_scope_closed_claimed",
    "schema_version",
    "secret_clearance_claimed",
    "secret_publication_allowed",
    "solver_outcome",
    "staging_allowed",
    "status",
    "validation_complete_claimed",
    "witness_id",
}
EXPECTED_CHECKLIST_ITEM_KEYS = {
    "checklist_id",
    "checklist_type",
    "evidence_ref",
    "public_safe_question",
    "state",
}
EXPECTED_APPLICATION_ROOT_KEYS = {
    "application_id",
    "blocked_claims",
    "checklist_complete_claimed",
    "commit_allowed",
    "company_formation_claimed",
    "customer_access_allowed",
    "deployment_allowed",
    "external_publication_allowed",
    "legal_clearance_claimed",
    "money_action_allowed",
    "next_action",
    "observed_change_categories",
    "patent_action_allowed",
    "pull_request_allowed",
    "push_allowed",
    "release_allowed",
    "review_context",
    "review_items",
    "review_scope_closed_claimed",
    "schema_version",
    "secret_clearance_claimed",
    "secret_publication_allowed",
    "solver_outcome",
    "source_control_review_checklist_witness_ref",
    "staging_allowed",
    "status",
    "validation_complete_claimed",
}
EXPECTED_REVIEW_CONTEXT_KEYS = {
    "branch_ref_recorded",
    "changed_file_list_recorded",
    "commit_ref_recorded",
    "company_filing_recorded",
    "customer_identifier_recorded",
    "endpoint_target_recorded",
    "legal_conclusion_recorded",
    "mode",
    "patent_filing_recorded",
    "payment_detail_recorded",
    "private_values_recorded",
    "provider_id_recorded",
    "pull_request_ref_recorded",
    "receipt_is_terminal_closure_claimed",
    "saved_preflight_receipt_available",
    "scope",
    "secret_value_recorded",
}
EXPECTED_APPLICATION_REVIEW_ITEM_KEYS = {
    "application_note",
    "checklist_id",
    "state",
}
EXPECTED_DIRTY_WORKTREE_ROOT_KEYS = {
    "application_id",
    "blocked_claims",
    "branch_ref_recorded",
    "changed_file_count_recorded",
    "changed_file_list_recorded",
    "clean_worktree_claimed",
    "commit_allowed",
    "commit_ref_recorded",
    "company_formation_claimed",
    "customer_access_allowed",
    "deployment_allowed",
    "dirty_state_observed",
    "exact_diff_recorded",
    "external_publication_allowed",
    "legal_clearance_claimed",
    "money_action_allowed",
    "next_action",
    "ownership_assigned",
    "patent_action_allowed",
    "private_paths_recorded",
    "pull_request_allowed",
    "pull_request_ref_recorded",
    "push_allowed",
    "release_allowed",
    "review_items",
    "schema_version",
    "secret_publication_allowed",
    "snapshot_categories",
    "solver_outcome",
    "source_control_review_checklist_current_packet_ref",
    "source_control_review_checklist_witness_ref",
    "staging_allowed",
    "status",
    "status_output_recorded",
}
EXPECTED_DIRTY_WORKTREE_ITEM_KEYS = {
    "application_note",
    "review_id",
    "state",
}
EXPECTED_DIRTY_WORKTREE_BLOCKED_CLAIMS = (
    "dirty-worktree closure",
    "clean worktree claim",
    "changed-file count closure",
    "changed-file list closure",
    "exact diff publication",
    "status-output publication",
    "branch ref publication",
    "commit ref publication",
    "pull request ref publication",
    "private path recording",
    "ownership assignment",
    "source-control approval",
    "staging approval",
    "commit approval",
    "push approval",
    "pull request approval",
    "release readiness",
    "external publication",
    "deployment readiness",
    "customer access",
    "legal clearance",
    "company formation",
    "patent action",
    "money movement",
    "secret publication",
)
EXPECTED_DIRTY_WORKTREE_CATEGORIES = (
    "dirty_worktree_present",
    "modified_worktree_category",
    "untracked_artifact_category",
    "prior_or_user_work_possible",
    "line_ending_warning_category",
    "no_file_list_recorded",
    "manual_review_pending",
    "git_effects_blocked",
)
EXPECTED_DIRTY_WORKTREE_ITEMS = (
    ("dirty_state_presence_review", "AwaitingEvidence"),
    ("status_output_boundary", "AwaitingEvidence"),
    ("file_count_boundary", "AwaitingEvidence"),
    ("file_list_boundary", "AwaitingEvidence"),
    ("source_control_ref_boundary", "AwaitingEvidence"),
    ("ownership_boundary", "AwaitingEvidence"),
    ("git_effect_stop_rule", "AwaitingEvidence"),
    ("external_effect_stop_rule", "AwaitingEvidence"),
)
EXPECTED_DIRTY_WORKTREE_NOTE_FRAGMENTS = {
    "dirty_state_presence_review": (
        "Dirty worktree presence is recorded as a category only",
        "no clean worktree claim is made",
    ),
    "status_output_boundary": (
        "Git status output is not copied",
        "status-output publication remains blocked",
    ),
    "file_count_boundary": (
        "Changed-file counts are not recorded",
        "no count closure is claimed",
    ),
    "file_list_boundary": (
        "Changed-file lists and exact diffs are not recorded",
        "private paths remain excluded",
    ),
    "source_control_ref_boundary": (
        "Branch refs, commit refs, and pull request refs are not recorded",
    ),
    "ownership_boundary": (
        "Ownership assignment remains blocked",
    ),
    "git_effect_stop_rule": (
        "Staging, commit, push, and pull request remain blocked",
    ),
    "external_effect_stop_rule": (
        "Publication, deployment, customer access, legal, company, patent, money, and secret-publication actions remain blocked",
    ),
}
EXPECTED_LINE_ENDING_ROOT_KEYS = {
    "application_id",
    "blocked_claims",
    "changed_file_list_recorded",
    "commit_allowed",
    "company_formation_claimed",
    "customer_access_allowed",
    "deployment_allowed",
    "external_publication_allowed",
    "file_rewrite_allowed",
    "git_config_change_allowed",
    "legal_clearance_claimed",
    "line_ending_normalization_allowed",
    "money_action_allowed",
    "next_action",
    "patent_action_allowed",
    "private_paths_recorded",
    "pull_request_allowed",
    "push_allowed",
    "release_allowed",
    "schema_version",
    "secret_publication_allowed",
    "solver_outcome",
    "source_control_review_checklist_current_packet_ref",
    "source_control_review_checklist_witness_ref",
    "staging_allowed",
    "status",
    "triage_items",
    "warning_categories",
    "warning_count_recorded",
    "warning_hidden_claimed",
    "warning_presence_observed",
    "warning_resolution_claimed",
    "warning_text_recorded",
}
EXPECTED_LINE_ENDING_TRIAGE_ITEM_KEYS = {
    "application_note",
    "state",
    "triage_id",
}
EXPECTED_LINE_ENDING_BLOCKED_CLAIMS = (
    "warning resolution",
    "warning hidden",
    "warning count closure",
    "changed-file list closure",
    "line-ending normalization",
    "Git configuration change",
    "file rewrite",
    "staging approval",
    "commit approval",
    "push approval",
    "pull request approval",
    "release readiness",
    "external publication",
    "deployment readiness",
    "customer access",
    "legal clearance",
    "company formation",
    "patent action",
    "money movement",
    "secret publication",
)
EXPECTED_LINE_ENDING_CATEGORIES = (
    "lf_to_crlf_warning_category",
    "diff_check_warning_category",
    "line_ending_policy_unknown",
    "manual_triage_pending",
    "no_file_list_recorded",
)
EXPECTED_LINE_ENDING_TRIAGE_ITEMS = (
    ("warning_presence_review", "AwaitingEvidence"),
    ("warning_count_boundary", "AwaitingEvidence"),
    ("file_list_boundary", "AwaitingEvidence"),
    ("mutation_stop_rule", "AwaitingEvidence"),
    ("git_effect_stop_rule", "AwaitingEvidence"),
    ("external_effect_stop_rule", "AwaitingEvidence"),
)
EXPECTED_LINE_ENDING_NOTE_FRAGMENTS = {
    "warning_presence_review": (
        "LF-to-CRLF warning category",
        "without claiming warning resolution",
    ),
    "warning_count_boundary": (
        "Warning count is not recorded",
        "no warning-count closure is claimed",
    ),
    "file_list_boundary": (
        "Changed-file list is not recorded",
        "private paths remain excluded",
    ),
    "mutation_stop_rule": (
        "Line-ending normalization",
        "Git configuration changes",
        "file rewrites remain blocked",
    ),
    "git_effect_stop_rule": (
        "Staging, commit, push, and pull request remain blocked",
    ),
    "external_effect_stop_rule": (
        "Publication, deployment, customer access, legal, company, patent, money, and secret-publication actions remain blocked",
    ),
}
EXPECTED_UNTRACKED_ARTIFACT_ROOT_KEYS = {
    "application_id",
    "artifact_categories",
    "artifact_contents_recorded",
    "artifact_count_recorded",
    "artifact_ownership_closed_claimed",
    "artifact_paths_recorded",
    "artifact_presence_observed",
    "blocked_claims",
    "changed_file_list_recorded",
    "commit_allowed",
    "company_formation_claimed",
    "customer_access_allowed",
    "deployment_allowed",
    "external_publication_allowed",
    "file_list_publication_allowed",
    "legal_clearance_claimed",
    "money_action_allowed",
    "next_action",
    "patent_action_allowed",
    "private_paths_recorded",
    "pull_request_allowed",
    "push_allowed",
    "release_allowed",
    "review_items",
    "schema_version",
    "secret_publication_allowed",
    "solver_outcome",
    "source_control_review_checklist_current_packet_ref",
    "source_control_review_checklist_witness_ref",
    "staging_allowed",
    "status",
}
EXPECTED_UNTRACKED_ARTIFACT_ITEM_KEYS = {
    "application_note",
    "review_id",
    "state",
}
EXPECTED_UNTRACKED_ARTIFACT_BLOCKED_CLAIMS = (
    "untracked artifact closure",
    "artifact count closure",
    "changed-file list closure",
    "file-list publication",
    "private path recording",
    "artifact ownership closure",
    "artifact content publication",
    "staging approval",
    "commit approval",
    "push approval",
    "pull request approval",
    "release readiness",
    "external publication",
    "deployment readiness",
    "customer access",
    "legal clearance",
    "company formation",
    "patent action",
    "money movement",
    "secret publication",
)
EXPECTED_UNTRACKED_ARTIFACT_CATEGORIES = (
    "new_document_artifact_category",
    "new_example_packet_category",
    "new_validator_script_category",
    "new_test_artifact_category",
    "source_control_review_category",
    "no_file_list_recorded",
    "manual_review_pending",
)
EXPECTED_UNTRACKED_ARTIFACT_ITEMS = (
    ("untracked_presence_review", "AwaitingEvidence"),
    ("artifact_count_boundary", "AwaitingEvidence"),
    ("artifact_path_boundary", "AwaitingEvidence"),
    ("artifact_content_boundary", "AwaitingEvidence"),
    ("ownership_scope_boundary", "AwaitingEvidence"),
    ("git_effect_stop_rule", "AwaitingEvidence"),
    ("external_effect_stop_rule", "AwaitingEvidence"),
)
EXPECTED_UNTRACKED_ARTIFACT_NOTE_FRAGMENTS = {
    "untracked_presence_review": (
        "untracked artifact category",
        "without claiming untracked artifact closure",
    ),
    "artifact_count_boundary": (
        "Artifact count is not recorded",
        "no artifact-count closure is claimed",
    ),
    "artifact_path_boundary": (
        "Artifact paths and changed-file lists are not recorded",
        "private paths remain excluded",
    ),
    "artifact_content_boundary": (
        "Artifact contents are not copied",
        "content publication remains blocked",
    ),
    "ownership_scope_boundary": (
        "Artifact ownership and review scope remain manual review questions",
    ),
    "git_effect_stop_rule": (
        "Staging, commit, push, and pull request remain blocked",
    ),
    "external_effect_stop_rule": (
        "Publication, deployment, customer access, legal, company, patent, money, and secret-publication actions remain blocked",
    ),
}
EXPECTED_UNRELATED_WORK_ROOT_KEYS = {
    "application_id",
    "blocked_claims",
    "changed_file_list_recorded",
    "checkout_allowed",
    "commit_allowed",
    "company_formation_claimed",
    "customer_access_allowed",
    "delete_allowed",
    "deployment_allowed",
    "diff_scope_closed_claimed",
    "exact_diff_recorded",
    "external_publication_allowed",
    "legal_clearance_claimed",
    "money_action_allowed",
    "move_allowed",
    "next_action",
    "ownership_assigned",
    "patent_action_allowed",
    "preservation_required",
    "prior_work_closure_claimed",
    "private_paths_recorded",
    "pull_request_allowed",
    "push_allowed",
    "release_allowed",
    "reset_allowed",
    "revert_allowed",
    "review_items",
    "schema_version",
    "secret_publication_allowed",
    "solver_outcome",
    "source_control_review_checklist_current_packet_ref",
    "source_control_review_checklist_witness_ref",
    "staging_allowed",
    "status",
    "unrelated_work_categories",
    "unrelated_work_closure_claimed",
    "user_change_overwrite_allowed",
}
EXPECTED_UNRELATED_WORK_ITEM_KEYS = {
    "application_note",
    "review_id",
    "state",
}
EXPECTED_UNRELATED_WORK_BLOCKED_CLAIMS = (
    "unrelated-work closure",
    "prior-work closure",
    "ownership assignment",
    "changed-file list closure",
    "diff scope closure",
    "user-change overwrite",
    "reset approval",
    "checkout approval",
    "delete approval",
    "move approval",
    "revert approval",
    "staging approval",
    "commit approval",
    "push approval",
    "pull request approval",
    "release readiness",
    "external publication",
    "deployment readiness",
    "customer access",
    "legal clearance",
    "company formation",
    "patent action",
    "money movement",
    "secret publication",
)
EXPECTED_UNRELATED_WORK_CATEGORIES = (
    "prior_or_user_work_possible",
    "ownership_unknown",
    "manual_review_pending",
    "no_file_list_recorded",
    "destructive_git_effects_blocked",
    "preserve_until_explicit_review",
)
EXPECTED_UNRELATED_WORK_ITEMS = (
    ("prior_or_user_work_presence_review", "AwaitingEvidence"),
    ("ownership_boundary", "AwaitingEvidence"),
    ("file_list_boundary", "AwaitingEvidence"),
    ("destructive_effect_stop_rule", "AwaitingEvidence"),
    ("user_change_preservation_rule", "AwaitingEvidence"),
    ("git_effect_stop_rule", "AwaitingEvidence"),
    ("external_effect_stop_rule", "AwaitingEvidence"),
)
EXPECTED_UNRELATED_WORK_NOTE_FRAGMENTS = {
    "prior_or_user_work_presence_review": (
        "Prior or user work is treated as possible",
        "without claiming unrelated-work closure",
    ),
    "ownership_boundary": (
        "Ownership remains unknown",
        "no ownership assignment is claimed",
    ),
    "file_list_boundary": (
        "Changed-file lists and exact diffs are not recorded",
    ),
    "destructive_effect_stop_rule": (
        "Reset, checkout, delete, move, and revert remain blocked",
    ),
    "user_change_preservation_rule": (
        "User-change overwrite remains blocked",
        "preservation is required",
    ),
    "git_effect_stop_rule": (
        "Staging, commit, push, and pull request remain blocked",
    ),
    "external_effect_stop_rule": (
        "Publication, deployment, customer access, legal, company, patent, money, and secret-publication actions remain blocked",
    ),
}
EXPECTED_SECRETS_ROOT_KEYS = {
    "api_key_creation_allowed",
    "application_id",
    "blocked_claims",
    "commit_allowed",
    "company_formation_claimed",
    "credential_activation_allowed",
    "customer_access_allowed",
    "deployment_allowed",
    "env_file_commit_allowed",
    "external_call_allowed",
    "external_publication_allowed",
    "legal_clearance_claimed",
    "money_action_allowed",
    "next_action",
    "oauth_app_creation_allowed",
    "observed_screening_categories",
    "patent_action_allowed",
    "private_key_storage_allowed",
    "provider_account_binding_allowed",
    "pull_request_allowed",
    "push_allowed",
    "real_secret_storage_allowed",
    "schema_version",
    "screening_context",
    "screening_items",
    "secret_rotation_claimed",
    "secret_scan_pass_claimed",
    "service_account_creation_allowed",
    "solver_outcome",
    "source_witness_ref",
    "staging_allowed",
    "status",
}
EXPECTED_SECRETS_CONTEXT_KEYS = {
    "account_identifier_recorded",
    "assigned_environment_value_recorded",
    "changed_file_list_recorded",
    "credential_value_recorded",
    "mode",
    "private_path_recorded",
    "private_values_recorded",
    "provider_binding_recorded",
    "receipt_is_terminal_closure_claimed",
    "saved_preflight_receipt_available",
    "scope",
    "secret_value_recorded",
}
EXPECTED_SECRETS_ITEM_KEYS = {
    "application_note",
    "state",
    "surface_id",
}
EXPECTED_SECRETS_BLOCKED_CLAIMS = (
    "real secret storage",
    "credential activation",
    "provider account binding",
    "API key creation",
    "OAuth app creation",
    "service account creation",
    "environment file commit",
    "private key storage",
    "secret rotation readiness",
    "secret scan pass",
    "external call readiness",
    "deployment readiness",
    "customer access",
    "external publication",
    "legal clearance",
    "company formation",
    "patent action",
    "money movement",
    "Git effect",
)
EXPECTED_SECRETS_CATEGORIES = (
    "secret_value_pattern_guard",
    "environment_assignment_guard",
    "private_path_guard",
    "token_shape_guard",
    "provider_binding_guard",
    "source_control_publication_stop_rule",
    "current_packet_category_only_review",
)
EXPECTED_SECRETS_ITEMS = (
    ("credential_inventory_draft", "AwaitingEvidence"),
    ("environment_variable_plan", "AwaitingEvidence"),
    ("provider_access_questions", "AwaitingEvidence"),
    ("api_key_questions", "AwaitingEvidence"),
    ("oauth_app_questions", "AwaitingEvidence"),
    ("service_account_questions", "AwaitingEvidence"),
    ("rotation_recovery_questions", "AwaitingEvidence"),
    ("secret_scan_checklist", "AwaitingEvidence"),
)
EXPECTED_SECRETS_NOTE_FRAGMENTS = {
    "credential_inventory_draft": (
        "Credential inventory draft category only",
        "no real secret values",
        "live provider bindings",
    ),
    "environment_variable_plan": (
        "Environment variable plan category only",
        "no environment files or assigned values",
    ),
    "provider_access_questions": (
        "Provider access question category only",
        "no provider account identifiers",
    ),
    "api_key_questions": (
        "API key question category only",
        "no created keys",
        "key readiness is claimed",
    ),
    "oauth_app_questions": (
        "OAuth app question category only",
        "no client secrets",
    ),
    "service_account_questions": (
        "Service account question category only",
        "no service account keys",
    ),
    "rotation_recovery_questions": (
        "Rotation and recovery question category only",
        "no rotation-ready claim",
    ),
    "secret_scan_checklist": (
        "Secret scan checklist category only",
        "no scan-pass claim",
    ),
}
EXPECTED_RUNTIME_SAFETY_ROOT_KEYS = {
    "acceptance_test_harness_complete_claimed",
    "adapter_authority_claimed",
    "application_id",
    "blocked_claims",
    "changed_file_list_recorded",
    "commit_allowed",
    "company_formation_claimed",
    "connector_use_claimed",
    "customer_access_allowed",
    "deployment_allowed",
    "endpoint_target_recorded",
    "external_publication_allowed",
    "full_coverage_claimed",
    "legal_clearance_claimed",
    "money_action_allowed",
    "next_action",
    "packet_categories",
    "patent_action_allowed",
    "private_values_recorded",
    "provider_binding_claimed",
    "pull_request_allowed",
    "push_allowed",
    "release_allowed",
    "review_items",
    "review_scope_closed_claimed",
    "runtime_completion_claimed",
    "runtime_readiness_claimed",
    "runtime_safety_family_observed",
    "schema_version",
    "secret_publication_allowed",
    "secret_use_claimed",
    "secret_value_recorded",
    "solver_outcome",
    "source_control_review_checklist_current_packet_ref",
    "source_control_review_checklist_witness_ref",
    "staging_allowed",
    "status",
}
EXPECTED_RUNTIME_SAFETY_ITEM_KEYS = {
    "application_note",
    "review_id",
    "state",
}
EXPECTED_RUNTIME_SAFETY_BLOCKED_CLAIMS = (
    "runtime completion",
    "runtime readiness",
    "public readiness",
    "adapter authority",
    "provider binding",
    "connector use",
    "endpoint target recording",
    "secret use",
    "secret value recording",
    "acceptance-test harness completion",
    "full coverage",
    "review-scope closure",
    "source-control approval",
    "staging approval",
    "commit approval",
    "push approval",
    "pull request approval",
    "release readiness",
    "external publication",
    "deployment readiness",
    "customer access",
    "legal clearance",
    "company formation",
    "patent action",
    "money movement",
    "secret publication",
)
EXPECTED_RUNTIME_SAFETY_CATEGORIES = (
    "phi_gps_v3_platform_overlay_category",
    "runtime_safety_hardening_category",
    "problem_compiler_contract_category",
    "provider_connector_secret_pagination_category",
    "governance_preflight_coverage_category",
    "acceptance_test_harness_pending",
    "runtime_completion_blocked",
    "adapter_authority_blocked",
    "no_endpoint_values_recorded",
    "no_secret_values_recorded",
    "git_effects_blocked",
)
EXPECTED_RUNTIME_SAFETY_ITEMS = (
    ("platform_overlay_boundary", "AwaitingEvidence"),
    ("runtime_completion_boundary", "AwaitingEvidence"),
    ("adapter_authority_boundary", "AwaitingEvidence"),
    ("acceptance_test_boundary", "AwaitingEvidence"),
    ("evidence_scope_boundary", "AwaitingEvidence"),
    ("git_effect_stop_rule", "AwaitingEvidence"),
    ("external_effect_stop_rule", "AwaitingEvidence"),
)
EXPECTED_RUNTIME_SAFETY_NOTE_FRAGMENTS = {
    "platform_overlay_boundary": (
        "Phi-GPS v3 platform overlay is recorded as a local specification category only",
        "runtime completion remains unclaimed",
    ),
    "runtime_completion_boundary": (
        "Runtime implementation",
        "external deployment",
        "customer readiness remain AwaitingEvidence",
    ),
    "adapter_authority_boundary": (
        "Adapter authority",
        "provider binding",
        "connector use",
        "endpoint targets",
        "secret use remain blocked",
    ),
    "acceptance_test_boundary": (
        "Acceptance-test harness completion",
        "full coverage remain unclaimed",
    ),
    "evidence_scope_boundary": (
        "Changed-file lists",
        "private values",
        "endpoint values",
        "provider ids",
        "secret values are not recorded",
    ),
    "git_effect_stop_rule": (
        "Staging, commit, push, and pull request remain blocked",
    ),
    "external_effect_stop_rule": (
        "Publication, deployment, customer access, legal, company, patent, money, and secret-publication actions remain blocked",
    ),
}
EXPECTED_OBSERVED_CHANGE_CATEGORIES = (
    "foundation_posture_and_navigation",
    "dirty_worktree_snapshot_current_packet_triage",
    "source_control_review_checklist_boundary",
    "source_control_boundary_and_preflight_wiring",
    "diff_review_change_handoff_test_evidence_boundaries",
    "unrelated_prior_work_preservation_triage",
    "secrets_credentials_current_packet_screening",
    "line_ending_warning_current_packet_triage",
    "untracked_artifact_current_packet_triage",
    "runtime_safety_current_packet_triage",
    "phi_gps_v3_runtime_safety_packet",
    "provider_connector_secret_pagination_hardening",
    "workspace_governance_receipt_and_witness_contracts",
    "validation_receipt_current_packet_routing",
    "untracked_validator_and_test_artifacts",
)
EXPECTED_APPLICATION_REVIEW_ITEMS = tuple((checklist_id, "AwaitingEvidence") for checklist_id, _, _ in EXPECTED_CHECKLIST_ITEMS)
EXPECTED_APPLICATION_NOTE_FRAGMENTS = {
    "dirty_worktree_snapshot_review": (
        "current dirty worktree categories",
        "without claiming checklist completion",
    ),
    "runtime_safety_packet_family_review": (
        "runtime-safety current packet and family category",
        "without claiming review-scope closure",
    ),
    "unrelated_or_prior_work_review": (
        "user or prior work separation",
        "without reverting unrelated work",
    ),
    "untracked_artifact_review": (
        "validator and test artifact category",
        "without staging untracked files",
    ),
    "validation_receipt_review": (
        "saved governance receipt",
        "without claiming validation completeness",
    ),
    "secret_private_value_review": (
        "secret-shaped or private value screening",
        "without claiming secret clearance",
    ),
    "line_ending_warning_review": (
        "CRLF warning category",
        "without hiding warnings",
    ),
    "git_effect_stop_rule_review": (
        "staging, commit, push, and pull request stop-rule",
        "without authorizing Git effects",
    ),
    "external_action_stop_rule_review": (
        "customer, legal, company, patent, money, secret, publication, and deployment action stop-rule",
        "without authorizing external effects",
    ),
    "next_action_review": (
        "next bounded local action",
        "without release or deployment promotion",
    ),
}
EXPECTED_VALIDATION_RECEIPT_ROOT_KEYS = {
    "application_categories",
    "application_id",
    "blocked_claims",
    "check_count_recorded",
    "check_stdout_recorded",
    "ci_parity_claimed",
    "commit_allowed",
    "complete_coverage_claimed",
    "customer_readiness_claimed",
    "deployment_allowed",
    "deployment_readiness_claimed",
    "external_publication_allowed",
    "failed_check_names_recorded",
    "flake_free_guarantee_claimed",
    "freshness_claimed",
    "full_test_pass_claimed",
    "generated_at_recorded",
    "legal_clearance_claimed",
    "next_action",
    "performance_readiness_claimed",
    "private_path_recorded",
    "pull_request_allowed",
    "push_allowed",
    "receipt_content_recorded",
    "receipt_presence_observed",
    "receipt_summary_recorded",
    "release_readiness_claimed",
    "saved_receipt_ref",
    "schema_version",
    "secret_clearance_claimed",
    "security_clearance_claimed",
    "solver_outcome",
    "source_receipt_routing_ref",
    "source_test_evidence_witness_ref",
    "staging_allowed",
    "status",
    "terminal_closure_claimed",
    "validation_items",
    "validator_ref",
}
EXPECTED_VALIDATION_RECEIPT_ITEM_KEYS = {
    "application_note",
    "state",
    "validation_id",
}
EXPECTED_VALIDATION_RECEIPT_BLOCKED_CLAIMS = (
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
    "receipt freshness",
    "check-count closure",
    "failed-check closure",
    "source-control approval",
)
EXPECTED_VALIDATION_RECEIPT_CATEGORIES = (
    "saved_preflight_receipt_presence_category",
    "receipt_validation_command_category",
    "receipt_summary_boundary",
    "check_count_boundary",
    "failed_check_name_boundary",
    "receipt_content_boundary",
    "freshness_boundary",
    "promotion_stop_rule",
)
EXPECTED_VALIDATION_RECEIPT_ITEMS = (
    ("receipt_presence_review", "AwaitingEvidence"),
    ("receipt_validation_review", "AwaitingEvidence"),
    ("receipt_summary_boundary", "AwaitingEvidence"),
    ("check_count_boundary", "AwaitingEvidence"),
    ("failed_check_name_boundary", "AwaitingEvidence"),
    ("freshness_boundary", "AwaitingEvidence"),
    ("promotion_stop_rule", "AwaitingEvidence"),
    ("git_effect_stop_rule", "AwaitingEvidence"),
)
EXPECTED_VALIDATION_RECEIPT_NOTE_FRAGMENTS = {
    "receipt_presence_review": (
        "Saved preflight receipt presence",
        "receipt content is not copied",
    ),
    "receipt_validation_review": (
        "Receipt-validation command",
        "without claiming terminal closure",
    ),
    "receipt_summary_boundary": (
        "Receipt summary values are not recorded",
        "exact result review remains local",
    ),
    "check_count_boundary": (
        "Check counts are not recorded",
        "no check-count closure is claimed",
    ),
    "failed_check_name_boundary": (
        "Failed-check names are not recorded",
        "no failed-check closure is claimed",
    ),
    "freshness_boundary": (
        "Generated timestamps and freshness values are not recorded",
        "freshness remains a local review question",
    ),
    "promotion_stop_rule": (
        "Full-test, coverage, CI, release, security, customer, legal, terminal-closure, publication, and deployment promotions remain blocked",
    ),
    "git_effect_stop_rule": (
        "Staging, commit, push, and pull request remain blocked",
    ),
}
EXPECTED_NEXT_ACTION_ROOT_KEYS = {
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
EXPECTED_NEXT_ACTION_SURFACE_KEYS = {
    "evidence_ref",
    "public_safe_note",
    "state",
    "surface_id",
    "surface_type",
}
EXPECTED_NEXT_ACTION_BLOCKED_CLAIMS = (
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
EXPECTED_NEXT_ACTION_SURFACES = (
    ("continue_request_triage", "local_draft", "AwaitingEvidence"),
    ("smallest_prerequisite_selection", "local_draft", "AwaitingEvidence"),
    ("dependency_check", "local_draft", "AwaitingEvidence"),
    ("local_edit_scope", "local_draft", "AwaitingEvidence"),
    ("verification_plan", "local_draft", "AwaitingEvidence"),
    ("stop_rule", "local_draft", "AwaitingEvidence"),
    ("evidence_receipt_plan", "local_draft", "AwaitingEvidence"),
    ("handoff_summary", "local_draft", "AwaitingEvidence"),
)
EXPECTED_NEXT_ACTION_NOTE_FRAGMENTS = {
    "continue_request_triage": (
        "broad continuation execution is not authorized",
    ),
    "smallest_prerequisite_selection": (
        "deployment, customer, legal, money, and publication work remain blocked",
    ),
    "dependency_check": (
        "unknown hard constraints remain AwaitingEvidence",
    ),
    "local_edit_scope": (
        "external systems, website publication, DNS, accounts, and services remain untouched",
    ),
    "verification_plan": (
        "completion is not claimed without focused checks and preflight evidence",
    ),
    "stop_rule": (
        "roadmap commitment or deadline promise",
    ),
    "evidence_receipt_plan": (
        "no secrets, credentials, customer data, provider accounts, or private paths are recorded",
    ),
    "handoff_summary": (
        "staging, committing, pushing, publishing, and deployment require explicit later request",
    ),
}
EXPECTED_GIT_EFFECT_ROOT_KEYS = {
    "application_id",
    "approval_claimed",
    "blocked_claims",
    "branch_ref_recorded",
    "branch_switch_allowed",
    "changed_file_list_recorded",
    "checkout_allowed",
    "commit_allowed",
    "commit_ref_recorded",
    "exact_diff_recorded",
    "effect_categories",
    "git_config_change_allowed",
    "next_action",
    "private_paths_recorded",
    "pull_request_allowed",
    "pull_request_ref_recorded",
    "push_allowed",
    "release_allowed",
    "reset_allowed",
    "revert_allowed",
    "review_items",
    "schema_version",
    "solver_outcome",
    "source_control_boundary_ref",
    "source_control_publication_allowed",
    "source_control_review_checklist_current_packet_ref",
    "source_control_review_checklist_witness_ref",
    "staging_allowed",
    "status",
    "status_output_recorded",
    "tag_allowed",
}
EXPECTED_GIT_EFFECT_ITEM_KEYS = {
    "application_note",
    "review_id",
    "state",
}
EXPECTED_GIT_EFFECT_BLOCKED_CLAIMS = (
    "source-control approval",
    "staging approval",
    "commit approval",
    "push approval",
    "pull request approval",
    "branch switch approval",
    "tag creation",
    "release readiness",
    "source-control publication",
    "status-output publication",
    "changed-file list closure",
    "exact-diff publication",
    "private path recording",
    "Git configuration change",
    "reset approval",
    "checkout approval",
    "revert approval",
)
EXPECTED_GIT_EFFECT_CATEGORIES = (
    "git_effect_stop_rule_category",
    "source_control_publication_stop_rule",
    "staging_commit_push_pr_blocked",
    "branch_ref_commit_ref_pr_ref_blocked",
    "status_output_and_file_list_blocked",
    "destructive_git_effects_blocked",
    "git_config_change_blocked",
    "manual_review_pending",
)
EXPECTED_GIT_EFFECT_ITEMS = (
    ("staging_boundary", "AwaitingEvidence"),
    ("commit_boundary", "AwaitingEvidence"),
    ("push_boundary", "AwaitingEvidence"),
    ("pull_request_boundary", "AwaitingEvidence"),
    ("source_control_ref_boundary", "AwaitingEvidence"),
    ("status_output_boundary", "AwaitingEvidence"),
    ("destructive_effect_boundary", "AwaitingEvidence"),
    ("git_config_boundary", "AwaitingEvidence"),
)
EXPECTED_GIT_EFFECT_NOTE_FRAGMENTS = {
    "staging_boundary": (
        "Staging remains blocked",
        "no staging approval is claimed",
    ),
    "commit_boundary": (
        "Commit remains blocked",
        "no commit approval is claimed",
    ),
    "push_boundary": (
        "Push remains blocked",
        "no push approval is claimed",
    ),
    "pull_request_boundary": (
        "Pull request remains blocked",
        "no pull request approval is claimed",
    ),
    "source_control_ref_boundary": (
        "Branch refs, commit refs, and pull request refs are not recorded",
    ),
    "status_output_boundary": (
        "Status output, changed-file lists, and exact diffs are not recorded",
    ),
    "destructive_effect_boundary": (
        "Reset, checkout, and revert remain blocked",
    ),
    "git_config_boundary": (
        "Git configuration changes remain blocked",
    ),
}
EXPECTED_EXTERNAL_ACTION_ROOT_KEYS = {
    "application_id",
    "blocked_claims",
    "company_action_allowed",
    "company_filing_recorded",
    "company_formation_claimed",
    "customer_access_allowed",
    "customer_action_allowed",
    "customer_identifier_recorded",
    "deployment_allowed",
    "deployment_readiness_claimed",
    "endpoint_target_recorded",
    "external_account_activation_allowed",
    "external_action_allowed",
    "external_publication_allowed",
    "legal_action_allowed",
    "legal_clearance_claimed",
    "legal_conclusion_recorded",
    "money_action_allowed",
    "next_action",
    "patent_action_allowed",
    "patent_filing_recorded",
    "payment_detail_recorded",
    "personal_data_collection_allowed",
    "provider_binding_allowed",
    "provider_id_recorded",
    "review_items",
    "schema_version",
    "secret_publication_allowed",
    "secret_value_recorded",
    "service_activation_allowed",
    "solver_outcome",
    "source_control_review_checklist_current_packet_ref",
    "source_control_review_checklist_witness_ref",
    "status",
    "stop_rule_categories",
}
EXPECTED_EXTERNAL_ACTION_ITEM_KEYS = {
    "application_note",
    "review_id",
    "state",
}
EXPECTED_EXTERNAL_ACTION_BLOCKED_CLAIMS = (
    "external action approval",
    "external publication",
    "deployment readiness",
    "customer access",
    "customer action",
    "legal clearance",
    "legal action",
    "company formation",
    "company action",
    "patent action",
    "money movement",
    "payment action",
    "secret publication",
    "external account activation",
    "service activation",
    "provider binding",
    "endpoint target recording",
    "personal-data collection",
)
EXPECTED_EXTERNAL_ACTION_CATEGORIES = (
    "external_action_stop_rule_category",
    "customer_action_blocked",
    "legal_company_patent_blocked",
    "money_payment_blocked",
    "secret_publication_blocked",
    "publication_deployment_blocked",
    "external_account_service_provider_blocked",
    "no_external_values_recorded",
)
EXPECTED_EXTERNAL_ACTION_ITEMS = (
    ("external_action_boundary", "AwaitingEvidence"),
    ("publication_deployment_boundary", "AwaitingEvidence"),
    ("customer_action_boundary", "AwaitingEvidence"),
    ("legal_company_boundary", "AwaitingEvidence"),
    ("patent_action_boundary", "AwaitingEvidence"),
    ("money_payment_boundary", "AwaitingEvidence"),
    ("secret_publication_boundary", "AwaitingEvidence"),
    ("external_service_boundary", "AwaitingEvidence"),
)
EXPECTED_EXTERNAL_ACTION_NOTE_FRAGMENTS = {
    "external_action_boundary": (
        "External action remains blocked",
        "no external approval is claimed",
    ),
    "publication_deployment_boundary": (
        "Publication and deployment remain blocked",
        "no readiness claim is made",
    ),
    "customer_action_boundary": (
        "Customer access and customer action remain blocked",
        "no customer identifiers are recorded",
    ),
    "legal_company_boundary": (
        "Legal and company actions remain blocked",
        "no legal conclusions or company filings are recorded",
    ),
    "patent_action_boundary": (
        "Patent action remains blocked",
        "no patent filings are recorded",
    ),
    "money_payment_boundary": (
        "Money and payment actions remain blocked",
        "no payment details are recorded",
    ),
    "secret_publication_boundary": (
        "Secret publication remains blocked",
        "no secret values are recorded",
    ),
    "external_service_boundary": (
        "External account activation",
        "service activation",
        "provider binding",
        "endpoint target recording",
        "personal-data collection remain blocked",
    ),
}
REQUIRED_DOC_PHRASES = (
    "Foundation Source-Control Review Checklist Boundary",
    "Witness packet: [`../examples/foundation_source_control_review_checklist_witness.awaiting_evidence.json`]",
    "Application packet: [`../examples/foundation_source_control_review_checklist_current_packet.awaiting_evidence.json`]",
    "Validation receipt packet: [`../examples/foundation_validation_receipt_current_packet.awaiting_evidence.json`]",
    "Next-action witness packet: [`../examples/foundation_next_action_witness.awaiting_evidence.json`]",
    "Git-effect stop-rule packet: [`../examples/foundation_git_effect_stop_rule_current_packet.awaiting_evidence.json`]",
    "External-action stop-rule packet: [`../examples/foundation_external_action_stop_rule_current_packet.awaiting_evidence.json`]",
    "Dirty-worktree snapshot packet: [`../examples/foundation_dirty_worktree_snapshot_current_packet.awaiting_evidence.json`]",
    "Line-ending warning packet: [`../examples/foundation_line_ending_warning_current_packet.awaiting_evidence.json`]",
    "Untracked artifact packet: [`../examples/foundation_untracked_artifact_current_packet.awaiting_evidence.json`]",
    "Unrelated work preservation packet: [`../examples/foundation_unrelated_work_preservation_current_packet.awaiting_evidence.json`]",
    "Secrets/private-value screening packet: [`../examples/foundation_secrets_credentials_current_packet.awaiting_evidence.json`]",
    "Runtime-safety packet: [`../examples/foundation_runtime_safety_current_packet.awaiting_evidence.json`]",
    "Rule: Source-control review checklist preparation is a local planning boundary",
    "No checklist completion, review-scope closure, staging approval, commit",
    "source_control_review_checklist_state=AwaitingEvidence",
    "checklist_complete_claimed=false",
    "review_scope_closed_claimed=false",
    "validation_complete_claimed=false",
    "secret_clearance_claimed=false",
    "staging_allowed=false",
    "commit_allowed=false",
    "push_allowed=false",
    "pull_request_allowed=false",
    "deployment_allowed=false",
    "customer_access_allowed=false",
    "legal_clearance_claimed=false",
    "company_formation_claimed=false",
    "patent_action_allowed=false",
    "money_action_allowed=false",
    "secret_publication_allowed=false",
    "Runtime-safety packet family review",
    "External-action stop-rule review",
    "Current Dirty-Packet Application",
    "Validation Receipt Current-Packet Application",
    "Next-Action Witness Review",
    "Git-Effect Stop-Rule Application",
    "External-Action Stop-Rule Application",
    "Dirty-Worktree Snapshot Application",
    "Line-Ending Warning Application",
    "Untracked Artifact Application",
    "Unrelated Work Preservation Application",
    "Secrets/Private-Value Screening Application",
    "Runtime-Safety Packet Application",
    "Validation receipt current-packet routing",
    "python scripts/validate_foundation_source_control_review_checklist_boundary.py",
)
FORBIDDEN_VALUE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("url_value", re.compile(r"https?://", re.IGNORECASE)),
    ("email_value", re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)),
    ("private_path", re.compile(r"\b[A-Za-z]:[\\/]|\\\\", re.IGNORECASE)),
    (
        "source_control_assignment",
        re.compile(
            r"\b(?:stage|staging|commit|branch|push|pull[_ -]?request|release|revert)[_ -]?"
            r"(?:id|ref|target|value|status|result|state|approval)?\s*=",
            re.IGNORECASE,
        ),
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
        "external_or_endpoint_assignment",
        re.compile(
            r"\b(?:endpoint|provider|account|legal|company|patent|payment|money|publication|deploy|deployment)[_ -]?"
            r"(?:id|url|ref|target|value|status)?\s*=",
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
    ("checklist_complete", re.compile(r"\bchecklist\s+(?:is\s+)?complete\b", re.IGNORECASE)),
    ("review_scope_closed", re.compile(r"\breview[- ]scope\s+(?:is\s+)?closed\b", re.IGNORECASE)),
    ("validation_complete", re.compile(r"\bvalidation\s+(?:is\s+)?complete\b", re.IGNORECASE)),
    ("secret_clear", re.compile(r"\bsecrets?\s+(?:are\s+)?clear(?:ed)?\b", re.IGNORECASE)),
    ("staging_approved", re.compile(r"\bstaging\s+(?:is\s+)?approved\b", re.IGNORECASE)),
    ("commit_approved", re.compile(r"\bcommit\s+(?:is\s+)?approved\b", re.IGNORECASE)),
    ("push_approved", re.compile(r"\bpush\s+(?:is\s+)?approved\b", re.IGNORECASE)),
    ("pull_request_approved", re.compile(r"\bpull\s+request\s+(?:is\s+)?approved\b", re.IGNORECASE)),
    ("release_ready", re.compile(r"\brelease\s+(?:is\s+)?ready\b", re.IGNORECASE)),
    ("external_publication", re.compile(r"\bexternal\s+publication\s+(?:is\s+)?(?:allowed|approved)\b", re.IGNORECASE)),
    ("deployment_ready", re.compile(r"\bdeployment\s+(?:is\s+)?ready\b", re.IGNORECASE)),
    ("customer_access", re.compile(r"\bcustomer\s+access\s+(?:is\s+)?(?:allowed|approved)\b", re.IGNORECASE)),
    ("legal_clearance", re.compile(r"\blegal\s+clearance\s+(?:is\s+)?(?:complete|granted)\b", re.IGNORECASE)),
    ("company_formation", re.compile(r"\bcompany\s+formation\s+(?:is\s+)?complete\b", re.IGNORECASE)),
    ("patent_action", re.compile(r"\bpatent\s+(?:is\s+)?(?:filed|approved)\b", re.IGNORECASE)),
    ("money_movement", re.compile(r"\bmoney\s+movement\s+(?:is\s+)?approved\b", re.IGNORECASE)),
    ("secret_publication", re.compile(r"\bsecret\s+publication\s+(?:is\s+)?(?:allowed|approved)\b", re.IGNORECASE)),
    ("continue_authorized", re.compile(r"\bcontinue\s+(?:is\s+)?authorized\b", re.IGNORECASE)),
    ("broad_execution_allowed", re.compile(r"\bbroad\s+execution\s+(?:is\s+)?allowed\b", re.IGNORECASE)),
    ("external_action_approved", re.compile(r"\bexternal\s+action\s+(?:is\s+)?approved\b", re.IGNORECASE)),
    ("customer_action_open", re.compile(r"\bcustomer\s+action\s+(?:is\s+)?open\b", re.IGNORECASE)),
    ("legal_action_approved", re.compile(r"\blegal\s+action\s+(?:is\s+)?approved\b", re.IGNORECASE)),
    ("company_action_approved", re.compile(r"\bcompany\s+action\s+(?:is\s+)?approved\b", re.IGNORECASE)),
    ("payment_action_approved", re.compile(r"\bpayment\s+action\s+(?:is\s+)?approved\b", re.IGNORECASE)),
    ("spending_approved", re.compile(r"\bspending\s+(?:is\s+)?approved\b", re.IGNORECASE)),
    ("service_active", re.compile(r"\bservice\s+(?:is\s+)?active\b", re.IGNORECASE)),
    ("source_control_published", re.compile(r"\bsource\s+control\s+(?:is\s+)?published\b", re.IGNORECASE)),
    ("roadmap_committed", re.compile(r"\broadmap\s+(?:is\s+)?committed\b", re.IGNORECASE)),
    ("deadline_promised", re.compile(r"\bdeadline\s+(?:is\s+)?promised\b", re.IGNORECASE)),
)


@dataclass(frozen=True, slots=True)
class SourceControlReviewChecklistFinding:
    """One deterministic source-control review checklist validation finding."""

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


def validate_doc_text(text: str) -> list[SourceControlReviewChecklistFinding]:
    """Return findings for missing checklist documentation anchors."""

    findings: list[SourceControlReviewChecklistFinding] = []
    for phrase in REQUIRED_DOC_PHRASES:
        if phrase not in text:
            findings.append(
                SourceControlReviewChecklistFinding(
                    "foundation_source_control_review_checklist_doc_phrase_missing",
                    f"source-control review checklist doc missing required phrase: {phrase}",
                )
            )
    return findings


def validate_packet(payload: dict[str, Any]) -> list[SourceControlReviewChecklistFinding]:
    """Return findings for checklist witness drift."""

    findings: list[SourceControlReviewChecklistFinding] = []
    findings.extend(validate_root_contract(payload))
    findings.extend(validate_checklist_items(payload.get("checklist_items")))
    findings.extend(validate_forbidden_value_patterns(payload))
    findings.extend(validate_forbidden_promotion_patterns(payload))
    return findings


def validate_application(payload: dict[str, Any]) -> list[SourceControlReviewChecklistFinding]:
    """Return findings for current-packet checklist application drift."""

    findings: list[SourceControlReviewChecklistFinding] = []
    findings.extend(validate_application_root_contract(payload))
    findings.extend(validate_review_context(payload.get("review_context")))
    findings.extend(validate_observed_change_categories(payload.get("observed_change_categories")))
    findings.extend(validate_application_review_items(payload.get("review_items")))
    findings.extend(validate_forbidden_value_patterns(payload))
    findings.extend(validate_forbidden_promotion_patterns(payload))
    return findings


def validate_validation_receipt_application(payload: dict[str, Any]) -> list[SourceControlReviewChecklistFinding]:
    """Return findings for validation-receipt current-packet drift."""

    findings: list[SourceControlReviewChecklistFinding] = []
    findings.extend(validate_validation_receipt_root_contract(payload))
    findings.extend(validate_validation_receipt_categories(payload.get("application_categories")))
    findings.extend(validate_validation_receipt_items(payload.get("validation_items")))
    findings.extend(validate_forbidden_value_patterns(payload))
    findings.extend(validate_forbidden_promotion_patterns(payload))
    return findings


def validate_next_action_witness(payload: dict[str, Any]) -> list[SourceControlReviewChecklistFinding]:
    """Return findings for next-action witness drift."""

    findings: list[SourceControlReviewChecklistFinding] = []
    findings.extend(validate_next_action_root_contract(payload))
    findings.extend(validate_next_action_surfaces(payload.get("next_action_surfaces")))
    findings.extend(validate_forbidden_value_patterns(payload))
    findings.extend(validate_forbidden_promotion_patterns(payload))
    return findings


def validate_git_effect_application(payload: dict[str, Any]) -> list[SourceControlReviewChecklistFinding]:
    """Return findings for Git-effect stop-rule current-packet drift."""

    findings: list[SourceControlReviewChecklistFinding] = []
    findings.extend(validate_git_effect_root_contract(payload))
    findings.extend(validate_git_effect_categories(payload.get("effect_categories")))
    findings.extend(validate_git_effect_review_items(payload.get("review_items")))
    findings.extend(validate_forbidden_value_patterns(payload))
    findings.extend(validate_forbidden_promotion_patterns(payload))
    return findings


def validate_external_action_application(payload: dict[str, Any]) -> list[SourceControlReviewChecklistFinding]:
    """Return findings for external-action stop-rule current-packet drift."""

    findings: list[SourceControlReviewChecklistFinding] = []
    findings.extend(validate_external_action_root_contract(payload))
    findings.extend(validate_external_action_categories(payload.get("stop_rule_categories")))
    findings.extend(validate_external_action_review_items(payload.get("review_items")))
    findings.extend(validate_forbidden_value_patterns(payload))
    findings.extend(validate_forbidden_promotion_patterns(payload))
    return findings


def validate_dirty_worktree_application(payload: dict[str, Any]) -> list[SourceControlReviewChecklistFinding]:
    """Return findings for dirty-worktree snapshot application drift."""

    findings: list[SourceControlReviewChecklistFinding] = []
    findings.extend(validate_dirty_worktree_root_contract(payload))
    findings.extend(validate_dirty_worktree_categories(payload.get("snapshot_categories")))
    findings.extend(validate_dirty_worktree_review_items(payload.get("review_items")))
    findings.extend(validate_forbidden_value_patterns(payload))
    findings.extend(validate_forbidden_promotion_patterns(payload))
    return findings


def validate_line_ending_application(payload: dict[str, Any]) -> list[SourceControlReviewChecklistFinding]:
    """Return findings for line-ending warning application drift."""

    findings: list[SourceControlReviewChecklistFinding] = []
    findings.extend(validate_line_ending_root_contract(payload))
    findings.extend(validate_line_ending_categories(payload.get("warning_categories")))
    findings.extend(validate_line_ending_triage_items(payload.get("triage_items")))
    findings.extend(validate_forbidden_value_patterns(payload))
    findings.extend(validate_forbidden_promotion_patterns(payload))
    return findings


def validate_untracked_artifact_application(payload: dict[str, Any]) -> list[SourceControlReviewChecklistFinding]:
    """Return findings for untracked artifact application drift."""

    findings: list[SourceControlReviewChecklistFinding] = []
    findings.extend(validate_untracked_artifact_root_contract(payload))
    findings.extend(validate_untracked_artifact_categories(payload.get("artifact_categories")))
    findings.extend(validate_untracked_artifact_review_items(payload.get("review_items")))
    findings.extend(validate_forbidden_value_patterns(payload))
    findings.extend(validate_forbidden_promotion_patterns(payload))
    return findings


def validate_unrelated_work_application(payload: dict[str, Any]) -> list[SourceControlReviewChecklistFinding]:
    """Return findings for unrelated/prior work preservation application drift."""

    findings: list[SourceControlReviewChecklistFinding] = []
    findings.extend(validate_unrelated_work_root_contract(payload))
    findings.extend(validate_unrelated_work_categories(payload.get("unrelated_work_categories")))
    findings.extend(validate_unrelated_work_review_items(payload.get("review_items")))
    findings.extend(validate_forbidden_value_patterns(payload))
    findings.extend(validate_forbidden_promotion_patterns(payload))
    return findings


def validate_secrets_application(payload: dict[str, Any]) -> list[SourceControlReviewChecklistFinding]:
    """Return findings for secrets/private-value screening application drift."""

    findings: list[SourceControlReviewChecklistFinding] = []
    findings.extend(validate_secrets_root_contract(payload))
    findings.extend(validate_secrets_context(payload.get("screening_context")))
    findings.extend(validate_secrets_categories(payload.get("observed_screening_categories")))
    findings.extend(validate_secrets_screening_items(payload.get("screening_items")))
    findings.extend(validate_forbidden_value_patterns(payload))
    findings.extend(validate_forbidden_promotion_patterns(payload))
    return findings


def validate_runtime_safety_application(payload: dict[str, Any]) -> list[SourceControlReviewChecklistFinding]:
    """Return findings for runtime-safety packet application drift."""

    findings: list[SourceControlReviewChecklistFinding] = []
    findings.extend(validate_runtime_safety_root_contract(payload))
    findings.extend(validate_runtime_safety_categories(payload.get("packet_categories")))
    findings.extend(validate_runtime_safety_review_items(payload.get("review_items")))
    findings.extend(validate_forbidden_value_patterns(payload))
    findings.extend(validate_forbidden_promotion_patterns(payload))
    return findings


def validate_root_contract(payload: dict[str, Any]) -> list[SourceControlReviewChecklistFinding]:
    """Return findings for root-level checklist witness drift."""

    findings: list[SourceControlReviewChecklistFinding] = []
    if set(payload) != EXPECTED_ROOT_KEYS:
        findings.append(
            SourceControlReviewChecklistFinding(
                "source_control_review_checklist_root_keys_invalid",
                f"root keys must be: {', '.join(sorted(EXPECTED_ROOT_KEYS))}",
            )
        )
    expected_values = {
        "witness_id": EXPECTED_WITNESS_ID,
        "schema_version": 1,
        "status": "AwaitingEvidence",
        "solver_outcome": "AwaitingEvidence",
        "checklist_complete_claimed": False,
        "review_scope_closed_claimed": False,
        "validation_complete_claimed": False,
        "secret_clearance_claimed": False,
        "staging_allowed": False,
        "commit_allowed": False,
        "push_allowed": False,
        "pull_request_allowed": False,
        "release_allowed": False,
        "external_publication_allowed": False,
        "deployment_allowed": False,
        "customer_access_allowed": False,
        "legal_clearance_claimed": False,
        "company_formation_claimed": False,
        "patent_action_allowed": False,
        "money_action_allowed": False,
        "secret_publication_allowed": False,
    }
    for key, expected_value in expected_values.items():
        if payload.get(key) != expected_value:
            findings.append(
                SourceControlReviewChecklistFinding(
                    "source_control_review_checklist_root_value_invalid",
                    f"{key} must be {expected_value!r}",
                )
            )
    if tuple(payload.get("blocked_claims") or ()) != EXPECTED_BLOCKED_CLAIMS:
        findings.append(
            SourceControlReviewChecklistFinding(
                "source_control_review_checklist_blocked_claims_invalid",
                f"blocked_claims must be: {', '.join(EXPECTED_BLOCKED_CLAIMS)}",
            )
        )
    next_action = payload.get("next_action")
    if not isinstance(next_action, str) or "continue local source-control review checklist drafting" not in next_action:
        findings.append(
            SourceControlReviewChecklistFinding(
                "source_control_review_checklist_next_action_invalid",
                "next_action must preserve local checklist drafting without Git or external effect promotion",
            )
        )
    return findings


def validate_line_ending_root_contract(payload: dict[str, Any]) -> list[SourceControlReviewChecklistFinding]:
    """Return findings for line-ending warning application root drift."""

    findings: list[SourceControlReviewChecklistFinding] = []
    if set(payload) != EXPECTED_LINE_ENDING_ROOT_KEYS:
        findings.append(
            SourceControlReviewChecklistFinding(
                "source_control_review_checklist_line_ending_root_keys_invalid",
                f"line-ending application root keys must be: {', '.join(sorted(EXPECTED_LINE_ENDING_ROOT_KEYS))}",
            )
        )
    expected_values = {
        "application_id": EXPECTED_LINE_ENDING_APPLICATION_ID,
        "schema_version": 1,
        "status": "AwaitingEvidence",
        "solver_outcome": "AwaitingEvidence",
        "source_control_review_checklist_witness_ref": (
            "examples/foundation_source_control_review_checklist_witness.awaiting_evidence.json"
        ),
        "source_control_review_checklist_current_packet_ref": (
            "examples/foundation_source_control_review_checklist_current_packet.awaiting_evidence.json"
        ),
        "warning_presence_observed": True,
        "warning_count_recorded": False,
        "warning_text_recorded": False,
        "warning_hidden_claimed": False,
        "warning_resolution_claimed": False,
        "changed_file_list_recorded": False,
        "private_paths_recorded": False,
        "line_ending_normalization_allowed": False,
        "git_config_change_allowed": False,
        "file_rewrite_allowed": False,
        "staging_allowed": False,
        "commit_allowed": False,
        "push_allowed": False,
        "pull_request_allowed": False,
        "release_allowed": False,
        "external_publication_allowed": False,
        "deployment_allowed": False,
        "customer_access_allowed": False,
        "legal_clearance_claimed": False,
        "company_formation_claimed": False,
        "patent_action_allowed": False,
        "money_action_allowed": False,
        "secret_publication_allowed": False,
    }
    for key, expected_value in expected_values.items():
        if payload.get(key) != expected_value:
            findings.append(
                SourceControlReviewChecklistFinding(
                    "source_control_review_checklist_line_ending_root_value_invalid",
                    f"{key} must be {expected_value!r}",
                )
            )
    if tuple(payload.get("blocked_claims") or ()) != EXPECTED_LINE_ENDING_BLOCKED_CLAIMS:
        findings.append(
            SourceControlReviewChecklistFinding(
                "source_control_review_checklist_line_ending_blocked_claims_invalid",
                f"line-ending blocked_claims must be: {', '.join(EXPECTED_LINE_ENDING_BLOCKED_CLAIMS)}",
            )
        )
    next_action = payload.get("next_action")
    if not isinstance(next_action, str) or "continue local line-ending warning triage" not in next_action:
        findings.append(
            SourceControlReviewChecklistFinding(
                "source_control_review_checklist_line_ending_next_action_invalid",
                "line-ending next_action must preserve local warning triage without hiding warnings or authorizing Git effects",
            )
        )
    return findings


def validate_dirty_worktree_root_contract(payload: dict[str, Any]) -> list[SourceControlReviewChecklistFinding]:
    """Return findings for dirty-worktree snapshot application root drift."""

    findings: list[SourceControlReviewChecklistFinding] = []
    if set(payload) != EXPECTED_DIRTY_WORKTREE_ROOT_KEYS:
        findings.append(
            SourceControlReviewChecklistFinding(
                "source_control_review_checklist_dirty_worktree_root_keys_invalid",
                f"dirty-worktree root keys must be: {', '.join(sorted(EXPECTED_DIRTY_WORKTREE_ROOT_KEYS))}",
            )
        )
    expected_values = {
        "application_id": EXPECTED_DIRTY_WORKTREE_APPLICATION_ID,
        "schema_version": 1,
        "status": "AwaitingEvidence",
        "solver_outcome": "AwaitingEvidence",
        "source_control_review_checklist_current_packet_ref": (
            "examples/foundation_source_control_review_checklist_current_packet.awaiting_evidence.json"
        ),
        "source_control_review_checklist_witness_ref": (
            "examples/foundation_source_control_review_checklist_witness.awaiting_evidence.json"
        ),
        "dirty_state_observed": True,
        "clean_worktree_claimed": False,
        "status_output_recorded": False,
        "changed_file_count_recorded": False,
        "changed_file_list_recorded": False,
        "exact_diff_recorded": False,
        "private_paths_recorded": False,
        "branch_ref_recorded": False,
        "commit_ref_recorded": False,
        "pull_request_ref_recorded": False,
        "ownership_assigned": False,
        "staging_allowed": False,
        "commit_allowed": False,
        "push_allowed": False,
        "pull_request_allowed": False,
        "release_allowed": False,
        "external_publication_allowed": False,
        "deployment_allowed": False,
        "customer_access_allowed": False,
        "legal_clearance_claimed": False,
        "company_formation_claimed": False,
        "patent_action_allowed": False,
        "money_action_allowed": False,
        "secret_publication_allowed": False,
    }
    for key, expected_value in expected_values.items():
        if payload.get(key) != expected_value:
            findings.append(
                SourceControlReviewChecklistFinding(
                    "source_control_review_checklist_dirty_worktree_root_value_invalid",
                    f"{key} must be {expected_value!r}",
                )
            )
    if tuple(payload.get("blocked_claims") or ()) != EXPECTED_DIRTY_WORKTREE_BLOCKED_CLAIMS:
        findings.append(
            SourceControlReviewChecklistFinding(
                "source_control_review_checklist_dirty_worktree_blocked_claims_invalid",
                f"dirty-worktree blocked_claims must be: {', '.join(EXPECTED_DIRTY_WORKTREE_BLOCKED_CLAIMS)}",
            )
        )
    next_action = payload.get("next_action")
    if not isinstance(next_action, str) or "category-only evidence" not in next_action:
        findings.append(
            SourceControlReviewChecklistFinding(
                "source_control_review_checklist_dirty_worktree_next_action_invalid",
                "dirty-worktree next_action must preserve category-only evidence without Git or publication promotion",
            )
        )
    return findings


def validate_dirty_worktree_categories(categories: object) -> list[SourceControlReviewChecklistFinding]:
    """Return findings for dirty-worktree snapshot category drift."""

    if tuple(categories or ()) != EXPECTED_DIRTY_WORKTREE_CATEGORIES:
        return [
            SourceControlReviewChecklistFinding(
                "source_control_review_checklist_dirty_worktree_categories_invalid",
                "snapshot_categories must match the current public-safe dirty-worktree category set",
            )
        ]
    return []


def validate_dirty_worktree_review_items(review_items: object) -> list[SourceControlReviewChecklistFinding]:
    """Return findings for dirty-worktree snapshot review item drift."""

    findings: list[SourceControlReviewChecklistFinding] = []
    if not isinstance(review_items, list) or not all(isinstance(item, dict) for item in review_items):
        return [
            SourceControlReviewChecklistFinding(
                "source_control_review_checklist_dirty_worktree_items_invalid",
                "review_items must be a list of objects",
            )
        ]
    observed_items = tuple((item.get("review_id"), item.get("state")) for item in review_items)
    if observed_items != EXPECTED_DIRTY_WORKTREE_ITEMS:
        findings.append(
            SourceControlReviewChecklistFinding(
                "source_control_review_checklist_dirty_worktree_inventory_invalid",
                "dirty-worktree review item inventory does not match the expected snapshot set",
            )
        )
    review_ids = [item.get("review_id") for item in review_items]
    if len(set(review_ids)) != len(review_ids):
        findings.append(
            SourceControlReviewChecklistFinding(
                "source_control_review_checklist_dirty_worktree_duplicate",
                "dirty-worktree review ids must be unique",
            )
        )
    for item in review_items:
        review_id = str(item.get("review_id", "<missing>"))
        if set(item) != EXPECTED_DIRTY_WORKTREE_ITEM_KEYS:
            findings.append(
                SourceControlReviewChecklistFinding(
                    "source_control_review_checklist_dirty_worktree_item_keys_invalid",
                    f"{review_id} dirty-worktree item keys must be: {', '.join(sorted(EXPECTED_DIRTY_WORKTREE_ITEM_KEYS))}",
                )
            )
        if item.get("state") != "AwaitingEvidence":
            findings.append(
                SourceControlReviewChecklistFinding(
                    "source_control_review_checklist_dirty_worktree_item_state_invalid",
                    f"{review_id} dirty-worktree item state must be AwaitingEvidence",
                )
            )
        application_note = item.get("application_note")
        if not isinstance(application_note, str) or not application_note.strip():
            findings.append(
                SourceControlReviewChecklistFinding(
                    "source_control_review_checklist_dirty_worktree_note_invalid",
                    f"{review_id} application_note must be a non-empty string",
                )
            )
            continue
        missing_fragments = tuple(
            fragment
            for fragment in EXPECTED_DIRTY_WORKTREE_NOTE_FRAGMENTS.get(review_id, ())
            if fragment not in application_note
        )
        if missing_fragments:
            findings.append(
                SourceControlReviewChecklistFinding(
                    "source_control_review_checklist_dirty_worktree_note_fragment_missing",
                    f"{review_id} application_note missing required fragments: {', '.join(missing_fragments)}",
                )
            )
    return findings


def validate_line_ending_categories(categories: object) -> list[SourceControlReviewChecklistFinding]:
    """Return findings for line-ending warning category drift."""

    if tuple(categories or ()) != EXPECTED_LINE_ENDING_CATEGORIES:
        return [
            SourceControlReviewChecklistFinding(
                "source_control_review_checklist_line_ending_categories_invalid",
                "warning_categories must match the current public-safe line-ending warning category set",
            )
        ]
    return []


def validate_line_ending_triage_items(triage_items: object) -> list[SourceControlReviewChecklistFinding]:
    """Return findings for line-ending warning triage item drift."""

    findings: list[SourceControlReviewChecklistFinding] = []
    if not isinstance(triage_items, list) or not all(isinstance(item, dict) for item in triage_items):
        return [
            SourceControlReviewChecklistFinding(
                "source_control_review_checklist_line_ending_items_invalid",
                "triage_items must be a list of objects",
            )
        ]
    observed_items = tuple((item.get("triage_id"), item.get("state")) for item in triage_items)
    if observed_items != EXPECTED_LINE_ENDING_TRIAGE_ITEMS:
        findings.append(
            SourceControlReviewChecklistFinding(
                "source_control_review_checklist_line_ending_inventory_invalid",
                "line-ending triage item inventory does not match the expected warning triage set",
            )
        )
    triage_ids = [item.get("triage_id") for item in triage_items]
    if len(set(triage_ids)) != len(triage_ids):
        findings.append(
            SourceControlReviewChecklistFinding(
                "source_control_review_checklist_line_ending_duplicate",
                "line-ending triage ids must be unique",
            )
        )
    for item in triage_items:
        triage_id = str(item.get("triage_id", "<missing>"))
        if set(item) != EXPECTED_LINE_ENDING_TRIAGE_ITEM_KEYS:
            findings.append(
                SourceControlReviewChecklistFinding(
                    "source_control_review_checklist_line_ending_item_keys_invalid",
                    f"{triage_id} line-ending item keys must be: {', '.join(sorted(EXPECTED_LINE_ENDING_TRIAGE_ITEM_KEYS))}",
                )
            )
        if item.get("state") != "AwaitingEvidence":
            findings.append(
                SourceControlReviewChecklistFinding(
                    "source_control_review_checklist_line_ending_item_state_invalid",
                    f"{triage_id} line-ending item state must be AwaitingEvidence",
                )
            )
        application_note = item.get("application_note")
        if not isinstance(application_note, str) or not application_note.strip():
            findings.append(
                SourceControlReviewChecklistFinding(
                    "source_control_review_checklist_line_ending_note_invalid",
                    f"{triage_id} application_note must be a non-empty string",
                )
            )
            continue
        missing_fragments = tuple(
            fragment for fragment in EXPECTED_LINE_ENDING_NOTE_FRAGMENTS.get(triage_id, ()) if fragment not in application_note
        )
        if missing_fragments:
            findings.append(
                SourceControlReviewChecklistFinding(
                    "source_control_review_checklist_line_ending_note_fragment_missing",
                    f"{triage_id} application_note missing required fragments: {', '.join(missing_fragments)}",
                )
            )
    return findings


def validate_untracked_artifact_root_contract(payload: dict[str, Any]) -> list[SourceControlReviewChecklistFinding]:
    """Return findings for untracked artifact application root drift."""

    findings: list[SourceControlReviewChecklistFinding] = []
    if set(payload) != EXPECTED_UNTRACKED_ARTIFACT_ROOT_KEYS:
        findings.append(
            SourceControlReviewChecklistFinding(
                "source_control_review_checklist_untracked_artifact_root_keys_invalid",
                f"untracked artifact root keys must be: {', '.join(sorted(EXPECTED_UNTRACKED_ARTIFACT_ROOT_KEYS))}",
            )
        )
    expected_values = {
        "application_id": EXPECTED_UNTRACKED_ARTIFACT_APPLICATION_ID,
        "schema_version": 1,
        "status": "AwaitingEvidence",
        "solver_outcome": "AwaitingEvidence",
        "source_control_review_checklist_current_packet_ref": (
            "examples/foundation_source_control_review_checklist_current_packet.awaiting_evidence.json"
        ),
        "source_control_review_checklist_witness_ref": (
            "examples/foundation_source_control_review_checklist_witness.awaiting_evidence.json"
        ),
        "artifact_presence_observed": True,
        "artifact_count_recorded": False,
        "artifact_paths_recorded": False,
        "changed_file_list_recorded": False,
        "private_paths_recorded": False,
        "artifact_contents_recorded": False,
        "artifact_ownership_closed_claimed": False,
        "file_list_publication_allowed": False,
        "staging_allowed": False,
        "commit_allowed": False,
        "push_allowed": False,
        "pull_request_allowed": False,
        "release_allowed": False,
        "external_publication_allowed": False,
        "deployment_allowed": False,
        "customer_access_allowed": False,
        "legal_clearance_claimed": False,
        "company_formation_claimed": False,
        "patent_action_allowed": False,
        "money_action_allowed": False,
        "secret_publication_allowed": False,
    }
    for key, expected_value in expected_values.items():
        if payload.get(key) != expected_value:
            findings.append(
                SourceControlReviewChecklistFinding(
                    "source_control_review_checklist_untracked_artifact_root_value_invalid",
                    f"{key} must be {expected_value!r}",
                )
            )
    if tuple(payload.get("blocked_claims") or ()) != EXPECTED_UNTRACKED_ARTIFACT_BLOCKED_CLAIMS:
        findings.append(
            SourceControlReviewChecklistFinding(
                "source_control_review_checklist_untracked_artifact_blocked_claims_invalid",
                f"untracked artifact blocked_claims must be: {', '.join(EXPECTED_UNTRACKED_ARTIFACT_BLOCKED_CLAIMS)}",
            )
        )
    next_action = payload.get("next_action")
    if not isinstance(next_action, str) or "category-only evidence" not in next_action:
        findings.append(
            SourceControlReviewChecklistFinding(
                "source_control_review_checklist_untracked_artifact_next_action_invalid",
                "untracked artifact next_action must preserve category-only evidence without Git or publication promotion",
            )
        )
    return findings


def validate_untracked_artifact_categories(categories: object) -> list[SourceControlReviewChecklistFinding]:
    """Return findings for untracked artifact category drift."""

    if tuple(categories or ()) != EXPECTED_UNTRACKED_ARTIFACT_CATEGORIES:
        return [
            SourceControlReviewChecklistFinding(
                "source_control_review_checklist_untracked_artifact_categories_invalid",
                "artifact_categories must match the current public-safe untracked artifact category set",
            )
        ]
    return []


def validate_untracked_artifact_review_items(review_items: object) -> list[SourceControlReviewChecklistFinding]:
    """Return findings for untracked artifact review item drift."""

    findings: list[SourceControlReviewChecklistFinding] = []
    if not isinstance(review_items, list) or not all(isinstance(item, dict) for item in review_items):
        return [
            SourceControlReviewChecklistFinding(
                "source_control_review_checklist_untracked_artifact_items_invalid",
                "review_items must be a list of objects",
            )
        ]
    observed_items = tuple((item.get("review_id"), item.get("state")) for item in review_items)
    if observed_items != EXPECTED_UNTRACKED_ARTIFACT_ITEMS:
        findings.append(
            SourceControlReviewChecklistFinding(
                "source_control_review_checklist_untracked_artifact_inventory_invalid",
                "untracked artifact review item inventory does not match the expected review set",
            )
        )
    review_ids = [item.get("review_id") for item in review_items]
    if len(set(review_ids)) != len(review_ids):
        findings.append(
            SourceControlReviewChecklistFinding(
                "source_control_review_checklist_untracked_artifact_duplicate",
                "untracked artifact review ids must be unique",
            )
        )
    for item in review_items:
        review_id = str(item.get("review_id", "<missing>"))
        if set(item) != EXPECTED_UNTRACKED_ARTIFACT_ITEM_KEYS:
            findings.append(
                SourceControlReviewChecklistFinding(
                    "source_control_review_checklist_untracked_artifact_item_keys_invalid",
                    f"{review_id} untracked artifact item keys must be: {', '.join(sorted(EXPECTED_UNTRACKED_ARTIFACT_ITEM_KEYS))}",
                )
            )
        if item.get("state") != "AwaitingEvidence":
            findings.append(
                SourceControlReviewChecklistFinding(
                    "source_control_review_checklist_untracked_artifact_item_state_invalid",
                    f"{review_id} untracked artifact item state must be AwaitingEvidence",
                )
            )
        application_note = item.get("application_note")
        if not isinstance(application_note, str) or not application_note.strip():
            findings.append(
                SourceControlReviewChecklistFinding(
                    "source_control_review_checklist_untracked_artifact_note_invalid",
                    f"{review_id} application_note must be a non-empty string",
                )
            )
            continue
        missing_fragments = tuple(
            fragment
            for fragment in EXPECTED_UNTRACKED_ARTIFACT_NOTE_FRAGMENTS.get(review_id, ())
            if fragment not in application_note
        )
        if missing_fragments:
            findings.append(
                SourceControlReviewChecklistFinding(
                    "source_control_review_checklist_untracked_artifact_note_fragment_missing",
                    f"{review_id} application_note missing required fragments: {', '.join(missing_fragments)}",
                )
            )
    return findings


def validate_unrelated_work_root_contract(payload: dict[str, Any]) -> list[SourceControlReviewChecklistFinding]:
    """Return findings for unrelated/prior work preservation root drift."""

    findings: list[SourceControlReviewChecklistFinding] = []
    if set(payload) != EXPECTED_UNRELATED_WORK_ROOT_KEYS:
        findings.append(
            SourceControlReviewChecklistFinding(
                "source_control_review_checklist_unrelated_work_root_keys_invalid",
                f"unrelated work root keys must be: {', '.join(sorted(EXPECTED_UNRELATED_WORK_ROOT_KEYS))}",
            )
        )
    expected_values = {
        "application_id": EXPECTED_UNRELATED_WORK_APPLICATION_ID,
        "schema_version": 1,
        "status": "AwaitingEvidence",
        "solver_outcome": "AwaitingEvidence",
        "source_control_review_checklist_current_packet_ref": (
            "examples/foundation_source_control_review_checklist_current_packet.awaiting_evidence.json"
        ),
        "source_control_review_checklist_witness_ref": (
            "examples/foundation_source_control_review_checklist_witness.awaiting_evidence.json"
        ),
        "preservation_required": True,
        "unrelated_work_closure_claimed": False,
        "prior_work_closure_claimed": False,
        "ownership_assigned": False,
        "changed_file_list_recorded": False,
        "exact_diff_recorded": False,
        "private_paths_recorded": False,
        "diff_scope_closed_claimed": False,
        "user_change_overwrite_allowed": False,
        "reset_allowed": False,
        "checkout_allowed": False,
        "delete_allowed": False,
        "move_allowed": False,
        "revert_allowed": False,
        "staging_allowed": False,
        "commit_allowed": False,
        "push_allowed": False,
        "pull_request_allowed": False,
        "release_allowed": False,
        "external_publication_allowed": False,
        "deployment_allowed": False,
        "customer_access_allowed": False,
        "legal_clearance_claimed": False,
        "company_formation_claimed": False,
        "patent_action_allowed": False,
        "money_action_allowed": False,
        "secret_publication_allowed": False,
    }
    for key, expected_value in expected_values.items():
        if payload.get(key) != expected_value:
            findings.append(
                SourceControlReviewChecklistFinding(
                    "source_control_review_checklist_unrelated_work_root_value_invalid",
                    f"{key} must be {expected_value!r}",
                )
            )
    if tuple(payload.get("blocked_claims") or ()) != EXPECTED_UNRELATED_WORK_BLOCKED_CLAIMS:
        findings.append(
            SourceControlReviewChecklistFinding(
                "source_control_review_checklist_unrelated_work_blocked_claims_invalid",
                f"unrelated work blocked_claims must be: {', '.join(EXPECTED_UNRELATED_WORK_BLOCKED_CLAIMS)}",
            )
        )
    next_action = payload.get("next_action")
    if not isinstance(next_action, str) or "category-only evidence" not in next_action:
        findings.append(
            SourceControlReviewChecklistFinding(
                "source_control_review_checklist_unrelated_work_next_action_invalid",
                "unrelated work next_action must preserve category-only evidence without destructive Git or publication promotion",
            )
        )
    return findings


def validate_unrelated_work_categories(categories: object) -> list[SourceControlReviewChecklistFinding]:
    """Return findings for unrelated/prior work category drift."""

    if tuple(categories or ()) != EXPECTED_UNRELATED_WORK_CATEGORIES:
        return [
            SourceControlReviewChecklistFinding(
                "source_control_review_checklist_unrelated_work_categories_invalid",
                "unrelated_work_categories must match the current preservation category set",
            )
        ]
    return []


def validate_unrelated_work_review_items(review_items: object) -> list[SourceControlReviewChecklistFinding]:
    """Return findings for unrelated/prior work preservation item drift."""

    findings: list[SourceControlReviewChecklistFinding] = []
    if not isinstance(review_items, list) or not all(isinstance(item, dict) for item in review_items):
        return [
            SourceControlReviewChecklistFinding(
                "source_control_review_checklist_unrelated_work_items_invalid",
                "review_items must be a list of objects",
            )
        ]
    observed_items = tuple((item.get("review_id"), item.get("state")) for item in review_items)
    if observed_items != EXPECTED_UNRELATED_WORK_ITEMS:
        findings.append(
            SourceControlReviewChecklistFinding(
                "source_control_review_checklist_unrelated_work_inventory_invalid",
                "unrelated work review item inventory does not match the expected preservation set",
            )
        )
    review_ids = [item.get("review_id") for item in review_items]
    if len(set(review_ids)) != len(review_ids):
        findings.append(
            SourceControlReviewChecklistFinding(
                "source_control_review_checklist_unrelated_work_duplicate",
                "unrelated work review ids must be unique",
            )
        )
    for item in review_items:
        review_id = str(item.get("review_id", "<missing>"))
        if set(item) != EXPECTED_UNRELATED_WORK_ITEM_KEYS:
            findings.append(
                SourceControlReviewChecklistFinding(
                    "source_control_review_checklist_unrelated_work_item_keys_invalid",
                    f"{review_id} unrelated work item keys must be: {', '.join(sorted(EXPECTED_UNRELATED_WORK_ITEM_KEYS))}",
                )
            )
        if item.get("state") != "AwaitingEvidence":
            findings.append(
                SourceControlReviewChecklistFinding(
                    "source_control_review_checklist_unrelated_work_item_state_invalid",
                    f"{review_id} unrelated work item state must be AwaitingEvidence",
                )
            )
        application_note = item.get("application_note")
        if not isinstance(application_note, str) or not application_note.strip():
            findings.append(
                SourceControlReviewChecklistFinding(
                    "source_control_review_checklist_unrelated_work_note_invalid",
                    f"{review_id} application_note must be a non-empty string",
                )
            )
            continue
        missing_fragments = tuple(
            fragment
            for fragment in EXPECTED_UNRELATED_WORK_NOTE_FRAGMENTS.get(review_id, ())
            if fragment not in application_note
        )
        if missing_fragments:
            findings.append(
                SourceControlReviewChecklistFinding(
                    "source_control_review_checklist_unrelated_work_note_fragment_missing",
                    f"{review_id} application_note missing required fragments: {', '.join(missing_fragments)}",
                )
            )
    return findings


def validate_secrets_root_contract(payload: dict[str, Any]) -> list[SourceControlReviewChecklistFinding]:
    """Return findings for secrets/private-value screening packet root drift."""

    findings: list[SourceControlReviewChecklistFinding] = []
    if set(payload) != EXPECTED_SECRETS_ROOT_KEYS:
        findings.append(
            SourceControlReviewChecklistFinding(
                "source_control_review_checklist_secrets_root_keys_invalid",
                f"secrets root keys must be: {', '.join(sorted(EXPECTED_SECRETS_ROOT_KEYS))}",
            )
        )
    expected_values = {
        "application_id": EXPECTED_SECRETS_APPLICATION_ID,
        "schema_version": 1,
        "status": "AwaitingEvidence",
        "solver_outcome": "AwaitingEvidence",
        "source_witness_ref": "examples/foundation_secrets_credentials_witness.awaiting_evidence.json",
        "real_secret_storage_allowed": False,
        "credential_activation_allowed": False,
        "provider_account_binding_allowed": False,
        "api_key_creation_allowed": False,
        "oauth_app_creation_allowed": False,
        "service_account_creation_allowed": False,
        "env_file_commit_allowed": False,
        "private_key_storage_allowed": False,
        "secret_rotation_claimed": False,
        "secret_scan_pass_claimed": False,
        "external_call_allowed": False,
        "staging_allowed": False,
        "commit_allowed": False,
        "push_allowed": False,
        "pull_request_allowed": False,
        "external_publication_allowed": False,
        "deployment_allowed": False,
        "customer_access_allowed": False,
        "legal_clearance_claimed": False,
        "company_formation_claimed": False,
        "patent_action_allowed": False,
        "money_action_allowed": False,
    }
    for key, expected_value in expected_values.items():
        if payload.get(key) != expected_value:
            findings.append(
                SourceControlReviewChecklistFinding(
                    "source_control_review_checklist_secrets_root_value_invalid",
                    f"{key} must be {expected_value!r}",
                )
            )
    if tuple(payload.get("blocked_claims") or ()) != EXPECTED_SECRETS_BLOCKED_CLAIMS:
        findings.append(
            SourceControlReviewChecklistFinding(
                "source_control_review_checklist_secrets_blocked_claims_invalid",
                f"secrets blocked_claims must be: {', '.join(EXPECTED_SECRETS_BLOCKED_CLAIMS)}",
            )
        )
    next_action = payload.get("next_action")
    if not isinstance(next_action, str) or "category-only evidence" not in next_action:
        findings.append(
            SourceControlReviewChecklistFinding(
                "source_control_review_checklist_secrets_next_action_invalid",
                "secrets next_action must preserve category-only evidence without clearance or effect promotion",
            )
        )
    return findings


def validate_secrets_context(screening_context: object) -> list[SourceControlReviewChecklistFinding]:
    """Return findings for secrets/private-value screening context drift."""

    if not isinstance(screening_context, dict):
        return [
            SourceControlReviewChecklistFinding(
                "source_control_review_checklist_secrets_context_invalid",
                "screening_context must be an object",
            )
        ]
    findings: list[SourceControlReviewChecklistFinding] = []
    if set(screening_context) != EXPECTED_SECRETS_CONTEXT_KEYS:
        findings.append(
            SourceControlReviewChecklistFinding(
                "source_control_review_checklist_secrets_context_keys_invalid",
                f"screening_context keys must be: {', '.join(sorted(EXPECTED_SECRETS_CONTEXT_KEYS))}",
            )
        )
    expected_values = {
        "mode": "Foundation Mode",
        "scope": "current dirty worktree secret and private-value screening categories only",
        "changed_file_list_recorded": False,
        "private_values_recorded": False,
        "secret_value_recorded": False,
        "credential_value_recorded": False,
        "assigned_environment_value_recorded": False,
        "private_path_recorded": False,
        "account_identifier_recorded": False,
        "provider_binding_recorded": False,
        "saved_preflight_receipt_available": True,
        "receipt_is_terminal_closure_claimed": False,
    }
    for key, expected_value in expected_values.items():
        if screening_context.get(key) != expected_value:
            findings.append(
                SourceControlReviewChecklistFinding(
                    "source_control_review_checklist_secrets_context_value_invalid",
                    f"{key} must be {expected_value!r}",
                )
            )
    return findings


def validate_secrets_categories(categories: object) -> list[SourceControlReviewChecklistFinding]:
    """Return findings for secrets/private-value screening category drift."""

    if tuple(categories or ()) != EXPECTED_SECRETS_CATEGORIES:
        return [
            SourceControlReviewChecklistFinding(
                "source_control_review_checklist_secrets_categories_invalid",
                "observed_screening_categories must match the current category-only secrets screening set",
            )
        ]
    return []


def validate_secrets_screening_items(screening_items: object) -> list[SourceControlReviewChecklistFinding]:
    """Return findings for secrets/private-value screening item drift."""

    findings: list[SourceControlReviewChecklistFinding] = []
    if not isinstance(screening_items, list) or not all(isinstance(item, dict) for item in screening_items):
        return [
            SourceControlReviewChecklistFinding(
                "source_control_review_checklist_secrets_items_invalid",
                "screening_items must be a list of objects",
            )
        ]
    observed_items = tuple((item.get("surface_id"), item.get("state")) for item in screening_items)
    if observed_items != EXPECTED_SECRETS_ITEMS:
        findings.append(
            SourceControlReviewChecklistFinding(
                "source_control_review_checklist_secrets_inventory_invalid",
                "secrets screening item inventory does not match the expected packet set",
            )
        )
    surface_ids = [item.get("surface_id") for item in screening_items]
    if len(set(surface_ids)) != len(surface_ids):
        findings.append(
            SourceControlReviewChecklistFinding(
                "source_control_review_checklist_secrets_duplicate",
                "secrets screening surface ids must be unique",
            )
        )
    for item in screening_items:
        surface_id = str(item.get("surface_id", "<missing>"))
        if set(item) != EXPECTED_SECRETS_ITEM_KEYS:
            findings.append(
                SourceControlReviewChecklistFinding(
                    "source_control_review_checklist_secrets_item_keys_invalid",
                    f"{surface_id} secrets item keys must be: {', '.join(sorted(EXPECTED_SECRETS_ITEM_KEYS))}",
                )
            )
        if item.get("state") != "AwaitingEvidence":
            findings.append(
                SourceControlReviewChecklistFinding(
                    "source_control_review_checklist_secrets_item_state_invalid",
                    f"{surface_id} secrets item state must be AwaitingEvidence",
                )
            )
        application_note = item.get("application_note")
        if not isinstance(application_note, str) or not application_note.strip():
            findings.append(
                SourceControlReviewChecklistFinding(
                    "source_control_review_checklist_secrets_note_invalid",
                    f"{surface_id} application_note must be a non-empty string",
                )
            )
            continue
        missing_fragments = tuple(
            fragment
            for fragment in EXPECTED_SECRETS_NOTE_FRAGMENTS.get(surface_id, ())
            if fragment not in application_note
        )
        if missing_fragments:
            findings.append(
                SourceControlReviewChecklistFinding(
                    "source_control_review_checklist_secrets_note_fragment_missing",
                    f"{surface_id} application_note missing required fragments: {', '.join(missing_fragments)}",
                )
            )
    return findings


def validate_runtime_safety_root_contract(payload: dict[str, Any]) -> list[SourceControlReviewChecklistFinding]:
    """Return findings for runtime-safety packet root drift."""

    findings: list[SourceControlReviewChecklistFinding] = []
    if set(payload) != EXPECTED_RUNTIME_SAFETY_ROOT_KEYS:
        findings.append(
            SourceControlReviewChecklistFinding(
                "source_control_review_checklist_runtime_safety_root_keys_invalid",
                f"runtime safety root keys must be: {', '.join(sorted(EXPECTED_RUNTIME_SAFETY_ROOT_KEYS))}",
            )
        )
    expected_values = {
        "application_id": EXPECTED_RUNTIME_SAFETY_APPLICATION_ID,
        "schema_version": 1,
        "status": "AwaitingEvidence",
        "solver_outcome": "AwaitingEvidence",
        "source_control_review_checklist_current_packet_ref": (
            "examples/foundation_source_control_review_checklist_current_packet.awaiting_evidence.json"
        ),
        "source_control_review_checklist_witness_ref": (
            "examples/foundation_source_control_review_checklist_witness.awaiting_evidence.json"
        ),
        "runtime_safety_family_observed": True,
        "runtime_completion_claimed": False,
        "runtime_readiness_claimed": False,
        "adapter_authority_claimed": False,
        "provider_binding_claimed": False,
        "connector_use_claimed": False,
        "endpoint_target_recorded": False,
        "secret_use_claimed": False,
        "secret_value_recorded": False,
        "acceptance_test_harness_complete_claimed": False,
        "full_coverage_claimed": False,
        "review_scope_closed_claimed": False,
        "changed_file_list_recorded": False,
        "private_values_recorded": False,
        "staging_allowed": False,
        "commit_allowed": False,
        "push_allowed": False,
        "pull_request_allowed": False,
        "release_allowed": False,
        "external_publication_allowed": False,
        "deployment_allowed": False,
        "customer_access_allowed": False,
        "legal_clearance_claimed": False,
        "company_formation_claimed": False,
        "patent_action_allowed": False,
        "money_action_allowed": False,
        "secret_publication_allowed": False,
    }
    for key, expected_value in expected_values.items():
        if payload.get(key) != expected_value:
            findings.append(
                SourceControlReviewChecklistFinding(
                    "source_control_review_checklist_runtime_safety_root_value_invalid",
                    f"{key} must be {expected_value!r}",
                )
            )
    if tuple(payload.get("blocked_claims") or ()) != EXPECTED_RUNTIME_SAFETY_BLOCKED_CLAIMS:
        findings.append(
            SourceControlReviewChecklistFinding(
                "source_control_review_checklist_runtime_safety_blocked_claims_invalid",
                f"runtime safety blocked_claims must be: {', '.join(EXPECTED_RUNTIME_SAFETY_BLOCKED_CLAIMS)}",
            )
        )
    next_action = payload.get("next_action")
    if not isinstance(next_action, str) or "category-only evidence" not in next_action:
        findings.append(
            SourceControlReviewChecklistFinding(
                "source_control_review_checklist_runtime_safety_next_action_invalid",
                "runtime safety next_action must preserve category-only evidence without runtime, Git, or external promotion",
            )
        )
    return findings


def validate_runtime_safety_categories(categories: object) -> list[SourceControlReviewChecklistFinding]:
    """Return findings for runtime-safety packet category drift."""

    if tuple(categories or ()) != EXPECTED_RUNTIME_SAFETY_CATEGORIES:
        return [
            SourceControlReviewChecklistFinding(
                "source_control_review_checklist_runtime_safety_categories_invalid",
                "packet_categories must match the current public-safe runtime-safety category set",
            )
        ]
    return []


def validate_runtime_safety_review_items(review_items: object) -> list[SourceControlReviewChecklistFinding]:
    """Return findings for runtime-safety packet item drift."""

    findings: list[SourceControlReviewChecklistFinding] = []
    if not isinstance(review_items, list) or not all(isinstance(item, dict) for item in review_items):
        return [
            SourceControlReviewChecklistFinding(
                "source_control_review_checklist_runtime_safety_items_invalid",
                "review_items must be a list of objects",
            )
        ]
    observed_items = tuple((item.get("review_id"), item.get("state")) for item in review_items)
    if observed_items != EXPECTED_RUNTIME_SAFETY_ITEMS:
        findings.append(
            SourceControlReviewChecklistFinding(
                "source_control_review_checklist_runtime_safety_inventory_invalid",
                "runtime-safety review item inventory does not match the expected packet set",
            )
        )
    review_ids = [item.get("review_id") for item in review_items]
    if len(set(review_ids)) != len(review_ids):
        findings.append(
            SourceControlReviewChecklistFinding(
                "source_control_review_checklist_runtime_safety_duplicate",
                "runtime-safety review ids must be unique",
            )
        )
    for item in review_items:
        review_id = str(item.get("review_id", "<missing>"))
        if set(item) != EXPECTED_RUNTIME_SAFETY_ITEM_KEYS:
            findings.append(
                SourceControlReviewChecklistFinding(
                    "source_control_review_checklist_runtime_safety_item_keys_invalid",
                    f"{review_id} runtime-safety item keys must be: {', '.join(sorted(EXPECTED_RUNTIME_SAFETY_ITEM_KEYS))}",
                )
            )
        if item.get("state") != "AwaitingEvidence":
            findings.append(
                SourceControlReviewChecklistFinding(
                    "source_control_review_checklist_runtime_safety_item_state_invalid",
                    f"{review_id} runtime-safety item state must be AwaitingEvidence",
                )
            )
        application_note = item.get("application_note")
        if not isinstance(application_note, str) or not application_note.strip():
            findings.append(
                SourceControlReviewChecklistFinding(
                    "source_control_review_checklist_runtime_safety_note_invalid",
                    f"{review_id} application_note must be a non-empty string",
                )
            )
            continue
        missing_fragments = tuple(
            fragment
            for fragment in EXPECTED_RUNTIME_SAFETY_NOTE_FRAGMENTS.get(review_id, ())
            if fragment not in application_note
        )
        if missing_fragments:
            findings.append(
                SourceControlReviewChecklistFinding(
                    "source_control_review_checklist_runtime_safety_note_fragment_missing",
                    f"{review_id} application_note missing required fragments: {', '.join(missing_fragments)}",
                )
            )
    return findings


def validate_application_root_contract(payload: dict[str, Any]) -> list[SourceControlReviewChecklistFinding]:
    """Return findings for current-packet application root drift."""

    findings: list[SourceControlReviewChecklistFinding] = []
    if set(payload) != EXPECTED_APPLICATION_ROOT_KEYS:
        findings.append(
            SourceControlReviewChecklistFinding(
                "source_control_review_checklist_application_root_keys_invalid",
                f"application root keys must be: {', '.join(sorted(EXPECTED_APPLICATION_ROOT_KEYS))}",
            )
        )
    expected_values = {
        "application_id": EXPECTED_APPLICATION_ID,
        "schema_version": 1,
        "status": "AwaitingEvidence",
        "solver_outcome": "AwaitingEvidence",
        "source_control_review_checklist_witness_ref": (
            "examples/foundation_source_control_review_checklist_witness.awaiting_evidence.json"
        ),
        "checklist_complete_claimed": False,
        "review_scope_closed_claimed": False,
        "validation_complete_claimed": False,
        "secret_clearance_claimed": False,
        "staging_allowed": False,
        "commit_allowed": False,
        "push_allowed": False,
        "pull_request_allowed": False,
        "release_allowed": False,
        "external_publication_allowed": False,
        "deployment_allowed": False,
        "customer_access_allowed": False,
        "legal_clearance_claimed": False,
        "company_formation_claimed": False,
        "patent_action_allowed": False,
        "money_action_allowed": False,
        "secret_publication_allowed": False,
    }
    for key, expected_value in expected_values.items():
        if payload.get(key) != expected_value:
            findings.append(
                SourceControlReviewChecklistFinding(
                    "source_control_review_checklist_application_root_value_invalid",
                    f"{key} must be {expected_value!r}",
                )
            )
    if tuple(payload.get("blocked_claims") or ()) != EXPECTED_BLOCKED_CLAIMS:
        findings.append(
            SourceControlReviewChecklistFinding(
                "source_control_review_checklist_application_blocked_claims_invalid",
                f"application blocked_claims must be: {', '.join(EXPECTED_BLOCKED_CLAIMS)}",
            )
        )
    next_action = payload.get("next_action")
    if not isinstance(next_action, str) or "continue local packet review using public-safe categories" not in next_action:
        findings.append(
            SourceControlReviewChecklistFinding(
                "source_control_review_checklist_application_next_action_invalid",
                "application next_action must preserve local packet review without Git or external effect promotion",
            )
        )
    return findings


def validate_review_context(review_context: object) -> list[SourceControlReviewChecklistFinding]:
    """Return findings for current-packet review context drift."""

    if not isinstance(review_context, dict):
        return [
            SourceControlReviewChecklistFinding(
                "source_control_review_checklist_application_context_invalid",
                "review_context must be an object",
            )
        ]
    findings: list[SourceControlReviewChecklistFinding] = []
    if set(review_context) != EXPECTED_REVIEW_CONTEXT_KEYS:
        findings.append(
            SourceControlReviewChecklistFinding(
                "source_control_review_checklist_application_context_keys_invalid",
                f"review_context keys must be: {', '.join(sorted(EXPECTED_REVIEW_CONTEXT_KEYS))}",
            )
        )
    expected_values = {
        "mode": "Foundation Mode",
        "scope": "current dirty worktree packet categories only",
        "changed_file_list_recorded": False,
        "private_values_recorded": False,
        "branch_ref_recorded": False,
        "commit_ref_recorded": False,
        "pull_request_ref_recorded": False,
        "endpoint_target_recorded": False,
        "provider_id_recorded": False,
        "customer_identifier_recorded": False,
        "legal_conclusion_recorded": False,
        "company_filing_recorded": False,
        "patent_filing_recorded": False,
        "payment_detail_recorded": False,
        "secret_value_recorded": False,
        "saved_preflight_receipt_available": True,
        "receipt_is_terminal_closure_claimed": False,
    }
    for key, expected_value in expected_values.items():
        if review_context.get(key) != expected_value:
            findings.append(
                SourceControlReviewChecklistFinding(
                    "source_control_review_checklist_application_context_value_invalid",
                    f"{key} must be {expected_value!r}",
                )
            )
    return findings


def validate_observed_change_categories(categories: object) -> list[SourceControlReviewChecklistFinding]:
    """Return findings for current-packet category drift."""

    if tuple(categories or ()) != EXPECTED_OBSERVED_CHANGE_CATEGORIES:
        return [
            SourceControlReviewChecklistFinding(
                "source_control_review_checklist_application_categories_invalid",
                "observed_change_categories must match the current public-safe packet category set",
            )
        ]
    return []


def validate_application_review_items(review_items: object) -> list[SourceControlReviewChecklistFinding]:
    """Return findings for current-packet checklist application item drift."""

    findings: list[SourceControlReviewChecklistFinding] = []
    if not isinstance(review_items, list) or not all(isinstance(item, dict) for item in review_items):
        return [
            SourceControlReviewChecklistFinding(
                "source_control_review_checklist_application_items_invalid",
                "review_items must be a list of objects",
            )
        ]
    observed_items = tuple((item.get("checklist_id"), item.get("state")) for item in review_items)
    if observed_items != EXPECTED_APPLICATION_REVIEW_ITEMS:
        findings.append(
            SourceControlReviewChecklistFinding(
                "source_control_review_checklist_application_inventory_invalid",
                "application review item inventory does not match the checklist set",
            )
        )
    item_ids = [item.get("checklist_id") for item in review_items]
    if len(set(item_ids)) != len(item_ids):
        findings.append(
            SourceControlReviewChecklistFinding(
                "source_control_review_checklist_application_duplicate",
                "application review item ids must be unique",
            )
        )
    for item in review_items:
        checklist_id = str(item.get("checklist_id", "<missing>"))
        if set(item) != EXPECTED_APPLICATION_REVIEW_ITEM_KEYS:
            findings.append(
                SourceControlReviewChecklistFinding(
                    "source_control_review_checklist_application_item_keys_invalid",
                    f"{checklist_id} application item keys must be: {', '.join(sorted(EXPECTED_APPLICATION_REVIEW_ITEM_KEYS))}",
                )
            )
        if item.get("state") != "AwaitingEvidence":
            findings.append(
                SourceControlReviewChecklistFinding(
                    "source_control_review_checklist_application_item_state_invalid",
                    f"{checklist_id} application state must be AwaitingEvidence",
                )
            )
        application_note = item.get("application_note")
        if not isinstance(application_note, str) or not application_note.strip():
            findings.append(
                SourceControlReviewChecklistFinding(
                    "source_control_review_checklist_application_note_invalid",
                    f"{checklist_id} application_note must be a non-empty string",
                )
            )
            continue
        missing_fragments = tuple(
            fragment for fragment in EXPECTED_APPLICATION_NOTE_FRAGMENTS.get(checklist_id, ()) if fragment not in application_note
        )
        if missing_fragments:
            findings.append(
                SourceControlReviewChecklistFinding(
                    "source_control_review_checklist_application_note_fragment_missing",
                    f"{checklist_id} application_note missing required fragments: {', '.join(missing_fragments)}",
                )
            )
    return findings


def validate_validation_receipt_root_contract(payload: dict[str, Any]) -> list[SourceControlReviewChecklistFinding]:
    """Return findings for validation-receipt current-packet root drift."""

    findings: list[SourceControlReviewChecklistFinding] = []
    if set(payload) != EXPECTED_VALIDATION_RECEIPT_ROOT_KEYS:
        findings.append(
            SourceControlReviewChecklistFinding(
                "source_control_review_checklist_validation_receipt_root_keys_invalid",
                f"validation receipt root keys must be: {', '.join(sorted(EXPECTED_VALIDATION_RECEIPT_ROOT_KEYS))}",
            )
        )
    expected_values = {
        "application_id": EXPECTED_VALIDATION_RECEIPT_APPLICATION_ID,
        "schema_version": 1,
        "status": "AwaitingEvidence",
        "solver_outcome": "AwaitingEvidence",
        "source_test_evidence_witness_ref": "examples/foundation_test_evidence_witness.awaiting_evidence.json",
        "source_receipt_routing_ref": "examples/foundation_test_receipt_routing.awaiting_evidence.json",
        "saved_receipt_ref": ".tmp/workspace-governance-preflight-receipt.json",
        "validator_ref": "scripts/validate_workspace_governance_preflight_receipt.py",
        "receipt_presence_observed": True,
        "receipt_summary_recorded": False,
        "check_count_recorded": False,
        "failed_check_names_recorded": False,
        "check_stdout_recorded": False,
        "receipt_content_recorded": False,
        "generated_at_recorded": False,
        "freshness_claimed": False,
        "private_path_recorded": False,
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
        "staging_allowed": False,
        "commit_allowed": False,
        "push_allowed": False,
        "pull_request_allowed": False,
        "external_publication_allowed": False,
        "deployment_allowed": False,
    }
    for key, expected_value in expected_values.items():
        if payload.get(key) != expected_value:
            findings.append(
                SourceControlReviewChecklistFinding(
                    "source_control_review_checklist_validation_receipt_root_value_invalid",
                    f"{key} must be {expected_value!r}",
                )
            )
    if tuple(payload.get("blocked_claims") or ()) != EXPECTED_VALIDATION_RECEIPT_BLOCKED_CLAIMS:
        findings.append(
            SourceControlReviewChecklistFinding(
                "source_control_review_checklist_validation_receipt_blocked_claims_invalid",
                f"validation receipt blocked_claims must be: {', '.join(EXPECTED_VALIDATION_RECEIPT_BLOCKED_CLAIMS)}",
            )
        )
    next_action = payload.get("next_action")
    if not isinstance(next_action, str) or "category-only evidence" not in next_action:
        findings.append(
            SourceControlReviewChecklistFinding(
                "source_control_review_checklist_validation_receipt_next_action_invalid",
                "validation receipt next_action must preserve category-only evidence without terminal closure or effect promotion",
            )
        )
    return findings


def validate_validation_receipt_categories(categories: object) -> list[SourceControlReviewChecklistFinding]:
    """Return findings for validation-receipt current-packet category drift."""

    if tuple(categories or ()) != EXPECTED_VALIDATION_RECEIPT_CATEGORIES:
        return [
            SourceControlReviewChecklistFinding(
                "source_control_review_checklist_validation_receipt_categories_invalid",
                "application_categories must match the current category-only validation-receipt set",
            )
        ]
    return []


def validate_validation_receipt_items(validation_items: object) -> list[SourceControlReviewChecklistFinding]:
    """Return findings for validation-receipt current-packet item drift."""

    findings: list[SourceControlReviewChecklistFinding] = []
    if not isinstance(validation_items, list) or not all(isinstance(item, dict) for item in validation_items):
        return [
            SourceControlReviewChecklistFinding(
                "source_control_review_checklist_validation_receipt_items_invalid",
                "validation_items must be a list of objects",
            )
        ]
    observed_items = tuple((item.get("validation_id"), item.get("state")) for item in validation_items)
    if observed_items != EXPECTED_VALIDATION_RECEIPT_ITEMS:
        findings.append(
            SourceControlReviewChecklistFinding(
                "source_control_review_checklist_validation_receipt_inventory_invalid",
                "validation-receipt item inventory does not match the expected packet set",
            )
        )
    item_ids = [item.get("validation_id") for item in validation_items]
    if len(set(item_ids)) != len(item_ids):
        findings.append(
            SourceControlReviewChecklistFinding(
                "source_control_review_checklist_validation_receipt_duplicate",
                "validation-receipt item ids must be unique",
            )
        )
    for item in validation_items:
        validation_id = str(item.get("validation_id", "<missing>"))
        if set(item) != EXPECTED_VALIDATION_RECEIPT_ITEM_KEYS:
            findings.append(
                SourceControlReviewChecklistFinding(
                    "source_control_review_checklist_validation_receipt_item_keys_invalid",
                    f"{validation_id} validation-receipt item keys must be: {', '.join(sorted(EXPECTED_VALIDATION_RECEIPT_ITEM_KEYS))}",
                )
            )
        if item.get("state") != "AwaitingEvidence":
            findings.append(
                SourceControlReviewChecklistFinding(
                    "source_control_review_checklist_validation_receipt_item_state_invalid",
                    f"{validation_id} validation-receipt item state must be AwaitingEvidence",
                )
            )
        application_note = item.get("application_note")
        if not isinstance(application_note, str) or not application_note.strip():
            findings.append(
                SourceControlReviewChecklistFinding(
                    "source_control_review_checklist_validation_receipt_note_invalid",
                    f"{validation_id} application_note must be a non-empty string",
                )
            )
            continue
        missing_fragments = tuple(
            fragment
            for fragment in EXPECTED_VALIDATION_RECEIPT_NOTE_FRAGMENTS.get(validation_id, ())
            if fragment not in application_note
        )
        if missing_fragments:
            findings.append(
                SourceControlReviewChecklistFinding(
                    "source_control_review_checklist_validation_receipt_note_fragment_missing",
                    f"{validation_id} application_note missing required fragments: {', '.join(missing_fragments)}",
                )
            )
    return findings


def validate_next_action_root_contract(payload: dict[str, Any]) -> list[SourceControlReviewChecklistFinding]:
    """Return findings for next-action witness root drift."""

    findings: list[SourceControlReviewChecklistFinding] = []
    if set(payload) != EXPECTED_NEXT_ACTION_ROOT_KEYS:
        findings.append(
            SourceControlReviewChecklistFinding(
                "source_control_review_checklist_next_action_root_keys_invalid",
                f"next-action root keys must be: {', '.join(sorted(EXPECTED_NEXT_ACTION_ROOT_KEYS))}",
            )
        )
    expected_values = {
        "witness_id": EXPECTED_NEXT_ACTION_WITNESS_ID,
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
                SourceControlReviewChecklistFinding(
                    "source_control_review_checklist_next_action_root_value_invalid",
                    f"{key} must be {expected_value!r}",
                )
            )
    if tuple(payload.get("blocked_claims") or ()) != EXPECTED_NEXT_ACTION_BLOCKED_CLAIMS:
        findings.append(
            SourceControlReviewChecklistFinding(
                "source_control_review_checklist_next_action_blocked_claims_invalid",
                f"next-action blocked_claims must be: {', '.join(EXPECTED_NEXT_ACTION_BLOCKED_CLAIMS)}",
            )
        )
    next_action = payload.get("next_action")
    if not isinstance(next_action, str) or "choosing one local-safe prerequisite" not in next_action:
        findings.append(
            SourceControlReviewChecklistFinding(
                "source_control_review_checklist_next_action_next_action_invalid",
                "next-action next_action must preserve one local-safe prerequisite selection",
            )
        )
    return findings


def validate_next_action_surfaces(next_action_surfaces: object) -> list[SourceControlReviewChecklistFinding]:
    """Return findings for next-action witness surface drift."""

    findings: list[SourceControlReviewChecklistFinding] = []
    if not isinstance(next_action_surfaces, list) or not all(isinstance(surface, dict) for surface in next_action_surfaces):
        return [
            SourceControlReviewChecklistFinding(
                "source_control_review_checklist_next_action_surfaces_invalid",
                "next_action_surfaces must be a list of objects",
            )
        ]
    observed_surfaces = tuple(
        (surface.get("surface_id"), surface.get("surface_type"), surface.get("state"))
        for surface in next_action_surfaces
    )
    if observed_surfaces != EXPECTED_NEXT_ACTION_SURFACES:
        findings.append(
            SourceControlReviewChecklistFinding(
                "source_control_review_checklist_next_action_surface_inventory_invalid",
                "next-action surface inventory does not match the Foundation Mode continuation set",
            )
        )
    surface_ids = [surface.get("surface_id") for surface in next_action_surfaces]
    if len(set(surface_ids)) != len(surface_ids):
        findings.append(
            SourceControlReviewChecklistFinding(
                "source_control_review_checklist_next_action_surface_duplicate",
                "next-action surface ids must be unique",
            )
        )
    for surface in next_action_surfaces:
        surface_id = str(surface.get("surface_id", "<missing>"))
        if set(surface) != EXPECTED_NEXT_ACTION_SURFACE_KEYS:
            findings.append(
                SourceControlReviewChecklistFinding(
                    "source_control_review_checklist_next_action_surface_keys_invalid",
                    f"{surface_id} next-action surface keys must be: {', '.join(sorted(EXPECTED_NEXT_ACTION_SURFACE_KEYS))}",
                )
            )
        if surface.get("state") != "AwaitingEvidence":
            findings.append(
                SourceControlReviewChecklistFinding(
                    "source_control_review_checklist_next_action_surface_state_invalid",
                    f"{surface_id} next-action surface state must be AwaitingEvidence",
                )
            )
        if surface.get("evidence_ref") != "manual_preparation_pending":
            findings.append(
                SourceControlReviewChecklistFinding(
                    "source_control_review_checklist_next_action_surface_evidence_invalid",
                    f"{surface_id} evidence_ref must stay manual_preparation_pending in the witness",
                )
            )
        public_safe_note = surface.get("public_safe_note")
        if not isinstance(public_safe_note, str) or not public_safe_note.strip():
            findings.append(
                SourceControlReviewChecklistFinding(
                    "source_control_review_checklist_next_action_surface_note_invalid",
                    f"{surface_id} public_safe_note must be a non-empty string",
                )
            )
            continue
        missing_fragments = tuple(
            fragment
            for fragment in EXPECTED_NEXT_ACTION_NOTE_FRAGMENTS.get(surface_id, ())
            if fragment not in public_safe_note
        )
        if missing_fragments:
            findings.append(
                SourceControlReviewChecklistFinding(
                    "source_control_review_checklist_next_action_surface_note_fragment_missing",
                    f"{surface_id} public_safe_note missing required fragments: {', '.join(missing_fragments)}",
                )
            )
    return findings


def validate_git_effect_root_contract(payload: dict[str, Any]) -> list[SourceControlReviewChecklistFinding]:
    """Return findings for Git-effect stop-rule packet root drift."""

    findings: list[SourceControlReviewChecklistFinding] = []
    if set(payload) != EXPECTED_GIT_EFFECT_ROOT_KEYS:
        findings.append(
            SourceControlReviewChecklistFinding(
                "source_control_review_checklist_git_effect_root_keys_invalid",
                f"Git-effect root keys must be: {', '.join(sorted(EXPECTED_GIT_EFFECT_ROOT_KEYS))}",
            )
        )
    expected_values = {
        "application_id": EXPECTED_GIT_EFFECT_APPLICATION_ID,
        "schema_version": 1,
        "status": "AwaitingEvidence",
        "solver_outcome": "AwaitingEvidence",
        "source_control_boundary_ref": "examples/foundation_source_control_boundary.awaiting_commit.json",
        "source_control_review_checklist_current_packet_ref": (
            "examples/foundation_source_control_review_checklist_current_packet.awaiting_evidence.json"
        ),
        "source_control_review_checklist_witness_ref": (
            "examples/foundation_source_control_review_checklist_witness.awaiting_evidence.json"
        ),
        "approval_claimed": False,
        "staging_allowed": False,
        "commit_allowed": False,
        "push_allowed": False,
        "pull_request_allowed": False,
        "source_control_publication_allowed": False,
        "branch_switch_allowed": False,
        "tag_allowed": False,
        "release_allowed": False,
        "reset_allowed": False,
        "checkout_allowed": False,
        "revert_allowed": False,
        "git_config_change_allowed": False,
        "status_output_recorded": False,
        "changed_file_list_recorded": False,
        "exact_diff_recorded": False,
        "private_paths_recorded": False,
        "branch_ref_recorded": False,
        "commit_ref_recorded": False,
        "pull_request_ref_recorded": False,
    }
    for key, expected_value in expected_values.items():
        if payload.get(key) != expected_value:
            findings.append(
                SourceControlReviewChecklistFinding(
                    "source_control_review_checklist_git_effect_root_value_invalid",
                    f"{key} must be {expected_value!r}",
                )
            )
    if tuple(payload.get("blocked_claims") or ()) != EXPECTED_GIT_EFFECT_BLOCKED_CLAIMS:
        findings.append(
            SourceControlReviewChecklistFinding(
                "source_control_review_checklist_git_effect_blocked_claims_invalid",
                f"Git-effect blocked_claims must be: {', '.join(EXPECTED_GIT_EFFECT_BLOCKED_CLAIMS)}",
            )
        )
    next_action = payload.get("next_action")
    if not isinstance(next_action, str) or "category-only evidence" not in next_action:
        findings.append(
            SourceControlReviewChecklistFinding(
                "source_control_review_checklist_git_effect_next_action_invalid",
                "Git-effect next_action must preserve category-only evidence without approval or effect promotion",
            )
        )
    return findings


def validate_git_effect_categories(categories: object) -> list[SourceControlReviewChecklistFinding]:
    """Return findings for Git-effect stop-rule category drift."""

    if tuple(categories or ()) != EXPECTED_GIT_EFFECT_CATEGORIES:
        return [
            SourceControlReviewChecklistFinding(
                "source_control_review_checklist_git_effect_categories_invalid",
                "effect_categories must match the current Git-effect stop-rule category set",
            )
        ]
    return []


def validate_git_effect_review_items(review_items: object) -> list[SourceControlReviewChecklistFinding]:
    """Return findings for Git-effect stop-rule item drift."""

    findings: list[SourceControlReviewChecklistFinding] = []
    if not isinstance(review_items, list) or not all(isinstance(item, dict) for item in review_items):
        return [
            SourceControlReviewChecklistFinding(
                "source_control_review_checklist_git_effect_items_invalid",
                "review_items must be a list of objects",
            )
        ]
    observed_items = tuple((item.get("review_id"), item.get("state")) for item in review_items)
    if observed_items != EXPECTED_GIT_EFFECT_ITEMS:
        findings.append(
            SourceControlReviewChecklistFinding(
                "source_control_review_checklist_git_effect_inventory_invalid",
                "Git-effect review item inventory does not match the expected stop-rule set",
            )
        )
    review_ids = [item.get("review_id") for item in review_items]
    if len(set(review_ids)) != len(review_ids):
        findings.append(
            SourceControlReviewChecklistFinding(
                "source_control_review_checklist_git_effect_duplicate",
                "Git-effect review ids must be unique",
            )
        )
    for item in review_items:
        review_id = str(item.get("review_id", "<missing>"))
        if set(item) != EXPECTED_GIT_EFFECT_ITEM_KEYS:
            findings.append(
                SourceControlReviewChecklistFinding(
                    "source_control_review_checklist_git_effect_item_keys_invalid",
                    f"{review_id} Git-effect item keys must be: {', '.join(sorted(EXPECTED_GIT_EFFECT_ITEM_KEYS))}",
                )
            )
        if item.get("state") != "AwaitingEvidence":
            findings.append(
                SourceControlReviewChecklistFinding(
                    "source_control_review_checklist_git_effect_item_state_invalid",
                    f"{review_id} Git-effect item state must be AwaitingEvidence",
                )
            )
        application_note = item.get("application_note")
        if not isinstance(application_note, str) or not application_note.strip():
            findings.append(
                SourceControlReviewChecklistFinding(
                    "source_control_review_checklist_git_effect_note_invalid",
                    f"{review_id} application_note must be a non-empty string",
                )
            )
            continue
        missing_fragments = tuple(
            fragment
            for fragment in EXPECTED_GIT_EFFECT_NOTE_FRAGMENTS.get(review_id, ())
            if fragment not in application_note
        )
        if missing_fragments:
            findings.append(
                SourceControlReviewChecklistFinding(
                    "source_control_review_checklist_git_effect_note_fragment_missing",
                    f"{review_id} application_note missing required fragments: {', '.join(missing_fragments)}",
                )
            )
    return findings


def validate_external_action_root_contract(payload: dict[str, Any]) -> list[SourceControlReviewChecklistFinding]:
    """Return findings for external-action stop-rule packet root drift."""

    findings: list[SourceControlReviewChecklistFinding] = []
    if set(payload) != EXPECTED_EXTERNAL_ACTION_ROOT_KEYS:
        findings.append(
            SourceControlReviewChecklistFinding(
                "source_control_review_checklist_external_action_root_keys_invalid",
                f"external-action root keys must be: {', '.join(sorted(EXPECTED_EXTERNAL_ACTION_ROOT_KEYS))}",
            )
        )
    expected_values = {
        "application_id": EXPECTED_EXTERNAL_ACTION_APPLICATION_ID,
        "schema_version": 1,
        "status": "AwaitingEvidence",
        "solver_outcome": "AwaitingEvidence",
        "source_control_review_checklist_current_packet_ref": (
            "examples/foundation_source_control_review_checklist_current_packet.awaiting_evidence.json"
        ),
        "source_control_review_checklist_witness_ref": (
            "examples/foundation_source_control_review_checklist_witness.awaiting_evidence.json"
        ),
        "external_action_allowed": False,
        "external_publication_allowed": False,
        "deployment_allowed": False,
        "deployment_readiness_claimed": False,
        "customer_access_allowed": False,
        "customer_action_allowed": False,
        "customer_identifier_recorded": False,
        "legal_clearance_claimed": False,
        "legal_action_allowed": False,
        "legal_conclusion_recorded": False,
        "company_formation_claimed": False,
        "company_action_allowed": False,
        "company_filing_recorded": False,
        "patent_action_allowed": False,
        "patent_filing_recorded": False,
        "money_action_allowed": False,
        "payment_detail_recorded": False,
        "secret_publication_allowed": False,
        "secret_value_recorded": False,
        "external_account_activation_allowed": False,
        "service_activation_allowed": False,
        "provider_binding_allowed": False,
        "provider_id_recorded": False,
        "endpoint_target_recorded": False,
        "personal_data_collection_allowed": False,
    }
    for key, expected_value in expected_values.items():
        if payload.get(key) != expected_value:
            findings.append(
                SourceControlReviewChecklistFinding(
                    "source_control_review_checklist_external_action_root_value_invalid",
                    f"{key} must be {expected_value!r}",
                )
            )
    if tuple(payload.get("blocked_claims") or ()) != EXPECTED_EXTERNAL_ACTION_BLOCKED_CLAIMS:
        findings.append(
            SourceControlReviewChecklistFinding(
                "source_control_review_checklist_external_action_blocked_claims_invalid",
                f"external-action blocked_claims must be: {', '.join(EXPECTED_EXTERNAL_ACTION_BLOCKED_CLAIMS)}",
            )
        )
    next_action = payload.get("next_action")
    if not isinstance(next_action, str) or "category-only evidence" not in next_action:
        findings.append(
            SourceControlReviewChecklistFinding(
                "source_control_review_checklist_external_action_next_action_invalid",
                "external-action next_action must preserve category-only evidence without approval or readiness promotion",
            )
        )
    return findings


def validate_external_action_categories(categories: object) -> list[SourceControlReviewChecklistFinding]:
    """Return findings for external-action stop-rule category drift."""

    if tuple(categories or ()) != EXPECTED_EXTERNAL_ACTION_CATEGORIES:
        return [
            SourceControlReviewChecklistFinding(
                "source_control_review_checklist_external_action_categories_invalid",
                "stop_rule_categories must match the current external-action stop-rule category set",
            )
        ]
    return []


def validate_external_action_review_items(review_items: object) -> list[SourceControlReviewChecklistFinding]:
    """Return findings for external-action stop-rule item drift."""

    findings: list[SourceControlReviewChecklistFinding] = []
    if not isinstance(review_items, list) or not all(isinstance(item, dict) for item in review_items):
        return [
            SourceControlReviewChecklistFinding(
                "source_control_review_checklist_external_action_items_invalid",
                "review_items must be a list of objects",
            )
        ]
    observed_items = tuple((item.get("review_id"), item.get("state")) for item in review_items)
    if observed_items != EXPECTED_EXTERNAL_ACTION_ITEMS:
        findings.append(
            SourceControlReviewChecklistFinding(
                "source_control_review_checklist_external_action_inventory_invalid",
                "external-action review item inventory does not match the expected stop-rule set",
            )
        )
    review_ids = [item.get("review_id") for item in review_items]
    if len(set(review_ids)) != len(review_ids):
        findings.append(
            SourceControlReviewChecklistFinding(
                "source_control_review_checklist_external_action_duplicate",
                "external-action review ids must be unique",
            )
        )
    for item in review_items:
        review_id = str(item.get("review_id", "<missing>"))
        if set(item) != EXPECTED_EXTERNAL_ACTION_ITEM_KEYS:
            findings.append(
                SourceControlReviewChecklistFinding(
                    "source_control_review_checklist_external_action_item_keys_invalid",
                    f"{review_id} external-action item keys must be: {', '.join(sorted(EXPECTED_EXTERNAL_ACTION_ITEM_KEYS))}",
                )
            )
        if item.get("state") != "AwaitingEvidence":
            findings.append(
                SourceControlReviewChecklistFinding(
                    "source_control_review_checklist_external_action_item_state_invalid",
                    f"{review_id} external-action item state must be AwaitingEvidence",
                )
            )
        application_note = item.get("application_note")
        if not isinstance(application_note, str) or not application_note.strip():
            findings.append(
                SourceControlReviewChecklistFinding(
                    "source_control_review_checklist_external_action_note_invalid",
                    f"{review_id} application_note must be a non-empty string",
                )
            )
            continue
        missing_fragments = tuple(
            fragment
            for fragment in EXPECTED_EXTERNAL_ACTION_NOTE_FRAGMENTS.get(review_id, ())
            if fragment not in application_note
        )
        if missing_fragments:
            findings.append(
                SourceControlReviewChecklistFinding(
                    "source_control_review_checklist_external_action_note_fragment_missing",
                    f"{review_id} application_note missing required fragments: {', '.join(missing_fragments)}",
                )
            )
    return findings


def validate_checklist_items(checklist_items: object) -> list[SourceControlReviewChecklistFinding]:
    """Return findings for checklist item drift."""

    findings: list[SourceControlReviewChecklistFinding] = []
    if not isinstance(checklist_items, list) or not all(isinstance(item, dict) for item in checklist_items):
        return [
            SourceControlReviewChecklistFinding(
                "source_control_review_checklist_items_invalid",
                "checklist_items must be a list of objects",
            )
        ]
    observed_items = tuple(
        (item.get("checklist_id"), item.get("checklist_type"), item.get("state"))
        for item in checklist_items
    )
    if observed_items != EXPECTED_CHECKLIST_ITEMS:
        findings.append(
            SourceControlReviewChecklistFinding(
                "source_control_review_checklist_inventory_invalid",
                "checklist item inventory does not match the Foundation Mode source-control review checklist set",
            )
        )
    item_ids = [item.get("checklist_id") for item in checklist_items]
    if len(set(item_ids)) != len(item_ids):
        findings.append(SourceControlReviewChecklistFinding("source_control_review_checklist_duplicate", "checklist ids must be unique"))
    for item in checklist_items:
        checklist_id = str(item.get("checklist_id", "<missing>"))
        if set(item) != EXPECTED_CHECKLIST_ITEM_KEYS:
            findings.append(
                SourceControlReviewChecklistFinding(
                    "source_control_review_checklist_item_keys_invalid",
                    f"{checklist_id} item keys must be: {', '.join(sorted(EXPECTED_CHECKLIST_ITEM_KEYS))}",
                )
            )
        if item.get("state") != "AwaitingEvidence":
            findings.append(
                SourceControlReviewChecklistFinding(
                    "source_control_review_checklist_item_state_invalid",
                    f"{checklist_id} state must be AwaitingEvidence",
                )
            )
        if item.get("evidence_ref") != "manual_review_pending":
            findings.append(
                SourceControlReviewChecklistFinding(
                    "source_control_review_checklist_item_evidence_invalid",
                    f"{checklist_id} evidence_ref must stay manual_review_pending in the committed packet",
                )
            )
        public_safe_question = item.get("public_safe_question")
        if not isinstance(public_safe_question, str) or not public_safe_question.strip():
            findings.append(
                SourceControlReviewChecklistFinding(
                    "source_control_review_checklist_item_question_invalid",
                    f"{checklist_id} public_safe_question must be a non-empty string",
                )
            )
            continue
        missing_fragments = tuple(
            fragment for fragment in EXPECTED_CHECKLIST_NOTE_FRAGMENTS.get(checklist_id, ()) if fragment not in public_safe_question
        )
        if missing_fragments:
            findings.append(
                SourceControlReviewChecklistFinding(
                    "source_control_review_checklist_item_question_fragment_missing",
                    f"{checklist_id} public_safe_question missing required fragments: {', '.join(missing_fragments)}",
                )
            )
    return findings


def validate_forbidden_value_patterns(payload: dict[str, Any]) -> list[SourceControlReviewChecklistFinding]:
    """Return findings for private, source-control, customer, external, or secret values."""

    serialized_payload = json.dumps(payload, sort_keys=True)
    findings: list[SourceControlReviewChecklistFinding] = []
    for rule_id, pattern in FORBIDDEN_VALUE_PATTERNS:
        if pattern.search(serialized_payload):
            findings.append(
                SourceControlReviewChecklistFinding(
                    "source_control_review_checklist_forbidden_private_value_pattern",
                    f"source-control review checklist witness contains forbidden value pattern: {rule_id}",
                )
            )
    return findings


def validate_forbidden_promotion_patterns(payload: dict[str, Any]) -> list[SourceControlReviewChecklistFinding]:
    """Return findings if the witness drifts into effect promotion phrases."""

    serialized_payload = json.dumps(payload, sort_keys=True)
    findings: list[SourceControlReviewChecklistFinding] = []
    for rule_id, pattern in FORBIDDEN_PROMOTION_PATTERNS:
        if pattern.search(serialized_payload):
            findings.append(
                SourceControlReviewChecklistFinding(
                    "source_control_review_checklist_forbidden_promotion_phrase",
                    f"source-control review checklist witness contains forbidden promotion pattern: {rule_id}",
                )
            )
    return findings


def validate_foundation_source_control_review_checklist_boundary(
    doc_path: Path = DEFAULT_DOC_PATH,
    packet_path: Path = DEFAULT_PACKET_PATH,
    application_path: Path = DEFAULT_APPLICATION_PATH,
    validation_receipt_application_path: Path = DEFAULT_VALIDATION_RECEIPT_APPLICATION_PATH,
    next_action_witness_path: Path = DEFAULT_NEXT_ACTION_WITNESS_PATH,
    git_effect_application_path: Path = DEFAULT_GIT_EFFECT_APPLICATION_PATH,
    external_action_application_path: Path = DEFAULT_EXTERNAL_ACTION_APPLICATION_PATH,
    dirty_worktree_application_path: Path = DEFAULT_DIRTY_WORKTREE_APPLICATION_PATH,
    line_ending_application_path: Path = DEFAULT_LINE_ENDING_APPLICATION_PATH,
    untracked_artifact_application_path: Path = DEFAULT_UNTRACKED_ARTIFACT_APPLICATION_PATH,
    unrelated_work_application_path: Path = DEFAULT_UNRELATED_WORK_APPLICATION_PATH,
    secrets_application_path: Path = DEFAULT_SECRETS_APPLICATION_PATH,
    runtime_safety_application_path: Path = DEFAULT_RUNTIME_SAFETY_APPLICATION_PATH,
) -> list[SourceControlReviewChecklistFinding]:
    """Validate the Foundation Mode source-control review checklist artifacts."""

    doc_text = load_text(doc_path, "source-control review checklist doc")
    packet_payload = load_json_object(packet_path, "source-control review checklist witness")
    application_payload = load_json_object(application_path, "source-control review checklist current-packet application")
    validation_receipt_payload = load_json_object(
        validation_receipt_application_path,
        "source-control review checklist validation-receipt current-packet application",
    )
    next_action_payload = load_json_object(
        next_action_witness_path,
        "source-control review checklist next-action witness",
    )
    git_effect_payload = load_json_object(
        git_effect_application_path,
        "source-control review checklist Git-effect stop-rule application",
    )
    external_action_payload = load_json_object(
        external_action_application_path,
        "source-control review checklist external-action stop-rule application",
    )
    dirty_worktree_payload = load_json_object(
        dirty_worktree_application_path,
        "source-control review checklist dirty-worktree snapshot application",
    )
    line_ending_payload = load_json_object(
        line_ending_application_path,
        "source-control review checklist line-ending warning application",
    )
    untracked_artifact_payload = load_json_object(
        untracked_artifact_application_path,
        "source-control review checklist untracked artifact application",
    )
    unrelated_work_payload = load_json_object(
        unrelated_work_application_path,
        "source-control review checklist unrelated work preservation application",
    )
    secrets_payload = load_json_object(
        secrets_application_path,
        "source-control review checklist secrets/private-value screening application",
    )
    runtime_safety_payload = load_json_object(
        runtime_safety_application_path,
        "source-control review checklist runtime-safety packet application",
    )
    return [
        *validate_doc_text(doc_text),
        *validate_packet(packet_payload),
        *validate_application(application_payload),
        *validate_validation_receipt_application(validation_receipt_payload),
        *validate_next_action_witness(next_action_payload),
        *validate_git_effect_application(git_effect_payload),
        *validate_external_action_application(external_action_payload),
        *validate_dirty_worktree_application(dirty_worktree_payload),
        *validate_line_ending_application(line_ending_payload),
        *validate_untracked_artifact_application(untracked_artifact_payload),
        *validate_unrelated_work_application(unrelated_work_payload),
        *validate_secrets_application(secrets_payload),
        *validate_runtime_safety_application(runtime_safety_payload),
    ]


def main(argv: list[str] | None = None) -> int:
    """Validate source-control review checklist artifacts and print deterministic status."""

    parser = argparse.ArgumentParser(description="Validate Foundation Mode source-control review checklist artifacts.")
    parser.add_argument("--doc", type=Path, default=DEFAULT_DOC_PATH)
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET_PATH)
    parser.add_argument("--application", type=Path, default=DEFAULT_APPLICATION_PATH)
    parser.add_argument("--validation-receipt-application", type=Path, default=DEFAULT_VALIDATION_RECEIPT_APPLICATION_PATH)
    parser.add_argument("--next-action-witness", type=Path, default=DEFAULT_NEXT_ACTION_WITNESS_PATH)
    parser.add_argument("--git-effect-application", type=Path, default=DEFAULT_GIT_EFFECT_APPLICATION_PATH)
    parser.add_argument("--external-action-application", type=Path, default=DEFAULT_EXTERNAL_ACTION_APPLICATION_PATH)
    parser.add_argument("--dirty-worktree-application", type=Path, default=DEFAULT_DIRTY_WORKTREE_APPLICATION_PATH)
    parser.add_argument("--line-ending-application", type=Path, default=DEFAULT_LINE_ENDING_APPLICATION_PATH)
    parser.add_argument("--untracked-artifact-application", type=Path, default=DEFAULT_UNTRACKED_ARTIFACT_APPLICATION_PATH)
    parser.add_argument("--unrelated-work-application", type=Path, default=DEFAULT_UNRELATED_WORK_APPLICATION_PATH)
    parser.add_argument("--secrets-application", type=Path, default=DEFAULT_SECRETS_APPLICATION_PATH)
    parser.add_argument("--runtime-safety-application", type=Path, default=DEFAULT_RUNTIME_SAFETY_APPLICATION_PATH)
    args = parser.parse_args(argv)

    try:
        findings = validate_foundation_source_control_review_checklist_boundary(
            args.doc,
            args.packet,
            args.application,
            args.validation_receipt_application,
            args.next_action_witness,
            args.git_effect_application,
            args.external_action_application,
            args.dirty_worktree_application,
            args.line_ending_application,
            args.untracked_artifact_application,
            args.unrelated_work_application,
            args.secrets_application,
            args.runtime_safety_application,
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"[FAIL] foundation_source_control_review_checklist_load: {exc}", file=sys.stderr)
        print("STATUS: failed", file=sys.stderr)
        return 1

    if findings:
        for finding in findings:
            print(f"[FAIL] {finding.rule_id}: {finding.message}", file=sys.stderr)
        print("STATUS: failed", file=sys.stderr)
        return 1
    print("[PASS] foundation_source_control_review_checklist_doc")
    print("[PASS] foundation_source_control_review_checklist_witness")
    print("[PASS] foundation_source_control_review_checklist_current_packet")
    print("[PASS] foundation_source_control_review_checklist_validation_receipt")
    print("[PASS] foundation_source_control_review_checklist_next_action")
    print("[PASS] foundation_source_control_review_checklist_git_effect")
    print("[PASS] foundation_source_control_review_checklist_external_action")
    print("[PASS] foundation_source_control_review_checklist_dirty_worktree")
    print("[PASS] foundation_source_control_review_checklist_line_ending_warning")
    print("[PASS] foundation_source_control_review_checklist_untracked_artifact")
    print("[PASS] foundation_source_control_review_checklist_unrelated_work")
    print("[PASS] foundation_source_control_review_checklist_secrets_screening")
    print("[PASS] foundation_source_control_review_checklist_runtime_safety")
    print("STATUS: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
