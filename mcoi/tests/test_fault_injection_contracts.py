"""Contract-level tests for fault_injection contracts."""

from __future__ import annotations

import pytest

from mcoi_runtime.contracts.fault_injection import (
    AdversarialOutcome,
    AdversarialSession,
    FaultDisposition,
    FaultInjectionRecord,
    FaultObservation,
    FaultRecoveryAssessment,
    FaultSeverity,
    FaultSpec,
    FaultTargetKind,
    FaultType,
    FaultWindow,
    InjectionMode,
)

NOW = "2026-03-20T12:00:00+00:00"


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class TestEnumCoverage:
    def test_fault_type_count(self):
        assert len(FaultType) == 12

    def test_fault_target_kind_count(self):
        assert len(FaultTargetKind) == 12

    def test_fault_severity_count(self):
        assert len(FaultSeverity) == 4

    def test_fault_disposition_count(self):
        assert len(FaultDisposition) == 7

    def test_injection_mode_count(self):
        assert len(InjectionMode) == 4


# ---------------------------------------------------------------------------
# FaultSpec
# ---------------------------------------------------------------------------


class TestFaultSpec:
    def _make(self, **kw):
        defaults = dict(
            spec_id="fs-1",
            fault_type=FaultType.FAILURE,
            target_kind=FaultTargetKind.PROVIDER,
            severity=FaultSeverity.MEDIUM,
            created_at=NOW,
        )
        defaults.update(kw)
        return FaultSpec(**defaults)

    def test_valid(self):
        s = self._make()
        assert s.spec_id == "fs-1"
        assert s.repeat_count == 1

    def test_empty_spec_id_rejected(self):
        with pytest.raises(ValueError):
            self._make(spec_id="")

    def test_invalid_fault_type(self):
        with pytest.raises(ValueError) as exc_info:
            self._make(fault_type="magic")
        message = str(exc_info.value)
        assert message == "fault_type must be a FaultType value"
        assert "magic" not in message
        assert "str" not in message

    def test_invalid_target_kind(self):
        with pytest.raises(ValueError) as exc_info:
            self._make(target_kind="mars")
        message = str(exc_info.value)
        assert message == "target_kind must be a FaultTargetKind value"
        assert "mars" not in message
        assert "str" not in message

    def test_invalid_severity(self):
        with pytest.raises(ValueError) as exc_info:
            self._make(severity="extreme")
        message = str(exc_info.value)
        assert message == "severity must be a FaultSeverity value"
        assert "extreme" not in message
        assert "str" not in message

    def test_invalid_injection_mode(self):
        with pytest.raises(ValueError) as exc_info:
            self._make(injection_mode="loop")
        message = str(exc_info.value)
        assert message == "injection_mode must be an InjectionMode value"
        assert "loop" not in message
        assert "str" not in message

    def test_zero_repeat_rejected(self):
        with pytest.raises(ValueError):
            self._make(repeat_count=0)

    def test_tags_frozen(self):
        s = self._make(tags=["a", "b"])
        assert s.tags == ("a", "b")

    def test_metadata_frozen(self):
        s = self._make(metadata={"k": "v"})
        with pytest.raises(TypeError):
            s.metadata["new"] = "val"

    def test_frozen(self):
        s = self._make()
        with pytest.raises(AttributeError):
            s.spec_id = "new"

    def test_all_fault_types(self):
        for ft in FaultType:
            s = self._make(fault_type=ft)
            assert s.fault_type == ft

    def test_all_target_kinds(self):
        for tk in FaultTargetKind:
            s = self._make(target_kind=tk)
            assert s.target_kind == tk

    def test_all_severities(self):
        for sv in FaultSeverity:
            s = self._make(severity=sv)
            assert s.severity == sv

    def test_all_injection_modes(self):
        for im in InjectionMode:
            s = self._make(injection_mode=im)
            assert s.injection_mode == im

    def test_serialization(self):
        d = self._make().to_dict()
        assert d["fault_type"] == "failure"
        assert d["target_kind"] == "provider"


# ---------------------------------------------------------------------------
# FaultWindow
# ---------------------------------------------------------------------------


class TestFaultWindow:
    def test_valid(self):
        w = FaultWindow(
            window_id="w-1", spec_id="fs-1",
            start_tick=0, end_tick=10, created_at=NOW,
        )
        assert w.end_tick == 10

    def test_end_before_start_rejected(self):
        with pytest.raises(ValueError):
            FaultWindow(
                window_id="w-bad", spec_id="fs-1",
                start_tick=10, end_tick=5, created_at=NOW,
            )

    def test_empty_window_id_rejected(self):
        with pytest.raises(ValueError):
            FaultWindow(
                window_id="", spec_id="fs-1",
                start_tick=0, end_tick=10, created_at=NOW,
            )


# ---------------------------------------------------------------------------
# FaultInjectionRecord
# ---------------------------------------------------------------------------


class TestFaultInjectionRecord:
    def test_valid(self):
        r = FaultInjectionRecord(
            record_id="fir-1", spec_id="fs-1",
            injected_at=NOW,
        )
        assert r.disposition == FaultDisposition.INJECTED

    def test_empty_record_id_rejected(self):
        with pytest.raises(ValueError):
            FaultInjectionRecord(
                record_id="", spec_id="fs-1",
                injected_at=NOW,
            )


# ---------------------------------------------------------------------------
# FaultObservation
# ---------------------------------------------------------------------------


class TestFaultObservation:
    def test_valid(self):
        o = FaultObservation(
            observation_id="fo-1", record_id="fir-1",
            observed_behavior="system degraded",
            observed_at=NOW,
        )
        assert o.matches_expected is False

    def test_empty_observed_behavior_rejected(self):
        with pytest.raises(ValueError):
            FaultObservation(
                observation_id="fo-bad", record_id="fir-1",
                observed_behavior="",
                observed_at=NOW,
            )


# ---------------------------------------------------------------------------
# FaultRecoveryAssessment
# ---------------------------------------------------------------------------


class TestFaultRecoveryAssessment:
    def test_valid_recovered(self):
        a = FaultRecoveryAssessment(
            assessment_id="fra-1", record_id="fir-1",
            recovered=True, recovery_method="rollback",
            assessed_at=NOW,
        )
        assert a.recovered is True
        assert a.state_consistent is True

    def test_valid_degraded(self):
        a = FaultRecoveryAssessment(
            assessment_id="fra-2", record_id="fir-1",
            recovered=False, degraded=True,
            degraded_reason="partial service",
            assessed_at=NOW,
        )
        assert a.degraded is True

    def test_empty_assessment_id_rejected(self):
        with pytest.raises(ValueError):
            FaultRecoveryAssessment(
                assessment_id="", record_id="fir-1",
                assessed_at=NOW,
            )


# ---------------------------------------------------------------------------
# AdversarialSession
# ---------------------------------------------------------------------------


class TestAdversarialSession:
    def test_valid(self):
        s = AdversarialSession(
            session_id="as-1", name="test-campaign",
            fault_spec_ids=("fs-1", "fs-2"),
            started_at=NOW,
        )
        assert len(s.fault_spec_ids) == 2

    def test_empty_name_rejected(self):
        with pytest.raises(ValueError):
            AdversarialSession(
                session_id="as-bad", name="",
                started_at=NOW,
            )

    def test_tags_frozen(self):
        s = AdversarialSession(
            session_id="as-2", name="test",
            tags=["a"], started_at=NOW,
        )
        assert s.tags == ("a",)


# ---------------------------------------------------------------------------
# AdversarialOutcome
# ---------------------------------------------------------------------------


class TestAdversarialOutcome:
    def test_valid_passed(self):
        o = AdversarialOutcome(
            outcome_id="ao-1", session_id="as-1",
            passed=True, total_faults=5,
            faults_detected=5, faults_recovered=5,
            state_consistent=True, score=1.0,
            completed_at=NOW,
        )
        assert o.passed is True
        assert o.score == 1.0

    def test_valid_failed(self):
        o = AdversarialOutcome(
            outcome_id="ao-2", session_id="as-1",
            passed=False, total_faults=5,
            faults_failed=2, score=0.6,
            completed_at=NOW,
        )
        assert o.passed is False

    def test_score_out_of_range(self):
        with pytest.raises(ValueError):
            AdversarialOutcome(
                outcome_id="ao-bad", session_id="as-1",
                score=1.5, completed_at=NOW,
            )

    def test_frozen(self):
        o = AdversarialOutcome(
            outcome_id="ao-3", session_id="as-1",
            score=0.5, completed_at=NOW,
        )
        with pytest.raises(AttributeError):
            o.passed = True
