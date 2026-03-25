"""Edge case tests for Holistic Audit #11 fixes.

Covers:
  - EventSpine state_hash includes reactions and envelopes
  - CheckpointManager supervisor state hash includes error/idle counters
  - CheckpointManager rollback preserves pre-restore error/idle state
  - CheckpointManager supervisor payload stores consecutive_errors/idle/halted
  - ObligationRuntime restore rejects snapshot missing event_seq
  - freeze_value handles set/frozenset
  - thaw_value handles frozenset
  - ObligationRuntime state_hash includes closures/transfers/escalations
  - EventSpine emit_and_envelope construct-then-commit
"""

from __future__ import annotations

import pytest

from mcoi_runtime.contracts._base import freeze_value, thaw_value
from mcoi_runtime.contracts.event import (
    EventReaction,
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
from mcoi_runtime.contracts.state_machine import CheckpointScope
from mcoi_runtime.contracts.supervisor import (
    LivelockStrategy,
    SupervisorPolicy,
)
from mcoi_runtime.core.checkpoint_manager import CheckpointManager
from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
from mcoi_runtime.core.obligation_runtime import ObligationRuntimeEngine
from mcoi_runtime.core.supervisor_engine import SupervisorEngine

NOW = "2026-03-20T12:00:00+00:00"
CLOCK = lambda: NOW  # noqa: E731


def _owner(oid: str = "o1") -> ObligationOwner:
    return ObligationOwner(owner_id=oid, owner_type="human", display_name="tester")


def _deadline() -> ObligationDeadline:
    return ObligationDeadline(deadline_id="dl-1", due_at=NOW, hard=False)


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


# =====================================================================
# EventSpine state_hash completeness
# =====================================================================


class TestEventSpineStateHashCompleteness:
    def test_hash_changes_when_reaction_added(self) -> None:
        """state_hash must change when a reaction is recorded."""
        spine = EventSpineEngine(clock=CLOCK)
        evt = EventRecord(
            event_id="e1", event_type=EventType.CUSTOM,
            source=EventSource.SUPERVISOR, correlation_id="cor-1",
            payload={}, emitted_at=NOW,
        )
        spine.emit(evt)
        hash_before = spine.state_hash()

        reaction = EventReaction(
            reaction_id="r1", event_id="e1",
            subscription_id="sub-1", action_taken="log",
            result="ok", reacted_at=NOW,
        )
        spine.record_reaction(reaction)
        hash_after = spine.state_hash()
        assert hash_before != hash_after

    def test_hash_changes_when_envelope_added(self) -> None:
        """state_hash must change when an envelope is created."""
        spine = EventSpineEngine(clock=CLOCK)
        hash_before = spine.state_hash()

        evt = EventRecord(
            event_id="e1", event_type=EventType.CUSTOM,
            source=EventSource.SUPERVISOR, correlation_id="cor-1",
            payload={}, emitted_at=NOW,
        )
        spine.emit_and_envelope(evt, target_subsystems=("sub1",))
        hash_after = spine.state_hash()
        assert hash_before != hash_after

    def test_snapshot_restore_hash_roundtrip_with_reactions(self) -> None:
        """Snapshot/restore with reactions must produce identical hash."""
        spine = EventSpineEngine(clock=CLOCK)
        evt = EventRecord(
            event_id="e1", event_type=EventType.CUSTOM,
            source=EventSource.SUPERVISOR, correlation_id="cor-1",
            payload={}, emitted_at=NOW,
        )
        spine.emit(evt)
        reaction = EventReaction(
            reaction_id="r1", event_id="e1",
            subscription_id="sub-1", action_taken="log",
            result="ok", reacted_at=NOW,
        )
        spine.record_reaction(reaction)
        snap = spine.snapshot()
        original_hash = spine.state_hash()

        spine2 = EventSpineEngine(clock=CLOCK)
        spine2.restore(snap)
        assert spine2.state_hash() == original_hash


# =====================================================================
# CheckpointManager supervisor hash completeness
# =====================================================================


class TestCheckpointManagerSupervisorHash:
    def test_supervisor_hash_includes_error_counters(self) -> None:
        """Supervisor state hash must differ when error counters change."""
        sup, spine, obl = _full_stack()
        mgr = CheckpointManager(
            supervisor=sup, spine=spine, obligation_engine=obl, clock=CLOCK,
        )
        hash_clean = mgr._supervisor_state_hash()

        sup._consecutive_errors = 2
        hash_with_errors = mgr._supervisor_state_hash()
        assert hash_clean != hash_with_errors

    def test_supervisor_hash_includes_idle_counters(self) -> None:
        sup, spine, obl = _full_stack()
        mgr = CheckpointManager(
            supervisor=sup, spine=spine, obligation_engine=obl, clock=CLOCK,
        )
        hash_clean = mgr._supervisor_state_hash()

        sup._consecutive_idle_ticks = 5
        hash_with_idle = mgr._supervisor_state_hash()
        assert hash_clean != hash_with_idle

    def test_checkpoint_payload_stores_error_counters(self) -> None:
        """Checkpoint payload must include error/idle/halted fields."""
        sup, spine, obl = _full_stack()
        sup._consecutive_errors = 3
        sup._consecutive_idle_ticks = 7

        mgr = CheckpointManager(
            supervisor=sup, spine=spine, obligation_engine=obl, clock=CLOCK,
        )
        cp = mgr.create_checkpoint()
        sup_snap = cp.snapshot_for(CheckpointScope.SUPERVISOR)
        assert sup_snap is not None
        assert sup_snap.payload["consecutive_errors"] == 3
        assert sup_snap.payload["consecutive_idle_ticks"] == 7
        assert "halted" in sup_snap.payload


# =====================================================================
# CheckpointManager rollback preserves pre-restore state
# =====================================================================


class TestCheckpointManagerRollbackPreservesState:
    def test_restore_uses_stored_error_counters(self) -> None:
        """Restore must use error counters from checkpoint payload, not zeros."""
        sup, spine, obl = _full_stack()
        # Set error state before checkpoint
        sup._consecutive_errors = 3
        sup._consecutive_idle_ticks = 7

        mgr = CheckpointManager(
            supervisor=sup, spine=spine, obligation_engine=obl, clock=CLOCK,
        )
        cp = mgr.create_checkpoint()

        # Restore onto fresh stack
        sup2, spine2, obl2 = _full_stack()
        mgr2 = CheckpointManager(
            supervisor=sup2, spine=spine2, obligation_engine=obl2, clock=CLOCK,
        )
        mgr2.restore_checkpoint(cp)
        assert sup2._consecutive_errors == 3
        assert sup2._consecutive_idle_ticks == 7

    def test_restore_clean_checkpoint_resets_counters(self) -> None:
        """Restoring a clean checkpoint must set counters to 0."""
        sup, spine, obl = _full_stack()
        mgr = CheckpointManager(
            supervisor=sup, spine=spine, obligation_engine=obl, clock=CLOCK,
        )
        cp = mgr.create_checkpoint()

        # Target has error state
        sup2, spine2, obl2 = _full_stack()
        sup2._consecutive_errors = 5
        mgr2 = CheckpointManager(
            supervisor=sup2, spine=spine2, obligation_engine=obl2, clock=CLOCK,
        )
        mgr2.restore_checkpoint(cp)
        assert sup2._consecutive_errors == 0
        assert sup2._consecutive_idle_ticks == 0


# =====================================================================
# ObligationRuntime restore rejects missing event_seq
# =====================================================================


class TestObligationRestoreMissingEventSeq:
    def test_restore_rejects_missing_event_seq(self) -> None:
        """Snapshot without event_seq must raise RuntimeCoreInvariantError."""
        obl = ObligationRuntimeEngine(clock=CLOCK)
        bad_snapshot = {
            "obligations": {},
            "closures": {},
            "transfers": {},
            "escalations": {},
            "state_hash": "abc",
        }
        with pytest.raises(RuntimeCoreInvariantError, match="event_seq"):
            obl.restore(bad_snapshot)

    def test_restore_accepts_valid_event_seq(self) -> None:
        """Snapshot with event_seq must restore correctly."""
        obl = ObligationRuntimeEngine(clock=CLOCK)
        obl.create_obligation(
            trigger=ObligationTrigger.CUSTOM,
            trigger_ref_id="ref-1",
            owner=_owner(), deadline=_deadline(),
            description="test", correlation_id="cor-1",
        )
        snap = obl.snapshot()
        assert "event_seq" in snap

        obl2 = ObligationRuntimeEngine(clock=CLOCK)
        obl2.restore(snap)
        assert obl2._event_seq == snap["event_seq"]


# =====================================================================
# freeze_value / thaw_value set/frozenset handling
# =====================================================================


class TestFreezeThawSetHandling:
    def test_freeze_value_set(self) -> None:
        result = freeze_value({"a", "b", "c"})
        assert isinstance(result, frozenset)
        assert result == frozenset({"a", "b", "c"})

    def test_freeze_value_frozenset(self) -> None:
        result = freeze_value(frozenset({"x", "y"}))
        assert isinstance(result, frozenset)
        assert result == frozenset({"x", "y"})

    def test_freeze_value_nested_set_in_dict(self) -> None:
        result = freeze_value({"tags": {"a", "b"}})
        assert isinstance(result["tags"], frozenset)

    def test_thaw_value_frozenset(self) -> None:
        result = thaw_value(frozenset({"a", "b"}))
        assert isinstance(result, list)
        assert set(result) == {"a", "b"}

    def test_freeze_thaw_roundtrip_set(self) -> None:
        original = {"x", "y", "z"}
        frozen = freeze_value(original)
        thawed = thaw_value(frozen)
        assert isinstance(thawed, list)
        assert set(thawed) == original


# =====================================================================
# ObligationRuntime state_hash completeness
# =====================================================================


class TestObligationStateHashCompleteness:
    def test_hash_changes_with_closure(self) -> None:
        """state_hash must change when an obligation is closed."""
        obl = ObligationRuntimeEngine(clock=CLOCK)
        rec = obl.create_obligation(
            trigger=ObligationTrigger.CUSTOM,
            trigger_ref_id="ref-1",
            owner=_owner(), deadline=_deadline(),
            description="test", correlation_id="cor-1",
        )
        hash_before = obl.state_hash()

        obl.close(rec.obligation_id, final_state=ObligationState.COMPLETED, reason="done", closed_by="tester")
        hash_after = obl.state_hash()
        assert hash_before != hash_after

    def test_hash_changes_with_transfer(self) -> None:
        """state_hash must change when an obligation is transferred."""
        obl = ObligationRuntimeEngine(clock=CLOCK)
        rec = obl.create_obligation(
            trigger=ObligationTrigger.CUSTOM,
            trigger_ref_id="ref-1",
            owner=_owner("o1"), deadline=_deadline(),
            description="test", correlation_id="cor-1",
        )
        obl.activate(rec.obligation_id)
        hash_before = obl.state_hash()

        obl.transfer(rec.obligation_id, to_owner=_owner("o2"), reason="reassign")
        hash_after = obl.state_hash()
        assert hash_before != hash_after


# =====================================================================
# EventSpine emit_and_envelope construct-then-commit
# =====================================================================


class TestEmitAndEnvelopeAtomicity:
    def test_emit_and_envelope_duplicate_rejected(self) -> None:
        """If event already exists, emit_and_envelope must not create extra envelope."""
        spine = EventSpineEngine(clock=CLOCK)
        evt = EventRecord(
            event_id="e1", event_type=EventType.CUSTOM,
            source=EventSource.SUPERVISOR, correlation_id="cor-1",
            payload={}, emitted_at=NOW,
        )
        spine.emit_and_envelope(evt, target_subsystems=("s1",))
        assert spine.event_count == 1

        evt2 = EventRecord(
            event_id="e1", event_type=EventType.CUSTOM,
            source=EventSource.SUPERVISOR, correlation_id="cor-2",
            payload={}, emitted_at=NOW,
        )
        envelope_count_before = len(spine._envelopes)
        with pytest.raises(RuntimeCoreInvariantError, match="already exists"):
            spine.emit_and_envelope(evt2, target_subsystems=("s2",))
        assert len(spine._envelopes) == envelope_count_before
