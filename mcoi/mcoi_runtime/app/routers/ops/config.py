"""Runtime configuration endpoints: get, history, update, rollback, watcher, drift."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from pydantic import BaseModel

from mcoi_runtime.app.routers.auth_context import bind_claimed_actor
from mcoi_runtime.app.routers.deps import deps

router = APIRouter()


class ConfigUpdateRequest(BaseModel):
    changes: dict[str, Any]
    applied_by: str = "api"
    description: str = ""


class ConfigRollbackRequest(BaseModel):
    to_version: int
    applied_by: str = "api"


@router.get("/api/v1/config")
def get_config():
    """Current runtime configuration."""
    return {
        "version": deps.config_manager.version,
        "config": deps.config_manager.get_all(),
        "hash": deps.config_manager.config_hash[:16] if deps.config_manager.config_hash else "",
    }


@router.get("/api/v1/config/history")
def config_history(limit: int = 10):
    """Configuration change history."""
    return {
        "versions": [
            {"version": v.version, "hash": v.config_hash[:16], "by": v.applied_by, "at": v.applied_at, "desc": v.description}
            for v in deps.config_manager.history(limit=limit)
        ],
    }


@router.post("/api/v1/config/update")
def update_config(req: ConfigUpdateRequest, request: Request):
    """Hot-reload configuration via REST API."""
    deps.metrics.inc("requests_governed")
    applied_by = bind_claimed_actor(
        request,
        req.applied_by,
        default_claims=("api",),
        error_code="config_actor_identity_mismatch",
        error_message="applied_by does not match authenticated identity",
    )
    result = deps.config_manager.update(
        req.changes, applied_by=applied_by, description=req.description,
    )
    deps.audit_trail.record(
        action="config.update", actor_id=applied_by,
        tenant_id="system", target="config",
        outcome="success" if result.success else "denied",
        detail={"version": result.version, "changes": list(req.changes.keys())},
    )
    deps.event_bus.publish(
        "config.updated" if result.success else "config.rejected",
        source="config_manager",
        payload={"version": result.version, "success": result.success},
    )
    return {
        "success": result.success,
        "version": result.version,
        "previous_version": result.previous_version,
        "error": result.error,
    }


@router.post("/api/v1/config/rollback")
def rollback_config(req: ConfigRollbackRequest, request: Request):
    """Rollback configuration to a previous version."""
    deps.metrics.inc("requests_governed")
    applied_by = bind_claimed_actor(
        request,
        req.applied_by,
        default_claims=("api",),
        error_code="config_actor_identity_mismatch",
        error_message="applied_by does not match authenticated identity",
    )
    result = deps.config_manager.rollback(req.to_version, applied_by=applied_by)
    deps.audit_trail.record(
        action="config.rollback", actor_id=applied_by,
        tenant_id="system", target="config",
        outcome="success" if result.success else "denied",
        detail={"to_version": req.to_version},
    )
    return {
        "success": result.success,
        "version": result.version,
        "error": result.error,
    }


@router.get("/api/v1/config/watcher")
def get_config_watcher_status():
    """Return config file watcher status."""
    deps.metrics.inc("requests_governed")
    return {"config_watcher": deps.config_watcher.summary(), "governed": True}


@router.get("/api/v1/config/drift")
def get_config_drift():
    """Return config drift detection summary."""
    deps.metrics.inc("requests_governed")
    return {"drift": deps.config_drift.summary(), "governed": True}
