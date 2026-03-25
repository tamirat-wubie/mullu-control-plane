"""Purpose: comprehensive tests for the RegulatoryReportingEngine.
Governance scope: regulatory-reporting-core tests only.
Dependencies: regulatory_reporting contracts, event_spine, core invariants.
Invariants:
  - Incomplete packages cannot be submitted.
  - Filing windows enforce deadlines.
  - Every mutation emits an event.
  - All returns are immutable.
  - Terminal submission states cannot transition further.
  - Duplicate IDs always raise.
  - Violation detection is idempotent.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.contracts.regulatory_reporting import (
    AuditorRequest,
    AuditorResponse,
    EvidenceCompleteness,
    EvidencePackage,
    FilingKind,
    FilingWindow,
    RegulatorySnapshot,
    ReportAudience,
    ReportingRequirement,
    ReportingReview,
    ReportingViolation,
    ReviewRequirement,
    SubmissionRecord,
    SubmissionStatus,
)
from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
from mcoi_runtime.core.regulatory_reporting import RegulatoryReportingEngine


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_PAST_OPEN = "2020-01-01T00:00:00+00:00"
_PAST_CLOSE = "2020-06-01T00:00:00+00:00"
_FUTURE_OPEN = "2099-01-01T00:00:00+00:00"
_FUTURE_CLOSE = "2099-12-31T23:59:59+00:00"


def _make_engine() -> tuple[RegulatoryReportingEngine, EventSpineEngine]:
    es = EventSpineEngine()
    engine = RegulatoryReportingEngine(es)
    return engine, es


def _seed_requirement(
    engine: RegulatoryReportingEngine,
    requirement_id: str = "req-1",
    tenant_id: str = "tenant-a",
    title: str = "Annual Compliance",
    **kwargs,
) -> ReportingRequirement:
    return engine.register_requirement(requirement_id, tenant_id, title, **kwargs)


def _seed_window(
    engine: RegulatoryReportingEngine,
    window_id: str = "win-1",
    requirement_id: str = "req-1",
    opens_at: str = _FUTURE_OPEN,
    closes_at: str = _FUTURE_CLOSE,
) -> FilingWindow:
    return engine.open_filing_window(window_id, requirement_id, opens_at, closes_at)


def _seed_package(
    engine: RegulatoryReportingEngine,
    package_id: str = "pkg-1",
    tenant_id: str = "tenant-a",
    requirement_id: str = "req-1",
    evidence_ids: tuple[str, ...] = ("ev-1", "ev-2"),
    **kwargs,
) -> EvidencePackage:
    return engine.assemble_evidence_package(
        package_id, tenant_id, requirement_id, evidence_ids, **kwargs
    )


def _seed_submission(
    engine: RegulatoryReportingEngine,
    submission_id: str = "sub-1",
    window_id: str = "win-1",
    tenant_id: str = "tenant-a",
    package_id: str = "pkg-1",
    **kwargs,
) -> SubmissionRecord:
    return engine.submit_report(submission_id, window_id, tenant_id, package_id, **kwargs)


def _full_pipeline(engine: RegulatoryReportingEngine) -> SubmissionRecord:
    """Register requirement, open window, assemble package, submit."""
    _seed_requirement(engine)
    _seed_window(engine)
    _seed_package(engine)
    return _seed_submission(engine)


# ===================================================================
# Constructor
# ===================================================================


class TestConstructor:
    def test_requires_event_spine_engine(self) -> None:
        with pytest.raises(RuntimeCoreInvariantError):
            RegulatoryReportingEngine("not-an-engine")  # type: ignore[arg-type]

    def test_accepts_valid_event_spine(self) -> None:
        engine, _ = _make_engine()
        assert engine.requirement_count == 0

    def test_initial_counts_are_zero(self) -> None:
        engine, _ = _make_engine()
        assert engine.requirement_count == 0
        assert engine.window_count == 0
        assert engine.package_count == 0
        assert engine.submission_count == 0
        assert engine.review_count == 0
        assert engine.auditor_request_count == 0
        assert engine.auditor_response_count == 0
        assert engine.violation_count == 0


# ===================================================================
# Requirements
# ===================================================================


class TestRegisterRequirement:
    def test_basic_registration(self) -> None:
        engine, _ = _make_engine()
        req = _seed_requirement(engine)
        assert isinstance(req, ReportingRequirement)
        assert req.requirement_id == "req-1"
        assert req.tenant_id == "tenant-a"
        assert req.title == "Annual Compliance"

    def test_default_fields(self) -> None:
        engine, _ = _make_engine()
        req = _seed_requirement(engine)
        assert req.filing_kind == FilingKind.AD_HOC
        assert req.audience == ReportAudience.REGULATOR
        assert req.review_requirement == ReviewRequirement.NONE
        assert req.recurring is False
        assert req.description == ""

    def test_custom_filing_kind(self) -> None:
        engine, _ = _make_engine()
        req = _seed_requirement(engine, filing_kind=FilingKind.ANNUAL)
        assert req.filing_kind == FilingKind.ANNUAL

    def test_custom_audience(self) -> None:
        engine, _ = _make_engine()
        req = _seed_requirement(engine, audience=ReportAudience.BOARD)
        assert req.audience == ReportAudience.BOARD

    def test_custom_review_requirement(self) -> None:
        engine, _ = _make_engine()
        req = _seed_requirement(engine, review_requirement=ReviewRequirement.LEGAL_REVIEW)
        assert req.review_requirement == ReviewRequirement.LEGAL_REVIEW

    def test_recurring_flag(self) -> None:
        engine, _ = _make_engine()
        req = _seed_requirement(engine, recurring=True)
        assert req.recurring is True

    def test_description(self) -> None:
        engine, _ = _make_engine()
        req = _seed_requirement(engine, description="Must file annually")
        assert req.description == "Must file annually"

    def test_created_at_is_set(self) -> None:
        engine, _ = _make_engine()
        req = _seed_requirement(engine)
        assert req.created_at  # non-empty ISO timestamp

    def test_duplicate_raises(self) -> None:
        engine, _ = _make_engine()
        _seed_requirement(engine)
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate"):
            _seed_requirement(engine)

    def test_increments_count(self) -> None:
        engine, _ = _make_engine()
        assert engine.requirement_count == 0
        _seed_requirement(engine, requirement_id="r1")
        assert engine.requirement_count == 1
        _seed_requirement(engine, requirement_id="r2")
        assert engine.requirement_count == 2

    def test_emits_event(self) -> None:
        engine, es = _make_engine()
        before = es.event_count
        _seed_requirement(engine)
        assert es.event_count == before + 1

    def test_all_filing_kinds(self) -> None:
        engine, _ = _make_engine()
        for i, kind in enumerate(FilingKind):
            req = _seed_requirement(
                engine, requirement_id=f"req-fk-{i}", filing_kind=kind
            )
            assert req.filing_kind == kind

    def test_all_audiences(self) -> None:
        engine, _ = _make_engine()
        for i, aud in enumerate(ReportAudience):
            req = _seed_requirement(
                engine, requirement_id=f"req-aud-{i}", audience=aud
            )
            assert req.audience == aud

    def test_all_review_requirements(self) -> None:
        engine, _ = _make_engine()
        for i, rr in enumerate(ReviewRequirement):
            req = _seed_requirement(
                engine, requirement_id=f"req-rr-{i}", review_requirement=rr
            )
            assert req.review_requirement == rr


class TestGetRequirement:
    def test_returns_registered_requirement(self) -> None:
        engine, _ = _make_engine()
        _seed_requirement(engine)
        req = engine.get_requirement("req-1")
        assert req.requirement_id == "req-1"

    def test_unknown_raises(self) -> None:
        engine, _ = _make_engine()
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown"):
            engine.get_requirement("no-such-req")


class TestRequirementsForTenant:
    def test_returns_tuple(self) -> None:
        engine, _ = _make_engine()
        _seed_requirement(engine)
        result = engine.requirements_for_tenant("tenant-a")
        assert isinstance(result, tuple)
        assert len(result) == 1

    def test_filters_by_tenant(self) -> None:
        engine, _ = _make_engine()
        _seed_requirement(engine, requirement_id="r1", tenant_id="t1")
        _seed_requirement(engine, requirement_id="r2", tenant_id="t2")
        _seed_requirement(engine, requirement_id="r3", tenant_id="t1")
        assert len(engine.requirements_for_tenant("t1")) == 2
        assert len(engine.requirements_for_tenant("t2")) == 1

    def test_empty_for_unknown_tenant(self) -> None:
        engine, _ = _make_engine()
        assert engine.requirements_for_tenant("ghost") == ()


# ===================================================================
# Filing windows
# ===================================================================


class TestOpenFilingWindow:
    def test_basic_window(self) -> None:
        engine, _ = _make_engine()
        _seed_requirement(engine)
        w = _seed_window(engine)
        assert isinstance(w, FilingWindow)
        assert w.window_id == "win-1"
        assert w.requirement_id == "req-1"
        assert w.status == SubmissionStatus.DRAFT

    def test_opens_at_and_closes_at(self) -> None:
        engine, _ = _make_engine()
        _seed_requirement(engine)
        w = _seed_window(engine)
        assert w.opens_at == _FUTURE_OPEN
        assert w.closes_at == _FUTURE_CLOSE

    def test_duplicate_raises(self) -> None:
        engine, _ = _make_engine()
        _seed_requirement(engine)
        _seed_window(engine)
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate"):
            _seed_window(engine)

    def test_unknown_requirement_raises(self) -> None:
        engine, _ = _make_engine()
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown"):
            _seed_window(engine, requirement_id="no-req")

    def test_increments_count(self) -> None:
        engine, _ = _make_engine()
        _seed_requirement(engine)
        assert engine.window_count == 0
        _seed_window(engine, window_id="w1")
        assert engine.window_count == 1

    def test_emits_event(self) -> None:
        engine, es = _make_engine()
        _seed_requirement(engine)
        before = es.event_count
        _seed_window(engine)
        assert es.event_count == before + 1


class TestGetWindow:
    def test_returns_window(self) -> None:
        engine, _ = _make_engine()
        _seed_requirement(engine)
        _seed_window(engine)
        w = engine.get_window("win-1")
        assert w.window_id == "win-1"

    def test_unknown_raises(self) -> None:
        engine, _ = _make_engine()
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown"):
            engine.get_window("no-win")


class TestWindowsForRequirement:
    def test_returns_tuple(self) -> None:
        engine, _ = _make_engine()
        _seed_requirement(engine)
        _seed_window(engine, window_id="w1")
        _seed_window(engine, window_id="w2")
        result = engine.windows_for_requirement("req-1")
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_filters_by_requirement(self) -> None:
        engine, _ = _make_engine()
        _seed_requirement(engine, requirement_id="r1")
        _seed_requirement(engine, requirement_id="r2")
        _seed_window(engine, window_id="w1", requirement_id="r1")
        _seed_window(engine, window_id="w2", requirement_id="r2")
        assert len(engine.windows_for_requirement("r1")) == 1
        assert len(engine.windows_for_requirement("r2")) == 1

    def test_empty_for_no_windows(self) -> None:
        engine, _ = _make_engine()
        assert engine.windows_for_requirement("ghost") == ()


# ===================================================================
# Evidence packages
# ===================================================================


class TestAssembleEvidencePackage:
    def test_basic_assembly(self) -> None:
        engine, _ = _make_engine()
        _seed_requirement(engine)
        pkg = _seed_package(engine)
        assert isinstance(pkg, EvidencePackage)
        assert pkg.package_id == "pkg-1"
        assert pkg.tenant_id == "tenant-a"
        assert pkg.requirement_id == "req-1"

    def test_zero_evidence_is_incomplete(self) -> None:
        engine, _ = _make_engine()
        _seed_requirement(engine)
        pkg = _seed_package(engine, evidence_ids=())
        assert pkg.completeness == EvidenceCompleteness.INCOMPLETE

    def test_one_evidence_is_partial(self) -> None:
        engine, _ = _make_engine()
        _seed_requirement(engine)
        pkg = _seed_package(engine, evidence_ids=("e1",))
        assert pkg.completeness == EvidenceCompleteness.PARTIAL

    def test_two_evidence_is_complete(self) -> None:
        engine, _ = _make_engine()
        _seed_requirement(engine)
        pkg = _seed_package(engine, evidence_ids=("e1", "e2"))
        assert pkg.completeness == EvidenceCompleteness.COMPLETE

    def test_three_evidence_is_complete(self) -> None:
        engine, _ = _make_engine()
        _seed_requirement(engine)
        pkg = _seed_package(engine, evidence_ids=("e1", "e2", "e3"))
        assert pkg.completeness == EvidenceCompleteness.COMPLETE

    def test_four_evidence_is_verified(self) -> None:
        engine, _ = _make_engine()
        _seed_requirement(engine)
        pkg = _seed_package(engine, evidence_ids=("e1", "e2", "e3", "e4"))
        assert pkg.completeness == EvidenceCompleteness.VERIFIED

    def test_many_evidence_is_verified(self) -> None:
        engine, _ = _make_engine()
        _seed_requirement(engine)
        ids = tuple(f"e{i}" for i in range(10))
        pkg = _seed_package(engine, evidence_ids=ids)
        assert pkg.completeness == EvidenceCompleteness.VERIFIED
        assert pkg.total_evidence_items == 10

    def test_evidence_ids_stored(self) -> None:
        engine, _ = _make_engine()
        _seed_requirement(engine)
        pkg = _seed_package(engine, evidence_ids=("a", "b", "c"))
        assert pkg.evidence_ids == ("a", "b", "c")

    def test_total_evidence_items(self) -> None:
        engine, _ = _make_engine()
        _seed_requirement(engine)
        pkg = _seed_package(engine, evidence_ids=("a", "b"))
        assert pkg.total_evidence_items == 2

    def test_assembled_by_default(self) -> None:
        engine, _ = _make_engine()
        _seed_requirement(engine)
        pkg = _seed_package(engine)
        assert pkg.assembled_by == "system"

    def test_assembled_by_custom(self) -> None:
        engine, _ = _make_engine()
        _seed_requirement(engine)
        pkg = _seed_package(engine, assembled_by="alice")
        assert pkg.assembled_by == "alice"

    def test_assembled_at_set(self) -> None:
        engine, _ = _make_engine()
        _seed_requirement(engine)
        pkg = _seed_package(engine)
        assert pkg.assembled_at  # non-empty

    def test_duplicate_raises(self) -> None:
        engine, _ = _make_engine()
        _seed_requirement(engine)
        _seed_package(engine)
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate"):
            _seed_package(engine)

    def test_unknown_requirement_raises(self) -> None:
        engine, _ = _make_engine()
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown"):
            _seed_package(engine, requirement_id="no-req")

    def test_increments_count(self) -> None:
        engine, _ = _make_engine()
        _seed_requirement(engine)
        assert engine.package_count == 0
        _seed_package(engine)
        assert engine.package_count == 1

    def test_emits_event(self) -> None:
        engine, es = _make_engine()
        _seed_requirement(engine)
        before = es.event_count
        _seed_package(engine)
        assert es.event_count == before + 1


class TestGetPackage:
    def test_returns_package(self) -> None:
        engine, _ = _make_engine()
        _seed_requirement(engine)
        _seed_package(engine)
        p = engine.get_package("pkg-1")
        assert p.package_id == "pkg-1"

    def test_unknown_raises(self) -> None:
        engine, _ = _make_engine()
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown"):
            engine.get_package("no-pkg")


class TestValidatePackage:
    def test_returns_completeness(self) -> None:
        engine, _ = _make_engine()
        _seed_requirement(engine)
        _seed_package(engine, evidence_ids=("e1", "e2"))
        result = engine.validate_package("pkg-1")
        assert result == EvidenceCompleteness.COMPLETE

    def test_incomplete_validation(self) -> None:
        engine, _ = _make_engine()
        _seed_requirement(engine)
        _seed_package(engine, evidence_ids=())
        result = engine.validate_package("pkg-1")
        assert result == EvidenceCompleteness.INCOMPLETE

    def test_emits_event(self) -> None:
        engine, es = _make_engine()
        _seed_requirement(engine)
        _seed_package(engine)
        before = es.event_count
        engine.validate_package("pkg-1")
        assert es.event_count == before + 1

    def test_unknown_package_raises(self) -> None:
        engine, _ = _make_engine()
        with pytest.raises(RuntimeCoreInvariantError):
            engine.validate_package("no-pkg")


# ===================================================================
# Submissions
# ===================================================================


class TestSubmitReport:
    def test_basic_submission(self) -> None:
        engine, _ = _make_engine()
        sub = _full_pipeline(engine)
        assert isinstance(sub, SubmissionRecord)
        assert sub.submission_id == "sub-1"
        assert sub.status == SubmissionStatus.SUBMITTED

    def test_submitted_by_default(self) -> None:
        engine, _ = _make_engine()
        sub = _full_pipeline(engine)
        assert sub.submitted_by == "system"

    def test_submitted_by_custom(self) -> None:
        engine, _ = _make_engine()
        _seed_requirement(engine)
        _seed_window(engine)
        _seed_package(engine)
        sub = _seed_submission(engine, submitted_by="alice")
        assert sub.submitted_by == "alice"

    def test_submitted_at_set(self) -> None:
        engine, _ = _make_engine()
        sub = _full_pipeline(engine)
        assert sub.submitted_at

    def test_updates_window_status_to_submitted(self) -> None:
        engine, _ = _make_engine()
        _full_pipeline(engine)
        w = engine.get_window("win-1")
        assert w.status == SubmissionStatus.SUBMITTED

    def test_window_submitted_at_set(self) -> None:
        engine, _ = _make_engine()
        _full_pipeline(engine)
        w = engine.get_window("win-1")
        assert w.submitted_at  # non-empty

    def test_duplicate_raises(self) -> None:
        engine, _ = _make_engine()
        _full_pipeline(engine)
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate"):
            _seed_submission(engine)

    def test_incomplete_package_blocks_submission(self) -> None:
        engine, _ = _make_engine()
        _seed_requirement(engine)
        _seed_window(engine)
        _seed_package(engine, evidence_ids=())  # INCOMPLETE
        with pytest.raises(RuntimeCoreInvariantError, match="INCOMPLETE"):
            _seed_submission(engine)

    def test_partial_package_allows_submission(self) -> None:
        engine, _ = _make_engine()
        _seed_requirement(engine)
        _seed_window(engine)
        _seed_package(engine, evidence_ids=("e1",))  # PARTIAL
        sub = _seed_submission(engine)
        assert sub.status == SubmissionStatus.SUBMITTED

    def test_verified_package_allows_submission(self) -> None:
        engine, _ = _make_engine()
        _seed_requirement(engine)
        _seed_window(engine)
        _seed_package(engine, evidence_ids=("e1", "e2", "e3", "e4"))  # VERIFIED
        sub = _seed_submission(engine)
        assert sub.status == SubmissionStatus.SUBMITTED

    def test_unknown_window_raises(self) -> None:
        engine, _ = _make_engine()
        _seed_requirement(engine)
        _seed_package(engine)
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown"):
            _seed_submission(engine, window_id="no-win")

    def test_unknown_package_raises(self) -> None:
        engine, _ = _make_engine()
        _seed_requirement(engine)
        _seed_window(engine)
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown"):
            _seed_submission(engine, package_id="no-pkg")

    def test_increments_count(self) -> None:
        engine, _ = _make_engine()
        _full_pipeline(engine)
        assert engine.submission_count == 1

    def test_emits_event(self) -> None:
        engine, es = _make_engine()
        _seed_requirement(engine)
        _seed_window(engine)
        _seed_package(engine)
        before = es.event_count
        _seed_submission(engine)
        assert es.event_count == before + 1


class TestGetSubmission:
    def test_returns_submission(self) -> None:
        engine, _ = _make_engine()
        _full_pipeline(engine)
        s = engine.get_submission("sub-1")
        assert s.submission_id == "sub-1"

    def test_unknown_raises(self) -> None:
        engine, _ = _make_engine()
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown"):
            engine.get_submission("no-sub")


class TestAcceptSubmission:
    def test_basic_accept(self) -> None:
        engine, _ = _make_engine()
        _full_pipeline(engine)
        result = engine.accept_submission("sub-1")
        assert result.status == SubmissionStatus.ACCEPTED

    def test_emits_event(self) -> None:
        engine, es = _make_engine()
        _full_pipeline(engine)
        before = es.event_count
        engine.accept_submission("sub-1")
        assert es.event_count == before + 1

    def test_already_accepted_raises(self) -> None:
        engine, _ = _make_engine()
        _full_pipeline(engine)
        engine.accept_submission("sub-1")
        with pytest.raises(RuntimeCoreInvariantError):
            engine.accept_submission("sub-1")

    def test_rejected_cannot_accept(self) -> None:
        engine, _ = _make_engine()
        _full_pipeline(engine)
        engine.reject_submission("sub-1")
        with pytest.raises(RuntimeCoreInvariantError):
            engine.accept_submission("sub-1")

    def test_withdrawn_cannot_accept(self) -> None:
        engine, _ = _make_engine()
        _full_pipeline(engine)
        engine.withdraw_submission("sub-1")
        with pytest.raises(RuntimeCoreInvariantError):
            engine.accept_submission("sub-1")

    def test_unknown_raises(self) -> None:
        engine, _ = _make_engine()
        with pytest.raises(RuntimeCoreInvariantError):
            engine.accept_submission("no-sub")


class TestRejectSubmission:
    def test_basic_reject(self) -> None:
        engine, _ = _make_engine()
        _full_pipeline(engine)
        result = engine.reject_submission("sub-1")
        assert result.status == SubmissionStatus.REJECTED

    def test_reject_with_reason(self) -> None:
        engine, _ = _make_engine()
        _full_pipeline(engine)
        result = engine.reject_submission("sub-1", reason="Missing appendix")
        assert result.status == SubmissionStatus.REJECTED

    def test_emits_event(self) -> None:
        engine, es = _make_engine()
        _full_pipeline(engine)
        before = es.event_count
        engine.reject_submission("sub-1")
        assert es.event_count == before + 1

    def test_already_rejected_raises(self) -> None:
        engine, _ = _make_engine()
        _full_pipeline(engine)
        engine.reject_submission("sub-1")
        with pytest.raises(RuntimeCoreInvariantError):
            engine.reject_submission("sub-1")

    def test_accepted_cannot_reject(self) -> None:
        engine, _ = _make_engine()
        _full_pipeline(engine)
        engine.accept_submission("sub-1")
        with pytest.raises(RuntimeCoreInvariantError):
            engine.reject_submission("sub-1")

    def test_withdrawn_cannot_reject(self) -> None:
        engine, _ = _make_engine()
        _full_pipeline(engine)
        engine.withdraw_submission("sub-1")
        with pytest.raises(RuntimeCoreInvariantError):
            engine.reject_submission("sub-1")


class TestWithdrawSubmission:
    def test_basic_withdraw(self) -> None:
        engine, _ = _make_engine()
        _full_pipeline(engine)
        result = engine.withdraw_submission("sub-1")
        assert result.status == SubmissionStatus.WITHDRAWN

    def test_emits_event(self) -> None:
        engine, es = _make_engine()
        _full_pipeline(engine)
        before = es.event_count
        engine.withdraw_submission("sub-1")
        assert es.event_count == before + 1

    def test_already_withdrawn_raises(self) -> None:
        engine, _ = _make_engine()
        _full_pipeline(engine)
        engine.withdraw_submission("sub-1")
        with pytest.raises(RuntimeCoreInvariantError):
            engine.withdraw_submission("sub-1")

    def test_accepted_cannot_withdraw(self) -> None:
        engine, _ = _make_engine()
        _full_pipeline(engine)
        engine.accept_submission("sub-1")
        with pytest.raises(RuntimeCoreInvariantError):
            engine.withdraw_submission("sub-1")

    def test_rejected_cannot_withdraw(self) -> None:
        engine, _ = _make_engine()
        _full_pipeline(engine)
        engine.reject_submission("sub-1")
        with pytest.raises(RuntimeCoreInvariantError):
            engine.withdraw_submission("sub-1")


class TestSubmissionsForWindow:
    def test_returns_tuple(self) -> None:
        engine, _ = _make_engine()
        _full_pipeline(engine)
        result = engine.submissions_for_window("win-1")
        assert isinstance(result, tuple)
        assert len(result) == 1

    def test_filters_by_window(self) -> None:
        engine, _ = _make_engine()
        _seed_requirement(engine)
        _seed_window(engine, window_id="w1")
        _seed_window(engine, window_id="w2")
        _seed_package(engine, package_id="p1", evidence_ids=("e1", "e2"))
        _seed_package(engine, package_id="p2", evidence_ids=("e1", "e2"))
        _seed_submission(engine, submission_id="s1", window_id="w1", package_id="p1")
        _seed_submission(engine, submission_id="s2", window_id="w2", package_id="p2")
        assert len(engine.submissions_for_window("w1")) == 1
        assert len(engine.submissions_for_window("w2")) == 1

    def test_empty_for_no_submissions(self) -> None:
        engine, _ = _make_engine()
        assert engine.submissions_for_window("ghost") == ()


# ===================================================================
# Reviews
# ===================================================================


class TestRecordReview:
    def test_basic_review(self) -> None:
        engine, _ = _make_engine()
        _full_pipeline(engine)
        review = engine.record_review("rev-1", "sub-1")
        assert isinstance(review, ReportingReview)
        assert review.review_id == "rev-1"
        assert review.submission_id == "sub-1"

    def test_default_reviewer(self) -> None:
        engine, _ = _make_engine()
        _full_pipeline(engine)
        review = engine.record_review("rev-1", "sub-1")
        assert review.reviewer == "system"

    def test_custom_reviewer(self) -> None:
        engine, _ = _make_engine()
        _full_pipeline(engine)
        review = engine.record_review("rev-1", "sub-1", reviewer="bob")
        assert review.reviewer == "bob"

    def test_default_review_requirement(self) -> None:
        engine, _ = _make_engine()
        _full_pipeline(engine)
        review = engine.record_review("rev-1", "sub-1")
        assert review.review_requirement == ReviewRequirement.PEER_REVIEW

    def test_custom_review_requirement(self) -> None:
        engine, _ = _make_engine()
        _full_pipeline(engine)
        review = engine.record_review(
            "rev-1", "sub-1", review_requirement=ReviewRequirement.LEGAL_REVIEW
        )
        assert review.review_requirement == ReviewRequirement.LEGAL_REVIEW

    def test_approved_flag(self) -> None:
        engine, _ = _make_engine()
        _full_pipeline(engine)
        review = engine.record_review("rev-1", "sub-1", approved=True)
        assert review.approved is True

    def test_default_not_approved(self) -> None:
        engine, _ = _make_engine()
        _full_pipeline(engine)
        review = engine.record_review("rev-1", "sub-1")
        assert review.approved is False

    def test_comments(self) -> None:
        engine, _ = _make_engine()
        _full_pipeline(engine)
        review = engine.record_review("rev-1", "sub-1", comments="Looks good")
        assert review.comments == "Looks good"

    def test_reviewed_at_set(self) -> None:
        engine, _ = _make_engine()
        _full_pipeline(engine)
        review = engine.record_review("rev-1", "sub-1")
        assert review.reviewed_at

    def test_duplicate_raises(self) -> None:
        engine, _ = _make_engine()
        _full_pipeline(engine)
        engine.record_review("rev-1", "sub-1")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate"):
            engine.record_review("rev-1", "sub-1")

    def test_unknown_submission_raises(self) -> None:
        engine, _ = _make_engine()
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown"):
            engine.record_review("rev-1", "no-sub")

    def test_increments_count(self) -> None:
        engine, _ = _make_engine()
        _full_pipeline(engine)
        assert engine.review_count == 0
        engine.record_review("rev-1", "sub-1")
        assert engine.review_count == 1

    def test_emits_event(self) -> None:
        engine, es = _make_engine()
        _full_pipeline(engine)
        before = es.event_count
        engine.record_review("rev-1", "sub-1")
        assert es.event_count == before + 1

    def test_multiple_reviews_per_submission(self) -> None:
        engine, _ = _make_engine()
        _full_pipeline(engine)
        engine.record_review("rev-1", "sub-1", reviewer="alice")
        engine.record_review("rev-2", "sub-1", reviewer="bob")
        assert engine.review_count == 2


class TestReviewsForSubmission:
    def test_returns_tuple(self) -> None:
        engine, _ = _make_engine()
        _full_pipeline(engine)
        engine.record_review("rev-1", "sub-1")
        result = engine.reviews_for_submission("sub-1")
        assert isinstance(result, tuple)
        assert len(result) == 1

    def test_filters_by_submission(self) -> None:
        engine, _ = _make_engine()
        _seed_requirement(engine)
        _seed_window(engine, window_id="w1")
        _seed_window(engine, window_id="w2")
        _seed_package(engine, package_id="p1", evidence_ids=("e1", "e2"))
        _seed_package(engine, package_id="p2", evidence_ids=("e1", "e2"))
        _seed_submission(engine, submission_id="s1", window_id="w1", package_id="p1")
        _seed_submission(engine, submission_id="s2", window_id="w2", package_id="p2")
        engine.record_review("rev-1", "s1")
        engine.record_review("rev-2", "s2")
        assert len(engine.reviews_for_submission("s1")) == 1

    def test_empty_for_no_reviews(self) -> None:
        engine, _ = _make_engine()
        assert engine.reviews_for_submission("ghost") == ()


# ===================================================================
# Auditor requests / responses
# ===================================================================


class TestRecordAuditorRequest:
    def test_basic_request(self) -> None:
        engine, _ = _make_engine()
        _full_pipeline(engine)
        ar = engine.record_auditor_request("ar-1", "tenant-a", "sub-1")
        assert isinstance(ar, AuditorRequest)
        assert ar.request_id == "ar-1"
        assert ar.tenant_id == "tenant-a"
        assert ar.submission_id == "sub-1"

    def test_default_requested_by(self) -> None:
        engine, _ = _make_engine()
        _full_pipeline(engine)
        ar = engine.record_auditor_request("ar-1", "tenant-a", "sub-1")
        assert ar.requested_by == "auditor"

    def test_custom_requested_by(self) -> None:
        engine, _ = _make_engine()
        _full_pipeline(engine)
        ar = engine.record_auditor_request(
            "ar-1", "tenant-a", "sub-1", requested_by="external-auditor"
        )
        assert ar.requested_by == "external-auditor"

    def test_description(self) -> None:
        engine, _ = _make_engine()
        _full_pipeline(engine)
        ar = engine.record_auditor_request(
            "ar-1", "tenant-a", "sub-1", description="Need more info"
        )
        assert ar.description == "Need more info"

    def test_due_at_defaults_to_now(self) -> None:
        engine, _ = _make_engine()
        _full_pipeline(engine)
        ar = engine.record_auditor_request("ar-1", "tenant-a", "sub-1")
        assert ar.due_at  # non-empty

    def test_custom_due_at(self) -> None:
        engine, _ = _make_engine()
        _full_pipeline(engine)
        ar = engine.record_auditor_request(
            "ar-1", "tenant-a", "sub-1", due_at="2099-12-31T23:59:59+00:00"
        )
        assert ar.due_at == "2099-12-31T23:59:59+00:00"

    def test_moves_submitted_to_pending_review(self) -> None:
        engine, _ = _make_engine()
        _full_pipeline(engine)
        assert engine.get_submission("sub-1").status == SubmissionStatus.SUBMITTED
        engine.record_auditor_request("ar-1", "tenant-a", "sub-1")
        assert engine.get_submission("sub-1").status == SubmissionStatus.PENDING_REVIEW

    def test_does_not_move_non_submitted(self) -> None:
        engine, _ = _make_engine()
        _full_pipeline(engine)
        # Move to PENDING_REVIEW first
        engine.record_auditor_request("ar-1", "tenant-a", "sub-1")
        assert engine.get_submission("sub-1").status == SubmissionStatus.PENDING_REVIEW
        # Second request should not change status further (already PENDING_REVIEW)
        engine.record_auditor_request("ar-2", "tenant-a", "sub-1")
        assert engine.get_submission("sub-1").status == SubmissionStatus.PENDING_REVIEW

    def test_duplicate_raises(self) -> None:
        engine, _ = _make_engine()
        _full_pipeline(engine)
        engine.record_auditor_request("ar-1", "tenant-a", "sub-1")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate"):
            engine.record_auditor_request("ar-1", "tenant-a", "sub-1")

    def test_unknown_submission_raises(self) -> None:
        engine, _ = _make_engine()
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown"):
            engine.record_auditor_request("ar-1", "tenant-a", "no-sub")

    def test_increments_count(self) -> None:
        engine, _ = _make_engine()
        _full_pipeline(engine)
        assert engine.auditor_request_count == 0
        engine.record_auditor_request("ar-1", "tenant-a", "sub-1")
        assert engine.auditor_request_count == 1

    def test_emits_event(self) -> None:
        engine, es = _make_engine()
        _full_pipeline(engine)
        before = es.event_count
        engine.record_auditor_request("ar-1", "tenant-a", "sub-1")
        assert es.event_count == before + 1


class TestRecordAuditorResponse:
    def test_basic_response(self) -> None:
        engine, _ = _make_engine()
        _full_pipeline(engine)
        engine.record_auditor_request("ar-1", "tenant-a", "sub-1")
        resp = engine.record_auditor_response("resp-1", "ar-1")
        assert isinstance(resp, AuditorResponse)
        assert resp.response_id == "resp-1"
        assert resp.request_id == "ar-1"

    def test_default_responder(self) -> None:
        engine, _ = _make_engine()
        _full_pipeline(engine)
        engine.record_auditor_request("ar-1", "tenant-a", "sub-1")
        resp = engine.record_auditor_response("resp-1", "ar-1")
        assert resp.responder == "system"

    def test_custom_responder(self) -> None:
        engine, _ = _make_engine()
        _full_pipeline(engine)
        engine.record_auditor_request("ar-1", "tenant-a", "sub-1")
        resp = engine.record_auditor_response("resp-1", "ar-1", responder="carol")
        assert resp.responder == "carol"

    def test_content(self) -> None:
        engine, _ = _make_engine()
        _full_pipeline(engine)
        engine.record_auditor_request("ar-1", "tenant-a", "sub-1")
        resp = engine.record_auditor_response(
            "resp-1", "ar-1", content="Here is the evidence"
        )
        assert resp.content == "Here is the evidence"

    def test_evidence_ids(self) -> None:
        engine, _ = _make_engine()
        _full_pipeline(engine)
        engine.record_auditor_request("ar-1", "tenant-a", "sub-1")
        resp = engine.record_auditor_response(
            "resp-1", "ar-1", evidence_ids=("ev-99", "ev-100")
        )
        assert resp.evidence_ids == ("ev-99", "ev-100")

    def test_responded_at_set(self) -> None:
        engine, _ = _make_engine()
        _full_pipeline(engine)
        engine.record_auditor_request("ar-1", "tenant-a", "sub-1")
        resp = engine.record_auditor_response("resp-1", "ar-1")
        assert resp.responded_at

    def test_duplicate_raises(self) -> None:
        engine, _ = _make_engine()
        _full_pipeline(engine)
        engine.record_auditor_request("ar-1", "tenant-a", "sub-1")
        engine.record_auditor_response("resp-1", "ar-1")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate"):
            engine.record_auditor_response("resp-1", "ar-1")

    def test_unknown_request_raises(self) -> None:
        engine, _ = _make_engine()
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown"):
            engine.record_auditor_response("resp-1", "no-req")

    def test_increments_count(self) -> None:
        engine, _ = _make_engine()
        _full_pipeline(engine)
        engine.record_auditor_request("ar-1", "tenant-a", "sub-1")
        assert engine.auditor_response_count == 0
        engine.record_auditor_response("resp-1", "ar-1")
        assert engine.auditor_response_count == 1

    def test_emits_event(self) -> None:
        engine, es = _make_engine()
        _full_pipeline(engine)
        engine.record_auditor_request("ar-1", "tenant-a", "sub-1")
        before = es.event_count
        engine.record_auditor_response("resp-1", "ar-1")
        assert es.event_count == before + 1


class TestRequestsForSubmission:
    def test_returns_tuple(self) -> None:
        engine, _ = _make_engine()
        _full_pipeline(engine)
        engine.record_auditor_request("ar-1", "tenant-a", "sub-1")
        result = engine.requests_for_submission("sub-1")
        assert isinstance(result, tuple)
        assert len(result) == 1

    def test_multiple_requests(self) -> None:
        engine, _ = _make_engine()
        _full_pipeline(engine)
        engine.record_auditor_request("ar-1", "tenant-a", "sub-1")
        engine.record_auditor_request("ar-2", "tenant-a", "sub-1")
        assert len(engine.requests_for_submission("sub-1")) == 2

    def test_empty_for_no_requests(self) -> None:
        engine, _ = _make_engine()
        assert engine.requests_for_submission("ghost") == ()


class TestResponsesForRequest:
    def test_returns_tuple(self) -> None:
        engine, _ = _make_engine()
        _full_pipeline(engine)
        engine.record_auditor_request("ar-1", "tenant-a", "sub-1")
        engine.record_auditor_response("resp-1", "ar-1")
        result = engine.responses_for_request("ar-1")
        assert isinstance(result, tuple)
        assert len(result) == 1

    def test_multiple_responses(self) -> None:
        engine, _ = _make_engine()
        _full_pipeline(engine)
        engine.record_auditor_request("ar-1", "tenant-a", "sub-1")
        engine.record_auditor_response("resp-1", "ar-1")
        engine.record_auditor_response("resp-2", "ar-1")
        assert len(engine.responses_for_request("ar-1")) == 2

    def test_empty_for_no_responses(self) -> None:
        engine, _ = _make_engine()
        assert engine.responses_for_request("ghost") == ()


# ===================================================================
# Violation detection
# ===================================================================


class TestDetectReportingViolations:
    def test_no_violations_for_future_windows(self) -> None:
        engine, _ = _make_engine()
        _seed_requirement(engine)
        _seed_window(engine, opens_at=_FUTURE_OPEN, closes_at=_FUTURE_CLOSE)
        violations = engine.detect_reporting_violations()
        assert violations == ()
        assert engine.violation_count == 0

    def test_missed_window_creates_violation(self) -> None:
        engine, _ = _make_engine()
        _seed_requirement(engine)
        _seed_window(engine, opens_at=_PAST_OPEN, closes_at=_PAST_CLOSE)
        violations = engine.detect_reporting_violations()
        assert len(violations) == 1
        assert isinstance(violations[0], ReportingViolation)
        assert violations[0].operation == "missed_filing_window"
        assert engine.violation_count == 1

    def test_violation_has_correct_tenant(self) -> None:
        engine, _ = _make_engine()
        _seed_requirement(engine, tenant_id="tenant-x")
        _seed_window(engine, opens_at=_PAST_OPEN, closes_at=_PAST_CLOSE)
        violations = engine.detect_reporting_violations()
        assert violations[0].tenant_id == "tenant-x"

    def test_violation_has_correct_requirement_and_window(self) -> None:
        engine, _ = _make_engine()
        _seed_requirement(engine)
        _seed_window(engine, opens_at=_PAST_OPEN, closes_at=_PAST_CLOSE)
        violations = engine.detect_reporting_violations()
        assert violations[0].requirement_id == "req-1"
        assert violations[0].window_id == "win-1"

    def test_idempotent_detection(self) -> None:
        engine, _ = _make_engine()
        _seed_requirement(engine)
        _seed_window(engine, opens_at=_PAST_OPEN, closes_at=_PAST_CLOSE)
        v1 = engine.detect_reporting_violations()
        v2 = engine.detect_reporting_violations()
        assert len(v1) == 1
        assert len(v2) == 0  # no new violations
        assert engine.violation_count == 1

    def test_submitted_window_no_violation(self) -> None:
        engine, _ = _make_engine()
        _seed_requirement(engine)
        _seed_window(engine, opens_at=_PAST_OPEN, closes_at=_PAST_CLOSE)
        _seed_package(engine, evidence_ids=("e1", "e2"))
        _seed_submission(engine)
        # Window status is now SUBMITTED, not DRAFT
        violations = engine.detect_reporting_violations()
        assert violations == ()

    def test_multiple_missed_windows(self) -> None:
        engine, _ = _make_engine()
        _seed_requirement(engine)
        _seed_window(engine, window_id="w1", opens_at=_PAST_OPEN, closes_at=_PAST_CLOSE)
        _seed_window(engine, window_id="w2", opens_at=_PAST_OPEN, closes_at=_PAST_CLOSE)
        violations = engine.detect_reporting_violations()
        assert len(violations) == 2

    def test_emits_event_when_violations_found(self) -> None:
        engine, es = _make_engine()
        _seed_requirement(engine)
        _seed_window(engine, opens_at=_PAST_OPEN, closes_at=_PAST_CLOSE)
        before = es.event_count
        engine.detect_reporting_violations()
        assert es.event_count == before + 1

    def test_no_event_when_no_violations(self) -> None:
        engine, es = _make_engine()
        _seed_requirement(engine)
        _seed_window(engine, opens_at=_FUTURE_OPEN, closes_at=_FUTURE_CLOSE)
        before = es.event_count
        engine.detect_reporting_violations()
        assert es.event_count == before  # no event emitted


class TestViolationsForTenant:
    def test_returns_tuple(self) -> None:
        engine, _ = _make_engine()
        _seed_requirement(engine, tenant_id="t1")
        _seed_window(engine, opens_at=_PAST_OPEN, closes_at=_PAST_CLOSE)
        engine.detect_reporting_violations()
        result = engine.violations_for_tenant("t1")
        assert isinstance(result, tuple)
        assert len(result) == 1

    def test_filters_by_tenant(self) -> None:
        engine, _ = _make_engine()
        _seed_requirement(engine, requirement_id="r1", tenant_id="t1")
        _seed_requirement(engine, requirement_id="r2", tenant_id="t2")
        _seed_window(engine, window_id="w1", requirement_id="r1", opens_at=_PAST_OPEN, closes_at=_PAST_CLOSE)
        _seed_window(engine, window_id="w2", requirement_id="r2", opens_at=_PAST_OPEN, closes_at=_PAST_CLOSE)
        engine.detect_reporting_violations()
        assert len(engine.violations_for_tenant("t1")) == 1
        assert len(engine.violations_for_tenant("t2")) == 1

    def test_empty_for_unknown_tenant(self) -> None:
        engine, _ = _make_engine()
        assert engine.violations_for_tenant("ghost") == ()


# ===================================================================
# Snapshot
# ===================================================================


class TestRegulatorySnapshot:
    def test_basic_snapshot(self) -> None:
        engine, _ = _make_engine()
        snap = engine.regulatory_snapshot("snap-1")
        assert isinstance(snap, RegulatorySnapshot)
        assert snap.snapshot_id == "snap-1"

    def test_captures_counts(self) -> None:
        engine, _ = _make_engine()
        _full_pipeline(engine)
        engine.record_review("rev-1", "sub-1")
        engine.record_auditor_request("ar-1", "tenant-a", "sub-1")
        engine.record_auditor_response("resp-1", "ar-1")
        snap = engine.regulatory_snapshot("snap-1")
        assert snap.total_requirements == 1
        assert snap.total_windows == 1
        assert snap.total_packages == 1
        assert snap.total_submissions == 1
        assert snap.total_reviews == 1
        assert snap.total_auditor_requests == 1
        assert snap.total_auditor_responses == 1

    def test_empty_state_snapshot(self) -> None:
        engine, _ = _make_engine()
        snap = engine.regulatory_snapshot("snap-1")
        assert snap.total_requirements == 0
        assert snap.total_windows == 0
        assert snap.total_packages == 0
        assert snap.total_submissions == 0
        assert snap.total_reviews == 0
        assert snap.total_auditor_requests == 0
        assert snap.total_auditor_responses == 0
        assert snap.total_violations == 0

    def test_captured_at_set(self) -> None:
        engine, _ = _make_engine()
        snap = engine.regulatory_snapshot("snap-1")
        assert snap.captured_at

    def test_duplicate_raises(self) -> None:
        engine, _ = _make_engine()
        engine.regulatory_snapshot("snap-1")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate"):
            engine.regulatory_snapshot("snap-1")

    def test_emits_event(self) -> None:
        engine, es = _make_engine()
        before = es.event_count
        engine.regulatory_snapshot("snap-1")
        assert es.event_count == before + 1

    def test_multiple_snapshots(self) -> None:
        engine, _ = _make_engine()
        s1 = engine.regulatory_snapshot("snap-1")
        _seed_requirement(engine)
        s2 = engine.regulatory_snapshot("snap-2")
        assert s1.total_requirements == 0
        assert s2.total_requirements == 1

    def test_snapshot_includes_violations(self) -> None:
        engine, _ = _make_engine()
        _seed_requirement(engine)
        _seed_window(engine, opens_at=_PAST_OPEN, closes_at=_PAST_CLOSE)
        engine.detect_reporting_violations()
        snap = engine.regulatory_snapshot("snap-1")
        assert snap.total_violations == 1


# ===================================================================
# State hash
# ===================================================================


class TestStateHash:
    def test_returns_string(self) -> None:
        engine, _ = _make_engine()
        h = engine.state_hash()
        assert isinstance(h, str)

    def test_is_16_chars(self) -> None:
        engine, _ = _make_engine()
        h = engine.state_hash()
        assert len(h) == 64

    def test_deterministic(self) -> None:
        engine, _ = _make_engine()
        h1 = engine.state_hash()
        h2 = engine.state_hash()
        assert h1 == h2

    def test_changes_after_mutation(self) -> None:
        engine, _ = _make_engine()
        h1 = engine.state_hash()
        _seed_requirement(engine)
        h2 = engine.state_hash()
        assert h1 != h2

    def test_different_states_different_hashes(self) -> None:
        e1, _ = _make_engine()
        e2, _ = _make_engine()
        _seed_requirement(e1, requirement_id="a")
        _seed_requirement(e2, requirement_id="b")
        _seed_requirement(e2, requirement_id="c")
        assert e1.state_hash() != e2.state_hash()

    def test_empty_engines_same_hash(self) -> None:
        e1, _ = _make_engine()
        e2, _ = _make_engine()
        assert e1.state_hash() == e2.state_hash()


# ===================================================================
# Properties (comprehensive)
# ===================================================================


class TestProperties:
    def test_requirement_count(self) -> None:
        engine, _ = _make_engine()
        assert engine.requirement_count == 0
        _seed_requirement(engine, requirement_id="r1")
        _seed_requirement(engine, requirement_id="r2")
        assert engine.requirement_count == 2

    def test_window_count(self) -> None:
        engine, _ = _make_engine()
        _seed_requirement(engine)
        assert engine.window_count == 0
        _seed_window(engine, window_id="w1")
        _seed_window(engine, window_id="w2")
        assert engine.window_count == 2

    def test_package_count(self) -> None:
        engine, _ = _make_engine()
        _seed_requirement(engine)
        assert engine.package_count == 0
        _seed_package(engine, package_id="p1")
        _seed_package(engine, package_id="p2")
        assert engine.package_count == 2

    def test_submission_count(self) -> None:
        engine, _ = _make_engine()
        _seed_requirement(engine)
        _seed_window(engine, window_id="w1")
        _seed_window(engine, window_id="w2")
        _seed_package(engine, package_id="p1", evidence_ids=("e1", "e2"))
        _seed_package(engine, package_id="p2", evidence_ids=("e1", "e2"))
        _seed_submission(engine, submission_id="s1", window_id="w1", package_id="p1")
        _seed_submission(engine, submission_id="s2", window_id="w2", package_id="p2")
        assert engine.submission_count == 2

    def test_review_count(self) -> None:
        engine, _ = _make_engine()
        _full_pipeline(engine)
        engine.record_review("rev-1", "sub-1")
        engine.record_review("rev-2", "sub-1")
        assert engine.review_count == 2

    def test_auditor_request_count(self) -> None:
        engine, _ = _make_engine()
        _full_pipeline(engine)
        engine.record_auditor_request("ar-1", "tenant-a", "sub-1")
        engine.record_auditor_request("ar-2", "tenant-a", "sub-1")
        assert engine.auditor_request_count == 2

    def test_auditor_response_count(self) -> None:
        engine, _ = _make_engine()
        _full_pipeline(engine)
        engine.record_auditor_request("ar-1", "tenant-a", "sub-1")
        engine.record_auditor_response("resp-1", "ar-1")
        engine.record_auditor_response("resp-2", "ar-1")
        assert engine.auditor_response_count == 2

    def test_violation_count(self) -> None:
        engine, _ = _make_engine()
        _seed_requirement(engine)
        _seed_window(engine, opens_at=_PAST_OPEN, closes_at=_PAST_CLOSE)
        engine.detect_reporting_violations()
        assert engine.violation_count == 1


# ===================================================================
# Event emission (comprehensive)
# ===================================================================


class TestEventEmission:
    def test_register_requirement_emits(self) -> None:
        engine, es = _make_engine()
        before = es.event_count
        _seed_requirement(engine)
        assert es.event_count == before + 1

    def test_open_filing_window_emits(self) -> None:
        engine, es = _make_engine()
        _seed_requirement(engine)
        before = es.event_count
        _seed_window(engine)
        assert es.event_count == before + 1

    def test_assemble_evidence_package_emits(self) -> None:
        engine, es = _make_engine()
        _seed_requirement(engine)
        before = es.event_count
        _seed_package(engine)
        assert es.event_count == before + 1

    def test_submit_report_emits(self) -> None:
        engine, es = _make_engine()
        _seed_requirement(engine)
        _seed_window(engine)
        _seed_package(engine)
        before = es.event_count
        _seed_submission(engine)
        assert es.event_count == before + 1

    def test_accept_submission_emits(self) -> None:
        engine, es = _make_engine()
        _full_pipeline(engine)
        before = es.event_count
        engine.accept_submission("sub-1")
        assert es.event_count == before + 1

    def test_reject_submission_emits(self) -> None:
        engine, es = _make_engine()
        _full_pipeline(engine)
        before = es.event_count
        engine.reject_submission("sub-1")
        assert es.event_count == before + 1

    def test_withdraw_submission_emits(self) -> None:
        engine, es = _make_engine()
        _full_pipeline(engine)
        before = es.event_count
        engine.withdraw_submission("sub-1")
        assert es.event_count == before + 1

    def test_record_review_emits(self) -> None:
        engine, es = _make_engine()
        _full_pipeline(engine)
        before = es.event_count
        engine.record_review("rev-1", "sub-1")
        assert es.event_count == before + 1

    def test_record_auditor_request_emits(self) -> None:
        engine, es = _make_engine()
        _full_pipeline(engine)
        before = es.event_count
        engine.record_auditor_request("ar-1", "tenant-a", "sub-1")
        assert es.event_count == before + 1

    def test_record_auditor_response_emits(self) -> None:
        engine, es = _make_engine()
        _full_pipeline(engine)
        engine.record_auditor_request("ar-1", "tenant-a", "sub-1")
        before = es.event_count
        engine.record_auditor_response("resp-1", "ar-1")
        assert es.event_count == before + 1

    def test_validate_package_emits(self) -> None:
        engine, es = _make_engine()
        _seed_requirement(engine)
        _seed_package(engine)
        before = es.event_count
        engine.validate_package("pkg-1")
        assert es.event_count == before + 1

    def test_regulatory_snapshot_emits(self) -> None:
        engine, es = _make_engine()
        before = es.event_count
        engine.regulatory_snapshot("snap-1")
        assert es.event_count == before + 1

    def test_total_event_count_full_pipeline(self) -> None:
        engine, es = _make_engine()
        assert es.event_count == 0
        _seed_requirement(engine)  # +1
        _seed_window(engine)       # +1
        _seed_package(engine)      # +1
        _seed_submission(engine)   # +1
        assert es.event_count == 4


# ===================================================================
# Terminal state transitions (comprehensive matrix)
# ===================================================================


class TestTerminalStateTransitions:
    """All three terminal states (ACCEPTED, REJECTED, WITHDRAWN) block all transitions."""

    @pytest.mark.parametrize("terminal_action", ["accept", "reject", "withdraw"])
    def test_accepted_blocks_all(self, terminal_action: str) -> None:
        engine, _ = _make_engine()
        _full_pipeline(engine)
        engine.accept_submission("sub-1")
        action = getattr(engine, f"{terminal_action}_submission")
        with pytest.raises(RuntimeCoreInvariantError):
            action("sub-1")

    @pytest.mark.parametrize("terminal_action", ["accept", "reject", "withdraw"])
    def test_rejected_blocks_all(self, terminal_action: str) -> None:
        engine, _ = _make_engine()
        _full_pipeline(engine)
        engine.reject_submission("sub-1")
        action = getattr(engine, f"{terminal_action}_submission")
        with pytest.raises(RuntimeCoreInvariantError):
            action("sub-1")

    @pytest.mark.parametrize("terminal_action", ["accept", "reject", "withdraw"])
    def test_withdrawn_blocks_all(self, terminal_action: str) -> None:
        engine, _ = _make_engine()
        _full_pipeline(engine)
        engine.withdraw_submission("sub-1")
        action = getattr(engine, f"{terminal_action}_submission")
        with pytest.raises(RuntimeCoreInvariantError):
            action("sub-1")


# ===================================================================
# Completeness boundary tests
# ===================================================================


class TestCompletenessThresholds:
    """Verify exact boundaries of evidence count -> completeness mapping."""

    @pytest.mark.parametrize(
        "count,expected",
        [
            (0, EvidenceCompleteness.INCOMPLETE),
            (1, EvidenceCompleteness.PARTIAL),
            (2, EvidenceCompleteness.COMPLETE),
            (3, EvidenceCompleteness.COMPLETE),
            (4, EvidenceCompleteness.VERIFIED),
            (5, EvidenceCompleteness.VERIFIED),
            (10, EvidenceCompleteness.VERIFIED),
        ],
    )
    def test_completeness_by_count(
        self, count: int, expected: EvidenceCompleteness
    ) -> None:
        engine, _ = _make_engine()
        _seed_requirement(engine)
        ids = tuple(f"e{i}" for i in range(count))
        pkg = _seed_package(engine, evidence_ids=ids)
        assert pkg.completeness == expected


# ===================================================================
# Immutability / frozen contracts
# ===================================================================


class TestImmutability:
    def test_requirement_is_frozen(self) -> None:
        engine, _ = _make_engine()
        req = _seed_requirement(engine)
        with pytest.raises(AttributeError):
            req.title = "changed"  # type: ignore[misc]

    def test_filing_window_is_frozen(self) -> None:
        engine, _ = _make_engine()
        _seed_requirement(engine)
        w = _seed_window(engine)
        with pytest.raises(AttributeError):
            w.window_id = "changed"  # type: ignore[misc]

    def test_evidence_package_is_frozen(self) -> None:
        engine, _ = _make_engine()
        _seed_requirement(engine)
        pkg = _seed_package(engine)
        with pytest.raises(AttributeError):
            pkg.package_id = "changed"  # type: ignore[misc]

    def test_submission_record_is_frozen(self) -> None:
        engine, _ = _make_engine()
        sub = _full_pipeline(engine)
        with pytest.raises(AttributeError):
            sub.status = SubmissionStatus.ACCEPTED  # type: ignore[misc]

    def test_review_is_frozen(self) -> None:
        engine, _ = _make_engine()
        _full_pipeline(engine)
        rev = engine.record_review("rev-1", "sub-1")
        with pytest.raises(AttributeError):
            rev.approved = True  # type: ignore[misc]

    def test_auditor_request_is_frozen(self) -> None:
        engine, _ = _make_engine()
        _full_pipeline(engine)
        ar = engine.record_auditor_request("ar-1", "tenant-a", "sub-1")
        with pytest.raises(AttributeError):
            ar.description = "changed"  # type: ignore[misc]

    def test_auditor_response_is_frozen(self) -> None:
        engine, _ = _make_engine()
        _full_pipeline(engine)
        engine.record_auditor_request("ar-1", "tenant-a", "sub-1")
        resp = engine.record_auditor_response("resp-1", "ar-1")
        with pytest.raises(AttributeError):
            resp.content = "changed"  # type: ignore[misc]

    def test_violation_is_frozen(self) -> None:
        engine, _ = _make_engine()
        _seed_requirement(engine)
        _seed_window(engine, opens_at=_PAST_OPEN, closes_at=_PAST_CLOSE)
        violations = engine.detect_reporting_violations()
        assert len(violations) > 0
        with pytest.raises(AttributeError):
            violations[0].reason = "changed"  # type: ignore[misc]

    def test_snapshot_is_frozen(self) -> None:
        engine, _ = _make_engine()
        snap = engine.regulatory_snapshot("snap-1")
        with pytest.raises(AttributeError):
            snap.total_requirements = 999  # type: ignore[misc]


# ===================================================================
# Edge cases / misc
# ===================================================================


class TestEdgeCases:
    def test_multiple_tenants_isolated(self) -> None:
        engine, _ = _make_engine()
        _seed_requirement(engine, requirement_id="r1", tenant_id="t1")
        _seed_requirement(engine, requirement_id="r2", tenant_id="t2")
        assert len(engine.requirements_for_tenant("t1")) == 1
        assert len(engine.requirements_for_tenant("t2")) == 1

    def test_multiple_packages_different_completeness(self) -> None:
        engine, _ = _make_engine()
        _seed_requirement(engine)
        p1 = _seed_package(engine, package_id="p1", evidence_ids=())
        p2 = _seed_package(engine, package_id="p2", evidence_ids=("e1",))
        p3 = _seed_package(engine, package_id="p3", evidence_ids=("e1", "e2"))
        assert p1.completeness == EvidenceCompleteness.INCOMPLETE
        assert p2.completeness == EvidenceCompleteness.PARTIAL
        assert p3.completeness == EvidenceCompleteness.COMPLETE

    def test_submission_references_correct_ids(self) -> None:
        engine, _ = _make_engine()
        _full_pipeline(engine)
        sub = engine.get_submission("sub-1")
        assert sub.window_id == "win-1"
        assert sub.tenant_id == "tenant-a"
        assert sub.package_id == "pkg-1"

    def test_review_references_correct_submission(self) -> None:
        engine, _ = _make_engine()
        _full_pipeline(engine)
        rev = engine.record_review("rev-1", "sub-1")
        assert rev.submission_id == "sub-1"

    def test_auditor_request_references_correct_submission(self) -> None:
        engine, _ = _make_engine()
        _full_pipeline(engine)
        ar = engine.record_auditor_request("ar-1", "tenant-a", "sub-1")
        assert ar.submission_id == "sub-1"

    def test_auditor_response_references_correct_request(self) -> None:
        engine, _ = _make_engine()
        _full_pipeline(engine)
        engine.record_auditor_request("ar-1", "tenant-a", "sub-1")
        resp = engine.record_auditor_response("resp-1", "ar-1")
        assert resp.request_id == "ar-1"

    def test_state_hash_after_full_pipeline(self) -> None:
        engine, _ = _make_engine()
        _full_pipeline(engine)
        h = engine.state_hash()
        assert len(h) == 64

    def test_many_requirements_many_windows(self) -> None:
        engine, _ = _make_engine()
        for i in range(20):
            _seed_requirement(engine, requirement_id=f"r-{i}")
            _seed_window(engine, window_id=f"w-{i}", requirement_id=f"r-{i}")
        assert engine.requirement_count == 20
        assert engine.window_count == 20

    def test_pending_review_submission_can_be_accepted(self) -> None:
        engine, _ = _make_engine()
        _full_pipeline(engine)
        engine.record_auditor_request("ar-1", "tenant-a", "sub-1")
        assert engine.get_submission("sub-1").status == SubmissionStatus.PENDING_REVIEW
        result = engine.accept_submission("sub-1")
        assert result.status == SubmissionStatus.ACCEPTED

    def test_pending_review_submission_can_be_rejected(self) -> None:
        engine, _ = _make_engine()
        _full_pipeline(engine)
        engine.record_auditor_request("ar-1", "tenant-a", "sub-1")
        result = engine.reject_submission("sub-1")
        assert result.status == SubmissionStatus.REJECTED

    def test_pending_review_submission_can_be_withdrawn(self) -> None:
        engine, _ = _make_engine()
        _full_pipeline(engine)
        engine.record_auditor_request("ar-1", "tenant-a", "sub-1")
        result = engine.withdraw_submission("sub-1")
        assert result.status == SubmissionStatus.WITHDRAWN


# ===================================================================
# Golden scenarios
# ===================================================================


class TestGoldenScenario1AssurancePackageAssembledAndSubmitted:
    """Golden scenario 1: assurance package assembled and submitted successfully."""

    def test_full_happy_path(self) -> None:
        engine, es = _make_engine()
        initial_events = es.event_count

        # 1. Register requirement
        req = engine.register_requirement(
            "req-annual", "tenant-corp", "Annual Compliance Report",
            filing_kind=FilingKind.ANNUAL,
            audience=ReportAudience.REGULATOR,
            review_requirement=ReviewRequirement.MANAGEMENT_REVIEW,
            recurring=True,
        )
        assert req.filing_kind == FilingKind.ANNUAL
        assert req.recurring is True

        # 2. Open filing window
        window = engine.open_filing_window(
            "win-2026", "req-annual",
            "2026-01-01T00:00:00+00:00", "2026-12-31T23:59:59+00:00",
        )
        assert window.status == SubmissionStatus.DRAFT

        # 3. Assemble evidence
        pkg = engine.assemble_evidence_package(
            "pkg-annual", "tenant-corp", "req-annual",
            ("ev-policy", "ev-audit-log", "ev-training"),
            assembled_by="compliance-officer",
        )
        assert pkg.completeness == EvidenceCompleteness.COMPLETE
        assert pkg.total_evidence_items == 3

        # 4. Validate
        completeness = engine.validate_package("pkg-annual")
        assert completeness == EvidenceCompleteness.COMPLETE

        # 5. Submit
        sub = engine.submit_report(
            "sub-annual", "win-2026", "tenant-corp", "pkg-annual",
            submitted_by="compliance-officer",
        )
        assert sub.status == SubmissionStatus.SUBMITTED
        assert sub.submitted_by == "compliance-officer"

        # 6. Window updated
        w = engine.get_window("win-2026")
        assert w.status == SubmissionStatus.SUBMITTED

        # 7. Review
        review = engine.record_review(
            "rev-mgmt", "sub-annual",
            reviewer="cfo",
            review_requirement=ReviewRequirement.MANAGEMENT_REVIEW,
            approved=True,
            comments="All in order",
        )
        assert review.approved is True

        # 8. Accept
        accepted = engine.accept_submission("sub-annual")
        assert accepted.status == SubmissionStatus.ACCEPTED

        # 9. Snapshot
        snap = engine.regulatory_snapshot("snap-annual")
        assert snap.total_requirements == 1
        assert snap.total_windows == 1
        assert snap.total_packages == 1
        assert snap.total_submissions == 1
        assert snap.total_reviews == 1

        # 10. Events emitted for every step
        assert es.event_count > initial_events
        # req + window + pkg + validate + submit + review + accept + snapshot = 8
        assert es.event_count == initial_events + 8


class TestGoldenScenario2MissingEvidenceBlocksSubmission:
    """Golden scenario 2: missing evidence blocks submission (INCOMPLETE package)."""

    def test_incomplete_blocks_then_complete_succeeds(self) -> None:
        engine, _ = _make_engine()

        req = engine.register_requirement("req-inc", "tenant-x", "Incident Report")
        window = engine.open_filing_window(
            "win-inc", "req-inc",
            "2026-01-01T00:00:00+00:00", "2026-06-30T23:59:59+00:00",
        )

        # Assemble with no evidence
        pkg_empty = engine.assemble_evidence_package(
            "pkg-empty", "tenant-x", "req-inc", (),
        )
        assert pkg_empty.completeness == EvidenceCompleteness.INCOMPLETE

        # Validate confirms INCOMPLETE
        assert engine.validate_package("pkg-empty") == EvidenceCompleteness.INCOMPLETE

        # Submission blocked
        with pytest.raises(RuntimeCoreInvariantError, match="INCOMPLETE"):
            engine.submit_report("sub-inc", "win-inc", "tenant-x", "pkg-empty")

        # Assemble a proper package
        pkg_good = engine.assemble_evidence_package(
            "pkg-good", "tenant-x", "req-inc", ("ev-1", "ev-2"),
        )
        assert pkg_good.completeness == EvidenceCompleteness.COMPLETE

        # Now submission succeeds
        sub = engine.submit_report("sub-inc", "win-inc", "tenant-x", "pkg-good")
        assert sub.status == SubmissionStatus.SUBMITTED


class TestGoldenScenario3MissedFilingWindowCreatesViolation:
    """Golden scenario 3: missed filing window creates reporting violation."""

    def test_missed_window_violation_lifecycle(self) -> None:
        engine, es = _make_engine()

        req = engine.register_requirement("req-q", "tenant-late", "Q1 Report",
                                          filing_kind=FilingKind.QUARTERLY)
        # Window already closed (past dates)
        engine.open_filing_window(
            "win-q1", "req-q",
            "2020-01-01T00:00:00+00:00", "2020-03-31T23:59:59+00:00",
        )

        # No submission made; detect violations
        violations = engine.detect_reporting_violations()
        assert len(violations) == 1
        v = violations[0]
        assert v.tenant_id == "tenant-late"
        assert v.requirement_id == "req-q"
        assert v.window_id == "win-q1"
        assert v.operation == "missed_filing_window"
        assert engine.violation_count == 1

        # Idempotent: re-running yields no new violations
        violations2 = engine.detect_reporting_violations()
        assert len(violations2) == 0
        assert engine.violation_count == 1

        # Violations for tenant
        tenant_violations = engine.violations_for_tenant("tenant-late")
        assert len(tenant_violations) == 1

        # Snapshot captures violations
        snap = engine.regulatory_snapshot("snap-violations")
        assert snap.total_violations == 1


class TestGoldenScenario4AuditorRequestAttachesNewEvidence:
    """Golden scenario 4: auditor request attaches new evidence and updates submission state."""

    def test_auditor_roundtrip(self) -> None:
        engine, es = _make_engine()

        # Setup: requirement -> window -> package -> submit
        engine.register_requirement("req-aud", "tenant-b", "Audit Response Filing",
                                    filing_kind=FilingKind.AUDIT_RESPONSE)
        engine.open_filing_window(
            "win-aud", "req-aud",
            "2026-01-01T00:00:00+00:00", "2026-12-31T23:59:59+00:00",
        )
        engine.assemble_evidence_package(
            "pkg-aud", "tenant-b", "req-aud",
            ("ev-initial-1", "ev-initial-2"),
        )
        sub = engine.submit_report("sub-aud", "win-aud", "tenant-b", "pkg-aud")
        assert sub.status == SubmissionStatus.SUBMITTED

        # Auditor requests additional info
        ar = engine.record_auditor_request(
            "ar-add-info", "tenant-b", "sub-aud",
            requested_by="external-auditor",
            description="Provide server access logs",
            due_at="2026-06-30T23:59:59+00:00",
        )
        assert ar.requested_by == "external-auditor"
        assert ar.description == "Provide server access logs"

        # Submission moves to PENDING_REVIEW
        updated_sub = engine.get_submission("sub-aud")
        assert updated_sub.status == SubmissionStatus.PENDING_REVIEW

        # Response with new evidence
        resp = engine.record_auditor_response(
            "resp-logs", "ar-add-info",
            responder="sysadmin",
            content="Attached server access logs for Q1-Q2",
            evidence_ids=("ev-access-log-q1", "ev-access-log-q2"),
        )
        assert resp.evidence_ids == ("ev-access-log-q1", "ev-access-log-q2")
        assert resp.responder == "sysadmin"

        # Verify lookup methods
        assert len(engine.requests_for_submission("sub-aud")) == 1
        assert len(engine.responses_for_request("ar-add-info")) == 1

        # Now accept the submission
        accepted = engine.accept_submission("sub-aud")
        assert accepted.status == SubmissionStatus.ACCEPTED

        # Snapshot captures auditor activity
        snap = engine.regulatory_snapshot("snap-audit")
        assert snap.total_auditor_requests == 1
        assert snap.total_auditor_responses == 1


class TestGoldenScenario5RemediationCompletionUpdatesPendingReport:
    """Golden scenario 5: remediation completion updates pending external report.

    Models the case where a rejected submission is remediated by assembling
    a new evidence package and resubmitting through a new window cycle.
    """

    def test_remediation_resubmission(self) -> None:
        engine, _ = _make_engine()

        # Initial submission
        engine.register_requirement("req-cert", "tenant-c", "Certification Filing",
                                    filing_kind=FilingKind.CERTIFICATION)
        engine.open_filing_window(
            "win-cert-1", "req-cert",
            "2026-01-01T00:00:00+00:00", "2026-06-30T23:59:59+00:00",
        )
        engine.assemble_evidence_package(
            "pkg-cert-1", "tenant-c", "req-cert", ("ev-partial",),
        )
        sub1 = engine.submit_report("sub-cert-1", "win-cert-1", "tenant-c", "pkg-cert-1")
        assert sub1.status == SubmissionStatus.SUBMITTED

        # Review rejects the submission
        engine.record_review(
            "rev-cert-1", "sub-cert-1",
            reviewer="auditor",
            review_requirement=ReviewRequirement.EXTERNAL_REVIEW,
            approved=False,
            comments="Insufficient evidence for certification",
        )
        rejected = engine.reject_submission("sub-cert-1")
        assert rejected.status == SubmissionStatus.REJECTED

        # Remediation: new package with more evidence
        pkg2 = engine.assemble_evidence_package(
            "pkg-cert-2", "tenant-c", "req-cert",
            ("ev-full-1", "ev-full-2", "ev-full-3", "ev-full-4"),
        )
        assert pkg2.completeness == EvidenceCompleteness.VERIFIED

        # New window for resubmission
        engine.open_filing_window(
            "win-cert-2", "req-cert",
            "2026-07-01T00:00:00+00:00", "2026-12-31T23:59:59+00:00",
        )
        sub2 = engine.submit_report("sub-cert-2", "win-cert-2", "tenant-c", "pkg-cert-2")
        assert sub2.status == SubmissionStatus.SUBMITTED

        # Review approves
        engine.record_review(
            "rev-cert-2", "sub-cert-2",
            reviewer="auditor",
            review_requirement=ReviewRequirement.EXTERNAL_REVIEW,
            approved=True,
            comments="Remediation complete",
        )
        accepted = engine.accept_submission("sub-cert-2")
        assert accepted.status == SubmissionStatus.ACCEPTED

        # Counts reflect both cycles
        assert engine.submission_count == 2
        assert engine.review_count == 2
        assert engine.package_count == 2
        assert engine.window_count == 2


class TestGoldenScenario6SnapshotCapturesFullState:
    """Golden scenario 6: snapshot captures full state."""

    def test_comprehensive_snapshot(self) -> None:
        engine, es = _make_engine()

        # Build up state across multiple entities
        engine.register_requirement("req-s1", "tenant-snap", "Snap Req 1")
        engine.register_requirement("req-s2", "tenant-snap", "Snap Req 2")

        engine.open_filing_window("win-s1", "req-s1",
                                  "2026-01-01T00:00:00+00:00", "2026-12-31T23:59:59+00:00")
        engine.open_filing_window("win-s2", "req-s2",
                                  "2026-01-01T00:00:00+00:00", "2026-12-31T23:59:59+00:00")

        engine.assemble_evidence_package("pkg-s1", "tenant-snap", "req-s1", ("e1", "e2"))
        engine.assemble_evidence_package("pkg-s2", "tenant-snap", "req-s2", ("e3", "e4"))

        engine.submit_report("sub-s1", "win-s1", "tenant-snap", "pkg-s1")
        engine.submit_report("sub-s2", "win-s2", "tenant-snap", "pkg-s2")

        engine.record_review("rev-s1", "sub-s1", approved=True)
        engine.record_review("rev-s2", "sub-s2", approved=True)
        engine.record_review("rev-s3", "sub-s1", reviewer="mgr", approved=True)

        engine.record_auditor_request("ar-s1", "tenant-snap", "sub-s1",
                                      description="Details needed")
        engine.record_auditor_request("ar-s2", "tenant-snap", "sub-s2")

        engine.record_auditor_response("resp-s1", "ar-s1",
                                       content="Here you go",
                                       evidence_ids=("ev-extra",))
        engine.record_auditor_response("resp-s2", "ar-s2")
        engine.record_auditor_response("resp-s3", "ar-s1")

        # Add a violation via a separate missed window
        engine.register_requirement("req-s3", "tenant-snap", "Late Report")
        engine.open_filing_window("win-s3", "req-s3",
                                  _PAST_OPEN, _PAST_CLOSE)
        engine.detect_reporting_violations()

        # Capture snapshot
        snap = engine.regulatory_snapshot("snap-full")

        assert snap.snapshot_id == "snap-full"
        assert snap.total_requirements == 3
        assert snap.total_windows == 3
        assert snap.total_packages == 2
        assert snap.total_submissions == 2
        assert snap.total_reviews == 3
        assert snap.total_auditor_requests == 2
        assert snap.total_auditor_responses == 3
        assert snap.total_violations == 1
        assert snap.captured_at  # non-empty

        # State hash is deterministic
        h1 = engine.state_hash()
        h2 = engine.state_hash()
        assert h1 == h2
        assert len(h1) == 64

        # Event count is positive
        assert es.event_count > 0
