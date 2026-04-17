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
    include_default_routers_fn: Callable[[Any], None] = include_default_routers,
    flush_state_on_shutdown_impl: Callable[..., Any] = _flush_state_on_shutdown_impl,
    restore_state_on_startup_impl: Callable[..., Any] = _restore_state_on_startup_impl,
    close_governance_stores_impl: Callable[..., Any] = _close_governance_stores_impl,
) -> ServerLifecycleBootstrap:
    """Mount routers and register startup/shutdown lifecycle helpers."""

    def flush_state_on_shutdown() -> Any:
        return flush_state_on_shutdown_impl(
            tenant_budget_mgr=tenant_budget_mgr,
            state_persistence=state_persistence,
            audit_trail=audit_trail,
            cost_analytics=cost_analytics,
            platform_logger=platform_logger,
            log_levels=log_levels,
            append_bounded_warning=append_bounded_warning,
        )

    def restore_state_on_startup() -> Any:
        return restore_state_on_startup_impl(
            tenant_budget_mgr=tenant_budget_mgr,
            state_persistence=state_persistence,
            platform_logger=platform_logger,
            log_levels=log_levels,
            append_bounded_warning=append_bounded_warning,
        )

    def close_governance_stores() -> Any:
        return close_governance_stores_impl(
            governance_stores=governance_stores,
            primary_store=primary_store,
            platform_logger=platform_logger,
            log_levels=log_levels,
            append_bounded_warning=append_bounded_warning,
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
