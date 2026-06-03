"""Purpose: the LIVE-acting cognitive components that go beyond the record-only
    shadow (core/cognitive_shadow.py): a pre-dispatch DECIDE gate that may WITHHOLD
    a live dispatch (Stage B) and a post-outcome learner that feeds the organs from
    real outcomes (Stage C). Both reuse the SAME shared decision/confidence logic as
    the CognitiveLoop, but operate around the live HTTP execution seam instead of
    the CLI operator loop. Both are wired default-OFF (see cognitive_live_integration).
Governance scope: cognitive control + learning only. The gate NEVER acts more than
    today (it can only REFUSE a dispatch whose DECIDE verdict is a blocking one); the
    learner only updates meta-reasoning confidence (deterministic running rate) and
    appends episodic outcomes through a rollback-safe admission rule. Neither
    reimplements or mutates the governed dispatch.
Dependencies:
  - mcoi_runtime.core.cognitive_loop: decide_verdict, next_capability_confidence,
    DecisionVerdict, HardConstraint (shared logic = single source of truth).
  - mcoi_runtime.core.memory: MemoryEntry / MemoryTier (episodic admission).
  - mcoi_runtime.core.invariants: stable ids + text validation.
Invariants:
  - Gate is read-only and safety-positive: only BLOCK_UNKNOWN_CONSTRAINT /
    DEFER_TO_REVIEW set blocked=True; every other verdict is allowed (parity with
    today => enabling the gate can only refuse, never act where it would not have).
  - Learner is deterministic for a given (prior state, outcome, clock) and
    rollback-safe: an episodic outcome is admitted ONLY on a verified success, keyed
    on the caller's unique source_ref (no duplicate-id admission). A lock serialises
    in-process writes.
  - Neither component dispatches or mutates governed semantics.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass

from mcoi_runtime.core.cognitive_loop import (
    DecisionVerdict,
    HardConstraint,
    decide_verdict,
    next_capability_confidence,
)
from mcoi_runtime.core.invariants import (
    RuntimeCoreInvariantError,
    ensure_non_empty_text,
    stable_identifier,
)
from mcoi_runtime.core.memory import MemoryEntry, MemoryTier
from typing import Callable

# Mirror CognitiveLoop's DECIDE-phase defaults (kept in sync intentionally).
_LIVE_REPLAN_THRESHOLD = 0.3
_LIVE_CAUTION_THRESHOLD = 0.5
_LIVE_NEUTRAL_CONFIDENCE = 0.5

# Verdicts under which the DECIDE gate would NOT dispatch.
_BLOCKING_VERDICTS = frozenset(
    {DecisionVerdict.BLOCK_UNKNOWN_CONSTRAINT, DecisionVerdict.DEFER_TO_REVIEW}
)


@dataclass(frozen=True, slots=True)
class GateDecision:
    """A pre-dispatch DECIDE decision for a live execution.

    ``blocked`` is True only for a blocking verdict. The verdict is an enum and no
    field carries interpolated free text, so the record is auditable and passes
    the reflective-contract guard.
    """

    capability_id: str
    decision_verdict: DecisionVerdict
    blocked: bool
    confidence: float
    degraded: bool

    def __post_init__(self) -> None:
        object.__setattr__(self, "capability_id", ensure_non_empty_text("capability_id", self.capability_id))
        if not isinstance(self.decision_verdict, DecisionVerdict):
            raise RuntimeCoreInvariantError("decision_verdict must be a DecisionVerdict")
        if not isinstance(self.blocked, bool):
            raise RuntimeCoreInvariantError("blocked must be a bool")
        if not isinstance(self.degraded, bool):
            raise RuntimeCoreInvariantError("degraded must be a bool")
        if not (0.0 <= float(self.confidence) <= 1.0):
            raise RuntimeCoreInvariantError("confidence must be in [0.0, 1.0]")


class CognitiveExecutionGate:
    """Stage B: a pre-dispatch DECIDE gate that may WITHHOLD a live dispatch.

    Read-only over the organs. Safety-positive: ``evaluate`` returns a GateDecision
    and only a blocking verdict sets ``blocked=True``; every non-block verdict is
    allowed, so enabling the gate can never cause the system to act where it would
    not have - it can only refuse.
    """

    def __init__(
        self,
        *,
        meta_reasoning: object,
        replan_threshold: float = _LIVE_REPLAN_THRESHOLD,
        caution_threshold: float = _LIVE_CAUTION_THRESHOLD,
    ) -> None:
        if meta_reasoning is None:
            raise RuntimeCoreInvariantError("execution gate requires a meta_reasoning engine")
        if not (0.0 <= replan_threshold <= caution_threshold <= 1.0):
            raise RuntimeCoreInvariantError(
                "thresholds must satisfy 0.0 <= replan_threshold <= caution_threshold <= 1.0"
            )
        self._meta = meta_reasoning
        self._replan_threshold = float(replan_threshold)
        self._caution_threshold = float(caution_threshold)

    def evaluate(
        self,
        *,
        capability_id: str,
        hard_constraints: tuple[HardConstraint, ...] = (),
    ) -> GateDecision:
        capability_id = ensure_non_empty_text("capability_id", capability_id)
        confidence = round(self._capability_confidence(capability_id), 4)
        degraded = self._is_degraded(capability_id)
        verdict, _reason = decide_verdict(
            confidence=confidence,
            degraded=degraded,
            hard_constraints=hard_constraints,
            replan_threshold=self._replan_threshold,
            caution_threshold=self._caution_threshold,
        )
        return GateDecision(
            capability_id=capability_id,
            decision_verdict=verdict,
            blocked=verdict in _BLOCKING_VERDICTS,
            confidence=confidence,
            degraded=bool(degraded),
        )

    def _capability_confidence(self, capability_id: str) -> float:
        get_confidence = getattr(self._meta, "get_confidence", None)
        if get_confidence is None:
            return _LIVE_NEUTRAL_CONFIDENCE
        existing = get_confidence(capability_id)
        if existing is None:
            return _LIVE_NEUTRAL_CONFIDENCE
        return float(existing.overall_confidence)

    def _is_degraded(self, capability_id: str) -> bool:
        is_degraded = getattr(self._meta, "is_degraded", None)
        if is_degraded is None:
            return False
        return bool(is_degraded(capability_id))


@dataclass(frozen=True, slots=True)
class LearnRecord:
    """Record of one live LEARN write-back."""

    capability_id: str
    succeeded: bool
    verified: bool
    admitted_entry_id: str | None
    learned_at: str


class CognitiveLearner:
    """Stage C: feed live outcomes back into the organs, deterministically.

    Updates meta-reasoning confidence via the shared ``next_capability_confidence``
    running rate, and appends an episodic outcome ONLY on a verified success
    (rollback-safe), keyed on the caller's unique ``source_ref`` so admission never
    collides. A lock serialises in-process writes so concurrent requests do not
    interleave a confidence read/update. The episodic content matches what the
    shadow observer reads (capability_id / route), so the loop closes.

    Determinism note: deterministic for a given ordered outcome sequence + clock.
    Strict cross-run / multi-worker determinism (the design doc's D1 record-and-
    replay) requires a durable, replayable event ledger; until that backend lands,
    this is wired default-OFF and behaves as a single-process running cache.
    """

    def __init__(
        self,
        *,
        meta_reasoning: object,
        episodic_memory: object,
        clock: Callable[[], str],
    ) -> None:
        if meta_reasoning is None:
            raise RuntimeCoreInvariantError("learner requires a meta_reasoning engine")
        if episodic_memory is None:
            raise RuntimeCoreInvariantError("learner requires an episodic_memory engine")
        if clock is None:
            raise RuntimeCoreInvariantError("learner requires an injected clock")
        self._meta = meta_reasoning
        self._episodic = episodic_memory
        self._clock = clock
        self._lock = threading.Lock()

    def learn(
        self,
        *,
        capability_id: str,
        succeeded: bool,
        verified: bool,
        source_ref: str,
    ) -> LearnRecord:
        capability_id = ensure_non_empty_text("capability_id", capability_id)
        source_ref = ensure_non_empty_text("source_ref", source_ref)
        succeeded = bool(succeeded)
        verified = bool(verified)
        with self._lock:
            learned_at = self._clock()
            self._update_confidence(capability_id, succeeded=succeeded, verified=verified, assessed_at=learned_at)
            admitted_id = self._admit_outcome(capability_id, succeeded=succeeded, verified=verified, source_ref=source_ref)
        return LearnRecord(
            capability_id=capability_id,
            succeeded=succeeded,
            verified=verified,
            admitted_entry_id=admitted_id,
            learned_at=learned_at,
        )

    def _update_confidence(self, capability_id: str, *, succeeded: bool, verified: bool, assessed_at: str) -> None:
        update = getattr(self._meta, "update_confidence", None)
        get_confidence = getattr(self._meta, "get_confidence", None)
        if update is None or get_confidence is None:
            return
        existing = get_confidence(capability_id)
        update(
            next_capability_confidence(
                existing,
                capability_id=capability_id,
                succeeded=succeeded,
                verified=verified,
                assessed_at=assessed_at,
            )
        )

    def _admit_outcome(self, capability_id: str, *, succeeded: bool, verified: bool, source_ref: str) -> str | None:
        # Rollback-safe: ONLY a verified success is admitted to episodic memory.
        if not (succeeded and verified):
            return None
        admit = getattr(self._episodic, "admit", None)
        if admit is None:
            return None
        entry = MemoryEntry(
            entry_id=stable_identifier(
                "cognitive-live-outcome",
                {"capability_id": capability_id, "source_ref": source_ref},
            ),
            tier=MemoryTier.EPISODIC,
            category="cognitive_loop_outcome",
            content={
                "capability_id": capability_id,
                "route": capability_id,
                "succeeded": succeeded,
                "verified": verified,
                "source_ref": source_ref,
            },
            source_ids=(source_ref,),
        )
        admitted = admit(entry)
        return getattr(admitted, "entry_id", None)


@dataclass(frozen=True, slots=True)
class CognitivePlanContext:
    """A read-only snapshot of the organs' state for one capability.

    Composed from the SAME organ public APIs the gate and learner already use,
    so the read surface cannot diverge from the write surface. Every field is a
    plain scalar or a deterministically-ordered tuple so the snapshot is
    hashable / loggable / replayable. Each per-organ read in the builder below
    is independently try/except'd, so a missing or raising organ degrades to a
    safe default (zero / empty / None) and never blocks the snapshot.
    """

    capability_id: str
    confidence: float
    degraded: bool
    prior_outcomes_count: int
    prior_success_count: int
    learned_factor_adjustments: tuple[tuple[str, float], ...]
    learned_adjustment_count: int
    world_entity_count: int
    world_snapshot_hash: str | None

    def __post_init__(self) -> None:
        object.__setattr__(self, "capability_id", ensure_non_empty_text("capability_id", self.capability_id))
        if not (0.0 <= float(self.confidence) <= 1.0):
            raise RuntimeCoreInvariantError("confidence must be in [0.0, 1.0]")
        if not isinstance(self.degraded, bool):
            raise RuntimeCoreInvariantError("degraded must be a bool")
        for field_name in (
            "prior_outcomes_count",
            "prior_success_count",
            "learned_adjustment_count",
            "world_entity_count",
        ):
            value = getattr(self, field_name)
            if not isinstance(value, int) or value < 0:
                raise RuntimeCoreInvariantError("counts must be non-negative ints")
        if self.prior_success_count > self.prior_outcomes_count:
            raise RuntimeCoreInvariantError("prior_success_count cannot exceed prior_outcomes_count")
        if not isinstance(self.learned_factor_adjustments, tuple):
            raise RuntimeCoreInvariantError("learned_factor_adjustments must be a tuple")
        for pair in self.learned_factor_adjustments:
            if (
                not isinstance(pair, tuple)
                or len(pair) != 2
                or not isinstance(pair[0], str)
                or not isinstance(pair[1], (int, float))
            ):
                raise RuntimeCoreInvariantError("each learned_factor entry must be (str, float)")
        if self.world_snapshot_hash is not None and not isinstance(self.world_snapshot_hash, str):
            raise RuntimeCoreInvariantError("world_snapshot_hash must be str or None")


def _read_confidence(meta_reasoning: object | None, capability_id: str) -> tuple[float, bool]:
    """Read confidence + degraded from meta_reasoning, fail-OPEN to neutral."""
    if meta_reasoning is None:
        return _LIVE_NEUTRAL_CONFIDENCE, False
    confidence = _LIVE_NEUTRAL_CONFIDENCE
    try:
        get_confidence = getattr(meta_reasoning, "get_confidence", None)
        if get_confidence is not None:
            existing = get_confidence(capability_id)
            if existing is not None:
                confidence = float(existing.overall_confidence)
                if not (0.0 <= confidence <= 1.0):
                    confidence = _LIVE_NEUTRAL_CONFIDENCE
    except Exception:  # noqa: BLE001 - organ read must never raise into the snapshot
        confidence = _LIVE_NEUTRAL_CONFIDENCE
    degraded = False
    try:
        is_degraded = getattr(meta_reasoning, "is_degraded", None)
        if is_degraded is not None:
            degraded = bool(is_degraded(capability_id))
    except Exception:  # noqa: BLE001 - organ read must never raise into the snapshot
        degraded = False
    return confidence, degraded


def _read_episodic_priors(episodic_memory: object | None, capability_id: str) -> tuple[int, int]:
    """Count prior cognitive_loop_outcome episodic entries for capability_id.

    Returns (total_count, success_count). Each iteration is wrapped so a
    malformed entry or a missing attribute degrades to skip-this-entry rather
    than blowing up the whole read.
    """
    if episodic_memory is None:
        return 0, 0
    try:
        list_entries = getattr(episodic_memory, "list_entries", None)
        if list_entries is None:
            return 0, 0
        entries = list_entries(category="cognitive_loop_outcome")
    except Exception:  # noqa: BLE001 - organ read must never raise into the snapshot
        return 0, 0
    total = 0
    successes = 0
    for entry in entries:
        try:
            content = getattr(entry, "content", None) or {}
            if str(content.get("capability_id", "")) != capability_id:
                continue
            total += 1
            if bool(content.get("succeeded", False)):
                successes += 1
        except Exception:  # noqa: BLE001 - skip malformed entries
            continue
    return total, successes


def _read_learned_factors(
    decision_learning: object | None,
) -> tuple[tuple[tuple[str, float], ...], int]:
    """Read learned factor adjustments + total adjustment count, sorted by key."""
    if decision_learning is None:
        return (), 0
    adjustments: tuple[tuple[str, float], ...] = ()
    try:
        get_factors = getattr(decision_learning, "get_learned_factor_adjustments", None)
        if get_factors is not None:
            factors = get_factors()
            adjustments = tuple(
                sorted(
                    ((str(key), float(value)) for key, value in dict(factors).items()),
                    key=lambda pair: pair[0],
                )
            )
    except Exception:  # noqa: BLE001 - organ read must never raise into the snapshot
        adjustments = ()
    count = 0
    try:
        adjustment_count = getattr(decision_learning, "adjustment_count", None)
        if adjustment_count is not None:
            count = int(adjustment_count)
            if count < 0:
                count = 0
    except Exception:  # noqa: BLE001 - organ read must never raise into the snapshot
        count = 0
    return adjustments, count


def _read_world_summary(world_state: object | None) -> tuple[int, str | None]:
    """Read entity count + snapshot hash from world_state."""
    if world_state is None:
        return 0, None
    entity_count = 0
    try:
        list_entities = getattr(world_state, "list_entities", None)
        if list_entities is not None:
            entity_count = len(list_entities())
            if entity_count < 0:
                entity_count = 0
    except Exception:  # noqa: BLE001 - organ read must never raise into the snapshot
        entity_count = 0
    snapshot_hash: str | None = None
    try:
        snapshot_hash_fn = getattr(world_state, "snapshot_hash", None)
        if snapshot_hash_fn is not None:
            raw = snapshot_hash_fn()
            snapshot_hash = str(raw) if raw is not None else None
    except Exception:  # noqa: BLE001 - organ read must never raise into the snapshot
        snapshot_hash = None
    return entity_count, snapshot_hash


def build_plan_context(
    *,
    capability_id: str,
    meta_reasoning: object | None,
    episodic_memory: object | None,
    decision_learning: object | None,
    world_state: object | None,
) -> CognitivePlanContext:
    """Build a CognitivePlanContext snapshot from the organs (Stage D read-back).

    Pure read. Each organ read is independently fail-OPEN: a missing or raising
    organ degrades to a safe default (neutral confidence, zero counts, empty
    adjustments, no snapshot hash) so the snapshot is always returned. The
    snapshot deliberately does NOT consult the gate's verdict - it is the
    organ state, NOT a decision.
    """
    capability_id = ensure_non_empty_text("capability_id", capability_id)
    confidence, degraded = _read_confidence(meta_reasoning, capability_id)
    prior_total, prior_success = _read_episodic_priors(episodic_memory, capability_id)
    learned, learned_count = _read_learned_factors(decision_learning)
    world_entities, world_hash = _read_world_summary(world_state)
    return CognitivePlanContext(
        capability_id=capability_id,
        confidence=round(confidence, 4),
        degraded=bool(degraded),
        prior_outcomes_count=prior_total,
        prior_success_count=prior_success,
        learned_factor_adjustments=learned,
        learned_adjustment_count=learned_count,
        world_entity_count=world_entities,
        world_snapshot_hash=world_hash,
    )


__all__ = [
    "CognitiveExecutionGate",
    "CognitiveLearner",
    "CognitivePlanContext",
    "GateDecision",
    "LearnRecord",
    "build_plan_context",
]
