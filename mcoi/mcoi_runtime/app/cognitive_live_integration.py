"""Live-acting cognitive integration for the server (Stage B + Stage C).

Purpose: validate the enforce/learn env flags and, when enabled, build the
    pre-dispatch DECIDE gate (Stage B) and the post-outcome learner (Stage C) from
    the organs mounted on the runtime, plus the live-router entrypoints that apply
    them. Both flags are default-OFF; with both off the live path is byte-identical.
Governance scope: env-flag validation + construction + two no-/low-authority hooks.
  - The gate can only WITHHOLD a dispatch (safety-positive); it is fail-OPEN on
    error (a gate bug must never wedge live traffic - existing governance still
    applies), so an exception degrades to "allow" (parity with today), never to a
    spurious block.
  - The learner only writes confidence + episodic outcomes; record_execution_learning
    NEVER raises into the caller.
Invariants:
  - Disabled by default; a malformed flag fails SAFE (disabled, error surfaced in
    the report) rather than raising into startup.
  - evaluate_execution_gate returns None (=> allow) when the gate is absent/off or
    on ANY error (fail-open). record_execution_learning is a no-op when off and
    swallows every error.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Mapping

from mcoi_runtime.core.cognitive_live import (
    CognitiveExecutionGate,
    CognitiveLearner,
    GateDecision,
)

COGNITIVE_LOOP_ENFORCE_ENV = "MULLU_COGNITIVE_LOOP_ENFORCE"
COGNITIVE_LOOP_LEARN_ENV = "MULLU_COGNITIVE_LOOP_LEARN"
EXECUTION_GATE_DEP = "cognitive_execution_gate"
LEARNER_DEP = "cognitive_learner"

_TRUE_VALUES = frozenset({"1", "true", "yes", "on"})
_FALSE_VALUES = frozenset({"0", "false", "no", "off", ""})


@dataclass(frozen=True)
class CognitiveLiveConfigReport:
    """Validation report for one live-cognitive env flag."""

    enabled: bool
    error: str | None


def _normalize(raw_value: str | None) -> str:
    return (raw_value or "").strip().lower()


def _validate(runtime_env: Mapping[str, str], env_name: str) -> CognitiveLiveConfigReport:
    raw_value = runtime_env.get(env_name)
    normalized = _normalize(raw_value)
    if normalized in _TRUE_VALUES:
        return CognitiveLiveConfigReport(enabled=True, error=None)
    if normalized in _FALSE_VALUES:
        return CognitiveLiveConfigReport(enabled=False, error=None)
    return CognitiveLiveConfigReport(
        enabled=False,
        error=f"unsupported {env_name} value: {raw_value!r}",
    )


def validate_enforce_config(runtime_env: Mapping[str, str]) -> CognitiveLiveConfigReport:
    """Validate the Stage-B enforce flag without raising into startup."""
    return _validate(runtime_env, COGNITIVE_LOOP_ENFORCE_ENV)


def validate_learn_config(runtime_env: Mapping[str, str]) -> CognitiveLiveConfigReport:
    """Validate the Stage-C learn flag without raising into startup."""
    return _validate(runtime_env, COGNITIVE_LOOP_LEARN_ENV)


def build_execution_gate(
    runtime_env: Mapping[str, str], organs: object
) -> CognitiveExecutionGate | None:
    """Build the Stage-B DECIDE gate when enabled and organs are present, else None.

    Fail-safe: a malformed flag or missing organ returns None (the gate is optional;
    a typo must not crash startup). When None, the live path applies no gate.
    """
    if not validate_enforce_config(runtime_env).enabled:
        return None
    meta_reasoning = getattr(organs, "meta_reasoning", None)
    if meta_reasoning is None:
        return None
    return CognitiveExecutionGate(meta_reasoning=meta_reasoning)


def build_learner(
    runtime_env: Mapping[str, str],
    organs: object,
    *,
    clock: Callable[[], str],
) -> CognitiveLearner | None:
    """Build the Stage-C learner when enabled and organs are present, else None."""
    if not validate_learn_config(runtime_env).enabled:
        return None
    meta_reasoning = getattr(organs, "meta_reasoning", None)
    episodic_memory = getattr(organs, "episodic_memory", None)
    if meta_reasoning is None or episodic_memory is None or clock is None:
        return None
    return CognitiveLearner(
        meta_reasoning=meta_reasoning,
        episodic_memory=episodic_memory,
        clock=clock,
    )


def evaluate_execution_gate(deps: object, *, capability_id: str) -> GateDecision | None:
    """Evaluate the pre-dispatch DECIDE gate. Returns None when there is no gate.

    FAIL-OPEN: a missing/None gate or ANY error returns None (= allow), so a gate
    bug can never wedge live traffic - the existing governed path still applies its
    own gates. The gate can therefore only ever WITHHOLD on a definite block verdict.
    """
    try:
        gate = deps.get(EXECUTION_GATE_DEP)
    except Exception:  # noqa: BLE001 - absent/None gate => no gating
        return None
    if gate is None:
        return None
    try:
        return gate.evaluate(capability_id=str(capability_id))
    except Exception:  # noqa: BLE001 - fail-OPEN: never block live traffic on a gate error
        return None


def record_execution_learning(
    deps: object,
    *,
    capability_id: str,
    succeeded: bool,
    verified: bool,
    source_ref: str,
) -> None:
    """Feed one live outcome into the learner. NEVER raises into the caller.

    A missing/None learner (flag OFF) is a no-op. Any error is swallowed so the
    learner can never perturb the live request or response.
    """
    try:
        learner = deps.get(LEARNER_DEP)
    except Exception:  # noqa: BLE001 - absent/None learner => learning disabled
        return
    if learner is None:
        return
    try:
        learner.learn(
            capability_id=str(capability_id),
            succeeded=bool(succeeded),
            verified=bool(verified),
            source_ref=str(source_ref),
        )
    except Exception:  # noqa: BLE001 - learning must never perturb the live path
        return


def chain_capability_key(step_names: tuple[str, ...]) -> str:
    """Derive a stable capability key for an agent chain.

    A chain has no single capability, so the key is COARSE: it is anchored on the
    chain's entry step (the first non-empty step name), or a generic key when the
    chain is empty. This groups chains by their entry step for confidence / gating -
    good enough for shadow + learn; a finer key is a future refinement.
    """
    for name in step_names:
        cleaned = (name or "").strip()
        if cleaned:
            return f"agent_chain:{cleaned}"
    return "agent_chain"


def cognitive_block_detail(verdict: str) -> dict[str, object]:
    """Shared detail body for a dispatch withheld by the Stage-B cognitive gate.

    Static strings only (the verdict is a fixed enum value, not interpolated caller
    text), so it passes the reflective-contract guard.
    """
    return {
        "error": "cognitive governance gate withheld dispatch pending review",
        "error_code": "cognitive_gate_withheld",
        "verdict": verdict,
        "governed": True,
    }


__all__ = [
    "COGNITIVE_LOOP_ENFORCE_ENV",
    "COGNITIVE_LOOP_LEARN_ENV",
    "EXECUTION_GATE_DEP",
    "LEARNER_DEP",
    "CognitiveLiveConfigReport",
    "build_execution_gate",
    "build_learner",
    "evaluate_execution_gate",
    "record_execution_learning",
    "validate_enforce_config",
    "validate_learn_config",
    "chain_capability_key",
    "cognitive_block_detail",
]
