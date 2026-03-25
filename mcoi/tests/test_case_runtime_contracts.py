"""Contract-level tests for case_runtime contracts.

Covers all 7 enums, 10 dataclasses, freeze/thaw semantics, to_dict round-trips,
immutability, and validation edge cases.  Does NOT test to_json (known enum
serialization issue).
"""

from __future__ import annotations

from types import MappingProxyType

import pytest

from mcoi_runtime.contracts.case_runtime import (
    CaseAssignment,
    CaseClosureDisposition,
    CaseClosureReport,
    CaseDecision,
    CaseKind,
    CaseRecord,
    CaseSeverity,
    CaseSnapshot,
    CaseStatus,
    CaseViolation,
    EvidenceCollection,
    EvidenceItem,
    EvidenceStatus,
    FindingRecord,
    FindingSeverity,
    ReviewDisposition,
    ReviewRecord,
)

TS = "2025-06-01T12:00:00+00:00"
TS2 = "2025-07-01T12:00:00+00:00"


# ===================================================================
# Enum completeness
# ===================================================================


class TestCaseStatusEnum:
    def test_member_count(self):
        assert len(CaseStatus) == 6

    def test_all_members(self):
        expected = {
            "OPEN", "IN_PROGRESS", "UNDER_REVIEW",
            "PENDING_DECISION", "CLOSED", "ESCALATED",
        }
        assert {m.name for m in CaseStatus} == expected

    def test_values(self):
        assert CaseStatus.OPEN.value == "open"
        assert CaseStatus.IN_PROGRESS.value == "in_progress"
        assert CaseStatus.ESCALATED.value == "escalated"


class TestCaseSeverityEnum:
    def test_member_count(self):
        assert len(CaseSeverity) == 4

    def test_all_members(self):
        expected = {"LOW", "MEDIUM", "HIGH", "CRITICAL"}
        assert {m.name for m in CaseSeverity} == expected

    def test_values(self):
        assert CaseSeverity.LOW.value == "low"
        assert CaseSeverity.CRITICAL.value == "critical"


class TestCaseKindEnum:
    def test_member_count(self):
        assert len(CaseKind) == 7

    def test_all_members(self):
        expected = {
            "INCIDENT", "COMPLIANCE", "AUDIT", "SECURITY",
            "OPERATIONAL", "LEGAL", "FAULT_ANALYSIS",
        }
        assert {m.name for m in CaseKind} == expected

    def test_values(self):
        assert CaseKind.INCIDENT.value == "incident"
        assert CaseKind.FAULT_ANALYSIS.value == "fault_analysis"


class TestEvidenceStatusEnum:
    def test_member_count(self):
        assert len(EvidenceStatus) == 5

    def test_all_members(self):
        expected = {"PENDING", "ADMITTED", "REVIEWED", "CHALLENGED", "EXCLUDED"}
        assert {m.name for m in EvidenceStatus} == expected

    def test_values(self):
        assert EvidenceStatus.PENDING.value == "pending"
        assert EvidenceStatus.EXCLUDED.value == "excluded"


class TestReviewDispositionEnum:
    def test_member_count(self):
        assert len(ReviewDisposition) == 5

    def test_all_members(self):
        expected = {
            "REQUIRES_REVIEW", "ACCEPTED", "REJECTED",
            "INCONCLUSIVE", "ESCALATED",
        }
        assert {m.name for m in ReviewDisposition} == expected

    def test_values(self):
        assert ReviewDisposition.REQUIRES_REVIEW.value == "requires_review"
        assert ReviewDisposition.ESCALATED.value == "escalated"


class TestFindingSeverityEnum:
    def test_member_count(self):
        assert len(FindingSeverity) == 5

    def test_all_members(self):
        expected = {"INFORMATIONAL", "LOW", "MEDIUM", "HIGH", "CRITICAL"}
        assert {m.name for m in FindingSeverity} == expected

    def test_values(self):
        assert FindingSeverity.INFORMATIONAL.value == "informational"
        assert FindingSeverity.CRITICAL.value == "critical"


class TestCaseClosureDispositionEnum:
    def test_member_count(self):
        assert len(CaseClosureDisposition) == 5

    def test_all_members(self):
        expected = {"RESOLVED", "UNRESOLVED", "REMEDIATED", "ESCALATED", "DISMISSED"}
        assert {m.name for m in CaseClosureDisposition} == expected

    def test_values(self):
        assert CaseClosureDisposition.RESOLVED.value == "resolved"
        assert CaseClosureDisposition.DISMISSED.value == "dismissed"


# ===================================================================
# CaseRecord
# ===================================================================


class TestCaseRecord:
    def _make(self, **kw):
        defaults = dict(
            case_id="case-1", tenant_id="t-1", title="Case Title",
            opened_by="user-1", opened_at=TS,
        )
        defaults.update(kw)
        return CaseRecord(**defaults)

    def test_valid_defaults(self):
        r = self._make()
        assert r.case_id == "case-1"
        assert r.tenant_id == "t-1"
        assert r.kind == CaseKind.INCIDENT
        assert r.severity == CaseSeverity.MEDIUM
        assert r.status == CaseStatus.OPEN
        assert r.title == "Case Title"
        assert r.description == ""
        assert r.opened_by == "user-1"
        assert r.opened_at == TS
        assert r.closed_at == ""

    def test_empty_case_id_rejected(self):
        with pytest.raises(ValueError):
            self._make(case_id="")

    def test_whitespace_case_id_rejected(self):
        with pytest.raises(ValueError):
            self._make(case_id="   ")

    def test_empty_tenant_id_rejected(self):
        with pytest.raises(ValueError):
            self._make(tenant_id="")

    def test_empty_title_rejected(self):
        with pytest.raises(ValueError):
            self._make(title="")

    def test_whitespace_title_rejected(self):
        with pytest.raises(ValueError):
            self._make(title="  \t ")

    def test_empty_opened_by_rejected(self):
        with pytest.raises(ValueError):
            self._make(opened_by="")

    def test_invalid_kind_rejected(self):
        with pytest.raises(ValueError):
            self._make(kind="not_a_kind")

    def test_invalid_severity_rejected(self):
        with pytest.raises(ValueError):
            self._make(severity="extreme")

    def test_invalid_status_rejected(self):
        with pytest.raises(ValueError):
            self._make(status="unknown")

    def test_bad_datetime_rejected(self):
        with pytest.raises(ValueError):
            self._make(opened_at="not-a-date")

    def test_numeric_datetime_rejected(self):
        with pytest.raises((ValueError, TypeError)):
            self._make(opened_at=12345)

    def test_empty_datetime_rejected(self):
        with pytest.raises(ValueError):
            self._make(opened_at="")

    def test_all_kinds(self):
        for kind in CaseKind:
            r = self._make(kind=kind)
            assert r.kind is kind

    def test_all_severities(self):
        for sev in CaseSeverity:
            r = self._make(severity=sev)
            assert r.severity is sev

    def test_all_statuses(self):
        for st in CaseStatus:
            r = self._make(status=st)
            assert r.status is st

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
        assert d["kind"] is CaseKind.INCIDENT
        assert d["severity"] is CaseSeverity.MEDIUM
        assert d["status"] is CaseStatus.OPEN

    def test_to_dict_keys(self):
        r = self._make()
        d = r.to_dict()
        expected_keys = {
            "case_id", "tenant_id", "kind", "severity", "status",
            "title", "description", "opened_by", "opened_at",
            "closed_at", "metadata",
        }
        assert set(d.keys()) == expected_keys

    def test_fail_closed_default_status(self):
        """CaseStatus default is OPEN (fail-closed)."""
        r = self._make()
        assert r.status is CaseStatus.OPEN


# ===================================================================
# CaseAssignment
# ===================================================================


class TestCaseAssignment:
    def _make(self, **kw):
        defaults = dict(
            assignment_id="asgn-1", case_id="case-1",
            assignee_id="user-1", role="investigator",
            assigned_at=TS,
        )
        defaults.update(kw)
        return CaseAssignment(**defaults)

    def test_valid_defaults(self):
        r = self._make()
        assert r.assignment_id == "asgn-1"
        assert r.case_id == "case-1"
        assert r.assignee_id == "user-1"
        assert r.role == "investigator"
        assert r.assigned_at == TS

    def test_empty_assignment_id_rejected(self):
        with pytest.raises(ValueError):
            self._make(assignment_id="")

    def test_whitespace_assignment_id_rejected(self):
        with pytest.raises(ValueError):
            self._make(assignment_id="   ")

    def test_empty_case_id_rejected(self):
        with pytest.raises(ValueError):
            self._make(case_id="")

    def test_empty_assignee_id_rejected(self):
        with pytest.raises(ValueError):
            self._make(assignee_id="")

    def test_empty_role_rejected(self):
        with pytest.raises(ValueError):
            self._make(role="")

    def test_bad_datetime_rejected(self):
        with pytest.raises(ValueError):
            self._make(assigned_at="garbage")

    def test_numeric_datetime_rejected(self):
        with pytest.raises((ValueError, TypeError)):
            self._make(assigned_at=99999)

    def test_empty_datetime_rejected(self):
        with pytest.raises(ValueError):
            self._make(assigned_at="")

    def test_metadata_frozen(self):
        r = self._make(metadata={"x": 1})
        assert isinstance(r.metadata, MappingProxyType)
        with pytest.raises(TypeError):
            r.metadata["y"] = 2

    def test_metadata_empty_default(self):
        r = self._make()
        assert isinstance(r.metadata, MappingProxyType)
        assert len(r.metadata) == 0

    def test_frozen_immutable(self):
        r = self._make()
        with pytest.raises(AttributeError):
            r.role = "reviewer"

    def test_to_dict_keys(self):
        r = self._make()
        d = r.to_dict()
        expected_keys = {
            "assignment_id", "case_id", "assignee_id", "role",
            "assigned_at", "metadata",
        }
        assert set(d.keys()) == expected_keys


# ===================================================================
# EvidenceItem
# ===================================================================


class TestEvidenceItem:
    def _make(self, **kw):
        defaults = dict(
            evidence_id="ev-1", case_id="case-1",
            source_type="log", source_id="src-1",
            title="Evidence Title", submitted_by="user-1",
            submitted_at=TS,
        )
        defaults.update(kw)
        return EvidenceItem(**defaults)

    def test_valid_defaults(self):
        r = self._make()
        assert r.evidence_id == "ev-1"
        assert r.case_id == "case-1"
        assert r.source_type == "log"
        assert r.source_id == "src-1"
        assert r.status == EvidenceStatus.PENDING
        assert r.title == "Evidence Title"
        assert r.description == ""
        assert r.submitted_by == "user-1"
        assert r.submitted_at == TS

    def test_empty_evidence_id_rejected(self):
        with pytest.raises(ValueError):
            self._make(evidence_id="")

    def test_whitespace_evidence_id_rejected(self):
        with pytest.raises(ValueError):
            self._make(evidence_id="  ")

    def test_empty_case_id_rejected(self):
        with pytest.raises(ValueError):
            self._make(case_id="")

    def test_empty_source_type_rejected(self):
        with pytest.raises(ValueError):
            self._make(source_type="")

    def test_empty_source_id_rejected(self):
        with pytest.raises(ValueError):
            self._make(source_id="")

    def test_empty_title_rejected(self):
        with pytest.raises(ValueError):
            self._make(title="")

    def test_empty_submitted_by_rejected(self):
        with pytest.raises(ValueError):
            self._make(submitted_by="")

    def test_invalid_status_rejected(self):
        with pytest.raises(ValueError):
            self._make(status="not_valid")

    def test_bad_datetime_rejected(self):
        with pytest.raises(ValueError):
            self._make(submitted_at="xyz")

    def test_numeric_datetime_rejected(self):
        with pytest.raises((ValueError, TypeError)):
            self._make(submitted_at=42)

    def test_empty_datetime_rejected(self):
        with pytest.raises(ValueError):
            self._make(submitted_at="")

    def test_all_statuses(self):
        for st in EvidenceStatus:
            r = self._make(status=st)
            assert r.status is st

    def test_fail_closed_default_status(self):
        """EvidenceStatus default is PENDING (fail-closed)."""
        r = self._make()
        assert r.status is EvidenceStatus.PENDING

    def test_metadata_frozen(self):
        r = self._make(metadata={"a": "b"})
        assert isinstance(r.metadata, MappingProxyType)
        with pytest.raises(TypeError):
            r.metadata["c"] = "d"

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
        assert d["status"] is EvidenceStatus.PENDING

    def test_to_dict_keys(self):
        r = self._make()
        d = r.to_dict()
        expected_keys = {
            "evidence_id", "case_id", "source_type", "source_id",
            "status", "title", "description", "submitted_by",
            "submitted_at", "metadata",
        }
        assert set(d.keys()) == expected_keys


# ===================================================================
# EvidenceCollection
# ===================================================================


class TestEvidenceCollection:
    def _make(self, **kw):
        defaults = dict(
            collection_id="col-1", case_id="case-1",
            title="Collection Title", created_at=TS,
        )
        defaults.update(kw)
        return EvidenceCollection(**defaults)

    def test_valid_defaults(self):
        r = self._make()
        assert r.collection_id == "col-1"
        assert r.case_id == "case-1"
        assert r.title == "Collection Title"
        assert r.evidence_ids == ()
        assert r.created_at == TS

    def test_evidence_ids_as_tuple(self):
        r = self._make(evidence_ids=("ev-1", "ev-2"))
        assert r.evidence_ids == ("ev-1", "ev-2")
        assert isinstance(r.evidence_ids, tuple)

    def test_evidence_ids_list_converted_to_tuple(self):
        r = self._make(evidence_ids=["ev-1", "ev-2"])
        assert r.evidence_ids == ("ev-1", "ev-2")
        assert isinstance(r.evidence_ids, tuple)

    def test_empty_collection_id_rejected(self):
        with pytest.raises(ValueError):
            self._make(collection_id="")

    def test_whitespace_collection_id_rejected(self):
        with pytest.raises(ValueError):
            self._make(collection_id="  \n ")

    def test_empty_case_id_rejected(self):
        with pytest.raises(ValueError):
            self._make(case_id="")

    def test_empty_title_rejected(self):
        with pytest.raises(ValueError):
            self._make(title="")

    def test_bad_datetime_rejected(self):
        with pytest.raises(ValueError):
            self._make(created_at="nope")

    def test_numeric_datetime_rejected(self):
        with pytest.raises((ValueError, TypeError)):
            self._make(created_at=100)

    def test_empty_datetime_rejected(self):
        with pytest.raises(ValueError):
            self._make(created_at="")

    def test_metadata_frozen(self):
        r = self._make(metadata={"x": "y"})
        assert isinstance(r.metadata, MappingProxyType)
        with pytest.raises(TypeError):
            r.metadata["z"] = "w"

    def test_metadata_empty_default(self):
        r = self._make()
        assert isinstance(r.metadata, MappingProxyType)
        assert len(r.metadata) == 0

    def test_frozen_immutable(self):
        r = self._make()
        with pytest.raises(AttributeError):
            r.title = "changed"

    def test_to_dict_keys(self):
        r = self._make()
        d = r.to_dict()
        expected_keys = {
            "collection_id", "case_id", "title",
            "evidence_ids", "created_at", "metadata",
        }
        assert set(d.keys()) == expected_keys


# ===================================================================
# ReviewRecord
# ===================================================================


class TestReviewRecord:
    def _make(self, **kw):
        defaults = dict(
            review_id="rev-1", case_id="case-1",
            evidence_id="ev-1", reviewer_id="user-1",
            reviewed_at=TS,
        )
        defaults.update(kw)
        return ReviewRecord(**defaults)

    def test_valid_defaults(self):
        r = self._make()
        assert r.review_id == "rev-1"
        assert r.case_id == "case-1"
        assert r.evidence_id == "ev-1"
        assert r.reviewer_id == "user-1"
        assert r.disposition == ReviewDisposition.REQUIRES_REVIEW
        assert r.notes == ""
        assert r.reviewed_at == TS

    def test_empty_review_id_rejected(self):
        with pytest.raises(ValueError):
            self._make(review_id="")

    def test_whitespace_review_id_rejected(self):
        with pytest.raises(ValueError):
            self._make(review_id="   ")

    def test_empty_case_id_rejected(self):
        with pytest.raises(ValueError):
            self._make(case_id="")

    def test_empty_evidence_id_rejected(self):
        with pytest.raises(ValueError):
            self._make(evidence_id="")

    def test_empty_reviewer_id_rejected(self):
        with pytest.raises(ValueError):
            self._make(reviewer_id="")

    def test_invalid_disposition_rejected(self):
        with pytest.raises(ValueError):
            self._make(disposition="approved")

    def test_bad_datetime_rejected(self):
        with pytest.raises(ValueError):
            self._make(reviewed_at="bad-date")

    def test_numeric_datetime_rejected(self):
        with pytest.raises((ValueError, TypeError)):
            self._make(reviewed_at=0)

    def test_empty_datetime_rejected(self):
        with pytest.raises(ValueError):
            self._make(reviewed_at="")

    def test_all_dispositions(self):
        for disp in ReviewDisposition:
            r = self._make(disposition=disp)
            assert r.disposition is disp

    def test_fail_closed_default_disposition(self):
        """ReviewDisposition default is REQUIRES_REVIEW (fail-closed)."""
        r = self._make()
        assert r.disposition is ReviewDisposition.REQUIRES_REVIEW

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
            r.notes = "changed"

    def test_to_dict_preserves_enums(self):
        r = self._make()
        d = r.to_dict()
        assert d["disposition"] is ReviewDisposition.REQUIRES_REVIEW

    def test_to_dict_keys(self):
        r = self._make()
        d = r.to_dict()
        expected_keys = {
            "review_id", "case_id", "evidence_id", "reviewer_id",
            "disposition", "notes", "reviewed_at", "metadata",
        }
        assert set(d.keys()) == expected_keys


# ===================================================================
# FindingRecord
# ===================================================================


class TestFindingRecord:
    def _make(self, **kw):
        defaults = dict(
            finding_id="find-1", case_id="case-1",
            title="Finding Title", found_at=TS,
        )
        defaults.update(kw)
        return FindingRecord(**defaults)

    def test_valid_defaults(self):
        r = self._make()
        assert r.finding_id == "find-1"
        assert r.case_id == "case-1"
        assert r.severity == FindingSeverity.INFORMATIONAL
        assert r.title == "Finding Title"
        assert r.description == ""
        assert r.evidence_ids == ()
        assert r.remediation == ""
        assert r.found_at == TS

    def test_empty_finding_id_rejected(self):
        with pytest.raises(ValueError):
            self._make(finding_id="")

    def test_whitespace_finding_id_rejected(self):
        with pytest.raises(ValueError):
            self._make(finding_id="  ")

    def test_empty_case_id_rejected(self):
        with pytest.raises(ValueError):
            self._make(case_id="")

    def test_empty_title_rejected(self):
        with pytest.raises(ValueError):
            self._make(title="")

    def test_invalid_severity_rejected(self):
        with pytest.raises(ValueError):
            self._make(severity="extreme")

    def test_bad_datetime_rejected(self):
        with pytest.raises(ValueError):
            self._make(found_at="garbage")

    def test_numeric_datetime_rejected(self):
        with pytest.raises((ValueError, TypeError)):
            self._make(found_at=9999)

    def test_empty_datetime_rejected(self):
        with pytest.raises(ValueError):
            self._make(found_at="")

    def test_evidence_ids_as_tuple(self):
        r = self._make(evidence_ids=("ev-1", "ev-2"))
        assert r.evidence_ids == ("ev-1", "ev-2")
        assert isinstance(r.evidence_ids, tuple)

    def test_evidence_ids_list_converted_to_tuple(self):
        r = self._make(evidence_ids=["ev-1"])
        assert r.evidence_ids == ("ev-1",)
        assert isinstance(r.evidence_ids, tuple)

    def test_all_severities(self):
        for sev in FindingSeverity:
            r = self._make(severity=sev)
            assert r.severity is sev

    def test_metadata_frozen(self):
        r = self._make(metadata={"a": 1})
        assert isinstance(r.metadata, MappingProxyType)
        with pytest.raises(TypeError):
            r.metadata["b"] = 2

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
        assert d["severity"] is FindingSeverity.INFORMATIONAL

    def test_to_dict_keys(self):
        r = self._make()
        d = r.to_dict()
        expected_keys = {
            "finding_id", "case_id", "severity", "title",
            "description", "evidence_ids", "remediation",
            "found_at", "metadata",
        }
        assert set(d.keys()) == expected_keys


# ===================================================================
# CaseDecision
# ===================================================================


class TestCaseDecision:
    def _make(self, **kw):
        defaults = dict(
            decision_id="dec-1", case_id="case-1",
            decided_by="user-1", decided_at=TS,
        )
        defaults.update(kw)
        return CaseDecision(**defaults)

    def test_valid_defaults(self):
        r = self._make()
        assert r.decision_id == "dec-1"
        assert r.case_id == "case-1"
        assert r.disposition == CaseClosureDisposition.UNRESOLVED
        assert r.decided_by == "user-1"
        assert r.reason == ""
        assert r.decided_at == TS

    def test_empty_decision_id_rejected(self):
        with pytest.raises(ValueError):
            self._make(decision_id="")

    def test_whitespace_decision_id_rejected(self):
        with pytest.raises(ValueError):
            self._make(decision_id="   ")

    def test_empty_case_id_rejected(self):
        with pytest.raises(ValueError):
            self._make(case_id="")

    def test_empty_decided_by_rejected(self):
        with pytest.raises(ValueError):
            self._make(decided_by="")

    def test_invalid_disposition_rejected(self):
        with pytest.raises(ValueError):
            self._make(disposition="done")

    def test_bad_datetime_rejected(self):
        with pytest.raises(ValueError):
            self._make(decided_at="bad")

    def test_numeric_datetime_rejected(self):
        with pytest.raises((ValueError, TypeError)):
            self._make(decided_at=1234)

    def test_empty_datetime_rejected(self):
        with pytest.raises(ValueError):
            self._make(decided_at="")

    def test_all_dispositions(self):
        for disp in CaseClosureDisposition:
            r = self._make(disposition=disp)
            assert r.disposition is disp

    def test_fail_closed_default_disposition(self):
        """CaseClosureDisposition default is UNRESOLVED (fail-closed)."""
        r = self._make()
        assert r.disposition is CaseClosureDisposition.UNRESOLVED

    def test_metadata_frozen(self):
        r = self._make(metadata={"reason": "test"})
        assert isinstance(r.metadata, MappingProxyType)
        with pytest.raises(TypeError):
            r.metadata["extra"] = "val"

    def test_metadata_empty_default(self):
        r = self._make()
        assert isinstance(r.metadata, MappingProxyType)
        assert len(r.metadata) == 0

    def test_frozen_immutable(self):
        r = self._make()
        with pytest.raises(AttributeError):
            r.reason = "changed"

    def test_to_dict_preserves_enums(self):
        r = self._make()
        d = r.to_dict()
        assert d["disposition"] is CaseClosureDisposition.UNRESOLVED

    def test_to_dict_keys(self):
        r = self._make()
        d = r.to_dict()
        expected_keys = {
            "decision_id", "case_id", "disposition",
            "decided_by", "reason", "decided_at", "metadata",
        }
        assert set(d.keys()) == expected_keys


# ===================================================================
# CaseSnapshot
# ===================================================================


class TestCaseSnapshot:
    def _make(self, **kw):
        defaults = dict(
            snapshot_id="snap-1", captured_at=TS,
        )
        defaults.update(kw)
        return CaseSnapshot(**defaults)

    def test_valid_defaults(self):
        r = self._make()
        assert r.snapshot_id == "snap-1"
        assert r.scope_ref_id == ""
        assert r.total_cases == 0
        assert r.open_cases == 0
        assert r.total_evidence == 0
        assert r.total_reviews == 0
        assert r.total_findings == 0
        assert r.total_decisions == 0
        assert r.total_violations == 0
        assert r.captured_at == TS

    def test_empty_snapshot_id_rejected(self):
        with pytest.raises(ValueError):
            self._make(snapshot_id="")

    def test_whitespace_snapshot_id_rejected(self):
        with pytest.raises(ValueError):
            self._make(snapshot_id="  ")

    def test_negative_total_cases_rejected(self):
        with pytest.raises(ValueError):
            self._make(total_cases=-1)

    def test_negative_open_cases_rejected(self):
        with pytest.raises(ValueError):
            self._make(open_cases=-1)

    def test_negative_total_evidence_rejected(self):
        with pytest.raises(ValueError):
            self._make(total_evidence=-1)

    def test_negative_total_reviews_rejected(self):
        with pytest.raises(ValueError):
            self._make(total_reviews=-1)

    def test_negative_total_findings_rejected(self):
        with pytest.raises(ValueError):
            self._make(total_findings=-1)

    def test_negative_total_decisions_rejected(self):
        with pytest.raises(ValueError):
            self._make(total_decisions=-1)

    def test_negative_total_violations_rejected(self):
        with pytest.raises(ValueError):
            self._make(total_violations=-1)

    def test_positive_ints_accepted(self):
        r = self._make(
            total_cases=5, open_cases=3, total_evidence=10,
            total_reviews=7, total_findings=2, total_decisions=1,
            total_violations=0,
        )
        assert r.total_cases == 5
        assert r.open_cases == 3
        assert r.total_evidence == 10
        assert r.total_reviews == 7
        assert r.total_findings == 2
        assert r.total_decisions == 1
        assert r.total_violations == 0

    def test_bad_datetime_rejected(self):
        with pytest.raises(ValueError):
            self._make(captured_at="nope")

    def test_numeric_datetime_rejected(self):
        with pytest.raises((ValueError, TypeError)):
            self._make(captured_at=555)

    def test_empty_datetime_rejected(self):
        with pytest.raises(ValueError):
            self._make(captured_at="")

    def test_metadata_frozen(self):
        r = self._make(metadata={"env": "prod"})
        assert isinstance(r.metadata, MappingProxyType)
        with pytest.raises(TypeError):
            r.metadata["new"] = "val"

    def test_metadata_empty_default(self):
        r = self._make()
        assert isinstance(r.metadata, MappingProxyType)
        assert len(r.metadata) == 0

    def test_frozen_immutable(self):
        r = self._make()
        with pytest.raises(AttributeError):
            r.total_cases = 99

    def test_to_dict_keys(self):
        r = self._make()
        d = r.to_dict()
        expected_keys = {
            "snapshot_id", "scope_ref_id", "total_cases", "open_cases",
            "total_evidence", "total_reviews", "total_findings",
            "total_decisions", "total_violations", "captured_at", "metadata",
        }
        assert set(d.keys()) == expected_keys


# ===================================================================
# CaseViolation
# ===================================================================


class TestCaseViolation:
    def _make(self, **kw):
        defaults = dict(
            violation_id="viol-1", case_id="case-1",
            tenant_id="t-1", operation="delete",
            detected_at=TS,
        )
        defaults.update(kw)
        return CaseViolation(**defaults)

    def test_valid_defaults(self):
        r = self._make()
        assert r.violation_id == "viol-1"
        assert r.case_id == "case-1"
        assert r.tenant_id == "t-1"
        assert r.operation == "delete"
        assert r.reason == ""
        assert r.detected_at == TS

    def test_empty_violation_id_rejected(self):
        with pytest.raises(ValueError):
            self._make(violation_id="")

    def test_whitespace_violation_id_rejected(self):
        with pytest.raises(ValueError):
            self._make(violation_id="  ")

    def test_empty_case_id_rejected(self):
        with pytest.raises(ValueError):
            self._make(case_id="")

    def test_empty_tenant_id_rejected(self):
        with pytest.raises(ValueError):
            self._make(tenant_id="")

    def test_empty_operation_rejected(self):
        with pytest.raises(ValueError):
            self._make(operation="")

    def test_whitespace_operation_rejected(self):
        with pytest.raises(ValueError):
            self._make(operation="   ")

    def test_bad_datetime_rejected(self):
        with pytest.raises(ValueError):
            self._make(detected_at="nope")

    def test_numeric_datetime_rejected(self):
        with pytest.raises((ValueError, TypeError)):
            self._make(detected_at=777)

    def test_empty_datetime_rejected(self):
        with pytest.raises(ValueError):
            self._make(detected_at="")

    def test_metadata_frozen(self):
        r = self._make(metadata={"source": "audit"})
        assert isinstance(r.metadata, MappingProxyType)
        with pytest.raises(TypeError):
            r.metadata["x"] = "y"

    def test_metadata_empty_default(self):
        r = self._make()
        assert isinstance(r.metadata, MappingProxyType)
        assert len(r.metadata) == 0

    def test_frozen_immutable(self):
        r = self._make()
        with pytest.raises(AttributeError):
            r.operation = "update"

    def test_to_dict_keys(self):
        r = self._make()
        d = r.to_dict()
        expected_keys = {
            "violation_id", "case_id", "tenant_id",
            "operation", "reason", "detected_at", "metadata",
        }
        assert set(d.keys()) == expected_keys


# ===================================================================
# CaseClosureReport
# ===================================================================


class TestCaseClosureReport:
    def _make(self, **kw):
        defaults = dict(
            report_id="rpt-1", case_id="case-1",
            tenant_id="t-1", closed_at=TS,
        )
        defaults.update(kw)
        return CaseClosureReport(**defaults)

    def test_valid_defaults(self):
        r = self._make()
        assert r.report_id == "rpt-1"
        assert r.case_id == "case-1"
        assert r.tenant_id == "t-1"
        assert r.disposition == CaseClosureDisposition.UNRESOLVED
        assert r.total_evidence == 0
        assert r.total_reviews == 0
        assert r.total_findings == 0
        assert r.total_violations == 0
        assert r.closed_at == TS

    def test_empty_report_id_rejected(self):
        with pytest.raises(ValueError):
            self._make(report_id="")

    def test_whitespace_report_id_rejected(self):
        with pytest.raises(ValueError):
            self._make(report_id="  ")

    def test_empty_case_id_rejected(self):
        with pytest.raises(ValueError):
            self._make(case_id="")

    def test_empty_tenant_id_rejected(self):
        with pytest.raises(ValueError):
            self._make(tenant_id="")

    def test_invalid_disposition_rejected(self):
        with pytest.raises(ValueError):
            self._make(disposition="finished")

    def test_negative_total_evidence_rejected(self):
        with pytest.raises(ValueError):
            self._make(total_evidence=-1)

    def test_negative_total_reviews_rejected(self):
        with pytest.raises(ValueError):
            self._make(total_reviews=-1)

    def test_negative_total_findings_rejected(self):
        with pytest.raises(ValueError):
            self._make(total_findings=-1)

    def test_negative_total_violations_rejected(self):
        with pytest.raises(ValueError):
            self._make(total_violations=-1)

    def test_positive_ints_accepted(self):
        r = self._make(
            total_evidence=10, total_reviews=5,
            total_findings=3, total_violations=1,
        )
        assert r.total_evidence == 10
        assert r.total_reviews == 5
        assert r.total_findings == 3
        assert r.total_violations == 1

    def test_bad_datetime_rejected(self):
        with pytest.raises(ValueError):
            self._make(closed_at="bad")

    def test_numeric_datetime_rejected(self):
        with pytest.raises((ValueError, TypeError)):
            self._make(closed_at=123)

    def test_empty_datetime_rejected(self):
        with pytest.raises(ValueError):
            self._make(closed_at="")

    def test_all_dispositions(self):
        for disp in CaseClosureDisposition:
            r = self._make(disposition=disp)
            assert r.disposition is disp

    def test_fail_closed_default_disposition(self):
        """CaseClosureDisposition default is UNRESOLVED (fail-closed)."""
        r = self._make()
        assert r.disposition is CaseClosureDisposition.UNRESOLVED

    def test_metadata_frozen(self):
        r = self._make(metadata={"summary": "ok"})
        assert isinstance(r.metadata, MappingProxyType)
        with pytest.raises(TypeError):
            r.metadata["extra"] = "val"

    def test_metadata_empty_default(self):
        r = self._make()
        assert isinstance(r.metadata, MappingProxyType)
        assert len(r.metadata) == 0

    def test_frozen_immutable(self):
        r = self._make()
        with pytest.raises(AttributeError):
            r.total_evidence = 99

    def test_to_dict_preserves_enums(self):
        r = self._make()
        d = r.to_dict()
        assert d["disposition"] is CaseClosureDisposition.UNRESOLVED

    def test_to_dict_keys(self):
        r = self._make()
        d = r.to_dict()
        expected_keys = {
            "report_id", "case_id", "tenant_id", "disposition",
            "total_evidence", "total_reviews", "total_findings",
            "total_violations", "closed_at", "metadata",
        }
        assert set(d.keys()) == expected_keys


# ===================================================================
# Cross-cutting immutability
# ===================================================================


class TestCrossCuttingImmutability:
    """Verify that all dataclasses are truly frozen."""

    def test_case_record_immutable(self):
        r = CaseRecord(
            case_id="c-1", tenant_id="t-1", title="T",
            opened_by="u-1", opened_at=TS,
        )
        with pytest.raises(AttributeError):
            r.case_id = "c-2"

    def test_case_assignment_immutable(self):
        r = CaseAssignment(
            assignment_id="a-1", case_id="c-1",
            assignee_id="u-1", role="lead", assigned_at=TS,
        )
        with pytest.raises(AttributeError):
            r.assignment_id = "a-2"

    def test_evidence_item_immutable(self):
        r = EvidenceItem(
            evidence_id="e-1", case_id="c-1",
            source_type="log", source_id="s-1",
            title="T", submitted_by="u-1", submitted_at=TS,
        )
        with pytest.raises(AttributeError):
            r.evidence_id = "e-2"

    def test_evidence_collection_immutable(self):
        r = EvidenceCollection(
            collection_id="col-1", case_id="c-1",
            title="T", created_at=TS,
        )
        with pytest.raises(AttributeError):
            r.collection_id = "col-2"

    def test_review_record_immutable(self):
        r = ReviewRecord(
            review_id="r-1", case_id="c-1",
            evidence_id="e-1", reviewer_id="u-1",
            reviewed_at=TS,
        )
        with pytest.raises(AttributeError):
            r.review_id = "r-2"

    def test_finding_record_immutable(self):
        r = FindingRecord(
            finding_id="f-1", case_id="c-1",
            title="T", found_at=TS,
        )
        with pytest.raises(AttributeError):
            r.finding_id = "f-2"

    def test_case_decision_immutable(self):
        r = CaseDecision(
            decision_id="d-1", case_id="c-1",
            decided_by="u-1", decided_at=TS,
        )
        with pytest.raises(AttributeError):
            r.decision_id = "d-2"

    def test_case_snapshot_immutable(self):
        r = CaseSnapshot(snapshot_id="s-1", captured_at=TS)
        with pytest.raises(AttributeError):
            r.snapshot_id = "s-2"

    def test_case_violation_immutable(self):
        r = CaseViolation(
            violation_id="v-1", case_id="c-1",
            tenant_id="t-1", operation="op",
            detected_at=TS,
        )
        with pytest.raises(AttributeError):
            r.violation_id = "v-2"

    def test_case_closure_report_immutable(self):
        r = CaseClosureReport(
            report_id="rpt-1", case_id="c-1",
            tenant_id="t-1", closed_at=TS,
        )
        with pytest.raises(AttributeError):
            r.report_id = "rpt-2"


# ===================================================================
# Cross-cutting metadata freeze
# ===================================================================


class TestCrossCuttingMetadataFreeze:
    """Verify that metadata is MappingProxyType across all dataclasses."""

    def test_case_record_metadata(self):
        r = CaseRecord(
            case_id="c-1", tenant_id="t-1", title="T",
            opened_by="u-1", opened_at=TS, metadata={"k": "v"},
        )
        assert isinstance(r.metadata, MappingProxyType)

    def test_case_assignment_metadata(self):
        r = CaseAssignment(
            assignment_id="a-1", case_id="c-1",
            assignee_id="u-1", role="lead", assigned_at=TS,
            metadata={"k": "v"},
        )
        assert isinstance(r.metadata, MappingProxyType)

    def test_evidence_item_metadata(self):
        r = EvidenceItem(
            evidence_id="e-1", case_id="c-1",
            source_type="log", source_id="s-1",
            title="T", submitted_by="u-1", submitted_at=TS,
            metadata={"k": "v"},
        )
        assert isinstance(r.metadata, MappingProxyType)

    def test_evidence_collection_metadata(self):
        r = EvidenceCollection(
            collection_id="col-1", case_id="c-1",
            title="T", created_at=TS, metadata={"k": "v"},
        )
        assert isinstance(r.metadata, MappingProxyType)

    def test_review_record_metadata(self):
        r = ReviewRecord(
            review_id="r-1", case_id="c-1",
            evidence_id="e-1", reviewer_id="u-1",
            reviewed_at=TS, metadata={"k": "v"},
        )
        assert isinstance(r.metadata, MappingProxyType)

    def test_finding_record_metadata(self):
        r = FindingRecord(
            finding_id="f-1", case_id="c-1",
            title="T", found_at=TS, metadata={"k": "v"},
        )
        assert isinstance(r.metadata, MappingProxyType)

    def test_case_decision_metadata(self):
        r = CaseDecision(
            decision_id="d-1", case_id="c-1",
            decided_by="u-1", decided_at=TS, metadata={"k": "v"},
        )
        assert isinstance(r.metadata, MappingProxyType)

    def test_case_snapshot_metadata(self):
        r = CaseSnapshot(
            snapshot_id="s-1", captured_at=TS, metadata={"k": "v"},
        )
        assert isinstance(r.metadata, MappingProxyType)

    def test_case_violation_metadata(self):
        r = CaseViolation(
            violation_id="v-1", case_id="c-1",
            tenant_id="t-1", operation="op",
            detected_at=TS, metadata={"k": "v"},
        )
        assert isinstance(r.metadata, MappingProxyType)

    def test_case_closure_report_metadata(self):
        r = CaseClosureReport(
            report_id="rpt-1", case_id="c-1",
            tenant_id="t-1", closed_at=TS, metadata={"k": "v"},
        )
        assert isinstance(r.metadata, MappingProxyType)


# ===================================================================
# Fail-closed defaults (consolidated)
# ===================================================================


class TestFailClosedDefaults:
    """All fail-closed defaults are the most restrictive option."""

    def test_case_status_default_open(self):
        r = CaseRecord(
            case_id="c-1", tenant_id="t-1", title="T",
            opened_by="u-1", opened_at=TS,
        )
        assert r.status is CaseStatus.OPEN

    def test_evidence_status_default_pending(self):
        r = EvidenceItem(
            evidence_id="e-1", case_id="c-1",
            source_type="log", source_id="s-1",
            title="T", submitted_by="u-1", submitted_at=TS,
        )
        assert r.status is EvidenceStatus.PENDING

    def test_review_disposition_default_requires_review(self):
        r = ReviewRecord(
            review_id="r-1", case_id="c-1",
            evidence_id="e-1", reviewer_id="u-1",
            reviewed_at=TS,
        )
        assert r.disposition is ReviewDisposition.REQUIRES_REVIEW

    def test_case_closure_disposition_default_unresolved_decision(self):
        r = CaseDecision(
            decision_id="d-1", case_id="c-1",
            decided_by="u-1", decided_at=TS,
        )
        assert r.disposition is CaseClosureDisposition.UNRESOLVED

    def test_case_closure_disposition_default_unresolved_report(self):
        r = CaseClosureReport(
            report_id="rpt-1", case_id="c-1",
            tenant_id="t-1", closed_at=TS,
        )
        assert r.disposition is CaseClosureDisposition.UNRESOLVED
