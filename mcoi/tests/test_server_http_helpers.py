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
from mcoi_runtime.app.security_headers import SecurityHeadersConfig, build_security_headers


def _assert_request_id_shape(request_id: str) -> None:
    request_id_hex = request_id.removeprefix(server_http.REQUEST_ID_PREFIX)

    assert request_id.startswith(server_http.REQUEST_ID_PREFIX)
    assert len(request_id) == len(server_http.REQUEST_ID_PREFIX) + 32
    assert all(character in "0123456789abcdef" for character in request_id_hex)


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


def test_configure_cors_middleware_exposes_boundary_witness_headers() -> None:
    app = FastAPI()
    app.add_middleware(server_http.RequestIdMiddleware)
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
    resp = client.get("/probe", headers={"Origin": "http://localhost:3000"})
    exposed_headers = {
        header.strip().lower()
        for header in resp.headers["access-control-expose-headers"].split(",")
    }

    assert resp.status_code == 200
    assert resp.headers[server_http.REQUEST_ID_HEADER].startswith(server_http.REQUEST_ID_PREFIX)
    assert resp.headers[server_http.GOVERNED_HEADER] == "true"
    assert exposed_headers == {"x-request-id", "x-governed"}


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


def test_global_exception_response_preserves_request_id_witness() -> None:
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
    app.add_middleware(server_http.RequestIdMiddleware)
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
    resp = client.get("/explode", headers={server_http.REQUEST_ID_HEADER: "req-client-spoof"})
    response_request_id = resp.headers[server_http.REQUEST_ID_HEADER]

    assert resp.status_code == 500
    assert resp.json() == {"error": "Internal server error", "governed": True}
    assert resp.headers[server_http.GOVERNED_HEADER] == "true"
    assert response_request_id != "req-client-spoof"
    _assert_request_id_shape(response_request_id)
    assert metrics.calls == [("errors_total", 1)]
    assert logger.messages == ["Unhandled exception on /explode: RuntimeError"]


def test_global_exception_response_preserves_security_headers() -> None:
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
    security_headers = build_security_headers(SecurityHeadersConfig(environment="local_dev"))
    server_http.install_global_exception_handler(
        app=app,
        metrics=Metrics(),
        platform_logger=Logger(),
        log_levels=Levels,
        security_headers=security_headers,
    )

    @app.get("/explode")
    def explode() -> dict[str, str]:
        raise RuntimeError("secret detail")

    client = TestClient(app, raise_server_exceptions=False)
    resp = client.get("/explode")

    assert resp.status_code == 500
    assert resp.headers["X-Content-Type-Options"] == "nosniff"
    assert resp.headers["X-Frame-Options"] == "DENY"
    assert resp.headers["Cache-Control"] == "no-store"
    assert "connect-src *" in resp.headers["Content-Security-Policy"]


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

    paths = {route.path for route in server_http.iter_effective_app_routes(app)}
    assert "/health" in paths
    assert "/api/v1/complete" in paths
    assert "/software/receipts" in paths
