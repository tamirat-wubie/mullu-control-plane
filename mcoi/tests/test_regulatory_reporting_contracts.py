"""Tests for regulatory reporting contracts."""

from __future__ import annotations

import dataclasses
from types import MappingProxyType

import pytest

from mcoi_runtime.contracts.regulatory_reporting import (
    AuditorRequest,
    AuditorResponse,
    EvidenceCompleteness,
    EvidencePackage,
    FilingKind,
    FilingWindow,
    ReportAudience,
    ReportingClosureReport,
    ReportingDisposition,
    ReportingRequirement,
    ReportingReview,
    ReportingViolation,
    RegulatorySnapshot,
    ReviewRequirement,
    SubmissionRecord,
    SubmissionStatus,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

TS = "2025-06-01T12:00:00+00:00"
TS2 = "2025-06-15T09:00:00+00:00"


def _requirement(**overrides) -> ReportingRequirement:
    defaults = dict(
        requirement_id="req-001",
        tenant_id="t-001",
        filing_kind=FilingKind.ANNUAL,
        audience=ReportAudience.REGULATOR,
        review_requirement=ReviewRequirement.LEGAL_REVIEW,
        title="Annual Compliance Report",
        description="Full annual filing",
        recurring=True,
        created_at=TS,
    )
    defaults.update(overrides)
    return ReportingRequirement(**defaults)


def _filing_window(**overrides) -> FilingWindow:
    defaults = dict(
        window_id="win-001",
        requirement_id="req-001",
        opens_at=TS,
        closes_at=TS2,
        submitted_at="",
        status=SubmissionStatus.DRAFT,
    )
    defaults.update(overrides)
    return FilingWindow(**defaults)


def _submission(**overrides) -> SubmissionRecord:
    defaults = dict(
        submission_id="sub-001",
        window_id="win-001",
        tenant_id="t-001",
        package_id="pkg-001",
        status=SubmissionStatus.SUBMITTED,
        submitted_by="user-1",
        submitted_at=TS,
    )
    defaults.update(overrides)
    return SubmissionRecord(**defaults)


def _evidence_package(**overrides) -> EvidencePackage:
    defaults = dict(
        package_id="pkg-001",
        tenant_id="t-001",
        requirement_id="req-001",
        completeness=EvidenceCompleteness.COMPLETE,
        evidence_ids=("ev-1", "ev-2"),
        total_evidence_items=2,
        assembled_by="assembler-1",
        assembled_at=TS,
    )
    defaults.update(overrides)
    return EvidencePackage(**defaults)


def _review(**overrides) -> ReportingReview:
    defaults = dict(
        review_id="rev-001",
        submission_id="sub-001",
        reviewer="reviewer-1",
        review_requirement=ReviewRequirement.PEER_REVIEW,
        approved=True,
        comments="Looks good",
        reviewed_at=TS,
    )
    defaults.update(overrides)
    return ReportingReview(**defaults)


def _auditor_request(**overrides) -> AuditorRequest:
    defaults = dict(
        request_id="areq-001",
        tenant_id="t-001",
        submission_id="sub-001",
        requested_by="auditor-1",
        description="Need supporting docs",
        requested_at=TS,
        due_at=TS2,
    )
    defaults.update(overrides)
    return AuditorRequest(**defaults)


def _auditor_response(**overrides) -> AuditorResponse:
    defaults = dict(
        response_id="aresp-001",
        request_id="areq-001",
        responder="responder-1",
        content="Here are the docs",
        evidence_ids=("ev-3",),
        responded_at=TS,
    )
    defaults.update(overrides)
    return AuditorResponse(**defaults)


def _snapshot(**overrides) -> RegulatorySnapshot:
    defaults = dict(
        snapshot_id="snap-001",
        total_requirements=10,
        total_windows=8,
        total_packages=6,
        total_submissions=5,
        total_reviews=4,
        total_auditor_requests=3,
        total_auditor_responses=2,
        total_violations=1,
        captured_at=TS,
    )
    defaults.update(overrides)
    return RegulatorySnapshot(**defaults)


def _violation(**overrides) -> ReportingViolation:
    defaults = dict(
        violation_id="viol-001",
        tenant_id="t-001",
        requirement_id="req-001",
        window_id="win-001",
        operation="submit",
        reason="deadline missed",
        detected_at=TS,
    )
    defaults.update(overrides)
    return ReportingViolation(**defaults)


def _closure_report(**overrides) -> ReportingClosureReport:
    defaults = dict(
        report_id="rep-001",
        requirement_id="req-001",
        tenant_id="t-001",
        disposition=ReportingDisposition.ACCEPTED,
        total_submissions=3,
        total_reviews=2,
        total_auditor_requests=1,
        total_violations=0,
        closed_at=TS,
    )
    defaults.update(overrides)
    return ReportingClosureReport(**defaults)


# ===================================================================
# Enum tests
# ===================================================================


class TestSubmissionStatus:
    def test_member_count(self):
        assert len(SubmissionStatus) == 6

    def test_names(self):
        assert {m.name for m in SubmissionStatus} == {
            "DRAFT", "PENDING_REVIEW", "SUBMITTED", "ACCEPTED",
            "REJECTED", "WITHDRAWN",
        }

    def test_values(self):
        assert SubmissionStatus.DRAFT.value == "draft"
        assert SubmissionStatus.PENDING_REVIEW.value == "pending_review"
        assert SubmissionStatus.SUBMITTED.value == "submitted"
        assert SubmissionStatus.ACCEPTED.value == "accepted"
        assert SubmissionStatus.REJECTED.value == "rejected"
        assert SubmissionStatus.WITHDRAWN.value == "withdrawn"

    def test_fail_closed_default(self):
        """Fail-closed: safest default is DRAFT (not ACCEPTED)."""
        assert SubmissionStatus.DRAFT.value == "draft"


class TestFilingKind:
    def test_member_count(self):
        assert len(FilingKind) == 6

    def test_names(self):
        assert {m.name for m in FilingKind} == {
            "ANNUAL", "QUARTERLY", "AD_HOC", "INCIDENT",
            "AUDIT_RESPONSE", "CERTIFICATION",
        }

    def test_values(self):
        assert FilingKind.ANNUAL.value == "annual"
        assert FilingKind.QUARTERLY.value == "quarterly"
        assert FilingKind.AD_HOC.value == "ad_hoc"
        assert FilingKind.INCIDENT.value == "incident"
        assert FilingKind.AUDIT_RESPONSE.value == "audit_response"
        assert FilingKind.CERTIFICATION.value == "certification"


class TestReportAudience:
    def test_member_count(self):
        assert len(ReportAudience) == 5

    def test_names(self):
        assert {m.name for m in ReportAudience} == {
            "REGULATOR", "EXTERNAL_AUDITOR", "INTERNAL_AUDIT",
            "BOARD", "MANAGEMENT",
        }

    def test_values(self):
        assert ReportAudience.REGULATOR.value == "regulator"
        assert ReportAudience.EXTERNAL_AUDITOR.value == "external_auditor"
        assert ReportAudience.INTERNAL_AUDIT.value == "internal_audit"
        assert ReportAudience.BOARD.value == "board"
        assert ReportAudience.MANAGEMENT.value == "management"


class TestEvidenceCompleteness:
    def test_member_count(self):
        assert len(EvidenceCompleteness) == 4

    def test_names(self):
        assert {m.name for m in EvidenceCompleteness} == {
            "INCOMPLETE", "PARTIAL", "COMPLETE", "VERIFIED",
        }

    def test_values(self):
        assert EvidenceCompleteness.INCOMPLETE.value == "incomplete"
        assert EvidenceCompleteness.PARTIAL.value == "partial"
        assert EvidenceCompleteness.COMPLETE.value == "complete"
        assert EvidenceCompleteness.VERIFIED.value == "verified"

    def test_fail_closed_default(self):
        """Fail-closed: safest default is INCOMPLETE."""
        assert EvidenceCompleteness.INCOMPLETE.value == "incomplete"


class TestReviewRequirement:
    def test_member_count(self):
        assert len(ReviewRequirement) == 5

    def test_names(self):
        assert {m.name for m in ReviewRequirement} == {
            "NONE", "PEER_REVIEW", "MANAGEMENT_REVIEW",
            "LEGAL_REVIEW", "EXTERNAL_REVIEW",
        }

    def test_values(self):
        assert ReviewRequirement.NONE.value == "none"
        assert ReviewRequirement.PEER_REVIEW.value == "peer_review"
        assert ReviewRequirement.MANAGEMENT_REVIEW.value == "management_review"
        assert ReviewRequirement.LEGAL_REVIEW.value == "legal_review"
        assert ReviewRequirement.EXTERNAL_REVIEW.value == "external_review"


class TestReportingDisposition:
    def test_member_count(self):
        assert len(ReportingDisposition) == 5

    def test_names(self):
        assert {m.name for m in ReportingDisposition} == {
            "FILED", "ACCEPTED", "REJECTED", "WITHDRAWN", "OVERDUE",
        }

    def test_values(self):
        assert ReportingDisposition.FILED.value == "filed"
        assert ReportingDisposition.ACCEPTED.value == "accepted"
        assert ReportingDisposition.REJECTED.value == "rejected"
        assert ReportingDisposition.WITHDRAWN.value == "withdrawn"
        assert ReportingDisposition.OVERDUE.value == "overdue"

    def test_fail_closed_default(self):
        """Fail-closed: safest default is OVERDUE (not ACCEPTED)."""
        assert ReportingDisposition.OVERDUE.value == "overdue"


# ===================================================================
# ReportingRequirement
# ===================================================================


class TestReportingRequirement:
    def test_valid_construction(self):
        rec = _requirement()
        assert rec.requirement_id == "req-001"
        assert rec.tenant_id == "t-001"
        assert rec.filing_kind is FilingKind.ANNUAL
        assert rec.audience is ReportAudience.REGULATOR
        assert rec.review_requirement is ReviewRequirement.LEGAL_REVIEW
        assert rec.title == "Annual Compliance Report"
        assert rec.description == "Full annual filing"
        assert rec.recurring is True

    def test_empty_requirement_id_rejected(self):
        with pytest.raises(ValueError):
            _requirement(requirement_id="")

    def test_whitespace_requirement_id_rejected(self):
        with pytest.raises(ValueError):
            _requirement(requirement_id="   ")

    def test_empty_tenant_id_rejected(self):
        with pytest.raises(ValueError):
            _requirement(tenant_id="")

    def test_whitespace_tenant_id_rejected(self):
        with pytest.raises(ValueError):
            _requirement(tenant_id="\t  ")

    def test_empty_title_rejected(self):
        with pytest.raises(ValueError):
            _requirement(title="")

    def test_whitespace_title_rejected(self):
        with pytest.raises(ValueError):
            _requirement(title="   \n")

    def test_invalid_filing_kind_rejected(self):
        with pytest.raises(ValueError):
            _requirement(filing_kind="annual")

    def test_invalid_audience_rejected(self):
        with pytest.raises(ValueError):
            _requirement(audience="regulator")

    def test_invalid_review_requirement_rejected(self):
        with pytest.raises(ValueError):
            _requirement(review_requirement="legal_review")

    def test_garbage_datetime_rejected(self):
        with pytest.raises(ValueError):
            _requirement(created_at="not-a-date")

    def test_numeric_datetime_rejected(self):
        with pytest.raises(ValueError):
            _requirement(created_at=12345)

    def test_metadata_frozen(self):
        rec = _requirement(metadata={"key": "val"})
        assert isinstance(rec.metadata, MappingProxyType)
        assert rec.metadata["key"] == "val"

    def test_nested_metadata_frozen(self):
        rec = _requirement(metadata={"inner": {"a": 1}})
        assert isinstance(rec.metadata["inner"], MappingProxyType)

    def test_metadata_list_becomes_tuple(self):
        rec = _requirement(metadata={"items": [1, 2, 3]})
        assert rec.metadata["items"] == (1, 2, 3)

    def test_immutability(self):
        rec = _requirement()
        with pytest.raises(dataclasses.FrozenInstanceError):
            rec.requirement_id = "other"

    def test_has_slots(self):
        assert hasattr(ReportingRequirement, "__slots__")

    def test_to_dict(self):
        rec = _requirement()
        d = rec.to_dict()
        assert d["requirement_id"] == "req-001"
        assert d["filing_kind"] is FilingKind.ANNUAL
        assert d["audience"] is ReportAudience.REGULATOR
        assert d["review_requirement"] is ReviewRequirement.LEGAL_REVIEW
        assert isinstance(d["metadata"], dict)

    def test_to_dict_preserves_enum_objects(self):
        d = _requirement().to_dict()
        assert isinstance(d["filing_kind"], FilingKind)
        assert isinstance(d["audience"], ReportAudience)
        assert isinstance(d["review_requirement"], ReviewRequirement)

    def test_fail_closed_filing_kind_default(self):
        """Default filing_kind is AD_HOC (safest)."""
        assert ReportingRequirement.__dataclass_fields__["filing_kind"].default is FilingKind.AD_HOC

    def test_fail_closed_review_requirement_default(self):
        """Default review_requirement is NONE."""
        assert ReportingRequirement.__dataclass_fields__["review_requirement"].default is ReviewRequirement.NONE

    def test_fail_closed_recurring_default(self):
        """Default recurring is False."""
        assert ReportingRequirement.__dataclass_fields__["recurring"].default is False


# ===================================================================
# FilingWindow
# ===================================================================


class TestFilingWindow:
    def test_valid_construction(self):
        rec = _filing_window()
        assert rec.window_id == "win-001"
        assert rec.requirement_id == "req-001"
        assert rec.status is SubmissionStatus.DRAFT

    def test_empty_window_id_rejected(self):
        with pytest.raises(ValueError):
            _filing_window(window_id="")

    def test_whitespace_window_id_rejected(self):
        with pytest.raises(ValueError):
            _filing_window(window_id="   ")

    def test_empty_requirement_id_rejected(self):
        with pytest.raises(ValueError):
            _filing_window(requirement_id="")

    def test_invalid_status_rejected(self):
        with pytest.raises(ValueError):
            _filing_window(status="draft")

    def test_garbage_opens_at_rejected(self):
        with pytest.raises(ValueError):
            _filing_window(opens_at="garbage")

    def test_garbage_closes_at_rejected(self):
        with pytest.raises(ValueError):
            _filing_window(closes_at="garbage")

    def test_numeric_datetime_rejected(self):
        with pytest.raises(ValueError):
            _filing_window(opens_at=99999)

    def test_submitted_at_optional_empty(self):
        """submitted_at can be empty string (not validated)."""
        rec = _filing_window(submitted_at="")
        assert rec.submitted_at == ""

    def test_metadata_frozen(self):
        rec = _filing_window(metadata={"k": "v"})
        assert isinstance(rec.metadata, MappingProxyType)

    def test_nested_metadata_frozen(self):
        rec = _filing_window(metadata={"nest": {"x": 1}})
        assert isinstance(rec.metadata["nest"], MappingProxyType)

    def test_immutability(self):
        rec = _filing_window()
        with pytest.raises(dataclasses.FrozenInstanceError):
            rec.window_id = "other"

    def test_has_slots(self):
        assert hasattr(FilingWindow, "__slots__")

    def test_to_dict(self):
        rec = _filing_window()
        d = rec.to_dict()
        assert d["window_id"] == "win-001"
        assert d["status"] is SubmissionStatus.DRAFT
        assert isinstance(d["metadata"], dict)

    def test_to_dict_preserves_enum_objects(self):
        d = _filing_window().to_dict()
        assert isinstance(d["status"], SubmissionStatus)

    def test_fail_closed_status_default(self):
        """Default status is DRAFT (safest)."""
        assert FilingWindow.__dataclass_fields__["status"].default is SubmissionStatus.DRAFT


# ===================================================================
# SubmissionRecord
# ===================================================================


class TestSubmissionRecord:
    def test_valid_construction(self):
        rec = _submission()
        assert rec.submission_id == "sub-001"
        assert rec.window_id == "win-001"
        assert rec.tenant_id == "t-001"
        assert rec.package_id == "pkg-001"
        assert rec.status is SubmissionStatus.SUBMITTED
        assert rec.submitted_by == "user-1"

    def test_empty_submission_id_rejected(self):
        with pytest.raises(ValueError):
            _submission(submission_id="")

    def test_whitespace_submission_id_rejected(self):
        with pytest.raises(ValueError):
            _submission(submission_id="  \t")

    def test_empty_window_id_rejected(self):
        with pytest.raises(ValueError):
            _submission(window_id="")

    def test_empty_tenant_id_rejected(self):
        with pytest.raises(ValueError):
            _submission(tenant_id="")

    def test_empty_package_id_rejected(self):
        with pytest.raises(ValueError):
            _submission(package_id="")

    def test_empty_submitted_by_rejected(self):
        with pytest.raises(ValueError):
            _submission(submitted_by="")

    def test_whitespace_submitted_by_rejected(self):
        with pytest.raises(ValueError):
            _submission(submitted_by="   ")

    def test_invalid_status_rejected(self):
        with pytest.raises(ValueError):
            _submission(status="submitted")

    def test_garbage_datetime_rejected(self):
        with pytest.raises(ValueError):
            _submission(submitted_at="nope")

    def test_numeric_datetime_rejected(self):
        with pytest.raises(ValueError):
            _submission(submitted_at=42)

    def test_metadata_frozen(self):
        rec = _submission(metadata={"a": "b"})
        assert isinstance(rec.metadata, MappingProxyType)

    def test_nested_metadata_frozen(self):
        rec = _submission(metadata={"n": {"z": 9}})
        assert isinstance(rec.metadata["n"], MappingProxyType)

    def test_immutability(self):
        rec = _submission()
        with pytest.raises(dataclasses.FrozenInstanceError):
            rec.submission_id = "other"

    def test_has_slots(self):
        assert hasattr(SubmissionRecord, "__slots__")

    def test_to_dict(self):
        rec = _submission()
        d = rec.to_dict()
        assert d["submission_id"] == "sub-001"
        assert d["status"] is SubmissionStatus.SUBMITTED
        assert isinstance(d["metadata"], dict)

    def test_to_dict_preserves_enum_objects(self):
        d = _submission().to_dict()
        assert isinstance(d["status"], SubmissionStatus)

    def test_fail_closed_status_default(self):
        """Default status is DRAFT (safest)."""
        assert SubmissionRecord.__dataclass_fields__["status"].default is SubmissionStatus.DRAFT


# ===================================================================
# EvidencePackage
# ===================================================================


class TestEvidencePackage:
    def test_valid_construction(self):
        rec = _evidence_package()
        assert rec.package_id == "pkg-001"
        assert rec.tenant_id == "t-001"
        assert rec.requirement_id == "req-001"
        assert rec.completeness is EvidenceCompleteness.COMPLETE
        assert rec.evidence_ids == ("ev-1", "ev-2")
        assert rec.total_evidence_items == 2
        assert rec.assembled_by == "assembler-1"

    def test_empty_package_id_rejected(self):
        with pytest.raises(ValueError):
            _evidence_package(package_id="")

    def test_whitespace_package_id_rejected(self):
        with pytest.raises(ValueError):
            _evidence_package(package_id="   ")

    def test_empty_tenant_id_rejected(self):
        with pytest.raises(ValueError):
            _evidence_package(tenant_id="")

    def test_empty_requirement_id_rejected(self):
        with pytest.raises(ValueError):
            _evidence_package(requirement_id="")

    def test_empty_assembled_by_rejected(self):
        with pytest.raises(ValueError):
            _evidence_package(assembled_by="")

    def test_whitespace_assembled_by_rejected(self):
        with pytest.raises(ValueError):
            _evidence_package(assembled_by="  \n")

    def test_invalid_completeness_rejected(self):
        with pytest.raises(ValueError):
            _evidence_package(completeness="complete")

    def test_evidence_ids_list_becomes_tuple(self):
        rec = _evidence_package(evidence_ids=["a", "b", "c"])
        assert rec.evidence_ids == ("a", "b", "c")
        assert isinstance(rec.evidence_ids, tuple)

    def test_evidence_ids_empty_tuple(self):
        rec = _evidence_package(evidence_ids=())
        assert rec.evidence_ids == ()

    def test_negative_total_evidence_items_rejected(self):
        with pytest.raises(ValueError):
            _evidence_package(total_evidence_items=-1)

    def test_zero_total_evidence_items_accepted(self):
        rec = _evidence_package(total_evidence_items=0)
        assert rec.total_evidence_items == 0

    def test_garbage_datetime_rejected(self):
        with pytest.raises(ValueError):
            _evidence_package(assembled_at="xyz")

    def test_numeric_datetime_rejected(self):
        with pytest.raises(ValueError):
            _evidence_package(assembled_at=12345)

    def test_metadata_frozen(self):
        rec = _evidence_package(metadata={"k": "v"})
        assert isinstance(rec.metadata, MappingProxyType)

    def test_nested_metadata_frozen(self):
        rec = _evidence_package(metadata={"n": {"q": 2}})
        assert isinstance(rec.metadata["n"], MappingProxyType)

    def test_metadata_list_becomes_tuple(self):
        rec = _evidence_package(metadata={"lst": [10, 20]})
        assert rec.metadata["lst"] == (10, 20)

    def test_immutability(self):
        rec = _evidence_package()
        with pytest.raises(dataclasses.FrozenInstanceError):
            rec.package_id = "other"

    def test_has_slots(self):
        assert hasattr(EvidencePackage, "__slots__")

    def test_to_dict(self):
        rec = _evidence_package()
        d = rec.to_dict()
        assert d["package_id"] == "pkg-001"
        assert d["completeness"] is EvidenceCompleteness.COMPLETE
        assert isinstance(d["metadata"], dict)

    def test_to_dict_preserves_enum_objects(self):
        d = _evidence_package().to_dict()
        assert isinstance(d["completeness"], EvidenceCompleteness)

    def test_fail_closed_completeness_default(self):
        """Default completeness is INCOMPLETE (safest)."""
        assert EvidencePackage.__dataclass_fields__["completeness"].default is EvidenceCompleteness.INCOMPLETE


# ===================================================================
# ReportingReview
# ===================================================================


class TestReportingReview:
    def test_valid_construction(self):
        rec = _review()
        assert rec.review_id == "rev-001"
        assert rec.submission_id == "sub-001"
        assert rec.reviewer == "reviewer-1"
        assert rec.review_requirement is ReviewRequirement.PEER_REVIEW
        assert rec.approved is True
        assert rec.comments == "Looks good"

    def test_empty_review_id_rejected(self):
        with pytest.raises(ValueError):
            _review(review_id="")

    def test_whitespace_review_id_rejected(self):
        with pytest.raises(ValueError):
            _review(review_id="   ")

    def test_empty_submission_id_rejected(self):
        with pytest.raises(ValueError):
            _review(submission_id="")

    def test_empty_reviewer_rejected(self):
        with pytest.raises(ValueError):
            _review(reviewer="")

    def test_whitespace_reviewer_rejected(self):
        with pytest.raises(ValueError):
            _review(reviewer="  \t ")

    def test_invalid_review_requirement_rejected(self):
        with pytest.raises(ValueError):
            _review(review_requirement="peer_review")

    def test_garbage_datetime_rejected(self):
        with pytest.raises(ValueError):
            _review(reviewed_at="bad")

    def test_numeric_datetime_rejected(self):
        with pytest.raises(ValueError):
            _review(reviewed_at=999)

    def test_metadata_frozen(self):
        rec = _review(metadata={"x": "y"})
        assert isinstance(rec.metadata, MappingProxyType)

    def test_nested_metadata_frozen(self):
        rec = _review(metadata={"n": {"p": 3}})
        assert isinstance(rec.metadata["n"], MappingProxyType)

    def test_immutability(self):
        rec = _review()
        with pytest.raises(dataclasses.FrozenInstanceError):
            rec.review_id = "other"

    def test_has_slots(self):
        assert hasattr(ReportingReview, "__slots__")

    def test_to_dict(self):
        rec = _review()
        d = rec.to_dict()
        assert d["review_id"] == "rev-001"
        assert d["review_requirement"] is ReviewRequirement.PEER_REVIEW
        assert isinstance(d["metadata"], dict)

    def test_to_dict_preserves_enum_objects(self):
        d = _review().to_dict()
        assert isinstance(d["review_requirement"], ReviewRequirement)

    def test_fail_closed_approved_default(self):
        """Default approved is False (safest)."""
        assert ReportingReview.__dataclass_fields__["approved"].default is False

    def test_fail_closed_review_requirement_default(self):
        """Default review_requirement is NONE."""
        assert ReportingReview.__dataclass_fields__["review_requirement"].default is ReviewRequirement.NONE


# ===================================================================
# AuditorRequest
# ===================================================================


class TestAuditorRequest:
    def test_valid_construction(self):
        rec = _auditor_request()
        assert rec.request_id == "areq-001"
        assert rec.tenant_id == "t-001"
        assert rec.submission_id == "sub-001"
        assert rec.requested_by == "auditor-1"
        assert rec.description == "Need supporting docs"

    def test_empty_request_id_rejected(self):
        with pytest.raises(ValueError):
            _auditor_request(request_id="")

    def test_whitespace_request_id_rejected(self):
        with pytest.raises(ValueError):
            _auditor_request(request_id="   ")

    def test_empty_tenant_id_rejected(self):
        with pytest.raises(ValueError):
            _auditor_request(tenant_id="")

    def test_empty_submission_id_rejected(self):
        with pytest.raises(ValueError):
            _auditor_request(submission_id="")

    def test_empty_requested_by_rejected(self):
        with pytest.raises(ValueError):
            _auditor_request(requested_by="")

    def test_whitespace_requested_by_rejected(self):
        with pytest.raises(ValueError):
            _auditor_request(requested_by="  \t")

    def test_garbage_requested_at_rejected(self):
        with pytest.raises(ValueError):
            _auditor_request(requested_at="nope")

    def test_garbage_due_at_rejected(self):
        with pytest.raises(ValueError):
            _auditor_request(due_at="nope")

    def test_numeric_datetime_rejected(self):
        with pytest.raises(ValueError):
            _auditor_request(requested_at=42)

    def test_metadata_frozen(self):
        rec = _auditor_request(metadata={"a": "b"})
        assert isinstance(rec.metadata, MappingProxyType)

    def test_nested_metadata_frozen(self):
        rec = _auditor_request(metadata={"deep": {"v": 1}})
        assert isinstance(rec.metadata["deep"], MappingProxyType)

    def test_immutability(self):
        rec = _auditor_request()
        with pytest.raises(dataclasses.FrozenInstanceError):
            rec.request_id = "other"

    def test_has_slots(self):
        assert hasattr(AuditorRequest, "__slots__")

    def test_to_dict(self):
        rec = _auditor_request()
        d = rec.to_dict()
        assert d["request_id"] == "areq-001"
        assert isinstance(d["metadata"], dict)


# ===================================================================
# AuditorResponse
# ===================================================================


class TestAuditorResponse:
    def test_valid_construction(self):
        rec = _auditor_response()
        assert rec.response_id == "aresp-001"
        assert rec.request_id == "areq-001"
        assert rec.responder == "responder-1"
        assert rec.content == "Here are the docs"
        assert rec.evidence_ids == ("ev-3",)

    def test_empty_response_id_rejected(self):
        with pytest.raises(ValueError):
            _auditor_response(response_id="")

    def test_whitespace_response_id_rejected(self):
        with pytest.raises(ValueError):
            _auditor_response(response_id="   ")

    def test_empty_request_id_rejected(self):
        with pytest.raises(ValueError):
            _auditor_response(request_id="")

    def test_empty_responder_rejected(self):
        with pytest.raises(ValueError):
            _auditor_response(responder="")

    def test_whitespace_responder_rejected(self):
        with pytest.raises(ValueError):
            _auditor_response(responder="  \n  ")

    def test_evidence_ids_list_becomes_tuple(self):
        rec = _auditor_response(evidence_ids=["a", "b"])
        assert rec.evidence_ids == ("a", "b")
        assert isinstance(rec.evidence_ids, tuple)

    def test_evidence_ids_empty_tuple(self):
        rec = _auditor_response(evidence_ids=())
        assert rec.evidence_ids == ()

    def test_garbage_datetime_rejected(self):
        with pytest.raises(ValueError):
            _auditor_response(responded_at="xyz")

    def test_numeric_datetime_rejected(self):
        with pytest.raises(ValueError):
            _auditor_response(responded_at=12345)

    def test_metadata_frozen(self):
        rec = _auditor_response(metadata={"m": "n"})
        assert isinstance(rec.metadata, MappingProxyType)

    def test_nested_metadata_frozen(self):
        rec = _auditor_response(metadata={"d": {"e": 5}})
        assert isinstance(rec.metadata["d"], MappingProxyType)

    def test_metadata_list_becomes_tuple(self):
        rec = _auditor_response(metadata={"items": [7, 8]})
        assert rec.metadata["items"] == (7, 8)

    def test_immutability(self):
        rec = _auditor_response()
        with pytest.raises(dataclasses.FrozenInstanceError):
            rec.response_id = "other"

    def test_has_slots(self):
        assert hasattr(AuditorResponse, "__slots__")

    def test_to_dict(self):
        rec = _auditor_response()
        d = rec.to_dict()
        assert d["response_id"] == "aresp-001"
        assert isinstance(d["metadata"], dict)


# ===================================================================
# RegulatorySnapshot
# ===================================================================


class TestRegulatorySnapshot:
    def test_valid_construction(self):
        rec = _snapshot()
        assert rec.snapshot_id == "snap-001"
        assert rec.total_requirements == 10
        assert rec.total_windows == 8
        assert rec.total_packages == 6
        assert rec.total_submissions == 5
        assert rec.total_reviews == 4
        assert rec.total_auditor_requests == 3
        assert rec.total_auditor_responses == 2
        assert rec.total_violations == 1

    def test_empty_snapshot_id_rejected(self):
        with pytest.raises(ValueError):
            _snapshot(snapshot_id="")

    def test_whitespace_snapshot_id_rejected(self):
        with pytest.raises(ValueError):
            _snapshot(snapshot_id="   ")

    def test_negative_total_requirements_rejected(self):
        with pytest.raises(ValueError):
            _snapshot(total_requirements=-1)

    def test_negative_total_windows_rejected(self):
        with pytest.raises(ValueError):
            _snapshot(total_windows=-1)

    def test_negative_total_packages_rejected(self):
        with pytest.raises(ValueError):
            _snapshot(total_packages=-1)

    def test_negative_total_submissions_rejected(self):
        with pytest.raises(ValueError):
            _snapshot(total_submissions=-1)

    def test_negative_total_reviews_rejected(self):
        with pytest.raises(ValueError):
            _snapshot(total_reviews=-1)

    def test_negative_total_auditor_requests_rejected(self):
        with pytest.raises(ValueError):
            _snapshot(total_auditor_requests=-1)

    def test_negative_total_auditor_responses_rejected(self):
        with pytest.raises(ValueError):
            _snapshot(total_auditor_responses=-1)

    def test_negative_total_violations_rejected(self):
        with pytest.raises(ValueError):
            _snapshot(total_violations=-1)

    def test_zero_counts_accepted(self):
        rec = _snapshot(
            total_requirements=0,
            total_windows=0,
            total_packages=0,
            total_submissions=0,
            total_reviews=0,
            total_auditor_requests=0,
            total_auditor_responses=0,
            total_violations=0,
        )
        assert rec.total_requirements == 0
        assert rec.total_violations == 0

    def test_garbage_datetime_rejected(self):
        with pytest.raises(ValueError):
            _snapshot(captured_at="garbage")

    def test_numeric_datetime_rejected(self):
        with pytest.raises(ValueError):
            _snapshot(captured_at=9999)

    def test_metadata_frozen(self):
        rec = _snapshot(metadata={"s": "t"})
        assert isinstance(rec.metadata, MappingProxyType)

    def test_nested_metadata_frozen(self):
        rec = _snapshot(metadata={"n": {"r": 4}})
        assert isinstance(rec.metadata["n"], MappingProxyType)

    def test_immutability(self):
        rec = _snapshot()
        with pytest.raises(dataclasses.FrozenInstanceError):
            rec.snapshot_id = "other"

    def test_has_slots(self):
        assert hasattr(RegulatorySnapshot, "__slots__")

    def test_to_dict(self):
        rec = _snapshot()
        d = rec.to_dict()
        assert d["snapshot_id"] == "snap-001"
        assert d["total_requirements"] == 10
        assert isinstance(d["metadata"], dict)


# ===================================================================
# ReportingViolation
# ===================================================================


class TestReportingViolation:
    def test_valid_construction(self):
        rec = _violation()
        assert rec.violation_id == "viol-001"
        assert rec.tenant_id == "t-001"
        assert rec.requirement_id == "req-001"
        assert rec.window_id == "win-001"
        assert rec.operation == "submit"
        assert rec.reason == "deadline missed"

    def test_empty_violation_id_rejected(self):
        with pytest.raises(ValueError):
            _violation(violation_id="")

    def test_whitespace_violation_id_rejected(self):
        with pytest.raises(ValueError):
            _violation(violation_id="   ")

    def test_empty_tenant_id_rejected(self):
        with pytest.raises(ValueError):
            _violation(tenant_id="")

    def test_empty_requirement_id_rejected(self):
        with pytest.raises(ValueError):
            _violation(requirement_id="")

    def test_empty_window_id_rejected(self):
        with pytest.raises(ValueError):
            _violation(window_id="")

    def test_empty_operation_rejected(self):
        with pytest.raises(ValueError):
            _violation(operation="")

    def test_whitespace_operation_rejected(self):
        with pytest.raises(ValueError):
            _violation(operation="  \t  ")

    def test_garbage_datetime_rejected(self):
        with pytest.raises(ValueError):
            _violation(detected_at="bad-date")

    def test_numeric_datetime_rejected(self):
        with pytest.raises(ValueError):
            _violation(detected_at=11111)

    def test_metadata_frozen(self):
        rec = _violation(metadata={"v": "w"})
        assert isinstance(rec.metadata, MappingProxyType)

    def test_nested_metadata_frozen(self):
        rec = _violation(metadata={"deep": {"val": 7}})
        assert isinstance(rec.metadata["deep"], MappingProxyType)

    def test_immutability(self):
        rec = _violation()
        with pytest.raises(dataclasses.FrozenInstanceError):
            rec.violation_id = "other"

    def test_has_slots(self):
        assert hasattr(ReportingViolation, "__slots__")

    def test_to_dict(self):
        rec = _violation()
        d = rec.to_dict()
        assert d["violation_id"] == "viol-001"
        assert isinstance(d["metadata"], dict)


# ===================================================================
# ReportingClosureReport
# ===================================================================


class TestReportingClosureReport:
    def test_valid_construction(self):
        rec = _closure_report()
        assert rec.report_id == "rep-001"
        assert rec.requirement_id == "req-001"
        assert rec.tenant_id == "t-001"
        assert rec.disposition is ReportingDisposition.ACCEPTED
        assert rec.total_submissions == 3
        assert rec.total_reviews == 2
        assert rec.total_auditor_requests == 1
        assert rec.total_violations == 0

    def test_empty_report_id_rejected(self):
        with pytest.raises(ValueError):
            _closure_report(report_id="")

    def test_whitespace_report_id_rejected(self):
        with pytest.raises(ValueError):
            _closure_report(report_id="   ")

    def test_empty_requirement_id_rejected(self):
        with pytest.raises(ValueError):
            _closure_report(requirement_id="")

    def test_empty_tenant_id_rejected(self):
        with pytest.raises(ValueError):
            _closure_report(tenant_id="")

    def test_whitespace_tenant_id_rejected(self):
        with pytest.raises(ValueError):
            _closure_report(tenant_id="\t ")

    def test_invalid_disposition_rejected(self):
        with pytest.raises(ValueError):
            _closure_report(disposition="accepted")

    def test_negative_total_submissions_rejected(self):
        with pytest.raises(ValueError):
            _closure_report(total_submissions=-1)

    def test_negative_total_reviews_rejected(self):
        with pytest.raises(ValueError):
            _closure_report(total_reviews=-1)

    def test_negative_total_auditor_requests_rejected(self):
        with pytest.raises(ValueError):
            _closure_report(total_auditor_requests=-1)

    def test_negative_total_violations_rejected(self):
        with pytest.raises(ValueError):
            _closure_report(total_violations=-1)

    def test_zero_counts_accepted(self):
        rec = _closure_report(
            total_submissions=0,
            total_reviews=0,
            total_auditor_requests=0,
            total_violations=0,
        )
        assert rec.total_submissions == 0
        assert rec.total_violations == 0

    def test_garbage_datetime_rejected(self):
        with pytest.raises(ValueError):
            _closure_report(closed_at="nope")

    def test_numeric_datetime_rejected(self):
        with pytest.raises(ValueError):
            _closure_report(closed_at=42)

    def test_metadata_frozen(self):
        rec = _closure_report(metadata={"fin": "val"})
        assert isinstance(rec.metadata, MappingProxyType)

    def test_nested_metadata_frozen(self):
        rec = _closure_report(metadata={"deep": {"k": 9}})
        assert isinstance(rec.metadata["deep"], MappingProxyType)

    def test_metadata_list_becomes_tuple(self):
        rec = _closure_report(metadata={"lst": [1, 2]})
        assert rec.metadata["lst"] == (1, 2)

    def test_immutability(self):
        rec = _closure_report()
        with pytest.raises(dataclasses.FrozenInstanceError):
            rec.report_id = "other"

    def test_has_slots(self):
        assert hasattr(ReportingClosureReport, "__slots__")

    def test_to_dict(self):
        rec = _closure_report()
        d = rec.to_dict()
        assert d["report_id"] == "rep-001"
        assert d["disposition"] is ReportingDisposition.ACCEPTED
        assert isinstance(d["metadata"], dict)

    def test_to_dict_preserves_enum_objects(self):
        d = _closure_report().to_dict()
        assert isinstance(d["disposition"], ReportingDisposition)

    def test_fail_closed_disposition_default(self):
        """Default disposition is OVERDUE (safest -- not ACCEPTED)."""
        assert ReportingClosureReport.__dataclass_fields__["disposition"].default is ReportingDisposition.OVERDUE
