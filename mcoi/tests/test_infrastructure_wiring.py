"""Tests proving infrastructure wiring: CORS, shutdown, router deps."""
from __future__ import annotations

import os
from types import SimpleNamespace

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
        with pytest.raises(RuntimeError) as exc:
            d.get("nonexistent")
        assert str(exc.value) == "dependency not registered"
        assert "nonexistent" not in str(exc.value)


class TestServerDependencyHelpers:
    def test_register_dependency_groups_sets_all_values(self):
        from mcoi_runtime.app.server_deps import register_dependency_groups

        class FakeDeps:
            def __init__(self):
                self.values = {}

            def set(self, name, value):
                self.values[name] = value

        deps = FakeDeps()
        register_dependency_groups(
            deps,
            {"alpha": 1, "beta": 2},
            {"gamma": 3},
        )

        assert deps.values["alpha"] == 1
        assert deps.values["beta"] == 2
        assert deps.values["gamma"] == 3

    def test_wire_runtime_dependencies_sets_late_bound_fields(self):
        from mcoi_runtime.app.server_deps import wire_runtime_dependencies

        guard_chain = object()
        audit_trail = object()
        scheduler = SimpleNamespace(_guard_chain=None, _audit_trail=None)
        connector_framework = SimpleNamespace(_guard_chain=None, _audit_trail=None)
        policy_sandbox = SimpleNamespace(_guard_chain=None)
        explanation_engine = SimpleNamespace(_guard_chain=None, _audit_trail=None)

        wire_runtime_dependencies(
            guard_chain=guard_chain,
            audit_trail=audit_trail,
            scheduler=scheduler,
            connector_framework=connector_framework,
            policy_sandbox=policy_sandbox,
            explanation_engine=explanation_engine,
        )

        assert scheduler._guard_chain is guard_chain
        assert scheduler._audit_trail is audit_trail
        assert connector_framework._guard_chain is guard_chain
        assert connector_framework._audit_trail is audit_trail
        assert policy_sandbox._guard_chain is guard_chain
        assert explanation_engine._guard_chain is guard_chain
        assert explanation_engine._audit_trail is audit_trail
