"""Tests for operational dashboard runtime API and FastAPI adapter.

Purpose: verify app-facing dashboard envelopes expose the simple home summary
without granting execution authority.
Governance scope: dashboard API remains projection-only and rejects invalid
state providers.
Dependencies: operational dashboard API, FastAPI adapter, and dashboard
projection dataclasses.
Invariants: full state and home endpoints are governed, read-only, and stable.
"""

from __future__ import annotations

from mcoi_runtime.core.operational_dashboard_api import OperationalDashboardRuntime
from mcoi_runtime.core.operational_dashboard_fastapi_router import (
    OperationalDashboardFastAPIAdapter,
    create_operational_dashboard_fastapi_router,
)
from mcoi_runtime.core.operational_dashboard_intelligence import (
    DashboardSimpleHomeSummary,
    OperationalDashboardState,
    WorkflowHealth,
)


def _dashboard_state() -> OperationalDashboardState:
    return OperationalDashboardState(
        dashboard_id="dashboard-test",
        projection_id="projection-test",
        active_project_count=1,
        ready_action_ids=(),
        blocked_action_ids=(),
        open_blocker_ids=(),
        open_conflict_ids=(),
        repair_ids=(),
        stale_high_impact_claim_ids=(),
        high_intensity_box_ids=(),
        constructive_delta_ids=(),
        fracture_delta_ids=(),
        memory_confidence_trend=1.0,
        workflow_health=WorkflowHealth.READY,
        execution_readiness="no_action_candidate_ready",
        interrogation_task_ids=(),
        simple_home_summary=DashboardSimpleHomeSummary(
            title="Ready",
            message="Users can start with the recommended simple workflow path.",
            primary_command="mullu workflows",
            ready_workflow_count=1,
            review_workflow_count=0,
            blocked_workflow_count=0,
        ),
    )


def test_operational_dashboard_runtime_returns_simple_home_envelope() -> None:
    runtime = OperationalDashboardRuntime.from_state(_dashboard_state())
    envelope = runtime.simple_home().to_dict()

    assert envelope["governed"] is True
    assert envelope["ok"] is True
    assert envelope["status"] == "ready"
    assert envelope["payload"]["home"]["title"] == "Ready"
    assert envelope["payload"]["home"]["status_label"] == "Ready"
    assert envelope["payload"]["home"]["count_summary"] == "1 ready, 0 need review, 0 blocked"
    assert envelope["payload"]["home"]["next_action"] == "Start with `mullu workflows`."
    assert envelope["payload"]["home"]["action_items"] == []
    assert envelope["payload"]["home"]["command_guidance"] == ["mullu workflows"]
    assert envelope["payload"]["home"]["start_here"]["title"] == "Start here"
    assert envelope["payload"]["home"]["start_here"]["status_label"] == "Ready"
    assert envelope["payload"]["home"]["start_here"]["command_guidance"] == ["mullu workflows"]
    assert envelope["payload"]["home"]["primary_command"] == "mullu workflows"
    assert envelope["payload"]["home"]["execution_allowed"] is False


def test_operational_dashboard_runtime_returns_full_state_envelope() -> None:
    runtime = OperationalDashboardRuntime.from_state(_dashboard_state())
    envelope = runtime.state().to_dict()

    assert envelope["governed"] is True
    assert envelope["ok"] is True
    assert envelope["payload"]["dashboard"]["dashboard_id"] == "dashboard-test"
    assert envelope["payload"]["dashboard"]["simple_home_summary"]["ready_workflow_count"] == 1
    assert envelope["payload"]["dashboard"]["execution_allowed"] is False


def test_operational_dashboard_runtime_rejects_invalid_provider() -> None:
    runtime = OperationalDashboardRuntime(lambda: object())  # type: ignore[arg-type, return-value]
    envelope = runtime.simple_home().to_dict()

    assert envelope["governed"] is True
    assert envelope["ok"] is False
    assert envelope["status"] == "rejected"
    assert "OperationalDashboardState" in envelope["error"]


def test_operational_dashboard_fastapi_adapter_route_specs_are_stable() -> None:
    specs = OperationalDashboardFastAPIAdapter.route_specs()

    assert [(spec.method, spec.path, spec.handler_name) for spec in specs] == [
        ("GET", "/api/v1/dashboard/home", "simple_home"),
        ("GET", "/api/v1/dashboard/state", "state"),
    ]
    assert all(spec.purpose for spec in specs)


def test_operational_dashboard_fastapi_adapter_preserves_runtime_envelopes() -> None:
    adapter = OperationalDashboardFastAPIAdapter(OperationalDashboardRuntime.from_state(_dashboard_state()))

    home = adapter.simple_home()
    state = adapter.state()

    assert home["governed"] is True
    assert home["payload"]["home"]["primary_command"] == "mullu workflows"
    assert state["payload"]["dashboard"]["simple_home_summary"]["execution_allowed"] is False


def test_create_operational_dashboard_fastapi_router_reports_missing_dependency() -> None:
    runtime = OperationalDashboardRuntime.from_state(_dashboard_state())

    try:
        router = create_operational_dashboard_fastapi_router(runtime)
    except RuntimeError as exc:
        assert "FastAPI is required" in str(exc)
    else:
        assert router is not None
