"""Purpose: verify bounded helper contracts in the governed server boundary.
Governance scope: helper validation tests only.
Dependencies: server helper functions and pytest monkeypatch support.
Invariants: environment flag validation stays bounded and does not reflect caller names.
"""

from __future__ import annotations

import importlib

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from mcoi_runtime.app import server_http
from mcoi_runtime.app import server_policy
from mcoi_runtime.app import server_runtime
from mcoi_runtime.core.structured_output import StructuredOutputEngine
from mcoi_runtime.core.tool_use import ToolRegistry


def test_env_flag_bounds_invalid_boolean_name(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MCOI_TEST_FLAG", "sometimes")

    with pytest.raises(ValueError, match="^value must be a boolean flag$") as exc_info:
        server_policy._env_flag("MCOI_TEST_FLAG", {"MCOI_TEST_FLAG": "sometimes"})

    message = str(exc_info.value)
    assert message == "value must be a boolean flag"
    assert "MCOI_TEST_FLAG" not in message
    assert "boolean flag" in message


def test_db_backend_rejects_memory_in_production() -> None:
    with pytest.raises(
        RuntimeError,
        match="^MULLU_DB_BACKEND=memory is not allowed in production environment\\.",
    ) as exc_info:
        server_policy._validate_db_backend_for_env("memory", "production")

    message = str(exc_info.value)
    assert "postgresql" in message
    assert "production" in message


def test_db_backend_warns_for_unknown_non_dev_env() -> None:
    warning = server_policy._validate_db_backend_for_env("memory", "staging")
    assert warning is not None
    assert warning.startswith("MULLU_DB_BACKEND=memory in non-dev environment.")
    assert "postgresql" in warning


def test_resolve_cors_origins_uses_dev_defaults() -> None:
    origins = server_policy._resolve_cors_origins(None, "local_dev")
    assert origins == ["http://localhost:3000", "http://localhost:8080"]


def test_validate_cors_origins_rejects_empty_in_production() -> None:
    with pytest.raises(
        RuntimeError,
        match="^MULLU_CORS_ORIGINS must be set in pilot or production environment\\.",
    ) as exc_info:
        server_policy._validate_cors_origins_for_env([], "production")

    message = str(exc_info.value)
    assert "https://app.mullu.io" in message
    assert "*" not in message


def test_validate_cors_origins_warns_for_unknown_non_dev_env() -> None:
    warning = server_policy._validate_cors_origins_for_env([], "staging")
    assert warning is not None
    assert warning.startswith("MULLU_CORS_ORIGINS is empty in non-dev environment.")
    assert "https://app.mullu.io" in warning


def test_server_rejects_empty_cors_in_production(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MULLU_ENV", "production")
    monkeypatch.setenv("MULLU_DB_BACKEND", "postgresql")
    monkeypatch.delenv("MULLU_CORS_ORIGINS", raising=False)

    with pytest.raises(
        RuntimeError,
        match="^MULLU_CORS_ORIGINS must be set in pilot or production environment\\.",
    ):
        from mcoi_runtime.app import server as server_module
        importlib.reload(server_module)

    monkeypatch.setenv("MULLU_ENV", "local_dev")
    monkeypatch.setenv("MULLU_DB_BACKEND", "memory")
    monkeypatch.setenv(
        "MULLU_CORS_ORIGINS",
        "http://localhost:3000,http://localhost:8080",
    )
    from mcoi_runtime.app import server as server_module
    importlib.reload(server_module)


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


def test_build_default_input_validator_registers_expected_schemas() -> None:
    validator = server_runtime.build_default_input_validator()

    assert validator.schema_count == 3
    assert validator.validate("api_request", {"tenant_id": "tenant-a"}).valid is True
    assert validator.validate("completion", {"prompt": "x", "max_tokens": 1, "temperature": 0.0}).valid is True


def test_validate_or_raise_returns_bounded_422_payload() -> None:
    validator = server_runtime.build_default_input_validator()

    with pytest.raises(Exception) as exc_info:
        server_runtime.validate_or_raise(
            input_validator=validator,
            schema_id="completion",
            data={"prompt": "", "max_tokens": 0, "temperature": 3.0},
        )

    exc = exc_info.value
    assert getattr(exc, "status_code", None) == 422
    assert exc.detail["error"] == "Validation failed"
    assert exc.detail["governed"] is True
    assert exc.detail["validation_errors"]


def test_calculator_handler_uses_expression_engine() -> None:
    result = server_runtime.calculator_handler(
        {"expression": "2+3"},
        evaluate_expression_fn=lambda expression: 5 if expression == "2+3" else 0,
    )

    assert result == {"result": "5"}


def test_register_default_tools_registers_calculator_and_time() -> None:
    registry = ToolRegistry(clock=lambda: "2026-01-01T00:00:00Z")

    server_runtime.register_default_tools(
        tool_registry=registry,
        clock=lambda: "2026-01-01T00:00:00Z",
        evaluate_expression_fn=lambda expression: 7 if expression == "3+4" else 0,
    )

    listed = registry.list_tools()
    ids = {tool.tool_id for tool in listed}
    assert ids == {"calculator", "get_time"}
    assert registry.invoke("calculator", {"expression": "3+4"}).output == {"result": "7"}
    assert registry.invoke("get_time", {}).output == {"time": "2026-01-01T00:00:00Z"}


def test_register_default_output_schemas_registers_analysis_schema() -> None:
    engine = StructuredOutputEngine()
    server_runtime.register_default_output_schemas(engine)

    summary = engine.summary()
    assert summary["schemas"] == 1
    assert engine.list_schemas()[0].schema_id == "analysis"
