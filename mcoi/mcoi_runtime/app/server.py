"""Phase 200 â€” Governed HTTP Server (FastAPI).

Purpose: HTTP boundary for the governed platform. All requests enter governed execution.
    Phase 199: LLM completion, certification, persistence-backed ledger, budget reporting.
    Phase 200: Bootstrap wiring, streaming, certification daemon, Docker Compose.
Dependencies: fastapi, production_surface, llm_bootstrap, streaming, certification_daemon.
Run: uvicorn mcoi_runtime.app.server:app --host 0.0.0.0 --port 8000
"""
from __future__ import annotations
from typing import Any

from mcoi_runtime.app.production_surface import (
    ProductionSurface, DEPLOYMENT_MANIFESTS,
)
from mcoi_runtime.core.safe_arithmetic import evaluate_expression

import os

from mcoi_runtime.app.server_policy import (
    _append_bounded_warning,
    _bounded_bootstrap_warning,
    _env_flag,
    _resolve_cors_origins,
    _validate_cors_origins_for_env,
    _validate_db_backend_for_env,
)
from mcoi_runtime.app.server_platform import (
    bootstrap_governance_runtime,
    bootstrap_primary_store,
)
from mcoi_runtime.app.server_agents import bootstrap_agent_runtime
from mcoi_runtime.app.server_app import create_governed_app
from mcoi_runtime.app.server_capabilities import bootstrap_capability_services
from mcoi_runtime.app.server_lifecycle import bootstrap_server_lifecycle
from mcoi_runtime.app.server_registry import bootstrap_dependency_registry
from mcoi_runtime.app.server_services import bootstrap_operational_services
from mcoi_runtime.app.server_subsystems import bootstrap_subsystems
from mcoi_runtime.app.server_bootstrap import (
    init_field_encryption_from_env as _init_field_encryption_from_env_impl,
    utc_clock as _utc_clock,
)
from mcoi_runtime.app.server_foundation import bootstrap_foundation_services
from mcoi_runtime.app.server_runtime import (
    build_default_input_validator,
    calculator_handler as _calculator_handler_impl,
    register_default_output_schemas,
    register_default_tools,
    validate_or_raise as _validate_or_raise_impl,
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

# Phase 200 foundation services
_foundation_bootstrap = bootstrap_foundation_services(
    clock=_clock,
    runtime_env=os.environ,
    store=store,
)
llm_bootstrap_result = _foundation_bootstrap.llm_bootstrap_result
llm_bridge = llm_bootstrap_result.bridge
certifier = _foundation_bootstrap.certifier
streaming_adapter = _foundation_bootstrap.streaming_adapter
cert_daemon = _foundation_bootstrap.cert_daemon
pii_scanner = _foundation_bootstrap.pii_scanner
content_safety_chain = _foundation_bootstrap.content_safety_chain
proof_bridge = _foundation_bootstrap.proof_bridge
tenant_ledger = _foundation_bootstrap.tenant_ledger

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

# Phase 3C: Shell sandbox policy (env-driven profile selection)
shell_policy = _governance_bootstrap.shell_policy

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

app = create_governed_app(
    env=ENV,
    cors_origins_raw=os.environ.get("MULLU_CORS_ORIGINS"),
    guard_chain=guard_chain,
    metrics=metrics,
    proof_bridge=proof_bridge,
    audit_trail=audit_trail,
    pii_scanner=pii_scanner,
    platform_logger=platform_logger,
    log_levels=LogLevel,
    shutdown_mgr=shutdown_mgr,
    resolve_cors_origins=_resolve_cors_origins,
    validate_cors_origins_for_env=_validate_cors_origins_for_env,
)


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# Dependency injection â€” register all subsystems into deps container
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

from mcoi_runtime.app.routers.deps import deps

_dependency_bootstrap = bootstrap_dependency_registry(
    deps_container=deps,
    clock=_clock,
    env=ENV,
    surface=surface,
    store=store,
    llm_bootstrap_result=llm_bootstrap_result,
    streaming_adapter=streaming_adapter,
    proof_bridge=proof_bridge,
    pii_scanner=pii_scanner,
    content_safety_chain=content_safety_chain,
    field_encryption_bootstrap=_field_encryption_bootstrap,
    tenant_ledger=tenant_ledger,
    certifier=certifier,
    cert_daemon=cert_daemon,
    governance_bootstrap=_governance_bootstrap,
    agent_bootstrap=_agent_bootstrap,
    subsystem_bootstrap=_subsystem_bootstrap,
    operational_bootstrap=_operational_bootstrap,
    capability_bootstrap=_capability_bootstrap,
)
platform = _dependency_bootstrap.platform


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# Include routers â€” all route handlers live in routers/ modules
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

_lifecycle_bootstrap = bootstrap_server_lifecycle(
    app=app,
    shutdown_mgr=shutdown_mgr,
    tenant_budget_mgr=lambda: tenant_budget_mgr,
    state_persistence=lambda: state_persistence,
    audit_trail=lambda: audit_trail,
    cost_analytics=lambda: cost_analytics,
    platform_logger=lambda: platform_logger,
    log_levels=LogLevel,
    append_bounded_warning=_append_bounded_warning,
    governance_stores=lambda: _gov_stores,
    primary_store=lambda: store,
)
_flush_state_on_shutdown = _lifecycle_bootstrap.flush_state_on_shutdown
_restore_state_on_startup = _lifecycle_bootstrap.restore_state_on_startup
_close_governance_stores = _lifecycle_bootstrap.close_governance_stores
_startup_restored = _lifecycle_bootstrap.startup_restored


