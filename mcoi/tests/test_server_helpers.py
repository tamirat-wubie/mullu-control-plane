"""Purpose: verify registry and runtime helper contracts for the governed server.
Governance scope: helper validation tests only.
Dependencies: server registry and runtime helpers with pytest support.
Invariants: helper composition remains deterministic and auditable.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from mcoi_runtime.app import server_registry
from mcoi_runtime.app import server_runtime
from mcoi_runtime.app import server_runtime_stack
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
