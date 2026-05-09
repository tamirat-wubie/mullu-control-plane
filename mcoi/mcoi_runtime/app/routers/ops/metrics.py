"""Governance metrics, Prometheus exposition, and Grafana dashboard endpoints."""
from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import PlainTextResponse

from mcoi_runtime.app.routers.deps import deps

router = APIRouter()


@router.get("/api/v1/metrics")
def get_metrics():
    """Governance metrics -- counters, gauges, histograms."""
    return deps.metrics.to_dict()


@router.get("/metrics")
def prometheus_metrics():
    """Export metrics in Prometheus text exposition format."""
    deps.prom_exporter.inc_counter("requests_governed_total")
    return PlainTextResponse(content=deps.prom_exporter.export(), media_type="text/plain")


@router.get("/api/v1/grafana/dashboard")
def get_grafana_dashboard():
    """Export the default Grafana dashboard JSON."""
    deps.metrics.inc("requests_governed")
    return deps.grafana_dashboard.generate()
