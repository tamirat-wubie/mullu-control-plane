"""Tests for Phase 37 Subphase 3: replay/checkpoint semantics hardening.

Covers:
- Restore verification (hash match/mismatch, rollback)
- Atomic restore with rollback on failure
- Journal validation (valid, gaps, epoch mismatch, ordering violation, empty)
- Journal replay engine (deterministic tick replay, divergence detection)
- Checkpoint boundary contracts (RestoreVerification, JournalValidationResult)
- Epoch management
"""

from __future__ import annotations

import pytest

from mcoi_runtime.contracts.event import EventRecord, EventSource, EventType
from mcoi_runtime.contracts.obligation import (
    ObligationDeadline,
    ObligationOwner,
    ObligationState,
    ObligationTrigger,
)
from mcoi_runtime.contracts.state_machine import (
    CheckpointScope,
    JournalEntry,
    JournalEntryKind,
    JournalValidationResult,
    JournalValidationVerdict,
    RestoreVerdict,
    RestoreVerification,
)
from mcoi_runtime.contracts.supervisor import (
    LivelockStrategy,
    SupervisorPolicy,
    TickOutcome,
)
from mcoi_runtime.core.checkpoint_manager import CheckpointManager
from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
from mcoi_runtime.core.journal_replay import (
    JournalReplayEngine,
    ReplaySessionResult,
    ReplaySessionVerdict,
    ReplayStepResult,
    ReplayStepVerdict,
)
from mcoi_runtime.core.obligation_runtime import ObligationRuntimeEngine
from mcoi_runtime.core.pilot_control import (
    PilotControlPlane,
    RuntimeStatus,
)
from mcoi_runtime.core.supervisor_engine import SupervisorEngine


NOW = "2026-03-20T12:00:00+00:00"
CLOCK = lambda: NOW  # noqa: E731


def _policy(**overrides) -> SupervisorPolicy:
    defaults = dict(
        policy_id="test-policy",
        tick_interval_ms=100,
        max_events_per_tick=10,
        max_actions_per_tick=10,
        backpressure_threshold=50,
        livelock_repeat_threshold=100,
        livelock_strategy=LivelockStrategy.ESCALATE,
        heartbeat_every_n_ticks=100,
        checkpoint_every_n_ticks=100,
        max_consecutive_errors=5,
        created_at=NOW,
    )
    defaults.update(overrides)
    return SupervisorPolicy(**defaults)


def _owner() -> ObligationOwner:
    return ObligationOwner(owner_id="owner-1", owner_type="team", display_name="Team Alpha")


def _deadline() -> ObligationDeadline:
    return ObligationDeadline(
        deadline_id="dl-1",
        due_at="2026-03-21T12:00:00+00:00",
    )


def _full_stack():
    spine = EventSpineEngine(clock=CLOCK)
    obl = ObligationRuntimeEngine(clock=CLOCK)
    sup = SupervisorEngine(
        policy=_policy(), spine=spine, obligation_engine=obl, clock=CLOCK,
    )
    return sup, spine, obl


def _mgr(sup=None, spine=None, obl=None):
    if sup is None:
        sup, spine, obl = _full_stack()
    return CheckpointManager(
        supervisor=sup, spine=spine, obligation_engine=obl, clock=CLOCK,
    ), sup, spine, obl


def _pilot():
    sup, spine, obl = _full_stack()
    pilot = PilotControlPlane(
        supervisor=sup, spine=spine, obligation_engine=obl, clock=CLOCK,
    )
    return pilot, sup, spine, obl


# =====================================================================
# RestoreVerification contract tests
# =====================================================================


class TestRestoreVerificationContract:
    def test_valid_verified_record(self) -> None:
        rv = RestoreVerification(
            verification_id="rv-1",
            checkpoint_id="cp-1",
            epoch_id="epoch-1",
            tick_number=10,
            verdict=RestoreVerdict.VERIFIED,
            expected_composite_hash="abc123",
            actual_composite_hash="abc123",
            verified_at=NOW,
        )
        assert rv.verdict == RestoreVerdict.VERIFIED
        assert rv.expected_composite_hash == rv.actual_composite_hash

    def test_hash_mismatch_record(self) -> None:
        rv = RestoreVerification(
            verification_id="rv-2",
            checkpoint_id="cp-1",
            epoch_id="epoch-1",
            tick_number=10,
            verdict=RestoreVerdict.HASH_MISMATCH,
            expected_composite_hash="abc123",
            actual_composite_hash="def456",
            verified_at=NOW,
        )
        assert rv.verdict == RestoreVerdict.HASH_MISMATCH
        assert rv.expected_composite_hash != rv.actual_composite_hash

    def test_all_verdicts(self) -> None:
        for v in RestoreVerdict:
            rv = RestoreVerification(
                verification_id=f"rv-{v.value}",
                checkpoint_id="cp-1",
                epoch_id="epoch-1",
                tick_number=0,
                verdict=v,
                expected_composite_hash="h1",
                actual_composite_hash="h2",
                verified_at=NOW,
            )
            assert rv.verdict == v

    def test_serialization_round_trip(self) -> None:
        rv = RestoreVerification(
            verification_id="rv-rt",
            checkpoint_id="cp-1",
            epoch_id="epoch-1",
            tick_number=5,
            verdict=RestoreVerdict.VERIFIED,
            expected_composite_hash="abc",
            actual_composite_hash="abc",
            subsystem_results={"spine": {"expected": "a", "actual": "a", "match": "yes"}},
            verified_at=NOW,
        )
        d = rv.to_dict()
        assert d["verdict"] == "verified"
        assert "spine" in d["subsystem_results"]


# =====================================================================
# JournalValidationResult contract tests
# =====================================================================


class TestJournalValidationContract:
    def test_valid_result(self) -> None:
        jvr = JournalValidationResult(
            validation_id="jv-1",
            epoch_id="epoch-1",
            entry_count=10,
            first_sequence=0,
            last_sequence=9,
            verdict=JournalValidationVerdict.VALID,
        )
        assert jvr.verdict == JournalValidationVerdict.VALID
        assert jvr.gap_positions == ()

    def test_gap_result(self) -> None:
        jvr = JournalValidationResult(
            validation_id="jv-2",
            epoch_id="epoch-1",
            entry_count=8,
            first_sequence=0,
            last_sequence=10,
            verdict=JournalValidationVerdict.SEQUENCE_GAP,
            gap_positions=(3, 7),
            detail="2 gaps",
        )
        assert len(jvr.gap_positions) == 2

    def test_all_verdicts(self) -> None:
        for v in JournalValidationVerdict:
            jvr = JournalValidationResult(
                validation_id=f"jv-{v.value}",
                epoch_id="epoch-1",
                entry_count=0,
                first_sequence=0,
                last_sequence=0,
                verdict=v,
            )
            assert jvr.verdict == v


# =====================================================================
# Checkpoint Manager — restore verification
# =====================================================================


class TestRestoreVerification:
    def test_verified_restore_returns_verification(self) -> None:
        mgr, sup, spine, obl = _mgr()
        spine.emit(EventRecord(
            event_id="e1", event_type=EventType.CUSTOM,
            source=EventSource.SUPERVISOR, correlation_id="cor-1",
            payload={}, emitted_at=NOW,
        ))
        cp = mgr.create_checkpoint()

        # Restore to fresh stack
        sup2, spine2, obl2 = _full_stack()
        mgr2 = CheckpointManager(
            supervisor=sup2, spine=spine2, obligation_engine=obl2, clock=CLOCK,
        )
        rv = mgr2.restore_checkpoint(cp, verify=True)
        assert rv is not None
        assert rv.verdict == RestoreVerdict.VERIFIED
        assert rv.expected_composite_hash == rv.actual_composite_hash

    def test_verified_restore_records_subsystem_results(self) -> None:
        mgr, sup, spine, obl = _mgr()
        cp = mgr.create_checkpoint()

        sup2, spine2, obl2 = _full_stack()
        mgr2 = CheckpointManager(
            supervisor=sup2, spine=spine2, obligation_engine=obl2, clock=CLOCK,
        )
        rv = mgr2.restore_checkpoint(cp, verify=True)
        assert "event_spine" in rv.subsystem_results
        assert "obligation_runtime" in rv.subsystem_results
        assert "supervisor" in rv.subsystem_results
        # All should match
        for scope_name, result in rv.subsystem_results.items():
            assert result["match"] == "yes", f"{scope_name} hash mismatch"

    def test_unverified_restore_returns_none(self) -> None:
        mgr, sup, spine, obl = _mgr()
        cp = mgr.create_checkpoint()

        sup2, spine2, obl2 = _full_stack()
        mgr2 = CheckpointManager(
            supervisor=sup2, spine=spine2, obligation_engine=obl2, clock=CLOCK,
        )
        rv = mgr2.restore_checkpoint(cp, verify=False)
        assert rv is None

    def test_verification_count_increments(self) -> None:
        mgr, sup, spine, obl = _mgr()
        cp = mgr.create_checkpoint()

        sup2, spine2, obl2 = _full_stack()
        mgr2 = CheckpointManager(
            supervisor=sup2, spine=spine2, obligation_engine=obl2, clock=CLOCK,
        )
        assert mgr2.verification_count == 0
        mgr2.restore_checkpoint(cp, verify=True)
        assert mgr2.verification_count == 1

    def test_latest_verification(self) -> None:
        mgr, sup, spine, obl = _mgr()
        cp = mgr.create_checkpoint()

        sup2, spine2, obl2 = _full_stack()
        mgr2 = CheckpointManager(
            supervisor=sup2, spine=spine2, obligation_engine=obl2, clock=CLOCK,
        )
        mgr2.restore_checkpoint(cp, verify=True)
        lv = mgr2.latest_verification()
        assert lv is not None
        assert lv.verdict == RestoreVerdict.VERIFIED

    def test_list_verifications(self) -> None:
        mgr, sup, spine, obl = _mgr()
        cp = mgr.create_checkpoint()

        sup2, spine2, obl2 = _full_stack()
        mgr2 = CheckpointManager(
            supervisor=sup2, spine=spine2, obligation_engine=obl2, clock=CLOCK,
        )
        mgr2.restore_checkpoint(cp, verify=True)
        mgr2.restore_checkpoint(cp, verify=True)
        assert len(mgr2.list_verifications()) == 2


# =====================================================================
# Checkpoint Manager — atomic restore with rollback
# =====================================================================


class TestAtomicRestoreRollback:
    def test_restore_with_obligation_state_preserved(self) -> None:
        """Full stack restore preserves obligation state."""
        mgr, sup, spine, obl = _mgr()
        obl.create_obligation(
            trigger=ObligationTrigger.CUSTOM,
            trigger_ref_id="ref-1",
            owner=_owner(), deadline=_deadline(),
            description="test obl",
            correlation_id="cor-1",
        )
        cp = mgr.create_checkpoint()

        sup2, spine2, obl2 = _full_stack()
        mgr2 = CheckpointManager(
            supervisor=sup2, spine=spine2, obligation_engine=obl2, clock=CLOCK,
        )
        mgr2.restore_checkpoint(cp, verify=True)
        assert obl2.obligation_count == 1

    def test_restore_journals_resume_with_verification(self) -> None:
        """Restore journals a RESUME entry with verification info."""
        mgr, sup, spine, obl = _mgr()
        cp = mgr.create_checkpoint()

        sup2, spine2, obl2 = _full_stack()
        mgr2 = CheckpointManager(
            supervisor=sup2, spine=spine2, obligation_engine=obl2, clock=CLOCK,
        )
        mgr2.restore_checkpoint(cp, verify=True)
        entries = mgr2.journal_since(0)
        resume_entries = [e for e in entries if e.kind == JournalEntryKind.RESUME]
        assert len(resume_entries) == 1
        assert resume_entries[0].payload["verified"] is True
        assert resume_entries[0].payload["verdict"] == "verified"


# =====================================================================
# Journal validation
# =====================================================================


class TestJournalValidation:
    def test_empty_journal(self) -> None:
        mgr, _, _, _ = _mgr()
        result = mgr.validate_journal()
        assert result.verdict == JournalValidationVerdict.EMPTY_JOURNAL
        assert result.entry_count == 0

    def test_valid_journal(self) -> None:
        mgr, _, _, _ = _mgr()
        mgr.append_journal(JournalEntryKind.TICK, "tick-1", {"tick_number": 1})
        mgr.append_journal(JournalEntryKind.TICK, "tick-2", {"tick_number": 2})
        mgr.append_journal(JournalEntryKind.CHECKPOINT, "cp-1", {"tick": 2})
        result = mgr.validate_journal()
        assert result.verdict == JournalValidationVerdict.VALID
        assert result.entry_count == 3
        assert result.first_sequence == 0
        assert result.last_sequence == 2

    def test_journal_after_checkpoint_create(self) -> None:
        mgr, sup, spine, obl = _mgr()
        mgr.create_checkpoint()
        result = mgr.validate_journal()
        assert result.verdict == JournalValidationVerdict.VALID

    def test_journal_after_multiple_operations(self) -> None:
        """Pilot run + checkpoint = valid journal."""
        pilot, sup, spine, obl = _pilot()
        pilot.start("op-1")
        pilot.run_ticks(5)
        pilot.create_checkpoint("op-1")
        mgr = pilot.checkpoint_manager
        result = mgr.validate_journal()
        assert result.verdict == JournalValidationVerdict.VALID
        assert result.entry_count == 6  # 5 ticks + 1 checkpoint

    def test_journal_entries_returns_all(self) -> None:
        mgr, _, _, _ = _mgr()
        mgr.append_journal(JournalEntryKind.TICK, "t-1", {})
        mgr.append_journal(JournalEntryKind.TICK, "t-2", {})
        entries = mgr.journal_entries()
        assert len(entries) == 2
        assert entries[0].sequence == 0
        assert entries[1].sequence == 1

    def test_epoch_mismatch_detail_is_bounded(self) -> None:
        mgr, _, _, _ = _mgr()
        mgr.append_journal(JournalEntryKind.TICK, "t-1", {})
        mgr.append_journal(JournalEntryKind.TICK, "t-2", {})
        object.__setattr__(mgr.journal_entries()[1], "epoch_id", "epoch-secret")

        result = mgr.validate_journal()

        assert result.verdict == JournalValidationVerdict.EPOCH_MISMATCH
        assert result.detail == "journal epoch mismatch detected"
        assert "epoch-secret" not in result.detail
        assert "2" not in result.detail

    def test_ordering_violation_detail_is_bounded(self) -> None:
        mgr, _, _, _ = _mgr()
        mgr.append_journal(JournalEntryKind.TICK, "t-1", {})
        mgr.append_journal(JournalEntryKind.TICK, "t-2", {})
        object.__setattr__(mgr.journal_entries()[1], "sequence", 0)

        result = mgr.validate_journal()

        assert result.verdict == JournalValidationVerdict.ORDERING_VIOLATION
        assert result.detail == "journal ordering violation detected"
        assert "<=" not in result.detail
        assert "0" not in result.detail

    def test_sequence_gap_detail_is_bounded(self) -> None:
        mgr, _, _, _ = _mgr()
        mgr.append_journal(JournalEntryKind.TICK, "t-1", {})
        mgr.append_journal(JournalEntryKind.TICK, "t-2", {})
        object.__setattr__(mgr.journal_entries()[1], "sequence", 2)

        result = mgr.validate_journal()

        assert result.verdict == JournalValidationVerdict.SEQUENCE_GAP
        assert result.detail == "journal sequence gap detected"
        assert "gap(" not in result.detail
        assert "1" not in result.detail


# =====================================================================
# Epoch management
# =====================================================================


class TestEpochManagement:
    def test_default_epoch(self) -> None:
        mgr, _, _, _ = _mgr()
        assert mgr.epoch_id == "epoch-1"

    def test_advance_epoch(self) -> None:
        mgr, _, _, _ = _mgr()
        mgr.append_journal(JournalEntryKind.TICK, "t-1", {})
        assert mgr.journal_length == 1

        mgr.advance_epoch("epoch-2")
        assert mgr.epoch_id == "epoch-2"

        # New entries use new epoch
        entry = mgr.append_journal(JournalEntryKind.TICK, "t-2", {})
        assert entry.epoch_id == "epoch-2"
        assert entry.sequence == 0  # reset

    def test_advance_epoch_rejects_empty(self) -> None:
        mgr, _, _, _ = _mgr()
        with pytest.raises(RuntimeCoreInvariantError, match="non-empty"):
            mgr.advance_epoch("")

    def test_advance_epoch_rejects_whitespace(self) -> None:
        mgr, _, _, _ = _mgr()
        with pytest.raises(RuntimeCoreInvariantError, match="non-empty"):
            mgr.advance_epoch("   ")


# =====================================================================
# Pilot control plane — verified restore
# =====================================================================


class TestPilotVerifiedRestore:
    def test_pilot_restore_with_verification(self) -> None:
        pilot, sup, spine, obl = _pilot()
        pilot.start("op-1")
        pilot.run_ticks(5)
        cp = pilot.create_checkpoint("op-1")

        # Fresh stack, restore
        sup2, spine2, obl2 = _full_stack()
        pilot2 = PilotControlPlane(
            supervisor=sup2, spine=spine2, obligation_engine=obl2, clock=CLOCK,
        )
        pilot2.start("op-1")
        pilot2.restore_checkpoint(cp, "op-1", verify=True)

        # Continue ticking from restored state
        result = pilot2.tick()
        assert result.tick_number == 6

    def test_pilot_restore_without_verification(self) -> None:
        pilot, sup, spine, obl = _pilot()
        pilot.start("op-1")
        pilot.run_ticks(3)
        cp = pilot.create_checkpoint("op-1")

        sup2, spine2, obl2 = _full_stack()
        pilot2 = PilotControlPlane(
            supervisor=sup2, spine=spine2, obligation_engine=obl2, clock=CLOCK,
        )
        pilot2.start("op-1")
        pilot2.restore_checkpoint(cp, "op-1", verify=False)
        result = pilot2.tick()
        assert result.tick_number == 4


# =====================================================================
# Journal replay engine
# =====================================================================


class TestReplayStepResultContract:
    def test_valid_match_step(self) -> None:
        step = ReplayStepResult(
            step_id="rs-1",
            sequence=0,
            kind=JournalEntryKind.TICK,
            verdict=ReplayStepVerdict.MATCH,
            expected_payload={"tick_number": 1, "outcome": "idle_tick"},
            actual_payload={"tick_number": 1, "outcome": "idle_tick"},
        )
        assert step.verdict == ReplayStepVerdict.MATCH

    def test_all_step_verdicts(self) -> None:
        for v in ReplayStepVerdict:
            step = ReplayStepResult(
                step_id=f"rs-{v.value}",
                sequence=0,
                kind=JournalEntryKind.TICK,
                verdict=v,
            )
            assert step.verdict == v

    def test_serialization(self) -> None:
        step = ReplayStepResult(
            step_id="rs-ser",
            sequence=5,
            kind=JournalEntryKind.TICK,
            verdict=ReplayStepVerdict.OUTCOME_DIVERGED,
            expected_payload={"outcome": "idle_tick"},
            actual_payload={"outcome": "work_done"},
            detail="mismatch",
        )
        d = step.to_dict()
        assert d["verdict"] == "outcome_diverged"
        assert d["detail"] == "mismatch"


class TestReplaySessionResultContract:
    def test_valid_session(self) -> None:
        session = ReplaySessionResult(
            session_id="rses-1",
            epoch_id="epoch-1",
            entries_replayed=10,
            entries_matched=8,
            entries_diverged=0,
            entries_skipped=2,
            verdict=ReplaySessionVerdict.SUCCESS,
            started_at=NOW,
            completed_at=NOW,
        )
        assert session.verdict == ReplaySessionVerdict.SUCCESS

    def test_all_session_verdicts(self) -> None:
        for v in ReplaySessionVerdict:
            session = ReplaySessionResult(
                session_id=f"rses-{v.value}",
                epoch_id="epoch-1",
                entries_replayed=0,
                entries_matched=0,
                entries_diverged=0,
                entries_skipped=0,
                verdict=v,
            )
            assert session.verdict == v


class TestJournalReplayDeterministic:
    """Replay of idle ticks should match exactly."""

    def test_replay_idle_ticks(self) -> None:
        """Run 10 idle ticks, record journal, replay from checkpoint — all match."""
        sup, spine, obl = _full_stack()
        mgr = CheckpointManager(
            supervisor=sup, spine=spine, obligation_engine=obl, clock=CLOCK,
        )

        # Create initial checkpoint
        cp = mgr.create_checkpoint()

        # Run ticks and journal them
        for _ in range(10):
            tick_result = sup.tick()
            mgr.append_journal(
                JournalEntryKind.TICK,
                subject_id=f"tick-{tick_result.tick_number}",
                payload={
                    "tick_number": tick_result.tick_number,
                    "outcome": tick_result.outcome.value,
                },
            )

        # Get tick-only journal entries
        tick_entries = tuple(
            e for e in mgr.journal_since(0)
            if e.kind == JournalEntryKind.TICK
        )
        assert len(tick_entries) == 10

        # Fresh stack for replay
        sup2, spine2, obl2 = _full_stack()
        mgr2 = CheckpointManager(
            supervisor=sup2, spine=spine2, obligation_engine=obl2, clock=CLOCK,
        )
        replay = JournalReplayEngine(
            supervisor=sup2, checkpoint_manager=mgr2, clock=CLOCK,
        )

        result = replay.replay_from_checkpoint(cp, tick_entries)
        assert result.verdict == ReplaySessionVerdict.SUCCESS
        assert result.entries_matched == 10
        assert result.entries_diverged == 0

    def test_replay_empty_journal(self) -> None:
        sup, spine, obl = _full_stack()
        mgr = CheckpointManager(
            supervisor=sup, spine=spine, obligation_engine=obl, clock=CLOCK,
        )
        cp = mgr.create_checkpoint()

        sup2, spine2, obl2 = _full_stack()
        mgr2 = CheckpointManager(
            supervisor=sup2, spine=spine2, obligation_engine=obl2, clock=CLOCK,
        )
        replay = JournalReplayEngine(
            supervisor=sup2, checkpoint_manager=mgr2, clock=CLOCK,
        )
        result = replay.replay_from_checkpoint(cp, ())
        assert result.verdict == ReplaySessionVerdict.EMPTY_JOURNAL

    def test_replay_skips_non_tick_entries(self) -> None:
        """Non-tick journal entries should be skipped, not re-executed."""
        sup, spine, obl = _full_stack()
        mgr = CheckpointManager(
            supervisor=sup, spine=spine, obligation_engine=obl, clock=CLOCK,
        )
        cp = mgr.create_checkpoint()

        # Add various non-tick entries
        mgr.append_journal(JournalEntryKind.HEARTBEAT, "hb-1", {})
        mgr.append_journal(JournalEntryKind.CHECKPOINT, "cp-2", {})

        entries = mgr.journal_since(0)
        # Filter out the checkpoint entry from create_checkpoint
        non_cp_entries = tuple(e for e in entries if e.sequence >= 1)

        sup2, spine2, obl2 = _full_stack()
        mgr2 = CheckpointManager(
            supervisor=sup2, spine=spine2, obligation_engine=obl2, clock=CLOCK,
        )
        replay = JournalReplayEngine(
            supervisor=sup2, checkpoint_manager=mgr2, clock=CLOCK,
        )
        result = replay.replay_from_checkpoint(cp, non_cp_entries)
        assert result.verdict == ReplaySessionVerdict.SUCCESS
        assert result.entries_skipped == 2
        assert result.entries_matched == 0
        assert all(step.detail == "entry not re-executed during replay" for step in result.steps)
        assert all("heartbeat" not in step.detail for step in result.steps)

    def test_replay_mixed_entries(self) -> None:
        """Mix of tick and non-tick entries — ticks matched, others skipped."""
        sup, spine, obl = _full_stack()
        mgr = CheckpointManager(
            supervisor=sup, spine=spine, obligation_engine=obl, clock=CLOCK,
        )
        cp = mgr.create_checkpoint()

        # Run some ticks with intervening non-tick entries
        tick_result = sup.tick()
        mgr.append_journal(JournalEntryKind.TICK, f"tick-{tick_result.tick_number}", {
            "tick_number": tick_result.tick_number,
            "outcome": tick_result.outcome.value,
        })
        mgr.append_journal(JournalEntryKind.HEARTBEAT, "hb-1", {})
        tick_result = sup.tick()
        mgr.append_journal(JournalEntryKind.TICK, f"tick-{tick_result.tick_number}", {
            "tick_number": tick_result.tick_number,
            "outcome": tick_result.outcome.value,
        })

        entries = tuple(e for e in mgr.journal_since(0) if e.sequence >= 1)

        sup2, spine2, obl2 = _full_stack()
        mgr2 = CheckpointManager(
            supervisor=sup2, spine=spine2, obligation_engine=obl2, clock=CLOCK,
        )
        replay = JournalReplayEngine(
            supervisor=sup2, checkpoint_manager=mgr2, clock=CLOCK,
        )
        result = replay.replay_from_checkpoint(cp, entries)
        assert result.verdict == ReplaySessionVerdict.SUCCESS
        assert result.entries_matched == 2
        assert result.entries_skipped == 1

    def test_replay_journal_no_checkpoint(self) -> None:
        """replay_journal replays against current state without restore."""
        sup, spine, obl = _full_stack()
        mgr = CheckpointManager(
            supervisor=sup, spine=spine, obligation_engine=obl, clock=CLOCK,
        )

        # Record ticks
        for _ in range(5):
            tick_result = sup.tick()
            mgr.append_journal(JournalEntryKind.TICK, f"tick-{tick_result.tick_number}", {
                "tick_number": tick_result.tick_number,
                "outcome": tick_result.outcome.value,
            })

        tick_entries = tuple(
            e for e in mgr.journal_since(0)
            if e.kind == JournalEntryKind.TICK
        )

        # Fresh supervisor at tick 0 — should replay to match tick 1,2,3,4,5
        sup2, spine2, obl2 = _full_stack()
        mgr2 = CheckpointManager(
            supervisor=sup2, spine=spine2, obligation_engine=obl2, clock=CLOCK,
        )
        replay = JournalReplayEngine(
            supervisor=sup2, checkpoint_manager=mgr2, clock=CLOCK,
        )
        result = replay.replay_journal(tick_entries)
        assert result.verdict == ReplaySessionVerdict.SUCCESS
        assert result.entries_matched == 5

    def test_tick_execution_error_is_bounded(self) -> None:
        sup, spine, obl = _full_stack()
        mgr = CheckpointManager(
            supervisor=sup, spine=spine, obligation_engine=obl, clock=CLOCK,
        )
        cp = mgr.create_checkpoint()
        entry = mgr.append_journal(
            JournalEntryKind.TICK,
            "tick-1",
            {"tick_number": 1, "outcome": "idle_tick"},
        )

        _, spine2, obl2 = _full_stack()
        mgr2 = CheckpointManager(
            supervisor=sup, spine=spine2, obligation_engine=obl2, clock=CLOCK,
        )

        class CrashingSupervisor:
            def tick(self):
                raise RuntimeError("secret tick failure")

        replay = JournalReplayEngine(
            supervisor=CrashingSupervisor(), checkpoint_manager=mgr2, clock=CLOCK,
        )
        result = replay.replay_from_checkpoint(cp, (entry,), halt_on_divergence=True)
        step = result.steps[0]

        assert result.verdict == ReplaySessionVerdict.DIVERGENCE_DETECTED
        assert step.verdict == ReplayStepVerdict.ERROR
        assert step.detail == "tick execution error (RuntimeError)"
        assert "secret tick failure" not in step.detail


class TestReplayDivergenceDetection:
    def test_halt_on_divergence(self) -> None:
        """When halt_on_divergence=True, replay stops at first mismatch."""
        sup, spine, obl = _full_stack()
        mgr = CheckpointManager(
            supervisor=sup, spine=spine, obligation_engine=obl, clock=CLOCK,
        )
        cp = mgr.create_checkpoint()

        # Record 5 tick entries with WRONG tick numbers (tick 100, 101, ...)
        fake_entries: list[JournalEntry] = []
        for i in range(5):
            entry = mgr.append_journal(JournalEntryKind.TICK, f"fake-{i}", {
                "tick_number": 100 + i,
                "outcome": "idle_tick",
            })
            fake_entries.append(entry)

        # Filter to just the fake entries
        entries = tuple(fake_entries)

        sup2, spine2, obl2 = _full_stack()
        mgr2 = CheckpointManager(
            supervisor=sup2, spine=spine2, obligation_engine=obl2, clock=CLOCK,
        )
        replay = JournalReplayEngine(
            supervisor=sup2, checkpoint_manager=mgr2, clock=CLOCK,
        )
        result = replay.replay_from_checkpoint(cp, entries, halt_on_divergence=True)
        assert result.verdict == ReplaySessionVerdict.DIVERGENCE_DETECTED
        # Should stop at first divergence
        assert result.entries_replayed == 1
        assert result.entries_diverged == 1
        assert result.steps[0].detail == "tick number diverged"
        assert "100" not in result.steps[0].detail

    def test_continue_past_divergence(self) -> None:
        """When halt_on_divergence=False, replay continues past mismatches."""
        sup, spine, obl = _full_stack()
        mgr = CheckpointManager(
            supervisor=sup, spine=spine, obligation_engine=obl, clock=CLOCK,
        )
        cp = mgr.create_checkpoint()

        fake_entries: list[JournalEntry] = []
        for i in range(3):
            entry = mgr.append_journal(JournalEntryKind.TICK, f"fake-{i}", {
                "tick_number": 100 + i,
                "outcome": "idle_tick",
            })
            fake_entries.append(entry)

        sup2, spine2, obl2 = _full_stack()
        mgr2 = CheckpointManager(
            supervisor=sup2, spine=spine2, obligation_engine=obl2, clock=CLOCK,
        )
        replay = JournalReplayEngine(
            supervisor=sup2, checkpoint_manager=mgr2, clock=CLOCK,
        )
        result = replay.replay_from_checkpoint(
            cp, tuple(fake_entries), halt_on_divergence=False,
        )
        assert result.verdict == ReplaySessionVerdict.DIVERGENCE_DETECTED
        # All entries should be attempted
        assert result.entries_replayed == 3
        assert result.entries_diverged == 3

    def test_outcome_divergence(self) -> None:
        """Wrong outcome in journal is detected as divergence."""
        sup, spine, obl = _full_stack()
        mgr = CheckpointManager(
            supervisor=sup, spine=spine, obligation_engine=obl, clock=CLOCK,
        )
        cp = mgr.create_checkpoint()

        # Record entry with correct tick number but wrong outcome
        entry = mgr.append_journal(JournalEntryKind.TICK, "tick-1", {
            "tick_number": 1,
            "outcome": "work_done",  # Wrong — supervisor will produce idle_tick
        })

        sup2, spine2, obl2 = _full_stack()
        mgr2 = CheckpointManager(
            supervisor=sup2, spine=spine2, obligation_engine=obl2, clock=CLOCK,
        )
        replay = JournalReplayEngine(
            supervisor=sup2, checkpoint_manager=mgr2, clock=CLOCK,
        )
        result = replay.replay_from_checkpoint(cp, (entry,))
        assert result.verdict == ReplaySessionVerdict.DIVERGENCE_DETECTED
        assert result.steps[0].verdict == ReplayStepVerdict.OUTCOME_DIVERGED
        assert result.steps[0].detail == "tick outcome diverged"
        assert "work_done" not in result.steps[0].detail


# =====================================================================
# Long-run replay determinism
# =====================================================================


class TestLongRunReplayDeterminism:
    def test_50_tick_replay_round_trip(self) -> None:
        """Run 50 ticks, checkpoint, replay all 50 — every tick matches."""
        sup, spine, obl = _full_stack()
        mgr = CheckpointManager(
            supervisor=sup, spine=spine, obligation_engine=obl, clock=CLOCK,
        )

        # Initial checkpoint
        cp = mgr.create_checkpoint()

        # Run 50 ticks and record
        for _ in range(50):
            tick_result = sup.tick()
            mgr.append_journal(JournalEntryKind.TICK, f"tick-{tick_result.tick_number}", {
                "tick_number": tick_result.tick_number,
                "outcome": tick_result.outcome.value,
            })

        tick_entries = tuple(
            e for e in mgr.journal_since(0)
            if e.kind == JournalEntryKind.TICK
        )
        assert len(tick_entries) == 50

        # Replay on fresh stack
        sup2, spine2, obl2 = _full_stack()
        mgr2 = CheckpointManager(
            supervisor=sup2, spine=spine2, obligation_engine=obl2, clock=CLOCK,
        )
        replay = JournalReplayEngine(
            supervisor=sup2, checkpoint_manager=mgr2, clock=CLOCK,
        )
        result = replay.replay_from_checkpoint(cp, tick_entries)
        assert result.verdict == ReplaySessionVerdict.SUCCESS
        assert result.entries_matched == 50
        assert result.entries_diverged == 0

    def test_checkpoint_mid_run_replay(self) -> None:
        """Checkpoint at tick 20, replay ticks 21-40."""
        sup, spine, obl = _full_stack()
        mgr = CheckpointManager(
            supervisor=sup, spine=spine, obligation_engine=obl, clock=CLOCK,
        )

        # Run 20 ticks
        for _ in range(20):
            sup.tick()

        # Checkpoint at tick 20
        cp = mgr.create_checkpoint()
        assert cp.tick_number == 20

        # Run 20 more ticks, recording journal
        for _ in range(20):
            tick_result = sup.tick()
            mgr.append_journal(JournalEntryKind.TICK, f"tick-{tick_result.tick_number}", {
                "tick_number": tick_result.tick_number,
                "outcome": tick_result.outcome.value,
            })

        tick_entries = tuple(
            e for e in mgr.journal_since(0)
            if e.kind == JournalEntryKind.TICK
        )
        assert len(tick_entries) == 20  # only ticks 21-40

        # Replay from checkpoint at tick 20
        sup2, spine2, obl2 = _full_stack()
        mgr2 = CheckpointManager(
            supervisor=sup2, spine=spine2, obligation_engine=obl2, clock=CLOCK,
        )
        replay = JournalReplayEngine(
            supervisor=sup2, checkpoint_manager=mgr2, clock=CLOCK,
        )
        result = replay.replay_from_checkpoint(cp, tick_entries)
        assert result.verdict == ReplaySessionVerdict.SUCCESS
        assert result.entries_matched == 20

    def test_replay_with_events(self) -> None:
        """Replay ticks that processed real events — outcomes should match."""
        sup, spine, obl = _full_stack()
        mgr = CheckpointManager(
            supervisor=sup, spine=spine, obligation_engine=obl, clock=CLOCK,
        )

        # Inject events before checkpoint
        for i in range(5):
            spine.emit(EventRecord(
                event_id=f"e-{i}", event_type=EventType.CUSTOM,
                source=EventSource.SUPERVISOR, correlation_id=f"cor-{i}",
                payload={"index": i}, emitted_at=NOW,
            ))

        # Checkpoint with events present
        cp = mgr.create_checkpoint()

        # Run ticks that will process events
        for _ in range(15):
            tick_result = sup.tick()
            mgr.append_journal(JournalEntryKind.TICK, f"tick-{tick_result.tick_number}", {
                "tick_number": tick_result.tick_number,
                "outcome": tick_result.outcome.value,
            })

        tick_entries = tuple(
            e for e in mgr.journal_since(0)
            if e.kind == JournalEntryKind.TICK
        )

        # Replay on fresh stack — restore brings back the events
        sup2, spine2, obl2 = _full_stack()
        mgr2 = CheckpointManager(
            supervisor=sup2, spine=spine2, obligation_engine=obl2, clock=CLOCK,
        )
        replay = JournalReplayEngine(
            supervisor=sup2, checkpoint_manager=mgr2, clock=CLOCK,
        )
        result = replay.replay_from_checkpoint(cp, tick_entries)
        assert result.verdict == ReplaySessionVerdict.SUCCESS
        assert result.entries_matched == 15
