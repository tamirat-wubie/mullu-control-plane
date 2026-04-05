"""Engine-level tests for FaultInjectionEngine."""

from __future__ import annotations

import pytest

from mcoi_runtime.contracts.fault_injection import (
    FaultDisposition,
    FaultSeverity,
    FaultSpec,
    FaultTargetKind,
    FaultType,
    FaultWindow,
    InjectionMode,
)
from mcoi_runtime.core.fault_injection import FaultInjectionEngine
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError

NOW = "2026-03-20T12:00:00+00:00"


def _make_spec(spec_id="fs-1", fault_type=FaultType.FAILURE,
               target_kind=FaultTargetKind.PROVIDER,
               severity=FaultSeverity.MEDIUM,
               injection_mode=InjectionMode.SINGLE,
               repeat_count=1, **kw):
    return FaultSpec(
        spec_id=spec_id, fault_type=fault_type,
        target_kind=target_kind, severity=severity,
        injection_mode=injection_mode, repeat_count=repeat_count,
        created_at=NOW, **kw,
    )


# ---------------------------------------------------------------------------
# Spec registration
# ---------------------------------------------------------------------------


class TestSpecRegistration:
    def test_register(self):
        engine = FaultInjectionEngine()
        spec = engine.register_spec(_make_spec())
        assert spec.spec_id == "fs-1"
        assert engine.spec_count == 1

    def test_duplicate_rejected(self):
        engine = FaultInjectionEngine()
        engine.register_spec(_make_spec())
        with pytest.raises(RuntimeCoreInvariantError, match="already registered"):
            engine.register_spec(_make_spec())

    def test_invalid_spec(self):
        engine = FaultInjectionEngine()
        with pytest.raises(RuntimeCoreInvariantError, match="FaultSpec"):
            engine.register_spec("bad")

    def test_get_spec(self):
        engine = FaultInjectionEngine()
        engine.register_spec(_make_spec())
        assert engine.get_spec("fs-1").spec_id == "fs-1"

    def test_get_missing(self):
        engine = FaultInjectionEngine()
        with pytest.raises(RuntimeCoreInvariantError, match="not found"):
            engine.get_spec("missing")

    def test_list_all(self):
        engine = FaultInjectionEngine()
        engine.register_spec(_make_spec("fs-1"))
        engine.register_spec(_make_spec("fs-2", fault_type=FaultType.TIMEOUT))
        assert len(engine.list_specs()) == 2

    def test_list_by_fault_type(self):
        engine = FaultInjectionEngine()
        engine.register_spec(_make_spec("fs-1"))
        engine.register_spec(_make_spec("fs-2", fault_type=FaultType.TIMEOUT))
        assert len(engine.list_specs(fault_type=FaultType.TIMEOUT)) == 1

    def test_list_by_target(self):
        engine = FaultInjectionEngine()
        engine.register_spec(_make_spec("fs-1"))
        engine.register_spec(_make_spec("fs-2", target_kind=FaultTargetKind.SUPERVISOR))
        assert len(engine.list_specs(target_kind=FaultTargetKind.SUPERVISOR)) == 1

    def test_list_by_severity(self):
        engine = FaultInjectionEngine()
        engine.register_spec(_make_spec("fs-1"))
        engine.register_spec(_make_spec("fs-2", severity=FaultSeverity.CRITICAL))
        assert len(engine.list_specs(severity=FaultSeverity.CRITICAL)) == 1


# ---------------------------------------------------------------------------
# Windows
# ---------------------------------------------------------------------------


class TestWindows:
    def test_set_window(self):
        engine = FaultInjectionEngine()
        engine.register_spec(_make_spec())
        w = engine.set_window(FaultWindow(
            window_id="w-1", spec_id="fs-1",
            start_tick=5, end_tick=15, created_at=NOW,
        ))
        assert w.window_id == "w-1"

    def test_window_requires_spec(self):
        engine = FaultInjectionEngine()
        with pytest.raises(RuntimeCoreInvariantError, match="not found"):
            engine.set_window(FaultWindow(
                window_id="w-1", spec_id="missing",
                start_tick=0, end_tick=10, created_at=NOW,
            ))

    def test_duplicate_window(self):
        engine = FaultInjectionEngine()
        engine.register_spec(_make_spec())
        engine.set_window(FaultWindow(
            window_id="w-1", spec_id="fs-1",
            start_tick=0, end_tick=10, created_at=NOW,
        ))
        with pytest.raises(RuntimeCoreInvariantError, match="already exists"):
            engine.set_window(FaultWindow(
                window_id="w-1", spec_id="fs-1",
                start_tick=0, end_tick=10, created_at=NOW,
            ))

    def test_is_active_no_window(self):
        engine = FaultInjectionEngine()
        engine.register_spec(_make_spec())
        # No window → always active for SINGLE mode
        assert engine.is_active_at_tick("fs-1", 0) is True

    def test_is_active_windowed_requires_window(self):
        engine = FaultInjectionEngine()
        engine.register_spec(_make_spec(injection_mode=InjectionMode.WINDOWED))
        # Windowed mode with no window → not active
        assert engine.is_active_at_tick("fs-1", 0) is False

    def test_is_active_within_window(self):
        engine = FaultInjectionEngine()
        engine.register_spec(_make_spec(injection_mode=InjectionMode.WINDOWED,
                                        repeat_count=100))
        engine.set_window(FaultWindow(
            window_id="w-1", spec_id="fs-1",
            start_tick=5, end_tick=15, created_at=NOW,
        ))
        assert engine.is_active_at_tick("fs-1", 3) is False
        assert engine.is_active_at_tick("fs-1", 5) is True
        assert engine.is_active_at_tick("fs-1", 10) is True
        assert engine.is_active_at_tick("fs-1", 15) is True
        assert engine.is_active_at_tick("fs-1", 16) is False

    def test_is_active_missing_spec(self):
        engine = FaultInjectionEngine()
        assert engine.is_active_at_tick("missing", 0) is False


# ---------------------------------------------------------------------------
# Injection
# ---------------------------------------------------------------------------


class TestInjection:
    def test_inject_single(self):
        engine = FaultInjectionEngine()
        engine.register_spec(_make_spec())
        record = engine.inject("fs-1", tick=0)
        assert record is not None
        assert record.disposition == FaultDisposition.INJECTED
        assert engine.record_count == 1

    def test_inject_single_exhausts(self):
        engine = FaultInjectionEngine()
        engine.register_spec(_make_spec())
        engine.inject("fs-1", tick=0)
        assert engine.inject("fs-1", tick=1) is None

    def test_inject_repeated(self):
        engine = FaultInjectionEngine()
        engine.register_spec(_make_spec(
            injection_mode=InjectionMode.REPEATED, repeat_count=3,
        ))
        for i in range(3):
            assert engine.inject("fs-1", tick=i) is not None
        assert engine.inject("fs-1", tick=3) is None
        assert engine.record_count == 3

    def test_inject_for_target(self):
        engine = FaultInjectionEngine()
        engine.register_spec(_make_spec("fs-1", target_kind=FaultTargetKind.PROVIDER))
        engine.register_spec(_make_spec("fs-2", target_kind=FaultTargetKind.SUPERVISOR))
        records = engine.inject_for_target(FaultTargetKind.PROVIDER, tick=0)
        assert len(records) == 1
        assert records[0].target_kind == FaultTargetKind.PROVIDER

    def test_inject_not_active(self):
        engine = FaultInjectionEngine()
        engine.register_spec(_make_spec(injection_mode=InjectionMode.WINDOWED))
        # No window set → not active for windowed mode
        assert engine.inject("fs-1", tick=0) is None


# ---------------------------------------------------------------------------
# Observations
# ---------------------------------------------------------------------------


class TestObservations:
    def test_record_observation(self):
        engine = FaultInjectionEngine()
        engine.register_spec(_make_spec())
        record = engine.inject("fs-1", tick=0)
        obs = engine.record_observation(
            record.record_id,
            observed_behavior="system degraded gracefully",
            matches_expected=True,
        )
        assert obs.matches_expected is True
        assert engine.observation_count == 1

    def test_observation_requires_record(self):
        engine = FaultInjectionEngine()
        with pytest.raises(RuntimeCoreInvariantError, match="not found"):
            engine.record_observation("missing", "something happened")

    def test_get_observations_for_record(self):
        engine = FaultInjectionEngine()
        engine.register_spec(_make_spec())
        record = engine.inject("fs-1", tick=0)
        engine.record_observation(record.record_id, "obs 1")
        engine.record_observation(record.record_id, "obs 2")
        obs = engine.get_observations_for_record(record.record_id)
        assert len(obs) == 2


# ---------------------------------------------------------------------------
# Recovery assessments
# ---------------------------------------------------------------------------


class TestRecoveryAssessments:
    def test_assess_recovered(self):
        engine = FaultInjectionEngine()
        engine.register_spec(_make_spec())
        record = engine.inject("fs-1", tick=0)
        assessment = engine.assess_recovery(
            record.record_id, recovered=True,
            recovery_method="rollback",
        )
        assert assessment.recovered is True
        assert engine.assessment_count == 1

    def test_assess_degraded(self):
        engine = FaultInjectionEngine()
        engine.register_spec(_make_spec())
        record = engine.inject("fs-1", tick=0)
        assessment = engine.assess_recovery(
            record.record_id, recovered=False,
            degraded=True, degraded_reason="partial service",
        )
        assert assessment.degraded is True

    def test_assess_requires_record(self):
        engine = FaultInjectionEngine()
        with pytest.raises(RuntimeCoreInvariantError, match="not found"):
            engine.assess_recovery("missing", recovered=True)


# ---------------------------------------------------------------------------
# Sessions and outcomes
# ---------------------------------------------------------------------------


class TestSessions:
    def test_start_session(self):
        engine = FaultInjectionEngine()
        engine.register_spec(_make_spec("fs-1"))
        engine.register_spec(_make_spec("fs-2", fault_type=FaultType.TIMEOUT))
        session = engine.start_session("test", ("fs-1", "fs-2"))
        assert session.name == "test"
        assert len(session.fault_spec_ids) == 2
        assert engine.session_count == 1

    def test_session_requires_valid_specs(self):
        engine = FaultInjectionEngine()
        with pytest.raises(RuntimeCoreInvariantError, match="not found"):
            engine.start_session("test", ("missing",))

    def test_complete_session(self):
        engine = FaultInjectionEngine()
        engine.register_spec(_make_spec("fs-1", repeat_count=3,
                                        injection_mode=InjectionMode.REPEATED))
        session = engine.start_session("test", ("fs-1",))

        # Inject and assess
        for i in range(3):
            record = engine.inject("fs-1", tick=i)
            engine.assess_recovery(record.record_id, recovered=True)

        outcome = engine.complete_session(session.session_id)
        assert outcome.passed is True
        assert outcome.total_faults == 3
        assert outcome.faults_recovered == 3
        assert outcome.score == 1.0
        assert engine.outcome_count == 1

    def test_complete_missing_session(self):
        engine = FaultInjectionEngine()
        with pytest.raises(RuntimeCoreInvariantError, match="not found"):
            engine.complete_session("missing")


# ---------------------------------------------------------------------------
# Built-in fault families
# ---------------------------------------------------------------------------


class TestFaultFamilies:
    def test_provider_storm(self):
        engine = FaultInjectionEngine()
        specs = engine.register_provider_storm()
        assert len(specs) == 3
        assert all(s.target_kind == FaultTargetKind.PROVIDER for s in specs)

    def test_event_flood(self):
        engine = FaultInjectionEngine()
        specs = engine.register_event_flood()
        assert len(specs) == 2
        assert all(s.target_kind == FaultTargetKind.EVENT_SPINE for s in specs)

    def test_checkpoint_corruption(self):
        engine = FaultInjectionEngine()
        specs = engine.register_checkpoint_corruption()
        assert len(specs) == 2
        assert all(s.target_kind == FaultTargetKind.CHECKPOINT for s in specs)

    def test_communication_failure(self):
        engine = FaultInjectionEngine()
        specs = engine.register_communication_failure()
        assert len(specs) == 3
        assert all(s.target_kind == FaultTargetKind.COMMUNICATION for s in specs)

    def test_artifact_corruption(self):
        engine = FaultInjectionEngine()
        specs = engine.register_artifact_corruption()
        assert len(specs) == 3

    def test_obligation_escalation_stress(self):
        engine = FaultInjectionEngine()
        specs = engine.register_obligation_escalation_stress()
        assert len(specs) == 3

    def test_governance_conflict_storm(self):
        engine = FaultInjectionEngine()
        specs = engine.register_governance_conflict_storm()
        assert len(specs) == 2

    def test_domain_pack_conflict_stress(self):
        engine = FaultInjectionEngine()
        specs = engine.register_domain_pack_conflict_stress()
        assert len(specs) == 2


# ---------------------------------------------------------------------------
# Retrieval
# ---------------------------------------------------------------------------


class TestRetrieval:
    def test_get_records_all(self):
        engine = FaultInjectionEngine()
        engine.register_spec(_make_spec(repeat_count=3,
                                        injection_mode=InjectionMode.REPEATED))
        for i in range(3):
            engine.inject("fs-1", tick=i)
        assert len(engine.get_records()) == 3

    def test_get_records_by_spec(self):
        engine = FaultInjectionEngine()
        engine.register_spec(_make_spec("fs-1"))
        engine.register_spec(_make_spec("fs-2", fault_type=FaultType.TIMEOUT))
        engine.inject("fs-1", tick=0)
        engine.inject("fs-2", tick=0)
        assert len(engine.get_records(spec_id="fs-1")) == 1

    def test_get_session(self):
        engine = FaultInjectionEngine()
        engine.register_spec(_make_spec())
        session = engine.start_session("test", ("fs-1",))
        assert engine.get_session(session.session_id).name == "test"

    def test_get_outcome(self):
        engine = FaultInjectionEngine()
        engine.register_spec(_make_spec())
        session = engine.start_session("test", ("fs-1",))
        record = engine.inject("fs-1", tick=0)
        engine.assess_recovery(record.record_id, recovered=True)
        outcome = engine.complete_session(session.session_id)
        assert engine.get_outcome(outcome.outcome_id).passed is True


# ---------------------------------------------------------------------------
# State hash
# ---------------------------------------------------------------------------


class TestStateHash:
    def test_deterministic(self):
        e1 = FaultInjectionEngine()
        e2 = FaultInjectionEngine()
        assert e1.state_hash() == e2.state_hash()

    def test_changes_on_register(self):
        engine = FaultInjectionEngine()
        h1 = engine.state_hash()
        engine.register_spec(_make_spec())
        h2 = engine.state_hash()
        assert h1 != h2

    def test_length(self):
        engine = FaultInjectionEngine()
        assert len(engine.state_hash()) == 64


class TestBoundedFaultContracts:
    def test_missing_session_does_not_echo_session_id(self):
        engine = FaultInjectionEngine()
        with pytest.raises(RuntimeCoreInvariantError, match="session not found") as exc:
            engine.complete_session("session-secret")
        assert "session-secret" not in str(exc.value)

    @pytest.mark.parametrize(
        ("register", "expected_description"),
        [
            ("register_provider_storm", "provider failure storm"),
            ("register_event_flood", "event flood"),
            ("register_checkpoint_corruption", "checkpoint corruption"),
            ("register_communication_failure", "communication failure"),
            ("register_artifact_corruption", "artifact corruption"),
            ("register_obligation_escalation_stress", "obligation escalation stress"),
            ("register_governance_conflict_storm", "governance conflict storm"),
            ("register_domain_pack_conflict_stress", "domain pack conflict stress"),
        ],
    )
    def test_builtin_fault_family_descriptions_are_bounded(self, register: str, expected_description: str):
        engine = FaultInjectionEngine()
        specs = getattr(engine, register)()
        assert specs
        assert {spec.description for spec in specs} == {expected_description}
