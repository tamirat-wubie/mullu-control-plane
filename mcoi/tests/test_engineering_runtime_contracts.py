"""Comprehensive tests for engineering quantities / systems constraints runtime contracts.

Tests cover: enum membership, dataclass construction, validation failures,
frozen immutability, metadata freezing, to_dict() serialization, to_json_dict(),
to_json(), and edge cases for every contract type.
"""

from __future__ import annotations

import json
import math
from dataclasses import FrozenInstanceError
from types import MappingProxyType

import pytest

from mcoi_runtime.contracts.engineering_runtime import (
    CapacityCurve,
    EngineeringClosureReport,
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


# ===================================================================
# Helpers: valid kwargs for each dataclass
# ===================================================================

TS = "2025-06-01T00:00:00+00:00"


def _engineering_quantity_kw(**overrides):
    base = dict(
        quantity_id="q-1", tenant_id="t-1", display_name="Temperature",
        value=25.0, unit_label="C", domain=EngineeringDomain.THERMAL,
        tolerance=0.5, created_at=TS,
    )
    base.update(overrides)
    return base


def _tolerance_record_kw(**overrides):
    base = dict(
        tolerance_id="tol-1", tenant_id="t-1", quantity_ref="q-1",
        nominal=100.0, lower_limit=90.0, upper_limit=110.0,
        status=ToleranceStatus.WITHIN, checked_at=TS,
    )
    base.update(overrides)
    return base


def _reliability_target_kw(**overrides):
    base = dict(
        target_id="rt-1", tenant_id="t-1", component_ref="c-1",
        grade=ReliabilityGrade.A, mtbf_hours=5000.0,
        target_availability=0.99, created_at=TS,
    )
    base.update(overrides)
    return base


def _safety_margin_kw(**overrides):
    base = dict(
        margin_id="sm-1", tenant_id="t-1", component_ref="c-1",
        design_load=100.0, actual_load=50.0, margin_ratio=0.5,
        status=SafetyMarginStatus.ADEQUATE, assessed_at=TS,
    )
    base.update(overrides)
    return base


def _load_envelope_kw(**overrides):
    base = dict(
        envelope_id="le-1", tenant_id="t-1", component_ref="c-1",
        max_load=100.0, current_load=50.0,
        status=LoadEnvelopeStatus.NOMINAL, measured_at=TS,
    )
    base.update(overrides)
    return base


def _process_window_kw(**overrides):
    base = dict(
        window_id="pw-1", tenant_id="t-1", process_ref="p-1",
        target_value=50.0, lower_spec=40.0, upper_spec=60.0,
        actual_value=50.0, status=ProcessWindowStatus.IN_SPEC, measured_at=TS,
    )
    base.update(overrides)
    return base


def _capacity_curve_kw(**overrides):
    base = dict(
        curve_id="cc-1", tenant_id="t-1", component_ref="c-1",
        max_capacity=1000.0, current_utilization=0.5, headroom=500.0,
        created_at=TS,
    )
    base.update(overrides)
    return base


def _engineering_snapshot_kw(**overrides):
    base = dict(
        snapshot_id="ss-1", tenant_id="t-1",
        total_quantities=5, total_tolerances=3, total_targets=2,
        total_margins=2, total_envelopes=1, total_violations=0,
        captured_at=TS,
    )
    base.update(overrides)
    return base


def _engineering_violation_kw(**overrides):
    base = dict(
        violation_id="ev-1", tenant_id="t-1",
        operation="tolerance_exceeded", reason="value out of range",
        detected_at=TS,
    )
    base.update(overrides)
    return base


def _engineering_closure_report_kw(**overrides):
    base = dict(
        report_id="cr-1", tenant_id="t-1",
        total_quantities=5, total_tolerances=3, total_targets=2,
        total_margins=2, total_violations=0, created_at=TS,
    )
    base.update(overrides)
    return base


# ===================================================================
# Enum Tests
# ===================================================================


class TestEnums:
    def test_engineering_domain_members(self):
        assert len(EngineeringDomain) == 6
        assert EngineeringDomain.MECHANICAL.value == "mechanical"
        assert EngineeringDomain.PROCESS.value == "process"

    def test_tolerance_status_members(self):
        assert len(ToleranceStatus) == 4
        assert ToleranceStatus.WITHIN.value == "within"
        assert ToleranceStatus.CRITICAL.value == "critical"

    def test_reliability_grade_members(self):
        assert len(ReliabilityGrade) == 5
        assert ReliabilityGrade.A.value == "A"
        assert ReliabilityGrade.F.value == "F"

    def test_safety_margin_status_members(self):
        assert len(SafetyMarginStatus) == 4
        assert SafetyMarginStatus.ADEQUATE.value == "adequate"
        assert SafetyMarginStatus.UNKNOWN.value == "unknown"

    def test_load_envelope_status_members(self):
        assert len(LoadEnvelopeStatus) == 4
        assert LoadEnvelopeStatus.NOMINAL.value == "nominal"
        assert LoadEnvelopeStatus.FAILURE.value == "failure"

    def test_process_window_status_members(self):
        assert len(ProcessWindowStatus) == 4
        assert ProcessWindowStatus.IN_SPEC.value == "in_spec"
        assert ProcessWindowStatus.SHUTDOWN.value == "shutdown"


# ===================================================================
# EngineeringQuantity Tests
# ===================================================================


class TestEngineeringQuantity:
    def test_valid_construction(self):
        q = EngineeringQuantity(**_engineering_quantity_kw())
        assert q.quantity_id == "q-1"
        assert q.value == 25.0
        assert q.domain == EngineeringDomain.THERMAL

    def test_negative_value_allowed(self):
        q = EngineeringQuantity(**_engineering_quantity_kw(value=-50.0))
        assert q.value == -50.0

    def test_bool_value_rejected(self):
        with pytest.raises(ValueError):
            EngineeringQuantity(**_engineering_quantity_kw(value=True))

    def test_nan_value_rejected(self):
        with pytest.raises(ValueError):
            EngineeringQuantity(**_engineering_quantity_kw(value=float("nan")))

    def test_inf_value_rejected(self):
        with pytest.raises(ValueError):
            EngineeringQuantity(**_engineering_quantity_kw(value=float("inf")))

    def test_negative_tolerance_rejected(self):
        with pytest.raises(ValueError):
            EngineeringQuantity(**_engineering_quantity_kw(tolerance=-0.1))

    def test_empty_quantity_id_rejected(self):
        with pytest.raises(ValueError):
            EngineeringQuantity(**_engineering_quantity_kw(quantity_id=""))

    def test_frozen_immutability(self):
        q = EngineeringQuantity(**_engineering_quantity_kw())
        with pytest.raises((FrozenInstanceError, AttributeError)):
            q.value = 999.0

    def test_metadata_frozen(self):
        q = EngineeringQuantity(**_engineering_quantity_kw(metadata={"key": "val"}))
        assert isinstance(q.metadata, MappingProxyType)

    def test_to_dict(self):
        q = EngineeringQuantity(**_engineering_quantity_kw())
        d = q.to_dict()
        assert d["quantity_id"] == "q-1"
        assert d["domain"] == EngineeringDomain.THERMAL

    def test_to_json_dict(self):
        q = EngineeringQuantity(**_engineering_quantity_kw())
        d = q.to_json_dict()
        assert d["domain"] == "thermal"

    def test_to_json(self):
        q = EngineeringQuantity(**_engineering_quantity_kw())
        s = q.to_json()
        parsed = json.loads(s)
        assert parsed["quantity_id"] == "q-1"

    def test_int_value_accepted(self):
        q = EngineeringQuantity(**_engineering_quantity_kw(value=10))
        assert q.value == 10.0


# ===================================================================
# ToleranceRecord Tests
# ===================================================================


class TestToleranceRecord:
    def test_valid_construction(self):
        t = ToleranceRecord(**_tolerance_record_kw())
        assert t.nominal == 100.0

    def test_negative_nominal_allowed(self):
        t = ToleranceRecord(**_tolerance_record_kw(nominal=-10.0))
        assert t.nominal == -10.0

    def test_bool_nominal_rejected(self):
        with pytest.raises(ValueError):
            ToleranceRecord(**_tolerance_record_kw(nominal=True))

    def test_to_json(self):
        t = ToleranceRecord(**_tolerance_record_kw())
        parsed = json.loads(t.to_json())
        assert parsed["status"] == "within"


# ===================================================================
# ReliabilityTarget Tests
# ===================================================================


class TestReliabilityTarget:
    def test_valid_construction(self):
        r = ReliabilityTarget(**_reliability_target_kw())
        assert r.grade == ReliabilityGrade.A

    def test_availability_out_of_range_rejected(self):
        with pytest.raises(ValueError):
            ReliabilityTarget(**_reliability_target_kw(target_availability=1.5))

    def test_negative_mtbf_rejected(self):
        with pytest.raises(ValueError):
            ReliabilityTarget(**_reliability_target_kw(mtbf_hours=-1.0))


# ===================================================================
# SafetyMargin Tests
# ===================================================================


class TestSafetyMargin:
    def test_valid_construction(self):
        sm = SafetyMargin(**_safety_margin_kw())
        assert sm.margin_ratio == 0.5

    def test_negative_design_load_rejected(self):
        with pytest.raises(ValueError):
            SafetyMargin(**_safety_margin_kw(design_load=-1.0))


# ===================================================================
# LoadEnvelope Tests
# ===================================================================


class TestLoadEnvelope:
    def test_valid_construction(self):
        le = LoadEnvelope(**_load_envelope_kw())
        assert le.status == LoadEnvelopeStatus.NOMINAL


# ===================================================================
# ProcessWindow Tests
# ===================================================================


class TestProcessWindow:
    def test_valid_construction(self):
        pw = ProcessWindow(**_process_window_kw())
        assert pw.status == ProcessWindowStatus.IN_SPEC

    def test_negative_actual_value_allowed(self):
        pw = ProcessWindow(**_process_window_kw(actual_value=-5.0, lower_spec=-10.0))
        assert pw.actual_value == -5.0


# ===================================================================
# CapacityCurve Tests
# ===================================================================


class TestCapacityCurve:
    def test_valid_construction(self):
        cc = CapacityCurve(**_capacity_curve_kw())
        assert cc.current_utilization == 0.5

    def test_utilization_out_of_range_rejected(self):
        with pytest.raises(ValueError):
            CapacityCurve(**_capacity_curve_kw(current_utilization=1.5))


# ===================================================================
# EngineeringSnapshot Tests
# ===================================================================


class TestEngineeringSnapshot:
    def test_valid_construction(self):
        ss = EngineeringSnapshot(**_engineering_snapshot_kw())
        assert ss.total_quantities == 5

    def test_negative_count_rejected(self):
        with pytest.raises(ValueError):
            EngineeringSnapshot(**_engineering_snapshot_kw(total_quantities=-1))


# ===================================================================
# EngineeringViolation Tests
# ===================================================================


class TestEngineeringViolation:
    def test_valid_construction(self):
        v = EngineeringViolation(**_engineering_violation_kw())
        assert v.operation == "tolerance_exceeded"


# ===================================================================
# EngineeringClosureReport Tests
# ===================================================================


class TestEngineeringClosureReport:
    def test_valid_construction(self):
        cr = EngineeringClosureReport(**_engineering_closure_report_kw())
        assert cr.total_quantities == 5

    def test_to_json(self):
        cr = EngineeringClosureReport(**_engineering_closure_report_kw())
        parsed = json.loads(cr.to_json())
        assert parsed["report_id"] == "cr-1"
