"""Pilot provisioning and product demo read-only endpoints.

Purpose: expose hosted pilot scaffold generation without live infrastructure
mutation and mount fixture-backed governed product demo read models.
Governance scope: pilot artifact provisioning and no-effect dashboard surfaces.
Dependencies: FastAPI, pilot scaffold generator, shared dependency registry, and
read-only Governed Work Assistant dashboard router.
Invariants: provisioning endpoint returns deterministic artifacts, records audit,
and never writes filesystem state; dashboard endpoint is read-only, fixture-backed,
and grants no connector, mailbox, send, repository, worker, or receipt authority.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from mcoi_runtime.app.pilot_init import PilotInitRequest, PilotProvisionRegistry, build_pilot_scaffold
from mcoi_runtime.app.routers.deps import deps
from mcoi_runtime.app.routers._tenant_scope import enforce_tenant_scope, scoped_listing_tenant
from mcoi_runtime.app.routers.musia_auth import require_admin
from mcoi_runtime.app.routers.work_assistant_dashboard import router as work_assistant_dashboard_router


router = APIRouter()
router.include_router(work_assistant_dashboard_router)
_provision_registry = PilotProvisionRegistry()


class PilotProvisionRequest(BaseModel):
    tenant_id: str
    name: str
    policy_pack: str = "default-safe"
    policy_version: str = "v0.1"
    max_cost: float = Field(default=100.0, ge=0.0)
    max_calls: int = Field(default=1000, ge=1)


def _pilot_provision_registry() -> PilotProvisionRegistry:
    """Resolve the configured pilot provision registry with test fallback."""

    try:
        return deps.pilot_provision_registry
    except RuntimeError:
        return _provision_registry


@router.post("/api/v1/pilots/provision")
def provision_pilot(req: PilotProvisionRequest, _: str = Depends(require_admin)) -> dict[str, Any]:
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

    record = _pilot_provision_registry().accept(request=request, bundle=bundle, accepted_at=deps._clock())
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
    request: Request,
    tenant_id: str = "",
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    """List accepted hosted pilot provisioning records."""
    deps.metrics.inc("requests_governed")
    tenant_id = scoped_listing_tenant(request, tenant_id)
    registry = _pilot_provision_registry()
    records = registry.list_records(tenant_id=tenant_id, limit=limit, offset=offset)
    return {
        "records": [record.to_dict() for record in records],
        "count": registry.count(tenant_id=tenant_id),
        "limit": min(max(limit, 1), 100),
        "offset": max(offset, 0),
        "governed": True,
    }


@router.get("/api/v1/pilots/provisions/{pilot_id}")
def get_pilot_provision(pilot_id: str, request: Request) -> dict[str, Any]:
    """Fetch one accepted hosted pilot provisioning record."""
    deps.metrics.inc("requests_governed")
    record = _pilot_provision_registry().get(pilot_id)
    if record is None:
        raise HTTPException(
            404,
            detail={
                "error": "pilot provision not found",
                "error_code": "pilot_provision_not_found",
                "governed": True,
            },
        )
    enforce_tenant_scope(request, record.tenant_id)
    return {"record": record.to_dict(), "governed": True}
