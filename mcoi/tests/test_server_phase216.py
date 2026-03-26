"""Phase 216 — Server endpoint tests for memory, A/B, isolation."""

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
    from mcoi_runtime.app.server import app
    return TestClient(app)


class TestMemoryEndpoints:
    def test_store_memory(self, client):
        resp = client.post("/api/v1/memory/store", json={
            "agent_id": "llm-agent", "tenant_id": "t1",
            "category": "fact", "content": "User prefers Python",
        })
        assert resp.status_code == 200
        assert resp.json()["memory_id"]

    def test_search_memory(self, client):
        client.post("/api/v1/memory/store", json={
            "agent_id": "a1", "tenant_id": "t1",
            "content": "Python is a programming language",
            "keywords": ["python", "programming"],
        })
        resp = client.post("/api/v1/memory/search", json={
            "agent_id": "a1", "tenant_id": "t1", "query": "python",
        })
        assert resp.status_code == 200
        assert resp.json()["count"] >= 1

    def test_memory_summary(self, client):
        resp = client.get("/api/v1/memory/summary")
        assert resp.status_code == 200
        assert "total" in resp.json()


class TestABTestEndpoints:
    def test_ab_test(self, client):
        resp = client.post("/api/v1/ab-test", json={
            "prompt": "What is 2+2?", "model_ids": ["default"],
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["experiment_id"]
        assert data["winner"]

    def test_ab_summary(self, client):
        client.post("/api/v1/ab-test", json={"prompt": "test"})
        resp = client.get("/api/v1/ab-test/summary")
        assert resp.json()["total_experiments"] >= 1


class TestIsolationEndpoints:
    def test_verify_isolation(self, client):
        resp = client.post("/api/v1/isolation/verify", params={
            "tenant_a": "iso-a", "tenant_b": "iso-b",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["all_isolated"] is True
        assert data["probes_run"] >= 3

    def test_isolation_summary(self, client):
        resp = client.get("/api/v1/isolation/summary")
        assert resp.status_code == 200
        assert "probes_registered" in resp.json()
