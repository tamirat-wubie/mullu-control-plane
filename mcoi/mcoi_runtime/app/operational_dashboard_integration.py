"""App integration helper for read-only operational dashboard routes.

Purpose: mount dashboard home and state routes behind an explicit environment
gate so host apps can expose simple platform status without wiring dashboard
projection internals into startup code.
Governance scope: app integration only; OperationalDashboardRuntime remains
the authority for read-only envelopes and execution denial.
Dependencies: dataclasses, os, operational dashboard runtime API, and optional
router factory injection for tests.
Invariants: disabled integration does not import FastAPI, enabled integration
requires an explicit dashboard runtime, and mounted routes grant no execution
authority.
"""

from __future__ import annotations

from dataclasses import dataclass
import os
from typing import Any, Callable, Mapping

from mcoi_runtime.app._integration_paths import route_prefix_or_default, validate_route_prefix
from mcoi_runtime.core.operational_dashboard_api import OperationalDashboardRuntime
from mcoi_runtime.core.operational_dashboard_fastapi_router import create_operational_dashboard_fastapi_router


OperationalDashboardRouterFactory = Callable[[OperationalDashboardRuntime, str], Any]
_DEFAULT_OPERATIONAL_DASHBOARD_PREFIX = "/api/v1/dashboard"


@dataclass(frozen=True)
class OperationalDashboardMountResult:
    """Mount outcome for host app startup reporting."""

    enabled: bool
    mounted: bool
    prefix: str
    reason: str

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-compatible mount result."""

        return {
            "enabled": self.enabled,
            "mounted": self.mounted,
            "prefix": self.prefix,
            "reason": self.reason,
        }


def mount_operational_dashboard_router_from_env(
    app: Any,
    env: Mapping[str, str] | None = None,
    *,
    runtime: OperationalDashboardRuntime | None = None,
    router_factory: OperationalDashboardRouterFactory = create_operational_dashboard_fastapi_router,
) -> OperationalDashboardMountResult:
    """Mount dashboard routes when enabled by environment policy."""

    runtime_env = os.environ if env is None else env
    if not _env_flag(runtime_env.get("MULLU_DASHBOARD_ENABLED")):
        return OperationalDashboardMountResult(
            enabled=False,
            mounted=False,
            prefix=route_prefix_or_default(
                runtime_env.get("MULLU_DASHBOARD_PREFIX"),
                default=_DEFAULT_OPERATIONAL_DASHBOARD_PREFIX,
                env_name="MULLU_DASHBOARD_PREFIX",
            ),
            reason="disabled_by_env",
        )
    prefix = validate_route_prefix(
        runtime_env.get("MULLU_DASHBOARD_PREFIX"),
        default=_DEFAULT_OPERATIONAL_DASHBOARD_PREFIX,
        env_name="MULLU_DASHBOARD_PREFIX",
    )
    if runtime is None:
        return OperationalDashboardMountResult(
            enabled=True,
            mounted=False,
            prefix=prefix,
            reason="runtime_required",
        )
    router = router_factory(runtime, prefix)
    app.include_router(router)
    return OperationalDashboardMountResult(
        enabled=True,
        mounted=True,
        prefix=prefix,
        reason="mounted",
    )


def _env_flag(value: str | None) -> bool:
    """Parse common environment flag spellings."""

    if value is None:
        return False
    return value.strip().lower() in {"1", "true", "yes", "on", "enabled"}
