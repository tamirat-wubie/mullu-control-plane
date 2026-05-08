"""Feature flag endpoints."""
from __future__ import annotations

from fastapi import APIRouter

from mcoi_runtime.app.routers.deps import deps

router = APIRouter()


@router.get("/api/v1/flags")
def list_feature_flags():
    """List feature flags."""
    return {
        "flags": [
            {"id": f.flag_id, "name": f.name, "enabled": f.enabled}
            for f in deps.feature_flags.list_flags()
        ],
        "summary": deps.feature_flags.summary(),
    }


@router.get("/api/v1/flags/{flag_id}")
def check_flag(flag_id: str, tenant_id: str = ""):
    """Check if a feature flag is enabled."""
    return {"flag_id": flag_id, "enabled": deps.feature_flags.is_enabled(flag_id, tenant_id=tenant_id)}
