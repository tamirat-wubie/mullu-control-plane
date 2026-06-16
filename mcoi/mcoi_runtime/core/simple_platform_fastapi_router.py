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

from .invariants import RuntimeCoreInvariantError
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

        return self.runtime.check_action_experience(request_body).to_dict()

    def check_action_audit(self, request_body: Mapping[str, Any]) -> dict[str, Any]:
        """Handle POST /actions/check/audit."""

        return self.runtime.check_action(request_body).to_dict()

    def check_action_experience(self, request_body: Mapping[str, Any]) -> dict[str, Any]:
        """Handle POST /actions/experience."""

        return self.runtime.check_action_experience(request_body).to_dict()

    def check_task(self, request_body: Mapping[str, Any]) -> dict[str, Any]:
        """Handle POST /tasks/check."""

        return self.runtime.check_task_experience(request_body).to_dict()

    def check_task_audit(self, request_body: Mapping[str, Any]) -> dict[str, Any]:
        """Handle POST /tasks/check/audit."""

        return self.runtime.check_task(request_body).to_dict()

    def check_workflow(self, request_body: Mapping[str, Any]) -> dict[str, Any]:
        """Handle POST /workflows/check."""

        return self.runtime.check_workflow_experience(request_body).to_dict()

    def check_workflow_audit(self, request_body: Mapping[str, Any]) -> dict[str, Any]:
        """Handle POST /workflows/check/audit."""

        return self.runtime.check_workflow(request_body).to_dict()

    def action_menu(self) -> dict[str, Any]:
        """Handle GET /actions."""

        return self.runtime.action_menu().to_dict()

    def simple_home(self) -> dict[str, Any]:
        """Handle GET /home."""

        return self.runtime.simple_home().to_dict()

    def document_manipulation_wiring(self) -> dict[str, Any]:
        """Handle GET /documents/wiring."""

        return self.runtime.document_manipulation_wiring().to_dict()

    def document_manipulation_wiring_contract(self) -> dict[str, Any]:
        """Handle GET /documents/wiring/contract."""

        return self.runtime.document_manipulation_wiring_contract().to_dict()

    def start_guide(self) -> dict[str, Any]:
        """Handle GET /start."""

        return self.runtime.start_guide().to_dict()

    @staticmethod
    def route_specs(prefix: str = "/api/v1/simple") -> tuple[SimplePlatformRouteSpec, ...]:
        """Return the stable HTTP route contracts."""

        normalized = _route_prefix(prefix, "prefix")
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
                method="GET",
                path=f"{normalized}/documents/wiring",
                handler_name="document_manipulation_wiring",
                purpose="show read-only document manipulation component wiring",
            ),
            SimplePlatformRouteSpec(
                method="GET",
                path=f"{normalized}/documents/wiring/contract",
                handler_name="document_manipulation_wiring_contract",
                purpose="show the client contract for document manipulation wiring",
            ),
            SimplePlatformRouteSpec(
                method="POST",
                path=f"{normalized}/actions/check",
                handler_name="check_action",
                purpose="show the normal user shell for a plain action check",
            ),
            SimplePlatformRouteSpec(
                method="POST",
                path=f"{normalized}/actions/experience",
                handler_name="check_action_experience",
                purpose="show the normal user shell while keeping audit details hidden by default",
            ),
            SimplePlatformRouteSpec(
                method="POST",
                path=f"{normalized}/actions/check/audit",
                handler_name="check_action_audit",
                purpose="show proof-bearing action check details for operator audit surfaces",
            ),
            SimplePlatformRouteSpec(
                method="POST",
                path=f"{normalized}/tasks/check",
                handler_name="check_task",
                purpose="show the normal user shell for a template-backed task check",
            ),
            SimplePlatformRouteSpec(
                method="POST",
                path=f"{normalized}/tasks/check/audit",
                handler_name="check_task_audit",
                purpose="show proof-bearing task check details for operator audit surfaces",
            ),
            SimplePlatformRouteSpec(
                method="POST",
                path=f"{normalized}/workflows/check",
                handler_name="check_workflow",
                purpose="show the normal user shell for a common workflow check",
            ),
            SimplePlatformRouteSpec(
                method="POST",
                path=f"{normalized}/workflows/check/audit",
                handler_name="check_workflow_audit",
                purpose="show proof-bearing workflow check details for operator audit surfaces",
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
    route_prefix = _route_prefix(prefix, "prefix")
    router = APIRouter(prefix=route_prefix, tags=["simple-platform"])

    @router.get("/home")
    def simple_home():
        return adapter.simple_home()

    @router.get("/actions")
    def action_menu():
        return adapter.action_menu()

    @router.get("/start")
    def start_guide():
        return adapter.start_guide()

    @router.get("/documents/wiring")
    def document_manipulation_wiring():
        return adapter.document_manipulation_wiring()

    @router.get("/documents/wiring/contract")
    def document_manipulation_wiring_contract():
        return adapter.document_manipulation_wiring_contract()

    @router.post("/actions/check")
    def check_action(request_body: dict[str, Any] = Body(...)):
        return adapter.check_action(request_body)

    @router.post("/actions/experience")
    def check_action_experience(request_body: dict[str, Any] = Body(...)):
        return adapter.check_action_experience(request_body)

    @router.post("/actions/check/audit")
    def check_action_audit(request_body: dict[str, Any] = Body(...)):
        return adapter.check_action_audit(request_body)

    @router.post("/tasks/check")
    def check_task(request_body: dict[str, Any] = Body(...)):
        return adapter.check_task(request_body)

    @router.post("/tasks/check/audit")
    def check_task_audit(request_body: dict[str, Any] = Body(...)):
        return adapter.check_task_audit(request_body)

    @router.post("/workflows/check")
    def check_workflow(request_body: dict[str, Any] = Body(...)):
        return adapter.check_workflow(request_body)

    @router.post("/workflows/check/audit")
    def check_workflow_audit(request_body: dict[str, Any] = Body(...)):
        return adapter.check_workflow_audit(request_body)

    return router


def _route_prefix(value: object, field_name: str) -> str:
    prefix = _require_text(value, field_name).rstrip("/")
    if not prefix.startswith("/"):
        raise RuntimeCoreInvariantError(f"{field_name} must start with /")
    if "?" in prefix or "#" in prefix:
        raise RuntimeCoreInvariantError(f"{field_name} must not contain query or fragment markers")
    if "//" in prefix:
        raise RuntimeCoreInvariantError(f"{field_name} must not contain empty path segments")
    for segment in prefix.split("/")[1:]:
        if segment in {".", ".."}:
            raise RuntimeCoreInvariantError(f"{field_name} must not contain traversal segments")
        if not _is_route_prefix_segment(segment):
            raise RuntimeCoreInvariantError(f"{field_name} contains unsupported path characters")
    return prefix


def _is_route_prefix_segment(segment: str) -> bool:
    return all(char.isascii() and (char.isalnum() or char in {"-", "_", "."}) for char in segment)


def _require_text(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise RuntimeCoreInvariantError(f"{field_name} must be non-empty text")
    return value.strip()
