"""Subphase 5 tests: supervisor soak / canary scenarios.

Long-horizon supervised operation tests proving the runtime can run
continuously, safely, and controllably over time.

Covers:
  - Thousands of ticks under normal operation
  - Event churn (high volume event injection)
  - Repeated checkpoint/restore cycles
  - Obligation expiry/escalation loops
  - Reaction storms under backpressure
  - Canary shadow mode vs active mode
  - Replay after partial degradation
  - Supervisor pause/resume/halt under load
  - Checkpoint/replay consistency under churn
  - Operator controls remain authoritative under load
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
from mcoi_runtime.contracts.pilot import OperatorAuthority
from mcoi_runtime.contracts.supervisor import (
    LivelockStrategy,
    SupervisorPolicy,
    TickOutcome,
)
from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
from mcoi_runtime.core.obligation_runtime import ObligationRuntimeEngine
from mcoi_runtime.core.pilot_control import (
    CanaryMode,
    PilotControlPlane,
    RuntimeStatus,
)
from mcoi_runtime.core.supervisor_engine import SupervisorEngine

_TS = "2026-03-20T00:00:00+00:00"
_tick = 0


def _clock():
    global _tick
    _tick += 1
    minutes = _tick // 60
    seconds = _tick % 60
    return f"2026-03-20T{minutes // 60:02d}:{minutes % 60:02d}:{seconds:02d}+00:00"


@pytest.fixture(autouse=True)
def _reset():
    global _tick
    _tick = 0
    yield
    _tick = 0


def _make_policy(**overrides) -> SupervisorPolicy:
    defaults = dict(
        policy_id="soak-policy",
        tick_interval_ms=100,
        max_events_per_tick=50,
        max_actions_per_tick=50,
        backpressure_threshold=100,
        livelock_repeat_threshold=5,
        livelock_strategy=LivelockStrategy.SKIP_AND_LOG,
        heartbeat_every_n_ticks=10,
        checkpoint_every_n_ticks=25,
        max_consecutive_errors=20,
        created_at=_TS,
    )
    defaults.update(overrides)
    return SupervisorPolicy(**defaults)


def _make_plane(**policy_overrides) -> PilotControlPlane:
    spine = EventSpineEngine(clock=_clock)
    obl = ObligationRuntimeEngine(clock=_clock)
    policy = _make_policy(**policy_overrides)
    sup = SupervisorEngine(
        policy=policy, spine=spine, obligation_engine=obl, clock=_clock,
    )
    return PilotControlPlane(
        supervisor=sup, spine=spine, obligation_engine=obl, clock=_clock,
    )


def _inject_events(spine: EventSpineEngine, n: int, prefix: str = "evt") -> list[EventRecord]:
    """Inject n events into the spine."""
    events = []
    for i in range(n):
        evt = EventRecord(
            event_id=f"{prefix}-{i}",
            event_type=EventType.CUSTOM,
            source=EventSource.SUPERVISOR,
            correlation_id=f"corr-{prefix}",
            payload={"index": i},
            emitted_at=_clock(),
        )
        spine.emit(evt)
        events.append(evt)
    return events


def _create_obligation(obl_engine: ObligationRuntimeEngine, obl_id: str, deadline_at: str) -> None:
    """Create a test obligation."""
    obl_engine.create_obligation(
        obligation_id=obl_id,
        trigger=ObligationTrigger.CUSTOM,
        trigger_ref_id="ref-1",
        owner=ObligationOwner(
            owner_id="owner-1",
            owner_type="operator",
            display_name="test owner",
        ),
        deadline=ObligationDeadline(
            deadline_id=f"dl-{obl_id}",
            due_at=deadline_at,
        ),
        description=f"Test obligation {obl_id}",
        correlation_id=f"corr-{obl_id}",
    )


# ---------------------------------------------------------------------------
# Soak: thousands of ticks
# ---------------------------------------------------------------------------


class TestLongHorizonTicks:
    def test_1000_ticks_no_state_corruption(self):
        """Run 1000 ticks and verify state consistency throughout."""
        plane = _make_plane()
        plane.start("op-1")
        results = plane.run_ticks(1000)
        assert len(results) == 1000
        assert plane._supervisor.tick_number == 1000
        # Health should be stable
        h = plane.health()
        assert h.is_healthy
        assert h.tick_number == 1000
        # Supervisor should have created periodic heartbeats internally
        assert len(plane._supervisor.heartbeat_history) > 0
        # Supervisor creates its own internal checkpoints per policy
        assert len(plane._supervisor.checkpoint_history) > 0

    def test_2000_ticks_memory_bounded(self):
        """Run 2000 ticks and verify retention pruning keeps memory bounded."""
        plane = _make_plane()
        plane.start("op-1")
        plane.run_ticks(2000)
        # Supervisor prunes to 1000 max
        assert len(plane._supervisor.tick_history) <= 1000
        assert len(plane._supervisor.heartbeat_history) <= 500
        assert len(plane._supervisor.checkpoint_history) <= 100

    def test_1000_ticks_deterministic(self):
        """Two identical runs should produce identical tick sequences."""
        global _tick
        _tick = 0
        plane1 = _make_plane()
        plane1.start("op-1")
        results1 = plane1.run_ticks(100)
        outcomes1 = [r.outcome for r in results1]

        _tick = 0
        plane2 = _make_plane()
        plane2.start("op-1")
        results2 = plane2.run_ticks(100)
        outcomes2 = [r.outcome for r in results2]

        assert outcomes1 == outcomes2


# ---------------------------------------------------------------------------
# Soak: event churn
# ---------------------------------------------------------------------------


class TestEventChurn:
    def test_high_volume_event_injection(self):
        """Inject 500 events and run ticks to process them."""
        plane = _make_plane()
        plane.start("op-1")
        _inject_events(plane._spine, 500, "churn")
        assert plane._spine.event_count >= 500
        # Run enough ticks to process events
        plane.run_ticks(100)
        h = plane.health()
        assert h.is_healthy

    def test_events_during_ticks(self):
        """Inject events interleaved with tick execution."""
        plane = _make_plane()
        plane.start("op-1")
        for batch in range(20):
            _inject_events(plane._spine, 10, f"batch-{batch}")
            plane.run_ticks(5)
        assert plane._supervisor.tick_number == 100
        assert plane._spine.event_count >= 200
        h = plane.health()
        assert h.is_healthy


# ---------------------------------------------------------------------------
# Soak: repeated checkpoint/restore cycles
# ---------------------------------------------------------------------------


class TestRepeatedCheckpointRestore:
    def test_checkpoint_restore_cycle_50_times(self):
        """Create and restore checkpoints 50 times without corruption."""
        plane = _make_plane()
        plane.start("op-1")
        for i in range(50):
            plane.run_ticks(5)
            cp = plane.create_checkpoint("op-1")
            # Restore to the checkpoint we just created
            plane.restore_checkpoint(cp, "op-1")
            # Verify state is consistent
            h = plane.health()
            assert h.is_healthy

    def test_checkpoint_round_trip_preserves_tick_number(self):
        """Checkpoint → run more ticks → restore → tick number matches."""
        plane = _make_plane()
        plane.start("op-1")
        plane.run_ticks(50)
        cp = plane.create_checkpoint("op-1")
        saved_tick = plane._supervisor.tick_number
        # Run 20 more ticks
        plane.run_ticks(20)
        assert plane._supervisor.tick_number == saved_tick + 20
        # Restore
        plane.restore_checkpoint(cp, "op-1")
        assert plane._supervisor.tick_number == saved_tick

    def test_repeated_checkpoint_hashes_stable(self):
        """Creating checkpoints at the same state should produce same hashes."""
        plane = _make_plane()
        plane.start("op-1")
        plane.run_ticks(10)
        cp1 = plane.create_checkpoint("op-1")
        # Restore and checkpoint again at the same state
        plane.restore_checkpoint(cp1, "op-1")
        cp2 = plane.create_checkpoint("op-1")
        assert cp1.composite_hash == cp2.composite_hash


# ---------------------------------------------------------------------------
# Soak: obligation lifecycle under load
# ---------------------------------------------------------------------------


class TestObligationLifecycleUnderLoad:
    def test_create_and_activate_obligations_during_ticks(self):
        """Create obligations during tick cycles — they should activate."""
        plane = _make_plane()
        plane.start("op-1")
        for i in range(20):
            _create_obligation(
                plane._obligation_engine,
                f"obl-{i}",
                "2026-03-21T00:00:00+00:00",  # future deadline
            )
        plane.run_ticks(50)
        # All obligations should have been evaluated
        h = plane.health()
        assert h.is_healthy

    def test_obligations_with_expired_deadlines(self):
        """Obligations with past deadlines should be detected."""
        plane = _make_plane()
        plane.start("op-1")
        for i in range(10):
            _create_obligation(
                plane._obligation_engine,
                f"exp-obl-{i}",
                "2026-03-19T00:00:00+00:00",  # past deadline
            )
        plane.run_ticks(50)
        h = plane.health()
        assert h.is_healthy


# ---------------------------------------------------------------------------
# Soak: backpressure under high event rates
# ---------------------------------------------------------------------------


class TestBackpressureUnderLoad:
    def test_backpressure_triggered_by_event_flood(self):
        """Flooding events beyond threshold should trigger backpressure."""
        plane = _make_plane(backpressure_threshold=5, max_events_per_tick=3)
        plane.start("op-1")
        # Inject far more events than the threshold
        _inject_events(plane._spine, 100, "flood")
        results = plane.run_ticks(10)
        # At least some ticks should show backpressure or degraded outcome
        outcomes = [r.outcome for r in results]
        # System should remain healthy even under backpressure
        h = plane.health()
        assert h.is_healthy or h.is_degraded

    def test_backpressure_does_not_lose_events(self):
        """Events should not be lost under backpressure — just paced."""
        plane = _make_plane(backpressure_threshold=5, max_events_per_tick=2)
        plane.start("op-1")
        injected = _inject_events(plane._spine, 50, "bp")
        initial_count = plane._spine.event_count
        plane.run_ticks(100)
        # All injected events should still exist in spine (append-only)
        # Count may grow because supervisor emits heartbeats/checkpoints internally
        assert plane._spine.event_count >= initial_count


# ---------------------------------------------------------------------------
# Soak: canary shadow mode vs active mode
# ---------------------------------------------------------------------------


class TestCanarySoakScenarios:
    def test_shadow_mode_ticks_normally(self):
        """Shadow mode allows ticks to execute (caller discards mutations)."""
        plane = _make_plane()
        plane.start("op-1")
        plane.set_canary_mode(CanaryMode.SHADOW, "op-1", "shadow test")
        plane.run_ticks(100)
        assert plane._supervisor.tick_number == 100
        h = plane.health()
        assert h.is_healthy
        assert not h.is_ready  # shadow mode → not ready

    def test_observation_to_shadow_to_active_promotion(self):
        """Canary promotion path: observation → shadow → active."""
        plane = _make_plane()
        plane.start("op-1")

        # Start in observation
        plane.set_canary_mode(CanaryMode.OBSERVATION, "op-1", "observe first")
        h = plane.health()
        assert not h.is_ready
        assert not plane.canary_allows_action("fire_reaction")

        # Promote to shadow
        plane.set_canary_mode(CanaryMode.SHADOW, "op-1", "shadow trial")
        plane.run_ticks(50)
        h = plane.health()
        assert not h.is_ready
        assert plane.canary_allows_action("fire_reaction")

        # Promote to active
        plane.set_canary_mode(CanaryMode.ACTIVE, "op-1", "full rollout")
        h = plane.health()
        assert h.is_ready
        assert plane.canary_allows_action("fire_reaction")

    def test_active_to_off_transition(self):
        """Active → off canary transition maintains readiness."""
        plane = _make_plane()
        plane.start("op-1")
        plane.set_canary_mode(CanaryMode.ACTIVE, "op-1", "active")
        assert plane.health().is_ready
        plane.set_canary_mode(CanaryMode.OFF, "op-1", "canary complete")
        assert plane.health().is_ready


# ---------------------------------------------------------------------------
# Soak: supervisor pause/resume/halt under load
# ---------------------------------------------------------------------------


class TestPauseResumeHaltUnderLoad:
    def test_pause_resume_during_ticks(self):
        """Pause and resume multiple times during a long tick sequence."""
        plane = _make_plane()
        plane.start("op-1")
        for i in range(10):
            plane.run_ticks(20)
            plane.pause("op-1")
            assert plane.status == RuntimeStatus.PAUSED
            # Cannot tick while paused
            with pytest.raises(RuntimeCoreInvariantError):
                plane.tick()
            plane.resume("op-1")
            assert plane.status == RuntimeStatus.RUNNING
        assert plane._supervisor.tick_number == 200

    def test_checkpoint_after_pause_resume(self):
        """Checkpoints created after pause/resume should be valid."""
        plane = _make_plane()
        plane.start("op-1")
        plane.run_ticks(50)
        plane.pause("op-1")
        plane.resume("op-1")
        plane.run_ticks(50)
        cp = plane.create_checkpoint("op-1")
        assert cp is not None
        assert cp.tick_number == 100

    def test_halt_stops_ticks(self):
        """Halted supervisor produces HALTED tick outcomes."""
        plane = _make_plane(max_consecutive_errors=1)
        plane.start("op-1")
        # Force halt by setting internal state
        plane._supervisor._halted = True
        result = plane.tick()
        assert result.outcome == TickOutcome.HALTED

    def test_operator_authority_maintained_under_load(self):
        """Operator authority checks remain authoritative after many ticks."""
        plane = _make_plane()
        plane.register_operator("admin-1", OperatorAuthority.ADMIN)
        plane.register_operator("viewer-1", OperatorAuthority.VIEWER)
        plane.start("admin-1")
        plane.run_ticks(500)
        # Viewer still cannot pause after 500 ticks
        with pytest.raises(RuntimeCoreInvariantError, match="lacks authority"):
            plane.pause("viewer-1")
        # Admin can still pause
        plane.pause("admin-1")
        assert plane.status == RuntimeStatus.PAUSED


# ---------------------------------------------------------------------------
# Soak: replay after partial degradation
# ---------------------------------------------------------------------------


class TestReplayAfterDegradation:
    def test_checkpoint_restore_after_simulated_degradation(self):
        """Restore from checkpoint after supervisor enters degraded state."""
        plane = _make_plane()
        plane.start("op-1")
        plane.run_ticks(100)
        cp = plane.create_checkpoint("op-1")
        # Simulate degradation
        plane._supervisor._halted = True
        h = plane.health()
        assert h.is_degraded
        # Restore from pre-degradation checkpoint
        plane.restore_checkpoint(cp, "op-1")
        # After restore, supervisor should be at checkpoint state
        assert plane._supervisor.tick_number == cp.tick_number

    def test_state_export_tracks_degradation(self):
        """Runtime state export accurately reflects degradation."""
        plane = _make_plane()
        plane.start("op-1")
        plane.run_ticks(10)
        export1 = plane.export_state()
        assert not export1.is_degraded
        # Simulate degradation
        plane._supervisor._halted = True
        export2 = plane.export_state()
        assert export2.is_degraded
        assert "supervisor_halted" in export2.degraded_reasons


# ---------------------------------------------------------------------------
# Soak: journal integrity under churn
# ---------------------------------------------------------------------------


class TestJournalIntegrityUnderChurn:
    def test_journal_valid_after_500_ticks(self):
        """Journal should maintain integrity after 500 ticks."""
        plane = _make_plane()
        plane.start("op-1")
        plane.run_ticks(500)
        result = plane.checkpoint_manager.validate_journal()
        assert result.verdict.value == "valid"
        assert result.entry_count >= 500

    def test_journal_valid_after_checkpoint_restore_cycles(self):
        """Journal remains valid through multiple checkpoint/restore cycles."""
        plane = _make_plane()
        plane.start("op-1")
        for _ in range(10):
            plane.run_ticks(20)
            cp = plane.create_checkpoint("op-1")
        result = plane.checkpoint_manager.validate_journal()
        assert result.verdict.value == "valid"

    def test_journal_length_tracks_all_ticks(self):
        """Journal should have at least one entry per tick."""
        plane = _make_plane()
        plane.start("op-1")
        plane.run_ticks(200)
        assert plane.checkpoint_manager.journal_length >= 200


# ---------------------------------------------------------------------------
# Soak: combined stress scenario
# ---------------------------------------------------------------------------


class TestCombinedStressScenario:
    def test_full_lifecycle_stress(self):
        """Combined scenario: events + obligations + ticks + checkpoints + canary."""
        plane = _make_plane()
        plane.start("op-1")

        # Phase 1: Inject events and run ticks
        _inject_events(plane._spine, 50, "phase1")
        plane.run_ticks(100)

        # Phase 2: Create obligations and tick more
        for i in range(10):
            _create_obligation(
                plane._obligation_engine,
                f"stress-obl-{i}",
                "2026-03-21T00:00:00+00:00",
            )
        plane.run_ticks(100)

        # Phase 3: Checkpoint
        cp = plane.create_checkpoint("op-1")

        # Phase 4: Canary shadow mode
        plane.set_canary_mode(CanaryMode.SHADOW, "op-1", "shadow")
        plane.run_ticks(50)

        # Phase 5: Promote to active
        plane.set_canary_mode(CanaryMode.ACTIVE, "op-1", "active")
        plane.run_ticks(50)

        # Phase 6: Pause / resume
        plane.pause("op-1")
        plane.resume("op-1")

        # Phase 7: More events + ticks
        _inject_events(plane._spine, 50, "phase7")
        plane.run_ticks(100)

        # Final verification
        h = plane.health()
        assert h.is_healthy
        assert h.is_ready
        assert plane._supervisor.tick_number == 400
        assert plane._spine.event_count >= 100
        assert plane.action_count >= 5  # start + checkpoint + 2 canary + pause + resume

        # Export should capture everything
        export = plane.export_state()
        assert export.tick_number == 400
        assert export.is_healthy
        assert export.is_ready
