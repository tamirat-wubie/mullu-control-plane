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
from mcoi_runtime.app.server_capabilities import bootstrap_capability_services
from mcoi_runtime.app.server_services import bootstrap_operational_services
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

explanation_engine = _subsystem_bootstrap.explanation_engine
audit_anchor = _subsystem_bootstrap.audit_anchor
knowledge_graph = _subsystem_bootstrap.knowledge_graph
event_bus = _subsystem_bootstrap.event_bus
batch_pipeline = _subsystem_bootstrap.batch_pipeline

from mcoi_runtime.app.middleware import GovernanceMiddleware
from mcoi_runtime.core.structured_logging import LogLevel

_operational_bootstrap = bootstrap_operational_services(
    clock=_clock,
    env=ENV,
    runtime_env=os.environ,
    cert_daemon=cert_daemon,
    workflow_engine=workflow_engine,
    event_bus=event_bus,
    observability=observability,
    audit_trail=audit_trail,
    metrics=metrics,
    tenant_budget_mgr=tenant_budget_mgr,
    rate_limiter=rate_limiter,
    jwt_authenticator=_jwt_authenticator,
    tenant_gating=_tenant_gating,
    access_runtime=access_runtime,
    content_safety_chain=content_safety_chain,
)
plugin_registry = _operational_bootstrap.plugin_registry
guard_chain = _operational_bootstrap.guard_chain
replay_recorder = _operational_bootstrap.replay_recorder
traced_workflow = _operational_bootstrap.traced_workflow
conversation_store = _operational_bootstrap.conversation_store
schema_validator = _operational_bootstrap.schema_validator
prompt_engine = _operational_bootstrap.prompt_engine
cost_analytics = _operational_bootstrap.cost_analytics
chat_workflow = _operational_bootstrap.chat_workflow
health_agg = _operational_bootstrap.health_agg
api_versions = _operational_bootstrap.api_versions
grafana_dashboard = _operational_bootstrap.grafana_dashboard
request_tracer = _operational_bootstrap.request_tracer
agent_orchestrator = _operational_bootstrap.agent_orchestrator
rate_limit_headers = _operational_bootstrap.rate_limit_headers
webhook_retry = _operational_bootstrap.webhook_retry
config_watcher = _operational_bootstrap.config_watcher
platform_logger = _operational_bootstrap.platform_logger
api_key_mgr = _operational_bootstrap.api_key_mgr
data_export = _operational_bootstrap.data_export
sla_monitor = _operational_bootstrap.sla_monitor
notification_dispatcher = _operational_bootstrap.notification_dispatcher
tenant_isolation = _operational_bootstrap.tenant_isolation
input_validator = _operational_bootstrap.input_validator
prom_exporter = _operational_bootstrap.prom_exporter
health_agg_v2 = _operational_bootstrap.health_agg_v2
idempotency_store = _operational_bootstrap.idempotency_store
response_compressor = _operational_bootstrap.response_compressor
canary_controller = _operational_bootstrap.canary_controller
secret_rotation = _operational_bootstrap.secret_rotation
request_dedup = _operational_bootstrap.request_dedup
snapshot_mgr = _operational_bootstrap.snapshot_mgr
otel_exporter = _operational_bootstrap.otel_exporter
circuit_dashboard = _operational_bootstrap.circuit_dashboard
tenant_quota = _operational_bootstrap.tenant_quota
deploy_checker = _operational_bootstrap.deploy_checker
api_migration = _operational_bootstrap.api_migration
retry_engine = _operational_bootstrap.retry_engine
region_router = _operational_bootstrap.region_router
config_drift = _operational_bootstrap.config_drift
request_ctx_factory = _operational_bootstrap.request_ctx_factory
tenant_partitions = _operational_bootstrap.tenant_partitions
health_v3 = _operational_bootstrap.health_v3


def _validate_or_raise(schema_id: str, data: dict[str, Any]) -> None:
    """Validate request data against a schema; raise 422 if invalid."""
    _validate_or_raise_impl(
        input_validator=input_validator,
        schema_id=schema_id,
        data=data,
    )

_capability_bootstrap = bootstrap_capability_services(
    clock=_clock,
    runtime_env=os.environ,
    llm_bridge=llm_bridge,
    observability=observability,
    tenant_budget_mgr=tenant_budget_mgr,
    evaluate_expression_fn=evaluate_expression,
)
tool_registry = _capability_bootstrap.tool_registry
structured_output = _capability_bootstrap.structured_output
state_persistence = _capability_bootstrap.state_persistence
llm_circuit = _capability_bootstrap.llm_circuit
tool_agent = _capability_bootstrap.tool_agent
model_router = _capability_bootstrap.model_router
correlation_mgr = _capability_bootstrap.correlation_mgr
shutdown_mgr = _capability_bootstrap.shutdown_mgr
agent_chain = _capability_bootstrap.agent_chain
monitor = _capability_bootstrap.monitor
task_queue = _capability_bootstrap.task_queue
agent_memory = _capability_bootstrap.agent_memory
ab_engine = _capability_bootstrap.ab_engine
isolation_verifier = _capability_bootstrap.isolation_verifier
usage_reporter = _capability_bootstrap.usage_reporter
dep_graph = _capability_bootstrap.dep_graph
backpressure = _capability_bootstrap.backpressure
governed_cache = _capability_bootstrap.governed_cache
feature_flags = _capability_bootstrap.feature_flags
semantic_search = _capability_bootstrap.semantic_search
tenant_analytics = _capability_bootstrap.tenant_analytics
wf_templates = _capability_bootstrap.wf_templates
event_store = _capability_bootstrap.event_store


def _calculator_handler(args: dict[str, Any]) -> dict[str, str]:
    return _calculator_handler_impl(
        args,
        evaluate_expression_fn=evaluate_expression,
    )

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


