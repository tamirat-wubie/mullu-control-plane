"""Component Harness read-model route.

Purpose: expose a bounded read-only projection of registered components,
router inventory, and proof binding posture.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: FastAPI, router deps, component_read_model, request simulator,
and component autopsy.
Invariants: route is GET-only, projection-only, and never grants live
execution, connector send, mutation, or terminal closure authority.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from mcoi_runtime.app.component_autopsy import (
    ComponentAutopsyError,
    build_component_autopsy,
)
from mcoi_runtime.app.component_read_model import (
    ComponentReadModelError,
    build_component_read_model,
)
from mcoi_runtime.app.component_request_simulator import (
    ComponentRequestSimulationError,
    simulate_component_request,
)
from mcoi_runtime.app.routers.deps import deps


router = APIRouter()


class ComponentSimulationRequest(BaseModel):
    """Request envelope for preview-only Component Harness simulation."""

    request_text: str = Field(min_length=1, max_length=500)


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


@router.get("/api/v1/components/{component_id}/autopsy")
def components_autopsy(component_id: str) -> dict[str, Any]:
    """Return a non-executing autopsy for one registered component."""

    _inc_metric("requests_governed")
    try:
        return build_component_autopsy(component_id)
    except ComponentAutopsyError as exc:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "component autopsy unavailable",
                "error_code": "component_autopsy_unavailable",
                "governed": True,
                "detail": str(exc)[:200],
            },
        ) from exc


@router.post("/api/v1/components/simulate")
def components_request_simulation(request: ComponentSimulationRequest) -> dict[str, Any]:
    """Return a non-executing component route preview for an operator request."""

    _inc_metric("requests_governed")
    try:
        return simulate_component_request(request.request_text)
    except ComponentRequestSimulationError as exc:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "component request simulation unavailable",
                "error_code": "component_request_simulation_unavailable",
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
