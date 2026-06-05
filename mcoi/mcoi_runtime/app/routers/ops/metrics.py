"""Governance metrics, Prometheus exposition, and Grafana dashboard endpoints."""
from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import PlainTextResponse

from mcoi_runtime.app.routers.deps import deps
from mcoi_runtime.core.prometheus_metric_projection import PrometheusMetricProjector

router = APIRouter()
_DASHBOARD_PROMETHEUS_PROJECTOR = PrometheusMetricProjector()


@router.get("/api/v1/metrics")
def get_metrics():
    """Governance metrics -- counters, gauges, histograms."""
    return deps.metrics.to_dict()


@router.get("/metrics")
def prometheus_metrics():
    """Export metrics in Prometheus text exposition format."""
    deps.metrics.inc("requests_governed")
    _DASHBOARD_PROMETHEUS_PROJECTOR.project(
        exporter=deps.prom_exporter,
        metrics=deps.metrics,
        tenant_budget_mgr=_optional_dependency("tenant_budget_mgr"),
        health_agg=_optional_dependency("health_agg"),
        llm_bridge=_optional_dependency("llm_bridge"),
        llm_circuit=_optional_dependency("llm_circuit"),
        audit_trail=_optional_dependency("audit_trail"),
        agent_registry=_optional_dependency("agent_registry"),
        task_manager=_optional_dependency("task_manager"),
        task_queue=_optional_dependency("task_queue"),
        agent_memory=_optional_dependency("agent_memory"),
        circuit_dashboard=_optional_dependency("circuit_dashboard"),
    )
    return PlainTextResponse(content=deps.prom_exporter.export(), media_type="text/plain")


@router.get("/api/v1/grafana/dashboard")
def get_grafana_dashboard():
    """Export the default Grafana dashboard JSON."""
    deps.metrics.inc("requests_governed")
    return deps.grafana_dashboard.generate()


def _optional_dependency(name: str):
    try:
        return getattr(deps, name)
    except RuntimeError:
        return None
