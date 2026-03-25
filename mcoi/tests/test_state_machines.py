"""Tests for state machine formalization, transition enforcement,
checkpoint journal, composite checkpoints, snapshot/restore,
long-run deterministic supervisor, and pilot control plane."""

from __future__ import annotations

import pytest
from types import MappingProxyType

from mcoi_runtime.contracts.event import EventRecord, EventSource, EventType
from mcoi_runtime.contracts.obligation import (
    ObligationDeadline,
    ObligationOwner,
    ObligationState,
    ObligationTrigger,
)
from mcoi_runtime.contracts.state_machine import (
    CheckpointScope,
    CompositeCheckpoint,
    JournalEntry,
    JournalEntryKind,
    StateMachineSpec,
    SubsystemSnapshot,
    TransitionAuditRecord,
    TransitionRule,
    TransitionVerdict,
)
from mcoi_runtime.contracts.supervisor import (
    LivelockStrategy,
    SupervisorPolicy,
    TickOutcome,
)
from mcoi_runtime.core.checkpoint_manager import CheckpointManager
from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
from mcoi_runtime.core.obligation_runtime import ObligationRuntimeEngine
from mcoi_runtime.core.pilot_control import (
    CanaryMode,
    HealthReport,
    OperatorAction,
    PilotControlPlane,
    RuntimeStatus,
)
from mcoi_runtime.core.state_machines import (
    MACHINE_REGISTRY,
    OBLIGATION_MACHINE,
    REACTION_PIPELINE_MACHINE,
    SUPERVISOR_MACHINE,
    enforce_transition,
)
from mcoi_runtime.core.supervisor_engine import SupervisorEngine

NOW = "2026-03-20T12:00:00+00:00"
CLOCK = lambda: NOW  # noqa: E731


# =====================================================================
# StateMachineSpec contract tests
# =====================================================================


class TestStateMachineSpec:
    def test_obligation_machine_structure(self) -> None:
        m = OBLIGATION_MACHINE
        assert m.machine_id == "obligation-lifecycle"
        assert m.initial_state == "pending"
        assert "completed" in m.terminal_states
        assert "expired" in m.terminal_states
        assert "cancelled" in m.terminal_states
        assert m.transition_count > 0

    def test_supervisor_machine_structure(self) -> None:
        m = SUPERVISOR_MACHINE
        assert m.machine_id == "supervisor-tick-lifecycle"
        assert m.initial_state == "idle"
        assert "halted" in m.terminal_states

    def test_reaction_machine_structure(self) -> None:
        m = REACTION_PIPELINE_MACHINE
        assert m.machine_id == "reaction-pipeline"
        assert m.initial_state == "received"
        assert "recorded" in m.terminal_states

    def test_registry_has_all_machines(self) -> None:
        assert len(MACHINE_REGISTRY) == 4
        assert "obligation-lifecycle" in MACHINE_REGISTRY
        assert "supervisor-tick-lifecycle" in MACHINE_REGISTRY
        assert "reaction-pipeline" in MACHINE_REGISTRY
        assert "checkpoint-lifecycle" in MACHINE_REGISTRY


class TestTransitionLegality:
    def test_obligation_legal_activate(self) -> None:
        v = OBLIGATION_MACHINE.is_legal("pending", "active", "activate")
        assert v == TransitionVerdict.ALLOWED

    def test_obligation_legal_close(self) -> None:
        v = OBLIGATION_MACHINE.is_legal("active", "completed", "close")
        assert v == TransitionVerdict.ALLOWED

    def test_obligation_legal_escalate(self) -> None:
        v = OBLIGATION_MACHINE.is_legal("pending", "escalated", "escalate")
        assert v == TransitionVerdict.ALLOWED

    def test_obligation_legal_transfer(self) -> None:
        v = OBLIGATION_MACHINE.is_legal("active", "active", "transfer")
        assert v == TransitionVerdict.ALLOWED

    def test_obligation_illegal_activate_from_active(self) -> None:
        v = OBLIGATION_MACHINE.is_legal("active", "pending", "activate")
        assert v == TransitionVerdict.DENIED_ILLEGAL_EDGE

    def test_obligation_terminal_completed(self) -> None:
        v = OBLIGATION_MACHINE.is_legal("completed", "active", "activate")
        assert v == TransitionVerdict.DENIED_TERMINAL_STATE

    def test_obligation_terminal_expired(self) -> None:
        v = OBLIGATION_MACHINE.is_legal("expired", "pending", "reset")
        assert v == TransitionVerdict.DENIED_TERMINAL_STATE

    def test_supervisor_legal_tick_start(self) -> None:
        v = SUPERVISOR_MACHINE.is_legal("idle", "polling", "tick_start")
        assert v == TransitionVerdict.ALLOWED

    def test_supervisor_halted_terminal(self) -> None:
        v = SUPERVISOR_MACHINE.is_legal("halted", "idle", "tick_start")
        assert v == TransitionVerdict.DENIED_TERMINAL_STATE

    def test_reaction_legal_begin(self) -> None:
        v = REACTION_PIPELINE_MACHINE.is_legal("received", "matching", "begin_react")
        assert v == TransitionVerdict.ALLOWED

    def test_reaction_legal_proceed(self) -> None:
        v = REACTION_PIPELINE_MACHINE.is_legal("gating", "executed", "verdict_proceed")
        assert v == TransitionVerdict.ALLOWED


class TestTransitionQueries:
    def test_legal_actions_from_pending(self) -> None:
        actions = OBLIGATION_MACHINE.legal_actions("pending")
        action_names = {a.action for a in actions}
        assert "activate" in action_names
        assert "close" in action_names
        assert "escalate" in action_names
        assert "transfer" in action_names

    def test_legal_actions_from_terminal(self) -> None:
        actions = OBLIGATION_MACHINE.legal_actions("completed")
        assert len(actions) == 0

    def test_reachable_from_active(self) -> None:
        reachable = OBLIGATION_MACHINE.reachable_from("active")
        assert "completed" in reachable
        assert "escalated" in reachable
        assert "pending" not in reachable


class TestEnforceTransition:
    def test_enforce_legal_passes(self) -> None:
        v = enforce_transition(OBLIGATION_MACHINE, "pending", "active", "activate")
        assert v == TransitionVerdict.ALLOWED

    def test_enforce_illegal_raises(self) -> None:
        with pytest.raises(RuntimeCoreInvariantError, match="illegal transition"):
            enforce_transition(OBLIGATION_MACHINE, "active", "pending", "activate")

    def test_enforce_terminal_raises(self) -> None:
        with pytest.raises(RuntimeCoreInvariantError, match="illegal transition"):
            enforce_transition(OBLIGATION_MACHINE, "completed", "active", "activate")


class TestTerminalInvariant:
    """Terminal states must have zero outgoing transitions."""

    def test_obligation_terminal_no_outgoing(self) -> None:
        for ts in OBLIGATION_MACHINE.terminal_states:
            assert len(OBLIGATION_MACHINE.legal_actions(ts)) == 0

    def test_supervisor_terminal_no_outgoing(self) -> None:
        for ts in SUPERVISOR_MACHINE.terminal_states:
            assert len(SUPERVISOR_MACHINE.legal_actions(ts)) == 0

    def test_reaction_terminal_no_outgoing(self) -> None:
        for ts in REACTION_PIPELINE_MACHINE.terminal_states:
            assert len(REACTION_PIPELINE_MACHINE.legal_actions(ts)) == 0

    def test_spec_rejects_terminal_with_outgoing(self) -> None:
        with pytest.raises(ValueError, match="terminal state.*outgoing"):
            StateMachineSpec(
                machine_id="bad",
                name="Bad Machine",
                version="1.0.0",
                states=("a", "b"),
                initial_state="a",
                terminal_states=("b",),
                transitions=(
                    TransitionRule(from_state="a", to_state="b", action="go"),
                    TransitionRule(from_state="b", to_state="a", action="illegal"),
                ),
            )


# =====================================================================
# TransitionAuditRecord tests
# =====================================================================


class TestTransitionAuditRecord:
    def test_valid_record(self) -> None:
        rec = TransitionAuditRecord(
            audit_id="a-1",
            machine_id="obligation-lifecycle",
            entity_id="obl-1",
            from_state="pending",
            to_state="active",
            action="activate",
            verdict=TransitionVerdict.ALLOWED,
            actor_id="supervisor",
            reason="deadline approaching",
            transitioned_at=NOW,
        )
        assert rec.succeeded is True

    def test_failed_record(self) -> None:
        rec = TransitionAuditRecord(
            audit_id="a-2",
            machine_id="obligation-lifecycle",
            entity_id="obl-1",
            from_state="completed",
            to_state="active",
            action="activate",
            verdict=TransitionVerdict.DENIED_TERMINAL_STATE,
            actor_id="supervisor",
            reason="attempted reactivation",
            transitioned_at=NOW,
        )
        assert rec.succeeded is False


# =====================================================================
# Journal entry tests
# =====================================================================


class TestJournalEntry:
    def test_valid_entry(self) -> None:
        entry = JournalEntry(
            entry_id="j-1",
            epoch_id="epoch-1",
            sequence=0,
            kind=JournalEntryKind.TICK,
            subject_id="supervisor",
            payload={"tick": 1, "outcome": "work_done"},
            recorded_at=NOW,
        )
        assert entry.sequence == 0
        assert entry.kind == JournalEntryKind.TICK

    def test_all_journal_kinds(self) -> None:
        for kind in JournalEntryKind:
            entry = JournalEntry(
                entry_id=f"j-{kind.value}",
                epoch_id="epoch-1",
                sequence=0,
                kind=kind,
                subject_id="test",
                payload={},
                recorded_at=NOW,
            )
            assert entry.kind == kind


# =====================================================================
# SubsystemSnapshot and CompositeCheckpoint tests
# =====================================================================


class TestSubsystemSnapshot:
    def test_valid_snapshot(self) -> None:
        snap = SubsystemSnapshot(
            snapshot_id="snap-1",
            scope=CheckpointScope.EVENT_SPINE,
            state_hash="abc123",
            record_count=42,
            captured_at=NOW,
        )
        assert snap.scope == CheckpointScope.EVENT_SPINE

    def test_all_scopes(self) -> None:
        for scope in CheckpointScope:
            snap = SubsystemSnapshot(
                snapshot_id=f"snap-{scope.value}",
                scope=scope,
                state_hash="hash",
                record_count=0,
                captured_at=NOW,
            )
            assert snap.scope == scope


class TestCompositeCheckpoint:
    def test_valid_checkpoint(self) -> None:
        cp = CompositeCheckpoint(
            checkpoint_id="cp-1",
            epoch_id="epoch-1",
            tick_number=10,
            snapshots=(
                SubsystemSnapshot(snapshot_id="s1", scope=CheckpointScope.SUPERVISOR,
                                  state_hash="h1", record_count=10, captured_at=NOW),
                SubsystemSnapshot(snapshot_id="s2", scope=CheckpointScope.EVENT_SPINE,
                                  state_hash="h2", record_count=100, captured_at=NOW),
            ),
            journal_sequence=50,
            composite_hash="composite",
            created_at=NOW,
        )
        assert cp.tick_number == 10
        assert cp.scope_names == ("supervisor", "event_spine")

    def test_snapshot_for(self) -> None:
        cp = CompositeCheckpoint(
            checkpoint_id="cp-1",
            epoch_id="epoch-1",
            tick_number=1,
            snapshots=(
                SubsystemSnapshot(snapshot_id="s1", scope=CheckpointScope.SUPERVISOR,
                                  state_hash="h1", record_count=0, captured_at=NOW),
            ),
            journal_sequence=0,
            composite_hash="h",
            created_at=NOW,
        )
        assert cp.snapshot_for(CheckpointScope.SUPERVISOR) is not None
        assert cp.snapshot_for(CheckpointScope.EVENT_SPINE) is None

    def test_duplicate_scopes_rejected(self) -> None:
        with pytest.raises(ValueError, match="duplicate scopes"):
            CompositeCheckpoint(
                checkpoint_id="cp-1",
                epoch_id="epoch-1",
                tick_number=1,
                snapshots=(
                    SubsystemSnapshot(snapshot_id="s1", scope=CheckpointScope.SUPERVISOR,
                                      state_hash="h1", record_count=0, captured_at=NOW),
                    SubsystemSnapshot(snapshot_id="s2", scope=CheckpointScope.SUPERVISOR,
                                      state_hash="h2", record_count=0, captured_at=NOW),
                ),
                journal_sequence=0,
                composite_hash="h",
                created_at=NOW,
            )


# =====================================================================
# EventSpine snapshot/restore tests
# =====================================================================


class TestEventSpineSnapshot:
    def test_snapshot_and_restore(self) -> None:
        spine = EventSpineEngine(clock=CLOCK)
        evt = EventRecord(
            event_id="e1", event_type=EventType.CUSTOM,
            source=EventSource.SUPERVISOR, correlation_id="cor-1",
            payload={"key": "value"}, emitted_at=NOW,
        )
        spine.emit(evt)
        assert spine.event_count == 1

        snap = spine.snapshot()
        assert "events" in snap
        assert "state_hash" in snap

        # Restore into a fresh spine
        spine2 = EventSpineEngine(clock=CLOCK)
        spine2.restore(snap)
        assert spine2.event_count == 1
        restored = spine2.get_event("e1")
        assert restored is not None
        assert restored.event_id == "e1"

    def test_state_hash_deterministic(self) -> None:
        spine = EventSpineEngine(clock=CLOCK)
        h1 = spine.state_hash()
        h2 = spine.state_hash()
        assert h1 == h2

    def test_state_hash_changes_on_emit(self) -> None:
        spine = EventSpineEngine(clock=CLOCK)
        h1 = spine.state_hash()
        spine.emit(EventRecord(
            event_id="e1", event_type=EventType.CUSTOM,
            source=EventSource.SUPERVISOR, correlation_id="cor-1",
            payload={}, emitted_at=NOW,
        ))
        h2 = spine.state_hash()
        assert h1 != h2


# =====================================================================
# ObligationRuntime snapshot/restore tests
# =====================================================================


def _owner(oid: str = "o1") -> ObligationOwner:
    return ObligationOwner(owner_id=oid, owner_type="human", display_name="Test")


def _deadline() -> ObligationDeadline:
    return ObligationDeadline(deadline_id="dl-1", due_at="2027-01-01T00:00:00+00:00")


class TestObligationSnapshot:
    def test_snapshot_and_restore(self) -> None:
        eng = ObligationRuntimeEngine(clock=CLOCK)
        obl = eng.create_obligation(
            trigger=ObligationTrigger.CUSTOM,
            trigger_ref_id="ref-1",
            owner=_owner(),
            deadline=_deadline(),
            description="test obligation",
            correlation_id="cor-1",
        )
        eng.activate(obl.obligation_id)
        assert eng.obligation_count == 1

        snap = eng.snapshot()
        assert "obligations" in snap
        assert "state_hash" in snap

        eng2 = ObligationRuntimeEngine(clock=CLOCK)
        eng2.restore(snap)
        assert eng2.obligation_count == 1
        restored = eng2.get_obligation(obl.obligation_id)
        assert restored is not None
        assert restored.state == ObligationState.ACTIVE

    def test_state_hash_deterministic(self) -> None:
        eng = ObligationRuntimeEngine(clock=CLOCK)
        h1 = eng.state_hash()
        h2 = eng.state_hash()
        assert h1 == h2

    def test_state_hash_changes_on_transition(self) -> None:
        eng = ObligationRuntimeEngine(clock=CLOCK)
        h1 = eng.state_hash()
        eng.create_obligation(
            trigger=ObligationTrigger.CUSTOM,
            trigger_ref_id="ref-1",
            owner=_owner(), deadline=_deadline(),
            description="test",
            correlation_id="cor-1",
        )
        h2 = eng.state_hash()
        assert h1 != h2


# =====================================================================
# CheckpointManager tests
# =====================================================================


def _policy(**overrides) -> SupervisorPolicy:
    defaults = dict(
        policy_id="test-policy",
        tick_interval_ms=100,
        max_events_per_tick=10,
        max_actions_per_tick=10,
        backpressure_threshold=50,
        livelock_repeat_threshold=5,
        livelock_strategy=LivelockStrategy.ESCALATE,
        heartbeat_every_n_ticks=100,
        checkpoint_every_n_ticks=100,
        max_consecutive_errors=5,
        created_at=NOW,
    )
    defaults.update(overrides)
    return SupervisorPolicy(**defaults)


def _full_stack():
    spine = EventSpineEngine(clock=CLOCK)
    obl = ObligationRuntimeEngine(clock=CLOCK)
    sup = SupervisorEngine(
        policy=_policy(), spine=spine, obligation_engine=obl, clock=CLOCK,
    )
    return sup, spine, obl


class TestCheckpointManager:
    def test_create_checkpoint(self) -> None:
        sup, spine, obl = _full_stack()
        mgr = CheckpointManager(
            supervisor=sup, spine=spine, obligation_engine=obl,
            clock=CLOCK,
        )
        cp = mgr.create_checkpoint()
        assert cp.tick_number == 0
        assert len(cp.snapshots) == 3
        assert cp.snapshot_for(CheckpointScope.SUPERVISOR) is not None
        assert cp.snapshot_for(CheckpointScope.EVENT_SPINE) is not None
        assert cp.snapshot_for(CheckpointScope.OBLIGATION_RUNTIME) is not None

    def test_journal_appended_on_checkpoint(self) -> None:
        sup, spine, obl = _full_stack()
        mgr = CheckpointManager(
            supervisor=sup, spine=spine, obligation_engine=obl,
            clock=CLOCK,
        )
        assert mgr.journal_length == 0
        mgr.create_checkpoint()
        assert mgr.journal_length == 1
        entry = mgr.journal_since(0)[0]
        assert entry.kind == JournalEntryKind.CHECKPOINT

    def test_restore_from_checkpoint(self) -> None:
        sup, spine, obl = _full_stack()
        # Add some state
        spine.emit(EventRecord(
            event_id="e1", event_type=EventType.CUSTOM,
            source=EventSource.SUPERVISOR, correlation_id="cor-1",
            payload={}, emitted_at=NOW,
        ))
        obl.create_obligation(
            trigger=ObligationTrigger.CUSTOM,
            trigger_ref_id="ref-1",
            owner=_owner(), deadline=_deadline(),
            description="test",
            correlation_id="cor-1",
        )

        mgr = CheckpointManager(
            supervisor=sup, spine=spine, obligation_engine=obl,
            clock=CLOCK,
        )
        cp = mgr.create_checkpoint()

        # Clear state
        spine2 = EventSpineEngine(clock=CLOCK)
        obl2 = ObligationRuntimeEngine(clock=CLOCK)
        sup2 = SupervisorEngine(
            policy=_policy(), spine=spine2, obligation_engine=obl2, clock=CLOCK,
        )
        mgr2 = CheckpointManager(
            supervisor=sup2, spine=spine2, obligation_engine=obl2,
            clock=CLOCK,
        )
        mgr2.restore_checkpoint(cp)
        assert spine2.event_count == 1
        assert obl2.obligation_count == 1


# =====================================================================
# PilotControlPlane tests
# =====================================================================


def _pilot():
    sup, spine, obl = _full_stack()
    pilot = PilotControlPlane(
        supervisor=sup, spine=spine, obligation_engine=obl, clock=CLOCK,
    )
    return pilot


class TestPilotLifecycle:
    def test_start_stop(self) -> None:
        pilot = _pilot()
        assert pilot.status == RuntimeStatus.STOPPED

        pilot.start("op-1")
        assert pilot.status == RuntimeStatus.RUNNING

        pilot.stop("op-1")
        assert pilot.status == RuntimeStatus.STOPPED

    def test_pause_resume(self) -> None:
        pilot = _pilot()
        pilot.start("op-1")
        pilot.pause("op-1")
        assert pilot.status == RuntimeStatus.PAUSED

        pilot.resume("op-1")
        assert pilot.status == RuntimeStatus.RUNNING

    def test_cannot_start_when_running(self) -> None:
        pilot = _pilot()
        pilot.start("op-1")
        with pytest.raises(RuntimeCoreInvariantError, match="cannot start"):
            pilot.start("op-1")

    def test_cannot_pause_when_stopped(self) -> None:
        pilot = _pilot()
        with pytest.raises(RuntimeCoreInvariantError, match="cannot pause"):
            pilot.pause("op-1")

    def test_cannot_resume_when_running(self) -> None:
        pilot = _pilot()
        pilot.start("op-1")
        with pytest.raises(RuntimeCoreInvariantError, match="cannot resume"):
            pilot.resume("op-1")

    def test_cannot_tick_when_paused(self) -> None:
        pilot = _pilot()
        pilot.start("op-1")
        pilot.pause("op-1")
        with pytest.raises(RuntimeCoreInvariantError, match="cannot tick"):
            pilot.tick()


class TestPilotTicking:
    def test_tick_produces_result(self) -> None:
        pilot = _pilot()
        pilot.start("op-1")
        result = pilot.tick()
        assert result.outcome == TickOutcome.IDLE_TICK

    def test_run_n_ticks(self) -> None:
        pilot = _pilot()
        pilot.start("op-1")
        results = pilot.run_ticks(5)
        assert len(results) == 5


class TestPilotCheckpoint:
    def test_create_and_export_checkpoint(self) -> None:
        pilot = _pilot()
        pilot.start("op-1")
        pilot.tick()
        cp = pilot.create_checkpoint("op-1")
        assert cp.tick_number == 1

        exported = pilot.export_checkpoint()
        assert exported is not None
        assert "checkpoint_id" in exported


class TestPilotHealth:
    def test_health_when_running(self) -> None:
        pilot = _pilot()
        pilot.start("op-1")
        h = pilot.health()
        assert h.is_healthy is True
        assert h.is_ready is True
        assert h.status == RuntimeStatus.RUNNING

    def test_health_when_stopped(self) -> None:
        pilot = _pilot()
        h = pilot.health()
        assert h.is_healthy is False
        assert h.is_ready is False
        assert h.status == RuntimeStatus.STOPPED

    def test_health_when_paused(self) -> None:
        pilot = _pilot()
        pilot.start("op-1")
        pilot.pause("op-1")
        h = pilot.health()
        assert h.is_healthy is True
        assert h.is_ready is False


class TestPilotCanary:
    def test_set_canary_mode(self) -> None:
        pilot = _pilot()
        pilot.set_canary_mode(CanaryMode.OBSERVATION, "op-1", "testing canary")
        assert pilot.canary_mode == CanaryMode.OBSERVATION

    def test_canary_modes(self) -> None:
        pilot = _pilot()
        for mode in CanaryMode:
            pilot.set_canary_mode(mode, "op-1", f"setting {mode.value}")
            assert pilot.canary_mode == mode


class TestPilotAuditTrail:
    def test_actions_recorded(self) -> None:
        pilot = _pilot()
        pilot.start("op-1", "initial start")
        pilot.pause("op-1", "maintenance")
        pilot.resume("op-1", "maintenance complete")
        pilot.stop("op-1", "end of shift")
        assert pilot.action_count == 4
        actions = pilot.list_actions()
        assert actions[0].action == "start"
        assert actions[1].action == "pause"
        assert actions[2].action == "resume"
        assert actions[3].action == "stop"


# =====================================================================
# Long-run deterministic supervisor test
# =====================================================================


class TestLongRunDeterminism:
    """Verify supervisor tick behavior is deterministic over many ticks."""

    def test_50_idle_ticks_deterministic(self) -> None:
        """Run 50 ticks with no events — verify deterministic behavior."""
        sup, spine, obl = _full_stack()
        # Use high livelock threshold to prevent livelock detection
        sup2 = SupervisorEngine(
            policy=_policy(livelock_repeat_threshold=100),
            spine=spine, obligation_engine=obl, clock=CLOCK,
        )
        pilot = PilotControlPlane(
            supervisor=sup2, spine=spine, obligation_engine=obl, clock=CLOCK,
        )
        pilot.start("op-1")
        results = pilot.run_ticks(50)
        outcomes = [r.outcome for r in results]
        # All idle ticks
        assert all(o == TickOutcome.IDLE_TICK for o in outcomes)
        # Tick numbers are sequential
        ticks = [r.tick_number for r in results]
        assert ticks == list(range(1, 51))

    def test_50_ticks_with_events(self) -> None:
        """Run 50 ticks injecting events — verify work_done outcomes."""
        sup, spine, obl = _full_stack()
        pilot = PilotControlPlane(
            supervisor=sup, spine=spine, obligation_engine=obl, clock=CLOCK,
        )
        pilot.start("op-1")

        # Inject 10 events
        for i in range(10):
            spine.emit(EventRecord(
                event_id=f"e-{i}", event_type=EventType.CUSTOM,
                source=EventSource.SUPERVISOR, correlation_id=f"cor-{i}",
                payload={"index": i}, emitted_at=NOW,
            ))

        results = pilot.run_ticks(50)
        work_done = [r for r in results if r.outcome == TickOutcome.WORK_DONE]
        idle = [r for r in results if r.outcome == TickOutcome.IDLE_TICK]
        # At least some ticks should process events
        assert len(work_done) >= 1
        # After events consumed, remaining ticks are idle
        assert len(idle) >= 1

    def test_checkpoint_restore_resumes_correctly(self) -> None:
        """Create checkpoint, restore, and verify tick continues from correct point."""
        sup, spine, obl = _full_stack()
        pilot = PilotControlPlane(
            supervisor=sup, spine=spine, obligation_engine=obl, clock=CLOCK,
        )
        pilot.start("op-1")
        pilot.run_ticks(10)

        # Checkpoint at tick 10
        cp = pilot.create_checkpoint("op-1")
        assert cp.tick_number == 10

        # Restore to fresh stack
        sup2, spine2, obl2 = _full_stack()
        pilot2 = PilotControlPlane(
            supervisor=sup2, spine=spine2, obligation_engine=obl2, clock=CLOCK,
        )
        pilot2.start("op-1")
        pilot2.restore_checkpoint(cp, "op-1")

        # Continue ticking from restored state
        result = pilot2.tick()
        # Tick number should be 11 (restored from 10)
        assert result.tick_number == 11

    def test_journal_captures_all_ticks(self) -> None:
        """Journal should capture every tick executed."""
        pilot = _pilot()
        pilot.start("op-1")
        pilot.run_ticks(20)
        mgr = pilot.checkpoint_manager
        entries = mgr.journal_since(0)
        tick_entries = [e for e in entries if e.kind == JournalEntryKind.TICK]
        assert len(tick_entries) == 20
        # Sequences are monotonically increasing
        seqs = [e.sequence for e in entries]
        assert seqs == sorted(seqs)
