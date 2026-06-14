"""Purpose: verify the SNet operator read-model HTTP route.
Governance scope: read-only SNet route exposure, bounded symbol projection,
    raw-answer suppression, no-authority flags, and default router mounting.
Dependencies: FastAPI TestClient, SNet router, and SNet read-model validator.
Invariants:
  - The route exposes a bounded read model only.
  - The route does not expose raw answers or raw metadata values.
  - The route has no mutation companion.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from mcoi_runtime.app.routers.snet import router
from mcoi_runtime.app.server_http import include_default_routers, iter_effective_app_routes
from scripts.validate_snet_operator_read_model import validate_read_model


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_snet_operator_read_model_exposes_bounded_no_authority_projection() -> None:
    client = _client()

    response = client.get("/api/v1/snet/operator/read-model", params={"max_symbol_count": 1})
    payload = response.json()

    assert response.status_code == 200
    assert not validate_read_model(payload)
    assert payload["surface"] == "read_only_snet_recursive_mesh"
    assert payload["raw_answers_exposed"] is False
    assert payload["raw_metadata_values_exposed"] is False
    assert payload["execution_authority_granted"] is False
    assert payload["connector_authority_granted"] is False
    assert payload["route_authority_granted"] is False
    assert payload["filesystem_authority_granted"] is False
    assert payload["receipt"]["receipt_is_not_terminal_closure"] is True
    assert payload["receipt"]["terminal_closure_required"] is True
    assert len(payload["selected_symbols"]) == 1
    assert payload["truncated_symbol_count"] == payload["symbol_count"] - 1


def test_snet_operator_read_model_zero_symbol_projection_is_valid() -> None:
    client = _client()

    response = client.get("/api/v1/snet/operator/read-model", params={"max_symbol_count": 0})
    payload = response.json()

    assert response.status_code == 200
    assert not validate_read_model(payload)
    assert payload["selected_symbols"] == []
    assert payload["truncated_symbol_count"] == payload["symbol_count"]


def test_snet_operator_read_model_rejects_invalid_bound_without_server_error() -> None:
    client = _client()

    response = client.get("/api/v1/snet/operator/read-model", params={"max_symbol_count": -1})
    payload = response.json()

    assert response.status_code == 422
    assert "detail" in payload
    assert "Traceback" not in response.text


def test_snet_operator_read_model_has_no_mutation_companion() -> None:
    client = _client()

    post_response = client.post("/api/v1/snet/operator/read-model", json={})
    put_response = client.put("/api/v1/snet/operator/read-model", json={})
    delete_response = client.delete("/api/v1/snet/operator/read-model")

    assert post_response.status_code == 405
    assert put_response.status_code == 405
    assert delete_response.status_code == 405
    assert "Traceback" not in post_response.text


def test_default_router_mounts_snet_operator_read_model() -> None:
    app = FastAPI()
    include_default_routers(app)
    client = TestClient(app)

    paths = {route.path for route in iter_effective_app_routes(app)}
    response = client.get("/api/v1/snet/operator/read-model", params={"max_symbol_count": 1})
    payload = response.json()

    assert "/api/v1/snet/operator/read-model" in paths
    assert response.status_code == 200
    assert payload["surface"] == "read_only_snet_recursive_mesh"
    assert payload["receipt"]["connector_authority_granted"] is False
