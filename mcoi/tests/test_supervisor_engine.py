"""Engine-level tests for the SupervisorEngine.

Tests deterministic tick execution, obligation evaluation, deadline checking,
event processing, backpressure, livelock detection, heartbeats, checkpoints,
health assessment, halt behavior, and resume.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.contracts.event import (
    EventRecord,
    EventSource,
    EventSubscription,
    EventType,
)
from mcoi_runtime.contracts.obligation import (
    ObligationDeadline,
    ObligationOwner,
    ObligationState,
    ObligationTrigger,
)
from mcoi_runtime.contracts.supervisor import (
    CheckpointStatus,
    LivelockStrategy,
    SupervisorPhase,
    SupervisorPolicy,
    TickOutcome,
)
from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.obligation_runtime import ObligationRuntimeEngine
from mcoi_runtime.core.supervisor_engine import SupervisorEngine

NOW = "2025-01-01T00:00:00+00:00"
FUTURE = "2026-01-01T00:00:00+00:00"
PAST = "2024-01-01T00:00:00+00:00"


def _clock():
    return NOW


def _policy(**overrides) -> SupervisorPolicy:
    defaults = dict(
        policy_id="test-policy",
        tick_interval_ms=100,
        max_events_per_tick=10,
        max_actions_per_tick=10,
        backpressure_threshold=5,
        livelock_repeat_threshold=3,
        livelock_strategy=LivelockStrategy.ESCALATE,
        heartbeat_every_n_ticks=5,
        checkpoint_every_n_ticks=5,
        max_consecutive_errors=3,
        created_at=NOW,
    )
    defaults.update(overrides)
    return SupervisorPolicy(**defaults)


def _engine(**overrides) -> SupervisorEngine:
    spine = EventSpineEngine(clock=_clock)
    obl_engine = ObligationRuntimeEngine(clock=_clock)
    return SupervisorEngine(
        policy=overrides.pop("policy", _policy()),
        spine=overrides.pop("spine", spine),
        obligation_engine=overrides.pop("obligation_engine", obl_engine),
        clock=overrides.pop("clock", _clock),
        **overrides,
    )


def _event(event_id: str, event_type: EventType = EventType.CUSTOM) -> EventRecord:
    return EventRecord(
        event_id=event_id,
        event_type=event_type,
        source=EventSource.EXTERNAL,
        correlation_id="corr-1",
        payload={"test": True},
        emitted_at=NOW,
    )


def _owner(owner_id: str = "owner-1") -> ObligationOwner:
    return ObligationOwner(owner_id=owner_id, owner_type="team", display_name="Test Team")


def _deadline(due_at: str = FUTURE) -> ObligationDeadline:
    return ObligationDeadline(deadline_id="dl-1", due_at=due_at)


# =====================================================================
# Basic tick behavior
# =====================================================================


class TestBasicTick:
    def test_idle_tick_no_events(self) -> None:
        eng = _engine()
        tick = eng.tick()
        assert tick.outcome == TickOutcome.IDLE_TICK
        assert tick.tick_number == 1
        assert tick.events_polled == 0

    def test_tick_increments(self) -> None:
        eng = _engine()
        eng.tick()
        eng.tick()
        assert eng.tick_number == 2

    def test_tick_records_phases(self) -> None:
        eng = _engine()
        tick = eng.tick()
        assert SupervisorPhase.POLLING in tick.phase_sequence
        assert SupervisorPhase.EVALUATING_OBLIGATIONS in tick.phase_sequence
        assert SupervisorPhase.ACTING in tick.phase_sequence


# =====================================================================
# Event processing
# =====================================================================


class TestEventProcessing:
    def test_new_events_polled(self) -> None:
        spine = EventSpineEngine(clock=_clock)
        spine.emit(_event("e1"))
        eng = _engine(spine=spine)
        tick = eng.tick()
        assert tick.events_polled == 1
        assert tick.outcome == TickOutcome.WORK_DONE

    def test_events_not_reprocessed(self) -> None:
        spine = EventSpineEngine(clock=_clock)
        spine.emit(_event("e1"))
        eng = _engine(spine=spine)
        eng.tick()
        tick2 = eng.tick()
        assert tick2.events_polled == 0

    def test_subscription_matching_fires_reaction(self) -> None:
        spine = EventSpineEngine(clock=_clock)
        spine.subscribe(EventSubscription(
            subscription_id="sub1",
            event_type=EventType.CUSTOM,
            subscriber_id="test",
            reaction_id="rxn1",
            created_at=NOW,
        ))
        spine.emit(_event("e1"))
        eng = _engine(spine=spine)
        tick = eng.tick()
        assert tick.reactions_fired == 1
        assert any(d.action_type == "fire_reaction" for d in tick.decisions)

    def test_subscription_matching_reason_bounded(self) -> None:
        spine = EventSpineEngine(clock=_clock)
        spine.subscribe(EventSubscription(
            subscription_id="sub-secret",
            event_type=EventType.CUSTOM,
            subscriber_id="test",
            reaction_id="rxn1",
            created_at=NOW,
        ))
        spine.emit(_event("e-secret"))
        eng = _engine(spine=spine)
        tick = eng.tick()
        decision = next(d for d in tick.decisions if d.action_type == "fire_reaction")
        assert decision.reason == "event matched subscription"
        assert "sub-secret" not in decision.reason
        assert EventType.CUSTOM.value not in decision.reason


# =====================================================================
# Obligation evaluation
# =====================================================================


class TestObligationEvaluation:
    def test_pending_obligations_activated(self) -> None:
        spine = EventSpineEngine(clock=_clock)
        obl_engine = ObligationRuntimeEngine(clock=_clock)
        obl = obl_engine.create_obligation(
            trigger=ObligationTrigger.CUSTOM,
            trigger_ref_id="ref-1",
            owner=_owner(),
            deadline=_deadline(),
            description="test obligation",
            correlation_id="corr-1",
        )
        eng = _engine(spine=spine, obligation_engine=obl_engine)
        tick = eng.tick()
        assert tick.obligations_evaluated > 0
        updated = obl_engine.get_obligation(obl.obligation_id)
        assert updated is not None
        assert updated.state == ObligationState.ACTIVE

    def test_governance_can_block_activation(self) -> None:
        spine = EventSpineEngine(clock=_clock)
        obl_engine = ObligationRuntimeEngine(clock=_clock)
        obl_engine.create_obligation(
            trigger=ObligationTrigger.CUSTOM,
            trigger_ref_id="ref-1",
            owner=_owner(),
            deadline=_deadline(),
            description="test",
            correlation_id="corr-1",
        )
        eng = _engine(
            spine=spine,
            obligation_engine=obl_engine,
            governance_gate=lambda *_: False,
        )
        tick = eng.tick()
        # Should have a decision that was not approved
        blocked = [d for d in tick.decisions if not d.governance_approved]
        assert len(blocked) > 0

    def test_pending_obligation_reason_bounded(self) -> None:
        spine = EventSpineEngine(clock=_clock)
        obl_engine = ObligationRuntimeEngine(clock=_clock)
        obl_engine.create_obligation(
            trigger=ObligationTrigger.CUSTOM,
            trigger_ref_id="ref-1",
            owner=_owner(),
            deadline=_deadline(),
            description="test",
            correlation_id="corr-1",
        )
        eng = _engine(spine=spine, obligation_engine=obl_engine)
        tick = eng.tick()
        decision = next(d for d in tick.decisions if d.action_type == "activate_obligation")
        assert decision.reason == "pending obligation"
        assert ObligationTrigger.CUSTOM.value not in decision.reason


# =====================================================================
# Deadline checking
# =====================================================================


class TestDeadlineChecking:
    def test_expired_obligation_closed(self) -> None:
        spine = EventSpineEngine(clock=_clock)
        obl_engine = ObligationRuntimeEngine(clock=_clock)
        obl = obl_engine.create_obligation(
            trigger=ObligationTrigger.CUSTOM,
            trigger_ref_id="ref-1",
            owner=_owner(),
            deadline=_deadline(due_at=PAST),
            description="expired test",
            correlation_id="corr-1",
        )
        obl_engine.activate(obl.obligation_id)
        eng = _engine(spine=spine, obligation_engine=obl_engine)
        tick = eng.tick()
        assert tick.deadlines_checked > 0
        updated = obl_engine.get_obligation(obl.obligation_id)
        assert updated is not None
        assert updated.state == ObligationState.EXPIRED

    def test_deadline_reason_bounded(self) -> None:
        spine = EventSpineEngine(clock=_clock)
        obl_engine = ObligationRuntimeEngine(clock=_clock)
        obl = obl_engine.create_obligation(
            trigger=ObligationTrigger.CUSTOM,
            trigger_ref_id="ref-1",
            owner=_owner(),
            deadline=_deadline(due_at=PAST),
            description="expired test",
            correlation_id="corr-1",
        )
        obl_engine.activate(obl.obligation_id)
        eng = _engine(spine=spine, obligation_engine=obl_engine)
        tick = eng.tick()
        decision = next(d for d in tick.decisions if d.action_type == "expire_obligation")
        assert decision.reason == "deadline breached"
        assert PAST not in decision.reason


# =====================================================================
# Backpressure
# =====================================================================


class TestBackpressure:
    def test_backpressure_when_events_exceed_threshold(self) -> None:
        spine = EventSpineEngine(clock=_clock)
        # Emit more events than backpressure threshold (5)
        for i in range(10):
            spine.emit(_event(f"e{i}"))
        eng = _engine(spine=spine)
        tick = eng.tick()
        assert tick.outcome == TickOutcome.BACKPRESSURE_APPLIED
        assert SupervisorPhase.DEGRADED in tick.phase_sequence


# =====================================================================
# Livelock detection
# =====================================================================


class TestLivelockDetection:
    def test_livelock_after_repeated_idle(self) -> None:
        eng = _engine(policy=_policy(livelock_repeat_threshold=3))
        eng.tick()  # idle 1
        eng.tick()  # idle 2
        tick3 = eng.tick()  # idle 3 — should detect livelock
        assert tick3.outcome == TickOutcome.LIVELOCK_DETECTED
        assert len(eng.livelock_history) == 1

    def test_livelock_halt_strategy(self) -> None:
        eng = _engine(policy=_policy(
            livelock_repeat_threshold=3,
            livelock_strategy=LivelockStrategy.HALT,
        ))
        eng.tick()
        eng.tick()
        eng.tick()
        assert eng.is_halted

    def test_no_livelock_with_mixed_outcomes(self) -> None:
        spine = EventSpineEngine(clock=_clock)
        obl_engine = ObligationRuntimeEngine(clock=_clock)
        eng = _engine(spine=spine, obligation_engine=obl_engine, policy=_policy(livelock_repeat_threshold=3))
        eng.tick()  # idle
        spine.emit(_event("e1"))
        eng.tick()  # work_done
        eng.tick()  # idle again
        assert len(eng.livelock_history) == 0


# =====================================================================
# Halt behavior
# =====================================================================


class TestHaltBehavior:
    def test_halted_engine_produces_halted_ticks(self) -> None:
        eng = _engine(policy=_policy(
            livelock_repeat_threshold=3,
            livelock_strategy=LivelockStrategy.HALT,
        ))
        eng.tick()
        eng.tick()
        eng.tick()  # triggers livelock -> halt
        tick4 = eng.tick()
        assert tick4.outcome == TickOutcome.HALTED
        assert tick4.phase_sequence == (SupervisorPhase.HALTED,)

    def test_consecutive_errors_cause_halt(self) -> None:
        spine = EventSpineEngine(clock=_clock)

        # Use a gate that returns False (denied) to exercise the
        # fail-closed path without raising — gate exceptions are now
        # caught by _safe_governance_gate and converted to False.
        # To test halt on errors, we instead inject a spine that breaks
        # during polling to produce real tick-level errors.
        class BrokenSpine(EventSpineEngine):
            _call_count = 0

            def list_events(self):
                self._call_count += 1
                raise RuntimeError("spine down")

        broken_spine = BrokenSpine(clock=_clock)
        obl_engine = ObligationRuntimeEngine(clock=_clock)
        eng = _engine(
            spine=broken_spine,
            obligation_engine=obl_engine,
            policy=_policy(max_consecutive_errors=2),
        )
        eng.tick()  # error 1
        tick2 = eng.tick()  # error 2 — should halt
        assert tick2.outcome == TickOutcome.HALTED
        assert eng.is_halted
        assert tick2.errors[-1] == "supervisor tick error"
        assert "spine down" not in tick2.errors[-1]

    def test_timeout_errors_use_bounded_label(self) -> None:
        class SlowSpine(EventSpineEngine):
            def list_events(self):
                raise TimeoutError("poll timeout")

        eng = _engine(
            spine=SlowSpine(clock=_clock),
            obligation_engine=ObligationRuntimeEngine(clock=_clock),
            policy=_policy(max_consecutive_errors=5),
        )
        tick = eng.tick()
        assert tick.errors[-1] == "supervisor tick timeout"
        assert "TimeoutError" not in tick.errors[-1]
        assert "poll timeout" not in tick.errors[-1]


# =====================================================================
# Heartbeats
# =====================================================================


class TestHeartbeats:
    def test_heartbeat_emitted_on_schedule(self) -> None:
        eng = _engine(policy=_policy(heartbeat_every_n_ticks=2))
        eng.tick()
        eng.tick()  # tick 2 — should emit heartbeat
        assert len(eng.heartbeat_history) == 1

    def test_heartbeat_event_in_spine(self) -> None:
        spine = EventSpineEngine(clock=_clock)
        eng = _engine(spine=spine, policy=_policy(heartbeat_every_n_ticks=1))
        eng.tick()
        events = spine.list_events(event_type=EventType.SUPERVISOR_HEARTBEAT)
        assert len(events) >= 1


# =====================================================================
# Checkpoints
# =====================================================================


class TestCheckpoints:
    def test_checkpoint_created_on_schedule(self) -> None:
        eng = _engine(policy=_policy(checkpoint_every_n_ticks=2))
        eng.tick()
        eng.tick()  # should checkpoint
        assert len(eng.checkpoint_history) == 1

    def test_checkpoint_has_valid_status(self) -> None:
        eng = _engine(policy=_policy(checkpoint_every_n_ticks=1))
        eng.tick()
        cp = eng.checkpoint_history[0]
        assert cp.status == CheckpointStatus.VALID
        assert cp.tick_number == 1

    def test_checkpoint_event_in_spine(self) -> None:
        spine = EventSpineEngine(clock=_clock)
        eng = _engine(spine=spine, policy=_policy(checkpoint_every_n_ticks=1))
        eng.tick()
        events = spine.list_events(event_type=EventType.SUPERVISOR_CHECKPOINT)
        assert len(events) >= 1


# =====================================================================
# Resume from checkpoint
# =====================================================================


class TestResumeFromCheckpoint:
    def test_resume_restores_tick_number(self) -> None:
        eng = _engine(policy=_policy(checkpoint_every_n_ticks=1))
        eng.tick()
        eng.tick()
        eng.tick()
        cp = eng.checkpoint_history[-1]

        # Create fresh engine and resume
        new_eng = _engine(policy=_policy(checkpoint_every_n_ticks=1))
        new_eng.resume_from_checkpoint(cp)
        assert new_eng.tick_number == cp.tick_number

    def test_resume_rejects_invalid_checkpoint(self) -> None:
        from mcoi_runtime.contracts.supervisor import (
            CheckpointStatus,
            SupervisorCheckpoint,
            SupervisorPhase,
        )
        from mcoi_runtime.core.invariants import RuntimeCoreInvariantError

        eng = _engine()
        cp = SupervisorCheckpoint(
            checkpoint_id="cp-bad",
            tick_number=5,
            phase=SupervisorPhase.IDLE,
            status=CheckpointStatus.CORRUPTED,
            open_obligation_ids=(),
            pending_event_count=0,
            consecutive_errors=0,
            consecutive_idle_ticks=0,
            recent_tick_outcomes=(),
            state_hash="hash",
            created_at=NOW,
        )
        with pytest.raises(RuntimeCoreInvariantError, match="corrupted"):
            eng.resume_from_checkpoint(cp)


# =====================================================================
# Health assessment
# =====================================================================


class TestHealthAssessment:
    def test_healthy_engine(self) -> None:
        eng = _engine()
        health = eng.assess_health()
        assert health.overall_confidence == 1.0
        assert health.livelock_detected is False

    def test_health_degrades_on_errors(self) -> None:
        # Use a spine that fails once during tick, then recovers for health check.
        class FailOnceSpine(EventSpineEngine):
            _fail = True

            def list_events(self):
                if self._fail:
                    self._fail = False
                    raise RuntimeError("spine read failure")
                return super().list_events()

        spine = FailOnceSpine(clock=_clock)
        obl_engine = ObligationRuntimeEngine(clock=_clock)
        eng = _engine(
            spine=spine,
            obligation_engine=obl_engine,
            policy=_policy(max_consecutive_errors=10),
        )
        eng.tick()
        health = eng.assess_health()
        assert health.consecutive_errors == 1
        assert health.overall_confidence < 1.0

    def test_halted_engine_zero_confidence(self) -> None:
        eng = _engine(policy=_policy(
            livelock_repeat_threshold=3,
            livelock_strategy=LivelockStrategy.HALT,
        ))
        eng.tick()
        eng.tick()
        eng.tick()
        health = eng.assess_health()
        assert health.overall_confidence == 0.0


# =====================================================================
# Properties
# =====================================================================


class TestEngineProperties:
    def test_tick_history(self) -> None:
        eng = _engine()
        eng.tick()
        eng.tick()
        assert len(eng.tick_history) == 2

    def test_phase_starts_idle(self) -> None:
        eng = _engine()
        assert eng.phase == SupervisorPhase.IDLE


# ---------------------------------------------------------------------------
# Audit #10 — history pruning and event ID validation
# ---------------------------------------------------------------------------


class TestHistoryPruning:
    """Verify that retained collections are bounded after many ticks."""

    def test_ticks_pruned_after_threshold(self) -> None:
        eng = _engine(policy=_policy(
            heartbeat_every_n_ticks=9999,
            checkpoint_every_n_ticks=9999,
        ))
        # Run more ticks than the retention limit
        for _ in range(eng._max_retained_ticks + 50):
            eng.tick()
        assert len(eng._ticks) <= eng._max_retained_ticks

    def test_small_tick_count_not_pruned(self) -> None:
        eng = _engine()
        for _ in range(3):
            eng.tick()
        assert len(eng._ticks) == 3


class TestProcessedEventIdValidation:
    """Verify restore_processed_event_ids validates elements."""

    def test_non_string_event_id_rejected(self) -> None:
        eng = _engine()
        with pytest.raises(Exception, match="non-empty string"):
            eng.restore_processed_event_ids({123})  # type: ignore[arg-type]

    def test_empty_string_event_id_rejected(self) -> None:
        eng = _engine()
        with pytest.raises(Exception, match="non-empty string"):
            eng.restore_processed_event_ids({"valid-id", ""})

    def test_valid_event_ids_accepted(self) -> None:
        eng = _engine()
        eng.restore_processed_event_ids({"evt-1", "evt-2", "evt-3"})
        assert eng.processed_event_ids == frozenset({"evt-1", "evt-2", "evt-3"})
