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


def test_gateway_runtime_witness_covers_orchestration_receipts() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    runtime_surface = surfaces["gateway_runtime_witness"]

    assert runtime_surface["coverage_state"] == "witnessed"
    assert "scripts/orchestrate_deployment_witness.py" in runtime_surface["evidence_files"]
    assert ".github/workflows/gateway-publication.yml" in runtime_surface["evidence_files"]
    assert "schemas/deployment_orchestration_receipt.schema.json" in runtime_surface["evidence_files"]
    assert "schemas/mullu_governance_protocol.manifest.json" in runtime_surface["evidence_files"]
    assert "tests/test_orchestrate_deployment_witness.py" in runtime_surface["evidence_files"]
    assert "tests/test_validate_protocol_manifest.py" in runtime_surface["evidence_files"]
    assert "deployment_witness_orchestration_receipt" in runtime_surface["runtime_witnesses"]
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
    assert "offline_reflex_witness_replay" in witnesses
    assert "reflex_validator_receipt_artifact" in witnesses
    assert closure_actions["publish_runtime_reflex_engine_read_models"]["status"] == "closed"


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
