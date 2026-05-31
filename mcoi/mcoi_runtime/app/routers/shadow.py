"""Read-only InceptaDive Shadow Pass posture routes.

Purpose: expose health and console posture for the shadow interrogation layer
without exposing raw requests, private memory, or execution authority.
Governance scope: observability only; routes cannot inspect live user input,
mutate memory, approve actions, or execute candidate plans.
Dependencies: FastAPI router, dependency container, and shadow app facade.
Invariants: responses are bounded, redacted, deterministic in shape, and always
carry execution_authority=false.
"""

from __future__ import annotations

import os
from typing import Any

from fastapi import APIRouter

from mcoi_runtime.app.inceptadive_shadow_integration import (
    InceptaDiveShadowRuntime,
    build_inceptadive_shadow_runtime,
)
from mcoi_runtime.app.routers.deps import deps

router = APIRouter()


@router.get("/api/v1/health/shadow")
def shadow_health() -> dict[str, object]:
    """Read-only shadow subsystem health posture."""

    _inc_metric("requests_governed")
    runtime, registered = _shadow_runtime()
    posture = runtime.health_posture(created_at=_created_at()).to_dict()
    return {
        "governed": True,
        "registered": registered,
        "shadow": posture,
        "execution_authority": False,
        "raw_request_text_exposed": False,
        "private_memory_exposed": False,
    }


@router.get("/api/v1/console/shadow")
def shadow_console() -> dict[str, object]:
    """Read-only operator console summary for the shadow subsystem."""

    _inc_metric("requests_governed")
    runtime, registered = _shadow_runtime()
    created_at = _created_at()
    posture = runtime.health_posture(created_at=created_at).to_dict()
    summary = runtime.console_summary(created_at=created_at).to_dict()
    return {
        "governed": True,
        "registered": registered,
        "status": str(posture.get("status", "unknown")),
        "health": posture,
        "summary": summary,
        "execution_authority": False,
        "raw_request_text_exposed": False,
        "private_memory_exposed": False,
    }


def _shadow_runtime() -> tuple[InceptaDiveShadowRuntime, bool]:
    """Return registered runtime or a bounded env-derived fallback."""

    try:
        runtime = deps.get("inceptadive_shadow_runtime")
    except RuntimeError:
        return build_inceptadive_shadow_runtime(os.environ), False
    if not isinstance(runtime, InceptaDiveShadowRuntime):
        return build_inceptadive_shadow_runtime(os.environ), False
    return runtime, True


def _created_at() -> str:
    """Return registered server clock when available without requiring it."""

    try:
        clock = deps.get("clock")
    except RuntimeError:
        return "1970-01-01T00:00:00+00:00"
    try:
        value = clock() if callable(clock) else clock
    except (TypeError, ValueError):
        return "1970-01-01T00:00:00+00:00"
    return str(value or "1970-01-01T00:00:00+00:00")


def _inc_metric(name: str) -> None:
    """Increment metrics if the governed metrics dependency is registered."""

    try:
        metrics: Any = deps.get("metrics")
    except RuntimeError:
        return
    inc = getattr(metrics, "inc", None)
    if callable(inc):
        inc(name)
