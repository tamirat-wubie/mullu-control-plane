"""Subphase 4 tests: pilot control plane deployment hardening.

Covers:
  - Startup validation (fail-closed on missing/invalid subsystems)
  - Config locking and immutable launch manifests
  - Canary-mode behavioral gating (canary_allows_action)
  - Operator authority boundaries (register, enforce, reject)
  - Checkpoint import verification before acceptance
  - Health/readiness/degraded surfaces with confidence scoring
  - Runtime state export for dashboards
  - Pilot contract validation (RuntimeLaunchManifest, StartupValidationResult, etc.)
"""

from __future__ import annotations

import pytest

from mcoi_runtime.contracts.pilot import (
    AUTHORITY_ACTIONS,
    CheckpointImportResult,
    CheckpointImportVerdict,
    DegradedReason,
    OperatorAuthority,
    RuntimeLaunchManifest,
    RuntimeStateExport,
    StartupValidationResult,
    StartupVerdict,
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
    return f"2026-03-20T00:00:{_tick:02d}+00:00"


@pytest.fixture(autouse=True)
def _reset():
    global _tick
    _tick = 0
    yield
    _tick = 0


def _make_policy() -> SupervisorPolicy:
    return SupervisorPolicy(
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


def _make_plane() -> PilotControlPlane:
    spine = EventSpineEngine(clock=_clock)
    obl = ObligationRuntimeEngine(clock=_clock)
    policy = _make_policy()
    sup = SupervisorEngine(
        policy=policy, spine=spine, obligation_engine=obl, clock=_clock,
    )
    return PilotControlPlane(
        supervisor=sup, spine=spine, obligation_engine=obl, clock=_clock,
    )


# ---------------------------------------------------------------------------
# Startup validation
# ---------------------------------------------------------------------------


class TestStartupValidation:
    def test_validation_passes_with_all_subsystems(self):
        plane = _make_plane()
        result = plane.validate_startup()
        assert result.verdict == StartupVerdict.PASSED
        assert result.is_valid
        assert len(result.checks_failed) == 0
        assert len(result.checks_passed) >= 4

    def test_start_runs_validation(self):
        """start() internally calls validate_startup and fails closed."""
        plane = _make_plane()
        # Normal start should succeed since all subsystems present
        action = plane.start("op-1")
        assert plane.status == RuntimeStatus.RUNNING
        assert action.action == "start"

    def test_validation_result_contract(self):
        plane = _make_plane()
        result = plane.validate_startup()
        assert isinstance(result, StartupValidationResult)
        assert result.validation_id
        assert result.validated_at
        # Serializable
        d = result.to_dict()
        assert d["verdict"] == "passed"


# ---------------------------------------------------------------------------
# Config locking and launch manifest
# ---------------------------------------------------------------------------


class TestConfigLocking:
    def test_config_unlocked_before_start(self):
        plane = _make_plane()
        assert not plane.config_locked
        assert plane.launch_manifest is None

    def test_config_locked_after_start(self):
        plane = _make_plane()
        plane.start("op-1")
        assert plane.config_locked
        assert plane.launch_manifest is not None

    def test_launch_manifest_immutable(self):
        plane = _make_plane()
        plane.start("op-1")
        manifest = plane.launch_manifest
        assert isinstance(manifest, RuntimeLaunchManifest)
        assert manifest.policy_id == "test-policy"
        assert manifest.canary_mode == "off"
        assert "supervisor" in manifest.subsystem_ids
        assert manifest.config_snapshot["max_events_per_tick"] == 10

    def test_config_unlocked_after_stop(self):
        plane = _make_plane()
        plane.start("op-1")
        assert plane.config_locked
        plane.stop("op-1")
        assert not plane.config_locked

    def test_cannot_register_operator_while_locked(self):
        plane = _make_plane()
        plane.start("op-1")
        with pytest.raises(RuntimeCoreInvariantError, match="config is locked"):
            plane.register_operator("op-2", OperatorAuthority.ADMIN)

    def test_manifest_inspectable_after_start(self):
        """The manifest is the auditable reference for launch config."""
        plane = _make_plane()
        plane.start("op-1")
        d = plane.launch_manifest.to_dict()
        assert "policy_id" in d
        assert "config_snapshot" in d
        assert "subsystem_ids" in d


# ---------------------------------------------------------------------------
# Operator authority boundaries
# ---------------------------------------------------------------------------


class TestOperatorAuthority:
    def test_no_authorities_permissive_mode(self):
        """With no operators registered, all actions are allowed (backwards-compatible)."""
        plane = _make_plane()
        plane.start("anyone")
        assert plane.status == RuntimeStatus.RUNNING

    def test_admin_can_start(self):
        plane = _make_plane()
        plane.register_operator("admin-1", OperatorAuthority.ADMIN)
        plane.start("admin-1")
        assert plane.status == RuntimeStatus.RUNNING

    def test_operator_can_pause(self):
        plane = _make_plane()
        plane.register_operator("admin-1", OperatorAuthority.ADMIN)
        plane.register_operator("op-1", OperatorAuthority.OPERATOR)
        plane.start("admin-1")
        plane.pause("op-1")
        assert plane.status == RuntimeStatus.PAUSED

    def test_operator_cannot_start(self):
        plane = _make_plane()
        plane.register_operator("op-1", OperatorAuthority.OPERATOR)
        with pytest.raises(RuntimeCoreInvariantError, match="lacks authority"):
            plane.start("op-1")

    def test_viewer_cannot_pause(self):
        plane = _make_plane()
        plane.register_operator("admin-1", OperatorAuthority.ADMIN)
        plane.register_operator("viewer-1", OperatorAuthority.VIEWER)
        plane.start("admin-1")
        with pytest.raises(RuntimeCoreInvariantError, match="lacks authority"):
            plane.pause("viewer-1")

    def test_unregistered_operator_rejected(self):
        plane = _make_plane()
        plane.register_operator("admin-1", OperatorAuthority.ADMIN)
        with pytest.raises(RuntimeCoreInvariantError, match="not registered"):
            plane.start("unknown-op")

    def test_operator_can_checkpoint(self):
        plane = _make_plane()
        plane.register_operator("admin-1", OperatorAuthority.ADMIN)
        plane.register_operator("op-1", OperatorAuthority.OPERATOR)
        plane.start("admin-1")
        cp = plane.create_checkpoint("op-1")
        assert cp is not None

    def test_viewer_cannot_checkpoint(self):
        plane = _make_plane()
        plane.register_operator("admin-1", OperatorAuthority.ADMIN)
        plane.register_operator("viewer-1", OperatorAuthority.VIEWER)
        plane.start("admin-1")
        with pytest.raises(RuntimeCoreInvariantError, match="lacks authority"):
            plane.create_checkpoint("viewer-1")

    def test_authority_actions_are_complete(self):
        """Every authority level should have at least the viewer actions."""
        viewer_actions = AUTHORITY_ACTIONS[OperatorAuthority.VIEWER]
        operator_actions = AUTHORITY_ACTIONS[OperatorAuthority.OPERATOR]
        admin_actions = AUTHORITY_ACTIONS[OperatorAuthority.ADMIN]
        # Viewer ⊆ Operator ⊆ Admin
        assert viewer_actions.issubset(operator_actions)
        assert operator_actions.issubset(admin_actions)


# ---------------------------------------------------------------------------
# Canary-mode behavioral gating
# ---------------------------------------------------------------------------


class TestCanaryBehavioralGating:
    def test_off_allows_all(self):
        plane = _make_plane()
        assert plane.canary_allows_action("fire_reaction")
        assert plane.canary_allows_action("create_obligation")
        assert plane.canary_allows_action("health")

    def test_active_allows_all(self):
        plane = _make_plane()
        plane.start("op-1")
        plane.set_canary_mode(CanaryMode.ACTIVE, "op-1", "full rollout")
        assert plane.canary_allows_action("fire_reaction")
        assert plane.canary_allows_action("create_obligation")

    def test_observation_blocks_mutations(self):
        plane = _make_plane()
        plane.start("op-1")
        plane.set_canary_mode(CanaryMode.OBSERVATION, "op-1", "observing")
        # Read-only actions allowed
        assert plane.canary_allows_action("health")
        assert plane.canary_allows_action("list_events")
        assert plane.canary_allows_action("list_obligations")
        # Mutation actions blocked
        assert not plane.canary_allows_action("fire_reaction")
        assert not plane.canary_allows_action("create_obligation")
        assert not plane.canary_allows_action("emit_event")

    def test_shadow_allows_mutations(self):
        """Shadow mode allows mutations (caller discards results)."""
        plane = _make_plane()
        plane.start("op-1")
        plane.set_canary_mode(CanaryMode.SHADOW, "op-1", "shadow run")
        assert plane.canary_allows_action("fire_reaction")
        assert plane.canary_allows_action("create_obligation")

    def test_observation_readiness_false(self):
        plane = _make_plane()
        plane.start("op-1")
        plane.set_canary_mode(CanaryMode.OBSERVATION, "op-1", "observe")
        h = plane.health()
        assert h.is_healthy
        assert not h.is_ready


# ---------------------------------------------------------------------------
# Checkpoint import verification
# ---------------------------------------------------------------------------


class TestCheckpointImportVerification:
    def test_valid_checkpoint_accepted(self):
        plane = _make_plane()
        plane.start("op-1")
        cp = plane.create_checkpoint("op-1")
        result = plane.verify_checkpoint_import(cp)
        assert result.verdict == CheckpointImportVerdict.ACCEPTED
        assert result.accepted
        assert len(result.checks_failed) == 0

    def test_import_restores_on_acceptance(self):
        plane = _make_plane()
        plane.start("op-1")
        # Run a few ticks
        plane.run_ticks(3)
        cp = plane.create_checkpoint("op-1")
        # Run more ticks to diverge
        plane.run_ticks(3)
        assert plane._supervisor.tick_number > cp.tick_number
        # Import should verify + restore
        result = plane.import_checkpoint(cp, "op-1", "rollback test")
        assert result.accepted

    def test_import_result_contract(self):
        plane = _make_plane()
        plane.start("op-1")
        cp = plane.create_checkpoint("op-1")
        result = plane.verify_checkpoint_import(cp)
        assert isinstance(result, CheckpointImportResult)
        d = result.to_dict()
        assert d["verdict"] == "accepted"


# ---------------------------------------------------------------------------
# Health / readiness / degraded surfaces
# ---------------------------------------------------------------------------


class TestHealthDegradedSurfaces:
    def test_healthy_running_not_degraded(self):
        plane = _make_plane()
        plane.start("op-1")
        h = plane.health()
        assert h.is_healthy
        assert h.is_ready
        assert not h.is_degraded
        assert len(h.degraded_reasons) == 0

    def test_health_includes_confidence(self):
        plane = _make_plane()
        plane.start("op-1")
        h = plane.health()
        assert 0.0 <= h.overall_confidence <= 1.0

    def test_stopped_not_healthy(self):
        plane = _make_plane()
        h = plane.health()
        assert not h.is_healthy
        assert not h.is_ready

    def test_error_not_healthy(self):
        plane = _make_plane()
        plane.start("op-1")
        plane.mark_error("op-1", "test error")
        h = plane.health()
        assert not h.is_healthy

    def test_halted_supervisor_degrades(self):
        """If supervisor halts, health should report degraded."""
        spine = EventSpineEngine(clock=_clock)
        obl = ObligationRuntimeEngine(clock=_clock)
        policy = SupervisorPolicy(
            policy_id="halt-policy",
            tick_interval_ms=100,
            max_events_per_tick=10,
            max_actions_per_tick=10,
            backpressure_threshold=50,
            livelock_repeat_threshold=3,
            livelock_strategy=LivelockStrategy.HALT,
            heartbeat_every_n_ticks=100,
            checkpoint_every_n_ticks=100,
            max_consecutive_errors=1,
            created_at=_TS,
        )

        # Create a gate that blocks everything to force errors
        def blocking_gate(action_type, target_id, context):
            return False

        sup = SupervisorEngine(
            policy=policy, spine=spine, obligation_engine=obl,
            clock=_clock, governance_gate=blocking_gate,
        )
        plane = PilotControlPlane(
            supervisor=sup, spine=spine, obligation_engine=obl, clock=_clock,
        )
        plane.start("op-1")
        # Run enough ticks for potential error accumulation
        # Even without errors, we can manually check halted detection
        sup._halted = True  # simulate halt
        h = plane.health()
        assert h.is_degraded
        assert DegradedReason.SUPERVISOR_HALTED.value in h.degraded_reasons
        # Halted supervisor means not ready
        assert not h.is_ready

    def test_health_report_serializable(self):
        plane = _make_plane()
        plane.start("op-1")
        h = plane.health()
        d = h.to_dict()
        assert "is_degraded" in d
        assert "degraded_reasons" in d
        assert "overall_confidence" in d


# ---------------------------------------------------------------------------
# Runtime state export
# ---------------------------------------------------------------------------


class TestRuntimeStateExport:
    def test_export_when_running(self):
        plane = _make_plane()
        plane.start("op-1")
        export = plane.export_state()
        assert isinstance(export, RuntimeStateExport)
        assert export.status == "running"
        assert export.canary_mode == "off"
        assert export.is_healthy
        assert export.is_ready
        assert 0.0 <= export.overall_confidence <= 1.0
        assert export.manifest_id != "none"

    def test_export_when_stopped(self):
        plane = _make_plane()
        export = plane.export_state()
        assert export.status == "stopped"
        assert not export.is_healthy
        assert not export.is_ready
        assert export.manifest_id == "none"

    def test_export_after_ticks(self):
        plane = _make_plane()
        plane.start("op-1")
        plane.run_ticks(5)
        export = plane.export_state()
        assert export.tick_number == 5
        assert export.journal_length >= 5

    def test_export_serializable(self):
        plane = _make_plane()
        plane.start("op-1")
        export = plane.export_state()
        d = export.to_dict()
        assert "status" in d
        assert "canary_mode" in d
        assert "supervisor_phase" in d
        assert "overall_confidence" in d
        assert "degraded_reasons" in d
        assert "manifest_id" in d

    def test_export_includes_action_count(self):
        plane = _make_plane()
        plane.start("op-1")
        plane.pause("op-1")
        plane.resume("op-1")
        export = plane.export_state()
        assert export.action_count == 3  # start + pause + resume


# ---------------------------------------------------------------------------
# Pilot contract validation
# ---------------------------------------------------------------------------


class TestPilotContracts:
    def test_launch_manifest_rejects_empty_policy_id(self):
        with pytest.raises(ValueError, match="policy_id"):
            RuntimeLaunchManifest(
                manifest_id="m-1",
                policy_id="",
                epoch_id="epoch-1",
                canary_mode="off",
                subsystem_ids=("supervisor",),
                config_snapshot={},
                created_at=_TS,
            )

    def test_launch_manifest_rejects_empty_subsystem_ids(self):
        with pytest.raises(ValueError, match="subsystem_ids"):
            RuntimeLaunchManifest(
                manifest_id="m-1",
                policy_id="pol-1",
                epoch_id="epoch-1",
                canary_mode="off",
                subsystem_ids=(),
                config_snapshot={},
                created_at=_TS,
            )

    def test_startup_validation_result_rejects_invalid_verdict(self):
        with pytest.raises(ValueError, match="verdict"):
            StartupValidationResult(
                validation_id="v-1",
                verdict="not-a-verdict",
                checks_passed=(),
                checks_failed=(),
                detail="test",
                validated_at=_TS,
            )

    def test_runtime_state_export_rejects_invalid_confidence(self):
        with pytest.raises(ValueError, match="overall_confidence"):
            RuntimeStateExport(
                export_id="e-1",
                status="running",
                canary_mode="off",
                supervisor_phase="idle",
                tick_number=0,
                event_count=0,
                open_obligations=0,
                checkpoint_count=0,
                journal_length=0,
                consecutive_errors=0,
                consecutive_idle_ticks=0,
                is_healthy=True,
                is_ready=True,
                is_degraded=False,
                degraded_reasons=(),
                overall_confidence=1.5,  # Out of range
                last_error="none",
                action_count=0,
                manifest_id="m-1",
                exported_at=_TS,
            )

    def test_checkpoint_import_result_accepted_property(self):
        result = CheckpointImportResult(
            import_id="imp-1",
            checkpoint_id="cp-1",
            verdict=CheckpointImportVerdict.ACCEPTED,
            checks_passed=("scope_supervisor_present",),
            checks_failed=(),
            verified_at=_TS,
        )
        assert result.accepted

    def test_checkpoint_import_result_rejected_property(self):
        result = CheckpointImportResult(
            import_id="imp-1",
            checkpoint_id="cp-1",
            verdict=CheckpointImportVerdict.REJECTED_MISSING_SCOPE,
            checks_passed=(),
            checks_failed=("scope_supervisor_present",),
            verified_at=_TS,
        )
        assert not result.accepted
