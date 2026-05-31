"""Public runtime route integration for the governed HTTP server.

Purpose: wire optional simple-platform and operational-dashboard routes into
server startup through explicit environment flags.
Governance scope: app bootstrap only; route runtimes keep request validation,
read-only projection, and execution-denial authority.
Dependencies: simple platform integration, operational dashboard integration,
note-memory projection, and dashboard projection builders.
Invariants: public routes are disabled by default, enabled routes mount only
through their bounded helpers, dashboard state remains read-only, and no
startup path grants execution authority.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping

from mcoi_runtime.app._integration_paths import env_flag
from mcoi_runtime.app.operational_dashboard_integration import (
    OperationalDashboardMountResult,
    mount_operational_dashboard_router_from_env,
)
from mcoi_runtime.app.simple_platform_integration import (
    SimplePlatformMountResult,
    mount_simple_platform_router_from_env,
)
from mcoi_runtime.core.note_memory_projection import project_note_memory
from mcoi_runtime.core.operational_dashboard_api import OperationalDashboardRuntime
from mcoi_runtime.core.operational_dashboard_intelligence import (
    build_operational_dashboard_state,
)
from mcoi_runtime.core.simple_platform import (
    SimplePlatform,
    SimpleTaskTemplate,
    SimpleWorkflowTemplate,
)
from mcoi_runtime.core.simple_platform_api import SimplePlatformRuntime


PublicRouteClock = Callable[[], str]
SimpleMountFn = Callable[..., SimplePlatformMountResult]
DashboardMountFn = Callable[..., OperationalDashboardMountResult]
DashboardRuntimeFactory = Callable[..., OperationalDashboardRuntime]


@dataclass(frozen=True)
class PublicRuntimeRouteBootstrap:
    """Startup posture for optional public runtime route integration."""

    simple_platform: SimplePlatformMountResult
    operational_dashboard: OperationalDashboardMountResult

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-compatible startup posture."""

        return {
            "simple_platform": self.simple_platform.to_dict(),
            "operational_dashboard": self.operational_dashboard.to_dict(),
        }


def mount_public_runtime_routes_from_env(
    *,
    app: Any,
    runtime_env: Mapping[str, str],
    clock: PublicRouteClock,
    simple_runtime: SimplePlatformRuntime | None = None,
    simple_mount_fn: SimpleMountFn = mount_simple_platform_router_from_env,
    dashboard_mount_fn: DashboardMountFn = mount_operational_dashboard_router_from_env,
    dashboard_runtime_factory: DashboardRuntimeFactory | None = None,
) -> PublicRuntimeRouteBootstrap:
    """Mount optional public runtime routes through one server bootstrap point."""

    simple_enabled = env_flag(runtime_env.get("MULLU_SIMPLE_PLATFORM_ENABLED"))
    dashboard_enabled = env_flag(runtime_env.get("MULLU_DASHBOARD_ENABLED"))
    shared_simple_runtime = simple_runtime
    if (simple_enabled or dashboard_enabled) and shared_simple_runtime is None:
        shared_simple_runtime = SimplePlatformRuntime()

    simple_mount = simple_mount_fn(
        app,
        runtime_env,
        runtime=shared_simple_runtime,
    )
    dashboard_runtime = None
    if dashboard_enabled:
        if shared_simple_runtime is None:
            shared_simple_runtime = SimplePlatformRuntime()
        runtime_factory = dashboard_runtime_factory or build_simple_operational_dashboard_runtime
        dashboard_runtime = runtime_factory(
            simple_runtime=shared_simple_runtime,
            assessed_at=clock(),
        )

    dashboard_mount = dashboard_mount_fn(
        app,
        runtime_env,
        runtime=dashboard_runtime,
    )
    return PublicRuntimeRouteBootstrap(
        simple_platform=simple_mount,
        operational_dashboard=dashboard_mount,
    )


def build_simple_operational_dashboard_runtime(
    *,
    simple_runtime: SimplePlatformRuntime | None = None,
    assessed_at: str,
) -> OperationalDashboardRuntime:
    """Build a read-only dashboard runtime from the simple-platform catalog."""

    runtime = simple_runtime or SimplePlatformRuntime()
    platform = runtime.platform
    projection = project_note_memory((), assessed_at=assessed_at)
    workflow_plans = tuple(
        platform.check_workflow(
            {
                "workflow": template.workflow,
                "target": _dashboard_workflow_target(template, platform),
                "goal": template.default_goal,
                "actor_id": "dashboard-startup",
            }
        )
        for template in platform.workflow_templates()
    )
    state = build_operational_dashboard_state(
        projection=projection,
        simple_workflow_plans=workflow_plans,
        simple_start_guide=platform.onboarding_guide(),
    )
    return OperationalDashboardRuntime.from_state(state)


def _dashboard_workflow_target(
    template: SimpleWorkflowTemplate,
    platform: SimplePlatform,
) -> str:
    """Return a deterministic sample target for dashboard workflow previews."""

    if template.default_target:
        return template.default_target
    task_templates = {task.task: task for task in platform.task_templates()}
    for task_name in template.tasks:
        task_template = task_templates.get(task_name)
        if task_template is None:
            raise RuntimeError("dashboard workflow task catalog is incomplete")
        target = _dashboard_task_target(task_template)
        if target:
            return target
    if template.target_required:
        raise RuntimeError("dashboard workflow target is required")
    return ""


def _dashboard_task_target(template: SimpleTaskTemplate) -> str:
    """Return a sample target that stays inside the task boundary."""

    if template.default_target:
        return template.default_target
    allowed_area = template.allowed_area
    if allowed_area == "**":
        return "README.md"
    if allowed_area.endswith("/**"):
        return f"{allowed_area[:-3]}/README.md"
    if "*" not in allowed_area:
        return allowed_area
    return ""
