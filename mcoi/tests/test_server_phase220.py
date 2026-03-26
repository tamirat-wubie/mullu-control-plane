"""Phase 220 — Server endpoint tests for cache, feature flags."""

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


class TestCacheEndpoint:
    def test_cache_stats(self, client):
        resp = client.get("/api/v1/cache/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert "size" in data
        assert "hit_rate" in data


class TestFeatureFlagsEndpoints:
    def test_list_flags(self, client):
        resp = client.get("/api/v1/flags")
        assert resp.status_code == 200
        data = resp.json()
        assert data["summary"]["total"] >= 4
        ids = [f["id"] for f in data["flags"]]
        assert "streaming_v2" in ids

    def test_check_flag_enabled(self, client):
        resp = client.get("/api/v1/flags/streaming_v2")
        assert resp.json()["enabled"] is True

    def test_check_flag_unknown(self, client):
        resp = client.get("/api/v1/flags/nonexistent")
        assert resp.json()["enabled"] is False
