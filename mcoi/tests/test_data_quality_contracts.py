"""Comprehensive tests for data quality / schema evolution / lineage contracts.

Covers all 7 enums and 11 frozen dataclasses in
mcoi_runtime.contracts.data_quality with ~300 tests.
"""

from __future__ import annotations

import math
from dataclasses import FrozenInstanceError
from types import MappingProxyType

import pytest

from mcoi_runtime.contracts.data_quality import (
    DataQualityClosureReport,
    DataQualityRecord,
    DataQualitySnapshot,
    DataQualityStatus,
    DataQualityViolation,
    DriftDetection,
    DriftSeverity,
    DuplicateDisposition,
    DuplicateRecord,
    LineageDisposition,
    LineageRecord,
    ReconciliationRecord,
    SchemaEvolutionStatus,
    SchemaVersion,
    SourceQualityPolicy,
    TrustScore,
)


# ===================================================================
# Helpers
# ===================================================================

NOW = "2025-06-01T12:00:00+00:00"
DATE_ONLY = "2025-06-01"


def _dqr(**kw):
    defaults = dict(
        record_id="r1", tenant_id="t1", source_ref="src1",
        status=DataQualityStatus.CLEAN, trust_score=TrustScore.HIGH,
        error_count=0, checked_at=NOW,
    )
    defaults.update(kw)
    return DataQualityRecord(**defaults)


def _sv(**kw):
    defaults = dict(
        version_id="v1", tenant_id="t1", schema_ref="sch1",
        status=SchemaEvolutionStatus.CURRENT, version_number=1,
        field_count=5, created_at=NOW,
    )
    defaults.update(kw)
    return SchemaVersion(**defaults)


def _dd(**kw):
    defaults = dict(
        detection_id="d1", tenant_id="t1", schema_ref="sch1",
        severity=DriftSeverity.MINOR, field_name="col_a",
        expected_type="str", actual_type="int", detected_at=NOW,
    )
    defaults.update(kw)
    return DriftDetection(**defaults)


def _lr(**kw):
    defaults = dict(
        lineage_id="l1", tenant_id="t1", source_ref="src1",
        target_ref="tgt1", disposition=LineageDisposition.VERIFIED,
        hop_count=1, created_at=NOW,
    )
    defaults.update(kw)
    return LineageRecord(**defaults)


def _dup(**kw):
    defaults = dict(
        duplicate_id="dup1", tenant_id="t1", record_ref_a="ra",
        record_ref_b="rb", disposition=DuplicateDisposition.SUSPECTED,
        confidence=0.8, detected_at=NOW,
    )
    defaults.update(kw)
    return DuplicateRecord(**defaults)


def _rec(**kw):
    defaults = dict(
        reconciliation_id="rec1", tenant_id="t1", source_ref="src1",
        canonical_ref="can1", resolved=True, created_at=NOW,
    )
    defaults.update(kw)
    return ReconciliationRecord(**defaults)


def _sqp(**kw):
    defaults = dict(
        policy_id="pol1", tenant_id="t1", source_ref="src1",
        min_trust=TrustScore.MEDIUM, max_errors=10, created_at=NOW,
    )
    defaults.update(kw)
    return SourceQualityPolicy(**defaults)


def _snap(**kw):
    defaults = dict(
        snapshot_id="snap1", tenant_id="t1",
        total_records=0, total_schemas=0, total_drifts=0,
        total_duplicates=0, total_lineages=0, total_violations=0,
        captured_at=NOW,
    )
    defaults.update(kw)
    return DataQualitySnapshot(**defaults)


def _viol(**kw):
    defaults = dict(
        violation_id="viol1", tenant_id="t1",
        operation="dirty_no_quarantine", reason="dirty record",
        detected_at=NOW,
    )
    defaults.update(kw)
    return DataQualityViolation(**defaults)


def _closure(**kw):
    defaults = dict(
        report_id="rpt1", tenant_id="t1",
        total_records=0, total_schemas=0, total_drifts=0,
        total_duplicates=0, total_violations=0, created_at=NOW,
    )
    defaults.update(kw)
    return DataQualityClosureReport(**defaults)


# ===================================================================
# 1. Enum tests
# ===================================================================


class TestDataQualityStatus:
    def test_members(self):
        assert set(DataQualityStatus) == {
            DataQualityStatus.CLEAN, DataQualityStatus.DEGRADED,
            DataQualityStatus.DIRTY, DataQualityStatus.QUARANTINED,
        }

    @pytest.mark.parametrize("member,value", [
        (DataQualityStatus.CLEAN, "clean"),
        (DataQualityStatus.DEGRADED, "degraded"),
        (DataQualityStatus.DIRTY, "dirty"),
        (DataQualityStatus.QUARANTINED, "quarantined"),
    ])
    def test_value(self, member, value):
        assert member.value == value

    def test_from_value(self):
        assert DataQualityStatus("clean") is DataQualityStatus.CLEAN

    def test_invalid_value(self):
        with pytest.raises(ValueError):
            DataQualityStatus("invalid")

    def test_count(self):
        assert len(DataQualityStatus) == 4


class TestSchemaEvolutionStatus:
    def test_members(self):
        assert set(SchemaEvolutionStatus) == {
            SchemaEvolutionStatus.CURRENT, SchemaEvolutionStatus.MIGRATING,
            SchemaEvolutionStatus.DEPRECATED, SchemaEvolutionStatus.RETIRED,
        }

    @pytest.mark.parametrize("member,value", [
        (SchemaEvolutionStatus.CURRENT, "current"),
        (SchemaEvolutionStatus.MIGRATING, "migrating"),
        (SchemaEvolutionStatus.DEPRECATED, "deprecated"),
        (SchemaEvolutionStatus.RETIRED, "retired"),
    ])
    def test_value(self, member, value):
        assert member.value == value

    def test_from_value(self):
        assert SchemaEvolutionStatus("retired") is SchemaEvolutionStatus.RETIRED

    def test_invalid_value(self):
        with pytest.raises(ValueError):
            SchemaEvolutionStatus("unknown")

    def test_count(self):
        assert len(SchemaEvolutionStatus) == 4


class TestDriftSeverity:
    def test_members(self):
        assert set(DriftSeverity) == {
            DriftSeverity.NONE, DriftSeverity.MINOR,
            DriftSeverity.MAJOR, DriftSeverity.BREAKING,
        }

    @pytest.mark.parametrize("member,value", [
        (DriftSeverity.NONE, "none"),
        (DriftSeverity.MINOR, "minor"),
        (DriftSeverity.MAJOR, "major"),
        (DriftSeverity.BREAKING, "breaking"),
    ])
    def test_value(self, member, value):
        assert member.value == value

    def test_count(self):
        assert len(DriftSeverity) == 4


class TestLineageDisposition:
    def test_members(self):
        assert set(LineageDisposition) == {
            LineageDisposition.VERIFIED, LineageDisposition.UNVERIFIED,
            LineageDisposition.BROKEN, LineageDisposition.UNKNOWN,
        }

    @pytest.mark.parametrize("member,value", [
        (LineageDisposition.VERIFIED, "verified"),
        (LineageDisposition.UNVERIFIED, "unverified"),
        (LineageDisposition.BROKEN, "broken"),
        (LineageDisposition.UNKNOWN, "unknown"),
    ])
    def test_value(self, member, value):
        assert member.value == value

    def test_count(self):
        assert len(LineageDisposition) == 4


class TestDuplicateDisposition:
    def test_members(self):
        assert set(DuplicateDisposition) == {
            DuplicateDisposition.UNIQUE, DuplicateDisposition.SUSPECTED,
            DuplicateDisposition.CONFIRMED, DuplicateDisposition.MERGED,
        }

    @pytest.mark.parametrize("member,value", [
        (DuplicateDisposition.UNIQUE, "unique"),
        (DuplicateDisposition.SUSPECTED, "suspected"),
        (DuplicateDisposition.CONFIRMED, "confirmed"),
        (DuplicateDisposition.MERGED, "merged"),
    ])
    def test_value(self, member, value):
        assert member.value == value

    def test_count(self):
        assert len(DuplicateDisposition) == 4


class TestTrustScore:
    def test_members(self):
        assert set(TrustScore) == {
            TrustScore.HIGH, TrustScore.MEDIUM,
            TrustScore.LOW, TrustScore.UNTRUSTED,
        }

    @pytest.mark.parametrize("member,value", [
        (TrustScore.HIGH, "high"),
        (TrustScore.MEDIUM, "medium"),
        (TrustScore.LOW, "low"),
        (TrustScore.UNTRUSTED, "untrusted"),
    ])
    def test_value(self, member, value):
        assert member.value == value

    def test_count(self):
        assert len(TrustScore) == 4


# ===================================================================
# 2. DataQualityRecord tests
# ===================================================================


class TestDataQualityRecordConstruction:
    def test_happy_path(self):
        r = _dqr()
        assert r.record_id == "r1"
        assert r.tenant_id == "t1"
        assert r.source_ref == "src1"
        assert r.status is DataQualityStatus.CLEAN
        assert r.trust_score is TrustScore.HIGH
        assert r.error_count == 0

    def test_all_status_values(self):
        for s in DataQualityStatus:
            r = _dqr(status=s)
            assert r.status is s

    def test_all_trust_scores(self):
        for ts in TrustScore:
            r = _dqr(trust_score=ts)
            assert r.trust_score is ts

    def test_error_count_zero(self):
        assert _dqr(error_count=0).error_count == 0

    def test_error_count_positive(self):
        assert _dqr(error_count=42).error_count == 42

    def test_date_only_accepted(self):
        r = _dqr(checked_at=DATE_ONLY)
        assert r.checked_at == DATE_ONLY

    def test_metadata_empty(self):
        r = _dqr()
        assert isinstance(r.metadata, MappingProxyType)
        assert len(r.metadata) == 0

    def test_metadata_frozen(self):
        r = _dqr(metadata={"k": "v"})
        assert isinstance(r.metadata, MappingProxyType)
        assert r.metadata["k"] == "v"

    def test_to_dict_metadata_plain_dict(self):
        r = _dqr(metadata={"a": 1})
        d = r.to_dict()
        assert isinstance(d["metadata"], dict)

    def test_to_dict_preserves_enum(self):
        r = _dqr()
        d = r.to_dict()
        assert d["status"] is DataQualityStatus.CLEAN
        assert d["trust_score"] is TrustScore.HIGH

    def test_to_json_dict_converts_enum(self):
        r = _dqr()
        d = r.to_json_dict()
        assert d["status"] == "clean"
        assert d["trust_score"] == "high"


class TestDataQualityRecordValidation:
    @pytest.mark.parametrize("field", ["record_id", "tenant_id", "source_ref"])
    def test_empty_text_rejected(self, field):
        with pytest.raises(ValueError):
            _dqr(**{field: ""})

    @pytest.mark.parametrize("field", ["record_id", "tenant_id", "source_ref"])
    def test_whitespace_only_rejected(self, field):
        with pytest.raises(ValueError):
            _dqr(**{field: "   "})

    def test_status_non_enum_rejected(self):
        with pytest.raises(ValueError):
            _dqr(status="clean")

    def test_trust_score_non_enum_rejected(self):
        with pytest.raises(ValueError):
            _dqr(trust_score="high")

    def test_error_count_negative_rejected(self):
        with pytest.raises(ValueError):
            _dqr(error_count=-1)

    def test_error_count_bool_rejected(self):
        with pytest.raises(ValueError):
            _dqr(error_count=True)

    def test_error_count_float_rejected(self):
        with pytest.raises(ValueError):
            _dqr(error_count=1.5)

    def test_checked_at_empty_rejected(self):
        with pytest.raises(ValueError):
            _dqr(checked_at="")

    def test_checked_at_garbage_rejected(self):
        with pytest.raises(ValueError):
            _dqr(checked_at="not-a-date")


class TestDataQualityRecordFrozen:
    @pytest.mark.parametrize("field", [
        "record_id", "tenant_id", "source_ref", "error_count",
    ])
    def test_frozen_field(self, field):
        r = _dqr()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            setattr(r, field, "x")

    def test_frozen_status(self):
        r = _dqr()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            setattr(r, "status", DataQualityStatus.DIRTY)


# ===================================================================
# 3. SchemaVersion tests
# ===================================================================


class TestSchemaVersionConstruction:
    def test_happy_path(self):
        s = _sv()
        assert s.version_id == "v1"
        assert s.tenant_id == "t1"
        assert s.schema_ref == "sch1"
        assert s.status is SchemaEvolutionStatus.CURRENT
        assert s.version_number == 1
        assert s.field_count == 5

    def test_all_statuses(self):
        for st in SchemaEvolutionStatus:
            s = _sv(status=st)
            assert s.status is st

    def test_version_number_zero(self):
        s = _sv(version_number=0)
        assert s.version_number == 0

    def test_field_count_zero(self):
        s = _sv(field_count=0)
        assert s.field_count == 0

    def test_date_only_accepted(self):
        s = _sv(created_at=DATE_ONLY)
        assert s.created_at == DATE_ONLY

    def test_metadata_frozen(self):
        s = _sv(metadata={"x": 1})
        assert isinstance(s.metadata, MappingProxyType)

    def test_to_dict_preserves_enum(self):
        s = _sv()
        d = s.to_dict()
        assert d["status"] is SchemaEvolutionStatus.CURRENT

    def test_to_json_dict_converts_enum(self):
        d = _sv().to_json_dict()
        assert d["status"] == "current"


class TestSchemaVersionValidation:
    @pytest.mark.parametrize("field", ["version_id", "tenant_id", "schema_ref"])
    def test_empty_text_rejected(self, field):
        with pytest.raises(ValueError):
            _sv(**{field: ""})

    def test_status_non_enum_rejected(self):
        with pytest.raises(ValueError):
            _sv(status="current")

    def test_version_number_negative_rejected(self):
        with pytest.raises(ValueError):
            _sv(version_number=-1)

    def test_version_number_bool_rejected(self):
        with pytest.raises(ValueError):
            _sv(version_number=True)

    def test_version_number_float_rejected(self):
        with pytest.raises(ValueError):
            _sv(version_number=2.5)

    def test_field_count_negative_rejected(self):
        with pytest.raises(ValueError):
            _sv(field_count=-1)

    def test_field_count_bool_rejected(self):
        with pytest.raises(ValueError):
            _sv(field_count=False)

    def test_created_at_empty_rejected(self):
        with pytest.raises(ValueError):
            _sv(created_at="")

    def test_created_at_garbage_rejected(self):
        with pytest.raises(ValueError):
            _sv(created_at="garbage")


class TestSchemaVersionFrozen:
    @pytest.mark.parametrize("field", [
        "version_id", "tenant_id", "schema_ref", "version_number", "field_count",
    ])
    def test_frozen_field(self, field):
        s = _sv()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            setattr(s, field, "x")


# ===================================================================
# 4. DriftDetection tests
# ===================================================================


class TestDriftDetectionConstruction:
    def test_happy_path(self):
        d = _dd()
        assert d.detection_id == "d1"
        assert d.severity is DriftSeverity.MINOR
        assert d.field_name == "col_a"
        assert d.expected_type == "str"
        assert d.actual_type == "int"

    def test_all_severities(self):
        for sev in DriftSeverity:
            d = _dd(severity=sev)
            assert d.severity is sev

    def test_date_only_accepted(self):
        d = _dd(detected_at=DATE_ONLY)
        assert d.detected_at == DATE_ONLY

    def test_metadata_frozen(self):
        d = _dd(metadata={"key": "val"})
        assert isinstance(d.metadata, MappingProxyType)

    def test_to_dict_preserves_enum(self):
        d = _dd()
        dd = d.to_dict()
        assert dd["severity"] is DriftSeverity.MINOR

    def test_to_json_dict_converts_enum(self):
        d = _dd().to_json_dict()
        assert d["severity"] == "minor"


class TestDriftDetectionValidation:
    @pytest.mark.parametrize("field", [
        "detection_id", "tenant_id", "schema_ref",
        "field_name", "expected_type", "actual_type",
    ])
    def test_empty_text_rejected(self, field):
        with pytest.raises(ValueError):
            _dd(**{field: ""})

    def test_severity_non_enum_rejected(self):
        with pytest.raises(ValueError):
            _dd(severity="minor")

    def test_detected_at_empty_rejected(self):
        with pytest.raises(ValueError):
            _dd(detected_at="")


class TestDriftDetectionFrozen:
    @pytest.mark.parametrize("field", [
        "detection_id", "tenant_id", "schema_ref", "field_name",
    ])
    def test_frozen_field(self, field):
        d = _dd()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            setattr(d, field, "x")


# ===================================================================
# 5. LineageRecord tests
# ===================================================================


class TestLineageRecordConstruction:
    def test_happy_path(self):
        lr = _lr()
        assert lr.lineage_id == "l1"
        assert lr.source_ref == "src1"
        assert lr.target_ref == "tgt1"
        assert lr.disposition is LineageDisposition.VERIFIED
        assert lr.hop_count == 1

    def test_all_dispositions(self):
        for disp in LineageDisposition:
            lr = _lr(disposition=disp)
            assert lr.disposition is disp

    def test_hop_count_zero(self):
        lr = _lr(hop_count=0)
        assert lr.hop_count == 0

    def test_date_only_accepted(self):
        lr = _lr(created_at=DATE_ONLY)
        assert lr.created_at == DATE_ONLY

    def test_metadata_frozen(self):
        lr = _lr(metadata={"foo": "bar"})
        assert isinstance(lr.metadata, MappingProxyType)

    def test_to_dict_preserves_enum(self):
        d = _lr().to_dict()
        assert d["disposition"] is LineageDisposition.VERIFIED

    def test_to_json_dict_converts_enum(self):
        d = _lr().to_json_dict()
        assert d["disposition"] == "verified"


class TestLineageRecordValidation:
    @pytest.mark.parametrize("field", [
        "lineage_id", "tenant_id", "source_ref", "target_ref",
    ])
    def test_empty_text_rejected(self, field):
        with pytest.raises(ValueError):
            _lr(**{field: ""})

    def test_disposition_non_enum_rejected(self):
        with pytest.raises(ValueError):
            _lr(disposition="verified")

    def test_hop_count_negative_rejected(self):
        with pytest.raises(ValueError):
            _lr(hop_count=-1)

    def test_hop_count_bool_rejected(self):
        with pytest.raises(ValueError):
            _lr(hop_count=True)

    def test_hop_count_float_rejected(self):
        with pytest.raises(ValueError):
            _lr(hop_count=1.0)

    def test_created_at_empty_rejected(self):
        with pytest.raises(ValueError):
            _lr(created_at="")


class TestLineageRecordFrozen:
    @pytest.mark.parametrize("field", [
        "lineage_id", "tenant_id", "source_ref", "target_ref",
    ])
    def test_frozen_field(self, field):
        lr = _lr()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            setattr(lr, field, "x")


# ===================================================================
# 6. DuplicateRecord tests
# ===================================================================


class TestDuplicateRecordConstruction:
    def test_happy_path(self):
        d = _dup()
        assert d.duplicate_id == "dup1"
        assert d.record_ref_a == "ra"
        assert d.record_ref_b == "rb"
        assert d.disposition is DuplicateDisposition.SUSPECTED
        assert d.confidence == 0.8

    def test_all_dispositions(self):
        for disp in DuplicateDisposition:
            d = _dup(disposition=disp)
            assert d.disposition is disp

    def test_confidence_zero(self):
        d = _dup(confidence=0.0)
        assert d.confidence == 0.0

    def test_confidence_one(self):
        d = _dup(confidence=1.0)
        assert d.confidence == 1.0

    def test_confidence_mid(self):
        d = _dup(confidence=0.5)
        assert d.confidence == 0.5

    def test_date_only_accepted(self):
        d = _dup(detected_at=DATE_ONLY)
        assert d.detected_at == DATE_ONLY

    def test_metadata_frozen(self):
        d = _dup(metadata={"m": 1})
        assert isinstance(d.metadata, MappingProxyType)

    def test_to_dict_preserves_enum(self):
        d = _dup().to_dict()
        assert d["disposition"] is DuplicateDisposition.SUSPECTED

    def test_to_json_dict_converts_enum(self):
        d = _dup().to_json_dict()
        assert d["disposition"] == "suspected"


class TestDuplicateRecordValidation:
    @pytest.mark.parametrize("field", [
        "duplicate_id", "tenant_id", "record_ref_a", "record_ref_b",
    ])
    def test_empty_text_rejected(self, field):
        with pytest.raises(ValueError):
            _dup(**{field: ""})

    def test_disposition_non_enum_rejected(self):
        with pytest.raises(ValueError):
            _dup(disposition="suspected")

    def test_confidence_negative_rejected(self):
        with pytest.raises(ValueError):
            _dup(confidence=-0.1)

    def test_confidence_above_one_rejected(self):
        with pytest.raises(ValueError):
            _dup(confidence=1.1)

    def test_confidence_bool_rejected(self):
        with pytest.raises(ValueError):
            _dup(confidence=True)

    def test_confidence_nan_rejected(self):
        with pytest.raises(ValueError):
            _dup(confidence=float("nan"))

    def test_confidence_inf_rejected(self):
        with pytest.raises(ValueError):
            _dup(confidence=float("inf"))

    def test_detected_at_empty_rejected(self):
        with pytest.raises(ValueError):
            _dup(detected_at="")


class TestDuplicateRecordFrozen:
    @pytest.mark.parametrize("field", [
        "duplicate_id", "tenant_id", "record_ref_a", "record_ref_b",
    ])
    def test_frozen_field(self, field):
        d = _dup()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            setattr(d, field, "x")


# ===================================================================
# 7. ReconciliationRecord tests
# ===================================================================


class TestReconciliationRecordConstruction:
    def test_happy_path_resolved(self):
        r = _rec(resolved=True)
        assert r.resolved is True

    def test_happy_path_unresolved(self):
        r = _rec(resolved=False)
        assert r.resolved is False

    def test_fields(self):
        r = _rec()
        assert r.reconciliation_id == "rec1"
        assert r.tenant_id == "t1"
        assert r.source_ref == "src1"
        assert r.canonical_ref == "can1"

    def test_date_only_accepted(self):
        r = _rec(created_at=DATE_ONLY)
        assert r.created_at == DATE_ONLY

    def test_metadata_frozen(self):
        r = _rec(metadata={"k": "v"})
        assert isinstance(r.metadata, MappingProxyType)

    def test_to_dict_metadata_plain_dict(self):
        r = _rec(metadata={"a": 1})
        d = r.to_dict()
        assert isinstance(d["metadata"], dict)


class TestReconciliationRecordValidation:
    @pytest.mark.parametrize("field", [
        "reconciliation_id", "tenant_id", "source_ref", "canonical_ref",
    ])
    def test_empty_text_rejected(self, field):
        with pytest.raises(ValueError):
            _rec(**{field: ""})

    def test_resolved_non_bool_int_rejected(self):
        with pytest.raises(ValueError):
            _rec(resolved=1)

    def test_resolved_non_bool_str_rejected(self):
        with pytest.raises(ValueError):
            _rec(resolved="yes")

    def test_resolved_non_bool_none_rejected(self):
        with pytest.raises(ValueError):
            _rec(resolved=None)

    def test_created_at_empty_rejected(self):
        with pytest.raises(ValueError):
            _rec(created_at="")


class TestReconciliationRecordFrozen:
    @pytest.mark.parametrize("field", [
        "reconciliation_id", "tenant_id", "source_ref", "canonical_ref",
    ])
    def test_frozen_field(self, field):
        r = _rec()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            setattr(r, field, "x")

    def test_frozen_resolved(self):
        r = _rec()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            setattr(r, "resolved", False)


# ===================================================================
# 8. SourceQualityPolicy tests
# ===================================================================


class TestSourceQualityPolicyConstruction:
    def test_happy_path(self):
        p = _sqp()
        assert p.policy_id == "pol1"
        assert p.tenant_id == "t1"
        assert p.source_ref == "src1"
        assert p.min_trust is TrustScore.MEDIUM
        assert p.max_errors == 10

    def test_all_trust_scores(self):
        for ts in TrustScore:
            p = _sqp(min_trust=ts)
            assert p.min_trust is ts

    def test_max_errors_zero(self):
        p = _sqp(max_errors=0)
        assert p.max_errors == 0

    def test_date_only_accepted(self):
        p = _sqp(created_at=DATE_ONLY)
        assert p.created_at == DATE_ONLY

    def test_metadata_frozen(self):
        p = _sqp(metadata={"x": 1})
        assert isinstance(p.metadata, MappingProxyType)

    def test_to_dict_preserves_enum(self):
        d = _sqp().to_dict()
        assert d["min_trust"] is TrustScore.MEDIUM

    def test_to_json_dict_converts_enum(self):
        d = _sqp().to_json_dict()
        assert d["min_trust"] == "medium"


class TestSourceQualityPolicyValidation:
    @pytest.mark.parametrize("field", ["policy_id", "tenant_id", "source_ref"])
    def test_empty_text_rejected(self, field):
        with pytest.raises(ValueError):
            _sqp(**{field: ""})

    def test_min_trust_non_enum_rejected(self):
        with pytest.raises(ValueError):
            _sqp(min_trust="medium")

    def test_max_errors_negative_rejected(self):
        with pytest.raises(ValueError):
            _sqp(max_errors=-1)

    def test_max_errors_bool_rejected(self):
        with pytest.raises(ValueError):
            _sqp(max_errors=True)

    def test_max_errors_float_rejected(self):
        with pytest.raises(ValueError):
            _sqp(max_errors=5.0)

    def test_created_at_empty_rejected(self):
        with pytest.raises(ValueError):
            _sqp(created_at="")


class TestSourceQualityPolicyFrozen:
    @pytest.mark.parametrize("field", ["policy_id", "tenant_id", "source_ref"])
    def test_frozen_field(self, field):
        p = _sqp()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            setattr(p, field, "x")


# ===================================================================
# 9. DataQualitySnapshot tests
# ===================================================================


class TestSnapshotConstruction:
    def test_happy_path(self):
        s = _snap(total_records=5, total_schemas=3, total_drifts=1,
                  total_duplicates=2, total_lineages=4, total_violations=0)
        assert s.total_records == 5
        assert s.total_schemas == 3
        assert s.total_drifts == 1
        assert s.total_duplicates == 2
        assert s.total_lineages == 4
        assert s.total_violations == 0

    def test_all_zeros(self):
        s = _snap()
        assert s.total_records == 0
        assert s.total_violations == 0

    def test_date_only_accepted(self):
        s = _snap(captured_at=DATE_ONLY)
        assert s.captured_at == DATE_ONLY

    def test_metadata_frozen(self):
        s = _snap(metadata={"k": 1})
        assert isinstance(s.metadata, MappingProxyType)


class TestSnapshotValidation:
    @pytest.mark.parametrize("field", ["snapshot_id", "tenant_id"])
    def test_empty_text_rejected(self, field):
        with pytest.raises(ValueError):
            _snap(**{field: ""})

    @pytest.mark.parametrize("field", [
        "total_records", "total_schemas", "total_drifts",
        "total_duplicates", "total_lineages", "total_violations",
    ])
    def test_negative_int_rejected(self, field):
        with pytest.raises(ValueError):
            _snap(**{field: -1})

    @pytest.mark.parametrize("field", [
        "total_records", "total_schemas", "total_drifts",
        "total_duplicates", "total_lineages", "total_violations",
    ])
    def test_bool_rejected(self, field):
        with pytest.raises(ValueError):
            _snap(**{field: True})

    @pytest.mark.parametrize("field", [
        "total_records", "total_schemas", "total_drifts",
        "total_duplicates", "total_lineages", "total_violations",
    ])
    def test_float_rejected(self, field):
        with pytest.raises(ValueError):
            _snap(**{field: 1.0})

    def test_captured_at_empty_rejected(self):
        with pytest.raises(ValueError):
            _snap(captured_at="")


class TestSnapshotFrozen:
    @pytest.mark.parametrize("field", [
        "snapshot_id", "tenant_id", "total_records", "total_schemas",
    ])
    def test_frozen_field(self, field):
        s = _snap()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            setattr(s, field, "x")


# ===================================================================
# 10. DataQualityViolation tests
# ===================================================================


class TestViolationConstruction:
    def test_happy_path(self):
        v = _viol()
        assert v.violation_id == "viol1"
        assert v.tenant_id == "t1"
        assert v.operation == "dirty_no_quarantine"
        assert v.reason == "dirty record"

    def test_date_only_accepted(self):
        v = _viol(detected_at=DATE_ONLY)
        assert v.detected_at == DATE_ONLY

    def test_metadata_frozen(self):
        v = _viol(metadata={"k": "v"})
        assert isinstance(v.metadata, MappingProxyType)


class TestViolationValidation:
    @pytest.mark.parametrize("field", [
        "violation_id", "tenant_id", "operation", "reason",
    ])
    def test_empty_text_rejected(self, field):
        with pytest.raises(ValueError):
            _viol(**{field: ""})

    def test_detected_at_empty_rejected(self):
        with pytest.raises(ValueError):
            _viol(detected_at="")


class TestViolationFrozen:
    @pytest.mark.parametrize("field", [
        "violation_id", "tenant_id", "operation", "reason",
    ])
    def test_frozen_field(self, field):
        v = _viol()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            setattr(v, field, "x")


# ===================================================================
# 11. DataQualityClosureReport tests
# ===================================================================


class TestClosureReportConstruction:
    def test_happy_path(self):
        c = _closure(total_records=10, total_schemas=5, total_drifts=2,
                     total_duplicates=3, total_violations=1)
        assert c.report_id == "rpt1"
        assert c.total_records == 10
        assert c.total_schemas == 5
        assert c.total_drifts == 2
        assert c.total_duplicates == 3
        assert c.total_violations == 1

    def test_all_zeros(self):
        c = _closure()
        assert c.total_records == 0
        assert c.total_violations == 0

    def test_date_only_accepted(self):
        c = _closure(created_at=DATE_ONLY)
        assert c.created_at == DATE_ONLY

    def test_metadata_frozen(self):
        c = _closure(metadata={"key": "val"})
        assert isinstance(c.metadata, MappingProxyType)


class TestClosureReportValidation:
    @pytest.mark.parametrize("field", ["report_id", "tenant_id"])
    def test_empty_text_rejected(self, field):
        with pytest.raises(ValueError):
            _closure(**{field: ""})

    @pytest.mark.parametrize("field", [
        "total_records", "total_schemas", "total_drifts",
        "total_duplicates", "total_violations",
    ])
    def test_negative_int_rejected(self, field):
        with pytest.raises(ValueError):
            _closure(**{field: -1})

    @pytest.mark.parametrize("field", [
        "total_records", "total_schemas", "total_drifts",
        "total_duplicates", "total_violations",
    ])
    def test_bool_rejected(self, field):
        with pytest.raises(ValueError):
            _closure(**{field: True})

    @pytest.mark.parametrize("field", [
        "total_records", "total_schemas", "total_drifts",
        "total_duplicates", "total_violations",
    ])
    def test_float_rejected(self, field):
        with pytest.raises(ValueError):
            _closure(**{field: 1.0})

    def test_created_at_empty_rejected(self):
        with pytest.raises(ValueError):
            _closure(created_at="")


class TestClosureReportFrozen:
    @pytest.mark.parametrize("field", [
        "report_id", "tenant_id", "total_records", "total_schemas",
    ])
    def test_frozen_field(self, field):
        c = _closure()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            setattr(c, field, "x")


# ===================================================================
# 12. Cross-cutting serialization tests
# ===================================================================


class TestSerialization:
    """Verify to_dict / to_json_dict / to_json across all contract types."""

    @pytest.mark.parametrize("factory", [
        _dqr, _sv, _dd, _lr, _dup, _rec, _sqp, _snap, _viol, _closure,
    ])
    def test_to_dict_returns_dict(self, factory):
        assert isinstance(factory().to_dict(), dict)

    @pytest.mark.parametrize("factory", [
        _dqr, _sv, _dd, _lr, _dup, _rec, _sqp, _snap, _viol, _closure,
    ])
    def test_to_json_dict_returns_dict(self, factory):
        assert isinstance(factory().to_json_dict(), dict)

    @pytest.mark.parametrize("factory", [
        _rec, _snap, _viol, _closure,
    ])
    def test_to_json_returns_string(self, factory):
        """to_json works on types that have no enum fields or use to_json_dict."""
        j = factory().to_json()
        assert isinstance(j, str)
        import json
        json.loads(j)  # must be valid JSON

    @pytest.mark.parametrize("factory", [
        _dqr, _sv, _dd, _lr, _dup, _sqp,
    ])
    def test_to_json_works_via_json_dict(self, factory):
        """Types with enum fields can still to_json() since it uses to_json_dict."""
        j = factory().to_json()
        assert isinstance(j, str)
        import json
        json.loads(j)


# ===================================================================
# 13. Metadata deep freeze tests
# ===================================================================


class TestMetadataDeepFreeze:
    def test_nested_dict_frozen(self):
        r = _dqr(metadata={"outer": {"inner": 1}})
        assert isinstance(r.metadata["outer"], MappingProxyType)

    def test_nested_list_becomes_tuple(self):
        r = _dqr(metadata={"items": [1, 2, 3]})
        assert isinstance(r.metadata["items"], tuple)
        assert r.metadata["items"] == (1, 2, 3)

    def test_mutation_of_source_dict_does_not_affect_record(self):
        src = {"k": "v"}
        r = _dqr(metadata=src)
        src["k"] = "changed"
        assert r.metadata["k"] == "v"

    def test_nested_set_frozen(self):
        r = _dqr(metadata={"s": {1, 2}})
        assert isinstance(r.metadata["s"], frozenset)


# ===================================================================
# 14. Boundary value tests
# ===================================================================


class TestBoundaryValues:
    def test_large_error_count(self):
        r = _dqr(error_count=999_999)
        assert r.error_count == 999_999

    def test_large_version_number(self):
        s = _sv(version_number=100_000)
        assert s.version_number == 100_000

    def test_large_hop_count(self):
        lr = _lr(hop_count=1_000_000)
        assert lr.hop_count == 1_000_000

    def test_confidence_boundary_zero(self):
        d = _dup(confidence=0.0)
        assert d.confidence == 0.0

    def test_confidence_boundary_one(self):
        d = _dup(confidence=1.0)
        assert d.confidence == 1.0

    def test_confidence_just_above_zero(self):
        d = _dup(confidence=0.001)
        assert d.confidence == pytest.approx(0.001)

    def test_confidence_just_below_one(self):
        d = _dup(confidence=0.999)
        assert d.confidence == pytest.approx(0.999)


# ===================================================================
# 15. Timestamp format tests
# ===================================================================


class TestTimestampFormats:
    VALID_STAMPS = [
        "2025-06-01",
        "2025-06-01T12:00:00",
        "2025-06-01T12:00:00+00:00",
        "2025-06-01T12:00:00Z",
        "2025-06-01T12:00:00.123456+00:00",
        "2025-12-31T23:59:59-05:00",
    ]

    @pytest.mark.parametrize("ts", VALID_STAMPS)
    def test_valid_timestamp_accepted_dqr(self, ts):
        r = _dqr(checked_at=ts)
        assert r.checked_at == ts

    @pytest.mark.parametrize("ts", VALID_STAMPS)
    def test_valid_timestamp_accepted_sv(self, ts):
        s = _sv(created_at=ts)
        assert s.created_at == ts

    @pytest.mark.parametrize("ts", VALID_STAMPS)
    def test_valid_timestamp_accepted_dd(self, ts):
        d = _dd(detected_at=ts)
        assert d.detected_at == ts

    @pytest.mark.parametrize("ts", VALID_STAMPS)
    def test_valid_timestamp_accepted_lr(self, ts):
        lr = _lr(created_at=ts)
        assert lr.created_at == ts

    @pytest.mark.parametrize("ts", VALID_STAMPS)
    def test_valid_timestamp_accepted_dup(self, ts):
        d = _dup(detected_at=ts)
        assert d.detected_at == ts

    @pytest.mark.parametrize("ts", VALID_STAMPS)
    def test_valid_timestamp_accepted_rec(self, ts):
        r = _rec(created_at=ts)
        assert r.created_at == ts


# ===================================================================
# 16. Identity / equality tests
# ===================================================================


class TestIdentityEquality:
    def test_equal_records_are_equal(self):
        a = _dqr()
        b = _dqr()
        assert a == b

    def test_different_id_not_equal(self):
        a = _dqr(record_id="r1")
        b = _dqr(record_id="r2")
        assert a != b

    def test_schema_equal(self):
        a = _sv()
        b = _sv()
        assert a == b

    def test_schema_different_status_not_equal(self):
        a = _sv(status=SchemaEvolutionStatus.CURRENT)
        b = _sv(status=SchemaEvolutionStatus.RETIRED)
        assert a != b

    def test_drift_equal(self):
        a = _dd()
        b = _dd()
        assert a == b

    def test_lineage_equal(self):
        a = _lr()
        b = _lr()
        assert a == b

    def test_duplicate_equal(self):
        a = _dup()
        b = _dup()
        assert a == b

    def test_reconciliation_equal(self):
        a = _rec()
        b = _rec()
        assert a == b

    def test_policy_equal(self):
        a = _sqp()
        b = _sqp()
        assert a == b

    def test_snapshot_equal(self):
        a = _snap()
        b = _snap()
        assert a == b

    def test_violation_equal(self):
        a = _viol()
        b = _viol()
        assert a == b

    def test_closure_equal(self):
        a = _closure()
        b = _closure()
        assert a == b


# ===================================================================
# 17. Whitespace-only text rejection
# ===================================================================


class TestWhitespaceRejection:
    @pytest.mark.parametrize("val", ["", "  ", "\t", "\n", " \t\n "])
    def test_dqr_record_id_whitespace(self, val):
        with pytest.raises(ValueError):
            _dqr(record_id=val)

    @pytest.mark.parametrize("val", ["", "  ", "\t"])
    def test_sv_version_id_whitespace(self, val):
        with pytest.raises(ValueError):
            _sv(version_id=val)

    @pytest.mark.parametrize("val", ["", "  ", "\t"])
    def test_dd_detection_id_whitespace(self, val):
        with pytest.raises(ValueError):
            _dd(detection_id=val)

    @pytest.mark.parametrize("val", ["", "  "])
    def test_lr_lineage_id_whitespace(self, val):
        with pytest.raises(ValueError):
            _lr(lineage_id=val)

    @pytest.mark.parametrize("val", ["", "  "])
    def test_dup_duplicate_id_whitespace(self, val):
        with pytest.raises(ValueError):
            _dup(duplicate_id=val)

    @pytest.mark.parametrize("val", ["", "  "])
    def test_rec_reconciliation_id_whitespace(self, val):
        with pytest.raises(ValueError):
            _rec(reconciliation_id=val)

    @pytest.mark.parametrize("val", ["", "  "])
    def test_sqp_policy_id_whitespace(self, val):
        with pytest.raises(ValueError):
            _sqp(policy_id=val)

    @pytest.mark.parametrize("val", ["", "  "])
    def test_snap_snapshot_id_whitespace(self, val):
        with pytest.raises(ValueError):
            _snap(snapshot_id=val)

    @pytest.mark.parametrize("val", ["", "  "])
    def test_viol_violation_id_whitespace(self, val):
        with pytest.raises(ValueError):
            _viol(violation_id=val)

    @pytest.mark.parametrize("val", ["", "  "])
    def test_closure_report_id_whitespace(self, val):
        with pytest.raises(ValueError):
            _closure(report_id=val)
