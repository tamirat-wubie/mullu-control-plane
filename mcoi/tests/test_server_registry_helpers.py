"""Purpose: verify registry helper contracts for the governed server.
Governance scope: registry helper validation tests only.
Dependencies: server registry helpers.
Invariants: registry composition remains deterministic and auditable.
"""

from __future__ import annotations

from types import SimpleNamespace

from mcoi_runtime.app import server_registry


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
