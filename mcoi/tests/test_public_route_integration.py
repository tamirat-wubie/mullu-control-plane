"""Tests for optional public runtime route integration.

Purpose: verify server startup can mount simple-platform and dashboard routes
through one explicit environment-gated helper.
Governance scope: startup wiring, disabled-by-default posture, shared runtime
identity, read-only dashboard projection, and execution denial.
Dependencies: public route integration helper and simple platform runtime API.
Invariants: disabled routes do not build dashboard state, enabled dashboard
routes receive a runtime, and projected dashboard responses stay non-executing.
"""

from __future__ import annotations

from typing import Any

from mcoi_runtime.app.operational_dashboard_integration import OperationalDashboardMountResult
from mcoi_runtime.app.public_route_integration import (
    build_simple_operational_dashboard_runtime,
    mount_public_runtime_routes_from_env,
)
from mcoi_runtime.app.simple_platform_integration import SimplePlatformMountResult
from mcoi_runtime.core.operational_dashboard_api import OperationalDashboardRuntime
from mcoi_runtime.core.simple_platform_api import SimplePlatformRuntime


class FakeApp:
    """Minimal app test double with include_router support."""

    def __init__(self) -> None:
        self.routers: list[Any] = []

    def include_router(self, router: Any) -> None:
        self.routers.append(router)


def test_public_runtime_routes_default_to_disabled_without_building_dashboard() -> None:
    app = FakeApp()

    def simple_mount_fn(
        app: Any,
        env: dict[str, str],
        *,
        runtime: SimplePlatformRuntime | None = None,
    ) -> SimplePlatformMountResult:
        assert runtime is None
        return SimplePlatformMountResult(
            enabled=False,
            mounted=False,
            prefix="/api/v1/simple",
            reason="disabled_by_env",
        )

    def dashboard_mount_fn(
        app: Any,
        env: dict[str, str],
        *,
        runtime: OperationalDashboardRuntime | None = None,
    ) -> OperationalDashboardMountResult:
        assert runtime is None
        return OperationalDashboardMountResult(
            enabled=False,
            mounted=False,
            prefix="/api/v1/dashboard",
            reason="disabled_by_env",
        )

    def dashboard_runtime_factory(**_: object) -> OperationalDashboardRuntime:
        raise AssertionError("disabled dashboard must not build a runtime")

    result = mount_public_runtime_routes_from_env(
        app=app,
        runtime_env={},
        clock=lambda: "2026-05-31T00:00:00+00:00",
        simple_mount_fn=simple_mount_fn,
        dashboard_mount_fn=dashboard_mount_fn,
        dashboard_runtime_factory=dashboard_runtime_factory,
    )

    assert result.simple_platform.enabled is False
    assert result.operational_dashboard.enabled is False
    assert result.to_dict()["simple_platform"]["mounted"] is False
    assert result.to_dict()["operational_dashboard"]["mounted"] is False
    assert app.routers == []


def test_public_runtime_routes_share_simple_runtime_when_enabled() -> None:
    app = FakeApp()
    simple_runtime_seen: list[SimplePlatformRuntime] = []
    dashboard_runtime_source_seen: list[SimplePlatformRuntime] = []

    def simple_mount_fn(
        app: Any,
        env: dict[str, str],
        *,
        runtime: SimplePlatformRuntime | None = None,
    ) -> SimplePlatformMountResult:
        assert runtime is not None
        simple_runtime_seen.append(runtime)
        app.include_router({"router": "simple"})
        return SimplePlatformMountResult(
            enabled=True,
            mounted=True,
            prefix="/api/v1/simple",
            reason="mounted",
        )

    def dashboard_runtime_factory(
        *,
        simple_runtime: SimplePlatformRuntime,
        assessed_at: str,
    ) -> OperationalDashboardRuntime:
        assert assessed_at == "2026-05-31T00:00:00+00:00"
        dashboard_runtime_source_seen.append(simple_runtime)
        return build_simple_operational_dashboard_runtime(
            simple_runtime=simple_runtime,
            assessed_at=assessed_at,
        )

    def dashboard_mount_fn(
        app: Any,
        env: dict[str, str],
        *,
        runtime: OperationalDashboardRuntime | None = None,
    ) -> OperationalDashboardMountResult:
        assert runtime is not None
        app.include_router({"router": "dashboard"})
        return OperationalDashboardMountResult(
            enabled=True,
            mounted=True,
            prefix="/api/v1/dashboard",
            reason="mounted",
        )

    result = mount_public_runtime_routes_from_env(
        app=app,
        runtime_env={
            "MULLU_SIMPLE_PLATFORM_ENABLED": "1",
            "MULLU_DASHBOARD_ENABLED": "1",
        },
        clock=lambda: "2026-05-31T00:00:00+00:00",
        simple_mount_fn=simple_mount_fn,
        dashboard_mount_fn=dashboard_mount_fn,
        dashboard_runtime_factory=dashboard_runtime_factory,
    )

    assert result.simple_platform.mounted is True
    assert result.operational_dashboard.mounted is True
    assert simple_runtime_seen == dashboard_runtime_source_seen
    assert app.routers == [{"router": "simple"}, {"router": "dashboard"}]


def test_simple_dashboard_runtime_projects_non_executing_home() -> None:
    runtime = build_simple_operational_dashboard_runtime(
        assessed_at="2026-05-31T00:00:00+00:00",
    )

    home = runtime.simple_home().to_dict()
    simple = runtime.simple_state().to_dict()
    state = runtime.state().to_dict()
    home_payload = home["payload"]["home"]
    simple_payload = simple["payload"]["dashboard"]
    dashboard_payload = state["payload"]["dashboard"]

    assert home["governed"] is True
    assert home["ok"] is True
    assert simple["governed"] is True
    assert simple["ok"] is True
    assert simple_payload["visibility_level"] == "normal_user"
    assert simple_payload["audit_details_visible"] is False
    assert simple_payload["receipts_visible"] is False
    assert simple_payload["proof_details_hidden"] is True
    assert "sdlc_receipt_summaries" not in simple_payload
    assert home_payload["execution_allowed"] is False
    assert home_payload["start_here"]["execution_allowed"] is False
    assert simple_payload["execution_allowed"] is False
    assert simple_payload["simple_start_guide"]["execution_allowed"] is False
    assert dashboard_payload["execution_allowed"] is False
    assert dashboard_payload["simple_start_guide"]["execution_allowed"] is False
    assert simple_payload["simple_workflow_summaries"]
    assert dashboard_payload["simple_workflow_summaries"]
    assert simple_payload["simple_workflow_summaries"][0]["action_refs"][0].startswith(
        "dashboard-simple-action-"
    )
    assert dashboard_payload["simple_workflow_summaries"][0]["action_refs"][0].startswith(
        "dashboard-simple-action-"
    )
    assert all(
        not action_ref.startswith(("gate-decision-", "proof-", "witness-"))
        for summary in dashboard_payload["simple_workflow_summaries"]
        for action_ref in summary["action_refs"]
    )
    assert all(
        not action_ref.startswith(("gate-decision-", "proof-", "witness-"))
        for summary in simple_payload["simple_workflow_summaries"]
        for action_ref in summary["action_refs"]
    )
    assert all("checks" not in summary for summary in simple_payload["simple_workflow_summaries"])
    assert all("decision_ref" not in summary for summary in simple_payload["simple_action_summaries"])
    assert dashboard_payload["workflow_health"] == "ready"
