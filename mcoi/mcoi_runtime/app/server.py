"""Phase 200 - Governed HTTP Server (FastAPI).

Purpose: HTTP boundary for the governed platform. All requests enter governed execution.
    Phase 199: LLM completion, certification, persistence-backed ledger, budget reporting.
    Phase 200: Bootstrap wiring, streaming, certification daemon, Docker Compose.
Dependencies: fastapi, production_surface, llm_bootstrap, streaming, certification_daemon.
Run: uvicorn mcoi_runtime.app.server:app --host 0.0.0.0 --port 8000
"""
from __future__ import annotations
from typing import Any

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
from mcoi_runtime.app.engineering_puzzle_control import EngineeringPuzzleControlSurface
from mcoi_runtime.app.routers.deps import deps
from mcoi_runtime.app.server_app import create_governed_app
from mcoi_runtime.app.server_context import bootstrap_server_context, resolve_env
from mcoi_runtime.app.governed_swarm_integration import mount_governed_swarm_router_from_env
from mcoi_runtime.app.note_memory_integration import mount_note_memory_router_from_env
from mcoi_runtime.app.public_route_integration import mount_public_runtime_routes_from_env
from mcoi_runtime.app.nested_mind_integration import (
    mount_nested_mind_connector_from_env,
    mount_nested_mind_observation_bridge_from_env,
    mount_nested_mind_observation_submitter_from_env,
)
from mcoi_runtime.app.inceptadive_shadow_integration import (
    build_inceptadive_shadow_runtime,
)
from mcoi_runtime.app.operational_math_integration import (
    select_operational_math_receipt_store,
)
from mcoi_runtime.app.organization_kernel_integration import (
    bootstrap_organization_kernel,
)
from mcoi_runtime.app.software_receipt_integration import (
    select_software_receipt_store,
)
from mcoi_runtime.app.finance_approval_integration import (
    select_finance_approval_store,
)
from mcoi_runtime.app.policy_version_integration import (
    select_policy_version_registry,
)
from mcoi_runtime.app.pilot_provision_integration import (
    select_pilot_provision_registry,
)
from mcoi_runtime.app.tool_permission_integration import (
    select_tool_permission_registry,
)
from mcoi_runtime.app.replay_report_integration import (
    select_replay_report_store,
)
from mcoi_runtime.app.artifact_lineage_integration import (
    bootstrap_artifact_lineage,
)
from mcoi_runtime.app.temporal_scheduler_integration import (
    bootstrap_temporal_scheduler,
    maybe_start_temporal_worker,
    select_temporal_scheduler_store,
)
from mcoi_runtime.app.job_conversation_integration import (
    bootstrap_job_conversation_threads,
    record_job_conversation_thread,
)
from mcoi_runtime.app.server_lifecycle import bootstrap_server_lifecycle
from mcoi_runtime.app.server_registry import bootstrap_dependency_registry
from mcoi_runtime.app.server_runtime_stack import bootstrap_server_runtime_stack
from mcoi_runtime.app.cognitive_runtime_integration import (
    bootstrap_cognitive_runtime,
    build_rehydrate_ledger,
    register_cognitive_runtime,
)
from mcoi_runtime.app.cognitive_shadow_integration import (
    SHADOW_OBSERVER_DEP,
    build_shadow_observer,
)
from mcoi_runtime.app.cognitive_live_integration import (
    EXECUTION_GATE_DEP,
    LEARNER_DEP,
    build_execution_gate,
    build_learner,
)
from mcoi_runtime.app.cognitive_planning_integration import (
    PLANNING_READER_DEP,
    build_planning_reader,
)
from mcoi_runtime.app.server_bootstrap import (
    init_field_encryption_from_env as _init_field_encryption_from_env_impl,
    utc_clock as _utc_clock,
)
from mcoi_runtime.app.server_runtime import (
    calculator_handler as _calculator_handler_impl,
    validate_or_raise as _validate_or_raise_impl,
)
from mcoi_runtime.substrate.registry_store import configure_max_tenants_from_env
from mcoi_runtime.app.software_receipt_observability import (
    register_software_receipt_observability,
)
from mcoi_runtime.app.operational_math_observability import (
    register_operational_math_observability,
)
from mcoi_runtime.app.software_receipt_review_queue import SoftwareReceiptReviewQueue
from mcoi_runtime.core.review import ReviewEngine
from mcoi_runtime.core.structured_logging import LogLevel
from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.jobs import JobEngine


def _init_field_encryption_from_env() -> tuple[Any | None, dict[str, Any]]:
    """Build optional field encryption and expose explicit startup posture."""
    return _init_field_encryption_from_env_impl(
        env=os.environ,
        bounded_bootstrap_warning=_bounded_bootstrap_warning,
    )


# Clock
def _clock() -> str:
    return _utc_clock()


def _validate_startup_boundary_policy() -> None:
    """Validate network boundary policy before stateful bootstrap."""
    env = os.environ.get("MULLU_ENV", "local_dev")
    origins = _resolve_cors_origins(os.environ.get("MULLU_CORS_ORIGINS"), env)
    _validate_cors_origins_for_env(origins, env)


_validate_startup_boundary_policy()

# Environment and governance context
_server_context = bootstrap_server_context(
    runtime_env=os.environ,
    clock=_clock,
    env_flag_fn=_env_flag,
    validate_db_backend_for_env=_validate_db_backend_for_env,
    init_field_encryption_from_env_fn=_init_field_encryption_from_env,
)
ENV = _server_context.env
surface = _server_context.surface
_tenant_allow_unknown = _server_context.tenant_allow_unknown
_tenant_registry_max_tenants = configure_max_tenants_from_env(os.environ)
_db_backend = _server_context.db_backend
_db_backend_warning = _server_context.db_backend_warning
store = _server_context.store
_foundation_bootstrap = _server_context.foundation_bootstrap
llm_bootstrap_result = _foundation_bootstrap.llm_bootstrap_result
llm_bridge = llm_bootstrap_result.bridge
certifier = _foundation_bootstrap.certifier
streaming_adapter = _foundation_bootstrap.streaming_adapter
cert_daemon = _foundation_bootstrap.cert_daemon
pii_scanner = _foundation_bootstrap.pii_scanner
content_safety_chain = _foundation_bootstrap.content_safety_chain
proof_bridge = _foundation_bootstrap.proof_bridge
tenant_ledger = _foundation_bootstrap.tenant_ledger
_field_encryptor = _server_context.field_encryptor
_field_encryption_bootstrap = _server_context.field_encryption_bootstrap
_governance_bootstrap = _server_context.governance_bootstrap
_gov_stores = _governance_bootstrap.governance_stores
tenant_budget_mgr = _governance_bootstrap.tenant_budget_mgr
metrics = _governance_bootstrap.metrics
rate_limiter = _governance_bootstrap.rate_limiter
audit_trail = _governance_bootstrap.audit_trail
_jwt_authenticator = _governance_bootstrap.jwt_authenticator
_tenant_gating = _governance_bootstrap.tenant_gating

# Phase 3C: Shell sandbox policy (env-driven profile selection)
shell_policy = _server_context.shell_policy

_runtime_stack = bootstrap_server_runtime_stack(
    clock=_clock,
    env=ENV,
    runtime_env=os.environ,
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
    jwt_authenticator=_jwt_authenticator,
    evaluate_expression_fn=evaluate_expression,
)
_agent_bootstrap = _runtime_stack.agent_bootstrap
_subsystem_bootstrap = _runtime_stack.subsystem_bootstrap
_operational_bootstrap = _runtime_stack.operational_bootstrap
_capability_bootstrap = _runtime_stack.capability_bootstrap
observability = _runtime_stack.observability
access_runtime = _runtime_stack.access_runtime
guard_chain = _runtime_stack.guard_chain
shutdown_mgr = _runtime_stack.shutdown_mgr
state_persistence = _runtime_stack.state_persistence
platform_logger = _operational_bootstrap.platform_logger


def _field_encryption_deep_health() -> dict[str, Any]:
    """Readiness fact for field-level encryption (read-only).

    Reports whether an encryptor is configured and whether AES-GCM is
    actually available. The /ready policy requires AES in pilot/production;
    dev/test only reports it. Registered here (not in server_agents) because
    the encryptor is constructed in the server context, not the agent runtime.
    """
    enc = _field_encryptor
    return {
        "status": "healthy",
        "configured": enc is not None,
        "aes_available": bool(getattr(enc, "aes_available", False)),
    }


# The field-encryption probe shares the same DeepHealthChecker instance that
# is registered into ``deps`` as ``deep_health`` (server_registry reads
# ``agent_bootstrap.deep_health``), so /ready and /api/v1/health/deep see it.
_agent_bootstrap.deep_health.register("field_encryption", _field_encryption_deep_health)


def _validate_or_raise(schema_id: str, data: dict[str, Any]) -> None:
    """Validate request data against a schema; raise 422 if invalid."""
    _validate_or_raise_impl(
        input_validator=_operational_bootstrap.input_validator,
        schema_id=schema_id,
        data=data,
    )


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


# =============================================================================
# Dependency injection - register all subsystems into deps container
# =============================================================================
_policy_version_registry_bootstrap = select_policy_version_registry(os.environ)
_pilot_provision_registry_bootstrap = select_pilot_provision_registry(os.environ)
_tool_permission_registry_bootstrap = select_tool_permission_registry(os.environ)
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
    policy_version_registry=_policy_version_registry_bootstrap.registry,
    pilot_provision_registry=_pilot_provision_registry_bootstrap.registry,
    tool_permission_registry=_tool_permission_registry_bootstrap.registry,
)
platform = _dependency_bootstrap.platform
deps.set("policy_version_registry_bootstrap", _policy_version_registry_bootstrap)
deps.set("pilot_provision_registry_bootstrap", _pilot_provision_registry_bootstrap)
deps.set("tool_permission_registry_bootstrap", _tool_permission_registry_bootstrap)
deps.set("job_engine", JobEngine(clock=_clock))
_job_conversation_bootstrap = bootstrap_job_conversation_threads(os.environ)
deps.set("job_conversation_threads", _job_conversation_bootstrap.thread_index)
deps.set(
    "record_job_conversation_thread",
    lambda thread: record_job_conversation_thread(
        _job_conversation_bootstrap.thread_index,
        thread,
        _job_conversation_bootstrap.store,
    ),
)
if _job_conversation_bootstrap.store is not None:
    deps.set("job_conversation_thread_store", _job_conversation_bootstrap.store)
if _job_conversation_bootstrap.save_on_shutdown is not None:
    shutdown_mgr.register(
        "save_job_conversation_threads",
        _job_conversation_bootstrap.save_on_shutdown,
        priority=80,
    )

# Cognitive organs (live wiring, Slice 1): mount the reasoning/learning engines
# into the SERVED runtime (historically CLI-bootstrap only) and register them on
# deps so live paths CAN consult them. With MULLU_COGNITIVE_LOOP_LEDGER=1, the
# D1 ledger is validated + replayed BEFORE deps are published; corruption, timeout,
# or missing required path fails startup closed.
_cognitive_rehydrate_ledger = build_rehydrate_ledger(os.environ)
_cognitive_runtime = bootstrap_cognitive_runtime(
    clock=_clock,
    ledger=_cognitive_rehydrate_ledger,
)
register_cognitive_runtime(deps, _cognitive_runtime)

# Record-only cognitive shadow observer (live wiring, Slice 2): default-OFF via
# MULLU_COGNITIVE_LOOP_SHADOW. None when disabled (or malformed flag — fail-safe).
# It holds NO authority over any response; routers record observations through the
# exception-isolated record_execution_shadow entrypoint.
_cognitive_shadow_observer = build_shadow_observer(os.environ, _cognitive_runtime, clock=_clock)
deps.set(SHADOW_OBSERVER_DEP, _cognitive_shadow_observer)

# Live-acting cognitive components (live wiring, Stage B + C), both default-OFF:
#  - Stage B enforce gate (MULLU_COGNITIVE_LOOP_ENFORCE): may WITHHOLD a dispatch on a
#    blocking DECIDE verdict. fail-OPEN, safety-positive (it can only ever refuse).
#  - Stage C learner (MULLU_COGNITIVE_LOOP_LEARN): feeds live outcomes back into the
#    organs (confidence + episodic), deterministic + rollback-safe.
# Both None when disabled => byte-identical live path. See COGNITIVE_LOOP_LIVE_WIRING.md.
_cognitive_execution_gate = build_execution_gate(os.environ, _cognitive_runtime)
deps.set(EXECUTION_GATE_DEP, _cognitive_execution_gate)
_cognitive_learner = build_learner(os.environ, _cognitive_runtime, clock=_clock)
deps.set(LEARNER_DEP, _cognitive_learner)

# Plan-time cognitive context reader (read-back, default-OFF via
# MULLU_COGNITIVE_LOOP_PLAN_CONTEXT): when enabled, plan-compilation routers attach a
# read-only learned-context advisory for the plan's capabilities. None when disabled
# => byte-identical responses. Read-only: never writes organs, never mutates plans.
_cognitive_planning_reader = build_planning_reader(os.environ, _cognitive_runtime)
deps.set(PLANNING_READER_DEP, _cognitive_planning_reader)

_shadow_runtime = build_inceptadive_shadow_runtime(os.environ)
deps.set("inceptadive_shadow_runtime", _shadow_runtime)

_software_receipt_bootstrap = select_software_receipt_store(os.environ)
software_receipt_store = _software_receipt_bootstrap.store
review_engine = ReviewEngine(clock=_clock)
software_receipt_review_queue = SoftwareReceiptReviewQueue(
    review_engine=review_engine,
    receipt_store=software_receipt_store,
)
deps.set("software_receipt_store", software_receipt_store)
deps.set("review_engine", review_engine)
deps.set("software_receipt_review_queue", software_receipt_review_queue)
register_software_receipt_observability(
    observability=observability,
    receipt_store=software_receipt_store,
)

_operational_math_bootstrap = select_operational_math_receipt_store(os.environ)
operational_math_receipt_store = _operational_math_bootstrap.store
deps.set("operational_math_receipt_store", operational_math_receipt_store)
register_operational_math_observability(
    observability=observability,
    receipt_store=operational_math_receipt_store,
)

_replay_report_bootstrap = select_replay_report_store(os.environ)
replay_report_store = _replay_report_bootstrap.store
deps.set("replay_report_store", replay_report_store)

_temporal_store_bootstrap = select_temporal_scheduler_store(os.environ)
temporal_scheduler_store = _temporal_store_bootstrap.store
_temporal_bootstrap = bootstrap_temporal_scheduler(temporal_scheduler_store, clock=_clock)
temporal_event_spine = _temporal_bootstrap.event_spine
temporal_runtime = _temporal_bootstrap.runtime
temporal_scheduler = _temporal_bootstrap.scheduler
temporal_action_handlers = _temporal_bootstrap.action_handlers
_temporal_worker_bootstrap = maybe_start_temporal_worker(
    os.environ,
    scheduler=temporal_scheduler,
    store=temporal_scheduler_store,
    action_handlers=temporal_action_handlers,
    proof_bridge=proof_bridge,
)
temporal_scheduler_background = _temporal_worker_bootstrap.background
if temporal_scheduler_background is not None:
    shutdown_mgr.register(
        "stop_temporal_scheduler",
        temporal_scheduler_background.stop,
        priority=95,
    )
deps.set("temporal_event_spine", temporal_event_spine)
deps.set("temporal_runtime", temporal_runtime)
deps.set("temporal_scheduler", temporal_scheduler)
deps.set("temporal_scheduler_store", temporal_scheduler_store)
deps.set("temporal_action_handlers", temporal_action_handlers)
if temporal_scheduler_background is not None:
    deps.set("temporal_scheduler_background", temporal_scheduler_background)

engineering_puzzle_event_spine = EventSpineEngine(clock=_clock)
engineering_puzzle_control = EngineeringPuzzleControlSurface(engineering_puzzle_event_spine)
deps.set("engineering_puzzle_event_spine", engineering_puzzle_event_spine)
deps.set("engineering_puzzle_control", engineering_puzzle_control)

_finance_approval_bootstrap = select_finance_approval_store(os.environ)
finance_approval_store = _finance_approval_bootstrap.store
deps.set("finance_approval_store", finance_approval_store)

_organization_kernel_bootstrap = bootstrap_organization_kernel(os.environ, clock=_clock)
organization_kernel = _organization_kernel_bootstrap.kernel
organization_kernel_store = _organization_kernel_bootstrap.store
deps.set("organization_kernel", organization_kernel)
if organization_kernel_store is not None:
    deps.set("organization_kernel_store", organization_kernel_store)

_artifact_lineage_bootstrap = bootstrap_artifact_lineage(os.environ, clock=_clock)
artifact_lineage = _artifact_lineage_bootstrap.dag
artifact_lineage_store = _artifact_lineage_bootstrap.store
deps.set("artifact_lineage", artifact_lineage)
if artifact_lineage_store is not None:
    deps.set("artifact_lineage_store", artifact_lineage_store)
if _artifact_lineage_bootstrap.save_on_shutdown is not None:
    shutdown_mgr.register(
        "save_artifact_lineage",
        _artifact_lineage_bootstrap.save_on_shutdown,
        priority=80,
    )

public_runtime_route_bootstrap = mount_public_runtime_routes_from_env(
    app=app,
    runtime_env=os.environ,
    clock=_clock,
)
deps.set("public_runtime_route_bootstrap", public_runtime_route_bootstrap)
deps.set("simple_platform_bootstrap", public_runtime_route_bootstrap.simple_platform)
deps.set(
    "operational_dashboard_bootstrap",
    public_runtime_route_bootstrap.operational_dashboard,
)

governed_swarm_bootstrap = mount_governed_swarm_router_from_env(
    app=app,
    runtime_env=os.environ,
)
deps.set("governed_swarm_bootstrap", governed_swarm_bootstrap)

note_memory_bootstrap = mount_note_memory_router_from_env(
    app=app,
    runtime_env=os.environ,
)
deps.set("note_memory_bootstrap", note_memory_bootstrap)

nested_mind_bootstrap = mount_nested_mind_connector_from_env(
    runtime_env=os.environ,
    clock=_clock,
)
deps.set("nested_mind_bootstrap", nested_mind_bootstrap)
if nested_mind_bootstrap.connector is not None:
    deps.set("nested_mind_connector", nested_mind_bootstrap.connector)

nested_mind_observation_bridge_bootstrap = mount_nested_mind_observation_bridge_from_env(
    runtime_env=os.environ,
    clock=_clock,
)
deps.set(
    "nested_mind_observation_bridge_bootstrap",
    nested_mind_observation_bridge_bootstrap,
)
deps.set(
    "nested_mind_observation_bridge_planner",
    nested_mind_observation_bridge_bootstrap.planner,
)

nested_mind_observation_submitter_bootstrap = mount_nested_mind_observation_submitter_from_env(
    runtime_env=os.environ,
    clock=_clock,
)
deps.set(
    "nested_mind_observation_submitter_bootstrap",
    nested_mind_observation_submitter_bootstrap,
)
if nested_mind_observation_submitter_bootstrap.submitter is not None:
    deps.set(
        "nested_mind_observation_submitter",
        nested_mind_observation_submitter_bootstrap.submitter,
    )

from mcoi_runtime.core.god_mode_integration import install_god_mode  # noqa: E402

god_mode_engine = install_god_mode(deps, audit_trail=audit_trail)
deps.set("god_mode_engine", god_mode_engine)


# =============================================================================
# Include routers - all route handlers live in routers/ modules
# =============================================================================

_lifecycle_bootstrap = bootstrap_server_lifecycle(
    app=app,
    shutdown_mgr=shutdown_mgr,
    tenant_budget_mgr=lambda: tenant_budget_mgr,
    state_persistence=lambda: state_persistence,
    audit_trail=lambda: audit_trail,
    cost_analytics=lambda: _operational_bootstrap.cost_analytics,
    platform_logger=lambda: platform_logger,
    log_levels=LogLevel,
    append_bounded_warning=_append_bounded_warning,
    governance_stores=lambda: _gov_stores,
    primary_store=lambda: store,
    # v4.26.0 (audit P0 fix): wire MUSIA-side auth resolver. See
    # bootstrap_server_lifecycle docstring + RELEASE_NOTES_v4.26.0.md.
    api_key_mgr=_operational_bootstrap.api_key_mgr,
    jwt_authenticator=_jwt_authenticator,
    # v4.35.0 (audit F5): unified env resolution with fail-closed
    # support via MULLU_ENV_REQUIRED. See server_context.resolve_env.
    env=resolve_env(os.environ),
)
_flush_state_on_shutdown = _lifecycle_bootstrap.flush_state_on_shutdown
_restore_state_on_startup = _lifecycle_bootstrap.restore_state_on_startup
_close_governance_stores = _lifecycle_bootstrap.close_governance_stores
_startup_restored = _lifecycle_bootstrap.startup_restored
