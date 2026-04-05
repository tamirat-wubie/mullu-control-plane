"""Purpose: verify bounded helper contracts in the governed server boundary.
Governance scope: helper validation tests only.
Dependencies: server helper functions and pytest monkeypatch support.
Invariants: environment flag validation stays bounded and does not reflect caller names.
"""

from __future__ import annotations

import importlib
from datetime import datetime

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from mcoi_runtime.app import server_bootstrap
from mcoi_runtime.app import server_agents
from mcoi_runtime.app import server_http
from mcoi_runtime.app import server_platform
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


def test_utc_clock_returns_parseable_utc_timestamp() -> None:
    value = server_bootstrap.utc_clock()
    parsed = datetime.fromisoformat(value)

    assert parsed.tzinfo is not None
    assert parsed.utcoffset().total_seconds() == 0


def test_init_field_encryption_from_env_without_key_is_disabled() -> None:
    encryptor, state = server_bootstrap.init_field_encryption_from_env(
        env={},
        bounded_bootstrap_warning=lambda context, exc: f"{context} failed ({type(exc).__name__})",
    )

    assert encryptor is None
    assert state == {
        "configured": False,
        "enabled": False,
        "aes_available": False,
        "warning": "",
    }


def test_init_field_encryption_from_env_bounds_invalid_key() -> None:
    def raise_invalid_key():
        raise ValueError("secret bootstrap detail")

    encryptor, state = server_bootstrap.init_field_encryption_from_env(
        env={"MULLU_ENCRYPTION_KEY": "c2hvcnQ="},
        bounded_bootstrap_warning=lambda context, exc: f"{context} failed ({type(exc).__name__})",
        key_provider_factory=raise_invalid_key,
    )

    assert encryptor is None
    assert state["configured"] is True
    assert state["enabled"] is False
    assert state["aes_available"] is False
    assert state["warning"] == "field encryption failed (ValueError)"


def test_bootstrap_primary_store_applies_sqlite_migrations() -> None:
    class MigrationEngine:
        def apply_all(self, conn):
            assert conn == "sqlite-conn"
            return [
                type("Result", (), {"name": "001-init", "success": True})(),
                type("Result", (), {"name": "002-skip", "success": False})(),
            ]

    warnings_seen: list[tuple[str, int]] = []

    bootstrap = server_platform.bootstrap_primary_store(
        env="local_dev",
        runtime_env={
            "MULLU_DB_BACKEND": "sqlite",
            "MULLU_DB_URL": "sqlite:///govern.db",
        },
        clock=lambda: "2026-01-01T00:00:00Z",
        validate_db_backend_for_env=lambda backend, env: None,
        create_store_fn=lambda **kwargs: type("Store", (), {"_conn": "sqlite-conn"})(),
        create_platform_migration_engine_fn=lambda **kwargs: MigrationEngine(),
        warnings_module=type("Warnings", (), {"warn": lambda self, message, stacklevel=1: warnings_seen.append((message, stacklevel))})(),
    )

    assert bootstrap.db_backend == "sqlite"
    assert bootstrap.warning is None
    assert bootstrap.migrations_applied == ("001-init",)
    assert warnings_seen == []


def test_bootstrap_governance_runtime_wires_services_and_local_policy() -> None:
    class BudgetManager:
        def __init__(self, *, clock, store):
            self.clock = clock
            self.store = store

    class MetricsEngine:
        def __init__(self, *, clock):
            self.clock = clock

    class RateLimitConfig:
        def __init__(self, *, max_tokens, refill_rate):
            self.max_tokens = max_tokens
            self.refill_rate = refill_rate

    class RateLimiter:
        def __init__(self, *, default_config, store):
            self.default_config = default_config
            self.store = store

    class AuditTrail:
        def __init__(self, *, clock, store):
            self.clock = clock
            self.store = store

    class TenantGating:
        def __init__(self, *, clock, store, allow_unknown_tenants):
            self.clock = clock
            self.store = store
            self.allow_unknown_tenants = allow_unknown_tenants

    stores = {
        "budget": object(),
        "rate_limit": object(),
        "audit": object(),
        "tenant_gating": object(),
    }
    local_policy = object()

    bootstrap = server_platform.bootstrap_governance_runtime(
        env="local_dev",
        runtime_env={},
        db_backend="memory",
        clock=lambda: "2026-01-01T00:00:00Z",
        field_encryptor=None,
        allow_unknown_tenants=True,
        create_governance_stores_fn=lambda **kwargs: stores,
        tenant_budget_manager_cls=BudgetManager,
        governance_metrics_engine_cls=MetricsEngine,
        rate_limiter_cls=RateLimiter,
        rate_limit_config_cls=RateLimitConfig,
        audit_trail_cls=AuditTrail,
        tenant_gating_registry_cls=TenantGating,
        sandboxed_policy=object(),
        local_dev_policy=local_policy,
        pilot_prod_policy=object(),
    )

    assert bootstrap.governance_stores is stores
    assert bootstrap.tenant_budget_mgr.store is stores["budget"]
    assert bootstrap.metrics.clock() == "2026-01-01T00:00:00Z"
    assert bootstrap.rate_limiter.store is stores["rate_limit"]
    assert bootstrap.rate_limiter.default_config.max_tokens == 60
    assert bootstrap.audit_trail.store is stores["audit"]
    assert bootstrap.tenant_gating.store is stores["tenant_gating"]
    assert bootstrap.tenant_gating.allow_unknown_tenants is True
    assert bootstrap.jwt_authenticator is None
    assert bootstrap.shell_policy is local_policy


def test_bootstrap_governance_runtime_builds_jwt_authenticator() -> None:
    captured = {}

    class Config:
        def __init__(self, **kwargs):
            captured["config"] = kwargs

    class Authenticator:
        def __init__(self, config):
            self.config = config

    bootstrap = server_platform.bootstrap_governance_runtime(
        env="production",
        runtime_env={
            "MULLU_JWT_SECRET": "c2VjcmV0",
            "MULLU_JWT_ISSUER": "issuer-a",
            "MULLU_JWT_AUDIENCE": "aud-a",
            "MULLU_JWT_TENANT_CLAIM": "tenant",
        },
        db_backend="postgresql",
        clock=lambda: "2026-01-01T00:00:00Z",
        field_encryptor=None,
        allow_unknown_tenants=False,
        create_governance_stores_fn=lambda **kwargs: {
            "budget": object(),
            "rate_limit": object(),
            "audit": object(),
            "tenant_gating": object(),
        },
        tenant_budget_manager_cls=lambda **kwargs: object(),
        governance_metrics_engine_cls=lambda **kwargs: object(),
        rate_limiter_cls=lambda **kwargs: object(),
        rate_limit_config_cls=lambda **kwargs: object(),
        audit_trail_cls=lambda **kwargs: object(),
        tenant_gating_registry_cls=lambda **kwargs: object(),
        sandboxed_policy=object(),
        local_dev_policy=object(),
        pilot_prod_policy=object(),
        jwt_authenticator_cls=Authenticator,
        oidc_config_cls=Config,
    )

    assert isinstance(bootstrap.jwt_authenticator, Authenticator)
    assert captured["config"]["issuer"] == "issuer-a"
    assert captured["config"]["audience"] == "aud-a"
    assert captured["config"]["signing_key"] == b"secret"
    assert captured["config"]["tenant_claim"] == "tenant"


def test_bootstrap_agent_runtime_registers_default_agents_and_health_probes() -> None:
    class FakeRegistry:
        def __init__(self):
            self.registered = []

        def register(self, descriptor):
            self.registered.append(descriptor)

        @property
        def count(self):
            return len(self.registered)

    class FakeTaskManager:
        def __init__(self, *, clock, registry):
            self.clock = clock
            self.registry = registry
            self.task_count = 0

    class FakeWebhookManager:
        def __init__(self, *, clock):
            self.clock = clock

    class FakeDeepHealth:
        def __init__(self, *, clock):
            self.clock = clock
            self.probes = {}

        def register(self, name, probe):
            self.probes[name] = probe

    class FakeConfigManager:
        def __init__(self, *, clock, initial):
            self.clock = clock
            self.initial = initial

    class FakeWorkflowEngine:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        def summary(self):
            return {"tasks": 0}

    class FakeObservability:
        def __init__(self, *, clock):
            self.clock = clock
            self.sources = {}

        def register_source(self, name, source):
            self.sources[name] = source

    class FakeDescriptor:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)

    store = type("Store", (), {"ledger_count": lambda self: 7})()
    llm_bridge = type(
        "Bridge",
        (),
        {
            "invocation_count": 3,
            "budget_summary": lambda self: {"spent": 1.5},
            "complete": lambda self, prompt, budget_id: {"text": prompt, "budget_id": budget_id},
        },
    )()
    cert_daemon = type("Daemon", (), {"status": lambda self: {"runs": 2}})()
    metrics = type("Metrics", (), {"KNOWN_COUNTERS": ("a", "b")})()
    audit_trail = type("Audit", (), {"summary": lambda self: {"count": 4}})()
    tenant_budget_mgr = type(
        "Budget",
        (),
        {"tenant_count": lambda self: 2, "total_spent": lambda self: 9.0},
    )()
    tenant_gating = type("Gating", (), {"summary": lambda self: {"registered": 2}})()
    pii_scanner = type("PII", (), {"enabled": True, "pattern_count": 5})()
    content_safety_chain = type(
        "Safety",
        (),
        {"filter_count": 3, "filter_names": lambda self: ["a", "b", "c"]},
    )()
    proof_bridge = type("Proof", (), {"summary": lambda self: {"proofs": 1}})()
    rate_limiter = type("Limiter", (), {"status": lambda self: {"allowed": 10}})()
    shell_policy = type("Policy", (), {"policy_id": "shell-local-dev", "allowed_executables": ("python", "echo")})()

    bootstrap = server_agents.bootstrap_agent_runtime(
        clock=lambda: "2026-01-01T00:00:00Z",
        store=store,
        llm_bridge=llm_bridge,
        cert_daemon=cert_daemon,
        metrics=metrics,
        default_model="stub",
        audit_trail=audit_trail,
        tenant_budget_mgr=tenant_budget_mgr,
        tenant_gating=tenant_gating,
        pii_scanner=pii_scanner,
        content_safety_chain=content_safety_chain,
        proof_bridge=proof_bridge,
        rate_limiter=rate_limiter,
        shell_policy=shell_policy,
        agent_registry_cls=FakeRegistry,
        task_manager_cls=FakeTaskManager,
        webhook_manager_cls=FakeWebhookManager,
        deep_health_checker_cls=FakeDeepHealth,
        config_manager_cls=FakeConfigManager,
        workflow_engine_cls=FakeWorkflowEngine,
        observability_aggregator_cls=FakeObservability,
        agent_descriptor_cls=FakeDescriptor,
    )

    assert [descriptor.agent_id for descriptor in bootstrap.agent_registry.registered] == [
        "llm-agent",
        "code-agent",
    ]
    assert bootstrap.task_manager.registry is bootstrap.agent_registry
    assert set(bootstrap.deep_health.probes) == {"store", "llm", "certification", "metrics"}
    assert bootstrap.deep_health.probes["store"]() == {"status": "healthy", "ledger_count": 7}
    assert bootstrap.config_manager.initial["llm"]["default_model"] == "stub"


def test_bootstrap_agent_runtime_wires_workflow_and_observability_sources() -> None:
    class FakeWorkflowEngine:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        def summary(self):
            return {"workflow_count": 1}

    class FakeObservability:
        def __init__(self, *, clock):
            self.sources = {}

        def register_source(self, name, source):
            self.sources[name] = source

    bootstrap = server_agents.bootstrap_agent_runtime(
        clock=lambda: "2026-01-01T00:00:00Z",
        store=type("Store", (), {"ledger_count": lambda self: 1})(),
        llm_bridge=type(
            "Bridge",
            (),
            {
                "invocation_count": 1,
                "budget_summary": lambda self: {"spent": 2.0},
                "complete": lambda self, prompt, budget_id: {"prompt": prompt, "budget_id": budget_id},
            },
        )(),
        cert_daemon=type("Daemon", (), {"status": lambda self: {"runs": 1}})(),
        metrics=type("Metrics", (), {"KNOWN_COUNTERS": ("x",)})(),
        default_model="governed-model",
        audit_trail=type("Audit", (), {"summary": lambda self: {"count": 1}})(),
        tenant_budget_mgr=type("Budget", (), {"tenant_count": lambda self: 3, "total_spent": lambda self: 6.5})(),
        tenant_gating=type("Gating", (), {"summary": lambda self: {"registered": 3}})(),
        pii_scanner=type("PII", (), {"enabled": False, "pattern_count": 2})(),
        content_safety_chain=type("Safety", (), {"filter_count": 4, "filter_names": lambda self: ["f1"]})(),
        proof_bridge=type("Proof", (), {"summary": lambda self: {"proofs": 2}})(),
        rate_limiter=type("Limiter", (), {"status": lambda self: {"allowed": 8}})(),
        shell_policy=type("Policy", (), {"policy_id": "shell-sandboxed", "allowed_executables": ("echo",)})(),
        workflow_engine_cls=FakeWorkflowEngine,
        observability_aggregator_cls=FakeObservability,
    )

    workflow = bootstrap.workflow_engine
    llm_complete = workflow.kwargs["llm_complete_fn"]
    assert workflow.kwargs["task_manager"] is bootstrap.task_manager
    assert workflow.kwargs["webhook_manager"] is bootstrap.webhook_manager
    assert llm_complete("hello", "budget-a") == {"prompt": "hello", "budget_id": "budget-a"}

    sources = bootstrap.observability.sources
    assert set(sources) == {
        "health",
        "llm",
        "tenants",
        "agents",
        "audit",
        "certification",
        "workflows",
        "tenant_gating",
        "pii_scanner",
        "content_safety",
        "proof_bridge",
        "rate_limiter",
        "shell_policy",
    }
    assert sources["shell_policy"]() == {
        "policy_id": "shell-sandboxed",
        "allowed": ["echo"],
    }
    assert sources["workflows"]() == {"workflow_count": 1}


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
