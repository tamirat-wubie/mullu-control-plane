"""Tests for the public Mullu Governance Protocol manifest.

Purpose: verify the open schema surface is complete and the runtime remains outside the public contract boundary.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA]
Dependencies: protocol manifest validator and public schemas.
Invariants: every schema is indexed once, URNs match, and runtime paths are non-contract surfaces.
"""
from __future__ import annotations

import importlib
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

validate_protocol_manifest_module = importlib.import_module("scripts.validate_protocol_manifest")

CLOSED_SURFACE = validate_protocol_manifest_module.CLOSED_SURFACE
OPEN_SURFACE = validate_protocol_manifest_module.OPEN_SURFACE
PROTOCOL_ID = validate_protocol_manifest_module.PROTOCOL_ID
SCHEMA_DIR = validate_protocol_manifest_module.SCHEMA_DIR
load_manifest = validate_protocol_manifest_module.load_manifest
validate_protocol_manifest = validate_protocol_manifest_module.validate_protocol_manifest


def test_protocol_manifest_is_valid() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    agent_identity_entry = entries["agent-identity"]
    claim_verification_entry = entries["claim-verification-report"]
    connector_self_healing_entry = entries["connector-self-healing-receipt"]
    collaboration_entry = entries["collaboration-case"]
    autonomous_test_entry = entries["autonomous-test-generation-plan"]
    capability_upgrade_entry = entries["capability-upgrade-plan"]
    orchestration_validation_entry = entries["deployment-orchestration-receipt-validation"]
    publication_closure_validation_entry = entries["deployment-publication-closure-validation"]
    candidate_entry = entries["capability-candidate"]
    maturity_entry = entries["capability-maturity"]
    marketplace_entry = entries["marketplace-sdk-catalog"]
    math_solver_receipt_entry = entries["math-solver-receipt"]
    economic_intelligence_entry = entries["economic-intelligence-snapshot"]
    federated_control_entry = entries["federated-control-snapshot"]
    memory_lattice_entry = entries["memory-lattice"]
    policy_rule_entry = entries["policy-rule"]
    policy_bundle_entry = entries["policy-bundle"]
    policy_evaluation_trace_entry = entries["policy-evaluation-trace"]
    policy_proof_entry = entries["policy-proof-report"]
    trust_ledger_entry = entries["trust-ledger-bundle"]
    trust_anchor_entry = entries["trust-ledger-anchor-receipt"]
    domain_pack_entry = entries["domain-operating-pack"]
    multimodal_entry = entries["multimodal-operation-receipt"]
    gateway_readiness_entry = entries["gateway-publication-readiness"]
    gateway_receipt_validation_entry = entries["gateway-publication-receipt-validation"]
    goal_entry = entries["goal"]
    temporal_entry = entries["temporal-operation-receipt"]
    temporal_resolution_entry = entries["temporal-resolution-receipt"]
    temporal_evidence_entry = entries["temporal-evidence-freshness-receipt"]
    temporal_reapproval_entry = entries["temporal-reapproval-receipt"]
    temporal_dispatch_window_entry = entries["temporal-dispatch-window-receipt"]
    temporal_budget_window_entry = entries["temporal-budget-window-receipt"]
    temporal_causal_order_entry = entries["temporal-causal-order-receipt"]
    temporal_monotonic_duration_entry = entries["temporal-monotonic-duration-receipt"]
    temporal_accepted_risk_entry = entries["temporal-accepted-risk-expiry-receipt"]
    temporal_credential_entry = entries["temporal-credential-expiry-receipt"]
    temporal_retention_entry = entries["temporal-retention-window-receipt"]
    temporal_rate_limit_entry = entries["temporal-rate-limit-window-receipt"]
    temporal_retry_window_entry = entries["temporal-retry-window-receipt"]
    temporal_lease_window_entry = entries["temporal-lease-window-receipt"]
    temporal_idempotency_window_entry = entries["temporal-idempotency-window-receipt"]
    temporal_missed_run_entry = entries["temporal-missed-run-receipt"]
    temporal_recurrence_window_entry = entries["temporal-recurrence-window-receipt"]
    temporal_memory_entry = entries["temporal-memory-receipt"]
    temporal_memory_refresh_entry = entries["temporal-memory-refresh-receipt"]
    scheduler_entry = entries["temporal-scheduler-receipt"]
    simulation_entry = entries["simulation-receipt"]
    supervisor_tick_entry = entries["supervisor-tick"]
    supervisor_checkpoint_entry = entries["supervisor-checkpoint"]
    livelock_entry = entries["livelock-record"]
    workflow_mining_entry = entries["workflow-mining-report"]
    universal_action_orchestration_entry = entries["universal-action-orchestration"]
    universal_action_orchestration_validation_receipt_entry = entries[
        "universal-action-orchestration-validation-receipt"
    ]
    worker_mesh_entry = entries["worker-mesh"]
    worker_failure_entry = entries["worker-failure-receipt"]
    read_only_worker_entry = entries["read-only-worker-binding"]
    read_only_worker_lease_preflight_entry = entries["read-only-worker-lease-preflight"]
    read_only_worker_rehearsal_receipt_entry = entries["read-only-worker-rehearsal-receipt"]
    read_only_worker_runtime_receipt_handoff_entry = entries["read-only-worker-runtime-receipt-handoff"]
    read_only_worker_runtime_receipt_emitter_dry_run_entry = entries[
        "read-only-worker-runtime-receipt-emitter-dry-run"
    ]
    read_only_worker_runtime_runner_binding_witness_entry = entries[
        "read-only-worker-runtime-runner-binding-witness"
    ]
    read_only_worker_runtime_receipt_candidate_entry = entries[
        "read-only-worker-runtime-receipt-candidate"
    ]
    read_only_worker_runtime_receipt_schema_binding_witness_entry = entries[
        "read-only-worker-runtime-receipt-schema-binding-witness"
    ]
    read_only_worker_runtime_receipt_store_write_path_witness_entry = entries[
        "read-only-worker-runtime-receipt-store-write-path-witness"
    ]
    read_only_worker_runtime_runner_registration_witness_entry = entries[
        "read-only-worker-runtime-runner-registration-witness"
    ]
    read_only_worker_runtime_dispatch_endpoint_registration_witness_entry = entries[
        "read-only-worker-runtime-dispatch-endpoint-registration-witness"
    ]
    read_only_worker_runtime_receipt_emitter_registration_witness_entry = entries[
        "read-only-worker-runtime-receipt-emitter-registration-witness"
    ]
    read_only_worker_runtime_receipt_schema_binding_activation_witness_entry = entries[
        "read-only-worker-runtime-receipt-schema-binding-activation-witness"
    ]
    read_only_worker_runtime_receipt_store_activation_witness_entry = entries[
        "read-only-worker-runtime-receipt-store-activation-witness"
    ]
    read_only_worker_runtime_receipt_emission_admission_witness_entry = entries[
        "read-only-worker-runtime-receipt-emission-admission-witness"
    ]
    read_only_worker_runtime_active_lease_admission_witness_entry = entries[
        "read-only-worker-runtime-active-lease-admission-witness"
    ]
    read_only_worker_runtime_authority_chain_witness_entry = entries[
        "read-only-worker-runtime-authority-chain-witness"
    ]
    read_only_worker_runtime_dispatch_admission_witness_entry = entries[
        "read-only-worker-runtime-dispatch-admission-witness"
    ]
    world_state_entry = entries["world-state"]
    reflex_entry = entries["reflex-deployment-witness-envelope"]
    receipt_entry = entries["reflex-deployment-witness-validator-receipt"]
    interpreted_request_entry = entries["interpreted-request"]
    interpretation_receipt_entry = entries["interpretation-receipt"]
    clarification_request_entry = entries["clarification-request"]
    search_decision_entry = entries["search-decision"]
    search_receipt_entry = entries["search-receipt"]
    capability_plan_preview_entry = entries["capability-plan-preview"]
    governed_planning_profile_entry = entries["governed-planning-profile"]
    governed_planning_profile_report_entry = entries["governed-planning-profile-admission-report"]
    governed_planning_profile_dossier_entry = entries["governed-planning-profile-shadow-dossier"]
    governed_planning_profile_operator_evidence_entry = entries[
        "governed-planning-profile-operator-shadow-pilot-evidence"
    ]
    governed_planning_profile_operator_observation_entry = entries[
        "governed-planning-profile-operator-shadow-pilot-observation-receipt"
    ]
    governed_planning_profile_runtime_approval_entry = entries[
        "governed-planning-profile-runtime-promotion-approval-packet"
    ]
    governed_planning_profile_replay_recovery_entry = entries[
        "governed-planning-profile-replay-recovery-witness"
    ]
    governed_planning_profile_terminal_closure_entry = entries[
        "governed-planning-profile-terminal-closure-certificate"
    ]
    governed_planning_profile_runtime_authorization_request_entry = entries[
        "governed-planning-profile-runtime-authorization-request"
    ]
    governed_symbolic_loop_entry = entries["governed-symbolic-loop-contract"]
    errors = validate_protocol_manifest(manifest)

    assert errors == []
    assert manifest["protocol_id"] == PROTOCOL_ID
    assert manifest["protocol_name"] == "Mullu Governance Protocol"
    assert manifest["protocol_uri_scheme"] == "mgp://"
    assert len(entries) == len(manifest["schemas"])
    assert len(manifest["schemas"]) == len(tuple(SCHEMA_DIR.glob("*.schema.json")))
    assert interpreted_request_entry["path"] == "schemas/interpreted_request.schema.json"
    assert interpreted_request_entry["urn"] == "urn:mullusi:schema:interpreted-request:1"
    assert interpreted_request_entry["surface"] == "interpretation"
    assert interpretation_receipt_entry["path"] == "schemas/interpretation_receipt.schema.json"
    assert interpretation_receipt_entry["urn"] == "urn:mullusi:schema:interpretation-receipt:1"
    assert interpretation_receipt_entry["surface"] == "evidence"
    assert clarification_request_entry["path"] == "schemas/clarification_request.schema.json"
    assert clarification_request_entry["urn"] == "urn:mullusi:schema:clarification-request:1"
    assert clarification_request_entry["surface"] == "interpretation"
    assert search_decision_entry["path"] == "schemas/search_decision.schema.json"
    assert search_decision_entry["urn"] == "urn:mullusi:schema:search-decision:1"
    assert search_decision_entry["surface"] == "search"
    assert search_receipt_entry["path"] == "schemas/search_receipt.schema.json"
    assert search_receipt_entry["urn"] == "urn:mullusi:schema:search-receipt:1"
    assert search_receipt_entry["surface"] == "search"
    assert capability_plan_preview_entry["path"] == "schemas/capability_plan_preview.schema.json"
    assert capability_plan_preview_entry["urn"] == "urn:mullusi:schema:capability-plan-preview:1"
    assert capability_plan_preview_entry["surface"] == "planning"
    assert governed_planning_profile_entry["path"] == "schemas/governed_planning_profile.schema.json"
    assert governed_planning_profile_entry["urn"] == "urn:mullusi:schema:governed-planning-profile:1"
    assert governed_planning_profile_entry["surface"] == "planning"
    assert governed_planning_profile_report_entry["path"] == (
        "schemas/governed_planning_profile_admission_report.schema.json"
    )
    assert governed_planning_profile_report_entry["urn"] == (
        "urn:mullusi:schema:governed-planning-profile-admission-report:1"
    )
    assert governed_planning_profile_report_entry["surface"] == "planning"
    assert governed_planning_profile_dossier_entry["path"] == (
        "schemas/governed_planning_profile_shadow_dossier.schema.json"
    )
    assert governed_planning_profile_dossier_entry["urn"] == (
        "urn:mullusi:schema:governed-planning-profile-shadow-dossier:1"
    )
    assert governed_planning_profile_dossier_entry["surface"] == "planning"
    assert governed_planning_profile_operator_evidence_entry["path"] == (
        "schemas/governed_planning_profile_operator_shadow_pilot_evidence.schema.json"
    )
    assert governed_planning_profile_operator_evidence_entry["urn"] == (
        "urn:mullusi:schema:governed-planning-profile-operator-shadow-pilot-evidence:1"
    )
    assert governed_planning_profile_operator_evidence_entry["surface"] == "planning"
    assert governed_planning_profile_operator_observation_entry["path"] == (
        "schemas/governed_planning_profile_operator_shadow_pilot_observation_receipt.schema.json"
    )
    assert governed_planning_profile_operator_observation_entry["urn"] == (
        "urn:mullusi:schema:governed-planning-profile-operator-shadow-pilot-observation-receipt:1"
    )
    assert governed_planning_profile_operator_observation_entry["surface"] == "planning"
    assert governed_planning_profile_runtime_approval_entry["path"] == (
        "schemas/governed_planning_profile_runtime_promotion_approval_packet.schema.json"
    )
    assert governed_planning_profile_runtime_approval_entry["urn"] == (
        "urn:mullusi:schema:governed-planning-profile-runtime-promotion-approval-packet:1"
    )
    assert governed_planning_profile_runtime_approval_entry["surface"] == "planning"
    assert governed_planning_profile_replay_recovery_entry["path"] == (
        "schemas/governed_planning_profile_replay_recovery_witness.schema.json"
    )
    assert governed_planning_profile_replay_recovery_entry["urn"] == (
        "urn:mullusi:schema:governed-planning-profile-replay-recovery-witness:1"
    )
    assert governed_planning_profile_replay_recovery_entry["surface"] == "planning"
    assert governed_planning_profile_terminal_closure_entry["path"] == (
        "schemas/governed_planning_profile_terminal_closure_certificate.schema.json"
    )
    assert governed_planning_profile_terminal_closure_entry["urn"] == (
        "urn:mullusi:schema:governed-planning-profile-terminal-closure-certificate:1"
    )
    assert governed_planning_profile_terminal_closure_entry["surface"] == "planning"
    assert governed_planning_profile_runtime_authorization_request_entry["path"] == (
        "schemas/governed_planning_profile_runtime_authorization_request.schema.json"
    )
    assert governed_planning_profile_runtime_authorization_request_entry["urn"] == (
        "urn:mullusi:schema:governed-planning-profile-runtime-authorization-request:1"
    )
    assert governed_planning_profile_runtime_authorization_request_entry["surface"] == "planning"
    assert governed_symbolic_loop_entry["path"] == "schemas/governed_symbolic_loop_contract.schema.json"
    assert governed_symbolic_loop_entry["urn"] == "urn:mullusi:schema:governed-symbolic-loop-contract:1"
    assert governed_symbolic_loop_entry["surface"] == "governance"
    assert agent_identity_entry["path"] == "schemas/agent_identity.schema.json"
    assert agent_identity_entry["urn"] == "urn:mullusi:schema:agent-identity:1"
    assert agent_identity_entry["surface"] == "identity"
    assert claim_verification_entry["path"] == "schemas/claim_verification_report.schema.json"
    assert claim_verification_entry["urn"] == "urn:mullusi:schema:claim-verification-report:1"
    assert claim_verification_entry["surface"] == "claim"
    assert collaboration_entry["path"] == "schemas/collaboration_case.schema.json"
    assert collaboration_entry["urn"] == "urn:mullusi:schema:collaboration-case:1"
    assert collaboration_entry["surface"] == "collaboration"
    assert connector_self_healing_entry["path"] == "schemas/connector_self_healing_receipt.schema.json"
    assert connector_self_healing_entry["urn"] == "urn:mullusi:schema:connector-self-healing-receipt:1"
    assert connector_self_healing_entry["surface"] == "connector"
    assert autonomous_test_entry["path"] == "schemas/autonomous_test_generation_plan.schema.json"
    assert autonomous_test_entry["urn"] == "urn:mullusi:schema:autonomous-test-generation-plan:1"
    assert autonomous_test_entry["surface"] == "testing"
    assert capability_upgrade_entry["path"] == "schemas/capability_upgrade_plan.schema.json"
    assert capability_upgrade_entry["urn"] == "urn:mullusi:schema:capability-upgrade-plan:1"
    assert capability_upgrade_entry["surface"] == "capability"
    assert orchestration_validation_entry["path"] == "schemas/deployment_orchestration_receipt_validation.schema.json"
    assert orchestration_validation_entry["urn"] == "urn:mullusi:schema:deployment-orchestration-receipt-validation:1"
    assert orchestration_validation_entry["surface"] == "deployment"
    assert publication_closure_validation_entry["path"] == "schemas/deployment_publication_closure_validation.schema.json"
    assert publication_closure_validation_entry["urn"] == "urn:mullusi:schema:deployment-publication-closure-validation:1"
    assert publication_closure_validation_entry["surface"] == "deployment"
    assert candidate_entry["path"] == "schemas/capability_candidate.schema.json"
    assert candidate_entry["urn"] == "urn:mullusi:schema:capability-candidate:1"
    assert candidate_entry["surface"] == "capability"
    assert maturity_entry["path"] == "schemas/capability_maturity.schema.json"
    assert maturity_entry["urn"] == "urn:mullusi:schema:capability-maturity:1"
    assert maturity_entry["surface"] == "capability"
    assert marketplace_entry["path"] == "schemas/marketplace_sdk_catalog.schema.json"
    assert marketplace_entry["urn"] == "urn:mullusi:schema:marketplace-sdk-catalog:1"
    assert marketplace_entry["surface"] == "marketplace"
    assert math_solver_receipt_entry["path"] == "schemas/math_solver_receipt.schema.json"
    assert math_solver_receipt_entry["urn"] == "urn:mullusi:schema:math-solver-receipt:1"
    assert math_solver_receipt_entry["surface"] == "math"
    assert economic_intelligence_entry["path"] == "schemas/economic_intelligence_snapshot.schema.json"
    assert economic_intelligence_entry["urn"] == "urn:mullusi:schema:economic-intelligence-snapshot:1"
    assert economic_intelligence_entry["surface"] == "commercial"
    assert federated_control_entry["path"] == "schemas/federated_control_snapshot.schema.json"
    assert federated_control_entry["urn"] == "urn:mullusi:schema:federated-control-snapshot:1"
    assert federated_control_entry["surface"] == "federation"
    assert memory_lattice_entry["path"] == "schemas/memory_lattice.schema.json"
    assert memory_lattice_entry["urn"] == "urn:mullusi:schema:memory-lattice:1"
    assert memory_lattice_entry["surface"] == "memory"
    assert policy_rule_entry["path"] == "schemas/policy_rule.schema.json"
    assert policy_rule_entry["urn"] == "urn:mullusi:schema:policy-rule:1"
    assert policy_rule_entry["surface"] == "policy"
    assert policy_bundle_entry["path"] == "schemas/policy_bundle.schema.json"
    assert policy_bundle_entry["urn"] == "urn:mullusi:schema:policy-bundle:1"
    assert policy_bundle_entry["surface"] == "policy"
    assert policy_evaluation_trace_entry["path"] == "schemas/policy_evaluation_trace.schema.json"
    assert policy_evaluation_trace_entry["urn"] == "urn:mullusi:schema:policy-evaluation-trace:1"
    assert policy_evaluation_trace_entry["surface"] == "policy"
    assert policy_proof_entry["path"] == "schemas/policy_proof_report.schema.json"
    assert policy_proof_entry["urn"] == "urn:mullusi:schema:policy-proof-report:1"
    assert policy_proof_entry["surface"] == "policy"
    assert trust_ledger_entry["path"] == "schemas/trust_ledger_bundle.schema.json"
    assert trust_ledger_entry["urn"] == "urn:mullusi:schema:trust-ledger-bundle:1"
    assert trust_ledger_entry["surface"] == "evidence"
    assert trust_anchor_entry["path"] == "schemas/trust_ledger_anchor_receipt.schema.json"
    assert trust_anchor_entry["urn"] == "urn:mullusi:schema:trust-ledger-anchor-receipt:1"
    assert trust_anchor_entry["surface"] == "evidence"
    assert domain_pack_entry["path"] == "schemas/domain_operating_pack.schema.json"
    assert domain_pack_entry["urn"] == "urn:mullusi:schema:domain-operating-pack:1"
    assert domain_pack_entry["surface"] == "domain"
    assert multimodal_entry["path"] == "schemas/multimodal_operation_receipt.schema.json"
    assert multimodal_entry["urn"] == "urn:mullusi:schema:multimodal-operation-receipt:1"
    assert multimodal_entry["surface"] == "multimodal"
    assert gateway_readiness_entry["path"] == "schemas/gateway_publication_readiness.schema.json"
    assert gateway_readiness_entry["urn"] == "urn:mullusi:schema:gateway-publication-readiness:1"
    assert gateway_readiness_entry["surface"] == "deployment"
    assert gateway_receipt_validation_entry["path"] == "schemas/gateway_publication_receipt_validation.schema.json"
    assert gateway_receipt_validation_entry["urn"] == "urn:mullusi:schema:gateway-publication-receipt-validation:1"
    assert gateway_receipt_validation_entry["surface"] == "deployment"
    assert goal_entry["path"] == "schemas/goal.schema.json"
    assert goal_entry["urn"] == "urn:mullusi:schema:goal:1"
    assert goal_entry["surface"] == "planning"
    assert temporal_entry["path"] == "schemas/temporal_operation_receipt.schema.json"
    assert temporal_entry["urn"] == "urn:mullusi:schema:temporal-operation-receipt:1"
    assert temporal_entry["surface"] == "temporal"
    assert temporal_resolution_entry["path"] == "schemas/temporal_resolution_receipt.schema.json"
    assert temporal_resolution_entry["urn"] == "urn:mullusi:schema:temporal-resolution-receipt:1"
    assert temporal_resolution_entry["surface"] == "temporal"
    assert temporal_evidence_entry["path"] == "schemas/temporal_evidence_freshness_receipt.schema.json"
    assert temporal_evidence_entry["urn"] == "urn:mullusi:schema:temporal-evidence-freshness-receipt:1"
    assert temporal_evidence_entry["surface"] == "temporal"
    assert temporal_reapproval_entry["path"] == "schemas/temporal_reapproval_receipt.schema.json"
    assert temporal_reapproval_entry["urn"] == "urn:mullusi:schema:temporal-reapproval-receipt:1"
    assert temporal_reapproval_entry["surface"] == "temporal"
    assert temporal_dispatch_window_entry["path"] == "schemas/temporal_dispatch_window_receipt.schema.json"
    assert temporal_dispatch_window_entry["urn"] == "urn:mullusi:schema:temporal-dispatch-window-receipt:1"
    assert temporal_dispatch_window_entry["surface"] == "temporal"
    assert temporal_budget_window_entry["path"] == "schemas/temporal_budget_window_receipt.schema.json"
    assert temporal_budget_window_entry["urn"] == "urn:mullusi:schema:temporal-budget-window-receipt:1"
    assert temporal_budget_window_entry["surface"] == "temporal"
    assert temporal_causal_order_entry["path"] == "schemas/temporal_causal_order_receipt.schema.json"
    assert temporal_causal_order_entry["urn"] == "urn:mullusi:schema:temporal-causal-order-receipt:1"
    assert temporal_causal_order_entry["surface"] == "temporal"
    assert temporal_monotonic_duration_entry["path"] == "schemas/temporal_monotonic_duration_receipt.schema.json"
    assert (
        temporal_monotonic_duration_entry["urn"]
        == "urn:mullusi:schema:temporal-monotonic-duration-receipt:1"
    )
    assert temporal_monotonic_duration_entry["surface"] == "temporal"
    assert temporal_accepted_risk_entry["path"] == "schemas/temporal_accepted_risk_expiry_receipt.schema.json"
    assert (
        temporal_accepted_risk_entry["urn"]
        == "urn:mullusi:schema:temporal-accepted-risk-expiry-receipt:1"
    )
    assert temporal_accepted_risk_entry["surface"] == "temporal"
    assert temporal_credential_entry["path"] == "schemas/temporal_credential_expiry_receipt.schema.json"
    assert temporal_credential_entry["urn"] == "urn:mullusi:schema:temporal-credential-expiry-receipt:1"
    assert temporal_credential_entry["surface"] == "temporal"
    assert temporal_retention_entry["path"] == "schemas/temporal_retention_window_receipt.schema.json"
    assert temporal_retention_entry["urn"] == "urn:mullusi:schema:temporal-retention-window-receipt:1"
    assert temporal_retention_entry["surface"] == "temporal"
    assert temporal_rate_limit_entry["path"] == "schemas/temporal_rate_limit_window_receipt.schema.json"
    assert temporal_rate_limit_entry["urn"] == "urn:mullusi:schema:temporal-rate-limit-window-receipt:1"
    assert temporal_rate_limit_entry["surface"] == "temporal"
    assert temporal_retry_window_entry["path"] == "schemas/temporal_retry_window_receipt.schema.json"
    assert temporal_retry_window_entry["urn"] == "urn:mullusi:schema:temporal-retry-window-receipt:1"
    assert temporal_retry_window_entry["surface"] == "temporal"
    assert temporal_lease_window_entry["path"] == "schemas/temporal_lease_window_receipt.schema.json"
    assert temporal_lease_window_entry["urn"] == "urn:mullusi:schema:temporal-lease-window-receipt:1"
    assert temporal_lease_window_entry["surface"] == "temporal"
    assert temporal_idempotency_window_entry["path"] == "schemas/temporal_idempotency_window_receipt.schema.json"
    assert (
        temporal_idempotency_window_entry["urn"]
        == "urn:mullusi:schema:temporal-idempotency-window-receipt:1"
    )
    assert temporal_idempotency_window_entry["surface"] == "temporal"
    assert temporal_missed_run_entry["path"] == "schemas/temporal_missed_run_receipt.schema.json"
    assert temporal_missed_run_entry["urn"] == "urn:mullusi:schema:temporal-missed-run-receipt:1"
    assert temporal_missed_run_entry["surface"] == "temporal"
    assert temporal_recurrence_window_entry["path"] == "schemas/temporal_recurrence_window_receipt.schema.json"
    assert (
        temporal_recurrence_window_entry["urn"]
        == "urn:mullusi:schema:temporal-recurrence-window-receipt:1"
    )
    assert temporal_recurrence_window_entry["surface"] == "temporal"
    assert temporal_memory_entry["path"] == "schemas/temporal_memory_receipt.schema.json"
    assert temporal_memory_entry["urn"] == "urn:mullusi:schema:temporal-memory-receipt:1"
    assert temporal_memory_entry["surface"] == "temporal"
    assert temporal_memory_refresh_entry["path"] == "schemas/temporal_memory_refresh_receipt.schema.json"
    assert temporal_memory_refresh_entry["urn"] == "urn:mullusi:schema:temporal-memory-refresh-receipt:1"
    assert temporal_memory_refresh_entry["surface"] == "temporal"
    assert scheduler_entry["path"] == "schemas/temporal_scheduler_receipt.schema.json"
    assert scheduler_entry["urn"] == "urn:mullusi:schema:temporal-scheduler-receipt:1"
    assert scheduler_entry["surface"] == "temporal"
    assert simulation_entry["path"] == "schemas/simulation_receipt.schema.json"
    assert simulation_entry["urn"] == "urn:mullusi:schema:simulation-receipt:1"
    assert simulation_entry["surface"] == "simulation"
    assert supervisor_tick_entry["path"] == "schemas/supervisor_tick.schema.json"
    assert supervisor_tick_entry["urn"] == "urn:mullusi:schema:supervisor-tick:1"
    assert supervisor_tick_entry["surface"] == "supervisor"
    assert supervisor_checkpoint_entry["path"] == "schemas/supervisor_checkpoint.schema.json"
    assert supervisor_checkpoint_entry["urn"] == "urn:mullusi:schema:supervisor-checkpoint:1"
    assert supervisor_checkpoint_entry["surface"] == "supervisor"
    assert livelock_entry["path"] == "schemas/livelock_record.schema.json"
    assert livelock_entry["urn"] == "urn:mullusi:schema:livelock-record:1"
    assert livelock_entry["surface"] == "supervisor"
    assert workflow_mining_entry["path"] == "schemas/workflow_mining_report.schema.json"
    assert workflow_mining_entry["urn"] == "urn:mullusi:schema:workflow-mining-report:1"
    assert workflow_mining_entry["surface"] == "workflow"
    assert universal_action_orchestration_entry["path"] == "schemas/universal_action_orchestration.schema.json"
    assert universal_action_orchestration_entry["urn"] == "urn:mullusi:schema:universal-action-orchestration:1"
    assert universal_action_orchestration_entry["surface"] == "orchestration"
    assert universal_action_orchestration_validation_receipt_entry["path"] == (
        "schemas/universal_action_orchestration_validation_receipt.schema.json"
    )
    assert universal_action_orchestration_validation_receipt_entry["urn"] == (
        "urn:mullusi:schema:universal-action-orchestration-validation-receipt:1"
    )
    assert universal_action_orchestration_validation_receipt_entry["surface"] == "orchestration"
    assert worker_mesh_entry["path"] == "schemas/worker_mesh.schema.json"
    assert worker_mesh_entry["urn"] == "urn:mullusi:schema:worker-mesh:1"
    assert worker_mesh_entry["surface"] == "worker"
    assert worker_failure_entry["path"] == "schemas/worker_failure_receipt.schema.json"
    assert worker_failure_entry["urn"] == "urn:mullusi:schema:worker-failure-receipt:1"
    assert worker_failure_entry["surface"] == "worker"
    assert read_only_worker_entry["path"] == "schemas/read_only_worker_binding.schema.json"
    assert read_only_worker_entry["urn"] == "urn:mullusi:schema:read-only-worker-binding:1"
    assert read_only_worker_entry["surface"] == "worker"
    assert read_only_worker_lease_preflight_entry["path"] == "schemas/read_only_worker_lease_preflight.schema.json"
    assert read_only_worker_lease_preflight_entry["urn"] == "urn:mullusi:schema:read-only-worker-lease-preflight:1"
    assert read_only_worker_lease_preflight_entry["surface"] == "worker"
    assert read_only_worker_rehearsal_receipt_entry["path"] == (
        "schemas/read_only_worker_rehearsal_receipt.schema.json"
    )
    assert read_only_worker_rehearsal_receipt_entry["urn"] == (
        "urn:mullusi:schema:read-only-worker-rehearsal-receipt:1"
    )
    assert read_only_worker_rehearsal_receipt_entry["surface"] == "worker"
    assert read_only_worker_runtime_receipt_handoff_entry["path"] == (
        "schemas/read_only_worker_runtime_receipt_handoff.schema.json"
    )
    assert read_only_worker_runtime_receipt_handoff_entry["urn"] == (
        "urn:mullusi:schema:read-only-worker-runtime-receipt-handoff:1"
    )
    assert read_only_worker_runtime_receipt_handoff_entry["surface"] == "worker"
    assert read_only_worker_runtime_receipt_emitter_dry_run_entry["path"] == (
        "schemas/read_only_worker_runtime_receipt_emitter_dry_run.schema.json"
    )
    assert read_only_worker_runtime_receipt_emitter_dry_run_entry["urn"] == (
        "urn:mullusi:schema:read-only-worker-runtime-receipt-emitter-dry-run:1"
    )
    assert read_only_worker_runtime_receipt_emitter_dry_run_entry["surface"] == "worker"
    assert read_only_worker_runtime_runner_binding_witness_entry["path"] == (
        "schemas/read_only_worker_runtime_runner_binding_witness.schema.json"
    )
    assert read_only_worker_runtime_runner_binding_witness_entry["urn"] == (
        "urn:mullusi:schema:read-only-worker-runtime-runner-binding-witness:1"
    )
    assert read_only_worker_runtime_runner_binding_witness_entry["surface"] == "worker"
    assert read_only_worker_runtime_receipt_candidate_entry["path"] == (
        "schemas/read_only_worker_runtime_receipt_candidate.schema.json"
    )
    assert read_only_worker_runtime_receipt_candidate_entry["urn"] == (
        "urn:mullusi:schema:read-only-worker-runtime-receipt-candidate:1"
    )
    assert read_only_worker_runtime_receipt_candidate_entry["surface"] == "worker"
    assert read_only_worker_runtime_receipt_schema_binding_witness_entry["path"] == (
        "schemas/read_only_worker_runtime_receipt_schema_binding_witness.schema.json"
    )
    assert read_only_worker_runtime_receipt_schema_binding_witness_entry["urn"] == (
        "urn:mullusi:schema:read-only-worker-runtime-receipt-schema-binding-witness:1"
    )
    assert read_only_worker_runtime_receipt_schema_binding_witness_entry["surface"] == "worker"
    assert read_only_worker_runtime_receipt_store_write_path_witness_entry["path"] == (
        "schemas/read_only_worker_runtime_receipt_store_write_path_witness.schema.json"
    )
    assert read_only_worker_runtime_receipt_store_write_path_witness_entry["urn"] == (
        "urn:mullusi:schema:read-only-worker-runtime-receipt-store-write-path-witness:1"
    )
    assert read_only_worker_runtime_receipt_store_write_path_witness_entry["surface"] == "worker"
    assert read_only_worker_runtime_runner_registration_witness_entry["path"] == (
        "schemas/read_only_worker_runtime_runner_registration_witness.schema.json"
    )
    assert read_only_worker_runtime_runner_registration_witness_entry["urn"] == (
        "urn:mullusi:schema:read-only-worker-runtime-runner-registration-witness:1"
    )
    assert read_only_worker_runtime_runner_registration_witness_entry["surface"] == "worker"
    assert read_only_worker_runtime_dispatch_endpoint_registration_witness_entry["path"] == (
        "schemas/read_only_worker_runtime_dispatch_endpoint_registration_witness.schema.json"
    )
    assert read_only_worker_runtime_dispatch_endpoint_registration_witness_entry["urn"] == (
        "urn:mullusi:schema:read-only-worker-runtime-dispatch-endpoint-registration-witness:1"
    )
    assert read_only_worker_runtime_dispatch_endpoint_registration_witness_entry["surface"] == "worker"
    assert read_only_worker_runtime_receipt_emitter_registration_witness_entry["path"] == (
        "schemas/read_only_worker_runtime_receipt_emitter_registration_witness.schema.json"
    )
    assert read_only_worker_runtime_receipt_emitter_registration_witness_entry["urn"] == (
        "urn:mullusi:schema:read-only-worker-runtime-receipt-emitter-registration-witness:1"
    )
    assert read_only_worker_runtime_receipt_emitter_registration_witness_entry["surface"] == "worker"
    assert read_only_worker_runtime_receipt_schema_binding_activation_witness_entry["path"] == (
        "schemas/read_only_worker_runtime_receipt_schema_binding_activation_witness.schema.json"
    )
    assert read_only_worker_runtime_receipt_schema_binding_activation_witness_entry["urn"] == (
        "urn:mullusi:schema:read-only-worker-runtime-receipt-schema-binding-activation-witness:1"
    )
    assert read_only_worker_runtime_receipt_schema_binding_activation_witness_entry["surface"] == "worker"
    assert read_only_worker_runtime_receipt_store_activation_witness_entry["path"] == (
        "schemas/read_only_worker_runtime_receipt_store_activation_witness.schema.json"
    )
    assert read_only_worker_runtime_receipt_store_activation_witness_entry["urn"] == (
        "urn:mullusi:schema:read-only-worker-runtime-receipt-store-activation-witness:1"
    )
    assert read_only_worker_runtime_receipt_store_activation_witness_entry["surface"] == "worker"
    assert read_only_worker_runtime_receipt_emission_admission_witness_entry["path"] == (
        "schemas/read_only_worker_runtime_receipt_emission_admission_witness.schema.json"
    )
    assert read_only_worker_runtime_receipt_emission_admission_witness_entry["urn"] == (
        "urn:mullusi:schema:read-only-worker-runtime-receipt-emission-admission-witness:1"
    )
    assert read_only_worker_runtime_receipt_emission_admission_witness_entry["surface"] == "worker"
    assert read_only_worker_runtime_active_lease_admission_witness_entry["path"] == (
        "schemas/read_only_worker_runtime_active_lease_admission_witness.schema.json"
    )
    assert read_only_worker_runtime_active_lease_admission_witness_entry["urn"] == (
        "urn:mullusi:schema:read-only-worker-runtime-active-lease-admission-witness:1"
    )
    assert read_only_worker_runtime_active_lease_admission_witness_entry["surface"] == "worker"
    assert read_only_worker_runtime_authority_chain_witness_entry["path"] == (
        "schemas/read_only_worker_runtime_authority_chain_witness.schema.json"
    )
    assert read_only_worker_runtime_authority_chain_witness_entry["urn"] == (
        "urn:mullusi:schema:read-only-worker-runtime-authority-chain-witness:1"
    )
    assert read_only_worker_runtime_authority_chain_witness_entry["surface"] == "worker"
    assert read_only_worker_runtime_dispatch_admission_witness_entry["path"] == (
        "schemas/read_only_worker_runtime_dispatch_admission_witness.schema.json"
    )
    assert read_only_worker_runtime_dispatch_admission_witness_entry["urn"] == (
        "urn:mullusi:schema:read-only-worker-runtime-dispatch-admission-witness:1"
    )
    assert read_only_worker_runtime_dispatch_admission_witness_entry["surface"] == "worker"
    assert world_state_entry["path"] == "schemas/world_state.schema.json"
    assert world_state_entry["urn"] == "urn:mullusi:schema:world-state:1"
    assert world_state_entry["surface"] == "world"
    assert reflex_entry["path"] == "schemas/reflex_deployment_witness_envelope.schema.json"
    assert reflex_entry["urn"] == "urn:mullusi:schema:reflex-deployment-witness-envelope:1"
    assert reflex_entry["surface"] == "deployment"
    assert receipt_entry["path"] == "schemas/reflex_deployment_witness_validator_receipt.schema.json"
    assert receipt_entry["urn"] == "urn:mullusi:schema:reflex-deployment-witness-validator-receipt:1"
    assert receipt_entry["surface"] == "deployment"


def test_protocol_manifest_defines_open_and_closed_surfaces() -> None:
    manifest = load_manifest()
    claim_boundary = manifest["claim_boundary"]

    assert claim_boundary["open_surface"] == OPEN_SURFACE
    assert claim_boundary["closed_surface"] == CLOSED_SURFACE
    assert claim_boundary["reference_runtime"] == "mullu-control-plane"
    assert claim_boundary["third_party_implementation_allowed"] is True
    assert manifest["compatibility"]["runtime_private_modules_are_not_protocol_contracts"] is True


def test_protocol_manifest_urns_match_schema_files() -> None:
    manifest = load_manifest()

    for entry in manifest["schemas"]:
        assert entry["path"].startswith("schemas/")
        assert entry["urn"].startswith("urn:mullusi:schema:")
        assert entry["schema_id"]
        assert entry["surface"]


def test_protocol_manifest_rejects_missing_schema_entry() -> None:
    manifest = load_manifest()
    manifest["schemas"] = manifest["schemas"][:-1]

    errors = validate_protocol_manifest(manifest)

    assert any("manifest missing public schemas" in error for error in errors)


def test_protocol_manifest_rejects_runtime_as_open_schema() -> None:
    manifest = load_manifest()
    manifest["schemas"].append(
        {
            "schema_id": "runtime-core",
            "path": "mcoi/mcoi_runtime/core/runtime.py",
            "urn": "urn:mullusi:schema:runtime-core:1",
            "surface": "runtime",
        }
    )

    errors = validate_protocol_manifest(manifest)

    assert any("manifest references non-public schemas" in error for error in errors)
    assert any("schema path must start with schemas/" in error for error in errors)
