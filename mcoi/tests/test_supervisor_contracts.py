"""Contract-level tests for Phase 36 supervisor contracts.

Tests all enums, frozen dataclasses, and validation invariants.
"""

from __future__ import annotations

import pytest

NOW = "2025-01-01T00:00:00+00:00"


# =====================================================================
# Enum coverage
# =====================================================================


class TestSupervisorEnums:
    def test_supervisor_phase_values(self) -> None:
        from mcoi_runtime.contracts.supervisor import SupervisorPhase

        assert len(SupervisorPhase) == 13
        assert SupervisorPhase.IDLE == "idle"
        assert SupervisorPhase.PAUSED == "paused"
        assert SupervisorPhase.HALTED == "halted"

    def test_tick_outcome_values(self) -> None:
        from mcoi_runtime.contracts.supervisor import TickOutcome

        assert len(TickOutcome) == 8
        assert TickOutcome.HEALTHY == "healthy"
        assert TickOutcome.LIVELOCK_DETECTED == "livelock_detected"

    def test_livelock_strategy_values(self) -> None:
        from mcoi_runtime.contracts.supervisor import LivelockStrategy

        assert len(LivelockStrategy) == 4
        assert LivelockStrategy.ESCALATE == "escalate"

    def test_checkpoint_status_values(self) -> None:
        from mcoi_runtime.contracts.supervisor import CheckpointStatus

        assert len(CheckpointStatus) == 3
        assert CheckpointStatus.VALID == "valid"

    def test_event_type_supervisor_entries(self) -> None:
        from mcoi_runtime.contracts.event import EventType

        assert EventType.SUPERVISOR_HEARTBEAT == "supervisor_heartbeat"
        assert EventType.SUPERVISOR_LIVELOCK == "supervisor_livelock"
        assert EventType.SUPERVISOR_CHECKPOINT == "supervisor_checkpoint"
        assert EventType.SUPERVISOR_HALTED == "supervisor_halted"

    def test_event_source_supervisor(self) -> None:
        from mcoi_runtime.contracts.event import EventSource

        assert EventSource.SUPERVISOR == "supervisor"


# =====================================================================
# SupervisorPolicy
# =====================================================================


class TestSupervisorPolicy:
    def _policy(self, **overrides):
        from mcoi_runtime.contracts.supervisor import LivelockStrategy, SupervisorPolicy

        defaults = dict(
            policy_id="p1",
            tick_interval_ms=1000,
            max_events_per_tick=100,
            max_actions_per_tick=50,
            backpressure_threshold=200,
            livelock_repeat_threshold=5,
            livelock_strategy=LivelockStrategy.ESCALATE,
            heartbeat_every_n_ticks=10,
            checkpoint_every_n_ticks=25,
            max_consecutive_errors=3,
            created_at=NOW,
        )
        defaults.update(overrides)
        return SupervisorPolicy(**defaults)

    def test_valid_policy(self) -> None:
        p = self._policy()
        assert p.policy_id == "p1"
        assert p.tick_interval_ms == 1000

    def test_empty_policy_id_rejected(self) -> None:
        with pytest.raises(ValueError, match="policy_id"):
            self._policy(policy_id="")

    def test_zero_tick_interval_rejected(self) -> None:
        with pytest.raises(ValueError, match="tick_interval_ms"):
            self._policy(tick_interval_ms=0)

    def test_negative_max_events_rejected(self) -> None:
        with pytest.raises(ValueError, match="max_events_per_tick"):
            self._policy(max_events_per_tick=-1)

    def test_invalid_created_at_rejected(self) -> None:
        with pytest.raises(ValueError, match="created_at"):
            self._policy(created_at="bad")


# =====================================================================
# SupervisorDecision
# =====================================================================


class TestSupervisorDecision:
    def _decision(self, **overrides):
        from mcoi_runtime.contracts.supervisor import SupervisorDecision

        defaults = dict(
            decision_id="d1",
            action_type="activate_obligation",
            target_id="obl-1",
            reason="pending obligation",
            governance_approved=True,
            decided_at=NOW,
        )
        defaults.update(overrides)
        return SupervisorDecision(**defaults)

    def test_valid_decision(self) -> None:
        d = self._decision()
        assert d.governance_approved is True

    def test_empty_action_type_rejected(self) -> None:
        with pytest.raises(ValueError, match="action_type"):
            self._decision(action_type="")

    def test_non_bool_governance_approved_rejected(self) -> None:
        with pytest.raises(ValueError, match="governance_approved"):
            self._decision(governance_approved="yes")

    def test_metadata_frozen(self) -> None:
        d = self._decision(metadata={"k": "v"})
        assert d.metadata["k"] == "v"
        with pytest.raises(TypeError):
            d.metadata["k2"] = "v2"  # type: ignore[index]


# =====================================================================
# SupervisorTick
# =====================================================================


class TestSupervisorTick:
    def _tick(self, **overrides):
        from mcoi_runtime.contracts.supervisor import SupervisorPhase, SupervisorTick, TickOutcome

        defaults = dict(
            tick_id="t1",
            tick_number=1,
            phase_sequence=(SupervisorPhase.POLLING, SupervisorPhase.ACTING),
            events_polled=5,
            obligations_evaluated=2,
            deadlines_checked=1,
            reactions_fired=3,
            decisions=(),
            outcome=TickOutcome.WORK_DONE,
            started_at=NOW,
            completed_at=NOW,
        )
        defaults.update(overrides)
        return SupervisorTick(**defaults)

    def test_valid_tick(self) -> None:
        t = self._tick()
        assert t.tick_number == 1
        assert t.events_polled == 5

    def test_negative_tick_number_rejected(self) -> None:
        with pytest.raises(ValueError, match="tick_number"):
            self._tick(tick_number=-1)

    def test_invalid_phase_rejected(self) -> None:
        with pytest.raises(ValueError, match="phase"):
            self._tick(phase_sequence=("not_a_phase",))

    def test_invalid_decision_type_rejected(self) -> None:
        with pytest.raises(ValueError, match="decision"):
            self._tick(decisions=("not_a_decision",))

    def test_invalid_started_at_rejected(self) -> None:
        with pytest.raises(ValueError, match="started_at"):
            self._tick(started_at="bad")


# =====================================================================
# SupervisorHealth
# =====================================================================


class TestSupervisorHealth:
    def _health(self, **overrides):
        from mcoi_runtime.contracts.supervisor import SupervisorHealth, SupervisorPhase

        defaults = dict(
            health_id="h1",
            tick_number=10,
            phase=SupervisorPhase.IDLE,
            consecutive_errors=0,
            consecutive_idle_ticks=0,
            backpressure_active=False,
            livelock_detected=False,
            open_obligations=3,
            pending_events=5,
            overall_confidence=0.95,
            assessed_at=NOW,
        )
        defaults.update(overrides)
        return SupervisorHealth(**defaults)

    def test_valid_health(self) -> None:
        h = self._health()
        assert h.overall_confidence == 0.95

    def test_confidence_out_of_range_rejected(self) -> None:
        with pytest.raises(ValueError, match="overall_confidence"):
            self._health(overall_confidence=1.5)

    def test_negative_open_obligations_rejected(self) -> None:
        with pytest.raises(ValueError, match="open_obligations"):
            self._health(open_obligations=-1)

    def test_non_bool_backpressure_rejected(self) -> None:
        with pytest.raises(ValueError, match="backpressure_active"):
            self._health(backpressure_active="yes")


# =====================================================================
# RuntimeHeartbeat
# =====================================================================


class TestRuntimeHeartbeat:
    def _hb(self, **overrides):
        from mcoi_runtime.contracts.supervisor import RuntimeHeartbeat, SupervisorPhase, TickOutcome

        defaults = dict(
            heartbeat_id="hb1",
            tick_number=10,
            phase=SupervisorPhase.IDLE,
            outcome_of_last_tick=TickOutcome.WORK_DONE,
            open_obligations=2,
            pending_events=0,
            uptime_ticks=10,
            emitted_at=NOW,
        )
        defaults.update(overrides)
        return RuntimeHeartbeat(**defaults)

    def test_valid_heartbeat(self) -> None:
        hb = self._hb()
        assert hb.uptime_ticks == 10

    def test_empty_heartbeat_id_rejected(self) -> None:
        with pytest.raises(ValueError, match="heartbeat_id"):
            self._hb(heartbeat_id="")

    def test_negative_uptime_rejected(self) -> None:
        with pytest.raises(ValueError, match="uptime_ticks"):
            self._hb(uptime_ticks=-1)


# =====================================================================
# SupervisorCheckpoint
# =====================================================================


class TestSupervisorCheckpoint:
    def _cp(self, **overrides):
        from mcoi_runtime.contracts.supervisor import (
            CheckpointStatus,
            SupervisorCheckpoint,
            SupervisorPhase,
            TickOutcome,
        )

        defaults = dict(
            checkpoint_id="cp1",
            tick_number=25,
            phase=SupervisorPhase.IDLE,
            status=CheckpointStatus.VALID,
            open_obligation_ids=("obl-1",),
            pending_event_count=3,
            consecutive_errors=0,
            consecutive_idle_ticks=0,
            recent_tick_outcomes=(TickOutcome.WORK_DONE, TickOutcome.IDLE_TICK),
            state_hash="abc123",
            created_at=NOW,
        )
        defaults.update(overrides)
        return SupervisorCheckpoint(**defaults)

    def test_valid_checkpoint(self) -> None:
        cp = self._cp()
        assert cp.tick_number == 25
        assert cp.state_hash == "abc123"

    def test_empty_state_hash_rejected(self) -> None:
        with pytest.raises(ValueError, match="state_hash"):
            self._cp(state_hash="")

    def test_invalid_obligation_id_rejected(self) -> None:
        with pytest.raises(ValueError, match="open_obligation_id"):
            self._cp(open_obligation_ids=("",))

    def test_invalid_tick_outcome_rejected(self) -> None:
        with pytest.raises(ValueError, match="recent_tick_outcome"):
            self._cp(recent_tick_outcomes=("bad",))

    def test_empty_obligations_ok(self) -> None:
        cp = self._cp(open_obligation_ids=())
        assert cp.open_obligation_ids == ()


# =====================================================================
# LivelockRecord
# =====================================================================


class TestLivelockRecord:
    def _ll(self, **overrides):
        from mcoi_runtime.contracts.supervisor import LivelockRecord, LivelockStrategy

        defaults = dict(
            livelock_id="ll1",
            tick_number=50,
            repeated_pattern="idle_tick",
            repeat_count=5,
            strategy_applied=LivelockStrategy.ESCALATE,
            resolved=False,
            detected_at=NOW,
        )
        defaults.update(overrides)
        return LivelockRecord(**defaults)

    def test_valid_livelock(self) -> None:
        ll = self._ll()
        assert ll.repeat_count == 5

    def test_empty_pattern_rejected(self) -> None:
        with pytest.raises(ValueError, match="repeated_pattern"):
            self._ll(repeated_pattern="")

    def test_zero_repeat_count_rejected(self) -> None:
        with pytest.raises(ValueError, match="repeat_count"):
            self._ll(repeat_count=0)

    def test_non_bool_resolved_rejected(self) -> None:
        with pytest.raises(ValueError, match="resolved"):
            self._ll(resolved="no")

    def test_resolution_detail_optional(self) -> None:
        ll = self._ll(resolution_detail="paused and recovered")
        assert ll.resolution_detail == "paused and recovered"


# =====================================================================
# Serialization
# =====================================================================


class TestSupervisorSerialization:
    def test_policy_to_dict(self) -> None:
        from mcoi_runtime.contracts.supervisor import LivelockStrategy, SupervisorPolicy

        p = SupervisorPolicy(
            policy_id="p1",
            tick_interval_ms=1000,
            max_events_per_tick=100,
            max_actions_per_tick=50,
            backpressure_threshold=200,
            livelock_repeat_threshold=5,
            livelock_strategy=LivelockStrategy.ESCALATE,
            heartbeat_every_n_ticks=10,
            checkpoint_every_n_ticks=25,
            max_consecutive_errors=3,
            created_at=NOW,
        )
        d = p.to_dict()
        assert d["policy_id"] == "p1"
        assert d["tick_interval_ms"] == 1000

    def test_tick_to_json(self) -> None:
        import json

        from mcoi_runtime.contracts.supervisor import SupervisorPhase, SupervisorTick, TickOutcome

        t = SupervisorTick(
            tick_id="t1",
            tick_number=1,
            phase_sequence=(SupervisorPhase.POLLING,),
            events_polled=0,
            obligations_evaluated=0,
            deadlines_checked=0,
            reactions_fired=0,
            decisions=(),
            outcome=TickOutcome.IDLE_TICK,
            started_at=NOW,
            completed_at=NOW,
        )
        parsed = json.loads(t.to_json())
        assert parsed["tick_id"] == "t1"

    def test_decision_nested_in_tick_serializes(self) -> None:
        import json

        from mcoi_runtime.contracts.supervisor import (
            SupervisorDecision,
            SupervisorPhase,
            SupervisorTick,
            TickOutcome,
        )

        dec = SupervisorDecision(
            decision_id="d1",
            action_type="fire_reaction",
            target_id="rxn-1",
            reason="matched",
            governance_approved=True,
            decided_at=NOW,
        )
        t = SupervisorTick(
            tick_id="t1",
            tick_number=1,
            phase_sequence=(SupervisorPhase.ACTING,),
            events_polled=1,
            obligations_evaluated=0,
            deadlines_checked=0,
            reactions_fired=1,
            decisions=(dec,),
            outcome=TickOutcome.WORK_DONE,
            started_at=NOW,
            completed_at=NOW,
        )
        parsed = json.loads(t.to_json())
        assert parsed["decisions"][0]["decision_id"] == "d1"


# =====================================================================
# Package exports
# =====================================================================


class TestSupervisorExports:
    def test_all_supervisor_types_exported(self) -> None:
        from mcoi_runtime.contracts import (
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

        # Smoke: all imports succeed
        assert SupervisorPhase.IDLE == "idle"
        assert TickOutcome.HALTED == "halted"
