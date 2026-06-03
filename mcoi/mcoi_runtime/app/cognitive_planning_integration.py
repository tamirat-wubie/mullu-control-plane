"""Plan-time cognitive context integration (read-back), default-OFF.

Purpose: validate the MULLU_COGNITIVE_LOOP_PLAN_CONTEXT env flag and, when enabled,
    build the read-only CognitivePlanningReader from the organs mounted on the
    runtime, plus an exception-isolated entrypoint a plan-compilation router calls to
    attach a learned-context advisory to its response. When the flag is OFF (default)
    the entrypoint returns None and the response is byte-identical.
Governance scope: observability / advisory only. Reads organs; never writes, never
    gates, never mutates the governed plan.
Invariants:
  - Disabled by default; a malformed flag fails SAFE (disabled, error surfaced in the
    report) rather than raising into startup.
  - planning_context_for NEVER raises into the caller and returns None on any error,
    so the read-back can never perturb plan compilation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from mcoi_runtime.core.cognitive_planning import CognitivePlanningReader

COGNITIVE_LOOP_PLAN_CONTEXT_ENV = "MULLU_COGNITIVE_LOOP_PLAN_CONTEXT"
PLANNING_READER_DEP = "cognitive_planning_reader"

_TRUE_VALUES = frozenset({"1", "true", "yes", "on"})
_FALSE_VALUES = frozenset({"0", "false", "no", "off", ""})


@dataclass(frozen=True)
class CognitivePlanningConfigReport:
    """Validation report for the plan-context env flag."""

    enabled: bool
    error: str | None


def _normalize(raw_value: str | None) -> str:
    return (raw_value or "").strip().lower()


def validate_planning_context_config(
    runtime_env: Mapping[str, str],
) -> CognitivePlanningConfigReport:
    """Validate the plan-context env flag without raising into startup."""
    raw_value = runtime_env.get(COGNITIVE_LOOP_PLAN_CONTEXT_ENV)
    normalized = _normalize(raw_value)
    if normalized in _TRUE_VALUES:
        return CognitivePlanningConfigReport(enabled=True, error=None)
    if normalized in _FALSE_VALUES:
        return CognitivePlanningConfigReport(enabled=False, error=None)
    return CognitivePlanningConfigReport(
        enabled=False,
        error=f"unsupported {COGNITIVE_LOOP_PLAN_CONTEXT_ENV} value: {raw_value!r}",
    )


def build_planning_reader(
    runtime_env: Mapping[str, str], organs: object
) -> CognitivePlanningReader | None:
    """Build the read-only planning reader when enabled and organs present, else None."""
    if not validate_planning_context_config(runtime_env).enabled:
        return None
    meta_reasoning = getattr(organs, "meta_reasoning", None)
    world_state = getattr(organs, "world_state", None)
    episodic_memory = getattr(organs, "episodic_memory", None)
    if meta_reasoning is None or world_state is None or episodic_memory is None:
        return None
    return CognitivePlanningReader(
        meta_reasoning=meta_reasoning,
        world_state=world_state,
        episodic_memory=episodic_memory,
    )


def planning_context_for(deps: object, capability_ids: tuple[str, ...]) -> dict | None:
    """Return a read-only plan-time cognitive context dict, or None.

    None when there is no reader (flag OFF / absent) or on ANY error - the read-back
    is advisory and must never perturb plan compilation.
    """
    try:
        reader = deps.get(PLANNING_READER_DEP)
    except Exception:  # noqa: BLE001 - absent/None reader => no context
        return None
    if reader is None:
        return None
    try:
        return reader.read(tuple(capability_ids)).to_dict()
    except Exception:  # noqa: BLE001 - advisory read-back must never break planning
        return None


__all__ = [
    "COGNITIVE_LOOP_PLAN_CONTEXT_ENV",
    "PLANNING_READER_DEP",
    "CognitivePlanningConfigReport",
    "build_planning_reader",
    "planning_context_for",
    "validate_planning_context_config",
]
