"""App integration helper for simple governed platform routes.

Purpose: mount the simple platform FastAPI router behind an explicit
environment gate so host apps can expose plain task checks without wiring MVK
internals.
Governance scope: app integration only; SimplePlatformRuntime and MVK remain
the authority for request validation, proof refs, and action decisions.
Dependencies: dataclasses, os, simple platform runtime API, and optional router
factory injection for tests.
Invariants: disabled integration does not import FastAPI, enabled integration
mounts only through the simple platform router factory, and no route grants
execution authority.
"""

from __future__ import annotations

from dataclasses import dataclass
import os
from typing import Any, Callable, Mapping

from mcoi_runtime.app._integration_paths import env_flag, route_prefix_or_default, validate_route_prefix
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
from mcoi_runtime.core.simple_platform_api import SimplePlatformRuntime
from mcoi_runtime.core.simple_platform_fastapi_router import create_simple_platform_fastapi_router


SimplePlatformRouterFactory = Callable[[SimplePlatformRuntime, str], Any]
_DEFAULT_SIMPLE_PLATFORM_PREFIX = "/api/v1/simple"


@dataclass(frozen=True)
class SimplePlatformMountResult:
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


def mount_simple_platform_router_from_env(
    app: Any,
    env: Mapping[str, str] | None = None,
    *,
    runtime: SimplePlatformRuntime | None = None,
    router_factory: SimplePlatformRouterFactory = create_simple_platform_fastapi_router,
) -> SimplePlatformMountResult:
    """Mount simple platform routes when enabled by environment policy."""

    runtime_env = os.environ if env is None else env
    if not env_flag(runtime_env.get("MULLU_SIMPLE_PLATFORM_ENABLED")):
        return SimplePlatformMountResult(
            enabled=False,
            mounted=False,
            prefix=route_prefix_or_default(
                runtime_env.get("MULLU_SIMPLE_PLATFORM_PREFIX"),
                default=_DEFAULT_SIMPLE_PLATFORM_PREFIX,
                env_name="MULLU_SIMPLE_PLATFORM_PREFIX",
            ),
            reason="disabled_by_env",
        )
    try:
        prefix = validate_route_prefix(
            runtime_env.get("MULLU_SIMPLE_PLATFORM_PREFIX"),
            default=_DEFAULT_SIMPLE_PLATFORM_PREFIX,
            env_name="MULLU_SIMPLE_PLATFORM_PREFIX",
        )
    except RuntimeError as exc:
        raise RuntimeCoreInvariantError(str(exc).replace("'", "")) from exc
    simple_runtime = runtime or SimplePlatformRuntime()
    router = router_factory(simple_runtime, prefix)
    app.include_router(router)
    return SimplePlatformMountResult(
        enabled=True,
        mounted=True,
        prefix=prefix,
        reason="mounted",
    )
