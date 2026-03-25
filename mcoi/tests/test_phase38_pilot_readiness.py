"""Phase 38 — Live Pilot Readiness Package tests.

Covers:
  38.3 — Sealed Launch Package (SealedLaunchPackage creation, contents, pre-start
         configuration, config-locked rejection, is_valid)
  38.4 — Operator Runbook (runbook_halt, runbook_canary_promote,
         runbook_canary_rollback, runbook_checkpoint_restore_drill)
  38.5 — Live Observability (pilot_observability_snapshot keys, immutability, values)
  38.6 — Fault Injection / Canary Drills (provider storm, event flood,
         checkpoint mismatch, pause/resume/halt under load, full canary cycle,
         repeated restore under churn)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

import pytest

from mcoi_runtime.contracts.event import EventRecord, EventSource, EventType
from mcoi_runtime.contracts.pilot import (
    BuildFingerprint,
    CheckpointCompatibilityManifest,
    PolicyBundleManifest,
    ProviderCapabilityManifest,
    SealedLaunchPackage,
    StartupValidationReport,
)
from mcoi_runtime.contracts.state_machine import (
    CheckpointScope,
    CompositeCheckpoint,
    SubsystemSnapshot,
)
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
    minutes = _tick // 60
    seconds = _tick % 60
    return f"2026-03-20T00:{minutes:02d}:{seconds:02d}+00:00"


@pytest.fixture(autouse=True)
def _reset():
    global _tick
    _tick = 0
    yield
    _tick = 0


def _make_plane(
    *,
    backpressure_threshold: int = 50,
    max_events_per_tick: int = 10,
    max_consecutive_errors: int = 10,
) -> PilotControlPlane:
    spine = EventSpineEngine(clock=_clock)
    obl = ObligationRuntimeEngine(clock=_clock)
    policy = SupervisorPolicy(
        policy_id="test-policy",
        tick_interval_ms=100,
        max_events_per_tick=max_events_per_tick,
        max_actions_per_tick=10,
        backpressure_threshold=backpressure_threshold,
        livelock_repeat_threshold=3,
        livelock_strategy=LivelockStrategy.ESCALATE,
        heartbeat_every_n_ticks=100,
        checkpoint_every_n_ticks=100,
        max_consecutive_errors=max_consecutive_errors,
        created_at=_TS,
    )
    sup = SupervisorEngine(
        policy=policy, spine=spine, obligation_engine=obl, clock=_clock,
    )
    return PilotControlPlane(
        supervisor=sup, spine=spine, obligation_engine=obl, clock=_clock,
    )


def _make_fingerprint() -> BuildFingerprint:
    return BuildFingerprint(
        fingerprint_id="fp-1",
        version="1.2.3",
        commit_hash="abc123",
        build_timestamp=_TS,
        python_version="3.12.0",
        rust_version="1.75.0",
        platform="linux-x86_64",
    )


def _make_policy_bundle_manifest() -> PolicyBundleManifest:
    return PolicyBundleManifest(
        manifest_id="pbm-1",
        bundle_id="bundle-1",
        bundle_name="default-governance",
        bundle_version="2.0.0",
        rule_count=42,
        bundle_hash="sha256:deadbeef",
        loaded_at=_TS,
    )


def _make_provider_manifest() -> ProviderCapabilityManifest:
    return ProviderCapabilityManifest(
        manifest_id="prov-1",
        provider_ids=("openai", "anthropic"),
        connector_ids=("http", "ws"),
        provider_count=2,
        connector_count=2,
        captured_at=_TS,
    )


def _emit_event(spine: EventSpineEngine, event_id: str) -> EventRecord:
    evt = EventRecord(
        event_id=event_id,
        event_type=EventType.CUSTOM,
        source=EventSource.SUPERVISOR,
        correlation_id="cor-1",
        payload={},
        emitted_at=_clock(),
    )
    return spine.emit(evt)


# ===========================================================================
# 38.3 — Sealed Launch Package
# ===========================================================================


class TestSealedLaunchPackage:
    """Test that starting the pilot creates a SealedLaunchPackage with all
    required components and that pre-start configuration flows through."""

    def test_start_creates_sealed_package(self):
        plane = _make_plane()
        plane.start("op-1")
        assert plane.sealed_package is not None
        assert isinstance(plane.sealed_package, SealedLaunchPackage)

    def test_sealed_package_contains_launch_manifest(self):
        plane = _make_plane()
        plane.start("op-1")
        pkg = plane.sealed_package
        assert pkg.launch_manifest is not None
        assert pkg.launch_manifest.policy_id == "test-policy"
        assert pkg.launch_manifest.epoch_id == "epoch-1"

    def test_sealed_package_contains_build_fingerprint(self):
        plane = _make_plane()
        plane.start("op-1")
        pkg = plane.sealed_package
        assert pkg.build_fingerprint is not None
        # Default fingerprint if none set
        assert pkg.build_fingerprint.version != ""

    def test_sealed_package_contains_checkpoint_compatibility(self):
        plane = _make_plane()
        plane.start("op-1")
        pkg = plane.sealed_package
        assert pkg.checkpoint_compatibility is not None
        assert isinstance(pkg.checkpoint_compatibility, CheckpointCompatibilityManifest)
        assert pkg.checkpoint_compatibility.epoch_id == "epoch-1"

    def test_sealed_package_contains_startup_report(self):
        plane = _make_plane()
        plane.start("op-1")
        pkg = plane.sealed_package
        assert pkg.startup_report is not None
        assert isinstance(pkg.startup_report, StartupValidationReport)
        assert pkg.startup_report.all_passed is True

    def test_set_build_fingerprint_before_start(self):
        plane = _make_plane()
        fp = _make_fingerprint()
        plane.set_build_fingerprint(fp)
        plane.start("op-1")
        pkg = plane.sealed_package
        assert pkg.build_fingerprint is fp
        assert pkg.build_fingerprint.version == "1.2.3"
        assert pkg.build_fingerprint.commit_hash == "abc123"

    def test_set_policy_bundle_manifest_before_start(self):
        plane = _make_plane()
        pbm = _make_policy_bundle_manifest()
        plane.set_policy_bundle_manifest(pbm)
        plane.start("op-1")
        pkg = plane.sealed_package
        assert pkg.policy_bundle_manifest is pbm
        assert pkg.policy_bundle_manifest.bundle_name == "default-governance"

    def test_set_provider_manifest_before_start(self):
        plane = _make_plane()
        pm = _make_provider_manifest()
        plane.set_provider_manifest(pm)
        plane.start("op-1")
        pkg = plane.sealed_package
        assert pkg.provider_manifest is pm
        assert pkg.provider_manifest.provider_count == 2

    def test_set_build_fingerprint_after_start_raises(self):
        plane = _make_plane()
        plane.start("op-1")
        with pytest.raises(RuntimeCoreInvariantError, match="config is locked"):
            plane.set_build_fingerprint(_make_fingerprint())

    def test_set_policy_bundle_manifest_after_start_raises(self):
        plane = _make_plane()
        plane.start("op-1")
        with pytest.raises(RuntimeCoreInvariantError, match="config is locked"):
            plane.set_policy_bundle_manifest(_make_policy_bundle_manifest())

    def test_set_provider_manifest_after_start_raises(self):
        plane = _make_plane()
        plane.start("op-1")
        with pytest.raises(RuntimeCoreInvariantError, match="config is locked"):
            plane.set_provider_manifest(_make_provider_manifest())

    def test_sealed_package_is_valid_when_startup_passes(self):
        plane = _make_plane()
        plane.start("op-1")
        assert plane.sealed_package.is_valid is True

    def test_sealed_package_none_before_start(self):
        plane = _make_plane()
        assert plane.sealed_package is None


# ===========================================================================
# 38.4 — Operator Runbook
# ===========================================================================


class TestRunbookHalt:
    """runbook_halt stops supervisor and sets ERROR state."""

    def test_halt_from_running(self):
        plane = _make_plane()
        plane.start("op-1")
        action = plane.runbook_halt("op-1", "emergency shutdown")
        assert plane.status == RuntimeStatus.ERROR
        assert action.action == "halt"
        assert plane.last_error == "emergency shutdown"

    def test_halt_from_paused(self):
        plane = _make_plane()
        plane.start("op-1")
        plane.pause("op-1")
        action = plane.runbook_halt("op-1", "emergency from paused")
        assert plane.status == RuntimeStatus.ERROR

    def test_halt_from_stopped_raises(self):
        plane = _make_plane()
        with pytest.raises(RuntimeCoreInvariantError, match="cannot halt a stopped"):
            plane.runbook_halt("op-1", "bad halt")


class TestRunbookCanaryPromote:
    """runbook_canary_promote goes OFF->OBSERVATION->SHADOW->ACTIVE."""

    def test_promote_off_to_observation(self):
        plane = _make_plane()
        plane.start("op-1")
        actions = plane.runbook_canary_promote("op-1", "canary start")
        assert plane.canary_mode == CanaryMode.OBSERVATION
        assert len(actions) == 1

    def test_promote_observation_to_shadow(self):
        plane = _make_plane()
        plane.start("op-1")
        plane.runbook_canary_promote("op-1", "step 1")
        plane.runbook_canary_promote("op-1", "step 2")
        assert plane.canary_mode == CanaryMode.SHADOW

    def test_promote_shadow_to_active(self):
        plane = _make_plane()
        plane.start("op-1")
        plane.runbook_canary_promote("op-1", "step 1")
        plane.runbook_canary_promote("op-1", "step 2")
        plane.runbook_canary_promote("op-1", "step 3")
        assert plane.canary_mode == CanaryMode.ACTIVE

    def test_promote_full_sequence(self):
        plane = _make_plane()
        plane.start("op-1")
        assert plane.canary_mode == CanaryMode.OFF

        plane.runbook_canary_promote("op-1", "promote")
        assert plane.canary_mode == CanaryMode.OBSERVATION

        plane.runbook_canary_promote("op-1", "promote")
        assert plane.canary_mode == CanaryMode.SHADOW

        plane.runbook_canary_promote("op-1", "promote")
        assert plane.canary_mode == CanaryMode.ACTIVE

    def test_promote_from_active_raises(self):
        plane = _make_plane()
        plane.start("op-1")
        plane.runbook_canary_promote("op-1", "1")
        plane.runbook_canary_promote("op-1", "2")
        plane.runbook_canary_promote("op-1", "3")
        assert plane.canary_mode == CanaryMode.ACTIVE
        with pytest.raises(RuntimeCoreInvariantError, match="terminal"):
            plane.runbook_canary_promote("op-1", "impossible")


class TestRunbookCanaryRollback:
    """runbook_canary_rollback returns to OBSERVATION."""

    def test_rollback_from_shadow(self):
        plane = _make_plane()
        plane.start("op-1")
        plane.runbook_canary_promote("op-1", "1")
        plane.runbook_canary_promote("op-1", "2")
        assert plane.canary_mode == CanaryMode.SHADOW
        plane.runbook_canary_rollback("op-1", "rollback")
        assert plane.canary_mode == CanaryMode.OBSERVATION

    def test_rollback_from_active(self):
        plane = _make_plane()
        plane.start("op-1")
        plane.runbook_canary_promote("op-1", "1")
        plane.runbook_canary_promote("op-1", "2")
        plane.runbook_canary_promote("op-1", "3")
        assert plane.canary_mode == CanaryMode.ACTIVE
        plane.runbook_canary_rollback("op-1", "rollback")
        assert plane.canary_mode == CanaryMode.OBSERVATION

    def test_rollback_from_off_raises(self):
        plane = _make_plane()
        plane.start("op-1")
        assert plane.canary_mode == CanaryMode.OFF
        with pytest.raises(RuntimeCoreInvariantError, match="OFF"):
            plane.runbook_canary_rollback("op-1", "impossible")


class TestRunbookCheckpointRestoreDrill:
    """runbook_checkpoint_restore_drill creates and restores a checkpoint."""

    def test_drill_creates_and_restores(self):
        plane = _make_plane()
        plane.start("op-1")
        # Tick a few times so there is state to checkpoint
        plane.tick()
        plane.tick()
        actions = plane.runbook_checkpoint_restore_drill("op-1")
        assert len(actions) == 2
        assert actions[0].action == "checkpoint"
        assert actions[1].action == "restore"

    def test_drill_is_idempotent(self):
        """Running the drill twice should succeed both times."""
        plane = _make_plane()
        plane.start("op-1")
        plane.tick()
        actions1 = plane.runbook_checkpoint_restore_drill("op-1")
        actions2 = plane.runbook_checkpoint_restore_drill("op-1")
        assert len(actions1) == 2
        assert len(actions2) == 2


# ===========================================================================
# 38.5 — Live Observability
# ===========================================================================


class TestPilotObservabilitySnapshot:
    """pilot_observability_snapshot returns an immutable Mapping with all
    required keys and correct values."""

    _REQUIRED_KEYS = frozenset({
        "supervisor_state",
        "canary_state",
        "checkpoint_freshness",
        "replay_readiness",
        "backlog_pressure",
        "event_rate",
        "degraded_reasons",
        "overall_confidence",
        "is_degraded",
        "policy_in_force",
        "manifest_id",
        "build_fingerprint",
        "status",
    })

    def test_snapshot_returns_mapping(self):
        plane = _make_plane()
        plane.start("op-1")
        snap = plane.pilot_observability_snapshot()
        assert isinstance(snap, Mapping)

    def test_snapshot_is_immutable(self):
        plane = _make_plane()
        plane.start("op-1")
        snap = plane.pilot_observability_snapshot()
        with pytest.raises(TypeError):
            snap["status"] = "hacked"  # type: ignore[index]

    def test_snapshot_contains_all_required_keys(self):
        plane = _make_plane()
        plane.start("op-1")
        snap = plane.pilot_observability_snapshot()
        missing = self._REQUIRED_KEYS - set(snap.keys())
        assert not missing, f"Missing keys: {missing}"

    def test_snapshot_values_after_ticking(self):
        plane = _make_plane()
        plane.start("op-1")
        plane.tick()
        plane.tick()
        snap = plane.pilot_observability_snapshot()

        # supervisor_state reflects ticks
        assert snap["supervisor_state"]["tick_number"] >= 2
        assert snap["supervisor_state"]["halted"] is False

        # status is running
        assert snap["status"] == "running"

        # canary defaults to OFF
        assert snap["canary_state"]["mode"] == "off"

        # manifest_id is populated
        assert snap["manifest_id"] != ""

        # policy_in_force populated
        assert snap["policy_in_force"] == "test-policy"

        # confidence is a float between 0 and 1
        assert 0.0 <= snap["overall_confidence"] <= 1.0

    def test_snapshot_reflects_canary_change(self):
        plane = _make_plane()
        plane.start("op-1")
        plane.runbook_canary_promote("op-1", "go observe")
        snap = plane.pilot_observability_snapshot()
        assert snap["canary_state"]["mode"] == "observation"

    def test_snapshot_checkpoint_freshness_after_checkpoint(self):
        plane = _make_plane()
        plane.start("op-1")
        plane.tick()
        plane.create_checkpoint()
        snap = plane.pilot_observability_snapshot()
        assert snap["checkpoint_freshness"]["checkpoint_count"] >= 1

    def test_snapshot_build_fingerprint_from_sealed_package(self):
        plane = _make_plane()
        fp = _make_fingerprint()
        plane.set_build_fingerprint(fp)
        plane.start("op-1")
        snap = plane.pilot_observability_snapshot()
        assert snap["build_fingerprint"]["version"] == "1.2.3"
        assert snap["build_fingerprint"]["commit"] == "abc123"


# ===========================================================================
# 38.6 — Fault Injection / Canary Drills
# ===========================================================================


class TestProviderStorm:
    """Emit many events and verify supervisor handles backpressure."""

    def test_many_events_tick_does_not_crash(self):
        plane = _make_plane(backpressure_threshold=5, max_events_per_tick=3)
        plane.start("op-1")

        # Emit events directly into the spine via the supervisor's spine ref
        spine = plane._spine
        for i in range(20):
            _emit_event(spine, f"storm-{i}")

        # Tick several times — should not raise
        for _ in range(10):
            plane.tick()

    def test_storm_supervisor_remains_healthy(self):
        plane = _make_plane(backpressure_threshold=5, max_events_per_tick=3)
        plane.start("op-1")
        spine = plane._spine
        for i in range(15):
            _emit_event(spine, f"storm-{i}")
        # Tick through all events
        for _ in range(10):
            plane.tick()
        # Supervisor should still be ticking (not halted)
        assert plane.status == RuntimeStatus.RUNNING


class TestEventFlood:
    """Emit events above backpressure threshold; verify observability shows it."""

    def test_flood_triggers_backpressure_in_observability(self):
        plane = _make_plane(backpressure_threshold=5, max_events_per_tick=2)
        plane.start("op-1")
        spine = plane._spine

        # Tick once so supervisor is in a normal state
        plane.tick()

        # Now flood: emit more than backpressure_threshold AFTER tick
        # so they appear as pending in the next health assessment
        for i in range(10):
            _emit_event(spine, f"flood-{i}")

        # The health assessment checks pending = total_events - processed_events
        # After the tick, all prior events are processed, but these 10 new ones
        # are not yet processed, so pending = 10 > threshold = 5
        snap = plane.pilot_observability_snapshot()
        assert snap["event_rate"]["backpressure_active"] is True


class TestCheckpointMismatch:
    """Corrupt a checkpoint hash and verify restore fails."""

    def test_corrupted_hash_restore_fails(self):
        plane = _make_plane()
        plane.start("op-1")
        plane.tick()

        cp = plane.create_checkpoint()

        # Corrupt the composite hash by creating a new checkpoint with bad hash
        corrupted = CompositeCheckpoint(
            checkpoint_id=cp.checkpoint_id,
            epoch_id=cp.epoch_id,
            tick_number=cp.tick_number,
            snapshots=cp.snapshots,
            journal_sequence=cp.journal_sequence,
            composite_hash="CORRUPTED-HASH",
            created_at=cp.created_at,
        )

        # Restoring with verification should fail because post-restore
        # hash will not match the corrupted composite_hash
        with pytest.raises(RuntimeCoreInvariantError):
            plane.restore_checkpoint(corrupted, "op-1", verify=True)


class TestPauseResumeHaltUnderLoad:
    """Tick, pause, resume, halt while events are queued."""

    def test_pause_resume_halt_under_load(self):
        plane = _make_plane(backpressure_threshold=50)
        plane.start("op-1")
        spine = plane._spine

        # Queue some events
        for i in range(5):
            _emit_event(spine, f"load-{i}")

        # Tick to process some
        plane.tick()

        # Pause
        plane.pause("op-1", "maintenance")
        assert plane.status == RuntimeStatus.PAUSED

        # Cannot tick while paused
        with pytest.raises(RuntimeCoreInvariantError):
            plane.tick()

        # Resume
        plane.resume("op-1", "maintenance done")
        assert plane.status == RuntimeStatus.RUNNING

        # Tick some more
        plane.tick()

        # Halt
        plane.runbook_halt("op-1", "emergency")
        assert plane.status == RuntimeStatus.ERROR

    def test_events_survive_pause_resume(self):
        plane = _make_plane()
        plane.start("op-1")
        spine = plane._spine

        for i in range(3):
            _emit_event(spine, f"survive-{i}")

        initial_count = spine.event_count
        plane.pause("op-1")
        plane.resume("op-1")

        # Events should still be in spine
        assert spine.event_count == initial_count


class TestCanaryFullCycle:
    """Full canary cycle: observation -> shadow -> active -> rollback."""

    def test_full_canary_cycle(self):
        plane = _make_plane()
        plane.start("op-1")

        assert plane.canary_mode == CanaryMode.OFF

        # Promote OFF -> OBSERVATION
        plane.runbook_canary_promote("op-1", "start canary")
        assert plane.canary_mode == CanaryMode.OBSERVATION

        # In observation, mutations should be gated
        assert plane.canary_allows_action("health") is True
        assert plane.canary_allows_action("emit_event") is False

        # Promote OBSERVATION -> SHADOW
        plane.runbook_canary_promote("op-1", "shadow phase")
        assert plane.canary_mode == CanaryMode.SHADOW

        # In shadow, actions are allowed (caller discards results)
        assert plane.canary_allows_action("emit_event") is True

        # Promote SHADOW -> ACTIVE
        plane.runbook_canary_promote("op-1", "go active")
        assert plane.canary_mode == CanaryMode.ACTIVE
        assert plane.canary_allows_action("emit_event") is True

        # Rollback to OBSERVATION
        plane.runbook_canary_rollback("op-1", "issue detected")
        assert plane.canary_mode == CanaryMode.OBSERVATION


class TestRepeatedRestoreUnderChurn:
    """Checkpoint, add events, restore, verify state — repeated."""

    def test_repeated_checkpoint_restore(self):
        plane = _make_plane()
        plane.start("op-1")

        for cycle in range(3):
            # Tick to advance state
            plane.tick()

            # Checkpoint
            cp = plane.create_checkpoint()

            # Add more events (churn)
            spine = plane._spine
            for i in range(3):
                _emit_event(spine, f"churn-{cycle}-{i}")
            plane.tick()

            # Restore back to checkpoint
            plane.restore_checkpoint(cp, "op-1", verify=True)

            # After restore, state should match checkpoint moment
            # Tick number should be back to checkpoint's tick
            assert plane._supervisor.tick_number == cp.tick_number

    def test_restore_then_tick_continues_normally(self):
        plane = _make_plane()
        plane.start("op-1")
        plane.tick()
        plane.tick()

        cp = plane.create_checkpoint()
        tick_at_cp = plane._supervisor.tick_number

        # More ticks
        plane.tick()
        plane.tick()

        # Restore
        plane.restore_checkpoint(cp, "op-1", verify=True)
        assert plane._supervisor.tick_number == tick_at_cp

        # Continue ticking after restore — should work
        plane.tick()
        assert plane._supervisor.tick_number == tick_at_cp + 1
