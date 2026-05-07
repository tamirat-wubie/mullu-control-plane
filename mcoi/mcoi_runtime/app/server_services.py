"""Operational service bootstrap helpers for the governed HTTP server.

Purpose: isolate mid-file operational service wiring from the main server
module.
Governance scope: [OCE, CDCV, CQTE, UWMA]
Dependencies: middleware guards, replay, schema, prompts, health, tracing,
quotas, migration, and platform operational services.
Invariants:
  - Logging and cost alert plugin activation stays deterministic.
  - API key guard insertion remains first in the guard chain.
  - Observability source names remain stable.
  - Default schema, prompt, health, retry, and migration registrations stay
    behavior-compatible with the server boundary.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping

from mcoi_runtime.app.middleware import build_guard_chain
from mcoi_runtime.app.server_policy import _env_flag
from mcoi_runtime.app.server_runtime import build_default_input_validator
from mcoi_runtime.governance.auth.api_key import APIKeyManager
from mcoi_runtime.core.api_migration import ApiMigrationEngine
from mcoi_runtime.core.api_version import APIVersionManager
from mcoi_runtime.core.agent_orchestration import AgentOrchestrator
from mcoi_runtime.core.canary_controller import CanaryController
from mcoi_runtime.core.chat_workflow import ChatWorkflowEngine
from mcoi_runtime.core.circuit_dashboard import CircuitDashboard
from mcoi_runtime.core.config_drift import ConfigDriftDetector
from mcoi_runtime.core.config_watcher import ConfigFileWatcher
from mcoi_runtime.core.conversation_memory import ConversationStore
from mcoi_runtime.core.cost_analytics import CostAnalyticsEngine
from mcoi_runtime.core.data_export import DataExportPipeline
from mcoi_runtime.core.deploy_readiness import (
    CheckResult,
    CheckStatus,
    DeployReadinessChecker,
)
from mcoi_runtime.core.execution_replay import ReplayRecorder
from mcoi_runtime.governance.guards.chain import create_api_key_guard
from mcoi_runtime.core.grafana_dashboard import build_default_dashboard
from mcoi_runtime.core.health_aggregator import HealthAggregator
from mcoi_runtime.core.health_check_agg import HealthCheckAggregator, HealthCheckDef
from mcoi_runtime.core.health_v3 import ComponentHealth, HealthAggregatorV3
from mcoi_runtime.core.idempotency import IdempotencyStore
from mcoi_runtime.core.notification_dispatcher import (
    NotificationChannel,
    NotificationDispatcher,
)
from mcoi_runtime.core.otel_exporter import OtelExporter
from mcoi_runtime.core.plugin_system import HookPoint, PluginDescriptor, PluginRegistry
from mcoi_runtime.core.prometheus_exporter import PrometheusExporter
from mcoi_runtime.core.prompt_template_engine import PromptTemplate, PromptTemplateEngine
from mcoi_runtime.core.rate_limit_headers import RateLimitHeaderProvider
from mcoi_runtime.core.region_router import RegionRouter, RoutingStrategy
from mcoi_runtime.core.request_context import RequestContextFactory
from mcoi_runtime.core.request_dedup import RequestDeduplicator
from mcoi_runtime.core.request_tracing import RequestTracer
from mcoi_runtime.core.response_compression import ResponseCompressor
from mcoi_runtime.core.retry_policy import RetryPolicyEngine
from mcoi_runtime.core.rollback_snapshot import SnapshotManager
from mcoi_runtime.core.schema_validator import SchemaDefinition, SchemaRule, SchemaValidator
from mcoi_runtime.core.secret_rotation import SecretRotationEngine
from mcoi_runtime.core.sla_monitor import SLAMetricType, SLAMonitor, SLATarget
from mcoi_runtime.core.structured_logging import LogLevel, StructuredLogger
from mcoi_runtime.core.tenant_isolation_audit import TenantIsolationAuditor
from mcoi_runtime.core.tenant_partition import TenantPartitionManager
from mcoi_runtime.core.tenant_quota import TenantQuotaEngine
from mcoi_runtime.core.traced_workflow import TracedWorkflowEngine
from mcoi_runtime.core.webhook_retry import RetryPolicy, WebhookRetryEngine


@dataclass(frozen=True)
class OperationalBootstrap:
    """Operational bootstrap result."""

    plugin_registry: Any
    guard_chain: Any
    replay_recorder: Any
    traced_workflow: Any
    conversation_store: Any
    schema_validator: Any
    prompt_engine: Any
    cost_analytics: Any
    chat_workflow: Any
    health_agg: Any
    api_versions: Any
    grafana_dashboard: Any
    request_tracer: Any
    agent_orchestrator: Any
    rate_limit_headers: Any
    webhook_retry: Any
    config_watcher: Any
    platform_logger: Any
    api_key_mgr: Any
    data_export: Any
    sla_monitor: Any
    notification_dispatcher: Any
    tenant_isolation: Any
    input_validator: Any
    prom_exporter: Any
    health_agg_v2: Any
    idempotency_store: Any
    response_compressor: Any
    canary_controller: Any
    secret_rotation: Any
    request_dedup: Any
    snapshot_mgr: Any
    otel_exporter: Any
    circuit_dashboard: Any
    tenant_quota: Any
    deploy_checker: Any
    api_migration: Any
    retry_engine: Any
    region_router: Any
    config_drift: Any
    request_ctx_factory: Any
    tenant_partitions: Any
    health_v3: Any


def bootstrap_operational_services(
    *,
    clock: Callable[[], str],
    env: str,
    runtime_env: Mapping[str, str],
    cert_daemon: Any,
    workflow_engine: Any,
    event_bus: Any,
    observability: Any,
    audit_trail: Any,
    metrics: Any,
    tenant_budget_mgr: Any,
    rate_limiter: Any,
    jwt_authenticator: Any,
    tenant_gating: Any,
    access_runtime: Any,
    content_safety_chain: Any,
    temporal_runtime: Any | None = None,
    build_guard_chain_fn: Callable[..., Any] = build_guard_chain,
    create_api_key_guard_fn: Callable[..., Any] = create_api_key_guard,
    build_default_dashboard_fn: Callable[[], Any] = build_default_dashboard,
    build_default_input_validator_fn: Callable[[], Any] = build_default_input_validator,
) -> OperationalBootstrap:
    """Create operational services that sit between bootstrap and routes."""
    plugin_registry = PluginRegistry()
    plugin_registry.register(
        PluginDescriptor(
            plugin_id="logging",
            name="Governance Logger",
            version="1.0.0",
            description="Logs all governed operations to audit trail",
            hooks=(HookPoint.POST_DISPATCH, HookPoint.POST_LLM_CALL),
        )
    )
    plugin_registry.load(
        "logging",
        hooks={
            HookPoint.POST_DISPATCH: lambda **kw: audit_trail.record(
                action="plugin.log.dispatch",
                actor_id="logging-plugin",
                tenant_id=kw.get("tenant_id", ""),
                target="dispatch",
                outcome="logged",
            ),
            HookPoint.POST_LLM_CALL: lambda **kw: metrics.inc("llm_calls_total"),
        },
    )
    plugin_registry.activate("logging")

    plugin_registry.register(
        PluginDescriptor(
            plugin_id="cost-alert",
            name="Cost Alert Plugin",
            version="1.0.0",
            description="Emits budget.warning events when utilization exceeds 80%",
            hooks=(HookPoint.ON_BUDGET_CHECK,),
        )
    )
    plugin_registry.load(
        "cost-alert",
        hooks={
            HookPoint.ON_BUDGET_CHECK: lambda **kw: event_bus.publish(
                "budget.warning",
                tenant_id=kw.get("tenant_id", ""),
                source="cost-alert-plugin",
                payload=kw,
            )
            if kw.get("utilization_pct", 0) > 80
            else None,
        },
    )
    plugin_registry.activate("cost-alert")

    guard_chain = build_guard_chain_fn(
        rate_limiter=rate_limiter,
        budget_mgr=tenant_budget_mgr,
        jwt_authenticator=jwt_authenticator,
        tenant_gating_registry=tenant_gating,
        access_runtime=access_runtime,
        content_safety_chain=content_safety_chain,
        temporal_runtime=temporal_runtime,
    )

    replay_recorder = ReplayRecorder(clock=clock)
    traced_workflow = TracedWorkflowEngine(
        workflow_engine=workflow_engine,
        replay_recorder=replay_recorder,
    )
    observability.register_source("replay", lambda: replay_recorder.summary())

    conversation_store = ConversationStore(clock=clock)

    schema_validator = SchemaValidator()
    schema_validator.register(
        SchemaDefinition(
            schema_id="workflow_request",
            name="Workflow Request",
            rules=(
                SchemaRule(field="task_id", rule_type="required", value=True),
                SchemaRule(field="description", rule_type="required", value=True),
                SchemaRule(field="capability", rule_type="required", value=True),
            ),
        )
    )
    schema_validator.register(
        SchemaDefinition(
            schema_id="pipeline_request",
            name="Pipeline Request",
            rules=(
                SchemaRule(field="steps", rule_type="required", value=True),
                SchemaRule(field="steps", rule_type="type", value="list"),
            ),
        )
    )

    prompt_engine = PromptTemplateEngine()
    prompt_engine.register(
        PromptTemplate(
            template_id="summarize",
            name="Summarize",
            template="Summarize the following text concisely:\n\n{{text}}",
            variables=("text",),
            system_prompt="You are a concise summarizer.",
            category="analysis",
        )
    )
    prompt_engine.register(
        PromptTemplate(
            template_id="translate",
            name="Translate",
            template="Translate the following text to {{language}}:\n\n{{text}}",
            variables=("text", "language"),
            system_prompt="You are a professional translator.",
            category="language",
        )
    )
    prompt_engine.register(
        PromptTemplate(
            template_id="analyze",
            name="Analyze",
            template="Analyze the following {{topic}} and provide key insights:\n\n{{content}}",
            variables=("topic", "content"),
            system_prompt="You are an expert analyst.",
            category="analysis",
        )
    )

    cost_analytics = CostAnalyticsEngine(clock=clock)
    observability.register_source("cost_analytics", lambda: cost_analytics.summary())

    chat_workflow = ChatWorkflowEngine(
        clock=clock,
        conversation_store=conversation_store,
        traced_workflow=traced_workflow,
        cost_record_fn=lambda tid, model, cost, tokens: cost_analytics.record(
            tid,
            model,
            cost,
            tokens,
        ),
    )
    observability.register_source("chat_workflows", lambda: chat_workflow.summary())

    health_agg = HealthAggregator(clock=clock)
    health_agg.register("store", lambda: {"status": "healthy"}, weight=1.0)
    health_agg.register("llm", lambda: {"status": "healthy"}, weight=2.0)
    health_agg.register(
        "certification",
        lambda: {
            "status": "healthy" if cert_daemon.health.is_healthy else "degraded"
        },
        weight=1.5,
    )
    health_agg.register("metrics", lambda: {"status": "healthy"}, weight=0.5)
    health_agg.register(
        "event_bus",
        lambda: {
            "status": "healthy" if event_bus.error_count == 0 else "degraded"
        },
        weight=0.5,
    )

    api_versions = APIVersionManager(clock=clock)
    grafana_dashboard = build_default_dashboard_fn()

    request_tracer = RequestTracer(
        max_traces=10_000,
        on_span_finish=lambda span: audit_trail.record(
            action="trace.span.finish",
            actor_id="tracer",
            tenant_id="",
            target=span.operation,
            outcome=span.status.value,
        ),
    )
    observability.register_source("tracing", lambda: request_tracer.summary())

    agent_orchestrator = AgentOrchestrator(
        clock=clock,
        agent_capabilities={
            "llm-agent": ("llm_completion", "tool_use"),
            "code-agent": ("code_execution",),
        },
    )
    observability.register_source("orchestration", lambda: agent_orchestrator.summary())

    rate_limit_headers = RateLimitHeaderProvider(
        default_limit=60,
        window_seconds=60.0,
    )

    webhook_retry = WebhookRetryEngine(
        policy=RetryPolicy(max_retries=3, base_delay_seconds=1.0)
    )
    observability.register_source("webhook_retry", lambda: webhook_retry.summary())

    config_watcher = ConfigFileWatcher(poll_interval=30.0, clock=clock)
    platform_logger = StructuredLogger(name="mullu-control-plane", min_level=LogLevel.INFO)

    allow_wildcard_api_keys = _env_flag("MULLU_ALLOW_WILDCARD_API_KEYS", runtime_env)
    if allow_wildcard_api_keys is None:
        allow_wildcard_api_keys = env in ("local_dev", "test")
    api_key_mgr = APIKeyManager(
        clock=clock,
        allow_wildcard_keys=allow_wildcard_api_keys,
    )
    observability.register_source("api_keys", lambda: api_key_mgr.summary())
    api_auth_required = _env_flag("MULLU_API_AUTH_REQUIRED", runtime_env)
    if api_auth_required is None:
        api_auth_required = env in ("pilot", "production")
    guard_chain.insert(
        0,
        create_api_key_guard_fn(
            api_key_mgr,
            require_auth=api_auth_required,
            allow_jwt_passthrough=jwt_authenticator is not None,
        ),
    )

    data_export = DataExportPipeline(clock=clock)
    data_export.register_source(
        "audit",
        lambda: [
            e.to_dict() if hasattr(e, "to_dict") else e
            for e in audit_trail.recent(1000)
        ],
    )

    sla_monitor = SLAMonitor(clock=clock)
    sla_monitor.add_target(
        SLATarget("uptime", "Platform Uptime", SLAMetricType.UPTIME, 99.9, "gte")
    )
    sla_monitor.add_target(
        SLATarget(
            "latency-p99",
            "API Latency P99",
            SLAMetricType.LATENCY_P99,
            500.0,
            "lte",
        )
    )
    observability.register_source("sla", lambda: sla_monitor.summary())

    notification_dispatcher = NotificationDispatcher(clock=clock)
    notification_dispatcher.register_channel(NotificationChannel.IN_APP, lambda n: True)

    tenant_isolation = TenantIsolationAuditor(clock=clock)
    observability.register_source(
        "tenant_isolation",
        lambda: tenant_isolation.summary(),
    )

    input_validator = build_default_input_validator_fn()

    prom_exporter = PrometheusExporter(prefix="mullu")
    prom_exporter.register_counter(
        "requests_governed_total",
        "Total governed requests",
    )
    prom_exporter.register_counter("errors_total", "Total errors")
    prom_exporter.register_gauge("active_tenants", "Active tenant count")
    prom_exporter.register_gauge("health_score", "Platform health score")

    health_agg_v2 = HealthCheckAggregator(clock=clock)
    health_agg_v2.register(
        HealthCheckDef(
            "store",
            lambda: {"status": "healthy"},
            weight=2.0,
            critical=True,
        )
    )
    health_agg_v2.register(
        HealthCheckDef(
            "llm",
            lambda: {"status": "healthy"},
            weight=2.0,
            critical=True,
        )
    )
    health_agg_v2.register(
        HealthCheckDef(
            "event_bus",
            lambda: {
                "status": "healthy" if event_bus.error_count == 0 else "degraded"
            },
            weight=1.0,
        )
    )

    idempotency_store = IdempotencyStore(max_entries=10_000, ttl_seconds=3600.0)
    response_compressor = ResponseCompressor(min_size_bytes=1024)
    canary_controller = CanaryController(health_threshold=90.0, clock=clock)
    secret_rotation = SecretRotationEngine(clock=clock)
    request_dedup = RequestDeduplicator(window_seconds=300.0)

    snapshot_mgr = SnapshotManager(max_snapshots=50, clock=clock)
    observability.register_source("snapshots", lambda: snapshot_mgr.summary())

    otel_exporter = OtelExporter(service_name="mullu-control-plane", batch_size=100)
    circuit_dashboard = CircuitDashboard()

    tenant_quota = TenantQuotaEngine()
    observability.register_source("quotas", lambda: tenant_quota.summary())

    deploy_checker = DeployReadinessChecker()
    deploy_checker.register_check(
        "config",
        lambda: CheckResult("config", CheckStatus.PASS, "Config valid"),
    )
    deploy_checker.register_check(
        "health",
        lambda: CheckResult("health", CheckStatus.PASS, "Healthy"),
    )

    api_migration = ApiMigrationEngine()
    api_migration.register_version("v1", endpoints=["/api/v1/*"])

    retry_engine = RetryPolicyEngine()

    region_router = RegionRouter(strategy=RoutingStrategy.LATENCY)
    region_router.add_region("primary", latency_ms=20.0, is_primary=True)

    config_drift = ConfigDriftDetector()
    request_ctx_factory = RequestContextFactory()
    tenant_partitions = TenantPartitionManager(max_partitions=10_000)

    health_v3 = HealthAggregatorV3(recovery_threshold=3)
    health_v3.register("llm_bridge", lambda: ComponentHealth.HEALTHY, weight=3.0)
    health_v3.register("store", lambda: ComponentHealth.HEALTHY, weight=2.0)
    health_v3.register(
        "rate_limiter",
        lambda: ComponentHealth.HEALTHY,
        weight=1.0,
    )

    return OperationalBootstrap(
        plugin_registry=plugin_registry,
        guard_chain=guard_chain,
        replay_recorder=replay_recorder,
        traced_workflow=traced_workflow,
        conversation_store=conversation_store,
        schema_validator=schema_validator,
        prompt_engine=prompt_engine,
        cost_analytics=cost_analytics,
        chat_workflow=chat_workflow,
        health_agg=health_agg,
        api_versions=api_versions,
        grafana_dashboard=grafana_dashboard,
        request_tracer=request_tracer,
        agent_orchestrator=agent_orchestrator,
        rate_limit_headers=rate_limit_headers,
        webhook_retry=webhook_retry,
        config_watcher=config_watcher,
        platform_logger=platform_logger,
        api_key_mgr=api_key_mgr,
        data_export=data_export,
        sla_monitor=sla_monitor,
        notification_dispatcher=notification_dispatcher,
        tenant_isolation=tenant_isolation,
        input_validator=input_validator,
        prom_exporter=prom_exporter,
        health_agg_v2=health_agg_v2,
        idempotency_store=idempotency_store,
        response_compressor=response_compressor,
        canary_controller=canary_controller,
        secret_rotation=secret_rotation,
        request_dedup=request_dedup,
        snapshot_mgr=snapshot_mgr,
        otel_exporter=otel_exporter,
        circuit_dashboard=circuit_dashboard,
        tenant_quota=tenant_quota,
        deploy_checker=deploy_checker,
        api_migration=api_migration,
        retry_engine=retry_engine,
        region_router=region_router,
        config_drift=config_drift,
        request_ctx_factory=request_ctx_factory,
        tenant_partitions=tenant_partitions,
        health_v3=health_v3,
    )
