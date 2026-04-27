"""Lifecycle bootstrap helpers for the governed HTTP server.

Purpose: isolate final router inclusion and startup/shutdown registration from
the main server module.
Governance scope: [OCE, CDCV, CQTE, UWMA]
Dependencies: router inclusion and persisted state/governance close helpers.
Invariants:
  - Default routers are mounted before lifecycle registration completes.
  - Startup restore executes once during bootstrap.
  - Shutdown handlers preserve names, priorities, and bounded warning hooks.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from mcoi_runtime.app.server_http import include_default_routers
from mcoi_runtime.app.server_state import (
    close_governance_stores as _close_governance_stores_impl,
    flush_state_on_shutdown as _flush_state_on_shutdown_impl,
    restore_state_on_startup as _restore_state_on_startup_impl,
)


@dataclass(frozen=True)
class ServerLifecycleBootstrap:
    """Lifecycle bootstrap result."""

    flush_state_on_shutdown: Callable[[], Any]
    restore_state_on_startup: Callable[[], Any]
    close_governance_stores: Callable[[], Any]
    startup_restored: Any


def _as_getter(value: Any) -> Callable[[], Any]:
    """Normalize a value or zero-arg provider into a getter."""
    if callable(value):
        return value
    return lambda: value


def bootstrap_server_lifecycle(
    *,
    app: Any,
    shutdown_mgr: Any,
    tenant_budget_mgr: Any,
    state_persistence: Any,
    audit_trail: Any,
    cost_analytics: Any,
    platform_logger: Any,
    log_levels: Any,
    append_bounded_warning: Callable[..., Any],
    governance_stores: Any,
    primary_store: Any,
    api_key_mgr: Any = None,
    jwt_authenticator: Any = None,
    env: str = "local_dev",
    include_default_routers_fn: Callable[[Any], None] = include_default_routers,
    flush_state_on_shutdown_impl: Callable[..., Any] = _flush_state_on_shutdown_impl,
    restore_state_on_startup_impl: Callable[..., Any] = _restore_state_on_startup_impl,
    close_governance_stores_impl: Callable[..., Any] = _close_governance_stores_impl,
) -> ServerLifecycleBootstrap:
    """Mount routers and register startup/shutdown lifecycle helpers."""
    tenant_budget_mgr_getter = _as_getter(tenant_budget_mgr)
    state_persistence_getter = _as_getter(state_persistence)
    audit_trail_getter = _as_getter(audit_trail)
    cost_analytics_getter = _as_getter(cost_analytics)
    platform_logger_getter = _as_getter(platform_logger)
    governance_stores_getter = _as_getter(governance_stores)
    primary_store_getter = _as_getter(primary_store)

    def flush_state_on_shutdown() -> Any:
        return flush_state_on_shutdown_impl(
            tenant_budget_mgr=tenant_budget_mgr_getter(),
            state_persistence=state_persistence_getter(),
            audit_trail=audit_trail_getter(),
            cost_analytics=cost_analytics_getter(),
            platform_logger=platform_logger_getter(),
            log_levels=log_levels,
            append_bounded_warning=append_bounded_warning,
        )

    def restore_state_on_startup() -> Any:
        return restore_state_on_startup_impl(
            tenant_budget_mgr=tenant_budget_mgr_getter(),
            state_persistence=state_persistence_getter(),
            platform_logger=platform_logger_getter(),
            log_levels=log_levels,
            append_bounded_warning=append_bounded_warning,
        )

    def close_governance_stores() -> Any:
        return close_governance_stores_impl(
            governance_stores=governance_stores_getter(),
            primary_store=primary_store_getter(),
            platform_logger=platform_logger_getter(),
            log_levels=log_levels,
            append_bounded_warning=append_bounded_warning,
        )

    # v4.26.0 (audit P0 fix): wire MUSIA-side auth resolver. Pre-v4.26 the
    # bootstrap path never called configure_musia_auth(...), so every
    # MUSIA endpoint (constructs, domains, cognition, ucja, mfidel,
    # musia/*) accepted unauthenticated wildcard-scope requests in any
    # default deployment. Now the resolver shares the same APIKeyManager
    # and JWT authenticator stack as the HTTP-side guard chain.
    from mcoi_runtime.app.routers.musia_auth import (
        configure_musia_auth,
        configure_musia_dev_mode,
        configure_musia_jwt,
    )
    if api_key_mgr is not None:
        configure_musia_auth(api_key_mgr)
    if jwt_authenticator is not None:
        configure_musia_jwt(jwt_authenticator)
    # Dev wildcard branch is allowed only when env is local_dev/test AND
    # nothing real was wired. In pilot/production the resolver fails
    # closed (503 musia_auth_not_configured) instead of degrading.
    musia_auth_wired = api_key_mgr is not None or jwt_authenticator is not None
    configure_musia_dev_mode(
        not musia_auth_wired and env in ("local_dev", "test")
    )

    include_default_routers_fn(app)
    startup_restored = restore_state_on_startup()

    shutdown_mgr.register("save_state", flush_state_on_shutdown, priority=100)
    shutdown_mgr.register("flush_metrics", lambda: {"flushed": True}, priority=90)
    shutdown_mgr.register("close_connections", close_governance_stores, priority=10)

    return ServerLifecycleBootstrap(
        flush_state_on_shutdown=flush_state_on_shutdown,
        restore_state_on_startup=restore_state_on_startup,
        close_governance_stores=close_governance_stores,
        startup_restored=startup_restored,
    )
