"""Optional FastAPI router adapter for read-only operational dashboard data.

Purpose: expose dashboard state and the simple home summary for host FastAPI
applications without making FastAPI a core runtime dependency.
Governance scope: HTTP adapter boundary only; OperationalDashboardRuntime owns
the governed envelope and no route grants execution authority.
Dependencies: dataclasses, typing, operational dashboard runtime API, and
optional FastAPI at router creation.
Invariants: importing this module does not require FastAPI, handlers preserve
runtime envelopes, and missing FastAPI is reported explicitly.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from mcoi_runtime.core.operational_dashboard_api import OperationalDashboardRuntime


@dataclass(frozen=True)
class OperationalDashboardRouteSpec:
    """Documented HTTP route contract for dashboard adapters."""

    method: str
    path: str
    handler_name: str
    purpose: str


class OperationalDashboardFastAPIAdapter:
    """Framework-adjacent handler object for read-only dashboard endpoints."""

    def __init__(self, runtime: OperationalDashboardRuntime) -> None:
        self.runtime = runtime

    def simple_home(self) -> dict[str, Any]:
        """Handle GET /home."""

        return self.runtime.simple_home().to_dict()

    def state(self) -> dict[str, Any]:
        """Handle GET /state."""

        return self.runtime.state().to_dict()

    def sdlc_receipts(self) -> dict[str, Any]:
        """Handle GET /sdlc/receipts."""

        return self.runtime.sdlc_receipts().to_dict()

    @staticmethod
    def route_specs(prefix: str = "/api/v1/dashboard") -> tuple[OperationalDashboardRouteSpec, ...]:
        """Return the stable HTTP route contracts."""

        normalized = prefix.rstrip("/")
        return (
            OperationalDashboardRouteSpec(
                method="GET",
                path=f"{normalized}/home",
                handler_name="simple_home",
                purpose="return the compact simple dashboard home projection",
            ),
            OperationalDashboardRouteSpec(
                method="GET",
                path=f"{normalized}/state",
                handler_name="state",
                purpose="return the full read-only operational dashboard state",
            ),
            OperationalDashboardRouteSpec(
                method="GET",
                path=f"{normalized}/sdlc/receipts",
                handler_name="sdlc_receipts",
                purpose="return read-only SDLC validation receipt summaries",
            ),
        )


def create_operational_dashboard_fastapi_router(
    runtime: OperationalDashboardRuntime,
    prefix: str = "/api/v1/dashboard",
):
    """Create a FastAPI APIRouter for read-only dashboard endpoints."""

    try:
        from fastapi import APIRouter
    except ImportError as exc:
        raise RuntimeError("FastAPI is required to create the operational dashboard router") from exc

    adapter = OperationalDashboardFastAPIAdapter(runtime)
    router = APIRouter(prefix=prefix.rstrip("/"), tags=["operational-dashboard"])

    @router.get("/home")
    def simple_home():
        return adapter.simple_home()

    @router.get("/state")
    def state():
        return adapter.state()

    @router.get("/sdlc/receipts")
    def sdlc_receipts():
        return adapter.sdlc_receipts()

    return router
