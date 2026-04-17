"""Purpose: verify operational and capability helper contracts for the governed server.
Governance scope: service helper validation tests only.
Dependencies: server operational and capability helpers.
Invariants: service wiring remains deterministic and auditable.
"""

from __future__ import annotations

from mcoi_runtime.app import server_capabilities
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

    def fake_create_api_key_guard(manager, require_auth):
        return ("api-key-guard", require_auth, manager)

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
    assert bootstrap.guard_chain[1:] == ["budget-guard", "rate-guard"]
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
        create_api_key_guard_fn=lambda manager, require_auth: ("api-key", require_auth),
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


def test_bootstrap_capability_services_registers_tools_models_and_flags() -> None:
    class FakeObservability:
        def __init__(self) -> None:
            self.sources: dict[str, object] = {}

        def register_source(self, name, source) -> None:
            self.sources[name] = source

    class FakeBudgetManager:
        def get_budget(self, tenant_id: str):
            return {"tenant-a": object(), "tenant-b": object()}.get(tenant_id)

    bridge = type(
        "Bridge",
        (),
        {
            "invocation_count": 7,
            "total_cost": 1.25,
            "complete": lambda self, prompt, **kwargs: {"prompt": prompt, **kwargs},
        },
    )()
    observability = FakeObservability()

    bootstrap = server_capabilities.bootstrap_capability_services(
        clock=lambda: "2026-01-01T00:00:00Z",
        runtime_env={},
        llm_bridge=bridge,
        observability=observability,
        tenant_budget_mgr=FakeBudgetManager(),
        evaluate_expression_fn=lambda expression: 9 if expression == "4+5" else 0,
    )

    assert bootstrap.tool_registry.invoke("calculator", {"expression": "4+5"}).output == {
        "result": "9"
    }
    assert bootstrap.tool_registry.invoke("get_time", {}).output == {
        "time": "2026-01-01T00:00:00Z"
    }
    assert bootstrap.structured_output.summary()["schemas"] == 1
    assert bootstrap.model_router.summary()["models"] == 4
    assert bootstrap.feature_flags.summary() == {"total": 4, "enabled": 4, "disabled": 0}
    assert bootstrap.feature_flags.is_enabled("tool_augmentation") is True
    assert bootstrap.llm_circuit.status()["state"] == "closed"
    assert bootstrap.state_persistence.summary()["base_dir"]
    assert {"tools", "model_router", "agent_memory"}.issubset(observability.sources)


def test_bootstrap_capability_services_wires_usage_templates_and_isolation() -> None:
    class FakeObservability:
        def register_source(self, name, source) -> None:
            return None

    class FakeBudgetManager:
        def get_budget(self, tenant_id: str):
            if tenant_id == "tenant-a":
                return {"budget": 1}
            if tenant_id == "tenant-b":
                return {"budget": 2}
            return None

    bridge = type(
        "Bridge",
        (),
        {
            "invocation_count": 11,
            "total_cost": 4.5,
            "complete": lambda self, prompt, **kwargs: {"prompt": prompt, **kwargs},
        },
    )()

    bootstrap = server_capabilities.bootstrap_capability_services(
        clock=lambda: "2026-01-01T00:00:00Z",
        runtime_env={"MULLU_STATE_DIR": "C:\\state"},
        llm_bridge=bridge,
        observability=FakeObservability(),
        tenant_budget_mgr=FakeBudgetManager(),
        evaluate_expression_fn=lambda expression: 0,
    )

    isolation = bootstrap.isolation_verifier.verify("tenant-a", "tenant-b")
    usage = bootstrap.usage_reporter.generate("tenant-a")
    analytics = bootstrap.tenant_analytics.compute("tenant-a")
    templates = [template.template_id for template in bootstrap.wf_templates.list_templates()]

    assert isolation.all_isolated is True
    assert bootstrap.isolation_verifier.summary()["probes_registered"] == 3
    assert usage.llm_calls == 11
    assert usage.total_cost == 4.5
    assert analytics.llm_calls == 11
    assert analytics.total_cost == 4.5
    assert bootstrap.tenant_analytics.summary()["collectors"] == ["llm_calls", "total_cost"]
    assert templates == ["research-draft", "summarize-refine"]
    assert bootstrap.dep_graph.topological_sort()[-1] == "api"
    assert bootstrap.event_store.summary()["total_events"] == 0
