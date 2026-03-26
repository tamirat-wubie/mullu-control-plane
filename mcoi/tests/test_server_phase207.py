"""Phase 207 — Server endpoint tests for config API, guards, capabilities, replay."""

import pytest
import os

try:
    from fastapi.testclient import TestClient
    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False


@pytest.fixture
def client():
    if not FASTAPI_AVAILABLE:
        pytest.skip("FastAPI not installed")
    os.environ["MULLU_ENV"] = "local_dev"
    os.environ["MULLU_DB_BACKEND"] = "memory"
    os.environ["MULLU_CERT_INTERVAL"] = "0"
    from mcoi_runtime.app.server import app
    return TestClient(app)


class TestConfigUpdateAPI:
    def test_update_config(self, client):
        resp = client.post("/api/v1/config/update", json={
            "changes": {"features": {"dark_mode": True}},
            "applied_by": "admin",
            "description": "enable dark mode",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["version"] >= 2

    def test_update_config_reflects(self, client):
        client.post("/api/v1/config/update", json={
            "changes": {"features": {"new_feature": True}},
        })
        resp = client.get("/api/v1/config")
        assert resp.json()["config"]["features"]["new_feature"] is True

    def test_update_emits_event(self, client):
        client.post("/api/v1/config/update", json={
            "changes": {"test_section": {"v": 1}},
        })
        resp = client.get("/api/v1/events", params={"event_type": "config.updated"})
        assert resp.json()["count"] >= 1

    def test_update_audited(self, client):
        client.post("/api/v1/config/update", json={
            "changes": {"audit_test": True}, "applied_by": "test-user",
        })
        resp = client.get("/api/v1/audit", params={"action": "config.update"})
        assert resp.json()["count"] >= 1

    def test_rollback(self, client):
        # Get initial version
        resp = client.get("/api/v1/config")
        initial_version = resp.json()["version"]

        # Update
        client.post("/api/v1/config/update", json={
            "changes": {"rollback_test": "new_value"},
        })

        # Rollback
        resp = client.post("/api/v1/config/rollback", json={
            "to_version": initial_version,
        })
        assert resp.json()["success"] is True

    def test_rollback_invalid_version(self, client):
        resp = client.post("/api/v1/config/rollback", json={
            "to_version": 99999,
        })
        assert resp.json()["success"] is False


class TestGuardsEndpoint:
    def test_list_guards(self, client):
        resp = client.get("/api/v1/guards")
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 3
        assert "tenant" in data["guards"]
        assert "rate_limit" in data["guards"]
        assert "budget" in data["guards"]


class TestCapabilitiesEndpoint:
    def test_list_capabilities(self, client):
        resp = client.get("/api/v1/capabilities")
        assert resp.status_code == 200
        caps = resp.json()["capabilities"]
        ids = [c["id"] for c in caps]
        assert "llm.completion" in ids
        assert "code.execution" in ids


class TestReplayEndpoint:
    def test_list_traces(self, client):
        resp = client.get("/api/v1/replay/traces")
        assert resp.status_code == 200
        assert resp.json()["count"] == 0
