"""Tests for the public Mullu Governance Protocol manifest.

Purpose: verify the open schema surface is complete and the runtime remains outside the public contract boundary.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA]
Dependencies: protocol manifest validator and public schemas.
Invariants: every schema is indexed once, URNs match, and runtime paths are non-contract surfaces.
"""
from __future__ import annotations

from scripts.validate_protocol_manifest import (
    CLOSED_SURFACE,
    OPEN_SURFACE,
    PROTOCOL_ID,
    load_manifest,
    validate_protocol_manifest,
)


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
    memory_lattice_entry = entries["memory-lattice"]
    policy_proof_entry = entries["policy-proof-report"]
    trust_ledger_entry = entries["trust-ledger-bundle"]
    trust_anchor_entry = entries["trust-ledger-anchor-receipt"]
    domain_pack_entry = entries["domain-operating-pack"]
    multimodal_entry = entries["multimodal-operation-receipt"]
    gateway_readiness_entry = entries["gateway-publication-readiness"]
    gateway_receipt_validation_entry = entries["gateway-publication-receipt-validation"]
    goal_entry = entries["goal"]
    temporal_entry = entries["temporal-operation-receipt"]
    temporal_evidence_entry = entries["temporal-evidence-freshness-receipt"]
    temporal_reapproval_entry = entries["temporal-reapproval-receipt"]
    temporal_dispatch_window_entry = entries["temporal-dispatch-window-receipt"]
    temporal_budget_window_entry = entries["temporal-budget-window-receipt"]
    temporal_memory_entry = entries["temporal-memory-receipt"]
    temporal_memory_refresh_entry = entries["temporal-memory-refresh-receipt"]
    scheduler_entry = entries["temporal-scheduler-receipt"]
    simulation_entry = entries["simulation-receipt"]
    workflow_mining_entry = entries["workflow-mining-report"]
    worker_mesh_entry = entries["worker-mesh"]
    world_state_entry = entries["world-state"]
    reflex_entry = entries["reflex-deployment-witness-envelope"]
    receipt_entry = entries["reflex-deployment-witness-validator-receipt"]
    errors = validate_protocol_manifest(manifest)

    assert errors == []
    assert manifest["protocol_id"] == PROTOCOL_ID
    assert manifest["protocol_name"] == "Mullu Governance Protocol"
    assert manifest["protocol_uri_scheme"] == "mgp://"
    assert len(manifest["schemas"]) == 95
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
    assert memory_lattice_entry["path"] == "schemas/memory_lattice.schema.json"
    assert memory_lattice_entry["urn"] == "urn:mullusi:schema:memory-lattice:1"
    assert memory_lattice_entry["surface"] == "memory"
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
    assert workflow_mining_entry["path"] == "schemas/workflow_mining_report.schema.json"
    assert workflow_mining_entry["urn"] == "urn:mullusi:schema:workflow-mining-report:1"
    assert workflow_mining_entry["surface"] == "workflow"
    assert worker_mesh_entry["path"] == "schemas/worker_mesh.schema.json"
    assert worker_mesh_entry["urn"] == "urn:mullusi:schema:worker-mesh:1"
    assert worker_mesh_entry["surface"] == "worker"
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
