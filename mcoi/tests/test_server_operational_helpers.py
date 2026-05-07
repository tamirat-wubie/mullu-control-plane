"""Purpose: verify operational helper contracts for the governed server.
Governance scope: operational helper validation tests only.
Dependencies: server operational helpers and plugin hook points.
Invariants: operational service wiring remains deterministic and auditable.
"""

from __future__ import annotations

from mcoi_runtime.app import server_services
from mcoi_runtime.core.plugin_system import HookPoint


def test_bootstrap_operational_services_preserves_guard_order_and_sources() -> None:
    class FakeObservability:
        def __init__(self) -> None:
            self.sources: dict[str, object] = {}

        def register_source(self, name, source) -> None:
            self.sources[name] = source

    class FakeAuditTrail:
        def __init__(self) -> None:
            self.records: list[dict[str, object]] = []

        def record(self, **kwargs) -> None:
            self.records.append(kwargs)

        def recent(self, limit: int) -> list[dict[str, int]]:
            return [{"limit": limit}]

    class FakeMetrics:
        def __init__(self) -> None:
            self.calls: list[str] = []

        def inc(self, name: str) -> None:
            self.calls.append(name)

    class FakeCertDaemon:
        health = type("Health", (), {"is_healthy": True})()

        def status(self) -> dict[str, str]:
            return {"status": "ok"}

    class FakeWorkflowEngine:
        def summary(self) -> dict[str, int]:
            return {"workflows": 0}

    class FakeEventBus:
        error_count = 0

        def publish(self, *args, **kwargs) -> None:
            return None

    guard_calls: list[dict[str, object]] = []

    def fake_build_guard_chain(**kwargs):
        guard_calls.append(kwargs)
        return ["budget-guard", "rate-guard"]

    def fake_create_api_key_guard(manager, require_auth, allow_jwt_passthrough):
        return ("api-key-guard", require_auth, allow_jwt_passthrough, manager)

    observability = FakeObservability()
    bootstrap = server_services.bootstrap_operational_services(
        clock=lambda: "2026-01-01T00:00:00Z",
        env="production",
        runtime_env={},
        cert_daemon=FakeCertDaemon(),
        workflow_engine=FakeWorkflowEngine(),
        event_bus=FakeEventBus(),
        observability=observability,
        audit_trail=FakeAuditTrail(),
        metrics=FakeMetrics(),
        tenant_budget_mgr=object(),
        rate_limiter=object(),
        jwt_authenticator=object(),
        tenant_gating=object(),
        access_runtime=object(),
        content_safety_chain=object(),
        build_guard_chain_fn=fake_build_guard_chain,
        create_api_key_guard_fn=fake_create_api_key_guard,
        build_default_dashboard_fn=lambda: {"dashboard": True},
        build_default_input_validator_fn=lambda: "validator",
    )

    assert bootstrap.guard_chain[0][0] == "api-key-guard"
    assert bootstrap.guard_chain[0][1] is True
    assert bootstrap.guard_chain[0][2] is True
    assert bootstrap.guard_chain[1:] == ["budget-guard", "rate-guard"]
    assert bootstrap.api_key_mgr.allow_wildcard_keys is False
    assert guard_calls[0]["tenant_gating_registry"] is not None
    assert bootstrap.input_validator == "validator"
    assert bootstrap.grafana_dashboard == {"dashboard": True}
    assert {
        "replay",
        "cost_analytics",
        "chat_workflows",
        "tracing",
        "orchestration",
        "api_keys",
        "sla",
        "tenant_isolation",
        "snapshots",
        "quotas",
    }.issubset(observability.sources)


def test_bootstrap_operational_services_activates_plugins_and_budget_alerts() -> None:
    class FakeObservability:
        def register_source(self, name, source) -> None:
            return None

    class FakeAuditTrail:
        def __init__(self) -> None:
            self.records: list[dict[str, object]] = []

        def record(self, **kwargs) -> None:
            self.records.append(kwargs)

        def recent(self, limit: int) -> list[dict[str, int]]:
            return []

    class FakeMetrics:
        def __init__(self) -> None:
            self.calls: list[str] = []

        def inc(self, name: str) -> None:
            self.calls.append(name)

    class FakeCertDaemon:
        health = type("Health", (), {"is_healthy": True})()

        def status(self) -> dict[str, str]:
            return {"status": "ok"}

    class FakeWorkflowEngine:
        def summary(self) -> dict[str, int]:
            return {"workflows": 0}

    class FakeEventBus:
        def __init__(self) -> None:
            self.error_count = 0
            self.published: list[tuple[str, str, str, dict[str, object]]] = []

        def publish(self, event_name: str, tenant_id: str, source: str, payload) -> None:
            self.published.append((event_name, tenant_id, source, payload))

    audit_trail = FakeAuditTrail()
    metrics = FakeMetrics()
    event_bus = FakeEventBus()
    bootstrap = server_services.bootstrap_operational_services(
        clock=lambda: "2026-01-01T00:00:00Z",
        env="local_dev",
        runtime_env={"MULLU_API_AUTH_REQUIRED": "false"},
        cert_daemon=FakeCertDaemon(),
        workflow_engine=FakeWorkflowEngine(),
        event_bus=event_bus,
        observability=FakeObservability(),
        audit_trail=audit_trail,
        metrics=metrics,
        tenant_budget_mgr=object(),
        rate_limiter=object(),
        jwt_authenticator=object(),
        tenant_gating=object(),
        access_runtime=object(),
        content_safety_chain=object(),
        build_guard_chain_fn=lambda **kwargs: [],
        create_api_key_guard_fn=lambda manager, require_auth, allow_jwt_passthrough: (
            "api-key",
            require_auth,
            allow_jwt_passthrough,
        ),
    )

    dispatch_results = bootstrap.plugin_registry.dispatch_hook(
        HookPoint.POST_DISPATCH,
        tenant_id="tenant-a",
    )
    llm_results = bootstrap.plugin_registry.dispatch_hook(HookPoint.POST_LLM_CALL)
    alert_results = bootstrap.plugin_registry.dispatch_hook(
        HookPoint.ON_BUDGET_CHECK,
        tenant_id="tenant-a",
        utilization_pct=81,
    )

    assert bootstrap.plugin_registry.summary()["total"] == 2
    assert bootstrap.plugin_registry.summary()["active"] == 2
    assert dispatch_results == [None]
    assert llm_results == [None]
    assert alert_results == [None]
    assert audit_trail.records[0]["action"] == "plugin.log.dispatch"
    assert metrics.calls == ["llm_calls_total"]
    assert event_bus.published == [
        (
            "budget.warning",
            "tenant-a",
            "cost-alert-plugin",
            {"tenant_id": "tenant-a", "utilization_pct": 81},
        )
    ]


def test_bootstrap_operational_services_allows_wildcard_keys_in_local_dev() -> None:
    class FakeObservability:
        def register_source(self, name, source) -> None:
            return None

    bootstrap = server_services.bootstrap_operational_services(
        clock=lambda: "2026-01-01T00:00:00Z",
        env="local_dev",
        runtime_env={},
        cert_daemon=type("FakeCertDaemon", (), {"health": type("Health", (), {"is_healthy": True})(), "status": lambda self: {"status": "ok"}})(),
        workflow_engine=type("FakeWorkflowEngine", (), {"summary": lambda self: {"workflows": 0}})(),
        event_bus=type("FakeEventBus", (), {"error_count": 0, "publish": lambda self, *args, **kwargs: None})(),
        observability=FakeObservability(),
        audit_trail=type("FakeAuditTrail", (), {"record": lambda self, **kwargs: None, "recent": lambda self, limit: []})(),
        metrics=type("FakeMetrics", (), {"inc": lambda self, name: None})(),
        tenant_budget_mgr=object(),
        rate_limiter=object(),
        jwt_authenticator=None,
        tenant_gating=object(),
        access_runtime=object(),
        content_safety_chain=object(),
        build_guard_chain_fn=lambda **kwargs: [],
        create_api_key_guard_fn=lambda manager, require_auth, allow_jwt_passthrough: (
            "api-key",
            require_auth,
            allow_jwt_passthrough,
        ),
    )

    assert bootstrap.api_key_mgr.allow_wildcard_keys is True
