"""Rate limiter status endpoints."""
from __future__ import annotations

from fastapi import APIRouter

from mcoi_runtime.app.routers.deps import deps

router = APIRouter()


@router.get("/api/v1/rate-limit/status")
def rate_limit_status():
    """Rate limiter status."""
    return deps.rate_limiter.status()


@router.get("/api/v1/rate-limits/{client_id}")
def get_rate_limit_info(client_id: str):
    """Return rate limit headers for a client."""
    deps.metrics.inc("requests_governed")
    info = deps.rate_limit_headers.peek(client_id)
    return {"headers": info.to_headers(), "is_exhausted": info.is_exhausted, "governed": True}
