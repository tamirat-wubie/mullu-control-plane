"""Comprehensive tests for the EngineeringRuntimeEngine.

Tests cover: construction, quantity registration, tolerance checking (auto-status),
reliability targets, safety margin assessment (auto-status), load envelope
measurement (auto-status), process window measurement (auto-status), capacity
curves, snapshots, violation detection (idempotent), state_hash, and properties.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.contracts.engineering_runtime import (
    CapacityCurve,
    EngineeringDomain,
    EngineeringQuantity,
    EngineeringSnapshot,
    EngineeringViolation,
    LoadEnvelope,
    LoadEnvelopeStatus,
    ProcessWindow,
    ProcessWindowStatus,
    ReliabilityGrade,
    ReliabilityTarget,
    SafetyMargin,
    SafetyMarginStatus,
    ToleranceRecord,
    ToleranceStatus,
)
from mcoi_runtime.core.engineering_runtime import EngineeringRuntimeEngine
from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.engine_protocol import FixedClock
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError


# ===================================================================
# Fixtures
# ===================================================================


@pytest.fixture()
def clock():
    return FixedClock("2026-01-01T00:00:00+00:00")


@pytest.fixture()
def es():
    return EventSpineEngine()


@pytest.fixture()
def engine(es, clock):
    return EngineeringRuntimeEngine(es, clock=clock)


def _register_qty(engine, quantity_id="q-1", tenant_id="t-1", value=50.0,
                   domain=EngineeringDomain.THERMAL):
    return engine.register_quantity(
        quantity_id=quantity_id, tenant_id=tenant_id,
        display_name=f"Qty {quantity_id}", value=value,
        unit_label="C", domain=domain, tolerance=1.0,
    )


# ===================================================================
# Construction Tests
# ===================================================================


class TestEngineConstruction:
    def test_valid_construction(self, es, clock):
        eng = EngineeringRuntimeEngine(es, clock=clock)
        assert eng.quantity_count == 0

    def test_construction_without_clock(self, es):
        eng = EngineeringRuntimeEngine(es)
        assert eng.quantity_count == 0

    def test_invalid_event_spine(self, clock):
        with pytest.raises(RuntimeCoreInvariantError):
            EngineeringRuntimeEngine("not_spine", clock=clock)


# ===================================================================
# Quantity Tests
# ===================================================================


class TestQuantities:
    def test_register_quantity(self, engine):
        q = _register_qty(engine)
        assert q.quantity_id == "q-1"
        assert q.value == 50.0
        assert engine.quantity_count == 1

    def test_duplicate_quantity_raises(self, engine):
        _register_qty(engine)
        with pytest.raises(RuntimeCoreInvariantError) as exc_info:
            _register_qty(engine)
        assert str(exc_info.value) == "Duplicate quantity_id"
        assert "q-1" not in str(exc_info.value)

    def test_get_quantity(self, engine):
        _register_qty(engine)
        q = engine.get_quantity("q-1")
        assert q.value == 50.0

    def test_get_unknown_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError) as exc_info:
            engine.get_quantity("nope")
        assert str(exc_info.value) == "Unknown quantity_id"
        assert "nope" not in str(exc_info.value)

    def test_quantities_for_tenant(self, engine):
        _register_qty(engine, "q-1", "t-1")
        _register_qty(engine, "q-2", "t-2")
        result = engine.quantities_for_tenant("t-1")
        assert len(result) == 1


# ===================================================================
# Tolerance Tests
# ===================================================================


class TestTolerances:
    def test_tolerance_within(self, engine):
        _register_qty(engine, value=100.0)
        tol = engine.check_tolerance("tol-1", "t-1", "q-1", 100.0, 80.0, 120.0)
        assert tol.status == ToleranceStatus.WITHIN

    def test_tolerance_exceeded_below(self, engine):
        _register_qty(engine, value=70.0)
        tol = engine.check_tolerance("tol-1", "t-1", "q-1", 100.0, 80.0, 120.0)
        assert tol.status == ToleranceStatus.EXCEEDED

    def test_tolerance_exceeded_above(self, engine):
        _register_qty(engine, value=130.0)
        tol = engine.check_tolerance("tol-1", "t-1", "q-1", 100.0, 80.0, 120.0)
        assert tol.status == ToleranceStatus.EXCEEDED

    def test_tolerance_warning_near_lower(self, engine):
        # span=40, warning_band=4, lower+band=84, value=82 -> WARNING
        _register_qty(engine, value=82.0)
        tol = engine.check_tolerance("tol-1", "t-1", "q-1", 100.0, 80.0, 120.0)
        assert tol.status == ToleranceStatus.WARNING

    def test_tolerance_warning_near_upper(self, engine):
        # span=40, warning_band=4, upper-band=116, value=118 -> WARNING
        _register_qty(engine, value=118.0)
        tol = engine.check_tolerance("tol-1", "t-1", "q-1", 100.0, 80.0, 120.0)
        assert tol.status == ToleranceStatus.WARNING

    def test_duplicate_tolerance_raises(self, engine):
        _register_qty(engine, value=100.0)
        engine.check_tolerance("tol-1", "t-1", "q-1", 100.0, 80.0, 120.0)
        with pytest.raises(RuntimeCoreInvariantError) as exc_info:
            engine.check_tolerance("tol-1", "t-1", "q-1", 100.0, 80.0, 120.0)
        assert str(exc_info.value) == "Duplicate tolerance_id"
        assert "tol-1" not in str(exc_info.value)


# ===================================================================
# Reliability Target Tests
# ===================================================================


class TestReliabilityTargets:
    def test_register_target(self, engine):
        tgt = engine.register_reliability_target(
            "rt-1", "t-1", "c-1", ReliabilityGrade.A, 5000.0, 0.99,
        )
        assert tgt.grade == ReliabilityGrade.A
        assert engine.target_count == 1

    def test_duplicate_target_raises(self, engine):
        engine.register_reliability_target("rt-1", "t-1", "c-1", ReliabilityGrade.A, 5000.0, 0.99)
        with pytest.raises(RuntimeCoreInvariantError) as exc_info:
            engine.register_reliability_target("rt-1", "t-1", "c-1", ReliabilityGrade.B, 3000.0, 0.95)
        assert str(exc_info.value) == "Duplicate target_id"
        assert "rt-1" not in str(exc_info.value)


# ===================================================================
# Safety Margin Tests
# ===================================================================


class TestSafetyMargins:
    def test_adequate_margin(self, engine):
        sm = engine.assess_safety_margin("sm-1", "t-1", "c-1", 100.0, 40.0)
        assert sm.status == SafetyMarginStatus.ADEQUATE
        assert sm.margin_ratio == 0.6

    def test_marginal_margin(self, engine):
        sm = engine.assess_safety_margin("sm-1", "t-1", "c-1", 100.0, 75.0)
        assert sm.status == SafetyMarginStatus.MARGINAL
        assert sm.margin_ratio == 0.25

    def test_insufficient_margin(self, engine):
        sm = engine.assess_safety_margin("sm-1", "t-1", "c-1", 100.0, 90.0)
        assert sm.status == SafetyMarginStatus.INSUFFICIENT
        assert sm.margin_ratio == pytest.approx(0.1)

    def test_overloaded_insufficient(self, engine):
        sm = engine.assess_safety_margin("sm-1", "t-1", "c-1", 100.0, 120.0)
        assert sm.status == SafetyMarginStatus.INSUFFICIENT
        # margin_ratio clamped to 0 since actual > design
        assert sm.margin_ratio == 0.0

    def test_zero_design_load(self, engine):
        sm = engine.assess_safety_margin("sm-1", "t-1", "c-1", 0.0, 0.0)
        assert sm.margin_ratio == 0.0
        assert sm.status == SafetyMarginStatus.INSUFFICIENT

    def test_duplicate_margin_raises(self, engine):
        engine.assess_safety_margin("sm-1", "t-1", "c-1", 100.0, 50.0)
        with pytest.raises(RuntimeCoreInvariantError) as exc_info:
            engine.assess_safety_margin("sm-1", "t-1", "c-1", 100.0, 50.0)
        assert str(exc_info.value) == "Duplicate margin_id"
        assert "sm-1" not in str(exc_info.value)


# ===================================================================
# Load Envelope Tests
# ===================================================================


class TestLoadEnvelopes:
    def test_nominal(self, engine):
        le = engine.measure_load_envelope("le-1", "t-1", "c-1", 100.0, 50.0)
        assert le.status == LoadEnvelopeStatus.NOMINAL

    def test_elevated(self, engine):
        le = engine.measure_load_envelope("le-1", "t-1", "c-1", 100.0, 75.0)
        assert le.status == LoadEnvelopeStatus.ELEVATED

    def test_overload(self, engine):
        le = engine.measure_load_envelope("le-1", "t-1", "c-1", 100.0, 95.0)
        assert le.status == LoadEnvelopeStatus.OVERLOAD

    def test_failure(self, engine):
        le = engine.measure_load_envelope("le-1", "t-1", "c-1", 100.0, 100.0)
        assert le.status == LoadEnvelopeStatus.FAILURE

    def test_failure_over_max(self, engine):
        le = engine.measure_load_envelope("le-1", "t-1", "c-1", 100.0, 110.0)
        assert le.status == LoadEnvelopeStatus.FAILURE


# ===================================================================
# Process Window Tests
# ===================================================================


class TestProcessWindows:
    def test_in_spec(self, engine):
        pw = engine.measure_process_window("pw-1", "t-1", "p-1", 50.0, 40.0, 60.0, 50.0)
        assert pw.status == ProcessWindowStatus.IN_SPEC

    def test_out_of_spec_below(self, engine):
        pw = engine.measure_process_window("pw-1", "t-1", "p-1", 50.0, 40.0, 60.0, 35.0)
        assert pw.status == ProcessWindowStatus.OUT_OF_SPEC

    def test_out_of_spec_above(self, engine):
        pw = engine.measure_process_window("pw-1", "t-1", "p-1", 50.0, 40.0, 60.0, 65.0)
        assert pw.status == ProcessWindowStatus.OUT_OF_SPEC

    def test_drift_near_lower(self, engine):
        # span=20, band=2, lower+band=42, value=41 -> DRIFT
        pw = engine.measure_process_window("pw-1", "t-1", "p-1", 50.0, 40.0, 60.0, 41.0)
        assert pw.status == ProcessWindowStatus.DRIFT

    def test_drift_near_upper(self, engine):
        # span=20, band=2, upper-band=58, value=59 -> DRIFT
        pw = engine.measure_process_window("pw-1", "t-1", "p-1", 50.0, 40.0, 60.0, 59.0)
        assert pw.status == ProcessWindowStatus.DRIFT


# ===================================================================
# Capacity Curve Tests
# ===================================================================


class TestCapacityCurves:
    def test_register_curve(self, engine):
        cc = engine.register_capacity_curve("cc-1", "t-1", "c-1", 1000.0, 0.5, 500.0)
        assert cc.max_capacity == 1000.0
        assert engine.curve_count == 1


# ===================================================================
# Snapshot Tests
# ===================================================================


class TestSnapshot:
    def test_engineering_snapshot(self, engine):
        _register_qty(engine)
        snap = engine.engineering_snapshot("ss-1", "t-1")
        assert snap.total_quantities == 1
        assert snap.total_violations == 0

    def test_snapshot_dict(self, engine):
        _register_qty(engine)
        s = engine.snapshot()
        assert "_state_hash" in s
        assert "quantities" in s

    def test_state_hash_deterministic(self, engine):
        h1 = engine.state_hash()
        h2 = engine.state_hash()
        assert h1 == h2


# ===================================================================
# Violation Detection Tests
# ===================================================================


class TestViolationDetection:
    def test_no_violations_on_clean_state(self, engine):
        _register_qty(engine, value=100.0)
        engine.check_tolerance("tol-1", "t-1", "q-1", 100.0, 80.0, 120.0)
        viols = engine.detect_engineering_violations("t-1")
        assert len(viols) == 0

    def test_tolerance_exceeded_violation(self, engine):
        _register_qty(engine, value=130.0)
        engine.check_tolerance("tol-1", "t-1", "q-1", 100.0, 80.0, 120.0)
        viols = engine.detect_engineering_violations("t-1")
        assert len(viols) == 1
        assert viols[0].operation == "tolerance_exceeded"
        assert viols[0].reason == "tolerance is exceeded"
        assert "tol-1" not in viols[0].reason
        assert "q-1" not in viols[0].reason

    def test_safety_margin_insufficient_violation(self, engine):
        engine.assess_safety_margin("sm-1", "t-1", "c-1", 100.0, 95.0)
        viols = engine.detect_engineering_violations("t-1")
        assert len(viols) == 1
        assert viols[0].operation == "safety_margin_insufficient"
        assert viols[0].reason == "safety margin is insufficient"
        assert "sm-1" not in viols[0].reason
        assert "c-1" not in viols[0].reason

    def test_load_envelope_failure_violation(self, engine):
        engine.measure_load_envelope("le-1", "t-1", "c-1", 100.0, 100.0)
        viols = engine.detect_engineering_violations("t-1")
        assert len(viols) == 1
        assert viols[0].operation == "load_envelope_failure"
        assert viols[0].reason == "load envelope is in failure"
        assert "le-1" not in viols[0].reason
        assert "c-1" not in viols[0].reason

    def test_idempotent_violation_detection(self, engine):
        _register_qty(engine, value=130.0)
        engine.check_tolerance("tol-1", "t-1", "q-1", 100.0, 80.0, 120.0)
        viols1 = engine.detect_engineering_violations("t-1")
        viols2 = engine.detect_engineering_violations("t-1")
        assert len(viols1) == 1
        assert len(viols2) == 0  # idempotent: already recorded
        assert engine.violation_count == 1

    def test_multiple_violations(self, engine):
        _register_qty(engine, value=130.0)
        engine.check_tolerance("tol-1", "t-1", "q-1", 100.0, 80.0, 120.0)
        engine.assess_safety_margin("sm-1", "t-1", "c-1", 100.0, 95.0)
        engine.measure_load_envelope("le-1", "t-1", "c-1", 100.0, 100.0)
        viols = engine.detect_engineering_violations("t-1")
        assert len(viols) == 3


# ===================================================================
# Properties Tests
# ===================================================================


class TestProperties:
    def test_all_counts_zero(self, engine):
        assert engine.quantity_count == 0
        assert engine.tolerance_count == 0
        assert engine.target_count == 0
        assert engine.margin_count == 0
        assert engine.envelope_count == 0
        assert engine.window_count == 0
        assert engine.curve_count == 0
        assert engine.violation_count == 0
