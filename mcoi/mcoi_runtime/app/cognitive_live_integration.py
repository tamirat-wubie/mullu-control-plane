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
from pathlib import Path
from typing import Callable, Mapping

from mcoi_runtime.core.cognitive_live import (
    CognitiveExecutionGate,
    CognitiveLearner,
    GateDecision,
)
from mcoi_runtime.persistence.cognitive_outcome_ledger import (
    CognitiveOutcomeLedger,
    FileBackedCognitiveOutcomeLedger,
)

COGNITIVE_LOOP_ENFORCE_ENV = "MULLU_COGNITIVE_LOOP_ENFORCE"
COGNITIVE_LOOP_LEARN_ENV = "MULLU_COGNITIVE_LOOP_LEARN"
COGNITIVE_LOOP_GATE_ENRICHED_ENV = "MULLU_COGNITIVE_LOOP_GATE_ENRICHED"
COGNITIVE_LOOP_LEDGER_ENV = "MULLU_COGNITIVE_LOOP_LEDGER"
COGNITIVE_LOOP_LEDGER_PATH_ENV = "MULLU_COGNITIVE_LOOP_LEDGER_PATH"
COGNITIVE_LOOP_LEDGER_TENANT_DEFAULT = "system"
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


def validate_gate_enriched_config(runtime_env: Mapping[str, str]) -> CognitiveLiveConfigReport:
    """Validate the Stage-E gate enrichment flag without raising into startup."""
    return _validate(runtime_env, COGNITIVE_LOOP_GATE_ENRICHED_ENV)


def validate_ledger_config(runtime_env: Mapping[str, str]) -> CognitiveLiveConfigReport:
    """Validate the D1 ledger flag without raising into startup.

    When enabled AND the path env is set AND the Stage-C learner is built, the
    learner is wired to a FileBackedCognitiveOutcomeLedger so every LEARN event
    is durably recorded under the configured path. With the flag OFF (default),
    the learner's ledger reference stays None and the live path is byte-
    identical to today.
    """
    return _validate(runtime_env, COGNITIVE_LOOP_LEDGER_ENV)


def build_outcome_ledger(
    runtime_env: Mapping[str, str],
    *,
    tenant_id: str = COGNITIVE_LOOP_LEDGER_TENANT_DEFAULT,
) -> CognitiveOutcomeLedger | None:
    """Build a FileBackedCognitiveOutcomeLedger when D1 is enabled, else None.

    Returns None on any of:
      * the ledger flag (MULLU_COGNITIVE_LOOP_LEDGER) is missing / off /
        malformed;
      * the ledger path env (MULLU_COGNITIVE_LOOP_LEDGER_PATH) is unset or
        blank;
      * the substrate construction raises (e.g. invalid tenant_id, path-
        traversal).
    Fail-safe: a typo or missing config does NOT crash startup; the learner
    is simply built without a ledger reference (= byte-identical to pre-D1).
    """
    if not validate_ledger_config(runtime_env).enabled:
        return None
    raw_path = runtime_env.get(COGNITIVE_LOOP_LEDGER_PATH_ENV)
    if raw_path is None:
        return None
    cleaned_path = raw_path.strip()
    if not cleaned_path:
        return None
    try:
        return FileBackedCognitiveOutcomeLedger(
            base_path=Path(cleaned_path),
            tenant_id=tenant_id,
        )
    except Exception:  # noqa: BLE001 - misconfig must never crash startup
        return None


def build_execution_gate(
    runtime_env: Mapping[str, str], organs: object
) -> CognitiveExecutionGate | None:
    """Build the Stage-B DECIDE gate when enabled and organs are present, else None.

    Fail-safe: a malformed flag or missing organ returns None (the gate is optional;
    a typo must not crash startup). When None, the live path applies no gate.

    Stage-E enrichment is additive and default-off. When both the Stage-B enforce
    flag and MULLU_COGNITIVE_LOOP_GATE_ENRICHED are enabled, and episodic_memory is
    present, the gate reads prior cognitive outcomes and may escalate to a stricter
    verdict. If the enrichment flag is off/malformed or episodic_memory is absent,
    the built gate is the original unenriched gate.
    """
    if not validate_enforce_config(runtime_env).enabled:
        return None
    meta_reasoning = getattr(organs, "meta_reasoning", None)
    if meta_reasoning is None:
        return None
    enrichment_enabled = validate_gate_enriched_config(runtime_env).enabled
    episodic_memory = getattr(organs, "episodic_memory", None)
    if enrichment_enabled and episodic_memory is not None:
        return CognitiveExecutionGate(
            meta_reasoning=meta_reasoning,
            episodic_memory=episodic_memory,
            enriched=True,
        )
    return CognitiveExecutionGate(meta_reasoning=meta_reasoning)


def build_learner(
    runtime_env: Mapping[str, str],
    organs: object,
    *,
    clock: Callable[[], str],
    tenant_id: str = COGNITIVE_LOOP_LEDGER_TENANT_DEFAULT,
) -> CognitiveLearner | None:
    """Build the Stage-C learner when enabled and organs are present, else None.

    Composes the optional D1 ledger when MULLU_COGNITIVE_LOOP_LEDGER is on and
    the path env is set. When EITHER condition is missing, the learner is
    built without a ledger (= byte-identical to the pre-D1 implementation).
    The same tenant_id is carried by both the ledger and CognitiveOutcomeEvent
    bodies, so replay cannot infer partitioning from path alone.
    """
    if not validate_learn_config(runtime_env).enabled:
        return None
    meta_reasoning = getattr(organs, "meta_reasoning", None)
    episodic_memory = getattr(organs, "episodic_memory", None)
    if meta_reasoning is None or episodic_memory is None or clock is None:
        return None
    ledger = build_outcome_ledger(runtime_env, tenant_id=tenant_id)
    return CognitiveLearner(
        meta_reasoning=meta_reasoning,
        episodic_memory=episodic_memory,
        clock=clock,
        ledger=ledger,
        tenant_id=tenant_id,
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
    "COGNITIVE_LOOP_GATE_ENRICHED_ENV",
    "COGNITIVE_LOOP_LEDGER_ENV",
    "COGNITIVE_LOOP_LEDGER_PATH_ENV",
    "COGNITIVE_LOOP_LEDGER_TENANT_DEFAULT",
    "EXECUTION_GATE_DEP",
    "LEARNER_DEP",
    "CognitiveLiveConfigReport",
    "build_execution_gate",
    "build_learner",
    "build_outcome_ledger",
    "evaluate_execution_gate",
    "record_execution_learning",
    "validate_enforce_config",
    "validate_learn_config",
    "validate_gate_enriched_config",
    "validate_ledger_config",
    "chain_capability_key",
    "cognitive_block_detail",
]
