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
    REPO_ROOT,
    discover_declared_routes,
    route_coverage_report,
    proof_coverage_matrix,
    validate_matrix_routes,
)


def _load_fixture() -> dict:
    return json.loads(CANONICAL_OUTPUT.read_text(encoding="utf-8"))


def test_fixture_contract_is_canonical() -> None:
    matrix = _load_fixture()

    assert matrix == proof_coverage_matrix()
    assert matrix["schema_version"] == 1
    assert matrix["generated_by"] == "scripts/proof_coverage_matrix.py"
    assert len(matrix["surfaces"]) >= 3


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
    assert any(
        record["surface_id"] == "unclassified_declared_route"
        and record["coverage_state"] == "unproven"
        for record in report["routes"]
    )


def test_representative_routes_are_not_unclassified() -> None:
    matrix = _load_fixture()
    classified_routes = {
        record["route"]: record
        for record in matrix["route_coverage"]["routes"]
    }

    assert classified_routes["/api/v1/lineage/resolve"]["surface_id"] == "lineage_query_api"
    assert classified_routes["/api/v1/stream"]["surface_id"] == "llm_streaming"
    assert classified_routes["/webhook/web"]["surface_id"] == "gateway_webhook_ingress"
    assert classified_routes["/api/v1/data-governance/evaluate"]["surface_id"] == "data_governance_controls"
    assert classified_routes["/api/v1/compliance/audit-package"]["surface_id"] == "compliance_evidence_exports"
    assert classified_routes["/api/v1/runbooks/analyze"]["surface_id"] == "runbook_learning_lifecycle"
    assert classified_routes["/api/v1/runbooks/{runbook_id}/activate"]["surface_id"] == "runbook_learning_lifecycle"
    assert classified_routes["/authority/operator"]["surface_id"] == "authority_operator_controls"
    assert classified_routes["/authority/ownership"]["surface_id"] == "authority_operator_controls"
    assert classified_routes["/api/v1/temporal/schedules"]["surface_id"] == "temporal_kernel"
    assert classified_routes["/api/v1/temporal/worker/tick"]["surface_id"] == "temporal_kernel"
    assert classified_routes["/api/v1/finance/approval-packets"]["surface_id"] == "finance_approval_packets"
    assert (
        classified_routes["/api/v1/finance/approval-packets/operator/read-model"]["surface_id"]
        == "finance_approval_packets"
    )
    assert (
        classified_routes["/api/v1/finance/approval-packets/{case_id}/proof"]["surface_id"]
        == "finance_approval_packets"
    )
    assert classified_routes["/api/v1/agent/register"]["coverage_state"] == "unproven"


def test_finance_approval_packet_surface_is_witnessed() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    finance_surface = surfaces["finance_approval_packets"]
    witnesses = set(finance_surface["runtime_witnesses"])

    assert finance_surface["coverage_state"] == "witnessed"
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
    assert "finance_packet_policy_reasons_explicit" in witnesses
    assert "blocked_packet_emits_no_effect" in witnesses
    assert "approval_action_binds_approval_effect_and_closure_refs" in witnesses
    assert "packet_proof_requires_policy_evidence_and_closure_for_closed_states" in witnesses
    assert "operator_read_model_bounds_visible_packets_and_counts" in witnesses
    assert closure_actions["classify_finance_approval_packet_routes"]["status"] == "closed"


def test_gateway_runtime_witnesses_bind_closure_invariants() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    gateway_surface = surfaces["gateway_capability_fabric"]
    witnesses = set(gateway_surface["runtime_witnesses"])

    assert gateway_surface["action_proof"] == "action_proof"
    assert "/commands/{command_id}/closure" in gateway_surface["representative_paths"]
    assert "DomainCapsuleCompiler.compile" in gateway_surface["representative_paths"]
    assert "install_certified_capsule_with_handoff_evidence" in gateway_surface["representative_paths"]
    assert "gateway/capability_capsule_installer.py" in gateway_surface["evidence_files"]
    assert "mcoi/mcoi_runtime/core/domain_capsule_compiler.py" in gateway_surface["evidence_files"]
    assert "tests/test_gateway/test_capability_capsule_installer.py" in gateway_surface["evidence_files"]
    assert "tests/test_governed_capability_fabric.py" in gateway_surface["evidence_files"]
    assert "command_lifecycle_events_are_hash_linked" in witnesses
    assert "terminal_closure_requires_evidence_refs" in witnesses
    assert "successful_response_is_bound_to_response_evidence_closure" in witnesses
    assert "capsule_compiler_emits_certification_evidence_manifest" in witnesses
    assert "capsule_installer_stamps_admission_receipt" in witnesses


def test_data_governance_controls_surface_is_witnessed() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    data_surface = surfaces["data_governance_controls"]
    witnesses = set(data_surface["runtime_witnesses"])

    assert data_surface["coverage_state"] == "witnessed"
    assert data_surface["request_proof"] == "request_proof"
    assert data_surface["action_proof"] == "action_proof"
    assert "/api/v1/data-governance/classify" in data_surface["representative_paths"]
    assert "/api/v1/data-governance/evaluate" in data_surface["representative_paths"]
    assert "mcoi/mcoi_runtime/app/routers/data.py" in data_surface["evidence_files"]
    assert "mcoi/mcoi_runtime/core/data_governance.py" in data_surface["evidence_files"]
    assert "mcoi/tests/test_data_governance_endpoints.py" in data_surface["evidence_files"]
    assert "data_governance_state_hash" in witnesses
    assert "data_governance_action_proof" in witnesses
    assert "tenant_visible_violation_read_model" in witnesses
    assert closure_actions["classify_data_governance_routes"]["status"] == "closed"


def test_compliance_evidence_exports_surface_is_witnessed() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    compliance_surface = surfaces["compliance_evidence_exports"]
    witnesses = set(compliance_surface["runtime_witnesses"])

    assert compliance_surface["coverage_state"] == "witnessed"
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


def test_runbook_learning_lifecycle_surface_is_witnessed() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    runbook_surface = surfaces["runbook_learning_lifecycle"]
    witnesses = set(runbook_surface["runtime_witnesses"])

    assert runbook_surface["coverage_state"] == "witnessed"
    assert runbook_surface["request_proof"] == "request_proof"
    assert runbook_surface["action_proof"] == "action_proof"
    assert "/api/v1/runbooks" in runbook_surface["representative_paths"]
    assert "/api/v1/runbooks/analyze" in runbook_surface["representative_paths"]
    assert "/api/v1/runbooks/promote" in runbook_surface["representative_paths"]
    assert "/api/v1/runbooks/approve" in runbook_surface["representative_paths"]
    assert "/api/v1/runbooks/{runbook_id}/activate" in runbook_surface["representative_paths"]
    assert "/api/v1/runbooks/{runbook_id}/retire" in runbook_surface["representative_paths"]
    assert "mcoi/mcoi_runtime/app/routers/runbooks.py" in runbook_surface["evidence_files"]
    assert "mcoi/mcoi_runtime/core/runbook_learning.py" in runbook_surface["evidence_files"]
    assert "mcoi/tests/test_runbook_learning.py" in runbook_surface["evidence_files"]
    assert "patterns_detected_from_audit_trail" in witnesses
    assert "promotion_requires_detected_pattern" in witnesses
    assert "approval_required_before_activation" in witnesses
    assert "retirement_requires_active_runbook" in witnesses
    assert "promote_and_approve_audit_records" in witnesses
    assert "sanitized_runbook_error_details" in witnesses
    assert "runbook_pattern_read_models_bounded" in witnesses
    assert "runbook_responses_governed" in witnesses
    assert closure_actions["classify_runbook_learning_routes"]["status"] == "closed"


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
    assert "mcoi/mcoi_runtime/app/routers/audit.py" in audit_surface["evidence_files"]
    assert "mcoi/mcoi_runtime/governance/audit/trail.py" in audit_surface["evidence_files"]
    assert "mcoi/mcoi_runtime/governance/audit/anchor.py" in audit_surface["evidence_files"]
    assert "mcoi/tests/test_audit_trail.py" in audit_surface["evidence_files"]
    assert "mcoi/tests/test_v4_28_audit_checkpoint.py" in audit_surface["evidence_files"]
    assert "audit_chain_verify_endpoint" in witnesses
    assert "audit_anchor_checkpoint_created" in witnesses
    assert "audit_anchor_verification_endpoint" in witnesses
    assert closure_actions["classify_audit_chain_api"]["status"] == "closed"


def test_gateway_runtime_witness_covers_orchestration_receipts() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    runtime_surface = surfaces["gateway_runtime_witness"]

    assert runtime_surface["coverage_state"] == "witnessed"
    assert "scripts/orchestrate_deployment_witness.py" in runtime_surface["evidence_files"]
    assert ".github/workflows/gateway-publication.yml" in runtime_surface["evidence_files"]
    assert "schemas/deployment_orchestration_receipt.schema.json" in runtime_surface["evidence_files"]
    assert "schemas/deployment_publication_closure_validation.schema.json" in runtime_surface["evidence_files"]
    assert "schemas/deployment_orchestration_receipt_validation.schema.json" in runtime_surface["evidence_files"]
    assert "schemas/gateway_publication_readiness.schema.json" in runtime_surface["evidence_files"]
    assert "schemas/gateway_publication_receipt_validation.schema.json" in runtime_surface["evidence_files"]
    assert "schemas/mullu_governance_protocol.manifest.json" in runtime_surface["evidence_files"]
    assert "tests/test_orchestrate_deployment_witness.py" in runtime_surface["evidence_files"]
    assert "tests/test_report_gateway_publication_readiness.py" in runtime_surface["evidence_files"]
    assert "tests/test_validate_gateway_publication_receipt.py" in runtime_surface["evidence_files"]
    assert "tests/test_validate_deployment_publication_closure.py" in runtime_surface["evidence_files"]
    assert "tests/test_validate_protocol_manifest.py" in runtime_surface["evidence_files"]
    assert "deployment_witness_orchestration_receipt" in runtime_surface["runtime_witnesses"]
    assert "deployment_publication_closure_validation_schema" in runtime_surface["runtime_witnesses"]
    assert "deployment_orchestration_validation_schema" in runtime_surface["runtime_witnesses"]
    assert "gateway_publication_readiness_schema" in runtime_surface["runtime_witnesses"]
    assert "gateway_publication_receipt_validation_schema" in runtime_surface["runtime_witnesses"]
    assert closure_actions["publish_deployment_orchestration_receipt_contract"]["status"] == "closed"


def test_gateway_runtime_witness_covers_publication_responsibility_debt() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    runtime_surface = surfaces["gateway_runtime_witness"]
    witnesses = set(runtime_surface["runtime_witnesses"])

    assert "schemas/deployment_witness.schema.json" in runtime_surface["evidence_files"]
    assert "scripts/validate_deployment_publication_closure.py" in runtime_surface["evidence_files"]
    assert "tests/test_validate_deployment_publication_closure.py" in runtime_surface["evidence_files"]
    assert "responsibility_debt_clear" in witnesses
    assert "runtime_responsibility_debt_clear" in witnesses
    assert "authority_responsibility_debt_clear" in witnesses
    assert "authority_overdue_approval_chain_count" in witnesses
    assert "authority_overdue_obligation_count" in witnesses
    assert "authority_escalated_obligation_count" in witnesses
    assert "authority_unowned_high_risk_capability_count" in witnesses


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
    assert "/deployment/witness" in evidence_surface["representative_paths"]
    assert "/capabilities/evidence" in evidence_surface["representative_paths"]
    assert "/audit/verify" in evidence_surface["representative_paths"]
    assert "/proof/verify" in evidence_surface["representative_paths"]
    assert "schemas/production_evidence_witness.schema.json" in evidence_surface["evidence_files"]
    assert "schemas/capability_evidence_endpoint.schema.json" in evidence_surface["evidence_files"]
    assert "schemas/audit_verification_endpoint.schema.json" in evidence_surface["evidence_files"]
    assert "schemas/proof_verification_endpoint.schema.json" in evidence_surface["evidence_files"]
    assert "tests/test_gateway/test_production_evidence.py" in evidence_surface["evidence_files"]
    assert "tests/test_collect_deployment_witness.py" in evidence_surface["evidence_files"]
    assert "signed_production_evidence_witness" in witnesses
    assert "capability_evidence_schema_valid" in witnesses
    assert "audit_verification_schema_valid" in witnesses
    assert "proof_verification_schema_valid" in witnesses
    assert "deployment_collection_requires_production_evidence" in witnesses
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


def test_lineage_query_api_is_witnessed_read_model() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    lineage_surface = surfaces["lineage_query_api"]
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}

    assert lineage_surface["coverage_state"] == "witnessed"
    assert lineage_surface["request_proof"] == "read_model"
    assert lineage_surface["action_proof"] == "read_model"
    assert "/api/v1/lineage/command/{command_id}" in lineage_surface["representative_paths"]
    assert "mcoi/mcoi_runtime/core/lineage_query.py" in lineage_surface["evidence_files"]
    assert "schemas/lineage_query.schema.json" in lineage_surface["evidence_files"]
    assert "docs/42_lineage_query_api.md" in lineage_surface["evidence_files"]
    assert closure_actions["implement_lineage_query_routes_and_schema"]["status"] == "closed"


def test_capability_plan_evidence_bundle_surface_is_witnessed() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    plan_surface = surfaces["capability_plan_evidence_bundle"]
    conformance_surface = surfaces["runtime_conformance_attestation"]
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}

    assert plan_surface["coverage_state"] == "witnessed"
    assert plan_surface["request_proof"] == "request_proof"
    assert plan_surface["action_proof"] == "action_proof"
    assert "/capability-plans/{plan_id}/closure" in plan_surface["representative_paths"]
    assert "gateway/plan_ledger.py" in plan_surface["evidence_files"]
    assert "tests/test_gateway/test_plan.py" in plan_surface["evidence_files"]
    assert "plan_evidence_bundle" in plan_surface["runtime_witnesses"]
    assert "capability_plan_bundle_canary_passed" in conformance_surface["runtime_witnesses"]
    assert "physical_worker_canary_passed" in conformance_surface["runtime_witnesses"]
    assert "physical_worker_canary_artifact_hash_bound" in conformance_surface["runtime_witnesses"]
    assert "gateway/physical_worker_canary.py" in conformance_surface["evidence_files"]
    assert "scripts/produce_physical_worker_canary.py" in conformance_surface["evidence_files"]
    assert "runtime_conformance_certificate_schema_valid" in conformance_surface["runtime_witnesses"]
    assert "runtime_conformance_collector_schema_valid" in conformance_surface["runtime_witnesses"]
    assert "proof_coverage_unclassified_routes_reported" in conformance_surface["runtime_witnesses"]
    assert closure_actions["publish_capability_plan_evidence_bundles"]["status"] == "closed"
    assert "runtime_conformance_attestation" in closure_actions["publish_capability_plan_evidence_bundles"]["surfaces"]


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
    assert "gateway/world_state.py" in operational_surface["evidence_files"]
    assert "gateway/goal_compiler.py" in operational_surface["evidence_files"]
    assert "gateway/causal_simulator.py" in operational_surface["evidence_files"]
    assert "schemas/world_state.schema.json" in operational_surface["evidence_files"]
    assert "schemas/goal.schema.json" in operational_surface["evidence_files"]
    assert "schemas/simulation_receipt.schema.json" in operational_surface["evidence_files"]
    assert "tests/test_gateway/test_world_state.py" in operational_surface["evidence_files"]
    assert "tests/test_gateway/test_goal_compiler.py" in operational_surface["evidence_files"]
    assert "tests/test_gateway/test_causal_simulator.py" in operational_surface["evidence_files"]
    assert "world_assertions_require_source_evidence" in witnesses
    assert "goal_plan_certificate_hash_bound" in witnesses
    assert "simulation_receipt_schema_valid" in witnesses
    assert "open_world_contradictions_block_execution" in witnesses
    assert "high_risk_controls_projected_before_execution" in witnesses
    assert closure_actions["publish_governed_operational_intelligence_witnesses"]["status"] == "closed"


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
    assert "gateway/physical_action_boundary.py" in worker_surface["evidence_files"]
    assert "gateway/physical_worker_canary.py" in worker_surface["evidence_files"]
    assert "gateway/worker_mesh.py" in worker_surface["evidence_files"]
    assert "scripts/produce_physical_worker_canary.py" in worker_surface["evidence_files"]
    assert "schemas/physical_action_receipt.schema.json" in worker_surface["evidence_files"]
    assert "schemas/worker_mesh.schema.json" in worker_surface["evidence_files"]
    assert "tests/test_gateway/test_physical_action_boundary.py" in worker_surface["evidence_files"]
    assert "tests/test_gateway/test_physical_worker_canary.py" in worker_surface["evidence_files"]
    assert "tests/test_gateway/test_worker_mesh.py" in worker_surface["evidence_files"]
    assert "tests/test_produce_physical_worker_canary.py" in worker_surface["evidence_files"]
    assert "active_lease_required" in witnesses
    assert "tenant_capability_operation_budget_checked" in witnesses
    assert "forbidden_operations_override_allowed" in witnesses
    assert "physical_action_receipt_required_for_physical_workers" in witnesses
    assert "physical_worker_canary_blocks_without_receipt" in witnesses
    assert "physical_worker_canary_passed" in witnesses
    assert "physical_worker_canary_uses_sandbox_handler" in witnesses
    assert "worker_evidence_refs_required" in witnesses
    assert "worker_receipt_not_terminal_closure" in witnesses
    assert "worker_mesh_schema_valid" in witnesses
    assert closure_actions["publish_networked_worker_mesh_contract"]["status"] == "closed"


def test_agent_identity_surface_binds_owner_tenant_and_scope() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    identity_surface = surfaces["agent_identity"]
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
    assert closure_actions["publish_agent_identity_contract"]["status"] == "closed"


def test_claim_verification_surface_gates_execution_admission() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    claim_surface = surfaces["claim_verification"]
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
    assert closure_actions["publish_claim_verification_report_contract"]["status"] == "closed"


def test_connector_self_healing_surface_emits_bounded_recovery_receipts() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    healing_surface = surfaces["connector_self_healing"]
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
    assert closure_actions["publish_connector_self_healing_receipt_contract"]["status"] == "closed"


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
    assert "autonomy_requires_c7" in witnesses
    assert closure_actions["publish_capability_maturity_contract"]["status"] == "closed"


def test_policy_prover_surface_reports_counterexamples() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    prover_surface = surfaces["policy_prover"]
    witnesses = set(prover_surface["runtime_witnesses"])

    assert prover_surface["coverage_state"] == "witnessed"
    assert prover_surface["request_proof"] == "request_proof"
    assert prover_surface["action_proof"] == "action_proof"
    assert "gateway/policy_prover.py" in prover_surface["evidence_files"]
    assert "schemas/policy_proof_report.schema.json" in prover_surface["evidence_files"]
    assert "tests/test_gateway/test_policy_prover.py" in prover_surface["evidence_files"]
    assert "payment_requires_approval_counterexample" in witnesses
    assert "shell_requires_sandbox_counterexample" in witnesses
    assert "unknown_property_fails_closed" in witnesses
    assert closure_actions["publish_policy_prover_counterexample_contract"]["status"] == "closed"


def test_memory_lattice_surface_gates_planning_and_execution() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    lattice_surface = surfaces["memory_lattice"]
    witnesses = set(lattice_surface["runtime_witnesses"])

    assert lattice_surface["coverage_state"] == "witnessed"
    assert lattice_surface["request_proof"] == "request_proof"
    assert lattice_surface["action_proof"] == "action_proof"
    assert "gateway/memory_lattice.py" in lattice_surface["evidence_files"]
    assert "schemas/memory_lattice.schema.json" in lattice_surface["evidence_files"]
    assert "tests/test_gateway/test_memory_lattice.py" in lattice_surface["evidence_files"]
    assert "raw_event_memory_not_directly_admitted" in witnesses
    assert "semantic_memory_requires_learning_admission" in witnesses
    assert "contradiction_and_stale_memory_block_execution" in witnesses
    assert closure_actions["publish_memory_lattice_admission_contract"]["status"] == "closed"


def test_workflow_mining_surface_emits_blocked_drafts() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    mining_surface = surfaces["workflow_mining"]
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
    assert closure_actions["publish_workflow_mining_draft_contract"]["status"] == "closed"


def test_trust_ledger_surface_signs_terminal_evidence_bundles() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    trust_surface = surfaces["trust_ledger"]
    witnesses = set(trust_surface["runtime_witnesses"])

    assert trust_surface["coverage_state"] == "witnessed"
    assert trust_surface["request_proof"] == "request_proof"
    assert trust_surface["action_proof"] == "action_proof"
    assert "gateway/trust_ledger.py" in trust_surface["evidence_files"]
    assert "schemas/trust_ledger_anchor_receipt.schema.json" in trust_surface["evidence_files"]
    assert "schemas/trust_ledger_bundle.schema.json" in trust_surface["evidence_files"]
    assert "tests/test_gateway/test_trust_ledger_anchor_receipt.py" in trust_surface["evidence_files"]
    assert "tests/test_gateway/test_trust_ledger.py" in trust_surface["evidence_files"]
    assert "terminal_certificate_id_required" in witnesses
    assert "bundle_hash_tamper_detection" in witnesses
    assert "hmac_signature_verification" in witnesses
    assert "typed_artifact_root_required" in witnesses
    assert "anchor_receipt_hmac_verification" in witnesses
    assert "anchor_receipt_schema_valid" in witnesses
    assert closure_actions["publish_trust_ledger_bundle_contract"]["status"] == "closed"
    assert closure_actions["publish_trust_ledger_anchor_receipt_contract"]["status"] == "closed"


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
    assert "high_risk_pack_requires_approval_roles" in witnesses
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
    assert "gateway/physical_action_boundary.py" in physical_surface["evidence_files"]
    assert "gateway/physical_worker_canary.py" in physical_surface["evidence_files"]
    assert "scripts/produce_physical_worker_canary.py" in physical_surface["evidence_files"]
    assert "schemas/physical_action_receipt.schema.json" in physical_surface["evidence_files"]
    assert "tests/test_gateway/test_physical_action_boundary.py" in physical_surface["evidence_files"]
    assert "tests/test_gateway/test_physical_worker_canary.py" in physical_surface["evidence_files"]
    assert "tests/test_produce_physical_worker_canary.py" in physical_surface["evidence_files"]
    assert "hardware_identity_required" in witnesses
    assert "emergency_stop_required" in witnesses
    assert "physical_dispatch_blocked_until_controls_complete" in witnesses
    assert "physical_worker_canary_uses_sandbox_handler" in witnesses
    assert "physical_worker_canary_artifact_hash_bound" in witnesses
    assert closure_actions["publish_physical_action_receipt_contract"]["status"] == "closed"


def test_temporal_kernel_surface_owns_runtime_time_truth() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    temporal_surface = surfaces["temporal_kernel"]
    witnesses = set(temporal_surface["runtime_witnesses"])

    assert temporal_surface["coverage_state"] == "witnessed"
    assert temporal_surface["request_proof"] == "request_proof"
    assert temporal_surface["action_proof"] == "action_proof"
    assert "/api/v1/temporal/schedules" in temporal_surface["representative_paths"]
    assert "/api/v1/temporal/schedules/{schedule_id}" in temporal_surface["representative_paths"]
    assert "/api/v1/temporal/schedules/{schedule_id}/cancel" in temporal_surface["representative_paths"]
    assert "/api/v1/temporal/worker/tick" in temporal_surface["representative_paths"]
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
    assert "schedule_read_models_persisted" in witnesses
    assert "worker_tick_certifies_proofs" in witnesses
    assert "cancel_emits_terminal_receipt" in witnesses
    assert "temporal_receipt_schema_valid" in witnesses
    assert closure_actions["publish_temporal_operation_receipt_contract"]["status"] == "closed"
    assert closure_actions["classify_temporal_scheduler_routes"]["status"] == "closed"


def test_temporal_evidence_freshness_surface_rechecks_required_evidence() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    evidence_surface = surfaces["temporal_evidence_freshness"]
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
    assert closure_actions["publish_temporal_evidence_freshness_receipt_contract"]["status"] == "closed"


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
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    refresh_surface = surfaces["temporal_memory_refresh"]
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
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    policy_surface = surfaces["policy_proof_report"]
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
    assert closure_actions["publish_policy_proof_report_contract"]["status"] == "closed"


def test_autonomous_capability_upgrade_surface_keeps_plans_activation_blocked() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    upgrade_surface = surfaces["autonomous_capability_upgrade"]
    witnesses = set(upgrade_surface["runtime_witnesses"])

    assert upgrade_surface["coverage_state"] == "witnessed"
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
    assert "plans_are_activation_blocked" in witnesses
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
        assert [surface["surface_id"] for surface in assurance["surfaces"]] == [
            surface["surface_id"] for surface in matrix["surfaces"]
        ]


def test_operator_document_mentions_every_surface() -> None:
    matrix = _load_fixture()
    doc = (REPO_ROOT / "docs" / "40_proof_coverage_matrix.md").read_text(encoding="utf-8")

    assert all(f"`{surface['surface_id']}`" in doc for surface in matrix["surfaces"])
    assert all(f"`{action['action_id']}`" in doc for action in matrix["closure_actions"])
    assert "schema contract validation" in doc
    assert "deployment orchestration receipt schema contract" in doc
