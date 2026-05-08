"""System snapshot endpoints: full export, list, create."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from mcoi_runtime.app.routers.deps import deps

router = APIRouter()


class CreateSnapshotRequest(BaseModel):
    snapshot_id: str
    name: str
    state: dict[str, Any] = Field(default_factory=dict)


@router.get("/api/v1/snapshot")
def system_snapshot():
    """Full system state export -- all subsystem summaries in one call."""
    return {
        "version": "0.6.0",
        "environment": deps.ENV,
        "store": {"ledger_count": deps.store.ledger_count()},
        "llm": {"invocations": deps.llm_bridge.invocation_count, "total_cost": deps.llm_bridge.total_cost, **deps.llm_bridge.budget_summary()},
        "certification": deps.cert_daemon.status(),
        "tenants": {"count": deps.tenant_budget_mgr.tenant_count(), "total_spent": deps.tenant_budget_mgr.total_spent()},
        "agents": {"count": deps.agent_registry.count, "tasks": deps.task_manager.task_count},
        "workflows": deps.workflow_engine.summary(),
        "pipelines": deps.batch_pipeline.summary(),
        "metrics": deps.metrics.to_dict(),
        "audit": deps.audit_trail.summary(),
        "events": deps.event_bus.summary(),
        "webhooks": deps.webhook_manager.summary(),
        "config": deps.config_manager.summary(),
        "plugins": deps.plugin_registry.summary(),
        "rate_limiter": deps.rate_limiter.status(),
        "captured_at": deps._clock(),
    }


@router.get("/api/v1/snapshots")
def list_snapshots(limit: int = 10):
    """List recent system snapshots."""
    deps.metrics.inc("requests_governed")
    snaps = deps.snapshot_mgr.list_snapshots(limit=limit)
    return {
        "snapshots": [s.to_dict() for s in snaps],
        "summary": deps.snapshot_mgr.summary(),
        "governed": True,
    }


@router.post("/api/v1/snapshots")
def create_snapshot(req: CreateSnapshotRequest):
    """Create a system state snapshot."""
    deps.metrics.inc("requests_governed")
    snap = deps.snapshot_mgr.create_snapshot(req.snapshot_id, req.name, req.state)
    return {"snapshot": snap.to_dict(), "governed": True}
