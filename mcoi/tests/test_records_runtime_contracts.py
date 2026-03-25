"""Contract-level tests for records_runtime contracts.

Covers all 6 enums, 10 dataclasses, freeze/thaw semantics, to_dict round-trips,
immutability, and validation edge cases.  Does NOT test to_json (known enum
serialization issue).
"""

from __future__ import annotations

from types import MappingProxyType

import pytest

from mcoi_runtime.contracts.records_runtime import (
    DisposalDecision,
    DisposalDisposition,
    DispositionReview,
    EvidenceGrade,
    HoldStatus,
    LegalHoldRecord,
    PreservationDecision,
    RecordAuthority,
    RecordDescriptor,
    RecordKind,
    RecordLink,
    RecordSnapshot,
    RecordViolation,
    RecordsClosureReport,
    RetentionSchedule,
    RetentionStatus,
)

TS = "2025-06-01T12:00:00+00:00"
TS2 = "2025-07-01T12:00:00+00:00"


# ===================================================================
# Enum completeness
# ===================================================================


class TestRecordKindEnum:
    def test_member_count(self):
        assert len(RecordKind) == 7

    def test_all_members(self):
        expected = {
            "OPERATIONAL", "COMPLIANCE", "AUDIT", "EVIDENCE",
            "COMMUNICATION", "FINANCIAL", "LEGAL",
        }
        assert {m.name for m in RecordKind} == expected

    def test_values(self):
        assert RecordKind.OPERATIONAL.value == "operational"
        assert RecordKind.LEGAL.value == "legal"


class TestRetentionStatusEnum:
    def test_member_count(self):
        assert len(RetentionStatus) == 5

    def test_all_members(self):
        expected = {"ACTIVE", "EXPIRED", "DISPOSED", "HELD", "PENDING_REVIEW"}
        assert {m.name for m in RetentionStatus} == expected

    def test_values(self):
        assert RetentionStatus.PENDING_REVIEW.value == "pending_review"


class TestHoldStatusEnum:
    def test_member_count(self):
        assert len(HoldStatus) == 3

    def test_all_members(self):
        expected = {"ACTIVE", "RELEASED", "EXPIRED"}
        assert {m.name for m in HoldStatus} == expected

    def test_values(self):
        assert HoldStatus.RELEASED.value == "released"


class TestDisposalDispositionEnum:
    def test_member_count(self):
        assert len(DisposalDisposition) == 5

    def test_all_members(self):
        expected = {"DELETE", "ARCHIVE", "ANONYMIZE", "TRANSFER", "DENY"}
        assert {m.name for m in DisposalDisposition} == expected

    def test_values(self):
        assert DisposalDisposition.ANONYMIZE.value == "anonymize"


class TestRecordAuthorityEnum:
    def test_member_count(self):
        assert len(RecordAuthority) == 6

    def test_all_members(self):
        expected = {"SYSTEM", "OPERATOR", "LEGAL", "COMPLIANCE", "EXECUTIVE", "AUTOMATED"}
        assert {m.name for m in RecordAuthority} == expected

    def test_values(self):
        assert RecordAuthority.EXECUTIVE.value == "executive"


class TestEvidenceGradeEnum:
    def test_member_count(self):
        assert len(EvidenceGrade) == 5

    def test_all_members(self):
        expected = {"PRIMARY", "SECONDARY", "DERIVED", "COPY", "RECONSTRUCTED"}
        assert {m.name for m in EvidenceGrade} == expected

    def test_values(self):
        assert EvidenceGrade.RECONSTRUCTED.value == "reconstructed"


# ===================================================================
# RecordDescriptor
# ===================================================================


class TestRecordDescriptor:
    def _make(self, **kw):
        defaults = dict(
            record_id="rec-1", tenant_id="t-1", title="Title",
            created_at=TS,
        )
        defaults.update(kw)
        return RecordDescriptor(**defaults)

    def test_valid_defaults(self):
        r = self._make()
        assert r.record_id == "rec-1"
        assert r.tenant_id == "t-1"
        assert r.title == "Title"
        assert r.kind == RecordKind.OPERATIONAL
        assert r.source_type == ""
        assert r.source_id == ""
        assert r.authority == RecordAuthority.SYSTEM
        assert r.evidence_grade == EvidenceGrade.PRIMARY
        assert r.classification == ""
        assert r.created_at == TS

    def test_empty_record_id_rejected(self):
        with pytest.raises(ValueError):
            self._make(record_id="")

    def test_empty_tenant_id_rejected(self):
        with pytest.raises(ValueError):
            self._make(tenant_id="")

    def test_empty_title_rejected(self):
        with pytest.raises(ValueError):
            self._make(title="")

    def test_whitespace_only_title_rejected(self):
        with pytest.raises(ValueError):
            self._make(title="   ")

    def test_invalid_kind_rejected(self):
        with pytest.raises(ValueError):
            self._make(kind="not_a_kind")

    def test_invalid_authority_rejected(self):
        with pytest.raises(ValueError):
            self._make(authority="admin")

    def test_invalid_evidence_grade_rejected(self):
        with pytest.raises(ValueError):
            self._make(evidence_grade="best")

    def test_missing_created_at_rejected(self):
        with pytest.raises(ValueError):
            self._make(created_at="")

    def test_bad_datetime_rejected(self):
        with pytest.raises(ValueError):
            self._make(created_at="not-a-date")

    def test_all_kinds(self):
        for kind in RecordKind:
            r = self._make(kind=kind)
            assert r.kind is kind

    def test_all_authorities(self):
        for auth in RecordAuthority:
            r = self._make(authority=auth)
            assert r.authority is auth

    def test_all_evidence_grades(self):
        for grade in EvidenceGrade:
            r = self._make(evidence_grade=grade)
            assert r.evidence_grade is grade

    def test_metadata_frozen(self):
        r = self._make(metadata={"k": "v"})
        assert isinstance(r.metadata, MappingProxyType)
        with pytest.raises(TypeError):
            r.metadata["new"] = "x"

    def test_metadata_empty_default(self):
        r = self._make()
        assert isinstance(r.metadata, MappingProxyType)
        assert len(r.metadata) == 0

    def test_frozen_immutable(self):
        r = self._make()
        with pytest.raises(AttributeError):
            r.title = "changed"

    def test_to_dict_preserves_enums(self):
        r = self._make()
        d = r.to_dict()
        assert d["kind"] is RecordKind.OPERATIONAL
        assert d["authority"] is RecordAuthority.SYSTEM
        assert d["evidence_grade"] is EvidenceGrade.PRIMARY

    def test_to_dict_keys(self):
        d = self._make().to_dict()
        expected_keys = {
            "record_id", "tenant_id", "kind", "title", "source_type",
            "source_id", "authority", "evidence_grade", "classification",
            "created_at", "metadata",
        }
        assert set(d.keys()) == expected_keys

    def test_to_dict_metadata_thawed(self):
        r = self._make(metadata={"a": [1, 2]})
        d = r.to_dict()
        assert isinstance(d["metadata"], dict)
        assert isinstance(d["metadata"]["a"], list)

    def test_custom_fields(self):
        r = self._make(
            source_type="api", source_id="src-1",
            classification="secret",
            kind=RecordKind.EVIDENCE,
            authority=RecordAuthority.LEGAL,
            evidence_grade=EvidenceGrade.COPY,
        )
        assert r.source_type == "api"
        assert r.source_id == "src-1"
        assert r.classification == "secret"
        assert r.kind is RecordKind.EVIDENCE
        assert r.authority is RecordAuthority.LEGAL
        assert r.evidence_grade is EvidenceGrade.COPY


# ===================================================================
# RetentionSchedule
# ===================================================================


class TestRetentionSchedule:
    def _make(self, **kw):
        defaults = dict(
            schedule_id="sched-1", record_id="rec-1", tenant_id="t-1",
            created_at=TS,
        )
        defaults.update(kw)
        return RetentionSchedule(**defaults)

    def test_valid_defaults(self):
        r = self._make()
        assert r.schedule_id == "sched-1"
        assert r.retention_days == 0
        assert r.status is RetentionStatus.ACTIVE
        assert r.disposal_disposition is DisposalDisposition.DELETE
        assert r.scope_ref_id == ""
        assert r.expires_at == ""

    def test_empty_schedule_id_rejected(self):
        with pytest.raises(ValueError):
            self._make(schedule_id="")

    def test_empty_record_id_rejected(self):
        with pytest.raises(ValueError):
            self._make(record_id="")

    def test_empty_tenant_id_rejected(self):
        with pytest.raises(ValueError):
            self._make(tenant_id="")

    def test_negative_retention_days_rejected(self):
        with pytest.raises(ValueError):
            self._make(retention_days=-1)

    def test_zero_retention_days_ok(self):
        r = self._make(retention_days=0)
        assert r.retention_days == 0

    def test_positive_retention_days_ok(self):
        r = self._make(retention_days=365)
        assert r.retention_days == 365

    def test_bool_retention_days_rejected(self):
        with pytest.raises(ValueError):
            self._make(retention_days=True)

    def test_invalid_status_rejected(self):
        with pytest.raises(ValueError):
            self._make(status="active")

    def test_invalid_disposal_disposition_rejected(self):
        with pytest.raises(ValueError):
            self._make(disposal_disposition="burn")

    def test_missing_created_at_rejected(self):
        with pytest.raises(ValueError):
            self._make(created_at="")

    def test_all_statuses(self):
        for s in RetentionStatus:
            r = self._make(status=s)
            assert r.status is s

    def test_all_dispositions(self):
        for d in DisposalDisposition:
            r = self._make(disposal_disposition=d)
            assert r.disposal_disposition is d

    def test_metadata_frozen(self):
        r = self._make(metadata={"k": "v"})
        assert isinstance(r.metadata, MappingProxyType)
        with pytest.raises(TypeError):
            r.metadata["x"] = "y"

    def test_frozen_immutable(self):
        r = self._make()
        with pytest.raises(AttributeError):
            r.schedule_id = "other"

    def test_to_dict_preserves_enums(self):
        d = self._make().to_dict()
        assert d["status"] is RetentionStatus.ACTIVE
        assert d["disposal_disposition"] is DisposalDisposition.DELETE

    def test_to_dict_keys(self):
        d = self._make().to_dict()
        expected = {
            "schedule_id", "record_id", "tenant_id", "retention_days",
            "status", "disposal_disposition", "scope_ref_id",
            "created_at", "expires_at", "metadata",
        }
        assert set(d.keys()) == expected


# ===================================================================
# LegalHoldRecord
# ===================================================================


class TestLegalHoldRecord:
    def _make(self, **kw):
        defaults = dict(
            hold_id="hold-1", record_id="rec-1", tenant_id="t-1",
            placed_at=TS,
        )
        defaults.update(kw)
        return LegalHoldRecord(**defaults)

    def test_valid_defaults(self):
        r = self._make()
        assert r.hold_id == "hold-1"
        assert r.reason == ""
        assert r.authority is RecordAuthority.LEGAL
        assert r.status is HoldStatus.ACTIVE
        assert r.released_at == ""

    def test_empty_hold_id_rejected(self):
        with pytest.raises(ValueError):
            self._make(hold_id="")

    def test_empty_record_id_rejected(self):
        with pytest.raises(ValueError):
            self._make(record_id="")

    def test_empty_tenant_id_rejected(self):
        with pytest.raises(ValueError):
            self._make(tenant_id="")

    def test_invalid_authority_rejected(self):
        with pytest.raises(ValueError):
            self._make(authority="judge")

    def test_invalid_status_rejected(self):
        with pytest.raises(ValueError):
            self._make(status="pending")

    def test_missing_placed_at_rejected(self):
        with pytest.raises(ValueError):
            self._make(placed_at="")

    def test_bad_placed_at_rejected(self):
        with pytest.raises(ValueError):
            self._make(placed_at="yesterday")

    def test_all_hold_statuses(self):
        for hs in HoldStatus:
            r = self._make(status=hs)
            assert r.status is hs

    def test_all_authorities(self):
        for auth in RecordAuthority:
            r = self._make(authority=auth)
            assert r.authority is auth

    def test_metadata_frozen(self):
        r = self._make(metadata={"x": "y"})
        assert isinstance(r.metadata, MappingProxyType)
        with pytest.raises(TypeError):
            r.metadata["z"] = "w"

    def test_frozen_immutable(self):
        r = self._make()
        with pytest.raises(AttributeError):
            r.hold_id = "other"

    def test_to_dict_preserves_enums(self):
        d = self._make().to_dict()
        assert d["authority"] is RecordAuthority.LEGAL
        assert d["status"] is HoldStatus.ACTIVE

    def test_to_dict_keys(self):
        d = self._make().to_dict()
        expected = {
            "hold_id", "record_id", "tenant_id", "reason",
            "authority", "status", "placed_at", "released_at", "metadata",
        }
        assert set(d.keys()) == expected

    def test_custom_reason_and_released_at(self):
        r = self._make(reason="litigation", released_at=TS2)
        assert r.reason == "litigation"
        assert r.released_at == TS2


# ===================================================================
# DispositionReview
# ===================================================================


class TestDispositionReview:
    def _make(self, **kw):
        defaults = dict(
            review_id="rev-1", record_id="rec-1", reviewer_id="user-1",
            reviewed_at=TS,
        )
        defaults.update(kw)
        return DispositionReview(**defaults)

    def test_valid_defaults(self):
        r = self._make()
        assert r.review_id == "rev-1"
        assert r.decision is DisposalDisposition.DENY
        assert r.reason == ""

    def test_empty_review_id_rejected(self):
        with pytest.raises(ValueError):
            self._make(review_id="")

    def test_empty_record_id_rejected(self):
        with pytest.raises(ValueError):
            self._make(record_id="")

    def test_empty_reviewer_id_rejected(self):
        with pytest.raises(ValueError):
            self._make(reviewer_id="")

    def test_invalid_decision_rejected(self):
        with pytest.raises(ValueError):
            self._make(decision="approve")

    def test_missing_reviewed_at_rejected(self):
        with pytest.raises(ValueError):
            self._make(reviewed_at="")

    def test_all_decisions(self):
        for dd in DisposalDisposition:
            r = self._make(decision=dd)
            assert r.decision is dd

    def test_metadata_frozen(self):
        r = self._make(metadata={"k": [1, 2]})
        assert isinstance(r.metadata, MappingProxyType)

    def test_frozen_immutable(self):
        r = self._make()
        with pytest.raises(AttributeError):
            r.review_id = "other"

    def test_to_dict_preserves_enums(self):
        d = self._make().to_dict()
        assert d["decision"] is DisposalDisposition.DENY

    def test_to_dict_keys(self):
        d = self._make().to_dict()
        expected = {
            "review_id", "record_id", "reviewer_id",
            "decision", "reason", "reviewed_at", "metadata",
        }
        assert set(d.keys()) == expected

    def test_to_dict_metadata_thawed(self):
        r = self._make(metadata={"nested": {"a": 1}})
        d = r.to_dict()
        assert isinstance(d["metadata"], dict)
        assert isinstance(d["metadata"]["nested"], dict)


# ===================================================================
# RecordLink
# ===================================================================


class TestRecordLink:
    def _make(self, **kw):
        defaults = dict(
            link_id="lnk-1", record_id="rec-1", target_type="audit_event",
            target_id="evt-1", relationship="source_of", created_at=TS,
        )
        defaults.update(kw)
        return RecordLink(**defaults)

    def test_valid(self):
        r = self._make()
        assert r.link_id == "lnk-1"
        assert r.target_type == "audit_event"
        assert r.relationship == "source_of"

    def test_empty_link_id_rejected(self):
        with pytest.raises(ValueError):
            self._make(link_id="")

    def test_empty_record_id_rejected(self):
        with pytest.raises(ValueError):
            self._make(record_id="")

    def test_empty_target_type_rejected(self):
        with pytest.raises(ValueError):
            self._make(target_type="")

    def test_empty_target_id_rejected(self):
        with pytest.raises(ValueError):
            self._make(target_id="")

    def test_empty_relationship_rejected(self):
        with pytest.raises(ValueError):
            self._make(relationship="")

    def test_whitespace_only_link_id_rejected(self):
        with pytest.raises(ValueError):
            self._make(link_id="   ")

    def test_missing_created_at_rejected(self):
        with pytest.raises(ValueError):
            self._make(created_at="")

    def test_frozen_immutable(self):
        r = self._make()
        with pytest.raises(AttributeError):
            r.link_id = "other"

    def test_to_dict_keys(self):
        d = self._make().to_dict()
        expected = {
            "link_id", "record_id", "target_type",
            "target_id", "relationship", "created_at",
        }
        assert set(d.keys()) == expected

    def test_no_metadata_field(self):
        r = self._make()
        assert not hasattr(r, "metadata")


# ===================================================================
# RecordSnapshot
# ===================================================================


class TestRecordSnapshot:
    def _make(self, **kw):
        defaults = dict(snapshot_id="snap-1", captured_at=TS)
        defaults.update(kw)
        return RecordSnapshot(**defaults)

    def test_valid_defaults(self):
        r = self._make()
        assert r.snapshot_id == "snap-1"
        assert r.scope_ref_id == ""
        assert r.total_records == 0
        assert r.total_schedules == 0
        assert r.total_holds == 0
        assert r.active_holds == 0
        assert r.total_links == 0
        assert r.total_disposals == 0
        assert r.total_violations == 0

    def test_empty_snapshot_id_rejected(self):
        with pytest.raises(ValueError):
            self._make(snapshot_id="")

    def test_missing_captured_at_rejected(self):
        with pytest.raises(ValueError):
            self._make(captured_at="")

    def test_negative_total_records_rejected(self):
        with pytest.raises(ValueError):
            self._make(total_records=-1)

    def test_negative_total_schedules_rejected(self):
        with pytest.raises(ValueError):
            self._make(total_schedules=-1)

    def test_negative_total_holds_rejected(self):
        with pytest.raises(ValueError):
            self._make(total_holds=-1)

    def test_negative_active_holds_rejected(self):
        with pytest.raises(ValueError):
            self._make(active_holds=-1)

    def test_negative_total_links_rejected(self):
        with pytest.raises(ValueError):
            self._make(total_links=-1)

    def test_negative_total_disposals_rejected(self):
        with pytest.raises(ValueError):
            self._make(total_disposals=-1)

    def test_negative_total_violations_rejected(self):
        with pytest.raises(ValueError):
            self._make(total_violations=-1)

    def test_bool_int_field_rejected(self):
        with pytest.raises(ValueError):
            self._make(total_records=True)

    def test_positive_counts_ok(self):
        r = self._make(
            total_records=10, total_schedules=5, total_holds=3,
            active_holds=2, total_links=7, total_disposals=1,
            total_violations=4,
        )
        assert r.total_records == 10
        assert r.total_schedules == 5
        assert r.total_holds == 3
        assert r.active_holds == 2
        assert r.total_links == 7
        assert r.total_disposals == 1
        assert r.total_violations == 4

    def test_metadata_frozen(self):
        r = self._make(metadata={"k": "v"})
        assert isinstance(r.metadata, MappingProxyType)
        with pytest.raises(TypeError):
            r.metadata["x"] = "y"

    def test_frozen_immutable(self):
        r = self._make()
        with pytest.raises(AttributeError):
            r.snapshot_id = "other"

    def test_to_dict_keys(self):
        d = self._make().to_dict()
        expected = {
            "snapshot_id", "scope_ref_id", "total_records", "total_schedules",
            "total_holds", "active_holds", "total_links", "total_disposals",
            "total_violations", "captured_at", "metadata",
        }
        assert set(d.keys()) == expected

    def test_scope_ref_id_custom(self):
        r = self._make(scope_ref_id="scope-abc")
        assert r.scope_ref_id == "scope-abc"


# ===================================================================
# RecordViolation
# ===================================================================


class TestRecordViolation:
    def _make(self, **kw):
        defaults = dict(
            violation_id="viol-1", record_id="rec-1", tenant_id="t-1",
            operation="delete", detected_at=TS,
        )
        defaults.update(kw)
        return RecordViolation(**defaults)

    def test_valid_defaults(self):
        r = self._make()
        assert r.violation_id == "viol-1"
        assert r.operation == "delete"
        assert r.reason == ""

    def test_empty_violation_id_rejected(self):
        with pytest.raises(ValueError):
            self._make(violation_id="")

    def test_empty_record_id_rejected(self):
        with pytest.raises(ValueError):
            self._make(record_id="")

    def test_empty_tenant_id_rejected(self):
        with pytest.raises(ValueError):
            self._make(tenant_id="")

    def test_empty_operation_rejected(self):
        with pytest.raises(ValueError):
            self._make(operation="")

    def test_whitespace_only_operation_rejected(self):
        with pytest.raises(ValueError):
            self._make(operation="   ")

    def test_missing_detected_at_rejected(self):
        with pytest.raises(ValueError):
            self._make(detected_at="")

    def test_bad_detected_at_rejected(self):
        with pytest.raises(ValueError):
            self._make(detected_at="not-a-date")

    def test_metadata_frozen(self):
        r = self._make(metadata={"k": "v"})
        assert isinstance(r.metadata, MappingProxyType)
        with pytest.raises(TypeError):
            r.metadata["z"] = "w"

    def test_frozen_immutable(self):
        r = self._make()
        with pytest.raises(AttributeError):
            r.violation_id = "other"

    def test_to_dict_keys(self):
        d = self._make().to_dict()
        expected = {
            "violation_id", "record_id", "tenant_id",
            "operation", "reason", "detected_at", "metadata",
        }
        assert set(d.keys()) == expected

    def test_custom_reason(self):
        r = self._make(reason="unauthorized disposal")
        assert r.reason == "unauthorized disposal"


# ===================================================================
# PreservationDecision
# ===================================================================


class TestPreservationDecision:
    def _make(self, **kw):
        defaults = dict(
            decision_id="pres-1", record_id="rec-1", decided_at=TS,
        )
        defaults.update(kw)
        return PreservationDecision(**defaults)

    def test_valid_defaults(self):
        r = self._make()
        assert r.decision_id == "pres-1"
        assert r.preserve is True
        assert r.reason == ""
        assert r.authority is RecordAuthority.SYSTEM

    def test_empty_decision_id_rejected(self):
        with pytest.raises(ValueError):
            self._make(decision_id="")

    def test_empty_record_id_rejected(self):
        with pytest.raises(ValueError):
            self._make(record_id="")

    def test_missing_decided_at_rejected(self):
        with pytest.raises(ValueError):
            self._make(decided_at="")

    def test_preserve_false(self):
        r = self._make(preserve=False)
        assert r.preserve is False

    def test_preserve_non_bool_rejected(self):
        with pytest.raises(ValueError):
            self._make(preserve="yes")

    def test_preserve_int_rejected(self):
        with pytest.raises(ValueError):
            self._make(preserve=1)

    def test_invalid_authority_rejected(self):
        with pytest.raises(ValueError):
            self._make(authority="admin")

    def test_all_authorities(self):
        for auth in RecordAuthority:
            r = self._make(authority=auth)
            assert r.authority is auth

    def test_frozen_immutable(self):
        r = self._make()
        with pytest.raises(AttributeError):
            r.preserve = False

    def test_no_metadata_field(self):
        r = self._make()
        assert not hasattr(r, "metadata")

    def test_to_dict_preserves_enums(self):
        d = self._make().to_dict()
        assert d["authority"] is RecordAuthority.SYSTEM

    def test_to_dict_keys(self):
        d = self._make().to_dict()
        expected = {
            "decision_id", "record_id", "preserve",
            "reason", "authority", "decided_at",
        }
        assert set(d.keys()) == expected

    def test_custom_reason(self):
        r = self._make(reason="legal hold active")
        assert r.reason == "legal hold active"


# ===================================================================
# DisposalDecision
# ===================================================================


class TestDisposalDecision:
    def _make(self, **kw):
        defaults = dict(
            decision_id="disp-1", record_id="rec-1", tenant_id="t-1",
            decided_at=TS,
        )
        defaults.update(kw)
        return DisposalDecision(**defaults)

    def test_valid_defaults(self):
        r = self._make()
        assert r.decision_id == "disp-1"
        assert r.disposition is DisposalDisposition.DENY
        assert r.reason == ""
        assert r.authority is RecordAuthority.SYSTEM

    def test_empty_decision_id_rejected(self):
        with pytest.raises(ValueError):
            self._make(decision_id="")

    def test_empty_record_id_rejected(self):
        with pytest.raises(ValueError):
            self._make(record_id="")

    def test_empty_tenant_id_rejected(self):
        with pytest.raises(ValueError):
            self._make(tenant_id="")

    def test_invalid_disposition_rejected(self):
        with pytest.raises(ValueError):
            self._make(disposition="shred")

    def test_invalid_authority_rejected(self):
        with pytest.raises(ValueError):
            self._make(authority="nobody")

    def test_missing_decided_at_rejected(self):
        with pytest.raises(ValueError):
            self._make(decided_at="")

    def test_all_dispositions(self):
        for dd in DisposalDisposition:
            r = self._make(disposition=dd)
            assert r.disposition is dd

    def test_all_authorities(self):
        for auth in RecordAuthority:
            r = self._make(authority=auth)
            assert r.authority is auth

    def test_metadata_frozen(self):
        r = self._make(metadata={"k": "v"})
        assert isinstance(r.metadata, MappingProxyType)
        with pytest.raises(TypeError):
            r.metadata["x"] = "y"

    def test_frozen_immutable(self):
        r = self._make()
        with pytest.raises(AttributeError):
            r.decision_id = "other"

    def test_to_dict_preserves_enums(self):
        d = self._make().to_dict()
        assert d["disposition"] is DisposalDisposition.DENY
        assert d["authority"] is RecordAuthority.SYSTEM

    def test_to_dict_keys(self):
        d = self._make().to_dict()
        expected = {
            "decision_id", "record_id", "tenant_id",
            "disposition", "reason", "authority", "decided_at", "metadata",
        }
        assert set(d.keys()) == expected

    def test_custom_fields(self):
        r = self._make(
            disposition=DisposalDisposition.ARCHIVE,
            reason="compliance requirement",
            authority=RecordAuthority.COMPLIANCE,
        )
        assert r.disposition is DisposalDisposition.ARCHIVE
        assert r.reason == "compliance requirement"
        assert r.authority is RecordAuthority.COMPLIANCE


# ===================================================================
# RecordsClosureReport
# ===================================================================


class TestRecordsClosureReport:
    def _make(self, **kw):
        defaults = dict(
            report_id="rpt-1", tenant_id="t-1", closed_at=TS,
        )
        defaults.update(kw)
        return RecordsClosureReport(**defaults)

    def test_valid_defaults(self):
        r = self._make()
        assert r.report_id == "rpt-1"
        assert r.tenant_id == "t-1"
        assert r.total_records == 0
        assert r.total_preserved == 0
        assert r.total_disposed == 0
        assert r.total_held == 0
        assert r.total_violations == 0

    def test_empty_report_id_rejected(self):
        with pytest.raises(ValueError):
            self._make(report_id="")

    def test_empty_tenant_id_rejected(self):
        with pytest.raises(ValueError):
            self._make(tenant_id="")

    def test_missing_closed_at_rejected(self):
        with pytest.raises(ValueError):
            self._make(closed_at="")

    def test_negative_total_records_rejected(self):
        with pytest.raises(ValueError):
            self._make(total_records=-1)

    def test_negative_total_preserved_rejected(self):
        with pytest.raises(ValueError):
            self._make(total_preserved=-1)

    def test_negative_total_disposed_rejected(self):
        with pytest.raises(ValueError):
            self._make(total_disposed=-1)

    def test_negative_total_held_rejected(self):
        with pytest.raises(ValueError):
            self._make(total_held=-1)

    def test_negative_total_violations_rejected(self):
        with pytest.raises(ValueError):
            self._make(total_violations=-1)

    def test_bool_int_field_rejected(self):
        with pytest.raises(ValueError):
            self._make(total_records=False)

    def test_positive_counts_ok(self):
        r = self._make(
            total_records=100, total_preserved=50,
            total_disposed=30, total_held=10,
            total_violations=5,
        )
        assert r.total_records == 100
        assert r.total_preserved == 50
        assert r.total_disposed == 30
        assert r.total_held == 10
        assert r.total_violations == 5

    def test_metadata_frozen(self):
        r = self._make(metadata={"k": "v"})
        assert isinstance(r.metadata, MappingProxyType)
        with pytest.raises(TypeError):
            r.metadata["x"] = "y"

    def test_frozen_immutable(self):
        r = self._make()
        with pytest.raises(AttributeError):
            r.report_id = "other"

    def test_to_dict_keys(self):
        d = self._make().to_dict()
        expected = {
            "report_id", "tenant_id", "total_records", "total_preserved",
            "total_disposed", "total_held", "total_violations",
            "closed_at", "metadata",
        }
        assert set(d.keys()) == expected

    def test_to_dict_metadata_thawed(self):
        r = self._make(metadata={"nested": {"a": 1}})
        d = r.to_dict()
        assert isinstance(d["metadata"], dict)


# ===================================================================
# Cross-cutting freeze / thaw / immutability tests
# ===================================================================


class TestFreezeValueSemantics:
    """Tests that freeze_value correctly handles nested structures."""

    def test_list_in_metadata_becomes_tuple(self):
        r = RecordDescriptor(
            record_id="r-1", tenant_id="t-1", title="T",
            created_at=TS, metadata={"tags": ["a", "b"]},
        )
        assert isinstance(r.metadata["tags"], tuple)
        assert r.metadata["tags"] == ("a", "b")

    def test_nested_dict_in_metadata_becomes_mapping_proxy(self):
        r = RecordDescriptor(
            record_id="r-1", tenant_id="t-1", title="T",
            created_at=TS, metadata={"inner": {"x": 1}},
        )
        assert isinstance(r.metadata["inner"], MappingProxyType)
        with pytest.raises(TypeError):
            r.metadata["inner"]["y"] = 2

    def test_deeply_nested_freeze(self):
        r = RecordDescriptor(
            record_id="r-1", tenant_id="t-1", title="T",
            created_at=TS,
            metadata={"level1": {"level2": [1, 2, {"level3": "val"}]}},
        )
        level2 = r.metadata["level1"]["level2"]
        assert isinstance(level2, tuple)
        assert isinstance(level2[2], MappingProxyType)

    def test_thaw_restores_list_from_tuple(self):
        r = RecordDescriptor(
            record_id="r-1", tenant_id="t-1", title="T",
            created_at=TS, metadata={"items": [1, 2, 3]},
        )
        d = r.to_dict()
        assert isinstance(d["metadata"]["items"], list)
        assert d["metadata"]["items"] == [1, 2, 3]

    def test_thaw_restores_dict_from_mapping_proxy(self):
        r = RetentionSchedule(
            schedule_id="s-1", record_id="r-1", tenant_id="t-1",
            created_at=TS, metadata={"inner": {"k": "v"}},
        )
        d = r.to_dict()
        assert isinstance(d["metadata"]["inner"], dict)


class TestCrossCuttingImmutability:
    """Verify frozen=True across all dataclasses."""

    def test_record_descriptor_frozen(self):
        r = RecordDescriptor(
            record_id="r-1", tenant_id="t-1", title="T", created_at=TS,
        )
        with pytest.raises(AttributeError):
            r.record_id = "changed"

    def test_retention_schedule_frozen(self):
        r = RetentionSchedule(
            schedule_id="s-1", record_id="r-1", tenant_id="t-1", created_at=TS,
        )
        with pytest.raises(AttributeError):
            r.retention_days = 999

    def test_legal_hold_record_frozen(self):
        r = LegalHoldRecord(
            hold_id="h-1", record_id="r-1", tenant_id="t-1", placed_at=TS,
        )
        with pytest.raises(AttributeError):
            r.reason = "changed"

    def test_disposition_review_frozen(self):
        r = DispositionReview(
            review_id="rv-1", record_id="r-1", reviewer_id="u-1",
            reviewed_at=TS,
        )
        with pytest.raises(AttributeError):
            r.reason = "changed"

    def test_record_link_frozen(self):
        r = RecordLink(
            link_id="l-1", record_id="r-1", target_type="t",
            target_id="t-1", relationship="rel", created_at=TS,
        )
        with pytest.raises(AttributeError):
            r.relationship = "changed"

    def test_record_snapshot_frozen(self):
        r = RecordSnapshot(snapshot_id="sn-1", captured_at=TS)
        with pytest.raises(AttributeError):
            r.total_records = 999

    def test_record_violation_frozen(self):
        r = RecordViolation(
            violation_id="v-1", record_id="r-1", tenant_id="t-1",
            operation="delete", detected_at=TS,
        )
        with pytest.raises(AttributeError):
            r.reason = "changed"

    def test_preservation_decision_frozen(self):
        r = PreservationDecision(
            decision_id="pd-1", record_id="r-1", decided_at=TS,
        )
        with pytest.raises(AttributeError):
            r.preserve = False

    def test_disposal_decision_frozen(self):
        r = DisposalDecision(
            decision_id="dd-1", record_id="r-1", tenant_id="t-1",
            decided_at=TS,
        )
        with pytest.raises(AttributeError):
            r.reason = "changed"

    def test_records_closure_report_frozen(self):
        r = RecordsClosureReport(
            report_id="rp-1", tenant_id="t-1", closed_at=TS,
        )
        with pytest.raises(AttributeError):
            r.total_records = 999


class TestToDictRoundTrip:
    """Verify to_dict returns proper dicts with enum objects preserved."""

    def test_record_descriptor_round_trip(self):
        r = RecordDescriptor(
            record_id="r-1", tenant_id="t-1", title="T",
            kind=RecordKind.AUDIT, authority=RecordAuthority.COMPLIANCE,
            evidence_grade=EvidenceGrade.DERIVED, created_at=TS,
        )
        d = r.to_dict()
        assert isinstance(d, dict)
        assert d["kind"] is RecordKind.AUDIT
        assert d["authority"] is RecordAuthority.COMPLIANCE
        assert d["evidence_grade"] is EvidenceGrade.DERIVED
        assert d["record_id"] == "r-1"
        assert d["created_at"] == TS

    def test_retention_schedule_round_trip(self):
        r = RetentionSchedule(
            schedule_id="s-1", record_id="r-1", tenant_id="t-1",
            retention_days=90, status=RetentionStatus.HELD,
            disposal_disposition=DisposalDisposition.ARCHIVE,
            created_at=TS,
        )
        d = r.to_dict()
        assert d["retention_days"] == 90
        assert d["status"] is RetentionStatus.HELD
        assert d["disposal_disposition"] is DisposalDisposition.ARCHIVE

    def test_legal_hold_round_trip(self):
        r = LegalHoldRecord(
            hold_id="h-1", record_id="r-1", tenant_id="t-1",
            authority=RecordAuthority.EXECUTIVE,
            status=HoldStatus.RELEASED, placed_at=TS,
        )
        d = r.to_dict()
        assert d["authority"] is RecordAuthority.EXECUTIVE
        assert d["status"] is HoldStatus.RELEASED

    def test_disposition_review_round_trip(self):
        r = DispositionReview(
            review_id="rv-1", record_id="r-1", reviewer_id="u-1",
            decision=DisposalDisposition.TRANSFER, reviewed_at=TS,
        )
        d = r.to_dict()
        assert d["decision"] is DisposalDisposition.TRANSFER

    def test_preservation_decision_round_trip(self):
        r = PreservationDecision(
            decision_id="pd-1", record_id="r-1",
            preserve=False, authority=RecordAuthority.LEGAL,
            decided_at=TS,
        )
        d = r.to_dict()
        assert d["preserve"] is False
        assert d["authority"] is RecordAuthority.LEGAL

    def test_disposal_decision_round_trip(self):
        r = DisposalDecision(
            decision_id="dd-1", record_id="r-1", tenant_id="t-1",
            disposition=DisposalDisposition.ANONYMIZE,
            authority=RecordAuthority.AUTOMATED,
            decided_at=TS,
        )
        d = r.to_dict()
        assert d["disposition"] is DisposalDisposition.ANONYMIZE
        assert d["authority"] is RecordAuthority.AUTOMATED

    def test_record_link_round_trip(self):
        r = RecordLink(
            link_id="l-1", record_id="r-1", target_type="policy",
            target_id="p-1", relationship="governed_by", created_at=TS,
        )
        d = r.to_dict()
        assert d["link_id"] == "l-1"
        assert d["relationship"] == "governed_by"

    def test_record_snapshot_round_trip(self):
        r = RecordSnapshot(
            snapshot_id="sn-1", total_records=42,
            total_violations=3, captured_at=TS,
        )
        d = r.to_dict()
        assert d["total_records"] == 42
        assert d["total_violations"] == 3

    def test_record_violation_round_trip(self):
        r = RecordViolation(
            violation_id="v-1", record_id="r-1", tenant_id="t-1",
            operation="modify", reason="immutable record", detected_at=TS,
        )
        d = r.to_dict()
        assert d["operation"] == "modify"
        assert d["reason"] == "immutable record"

    def test_records_closure_report_round_trip(self):
        r = RecordsClosureReport(
            report_id="rp-1", tenant_id="t-1",
            total_records=100, total_preserved=60,
            total_disposed=20, total_held=15,
            total_violations=5, closed_at=TS,
        )
        d = r.to_dict()
        assert d["total_records"] == 100
        assert d["total_preserved"] == 60


class TestDatetimeValidation:
    """Additional datetime format tests across types."""

    def test_z_suffix_accepted(self):
        r = RecordDescriptor(
            record_id="r-1", tenant_id="t-1", title="T",
            created_at="2025-06-01T12:00:00Z",
        )
        assert r.created_at == "2025-06-01T12:00:00Z"

    def test_garbage_datetime_rejected(self):
        with pytest.raises(ValueError):
            LegalHoldRecord(
                hold_id="h-1", record_id="r-1", tenant_id="t-1",
                placed_at="last_tuesday",
            )

    def test_numeric_datetime_rejected(self):
        with pytest.raises(ValueError):
            RecordViolation(
                violation_id="v-1", record_id="r-1", tenant_id="t-1",
                operation="op", detected_at="12345",
            )


class TestDefaultFailClosed:
    """Verify fail-closed defaults: disposal defaults to DENY."""

    def test_disposition_review_defaults_deny(self):
        r = DispositionReview(
            review_id="rv-1", record_id="r-1", reviewer_id="u-1",
            reviewed_at=TS,
        )
        assert r.decision is DisposalDisposition.DENY

    def test_disposal_decision_defaults_deny(self):
        r = DisposalDecision(
            decision_id="dd-1", record_id="r-1", tenant_id="t-1",
            decided_at=TS,
        )
        assert r.disposition is DisposalDisposition.DENY

    def test_preservation_defaults_true(self):
        r = PreservationDecision(
            decision_id="pd-1", record_id="r-1", decided_at=TS,
        )
        assert r.preserve is True

    def test_legal_hold_defaults_active(self):
        r = LegalHoldRecord(
            hold_id="h-1", record_id="r-1", tenant_id="t-1",
            placed_at=TS,
        )
        assert r.status is HoldStatus.ACTIVE

    def test_legal_hold_default_authority_is_legal(self):
        r = LegalHoldRecord(
            hold_id="h-1", record_id="r-1", tenant_id="t-1",
            placed_at=TS,
        )
        assert r.authority is RecordAuthority.LEGAL

    def test_retention_schedule_defaults_active(self):
        r = RetentionSchedule(
            schedule_id="s-1", record_id="r-1", tenant_id="t-1",
            created_at=TS,
        )
        assert r.status is RetentionStatus.ACTIVE

    def test_retention_schedule_default_disposal_is_delete(self):
        r = RetentionSchedule(
            schedule_id="s-1", record_id="r-1", tenant_id="t-1",
            created_at=TS,
        )
        assert r.disposal_disposition is DisposalDisposition.DELETE
