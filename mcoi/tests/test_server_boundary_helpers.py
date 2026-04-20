"""Purpose: verify app and HTTP helper contracts for the governed server.
Governance scope: boundary helper validation tests only.
Dependencies: server boundary helpers, FastAPI test client, and pytest support.
Invariants: boundary-facing helper behavior stays bounded, deterministic, and auditable.
"""

from __future__ import annotations

import asyncio

from fastapi import FastAPI
from fastapi.testclient import TestClient

from mcoi_runtime.app import server_app
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


def test_include_default_routers_mounts_health_and_completion_routes() -> None:
    app = FastAPI()
    server_http.include_default_routers(app)

    paths = {route.path for route in app.routes}
    assert "/health" in paths
    assert "/api/v1/complete" in paths


def test_build_app_lifespan_executes_shutdown_manager_on_exit() -> None:
    events: list[str] = []

    class ShutdownManager:
        def execute(self) -> None:
            events.append("shutdown")

    lifespan = server_app.build_app_lifespan(shutdown_mgr=ShutdownManager())

    async def run_lifespan() -> None:
        async with lifespan(FastAPI()):
            events.append("running")

    asyncio.run(run_lifespan())

    assert events == ["running", "shutdown"]
    assert events[0] == "running"
    assert events[-1] == "shutdown"


def test_create_governed_app_wires_middleware_and_http_boundaries() -> None:
    captured: dict[str, object] = {}

    class FakeFastAPI:
        def __init__(self, **kwargs) -> None:
            captured["init_kwargs"] = kwargs
            self.middlewares: list[tuple[object, dict[str, object]]] = []

        def add_middleware(self, middleware_cls, **kwargs) -> None:
            self.middlewares.append((middleware_cls, kwargs))
            captured["middleware"] = (middleware_cls, kwargs)

    class Metrics:
        def __init__(self) -> None:
            self.calls: list[tuple[str, int]] = []

        def inc(self, name: str, value: int) -> None:
            self.calls.append((name, value))

    class AuditTrail:
        def __init__(self) -> None:
            self.records: list[dict[str, object]] = []

        def record(self, **kwargs) -> None:
            self.records.append(kwargs)

    class PIIScanner:
        enabled = True

        def scan_dict(self, payload):
            return ({"scrubbed": payload["path"]},)

    class ShutdownManager:
        def execute(self) -> None:
            captured["shutdown_called"] = True

    metrics = Metrics()
    audit_trail = AuditTrail()

    def fake_configure_cors_middleware_fn(**kwargs) -> None:
        captured["cors_kwargs"] = kwargs

    def fake_install_global_exception_handler_fn(**kwargs) -> None:
        captured["exception_kwargs"] = kwargs

    app = server_app.create_governed_app(
        env="test",
        cors_origins_raw="https://example.com",
        guard_chain=object(),
        metrics=metrics,
        proof_bridge=object(),
        audit_trail=audit_trail,
        pii_scanner=PIIScanner(),
        platform_logger=object(),
        log_levels=object(),
        shutdown_mgr=ShutdownManager(),
        resolve_cors_origins=lambda raw, env: [raw or env],
        validate_cors_origins_for_env=lambda origins, env: None,
        fastapi_cls=FakeFastAPI,
        governance_middleware_cls="governance-middleware",
        configure_cors_middleware_fn=fake_configure_cors_middleware_fn,
        install_global_exception_handler_fn=fake_install_global_exception_handler_fn,
        warnings_module="warnings-module",
    )

    middleware_cls, middleware_kwargs = captured["middleware"]
    middleware_kwargs["metrics_fn"]("requests_total", 3)
    middleware_kwargs["on_reject"]({"tenant_id": "tenant-a", "path": "/guarded"})
    middleware_kwargs["on_allow"]({"tenant_id": "tenant-a", "path": "/guarded"})

    assert app is not None
    assert captured["init_kwargs"]["title"] == "Mullu Platform"
    assert captured["init_kwargs"]["version"] == "3.13.0"
    assert callable(captured["init_kwargs"]["lifespan"])
    assert middleware_cls == "governance-middleware"
    assert middleware_kwargs["proof_bridge"] is not None
    assert metrics.calls == [("requests_total", 3)]
    assert audit_trail.records[0]["detail"] == {"scrubbed": "/guarded"}
    assert audit_trail.records[0]["outcome"] == "denied"
    assert audit_trail.records[1]["actor_id"] == "tenant-a"
    assert captured["cors_kwargs"]["env"] == "test"
    assert captured["cors_kwargs"]["warnings_module"] == "warnings-module"
    assert captured["exception_kwargs"]["app"] is app
