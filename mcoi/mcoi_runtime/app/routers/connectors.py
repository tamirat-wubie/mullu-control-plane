"""Connector endpoints — register, invoke, and manage governed integrations."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from mcoi_runtime.app.routers.deps import deps

router = APIRouter()


def _connector_error_detail(error: str, error_code: str) -> dict[str, object]:
    return {"error": error, "error_code": error_code, "governed": True}


class RegisterConnectorRequest(BaseModel):
    connector_id: str
    name: str
    connector_type: str = "http_api"
    base_url: str = ""
    capabilities: list[str] = Field(default_factory=list)
    max_retries: int = 3
    timeout_seconds: int = 30
    tenant_id: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class InvokeConnectorRequest(BaseModel):
    connector_id: str
    action: str
    payload: dict[str, Any] = Field(default_factory=dict)
    tenant_id: str = ""
    budget_id: str = ""
    mission_id: str = ""
    goal_id: str = ""


@router.post("/api/v1/connectors/register")
def register_connector(req: RegisterConnectorRequest):
    """Register a governed external connector."""
    from mcoi_runtime.core.connector_framework import ConnectorDefinition, ConnectorType
    deps.metrics.inc("requests_governed")
    try:
        ctype = ConnectorType(req.connector_type)
    except ValueError:
        raise HTTPException(400, detail=_connector_error_detail("invalid connector type", "invalid_connector_type"))
    definition = ConnectorDefinition(
        connector_id=req.connector_id,
        name=req.name,
        connector_type=ctype,
        base_url=req.base_url,
        capabilities=tuple(req.capabilities),
        max_retries=req.max_retries,
        timeout_seconds=req.timeout_seconds,
        tenant_id=req.tenant_id,
        metadata=req.metadata,
    )
    # Register with a default echo handler (real handlers wired programmatically)
    deps.connector_framework.register(
        definition,
        handler=lambda action, payload: {"echo": action, "received": list(payload.keys())},
    )
    return {
        "connector_id": definition.connector_id,
        "name": definition.name,
        "connector_type": definition.connector_type.value,
        "status": "registered",
        "governed": True,
    }


@router.post("/api/v1/connectors/invoke")
def invoke_connector(req: InvokeConnectorRequest):
    """Invoke a connector action through the governed pipeline."""
    deps.metrics.inc("requests_governed")
    invocation = deps.connector_framework.invoke(
        req.connector_id,
        req.action,
        req.payload,
        tenant_id=req.tenant_id,
        budget_id=req.budget_id,
        mission_id=req.mission_id,
        goal_id=req.goal_id,
    )
    return {
        "invocation_id": invocation.invocation_id,
        "connector_id": invocation.connector_id,
        "action": invocation.action,
        "outcome": invocation.outcome.value,
        "duration_ms": round(invocation.duration_ms, 1),
        "error": invocation.error,
        "governed": True,
    }


@router.get("/api/v1/connectors")
def list_connectors():
    """List all registered connectors."""
    deps.metrics.inc("requests_governed")
    connectors = deps.connector_framework.list_connectors()
    return {
        "connectors": [
            {
                "connector_id": c.definition.connector_id,
                "name": c.definition.name,
                "type": c.definition.connector_type.value,
                "status": c.status.value,
                "invocations": c.invocation_count,
                "successes": c.success_count,
                "failures": c.failure_count,
            }
            for c in connectors
        ],
        "count": len(connectors),
        "governed": True,
    }


@router.post("/api/v1/connectors/{connector_id}/disable")
def disable_connector(connector_id: str):
    """Disable a connector."""
    deps.metrics.inc("requests_governed")
    if not deps.connector_framework.disable(connector_id):
        raise HTTPException(404, detail={
            "error": "connector not found",
            "error_code": "connector_not_found",
            "governed": True,
        })
    return {"connector_id": connector_id, "status": "disabled", "governed": True}


@router.post("/api/v1/connectors/{connector_id}/enable")
def enable_connector(connector_id: str):
    """Enable a disabled connector."""
    deps.metrics.inc("requests_governed")
    if not deps.connector_framework.enable(connector_id):
        raise HTTPException(404, detail={
            "error": "connector not found",
            "error_code": "connector_not_found",
            "governed": True,
        })
    return {"connector_id": connector_id, "status": "healthy", "governed": True}


@router.get("/api/v1/connectors/history")
def connector_history(limit: int = 50):
    """Recent connector invocation history."""
    deps.metrics.inc("requests_governed")
    invocations = deps.connector_framework.recent_invocations(limit=limit)
    return {
        "invocations": [
            {
                "invocation_id": i.invocation_id,
                "connector_id": i.connector_id,
                "action": i.action,
                "outcome": i.outcome.value,
                "duration_ms": round(i.duration_ms, 1),
                "invoked_at": i.invoked_at,
                "error": i.error,
            }
            for i in invocations
        ],
        "count": len(invocations),
        "governed": True,
    }


@router.get("/api/v1/connectors/summary")
def connectors_summary():
    """Connector framework summary."""
    deps.metrics.inc("requests_governed")
    return {**deps.connector_framework.summary(), "governed": True}
