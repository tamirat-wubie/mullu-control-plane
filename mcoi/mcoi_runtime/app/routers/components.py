"""Component Harness read-model route.

Purpose: expose a bounded read-only projection of registered components,
router inventory, and proof binding posture.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: FastAPI, router deps, and component_read_model.
Invariants: route is GET-only, projection-only, and never grants live
execution, connector send, mutation, or terminal closure authority.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from mcoi_runtime.app.component_read_model import (
    ComponentReadModelError,
    build_component_read_model,
)
from mcoi_runtime.app.routers.deps import deps


router = APIRouter()


@router.get("/api/v1/components/read-model")
def components_read_model() -> dict[str, Any]:
    """Return the foundation Component Harness read model."""

    _inc_metric("requests_governed")
    try:
        return build_component_read_model()
    except ComponentReadModelError as exc:
        raise HTTPException(
            status_code=500,
            detail={
                "error": "component read model unavailable",
                "error_code": "component_read_model_unavailable",
                "governed": True,
                "detail": str(exc)[:200],
            },
        ) from exc


def _inc_metric(name: str) -> None:
    """Increment metrics if the governed metrics dependency is registered."""

    try:
        metrics: Any = deps.get("metrics")
    except RuntimeError:
        return
    inc = getattr(metrics, "inc", None)
    if callable(inc):
        inc(name)
