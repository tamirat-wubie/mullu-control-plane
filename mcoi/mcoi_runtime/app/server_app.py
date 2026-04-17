"""FastAPI shell bootstrap helpers for the governed HTTP server.

Purpose: isolate app lifespan and boundary middleware/bootstrap wiring from
the main server module.
Governance scope: [OCE, CDCV, CQTE, UWMA]
Dependencies: FastAPI, governance middleware, and HTTP boundary helpers.
Invariants:
  - App metadata stays stable across extractions.
  - Guard middleware wiring preserves audit, proof, and metric hooks.
  - CORS and global exception boundaries stay configured before router mount.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
import warnings
from typing import Any, Callable

from fastapi import FastAPI

from mcoi_runtime.app.middleware import GovernanceMiddleware
from mcoi_runtime.app.server_http import (
    configure_cors_middleware,
    install_global_exception_handler,
)


def build_app_lifespan(*, shutdown_mgr: Any) -> Callable[[FastAPI], Any]:
    """Build the governed application lifespan handler."""

    @asynccontextmanager
    async def _app_lifespan(_app: FastAPI):
        try:
            yield
        finally:
            shutdown_mgr.execute()

    return _app_lifespan


def create_governed_app(
    *,
    env: str,
    cors_origins_raw: str | None,
    guard_chain: Any,
    metrics: Any,
    proof_bridge: Any,
    audit_trail: Any,
    pii_scanner: Any,
    platform_logger: Any,
    log_levels: Any,
    shutdown_mgr: Any,
    resolve_cors_origins: Callable[[str | None, str], list[str]],
    validate_cors_origins_for_env: Callable[[list[str], str], str | None],
    fastapi_cls: type[FastAPI] = FastAPI,
    governance_middleware_cls: type[Any] = GovernanceMiddleware,
    configure_cors_middleware_fn: Callable[..., None] = configure_cors_middleware,
    install_global_exception_handler_fn: Callable[..., None] = install_global_exception_handler,
    warnings_module: Any = warnings,
    lifespan_factory: Callable[..., Callable[[FastAPI], Any]] = build_app_lifespan,
) -> FastAPI:
    """Create the governed FastAPI shell and wire boundary concerns."""
    app = fastapi_cls(
        title="Mullu Platform",
        version="3.13.0",
        description="Governed AI Operating System",
        lifespan=lifespan_factory(shutdown_mgr=shutdown_mgr),
    )

    app.add_middleware(
        governance_middleware_cls,
        guard_chain=guard_chain,
        metrics_fn=lambda name, val: metrics.inc(name, val),
        proof_bridge=proof_bridge,
        on_reject=lambda ctx: audit_trail.record(
            action="guard.rejected",
            actor_id="system",
            tenant_id=ctx.get("tenant_id", ""),
            target=ctx.get("path", ""),
            outcome="denied",
            detail=pii_scanner.scan_dict(ctx)[0] if pii_scanner.enabled else ctx,
        ),
        on_allow=lambda ctx: audit_trail.record(
            action="guard.allowed",
            actor_id=ctx.get("tenant_id", "system"),
            tenant_id=ctx.get("tenant_id", ""),
            target=ctx.get("path", ""),
            outcome="success",
        ),
    )

    configure_cors_middleware_fn(
        app=app,
        env=env,
        cors_origins_raw=cors_origins_raw,
        resolve_cors_origins=resolve_cors_origins,
        validate_cors_origins_for_env=validate_cors_origins_for_env,
        warnings_module=warnings_module,
    )

    install_global_exception_handler_fn(
        app=app,
        metrics=metrics,
        platform_logger=platform_logger,
        log_levels=log_levels,
    )

    return app
