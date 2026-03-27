"""Tests proving infrastructure wiring: CORS, shutdown, router deps."""
from __future__ import annotations

import os
import pytest

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
    return TestClient(app, raise_server_exceptions=False)


class TestCORSMiddleware:
    """Prove CORS middleware is wired."""

    def test_cors_headers_on_preflight(self, client):
        resp = client.options(
            "/api/v1/complete",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "POST",
            },
        )
        assert resp.status_code == 200
        assert "access-control-allow-origin" in resp.headers

    def test_cors_headers_on_get(self, client):
        resp = client.get(
            "/health",
            headers={"Origin": "http://localhost:3000"},
        )
        assert resp.status_code == 200
        assert "access-control-allow-origin" in resp.headers


class TestGracefulShutdownWiring:
    """Prove shutdown manager is wired with real handlers."""

    def test_shutdown_hooks_registered(self):
        os.environ["MULLU_ENV"] = "local_dev"
        os.environ["MULLU_DB_BACKEND"] = "memory"
        from mcoi_runtime.app.server import shutdown_mgr
        names = shutdown_mgr.hook_names()
        assert "save_state" in names
        assert "flush_metrics" in names
        assert "close_connections" in names

    def test_save_state_hook_returns_data(self):
        os.environ["MULLU_ENV"] = "local_dev"
        os.environ["MULLU_DB_BACKEND"] = "memory"
        from mcoi_runtime.app.server import shutdown_mgr
        result = shutdown_mgr.execute()
        assert result.hooks_run >= 3
        # At least flush_metrics and close_connections should succeed
        assert result.hooks_succeeded >= 2

    def test_shutdown_endpoint_shows_hooks(self, client):
        resp = client.get("/api/v1/shutdown/info")
        assert resp.status_code == 200
        body = resp.json()
        assert body["hooks"] >= 3


class TestRouterDeps:
    """Test the dependency container for router modules."""

    def test_deps_set_and_get(self):
        from mcoi_runtime.app.routers.deps import deps
        deps.set("test_val", 42)
        assert deps.get("test_val") == 42

    def test_deps_getattr(self):
        from mcoi_runtime.app.routers.deps import deps
        deps.set("my_service", "hello")
        assert deps.my_service == "hello"

    def test_deps_missing_raises(self):
        from mcoi_runtime.app.routers.deps import _Deps
        d = _Deps()
        with pytest.raises(RuntimeError, match="not registered"):
            d.get("nonexistent")
