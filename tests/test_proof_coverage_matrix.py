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
    assert classified_routes["/api/v1/agent/register"]["coverage_state"] == "unproven"


def test_gateway_runtime_witnesses_bind_closure_invariants() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    gateway_surface = surfaces["gateway_capability_fabric"]
    witnesses = set(gateway_surface["runtime_witnesses"])

    assert gateway_surface["action_proof"] == "action_proof"
    assert "/commands/{command_id}/closure" in gateway_surface["representative_paths"]
    assert "command_lifecycle_events_are_hash_linked" in witnesses
    assert "terminal_closure_requires_evidence_refs" in witnesses
    assert "successful_response_is_bound_to_response_evidence_closure" in witnesses


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
    assert "runtime_conformance_certificate_schema_valid" in conformance_surface["runtime_witnesses"]
    assert "runtime_conformance_collector_schema_valid" in conformance_surface["runtime_witnesses"]
    assert "proof_coverage_declared_routes_classified" in conformance_surface["runtime_witnesses"]
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
    assert "gateway/capability_forge.py" in forge_surface["evidence_files"]
    assert "schemas/capability_candidate.schema.json" in forge_surface["evidence_files"]
    assert "tests/test_gateway/test_capability_forge.py" in forge_surface["evidence_files"]
    assert "candidate_promotion_blocked" in witnesses
    assert "candidate_schema_valid" in witnesses
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
    assert "CapabilityMaturityAssessor.assess" in maturity_surface["representative_paths"]
    assert "CapabilityRegistryMaturityProjector.decorate_read_model" in maturity_surface["representative_paths"]
    assert "MaturityProjectingCapabilityAdmissionGate.read_model" in maturity_surface["representative_paths"]
    assert "docs/39_governed_capability_fabric.md" in maturity_surface["evidence_files"]
    assert "gateway/capability_fabric.py" in maturity_surface["evidence_files"]
    assert "gateway/capability_maturity.py" in maturity_surface["evidence_files"]
    assert "gateway/operator_capability_console.py" in maturity_surface["evidence_files"]
    assert "schemas/capability_maturity.schema.json" in maturity_surface["evidence_files"]
    assert "tests/test_gateway/test_capability_fabric.py" in maturity_surface["evidence_files"]
    assert "tests/test_gateway/test_capability_maturity.py" in maturity_surface["evidence_files"]
    assert "tests/test_gateway/test_operator_capability_console.py" in maturity_surface["evidence_files"]
    assert "maturity_derived_from_evidence" in witnesses
    assert "registry_read_model_exposes_maturity" in witnesses
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
    assert "gateway/worker_mesh.py" in worker_surface["evidence_files"]
    assert "schemas/worker_mesh.schema.json" in worker_surface["evidence_files"]
    assert "tests/test_gateway/test_worker_mesh.py" in worker_surface["evidence_files"]
    assert "active_lease_required" in witnesses
    assert "tenant_capability_operation_budget_checked" in witnesses
    assert "forbidden_operations_override_allowed" in witnesses
    assert "worker_evidence_refs_required" in witnesses
    assert "worker_receipt_not_terminal_closure" in witnesses
    assert "worker_mesh_schema_valid" in witnesses
    assert closure_actions["publish_networked_worker_mesh_contract"]["status"] == "closed"


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
