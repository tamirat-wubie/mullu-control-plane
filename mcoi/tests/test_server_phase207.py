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
    def test_config_read_model_hash_bound(self, client):
        client.post("/api/v1/config/update", json={
            "changes": {"features": {"hash_bound": True}},
            "applied_by": "anchor-test",
        })
        resp = client.get("/api/v1/config")
        data = resp.json()
        assert resp.status_code == 200
        assert isinstance(data["hash"], str)
        assert len(data["hash"]) == 16

    def test_config_current_read_model_hash_bound(self, client):
        client.post("/api/v1/config/update", json={
            "changes": {"features": {"current_hash_bound": True}},
            "applied_by": "anchor-test",
        })
        first = client.get("/api/v1/config").json()
        second = client.get("/api/v1/config").json()
        assert first["version"] == second["version"]
        assert first["hash"] == second["hash"]
        assert first["config"] == second["config"]

    def test_config_history_versions_bounded(self, client):
        client.post("/api/v1/config/update", json={"changes": {"features": {"history_versions": True}}})
        resp = client.get("/api/v1/config/history", params={"limit": 3})
        versions = resp.json()["versions"]
        assert resp.status_code == 200
        assert len(versions) <= 3
        assert all(isinstance(record["version"], int) for record in versions)

    def test_config_history_bounded(self, client):
        for index in range(4):
            client.post("/api/v1/config/update", json={"changes": {"features": {f"bounded_{index}": True}}})
        resp = client.get("/api/v1/config/history", params={"limit": 2})
        versions = resp.json()["versions"]
        assert resp.status_code == 200
        assert len(versions) == 2
        assert all(len(record["hash"]) == 16 for record in versions)

    def test_config_update_applies_atomically(self, client):
        before = client.get("/api/v1/config").json()["version"]
        resp = client.post("/api/v1/config/update", json={
            "changes": {"features": {"atomic_update": True}},
            "applied_by": "anchor-test",
            "description": "atomic witness",
        })
        after = client.get("/api/v1/config").json()
        assert resp.json()["success"] is True
        assert after["version"] == before + 1
        assert after["config"]["features"]["atomic_update"] is True

    def test_config_update_audited(self, client):
        resp = client.post("/api/v1/config/update", json={
            "changes": {"audit_anchor": True},
            "applied_by": "audit-anchor",
        })
        audit = client.get("/api/v1/audit", params={"action": "config.update"}).json()
        assert resp.status_code == 200
        assert resp.json()["success"] is True
        assert audit["count"] >= 1

    def test_config_update_emits_event_and_audit(self, client):
        resp = client.post("/api/v1/config/update", json={
            "changes": {"event_audit_anchor": True},
            "applied_by": "event-audit-anchor",
        })
        events = client.get("/api/v1/events", params={"event_type": "config.updated"}).json()
        audit = client.get("/api/v1/audit", params={"action": "config.update"}).json()
        assert resp.json()["success"] is True
        assert events["count"] >= 1
        assert audit["count"] >= 1

    def test_config_update_emits_event(self, client):
        resp = client.post("/api/v1/config/update", json={"changes": {"event_anchor": True}})
        events = client.get("/api/v1/events", params={"event_type": "config.updated"}).json()
        assert resp.status_code == 200
        assert resp.json()["success"] is True
        assert events["count"] >= 1

    def test_config_rollback_requires_known_version(self, client):
        resp = client.post("/api/v1/config/rollback", json={"to_version": 999999})
        data = resp.json()
        assert resp.status_code == 200
        assert data["success"] is False
        assert data["error"] == "version not found"

    def test_config_rollback_version_checked(self, client):
        before = client.get("/api/v1/config").json()["version"]
        client.post("/api/v1/config/update", json={"changes": {"rollback_anchor": True}})
        resp = client.post("/api/v1/config/rollback", json={"to_version": before})
        data = resp.json()
        assert resp.status_code == 200
        assert data["success"] is True
        assert data["version"] > before

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
    def test_replay_trace_list_bounded(self, client):
        resp = client.get("/api/v1/replay/traces")
        data = resp.json()
        assert resp.status_code == 200
        assert data["count"] == len(data["traces"])
        assert data["count"] <= 50
        assert {"completed", "active", "total_frames"} <= set(data["summary"])
