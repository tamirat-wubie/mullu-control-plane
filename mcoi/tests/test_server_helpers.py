"""Purpose: verify service, registry, and runtime helper contracts for the governed server.
Governance scope: helper validation tests only.
Dependencies: server service and runtime helpers with pytest support.
Invariants: helper composition remains deterministic and auditable.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from mcoi_runtime.app import server_agents
from mcoi_runtime.app import server_capabilities
from mcoi_runtime.app import server_registry
from mcoi_runtime.app import server_runtime
from mcoi_runtime.app import server_runtime_stack
from mcoi_runtime.app import server_services
from mcoi_runtime.app import server_subsystems
from mcoi_runtime.core.plugin_system import HookPoint
from mcoi_runtime.core.structured_output import StructuredOutputEngine
from mcoi_runtime.core.tool_use import ToolRegistry


def _server_registry_kwargs() -> dict[str, object]:
    llm_bridge = object()
    return {
        "deps_container": object(),
        "clock": lambda: "2026-01-01T00:00:00Z",
        "env": "test",
        "surface": object(),
        "store": object(),
        "llm_bootstrap_result": SimpleNamespace(bridge=llm_bridge),
        "streaming_adapter": object(),
        "proof_bridge": object(),
        "pii_scanner": object(),
        "content_safety_chain": object(),
        "field_encryption_bootstrap": {"enabled": True, "warning": "field warning"},
        "tenant_ledger": object(),
        "certifier": object(),
        "cert_daemon": object(),
        "governance_bootstrap": SimpleNamespace(
            tenant_budget_mgr=object(),
            metrics=object(),
            rate_limiter=object(),
            audit_trail=object(),
            tenant_gating=object(),
        ),
        "agent_bootstrap": SimpleNamespace(
            agent_registry=object(),
            task_manager=object(),
            webhook_manager=object(),
            deep_health=object(),
            config_manager=object(),
            workflow_engine=object(),
            observability=object(),
        ),
        "subsystem_bootstrap": SimpleNamespace(
            coordination_store=object(),
            coordination_engine=object(),
            scheduler=object(),
            connector_framework=object(),
            access_runtime=object(),
            policy_sandbox=object(),
            runbook_learning=object(),
            explanation_engine=object(),
            audit_anchor=object(),
            knowledge_graph=object(),
            event_bus=object(),
            batch_pipeline=object(),
        ),
        "operational_bootstrap": SimpleNamespace(
            guard_chain=object(),
            replay_recorder=object(),
            traced_workflow=object(),
            conversation_store=object(),
            schema_validator=object(),
            prompt_engine=object(),
            cost_analytics=object(),
            chat_workflow=object(),
            health_agg=object(),
            api_versions=object(),
            grafana_dashboard=object(),
            request_tracer=object(),
            agent_orchestrator=object(),
            rate_limit_headers=object(),
            webhook_retry=object(),
            config_watcher=object(),
            platform_logger=object(),
            plugin_registry=object(),
            api_key_mgr=object(),
            data_export=object(),
            sla_monitor=object(),
            notification_dispatcher=object(),
            tenant_isolation=object(),
            input_validator=object(),
            prom_exporter=object(),
            health_agg_v2=object(),
            idempotency_store=object(),
            response_compressor=object(),
            canary_controller=object(),
            secret_rotation=object(),
            request_dedup=object(),
            snapshot_mgr=object(),
            otel_exporter=object(),
            circuit_dashboard=object(),
            tenant_quota=object(),
            deploy_checker=object(),
            api_migration=object(),
            retry_engine=object(),
            region_router=object(),
            config_drift=object(),
            request_ctx_factory=object(),
            tenant_partitions=object(),
            health_v3=object(),
        ),
        "capability_bootstrap": SimpleNamespace(
            tool_registry=object(),
            structured_output=object(),
            state_persistence=object(),
            llm_circuit=object(),
            tool_agent=object(),
            model_router=object(),
            correlation_mgr=object(),
            shutdown_mgr=object(),
            agent_chain=object(),
            monitor=object(),
            task_queue=object(),
            agent_memory=object(),
            ab_engine=object(),
            isolation_verifier=object(),
            usage_reporter=object(),
            dep_graph=object(),
            backpressure=object(),
            governed_cache=object(),
            feature_flags=object(),
            semantic_search=object(),
            tenant_analytics=object(),
            wf_templates=object(),
            event_store=object(),
        ),
    }


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


def test_bootstrap_subsystems_wires_coordination_and_governed_services() -> None:
    class FakeObservability:
        def __init__(self):
            self.sources = {}

        def register_source(self, name, source):
            self.sources[name] = source

    class FakeDeepHealth:
        def __init__(self):
            self.probes = {}

        def register(self, name, probe):
            self.probes[name] = probe

    class FakeCoordinationStore:
        def __init__(self, base):
            self.base = base

    class FakeCoordinationEngine:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        def summary(self):
            return {"coordination": True}

    class FakeScheduler:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        def summary(self):
            return {"scheduler": True}

    class FakeConnectorFramework:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        def summary(self):
            return {"connectors": True}

    class FakeSpine:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    class FakeAccessRuntime:
        def __init__(self, spine):
            self.spine = spine
            self.identity_count = 2
            self.role_count = 3
            self.binding_count = 4

    class FakePolicySandbox:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        def summary(self):
            return {"simulation": True}

    class FakeRunbookLearning:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        def summary(self):
            return {"runbooks": True}

    class FakeExplanationEngine:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        def summary(self):
            return {"explanations": True}

    class FakeAuditAnchor:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        def summary(self):
            return {"anchors": 1}

    class FakeKnowledgeGraph:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        def summary(self):
            return {"knowledge": 1}

    class FakeEventBus:
        def __init__(self, **kwargs):
            self.kwargs = kwargs
            self.event_count = 7
            self.error_count = 1

        def summary(self):
            return {"events": self.event_count}

    class FakeBatchPipeline:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        def summary(self):
            return {"pipelines": 1}

    observability = FakeObservability()
    deep_health = FakeDeepHealth()
    llm_bridge = type(
        "Bridge",
        (),
        {"complete": lambda self, prompt, **kwargs: {"prompt": prompt, **kwargs}},
    )()

    bootstrap = server_subsystems.bootstrap_subsystems(
        clock=lambda: "2026-01-01T00:00:00Z",
        runtime_env={"MULLU_DATA_DIR": "C:\\data"},
        llm_bridge=llm_bridge,
        audit_trail=object(),
        observability=observability,
        deep_health=deep_health,
        coordination_store_cls=FakeCoordinationStore,
        coordination_engine_cls=FakeCoordinationEngine,
        governed_scheduler_cls=FakeScheduler,
        connector_framework_cls=FakeConnectorFramework,
        event_spine_engine_cls=FakeSpine,
        access_runtime_engine_cls=FakeAccessRuntime,
        seed_default_permissions_fn=lambda runtime: 9,
        policy_sandbox_cls=FakePolicySandbox,
        runbook_learning_engine_cls=FakeRunbookLearning,
        explanation_engine_cls=FakeExplanationEngine,
        audit_anchor_store_cls=FakeAuditAnchor,
        knowledge_graph_cls=FakeKnowledgeGraph,
        event_bus_cls=FakeEventBus,
        batch_pipeline_cls=FakeBatchPipeline,
        tempdir_getter=lambda: "C:\\temp",
    )

    assert str(bootstrap.coordination_store.base).replace("\\", "/").endswith(
        "C:/data/mullu-coordination"
    )
    assert bootstrap.coordination_engine.kwargs["policy_pack_id"] == "default"
    assert bootstrap.scheduler.kwargs["guard_chain"] is None
    assert bootstrap.scheduler.kwargs["audit_trail"] is None
    assert bootstrap.connector_framework.kwargs["guard_chain"] is None
    assert bootstrap.connector_framework.kwargs["audit_trail"] is None
    assert bootstrap.policy_sandbox.kwargs["guard_chain"] is None
    assert bootstrap.explanation_engine.kwargs["guard_chain"] is None
    assert bootstrap.explanation_engine.kwargs["audit_trail"] is None
    assert bootstrap.rbac_rules_seeded == 9


def test_bootstrap_subsystems_registers_observability_and_event_bus_health() -> None:
    class FakeObservability:
        def __init__(self):
            self.sources = {}

        def register_source(self, name, source):
            self.sources[name] = source

    class FakeDeepHealth:
        def __init__(self):
            self.probes = {}

        def register(self, name, probe):
            self.probes[name] = probe

    observability = FakeObservability()
    deep_health = FakeDeepHealth()

    bootstrap = server_subsystems.bootstrap_subsystems(
        clock=lambda: "2026-01-01T00:00:00Z",
        runtime_env={"MULLU_COORDINATION_DIR": "C:\\coord"},
        llm_bridge=type(
            "Bridge",
            (),
            {"complete": lambda self, prompt, **kwargs: {"prompt": prompt, **kwargs}},
        )(),
        audit_trail=object(),
        observability=observability,
        deep_health=deep_health,
        coordination_store_cls=lambda base: type("Store", (), {"base": base})(),
        coordination_engine_cls=lambda **kwargs: type("Coord", (), {"summary": lambda self: {"coord": 1}})(),
        governed_scheduler_cls=lambda **kwargs: type("Sched", (), {"summary": lambda self: {"sched": 1}})(),
        connector_framework_cls=lambda **kwargs: type("Conn", (), {"summary": lambda self: {"conn": 1}})(),
        event_spine_engine_cls=lambda **kwargs: object(),
        access_runtime_engine_cls=lambda spine: type(
            "Access",
            (),
            {"identity_count": 1, "role_count": 2, "binding_count": 3},
        )(),
        seed_default_permissions_fn=lambda runtime: 4,
        policy_sandbox_cls=lambda **kwargs: type("Sandbox", (), {"summary": lambda self: {"sim": 1}})(),
        runbook_learning_engine_cls=lambda **kwargs: type("Runbook", (), {"summary": lambda self: {"run": 1}})(),
        explanation_engine_cls=lambda **kwargs: type("Explain", (), {"summary": lambda self: {"exp": 1}})(),
        audit_anchor_store_cls=lambda **kwargs: type("Anchor", (), {"summary": lambda self: {"anchor": 1}})(),
        knowledge_graph_cls=lambda **kwargs: type("Graph", (), {"summary": lambda self: {"kg": 1}})(),
        event_bus_cls=lambda **kwargs: type(
            "Bus",
            (),
            {"event_count": 5, "error_count": 0, "summary": lambda self: {"events": 5}},
        )(),
        batch_pipeline_cls=lambda **kwargs: type(
            "Pipeline",
            (),
            {"kwargs": kwargs, "summary": lambda self: {"pipes": 1}},
        )(),
    )

    sources = observability.sources
    assert set(sources) == {
        "coordination",
        "scheduler",
        "connectors",
        "rbac",
        "simulation",
        "runbooks",
        "explanations",
        "audit_anchors",
        "knowledge",
        "event_bus",
        "pipelines",
    }
    assert sources["rbac"]() == {
        "identities": 1,
        "roles": 2,
        "bindings": 3,
        "rules_seeded": 4,
    }
    assert deep_health.probes["event_bus"]() == {
        "status": "healthy",
        "events": 5,
        "errors": 0,
    }
    assert bootstrap.batch_pipeline.kwargs["llm_complete_fn"]("hello", budget_id="b1") == {
        "prompt": "hello",
        "budget_id": "b1",
    }


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


def test_bootstrap_dependency_registry_preserves_platform_and_runtime_wiring() -> None:
    captured: dict[str, object] = {}

    class FakePlatform:
        def __init__(self, **kwargs) -> None:
            self.kwargs = kwargs

    def fake_wire_runtime_dependencies_fn(**kwargs) -> None:
        captured["wire_kwargs"] = kwargs

    def fake_register_dependency_groups_fn(_deps, *groups) -> None:
        captured["groups"] = groups

    bootstrap = server_registry.bootstrap_dependency_registry(
        **_server_registry_kwargs(),
        platform_cls=FakePlatform,
        wire_runtime_dependencies_fn=fake_wire_runtime_dependencies_fn,
        register_dependency_groups_fn=fake_register_dependency_groups_fn,
    )

    assert bootstrap.platform.kwargs["bootstrap_warnings"] == ("field warning",)
    assert bootstrap.platform.kwargs["bootstrap_components"]["field_encryption"] is True
    assert bootstrap.platform.kwargs["llm_bridge"] is not None
    assert captured["wire_kwargs"]["guard_chain"] is not None
    assert captured["wire_kwargs"]["scheduler"] is not None
    assert captured["wire_kwargs"]["connector_framework"] is not None
    assert captured["wire_kwargs"]["policy_sandbox"] is not None
    assert captured["wire_kwargs"]["explanation_engine"] is not None


def test_bootstrap_dependency_registry_registers_expected_dependency_keys() -> None:
    captured: dict[str, object] = {}
    registry_kwargs = _server_registry_kwargs()
    deps_container = registry_kwargs["deps_container"]

    class FakePlatform:
        def __init__(self, **kwargs) -> None:
            self.kwargs = kwargs

    def fake_register_dependency_groups_fn(container, *groups) -> None:
        captured["container"] = container
        captured["groups"] = groups

    bootstrap = server_registry.bootstrap_dependency_registry(
        **registry_kwargs,
        platform_cls=FakePlatform,
        wire_runtime_dependencies_fn=lambda **kwargs: None,
        register_dependency_groups_fn=fake_register_dependency_groups_fn,
    )

    group_keys = {key for group in captured["groups"] for key in group}

    assert captured["container"] is deps_container
    assert len(captured["groups"]) == 10
    assert "surface" in group_keys
    assert "store" in group_keys
    assert "platform" in group_keys
    assert "tool_registry" in group_keys
    assert "event_bus" in group_keys
    assert "shutdown_mgr" in group_keys
    assert "request_ctx_factory" in group_keys
    assert "governed_cache" in group_keys
    assert "feature_flags" in group_keys
    assert "dep_graph" in group_keys
    assert "backpressure" in group_keys
    assert (
        bootstrap.platform.kwargs["tenant_gating"]
        is registry_kwargs["governance_bootstrap"].tenant_gating
    )


def test_build_default_input_validator_registers_expected_schemas() -> None:
    validator = server_runtime.build_default_input_validator()

    assert validator.schema_count == 3
    assert validator.validate("api_request", {"tenant_id": "tenant-a"}).valid is True
    assert validator.validate("completion", {"prompt": "x", "max_tokens": 1, "temperature": 0.0}).valid is True


def test_bootstrap_server_runtime_stack_preserves_order_and_exported_bindings() -> None:
    captured: dict[str, object] = {}
    observability = object()
    access_runtime = object()
    guard_chain = object()
    shutdown_mgr = object()
    state_persistence = object()

    agent_bootstrap = SimpleNamespace(
        observability=observability,
        deep_health=object(),
        workflow_engine=object(),
    )
    subsystem_bootstrap = SimpleNamespace(
        event_bus=object(),
        access_runtime=access_runtime,
    )
    operational_bootstrap = SimpleNamespace(
        guard_chain=guard_chain,
    )
    capability_bootstrap = SimpleNamespace(
        shutdown_mgr=shutdown_mgr,
        state_persistence=state_persistence,
    )

    def fake_bootstrap_agent_runtime_fn(**kwargs):
        captured["agent_kwargs"] = kwargs
        return agent_bootstrap

    def fake_bootstrap_subsystems_fn(**kwargs):
        captured["subsystem_kwargs"] = kwargs
        return subsystem_bootstrap

    def fake_bootstrap_operational_services_fn(**kwargs):
        captured["operational_kwargs"] = kwargs
        return operational_bootstrap

    def fake_bootstrap_capability_services_fn(**kwargs):
        captured["capability_kwargs"] = kwargs
        return capability_bootstrap

    bootstrap = server_runtime_stack.bootstrap_server_runtime_stack(
        clock=lambda: "2026-01-01T00:00:00Z",
        env="test",
        runtime_env={"MULLU_ENV": "test"},
        store=object(),
        llm_bridge=object(),
        cert_daemon=object(),
        metrics=object(),
        default_model="stub",
        audit_trail=object(),
        tenant_budget_mgr=object(),
        tenant_gating=object(),
        pii_scanner=object(),
        content_safety_chain=object(),
        proof_bridge=object(),
        rate_limiter=object(),
        shell_policy=object(),
        jwt_authenticator=object(),
        evaluate_expression_fn=lambda value: value,
        bootstrap_agent_runtime_fn=fake_bootstrap_agent_runtime_fn,
        bootstrap_subsystems_fn=fake_bootstrap_subsystems_fn,
        bootstrap_operational_services_fn=fake_bootstrap_operational_services_fn,
        bootstrap_capability_services_fn=fake_bootstrap_capability_services_fn,
    )

    assert captured["subsystem_kwargs"]["observability"] is observability
    assert captured["subsystem_kwargs"]["deep_health"] is agent_bootstrap.deep_health
    assert captured["operational_kwargs"]["workflow_engine"] is agent_bootstrap.workflow_engine
    assert captured["operational_kwargs"]["event_bus"] is subsystem_bootstrap.event_bus
    assert captured["operational_kwargs"]["access_runtime"] is access_runtime
    assert captured["capability_kwargs"]["observability"] is observability
    assert bootstrap.observability is observability
    assert bootstrap.access_runtime is access_runtime
    assert bootstrap.guard_chain is guard_chain
    assert bootstrap.shutdown_mgr is shutdown_mgr
    assert bootstrap.state_persistence is state_persistence


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
