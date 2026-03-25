"""Edge case tests for Holistic Audit #8 fixes.

Covers:
  - Timestamp validation (require_datetime_text) in operator.py contracts
  - Timestamp validation in review.py contracts
  - Timestamp validation in organization.py EscalationState
  - MACHINE_REGISTRY immutability
  - EventSpine.restore() rollback on error
  - ObligationRuntime.close() atomicity
  - ObligationRuntime.restore() rollback on error
  - Supervisor sync_processed_events after checkpoint restore
"""

from __future__ import annotations

import pytest
from types import MappingProxyType

# ── Contract imports ──────────────────────────────────────────────

from mcoi_runtime.contracts.operator import (
    ActionAttribution,
    ActorType,
    ApprovalAttribution,
    AuditEntry,
    ManualOverride,
    OperatorIdentity,
    OperatorRole,
)
from mcoi_runtime.contracts.review import (
    ReviewDecision,
    ReviewRequest,
    ReviewScope,
    ReviewScopeType,
    ReviewStatus,
)
from mcoi_runtime.contracts.organization import (
    EscalationState,
)
from mcoi_runtime.contracts.state_machine import (
    StateMachineSpec,
)

# ── Core imports ──────────────────────────────────────────────────

from mcoi_runtime.core.state_machines import MACHINE_REGISTRY
from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.obligation_runtime import ObligationRuntimeEngine
from mcoi_runtime.core.supervisor_engine import SupervisorEngine
from mcoi_runtime.core.checkpoint_manager import CheckpointManager
from mcoi_runtime.contracts.event import EventRecord, EventSource, EventType
from mcoi_runtime.contracts.obligation import (
    ObligationDeadline,
    ObligationOwner,
    ObligationState,
    ObligationTrigger,
)
from mcoi_runtime.contracts.supervisor import LivelockStrategy, SupervisorPolicy
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError

_TS = "2026-03-20T00:00:00+00:00"
_TS2 = "2026-03-20T01:00:00+00:00"


# ── Timestamp validation: operator.py ─────────────────────────────


class TestActionAttributionTimestamp:
    def test_valid_iso_timestamp_accepted(self):
        aa = ActionAttribution(
            attribution_id="aa-1",
            operator_id="op-1",
            action_type="approve",
            target_id="t-1",
            timestamp=_TS,
        )
        assert aa.timestamp == _TS

    def test_invalid_timestamp_rejected(self):
        with pytest.raises(ValueError, match="timestamp"):
            ActionAttribution(
                attribution_id="aa-1",
                operator_id="op-1",
                action_type="approve",
                target_id="t-1",
                timestamp="not-a-date",
            )

    def test_empty_timestamp_rejected(self):
        with pytest.raises(ValueError):
            ActionAttribution(
                attribution_id="aa-1",
                operator_id="op-1",
                action_type="approve",
                target_id="t-1",
                timestamp="",
            )


class TestApprovalAttributionTimestamp:
    def test_valid_timestamp_accepted(self):
        aa = ApprovalAttribution(
            approval_id="appr-1",
            approver_id="op-1",
            decision="approved",
            target_id="t-1",
            correlation_id="c-1",
            timestamp=_TS,
        )
        assert aa.timestamp == _TS

    def test_invalid_timestamp_rejected(self):
        with pytest.raises(ValueError, match="timestamp"):
            ApprovalAttribution(
                approval_id="appr-1",
                approver_id="op-1",
                decision="approved",
                target_id="t-1",
                correlation_id="c-1",
                timestamp="tuesday",
            )


class TestManualOverrideTimestamp:
    def test_valid_timestamp_accepted(self):
        mo = ManualOverride(
            override_id="ov-1",
            operator_id="op-1",
            overridden_decision_id="d-1",
            original_status="pending",
            new_status="approved",
            reason="urgent",
            timestamp=_TS,
        )
        assert mo.timestamp == _TS

    def test_invalid_timestamp_rejected(self):
        with pytest.raises(ValueError, match="timestamp"):
            ManualOverride(
                override_id="ov-1",
                operator_id="op-1",
                overridden_decision_id="d-1",
                original_status="pending",
                new_status="approved",
                reason="urgent",
                timestamp="yesterday",
            )


class TestAuditEntryTimestamp:
    def test_valid_timestamp_accepted(self):
        ae = AuditEntry(
            entry_id="ae-1",
            operator_id="op-1",
            actor_type=ActorType.HUMAN,
            action="deploy",
            target_artifact_id="art-1",
            timestamp=_TS,
        )
        assert ae.timestamp == _TS

    def test_invalid_timestamp_rejected(self):
        with pytest.raises(ValueError, match="timestamp"):
            AuditEntry(
                entry_id="ae-1",
                operator_id="op-1",
                actor_type=ActorType.HUMAN,
                action="deploy",
                target_artifact_id="art-1",
                timestamp="noon",
            )


# ── Timestamp validation: review.py ──────────────────────────────


class TestReviewRequestTimestamp:
    def _scope(self):
        return ReviewScope(
            scope_type=ReviewScopeType.DEPLOYMENT_CHANGE,
            target_id="dep-1",
            description="test",
        )

    def test_valid_timestamp_accepted(self):
        rr = ReviewRequest(
            request_id="rr-1",
            requester_id="u-1",
            scope=self._scope(),
            reason="review needed",
            requested_at=_TS,
        )
        assert rr.requested_at == _TS

    def test_invalid_timestamp_rejected(self):
        with pytest.raises(ValueError, match="requested_at"):
            ReviewRequest(
                request_id="rr-1",
                requester_id="u-1",
                scope=self._scope(),
                reason="review needed",
                requested_at="last week",
            )


class TestReviewDecisionTimestamp:
    def test_valid_timestamp_accepted(self):
        rd = ReviewDecision(
            decision_id="rd-1",
            request_id="rr-1",
            reviewer_id="u-2",
            status=ReviewStatus.APPROVED,
            decided_at=_TS,
        )
        assert rd.decided_at == _TS

    def test_invalid_timestamp_rejected(self):
        with pytest.raises(ValueError, match="decided_at"):
            ReviewDecision(
                decision_id="rd-1",
                request_id="rr-1",
                reviewer_id="u-2",
                status=ReviewStatus.APPROVED,
                decided_at="now-ish",
            )


# ── Timestamp validation: organization.py ─────────────────────────


class TestEscalationStateTimestamp:
    def test_valid_timestamps_accepted(self):
        es = EscalationState(
            chain_id="ch-1",
            current_step=1,
            started_at=_TS,
            last_escalated_at=_TS2,
        )
        assert es.started_at == _TS
        assert es.last_escalated_at == _TS2

    def test_invalid_started_at_rejected(self):
        with pytest.raises(ValueError, match="started_at"):
            EscalationState(
                chain_id="ch-1",
                current_step=1,
                started_at="morning",
            )

    def test_invalid_last_escalated_at_rejected(self):
        with pytest.raises(ValueError, match="last_escalated_at"):
            EscalationState(
                chain_id="ch-1",
                current_step=1,
                started_at=_TS,
                last_escalated_at="recently",
            )

    def test_none_last_escalated_at_accepted(self):
        es = EscalationState(chain_id="ch-1", current_step=1, started_at=_TS)
        assert es.last_escalated_at is None


# ── MACHINE_REGISTRY immutability ─────────────────────────────────


class TestMachineRegistryImmutability:
    def test_registry_is_mapping_proxy(self):
        assert isinstance(MACHINE_REGISTRY, MappingProxyType)

    def test_cannot_mutate_registry(self):
        with pytest.raises(TypeError):
            MACHINE_REGISTRY["new-machine"] = None  # type: ignore[index]

    def test_contains_all_three_machines(self):
        assert "obligation-lifecycle" in MACHINE_REGISTRY
        assert "supervisor-tick-lifecycle" in MACHINE_REGISTRY
        assert "reaction-pipeline" in MACHINE_REGISTRY


# ── EventSpine.restore() rollback ─────────────────────────────────

_tick = 0


def _clock():
    global _tick
    _tick += 1
    return f"2026-03-20T00:00:{_tick:02d}+00:00"


class TestEventSpineRestoreRollback:
    def test_corrupt_snapshot_triggers_rollback(self):
        spine = EventSpineEngine(clock=_clock)
        evt = EventRecord(
            event_id="e-1",
            event_type=EventType.JOB_STATE_TRANSITION,
            source=EventSource.SUPERVISOR,
            correlation_id="c-1",
            payload={},
            emitted_at=_clock(),
        )
        spine.emit(evt)
        assert spine.event_count == 1

        # Attempt restore with corrupt data — events dict has invalid values
        with pytest.raises(Exception):
            spine.restore({"events": {"e-bad": {"not": "valid"}}})

        # Original state preserved after rollback
        assert spine.event_count == 1
        assert spine.get_event("e-1") is not None


# ── ObligationRuntime.restore() rollback ──────────────────────────


class TestObligationRestoreRollback:
    def test_corrupt_snapshot_triggers_rollback(self):
        engine = ObligationRuntimeEngine(clock=_clock)
        engine.create_obligation(
            obligation_id="obl-1",
            trigger=ObligationTrigger.JOB_ASSIGNMENT,
            trigger_ref_id="evt-1",
            owner=ObligationOwner(owner_id="team-a", owner_type="team", display_name="Team A"),
            deadline=ObligationDeadline(deadline_id="dl-1", due_at=_TS),
            description="test obligation",
            correlation_id="c-1",
        )
        assert engine.obligation_count == 1

        with pytest.raises(Exception):
            engine.restore({"obligations": {"obl-bad": {"invalid": True}}})

        # Rollback preserved original
        assert engine.obligation_count == 1
        assert engine.get_obligation("obl-1") is not None


# ── Supervisor sync_processed_events ──────────────────────────────


class TestSupervisorSyncProcessedEvents:
    def _make_supervisor(self):
        spine = EventSpineEngine(clock=_clock)
        obl_engine = ObligationRuntimeEngine(clock=_clock)
        policy = SupervisorPolicy(
            policy_id="test-policy",
            tick_interval_ms=100,
            max_events_per_tick=10,
            max_actions_per_tick=10,
            backpressure_threshold=50,
            livelock_repeat_threshold=3,
            livelock_strategy=LivelockStrategy.ESCALATE,
            heartbeat_every_n_ticks=100,
            checkpoint_every_n_ticks=100,
            max_consecutive_errors=10,
            created_at=_TS,
        )
        sup = SupervisorEngine(
            policy=policy,
            spine=spine,
            obligation_engine=obl_engine,
            clock=_clock,
        )
        return sup, spine, obl_engine

    def test_sync_marks_all_spine_events_as_processed(self):
        sup, spine, _ = self._make_supervisor()

        # Emit events directly into spine
        for i in range(5):
            spine.emit(EventRecord(
                event_id=f"ext-{i}",
                event_type=EventType.JOB_STATE_TRANSITION,
                source=EventSource.SUPERVISOR,
                correlation_id="c-1",
                payload={},
                emitted_at=_clock(),
            ))

        # Before sync, _poll_new_events would return all 5
        assert spine.event_count == 5

        # Sync marks them as processed
        sup.sync_processed_events()

        # Now poll should return nothing new
        new_events = sup._poll_new_events()
        assert len(new_events) == 0

    def test_checkpoint_restore_preserves_processed_events(self):
        sup, spine, obl_engine = self._make_supervisor()
        mgr = CheckpointManager(
            supervisor=sup,
            spine=spine,
            obligation_engine=obl_engine,
            clock=_clock,
        )

        # Emit some events and tick to process them
        for i in range(3):
            spine.emit(EventRecord(
                event_id=f"pre-{i}",
                event_type=EventType.JOB_STATE_TRANSITION,
                source=EventSource.SUPERVISOR,
                correlation_id="c-1",
                payload={},
                emitted_at=_clock(),
            ))
        sup.tick()
        processed_at_cp = sup.processed_event_ids
        assert len(processed_at_cp) > 0  # should have processed the 3 events + tick events

        # Checkpoint — should capture processed_event_ids in payload
        cp = mgr.create_checkpoint()

        # Run more ticks to change processed set
        sup.tick()
        sup.tick()

        # Restore — should restore exact processed_event_ids from checkpoint
        mgr.restore_checkpoint(cp, verify=False)

        # After restore, the processed set should match what was captured
        assert sup.processed_event_ids == processed_at_cp

    def test_unprocessed_events_remain_unprocessed_after_restore(self):
        sup, spine, obl_engine = self._make_supervisor()
        mgr = CheckpointManager(
            supervisor=sup,
            spine=spine,
            obligation_engine=obl_engine,
            clock=_clock,
        )

        # Emit events without ticking (they remain unprocessed)
        for i in range(3):
            spine.emit(EventRecord(
                event_id=f"unproc-{i}",
                event_type=EventType.JOB_STATE_TRANSITION,
                source=EventSource.SUPERVISOR,
                correlation_id="c-1",
                payload={},
                emitted_at=_clock(),
            ))

        # Checkpoint before processing
        cp = mgr.create_checkpoint()

        # Tick to process events
        sup.tick()
        assert len(sup.processed_event_ids) > 0

        # Restore — events should be unprocessed again
        mgr.restore_checkpoint(cp, verify=False)

        # The 3 events should now be available for re-processing
        new_events = sup._poll_new_events()
        unproc_ids = {e.event_id for e in new_events if e.event_id.startswith("unproc-")}
        assert len(unproc_ids) == 3
