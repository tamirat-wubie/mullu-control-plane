"""HTTP bootstrap helpers for the governed server.

Purpose: isolate HTTP-boundary middleware, exception handling, and router mounting.
Governance scope: [OCE, CDCV, CQTE, UWMA]
Dependencies: FastAPI, Starlette, bounded startup policy helpers, router modules.
Invariants: CORS policy remains fail-closed outside dev, internal exception detail stays bounded, router set is deterministic.
"""
from __future__ import annotations

from typing import Any, Callable

from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request as StarletteRequest
from starlette.responses import JSONResponse as StarletteJSONResponse


def configure_cors_middleware(
    *,
    app: FastAPI,
    env: str,
    cors_origins_raw: str | None,
    resolve_cors_origins: Callable[[str | None, str], list[str]],
    validate_cors_origins_for_env: Callable[[list[str], str], str | None],
    warnings_module: Any,
) -> None:
    """Install governed CORS middleware with environment-aware validation."""
    cors_origins = resolve_cors_origins(cors_origins_raw, env)
    cors_warning = validate_cors_origins_for_env(cors_origins, env)
    if cors_warning:
        warnings_module.warn(cors_warning, stacklevel=1)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins or ["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-Id", "X-Governed"],
    )


def install_global_exception_handler(
    *,
    app: FastAPI,
    metrics: Any,
    platform_logger: Any,
    log_levels: Any,
) -> None:
    """Register the bounded global exception handler."""

    async def global_exception_handler(
        request: StarletteRequest,
        exc: Exception,
    ) -> StarletteJSONResponse:
        metrics.inc("errors_total")
        platform_logger.log(
            log_levels.ERROR,
            f"Unhandled exception on {request.url.path}: {type(exc).__name__}",
        )
        return StarletteJSONResponse(
            status_code=500,
            content={
                "error": "Internal server error",
                "governed": True,
            },
        )

    app.add_exception_handler(Exception, global_exception_handler)


def include_default_routers(app: FastAPI) -> None:
    """Mount the default API router set onto the application."""
    from mcoi_runtime.app.routers.adapter import router as adapter_router
    from mcoi_runtime.app.routers.agent import router as agent_router
    from mcoi_runtime.app.routers.audit import router as audit_router
    from mcoi_runtime.app.routers.compliance import router as compliance_router
    from mcoi_runtime.app.routers.connectors import router as connectors_router
    from mcoi_runtime.app.routers.console import router as console_router
    from mcoi_runtime.app.routers.data import router as data_router
    from mcoi_runtime.app.routers.explain import router as explain_router
    from mcoi_runtime.app.routers.health import router as health_router
    from mcoi_runtime.app.routers.knowledge import router as knowledge_router
    from mcoi_runtime.app.routers.lineage import router as lineage_router
    from mcoi_runtime.app.routers.llm import router as llm_router
    from mcoi_runtime.app.routers.multi_agent import router as multi_agent_router
    from mcoi_runtime.app.routers.ops import router as ops_router
    from mcoi_runtime.app.routers.policy_versions import router as policy_versions_router
    from mcoi_runtime.app.routers.rbac import router as rbac_router
    from mcoi_runtime.app.routers.replay import router as replay_router
    from mcoi_runtime.app.routers.runbooks import router as runbooks_router
    from mcoi_runtime.app.routers.scheduler import router as scheduler_router
    from mcoi_runtime.app.routers.simulation import router as simulation_router
    from mcoi_runtime.app.routers.tenant import router as tenant_router
    from mcoi_runtime.app.routers.workflow import router as workflow_router

    app.include_router(health_router)
    app.include_router(llm_router)
    app.include_router(lineage_router)
    app.include_router(tenant_router)
    app.include_router(audit_router)
    app.include_router(workflow_router)
    app.include_router(agent_router)
    app.include_router(data_router)
    app.include_router(ops_router)
    app.include_router(adapter_router)
    app.include_router(compliance_router)
    app.include_router(scheduler_router)
    app.include_router(console_router)
    app.include_router(connectors_router)
    app.include_router(rbac_router)
    app.include_router(policy_versions_router)
    app.include_router(replay_router)
    app.include_router(simulation_router)
    app.include_router(runbooks_router)
    app.include_router(explain_router)
    app.include_router(multi_agent_router)
    app.include_router(knowledge_router)
