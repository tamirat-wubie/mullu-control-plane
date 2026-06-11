"""Runtime configuration endpoints: get, history, update, rollback, watcher, drift."""
from __future__ import annotations

from typing import Any, NoReturn

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from mcoi_runtime.app.routers.auth_context import bind_claimed_actor
from mcoi_runtime.app.routers.deps import deps

router = APIRouter()
_MAX_CONFIG_HISTORY_READ_LIMIT = 500


def _config_error_detail(error: str, error_code: str) -> dict[str, object]:
    return {"error": error, "error_code": error_code, "governed": True}


def _raise_config_history_validation_error(error: ValueError) -> NoReturn:
    raise HTTPException(
        status_code=422,
        detail=_config_error_detail("invalid config history request", "config_history_invalid_request"),
    ) from error


def _coerce_config_history_limit(limit: object) -> int:
    if isinstance(limit, bool):
        raise ValueError("limit must be an integer")
    if isinstance(limit, int):
        value = limit
    elif isinstance(limit, str):
        normalized = limit.strip()
        if not normalized.isdecimal():
            raise ValueError("limit must be an integer")
        value = int(normalized)
    else:
        raise ValueError("limit must be an integer")
    if value < 0 or value > _MAX_CONFIG_HISTORY_READ_LIMIT:
        raise ValueError("limit is outside the allowed range")
    return value


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
def config_history(limit: str = "10"):
    """Configuration change history."""
    try:
        read_limit = _coerce_config_history_limit(limit)
    except ValueError as error:
        _raise_config_history_validation_error(error)
    return {
        "versions": [
            {"version": v.version, "hash": v.config_hash[:16], "by": v.applied_by, "at": v.applied_at, "desc": v.description}
            for v in deps.config_manager.history(limit=read_limit)
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
    try:
        result = deps.config_manager.update(
            req.changes, applied_by=applied_by, description=req.description,
        )
    except ValueError as exc:
        raise HTTPException(
            400,
            detail=_config_error_detail(str(exc)[:200], "invalid_config_request"),
        ) from exc
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
    try:
        result = deps.config_manager.rollback(req.to_version, applied_by=applied_by)
    except ValueError as exc:
        raise HTTPException(
            400,
            detail={"error": str(exc)[:200], "error_code": "invalid_config_request", "governed": True},
        ) from exc
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
