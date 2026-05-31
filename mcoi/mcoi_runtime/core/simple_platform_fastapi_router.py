"""Optional FastAPI router adapter for simple governed platform actions.

Purpose: expose plain action checks and the action menu for host FastAPI
applications without making FastAPI a core runtime dependency.
Governance scope: HTTP adapter boundary only; SimplePlatformRuntime owns
request validation, governed projection, and rejection envelopes.
Dependencies: dataclasses, typing, simple platform runtime API, and optional
FastAPI at router creation.
Invariants: importing this module does not require FastAPI, route handlers do
not bypass runtime envelopes, and missing FastAPI is reported explicitly.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .simple_platform_api import SimplePlatformRuntime


@dataclass(frozen=True)
class SimplePlatformRouteSpec:
    """Documented HTTP route contract for simple platform adapters."""

    method: str
    path: str
    handler_name: str
    purpose: str


class SimplePlatformFastAPIAdapter:
    """Framework-adjacent handler object for simple platform endpoints."""

    def __init__(self, runtime: SimplePlatformRuntime) -> None:
        self.runtime = runtime

    def check_action(self, request_body: Mapping[str, Any]) -> dict[str, Any]:
        """Handle POST /actions/check."""

        return self.runtime.check_action(request_body).to_dict()

    def check_task(self, request_body: Mapping[str, Any]) -> dict[str, Any]:
        """Handle POST /tasks/check."""

        return self.runtime.check_task(request_body).to_dict()

    def check_workflow(self, request_body: Mapping[str, Any]) -> dict[str, Any]:
        """Handle POST /workflows/check."""

        return self.runtime.check_workflow(request_body).to_dict()

    def action_menu(self) -> dict[str, Any]:
        """Handle GET /actions."""

        return self.runtime.action_menu().to_dict()

    def simple_home(self) -> dict[str, Any]:
        """Handle GET /home."""

        return self.runtime.simple_home().to_dict()

    def start_guide(self) -> dict[str, Any]:
        """Handle GET /start."""

        return self.runtime.start_guide().to_dict()

    @staticmethod
    def route_specs(prefix: str = "/api/v1/simple") -> tuple[SimplePlatformRouteSpec, ...]:
        """Return the stable HTTP route contracts."""

        normalized = prefix.rstrip("/")
        return (
            SimplePlatformRouteSpec(
                method="GET",
                path=f"{normalized}/home",
                handler_name="simple_home",
                purpose="show the compact first-screen summary for simple mode",
            ),
            SimplePlatformRouteSpec(
                method="GET",
                path=f"{normalized}/actions",
                handler_name="action_menu",
                purpose="list plain user actions and possible outcomes",
            ),
            SimplePlatformRouteSpec(
                method="GET",
                path=f"{normalized}/start",
                handler_name="start_guide",
                purpose="show the plain onboarding path for simple mode",
            ),
            SimplePlatformRouteSpec(
                method="POST",
                path=f"{normalized}/actions/check",
                handler_name="check_action",
                purpose="check whether a plain task is ready, needs review, or is blocked",
            ),
            SimplePlatformRouteSpec(
                method="POST",
                path=f"{normalized}/tasks/check",
                handler_name="check_task",
                purpose="check a template-backed task without requiring a manual allowed area",
            ),
            SimplePlatformRouteSpec(
                method="POST",
                path=f"{normalized}/workflows/check",
                handler_name="check_workflow",
                purpose="check a common workflow as one plain outcome",
            ),
        )


def create_simple_platform_fastapi_router(runtime: SimplePlatformRuntime, prefix: str = "/api/v1/simple"):
    """Create a FastAPI APIRouter for simple governed platform endpoints.

    FastAPI is imported only here so the core simple platform runtime remains
    usable in CLI, worker, and test contexts.
    """

    try:
        from fastapi import APIRouter, Body
    except ImportError as exc:
        raise RuntimeError("FastAPI is required to create the simple platform router") from exc

    adapter = SimplePlatformFastAPIAdapter(runtime)
    router = APIRouter(prefix=prefix.rstrip("/"), tags=["simple-platform"])

    @router.get("/home")
    def simple_home():
        return adapter.simple_home()

    @router.get("/actions")
    def action_menu():
        return adapter.action_menu()

    @router.get("/start")
    def start_guide():
        return adapter.start_guide()

    @router.post("/actions/check")
    def check_action(request_body: dict[str, Any] = Body(...)):
        return adapter.check_action(request_body)

    @router.post("/tasks/check")
    def check_task(request_body: dict[str, Any] = Body(...)):
        return adapter.check_task(request_body)

    @router.post("/workflows/check")
    def check_workflow(request_body: dict[str, Any] = Body(...)):
        return adapter.check_workflow(request_body)

    return router
