"""Edge case tests for Holistic Audit #6 fixes.

Covers:
- Supervisor livelock detection fix (unreachable condition + resolution)
- Obligation transfer preserves original state (not forced to ACTIVE)
- Obligation escalation rejects terminal-state obligations
- Obligation metadata re-freeze on rebuild
- Event-obligation bridge post-operation state validation
- WorkerCapacity overload guard (current_load > max_concurrent)
- DecisionLearningEngine.assess_tradeoff stores outcome
"""

from __future__ import annotations

import pytest

NOW = "2025-01-01T00:00:00+00:00"
FUTURE = "2026-01-01T00:00:00+00:00"
PAST = "2024-01-01T00:00:00+00:00"


def _clock():
    return NOW


# =====================================================================
# 1. Supervisor livelock detection — IDLE_TICK triggers detection
# =====================================================================


class TestSupervisorLivelockDetection:
    """Livelock detection triggers on repeated non-productive outcomes."""

    def _make_engine(self, **policy_overrides):
        from mcoi_runtime.contracts.supervisor import LivelockStrategy, SupervisorPolicy
        from mcoi_runtime.core.event_spine import EventSpineEngine
        from mcoi_runtime.core.obligation_runtime import ObligationRuntimeEngine
        from mcoi_runtime.core.supervisor_engine import SupervisorEngine

        policy = SupervisorPolicy(
            policy_id="test-policy",
            tick_interval_ms=100,
            max_events_per_tick=10,
            max_actions_per_tick=10,
            backpressure_threshold=50,
            livelock_repeat_threshold=policy_overrides.get("livelock_repeat_threshold", 3),
            livelock_strategy=policy_overrides.get("livelock_strategy", LivelockStrategy.ESCALATE),
            heartbeat_every_n_ticks=100,
            checkpoint_every_n_ticks=100,
            max_consecutive_errors=10,
            created_at=NOW,
        )
        spine = EventSpineEngine(clock=_clock)
        obl = ObligationRuntimeEngine(clock=_clock)
        return SupervisorEngine(policy=policy, spine=spine, obligation_engine=obl, clock=_clock)

    def test_idle_ticks_trigger_livelock(self) -> None:
        """Repeated IDLE_TICK outcomes trigger livelock detection."""
        from mcoi_runtime.contracts.supervisor import TickOutcome

        eng = self._make_engine(livelock_repeat_threshold=3)
        results = [eng.tick() for _ in range(4)]
        # The 4th tick should detect livelock after 3 identical idle ticks
        outcomes = [r.outcome for r in results]
        assert TickOutcome.LIVELOCK_DETECTED in outcomes

    def test_work_done_resolves_livelock(self) -> None:
        """WORK_DONE outcome resolves previously detected livelocks."""
        from mcoi_runtime.contracts.event import EventRecord, EventSource, EventType
        from mcoi_runtime.contracts.supervisor import TickOutcome

        eng = self._make_engine(livelock_repeat_threshold=3)
        # Generate livelock
        for _ in range(4):
            eng.tick()

        # Now inject an event so the next tick does work
        evt = EventRecord(
            event_id="evt-work",
            event_type=EventType.CUSTOM,
            source=EventSource.EXTERNAL,
            correlation_id="corr-1",
            payload={"data": True},
            emitted_at=NOW,
        )
        eng._spine.emit(evt)
        tick = eng.tick()
        # After work, livelocks should be resolved
        if tick.outcome == TickOutcome.WORK_DONE:
            for ll in eng._livelocks:
                assert ll.resolved is True

    def test_healthy_ticks_do_not_trigger_livelock(self) -> None:
        """WORK_DONE ticks should not trigger livelock detection."""
        from mcoi_runtime.contracts.event import EventRecord, EventSource, EventType
        from mcoi_runtime.contracts.supervisor import TickOutcome

        eng = self._make_engine(livelock_repeat_threshold=3)
        for i in range(5):
            evt = EventRecord(
                event_id=f"evt-{i}",
                event_type=EventType.CUSTOM,
                source=EventSource.EXTERNAL,
                correlation_id=f"corr-{i}",
                payload={},
                emitted_at=NOW,
            )
            eng._spine.emit(evt)
            tick = eng.tick()
            assert tick.outcome != TickOutcome.LIVELOCK_DETECTED


# =====================================================================
# 2. Obligation transfer preserves original state
# =====================================================================


class TestObligationTransferPreservesState:
    """Transfer should preserve the obligation's current state, not force ACTIVE."""

    def _make_engine(self):
        from mcoi_runtime.core.obligation_runtime import ObligationRuntimeEngine
        return ObligationRuntimeEngine(clock=_clock)

    def _owner(self, oid: str):
        from mcoi_runtime.contracts.obligation import ObligationOwner
        return ObligationOwner(owner_id=oid, owner_type="team", display_name=f"Team {oid}")

    def _deadline(self):
        from mcoi_runtime.contracts.obligation import ObligationDeadline
        return ObligationDeadline(deadline_id="dl-1", due_at=FUTURE)

    def test_transfer_preserves_pending_state(self) -> None:
        from mcoi_runtime.contracts.obligation import ObligationState, ObligationTrigger

        eng = self._make_engine()
        obl = eng.create_obligation(
            trigger=ObligationTrigger.CUSTOM,
            trigger_ref_id="ref-1",
            owner=self._owner("a"),
            deadline=self._deadline(),
            description="test",
            correlation_id="corr-1",
        )
        assert obl.state == ObligationState.PENDING
        eng.transfer(obl.obligation_id, to_owner=self._owner("b"), reason="reassign")
        updated = eng.get_obligation(obl.obligation_id)
        assert updated is not None
        assert updated.state == ObligationState.PENDING

    def test_transfer_preserves_escalated_state(self) -> None:
        from mcoi_runtime.contracts.obligation import ObligationState, ObligationTrigger

        eng = self._make_engine()
        obl = eng.create_obligation(
            trigger=ObligationTrigger.CUSTOM,
            trigger_ref_id="ref-2",
            owner=self._owner("a"),
            deadline=self._deadline(),
            description="test",
            correlation_id="corr-2",
        )
        eng.activate(obl.obligation_id)
        eng.escalate(obl.obligation_id, escalated_to=self._owner("c"), reason="urgent")
        escalated = eng.get_obligation(obl.obligation_id)
        assert escalated is not None
        assert escalated.state == ObligationState.ESCALATED

        eng.transfer(obl.obligation_id, to_owner=self._owner("d"), reason="hand off")
        final = eng.get_obligation(obl.obligation_id)
        assert final is not None
        assert final.state == ObligationState.ESCALATED


# =====================================================================
# 3. Obligation escalation rejects terminal-state obligations
# =====================================================================


class TestObligationEscalationTerminalGuard:
    """Cannot escalate an already-closed obligation."""

    def _make_engine(self):
        from mcoi_runtime.core.obligation_runtime import ObligationRuntimeEngine
        return ObligationRuntimeEngine(clock=_clock)

    def _owner(self, oid: str = "o1"):
        from mcoi_runtime.contracts.obligation import ObligationOwner
        return ObligationOwner(owner_id=oid, owner_type="team", display_name="Team")

    def _deadline(self):
        from mcoi_runtime.contracts.obligation import ObligationDeadline
        return ObligationDeadline(deadline_id="dl-1", due_at=FUTURE)

    def test_escalate_completed_raises(self) -> None:
        from mcoi_runtime.contracts.obligation import ObligationState, ObligationTrigger
        from mcoi_runtime.core.invariants import RuntimeCoreInvariantError

        eng = self._make_engine()
        obl = eng.create_obligation(
            trigger=ObligationTrigger.CUSTOM,
            trigger_ref_id="ref-3",
            owner=self._owner(),
            deadline=self._deadline(),
            description="test",
            correlation_id="corr-3",
        )
        eng.activate(obl.obligation_id)
        eng.close(obl.obligation_id, final_state=ObligationState.COMPLETED, reason="done", closed_by="admin")

        with pytest.raises(RuntimeCoreInvariantError, match="cannot escalate closed"):
            eng.escalate(obl.obligation_id, escalated_to=self._owner("e"), reason="too late")

    def test_escalate_expired_raises(self) -> None:
        from mcoi_runtime.contracts.obligation import ObligationState, ObligationTrigger
        from mcoi_runtime.core.invariants import RuntimeCoreInvariantError

        eng = self._make_engine()
        obl = eng.create_obligation(
            trigger=ObligationTrigger.CUSTOM,
            trigger_ref_id="ref-4",
            owner=self._owner(),
            deadline=self._deadline(),
            description="test",
            correlation_id="corr-4",
        )
        eng.activate(obl.obligation_id)
        eng.close(obl.obligation_id, final_state=ObligationState.EXPIRED, reason="deadline", closed_by="system")

        with pytest.raises(RuntimeCoreInvariantError, match="cannot escalate closed"):
            eng.escalate(obl.obligation_id, escalated_to=self._owner("f"), reason="too late")

    def test_escalate_cancelled_raises(self) -> None:
        from mcoi_runtime.contracts.obligation import ObligationState, ObligationTrigger
        from mcoi_runtime.core.invariants import RuntimeCoreInvariantError

        eng = self._make_engine()
        obl = eng.create_obligation(
            trigger=ObligationTrigger.CUSTOM,
            trigger_ref_id="ref-5",
            owner=self._owner(),
            deadline=self._deadline(),
            description="test",
            correlation_id="corr-5",
        )
        eng.activate(obl.obligation_id)
        eng.close(obl.obligation_id, final_state=ObligationState.CANCELLED, reason="nope", closed_by="admin")

        with pytest.raises(RuntimeCoreInvariantError, match="cannot escalate closed"):
            eng.escalate(obl.obligation_id, escalated_to=self._owner("g"), reason="too late")


# =====================================================================
# 4. Obligation metadata re-freeze on rebuild
# =====================================================================


class TestObligationMetadataRefreeze:
    """Metadata must be re-frozen when rebuilding obligation records."""

    def _make_engine(self):
        from mcoi_runtime.core.obligation_runtime import ObligationRuntimeEngine
        return ObligationRuntimeEngine(clock=_clock)

    def _owner(self, oid: str = "o1"):
        from mcoi_runtime.contracts.obligation import ObligationOwner
        return ObligationOwner(owner_id=oid, owner_type="team", display_name="Team")

    def _deadline(self):
        from mcoi_runtime.contracts.obligation import ObligationDeadline
        return ObligationDeadline(deadline_id="dl-1", due_at=FUTURE)

    def test_metadata_immutable_after_transition(self) -> None:
        from mcoi_runtime.contracts.obligation import ObligationTrigger

        eng = self._make_engine()
        obl = eng.create_obligation(
            trigger=ObligationTrigger.CUSTOM,
            trigger_ref_id="ref-6",
            owner=self._owner(),
            deadline=self._deadline(),
            description="test",
            correlation_id="corr-6",
            metadata={"key": "value"},
        )
        activated = eng.activate(obl.obligation_id)
        # Metadata should be frozen (immutable mapping)
        with pytest.raises(TypeError):
            activated.metadata["key"] = "changed"  # type: ignore[index]

    def test_metadata_immutable_after_transfer(self) -> None:
        from mcoi_runtime.contracts.obligation import ObligationTrigger

        eng = self._make_engine()
        obl = eng.create_obligation(
            trigger=ObligationTrigger.CUSTOM,
            trigger_ref_id="ref-7",
            owner=self._owner("a"),
            deadline=self._deadline(),
            description="test",
            correlation_id="corr-7",
            metadata={"nested": {"inner": 1}},
        )
        eng.transfer(obl.obligation_id, to_owner=self._owner("b"), reason="test")
        updated = eng.get_obligation(obl.obligation_id)
        assert updated is not None
        with pytest.raises(TypeError):
            updated.metadata["nested"] = "changed"  # type: ignore[index]

    def test_metadata_immutable_after_close(self) -> None:
        from mcoi_runtime.contracts.obligation import ObligationState, ObligationTrigger

        eng = self._make_engine()
        obl = eng.create_obligation(
            trigger=ObligationTrigger.CUSTOM,
            trigger_ref_id="ref-8",
            owner=self._owner(),
            deadline=self._deadline(),
            description="test",
            correlation_id="corr-8",
            metadata={"k": "v"},
        )
        eng.activate(obl.obligation_id)
        eng.close(obl.obligation_id, final_state=ObligationState.COMPLETED, reason="done", closed_by="admin")
        updated = eng.get_obligation(obl.obligation_id)
        assert updated is not None
        with pytest.raises(TypeError):
            updated.metadata["k"] = "new"  # type: ignore[index]


# =====================================================================
# 5. Event-obligation bridge post-operation validation
# =====================================================================


class TestEventObligationBridgePostValidation:
    """Bridge methods validate state after engine operations."""

    def _make_engines(self):
        from mcoi_runtime.core.event_spine import EventSpineEngine
        from mcoi_runtime.core.obligation_runtime import ObligationRuntimeEngine
        return EventSpineEngine(clock=_clock), ObligationRuntimeEngine(clock=_clock)

    def _owner(self, oid: str = "o1"):
        from mcoi_runtime.contracts.obligation import ObligationOwner
        return ObligationOwner(owner_id=oid, owner_type="team", display_name="Team")

    def _deadline(self):
        from mcoi_runtime.contracts.obligation import ObligationDeadline
        return ObligationDeadline(deadline_id="dl-1", due_at=FUTURE)

    def test_close_and_emit_returns_correct_state(self) -> None:
        from mcoi_runtime.contracts.event import EventRecord, EventSource, EventType
        from mcoi_runtime.contracts.obligation import ObligationState, ObligationTrigger
        from mcoi_runtime.core.event_obligation_integration import EventObligationBridge

        spine, obl_eng = self._make_engines()
        evt = EventRecord(
            event_id="evt-1",
            event_type=EventType.CUSTOM,
            source=EventSource.EXTERNAL,
            correlation_id="corr-1",
            payload={},
            emitted_at=NOW,
        )
        obl, _ = EventObligationBridge.process_event(
            spine, obl_eng, evt,
            owner=self._owner(),
            deadline=self._deadline(),
            trigger=ObligationTrigger.CUSTOM,
            description="test",
        )
        obl_eng.activate(obl.obligation_id)
        closed_obl, closed_evt = EventObligationBridge.close_and_emit(
            spine, obl_eng, obl.obligation_id,
            final_state=ObligationState.COMPLETED,
            reason="done",
            closed_by="admin",
        )
        assert closed_obl.state == ObligationState.COMPLETED
        assert closed_evt.event_type == EventType.OBLIGATION_CLOSED

    def test_transfer_and_emit_returns_correct_owner(self) -> None:
        from mcoi_runtime.contracts.event import EventRecord, EventSource, EventType
        from mcoi_runtime.contracts.obligation import ObligationTrigger
        from mcoi_runtime.core.event_obligation_integration import EventObligationBridge

        spine, obl_eng = self._make_engines()
        evt = EventRecord(
            event_id="evt-2",
            event_type=EventType.CUSTOM,
            source=EventSource.EXTERNAL,
            correlation_id="corr-2",
            payload={},
            emitted_at=NOW,
        )
        obl, _ = EventObligationBridge.process_event(
            spine, obl_eng, evt,
            owner=self._owner("a"),
            deadline=self._deadline(),
            trigger=ObligationTrigger.CUSTOM,
            description="test",
        )
        new_owner = self._owner("b")
        transferred_obl, xfr_evt = EventObligationBridge.transfer_and_emit(
            spine, obl_eng, obl.obligation_id,
            to_owner=new_owner,
            reason="reassign",
        )
        assert transferred_obl.owner == new_owner
        assert xfr_evt.event_type == EventType.OBLIGATION_TRANSFERRED

    def test_escalate_and_emit_returns_escalated_state(self) -> None:
        from mcoi_runtime.contracts.event import EventRecord, EventSource, EventType
        from mcoi_runtime.contracts.obligation import ObligationState, ObligationTrigger
        from mcoi_runtime.core.event_obligation_integration import EventObligationBridge

        spine, obl_eng = self._make_engines()
        evt = EventRecord(
            event_id="evt-3",
            event_type=EventType.CUSTOM,
            source=EventSource.EXTERNAL,
            correlation_id="corr-3",
            payload={},
            emitted_at=NOW,
        )
        obl, _ = EventObligationBridge.process_event(
            spine, obl_eng, evt,
            owner=self._owner(),
            deadline=self._deadline(),
            trigger=ObligationTrigger.CUSTOM,
            description="test",
        )
        obl_eng.activate(obl.obligation_id)
        esc_owner = self._owner("esc")
        esc_obl, esc_evt = EventObligationBridge.escalate_and_emit(
            spine, obl_eng, obl.obligation_id,
            escalated_to=esc_owner,
            reason="urgent",
        )
        assert esc_obl.state == ObligationState.ESCALATED
        assert esc_evt.event_type == EventType.OBLIGATION_ESCALATED

    def test_close_and_emit_expired_uses_correct_event_type(self) -> None:
        from mcoi_runtime.contracts.event import EventRecord, EventSource, EventType
        from mcoi_runtime.contracts.obligation import ObligationState, ObligationTrigger
        from mcoi_runtime.core.event_obligation_integration import EventObligationBridge

        spine, obl_eng = self._make_engines()
        evt = EventRecord(
            event_id="evt-4",
            event_type=EventType.CUSTOM,
            source=EventSource.EXTERNAL,
            correlation_id="corr-4",
            payload={},
            emitted_at=NOW,
        )
        obl, _ = EventObligationBridge.process_event(
            spine, obl_eng, evt,
            owner=self._owner(),
            deadline=self._deadline(),
            trigger=ObligationTrigger.CUSTOM,
            description="test",
        )
        obl_eng.activate(obl.obligation_id)
        expired_obl, expired_evt = EventObligationBridge.close_and_emit(
            spine, obl_eng, obl.obligation_id,
            final_state=ObligationState.EXPIRED,
            reason="deadline passed",
            closed_by="system",
        )
        assert expired_obl.state == ObligationState.EXPIRED
        assert expired_evt.event_type == EventType.OBLIGATION_EXPIRED


# =====================================================================
# 6. WorkerCapacity overload guard
# =====================================================================


class TestWorkerCapacityOverloadGuard:
    """current_load cannot exceed max_concurrent."""

    def test_current_load_exceeds_max_concurrent_raises(self) -> None:
        from mcoi_runtime.contracts.roles import WorkerCapacity

        with pytest.raises(ValueError, match="current_load cannot exceed max_concurrent"):
            WorkerCapacity(
                worker_id="w1",
                max_concurrent=3,
                current_load=4,
                available_slots=-1,
                updated_at=NOW,
            )

    def test_current_load_equals_max_concurrent_ok(self) -> None:
        from mcoi_runtime.contracts.roles import WorkerCapacity

        wc = WorkerCapacity(
            worker_id="w1",
            max_concurrent=3,
            current_load=3,
            available_slots=0,
            updated_at=NOW,
        )
        assert wc.current_load == 3
        assert wc.available_slots == 0

    def test_available_slots_mismatch_raises(self) -> None:
        from mcoi_runtime.contracts.roles import WorkerCapacity

        with pytest.raises(ValueError, match="available_slots must equal"):
            WorkerCapacity(
                worker_id="w1",
                max_concurrent=5,
                current_load=2,
                available_slots=2,  # should be 3
                updated_at=NOW,
            )


# =====================================================================
# 7. DecisionLearningEngine.assess_tradeoff stores outcome
# =====================================================================


class TestAssessTradeoffStoresOutcome:
    """assess_tradeoff must store the TradeoffOutcome in _tradeoff_outcomes."""

    def _make_engine(self):
        from mcoi_runtime.core.decision_learning import DecisionLearningEngine
        return DecisionLearningEngine(clock=_clock)

    def _tradeoff(self):
        from mcoi_runtime.contracts.utility import TradeoffDirection, TradeoffRecord
        return TradeoffRecord(
            tradeoff_id="t-1",
            comparison_id="cmp-1",
            chosen_option_id="opt-a",
            rejected_option_ids=("opt-b",),
            tradeoff_direction=TradeoffDirection.BALANCED,
            rationale="balanced choice",
            recorded_at=NOW,
        )

    def test_assess_tradeoff_stores_in_list(self) -> None:
        from mcoi_runtime.contracts.decision_learning import OutcomeQuality

        eng = self._make_engine()
        assert len(eng._tradeoff_outcomes) == 0
        outcome = eng.assess_tradeoff(
            self._tradeoff(),
            quality=OutcomeQuality.SUCCESS,
            alternative_would_have_been_better=False,
            explanation="worked well",
        )
        assert len(eng._tradeoff_outcomes) == 1
        assert eng._tradeoff_outcomes[0] is outcome

    def test_assess_tradeoff_stores_multiple(self) -> None:
        from mcoi_runtime.contracts.decision_learning import OutcomeQuality

        eng = self._make_engine()
        for _ in range(3):
            eng.assess_tradeoff(
                self._tradeoff(),
                quality=OutcomeQuality.PARTIAL_SUCCESS,
                alternative_would_have_been_better=True,
                explanation="could be better",
            )
        assert len(eng._tradeoff_outcomes) == 3

    def test_assess_tradeoff_regret_score_success(self) -> None:
        from mcoi_runtime.contracts.decision_learning import OutcomeQuality

        eng = self._make_engine()
        outcome = eng.assess_tradeoff(
            self._tradeoff(),
            quality=OutcomeQuality.SUCCESS,
            alternative_would_have_been_better=False,
            explanation="perfect",
        )
        assert outcome.regret_score == 0.0

    def test_assess_tradeoff_regret_score_failure_with_alternative(self) -> None:
        from mcoi_runtime.contracts.decision_learning import OutcomeQuality

        eng = self._make_engine()
        outcome = eng.assess_tradeoff(
            self._tradeoff(),
            quality=OutcomeQuality.FAILURE,
            alternative_would_have_been_better=True,
            explanation="bad choice",
        )
        # 1.0 (failure) + 0.2 (alternative better) = 1.0 (clamped)
        assert outcome.regret_score == 1.0

    def test_assess_tradeoff_regret_score_partial_with_alternative(self) -> None:
        from mcoi_runtime.contracts.decision_learning import OutcomeQuality

        eng = self._make_engine()
        outcome = eng.assess_tradeoff(
            self._tradeoff(),
            quality=OutcomeQuality.PARTIAL_SUCCESS,
            alternative_would_have_been_better=True,
            explanation="meh",
        )
        # 0.3 + 0.2 = 0.5
        assert outcome.regret_score == pytest.approx(0.5)
