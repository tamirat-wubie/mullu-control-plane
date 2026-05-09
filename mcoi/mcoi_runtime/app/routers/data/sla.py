"""SLA monitoring endpoints."""
from __future__ import annotations

from fastapi import APIRouter

from mcoi_runtime.app.routers.data._common import deps

router = APIRouter()


@router.get("/api/v1/sla")
def get_sla_summary():
    """Return SLA monitoring summary."""
    deps.metrics.inc("requests_governed")
    return {"sla": deps.sla_monitor.summary(), "governed": True}


@router.get("/api/v1/sla/violations")
def get_sla_violations(sla_id: str | None = None):
    """Return SLA violations."""
    deps.metrics.inc("requests_governed")
    violations = deps.sla_monitor.violations(sla_id)
    return {
        "violations": [{"sla_id": v.sla_id, "actual": v.actual_value,
                         "threshold": v.threshold} for v in violations],
        "count": len(violations),
        "governed": True,
    }
