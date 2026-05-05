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
    orchestration_validation_entry = entries["deployment-orchestration-receipt-validation"]
    publication_closure_validation_entry = entries["deployment-publication-closure-validation"]
    candidate_entry = entries["capability-candidate"]
    gateway_readiness_entry = entries["gateway-publication-readiness"]
    gateway_receipt_validation_entry = entries["gateway-publication-receipt-validation"]
    goal_entry = entries["goal"]
    simulation_entry = entries["simulation-receipt"]
    worker_mesh_entry = entries["worker-mesh"]
    world_state_entry = entries["world-state"]
    reflex_entry = entries["reflex-deployment-witness-envelope"]
    receipt_entry = entries["reflex-deployment-witness-validator-receipt"]
    errors = validate_protocol_manifest(manifest)

    assert errors == []
    assert manifest["protocol_id"] == PROTOCOL_ID
    assert manifest["protocol_name"] == "Mullu Governance Protocol"
    assert manifest["protocol_uri_scheme"] == "mgp://"
    assert len(manifest["schemas"]) == 43
    assert orchestration_validation_entry["path"] == "schemas/deployment_orchestration_receipt_validation.schema.json"
    assert orchestration_validation_entry["urn"] == "urn:mullusi:schema:deployment-orchestration-receipt-validation:1"
    assert orchestration_validation_entry["surface"] == "deployment"
    assert publication_closure_validation_entry["path"] == "schemas/deployment_publication_closure_validation.schema.json"
    assert publication_closure_validation_entry["urn"] == "urn:mullusi:schema:deployment-publication-closure-validation:1"
    assert publication_closure_validation_entry["surface"] == "deployment"
    assert candidate_entry["path"] == "schemas/capability_candidate.schema.json"
    assert candidate_entry["urn"] == "urn:mullusi:schema:capability-candidate:1"
    assert candidate_entry["surface"] == "capability"
    assert gateway_readiness_entry["path"] == "schemas/gateway_publication_readiness.schema.json"
    assert gateway_readiness_entry["urn"] == "urn:mullusi:schema:gateway-publication-readiness:1"
    assert gateway_readiness_entry["surface"] == "deployment"
    assert gateway_receipt_validation_entry["path"] == "schemas/gateway_publication_receipt_validation.schema.json"
    assert gateway_receipt_validation_entry["urn"] == "urn:mullusi:schema:gateway-publication-receipt-validation:1"
    assert gateway_receipt_validation_entry["surface"] == "deployment"
    assert goal_entry["path"] == "schemas/goal.schema.json"
    assert goal_entry["urn"] == "urn:mullusi:schema:goal:1"
    assert goal_entry["surface"] == "planning"
    assert simulation_entry["path"] == "schemas/simulation_receipt.schema.json"
    assert simulation_entry["urn"] == "urn:mullusi:schema:simulation-receipt:1"
    assert simulation_entry["surface"] == "simulation"
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
