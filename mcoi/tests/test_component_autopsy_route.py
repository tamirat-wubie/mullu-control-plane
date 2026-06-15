"""Tests for the Component Harness autopsy route.

Purpose: prove component autopsy route exposes blockers and evidence posture
without granting execution authority.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: FastAPI TestClient and mcoi_runtime.app.component_autopsy.
Invariants: route is GET-only, schema-shaped, and keeps live authority false.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from mcoi_runtime.app.component_autopsy import (
    build_component_autopsy,
    build_foundation_component_autopsies,
)
from mcoi_runtime.app.routers.components import router


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_component_autopsy_builds_nested_mind_blocker_view() -> None:
    autopsy = build_component_autopsy("nested_mind_bridge")

    assert autopsy["component_id"] == "nested_mind_bridge"
    assert autopsy["autopsy_is_not_execution_authority"] is True
    assert autopsy["live_execution_enabled"] is False
    assert autopsy["outcome"] == "AwaitingEvidence"
    assert "proof_matrix_surface" in autopsy["missing_evidence"]
    assert "memory_topology_activation_witness" in autopsy["missing_evidence"]
    assert autopsy["next_transition_candidates"][0]["to_state"] == "registered"


def test_component_autopsy_route_is_read_only() -> None:
    client = _client()

    response = client.get("/api/v1/components/nested_mind_bridge/autopsy")
    post_response = client.post("/api/v1/components/nested_mind_bridge/autopsy", json={"action": "mutate"})
    put_response = client.put("/api/v1/components/nested_mind_bridge/autopsy", json={"action": "mutate"})
    delete_response = client.delete("/api/v1/components/nested_mind_bridge/autopsy")

    payload = response.json()
    assert response.status_code == 200
    assert payload["component_id"] == "nested_mind_bridge"
    assert payload["autopsy_is_not_execution_authority"] is True
    assert payload["can_execute"] is False
    assert payload["can_claim_terminal_closure"] is False
    assert post_response.status_code == 405
    assert put_response.status_code == 405
    assert delete_response.status_code == 405


def test_component_autopsy_route_rejects_unknown_component() -> None:
    response = _client().get("/api/v1/components/missing_component/autopsy")
    detail = response.json()["detail"]

    assert response.status_code == 404
    assert detail["error_code"] == "component_autopsy_unavailable"
    assert detail["governed"] is True
    assert "not registered" in detail["detail"]


def test_foundation_component_autopsies_keep_live_authority_false() -> None:
    autopsies = build_foundation_component_autopsies()

    assert len(autopsies) == 10
    assert any(autopsy["outcome"] == "AwaitingEvidence" for autopsy in autopsies)
    for autopsy in autopsies:
        assert autopsy["live_execution_enabled"] is False
        assert autopsy["live_connector_send_enabled"] is False
        assert autopsy["can_execute"] is False
        assert autopsy["can_mutate"] is False
        assert autopsy["can_call_connector"] is False
        assert autopsy["can_claim_terminal_closure"] is False
