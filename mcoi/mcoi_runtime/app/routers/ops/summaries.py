"""Read-only operational summary endpoints — dashboards, registries, monitors.

Aggregates the small "*_summary" / "*_status" / "list_*" endpoints that don't
warrant their own per-concern module.
"""
from __future__ import annotations

from fastapi import APIRouter

from mcoi_runtime.app.readiness import production_readiness_checks
from mcoi_runtime.app.routers.deps import deps
from mcoi_runtime.core.spatial_governance import build_gateway_spatial_map

router = APIRouter()


# ═══ Observability Dashboard ═══


@router.get("/api/v1/dashboard")
def dashboard():
    """Aggregated observability dashboard data."""
    return deps.observability.collect_all()


# ═══ Plugins ═══


@router.get("/api/v1/plugins")
def list_plugins():
    """List registered plugins."""
    return {
        "plugins": [
            {"id": p.descriptor.plugin_id, "name": p.descriptor.name, "version": p.descriptor.version, "status": p.status.value}
            for p in deps.plugin_registry.list_plugins()
        ],
        "summary": deps.plugin_registry.summary(),
    }


# ═══ Governance Guards ═══


@router.get("/api/v1/guards")
def list_guards():
    """List governance guard chain."""
    from mcoi_runtime.governance.guards.chain import (
        GovernanceGuardChain, create_rate_limit_guard,
        create_budget_guard, create_tenant_guard,
    )
    chain = GovernanceGuardChain()
    chain.add(create_tenant_guard())
    chain.add(create_rate_limit_guard(deps.rate_limiter))
    chain.add(create_budget_guard(deps.tenant_budget_mgr))
    return {
        "guards": chain.guard_names(),
        "count": chain.guard_count,
    }


# ═══ Capabilities ═══


@router.get("/api/v1/capabilities")
def list_capabilities():
    """List available agent capabilities."""
    from mcoi_runtime.core.agent_protocol import AgentCapability
    return {
        "capabilities": [
            {"id": c.value, "name": c.name}
            for c in AgentCapability
        ],
    }


# ═══ Production Readiness ═══


@router.get("/api/v1/readiness")
def production_readiness():
    """Production readiness checks -- verifies all subsystems are operational."""
    checks = production_readiness_checks()
    all_ready = all(checks.values())
    return {
        "ready": all_ready,
        "checks": checks,
        "version": "1.3.0",
        "subsystems": len(checks),
        "governed": True,
    }


# ═══ Spatial Governance ═══


@router.get("/api/v1/spatial-map")
def read_spatial_map():
    """Return the bounded gateway spatial-causal governance map."""
    deps.metrics.inc("requests_governed")
    return {
        "spatial_map": build_gateway_spatial_map(production_readiness_checks()).to_dict(),
        "governed": True,
    }


# ═══ Monitoring ═══


@router.get("/api/v1/monitor")
def monitoring_dashboard():
    """Real-time monitoring vitals."""
    vitals = deps.monitor.compute_vitals(
        active_tenants=deps.tenant_budget_mgr.tenant_count(),
        llm_calls=deps.llm_bridge.invocation_count,
        total_cost=deps.llm_bridge.total_cost,
        health_score=deps.health_agg.compute().overall_score,
        circuit_state=deps.llm_circuit.state.value,
        event_count=deps.event_bus.event_count,
    )
    return {
        "uptime_seconds": vitals.uptime_seconds,
        "requests_per_minute": vitals.requests_per_minute,
        "errors_per_minute": vitals.errors_per_minute,
        "error_rate_pct": vitals.error_rate_pct,
        "active_tenants": vitals.active_tenants,
        "llm_calls_total": vitals.llm_calls_total,
        "total_cost": vitals.total_cost,
        "health_score": vitals.health_score,
        "circuit_breaker": vitals.circuit_breaker_state,
        "events": vitals.event_bus_events,
        "captured_at": vitals.captured_at,
    }


# ═══ Shutdown / Correlation ═══


@router.get("/api/v1/shutdown/info")
def shutdown_info():
    """Graceful shutdown configuration."""
    return deps.shutdown_mgr.summary()


@router.get("/api/v1/correlation/active")
def active_correlations():
    """Active request correlations."""
    return deps.correlation_mgr.summary()


# ═══ Notifications ═══


@router.get("/api/v1/notifications/summary")
def get_notification_summary():
    """Return notification dispatcher summary."""
    deps.metrics.inc("requests_governed")
    return {"notifications": deps.notification_dispatcher.summary(), "governed": True}


# ═══ Validation ═══


@router.get("/api/v1/validation/schemas")
def list_validation_schemas():
    """List registered validation schemas."""
    deps.metrics.inc("requests_governed")
    return {"validation": deps.input_validator.summary(), "governed": True}


# ═══ Idempotency ═══


@router.get("/api/v1/idempotency/summary")
def get_idempotency_summary():
    """Return idempotency store summary."""
    deps.metrics.inc("requests_governed")
    return {"idempotency": deps.idempotency_store.summary(), "governed": True}


# ═══ Compression ═══


@router.get("/api/v1/compression/summary")
def get_compression_summary():
    """Return response compression summary."""
    deps.metrics.inc("requests_governed")
    return {"compression": deps.response_compressor.summary(), "governed": True}


# ═══ Canary Deployment ═══


@router.get("/api/v1/canary")
def get_canary_status():
    """Return canary deployment status."""
    deps.metrics.inc("requests_governed")
    return {"canary": deps.canary_controller.summary(), "governed": True}


# ═══ Secret Rotation ═══


@router.get("/api/v1/secrets/summary")
def get_secrets_summary():
    """Return secret rotation engine summary."""
    deps.metrics.inc("requests_governed")
    return {"secrets": deps.secret_rotation.summary(), "governed": True}


# ═══ Request Deduplication ═══


@router.get("/api/v1/dedup/summary")
def get_dedup_summary():
    """Return request deduplication summary."""
    deps.metrics.inc("requests_governed")
    return {"dedup": deps.request_dedup.summary(), "governed": True}


# ═══ Deploy Readiness ═══


@router.get("/api/v1/deploy/readiness")
def get_deploy_readiness():
    """Run deployment readiness checks."""
    deps.metrics.inc("requests_governed")
    report = deps.deploy_checker.run_all()
    return {"readiness": report.to_dict(), "governed": True}


# ═══ API Migration ═══


@router.get("/api/v1/migrations/summary")
def get_migration_summary():
    """Return API version migration summary."""
    deps.metrics.inc("requests_governed")
    return {
        "migrations": deps.api_migration.summary(),
        "versions": [v.to_dict() for v in deps.api_migration.list_versions()],
        "governed": True,
    }


# ═══ Retry Policy ═══


@router.get("/api/v1/retries/summary")
def get_retries_summary():
    """Return governed retry policy summary."""
    deps.metrics.inc("requests_governed")
    return {"retries": deps.retry_engine.summary(), "governed": True}


# ═══ Region Routing ═══


@router.get("/api/v1/regions")
def get_regions():
    """Return multi-region routing status."""
    deps.metrics.inc("requests_governed")
    return {"regions": deps.region_router.summary(), "governed": True}


# ═══ Request Context ═══


@router.get("/api/v1/context/summary")
def get_context_summary():
    """Return request context factory summary."""
    deps.metrics.inc("requests_governed")
    return {"context": deps.request_ctx_factory.summary(), "governed": True}


# ═══ Circuit Breaker Dashboard ═══


@router.get("/api/v1/circuits/dashboard")
def get_circuit_dashboard():
    """Return circuit breaker dashboard aggregate."""
    deps.metrics.inc("requests_governed")
    return {"circuits": deps.circuit_dashboard.summary(), "governed": True}


# ═══ Cache Stats ═══


@router.get("/api/v1/cache/stats")
def cache_stats():
    """Cache statistics."""
    return deps.governed_cache.summary()


# ═══ Backpressure ═══


@router.get("/api/v1/backpressure")
def backpressure_status():
    """Current backpressure state."""
    return deps.backpressure.status()


# ═══ Traces Summary ═══
# NOTE: ``/api/v1/traces/summary`` lives in routers/agent.py because the trace
# namespace there registers ``/api/v1/traces/{trace_id}`` last. Without the
# summary route being registered ahead of the {trace_id} parameter capture,
# FastAPI matches "summary" as a trace_id and returns 404. A duplicate copy
# here would just generate a FastAPI duplicate-operation-id warning while
# being shadowed by the agent.py registration. See PR #805 / audit 2026-05-30.
