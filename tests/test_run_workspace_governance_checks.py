"""Purpose: verify repository-local workspace governance preflight orchestration.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, PRS]
Dependencies: scripts.run_workspace_governance_checks.
Invariants:
  - Check names are stable and map to repository-local scripts.
  - Result receipts derive status from return codes.
  - Saved canonical receipts require a full unsharded preflight.
  - Receipt writes cannot escape the workspace root.
"""

from __future__ import annotations

import ast
import io
import json
import re
import sys
from pathlib import Path

import pytest

from scripts import run_workspace_governance_checks as runner


def _foundation_boundary_validator_scripts() -> tuple[Path, ...]:
    return tuple(sorted((runner.WORKSPACE_ROOT / "scripts").glob("validate_foundation_*_boundary.py")))


def _foundation_boundary_docs() -> tuple[Path, ...]:
    return tuple(sorted((runner.WORKSPACE_ROOT / "docs").glob("FOUNDATION_*BOUNDARY.md")))


def _foundation_boundary_test_files() -> tuple[Path, ...]:
    return tuple(sorted((runner.WORKSPACE_ROOT / "tests").glob("test_validate_foundation_*_boundary.py")))


def _ci_workflow_text() -> str:
    return (runner.WORKSPACE_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")


def _module_docstring(module_path: Path) -> str:
    return ast.get_docstring(ast.parse(module_path.read_text(encoding="utf-8-sig")), clean=False) or ""


def test_build_check_commands_are_ordered_and_repo_local() -> None:
    commands = runner.build_check_commands("python-test")
    names = [command.name for command in commands]
    args_by_name = {command.name: command.args for command in commands}
    foundation_start = names.index("foundation_mode")
    protocol_index = names.index("protocol_manifest")
    foundation_phase = names[foundation_start:protocol_index]
    expected_foundation_names = {
        "agentic_service_harness_contract",
        "agentic_service_harness_read_models",
        "agentic_service_harness_read_model_projections",
        "agentic_service_harness_read_model_integrity",
        "agentic_service_harness_read_model_persistence",
        "agentic_service_harness_read_model_binding_plan",
        "agentic_service_harness_github_repo_task_service",
        "agentic_service_harness_github_repo_task_intake",
        "agentic_service_harness_dashboard_data_contract",
        "agentic_service_harness_adapter_registry_contract",
        "agentic_service_harness_evidence_bundle_projection",
        "agentic_service_harness_receipt_evidence_read_models",
        "agentic_service_harness_loopstatus_projection",
        "agentic_service_harness_receipt_projection",
        "agentic_service_harness_task_creation_admission_preflight",
        "agentic_service_harness_github_task_receipt_emitter_dry_run",
        "agentic_service_harness_temporary_branch_workspace_preflight",
        "agentic_service_harness_workspace_sandbox_preflight",
        "agentic_service_harness_approved_branch_workspace_creation_preflight",
        "agentic_service_harness_approved_branch_workspace_creation_authority_binding",
        "agentic_service_harness_approved_branch_workspace_creation_observation_receipt",
        "agentic_service_harness_dry_run_test_runner_plan_receipt",
        "agentic_service_harness_dry_run_test_execution_observation_receipt",
        "agentic_service_harness_task_record_write_uao_admission_preflight",
        "agentic_service_harness_receipt_store_append_preflight",
        "agentic_service_harness_executed_test_receipt_admission_preflight",
        "agentic_service_harness_planned_file_change_collection_preflight",
        "agentic_service_harness_actual_file_change_summary_receipt",
        "agentic_service_harness_actual_diff_collection_admission_preflight",
        "agentic_service_harness_actual_diff_collection_receipt",
        "agentic_service_harness_non_empty_diff_receipt_admission_preflight",
        "agentic_service_harness_filesystem_write_admission_preflight",
        "agentic_service_harness_concrete_filesystem_write_evidence_candidate",
        "agentic_service_harness_actual_filesystem_write_receipt_admission",
        "agentic_service_harness_redacted_filesystem_write_execution_receipt",
        "agentic_service_harness_actual_non_empty_diff_receipt_binding",
        "agentic_service_harness_non_empty_diff_file_summary_receipt",
        "agentic_service_harness_github_pr_admission_preflight",
        "agentic_service_harness_github_pr_creation_dry_run_receipt",
        "agentic_service_harness_github_pr_creation_execution_admission",
        "agentic_service_harness_github_pr_creation_command_preview",
        "agentic_service_harness_github_pr_actual_non_empty_diff_admission_binding",
        "agentic_service_harness_github_pr_operator_approval_request",
        "agentic_service_harness_github_pr_operator_approval_request_actual_non_empty_diff_binding",
        "agentic_service_harness_github_pr_operator_approval_request_command_preview_binding",
        "agentic_service_harness_github_pr_operator_response_witness",
        "agentic_service_harness_github_pr_operator_response_command_preview_binding",
        "agentic_service_harness_github_pr_branch_write_authority_binding",
        "agentic_service_harness_github_pr_uao_admission_witness",
        "agentic_service_harness_github_pr_repository_effect_rollback_plan_witness",
        "agentic_service_harness_github_pr_ci_gate_before_ready_for_review_witness",
        "agentic_service_harness_github_pr_effect_reconciliation_witness",
        "agentic_service_harness_github_pr_effect_reconciliation_evidence_contract",
        "agentic_service_harness_github_pr_effect_reconciliation_live_evidence",
        "agentic_service_harness_github_pr_terminal_closure_certificate_candidate",
        "agentic_service_harness_github_pr_terminal_closure_operator_approval_gate",
        "agentic_service_harness_github_pr_terminal_closure_operator_decision_contract",
        "agentic_service_harness_github_pr_terminal_closure_generic_continuation_rejection",
        "agentic_service_harness_github_pr_terminal_closure_operator_decision_value_request",
        "agentic_service_harness_github_pr_terminal_closure_operator_decision_value_record",
        "agentic_service_harness_github_pr_terminal_closure_certificate_minting",
        "agentic_service_harness_github_pr_terminal_closure_certificate_read_model",
        "agentic_service_harness_github_pr_terminal_closure_certificate_witness",
        "agentic_service_harness_read_only_status_route_design",
        "agentic_service_harness_read_only_status_route",
        "agentic_service_harness_authority_transitions",
        "channel_approval_strength_policy",
        "component_registry",
        "component_lifecycle_transition_receipts",
        "component_authority_envelope_witnesses",
        "component_router_inventory",
        "component_proof_binding",
        "component_route_family_ownership",
        "component_route_family_promotion_preflight",
        "component_route_family_promotion_witness_requirements",
        "component_route_family_promotion_witness_evidence",
        "component_route_family_promotion_approval_candidates",
        "component_route_family_promotion_approval_intake",
        "component_route_family_promotion_submitted_evidence_verifier",
        "component_route_family_promotion_submitted_evidence_records",
        "component_route_family_promotion_submitted_evidence_payload_examples",
        "component_route_family_promotion_operator_submitted_evidence_records",
        "component_route_family_promotion_gate_satisfaction_evaluator",
        "component_route_family_promotion_authority_decision_report",
        "component_route_family_promotion_route_binding_decision_report",
        "component_route_family_promotion_lifecycle_transition_decision_report",
        "component_route_family_promotion_authority_upgrade_witness_decision_report",
        "component_route_family_promotion_product_ownership_decision_report",
        "component_route_family_promotion_terminal_closure_denial_report",
        "component_route_family_promotion_missing_evidence_ledger",
        "component_route_family_promotion_router_inventory_delta_candidate",
        "component_route_family_promotion_router_inventory_delta_witness_requirements",
        "component_route_family_promotion_router_inventory_delta_witness_minting_preflight",
        "component_route_family_promotion_router_inventory_delta_witness_minting_denial_report",
        "component_route_family_promotion_router_inventory_delta_witness_remediation_plan",
        "component_route_family_promotion_router_inventory_delta_witness_remediation_evidence_request",
        "component_route_family_promotion_router_inventory_delta_witness_remediation_evidence_request_status_ledger",
        "component_read_model",
        "component_autopsy",
        "component_request_simulation",
        "component_bundle_compiler",
        "component_evidence_request_queue",
        "component_evidence_submission_intake",
        "component_evidence_postmerge_audit",
        "component_graph",
        "component_dead_detector",
        "read_only_first_worker_path",
        "read_only_document_worker_path",
        "read_only_search_worker_path",
        "worker_failure_receipt",
        "agentic_service_harness_live_task_run_producer_evidence",
        "agentic_service_harness_live_task_run_producer_rehearsal",
        "agentic_service_harness_live_producer_admission_gate",
        "agentic_service_harness_live_producer_witness_requirements",
        "agentic_service_harness_live_producer_operator_approval_request",
        "agentic_service_harness_live_producer_operator_response_witness",
        "agentic_service_harness_live_producer_operator_decision_evidence",
        "agentic_service_harness_live_producer_operator_decision_record",
        "agentic_service_harness_live_producer_operator_decision_value_absence",
        "agentic_service_harness_live_producer_operator_decision_pending_status",
        "agentic_service_harness_live_producer_operator_decision_value_intake_preflight",
        "agentic_service_harness_live_producer_operator_decision_generic_continuation_rejection",
        "agentic_service_harness_live_producer_operator_decision_value_request",
        "agentic_service_harness_live_producer_operator_decision_value_template",
        "agentic_service_harness_live_producer_operator_decision_value_collection_gate",
        "agentic_service_harness_live_producer_operator_decision_value_record_path",
        "agentic_service_harness_live_producer_operator_decision_value_record",
        "agentic_service_harness_live_producer_effect_receipt_preflight",
        "agentic_service_harness_live_producer_external_adapter_evidence_preflight",
        "agentic_service_harness_live_producer_secret_handoff_preflight",
        "agentic_service_harness_live_producer_rollback_proof_preflight",
        "foundation_mode",
        "foundation_local_proof_thread",
        "evidence_ledger_foundation_source",
        *(
            script_path.stem.removeprefix("validate_")
            for script_path in _foundation_boundary_validator_scripts()
        ),
    }
    repository_governance_phase = [
        "protocol_manifest",
        "simple_assistant_ui_boundary",
        "logic_governance_application",
        "life_meaning_governance",
        "phi_gps_v3_platform_spec",
        "governance_normalization_map",
        "holistic_loop_reasoning_admission_binding",
        "public_repository_surface",
        "proprietary_boundary",
        "company_boundary_kernel",
        "release_status",
    ]
    workspace_evidence_phase = [
        "workspace_governance_preflight_receipt_contract",
        "workspace_governance_preflight_receipt_example",
        "workspace_governance_witness_contract",
        "workspace_governance_inventory_report",
        "workspace_governance_inventory_report_contract",
        "workspace_governance_integrity_report",
        "workspace_governance_integrity_report_contract",
        "governed_code_change_loop_sandbox_probe_example",
        "governed_code_change_loop_sandbox_readiness_runbook",
        "code_change_physics_packet",
        "search_decision_receipt",
        "intelligence_coordination_episode_receipt",
        "engineering_puzzle_universality_witness",
        "mil_audit_runbook_operator_checklist",
        "general_agent_promotion_handoff_packet",
        "general_agent_promotion_operator_checklist",
        "general_agent_promotion_environment_bindings",
        "general_agent_promotion_handoff_preflight",
        "general_agent_promotion_closure_chain",
        "finance_approval_live_handoff_closure_run",
        "finance_approval_live_handoff_chain",
        "route_receipt_coverage",
        "route_guard_chain_coverage",
        "reflective_contract_guard",
        "doc_code_consistency",
        "tenant_scope_coverage",
        "persistence_tenant_guard_coverage",
        "mcp_capability_manifest",
        "capability_success_contract_registry",
        "capability_debt_report",
        "capability_passports",
        "capability_passport_dashboard",
        "capability_friction_control",
        "forge_write_spine_bridge",
        "forge_state_write_admission_packet",
        "forge_live_runtime_readiness_gate",
        "forge_live_runtime_evidence_collection_packet",
        "forge_live_runtime_local_evidence_bundle",
        "forge_live_runtime_evidence_acceptance_gate",
        "forge_live_runtime_signed_evidence_receipt",
        "forge_live_runtime_probe_admission_packet",
        "forge_live_runtime_approved_probe_output_packet",
        "forge_live_runtime_post_probe_reconciliation_packet",
        "forge_live_runtime_signed_receipt_population_gate",
        "forge_live_runtime_evidence_chain_read_model",
        "forge_live_runtime_operator_evidence_request",
        "forge_live_runtime_operator_evidence_submission_packet",
        "forge_live_runtime_operator_evidence_verification_gate",
        "forge_live_runtime_operator_evidence_acceptance_handoff_packet",
        "operator_plan_receipt_bundle_read_model",
        "worker_receipt_ledger_read_model",
        "mcp_operator_checklist",
        "public_naming_readiness",
        "public_demo_surfaces",
        "snet_episode_replay",
        "strict_schema_validation",
        "strict_artifact_validation",
        "terminal_closure_certificate",
    ]
    terminal_protocol_phase = [
        "universal_action_orchestration_contract",
        "universal_action_orchestration_validation_receipt_contract",
        "universal_action_orchestration_validation_receipt_example",
        "universal_symbol_runtime_admission_policy",
        "universal_symbol_runtime_admission_evidence_receipt",
        "universal_symbol_runtime_live_witness_input_receipt",
        "universal_symbol_lane_runtime_authority_evidence_receipt",
        "universal_symbol_runtime_authority_witness",
        "universal_symbol_runtime_authority_read_model",
        "universal_symbol_skill_runtime_authority_witness",
        "universal_symbol_adapter_receipt_persistence_policy",
        "universal_symbol_append_audit_witness",
        "universal_symbol_receipt_store_operator_approval_witness",
        "universal_symbol_receipt_store_operator_identity_witness",
        "universal_symbol_receipt_store_operator_approval_decision_witness",
        "universal_symbol_receipt_store_operator_reapproval_expiry_witness",
        "universal_symbol_receipt_store_operator_revocation_witness",
        "universal_symbol_receipt_store_replacement_decision_receipt",
        "universal_symbol_receipt_store_replacement_decision_replay_idempotency_witness",
        "universal_symbol_receipt_store_reapproval_revocation_witness",
        "universal_symbol_receipt_store_lifecycle_evidence_receipt",
        "universal_symbol_receipt_store_lifecycle_audit_receipt",
        "universal_symbol_receipt_store_tenant_scope_witness",
        "universal_symbol_receipt_store_writer_duty_scope_witness",
        "universal_symbol_receipt_store_path_confinement_witness",
        "universal_symbol_receipt_store_write_path_idempotency_witness",
        "universal_symbol_receipt_store_durability_replay_witness",
        "universal_symbol_receipt_store_recovery_witness",
        "universal_symbol_receipt_store_writer_identity_witness",
        "universal_symbol_receipt_store_writer_registration_witness",
        "universal_symbol_receipt_store_path_custody_witness",
        "universal_symbol_receipt_store_write_path_witness",
        "universal_symbol_receipt_store_authority_witness",
        "universal_symbol_kernel",
        "inceptadive_external_effect_adapter_readiness",
        "sdlc_artifact_validation",
        "sdlc_route_validation",
        "sdlc_state_machine_validation",
        "sdlc_release_readiness_validation",
        "sdlc_security_review_validation",
        "sdlc_pr_enforcement_validation",
    ]
    expected_tail = repository_governance_phase + workspace_evidence_phase + terminal_protocol_phase

    def assert_ordered(before: str, after: str) -> None:
        assert names.index(before) < names.index(after)

    assert names[:foundation_start] == ["local_assurance_plan", "agents_policy", "trusted_local_control_studio"]
    assert foundation_phase
    assert set(foundation_phase) == expected_foundation_names
    assert len(foundation_phase) == len(expected_foundation_names)
    assert names[protocol_index:] == expected_tail
    assert len(names) == len(set(names))
    assert names == [command.name for command in runner.build_check_commands("python-test")]

    assert foundation_phase[:2] == ["foundation_mode", "foundation_source_control_boundary"]
    assert_ordered("foundation_source_control_boundary", "foundation_source_control_review_checklist_boundary")
    assert_ordered(
        "foundation_source_control_review_checklist_boundary",
        "foundation_local_release_packet_rehearsal_boundary",
    )
    assert_ordered(
        "foundation_local_release_packet_rehearsal_boundary",
        "foundation_python_dependency_visibility_rehearsal_boundary",
    )
    assert_ordered("foundation_python_dependency_visibility_rehearsal_boundary", "agentic_service_harness_contract")
    assert_ordered("agentic_service_harness_contract", "agentic_service_harness_read_models")
    assert_ordered("agentic_service_harness_read_models", "agentic_service_harness_read_model_projections")
    assert_ordered("agentic_service_harness_read_model_projections", "agentic_service_harness_read_model_integrity")
    assert_ordered("agentic_service_harness_read_model_integrity", "agentic_service_harness_read_model_persistence")
    assert_ordered(
        "agentic_service_harness_read_model_persistence",
        "agentic_service_harness_read_model_binding_plan",
    )
    assert_ordered(
        "agentic_service_harness_read_model_binding_plan",
        "agentic_service_harness_github_repo_task_service",
    )
    assert_ordered(
        "agentic_service_harness_github_repo_task_service",
        "agentic_service_harness_github_repo_task_intake",
    )
    assert_ordered(
        "agentic_service_harness_github_repo_task_intake",
        "agentic_service_harness_dashboard_data_contract",
    )
    assert_ordered(
        "agentic_service_harness_dashboard_data_contract",
        "agentic_service_harness_adapter_registry_contract",
    )
    assert_ordered(
        "agentic_service_harness_adapter_registry_contract",
        "agentic_service_harness_evidence_bundle_projection",
    )
    assert_ordered(
        "agentic_service_harness_evidence_bundle_projection",
        "agentic_service_harness_receipt_evidence_read_models",
    )
    assert_ordered(
        "agentic_service_harness_receipt_evidence_read_models",
        "agentic_service_harness_loopstatus_projection",
    )
    assert_ordered(
        "agentic_service_harness_loopstatus_projection",
        "agentic_service_harness_receipt_projection",
    )
    assert_ordered(
        "agentic_service_harness_receipt_projection",
        "agentic_service_harness_task_creation_admission_preflight",
    )
    assert_ordered(
        "agentic_service_harness_task_creation_admission_preflight",
        "agentic_service_harness_github_task_receipt_emitter_dry_run",
    )
    assert_ordered(
        "agentic_service_harness_workspace_sandbox_preflight",
        "agentic_service_harness_approved_branch_workspace_creation_preflight",
    )
    assert_ordered(
        "agentic_service_harness_approved_branch_workspace_creation_preflight",
        "agentic_service_harness_approved_branch_workspace_creation_authority_binding",
    )
    assert_ordered(
        "agentic_service_harness_approved_branch_workspace_creation_authority_binding",
        "agentic_service_harness_approved_branch_workspace_creation_observation_receipt",
    )
    assert_ordered(
        "agentic_service_harness_approved_branch_workspace_creation_observation_receipt",
        "agentic_service_harness_dry_run_test_runner_plan_receipt",
    )
    assert_ordered(
        "agentic_service_harness_dry_run_test_runner_plan_receipt",
        "agentic_service_harness_dry_run_test_execution_observation_receipt",
    )
    assert_ordered(
        "agentic_service_harness_dry_run_test_execution_observation_receipt",
        "agentic_service_harness_task_record_write_uao_admission_preflight",
    )
    assert_ordered(
        "agentic_service_harness_task_record_write_uao_admission_preflight",
        "agentic_service_harness_receipt_store_append_preflight",
    )
    assert_ordered(
        "agentic_service_harness_receipt_store_append_preflight",
        "agentic_service_harness_executed_test_receipt_admission_preflight",
    )
    assert_ordered(
        "agentic_service_harness_non_empty_diff_receipt_admission_preflight",
        "agentic_service_harness_filesystem_write_admission_preflight",
    )
    assert_ordered(
        "agentic_service_harness_filesystem_write_admission_preflight",
        "agentic_service_harness_concrete_filesystem_write_evidence_candidate",
    )
    assert_ordered(
        "agentic_service_harness_concrete_filesystem_write_evidence_candidate",
        "agentic_service_harness_actual_filesystem_write_receipt_admission",
    )
    assert_ordered(
        "agentic_service_harness_actual_filesystem_write_receipt_admission",
        "agentic_service_harness_redacted_filesystem_write_execution_receipt",
    )
    assert_ordered(
        "agentic_service_harness_redacted_filesystem_write_execution_receipt",
        "agentic_service_harness_actual_non_empty_diff_receipt_binding",
    )
    assert_ordered(
        "agentic_service_harness_actual_non_empty_diff_receipt_binding",
        "agentic_service_harness_non_empty_diff_file_summary_receipt",
    )
    assert_ordered(
        "agentic_service_harness_non_empty_diff_file_summary_receipt",
        "agentic_service_harness_github_pr_admission_preflight",
    )
    assert_ordered(
        "agentic_service_harness_github_pr_admission_preflight",
        "agentic_service_harness_github_pr_creation_dry_run_receipt",
    )
    assert_ordered(
        "agentic_service_harness_github_pr_creation_dry_run_receipt",
        "agentic_service_harness_github_pr_creation_execution_admission",
    )
    assert_ordered(
        "agentic_service_harness_github_pr_creation_execution_admission",
        "agentic_service_harness_github_pr_creation_command_preview",
    )
    assert_ordered(
        "agentic_service_harness_github_pr_creation_command_preview",
        "agentic_service_harness_github_pr_actual_non_empty_diff_admission_binding",
    )
    assert_ordered(
        "agentic_service_harness_github_pr_actual_non_empty_diff_admission_binding",
        "agentic_service_harness_github_pr_operator_approval_request",
    )
    assert_ordered(
        "agentic_service_harness_github_pr_operator_approval_request",
        "agentic_service_harness_github_pr_operator_approval_request_actual_non_empty_diff_binding",
    )
    assert_ordered(
        "agentic_service_harness_github_pr_operator_approval_request_actual_non_empty_diff_binding",
        "agentic_service_harness_github_pr_operator_approval_request_command_preview_binding",
    )
    assert_ordered(
        "agentic_service_harness_github_pr_operator_approval_request_command_preview_binding",
        "agentic_service_harness_github_pr_operator_response_witness",
    )
    assert_ordered(
        "agentic_service_harness_github_pr_operator_response_witness",
        "agentic_service_harness_github_pr_operator_response_command_preview_binding",
    )
    assert_ordered(
        "agentic_service_harness_github_pr_operator_response_command_preview_binding",
        "agentic_service_harness_github_pr_branch_write_authority_binding",
    )
    assert_ordered(
        "agentic_service_harness_executed_test_receipt_admission_preflight",
        "agentic_service_harness_planned_file_change_collection_preflight",
    )
    assert_ordered(
        "agentic_service_harness_github_repo_task_service",
        "agentic_service_harness_read_only_status_route_design",
    )
    assert_ordered(
        "agentic_service_harness_read_only_status_route_design",
        "agentic_service_harness_read_only_status_route",
    )
    assert_ordered(
        "agentic_service_harness_github_pr_terminal_closure_certificate_minting",
        "agentic_service_harness_github_pr_terminal_closure_certificate_read_model",
    )
    assert_ordered(
        "agentic_service_harness_github_pr_terminal_closure_certificate_read_model",
        "agentic_service_harness_github_pr_terminal_closure_certificate_witness",
    )
    assert_ordered(
        "agentic_service_harness_read_only_status_route",
        "agentic_service_harness_authority_transitions",
    )
    assert_ordered(
        "agentic_service_harness_authority_transitions",
        "channel_approval_strength_policy",
    )
    assert_ordered(
        "channel_approval_strength_policy",
        "component_registry",
    )
    assert_ordered(
        "component_registry",
        "component_lifecycle_transition_receipts",
    )
    assert_ordered(
        "component_lifecycle_transition_receipts",
        "component_authority_envelope_witnesses",
    )
    assert_ordered(
        "component_authority_envelope_witnesses",
        "component_router_inventory",
    )
    assert_ordered(
        "component_router_inventory",
        "component_proof_binding",
    )
    assert_ordered(
        "component_proof_binding",
        "component_route_family_ownership",
    )
    assert_ordered(
        "component_route_family_ownership",
        "component_route_family_promotion_preflight",
    )
    assert_ordered(
        "component_route_family_promotion_preflight",
        "component_route_family_promotion_witness_requirements",
    )
    assert_ordered(
        "component_route_family_promotion_witness_requirements",
        "component_route_family_promotion_witness_evidence",
    )
    assert_ordered(
        "component_route_family_promotion_witness_evidence",
        "component_route_family_promotion_approval_candidates",
    )
    assert_ordered(
        "component_route_family_promotion_approval_candidates",
        "component_route_family_promotion_approval_intake",
    )
    assert_ordered(
        "component_route_family_promotion_approval_intake",
        "component_route_family_promotion_submitted_evidence_verifier",
    )
    assert_ordered(
        "component_route_family_promotion_submitted_evidence_verifier",
        "component_route_family_promotion_submitted_evidence_records",
    )
    assert_ordered(
        "component_route_family_promotion_submitted_evidence_records",
        "component_route_family_promotion_submitted_evidence_payload_examples",
    )
    assert_ordered(
        "component_route_family_promotion_submitted_evidence_payload_examples",
        "component_route_family_promotion_operator_submitted_evidence_records",
    )
    assert_ordered(
        "component_route_family_promotion_operator_submitted_evidence_records",
        "component_route_family_promotion_gate_satisfaction_evaluator",
    )
    assert_ordered(
        "component_route_family_promotion_gate_satisfaction_evaluator",
        "component_route_family_promotion_authority_decision_report",
    )
    assert_ordered(
        "component_route_family_promotion_authority_decision_report",
        "component_route_family_promotion_route_binding_decision_report",
    )
    assert_ordered(
        "component_route_family_promotion_route_binding_decision_report",
        "component_route_family_promotion_lifecycle_transition_decision_report",
    )
    assert_ordered(
        "component_route_family_promotion_lifecycle_transition_decision_report",
        "component_route_family_promotion_authority_upgrade_witness_decision_report",
    )
    assert_ordered(
        "component_route_family_promotion_authority_upgrade_witness_decision_report",
        "component_route_family_promotion_product_ownership_decision_report",
    )
    assert_ordered(
        "component_route_family_promotion_product_ownership_decision_report",
        "component_route_family_promotion_terminal_closure_denial_report",
    )
    assert_ordered(
        "component_route_family_promotion_terminal_closure_denial_report",
        "component_route_family_promotion_missing_evidence_ledger",
    )
    assert_ordered(
        "component_route_family_promotion_missing_evidence_ledger",
        "component_route_family_promotion_router_inventory_delta_candidate",
    )
    assert_ordered(
        "component_route_family_promotion_router_inventory_delta_candidate",
        "component_route_family_promotion_router_inventory_delta_witness_requirements",
    )
    assert_ordered(
        "component_route_family_promotion_router_inventory_delta_witness_requirements",
        "component_route_family_promotion_router_inventory_delta_witness_minting_preflight",
    )
    assert_ordered(
        "component_route_family_promotion_router_inventory_delta_witness_minting_preflight",
        "component_route_family_promotion_router_inventory_delta_witness_minting_denial_report",
    )
    assert_ordered(
        "component_route_family_promotion_router_inventory_delta_witness_minting_denial_report",
        "component_route_family_promotion_router_inventory_delta_witness_remediation_plan",
    )
    assert_ordered(
        "component_route_family_promotion_router_inventory_delta_witness_remediation_plan",
        "component_route_family_promotion_router_inventory_delta_witness_remediation_evidence_request",
    )
    assert_ordered(
        "component_route_family_promotion_router_inventory_delta_witness_remediation_evidence_request",
        "component_route_family_promotion_router_inventory_delta_witness_remediation_evidence_request_status_ledger",
    )
    assert_ordered(
        "component_route_family_promotion_router_inventory_delta_witness_remediation_evidence_request_status_ledger",
        "component_read_model",
    )
    assert_ordered(
        "component_read_model",
        "component_autopsy",
    )
    assert_ordered(
        "component_autopsy",
        "component_request_simulation",
    )
    assert_ordered(
        "component_request_simulation",
        "component_bundle_compiler",
    )
    assert_ordered(
        "component_bundle_compiler",
        "component_evidence_request_queue",
    )
    assert_ordered(
        "component_evidence_request_queue",
        "component_evidence_submission_intake",
    )
    assert_ordered(
        "component_evidence_submission_intake",
        "component_evidence_postmerge_audit",
    )
    assert_ordered(
        "component_evidence_postmerge_audit",
        "component_graph",
    )
    assert_ordered(
        "component_graph",
        "component_dead_detector",
    )
    assert_ordered(
        "component_dead_detector",
        "read_only_first_worker_path",
    )
    assert_ordered(
        "read_only_first_worker_path",
        "read_only_document_worker_path",
    )
    assert_ordered(
        "read_only_document_worker_path",
        "read_only_search_worker_path",
    )
    assert_ordered(
        "read_only_search_worker_path",
        "worker_failure_receipt",
    )
    assert_ordered(
        "worker_failure_receipt",
        "agentic_service_harness_live_task_run_producer_evidence",
    )
    assert_ordered(
        "agentic_service_harness_live_task_run_producer_evidence",
        "agentic_service_harness_live_task_run_producer_rehearsal",
    )
    assert_ordered(
        "agentic_service_harness_live_task_run_producer_rehearsal",
        "agentic_service_harness_live_producer_admission_gate",
    )
    assert_ordered(
        "agentic_service_harness_live_producer_admission_gate",
        "agentic_service_harness_live_producer_witness_requirements",
    )
    assert_ordered(
        "agentic_service_harness_live_producer_witness_requirements",
        "agentic_service_harness_live_producer_operator_approval_request",
    )
    assert_ordered(
        "agentic_service_harness_live_producer_operator_approval_request",
        "agentic_service_harness_live_producer_operator_response_witness",
    )
    assert_ordered(
        "agentic_service_harness_live_producer_operator_response_witness",
        "agentic_service_harness_live_producer_operator_decision_evidence",
    )
    assert_ordered(
        "agentic_service_harness_live_producer_operator_decision_evidence",
        "agentic_service_harness_live_producer_operator_decision_record",
    )
    assert_ordered(
        "agentic_service_harness_live_producer_operator_decision_record",
        "agentic_service_harness_live_producer_operator_decision_value_absence",
    )
    assert_ordered(
        "agentic_service_harness_live_producer_operator_decision_value_absence",
        "agentic_service_harness_live_producer_operator_decision_pending_status",
    )
    assert_ordered(
        "agentic_service_harness_live_producer_operator_decision_pending_status",
        "agentic_service_harness_live_producer_operator_decision_value_intake_preflight",
    )
    assert_ordered(
        "agentic_service_harness_live_producer_operator_decision_value_intake_preflight",
        "agentic_service_harness_live_producer_operator_decision_generic_continuation_rejection",
    )
    assert_ordered(
        "agentic_service_harness_live_producer_operator_decision_generic_continuation_rejection",
        "agentic_service_harness_live_producer_operator_decision_value_request",
    )
    assert_ordered(
        "agentic_service_harness_live_producer_operator_decision_value_request",
        "agentic_service_harness_live_producer_operator_decision_value_template",
    )
    assert_ordered(
        "agentic_service_harness_live_producer_operator_decision_value_template",
        "agentic_service_harness_live_producer_operator_decision_value_collection_gate",
    )
    assert_ordered(
        "agentic_service_harness_live_producer_operator_decision_value_collection_gate",
        "agentic_service_harness_live_producer_operator_decision_value_record_path",
    )
    assert_ordered(
        "agentic_service_harness_live_producer_operator_decision_value_record_path",
        "agentic_service_harness_live_producer_operator_decision_value_record",
    )
    assert_ordered(
        "agentic_service_harness_live_producer_operator_decision_value_record",
        "agentic_service_harness_live_producer_effect_receipt_preflight",
    )
    assert_ordered(
        "agentic_service_harness_live_producer_effect_receipt_preflight",
        "agentic_service_harness_live_producer_external_adapter_evidence_preflight",
    )
    assert_ordered(
        "agentic_service_harness_live_producer_external_adapter_evidence_preflight",
        "agentic_service_harness_live_producer_secret_handoff_preflight",
    )
    assert_ordered(
        "agentic_service_harness_live_producer_secret_handoff_preflight",
        "agentic_service_harness_live_producer_rollback_proof_preflight",
    )
    assert_ordered(
        "agentic_service_harness_live_producer_rollback_proof_preflight",
        "foundation_operator_readiness_boundary",
    )
    assert_ordered("foundation_source_control_review_checklist_boundary", "foundation_operator_readiness_boundary")
    assert_ordered("foundation_source_control_boundary", "foundation_operator_readiness_boundary")
    assert_ordered("foundation_learning_path_boundary", "foundation_learning_loop_rehearsal_boundary")
    assert_ordered("foundation_learning_loop_rehearsal_boundary", "foundation_concept_glossary_rehearsal_boundary")
    assert_ordered(
        "foundation_concept_glossary_rehearsal_boundary",
        "foundation_life_meaning_doctrine_rehearsal_boundary",
    )
    assert_ordered("foundation_life_meaning_doctrine_rehearsal_boundary", "foundation_architecture_map_boundary")
    assert_ordered("foundation_external_infrastructure_boundary", "foundation_runtime_secret_handoff_rehearsal_boundary")
    assert_ordered(
        "foundation_runtime_secret_handoff_rehearsal_boundary",
        "foundation_runtime_witness_deferral_boundary",
    )
    assert_ordered(
        "foundation_runtime_witness_deferral_boundary",
        "foundation_production_dependency_evidence_rehearsal_boundary",
    )
    assert_ordered(
        "foundation_production_dependency_evidence_rehearsal_boundary",
        "foundation_external_evidence_acceptance_rehearsal_boundary",
    )
    assert_ordered(
        "foundation_external_evidence_acceptance_rehearsal_boundary",
        "foundation_deployment_upstream_api_gate_rehearsal_boundary",
    )
    assert_ordered("foundation_deployment_upstream_api_gate_rehearsal_boundary", "foundation_gateway_dns_target_binding_rehearsal_boundary")
    assert_ordered("foundation_gateway_dns_target_binding_rehearsal_boundary", "foundation_gateway_dns_publication_rehearsal_boundary")
    assert_ordered(
        "foundation_gateway_dns_publication_rehearsal_boundary",
        "foundation_gateway_dns_resolution_receipt_rehearsal_boundary",
    )
    assert_ordered("foundation_gateway_dns_resolution_receipt_rehearsal_boundary", "foundation_gateway_endpoint_reachability_rehearsal_boundary")
    assert_ordered("foundation_gateway_endpoint_reachability_rehearsal_boundary", "foundation_gateway_endpoint_evidence_receipt_rehearsal_boundary")
    assert_ordered("foundation_gateway_endpoint_evidence_receipt_rehearsal_boundary", "foundation_public_health_declaration_rehearsal_boundary")
    assert_ordered("foundation_public_health_declaration_rehearsal_boundary", "foundation_deployment_witness_input_boundary")
    assert_ordered("foundation_deployment_witness_input_boundary", "foundation_deployment_witness_preflight_rehearsal_boundary")
    assert_ordered(
        "foundation_deployment_witness_preflight_rehearsal_boundary",
        "foundation_deployment_witness_dispatch_rehearsal_boundary",
    )
    assert_ordered(
        "foundation_deployment_witness_dispatch_rehearsal_boundary",
        "foundation_deployment_witness_artifact_validation_rehearsal_boundary",
    )
    assert_ordered(
        "foundation_deployment_witness_artifact_validation_rehearsal_boundary",
        "foundation_deployment_witness_evidence_handoff_boundary",
    )
    assert_ordered("foundation_deployment_witness_evidence_handoff_boundary", "foundation_deployment_witness_evidence_ledger_routing_boundary")
    assert_ordered("foundation_legal_business_boundary", "foundation_legal_business_question_rehearsal_boundary")
    assert_ordered("foundation_legal_business_question_rehearsal_boundary", "foundation_legal_review_deferral_boundary")
    assert_ordered("foundation_legal_review_deferral_boundary", "foundation_company_formation_deferral_boundary")
    assert_ordered("foundation_company_formation_deferral_boundary", "foundation_patent_disclosure_deferral_boundary")
    assert_ordered("foundation_patent_disclosure_deferral_boundary", "foundation_product_scope_boundary")
    assert_ordered("foundation_pilot_deferral_boundary", "foundation_pilot_deferral_rehearsal_boundary")
    assert_ordered("foundation_pilot_deferral_rehearsal_boundary", "foundation_reassessment_gate_boundary")
    assert_ordered("foundation_support_readiness_boundary", "foundation_support_triage_rehearsal_boundary")
    assert_ordered("foundation_intake_onboarding_boundary", "foundation_intake_questionnaire_rehearsal_boundary")
    assert_ordered("foundation_customer_access_boundary", "foundation_customer_access_policy_rehearsal_boundary")
    assert_ordered("foundation_privacy_data_boundary", "foundation_privacy_minimization_rehearsal_boundary")
    assert_ordered("foundation_funding_team_boundary", "foundation_funding_team_obligation_rehearsal_boundary")
    assert_ordered("foundation_community_network_boundary", "foundation_community_network_no_outreach_rehearsal_boundary")
    assert_ordered("foundation_community_network_no_outreach_rehearsal_boundary", "protocol_manifest")
    assert_ordered("protocol_manifest", "simple_assistant_ui_boundary")
    assert_ordered("life_meaning_governance", "phi_gps_v3_platform_spec")
    assert_ordered("phi_gps_v3_platform_spec", "governance_normalization_map")
    assert_ordered("governance_normalization_map", "holistic_loop_reasoning_admission_binding")
    assert_ordered("holistic_loop_reasoning_admission_binding", "public_repository_surface")
    assert_ordered("code_change_physics_packet", "search_decision_receipt")
    assert_ordered("search_decision_receipt", "intelligence_coordination_episode_receipt")

    assert args_by_name["local_assurance_plan"][1:] == (
        "scripts/refresh_local_assurance.py",
        "--dry-run",
        "--json",
    )
    assert args_by_name["agents_policy"][1:] == ("scripts/validate_agents_governance.py",)
    assert args_by_name["trusted_local_control_studio"][1:] == (
        "scripts/validate_trusted_local_control_studio.py",
    )
    assert args_by_name["life_meaning_governance"][1:] == (
        "scripts/validate_life_meaning_governance.py",
    )
    assert args_by_name["phi_gps_v3_platform_spec"][1:] == (
        "scripts/validate_phi_gps_v3_platform_spec.py",
    )
    assert args_by_name["governance_normalization_map"][1:] == (
        "scripts/validate_governance_normalization_map.py",
    )
    assert args_by_name["company_boundary_kernel"][1:] == (
        "scripts/validate_foundation_company_boundary_kernel.py",
    )
    for check_name in foundation_phase:
        if check_name == "foundation_mode":
            expected_args = ("scripts/validate_foundation_mode.py",)
        elif check_name == "foundation_local_proof_thread":
            expected_args = ("scripts/validate_foundation_local_proof_thread.py",)
        elif check_name.startswith("agentic_service_harness_"):
            expected_args = (f"scripts/validate_{check_name}.py",)
        else:
            expected_args = (f"scripts/validate_{check_name}.py",)

        assert args_by_name[check_name][1:] == expected_args
    assert args_by_name["workspace_governance_inventory_report"][1:] == (
        "scripts/report_workspace_governance_inventory.py",
    )
    assert args_by_name["workspace_governance_inventory_report_contract"][1:] == (
        "scripts/validate_workspace_governance_inventory_report_contract.py",
    )
    assert args_by_name["workspace_governance_witness_contract"][1:] == (
        "scripts/validate_workspace_governance_witness.py",
    )
    assert args_by_name["workspace_governance_integrity_report"][1:] == (
        "scripts/report_workspace_governance_integrity.py",
    )
    assert args_by_name["workspace_governance_integrity_report_contract"][1:] == (
        "scripts/validate_workspace_governance_integrity_report_contract.py",
    )
    assert args_by_name["governed_code_change_loop_sandbox_probe_example"][1:] == (
        "scripts/validate_governed_code_change_loop_sandbox_probe.py",
        "--probe",
        "docs/governed-code-change-loop-sandbox-probe-example.json",
    )
    assert args_by_name["governed_code_change_loop_sandbox_readiness_runbook"][1:] == (
        "scripts/validate_governed_code_change_loop_sandbox_readiness_runbook.py",
    )
    assert args_by_name["code_change_physics_packet"][1:] == (
        "scripts/validate_code_change_physics_packet.py",
    )
    assert args_by_name["search_decision_receipt"][1:] == (
        "scripts/validate_search_decision_receipt.py",
    )
    assert args_by_name["intelligence_coordination_episode_receipt"][1:] == (
        "scripts/validate_intelligence_coordination_episode_receipt.py",
    )
    assert args_by_name["engineering_puzzle_universality_witness"][1:] == (
        "scripts/validate_engineering_puzzle_universality_witness.py",
        "--output",
        ".tmp/engineering-puzzle-universality-witness.json",
    )
    assert args_by_name["mil_audit_runbook_operator_checklist"][1:] == (
        "scripts/validate_mil_audit_runbook_operator_checklist.py",
        "--checklist",
        "examples/mil_audit_runbook_operator_checklist.json",
        "--json",
    )
    assert args_by_name["general_agent_promotion_handoff_packet"][1:] == (
        "scripts/validate_general_agent_promotion_handoff_packet.py",
        "--packet",
        "examples/general_agent_promotion_handoff_packet.json",
        "--json",
    )
    assert args_by_name["general_agent_promotion_operator_checklist"][1:] == (
        "scripts/validate_general_agent_promotion_operator_checklist.py",
        "--checklist",
        "examples/general_agent_promotion_operator_checklist.json",
        "--json",
    )
    assert args_by_name["general_agent_promotion_environment_bindings"][1:] == (
        "scripts/validate_general_agent_promotion_environment_bindings.py",
        "--contract",
        "examples/general_agent_promotion_environment_bindings.json",
        "--checklist",
        "examples/general_agent_promotion_operator_checklist.json",
        "--json",
    )
    assert args_by_name["general_agent_promotion_handoff_preflight"][1:] == (
        "scripts/preflight_general_agent_promotion_handoff.py",
        "--output",
        ".tmp/general-agent-promotion-handoff-preflight.json",
        "--json",
    )
    assert args_by_name["general_agent_promotion_closure_chain"][1:] == (
        "scripts/run_general_agent_promotion_closure_chain.py",
        "--output-dir",
        ".tmp/general-agent-promotion-closure-chain",
        "--adapter-evidence",
        "examples/capability_adapter_evidence_blocked.json",
        "--json",
        "--strict",
    )
    assert args_by_name["finance_approval_live_handoff_closure_run"][1:] == (
        "scripts/run_finance_approval_live_handoff_closure.py",
        "--output",
        ".tmp/finance-approval-live-handoff-closure-run.json",
        "--json",
    )
    assert args_by_name["finance_approval_live_handoff_chain"][1:] == (
        "scripts/run_finance_approval_live_handoff_chain.py",
        "--output-dir",
        ".tmp/finance-approval-live-handoff-chain",
        "--json",
    )
    assert args_by_name["route_receipt_coverage"][1:] == (
        "scripts/validate_receipt_coverage.py",
        "--strict",
    )
    assert args_by_name["route_guard_chain_coverage"][1:] == (
        "scripts/validate_guard_chain_coverage.py",
        "--strict",
    )
    assert args_by_name["reflective_contract_guard"][1:] == (
        "scripts/validate_reflective_contracts.py",
    )
    assert args_by_name["doc_code_consistency"][1:] == (
        "scripts/validate_doc_code_consistency.py",
    )
    assert args_by_name["tenant_scope_coverage"][1:] == (
        "scripts/validate_tenant_scope_coverage.py",
    )
    assert args_by_name["persistence_tenant_guard_coverage"][1:] == (
        "scripts/validate_persistence_tenant_guard_coverage.py",
    )
    assert args_by_name["mcp_capability_manifest"][1:] == (
        "scripts/validate_mcp_capability_manifest.py",
        "--manifest",
        "examples/mcp_capability_manifest.json",
        "--json",
    )
    assert args_by_name["capability_success_contract_registry"][1:] == (
        "scripts/validate_capability_success_contract_registry.py",
    )
    assert args_by_name["capability_debt_report"][1:] == (
        "scripts/validate_capability_debt_report.py",
    )
    assert args_by_name["capability_passports"][1:] == (
        "scripts/validate_capability_passports.py",
    )
    assert args_by_name["capability_passport_dashboard"][1:] == (
        "scripts/validate_capability_passport_dashboard.py",
    )
    assert args_by_name["capability_friction_control"][1:] == (
        "scripts/validate_capability_friction_control.py",
    )
    assert args_by_name["forge_write_spine_bridge"][1:] == (
        "scripts/validate_forge_write_spine_bridge.py",
    )
    assert args_by_name["forge_state_write_admission_packet"][1:] == (
        "scripts/validate_forge_state_write_admission_packet.py",
    )
    assert args_by_name["forge_live_runtime_readiness_gate"][1:] == (
        "scripts/validate_forge_live_runtime_readiness_gate.py",
    )
    assert args_by_name["forge_live_runtime_evidence_collection_packet"][1:] == (
        "scripts/validate_forge_live_runtime_evidence_collection_packet.py",
    )
    assert args_by_name["forge_live_runtime_local_evidence_bundle"][1:] == (
        "scripts/validate_forge_live_runtime_local_evidence_bundle.py",
    )
    assert args_by_name["forge_live_runtime_evidence_acceptance_gate"][1:] == (
        "scripts/validate_forge_live_runtime_evidence_acceptance_gate.py",
    )
    assert args_by_name["forge_live_runtime_signed_evidence_receipt"][1:] == (
        "scripts/validate_forge_live_runtime_signed_evidence_receipt.py",
    )
    assert args_by_name["forge_live_runtime_probe_admission_packet"][1:] == (
        "scripts/validate_forge_live_runtime_probe_admission_packet.py",
    )
    assert args_by_name["forge_live_runtime_approved_probe_output_packet"][1:] == (
        "scripts/validate_forge_live_runtime_approved_probe_output_packet.py",
    )
    assert args_by_name["forge_live_runtime_post_probe_reconciliation_packet"][1:] == (
        "scripts/validate_forge_live_runtime_post_probe_reconciliation_packet.py",
    )
    assert args_by_name["forge_live_runtime_signed_receipt_population_gate"][1:] == (
        "scripts/validate_forge_live_runtime_signed_receipt_population_gate.py",
    )
    assert args_by_name["forge_live_runtime_evidence_chain_read_model"][1:] == (
        "scripts/validate_forge_live_runtime_evidence_chain_read_model.py",
    )
    assert args_by_name["forge_live_runtime_operator_evidence_request"][1:] == (
        "scripts/validate_forge_live_runtime_operator_evidence_request.py",
    )
    assert args_by_name["forge_live_runtime_operator_evidence_submission_packet"][1:] == (
        "scripts/validate_forge_live_runtime_operator_evidence_submission_packet.py",
    )
    assert args_by_name["forge_live_runtime_operator_evidence_verification_gate"][1:] == (
        "scripts/validate_forge_live_runtime_operator_evidence_verification_gate.py",
    )
    assert args_by_name["forge_live_runtime_operator_evidence_acceptance_handoff_packet"][1:] == (
        "scripts/validate_forge_live_runtime_operator_evidence_acceptance_handoff_packet.py",
    )
    assert args_by_name["operator_plan_receipt_bundle_read_model"][1:] == (
        "scripts/validate_operator_plan_receipt_bundle_read_model.py",
    )
    assert args_by_name["worker_receipt_ledger_read_model"][1:] == (
        "scripts/validate_worker_receipt_ledger_read_model.py",
    )
    assert args_by_name["mcp_operator_checklist"][1:] == (
        "scripts/validate_mcp_operator_checklist.py",
        "--checklist",
        "examples/mcp_operator_handoff_checklist.json",
        "--json",
    )
    assert args_by_name["public_naming_readiness"][1:] == (
        "scripts/validate_public_naming_readiness.py",
    )
    assert args_by_name["public_demo_surfaces"][1:] == (
        "scripts/validate_public_demo_surfaces.py",
        "--output",
        ".tmp/public-demo-surface-validation.json",
    )
    assert args_by_name["snet_episode_replay"][1:] == (
        "scripts/validate_snet_episode_replay.py",
        "--episode",
        "examples/snet_episode_seed_dependency.json",
    )
    assert args_by_name["strict_schema_validation"][1:] == (
        "scripts/validate_schemas.py",
        "--strict",
    )
    assert args_by_name["strict_artifact_validation"][1:] == (
        "scripts/validate_artifacts.py",
        "--strict",
    )
    assert args_by_name["terminal_closure_certificate"][1:] == (
        "scripts/validate_terminal_closure_certificate.py",
        "--json",
    )
    assert args_by_name["inceptadive_external_effect_adapter_readiness"][1:] == (
        "scripts/validate_inceptadive_external_effect_adapter_readiness.py",
    )
    assert args_by_name["sdlc_artifact_validation"][1:] == (
        "scripts/validate_sdlc_artifact.py",
    )
    assert args_by_name["sdlc_release_readiness_validation"][1:] == (
        "scripts/validate_sdlc_release_readiness.py",
        "--strict",
    )
    assert args_by_name["sdlc_route_validation"][1:] == (
        "scripts/validate_sdlc_route.py",
    )
    assert args_by_name["sdlc_security_review_validation"][1:] == (
        "scripts/validate_sdlc_security_review.py",
        "--strict",
    )
    assert args_by_name["sdlc_pr_enforcement_validation"][1:] == (
        "scripts/validate_sdlc_pr_enforcement.py",
    )

def test_foundation_boundary_validators_are_preflight_gated_and_tested() -> None:
    """Every foundation boundary validator must be wired into closure evidence."""

    commands = runner.build_check_commands("python-test")
    args_by_name = {command.name: command.args for command in commands}
    boundary_docs = _foundation_boundary_docs()
    boundary_scripts = _foundation_boundary_validator_scripts()

    assert boundary_scripts
    assert len(boundary_scripts) == len(boundary_docs)
    for script_path in boundary_scripts:
        check_name = script_path.stem.removeprefix("validate_")
        relative_script_path = script_path.relative_to(runner.WORKSPACE_ROOT).as_posix()
        paired_test_path = (
            runner.WORKSPACE_ROOT
            / "tests"
            / f"test_{script_path.stem}.py"
        )

        assert check_name in args_by_name, f"{relative_script_path} missing from workspace preflight"
        assert args_by_name[check_name][1:] == (relative_script_path,)
        assert paired_test_path.exists(), f"{relative_script_path} missing paired validator test"


def test_foundation_boundary_docs_have_preflight_validators_and_tests() -> None:
    """Every foundation boundary document must carry executable closure evidence."""

    commands = runner.build_check_commands("python-test")
    args_by_name = {command.name: command.args for command in commands}
    boundary_docs = _foundation_boundary_docs()
    boundary_scripts = _foundation_boundary_validator_scripts()
    boundary_tests = _foundation_boundary_test_files()

    assert boundary_docs
    assert len(boundary_scripts) == len(boundary_docs)
    assert len(boundary_tests) == len(boundary_docs)
    for doc_path in boundary_docs:
        check_name = doc_path.stem.lower()
        validator_path = runner.WORKSPACE_ROOT / "scripts" / f"validate_{check_name}.py"
        paired_test_path = runner.WORKSPACE_ROOT / "tests" / f"test_validate_{check_name}.py"
        relative_doc_path = doc_path.relative_to(runner.WORKSPACE_ROOT).as_posix()
        relative_validator_path = validator_path.relative_to(runner.WORKSPACE_ROOT).as_posix()

        assert validator_path.exists(), f"{relative_doc_path} missing paired validator"
        assert paired_test_path.exists(), f"{relative_doc_path} missing paired validator test"
        assert check_name in args_by_name, f"{relative_doc_path} missing from workspace preflight"
        assert args_by_name[check_name][1:] == (relative_validator_path,)


def test_foundation_boundary_example_packets_exist_and_are_validator_referenced() -> None:
    """Every boundary-owned example packet must be validated by its boundary validator."""

    example_link_pattern = re.compile(r"\.\./examples/([A-Za-z0-9_.-]+\.json)")
    boundary_docs = _foundation_boundary_docs()

    assert boundary_docs
    for doc_path in boundary_docs:
        relative_doc_path = doc_path.relative_to(runner.WORKSPACE_ROOT).as_posix()
        validator_path = runner.WORKSPACE_ROOT / "scripts" / f"validate_{doc_path.stem.lower()}.py"
        validator_text = validator_path.read_text(encoding="utf-8-sig")
        packet_refs = tuple(dict.fromkeys(example_link_pattern.findall(doc_path.read_text(encoding="utf-8-sig"))))

        assert packet_refs, f"{relative_doc_path} does not link any local example packet"
        for packet_ref in packet_refs:
            packet_path = runner.WORKSPACE_ROOT / "examples" / packet_ref

            assert packet_path.exists(), f"{relative_doc_path} references missing example packet: {packet_ref}"
            assert packet_ref in validator_text, f"{validator_path.name} does not validate linked packet: {packet_ref}"


def test_foundation_boundary_validators_and_tests_keep_governed_headers() -> None:
    """Every foundation boundary validator/test module must explain its contract."""

    required_header_fields = ("Purpose:", "Governance scope:", "Dependencies:", "Invariants:")
    boundary_docs = _foundation_boundary_docs()
    boundary_scripts = _foundation_boundary_validator_scripts()
    boundary_tests = _foundation_boundary_test_files()
    module_paths = boundary_scripts + boundary_tests

    assert boundary_docs
    assert len(boundary_scripts) == len(boundary_docs)
    assert len(boundary_tests) == len(boundary_docs)
    assert len(module_paths) == len(boundary_docs) * 2
    for module_path in module_paths:
        relative_module_path = module_path.relative_to(runner.WORKSPACE_ROOT).as_posix()
        module_docstring = _module_docstring(module_path)

        assert module_docstring, f"{relative_module_path} missing module docstring"
        for header_field in required_header_fields:
            assert header_field in module_docstring, f"{relative_module_path} missing {header_field}"


def test_ci_runs_full_unsharded_workspace_preflight_receipt() -> None:
    workflow_text = _ci_workflow_text()
    preflight_command = (
        "python scripts/run_workspace_governance_checks.py --json "
        "--receipt-path .tmp/workspace-governance-preflight-receipt.json"
    )

    assert preflight_command in workflow_text
    command_line = next(line.strip() for line in workflow_text.splitlines() if preflight_command in line)

    assert command_line == (
        f"{preflight_command} > .tmp/workspace-governance-preflight-stdout.json"
    )
    receipt_validator_command = (
        "python scripts/validate_workspace_governance_preflight_receipt.py "
        "--receipt .tmp/workspace-governance-preflight-receipt.json"
    )

    assert receipt_validator_command in workflow_text
    assert "workspace governance preflight: status={status} checks={check_count}" in workflow_text
    assert "--check" not in command_line
    assert "--shard-count" not in command_line
    assert "--shard-index" not in command_line


def test_ci_uploads_workspace_preflight_receipt_artifact() -> None:
    workflow_text = _ci_workflow_text()
    preflight_command = (
        "python scripts/run_workspace_governance_checks.py --json "
        "--receipt-path .tmp/workspace-governance-preflight-receipt.json"
    )
    artifact_name = "name: sdlc-workspace-governance-preflight-receipt"
    artifact_path = "path: .tmp/workspace-governance-preflight-receipt.json"

    assert workflow_text.find(preflight_command) < workflow_text.find("Upload SDLC workspace preflight receipt")
    assert "uses: actions/upload-artifact@v6" in workflow_text
    assert artifact_name in workflow_text
    assert artifact_path in workflow_text
    assert workflow_text.find(artifact_name) < workflow_text.find(artifact_path)


def test_ci_durable_gmail_plan_runs_revocation_recovery_rehearsal() -> None:
    workflow_text = _ci_workflow_text()
    timestamp_command = "export MULLU_VALIDATION_TIMESTAMP="
    plan_command = "python scripts/validate_durable_gmail_connector_runtime_plan.py"
    emit_account_binding_inputs_command = (
        "python scripts/emit_durable_gmail_account_binding_operator_input_request.py "
        "--output .change_assurance/durable_gmail_account_binding_operator_input_request.json --json"
    )
    validate_account_binding_inputs_command = (
        "python scripts/validate_durable_gmail_account_binding_operator_input_request.py "
        "--request .change_assurance/durable_gmail_account_binding_operator_input_request.json "
        "--require-blocked --json"
    )
    produce_revocation_command = (
        "python scripts/produce_durable_gmail_revocation_recovery_rehearsal_receipt.py "
        "--output .change_assurance/durable_gmail_revocation_recovery_rehearsal_receipt.json --strict --json"
    )
    validate_revocation_command = (
        "python scripts/validate_durable_gmail_revocation_recovery_rehearsal_receipt.py "
        "--receipt .change_assurance/durable_gmail_revocation_recovery_rehearsal_receipt.json "
        "--max-age-days 14 --require-ready --json"
    )
    produce_write_command = (
        "python scripts/produce_durable_gmail_write_authority_rehearsal_receipt.py "
        "--output .change_assurance/durable_gmail_write_authority_rehearsal_receipt.json --strict --json"
    )

    assert timestamp_command in workflow_text
    assert emit_account_binding_inputs_command in workflow_text
    assert validate_account_binding_inputs_command in workflow_text
    assert produce_revocation_command in workflow_text
    assert validate_revocation_command in workflow_text
    assert workflow_text.find(timestamp_command) < workflow_text.find(emit_account_binding_inputs_command)
    assert workflow_text.find(plan_command) < workflow_text.find(emit_account_binding_inputs_command)
    assert workflow_text.find(emit_account_binding_inputs_command) < workflow_text.find(
        validate_account_binding_inputs_command
    )
    assert workflow_text.find(validate_account_binding_inputs_command) < workflow_text.find(
        produce_revocation_command
    )
    assert workflow_text.find(produce_revocation_command) < workflow_text.find(validate_revocation_command)
    assert workflow_text.find(validate_revocation_command) < workflow_text.find(produce_write_command)


def test_run_check_preserves_failure_evidence() -> None:
    command = runner.CheckCommand(
        "intentional_failure",
        (sys.executable, "-c", "import sys; print('observed failure'); sys.exit(7)"),
    )

    result = runner.run_check(command, runner.WORKSPACE_ROOT)

    assert result.passed is False
    assert result.return_code == 7
    assert "observed failure" in result.stdout
    assert result.termination_reason == "completed"
    assert result.termination_signal is None


def test_run_check_records_timeout_diagnosis() -> None:
    command = runner.CheckCommand(
        "intentional_timeout",
        (sys.executable, "-c", "import time; time.sleep(5)"),
    )

    result = runner.run_check(command, runner.WORKSPACE_ROOT, timeout_seconds=0.01)

    assert result.passed is False
    assert result.return_code == runner.TIMEOUT_RETURN_CODE
    assert result.termination_reason == "timeout"
    assert result.termination_signal is None
    assert "[TIMEOUT] intentional_timeout exceeded" in result.stderr


def test_run_command_process_terminates_process_tree_on_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    command = runner.CheckCommand("slow_validator", ("python", "slow.py"))
    cleanup_pids: list[int] = []

    class TimeoutProcess:
        pid = 321
        returncode = None

        def __init__(self) -> None:
            self.communicate_calls = 0

        def communicate(self, timeout: float | None = None) -> tuple[str, str]:
            self.communicate_calls += 1
            if self.communicate_calls == 1:
                raise runner.subprocess.TimeoutExpired(
                    command.args,
                    timeout,
                    output="partial stdout",
                    stderr="partial stderr",
                )
            self.returncode = -9
            return (" remaining stdout", " remaining stderr")

    def fake_popen(*args: object, **kwargs: object) -> TimeoutProcess:
        return TimeoutProcess()

    def fake_terminate_process_tree(pid: int) -> str:
        cleanup_pids.append(pid)
        return "[TIMEOUT-CLEANUP] terminated child process tree\n"

    monkeypatch.setattr(runner.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(runner, "terminate_process_tree", fake_terminate_process_tree)

    result = runner.run_command_process(command, runner.WORKSPACE_ROOT, timeout_seconds=0.01)

    assert result.return_code == runner.TIMEOUT_RETURN_CODE
    assert result.timed_out is True
    assert cleanup_pids == [321]
    assert result.stdout == "partial stdout remaining stdout"
    assert "partial stderr remaining stderr" in result.stderr
    assert "[TIMEOUT-CLEANUP] terminated child process tree" in result.stderr
    assert "[TIMEOUT] slow_validator exceeded" in result.stderr


def test_run_check_records_subprocess_start_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    command = runner.CheckCommand("missing_interpreter", ("missing-python", "validator.py"))

    def fake_command_process(*args: object, **kwargs: object) -> runner.ProcessExecution:
        raise OSError("interpreter not found")

    monkeypatch.setattr(runner, "run_command_process", fake_command_process)

    result = runner.run_check(command, runner.WORKSPACE_ROOT)

    assert result.passed is False
    assert result.return_code == runner.CHECK_EXCEPTION_RETURN_CODE
    assert result.termination_reason == "exception"
    assert result.termination_signal is None
    assert "[EXCEPTION] missing_interpreter could not start" in result.stderr


def test_run_check_records_signal_termination_diagnosis(monkeypatch: pytest.MonkeyPatch) -> None:
    command = runner.CheckCommand("terminated_check", ("python", "terminated.py"))

    def fake_command_process(*args: object, **kwargs: object) -> runner.ProcessExecution:
        return runner.ProcessExecution(-15, "", "terminated\n")

    monkeypatch.setattr(runner, "run_command_process", fake_command_process)

    result = runner.run_check(command, runner.WORKSPACE_ROOT)

    assert result.passed is False
    assert result.return_code == -15
    assert result.termination_reason == "terminated"
    assert result.termination_signal == 15
    assert result.stderr == "terminated\n"


def test_run_checks_emits_progress_witnesses(monkeypatch: pytest.MonkeyPatch) -> None:
    commands = (
        runner.CheckCommand("alpha", ("python", "alpha.py")),
        runner.CheckCommand("beta", ("python", "beta.py")),
    )
    progress_stream = io.StringIO()

    def fake_run_check(
        observed_command: runner.CheckCommand,
        workspace_root: Path = runner.WORKSPACE_ROOT,
        timeout_seconds: float | None = None,
    ) -> runner.CheckResult:
        if observed_command.name == "alpha":
            return runner.CheckResult("alpha", observed_command.args, 0, "alpha ok\n", "")
        return runner.CheckResult("beta", observed_command.args, 2, "", "beta failed\n")

    monkeypatch.setattr(runner, "run_check", fake_run_check)

    results = runner.run_checks(commands, progress_stream=progress_stream)
    progress_lines = progress_stream.getvalue().splitlines()

    assert [result.name for result in results] == ["alpha", "beta"]
    assert results[0].passed is True
    assert results[1].passed is False
    assert progress_lines[0] == "[RUN] preflight 1/2 alpha"
    assert progress_lines[1] == "[PASS] preflight 1/2 alpha return_code=0 termination=completed"
    assert progress_lines[2] == "[RUN] preflight 2/2 beta"
    assert progress_lines[3] == "[FAIL] preflight 2/2 beta return_code=2 termination=completed"


def test_select_check_commands_filters_and_shards() -> None:
    commands = (
        runner.CheckCommand("a", ("python", "a")),
        runner.CheckCommand("b", ("python", "b")),
        runner.CheckCommand("c", ("python", "c")),
        runner.CheckCommand("d", ("python", "d")),
    )

    selected = runner.select_check_commands(commands, selected_names=("d", "b"))
    shard_zero = runner.select_check_commands(commands, shard_count=2, shard_index=0)

    assert [command.name for command in selected] == ["b", "d"]
    assert [command.name for command in shard_zero] == ["a", "c"]
    with pytest.raises(ValueError):
        runner.select_check_commands(commands, selected_names=("missing",))


def test_build_receipt_records_pass_and_failure() -> None:
    pass_result = runner.CheckResult("pass_check", ("python", "--version"), 0, "ok\n", "")
    fail_result = runner.CheckResult("fail_check", ("python", "-c", "fail"), 1, "", "bad\n")

    receipt = runner.build_receipt((pass_result, fail_result), generated_at_epoch=12345.5)

    assert receipt["receipt_id"] == "workspace_governance_preflight_receipt"
    assert receipt["terminal_closure_required"] is True
    assert receipt["receipt_is_not_terminal_closure"] is True
    assert receipt["status"] == "failed"
    assert receipt["generated_at_epoch"] == 12345.5
    assert receipt["check_count"] == 2
    assert receipt["checks"][1]["passed"] is False
    assert receipt["checks"][0]["termination_reason"] == "completed"
    assert receipt["checks"][1]["termination_signal"] is None


def test_write_receipt_rejects_escape_and_non_json(tmp_path: Path) -> None:
    receipt = runner.build_receipt((runner.CheckResult("pass_check", ("python", "--version"), 0, "ok\n", ""),))

    receipt_path = runner.write_receipt(receipt, Path("receipt.json"), tmp_path)
    loaded = json.loads(receipt_path.read_text(encoding="utf-8"))

    assert loaded["status"] == "passed"
    assert receipt_path.name == "receipt.json"
    with pytest.raises(ValueError):
        runner.resolve_receipt_path(Path("../receipt.json"), tmp_path)
    with pytest.raises(ValueError):
        runner.resolve_receipt_path(Path("receipt.txt"), tmp_path)


def test_canonical_receipt_refresh_bootstraps_self_validating_example(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    commands = (
        runner.CheckCommand("alpha", ("python", "alpha.py")),
        runner.CheckCommand(runner.CANONICAL_PREFLIGHT_RECEIPT_EXAMPLE_NAME, ("python", "receipt.py")),
        runner.CheckCommand("omega", ("python", "omega.py")),
    )
    written_receipts: list[dict[str, object]] = []

    def fake_run_checks(
        observed_commands: tuple[runner.CheckCommand, ...],
        workspace_root: Path = runner.WORKSPACE_ROOT,
        max_workers: int = 1,
        timeout_seconds: float | None = None,
        progress_stream: object | None = None,
    ) -> tuple[runner.CheckResult, ...]:
        assert [command.name for command in observed_commands] == ["alpha", "omega"]
        return (
            runner.CheckResult("alpha", ("python", "alpha.py"), 0, "alpha ok\n", ""),
            runner.CheckResult("omega", ("python", "omega.py"), 0, "omega ok\n", ""),
        )

    def fake_run_check(
        observed_command: runner.CheckCommand,
        workspace_root: Path = runner.WORKSPACE_ROOT,
        timeout_seconds: float | None = None,
    ) -> runner.CheckResult:
        assert observed_command.name == runner.CANONICAL_PREFLIGHT_RECEIPT_EXAMPLE_NAME
        assert written_receipts[0]["status"] == "passed"
        return runner.CheckResult(observed_command.name, observed_command.args, 0, "receipt ok\n", "")

    def fake_write_receipt(
        receipt: dict[str, object],
        receipt_path: Path,
        workspace_root: Path = runner.WORKSPACE_ROOT,
    ) -> Path:
        written_receipts.append(receipt)
        return tmp_path / receipt_path.name

    monkeypatch.setattr(runner, "run_checks", fake_run_checks)
    monkeypatch.setattr(runner, "run_check", fake_run_check)
    monkeypatch.setattr(runner, "write_receipt", fake_write_receipt)

    results = runner.run_checks_for_canonical_receipt_refresh(commands, Path("receipt.json"), tmp_path)

    assert [result.name for result in results] == ["alpha", runner.CANONICAL_PREFLIGHT_RECEIPT_EXAMPLE_NAME, "omega"]
    assert len(written_receipts) == 2
    assert written_receipts[0]["checks"][1]["stdout"] == "STATUS: passed\n"
    assert written_receipts[1]["checks"][1]["stdout"] == "receipt ok\n"


def test_canonical_receipt_refresh_does_not_mask_prior_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    commands = (
        runner.CheckCommand("alpha", ("python", "alpha.py")),
        runner.CheckCommand(runner.CANONICAL_PREFLIGHT_RECEIPT_EXAMPLE_NAME, ("python", "receipt.py")),
    )

    def fake_run_checks(
        observed_commands: tuple[runner.CheckCommand, ...],
        workspace_root: Path = runner.WORKSPACE_ROOT,
        max_workers: int = 1,
        timeout_seconds: float | None = None,
        progress_stream: object | None = None,
    ) -> tuple[runner.CheckResult, ...]:
        return (runner.CheckResult("alpha", ("python", "alpha.py"), 1, "", "alpha failed\n"),)

    def fail_if_receipt_check_runs(
        observed_command: runner.CheckCommand,
        workspace_root: Path = runner.WORKSPACE_ROOT,
        timeout_seconds: float | None = None,
    ) -> runner.CheckResult:
        raise AssertionError("receipt example check should not run after prior failure")

    monkeypatch.setattr(runner, "run_checks", fake_run_checks)
    monkeypatch.setattr(runner, "run_check", fail_if_receipt_check_runs)

    results = runner.run_checks_for_canonical_receipt_refresh(commands, Path("receipt.json"))

    assert [result.name for result in results] == ["alpha", runner.CANONICAL_PREFLIGHT_RECEIPT_EXAMPLE_NAME]
    assert results[0].passed is False
    assert results[1].passed is False
    assert "prior checks failed" in results[1].stderr


def test_main_json_emits_machine_readable_receipt() -> None:
    exit_code = runner.main(
        [
            "--json",
            "--check",
            "workspace_governance_preflight_receipt_contract",
            "--check",
            "workspace_governance_preflight_receipt_example",
        ]
    )

    assert exit_code == 0
    assert runner.requires_full_preflight_lock((), 1) is True
    assert runner.requires_full_preflight_lock(("protocol_manifest",), 1) is False
    assert runner.allows_saved_canonical_receipt((), 1) is True
    assert runner.allows_saved_canonical_receipt(("protocol_manifest",), 1) is False


def test_main_defaults_to_bounded_parallel_preflight(monkeypatch: pytest.MonkeyPatch) -> None:
    observed_max_workers: list[int] = []

    def fake_build_check_commands() -> tuple[runner.CheckCommand, ...]:
        return (runner.CheckCommand("alpha", ("python", "alpha.py")),)

    def fake_run_checks(
        observed_commands: tuple[runner.CheckCommand, ...],
        workspace_root: Path = runner.WORKSPACE_ROOT,
        max_workers: int = 1,
        timeout_seconds: float | None = None,
        progress_stream: object | None = None,
    ) -> tuple[runner.CheckResult, ...]:
        observed_max_workers.append(max_workers)
        assert [command.name for command in observed_commands] == ["alpha"]
        return (runner.CheckResult("alpha", ("python", "alpha.py"), 0, "alpha ok\n", ""),)

    monkeypatch.setattr(runner, "build_check_commands", fake_build_check_commands)
    monkeypatch.setattr(runner, "run_checks", fake_run_checks)

    exit_code = runner.main(["--json", "--check", "alpha"])

    assert exit_code == 0
    assert runner.DEFAULT_MAX_WORKERS == 8
    assert observed_max_workers == [runner.DEFAULT_MAX_WORKERS]


def test_main_rejects_saved_receipt_for_selected_or_sharded_runs(capsys: pytest.CaptureFixture[str]) -> None:
    selected_receipt_path = runner.WORKSPACE_ROOT / ".tmp" / "partial-selected-preflight-receipt.json"
    sharded_receipt_path = runner.WORKSPACE_ROOT / ".tmp" / "partial-sharded-preflight-receipt.json"

    selected_exit_code = runner.main(
        [
            "--check",
            "protocol_manifest",
            "--receipt-path",
            str(selected_receipt_path.relative_to(runner.WORKSPACE_ROOT)),
        ]
    )
    selected_streams = capsys.readouterr()
    sharded_exit_code = runner.main(
        [
            "--shard-count",
            "2",
            "--shard-index",
            "0",
            "--receipt-path",
            str(sharded_receipt_path.relative_to(runner.WORKSPACE_ROOT)),
        ]
    )
    sharded_streams = capsys.readouterr()

    assert selected_exit_code == 1
    assert sharded_exit_code == 1
    assert "full unsharded preflight run" in selected_streams.err
    assert "full unsharded preflight run" in sharded_streams.err
    assert not selected_receipt_path.exists()
    assert not sharded_receipt_path.exists()


def test_preflight_lock_reclaims_stale_dead_pid_lock(tmp_path: Path) -> None:
    lock_path = tmp_path / "workspace-governance-preflight.lock"
    stale_payload = {
        "lock_id": runner.PREFLIGHT_LOCK_ID,
        "pid": 0,
        "created_at_epoch": 1,
    }
    lock_path.write_text(json.dumps(stale_payload), encoding="utf-8")

    with runner.PreflightLock(lock_path):
        observed_payload = json.loads(lock_path.read_text(encoding="utf-8"))

        assert observed_payload["lock_id"] == runner.PREFLIGHT_LOCK_ID
        assert observed_payload["pid"] != stale_payload["pid"]
        assert observed_payload["created_at_epoch"] > stale_payload["created_at_epoch"]

    assert not lock_path.exists()
