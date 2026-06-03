"""Shadow-observer integration for the live server.

Purpose: validate the MULLU_COGNITIVE_LOOP_SHADOW env flag and, when enabled,
    build a record-only ShadowCognitiveObserver from the cognitive organs mounted
    on the runtime, plus a fully exception-isolated entrypoint the live routers
    call to record a shadow observation of a real execution. When the flag is OFF
    (default) the builder returns None and the live path is byte-identical.
Governance scope: env-flag validation + observer construction + a no-authority
    recording hook. Never dispatches, never writes engine state, never alters a
    response.
Dependencies: mcoi_runtime.core.cognitive_shadow (the record-only observer) and
    the deps container (read-only lookup of the registered observer).
Invariants:
  - Disabled by default; observability-only, so a malformed flag fails SAFE
    (disabled, error surfaced in the report) rather than raising into startup.
  - record_execution_shadow NEVER raises into the caller: any error is swallowed
    so the shadow can never perturb the live request or response.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Mapping

from mcoi_runtime.core.cognitive_shadow import ShadowCognitiveObserver

COGNITIVE_LOOP_SHADOW_ENV = "MULLU_COGNITIVE_LOOP_SHADOW"
SHADOW_OBSERVER_DEP = "cognitive_shadow_observer"

_TRUE_VALUES = frozenset({"1", "true", "yes", "on"})
_FALSE_VALUES = frozenset({"0", "false", "no", "off", ""})


@dataclass(frozen=True)
class CognitiveShadowConfigReport:
    """Validation report for the cognitive-shadow env configuration."""

    enabled: bool
    error: str | None


def _normalize(raw_value: str | None) -> str:
    return (raw_value or "").strip().lower()


def validate_cognitive_shadow_config(
    runtime_env: Mapping[str, str],
) -> CognitiveShadowConfigReport:
    """Validate the shadow env flag without raising into startup."""
    raw_value = runtime_env.get(COGNITIVE_LOOP_SHADOW_ENV)
    normalized = _normalize(raw_value)
    if normalized in _TRUE_VALUES:
        return CognitiveShadowConfigReport(enabled=True, error=None)
    if normalized in _FALSE_VALUES:
        return CognitiveShadowConfigReport(enabled=False, error=None)
    return CognitiveShadowConfigReport(
        enabled=False,
        error=f"unsupported {COGNITIVE_LOOP_SHADOW_ENV} value: {raw_value!r}",
    )


def build_shadow_observer(
    runtime_env: Mapping[str, str],
    organs: object,
    *,
    clock: Callable[[], str],
) -> ShadowCognitiveObserver | None:
    """Build the record-only observer when enabled and organs are present, else None.

    Fail-safe: a malformed flag (config error) or a runtime missing organs returns
    None - the observer is optional observability and must not break startup. The
    config error, if any, is available via ``validate_cognitive_shadow_config`` so
    the caller may surface it (no silent enable, but no startup crash either).
    """
    report = validate_cognitive_shadow_config(runtime_env)
    if not report.enabled:
        return None
    meta_reasoning = getattr(organs, "meta_reasoning", None)
    world_state = getattr(organs, "world_state", None)
    episodic_memory = getattr(organs, "episodic_memory", None)
    if meta_reasoning is None or world_state is None or episodic_memory is None or clock is None:
        return None
    return ShadowCognitiveObserver(
        meta_reasoning=meta_reasoning,
        world_state=world_state,
        episodic_memory=episodic_memory,
        clock=clock,
    )


def record_execution_shadow(deps: object, *, capability_id: str, succeeded: bool) -> None:
    """Record one shadow observation of a live execution. NEVER raises.

    Resolves the (optional) observer registered on ``deps``. A missing/None
    observer (flag OFF) is a no-op. Any error during observation is swallowed so
    the shadow can never perturb the live request or response.
    """
    try:
        observer = deps.get(SHADOW_OBSERVER_DEP)
    except Exception:  # noqa: BLE001 - absent/None observer => shadow disabled
        return
    if observer is None:
        return
    try:
        observer.observe(capability_id=str(capability_id), live_succeeded=bool(succeeded))
    except Exception:  # noqa: BLE001 - shadow must never perturb the live path
        return


__all__ = [
    "COGNITIVE_LOOP_SHADOW_ENV",
    "SHADOW_OBSERVER_DEP",
    "CognitiveShadowConfigReport",
    "build_shadow_observer",
    "record_execution_shadow",
    "validate_cognitive_shadow_config",
]
