"""Comprehensive tests for PilotControlPlane lifecycle, canary mode,
health/readiness, tick enforcement, checkpoint, and operator audit trail.

Covers Audit #9 findings:
  - Lifecycle state machine completeness (start/stop/pause/resume/error)
  - Canary mode wired into health/readiness
  - Tick rejection when not RUNNING
  - mark_error / last_error visibility
  - Operator action audit trail ordering
  - Checkpoint create/restore through control plane
"""

from __future__ import annotations

import pytest

from mcoi_runtime.contracts.event import EventRecord, EventSource, EventType
from mcoi_runtime.contracts.obligation import ObligationDeadline, ObligationOwner, ObligationTrigger
from mcoi_runtime.contracts.supervisor import LivelockStrategy, SupervisorPolicy
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
    return f"2026-03-20T00:00:{_tick:02d}+00:00"


@pytest.fixture(autouse=True)
def _reset():
    global _tick
    _tick = 0
    yield
    _tick = 0


def _make_plane() -> PilotControlPlane:
    spine = EventSpineEngine(clock=_clock)
    obl = ObligationRuntimeEngine(clock=_clock)
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
        policy=policy, spine=spine, obligation_engine=obl, clock=_clock,
    )
    return PilotControlPlane(
        supervisor=sup, spine=spine, obligation_engine=obl, clock=_clock,
    )


# ---------------------------------------------------------------------------
# Lifecycle state transitions
# ---------------------------------------------------------------------------


class TestLifecycleStart:
    def test_start_from_stopped(self):
        plane = _make_plane()
        assert plane.status == RuntimeStatus.STOPPED
        action = plane.start("op-1")
        assert plane.status == RuntimeStatus.RUNNING
        assert action.action == "start"
        assert action.operator_id == "op-1"

    def test_start_from_error(self):
        plane = _make_plane()
        plane.start("op-1")
        plane.mark_error("op-1", "something broke")
        assert plane.status == RuntimeStatus.ERROR
        action = plane.start("op-1", reason="error recovery")
        assert plane.status == RuntimeStatus.RUNNING
        assert plane.last_error == ""  # cleared on start

    def test_start_rejects_from_running(self):
        plane = _make_plane()
        plane.start("op-1")
        with pytest.raises(RuntimeCoreInvariantError, match="cannot start"):
            plane.start("op-1")

    def test_start_rejects_from_paused(self):
        plane = _make_plane()
        plane.start("op-1")
        plane.pause("op-1")
        with pytest.raises(RuntimeCoreInvariantError, match="cannot start"):
            plane.start("op-1")


class TestLifecycleStop:
    def test_stop_from_running(self):
        plane = _make_plane()
        plane.start("op-1")
        action = plane.stop("op-1")
        assert plane.status == RuntimeStatus.STOPPED
        assert action.action == "stop"

    def test_stop_from_paused(self):
        plane = _make_plane()
        plane.start("op-1")
        plane.pause("op-1")
        action = plane.stop("op-1")
        assert plane.status == RuntimeStatus.STOPPED

    def test_stop_rejects_already_stopped(self):
        plane = _make_plane()
        with pytest.raises(RuntimeCoreInvariantError, match="already stopped"):
            plane.stop("op-1")


class TestLifecyclePauseResume:
    def test_pause_from_running(self):
        plane = _make_plane()
        plane.start("op-1")
        action = plane.pause("op-1")
        assert plane.status == RuntimeStatus.PAUSED
        assert action.action == "pause"

    def test_pause_rejects_from_stopped(self):
        plane = _make_plane()
        with pytest.raises(RuntimeCoreInvariantError, match="cannot pause"):
            plane.pause("op-1")

    def test_pause_rejects_from_paused(self):
        plane = _make_plane()
        plane.start("op-1")
        plane.pause("op-1")
        with pytest.raises(RuntimeCoreInvariantError, match="cannot pause"):
            plane.pause("op-1")

    def test_resume_from_paused(self):
        plane = _make_plane()
        plane.start("op-1")
        plane.pause("op-1")
        action = plane.resume("op-1")
        assert plane.status == RuntimeStatus.RUNNING
        assert action.action == "resume"

    def test_resume_rejects_from_running(self):
        plane = _make_plane()
        plane.start("op-1")
        with pytest.raises(RuntimeCoreInvariantError, match="cannot resume"):
            plane.resume("op-1")

    def test_resume_rejects_from_stopped(self):
        plane = _make_plane()
        with pytest.raises(RuntimeCoreInvariantError, match="cannot resume"):
            plane.resume("op-1")


class TestLifecycleError:
    def test_mark_error_from_running(self):
        plane = _make_plane()
        plane.start("op-1")
        action = plane.mark_error("op-1", "disk full")
        assert plane.status == RuntimeStatus.ERROR
        assert plane.last_error == "disk full"
        assert action.action == "mark_error"

    def test_mark_error_from_paused(self):
        plane = _make_plane()
        plane.start("op-1")
        plane.pause("op-1")
        plane.mark_error("op-1", "hardware fault")
        assert plane.status == RuntimeStatus.ERROR
        assert plane.last_error == "hardware fault"

    def test_mark_error_rejects_from_stopped(self):
        plane = _make_plane()
        with pytest.raises(RuntimeCoreInvariantError, match="cannot mark error"):
            plane.mark_error("op-1", "nope")

    def test_mark_error_rejects_from_error(self):
        plane = _make_plane()
        plane.start("op-1")
        plane.mark_error("op-1", "first error")
        with pytest.raises(RuntimeCoreInvariantError, match="cannot mark error"):
            plane.mark_error("op-1", "second error")


# ---------------------------------------------------------------------------
# Tick enforcement
# ---------------------------------------------------------------------------


class TestTickEnforcement:
    def test_tick_succeeds_when_running(self):
        plane = _make_plane()
        plane.start("op-1")
        result = plane.tick()
        assert result is not None

    def test_tick_rejects_when_stopped(self):
        plane = _make_plane()
        with pytest.raises(RuntimeCoreInvariantError, match="cannot tick"):
            plane.tick()

    def test_tick_rejects_when_paused(self):
        plane = _make_plane()
        plane.start("op-1")
        plane.pause("op-1")
        with pytest.raises(RuntimeCoreInvariantError, match="cannot tick"):
            plane.tick()

    def test_tick_rejects_when_error(self):
        plane = _make_plane()
        plane.start("op-1")
        plane.mark_error("op-1", "bad state")
        with pytest.raises(RuntimeCoreInvariantError, match="cannot tick"):
            plane.tick()

    def test_run_ticks_returns_list(self):
        plane = _make_plane()
        plane.start("op-1")
        results = plane.run_ticks(3)
        assert len(results) == 3


# ---------------------------------------------------------------------------
# Canary mode
# ---------------------------------------------------------------------------


class TestCanaryMode:
    def test_default_canary_off(self):
        plane = _make_plane()
        assert plane.canary_mode == CanaryMode.OFF

    def test_set_canary_mode(self):
        plane = _make_plane()
        action = plane.set_canary_mode(
            CanaryMode.OBSERVATION, "op-1", "testing new policy",
        )
        assert plane.canary_mode == CanaryMode.OBSERVATION
        assert action.action == "set_canary_mode"
        assert "was: off" in action.reason

    def test_canary_observation_not_ready(self):
        plane = _make_plane()
        plane.start("op-1")
        plane.set_canary_mode(CanaryMode.OBSERVATION, "op-1", "canary test")
        h = plane.health()
        assert h.is_healthy is True
        assert h.is_ready is False
        assert h.canary_mode == CanaryMode.OBSERVATION

    def test_canary_shadow_not_ready(self):
        plane = _make_plane()
        plane.start("op-1")
        plane.set_canary_mode(CanaryMode.SHADOW, "op-1", "shadow test")
        h = plane.health()
        assert h.is_healthy is True
        assert h.is_ready is False

    def test_canary_active_is_ready(self):
        plane = _make_plane()
        plane.start("op-1")
        plane.set_canary_mode(CanaryMode.ACTIVE, "op-1", "promote")
        h = plane.health()
        assert h.is_healthy is True
        assert h.is_ready is True

    def test_canary_off_is_ready(self):
        plane = _make_plane()
        plane.start("op-1")
        h = plane.health()
        assert h.is_ready is True


# ---------------------------------------------------------------------------
# Health / readiness
# ---------------------------------------------------------------------------


class TestHealthReport:
    def test_health_when_stopped(self):
        plane = _make_plane()
        h = plane.health()
        assert h.status == RuntimeStatus.STOPPED
        assert h.is_healthy is False
        assert h.is_ready is False

    def test_health_when_running(self):
        plane = _make_plane()
        plane.start("op-1")
        h = plane.health()
        assert h.status == RuntimeStatus.RUNNING
        assert h.is_healthy is True
        assert h.is_ready is True

    def test_health_when_paused(self):
        plane = _make_plane()
        plane.start("op-1")
        plane.pause("op-1")
        h = plane.health()
        assert h.status == RuntimeStatus.PAUSED
        assert h.is_healthy is True
        assert h.is_ready is False

    def test_health_when_error(self):
        plane = _make_plane()
        plane.start("op-1")
        plane.mark_error("op-1", "bad")
        h = plane.health()
        assert h.status == RuntimeStatus.ERROR
        assert h.is_healthy is False
        assert h.is_ready is False

    def test_health_reports_tick_number(self):
        plane = _make_plane()
        plane.start("op-1")
        plane.tick()
        plane.tick()
        h = plane.health()
        assert h.tick_number == 2


# ---------------------------------------------------------------------------
# Checkpoint through control plane
# ---------------------------------------------------------------------------


class TestCheckpoint:
    def test_create_checkpoint(self):
        plane = _make_plane()
        plane.start("op-1")
        plane.tick()
        cp = plane.create_checkpoint("op-1")
        assert cp.tick_number >= 1

    def test_restore_checkpoint(self):
        plane = _make_plane()
        plane.start("op-1")
        plane.tick()
        cp = plane.create_checkpoint("op-1")
        plane.tick()
        plane.tick()
        action = plane.restore_checkpoint(cp, "op-1", verify=False)
        assert action.action == "restore"

    def test_export_checkpoint_none_when_empty(self):
        plane = _make_plane()
        assert plane.export_checkpoint() is None

    def test_export_checkpoint_returns_dict(self):
        plane = _make_plane()
        plane.start("op-1")
        plane.tick()
        plane.create_checkpoint("op-1")
        exported = plane.export_checkpoint()
        assert isinstance(exported, dict)
        assert "checkpoint_id" in exported


# ---------------------------------------------------------------------------
# Operator action audit trail
# ---------------------------------------------------------------------------


class TestOperatorAuditTrail:
    def test_actions_accumulate(self):
        plane = _make_plane()
        plane.start("op-1")
        plane.pause("op-1")
        plane.resume("op-1")
        plane.stop("op-1")
        assert plane.action_count == 4

    def test_action_ordering_preserved(self):
        plane = _make_plane()
        plane.start("op-1")
        plane.pause("op-2")
        plane.resume("op-3")
        actions = plane.list_actions()
        assert actions[0].action == "start"
        assert actions[0].operator_id == "op-1"
        assert actions[1].action == "pause"
        assert actions[1].operator_id == "op-2"
        assert actions[2].action == "resume"
        assert actions[2].operator_id == "op-3"

    def test_checkpoint_records_operator_action(self):
        plane = _make_plane()
        plane.start("op-1")
        plane.tick()
        plane.create_checkpoint("op-2")
        actions = plane.list_actions()
        checkpoint_actions = [a for a in actions if a.action == "checkpoint"]
        assert len(checkpoint_actions) == 1
        assert checkpoint_actions[0].operator_id == "op-2"

    def test_mark_error_records_action(self):
        plane = _make_plane()
        plane.start("op-1")
        plane.mark_error("op-1", "disk full")
        actions = plane.list_actions()
        error_actions = [a for a in actions if a.action == "mark_error"]
        assert len(error_actions) == 1
        assert error_actions[0].reason == "disk full"

    def test_canary_mode_records_action(self):
        plane = _make_plane()
        plane.set_canary_mode(CanaryMode.SHADOW, "op-1", "testing")
        actions = plane.list_actions()
        canary_actions = [a for a in actions if a.action == "set_canary_mode"]
        assert len(canary_actions) == 1
        assert canary_actions[0].target == "shadow"
