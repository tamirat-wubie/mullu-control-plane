"""Tests for the Component Harness read-model route.

Purpose: prove the component read model joins registry, router inventory, and
proof binding posture without granting execution authority.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: FastAPI TestClient and mcoi_runtime.app.component_read_model.
Invariants: route is read-only, schema-shaped, and keeps live authority false.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from mcoi_runtime.app.component_read_model import build_component_read_model
from mcoi_runtime.app.routers.components import router


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_component_read_model_builds_registry_router_proof_projection() -> None:
    read_model = build_component_read_model()
    components = {component["component_id"]: component for component in read_model["components"]}

    assert read_model["governed"] is True
    assert read_model["route"] == "/api/v1/components/read-model"
    assert read_model["summary"]["component_count"] == 10
    assert read_model["summary"]["bound_route_count"] == 31
    assert read_model["summary"]["route_family_classification_count"] == 78
    assert read_model["summary"]["classified_declared_route_count"] == 441
    assert read_model["summary"]["lifecycle_receipt_count"] == 10
    assert read_model["summary"]["authority_witness_count"] == 10
    assert components["governance_core"]["route_binding"]["route_count"] == 23
    assert "component_harness_read_model" in components["governance_core"]["route_binding"]["proof_surface_ids"]
    assert "component_request_simulator" in components["governance_core"]["route_binding"]["proof_surface_ids"]
    assert "component_autopsy" in components["governance_core"]["route_binding"]["proof_surface_ids"]
    assert components["governance_core"]["lifecycle_receipt"]["proof_state"] == "Pass"
    assert components["governance_core"]["authority_witness"]["proof_state"] == "Pass"
    assert components["nested_mind_bridge"]["proof_binding"]["state"] == "awaiting_binding"


def test_component_read_model_route_is_read_only() -> None:
    client = _client()

    response = client.get("/api/v1/components/read-model")
    post_response = client.post("/api/v1/components/read-model", json={"action": "mutate"})
    put_response = client.put("/api/v1/components/read-model", json={"action": "mutate"})
    delete_response = client.delete("/api/v1/components/read-model")

    payload = response.json()
    assert response.status_code == 200
    assert payload["read_model_is_not_execution_authority"] is True
    assert payload["live_execution_enabled"] is False
    assert payload["live_connector_send_enabled"] is False
    assert payload["terminal_closure_required"] is True
    assert post_response.status_code == 405
    assert put_response.status_code == 405
    assert delete_response.status_code == 405


def test_component_read_model_blocks_live_authority() -> None:
    payload = _client().get("/api/v1/components/read-model").json()

    assert payload["summary"]["proof_bound_count"] == 9
    assert payload["summary"]["awaiting_binding_count"] == 1
    assert payload["summary"]["blocked_component_count"] == 1
    assert payload["summary"]["classified_declared_route_count"] == 441
    for component in payload["components"]:
        authority = component["authority"]
        assert authority["can_execute"] is False
        assert authority["can_mutate"] is False
        assert authority["can_call_connector"] is False
        assert authority["can_write_files"] is False
        assert authority["can_send_external_message"] is False
        assert authority["can_claim_terminal_closure"] is False
        assert component["authority_witness"]["witness_is_not_execution_authority"] is True
        assert component["authority_witness"]["can_claim_terminal_closure"] is False
        assert "terminal_closure" in component["blocked_actions"]
