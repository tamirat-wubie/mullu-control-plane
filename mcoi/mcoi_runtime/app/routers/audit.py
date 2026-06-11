"""Audit, event-bus, event-store, and structured-logging endpoints.

Extracted from server.py.  All subsystem access goes through the shared
dependency container (``deps``) so there are no circular imports.
"""
from __future__ import annotations

from typing import Any, NoReturn

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from mcoi_runtime.app.routers.deps import deps
from mcoi_runtime.app.routers._tenant_scope import enforce_tenant_scope, scoped_listing_tenant
from mcoi_runtime.core.structured_logging import LogLevel

router = APIRouter()
_MAX_AUDIT_READ_LIMIT = 500


def _audit_error_detail(error: str, error_code: str) -> dict[str, object]:
    return {"error": error, "error_code": error_code, "governed": True}


def _raise_audit_read_validation_error(error: ValueError) -> NoReturn:
    raise HTTPException(
        status_code=422,
        detail=_audit_error_detail("invalid audit/event read request", "audit_event_read_invalid_request"),
    ) from error


def _coerce_audit_read_limit(limit: object) -> int:
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
    if value < 0 or value > _MAX_AUDIT_READ_LIMIT:
        raise ValueError("limit is outside the allowed range")
    return value


# ═══ Audit Trail Endpoints ═══════════════════════════════════════════════


@router.get("/api/v1/audit")
def get_audit_trail(
    request: Request,
    tenant_id: str | None = None,
    action: str | None = None,
    outcome: str | None = None,
    limit: str = "50",
):
    """Query the audit trail with optional filters."""
    deps.metrics.inc("requests_governed")
    try:
        read_limit = _coerce_audit_read_limit(limit)
    except ValueError as error:
        _raise_audit_read_validation_error(error)
    entries = deps.audit_trail.query(
        tenant_id=scoped_listing_tenant(request, tenant_id), action=action, outcome=outcome, limit=read_limit,
    )
    return {
        "entries": [
            {"id": e.entry_id, "action": e.action, "actor": e.actor_id,
             "tenant": e.tenant_id, "target": e.target, "outcome": e.outcome,
             "at": e.recorded_at}
            for e in entries
        ],
        "count": len(entries),
    }


@router.get("/api/v1/audit/verify")
def verify_audit_chain():
    """Verify audit trail hash-chain integrity."""
    valid, checked = deps.audit_trail.verify_chain()
    return {"valid": valid, "entries_checked": checked, "last_hash": deps.audit_trail.last_hash[:16]}


@router.get("/api/v1/audit/summary")
def audit_summary():
    """Audit trail summary."""
    return deps.audit_trail.summary()


# ═══ Event Bus Endpoints ═════════════════════════════════════════════════


@router.get("/api/v1/events")
def list_events(request: Request, event_type: str | None = None, limit: str = "50"):
    """Query governed event bus history."""
    try:
        read_limit = _coerce_audit_read_limit(limit)
    except ValueError as error:
        _raise_audit_read_validation_error(error)
    events = deps.event_bus.history(event_type=event_type, limit=read_limit)
    scoped = scoped_listing_tenant(request, None)
    if scoped is not None:
        events = [event for event in events if event.tenant_id == scoped]
    return {
        "events": [
            {"id": e.event_id, "type": e.event_type, "tenant": e.tenant_id,
             "source": e.source, "at": e.published_at}
            for e in events
        ],
        "count": len(events),
    }


@router.get("/api/v1/events/summary")
def events_summary():
    """Event bus summary."""
    return deps.event_bus.summary()


class EventPublishRequest(BaseModel):
    event_type: str
    tenant_id: str = ""
    source: str = "api"
    payload: dict[str, Any] = Field(default_factory=dict)


@router.post("/api/v1/events/publish")
def publish_event(req: EventPublishRequest, request: Request):
    """Publish a governed event to the bus."""
    enforce_tenant_scope(request, req.tenant_id)
    deps.metrics.inc("requests_governed")
    event = deps.event_bus.publish(
        req.event_type, tenant_id=req.tenant_id,
        source=req.source, payload=req.payload,
    )
    return {"event_id": event.event_id, "type": event.event_type, "hash": event.event_hash[:16]}


# ═══ Event Store Endpoint ════════════════════════════════════════════════


@router.get("/api/v1/events/store/summary")
def get_event_store_summary():
    """Return event sourcing store summary."""
    deps.metrics.inc("requests_governed")
    return {"event_store": deps.event_store.summary(), "governed": True}


# ═══ Structured Logging Endpoint ═════════════════════════════════════════


@router.get("/api/v1/logs")
def get_logs(count: int = 50, min_level: str = "INFO"):
    """Return recent structured log entries."""
    deps.metrics.inc("requests_governed")
    level = LogLevel[min_level.upper()] if min_level.upper() in LogLevel.__members__ else LogLevel.INFO
    entries = deps.platform_logger.recent(count=count, min_level=level)
    return {
        "logs": [e.to_dict() for e in entries],
        "summary": deps.platform_logger.summary(),
        "governed": True,
    }


# ═══ Audit Chain Anchoring ═══════════════════════════════════════════════


@router.post("/api/v1/audit/anchor")
def create_audit_anchor(limit: int = 1000):
    """Create an external anchor checkpoint from current audit entries."""
    deps.metrics.inc("requests_governed")
    entries = deps.audit_trail.query(limit=limit)
    if not entries:
        return {"error": "no audit entries to anchor", "governed": True}
    anchor = deps.audit_anchor.create_anchor(entries)
    deps.audit_trail.record(
        action="audit.anchor.create",
        actor_id="api",
        tenant_id="system",
        target=anchor.anchor_id,
        outcome="success",
        detail={"entry_count": anchor.entry_count, "merkle_root": anchor.merkle_root[:16]},
    )
    return {
        "anchor_id": anchor.anchor_id,
        "entry_count": anchor.entry_count,
        "merkle_root": anchor.merkle_root[:16],
        "anchored_at": anchor.anchored_at,
        "governed": True,
    }


@router.post("/api/v1/audit/anchor/{anchor_id}/verify")
def verify_audit_anchor(anchor_id: str, limit: int = 1000):
    """Verify current audit chain against a stored anchor."""
    deps.metrics.inc("requests_governed")
    entries = deps.audit_trail.query(limit=limit)
    result = deps.audit_anchor.verify_anchor(anchor_id, entries)
    return {**result, "governed": True}


@router.get("/api/v1/audit/anchors")
def list_audit_anchors(limit: int = 20):
    """List recent audit chain anchors."""
    deps.metrics.inc("requests_governed")
    anchors = deps.audit_anchor.list_anchors(limit=limit)
    return {
        "anchors": [
            {
                "anchor_id": a.anchor_id,
                "entry_count": a.entry_count,
                "merkle_root": a.merkle_root[:16],
                "anchored_at": a.anchored_at,
            }
            for a in anchors
        ],
        "count": len(anchors),
        "governed": True,
    }
