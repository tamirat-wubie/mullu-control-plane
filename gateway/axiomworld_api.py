"""AxiomWorld bounded API routes.

Purpose: Expose the AxiomWorld generic event adapter through a small FastAPI
    route surface without mutating the main gateway server module.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: FastAPI, gateway.axiomworld_generic_event_adapter.
Invariants:
  - API requests route through the generic event adapter, never direct store
    mutation.
  - Malformed payloads return bounded error codes without echoing raw private
    payload values.
  - Projection scope is selected by request payload and filtered by the kernel.
  - Route construction is explicit and reversible.
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from gateway.axiomworld_generic_event_adapter import AxiomWorldGenericEventAdapter


AXIOMWORLD_INGEST_PATH = "/api/v1/axiomworld/events"


def register_axiomworld_routes(
    app: FastAPI,
    *,
    adapter: AxiomWorldGenericEventAdapter | None = None,
) -> AxiomWorldGenericEventAdapter:
    """Register bounded AxiomWorld event routes on an existing FastAPI app.

    Input contract:
      - `app` is a FastAPI instance controlled by the caller.
      - optional `adapter` carries the kernel state for route calls.
    Output contract:
      - returns the adapter bound to the app state.
    Error contract:
      - request shape errors return HTTP 422 with bounded reason strings.
    """
    bound_adapter = adapter or AxiomWorldGenericEventAdapter()
    app.state.axiomworld_adapter = bound_adapter

    @app.post("/api/v1/axiomworld/events")
    async def ingest_axiomworld_event(request: Request) -> JSONResponse:
        try:
            payload = await request.json()
        except ValueError as exc:
            raise HTTPException(
                status_code=422,
                detail={"reason": "json_object_required"},
            ) from exc
        if not isinstance(payload, dict):
            raise HTTPException(
                status_code=422,
                detail={"reason": "json_object_required"},
            )
        try:
            result = bound_adapter.ingest(payload)
        except ValueError as exc:
            raise HTTPException(
                status_code=422,
                detail={"reason": _bounded_error_reason(exc)},
            ) from exc
        return JSONResponse(result.to_json_dict())

    @app.get("/api/v1/axiomworld/health")
    async def axiomworld_health() -> dict[str, Any]:
        return {
            "status": "ready",
            "ingest_path": AXIOMWORLD_INGEST_PATH,
            "mutation_boundary": "adapter_only",
        }

    return bound_adapter


def create_axiomworld_app(
    *,
    adapter: AxiomWorldGenericEventAdapter | None = None,
) -> FastAPI:
    """Create a standalone AxiomWorld API app for tests and local wiring."""
    app = FastAPI(title="Mullu AxiomWorld Kernel", version="0.1.0")
    register_axiomworld_routes(app, adapter=adapter)
    return app


def _bounded_error_reason(exc: ValueError) -> str:
    reason = str(exc).strip() or "invalid_axiomworld_event"
    if len(reason) > 120:
        return "invalid_axiomworld_event"
    if any(marker in reason.lower() for marker in ("secret", "token", "password", "key=")):
        return "invalid_axiomworld_event"
    return reason
