"""IntentResolver — predicate-driven intent closure.

The resolver computes verdicts; closure is performed by an
application-supplied IntentClosure adapter. This decouples the
substrate from any specific lifecycle engine — obligations, request
statuses, orchestration steps, recovery executions are all valid
mappings.

Inputs:
  - StateView      caller-supplied: looks up current attribute mapping
                   for an entity_id (returns None if absent)
  - IntentClosure  caller-supplied: performs the success / failure
                   transition for an intent_id; reports is_open
  - EventSpineEngine
                   used for emit_and_dispatch convenience and as the
                   audit destination — the resolver does not subscribe
                   automatically

Mechanism:

  Differential dispatch — inverted index `EventType -> {intent_id}`
    only re-evaluates intents whose predicates watch the event's type.

  Per-intent debounce — bursts of events within `debounce_window_s`
    coalesce into a single re-evaluation per intent.

  Two-confirmation fulfillment — when all success predicates first
    pass, we record an EntityVector (per-entity attribute hash) and
    schedule a confirm at `now + confirm_window_s`. The confirm runs
    via tick(); at that point we re-fetch every referenced entity's
    state and re-hash. Reject if ANY hash advanced. Only when both
    reads agree do we ask the closure to close_success.

  Single-shot precondition failure — when any precondition predicate
    fails, we ask the closure to close_precondition_failed.

The resolver does NOT re-emit world events. Event flow:
  1. App mutates entity state in its engine
  2. App emits a relevant event into the spine
  3. App calls resolver.on_event(event) (or use emit_and_dispatch)
  4. Resolver re-evaluates affected intents, may close some

For idle systems, pair with BackgroundTicker so pending fulfillments
ripen on time even without ambient event traffic.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Callable, Mapping, Sequence

from mcoi_runtime.contracts.event import EventRecord, EventType
from mcoi_runtime.core.event_spine import EventSpineEngine

from .closures import IntentClosure
from .primitives import (
    EntityId,
    IntentId,
    IntentPredicate,
    StateView,
    gather_vector,
)


@dataclass
class _IntentSpec:
    intent_id: IntentId
    preconditions: tuple[IntentPredicate, ...]
    success: tuple[IntentPredicate, ...]
    last_vector: dict[EntityId, str] = field(default_factory=dict)

    @property
    def referenced_entities(self) -> set[EntityId]:
        return {p.entity_id for p in self.preconditions + self.success}


@dataclass
class _PendingConfirm:
    intent_id: IntentId
    candidate_vector: dict[EntityId, str]
    confirm_at_monotonic: float


class IntentResolver:
    DEFAULT_CONFIRM_WINDOW_S = 0.25
    DEFAULT_DEBOUNCE_WINDOW_S = 0.05

    def __init__(
        self,
        *,
        state_view: StateView,
        closure: IntentClosure,
        spine: EventSpineEngine,
        confirm_window_s: float = DEFAULT_CONFIRM_WINDOW_S,
        debounce_window_s: float = DEFAULT_DEBOUNCE_WINDOW_S,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._state_view = state_view
        self._closure = closure
        self._spine = spine
        self._intents: dict[IntentId, _IntentSpec] = {}
        self._index: dict[EventType, set[IntentId]] = defaultdict(set)
        self._pending: dict[IntentId, _PendingConfirm] = {}
        self._last_eval_at: dict[IntentId, float] = {}
        self._deferred_eval_at: dict[IntentId, float] = {}
        self._confirm_window_s = confirm_window_s
        self._debounce_window_s = debounce_window_s
        self._clock = clock
        self._lock = threading.RLock()
        self._closure_observers: list[Callable[[Any], None]] = []

    # --- Registration ---

    def register_intent(
        self,
        intent_id: IntentId,
        *,
        preconditions: Sequence[IntentPredicate],
        success: Sequence[IntentPredicate],
    ) -> None:
        """Register an intent under a caller-chosen ID.

        Typically intent_id is the obligation_id or whichever ID the
        application's IntentClosure understands. The resolver does not
        verify the ID against the closure at registration — it does so
        lazily on each evaluation via closure.is_open(), so an intent
        can be registered before its underlying lifecycle record exists
        if needed.
        """
        spec = _IntentSpec(
            intent_id=intent_id,
            preconditions=tuple(preconditions),
            success=tuple(success),
        )
        with self._lock:
            self._drop_intent_locked(intent_id)
            self._intents[intent_id] = spec
            for predicate in spec.preconditions + spec.success:
                for evt_type in predicate.watches():
                    self._index[evt_type].add(intent_id)

    def deregister_intent(self, intent_id: IntentId) -> None:
        with self._lock:
            self._drop_intent_locked(intent_id)

    def add_closure_observer(self, callback: Callable[[Any], None]) -> None:
        """Register a callback fired with whatever IntentClosure returns
        from close_success or close_precondition_failed."""
        with self._lock:
            self._closure_observers.append(callback)

    # --- Event dispatch ---

    def on_event(self, event: EventRecord) -> list[Any]:
        """Drive replay for a single event. Tick first so any ripe
        candidate confirms run against their original baseline before
        the new event has a chance to overwrite it.
        """
        emitted: list[Any] = list(self._tick_no_notify())
        with self._lock:
            affected = set(self._index.get(event.event_type, set()))
        now = self._clock()
        for iid in affected:
            with self._lock:
                last = self._last_eval_at.get(iid, -float("inf"))
                if now - last < self._debounce_window_s:
                    due_at = last + self._debounce_window_s
                    existing_due = self._deferred_eval_at.get(iid)
                    if existing_due is None or due_at < existing_due:
                        self._deferred_eval_at[iid] = due_at
                    continue
                self._last_eval_at[iid] = now
                self._deferred_eval_at.pop(iid, None)
            emitted.extend(self._evaluate_one(iid))
        emitted.extend(self._tick_no_notify())
        for record in emitted:
            self._notify(record)
        return emitted

    def emit_and_dispatch(self, event: EventRecord) -> list[Any]:
        """Emit the event into the spine and dispatch to indexed intents."""
        self._spine.emit(event)
        return self.on_event(event)

    def evaluate(self, intent_id: IntentId) -> list[Any]:
        """Re-evaluate a single intent on demand (no event)."""
        emitted: list[Any] = list(self._tick_no_notify())
        emitted.extend(self._evaluate_one(intent_id))
        emitted.extend(self._tick_no_notify())
        for record in emitted:
            self._notify(record)
        return emitted

    def tick(self) -> list[Any]:
        """Process pending two-confirm candidates whose window has ripened.

        Public entry point — notifies observers for any closures it
        produces. Use this from BackgroundTicker or any external caller
        that does not separately notify; internal call sites use
        `_tick_no_notify` to avoid double-notification.
        """
        emitted = self._tick_no_notify()
        for record in emitted:
            self._notify(record)
        return emitted

    def _tick_no_notify(self) -> list[Any]:
        emitted: list[Any] = []
        now = self._clock()
        with self._lock:
            ripe = [
                p for p in self._pending.values() if p.confirm_at_monotonic <= now
            ]
            for p in ripe:
                self._pending.pop(p.intent_id, None)
        for p in ripe:
            spec = self._intents.get(p.intent_id)
            if spec is None:
                continue
            if not self._closure.is_open(p.intent_id):
                self.deregister_intent(p.intent_id)
                continue
            current_vector = gather_vector(spec.referenced_entities, self._state_view)
            if self._versions_advanced(p.candidate_vector, current_vector):
                spec.last_vector = current_vector
                continue
            verdict = self._verdict(spec)
            if verdict is _Verdict.SUCCESS:
                record = self._closure.close_success(
                    p.intent_id,
                    "intent_substrate: success predicates confirmed",
                )
                emitted.append(record)
                self.deregister_intent(p.intent_id)
            elif verdict is _Verdict.BROKEN:
                record = self._closure.close_precondition_failed(
                    p.intent_id,
                    "intent_substrate: precondition failed at confirm",
                )
                emitted.append(record)
                self.deregister_intent(p.intent_id)
            else:
                spec.last_vector = current_vector
        now = self._clock()
        with self._lock:
            due_evals = [
                intent_id
                for intent_id, due_at in self._deferred_eval_at.items()
                if due_at <= now
            ]
            for intent_id in due_evals:
                self._deferred_eval_at.pop(intent_id, None)
                self._last_eval_at[intent_id] = now
        for intent_id in due_evals:
            emitted.extend(self._evaluate_one(intent_id))
        return emitted

    def pending_count(self) -> int:
        with self._lock:
            return len(self._pending)

    def is_registered(self, intent_id: IntentId) -> bool:
        with self._lock:
            return intent_id in self._intents

    # --- Internal ---

    def _drop_intent_locked(self, intent_id: IntentId) -> None:
        self._intents.pop(intent_id, None)
        self._pending.pop(intent_id, None)
        self._last_eval_at.pop(intent_id, None)
        self._deferred_eval_at.pop(intent_id, None)
        for ids in self._index.values():
            ids.discard(intent_id)

    def _evaluate_one(self, intent_id: IntentId) -> list[Any]:
        spec = self._intents.get(intent_id)
        if spec is None:
            return []
        if not self._closure.is_open(intent_id):
            self.deregister_intent(intent_id)
            return []
        # If a candidate is already pending, leave it alone — tick owns
        # the path out of pending. (Re-evaluating mid-window would
        # overwrite the candidate vector and silently extend the wait,
        # breaking the two-confirm guarantee.)
        with self._lock:
            if intent_id in self._pending:
                return []
        verdict = self._verdict(spec)
        emitted: list[Any] = []
        if verdict is _Verdict.BROKEN:
            record = self._closure.close_precondition_failed(
                intent_id, "intent_substrate: precondition failed"
            )
            emitted.append(record)
            self.deregister_intent(intent_id)
        elif verdict is _Verdict.SUCCESS:
            current_vector = gather_vector(spec.referenced_entities, self._state_view)
            with self._lock:
                self._pending[intent_id] = _PendingConfirm(
                    intent_id=intent_id,
                    candidate_vector=dict(current_vector),
                    confirm_at_monotonic=self._clock() + self._confirm_window_s,
                )
            spec.last_vector = current_vector
        else:
            spec.last_vector = gather_vector(spec.referenced_entities, self._state_view)
        return emitted

    def _verdict(self, spec: _IntentSpec) -> "_Verdict":
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

    def _notify(self, record: Any) -> None:
        with self._lock:
            obs = list(self._closure_observers)
        for cb in obs:
            cb(record)

    @staticmethod
    def _versions_advanced(
        baseline: Mapping[EntityId, str],
        current: Mapping[EntityId, str],
    ) -> bool:
        if set(baseline) != set(current):
            return True
        return any(current[k] != baseline[k] for k in baseline)


class _Verdict:
    """Internal sentinel objects. `object()` so `is` comparisons are
    unambiguous identity checks (string literals would work via CPython
    interning but the behavior is implementation-dependent).
    """
    OPEN = object()
    BROKEN = object()
    SUCCESS = object()
