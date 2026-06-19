"""Purpose: verify the generated proof coverage matrix witness.

Governance scope: prevents drift between route surfaces and the proof coverage
closure ledger.
Dependencies: scripts.proof_coverage_matrix, canonical JSON fixture, repository
source tree.
Invariants: coverage levels are bounded, evidence files exist, runtime witnesses
are explicit, and canonical fixture content is generated from code.
"""

from __future__ import annotations

import json

from scripts.proof_coverage_matrix import (
    ASSURANCE_OUTPUT,
    CANONICAL_OUTPUT,
    DOC_OUTPUT,
    REPO_ROOT,
    discover_declared_routes,
    evidence_quality_report,
    operator_document,
    route_coverage_report,
    proof_coverage_matrix,
    validate_matrix_routes,
    witness_integrity_report,
)


def _load_fixture() -> dict:
    return json.loads(CANONICAL_OUTPUT.read_text(encoding="utf-8"))


def test_fixture_contract_is_canonical() -> None:
    matrix = _load_fixture()

    assert matrix == proof_coverage_matrix()
    assert matrix["schema_version"] == 1
    assert matrix["generated_by"] == "scripts/proof_coverage_matrix.py"
    assert len(matrix["surfaces"]) >= 3


def test_surface_ids_are_unique_after_generation() -> None:
    matrix = _load_fixture()
    surface_ids = [surface["surface_id"] for surface in matrix["surfaces"]]

    assert len(surface_ids) == len(set(surface_ids))
    assert surface_ids.count("operational_platform_read_models") == 1
    assert all(surface_id for surface_id in surface_ids)


def test_coverage_levels_are_bounded() -> None:
    matrix = _load_fixture()
    coverage_levels = set(matrix["coverage_levels"])
    coverage_states = set(matrix["coverage_states"])

    assert {"gap", "request_proof", "action_proof", "audit_chain"} <= coverage_levels
    assert coverage_states == {"proven", "witnessed", "unproven"}
    assert all(surface["request_proof"] in coverage_levels for surface in matrix["surfaces"])
    assert all(surface["action_proof"] in coverage_levels for surface in matrix["surfaces"])
    assert all(surface["audit"] in coverage_levels for surface in matrix["surfaces"])
    assert all(surface["coverage_state"] in coverage_states for surface in matrix["surfaces"])
    assert {"proven", "witnessed"} <= {surface["coverage_state"] for surface in matrix["surfaces"]}


def test_coverage_summary_matches_surfaces() -> None:
    matrix = _load_fixture()
    summary = matrix["coverage_summary"]
    surfaces = matrix["surfaces"]

    assert summary["surface_count"] == len(surfaces)
    assert sum(summary["by_coverage_state"].values()) == len(surfaces)
    assert sum(summary["by_request_proof"].values()) == len(surfaces)
    assert sum(summary["by_action_proof"].values()) == len(surfaces)
    assert sum(summary["by_audit"].values()) == len(surfaces)
    assert summary["by_coverage_state"]["unproven"] == 0
    assert summary["by_coverage_state"]["proven"] >= 1
    assert summary["by_coverage_state"]["witnessed"] >= 1


def test_local_assurance_refresh_surface_covers_blocked_evidence_refresh() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    witness_surfaces = {
        surface["surface_id"]: surface
        for surface in matrix["witness_integrity"]["surfaces"]
    }
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    surface = surfaces["local_assurance_refresh"]
    witnesses = set(surface["runtime_witnesses"])

    assert surface["coverage_state"] == "witnessed"
    assert "refresh_local_assurance.run_refresh" in surface["representative_paths"]
    assert "scripts/refresh_local_assurance.py" in surface["evidence_files"]
    assert "tests/test_refresh_local_assurance.py" in surface["evidence_files"]
    assert "local_assurance_refresh_includes_durable_gmail_receipts" in witnesses
    assert "local_assurance_refresh_includes_team_ops_receipts" in witnesses
    assert "local_assurance_dry_run_does_not_execute" in witnesses
    assert "local_assurance_stops_on_first_failure" in witnesses
    assert "workspace_preflight_includes_local_assurance_plan" in witnesses
    assert witness_surfaces["local_assurance_refresh"]["exact_test_anchor_count"] == 5
    assert witness_surfaces["local_assurance_refresh"]["unanchored_witness_count"] == 0
    assert closure_actions["publish_local_assurance_refresh_contract"]["status"] == "closed"


def test_evidence_quality_report_tracks_witness_strength_gaps() -> None:
    matrix = _load_fixture()
    evidence_quality = matrix["evidence_quality"]
    quality_gaps = {
        record["surface_id"]: record
        for record in evidence_quality["quality_gaps"]
    }

    assert evidence_quality == evidence_quality_report(matrix["surfaces"])
    assert sum(evidence_quality["by_strength"].values()) == len(matrix["surfaces"])
    assert evidence_quality["quality_gap_count"] == len(evidence_quality["quality_gaps"])
    assert evidence_quality["by_strength"]["strong"] >= 1
    assert evidence_quality["by_strength"]["classified_with_quality_gaps"] == 0
    assert evidence_quality["quality_gap_count"] == 0
    assert "llm_streaming" not in quality_gaps
    assert "llm_completion" not in quality_gaps
    assert "llm_chat_workflow" not in quality_gaps
    assert "cost_budget_read_models" not in quality_gaps
    assert "model_experiment_control" not in quality_gaps
    assert "policy_version_registry" not in quality_gaps
    assert "pilot_provisioning" not in quality_gaps
    assert "hosted_demo_sandbox" not in quality_gaps
    assert "gateway_webhook_ingress" not in quality_gaps
    assert "gateway_approval_resolution" not in quality_gaps
    assert "replay_determinism" not in quality_gaps
    assert "tool_invocation" not in quality_gaps
    assert "tool_permission_registry" not in quality_gaps
    assert "governed_session" not in quality_gaps
    assert "health_docs_exempt" not in quality_gaps
    assert "lineage_query_api" not in quality_gaps


def test_witness_integrity_report_tracks_exact_test_anchors() -> None:
    matrix = _load_fixture()
    witness_integrity = matrix["witness_integrity"]
    surfaces = {
        record["surface_id"]: record
        for record in witness_integrity["surfaces"]
    }

    assert witness_integrity == witness_integrity_report(matrix["surfaces"])
    assert witness_integrity["runtime_witness_count"] >= witness_integrity["exact_test_anchor_count"]
    assert witness_integrity["runtime_witness_count"] == (
        witness_integrity["exact_test_anchor_count"] + witness_integrity["unanchored_witness_count"]
    )
    assert surfaces["policy_version_registry"]["unanchored_witness_count"] == 0
    assert surfaces["pilot_provisioning"]["unanchored_witness_count"] == 0
    assert surfaces["hosted_demo_sandbox"]["unanchored_witness_count"] == 0
    assert surfaces["local_assurance_refresh"]["exact_test_anchor_count"] == 5
    assert surfaces["local_assurance_refresh"]["unanchored_witness_count"] == 0
    assert surfaces["replay_determinism"]["unanchored_witness_count"] == 0
    assert surfaces["governed_session"]["unanchored_witness_count"] == 0
    assert surfaces["lineage_query_api"]["unanchored_witness_count"] == 0
    assert surfaces["physical_action_boundary"]["unanchored_witness_count"] == 0
    assert surfaces["cost_budget_read_models"]["exact_test_anchor_count"] == 6
    assert surfaces["cost_budget_read_models"]["unanchored_witness_count"] == 0
    assert surfaces["assistant_kernel_planning"]["exact_test_anchor_count"] == 23
    assert surfaces["assistant_kernel_planning"]["unanchored_witness_count"] == 0
    assert surfaces["operator_console_read_models"]["exact_test_anchor_count"] == 18
    assert surfaces["operator_console_read_models"]["unanchored_witness_count"] == 0
    assert surfaces["model_experiment_control"]["exact_test_anchor_count"] == 7
    assert surfaces["model_experiment_control"]["unanchored_witness_count"] == 0
    assert surfaces["federated_control_plane"]["exact_test_anchor_count"] == 10
    assert surfaces["federated_control_plane"]["unanchored_witness_count"] == 0
    assert surfaces["audit_chain_api"]["exact_test_anchor_count"] == 7
    assert surfaces["audit_chain_api"]["unanchored_witness_count"] == 0
    assert surfaces["event_bus_operations"]["exact_test_anchor_count"] == 6
    assert surfaces["event_bus_operations"]["unanchored_witness_count"] == 0
    assert surfaces["api_key_lifecycle"]["exact_test_anchor_count"] == 5
    assert surfaces["api_key_lifecycle"]["unanchored_witness_count"] == 0
    assert surfaces["ops_proof_surface"]["exact_test_anchor_count"] == 6
    assert surfaces["ops_proof_surface"]["unanchored_witness_count"] == 0
    assert surfaces["trace_observability_read_models"]["exact_test_anchor_count"] == 6
    assert surfaces["trace_observability_read_models"]["unanchored_witness_count"] == 0
    assert surfaces["structured_output_validation"]["exact_test_anchor_count"] == 7
    assert surfaces["structured_output_validation"]["unanchored_witness_count"] == 0
    assert surfaces["runtime_state_persistence_lifecycle"]["exact_test_anchor_count"] == 8
    assert surfaces["runtime_state_persistence_lifecycle"]["unanchored_witness_count"] == 0
    assert surfaces["multi_agent_coordination_runtime"]["exact_test_anchor_count"] == 8
    assert surfaces["multi_agent_coordination_runtime"]["unanchored_witness_count"] == 0
    assert surfaces["governed_connector_framework"]["exact_test_anchor_count"] == 115
    assert surfaces["governed_connector_framework"]["unanchored_witness_count"] == 0
    assert surfaces["governed_background_scheduler"]["exact_test_anchor_count"] == 6
    assert surfaces["governed_background_scheduler"]["unanchored_witness_count"] == 0
    assert surfaces["agent_memory_lifecycle"]["exact_test_anchor_count"] == 6
    assert surfaces["agent_memory_lifecycle"]["unanchored_witness_count"] == 0
    assert surfaces["governance_explanation_lifecycle"]["exact_test_anchor_count"] == 7
    assert surfaces["governance_explanation_lifecycle"]["unanchored_witness_count"] == 0
    assert surfaces["agent_orchestration_lifecycle"]["exact_test_anchor_count"] == 8
    assert surfaces["agent_orchestration_lifecycle"]["unanchored_witness_count"] == 0
    assert surfaces["live_path_certification_lifecycle"]["exact_test_anchor_count"] == 8
    assert surfaces["live_path_certification_lifecycle"]["unanchored_witness_count"] == 0
    assert surfaces["software_outcome_learning"]["exact_test_anchor_count"] == 7
    assert surfaces["software_outcome_learning"]["unanchored_witness_count"] == 0
    assert surfaces["approval_engine_lifecycle"]["exact_test_anchor_count"] == 6
    assert surfaces["approval_engine_lifecycle"]["unanchored_witness_count"] == 0
    assert surfaces["job_engine_lifecycle"]["exact_test_anchor_count"] == 6
    assert surfaces["job_engine_lifecycle"]["unanchored_witness_count"] == 0
    assert surfaces["authority_obligation_mesh"]["exact_test_anchor_count"] == 5
    assert surfaces["authority_obligation_mesh"]["unanchored_witness_count"] == 0
    assert surfaces["authority_operator_controls"]["exact_test_anchor_count"] == 6
    assert surfaces["authority_operator_controls"]["unanchored_witness_count"] == 0
    assert surfaces["agent_identity"]["exact_test_anchor_count"] == 8
    assert surfaces["agent_identity"]["unanchored_witness_count"] == 0
    assert surfaces["claim_verification"]["exact_test_anchor_count"] == 6
    assert surfaces["claim_verification"]["unanchored_witness_count"] == 0
    assert surfaces["connector_self_healing"]["exact_test_anchor_count"] == 6
    assert surfaces["connector_self_healing"]["unanchored_witness_count"] == 0
    assert surfaces["workflow_mining"]["exact_test_anchor_count"] == 6
    assert surfaces["workflow_mining"]["unanchored_witness_count"] == 0
    assert surfaces["policy_prover"]["exact_test_anchor_count"] == 7
    assert surfaces["policy_prover"]["unanchored_witness_count"] == 0
    assert surfaces["temporal_evidence_freshness"]["exact_test_anchor_count"] == 8
    assert surfaces["temporal_evidence_freshness"]["unanchored_witness_count"] == 0
    assert surfaces["temporal_reapproval"]["exact_test_anchor_count"] == 8
    assert surfaces["temporal_reapproval"]["unanchored_witness_count"] == 0
    assert surfaces["temporal_monotonic_duration"]["exact_test_anchor_count"] == 8
    assert surfaces["temporal_monotonic_duration"]["unanchored_witness_count"] == 0
    assert surfaces["temporal_missed_run"]["exact_test_anchor_count"] == 9
    assert surfaces["temporal_missed_run"]["unanchored_witness_count"] == 0
    assert surfaces["temporal_recurrence_window"]["exact_test_anchor_count"] == 10
    assert surfaces["temporal_recurrence_window"]["unanchored_witness_count"] == 0
    assert surfaces["temporal_memory_refresh"]["exact_test_anchor_count"] == 7
    assert surfaces["temporal_memory_refresh"]["unanchored_witness_count"] == 0
    assert surfaces["policy_proof_report"]["exact_test_anchor_count"] == 6
    assert surfaces["policy_proof_report"]["unanchored_witness_count"] == 0
    assert surfaces["agentic_service_harness_read_models"]["exact_test_anchor_count"] == 12
    assert surfaces["agentic_service_harness_read_models"]["unanchored_witness_count"] == 0
    assert surfaces["agentic_service_harness_authority_transitions"]["exact_test_anchor_count"] == 6
    assert surfaces["agentic_service_harness_authority_transitions"]["unanchored_witness_count"] == 0
    assert surfaces["code_intelligence_operator_read_model"]["exact_test_anchor_count"] >= 5
    assert surfaces["code_intelligence_operator_read_model"]["unanchored_witness_count"] == 0
    assert surfaces["data_export_lifecycle"]["exact_test_anchor_count"] >= 4
    assert surfaces["data_export_lifecycle"]["unanchored_witness_count"] == 0
    assert surfaces["prompt_template_lifecycle"]["unanchored_witness_count"] == 0
    assert surfaces["operational_platform_read_models"]["exact_test_anchor_count"] >= 25
    assert surfaces["operational_platform_read_models"]["unanchored_witness_count"] == 0
    assert surfaces["trust_ledger"]["unanchored_witness_count"] == 0
    assert surfaces["conversation_memory_lifecycle"]["unanchored_witness_count"] == 0
    assert surfaces["gateway_runtime_witness"]["unanchored_witness_count"] == 0
    assert surfaces["workflow_execution_lifecycle"]["unanchored_witness_count"] == 0
    assert surfaces["webhooks_proof_surface"]["unanchored_witness_count"] == 0
    assert surfaces["tenant_governance_lifecycle"]["unanchored_witness_count"] == 0
    assert surfaces["multimodal_operating_layer"]["unanchored_witness_count"] == 0
    assert surfaces["runtime_conformance_attestation"]["unanchored_witness_count"] == 0
    assert surfaces["runtime_reflex_engine"]["unanchored_witness_count"] == 0
    assert surfaces["runtime_reflex_engine"]["exact_test_anchor_count"] == 9
    assert surfaces["finance_approval_packets"]["unanchored_witness_count"] == 0
    assert surfaces["god_mode_lifecycle"]["unanchored_witness_count"] == 0
    assert surfaces["agent_adapter_protocol"]["exact_test_anchor_count"] == 14
    assert surfaces["agent_adapter_protocol"]["unanchored_witness_count"] == 0
    assert surfaces["effect_assurance_graph_commit"]["exact_test_anchor_count"] == 6
    assert surfaces["effect_assurance_graph_commit"]["unanchored_witness_count"] == 0
    assert surfaces["proof_route_gap_triage"]["exact_test_anchor_count"] == 4
    assert surfaces["proof_route_gap_triage"]["unanchored_witness_count"] == 0
    assert surfaces["tool_registry_read_models"]["unanchored_witness_count"] == 0
    assert surfaces["tool_permission_registry"]["unanchored_witness_count"] == 0
    assert surfaces["tool_permission_registry"]["exact_test_anchor_count"] == 11
    assert surfaces["gateway_capability_fabric"]["unanchored_witness_count"] == 0
    assert surfaces["gateway_capability_fabric"]["exact_test_anchor_count"] == 28
    assert surfaces["component_autopsy"]["unanchored_witness_count"] == 0
    assert surfaces["component_autopsy"]["exact_test_anchor_count"] == 5
    assert surfaces["component_request_simulator"]["unanchored_witness_count"] == 0
    assert surfaces["component_request_simulator"]["exact_test_anchor_count"] == 5
    assert surfaces["component_bundle_compiler"]["unanchored_witness_count"] == 0
    assert surfaces["component_bundle_compiler"]["exact_test_anchor_count"] == 5
    assert surfaces["component_route_family_ownership"]["unanchored_witness_count"] == 0
    assert surfaces["component_route_family_ownership"]["exact_test_anchor_count"] == 5
    assert surfaces["component_route_family_promotion_preflight"]["unanchored_witness_count"] == 0
    assert surfaces["component_route_family_promotion_preflight"]["exact_test_anchor_count"] == 5
    assert surfaces["component_route_family_promotion_witness_requirements"]["unanchored_witness_count"] == 0
    assert surfaces["component_route_family_promotion_witness_requirements"]["exact_test_anchor_count"] == 5
    assert surfaces["component_route_family_promotion_witness_evidence"]["unanchored_witness_count"] == 0
    assert surfaces["component_route_family_promotion_witness_evidence"]["exact_test_anchor_count"] == 5
    assert surfaces["component_route_family_promotion_approval_candidates"]["unanchored_witness_count"] == 0
    assert surfaces["component_route_family_promotion_approval_candidates"]["exact_test_anchor_count"] == 5
    assert surfaces["component_route_family_promotion_approval_intake"]["unanchored_witness_count"] == 0
    assert surfaces["component_route_family_promotion_approval_intake"]["exact_test_anchor_count"] == 5
    assert surfaces["component_route_family_promotion_submitted_evidence_verifier"]["unanchored_witness_count"] == 0
    assert surfaces["component_route_family_promotion_submitted_evidence_verifier"]["exact_test_anchor_count"] == 5
    assert surfaces["component_route_family_promotion_submitted_evidence_records"]["unanchored_witness_count"] == 0
    assert surfaces["component_route_family_promotion_submitted_evidence_records"]["exact_test_anchor_count"] == 5
    assert surfaces["component_route_family_promotion_submitted_evidence_payload_examples"]["unanchored_witness_count"] == 0
    assert surfaces["component_route_family_promotion_submitted_evidence_payload_examples"]["exact_test_anchor_count"] == 6
    assert surfaces["component_route_family_promotion_operator_submitted_evidence_records"]["unanchored_witness_count"] == 0
    assert surfaces["component_route_family_promotion_operator_submitted_evidence_records"]["exact_test_anchor_count"] == 6
    assert surfaces["component_route_family_promotion_gate_satisfaction_evaluator"]["unanchored_witness_count"] == 0
    assert surfaces["component_route_family_promotion_gate_satisfaction_evaluator"]["exact_test_anchor_count"] == 6
    assert surfaces["component_route_family_promotion_authority_decision_report"]["unanchored_witness_count"] == 0
    assert surfaces["component_route_family_promotion_authority_decision_report"]["exact_test_anchor_count"] == 6
    assert surfaces["component_route_family_promotion_route_binding_decision_report"]["unanchored_witness_count"] == 0
    assert surfaces["component_route_family_promotion_route_binding_decision_report"]["exact_test_anchor_count"] == 6
    assert (
        surfaces["component_route_family_promotion_lifecycle_transition_decision_report"]["unanchored_witness_count"]
        == 0
    )
    assert (
        surfaces["component_route_family_promotion_lifecycle_transition_decision_report"]["exact_test_anchor_count"]
        == 6
    )
    assert (
        surfaces["component_route_family_promotion_authority_upgrade_witness_decision_report"][
            "unanchored_witness_count"
        ]
        == 0
    )
    assert (
        surfaces["component_route_family_promotion_authority_upgrade_witness_decision_report"][
            "exact_test_anchor_count"
        ]
        == 6
    )
    assert (
        surfaces["component_route_family_promotion_product_ownership_decision_report"]["unanchored_witness_count"]
        == 0
    )
    assert (
        surfaces["component_route_family_promotion_product_ownership_decision_report"]["exact_test_anchor_count"]
        == 6
    )
    assert (
        surfaces["component_route_family_promotion_terminal_closure_denial_report"]["unanchored_witness_count"]
        == 0
    )
    assert (
        surfaces["component_route_family_promotion_terminal_closure_denial_report"]["exact_test_anchor_count"]
        == 6
    )
    assert (
        surfaces["component_route_family_promotion_missing_evidence_ledger"]["unanchored_witness_count"]
        == 0
    )
    assert (
        surfaces["component_route_family_promotion_missing_evidence_ledger"]["exact_test_anchor_count"]
        == 6
    )
    assert (
        surfaces["component_route_family_promotion_router_inventory_delta_candidate"]["unanchored_witness_count"]
        == 0
    )
    assert (
        surfaces["component_route_family_promotion_router_inventory_delta_candidate"]["exact_test_anchor_count"]
        == 6
    )
    assert (
        surfaces["component_route_family_promotion_router_inventory_delta_witness_requirements"][
            "unanchored_witness_count"
        ]
        == 0
    )
    assert (
        surfaces["component_route_family_promotion_router_inventory_delta_witness_requirements"][
            "exact_test_anchor_count"
        ]
        == 6
    )
    assert (
        surfaces["component_route_family_promotion_router_inventory_delta_witness_minting_preflight"][
            "unanchored_witness_count"
        ]
        == 0
    )
    assert (
        surfaces["component_route_family_promotion_router_inventory_delta_witness_minting_preflight"][
            "exact_test_anchor_count"
        ]
        == 6
    )
    assert (
        surfaces["component_route_family_promotion_router_inventory_delta_witness_minting_denial_report"][
            "unanchored_witness_count"
        ]
        == 0
    )
    assert (
        surfaces["component_route_family_promotion_router_inventory_delta_witness_minting_denial_report"][
            "exact_test_anchor_count"
        ]
        == 6
    )
    assert (
        surfaces["component_route_family_promotion_router_inventory_delta_witness_remediation_plan"][
            "unanchored_witness_count"
        ]
        == 0
    )
    assert (
        surfaces["component_route_family_promotion_router_inventory_delta_witness_remediation_plan"][
            "exact_test_anchor_count"
        ]
        == 6
    )
    assert (
        surfaces["component_route_family_promotion_router_inventory_delta_witness_remediation_evidence_request"][
            "unanchored_witness_count"
        ]
        == 0
    )
    assert (
        surfaces["component_route_family_promotion_router_inventory_delta_witness_remediation_evidence_request"][
            "exact_test_anchor_count"
        ]
        == 6
    )
    assert (
        surfaces[
            "component_route_family_promotion_router_inventory_delta_witness_remediation_evidence_request_status_ledger"
        ]["unanchored_witness_count"]
        == 0
    )
    assert (
        surfaces[
            "component_route_family_promotion_router_inventory_delta_witness_remediation_evidence_request_status_ledger"
        ]["exact_test_anchor_count"]
        == 6
    )
    assert surfaces["component_graph"]["unanchored_witness_count"] == 0
    assert surfaces["component_graph"]["exact_test_anchor_count"] == 5
    assert surfaces["component_dead_detector"]["unanchored_witness_count"] == 0
    assert surfaces["component_dead_detector"]["exact_test_anchor_count"] == 5
    assert surfaces["component_lifecycle_transition_receipts"]["unanchored_witness_count"] == 0
    assert surfaces["component_lifecycle_transition_receipts"]["exact_test_anchor_count"] == 5
    assert surfaces["component_authority_envelope_witnesses"]["unanchored_witness_count"] == 0
    assert surfaces["component_authority_envelope_witnesses"]["exact_test_anchor_count"] == 5
    assert surfaces["capability_worker_execution"]["unanchored_witness_count"] == 0
    assert surfaces["capability_worker_execution"]["exact_test_anchor_count"] == 7
    assert surfaces["capability_plan_evidence_bundle"]["unanchored_witness_count"] == 0
    assert surfaces["capability_plan_evidence_bundle"]["exact_test_anchor_count"] == 4
    assert surfaces["llm_completion"]["unanchored_witness_count"] == 0
    assert surfaces["llm_completion"]["exact_test_anchor_count"] == 7
    assert surfaces["llm_chat_workflow"]["unanchored_witness_count"] == 0
    assert surfaces["llm_chat_workflow"]["exact_test_anchor_count"] == 7
    assert surfaces["temporal_kernel"]["unanchored_witness_count"] == 0
    assert surfaces["temporal_kernel"]["exact_test_anchor_count"] == 16
    assert surfaces["networked_worker_mesh"]["unanchored_witness_count"] == 0
    assert surfaces["networked_worker_mesh"]["exact_test_anchor_count"] == 13
    assert surfaces["read_only_first_worker_path"]["unanchored_witness_count"] == 0
    assert surfaces["read_only_first_worker_path"]["exact_test_anchor_count"] == 11
    assert surfaces["read_only_document_worker_path"]["unanchored_witness_count"] == 0
    assert surfaces["read_only_document_worker_path"]["exact_test_anchor_count"] == 10
    assert surfaces["read_only_search_worker_path"]["unanchored_witness_count"] == 0
    assert surfaces["read_only_search_worker_path"]["exact_test_anchor_count"] == 11
    assert surfaces["task_queue_lifecycle"]["unanchored_witness_count"] == 0
    assert surfaces["task_queue_lifecycle"]["exact_test_anchor_count"] == 11
    assert surfaces["software_dev_capability_pack"]["unanchored_witness_count"] == 0
    assert surfaces["software_dev_capability_pack"]["exact_test_anchor_count"] == 16
    assert surfaces["agentic_control_capability_pack"]["unanchored_witness_count"] == 0
    assert surfaces["agentic_control_capability_pack"]["exact_test_anchor_count"] == 5
    assert surfaces["governed_operational_intelligence"]["unanchored_witness_count"] == 0
    assert surfaces["governed_operational_intelligence"]["exact_test_anchor_count"] == 11
    assert surfaces["runbook_learning_lifecycle"]["unanchored_witness_count"] == 0
    assert surfaces["runbook_learning_lifecycle"]["exact_test_anchor_count"] == 11
    assert surfaces["temporal_accepted_risk_expiry"]["unanchored_witness_count"] == 0
    assert surfaces["temporal_accepted_risk_expiry"]["exact_test_anchor_count"] == 9
    assert surfaces["temporal_dispatch_window"]["unanchored_witness_count"] == 0
    assert surfaces["temporal_dispatch_window"]["exact_test_anchor_count"] == 9
    assert surfaces["temporal_budget_window"]["unanchored_witness_count"] == 0
    assert surfaces["temporal_budget_window"]["exact_test_anchor_count"] == 9
    assert surfaces["temporal_causal_order"]["unanchored_witness_count"] == 0
    assert surfaces["temporal_causal_order"]["exact_test_anchor_count"] == 9
    assert surfaces["temporal_credential_expiry"]["unanchored_witness_count"] == 0
    assert surfaces["temporal_credential_expiry"]["exact_test_anchor_count"] == 11
    assert surfaces["temporal_retention_window"]["unanchored_witness_count"] == 0
    assert surfaces["temporal_retention_window"]["exact_test_anchor_count"] == 12
    assert surfaces["github_check_run_write_receipts"]["unanchored_witness_count"] == 0
    assert surfaces["github_check_run_write_receipts"]["exact_test_anchor_count"] == 8
    assert surfaces["github_app_token_exchange_receipts"]["unanchored_witness_count"] == 0
    assert surfaces["github_app_token_exchange_receipts"]["exact_test_anchor_count"] == 8
    assert surfaces["github_action_execution_receipts"]["unanchored_witness_count"] == 0
    assert surfaces["github_action_execution_receipts"]["exact_test_anchor_count"] == 9
    assert surfaces["github_branch_protection_reconcile_receipts"]["unanchored_witness_count"] == 0
    assert surfaces["github_branch_protection_reconcile_receipts"]["exact_test_anchor_count"] == 10
    assert surfaces["distributed_lease_claim_receipts"]["unanchored_witness_count"] == 0
    assert surfaces["distributed_lease_claim_receipts"]["exact_test_anchor_count"] == 14
    assert surfaces["distributed_lease_adapter_registry_receipts"]["unanchored_witness_count"] == 0
    assert surfaces["distributed_lease_adapter_registry_receipts"]["exact_test_anchor_count"] == 8
    assert surfaces["oidc_jwks_refresh_evidence"]["unanchored_witness_count"] == 0
    assert surfaces["oidc_jwks_refresh_evidence"]["exact_test_anchor_count"] == 6
    assert surfaces["trusted_identity_header_boundary"]["unanchored_witness_count"] == 0
    assert surfaces["trusted_identity_header_boundary"]["exact_test_anchor_count"] == 7
    assert surfaces["temporal_sla"]["unanchored_witness_count"] == 0
    assert surfaces["temporal_sla"]["exact_test_anchor_count"] == 10
    assert surfaces["temporal_resolution"]["unanchored_witness_count"] == 0
    assert surfaces["temporal_resolution"]["exact_test_anchor_count"] == 10
    assert surfaces["temporal_scheduler"]["unanchored_witness_count"] == 0
    assert surfaces["temporal_scheduler"]["exact_test_anchor_count"] == 10
    assert surfaces["temporal_retry_window"]["unanchored_witness_count"] == 0
    assert surfaces["temporal_retry_window"]["exact_test_anchor_count"] == 10
    assert surfaces["temporal_rate_limit_window"]["unanchored_witness_count"] == 0
    assert surfaces["temporal_rate_limit_window"]["exact_test_anchor_count"] == 10
    assert surfaces["temporal_lease_window"]["unanchored_witness_count"] == 0
    assert surfaces["temporal_lease_window"]["exact_test_anchor_count"] == 10
    assert surfaces["temporal_memory"]["unanchored_witness_count"] == 0
    assert surfaces["temporal_memory"]["exact_test_anchor_count"] == 9
    assert surfaces["capability_forge"]["unanchored_witness_count"] == 0
    assert surfaces["capability_forge"]["exact_test_anchor_count"] == 10
    assert surfaces["capability_maturity_assessment"]["unanchored_witness_count"] == 0
    assert surfaces["capability_maturity_assessment"]["exact_test_anchor_count"] == 9
    assert surfaces["capability_maturity"]["unanchored_witness_count"] == 0
    assert surfaces["capability_maturity"]["exact_test_anchor_count"] == 5
    assert surfaces["domain_operating_pack"]["unanchored_witness_count"] == 0
    assert surfaces["domain_operating_pack"]["exact_test_anchor_count"] == 5
    assert surfaces["collaboration_cases"]["unanchored_witness_count"] == 0
    assert surfaces["collaboration_cases"]["exact_test_anchor_count"] == 5
    assert surfaces["memory_lattice"]["unanchored_witness_count"] == 0
    assert surfaces["memory_lattice"]["exact_test_anchor_count"] == 9
    assert surfaces["coordination_checkpoint_lifecycle"]["unanchored_witness_count"] == 0
    assert surfaces["coordination_checkpoint_lifecycle"]["exact_test_anchor_count"] == 10
    assert surfaces["production_evidence_plane"]["unanchored_witness_count"] == 0
    assert surfaces["production_evidence_plane"]["exact_test_anchor_count"] == 10
    assert surfaces["capability_manifest_registry"]["unanchored_witness_count"] == 0
    assert surfaces["capability_manifest_registry"]["exact_test_anchor_count"] == 9


def test_holistic_loop_kernel_witness_labels_have_exact_anchors() -> None:
    matrix = _load_fixture()
    integrity = {
        record["surface_id"]: record
        for record in matrix["witness_integrity"]["surfaces"]
    }
    holistic_integrity = integrity["holistic_loop_read_model_kernel"]
    anchors_by_witness = {
        record["witness"]: set(record["anchors"])
        for record in holistic_integrity["anchored_witnesses"]
    }

    assert holistic_integrity["runtime_witness_count"] == 51
    assert holistic_integrity["exact_test_anchor_count"] == 51
    assert holistic_integrity["unanchored_witness_count"] == 0
    assert holistic_integrity["unanchored_witnesses"] == []
    assert anchors_by_witness["registered_loops_expose_governed_manifest_fields"] == {
        "mcoi/tests/test_holistic_loop_kernel.py::test_default_registry_exposes_governed_loop_manifests"
    }
    assert anchors_by_witness["missing_required_evidence_is_reported_as_blocker"] == {
        "mcoi/tests/test_holistic_loop_kernel.py::test_missing_evidence_is_reported_as_blocker_not_success"
    }
    assert anchors_by_witness["closure_report_blocks_incomplete_evidence"] == {
        "mcoi/tests/test_holistic_loop_kernel.py::test_loop_receipt_and_closure_report_contracts_are_explicit"
    }
    assert anchors_by_witness["loop_registry_rejects_duplicate_loop_ids"] == {
        "mcoi/tests/test_holistic_loop_kernel.py::test_loop_registry_rejects_duplicate_loop_ids"
    }
    assert anchors_by_witness["loop_status_bindings_explain_projected_status"] == {
        (
            "mcoi/tests/test_holistic_loop_kernel.py::"
            "test_loop_status_bindings_explain_projected_status_without_execution"
        )
    }
    assert anchors_by_witness["loop_transition_bindings_describe_allowed_transitions"] == {
        (
            "mcoi/tests/test_holistic_loop_kernel.py::"
            "test_loop_transition_bindings_describe_allowed_transitions_without_execution"
        )
    }
    assert anchors_by_witness["loop_mode_bindings_cover_allowed_modes"] == {
        (
            "mcoi/tests/test_holistic_loop_kernel.py::"
            "test_loop_mode_bindings_cover_allowed_modes_without_execution"
        )
    }
    assert anchors_by_witness["loop_closure_condition_bindings_cover_conditions"] == {
        (
            "mcoi/tests/test_holistic_loop_kernel.py::"
            "test_loop_closure_condition_bindings_cover_conditions_without_execution"
        )
    }
    assert anchors_by_witness["loop_closure_evidence_pack_aggregates_closure_inputs"] == {
        (
            "mcoi/tests/test_holistic_loop_kernel.py::"
            "test_loop_closure_evidence_pack_aggregates_required_closure_inputs"
        )
    }
    assert anchors_by_witness["loop_operator_closure_readiness_view_summarizes_next_action"] == {
        (
            "mcoi/tests/test_holistic_loop_kernel.py::"
            "test_loop_operator_closure_readiness_view_summarizes_blockers_and_next_action"
        )
    }
    assert anchors_by_witness["loop_proof_obligation_view_groups_required_proof_inputs"] == {
        (
            "mcoi/tests/test_holistic_loop_kernel.py::"
            "test_loop_proof_obligation_view_groups_required_proof_inputs"
        )
    }
    assert anchors_by_witness[
        "loop_audit_evolution_view_groups_receipts_blockers_and_learning_refs"
    ] == {
        (
            "mcoi/tests/test_holistic_loop_kernel.py::"
            "test_loop_audit_evolution_view_groups_receipts_blockers_and_learning_refs"
        )
    }
    assert anchors_by_witness[
        "loop_recovery_readiness_view_groups_rollback_blockers_and_lineage_refs"
    ] == {
        (
            "mcoi/tests/test_holistic_loop_kernel.py::"
            "test_loop_recovery_readiness_view_groups_rollback_blockers_and_lineage_refs"
        )
    }
    assert anchors_by_witness["loop_authority_bindings_cover_required_authority"] == {
        (
            "mcoi/tests/test_holistic_loop_kernel.py::"
            "test_loop_authority_bindings_cover_required_authority_without_execution"
        )
    }
    assert anchors_by_witness["loop_risk_bindings_cover_risk_class"] == {
        (
            "mcoi/tests/test_holistic_loop_kernel.py::"
            "test_loop_risk_bindings_cover_risk_class_without_execution"
        )
    }
    assert anchors_by_witness["loop_rollback_bindings_cover_recovery_policy"] == {
        (
            "mcoi/tests/test_holistic_loop_kernel.py::"
            "test_loop_rollback_bindings_cover_recovery_policy_without_execution"
        )
    }
    assert anchors_by_witness["loop_learning_bindings_cover_learning_policy"] == {
        (
            "mcoi/tests/test_holistic_loop_kernel.py::"
            "test_loop_learning_bindings_cover_learning_policy_without_execution"
        )
    }
    assert anchors_by_witness["loop_evidence_bindings_cover_required_evidence"] == {
        (
            "mcoi/tests/test_holistic_loop_kernel.py::"
            "test_loop_evidence_bindings_cover_required_evidence_without_execution"
        )
    }
    assert anchors_by_witness["loop_step_receipt_trail_is_read_only"] == {
        (
            "mcoi/tests/test_holistic_loop_kernel.py::"
            "test_loop_summary_exposes_read_only_step_receipt_trail"
        )
    }
    assert anchors_by_witness["loop_receipt_lineage_bindings_cover_step_receipts"] == {
        (
            "mcoi/tests/test_holistic_loop_kernel.py::"
            "test_loop_receipt_lineage_bindings_cover_step_receipts_without_emission"
        )
    }
    assert anchors_by_witness["loop_closure_report_blocks_terminal_closure"] == {
        (
            "mcoi/tests/test_holistic_loop_kernel.py::"
            "test_loop_summary_rejects_terminal_or_mismatched_closure_report"
        )
    }
    assert anchors_by_witness["loop_read_model_endpoint_is_read_only"] == {
        "mcoi/tests/test_holistic_loop_router.py::test_loop_read_model_has_no_mutation_companion"
    }
    assert anchors_by_witness["loop_http_surface_validator_rejects_mutation_routes"] == {
        "tests/test_validate_holistic_loop_http_surface.py::test_route_method_validation_rejects_mutation_route"
    }
    assert anchors_by_witness["loop_kernel_v1_golden_snapshot_matches_current_report"] == {
        (
            "tests/test_validate_holistic_loop_kernel_freeze.py::"
            "test_holistic_loop_kernel_freeze_contract_passes"
        )
    }
    assert anchors_by_witness["loop_kernel_v1_report_schema_http_parity_holds"] == {
        (
            "tests/test_validate_holistic_loop_kernel_freeze.py::"
            "test_http_payload_normalizes_to_report_contract"
        )
    }
    assert anchors_by_witness["loop_kernel_v1_extension_policy_is_documented"] == {
        (
            "tests/test_validate_holistic_loop_kernel_freeze.py::"
            "test_kernel_v1_policy_doc_contains_freeze_rules"
        )
    }
    assert anchors_by_witness["holistic_loop_witness_integrity_has_zero_unanchored_labels"] == {
        (
            "tests/test_validate_holistic_loop_kernel_freeze.py::"
            "test_holistic_loop_witness_integrity_has_zero_unanchored_labels"
        )
    }
    assert anchors_by_witness["holistic_loop_extension_admission_guards_default_registry"] == {
        (
            "tests/test_validate_holistic_loop_extension_admission.py::"
            "test_holistic_loop_extension_admission_guards_default_registry"
        )
    }
    assert anchors_by_witness["holistic_loop_candidate_map_lists_candidate_surfaces"] == {
        (
            "tests/test_report_holistic_loop_candidate_map.py::"
            "test_holistic_loop_candidate_map_lists_candidate_surfaces"
        )
    }
    assert anchors_by_witness["holistic_loop_candidate_map_is_read_only_non_terminal"] == {
        (
            "tests/test_report_holistic_loop_candidate_map.py::"
            "test_holistic_loop_candidate_map_is_read_only_non_terminal"
        )
    }
    assert anchors_by_witness[
        "holistic_loop_admission_closure_reports_no_pending_candidates"
    ] == {
        (
            "tests/test_report_holistic_loop_admission_closure.py::"
            "test_holistic_loop_admission_closure_reports_no_pending_candidates"
        )
    }
    assert anchors_by_witness["holistic_loop_audit_proof_registered_in_default_read_model"] == {
        (
            "mcoi/tests/test_holistic_loop_kernel.py::"
            "test_audit_proof_loop_is_registered_read_only_and_blocked"
        )
    }
    assert anchors_by_witness["holistic_loop_uao_registered_in_default_read_model"] == {
        (
            "mcoi/tests/test_holistic_loop_kernel.py::"
            "test_universal_action_orchestration_loop_is_registered_read_only_and_blocked"
        )
    }
    assert anchors_by_witness["holistic_loop_workflow_registered_in_default_read_model"] == {
        (
            "mcoi/tests/test_holistic_loop_kernel.py::"
            "test_workflow_execution_loop_is_registered_read_only_and_blocked"
        )
    }
    assert anchors_by_witness["holistic_loop_governed_symbolic_registered_in_default_read_model"] == {
        (
            "mcoi/tests/test_holistic_loop_kernel.py::"
            "test_governed_symbolic_loop_is_registered_read_only_and_blocked"
        )
    }
    assert anchors_by_witness["holistic_loop_uao_admission_dossier_builds_proposed_manifest"] == {
        (
            "tests/test_report_holistic_loop_uao_admission_dossier.py::"
            "test_uao_admission_dossier_builds_proposed_manifest"
        )
    }
    assert anchors_by_witness["holistic_loop_uao_admission_dossier_reports_registry_admission"] == {
        (
            "tests/test_report_holistic_loop_uao_admission_dossier.py::"
            "test_uao_admission_dossier_reports_registry_admission"
        )
    }
    assert anchors_by_witness["holistic_loop_uao_admission_dossier_blocks_registration_effects"] == {
        (
            "tests/test_report_holistic_loop_uao_admission_dossier.py::"
            "test_uao_admission_dossier_does_not_register_or_mutate_runtime"
        )
    }
    assert anchors_by_witness["holistic_loop_workflow_admission_dossier_builds_proposed_manifest"] == {
        (
            "tests/test_report_holistic_loop_workflow_admission_dossier.py::"
            "test_workflow_admission_dossier_builds_proposed_manifest"
        )
    }
    assert anchors_by_witness[
        "holistic_loop_workflow_admission_dossier_reports_registry_admission"
    ] == {
        (
            "tests/test_report_holistic_loop_workflow_admission_dossier.py::"
            "test_workflow_admission_dossier_reports_registry_admission"
        )
    }
    assert anchors_by_witness["holistic_loop_workflow_admission_dossier_blocks_registration_effects"] == {
        (
            "tests/test_report_holistic_loop_workflow_admission_dossier.py::"
            "test_workflow_admission_dossier_does_not_register_or_mutate_runtime"
        )
    }
    assert anchors_by_witness["holistic_loop_authority_admission_dossier_builds_proposed_manifest"] == {
        (
            "tests/test_report_holistic_loop_authority_admission_dossier.py::"
            "test_authority_admission_dossier_builds_proposed_manifest"
        )
    }
    assert anchors_by_witness["holistic_loop_authority_registered_in_default_read_model"] == {
        (
            "mcoi/tests/test_holistic_loop_kernel.py::"
            "test_authority_obligation_loop_is_registered_read_only_and_blocked"
        )
    }
    assert anchors_by_witness[
        "holistic_loop_authority_admission_dossier_reports_registry_admission"
    ] == {
        (
            "tests/test_report_holistic_loop_authority_admission_dossier.py::"
            "test_authority_admission_dossier_reports_registry_admission"
        )
    }
    assert anchors_by_witness["holistic_loop_authority_admission_dossier_blocks_registration_effects"] == {
        (
            "tests/test_report_holistic_loop_authority_admission_dossier.py::"
            "test_authority_admission_dossier_does_not_register_or_mutate_runtime"
        )
    }
    assert anchors_by_witness[
        "holistic_loop_audit_proof_admission_dossier_builds_proposed_manifest"
    ] == {
        (
            "tests/test_report_holistic_loop_audit_proof_admission_dossier.py::"
            "test_audit_proof_admission_dossier_builds_proposed_manifest"
        )
    }
    assert anchors_by_witness[
        "holistic_loop_audit_proof_admission_dossier_reports_registry_admission"
    ] == {
        (
            "tests/test_report_holistic_loop_audit_proof_admission_dossier.py::"
            "test_audit_proof_admission_dossier_reports_registry_admission"
        )
    }
    assert anchors_by_witness[
        "holistic_loop_audit_proof_admission_dossier_blocks_registration_effects"
    ] == {
        (
            "tests/test_report_holistic_loop_audit_proof_admission_dossier.py::"
            "test_audit_proof_admission_dossier_does_not_register_or_mutate_runtime"
        )
    }
    assert anchors_by_witness[
        "holistic_loop_governed_symbolic_admission_dossier_builds_proposed_manifest"
    ] == {
        (
            "tests/test_report_holistic_loop_governed_symbolic_admission_dossier.py::"
            "test_governed_symbolic_admission_dossier_builds_proposed_manifest"
        )
    }
    assert anchors_by_witness[
        "holistic_loop_governed_symbolic_admission_dossier_reports_registry_admission"
    ] == {
        (
            "tests/test_report_holistic_loop_governed_symbolic_admission_dossier.py::"
            "test_governed_symbolic_admission_dossier_reports_registry_admission"
        )
    }
    assert anchors_by_witness[
        "holistic_loop_governed_symbolic_admission_dossier_blocks_registration_effects"
    ] == {
        (
            "tests/test_report_holistic_loop_governed_symbolic_admission_dossier.py::"
            "test_governed_symbolic_admission_dossier_does_not_register_or_mutate_runtime"
        )
    }


def test_tool_permission_registry_surface_covers_durable_persistence() -> None:
    matrix = _load_fixture()
    surface = {item["surface_id"]: item for item in matrix["surfaces"]}["tool_permission_registry"]
    evidence_files = set(surface["evidence_files"])
    witnesses = set(surface["runtime_witnesses"])

    assert "mcoi/mcoi_runtime/app/tool_permission_integration.py" in evidence_files
    assert "file_tool_permission_registry_persists_and_reloads_permissions" in witnesses
    assert "file_tool_permission_registry_rejects_tampered_permission_identity" in witnesses
    assert "tool_permission_registry_integration_selects_memory_or_file" in witnesses
    assert "tool_permission_registry_path_validation_requires_absolute_json_path" in witnesses


def test_declared_routes_have_explicit_coverage_classification() -> None:
    matrix = _load_fixture()
    report = matrix["route_coverage"]
    declared_report = route_coverage_report(matrix["surfaces"], discover_declared_routes())

    assert report == declared_report
    assert report["route_count"] == len(report["routes"])
    assert sum(report["by_coverage_state"].values()) == report["route_count"]
    assert report["unclassified_route_count"] == report["by_coverage_state"]["unproven"]
    assert all(record["coverage_state"] in matrix["coverage_states"] for record in report["routes"])
    assert all(record["surface_id"] for record in report["routes"])
    assert report["unclassified_route_count"] == 0
    assert all(record["surface_id"] != "unclassified_declared_route" for record in report["routes"])
    assert all(record["coverage_state"] != "unproven" for record in report["routes"])


def test_component_bundle_compiler_surface_is_preview_only() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    bundle_surface = surfaces["component_bundle_compiler"]
    witnesses = set(bundle_surface["runtime_witnesses"])

    assert bundle_surface["coverage_state"] == "proven"
    assert bundle_surface["representative_paths"] == ["component_bundle_compilation"]
    assert "mcoi/mcoi_runtime/app/component_bundle_compiler.py" in bundle_surface["evidence_files"]
    assert "schemas/component_bundle_compilation.schema.json" in bundle_surface["evidence_files"]
    assert "component_bundle_compiler_compiles_personal_assistant_v0_preview" in witnesses
    assert "component_bundle_compiler_rejects_live_authority_drift" in witnesses
    assert closure_actions["publish_component_bundle_compiler"]["status"] == "closed"


def test_component_route_family_ownership_surface_is_read_only() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    ownership_surface = surfaces["component_route_family_ownership"]
    witnesses = set(ownership_surface["runtime_witnesses"])

    assert ownership_surface["coverage_state"] == "proven"
    assert ownership_surface["representative_paths"] == ["component_route_family_ownership"]
    assert "mcoi/mcoi_runtime/app/component_route_family_ownership.py" in ownership_surface["evidence_files"]
    assert "schemas/component_route_family_ownership.schema.json" in ownership_surface["evidence_files"]
    assert "component_route_family_ownership_schema_valid" in witnesses
    assert "component_route_family_ownership_blocks_platform_promotion_overclaim" in witnesses
    assert closure_actions["publish_component_route_family_ownership"]["status"] == "closed"


def test_component_route_family_promotion_preflight_surface_is_blocked() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    preflight_surface = surfaces["component_route_family_promotion_preflight"]
    witnesses = set(preflight_surface["runtime_witnesses"])

    assert preflight_surface["coverage_state"] == "proven"
    assert preflight_surface["representative_paths"] == ["component_route_family_promotion_preflight"]
    assert "mcoi/mcoi_runtime/app/component_route_family_promotion_preflight.py" in preflight_surface["evidence_files"]
    assert "schemas/component_route_family_promotion_preflight.schema.json" in preflight_surface["evidence_files"]
    assert "component_route_family_promotion_preflight_schema_valid" in witnesses
    assert "component_route_family_promotion_preflight_blocks_authority_overclaim" in witnesses
    assert closure_actions["publish_component_route_family_promotion_preflight"]["status"] == "closed"


def test_component_route_family_promotion_witness_requirements_surface_is_blocked() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    requirements_surface = surfaces["component_route_family_promotion_witness_requirements"]
    witnesses = set(requirements_surface["runtime_witnesses"])

    assert requirements_surface["coverage_state"] == "proven"
    assert requirements_surface["representative_paths"] == ["component_route_family_promotion_witness_requirements"]
    assert "mcoi/mcoi_runtime/app/component_route_family_promotion_witness_requirements.py" in requirements_surface["evidence_files"]
    assert "schemas/component_route_family_promotion_witness_requirements.schema.json" in requirements_surface["evidence_files"]
    assert "component_route_family_promotion_witness_requirements_schema_valid" in witnesses
    assert "component_route_family_promotion_witness_requirements_rejects_blocker_drift" in witnesses
    assert closure_actions["publish_component_route_family_promotion_witness_requirements"]["status"] == "closed"


def test_component_route_family_promotion_witness_evidence_surface_is_blocked() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    evidence_surface = surfaces["component_route_family_promotion_witness_evidence"]
    witnesses = set(evidence_surface["runtime_witnesses"])

    assert evidence_surface["coverage_state"] == "proven"
    assert evidence_surface["representative_paths"] == ["component_route_family_promotion_witness_evidence"]
    assert "mcoi/mcoi_runtime/app/component_route_family_promotion_witness_evidence.py" in evidence_surface["evidence_files"]
    assert "schemas/component_route_family_promotion_witness_evidence.schema.json" in evidence_surface["evidence_files"]
    assert "component_route_family_promotion_witness_evidence_schema_valid" in witnesses
    assert "component_route_family_promotion_witness_evidence_rejects_satisfied_product_ownership_drift" in witnesses
    assert closure_actions["publish_component_route_family_promotion_witness_evidence"]["status"] == "closed"


def test_component_route_family_promotion_approval_candidates_surface_is_blocked() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    candidate_surface = surfaces["component_route_family_promotion_approval_candidates"]
    witnesses = set(candidate_surface["runtime_witnesses"])

    assert candidate_surface["coverage_state"] == "proven"
    assert candidate_surface["representative_paths"] == ["component_route_family_promotion_approval_candidates"]
    assert "mcoi/mcoi_runtime/app/component_route_family_promotion_approval_candidates.py" in candidate_surface["evidence_files"]
    assert "schemas/component_route_family_promotion_approval_candidates.schema.json" in candidate_surface["evidence_files"]
    assert "component_route_family_promotion_approval_candidates_schema_valid" in witnesses
    assert "component_route_family_promotion_approval_candidates_rejects_approval_drift" in witnesses
    assert closure_actions["publish_component_route_family_promotion_approval_candidates"]["status"] == "closed"


def test_component_route_family_promotion_approval_intake_surface_is_blocked() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    intake_surface = surfaces["component_route_family_promotion_approval_intake"]
    witnesses = set(intake_surface["runtime_witnesses"])

    assert intake_surface["coverage_state"] == "proven"
    assert intake_surface["representative_paths"] == ["component_route_family_promotion_approval_intake"]
    assert "mcoi/mcoi_runtime/app/component_route_family_promotion_approval_intake.py" in intake_surface["evidence_files"]
    assert "schemas/component_route_family_promotion_approval_intake.schema.json" in intake_surface["evidence_files"]
    assert "component_route_family_promotion_approval_intake_schema_valid" in witnesses
    assert "component_route_family_promotion_approval_intake_rejects_submission_drift" in witnesses
    assert closure_actions["publish_component_route_family_promotion_approval_intake"]["status"] == "closed"


def test_component_route_family_promotion_submitted_evidence_verifier_surface_is_blocked() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    verifier_surface = surfaces["component_route_family_promotion_submitted_evidence_verifier"]
    witnesses = set(verifier_surface["runtime_witnesses"])

    assert verifier_surface["coverage_state"] == "proven"
    assert verifier_surface["representative_paths"] == [
        "component_route_family_promotion_submitted_evidence_verifier"
    ]
    assert (
        "mcoi/mcoi_runtime/app/component_route_family_promotion_submitted_evidence_verifier.py"
        in verifier_surface["evidence_files"]
    )
    assert (
        "schemas/component_route_family_promotion_submitted_evidence_verifier.schema.json"
        in verifier_surface["evidence_files"]
    )
    assert "component_route_family_promotion_submitted_evidence_verifier_schema_valid" in witnesses
    assert "component_route_family_promotion_submitted_evidence_verifier_rejects_submission_drift" in witnesses
    assert closure_actions["publish_component_route_family_promotion_submitted_evidence_verifier"]["status"] == "closed"


def test_component_route_family_promotion_submitted_evidence_records_surface_is_blocked() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    records_surface = surfaces["component_route_family_promotion_submitted_evidence_records"]
    witnesses = set(records_surface["runtime_witnesses"])

    assert records_surface["coverage_state"] == "proven"
    assert records_surface["representative_paths"] == [
        "component_route_family_promotion_submitted_evidence_records"
    ]
    assert (
        "mcoi/mcoi_runtime/app/component_route_family_promotion_submitted_evidence_records.py"
        in records_surface["evidence_files"]
    )
    assert (
        "schemas/component_route_family_promotion_submitted_evidence_records.schema.json"
        in records_surface["evidence_files"]
    )
    assert "component_route_family_promotion_submitted_evidence_records_schema_valid" in witnesses
    assert "component_route_family_promotion_submitted_evidence_records_rejects_payload_submission_drift" in witnesses
    assert closure_actions["publish_component_route_family_promotion_submitted_evidence_records"]["status"] == "closed"


def test_component_route_family_promotion_submitted_evidence_payload_examples_surface_is_blocked() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    payload_surface = surfaces["component_route_family_promotion_submitted_evidence_payload_examples"]
    witnesses = set(payload_surface["runtime_witnesses"])

    assert payload_surface["coverage_state"] == "proven"
    assert payload_surface["representative_paths"] == [
        "component_route_family_promotion_submitted_evidence_payload_examples"
    ]
    assert (
        "mcoi/mcoi_runtime/app/component_route_family_promotion_submitted_evidence_payload_examples.py"
        in payload_surface["evidence_files"]
    )
    assert (
        "schemas/component_route_family_promotion_submitted_evidence_payload_examples.schema.json"
        in payload_surface["evidence_files"]
    )
    assert "component_route_family_promotion_submitted_evidence_payload_examples_schema_valid" in witnesses
    assert "component_route_family_promotion_submitted_evidence_payload_examples_reject_rule_application_drift" in witnesses
    assert (
        closure_actions["publish_component_route_family_promotion_submitted_evidence_payload_examples"]["status"]
        == "closed"
    )


def test_component_route_family_promotion_operator_submitted_evidence_records_surface_is_blocked() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    submitted_records_surface = surfaces["component_route_family_promotion_operator_submitted_evidence_records"]
    witnesses = set(submitted_records_surface["runtime_witnesses"])

    assert submitted_records_surface["coverage_state"] == "proven"
    assert submitted_records_surface["representative_paths"] == [
        "component_route_family_promotion_operator_submitted_evidence_records"
    ]
    assert (
        "mcoi/mcoi_runtime/app/component_route_family_promotion_operator_submitted_evidence_records.py"
        in submitted_records_surface["evidence_files"]
    )
    assert (
        "schemas/component_route_family_promotion_operator_submitted_evidence_records.schema.json"
        in submitted_records_surface["evidence_files"]
    )
    assert "component_route_family_promotion_operator_submitted_evidence_records_schema_valid" in witnesses
    assert (
        "component_route_family_promotion_operator_submitted_evidence_records_reject_promotion_satisfaction_drift"
        in witnesses
    )
    assert (
        closure_actions["publish_component_route_family_promotion_operator_submitted_evidence_records"]["status"]
        == "closed"
    )


def test_component_route_family_promotion_gate_satisfaction_evaluator_surface_is_blocked() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    evaluator_surface = surfaces["component_route_family_promotion_gate_satisfaction_evaluator"]
    witnesses = set(evaluator_surface["runtime_witnesses"])

    assert evaluator_surface["coverage_state"] == "proven"
    assert evaluator_surface["representative_paths"] == [
        "component_route_family_promotion_gate_satisfaction_evaluator"
    ]
    assert (
        "mcoi/mcoi_runtime/app/component_route_family_promotion_gate_satisfaction_evaluator.py"
        in evaluator_surface["evidence_files"]
    )
    assert (
        "schemas/component_route_family_promotion_gate_satisfaction_evaluator.schema.json"
        in evaluator_surface["evidence_files"]
    )
    assert "component_route_family_promotion_gate_satisfaction_evaluator_schema_valid" in witnesses
    assert (
        "component_route_family_promotion_gate_satisfaction_evaluator_reject_promotion_authority_drift"
        in witnesses
    )
    assert (
        closure_actions["publish_component_route_family_promotion_gate_satisfaction_evaluator"]["status"]
        == "closed"
    )


def test_component_route_family_promotion_authority_decision_report_surface_is_blocked() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    decision_surface = surfaces["component_route_family_promotion_authority_decision_report"]
    witnesses = set(decision_surface["runtime_witnesses"])

    assert decision_surface["coverage_state"] == "proven"
    assert decision_surface["representative_paths"] == [
        "component_route_family_promotion_authority_decision_report"
    ]
    assert (
        "mcoi/mcoi_runtime/app/component_route_family_promotion_authority_decision_report.py"
        in decision_surface["evidence_files"]
    )
    assert (
        "schemas/component_route_family_promotion_authority_decision_report.schema.json"
        in decision_surface["evidence_files"]
    )
    assert "component_route_family_promotion_authority_decision_report_schema_valid" in witnesses
    assert (
        "component_route_family_promotion_authority_decision_report_reject_promotion_approval_drift"
        in witnesses
    )
    assert (
        closure_actions["publish_component_route_family_promotion_authority_decision_report"]["status"]
        == "closed"
    )


def test_component_route_family_promotion_route_binding_decision_report_surface_is_blocked() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    decision_surface = surfaces["component_route_family_promotion_route_binding_decision_report"]
    witnesses = set(decision_surface["runtime_witnesses"])

    assert decision_surface["coverage_state"] == "proven"
    assert decision_surface["representative_paths"] == [
        "component_route_family_promotion_route_binding_decision_report"
    ]
    assert (
        "mcoi/mcoi_runtime/app/component_route_family_promotion_route_binding_decision_report.py"
        in decision_surface["evidence_files"]
    )
    assert (
        "schemas/component_route_family_promotion_route_binding_decision_report.schema.json"
        in decision_surface["evidence_files"]
    )
    assert "component_route_family_promotion_route_binding_decision_report_schema_valid" in witnesses
    assert (
        "component_route_family_promotion_route_binding_decision_report_reject_router_inventory_mutation_drift"
        in witnesses
    )
    assert (
        closure_actions["publish_component_route_family_promotion_route_binding_decision_report"]["status"]
        == "closed"
    )


def test_component_route_family_promotion_lifecycle_transition_decision_report_surface_is_blocked() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    decision_surface = surfaces["component_route_family_promotion_lifecycle_transition_decision_report"]
    witnesses = set(decision_surface["runtime_witnesses"])

    assert decision_surface["coverage_state"] == "proven"
    assert decision_surface["representative_paths"] == [
        "component_route_family_promotion_lifecycle_transition_decision_report"
    ]
    assert (
        "mcoi/mcoi_runtime/app/component_route_family_promotion_lifecycle_transition_decision_report.py"
        in decision_surface["evidence_files"]
    )
    assert (
        "schemas/component_route_family_promotion_lifecycle_transition_decision_report.schema.json"
        in decision_surface["evidence_files"]
    )
    assert "component_route_family_promotion_lifecycle_transition_decision_report_schema_valid" in witnesses
    assert (
        "component_route_family_promotion_lifecycle_transition_decision_report_reject_lifecycle_receipt_drift"
        in witnesses
    )
    assert (
        closure_actions["publish_component_route_family_promotion_lifecycle_transition_decision_report"]["status"]
        == "closed"
    )


def test_component_route_family_promotion_authority_upgrade_witness_decision_report_surface_is_blocked() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    decision_surface = surfaces["component_route_family_promotion_authority_upgrade_witness_decision_report"]
    witnesses = set(decision_surface["runtime_witnesses"])

    assert decision_surface["coverage_state"] == "proven"
    assert decision_surface["representative_paths"] == [
        "component_route_family_promotion_authority_upgrade_witness_decision_report"
    ]
    assert (
        "mcoi/mcoi_runtime/app/component_route_family_promotion_authority_upgrade_witness_decision_report.py"
        in decision_surface["evidence_files"]
    )
    assert (
        "schemas/component_route_family_promotion_authority_upgrade_witness_decision_report.schema.json"
        in decision_surface["evidence_files"]
    )
    assert "component_route_family_promotion_authority_upgrade_witness_decision_report_schema_valid" in witnesses
    assert (
        "component_route_family_promotion_authority_upgrade_witness_decision_report_reject_witness_drift"
        in witnesses
    )
    assert (
        closure_actions["publish_component_route_family_promotion_authority_upgrade_witness_decision_report"]["status"]
        == "closed"
    )


def test_component_route_family_promotion_product_ownership_decision_report_surface_is_blocked() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    decision_surface = surfaces["component_route_family_promotion_product_ownership_decision_report"]
    witnesses = set(decision_surface["runtime_witnesses"])

    assert decision_surface["coverage_state"] == "proven"
    assert decision_surface["representative_paths"] == [
        "component_route_family_promotion_product_ownership_decision_report"
    ]
    assert (
        "mcoi/mcoi_runtime/app/component_route_family_promotion_product_ownership_decision_report.py"
        in decision_surface["evidence_files"]
    )
    assert (
        "schemas/component_route_family_promotion_product_ownership_decision_report.schema.json"
        in decision_surface["evidence_files"]
    )
    assert "component_route_family_promotion_product_ownership_decision_report_schema_valid" in witnesses
    assert (
        "component_route_family_promotion_product_ownership_decision_report_reject_witness_binding_drift"
        in witnesses
    )
    assert (
        closure_actions["publish_component_route_family_promotion_product_ownership_decision_report"]["status"]
        == "closed"
    )


def test_component_route_family_promotion_terminal_closure_denial_report_surface_is_blocked() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    decision_surface = surfaces["component_route_family_promotion_terminal_closure_denial_report"]
    witnesses = set(decision_surface["runtime_witnesses"])

    assert decision_surface["coverage_state"] == "proven"
    assert decision_surface["representative_paths"] == [
        "component_route_family_promotion_terminal_closure_denial_report"
    ]
    assert (
        "mcoi/mcoi_runtime/app/component_route_family_promotion_terminal_closure_denial_report.py"
        in decision_surface["evidence_files"]
    )
    assert (
        "schemas/component_route_family_promotion_terminal_closure_denial_report.schema.json"
        in decision_surface["evidence_files"]
    )
    assert "component_route_family_promotion_terminal_closure_denial_report_schema_valid" in witnesses
    assert (
        "component_route_family_promotion_terminal_closure_denial_report_reject_certificate_witness_drift"
        in witnesses
    )
    assert (
        closure_actions["publish_component_route_family_promotion_terminal_closure_denial_report"]["status"]
        == "closed"
    )


def test_component_route_family_promotion_missing_evidence_ledger_surface_is_blocked() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    ledger_surface = surfaces["component_route_family_promotion_missing_evidence_ledger"]
    witnesses = set(ledger_surface["runtime_witnesses"])

    assert ledger_surface["coverage_state"] == "proven"
    assert ledger_surface["representative_paths"] == [
        "component_route_family_promotion_missing_evidence_ledger"
    ]
    assert (
        "mcoi/mcoi_runtime/app/component_route_family_promotion_missing_evidence_ledger.py"
        in ledger_surface["evidence_files"]
    )
    assert (
        "schemas/component_route_family_promotion_missing_evidence_ledger.schema.json"
        in ledger_surface["evidence_files"]
    )
    assert "component_route_family_promotion_missing_evidence_ledger_schema_valid" in witnesses
    assert "component_route_family_promotion_missing_evidence_ledger_reject_witness_drift" in witnesses
    assert (
        closure_actions["publish_component_route_family_promotion_missing_evidence_ledger"]["status"]
        == "closed"
    )


def test_component_route_family_promotion_router_inventory_delta_candidate_surface_is_blocked() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    candidate_surface = surfaces["component_route_family_promotion_router_inventory_delta_candidate"]
    witnesses = set(candidate_surface["runtime_witnesses"])

    assert candidate_surface["coverage_state"] == "proven"
    assert candidate_surface["representative_paths"] == [
        "component_route_family_promotion_router_inventory_delta_candidate"
    ]
    assert (
        "mcoi/mcoi_runtime/app/component_route_family_promotion_router_inventory_delta_candidate.py"
        in candidate_surface["evidence_files"]
    )
    assert (
        "schemas/component_route_family_promotion_router_inventory_delta_candidate.schema.json"
        in candidate_surface["evidence_files"]
    )
    assert "component_route_family_promotion_router_inventory_delta_candidate_schema_valid" in witnesses
    assert (
        "component_route_family_promotion_router_inventory_delta_candidate_reject_witness_mutation_drift"
        in witnesses
    )
    assert (
        closure_actions["publish_component_route_family_promotion_router_inventory_delta_candidate"]["status"]
        == "closed"
    )


def test_component_route_family_promotion_router_inventory_delta_witness_requirements_surface_is_blocked() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    requirements_surface = surfaces[
        "component_route_family_promotion_router_inventory_delta_witness_requirements"
    ]
    witnesses = set(requirements_surface["runtime_witnesses"])

    assert requirements_surface["coverage_state"] == "proven"
    assert requirements_surface["representative_paths"] == [
        "component_route_family_promotion_router_inventory_delta_witness_requirements"
    ]
    assert (
        "mcoi/mcoi_runtime/app/component_route_family_promotion_router_inventory_delta_witness_requirements.py"
        in requirements_surface["evidence_files"]
    )
    assert (
        "schemas/component_route_family_promotion_router_inventory_delta_witness_requirements.schema.json"
        in requirements_surface["evidence_files"]
    )
    assert (
        "component_route_family_promotion_router_inventory_delta_witness_requirements_schema_valid"
        in witnesses
    )
    assert (
        "component_route_family_promotion_router_inventory_delta_witness_requirements_reject_mutation_authority_drift"
        in witnesses
    )
    assert (
        closure_actions[
            "publish_component_route_family_promotion_router_inventory_delta_witness_requirements"
        ]["status"]
        == "closed"
    )


def test_component_route_family_promotion_router_inventory_delta_witness_minting_preflight_surface_is_blocked() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    minting_surface = surfaces[
        "component_route_family_promotion_router_inventory_delta_witness_minting_preflight"
    ]
    witnesses = set(minting_surface["runtime_witnesses"])

    assert minting_surface["coverage_state"] == "proven"
    assert minting_surface["representative_paths"] == [
        "component_route_family_promotion_router_inventory_delta_witness_minting_preflight"
    ]
    assert (
        "mcoi/mcoi_runtime/app/component_route_family_promotion_router_inventory_delta_witness_minting_preflight.py"
        in minting_surface["evidence_files"]
    )
    assert (
        "schemas/component_route_family_promotion_router_inventory_delta_witness_minting_preflight.schema.json"
        in minting_surface["evidence_files"]
    )
    assert (
        "component_route_family_promotion_router_inventory_delta_witness_minting_preflight_schema_valid"
        in witnesses
    )
    assert (
        "component_route_family_promotion_router_inventory_delta_witness_minting_preflight_reject_mutation_authority_drift"
        in witnesses
    )
    assert (
        closure_actions[
            "publish_component_route_family_promotion_router_inventory_delta_witness_minting_preflight"
        ]["status"]
        == "closed"
    )


def test_component_route_family_promotion_router_inventory_delta_witness_minting_denial_report_surface_is_blocked() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    denial_surface = surfaces[
        "component_route_family_promotion_router_inventory_delta_witness_minting_denial_report"
    ]
    witnesses = set(denial_surface["runtime_witnesses"])

    assert denial_surface["coverage_state"] == "proven"
    assert denial_surface["representative_paths"] == [
        "component_route_family_promotion_router_inventory_delta_witness_minting_denial_report"
    ]
    assert (
        "mcoi/mcoi_runtime/app/component_route_family_promotion_router_inventory_delta_witness_minting_denial_report.py"
        in denial_surface["evidence_files"]
    )
    assert (
        "schemas/component_route_family_promotion_router_inventory_delta_witness_minting_denial_report.schema.json"
        in denial_surface["evidence_files"]
    )
    assert (
        "component_route_family_promotion_router_inventory_delta_witness_minting_denial_report_schema_valid"
        in witnesses
    )
    assert (
        "component_route_family_promotion_router_inventory_delta_witness_minting_denial_report_reject_mutation_authority_drift"
        in witnesses
    )
    assert (
        closure_actions[
            "publish_component_route_family_promotion_router_inventory_delta_witness_minting_denial_report"
        ]["status"]
        == "closed"
    )


def test_component_route_family_promotion_router_inventory_delta_witness_remediation_plan_surface_is_blocked() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    remediation_surface = surfaces[
        "component_route_family_promotion_router_inventory_delta_witness_remediation_plan"
    ]
    witnesses = set(remediation_surface["runtime_witnesses"])

    assert remediation_surface["coverage_state"] == "proven"
    assert remediation_surface["representative_paths"] == [
        "component_route_family_promotion_router_inventory_delta_witness_remediation_plan"
    ]
    assert (
        "mcoi/mcoi_runtime/app/component_route_family_promotion_router_inventory_delta_witness_remediation_plan.py"
        in remediation_surface["evidence_files"]
    )
    assert (
        "schemas/component_route_family_promotion_router_inventory_delta_witness_remediation_plan.schema.json"
        in remediation_surface["evidence_files"]
    )
    assert (
        "component_route_family_promotion_router_inventory_delta_witness_remediation_plan_schema_valid"
        in witnesses
    )
    assert (
        "component_route_family_promotion_router_inventory_delta_witness_remediation_plan_reject_mutation_drift"
        in witnesses
    )
    assert (
        closure_actions[
            "publish_component_route_family_promotion_router_inventory_delta_witness_remediation_plan"
        ]["status"]
        == "closed"
    )


def test_component_route_family_promotion_router_inventory_delta_witness_remediation_evidence_request_surface_is_blocked() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    evidence_request_surface = surfaces[
        "component_route_family_promotion_router_inventory_delta_witness_remediation_evidence_request"
    ]
    witnesses = set(evidence_request_surface["runtime_witnesses"])

    assert evidence_request_surface["coverage_state"] == "proven"
    assert evidence_request_surface["representative_paths"] == [
        "component_route_family_promotion_router_inventory_delta_witness_remediation_evidence_request"
    ]
    assert (
        "mcoi/mcoi_runtime/app/component_route_family_promotion_router_inventory_delta_witness_remediation_evidence_request.py"
        in evidence_request_surface["evidence_files"]
    )
    assert (
        "schemas/component_route_family_promotion_router_inventory_delta_witness_remediation_evidence_request.schema.json"
        in evidence_request_surface["evidence_files"]
    )
    assert (
        "component_route_family_promotion_router_inventory_delta_witness_remediation_evidence_request_schema_valid"
        in witnesses
    )
    assert (
        "component_route_family_promotion_router_inventory_delta_witness_remediation_evidence_request_reject_mutation_drift"
        in witnesses
    )
    assert (
        closure_actions[
            "publish_component_route_family_promotion_router_inventory_delta_witness_remediation_evidence_request"
        ]["status"]
        == "closed"
    )


def test_component_route_family_promotion_router_inventory_delta_witness_remediation_evidence_request_status_ledger_surface_is_blocked() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    status_ledger_surface = surfaces[
        "component_route_family_promotion_router_inventory_delta_witness_remediation_evidence_request_status_ledger"
    ]
    witnesses = set(status_ledger_surface["runtime_witnesses"])

    assert status_ledger_surface["coverage_state"] == "proven"
    assert status_ledger_surface["representative_paths"] == [
        "component_route_family_promotion_router_inventory_delta_witness_remediation_evidence_request_status_ledger"
    ]
    assert (
        "mcoi/mcoi_runtime/app/component_route_family_promotion_router_inventory_delta_witness_remediation_evidence_request_status_ledger.py"
        in status_ledger_surface["evidence_files"]
    )
    assert (
        "schemas/component_route_family_promotion_router_inventory_delta_witness_remediation_evidence_request_status_ledger.schema.json"
        in status_ledger_surface["evidence_files"]
    )
    assert (
        "component_route_family_promotion_router_inventory_delta_witness_remediation_evidence_request_status_ledger_schema_valid"
        in witnesses
    )
    assert (
        "component_route_family_promotion_router_inventory_delta_witness_remediation_evidence_request_status_ledger_reject_mutation_drift"
        in witnesses
    )
    assert (
        closure_actions[
            "publish_component_route_family_promotion_router_inventory_delta_witness_remediation_evidence_request_status_ledger"
        ]["status"]
        == "closed"
    )


def test_component_lifecycle_transition_receipts_surface_is_preview_only() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    lifecycle_surface = surfaces["component_lifecycle_transition_receipts"]
    witnesses = set(lifecycle_surface["runtime_witnesses"])

    assert lifecycle_surface["coverage_state"] == "proven"
    assert lifecycle_surface["representative_paths"] == ["component_lifecycle_transition_receipts"]
    assert "schemas/component_lifecycle_transition_receipts.schema.json" in lifecycle_surface["evidence_files"]
    assert "scripts/validate_component_lifecycle_transition_receipts.py" in lifecycle_surface["evidence_files"]
    assert "component_lifecycle_transition_receipts_validate_and_write" in witnesses
    assert "component_lifecycle_transition_receipts_reject_live_authority_drift" in witnesses
    assert closure_actions["publish_component_lifecycle_transition_receipts"]["status"] == "closed"


def test_component_authority_envelope_witnesses_surface_is_preview_only() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    authority_surface = surfaces["component_authority_envelope_witnesses"]
    witnesses = set(authority_surface["runtime_witnesses"])

    assert authority_surface["coverage_state"] == "proven"
    assert authority_surface["representative_paths"] == ["component_authority_envelope_witnesses"]
    assert "schemas/component_authority_envelope_witnesses.schema.json" in authority_surface["evidence_files"]
    assert "scripts/validate_component_authority_envelope_witnesses.py" in authority_surface["evidence_files"]
    assert "component_authority_envelope_witnesses_validate_and_write" in witnesses
    assert "component_authority_envelope_witnesses_reject_authority_drift" in witnesses
    assert closure_actions["publish_component_authority_envelope_witnesses"]["status"] == "closed"


def test_component_autopsy_surface_is_read_only() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    autopsy_surface = surfaces["component_autopsy"]
    witnesses = set(autopsy_surface["runtime_witnesses"])

    assert autopsy_surface["coverage_state"] == "proven"
    assert autopsy_surface["representative_paths"] == ["/api/v1/components/{component_id}/autopsy"]
    assert "mcoi/mcoi_runtime/app/component_autopsy.py" in autopsy_surface["evidence_files"]
    assert "schemas/component_autopsy.schema.json" in autopsy_surface["evidence_files"]
    assert "component_autopsy_explains_missing_evidence" in witnesses
    assert "component_autopsy_route_is_read_only" in witnesses
    assert closure_actions["publish_component_autopsy"]["status"] == "closed"


def test_operational_platform_surface_owns_operational_read_model_routes() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    route_records = {
        record["route"]: record
        for record in matrix["route_coverage"]["routes"]
    }
    aggregate_routes = {
        route
        for route in surfaces["operational_platform_read_models"]["representative_paths"]
        if route.startswith("/")
    }

    assert aggregate_routes
    assert all(route_records[route]["surface_id"] == "operational_platform_read_models" for route in aggregate_routes)
    assert route_records["/api/v1/rate-limit/status"]["surface_id"] == "operational_platform_read_models"
    assert route_records["/api/v1/flags"]["surface_id"] == "operational_platform_read_models"
    assert route_records["/gateway/status"]["surface_id"] == "operational_platform_read_models"


def test_representative_routes_are_not_unclassified() -> None:
    matrix = _load_fixture()
    classified_routes = {
        record["route"]: record
        for record in matrix["route_coverage"]["routes"]
    }

    assert classified_routes["/api/v1/lineage/resolve"]["surface_id"] == "lineage_query_api"
    assert classified_routes["/api/v1/lineage/artifact/{artifact_id}"]["surface_id"] == "lineage_query_api"
    assert classified_routes["/api/v1/stream"]["surface_id"] == "llm_streaming"
    assert classified_routes["/webhook/web"]["surface_id"] == "gateway_webhook_ingress"
    assert classified_routes["/capability-fabric/admission-audits"]["surface_id"] == "gateway_capability_fabric"
    assert classified_routes["/capability-fabric/capsule-admissions"]["surface_id"] == "gateway_capability_fabric"
    assert (
        classified_routes["/capability-fabric/capsule-admission-receipts"]["surface_id"]
        == "gateway_capability_fabric"
    )
    assert (
        classified_routes["/commands/{command_id}/interpretation-receipt"]["surface_id"]
        == "gateway_capability_fabric"
    )
    assert classified_routes["/commands/{command_id}/capability-admission"]["surface_id"] == "gateway_capability_fabric"
    assert classified_routes["/commands/{command_id}/authority"]["surface_id"] == "authority_obligation_mesh"
    assert classified_routes["/capability/execute"]["surface_id"] == "capability_worker_execution"
    assert classified_routes["/browser/execute"]["surface_id"] == "restricted_adapter_worker_boundaries"
    assert classified_routes["/document/execute"]["surface_id"] == "restricted_adapter_worker_boundaries"
    assert classified_routes["/email-calendar/execute"]["surface_id"] == "restricted_adapter_worker_boundaries"
    assert classified_routes["/messaging/execute"]["surface_id"] == "restricted_adapter_worker_boundaries"
    assert classified_routes["/phone/execute"]["surface_id"] == "restricted_adapter_worker_boundaries"
    assert classified_routes["/voice/execute"]["surface_id"] == "restricted_adapter_worker_boundaries"
    assert classified_routes["/evidence/bundles/{command_id}"]["surface_id"] == "trust_ledger"
    assert classified_routes["/api/v1/data-governance/evaluate"]["surface_id"] == "data_governance_controls"
    assert classified_routes["/api/v1/compliance/audit-package"]["surface_id"] == "compliance_evidence_exports"
    assert classified_routes["/api/v1/runbooks/analyze"]["surface_id"] == "runbook_learning_lifecycle"
    assert classified_routes["/api/v1/runbooks/{runbook_id}/activate"]["surface_id"] == "runbook_learning_lifecycle"
    assert classified_routes["/api/v1/tenant/register"]["surface_id"] == "tenant_governance_lifecycle"
    assert classified_routes["/api/v1/tenant/{tenant_id}/status"]["surface_id"] == "tenant_governance_lifecycle"
    assert classified_routes["/api/v1/tenant/{tenant_id}/gate"]["surface_id"] == "tenant_governance_lifecycle"
    assert classified_routes["/api/v1/usage/{tenant_id}"]["surface_id"] == "tenant_governance_lifecycle"
    assert classified_routes["/api/v1/isolation/verify"]["surface_id"] == "tenant_governance_lifecycle"
    assert classified_routes["/api/v1/quotas/{tenant_id}"]["surface_id"] == "tenant_governance_lifecycle"
    assert classified_routes["/authority/operator"]["surface_id"] == "authority_operator_controls"
    assert classified_routes["/authority/ownership"]["surface_id"] == "authority_operator_controls"
    assert classified_routes["/api/v1/orgs"]["surface_id"] == "orgos_case_governance_lifecycle"
    assert classified_routes["/api/v1/cases/{case_id}/plan"]["surface_id"] == "orgos_case_governance_lifecycle"
    assert classified_routes["/api/v1/orgos/replay"]["surface_id"] == "orgos_case_governance_lifecycle"
    assert classified_routes["/api/v1/temporal/schedules"]["surface_id"] == "temporal_kernel"
    assert classified_routes["/api/v1/temporal/schedules/{schedule_id}/lease/reclaim"]["surface_id"] == "temporal_kernel"
    assert classified_routes["/api/v1/temporal/schedules/{schedule_id}/missed"]["surface_id"] == "temporal_kernel"
    assert classified_routes["/api/v1/temporal/worker/tick"]["surface_id"] == "temporal_kernel"
    assert classified_routes["/api/v1/temporal/monitor"]["surface_id"] == "temporal_kernel"
    assert classified_routes["/api/v1/knowledge/entities"]["surface_id"] == "governed_operational_intelligence"
    assert classified_routes["/api/v1/knowledge/contradictions/unresolved"]["surface_id"] == "governed_operational_intelligence"
    assert classified_routes["/api/v1/simulate"]["surface_id"] == "governed_operational_intelligence"
    assert classified_routes["/api/v1/simulate/history"]["surface_id"] == "governed_operational_intelligence"
    assert classified_routes["/api/v1/connectors/register"]["surface_id"] == "governed_connector_framework"
    assert classified_routes["/api/v1/connectors/invoke"]["surface_id"] == "governed_connector_framework"
    assert classified_routes["/api/v1/scheduler/jobs"]["surface_id"] == "governed_background_scheduler"
    assert classified_routes["/api/v1/scheduler/execute"]["surface_id"] == "governed_background_scheduler"
    assert (
        classified_routes["/api/v1/scheduler/jobs/{job_id}/disable"]["surface_id"]
        == "governed_background_scheduler"
    )
    assert classified_routes["/api/v1/multi-agent/delegate"]["surface_id"] == "multi_agent_coordination_runtime"
    assert classified_routes["/api/v1/multi-agent/merge"]["surface_id"] == "multi_agent_coordination_runtime"
    assert (
        classified_routes["/api/v1/multi-agent/conflicts/unresolved"]["surface_id"]
        == "multi_agent_coordination_runtime"
    )
    assert classified_routes["/api/v1/config"]["surface_id"] == "runtime_config_management"
    assert classified_routes["/api/v1/config/update"]["surface_id"] == "runtime_config_management"
    assert classified_routes["/api/v1/config/rollback"]["surface_id"] == "runtime_config_management"
    assert classified_routes["/api/v1/config/watcher"]["surface_id"] == "runtime_config_management"
    assert classified_routes["/api/v1/config/drift"]["surface_id"] == "runtime_config_management"
    assert classified_routes["/api/v1/events/publish"]["surface_id"] == "event_bus_operations"
    assert classified_routes["/api/v1/events"]["surface_id"] == "event_bus_operations"
    assert classified_routes["/api/v1/events/store/summary"]["surface_id"] == "event_bus_operations"
    assert classified_routes["/api/v1/ops/benchmarks"]["surface_id"] == "ops_proof_surface"
    assert classified_routes["/api/v1/ops/imports"]["surface_id"] == "ops_proof_surface"
    assert classified_routes["/api/v1/ops/proof-bridge"]["surface_id"] == "ops_proof_surface"
    assert classified_routes["/api/v1/api-keys"]["surface_id"] == "api_key_lifecycle"
    assert classified_routes["/api/v1/api-keys/{key_id}"]["surface_id"] == "api_key_lifecycle"
    assert classified_routes["/api/v1/queue/submit"]["surface_id"] == "task_queue_lifecycle"
    assert classified_routes["/api/v1/queue/process"]["surface_id"] == "task_queue_lifecycle"
    assert classified_routes["/api/v1/queue/result/{task_id}"]["surface_id"] == "task_queue_lifecycle"
    assert classified_routes["/api/v1/memory/store"]["surface_id"] == "agent_memory_lifecycle"
    assert classified_routes["/api/v1/memory/search"]["surface_id"] == "agent_memory_lifecycle"
    assert classified_routes["/api/v1/memory/summary"]["surface_id"] == "agent_memory_lifecycle"
    assert classified_routes["/api/v1/explain/action"]["surface_id"] == "governance_explanation_lifecycle"
    assert (
        classified_routes["/api/v1/explain/audit/{entry_index}"]["surface_id"]
        == "governance_explanation_lifecycle"
    )
    assert classified_routes["/api/v1/explain/summary"]["surface_id"] == "governance_explanation_lifecycle"
    assert classified_routes["/api/v1/tools"]["surface_id"] == "tool_registry_read_models"
    assert classified_routes["/api/v1/tools/history"]["surface_id"] == "tool_registry_read_models"
    assert classified_routes["/api/v1/tools/llm-format"]["surface_id"] == "tool_registry_read_models"
    assert classified_routes["/api/v1/tools/invoke"]["surface_id"] == "tool_invocation"
    assert classified_routes["/api/v1/personal-assistant/skills"]["surface_id"] == "assistant_kernel_planning"
    assert (
        classified_routes["/api/v1/personal-assistant/requests/preview"]["surface_id"]
        == "assistant_kernel_planning"
    )
    assert (
        classified_routes["/api/v1/personal-assistant/approval-queue"]["surface_id"]
        == "assistant_kernel_planning"
    )
    assert (
        classified_routes["/api/v1/personal-assistant/approval-proposals/preview"]["surface_id"]
        == "assistant_kernel_planning"
    )
    assert (
        classified_routes["/api/v1/personal-assistant/approval-queue/preview"]["surface_id"]
        == "assistant_kernel_planning"
    )
    assert (
        classified_routes["/api/v1/personal-assistant/read-only/inbox/preview"]["surface_id"]
        == "assistant_kernel_planning"
    )
    assert (
        classified_routes["/api/v1/personal-assistant/read-only/calendar/preview"]["surface_id"]
        == "assistant_kernel_planning"
    )
    assert (
        classified_routes["/api/v1/personal-assistant/drafts/email/preview"]["surface_id"]
        == "assistant_kernel_planning"
    )
    assert (
        classified_routes["/api/v1/personal-assistant/drafts/calendar-event/preview"]["surface_id"]
        == "assistant_kernel_planning"
    )
    assert (
        classified_routes["/api/v1/personal-assistant/drafts/task/preview"]["surface_id"]
        == "assistant_kernel_planning"
    )
    assert (
        classified_routes["/api/v1/personal-assistant/memory-observations"]["surface_id"]
        == "assistant_kernel_planning"
    )
    assert (
        classified_routes["/api/v1/personal-assistant/memory-observations/preview"]["surface_id"]
        == "assistant_kernel_planning"
    )
    assert classified_routes["/api/v1/tool-permissions"]["surface_id"] == "tool_permission_registry"
    assert classified_routes["/api/v1/tool-permissions/evaluate"]["surface_id"] == "tool_permission_registry"
    assert classified_routes["/api/v1/output/parse"]["surface_id"] == "structured_output_validation"
    assert classified_routes["/api/v1/output/schemas"]["surface_id"] == "structured_output_validation"
    assert classified_routes["/api/v1/rate-limit/status"]["surface_id"] == "operational_platform_read_models"
    assert classified_routes["/api/v1/rate-limits/{client_id}"]["surface_id"] == "operational_platform_read_models"
    assert classified_routes["/api/v1/flags"]["surface_id"] == "operational_platform_read_models"
    assert classified_routes["/api/v1/flags/{flag_id}"]["surface_id"] == "operational_platform_read_models"
    assert classified_routes["/api/v1/traces"]["surface_id"] == "trace_observability_read_models"
    assert classified_routes["/api/v1/traces/slow"]["surface_id"] == "trace_observability_read_models"
    assert classified_routes["/api/v1/traces/summary"]["surface_id"] == "trace_observability_read_models"
    assert classified_routes["/api/v1/health/deep"]["surface_id"] == "operational_health_read_models"
    assert classified_routes["/api/v1/health/score"]["surface_id"] == "operational_health_read_models"
    assert classified_routes["/api/v1/health/extensions"]["surface_id"] == "operational_health_read_models"
    assert classified_routes["/api/v1/health/shadow"]["surface_id"] == "operational_health_read_models"
    assert classified_routes["/api/v1/components/read-model"]["surface_id"] == "component_harness_read_model"
    assert classified_routes["/api/v1/components/simulate"]["surface_id"] == "component_request_simulator"
    assert classified_routes["/api/v1/health/v3"]["surface_id"] == "operational_health_read_models"
    assert classified_routes["/api/v1/readiness"]["surface_id"] == "operational_health_read_models"
    assert classified_routes["/api/v1/spatial-map"]["surface_id"] == "operational_health_read_models"
    assert classified_routes["/api/v1/deploy/readiness"]["surface_id"] == "operational_health_read_models"
    assert classified_routes["/api/v1/release/latest"]["surface_id"] == "operational_health_read_models"
    assert classified_routes["/api/v1/snapshot"]["surface_id"] == "operational_health_read_models"
    assert classified_routes["/api/v1/console/shadow"]["surface_id"] == "operator_console_read_models"
    assert (
        classified_routes["/api/v1/console/personal-assistant"]["surface_id"]
        == "operator_console_read_models"
    )
    assert (
        classified_routes["/api/v1/console/personal-assistant/view"]["surface_id"]
        == "operator_console_read_models"
    )
    assert classified_routes["/api/v1/console/spatial-map"]["surface_id"] == "operator_console_read_models"
    assert classified_routes["/api/v1/console/spatial-map/view"]["surface_id"] == "operator_console_read_models"
    assert classified_routes["/api/v1/orchestration"]["surface_id"] == "agent_orchestration_lifecycle"
    assert classified_routes["/api/v1/orchestration/plans"]["surface_id"] == "agent_orchestration_lifecycle"
    assert (
        classified_routes["/api/v1/orchestration/plans/{plan_id}"]["surface_id"]
        == "agent_orchestration_lifecycle"
    )
    assert classified_routes["/api/v1/workflow/execute"]["surface_id"] == "workflow_execution_lifecycle"
    assert classified_routes["/api/v1/workflow/history"]["surface_id"] == "workflow_execution_lifecycle"
    assert classified_routes["/api/v1/workflow/traced"]["surface_id"] == "workflow_execution_lifecycle"
    assert classified_routes["/api/v1/execute"]["surface_id"] == "workflow_execution_lifecycle"
    assert classified_routes["/api/v1/pipeline/execute"]["surface_id"] == "workflow_execution_lifecycle"
    assert classified_routes["/api/v1/templates/execute"]["surface_id"] == "workflow_execution_lifecycle"
    assert classified_routes["/api/v1/chain/execute"]["surface_id"] == "agent_chain_execution_lifecycle"
    assert classified_routes["/api/v1/chain/history"]["surface_id"] == "agent_chain_execution_lifecycle"
    assert classified_routes["/api/v1/daemon/status"]["surface_id"] == "certification_daemon_lifecycle"
    assert classified_routes["/api/v1/daemon/tick"]["surface_id"] == "certification_daemon_lifecycle"
    assert classified_routes["/api/v1/daemon/force"]["surface_id"] == "certification_daemon_lifecycle"
    assert classified_routes["/api/v1/certify"]["surface_id"] == "live_path_certification_lifecycle"
    assert classified_routes["/api/v1/certify/history"]["surface_id"] == "live_path_certification_lifecycle"
    assert classified_routes["/api/v1/state"]["surface_id"] == "runtime_state_persistence_lifecycle"
    assert classified_routes["/api/v1/state/save"]["surface_id"] == "runtime_state_persistence_lifecycle"
    assert classified_routes["/api/v1/state/{state_type}"]["surface_id"] == "runtime_state_persistence_lifecycle"
    assert classified_routes["/api/v1/finance/approval-packets"]["surface_id"] == "finance_approval_packets"
    assert (
        classified_routes["/api/v1/finance/approval-packets/operator/read-model"]["surface_id"]
        == "finance_approval_packets"
    )
    assert (
        classified_routes["/api/v1/finance/approval-packets/{case_id}/proof"]["surface_id"]
        == "finance_approval_packets"
    )
    assert classified_routes["/api/v1/agent/register"]["surface_id"] == "agent_adapter_protocol"
    assert classified_routes["/api/v1/agent/action-request"]["surface_id"] == "agent_adapter_protocol"
    assert classified_routes["/api/v1/agent/restore"]["surface_id"] == "agent_adapter_protocol"
    assert classified_routes["/api/v1/agents"]["surface_id"] == "agent_adapter_protocol"
    assert classified_routes["/api/v1/agents/{agent_id}/tasks"]["surface_id"] == "agent_adapter_protocol"
    assert classified_routes["/api/v1/webhooks/subscribe"]["surface_id"] == "webhooks_proof_surface"
    assert classified_routes["/api/v1/webhooks"]["surface_id"] == "webhooks_proof_surface"
    assert classified_routes["/api/v1/webhooks/deliveries"]["surface_id"] == "webhooks_proof_surface"
    assert classified_routes["/api/v1/webhooks/retry/summary"]["surface_id"] == "webhooks_proof_surface"
    assert classified_routes["/api/v1/webhooks/retry/dead-letters"]["surface_id"] == "webhooks_proof_surface"
    assert classified_routes["/api/v1/rbac/identities"]["surface_id"] == "rbac_access_governance"
    assert classified_routes["/api/v1/rbac/roles"]["surface_id"] == "rbac_access_governance"
    assert classified_routes["/api/v1/rbac/bindings"]["surface_id"] == "rbac_access_governance"
    assert classified_routes["/api/v1/bootstrap"]["surface_id"] == "operational_platform_read_models"
    assert classified_routes["/api/v1/circuit-breaker"]["surface_id"] == "operational_platform_read_models"
    assert classified_routes["/api/v1/llm/history"]["surface_id"] == "operational_platform_read_models"
    assert classified_routes["/api/v1/conversation/message"]["surface_id"] == "conversation_memory_lifecycle"
    assert classified_routes["/api/v1/conversation/{conversation_id}"]["surface_id"] == "conversation_memory_lifecycle"
    assert classified_routes["/api/v1/conversations"]["surface_id"] == "conversation_memory_lifecycle"
    assert classified_routes["/api/v1/coordination/checkpoint"]["surface_id"] == "coordination_checkpoint_lifecycle"
    assert classified_routes["/api/v1/coordination/restore"]["surface_id"] == "coordination_checkpoint_lifecycle"
    assert classified_routes["/api/v1/dependencies"]["surface_id"] == "operational_platform_read_models"
    assert classified_routes["/api/v1/dependencies/{name}/impact"]["surface_id"] == "operational_platform_read_models"
    assert (
        classified_routes["/api/v1/engineering-puzzle/candidates/judge"]["surface_id"]
        == "engineering_puzzle_governance"
    )
    assert classified_routes["/api/v1/engineering-puzzle/goal-delta"]["surface_id"] == "engineering_puzzle_governance"
    assert classified_routes["/api/v1/export"]["surface_id"] == "data_export_lifecycle"
    assert classified_routes["/api/v1/export/sources"]["surface_id"] == "data_export_lifecycle"
    assert classified_routes["/api/v1/flags"]["surface_id"] == "operational_platform_read_models"
    assert classified_routes["/api/v1/flags/{flag_id}"]["surface_id"] == "operational_platform_read_models"
    assert classified_routes["/api/v1/metrics"]["surface_id"] == "operational_platform_read_models"
    assert classified_routes["/api/v1/grafana/dashboard"]["surface_id"] == "operational_platform_read_models"
    assert classified_routes["/api/v1/prompts"]["surface_id"] == "prompt_template_lifecycle"
    assert classified_routes["/api/v1/prompts/render"]["surface_id"] == "prompt_template_lifecycle"
    assert classified_routes["/api/v1/rate-limit/status"]["surface_id"] == "operational_platform_read_models"
    assert classified_routes["/api/v1/rate-limits/{client_id}"]["surface_id"] == "operational_platform_read_models"
    assert classified_routes["/api/v1/replay/traces"]["surface_id"] == "replay_trace_read_models"
    assert classified_routes["/api/v1/schemas"]["surface_id"] == "schema_validation_registry"
    assert classified_routes["/api/v1/schemas/validate"]["surface_id"] == "schema_validation_registry"
    assert classified_routes["/api/v1/search"]["surface_id"] == "semantic_search_read_models"
    assert classified_routes["/api/v1/search/stats"]["surface_id"] == "semantic_search_read_models"
    assert classified_routes["/api/v1/sla"]["surface_id"] == "operational_platform_read_models"
    assert classified_routes["/api/v1/sla/violations"]["surface_id"] == "operational_platform_read_models"
    assert classified_routes["/gateway/status"]["surface_id"] == "operational_platform_read_models"


def test_runtime_config_management_surface_is_witnessed() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    route_records = {
        record["route"]: record
        for record in matrix["route_coverage"]["routes"]
    }
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    config_surface = surfaces["runtime_config_management"]
    witnesses = set(config_surface["runtime_witnesses"])

    assert config_surface["coverage_state"] == "witnessed"
    assert config_surface["request_proof"] == "request_proof"
    assert config_surface["action_proof"] == "action_proof"
    assert config_surface["audit"] == "audit_chain"
    assert "/api/v1/config/update" in config_surface["representative_paths"]
    assert "/api/v1/config/rollback" in config_surface["representative_paths"]
    assert "/api/v1/config/watcher" in config_surface["representative_paths"]
    assert "/api/v1/config/drift" in config_surface["representative_paths"]
    assert "mcoi/mcoi_runtime/app/routers/ops/config.py" in config_surface["evidence_files"]
    assert "mcoi/mcoi_runtime/core/config_reload.py" in config_surface["evidence_files"]
    assert "mcoi/tests/test_server_phase207.py" in config_surface["evidence_files"]
    assert "mcoi/tests/test_config_drift.py" in config_surface["evidence_files"]
    assert "config_update_emits_event_and_audit" in witnesses
    assert "config_rollback_requires_known_version" in witnesses
    assert "config_watcher_errors_are_bounded" in witnesses
    assert "config_drift_secret_changes_are_critical" in witnesses
    assert route_records["/api/v1/config/update"]["coverage_state"] == "witnessed"
    assert route_records["/api/v1/config/update"]["surface_id"] == "runtime_config_management"
    assert route_records["/api/v1/config/drift"]["coverage_state"] == "witnessed"
    assert route_records["/api/v1/config/drift"]["surface_id"] == "runtime_config_management"
    assert closure_actions["classify_runtime_config_management_routes"]["status"] == "closed"


def test_orgos_case_governance_lifecycle_surface_is_proven() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    route_records = {
        record["route"]: record
        for record in matrix["route_coverage"]["routes"]
    }
    witness_records = {
        record["surface_id"]: record
        for record in matrix["witness_integrity"]["surfaces"]
    }
    surface = surfaces["orgos_case_governance_lifecycle"]
    witnesses = set(surface["runtime_witnesses"])

    assert surface["coverage_state"] == "proven"
    assert surface["request_proof"] == "request_proof"
    assert surface["action_proof"] == "action_proof"
    assert surface["audit"] == "audit_chain"
    assert "/api/v1/orgs" in surface["representative_paths"]
    assert "/api/v1/cases/{case_id}/close" in surface["representative_paths"]
    assert "/api/v1/orgos/replay" in surface["representative_paths"]
    assert "gateway/orgos_kernel.py" in surface["evidence_files"]
    assert "tests/test_gateway/test_orgos_api.py" in surface["evidence_files"]
    assert "orgos_api_runs_launch_gateway_case_control_loop" in witnesses
    assert "orgos_api_replays_projection_from_jsonl_event_log" in witnesses
    assert "launch_gateway_pilot_collects_deployment_witness_and_allows_engineering_gate" in witnesses
    assert "launch_gateway_pilot_gate_preview_is_non_mutating" in witnesses
    assert "launch_gateway_pilot_gate_preview_allows_without_writing_decisions" in witnesses
    assert "launch_gateway_pilot_readiness_read_model_reports_missing_evidence" in witnesses
    assert "launch_gateway_pilot_readiness_packet_closes_after_verified_witness" in witnesses
    assert "launch_gateway_pilot_readiness_packet_blocks_without_engineering_witness" in witnesses
    assert "case_proof_timeline_reports_open_case_without_closure" in witnesses
    assert "case_proof_timeline_reports_closure_certificate_and_learning" in witnesses
    assert "learning_binding_requires_admission_evidence_refs" in witnesses
    assert "learning_binding_rejects_non_decision_evidence_refs" in witnesses
    assert "case_proof_explorer_reports_open_case_attention_without_mutation" in witnesses
    assert "case_proof_explorer_reports_closed_verified_case" in witnesses
    assert "case_proof_explorer_html_view_is_read_only_and_escaped" in witnesses
    assert "authority_map_view_is_read_only_escaped_and_chained" in witnesses
    assert "case_audit_explorer_reports_open_case_without_mutation" in witnesses
    assert "case_audit_explorer_view_is_read_only_and_escaped" in witnesses
    assert "case_portfolio_view_is_read_only_escaped_and_grouped" in witnesses
    assert "case_portfolio_reports_closed_verified_case" in witnesses
    assert "case_step_handoffs_report_worker_receipt_binding_without_mutation" in witnesses
    assert "case_step_handoffs_view_is_read_only_and_escaped" in witnesses
    assert "case_plan_step_admission_preview_defers_missing_evidence_without_mutation" in witnesses
    assert "case_plan_step_admission_preview_allows_receipt_binding_without_dispatch" in witnesses
    assert "organization_action_queue_reports_deferred_handoff_actions_without_mutation" in witnesses
    assert "organization_action_queue_reports_receipt_ready_step_without_dispatch" in witnesses
    assert "organization_action_queue_filters_ready_receipt_actions_without_mutation" in witnesses
    assert "organization_action_queue_selection_preview_simulates_visible_filtered_action_without_mutation" in witnesses
    assert "organization_action_queue_selection_preview_rejects_filtered_out_action_without_mutation" in witnesses
    assert "organization_action_queue_approval_packet_preview_defers_missing_evidence_without_mutation" in witnesses
    assert "organization_action_queue_approval_packet_preview_requires_approval_after_evidence_ready" in witnesses
    assert "organization_action_queue_approval_packet_preview_rejects_filtered_out_action_without_mutation" in witnesses
    assert "organization_action_queue_dispatch_lease_preview_reports_ready_lease_without_dispatch" in witnesses
    assert "organization_action_queue_dispatch_lease_preview_simulates_missing_evidence_without_mutation" in witnesses
    assert "organization_action_queue_dispatch_lease_preview_blocks_until_approval_without_mutation" in witnesses
    assert "organization_action_queue_dispatch_lease_preview_rejects_filtered_out_action_without_mutation" in witnesses
    assert "organization_action_queue_worker_lease_creates_receipt_without_dispatch" in witnesses
    assert "organization_action_queue_worker_lease_rejects_not_ready_selection_without_mutation" in witnesses
    assert "organization_action_queue_worker_lease_rejects_duplicate_lease_without_extra_event" in witnesses
    assert "organization_action_queue_worker_dispatch_receipt_records_envelope_without_output_binding" in witnesses
    assert "organization_action_queue_worker_dispatch_receipt_rejects_missing_lease_without_mutation" in witnesses
    assert "organization_action_queue_worker_dispatch_receipt_rejects_duplicate_dispatch_without_extra_event" in witnesses
    assert "organization_action_queue_worker_dispatch_receipt_rejects_not_ready_selection_without_mutation" in witnesses
    assert "organization_action_queue_view_is_read_only_and_escaped" in witnesses
    assert "case_private_pilot_live_rehearsal_binds_preview_receipts_without_mutation" in witnesses
    assert "organization_action_queue_view_preserves_filters" in witnesses
    assert "department_registry_view_is_read_only_and_escaped" in witnesses
    assert "case_closure_certificate_view_is_read_only_and_escaped" in witnesses
    assert "case_closure_requires_effect_reconciliation_match_for_committed" in witnesses
    assert "terminal_closure_requires_latest_gate_evidence_refs" in witnesses
    assert "terminal_closure_rejects_unadmitted_certificate_evidence_ref" in witnesses
    assert "terminal_closure_requires_worker_bound_gate_evidence_refs" in witnesses
    assert "closure_certificate_reports_required_gate_evidence_before_closure" in witnesses
    assert "closed_case_reports_closure_packet_drift_after_gate_refresh" in witnesses
    assert "closure_packet_drift_accepts_remediation_routing" in witnesses
    assert "closure_packet_drift_remediation_rejects_mismatched_refs" in witnesses
    assert "closure_packet_drift_remediation_rejects_unrecorded_authority_ref" in witnesses
    assert "closure_packet_drift_remediation_rejects_unbound_superseded_evidence_refs" in witnesses
    assert "closure_packet_drift_remediation_rejects_unmet_disposition_policy" in witnesses
    assert "closure_packet_drift_operator_actions_report_policy_requirements" in witnesses
    assert "closure_packet_drift_operator_action_binds_review_remediation" in witnesses
    assert "closure_packet_drift_operator_action_binds_compensation_runbook_remediation" in witnesses
    assert "closure_packet_drift_operator_action_binds_accepted_risk_runbook_remediation" in witnesses
    assert "closure_packet_drift_operator_action_rejects_missing_policy_evidence" in witnesses
    assert "worker_receipt_requires_recorded_dispatch_receipt" in witnesses
    assert "worker_receipt_rejects_dispatch_identity_mismatch" in witnesses
    assert "worker_receipt_endpoint_rejects_missing_dispatch_receipt" in witnesses
    assert route_records["/api/v1/cases"]["surface_id"] == "orgos_case_governance_lifecycle"
    assert (
        route_records["/api/v1/orgs/{org_id}/authority-map"]["surface_id"]
        == "orgos_case_governance_lifecycle"
    )
    assert (
        route_records["/api/v1/orgs/{org_id}/authority-map/view"]["surface_id"]
        == "orgos_case_governance_lifecycle"
    )
    assert (
        route_records["/api/v1/orgs/{org_id}/case-portfolio"]["surface_id"]
        == "orgos_case_governance_lifecycle"
    )
    assert (
        route_records["/api/v1/orgs/{org_id}/case-portfolio/view"]["surface_id"]
        == "orgos_case_governance_lifecycle"
    )
    assert (
        route_records["/api/v1/orgs/{org_id}/action-queue"]["surface_id"]
        == "orgos_case_governance_lifecycle"
    )
    assert (
        route_records["/api/v1/orgs/{org_id}/action-queue/selection-preview"]["surface_id"]
        == "orgos_case_governance_lifecycle"
    )
    assert (
        route_records["/api/v1/orgs/{org_id}/action-queue/approval-packet-preview"]["surface_id"]
        == "orgos_case_governance_lifecycle"
    )
    assert (
        route_records["/api/v1/orgs/{org_id}/action-queue/dispatch-lease-preview"]["surface_id"]
        == "orgos_case_governance_lifecycle"
    )
    assert (
        route_records["/api/v1/orgs/{org_id}/action-queue/worker-lease"]["surface_id"]
        == "orgos_case_governance_lifecycle"
    )
    assert (
        route_records["/api/v1/orgs/{org_id}/action-queue/worker-dispatch-receipt"]["surface_id"]
        == "orgos_case_governance_lifecycle"
    )
    assert (
        route_records["/api/v1/orgs/{org_id}/action-queue/view"]["surface_id"]
        == "orgos_case_governance_lifecycle"
    )
    assert (
        route_records["/api/v1/orgs/{org_id}/department-registry"]["surface_id"]
        == "orgos_case_governance_lifecycle"
    )
    assert (
        route_records["/api/v1/orgs/{org_id}/department-registry/view"]["surface_id"]
        == "orgos_case_governance_lifecycle"
    )
    assert (
        route_records["/api/v1/cases/{case_id}/closure-certificate"]["surface_id"]
        == "orgos_case_governance_lifecycle"
    )
    assert (
        route_records["/api/v1/cases/{case_id}/closure-certificate/view"]["surface_id"]
        == "orgos_case_governance_lifecycle"
    )
    assert (
        route_records["/api/v1/cases/{case_id}/closure-drift-remediations"]["surface_id"]
        == "orgos_case_governance_lifecycle"
    )
    assert (
        route_records["/api/v1/cases/{case_id}/closure-drift-remediation-actions"]["surface_id"]
        == "orgos_case_governance_lifecycle"
    )
    assert (
        route_records["/api/v1/cases/{case_id}/audit-explorer"]["surface_id"]
        == "orgos_case_governance_lifecycle"
    )
    assert (
        route_records["/api/v1/cases/{case_id}/audit-explorer/view"]["surface_id"]
        == "orgos_case_governance_lifecycle"
    )
    assert (
        route_records["/api/v1/cases/{case_id}/step-handoffs"]["surface_id"]
        == "orgos_case_governance_lifecycle"
    )
    assert (
        route_records["/api/v1/cases/{case_id}/step-handoffs/view"]["surface_id"]
        == "orgos_case_governance_lifecycle"
    )
    assert (
        route_records["/api/v1/cases/{case_id}/plan-steps/{step_id}/admission-preview"]["surface_id"]
        == "orgos_case_governance_lifecycle"
    )
    assert (
        route_records["/api/v1/cases/{case_id}/plan-steps/{step_id}/private-pilot/rehearsal"]["surface_id"]
        == "orgos_case_governance_lifecycle"
    )
    assert (
        route_records["/api/v1/cases/{case_id}/launch-gateway-pilot/deployment-witness"]["surface_id"]
        == "orgos_case_governance_lifecycle"
    )
    assert (
        route_records["/api/v1/cases/{case_id}/launch-gateway-pilot/gate-preview"]["surface_id"]
        == "orgos_case_governance_lifecycle"
    )
    assert (
        route_records["/api/v1/cases/{case_id}/launch-gateway-pilot/readiness"]["surface_id"]
        == "orgos_case_governance_lifecycle"
    )
    assert (
        route_records["/api/v1/cases/{case_id}/launch-gateway-pilot/readiness-closure"]["surface_id"]
        == "orgos_case_governance_lifecycle"
    )
    assert (
        route_records["/api/v1/cases/{case_id}/proof-explorer"]["surface_id"]
        == "orgos_case_governance_lifecycle"
    )
    assert (
        route_records["/api/v1/cases/{case_id}/proof-explorer/view"]["surface_id"]
        == "orgos_case_governance_lifecycle"
    )
    assert (
        route_records["/api/v1/cases/{case_id}/proof-timeline"]["surface_id"]
        == "orgos_case_governance_lifecycle"
    )
    assert route_records["/api/v1/orgos/read-model"]["coverage_state"] == "proven"
    assert witness_records["orgos_case_governance_lifecycle"]["exact_test_anchor_count"] == 77


def test_webhooks_proof_surface_is_witnessed() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    route_records = {
        record["route"]: record
        for record in matrix["route_coverage"]["routes"]
    }
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    webhooks_surface = surfaces["webhooks_proof_surface"]
    witnesses = set(webhooks_surface["runtime_witnesses"])

    assert webhooks_surface["coverage_state"] == "witnessed"
    assert webhooks_surface["request_proof"] == "request_proof"
    assert webhooks_surface["action_proof"] == "action_proof"
    assert webhooks_surface["audit"] == "audit_chain"
    assert "/api/v1/webhooks/subscribe" in webhooks_surface["representative_paths"]
    assert "/api/v1/webhooks" in webhooks_surface["representative_paths"]
    assert "/api/v1/webhooks/deliveries" in webhooks_surface["representative_paths"]
    assert "/api/v1/webhooks/retry/summary" in webhooks_surface["representative_paths"]
    assert "/api/v1/webhooks/retry/dead-letters" in webhooks_surface["representative_paths"]
    assert "mcoi/mcoi_runtime/app/routers/agent.py" in webhooks_surface["evidence_files"]
    assert "mcoi/mcoi_runtime/core/webhook_retry.py" in webhooks_surface["evidence_files"]
    assert "mcoi/tests/test_server_phase205.py" in webhooks_surface["evidence_files"]
    assert "mcoi/tests/test_webhook_system.py" in webhooks_surface["evidence_files"]
    assert "mcoi/tests/test_webhook_retry.py" in webhooks_surface["evidence_files"]
    assert "webhook_mutation_receipt_closes_effect_assurance" in witnesses
    assert "subscribe" in witnesses
    assert "list_webhooks" in witnesses
    assert "duplicate_subscribe_error_is_bounded" in witnesses
    assert "emit_tenant_filter" in witnesses
    assert "multiple_subscriptions" in witnesses
    assert "webhook_deliveries" in witnesses
    assert "delivery_history" in witnesses
    assert "emit_queues_delivery" in witnesses
    assert "emit_with_secret_signature" in witnesses
    assert "disabled_subscription_skipped" in witnesses
    assert "webhook_mutation_receipt_closes_effect_assurance" in witnesses
    assert "summary_fields" in witnesses
    assert "summary_reports_bounded_enqueue_reasons" in witnesses
    assert "dead_letters_list" in witnesses
    assert "bounded" in witnesses
    assert "retry_exhaustion_reports_bounded_failure_reasons" in witnesses
    assert "delivery_error_classifier_uses_stable_taxonomy" in witnesses
    assert route_records["/api/v1/webhooks/subscribe"]["coverage_state"] == "witnessed"
    assert route_records["/api/v1/webhooks/subscribe"]["surface_id"] == "webhooks_proof_surface"
    assert route_records["/api/v1/webhooks/retry/dead-letters"]["coverage_state"] == "witnessed"
    assert route_records["/api/v1/webhooks/retry/dead-letters"]["surface_id"] == "webhooks_proof_surface"
    assert closure_actions["classify_webhooks_routes"]["status"] == "closed"


def test_agent_adapter_protocol_surface_is_witnessed() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    agent_surface = surfaces["agent_adapter_protocol"]
    witnesses = set(agent_surface["runtime_witnesses"])

    assert agent_surface["coverage_state"] == "witnessed"
    assert agent_surface["request_proof"] == "request_proof"
    assert agent_surface["action_proof"] == "action_proof"
    assert "/api/v1/agent/register" in agent_surface["representative_paths"]
    assert "/api/v1/agent/action-request" in agent_surface["representative_paths"]
    assert "/api/v1/agent/restore" in agent_surface["representative_paths"]
    assert "/api/v1/agent/adapter/summary" in agent_surface["representative_paths"]
    assert "/api/v1/agents" in agent_surface["representative_paths"]
    assert "/api/v1/agents/{agent_id}/tasks" in agent_surface["representative_paths"]
    assert "mcoi/mcoi_runtime/app/routers/adapter.py" in agent_surface["evidence_files"]
    assert "mcoi/mcoi_runtime/app/routers/deps.py" in agent_surface["evidence_files"]
    assert "mcoi/mcoi_runtime/app/routers/agent.py" in agent_surface["evidence_files"]
    assert "mcoi/tests/test_agent_adapter_protocol.py" in agent_surface["evidence_files"]
    assert "agent_register_emits_governed_identity" in witnesses
    assert "agent_register_emits_audit_record" in witnesses
    assert "agent_action_request_runs_guard_chain" in witnesses
    assert "agent_checkpoint_restore_errors_are_bounded" in witnesses
    assert "agent_checkpoint_restore_roundtrip_governed" in witnesses
    assert "agent_adapter_summary_is_governed_read_model" in witnesses
    assert "agent_adapter_summary_bounded" in witnesses
    assert "builtin_agent_registry_read_models_governed" in witnesses
    agent_integrity = {
        record["surface_id"]: record
        for record in matrix["witness_integrity"]["surfaces"]
    }["agent_adapter_protocol"]
    assert agent_integrity["exact_test_anchor_count"] == 14
    assert agent_integrity["unanchored_witness_count"] == 0
    assert closure_actions["classify_agent_adapter_protocol_routes"]["status"] == "closed"


def test_rbac_access_governance_surface_is_proven() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    rbac_surface = surfaces["rbac_access_governance"]
    witnesses = set(rbac_surface["runtime_witnesses"])

    assert rbac_surface["coverage_state"] == "proven"
    assert rbac_surface["request_proof"] == "request_proof"
    assert rbac_surface["action_proof"] == "action_proof"
    assert "/api/v1/rbac/identities" in rbac_surface["representative_paths"]
    assert "/api/v1/rbac/roles" in rbac_surface["representative_paths"]
    assert "/api/v1/rbac/bindings" in rbac_surface["representative_paths"]
    assert "/api/v1/rbac/summary" in rbac_surface["representative_paths"]
    assert "mcoi/mcoi_runtime/app/routers/rbac.py" in rbac_surface["evidence_files"]
    assert "mcoi/mcoi_runtime/contracts/access_runtime.py" in rbac_surface["evidence_files"]
    assert "mcoi/tests/test_rbac_endpoints.py" in rbac_surface["evidence_files"]
    assert "rbac_identity_registration_governed" in witnesses
    assert "rbac_role_registration_governed" in witnesses
    assert "rbac_role_binding_governed" in witnesses
    assert "rbac_identity_creation_audited" in witnesses
    assert closure_actions["classify_rbac_access_governance_routes"]["status"] == "closed"


def test_remaining_declared_route_groups_are_witnessed() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    route_records = {
        record["route"]: record
        for record in matrix["route_coverage"]["routes"]
    }
    expected_groups = (
        (
            "operational_platform_read_models",
            "classify_operational_platform_read_model_routes",
            ("/api/v1/bootstrap", "/api/v1/circuit-breaker", "/api/v1/llm/history"),
            "mcoi/mcoi_runtime/app/routers/llm/admin.py",
            "history_after_completion",
        ),
        (
            "operational_platform_read_models",
            "classify_operational_platform_read_model_routes",
            ("/api/v1/dependencies", "/api/v1/dependencies/{name}/impact"),
            "mcoi/mcoi_runtime/app/routers/ops/dependencies.py",
            "dependency_impact_analysis_bounded",
        ),
        (
            "operational_platform_read_models",
            "classify_operational_platform_read_model_routes",
            ("/api/v1/flags", "/api/v1/flags/{flag_id}"),
            "mcoi/mcoi_runtime/app/routers/ops/feature_flags.py",
            "check_flag_unknown",
        ),
        (
            "operational_platform_read_models",
            "classify_operational_platform_read_model_routes",
            ("/api/v1/metrics", "/api/v1/grafana/dashboard"),
            "mcoi/mcoi_runtime/app/routers/ops/metrics.py",
            "get_metrics",
        ),
        (
            "operational_platform_read_models",
            "classify_operational_platform_read_model_routes",
            ("/api/v1/rate-limit/status", "/api/v1/rate-limits/{client_id}"),
            "mcoi/mcoi_runtime/app/routers/ops/rate_limit.py",
            "rate_limit_status",
        ),
        (
            "operational_platform_read_models",
            "classify_operational_platform_read_model_routes",
            ("/api/v1/sla", "/api/v1/sla/violations"),
            "mcoi/mcoi_runtime/app/routers/data/sla.py",
            "sla_summary_endpoint_returns_bounded_governed_read_model",
        ),
        (
            "operational_platform_read_models",
            "classify_operational_platform_read_model_routes",
            ("/gateway/status",),
            "gateway/server.py",
            "health",
        ),
        (
            "conversation_memory_lifecycle",
            "classify_conversation_memory_routes",
            ("/api/v1/conversation/message", "/api/v1/conversation/{conversation_id}", "/api/v1/conversations"),
            "mcoi/mcoi_runtime/app/routers/data/conversations.py",
            "missing_conversation_bounded_404",
        ),
        (
            "engineering_puzzle_governance",
            "classify_engineering_puzzle_routes",
            ("/api/v1/engineering-puzzle/candidates/judge", "/api/v1/engineering-puzzle/goal-delta"),
            "mcoi/mcoi_runtime/app/routers/engineering_puzzle.py",
            "engineering_candidate_judgment_governed",
        ),
        (
            "replay_trace_read_models",
            "classify_replay_trace_routes",
            ("/api/v1/replay/traces",),
            "mcoi/mcoi_runtime/app/routers/agent.py",
            "replay_trace_hash_projected",
        ),
        (
            "semantic_search_read_models",
            "classify_semantic_search_routes",
            ("/api/v1/search", "/api/v1/search/stats"),
            "mcoi/mcoi_runtime/app/routers/data/search.py",
            "semantic_search_stats_bounded",
        ),
    )

    for surface_id, action_id, routes, evidence_file, witness in expected_groups:
        surface = surfaces[surface_id]
        witnesses = set(surface["runtime_witnesses"])

        assert surface["coverage_state"] == "witnessed"
        assert evidence_file in surface["evidence_files"]
        assert witness in witnesses
        assert closure_actions[action_id]["status"] == "closed"
        assert all(route in surface["representative_paths"] for route in routes)
        assert all(route_records[route]["surface_id"] == surface_id for route in routes)
        assert all(route_records[route]["coverage_state"] == "witnessed" for route in routes)

    # schema_validation_registry promoted to proven (HTTP tests in test_server_phase208.py)
    schema_surface = surfaces["schema_validation_registry"]
    assert schema_surface["coverage_state"] == "proven"
    assert "mcoi/mcoi_runtime/app/routers/data/schemas.py" in schema_surface["evidence_files"]
    assert "schema_validation_errors_explicit" in set(schema_surface["runtime_witnesses"])
    assert closure_actions["classify_schema_validation_routes"]["status"] == "closed"
    assert route_records["/api/v1/schemas"]["coverage_state"] == "proven"
    assert route_records["/api/v1/schemas/validate"]["coverage_state"] == "proven"

    # coordination_checkpoint_lifecycle promoted to proven (HTTP tests in mcoi/tests/)
    coord_surface = surfaces["coordination_checkpoint_lifecycle"]
    assert coord_surface["coverage_state"] == "proven"
    assert "mcoi/mcoi_runtime/app/routers/ops/coordination.py" in coord_surface["evidence_files"]
    assert "coordination_restore_missing_bounded" in set(coord_surface["runtime_witnesses"])
    assert closure_actions["classify_coordination_checkpoint_routes"]["status"] == "closed"
    assert route_records["/api/v1/coordination/checkpoint"]["coverage_state"] == "proven"
    assert route_records["/api/v1/coordination/restore"]["coverage_state"] == "proven"

    # data_export_lifecycle promoted to proven (HTTP tests in mcoi/tests/)
    export_surface = surfaces["data_export_lifecycle"]
    assert export_surface["coverage_state"] == "proven"
    assert "mcoi/mcoi_runtime/app/routers/data/export.py" in export_surface["evidence_files"]
    assert "data_export_format_validated" in set(export_surface["runtime_witnesses"])
    assert closure_actions["classify_data_export_routes"]["status"] == "closed"
    assert route_records["/api/v1/export"]["coverage_state"] == "proven"
    assert route_records["/api/v1/export/sources"]["coverage_state"] == "proven"

    # prompt_template_lifecycle promoted to proven (HTTP tests in mcoi/tests/)
    prompt_surface = surfaces["prompt_template_lifecycle"]
    assert prompt_surface["coverage_state"] == "proven"
    assert "mcoi/mcoi_runtime/app/routers/data/prompts.py" in prompt_surface["evidence_files"]
    assert "prompt_render_variables_validated" in set(prompt_surface["runtime_witnesses"])
    assert closure_actions["classify_prompt_template_routes"]["status"] == "closed"
    assert route_records["/api/v1/prompts"]["coverage_state"] == "proven"
    assert route_records["/api/v1/prompts/render"]["coverage_state"] == "proven"


def test_finance_approval_packet_surface_is_proven() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    finance_surface = surfaces["finance_approval_packets"]
    witnesses = set(finance_surface["runtime_witnesses"])

    assert finance_surface["coverage_state"] == "proven"
    assert finance_surface["request_proof"] == "request_proof"
    assert finance_surface["action_proof"] == "action_proof"
    assert "/api/v1/finance/approval-packets" in finance_surface["representative_paths"]
    assert "/api/v1/finance/approval-packets/operator/read-model" in finance_surface["representative_paths"]
    assert "/api/v1/finance/approval-packets/{case_id}/approval" in finance_surface["representative_paths"]
    assert "/api/v1/finance/approval-packets/{case_id}/proof" in finance_surface["representative_paths"]
    assert "mcoi/mcoi_runtime/app/routers/finance_approval.py" in finance_surface["evidence_files"]
    assert "mcoi/mcoi_runtime/contracts/finance_approval_packet.py" in finance_surface["evidence_files"]
    assert "mcoi/tests/test_finance_approval_packet.py" in finance_surface["evidence_files"]
    assert "mcoi/tests/test_finance_approval_router.py" in finance_surface["evidence_files"]
    assert "schemas/finance_approval_email_calendar_binding_receipt.schema.json" in finance_surface["evidence_files"]
    assert "schemas/finance_approval_email_calendar_operator_input_request.schema.json" in finance_surface["evidence_files"]
    assert "schemas/finance_approval_email_calendar_live_receipt.schema.json" in finance_surface["evidence_files"]
    assert "schemas/finance_approval_handoff_packet.schema.json" in finance_surface["evidence_files"]
    assert "schemas/finance_approval_live_handoff_chain_validation.schema.json" in finance_surface["evidence_files"]
    assert "scripts/plan_finance_approval_live_handoff.py" in finance_surface["evidence_files"]
    assert "scripts/emit_finance_approval_email_calendar_binding_receipt.py" in finance_surface["evidence_files"]
    assert "scripts/emit_finance_approval_email_calendar_operator_input_request.py" in finance_surface["evidence_files"]
    assert "scripts/validate_finance_approval_email_calendar_binding_receipt.py" in finance_surface["evidence_files"]
    assert "scripts/validate_finance_approval_email_calendar_operator_input_request.py" in finance_surface["evidence_files"]
    assert "scripts/produce_finance_approval_handoff_packet.py" in finance_surface["evidence_files"]
    assert "scripts/validate_finance_approval_handoff_packet_schema.py" in finance_surface["evidence_files"]
    assert "scripts/validate_finance_approval_live_handoff_chain.py" in finance_surface["evidence_files"]
    assert "tests/test_plan_finance_approval_live_handoff.py" in finance_surface["evidence_files"]
    assert "tests/test_emit_finance_approval_email_calendar_binding_receipt.py" in finance_surface["evidence_files"]
    assert "tests/test_emit_finance_approval_email_calendar_operator_input_request.py" in finance_surface["evidence_files"]
    assert "tests/test_validate_finance_approval_email_calendar_binding_receipt.py" in finance_surface["evidence_files"]
    assert "tests/test_validate_finance_approval_email_calendar_operator_input_request.py" in finance_surface["evidence_files"]
    assert "tests/test_produce_finance_approval_handoff_packet.py" in finance_surface["evidence_files"]
    assert "tests/test_finance_approval_handoff_packet_schema.py" in finance_surface["evidence_files"]
    assert "tests/test_validate_finance_approval_live_handoff_chain.py" in finance_surface["evidence_files"]
    assert "schemas/finance_approval_payment_provider_binding_receipt.schema.json" in finance_surface["evidence_files"]
    assert "schemas/finance_approval_payment_closure_receipt.schema.json" in finance_surface["evidence_files"]
    assert "scripts/emit_finance_approval_payment_provider_binding_receipt.py" in finance_surface["evidence_files"]
    assert "scripts/produce_finance_approval_payment_closure_receipt.py" in finance_surface["evidence_files"]
    assert "scripts/validate_finance_approval_payment_provider_binding_receipt.py" in finance_surface["evidence_files"]
    assert "scripts/validate_finance_approval_payment_closure_receipt.py" in finance_surface["evidence_files"]
    assert "tests/test_emit_finance_approval_payment_provider_binding_receipt.py" in finance_surface["evidence_files"]
    assert "tests/test_produce_finance_approval_payment_closure_receipt.py" in finance_surface["evidence_files"]
    assert "tests/test_validate_finance_approval_payment_provider_binding_receipt.py" in finance_surface["evidence_files"]
    assert "tests/test_validate_finance_approval_payment_closure_receipt.py" in finance_surface["evidence_files"]
    assert "tests/test_finance_payment_provider_binding_examples.py" in finance_surface["evidence_files"]
    assert "examples/finance_payment_provider_binding_receipt_stripe.json" in finance_surface["evidence_files"]
    assert "examples/finance_payment_closure_receipt_stripe_bound.json" in finance_surface["evidence_files"]
    assert "finance_packet_policy_reasons_explicit" in witnesses
    assert "blocked_packet_emits_no_effect" in witnesses
    assert "approval_action_binds_approval_effect_and_closure_refs" in witnesses
    assert "payment_handoff_prepared_without_live_payment_claim" in witnesses
    assert "email_calendar_binding_receipt_requires_worker_token_and_readonly_scope" in witnesses
    assert "email_calendar_operator_input_request_names_missing_inputs_without_values" in witnesses
    assert "email_calendar_handoff_plan_requires_binding_receipt_ready" in witnesses
    assert "email_calendar_handoff_packet_requires_live_receipt_ready" in witnesses
    assert "payment_receipt_and_ledger_reconciliation_required_for_payment_closure" in witnesses
    assert "payment_closure_receipt_validator_blocks_unbound_evidence" in witnesses
    assert "payment_closure_receipt_producer_emits_ready_sandbox_evidence" in witnesses
    assert "payment_provider_binding_receipt_redacts_credentials_and_scopes_provider" in witnesses
    assert "payment_closure_producer_consumes_provider_binding_receipt" in witnesses
    assert "payment_closure_validator_verifies_provider_binding_receipt_object" in witnesses
    assert "payment_closure_receipt_producer_requires_provider_binding_for_nonsandbox" in witnesses
    assert "payment_closure_example_evidence_validates_provider_binding_chain" in witnesses
    assert "packet_proof_requires_policy_evidence_and_closure_for_closed_states" in witnesses
    assert "operator_read_model_bounds_visible_packets_and_counts" in witnesses
    finance_integrity = {
        record["surface_id"]: record
        for record in matrix["witness_integrity"]["surfaces"]
    }["finance_approval_packets"]
    assert finance_integrity["exact_test_anchor_count"] == 18
    assert finance_integrity["unanchored_witness_count"] == 0
    assert closure_actions["classify_finance_approval_packet_routes"]["status"] == "closed"


def test_federated_control_plane_surface_is_witnessed() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    federation_surface = surfaces["federated_control_plane"]
    witnesses = set(federation_surface["runtime_witnesses"])
    route_records = {
        record["route"]: record
        for record in matrix["route_coverage"]["routes"]
    }

    assert federation_surface["coverage_state"] == "proven"
    assert federation_surface["request_proof"] == "request_proof"
    assert federation_surface["action_proof"] == "action_proof"
    assert "/api/v1/federation/summary" in federation_surface["representative_paths"]
    assert "/api/v1/federation/clusters" in federation_surface["representative_paths"]
    assert "/api/v1/federation/policies" in federation_surface["representative_paths"]
    assert "/api/v1/federation/policy-sync" in federation_surface["representative_paths"]
    assert "gateway/federated_control.py" in federation_surface["evidence_files"]
    assert "gateway/server.py" in federation_surface["evidence_files"]
    assert "mcoi/mcoi_runtime/app/routers/federation.py" in federation_surface["evidence_files"]
    assert "mcoi/mcoi_runtime/core/federated_control_plane.py" in federation_surface["evidence_files"]
    assert "schemas/federated_control_snapshot.schema.json" in federation_surface["evidence_files"]
    assert "tests/test_gateway/test_federated_control.py" in federation_surface["evidence_files"]
    assert "signed_policy_metadata_only_sync" in witnesses
    assert "federation_control_routes_publish_and_sync_policy_metadata" in witnesses
    assert "invalid_signature_denied_before_local_acceptance" in witnesses
    assert "policy_not_allowed_for_cluster_denied" in witnesses
    assert "federation_policy_sync_route_returns_denied_receipt_for_disallowed_policy" in witnesses
    assert "unsynced_policy_denied_locally" in witnesses
    assert "tenant_region_mismatch_denied_locally" in witnesses
    assert "central_data_transfer_forbidden" in witnesses
    assert "federation_policy_publish_route_rejects_tenant_data_payload" in witnesses
    assert "federated_snapshot_schema_valid" in witnesses
    assert route_records["/api/v1/federation/clusters"]["surface_id"] == "federated_control_plane"
    assert route_records["/api/v1/federation/policies"]["surface_id"] == "federated_control_plane"
    assert route_records["/api/v1/federation/policy-sync"]["surface_id"] == "federated_control_plane"
    assert closure_actions["publish_federated_control_plane_read_model"]["status"] == "closed"
    assert closure_actions["expose_federated_policy_sync_control_routes"]["status"] == "closed"


def test_gateway_runtime_witnesses_bind_closure_invariants() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    gateway_surface = surfaces["gateway_capability_fabric"]
    witnesses = set(gateway_surface["runtime_witnesses"])

    assert gateway_surface["action_proof"] == "action_proof"
    assert "/capability-fabric/admission-audits" in gateway_surface["representative_paths"]
    assert "/capability-fabric/capsule-admissions" in gateway_surface["representative_paths"]
    assert "/capability-fabric/capsule-admission-receipts" in gateway_surface["representative_paths"]
    assert "/commands/{command_id}/closure" in gateway_surface["representative_paths"]
    assert "/commands/{command_id}/capability-admission" in gateway_surface["representative_paths"]
    assert "/commands/{command_id}/universal-action-proof" in gateway_surface["representative_paths"]
    assert "/commands/{command_id}/universal-action-orchestration" in gateway_surface["representative_paths"]
    assert "/commands/{command_id}/interpretation-receipt" in gateway_surface["representative_paths"]
    assert "/operator/universal-actions/read-model" in gateway_surface["representative_paths"]
    assert "/operator/universal-actions" in gateway_surface["representative_paths"]
    assert "/operator/receipts/read-model" in gateway_surface["representative_paths"]
    assert "/operator/receipts" in gateway_surface["representative_paths"]
    assert "/operator/current-task/read-model" in gateway_surface["representative_paths"]
    assert "/operator/current-task" in gateway_surface["representative_paths"]
    assert "DomainCapsuleCompiler.compile" in gateway_surface["representative_paths"]
    assert "install_certified_capsule_with_handoff_evidence" in gateway_surface["representative_paths"]
    assert "gateway/capability_capsule_installer.py" in gateway_surface["evidence_files"]
    assert "gateway/command_spine.py" in gateway_surface["evidence_files"]
    assert "mcoi/mcoi_runtime/app/governed_execution.py" in gateway_surface["evidence_files"]
    assert "mcoi/mcoi_runtime/core/domain_capsule_compiler.py" in gateway_surface["evidence_files"]
    assert (
        "schemas/command_interpretation_receipt_read_model.schema.json"
        in gateway_surface["evidence_files"]
    )
    assert "tests/test_gateway/test_capability_capsule_installer.py" in gateway_surface["evidence_files"]
    assert "tests/test_gateway/test_webhooks.py" in gateway_surface["evidence_files"]
    assert "tests/test_governed_capability_fabric.py" in gateway_surface["evidence_files"]
    assert "command_lifecycle_events_are_hash_linked" in witnesses
    assert "terminal_closure_requires_evidence_refs" in witnesses
    assert "terminal_closure_exposes_whqr_replay_ref" in witnesses
    assert "successful_response_is_bound_to_response_evidence_closure" in witnesses
    assert "command_interpretation_receipt_read_model_bounds_raw_message" in witnesses
    assert "command_interpretation_receipt_read_model_schema_valid" in witnesses
    assert "command_interpretation_receipt_requires_operator_authority" in witnesses
    assert "command_interpretation_receipt_replays_from_command_store" in witnesses
    assert "universal_action_proof_replays_from_command_events" in witnesses
    assert "universal_action_proof_exposes_whqr_replay_ref" in witnesses
    assert "universal_action_orchestration_replays_from_command_events" in witnesses
    assert "universal_action_orchestration_exposes_whqr_replay_ref" in witnesses
    assert "operator_universal_action_read_model_filters_command_proofs" in witnesses
    assert "operator_universal_action_read_model_exposes_whqr_replay_ref" in witnesses
    assert "operator_universal_action_console_renders_replay_state" in witnesses
    assert "capability_admission_audits_filter_status" in witnesses
    assert "command_capability_admission_read_model_reports_accepted_witness" in witnesses
    assert "capsule_compiler_emits_certification_evidence_manifest" in witnesses
    assert "capsule_installer_stamps_admission_receipt" in witnesses
    assert "capsule_admission_operator_endpoint_lists_receipt" in witnesses
    assert "invalid_capsule_admission_preserves_registry_state" in witnesses
    assert "physical_capsule_admission_runs_promotion_preflight" in witnesses
    assert closure_actions["classify_gateway_capability_admission_routes"]["status"] == "closed"


def test_capability_worker_execution_surface_is_witnessed() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    worker_surface = surfaces["capability_worker_execution"]
    witnesses = set(worker_surface["runtime_witnesses"])

    assert worker_surface["coverage_state"] == "proven"
    assert worker_surface["request_proof"] == "request_proof"
    assert worker_surface["action_proof"] == "action_proof"
    assert worker_surface["audit"] == "audit_chain"
    assert "/capability/execute" in worker_surface["representative_paths"]
    assert "gateway/capability_worker.py" in worker_surface["evidence_files"]
    assert "gateway/capability_isolation.py" in worker_surface["evidence_files"]
    assert "gateway/capability_dispatch.py" in worker_surface["evidence_files"]
    assert "tests/test_gateway/test_capability_worker.py" in worker_surface["evidence_files"]
    assert "signed_capability_request_required" in witnesses
    assert "response_signature_verified" in witnesses
    assert "input_hash_mismatch_rejected" in witnesses
    assert "intent_boundary_mismatch_rejected" in witnesses
    assert "non_isolated_boundary_rejected" in witnesses
    assert "capability_worker_runs_computer_command_through_sandbox_receipt" in witnesses
    assert "local_smoke_stub_bound_to_local_environment" in witnesses
    assert "capability_worker_execution" in closure_actions["classify_gateway_capability_admission_routes"]["surfaces"]


def test_restricted_adapter_worker_boundary_surface_is_witnessed() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    worker_surface = surfaces["restricted_adapter_worker_boundaries"]
    witnesses = set(worker_surface["runtime_witnesses"])

    assert worker_surface["coverage_state"] == "witnessed"
    assert worker_surface["request_proof"] == "request_proof"
    assert worker_surface["action_proof"] == "action_proof"
    assert worker_surface["audit"] == "audit_chain"
    assert {
        "/browser/execute",
        "/document/execute",
        "/email-calendar/execute",
        "/messaging/execute",
        "/phone/execute",
        "/voice/execute",
    }.issubset(set(worker_surface["representative_paths"]))
    assert {
        "gateway/browser_worker.py",
        "gateway/document_worker.py",
        "gateway/email_calendar_worker.py",
        "gateway/messaging_worker.py",
        "gateway/phone_worker.py",
        "gateway/voice_worker.py",
    }.issubset(set(worker_surface["evidence_files"]))
    assert {
        "browser_worker_parse_error_detail_is_bounded",
        "document_worker_parse_error_detail_is_bounded",
        "email_calendar_worker_parse_error_detail_is_bounded",
        "messaging_worker_parse_error_detail_is_bounded",
        "phone_worker_parse_error_detail_is_bounded",
        "voice_worker_parse_error_detail_is_bounded",
    }.issubset(witnesses)


def test_data_governance_controls_surface_is_proven() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    data_surface = surfaces["data_governance_controls"]
    witnesses = set(data_surface["runtime_witnesses"])

    assert data_surface["coverage_state"] == "proven"
    assert data_surface["request_proof"] == "request_proof"
    assert data_surface["action_proof"] == "action_proof"
    assert "/api/v1/data-governance/classify" in data_surface["representative_paths"]
    assert "/api/v1/data-governance/evaluate" in data_surface["representative_paths"]
    assert "mcoi/mcoi_runtime/app/routers/data/governance.py" in data_surface["evidence_files"]
    assert "mcoi/mcoi_runtime/core/data_governance.py" in data_surface["evidence_files"]
    assert "mcoi/tests/test_data_governance_endpoints.py" in data_surface["evidence_files"]
    assert "data_governance_state_hash" in witnesses
    assert "data_governance_action_proof" in witnesses
    assert "tenant_visible_violation_read_model" in witnesses
    assert closure_actions["classify_data_governance_routes"]["status"] == "closed"


def test_compliance_evidence_exports_surface_is_proven() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    compliance_surface = surfaces["compliance_evidence_exports"]
    witnesses = set(compliance_surface["runtime_witnesses"])

    assert compliance_surface["coverage_state"] == "proven"
    assert compliance_surface["request_proof"] == "request_proof"
    assert compliance_surface["action_proof"] == "action_proof"
    assert "/api/v1/compliance/audit-package" in compliance_surface["representative_paths"]
    assert "/api/v1/compliance/summary" in compliance_surface["representative_paths"]
    assert "mcoi/mcoi_runtime/app/routers/compliance.py" in compliance_surface["evidence_files"]
    assert "mcoi/tests/test_compliance_export.py" in compliance_surface["evidence_files"]
    assert "scripts/compliance_alignment_matrix.py" in compliance_surface["evidence_files"]
    assert "compliance_package_hash" in witnesses
    assert "audit_chain_verification" in witnesses
    assert "self_audited_export_event" in witnesses
    assert closure_actions["classify_compliance_evidence_exports"]["status"] == "closed"


def test_tenant_governance_lifecycle_surface_is_proven() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    tenant_surface = surfaces["tenant_governance_lifecycle"]
    witnesses = set(tenant_surface["runtime_witnesses"])

    assert tenant_surface["coverage_state"] == "proven"
    assert tenant_surface["request_proof"] == "request_proof"
    assert tenant_surface["action_proof"] == "action_proof"
    assert "/api/v1/tenant/budget" in tenant_surface["representative_paths"]
    assert "/api/v1/tenant/{tenant_id}/budget" in tenant_surface["representative_paths"]
    assert "/api/v1/tenant/{tenant_id}/ledger" in tenant_surface["representative_paths"]
    assert "/api/v1/tenants" in tenant_surface["representative_paths"]
    assert "/api/v1/tenant/register" in tenant_surface["representative_paths"]
    assert "/api/v1/tenant/{tenant_id}/status" in tenant_surface["representative_paths"]
    assert "/api/v1/tenant/gates" in tenant_surface["representative_paths"]
    assert "/api/v1/usage/{tenant_id}" in tenant_surface["representative_paths"]
    assert "/api/v1/tenant-isolation/audits" in tenant_surface["representative_paths"]
    assert "/api/v1/quotas/{tenant_id}" in tenant_surface["representative_paths"]
    assert "/api/v1/partitions" in tenant_surface["representative_paths"]
    assert "mcoi/mcoi_runtime/app/routers/tenant.py" in tenant_surface["evidence_files"]
    assert "mcoi/mcoi_runtime/governance/guards/budget.py" in tenant_surface["evidence_files"]
    assert "mcoi/mcoi_runtime/governance/guards/tenant_gating.py" in tenant_surface["evidence_files"]
    assert "mcoi/tests/test_server_phase202.py" in tenant_surface["evidence_files"]
    assert "mcoi/tests/test_governance_endpoints.py" in tenant_surface["evidence_files"]
    assert "mcoi/tests/test_usage_reporter.py" in tenant_surface["evidence_files"]
    assert "mcoi/tests/test_tenant_analytics.py" in tenant_surface["evidence_files"]
    assert "mcoi/tests/test_tenant_quota.py" in tenant_surface["evidence_files"]
    assert "mcoi/tests/test_phase232.py" in tenant_surface["evidence_files"]
    assert "mcoi/tests/test_server_capability_helpers.py" in tenant_surface["evidence_files"]
    assert "tenant_budget_create_emits_action_proof" in witnesses
    assert "tenant_budget_create_records_audit" in witnesses
    assert "tenant_budget_read_models_scoped_by_tenant" in witnesses
    assert "tenant_ledger_queries_bounded" in witnesses
    assert "tenant_registry_lifecycle_errors_sanitized" in witnesses
    assert "tenant_register_emits_action_proof" in witnesses
    assert "tenant_status_update_emits_action_proof" in witnesses
    assert "tenant_gate_read_models_governed" in witnesses
    assert "tenant_gate_persistence_read_model_included" in witnesses
    assert "tenant_usage_read_model_scoped" in witnesses
    assert "tenant_analytics_read_model_scoped" in witnesses
    assert "tenant_isolation_verify_governed" in witnesses
    assert "tenant_isolation_audits_bounded" in witnesses
    assert "tenant_quota_read_models_bounded" in witnesses
    assert "tenant_partition_read_model_bounded" in witnesses
    tenant_integrity = {
        record["surface_id"]: record
        for record in matrix["witness_integrity"]["surfaces"]
    }["tenant_governance_lifecycle"]
    assert tenant_integrity["exact_test_anchor_count"] == 15
    assert tenant_integrity["unanchored_witness_count"] == 0
    assert closure_actions["classify_tenant_governance_lifecycle_routes"]["status"] == "closed"


def test_runbook_learning_lifecycle_surface_is_proven() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    runbook_surface = surfaces["runbook_learning_lifecycle"]
    witnesses = set(runbook_surface["runtime_witnesses"])

    assert runbook_surface["coverage_state"] == "proven"
    assert runbook_surface["request_proof"] == "request_proof"
    assert runbook_surface["action_proof"] == "action_proof"
    assert "/api/v1/runbooks" in runbook_surface["representative_paths"]
    assert "/api/v1/runbooks/analyze" in runbook_surface["representative_paths"]
    assert "/api/v1/runbooks/promote" in runbook_surface["representative_paths"]
    assert "/api/v1/runbooks/approve" in runbook_surface["representative_paths"]
    assert "/api/v1/runbooks/{runbook_id}/activate" in runbook_surface["representative_paths"]
    assert "/api/v1/runbooks/{runbook_id}/retire" in runbook_surface["representative_paths"]
    assert "/api/v1/mil-audit/admit-runbook" in runbook_surface["representative_paths"]
    assert "/api/v1/mil-audit/runbooks" in runbook_surface["representative_paths"]
    assert "/api/v1/mil-audit/runbooks/{runbook_id}" in runbook_surface["representative_paths"]
    assert "mcoi/mcoi_runtime/app/routers/runbooks.py" in runbook_surface["evidence_files"]
    assert "mcoi/mcoi_runtime/app/routers/mil_audit.py" in runbook_surface["evidence_files"]
    assert "mcoi/mcoi_runtime/core/runbook_learning.py" in runbook_surface["evidence_files"]
    assert "mcoi/tests/test_mil_audit_router.py" in runbook_surface["evidence_files"]
    assert "mcoi/tests/test_runbook_learning.py" in runbook_surface["evidence_files"]
    assert "examples/mil_audit_runbook_operator_checklist.json" in runbook_surface["evidence_files"]
    assert "scripts/validate_mil_audit_runbook_operator_checklist.py" in runbook_surface["evidence_files"]
    assert "scripts/preflight_mil_audit_runbook_workflow.py" in runbook_surface["evidence_files"]
    assert "tests/test_validate_mil_audit_runbook_operator_checklist.py" in runbook_surface["evidence_files"]
    assert "tests/test_preflight_mil_audit_runbook_workflow.py" in runbook_surface["evidence_files"]
    assert "patterns_detected_from_audit_trail" in witnesses
    assert "promotion_requires_detected_pattern" in witnesses
    assert "approval_required_before_activation" in witnesses
    assert "retirement_requires_active_runbook" in witnesses
    assert "promote_and_approve_audit_records" in witnesses
    assert "mil_audit_replay_admits_runbook" in witnesses
    assert "mil_audit_operator_checklist_validated" in witnesses
    assert "mil_audit_runbook_preflight_ready" in witnesses
    assert "sanitized_runbook_error_details" in witnesses
    assert "runbook_pattern_read_models_bounded" in witnesses
    assert "runbook_responses_governed" in witnesses
    assert closure_actions["classify_runbook_learning_routes"]["status"] == "closed"


def test_software_outcome_learning_surface_is_witnessed() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    learning_surface = surfaces["software_outcome_learning"]
    witnesses = set(learning_surface["runtime_witnesses"])

    assert learning_surface["coverage_state"] == "witnessed"
    assert learning_surface["request_proof"] == "request_proof"
    assert learning_surface["action_proof"] == "action_proof"
    assert "mullu_software_change" in learning_surface["representative_paths"]
    assert "mcoi/mcoi_runtime/mcp/server.py" in learning_surface["evidence_files"]
    assert "mcoi/mcoi_runtime/contracts/software_learning.py" in learning_surface["evidence_files"]
    assert "mcoi/mcoi_runtime/core/software_learning.py" in learning_surface["evidence_files"]
    assert "mcoi/tests/test_mcp_software_change.py" in learning_surface["evidence_files"]
    assert "mcoi/tests/test_software_learning.py" in learning_surface["evidence_files"]
    assert "software_learning_schema_default_enabled" in witnesses
    assert "passed_gates_yield_procedural_memory" in witnesses
    assert "failed_gates_yield_hashed_risk_memory" in witnesses
    assert "raw_logs_rejected_before_planning_use" in witnesses
    assert "rollback_failure_defers_learning" in witnesses
    assert "planning_projection_requires_admitted_matching_decision" in witnesses
    assert "software_learning_errors_are_bounded" in witnesses
    assert closure_actions["publish_software_outcome_learning_contract"]["status"] == "closed"


def test_authority_operator_controls_surface_is_witnessed() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    operator_surface = surfaces["authority_operator_controls"]
    witnesses = set(operator_surface["runtime_witnesses"])

    assert operator_surface["coverage_state"] == "witnessed"
    assert operator_surface["request_proof"] == "request_proof"
    assert operator_surface["action_proof"] == "action_proof"
    assert "/authority/operator" in operator_surface["representative_paths"]
    assert "/authority/operator-audit" in operator_surface["representative_paths"]
    assert "/authority/approval-chains/expire-overdue" in operator_surface["representative_paths"]
    assert "/authority/obligations/{obligation_id}/satisfy" in operator_surface["representative_paths"]
    assert "gateway/server.py" in operator_surface["evidence_files"]
    assert "gateway/authority_obligation_mesh.py" in operator_surface["evidence_files"]
    assert "scripts/collect_runtime_conformance.py" in operator_surface["evidence_files"]
    assert "tests/test_gateway/test_webhooks.py" in operator_surface["evidence_files"]
    assert "operator_access_guard" in witnesses
    assert "operator_audit_events" in witnesses
    assert "ownership_policy_read_models" in witnesses
    assert "approval_expiration_witness" in witnesses
    assert "obligation_satisfaction_escalation_witness" in witnesses
    assert closure_actions["classify_authority_operator_controls"]["status"] == "closed"


def test_approval_engine_lifecycle_surface_records_effect_receipts() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    approval_surface = surfaces["approval_engine_lifecycle"]
    witnesses = set(approval_surface["runtime_witnesses"])

    assert approval_surface["coverage_state"] == "witnessed"
    assert approval_surface["request_proof"] == "request_proof"
    assert approval_surface["action_proof"] == "action_proof"
    assert "ApprovalEngine.submit_request" in approval_surface["representative_paths"]
    assert "ApprovalEngine.record_decision" in approval_surface["representative_paths"]
    assert "ApprovalEngine.consume_approval" in approval_surface["representative_paths"]
    assert "ApprovalEngine.revoke" in approval_surface["representative_paths"]
    assert "ApprovalEngine.record_override" in approval_surface["representative_paths"]
    assert "mcoi/mcoi_runtime/core/approval.py" in approval_surface["evidence_files"]
    assert "mcoi/mcoi_runtime/contracts/approval.py" in approval_surface["evidence_files"]
    assert "mcoi/tests/test_approval.py" in approval_surface["evidence_files"]
    assert "approval_request_mutation_receipt_emitted" in witnesses
    assert "approval_decision_mutation_receipt_emitted" in witnesses
    assert "approval_consumption_mutation_receipt_emitted" in witnesses
    assert "approval_revocation_mutation_receipt_emitted" in witnesses
    assert "approval_override_mutation_receipt_emitted" in witnesses
    assert "approval_mutation_receipt_closes_effect_assurance" in witnesses
    assert closure_actions["bind_approval_engine_mutations_to_effect_receipts"]["status"] == "closed"


def test_effect_assurance_graph_commit_surface_records_effect_receipts() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    graph_commit_surface = surfaces["effect_assurance_graph_commit"]
    witnesses = set(graph_commit_surface["runtime_witnesses"])

    assert graph_commit_surface["coverage_state"] == "witnessed"
    assert graph_commit_surface["request_proof"] == "request_proof"
    assert graph_commit_surface["action_proof"] == "action_proof"
    assert "EffectAssuranceGate.commit_graph" in graph_commit_surface["representative_paths"]
    assert "EffectAssuranceGate.graph_commit_receipts" in graph_commit_surface["representative_paths"]
    assert "EffectAssuranceGate.graph_commit_effect_records" in graph_commit_surface["representative_paths"]
    assert "InMemoryEffectGraphCommitReceiptStore" in graph_commit_surface["representative_paths"]
    assert "JsonlEffectGraphCommitReceiptStore" in graph_commit_surface["representative_paths"]
    assert "bootstrap_runtime" in graph_commit_surface["representative_paths"]
    assert "AppConfig.effect_graph_commit_receipt_store_path" in graph_commit_surface["representative_paths"]
    assert "mcoi/mcoi_runtime/core/effect_assurance.py" in graph_commit_surface["evidence_files"]
    assert "mcoi/mcoi_runtime/core/operational_graph.py" in graph_commit_surface["evidence_files"]
    assert "mcoi/mcoi_runtime/app/bootstrap.py" in graph_commit_surface["evidence_files"]
    assert "mcoi/mcoi_runtime/app/config.py" in graph_commit_surface["evidence_files"]
    assert "mcoi/tests/test_effect_assurance_core.py" in graph_commit_surface["evidence_files"]
    assert "mcoi/tests/test_bootstrap.py" in graph_commit_surface["evidence_files"]
    assert "effect_graph_commit_requires_match" in witnesses
    assert "effect_graph_commit_receipt_emitted" in witnesses
    assert "effect_graph_commit_receipt_converts_to_actual_effect" in witnesses
    assert "effect_graph_commit_receipt_closes_effect_assurance" in witnesses
    assert "effect_graph_commit_receipt_store_replays_records" in witnesses
    assert "bootstrap_wires_durable_effect_graph_commit_receipt_store" in witnesses
    assert closure_actions["bind_effect_graph_commits_to_effect_receipts"]["status"] == "closed"
    assert closure_actions["persist_effect_graph_commit_receipts"]["status"] == "closed"
    assert closure_actions["wire_effect_graph_commit_receipt_store_into_bootstrap"]["status"] == "closed"


def test_job_engine_lifecycle_surface_records_effect_receipts() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    job_surface = surfaces["job_engine_lifecycle"]
    witnesses = set(job_surface["runtime_witnesses"])

    assert job_surface["coverage_state"] == "witnessed"
    assert job_surface["request_proof"] == "request_proof"
    assert job_surface["action_proof"] == "action_proof"
    assert "JobEngine.create_job" in job_surface["representative_paths"]
    assert "JobEngine.start_job" in job_surface["representative_paths"]
    assert "JobEngine.pause_job" in job_surface["representative_paths"]
    assert "JobEngine.resume_job" in job_surface["representative_paths"]
    assert "JobEngine.complete_job" in job_surface["representative_paths"]
    assert "JobEngine.fail_job" in job_surface["representative_paths"]
    assert "JobEngine.cancel_job" in job_surface["representative_paths"]
    assert "JobEngine.restore_job" in job_surface["representative_paths"]
    assert "mcoi/mcoi_runtime/core/jobs.py" in job_surface["evidence_files"]
    assert "mcoi/mcoi_runtime/contracts/job.py" in job_surface["evidence_files"]
    assert "mcoi/tests/test_job_core.py" in job_surface["evidence_files"]
    assert "job_create_mutation_receipt_emitted" in witnesses
    assert "job_start_mutation_receipt_emitted" in witnesses
    assert "job_pause_resume_mutation_receipts_emitted" in witnesses
    assert "job_terminal_mutation_receipts_emitted" in witnesses
    assert "job_restore_mutation_receipt_emitted" in witnesses
    assert "job_mutation_receipt_closes_effect_assurance" in witnesses
    assert closure_actions["bind_job_engine_mutations_to_effect_receipts"]["status"] == "closed"


def test_authority_obligation_mesh_binds_command_authority_read_model() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    authority_surface = surfaces["authority_obligation_mesh"]
    witnesses = set(authority_surface["runtime_witnesses"])

    assert authority_surface["coverage_state"] == "witnessed"
    assert authority_surface["request_proof"] == "request_proof"
    assert authority_surface["action_proof"] == "action_proof"
    assert "/commands/{command_id}/authority" in authority_surface["representative_paths"]
    assert "gateway/authority_obligation_mesh.py" in authority_surface["evidence_files"]
    assert "tests/test_gateway/test_webhooks.py" in authority_surface["evidence_files"]
    assert "command_authority_read_model_bound_to_approval_chain" in witnesses
    assert "authority_obligation_mesh" in closure_actions["bound_authority_read_models_to_paginated_windows"]["surfaces"]


def test_audit_chain_api_surface_is_witnessed() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    audit_surface = surfaces["audit_chain_api"]
    witnesses = set(audit_surface["runtime_witnesses"])

    assert audit_surface["coverage_state"] == "witnessed"
    assert audit_surface["request_proof"] == "read_model"
    assert audit_surface["action_proof"] == "request_proof"
    assert "/api/v1/audit/verify" in audit_surface["representative_paths"]
    assert "/api/v1/audit/anchor/{anchor_id}/verify" in audit_surface["representative_paths"]
    assert "/api/v1/logs" in audit_surface["representative_paths"]
    assert "mcoi/mcoi_runtime/app/routers/audit.py" in audit_surface["evidence_files"]
    assert "mcoi/mcoi_runtime/governance/audit/trail.py" in audit_surface["evidence_files"]
    assert "mcoi/mcoi_runtime/governance/audit/anchor.py" in audit_surface["evidence_files"]
    assert "mcoi/tests/test_audit_trail.py" in audit_surface["evidence_files"]
    assert "mcoi/tests/test_v4_28_audit_checkpoint.py" in audit_surface["evidence_files"]
    assert "audit_chain_verify_endpoint" in witnesses
    assert "audit_anchor_checkpoint_created" in witnesses
    assert "audit_anchor_verification_endpoint" in witnesses
    assert "audit_logs_read_model_bounded" in witnesses
    assert closure_actions["classify_audit_chain_api"]["status"] == "closed"


def test_event_bus_operations_surface_is_proven() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    event_surface = surfaces["event_bus_operations"]
    witnesses = set(event_surface["runtime_witnesses"])

    assert event_surface["coverage_state"] == "proven"
    assert event_surface["request_proof"] == "request_proof"
    assert event_surface["action_proof"] == "action_proof"
    assert "/api/v1/events" in event_surface["representative_paths"]
    assert "/api/v1/events/publish" in event_surface["representative_paths"]
    assert "/api/v1/events/summary" in event_surface["representative_paths"]
    assert "/api/v1/events/store/summary" in event_surface["representative_paths"]
    assert "mcoi/mcoi_runtime/app/routers/audit.py" in event_surface["evidence_files"]
    assert "mcoi/tests/test_server_phase206.py" in event_surface["evidence_files"]
    assert "mcoi/tests/test_server_phase207.py" in event_surface["evidence_files"]
    assert "event_publish_hash_bound" in witnesses
    assert "event_history_filter_bounded" in witnesses
    assert "event_store_summary_governed" in witnesses
    assert "pipeline_completion_event_visible" in witnesses
    assert closure_actions["classify_event_bus_operations_routes"]["status"] == "closed"


def test_api_key_lifecycle_surface_is_witnessed() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    api_key_surface = surfaces["api_key_lifecycle"]
    witnesses = set(api_key_surface["runtime_witnesses"])
    route_records = {
        record["route"]: record
        for record in matrix["route_coverage"]["routes"]
    }

    assert api_key_surface["coverage_state"] == "witnessed"
    assert api_key_surface["request_proof"] == "request_proof"
    assert api_key_surface["action_proof"] == "action_proof"
    assert "/api/v1/api-keys" in api_key_surface["representative_paths"]
    assert "/api/v1/api-keys/{key_id}" in api_key_surface["representative_paths"]
    assert "mcoi/mcoi_runtime/app/routers/data/api_keys.py" in api_key_surface["evidence_files"]
    assert "mcoi/mcoi_runtime/governance/auth/api_key.py" in api_key_surface["evidence_files"]
    assert "mcoi/tests/test_api_key_lifecycle.py" in api_key_surface["evidence_files"]
    assert "mcoi/tests/test_server_phase216.py" in api_key_surface["evidence_files"]
    assert "api_key_create_rejects_wildcard_when_disabled" in witnesses
    assert "api_key_create_rejects_empty_scopes" in witnesses
    assert "api_key_revoke_missing_is_bounded" in witnesses
    assert "api_key_rotation_links_old_and_new_keys" in witnesses
    assert "api_key_expiration_and_stale_detection" in witnesses
    assert route_records["/api/v1/api-keys"]["coverage_state"] == "witnessed"
    assert route_records["/api/v1/api-keys"]["surface_id"] == "api_key_lifecycle"
    assert route_records["/api/v1/api-keys/{key_id}"]["coverage_state"] == "witnessed"
    assert route_records["/api/v1/api-keys/{key_id}"]["surface_id"] == "api_key_lifecycle"
    assert closure_actions["classify_api_key_lifecycle_routes"]["status"] == "closed"


def test_conversation_memory_lifecycle_surface_is_witnessed() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    route_records = {
        record["route"]: record
        for record in matrix["route_coverage"]["routes"]
    }
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    conversation_surface = surfaces["conversation_memory_lifecycle"]
    witnesses = set(conversation_surface["runtime_witnesses"])

    assert conversation_surface["coverage_state"] == "witnessed"
    assert conversation_surface["request_proof"] == "request_proof"
    assert conversation_surface["action_proof"] == "action_proof"
    assert conversation_surface["audit"] == "audit_chain"
    assert "/api/v1/conversation/message" in conversation_surface["representative_paths"]
    assert "/api/v1/conversation/{conversation_id}" in conversation_surface["representative_paths"]
    assert "/api/v1/conversations" in conversation_surface["representative_paths"]
    assert "mcoi/mcoi_runtime/app/routers/data/conversations.py" in conversation_surface["evidence_files"]
    assert "mcoi/mcoi_runtime/core/conversation_memory.py" in conversation_surface["evidence_files"]
    assert "mcoi/tests/test_server_phase208.py" in conversation_surface["evidence_files"]
    assert "mcoi/tests/test_conversation_memory.py" in conversation_surface["evidence_files"]
    assert "conversation_message_append_increments_count" in witnesses
    assert "conversation_history_returns_messages_and_summary" in witnesses
    assert "conversation_store_tenant_filtering" in witnesses
    assert "conversation_memory_pruning_bounded" in witnesses
    assert route_records["/api/v1/conversation/message"]["coverage_state"] == "witnessed"
    assert route_records["/api/v1/conversation/message"]["surface_id"] == "conversation_memory_lifecycle"
    assert route_records["/api/v1/conversation/{conversation_id}"]["coverage_state"] == "witnessed"
    assert route_records["/api/v1/conversation/{conversation_id}"]["surface_id"] == "conversation_memory_lifecycle"
    assert route_records["/api/v1/conversations"]["coverage_state"] == "witnessed"
    assert route_records["/api/v1/conversations"]["surface_id"] == "conversation_memory_lifecycle"
    assert closure_actions["classify_conversation_memory_routes"]["status"] == "closed"


def test_coordination_checkpoint_lifecycle_surface_is_witnessed() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    route_records = {
        record["route"]: record
        for record in matrix["route_coverage"]["routes"]
    }
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    coordination_surface = surfaces["coordination_checkpoint_lifecycle"]
    witnesses = set(coordination_surface["runtime_witnesses"])

    assert coordination_surface["coverage_state"] == "proven"
    assert coordination_surface["request_proof"] == "request_proof"
    assert coordination_surface["action_proof"] == "action_proof"
    assert coordination_surface["audit"] == "audit_chain"
    assert "/api/v1/coordination/checkpoint" in coordination_surface["representative_paths"]
    assert "/api/v1/coordination/restore" in coordination_surface["representative_paths"]
    assert "mcoi/mcoi_runtime/app/routers/ops/coordination.py" in coordination_surface["evidence_files"]
    assert "mcoi/mcoi_runtime/core/coordination.py" in coordination_surface["evidence_files"]
    assert "mcoi/mcoi_runtime/persistence/coordination_store.py" in coordination_surface["evidence_files"]
    assert "mcoi/tests/test_coordination_http_endpoints.py" in coordination_surface["evidence_files"]
    assert "mcoi/tests/test_coordination_engine_persistence.py" in coordination_surface["evidence_files"]
    assert "coordination_checkpoint_save_governed" in witnesses
    assert "coordination_restore_resumes_checkpoint" in witnesses
    assert "coordination_restore_missing_is_bounded" in witnesses
    assert "coordination_policy_drift_requires_review" in witnesses
    assert "coordination_store_path_traversal_rejected" in witnesses
    assert route_records["/api/v1/coordination/checkpoint"]["coverage_state"] == "proven"
    assert route_records["/api/v1/coordination/checkpoint"]["surface_id"] == "coordination_checkpoint_lifecycle"
    assert route_records["/api/v1/coordination/restore"]["coverage_state"] == "proven"
    assert route_records["/api/v1/coordination/restore"]["surface_id"] == "coordination_checkpoint_lifecycle"
    assert closure_actions["classify_coordination_checkpoint_routes"]["status"] == "closed"


def test_ops_proof_surface_is_witnessed() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    route_records = {
        record["route"]: record
        for record in matrix["route_coverage"]["routes"]
    }
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    ops_surface = surfaces["ops_proof_surface"]
    witnesses = set(ops_surface["runtime_witnesses"])

    assert ops_surface["coverage_state"] == "witnessed"
    assert ops_surface["request_proof"] == "request_proof"
    assert ops_surface["action_proof"] == "action_proof"
    assert ops_surface["audit"] == "audit_chain"
    assert "/api/v1/ops/benchmarks" in ops_surface["representative_paths"]
    assert "/api/v1/ops/imports" in ops_surface["representative_paths"]
    assert "/api/v1/ops/proof-bridge" in ops_surface["representative_paths"]
    assert "mcoi/mcoi_runtime/app/routers/ops/diagnostics.py" in ops_surface["evidence_files"]
    assert "mcoi/mcoi_runtime/core/governance_bench.py" in ops_surface["evidence_files"]
    assert "mcoi/mcoi_runtime/core/import_analyzer.py" in ops_surface["evidence_files"]
    assert "mcoi/mcoi_runtime/core/proof_bridge.py" in ops_surface["evidence_files"]
    assert "mcoi/tests/test_governance_endpoints.py" in ops_surface["evidence_files"]
    assert "ops_benchmarks_return_governed_summary" in witnesses
    assert "ops_import_analysis_returns_dependency_summary" in witnesses
    assert "ops_proof_bridge_status_governed" in witnesses
    assert route_records["/api/v1/ops/benchmarks"]["coverage_state"] == "witnessed"
    assert route_records["/api/v1/ops/benchmarks"]["surface_id"] == "ops_proof_surface"
    assert route_records["/api/v1/ops/proof-bridge"]["coverage_state"] == "witnessed"
    assert route_records["/api/v1/ops/proof-bridge"]["surface_id"] == "ops_proof_surface"
    assert closure_actions["classify_ops_diagnostics_routes"]["status"] == "closed"


def test_gateway_runtime_witness_covers_orchestration_receipts() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    runtime_surface = surfaces["gateway_runtime_witness"]

    assert runtime_surface["coverage_state"] == "witnessed"
    assert "scripts/orchestrate_deployment_witness.py" in runtime_surface["evidence_files"]
    assert "scripts/emit_gateway_dns_target_binding_receipt.py" in runtime_surface["evidence_files"]
    assert "scripts/validate_gateway_dns_target_binding_receipt.py" in runtime_surface["evidence_files"]
    assert "scripts/emit_deployment_upstream_blocker_receipt.py" in runtime_surface["evidence_files"]
    assert "scripts/validate_deployment_upstream_blocker_receipt.py" in runtime_surface["evidence_files"]
    assert "scripts/collect_gateway_dns_resolution_receipt.py" in runtime_surface["evidence_files"]
    assert "scripts/validate_gateway_dns_resolution_receipt.py" in runtime_surface["evidence_files"]
    assert ".github/workflows/gateway-publication.yml" in runtime_surface["evidence_files"]
    assert ".github/workflows/deployment-witness.yml" in runtime_surface["evidence_files"]
    assert "schemas/deployment_orchestration_receipt.schema.json" in runtime_surface["evidence_files"]
    assert "schemas/deployment_publication_closure_validation.schema.json" in runtime_surface["evidence_files"]
    assert "schemas/public_production_health_declaration.schema.json" in runtime_surface["evidence_files"]
    assert "schemas/deployment_orchestration_receipt_validation.schema.json" in runtime_surface["evidence_files"]
    assert "schemas/gateway_dns_target_binding_receipt.schema.json" in runtime_surface["evidence_files"]
    assert "schemas/deployment_upstream_blocker_receipt.schema.json" in runtime_surface["evidence_files"]
    assert "schemas/gateway_dns_resolution_receipt.schema.json" in runtime_surface["evidence_files"]
    assert "schemas/gateway_publication_readiness.schema.json" in runtime_surface["evidence_files"]
    assert "schemas/gateway_publication_receipt_validation.schema.json" in runtime_surface["evidence_files"]
    assert "schemas/latest_anchor_read_model.schema.json" in runtime_surface["evidence_files"]
    assert "schemas/runtime_witness.schema.json" in runtime_surface["evidence_files"]
    assert "schemas/mullu_governance_protocol.manifest.json" in runtime_surface["evidence_files"]
    assert "tests/test_orchestrate_deployment_witness.py" in runtime_surface["evidence_files"]
    assert "tests/test_emit_gateway_dns_target_binding_receipt.py" in runtime_surface["evidence_files"]
    assert "tests/test_validate_gateway_dns_target_binding_receipt.py" in runtime_surface["evidence_files"]
    assert "tests/test_emit_deployment_upstream_blocker_receipt.py" in runtime_surface["evidence_files"]
    assert "tests/test_validate_deployment_upstream_blocker_receipt.py" in runtime_surface["evidence_files"]
    assert "tests/test_collect_gateway_dns_resolution_receipt.py" in runtime_surface["evidence_files"]
    assert "tests/test_report_gateway_publication_readiness.py" in runtime_surface["evidence_files"]
    assert "tests/test_validate_gateway_dns_resolution_receipt.py" in runtime_surface["evidence_files"]
    assert "tests/test_validate_gateway_publication_receipt.py" in runtime_surface["evidence_files"]
    assert "tests/test_validate_deployment_publication_closure.py" in runtime_surface["evidence_files"]
    assert "tests/test_validate_protocol_manifest.py" in runtime_surface["evidence_files"]
    assert "orchestrate_deployment_witness_renders_and_provisions" in runtime_surface["runtime_witnesses"]
    assert "latest_anchor_read_model" in runtime_surface["runtime_witnesses"]
    assert "runtime_witness_alias" in runtime_surface["runtime_witnesses"]
    assert "closure_validation_report_matches_public_schema_for_not_published" in runtime_surface["runtime_witnesses"]
    assert "orchestration_validation_report_matches_public_schema" in runtime_surface["runtime_witnesses"]
    assert "gateway_dns_target_binding_receipt_matches_public_schema" in runtime_surface["runtime_witnesses"]
    assert "gateway_dns_target_binding_validation_report_writes_bounded_result" in runtime_surface["runtime_witnesses"]
    assert "deployment_upstream_blocker_receipt_matches_public_schema" in runtime_surface["runtime_witnesses"]
    assert "deployment_upstream_blocker_validation_accepts_ready_receipt" in runtime_surface["runtime_witnesses"]
    assert "gateway_dns_resolution_receipt_matches_public_schema" in runtime_surface["runtime_witnesses"]
    assert "gateway_dns_receipt_validation_report_writes_bounded_result" in runtime_surface["runtime_witnesses"]
    assert "readiness_report_matches_public_schema" in runtime_surface["runtime_witnesses"]
    assert "receipt_validation_report_matches_public_schema" in runtime_surface["runtime_witnesses"]
    assert "protocol_manifest_indexes_public_production_health_declaration" in runtime_surface["runtime_witnesses"]
    assert "protocol_manifest_indexes_gateway_dns_target_binding_receipt" in runtime_surface["runtime_witnesses"]
    assert "protocol_manifest_indexes_deployment_upstream_blocker_receipt" in runtime_surface["runtime_witnesses"]
    assert "protocol_manifest_indexes_gateway_dns_resolution_receipt" in runtime_surface["runtime_witnesses"]
    assert "apply_deployment_publication_status_updates_verified_claim" in runtime_surface["runtime_witnesses"]
    assert "apply_deployment_publication_status_writes_receipt" in runtime_surface["runtime_witnesses"]
    assert closure_actions["publish_deployment_orchestration_receipt_contract"]["status"] == "closed"


def test_gateway_runtime_witness_covers_publication_responsibility_debt() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    runtime_surface = surfaces["gateway_runtime_witness"]
    witnesses = set(runtime_surface["runtime_witnesses"])

    assert "schemas/deployment_witness.schema.json" in runtime_surface["evidence_files"]
    assert "scripts/validate_deployment_publication_closure.py" in runtime_surface["evidence_files"]
    assert "scripts/apply_deployment_publication_status.py" in runtime_surface["evidence_files"]
    assert "tests/test_validate_deployment_publication_closure.py" in runtime_surface["evidence_files"]
    assert "tests/test_apply_deployment_publication_status.py" in runtime_surface["evidence_files"]
    assert "collect_deployment_witness_rejects_responsibility_debt" in witnesses
    assert "collect_deployment_witness_rejects_runtime_responsibility_debt" in witnesses
    assert "preflight_deployment_witness_rejects_responsibility_debt" in witnesses
    assert "preflight_deployment_witness_rejects_runtime_witness_responsibility_debt" in witnesses
    assert "published_status_rejects_authority_responsibility_debt" in witnesses
    assert "published_status_rejects_runtime_responsibility_debt" in witnesses
    assert "apply_deployment_publication_status_blocks_missing_approval" in witnesses
    assert "apply_deployment_publication_status_blocks_unpublished_witness" in witnesses
    assert "published_status_report_accepts_declaration_receipt" in witnesses
    assert "published_status_report_rejects_dry_run_declaration_receipt" in witnesses


def test_production_evidence_plane_is_witnessed_and_schema_backed() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    evidence_surface = surfaces["production_evidence_plane"]
    witnesses = set(evidence_surface["runtime_witnesses"])

    assert evidence_surface["coverage_state"] == "witnessed"
    assert evidence_surface["request_proof"] == "read_model"
    assert evidence_surface["action_proof"] == "read_model"
    assert evidence_surface["audit"] == "audit_chain"
    assert "/health" in evidence_surface["representative_paths"]
    assert "/deployment/witness" in evidence_surface["representative_paths"]
    assert "/capabilities/evidence" in evidence_surface["representative_paths"]
    assert "/audit/verify" in evidence_surface["representative_paths"]
    assert "/proof/verify" in evidence_surface["representative_paths"]
    assert "schemas/gateway_health.schema.json" in evidence_surface["evidence_files"]
    assert "schemas/production_evidence_witness.schema.json" in evidence_surface["evidence_files"]
    assert "schemas/capability_evidence_endpoint.schema.json" in evidence_surface["evidence_files"]
    assert "schemas/audit_verification_endpoint.schema.json" in evidence_surface["evidence_files"]
    assert "schemas/proof_verification_endpoint.schema.json" in evidence_surface["evidence_files"]
    assert "tests/test_gateway/test_production_evidence.py" in evidence_surface["evidence_files"]
    assert "tests/test_collect_deployment_witness.py" in evidence_surface["evidence_files"]
    assert "gateway_health_schema_valid" in witnesses
    assert "signed_production_evidence_witness" in witnesses
    assert "capability_evidence_schema_valid" in witnesses
    assert "audit_verification_schema_valid" in witnesses
    assert "proof_verification_schema_valid" in witnesses
    assert "deployment_collection_requires_production_evidence" in witnesses
    assert "live_physical_safety_evidence_derived_from_registry" in witnesses
    assert "live_physical_capability_requires_safety_evidence" in witnesses
    assert "sandbox_physical_capability_remains_non_production" in witnesses
    assert "missing_production_evidence_fails_closed" in witnesses
    assert closure_actions["publish_production_evidence_plane"]["status"] == "closed"
    assert "gateway_runtime_witness" in closure_actions["publish_production_evidence_plane"]["surfaces"]


def test_governed_session_request_envelope_is_covered() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    session_surface = surfaces["governed_session"]

    assert session_surface["request_proof"] == "request_proof"
    assert session_surface["action_proof"] == "action_proof"
    assert "GovernedSession.llm" in session_surface["representative_paths"]
    assert "mcoi/tests/test_governed_session.py" in session_surface["evidence_files"]


def test_gaps_have_closure_actions() -> None:
    matrix = _load_fixture()
    closure_surfaces = {
        surface_id
        for action in matrix["closure_actions"]
        for surface_id in action["surfaces"]
        if action["status"] == "open"
    }
    gap_surfaces = {
        surface["surface_id"]
        for surface in matrix["surfaces"]
        if "gap" in {surface["request_proof"], surface["action_proof"], surface["audit"]}
    }

    assert gap_surfaces <= closure_surfaces
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}

    assert closure_actions["bind_tool_arguments_to_capability_policy_receipts"]["status"] == "closed"
    assert closure_actions["normalize_gateway_request_receipt_envelopes"]["status"] == "closed"
    assert closure_actions["bound_authority_read_models_to_paginated_windows"]["status"] == "closed"
    assert surfaces["gateway_capability_fabric"]["request_proof"] == "request_proof"
    assert surfaces["tool_invocation"]["action_proof"] == "action_proof"
    assert "authority_obligation_mesh" in closure_actions["bound_authority_read_models_to_paginated_windows"]["surfaces"]
    assert all(action["surfaces"] for action in matrix["closure_actions"])


def test_closure_actions_reference_declared_surfaces() -> None:
    matrix = _load_fixture()
    declared_surfaces = {surface["surface_id"] for surface in matrix["surfaces"]}

    assert all(
        surface_id in declared_surfaces
        for action in matrix["closure_actions"]
        for surface_id in action["surfaces"]
    )
    assert {action["status"] for action in matrix["closure_actions"]} <= {"open", "closed"}


def test_evidence_files_exist() -> None:
    matrix = _load_fixture()
    evidence_files = {evidence_file for surface in matrix["surfaces"] for evidence_file in surface["evidence_files"]}

    assert "mcoi/mcoi_runtime/app/streaming.py" in evidence_files
    assert "schemas/streaming_budget_enforcement.schema.json" in evidence_files
    assert "schemas/lineage_query.schema.json" in evidence_files
    assert "mcoi/mcoi_runtime/app/routers/lineage.py" in evidence_files
    assert "docs/42_lineage_query_api.md" in evidence_files
    assert "gateway/server.py" in evidence_files
    assert all((REPO_ROOT / evidence_file).exists() for evidence_file in evidence_files)


def test_lineage_query_api_is_proven_read_model() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    lineage_surface = surfaces["lineage_query_api"]
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}

    assert lineage_surface["coverage_state"] == "proven"
    assert lineage_surface["request_proof"] == "read_model"
    assert lineage_surface["action_proof"] == "read_model"
    assert "/api/v1/lineage/command/{command_id}" in lineage_surface["representative_paths"]
    assert "/api/v1/lineage/artifact/{artifact_id}" in lineage_surface["representative_paths"]
    assert "mcoi/mcoi_runtime/core/lineage_query.py" in lineage_surface["evidence_files"]
    assert "mcoi/tests/test_server_lineage.py" in lineage_surface["evidence_files"]
    assert "schemas/lineage_query.schema.json" in lineage_surface["evidence_files"]
    assert "docs/42_lineage_query_api.md" in lineage_surface["evidence_files"]
    assert "lineage_route_enriches_policy_registry_metadata" in lineage_surface["runtime_witnesses"]
    assert closure_actions["implement_lineage_query_routes_and_schema"]["status"] == "closed"


def test_capability_plan_evidence_bundle_surface_is_witnessed() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    plan_surface = surfaces["capability_plan_evidence_bundle"]
    conformance_surface = surfaces["runtime_conformance_attestation"]
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    witnesses = set(plan_surface["runtime_witnesses"])

    assert plan_surface["coverage_state"] == "witnessed"
    assert plan_surface["request_proof"] == "request_proof"
    assert plan_surface["action_proof"] == "action_proof"
    assert "/capability-plans/{plan_id}/closure" in plan_surface["representative_paths"]
    assert "gateway/plan_ledger.py" in plan_surface["evidence_files"]
    assert "tests/test_gateway/test_plan.py" in plan_surface["evidence_files"]
    assert "plan_terminal_certificate" in witnesses
    assert "plan_evidence_bundle" in witnesses
    assert "plan_witnesses" in witnesses
    assert "plan_recovery_attempts" in witnesses
    assert "runtime_conformance_witnesses_capability_plan_bundle" in conformance_surface["runtime_witnesses"]
    assert "physical_worker_canary_blocks_missing_receipt_and_allows_sandbox_replay" in conformance_surface["runtime_witnesses"]
    assert "physical_worker_canary_evidence_and_hash_are_stable" in conformance_surface["runtime_witnesses"]
    assert "gateway/physical_worker_canary.py" in conformance_surface["evidence_files"]
    assert "scripts/produce_physical_worker_canary.py" in conformance_surface["evidence_files"]
    assert "tests/test_gateway/test_physical_worker_canary.py" in conformance_surface["evidence_files"]
    assert "runtime_conformance_certificate_matches_schema" in conformance_surface["runtime_witnesses"]
    assert "collect_runtime_conformance_rejects_schema_invalid_certificate" in conformance_surface["runtime_witnesses"]
    assert "runtime_conformance_surfaces_unclassified_proof_routes" in conformance_surface["runtime_witnesses"]
    assert ".github/workflows/deployment-witness.yml" in conformance_surface["evidence_files"]
    assert "schemas/runtime_conformance_collection.schema.json" in conformance_surface["evidence_files"]
    assert "deployment_witness_workflow_carries_conformance_secret_handoff" in conformance_surface["runtime_witnesses"]
    assert "deployment_witness_workflow_requires_conformance_secret_handoff" in conformance_surface["runtime_witnesses"]
    assert "write_runtime_conformance_persists_json" in conformance_surface["runtime_witnesses"]
    assert "write_runtime_conformance_rejects_collection_schema_drift" in conformance_surface["runtime_witnesses"]
    assert closure_actions["publish_capability_plan_evidence_bundles"]["status"] == "closed"
    assert "runtime_conformance_attestation" in closure_actions["publish_capability_plan_evidence_bundles"]["surfaces"]


def test_proof_route_gap_triage_surface_preserves_route_gaps() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    triage_surface = surfaces["proof_route_gap_triage"]
    witnesses = set(triage_surface["runtime_witnesses"])

    assert triage_surface["coverage_state"] == "witnessed"
    assert triage_surface["request_proof"] == "read_model"
    assert triage_surface["action_proof"] == "read_model"
    assert "build_gap_triage_report" in triage_surface["representative_paths"]
    assert "scripts/proof_route_gap_triage.py" in triage_surface["evidence_files"]
    assert "tests/test_proof_route_gap_triage.py" in triage_surface["evidence_files"]
    assert "docs/70_proof_route_gap_triage.md" in triage_surface["evidence_files"]
    assert "unclassified_routes_grouped_by_family" in witnesses
    assert "route_gap_triage_binds_source_files_and_methods" in witnesses
    assert "closure_candidates_ranked_deterministically" in witnesses
    assert closure_actions["publish_proof_route_gap_triage_report"]["status"] == "closed"
    assert "runtime_conformance_attestation" in closure_actions["publish_proof_route_gap_triage_report"]["surfaces"]


def test_god_mode_lifecycle_surface_is_proven() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    god_surface = surfaces["god_mode_lifecycle"]
    witnesses = set(god_surface["runtime_witnesses"])
    route_records = {
        record["route"]: record
        for record in matrix["route_coverage"]["routes"]
    }

    assert god_surface["coverage_state"] == "proven"
    assert god_surface["request_proof"] == "action_proof"
    assert god_surface["action_proof"] == "action_proof"
    assert "/api/v1/god-mode/capabilities" in god_surface["representative_paths"]
    assert "/api/v1/god-mode/health" in god_surface["representative_paths"]
    assert "/api/v1/god-mode/modules" in god_surface["representative_paths"]
    assert "mcoi/tests/test_god_mode_router.py" in god_surface["evidence_files"]
    assert "mcoi/tests/test_god_mode_dual_control.py" in god_surface["evidence_files"]
    assert "mcoi/tests/test_god_mode_invariants.py" in god_surface["evidence_files"]
    assert "capability_keys_are_unique" in witnesses
    assert "every_capability_declares_at_least_one_bypass" in witnesses
    assert "catastrophic_caps_require_dual_control" in witnesses
    assert route_records["/api/v1/god-mode/capabilities"]["coverage_state"] == "proven"
    assert route_records["/api/v1/god-mode/capabilities"]["surface_id"] == "god_mode_lifecycle"
    assert route_records["/api/v1/god-mode/health"]["coverage_state"] == "proven"
    assert route_records["/api/v1/god-mode/health"]["surface_id"] == "god_mode_lifecycle"


def test_runtime_reflex_engine_surface_is_operator_gated_and_non_mutating() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    reflex_surface = surfaces["runtime_reflex_engine"]
    witnesses = set(reflex_surface["runtime_witnesses"])

    assert reflex_surface["coverage_state"] == "witnessed"
    assert reflex_surface["request_proof"] == "read_model"
    assert reflex_surface["action_proof"] == "request_proof"
    assert "/runtime/self/propose-upgrade" in reflex_surface["representative_paths"]
    assert "/runtime/self/promote" in reflex_surface["representative_paths"]
    assert "/runtime/self/deployment-witnesses" in reflex_surface["representative_paths"]
    assert "mcoi/mcoi_runtime/contracts/reflex.py" in reflex_surface["evidence_files"]
    assert "mcoi/mcoi_runtime/core/reflex.py" in reflex_surface["evidence_files"]
    assert "schemas/reflex_deployment_witness_envelope.schema.json" in reflex_surface["evidence_files"]
    assert "schemas/reflex_deployment_witness_validator_receipt.schema.json" in reflex_surface["evidence_files"]
    assert "scripts/emit_reflex_deployment_witness_validator_receipt.py" in reflex_surface["evidence_files"]
    assert "scripts/validate_reflex_deployment_witness.py" in reflex_surface["evidence_files"]
    assert "tests/test_gateway/test_reflex_endpoints.py" in reflex_surface["evidence_files"]
    assert "tests/test_emit_reflex_deployment_witness_validator_receipt.py" in reflex_surface["evidence_files"]
    assert "tests/test_validate_reflex_deployment_witness.py" in reflex_surface["evidence_files"]
    assert "operator_only_access" in witnesses
    assert "mutation_applied_false" in witnesses
    assert "certification_handoff_required" in witnesses
    assert "signed_reflex_witness" in witnesses
    assert "reflex_deployment_witness_schema" in witnesses
    assert "reflex_validator_receipt_schema" in witnesses
    assert "offline_reflex_witness_replay" in witnesses
    assert "reflex_validator_receipt_artifact" in witnesses
    assert closure_actions["publish_runtime_reflex_engine_read_models"]["status"] == "closed"


def test_governed_operational_intelligence_surface_is_witnessed() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    operational_surface = surfaces["governed_operational_intelligence"]
    witnesses = set(operational_surface["runtime_witnesses"])

    assert operational_surface["coverage_state"] == "witnessed"
    assert operational_surface["request_proof"] == "request_proof"
    assert operational_surface["action_proof"] == "action_proof"
    assert "WorldStateStore.add_entity" in operational_surface["representative_paths"]
    assert "GoalCompiler.compile" in operational_surface["representative_paths"]
    assert "CausalSimulator.simulate" in operational_surface["representative_paths"]
    assert "/api/v1/knowledge/entities" in operational_surface["representative_paths"]
    assert "/api/v1/knowledge/links" in operational_surface["representative_paths"]
    assert "/api/v1/knowledge/contradictions/unresolved" in operational_surface["representative_paths"]
    assert "/api/v1/simulate" in operational_surface["representative_paths"]
    assert "/api/v1/simulate/history" in operational_surface["representative_paths"]
    assert "gateway/world_state.py" in operational_surface["evidence_files"]
    assert "gateway/goal_compiler.py" in operational_surface["evidence_files"]
    assert "gateway/causal_simulator.py" in operational_surface["evidence_files"]
    assert "mcoi/mcoi_runtime/app/routers/knowledge.py" in operational_surface["evidence_files"]
    assert "mcoi/mcoi_runtime/app/routers/simulation.py" in operational_surface["evidence_files"]
    assert "mcoi/mcoi_runtime/core/knowledge_graph.py" in operational_surface["evidence_files"]
    assert "mcoi/mcoi_runtime/governance/policy/sandbox.py" in operational_surface["evidence_files"]
    assert "schemas/world_state.schema.json" in operational_surface["evidence_files"]
    assert "schemas/goal.schema.json" in operational_surface["evidence_files"]
    assert "schemas/simulation_receipt.schema.json" in operational_surface["evidence_files"]
    assert "mcoi/tests/test_knowledge_graph.py" in operational_surface["evidence_files"]
    assert "mcoi/tests/test_policy_sandbox.py" in operational_surface["evidence_files"]
    assert "tests/test_gateway/test_world_state.py" in operational_surface["evidence_files"]
    assert "tests/test_gateway/test_goal_compiler.py" in operational_surface["evidence_files"]
    assert "tests/test_gateway/test_causal_simulator.py" in operational_surface["evidence_files"]
    assert "world_assertions_require_source_evidence" in witnesses
    assert "knowledge_entity_routes_governed" in witnesses
    assert "knowledge_link_routes_governed" in witnesses
    assert "knowledge_contradiction_routes_governed" in witnesses
    assert "knowledge_summary_route_bounded" in witnesses
    assert "policy_simulation_routes_governed" in witnesses
    assert "policy_simulation_history_summary_bounded" in witnesses
    assert "goal_plan_certificate_hash_bound" in witnesses
    assert "simulation_receipt_schema_valid" in witnesses
    assert "open_world_contradictions_block_execution" in witnesses
    assert "high_risk_controls_projected_before_execution" in witnesses
    assert closure_actions["publish_governed_operational_intelligence_witnesses"]["status"] == "closed"
    assert closure_actions["classify_world_state_knowledge_routes"]["status"] == "closed"
    assert closure_actions["classify_policy_simulation_routes"]["status"] == "closed"


def test_capability_forge_surface_is_candidate_only() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    forge_surface = surfaces["capability_forge"]
    witnesses = set(forge_surface["runtime_witnesses"])

    assert forge_surface["coverage_state"] == "witnessed"
    assert forge_surface["request_proof"] == "request_proof"
    assert forge_surface["action_proof"] == "action_proof"
    assert "CapabilityForge.create_candidate" in forge_surface["representative_paths"]
    assert "CapabilityForge.validate" in forge_surface["representative_paths"]
    assert "CapabilityForge.build_certification_handoff" in forge_surface["representative_paths"]
    assert "install_certification_handoff_evidence" in forge_surface["representative_paths"]
    assert "install_certification_handoff_evidence_batch" in forge_surface["representative_paths"]
    assert "gateway/capability_forge.py" in forge_surface["evidence_files"]
    assert "schemas/capability_candidate.schema.json" in forge_surface["evidence_files"]
    assert "tests/test_gateway/test_capability_forge.py" in forge_surface["evidence_files"]
    assert "candidate_promotion_blocked" in witnesses
    assert "candidate_schema_valid" in witnesses
    assert "candidate_certification_handoff_emits_maturity_bundle" in witnesses
    assert "certification_handoff_installs_evidence_without_maturity_claim" in witnesses
    assert "certification_handoff_batch_preserves_capsule_admission_gate" in witnesses
    assert "physical_candidate_declares_live_safety_evidence_requirements" in witnesses
    assert "physical_handoff_installs_live_safety_evidence" in witnesses
    assert "high_risk_approval_policy_required" in witnesses
    assert "effect_bearing_candidate_requires_sandbox" in witnesses
    assert "effect_bearing_candidate_requires_recovery_path" in witnesses
    assert closure_actions["publish_capability_forge_candidate_contract"]["status"] == "closed"


def test_capability_maturity_surface_blocks_readiness_overclaims() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    maturity_surface = surfaces["capability_maturity_assessment"]
    witnesses = set(maturity_surface["runtime_witnesses"])

    assert maturity_surface["coverage_state"] == "witnessed"
    assert maturity_surface["request_proof"] == "request_proof"
    assert maturity_surface["action_proof"] == "action_proof"
    assert "CapabilityMaturityEvidenceSynthesizer.materialize_extension" in maturity_surface["representative_paths"]
    assert "CapabilityMaturityAssessor.assess" in maturity_surface["representative_paths"]
    assert "CapabilityRegistryMaturityProjector.decorate_read_model" in maturity_surface["representative_paths"]
    assert "MaturityProjectingCapabilityAdmissionGate.read_model" in maturity_surface["representative_paths"]
    assert "capabilities/connector/capability_pack.json" in maturity_surface["evidence_files"]
    assert "capabilities/financial/capability_pack.json" in maturity_surface["evidence_files"]
    assert "docs/39_governed_capability_fabric.md" in maturity_surface["evidence_files"]
    assert "gateway/capability_fabric.py" in maturity_surface["evidence_files"]
    assert "gateway/capability_maturity.py" in maturity_surface["evidence_files"]
    assert "gateway/operator_capability_console.py" in maturity_surface["evidence_files"]
    assert "schemas/capability_maturity.schema.json" in maturity_surface["evidence_files"]
    assert "tests/test_gateway/test_capability_fabric.py" in maturity_surface["evidence_files"]
    assert "tests/test_gateway/test_capability_maturity.py" in maturity_surface["evidence_files"]
    assert "tests/test_gateway/test_operator_capability_console.py" in maturity_surface["evidence_files"]
    assert "certification_evidence_synthesizes_maturity_extension" in witnesses
    assert "maturity_derived_from_evidence" in witnesses
    assert "registry_read_model_exposes_maturity" in witnesses
    assert "default_pack_C6_examples_projected" in witnesses
    assert "effect_bearing_production_requires_live_write" in witnesses
    assert "production_requires_worker_deployment_recovery" in witnesses
    assert "autonomy_requires_C7_controls" in witnesses
    assert "capability_maturity_schema_valid" in witnesses
    assert closure_actions["publish_capability_maturity_assessment_contract"]["status"] == "closed"


def test_capability_manifest_registry_surface_admits_governed_manifests() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    manifest_surface = surfaces["capability_manifest_registry"]
    witnesses = set(manifest_surface["runtime_witnesses"])

    assert manifest_surface["coverage_state"] == "witnessed"
    assert manifest_surface["request_proof"] == "request_proof"
    assert manifest_surface["action_proof"] == "action_proof"
    assert "CapabilityManifestRegistry.admit_path" in manifest_surface["representative_paths"]
    assert "CapabilityManifestAdmission" in manifest_surface["representative_paths"]
    assert "build_software_dev_capability_manifest_registry" in manifest_surface["representative_paths"]
    assert "gateway/capability_fabric.py" in manifest_surface["evidence_files"]
    assert "mcoi/mcoi_runtime/contracts/capability_manifest.py" in manifest_surface["evidence_files"]
    assert "mcoi/mcoi_runtime/core/capability_manifest_registry.py" in manifest_surface["evidence_files"]
    assert "schemas/software_dev/capability_manifest.schema.json" in manifest_surface["evidence_files"]
    assert "tests/test_gateway/test_capability_fabric.py" in manifest_surface["evidence_files"]
    assert "tests/test_software_dev_capability_manifest_registry.py" in manifest_surface["evidence_files"]
    assert "capability_manifest_schema_valid" in witnesses
    assert "software_dev_manifests_admit_locally" in witnesses
    assert "effect_manifest_requires_sandbox_rollback" in witnesses
    assert "hot_reload_metadata_enforced" in witnesses
    assert "production_hot_reload_denied_for_effect_manifest" in witnesses
    assert "fabric_projects_local_manifest_registry" in witnesses
    assert "fabric_rejects_production_hot_reload_manifest_registry" in witnesses
    assert closure_actions["publish_capability_manifest_registry_contract"]["status"] == "closed"


def test_networked_worker_mesh_surface_requires_non_terminal_receipts() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    worker_surface = surfaces["networked_worker_mesh"]
    witnesses = set(worker_surface["runtime_witnesses"])

    assert worker_surface["coverage_state"] == "witnessed"
    assert worker_surface["request_proof"] == "request_proof"
    assert worker_surface["action_proof"] == "action_proof"
    assert "NetworkedWorkerMesh.register_worker" in worker_surface["representative_paths"]
    assert "NetworkedWorkerMesh.dispatch" in worker_surface["representative_paths"]
    assert "NetworkedWorkerMesh.read_model" in worker_surface["representative_paths"]
    assert "SandboxedCodeWorker.execute_command" in worker_surface["representative_paths"]
    assert "CodeWorkerLease" in worker_surface["representative_paths"]
    assert "CodeWorkerReceipt" in worker_surface["representative_paths"]
    assert "gateway/physical_action_boundary.py" in worker_surface["evidence_files"]
    assert "gateway/physical_worker_canary.py" in worker_surface["evidence_files"]
    assert "gateway/worker_mesh.py" in worker_surface["evidence_files"]
    assert "mcoi/mcoi_runtime/contracts/code_worker.py" in worker_surface["evidence_files"]
    assert "mcoi/mcoi_runtime/workers/code_worker.py" in worker_surface["evidence_files"]
    assert "scripts/produce_physical_worker_canary.py" in worker_surface["evidence_files"]
    assert "schemas/physical_action_receipt.schema.json" in worker_surface["evidence_files"]
    assert "schemas/worker_mesh.schema.json" in worker_surface["evidence_files"]
    assert "tests/test_code_worker.py" in worker_surface["evidence_files"]
    assert "tests/test_gateway/test_physical_action_boundary.py" in worker_surface["evidence_files"]
    assert "tests/test_gateway/test_physical_worker_canary.py" in worker_surface["evidence_files"]
    assert "tests/test_gateway/test_worker_mesh.py" in worker_surface["evidence_files"]
    assert "tests/test_produce_physical_worker_canary.py" in worker_surface["evidence_files"]
    assert "active_lease_required" in witnesses
    assert "tenant_capability_operation_budget_checked" in witnesses
    assert "forbidden_operations_override_allowed" in witnesses
    assert "code_worker_exact_lease_command_required" in witnesses
    assert "code_worker_blocks_network_shell_and_risky_git" in witnesses
    assert "code_worker_receipt_binds_sandbox_evidence" in witnesses
    assert "physical_action_receipt_required_for_physical_workers" in witnesses
    assert "physical_worker_canary_blocks_without_receipt" in witnesses
    assert "physical_worker_canary_passed" in witnesses
    assert "physical_worker_canary_uses_sandbox_handler" in witnesses
    assert "worker_evidence_refs_required" in witnesses
    assert "worker_receipt_not_terminal_closure" in witnesses
    assert "worker_mesh_schema_valid" in witnesses
    assert closure_actions["publish_networked_worker_mesh_contract"]["status"] == "closed"


def test_read_only_first_worker_path_surface_is_foundation_bound() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    worker_surface = surfaces["read_only_first_worker_path"]
    witnesses = set(worker_surface["runtime_witnesses"])

    assert worker_surface["coverage_state"] == "proven"
    assert worker_surface["request_proof"] == "request_proof"
    assert worker_surface["action_proof"] == "action_proof"
    assert "repository.inspect_read_only" in worker_surface["representative_paths"]
    assert "build_worker_failure_receipt" in worker_surface["representative_paths"]
    assert "gateway/read_only_repository_worker.py" in worker_surface["evidence_files"]
    assert "gateway/worker_failure_receipt.py" in worker_surface["evidence_files"]
    assert "schemas/read_only_first_worker_path.schema.json" in worker_surface["evidence_files"]
    assert "schemas/worker_failure_receipt.schema.json" in worker_surface["evidence_files"]
    assert "scripts/validate_read_only_first_worker_path.py" in worker_surface["evidence_files"]
    assert "read_only_first_worker_path_example_passes" in witnesses
    assert "read_only_repository_worker_rejects_mutation_and_network_inputs" in witnesses
    assert "worker_failure_receipt_validates_partial_completion" in witnesses
    assert "worker_failure_receipt_rejects_success_source" in witnesses
    assert closure_actions["publish_read_only_first_worker_path_contract"]["status"] == "closed"


def test_read_only_document_worker_path_surface_is_foundation_bound() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    document_surface = surfaces["read_only_document_worker_path"]
    witnesses = set(document_surface["runtime_witnesses"])

    assert document_surface["coverage_state"] == "proven"
    assert document_surface["request_proof"] == "request_proof"
    assert document_surface["action_proof"] == "action_proof"
    assert "document.inspect_read_only" in document_surface["representative_paths"]
    assert "build_read_only_document_inspection_lease" in document_surface["representative_paths"]
    assert "gateway/read_only_document_worker.py" in document_surface["evidence_files"]
    assert "schemas/read_only_document_worker_path.schema.json" in document_surface["evidence_files"]
    assert "scripts/validate_read_only_document_worker_path.py" in document_surface["evidence_files"]
    assert "read_only_document_worker_path_example_passes" in witnesses
    assert "read_only_document_worker_path_rejects_rich_document_parsing" in witnesses
    assert "read_only_document_worker_rejects_unsupported_format" in witnesses
    assert "read_only_document_worker_reports_text_decode_failure" in witnesses
    assert "read_only_document_worker_rejects_mutation_and_network_inputs" in witnesses
    assert "read_only_document_worker_rejects_secret_like_input_values" in witnesses
    assert closure_actions["publish_read_only_document_worker_path_contract"]["status"] == "closed"


def test_read_only_search_worker_path_surface_is_foundation_bound() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    search_surface = surfaces["read_only_search_worker_path"]
    witnesses = set(search_surface["runtime_witnesses"])

    assert search_surface["coverage_state"] == "proven"
    assert search_surface["request_proof"] == "request_proof"
    assert search_surface["action_proof"] == "action_proof"
    assert "enterprise.knowledge_search" in search_surface["representative_paths"]
    assert "build_read_only_search_worker_lease" in search_surface["representative_paths"]
    assert "gateway/read_only_search_worker.py" in search_surface["evidence_files"]
    assert "schemas/read_only_search_worker_path.schema.json" in search_surface["evidence_files"]
    assert "scripts/validate_read_only_search_worker_path.py" in search_surface["evidence_files"]
    assert "read_only_search_worker_path_example_passes" in witnesses
    assert "read_only_search_worker_path_rejects_web_retrieval" in witnesses
    assert "read_only_search_worker_rejects_missing_decision_receipt" in witnesses
    assert "read_only_search_worker_rejects_decision_query_mismatch" in witnesses
    assert "read_only_search_worker_rejects_unsupported_format" in witnesses
    assert "read_only_search_worker_rejects_mutation_and_network_inputs" in witnesses
    assert "read_only_search_worker_rejects_secret_like_input_values" in witnesses
    assert closure_actions["publish_read_only_search_worker_path_contract"]["status"] == "closed"


def test_software_dev_capability_pack_surface_requires_explicit_admission() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    software_surface = surfaces["software_dev_capability_pack"]
    witnesses = set(software_surface["runtime_witnesses"])

    assert software_surface["coverage_state"] == "witnessed"
    assert software_surface["request_proof"] == "request_proof"
    assert software_surface["action_proof"] == "action_proof"
    assert "build_software_dev_capability_admission_gate" in software_surface["representative_paths"]
    assert "software_dev.repo_map.read" in software_surface["representative_paths"]
    assert "software_dev.change.run" in software_surface["representative_paths"]
    assert "software_dev.pr_candidate.prepare" in software_surface["representative_paths"]
    assert "capsules/software_dev.json" in software_surface["evidence_files"]
    assert "capabilities/software_dev/capability_pack.json" in software_surface["evidence_files"]
    assert "gateway/capability_fabric.py" in software_surface["evidence_files"]
    assert "mcoi/mcoi_runtime/core/code_intelligence.py" in software_surface["evidence_files"]
    assert "mcoi/mcoi_runtime/core/code_context_builder.py" in software_surface["evidence_files"]
    assert "mcoi/mcoi_runtime/core/software_gate_planner.py" in software_surface["evidence_files"]
    assert "mcoi/mcoi_runtime/workers/code_worker.py" in software_surface["evidence_files"]
    assert "mcoi/mcoi_runtime/core/app_builder/codegen_pipeline.py" in software_surface["evidence_files"]
    assert "mcoi/mcoi_runtime/core/app_builder/pr_candidate.py" in software_surface["evidence_files"]
    assert "schemas/software_dev/app_task_graph.input.schema.json" in software_surface["evidence_files"]
    assert "schemas/software_dev/app_task_graph.output.schema.json" in software_surface["evidence_files"]
    assert "schemas/software_dev/change_run.input.schema.json" in software_surface["evidence_files"]
    assert "schemas/software_dev/code_context_bundle.output.schema.json" in software_surface["evidence_files"]
    assert "schemas/software_dev/context_bundle.input.schema.json" in software_surface["evidence_files"]
    assert "schemas/software_dev/gate_plan.input.schema.json" in software_surface["evidence_files"]
    assert "schemas/software_dev/pr_candidate.output.schema.json" in software_surface["evidence_files"]
    assert "schemas/software_dev/pr_candidate.input.schema.json" in software_surface["evidence_files"]
    assert "schemas/software_dev/repo_map.output.schema.json" in software_surface["evidence_files"]
    assert "schemas/software_dev/repo_map_read.input.schema.json" in software_surface["evidence_files"]
    assert "schemas/software_dev/software_change_receipt.output.schema.json" in software_surface["evidence_files"]
    assert "schemas/software_dev/software_gate_plan.output.schema.json" in software_surface["evidence_files"]
    assert "tests/test_software_dev_capability_pack.py" in software_surface["evidence_files"]
    assert "software_dev_pack_fixture_not_default_loaded" in witnesses
    assert "software_dev_capability_entries_schema_valid" in witnesses
    assert "software_dev_input_schema_refs_materialized" in witnesses
    assert "software_dev_input_schemas_reject_boundary_violations" in witnesses
    assert "software_dev_output_schema_refs_materialized" in witnesses
    assert "software_dev_output_schemas_reject_effect_overclaims" in witnesses
    assert "software_dev_named_loader_installs_only_software_dev_domain" in witnesses
    assert "software_dev_gate_projects_manifest_registry" in witnesses
    assert "software_dev_capsule_refs_match_pack_capabilities" in witnesses
    assert "software_dev_direct_deployment_capability_absent" in witnesses
    assert "software_dev_read_only_records_non_mutating" in witnesses
    assert "software_dev_effectful_records_require_sandbox_approval" in witnesses
    assert "software_dev_pr_candidate_blocks_git_push" in witnesses
    assert "software_dev_pr_candidate_local_commands_are_git_local_only" in witnesses
    assert "software_dev_production_ready_overclaim_rejected" in witnesses
    assert closure_actions["publish_software_dev_capability_pack_contract"]["status"] == "closed"


def test_agentic_control_capability_pack_surface_binds_default_authority() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    agentic_surface = surfaces["agentic_control_capability_pack"]
    witnesses = set(agentic_surface["runtime_witnesses"])

    assert agentic_surface["coverage_state"] == "witnessed"
    assert agentic_surface["request_proof"] == "request_proof"
    assert agentic_surface["action_proof"] == "action_proof"
    assert "agentic_control.mission.define" in agentic_surface["representative_paths"]
    assert "agentic_control.telemetry_triage.plan" in agentic_surface["representative_paths"]
    assert "agentic_control.code_change.plan" in agentic_surface["representative_paths"]
    assert "agentic_control.release_handoff.plan" in agentic_surface["representative_paths"]
    assert "agentic_control.evidence.append" in agentic_surface["representative_paths"]
    assert "agentic_control.project_discipline_mesh.v1" in agentic_surface["representative_paths"]
    assert "agentic_control.goal_governor.v1" in agentic_surface["representative_paths"]
    assert "agentic_control.strategy_governor.v1" in agentic_surface["representative_paths"]
    assert "agentic_control.decision_governor.v1" in agentic_surface["representative_paths"]
    assert "agentic_control.design_governor.v1" in agentic_surface["representative_paths"]
    assert "agentic_control.product_governor.v1" in agentic_surface["representative_paths"]
    assert "agentic_control.management_governor.v1" in agentic_surface["representative_paths"]
    assert "agentic_control.resource_governor.v1" in agentic_surface["representative_paths"]
    assert "agentic_control.policy_governor.v1" in agentic_surface["representative_paths"]
    assert "agentic_control.approval_governor.v1" in agentic_surface["representative_paths"]
    assert "agentic_control.temporal_governor.v1" in agentic_surface["representative_paths"]
    assert "agentic_control.memory_governor.v1" in agentic_surface["representative_paths"]
    assert "agentic_control.evidence_governor.v1" in agentic_surface["representative_paths"]
    assert "agentic_control.math_governor.v1" in agentic_surface["representative_paths"]
    assert "agentic_control.algorithm_governor.v1" in agentic_surface["representative_paths"]
    assert "agentic_control.security_governor.v1" in agentic_surface["representative_paths"]
    assert "agentic_control.swarm_governor.v1" in agentic_surface["representative_paths"]
    assert "agentic_control.coding_governor.v1" in agentic_surface["representative_paths"]
    assert "agentic_control.quality_governor.v1" in agentic_surface["representative_paths"]
    assert "agentic_control.execution_governor.v1" in agentic_surface["representative_paths"]
    assert "agentic_control.runtime_governor.v1" in agentic_surface["representative_paths"]
    assert "agentic_control.release_governor.v1" in agentic_surface["representative_paths"]
    assert "agentic_control.autonomous_operations.v1" in agentic_surface["representative_paths"]
    assert "capsules/agentic_control.json" in agentic_surface["evidence_files"]
    assert "capabilities/agentic_control/capability_pack.json" in agentic_surface["evidence_files"]
    assert "schemas/agentic_control/control_action.input.schema.json" in agentic_surface["evidence_files"]
    assert "schemas/agentic_control/control_action.output.schema.json" in agentic_surface["evidence_files"]
    assert "tests/test_gateway/test_agentic_control_capability_pack.py" in agentic_surface["evidence_files"]
    assert "agentic_control_capability_entries_schema_valid" in witnesses
    assert "agentic_control_pack_projects_governed_authority_records" in witnesses
    assert "agentic_control_schemas_reject_unbounded_or_unknown_payloads" in witnesses
    assert "agentic_control_production_gate_blocks_without_live_evidence" in witnesses


def test_agent_identity_surface_binds_owner_tenant_and_scope() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    witness_surfaces = {
        surface["surface_id"]: surface
        for surface in matrix["witness_integrity"]["surfaces"]
    }
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    identity_surface = surfaces["agent_identity"]
    identity_witness_surface = witness_surfaces["agent_identity"]
    witnesses = set(identity_surface["runtime_witnesses"])

    assert identity_surface["coverage_state"] == "witnessed"
    assert identity_surface["request_proof"] == "request_proof"
    assert identity_surface["action_proof"] == "action_proof"
    assert "AgentIdentityRegistry.register" in identity_surface["representative_paths"]
    assert "AgentIdentityRegistry.evaluate" in identity_surface["representative_paths"]
    assert "gateway/agent_identity.py" in identity_surface["evidence_files"]
    assert "schemas/agent_identity.schema.json" in identity_surface["evidence_files"]
    assert "tests/test_gateway/test_agent_identity.py" in identity_surface["evidence_files"]
    assert "owner_tenant_identity_required" in witnesses
    assert "self_approval_forbidden" in witnesses
    assert "policy_mutation_forbidden" in witnesses
    assert "delegation_requires_lease" in witnesses
    assert "agent_budget_enforced" in witnesses
    assert "agent_identity_schema_valid" in witnesses
    assert identity_witness_surface["exact_test_anchor_count"] == 8
    assert identity_witness_surface["unanchored_witness_count"] == 0
    assert closure_actions["publish_agent_identity_contract"]["status"] == "closed"


def test_oidc_jwks_refresh_evidence_surface_binds_trust_chain_receipts() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    witness_surfaces = {
        surface["surface_id"]: surface
        for surface in matrix["witness_integrity"]["surfaces"]
    }
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    refresh_surface = surfaces["oidc_jwks_refresh_evidence"]
    refresh_witness_surface = witness_surfaces["oidc_jwks_refresh_evidence"]
    witnesses = set(refresh_surface["runtime_witnesses"])

    assert refresh_surface["coverage_state"] == "witnessed"
    assert refresh_surface["request_proof"] == "request_proof"
    assert refresh_surface["action_proof"] == "action_proof"
    assert "assess_oidc_jwks_refresh_evidence" in refresh_surface["representative_paths"]
    assert "gateway/tenant_identity.py" in refresh_surface["evidence_files"]
    assert "docs/54_authority_directory_sync.md" in refresh_surface["evidence_files"]
    assert "tests/test_gateway/test_tenant_identity.py" in refresh_surface["evidence_files"]
    assert "fresh_https_jwks_receipt_accepted" in witnesses
    assert "stale_cache_and_missing_refs_blocked" in witnesses
    assert "insecure_discovery_and_redirects_blocked" in witnesses
    assert "invalid_hashes_and_algorithms_blocked" in witnesses
    assert "non_boolean_boundary_flags_rejected" in witnesses
    assert "jwks_refresh_supports_trusted_header_admission" in witnesses
    assert refresh_witness_surface["exact_test_anchor_count"] == 6
    assert refresh_witness_surface["unanchored_witness_count"] == 0
    assert closure_actions["publish_oidc_jwks_refresh_evidence_contract"]["status"] == "closed"


def test_trusted_identity_header_boundary_surface_blocks_header_spoofing() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    witness_surfaces = {
        surface["surface_id"]: surface
        for surface in matrix["witness_integrity"]["surfaces"]
    }
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    header_surface = surfaces["trusted_identity_header_boundary"]
    header_witness_surface = witness_surfaces["trusted_identity_header_boundary"]
    witnesses = set(header_surface["runtime_witnesses"])

    assert header_surface["coverage_state"] == "witnessed"
    assert header_surface["request_proof"] == "request_proof"
    assert header_surface["action_proof"] == "action_proof"
    assert "assess_trusted_identity_header_boundary" in header_surface["representative_paths"]
    assert "gateway/tenant_identity.py" in header_surface["evidence_files"]
    assert "docs/54_authority_directory_sync.md" in header_surface["evidence_files"]
    assert "tests/test_gateway/test_tenant_identity.py" in header_surface["evidence_files"]
    assert "trusted_headers_disabled_by_default" in witnesses
    assert "complete_oidc_gateway_evidence_accepted" in witnesses
    assert "complete_mtls_gateway_evidence_accepted" in witnesses
    assert "missing_gateway_evidence_blocked" in witnesses
    assert "malformed_evidence_refs_rejected" in witnesses
    assert "non_boolean_gateway_evidence_rejected" in witnesses
    assert "jwks_refresh_assessment_binds_trusted_header_path" in witnesses
    assert header_witness_surface["exact_test_anchor_count"] == 7
    assert header_witness_surface["unanchored_witness_count"] == 0
    assert closure_actions["publish_trusted_identity_header_boundary_contract"]["status"] == "closed"


def test_claim_verification_surface_gates_execution_admission() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    witness_surfaces = {
        surface["surface_id"]: surface
        for surface in matrix["witness_integrity"]["surfaces"]
    }
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    claim_surface = surfaces["claim_verification"]
    claim_witness_surface = witness_surfaces["claim_verification"]
    witnesses = set(claim_surface["runtime_witnesses"])

    assert claim_surface["coverage_state"] == "witnessed"
    assert claim_surface["request_proof"] == "request_proof"
    assert claim_surface["action_proof"] == "action_proof"
    assert "ClaimVerificationEngine.verify" in claim_surface["representative_paths"]
    assert "gateway/claim_verification.py" in claim_surface["evidence_files"]
    assert "schemas/claim_verification_report.schema.json" in claim_surface["evidence_files"]
    assert "tests/test_gateway/test_claim_verification.py" in claim_surface["evidence_files"]
    assert "source_evidence_required" in witnesses
    assert "contradictions_block_execution" in witnesses
    assert "stale_claims_block_execution" in witnesses
    assert "high_risk_requires_independent_support" in witnesses
    assert "claim_verification_schema_valid" in witnesses
    assert claim_witness_surface["exact_test_anchor_count"] == 6
    assert claim_witness_surface["unanchored_witness_count"] == 0
    assert closure_actions["publish_claim_verification_report_contract"]["status"] == "closed"


def test_governed_connector_framework_surface_gates_invocation_lifecycle() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    witness_surfaces = {
        surface["surface_id"]: surface
        for surface in matrix["witness_integrity"]["surfaces"]
    }
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    connector_surface = surfaces["governed_connector_framework"]
    connector_witness_surface = witness_surfaces["governed_connector_framework"]
    witnesses = set(connector_surface["runtime_witnesses"])
    route_records = {
        record["route"]: record
        for record in matrix["route_coverage"]["routes"]
    }

    assert connector_surface["coverage_state"] == "proven"
    assert connector_surface["request_proof"] == "request_proof"
    assert connector_surface["action_proof"] == "action_proof"
    assert "/api/v1/connectors/register" in connector_surface["representative_paths"]
    assert "/api/v1/connectors/invoke" in connector_surface["representative_paths"]
    assert "/api/v1/connectors/{connector_id}/disable" in connector_surface["representative_paths"]
    assert "/api/v1/connectors/{connector_id}/enable" in connector_surface["representative_paths"]
    assert "mcoi/mcoi_runtime/app/routers/connectors.py" in connector_surface["evidence_files"]
    assert "mcoi/mcoi_runtime/core/connector_framework.py" in connector_surface["evidence_files"]
    assert "mcoi/tests/test_connector_framework.py" in connector_surface["evidence_files"]
    assert "mcoi/tests/test_server_phase217.py" in connector_surface["evidence_files"]
    assert "mcoi/tests/test_server_phase218.py" in connector_surface["evidence_files"]
    assert "docs/64_durable_gmail_connector_runtime_plan.md" in connector_surface["evidence_files"]
    assert "schemas/durable_gmail_oauth_operator_handoff.schema.json" in connector_surface["evidence_files"]
    assert "scripts/produce_durable_gmail_oauth_operator_handoff.py" in connector_surface["evidence_files"]
    assert "scripts/validate_durable_gmail_oauth_operator_handoff.py" in connector_surface["evidence_files"]
    assert "tests/test_produce_durable_gmail_oauth_operator_handoff.py" in connector_surface["evidence_files"]
    assert "tests/test_validate_durable_gmail_oauth_operator_handoff.py" in connector_surface["evidence_files"]
    assert "schemas/team_ops_shared_inbox_operator_handoff.schema.json" in connector_surface["evidence_files"]
    assert "scripts/produce_team_ops_shared_inbox_operator_handoff.py" in connector_surface["evidence_files"]
    assert "scripts/validate_team_ops_shared_inbox_operator_handoff.py" in connector_surface["evidence_files"]
    assert "tests/test_produce_team_ops_shared_inbox_operator_handoff.py" in connector_surface["evidence_files"]
    assert "tests/test_validate_team_ops_shared_inbox_operator_handoff.py" in connector_surface["evidence_files"]
    assert "schemas/team_ops_shared_inbox_live_probe_approval_binding.schema.json" in connector_surface[
        "evidence_files"
    ]
    assert "scripts/bind_team_ops_shared_inbox_live_probe_approval.py" in connector_surface["evidence_files"]
    assert "scripts/validate_team_ops_shared_inbox_live_probe_approval_binding.py" in connector_surface[
        "evidence_files"
    ]
    assert "tests/test_bind_team_ops_shared_inbox_live_probe_approval.py" in connector_surface["evidence_files"]
    assert "tests/test_validate_team_ops_shared_inbox_live_probe_approval_binding.py" in connector_surface[
        "evidence_files"
    ]
    assert "schemas/team_ops_shared_inbox_live_probe_authority.schema.json" in connector_surface["evidence_files"]
    assert "scripts/produce_team_ops_shared_inbox_live_probe_authority.py" in connector_surface["evidence_files"]
    assert "scripts/validate_team_ops_shared_inbox_live_probe_authority.py" in connector_surface["evidence_files"]
    assert "tests/test_produce_team_ops_shared_inbox_live_probe_authority.py" in connector_surface["evidence_files"]
    assert "tests/test_validate_team_ops_shared_inbox_live_probe_authority.py" in connector_surface["evidence_files"]
    assert "schemas/team_ops_shared_inbox_live_probe_operator_input_request.schema.json" in connector_surface[
        "evidence_files"
    ]
    assert "scripts/emit_team_ops_shared_inbox_live_probe_operator_input_request.py" in connector_surface[
        "evidence_files"
    ]
    assert "scripts/validate_team_ops_shared_inbox_live_probe_operator_input_request.py" in connector_surface[
        "evidence_files"
    ]
    assert "tests/test_emit_team_ops_shared_inbox_live_probe_operator_input_request.py" in connector_surface[
        "evidence_files"
    ]
    assert "tests/test_validate_team_ops_shared_inbox_live_probe_operator_input_request.py" in connector_surface[
        "evidence_files"
    ]
    assert "schemas/team_ops_shared_inbox_live_probe_receipt.schema.json" in connector_surface["evidence_files"]
    assert "scripts/produce_team_ops_shared_inbox_live_probe_receipt.py" in connector_surface["evidence_files"]
    assert "scripts/validate_team_ops_shared_inbox_live_probe_receipt.py" in connector_surface["evidence_files"]
    assert "tests/test_produce_team_ops_shared_inbox_live_probe_receipt.py" in connector_surface["evidence_files"]
    assert "tests/test_validate_team_ops_shared_inbox_live_probe_receipt.py" in connector_surface["evidence_files"]
    assert "schemas/team_ops_shared_inbox_observation_routing_receipt.schema.json" in connector_surface[
        "evidence_files"
    ]
    assert "scripts/produce_team_ops_shared_inbox_observation_routing_receipt.py" in connector_surface[
        "evidence_files"
    ]
    assert "scripts/validate_team_ops_shared_inbox_observation_routing_receipt.py" in connector_surface[
        "evidence_files"
    ]
    assert "tests/test_produce_team_ops_shared_inbox_observation_routing_receipt.py" in connector_surface[
        "evidence_files"
    ]
    assert "tests/test_validate_team_ops_shared_inbox_observation_routing_receipt.py" in connector_surface[
        "evidence_files"
    ]
    assert "schemas/team_ops_shared_inbox_approval_queue_receipt.schema.json" in connector_surface["evidence_files"]
    assert "scripts/produce_team_ops_shared_inbox_approval_queue_receipt.py" in connector_surface["evidence_files"]
    assert "scripts/validate_team_ops_shared_inbox_approval_queue_receipt.py" in connector_surface["evidence_files"]
    assert "tests/test_produce_team_ops_shared_inbox_approval_queue_receipt.py" in connector_surface[
        "evidence_files"
    ]
    assert "tests/test_validate_team_ops_shared_inbox_approval_queue_receipt.py" in connector_surface[
        "evidence_files"
    ]
    assert "schemas/team_ops_shared_inbox_approval_decision_receipt.schema.json" in connector_surface[
        "evidence_files"
    ]
    assert "scripts/produce_team_ops_shared_inbox_approval_decision_receipt.py" in connector_surface[
        "evidence_files"
    ]
    assert "scripts/validate_team_ops_shared_inbox_approval_decision_receipt.py" in connector_surface[
        "evidence_files"
    ]
    assert "tests/test_produce_team_ops_shared_inbox_approval_decision_receipt.py" in connector_surface[
        "evidence_files"
    ]
    assert "tests/test_validate_team_ops_shared_inbox_approval_decision_receipt.py" in connector_surface[
        "evidence_files"
    ]
    assert "schemas/team_ops_shared_inbox_send_preparation_receipt.schema.json" in connector_surface["evidence_files"]
    assert "scripts/produce_team_ops_shared_inbox_send_preparation_receipt.py" in connector_surface["evidence_files"]
    assert "scripts/validate_team_ops_shared_inbox_send_preparation_receipt.py" in connector_surface[
        "evidence_files"
    ]
    assert "tests/test_produce_team_ops_shared_inbox_send_preparation_receipt.py" in connector_surface[
        "evidence_files"
    ]
    assert "tests/test_validate_team_ops_shared_inbox_send_preparation_receipt.py" in connector_surface[
        "evidence_files"
    ]
    assert "schemas/team_ops_shared_inbox_send_execution_receipt.schema.json" in connector_surface["evidence_files"]
    assert "scripts/produce_team_ops_shared_inbox_send_execution_receipt.py" in connector_surface["evidence_files"]
    assert "scripts/validate_team_ops_shared_inbox_send_execution_receipt.py" in connector_surface["evidence_files"]
    assert "tests/test_produce_team_ops_shared_inbox_send_execution_receipt.py" in connector_surface[
        "evidence_files"
    ]
    assert "tests/test_validate_team_ops_shared_inbox_send_execution_receipt.py" in connector_surface[
        "evidence_files"
    ]
    assert "schemas/team_ops_shared_inbox_sent_message_observation_receipt.schema.json" in connector_surface[
        "evidence_files"
    ]
    assert "scripts/produce_team_ops_shared_inbox_sent_message_observation_receipt.py" in connector_surface[
        "evidence_files"
    ]
    assert "scripts/validate_team_ops_shared_inbox_sent_message_observation_receipt.py" in connector_surface[
        "evidence_files"
    ]
    assert "tests/test_produce_team_ops_shared_inbox_sent_message_observation_receipt.py" in connector_surface[
        "evidence_files"
    ]
    assert "tests/test_validate_team_ops_shared_inbox_sent_message_observation_receipt.py" in connector_surface[
        "evidence_files"
    ]
    assert "schemas/team_ops_shared_inbox_terminal_closure_review_packet.schema.json" in connector_surface[
        "evidence_files"
    ]
    assert "scripts/produce_team_ops_shared_inbox_terminal_closure_review_packet.py" in connector_surface[
        "evidence_files"
    ]
    assert "scripts/validate_team_ops_shared_inbox_terminal_closure_review_packet.py" in connector_surface[
        "evidence_files"
    ]
    assert "tests/test_produce_team_ops_shared_inbox_terminal_closure_review_packet.py" in connector_surface[
        "evidence_files"
    ]
    assert "tests/test_validate_team_ops_shared_inbox_terminal_closure_review_packet.py" in connector_surface[
        "evidence_files"
    ]
    assert "scripts/mint_team_ops_shared_inbox_terminal_closure_certificate.py" in connector_surface["evidence_files"]
    assert "scripts/validate_team_ops_shared_inbox_terminal_closure_certificate.py" in connector_surface[
        "evidence_files"
    ]
    assert "tests/test_mint_team_ops_shared_inbox_terminal_closure_certificate.py" in connector_surface[
        "evidence_files"
    ]
    assert "tests/test_validate_team_ops_shared_inbox_terminal_closure_certificate.py" in connector_surface[
        "evidence_files"
    ]
    assert "scripts/produce_team_ops_shared_inbox_terminal_closure_evidence_bundle.py" in connector_surface[
        "evidence_files"
    ]
    assert "scripts/validate_team_ops_shared_inbox_terminal_closure_evidence_bundle.py" in connector_surface[
        "evidence_files"
    ]
    assert "tests/test_produce_team_ops_shared_inbox_terminal_closure_evidence_bundle.py" in connector_surface[
        "evidence_files"
    ]
    assert "tests/test_validate_team_ops_shared_inbox_terminal_closure_evidence_bundle.py" in connector_surface[
        "evidence_files"
    ]
    assert "schemas/team_ops_shared_inbox_terminal_closure_anchor_preflight.schema.json" in connector_surface[
        "evidence_files"
    ]
    assert "scripts/produce_team_ops_shared_inbox_terminal_closure_anchor_preflight.py" in connector_surface[
        "evidence_files"
    ]
    assert "scripts/validate_team_ops_shared_inbox_terminal_closure_anchor_preflight.py" in connector_surface[
        "evidence_files"
    ]
    assert "tests/test_produce_team_ops_shared_inbox_terminal_closure_anchor_preflight.py" in connector_surface[
        "evidence_files"
    ]
    assert "tests/test_validate_team_ops_shared_inbox_terminal_closure_anchor_preflight.py" in connector_surface[
        "evidence_files"
    ]
    assert "schemas/team_ops_shared_inbox_terminal_closure_anchor_receipt.schema.json" in connector_surface[
        "evidence_files"
    ]
    assert "scripts/produce_team_ops_shared_inbox_terminal_closure_anchor_receipt.py" in connector_surface[
        "evidence_files"
    ]
    assert "scripts/validate_team_ops_shared_inbox_terminal_closure_anchor_receipt.py" in connector_surface[
        "evidence_files"
    ]
    assert "tests/test_produce_team_ops_shared_inbox_terminal_closure_anchor_receipt.py" in connector_surface[
        "evidence_files"
    ]
    assert "tests/test_validate_team_ops_shared_inbox_terminal_closure_anchor_receipt.py" in connector_surface[
        "evidence_files"
    ]
    assert "connector_registration_typed" in witnesses
    assert "connector_invocation_guard_chain_checked" in witnesses
    assert "connector_lifecycle_disable_enable_bounded" in witnesses
    assert "connector_history_summary_bounded" in witnesses
    assert "connector_errors_sanitized" in witnesses
    assert "connector_invocation_audited" in witnesses
    assert "durable_gmail_oauth_handoff_blocks_until_authority" in witnesses
    assert "durable_gmail_oauth_handoff_blocks_default_as_evidence" in witnesses
    assert "durable_gmail_oauth_handoff_requires_live_probe_authority" in witnesses
    assert "durable_gmail_oauth_handoff_redacts_secret_markers" in witnesses
    assert "durable_gmail_oauth_handoff_accepts_ready_probe" in witnesses
    assert "durable_gmail_oauth_handoff_writes_validation_receipt" in witnesses
    assert "durable_gmail_oauth_uses_github_repo_inventory" in witnesses
    assert "durable_gmail_oauth_blocks_case_insensitive_secret_markers" in witnesses
    assert "durable_gmail_oauth_routes_witness_refs_as_variables" in witnesses
    assert "durable_gmail_oauth_rejects_secret_markers_in_readable_signals" in witnesses
    assert "durable_gmail_oauth_validates_repository_slug" in witnesses
    assert "team_ops_shared_inbox_handoff_blocks_until_authority" in witnesses
    assert "team_ops_shared_inbox_handoff_blocks_default_as_evidence" in witnesses
    assert "team_ops_shared_inbox_handoff_requires_live_probe_authority" in witnesses
    assert "team_ops_shared_inbox_handoff_redacts_secret_markers" in witnesses
    assert "team_ops_shared_inbox_handoff_accepts_ready_probe" in witnesses
    assert "team_ops_shared_inbox_handoff_blocks_external_message_drift" in witnesses
    assert "team_ops_shared_inbox_handoff_writes_validation_receipt" in witnesses
    assert "team_ops_shared_inbox_probe_approval_binding_lists_blockers" in witnesses
    assert "team_ops_shared_inbox_probe_approval_binding_allows_ready_handoff" in witnesses
    assert "team_ops_shared_inbox_probe_approval_binding_blocks_invalid_handoff" in witnesses
    assert "team_ops_shared_inbox_probe_approval_binding_blocks_effect_drift" in witnesses
    assert "team_ops_shared_inbox_probe_approval_binding_redacts_secret_markers" in witnesses
    assert "team_ops_shared_inbox_probe_approval_binding_writes_validation_receipt" in witnesses
    assert "team_ops_shared_inbox_probe_authority_blocks_missing_handoff" in witnesses
    assert "team_ops_shared_inbox_probe_authority_requires_probe_approval" in witnesses
    assert "team_ops_shared_inbox_probe_authority_admits_read_only_probe" in witnesses
    assert "team_ops_shared_inbox_probe_authority_blocks_effect_drift" in witnesses
    assert "team_ops_shared_inbox_probe_authority_redacts_secret_markers" in witnesses
    assert "team_ops_shared_inbox_probe_authority_writes_validation_receipt" in witnesses
    assert "team_ops_shared_inbox_probe_input_request_lists_blockers" in witnesses
    assert "team_ops_shared_inbox_probe_input_request_names_approval_binding_blockers" in witnesses
    assert "team_ops_shared_inbox_probe_input_request_allows_admitted_authority" in witnesses
    assert "team_ops_shared_inbox_probe_input_request_blocks_invalid_authority" in witnesses
    assert "team_ops_shared_inbox_probe_input_request_blocks_effect_drift" in witnesses
    assert "team_ops_shared_inbox_probe_input_request_redacts_secret_markers" in witnesses
    assert "team_ops_shared_inbox_probe_input_request_writes_validation_receipt" in witnesses
    assert "team_ops_shared_inbox_probe_receipt_blocks_without_operator_input" in witnesses
    assert "team_ops_shared_inbox_probe_receipt_requires_observation_evidence" in witnesses
    assert "team_ops_shared_inbox_probe_receipt_accepts_read_only_observation" in witnesses
    assert "team_ops_shared_inbox_probe_receipt_blocks_effect_drift" in witnesses
    assert "team_ops_shared_inbox_probe_receipt_redacts_secret_markers" in witnesses
    assert "team_ops_shared_inbox_probe_receipt_writes_validation_receipt" in witnesses
    assert "team_ops_shared_inbox_observation_routing_blocks_without_live_probe" in witnesses
    assert "team_ops_shared_inbox_observation_routing_requires_redacted_observation" in witnesses
    assert "team_ops_shared_inbox_observation_routing_accepts_assignment_plan" in witnesses
    assert "team_ops_shared_inbox_observation_routing_blocks_effect_drift" in witnesses
    assert "team_ops_shared_inbox_observation_routing_redacts_secret_markers" in witnesses
    assert "team_ops_shared_inbox_observation_routing_writes_validation_receipt" in witnesses
    assert "team_ops_shared_inbox_approval_queue_blocks_without_routing" in witnesses
    assert "team_ops_shared_inbox_approval_queue_requires_request_evidence" in witnesses
    assert "team_ops_shared_inbox_approval_queue_accepts_pending_obligation" in witnesses
    assert "team_ops_shared_inbox_approval_queue_blocks_effect_drift" in witnesses
    assert "team_ops_shared_inbox_approval_queue_redacts_secret_markers" in witnesses
    assert "team_ops_shared_inbox_approval_queue_writes_validation_receipt" in witnesses
    assert "team_ops_shared_inbox_approval_decision_blocks_without_queue" in witnesses
    assert "team_ops_shared_inbox_approval_decision_requires_decision_evidence" in witnesses
    assert "team_ops_shared_inbox_approval_decision_accepts_operator_decisions" in witnesses
    assert "team_ops_shared_inbox_approval_decision_blocks_role_or_authorization_drift" in witnesses
    assert "team_ops_shared_inbox_approval_decision_redacts_secret_markers" in witnesses
    assert "team_ops_shared_inbox_approval_decision_writes_validation_receipt" in witnesses
    assert "team_ops_shared_inbox_send_preparation_blocks_without_decision" in witnesses
    assert "team_ops_shared_inbox_send_preparation_requires_preparation_evidence" in witnesses
    assert "team_ops_shared_inbox_send_preparation_accepts_approved_packet" in witnesses
    assert "team_ops_shared_inbox_send_preparation_blocks_denied_or_drift" in witnesses
    assert "team_ops_shared_inbox_send_preparation_redacts_secret_markers" in witnesses
    assert "team_ops_shared_inbox_send_preparation_writes_validation_receipt" in witnesses
    assert "team_ops_shared_inbox_send_execution_blocks_without_preparation" in witnesses
    assert "team_ops_shared_inbox_send_execution_requires_execution_evidence" in witnesses
    assert "team_ops_shared_inbox_send_execution_accepts_provider_receipt" in witnesses
    assert "team_ops_shared_inbox_send_execution_blocks_drift_or_local_provider_claim" in witnesses
    assert "team_ops_shared_inbox_send_execution_redacts_secret_markers" in witnesses
    assert "team_ops_shared_inbox_send_execution_writes_validation_receipt" in witnesses
    assert "team_ops_shared_inbox_sent_message_observation_blocks_without_execution" in witnesses
    assert "team_ops_shared_inbox_sent_message_observation_requires_observation_replay" in witnesses
    assert "team_ops_shared_inbox_sent_message_observation_accepts_replay_closure" in witnesses
    assert "team_ops_shared_inbox_sent_message_observation_blocks_inconsistent_or_local_provider_claim" in witnesses
    assert "team_ops_shared_inbox_sent_message_observation_redacts_secret_markers" in witnesses
    assert "team_ops_shared_inbox_sent_message_observation_writes_validation_receipt" in witnesses
    assert "team_ops_shared_inbox_terminal_closure_review_blocks_without_observation" in witnesses
    assert "team_ops_shared_inbox_terminal_closure_review_requires_ready_packet" in witnesses
    assert "team_ops_shared_inbox_terminal_closure_review_accepts_candidate_packet" in witnesses
    assert "team_ops_shared_inbox_terminal_closure_review_blocks_certificate_or_raw_claim" in witnesses
    assert "team_ops_shared_inbox_terminal_closure_review_redacts_secret_markers" in witnesses
    assert "team_ops_shared_inbox_terminal_closure_review_writes_validation_receipt" in witnesses
    assert "team_ops_shared_inbox_terminal_closure_certificate_blocks_without_ready_review" in witnesses
    assert "team_ops_shared_inbox_terminal_closure_certificate_mints_schema_valid_certificate" in witnesses
    assert "team_ops_shared_inbox_terminal_closure_certificate_binds_source_review_packet" in witnesses
    assert "team_ops_shared_inbox_terminal_closure_certificate_rejects_generic_or_drifted_certificate" in witnesses
    assert "team_ops_shared_inbox_terminal_closure_certificate_blocks_raw_secret_or_production_claim" in witnesses
    assert "team_ops_shared_inbox_terminal_closure_certificate_writes_certificate_and_validation_receipts" in witnesses
    assert "team_ops_shared_inbox_terminal_closure_evidence_bundle_blocks_missing_secret" in witnesses
    assert "team_ops_shared_inbox_terminal_closure_evidence_bundle_signs_ready_certificate" in witnesses
    assert "team_ops_shared_inbox_terminal_closure_evidence_bundle_verifies_hmac" in witnesses
    assert "team_ops_shared_inbox_terminal_closure_evidence_bundle_binds_source_certificate" in witnesses
    assert "team_ops_shared_inbox_terminal_closure_evidence_bundle_blocks_raw_secret_or_production_claim" in witnesses
    assert "team_ops_shared_inbox_terminal_closure_evidence_bundle_writes_bundle_and_validation_receipts" in witnesses
    assert "team_ops_shared_inbox_terminal_closure_anchor_preflight_accepts_ready_bundle" in witnesses
    assert "team_ops_shared_inbox_terminal_closure_anchor_preflight_blocks_missing_authority_or_secret" in witnesses
    assert "team_ops_shared_inbox_terminal_closure_anchor_preflight_projects_anchor_artifacts" in witnesses
    assert "team_ops_shared_inbox_terminal_closure_anchor_preflight_blocks_invalid_bundle_or_target" in witnesses
    assert "team_ops_shared_inbox_terminal_closure_anchor_preflight_blocks_effect_or_raw_claim" in witnesses
    assert "team_ops_shared_inbox_terminal_closure_anchor_preflight_writes_preflight_and_validation_receipts" in witnesses
    assert "team_ops_shared_inbox_terminal_closure_anchor_receipt_accepts_ready_preflight" in witnesses
    assert "team_ops_shared_inbox_terminal_closure_anchor_receipt_blocks_missing_or_unready_inputs" in witnesses
    assert "team_ops_shared_inbox_terminal_closure_anchor_receipt_binds_preflight_bundle_and_artifacts" in witnesses
    assert "team_ops_shared_inbox_terminal_closure_anchor_receipt_verifies_anchor_signature" in witnesses
    assert "team_ops_shared_inbox_terminal_closure_anchor_receipt_blocks_effect_or_raw_claim" in witnesses
    assert "team_ops_shared_inbox_terminal_closure_anchor_receipt_writes_receipt_and_validation_receipts" in witnesses
    assert connector_witness_surface["exact_test_anchor_count"] == 115
    assert connector_witness_surface["unanchored_witness_count"] == 0
    assert route_records["/api/v1/connectors/register"]["coverage_state"] == "proven"
    assert route_records["/api/v1/connectors/register"]["surface_id"] == "governed_connector_framework"
    assert route_records["/api/v1/connectors/invoke"]["coverage_state"] == "proven"
    assert route_records["/api/v1/connectors/invoke"]["surface_id"] == "governed_connector_framework"
    assert closure_actions["classify_governed_connector_routes"]["status"] == "closed"
    assert closure_actions["publish_durable_gmail_oauth_operator_handoff_contract"]["status"] == "closed"
    assert closure_actions["publish_team_ops_shared_inbox_operator_handoff_contract"]["status"] == "closed"
    assert closure_actions["publish_team_ops_shared_inbox_live_probe_approval_binding_contract"]["status"] == "closed"
    assert closure_actions["publish_team_ops_shared_inbox_live_probe_authority_contract"]["status"] == "closed"
    assert closure_actions["publish_team_ops_shared_inbox_live_probe_operator_input_request_contract"][
        "status"
    ] == "closed"
    assert closure_actions["publish_team_ops_shared_inbox_live_probe_receipt_contract"]["status"] == "closed"
    assert closure_actions["publish_team_ops_shared_inbox_observation_routing_receipt_contract"][
        "status"
    ] == "closed"
    assert closure_actions["publish_team_ops_shared_inbox_approval_queue_receipt_contract"]["status"] == "closed"
    assert closure_actions["publish_team_ops_shared_inbox_approval_decision_receipt_contract"]["status"] == "closed"
    assert closure_actions["publish_team_ops_shared_inbox_send_preparation_receipt_contract"]["status"] == "closed"
    assert closure_actions["publish_team_ops_shared_inbox_send_execution_receipt_contract"]["status"] == "closed"
    assert (
        closure_actions["publish_team_ops_shared_inbox_sent_message_observation_receipt_contract"]["status"]
        == "closed"
    )
    assert (
        closure_actions["publish_team_ops_shared_inbox_terminal_closure_review_packet_contract"]["status"]
        == "closed"
    )
    assert (
        closure_actions["publish_team_ops_shared_inbox_terminal_closure_certificate_contract"]["status"]
        == "closed"
    )
    assert (
        closure_actions["publish_team_ops_shared_inbox_terminal_closure_evidence_bundle_contract"]["status"]
        == "closed"
    )
    assert (
        closure_actions["publish_team_ops_shared_inbox_terminal_closure_anchor_preflight_contract"]["status"]
        == "closed"
    )
    assert (
        closure_actions["publish_team_ops_shared_inbox_terminal_closure_anchor_receipt_contract"]["status"]
        == "closed"
    )


def test_governed_background_scheduler_surface_gates_job_lifecycle() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    scheduler_surface = surfaces["governed_background_scheduler"]
    witnesses = set(scheduler_surface["runtime_witnesses"])
    route_records = {
        record["route"]: record
        for record in matrix["route_coverage"]["routes"]
    }

    assert scheduler_surface["coverage_state"] == "proven"
    assert scheduler_surface["request_proof"] == "request_proof"
    assert scheduler_surface["action_proof"] == "action_proof"
    assert "/api/v1/scheduler/jobs" in scheduler_surface["representative_paths"]
    assert "/api/v1/scheduler/execute" in scheduler_surface["representative_paths"]
    assert "/api/v1/scheduler/jobs/{job_id}" in scheduler_surface["representative_paths"]
    assert "/api/v1/scheduler/jobs/{job_id}/disable" in scheduler_surface["representative_paths"]
    assert "/api/v1/scheduler/jobs/{job_id}/enable" in scheduler_surface["representative_paths"]
    assert "mcoi/mcoi_runtime/app/routers/scheduler.py" in scheduler_surface["evidence_files"]
    assert "mcoi/mcoi_runtime/core/scheduler.py" in scheduler_surface["evidence_files"]
    assert "mcoi/tests/test_scheduler.py" in scheduler_surface["evidence_files"]
    assert "mcoi/tests/test_server_phase217.py" in scheduler_surface["evidence_files"]
    assert "mcoi/tests/test_server_phase218.py" in scheduler_surface["evidence_files"]
    assert "scheduler_job_registration_typed" in witnesses
    assert "scheduler_execute_guard_chain_checked" in witnesses
    assert "scheduler_lifecycle_controls_bounded" in witnesses
    assert "scheduler_history_summary_bounded" in witnesses
    assert "scheduler_errors_sanitized" in witnesses
    assert "scheduler_execution_audited" in witnesses
    assert route_records["/api/v1/scheduler/jobs"]["coverage_state"] == "proven"
    assert route_records["/api/v1/scheduler/jobs"]["surface_id"] == "governed_background_scheduler"
    assert route_records["/api/v1/scheduler/execute"]["coverage_state"] == "proven"
    assert route_records["/api/v1/scheduler/execute"]["surface_id"] == "governed_background_scheduler"
    assert closure_actions["classify_governed_scheduler_routes"]["status"] == "closed"


def test_multi_agent_coordination_runtime_surface_tracks_cooperation_lifecycle() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    multi_agent_surface = surfaces["multi_agent_coordination_runtime"]
    witnesses = set(multi_agent_surface["runtime_witnesses"])
    route_records = {
        record["route"]: record
        for record in matrix["route_coverage"]["routes"]
    }

    assert multi_agent_surface["coverage_state"] == "proven"
    assert multi_agent_surface["request_proof"] == "request_proof"
    assert multi_agent_surface["action_proof"] == "action_proof"
    assert "/api/v1/multi-agent/delegate" in multi_agent_surface["representative_paths"]
    assert "/api/v1/multi-agent/delegate/resolve" in multi_agent_surface["representative_paths"]
    assert "/api/v1/multi-agent/handoff" in multi_agent_surface["representative_paths"]
    assert "/api/v1/multi-agent/conflicts/unresolved" in multi_agent_surface["representative_paths"]
    assert "mcoi/mcoi_runtime/app/routers/multi_agent.py" in multi_agent_surface["evidence_files"]
    assert "mcoi/mcoi_runtime/contracts/coordination.py" in multi_agent_surface["evidence_files"]
    assert "mcoi/mcoi_runtime/core/coordination.py" in multi_agent_surface["evidence_files"]
    assert "mcoi/tests/test_multi_agent_runtime.py" in multi_agent_surface["evidence_files"]
    assert "multi_agent_delegation_tracked" in witnesses
    assert "multi_agent_handoff_preserves_context" in witnesses
    assert "multi_agent_conflict_strategy_typed" in witnesses
    assert "multi_agent_errors_sanitized" in witnesses
    assert route_records["/api/v1/multi-agent/delegate"]["coverage_state"] == "proven"
    assert route_records["/api/v1/multi-agent/delegate"]["surface_id"] == "multi_agent_coordination_runtime"
    assert route_records["/api/v1/multi-agent/summary"]["coverage_state"] == "proven"
    assert route_records["/api/v1/multi-agent/summary"]["surface_id"] == "multi_agent_coordination_runtime"
    assert closure_actions["classify_multi_agent_coordination_routes"]["status"] == "closed"


def test_task_queue_lifecycle_surface_tracks_priority_processing() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    queue_surface = surfaces["task_queue_lifecycle"]
    witnesses = set(queue_surface["runtime_witnesses"])
    route_records = {
        record["route"]: record
        for record in matrix["route_coverage"]["routes"]
    }

    assert queue_surface["coverage_state"] == "witnessed"
    assert queue_surface["request_proof"] == "request_proof"
    assert queue_surface["action_proof"] == "action_proof"
    assert "/api/v1/queue/submit" in queue_surface["representative_paths"]
    assert "/api/v1/queue/process" in queue_surface["representative_paths"]
    assert "/api/v1/queue/status" in queue_surface["representative_paths"]
    assert "/api/v1/queue/result/{task_id}" in queue_surface["representative_paths"]
    assert "mcoi/mcoi_runtime/app/routers/agent.py" in queue_surface["evidence_files"]
    assert "mcoi/mcoi_runtime/core/task_queue.py" in queue_surface["evidence_files"]
    assert "mcoi/tests/test_task_queue.py" in queue_surface["evidence_files"]
    assert "mcoi/tests/test_server_phase215.py" in queue_surface["evidence_files"]
    assert "task_queue_priority_order" in witnesses
    assert "task_queue_depth_bounded" in witnesses
    assert "task_queue_submit_mutation_receipt_emitted" in witnesses
    assert "task_queue_process_mutation_receipts_emitted" in witnesses
    assert "task_queue_mutation_receipt_closes_effect_assurance" in witnesses
    assert "task_queue_empty_process_bounded" in witnesses
    assert "task_queue_missing_result_bounded" in witnesses
    assert "task_queue_errors_sanitized" in witnesses
    assert route_records["/api/v1/queue/submit"]["coverage_state"] == "witnessed"
    assert route_records["/api/v1/queue/submit"]["surface_id"] == "task_queue_lifecycle"
    assert route_records["/api/v1/queue/result/{task_id}"]["coverage_state"] == "witnessed"
    assert route_records["/api/v1/queue/result/{task_id}"]["surface_id"] == "task_queue_lifecycle"
    assert closure_actions["classify_task_queue_lifecycle_routes"]["status"] == "closed"


def test_trace_observability_surface_exposes_read_only_models() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    trace_surface = surfaces["trace_observability_read_models"]
    witnesses = set(trace_surface["runtime_witnesses"])
    route_records = {
        record["route"]: record
        for record in matrix["route_coverage"]["routes"]
    }

    assert trace_surface["coverage_state"] == "witnessed"
    assert trace_surface["request_proof"] == "read_model"
    assert trace_surface["action_proof"] == "read_model"
    assert "/api/v1/traces" in trace_surface["representative_paths"]
    assert "/api/v1/traces/slow" in trace_surface["representative_paths"]
    assert "/api/v1/traces/summary" in trace_surface["representative_paths"]
    assert "/api/v1/traces/{trace_id}" in trace_surface["representative_paths"]
    assert "mcoi/mcoi_runtime/app/routers/agent.py" in trace_surface["evidence_files"]
    assert "mcoi/mcoi_runtime/app/routers/ops/summaries.py" in trace_surface["evidence_files"]
    assert "mcoi/mcoi_runtime/core/request_tracing.py" in trace_surface["evidence_files"]
    assert "mcoi/tests/test_request_tracing.py" in trace_surface["evidence_files"]
    assert "request_trace_summary_bounded" in witnesses
    assert "missing_trace_returns_governed_404" in witnesses
    assert "slow_trace_projection_bounded" in witnesses
    assert "otel_trace_summary_bounded" in witnesses
    assert route_records["/api/v1/traces"]["coverage_state"] == "witnessed"
    assert route_records["/api/v1/traces"]["surface_id"] == "trace_observability_read_models"
    assert route_records["/api/v1/traces/summary"]["coverage_state"] == "witnessed"
    assert route_records["/api/v1/traces/summary"]["surface_id"] == "trace_observability_read_models"
    assert closure_actions["classify_trace_observability_routes"]["status"] == "closed"


def test_agent_memory_lifecycle_surface_is_proven() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    memory_surface = surfaces["agent_memory_lifecycle"]
    witnesses = set(memory_surface["runtime_witnesses"])
    route_records = {
        record["route"]: record
        for record in matrix["route_coverage"]["routes"]
    }

    assert memory_surface["coverage_state"] == "proven"
    assert memory_surface["request_proof"] == "request_proof"
    assert memory_surface["action_proof"] == "action_proof"
    assert "/api/v1/memory/store" in memory_surface["representative_paths"]
    assert "/api/v1/memory/search" in memory_surface["representative_paths"]
    assert "/api/v1/memory/summary" in memory_surface["representative_paths"]
    assert "mcoi/mcoi_runtime/app/routers/agent.py" in memory_surface["evidence_files"]
    assert "mcoi/mcoi_runtime/core/agent_memory.py" in memory_surface["evidence_files"]
    assert "mcoi/tests/test_agent_memory.py" in memory_surface["evidence_files"]
    assert "agent_memory_store_bounded" in witnesses
    assert "agent_memory_search_relevance_scored" in witnesses
    assert "agent_memory_tenant_isolation" in witnesses
    assert "agent_memory_capacity_eviction" in witnesses
    assert route_records["/api/v1/memory/store"]["coverage_state"] == "proven"
    assert route_records["/api/v1/memory/store"]["surface_id"] == "agent_memory_lifecycle"
    assert route_records["/api/v1/memory/summary"]["coverage_state"] == "proven"
    assert route_records["/api/v1/memory/summary"]["surface_id"] == "agent_memory_lifecycle"
    assert closure_actions["classify_agent_memory_lifecycle_routes"]["status"] == "closed"


def test_governance_explanation_lifecycle_surface_is_witnessed() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    explanation_surface = surfaces["governance_explanation_lifecycle"]
    witnesses = set(explanation_surface["runtime_witnesses"])
    route_records = {
        record["route"]: record
        for record in matrix["route_coverage"]["routes"]
    }

    assert explanation_surface["coverage_state"] == "witnessed"
    assert explanation_surface["request_proof"] == "request_proof"
    assert explanation_surface["action_proof"] == "action_proof"
    assert "/api/v1/explain/action" in explanation_surface["representative_paths"]
    assert "/api/v1/explain/audit/{entry_index}" in explanation_surface["representative_paths"]
    assert "/api/v1/explain/summary" in explanation_surface["representative_paths"]
    assert "mcoi/mcoi_runtime/app/routers/explain.py" in explanation_surface["evidence_files"]
    assert "mcoi/mcoi_runtime/core/explanation_engine.py" in explanation_surface["evidence_files"]
    assert "mcoi/tests/test_explanation_engine.py" in explanation_surface["evidence_files"]
    assert "explain_action_guard_chain_path_reported" in witnesses
    assert "explain_action_returns_explanation_id" in witnesses
    assert "explain_audit_entry_allowed_and_denied" in witnesses
    assert "explanation_cache_bounded" in witnesses
    assert "explain_summary_endpoint_governed" in witnesses
    assert route_records["/api/v1/explain/action"]["coverage_state"] == "witnessed"
    assert route_records["/api/v1/explain/action"]["surface_id"] == "governance_explanation_lifecycle"
    assert route_records["/api/v1/explain/summary"]["coverage_state"] == "witnessed"
    assert route_records["/api/v1/explain/summary"]["surface_id"] == "governance_explanation_lifecycle"
    assert closure_actions["classify_governance_explanation_lifecycle_routes"]["status"] == "closed"


def test_tool_registry_read_model_surface_keeps_invocation_separate() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    tool_surface = surfaces["tool_registry_read_models"]
    witnesses = set(tool_surface["runtime_witnesses"])
    route_records = {
        record["route"]: record
        for record in matrix["route_coverage"]["routes"]
    }

    assert tool_surface["coverage_state"] == "proven"
    assert tool_surface["request_proof"] == "read_model"
    assert tool_surface["action_proof"] == "read_model"
    assert "/api/v1/tools" in tool_surface["representative_paths"]
    assert "/api/v1/tools/history" in tool_surface["representative_paths"]
    assert "/api/v1/tools/llm-format" in tool_surface["representative_paths"]
    assert "/api/v1/tools/invoke" not in tool_surface["representative_paths"]
    assert "mcoi/mcoi_runtime/app/routers/data/tools.py" in tool_surface["evidence_files"]
    assert "mcoi/mcoi_runtime/core/tool_use.py" in tool_surface["evidence_files"]
    assert "mcoi/tests/test_server_phase212.py" in tool_surface["evidence_files"]
    assert "mcoi/tests/test_tool_registry_read_models.py" in tool_surface["evidence_files"]
    assert "tool_registry_list_returns_registered_tools" in witnesses
    assert "tool_registry_category_filter_bounded" in witnesses
    assert "tool_llm_format_exports_input_schema" in witnesses
    assert "tool_history_returns_bounded_summary" in witnesses
    assert "tool_invocation_history_limit_applied" in witnesses
    assert "tool_invoke_separate_action_proof_surface" in witnesses
    assert route_records["/api/v1/tools"]["surface_id"] == "tool_registry_read_models"
    assert route_records["/api/v1/tools/history"]["coverage_state"] == "proven"
    assert route_records["/api/v1/tools/llm-format"]["surface_id"] == "tool_registry_read_models"
    assert route_records["/api/v1/tools/invoke"]["surface_id"] == "tool_invocation"
    assert closure_actions["classify_tool_registry_read_model_routes"]["status"] == "closed"


def test_tool_invocation_surface_anchors_rejected_path_receipts() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    tool_surface = surfaces["tool_invocation"]
    witnesses = set(tool_surface["runtime_witnesses"])

    assert tool_surface["coverage_state"] == "proven"
    assert "mcoi/mcoi_runtime/core/governed_tool_gateway.py" in tool_surface["evidence_files"]
    assert "mcoi/mcoi_runtime/core/governed_tool_use.py" in tool_surface["evidence_files"]
    assert "mcoi/mcoi_runtime/governance/audit/rejected_path_records.py" in tool_surface["evidence_files"]
    assert "mcoi/tests/test_governed_tool_gateway.py" in tool_surface["evidence_files"]
    assert "mcoi/tests/test_governed_tool_use.py" in tool_surface["evidence_files"]
    assert "gateway_records_denied_tool_in_rejected_path_recorder" in witnesses
    assert "blocked_tool_decision_records_rejected_path_receipt" in witnesses
    assert "rejected_path_recorder_can_be_bound_after_registry_creation" in witnesses
    assert "rejected-path receipts" in tool_surface["notes"]


def test_operational_math_loop_surface_anchors_receipts_and_projection() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    math_surface = surfaces["operational_math_loop"]
    witnesses = set(math_surface["runtime_witnesses"])

    assert math_surface["coverage_state"] == "witnessed"
    assert math_surface["request_proof"] == "request_proof"
    assert math_surface["action_proof"] == "action_proof"
    assert "OperationalMathLoopEngine.apply_all" in math_surface["representative_paths"]
    assert "mcoi_runtime.app.operational_math_cli" in math_surface["representative_paths"]
    assert "OperationalMathReceiptStore" in math_surface["representative_paths"]
    assert "docs/operational_math_loop.md" in math_surface["evidence_files"]
    assert "mcoi/mcoi_runtime/contracts/operational_math.py" in math_surface["evidence_files"]
    assert "mcoi/mcoi_runtime/core/operational_math_loop.py" in math_surface["evidence_files"]
    assert "mcoi/mcoi_runtime/persistence/operational_math_receipt_store.py" in math_surface["evidence_files"]
    assert "mcoi/mcoi_runtime/app/operational_math_cli.py" in math_surface["evidence_files"]
    assert "mcoi/mcoi_runtime/app/operational_math_observability.py" in math_surface["evidence_files"]
    assert "mcoi/mcoi_runtime/app/server.py" in math_surface["evidence_files"]
    assert "mcoi/tests/test_operational_math_loop.py" in math_surface["evidence_files"]
    assert "mcoi/tests/test_operational_math_cli.py" in math_surface["evidence_files"]
    assert "mcoi/tests/test_operational_math_receipt_store.py" in math_surface["evidence_files"]
    assert "mcoi/tests/test_operational_math_observability.py" in math_surface["evidence_files"]
    assert "operational_math_loop_applies_all_audit_principles" in witnesses
    assert "operational_math_loop_stops_at_iteration_budget_with_open_gaps" in witnesses
    assert "operational_math_loop_blocks_solvedverified_without_control_binding" in witnesses
    assert "operational_math_loop_blocks_solvedverified_with_failed_control_binding" in witnesses
    assert "operational_math_cli_writes_dashboard_projection" in witnesses
    assert "operational_math_cli_appends_receipt_store" in witnesses
    assert "memory_store_appends_queries_and_summarizes_receipts" in witnesses
    assert "memory_store_surfaces_unverified_control_review_reason" in witnesses
    assert "file_store_persists_and_reloads_receipts" in witnesses
    assert "server_wires_operational_math_store_into_dashboard" in witnesses
    assert "summary_marks_incomplete_receipt_for_review" in witnesses
    assert "summary_marks_unverified_controls_for_review" in witnesses
    assert "append-only JSON receipt stores" in math_surface["notes"]
    assert closure_actions["anchor_operational_math_loop_receipts_and_projection"]["status"] == "closed"


def test_snet_episode_replay_surface_binds_deterministic_receipt_replay() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    witness_surfaces = {
        surface["surface_id"]: surface
        for surface in matrix["witness_integrity"]["surfaces"]
    }
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    replay_surface = surfaces["snet_episode_replay"]
    replay_integrity = witness_surfaces["snet_episode_replay"]
    witnesses = set(replay_surface["runtime_witnesses"])

    assert replay_surface["coverage_state"] == "witnessed"
    assert replay_surface["request_proof"] == "request_proof"
    assert replay_surface["action_proof"] == "action_proof"
    assert replay_surface["audit"] == "audit_chain"
    assert "scripts.validate_snet_episode_replay.validate_contract" in replay_surface["representative_paths"]
    assert "scripts.validate_snet_episode_replay.validate_episode" in replay_surface["representative_paths"]
    assert "scripts.validate_snet_episode_replay.replay_episode" in replay_surface["representative_paths"]
    assert "examples/snet_episode_seed_dependency.json" in replay_surface["representative_paths"]
    assert "schemas/snet_episode.schema.json" in replay_surface["evidence_files"]
    assert "schemas/snet_mesh_receipt.schema.json" in replay_surface["evidence_files"]
    assert "scripts/validate_snet_episode_replay.py" in replay_surface["evidence_files"]
    assert "scripts/validate_snet_mesh_receipt.py" in replay_surface["evidence_files"]
    assert "examples/snet_episode_seed_dependency.json" in replay_surface["evidence_files"]
    assert "tests/test_validate_snet_episode_replay.py" in replay_surface["evidence_files"]
    assert "snet_episode_replay_contract_passes" in witnesses
    assert "snet_episode_replay_is_deterministic" in witnesses
    assert "snet_episode_rejects_answer_drift" in witnesses
    assert "snet_episode_rejects_authority_and_raw_field_mutations" in witnesses
    assert "snet_episode_rejects_expected_count_drift" in witnesses
    assert "snet_episode_malformed_answer_bindings_report_errors" in witnesses
    assert "snet_episode_non_json_replay_inputs_report_errors" in witnesses
    assert "snet_episode_malformed_expected_receipt_report_errors" in witnesses
    assert "snet_episode_malformed_root_reports_errors" in witnesses
    assert "snet_episode_saved_file_validation" in witnesses
    assert "committed_snet_episode_example_replays_to_expected_receipt" in witnesses
    assert "read-only SNet mesh evidence" in replay_surface["notes"]
    assert replay_integrity["exact_test_anchor_count"] == 11
    assert replay_integrity["unanchored_witness_count"] == 0
    assert closure_actions["publish_snet_episode_replay_contract"]["status"] == "closed"


def test_snet_operator_read_model_surface_binds_no_authority_projection() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    witness_surfaces = {
        surface["surface_id"]: surface
        for surface in matrix["witness_integrity"]["surfaces"]
    }
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    read_model_surface = surfaces["snet_operator_read_model"]
    read_model_integrity = witness_surfaces["snet_operator_read_model"]
    witnesses = set(read_model_surface["runtime_witnesses"])

    assert read_model_surface["coverage_state"] == "witnessed"
    assert read_model_surface["request_proof"] == "read_model"
    assert read_model_surface["action_proof"] == "read_model"
    assert read_model_surface["audit"] == "audit_chain"
    assert "build_snet_operator_read_model" in read_model_surface["representative_paths"]
    assert "scripts.validate_snet_operator_read_model.validate_contract" in read_model_surface["representative_paths"]
    assert "scripts.validate_snet_operator_read_model.validate_read_model" in read_model_surface["representative_paths"]
    assert "examples/snet_operator_read_model.json" in read_model_surface["representative_paths"]
    assert "docs/73_snet_operator_read_model.md" in read_model_surface["representative_paths"]
    assert "docs/73_snet_operator_read_model.md" in read_model_surface["evidence_files"]
    assert "docs/START_HERE.md" in read_model_surface["evidence_files"]
    assert "mcoi/mcoi_runtime/snet/read_model.py" in read_model_surface["evidence_files"]
    assert "schemas/snet_operator_read_model.schema.json" in read_model_surface["evidence_files"]
    assert "schemas/snet_mesh_receipt.schema.json" in read_model_surface["evidence_files"]
    assert "scripts/validate_snet_operator_read_model.py" in read_model_surface["evidence_files"]
    assert "scripts/validate_snet_mesh_receipt.py" in read_model_surface["evidence_files"]
    assert "examples/snet_operator_read_model.json" in read_model_surface["evidence_files"]
    assert "tests/test_validate_snet_operator_read_model.py" in read_model_surface["evidence_files"]
    assert "tests/test_validate_snet_mesh_receipt.py" in read_model_surface["evidence_files"]
    assert "tests/test_snet_operator_read_model_doc.py" in read_model_surface["evidence_files"]
    assert "snet_operator_read_model_contract_passes" in witnesses
    assert "snet_operator_read_model_rejects_raw_and_authority_mutations" in witnesses
    assert "snet_operator_read_model_rejects_count_drift" in witnesses
    assert "snet_operator_read_model_rejects_symbol_raw_field" in witnesses
    assert "snet_operator_read_model_zero_symbol_projection_is_valid" in witnesses
    assert "snet_operator_read_model_malformed_root_reports_errors" in witnesses
    assert "snet_operator_read_model_non_integer_truncation_reports_errors" in witnesses
    assert "snet_mesh_receipt_contract_passes" in witnesses
    assert "snet_mesh_receipt_rejects_raw_answer_and_authority_mutations" in witnesses
    assert "snet_mesh_receipt_saved_file_validation" in witnesses
    assert "snet_mesh_receipt_rejects_settlement_count_drift" in witnesses
    assert "snet_mesh_receipt_requires_digest_evidence_ref" in witnesses
    assert "snet_mesh_receipt_non_string_evidence_ref_reports_errors" in witnesses
    assert "snet_mesh_receipt_malformed_payload_reports_errors" in witnesses
    assert "snet_mesh_receipt_rejects_identity_drift" in witnesses
    assert "snet_operator_doc_declares_read_only_boundary" in witnesses
    assert "snet_operator_doc_names_blocked_authorities" in witnesses
    assert "snet_operator_doc_lists_verification_commands" in witnesses
    assert "start_here_links_snet_operator_doc" in witnesses
    assert "denied execution, connector, filesystem, gateway" in read_model_surface["notes"]
    assert "terminal-closure authority" in read_model_surface["notes"]
    assert read_model_integrity["exact_test_anchor_count"] == 25
    assert read_model_integrity["unanchored_witness_count"] == 0
    assert closure_actions["publish_snet_operator_read_model_contract"]["status"] == "closed"


def test_agentic_service_harness_read_model_surface_binds_planning_only_projection() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    witness_surfaces = {
        surface["surface_id"]: surface
        for surface in matrix["witness_integrity"]["surfaces"]
    }
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    read_model_surface = surfaces["agentic_service_harness_read_models"]
    read_model_integrity = witness_surfaces["agentic_service_harness_read_models"]
    witnesses = set(read_model_surface["runtime_witnesses"])

    assert read_model_surface["request_proof"] == "read_model"
    assert read_model_surface["action_proof"] == "read_model"
    assert read_model_surface["audit"] == "audit_chain"
    assert read_model_surface["coverage_state"] == "witnessed"
    assert (
        "scripts.validate_agentic_service_harness_read_model_binding_plan.validate_read_model_binding_plan"
        in read_model_surface["representative_paths"]
    )
    assert (
        "scripts.validate_agentic_service_harness_read_models.validate_agentic_service_harness_read_models"
        in read_model_surface["representative_paths"]
    )
    assert (
        "scripts.validate_agentic_service_harness_read_model_projections.project_contract_to_read_model"
        in read_model_surface["representative_paths"]
    )
    assert (
        "scripts.validate_agentic_service_harness_read_model_integrity.validate_agentic_service_harness_read_model_integrity"
        in read_model_surface["representative_paths"]
    )
    assert "MULLUSI_AGENTIC_SERVICE_HARNESS_READ_MODEL_BINDING_PLAN.md" in read_model_surface["evidence_files"]
    assert "schemas/agentic_service_harness_read_models.schema.json" in read_model_surface["evidence_files"]
    assert "scripts/validate_agentic_service_harness_read_models.py" in read_model_surface["evidence_files"]
    assert "scripts/validate_agentic_service_harness_read_model_projections.py" in read_model_surface["evidence_files"]
    assert "scripts/validate_agentic_service_harness_read_model_integrity.py" in read_model_surface["evidence_files"]
    assert "tests/test_validate_agentic_service_harness_read_models.py" in read_model_surface["evidence_files"]
    assert "harness_read_model_binding_plan_is_planning_only" in witnesses
    assert "harness_read_model_rejects_mutation_and_secret_surfaces" in witnesses
    assert "harness_read_model_blocks_terminal_closure_claims" in witnesses
    assert "harness_read_model_projection_covers_contract_scenarios" in witnesses
    assert "harness_read_model_integrity_rejects_identity_drift" in witnesses
    assert "harness_read_model_validators_emit_strict_receipts" in witnesses
    assert "planning-only, read-only" in read_model_surface["notes"]
    assert "high-risk authority are admitted" in read_model_surface["notes"]
    assert read_model_integrity["exact_test_anchor_count"] == 12
    assert read_model_integrity["unanchored_witness_count"] == 0
    assert (
        closure_actions["publish_agentic_service_harness_read_model_contract"]["status"]
        == "closed"
    )


def test_agentic_service_harness_authority_surface_binds_blocked_effect_transitions() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    witness_surfaces = {
        surface["surface_id"]: surface
        for surface in matrix["witness_integrity"]["surfaces"]
    }
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    authority_surface = surfaces["agentic_service_harness_authority_transitions"]
    authority_integrity = witness_surfaces["agentic_service_harness_authority_transitions"]
    witnesses = set(authority_surface["runtime_witnesses"])

    assert authority_surface["request_proof"] == "request_proof"
    assert authority_surface["action_proof"] == "action_proof"
    assert authority_surface["audit"] == "audit_chain"
    assert authority_surface["coverage_state"] == "witnessed"
    assert (
        "scripts.validate_agentic_service_harness_contract.validate_agentic_service_harness_contract"
        in authority_surface["representative_paths"]
    )
    assert (
        "scripts.validate_agentic_service_harness_authority_transitions.validate_agentic_service_harness_authority_transitions"
        in authority_surface["representative_paths"]
    )
    assert "schemas/agentic_service_harness.schema.json" in authority_surface["evidence_files"]
    assert "scripts/validate_agentic_service_harness_authority_transitions.py" in authority_surface["evidence_files"]
    assert "examples/agentic_service_harness.branch_write_awaiting_approval.json" in authority_surface["evidence_files"]
    assert "examples/agentic_service_harness.open_pr_awaiting_approval.json" in authority_surface["evidence_files"]
    assert "examples/agentic_service_harness.blocked_high_risk.json" in authority_surface["evidence_files"]
    assert "tests/test_validate_agentic_service_harness_authority_transitions.py" in authority_surface["evidence_files"]
    assert "harness_authority_transitions_accept_default_fixtures" in witnesses
    assert "harness_authority_rejects_approved_branch_gate" in witnesses
    assert "harness_authority_rejects_dry_run_file_change" in witnesses
    assert "harness_authority_rejects_open_pr_without_branch_evidence" in witnesses
    assert "harness_authority_rejects_incomplete_high_risk_block" in witnesses
    assert "harness_authority_validator_emits_strict_receipt" in witnesses
    assert "read-only and dry-run scenarios non-effectful" in authority_surface["notes"]
    assert "high-risk merge, deploy, DNS" in authority_surface["notes"]
    assert authority_integrity["exact_test_anchor_count"] == 6
    assert authority_integrity["unanchored_witness_count"] == 0
    assert (
        closure_actions["publish_agentic_service_harness_authority_transition_contract"]["status"]
        == "closed"
    )


def test_structured_output_validation_surface_is_witnessed() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    output_surface = surfaces["structured_output_validation"]
    witnesses = set(output_surface["runtime_witnesses"])
    route_records = {
        record["route"]: record
        for record in matrix["route_coverage"]["routes"]
    }

    assert output_surface["coverage_state"] == "proven"
    assert output_surface["request_proof"] == "request_proof"
    assert output_surface["action_proof"] == "action_proof"
    assert "/api/v1/output/parse" in output_surface["representative_paths"]
    assert "/api/v1/output/schemas" in output_surface["representative_paths"]
    assert "mcoi/mcoi_runtime/app/routers/data/output.py" in output_surface["evidence_files"]
    assert "mcoi/mcoi_runtime/core/structured_output.py" in output_surface["evidence_files"]
    assert "mcoi/tests/test_server_phase212.py" in output_surface["evidence_files"]
    assert "mcoi/tests/test_structured_output.py" in output_surface["evidence_files"]
    assert "structured_output_parse_valid_json" in witnesses
    assert "structured_output_parse_invalid_json" in witnesses
    assert "structured_output_parse_unknown_schema_bounded" in witnesses
    assert "structured_output_schema_registration_validated" in witnesses
    assert "structured_output_endpoint_parse_valid_and_invalid" in witnesses
    assert route_records["/api/v1/output/parse"]["coverage_state"] == "proven"
    assert route_records["/api/v1/output/parse"]["surface_id"] == "structured_output_validation"
    assert route_records["/api/v1/output/schemas"]["coverage_state"] == "proven"
    assert route_records["/api/v1/output/schemas"]["surface_id"] == "structured_output_validation"
    assert closure_actions["classify_structured_output_validation_routes"]["status"] == "closed"


def test_rate_limit_read_model_surface_exposes_bounded_status_and_headers() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    rate_surface = surfaces["operational_platform_read_models"]
    witnesses = set(rate_surface["runtime_witnesses"])
    route_records = {
        record["route"]: record
        for record in matrix["route_coverage"]["routes"]
    }

    assert rate_surface["coverage_state"] == "witnessed"
    assert rate_surface["request_proof"] == "read_model"
    assert rate_surface["action_proof"] == "read_model"
    assert "/api/v1/rate-limit/status" in rate_surface["representative_paths"]
    assert "/api/v1/rate-limits/{client_id}" in rate_surface["representative_paths"]
    assert "mcoi/mcoi_runtime/app/routers/ops/rate_limit.py" in rate_surface["evidence_files"]
    assert "mcoi/mcoi_runtime/core/rate_limit_headers.py" in rate_surface["evidence_files"]
    assert "mcoi/mcoi_runtime/core/rate_limit_middleware.py" in rate_surface["evidence_files"]
    assert "mcoi/tests/test_rate_limiter.py" in rate_surface["evidence_files"]
    assert "mcoi/tests/test_server_phase202.py" in rate_surface["evidence_files"]
    assert "mcoi/tests/test_rate_limit_headers.py" in rate_surface["evidence_files"]
    assert "rate_limit_status" in witnesses
    assert "status" in witnesses
    assert "to_headers" in witnesses
    assert "peek_does_not_consume" in witnesses
    assert "consume_decrements" in witnesses
    assert route_records["/api/v1/rate-limit/status"]["coverage_state"] == "witnessed"
    assert route_records["/api/v1/rate-limit/status"]["surface_id"] == "operational_platform_read_models"
    assert route_records["/api/v1/rate-limits/{client_id}"]["coverage_state"] == "witnessed"
    assert route_records["/api/v1/rate-limits/{client_id}"]["surface_id"] == "operational_platform_read_models"
    assert closure_actions["classify_operational_platform_read_model_routes"]["status"] == "closed"


def test_feature_flag_read_model_surface_exposes_bounded_flag_checks() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    flag_surface = surfaces["operational_platform_read_models"]
    witnesses = set(flag_surface["runtime_witnesses"])
    route_records = {
        record["route"]: record
        for record in matrix["route_coverage"]["routes"]
    }

    assert flag_surface["coverage_state"] == "witnessed"
    assert flag_surface["request_proof"] == "read_model"
    assert flag_surface["action_proof"] == "read_model"
    assert "/api/v1/flags" in flag_surface["representative_paths"]
    assert "/api/v1/flags/{flag_id}" in flag_surface["representative_paths"]
    assert "mcoi/mcoi_runtime/app/routers/ops/feature_flags.py" in flag_surface["evidence_files"]
    assert "mcoi/mcoi_runtime/core/feature_flags.py" in flag_surface["evidence_files"]
    assert "mcoi/tests/test_server_phase220.py" in flag_surface["evidence_files"]
    assert "mcoi/tests/test_feature_flags.py" in flag_surface["evidence_files"]
    assert "list_flags" in witnesses
    assert "summary" in witnesses
    assert "check_flag_enabled" in witnesses
    assert "check_flag_unknown" in witnesses
    assert "tenant_override" in witnesses
    assert route_records["/api/v1/flags"]["coverage_state"] == "witnessed"
    assert route_records["/api/v1/flags"]["surface_id"] == "operational_platform_read_models"
    assert route_records["/api/v1/flags/{flag_id}"]["coverage_state"] == "witnessed"
    assert route_records["/api/v1/flags/{flag_id}"]["surface_id"] == "operational_platform_read_models"
    assert closure_actions["classify_operational_platform_read_model_routes"]["status"] == "closed"


def test_operational_health_surface_exposes_bounded_read_models() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    health_surface = surfaces["operational_health_read_models"]
    witnesses = set(health_surface["runtime_witnesses"])
    route_records = {
        record["route"]: record
        for record in matrix["route_coverage"]["routes"]
    }

    assert health_surface["coverage_state"] == "proven"
    assert health_surface["request_proof"] == "read_model"
    assert health_surface["action_proof"] == "read_model"
    assert "/api/v1/health/deep" in health_surface["representative_paths"]
    assert "/api/v1/health/score" in health_surface["representative_paths"]
    assert "/api/v1/health/extensions" in health_surface["representative_paths"]
    assert "/api/v1/health/shadow" in health_surface["representative_paths"]
    assert "/api/v1/health/v2" in health_surface["representative_paths"]
    assert "/api/v1/health/v3" in health_surface["representative_paths"]
    assert "/api/v1/readiness" in health_surface["representative_paths"]
    assert "/api/v1/spatial-map" in health_surface["representative_paths"]
    assert "/api/v1/deploy/readiness" in health_surface["representative_paths"]
    assert "/api/v1/release/latest" in health_surface["representative_paths"]
    assert "/api/v1/snapshot" in health_surface["representative_paths"]
    assert "/api/v1/cache/stats" in health_surface["representative_paths"]
    assert "mcoi/mcoi_runtime/app/routers/health.py" in health_surface["evidence_files"]
    assert "mcoi/mcoi_runtime/app/routers/shadow.py" in health_surface["evidence_files"]
    assert "mcoi/mcoi_runtime/app/routers/ops/summaries.py" in health_surface["evidence_files"]
    assert "mcoi/mcoi_runtime/app/routers/ops/release.py" in health_surface["evidence_files"]
    assert "mcoi/mcoi_runtime/app/routers/ops/snapshots.py" in health_surface["evidence_files"]
    assert "mcoi/mcoi_runtime/core/deep_health.py" in health_surface["evidence_files"]
    assert "mcoi/mcoi_runtime/core/health_aggregator.py" in health_surface["evidence_files"]
    assert "mcoi/mcoi_runtime/core/health_check_agg.py" in health_surface["evidence_files"]
    assert "mcoi/mcoi_runtime/core/health_v3.py" in health_surface["evidence_files"]
    assert "mcoi/mcoi_runtime/core/spatial_governance.py" in health_surface["evidence_files"]
    assert "mcoi/tests/test_deep_health.py" in health_surface["evidence_files"]
    assert "mcoi/tests/test_health_aggregator.py" in health_surface["evidence_files"]
    assert "mcoi/tests/test_health_check_agg.py" in health_surface["evidence_files"]
    assert "mcoi/tests/test_inceptadive_shadow_routes.py" in health_surface["evidence_files"]
    assert "mcoi/tests/test_operational_health_read_models.py" in health_surface["evidence_files"]
    assert "mcoi/tests/test_phase232.py" in health_surface["evidence_files"]
    assert "deep_health_components_bounded" in witnesses
    assert "health_score_range_bounded" in witnesses
    assert "extension_health_read_model_bounded" in witnesses
    assert "shadow_health_route_returns_redacted_read_model" in witnesses
    assert "shadow_routes_fallback_when_runtime_unregistered" in witnesses
    assert "shadow_routes_respect_disabled_runtime_posture" in witnesses
    assert "health_v2_degraded_state_supported" in witnesses
    assert "health_v2_exception_sanitized" in witnesses
    assert "health_v3_recovery_tracking" in witnesses
    assert "production_readiness_checks_bounded" in witnesses
    assert "spatial_map_read_model_bounded" in witnesses
    assert "spatial_path_missing_boundary_blocks_explicitly" in witnesses
    assert "deployment_readiness_read_model_bounded" in witnesses
    assert "release_info_read_model_bounded" in witnesses
    assert "system_snapshot_read_model_bounded" in witnesses
    assert route_records["/api/v1/health/deep"]["coverage_state"] == "proven"
    assert route_records["/api/v1/health/deep"]["surface_id"] == "operational_health_read_models"
    assert route_records["/api/v1/health/extensions"]["surface_id"] == "operational_health_read_models"
    assert route_records["/api/v1/health/shadow"]["surface_id"] == "operational_health_read_models"
    assert route_records["/api/v1/health/v3"]["coverage_state"] == "proven"
    assert route_records["/api/v1/health/v3"]["surface_id"] == "operational_health_read_models"
    assert route_records["/api/v1/readiness"]["surface_id"] == "operational_health_read_models"
    assert route_records["/api/v1/spatial-map"]["surface_id"] == "operational_health_read_models"
    assert route_records["/api/v1/release/latest"]["surface_id"] == "operational_health_read_models"
    assert closure_actions["classify_operational_health_read_model_routes"]["status"] == "closed"


def test_agent_orchestration_lifecycle_surface_tracks_plans_and_handoffs() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    orchestration_surface = surfaces["agent_orchestration_lifecycle"]
    witnesses = set(orchestration_surface["runtime_witnesses"])
    route_records = {
        record["route"]: record
        for record in matrix["route_coverage"]["routes"]
    }

    assert orchestration_surface["coverage_state"] == "witnessed"
    assert orchestration_surface["request_proof"] == "request_proof"
    assert orchestration_surface["action_proof"] == "action_proof"
    assert "/api/v1/orchestration" in orchestration_surface["representative_paths"]
    assert "/api/v1/orchestration/plans" in orchestration_surface["representative_paths"]
    assert "/api/v1/orchestration/plans/{plan_id}" in orchestration_surface["representative_paths"]
    assert "/api/v1/orchestration/handoff" in orchestration_surface["representative_paths"]
    assert "mcoi/mcoi_runtime/app/routers/agent.py" in orchestration_surface["evidence_files"]
    assert "mcoi/mcoi_runtime/core/agent_orchestration.py" in orchestration_surface["evidence_files"]
    assert "mcoi/tests/test_agent_orchestration.py" in orchestration_surface["evidence_files"]
    assert "mcoi/tests/test_server_phase216.py" in orchestration_surface["evidence_files"]
    assert "orchestration_summary_bounded" in witnesses
    assert "orchestration_plan_created_for_registered_agent" in witnesses
    assert "orchestration_missing_plan_bounded" in witnesses
    assert "orchestration_handoff_capability_checked" in witnesses
    assert "orchestration_quorum_required" in witnesses
    assert "orchestration_executor_errors_sanitized" in witnesses
    assert route_records["/api/v1/orchestration"]["coverage_state"] == "witnessed"
    assert route_records["/api/v1/orchestration"]["surface_id"] == "agent_orchestration_lifecycle"
    assert route_records["/api/v1/orchestration/plans/{plan_id}"]["coverage_state"] == "witnessed"
    assert route_records["/api/v1/orchestration/plans/{plan_id}"]["surface_id"] == "agent_orchestration_lifecycle"
    assert closure_actions["classify_agent_orchestration_lifecycle_routes"]["status"] == "closed"


def test_workflow_execution_lifecycle_surface_tracks_execution_history_and_tracing() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    workflow_surface = surfaces["workflow_execution_lifecycle"]
    witnesses = set(workflow_surface["runtime_witnesses"])
    route_records = {
        record["route"]: record
        for record in matrix["route_coverage"]["routes"]
    }

    assert workflow_surface["coverage_state"] == "proven"
    assert workflow_surface["request_proof"] == "request_proof"
    assert workflow_surface["action_proof"] == "action_proof"
    assert "/api/v1/workflow/execute" in workflow_surface["representative_paths"]
    assert "/api/v1/workflow/history" in workflow_surface["representative_paths"]
    assert "/api/v1/workflow/traced" in workflow_surface["representative_paths"]
    assert "/api/v1/execute" in workflow_surface["representative_paths"]
    assert "/api/v1/pipeline/execute" in workflow_surface["representative_paths"]
    assert "/api/v1/templates/execute" in workflow_surface["representative_paths"]
    assert "gateway/workflow_orchestration.py" in workflow_surface["evidence_files"]
    assert "mcoi/mcoi_runtime/app/routers/workflow.py" in workflow_surface["evidence_files"]
    assert "mcoi/mcoi_runtime/core/agent_workflow.py" in workflow_surface["evidence_files"]
    assert "mcoi/mcoi_runtime/core/traced_workflow.py" in workflow_surface["evidence_files"]
    assert "tests/test_gateway/test_workflow_orchestration.py" in workflow_surface["evidence_files"]
    assert "mcoi/tests/test_agent_workflow.py" in workflow_surface["evidence_files"]
    assert "mcoi/tests/test_traced_workflow.py" in workflow_surface["evidence_files"]
    assert "mcoi/tests/test_server_phase205.py" in workflow_surface["evidence_files"]
    assert "execute_workflow" in witnesses
    assert "execute_workflow_bad_capability" in witnesses
    assert "workflow_history" in witnesses
    assert "audit_on_success" in witnesses
    assert "audit_on_failure" in witnesses
    assert "workflow_runtime_error_redacted" in witnesses
    assert "workflow_lifecycle_records_bounded_mutation_receipts" in witnesses
    assert "workflow_failure_and_compensation_receipts_are_bounded" in witnesses
    assert "workflow_mutation_receipt_closes_effect_assurance" in witnesses
    assert "execute_produces_trace" in witnesses
    assert "start_trace_failure_is_counted_and_workflow_runs" in witnesses
    assert "complete_failure_is_counted_and_partial_trace_discarded" in witnesses
    assert "legacy_execute_uses_request_unique_trace_witness" in witnesses
    assert "create_session" in witnesses
    assert "ledger_returns_entries" in witnesses
    assert "execute_pipeline" in witnesses
    assert "pipeline_history" in witnesses
    assert "instantiate" in witnesses
    assert "list_by_category" in witnesses
    assert route_records["/api/v1/workflow/execute"]["coverage_state"] == "proven"
    assert route_records["/api/v1/workflow/execute"]["surface_id"] == "workflow_execution_lifecycle"
    assert route_records["/api/v1/workflow/traced"]["coverage_state"] == "proven"
    assert route_records["/api/v1/workflow/traced"]["surface_id"] == "workflow_execution_lifecycle"
    assert route_records["/api/v1/pipeline/execute"]["surface_id"] == "workflow_execution_lifecycle"
    assert route_records["/api/v1/templates/execute"]["surface_id"] == "workflow_execution_lifecycle"
    assert closure_actions["classify_workflow_execution_lifecycle_routes"]["status"] == "closed"
    assert closure_actions["bind_workflow_lifecycle_mutations_to_effect_receipts"]["status"] == "closed"


def test_agent_chain_execution_lifecycle_surface_tracks_execution_and_history() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    chain_surface = surfaces["agent_chain_execution_lifecycle"]
    witnesses = set(chain_surface["runtime_witnesses"])
    route_records = {
        record["route"]: record
        for record in matrix["route_coverage"]["routes"]
    }

    assert chain_surface["coverage_state"] == "proven"
    assert chain_surface["request_proof"] == "request_proof"
    assert chain_surface["action_proof"] == "action_proof"
    assert "/api/v1/chain/execute" in chain_surface["representative_paths"]
    assert "/api/v1/chain/history" in chain_surface["representative_paths"]
    assert "mcoi/mcoi_runtime/app/routers/agent.py" in chain_surface["evidence_files"]
    assert "mcoi/mcoi_runtime/core/agent_chain.py" in chain_surface["evidence_files"]
    assert "mcoi/tests/test_agent_chain.py" in chain_surface["evidence_files"]
    assert "mcoi/tests/test_server_phase215.py" in chain_surface["evidence_files"]
    assert "chain_execute_single_step" in witnesses
    assert "chain_execute_two_steps" in witnesses
    assert "chain_prev_template_propagates_output" in witnesses
    assert "chain_halt_on_failure_bounded" in witnesses
    assert "chain_skip_on_failure_continues" in witnesses
    assert "chain_returned_failure_redacted" in witnesses
    assert "chain_history_bounded" in witnesses
    assert route_records["/api/v1/chain/execute"]["coverage_state"] == "proven"
    assert route_records["/api/v1/chain/execute"]["surface_id"] == "agent_chain_execution_lifecycle"
    assert route_records["/api/v1/chain/history"]["coverage_state"] == "proven"
    assert route_records["/api/v1/chain/history"]["surface_id"] == "agent_chain_execution_lifecycle"
    assert closure_actions["classify_agent_chain_execution_routes"]["status"] == "closed"


def test_certification_daemon_lifecycle_surface_tracks_status_ticks_and_force_runs() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    daemon_surface = surfaces["certification_daemon_lifecycle"]
    witnesses = set(daemon_surface["runtime_witnesses"])
    route_records = {
        record["route"]: record
        for record in matrix["route_coverage"]["routes"]
    }

    assert daemon_surface["coverage_state"] == "proven"
    assert daemon_surface["request_proof"] == "request_proof"
    assert daemon_surface["action_proof"] == "action_proof"
    assert "/api/v1/daemon/status" in daemon_surface["representative_paths"]
    assert "/api/v1/daemon/tick" in daemon_surface["representative_paths"]
    assert "/api/v1/daemon/force" in daemon_surface["representative_paths"]
    assert "mcoi/mcoi_runtime/app/routers/data/daemon.py" in daemon_surface["evidence_files"]
    assert "mcoi/mcoi_runtime/core/certification_daemon.py" in daemon_surface["evidence_files"]
    assert "mcoi/tests/test_certification_daemon.py" in daemon_surface["evidence_files"]
    assert "mcoi/tests/test_server_phase200.py" in daemon_surface["evidence_files"]
    assert "daemon_status_bounded" in witnesses
    assert "daemon_tick_interval_gated" in witnesses
    assert "daemon_force_runs_when_disabled" in witnesses
    assert "daemon_force_returns_chain_hash" in witnesses
    assert "daemon_history_bounded" in witnesses
    assert "daemon_exceptions_sanitized" in witnesses
    assert route_records["/api/v1/daemon/status"]["coverage_state"] == "proven"
    assert route_records["/api/v1/daemon/status"]["surface_id"] == "certification_daemon_lifecycle"
    assert route_records["/api/v1/daemon/force"]["coverage_state"] == "proven"
    assert route_records["/api/v1/daemon/force"]["surface_id"] == "certification_daemon_lifecycle"
    assert closure_actions["classify_certification_daemon_lifecycle_routes"]["status"] == "closed"


def test_live_path_certification_lifecycle_surface_tracks_runs_and_history() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    certification_surface = surfaces["live_path_certification_lifecycle"]
    witnesses = set(certification_surface["runtime_witnesses"])
    route_records = {
        record["route"]: record
        for record in matrix["route_coverage"]["routes"]
    }

    assert certification_surface["coverage_state"] == "proven"
    assert certification_surface["request_proof"] == "request_proof"
    assert certification_surface["action_proof"] == "action_proof"
    assert "/api/v1/certify" in certification_surface["representative_paths"]
    assert "/api/v1/certify/history" in certification_surface["representative_paths"]
    assert "mcoi/mcoi_runtime/app/routers/data/certify.py" in certification_surface["evidence_files"]
    assert "mcoi/mcoi_runtime/core/live_path_certification.py" in certification_surface["evidence_files"]
    assert "mcoi/tests/test_live_path_certification.py" in certification_surface["evidence_files"]
    assert "mcoi/tests/test_server_phase199.py" in certification_surface["evidence_files"]
    assert "certification_run_emits_action_proof" in witnesses
    assert "certification_run_returns_chain_hash" in witnesses
    assert "certification_run_records_five_steps" in witnesses
    assert "certification_steps_named" in witnesses
    assert "certification_history_bounded" in witnesses
    assert "certification_chain_hash_deterministic" in witnesses
    assert "certification_failures_bounded" in witnesses
    assert route_records["/api/v1/certify"]["coverage_state"] == "proven"
    assert route_records["/api/v1/certify"]["surface_id"] == "live_path_certification_lifecycle"
    assert route_records["/api/v1/certify/history"]["coverage_state"] == "proven"
    assert route_records["/api/v1/certify/history"]["surface_id"] == "live_path_certification_lifecycle"
    assert closure_actions["classify_live_path_certification_routes"]["status"] == "closed"


def test_runtime_state_persistence_lifecycle_surface_tracks_save_load_and_list() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    state_surface = surfaces["runtime_state_persistence_lifecycle"]
    witnesses = set(state_surface["runtime_witnesses"])
    route_records = {
        record["route"]: record
        for record in matrix["route_coverage"]["routes"]
    }

    assert state_surface["coverage_state"] == "witnessed"
    assert state_surface["request_proof"] == "request_proof"
    assert state_surface["action_proof"] == "action_proof"
    assert "/api/v1/state" in state_surface["representative_paths"]
    assert "/api/v1/state/save" in state_surface["representative_paths"]
    assert "/api/v1/state/{state_type}" in state_surface["representative_paths"]
    assert "mcoi/mcoi_runtime/app/routers/data/state.py" in state_surface["evidence_files"]
    assert "mcoi/mcoi_runtime/persistence/state_persistence.py" in state_surface["evidence_files"]
    assert "mcoi/tests/test_state_persistence.py" in state_surface["evidence_files"]
    assert "mcoi/tests/test_server_phase212.py" in state_surface["evidence_files"]
    assert "state_save_returns_hash_bound_snapshot" in witnesses
    assert "state_load_roundtrip" in witnesses
    assert "state_load_missing_bounded" in witnesses
    assert "state_list_summary_bounded" in witnesses
    assert "state_save_rejects_path_traversal" in witnesses
    assert "state_load_rejects_path_traversal" in witnesses
    assert "state_hash_mismatch_rejected" in witnesses
    assert route_records["/api/v1/state"]["coverage_state"] == "witnessed"
    assert route_records["/api/v1/state"]["surface_id"] == "runtime_state_persistence_lifecycle"
    assert route_records["/api/v1/state/save"]["coverage_state"] == "witnessed"
    assert route_records["/api/v1/state/save"]["surface_id"] == "runtime_state_persistence_lifecycle"
    assert route_records["/api/v1/state/{state_type}"]["coverage_state"] == "witnessed"
    assert route_records["/api/v1/state/{state_type}"]["surface_id"] == "runtime_state_persistence_lifecycle"
    assert closure_actions["classify_runtime_state_persistence_routes"]["status"] == "closed"


def test_connector_self_healing_surface_emits_bounded_recovery_receipts() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    witness_surfaces = {
        surface["surface_id"]: surface
        for surface in matrix["witness_integrity"]["surfaces"]
    }
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    healing_surface = surfaces["connector_self_healing"]
    healing_witness_surface = witness_surfaces["connector_self_healing"]
    witnesses = set(healing_surface["runtime_witnesses"])

    assert healing_surface["coverage_state"] == "witnessed"
    assert healing_surface["request_proof"] == "request_proof"
    assert healing_surface["action_proof"] == "action_proof"
    assert "ConnectorSelfHealingEngine.evaluate" in healing_surface["representative_paths"]
    assert "gateway/connector_self_healing.py" in healing_surface["evidence_files"]
    assert "schemas/connector_self_healing_receipt.schema.json" in healing_surface["evidence_files"]
    assert "tests/test_gateway/test_connector_self_healing.py" in healing_surface["evidence_files"]
    assert "provider_success_not_assumed" in witnesses
    assert "write_failures_require_operator_review" in witnesses
    assert "missing_receipt_revokes_capability" in witnesses
    assert "connector_self_healing_schema_valid" in witnesses
    assert healing_witness_surface["exact_test_anchor_count"] == 6
    assert healing_witness_surface["unanchored_witness_count"] == 0
    assert closure_actions["publish_connector_self_healing_receipt_contract"]["status"] == "closed"


def test_connector_action_promotion_gate_blocks_live_authority() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    witness_surfaces = {
        surface["surface_id"]: surface
        for surface in matrix["witness_integrity"]["surfaces"]
    }
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    gate_surface = surfaces["connector_action_promotion_gate"]
    gate_witness_surface = witness_surfaces["connector_action_promotion_gate"]
    witnesses = set(gate_surface["runtime_witnesses"])

    assert gate_surface["coverage_state"] == "witnessed"
    assert gate_surface["request_proof"] == "request_proof"
    assert gate_surface["action_proof"] == "action_proof"
    assert "ConnectorActionPromotionGate" in gate_surface["representative_paths"]
    assert "schemas/connector_action_promotion_gate.schema.json" in gate_surface["evidence_files"]
    assert "examples/connector_action_promotion_gate.foundation.json" in gate_surface["evidence_files"]
    assert "scripts/validate_connector_action_promotion_gate.py" in gate_surface["evidence_files"]
    assert "tests/test_validate_connector_action_promotion_gate.py" in gate_surface["evidence_files"]
    assert "connector_action_promotion_gate_schema_valid" in witnesses
    assert "connector_action_promotion_gate_blocks_live_calls" in witnesses
    assert "connector_action_promotion_gate_binds_source_fixtures" in witnesses
    assert "connector_action_promotion_gate_rejects_authority_drift" in witnesses
    assert gate_witness_surface["exact_test_anchor_count"] == 6
    assert gate_witness_surface["unanchored_witness_count"] == 0
    assert closure_actions["publish_connector_action_promotion_gate_contract"]["status"] == "closed"


def test_readiness_waiver_review_packet_blocks_readiness_authority() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    witness_surfaces = {
        surface["surface_id"]: surface
        for surface in matrix["witness_integrity"]["surfaces"]
    }
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    packet_surface = surfaces["readiness_waiver_review_packet"]
    packet_witness_surface = witness_surfaces["readiness_waiver_review_packet"]
    witnesses = set(packet_surface["runtime_witnesses"])

    assert packet_surface["coverage_state"] == "witnessed"
    assert packet_surface["request_proof"] == "request_proof"
    assert packet_surface["action_proof"] == "action_proof"
    assert "ReadinessWaiverReviewPacket" in packet_surface["representative_paths"]
    assert "schemas/readiness_waiver_review_packet.schema.json" in packet_surface["evidence_files"]
    assert "examples/readiness_waiver_review_packet.foundation.json" in packet_surface["evidence_files"]
    assert "scripts/validate_readiness_waiver_review_packet.py" in packet_surface["evidence_files"]
    assert "tests/test_validate_readiness_waiver_review_packet.py" in packet_surface["evidence_files"]
    assert "readiness_waiver_review_packet_schema_valid" in witnesses
    assert "readiness_waiver_review_packet_blocks_readiness_authority" in witnesses
    assert "readiness_waiver_review_packet_requires_evidence_refs" in witnesses
    assert "readiness_waiver_review_packet_rejects_expiry_drift" in witnesses
    assert packet_witness_surface["exact_test_anchor_count"] == 6
    assert packet_witness_surface["unanchored_witness_count"] == 0
    assert closure_actions["publish_readiness_waiver_review_packet_contract"]["status"] == "closed"


def test_browser_observation_receipt_blocks_browser_authority() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    witness_surfaces = {
        surface["surface_id"]: surface
        for surface in matrix["witness_integrity"]["surfaces"]
    }
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}

    browser_surface = surfaces["browser_observation_receipt"]
    browser_witness_surface = witness_surfaces["browser_observation_receipt"]
    witnesses = set(browser_surface["runtime_witnesses"])

    assert browser_surface["coverage_state"] == "witnessed"
    assert browser_surface["request_proof"] == "request_proof"
    assert browser_surface["action_proof"] == "action_proof"
    assert browser_surface["audit"] == "audit_chain"
    assert "schemas/browser_observation_receipt.schema.json" in browser_surface["evidence_files"]
    assert "examples/browser_observation_receipt.foundation.json" in browser_surface["evidence_files"]
    assert "scripts/validate_browser_observation_receipt.py" in browser_surface["evidence_files"]
    assert "tests/test_validate_browser_observation_receipt.py" in browser_surface["evidence_files"]
    assert "browser_observation_receipt_schema_valid" in witnesses
    assert "browser_observation_receipt_blocks_browser_authority" in witnesses
    assert "browser_observation_receipt_requires_digest_refs" in witnesses
    assert "browser_observation_receipt_rejects_raw_storage" in witnesses
    assert browser_witness_surface["exact_test_anchor_count"] == 5
    assert browser_witness_surface["unanchored_witness_count"] == 0
    assert closure_actions["publish_browser_observation_receipt_contract"]["status"] == "closed"


def test_trusted_capture_evidence_packet_blocks_capture_authority() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    witness_surfaces = {
        surface["surface_id"]: surface
        for surface in matrix["witness_integrity"]["surfaces"]
    }
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}

    capture_surface = surfaces["trusted_capture_evidence_packet"]
    capture_witness_surface = witness_surfaces["trusted_capture_evidence_packet"]
    witnesses = set(capture_surface["runtime_witnesses"])

    assert capture_surface["coverage_state"] == "witnessed"
    assert capture_surface["request_proof"] == "request_proof"
    assert capture_surface["action_proof"] == "action_proof"
    assert capture_surface["audit"] == "audit_chain"
    assert "TrustedCaptureEvidencePacket" in capture_surface["representative_paths"]
    assert "schemas/trusted_capture_evidence_packet.schema.json" in capture_surface["evidence_files"]
    assert "examples/trusted_capture_evidence_packet.foundation.json" in capture_surface["evidence_files"]
    assert "scripts/validate_trusted_capture_evidence_packet.py" in capture_surface["evidence_files"]
    assert "tests/test_validate_trusted_capture_evidence_packet.py" in capture_surface["evidence_files"]
    assert "trusted_capture_evidence_packet_schema_valid" in witnesses
    assert "trusted_capture_evidence_packet_blocks_capture_authority" in witnesses
    assert "trusted_capture_evidence_packet_requires_digest_refs" in witnesses
    assert "trusted_capture_evidence_packet_rejects_raw_media_retention" in witnesses
    assert "trusted_capture_evidence_packet_rejects_receipt_ref_and_count_drift" in witnesses
    assert "trusted_capture_evidence_packet_sdlc_artifacts_valid" in witnesses
    assert capture_witness_surface["exact_test_anchor_count"] == 6
    assert capture_witness_surface["unanchored_witness_count"] == 0
    assert closure_actions["publish_trusted_capture_evidence_packet_contract"]["status"] == "closed"


def test_sccml_trace_adapter_witness_blocks_kernel_authority() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    witness_surfaces = {
        surface["surface_id"]: surface
        for surface in matrix["witness_integrity"]["surfaces"]
    }
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}

    sccml_surface = surfaces["sccml_trace_adapter_witness"]
    sccml_witness_surface = witness_surfaces["sccml_trace_adapter_witness"]
    witnesses = set(sccml_surface["runtime_witnesses"])

    assert sccml_surface["coverage_state"] == "witnessed"
    assert sccml_surface["request_proof"] == "request_proof"
    assert sccml_surface["action_proof"] == "action_proof"
    assert sccml_surface["audit"] == "audit_chain"
    assert "SccmlTraceAdapterWitness" in sccml_surface["representative_paths"]
    assert "schemas/sccml_trace_adapter_witness.schema.json" in sccml_surface["evidence_files"]
    assert "examples/sccml_trace_adapter_witness.foundation.json" in sccml_surface["evidence_files"]
    assert "scripts/validate_sccml_trace_adapter_witness.py" in sccml_surface["evidence_files"]
    assert "tests/test_validate_sccml_trace_adapter_witness.py" in sccml_surface["evidence_files"]
    assert "sccml_trace_adapter_witness_schema_valid" in witnesses
    assert "sccml_trace_adapter_witness_blocks_kernel_authority" in witnesses
    assert "sccml_trace_adapter_witness_requires_digest_refs" in witnesses
    assert "sccml_trace_adapter_witness_rejects_unsupported_op_silence" in witnesses
    assert "sccml_trace_adapter_witness_rejects_raw_trace_retention" in witnesses
    assert "sccml_trace_adapter_witness_rejects_receipt_ref_and_count_drift" in witnesses
    assert "sccml_trace_adapter_witness_sdlc_artifacts_valid" in witnesses
    assert sccml_witness_surface["exact_test_anchor_count"] == 7
    assert sccml_witness_surface["unanchored_witness_count"] == 0
    assert closure_actions["publish_sccml_trace_adapter_witness_contract"]["status"] == "closed"


def test_chaos_rehearsal_execution_report_blocks_runtime_disruption() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    witness_surfaces = {
        surface["surface_id"]: surface
        for surface in matrix["witness_integrity"]["surfaces"]
    }
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    chaos_surface = surfaces["chaos_rehearsal_execution_report"]
    chaos_witness_surface = witness_surfaces["chaos_rehearsal_execution_report"]
    witnesses = set(chaos_surface["runtime_witnesses"])

    assert chaos_surface["coverage_state"] == "witnessed"
    assert chaos_surface["request_proof"] == "request_proof"
    assert chaos_surface["action_proof"] == "action_proof"
    assert "schemas/chaos_rehearsal_execution_report.schema.json" in chaos_surface["evidence_files"]
    assert "examples/chaos_rehearsal_execution_report.foundation.json" in chaos_surface["evidence_files"]
    assert "scripts/validate_chaos_rehearsal_execution_report.py" in chaos_surface["evidence_files"]
    assert "tests/test_validate_chaos_rehearsal_execution_report.py" in chaos_surface["evidence_files"]
    assert "chaos_rehearsal_execution_report_schema_valid" in witnesses
    assert "chaos_rehearsal_execution_report_blocks_runtime_disruption" in witnesses
    assert "chaos_rehearsal_execution_report_requires_scenario_and_rollback_refs" in witnesses
    assert "chaos_rehearsal_execution_report_rejects_raw_runtime_retention" in witnesses
    assert "chaos_rehearsal_execution_report_rejects_result_count_drift" in witnesses
    assert "chaos_rehearsal_execution_report_rejects_receipt_ref_and_count_drift" in witnesses
    assert "chaos_rehearsal_execution_report_sdlc_artifacts_valid" in witnesses
    assert chaos_witness_surface["exact_test_anchor_count"] == 7
    assert chaos_witness_surface["unanchored_witness_count"] == 0
    assert closure_actions["publish_chaos_rehearsal_execution_report_contract"]["status"] == "closed"


def test_invariant_fuzz_execution_report_blocks_canonical_mutation() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    witness_surfaces = {
        surface["surface_id"]: surface
        for surface in matrix["witness_integrity"]["surfaces"]
    }
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    fuzz_surface = surfaces["invariant_fuzz_execution_report"]
    fuzz_witness_surface = witness_surfaces["invariant_fuzz_execution_report"]
    witnesses = set(fuzz_surface["runtime_witnesses"])

    assert fuzz_surface["coverage_state"] == "witnessed"
    assert fuzz_surface["request_proof"] == "request_proof"
    assert fuzz_surface["action_proof"] == "action_proof"
    assert "schemas/invariant_fuzz_execution_report.schema.json" in fuzz_surface["evidence_files"]
    assert "examples/invariant_fuzz_execution_report.foundation.json" in fuzz_surface["evidence_files"]
    assert "scripts/validate_invariant_fuzz_execution_report.py" in fuzz_surface["evidence_files"]
    assert "tests/test_validate_invariant_fuzz_execution_report.py" in fuzz_surface["evidence_files"]
    assert "invariant_fuzz_execution_report_schema_valid" in witnesses
    assert "invariant_fuzz_execution_report_blocks_canonical_mutation" in witnesses
    assert "invariant_fuzz_execution_report_requires_case_bank_and_oracles" in witnesses
    assert "invariant_fuzz_execution_report_rejects_projection_and_raw_retention" in witnesses
    assert "invariant_fuzz_execution_report_rejects_result_count_drift" in witnesses
    assert "invariant_fuzz_execution_report_rejects_receipt_ref_and_count_drift" in witnesses
    assert "invariant_fuzz_execution_report_sdlc_artifacts_valid" in witnesses
    assert fuzz_witness_surface["exact_test_anchor_count"] == 7
    assert fuzz_witness_surface["unanchored_witness_count"] == 0
    assert closure_actions["publish_invariant_fuzz_execution_report_contract"]["status"] == "closed"


def test_maf_receipt_parity_witness_denies_runtime_binding() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    witness_surfaces = {
        surface["surface_id"]: surface
        for surface in matrix["witness_integrity"]["surfaces"]
    }
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    parity_surface = surfaces["maf_receipt_parity_witness"]
    parity_witness_surface = witness_surfaces["maf_receipt_parity_witness"]
    witnesses = set(parity_surface["runtime_witnesses"])

    assert parity_surface["coverage_state"] == "witnessed"
    assert parity_surface["request_proof"] == "request_proof"
    assert parity_surface["action_proof"] == "action_proof"
    assert parity_surface["audit"] == "audit_chain"
    assert "MafReceiptParityWitness" in parity_surface["representative_paths"]
    assert "schemas/maf_receipt_parity_witness.schema.json" in parity_surface["evidence_files"]
    assert "examples/maf_receipt_parity_witness.foundation.json" in parity_surface["evidence_files"]
    assert "scripts/validate_maf_receipt_parity_witness.py" in parity_surface["evidence_files"]
    assert "tests/test_validate_maf_receipt_parity_witness.py" in parity_surface["evidence_files"]
    assert "maf/rust/Cargo.toml" in parity_surface["evidence_files"]
    assert "maf_receipt_parity_witness_schema_valid" in witnesses
    assert "maf_receipt_parity_witness_denies_runtime_binding" in witnesses
    assert "maf_receipt_parity_witness_requires_python_schema_and_rust_crate_refs" in witnesses
    assert "maf_receipt_parity_witness_rejects_digest_drift" in witnesses
    assert "maf_receipt_parity_witness_rejects_gap_closure_without_evidence" in witnesses
    assert "maf_receipt_parity_witness_rejects_summary_drift" in witnesses
    assert "maf_receipt_parity_witness_sdlc_artifacts_valid" in witnesses
    assert parity_witness_surface["exact_test_anchor_count"] == 7
    assert parity_witness_surface["unanchored_witness_count"] == 0
    assert closure_actions["publish_maf_receipt_parity_witness_contract"]["status"] == "closed"


def test_maf_abi_cli_contract_witness_denies_cli_execution() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    witness_surfaces = {
        surface["surface_id"]: surface
        for surface in matrix["witness_integrity"]["surfaces"]
    }
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    cli_surface = surfaces["maf_abi_cli_contract_witness"]
    cli_witness_surface = witness_surfaces["maf_abi_cli_contract_witness"]
    witnesses = set(cli_surface["runtime_witnesses"])

    assert cli_surface["coverage_state"] == "witnessed"
    assert cli_surface["request_proof"] == "request_proof"
    assert cli_surface["action_proof"] == "action_proof"
    assert cli_surface["audit"] == "audit_chain"
    assert "MafAbiCliContractWitness" in cli_surface["representative_paths"]
    assert "schemas/maf_abi_cli_contract_witness.schema.json" in cli_surface["evidence_files"]
    assert "examples/maf_abi_cli_contract_witness.foundation.json" in cli_surface["evidence_files"]
    assert "scripts/validate_maf_abi_cli_contract_witness.py" in cli_surface["evidence_files"]
    assert "tests/test_validate_maf_abi_cli_contract_witness.py" in cli_surface["evidence_files"]
    assert "maf/rust/crates/maf-cli/src/main.rs" in cli_surface["evidence_files"]
    assert "maf_abi_cli_contract_witness_schema_valid" in witnesses
    assert "maf_abi_cli_contract_witness_denies_cli_execution" in witnesses
    assert "maf_abi_cli_contract_witness_requires_cli_artifact_refs" in witnesses
    assert "maf_abi_cli_contract_witness_rejects_scaffold_and_command_drift" in witnesses
    assert "maf_abi_cli_contract_witness_rejects_digest_and_summary_drift" in witnesses
    assert "maf_abi_cli_contract_witness_sdlc_artifacts_valid" in witnesses
    assert cli_witness_surface["exact_test_anchor_count"] == 6
    assert cli_witness_surface["unanchored_witness_count"] == 0
    assert closure_actions["publish_maf_abi_cli_contract_witness_contract"]["status"] == "closed"


def test_maf_subprocess_effect_boundary_witness_denies_subprocess_execution() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    witness_surfaces = {
        surface["surface_id"]: surface
        for surface in matrix["witness_integrity"]["surfaces"]
    }
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    subprocess_surface = surfaces["maf_subprocess_effect_boundary_witness"]
    subprocess_witness_surface = witness_surfaces["maf_subprocess_effect_boundary_witness"]
    witnesses = set(subprocess_surface["runtime_witnesses"])

    assert subprocess_surface["coverage_state"] == "witnessed"
    assert subprocess_surface["request_proof"] == "request_proof"
    assert subprocess_surface["action_proof"] == "action_proof"
    assert subprocess_surface["audit"] == "audit_chain"
    assert "MafSubprocessEffectBoundaryWitness" in subprocess_surface["representative_paths"]
    assert "schemas/maf_subprocess_effect_boundary_witness.schema.json" in subprocess_surface["evidence_files"]
    assert "examples/maf_subprocess_effect_boundary_witness.foundation.json" in subprocess_surface["evidence_files"]
    assert "scripts/validate_maf_subprocess_effect_boundary_witness.py" in subprocess_surface["evidence_files"]
    assert "tests/test_validate_maf_subprocess_effect_boundary_witness.py" in subprocess_surface["evidence_files"]
    assert "maf/rust/crates/maf-cli/src/main.rs" in subprocess_surface["evidence_files"]
    assert "maf_subprocess_effect_boundary_witness_schema_valid" in witnesses
    assert "maf_subprocess_effect_boundary_witness_denies_subprocess_execution" in witnesses
    assert "maf_subprocess_effect_boundary_witness_requires_effect_controls" in witnesses
    assert "maf_subprocess_effect_boundary_witness_rejects_command_effect_drift" in witnesses
    assert "maf_subprocess_effect_boundary_witness_rejects_digest_and_summary_drift" in witnesses
    assert "maf_subprocess_effect_boundary_witness_sdlc_artifacts_valid" in witnesses
    assert subprocess_witness_surface["exact_test_anchor_count"] == 6
    assert subprocess_witness_surface["unanchored_witness_count"] == 0
    assert closure_actions["publish_maf_subprocess_effect_boundary_witness_contract"]["status"] == "closed"


def test_maf_deterministic_fixture_parity_witness_denies_execution() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    witness_surfaces = {
        surface["surface_id"]: surface
        for surface in matrix["witness_integrity"]["surfaces"]
    }
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    fixture_surface = surfaces["maf_deterministic_fixture_parity_witness"]
    fixture_witness_surface = witness_surfaces["maf_deterministic_fixture_parity_witness"]
    witnesses = set(fixture_surface["runtime_witnesses"])

    assert fixture_surface["coverage_state"] == "witnessed"
    assert fixture_surface["request_proof"] == "request_proof"
    assert fixture_surface["action_proof"] == "action_proof"
    assert fixture_surface["audit"] == "audit_chain"
    assert "MafDeterministicFixtureParityWitness" in fixture_surface["representative_paths"]
    assert "schemas/maf_deterministic_fixture_parity_witness.schema.json" in fixture_surface["evidence_files"]
    assert "examples/maf_deterministic_fixture_parity_witness.foundation.json" in fixture_surface["evidence_files"]
    assert "scripts/validate_maf_deterministic_fixture_parity_witness.py" in fixture_surface["evidence_files"]
    assert "tests/test_validate_maf_deterministic_fixture_parity_witness.py" in fixture_surface["evidence_files"]
    assert "maf/rust/crates/maf-cli/src/main.rs" in fixture_surface["evidence_files"]
    assert "maf_deterministic_fixture_parity_witness_schema_valid" in witnesses
    assert "maf_deterministic_fixture_parity_witness_denies_execution" in witnesses
    assert "maf_deterministic_fixture_parity_witness_requires_fixture_vectors" in witnesses
    assert "maf_deterministic_fixture_parity_witness_rejects_fixture_drift" in witnesses
    assert "maf_deterministic_fixture_parity_witness_rejects_digest_and_summary_drift" in witnesses
    assert "maf_deterministic_fixture_parity_witness_sdlc_artifacts_valid" in witnesses
    assert fixture_witness_surface["exact_test_anchor_count"] == 6
    assert fixture_witness_surface["unanchored_witness_count"] == 0
    assert closure_actions["publish_maf_deterministic_fixture_parity_witness_contract"]["status"] == "closed"


def test_maf_failure_receipt_path_witness_denies_execution() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    witness_surfaces = {
        surface["surface_id"]: surface
        for surface in matrix["witness_integrity"]["surfaces"]
    }
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    failure_surface = surfaces["maf_failure_receipt_path_witness"]
    failure_witness_surface = witness_surfaces["maf_failure_receipt_path_witness"]
    witnesses = set(failure_surface["runtime_witnesses"])

    assert failure_surface["coverage_state"] == "witnessed"
    assert failure_surface["request_proof"] == "request_proof"
    assert failure_surface["action_proof"] == "action_proof"
    assert failure_surface["audit"] == "audit_chain"
    assert "MafFailureReceiptPathWitness" in failure_surface["representative_paths"]
    assert "schemas/maf_failure_receipt_path_witness.schema.json" in failure_surface["evidence_files"]
    assert "examples/maf_failure_receipt_path_witness.foundation.json" in failure_surface["evidence_files"]
    assert "scripts/validate_maf_failure_receipt_path_witness.py" in failure_surface["evidence_files"]
    assert "tests/test_validate_maf_failure_receipt_path_witness.py" in failure_surface["evidence_files"]
    assert "maf/rust/crates/maf-cli/src/main.rs" in failure_surface["evidence_files"]
    assert "maf_failure_receipt_path_witness_schema_valid" in witnesses
    assert "maf_failure_receipt_path_witness_denies_execution" in witnesses
    assert "maf_failure_receipt_path_witness_requires_failure_path_controls" in witnesses
    assert "maf_failure_receipt_path_witness_rejects_control_drift" in witnesses
    assert "maf_failure_receipt_path_witness_rejects_digest_and_summary_drift" in witnesses
    assert "maf_failure_receipt_path_witness_sdlc_artifacts_valid" in witnesses
    assert failure_witness_surface["exact_test_anchor_count"] == 6
    assert failure_witness_surface["unanchored_witness_count"] == 0
    assert closure_actions["publish_maf_failure_receipt_path_witness_contract"]["status"] == "closed"


def test_maf_runtime_binding_admission_witness_denies_execution() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    witness_surfaces = {
        surface["surface_id"]: surface
        for surface in matrix["witness_integrity"]["surfaces"]
    }
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    admission_surface = surfaces["maf_runtime_binding_admission_witness"]
    admission_witness_surface = witness_surfaces["maf_runtime_binding_admission_witness"]
    witnesses = set(admission_surface["runtime_witnesses"])

    assert admission_surface["coverage_state"] == "witnessed"
    assert admission_surface["request_proof"] == "request_proof"
    assert admission_surface["action_proof"] == "action_proof"
    assert admission_surface["audit"] == "audit_chain"
    assert "MafRuntimeBindingAdmissionWitness" in admission_surface["representative_paths"]
    assert "schemas/maf_runtime_binding_admission_witness.schema.json" in admission_surface["evidence_files"]
    assert "examples/maf_runtime_binding_admission_witness.foundation.json" in admission_surface["evidence_files"]
    assert "scripts/validate_maf_runtime_binding_admission_witness.py" in admission_surface["evidence_files"]
    assert "tests/test_validate_maf_runtime_binding_admission_witness.py" in admission_surface["evidence_files"]
    assert "docs/AUDIT_F8_SCOPING_PLAN.md" in admission_surface["evidence_files"]
    assert "maf_runtime_binding_admission_witness_schema_valid" in witnesses
    assert "maf_runtime_binding_admission_witness_denies_execution" in witnesses
    assert "maf_runtime_binding_admission_witness_requires_implementation_evidence" in witnesses
    assert "maf_runtime_binding_admission_witness_rejects_requirement_drift" in witnesses
    assert "maf_runtime_binding_admission_witness_rejects_digest_and_summary_drift" in witnesses
    assert "maf_runtime_binding_admission_witness_sdlc_artifacts_valid" in witnesses
    assert admission_witness_surface["exact_test_anchor_count"] == 6
    assert admission_witness_surface["unanchored_witness_count"] == 0
    assert closure_actions["publish_maf_runtime_binding_admission_witness_contract"]["status"] == "closed"


def test_world_substrate_replay_witness_blocks_live_world_authority() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    witness_surfaces = {
        surface["surface_id"]: surface
        for surface in matrix["witness_integrity"]["surfaces"]
    }
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    world_surface = surfaces["world_substrate_replay_witness"]
    world_witness_surface = witness_surfaces["world_substrate_replay_witness"]
    witnesses = set(world_surface["runtime_witnesses"])

    assert world_surface["coverage_state"] == "witnessed"
    assert world_surface["request_proof"] == "request_proof"
    assert world_surface["action_proof"] == "action_proof"
    assert "WorldSubstrateReplayWitness" in world_surface["representative_paths"]
    assert "schemas/world_substrate_replay_witness.schema.json" in world_surface["evidence_files"]
    assert "examples/world_substrate_replay_witness.foundation.json" in world_surface["evidence_files"]
    assert "scripts/validate_world_substrate_replay_witness.py" in world_surface["evidence_files"]
    assert "tests/test_validate_world_substrate_replay_witness.py" in world_surface["evidence_files"]
    assert "world_substrate_replay_witness_schema_valid" in witnesses
    assert "world_substrate_replay_witness_blocks_live_world_authority" in witnesses
    assert "world_substrate_replay_witness_requires_digest_refs" in witnesses
    assert "world_substrate_replay_witness_requires_invariant_controls" in witnesses
    assert "world_substrate_replay_witness_rejects_raw_payload_retention" in witnesses
    assert "world_substrate_replay_witness_rejects_parity_drift" in witnesses
    assert "world_substrate_replay_witness_rejects_receipt_ref_and_count_drift" in witnesses
    assert "world_substrate_replay_witness_sdlc_artifacts_valid" in witnesses
    assert world_witness_surface["exact_test_anchor_count"] == 8
    assert world_witness_surface["unanchored_witness_count"] == 0
    assert closure_actions["publish_world_substrate_replay_witness_contract"]["status"] == "closed"


def test_research_source_conflict_map_preserves_source_disagreement() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    witness_surfaces = {
        surface["surface_id"]: surface
        for surface in matrix["witness_integrity"]["surfaces"]
    }
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    conflict_surface = surfaces["research_source_conflict_map"]
    conflict_witness_surface = witness_surfaces["research_source_conflict_map"]
    witnesses = set(conflict_surface["runtime_witnesses"])

    assert conflict_surface["coverage_state"] == "witnessed"
    assert conflict_surface["request_proof"] == "request_proof"
    assert conflict_surface["action_proof"] == "action_proof"
    assert conflict_surface["audit"] == "audit_chain"
    assert "ResearchSourceConflictMap" in conflict_surface["representative_paths"]
    assert "schemas/research_source_conflict_map.schema.json" in conflict_surface["evidence_files"]
    assert "examples/research_source_conflict_map.foundation.json" in conflict_surface["evidence_files"]
    assert "scripts/validate_research_source_conflict_map.py" in conflict_surface["evidence_files"]
    assert "tests/test_validate_research_source_conflict_map.py" in conflict_surface["evidence_files"]
    assert "research_source_conflict_map_schema_valid" in witnesses
    assert "research_source_conflict_map_blocks_live_research_authority" in witnesses
    assert "research_source_conflict_map_requires_citation_bound_conflicts" in witnesses
    assert "research_source_conflict_map_rejects_raw_body_retention" in witnesses
    assert "research_source_conflict_map_rejects_sensing_authority_drift" in witnesses
    assert conflict_witness_surface["exact_test_anchor_count"] == 6
    assert conflict_witness_surface["unanchored_witness_count"] == 0
    assert closure_actions["publish_research_source_conflict_map_contract"]["status"] == "closed"


def test_worker_receipt_ledger_read_model_blocks_live_authority() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    witness_surfaces = {
        surface["surface_id"]: surface
        for surface in matrix["witness_integrity"]["surfaces"]
    }
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    ledger_surface = surfaces["worker_receipt_ledger_read_model"]
    ledger_witness_surface = witness_surfaces["worker_receipt_ledger_read_model"]
    witnesses = set(ledger_surface["runtime_witnesses"])

    assert ledger_surface["coverage_state"] == "witnessed"
    assert ledger_surface["request_proof"] == "read_model"
    assert ledger_surface["action_proof"] == "read_model"
    assert "WorkerReceiptLedgerReadModel" in ledger_surface["representative_paths"]
    assert "schemas/worker_receipt_ledger_read_model.schema.json" in ledger_surface["evidence_files"]
    assert "examples/worker_receipt_ledger_read_model.foundation.json" in ledger_surface["evidence_files"]
    assert "scripts/validate_worker_receipt_ledger_read_model.py" in ledger_surface["evidence_files"]
    assert "tests/test_validate_worker_receipt_ledger_read_model.py" in ledger_surface["evidence_files"]
    assert "worker_receipt_ledger_read_model_schema_valid" in witnesses
    assert "worker_receipt_ledger_read_model_blocks_live_authority" in witnesses
    assert "worker_receipt_ledger_read_model_rejects_summary_drift" in witnesses
    assert "worker_receipt_ledger_read_model_rejects_missing_refs" in witnesses
    assert ledger_witness_surface["exact_test_anchor_count"] == 6
    assert ledger_witness_surface["unanchored_witness_count"] == 0
    assert closure_actions["publish_worker_receipt_ledger_read_model_contract"]["status"] == "closed"


def test_mfidel_substrate_conformance_receipt_preserves_atomicity() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    witness_surfaces = {
        surface["surface_id"]: surface
        for surface in matrix["witness_integrity"]["surfaces"]
    }
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    mfidel_surface = surfaces["mfidel_substrate_conformance_receipt"]
    mfidel_witness_surface = witness_surfaces["mfidel_substrate_conformance_receipt"]
    witnesses = set(mfidel_surface["runtime_witnesses"])

    assert mfidel_surface["coverage_state"] == "witnessed"
    assert mfidel_surface["request_proof"] == "audit_chain"
    assert mfidel_surface["action_proof"] == "audit_chain"
    assert "MfidelSubstrateConformanceReceipt" in mfidel_surface["representative_paths"]
    assert "schemas/mfidel_substrate_conformance_receipt.schema.json" in mfidel_surface["evidence_files"]
    assert "examples/mfidel_substrate_conformance_receipt.foundation.json" in mfidel_surface["evidence_files"]
    assert "scripts/validate_mfidel_substrate_conformance_receipt.py" in mfidel_surface["evidence_files"]
    assert "tests/test_validate_mfidel_substrate_conformance_receipt.py" in mfidel_surface["evidence_files"]
    assert "mcoi/mcoi_runtime/substrate/mfidel/grid.py" in mfidel_surface["evidence_files"]
    assert "mfidel_substrate_conformance_receipt_schema_valid" in witnesses
    assert "mfidel_substrate_conformance_receipt_preserves_atomicity" in witnesses
    assert "mfidel_substrate_conformance_receipt_rejects_guard_drift" in witnesses
    assert "mfidel_substrate_conformance_receipt_rejects_digest_drift" in witnesses
    assert "mfidel_substrate_conformance_receipt_rejects_cross_runtime_gap_drift" in witnesses
    assert mfidel_witness_surface["exact_test_anchor_count"] == 7
    assert mfidel_witness_surface["unanchored_witness_count"] == 0
    assert closure_actions["publish_mfidel_substrate_conformance_receipt_contract"]["status"] == "closed"


def test_collaboration_case_surface_keeps_closure_non_terminal() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    collaboration_surface = surfaces["collaboration_cases"]
    witnesses = set(collaboration_surface["runtime_witnesses"])

    assert collaboration_surface["coverage_state"] == "witnessed"
    assert collaboration_surface["request_proof"] == "request_proof"
    assert collaboration_surface["action_proof"] == "action_proof"
    assert "CollaborationCaseManager.open_case" in collaboration_surface["representative_paths"]
    assert "CollaborationCaseManager.close_case" in collaboration_surface["representative_paths"]
    assert "gateway/collaboration_cases.py" in collaboration_surface["evidence_files"]
    assert "schemas/collaboration_case.schema.json" in collaboration_surface["evidence_files"]
    assert "tests/test_gateway/test_collaboration_cases.py" in collaboration_surface["evidence_files"]
    assert "approval_separation_required" in witnesses
    assert "pending_controls_block_case_closure" in witnesses
    assert "decider_authority_required" in witnesses
    assert "case_closure_not_terminal_command_closure" in witnesses
    assert "collaboration_case_schema_valid" in witnesses
    assert closure_actions["publish_collaboration_case_contract"]["status"] == "closed"


def test_capability_maturity_surface_is_evidence_derived() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    maturity_surface = surfaces["capability_maturity"]
    witnesses = set(maturity_surface["runtime_witnesses"])

    assert maturity_surface["coverage_state"] == "witnessed"
    assert maturity_surface["request_proof"] == "request_proof"
    assert maturity_surface["action_proof"] == "action_proof"
    assert "gateway/capability_maturity.py" in maturity_surface["evidence_files"]
    assert "schemas/capability_maturity.schema.json" in maturity_surface["evidence_files"]
    assert "tests/test_gateway/test_capability_maturity.py" in maturity_surface["evidence_files"]
    assert "maturity_derived_from_evidence" in witnesses
    assert "effect_bearing_c6_requires_live_write" in witnesses
    assert "production_requires_c6_or_c7" in witnesses
    assert "autonomy_requires_c7" in witnesses
    assert "capability_maturity_schema_valid" in witnesses
    assert closure_actions["publish_capability_maturity_contract"]["status"] == "closed"


def test_policy_prover_surface_reports_counterexamples() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    witness_surfaces = {
        surface["surface_id"]: surface
        for surface in matrix["witness_integrity"]["surfaces"]
    }
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    prover_surface = surfaces["policy_prover"]
    prover_witness_surface = witness_surfaces["policy_prover"]
    witnesses = set(prover_surface["runtime_witnesses"])

    assert prover_surface["coverage_state"] == "witnessed"
    assert prover_surface["request_proof"] == "request_proof"
    assert prover_surface["action_proof"] == "action_proof"
    assert "gateway/policy_prover.py" in prover_surface["evidence_files"]
    assert "schemas/policy_proof_report.schema.json" in prover_surface["evidence_files"]
    assert "tests/test_gateway/test_policy_prover.py" in prover_surface["evidence_files"]
    assert "payment_requires_approval_counterexample" in witnesses
    assert "tenant_isolation_counterexample" in witnesses
    assert "shell_requires_sandbox_counterexample" in witnesses
    assert "provider_url_approved_counterexample" in witnesses
    assert "memory_requires_admission_counterexample" in witnesses
    assert "unknown_property_fails_closed" in witnesses
    assert "policy_proof_report_schema_valid" in witnesses
    assert prover_witness_surface["exact_test_anchor_count"] == 7
    assert prover_witness_surface["unanchored_witness_count"] == 0
    assert closure_actions["publish_policy_prover_counterexample_contract"]["status"] == "closed"


def test_shell_execution_adapter_surface_closes_effect_assurance() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    shell_surface = surfaces["shell_execution_adapter"]
    witnesses = set(shell_surface["runtime_witnesses"])

    assert shell_surface["coverage_state"] == "witnessed"
    assert shell_surface["request_proof"] == "request_proof"
    assert shell_surface["action_proof"] == "action_proof"
    assert "ShellExecutor.execute" in shell_surface["representative_paths"]
    assert "ShellExecutionReceipt" in shell_surface["representative_paths"]
    assert "ShellSandboxPolicy" in shell_surface["representative_paths"]
    assert "mcoi/mcoi_runtime/adapters/shell_executor.py" in shell_surface["evidence_files"]
    assert "mcoi/mcoi_runtime/contracts/shell_execution.py" in shell_surface["evidence_files"]
    assert "mcoi/tests/test_shell_executor.py" in shell_surface["evidence_files"]
    assert "shell_executor_argv_only" in witnesses
    assert "shell_policy_denial_receipt_emitted" in witnesses
    assert "shell_sandbox_denial_receipt_emitted" in witnesses
    assert "shell_receipt_becomes_effect_assurance_evidence_ref" in witnesses
    assert "shell_receipt_closes_effect_assurance" in witnesses
    assert closure_actions["bind_shell_execution_receipts_to_effect_assurance"]["status"] == "closed"


def test_memory_lattice_surface_gates_planning_and_execution() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    lattice_surface = surfaces["memory_lattice"]
    witnesses = set(lattice_surface["runtime_witnesses"])

    assert lattice_surface["coverage_state"] == "witnessed"
    assert lattice_surface["request_proof"] == "request_proof"
    assert lattice_surface["action_proof"] == "action_proof"
    assert "P3MemoryTopologyMap" in lattice_surface["representative_paths"]
    assert "build_p3_memory_topology_read_model" in lattice_surface["representative_paths"]
    assert "gateway/memory_lattice.py" in lattice_surface["evidence_files"]
    assert "schemas/memory_lattice.schema.json" in lattice_surface["evidence_files"]
    assert "schemas/p3_memory_topology_read_model.schema.json" in lattice_surface["evidence_files"]
    assert "tests/test_gateway/test_memory_lattice.py" in lattice_surface["evidence_files"]
    assert "raw_event_memory_not_directly_admitted" in witnesses
    assert "semantic_memory_requires_learning_admission" in witnesses
    assert "contradiction_and_stale_memory_block_execution" in witnesses
    assert "p3_memory_topology_binds_refs" in witnesses
    assert "p3_memory_topology_read_model_schema_valid" in witnesses
    assert "p3_memory_topology_read_model_blocks_authority" in witnesses
    assert closure_actions["publish_memory_lattice_admission_contract"]["status"] == "closed"
    assert closure_actions["publish_p3_memory_topology_read_model_contract"]["status"] == "closed"


def test_workflow_mining_surface_emits_blocked_drafts() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    witness_surfaces = {
        surface["surface_id"]: surface
        for surface in matrix["witness_integrity"]["surfaces"]
    }
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    mining_surface = surfaces["workflow_mining"]
    mining_witness_surface = witness_surfaces["workflow_mining"]
    witnesses = set(mining_surface["runtime_witnesses"])

    assert mining_surface["coverage_state"] == "witnessed"
    assert mining_surface["request_proof"] == "request_proof"
    assert mining_surface["action_proof"] == "action_proof"
    assert "gateway/workflow_mining.py" in mining_surface["evidence_files"]
    assert "schemas/workflow_mining_report.schema.json" in mining_surface["evidence_files"]
    assert "tests/test_gateway/test_workflow_mining.py" in mining_surface["evidence_files"]
    assert "workflow_draft_activation_blocked" in witnesses
    assert "operator_review_required" in witnesses
    assert "risky_pattern_requires_approval_rules" in witnesses
    assert mining_witness_surface["exact_test_anchor_count"] == 6
    assert mining_witness_surface["unanchored_witness_count"] == 0
    assert closure_actions["publish_workflow_mining_draft_contract"]["status"] == "closed"


def test_trust_ledger_surface_signs_terminal_evidence_bundles() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    trust_surface = surfaces["trust_ledger"]
    witnesses = set(trust_surface["runtime_witnesses"])

    assert trust_surface["coverage_state"] == "proven"
    assert trust_surface["request_proof"] == "request_proof"
    assert trust_surface["action_proof"] == "action_proof"
    assert "/evidence/bundles/{command_id}" in trust_surface["representative_paths"]
    assert "docs/65_trust_ledger_offline_verification.md" in trust_surface["evidence_files"]
    assert "gateway/trust_ledger.py" in trust_surface["evidence_files"]
    assert "scripts/verify_anchor_receipt.py" in trust_surface["evidence_files"]
    assert "scripts/package_orgos_anchor_export.py" in trust_surface["evidence_files"]
    assert "scripts/preflight_trust_ledger_remote_submission.py" in trust_surface["evidence_files"]
    assert "scripts/submit_trust_ledger_anchor_export.py" in trust_surface["evidence_files"]
    assert "schemas/trust_ledger_anchor_receipt.schema.json" in trust_surface["evidence_files"]
    assert "schemas/trust_ledger_remote_submission_preflight.schema.json" in trust_surface["evidence_files"]
    assert "schemas/trust_ledger_anchor_submission_receipt.schema.json" in trust_surface["evidence_files"]
    assert "schemas/trust_ledger_anchor_verification_report.schema.json" in trust_surface["evidence_files"]
    assert "schemas/trust_ledger_bundle.schema.json" in trust_surface["evidence_files"]
    assert "schemas/trust_ledger_bundle_verification_report.schema.json" in trust_surface["evidence_files"]
    assert "schemas/trust_ledger_evidence_artifacts.schema.json" in trust_surface["evidence_files"]
    assert "schemas/trust_ledger_export_package.schema.json" in trust_surface["evidence_files"]
    assert "tests/test_gateway/test_evidence_bundle_endpoint.py" in trust_surface["evidence_files"]
    assert "tests/test_gateway/test_trust_ledger_anchor_receipt.py" in trust_surface["evidence_files"]
    assert "tests/test_gateway/test_trust_ledger.py" in trust_surface["evidence_files"]
    assert "tests/test_verify_anchor_receipt.py" in trust_surface["evidence_files"]
    assert "tests/test_package_orgos_anchor_export.py" in trust_surface["evidence_files"]
    assert "tests/test_preflight_trust_ledger_remote_submission.py" in trust_surface["evidence_files"]
    assert "tests/test_submit_trust_ledger_anchor_export.py" in trust_surface["evidence_files"]
    expected_witnesses = {
        "terminal_command_exports_signed_evidence_bundle",
        "evidence_bundle_endpoint_rejects_non_terminal_command",
        "offline_bundle_verifier_detects_tampering",
        "offline_bundle_verifier_report_contract_allows_missing_secret",
        "trust_ledger_issues_and_verifies_signed_bundle",
        "trust_ledger_requires_terminal_certificate_and_evidence",
        "trust_ledger_requires_anchor_ref_when_anchored",
        "trust_ledger_bundle_schema_exposes_signature_contract",
        "trust_ledger_anchor_receipt_binds_required_artifacts",
        "trust_ledger_anchor_receipt_detects_tampered_artifact_root",
        "trust_ledger_anchor_receipt_rejects_missing_terminal_artifact",
        "trust_ledger_anchor_receipt_validates_against_schema",
        "trust_ledger_export_package_binds_verifier_inputs",
        "trust_ledger_export_package_rejects_receipt_identity_drift",
        "verify_anchor_receipt_files_accepts_valid_export",
        "verify_anchor_receipt_files_detects_tampered_artifact_root",
        "verify_anchor_receipt_files_rejects_schema_invalid_receipt",
        "verify_anchor_receipt_files_detects_package_bundle_hash_mismatch",
        "verify_anchor_receipt_files_rejects_schema_invalid_package",
        "verify_anchor_receipt_report_contract_allows_missing_secret_report",
        "package_orgos_anchor_export_merges_optional_orgos_artifact",
        "package_orgos_anchor_export_rejects_required_orgos_artifact",
        "package_orgos_anchor_export_rejects_missing_terminal_artifact",
        "package_orgos_anchor_export_blocks_invalid_generated_package_before_publish",
        "package_orgos_anchor_export_rolls_back_partial_publish_failure",
        "package_orgos_anchor_export_restores_existing_files_on_publish_failure",
        "package_orgos_anchor_export_cli_emits_verifiable_package",
        "trust_ledger_remote_submission_preflight_accepts_ready_export",
        "trust_ledger_remote_submission_preflight_projects_final_submit_payload_hash",
        "trust_ledger_remote_submission_preflight_blocks_missing_remote_token",
        "trust_ledger_remote_submission_preflight_blocks_nonfinite_remote_timeout",
        "trust_ledger_remote_submission_preflight_blocks_tampered_package",
        "trust_ledger_remote_submission_preflight_cli_writes_schema_checked_receipt",
        "trust_ledger_remote_submission_preflight_writer_validates_schema",
        "submit_trust_ledger_anchor_export_records_signed_submission",
        "submit_trust_ledger_anchor_export_blocks_without_confirmation",
        "submit_trust_ledger_anchor_export_blocks_when_submission_ledger_locked",
        "submit_trust_ledger_anchor_export_does_not_accept_boolean_lock_bypass",
        "submit_trust_ledger_anchor_export_removes_stale_submission_ledger_lock",
        "submit_trust_ledger_anchor_export_blocks_invalid_submission_ledger_lock_config",
        "submit_trust_ledger_anchor_export_blocks_unbounded_operator_id",
        "submit_trust_ledger_anchor_export_blocks_tampered_package",
        "submit_trust_ledger_anchor_export_posts_remote_transparency_log",
        "submit_trust_ledger_anchor_export_blocks_remote_without_confirmation",
        "submit_trust_ledger_anchor_export_blocks_remote_transport_when_submission_ledger_locked",
        "submit_trust_ledger_anchor_export_requires_remote_preflight_receipt",
        "submit_trust_ledger_anchor_export_blocks_invalid_remote_timeout_before_transport",
        "submit_trust_ledger_anchor_export_blocks_remote_preflight_hash_mismatch",
        "submit_trust_ledger_anchor_export_blocks_remote_preflight_receipt_id_mismatch",
        "submit_trust_ledger_anchor_export_blocks_remote_preflight_anchor_state_drift",
        "submit_trust_ledger_anchor_export_blocks_remote_preflight_ledger_state_drift",
        "submit_trust_ledger_anchor_export_blocks_remote_preflight_checked_at_drift",
        "submit_trust_ledger_anchor_export_blocks_nonfinite_remote_preflight_timeout",
        "submit_trust_ledger_anchor_export_blocks_remote_hash_mismatch",
        "submit_trust_ledger_anchor_export_blocks_missing_remote_receipt_hash",
        "submit_trust_ledger_anchor_export_blocks_malformed_remote_receipt_hash",
        "verify_submission_ledger_detects_hash_drift",
        "submit_trust_ledger_anchor_export_cli_emits_submission_receipt",
    }
    assert expected_witnesses <= witnesses
    assert closure_actions["publish_trust_ledger_bundle_contract"]["status"] == "closed"
    assert closure_actions["publish_trust_ledger_anchor_receipt_contract"]["status"] == "closed"
    assert closure_actions["publish_trust_ledger_anchor_submission_receipt_contract"]["status"] == "closed"
    assert closure_actions["publish_trust_ledger_remote_submission_preflight_contract"]["status"] == "closed"


def test_domain_operating_pack_surface_requires_certification_evidence() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    pack_surface = surfaces["domain_operating_pack"]
    witnesses = set(pack_surface["runtime_witnesses"])

    assert pack_surface["coverage_state"] == "witnessed"
    assert pack_surface["request_proof"] == "request_proof"
    assert pack_surface["action_proof"] == "action_proof"
    assert "gateway/domain_operating_pack.py" in pack_surface["evidence_files"]
    assert "schemas/domain_operating_pack.schema.json" in pack_surface["evidence_files"]
    assert "tests/test_gateway/test_domain_operating_pack.py" in pack_surface["evidence_files"]
    assert "builtin_domain_pack_catalog_complete" in witnesses
    assert "finance_ops_pack_declares_governed_artifacts" in witnesses
    assert "high_risk_pack_requires_approval_roles" in witnesses
    assert "certified_pack_requires_evidence_refs" in witnesses
    assert "domain_operating_pack_schema_valid" in witnesses
    assert closure_actions["publish_domain_operating_pack_contract"]["status"] == "closed"


def test_multimodal_operating_layer_surface_emits_source_bound_receipts() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    multimodal_surface = surfaces["multimodal_operating_layer"]
    witnesses = set(multimodal_surface["runtime_witnesses"])

    assert multimodal_surface["coverage_state"] == "witnessed"
    assert multimodal_surface["request_proof"] == "request_proof"
    assert multimodal_surface["action_proof"] == "action_proof"
    assert "gateway/multimodal_operating_layer.py" in multimodal_surface["evidence_files"]
    assert "schemas/multimodal_operation_receipt.schema.json" in multimodal_surface["evidence_files"]
    assert "tests/test_gateway/test_multimodal_operating_layer.py" in multimodal_surface["evidence_files"]
    assert "external_send_blocked_by_default" in witnesses
    assert "unknown_modality_fails_closed" in witnesses
    assert closure_actions["publish_multimodal_operation_receipt_contract"]["status"] == "closed"


def test_physical_action_boundary_surface_blocks_dispatch_without_safety_controls() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    physical_surface = surfaces["physical_action_boundary"]
    witnesses = set(physical_surface["runtime_witnesses"])

    assert physical_surface["coverage_state"] == "witnessed"
    assert physical_surface["request_proof"] == "request_proof"
    assert physical_surface["action_proof"] == "action_proof"
    assert "/operator/physical-capability-promotion-receipts" in physical_surface["representative_paths"]
    assert "/operator/physical-capability-promotion-receipts/console" in physical_surface["representative_paths"]
    assert "capsules/physical.json" in physical_surface["evidence_files"]
    assert "capabilities/physical/capability_pack.json" in physical_surface["evidence_files"]
    assert "gateway/capability_capsule_installer.py" in physical_surface["evidence_files"]
    assert "gateway/server.py" in physical_surface["evidence_files"]
    assert "gateway/physical_action_boundary.py" in physical_surface["evidence_files"]
    assert "gateway/physical_capability_promotion_receipt.py" in physical_surface["evidence_files"]
    assert "gateway/physical_capability_promotion_store.py" in physical_surface["evidence_files"]
    assert "gateway/physical_worker_canary.py" in physical_surface["evidence_files"]
    assert "scripts/emit_physical_capability_promotion_receipt.py" in physical_surface["evidence_files"]
    assert "scripts/preflight_physical_capability_promotion.py" in physical_surface["evidence_files"]
    assert "scripts/produce_physical_worker_canary.py" in physical_surface["evidence_files"]
    assert "schemas/physical_action_receipt.schema.json" in physical_surface["evidence_files"]
    assert "schemas/physical_capability_promotion_receipt.schema.json" in physical_surface["evidence_files"]
    assert "tests/test_emit_physical_capability_promotion_receipt.py" in physical_surface["evidence_files"]
    assert "tests/test_gateway/test_capability_capsule_installer.py" in physical_surface["evidence_files"]
    assert "tests/test_gateway/test_physical_action_boundary.py" in physical_surface["evidence_files"]
    assert "tests/test_gateway/test_physical_capability_pack.py" in physical_surface["evidence_files"]
    assert "tests/test_gateway/test_physical_capability_promotion_receipt.py" in physical_surface["evidence_files"]
    assert "tests/test_gateway/test_physical_worker_canary.py" in physical_surface["evidence_files"]
    assert "tests/test_preflight_physical_capability_promotion.py" in physical_surface["evidence_files"]
    assert "tests/test_produce_physical_worker_canary.py" in physical_surface["evidence_files"]
    expected_witnesses = {
        "physical_boundary_blocks_without_simulation",
        "physical_boundary_blocks_live_effects_without_certification",
        "physical_boundary_requires_operator_review_when_approval_missing",
        "physical_action_receipt_matches_schema",
        "physical_fixture_pack_is_not_loaded_by_default",
        "physical_fixture_pack_allows_sandbox_replay_when_production_gate_disabled",
        "physical_fixture_pack_blocks_live_promotion_when_production_gate_enabled",
        "physical_fixture_pack_projects_sandbox_only_gateway_evidence",
        "physical_capability_promotion_preflight_blocks_live_fixture_by_default",
        "physical_capability_promotion_preflight_passes_with_full_evidence",
        "physical_capability_promotion_preflight_allows_sandbox_only_pack",
        "capsule_installer_runs_physical_preflight_before_registry_mutation",
        "capsule_installer_returns_rejected_receipt_without_registry_mutation",
        "physical_capability_promotion_receipt_binds_ready_chain",
        "operator_physical_promotion_receipt_endpoint_emits_ready_bundle",
        "operator_physical_promotion_receipt_endpoint_blocks_missing_live_refs",
        "physical_promotion_receipt_jsonl_store_fails_closed_on_invalid_record",
        "physical_worker_canary_blocks_missing_receipt_and_allows_sandbox_replay",
        "physical_worker_canary_evidence_and_hash_are_stable",
    }
    assert expected_witnesses <= witnesses
    assert closure_actions["publish_physical_action_receipt_contract"]["status"] == "closed"


def test_code_intelligence_operator_surface_is_read_only() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    code_surface = surfaces["code_intelligence_operator_read_model"]
    witnesses = set(code_surface["runtime_witnesses"])

    assert code_surface["coverage_state"] == "witnessed"
    assert code_surface["request_proof"] == "read_model"
    assert code_surface["action_proof"] == "read_model"
    assert "/operator/code-intelligence/read-model" in code_surface["representative_paths"]
    assert "build_repo_map" in code_surface["representative_paths"]
    assert "build_code_context" in code_surface["representative_paths"]
    assert "gateway/code_intelligence_read_model.py" in code_surface["evidence_files"]
    assert "mcoi/mcoi_runtime/contracts/code_intelligence.py" in code_surface["evidence_files"]
    assert "mcoi/mcoi_runtime/contracts/code_context.py" in code_surface["evidence_files"]
    assert "mcoi/mcoi_runtime/core/code_intelligence.py" in code_surface["evidence_files"]
    assert "mcoi/mcoi_runtime/core/code_context_builder.py" in code_surface["evidence_files"]
    assert "tests/test_gateway/test_code_intelligence_read_model.py" in code_surface["evidence_files"]
    assert "code_intelligence_repo_map_detects_routes_schemas_dependencies" in witnesses
    assert "code_context_bundle_bounds_symbols_tests_and_edges" in witnesses
    assert "code_context_missing_affected_file_fails_closed" in witnesses
    assert "code_intelligence_operator_read_model_hides_source_content" in witnesses
    assert "code_intelligence_operator_endpoint_fails_closed_for_missing_file" in witnesses


def test_temporal_kernel_surface_owns_runtime_time_truth() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    temporal_surface = surfaces["temporal_kernel"]
    witnesses = set(temporal_surface["runtime_witnesses"])

    assert temporal_surface["coverage_state"] == "proven"
    assert temporal_surface["request_proof"] == "request_proof"
    assert temporal_surface["action_proof"] == "action_proof"
    assert "/api/v1/temporal/schedules" in temporal_surface["representative_paths"]
    assert "/api/v1/temporal/schedules/{schedule_id}" in temporal_surface["representative_paths"]
    assert "/api/v1/temporal/schedules/{schedule_id}/cancel" in temporal_surface["representative_paths"]
    assert "/api/v1/temporal/worker/tick" in temporal_surface["representative_paths"]
    assert "/api/v1/temporal/monitor" in temporal_surface["representative_paths"]
    assert "/api/v1/temporal/summary" in temporal_surface["representative_paths"]
    assert "TemporalKernel.evaluate" in temporal_surface["representative_paths"]
    assert "TrustedClock.now_utc" in temporal_surface["representative_paths"]
    assert "TrustedClock.monotonic_ns" in temporal_surface["representative_paths"]
    assert "gateway/temporal_kernel.py" in temporal_surface["evidence_files"]
    assert "mcoi/mcoi_runtime/app/routers/temporal_scheduler.py" in temporal_surface["evidence_files"]
    assert "mcoi/mcoi_runtime/core/temporal_scheduler.py" in temporal_surface["evidence_files"]
    assert "mcoi/mcoi_runtime/core/temporal_scheduler_worker.py" in temporal_surface["evidence_files"]
    assert "mcoi/mcoi_runtime/persistence/temporal_scheduler_store.py" in temporal_surface["evidence_files"]
    assert "schemas/temporal_operation_receipt.schema.json" in temporal_surface["evidence_files"]
    assert "tests/test_gateway/test_temporal_kernel.py" in temporal_surface["evidence_files"]
    assert "mcoi/tests/test_temporal_scheduler_router.py" in temporal_surface["evidence_files"]
    assert "runtime_clock_injected" in witnesses
    assert "monotonic_duration_measured" in witnesses
    assert "future_schedule_defers" in witnesses
    assert "approval_expiry_denies" in witnesses
    assert "stale_evidence_escalates" in witnesses
    assert "budget_window_checked" in witnesses
    assert "causal_preconditions_required" in witnesses
    assert "temporal_scheduler_routes_governed" in witnesses
    assert "temporal_monitor_is_read_only" in witnesses
    assert "schedule_read_models_persisted" in witnesses
    assert "worker_tick_certifies_proofs" in witnesses
    assert "cancel_emits_terminal_receipt" in witnesses
    assert "temporal_receipt_schema_valid" in witnesses
    assert closure_actions["publish_temporal_operation_receipt_contract"]["status"] == "closed"
    assert closure_actions["classify_temporal_scheduler_routes"]["status"] == "closed"


def test_policy_version_registry_surface_is_proven() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    policy_surface = surfaces["policy_version_registry"]
    witnesses = set(policy_surface["runtime_witnesses"])
    route_records = {
        record["route"]: record
        for record in matrix["route_coverage"]["routes"]
    }

    assert policy_surface["coverage_state"] == "proven"
    assert policy_surface["request_proof"] == "request_proof"
    assert policy_surface["action_proof"] == "action_proof"
    assert "/api/v1/policies/{policy_id}/versions" in policy_surface["representative_paths"]
    assert "/api/v1/policies/{policy_id}/versions/{version}/promote" in policy_surface["representative_paths"]
    assert "mcoi/tests/test_policy_version_endpoints.py" in policy_surface["evidence_files"]
    assert "policy_version_register_and_fetch" in witnesses
    assert "policy_version_promote_diff_shadow_and_rollback" in witnesses
    assert "policy_version_routes_fail_closed" in witnesses
    assert route_records["/api/v1/policies/{policy_id}/versions"]["coverage_state"] == "proven"
    assert route_records["/api/v1/policies/{policy_id}/versions"]["surface_id"] == "policy_version_registry"
    assert route_records["/api/v1/policies/{policy_id}/versions/{version}"]["coverage_state"] == "proven"
    assert route_records["/api/v1/policies/{policy_id}/versions/{version}"]["surface_id"] == "policy_version_registry"


def test_pilot_provisioning_surface_is_proven() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    pilot_surface = surfaces["pilot_provisioning"]
    witnesses = set(pilot_surface["runtime_witnesses"])
    route_records = {
        record["route"]: record
        for record in matrix["route_coverage"]["routes"]
    }

    assert pilot_surface["coverage_state"] == "proven"
    assert pilot_surface["request_proof"] == "request_proof"
    assert pilot_surface["action_proof"] == "action_proof"
    assert "/api/v1/pilots/provision" in pilot_surface["representative_paths"]
    assert "/api/v1/pilots/provisions" in pilot_surface["representative_paths"]
    assert "/api/v1/pilots/provisions/{pilot_id}" in pilot_surface["representative_paths"]
    assert "mcoi/tests/test_pilot_init.py" in pilot_surface["evidence_files"]
    assert "mcoi/mcoi_runtime/app/pilot_provision_integration.py" in pilot_surface["evidence_files"]
    assert "initialize_pilot_writes_complete_artifact_set" in witnesses
    assert "pilot_provision_registry_persists_bounded_records" in witnesses
    assert "file_pilot_provision_registry_persists_and_reloads_records" in witnesses
    assert "file_pilot_provision_registry_rejects_tampered_record_count" in witnesses
    assert "pilot_provision_registry_integration_selects_memory_or_file" in witnesses
    assert "pilot_provision_registry_path_validation_requires_absolute_json_path" in witnesses
    assert "initialize_pilot_fails_closed_on_existing_files" in witnesses
    assert route_records["/api/v1/pilots/provision"]["coverage_state"] == "proven"
    assert route_records["/api/v1/pilots/provision"]["surface_id"] == "pilot_provisioning"
    assert route_records["/api/v1/pilots/provisions"]["coverage_state"] == "proven"
    assert route_records["/api/v1/pilots/provisions"]["surface_id"] == "pilot_provisioning"


def test_temporal_evidence_freshness_surface_rechecks_required_evidence() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    witness_surfaces = {
        surface["surface_id"]: surface
        for surface in matrix["witness_integrity"]["surfaces"]
    }
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    evidence_surface = surfaces["temporal_evidence_freshness"]
    evidence_witness_surface = witness_surfaces["temporal_evidence_freshness"]
    witnesses = set(evidence_surface["runtime_witnesses"])

    assert evidence_surface["coverage_state"] == "witnessed"
    assert evidence_surface["request_proof"] == "request_proof"
    assert evidence_surface["action_proof"] == "action_proof"
    assert "TemporalEvidenceFreshness.evaluate" in evidence_surface["representative_paths"]
    assert "EvidenceFreshnessClaim" in evidence_surface["representative_paths"]
    assert "TemporalEvidenceFreshnessReceipt" in evidence_surface["representative_paths"]
    assert "gateway/temporal_evidence_freshness.py" in evidence_surface["evidence_files"]
    assert "schemas/temporal_evidence_freshness_receipt.schema.json" in evidence_surface["evidence_files"]
    assert "tests/test_gateway/test_temporal_evidence_freshness.py" in evidence_surface["evidence_files"]
    assert "evidence_age_computed_from_runtime_clock" in witnesses
    assert "freshness_window_required_for_dispatch" in witnesses
    assert "stale_required_evidence_triggers_refresh" in witnesses
    assert "missing_required_evidence_blocks_dispatch" in witnesses
    assert "revoked_or_unverified_high_risk_evidence_blocks" in witnesses
    assert "expiring_evidence_warns_before_dispatch" in witnesses
    assert "temporal_evidence_freshness_receipt_schema_valid" in witnesses
    assert "receipt_not_terminal_closure" in witnesses
    assert evidence_witness_surface["exact_test_anchor_count"] == 8
    assert evidence_witness_surface["unanchored_witness_count"] == 0
    assert closure_actions["publish_temporal_evidence_freshness_receipt_contract"]["status"] == "closed"


def test_temporal_resolution_surface_resolves_phrases_with_runtime_time() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    resolution_surface = surfaces["temporal_resolution"]
    witnesses = set(resolution_surface["runtime_witnesses"])

    assert resolution_surface["coverage_state"] == "witnessed"
    assert resolution_surface["request_proof"] == "request_proof"
    assert resolution_surface["action_proof"] == "action_proof"
    assert "evaluate_temporal_resolution" in resolution_surface["representative_paths"]
    assert "TemporalResolutionRequest" in resolution_surface["representative_paths"]
    assert "TemporalResolutionReceipt" in resolution_surface["representative_paths"]
    assert "gateway/temporal_resolution.py" in resolution_surface["evidence_files"]
    assert "schemas/temporal_resolution_receipt.schema.json" in resolution_surface["evidence_files"]
    assert "tests/test_gateway/test_temporal_resolution.py" in resolution_surface["evidence_files"]
    assert "runtime_clock_owns_phrase_resolution" in witnesses
    assert "original_text_preserved" in witnesses
    assert "tenant_timezone_controls_local_resolution" in witnesses
    assert "relative_duration_resolved_from_injected_now" in witnesses
    assert "ambiguous_low_risk_phrase_uses_safe_default" in witnesses
    assert "ambiguous_high_risk_phrase_requires_clarification" in witnesses
    assert "business_day_resolution_skips_weekends_and_holidays" in witnesses
    assert "unsupported_phrase_fails_closed" in witnesses
    assert "temporal_resolution_receipt_schema_valid" in witnesses
    assert closure_actions["publish_temporal_resolution_receipt_contract"]["status"] == "closed"


def test_temporal_sla_surface_classifies_sla_read_models_and_receipts() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    sla_surface = surfaces["temporal_sla"]
    witnesses = set(sla_surface["runtime_witnesses"])

    assert sla_surface["coverage_state"] == "witnessed"
    assert sla_surface["request_proof"] == "request_proof"
    assert sla_surface["action_proof"] == "action_proof"
    assert "/api/v1/sla" in sla_surface["representative_paths"]
    assert "/api/v1/sla/violations" in sla_surface["representative_paths"]
    assert "TemporalSla.evaluate" in sla_surface["representative_paths"]
    assert "SlaPolicy" in sla_surface["representative_paths"]
    assert "SlaCase" in sla_surface["representative_paths"]
    assert "TemporalSlaReceipt" in sla_surface["representative_paths"]
    assert "gateway/temporal_sla.py" in sla_surface["evidence_files"]
    assert "mcoi/mcoi_runtime/app/routers/data/sla.py" in sla_surface["evidence_files"]
    assert "mcoi/mcoi_runtime/core/sla_monitor.py" in sla_surface["evidence_files"]
    assert "schemas/temporal_sla_receipt.schema.json" in sla_surface["evidence_files"]
    assert "tests/test_gateway/test_temporal_sla.py" in sla_surface["evidence_files"]
    assert "mcoi/tests/test_sla_monitor.py" in sla_surface["evidence_files"]
    assert "mcoi/tests/test_sla_router.py" in sla_surface["evidence_files"]
    assert "runtime_clock_owns_sla_deadlines" in witnesses
    assert "business_time_deadlines_skip_closed_windows" in witnesses
    assert "approaching_deadline_warns_before_breach" in witnesses
    assert "breached_deadline_emits_escalation_reason" in witnesses
    assert "outside_business_window_holds_normal_dispatch" in witnesses
    assert "sla_evidence_and_scope_checked" in witnesses
    assert "sla_summary_read_model_bounded" in witnesses
    assert "sla_violations_read_model_bounded" in witnesses
    assert "temporal_sla_receipt_schema_valid" in witnesses
    assert closure_actions["publish_temporal_sla_receipt_contract"]["status"] == "closed"


def test_temporal_reapproval_surface_rechecks_execution_time_approval_grants() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    witness_surfaces = {
        surface["surface_id"]: surface
        for surface in matrix["witness_integrity"]["surfaces"]
    }
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    reapproval_surface = surfaces["temporal_reapproval"]
    reapproval_witness_surface = witness_surfaces["temporal_reapproval"]
    witnesses = set(reapproval_surface["runtime_witnesses"])

    assert reapproval_surface["coverage_state"] == "witnessed"
    assert reapproval_surface["request_proof"] == "request_proof"
    assert reapproval_surface["action_proof"] == "action_proof"
    assert "TemporalReapproval.evaluate" in reapproval_surface["representative_paths"]
    assert "ReapprovalRequest" in reapproval_surface["representative_paths"]
    assert "TemporalReapprovalReceipt" in reapproval_surface["representative_paths"]
    assert "gateway/temporal_reapproval.py" in reapproval_surface["evidence_files"]
    assert "schemas/temporal_reapproval_receipt.schema.json" in reapproval_surface["evidence_files"]
    assert "tests/test_gateway/test_temporal_reapproval.py" in reapproval_surface["evidence_files"]
    assert "runtime_clock_owns_reapproval_time" in witnesses
    assert "high_risk_approval_roles_required" in witnesses
    assert "expired_approval_requires_reapproval" in witnesses
    assert "revoked_or_out_of_scope_approval_blocks_dispatch" in witnesses
    assert "missing_approval_role_requires_reapproval" in witnesses
    assert "low_risk_action_does_not_require_reapproval" in witnesses
    assert "temporal_reapproval_receipt_schema_valid" in witnesses
    assert "receipt_not_terminal_closure" in witnesses
    assert reapproval_witness_surface["exact_test_anchor_count"] == 8
    assert reapproval_witness_surface["unanchored_witness_count"] == 0
    assert closure_actions["publish_temporal_reapproval_receipt_contract"]["status"] == "closed"


def test_temporal_dispatch_window_surface_rechecks_runtime_admission_windows() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    dispatch_window_surface = surfaces["temporal_dispatch_window"]
    witnesses = set(dispatch_window_surface["runtime_witnesses"])

    assert dispatch_window_surface["coverage_state"] == "witnessed"
    assert dispatch_window_surface["request_proof"] == "request_proof"
    assert dispatch_window_surface["action_proof"] == "action_proof"
    assert "TemporalDispatchWindow.evaluate" in dispatch_window_surface["representative_paths"]
    assert "DispatchWindowRequest" in dispatch_window_surface["representative_paths"]
    assert "TemporalDispatchWindowReceipt" in dispatch_window_surface["representative_paths"]
    assert "gateway/temporal_dispatch_window.py" in dispatch_window_surface["evidence_files"]
    assert "schemas/temporal_dispatch_window_receipt.schema.json" in dispatch_window_surface["evidence_files"]
    assert "tests/test_gateway/test_temporal_dispatch_window.py" in dispatch_window_surface["evidence_files"]
    assert "runtime_clock_owns_dispatch_window_time" in witnesses
    assert "tenant_timezone_resolved" in witnesses
    assert "allowed_window_required_for_high_risk_dispatch" in witnesses
    assert "outside_allowed_window_defers_dispatch" in witnesses
    assert "active_blackout_defers_dispatch" in witnesses
    assert "holiday_closure_defers_dispatch" in witnesses
    assert "source_reapproval_bound_for_high_risk_dispatch" in witnesses
    assert "temporal_dispatch_window_receipt_schema_valid" in witnesses
    assert closure_actions["publish_temporal_dispatch_window_receipt_contract"]["status"] == "closed"


def test_temporal_budget_window_surface_rechecks_tenant_budget_periods() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    budget_window_surface = surfaces["temporal_budget_window"]
    witnesses = set(budget_window_surface["runtime_witnesses"])

    assert budget_window_surface["coverage_state"] == "witnessed"
    assert budget_window_surface["request_proof"] == "request_proof"
    assert budget_window_surface["action_proof"] == "action_proof"
    assert "TemporalBudgetWindow.evaluate" in budget_window_surface["representative_paths"]
    assert "BudgetWindowRequest" in budget_window_surface["representative_paths"]
    assert "TemporalBudgetWindowReceipt" in budget_window_surface["representative_paths"]
    assert "gateway/temporal_budget_window.py" in budget_window_surface["evidence_files"]
    assert "schemas/temporal_budget_window_receipt.schema.json" in budget_window_surface["evidence_files"]
    assert "tests/test_gateway/test_temporal_budget_window.py" in budget_window_surface["evidence_files"]
    assert "runtime_clock_owns_budget_window_time" in witnesses
    assert "tenant_timezone_resolves_budget_period" in witnesses
    assert "daily_weekly_monthly_budget_resets_computed" in witnesses
    assert "spend_snapshot_period_matches_active_window" in witnesses
    assert "projected_spend_blocks_over_limit_dispatch" in witnesses
    assert "future_budget_window_defers_dispatch" in witnesses
    assert "source_reapproval_bound_for_high_risk_budget_window" in witnesses
    assert "temporal_budget_window_receipt_schema_valid" in witnesses
    assert closure_actions["publish_temporal_budget_window_receipt_contract"]["status"] == "closed"


def test_temporal_causal_order_surface_rechecks_required_event_order() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    causal_order_surface = surfaces["temporal_causal_order"]
    witnesses = set(causal_order_surface["runtime_witnesses"])

    assert causal_order_surface["coverage_state"] == "witnessed"
    assert causal_order_surface["request_proof"] == "request_proof"
    assert causal_order_surface["action_proof"] == "action_proof"
    assert "TemporalCausalOrder.evaluate" in causal_order_surface["representative_paths"]
    assert "TemporalCausalOrderRequest" in causal_order_surface["representative_paths"]
    assert "TemporalCausalOrderReceipt" in causal_order_surface["representative_paths"]
    assert "gateway/temporal_causal_order.py" in causal_order_surface["evidence_files"]
    assert "schemas/temporal_causal_order_receipt.schema.json" in causal_order_surface["evidence_files"]
    assert "tests/test_gateway/test_temporal_causal_order.py" in causal_order_surface["evidence_files"]
    assert "runtime_clock_owns_causal_order_time" in witnesses
    assert "required_events_must_be_present" in witnesses
    assert "tenant_and_command_scope_checked" in witnesses
    assert "predecessor_edges_checked" in witnesses
    assert "out_of_order_events_block_dispatch" in witnesses
    assert "future_events_block_dispatch" in witnesses
    assert "high_risk_source_receipts_bound" in witnesses
    assert "temporal_causal_order_receipt_schema_valid" in witnesses
    assert closure_actions["publish_temporal_causal_order_receipt_contract"]["status"] == "closed"


def test_temporal_monotonic_duration_surface_rechecks_elapsed_time() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    witness_surfaces = {
        surface["surface_id"]: surface
        for surface in matrix["witness_integrity"]["surfaces"]
    }
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    duration_surface = surfaces["temporal_monotonic_duration"]
    duration_witness_surface = witness_surfaces["temporal_monotonic_duration"]
    witnesses = set(duration_surface["runtime_witnesses"])

    assert duration_surface["coverage_state"] == "witnessed"
    assert duration_surface["request_proof"] == "request_proof"
    assert duration_surface["action_proof"] == "action_proof"
    assert "TemporalMonotonicDuration.evaluate" in duration_surface["representative_paths"]
    assert "TemporalMonotonicDurationRequest" in duration_surface["representative_paths"]
    assert "TemporalMonotonicDurationReceipt" in duration_surface["representative_paths"]
    assert "gateway/temporal_monotonic_duration.py" in duration_surface["evidence_files"]
    assert "schemas/temporal_monotonic_duration_receipt.schema.json" in duration_surface["evidence_files"]
    assert "tests/test_gateway/test_temporal_monotonic_duration.py" in duration_surface["evidence_files"]
    assert "runtime_monotonic_clock_owns_duration_truth" in witnesses
    assert "wall_clock_not_used_for_duration" in witnesses
    assert "duration_limit_exceeded_blocks_dispatch" in witnesses
    assert "cooldown_lower_bound_defers_dispatch" in witnesses
    assert "monotonic_clock_regression_blocks_dispatch" in witnesses
    assert "high_risk_source_receipts_bound" in witnesses
    assert "temporal_monotonic_duration_receipt_schema_valid" in witnesses
    assert "receipt_not_terminal_closure" in witnesses
    assert duration_witness_surface["exact_test_anchor_count"] == 8
    assert duration_witness_surface["unanchored_witness_count"] == 0
    assert closure_actions["publish_temporal_monotonic_duration_receipt_contract"]["status"] == "closed"


def test_temporal_accepted_risk_expiry_surface_blocks_stale_risk() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    accepted_risk_surface = surfaces["temporal_accepted_risk_expiry"]
    witnesses = set(accepted_risk_surface["runtime_witnesses"])

    assert accepted_risk_surface["coverage_state"] == "witnessed"
    assert accepted_risk_surface["request_proof"] == "request_proof"
    assert accepted_risk_surface["action_proof"] == "action_proof"
    assert "TemporalAcceptedRiskExpiry.evaluate" in accepted_risk_surface["representative_paths"]
    assert "TemporalAcceptedRiskRequest" in accepted_risk_surface["representative_paths"]
    assert "TemporalAcceptedRiskExpiryReceipt" in accepted_risk_surface["representative_paths"]
    assert "gateway/temporal_accepted_risk_expiry.py" in accepted_risk_surface["evidence_files"]
    assert "schemas/temporal_accepted_risk_expiry_receipt.schema.json" in accepted_risk_surface["evidence_files"]
    assert "tests/test_gateway/test_temporal_accepted_risk_expiry.py" in accepted_risk_surface["evidence_files"]
    assert "runtime_clock_owns_accepted_risk_expiry" in witnesses
    assert "expired_accepted_risk_blocks_dispatch" in witnesses
    assert "revoked_or_closed_accepted_risk_blocks_dispatch" in witnesses
    assert "tenant_command_and_action_scope_checked" in witnesses
    assert "review_obligation_required" in witnesses
    assert "accepted_risk_evidence_refs_required" in witnesses
    assert "high_risk_source_receipts_bound" in witnesses
    assert "temporal_accepted_risk_expiry_receipt_schema_valid" in witnesses
    assert closure_actions["publish_temporal_accepted_risk_expiry_receipt_contract"]["status"] == "closed"


def test_temporal_credential_expiry_surface_blocks_expired_credentials() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    credential_surface = surfaces["temporal_credential_expiry"]
    witnesses = set(credential_surface["runtime_witnesses"])

    assert credential_surface["coverage_state"] == "witnessed"
    assert credential_surface["request_proof"] == "request_proof"
    assert credential_surface["action_proof"] == "action_proof"
    assert "TemporalCredentialExpiry.evaluate" in credential_surface["representative_paths"]
    assert "TemporalCredentialRequest" in credential_surface["representative_paths"]
    assert "TemporalCredentialExpiryReceipt" in credential_surface["representative_paths"]
    assert "gateway/temporal_credential_expiry.py" in credential_surface["evidence_files"]
    assert "schemas/temporal_credential_expiry_receipt.schema.json" in credential_surface["evidence_files"]
    assert "tests/test_gateway/test_temporal_credential_expiry.py" in credential_surface["evidence_files"]
    assert "runtime_clock_owns_credential_expiry" in witnesses
    assert "expired_credentials_block_dispatch" in witnesses
    assert "revoked_credentials_block_dispatch" in witnesses
    assert "provider_and_credential_scope_checked" in witnesses
    assert "rotation_pending_warns_before_dispatch" in witnesses
    assert "rotation_overdue_blocks_dispatch" in witnesses
    assert "credential_evidence_refs_required" in witnesses
    assert "secret_value_absence_verified" in witnesses
    assert "high_risk_source_receipts_bound" in witnesses
    assert "temporal_credential_expiry_receipt_schema_valid" in witnesses
    assert closure_actions["publish_temporal_credential_expiry_receipt_contract"]["status"] == "closed"


def test_temporal_retention_window_surface_rechecks_data_lifecycle_timing() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    retention_surface = surfaces["temporal_retention_window"]
    witnesses = set(retention_surface["runtime_witnesses"])

    assert retention_surface["coverage_state"] == "witnessed"
    assert retention_surface["request_proof"] == "request_proof"
    assert retention_surface["action_proof"] == "action_proof"
    assert "TemporalRetentionWindow.evaluate" in retention_surface["representative_paths"]
    assert "TemporalRetentionRequest" in retention_surface["representative_paths"]
    assert "TemporalRetentionWindowReceipt" in retention_surface["representative_paths"]
    assert "gateway/temporal_retention_window.py" in retention_surface["evidence_files"]
    assert "schemas/temporal_retention_window_receipt.schema.json" in retention_surface["evidence_files"]
    assert "tests/test_gateway/test_temporal_retention_window.py" in retention_surface["evidence_files"]
    assert "runtime_clock_owns_retention_timing" in witnesses
    assert "delete_before_delete_after_defers_action" in witnesses
    assert "archive_and_anonymize_wait_for_retention_until" in witnesses
    assert "legal_hold_blocks_lifecycle_action" in witnesses
    assert "overdue_retention_action_warns" in witnesses
    assert "tenant_scope_checked" in witnesses
    assert "retention_policy_ref_required" in witnesses
    assert "subject_evidence_refs_required" in witnesses
    assert "high_risk_source_receipts_bound" in witnesses
    assert "retention_approval_and_backup_guard_bound" in witnesses
    assert "temporal_retention_window_receipt_schema_valid" in witnesses
    assert closure_actions["publish_temporal_retention_window_receipt_contract"]["status"] == "closed"


def test_github_check_run_write_receipt_surface_binds_external_write_evidence() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    check_surface = surfaces["github_check_run_write_receipts"]
    witnesses = set(check_surface["runtime_witnesses"])

    assert check_surface["coverage_state"] == "witnessed"
    assert check_surface["request_proof"] == "request_proof"
    assert check_surface["action_proof"] == "action_proof"
    assert "GitHubCheckRunWriter.evaluate" in check_surface["representative_paths"]
    assert "GitHubCheckRunWriteRequest" in check_surface["representative_paths"]
    assert "GitHubCheckRunWriteReceipt" in check_surface["representative_paths"]
    assert "gateway/github_check_run_writer.py" in check_surface["evidence_files"]
    assert "schemas/github_check_run_write_receipt.schema.json" in check_surface["evidence_files"]
    assert "tests/test_gateway/test_github_check_run_writer.py" in check_surface["evidence_files"]
    assert "check_run_payload_is_hash_bound" in witnesses
    assert "plan_only_does_not_write_check_run" in witnesses
    assert "dry_run_rejects_response_evidence" in witnesses
    assert "write_approved_requires_github_app_execution_receipt" in witnesses
    assert "write_approved_binds_external_execution_receipt" in witnesses
    assert "secret_value_absence_verified" in witnesses
    assert "completed_status_requires_conclusion" in witnesses
    assert "github_check_run_write_receipt_schema_valid" in witnesses
    assert closure_actions["publish_github_check_run_write_receipt_contract"]["status"] == "closed"


def test_github_app_token_exchange_receipt_surface_binds_external_exchange_evidence() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    exchange_surface = surfaces["github_app_token_exchange_receipts"]
    witnesses = set(exchange_surface["runtime_witnesses"])

    assert exchange_surface["coverage_state"] == "witnessed"
    assert exchange_surface["request_proof"] == "request_proof"
    assert exchange_surface["action_proof"] == "action_proof"
    assert "GitHubAppTokenExchange.evaluate" in exchange_surface["representative_paths"]
    assert "GitHubAppTokenExchangeRequest" in exchange_surface["representative_paths"]
    assert "GitHubAppTokenExchangeReceipt" in exchange_surface["representative_paths"]
    assert "gateway/github_app_token_exchange.py" in exchange_surface["evidence_files"]
    assert "schemas/github_app_token_exchange_receipt.schema.json" in exchange_surface["evidence_files"]
    assert "tests/test_gateway/test_github_app_token_exchange.py" in exchange_surface["evidence_files"]
    assert "token_exchange_payload_is_hash_bound" in witnesses
    assert "plan_only_does_not_exchange_token" in witnesses
    assert "dry_run_rejects_token_response_evidence" in witnesses
    assert "exchange_approved_requires_external_receipt" in witnesses
    assert "exchange_approved_binds_external_receipt" in witnesses
    assert "secret_token_absence_verified" in witnesses
    assert "token_ttl_bounds_enforced" in witnesses
    assert "github_app_token_exchange_receipt_schema_valid" in witnesses
    assert closure_actions["publish_github_app_token_exchange_receipt_contract"]["status"] == "closed"


def test_github_action_execution_receipt_surface_binds_external_action_evidence() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    action_surface = surfaces["github_action_execution_receipts"]
    witnesses = set(action_surface["runtime_witnesses"])

    assert action_surface["coverage_state"] == "witnessed"
    assert action_surface["request_proof"] == "request_proof"
    assert action_surface["action_proof"] == "action_proof"
    assert "GitHubActionExecution.evaluate" in action_surface["representative_paths"]
    assert "GitHubActionExecutionRequest" in action_surface["representative_paths"]
    assert "GitHubActionExecutionReceipt" in action_surface["representative_paths"]
    assert "gateway/github_action_execution.py" in action_surface["evidence_files"]
    assert "schemas/github_action_execution_receipt.schema.json" in action_surface["evidence_files"]
    assert "tests/test_gateway/test_github_action_execution.py" in action_surface["evidence_files"]
    assert "github_action_payload_is_hash_bound" in witnesses
    assert "plan_only_does_not_execute_github_action" in witnesses
    assert "dry_run_rejects_execution_response_evidence" in witnesses
    assert "execute_approved_requires_token_and_external_receipts" in witnesses
    assert "execute_approved_binds_external_execution_receipt" in witnesses
    assert "token_plan_repository_mismatch_blocks_execution" in witnesses
    assert "secret_token_absence_verified" in witnesses
    assert "branch_protection_reconcile_action_is_endpoint_bound" in witnesses
    assert "github_action_execution_receipt_schema_valid" in witnesses
    assert closure_actions["publish_github_action_execution_receipt_contract"]["status"] == "closed"


def test_github_branch_protection_reconcile_receipt_surface_binds_drift_and_apply_evidence() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    reconcile_surface = surfaces["github_branch_protection_reconcile_receipts"]
    witnesses = set(reconcile_surface["runtime_witnesses"])

    assert reconcile_surface["coverage_state"] == "witnessed"
    assert reconcile_surface["request_proof"] == "request_proof"
    assert reconcile_surface["action_proof"] == "action_proof"
    assert "BranchProtectionReconciler.evaluate" in reconcile_surface["representative_paths"]
    assert "BranchProtectionReconcileRequest" in reconcile_surface["representative_paths"]
    assert "BranchProtectionReconcileReceipt" in reconcile_surface["representative_paths"]
    assert "gateway/branch_protection_reconcile.py" in reconcile_surface["evidence_files"]
    assert "schemas/github_branch_protection_reconcile_receipt.schema.json" in reconcile_surface["evidence_files"]
    assert "tests/test_gateway/test_branch_protection_reconcile.py" in reconcile_surface["evidence_files"]
    assert "branch_protection_policy_payload_is_hash_bound" in witnesses
    assert "observed_compliance_emits_noop_receipt" in witnesses
    assert "observed_drift_emits_reconcile_actions" in witnesses
    assert "missing_observed_state_is_explicit" in witnesses
    assert "dry_run_rejects_apply_response_evidence" in witnesses
    assert "apply_approved_requires_external_receipts" in witnesses
    assert "apply_approved_binds_external_action_receipt" in witnesses
    assert "noop_apply_blocks_external_mutation" in witnesses
    assert "secret_value_absence_verified" in witnesses
    assert "github_branch_protection_reconcile_receipt_schema_valid" in witnesses
    assert closure_actions["publish_github_branch_protection_reconcile_receipt_contract"]["status"] == "closed"


def test_distributed_lease_claim_receipt_surface_binds_backend_claim_evidence() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    lease_surface = surfaces["distributed_lease_claim_receipts"]
    witnesses = set(lease_surface["runtime_witnesses"])

    assert lease_surface["coverage_state"] == "witnessed"
    assert lease_surface["request_proof"] == "request_proof"
    assert lease_surface["action_proof"] == "action_proof"
    assert "DistributedLeaseClaimPlanner.evaluate" in lease_surface["representative_paths"]
    assert "DistributedLeaseClaimBoundaryRequest" in lease_surface["representative_paths"]
    assert "DistributedLeaseClaimReceipt" in lease_surface["representative_paths"]
    assert "gateway/distributed_lease_boundary.py" in lease_surface["evidence_files"]
    assert "schemas/distributed_lease_claim_receipt.schema.json" in lease_surface["evidence_files"]
    assert "tests/test_gateway/test_distributed_lease_boundary.py" in lease_surface["evidence_files"]
    assert "distributed_lease_policy_and_request_hash_bound" in witnesses
    assert "backend_operation_payload_is_hash_bound" in witnesses
    assert "plan_only_does_not_claim_lease" in witnesses
    assert "dry_run_rejects_claim_response_evidence" in witnesses
    assert "claim_approved_requires_external_receipts" in witnesses
    assert "claim_approved_binds_adapter_receipt" in witnesses
    assert "claim_approved_allows_unfenced_policy_without_token" in witnesses
    assert "claim_approved_classifies_conflict_response" in witnesses
    assert "claim_approved_classifies_deferred_response" in witnesses
    assert "claim_approved_classifies_rejected_response" in witnesses
    assert "observed_payload_mismatch_blocks_claim" in witnesses
    assert "expired_or_unfenced_claim_blocks_dispatch" in witnesses
    assert "secret_value_absence_verified" in witnesses
    assert "distributed_lease_claim_receipt_schema_valid" in witnesses
    assert closure_actions["publish_distributed_lease_claim_receipt_contract"]["status"] == "closed"


def test_distributed_lease_adapter_registry_surface_binds_backend_capability() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    lease_surface = surfaces["distributed_lease_adapter_registry_receipts"]
    witnesses = set(lease_surface["runtime_witnesses"])

    assert lease_surface["coverage_state"] == "witnessed"
    assert lease_surface["request_proof"] == "request_proof"
    assert lease_surface["action_proof"] == "action_proof"
    assert "DistributedLeaseAdapterRegistryEvaluator.evaluate" in lease_surface["representative_paths"]
    assert "DistributedLeaseAdapterRegistry" in lease_surface["representative_paths"]
    assert "DistributedLeaseAdapterRegistryReceipt" in lease_surface["representative_paths"]
    assert "gateway/distributed_lease_adapters.py" in lease_surface["evidence_files"]
    assert "gateway/distributed_lease_boundary.py" in lease_surface["evidence_files"]
    assert "schemas/distributed_lease_adapter_registry_receipt.schema.json" in lease_surface["evidence_files"]
    assert "tests/test_gateway/test_distributed_lease_adapters.py" in lease_surface["evidence_files"]
    assert "adapter_registry_default_inventory_hash_bound" in witnesses
    assert "adapter_registry_delegates_external_gateway_without_local_execution" in witnesses
    assert "adapter_registry_blocks_native_adapter_without_production_readiness" in witnesses
    assert "adapter_registry_blocks_fencing_required_backend_without_token_support" in witnesses
    assert "adapter_registry_blocks_claim_receipt_violations" in witnesses
    assert "adapter_registry_binds_claim_approved_external_gateway_receipt" in witnesses
    assert "adapter_registry_rejects_secret_values" in witnesses
    assert "distributed_lease_adapter_registry_receipt_schema_valid" in witnesses
    assert closure_actions["publish_distributed_lease_adapter_registry_receipt_contract"]["status"] == "closed"


def test_temporal_rate_limit_window_surface_rechecks_token_windows() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    rate_limit_surface = surfaces["temporal_rate_limit_window"]
    witnesses = set(rate_limit_surface["runtime_witnesses"])

    assert rate_limit_surface["coverage_state"] == "witnessed"
    assert rate_limit_surface["request_proof"] == "request_proof"
    assert rate_limit_surface["action_proof"] == "action_proof"
    assert "TemporalRateLimitWindow.evaluate" in rate_limit_surface["representative_paths"]
    assert "RateLimitWindowRequest" in rate_limit_surface["representative_paths"]
    assert "TemporalRateLimitWindowReceipt" in rate_limit_surface["representative_paths"]
    assert "gateway/temporal_rate_limit_window.py" in rate_limit_surface["evidence_files"]
    assert "schemas/temporal_rate_limit_window_receipt.schema.json" in rate_limit_surface["evidence_files"]
    assert "tests/test_gateway/test_temporal_rate_limit_window.py" in rate_limit_surface["evidence_files"]
    assert "runtime_clock_owns_rate_limit_window" in witnesses
    assert "tenant_endpoint_identity_scope_checked" in witnesses
    assert "active_window_admits_sufficient_tokens" in witnesses
    assert "exhausted_window_emits_retry_after" in witnesses
    assert "future_window_defers_dispatch" in witnesses
    assert "burst_limit_blocks_overlarge_request" in witnesses
    assert "stale_rate_limit_snapshot_blocks_dispatch" in witnesses
    assert "high_risk_source_receipts_bound" in witnesses
    assert "temporal_rate_limit_window_receipt_schema_valid" in witnesses
    assert closure_actions["publish_temporal_rate_limit_window_receipt_contract"]["status"] == "closed"


def test_temporal_retry_window_surface_rechecks_retry_windows() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    retry_surface = surfaces["temporal_retry_window"]
    witnesses = set(retry_surface["runtime_witnesses"])

    assert retry_surface["coverage_state"] == "witnessed"
    assert retry_surface["request_proof"] == "request_proof"
    assert retry_surface["action_proof"] == "action_proof"
    assert "TemporalRetryWindow.evaluate" in retry_surface["representative_paths"]
    assert "RetryWindowRequest" in retry_surface["representative_paths"]
    assert "TemporalRetryWindowReceipt" in retry_surface["representative_paths"]
    assert "gateway/temporal_retry_window.py" in retry_surface["evidence_files"]
    assert "schemas/temporal_retry_window_receipt.schema.json" in retry_surface["evidence_files"]
    assert "tests/test_gateway/test_temporal_retry_window.py" in retry_surface["evidence_files"]
    assert "runtime_clock_owns_retry_window" in witnesses
    assert "retry_after_floor_checked" in witnesses
    assert "cooldown_window_defers_early_retry" in witnesses
    assert "max_attempts_block_exhausted_retry" in witnesses
    assert "expired_retry_window_blocks_dispatch" in witnesses
    assert "tenant_command_scope_checked" in witnesses
    assert "terminal_failure_blocks_retry" in witnesses
    assert "high_risk_source_receipts_bound" in witnesses
    assert "temporal_retry_window_receipt_schema_valid" in witnesses
    assert closure_actions["publish_temporal_retry_window_receipt_contract"]["status"] == "closed"


def test_temporal_lease_window_surface_rechecks_lease_ownership() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    lease_surface = surfaces["temporal_lease_window"]
    witnesses = set(lease_surface["runtime_witnesses"])

    assert lease_surface["coverage_state"] == "witnessed"
    assert lease_surface["request_proof"] == "request_proof"
    assert lease_surface["action_proof"] == "action_proof"
    assert "TemporalLeaseWindow.evaluate" in lease_surface["representative_paths"]
    assert "LeaseWindowRequest" in lease_surface["representative_paths"]
    assert "TemporalLeaseWindowReceipt" in lease_surface["representative_paths"]
    assert "gateway/temporal_lease_window.py" in lease_surface["evidence_files"]
    assert "schemas/temporal_lease_window_receipt.schema.json" in lease_surface["evidence_files"]
    assert "tests/test_gateway/test_temporal_lease_window.py" in lease_surface["evidence_files"]
    assert "runtime_clock_owns_lease_window" in witnesses
    assert "tenant_command_resource_worker_scope_checked" in witnesses
    assert "active_lease_admits_dispatch" in witnesses
    assert "near_expiry_lease_requires_renewal_warning" in witnesses
    assert "expired_lease_blocks_dispatch" in witnesses
    assert "released_or_revoked_lease_blocks_dispatch" in witnesses
    assert "fencing_token_required" in witnesses
    assert "high_risk_source_receipts_bound" in witnesses
    assert "temporal_lease_window_receipt_schema_valid" in witnesses
    assert closure_actions["publish_temporal_lease_window_receipt_contract"]["status"] == "closed"


def test_temporal_idempotency_window_surface_blocks_duplicate_dispatch() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    idempotency_surface = surfaces["temporal_idempotency_window"]
    witnesses = set(idempotency_surface["runtime_witnesses"])

    assert idempotency_surface["coverage_state"] == "witnessed"
    assert idempotency_surface["request_proof"] == "request_proof"
    assert idempotency_surface["action_proof"] == "action_proof"
    assert "TemporalIdempotencyWindow.evaluate" in idempotency_surface["representative_paths"]
    assert "IdempotencyWindowRequest" in idempotency_surface["representative_paths"]
    assert "TemporalIdempotencyWindowReceipt" in idempotency_surface["representative_paths"]
    assert "gateway/temporal_idempotency_window.py" in idempotency_surface["evidence_files"]
    assert "schemas/temporal_idempotency_window_receipt.schema.json" in idempotency_surface["evidence_files"]
    assert "tests/test_gateway/test_temporal_idempotency_window.py" in idempotency_surface["evidence_files"]
    assert "runtime_clock_owns_idempotency_window" in witnesses
    assert "new_idempotency_key_admits_dispatch" in witnesses
    assert "matching_replay_admits_uncommitted_dispatch" in witnesses
    assert "committed_effect_blocks_duplicate_dispatch" in witnesses
    assert "expired_idempotency_window_blocks_dispatch" in witnesses
    assert "request_fingerprint_mismatch_blocks_replay" in witnesses
    assert "tenant_command_action_scope_checked" in witnesses
    assert "high_risk_source_receipts_bound" in witnesses
    assert "temporal_idempotency_window_receipt_schema_valid" in witnesses
    assert closure_actions["publish_temporal_idempotency_window_receipt_contract"]["status"] == "closed"


def test_temporal_missed_run_surface_emits_skip_and_recovery_receipts() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    witness_surfaces = {
        surface["surface_id"]: surface
        for surface in matrix["witness_integrity"]["surfaces"]
    }
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    missed_run_surface = surfaces["temporal_missed_run"]
    missed_run_witness_surface = witness_surfaces["temporal_missed_run"]
    witnesses = set(missed_run_surface["runtime_witnesses"])

    assert missed_run_surface["coverage_state"] == "witnessed"
    assert missed_run_surface["request_proof"] == "request_proof"
    assert missed_run_surface["action_proof"] == "action_proof"
    assert "evaluate_temporal_missed_run" in missed_run_surface["representative_paths"]
    assert "MissedRunRequest" in missed_run_surface["representative_paths"]
    assert "TemporalMissedRunReceipt" in missed_run_surface["representative_paths"]
    assert "gateway/temporal_missed_run.py" in missed_run_surface["evidence_files"]
    assert "schemas/temporal_missed_run_receipt.schema.json" in missed_run_surface["evidence_files"]
    assert "tests/test_gateway/test_temporal_missed_run.py" in missed_run_surface["evidence_files"]
    assert "runtime_clock_owns_missed_run_time" in witnesses
    assert "late_within_grace_preserves_dispatch_eligibility" in witnesses
    assert "expired_command_emits_missed_run_receipt" in witnesses
    assert "duplicate_dispatched_run_requires_terminal_receipt" in witnesses
    assert "recovery_due_requires_review_actions" in witnesses
    assert "tenant_command_action_scope_checked" in witnesses
    assert "high_risk_source_receipts_bound" in witnesses
    assert "temporal_missed_run_receipt_schema_valid" in witnesses
    assert "receipt_not_terminal_closure" in witnesses
    assert missed_run_witness_surface["exact_test_anchor_count"] == 9
    assert missed_run_witness_surface["unanchored_witness_count"] == 0
    assert closure_actions["publish_temporal_missed_run_receipt_contract"]["status"] == "closed"


def test_temporal_recurrence_window_surface_emits_next_due_receipts() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    witness_surfaces = {
        surface["surface_id"]: surface
        for surface in matrix["witness_integrity"]["surfaces"]
    }
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    recurrence_surface = surfaces["temporal_recurrence_window"]
    recurrence_witness_surface = witness_surfaces["temporal_recurrence_window"]
    witnesses = set(recurrence_surface["runtime_witnesses"])

    assert recurrence_surface["coverage_state"] == "witnessed"
    assert recurrence_surface["request_proof"] == "request_proof"
    assert recurrence_surface["action_proof"] == "action_proof"
    assert "evaluate_temporal_recurrence_window" in recurrence_surface["representative_paths"]
    assert "RecurrenceWindowRequest" in recurrence_surface["representative_paths"]
    assert "TemporalRecurrenceWindowReceipt" in recurrence_surface["representative_paths"]
    assert "gateway/temporal_recurrence_window.py" in recurrence_surface["evidence_files"]
    assert "schemas/temporal_recurrence_window_receipt.schema.json" in recurrence_surface["evidence_files"]
    assert "tests/test_gateway/test_temporal_recurrence_window.py" in recurrence_surface["evidence_files"]
    assert "runtime_clock_owns_recurrence_window_time" in witnesses
    assert "tenant_timezone_preserved_across_dst" in witnesses
    assert "candidate_must_match_next_occurrence" in witnesses
    assert "future_candidate_defers_dispatch" in witnesses
    assert "completed_series_blocks_dispatch" in witnesses
    assert "duplicate_candidate_requires_terminal_receipt" in witnesses
    assert "monthly_end_of_month_clamped" in witnesses
    assert "high_risk_due_candidate_requires_reapproval_source" in witnesses
    assert "temporal_recurrence_window_receipt_schema_valid" in witnesses
    assert "receipt_not_terminal_closure" in witnesses
    assert recurrence_witness_surface["exact_test_anchor_count"] == 10
    assert recurrence_witness_surface["unanchored_witness_count"] == 0
    assert closure_actions["publish_temporal_recurrence_window_receipt_contract"]["status"] == "closed"


def test_temporal_memory_surface_blocks_stale_or_superseded_memory() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    memory_surface = surfaces["temporal_memory"]
    witnesses = set(memory_surface["runtime_witnesses"])

    assert memory_surface["coverage_state"] == "witnessed"
    assert memory_surface["request_proof"] == "request_proof"
    assert memory_surface["action_proof"] == "action_proof"
    assert "TemporalMemory.evaluate" in memory_surface["representative_paths"]
    assert "TemporalMemoryRecord" in memory_surface["representative_paths"]
    assert "TemporalMemoryReceipt" in memory_surface["representative_paths"]
    assert "gateway/temporal_memory.py" in memory_surface["evidence_files"]
    assert "schemas/temporal_memory_receipt.schema.json" in memory_surface["evidence_files"]
    assert "tests/test_gateway/test_temporal_memory.py" in memory_surface["evidence_files"]
    assert "memory_age_computed_from_runtime_clock" in witnesses
    assert "stale_memory_requires_refresh" in witnesses
    assert "validity_window_blocks_expired_memory" in witnesses
    assert "superseded_memory_not_usable" in witnesses
    assert "confidence_decay_blocks_weak_memory" in witnesses
    assert "temporal_memory_receipt_schema_valid" in witnesses
    assert closure_actions["publish_temporal_memory_receipt_contract"]["status"] == "closed"


def test_temporal_memory_refresh_surface_creates_bounded_refresh_work() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    witness_surfaces = {
        surface["surface_id"]: surface
        for surface in matrix["witness_integrity"]["surfaces"]
    }
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    refresh_surface = surfaces["temporal_memory_refresh"]
    refresh_witness_surface = witness_surfaces["temporal_memory_refresh"]
    witnesses = set(refresh_surface["runtime_witnesses"])

    assert refresh_surface["coverage_state"] == "witnessed"
    assert refresh_surface["request_proof"] == "request_proof"
    assert refresh_surface["action_proof"] == "action_proof"
    assert "TemporalMemoryRefresh.evaluate" in refresh_surface["representative_paths"]
    assert "MemoryRefreshRequest" in refresh_surface["representative_paths"]
    assert "TemporalMemoryRefreshReceipt" in refresh_surface["representative_paths"]
    assert "gateway/temporal_memory_refresh.py" in refresh_surface["evidence_files"]
    assert "schemas/temporal_memory_refresh_receipt.schema.json" in refresh_surface["evidence_files"]
    assert "tests/test_gateway/test_temporal_memory_refresh.py" in refresh_surface["evidence_files"]
    assert "usable_memory_does_not_create_refresh_task" in witnesses
    assert "stale_memory_creates_bounded_refresh_task" in witnesses
    assert "evidence_type_coverage_gates_review_readiness" in witnesses
    assert "invalid_refresh_policy_blocks_task_creation" in witnesses
    assert "superseded_memory_blocks_reactivation" in witnesses
    assert "temporal_memory_refresh_receipt_schema_valid" in witnesses
    assert "receipt_not_terminal_closure" in witnesses
    assert refresh_witness_surface["exact_test_anchor_count"] == 7
    assert refresh_witness_surface["unanchored_witness_count"] == 0
    assert closure_actions["publish_temporal_memory_refresh_receipt_contract"]["status"] == "closed"


def test_temporal_scheduler_surface_requires_leases_and_retry_windows() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    scheduler_surface = surfaces["temporal_scheduler"]
    witnesses = set(scheduler_surface["runtime_witnesses"])

    assert scheduler_surface["coverage_state"] == "witnessed"
    assert scheduler_surface["request_proof"] == "request_proof"
    assert scheduler_surface["action_proof"] == "action_proof"
    assert "TemporalScheduler.evaluate" in scheduler_surface["representative_paths"]
    assert "ScheduledCommand" in scheduler_surface["representative_paths"]
    assert "TemporalSchedulerReceipt" in scheduler_surface["representative_paths"]
    assert "gateway/temporal_scheduler.py" in scheduler_surface["evidence_files"]
    assert "schemas/temporal_scheduler_receipt.schema.json" in scheduler_surface["evidence_files"]
    assert "tests/test_gateway/test_temporal_scheduler.py" in scheduler_surface["evidence_files"]
    assert "scheduled_command_requires_execute_at" in witnesses
    assert "idempotency_required" in witnesses
    assert "lease_acquired_before_dispatch" in witnesses
    assert "missed_run_receipt_emitted" in witnesses
    assert "retry_window_checked" in witnesses
    assert "high_risk_reapproval_required" in witnesses
    assert "active_lease_blocks_duplicate_execution" in witnesses
    assert "temporal_scheduler_receipt_schema_valid" in witnesses
    assert closure_actions["publish_temporal_scheduler_receipt_contract"]["status"] == "closed"


def test_policy_proof_report_surface_is_counterexample_backed() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    witness_surfaces = {
        surface["surface_id"]: surface
        for surface in matrix["witness_integrity"]["surfaces"]
    }
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    policy_surface = surfaces["policy_proof_report"]
    policy_witness_surface = witness_surfaces["policy_proof_report"]
    witnesses = set(policy_surface["runtime_witnesses"])

    assert policy_surface["coverage_state"] == "witnessed"
    assert policy_surface["request_proof"] == "request_proof"
    assert policy_surface["action_proof"] == "action_proof"
    assert "PolicyProver.prove" in policy_surface["representative_paths"]
    assert "gateway/policy_prover.py" in policy_surface["evidence_files"]
    assert "schemas/policy_proof_report.schema.json" in policy_surface["evidence_files"]
    assert "tests/test_gateway/test_policy_prover.py" in policy_surface["evidence_files"]
    assert "bounded_policy_cases_required" in witnesses
    assert "empty_invariants_rejected" in witnesses
    assert "counterexamples_are_concrete" in witnesses
    assert "proved_report_has_no_counterexamples" in witnesses
    assert "policy_weakening_forbidden" in witnesses
    assert "policy_proof_schema_valid" in witnesses
    assert policy_witness_surface["exact_test_anchor_count"] == 6
    assert policy_witness_surface["unanchored_witness_count"] == 0
    assert closure_actions["publish_policy_proof_report_contract"]["status"] == "closed"


def test_autonomous_capability_upgrade_surface_keeps_plans_activation_blocked() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    upgrade_surface = surfaces["autonomous_capability_upgrade"]
    witnesses = set(upgrade_surface["runtime_witnesses"])

    assert upgrade_surface["coverage_state"] == "proven"
    assert upgrade_surface["request_proof"] == "request_proof"
    assert upgrade_surface["action_proof"] == "action_proof"
    assert "gateway/autonomous_capability_upgrade.py" in upgrade_surface["evidence_files"]
    assert "schemas/capability_upgrade_plan.schema.json" in upgrade_surface["evidence_files"]
    assert "tests/test_gateway/test_autonomous_capability_upgrade.py" in upgrade_surface["evidence_files"]
    assert "health_signal_requires_evidence_refs" in witnesses
    assert "upgrade_candidates_are_promotion_blocked" in witnesses
    assert "capability_upgrade_plan_schema_valid" in witnesses
    assert closure_actions["publish_capability_upgrade_plan_contract"]["status"] == "closed"


def test_autonomous_test_generation_surface_keeps_plans_activation_blocked() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    generation_surface = surfaces["autonomous_test_generation"]
    witnesses = set(generation_surface["runtime_witnesses"])

    assert generation_surface["coverage_state"] == "witnessed"
    assert generation_surface["request_proof"] == "request_proof"
    assert generation_surface["action_proof"] == "action_proof"
    assert "gateway/autonomous_test_generation.py" in generation_surface["evidence_files"]
    assert "schemas/autonomous_test_generation_plan.schema.json" in generation_surface["evidence_files"]
    assert "tests/test_gateway/test_autonomous_test_generation.py" in generation_surface["evidence_files"]
    assert "failure_trace_requires_evidence_refs" in witnesses
    assert "generation_requires_matching_certified_trace" in witnesses
    assert "plans_are_activation_blocked" in witnesses
    assert "schema_rejects_unanchored_empty_generation_plan" in witnesses
    assert "autonomous_test_generation_plan_schema_valid" in witnesses
    assert closure_actions["publish_autonomous_test_generation_plan_contract"]["status"] == "closed"


def test_representative_http_paths_are_declared() -> None:
    matrix = _load_fixture()
    routes = discover_declared_routes()

    assert "/api/v1/stream" in routes
    assert "/api/v1/chat/stream" in routes
    assert validate_matrix_routes(matrix, routes) == []


def test_generated_assurance_copy_matches_when_present() -> None:
    matrix = _load_fixture()

    assert CANONICAL_OUTPUT.exists()
    assert matrix["surfaces"]
    if ASSURANCE_OUTPUT.exists():
        assurance = json.loads(ASSURANCE_OUTPUT.read_text(encoding="utf-8"))
        assert assurance == matrix


def test_operator_document_mentions_every_surface() -> None:
    matrix = _load_fixture()
    doc = DOC_OUTPUT.read_text(encoding="utf-8")

    assert doc == operator_document(matrix)
    assert all(f"`{surface['surface_id']}`" in doc for surface in matrix["surfaces"])
    assert all(f"`{action['action_id']}`" in doc for action in matrix["closure_actions"])
    assert "schema contract validation" in doc
    assert "deployment orchestration receipt schema contract" in doc
