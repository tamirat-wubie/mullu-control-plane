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

from mcoi_runtime.app.capability_debt_report import (
    CapabilityDebtReportError,
    build_capability_debt_report,
)
from mcoi_runtime.app.capability_control_system import (
    CapabilityControlSystemError,
    build_capability_control_system,
)
from mcoi_runtime.app.capability_passport_dashboard import (
    CapabilityPassportDashboardError,
    build_capability_passport_dashboard,
)
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
from mcoi_runtime.app.symbol_operator_read_models import (
    SymbolOperatorReadModelError,
    build_component_symbol_read_model,
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


@router.get("/api/v1/components/symbols")
def components_symbol_read_model() -> dict[str, Any]:
    """Return read-only UniversalSymbol projections for registered components."""

    _inc_metric("requests_governed")
    try:
        return build_component_symbol_read_model()
    except (ComponentReadModelError, SymbolOperatorReadModelError) as exc:
        raise HTTPException(
            status_code=500,
            detail={
                "error": "component symbol read model unavailable",
                "error_code": "component_symbol_read_model_unavailable",
                "governed": True,
                "detail": str(exc)[:200],
            },
        ) from exc


@router.get("/api/v1/components/capability-governance")
def components_capability_governance_read_model() -> dict[str, Any]:
    """Return the read-only capability governance operator surface."""

    _inc_metric("requests_governed")
    try:
        dashboard = build_capability_passport_dashboard()
        debt_report = build_capability_debt_report()
        control_system = build_capability_control_system(dashboard=dashboard)
    except (CapabilityPassportDashboardError, CapabilityDebtReportError, CapabilityControlSystemError) as exc:
        raise HTTPException(
            status_code=500,
            detail={
                "error": "capability governance read model unavailable",
                "error_code": "capability_governance_read_model_unavailable",
                "governed": True,
                "detail": str(exc)[:200],
            },
        ) from exc
    dashboard_summary = dict(dashboard["summary"])
    debt_summary = dict(debt_report["summary"])
    control_summary = dict(control_system["summary"])
    return {
        "read_model_id": "capability_governance_operator_read_model.foundation.v1",
        "governed": True,
        "selectable": True,
        "read_model_is_not_execution_authority": True,
        "execution_authority_granted": False,
        "live_execution_enabled": False,
        "live_connector_send_enabled": False,
        "terminal_closure_required": True,
        "summary": {
            "capability_count": dashboard_summary["capability_count"],
            "attention_required_count": dashboard_summary["attention_required_count"],
            "ready_count": dashboard_summary["ready_count"],
            "debt_row_count": debt_summary["debt_row_count"],
            "total_debt_item_count": debt_summary["total_debt_item_count"],
            "critical_debt_count": debt_summary["severity_counts"]["critical"],
            "high_debt_count": debt_summary["severity_counts"]["high"],
            "control_unlocked_count": control_summary["unlocked_count"],
            "control_blocked_count": control_summary["blocked_count"],
            "fast_mode_lab_ready_count": control_summary["fast_mode_lab_ready_count"],
            "live_action_disabled": True,
        },
        "control_system": control_system,
        "dashboard": dashboard,
        "debt_report": debt_report,
    }


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
