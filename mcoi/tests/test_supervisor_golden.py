"""Golden scenario tests for the supervisor integration bridge.

Tests end-to-end flows: multi-tick execution, dashboard summary extraction,
checkpoint resume, governance integration, and the full operational loop.
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
    TickOutcome,
)
from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.obligation_runtime import ObligationRuntimeEngine
from mcoi_runtime.core.supervisor_engine import SupervisorEngine
from mcoi_runtime.core.supervisor_integration import SupervisorBridge

NOW = "2025-01-01T00:00:00+00:00"
FUTURE = "2026-01-01T00:00:00+00:00"
PAST = "2024-01-01T00:00:00+00:00"


def _clock():
    return NOW


def _event(event_id: str, event_type: EventType = EventType.CUSTOM) -> EventRecord:
    return EventRecord(
        event_id=event_id,
        event_type=event_type,
        source=EventSource.EXTERNAL,
        correlation_id="corr-1",
        payload={},
        emitted_at=NOW,
    )


def _owner() -> ObligationOwner:
    return ObligationOwner(owner_id="owner-1", owner_type="team", display_name="Team")


def _deadline(due_at: str = FUTURE) -> ObligationDeadline:
    return ObligationDeadline(deadline_id="dl-1", due_at=due_at)


# =====================================================================
# Bridge: default policy creation
# =====================================================================


class TestDefaultPolicy:
    def test_creates_valid_policy(self) -> None:
        policy = SupervisorBridge.create_default_policy(created_at=NOW)
        assert policy.tick_interval_ms == 1000
        assert policy.max_events_per_tick == 100
        assert policy.livelock_strategy == LivelockStrategy.ESCALATE

    def test_custom_overrides(self) -> None:
        policy = SupervisorBridge.create_default_policy(
            created_at=NOW,
            tick_interval_ms=500,
            livelock_strategy=LivelockStrategy.HALT,
        )
        assert policy.tick_interval_ms == 500
        assert policy.livelock_strategy == LivelockStrategy.HALT


# =====================================================================
# Bridge: run_n_ticks
# =====================================================================


class TestRunNTicks:
    def test_runs_exact_count(self) -> None:
        policy = SupervisorBridge.create_default_policy(created_at=NOW)
        spine = EventSpineEngine(clock=_clock)
        obl_engine = ObligationRuntimeEngine(clock=_clock)
        eng = SupervisorEngine(
            policy=policy, spine=spine, obligation_engine=obl_engine, clock=_clock,
        )
        ticks = SupervisorBridge.run_n_ticks(eng, 3)
        assert len(ticks) == 3

    def test_stops_on_halt(self) -> None:
        policy = SupervisorBridge.create_default_policy(
            created_at=NOW,
            livelock_repeat_threshold=2,
            livelock_strategy=LivelockStrategy.HALT,
        )
        spine = EventSpineEngine(clock=_clock)
        obl_engine = ObligationRuntimeEngine(clock=_clock)
        eng = SupervisorEngine(
            policy=policy, spine=spine, obligation_engine=obl_engine, clock=_clock,
        )
        ticks = SupervisorBridge.run_n_ticks(eng, 10, stop_on_halt=True)
        assert len(ticks) < 10
        assert ticks[-1].outcome in (TickOutcome.HALTED, TickOutcome.LIVELOCK_DETECTED)

    def test_stops_on_livelock(self) -> None:
        policy = SupervisorBridge.create_default_policy(
            created_at=NOW,
            livelock_repeat_threshold=2,
            livelock_strategy=LivelockStrategy.ESCALATE,
        )
        spine = EventSpineEngine(clock=_clock)
        obl_engine = ObligationRuntimeEngine(clock=_clock)
        eng = SupervisorEngine(
            policy=policy, spine=spine, obligation_engine=obl_engine, clock=_clock,
        )
        ticks = SupervisorBridge.run_n_ticks(eng, 10, stop_on_livelock=True)
        assert ticks[-1].outcome == TickOutcome.LIVELOCK_DETECTED


# =====================================================================
# Bridge: dashboard summary
# =====================================================================


class TestDashboardSummary:
    def test_summary_structure(self) -> None:
        policy = SupervisorBridge.create_default_policy(created_at=NOW)
        spine = EventSpineEngine(clock=_clock)
        obl_engine = ObligationRuntimeEngine(clock=_clock)
        eng = SupervisorEngine(
            policy=policy, spine=spine, obligation_engine=obl_engine, clock=_clock,
        )
        eng.tick()
        summary = SupervisorBridge.extract_dashboard_summary(eng)
        assert summary["tick_number"] == 1
        assert summary["is_halted"] is False
        assert "health" in summary
        assert "overall_confidence" in summary["health"]

    def test_summary_recent_outcomes(self) -> None:
        policy = SupervisorBridge.create_default_policy(created_at=NOW)
        spine = EventSpineEngine(clock=_clock)
        obl_engine = ObligationRuntimeEngine(clock=_clock)
        eng = SupervisorEngine(
            policy=policy, spine=spine, obligation_engine=obl_engine, clock=_clock,
        )
        eng.tick()
        eng.tick()
        summary = SupervisorBridge.extract_dashboard_summary(eng)
        assert len(summary["recent_outcomes"]) == 2


# =====================================================================
# Bridge: checkpoint validation and resume
# =====================================================================


class TestCheckpointResume:
    def test_validate_valid_checkpoint(self) -> None:
        from mcoi_runtime.contracts.supervisor import (
            CheckpointStatus,
            SupervisorCheckpoint,
            SupervisorPhase,
        )

        cp = SupervisorCheckpoint(
            checkpoint_id="cp1",
            tick_number=5,
            phase=SupervisorPhase.IDLE,
            status=CheckpointStatus.VALID,
            open_obligation_ids=(),
            pending_event_count=0,
            consecutive_errors=0,
            consecutive_idle_ticks=0,
            recent_tick_outcomes=(),
            state_hash="hash",
            created_at=NOW,
        )
        assert SupervisorBridge.validate_checkpoint(cp) is True

    def test_validate_stale_checkpoint(self) -> None:
        from mcoi_runtime.contracts.supervisor import (
            CheckpointStatus,
            SupervisorCheckpoint,
            SupervisorPhase,
        )

        cp = SupervisorCheckpoint(
            checkpoint_id="cp1",
            tick_number=5,
            phase=SupervisorPhase.IDLE,
            status=CheckpointStatus.STALE,
            open_obligation_ids=(),
            pending_event_count=0,
            consecutive_errors=0,
            consecutive_idle_ticks=0,
            recent_tick_outcomes=(),
            state_hash="hash",
            created_at=NOW,
        )
        assert SupervisorBridge.validate_checkpoint(cp) is False


# =====================================================================
# Golden scenario: full operational loop
# =====================================================================


class TestFullOperationalLoop:
    """End-to-end: events arrive, obligations created, deadlines expire,
    reactions fire, heartbeats emitted, checkpoints taken."""

    def test_full_loop(self) -> None:
        policy = SupervisorBridge.create_default_policy(
            created_at=NOW,
            heartbeat_every_n_ticks=2,
            checkpoint_every_n_ticks=3,
            livelock_repeat_threshold=10,
        )
        spine = EventSpineEngine(clock=_clock)
        obl_engine = ObligationRuntimeEngine(clock=_clock)

        # Pre-populate: event, obligation with expired deadline, subscription
        spine.emit(_event("e1", EventType.CUSTOM))
        spine.subscribe(EventSubscription(
            subscription_id="sub1",
            event_type=EventType.CUSTOM,
            subscriber_id="test",
            reaction_id="rxn1",
            created_at=NOW,
        ))
        obl_engine.create_obligation(
            trigger=ObligationTrigger.CUSTOM,
            trigger_ref_id="ref-1",
            owner=_owner(),
            deadline=_deadline(due_at=PAST),
            description="expired obligation",
            correlation_id="corr-1",
        )

        eng = SupervisorEngine(
            policy=policy, spine=spine, obligation_engine=obl_engine, clock=_clock,
        )

        # Run 6 ticks
        ticks = SupervisorBridge.run_n_ticks(eng, 6)

        # First tick should do work (event + obligation)
        assert ticks[0].outcome == TickOutcome.WORK_DONE
        assert ticks[0].events_polled >= 1

        # Heartbeats at tick 2, 4, 6
        assert len(eng.heartbeat_history) >= 2

        # Checkpoint at tick 3, 6
        assert len(eng.checkpoint_history) >= 1

        # Obligation should have been expired
        all_obls = obl_engine.list_obligations()
        expired = [o for o in all_obls if o.state == ObligationState.EXPIRED]
        assert len(expired) >= 1

    def test_governance_gate_blocks_all_actions(self) -> None:
        """When governance blocks everything, decisions are recorded but not executed."""
        policy = SupervisorBridge.create_default_policy(
            created_at=NOW, livelock_repeat_threshold=10,
        )
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

        eng = SupervisorEngine(
            policy=policy,
            spine=spine,
            obligation_engine=obl_engine,
            clock=_clock,
            governance_gate=lambda *_: False,
        )
        tick = eng.tick()
        # Decisions recorded but not approved
        blocked = [d for d in tick.decisions if not d.governance_approved]
        assert len(blocked) > 0
        # Obligation still pending — not activated
        obl = list(obl_engine.list_obligations(state=ObligationState.PENDING))
        assert len(obl) == 1

    def test_multi_obligation_multi_event_tick(self) -> None:
        """Multiple obligations and events in a single tick."""
        policy = SupervisorBridge.create_default_policy(
            created_at=NOW, livelock_repeat_threshold=10,
        )
        spine = EventSpineEngine(clock=_clock)
        obl_engine = ObligationRuntimeEngine(clock=_clock)

        for i in range(3):
            spine.emit(_event(f"e{i}"))
            obl_engine.create_obligation(
                obligation_id=f"obl-{i}",
                trigger=ObligationTrigger.CUSTOM,
                trigger_ref_id=f"ref-{i}",
                owner=_owner(),
                deadline=_deadline(),
                description=f"obligation {i}",
                correlation_id=f"corr-{i}",
            )

        eng = SupervisorEngine(
            policy=policy, spine=spine, obligation_engine=obl_engine, clock=_clock,
        )
        tick = eng.tick()
        assert tick.events_polled == 3
        assert tick.obligations_evaluated >= 3
        assert tick.outcome == TickOutcome.WORK_DONE

    def test_resume_and_continue(self) -> None:
        """Checkpoint, create a new engine, resume, and keep ticking."""
        policy = SupervisorBridge.create_default_policy(
            created_at=NOW,
            checkpoint_every_n_ticks=1,
            livelock_repeat_threshold=10,
        )
        spine = EventSpineEngine(clock=_clock)
        obl_engine = ObligationRuntimeEngine(clock=_clock)

        eng = SupervisorEngine(
            policy=policy, spine=spine, obligation_engine=obl_engine, clock=_clock,
        )
        eng.tick()
        eng.tick()
        cp = eng.checkpoint_history[-1]

        new_eng = SupervisorEngine(
            policy=policy, spine=spine, obligation_engine=obl_engine, clock=_clock,
        )
        SupervisorBridge.resume_engine(new_eng, cp)
        assert new_eng.tick_number == cp.tick_number

        # Can continue ticking
        tick = new_eng.tick()
        assert tick.tick_number > cp.tick_number
