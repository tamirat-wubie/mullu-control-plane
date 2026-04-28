"""Phase 200 â€” Governed HTTP Server (FastAPI).

Purpose: HTTP boundary for the governed platform. All requests enter governed execution.
    Phase 199: LLM completion, certification, persistence-backed ledger, budget reporting.
    Phase 200: Bootstrap wiring, streaming, certification daemon, Docker Compose.
Dependencies: fastapi, production_surface, llm_bootstrap, streaming, certification_daemon.
Run: uvicorn mcoi_runtime.app.server:app --host 0.0.0.0 --port 8000
"""
from __future__ import annotations
from pathlib import Path
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
from mcoi_runtime.app.routers.deps import deps
from mcoi_runtime.app.server_app import create_governed_app
from mcoi_runtime.app.server_context import bootstrap_server_context, resolve_env
from mcoi_runtime.app.server_lifecycle import bootstrap_server_lifecycle
from mcoi_runtime.app.server_registry import bootstrap_dependency_registry
from mcoi_runtime.app.server_runtime_stack import bootstrap_server_runtime_stack
from mcoi_runtime.app.server_bootstrap import (
    init_field_encryption_from_env as _init_field_encryption_from_env_impl,
    utc_clock as _utc_clock,
)
from mcoi_runtime.app.server_runtime import (
    calculator_handler as _calculator_handler_impl,
    validate_or_raise as _validate_or_raise_impl,
)
from mcoi_runtime.app.software_receipt_observability import (
    register_software_receipt_observability,
)
from mcoi_runtime.core.structured_logging import LogLevel
from mcoi_runtime.persistence.software_change_receipt_store import (
    FileSoftwareChangeReceiptStore,
    SoftwareChangeReceiptStore,
)

def _init_field_encryption_from_env() -> tuple[Any | None, dict[str, Any]]:
    """Build optional field encryption and expose explicit startup posture."""
    return _init_field_encryption_from_env_impl(
        env=os.environ,
        bounded_bootstrap_warning=_bounded_bootstrap_warning,
    )


# Clock
def _clock() -> str:
    return _utc_clock()

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


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# Dependency injection â€” register all subsystems into deps container
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

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

_software_receipt_store_path = os.environ.get("MULLU_SOFTWARE_RECEIPT_STORE_PATH")
software_receipt_store = (
    FileSoftwareChangeReceiptStore(Path(_software_receipt_store_path))
    if _software_receipt_store_path
    else SoftwareChangeReceiptStore()
)
deps.set("software_receipt_store", software_receipt_store)
register_software_receipt_observability(
    observability=observability,
    receipt_store=software_receipt_store,
)


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# Include routers â€” all route handlers live in routers/ modules
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

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


