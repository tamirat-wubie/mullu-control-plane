"""Pilot provisioning endpoints.

Purpose: expose hosted pilot scaffold generation without live infrastructure
mutation.
Governance scope: pilot artifact provisioning surface only.
Dependencies: FastAPI, pilot scaffold generator, shared dependency registry.
Invariants: endpoint returns deterministic artifacts, records audit, and never
writes filesystem state.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from mcoi_runtime.app.pilot_init import PilotInitRequest, PilotProvisionRegistry, build_pilot_scaffold
from mcoi_runtime.app.routers.deps import deps


router = APIRouter()
_provision_registry = PilotProvisionRegistry()


class PilotProvisionRequest(BaseModel):
    tenant_id: str
    name: str
    policy_pack: str = "default-safe"
    policy_version: str = "v0.1"
    max_cost: float = Field(default=100.0, ge=0.0)
    max_calls: int = Field(default=1000, ge=1)


@router.post("/api/v1/pilots/provision")
def provision_pilot(req: PilotProvisionRequest) -> dict[str, Any]:
    """Return a deterministic pilot scaffold bundle for hosted provisioning."""
    deps.metrics.inc("requests_governed")
    try:
        request = PilotInitRequest(
            tenant_id=req.tenant_id,
            pilot_name=req.name,
            output_dir=Path("."),
            policy_pack_id=req.policy_pack,
            policy_version=req.policy_version,
            max_cost=req.max_cost,
            max_calls=req.max_calls,
        )
        bundle = build_pilot_scaffold(request)
    except ValueError as exc:
        raise HTTPException(
            400,
            detail={
                "error": "pilot provisioning request failed",
                "error_code": "pilot_provisioning_request_failed",
                "reason": type(exc).__name__,
                "governed": True,
            },
        ) from exc

    record = _provision_registry.accept(request=request, bundle=bundle, accepted_at=deps._clock())
    deps.audit_trail.record(
        action="pilot.provision.scaffold",
        actor_id="api",
        tenant_id=req.tenant_id,
        target=bundle.pilot_id,
        outcome="success",
        detail={
            "policy_pack": req.policy_pack,
            "policy_version": req.policy_version,
            "artifact_count": len(bundle.artifacts),
        },
    )
    return {"pilot": bundle.to_dict(), "record": record.to_dict(), "governed": True}


@router.get("/api/v1/pilots/provisions")
def list_pilot_provisions(
    tenant_id: str = "",
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    """List accepted hosted pilot provisioning records."""
    deps.metrics.inc("requests_governed")
    records = _provision_registry.list_records(tenant_id=tenant_id, limit=limit, offset=offset)
    return {
        "records": [record.to_dict() for record in records],
        "count": _provision_registry.count(tenant_id=tenant_id),
        "limit": min(max(limit, 1), 100),
        "offset": max(offset, 0),
        "governed": True,
    }


@router.get("/api/v1/pilots/provisions/{pilot_id}")
def get_pilot_provision(pilot_id: str) -> dict[str, Any]:
    """Fetch one accepted hosted pilot provisioning record."""
    deps.metrics.inc("requests_governed")
    record = _provision_registry.get(pilot_id)
    if record is None:
        raise HTTPException(
            404,
            detail={
                "error": "pilot provision not found",
                "error_code": "pilot_provision_not_found",
                "governed": True,
            },
        )
    return {"record": record.to_dict(), "governed": True}
