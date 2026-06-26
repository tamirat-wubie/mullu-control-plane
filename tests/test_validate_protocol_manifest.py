"""Tests for the public governance protocol manifest.

Purpose: prove deployment orchestration receipts and effect assurance records
are indexed as public handoff contracts.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, PRS]
Dependencies: scripts.validate_protocol_manifest and schema manifest JSON.
Invariants:
  - Every public top-level schema is listed in the protocol manifest.
  - Deployment orchestration receipts have a stable schema id and URN.
  - Effect assurance has a stable schema id and URN.
  - Missing public handoff schema entries fail closed.
"""

from __future__ import annotations

import scripts.validate_protocol_manifest as protocol_manifest
from scripts.validate_protocol_manifest import load_manifest, validate_protocol_manifest


def test_protocol_manifest_indexes_deployment_orchestration_receipt() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    receipt_entry = entries["deployment-orchestration-receipt"]

    assert validate_protocol_manifest(manifest) == []
    assert receipt_entry["path"] == "schemas/deployment_orchestration_receipt.schema.json"
    assert receipt_entry["urn"] == "urn:mullusi:schema:deployment-orchestration-receipt:1"
    assert receipt_entry["surface"] == "deployment"


def test_protocol_manifest_indexes_agent_identity() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    identity_entry = entries["agent-identity"]
    runtime_entry = entries["agent-runtime-snapshot"]
    authority_entry = entries["enterprise-authority"]

    assert validate_protocol_manifest(manifest) == []
    assert identity_entry["path"] == "schemas/agent_identity.schema.json"
    assert identity_entry["urn"] == "urn:mullusi:schema:agent-identity:1"
    assert identity_entry["surface"] == "identity"
    assert runtime_entry["path"] == "schemas/agent_runtime_snapshot.schema.json"
    assert runtime_entry["urn"] == "urn:mullusi:schema:agent-runtime-snapshot:1"
    assert runtime_entry["surface"] == "runtime"
    assert authority_entry["path"] == "schemas/enterprise_authority.schema.json"
    assert authority_entry["urn"] == "urn:mullusi:schema:enterprise-authority:1"
    assert authority_entry["surface"] == "identity"


def test_protocol_manifest_indexes_agentic_service_harness_github_repo_task_intake() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    intake_entry = entries["agentic-service-harness-github-repo-task-intake"]

    assert validate_protocol_manifest(manifest) == []
    assert intake_entry["path"] == "schemas/agentic_service_harness_github_repo_task_intake.schema.json"
    assert intake_entry["urn"] == "urn:mullusi:schema:agentic-service-harness-github-repo-task-intake:1"
    assert intake_entry["surface"] == "runtime"


def test_protocol_manifest_indexes_agentic_service_harness_dashboard_data_contract() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    dashboard_entry = entries["agentic-service-harness-dashboard-data-contract"]

    assert validate_protocol_manifest(manifest) == []
    assert dashboard_entry["path"] == "schemas/agentic_service_harness_dashboard_data_contract.schema.json"
    assert dashboard_entry["urn"] == "urn:mullusi:schema:agentic-service-harness-dashboard-data-contract:1"
    assert dashboard_entry["surface"] == "runtime"


def test_protocol_manifest_indexes_agentic_service_harness_adapter_registry_contract() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    registry_entry = entries["agentic-service-harness-adapter-registry-contract"]

    assert validate_protocol_manifest(manifest) == []
    assert registry_entry["path"] == "schemas/agentic_service_harness_adapter_registry_contract.schema.json"
    assert registry_entry["urn"] == "urn:mullusi:schema:agentic-service-harness-adapter-registry-contract:1"
    assert registry_entry["surface"] == "runtime"


def test_protocol_manifest_indexes_agentic_service_harness_approved_branch_workspace_creation_preflight() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    workspace_entry = entries[
        "agentic-service-harness-approved-branch-workspace-creation-preflight"
    ]

    assert validate_protocol_manifest(manifest) == []
    assert workspace_entry["path"] == (
        "schemas/agentic_service_harness_approved_branch_workspace_creation_preflight.schema.json"
    )
    assert workspace_entry["urn"] == (
        "urn:mullusi:schema:agentic-service-harness-approved-branch-workspace-creation-preflight:1"
    )
    assert workspace_entry["surface"] == "runtime"


def test_protocol_manifest_indexes_agentic_service_harness_task_record_write_uao_admission_preflight() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    task_record_entry = entries[
        "agentic-service-harness-task-record-write-uao-admission-preflight"
    ]

    assert validate_protocol_manifest(manifest) == []
    assert task_record_entry["path"] == (
        "schemas/agentic_service_harness_task_record_write_uao_admission_preflight.schema.json"
    )
    assert task_record_entry["urn"] == (
        "urn:mullusi:schema:agentic-service-harness-task-record-write-uao-admission-preflight:1"
    )
    assert task_record_entry["surface"] == "runtime"


def test_protocol_manifest_indexes_agentic_service_harness_receipt_store_append_preflight() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    append_entry = entries[
        "agentic-service-harness-receipt-store-append-preflight"
    ]

    assert validate_protocol_manifest(manifest) == []
    assert append_entry["path"] == (
        "schemas/agentic_service_harness_receipt_store_append_preflight.schema.json"
    )
    assert append_entry["urn"] == (
        "urn:mullusi:schema:agentic-service-harness-receipt-store-append-preflight:1"
    )
    assert append_entry["surface"] == "runtime"


def test_protocol_manifest_indexes_agentic_service_harness_executed_test_receipt_admission_preflight() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    executed_test_entry = entries[
        "agentic-service-harness-executed-test-receipt-admission-preflight"
    ]

    assert validate_protocol_manifest(manifest) == []
    assert executed_test_entry["path"] == (
        "schemas/agentic_service_harness_executed_test_receipt_admission_preflight.schema.json"
    )
    assert executed_test_entry["urn"] == (
        "urn:mullusi:schema:agentic-service-harness-executed-test-receipt-admission-preflight:1"
    )
    assert executed_test_entry["surface"] == "runtime"


def test_protocol_manifest_indexes_agentic_service_harness_non_empty_diff_receipt_admission_preflight() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    diff_entry = entries[
        "agentic-service-harness-non-empty-diff-receipt-admission-preflight"
    ]

    assert validate_protocol_manifest(manifest) == []
    assert diff_entry["path"] == (
        "schemas/agentic_service_harness_non_empty_diff_receipt_admission_preflight.schema.json"
    )
    assert diff_entry["urn"] == (
        "urn:mullusi:schema:agentic-service-harness-non-empty-diff-receipt-admission-preflight:1"
    )
    assert diff_entry["surface"] == "runtime"


def test_protocol_manifest_indexes_agentic_service_harness_evidence_bundle_projection() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    evidence_entry = entries["agentic-service-harness-evidence-bundle-projection"]

    assert validate_protocol_manifest(manifest) == []
    assert evidence_entry["path"] == "schemas/agentic_service_harness_evidence_bundle_projection.schema.json"
    assert evidence_entry["urn"] == "urn:mullusi:schema:agentic-service-harness-evidence-bundle-projection:1"
    assert evidence_entry["surface"] == "runtime"


def test_protocol_manifest_indexes_agentic_service_harness_receipt_evidence_read_models() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    receipt_entry = entries["agentic-service-harness-receipt-evidence-read-models"]

    assert validate_protocol_manifest(manifest) == []
    assert receipt_entry["path"] == "schemas/agentic_service_harness_receipt_evidence_read_models.schema.json"
    assert receipt_entry["urn"] == "urn:mullusi:schema:agentic-service-harness-receipt-evidence-read-models:1"
    assert receipt_entry["surface"] == "runtime"


def test_protocol_manifest_indexes_governed_symbolic_loop_contract() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    loop_entry = entries["governed-symbolic-loop-contract"]

    assert validate_protocol_manifest(manifest) == []
    assert loop_entry["path"] == "schemas/governed_symbolic_loop_contract.schema.json"
    assert loop_entry["urn"] == "urn:mullusi:schema:governed-symbolic-loop-contract:1"
    assert loop_entry["surface"] == "governance"


def test_protocol_manifest_indexes_governed_planning_profile() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    profile_entry = entries["governed-planning-profile"]
    report_entry = entries["governed-planning-profile-admission-report"]
    dossier_entry = entries["governed-planning-profile-shadow-dossier"]
    operator_evidence_entry = entries["governed-planning-profile-operator-shadow-pilot-evidence"]
    operator_observation_entry = entries[
        "governed-planning-profile-operator-shadow-pilot-observation-receipt"
    ]
    runtime_approval_entry = entries[
        "governed-planning-profile-runtime-promotion-approval-packet"
    ]
    replay_recovery_entry = entries[
        "governed-planning-profile-replay-recovery-witness"
    ]
    terminal_closure_entry = entries[
        "governed-planning-profile-terminal-closure-certificate"
    ]
    runtime_authorization_request_entry = entries[
        "governed-planning-profile-runtime-authorization-request"
    ]
    generic_continuation_rejection_entry = entries[
        "governed-planning-profile-runtime-authorization-generic-continuation-rejection"
    ]
    approval_witness_template_entry = entries[
        "governed-planning-profile-runtime-authorization-approval-witness-template"
    ]
    signed_approval_intake_entry = entries[
        "governed-planning-profile-runtime-authorization-signed-approval-intake"
    ]
    signed_approval_generic_rejection_entry = entries[
        "governed-planning-profile-runtime-authorization-signed-approval-generic-continuation-rejection"
    ]

    assert validate_protocol_manifest(manifest) == []
    assert profile_entry["path"] == "schemas/governed_planning_profile.schema.json"
    assert profile_entry["urn"] == "urn:mullusi:schema:governed-planning-profile:1"
    assert profile_entry["surface"] == "planning"
    assert report_entry["path"] == "schemas/governed_planning_profile_admission_report.schema.json"
    assert report_entry["urn"] == "urn:mullusi:schema:governed-planning-profile-admission-report:1"
    assert report_entry["surface"] == "planning"
    assert dossier_entry["path"] == "schemas/governed_planning_profile_shadow_dossier.schema.json"
    assert dossier_entry["urn"] == "urn:mullusi:schema:governed-planning-profile-shadow-dossier:1"
    assert dossier_entry["surface"] == "planning"
    assert operator_evidence_entry["path"] == (
        "schemas/governed_planning_profile_operator_shadow_pilot_evidence.schema.json"
    )
    assert operator_evidence_entry["urn"] == (
        "urn:mullusi:schema:governed-planning-profile-operator-shadow-pilot-evidence:1"
    )
    assert operator_evidence_entry["surface"] == "planning"
    assert operator_observation_entry["path"] == (
        "schemas/governed_planning_profile_operator_shadow_pilot_observation_receipt.schema.json"
    )
    assert operator_observation_entry["urn"] == (
        "urn:mullusi:schema:governed-planning-profile-operator-shadow-pilot-observation-receipt:1"
    )
    assert operator_observation_entry["surface"] == "planning"
    assert runtime_approval_entry["path"] == (
        "schemas/governed_planning_profile_runtime_promotion_approval_packet.schema.json"
    )
    assert runtime_approval_entry["urn"] == (
        "urn:mullusi:schema:governed-planning-profile-runtime-promotion-approval-packet:1"
    )
    assert runtime_approval_entry["surface"] == "planning"
    assert replay_recovery_entry["path"] == (
        "schemas/governed_planning_profile_replay_recovery_witness.schema.json"
    )
    assert replay_recovery_entry["urn"] == (
        "urn:mullusi:schema:governed-planning-profile-replay-recovery-witness:1"
    )
    assert replay_recovery_entry["surface"] == "planning"
    assert terminal_closure_entry["path"] == (
        "schemas/governed_planning_profile_terminal_closure_certificate.schema.json"
    )
    assert terminal_closure_entry["urn"] == (
        "urn:mullusi:schema:governed-planning-profile-terminal-closure-certificate:1"
    )
    assert terminal_closure_entry["surface"] == "planning"
    assert runtime_authorization_request_entry["path"] == (
        "schemas/governed_planning_profile_runtime_authorization_request.schema.json"
    )
    assert runtime_authorization_request_entry["urn"] == (
        "urn:mullusi:schema:governed-planning-profile-runtime-authorization-request:1"
    )
    assert runtime_authorization_request_entry["surface"] == "planning"
    assert generic_continuation_rejection_entry["path"] == (
        "schemas/governed_planning_profile_runtime_authorization_generic_continuation_rejection.schema.json"
    )
    assert generic_continuation_rejection_entry["urn"] == (
        "urn:mullusi:schema:governed-planning-profile-runtime-authorization-generic-continuation-rejection:1"
    )
    assert generic_continuation_rejection_entry["surface"] == "planning"
    assert approval_witness_template_entry["path"] == (
        "schemas/governed_planning_profile_runtime_authorization_approval_witness_template.schema.json"
    )
    assert approval_witness_template_entry["urn"] == (
        "urn:mullusi:schema:governed-planning-profile-runtime-authorization-approval-witness-template:1"
    )
    assert approval_witness_template_entry["surface"] == "planning"
    assert signed_approval_intake_entry["path"] == (
        "schemas/governed_planning_profile_runtime_authorization_signed_approval_intake.schema.json"
    )
    assert signed_approval_intake_entry["urn"] == (
        "urn:mullusi:schema:governed-planning-profile-runtime-authorization-signed-approval-intake:1"
    )
    assert signed_approval_intake_entry["surface"] == "planning"
    assert signed_approval_generic_rejection_entry["path"] == (
        "schemas/governed_planning_profile_runtime_authorization_signed_approval_generic_continuation_rejection.schema.json"
    )
    assert signed_approval_generic_rejection_entry["urn"] == (
        "urn:mullusi:schema:governed-planning-profile-runtime-authorization-signed-approval-generic-continuation-rejection:1"
    )
    assert signed_approval_generic_rejection_entry["surface"] == "planning"


def test_protocol_manifest_indexes_search_decision() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    search_entry = entries["search-decision"]

    assert validate_protocol_manifest(manifest) == []
    assert search_entry["path"] == "schemas/search_decision.schema.json"
    assert search_entry["urn"] == "urn:mullusi:schema:search-decision:1"
    assert search_entry["surface"] == "search"


def test_protocol_manifest_indexes_search_receipt() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    search_entry = entries["search-receipt"]

    assert validate_protocol_manifest(manifest) == []
    assert search_entry["path"] == "schemas/search_receipt.schema.json"
    assert search_entry["urn"] == "urn:mullusi:schema:search-receipt:1"
    assert search_entry["surface"] == "search"


def test_protocol_manifest_indexes_research_epistemics_profile() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    profile_entry = entries["research-epistemics-profile"]

    assert validate_protocol_manifest(manifest) == []
    assert profile_entry["path"] == "schemas/research_epistemics_profile.schema.json"
    assert profile_entry["urn"] == "urn:mullusi:schema:research-epistemics-profile:1"
    assert profile_entry["surface"] == "research"


def test_protocol_manifest_indexes_capture_policy_decision_ledger() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    ledger_entry = entries["capture-policy-decision-ledger"]

    assert validate_protocol_manifest(manifest) == []
    assert ledger_entry["path"] == "schemas/capture_policy_decision_ledger.schema.json"
    assert ledger_entry["urn"] == "urn:mullusi:schema:capture-policy-decision-ledger:1"
    assert ledger_entry["surface"] == "data_governance"


def test_protocol_manifest_indexes_component_registry() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    registry_entry = entries["component-registry"]
    router_entry = entries["component-router-inventory"]
    ownership_entry = entries["component-route-family-ownership"]
    promotion_preflight_entry = entries["component-route-family-promotion-preflight"]
    promotion_witness_entry = entries["component-route-family-promotion-witness-requirements"]
    promotion_witness_evidence_entry = entries["component-route-family-promotion-witness-evidence"]
    promotion_approval_candidates_entry = entries["component-route-family-promotion-approval-candidates"]
    promotion_approval_intake_entry = entries["component-route-family-promotion-approval-intake"]
    promotion_submitted_evidence_verifier_entry = entries[
        "component-route-family-promotion-submitted-evidence-verifier"
    ]
    promotion_submitted_evidence_records_entry = entries[
        "component-route-family-promotion-submitted-evidence-records"
    ]
    promotion_submitted_evidence_payload_examples_entry = entries[
        "component-route-family-promotion-submitted-evidence-payload-examples"
    ]
    promotion_operator_submitted_evidence_records_entry = entries[
        "component-route-family-promotion-operator-submitted-evidence-records"
    ]
    promotion_gate_satisfaction_evaluator_entry = entries[
        "component-route-family-promotion-gate-satisfaction-evaluator"
    ]
    promotion_authority_decision_report_entry = entries[
        "component-route-family-promotion-authority-decision-report"
    ]
    promotion_authority_upgrade_witness_decision_report_entry = entries[
        "component-route-family-promotion-authority-upgrade-witness-decision-report"
    ]
    promotion_product_ownership_decision_report_entry = entries[
        "component-route-family-promotion-product-ownership-decision-report"
    ]
    promotion_terminal_closure_denial_report_entry = entries[
        "component-route-family-promotion-terminal-closure-denial-report"
    ]
    promotion_missing_evidence_ledger_entry = entries[
        "component-route-family-promotion-missing-evidence-ledger"
    ]
    promotion_router_inventory_delta_candidate_entry = entries[
        "component-route-family-promotion-router-inventory-delta-candidate"
    ]
    promotion_router_inventory_delta_witness_requirements_entry = entries[
        "component-route-family-promotion-router-inventory-delta-witness-requirements"
    ]
    promotion_router_inventory_delta_witness_minting_preflight_entry = entries[
        "component-route-family-promotion-router-inventory-delta-witness-minting-preflight"
    ]
    promotion_router_inventory_delta_witness_minting_denial_report_entry = entries[
        "component-route-family-promotion-router-inventory-delta-witness-minting-denial-report"
    ]
    promotion_router_inventory_delta_witness_remediation_plan_entry = entries[
        "component-route-family-promotion-router-inventory-delta-witness-remediation-plan"
    ]
    promotion_router_inventory_delta_witness_remediation_evidence_request_entry = entries[
        "component-route-family-promotion-router-inventory-delta-witness-remediation-evidence-request"
    ]
    promotion_router_inventory_delta_witness_remediation_evidence_request_status_ledger_entry = entries[
        "component-route-family-promotion-router-inventory-delta-witness-remediation-evidence-request-status-ledger"
    ]
    promotion_route_binding_decision_report_entry = entries[
        "component-route-family-promotion-route-binding-decision-report"
    ]
    promotion_lifecycle_transition_decision_report_entry = entries[
        "component-route-family-promotion-lifecycle-transition-decision-report"
    ]
    promotion_authority_upgrade_decision_report_entry = entries[
        "component-route-family-promotion-authority-upgrade-witness-decision-report"
    ]
    proof_entry = entries["component-proof-binding"]
    read_model_entry = entries["component-read-model"]
    graph_entry = entries["component-graph"]
    autopsy_entry = entries["component-autopsy"]
    simulation_entry = entries["component-request-simulation"]
    bundle_compilation_entry = entries["component-bundle-compilation"]
    lifecycle_entry = entries["component-lifecycle-transition-receipts"]
    authority_witness_entry = entries["component-authority-envelope-witnesses"]
    dead_component_entry = entries["component-dead-component-detection"]

    assert validate_protocol_manifest(manifest) == []
    assert registry_entry["path"] == "schemas/component_registry.schema.json"
    assert registry_entry["urn"] == "urn:mullusi:schema:component-registry:1"
    assert registry_entry["surface"] == "governance"
    assert router_entry["path"] == "schemas/component_router_inventory.schema.json"
    assert router_entry["urn"] == "urn:mullusi:schema:component-router-inventory:1"
    assert router_entry["surface"] == "governance"
    assert ownership_entry["path"] == "schemas/component_route_family_ownership.schema.json"
    assert ownership_entry["urn"] == "urn:mullusi:schema:component-route-family-ownership:1"
    assert ownership_entry["surface"] == "governance"
    assert promotion_preflight_entry["path"] == (
        "schemas/component_route_family_promotion_preflight.schema.json"
    )
    assert promotion_preflight_entry["urn"] == (
        "urn:mullusi:schema:component-route-family-promotion-preflight:1"
    )
    assert promotion_preflight_entry["surface"] == "governance"
    assert promotion_witness_entry["path"] == (
        "schemas/component_route_family_promotion_witness_requirements.schema.json"
    )
    assert promotion_witness_entry["urn"] == (
        "urn:mullusi:schema:component-route-family-promotion-witness-requirements:1"
    )
    assert promotion_witness_entry["surface"] == "governance"
    assert promotion_witness_evidence_entry["path"] == (
        "schemas/component_route_family_promotion_witness_evidence.schema.json"
    )
    assert promotion_witness_evidence_entry["urn"] == (
        "urn:mullusi:schema:component-route-family-promotion-witness-evidence:1"
    )
    assert promotion_witness_evidence_entry["surface"] == "governance"
    assert promotion_approval_candidates_entry["path"] == (
        "schemas/component_route_family_promotion_approval_candidates.schema.json"
    )
    assert promotion_approval_candidates_entry["urn"] == (
        "urn:mullusi:schema:component-route-family-promotion-approval-candidates:1"
    )
    assert promotion_approval_candidates_entry["surface"] == "governance"
    assert promotion_approval_intake_entry["path"] == (
        "schemas/component_route_family_promotion_approval_intake.schema.json"
    )
    assert promotion_approval_intake_entry["urn"] == (
        "urn:mullusi:schema:component-route-family-promotion-approval-intake:1"
    )
    assert promotion_approval_intake_entry["surface"] == "governance"
    assert promotion_submitted_evidence_verifier_entry["path"] == (
        "schemas/component_route_family_promotion_submitted_evidence_verifier.schema.json"
    )
    assert promotion_submitted_evidence_verifier_entry["urn"] == (
        "urn:mullusi:schema:component-route-family-promotion-submitted-evidence-verifier:1"
    )
    assert promotion_submitted_evidence_verifier_entry["surface"] == "governance"
    assert promotion_submitted_evidence_records_entry["path"] == (
        "schemas/component_route_family_promotion_submitted_evidence_records.schema.json"
    )
    assert promotion_submitted_evidence_records_entry["urn"] == (
        "urn:mullusi:schema:component-route-family-promotion-submitted-evidence-records:1"
    )
    assert promotion_submitted_evidence_records_entry["surface"] == "governance"
    assert promotion_submitted_evidence_payload_examples_entry["path"] == (
        "schemas/component_route_family_promotion_submitted_evidence_payload_examples.schema.json"
    )
    assert promotion_submitted_evidence_payload_examples_entry["urn"] == (
        "urn:mullusi:schema:component-route-family-promotion-submitted-evidence-payload-examples:1"
    )
    assert promotion_submitted_evidence_payload_examples_entry["surface"] == "governance"
    assert promotion_operator_submitted_evidence_records_entry["path"] == (
        "schemas/component_route_family_promotion_operator_submitted_evidence_records.schema.json"
    )
    assert promotion_operator_submitted_evidence_records_entry["urn"] == (
        "urn:mullusi:schema:component-route-family-promotion-operator-submitted-evidence-records:1"
    )
    assert promotion_operator_submitted_evidence_records_entry["surface"] == "governance"
    assert promotion_gate_satisfaction_evaluator_entry["path"] == (
        "schemas/component_route_family_promotion_gate_satisfaction_evaluator.schema.json"
    )
    assert promotion_gate_satisfaction_evaluator_entry["urn"] == (
        "urn:mullusi:schema:component-route-family-promotion-gate-satisfaction-evaluator:1"
    )
    assert promotion_gate_satisfaction_evaluator_entry["surface"] == "governance"
    assert promotion_authority_decision_report_entry["path"] == (
        "schemas/component_route_family_promotion_authority_decision_report.schema.json"
    )
    assert promotion_authority_decision_report_entry["urn"] == (
        "urn:mullusi:schema:component-route-family-promotion-authority-decision-report:1"
    )
    assert promotion_authority_decision_report_entry["surface"] == "governance"
    assert promotion_authority_upgrade_witness_decision_report_entry["path"] == (
        "schemas/component_route_family_promotion_authority_upgrade_witness_decision_report.schema.json"
    )
    assert promotion_authority_upgrade_witness_decision_report_entry["urn"] == (
        "urn:mullusi:schema:component-route-family-promotion-authority-upgrade-witness-decision-report:1"
    )
    assert promotion_authority_upgrade_witness_decision_report_entry["surface"] == "governance"
    assert promotion_product_ownership_decision_report_entry["path"] == (
        "schemas/component_route_family_promotion_product_ownership_decision_report.schema.json"
    )
    assert promotion_product_ownership_decision_report_entry["urn"] == (
        "urn:mullusi:schema:component-route-family-promotion-product-ownership-decision-report:1"
    )
    assert promotion_product_ownership_decision_report_entry["surface"] == "governance"
    assert promotion_terminal_closure_denial_report_entry["path"] == (
        "schemas/component_route_family_promotion_terminal_closure_denial_report.schema.json"
    )
    assert promotion_terminal_closure_denial_report_entry["urn"] == (
        "urn:mullusi:schema:component-route-family-promotion-terminal-closure-denial-report:1"
    )
    assert promotion_terminal_closure_denial_report_entry["surface"] == "governance"
    assert promotion_missing_evidence_ledger_entry["path"] == (
        "schemas/component_route_family_promotion_missing_evidence_ledger.schema.json"
    )
    assert promotion_missing_evidence_ledger_entry["urn"] == (
        "urn:mullusi:schema:component-route-family-promotion-missing-evidence-ledger:1"
    )
    assert promotion_missing_evidence_ledger_entry["surface"] == "governance"
    assert promotion_router_inventory_delta_candidate_entry["path"] == (
        "schemas/component_route_family_promotion_router_inventory_delta_candidate.schema.json"
    )
    assert promotion_router_inventory_delta_candidate_entry["urn"] == (
        "urn:mullusi:schema:component-route-family-promotion-router-inventory-delta-candidate:1"
    )
    assert promotion_router_inventory_delta_candidate_entry["surface"] == "governance"
    assert promotion_router_inventory_delta_witness_requirements_entry["path"] == (
        "schemas/component_route_family_promotion_router_inventory_delta_witness_requirements.schema.json"
    )
    assert promotion_router_inventory_delta_witness_requirements_entry["urn"] == (
        "urn:mullusi:schema:component-route-family-promotion-router-inventory-delta-witness-requirements:1"
    )
    assert promotion_router_inventory_delta_witness_requirements_entry["surface"] == "governance"
    assert promotion_router_inventory_delta_witness_minting_preflight_entry["path"] == (
        "schemas/component_route_family_promotion_router_inventory_delta_witness_minting_preflight.schema.json"
    )
    assert promotion_router_inventory_delta_witness_minting_preflight_entry["urn"] == (
        "urn:mullusi:schema:component-route-family-promotion-router-inventory-delta-witness-minting-preflight:1"
    )
    assert promotion_router_inventory_delta_witness_minting_preflight_entry["surface"] == "governance"
    assert promotion_router_inventory_delta_witness_minting_denial_report_entry["path"] == (
        "schemas/component_route_family_promotion_router_inventory_delta_witness_minting_denial_report.schema.json"
    )
    assert promotion_router_inventory_delta_witness_minting_denial_report_entry["urn"] == (
        "urn:mullusi:schema:component-route-family-promotion-router-inventory-delta-witness-minting-denial-report:1"
    )
    assert promotion_router_inventory_delta_witness_minting_denial_report_entry["surface"] == "governance"
    assert promotion_router_inventory_delta_witness_remediation_plan_entry["path"] == (
        "schemas/component_route_family_promotion_router_inventory_delta_witness_remediation_plan.schema.json"
    )
    assert promotion_router_inventory_delta_witness_remediation_plan_entry["urn"] == (
        "urn:mullusi:schema:component-route-family-promotion-router-inventory-delta-witness-remediation-plan:1"
    )
    assert promotion_router_inventory_delta_witness_remediation_plan_entry["surface"] == "governance"
    assert promotion_router_inventory_delta_witness_remediation_evidence_request_entry["path"] == (
        "schemas/component_route_family_promotion_router_inventory_delta_witness_remediation_evidence_request.schema.json"
    )
    assert promotion_router_inventory_delta_witness_remediation_evidence_request_entry["urn"] == (
        "urn:mullusi:schema:component-route-family-promotion-router-inventory-delta-witness-remediation-evidence-request:1"
    )
    assert promotion_router_inventory_delta_witness_remediation_evidence_request_entry["surface"] == "governance"
    assert promotion_router_inventory_delta_witness_remediation_evidence_request_status_ledger_entry["path"] == (
        "schemas/component_route_family_promotion_router_inventory_delta_witness_remediation_evidence_request_status_ledger.schema.json"
    )
    assert promotion_router_inventory_delta_witness_remediation_evidence_request_status_ledger_entry["urn"] == (
        "urn:mullusi:schema:component-route-family-promotion-router-inventory-delta-witness-remediation-evidence-request-status-ledger:1"
    )
    assert (
        promotion_router_inventory_delta_witness_remediation_evidence_request_status_ledger_entry["surface"]
        == "governance"
    )
    assert promotion_route_binding_decision_report_entry["path"] == (
        "schemas/component_route_family_promotion_route_binding_decision_report.schema.json"
    )
    assert promotion_route_binding_decision_report_entry["urn"] == (
        "urn:mullusi:schema:component-route-family-promotion-route-binding-decision-report:1"
    )
    assert promotion_route_binding_decision_report_entry["surface"] == "governance"
    assert promotion_lifecycle_transition_decision_report_entry["path"] == (
        "schemas/component_route_family_promotion_lifecycle_transition_decision_report.schema.json"
    )
    assert promotion_lifecycle_transition_decision_report_entry["urn"] == (
        "urn:mullusi:schema:component-route-family-promotion-lifecycle-transition-decision-report:1"
    )
    assert promotion_lifecycle_transition_decision_report_entry["surface"] == "governance"
    assert promotion_authority_upgrade_decision_report_entry["path"] == (
        "schemas/component_route_family_promotion_authority_upgrade_witness_decision_report.schema.json"
    )
    assert promotion_authority_upgrade_decision_report_entry["urn"] == (
        "urn:mullusi:schema:component-route-family-promotion-authority-upgrade-witness-decision-report:1"
    )
    assert promotion_authority_upgrade_decision_report_entry["surface"] == "governance"
    assert proof_entry["path"] == "schemas/component_proof_binding.schema.json"
    assert proof_entry["urn"] == "urn:mullusi:schema:component-proof-binding:1"
    assert proof_entry["surface"] == "governance"
    assert read_model_entry["path"] == "schemas/component_read_model.schema.json"
    assert read_model_entry["urn"] == "urn:mullusi:schema:component-read-model:1"
    assert read_model_entry["surface"] == "governance"
    assert graph_entry["path"] == "schemas/component_graph.schema.json"
    assert graph_entry["urn"] == "urn:mullusi:schema:component-graph:1"
    assert graph_entry["surface"] == "governance"
    assert autopsy_entry["path"] == "schemas/component_autopsy.schema.json"
    assert autopsy_entry["urn"] == "urn:mullusi:schema:component-autopsy:1"
    assert autopsy_entry["surface"] == "governance"
    assert simulation_entry["path"] == "schemas/component_request_simulation.schema.json"
    assert simulation_entry["urn"] == "urn:mullusi:schema:component-request-simulation:1"
    assert simulation_entry["surface"] == "governance"
    assert bundle_compilation_entry["path"] == "schemas/component_bundle_compilation.schema.json"
    assert bundle_compilation_entry["urn"] == "urn:mullusi:schema:component-bundle-compilation:1"
    assert bundle_compilation_entry["surface"] == "governance"
    assert lifecycle_entry["path"] == "schemas/component_lifecycle_transition_receipts.schema.json"
    assert lifecycle_entry["urn"] == "urn:mullusi:schema:component-lifecycle-transition-receipts:1"
    assert lifecycle_entry["surface"] == "governance"
    assert authority_witness_entry["path"] == "schemas/component_authority_envelope_witnesses.schema.json"
    assert authority_witness_entry["urn"] == "urn:mullusi:schema:component-authority-envelope-witnesses:1"
    assert authority_witness_entry["surface"] == "governance"
    assert dead_component_entry["path"] == (
        "schemas/component_dead_component_detection.schema.json"
    )
    assert dead_component_entry["urn"] == (
        "urn:mullusi:schema:component-dead-component-detection:1"
    )
    assert dead_component_entry["surface"] == "governance"


def test_protocol_manifest_indexes_operator_receipt_and_task_read_models() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    receipt_entry = entries["operator-receipt-viewer-read-model"]
    approval_history_entry = entries["operator-approval-history-read-model"]
    plan_review_entry = entries["operator-plan-review-read-model"]
    budget_report_entry = entries["operator-budget-report-read-model"]
    plan_receipt_bundle_entry = entries["operator-plan-receipt-bundle-read-model"]
    plan_receipt_export_entry = entries["operator-plan-receipt-export-read-model"]
    task_entry = entries["current-task-read-model"]

    assert validate_protocol_manifest(manifest) == []
    assert receipt_entry["path"] == (
        "schemas/operator_receipt_viewer_read_model.schema.json"
    )
    assert receipt_entry["urn"] == (
        "urn:mullusi:schema:operator-receipt-viewer-read-model:1"
    )
    assert receipt_entry["surface"] == "operator"
    assert approval_history_entry["path"] == (
        "schemas/operator_approval_history_read_model.schema.json"
    )
    assert approval_history_entry["urn"] == (
        "urn:mullusi:schema:operator-approval-history-read-model:1"
    )
    assert approval_history_entry["surface"] == "operator"
    assert plan_review_entry["path"] == (
        "schemas/operator_plan_review_read_model.schema.json"
    )
    assert plan_review_entry["urn"] == (
        "urn:mullusi:schema:operator-plan-review-read-model:1"
    )
    assert plan_review_entry["surface"] == "operator"
    assert budget_report_entry["path"] == (
        "schemas/operator_budget_report_read_model.schema.json"
    )
    assert budget_report_entry["urn"] == (
        "urn:mullusi:schema:operator-budget-report-read-model:1"
    )
    assert budget_report_entry["surface"] == "operator"
    assert plan_receipt_bundle_entry["path"] == (
        "schemas/operator_plan_receipt_bundle_read_model.schema.json"
    )
    assert plan_receipt_bundle_entry["urn"] == (
        "urn:mullusi:schema:operator-plan-receipt-bundle-read-model:1"
    )
    assert plan_receipt_bundle_entry["surface"] == "operator"
    assert plan_receipt_export_entry["path"] == (
        "schemas/operator_plan_receipt_export_read_model.schema.json"
    )
    assert plan_receipt_export_entry["urn"] == (
        "urn:mullusi:schema:operator-plan-receipt-export-read-model:1"
    )
    assert plan_receipt_export_entry["surface"] == "operator"
    assert task_entry["path"] == "schemas/current_task_read_model.schema.json"
    assert task_entry["urn"] == "urn:mullusi:schema:current-task-read-model:1"
    assert task_entry["surface"] == "operator"


def test_protocol_manifest_indexes_claim_verification_report() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    claim_entry = entries["claim-verification-report"]

    assert validate_protocol_manifest(manifest) == []
    assert claim_entry["path"] == "schemas/claim_verification_report.schema.json"
    assert claim_entry["urn"] == "urn:mullusi:schema:claim-verification-report:1"
    assert claim_entry["surface"] == "claim"


def test_protocol_manifest_indexes_policy_dsl_schemas() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    rule_entry = entries["policy-rule"]
    bundle_entry = entries["policy-bundle"]
    trace_entry = entries["policy-evaluation-trace"]

    assert validate_protocol_manifest(manifest) == []
    assert rule_entry["path"] == "schemas/policy_rule.schema.json"
    assert rule_entry["urn"] == "urn:mullusi:schema:policy-rule:1"
    assert rule_entry["surface"] == "policy"
    assert bundle_entry["path"] == "schemas/policy_bundle.schema.json"
    assert bundle_entry["urn"] == "urn:mullusi:schema:policy-bundle:1"
    assert bundle_entry["surface"] == "policy"
    assert trace_entry["path"] == "schemas/policy_evaluation_trace.schema.json"
    assert trace_entry["urn"] == "urn:mullusi:schema:policy-evaluation-trace:1"
    assert trace_entry["surface"] == "policy"


def test_protocol_manifest_indexes_supervisor_contract_schemas() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    tick_entry = entries["supervisor-tick"]
    checkpoint_entry = entries["supervisor-checkpoint"]
    livelock_entry = entries["livelock-record"]

    assert validate_protocol_manifest(manifest) == []
    assert tick_entry["path"] == "schemas/supervisor_tick.schema.json"
    assert tick_entry["urn"] == "urn:mullusi:schema:supervisor-tick:1"
    assert tick_entry["surface"] == "supervisor"
    assert checkpoint_entry["path"] == "schemas/supervisor_checkpoint.schema.json"
    assert checkpoint_entry["urn"] == "urn:mullusi:schema:supervisor-checkpoint:1"
    assert checkpoint_entry["surface"] == "supervisor"
    assert livelock_entry["path"] == "schemas/livelock_record.schema.json"
    assert livelock_entry["urn"] == "urn:mullusi:schema:livelock-record:1"
    assert livelock_entry["surface"] == "supervisor"


def test_protocol_manifest_indexes_connector_self_healing_receipt() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    healing_entry = entries["connector-self-healing-receipt"]

    assert validate_protocol_manifest(manifest) == []
    assert healing_entry["path"] == "schemas/connector_self_healing_receipt.schema.json"
    assert healing_entry["urn"] == "urn:mullusi:schema:connector-self-healing-receipt:1"
    assert healing_entry["surface"] == "connector"


def test_protocol_manifest_indexes_team_ops_shared_inbox_operator_handoff_bundle() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    handoff_entry = entries["durable-gmail-oauth-operator-handoff"]

    assert validate_protocol_manifest(manifest) == []
    assert handoff_entry["path"] == "schemas/durable_gmail_oauth_operator_handoff.schema.json"
    assert handoff_entry["urn"] == "urn:mullusi:schema:durable-gmail-oauth-operator-handoff:1"
    assert handoff_entry["surface"] == "connector"


def test_protocol_manifest_indexes_collaboration_case() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    collaboration_entry = entries["collaboration-case"]
    commercial_entry = entries["commercial-metering-snapshot"]
    economic_entry = entries["economic-intelligence-snapshot"]
    federated_entry = entries["federated-control-snapshot"]
    operational_entry = entries["operational-case"]
    operator_entry = entries["operator-control-tower-snapshot"]

    assert validate_protocol_manifest(manifest) == []
    assert collaboration_entry["path"] == "schemas/collaboration_case.schema.json"
    assert collaboration_entry["urn"] == "urn:mullusi:schema:collaboration-case:1"
    assert collaboration_entry["surface"] == "collaboration"
    assert commercial_entry["path"] == "schemas/commercial_metering_snapshot.schema.json"
    assert commercial_entry["urn"] == "urn:mullusi:schema:commercial-metering-snapshot:1"
    assert commercial_entry["surface"] == "commercial"
    assert economic_entry["path"] == "schemas/economic_intelligence_snapshot.schema.json"
    assert economic_entry["urn"] == "urn:mullusi:schema:economic-intelligence-snapshot:1"
    assert economic_entry["surface"] == "commercial"
    assert federated_entry["path"] == "schemas/federated_control_snapshot.schema.json"
    assert federated_entry["urn"] == "urn:mullusi:schema:federated-control-snapshot:1"
    assert federated_entry["surface"] == "federation"
    assert operational_entry["path"] == "schemas/operational_case.schema.json"
    assert operational_entry["urn"] == "urn:mullusi:schema:operational-case:1"
    assert operational_entry["surface"] == "case_management"
    assert operator_entry["path"] == "schemas/operator_control_tower_snapshot.schema.json"
    assert operator_entry["urn"] == "urn:mullusi:schema:operator-control-tower-snapshot:1"
    assert operator_entry["surface"] == "operator"


def test_protocol_manifest_indexes_connector_certification_registry() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    connector_entry = entries["connector-certification-registry"]
    commercial_entry = entries["commercial-metering-snapshot"]
    ci_health_entry = entries["ci-health-snapshot"]
    data_governance_entry = entries["data-governance-snapshot"]

    assert validate_protocol_manifest(manifest) == []
    assert connector_entry["path"] == "schemas/connector_certification_registry.schema.json"
    assert connector_entry["urn"] == "urn:mullusi:schema:connector-certification-registry:1"
    assert connector_entry["surface"] == "connector"
    assert commercial_entry["path"] == "schemas/commercial_metering_snapshot.schema.json"
    assert commercial_entry["urn"] == "urn:mullusi:schema:commercial-metering-snapshot:1"
    assert commercial_entry["surface"] == "commercial"
    assert ci_health_entry["path"] == "schemas/ci_health_snapshot.schema.json"
    assert ci_health_entry["urn"] == "urn:mullusi:schema:ci-health-snapshot:1"
    assert ci_health_entry["surface"] == "ci"
    assert data_governance_entry["path"] == "schemas/data_governance_snapshot.schema.json"
    assert data_governance_entry["urn"] == "urn:mullusi:schema:data-governance-snapshot:1"
    assert data_governance_entry["surface"] == "data_governance"


def test_protocol_manifest_indexes_durable_gmail_oauth_operator_handoff() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    handoff_entry = entries["durable-gmail-oauth-operator-handoff"]
    team_ops_entry = entries["team-ops-shared-inbox-operator-handoff"]
    team_ops_binding_entry = entries["team-ops-shared-inbox-live-probe-approval-binding"]
    team_ops_authority_entry = entries["team-ops-shared-inbox-live-probe-authority"]
    team_ops_input_entry = entries["team-ops-shared-inbox-live-probe-operator-input-request"]
    team_ops_receipt_entry = entries["team-ops-shared-inbox-live-probe-receipt"]
    team_ops_provider_observation_entry = entries["team-ops-shared-inbox-provider-observation-receipt"]
    team_ops_routing_entry = entries["team-ops-shared-inbox-observation-routing-receipt"]
    team_ops_approval_queue_entry = entries["team-ops-shared-inbox-approval-queue-receipt"]
    team_ops_approval_decision_entry = entries["team-ops-shared-inbox-approval-decision-receipt"]
    team_ops_send_preparation_entry = entries["team-ops-shared-inbox-send-preparation-receipt"]
    team_ops_send_execution_entry = entries["team-ops-shared-inbox-send-execution-receipt"]
    team_ops_sent_message_observation_entry = entries["team-ops-shared-inbox-sent-message-observation-receipt"]
    team_ops_terminal_closure_review_entry = entries["team-ops-shared-inbox-terminal-closure-review-packet"]
    team_ops_terminal_anchor_preflight_entry = entries[
        "team-ops-shared-inbox-terminal-closure-anchor-preflight"
    ]
    team_ops_terminal_anchor_receipt_entry = entries[
        "team-ops-shared-inbox-terminal-closure-anchor-receipt"
    ]

    assert validate_protocol_manifest(manifest) == []
    assert handoff_entry["path"] == "schemas/durable_gmail_oauth_operator_handoff.schema.json"
    assert handoff_entry["urn"] == "urn:mullusi:schema:durable-gmail-oauth-operator-handoff:1"
    assert handoff_entry["surface"] == "connector"
    assert team_ops_entry["path"] == "schemas/team_ops_shared_inbox_operator_handoff.schema.json"
    assert team_ops_entry["urn"] == "urn:mullusi:schema:team-ops-shared-inbox-operator-handoff:1"
    assert team_ops_entry["surface"] == "team_ops"
    assert team_ops_binding_entry["path"] == (
        "schemas/team_ops_shared_inbox_live_probe_approval_binding.schema.json"
    )
    assert team_ops_binding_entry["urn"] == (
        "urn:mullusi:schema:team-ops-shared-inbox-live-probe-approval-binding:1"
    )
    assert team_ops_binding_entry["surface"] == "team_ops"
    assert team_ops_authority_entry["path"] == "schemas/team_ops_shared_inbox_live_probe_authority.schema.json"
    assert team_ops_authority_entry["urn"] == "urn:mullusi:schema:team-ops-shared-inbox-live-probe-authority:1"
    assert team_ops_authority_entry["surface"] == "team_ops"
    assert team_ops_input_entry["path"] == (
        "schemas/team_ops_shared_inbox_live_probe_operator_input_request.schema.json"
    )
    assert team_ops_input_entry["urn"] == (
        "urn:mullusi:schema:team-ops-shared-inbox-live-probe-operator-input-request:1"
    )
    assert team_ops_input_entry["surface"] == "team_ops"
    assert team_ops_receipt_entry["path"] == "schemas/team_ops_shared_inbox_live_probe_receipt.schema.json"
    assert team_ops_receipt_entry["urn"] == "urn:mullusi:schema:team-ops-shared-inbox-live-probe-receipt:1"
    assert team_ops_receipt_entry["surface"] == "team_ops"
    assert team_ops_provider_observation_entry["path"] == (
        "schemas/team_ops_shared_inbox_provider_observation_receipt.schema.json"
    )
    assert team_ops_provider_observation_entry["urn"] == (
        "urn:mullusi:schema:team-ops-shared-inbox-provider-observation-receipt:1"
    )
    assert team_ops_provider_observation_entry["surface"] == "team_ops"
    assert team_ops_routing_entry["path"] == (
        "schemas/team_ops_shared_inbox_observation_routing_receipt.schema.json"
    )
    assert team_ops_routing_entry["urn"] == (
        "urn:mullusi:schema:team-ops-shared-inbox-observation-routing-receipt:1"
    )
    assert team_ops_routing_entry["surface"] == "team_ops"
    assert team_ops_approval_queue_entry["path"] == (
        "schemas/team_ops_shared_inbox_approval_queue_receipt.schema.json"
    )
    assert team_ops_approval_queue_entry["urn"] == (
        "urn:mullusi:schema:team-ops-shared-inbox-approval-queue-receipt:1"
    )
    assert team_ops_approval_queue_entry["surface"] == "team_ops"
    assert team_ops_approval_decision_entry["path"] == (
        "schemas/team_ops_shared_inbox_approval_decision_receipt.schema.json"
    )
    assert team_ops_approval_decision_entry["urn"] == (
        "urn:mullusi:schema:team-ops-shared-inbox-approval-decision-receipt:1"
    )
    assert team_ops_approval_decision_entry["surface"] == "team_ops"
    assert team_ops_send_preparation_entry["path"] == (
        "schemas/team_ops_shared_inbox_send_preparation_receipt.schema.json"
    )
    assert team_ops_send_preparation_entry["urn"] == (
        "urn:mullusi:schema:team-ops-shared-inbox-send-preparation-receipt:1"
    )
    assert team_ops_send_preparation_entry["surface"] == "team_ops"
    assert team_ops_send_execution_entry["path"] == (
        "schemas/team_ops_shared_inbox_send_execution_receipt.schema.json"
    )
    assert team_ops_send_execution_entry["urn"] == (
        "urn:mullusi:schema:team-ops-shared-inbox-send-execution-receipt:1"
    )
    assert team_ops_send_execution_entry["surface"] == "team_ops"
    assert team_ops_sent_message_observation_entry["path"] == (
        "schemas/team_ops_shared_inbox_sent_message_observation_receipt.schema.json"
    )
    assert team_ops_sent_message_observation_entry["urn"] == (
        "urn:mullusi:schema:team-ops-shared-inbox-sent-message-observation-receipt:1"
    )
    assert team_ops_sent_message_observation_entry["surface"] == "team_ops"
    assert team_ops_terminal_closure_review_entry["path"] == (
        "schemas/team_ops_shared_inbox_terminal_closure_review_packet.schema.json"
    )
    assert team_ops_terminal_closure_review_entry["urn"] == (
        "urn:mullusi:schema:team-ops-shared-inbox-terminal-closure-review-packet:1"
    )
    assert team_ops_terminal_closure_review_entry["surface"] == "team_ops"
    assert team_ops_terminal_anchor_preflight_entry["path"] == (
        "schemas/team_ops_shared_inbox_terminal_closure_anchor_preflight.schema.json"
    )
    assert team_ops_terminal_anchor_preflight_entry["urn"] == (
        "urn:mullusi:schema:team-ops-shared-inbox-terminal-closure-anchor-preflight:1"
    )
    assert team_ops_terminal_anchor_preflight_entry["surface"] == "team_ops"
    assert team_ops_terminal_anchor_receipt_entry["path"] == (
        "schemas/team_ops_shared_inbox_terminal_closure_anchor_receipt.schema.json"
    )
    assert team_ops_terminal_anchor_receipt_entry["urn"] == (
        "urn:mullusi:schema:team-ops-shared-inbox-terminal-closure-anchor-receipt:1"
    )
    assert team_ops_terminal_anchor_receipt_entry["surface"] == "team_ops"


def test_protocol_manifest_indexes_deployment_orchestration_validation() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    validation_entry = entries["deployment-orchestration-receipt-validation"]

    assert validate_protocol_manifest(manifest) == []
    assert validation_entry["path"] == "schemas/deployment_orchestration_receipt_validation.schema.json"
    assert validation_entry["urn"] == "urn:mullusi:schema:deployment-orchestration-receipt-validation:1"
    assert validation_entry["surface"] == "deployment"


def test_protocol_manifest_indexes_deployment_publication_closure_validation() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    validation_entry = entries["deployment-publication-closure-validation"]

    assert validate_protocol_manifest(manifest) == []
    assert validation_entry["path"] == "schemas/deployment_publication_closure_validation.schema.json"
    assert validation_entry["urn"] == "urn:mullusi:schema:deployment-publication-closure-validation:1"
    assert validation_entry["surface"] == "deployment"


def test_protocol_manifest_indexes_deployment_publication_closure_plan() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    plan_entry = entries["deployment-publication-closure-plan"]

    assert validate_protocol_manifest(manifest) == []
    assert plan_entry["path"] == "schemas/deployment_publication_closure_plan.schema.json"
    assert plan_entry["urn"] == "urn:mullusi:schema:deployment-publication-closure-plan:1"
    assert plan_entry["surface"] == "deployment"


def test_protocol_manifest_indexes_deployment_publication_evidence_packet() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    packet_entry = entries["deployment-publication-evidence-packet"]

    assert validate_protocol_manifest(manifest) == []
    assert packet_entry["path"] == "schemas/deployment_publication_evidence_packet.schema.json"
    assert packet_entry["urn"] == "urn:mullusi:schema:deployment-publication-evidence-packet:1"
    assert packet_entry["surface"] == "deployment"


def test_protocol_manifest_indexes_deployment_publication_operator_input_request() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    request_entry = entries["deployment-publication-operator-input-request"]

    assert validate_protocol_manifest(manifest) == []
    assert request_entry["path"] == "schemas/deployment_publication_operator_input_request.schema.json"
    assert request_entry["urn"] == "urn:mullusi:schema:deployment-publication-operator-input-request:1"
    assert request_entry["surface"] == "deployment"


def test_protocol_manifest_indexes_deployment_upstream_blocker_receipt() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    receipt_entry = entries["deployment-upstream-blocker-receipt"]

    assert validate_protocol_manifest(manifest) == []
    assert receipt_entry["path"] == "schemas/deployment_upstream_blocker_receipt.schema.json"
    assert receipt_entry["urn"] == "urn:mullusi:schema:deployment-upstream-blocker-receipt:1"
    assert receipt_entry["surface"] == "deployment"


def test_protocol_manifest_indexes_public_production_health_declaration() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    declaration_entry = entries["public-production-health-declaration"]

    assert validate_protocol_manifest(manifest) == []
    assert declaration_entry["path"] == "schemas/public_production_health_declaration.schema.json"
    assert declaration_entry["urn"] == "urn:mullusi:schema:public-production-health-declaration:1"
    assert declaration_entry["surface"] == "deployment"


def test_protocol_manifest_indexes_govern_cloud_public_route_monitor_receipt() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    monitor_entry = entries["govern-cloud-public-route-monitor-receipt"]

    assert validate_protocol_manifest(manifest) == []
    assert monitor_entry["path"] == "schemas/govern_cloud_public_route_monitor_receipt.schema.json"
    assert monitor_entry["urn"] == "urn:mullusi:schema:govern-cloud-public-route-monitor-receipt:1"
    assert monitor_entry["surface"] == "observability"


def test_protocol_manifest_indexes_personal_assistant_public_console_probe_receipt() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    probe_entry = entries["personal-assistant-public-console-probe-receipt"]

    assert validate_protocol_manifest(manifest) == []
    assert probe_entry["path"] == "schemas/personal_assistant_public_console_probe_receipt.schema.json"
    assert probe_entry["urn"] == "urn:mullusi:schema:personal-assistant-public-console-probe-receipt:1"
    assert probe_entry["surface"] == "observability"


def test_protocol_manifest_indexes_governed_swarm_production_readiness() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    readiness_entry = entries["governed-swarm-production-readiness"]

    assert validate_protocol_manifest(manifest) == []
    assert readiness_entry["path"] == "schemas/governed_swarm_production_readiness.schema.json"
    assert readiness_entry["urn"] == "urn:mullusi:schema:governed-swarm-production-readiness:1"
    assert readiness_entry["surface"] == "deployment"


def test_protocol_manifest_indexes_runtime_conformance_collection() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    collection_entry = entries["runtime-conformance-collection"]

    assert validate_protocol_manifest(manifest) == []
    assert collection_entry["path"] == "schemas/runtime_conformance_collection.schema.json"
    assert collection_entry["urn"] == "urn:mullusi:schema:runtime-conformance-collection:1"
    assert collection_entry["surface"] == "conformance"


def test_protocol_manifest_indexes_effect_assurance_record() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    effect_entry = entries["effect-assurance"]
    eval_entry = entries["eval-run"]

    assert validate_protocol_manifest(manifest) == []
    assert effect_entry["path"] == "schemas/effect_assurance.schema.json"
    assert effect_entry["urn"] == "urn:mullusi:schema:effect-assurance:1"
    assert effect_entry["surface"] == "effect_assurance"
    assert eval_entry["path"] == "schemas/eval_run.schema.json"
    assert eval_entry["urn"] == "urn:mullusi:schema:eval-run:1"
    assert eval_entry["surface"] == "testing"


def test_protocol_manifest_indexes_promotion_closure_plan() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    plan_entry = entries["general-agent-promotion-closure-plan"]

    assert validate_protocol_manifest(manifest) == []
    assert plan_entry["path"] == "schemas/general_agent_promotion_closure_plan.schema.json"
    assert plan_entry["urn"] == "urn:mullusi:schema:general-agent-promotion-closure-plan:1"
    assert plan_entry["surface"] == "promotion"


def test_protocol_manifest_indexes_policy_proof_report() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    policy_proof_entry = entries["policy-proof-report"]
    policy_studio_entry = entries["policy-studio-session"]

    assert validate_protocol_manifest(manifest) == []
    assert policy_proof_entry["path"] == "schemas/policy_proof_report.schema.json"
    assert policy_proof_entry["urn"] == "urn:mullusi:schema:policy-proof-report:1"
    assert policy_proof_entry["surface"] == "policy"
    assert policy_studio_entry["path"] == "schemas/policy_studio_session.schema.json"
    assert policy_studio_entry["urn"] == "urn:mullusi:schema:policy-studio-session:1"
    assert policy_studio_entry["surface"] == "policy"


def test_protocol_manifest_indexes_capability_adapter_closure_plan() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    plan_entry = entries["capability-adapter-closure-plan"]

    assert validate_protocol_manifest(manifest) == []
    assert plan_entry["path"] == "schemas/capability_adapter_closure_plan.schema.json"
    assert plan_entry["urn"] == "urn:mullusi:schema:capability-adapter-closure-plan:1"
    assert plan_entry["surface"] == "promotion"


def test_protocol_manifest_indexes_capability_upgrade_plan() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    upgrade_entry = entries["capability-upgrade-plan"]

    assert validate_protocol_manifest(manifest) == []
    assert upgrade_entry["path"] == "schemas/capability_upgrade_plan.schema.json"
    assert upgrade_entry["urn"] == "urn:mullusi:schema:capability-upgrade-plan:1"
    assert upgrade_entry["surface"] == "capability"


def test_protocol_manifest_indexes_capability_improvement_portfolio() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    portfolio_entry = entries["capability-improvement-portfolio"]

    assert validate_protocol_manifest(manifest) == []
    assert portfolio_entry["path"] == "schemas/capability_improvement_portfolio.schema.json"
    assert portfolio_entry["urn"] == "urn:mullusi:schema:capability-improvement-portfolio:1"
    assert portfolio_entry["surface"] == "capability"


def test_protocol_manifest_indexes_capability_improvement_proof_receipt() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    proof_entry = entries["capability-improvement-proof-receipt"]

    assert validate_protocol_manifest(manifest) == []
    assert proof_entry["path"] == "schemas/capability_improvement_proof_receipt.schema.json"
    assert proof_entry["urn"] == "urn:mullusi:schema:capability-improvement-proof-receipt:1"
    assert proof_entry["surface"] == "capability"


def test_protocol_manifest_indexes_autonomous_test_generation_plan() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    test_generation_entry = entries["autonomous-test-generation-plan"]

    assert validate_protocol_manifest(manifest) == []
    assert test_generation_entry["path"] == "schemas/autonomous_test_generation_plan.schema.json"
    assert test_generation_entry["urn"] == "urn:mullusi:schema:autonomous-test-generation-plan:1"
    assert test_generation_entry["surface"] == "testing"


def test_protocol_manifest_indexes_capability_candidate_package() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    candidate_entry = entries["capability-candidate"]

    assert validate_protocol_manifest(manifest) == []
    assert candidate_entry["path"] == "schemas/capability_candidate.schema.json"
    assert candidate_entry["urn"] == "urn:mullusi:schema:capability-candidate:1"
    assert candidate_entry["surface"] == "capability"


def test_protocol_manifest_indexes_capability_maturity_assessment() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    maturity_entry = entries["capability-maturity"]

    assert validate_protocol_manifest(manifest) == []
    assert maturity_entry["path"] == "schemas/capability_maturity.schema.json"
    assert maturity_entry["urn"] == "urn:mullusi:schema:capability-maturity:1"
    assert maturity_entry["surface"] == "capability"


def test_protocol_manifest_indexes_trust_ledger_anchor_verification_report() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    bundle_report_entry = entries["trust-ledger-bundle-verification-report"]
    report_entry = entries["trust-ledger-anchor-verification-report"]

    assert validate_protocol_manifest(manifest) == []
    assert bundle_report_entry["path"] == "schemas/trust_ledger_bundle_verification_report.schema.json"
    assert bundle_report_entry["urn"] == "urn:mullusi:schema:trust-ledger-bundle-verification-report:1"
    assert bundle_report_entry["surface"] == "evidence"
    assert report_entry["path"] == "schemas/trust_ledger_anchor_verification_report.schema.json"
    assert report_entry["urn"] == "urn:mullusi:schema:trust-ledger-anchor-verification-report:1"
    assert report_entry["surface"] == "evidence"


def test_protocol_manifest_indexes_domain_operating_pack() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    domain_entry = entries["domain-operating-pack"]

    assert validate_protocol_manifest(manifest) == []
    assert domain_entry["path"] == "schemas/domain_operating_pack.schema.json"
    assert domain_entry["urn"] == "urn:mullusi:schema:domain-operating-pack:1"
    assert domain_entry["surface"] == "domain"


def test_protocol_manifest_indexes_sdlc_contract_schemas() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    expected_paths_by_id = {
        "sdlc-change-request": "schemas/sdlc_change_request.schema.json",
        "sdlc-requirement": "schemas/sdlc_requirement.schema.json",
        "sdlc-design-decision": "schemas/sdlc_design_decision.schema.json",
        "sdlc-work-plan": "schemas/sdlc_work_plan.schema.json",
        "sdlc-implementation-receipt": "schemas/sdlc_implementation_receipt.schema.json",
        "sdlc-transition-receipt": "schemas/sdlc_transition_receipt.schema.json",
        "sdlc-verification-receipt": "schemas/sdlc_verification_receipt.schema.json",
        "sdlc-security-review": "schemas/sdlc_security_review.schema.json",
        "sdlc-release-candidate": "schemas/sdlc_release_candidate.schema.json",
        "sdlc-deployment-candidate": "schemas/sdlc_deployment_candidate.schema.json",
        "sdlc-recovery-handoff-receipt": "schemas/sdlc_recovery_handoff_receipt.schema.json",
        "sdlc-closure-receipt": "schemas/sdlc_closure_receipt.schema.json",
    }

    assert validate_protocol_manifest(manifest) == []
    for schema_id, schema_path in expected_paths_by_id.items():
        assert entries[schema_id]["path"] == schema_path
        assert entries[schema_id]["urn"].startswith("urn:mullusi:schema:sdlc-")
        assert entries[schema_id]["surface"] == "software_delivery"


def test_protocol_manifest_indexes_workspace_governance_schemas() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    inventory_entry = entries["workspace-governance-inventory-report"]
    integrity_entry = entries["workspace-governance-integrity-report"]
    witness_entry = entries["workspace-governance-witness"]

    assert validate_protocol_manifest(manifest) == []
    assert inventory_entry["path"] == "schemas/workspace_governance_inventory_report.schema.json"
    assert inventory_entry["urn"] == "urn:mullusi:schema:workspace-governance-inventory-report:1"
    assert inventory_entry["surface"] == "governance"
    assert integrity_entry["path"] == "schemas/workspace_governance_integrity_report.schema.json"
    assert integrity_entry["urn"] == "urn:mullusi:schema:workspace-governance-integrity-report:1"
    assert integrity_entry["surface"] == "governance"
    assert witness_entry["path"] == "schemas/workspace_governance_witness.schema.json"
    assert witness_entry["urn"] == "urn:mullusi:schema:workspace-governance-witness:1"
    assert witness_entry["surface"] == "governance"


def test_protocol_manifest_indexes_trust_ledger_bundle() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    trust_entry = entries["trust-ledger-bundle"]

    assert validate_protocol_manifest(manifest) == []
    assert trust_entry["path"] == "schemas/trust_ledger_bundle.schema.json"
    assert trust_entry["urn"] == "urn:mullusi:schema:trust-ledger-bundle:1"
    assert trust_entry["surface"] == "evidence"


def test_protocol_manifest_indexes_trust_ledger_anchor_receipt() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    trust_entry = entries["trust-ledger-anchor-receipt"]
    compliance_entry = entries["risk-compliance-mapping-snapshot"]

    assert validate_protocol_manifest(manifest) == []
    assert trust_entry["path"] == "schemas/trust_ledger_anchor_receipt.schema.json"
    assert trust_entry["urn"] == "urn:mullusi:schema:trust-ledger-anchor-receipt:1"
    assert trust_entry["surface"] == "evidence"
    assert compliance_entry["path"] == "schemas/risk_compliance_mapping_snapshot.schema.json"
    assert compliance_entry["urn"] == "urn:mullusi:schema:risk-compliance-mapping-snapshot:1"
    assert compliance_entry["surface"] == "compliance"


def test_protocol_manifest_indexes_trust_ledger_evidence_artifacts() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    trust_entry = entries["trust-ledger-evidence-artifacts"]

    assert validate_protocol_manifest(manifest) == []
    assert trust_entry["path"] == "schemas/trust_ledger_evidence_artifacts.schema.json"
    assert trust_entry["urn"] == "urn:mullusi:schema:trust-ledger-evidence-artifacts:1"
    assert trust_entry["surface"] == "evidence"


def test_protocol_manifest_indexes_trust_ledger_export_package() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    trust_entry = entries["trust-ledger-export-package"]

    assert validate_protocol_manifest(manifest) == []
    assert trust_entry["path"] == "schemas/trust_ledger_export_package.schema.json"
    assert trust_entry["urn"] == "urn:mullusi:schema:trust-ledger-export-package:1"
    assert trust_entry["surface"] == "evidence"


def test_protocol_manifest_indexes_trust_ledger_anchor_submission_receipt() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    trust_entry = entries["trust-ledger-anchor-submission-receipt"]
    preflight_entry = entries["trust-ledger-remote-submission-preflight"]

    assert validate_protocol_manifest(manifest) == []
    assert trust_entry["path"] == "schemas/trust_ledger_anchor_submission_receipt.schema.json"
    assert trust_entry["urn"] == "urn:mullusi:schema:trust-ledger-anchor-submission-receipt:1"
    assert trust_entry["surface"] == "evidence"
    assert preflight_entry["path"] == "schemas/trust_ledger_remote_submission_preflight.schema.json"
    assert preflight_entry["urn"] == "urn:mullusi:schema:trust-ledger-remote-submission-preflight:1"
    assert preflight_entry["surface"] == "evidence"


def test_protocol_manifest_indexes_memory_lattice_admission() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    builder_entry = entries["low-code-builder-catalog"]
    marketplace_entry = entries["marketplace-sdk-catalog"]
    lattice_entry = entries["memory-lattice"]
    topology_entry = entries["p3-memory-topology-read-model"]

    assert validate_protocol_manifest(manifest) == []
    assert builder_entry["path"] == "schemas/low_code_builder_catalog.schema.json"
    assert builder_entry["urn"] == "urn:mullusi:schema:low-code-builder-catalog:1"
    assert builder_entry["surface"] == "builder"
    assert marketplace_entry["path"] == "schemas/marketplace_sdk_catalog.schema.json"
    assert marketplace_entry["urn"] == "urn:mullusi:schema:marketplace-sdk-catalog:1"
    assert marketplace_entry["surface"] == "marketplace"
    assert lattice_entry["path"] == "schemas/memory_lattice.schema.json"
    assert lattice_entry["urn"] == "urn:mullusi:schema:memory-lattice:1"
    assert lattice_entry["surface"] == "memory"
    assert topology_entry["path"] == "schemas/p3_memory_topology_read_model.schema.json"
    assert topology_entry["urn"] == "urn:mullusi:schema:p3-memory-topology-read-model:1"
    assert topology_entry["surface"] == "memory"


def test_protocol_manifest_indexes_multimodal_operation_receipt() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    multimodal_entry = entries["multimodal-operation-receipt"]

    assert validate_protocol_manifest(manifest) == []
    assert multimodal_entry["path"] == "schemas/multimodal_operation_receipt.schema.json"
    assert multimodal_entry["urn"] == "urn:mullusi:schema:multimodal-operation-receipt:1"
    assert multimodal_entry["surface"] == "multimodal"


def test_protocol_manifest_indexes_physical_action_receipt() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    physical_entry = entries["physical-action-receipt"]

    assert validate_protocol_manifest(manifest) == []
    assert physical_entry["path"] == "schemas/physical_action_receipt.schema.json"
    assert physical_entry["urn"] == "urn:mullusi:schema:physical-action-receipt:1"
    assert physical_entry["surface"] == "safety"


def test_protocol_manifest_indexes_physical_capability_promotion_receipt() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    receipt_entry = entries["physical-capability-promotion-receipt"]

    assert validate_protocol_manifest(manifest) == []
    assert receipt_entry["path"] == "schemas/physical_capability_promotion_receipt.schema.json"
    assert receipt_entry["urn"] == "urn:mullusi:schema:physical-capability-promotion-receipt:1"
    assert receipt_entry["surface"] == "safety"


def test_protocol_manifest_indexes_temporal_operation_receipt() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    temporal_entry = entries["temporal-operation-receipt"]

    assert validate_protocol_manifest(manifest) == []
    assert temporal_entry["path"] == "schemas/temporal_operation_receipt.schema.json"
    assert temporal_entry["urn"] == "urn:mullusi:schema:temporal-operation-receipt:1"
    assert temporal_entry["surface"] == "temporal"


def test_protocol_manifest_indexes_temporal_evidence_freshness_receipt() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    evidence_entry = entries["temporal-evidence-freshness-receipt"]

    assert validate_protocol_manifest(manifest) == []
    assert evidence_entry["path"] == "schemas/temporal_evidence_freshness_receipt.schema.json"
    assert evidence_entry["urn"] == "urn:mullusi:schema:temporal-evidence-freshness-receipt:1"
    assert evidence_entry["surface"] == "temporal"


def test_protocol_manifest_indexes_search_decision_receipt() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    search_entry = entries["search-decision-receipt"]

    assert validate_protocol_manifest(manifest) == []
    assert search_entry["path"] == "schemas/search_decision_receipt.schema.json"
    assert search_entry["urn"] == "urn:mullusi:schema:search-decision-receipt:1"
    assert search_entry["surface"] == "search"


def test_protocol_manifest_indexes_temporal_reapproval_receipt() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    reapproval_entry = entries["temporal-reapproval-receipt"]

    assert validate_protocol_manifest(manifest) == []
    assert reapproval_entry["path"] == "schemas/temporal_reapproval_receipt.schema.json"
    assert reapproval_entry["urn"] == "urn:mullusi:schema:temporal-reapproval-receipt:1"
    assert reapproval_entry["surface"] == "temporal"


def test_protocol_manifest_indexes_temporal_dispatch_window_receipt() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    dispatch_window_entry = entries["temporal-dispatch-window-receipt"]

    assert validate_protocol_manifest(manifest) == []
    assert dispatch_window_entry["path"] == "schemas/temporal_dispatch_window_receipt.schema.json"
    assert dispatch_window_entry["urn"] == "urn:mullusi:schema:temporal-dispatch-window-receipt:1"
    assert dispatch_window_entry["surface"] == "temporal"


def test_protocol_manifest_indexes_temporal_budget_window_receipt() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    budget_window_entry = entries["temporal-budget-window-receipt"]

    assert validate_protocol_manifest(manifest) == []
    assert budget_window_entry["path"] == "schemas/temporal_budget_window_receipt.schema.json"
    assert budget_window_entry["urn"] == "urn:mullusi:schema:temporal-budget-window-receipt:1"
    assert budget_window_entry["surface"] == "temporal"


def test_protocol_manifest_indexes_temporal_causal_order_receipt() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    causal_order_entry = entries["temporal-causal-order-receipt"]

    assert validate_protocol_manifest(manifest) == []
    assert causal_order_entry["path"] == "schemas/temporal_causal_order_receipt.schema.json"
    assert causal_order_entry["urn"] == "urn:mullusi:schema:temporal-causal-order-receipt:1"
    assert causal_order_entry["surface"] == "temporal"


def test_protocol_manifest_indexes_temporal_monotonic_duration_receipt() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    duration_entry = entries["temporal-monotonic-duration-receipt"]

    assert validate_protocol_manifest(manifest) == []
    assert duration_entry["path"] == "schemas/temporal_monotonic_duration_receipt.schema.json"
    assert duration_entry["urn"] == "urn:mullusi:schema:temporal-monotonic-duration-receipt:1"
    assert duration_entry["surface"] == "temporal"


def test_protocol_manifest_indexes_temporal_accepted_risk_expiry_receipt() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    accepted_risk_entry = entries["temporal-accepted-risk-expiry-receipt"]

    assert validate_protocol_manifest(manifest) == []
    assert accepted_risk_entry["path"] == "schemas/temporal_accepted_risk_expiry_receipt.schema.json"
    assert accepted_risk_entry["urn"] == "urn:mullusi:schema:temporal-accepted-risk-expiry-receipt:1"
    assert accepted_risk_entry["surface"] == "temporal"


def test_protocol_manifest_indexes_temporal_credential_expiry_receipt() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    credential_entry = entries["temporal-credential-expiry-receipt"]

    assert validate_protocol_manifest(manifest) == []
    assert credential_entry["path"] == "schemas/temporal_credential_expiry_receipt.schema.json"
    assert credential_entry["urn"] == "urn:mullusi:schema:temporal-credential-expiry-receipt:1"
    assert credential_entry["surface"] == "temporal"


def test_protocol_manifest_indexes_temporal_retention_window_receipt() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    retention_entry = entries["temporal-retention-window-receipt"]

    assert validate_protocol_manifest(manifest) == []
    assert retention_entry["path"] == "schemas/temporal_retention_window_receipt.schema.json"
    assert retention_entry["urn"] == "urn:mullusi:schema:temporal-retention-window-receipt:1"
    assert retention_entry["surface"] == "temporal"


def test_protocol_manifest_indexes_temporal_rate_limit_window_receipt() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    rate_limit_entry = entries["temporal-rate-limit-window-receipt"]

    assert validate_protocol_manifest(manifest) == []
    assert rate_limit_entry["path"] == "schemas/temporal_rate_limit_window_receipt.schema.json"
    assert rate_limit_entry["urn"] == "urn:mullusi:schema:temporal-rate-limit-window-receipt:1"
    assert rate_limit_entry["surface"] == "temporal"


def test_protocol_manifest_indexes_temporal_retry_window_receipt() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    retry_entry = entries["temporal-retry-window-receipt"]

    assert validate_protocol_manifest(manifest) == []
    assert retry_entry["path"] == "schemas/temporal_retry_window_receipt.schema.json"
    assert retry_entry["urn"] == "urn:mullusi:schema:temporal-retry-window-receipt:1"
    assert retry_entry["surface"] == "temporal"


def test_protocol_manifest_indexes_temporal_lease_window_receipt() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    lease_entry = entries["temporal-lease-window-receipt"]

    assert validate_protocol_manifest(manifest) == []
    assert lease_entry["path"] == "schemas/temporal_lease_window_receipt.schema.json"
    assert lease_entry["urn"] == "urn:mullusi:schema:temporal-lease-window-receipt:1"
    assert lease_entry["surface"] == "temporal"


def test_protocol_manifest_indexes_temporal_idempotency_window_receipt() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    idempotency_entry = entries["temporal-idempotency-window-receipt"]

    assert validate_protocol_manifest(manifest) == []
    assert idempotency_entry["path"] == "schemas/temporal_idempotency_window_receipt.schema.json"
    assert idempotency_entry["urn"] == "urn:mullusi:schema:temporal-idempotency-window-receipt:1"
    assert idempotency_entry["surface"] == "temporal"


def test_protocol_manifest_indexes_temporal_missed_run_receipt() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    missed_run_entry = entries["temporal-missed-run-receipt"]

    assert validate_protocol_manifest(manifest) == []
    assert missed_run_entry["path"] == "schemas/temporal_missed_run_receipt.schema.json"
    assert missed_run_entry["urn"] == "urn:mullusi:schema:temporal-missed-run-receipt:1"
    assert missed_run_entry["surface"] == "temporal"


def test_protocol_manifest_indexes_temporal_recurrence_window_receipt() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    recurrence_entry = entries["temporal-recurrence-window-receipt"]

    assert validate_protocol_manifest(manifest) == []
    assert recurrence_entry["path"] == "schemas/temporal_recurrence_window_receipt.schema.json"
    assert recurrence_entry["urn"] == "urn:mullusi:schema:temporal-recurrence-window-receipt:1"
    assert recurrence_entry["surface"] == "temporal"


def test_protocol_manifest_indexes_temporal_resolution_receipt() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    resolution_entry = entries["temporal-resolution-receipt"]

    assert validate_protocol_manifest(manifest) == []
    assert resolution_entry["path"] == "schemas/temporal_resolution_receipt.schema.json"
    assert resolution_entry["urn"] == "urn:mullusi:schema:temporal-resolution-receipt:1"
    assert resolution_entry["surface"] == "temporal"


def test_protocol_manifest_indexes_temporal_memory_receipt() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    memory_entry = entries["temporal-memory-receipt"]

    assert validate_protocol_manifest(manifest) == []
    assert memory_entry["path"] == "schemas/temporal_memory_receipt.schema.json"
    assert memory_entry["urn"] == "urn:mullusi:schema:temporal-memory-receipt:1"
    assert memory_entry["surface"] == "temporal"


def test_protocol_manifest_indexes_temporal_memory_refresh_receipt() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    refresh_entry = entries["temporal-memory-refresh-receipt"]

    assert validate_protocol_manifest(manifest) == []
    assert refresh_entry["path"] == "schemas/temporal_memory_refresh_receipt.schema.json"
    assert refresh_entry["urn"] == "urn:mullusi:schema:temporal-memory-refresh-receipt:1"
    assert refresh_entry["surface"] == "temporal"


def test_protocol_manifest_indexes_temporal_scheduler_receipt() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    scheduler_entry = entries["temporal-scheduler-receipt"]

    assert validate_protocol_manifest(manifest) == []
    assert scheduler_entry["path"] == "schemas/temporal_scheduler_receipt.schema.json"
    assert scheduler_entry["urn"] == "urn:mullusi:schema:temporal-scheduler-receipt:1"
    assert scheduler_entry["surface"] == "temporal"


def test_protocol_manifest_indexes_temporal_sla_receipt() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    sla_entry = entries["temporal-sla-receipt"]

    assert validate_protocol_manifest(manifest) == []
    assert sla_entry["path"] == "schemas/temporal_sla_receipt.schema.json"
    assert sla_entry["urn"] == "urn:mullusi:schema:temporal-sla-receipt:1"
    assert sla_entry["surface"] == "temporal"


def test_protocol_manifest_indexes_promotion_environment_bindings() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    binding_entry = entries["general-agent-promotion-environment-bindings"]

    assert validate_protocol_manifest(manifest) == []
    assert binding_entry["path"] == "schemas/general_agent_promotion_environment_bindings.schema.json"
    assert binding_entry["urn"] == "urn:mullusi:schema:general-agent-promotion-environment-bindings:1"
    assert binding_entry["surface"] == "promotion"


def test_protocol_manifest_indexes_promotion_environment_binding_receipt() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    receipt_entry = entries["general-agent-promotion-environment-binding-receipt"]

    assert validate_protocol_manifest(manifest) == []
    assert receipt_entry["path"] == "schemas/general_agent_promotion_environment_binding_receipt.schema.json"
    assert receipt_entry["urn"] == "urn:mullusi:schema:general-agent-promotion-environment-binding-receipt:1"
    assert receipt_entry["surface"] == "promotion"


def test_protocol_manifest_indexes_promotion_live_evidence_queue() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    queue_entry = entries["general-agent-promotion-live-evidence-queue"]
    operator_request_entry = entries["general-agent-promotion-live-evidence-operator-input-request"]

    assert validate_protocol_manifest(manifest) == []
    assert queue_entry["path"] == "schemas/general_agent_promotion_live_evidence_queue.schema.json"
    assert queue_entry["urn"] == "urn:mullusi:schema:general-agent-promotion-live-evidence-queue:1"
    assert queue_entry["surface"] == "promotion"
    assert (
        operator_request_entry["path"]
        == "schemas/general_agent_promotion_live_evidence_operator_input_request.schema.json"
    )
    assert (
        operator_request_entry["urn"]
        == "urn:mullusi:schema:general-agent-promotion-live-evidence-operator-input-request:1"
    )
    assert operator_request_entry["surface"] == "promotion"


def test_protocol_manifest_indexes_promotion_terminal_certificate_gate() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    approval_entry = entries["general-agent-promotion-terminal-approvals"]
    gate_entry = entries["general-agent-promotion-terminal-certificate-gate"]
    candidate_entry = entries["general-agent-promotion-terminal-certificate-candidates"]
    reconciliation_entry = entries["general-agent-promotion-terminal-evidence-reconciliation"]
    minting_gate_entry = entries["general-agent-promotion-terminal-minting-gate"]
    minting_run_entry = entries["general-agent-promotion-terminal-certificate-minting-run"]

    assert validate_protocol_manifest(manifest) == []
    assert approval_entry["path"] == "schemas/general_agent_promotion_terminal_approvals.schema.json"
    assert approval_entry["urn"] == "urn:mullusi:schema:general-agent-promotion-terminal-approvals:1"
    assert approval_entry["surface"] == "promotion"
    assert gate_entry["path"] == "schemas/general_agent_promotion_terminal_certificate_gate.schema.json"
    assert gate_entry["urn"] == "urn:mullusi:schema:general-agent-promotion-terminal-certificate-gate:1"
    assert gate_entry["surface"] == "promotion"
    assert candidate_entry["path"] == "schemas/general_agent_promotion_terminal_certificate_candidates.schema.json"
    assert candidate_entry["urn"] == "urn:mullusi:schema:general-agent-promotion-terminal-certificate-candidates:1"
    assert candidate_entry["surface"] == "promotion"
    assert reconciliation_entry["path"] == "schemas/general_agent_promotion_terminal_evidence_reconciliation.schema.json"
    assert reconciliation_entry["urn"] == (
        "urn:mullusi:schema:general-agent-promotion-terminal-evidence-reconciliation:1"
    )
    assert reconciliation_entry["surface"] == "promotion"
    assert minting_gate_entry["path"] == "schemas/general_agent_promotion_terminal_minting_gate.schema.json"
    assert minting_gate_entry["urn"] == "urn:mullusi:schema:general-agent-promotion-terminal-minting-gate:1"
    assert minting_gate_entry["surface"] == "promotion"
    assert minting_run_entry["path"] == "schemas/general_agent_promotion_terminal_certificate_minting_run.schema.json"
    assert minting_run_entry["urn"] == (
        "urn:mullusi:schema:general-agent-promotion-terminal-certificate-minting-run:1"
    )
    assert minting_run_entry["surface"] == "promotion"


def test_protocol_manifest_indexes_promotion_handoff_packet() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    packet_entry = entries["general-agent-promotion-handoff-packet"]

    assert validate_protocol_manifest(manifest) == []
    assert packet_entry["path"] == "schemas/general_agent_promotion_handoff_packet.schema.json"
    assert packet_entry["urn"] == "urn:mullusi:schema:general-agent-promotion-handoff-packet:1"
    assert packet_entry["surface"] == "promotion"


def test_protocol_manifest_indexes_gateway_publication_readiness() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    readiness_entry = entries["gateway-publication-readiness"]

    assert validate_protocol_manifest(manifest) == []
    assert readiness_entry["path"] == "schemas/gateway_publication_readiness.schema.json"
    assert readiness_entry["urn"] == "urn:mullusi:schema:gateway-publication-readiness:1"
    assert readiness_entry["surface"] == "deployment"


def test_protocol_manifest_indexes_gateway_dns_resolution_receipt() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    receipt_entry = entries["gateway-dns-resolution-receipt"]

    assert validate_protocol_manifest(manifest) == []
    assert receipt_entry["path"] == "schemas/gateway_dns_resolution_receipt.schema.json"
    assert receipt_entry["urn"] == "urn:mullusi:schema:gateway-dns-resolution-receipt:1"
    assert receipt_entry["surface"] == "deployment"


def test_protocol_manifest_indexes_gateway_dns_target_binding_receipt() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    receipt_entry = entries["gateway-dns-target-binding-receipt"]

    assert validate_protocol_manifest(manifest) == []
    assert receipt_entry["path"] == "schemas/gateway_dns_target_binding_receipt.schema.json"
    assert receipt_entry["urn"] == "urn:mullusi:schema:gateway-dns-target-binding-receipt:1"
    assert receipt_entry["surface"] == "deployment"


def test_protocol_manifest_indexes_gateway_publication_receipt_validation() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    validation_entry = entries["gateway-publication-receipt-validation"]

    assert validate_protocol_manifest(manifest) == []
    assert validation_entry["path"] == "schemas/gateway_publication_receipt_validation.schema.json"
    assert validation_entry["urn"] == "urn:mullusi:schema:gateway-publication-receipt-validation:1"
    assert validation_entry["surface"] == "deployment"


def test_protocol_manifest_indexes_operational_intelligence_contracts() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    action_orchestration_entry = entries["universal-action-orchestration"]
    action_orchestration_validation_receipt_entry = entries["universal-action-orchestration-validation-receipt"]
    evidence_graph_entry = entries["universal-evidence-graph"]
    goal_entry = entries["goal"]
    simulation_entry = entries["simulation-receipt"]
    symbolic_simulation_entry = entries["symbolic-simulation-engine"]
    state_engine_entry = entries["universal-state-engine"]
    coordination_receipt_entry = entries["intelligence-coordination-episode-receipt"]
    world_state_entry = entries["world-state"]

    assert validate_protocol_manifest(manifest) == []
    assert action_orchestration_entry["path"] == "schemas/universal_action_orchestration.schema.json"
    assert action_orchestration_entry["urn"] == "urn:mullusi:schema:universal-action-orchestration:1"
    assert action_orchestration_entry["surface"] == "orchestration"
    assert action_orchestration_validation_receipt_entry["path"] == (
        "schemas/universal_action_orchestration_validation_receipt.schema.json"
    )
    assert action_orchestration_validation_receipt_entry["urn"] == (
        "urn:mullusi:schema:universal-action-orchestration-validation-receipt:1"
    )
    assert action_orchestration_validation_receipt_entry["surface"] == "orchestration"
    assert evidence_graph_entry["path"] == "schemas/universal_evidence_graph.schema.json"
    assert evidence_graph_entry["urn"] == "urn:mullusi:schema:universal-evidence-graph:1"
    assert evidence_graph_entry["surface"] == "orchestration"
    assert goal_entry["path"] == "schemas/goal.schema.json"
    assert goal_entry["urn"] == "urn:mullusi:schema:goal:1"
    assert goal_entry["surface"] == "planning"
    assert simulation_entry["path"] == "schemas/simulation_receipt.schema.json"
    assert simulation_entry["urn"] == "urn:mullusi:schema:simulation-receipt:1"
    assert simulation_entry["surface"] == "simulation"
    assert symbolic_simulation_entry["path"] == "schemas/symbolic_simulation_engine.schema.json"
    assert symbolic_simulation_entry["urn"] == "urn:mullusi:schema:symbolic-simulation-engine:1"
    assert symbolic_simulation_entry["surface"] == "simulation"
    assert state_engine_entry["path"] == "schemas/universal_state_engine.schema.json"
    assert state_engine_entry["urn"] == "urn:mullusi:schema:universal-state-engine:1"
    assert state_engine_entry["surface"] == "state"
    assert coordination_receipt_entry["path"] == "schemas/intelligence_coordination_episode_receipt.schema.json"
    assert coordination_receipt_entry["urn"] == "urn:mullusi:schema:intelligence-coordination-episode-receipt:1"
    assert coordination_receipt_entry["surface"] == "coordination"
    assert world_state_entry["path"] == "schemas/world_state.schema.json"
    assert world_state_entry["urn"] == "urn:mullusi:schema:world-state:1"
    assert world_state_entry["surface"] == "world"


def test_protocol_manifest_indexes_workflow_mining_report() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    workflow_entry = entries["workflow-mining-report"]
    workflow_run_entry = entries["workflow-run"]

    assert validate_protocol_manifest(manifest) == []
    assert workflow_entry["path"] == "schemas/workflow_mining_report.schema.json"
    assert workflow_entry["urn"] == "urn:mullusi:schema:workflow-mining-report:1"
    assert workflow_entry["surface"] == "workflow"
    assert workflow_run_entry["path"] == "schemas/workflow_run.schema.json"
    assert workflow_run_entry["urn"] == "urn:mullusi:schema:workflow-run:1"
    assert workflow_run_entry["surface"] == "workflow"


def test_protocol_manifest_indexes_terminal_closure_certificate() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    closure_entry = entries["terminal-closure-certificate"]

    assert validate_protocol_manifest(manifest) == []
    assert closure_entry["path"] == "schemas/terminal_closure_certificate.schema.json"
    assert closure_entry["urn"] == "urn:mullusi:schema:terminal-closure-certificate:1"
    assert closure_entry["surface"] == "closure"


def test_protocol_manifest_indexes_worker_mesh_contract() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    worker_entry = entries["worker-mesh"]
    failure_entry = entries["worker-failure-receipt"]
    first_worker_entry = entries["read-only-first-worker-path"]
    document_worker_entry = entries["read-only-document-worker-path"]
    search_worker_entry = entries["read-only-search-worker-path"]

    assert validate_protocol_manifest(manifest) == []
    assert worker_entry["path"] == "schemas/worker_mesh.schema.json"
    assert worker_entry["urn"] == "urn:mullusi:schema:worker-mesh:1"
    assert worker_entry["surface"] == "worker"
    assert failure_entry["path"] == "schemas/worker_failure_receipt.schema.json"
    assert failure_entry["urn"] == "urn:mullusi:schema:worker-failure-receipt:1"
    assert failure_entry["surface"] == "worker"
    assert first_worker_entry["path"] == "schemas/read_only_first_worker_path.schema.json"
    assert first_worker_entry["urn"] == "urn:mullusi:schema:read-only-first-worker-path:1"
    assert first_worker_entry["surface"] == "worker"
    assert document_worker_entry["path"] == "schemas/read_only_document_worker_path.schema.json"
    assert document_worker_entry["urn"] == "urn:mullusi:schema:read-only-document-worker-path:1"
    assert document_worker_entry["surface"] == "worker"
    assert search_worker_entry["path"] == "schemas/read_only_search_worker_path.schema.json"
    assert search_worker_entry["urn"] == "urn:mullusi:schema:read-only-search-worker-path:1"
    assert search_worker_entry["surface"] == "worker"


def test_protocol_manifest_indexes_worker_failure_receipt_contract() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    worker_failure_entry = entries["worker-failure-receipt"]

    assert validate_protocol_manifest(manifest) == []
    assert worker_failure_entry["path"] == "schemas/worker_failure_receipt.schema.json"
    assert worker_failure_entry["urn"] == "urn:mullusi:schema:worker-failure-receipt:1"
    assert worker_failure_entry["surface"] == "worker"


def test_protocol_manifest_indexes_read_only_worker_binding_contract() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    read_only_worker_entry = entries["read-only-worker-binding"]

    assert validate_protocol_manifest(manifest) == []
    assert read_only_worker_entry["path"] == "schemas/read_only_worker_binding.schema.json"
    assert read_only_worker_entry["urn"] == "urn:mullusi:schema:read-only-worker-binding:1"
    assert read_only_worker_entry["surface"] == "worker"


def test_protocol_manifest_indexes_read_only_worker_lease_preflight_contract() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    preflight_entry = entries["read-only-worker-lease-preflight"]

    assert validate_protocol_manifest(manifest) == []
    assert preflight_entry["path"] == "schemas/read_only_worker_lease_preflight.schema.json"
    assert preflight_entry["urn"] == "urn:mullusi:schema:read-only-worker-lease-preflight:1"
    assert preflight_entry["surface"] == "worker"


def test_protocol_manifest_indexes_read_only_worker_rehearsal_receipt_contract() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    rehearsal_entry = entries["read-only-worker-rehearsal-receipt"]

    assert validate_protocol_manifest(manifest) == []
    assert rehearsal_entry["path"] == "schemas/read_only_worker_rehearsal_receipt.schema.json"
    assert rehearsal_entry["urn"] == "urn:mullusi:schema:read-only-worker-rehearsal-receipt:1"
    assert rehearsal_entry["surface"] == "worker"


def test_protocol_manifest_indexes_read_only_worker_runtime_receipt_handoff_contract() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    handoff_entry = entries["read-only-worker-runtime-receipt-handoff"]

    assert validate_protocol_manifest(manifest) == []
    assert handoff_entry["path"] == "schemas/read_only_worker_runtime_receipt_handoff.schema.json"
    assert handoff_entry["urn"] == "urn:mullusi:schema:read-only-worker-runtime-receipt-handoff:1"
    assert handoff_entry["surface"] == "worker"


def test_protocol_manifest_indexes_read_only_worker_runtime_receipt_emitter_dry_run_contract() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    dry_run_entry = entries["read-only-worker-runtime-receipt-emitter-dry-run"]

    assert validate_protocol_manifest(manifest) == []
    assert dry_run_entry["path"] == "schemas/read_only_worker_runtime_receipt_emitter_dry_run.schema.json"
    assert dry_run_entry["urn"] == "urn:mullusi:schema:read-only-worker-runtime-receipt-emitter-dry-run:1"
    assert dry_run_entry["surface"] == "worker"


def test_protocol_manifest_indexes_read_only_worker_runtime_runner_binding_witness_contract() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    witness_entry = entries["read-only-worker-runtime-runner-binding-witness"]

    assert validate_protocol_manifest(manifest) == []
    assert witness_entry["path"] == "schemas/read_only_worker_runtime_runner_binding_witness.schema.json"
    assert witness_entry["urn"] == "urn:mullusi:schema:read-only-worker-runtime-runner-binding-witness:1"
    assert witness_entry["surface"] == "worker"


def test_protocol_manifest_indexes_read_only_worker_runtime_receipt_candidate_contract() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    candidate_entry = entries["read-only-worker-runtime-receipt-candidate"]

    assert validate_protocol_manifest(manifest) == []
    assert candidate_entry["path"] == "schemas/read_only_worker_runtime_receipt_candidate.schema.json"
    assert candidate_entry["urn"] == "urn:mullusi:schema:read-only-worker-runtime-receipt-candidate:1"
    assert candidate_entry["surface"] == "worker"


def test_protocol_manifest_indexes_read_only_worker_runtime_receipt_schema_binding_witness_contract() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    witness_entry = entries["read-only-worker-runtime-receipt-schema-binding-witness"]

    assert validate_protocol_manifest(manifest) == []
    assert witness_entry["path"] == "schemas/read_only_worker_runtime_receipt_schema_binding_witness.schema.json"
    assert witness_entry["urn"] == "urn:mullusi:schema:read-only-worker-runtime-receipt-schema-binding-witness:1"
    assert witness_entry["surface"] == "worker"


def test_protocol_manifest_indexes_read_only_worker_runtime_receipt_store_write_path_witness_contract() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    witness_entry = entries["read-only-worker-runtime-receipt-store-write-path-witness"]

    assert validate_protocol_manifest(manifest) == []
    assert witness_entry["path"] == "schemas/read_only_worker_runtime_receipt_store_write_path_witness.schema.json"
    assert witness_entry["urn"] == (
        "urn:mullusi:schema:read-only-worker-runtime-receipt-store-write-path-witness:1"
    )
    assert witness_entry["surface"] == "worker"


def test_protocol_manifest_indexes_read_only_worker_runtime_runner_registration_witness_contract() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    witness_entry = entries["read-only-worker-runtime-runner-registration-witness"]

    assert validate_protocol_manifest(manifest) == []
    assert witness_entry["path"] == "schemas/read_only_worker_runtime_runner_registration_witness.schema.json"
    assert witness_entry["urn"] == (
        "urn:mullusi:schema:read-only-worker-runtime-runner-registration-witness:1"
    )
    assert witness_entry["surface"] == "worker"


def test_protocol_manifest_indexes_read_only_worker_runtime_dispatch_endpoint_registration_witness_contract() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    witness_entry = entries["read-only-worker-runtime-dispatch-endpoint-registration-witness"]

    assert validate_protocol_manifest(manifest) == []
    assert witness_entry["path"] == "schemas/read_only_worker_runtime_dispatch_endpoint_registration_witness.schema.json"
    assert witness_entry["urn"] == (
        "urn:mullusi:schema:read-only-worker-runtime-dispatch-endpoint-registration-witness:1"
    )
    assert witness_entry["surface"] == "worker"


def test_protocol_manifest_indexes_read_only_worker_runtime_receipt_emitter_registration_witness_contract() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    witness_entry = entries["read-only-worker-runtime-receipt-emitter-registration-witness"]

    assert validate_protocol_manifest(manifest) == []
    assert witness_entry["path"] == "schemas/read_only_worker_runtime_receipt_emitter_registration_witness.schema.json"
    assert witness_entry["urn"] == (
        "urn:mullusi:schema:read-only-worker-runtime-receipt-emitter-registration-witness:1"
    )
    assert witness_entry["surface"] == "worker"


def test_protocol_manifest_indexes_read_only_worker_runtime_receipt_schema_binding_activation_witness_contract() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    witness_entry = entries["read-only-worker-runtime-receipt-schema-binding-activation-witness"]

    assert validate_protocol_manifest(manifest) == []
    assert witness_entry["path"] == (
        "schemas/read_only_worker_runtime_receipt_schema_binding_activation_witness.schema.json"
    )
    assert witness_entry["urn"] == (
        "urn:mullusi:schema:read-only-worker-runtime-receipt-schema-binding-activation-witness:1"
    )
    assert witness_entry["surface"] == "worker"



def test_protocol_manifest_indexes_read_only_worker_runtime_receipt_store_activation_witness_contract() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    witness_entry = entries["read-only-worker-runtime-receipt-store-activation-witness"]

    assert validate_protocol_manifest(manifest) == []
    assert witness_entry["path"] == "schemas/read_only_worker_runtime_receipt_store_activation_witness.schema.json"
    assert witness_entry["urn"] == "urn:mullusi:schema:read-only-worker-runtime-receipt-store-activation-witness:1"
    assert witness_entry["surface"] == "worker"


def test_protocol_manifest_indexes_read_only_worker_runtime_receipt_store_operator_approval_witness_contract() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    witness_entry = entries["read-only-worker-runtime-receipt-store-operator-approval-witness"]

    assert validate_protocol_manifest(manifest) == []
    assert (
        witness_entry["path"]
        == "schemas/read_only_worker_runtime_receipt_store_operator_approval_witness.schema.json"
    )
    assert (
        witness_entry["urn"]
        == "urn:mullusi:schema:read-only-worker-runtime-receipt-store-operator-approval-witness:1"
    )
    assert witness_entry["surface"] == "worker"


def test_protocol_manifest_indexes_read_only_worker_runtime_receipt_emission_admission_witness_contract() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    witness_entry = entries["read-only-worker-runtime-receipt-emission-admission-witness"]

    assert validate_protocol_manifest(manifest) == []
    assert witness_entry["path"] == "schemas/read_only_worker_runtime_receipt_emission_admission_witness.schema.json"
    assert witness_entry["urn"] == "urn:mullusi:schema:read-only-worker-runtime-receipt-emission-admission-witness:1"
    assert witness_entry["surface"] == "worker"


def test_protocol_manifest_indexes_read_only_worker_runtime_active_lease_admission_witness_contract() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    witness_entry = entries["read-only-worker-runtime-active-lease-admission-witness"]

    assert validate_protocol_manifest(manifest) == []
    assert witness_entry["path"] == "schemas/read_only_worker_runtime_active_lease_admission_witness.schema.json"
    assert witness_entry["urn"] == "urn:mullusi:schema:read-only-worker-runtime-active-lease-admission-witness:1"
    assert witness_entry["surface"] == "worker"


def test_protocol_manifest_indexes_read_only_worker_runtime_authority_chain_witness_contract() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    witness_entry = entries["read-only-worker-runtime-authority-chain-witness"]

    assert validate_protocol_manifest(manifest) == []
    assert witness_entry["path"] == "schemas/read_only_worker_runtime_authority_chain_witness.schema.json"
    assert witness_entry["urn"] == "urn:mullusi:schema:read-only-worker-runtime-authority-chain-witness:1"
    assert witness_entry["surface"] == "worker"


def test_protocol_manifest_indexes_read_only_worker_runtime_dispatch_admission_witness_contract() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    witness_entry = entries["read-only-worker-runtime-dispatch-admission-witness"]

    assert validate_protocol_manifest(manifest) == []
    assert witness_entry["path"] == "schemas/read_only_worker_runtime_dispatch_admission_witness.schema.json"
    assert witness_entry["urn"] == "urn:mullusi:schema:read-only-worker-runtime-dispatch-admission-witness:1"
    assert witness_entry["surface"] == "worker"


def test_protocol_manifest_indexes_read_only_worker_active_runtime_lease_admission_witness_contract() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    witness_entry = entries["read-only-worker-active-runtime-lease-admission-witness"]

    assert validate_protocol_manifest(manifest) == []
    assert (
        witness_entry["path"]
        == "schemas/read_only_worker_active_runtime_lease_admission_witness.schema.json"
    )
    assert (
        witness_entry["urn"]
        == "urn:mullusi:schema:read-only-worker-active-runtime-lease-admission-witness:1"
    )
    assert witness_entry["surface"] == "worker"


def test_protocol_manifest_indexes_read_only_worker_uao_dispatch_authorization_witness_contract() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    witness_entry = entries["read-only-worker-uao-dispatch-authorization-witness"]

    assert validate_protocol_manifest(manifest) == []
    assert (
        witness_entry["path"]
        == "schemas/read_only_worker_uao_dispatch_authorization_witness.schema.json"
    )
    assert (
        witness_entry["urn"]
        == "urn:mullusi:schema:read-only-worker-uao-dispatch-authorization-witness:1"
    )
    assert witness_entry["surface"] == "worker"


def test_protocol_manifest_indexes_read_only_worker_phi_gov_dispatch_authorization_witness_contract() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    witness_entry = entries["read-only-worker-phi-gov-dispatch-authorization-witness"]

    assert validate_protocol_manifest(manifest) == []
    assert (
        witness_entry["path"]
        == "schemas/read_only_worker_phi_gov_dispatch_authorization_witness.schema.json"
    )
    assert (
        witness_entry["urn"]
        == "urn:mullusi:schema:read-only-worker-phi-gov-dispatch-authorization-witness:1"
    )
    assert witness_entry["surface"] == "worker"


def test_protocol_manifest_indexes_universal_symbol_runtime_authority_witness() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    witness_entry = entries["universal-symbol-runtime-authority-witness"]

    assert validate_protocol_manifest(manifest) == []
    assert witness_entry["path"] == "schemas/universal_symbol_runtime_authority_witness.schema.json"
    assert witness_entry["urn"] == "urn:mullusi:schema:universal-symbol-runtime-authority-witness:1"
    assert witness_entry["surface"] == "symbol"


def test_protocol_manifest_indexes_universal_symbol_runtime_admission_evidence_receipt() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    receipt_entry = entries["universal-symbol-runtime-admission-evidence-receipt"]

    assert validate_protocol_manifest(manifest) == []
    assert receipt_entry["path"] == "schemas/universal_symbol_runtime_admission_evidence_receipt.schema.json"
    assert receipt_entry["urn"] == "urn:mullusi:schema:universal-symbol-runtime-admission-evidence-receipt:1"
    assert receipt_entry["surface"] == "symbol"


def test_protocol_manifest_indexes_universal_symbol_runtime_live_witness_input_receipt() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    receipt_entry = entries["universal-symbol-runtime-live-witness-input-receipt"]

    assert validate_protocol_manifest(manifest) == []
    assert receipt_entry["path"] == "schemas/universal_symbol_runtime_live_witness_input_receipt.schema.json"
    assert receipt_entry["urn"] == "urn:mullusi:schema:universal-symbol-runtime-live-witness-input-receipt:1"
    assert receipt_entry["surface"] == "symbol"


def test_protocol_manifest_indexes_universal_symbol_lane_runtime_authority_evidence_receipt() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    receipt_entry = entries["universal-symbol-lane-runtime-authority-evidence-receipt"]

    assert validate_protocol_manifest(manifest) == []
    assert receipt_entry["path"] == "schemas/universal_symbol_lane_runtime_authority_evidence_receipt.schema.json"
    assert receipt_entry["urn"] == "urn:mullusi:schema:universal-symbol-lane-runtime-authority-evidence-receipt:1"
    assert receipt_entry["surface"] == "symbol"


def test_protocol_manifest_indexes_universal_symbol_runtime_authority_read_model() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    read_model_entry = entries["universal-symbol-runtime-authority-read-model"]

    assert validate_protocol_manifest(manifest) == []
    assert read_model_entry["path"] == "schemas/universal_symbol_runtime_authority_read_model.schema.json"
    assert read_model_entry["urn"] == "urn:mullusi:schema:universal-symbol-runtime-authority-read-model:1"
    assert read_model_entry["surface"] == "symbol"


def test_protocol_manifest_indexes_universal_symbol_skill_runtime_authority_witness() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    witness_entry = entries["universal-symbol-skill-runtime-authority-witness"]

    assert validate_protocol_manifest(manifest) == []
    assert witness_entry["path"] == "schemas/universal_symbol_skill_runtime_authority_witness.schema.json"
    assert witness_entry["urn"] == "urn:mullusi:schema:universal-symbol-skill-runtime-authority-witness:1"
    assert witness_entry["surface"] == "symbol"

def test_protocol_manifest_indexes_universal_symbol_replacement_replay_idempotency_witness() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    witness_entry = entries[
        "universal-symbol-receipt-store-replacement-decision-replay-idempotency-witness"
    ]

    assert validate_protocol_manifest(manifest) == []
    assert witness_entry["path"] == (
        "schemas/universal_symbol_receipt_store_replacement_decision_replay_idempotency_witness.schema.json"
    )
    assert witness_entry["urn"] == (
        "urn:mullusi:schema:universal-symbol-receipt-store-replacement-decision-replay-idempotency-witness:1"
    )
    assert witness_entry["surface"] == "symbol"

def test_protocol_manifest_indexes_read_only_worker_effect_reconciliation_witness_contract() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    witness_entry = entries["read-only-worker-effect-reconciliation-witness"]

    assert validate_protocol_manifest(manifest) == []
    assert witness_entry["path"] == "schemas/read_only_worker_effect_reconciliation_witness.schema.json"
    assert witness_entry["urn"] == "urn:mullusi:schema:read-only-worker-effect-reconciliation-witness:1"
    assert witness_entry["surface"] == "worker"


def test_protocol_manifest_indexes_read_only_worker_receipt_append_witness_contract() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    witness_entry = entries["read-only-worker-receipt-append-witness"]

    assert validate_protocol_manifest(manifest) == []
    assert witness_entry["path"] == "schemas/read_only_worker_receipt_append_witness.schema.json"
    assert witness_entry["urn"] == "urn:mullusi:schema:read-only-worker-receipt-append-witness:1"
    assert witness_entry["surface"] == "worker"


def test_protocol_manifest_indexes_read_only_worker_terminal_closure_witness_contract() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    witness_entry = entries["read-only-worker-terminal-closure-witness"]

    assert validate_protocol_manifest(manifest) == []
    assert witness_entry["path"] == "schemas/read_only_worker_terminal_closure_witness.schema.json"
    assert witness_entry["urn"] == "urn:mullusi:schema:read-only-worker-terminal-closure-witness:1"
    assert witness_entry["surface"] == "worker"


def test_protocol_manifest_indexes_read_only_worker_runtime_enablement_witness_contract() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    witness_entry = entries["read-only-worker-runtime-enablement-witness"]

    assert validate_protocol_manifest(manifest) == []
    assert witness_entry["path"] == "schemas/read_only_worker_runtime_enablement_witness.schema.json"
    assert witness_entry["urn"] == "urn:mullusi:schema:read-only-worker-runtime-enablement-witness:1"
    assert witness_entry["surface"] == "worker"


def test_protocol_manifest_indexes_read_only_worker_runtime_enablement_operator_input_request_contract() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    request_entry = entries["read-only-worker-runtime-enablement-operator-input-request"]

    assert validate_protocol_manifest(manifest) == []
    assert request_entry["path"] == (
        "schemas/read_only_worker_runtime_enablement_operator_input_request.schema.json"
    )
    assert request_entry["urn"] == (
        "urn:mullusi:schema:read-only-worker-runtime-enablement-operator-input-request:1"
    )
    assert request_entry["surface"] == "worker"


def test_protocol_manifest_indexes_read_only_worker_runtime_enablement_evidence_request_status_ledger_contract() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    ledger_entry = entries["read-only-worker-runtime-enablement-evidence-request-status-ledger"]

    assert validate_protocol_manifest(manifest) == []
    assert ledger_entry["path"] == (
        "schemas/read_only_worker_runtime_enablement_evidence_request_status_ledger.schema.json"
    )
    assert ledger_entry["urn"] == (
        "urn:mullusi:schema:read-only-worker-runtime-enablement-evidence-request-status-ledger:1"
    )
    assert ledger_entry["surface"] == "worker"


def test_protocol_manifest_indexes_read_only_worker_runtime_enablement_submitted_evidence_refs_contract() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    evidence_refs_entry = entries["read-only-worker-runtime-enablement-submitted-evidence-refs"]

    assert validate_protocol_manifest(manifest) == []
    assert evidence_refs_entry["path"] == (
        "schemas/read_only_worker_runtime_enablement_submitted_evidence_refs.schema.json"
    )
    assert evidence_refs_entry["urn"] == (
        "urn:mullusi:schema:read-only-worker-runtime-enablement-submitted-evidence-refs:1"
    )
    assert evidence_refs_entry["surface"] == "worker"


def test_protocol_manifest_indexes_read_only_worker_runtime_enablement_review_packet_contract() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    review_packet_entry = entries["read-only-worker-runtime-enablement-review-packet"]

    assert validate_protocol_manifest(manifest) == []
    assert review_packet_entry["path"] == (
        "schemas/read_only_worker_runtime_enablement_review_packet.schema.json"
    )
    assert review_packet_entry["urn"] == (
        "urn:mullusi:schema:read-only-worker-runtime-enablement-review-packet:1"
    )
    assert review_packet_entry["surface"] == "worker"


def test_protocol_manifest_indexes_read_only_worker_runtime_enablement_evidence_acceptance_gate_contract() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    gate_entry = entries["read-only-worker-runtime-enablement-evidence-acceptance-gate"]

    assert validate_protocol_manifest(manifest) == []
    assert gate_entry["path"] == (
        "schemas/read_only_worker_runtime_enablement_evidence_acceptance_gate.schema.json"
    )
    assert gate_entry["urn"] == (
        "urn:mullusi:schema:read-only-worker-runtime-enablement-evidence-acceptance-gate:1"
    )
    assert gate_entry["surface"] == "worker"


def test_protocol_manifest_indexes_read_only_worker_runtime_enablement_admission_gate_contract() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    gate_entry = entries["read-only-worker-runtime-enablement-admission-gate"]

    assert validate_protocol_manifest(manifest) == []
    assert gate_entry["path"] == "schemas/read_only_worker_runtime_enablement_admission_gate.schema.json"
    assert gate_entry["urn"] == "urn:mullusi:schema:read-only-worker-runtime-enablement-admission-gate:1"
    assert gate_entry["surface"] == "worker"


def test_protocol_manifest_indexes_read_only_worker_runtime_enablement_promotion_decision_contract() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    decision_entry = entries["read-only-worker-runtime-enablement-promotion-decision"]

    assert validate_protocol_manifest(manifest) == []
    assert decision_entry["path"] == "schemas/read_only_worker_runtime_enablement_promotion_decision.schema.json"
    assert decision_entry["urn"] == "urn:mullusi:schema:read-only-worker-runtime-enablement-promotion-decision:1"
    assert decision_entry["surface"] == "worker"


def test_protocol_manifest_indexes_read_only_worker_runtime_foundation_closure_summary_contract() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    summary_entry = entries["read-only-worker-runtime-foundation-closure-summary"]

    assert validate_protocol_manifest(manifest) == []
    assert summary_entry["path"] == "schemas/read_only_worker_runtime_foundation_closure_summary.schema.json"
    assert summary_entry["urn"] == "urn:mullusi:schema:read-only-worker-runtime-foundation-closure-summary:1"
    assert summary_entry["surface"] == "worker"


def test_protocol_manifest_indexes_read_only_worker_operator_runtime_enablement_approval_ref_contract() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    approval_ref_entry = entries["read-only-worker-operator-runtime-enablement-approval-ref"]

    assert validate_protocol_manifest(manifest) == []
    assert approval_ref_entry["path"] == (
        "schemas/read_only_worker_operator_runtime_enablement_approval_ref.schema.json"
    )
    assert approval_ref_entry["urn"] == (
        "urn:mullusi:schema:read-only-worker-operator-runtime-enablement-approval-ref:1"
    )
    assert approval_ref_entry["surface"] == "worker"


def test_protocol_manifest_indexes_read_only_worker_runtime_disablement_rollback_plan_contract() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    plan_entry = entries["read-only-worker-runtime-disablement-rollback-plan"]

    assert validate_protocol_manifest(manifest) == []
    assert plan_entry["path"] == (
        "schemas/read_only_worker_runtime_disablement_rollback_plan.schema.json"
    )
    assert plan_entry["urn"] == (
        "urn:mullusi:schema:read-only-worker-runtime-disablement-rollback-plan:1"
    )
    assert plan_entry["surface"] == "worker"


def test_protocol_manifest_indexes_read_only_worker_trusted_runtime_clock_receipt_contract() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    receipt_entry = entries["read-only-worker-trusted-runtime-clock-receipt"]

    assert validate_protocol_manifest(manifest) == []
    assert receipt_entry["path"] == (
        "schemas/read_only_worker_trusted_runtime_clock_receipt.schema.json"
    )
    assert receipt_entry["urn"] == (
        "urn:mullusi:schema:read-only-worker-trusted-runtime-clock-receipt:1"
    )
    assert receipt_entry["surface"] == "worker"


def test_protocol_manifest_indexes_snet_operator_read_model_contract() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    mesh_receipt_entry = entries["snet-mesh-receipt"]
    read_model_entry = entries["snet-operator-read-model"]
    episode_entry = entries["snet-episode"]

    assert validate_protocol_manifest(manifest) == []
    assert mesh_receipt_entry["path"] == "schemas/snet_mesh_receipt.schema.json"
    assert mesh_receipt_entry["urn"] == "urn:mullusi:schema:snet-mesh-receipt:1"
    assert mesh_receipt_entry["surface"] == "symbolic_mesh"
    assert read_model_entry["path"] == "schemas/snet_operator_read_model.schema.json"
    assert read_model_entry["urn"] == "urn:mullusi:schema:snet-operator-read-model:1"
    assert read_model_entry["surface"] == "symbolic_mesh"
    assert episode_entry["path"] == "schemas/snet_episode.schema.json"
    assert episode_entry["urn"] == "urn:mullusi:schema:snet-episode:1"
    assert episode_entry["surface"] == "symbolic_mesh"


def test_protocol_manifest_indexes_reflex_deployment_witness_envelope() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    envelope_entry = entries["reflex-deployment-witness-envelope"]

    assert validate_protocol_manifest(manifest) == []
    assert envelope_entry["path"] == "schemas/reflex_deployment_witness_envelope.schema.json"
    assert envelope_entry["urn"] == "urn:mullusi:schema:reflex-deployment-witness-envelope:1"
    assert envelope_entry["surface"] == "deployment"


def test_protocol_manifest_indexes_reflex_validator_receipt() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    receipt_entry = entries["reflex-deployment-witness-validator-receipt"]

    assert validate_protocol_manifest(manifest) == []
    assert receipt_entry["path"] == "schemas/reflex_deployment_witness_validator_receipt.schema.json"
    assert receipt_entry["urn"] == "urn:mullusi:schema:reflex-deployment-witness-validator-receipt:1"
    assert receipt_entry["surface"] == "deployment"


def test_protocol_manifest_indexes_production_evidence_endpoint_contracts() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    health_entry = entries["gateway-health"]
    production_entry = entries["production-evidence-witness"]
    capability_entry = entries["capability-evidence-endpoint"]
    audit_entry = entries["audit-verification-endpoint"]
    proof_entry = entries["proof-verification-endpoint"]

    assert validate_protocol_manifest(manifest) == []
    assert health_entry["path"] == "schemas/gateway_health.schema.json"
    assert health_entry["urn"] == "urn:mullusi:schema:gateway-health:1"
    assert health_entry["surface"] == "deployment"
    assert production_entry["path"] == "schemas/production_evidence_witness.schema.json"
    assert production_entry["urn"] == "urn:mullusi:schema:production-evidence-witness:1"
    assert production_entry["surface"] == "deployment"
    assert capability_entry["path"] == "schemas/capability_evidence_endpoint.schema.json"
    assert capability_entry["urn"] == "urn:mullusi:schema:capability-evidence-endpoint:1"
    assert capability_entry["surface"] == "capability"
    assert audit_entry["path"] == "schemas/audit_verification_endpoint.schema.json"
    assert audit_entry["urn"] == "urn:mullusi:schema:audit-verification-endpoint:1"
    assert audit_entry["surface"] == "audit"
    assert proof_entry["path"] == "schemas/proof_verification_endpoint.schema.json"
    assert proof_entry["urn"] == "urn:mullusi:schema:proof-verification-endpoint:1"
    assert proof_entry["surface"] == "proof"


def test_protocol_manifest_indexes_runtime_witness_and_latest_anchor() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    witness_entry = entries["runtime-witness"]
    anchor_entry = entries["latest-anchor-read-model"]

    assert validate_protocol_manifest(manifest) == []
    assert witness_entry["path"] == "schemas/runtime_witness.schema.json"
    assert witness_entry["urn"] == "urn:mullusi:schema:runtime-witness:1"
    assert witness_entry["surface"] == "runtime"
    assert anchor_entry["path"] == "schemas/latest_anchor_read_model.schema.json"
    assert anchor_entry["urn"] == "urn:mullusi:schema:latest-anchor-read-model:1"
    assert anchor_entry["surface"] == "audit"


def test_protocol_manifest_indexes_finance_approval_packet_proof() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}

    assert entries["finance-approval-packet-proof"]["path"] == "schemas/finance_approval_packet_proof.schema.json"
    assert entries["finance-approval-packet-proof"]["urn"] == "urn:mullusi:schema:finance-approval-packet-proof:1"
    assert entries["finance-approval-packet-proof"]["surface"] == "finance"
    assert entries["finance-approval-live-handoff-plan"]["path"] == (
        "schemas/finance_approval_live_handoff_plan.schema.json"
    )
    assert entries["finance-approval-live-handoff-plan"]["urn"] == (
        "urn:mullusi:schema:finance-approval-live-handoff-plan:1"
    )
    assert entries["finance-approval-live-handoff-plan"]["surface"] == "finance"
    assert entries["finance-approval-live-handoff-closure-run"]["path"] == (
        "schemas/finance_approval_live_handoff_closure_run.schema.json"
    )
    assert entries["finance-approval-live-handoff-closure-run"]["urn"] == (
        "urn:mullusi:schema:finance-approval-live-handoff-closure-run:1"
    )
    assert entries["finance-approval-live-handoff-closure-run"]["surface"] == "finance"

    assert entries["finance-approval-live-handoff-chain-validation"]["path"] == (
        "schemas/finance_approval_live_handoff_chain_validation.schema.json"
    )
    assert entries["finance-approval-live-handoff-chain-validation"]["urn"] == (
        "urn:mullusi:schema:finance-approval-live-handoff-chain-validation:1"
    )
    assert entries["finance-approval-live-handoff-chain-validation"]["surface"] == "finance"
    assert entries["finance-approval-live-handoff-preflight"]["path"] == (
        "schemas/finance_approval_live_handoff_preflight.schema.json"
    )
    assert entries["finance-approval-live-handoff-preflight"]["urn"] == (
        "urn:mullusi:schema:finance-approval-live-handoff-preflight:1"
    )
    assert entries["finance-approval-live-handoff-preflight"]["surface"] == "finance"
    assert entries["finance-approval-email-calendar-binding-receipt"]["path"] == (
        "schemas/finance_approval_email_calendar_binding_receipt.schema.json"
    )
    assert entries["finance-approval-email-calendar-binding-receipt"]["urn"] == (
        "urn:mullusi:schema:finance-approval-email-calendar-binding-receipt:1"
    )
    assert entries["finance-approval-email-calendar-binding-receipt"]["surface"] == "finance"
    assert entries["finance-approval-email-calendar-operator-input-request"]["path"] == (
        "schemas/finance_approval_email_calendar_operator_input_request.schema.json"
    )
    assert entries["finance-approval-email-calendar-operator-input-request"]["urn"] == (
        "urn:mullusi:schema:finance-approval-email-calendar-operator-input-request:1"
    )
    assert entries["finance-approval-email-calendar-operator-input-request"]["surface"] == "finance"
    assert entries["finance-approval-payment-provider-binding-receipt"]["path"] == (
        "schemas/finance_approval_payment_provider_binding_receipt.schema.json"
    )
    assert entries["finance-approval-payment-provider-binding-receipt"]["urn"] == (
        "urn:mullusi:schema:finance-approval-payment-provider-binding-receipt:1"
    )
    assert entries["finance-approval-payment-provider-binding-receipt"]["surface"] == "finance"
    assert entries["finance-approval-email-calendar-live-receipt"]["path"] == (
        "schemas/finance_approval_email_calendar_live_receipt.schema.json"
    )
    assert entries["finance-approval-email-calendar-live-receipt"]["urn"] == (
        "urn:mullusi:schema:finance-approval-email-calendar-live-receipt:1"
    )
    assert entries["finance-approval-email-calendar-live-receipt"]["surface"] == "finance"
    assert entries["finance-approval-payment-closure-receipt"]["path"] == (
        "schemas/finance_approval_payment_closure_receipt.schema.json"
    )
    assert entries["finance-approval-payment-closure-receipt"]["urn"] == (
        "urn:mullusi:schema:finance-approval-payment-closure-receipt:1"
    )
    assert entries["finance-approval-payment-closure-receipt"]["surface"] == "finance"
    assert entries["finance-approval-handoff-packet"]["path"] == "schemas/finance_approval_handoff_packet.schema.json"
    assert entries["finance-approval-handoff-packet"]["urn"] == (
        "urn:mullusi:schema:finance-approval-handoff-packet:1"
    )
    assert entries["finance-approval-handoff-packet"]["surface"] == "finance"
    assert entries["finance-approval-operator-summary"]["path"] == (
        "schemas/finance_approval_operator_summary.schema.json"
    )
    assert entries["finance-approval-operator-summary"]["urn"] == (
        "urn:mullusi:schema:finance-approval-operator-summary:1"
    )
    assert entries["finance-approval-operator-summary"]["surface"] == "finance"
    assert validate_protocol_manifest(manifest) == []


def test_protocol_manifest_indexes_github_pr_terminal_decision_value_request() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    request_entry = entries[
        "agentic-service-harness-github-pr-terminal-closure-operator-decision-value-request"
    ]

    assert validate_protocol_manifest(manifest) == []
    assert request_entry["path"] == (
        "schemas/agentic_service_harness_github_pr_terminal_closure_operator_decision_value_request.schema.json"
    )
    assert request_entry["urn"] == (
        "urn:mullusi:schema:agentic-service-harness-github-pr-terminal-closure-operator-decision-value-request:1"
    )
    assert request_entry["surface"] == "runtime"


def test_protocol_manifest_indexes_personal_assistant_operator_reapproval_decision_receipt_intake() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    intake_entry = entries[
        "personal-assistant-operator-reapproval-decision-receipt-intake"
    ]

    assert validate_protocol_manifest(manifest) == []
    assert intake_entry["path"] == (
        "schemas/personal_assistant_operator_reapproval_decision_receipt_intake.schema.json"
    )
    assert intake_entry["urn"] == (
        "urn:mullusi:schema:personal-assistant-operator-reapproval-decision-receipt-intake:1"
    )
    assert intake_entry["surface"] == "approval"


def test_protocol_manifest_indexes_github_pr_terminal_decision_value_record() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    record_entry = entries[
        "agentic-service-harness-github-pr-terminal-closure-operator-decision-value-record"
    ]

    assert validate_protocol_manifest(manifest) == []
    assert record_entry["path"] == (
        "schemas/agentic_service_harness_github_pr_terminal_closure_operator_decision_value_record.schema.json"
    )
    assert record_entry["urn"] == (
        "urn:mullusi:schema:agentic-service-harness-github-pr-terminal-closure-operator-decision-value-record:1"
    )
    assert record_entry["surface"] == "runtime"


def test_protocol_manifest_indexes_github_pr_terminal_certificate_minting() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    minting_entry = entries[
        "agentic-service-harness-github-pr-terminal-closure-certificate-minting"
    ]

    assert validate_protocol_manifest(manifest) == []
    assert minting_entry["path"] == (
        "schemas/agentic_service_harness_github_pr_terminal_closure_certificate_minting.schema.json"
    )
    assert minting_entry["urn"] == (
        "urn:mullusi:schema:agentic-service-harness-github-pr-terminal-closure-certificate-minting:1"
    )
    assert minting_entry["surface"] == "runtime"


def test_protocol_manifest_indexes_personal_assistant_operator_reapproval_decision_receipt_value_request() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    value_request_entry = entries[
        "personal-assistant-operator-reapproval-decision-receipt-value-request"
    ]

    assert validate_protocol_manifest(manifest) == []
    assert value_request_entry["path"] == (
        "schemas/personal_assistant_operator_reapproval_decision_receipt_value_request.schema.json"
    )
    assert value_request_entry["urn"] == (
        "urn:mullusi:schema:personal-assistant-operator-reapproval-decision-receipt-value-request:1"
    )
    assert value_request_entry["surface"] == "approval"


def test_protocol_manifest_indexes_personal_assistant_operator_reapproval_decision_receipt_value_absence() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    value_absence_entry = entries[
        "personal-assistant-operator-reapproval-decision-receipt-value-absence"
    ]

    assert validate_protocol_manifest(manifest) == []
    assert value_absence_entry["path"] == (
        "schemas/personal_assistant_operator_reapproval_decision_receipt_value_absence.schema.json"
    )
    assert value_absence_entry["urn"] == (
        "urn:mullusi:schema:personal-assistant-operator-reapproval-decision-receipt-value-absence:1"
    )
    assert value_absence_entry["surface"] == "approval"

def test_protocol_manifest_indexes_personal_assistant_operator_reapproval_decision_receipt_value_template() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    value_template_entry = entries[
        "personal-assistant-operator-reapproval-decision-receipt-value-template"
    ]

    assert validate_protocol_manifest(manifest) == []
    assert value_template_entry["path"] == (
        "schemas/personal_assistant_operator_reapproval_decision_receipt_value_template.schema.json"
    )
    assert value_template_entry["urn"] == (
        "urn:mullusi:schema:personal-assistant-operator-reapproval-decision-receipt-value-template:1"
    )
    assert value_template_entry["surface"] == "approval"


def test_protocol_manifest_rejects_missing_deployment_receipt_entry() -> None:
    manifest = load_manifest()
    manifest["schemas"] = [
        entry
        for entry in manifest["schemas"]
        if entry["schema_id"] != "deployment-orchestration-receipt"
    ]

    errors = validate_protocol_manifest(manifest)

    assert len(errors) == 1
    assert "manifest missing public schemas" in errors[0]
    assert "deployment_orchestration_receipt.schema.json" in errors[0]
    assert "schemas/" in errors[0]


def test_protocol_manifest_rejects_missing_effect_assurance_entry() -> None:
    manifest = load_manifest()
    manifest["schemas"] = [
        entry
        for entry in manifest["schemas"]
        if entry["schema_id"] != "effect-assurance"
    ]

    errors = validate_protocol_manifest(manifest)

    assert len(errors) == 1
    assert "manifest missing public schemas" in errors[0]
    assert "effect_assurance.schema.json" in errors[0]
    assert "schemas/" in errors[0]


def test_protocol_manifest_rejects_missing_promotion_closure_plan_entry() -> None:
    manifest = load_manifest()
    manifest["schemas"] = [
        entry
        for entry in manifest["schemas"]
        if entry["schema_id"] != "general-agent-promotion-closure-plan"
    ]

    errors = validate_protocol_manifest(manifest)

    assert len(errors) == 1
    assert "manifest missing public schemas" in errors[0]
    assert "general_agent_promotion_closure_plan.schema.json" in errors[0]
    assert "schemas/" in errors[0]


def test_protocol_manifest_rejects_missing_capability_adapter_closure_plan_entry() -> None:
    manifest = load_manifest()
    manifest["schemas"] = [
        entry
        for entry in manifest["schemas"]
        if entry["schema_id"] != "capability-adapter-closure-plan"
    ]

    errors = validate_protocol_manifest(manifest)

    assert len(errors) == 1
    assert "manifest missing public schemas" in errors[0]
    assert "capability_adapter_closure_plan.schema.json" in errors[0]
    assert "schemas/" in errors[0]


def test_protocol_manifest_rejects_missing_promotion_environment_bindings_entry() -> None:
    manifest = load_manifest()
    manifest["schemas"] = [
        entry
        for entry in manifest["schemas"]
        if entry["schema_id"] != "general-agent-promotion-environment-bindings"
    ]

    errors = validate_protocol_manifest(manifest)

    assert len(errors) == 1
    assert "manifest missing public schemas" in errors[0]
    assert "general_agent_promotion_environment_bindings.schema.json" in errors[0]
    assert "schemas/" in errors[0]


def test_protocol_manifest_rejects_missing_promotion_environment_binding_receipt_entry() -> None:
    manifest = load_manifest()
    manifest["schemas"] = [
        entry
        for entry in manifest["schemas"]
        if entry["schema_id"] != "general-agent-promotion-environment-binding-receipt"
    ]

    errors = validate_protocol_manifest(manifest)

    assert len(errors) == 1
    assert "manifest missing public schemas" in errors[0]
    assert "general_agent_promotion_environment_binding_receipt.schema.json" in errors[0]
    assert "schemas/" in errors[0]


def test_protocol_manifest_rejects_missing_promotion_live_evidence_queue_entry() -> None:
    manifest = load_manifest()
    manifest["schemas"] = [
        entry
        for entry in manifest["schemas"]
        if entry["schema_id"] != "general-agent-promotion-live-evidence-queue"
    ]

    errors = validate_protocol_manifest(manifest)

    assert len(errors) == 1
    assert "manifest missing public schemas" in errors[0]
    assert "general_agent_promotion_live_evidence_queue.schema.json" in errors[0]
    assert "schemas/" in errors[0]


def test_protocol_manifest_rejects_missing_promotion_live_evidence_operator_input_request_entry() -> None:
    manifest = load_manifest()
    manifest["schemas"] = [
        entry
        for entry in manifest["schemas"]
        if entry["schema_id"] != "general-agent-promotion-live-evidence-operator-input-request"
    ]

    errors = validate_protocol_manifest(manifest)

    assert len(errors) == 1
    assert "manifest missing public schemas" in errors[0]
    assert "general_agent_promotion_live_evidence_operator_input_request.schema.json" in errors[0]
    assert "schemas/" in errors[0]


def test_protocol_manifest_rejects_missing_promotion_terminal_certificate_gate_entry() -> None:
    manifest = load_manifest()
    manifest["schemas"] = [
        entry
        for entry in manifest["schemas"]
        if entry["schema_id"] != "general-agent-promotion-terminal-certificate-gate"
    ]

    errors = validate_protocol_manifest(manifest)

    assert len(errors) == 1
    assert "manifest missing public schemas" in errors[0]
    assert "general_agent_promotion_terminal_certificate_gate.schema.json" in errors[0]
    assert "schemas/" in errors[0]


def test_protocol_manifest_rejects_missing_promotion_terminal_approvals_entry() -> None:
    manifest = load_manifest()
    manifest["schemas"] = [
        entry
        for entry in manifest["schemas"]
        if entry["schema_id"] != "general-agent-promotion-terminal-approvals"
    ]

    errors = validate_protocol_manifest(manifest)

    assert len(errors) == 1
    assert "manifest missing public schemas" in errors[0]
    assert "general_agent_promotion_terminal_approvals.schema.json" in errors[0]
    assert "schemas/" in errors[0]


def test_protocol_manifest_rejects_missing_promotion_terminal_certificate_candidates_entry() -> None:
    manifest = load_manifest()
    manifest["schemas"] = [
        entry
        for entry in manifest["schemas"]
        if entry["schema_id"] != "general-agent-promotion-terminal-certificate-candidates"
    ]

    errors = validate_protocol_manifest(manifest)

    assert len(errors) == 1
    assert "manifest missing public schemas" in errors[0]
    assert "general_agent_promotion_terminal_certificate_candidates.schema.json" in errors[0]
    assert "schemas/" in errors[0]


def test_protocol_manifest_rejects_missing_promotion_terminal_evidence_reconciliation_entry() -> None:
    manifest = load_manifest()
    manifest["schemas"] = [
        entry
        for entry in manifest["schemas"]
        if entry["schema_id"] != "general-agent-promotion-terminal-evidence-reconciliation"
    ]

    errors = validate_protocol_manifest(manifest)

    assert len(errors) == 1
    assert "manifest missing public schemas" in errors[0]
    assert "general_agent_promotion_terminal_evidence_reconciliation.schema.json" in errors[0]
    assert "schemas/" in errors[0]


def test_protocol_manifest_rejects_missing_promotion_terminal_minting_gate_entry() -> None:
    manifest = load_manifest()
    manifest["schemas"] = [
        entry
        for entry in manifest["schemas"]
        if entry["schema_id"] != "general-agent-promotion-terminal-minting-gate"
    ]

    errors = validate_protocol_manifest(manifest)

    assert len(errors) == 1
    assert "manifest missing public schemas" in errors[0]
    assert "general_agent_promotion_terminal_minting_gate.schema.json" in errors[0]
    assert "schemas/" in errors[0]


def test_protocol_manifest_rejects_missing_promotion_terminal_certificate_minting_run_entry() -> None:
    manifest = load_manifest()
    manifest["schemas"] = [
        entry
        for entry in manifest["schemas"]
        if entry["schema_id"] != "general-agent-promotion-terminal-certificate-minting-run"
    ]

    errors = validate_protocol_manifest(manifest)

    assert len(errors) == 1
    assert "manifest missing public schemas" in errors[0]
    assert "general_agent_promotion_terminal_certificate_minting_run.schema.json" in errors[0]
    assert "schemas/" in errors[0]


def test_protocol_manifest_rejects_missing_promotion_handoff_packet_entry() -> None:
    manifest = load_manifest()
    manifest["schemas"] = [
        entry
        for entry in manifest["schemas"]
        if entry["schema_id"] != "general-agent-promotion-handoff-packet"
    ]

    errors = validate_protocol_manifest(manifest)

    assert len(errors) == 1
    assert "manifest missing public schemas" in errors[0]
    assert "general_agent_promotion_handoff_packet.schema.json" in errors[0]
    assert "schemas/" in errors[0]


def test_protocol_manifest_rejects_missing_terminal_closure_certificate_entry() -> None:
    manifest = load_manifest()
    manifest["schemas"] = [
        entry
        for entry in manifest["schemas"]
        if entry["schema_id"] != "terminal-closure-certificate"
    ]

    errors = validate_protocol_manifest(manifest)

    assert len(errors) == 1
    assert "manifest missing public schemas" in errors[0]
    assert "terminal_closure_certificate.schema.json" in errors[0]
    assert "schemas/" in errors[0]


def test_protocol_manifest_rejects_missing_finance_live_receipt_entry() -> None:
    manifest = load_manifest()
    manifest["schemas"] = [
        entry
        for entry in manifest["schemas"]
        if entry["schema_id"] != "finance-approval-email-calendar-live-receipt"
    ]

    errors = validate_protocol_manifest(manifest)

    assert len(errors) == 1
    assert "manifest missing public schemas" in errors[0]
    assert "finance_approval_email_calendar_live_receipt.schema.json" in errors[0]
    assert "schemas/" in errors[0]


def test_protocol_manifest_rejects_missing_finance_operator_summary_entry() -> None:
    manifest = load_manifest()
    manifest["schemas"] = [
        entry
        for entry in manifest["schemas"]
        if entry["schema_id"] != "finance-approval-operator-summary"
    ]

    errors = validate_protocol_manifest(manifest)

    assert len(errors) == 1
    assert "manifest missing public schemas" in errors[0]
    assert "finance_approval_operator_summary.schema.json" in errors[0]
    assert "schemas/" in errors[0]


def test_protocol_manifest_reports_malformed_public_schema(monkeypatch, tmp_path) -> None:
    schema_dir = tmp_path / "schemas"
    schema_dir.mkdir()
    (schema_dir / "malformed.schema.json").write_text("{not-json", encoding="utf-8")
    manifest = {
        "protocol_id": "mullu-governance-protocol",
        "protocol_uri_scheme": "mgp://",
        "claim_boundary": {
            "open_surface": "schemas_and_wire_contracts",
            "closed_surface": "runtime_implementation",
            "third_party_implementation_allowed": True,
        },
        "compatibility": {
            "json_schema_draft": "2020-12",
            "runtime_private_modules_are_not_protocol_contracts": True,
        },
        "schemas": [
            {
                "schema_id": "malformed",
                "path": "schemas/malformed.schema.json",
                "urn": "urn:mullusi:schema:malformed:1",
                "surface": "test",
            }
        ],
        "non_contract_paths": [
            "mcoi/mcoi_runtime/core",
            "mcoi/mcoi_runtime/app",
            "gateway",
            "scripts",
        ],
        "uri_schemes": [
            {"scheme": "lineage://"},
            {"scheme": "proof://"},
            {"scheme": "mgp://"},
        ],
    }

    monkeypatch.setattr(protocol_manifest, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(protocol_manifest, "SCHEMA_DIR", schema_dir)

    errors = validate_protocol_manifest(manifest)

    assert len(errors) == 1
    assert errors[0] == "schemas/malformed.schema.json: invalid JSON schema"
    assert "Traceback" not in errors[0]


def test_protocol_manifest_indexes_universal_symbol_receipt_store_durability_replay_witness() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    witness_entry = entries["universal-symbol-receipt-store-durability-replay-witness"]

    assert validate_protocol_manifest(manifest) == []
    assert witness_entry["path"] == "schemas/universal_symbol_receipt_store_durability_replay_witness.schema.json"
    assert witness_entry["urn"] == (
        "urn:mullusi:schema:universal-symbol-receipt-store-durability-replay-witness:1"
    )
    assert witness_entry["surface"] == "symbol"


def test_protocol_manifest_indexes_universal_symbol_receipt_store_replacement_decision_replay_idempotency_witness() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    witness_entry = entries[
        "universal-symbol-receipt-store-replacement-decision-replay-idempotency-witness"
    ]

    assert validate_protocol_manifest(manifest) == []
    assert witness_entry["path"] == (
        "schemas/universal_symbol_receipt_store_replacement_decision_replay_idempotency_witness.schema.json"
    )
    assert witness_entry["urn"] == (
        "urn:mullusi:schema:universal-symbol-receipt-store-replacement-decision-replay-idempotency-witness:1"
    )
    assert witness_entry["surface"] == "symbol"


def test_protocol_manifest_indexes_universal_symbol_runtime_authority_witness() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    witness_entry = entries["universal-symbol-runtime-authority-witness"]

    assert validate_protocol_manifest(manifest) == []
    assert witness_entry["path"] == "schemas/universal_symbol_runtime_authority_witness.schema.json"
    assert witness_entry["urn"] == "urn:mullusi:schema:universal-symbol-runtime-authority-witness:1"
    assert witness_entry["surface"] == "symbol"
