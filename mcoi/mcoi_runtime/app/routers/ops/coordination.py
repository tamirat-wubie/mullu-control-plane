"""Coordination engine checkpoint and restore endpoints."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from mcoi_runtime.app.routers.deps import deps

router = APIRouter()


class CoordinationCheckpointRequest(BaseModel):
    checkpoint_id: str
    lease_duration_seconds: int = 3600


class CoordinationRestoreRequest(BaseModel):
    checkpoint_id: str
    current_policy_pack_id: str = ""


@router.post("/api/v1/coordination/checkpoint")
def save_coordination_checkpoint(req: CoordinationCheckpointRequest):
    """Save a coordination engine checkpoint with governed lease."""
    deps.metrics.inc("requests_governed")
    checkpoint = deps.coordination_engine.save_checkpoint(
        req.checkpoint_id,
        lease_duration_seconds=req.lease_duration_seconds,
    )
    deps.audit_trail.record(
        action="coordination.checkpoint.save",
        actor_id="api",
        tenant_id="system",
        target=req.checkpoint_id,
        outcome="success",
        detail={
            "lease_expires_at": checkpoint.lease_expires_at,
            "delegations": len(checkpoint.delegations),
            "handoffs": len(checkpoint.handoffs),
        },
    )
    return {
        "checkpoint_id": checkpoint.checkpoint_id,
        "created_at": checkpoint.created_at,
        "lease_expires_at": checkpoint.lease_expires_at,
        "delegations": len(checkpoint.delegations),
        "handoffs": len(checkpoint.handoffs),
        "merges": len(checkpoint.merges),
        "conflicts": len(checkpoint.conflicts),
        "governed": True,
    }


@router.post("/api/v1/coordination/restore")
def restore_coordination_checkpoint(req: CoordinationRestoreRequest):
    """Restore coordination engine state from a governed checkpoint."""
    from mcoi_runtime.persistence.errors import PersistenceError
    deps.metrics.inc("requests_governed")
    try:
        outcome = deps.coordination_engine.restore_checkpoint(
            req.checkpoint_id,
            current_policy_pack_id=req.current_policy_pack_id or None,
        )
    except PersistenceError:
        raise HTTPException(404, detail={
            "error": "checkpoint not found",
            "error_code": "checkpoint_not_found",
            "governed": True,
        })
    deps.audit_trail.record(
        action="coordination.checkpoint.restore",
        actor_id="api",
        tenant_id="system",
        target=req.checkpoint_id,
        outcome=outcome.status.value,
        detail={"reason": outcome.reason},
    )
    return {
        "checkpoint_id": outcome.checkpoint_id,
        "status": outcome.status.value,
        "reason": outcome.reason,
        "restored_at": outcome.restored_at,
        "governed": True,
    }
