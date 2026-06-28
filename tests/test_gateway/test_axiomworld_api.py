"""AxiomWorld API route tests.

Purpose: verify bounded HTTP access to the AxiomWorld generic event adapter.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: gateway.axiomworld_api and FastAPI TestClient.
Invariants:
  - Routes pass through the adapter and kernel receipts.
  - Malformed input returns bounded errors.
  - Route registration is explicit and reusable.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from gateway.axiomworld_api import (
    AXIOMWORLD_INGEST_PATH,
    create_axiomworld_app,
    register_axiomworld_routes,
)
from gateway.axiomworld_generic_event_adapter import AxiomWorldGenericEventAdapter


NOW = "2026-06-28T14:00:00+00:00"
TENANT = "tenant-api"


def test_axiomworld_health_route_reports_ready_boundary() -> None:
    client = TestClient(create_axiomworld_app())

    response = client.get("/api/v1/axiomworld/health")
    payload = response.json()

    assert response.status_code == 200
    assert payload["status"] == "ready"
    assert payload["ingest_path"] == AXIOMWORLD_INGEST_PATH
    assert payload["mutation_boundary"] == "adapter_only"


def test_axiomworld_ingest_route_returns_projection_receipts_and_state() -> None:
    adapter = AxiomWorldGenericEventAdapter()
    client = TestClient(create_axiomworld_app(adapter=adapter))

    response = client.post(AXIOMWORLD_INGEST_PATH, json=_payload())
    payload = response.json()

    assert response.status_code == 200
    assert payload["decision"] == "ACCEPT"
    assert payload["tenant_id"] == TENANT
    assert payload["materialized_state"]["entity_count"] == 1
    assert payload["materialized_state"]["claim_count"] == 1
    assert payload["projection"]["symbols"][0]["entity_id"] == "repo:mullu-control-plane"
    assert payload["projection"]["claims"][0]["claim_id"] == "claim:foundation-ready"
    assert len(payload["receipts"]) == 3
    assert len(adapter.kernel.receipts()) == 3


def test_axiomworld_ingest_route_bounds_validation_errors() -> None:
    client = TestClient(create_axiomworld_app())
    payload = _payload()
    payload["evidence"] = []

    response = client.post(AXIOMWORLD_INGEST_PATH, json=payload)
    body = response.json()

    assert response.status_code == 422
    assert body["detail"]["reason"] == "evidence_required"
    assert "repo:mullu-control-plane" not in str(body)
    assert "sha256:evidence-1" not in str(body)


def test_axiomworld_routes_register_on_existing_fastapi_app() -> None:
    app = FastAPI(title="host")
    adapter = register_axiomworld_routes(app)
    client = TestClient(app)

    health = client.get("/api/v1/axiomworld/health")
    ingest = client.post(AXIOMWORLD_INGEST_PATH, json=_payload())

    assert health.status_code == 200
    assert ingest.status_code == 200
    assert app.state.axiomworld_adapter is adapter
    assert ingest.json()["decision"] == "ACCEPT"


def test_gateway_factory_registers_axiomworld_routes() -> None:
    from gateway.server import create_gateway_app

    adapter = AxiomWorldGenericEventAdapter()
    app = create_gateway_app(platform=None, axiomworld_adapter=adapter)
    client = TestClient(app)

    health = client.get("/api/v1/axiomworld/health")
    ingest = client.post(AXIOMWORLD_INGEST_PATH, json=_payload())
    payload = ingest.json()

    assert health.status_code == 200
    assert ingest.status_code == 200
    assert app.state.axiomworld_adapter is adapter
    assert payload["projection"]["observer"] == "api-test"
    assert payload["materialized_state"]["entity_count"] == 1


def _payload() -> dict[str, object]:
    return {
        "event_id": "event:api-repo-observed",
        "tenant_id": TENANT,
        "source": "github_snapshot",
        "observed_at": NOW,
        "evidence": [
            {
                "evidence_id": "evidence-1",
                "evidence_type": "snapshot",
                "source": "fixture",
                "observed_at": NOW,
                "content_hash": "sha256:evidence-1",
            }
        ],
        "symbol": {
            "entity_id": "repo:mullu-control-plane",
            "entity_type": "repository",
            "display_name": "Mullu Control Plane",
            "stable_fingerprint": {
                "provider": "github",
                "owner": "tamirat-wubie",
                "repo": "mullu-control-plane",
            },
            "scope": "public",
            "permissions": {"public": True},
        },
        "claims": [
            {
                "claim_id": "claim:foundation-ready",
                "subject_ref": "repo:mullu-control-plane",
                "predicate": "readiness",
                "object_value": "foundation",
                "scope": "public",
            }
        ],
        "projection": {"observer": "api-test", "scope": "public"},
    }
