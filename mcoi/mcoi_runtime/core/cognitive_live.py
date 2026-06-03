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
from mcoi_runtime.persistence.cognitive_outcome_ledger import (
    CognitiveOutcomeEvent,
    CognitiveOutcomeLedger,
)
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
    replay) requires a durable, replayable event ledger; D1 is shipped as the
    optional ``ledger`` parameter below. When ``ledger`` is None (the historical
    default), the learner behaves byte-identically to the pre-D1 implementation.
    When a ledger is injected and the env-flag composition turns it on, each
    ``learn`` call appends one ``CognitiveOutcomeEvent`` to the durable substrate
    as the FINAL step inside the existing ``_lock``-serialised admission path.

    Durability contract: best-effort across worker crashes. The ledger write
    runs AFTER the in-memory cache mutations (``update_confidence`` then
    ``admit``), so a crash between admit success and ledger append loses the
    single in-flight event. The cache itself stays internally consistent.
    Stronger durability (ledger-first WAL) is a future refinement that needs
    the rehydrate path (#1276 / N+2) to handle idempotent re-application via
    ``source_ref`` and the explicit ``next_confidence`` recorded in the event.
    """

    def __init__(
        self,
        *,
        meta_reasoning: object,
        episodic_memory: object,
        clock: Callable[[], str],
        ledger: CognitiveOutcomeLedger | None = None,
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
        self._ledger = ledger

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
            # Read the prior confidence BEFORE mutation so the ledger event
            # records the actual (prior, next) transition. The read is a pure
            # query against the same accessor the gate uses.
            prior_value = self._read_capability_confidence(capability_id)
            self._update_confidence(capability_id, succeeded=succeeded, verified=verified, assessed_at=learned_at)
            admitted_id = self._admit_outcome(capability_id, succeeded=succeeded, verified=verified, source_ref=source_ref)
            # Ledger write LAST. When None (D1 disabled), the live path is
            # byte-identical to the pre-D1 implementation. When present, this
            # is the durable substrate the rehydrate path consumes; a write
            # failure surfaces to the caller (the existing
            # ``record_execution_learning`` wrapper still swallows exceptions
            # so the live request is never perturbed), and the cache is left
            # in its updated state -- a single in-flight event may be lost
            # across a worker crash but the cache itself stays consistent.
            if self._ledger is not None:
                next_value = self._read_capability_confidence(capability_id)
                event = CognitiveOutcomeEvent(
                    capability_id=capability_id,
                    succeeded=succeeded,
                    verified=verified,
                    admitted_entry_id=admitted_id,
                    source_ref=source_ref,
                    learned_at=learned_at,
                    prior_confidence=round(prior_value, 4),
                    next_confidence=round(next_value, 4),
                )
                self._ledger.append(event)
        return LearnRecord(
            capability_id=capability_id,
            succeeded=succeeded,
            verified=verified,
            admitted_entry_id=admitted_id,
            learned_at=learned_at,
        )

    def _read_capability_confidence(self, capability_id: str) -> float:
        """Read overall_confidence for ``capability_id`` via the meta organ.

        Returns ``_LIVE_NEUTRAL_CONFIDENCE`` when the organ has no record (a
        previously-unseen capability) or the get_confidence accessor is
        absent. Mirrors ``CognitiveExecutionGate._capability_confidence`` so
        the gate's read and the learner's pre/post-mutation snapshots are
        derived from the same source -- the ledger event's confidence values
        will agree with what the gate sees on the next read.
        """
        get_confidence = getattr(self._meta, "get_confidence", None)
        if get_confidence is None:
            return _LIVE_NEUTRAL_CONFIDENCE
        existing = get_confidence(capability_id)
        if existing is None:
            return _LIVE_NEUTRAL_CONFIDENCE
        return float(existing.overall_confidence)

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


__all__ = [
    "CognitiveExecutionGate",
    "CognitiveLearner",
    "GateDecision",
    "LearnRecord",
]
