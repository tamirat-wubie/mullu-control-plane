"""IntentResolver — predicate-driven obligation closure.

Bridges:
  - StateView                (caller-supplied — wraps whichever engine
                              holds mutable entity state)
  - ObligationRuntimeEngine  (declared / closed work items)
  - EventSpineEngine         (audit trail — what happened, when)

The resolver does not own state; it observes events from the spine and
queries state via StateView, deciding when to close obligations.

Mechanism:

  Differential dispatch — inverted index `EventType -> {obligation_id}`
    only re-evaluates intents whose predicates watch the event's type.

  Per-intent debounce — bursts of events within `debounce_window_s`
    coalesce into a single re-evaluation per intent.

  Two-confirmation fulfillment — when all success predicates first
    pass, we record an EntityVector (per-entity attribute hash) and
    schedule a confirm at `now + confirm_window_s`. The confirm runs
    via tick(); at that point we re-fetch every referenced entity's
    state and re-hash. Reject if ANY hash advanced. Only when both
    reads agree does the obligation close to COMPLETED.

  Single-shot precondition failure — closes the obligation to
    CANCELLED with reason='precondition_failed'.

The resolver does NOT re-emit world events. Event flow:
  1. App mutates entity state in its engine
  2. App emits a WORLD_STATE_CHANGED event into the spine
  3. App calls resolver.on_event(event) (or use emit_and_dispatch)
  4. Resolver re-evaluates affected intents, may close some

For idle systems, pair with BackgroundTicker so pending fulfillments
ripen on time even with no event traffic.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Callable, Mapping, Sequence

from mcoi_runtime.contracts.event import EventRecord, EventType
from mcoi_runtime.contracts.obligation import (
    ObligationClosure,
    ObligationRecord,
    ObligationState,
)
from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.obligation_runtime import ObligationRuntimeEngine

from .primitives import (
    EntityId,
    IntentPredicate,
    StateView,
    gather_vector,
)


@dataclass
class _IntentSpec:
    obligation_id: str
    preconditions: tuple[IntentPredicate, ...]
    success: tuple[IntentPredicate, ...]
    last_vector: dict[EntityId, str] = field(default_factory=dict)

    @property
    def referenced_entities(self) -> set[EntityId]:
        return {p.entity_id for p in self.preconditions + self.success}


@dataclass
class _PendingConfirm:
    obligation_id: str
    candidate_vector: dict[EntityId, str]
    confirm_at_monotonic: float


class IntentResolver:
    DEFAULT_CONFIRM_WINDOW_S = 0.25
    DEFAULT_DEBOUNCE_WINDOW_S = 0.05

    def __init__(
        self,
        *,
        state_view: StateView,
        obligations: ObligationRuntimeEngine,
        spine: EventSpineEngine,
        confirm_window_s: float = DEFAULT_CONFIRM_WINDOW_S,
        debounce_window_s: float = DEFAULT_DEBOUNCE_WINDOW_S,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._state_view = state_view
        self._obligations = obligations
        self._spine = spine
        self._intents: dict[str, _IntentSpec] = {}
        self._index: dict[EventType, set[str]] = defaultdict(set)
        self._pending: dict[str, _PendingConfirm] = {}
        self._last_eval_at: dict[str, float] = {}
        self._confirm_window_s = confirm_window_s
        self._debounce_window_s = debounce_window_s
        self._clock = clock
        self._lock = threading.RLock()
        self._closure_observers: list[Callable[[ObligationClosure], None]] = []

    # --- Registration ---

    def register_intent(
        self,
        obligation_id: str,
        *,
        preconditions: Sequence[IntentPredicate],
        success: Sequence[IntentPredicate],
    ) -> None:
        """Register a previously-created obligation as an intent.

        The obligation must already exist in the obligation engine. The
        substrate uses obligation_id as the intent identity — there is
        no parallel intent record.
        """
        if self._obligations.get_obligation(obligation_id) is None:
            raise LookupError(f"obligation {obligation_id!r} not found")
        spec = _IntentSpec(
            obligation_id=obligation_id,
            preconditions=tuple(preconditions),
            success=tuple(success),
        )
        with self._lock:
            self._intents[obligation_id] = spec
            for predicate in spec.preconditions + spec.success:
                for evt_type in predicate.watches():
                    self._index[evt_type].add(obligation_id)

    def deregister_intent(self, obligation_id: str) -> None:
        with self._lock:
            self._intents.pop(obligation_id, None)
            self._pending.pop(obligation_id, None)
            for ids in self._index.values():
                ids.discard(obligation_id)

    def add_closure_observer(
        self, callback: Callable[[ObligationClosure], None]
    ) -> None:
        with self._lock:
            self._closure_observers.append(callback)

    # --- Event dispatch ---

    def on_event(self, event: EventRecord) -> list[ObligationClosure]:
        """Drive replay for a single event. Tick first so any ripe
        candidate confirms run against their original baseline before
        the new event has a chance to overwrite it.
        """
        emitted: list[ObligationClosure] = list(self.tick())
        with self._lock:
            affected = set(self._index.get(event.event_type, set()))
        now = self._clock()
        for oid in affected:
            with self._lock:
                last = self._last_eval_at.get(oid, -float("inf"))
                if now - last < self._debounce_window_s:
                    continue
                self._last_eval_at[oid] = now
            emitted.extend(self._evaluate_one(oid))
        emitted.extend(self.tick())
        for cl in emitted:
            self._notify(cl)
        return emitted

    def emit_and_dispatch(self, event: EventRecord) -> list[ObligationClosure]:
        """Emit the event into the spine and dispatch to indexed intents.

        Convenience for callers that want spine + resolver in sync
        without remembering two calls.
        """
        self._spine.emit(event)
        return self.on_event(event)

    def evaluate(self, obligation_id: str) -> list[ObligationClosure]:
        """Re-evaluate a single intent on demand (no event)."""
        emitted: list[ObligationClosure] = list(self.tick())
        emitted.extend(self._evaluate_one(obligation_id))
        emitted.extend(self.tick())
        for cl in emitted:
            self._notify(cl)
        return emitted

    def tick(self) -> list[ObligationClosure]:
        """Process pending two-confirm candidates whose window has ripened."""
        emitted: list[ObligationClosure] = []
        now = self._clock()
        with self._lock:
            ripe = [
                p for p in self._pending.values() if p.confirm_at_monotonic <= now
            ]
            for p in ripe:
                self._pending.pop(p.obligation_id, None)
        for p in ripe:
            spec = self._intents.get(p.obligation_id)
            if spec is None:
                continue
            obligation = self._obligations.get_obligation(p.obligation_id)
            if obligation is None or obligation.state in _TERMINAL_STATES:
                continue
            current_vector = gather_vector(spec.referenced_entities, self._state_view)
            if self._versions_advanced(p.candidate_vector, current_vector):
                spec.last_vector = current_vector
                continue
            verdict = self._verdict(spec)
            if verdict is _Verdict.SUCCESS:
                closure = self._close(
                    obligation,
                    final_state=ObligationState.COMPLETED,
                    reason="intent_substrate: success predicates confirmed",
                )
                emitted.append(closure)
                self.deregister_intent(p.obligation_id)
            elif verdict is _Verdict.BROKEN:
                closure = self._close(
                    obligation,
                    final_state=ObligationState.CANCELLED,
                    reason="intent_substrate: precondition failed at confirm",
                )
                emitted.append(closure)
                self.deregister_intent(p.obligation_id)
            else:
                spec.last_vector = current_vector
        return emitted

    def pending_count(self) -> int:
        with self._lock:
            return len(self._pending)

    def is_registered(self, obligation_id: str) -> bool:
        with self._lock:
            return obligation_id in self._intents

    # --- Internal ---

    def _evaluate_one(self, obligation_id: str) -> list[ObligationClosure]:
        spec = self._intents.get(obligation_id)
        if spec is None:
            return []
        obligation = self._obligations.get_obligation(obligation_id)
        if obligation is None or obligation.state in _TERMINAL_STATES:
            self.deregister_intent(obligation_id)
            return []
        # If a candidate is already pending, leave it alone — tick owns
        # the path out of pending. (Re-evaluating mid-window would
        # overwrite the candidate vector and silently extend the wait,
        # breaking the two-confirm guarantee.)
        with self._lock:
            if obligation_id in self._pending:
                return []
        verdict = self._verdict(spec)
        emitted: list[ObligationClosure] = []
        if verdict is _Verdict.BROKEN:
            closure = self._close(
                obligation,
                final_state=ObligationState.CANCELLED,
                reason="intent_substrate: precondition failed",
            )
            emitted.append(closure)
            self.deregister_intent(obligation_id)
        elif verdict is _Verdict.SUCCESS:
            current_vector = gather_vector(spec.referenced_entities, self._state_view)
            with self._lock:
                self._pending[obligation_id] = _PendingConfirm(
                    obligation_id=obligation_id,
                    candidate_vector=dict(current_vector),
                    confirm_at_monotonic=self._clock() + self._confirm_window_s,
                )
            spec.last_vector = current_vector
        else:
            spec.last_vector = gather_vector(spec.referenced_entities, self._state_view)
        return emitted

    def _verdict(self, spec: _IntentSpec) -> "_Verdict":
        # Read each referenced entity's state once and dispatch
        # predicates by affinity.
        states: dict[EntityId, "Mapping[str, object] | None"] = {
            eid: self._state_view(eid) for eid in spec.referenced_entities
        }
        for predicate in spec.preconditions:
            if not predicate.evaluate(states.get(predicate.entity_id)):
                return _Verdict.BROKEN
        if not spec.success:
            return _Verdict.OPEN
        for predicate in spec.success:
            if not predicate.evaluate(states.get(predicate.entity_id)):
                return _Verdict.OPEN
        return _Verdict.SUCCESS

    def _close(
        self,
        obligation: ObligationRecord,
        *,
        final_state: ObligationState,
        reason: str,
    ) -> ObligationClosure:
        return self._obligations.close(
            obligation.obligation_id,
            final_state=final_state,
            reason=reason,
            closed_by="intent_substrate",
        )

    def _notify(self, closure: ObligationClosure) -> None:
        with self._lock:
            obs = list(self._closure_observers)
        for cb in obs:
            cb(closure)

    @staticmethod
    def _versions_advanced(
        baseline: Mapping[EntityId, str],
        current: Mapping[EntityId, str],
    ) -> bool:
        if set(baseline) != set(current):
            return True
        return any(current[k] != baseline[k] for k in baseline)


_TERMINAL_STATES = (
    ObligationState.COMPLETED,
    ObligationState.EXPIRED,
    ObligationState.CANCELLED,
)


class _Verdict:
    OPEN = "open"
    BROKEN = "broken"
    SUCCESS = "success"
