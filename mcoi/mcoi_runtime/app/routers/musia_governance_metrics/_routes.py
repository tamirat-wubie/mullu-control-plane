"""HTTP surface for governance metrics."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from fastapi.responses import PlainTextResponse

from mcoi_runtime.app.routers.musia_auth import require_admin, require_read
from mcoi_runtime.app.routers.musia_governance_metrics._registry import REGISTRY


router = APIRouter(prefix="/musia/governance", tags=["musia-governance"])


# Prometheus exposition format content type (v0.0.4)
_PROMETHEUS_CONTENT_TYPE = "text/plain; version=0.0.4; charset=utf-8"


@router.get("/stats")
def get_stats(_: str = Depends(require_admin)) -> dict[str, Any]:
    """Snapshot of chain counters and recent rejections.

    Admin scope. The response is JSON-shape-stable: tuple-keyed dicts
    are flattened to ``"<key1>:<key2>"`` strings so clients can read by
    string-key without tuple-aware deserialization.
    """
    return REGISTRY.snapshot().as_dict()


@router.post("/stats/reset", status_code=204)
def reset_stats(_: str = Depends(require_admin)) -> None:
    """Reset counters. For ops use only — surfaces a fresh window
    (e.g., before/after a deployment). Admin scope."""
    REGISTRY.reset()


@router.get(
    "/metrics",
    response_class=PlainTextResponse,
    responses={
        200: {
            "content": {_PROMETHEUS_CONTENT_TYPE: {}},
            "description": "Prometheus exposition format (v0.0.4).",
        }
    },
)
def get_prometheus_metrics(
    _: str = Depends(require_admin),
) -> PlainTextResponse:
    """v4.20.0+: Prometheus exposition of governance chain counters.

    Returns the same data as ``/stats`` but in Prometheus text format
    (v0.0.4) so any compatible scraper (Prometheus, Grafana Agent,
    Datadog Agent, OpenTelemetry Collector) can ingest natively.

    Admin scope — same as ``/stats``. The endpoint is deliberately at
    ``/musia/governance/metrics`` (not the customary ``/metrics`` at
    the app root) so deployments running multiple metric surfaces in
    one process can keep them separate. Operators wanting a unified
    ``/metrics`` endpoint can mount a thin aggregator that calls into
    each surface.
    """
    body = REGISTRY.snapshot().to_prometheus_text()
    return PlainTextResponse(content=body, media_type=_PROMETHEUS_CONTENT_TYPE)


# ---- Per-tenant scoped views (v4.24.0+) ----
#
# The /stats and /metrics endpoints above are admin-scoped and expose
# every tenant's data. Multi-org SaaS deployments need per-org
# self-service visibility — each customer should see THEIR governance
# data without leaking neighbors'. The two endpoints below take the
# caller's authenticated tenant_id as the filter; require_read scope
# (a customer's normal credential) is enough.


@router.get("/stats/tenant")
def get_stats_tenant(tenant_id: str = Depends(require_read)) -> dict[str, Any]:
    """Per-tenant view of governance counters.

    v4.24.0+. Returns the same JSON shape as ``/stats`` but filtered to
    the authenticated tenant's own data. Cross-tenant aggregates
    (latency_by_surface) are dropped. ``musia.read`` scope.
    """
    return REGISTRY.snapshot().for_tenant(tenant_id).as_dict()


@router.get(
    "/metrics/tenant",
    response_class=PlainTextResponse,
    responses={
        200: {
            "content": {_PROMETHEUS_CONTENT_TYPE: {}},
            "description": "Prometheus exposition format (v0.0.4), tenant-scoped.",
        }
    },
)
def get_prometheus_metrics_tenant(
    tenant_id: str = Depends(require_read),
) -> PlainTextResponse:
    """v4.24.0+: Prometheus exposition scoped to the authenticated tenant.

    Returns the same metric families as ``/metrics`` but with all
    series filtered to the caller's own tenant. Useful for SaaS
    deployments where each customer scrapes their own slice without
    seeing platform aggregates or other tenants' counts.

    ``musia.read`` scope (vs. ``/metrics`` which requires ``musia.admin``).
    """
    body = REGISTRY.snapshot().for_tenant(tenant_id).to_prometheus_text()
    return PlainTextResponse(content=body, media_type=_PROMETHEUS_CONTENT_TYPE)
