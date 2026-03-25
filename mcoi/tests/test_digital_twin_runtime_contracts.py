"""Comprehensive tests for digital twin runtime contracts.

Tests cover: enum membership, dataclass construction, validation failures,
frozen immutability, metadata freezing, to_dict() serialization, to_json_dict(),
to_json(), and edge cases for every contract type.
"""

from __future__ import annotations

import json
import math
from dataclasses import FrozenInstanceError

import pytest

from mcoi_runtime.contracts.digital_twin_runtime import (
    TwinAssembly,
    TwinAssessment,
    TwinClosureReport,
    TwinLifecycleStatus,
    TwinModel,
    TwinObject,
    TwinObjectKind,
    TwinRiskLevel,
    TwinSnapshot,
    TwinStateDisposition,
    TwinStateRecord,
    TwinStatus,
    TwinSyncRecord,
    TwinSyncStatus,
    TwinTelemetryBinding,
    TwinViolation,
)


# ===================================================================
# Helpers: valid kwargs for each dataclass
# ===================================================================

TS = "2025-06-01T00:00:00+00:00"


def _twin_model_kw(**overrides):
    base = dict(
        model_id="m-1", tenant_id="t-1", display_name="Plant A",
        status=TwinStatus.ACTIVE, object_count=0, created_at=TS,
    )
    base.update(overrides)
    return base


def _twin_object_kw(**overrides):
    base = dict(
        object_id="o-1", tenant_id="t-1", model_ref="m-1",
        kind=TwinObjectKind.MACHINE, display_name="Press 1",
        parent_ref="root", state=TwinStateDisposition.NOMINAL,
        created_at=TS,
    )
    base.update(overrides)
    return base


def _twin_assembly_kw(**overrides):
    base = dict(
        assembly_id="a-1", tenant_id="t-1",
        parent_object_ref="o-1", child_object_ref="o-2",
        depth=1, created_at=TS,
    )
    base.update(overrides)
    return base


def _twin_state_record_kw(**overrides):
    base = dict(
        state_id="s-1", tenant_id="t-1", object_ref="o-1",
        disposition=TwinStateDisposition.NOMINAL,
        source_runtime="factory", updated_at=TS,
    )
    base.update(overrides)
    return base


def _twin_telemetry_binding_kw(**overrides):
    base = dict(
        binding_id="b-1", tenant_id="t-1", object_ref="o-1",
        telemetry_ref="tel-1", source_runtime="obs", bound_at=TS,
    )
    base.update(overrides)
    return base


def _twin_sync_record_kw(**overrides):
    base = dict(
        sync_id="sy-1", tenant_id="t-1", object_ref="o-1",
        status=TwinSyncStatus.SYNCED, last_synced_at=TS,
    )
    base.update(overrides)
    return base


def _twin_assessment_kw(**overrides):
    base = dict(
        assessment_id="as-1", tenant_id="t-1",
        total_objects=10, total_nominal=8, total_degraded=2,
        health_score=0.8, assessed_at=TS,
    )
    base.update(overrides)
    return base


def _twin_violation_kw(**overrides):
    base = dict(
        violation_id="v-1", tenant_id="t-1",
        operation="stale_sync", reason="stale data", detected_at=TS,
    )
    base.update(overrides)
    return base


def _twin_snapshot_kw(**overrides):
    base = dict(
        snapshot_id="snap-1", tenant_id="t-1",
        total_models=1, total_objects=5, total_assemblies=3,
        total_states=2, total_bindings=1, total_violations=0,
        captured_at=TS,
    )
    base.update(overrides)
    return base


def _twin_closure_report_kw(**overrides):
    base = dict(
        report_id="r-1", tenant_id="t-1",
        total_models=1, total_objects=5, total_assemblies=3,
        total_states=2, total_violations=0, created_at=TS,
    )
    base.update(overrides)
    return base


# ===================================================================
# Enum Tests
# ===================================================================


class TestEnums:
    def test_twin_status_members(self):
        assert len(TwinStatus) == 4
        assert TwinStatus.ACTIVE.value == "active"
        assert TwinStatus.DEGRADED.value == "degraded"
        assert TwinStatus.OFFLINE.value == "offline"
        assert TwinStatus.RETIRED.value == "retired"

    def test_twin_object_kind_members(self):
        assert len(TwinObjectKind) == 6
        assert TwinObjectKind.SITE.value == "site"
        assert TwinObjectKind.SENSOR.value == "sensor"

    def test_twin_state_disposition_members(self):
        assert len(TwinStateDisposition) == 5
        assert TwinStateDisposition.NOMINAL.value == "nominal"
        assert TwinStateDisposition.UNKNOWN.value == "unknown"

    def test_twin_lifecycle_status_members(self):
        assert len(TwinLifecycleStatus) == 4
        assert TwinLifecycleStatus.DRAFT.value == "draft"
        assert TwinLifecycleStatus.RETIRED.value == "retired"

    def test_twin_sync_status_members(self):
        assert len(TwinSyncStatus) == 4
        assert TwinSyncStatus.SYNCED.value == "synced"
        assert TwinSyncStatus.DISCONNECTED.value == "disconnected"

    def test_twin_risk_level_members(self):
        assert len(TwinRiskLevel) == 4
        assert TwinRiskLevel.LOW.value == "low"
        assert TwinRiskLevel.CRITICAL.value == "critical"


# ===================================================================
# TwinModel Tests
# ===================================================================


class TestTwinModel:
    def test_valid_construction(self):
        m = TwinModel(**_twin_model_kw())
        assert m.model_id == "m-1"
        assert m.status == TwinStatus.ACTIVE
        assert m.object_count == 0

    def test_empty_model_id_rejected(self):
        with pytest.raises(ValueError):
            TwinModel(**_twin_model_kw(model_id=""))

    def test_empty_tenant_id_rejected(self):
        with pytest.raises(ValueError):
            TwinModel(**_twin_model_kw(tenant_id=""))

    def test_empty_display_name_rejected(self):
        with pytest.raises(ValueError):
            TwinModel(**_twin_model_kw(display_name=""))

    def test_negative_object_count_rejected(self):
        with pytest.raises(ValueError):
            TwinModel(**_twin_model_kw(object_count=-1))

    def test_bad_created_at_rejected(self):
        with pytest.raises(ValueError):
            TwinModel(**_twin_model_kw(created_at="not-a-date"))

    def test_frozen(self):
        m = TwinModel(**_twin_model_kw())
        with pytest.raises((FrozenInstanceError, AttributeError)):
            m.model_id = "x"

    def test_metadata_frozen(self):
        m = TwinModel(**_twin_model_kw(metadata={"k": "v"}))
        with pytest.raises(TypeError):
            m.metadata["k2"] = "v2"

    def test_to_dict(self):
        m = TwinModel(**_twin_model_kw())
        d = m.to_dict()
        assert d["model_id"] == "m-1"
        assert d["status"] == TwinStatus.ACTIVE

    def test_to_json_dict(self):
        m = TwinModel(**_twin_model_kw())
        d = m.to_json_dict()
        assert d["status"] == "active"

    def test_to_json(self):
        m = TwinModel(**_twin_model_kw())
        j = m.to_json()
        parsed = json.loads(j)
        assert parsed["model_id"] == "m-1"


# ===================================================================
# TwinObject Tests
# ===================================================================


class TestTwinObject:
    def test_valid_construction(self):
        o = TwinObject(**_twin_object_kw())
        assert o.object_id == "o-1"
        assert o.parent_ref == "root"
        assert o.state == TwinStateDisposition.NOMINAL

    def test_empty_object_id_rejected(self):
        with pytest.raises(ValueError):
            TwinObject(**_twin_object_kw(object_id=""))

    def test_empty_model_ref_rejected(self):
        with pytest.raises(ValueError):
            TwinObject(**_twin_object_kw(model_ref=""))

    def test_empty_display_name_rejected(self):
        with pytest.raises(ValueError):
            TwinObject(**_twin_object_kw(display_name=""))

    def test_frozen(self):
        o = TwinObject(**_twin_object_kw())
        with pytest.raises((FrozenInstanceError, AttributeError)):
            o.state = TwinStateDisposition.DEGRADED

    def test_to_json(self):
        o = TwinObject(**_twin_object_kw())
        parsed = json.loads(o.to_json())
        assert parsed["kind"] == "machine"


# ===================================================================
# TwinAssembly Tests
# ===================================================================


class TestTwinAssembly:
    def test_valid_construction(self):
        a = TwinAssembly(**_twin_assembly_kw())
        assert a.depth == 1

    def test_empty_parent_ref_rejected(self):
        with pytest.raises(ValueError):
            TwinAssembly(**_twin_assembly_kw(parent_object_ref=""))

    def test_empty_child_ref_rejected(self):
        with pytest.raises(ValueError):
            TwinAssembly(**_twin_assembly_kw(child_object_ref=""))

    def test_negative_depth_rejected(self):
        with pytest.raises(ValueError):
            TwinAssembly(**_twin_assembly_kw(depth=-1))

    def test_frozen(self):
        a = TwinAssembly(**_twin_assembly_kw())
        with pytest.raises((FrozenInstanceError, AttributeError)):
            a.depth = 5


# ===================================================================
# TwinStateRecord Tests
# ===================================================================


class TestTwinStateRecord:
    def test_valid_construction(self):
        r = TwinStateRecord(**_twin_state_record_kw())
        assert r.disposition == TwinStateDisposition.NOMINAL

    def test_empty_state_id_rejected(self):
        with pytest.raises(ValueError):
            TwinStateRecord(**_twin_state_record_kw(state_id=""))

    def test_empty_source_runtime_rejected(self):
        with pytest.raises(ValueError):
            TwinStateRecord(**_twin_state_record_kw(source_runtime=""))

    def test_frozen(self):
        r = TwinStateRecord(**_twin_state_record_kw())
        with pytest.raises((FrozenInstanceError, AttributeError)):
            r.state_id = "x"


# ===================================================================
# TwinTelemetryBinding Tests
# ===================================================================


class TestTwinTelemetryBinding:
    def test_valid_construction(self):
        b = TwinTelemetryBinding(**_twin_telemetry_binding_kw())
        assert b.telemetry_ref == "tel-1"

    def test_empty_binding_id_rejected(self):
        with pytest.raises(ValueError):
            TwinTelemetryBinding(**_twin_telemetry_binding_kw(binding_id=""))

    def test_empty_telemetry_ref_rejected(self):
        with pytest.raises(ValueError):
            TwinTelemetryBinding(**_twin_telemetry_binding_kw(telemetry_ref=""))

    def test_frozen(self):
        b = TwinTelemetryBinding(**_twin_telemetry_binding_kw())
        with pytest.raises((FrozenInstanceError, AttributeError)):
            b.binding_id = "x"


# ===================================================================
# TwinSyncRecord Tests
# ===================================================================


class TestTwinSyncRecord:
    def test_valid_construction(self):
        s = TwinSyncRecord(**_twin_sync_record_kw())
        assert s.status == TwinSyncStatus.SYNCED

    def test_empty_sync_id_rejected(self):
        with pytest.raises(ValueError):
            TwinSyncRecord(**_twin_sync_record_kw(sync_id=""))

    def test_frozen(self):
        s = TwinSyncRecord(**_twin_sync_record_kw())
        with pytest.raises((FrozenInstanceError, AttributeError)):
            s.sync_id = "x"


# ===================================================================
# TwinAssessment Tests
# ===================================================================


class TestTwinAssessment:
    def test_valid_construction(self):
        a = TwinAssessment(**_twin_assessment_kw())
        assert a.health_score == 0.8

    def test_health_score_above_1_rejected(self):
        with pytest.raises(ValueError):
            TwinAssessment(**_twin_assessment_kw(health_score=1.5))

    def test_health_score_below_0_rejected(self):
        with pytest.raises(ValueError):
            TwinAssessment(**_twin_assessment_kw(health_score=-0.1))

    def test_health_score_nan_rejected(self):
        with pytest.raises(ValueError):
            TwinAssessment(**_twin_assessment_kw(health_score=float("nan")))

    def test_negative_total_objects_rejected(self):
        with pytest.raises(ValueError):
            TwinAssessment(**_twin_assessment_kw(total_objects=-1))

    def test_frozen(self):
        a = TwinAssessment(**_twin_assessment_kw())
        with pytest.raises((FrozenInstanceError, AttributeError)):
            a.health_score = 0.5


# ===================================================================
# TwinViolation Tests
# ===================================================================


class TestTwinViolation:
    def test_valid_construction(self):
        v = TwinViolation(**_twin_violation_kw())
        assert v.operation == "stale_sync"

    def test_empty_operation_rejected(self):
        with pytest.raises(ValueError):
            TwinViolation(**_twin_violation_kw(operation=""))

    def test_empty_reason_rejected(self):
        with pytest.raises(ValueError):
            TwinViolation(**_twin_violation_kw(reason=""))

    def test_frozen(self):
        v = TwinViolation(**_twin_violation_kw())
        with pytest.raises((FrozenInstanceError, AttributeError)):
            v.violation_id = "x"


# ===================================================================
# TwinSnapshot Tests
# ===================================================================


class TestTwinSnapshot:
    def test_valid_construction(self):
        s = TwinSnapshot(**_twin_snapshot_kw())
        assert s.total_models == 1
        assert s.total_objects == 5

    def test_negative_total_rejected(self):
        with pytest.raises(ValueError):
            TwinSnapshot(**_twin_snapshot_kw(total_models=-1))

    def test_frozen(self):
        s = TwinSnapshot(**_twin_snapshot_kw())
        with pytest.raises((FrozenInstanceError, AttributeError)):
            s.snapshot_id = "x"

    def test_to_json(self):
        s = TwinSnapshot(**_twin_snapshot_kw())
        parsed = json.loads(s.to_json())
        assert parsed["total_objects"] == 5


# ===================================================================
# TwinClosureReport Tests
# ===================================================================


class TestTwinClosureReport:
    def test_valid_construction(self):
        r = TwinClosureReport(**_twin_closure_report_kw())
        assert r.total_models == 1

    def test_negative_total_rejected(self):
        with pytest.raises(ValueError):
            TwinClosureReport(**_twin_closure_report_kw(total_objects=-1))

    def test_frozen(self):
        r = TwinClosureReport(**_twin_closure_report_kw())
        with pytest.raises((FrozenInstanceError, AttributeError)):
            r.report_id = "x"

    def test_to_json(self):
        r = TwinClosureReport(**_twin_closure_report_kw())
        parsed = json.loads(r.to_json())
        assert parsed["total_violations"] == 0


# ===================================================================
# Cross-cutting: __init__.py re-exports
# ===================================================================


class TestInitReexports:
    def test_all_types_importable(self):
        from mcoi_runtime.contracts import (
            TwinAssembly,
            TwinAssessment,
            TwinClosureReport,
            TwinLifecycleStatus,
            TwinModel,
            TwinObject,
            TwinObjectKind,
            TwinRiskLevel,
            TwinSnapshot,
            TwinStateDisposition,
            TwinStateRecord,
            TwinStatus,
            TwinSyncRecord,
            TwinSyncStatus,
            TwinTelemetryBinding,
            TwinViolation,
        )
        assert TwinModel is not None
        assert len(TwinStatus) == 4
