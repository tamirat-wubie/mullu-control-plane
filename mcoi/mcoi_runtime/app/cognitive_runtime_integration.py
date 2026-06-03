"""Mount the cognitive organs into the live HTTP server runtime.

Purpose: instantiate the reasoning/learning engines (world-state, meta-reasoning,
    decision-learning, episodic/working memory) in the SERVED runtime and register
    them on the shared deps container, so live request paths CAN consult them.
    Historically these were instantiated only in the CLI bootstrap (app/bootstrap.py),
    leaving the HTTP server a "brain in a jar" (see
    docs/design/COGNITIVE_LOOP_LIVE_WIRING.md, correction in section 0).
Governance scope: composition/wiring only. This helper instantiates engines,
    optionally rehydrates learned state from the D1 cognitive outcome ledger before
    serving, and registers the completed bundle. It does NOT gate decisions or
    change responses by itself.
Dependencies: in-memory engines in mcoi_runtime.core.* plus the optional D1 ledger.
Invariants:
  - Default/no-ledger path is byte-identical to the previous in-memory bootstrap.
  - Ledger rehydrate is fail-CLOSED: validate + replay must finish before deps are
    published; corrupt, contradictory, or slow ledgers raise and abort startup.
  - The ledger is source of truth; meta_reasoning and episodic_memory are derived
    indexes rebuilt from ledger events.
  - Rehydrate mutates organs only after the ledger byte-stream is validated and read
    within the hard timeout, so timeout/corruption cannot leave partial served state.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, Mapping

from mcoi_runtime.app.cognitive_live_integration import (
    COGNITIVE_LOOP_LEDGER_ENV,
    COGNITIVE_LOOP_LEDGER_PATH_ENV,
    COGNITIVE_LOOP_LEDGER_TENANT_DEFAULT,
    validate_ledger_config,
)
from mcoi_runtime.core.cognitive_loop import next_capability_confidence
from mcoi_runtime.core.decision_learning import DecisionLearningEngine
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError, stable_identifier
from mcoi_runtime.core.memory import EpisodicMemory, MemoryEntry, MemoryTier, WorkingMemory
from mcoi_runtime.core.meta_reasoning import MetaReasoningEngine
from mcoi_runtime.core.world_state import WorldStateEngine
from mcoi_runtime.persistence.cognitive_outcome_ledger import (
    CognitiveOutcomeEntry,
    CognitiveOutcomeEvent,
    CognitiveOutcomeLedger,
    FileBackedCognitiveOutcomeLedger,
)

_DEFAULT_REHYDRATE_TIMEOUT_SECONDS = 30.0
_NEUTRAL_CONFIDENCE = 0.5


@dataclass(frozen=True)
class CognitiveRuntime:
    """The bundle of cognitive organs available to the served runtime."""

    world_state: WorldStateEngine
    meta_reasoning: MetaReasoningEngine
    decision_learning: DecisionLearningEngine
    episodic_memory: EpisodicMemory
    working_memory: WorkingMemory


@dataclass(frozen=True)
class CognitiveRuntimeRehydrateReport:
    """Receipt-like summary for one D1 ledger rehydrate pass."""

    events_seen: int
    events_applied: int
    duplicate_events_skipped: int
    last_sequence: int | None


def build_rehydrate_ledger(
    runtime_env: Mapping[str, str],
    *,
    tenant_id: str = COGNITIVE_LOOP_LEDGER_TENANT_DEFAULT,
) -> CognitiveOutcomeLedger | None:
    """Build the D1 ledger for startup rehydrate.

    Unlike the Stage-C learner builder, this is strict once the ledger flag is
    explicitly set. Disabled remains None (byte-identical startup). Malformed flag
    or enabled-without-path raises so startup fails before deps are published.
    """
    report = validate_ledger_config(runtime_env)
    if report.error is not None:
        raise RuntimeCoreInvariantError("unsupported cognitive ledger flag value")
    if not report.enabled:
        return None
    raw_path = runtime_env.get(COGNITIVE_LOOP_LEDGER_PATH_ENV)
    if raw_path is None or not raw_path.strip():
        raise RuntimeCoreInvariantError(
            f"{COGNITIVE_LOOP_LEDGER_ENV}=1 requires {COGNITIVE_LOOP_LEDGER_PATH_ENV}"
        )
    return FileBackedCognitiveOutcomeLedger(
        base_path=Path(raw_path.strip()),
        tenant_id=tenant_id,
    )


def bootstrap_cognitive_runtime(
    *,
    clock: Callable[[], str],
    ledger: CognitiveOutcomeLedger | None = None,
    rehydrate_timeout_seconds: float = _DEFAULT_REHYDRATE_TIMEOUT_SECONDS,
) -> CognitiveRuntime:
    """Instantiate the cognitive organs for the served runtime.

    With no ledger, this is the original pure/in-memory construction. With a D1
    ledger, validate + replay run before the runtime is returned, so callers cannot
    publish partially rehydrated organs.
    """
    if clock is None:
        raise ValueError("bootstrap_cognitive_runtime requires a clock")
    runtime = CognitiveRuntime(
        world_state=WorldStateEngine(),
        meta_reasoning=MetaReasoningEngine(clock=clock),
        decision_learning=DecisionLearningEngine(clock=clock),
        episodic_memory=EpisodicMemory(),
        working_memory=WorkingMemory(),
    )
    if ledger is not None:
        rehydrate_cognitive_runtime_from_ledger(
            runtime,
            ledger,
            timeout_seconds=rehydrate_timeout_seconds,
        )
    return runtime


def _read_ledger_entries_with_timeout(
    ledger: CognitiveOutcomeLedger,
    *,
    timeout_seconds: float,
) -> tuple[tuple[CognitiveOutcomeEntry, ...], int | None]:
    if timeout_seconds <= 0:
        raise RuntimeCoreInvariantError("rehydrate timeout must be positive")

    def read_all() -> tuple[tuple[CognitiveOutcomeEntry, ...], int | None]:
        ledger.validate()
        return tuple(ledger.replay()), ledger.latest_sequence()

    executor = ThreadPoolExecutor(max_workers=1)
    future = executor.submit(read_all)
    try:
        return future.result(timeout=float(timeout_seconds))
    except FutureTimeoutError as exc:
        future.cancel()
        raise RuntimeCoreInvariantError("cognitive ledger rehydrate timed out") from exc
    finally:
        executor.shutdown(wait=False, cancel_futures=True)


def rehydrate_cognitive_runtime_from_ledger(
    cognitive_runtime: CognitiveRuntime,
    ledger: CognitiveOutcomeLedger,
    *,
    timeout_seconds: float = _DEFAULT_REHYDRATE_TIMEOUT_SECONDS,
) -> CognitiveRuntimeRehydrateReport:
    """Validate and replay a D1 ledger into a runtime before serving.

    The ledger byte-stream is validated and materialized under the hard timeout
    before any organ mutation occurs. If validation, replay, or timeout fails, the
    caller gets an exception and should abort startup before deps are published.
    """
    if cognitive_runtime is None:
        raise RuntimeCoreInvariantError("cognitive_runtime is required")
    if ledger is None:
        raise RuntimeCoreInvariantError("ledger is required")
    entries, last_sequence = _read_ledger_entries_with_timeout(
        ledger,
        timeout_seconds=timeout_seconds,
    )
    return _apply_rehydrated_entries(
        cognitive_runtime,
        entries,
        last_sequence=last_sequence,
    )


def _apply_rehydrated_entries(
    cognitive_runtime: CognitiveRuntime,
    entries: Iterable[CognitiveOutcomeEntry],
    *,
    last_sequence: int | None,
) -> CognitiveRuntimeRehydrateReport:
    seen: dict[tuple[str, str, str], tuple[object, ...]] = {}
    applied = 0
    skipped = 0
    materialized = tuple(entries)
    for entry in materialized:
        event = entry.event
        if not isinstance(event, CognitiveOutcomeEvent):
            raise RuntimeCoreInvariantError("rehydrate entry must carry CognitiveOutcomeEvent")
        key = (event.tenant_id, event.capability_id, event.source_ref)
        signature = _event_signature(event)
        previous = seen.get(key)
        if previous is not None:
            if previous != signature:
                raise RuntimeCoreInvariantError("conflicting duplicate cognitive outcome event")
            skipped += 1
            continue
        seen[key] = signature
        _apply_event(cognitive_runtime, event)
        applied += 1
    return CognitiveRuntimeRehydrateReport(
        events_seen=len(materialized),
        events_applied=applied,
        duplicate_events_skipped=skipped,
        last_sequence=last_sequence,
    )


def _event_signature(event: CognitiveOutcomeEvent) -> tuple[object, ...]:
    return (
        event.succeeded,
        event.verified,
        event.admitted_entry_id,
        event.learned_at,
        round(float(event.prior_confidence), 4),
        round(float(event.next_confidence), 4),
    )


def _apply_event(cognitive_runtime: CognitiveRuntime, event: CognitiveOutcomeEvent) -> None:
    meta = cognitive_runtime.meta_reasoning
    existing = meta.get_confidence(event.capability_id)
    prior_value = _NEUTRAL_CONFIDENCE if existing is None else float(existing.overall_confidence)
    if round(prior_value, 4) != round(float(event.prior_confidence), 4):
        raise RuntimeCoreInvariantError("cognitive ledger prior_confidence mismatch")
    next_confidence = next_capability_confidence(
        existing,
        capability_id=event.capability_id,
        succeeded=event.succeeded,
        verified=event.verified,
        assessed_at=event.learned_at,
    )
    if round(float(next_confidence.overall_confidence), 4) != round(float(event.next_confidence), 4):
        raise RuntimeCoreInvariantError("cognitive ledger next_confidence mismatch")
    _validate_admitted_entry_contract(event)
    meta.update_confidence(next_confidence)
    _admit_replayed_outcome(cognitive_runtime.episodic_memory, event)


def _validate_admitted_entry_contract(event: CognitiveOutcomeEvent) -> None:
    if event.succeeded and event.verified:
        expected = stable_identifier(
            "cognitive-live-outcome",
            {"capability_id": event.capability_id, "source_ref": event.source_ref},
        )
        if event.admitted_entry_id != expected:
            raise RuntimeCoreInvariantError("cognitive ledger admitted_entry_id mismatch")
        return
    if event.admitted_entry_id is not None:
        raise RuntimeCoreInvariantError("non-admitted cognitive outcome carried admitted_entry_id")


def _admit_replayed_outcome(episodic_memory: EpisodicMemory, event: CognitiveOutcomeEvent) -> None:
    if not (event.succeeded and event.verified):
        return
    assert event.admitted_entry_id is not None
    entry = MemoryEntry(
        entry_id=event.admitted_entry_id,
        tier=MemoryTier.EPISODIC,
        category="cognitive_loop_outcome",
        content={
            "capability_id": event.capability_id,
            "route": event.capability_id,
            "succeeded": event.succeeded,
            "verified": event.verified,
            "source_ref": event.source_ref,
        },
        source_ids=(event.source_ref,),
    )
    existing = episodic_memory.get(event.admitted_entry_id)
    if existing is None:
        episodic_memory.admit(entry)
        return
    if existing.content != entry.content or existing.source_ids != entry.source_ids:
        raise RuntimeCoreInvariantError("existing episodic outcome conflicts with ledger replay")


def register_cognitive_runtime(deps: object, cognitive_runtime: CognitiveRuntime) -> None:
    """Register each organ (and the bundle) on the shared deps container."""
    deps.set("cognitive_runtime", cognitive_runtime)
    deps.set("world_state", cognitive_runtime.world_state)
    deps.set("meta_reasoning", cognitive_runtime.meta_reasoning)
    deps.set("decision_learning", cognitive_runtime.decision_learning)
    deps.set("episodic_memory", cognitive_runtime.episodic_memory)
    deps.set("working_memory", cognitive_runtime.working_memory)


__all__ = [
    "CognitiveRuntime",
    "CognitiveRuntimeRehydrateReport",
    "bootstrap_cognitive_runtime",
    "build_rehydrate_ledger",
    "rehydrate_cognitive_runtime_from_ledger",
    "register_cognitive_runtime",
]
