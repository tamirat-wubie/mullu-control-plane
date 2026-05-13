"""Runtime state persistence endpoints."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from mcoi_runtime.app.routers.data._common import _data_error_detail, deps
from mcoi_runtime.persistence import CorruptedDataError, PathTraversalError
from mcoi_runtime.persistence.state_persistence import thaw_state_data

router = APIRouter()


class StateSaveRequest(BaseModel):
    state_type: str
    data: dict[str, Any]


@router.post("/api/v1/state/save")
def save_state(req: StateSaveRequest):
    """Save runtime state."""
    deps.metrics.inc("requests_governed")
    try:
        snap = deps.state_persistence.save(req.state_type, req.data)
    except PathTraversalError:
        raise HTTPException(400, detail={
            "error": "invalid state_type",
            "error_code": "invalid_state_type",
            "governed": True,
        })
    return {"state_type": snap.state_type, "hash": snap.state_hash[:16], "saved_at": snap.saved_at}


@router.get("/api/v1/state/{state_type}")
def load_state(state_type: str):
    """Load runtime state."""
    try:
        snap = deps.state_persistence.load(state_type)
    except PathTraversalError:
        raise HTTPException(400, detail=_data_error_detail("invalid state_type", "invalid_state_type"))
    except CorruptedDataError:
        raise HTTPException(409, detail=_data_error_detail("state snapshot corrupted", "state_corrupted"))
    if snap is None:
        raise HTTPException(404, detail=_data_error_detail("state not found", "state_not_found"))
    return {"state_type": snap.state_type, "data": thaw_state_data(snap.data), "hash": snap.state_hash[:16]}


@router.get("/api/v1/state")
def list_states():
    """List saved states."""
    return {"states": deps.state_persistence.list_states(), "summary": deps.state_persistence.summary()}
