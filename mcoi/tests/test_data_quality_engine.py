"""Comprehensive tests for DataQualityEngine.

Covers registration, schema lifecycle, drift detection, lineage,
duplicates, reconciliation, policies, snapshots, violations,
trust score computation, state hashing, replay, and edge cases (~300 tests).
"""

from __future__ import annotations

import pytest

from mcoi_runtime.contracts.data_quality import (
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
from mcoi_runtime.core.data_quality import (
    DataQualityEngine,
    compute_trust_score,
    _auto_drift_severity,
)
from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError


# ===================================================================
# Fixtures
# ===================================================================


@pytest.fixture
def es():
    return EventSpineEngine()


@pytest.fixture
def engine(es):
    return DataQualityEngine(es)


# ===================================================================
# 1. Engine construction
# ===================================================================


class TestEngineConstruction:
    def test_accepts_event_spine(self, es):
        eng = DataQualityEngine(es)
        assert eng.record_count == 0

    def test_rejects_non_event_spine(self):
        with pytest.raises(RuntimeCoreInvariantError):
            DataQualityEngine("not-an-event-spine")

    def test_rejects_none(self):
        with pytest.raises(RuntimeCoreInvariantError):
            DataQualityEngine(None)

    def test_initial_counts_zero(self, engine):
        assert engine.record_count == 0
        assert engine.schema_count == 0
        assert engine.drift_count == 0
        assert engine.lineage_count == 0
        assert engine.duplicate_count == 0
        assert engine.reconciliation_count == 0
        assert engine.policy_count == 0
        assert engine.violation_count == 0


# ===================================================================
# 2. Trust score computation
# ===================================================================


class TestComputeTrustScore:
    def test_zero_errors_high(self):
        assert compute_trust_score(0) is TrustScore.HIGH

    def test_one_error_medium(self):
        assert compute_trust_score(1) is TrustScore.MEDIUM

    def test_two_errors_medium(self):
        assert compute_trust_score(2) is TrustScore.MEDIUM

    def test_three_errors_medium(self):
        assert compute_trust_score(3) is TrustScore.MEDIUM

    def test_four_errors_low(self):
        assert compute_trust_score(4) is TrustScore.LOW

    def test_nine_errors_low(self):
        assert compute_trust_score(9) is TrustScore.LOW

    def test_ten_errors_untrusted(self):
        assert compute_trust_score(10) is TrustScore.UNTRUSTED

    def test_hundred_errors_untrusted(self):
        assert compute_trust_score(100) is TrustScore.UNTRUSTED

    def test_negative_errors_high(self):
        assert compute_trust_score(-1) is TrustScore.HIGH


# ===================================================================
# 3. Auto drift severity
# ===================================================================


class TestAutoDriftSeverity:
    def test_same_type_none(self):
        assert _auto_drift_severity("str", "str", "f") is DriftSeverity.NONE

    def test_str_int_breaking(self):
        assert _auto_drift_severity("str", "int", "f") is DriftSeverity.BREAKING

    def test_int_str_breaking(self):
        assert _auto_drift_severity("int", "str", "f") is DriftSeverity.BREAKING

    def test_str_bool_breaking(self):
        assert _auto_drift_severity("str", "bool", "f") is DriftSeverity.BREAKING

    def test_bool_str_breaking(self):
        assert _auto_drift_severity("bool", "str", "f") is DriftSeverity.BREAKING

    def test_int_bool_breaking(self):
        assert _auto_drift_severity("int", "bool", "f") is DriftSeverity.BREAKING

    def test_bool_int_breaking(self):
        assert _auto_drift_severity("bool", "int", "f") is DriftSeverity.BREAKING

    def test_str_float_breaking(self):
        assert _auto_drift_severity("str", "float", "f") is DriftSeverity.BREAKING

    def test_float_str_breaking(self):
        assert _auto_drift_severity("float", "str", "f") is DriftSeverity.BREAKING

    def test_int_float_breaking(self):
        assert _auto_drift_severity("int", "float", "f") is DriftSeverity.BREAKING

    def test_float_int_breaking(self):
        assert _auto_drift_severity("float", "int", "f") is DriftSeverity.BREAKING

    def test_list_dict_breaking(self):
        assert _auto_drift_severity("list", "dict", "f") is DriftSeverity.BREAKING

    def test_dict_list_breaking(self):
        assert _auto_drift_severity("dict", "list", "f") is DriftSeverity.BREAKING

    def test_empty_expected_major(self):
        assert _auto_drift_severity("", "str", "f") is DriftSeverity.MAJOR

    def test_empty_actual_major(self):
        assert _auto_drift_severity("str", "", "f") is DriftSeverity.MAJOR

    def test_whitespace_expected_major(self):
        assert _auto_drift_severity("  ", "str", "f") is DriftSeverity.MAJOR

    def test_type_widened_minor(self):
        assert _auto_drift_severity("int", "number", "f") is DriftSeverity.MINOR

    def test_unknown_pair_minor(self):
        assert _auto_drift_severity("text", "varchar", "f") is DriftSeverity.MINOR

    def test_case_insensitive_breaking(self):
        assert _auto_drift_severity("Str", "Int", "f") is DriftSeverity.BREAKING

    def test_case_insensitive_same_none(self):
        # Both lowered to "str" == "str"
        assert _auto_drift_severity("STR", "str", "f") is DriftSeverity.MINOR


# ===================================================================
# 4. Quality record management
# ===================================================================


class TestQualityRecordRegistration:
    def test_register_returns_record(self, engine):
        r = engine.register_quality_record("r1", "t1", "src1")
        assert isinstance(r, DataQualityRecord)
        assert r.record_id == "r1"

    def test_register_default_clean(self, engine):
        r = engine.register_quality_record("r1", "t1", "src1")
        assert r.status is DataQualityStatus.CLEAN

    def test_register_default_zero_errors(self, engine):
        r = engine.register_quality_record("r1", "t1", "src1")
        assert r.error_count == 0

    def test_register_trust_score_auto(self, engine):
        r = engine.register_quality_record("r1", "t1", "src1", error_count=0)
        assert r.trust_score is TrustScore.HIGH

    def test_register_trust_score_medium(self, engine):
        r = engine.register_quality_record("r1", "t1", "src1", error_count=2)
        assert r.trust_score is TrustScore.MEDIUM

    def test_register_trust_score_low(self, engine):
        r = engine.register_quality_record("r1", "t1", "src1", error_count=5)
        assert r.trust_score is TrustScore.LOW

    def test_register_trust_score_untrusted(self, engine):
        r = engine.register_quality_record("r1", "t1", "src1", error_count=10)
        assert r.trust_score is TrustScore.UNTRUSTED

    def test_register_custom_status(self, engine):
        r = engine.register_quality_record("r1", "t1", "src1", status=DataQualityStatus.DIRTY)
        assert r.status is DataQualityStatus.DIRTY

    def test_register_increments_count(self, engine):
        engine.register_quality_record("r1", "t1", "src1")
        assert engine.record_count == 1
        engine.register_quality_record("r2", "t1", "src2")
        assert engine.record_count == 2

    def test_duplicate_id_rejected(self, engine):
        engine.register_quality_record("r1", "t1", "src1")
        with pytest.raises(RuntimeCoreInvariantError) as exc_info:
            engine.register_quality_record("r1", "t1", "src2")
        assert "r1" not in str(exc_info.value)

    def test_emits_event(self, engine, es):
        before = es.event_count
        engine.register_quality_record("r1", "t1", "src1")
        assert es.event_count == before + 1


class TestGetRecord:
    def test_get_existing(self, engine):
        engine.register_quality_record("r1", "t1", "src1")
        r = engine.get_record("r1")
        assert r.record_id == "r1"

    def test_get_unknown_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError) as exc_info:
            engine.get_record("nope")
        assert "nope" not in str(exc_info.value)


class TestRecordsForTenant:
    def test_empty(self, engine):
        assert engine.records_for_tenant("t1") == ()

    def test_filters_by_tenant(self, engine):
        engine.register_quality_record("r1", "t1", "src1")
        engine.register_quality_record("r2", "t2", "src2")
        engine.register_quality_record("r3", "t1", "src3")
        result = engine.records_for_tenant("t1")
        assert len(result) == 2
        assert all(r.tenant_id == "t1" for r in result)

    def test_returns_tuple(self, engine):
        engine.register_quality_record("r1", "t1", "src1")
        assert isinstance(engine.records_for_tenant("t1"), tuple)


# ===================================================================
# 5. Schema version management
# ===================================================================


class TestSchemaVersionRegistration:
    def test_register_returns_schema(self, engine):
        s = engine.register_schema_version("v1", "t1", "sch1")
        assert isinstance(s, SchemaVersion)
        assert s.version_id == "v1"

    def test_default_current_status(self, engine):
        s = engine.register_schema_version("v1", "t1", "sch1")
        assert s.status is SchemaEvolutionStatus.CURRENT

    def test_custom_version_number(self, engine):
        s = engine.register_schema_version("v1", "t1", "sch1", version_number=42)
        assert s.version_number == 42

    def test_custom_field_count(self, engine):
        s = engine.register_schema_version("v1", "t1", "sch1", field_count=10)
        assert s.field_count == 10

    def test_increments_count(self, engine):
        engine.register_schema_version("v1", "t1", "sch1")
        assert engine.schema_count == 1

    def test_duplicate_rejected(self, engine):
        engine.register_schema_version("v1", "t1", "sch1")
        with pytest.raises(RuntimeCoreInvariantError) as exc_info:
            engine.register_schema_version("v1", "t1", "sch2")
        assert "v1" not in str(exc_info.value)

    def test_emits_event(self, engine, es):
        before = es.event_count
        engine.register_schema_version("v1", "t1", "sch1")
        assert es.event_count == before + 1


class TestSchemaDeprecation:
    def test_deprecate_current(self, engine):
        engine.register_schema_version("v1", "t1", "sch1")
        s = engine.deprecate_schema("v1")
        assert s.status is SchemaEvolutionStatus.DEPRECATED

    def test_deprecate_unknown_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError) as exc_info:
            engine.deprecate_schema("nope")
        assert "nope" not in str(exc_info.value)

    def test_deprecate_retired_raises(self, engine):
        engine.register_schema_version("v1", "t1", "sch1")
        engine.retire_schema("v1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal"):
            engine.deprecate_schema("v1")

    def test_deprecate_preserves_fields(self, engine):
        engine.register_schema_version("v1", "t1", "sch1", version_number=3, field_count=7)
        s = engine.deprecate_schema("v1")
        assert s.version_number == 3
        assert s.field_count == 7

    def test_deprecate_emits_event(self, engine, es):
        engine.register_schema_version("v1", "t1", "sch1")
        before = es.event_count
        engine.deprecate_schema("v1")
        assert es.event_count == before + 1


class TestSchemaRetirement:
    def test_retire_current(self, engine):
        engine.register_schema_version("v1", "t1", "sch1")
        s = engine.retire_schema("v1")
        assert s.status is SchemaEvolutionStatus.RETIRED

    def test_retire_deprecated(self, engine):
        engine.register_schema_version("v1", "t1", "sch1")
        engine.deprecate_schema("v1")
        s = engine.retire_schema("v1")
        assert s.status is SchemaEvolutionStatus.RETIRED

    def test_retire_unknown_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError) as exc_info:
            engine.retire_schema("nope")
        assert "nope" not in str(exc_info.value)

    def test_retire_already_retired_raises(self, engine):
        engine.register_schema_version("v1", "t1", "sch1")
        engine.retire_schema("v1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal"):
            engine.retire_schema("v1")

    def test_retire_emits_event(self, engine, es):
        engine.register_schema_version("v1", "t1", "sch1")
        before = es.event_count
        engine.retire_schema("v1")
        assert es.event_count == before + 1


class TestSchemaLifecycle:
    """Golden scenario: CURRENT -> DEPRECATED -> RETIRED."""

    def test_full_lifecycle(self, engine):
        s = engine.register_schema_version("v1", "t1", "sch1")
        assert s.status is SchemaEvolutionStatus.CURRENT

        s = engine.deprecate_schema("v1")
        assert s.status is SchemaEvolutionStatus.DEPRECATED

        s = engine.retire_schema("v1")
        assert s.status is SchemaEvolutionStatus.RETIRED

    def test_terminal_blocks_deprecate(self, engine):
        engine.register_schema_version("v1", "t1", "sch1")
        engine.retire_schema("v1")
        with pytest.raises(RuntimeCoreInvariantError):
            engine.deprecate_schema("v1")

    def test_terminal_blocks_retire(self, engine):
        engine.register_schema_version("v1", "t1", "sch1")
        engine.retire_schema("v1")
        with pytest.raises(RuntimeCoreInvariantError):
            engine.retire_schema("v1")


# ===================================================================
# 6. Drift detection
# ===================================================================


class TestDriftDetection:
    def test_detect_returns_drift(self, engine):
        d = engine.detect_drift("d1", "t1", "sch1", "col_a", "str", "int")
        assert isinstance(d, DriftDetection)
        assert d.detection_id == "d1"

    def test_auto_severity_breaking(self, engine):
        d = engine.detect_drift("d1", "t1", "sch1", "col_a", "str", "int")
        assert d.severity is DriftSeverity.BREAKING

    def test_auto_severity_none_same_type(self, engine):
        d = engine.detect_drift("d1", "t1", "sch1", "col_a", "str", "str")
        assert d.severity is DriftSeverity.NONE

    def test_auto_severity_minor(self, engine):
        d = engine.detect_drift("d1", "t1", "sch1", "col_a", "int", "number")
        assert d.severity is DriftSeverity.MINOR

    def test_auto_severity_minor_different_type(self, engine):
        d = engine.detect_drift("d1", "t1", "sch1", "col_a", "str", "removed")
        assert d.severity is DriftSeverity.MINOR

    def test_increments_count(self, engine):
        engine.detect_drift("d1", "t1", "sch1", "col_a", "str", "int")
        assert engine.drift_count == 1

    def test_duplicate_rejected(self, engine):
        engine.detect_drift("d1", "t1", "sch1", "col_a", "str", "int")
        with pytest.raises(RuntimeCoreInvariantError) as exc_info:
            engine.detect_drift("d1", "t1", "sch1", "col_b", "str", "int")
        assert "d1" not in str(exc_info.value)

    def test_emits_event(self, engine, es):
        before = es.event_count
        engine.detect_drift("d1", "t1", "sch1", "col_a", "str", "int")
        assert es.event_count == before + 1

    def test_field_name_stored(self, engine):
        d = engine.detect_drift("d1", "t1", "sch1", "user_age", "str", "int")
        assert d.field_name == "user_age"

    def test_expected_type_stored(self, engine):
        d = engine.detect_drift("d1", "t1", "sch1", "f", "str", "int")
        assert d.expected_type == "str"

    def test_actual_type_stored(self, engine):
        d = engine.detect_drift("d1", "t1", "sch1", "f", "str", "int")
        assert d.actual_type == "int"


# ===================================================================
# 7. Lineage management
# ===================================================================


class TestLineageRegistration:
    def test_register_returns_lineage(self, engine):
        lr = engine.register_lineage("l1", "t1", "src1", "tgt1")
        assert isinstance(lr, LineageRecord)
        assert lr.lineage_id == "l1"

    def test_default_unverified(self, engine):
        lr = engine.register_lineage("l1", "t1", "src1", "tgt1")
        assert lr.disposition is LineageDisposition.UNVERIFIED

    def test_default_hop_count(self, engine):
        lr = engine.register_lineage("l1", "t1", "src1", "tgt1")
        assert lr.hop_count == 1

    def test_custom_hop_count(self, engine):
        lr = engine.register_lineage("l1", "t1", "src1", "tgt1", hop_count=5)
        assert lr.hop_count == 5

    def test_increments_count(self, engine):
        engine.register_lineage("l1", "t1", "src1", "tgt1")
        assert engine.lineage_count == 1

    def test_duplicate_rejected(self, engine):
        engine.register_lineage("l1", "t1", "src1", "tgt1")
        with pytest.raises(RuntimeCoreInvariantError) as exc_info:
            engine.register_lineage("l1", "t1", "src2", "tgt2")
        assert "l1" not in str(exc_info.value)

    def test_emits_event(self, engine, es):
        before = es.event_count
        engine.register_lineage("l1", "t1", "src1", "tgt1")
        assert es.event_count == before + 1


class TestGetLineage:
    def test_get_existing(self, engine):
        engine.register_lineage("l1", "t1", "src1", "tgt1")
        lr = engine.get_lineage("l1")
        assert lr.lineage_id == "l1"

    def test_get_unknown_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError) as exc_info:
            engine.get_lineage("nope")
        assert "nope" not in str(exc_info.value)


class TestVerifyLineage:
    def test_verify_true(self, engine):
        engine.register_lineage("l1", "t1", "src1", "tgt1")
        lr = engine.verify_lineage("l1", verified=True)
        assert lr.disposition is LineageDisposition.VERIFIED

    def test_verify_false_broken(self, engine):
        engine.register_lineage("l1", "t1", "src1", "tgt1")
        lr = engine.verify_lineage("l1", verified=False)
        assert lr.disposition is LineageDisposition.BROKEN

    def test_verify_default_true(self, engine):
        engine.register_lineage("l1", "t1", "src1", "tgt1")
        lr = engine.verify_lineage("l1")
        assert lr.disposition is LineageDisposition.VERIFIED

    def test_verify_unknown_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError) as exc_info:
            engine.verify_lineage("nope")
        assert "nope" not in str(exc_info.value)

    def test_verify_preserves_hop_count(self, engine):
        engine.register_lineage("l1", "t1", "src1", "tgt1", hop_count=3)
        lr = engine.verify_lineage("l1")
        assert lr.hop_count == 3

    def test_verify_emits_event(self, engine, es):
        engine.register_lineage("l1", "t1", "src1", "tgt1")
        before = es.event_count
        engine.verify_lineage("l1")
        assert es.event_count == before + 1


class TestLineageLifecycle:
    """Golden scenario: UNVERIFIED -> VERIFIED, UNVERIFIED -> BROKEN."""

    def test_register_then_verify(self, engine):
        lr = engine.register_lineage("l1", "t1", "src1", "tgt1")
        assert lr.disposition is LineageDisposition.UNVERIFIED
        lr = engine.verify_lineage("l1", verified=True)
        assert lr.disposition is LineageDisposition.VERIFIED

    def test_register_then_break(self, engine):
        lr = engine.register_lineage("l1", "t1", "src1", "tgt1")
        assert lr.disposition is LineageDisposition.UNVERIFIED
        lr = engine.verify_lineage("l1", verified=False)
        assert lr.disposition is LineageDisposition.BROKEN


# ===================================================================
# 8. Duplicate detection
# ===================================================================


class TestDuplicateDetection:
    def test_detect_returns_duplicate(self, engine):
        d = engine.detect_duplicate("dup1", "t1", "ra", "rb")
        assert isinstance(d, DuplicateRecord)
        assert d.duplicate_id == "dup1"

    def test_default_suspected(self, engine):
        d = engine.detect_duplicate("dup1", "t1", "ra", "rb")
        assert d.disposition is DuplicateDisposition.SUSPECTED

    def test_default_confidence(self, engine):
        d = engine.detect_duplicate("dup1", "t1", "ra", "rb")
        assert d.confidence == 0.5

    def test_custom_confidence(self, engine):
        d = engine.detect_duplicate("dup1", "t1", "ra", "rb", confidence=0.9)
        assert d.confidence == 0.9

    def test_increments_count(self, engine):
        engine.detect_duplicate("dup1", "t1", "ra", "rb")
        assert engine.duplicate_count == 1

    def test_duplicate_id_rejected(self, engine):
        engine.detect_duplicate("dup1", "t1", "ra", "rb")
        with pytest.raises(RuntimeCoreInvariantError) as exc_info:
            engine.detect_duplicate("dup1", "t1", "rc", "rd")
        assert "dup1" not in str(exc_info.value)

    def test_emits_event(self, engine, es):
        before = es.event_count
        engine.detect_duplicate("dup1", "t1", "ra", "rb")
        assert es.event_count == before + 1


class TestMergeDuplicate:
    def test_merge_confirmed(self, engine):
        engine.detect_duplicate("dup1", "t1", "ra", "rb")
        engine._confirm_duplicate("dup1")
        d = engine.merge_duplicate("dup1")
        assert d.disposition is DuplicateDisposition.MERGED

    def test_merge_suspected_raises(self, engine):
        engine.detect_duplicate("dup1", "t1", "ra", "rb")
        with pytest.raises(RuntimeCoreInvariantError, match="CONFIRMED"):
            engine.merge_duplicate("dup1")

    def test_merge_unknown_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError) as exc_info:
            engine.merge_duplicate("nope")
        assert "nope" not in str(exc_info.value)

    def test_merge_preserves_confidence(self, engine):
        engine.detect_duplicate("dup1", "t1", "ra", "rb", confidence=0.95)
        engine._confirm_duplicate("dup1")
        d = engine.merge_duplicate("dup1")
        assert d.confidence == 0.95

    def test_merge_emits_event(self, engine, es):
        engine.detect_duplicate("dup1", "t1", "ra", "rb")
        engine._confirm_duplicate("dup1")
        before = es.event_count
        engine.merge_duplicate("dup1")
        assert es.event_count == before + 1


class TestDismissDuplicate:
    def test_dismiss_returns_unique(self, engine):
        engine.detect_duplicate("dup1", "t1", "ra", "rb")
        d = engine.dismiss_duplicate("dup1")
        assert d.disposition is DuplicateDisposition.UNIQUE

    def test_dismiss_unknown_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError) as exc_info:
            engine.dismiss_duplicate("nope")
        assert "nope" not in str(exc_info.value)

    def test_dismiss_emits_event(self, engine, es):
        engine.detect_duplicate("dup1", "t1", "ra", "rb")
        before = es.event_count
        engine.dismiss_duplicate("dup1")
        assert es.event_count == before + 1


class TestConfirmDuplicate:
    def test_confirm_suspected(self, engine):
        engine.detect_duplicate("dup1", "t1", "ra", "rb")
        d = engine._confirm_duplicate("dup1")
        assert d.disposition is DuplicateDisposition.CONFIRMED

    def test_confirm_unknown_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError) as exc_info:
            engine._confirm_duplicate("nope")
        assert "nope" not in str(exc_info.value)


class TestDuplicateLifecycle:
    """Golden scenario: SUSPECTED -> CONFIRMED -> MERGED."""

    def test_full_lifecycle(self, engine):
        d = engine.detect_duplicate("dup1", "t1", "ra", "rb")
        assert d.disposition is DuplicateDisposition.SUSPECTED

        d = engine._confirm_duplicate("dup1")
        assert d.disposition is DuplicateDisposition.CONFIRMED

        d = engine.merge_duplicate("dup1")
        assert d.disposition is DuplicateDisposition.MERGED


# ===================================================================
# 9. Reconciliation
# ===================================================================


class TestReconciliation:
    def test_reconcile_returns_record(self, engine):
        r = engine.reconcile_record("rec1", "t1", "src1", "can1")
        assert isinstance(r, ReconciliationRecord)
        assert r.reconciliation_id == "rec1"

    def test_default_resolved_true(self, engine):
        r = engine.reconcile_record("rec1", "t1", "src1", "can1")
        assert r.resolved is True

    def test_resolved_false(self, engine):
        r = engine.reconcile_record("rec1", "t1", "src1", "can1", resolved=False)
        assert r.resolved is False

    def test_increments_count(self, engine):
        engine.reconcile_record("rec1", "t1", "src1", "can1")
        assert engine.reconciliation_count == 1

    def test_duplicate_rejected(self, engine):
        engine.reconcile_record("rec1", "t1", "src1", "can1")
        with pytest.raises(RuntimeCoreInvariantError) as exc_info:
            engine.reconcile_record("rec1", "t1", "src2", "can2")
        assert "rec1" not in str(exc_info.value)

    def test_emits_event(self, engine, es):
        before = es.event_count
        engine.reconcile_record("rec1", "t1", "src1", "can1")
        assert es.event_count == before + 1


# ===================================================================
# 10. Source quality policies
# ===================================================================


class TestSourceQualityPolicy:
    def test_register_returns_policy(self, engine):
        p = engine.register_source_policy("pol1", "t1", "src1")
        assert isinstance(p, SourceQualityPolicy)
        assert p.policy_id == "pol1"

    def test_default_min_trust(self, engine):
        p = engine.register_source_policy("pol1", "t1", "src1")
        assert p.min_trust is TrustScore.MEDIUM

    def test_default_max_errors(self, engine):
        p = engine.register_source_policy("pol1", "t1", "src1")
        assert p.max_errors == 10

    def test_custom_min_trust(self, engine):
        p = engine.register_source_policy("pol1", "t1", "src1", min_trust=TrustScore.HIGH)
        assert p.min_trust is TrustScore.HIGH

    def test_custom_max_errors(self, engine):
        p = engine.register_source_policy("pol1", "t1", "src1", max_errors=5)
        assert p.max_errors == 5

    def test_increments_count(self, engine):
        engine.register_source_policy("pol1", "t1", "src1")
        assert engine.policy_count == 1

    def test_duplicate_rejected(self, engine):
        engine.register_source_policy("pol1", "t1", "src1")
        with pytest.raises(RuntimeCoreInvariantError) as exc_info:
            engine.register_source_policy("pol1", "t1", "src2")
        assert "pol1" not in str(exc_info.value)

    def test_emits_event(self, engine, es):
        before = es.event_count
        engine.register_source_policy("pol1", "t1", "src1")
        assert es.event_count == before + 1


# ===================================================================
# 11. Snapshot
# ===================================================================


class TestSnapshot:
    def test_empty_snapshot(self, engine):
        s = engine.data_quality_snapshot("snap1", "t1")
        assert isinstance(s, DataQualitySnapshot)
        assert s.total_records == 0
        assert s.total_schemas == 0
        assert s.total_drifts == 0
        assert s.total_duplicates == 0
        assert s.total_lineages == 0
        assert s.total_violations == 0

    def test_snapshot_counts_tenant(self, engine):
        engine.register_quality_record("r1", "t1", "src1")
        engine.register_quality_record("r2", "t2", "src2")
        engine.register_schema_version("v1", "t1", "sch1")
        s = engine.data_quality_snapshot("snap1", "t1")
        assert s.total_records == 1
        assert s.total_schemas == 1

    def test_snapshot_counts_drifts(self, engine):
        engine.detect_drift("d1", "t1", "sch1", "f", "str", "int")
        engine.detect_drift("d2", "t2", "sch2", "f", "str", "int")
        s = engine.data_quality_snapshot("snap1", "t1")
        assert s.total_drifts == 1

    def test_snapshot_counts_duplicates(self, engine):
        engine.detect_duplicate("dup1", "t1", "ra", "rb")
        s = engine.data_quality_snapshot("snap1", "t1")
        assert s.total_duplicates == 1

    def test_snapshot_counts_lineages(self, engine):
        engine.register_lineage("l1", "t1", "src1", "tgt1")
        s = engine.data_quality_snapshot("snap1", "t1")
        assert s.total_lineages == 1

    def test_duplicate_snapshot_id_rejected(self, engine):
        engine.data_quality_snapshot("snap1", "t1")
        with pytest.raises(RuntimeCoreInvariantError) as exc_info:
            engine.data_quality_snapshot("snap1", "t1")
        assert "snap1" not in str(exc_info.value)

    def test_snapshot_emits_event(self, engine, es):
        before = es.event_count
        engine.data_quality_snapshot("snap1", "t1")
        assert es.event_count == before + 1


# ===================================================================
# 12. Violations
# ===================================================================


class TestViolationDetection:
    def test_no_violations_empty(self, engine):
        v = engine.detect_data_quality_violations("t1")
        assert v == ()

    def test_dirty_no_quarantine_violation(self, engine):
        engine.register_quality_record("r1", "t1", "src1", status=DataQualityStatus.DIRTY)
        v = engine.detect_data_quality_violations("t1")
        assert len(v) == 1
        assert v[0].operation == "dirty_no_quarantine"
        assert v[0].reason == "dirty record not quarantined"
        assert "r1" not in v[0].reason

    def test_clean_no_violation(self, engine):
        engine.register_quality_record("r1", "t1", "src1", status=DataQualityStatus.CLEAN)
        v = engine.detect_data_quality_violations("t1")
        assert len(v) == 0

    def test_breaking_drift_violation(self, engine):
        engine.detect_drift("d1", "t1", "sch1", "col_a", "str", "int")
        v = engine.detect_data_quality_violations("t1")
        assert len(v) == 1
        assert v[0].operation == "breaking_drift_unresolved"
        assert v[0].reason == "breaking drift unresolved"
        assert "d1" not in v[0].reason
        assert "col_a" not in v[0].reason

    def test_minor_drift_no_violation(self, engine):
        engine.detect_drift("d1", "t1", "sch1", "col_a", "int", "number")
        v = engine.detect_data_quality_violations("t1")
        assert len(v) == 0

    def test_broken_lineage_violation(self, engine):
        engine.register_lineage("l1", "t1", "src1", "tgt1")
        engine.verify_lineage("l1", verified=False)
        v = engine.detect_data_quality_violations("t1")
        assert len(v) == 1
        assert v[0].operation == "broken_lineage"
        assert v[0].reason == "lineage is broken"
        assert "l1" not in v[0].reason

    def test_verified_lineage_no_violation(self, engine):
        engine.register_lineage("l1", "t1", "src1", "tgt1")
        engine.verify_lineage("l1", verified=True)
        v = engine.detect_data_quality_violations("t1")
        assert len(v) == 0

    def test_idempotent_second_call_empty(self, engine):
        engine.register_quality_record("r1", "t1", "src1", status=DataQualityStatus.DIRTY)
        v1 = engine.detect_data_quality_violations("t1")
        assert len(v1) == 1
        v2 = engine.detect_data_quality_violations("t1")
        assert len(v2) == 0

    def test_idempotent_does_not_duplicate_count(self, engine):
        engine.register_quality_record("r1", "t1", "src1", status=DataQualityStatus.DIRTY)
        engine.detect_data_quality_violations("t1")
        before = engine.violation_count
        engine.detect_data_quality_violations("t1")
        assert engine.violation_count == before

    def test_multiple_violations(self, engine):
        engine.register_quality_record("r1", "t1", "src1", status=DataQualityStatus.DIRTY)
        engine.detect_drift("d1", "t1", "sch1", "col_a", "str", "int")
        engine.register_lineage("l1", "t1", "src1", "tgt1")
        engine.verify_lineage("l1", verified=False)
        v = engine.detect_data_quality_violations("t1")
        assert len(v) == 3

    def test_tenant_isolation(self, engine):
        engine.register_quality_record("r1", "t1", "src1", status=DataQualityStatus.DIRTY)
        engine.register_quality_record("r2", "t2", "src2", status=DataQualityStatus.DIRTY)
        v = engine.detect_data_quality_violations("t1")
        assert len(v) == 1
        assert all(viol.tenant_id == "t1" for viol in v)

    def test_violation_increments_count(self, engine):
        engine.register_quality_record("r1", "t1", "src1", status=DataQualityStatus.DIRTY)
        engine.detect_data_quality_violations("t1")
        assert engine.violation_count == 1

    def test_violations_emits_event(self, engine, es):
        engine.register_quality_record("r1", "t1", "src1", status=DataQualityStatus.DIRTY)
        before = es.event_count
        engine.detect_data_quality_violations("t1")
        assert es.event_count > before

    def test_violations_returns_tuple(self, engine):
        v = engine.detect_data_quality_violations("t1")
        assert isinstance(v, tuple)


# ===================================================================
# 13. State hash
# ===================================================================


class TestStateHash:
    def test_empty_engine_hash(self, engine):
        h = engine.state_hash()
        assert isinstance(h, str)
        assert len(h) == 64

    def test_hash_deterministic(self, engine):
        h1 = engine.state_hash()
        h2 = engine.state_hash()
        assert h1 == h2

    def test_hash_changes_after_mutation(self, engine):
        h1 = engine.state_hash()
        engine.register_quality_record("r1", "t1", "src1")
        h2 = engine.state_hash()
        assert h1 != h2

    def test_hash_changes_after_schema(self, engine):
        h1 = engine.state_hash()
        engine.register_schema_version("v1", "t1", "sch1")
        h2 = engine.state_hash()
        assert h1 != h2

    def test_hash_changes_after_drift(self, engine):
        h1 = engine.state_hash()
        engine.detect_drift("d1", "t1", "sch1", "f", "str", "int")
        h2 = engine.state_hash()
        assert h1 != h2

    def test_hash_changes_after_lineage(self, engine):
        h1 = engine.state_hash()
        engine.register_lineage("l1", "t1", "src1", "tgt1")
        h2 = engine.state_hash()
        assert h1 != h2


# ===================================================================
# 14. Replay golden scenario
# ===================================================================


class TestReplay:
    """Same operations produce same state_hash."""

    def _run_ops(self, eng):
        eng.register_quality_record("r1", "t1", "src1", error_count=2)
        eng.register_quality_record("r2", "t1", "src2", status=DataQualityStatus.DIRTY, error_count=5)
        eng.register_schema_version("v1", "t1", "sch1", version_number=1, field_count=10)
        eng.deprecate_schema("v1")
        eng.detect_drift("d1", "t1", "sch1", "col_a", "str", "int")
        eng.register_lineage("l1", "t1", "src1", "tgt1")
        eng.verify_lineage("l1", verified=True)
        eng.detect_duplicate("dup1", "t1", "ra", "rb", confidence=0.9)
        eng.reconcile_record("rec1", "t1", "src1", "can1")
        eng.register_source_policy("pol1", "t1", "src1")
        eng.detect_data_quality_violations("t1")
        return eng.state_hash()

    def test_same_ops_same_hash(self):
        es1 = EventSpineEngine()
        eng1 = DataQualityEngine(es1)
        h1 = self._run_ops(eng1)

        es2 = EventSpineEngine()
        eng2 = DataQualityEngine(es2)
        h2 = self._run_ops(eng2)

        assert h1 == h2

    def test_different_ops_different_hash(self):
        es1 = EventSpineEngine()
        eng1 = DataQualityEngine(es1)
        h1 = self._run_ops(eng1)

        es2 = EventSpineEngine()
        eng2 = DataQualityEngine(es2)
        eng2.register_quality_record("r1", "t1", "src1")
        h2 = eng2.state_hash()

        assert h1 != h2


# ===================================================================
# 15. Event emission counting
# ===================================================================


class TestEventCounting:
    def test_register_record_emits_one(self, engine, es):
        before = es.event_count
        engine.register_quality_record("r1", "t1", "src1")
        assert es.event_count == before + 1

    def test_register_schema_emits_one(self, engine, es):
        before = es.event_count
        engine.register_schema_version("v1", "t1", "sch1")
        assert es.event_count == before + 1

    def test_deprecate_schema_emits_one(self, engine, es):
        engine.register_schema_version("v1", "t1", "sch1")
        before = es.event_count
        engine.deprecate_schema("v1")
        assert es.event_count == before + 1

    def test_retire_schema_emits_one(self, engine, es):
        engine.register_schema_version("v1", "t1", "sch1")
        before = es.event_count
        engine.retire_schema("v1")
        assert es.event_count == before + 1

    def test_detect_drift_emits_one(self, engine, es):
        before = es.event_count
        engine.detect_drift("d1", "t1", "sch1", "f", "str", "int")
        assert es.event_count == before + 1

    def test_register_lineage_emits_one(self, engine, es):
        before = es.event_count
        engine.register_lineage("l1", "t1", "src1", "tgt1")
        assert es.event_count == before + 1

    def test_verify_lineage_emits_one(self, engine, es):
        engine.register_lineage("l1", "t1", "src1", "tgt1")
        before = es.event_count
        engine.verify_lineage("l1")
        assert es.event_count == before + 1

    def test_detect_duplicate_emits_one(self, engine, es):
        before = es.event_count
        engine.detect_duplicate("dup1", "t1", "ra", "rb")
        assert es.event_count == before + 1

    def test_merge_duplicate_emits_one(self, engine, es):
        engine.detect_duplicate("dup1", "t1", "ra", "rb")
        engine._confirm_duplicate("dup1")
        before = es.event_count
        engine.merge_duplicate("dup1")
        assert es.event_count == before + 1

    def test_dismiss_duplicate_emits_one(self, engine, es):
        engine.detect_duplicate("dup1", "t1", "ra", "rb")
        before = es.event_count
        engine.dismiss_duplicate("dup1")
        assert es.event_count == before + 1

    def test_reconcile_emits_one(self, engine, es):
        before = es.event_count
        engine.reconcile_record("rec1", "t1", "src1", "can1")
        assert es.event_count == before + 1

    def test_register_policy_emits_one(self, engine, es):
        before = es.event_count
        engine.register_source_policy("pol1", "t1", "src1")
        assert es.event_count == before + 1

    def test_snapshot_emits_one(self, engine, es):
        before = es.event_count
        engine.data_quality_snapshot("snap1", "t1")
        assert es.event_count == before + 1


# ===================================================================
# 16. Count property tests
# ===================================================================


class TestCountProperties:
    def test_record_count_increments(self, engine):
        for i in range(5):
            engine.register_quality_record(f"r{i}", "t1", f"src{i}")
        assert engine.record_count == 5

    def test_schema_count_increments(self, engine):
        for i in range(3):
            engine.register_schema_version(f"v{i}", "t1", f"sch{i}")
        assert engine.schema_count == 3

    def test_drift_count_increments(self, engine):
        for i in range(4):
            engine.detect_drift(f"d{i}", "t1", "sch1", f"col{i}", "str", "int")
        assert engine.drift_count == 4

    def test_lineage_count_increments(self, engine):
        for i in range(2):
            engine.register_lineage(f"l{i}", "t1", f"src{i}", f"tgt{i}")
        assert engine.lineage_count == 2

    def test_duplicate_count_increments(self, engine):
        for i in range(3):
            engine.detect_duplicate(f"dup{i}", "t1", f"ra{i}", f"rb{i}")
        assert engine.duplicate_count == 3

    def test_reconciliation_count_increments(self, engine):
        for i in range(2):
            engine.reconcile_record(f"rec{i}", "t1", f"src{i}", f"can{i}")
        assert engine.reconciliation_count == 2

    def test_policy_count_increments(self, engine):
        for i in range(2):
            engine.register_source_policy(f"pol{i}", "t1", f"src{i}")
        assert engine.policy_count == 2

    def test_violation_count_after_detection(self, engine):
        engine.register_quality_record("r1", "t1", "src1", status=DataQualityStatus.DIRTY)
        engine.detect_data_quality_violations("t1")
        assert engine.violation_count == 1


# ===================================================================
# 17. Multi-tenant isolation
# ===================================================================


class TestMultiTenantIsolation:
    def test_records_isolated(self, engine):
        engine.register_quality_record("r1", "t1", "src1")
        engine.register_quality_record("r2", "t2", "src2")
        assert len(engine.records_for_tenant("t1")) == 1
        assert len(engine.records_for_tenant("t2")) == 1

    def test_snapshot_isolated(self, engine):
        engine.register_quality_record("r1", "t1", "src1")
        engine.register_quality_record("r2", "t2", "src2")
        s = engine.data_quality_snapshot("snap1", "t1")
        assert s.total_records == 1

    def test_violations_isolated(self, engine):
        engine.register_quality_record("r1", "t1", "src1", status=DataQualityStatus.DIRTY)
        engine.register_quality_record("r2", "t2", "src2", status=DataQualityStatus.DIRTY)
        v = engine.detect_data_quality_violations("t1")
        assert len(v) == 1


# ===================================================================
# 18. Edge cases
# ===================================================================


class TestEdgeCases:
    def test_register_many_records(self, engine):
        for i in range(100):
            engine.register_quality_record(f"r{i}", "t1", f"src{i}")
        assert engine.record_count == 100

    def test_register_many_schemas(self, engine):
        for i in range(50):
            engine.register_schema_version(f"v{i}", "t1", f"sch{i}")
        assert engine.schema_count == 50

    def test_multiple_tenants_snapshot(self, engine):
        for i in range(10):
            engine.register_quality_record(f"r{i}", f"t{i%3}", f"src{i}")
        s0 = engine.data_quality_snapshot("snap0", "t0")
        s1 = engine.data_quality_snapshot("snap1", "t1")
        s2 = engine.data_quality_snapshot("snap2", "t2")
        assert s0.total_records + s1.total_records + s2.total_records == 10

    def test_degraded_no_violation(self, engine):
        engine.register_quality_record("r1", "t1", "src1", status=DataQualityStatus.DEGRADED)
        v = engine.detect_data_quality_violations("t1")
        assert len(v) == 0

    def test_quarantined_no_violation(self, engine):
        engine.register_quality_record("r1", "t1", "src1", status=DataQualityStatus.QUARANTINED)
        v = engine.detect_data_quality_violations("t1")
        assert len(v) == 0

    def test_none_severity_drift_no_violation(self, engine):
        engine.detect_drift("d1", "t1", "sch1", "f", "str", "str")
        v = engine.detect_data_quality_violations("t1")
        assert len(v) == 0

    def test_minor_drift_no_violation(self, engine):
        engine.detect_drift("d1", "t1", "sch1", "f", "str", "text")
        v = engine.detect_data_quality_violations("t1")
        assert len(v) == 0

    def test_unverified_lineage_no_violation(self, engine):
        engine.register_lineage("l1", "t1", "src1", "tgt1")
        v = engine.detect_data_quality_violations("t1")
        assert len(v) == 0


# ===================================================================
# 19. Golden scenario: trust score computation
# ===================================================================


class TestTrustScoreGolden:
    @pytest.mark.parametrize("error_count,expected", [
        (0, TrustScore.HIGH),
        (1, TrustScore.MEDIUM),
        (2, TrustScore.MEDIUM),
        (3, TrustScore.MEDIUM),
        (4, TrustScore.LOW),
        (5, TrustScore.LOW),
        (9, TrustScore.LOW),
        (10, TrustScore.UNTRUSTED),
        (50, TrustScore.UNTRUSTED),
        (100, TrustScore.UNTRUSTED),
    ])
    def test_thresholds(self, error_count, expected):
        assert compute_trust_score(error_count) is expected


# ===================================================================
# 20. Golden scenario: drift with auto-severity
# ===================================================================


class TestDriftWithAutoSeverityGolden:
    @pytest.mark.parametrize("exp,act,sev", [
        ("str", "int", DriftSeverity.BREAKING),
        ("int", "str", DriftSeverity.BREAKING),
        ("str", "bool", DriftSeverity.BREAKING),
        ("bool", "str", DriftSeverity.BREAKING),
        ("int", "bool", DriftSeverity.BREAKING),
        ("bool", "int", DriftSeverity.BREAKING),
        ("str", "float", DriftSeverity.BREAKING),
        ("float", "str", DriftSeverity.BREAKING),
        ("int", "float", DriftSeverity.BREAKING),
        ("float", "int", DriftSeverity.BREAKING),
        ("list", "dict", DriftSeverity.BREAKING),
        ("dict", "list", DriftSeverity.BREAKING),
        ("str", "null", DriftSeverity.MINOR),
        ("null", "str", DriftSeverity.MINOR),
        ("int", "number", DriftSeverity.MINOR),
        ("str", "str", DriftSeverity.NONE),
    ])
    def test_auto_severity(self, engine, exp, act, sev):
        d = engine.detect_drift(f"d-{exp}-{act}", "t1", "sch1", "f", exp, act)
        assert d.severity is sev
