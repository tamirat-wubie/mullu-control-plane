"""Cognitive loop integration for the control-plane app.

Purpose: validate and, when explicitly enabled, construct the bounded cognitive
loop that wraps the EXISTING governed single-step dispatch with the already
bootstrapped cognitive engines (meta-reasoning, decision-learning, world-state,
episodic memory, learning admission). When the flag is OFF this helper returns
None and the live operator path is byte-identical to today.
Governance scope: env-flag validation and cognitive-loop construction boundary
only. This helper never mutates the runtime, never reimplements dispatch, and
introduces no module-global state.
Dependencies: cognitive loop runtime (mcoi_runtime.core.cognitive_loop) and the
already-bootstrapped runtime object produced by app.bootstrap.
Invariants:
  - Disabled by default; an unknown env value is a hard validation error surfaced
    in the report and never silently enabled.
  - ``validate_cognitive_loop_config`` never raises into startup.
  - ``build_cognitive_loop`` returns None when disabled and otherwise wires a
    CognitiveLoop from engines that ALREADY exist on the bootstrapped runtime
    (it constructs no new engines and mutates no runtime state).
  - Construction is idempotent: calling it twice with the same inputs yields
    equivalent, independent handles with no shared mutable global state.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from mcoi_runtime.core.cognitive_loop import CognitiveLoop, InnerCritic


COGNITIVE_LOOP_ENABLED_ENV = "MULLU_COGNITIVE_LOOP_ENABLED"
COGNITIVE_LOOP_SHADOW_ENV = "MULLU_COGNITIVE_LOOP_SHADOW"

_TRUE_VALUES = frozenset({"1", "true", "yes", "on"})
_FALSE_VALUES = frozenset({"0", "false", "no", "off", ""})


@dataclass(frozen=True)
class CognitiveLoopConfigReport:
    """Validation report for the cognitive loop env configuration."""

    enabled: bool
    error: str | None


def _normalize(raw_value: str | None) -> str:
    return (raw_value or "").strip().lower()


def validate_cognitive_loop_config(
    runtime_env: Mapping[str, str],
) -> CognitiveLoopConfigReport:
    """Validate the cognitive loop env flag without raising into startup."""
    raw_value = runtime_env.get(COGNITIVE_LOOP_ENABLED_ENV)
    normalized = _normalize(raw_value)
    if normalized in _TRUE_VALUES:
        return CognitiveLoopConfigReport(enabled=True, error=None)
    if normalized in _FALSE_VALUES:
        return CognitiveLoopConfigReport(enabled=False, error=None)
    return CognitiveLoopConfigReport(
        enabled=False,
        error=f"unsupported {COGNITIVE_LOOP_ENABLED_ENV} value: {raw_value!r}",
    )


def build_cognitive_loop(
    runtime_env: Mapping[str, str],
    runtime: object,
    *,
    inner_critic: InnerCritic | None = None,
    max_steps: int = 3,
    step_budget: int = 3,
) -> CognitiveLoop | None:
    """Build the cognitive loop when the env flag is enabled, else return None.

    The loop is wired from engines that already exist on the bootstrapped
    runtime. A malformed flag is surfaced explicitly (no silent failure). A
    runtime missing a required engine is also an explicit error rather than a
    silently degraded loop.

    ``inner_critic`` is optional: when omitted the loop installs the default
    NullCritic and VERIFY is byte-identical to the mechanical-only behavior. A
    caller may pass a real (deterministic) critic to enable monotone-skeptic
    downgrade of mechanically-passing-but-wrong outcomes.
    """
    report = validate_cognitive_loop_config(runtime_env)
    if report.error is not None:
        raise ValueError(report.error)
    if not report.enabled:
        return None

    governed_dispatcher = getattr(runtime, "governed_dispatcher", None)
    world_state = getattr(runtime, "world_state", None)
    episodic_memory = getattr(runtime, "episodic_memory", None)
    meta_reasoning = getattr(runtime, "meta_reasoning", None)
    decision_learning = getattr(runtime, "decision_learning", None)
    clock = getattr(runtime, "clock", None)
    working_memory = getattr(runtime, "working_memory", None)

    missing = [
        name
        for name, value in (
            ("governed_dispatcher", governed_dispatcher),
            ("world_state", world_state),
            ("episodic_memory", episodic_memory),
            ("meta_reasoning", meta_reasoning),
            ("decision_learning", decision_learning),
            ("clock", clock),
        )
        if value is None
    ]
    if missing:
        raise ValueError(
            "cognitive loop cannot be built; runtime is missing required engines: "
            + ", ".join(missing)
        )

    return CognitiveLoop(
        governed_dispatcher=governed_dispatcher,
        world_state=world_state,
        episodic_memory=episodic_memory,
        meta_reasoning=meta_reasoning,
        decision_learning=decision_learning,
        clock=clock,
        working_memory=working_memory,
        inner_critic=inner_critic,
        max_steps=max_steps,
        step_budget=step_budget,
    )


def validate_cognitive_loop_shadow_config(
    runtime_env: Mapping[str, str],
) -> CognitiveLoopConfigReport:
    """Validate the Stage-A shadow-mode env flag without raising into startup."""
    raw_value = runtime_env.get(COGNITIVE_LOOP_SHADOW_ENV)
    normalized = _normalize(raw_value)
    if normalized in _TRUE_VALUES:
        return CognitiveLoopConfigReport(enabled=True, error=None)
    if normalized in _FALSE_VALUES:
        return CognitiveLoopConfigReport(enabled=False, error=None)
    return CognitiveLoopConfigReport(
        enabled=False,
        error=f"unsupported {COGNITIVE_LOOP_SHADOW_ENV} value: {raw_value!r}",
    )


def attach_shadow_observer(
    runtime_env: Mapping[str, str],
    runtime: object,
    operator_loop: object,
) -> bool:
    """Attach a side-effect-free Stage-A shadow observer to an OperatorLoop.

    Default-OFF: when ``MULLU_COGNITIVE_LOOP_SHADOW`` is not truthy this is a
    no-op and returns False (the operator loop is left byte-identical to today).
    A malformed flag is an explicit error, never a silent enable. When enabled,
    builds a CognitiveLoop wired from the runtime's existing engines (with a
    PeerReviewCritic so the shadow VERIFY preview has teeth) and sets it as the
    operator loop's ``shadow_loop`` so each dispatched run is also observed.

    Returns True iff a shadow observer was attached. Idempotent: a second call
    with the flag on replaces the handle with an equivalent, independent one.
    """
    report = validate_cognitive_loop_shadow_config(runtime_env)
    if report.error is not None:
        raise ValueError(report.error)
    if not report.enabled:
        return False

    # Reuse the same engine wiring as the enabled loop, but force-build it
    # regardless of the (separate) MULLU_COGNITIVE_LOOP_ENABLED flag - shadow is
    # its own opt-in. We construct directly to avoid coupling the two flags.
    from mcoi_runtime.core.peer_review_critic import PeerReviewCritic

    shadow_loop = build_cognitive_loop(
        {COGNITIVE_LOOP_ENABLED_ENV: "1"},
        runtime,
        inner_critic=PeerReviewCritic(strict=True),
    )
    if shadow_loop is None:  # defensive: build_cognitive_loop returned nothing
        raise ValueError("shadow observer requested but cognitive loop could not be built")
    setattr(operator_loop, "shadow_loop", shadow_loop)
    return True


__all__ = [
    "COGNITIVE_LOOP_ENABLED_ENV",
    "COGNITIVE_LOOP_SHADOW_ENV",
    "attach_shadow_observer",
    "validate_cognitive_loop_shadow_config",
    "CognitiveLoopConfigReport",
    "build_cognitive_loop",
    "validate_cognitive_loop_config",
]
