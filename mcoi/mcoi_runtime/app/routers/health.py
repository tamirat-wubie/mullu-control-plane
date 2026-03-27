"""Health-related endpoints extracted from server.py.

Provides liveness, readiness, deep-health, scored-health, and versioned
health-check routes.
"""
from __future__ import annotations

from fastapi import APIRouter

from mcoi_runtime.app.routers.deps import deps

router = APIRouter()


# ── Basic health & readiness ──────────────────────────────────────────────


@router.get("/health")
def health():
    h = deps.surface.health()
    h["llm_invocations"] = deps.llm_bridge.invocation_count
    h["llm_total_cost"] = round(deps.llm_bridge.total_cost, 6)
    h["certifications"] = deps.certifier.chain_count
    h["ledger_entries"] = deps.store.ledger_count()
    return h


@router.get("/ready")
def ready():
    h = health()
    return {"ready": h["status"] == "healthy", **h}


# ── Deep & scored health ─────────────────────────────────────────────────


@router.get("/api/v1/health/deep")
def deep_health_check():
    """System-wide deep health diagnostic."""
    result = deps.deep_health.run()
    return {
        "overall": result.overall.value,
        "components": [
            {"name": c.name, "status": c.status.value, "latency_ms": c.latency_ms, "detail": c.detail}
            for c in result.components
        ],
        "total_latency_ms": result.total_latency_ms,
        "checked_at": result.checked_at,
    }


@router.get("/api/v1/health/score")
def health_score():
    """Unified system health score (0.0-1.0)."""
    result = deps.health_agg.compute()
    return {
        "score": result.overall_score,
        "status": result.status,
        "components": [
            {"name": c.name, "score": c.score, "weight": c.weight, "status": c.status}
            for c in result.components
        ],
        "checked_at": result.checked_at,
    }


# ── Versioned health checks ──────────────────────────────────────────────


@router.get("/api/v1/health/v2")
def health_check_v2():
    """Run health checks with degraded state support."""
    deps.metrics.inc("requests_governed")
    result = deps.health_agg_v2.run()
    return {"health": result.to_dict(), "governed": True}


@router.get("/api/v1/health/v3")
def get_health_v3():
    """Weighted health check with recovery tracking."""
    deps.metrics.inc("requests_governed")
    return deps.health_v3.check_all()
