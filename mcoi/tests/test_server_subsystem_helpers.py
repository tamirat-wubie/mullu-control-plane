"""Purpose: verify subsystem helper contracts for the governed server.
Governance scope: service helper validation tests only.
Dependencies: server subsystem helpers.
Invariants: subsystem wiring remains deterministic and auditable.
"""

from __future__ import annotations

from mcoi_runtime.app import server_subsystems


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

    class FakeDataGovernance:
        def __init__(self, spine):
            self.spine = spine
            self.record_count = 1
            self.policy_count = 2
            self.residency_constraint_count = 3
            self.privacy_rule_count = 4
            self.redaction_rule_count = 5
            self.retention_rule_count = 6
            self.decision_count = 7
            self.violation_count = 8

        def state_hash(self):
            return "data-hash"

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
        data_governance_engine_cls=FakeDataGovernance,
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
        data_governance_engine_cls=lambda spine: type(
            "DataGov",
            (),
            {
                "record_count": 1,
                "policy_count": 2,
                "residency_constraint_count": 3,
                "privacy_rule_count": 4,
                "redaction_rule_count": 5,
                "retention_rule_count": 6,
                "decision_count": 7,
                "violation_count": 8,
                "state_hash": lambda self: "data-hash",
            },
        )(),
        temporal_runtime_engine_cls=lambda spine, clock: type(
            "TemporalRuntime",
            (),
            {
                "event_count": 9,
                "interval_count": 10,
                "constraint_count": 11,
                "action_decision_count": 12,
                "violation_count": 13,
            },
        )(),
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
        "data_governance",
        "temporal_runtime",
        "event_bus",
        "pipelines",
    }
    assert sources["rbac"]() == {
        "identities": 1,
        "roles": 2,
        "bindings": 3,
        "rules_seeded": 4,
    }
    assert sources["data_governance"]() == {
        "records": 1,
        "policies": 2,
        "residency_constraints": 3,
        "privacy_rules": 4,
        "redaction_rules": 5,
        "retention_rules": 6,
        "decisions": 7,
        "violations": 8,
        "state_hash": "data-hash",
    }
    assert sources["temporal_runtime"]() == {
        "events": 9,
        "intervals": 10,
        "constraints": 11,
        "action_decisions": 12,
        "violations": 13,
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
