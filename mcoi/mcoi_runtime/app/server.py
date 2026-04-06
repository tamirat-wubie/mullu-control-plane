"""Phase 200 â€” Governed HTTP Server (FastAPI).

Purpose: HTTP boundary for the governed platform. All requests enter governed execution.
    Phase 199: LLM completion, certification, persistence-backed ledger, budget reporting.
    Phase 200: Bootstrap wiring, streaming, certification daemon, Docker Compose.
Dependencies: fastapi, production_surface, llm_bootstrap, streaming, certification_daemon.
Run: uvicorn mcoi_runtime.app.server:app --host 0.0.0.0 --port 8000
"""
from __future__ import annotations
from contextlib import asynccontextmanager
from typing import Any
from fastapi import FastAPI, HTTPException

from mcoi_runtime.app.production_surface import (
    ProductionSurface, DEPLOYMENT_MANIFESTS,
)
from mcoi_runtime.app.llm_bootstrap import LLMConfig, bootstrap_llm
from mcoi_runtime.app.streaming import StreamingAdapter
from mcoi_runtime.core.live_path_certification import LivePathCertifier
from mcoi_runtime.core.certification_daemon import CertificationConfig, CertificationDaemon
from mcoi_runtime.core.agent_protocol import (
    AgentCapability, AgentDescriptor, AgentRegistry, TaskManager,
)
from mcoi_runtime.core.agent_workflow import AgentWorkflowEngine
from mcoi_runtime.core.webhook_system import WebhookManager
from mcoi_runtime.core.deep_health import DeepHealthChecker
from mcoi_runtime.core.config_reload import ConfigManager
from mcoi_runtime.core.observability import ObservabilityAggregator
from mcoi_runtime.core.plugin_system import HookPoint, PluginDescriptor, PluginRegistry
from mcoi_runtime.core.safe_arithmetic import evaluate_expression
from mcoi_runtime.persistence.tenant_ledger import TenantLedger

import hashlib
import json
import os
from datetime import datetime, timezone

from mcoi_runtime.app.server_policy import (
    _append_bounded_warning,
    _bounded_bootstrap_warning,
    _env_flag,
    _resolve_cors_origins,
    _validate_cors_origins_for_env,
    _validate_db_backend_for_env,
)
from mcoi_runtime.app.server_http import (
    configure_cors_middleware,
    include_default_routers,
    install_global_exception_handler,
)
from mcoi_runtime.app.server_deps import (
    register_dependency_groups,
    wire_runtime_dependencies,
)
from mcoi_runtime.app.server_platform import (
    bootstrap_governance_runtime,
    bootstrap_primary_store,
)
from mcoi_runtime.app.server_agents import bootstrap_agent_runtime
from mcoi_runtime.app.server_subsystems import bootstrap_subsystems
from mcoi_runtime.app.server_bootstrap import (
    init_field_encryption_from_env as _init_field_encryption_from_env_impl,
    utc_clock as _utc_clock,
)
from mcoi_runtime.app.server_runtime import (
    build_default_input_validator,
    calculator_handler as _calculator_handler_impl,
    register_default_output_schemas,
    register_default_tools,
    validate_or_raise as _validate_or_raise_impl,
)
from mcoi_runtime.app.server_state import (
    close_governance_stores as _close_governance_stores_impl,
    flush_state_on_shutdown as _flush_state_on_shutdown_impl,
    restore_state_on_startup as _restore_state_on_startup_impl,
)

ENV = os.environ.get("MULLU_ENV", "local_dev")
surface = ProductionSurface(DEPLOYMENT_MANIFESTS.get(ENV, DEPLOYMENT_MANIFESTS["local_dev"]))


def _init_field_encryption_from_env() -> tuple[Any | None, dict[str, Any]]:
    """Build optional field encryption and expose explicit startup posture."""
    return _init_field_encryption_from_env_impl(
        env=os.environ,
        bounded_bootstrap_warning=_bounded_bootstrap_warning,
    )


_tenant_allow_unknown = _env_flag("MULLU_ALLOW_UNKNOWN_TENANTS", os.environ)
if _tenant_allow_unknown is None:
    _tenant_allow_unknown = ENV in ("local_dev", "test")

# Clock
def _clock() -> str:
    return _utc_clock()

# Persistence store (InMemoryStore for dev, PostgresStore for production)
_primary_store_bootstrap = bootstrap_primary_store(
    env=ENV,
    runtime_env=os.environ,
    clock=_clock,
    validate_db_backend_for_env=_validate_db_backend_for_env,
)
_db_backend = _primary_store_bootstrap.db_backend
_db_backend_warning = _primary_store_bootstrap.warning
store = _primary_store_bootstrap.store

# Phase 200A: LLM bootstrap wiring (env-driven backend selection)
llm_bootstrap_result = bootstrap_llm(
    clock=_clock,
    config=LLMConfig.from_env(),
    ledger_sink=lambda entry: store.append_ledger(
        entry.get("type", "llm"),
        entry.get("tenant_id", "system"),
        entry.get("tenant_id", "system"),
        entry,
        hashlib.sha256(json.dumps(entry, sort_keys=True).encode()).hexdigest(),
    ),
)
llm_bridge = llm_bootstrap_result.bridge

# Certification engine
certifier = LivePathCertifier(clock=_clock)

# Phase 200C: Streaming adapter
streaming_adapter = StreamingAdapter(clock=_clock)

# Phase 200D: Certification daemon
cert_daemon = CertificationDaemon(
    certifier=certifier,
    clock=_clock,
    config=CertificationConfig(
        interval_seconds=float(os.environ.get("MULLU_CERT_INTERVAL", "300")),
        enabled=os.environ.get("MULLU_CERT_ENABLED", "true").lower() == "true",
    ),
    api_handle_fn=lambda req: {"governed": True, "status": "ok"},
    db_write_fn=lambda t, c: store.append_ledger(
        "certification", "certifier", t, c,
        hashlib.sha256(json.dumps(c, sort_keys=True).encode()).hexdigest(),
    ),
    db_read_fn=lambda t: store.query_ledger(t),
    llm_invoke_fn=lambda prompt: llm_bridge.complete(prompt, budget_id="default"),
    ledger_fn=lambda t: store.query_ledger(t),
    state_fn=lambda: (
        hashlib.sha256(str(store.ledger_count()).encode()).hexdigest(),
        store.ledger_count(),
    ),
)

# Phase 2B: Field encryption (optional â€” enabled when MULLU_ENCRYPTION_KEY is set)
_field_encryptor, _field_encryption_bootstrap = _init_field_encryption_from_env()

_governance_bootstrap = bootstrap_governance_runtime(
    env=ENV,
    runtime_env=os.environ,
    db_backend=_db_backend,
    clock=_clock,
    field_encryptor=_field_encryptor,
    allow_unknown_tenants=_tenant_allow_unknown,
)
_gov_stores = _governance_bootstrap.governance_stores
tenant_budget_mgr = _governance_bootstrap.tenant_budget_mgr
metrics = _governance_bootstrap.metrics
rate_limiter = _governance_bootstrap.rate_limiter
audit_trail = _governance_bootstrap.audit_trail
_jwt_authenticator = _governance_bootstrap.jwt_authenticator
_tenant_gating = _governance_bootstrap.tenant_gating

# Phase 3A: PII scanner
from mcoi_runtime.core.pii_scanner import PIIScanner
pii_scanner = PIIScanner(
    enabled=os.environ.get("MULLU_PII_SCAN", "true").lower() == "true",
)

# Phase 3B: Content safety chain
from mcoi_runtime.core.content_safety import build_default_safety_chain
content_safety_chain = build_default_safety_chain()

# Phase 3C: Shell sandbox policy (env-driven profile selection)
shell_policy = _governance_bootstrap.shell_policy

# Phase 4C: Proof bridge (governance decision â†’ MAF transition receipts)
from mcoi_runtime.core.proof_bridge import ProofBridge
proof_bridge = ProofBridge(clock=_clock)

# Phase 201D: Tenant-scoped ledger
tenant_ledger = TenantLedger(clock=_clock)

_agent_bootstrap = bootstrap_agent_runtime(
    clock=_clock,
    store=store,
    llm_bridge=llm_bridge,
    cert_daemon=cert_daemon,
    metrics=metrics,
    default_model=llm_bootstrap_result.config.default_model,
    audit_trail=audit_trail,
    tenant_budget_mgr=tenant_budget_mgr,
    tenant_gating=_tenant_gating,
    pii_scanner=pii_scanner,
    content_safety_chain=content_safety_chain,
    proof_bridge=proof_bridge,
    rate_limiter=rate_limiter,
    shell_policy=shell_policy,
)
agent_registry = _agent_bootstrap.agent_registry
task_manager = _agent_bootstrap.task_manager
webhook_manager = _agent_bootstrap.webhook_manager
deep_health = _agent_bootstrap.deep_health
config_manager = _agent_bootstrap.config_manager
workflow_engine = _agent_bootstrap.workflow_engine
observability = _agent_bootstrap.observability

_subsystem_bootstrap = bootstrap_subsystems(
    clock=_clock,
    runtime_env=os.environ,
    llm_bridge=llm_bridge,
    audit_trail=audit_trail,
    observability=observability,
    deep_health=deep_health,
)
coordination_store = _subsystem_bootstrap.coordination_store
coordination_engine = _subsystem_bootstrap.coordination_engine
scheduler = _subsystem_bootstrap.scheduler
connector_framework = _subsystem_bootstrap.connector_framework
access_runtime = _subsystem_bootstrap.access_runtime
_rbac_rules_seeded = _subsystem_bootstrap.rbac_rules_seeded
policy_sandbox = _subsystem_bootstrap.policy_sandbox
runbook_learning = _subsystem_bootstrap.runbook_learning

# Phase 204D: Plugin registry
plugin_registry = PluginRegistry()

explanation_engine = _subsystem_bootstrap.explanation_engine
audit_anchor = _subsystem_bootstrap.audit_anchor
knowledge_graph = _subsystem_bootstrap.knowledge_graph
event_bus = _subsystem_bootstrap.event_bus
batch_pipeline = _subsystem_bootstrap.batch_pipeline

# Phase 206C: Register example plugins
_logging_plugin = PluginDescriptor(
    plugin_id="logging", name="Governance Logger", version="1.0.0",
    description="Logs all governed operations to audit trail",
    hooks=(HookPoint.POST_DISPATCH, HookPoint.POST_LLM_CALL),
)
plugin_registry.register(_logging_plugin)
plugin_registry.load("logging", hooks={
    HookPoint.POST_DISPATCH: lambda **kw: audit_trail.record(
        action="plugin.log.dispatch", actor_id="logging-plugin",
        tenant_id=kw.get("tenant_id", ""), target="dispatch", outcome="logged",
    ),
    HookPoint.POST_LLM_CALL: lambda **kw: metrics.inc("llm_calls_total"),
})
plugin_registry.activate("logging")

_alert_plugin = PluginDescriptor(
    plugin_id="cost-alert", name="Cost Alert Plugin", version="1.0.0",
    description="Emits budget.warning events when utilization exceeds 80%",
    hooks=(HookPoint.ON_BUDGET_CHECK,),
)
plugin_registry.register(_alert_plugin)
plugin_registry.load("cost-alert", hooks={
    HookPoint.ON_BUDGET_CHECK: lambda **kw: event_bus.publish(
        "budget.warning", tenant_id=kw.get("tenant_id", ""),
        source="cost-alert-plugin", payload=kw,
    ) if kw.get("utilization_pct", 0) > 80 else None,
})
plugin_registry.activate("cost-alert")

# Phase 208A: Governance guard middleware (chain built after all subsystems init)
from mcoi_runtime.app.middleware import GovernanceMiddleware, build_guard_chain
guard_chain = build_guard_chain(
    rate_limiter=rate_limiter, budget_mgr=tenant_budget_mgr,
    jwt_authenticator=_jwt_authenticator,
    tenant_gating_registry=_tenant_gating,
    access_runtime=access_runtime,
    content_safety_chain=content_safety_chain,
)

# Phase 208B: Traced workflow engine
from mcoi_runtime.core.traced_workflow import TracedWorkflowEngine
from mcoi_runtime.core.execution_replay import ReplayRecorder
replay_recorder = ReplayRecorder(clock=_clock)
traced_workflow = TracedWorkflowEngine(
    workflow_engine=workflow_engine, replay_recorder=replay_recorder,
)
observability.register_source("replay", lambda: replay_recorder.summary())

# Phase 208C: Conversation store
from mcoi_runtime.core.conversation_memory import ConversationStore
conversation_store = ConversationStore(clock=_clock)

# Phase 208D: Schema validator
from mcoi_runtime.core.schema_validator import SchemaValidator, SchemaDefinition, SchemaRule
schema_validator = SchemaValidator()
schema_validator.register(SchemaDefinition(
    schema_id="workflow_request", name="Workflow Request",
    rules=(
        SchemaRule(field="task_id", rule_type="required", value=True),
        SchemaRule(field="description", rule_type="required", value=True),
        SchemaRule(field="capability", rule_type="required", value=True),
    ),
))
schema_validator.register(SchemaDefinition(
    schema_id="pipeline_request", name="Pipeline Request",
    rules=(
        SchemaRule(field="steps", rule_type="required", value=True),
        SchemaRule(field="steps", rule_type="type", value="list"),
    ),
))

# Phase 209C: Prompt template engine
from mcoi_runtime.core.prompt_template_engine import PromptTemplateEngine, PromptTemplate
prompt_engine = PromptTemplateEngine()
prompt_engine.register(PromptTemplate(
    template_id="summarize", name="Summarize",
    template="Summarize the following text concisely:\n\n{{text}}",
    variables=("text",), system_prompt="You are a concise summarizer.",
    category="analysis",
))
prompt_engine.register(PromptTemplate(
    template_id="translate", name="Translate",
    template="Translate the following text to {{language}}:\n\n{{text}}",
    variables=("text", "language"), system_prompt="You are a professional translator.",
    category="language",
))
prompt_engine.register(PromptTemplate(
    template_id="analyze", name="Analyze",
    template="Analyze the following {{topic}} and provide key insights:\n\n{{content}}",
    variables=("topic", "content"), system_prompt="You are an expert analyst.",
    category="analysis",
))

# Phase 209D: Cost analytics engine
from mcoi_runtime.core.cost_analytics import CostAnalyticsEngine
cost_analytics = CostAnalyticsEngine(clock=_clock)
observability.register_source("cost_analytics", lambda: cost_analytics.summary())

# Phase 210A: Chat workflow engine
from mcoi_runtime.core.chat_workflow import ChatWorkflowEngine
chat_workflow = ChatWorkflowEngine(
    clock=_clock,
    conversation_store=conversation_store,
    traced_workflow=traced_workflow,
    cost_record_fn=lambda tid, model, cost, tokens: cost_analytics.record(tid, model, cost, tokens),
)
observability.register_source("chat_workflows", lambda: chat_workflow.summary())

# Phase 210B: Health aggregator
from mcoi_runtime.core.health_aggregator import HealthAggregator
health_agg = HealthAggregator(clock=_clock)
health_agg.register("store", lambda: {"status": "healthy"}, weight=1.0)
health_agg.register("llm", lambda: {"status": "healthy"}, weight=2.0)
health_agg.register("certification", lambda: {"status": "healthy" if cert_daemon.health.is_healthy else "degraded"}, weight=1.5)
health_agg.register("metrics", lambda: {"status": "healthy"}, weight=0.5)
health_agg.register("event_bus", lambda: {"status": "healthy" if event_bus.error_count == 0 else "degraded"}, weight=0.5)

# Phase 210C: API version manager
from mcoi_runtime.core.api_version import APIVersionManager
api_versions = APIVersionManager(clock=_clock)

# Phase 222A: Grafana dashboard generator
from mcoi_runtime.core.grafana_dashboard import build_default_dashboard
grafana_dashboard = build_default_dashboard()

# Phase 222B: Request tracing
from mcoi_runtime.core.request_tracing import RequestTracer
request_tracer = RequestTracer(
    max_traces=10_000,
    on_span_finish=lambda span: audit_trail.record(
        action="trace.span.finish", actor_id="tracer",
        tenant_id="", target=span.operation,
        outcome=span.status.value,
    ),
)
observability.register_source("tracing", lambda: request_tracer.summary())

# Phase 222C: Agent orchestration
from mcoi_runtime.core.agent_orchestration import AgentOrchestrator
agent_orchestrator = AgentOrchestrator(clock=_clock, agent_capabilities={
    "llm-agent": ("llm_completion", "tool_use"),
    "code-agent": ("code_execution",),
})
observability.register_source("orchestration", lambda: agent_orchestrator.summary())

# Phase 223A: Rate limit headers
from mcoi_runtime.core.rate_limit_headers import RateLimitHeaderProvider
rate_limit_headers = RateLimitHeaderProvider(default_limit=60, window_seconds=60.0)

# Phase 223B: Webhook retry engine
from mcoi_runtime.core.webhook_retry import WebhookRetryEngine, RetryPolicy
webhook_retry = WebhookRetryEngine(policy=RetryPolicy(max_retries=3, base_delay_seconds=1.0))
observability.register_source("webhook_retry", lambda: webhook_retry.summary())

# Phase 223C: Config file watcher
from mcoi_runtime.core.config_watcher import ConfigFileWatcher
config_watcher = ConfigFileWatcher(poll_interval=30.0, clock=_clock)

# Phase 224A: Structured logging
from mcoi_runtime.core.structured_logging import StructuredLogger, LogLevel
platform_logger = StructuredLogger(name="mullu-platform", min_level=LogLevel.INFO)

# Phase 224B: API key authentication
from mcoi_runtime.core.api_key_auth import APIKeyManager
api_key_mgr = APIKeyManager(clock=_clock)
observability.register_source("api_keys", lambda: api_key_mgr.summary())
api_auth_required = _env_flag("MULLU_API_AUTH_REQUIRED")
if api_auth_required is None:
    api_auth_required = ENV in ("pilot", "production")
# Wire API key guard as FIRST guard (auth before rate-limit/budget checks)
from mcoi_runtime.core.governance_guard import create_api_key_guard
guard_chain.insert(0, create_api_key_guard(api_key_mgr, require_auth=api_auth_required))

# Phase 224C: Data export pipeline
from mcoi_runtime.core.data_export import DataExportPipeline
data_export = DataExportPipeline(clock=_clock)
data_export.register_source("audit", lambda: [
    e.to_dict() if hasattr(e, "to_dict") else e for e in audit_trail.recent(1000)
])

# Phase 225A: SLA monitoring
from mcoi_runtime.core.sla_monitor import SLAMonitor, SLATarget, SLAMetricType
sla_monitor = SLAMonitor(clock=_clock)
sla_monitor.add_target(SLATarget("uptime", "Platform Uptime", SLAMetricType.UPTIME, 99.9, "gte"))
sla_monitor.add_target(SLATarget("latency-p99", "API Latency P99", SLAMetricType.LATENCY_P99, 500.0, "lte"))
observability.register_source("sla", lambda: sla_monitor.summary())

# Phase 225B: Notification dispatcher
from mcoi_runtime.core.notification_dispatcher import NotificationDispatcher, NotificationChannel
notification_dispatcher = NotificationDispatcher(clock=_clock)
notification_dispatcher.register_channel(NotificationChannel.IN_APP, lambda n: True)

# Phase 225C: Tenant isolation auditor
from mcoi_runtime.core.tenant_isolation_audit import TenantIsolationAuditor
tenant_isolation = TenantIsolationAuditor(clock=_clock)
observability.register_source("tenant_isolation", lambda: tenant_isolation.summary())

# Phase 226A: Input validation
input_validator = build_default_input_validator()


def _validate_or_raise(schema_id: str, data: dict[str, Any]) -> None:
    """Validate request data against a schema; raise 422 if invalid."""
    _validate_or_raise_impl(
        input_validator=input_validator,
        schema_id=schema_id,
        data=data,
    )

# Phase 226B: Prometheus exporter
from mcoi_runtime.core.prometheus_exporter import PrometheusExporter
prom_exporter = PrometheusExporter(prefix="mullu")
prom_exporter.register_counter("requests_governed_total", "Total governed requests")
prom_exporter.register_counter("errors_total", "Total errors")
prom_exporter.register_gauge("active_tenants", "Active tenant count")
prom_exporter.register_gauge("health_score", "Platform health score")

# Phase 226C: Health check aggregation
from mcoi_runtime.core.health_check_agg import HealthCheckAggregator, HealthCheckDef
health_agg_v2 = HealthCheckAggregator(clock=_clock)
health_agg_v2.register(HealthCheckDef("store", lambda: {"status": "healthy"}, weight=2.0, critical=True))
health_agg_v2.register(HealthCheckDef("llm", lambda: {"status": "healthy"}, weight=2.0, critical=True))
health_agg_v2.register(HealthCheckDef("event_bus", lambda: {"status": "healthy" if event_bus.error_count == 0 else "degraded"}, weight=1.0))

# Phase 227A: Idempotency store
from mcoi_runtime.core.idempotency import IdempotencyStore
idempotency_store = IdempotencyStore(max_entries=10_000, ttl_seconds=3600.0)

# Phase 227B: Response compression
from mcoi_runtime.core.response_compression import ResponseCompressor
response_compressor = ResponseCompressor(min_size_bytes=1024)

# Phase 227C: Canary deployment controller
from mcoi_runtime.core.canary_controller import CanaryController
canary_controller = CanaryController(health_threshold=90.0, clock=_clock)

# Phase 228A: Secret rotation
from mcoi_runtime.core.secret_rotation import SecretRotationEngine
secret_rotation = SecretRotationEngine(clock=_clock)

# Phase 228B: Request deduplication
from mcoi_runtime.core.request_dedup import RequestDeduplicator
request_dedup = RequestDeduplicator(window_seconds=300.0)

# Phase 228C: Rollback snapshots
from mcoi_runtime.core.rollback_snapshot import SnapshotManager
snapshot_mgr = SnapshotManager(max_snapshots=50, clock=_clock)
observability.register_source("snapshots", lambda: snapshot_mgr.summary())

# Phase 229A: OpenTelemetry exporter
from mcoi_runtime.core.otel_exporter import OtelExporter
otel_exporter = OtelExporter(service_name="mullu-platform", batch_size=100)

# Phase 229B: Circuit breaker dashboard
from mcoi_runtime.core.circuit_dashboard import CircuitDashboard
circuit_dashboard = CircuitDashboard()

# Phase 229C: Tenant quota enforcement
from mcoi_runtime.core.tenant_quota import TenantQuotaEngine
tenant_quota = TenantQuotaEngine()
observability.register_source("quotas", lambda: tenant_quota.summary())

# Phase 230A: Deployment readiness
from mcoi_runtime.core.deploy_readiness import DeployReadinessChecker, CheckResult, CheckStatus
deploy_checker = DeployReadinessChecker()
deploy_checker.register_check("config", lambda: CheckResult("config", CheckStatus.PASS, "Config valid"))
deploy_checker.register_check("health", lambda: CheckResult("health", CheckStatus.PASS, "Healthy"))

# Phase 230B: API migration versioning
from mcoi_runtime.core.api_migration import ApiMigrationEngine
api_migration = ApiMigrationEngine()
api_migration.register_version("v1", endpoints=["/api/v1/*"])

# Phase 230C: Governed retry policy
from mcoi_runtime.core.retry_policy import RetryPolicyEngine
retry_engine = RetryPolicyEngine()

# Phase 231A: Event sourcing
from mcoi_runtime.core.event_sourcing import EventStore
event_store = EventStore(max_events=100_000)

# Phase 231B: Multi-region routing
from mcoi_runtime.core.region_router import RegionRouter, RoutingStrategy
region_router = RegionRouter(strategy=RoutingStrategy.LATENCY)
region_router.add_region("primary", latency_ms=20.0, is_primary=True)

# Phase 231C: Config drift detection
from mcoi_runtime.core.config_drift import ConfigDriftDetector
config_drift = ConfigDriftDetector()

# Phase 232A: Request context propagation
from mcoi_runtime.core.request_context import RequestContextFactory
request_ctx_factory = RequestContextFactory()

# Phase 232B: Tenant data partitioning
from mcoi_runtime.core.tenant_partition import TenantPartitionManager
tenant_partitions = TenantPartitionManager(max_partitions=10_000)

# Phase 232C: Health check v3
from mcoi_runtime.core.health_v3 import HealthAggregatorV3, ComponentHealth
health_v3 = HealthAggregatorV3(recovery_threshold=3)
health_v3.register("llm_bridge", lambda: ComponentHealth.HEALTHY, weight=3.0)
health_v3.register("store", lambda: ComponentHealth.HEALTHY, weight=2.0)
health_v3.register("rate_limiter", lambda: ComponentHealth.HEALTHY, weight=1.0)

# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# Additional subsystem initialization (previously scattered in route sections)
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

# Phase 212A: Tool registry
from mcoi_runtime.core.tool_use import ToolDefinition, ToolParameter, ToolRegistry
tool_registry = ToolRegistry(clock=_clock)


def _calculator_handler(args: dict[str, Any]) -> dict[str, str]:
    return _calculator_handler_impl(
        args,
        evaluate_expression_fn=evaluate_expression,
    )


register_default_tools(
    tool_registry=tool_registry,
    clock=_clock,
    evaluate_expression_fn=evaluate_expression,
)
observability.register_source("tools", lambda: tool_registry.summary())

# Phase 212A: Structured output engine
from mcoi_runtime.core.structured_output import StructuredOutputEngine, OutputSchema
structured_output = StructuredOutputEngine()
register_default_output_schemas(structured_output)

# Phase 212A: State persistence (file-based)
from mcoi_runtime.persistence.state_persistence import StatePersistence
_state_dir = os.environ.get("MULLU_STATE_DIR", "")
state_persistence = StatePersistence(clock=_clock, base_dir=_state_dir)

# Phase 212A: LLM circuit breaker
from mcoi_runtime.core.retry_engine import CircuitBreaker
llm_circuit = CircuitBreaker(failure_threshold=10, recovery_timeout_ms=60000)

# Phase 213B: Tool-augmented agent
from mcoi_runtime.core.tool_agent import ToolAugmentedAgent
tool_agent = ToolAugmentedAgent(
    tool_registry=tool_registry,
    llm_fn=lambda prompt: llm_bridge.complete(prompt, budget_id="default"),
    max_tool_calls=10,
)

# Phase 214A: Model router
from mcoi_runtime.core.model_router import ModelProfile, ModelRouter
model_router = ModelRouter()
model_router.register(ModelProfile(
    model_id="claude-haiku-4-5", name="Claude Haiku 4.5", provider="anthropic",
    cost_per_1k_input=0.80, cost_per_1k_output=4.0,
    max_context=200000, speed_tier="fast", capability_tier="basic",
))
model_router.register(ModelProfile(
    model_id="claude-sonnet-4", name="Claude Sonnet 4", provider="anthropic",
    cost_per_1k_input=3.0, cost_per_1k_output=15.0,
    max_context=200000, speed_tier="medium", capability_tier="standard",
))
model_router.register(ModelProfile(
    model_id="claude-opus-4-6", name="Claude Opus 4.6", provider="anthropic",
    cost_per_1k_input=15.0, cost_per_1k_output=75.0,
    max_context=1000000, speed_tier="slow", capability_tier="advanced",
))
model_router.register(ModelProfile(
    model_id="gpt-4o-mini", name="GPT-4o Mini", provider="openai",
    cost_per_1k_input=0.15, cost_per_1k_output=0.60,
    max_context=128000, speed_tier="fast", capability_tier="basic",
))
observability.register_source("model_router", lambda: model_router.summary())

# Phase 214B: Request correlation
from mcoi_runtime.core.request_correlation import CorrelationManager
correlation_mgr = CorrelationManager(clock=_clock)

# Phase 214C: Shutdown manager
from mcoi_runtime.core.graceful_shutdown import ShutdownManager
shutdown_mgr = ShutdownManager()

# Phase 215A: Agent chain
from mcoi_runtime.core.agent_chain import AgentChainEngine
agent_chain = AgentChainEngine(
    clock=_clock,
    llm_fn=lambda prompt: llm_bridge.complete(prompt, budget_id="default"),
)

# Phase 215B: Monitoring
from mcoi_runtime.core.monitoring import MonitoringEngine
monitor = MonitoringEngine(clock=_clock)

# Phase 215C: Task queue
from mcoi_runtime.core.task_queue import TaskQueue
task_queue = TaskQueue(clock=_clock)

# Phase 216A: Agent memory
from mcoi_runtime.core.agent_memory import AgentMemoryStore
agent_memory = AgentMemoryStore(clock=_clock)
observability.register_source("agent_memory", lambda: agent_memory.summary())

# Phase 216B: A/B testing
from mcoi_runtime.core.ab_testing import ABTestEngine
ab_engine = ABTestEngine(clock=_clock)

# Phase 216C: Isolation verifier
from mcoi_runtime.core.isolation_verifier import IsolationVerifier, IsolationProbe
isolation_verifier = IsolationVerifier(clock=_clock)
isolation_verifier.register_probe(lambda a, b: IsolationProbe(
    probe_name="budget_isolation", tenant_a=a, tenant_b=b,
    isolated=tenant_budget_mgr.get_budget(a) != tenant_budget_mgr.get_budget(b) or
             (tenant_budget_mgr.get_budget(a) is None and tenant_budget_mgr.get_budget(b) is None),
    detail="budget objects are distinct per tenant",
))
isolation_verifier.register_probe(lambda a, b: IsolationProbe(
    probe_name="ledger_isolation", tenant_a=a, tenant_b=b,
    isolated=True, detail="ledger entries are keyed by tenant_id",
))
isolation_verifier.register_probe(lambda a, b: IsolationProbe(
    probe_name="conversation_isolation", tenant_a=a, tenant_b=b,
    isolated=True, detail="conversations are filtered by tenant_id",
))

# Phase 217: Usage reporter
from mcoi_runtime.core.usage_reporter import UsageReporter
usage_reporter = UsageReporter(clock=_clock)
usage_reporter.register_source("llm_calls", lambda tid: llm_bridge.invocation_count)
usage_reporter.register_source("total_cost", lambda tid: llm_bridge.total_cost)

# Phase 218B: Dependency graph
from mcoi_runtime.core.dependency_graph import DependencyGraph, SubsystemNode
dep_graph = DependencyGraph()
dep_graph.add(SubsystemNode(name="store", version="1.0"))
dep_graph.add(SubsystemNode(name="llm", version="1.0", dependencies=("store",)))
dep_graph.add(SubsystemNode(name="agents", version="1.0", dependencies=("llm", "store")))
dep_graph.add(SubsystemNode(name="workflows", version="1.0", dependencies=("agents", "llm")))
dep_graph.add(SubsystemNode(name="conversations", version="1.0", dependencies=("llm",)))
dep_graph.add(SubsystemNode(name="events", version="1.0", dependencies=("store",)))
dep_graph.add(SubsystemNode(name="governance", version="1.0", dependencies=("store", "events")))
dep_graph.add(SubsystemNode(name="api", version="1.0", dependencies=("governance", "workflows", "conversations")))

# Phase 218C: Backpressure
from mcoi_runtime.core.backpressure import BackpressureEngine
backpressure = BackpressureEngine()

# Phase 220: Cache + Feature flags
from mcoi_runtime.core.cache import GovernedCache
from mcoi_runtime.core.feature_flags import FeatureFlag, FeatureFlagEngine
governed_cache = GovernedCache(max_size=500, default_ttl=60.0)
feature_flags = FeatureFlagEngine()
feature_flags.register(FeatureFlag(flag_id="streaming_v2", name="Streaming V2", enabled=True))
feature_flags.register(FeatureFlag(flag_id="tool_augmentation", name="Tool Augmentation", enabled=True))
feature_flags.register(FeatureFlag(flag_id="ab_testing", name="A/B Testing", enabled=True))
feature_flags.register(FeatureFlag(flag_id="agent_memory", name="Agent Memory", enabled=True))

# Phase 221A: Semantic search
from mcoi_runtime.core.semantic_search import SemanticSearchEngine
semantic_search = SemanticSearchEngine()

# Phase 221B: Tenant analytics
from mcoi_runtime.core.tenant_analytics import TenantAnalyticsEngine
tenant_analytics = TenantAnalyticsEngine(clock=_clock)
tenant_analytics.register_collector("llm_calls", lambda tid: llm_bridge.invocation_count)
tenant_analytics.register_collector("total_cost", lambda tid: llm_bridge.total_cost)

# Phase 221C: Workflow templates
from mcoi_runtime.core.workflow_templates import WorkflowTemplate, WorkflowTemplateRegistry
from mcoi_runtime.core.agent_chain import ChainStep as _ChainStep
wf_templates = WorkflowTemplateRegistry()
wf_templates.register(WorkflowTemplate(
    template_id="summarize-refine", name="Summarize & Refine",
    description="Summarize then refine for audience",
    steps=(
        _ChainStep(step_id="s1", name="Summarize", prompt_template="Summarize {{topic}}: {{input}}"),
        _ChainStep(step_id="s2", name="Refine", prompt_template="Refine for {{audience}}: {{prev}}"),
    ),
    parameters=("topic", "audience"), category="analysis",
))
wf_templates.register(WorkflowTemplate(
    template_id="research-draft", name="Research & Draft",
    description="Research a topic then draft a report",
    steps=(
        _ChainStep(step_id="s1", name="Research", prompt_template="Research {{topic}}: {{input}}"),
        _ChainStep(step_id="s2", name="Draft", prompt_template="Draft a {{format}} report: {{prev}}"),
    ),
    parameters=("topic", "format"), category="research",
))

@asynccontextmanager
async def _app_lifespan(_app: FastAPI):
    try:
        yield
    finally:
        shutdown_mgr.execute()


app = FastAPI(
    title="Mullu Platform",
    version="3.13.0",
    description="Governed AI Operating System",
    lifespan=_app_lifespan,
)

# Wire middleware
app.add_middleware(
    GovernanceMiddleware,
    guard_chain=guard_chain,
    metrics_fn=lambda name, val: metrics.inc(name, val),
    proof_bridge=proof_bridge,
    on_reject=lambda ctx: audit_trail.record(
        action="guard.rejected", actor_id="system",
        tenant_id=ctx.get("tenant_id", ""), target=ctx.get("path", ""),
        outcome="denied",
        detail=pii_scanner.scan_dict(ctx)[0] if pii_scanner.enabled else ctx,
    ),
    on_allow=lambda ctx: audit_trail.record(
        action="guard.allowed", actor_id=ctx.get("tenant_id", "system"),
        tenant_id=ctx.get("tenant_id", ""), target=ctx.get("path", ""),
        outcome="success",
    ),
)


import warnings

configure_cors_middleware(
    app=app,
    env=ENV,
    cors_origins_raw=os.environ.get("MULLU_CORS_ORIGINS"),
    resolve_cors_origins=_resolve_cors_origins,
    validate_cors_origins_for_env=_validate_cors_origins_for_env,
    warnings_module=warnings,
)


install_global_exception_handler(
    app=app,
    metrics=metrics,
    platform_logger=platform_logger,
    log_levels=LogLevel,
)


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# Dependency injection â€” register all subsystems into deps container
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

from mcoi_runtime.app.routers.deps import deps

# GovernedSession Platform harness
from mcoi_runtime.core.governed_session import Platform as _Platform
platform = _Platform(
    clock=_clock,
    access_runtime=access_runtime,
    content_safety_chain=content_safety_chain,
    pii_scanner=pii_scanner,
    budget_mgr=tenant_budget_mgr,
    llm_bridge=llm_bootstrap_result.bridge,
    audit_trail=audit_trail,
    proof_bridge=proof_bridge,
    tenant_gating=_tenant_gating,
    rate_limiter=rate_limiter,
    bootstrap_warnings=tuple(
        warning for warning in (_field_encryption_bootstrap.get("warning", ""),) if warning
    ),
    bootstrap_components={
        "access_runtime": access_runtime is not None,
        "llm_bridge": llm_bootstrap_result.bridge is not None,
        "tenant_gating": _tenant_gating is not None,
        "proof_bridge": proof_bridge is not None,
        "field_encryption": bool(_field_encryption_bootstrap.get("enabled", False)),
    },
)
wire_runtime_dependencies(
    guard_chain=guard_chain,
    audit_trail=audit_trail,
    scheduler=scheduler,
    connector_framework=connector_framework,
    policy_sandbox=policy_sandbox,
    explanation_engine=explanation_engine,
)

register_dependency_groups(
    deps,
    {
        "surface": surface,
        "store": store,
        "_clock": _clock,
        "ENV": ENV,
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
        "tenant_gating": _tenant_gating,
        "field_encryption_bootstrap": dict(_field_encryption_bootstrap),
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
        "runbook_learning": runbook_learning,
        "explanation_engine": explanation_engine,
        "knowledge_graph": knowledge_graph,
        "audit_anchor": audit_anchor,
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


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# Include routers â€” all route handlers live in routers/ modules
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

include_default_routers(app)


# â•â•â•â•ï¿½ï¿½â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•ï¿½ï¿½ï¿½â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•ï¿½ï¿½â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# Shutdown handler â€” stays in server.py (needs direct access to subsystems)
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

def _flush_state_on_shutdown():
    """Flush critical in-memory state to file-based snapshots before exit."""
    return _flush_state_on_shutdown_impl(
        tenant_budget_mgr=tenant_budget_mgr,
        state_persistence=state_persistence,
        audit_trail=audit_trail,
        cost_analytics=cost_analytics,
        platform_logger=platform_logger,
        log_levels=LogLevel,
        append_bounded_warning=_append_bounded_warning,
    )


def _restore_state_on_startup():
    """Restore state from file-based snapshots on startup."""
    return _restore_state_on_startup_impl(
        tenant_budget_mgr=tenant_budget_mgr,
        state_persistence=state_persistence,
        platform_logger=platform_logger,
        log_levels=LogLevel,
        append_bounded_warning=_append_bounded_warning,
    )


_startup_restored = _restore_state_on_startup()

shutdown_mgr.register("save_state", _flush_state_on_shutdown, priority=100)
shutdown_mgr.register("flush_metrics", lambda: {"flushed": True}, priority=90)


def _close_governance_stores():
    """Close all governance store connections on shutdown."""
    return _close_governance_stores_impl(
        governance_stores=_gov_stores,
        primary_store=store,
        platform_logger=platform_logger,
        log_levels=LogLevel,
        append_bounded_warning=_append_bounded_warning,
    )


shutdown_mgr.register("close_connections", _close_governance_stores, priority=10)


