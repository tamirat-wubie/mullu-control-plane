"""API key management endpoints."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from mcoi_runtime.app.routers.data._common import _data_error_detail, deps

router = APIRouter()


class CreateAPIKeyRequest(BaseModel):
    tenant_id: str
    scopes: list[str]
    description: str = ""
    ttl_seconds: float | None = None


@router.post("/api/v1/api-keys")
def create_api_key(req: CreateAPIKeyRequest):
    """Create a new API key."""
    deps.metrics.inc("requests_governed")
    if "*" in req.scopes and not deps.api_key_mgr.allow_wildcard_keys:
        raise HTTPException(
            400,
            detail=_data_error_detail(
                "wildcard api keys disabled",
                "wildcard_api_keys_disabled",
            ),
        )
    try:
        raw_key, api_key = deps.api_key_mgr.create_key(
            req.tenant_id,
            frozenset(req.scopes),
            description=req.description,
            ttl_seconds=req.ttl_seconds,
        )
    except ValueError:
        raise HTTPException(
            400,
            detail=_data_error_detail(
                "invalid api key request",
                "api_key_validation_error",
            ),
        )
    return {
        "raw_key": raw_key,
        "key": api_key.to_dict(),
        "governed": True,
    }


@router.get("/api/v1/api-keys")
def list_api_keys(tenant_id: str | None = None):
    """List API keys."""
    deps.metrics.inc("requests_governed")
    keys = deps.api_key_mgr.list_keys(tenant_id=tenant_id)
    return {"keys": [k.to_dict() for k in keys], "governed": True}


@router.delete("/api/v1/api-keys/{key_id}")
def revoke_api_key(key_id: str):
    """Revoke an API key."""
    deps.metrics.inc("requests_governed")
    if not deps.api_key_mgr.revoke(key_id):
        raise HTTPException(404, detail=_data_error_detail("api key not found", "api_key_not_found"))
    return {"revoked": True, "key_id": key_id, "governed": True}
