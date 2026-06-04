from __future__ import annotations

from fastapi import APIRouter

from mcoi_runtime.app.health_external import collect_external_dependency_health

router = APIRouter()


@router.get("/api/v1/health/remote")
def remote_health():
    return collect_external_dependency_health()
