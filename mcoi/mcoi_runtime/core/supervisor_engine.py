"""Purpose: continuous supervisor engine — runs one deterministic tick at a time,
polling events, evaluating obligations/deadlines, firing reactions, applying
reasoning, checkpointing state, and emitting heartbeats.
Governance scope: supervisor control loop only.
Dependencies: supervisor contracts, event spine, obligation runtime, reaction engine,
invariant helpers.
Invariants:
  - One tick at a time; no concurrent mutation.
  - Can be advanced manually in tests (clock-injected).
  - Can be resumed from checkpoint.
  - Never bypasses governance — every action passes through policy.
  - No hidden state outside durable subsystems.
  - Livelock detection is explicit.
  - Backpressure is policy-driven.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Callable, Mapping

from mcoi_runtime.contracts.event import EventRecord, EventSource, EventType
from mcoi_runtime.contracts.obligation import ObligationState
from mcoi_runtime.contracts.supervisor import (
    CheckpointStatus,
    LivelockRecord,
    LivelockStrategy,
    RuntimeHeartbeat,
    SupervisorCheckpoint,
    SupervisorDecision,
    SupervisorHealth,
    SupervisorPhase,
    SupervisorPolicy,
    SupervisorTick,
    TickOutcome,
)
from .event_spine import EventSpineEngine
from .invariants import RuntimeCoreInvariantError, stable_identifier
from .obligation_runtime import ObligationRuntimeEngine


# ---------------------------------------------------------------------------
# Governance gate callback protocol
# ---------------------------------------------------------------------------

GovernanceGate = Callable[[str, str, Mapping[str, Any]], bool]
"""(action_type, target_id, context) -> approved.

The supervisor does not own governance evaluation.  The integration bridge
injects this callback to check policy before every action.
"""


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------


class SupervisorEngine:
    """Continuous supervisor that advances one deterministic tick at a time.

    The engine:
    - Polls the event spine for new events
    - Evaluates open obligations and deadlines
    - Fires reactive orchestration for matched events
    - Applies governance before every action
    - Detects livelock (repeated identical tick outcomes)
    - Enforces backpressure (bounds events/actions per tick)
    - Emits heartbeats and checkpoints per policy
    - Can be resumed from a SupervisorCheckpoint
    """

    def __init__(
        self,
        *,
        policy: SupervisorPolicy,
        spine: EventSpineEngine,
        obligation_engine: ObligationRuntimeEngine,
        clock: Callable[[], str] | None = None,
        governance_gate: GovernanceGate | None = None,
    ) -> None:
        self._policy = policy
        self._spine = spine
        self._obligation_engine = obligation_engine
        self._clock = clock or self._default_clock
        self._governance_gate = governance_gate or self._default_gate

        # Mutable supervisor state (not hidden — exposed via checkpoint/health)
        self._tick_number: int = 0
        self._phase: SupervisorPhase = SupervisorPhase.IDLE
        self._consecutive_errors: int = 0
        self._consecutive_idle_ticks: int = 0
        self._recent_outcomes: list[TickOutcome] = []
        self._processed_event_ids: set[str] = set()
        self._livelocks: list[LivelockRecord] = []
        self._checkpoints: list[SupervisorCheckpoint] = []
        self._heartbeats: list[RuntimeHeartbeat] = []
        self._ticks: list[SupervisorTick] = []
        self._halted: bool = False

        # Retention bounds to prevent unbounded memory growth in long-running deployments
        self._max_retained_ticks: int = 1000
        self._max_retained_heartbeats: int = 500
        self._max_retained_checkpoints: int = 100
        self._max_retained_livelocks: int = 200

    @staticmethod
    def _default_clock() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _default_gate(action_type: str, target_id: str, context: Mapping[str, Any]) -> bool:
        return True

    def _safe_governance_gate(
        self, action_type: str, target_id: str, context: Mapping[str, Any],
    ) -> bool:
        """Call governance gate with fail-closed exception handling.

        If the gate callback raises, the action is denied (fail-closed)
        and the error is not propagated — it is logged as a tick error.
        """
        try:
            return self._governance_gate(action_type, target_id, context)
        except Exception:
            return False

    def _now(self) -> str:
        return self._clock()

    # --- Core tick ---

    def tick(self) -> SupervisorTick:
        """Execute one deterministic supervisor tick.

        Returns an immutable SupervisorTick record capturing everything
        that happened during this cycle.
        """
        if self._halted:
            return self._halted_tick()

        started_at = self._now()
        phases: list[SupervisorPhase] = []
        decisions: list[SupervisorDecision] = []
        errors: list[str] = []
        events_polled = 0
        obligations_evaluated = 0
        deadlines_checked = 0
        reactions_fired = 0

        try:
            # Phase 1: Poll events
            self._phase = SupervisorPhase.POLLING
            phases.append(SupervisorPhase.POLLING)
            new_events = self._poll_new_events()
            events_polled = len(new_events)

            # Backpressure check
            if events_polled > self._policy.backpressure_threshold:
                self._phase = SupervisorPhase.DEGRADED
                phases.append(SupervisorPhase.DEGRADED)
                new_events = new_events[: self._policy.max_events_per_tick]
                return self._finalize_tick(
                    started_at, phases, decisions, errors,
                    events_polled, obligations_evaluated, deadlines_checked,
                    reactions_fired, TickOutcome.BACKPRESSURE_APPLIED,
                )

            # Phase 2: Evaluate obligations
            self._phase = SupervisorPhase.EVALUATING_OBLIGATIONS
            phases.append(SupervisorPhase.EVALUATING_OBLIGATIONS)
            obl_decisions, obl_count = self._evaluate_obligations()
            obligations_evaluated = obl_count
            decisions.extend(obl_decisions)

            # Phase 3: Check deadlines
            self._phase = SupervisorPhase.EVALUATING_DEADLINES
            phases.append(SupervisorPhase.EVALUATING_DEADLINES)
            deadline_decisions, dl_count = self._check_deadlines()
            deadlines_checked = dl_count
            decisions.extend(deadline_decisions)

            # Phase 4: Run reactions for new events
            self._phase = SupervisorPhase.RUNNING_REACTIONS
            phases.append(SupervisorPhase.RUNNING_REACTIONS)
            reaction_decisions, rxn_count = self._process_events(new_events)
            reactions_fired = rxn_count
            decisions.extend(reaction_decisions)

            # Phase 5: Reasoning (meta-reasoning hook)
            self._phase = SupervisorPhase.REASONING
            phases.append(SupervisorPhase.REASONING)

            # Phase 6: Act on approved decisions
            self._phase = SupervisorPhase.ACTING
            phases.append(SupervisorPhase.ACTING)
            approved_count = sum(1 for d in decisions if d.governance_approved)

            # Determine outcome
            work_done = (
                events_polled > 0
                or obligations_evaluated > 0
                or reactions_fired > 0
                or approved_count > 0
            )
            outcome = TickOutcome.WORK_DONE if work_done else TickOutcome.IDLE_TICK

            # Livelock detection
            livelock = self._check_livelock(outcome)
            if livelock is not None:
                outcome = TickOutcome.LIVELOCK_DETECTED
                phases.append(SupervisorPhase.DEGRADED)

            # Resolve any unresolved livelocks when work resumes
            if outcome == TickOutcome.WORK_DONE:
                self._resolve_livelocks()

            # Reset or accumulate idle tracking
            if outcome == TickOutcome.IDLE_TICK:
                self._consecutive_idle_ticks += 1
            else:
                self._consecutive_idle_ticks = 0

            self._consecutive_errors = 0

        except Exception as exc:
            errors.append(str(exc))
            outcome = TickOutcome.ERROR
            self._consecutive_errors += 1
            if self._consecutive_errors >= self._policy.max_consecutive_errors:
                self._halted = True
                self._phase = SupervisorPhase.HALTED
                outcome = TickOutcome.HALTED
                phases.append(SupervisorPhase.HALTED)

        tick_record = self._finalize_tick(
            started_at, phases, decisions, errors,
            events_polled, obligations_evaluated, deadlines_checked,
            reactions_fired, outcome,
        )

        # Heartbeat emission
        if self._tick_number % self._policy.heartbeat_every_n_ticks == 0:
            self._emit_heartbeat(tick_record)

        # Checkpoint
        if self._tick_number % self._policy.checkpoint_every_n_ticks == 0:
            self._create_checkpoint()

        return tick_record

    # --- Internal phases ---

    def _poll_new_events(self) -> list[EventRecord]:
        """Get events from the spine that haven't been processed yet."""
        all_events = self._spine.list_events()
        new = [e for e in all_events if e.event_id not in self._processed_event_ids]
        # Batch update — all-or-nothing to avoid partial state on exception
        self._processed_event_ids.update(e.event_id for e in new)
        return new

    def _evaluate_obligations(self) -> tuple[list[SupervisorDecision], int]:
        """Check open obligations and decide on actions."""
        decisions: list[SupervisorDecision] = []
        open_obls = self._obligation_engine.list_obligations(state=ObligationState.ACTIVE)
        open_obls += self._obligation_engine.list_obligations(state=ObligationState.PENDING)

        for obl in open_obls:
            # Pending obligations should be activated
            if obl.state == ObligationState.PENDING:
                approved = self._safe_governance_gate(
                    "activate_obligation",
                    obl.obligation_id,
                    {"trigger": obl.trigger.value},
                )
                decision = SupervisorDecision(
                    decision_id=stable_identifier("sv-dec", {
                        "tick": self._tick_number,
                        "action": "activate_obligation",
                        "target": obl.obligation_id,
                    }),
                    action_type="activate_obligation",
                    target_id=obl.obligation_id,
                    reason=f"pending obligation from trigger {obl.trigger.value}",
                    governance_approved=approved,
                    decided_at=self._now(),
                )
                decisions.append(decision)
                if approved:
                    self._obligation_engine.activate(obl.obligation_id)

        return decisions, len(open_obls)

    def _check_deadlines(self) -> tuple[list[SupervisorDecision], int]:
        """Check active obligations for deadline breaches."""
        decisions: list[SupervisorDecision] = []
        now = self._now()
        active = self._obligation_engine.list_obligations(state=ObligationState.ACTIVE)
        checked = 0

        for obl in active:
            checked += 1
            if obl.deadline.due_at <= now:
                approved = self._safe_governance_gate(
                    "expire_obligation",
                    obl.obligation_id,
                    {"due_at": obl.deadline.due_at, "current_time": now},
                )
                decision = SupervisorDecision(
                    decision_id=stable_identifier("sv-dec", {
                        "tick": self._tick_number,
                        "action": "expire_obligation",
                        "target": obl.obligation_id,
                    }),
                    action_type="expire_obligation",
                    target_id=obl.obligation_id,
                    reason=f"deadline breached: due_at={obl.deadline.due_at}",
                    governance_approved=approved,
                    decided_at=self._now(),
                )
                decisions.append(decision)
                if approved:
                    self._obligation_engine.close(
                        obl.obligation_id,
                        final_state=ObligationState.EXPIRED,
                        reason="deadline breached by supervisor tick",
                        closed_by="supervisor",
                    )

        return decisions, checked

    def _process_events(self, events: list[EventRecord]) -> tuple[list[SupervisorDecision], int]:
        """Process new events through reactive orchestration."""
        decisions: list[SupervisorDecision] = []
        reactions_fired = 0

        for event in events[: self._policy.max_events_per_tick]:
            subs = self._spine.matching_subscriptions(event)
            for sub in subs:
                approved = self._safe_governance_gate(
                    "fire_reaction",
                    sub.reaction_id,
                    {"event_type": event.event_type.value, "event_id": event.event_id},
                )
                decision = SupervisorDecision(
                    decision_id=stable_identifier("sv-dec", {
                        "tick": self._tick_number,
                        "action": "fire_reaction",
                        "target": sub.reaction_id,
                        "event": event.event_id,
                    }),
                    action_type="fire_reaction",
                    target_id=sub.reaction_id,
                    reason=f"event {event.event_type.value} matched subscription {sub.subscription_id}",
                    governance_approved=approved,
                    decided_at=self._now(),
                )
                decisions.append(decision)
                if approved:
                    reactions_fired += 1

        return decisions, reactions_fired

    # --- Livelock detection ---

    def _check_livelock(self, current_outcome: TickOutcome) -> LivelockRecord | None:
        """Detect repeated identical outcomes indicating a stall loop."""
        self._recent_outcomes.append(current_outcome)

        # Keep a rolling window of recent outcomes
        window_size = self._policy.livelock_repeat_threshold
        if len(self._recent_outcomes) > window_size * 2:
            self._recent_outcomes = self._recent_outcomes[-(window_size * 2):]

        if len(self._recent_outcomes) < window_size:
            return None

        recent = self._recent_outcomes[-window_size:]
        if len(set(recent)) == 1 and recent[0] not in (TickOutcome.WORK_DONE, TickOutcome.HEALTHY):
            pattern = recent[0].value
            livelock = LivelockRecord(
                livelock_id=stable_identifier("livelock", {
                    "tick": self._tick_number,
                    "pattern": pattern,
                }),
                tick_number=self._tick_number,
                repeated_pattern=pattern,
                repeat_count=window_size,
                strategy_applied=self._policy.livelock_strategy,
                resolved=False,
                detected_at=self._now(),
            )
            self._livelocks.append(livelock)

            # Apply strategy
            if self._policy.livelock_strategy == LivelockStrategy.HALT:
                self._halted = True
                self._phase = SupervisorPhase.HALTED
            elif self._policy.livelock_strategy == LivelockStrategy.PAUSE:
                self._phase = SupervisorPhase.DEGRADED

            # Emit livelock event
            evt = EventRecord(
                event_id=stable_identifier("evt", {
                    "type": "livelock",
                    "tick": self._tick_number,
                }),
                event_type=EventType.SUPERVISOR_LIVELOCK,
                source=EventSource.SUPERVISOR,
                correlation_id=f"supervisor-tick-{self._tick_number}",
                payload={"pattern": pattern, "repeat_count": window_size},
                emitted_at=self._now(),
            )
            self._spine.emit(evt)

            # Reset window to prevent immediate re-detection
            self._recent_outcomes.clear()

            return livelock

        return None

    def _resolve_livelocks(self) -> None:
        """Mark all unresolved livelock records as resolved."""
        resolved: list[LivelockRecord] = []
        for ll in self._livelocks:
            if not ll.resolved:
                resolved_ll = LivelockRecord(
                    livelock_id=ll.livelock_id,
                    tick_number=ll.tick_number,
                    repeated_pattern=ll.repeated_pattern,
                    repeat_count=ll.repeat_count,
                    strategy_applied=ll.strategy_applied,
                    resolved=True,
                    detected_at=ll.detected_at,
                    resolution_detail=f"work resumed at tick {self._tick_number}",
                )
                resolved.append(resolved_ll)
            else:
                resolved.append(ll)
        self._livelocks = resolved

    # --- Heartbeat ---

    def _emit_heartbeat(self, tick: SupervisorTick) -> RuntimeHeartbeat:
        """Emit a periodic heartbeat event into the spine."""
        hb = RuntimeHeartbeat(
            heartbeat_id=stable_identifier("hb", {"tick": self._tick_number}),
            tick_number=self._tick_number,
            phase=self._phase,
            outcome_of_last_tick=tick.outcome,
            open_obligations=self._obligation_engine.open_count,
            pending_events=len(self._spine.list_events()) - len(self._processed_event_ids),
            uptime_ticks=self._tick_number,
            emitted_at=self._now(),
        )
        self._heartbeats.append(hb)

        evt = EventRecord(
            event_id=stable_identifier("evt", {
                "type": "heartbeat",
                "tick": self._tick_number,
            }),
            event_type=EventType.SUPERVISOR_HEARTBEAT,
            source=EventSource.SUPERVISOR,
            correlation_id=f"supervisor-heartbeat-{self._tick_number}",
            payload={"tick_number": self._tick_number, "outcome": tick.outcome.value},
            emitted_at=self._now(),
        )
        self._spine.emit(evt)
        # Mark heartbeat event as processed so we don't re-process it
        self._processed_event_ids.add(evt.event_id)

        return hb

    # --- Checkpoint ---

    def _create_checkpoint(self) -> SupervisorCheckpoint:
        """Create a serializable checkpoint of current supervisor state."""
        open_obls = self._obligation_engine.list_obligations(state=ObligationState.ACTIVE)
        open_obls += self._obligation_engine.list_obligations(state=ObligationState.PENDING)

        state_hash = hashlib.sha256(
            json.dumps({
                "tick": self._tick_number,
                "phase": self._phase.value,
                "errors": self._consecutive_errors,
                "idle": self._consecutive_idle_ticks,
                "processed": len(self._processed_event_ids),
                "halted": self._halted,
                "recent_outcomes": [o.value for o in self._recent_outcomes[-10:]],
            }, sort_keys=True).encode()
        ).hexdigest()

        cp = SupervisorCheckpoint(
            checkpoint_id=stable_identifier("cp", {"tick": self._tick_number}),
            tick_number=self._tick_number,
            phase=self._phase,
            status=CheckpointStatus.VALID,
            open_obligation_ids=tuple(o.obligation_id for o in open_obls),
            pending_event_count=max(0, len(self._spine.list_events()) - len(self._processed_event_ids)),
            consecutive_errors=self._consecutive_errors,
            consecutive_idle_ticks=self._consecutive_idle_ticks,
            recent_tick_outcomes=tuple(self._recent_outcomes[-10:]),
            state_hash=state_hash,
            created_at=self._now(),
        )
        self._checkpoints.append(cp)

        evt = EventRecord(
            event_id=stable_identifier("evt", {
                "type": "checkpoint",
                "tick": self._tick_number,
            }),
            event_type=EventType.SUPERVISOR_CHECKPOINT,
            source=EventSource.SUPERVISOR,
            correlation_id=f"supervisor-checkpoint-{self._tick_number}",
            payload={"checkpoint_id": cp.checkpoint_id, "state_hash": state_hash},
            emitted_at=self._now(),
        )
        self._spine.emit(evt)
        self._processed_event_ids.add(evt.event_id)

        return cp

    # --- Resume from checkpoint ---

    def resume_from_checkpoint(self, checkpoint: SupervisorCheckpoint) -> None:
        """Restore supervisor state from a checkpoint.

        This resets the internal counters to match the checkpoint and
        allows the supervisor to continue ticking from where it left off.
        """
        if checkpoint.status != CheckpointStatus.VALID:
            raise RuntimeCoreInvariantError(
                f"cannot resume from {checkpoint.status.value} checkpoint"
            )
        self._tick_number = checkpoint.tick_number
        self._consecutive_errors = checkpoint.consecutive_errors
        self._consecutive_idle_ticks = checkpoint.consecutive_idle_ticks
        self._recent_outcomes = list(checkpoint.recent_tick_outcomes)
        self._phase = checkpoint.phase
        self._halted = checkpoint.phase == SupervisorPhase.HALTED

    def sync_processed_events(self) -> None:
        """Mark all current spine events as processed.

        Called when the supervisor needs to skip all events currently
        in the spine (e.g., after a non-replay restore where re-processing
        is undesirable).
        """
        self._processed_event_ids = {
            e.event_id for e in self._spine.list_events()
        }

    def restore_processed_event_ids(self, event_ids: set[str]) -> None:
        """Restore the exact set of processed event IDs from a snapshot."""
        validated: set[str] = set()
        for eid in event_ids:
            if not isinstance(eid, str) or not eid.strip():
                raise RuntimeCoreInvariantError(
                    f"processed event ID must be a non-empty string, got {eid!r}"
                )
            validated.add(eid)
        self._processed_event_ids = validated

    @property
    def processed_event_ids(self) -> frozenset[str]:
        """Return the current set of processed event IDs (immutable view)."""
        return frozenset(self._processed_event_ids)

    # --- Health assessment ---

    def assess_health(self) -> SupervisorHealth:
        """Produce a point-in-time health assessment."""
        open_obls = self._obligation_engine.list_obligations(state=ObligationState.ACTIVE)
        open_obls += self._obligation_engine.list_obligations(state=ObligationState.PENDING)

        pending = max(0, len(self._spine.list_events()) - len(self._processed_event_ids))
        has_livelock = any(not ll.resolved for ll in self._livelocks)

        # Confidence: degrade based on errors, idle ticks, livelock
        confidence = 1.0
        if self._consecutive_errors > 0:
            confidence -= min(0.3, self._consecutive_errors * 0.1)
        if self._consecutive_idle_ticks > 5:
            confidence -= 0.1
        if has_livelock:
            confidence -= 0.3
        if self._halted:
            confidence = 0.0
        confidence = max(0.0, min(1.0, confidence))

        return SupervisorHealth(
            health_id=stable_identifier("sv-health", {"tick": self._tick_number}),
            tick_number=self._tick_number,
            phase=self._phase,
            consecutive_errors=self._consecutive_errors,
            consecutive_idle_ticks=self._consecutive_idle_ticks,
            backpressure_active=pending > self._policy.backpressure_threshold,
            livelock_detected=has_livelock,
            open_obligations=len(open_obls),
            pending_events=pending,
            overall_confidence=round(confidence, 4),
            assessed_at=self._now(),
        )

    # --- Halted tick ---

    def _halted_tick(self) -> SupervisorTick:
        """Produce a HALTED tick record when the supervisor is stopped."""
        self._tick_number += 1
        now = self._now()
        tick_id = stable_identifier("tick", {"n": self._tick_number})
        return SupervisorTick(
            tick_id=tick_id,
            tick_number=self._tick_number,
            phase_sequence=(SupervisorPhase.HALTED,),
            events_polled=0,
            obligations_evaluated=0,
            deadlines_checked=0,
            reactions_fired=0,
            decisions=(),
            outcome=TickOutcome.HALTED,
            errors=("supervisor is halted",),
            started_at=now,
            completed_at=now,
            duration_ms=0,
        )

    # --- Finalize tick ---

    def _finalize_tick(
        self,
        started_at: str,
        phases: list[SupervisorPhase],
        decisions: list[SupervisorDecision],
        errors: list[str],
        events_polled: int,
        obligations_evaluated: int,
        deadlines_checked: int,
        reactions_fired: int,
        outcome: TickOutcome,
    ) -> SupervisorTick:
        """Create the immutable tick record and advance the tick counter."""
        self._tick_number += 1
        completed_at = self._now()
        tick_id = stable_identifier("tick", {"n": self._tick_number})

        # Cap decisions per policy
        capped_decisions = decisions[: self._policy.max_actions_per_tick]

        tick = SupervisorTick(
            tick_id=tick_id,
            tick_number=self._tick_number,
            phase_sequence=tuple(phases),
            events_polled=events_polled,
            obligations_evaluated=obligations_evaluated,
            deadlines_checked=deadlines_checked,
            reactions_fired=reactions_fired,
            decisions=tuple(capped_decisions),
            outcome=outcome,
            errors=tuple(errors),
            started_at=started_at,
            completed_at=completed_at,
            duration_ms=0,
        )
        self._ticks.append(tick)
        self._prune_history()
        return tick

    def _prune_history(self) -> None:
        """Trim retained collections to prevent unbounded memory growth."""
        if len(self._ticks) > self._max_retained_ticks:
            self._ticks = self._ticks[-self._max_retained_ticks:]
        if len(self._heartbeats) > self._max_retained_heartbeats:
            self._heartbeats = self._heartbeats[-self._max_retained_heartbeats:]
        if len(self._checkpoints) > self._max_retained_checkpoints:
            self._checkpoints = self._checkpoints[-self._max_retained_checkpoints:]
        if len(self._livelocks) > self._max_retained_livelocks:
            self._livelocks = self._livelocks[-self._max_retained_livelocks:]

    # --- Properties ---

    @property
    def tick_number(self) -> int:
        return self._tick_number

    @property
    def phase(self) -> SupervisorPhase:
        return self._phase

    @property
    def is_halted(self) -> bool:
        return self._halted

    @property
    def tick_history(self) -> tuple[SupervisorTick, ...]:
        return tuple(self._ticks)

    @property
    def checkpoint_history(self) -> tuple[SupervisorCheckpoint, ...]:
        return tuple(self._checkpoints)

    @property
    def heartbeat_history(self) -> tuple[RuntimeHeartbeat, ...]:
        return tuple(self._heartbeats)

    @property
    def livelock_history(self) -> tuple[LivelockRecord, ...]:
        return tuple(self._livelocks)
