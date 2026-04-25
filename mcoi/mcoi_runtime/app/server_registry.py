"""Dependency registry bootstrap helpers for the governed HTTP server.

Purpose: isolate platform construction and dependency group registration from
the main server module.
Governance scope: [OCE, CDCV, CQTE, UWMA]
Dependencies: governed session platform, dependency wiring, and dependency
group registration helpers.
Invariants:
  - Platform bootstrap warnings remain bounded and deterministic.
  - Runtime dependency wiring keeps the same scheduler, connector, sandbox,
    and explanation bindings.
  - Dependency group keys remain stable for router resolution.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping

from mcoi_runtime.app.server_deps import (
    register_dependency_groups,
    wire_runtime_dependencies,
)
from mcoi_runtime.core.governed_session import Platform as GovernedPlatform
from mcoi_runtime.core.policy_versioning import PolicyVersionRegistry


@dataclass(frozen=True)
class DependencyRegistryBootstrap:
    """Dependency registry bootstrap result."""

    platform: Any


def bootstrap_dependency_registry(
    *,
    deps_container: Any,
    clock: Callable[[], str],
    env: str,
    surface: Any,
    store: Any,
    llm_bootstrap_result: Any,
    streaming_adapter: Any,
    proof_bridge: Any,
    pii_scanner: Any,
    content_safety_chain: Any,
    field_encryption_bootstrap: Mapping[str, Any],
    tenant_ledger: Any,
    certifier: Any,
    cert_daemon: Any,
    governance_bootstrap: Any,
    agent_bootstrap: Any,
    subsystem_bootstrap: Any,
    operational_bootstrap: Any,
    capability_bootstrap: Any,
    platform_cls: type[Any] = GovernedPlatform,
    policy_version_registry_cls: type[Any] = PolicyVersionRegistry,
    wire_runtime_dependencies_fn: Callable[..., Any] = wire_runtime_dependencies,
    register_dependency_groups_fn: Callable[..., Any] = register_dependency_groups,
) -> DependencyRegistryBootstrap:
    """Build the platform harness and register dependency groups."""
    llm_bridge = llm_bootstrap_result.bridge
    tenant_budget_mgr = governance_bootstrap.tenant_budget_mgr
    metrics = governance_bootstrap.metrics
    rate_limiter = governance_bootstrap.rate_limiter
    audit_trail = governance_bootstrap.audit_trail
    tenant_gating = governance_bootstrap.tenant_gating
    agent_registry = agent_bootstrap.agent_registry
    task_manager = agent_bootstrap.task_manager
    webhook_manager = agent_bootstrap.webhook_manager
    deep_health = agent_bootstrap.deep_health
    config_manager = agent_bootstrap.config_manager
    workflow_engine = agent_bootstrap.workflow_engine
    observability = agent_bootstrap.observability
    coordination_store = subsystem_bootstrap.coordination_store
    coordination_engine = subsystem_bootstrap.coordination_engine
    scheduler = subsystem_bootstrap.scheduler
    connector_framework = subsystem_bootstrap.connector_framework
    access_runtime = subsystem_bootstrap.access_runtime
    policy_sandbox = subsystem_bootstrap.policy_sandbox
    runbook_learning = subsystem_bootstrap.runbook_learning
    explanation_engine = subsystem_bootstrap.explanation_engine
    audit_anchor = subsystem_bootstrap.audit_anchor
    knowledge_graph = subsystem_bootstrap.knowledge_graph
    data_governance = subsystem_bootstrap.data_governance
    event_bus = subsystem_bootstrap.event_bus
    batch_pipeline = subsystem_bootstrap.batch_pipeline
    guard_chain = operational_bootstrap.guard_chain
    replay_recorder = operational_bootstrap.replay_recorder
    traced_workflow = operational_bootstrap.traced_workflow
    conversation_store = operational_bootstrap.conversation_store
    schema_validator = operational_bootstrap.schema_validator
    prompt_engine = operational_bootstrap.prompt_engine
    cost_analytics = operational_bootstrap.cost_analytics
    chat_workflow = operational_bootstrap.chat_workflow
    health_agg = operational_bootstrap.health_agg
    api_versions = operational_bootstrap.api_versions
    grafana_dashboard = operational_bootstrap.grafana_dashboard
    request_tracer = operational_bootstrap.request_tracer
    agent_orchestrator = operational_bootstrap.agent_orchestrator
    rate_limit_headers = operational_bootstrap.rate_limit_headers
    webhook_retry = operational_bootstrap.webhook_retry
    config_watcher = operational_bootstrap.config_watcher
    platform_logger = operational_bootstrap.platform_logger
    plugin_registry = operational_bootstrap.plugin_registry
    api_key_mgr = operational_bootstrap.api_key_mgr
    data_export = operational_bootstrap.data_export
    sla_monitor = operational_bootstrap.sla_monitor
    notification_dispatcher = operational_bootstrap.notification_dispatcher
    tenant_isolation = operational_bootstrap.tenant_isolation
    input_validator = operational_bootstrap.input_validator
    prom_exporter = operational_bootstrap.prom_exporter
    health_agg_v2 = operational_bootstrap.health_agg_v2
    idempotency_store = operational_bootstrap.idempotency_store
    response_compressor = operational_bootstrap.response_compressor
    canary_controller = operational_bootstrap.canary_controller
    secret_rotation = operational_bootstrap.secret_rotation
    request_dedup = operational_bootstrap.request_dedup
    snapshot_mgr = operational_bootstrap.snapshot_mgr
    otel_exporter = operational_bootstrap.otel_exporter
    circuit_dashboard = operational_bootstrap.circuit_dashboard
    tenant_quota = operational_bootstrap.tenant_quota
    deploy_checker = operational_bootstrap.deploy_checker
    api_migration = operational_bootstrap.api_migration
    retry_engine = operational_bootstrap.retry_engine
    region_router = operational_bootstrap.region_router
    config_drift = operational_bootstrap.config_drift
    request_ctx_factory = operational_bootstrap.request_ctx_factory
    tenant_partitions = operational_bootstrap.tenant_partitions
    health_v3 = operational_bootstrap.health_v3
    tool_registry = capability_bootstrap.tool_registry
    structured_output = capability_bootstrap.structured_output
    state_persistence = capability_bootstrap.state_persistence
    llm_circuit = capability_bootstrap.llm_circuit
    tool_agent = capability_bootstrap.tool_agent
    model_router = capability_bootstrap.model_router
    correlation_mgr = capability_bootstrap.correlation_mgr
    shutdown_mgr = capability_bootstrap.shutdown_mgr
    agent_chain = capability_bootstrap.agent_chain
    monitor = capability_bootstrap.monitor
    task_queue = capability_bootstrap.task_queue
    agent_memory = capability_bootstrap.agent_memory
    ab_engine = capability_bootstrap.ab_engine
    isolation_verifier = capability_bootstrap.isolation_verifier
    usage_reporter = capability_bootstrap.usage_reporter
    dep_graph = capability_bootstrap.dep_graph
    backpressure = capability_bootstrap.backpressure
    governed_cache = capability_bootstrap.governed_cache
    feature_flags = capability_bootstrap.feature_flags
    semantic_search = capability_bootstrap.semantic_search
    tenant_analytics = capability_bootstrap.tenant_analytics
    wf_templates = capability_bootstrap.wf_templates
    event_store = capability_bootstrap.event_store
    policy_version_registry = policy_version_registry_cls()

    platform = platform_cls(
        clock=clock,
        access_runtime=access_runtime,
        content_safety_chain=content_safety_chain,
        pii_scanner=pii_scanner,
        budget_mgr=tenant_budget_mgr,
        llm_bridge=llm_bridge,
        audit_trail=audit_trail,
        proof_bridge=proof_bridge,
        tenant_gating=tenant_gating,
        rate_limiter=rate_limiter,
        bootstrap_warnings=tuple(
            warning
            for warning in (field_encryption_bootstrap.get("warning", ""),)
            if warning
        ),
        bootstrap_components={
            "access_runtime": access_runtime is not None,
            "llm_bridge": llm_bridge is not None,
            "tenant_gating": tenant_gating is not None,
            "proof_bridge": proof_bridge is not None,
            "field_encryption": bool(field_encryption_bootstrap.get("enabled", False)),
        },
    )

    wire_runtime_dependencies_fn(
        guard_chain=guard_chain,
        audit_trail=audit_trail,
        scheduler=scheduler,
        connector_framework=connector_framework,
        policy_sandbox=policy_sandbox,
        explanation_engine=explanation_engine,
    )

    register_dependency_groups_fn(
        deps_container,
        {
            "surface": surface,
            "store": store,
            "_clock": clock,
            "ENV": env,
        },
        {
            "llm_bridge": llm_bridge,
            "llm_bootstrap_result": llm_bootstrap_result,
            "llm_circuit": llm_circuit,
            "streaming_adapter": streaming_adapter,
            "model_router": model_router,
        },
        {
            "metrics": metrics,
            "rate_limiter": rate_limiter,
            "rate_limit_headers": rate_limit_headers,
            "guard_chain": guard_chain,
            "audit_trail": audit_trail,
            "input_validator": input_validator,
            "proof_bridge": proof_bridge,
            "pii_scanner": pii_scanner,
            "content_safety_chain": content_safety_chain,
            "tenant_gating": tenant_gating,
            "field_encryption_bootstrap": dict(field_encryption_bootstrap),
            "platform": platform,
        },
        {
            "tenant_budget_mgr": tenant_budget_mgr,
            "tenant_ledger": tenant_ledger,
            "tenant_isolation": tenant_isolation,
            "tenant_quota": tenant_quota,
            "tenant_partitions": tenant_partitions,
            "tenant_analytics": tenant_analytics,
            "usage_reporter": usage_reporter,
            "isolation_verifier": isolation_verifier,
        },
        {
            "agent_registry": agent_registry,
            "task_manager": task_manager,
            "workflow_engine": workflow_engine,
            "traced_workflow": traced_workflow,
            "replay_recorder": replay_recorder,
            "chat_workflow": chat_workflow,
            "agent_chain": agent_chain,
            "agent_orchestrator": agent_orchestrator,
            "coordination_engine": coordination_engine,
            "coordination_store": coordination_store,
            "scheduler": scheduler,
            "connector_framework": connector_framework,
            "access_runtime": access_runtime,
            "policy_sandbox": policy_sandbox,
            "policy_version_registry": policy_version_registry,
            "runbook_learning": runbook_learning,
            "explanation_engine": explanation_engine,
            "knowledge_graph": knowledge_graph,
            "audit_anchor": audit_anchor,
            "data_governance": data_governance,
            "tool_registry": tool_registry,
            "tool_agent": tool_agent,
            "agent_memory": agent_memory,
            "task_queue": task_queue,
            "batch_pipeline": batch_pipeline,
            "wf_templates": wf_templates,
            "semantic_search": semantic_search,
        },
        {
            "conversation_store": conversation_store,
            "prompt_engine": prompt_engine,
            "schema_validator": schema_validator,
        },
        {
            "state_persistence": state_persistence,
            "structured_output": structured_output,
            "cost_analytics": cost_analytics,
        },
        {
            "deep_health": deep_health,
            "health_agg": health_agg,
            "health_agg_v2": health_agg_v2,
            "health_v3": health_v3,
            "certifier": certifier,
            "cert_daemon": cert_daemon,
        },
        {
            "event_bus": event_bus,
            "event_store": event_store,
            "webhook_manager": webhook_manager,
            "webhook_retry": webhook_retry,
        },
        {
            "config_manager": config_manager,
            "config_watcher": config_watcher,
            "config_drift": config_drift,
            "observability": observability,
            "plugin_registry": plugin_registry,
            "api_versions": api_versions,
            "platform_logger": platform_logger,
            "api_key_mgr": api_key_mgr,
            "data_export": data_export,
            "sla_monitor": sla_monitor,
            "notification_dispatcher": notification_dispatcher,
            "prom_exporter": prom_exporter,
            "grafana_dashboard": grafana_dashboard,
            "request_tracer": request_tracer,
            "monitor": monitor,
            "shutdown_mgr": shutdown_mgr,
            "correlation_mgr": correlation_mgr,
            "idempotency_store": idempotency_store,
            "response_compressor": response_compressor,
            "canary_controller": canary_controller,
            "secret_rotation": secret_rotation,
            "request_dedup": request_dedup,
            "snapshot_mgr": snapshot_mgr,
            "otel_exporter": otel_exporter,
            "circuit_dashboard": circuit_dashboard,
            "deploy_checker": deploy_checker,
            "api_migration": api_migration,
            "retry_engine": retry_engine,
            "region_router": region_router,
            "request_ctx_factory": request_ctx_factory,
            "governed_cache": governed_cache,
            "feature_flags": feature_flags,
            "dep_graph": dep_graph,
            "backpressure": backpressure,
            "ab_engine": ab_engine,
        },
    )

    return DependencyRegistryBootstrap(platform=platform)
