"""Purpose: verify HTTP helper contracts for the governed server.
Governance scope: HTTP helper validation tests only.
Dependencies: server HTTP helpers, FastAPI test client, and pytest support.
Invariants: HTTP-facing helper behavior stays bounded, deterministic, and auditable.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from mcoi_runtime.app import server_http
from mcoi_runtime.app import server_policy


def test_configure_cors_middleware_adds_preflight_headers() -> None:
    app = FastAPI()
    server_http.configure_cors_middleware(
        app=app,
        env="local_dev",
        cors_origins_raw=None,
        resolve_cors_origins=server_policy._resolve_cors_origins,
        validate_cors_origins_for_env=server_policy._validate_cors_origins_for_env,
        warnings_module=__import__("warnings"),
    )

    @app.get("/probe")
    def probe() -> dict[str, bool]:
        return {"ok": True}

    client = TestClient(app, raise_server_exceptions=False)
    resp = client.options(
        "/probe",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert resp.status_code == 200
    assert resp.headers["access-control-allow-origin"] == "http://localhost:3000"


def test_configure_cors_middleware_fails_closed_for_empty_non_dev_origins() -> None:
    warnings_seen: list[tuple[str, int]] = []
    app = FastAPI()
    server_http.configure_cors_middleware(
        app=app,
        env="staging",
        cors_origins_raw="",
        resolve_cors_origins=server_policy._resolve_cors_origins,
        validate_cors_origins_for_env=server_policy._validate_cors_origins_for_env,
        warnings_module=type(
            "Warnings",
            (),
            {"warn": lambda self, message, stacklevel=1: warnings_seen.append((message, stacklevel))},
        )(),
    )

    @app.get("/probe")
    def probe() -> dict[str, bool]:
        return {"ok": True}

    client = TestClient(app, raise_server_exceptions=False)
    resp = client.options(
        "/probe",
        headers={
            "Origin": "https://untrusted.example",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert resp.status_code == 400
    assert "access-control-allow-origin" not in resp.headers
    assert warnings_seen[0][0].startswith("MULLU_CORS_ORIGINS is empty in non-dev environment.")


def test_global_exception_handler_returns_bounded_500() -> None:
    class Metrics:
        def __init__(self) -> None:
            self.calls: list[tuple[str, int]] = []

        def inc(self, name: str, value: int = 1) -> None:
            self.calls.append((name, value))

    class Logger:
        def __init__(self) -> None:
            self.messages: list[str] = []

        def log(self, level: str, message: str) -> None:
            self.messages.append(message)

    class Levels:
        ERROR = "error"

    app = FastAPI()
    metrics = Metrics()
    logger = Logger()
    server_http.install_global_exception_handler(
        app=app,
        metrics=metrics,
        platform_logger=logger,
        log_levels=Levels,
    )

    @app.get("/explode")
    def explode() -> dict[str, str]:
        raise RuntimeError("secret detail")

    client = TestClient(app, raise_server_exceptions=False)
    resp = client.get("/explode")

    assert resp.status_code == 500
    assert resp.json() == {"error": "Internal server error", "governed": True}
    assert metrics.calls == [("errors_total", 1)]
    assert logger.messages == ["Unhandled exception on /explode: RuntimeError"]


def test_global_exception_handler_maps_tenant_quota_to_bounded_429() -> None:
    from mcoi_runtime.substrate.registry_store import TenantQuotaExceeded

    class Metrics:
        def __init__(self) -> None:
            self.calls: list[tuple[str, int]] = []

        def inc(self, name: str, value: int = 1) -> None:
            self.calls.append((name, value))

    class Logger:
        def log(self, level: str, message: str) -> None:
            raise AssertionError("tenant quota handler must not use generic logger")

    class Levels:
        ERROR = "error"

    app = FastAPI()
    metrics = Metrics()
    server_http.install_global_exception_handler(
        app=app,
        metrics=metrics,
        platform_logger=Logger(),
        log_levels=Levels,
    )

    @app.get("/tenant-cap")
    def tenant_cap() -> dict[str, str]:
        raise TenantQuotaExceeded("max_tenants cap reached: secret-tenant")

    client = TestClient(app, raise_server_exceptions=False)
    resp = client.get("/tenant-cap")

    assert resp.status_code == 429
    assert resp.json() == {
        "error": "tenant registry capacity exhausted",
        "error_code": "tenant_registry_capacity_exhausted",
        "governed": True,
    }
    assert metrics.calls == [("requests_rejected", 1)]
    assert "secret-tenant" not in resp.text


def test_global_exception_handler_survives_metrics_and_logger_failures() -> None:
    class BrokenMetrics:
        def inc(self, name: str, value: int = 1) -> None:
            raise RuntimeError("metrics-secret")

    class BrokenLogger:
        def log(self, level: str, message: str) -> None:
            raise RuntimeError("logger-secret")

    class Levels:
        ERROR = "error"

    app = FastAPI()
    server_http.install_global_exception_handler(
        app=app,
        metrics=BrokenMetrics(),
        platform_logger=BrokenLogger(),
        log_levels=Levels,
    )

    @app.get("/explode")
    def explode() -> dict[str, str]:
        raise RuntimeError("handler-secret")

    client = TestClient(app, raise_server_exceptions=False)
    resp = client.get("/explode")

    assert resp.status_code == 500
    assert resp.json() == {"error": "Internal server error", "governed": True}
    assert "secret" not in resp.text


def test_include_default_routers_mounts_health_and_completion_routes() -> None:
    app = FastAPI()
    server_http.include_default_routers(app)

    paths = {route.path for route in app.routes}
    assert "/health" in paths
    assert "/api/v1/complete" in paths
    assert "/software/receipts" in paths
