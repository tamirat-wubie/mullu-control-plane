"""Tests for operational dashboard app integration.

Purpose: verify host apps can mount read-only dashboard routes through an
environment gate without constructing dashboard state implicitly.
Governance scope: integration helper only; dashboard runtime and router
factory retain envelope and route authority.
Dependencies: dashboard integration helper, runtime API, and dashboard
projection dataclasses.
Invariants: disabled integration does not mount routes, enabled integration
requires an explicit runtime, and mount results are explicit.
"""

from __future__ import annotations

from typing import Any

import pytest

from mcoi_runtime.app.operational_dashboard_integration import (
    OperationalDashboardMountResult,
    mount_operational_dashboard_router_from_env,
)
from mcoi_runtime.core.operational_dashboard_api import OperationalDashboardRuntime
from mcoi_runtime.core.operational_dashboard_intelligence import (
    DashboardSimpleHomeSummary,
    OperationalDashboardState,
    WorkflowHealth,
)


class FakeApp:
    """Minimal app test double with include_router support."""

    def __init__(self) -> None:
        self.routers: list[Any] = []

    def include_router(self, router: Any) -> None:
        self.routers.append(router)


def _dashboard_runtime() -> OperationalDashboardRuntime:
    state = OperationalDashboardState(
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
    return OperationalDashboardRuntime.from_state(state)


def test_operational_dashboard_integration_mounts_when_enabled() -> None:
    app = FakeApp()
    runtime = _dashboard_runtime()
    runtime_seen: list[OperationalDashboardRuntime] = []
    prefix_seen: list[str] = []

    def router_factory(dashboard_runtime: OperationalDashboardRuntime, prefix: str) -> dict[str, object]:
        runtime_seen.append(dashboard_runtime)
        prefix_seen.append(prefix)
        return {"router": "operational-dashboard", "prefix": prefix}

    result = mount_operational_dashboard_router_from_env(
        app,
        {"MULLU_DASHBOARD_ENABLED": "1", "MULLU_DASHBOARD_PREFIX": "/dashboard"},
        runtime=runtime,
        router_factory=router_factory,
    )

    assert result.enabled is True
    assert result.mounted is True
    assert result.prefix == "/dashboard"
    assert result.reason == "mounted"
    assert result.to_dict()["mounted"] is True
    assert app.routers == [{"router": "operational-dashboard", "prefix": "/dashboard"}]
    assert runtime_seen == [runtime]
    assert prefix_seen == ["/dashboard"]


def test_operational_dashboard_integration_uses_shared_env_flag_parser() -> None:
    app = FakeApp()
    runtime = _dashboard_runtime()

    def router_factory(dashboard_runtime: OperationalDashboardRuntime, prefix: str) -> dict[str, str]:
        assert dashboard_runtime is runtime
        return {"prefix": prefix}

    result = mount_operational_dashboard_router_from_env(
        app,
        {"MULLU_DASHBOARD_ENABLED": " YES ", "MULLU_DASHBOARD_PREFIX": "/dashboard"},
        runtime=runtime,
        router_factory=router_factory,
    )

    assert result.enabled is True
    assert result.mounted is True
    assert result.prefix == "/dashboard"
    assert app.routers == [{"prefix": "/dashboard"}]


def test_operational_dashboard_integration_defaults_to_disabled_without_env_flag(monkeypatch) -> None:
    app = FakeApp()
    monkeypatch.setenv("MULLU_DASHBOARD_ENABLED", "1")

    def router_factory(dashboard_runtime: OperationalDashboardRuntime, prefix: str) -> object:
        raise AssertionError("explicit env mapping must not fall back to process env")

    result = mount_operational_dashboard_router_from_env(
        app,
        {},
        runtime=_dashboard_runtime(),
        router_factory=router_factory,
    )

    assert result == OperationalDashboardMountResult(
        enabled=False,
        mounted=False,
        prefix="/api/v1/dashboard",
        reason="disabled_by_env",
    )
    assert app.routers == []


def test_operational_dashboard_integration_ignores_malformed_prefix_when_disabled() -> None:
    app = FakeApp()

    result = mount_operational_dashboard_router_from_env(
        app,
        {"MULLU_DASHBOARD_ENABLED": "0", "MULLU_DASHBOARD_PREFIX": "dashboard"},
        runtime=_dashboard_runtime(),
    )

    assert result.enabled is False
    assert result.mounted is False
    assert result.prefix == "/api/v1/dashboard"
    assert result.reason == "disabled_by_env"
    assert app.routers == []


def test_operational_dashboard_integration_requires_runtime_when_enabled() -> None:
    app = FakeApp()

    def router_factory(dashboard_runtime: OperationalDashboardRuntime, prefix: str) -> object:
        raise AssertionError("router factory must not be called without runtime")

    result = mount_operational_dashboard_router_from_env(
        app,
        {"MULLU_DASHBOARD_ENABLED": "true"},
        router_factory=router_factory,
    )

    assert result.enabled is True
    assert result.mounted is False
    assert result.prefix == "/api/v1/dashboard"
    assert result.reason == "runtime_required"
    assert app.routers == []


def test_operational_dashboard_integration_uses_default_prefix() -> None:
    app = FakeApp()

    def router_factory(dashboard_runtime: OperationalDashboardRuntime, prefix: str) -> dict[str, str]:
        return {"prefix": prefix}

    result = mount_operational_dashboard_router_from_env(
        app,
        {"MULLU_DASHBOARD_ENABLED": "enabled"},
        runtime=_dashboard_runtime(),
        router_factory=router_factory,
    )

    assert result.enabled is True
    assert result.mounted is True
    assert result.prefix == "/api/v1/dashboard"
    assert result.reason == "mounted"
    assert app.routers == [{"prefix": "/api/v1/dashboard"}]


def test_operational_dashboard_integration_rejects_malformed_prefix() -> None:
    app = FakeApp()

    with pytest.raises(RuntimeError, match="MULLU_DASHBOARD_PREFIX must start with '/'"):
        mount_operational_dashboard_router_from_env(
            app,
            {"MULLU_DASHBOARD_ENABLED": "1", "MULLU_DASHBOARD_PREFIX": "dashboard"},
            runtime=_dashboard_runtime(),
        )

    assert app.routers == []
