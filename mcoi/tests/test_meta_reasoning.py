"""Purpose: verify meta-reasoning engine — confidence tracking, degraded mode, uncertainty, health.
Governance scope: meta-reasoning plane tests only.
Dependencies: meta-reasoning contracts, meta-reasoning engine.
Invariants: confidence from history; uncertainty explicit; health deterministic.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.contracts.meta_reasoning import (
    CapabilityConfidence,
    EscalationRecommendation,
    EscalationSeverity,
    HealthStatus,
    SubsystemHealth,
    UncertaintyReport,
    UncertaintySource,
)
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
from mcoi_runtime.core.meta_reasoning import MetaReasoningEngine


_CLOCK = "2026-03-19T00:00:00+00:00"


def _confidence(
    capability_id: str = "cap-1",
    success: float = 0.9,
    verify: float = 0.95,
    timeout: float = 0.05,
    error: float = 0.02,
    samples: int = 100,
) -> CapabilityConfidence:
    return CapabilityConfidence(
        capability_id=capability_id,
        success_rate=success,
        verification_pass_rate=verify,
        timeout_rate=timeout,
        error_rate=error,
        sample_count=samples,
        assessed_at=_CLOCK,
    )


# --- Confidence tests ---

def test_overall_confidence_computed() -> None:
    c = _confidence(success=0.9, verify=1.0, error=0.0)
    assert c.overall_confidence == 0.9


def test_overall_confidence_zero_samples() -> None:
    c = _confidence(samples=0)
    assert c.overall_confidence == 0.0


def test_confidence_rejects_out_of_range() -> None:
    with pytest.raises(ValueError, match="success_rate"):
        _confidence(success=1.5)


def test_update_and_get_confidence() -> None:
    engine = MetaReasoningEngine(clock=lambda: _CLOCK)
    engine.update_confidence(_confidence("cap-1"))
    assert engine.get_confidence("cap-1") is not None


# --- Degraded mode tests ---

def test_degraded_mode_triggers_on_low_confidence() -> None:
    engine = MetaReasoningEngine(clock=lambda: _CLOCK, default_threshold=0.8)
    engine.update_confidence(_confidence("cap-1", success=0.3, verify=0.3, error=0.5))
    assert engine.is_degraded("cap-1") is True
    assert len(engine.list_degraded()) == 1


def test_degraded_mode_exits_on_recovery() -> None:
    engine = MetaReasoningEngine(clock=lambda: _CLOCK, default_threshold=0.5)
    engine.update_confidence(_confidence("cap-1", success=0.2, verify=0.2, error=0.8))
    assert engine.is_degraded("cap-1") is True

    engine.update_confidence(_confidence("cap-1", success=0.95, verify=0.95, error=0.01))
    assert engine.is_degraded("cap-1") is False


def test_custom_threshold() -> None:
    engine = MetaReasoningEngine(clock=lambda: _CLOCK, default_threshold=0.1)
    engine.set_threshold("cap-1", 0.95)
    engine.update_confidence(_confidence("cap-1", success=0.9, verify=0.9, error=0.0))
    # 0.9 * 0.9 * 1.0 = 0.81, below 0.95 threshold
    assert engine.is_degraded("cap-1") is True


# --- Uncertainty tests ---

def test_report_uncertainty() -> None:
    engine = MetaReasoningEngine(clock=lambda: _CLOCK)
    report = UncertaintyReport(
        report_id="u-1",
        subject="filesystem state",
        source=UncertaintySource.INCOMPLETE_OBSERVATION,
        description="only partial directory listing available",
        affected_ids=("e-1",),
        created_at=_CLOCK,
    )
    engine.report_uncertainty(report)
    assert len(engine.list_uncertainty()) == 1


def test_duplicate_uncertainty_rejected() -> None:
    engine = MetaReasoningEngine(clock=lambda: _CLOCK)
    report = UncertaintyReport(
        report_id="u-1", subject="s", source=UncertaintySource.LOW_CONFIDENCE,
        description="d", affected_ids=(), created_at=_CLOCK,
    )
    engine.report_uncertainty(report)
    with pytest.raises(RuntimeCoreInvariantError, match="already exists"):
        engine.report_uncertainty(report)


# --- Escalation tests ---

def test_recommend_escalation() -> None:
    engine = MetaReasoningEngine(clock=lambda: _CLOCK)
    rec = EscalationRecommendation(
        recommendation_id="esc-1",
        reason="capability degraded",
        severity=EscalationSeverity.HIGH,
        affected_ids=("cap-1",),
        suggested_action="notify operator",
        created_at=_CLOCK,
    )
    engine.recommend_escalation(rec)
    assert len(engine.list_escalation_recommendations()) == 1


# --- Health assessment tests ---

def test_health_snapshot_healthy() -> None:
    engine = MetaReasoningEngine(clock=lambda: _CLOCK)
    snapshot = engine.assess_health((
        SubsystemHealth(subsystem="execution", status=HealthStatus.HEALTHY, details="ok"),
        SubsystemHealth(subsystem="persistence", status=HealthStatus.HEALTHY, details="ok"),
    ))
    assert snapshot.overall_status is HealthStatus.HEALTHY


def test_health_snapshot_degraded() -> None:
    engine = MetaReasoningEngine(clock=lambda: _CLOCK)
    snapshot = engine.assess_health((
        SubsystemHealth(subsystem="execution", status=HealthStatus.HEALTHY, details="ok"),
        SubsystemHealth(subsystem="integration", status=HealthStatus.DEGRADED, details="slow"),
    ))
    assert snapshot.overall_status is HealthStatus.DEGRADED


def test_health_snapshot_unavailable_trumps_degraded() -> None:
    engine = MetaReasoningEngine(clock=lambda: _CLOCK)
    snapshot = engine.assess_health((
        SubsystemHealth(subsystem="execution", status=HealthStatus.DEGRADED, details="slow"),
        SubsystemHealth(subsystem="persistence", status=HealthStatus.UNAVAILABLE, details="disk full"),
    ))
    assert snapshot.overall_status is HealthStatus.UNAVAILABLE


def test_health_snapshot_deterministic_id() -> None:
    engine = MetaReasoningEngine(clock=lambda: _CLOCK)
    checks = (
        SubsystemHealth(subsystem="execution", status=HealthStatus.HEALTHY, details="ok"),
    )
    s1 = engine.assess_health(checks)
    s2 = engine.assess_health(checks)
    assert s1.snapshot_id == s2.snapshot_id
