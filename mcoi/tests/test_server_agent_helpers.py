"""Purpose: verify agent helper contracts for the governed server.
Governance scope: service helper validation tests only.
Dependencies: server agent helpers.
Invariants: agent wiring remains deterministic and auditable.
"""

from __future__ import annotations

from mcoi_runtime.app import server_agents


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
    shell_policy = type(
        "Policy",
        (),
        {"policy_id": "shell-local-dev", "allowed_executables": ("python", "echo")},
    )()

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
        tenant_budget_mgr=type(
            "Budget",
            (),
            {"tenant_count": lambda self: 3, "total_spent": lambda self: 6.5},
        )(),
        tenant_gating=type("Gating", (), {"summary": lambda self: {"registered": 3}})(),
        pii_scanner=type("PII", (), {"enabled": False, "pattern_count": 2})(),
        content_safety_chain=type(
            "Safety",
            (),
            {"filter_count": 4, "filter_names": lambda self: ["f1"]},
        )(),
        proof_bridge=type("Proof", (), {"summary": lambda self: {"proofs": 2}})(),
        rate_limiter=type("Limiter", (), {"status": lambda self: {"allowed": 8}})(),
        shell_policy=type(
            "Policy",
            (),
            {"policy_id": "shell-sandboxed", "allowed_executables": ("echo",)},
        )(),
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
