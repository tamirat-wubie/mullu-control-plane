"""Robustness: POST handlers must return a bounded 400 (not 500) on invalid input.

The schema-aware POST fuzz found four handlers that let a core ValueError escape
to the generic 500 handler when given valid-schema-but-invalid input (empty
required ids, a private/empty webhook URL). A 500 on client input is both a
reliability signal-to-noise problem and an internal-detail leak. Each now
translates the domain ValueError into a bounded 400 at the HTTP boundary.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from mcoi_runtime.app.routers.agent import router as agent_router
from mcoi_runtime.app.routers.data.governance import router as governance_router
from mcoi_runtime.app.routers.ops.config import router as config_router


@pytest.fixture
def client() -> TestClient:
    app = FastAPI()
    app.include_router(agent_router)
    app.include_router(governance_router)
    app.include_router(config_router)
    return TestClient(app, raise_server_exceptions=False)


def test_webhook_subscribe_invalid_url_is_400(client):
    resp = client.post(
        "/api/v1/webhooks/subscribe",
        json={"subscription_id": "s", "tenant_id": "t", "url": "", "events": [], "secret": ""},
    )
    assert resp.status_code == 400


def test_residency_constraint_empty_id_is_400(client):
    resp = client.post(
        "/api/v1/data-governance/residency-constraints",
        json={"constraint_id": "", "tenant_id": "t", "allowed_regions": [], "denied_regions": []},
    )
    assert resp.status_code == 400


def test_config_update_empty_actor_is_400(client):
    resp = client.post(
        "/api/v1/config/update",
        json={"changes": {}, "applied_by": "", "description": ""},
    )
    assert resp.status_code == 400


def test_config_rollback_empty_actor_is_400(client):
    resp = client.post(
        "/api/v1/config/rollback",
        json={"to_version": 0, "applied_by": ""},
    )
    assert resp.status_code == 400
