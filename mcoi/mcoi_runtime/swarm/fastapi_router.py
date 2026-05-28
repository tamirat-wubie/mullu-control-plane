"""Optional FastAPI router adapter for governed swarm runtime operations.

Purpose: expose invoice swarm run, lookup, and listing handlers for host
FastAPI applications without making FastAPI a core runtime dependency.
Governance scope: HTTP adapter boundary only; InvoiceSwarmRuntime owns request
validation, execution, audit persistence, lookup, and rejection envelopes.
Dependencies: runtime API, dataclasses, and optional FastAPI at router creation.
Invariants: importing this module does not require FastAPI, route handlers do
not bypass runtime envelopes, and missing FastAPI is reported explicitly.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .runtime_api import InvoiceSwarmRuntime


@dataclass(frozen=True)
class SwarmRouteSpec:
    """Documented HTTP route contract for a governed swarm adapter."""

    method: str
    path: str
    handler_name: str
    purpose: str


class SwarmFastAPIAdapter:
    """Framework-adjacent handler object for governed swarm endpoints."""

    def __init__(self, runtime: InvoiceSwarmRuntime) -> None:
        self.runtime = runtime

    def run_invoice(self, request_body: Mapping[str, Any]) -> dict[str, Any]:
        """Handle POST /invoice-runs."""

        return self.runtime.run_invoice(request_body).to_dict()

    def get_run(self, run_id: str) -> dict[str, Any]:
        """Handle GET /runs/{run_id}."""

        return self.runtime.get_run(run_id).to_dict()

    def list_runs(self) -> dict[str, Any]:
        """Handle GET /runs."""

        return self.runtime.list_runs().to_dict()

    @staticmethod
    def route_specs(prefix: str = "/api/v1/swarm") -> tuple[SwarmRouteSpec, ...]:
        """Return the stable HTTP route contracts."""

        normalized = prefix.rstrip("/")
        return (
            SwarmRouteSpec(
                method="POST",
                path=f"{normalized}/invoice-runs",
                handler_name="run_invoice",
                purpose="run a governed invoice swarm and persist its audit record",
            ),
            SwarmRouteSpec(
                method="GET",
                path=f"{normalized}/runs/{{run_id}}",
                handler_name="get_run",
                purpose="read one persisted governed swarm run",
            ),
            SwarmRouteSpec(
                method="GET",
                path=f"{normalized}/runs",
                handler_name="list_runs",
                purpose="list persisted governed swarm runs",
            ),
        )


def create_fastapi_router(runtime: InvoiceSwarmRuntime, prefix: str = "/api/v1/swarm"):
    """Create a FastAPI APIRouter for governed swarm endpoints.

    FastAPI is imported only here so the core swarm runtime remains usable in
    lightweight worker, CLI, and test contexts.
    """

    try:
        from fastapi import APIRouter, Body
    except ImportError as exc:
        raise RuntimeError("FastAPI is required to create the swarm router") from exc

    adapter = SwarmFastAPIAdapter(runtime)
    router = APIRouter(prefix=prefix.rstrip("/"), tags=["governed-swarm"])

    @router.post("/invoice-runs")
    def run_invoice(request_body: dict[str, Any] = Body(...)):
        return adapter.run_invoice(request_body)

    @router.get("/runs/{run_id}")
    def get_run(run_id: str):
        return adapter.get_run(run_id)

    @router.get("/runs")
    def list_runs():
        return adapter.list_runs()

    return router
