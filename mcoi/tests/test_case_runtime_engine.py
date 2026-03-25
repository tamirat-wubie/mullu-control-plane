"""Comprehensive tests for CaseRuntimeEngine.

Covers: case management, assignments, evidence management, evidence collections,
reviews, findings, decisions, case closure, violation detection, snapshots,
state hash, count properties, and 6 golden end-to-end scenarios.
"""

from __future__ import annotations

import itertools
import pytest
from datetime import datetime, timezone

from mcoi_runtime.core.case_runtime import CaseRuntimeEngine
from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
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


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@pytest.fixture()
def engine() -> CaseRuntimeEngine:
    es = EventSpineEngine()
    return CaseRuntimeEngine(es)


@pytest.fixture()
def engine_with_case(engine: CaseRuntimeEngine) -> CaseRuntimeEngine:
    """Engine pre-loaded with a single open case."""
    engine.open_case("c1", "t1", "Test Case")
    return engine


# ===================================================================
# Construction
# ===================================================================


class TestConstruction:
    def test_requires_event_spine(self):
        with pytest.raises(RuntimeCoreInvariantError):
            CaseRuntimeEngine("not-an-event-spine")

    def test_initial_counts_zero(self, engine: CaseRuntimeEngine):
        assert engine.case_count == 0
        assert engine.open_case_count == 0
        assert engine.evidence_count == 0
        assert engine.review_count == 0
        assert engine.finding_count == 0
        assert engine.decision_count == 0
        assert engine.violation_count == 0
        assert engine.assignment_count == 0
        assert engine.collection_count == 0


# ===================================================================
# Case management
# ===================================================================


class TestOpenCase:
    def test_open_case_defaults(self, engine: CaseRuntimeEngine):
        c = engine.open_case("c1", "t1", "My Case")
        assert isinstance(c, CaseRecord)
        assert c.case_id == "c1"
        assert c.tenant_id == "t1"
        assert c.title == "My Case"
        assert c.kind == CaseKind.INCIDENT
        assert c.severity == CaseSeverity.MEDIUM
        assert c.status == CaseStatus.OPEN
        assert c.opened_by == "system"
        assert c.opened_at != ""

    def test_open_case_custom_fields(self, engine: CaseRuntimeEngine):
        c = engine.open_case(
            "c2", "t2", "Custom",
            kind=CaseKind.SECURITY,
            severity=CaseSeverity.CRITICAL,
            description="desc",
            opened_by="admin",
        )
        assert c.kind == CaseKind.SECURITY
        assert c.severity == CaseSeverity.CRITICAL
        assert c.description == "desc"
        assert c.opened_by == "admin"

    @pytest.mark.parametrize("kind", list(CaseKind))
    def test_open_case_all_kinds(self, engine: CaseRuntimeEngine, kind: CaseKind):
        c = engine.open_case(f"c-{kind.value}", "t1", "Case", kind=kind)
        assert c.kind == kind

    @pytest.mark.parametrize("sev", list(CaseSeverity))
    def test_open_case_all_severities(self, engine: CaseRuntimeEngine, sev: CaseSeverity):
        c = engine.open_case(f"c-{sev.value}", "t1", "Case", severity=sev)
        assert c.severity == sev

    @pytest.mark.parametrize("kind,sev", list(itertools.product(CaseKind, CaseSeverity)))
    def test_open_case_kind_severity_combinations(
        self, engine: CaseRuntimeEngine, kind: CaseKind, sev: CaseSeverity
    ):
        cid = f"c-{kind.value}-{sev.value}"
        c = engine.open_case(cid, "t1", "Case", kind=kind, severity=sev)
        assert c.kind == kind
        assert c.severity == sev

    def test_duplicate_case_id_raises(self, engine: CaseRuntimeEngine):
        engine.open_case("c1", "t1", "First")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate case_id"):
            engine.open_case("c1", "t2", "Second")

    def test_case_count_increments(self, engine: CaseRuntimeEngine):
        engine.open_case("c1", "t1", "A")
        assert engine.case_count == 1
        engine.open_case("c2", "t1", "B")
        assert engine.case_count == 2

    def test_open_case_count(self, engine: CaseRuntimeEngine):
        engine.open_case("c1", "t1", "A")
        engine.open_case("c2", "t1", "B")
        assert engine.open_case_count == 2


class TestGetCase:
    def test_get_existing(self, engine_with_case: CaseRuntimeEngine):
        c = engine_with_case.get_case("c1")
        assert c.case_id == "c1"

    def test_get_missing_raises(self, engine: CaseRuntimeEngine):
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown case_id"):
            engine.get_case("nonexistent")


class TestCasesForTenant:
    def test_filter_by_tenant(self, engine: CaseRuntimeEngine):
        engine.open_case("c1", "t1", "A")
        engine.open_case("c2", "t2", "B")
        engine.open_case("c3", "t1", "C")
        result = engine.cases_for_tenant("t1")
        assert len(result) == 2
        assert all(c.tenant_id == "t1" for c in result)

    def test_empty_for_unknown_tenant(self, engine_with_case: CaseRuntimeEngine):
        result = engine_with_case.cases_for_tenant("unknown")
        assert result == ()

    def test_returns_tuple(self, engine_with_case: CaseRuntimeEngine):
        result = engine_with_case.cases_for_tenant("t1")
        assert isinstance(result, tuple)


class TestUpdateCaseStatus:
    @pytest.mark.parametrize("status", [
        CaseStatus.IN_PROGRESS,
        CaseStatus.UNDER_REVIEW,
        CaseStatus.PENDING_DECISION,
        CaseStatus.ESCALATED,
        CaseStatus.CLOSED,
    ])
    def test_valid_transitions(self, engine_with_case: CaseRuntimeEngine, status: CaseStatus):
        updated = engine_with_case.update_case_status("c1", status)
        assert updated.status == status

    def test_cannot_update_closed_case(self, engine_with_case: CaseRuntimeEngine):
        engine_with_case.update_case_status("c1", CaseStatus.CLOSED)
        with pytest.raises(RuntimeCoreInvariantError, match="Cannot update a closed case"):
            engine_with_case.update_case_status("c1", CaseStatus.OPEN)

    def test_unknown_case_raises(self, engine: CaseRuntimeEngine):
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown case_id"):
            engine.update_case_status("nope", CaseStatus.OPEN)

    def test_preserves_other_fields(self, engine: CaseRuntimeEngine):
        engine.open_case("c1", "t1", "Title", kind=CaseKind.AUDIT, severity=CaseSeverity.HIGH)
        updated = engine.update_case_status("c1", CaseStatus.IN_PROGRESS)
        assert updated.kind == CaseKind.AUDIT
        assert updated.severity == CaseSeverity.HIGH
        assert updated.title == "Title"
        assert updated.tenant_id == "t1"

    def test_open_case_count_decrements_on_close(self, engine_with_case: CaseRuntimeEngine):
        assert engine_with_case.open_case_count == 1
        engine_with_case.update_case_status("c1", CaseStatus.CLOSED)
        assert engine_with_case.open_case_count == 0


class TestEscalateCase:
    def test_escalate_changes_severity_and_status(self, engine_with_case: CaseRuntimeEngine):
        updated = engine_with_case.escalate_case("c1", CaseSeverity.CRITICAL)
        assert updated.severity == CaseSeverity.CRITICAL
        assert updated.status == CaseStatus.ESCALATED

    def test_escalate_unknown_case_raises(self, engine: CaseRuntimeEngine):
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown case_id"):
            engine.escalate_case("nope", CaseSeverity.HIGH)

    def test_cannot_escalate_closed_case(self, engine_with_case: CaseRuntimeEngine):
        engine_with_case.update_case_status("c1", CaseStatus.CLOSED)
        with pytest.raises(RuntimeCoreInvariantError, match="Cannot escalate a closed case"):
            engine_with_case.escalate_case("c1", CaseSeverity.CRITICAL)

    @pytest.mark.parametrize("sev", list(CaseSeverity))
    def test_escalate_all_severities(self, engine_with_case: CaseRuntimeEngine, sev: CaseSeverity):
        updated = engine_with_case.escalate_case("c1", sev)
        assert updated.severity == sev
        assert updated.status == CaseStatus.ESCALATED


# ===================================================================
# Assignments
# ===================================================================


class TestAssignCase:
    def test_creates_assignment(self, engine_with_case: CaseRuntimeEngine):
        a = engine_with_case.assign_case("a1", "c1", "user1")
        assert isinstance(a, CaseAssignment)
        assert a.assignment_id == "a1"
        assert a.case_id == "c1"
        assert a.assignee_id == "user1"
        assert a.role == "investigator"
        assert a.assigned_at != ""

    def test_custom_role(self, engine_with_case: CaseRuntimeEngine):
        a = engine_with_case.assign_case("a1", "c1", "user1", role="reviewer")
        assert a.role == "reviewer"

    def test_duplicate_assignment_id_raises(self, engine_with_case: CaseRuntimeEngine):
        engine_with_case.assign_case("a1", "c1", "user1")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate assignment_id"):
            engine_with_case.assign_case("a1", "c1", "user2")

    def test_unknown_case_raises(self, engine: CaseRuntimeEngine):
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown case_id"):
            engine.assign_case("a1", "nope", "user1")

    def test_assignment_count(self, engine_with_case: CaseRuntimeEngine):
        assert engine_with_case.assignment_count == 0
        engine_with_case.assign_case("a1", "c1", "user1")
        assert engine_with_case.assignment_count == 1
        engine_with_case.assign_case("a2", "c1", "user2")
        assert engine_with_case.assignment_count == 2


class TestAssignmentsForCase:
    def test_returns_correct_assignments(self, engine: CaseRuntimeEngine):
        engine.open_case("c1", "t1", "A")
        engine.open_case("c2", "t1", "B")
        engine.assign_case("a1", "c1", "user1")
        engine.assign_case("a2", "c1", "user2")
        engine.assign_case("a3", "c2", "user3")
        result = engine.assignments_for_case("c1")
        assert len(result) == 2
        assert all(a.case_id == "c1" for a in result)

    def test_empty_for_no_assignments(self, engine_with_case: CaseRuntimeEngine):
        assert engine_with_case.assignments_for_case("c1") == ()

    def test_returns_tuple(self, engine_with_case: CaseRuntimeEngine):
        engine_with_case.assign_case("a1", "c1", "user1")
        assert isinstance(engine_with_case.assignments_for_case("c1"), tuple)


# ===================================================================
# Evidence management
# ===================================================================


class TestAddEvidence:
    def test_creates_evidence_item(self, engine_with_case: CaseRuntimeEngine):
        e = engine_with_case.add_evidence("e1", "c1", "log", "src1")
        assert isinstance(e, EvidenceItem)
        assert e.evidence_id == "e1"
        assert e.case_id == "c1"
        assert e.source_type == "log"
        assert e.source_id == "src1"
        assert e.status == EvidenceStatus.PENDING
        assert e.title == "Evidence"
        assert e.submitted_by == "system"
        assert e.submitted_at != ""

    def test_custom_fields(self, engine_with_case: CaseRuntimeEngine):
        e = engine_with_case.add_evidence(
            "e1", "c1", "artifact", "src1",
            title="My Evidence",
            description="desc",
            submitted_by="analyst",
        )
        assert e.title == "My Evidence"
        assert e.description == "desc"
        assert e.submitted_by == "analyst"

    def test_duplicate_evidence_id_raises(self, engine_with_case: CaseRuntimeEngine):
        engine_with_case.add_evidence("e1", "c1", "log", "src1")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate evidence_id"):
            engine_with_case.add_evidence("e1", "c1", "log", "src2")

    def test_unknown_case_raises(self, engine: CaseRuntimeEngine):
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown case_id"):
            engine.add_evidence("e1", "nope", "log", "src1")

    def test_evidence_count(self, engine_with_case: CaseRuntimeEngine):
        assert engine_with_case.evidence_count == 0
        engine_with_case.add_evidence("e1", "c1", "log", "src1")
        assert engine_with_case.evidence_count == 1


class TestGetEvidence:
    def test_get_existing(self, engine_with_case: CaseRuntimeEngine):
        engine_with_case.add_evidence("e1", "c1", "log", "src1")
        e = engine_with_case.get_evidence("e1")
        assert e.evidence_id == "e1"

    def test_get_missing_raises(self, engine: CaseRuntimeEngine):
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown evidence_id"):
            engine.get_evidence("nope")


class TestEvidenceForCase:
    def test_filter_by_case(self, engine: CaseRuntimeEngine):
        engine.open_case("c1", "t1", "A")
        engine.open_case("c2", "t1", "B")
        engine.add_evidence("e1", "c1", "log", "s1")
        engine.add_evidence("e2", "c1", "log", "s2")
        engine.add_evidence("e3", "c2", "log", "s3")
        result = engine.evidence_for_case("c1")
        assert len(result) == 2
        assert all(e.case_id == "c1" for e in result)

    def test_empty_for_no_evidence(self, engine_with_case: CaseRuntimeEngine):
        assert engine_with_case.evidence_for_case("c1") == ()

    def test_returns_tuple(self, engine_with_case: CaseRuntimeEngine):
        assert isinstance(engine_with_case.evidence_for_case("c1"), tuple)


class TestAdmitEvidence:
    def test_pending_to_admitted(self, engine_with_case: CaseRuntimeEngine):
        engine_with_case.add_evidence("e1", "c1", "log", "s1")
        updated = engine_with_case.admit_evidence("e1")
        assert updated.status == EvidenceStatus.ADMITTED

    def test_cannot_admit_non_pending(self, engine_with_case: CaseRuntimeEngine):
        engine_with_case.add_evidence("e1", "c1", "log", "s1")
        engine_with_case.admit_evidence("e1")
        with pytest.raises(RuntimeCoreInvariantError, match="Can only admit PENDING"):
            engine_with_case.admit_evidence("e1")

    def test_cannot_admit_excluded(self, engine_with_case: CaseRuntimeEngine):
        engine_with_case.add_evidence("e1", "c1", "log", "s1")
        engine_with_case.exclude_evidence("e1")
        with pytest.raises(RuntimeCoreInvariantError, match="Can only admit PENDING"):
            engine_with_case.admit_evidence("e1")

    def test_unknown_evidence_raises(self, engine: CaseRuntimeEngine):
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown evidence_id"):
            engine.admit_evidence("nope")

    def test_preserves_fields(self, engine_with_case: CaseRuntimeEngine):
        engine_with_case.add_evidence(
            "e1", "c1", "artifact", "s1",
            title="My Evidence",
            description="important",
            submitted_by="analyst",
        )
        updated = engine_with_case.admit_evidence("e1")
        assert updated.title == "My Evidence"
        assert updated.description == "important"
        assert updated.submitted_by == "analyst"
        assert updated.source_type == "artifact"


class TestExcludeEvidence:
    def test_exclude_pending(self, engine_with_case: CaseRuntimeEngine):
        engine_with_case.add_evidence("e1", "c1", "log", "s1")
        updated = engine_with_case.exclude_evidence("e1", reason="irrelevant")
        assert updated.status == EvidenceStatus.EXCLUDED

    def test_exclude_admitted(self, engine_with_case: CaseRuntimeEngine):
        engine_with_case.add_evidence("e1", "c1", "log", "s1")
        engine_with_case.admit_evidence("e1")
        updated = engine_with_case.exclude_evidence("e1")
        assert updated.status == EvidenceStatus.EXCLUDED

    def test_cannot_exclude_legal_hold(self, engine_with_case: CaseRuntimeEngine):
        engine_with_case.add_evidence("e1", "c1", "legal_hold", "s1")
        with pytest.raises(RuntimeCoreInvariantError, match="Cannot exclude legal-hold"):
            engine_with_case.exclude_evidence("e1")

    def test_unknown_evidence_raises(self, engine: CaseRuntimeEngine):
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown evidence_id"):
            engine.exclude_evidence("nope")


# ===================================================================
# Evidence collections
# ===================================================================


class TestCollectEvidence:
    def test_creates_collection(self, engine_with_case: CaseRuntimeEngine):
        engine_with_case.add_evidence("e1", "c1", "log", "s1")
        engine_with_case.add_evidence("e2", "c1", "log", "s2")
        col = engine_with_case.collect_evidence("col1", "c1", ("e1", "e2"), title="Logs")
        assert isinstance(col, EvidenceCollection)
        assert col.collection_id == "col1"
        assert col.case_id == "c1"
        assert col.evidence_ids == ("e1", "e2")
        assert col.title == "Logs"
        assert col.created_at != ""

    def test_validates_evidence_ids_exist(self, engine_with_case: CaseRuntimeEngine):
        engine_with_case.add_evidence("e1", "c1", "log", "s1")
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown evidence_id"):
            engine_with_case.collect_evidence("col1", "c1", ("e1", "nonexistent"))

    def test_unknown_case_raises(self, engine: CaseRuntimeEngine):
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown case_id"):
            engine.collect_evidence("col1", "nope", ())

    def test_duplicate_collection_id_raises(self, engine_with_case: CaseRuntimeEngine):
        engine_with_case.add_evidence("e1", "c1", "log", "s1")
        engine_with_case.collect_evidence("col1", "c1", ("e1",))
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate collection_id"):
            engine_with_case.collect_evidence("col1", "c1", ("e1",))

    def test_empty_evidence_ids(self, engine_with_case: CaseRuntimeEngine):
        col = engine_with_case.collect_evidence("col1", "c1", ())
        assert col.evidence_ids == ()

    def test_collection_count(self, engine_with_case: CaseRuntimeEngine):
        assert engine_with_case.collection_count == 0
        engine_with_case.collect_evidence("col1", "c1", ())
        assert engine_with_case.collection_count == 1


class TestCollectionsForCase:
    def test_filter_by_case(self, engine: CaseRuntimeEngine):
        engine.open_case("c1", "t1", "A")
        engine.open_case("c2", "t1", "B")
        engine.collect_evidence("col1", "c1", ())
        engine.collect_evidence("col2", "c2", ())
        result = engine.collections_for_case("c1")
        assert len(result) == 1
        assert result[0].case_id == "c1"

    def test_empty_for_no_collections(self, engine_with_case: CaseRuntimeEngine):
        assert engine_with_case.collections_for_case("c1") == ()

    def test_returns_tuple(self, engine_with_case: CaseRuntimeEngine):
        assert isinstance(engine_with_case.collections_for_case("c1"), tuple)


# ===================================================================
# Reviews
# ===================================================================


class TestReviewEvidence:
    def test_creates_review_record(self, engine_with_case: CaseRuntimeEngine):
        engine_with_case.add_evidence("e1", "c1", "log", "s1")
        r = engine_with_case.review_evidence("r1", "c1", "e1", "reviewer1")
        assert isinstance(r, ReviewRecord)
        assert r.review_id == "r1"
        assert r.case_id == "c1"
        assert r.evidence_id == "e1"
        assert r.reviewer_id == "reviewer1"
        assert r.disposition == ReviewDisposition.REQUIRES_REVIEW
        assert r.reviewed_at != ""

    def test_accepted_transitions_evidence_to_reviewed(self, engine_with_case: CaseRuntimeEngine):
        engine_with_case.add_evidence("e1", "c1", "log", "s1")
        engine_with_case.review_evidence(
            "r1", "c1", "e1", "rev1", disposition=ReviewDisposition.ACCEPTED
        )
        e = engine_with_case.get_evidence("e1")
        assert e.status == EvidenceStatus.REVIEWED

    def test_accepted_on_admitted_transitions_to_reviewed(self, engine_with_case: CaseRuntimeEngine):
        engine_with_case.add_evidence("e1", "c1", "log", "s1")
        engine_with_case.admit_evidence("e1")
        engine_with_case.review_evidence(
            "r1", "c1", "e1", "rev1", disposition=ReviewDisposition.ACCEPTED
        )
        e = engine_with_case.get_evidence("e1")
        assert e.status == EvidenceStatus.REVIEWED

    def test_rejected_transitions_evidence_to_challenged(self, engine_with_case: CaseRuntimeEngine):
        engine_with_case.add_evidence("e1", "c1", "log", "s1")
        engine_with_case.review_evidence(
            "r1", "c1", "e1", "rev1", disposition=ReviewDisposition.REJECTED
        )
        e = engine_with_case.get_evidence("e1")
        assert e.status == EvidenceStatus.CHALLENGED

    def test_rejected_on_admitted_transitions_to_challenged(self, engine_with_case: CaseRuntimeEngine):
        engine_with_case.add_evidence("e1", "c1", "log", "s1")
        engine_with_case.admit_evidence("e1")
        engine_with_case.review_evidence(
            "r1", "c1", "e1", "rev1", disposition=ReviewDisposition.REJECTED
        )
        e = engine_with_case.get_evidence("e1")
        assert e.status == EvidenceStatus.CHALLENGED

    def test_inconclusive_no_transition(self, engine_with_case: CaseRuntimeEngine):
        engine_with_case.add_evidence("e1", "c1", "log", "s1")
        engine_with_case.review_evidence(
            "r1", "c1", "e1", "rev1", disposition=ReviewDisposition.INCONCLUSIVE
        )
        e = engine_with_case.get_evidence("e1")
        assert e.status == EvidenceStatus.PENDING

    def test_requires_review_no_transition(self, engine_with_case: CaseRuntimeEngine):
        engine_with_case.add_evidence("e1", "c1", "log", "s1")
        engine_with_case.review_evidence(
            "r1", "c1", "e1", "rev1", disposition=ReviewDisposition.REQUIRES_REVIEW
        )
        e = engine_with_case.get_evidence("e1")
        assert e.status == EvidenceStatus.PENDING

    def test_escalated_disposition_no_transition(self, engine_with_case: CaseRuntimeEngine):
        engine_with_case.add_evidence("e1", "c1", "log", "s1")
        engine_with_case.review_evidence(
            "r1", "c1", "e1", "rev1", disposition=ReviewDisposition.ESCALATED
        )
        e = engine_with_case.get_evidence("e1")
        assert e.status == EvidenceStatus.PENDING

    def test_duplicate_review_id_raises(self, engine_with_case: CaseRuntimeEngine):
        engine_with_case.add_evidence("e1", "c1", "log", "s1")
        engine_with_case.review_evidence("r1", "c1", "e1", "rev1")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate review_id"):
            engine_with_case.review_evidence("r1", "c1", "e1", "rev2")

    def test_unknown_case_raises(self, engine: CaseRuntimeEngine):
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown case_id"):
            engine.review_evidence("r1", "nope", "e1", "rev1")

    def test_unknown_evidence_raises(self, engine_with_case: CaseRuntimeEngine):
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown evidence_id"):
            engine_with_case.review_evidence("r1", "c1", "nope", "rev1")

    def test_review_with_notes(self, engine_with_case: CaseRuntimeEngine):
        engine_with_case.add_evidence("e1", "c1", "log", "s1")
        r = engine_with_case.review_evidence(
            "r1", "c1", "e1", "rev1", notes="looks good"
        )
        assert r.notes == "looks good"

    def test_review_count(self, engine_with_case: CaseRuntimeEngine):
        engine_with_case.add_evidence("e1", "c1", "log", "s1")
        assert engine_with_case.review_count == 0
        engine_with_case.review_evidence("r1", "c1", "e1", "rev1")
        assert engine_with_case.review_count == 1

    @pytest.mark.parametrize("disposition", list(ReviewDisposition))
    def test_all_dispositions_create_review(
        self, engine_with_case: CaseRuntimeEngine, disposition: ReviewDisposition
    ):
        engine_with_case.add_evidence(f"e-{disposition.value}", "c1", "log", "s1")
        r = engine_with_case.review_evidence(
            f"r-{disposition.value}", "c1", f"e-{disposition.value}",
            "rev1", disposition=disposition,
        )
        assert r.disposition == disposition


class TestReviewsForCase:
    def test_filter_by_case(self, engine: CaseRuntimeEngine):
        engine.open_case("c1", "t1", "A")
        engine.open_case("c2", "t1", "B")
        engine.add_evidence("e1", "c1", "log", "s1")
        engine.add_evidence("e2", "c2", "log", "s2")
        engine.review_evidence("r1", "c1", "e1", "rev1")
        engine.review_evidence("r2", "c2", "e2", "rev1")
        result = engine.reviews_for_case("c1")
        assert len(result) == 1
        assert result[0].case_id == "c1"

    def test_empty_returns_empty_tuple(self, engine_with_case: CaseRuntimeEngine):
        assert engine_with_case.reviews_for_case("c1") == ()


# ===================================================================
# Findings
# ===================================================================


class TestRecordFinding:
    def test_creates_finding(self, engine_with_case: CaseRuntimeEngine):
        f = engine_with_case.record_finding("f1", "c1", "Found something")
        assert isinstance(f, FindingRecord)
        assert f.finding_id == "f1"
        assert f.case_id == "c1"
        assert f.title == "Found something"
        assert f.severity == FindingSeverity.INFORMATIONAL
        assert f.found_at != ""

    def test_custom_fields(self, engine_with_case: CaseRuntimeEngine):
        f = engine_with_case.record_finding(
            "f1", "c1", "Finding",
            severity=FindingSeverity.MEDIUM,
            description="details",
            evidence_ids=("e1",),
            remediation="fix it",
        )
        assert f.severity == FindingSeverity.MEDIUM
        assert f.description == "details"
        assert f.evidence_ids == ("e1",)
        assert f.remediation == "fix it"

    def test_duplicate_finding_id_raises(self, engine_with_case: CaseRuntimeEngine):
        engine_with_case.record_finding("f1", "c1", "A")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate finding_id"):
            engine_with_case.record_finding("f1", "c1", "B")

    def test_unknown_case_raises(self, engine: CaseRuntimeEngine):
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown case_id"):
            engine.record_finding("f1", "nope", "Title")

    def test_high_severity_auto_escalates_case(self, engine_with_case: CaseRuntimeEngine):
        engine_with_case.record_finding("f1", "c1", "Bad", severity=FindingSeverity.HIGH)
        c = engine_with_case.get_case("c1")
        assert c.severity == CaseSeverity.HIGH
        assert c.status == CaseStatus.ESCALATED

    def test_critical_severity_auto_escalates_case(self, engine_with_case: CaseRuntimeEngine):
        engine_with_case.record_finding("f1", "c1", "Worst", severity=FindingSeverity.CRITICAL)
        c = engine_with_case.get_case("c1")
        assert c.severity == CaseSeverity.CRITICAL
        assert c.status == CaseStatus.ESCALATED

    def test_high_no_escalate_if_already_critical(self, engine: CaseRuntimeEngine):
        engine.open_case("c1", "t1", "Case", severity=CaseSeverity.CRITICAL)
        engine.record_finding("f1", "c1", "Finding", severity=FindingSeverity.HIGH)
        c = engine.get_case("c1")
        # Should NOT downgrade from CRITICAL
        assert c.severity == CaseSeverity.CRITICAL
        # Status stays OPEN since no escalation happened
        assert c.status == CaseStatus.OPEN

    def test_informational_no_escalation(self, engine_with_case: CaseRuntimeEngine):
        engine_with_case.record_finding("f1", "c1", "Info", severity=FindingSeverity.INFORMATIONAL)
        c = engine_with_case.get_case("c1")
        assert c.status == CaseStatus.OPEN
        assert c.severity == CaseSeverity.MEDIUM

    def test_low_no_escalation(self, engine_with_case: CaseRuntimeEngine):
        engine_with_case.record_finding("f1", "c1", "Low", severity=FindingSeverity.LOW)
        c = engine_with_case.get_case("c1")
        assert c.status == CaseStatus.OPEN

    def test_medium_no_escalation(self, engine_with_case: CaseRuntimeEngine):
        engine_with_case.record_finding("f1", "c1", "Med", severity=FindingSeverity.MEDIUM)
        c = engine_with_case.get_case("c1")
        assert c.status == CaseStatus.OPEN

    def test_finding_count(self, engine_with_case: CaseRuntimeEngine):
        assert engine_with_case.finding_count == 0
        engine_with_case.record_finding("f1", "c1", "A")
        assert engine_with_case.finding_count == 1

    @pytest.mark.parametrize("sev", list(FindingSeverity))
    def test_all_severities(self, engine_with_case: CaseRuntimeEngine, sev: FindingSeverity):
        f = engine_with_case.record_finding(f"f-{sev.value}", "c1", "Title", severity=sev)
        assert f.severity == sev


class TestFindingsForCase:
    def test_filter_by_case(self, engine: CaseRuntimeEngine):
        engine.open_case("c1", "t1", "A")
        engine.open_case("c2", "t1", "B")
        engine.record_finding("f1", "c1", "F1")
        engine.record_finding("f2", "c2", "F2")
        result = engine.findings_for_case("c1")
        assert len(result) == 1
        assert result[0].case_id == "c1"

    def test_empty_returns_tuple(self, engine_with_case: CaseRuntimeEngine):
        assert engine_with_case.findings_for_case("c1") == ()


# ===================================================================
# Decisions
# ===================================================================


class TestMakeCaseDecision:
    def test_creates_decision(self, engine_with_case: CaseRuntimeEngine):
        d = engine_with_case.make_case_decision("d1", "c1")
        assert isinstance(d, CaseDecision)
        assert d.decision_id == "d1"
        assert d.case_id == "c1"
        assert d.disposition == CaseClosureDisposition.UNRESOLVED
        assert d.decided_by == "system"
        assert d.decided_at != ""

    def test_custom_fields(self, engine_with_case: CaseRuntimeEngine):
        d = engine_with_case.make_case_decision(
            "d1", "c1",
            disposition=CaseClosureDisposition.RESOLVED,
            decided_by="admin",
            reason="fixed",
        )
        assert d.disposition == CaseClosureDisposition.RESOLVED
        assert d.decided_by == "admin"
        assert d.reason == "fixed"

    def test_duplicate_decision_id_raises(self, engine_with_case: CaseRuntimeEngine):
        engine_with_case.make_case_decision("d1", "c1")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate decision_id"):
            engine_with_case.make_case_decision("d1", "c1")

    def test_unknown_case_raises(self, engine: CaseRuntimeEngine):
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown case_id"):
            engine.make_case_decision("d1", "nope")

    def test_decision_count(self, engine_with_case: CaseRuntimeEngine):
        assert engine_with_case.decision_count == 0
        engine_with_case.make_case_decision("d1", "c1")
        assert engine_with_case.decision_count == 1

    @pytest.mark.parametrize("disp", list(CaseClosureDisposition))
    def test_all_dispositions(self, engine_with_case: CaseRuntimeEngine, disp: CaseClosureDisposition):
        d = engine_with_case.make_case_decision(f"d-{disp.value}", "c1", disposition=disp)
        assert d.disposition == disp


# ===================================================================
# Case closure
# ===================================================================


class TestCloseCase:
    def test_produces_closure_report(self, engine_with_case: CaseRuntimeEngine):
        report = engine_with_case.close_case("c1")
        assert isinstance(report, CaseClosureReport)
        assert report.case_id == "c1"
        assert report.tenant_id == "t1"
        assert report.disposition == CaseClosureDisposition.RESOLVED
        assert report.closed_at != ""

    def test_case_becomes_closed(self, engine_with_case: CaseRuntimeEngine):
        engine_with_case.close_case("c1")
        c = engine_with_case.get_case("c1")
        assert c.status == CaseStatus.CLOSED
        assert c.closed_at != ""

    def test_auto_creates_decision(self, engine_with_case: CaseRuntimeEngine):
        assert engine_with_case.decision_count == 0
        engine_with_case.close_case("c1")
        assert engine_with_case.decision_count == 1

    def test_cannot_close_already_closed(self, engine_with_case: CaseRuntimeEngine):
        engine_with_case.close_case("c1")
        with pytest.raises(RuntimeCoreInvariantError, match="already closed"):
            engine_with_case.close_case("c1")

    def test_unknown_case_raises(self, engine: CaseRuntimeEngine):
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown case_id"):
            engine.close_case("nope")

    def test_correct_counts_in_report(self, engine_with_case: CaseRuntimeEngine):
        engine_with_case.add_evidence("e1", "c1", "log", "s1")
        engine_with_case.add_evidence("e2", "c1", "log", "s2")
        engine_with_case.review_evidence("r1", "c1", "e1", "rev1")
        engine_with_case.record_finding("f1", "c1", "Finding")
        report = engine_with_case.close_case("c1")
        assert report.total_evidence == 2
        assert report.total_reviews == 1
        assert report.total_findings == 1

    def test_custom_disposition(self, engine_with_case: CaseRuntimeEngine):
        report = engine_with_case.close_case(
            "c1", disposition=CaseClosureDisposition.REMEDIATED,
            decided_by="admin", reason="patched",
        )
        assert report.disposition == CaseClosureDisposition.REMEDIATED

    def test_open_case_count_decrements(self, engine_with_case: CaseRuntimeEngine):
        assert engine_with_case.open_case_count == 1
        engine_with_case.close_case("c1")
        assert engine_with_case.open_case_count == 0

    def test_case_count_unchanged(self, engine_with_case: CaseRuntimeEngine):
        assert engine_with_case.case_count == 1
        engine_with_case.close_case("c1")
        assert engine_with_case.case_count == 1

    def test_report_has_report_id(self, engine_with_case: CaseRuntimeEngine):
        report = engine_with_case.close_case("c1")
        assert report.report_id != ""

    def test_violations_counted_in_report(self, engine: CaseRuntimeEngine):
        engine.open_case("c1", "t1", "A")
        engine.add_evidence("e1", "c1", "log", "s1")
        # Manually close to create a violation scenario, then reopen equivalent
        # Just close normally -- violations = 0 since no prior violations
        report = engine.close_case("c1")
        assert report.total_violations == 0


# ===================================================================
# Violation detection
# ===================================================================


class TestDetectCaseViolations:
    def test_closed_without_decision(self, engine_with_case: CaseRuntimeEngine):
        # Manually set case to CLOSED without using close_case (which auto-creates decision)
        engine_with_case.update_case_status("c1", CaseStatus.CLOSED)
        violations = engine_with_case.detect_case_violations()
        assert len(violations) >= 1
        ops = [v.operation for v in violations]
        assert "closed_without_decision" in ops

    def test_pending_evidence_on_closed_case(self, engine_with_case: CaseRuntimeEngine):
        engine_with_case.add_evidence("e1", "c1", "log", "s1")
        # Manually close to keep evidence PENDING
        engine_with_case.update_case_status("c1", CaseStatus.CLOSED)
        violations = engine_with_case.detect_case_violations()
        ops = [v.operation for v in violations]
        assert "unreviewed_evidence_on_closure" in ops

    def test_no_violations_on_clean_close(self, engine_with_case: CaseRuntimeEngine):
        engine_with_case.close_case("c1")
        violations = engine_with_case.detect_case_violations()
        assert len(violations) == 0

    def test_no_violations_on_open_case(self, engine_with_case: CaseRuntimeEngine):
        violations = engine_with_case.detect_case_violations()
        assert len(violations) == 0

    def test_idempotent_redetection(self, engine_with_case: CaseRuntimeEngine):
        engine_with_case.update_case_status("c1", CaseStatus.CLOSED)
        v1 = engine_with_case.detect_case_violations()
        v2 = engine_with_case.detect_case_violations()
        assert len(v1) >= 1
        assert len(v2) == 0  # Already detected, not duplicated

    def test_violation_count_property(self, engine_with_case: CaseRuntimeEngine):
        assert engine_with_case.violation_count == 0
        engine_with_case.update_case_status("c1", CaseStatus.CLOSED)
        engine_with_case.detect_case_violations()
        assert engine_with_case.violation_count >= 1

    def test_violations_have_correct_tenant(self, engine_with_case: CaseRuntimeEngine):
        engine_with_case.update_case_status("c1", CaseStatus.CLOSED)
        violations = engine_with_case.detect_case_violations()
        for v in violations:
            assert v.tenant_id == "t1"

    def test_both_violation_types_at_once(self, engine_with_case: CaseRuntimeEngine):
        engine_with_case.add_evidence("e1", "c1", "log", "s1")
        engine_with_case.update_case_status("c1", CaseStatus.CLOSED)
        violations = engine_with_case.detect_case_violations()
        ops = {v.operation for v in violations}
        assert "closed_without_decision" in ops
        assert "unreviewed_evidence_on_closure" in ops


class TestViolationsForCase:
    def test_filter_by_case(self, engine: CaseRuntimeEngine):
        engine.open_case("c1", "t1", "A")
        engine.open_case("c2", "t1", "B")
        engine.update_case_status("c1", CaseStatus.CLOSED)
        engine.detect_case_violations()
        result = engine.violations_for_case("c1")
        assert len(result) >= 1
        assert all(v.case_id == "c1" for v in result)
        assert engine.violations_for_case("c2") == ()

    def test_empty_for_no_violations(self, engine_with_case: CaseRuntimeEngine):
        assert engine_with_case.violations_for_case("c1") == ()


class TestViolationsForTenant:
    def test_filter_by_tenant(self, engine: CaseRuntimeEngine):
        engine.open_case("c1", "t1", "A")
        engine.open_case("c2", "t2", "B")
        engine.update_case_status("c1", CaseStatus.CLOSED)
        engine.detect_case_violations()
        t1_violations = engine.violations_for_tenant("t1")
        t2_violations = engine.violations_for_tenant("t2")
        assert len(t1_violations) >= 1
        assert len(t2_violations) == 0

    def test_empty_for_unknown_tenant(self, engine: CaseRuntimeEngine):
        assert engine.violations_for_tenant("nonexistent") == ()


# ===================================================================
# Snapshots & state
# ===================================================================


class TestCaseSnapshot:
    def test_captures_all_counters(self, engine: CaseRuntimeEngine):
        engine.open_case("c1", "t1", "A")
        engine.add_evidence("e1", "c1", "log", "s1")
        engine.review_evidence("r1", "c1", "e1", "rev1")
        engine.record_finding("f1", "c1", "Finding")
        engine.make_case_decision("d1", "c1")

        snap = engine.case_snapshot("snap1", scope_ref_id="test")
        assert isinstance(snap, CaseSnapshot)
        assert snap.snapshot_id == "snap1"
        assert snap.scope_ref_id == "test"
        assert snap.total_cases == 1
        assert snap.open_cases == 1
        assert snap.total_evidence == 1
        assert snap.total_reviews == 1
        assert snap.total_findings == 1
        assert snap.total_decisions == 1
        assert snap.total_violations == 0
        assert snap.captured_at != ""

    def test_duplicate_snapshot_id_raises(self, engine: CaseRuntimeEngine):
        engine.case_snapshot("snap1")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate snapshot_id"):
            engine.case_snapshot("snap1")

    def test_snapshot_reflects_closed_cases(self, engine_with_case: CaseRuntimeEngine):
        engine_with_case.close_case("c1")
        snap = engine_with_case.case_snapshot("snap1")
        assert snap.total_cases == 1
        assert snap.open_cases == 0

    def test_snapshot_with_violations(self, engine_with_case: CaseRuntimeEngine):
        engine_with_case.update_case_status("c1", CaseStatus.CLOSED)
        engine_with_case.detect_case_violations()
        snap = engine_with_case.case_snapshot("snap1")
        assert snap.total_violations >= 1

    def test_default_scope_ref_id(self, engine: CaseRuntimeEngine):
        snap = engine.case_snapshot("snap1")
        assert snap.scope_ref_id == ""


class TestStateHash:
    def test_changes_after_mutation(self, engine: CaseRuntimeEngine):
        h1 = engine.state_hash()
        engine.open_case("c1", "t1", "A")
        h2 = engine.state_hash()
        assert h1 != h2

    def test_same_state_same_hash(self, engine: CaseRuntimeEngine):
        h1 = engine.state_hash()
        h2 = engine.state_hash()
        assert h1 == h2

    def test_changes_after_evidence(self, engine_with_case: CaseRuntimeEngine):
        h1 = engine_with_case.state_hash()
        engine_with_case.add_evidence("e1", "c1", "log", "s1")
        h2 = engine_with_case.state_hash()
        assert h1 != h2

    def test_changes_after_review(self, engine_with_case: CaseRuntimeEngine):
        engine_with_case.add_evidence("e1", "c1", "log", "s1")
        h1 = engine_with_case.state_hash()
        engine_with_case.review_evidence("r1", "c1", "e1", "rev1")
        h2 = engine_with_case.state_hash()
        assert h1 != h2

    def test_changes_after_finding(self, engine_with_case: CaseRuntimeEngine):
        h1 = engine_with_case.state_hash()
        engine_with_case.record_finding("f1", "c1", "Finding")
        h2 = engine_with_case.state_hash()
        assert h1 != h2

    def test_changes_after_decision(self, engine_with_case: CaseRuntimeEngine):
        h1 = engine_with_case.state_hash()
        engine_with_case.make_case_decision("d1", "c1")
        h2 = engine_with_case.state_hash()
        assert h1 != h2

    def test_changes_after_close(self, engine_with_case: CaseRuntimeEngine):
        h1 = engine_with_case.state_hash()
        engine_with_case.close_case("c1")
        h2 = engine_with_case.state_hash()
        assert h1 != h2

    def test_changes_after_violation_detection(self, engine_with_case: CaseRuntimeEngine):
        engine_with_case.update_case_status("c1", CaseStatus.CLOSED)
        h1 = engine_with_case.state_hash()
        engine_with_case.detect_case_violations()
        h2 = engine_with_case.state_hash()
        assert h1 != h2

    def test_hash_is_string(self, engine: CaseRuntimeEngine):
        h = engine.state_hash()
        assert isinstance(h, str)
        assert len(h) == 64


# ===================================================================
# Count properties
# ===================================================================


class TestCountProperties:
    def test_case_count(self, engine: CaseRuntimeEngine):
        assert engine.case_count == 0
        engine.open_case("c1", "t1", "A")
        assert engine.case_count == 1
        engine.open_case("c2", "t1", "B")
        assert engine.case_count == 2

    def test_open_case_count_excludes_closed(self, engine: CaseRuntimeEngine):
        engine.open_case("c1", "t1", "A")
        engine.open_case("c2", "t1", "B")
        assert engine.open_case_count == 2
        engine.close_case("c1")
        assert engine.open_case_count == 1

    def test_open_case_count_includes_escalated(self, engine: CaseRuntimeEngine):
        engine.open_case("c1", "t1", "A")
        engine.escalate_case("c1", CaseSeverity.HIGH)
        assert engine.open_case_count == 1

    def test_evidence_count_after_multiple(self, engine_with_case: CaseRuntimeEngine):
        for i in range(5):
            engine_with_case.add_evidence(f"e{i}", "c1", "log", f"s{i}")
        assert engine_with_case.evidence_count == 5

    def test_review_count_after_multiple(self, engine_with_case: CaseRuntimeEngine):
        for i in range(3):
            engine_with_case.add_evidence(f"e{i}", "c1", "log", f"s{i}")
            engine_with_case.review_evidence(f"r{i}", "c1", f"e{i}", "rev1")
        assert engine_with_case.review_count == 3

    def test_finding_count_after_multiple(self, engine_with_case: CaseRuntimeEngine):
        for i in range(4):
            engine_with_case.record_finding(f"f{i}", "c1", f"Finding {i}")
        assert engine_with_case.finding_count == 4

    def test_decision_count_after_close(self, engine_with_case: CaseRuntimeEngine):
        engine_with_case.close_case("c1")
        assert engine_with_case.decision_count == 1

    def test_violation_count_after_detection(self, engine_with_case: CaseRuntimeEngine):
        engine_with_case.update_case_status("c1", CaseStatus.CLOSED)
        engine_with_case.detect_case_violations()
        assert engine_with_case.violation_count >= 1

    def test_assignment_count_after_multiple(self, engine_with_case: CaseRuntimeEngine):
        engine_with_case.assign_case("a1", "c1", "u1")
        engine_with_case.assign_case("a2", "c1", "u2")
        assert engine_with_case.assignment_count == 2

    def test_collection_count_after_multiple(self, engine_with_case: CaseRuntimeEngine):
        engine_with_case.add_evidence("e1", "c1", "log", "s1")
        engine_with_case.collect_evidence("col1", "c1", ("e1",))
        engine_with_case.collect_evidence("col2", "c1", ("e1",))
        assert engine_with_case.collection_count == 2


# ===================================================================
# Golden scenarios
# ===================================================================


class TestGoldenScenario1ControlFailure:
    """Control failure -> case -> assign reviewer -> add evidence -> review -> finding -> close."""

    def test_full_flow(self, engine: CaseRuntimeEngine):
        # Open case for control failure
        case = engine.open_case(
            "cf-001", "tenant-alpha", "Control Failure Detected",
            kind=CaseKind.INCIDENT, severity=CaseSeverity.MEDIUM,
            description="Automated control check failed",
        )
        assert case.status == CaseStatus.OPEN

        # Assign a reviewer
        assignment = engine.assign_case("asgn-1", "cf-001", "reviewer-jane", role="reviewer")
        assert assignment.role == "reviewer"
        assert assignment.assignee_id == "reviewer-jane"

        # Add evidence
        ev = engine.add_evidence(
            "ev-ctrl-1", "cf-001", "control_log", "ctrl-check-42",
            title="Control check output log",
        )
        assert ev.status == EvidenceStatus.PENDING

        # Admit and review
        engine.admit_evidence("ev-ctrl-1")
        review = engine.review_evidence(
            "rev-1", "cf-001", "ev-ctrl-1", "reviewer-jane",
            disposition=ReviewDisposition.ACCEPTED,
            notes="Confirmed control failure",
        )
        assert review.disposition == ReviewDisposition.ACCEPTED
        assert engine.get_evidence("ev-ctrl-1").status == EvidenceStatus.REVIEWED

        # Record finding
        finding = engine.record_finding(
            "find-1", "cf-001", "Control X failed validation",
            severity=FindingSeverity.MEDIUM,
            evidence_ids=("ev-ctrl-1",),
            remediation="Re-run control with updated parameters",
        )
        assert finding.severity == FindingSeverity.MEDIUM

        # Close case
        report = engine.close_case(
            "cf-001",
            disposition=CaseClosureDisposition.REMEDIATED,
            decided_by="reviewer-jane",
            reason="Control re-run passed after parameter update",
        )
        assert report.total_evidence == 1
        assert report.total_reviews == 1
        assert report.total_findings == 1
        assert report.disposition == CaseClosureDisposition.REMEDIATED
        assert engine.get_case("cf-001").status == CaseStatus.CLOSED


class TestGoldenScenario2LegalHold:
    """Legal-hold evidence cannot be excluded from a case."""

    def test_legal_hold_cannot_be_excluded(self, engine: CaseRuntimeEngine):
        engine.open_case("lh-001", "tenant-beta", "Legal Hold Case", kind=CaseKind.LEGAL)
        ev = engine.add_evidence(
            "ev-lh-1", "lh-001", "legal_hold", "doc-99",
            title="Preserved document under legal hold",
        )
        assert ev.source_type == "legal_hold"

        # Attempt to exclude should fail
        with pytest.raises(RuntimeCoreInvariantError, match="Cannot exclude legal-hold"):
            engine.exclude_evidence("ev-lh-1")

        # Evidence remains PENDING
        assert engine.get_evidence("ev-lh-1").status == EvidenceStatus.PENDING

        # Can still admit and review it
        engine.admit_evidence("ev-lh-1")
        assert engine.get_evidence("ev-lh-1").status == EvidenceStatus.ADMITTED

        engine.review_evidence(
            "rev-lh-1", "lh-001", "ev-lh-1", "legal-reviewer",
            disposition=ReviewDisposition.ACCEPTED,
        )
        assert engine.get_evidence("ev-lh-1").status == EvidenceStatus.REVIEWED


class TestGoldenScenario3MultiEvidenceAutoEscalation:
    """Multiple evidence -> collection -> reviews -> finding HIGH -> auto-escalation."""

    def test_auto_escalation_flow(self, engine: CaseRuntimeEngine):
        engine.open_case("me-001", "tenant-gamma", "Multi-evidence Case")
        assert engine.get_case("me-001").severity == CaseSeverity.MEDIUM

        # Add 3 evidence items
        for i in range(3):
            engine.add_evidence(f"ev-me-{i}", "me-001", "artifact", f"src-{i}")

        # Collect them
        col = engine.collect_evidence(
            "col-me-1", "me-001",
            ("ev-me-0", "ev-me-1", "ev-me-2"),
            title="Artifact collection",
        )
        assert len(col.evidence_ids) == 3

        # Review all with ACCEPTED
        for i in range(3):
            engine.review_evidence(
                f"rev-me-{i}", "me-001", f"ev-me-{i}", "analyst1",
                disposition=ReviewDisposition.ACCEPTED,
            )

        # All evidence should be REVIEWED
        for i in range(3):
            assert engine.get_evidence(f"ev-me-{i}").status == EvidenceStatus.REVIEWED

        # Record HIGH finding -> auto-escalate
        engine.record_finding(
            "find-me-1", "me-001", "Critical pattern detected",
            severity=FindingSeverity.HIGH,
            evidence_ids=("ev-me-0", "ev-me-1", "ev-me-2"),
        )
        case = engine.get_case("me-001")
        assert case.severity == CaseSeverity.HIGH
        assert case.status == CaseStatus.ESCALATED

        # Close
        report = engine.close_case("me-001")
        assert report.total_evidence == 3
        assert report.total_reviews == 3
        assert report.total_findings == 1


class TestGoldenScenario4FaultCampaign:
    """Fault campaign -> case -> preserve evidence -> review -> remediation decision."""

    def test_fault_campaign_flow(self, engine: CaseRuntimeEngine):
        case = engine.open_case(
            "fc-001", "tenant-delta", "Fault Campaign Analysis",
            kind=CaseKind.FAULT_ANALYSIS, severity=CaseSeverity.HIGH,
        )
        assert case.kind == CaseKind.FAULT_ANALYSIS

        # Assign investigator
        engine.assign_case("asgn-fc-1", "fc-001", "investigator-bob", role="investigator")

        # Add and preserve evidence
        engine.add_evidence(
            "ev-fc-1", "fc-001", "fault_log", "fault-123",
            title="Fault trace log",
        )
        engine.add_evidence(
            "ev-fc-2", "fc-001", "metric_dump", "metrics-456",
            title="System metrics snapshot",
        )
        engine.admit_evidence("ev-fc-1")
        engine.admit_evidence("ev-fc-2")

        # Review evidence
        engine.review_evidence(
            "rev-fc-1", "fc-001", "ev-fc-1", "investigator-bob",
            disposition=ReviewDisposition.ACCEPTED,
            notes="Fault trace confirms root cause",
        )
        engine.review_evidence(
            "rev-fc-2", "fc-001", "ev-fc-2", "investigator-bob",
            disposition=ReviewDisposition.ACCEPTED,
            notes="Metrics corroborate fault timeline",
        )

        # Record finding
        engine.record_finding(
            "find-fc-1", "fc-001", "Root cause identified: memory leak in service X",
            severity=FindingSeverity.MEDIUM,
            evidence_ids=("ev-fc-1", "ev-fc-2"),
            remediation="Deploy hotfix to service X, increase memory limits",
        )

        # Make remediation decision and close
        report = engine.close_case(
            "fc-001",
            disposition=CaseClosureDisposition.REMEDIATED,
            decided_by="investigator-bob",
            reason="Hotfix deployed, fault resolved",
        )
        assert report.disposition == CaseClosureDisposition.REMEDIATED
        assert report.total_evidence == 2
        assert report.total_reviews == 2
        assert report.total_findings == 1


class TestGoldenScenario5MultiTenantIsolation:
    """Cases from different tenants don't cross."""

    def test_tenant_isolation(self, engine: CaseRuntimeEngine):
        # Create cases for different tenants
        engine.open_case("c-t1-1", "tenant-1", "Tenant 1 Case A")
        engine.open_case("c-t1-2", "tenant-1", "Tenant 1 Case B")
        engine.open_case("c-t2-1", "tenant-2", "Tenant 2 Case A")
        engine.open_case("c-t3-1", "tenant-3", "Tenant 3 Case A")

        # Tenant 1 sees only their cases
        t1_cases = engine.cases_for_tenant("tenant-1")
        assert len(t1_cases) == 2
        assert all(c.tenant_id == "tenant-1" for c in t1_cases)

        # Tenant 2 sees only theirs
        t2_cases = engine.cases_for_tenant("tenant-2")
        assert len(t2_cases) == 1
        assert t2_cases[0].tenant_id == "tenant-2"

        # Add evidence to different tenant cases
        engine.add_evidence("ev-t1-1", "c-t1-1", "log", "s1")
        engine.add_evidence("ev-t2-1", "c-t2-1", "log", "s2")

        # Evidence for case only returns matching case
        assert len(engine.evidence_for_case("c-t1-1")) == 1
        assert len(engine.evidence_for_case("c-t2-1")) == 1
        assert len(engine.evidence_for_case("c-t1-2")) == 0

        # Violations filter by tenant
        engine.update_case_status("c-t1-1", CaseStatus.CLOSED)
        engine.detect_case_violations()
        t1_violations = engine.violations_for_tenant("tenant-1")
        t2_violations = engine.violations_for_tenant("tenant-2")
        assert len(t1_violations) >= 1
        assert len(t2_violations) == 0

        # Unknown tenant returns empty
        assert engine.cases_for_tenant("tenant-99") == ()
        assert engine.violations_for_tenant("tenant-99") == ()


class TestGoldenScenario6FullLifecycle:
    """Open -> assign -> evidence -> review -> finding -> decision -> close -> snapshot."""

    def test_complete_lifecycle(self, engine: CaseRuntimeEngine):
        # 1. Open
        case = engine.open_case(
            "lc-001", "lifecycle-tenant", "Full Lifecycle Case",
            kind=CaseKind.COMPLIANCE, severity=CaseSeverity.LOW,
            description="End-to-end lifecycle test",
            opened_by="system-test",
        )
        assert case.status == CaseStatus.OPEN
        h0 = engine.state_hash()

        # 2. Assign
        engine.assign_case("asgn-lc-1", "lc-001", "auditor-alice", role="auditor")
        engine.assign_case("asgn-lc-2", "lc-001", "reviewer-bob", role="reviewer")
        assert engine.assignment_count == 2
        assignments = engine.assignments_for_case("lc-001")
        assert len(assignments) == 2
        h1 = engine.state_hash()
        # Assignments don't change state_hash (it tracks cases/evidence/reviews/findings/decisions/violations)
        # Actually assignments_count is not in state_hash, so h1 may equal h0
        # The state_hash only tracks case_count, open, evidence, reviews, findings, decisions, violations

        # 3. Evidence
        engine.add_evidence("ev-lc-1", "lc-001", "audit_report", "rpt-100", title="Q1 Audit Report")
        engine.add_evidence("ev-lc-2", "lc-001", "policy_doc", "pol-200", title="Policy Document")
        engine.add_evidence("ev-lc-3", "lc-001", "access_log", "log-300", title="Access Logs")
        assert engine.evidence_count == 3
        h2 = engine.state_hash()
        assert h2 != h0  # evidence changed

        # Admit all
        for eid in ("ev-lc-1", "ev-lc-2", "ev-lc-3"):
            engine.admit_evidence(eid)
        for eid in ("ev-lc-1", "ev-lc-2", "ev-lc-3"):
            assert engine.get_evidence(eid).status == EvidenceStatus.ADMITTED

        # Collect
        engine.collect_evidence(
            "col-lc-1", "lc-001",
            ("ev-lc-1", "ev-lc-2", "ev-lc-3"),
            title="Complete evidence set",
        )
        assert engine.collection_count == 1

        # 4. Review
        engine.review_evidence(
            "rev-lc-1", "lc-001", "ev-lc-1", "reviewer-bob",
            disposition=ReviewDisposition.ACCEPTED, notes="Audit report verified",
        )
        engine.review_evidence(
            "rev-lc-2", "lc-001", "ev-lc-2", "reviewer-bob",
            disposition=ReviewDisposition.ACCEPTED, notes="Policy up to date",
        )
        engine.review_evidence(
            "rev-lc-3", "lc-001", "ev-lc-3", "reviewer-bob",
            disposition=ReviewDisposition.REJECTED, notes="Access logs incomplete",
        )
        assert engine.review_count == 3
        assert engine.get_evidence("ev-lc-1").status == EvidenceStatus.REVIEWED
        assert engine.get_evidence("ev-lc-2").status == EvidenceStatus.REVIEWED
        assert engine.get_evidence("ev-lc-3").status == EvidenceStatus.CHALLENGED

        # 5. Finding
        engine.record_finding(
            "find-lc-1", "lc-001", "Access logging gaps detected",
            severity=FindingSeverity.LOW,
            evidence_ids=("ev-lc-3",),
            remediation="Enable comprehensive access logging",
        )
        assert engine.finding_count == 1
        findings = engine.findings_for_case("lc-001")
        assert len(findings) == 1

        # 6. Decision (explicit before close)
        engine.make_case_decision(
            "dec-lc-1", "lc-001",
            disposition=CaseClosureDisposition.RESOLVED,
            decided_by="auditor-alice",
            reason="Findings addressed, logging gaps remediated",
        )
        assert engine.decision_count == 1

        # 7. Close
        report = engine.close_case(
            "lc-001",
            disposition=CaseClosureDisposition.RESOLVED,
            decided_by="auditor-alice",
            reason="Case resolved after remediation",
        )
        assert engine.get_case("lc-001").status == CaseStatus.CLOSED
        assert report.total_evidence == 3
        assert report.total_reviews == 3
        assert report.total_findings == 1
        assert report.total_violations == 0
        # close_case also auto-creates a decision
        assert engine.decision_count == 2

        # 8. Snapshot
        snap = engine.case_snapshot("snap-lc-final", scope_ref_id="lc-001")
        assert snap.total_cases == 1
        assert snap.open_cases == 0
        assert snap.total_evidence == 3
        assert snap.total_reviews == 3
        assert snap.total_findings == 1
        assert snap.total_decisions == 2
        assert snap.total_violations == 0

        # Verify no violations
        violations = engine.detect_case_violations()
        assert len(violations) == 0


# ===================================================================
# Additional edge cases
# ===================================================================


class TestEdgeCases:
    def test_multiple_assignments_same_case(self, engine_with_case: CaseRuntimeEngine):
        engine_with_case.assign_case("a1", "c1", "user1", role="investigator")
        engine_with_case.assign_case("a2", "c1", "user2", role="reviewer")
        engine_with_case.assign_case("a3", "c1", "user3", role="observer")
        assignments = engine_with_case.assignments_for_case("c1")
        assert len(assignments) == 3
        roles = {a.role for a in assignments}
        assert roles == {"investigator", "reviewer", "observer"}

    def test_multiple_reviews_same_evidence(self, engine_with_case: CaseRuntimeEngine):
        engine_with_case.add_evidence("e1", "c1", "log", "s1")
        engine_with_case.review_evidence("r1", "c1", "e1", "rev1", disposition=ReviewDisposition.INCONCLUSIVE)
        engine_with_case.review_evidence("r2", "c1", "e1", "rev2", disposition=ReviewDisposition.ACCEPTED)
        assert engine_with_case.get_evidence("e1").status == EvidenceStatus.REVIEWED
        assert engine_with_case.review_count == 2

    def test_exclude_then_review_does_not_transition(self, engine_with_case: CaseRuntimeEngine):
        engine_with_case.add_evidence("e1", "c1", "log", "s1")
        engine_with_case.exclude_evidence("e1")
        # Reviewing excluded evidence with ACCEPTED should NOT change status
        # because status is EXCLUDED, not PENDING or ADMITTED
        engine_with_case.review_evidence(
            "r1", "c1", "e1", "rev1", disposition=ReviewDisposition.ACCEPTED
        )
        assert engine_with_case.get_evidence("e1").status == EvidenceStatus.EXCLUDED

    def test_case_status_transitions_chain(self, engine_with_case: CaseRuntimeEngine):
        engine_with_case.update_case_status("c1", CaseStatus.IN_PROGRESS)
        engine_with_case.update_case_status("c1", CaseStatus.UNDER_REVIEW)
        engine_with_case.update_case_status("c1", CaseStatus.PENDING_DECISION)
        engine_with_case.update_case_status("c1", CaseStatus.CLOSED)
        assert engine_with_case.get_case("c1").status == CaseStatus.CLOSED

    def test_many_cases_count(self, engine: CaseRuntimeEngine):
        for i in range(20):
            engine.open_case(f"c{i}", "t1", f"Case {i}")
        assert engine.case_count == 20
        assert engine.open_case_count == 20

    def test_snapshot_empty_engine(self, engine: CaseRuntimeEngine):
        snap = engine.case_snapshot("snap-empty")
        assert snap.total_cases == 0
        assert snap.open_cases == 0
        assert snap.total_evidence == 0
        assert snap.total_reviews == 0
        assert snap.total_findings == 0
        assert snap.total_decisions == 0
        assert snap.total_violations == 0

    def test_evidence_status_preserved_on_reject_after_exclude(self, engine_with_case: CaseRuntimeEngine):
        engine_with_case.add_evidence("e1", "c1", "log", "s1")
        engine_with_case.exclude_evidence("e1")
        engine_with_case.review_evidence(
            "r1", "c1", "e1", "rev1", disposition=ReviewDisposition.REJECTED
        )
        # Should stay EXCLUDED since it's not in PENDING/ADMITTED
        assert engine_with_case.get_evidence("e1").status == EvidenceStatus.EXCLUDED

    def test_close_case_with_multiple_evidence_and_reviews(self, engine: CaseRuntimeEngine):
        engine.open_case("c1", "t1", "Big Case")
        for i in range(10):
            engine.add_evidence(f"e{i}", "c1", "log", f"s{i}")
        for i in range(10):
            engine.review_evidence(f"r{i}", "c1", f"e{i}", "rev1", disposition=ReviewDisposition.ACCEPTED)
        for i in range(5):
            engine.record_finding(f"f{i}", "c1", f"Finding {i}")
        report = engine.close_case("c1")
        assert report.total_evidence == 10
        assert report.total_reviews == 10
        assert report.total_findings == 5

    def test_escalation_from_medium_to_critical(self, engine: CaseRuntimeEngine):
        engine.open_case("c1", "t1", "Case", severity=CaseSeverity.MEDIUM)
        engine.record_finding("f1", "c1", "Critical finding", severity=FindingSeverity.CRITICAL)
        c = engine.get_case("c1")
        assert c.severity == CaseSeverity.CRITICAL
        assert c.status == CaseStatus.ESCALATED

    def test_escalation_from_low_to_high(self, engine: CaseRuntimeEngine):
        engine.open_case("c1", "t1", "Case", severity=CaseSeverity.LOW)
        engine.record_finding("f1", "c1", "High finding", severity=FindingSeverity.HIGH)
        c = engine.get_case("c1")
        assert c.severity == CaseSeverity.HIGH
        assert c.status == CaseStatus.ESCALATED

    def test_no_escalation_when_same_severity(self, engine: CaseRuntimeEngine):
        engine.open_case("c1", "t1", "Case", severity=CaseSeverity.HIGH)
        engine.record_finding("f1", "c1", "High finding", severity=FindingSeverity.HIGH)
        c = engine.get_case("c1")
        # Same severity, no escalation needed
        assert c.severity == CaseSeverity.HIGH
        assert c.status == CaseStatus.OPEN

    def test_reviews_for_case_returns_tuple(self, engine_with_case: CaseRuntimeEngine):
        engine_with_case.add_evidence("e1", "c1", "log", "s1")
        engine_with_case.review_evidence("r1", "c1", "e1", "rev1")
        assert isinstance(engine_with_case.reviews_for_case("c1"), tuple)

    def test_findings_for_case_returns_tuple(self, engine_with_case: CaseRuntimeEngine):
        engine_with_case.record_finding("f1", "c1", "Finding")
        assert isinstance(engine_with_case.findings_for_case("c1"), tuple)

    def test_collections_for_case_returns_tuple(self, engine_with_case: CaseRuntimeEngine):
        engine_with_case.collect_evidence("col1", "c1", ())
        assert isinstance(engine_with_case.collections_for_case("c1"), tuple)

    def test_violations_for_case_returns_tuple(self, engine_with_case: CaseRuntimeEngine):
        assert isinstance(engine_with_case.violations_for_case("c1"), tuple)

    def test_violations_for_tenant_returns_tuple(self, engine_with_case: CaseRuntimeEngine):
        assert isinstance(engine_with_case.violations_for_tenant("t1"), tuple)

    def test_case_record_is_frozen(self, engine_with_case: CaseRuntimeEngine):
        c = engine_with_case.get_case("c1")
        with pytest.raises(AttributeError):
            c.title = "Modified"  # type: ignore[misc]

    def test_evidence_item_is_frozen(self, engine_with_case: CaseRuntimeEngine):
        engine_with_case.add_evidence("e1", "c1", "log", "s1")
        e = engine_with_case.get_evidence("e1")
        with pytest.raises(AttributeError):
            e.title = "Modified"  # type: ignore[misc]

    def test_assignment_is_frozen(self, engine_with_case: CaseRuntimeEngine):
        a = engine_with_case.assign_case("a1", "c1", "user1")
        with pytest.raises(AttributeError):
            a.role = "hacker"  # type: ignore[misc]

    def test_multiple_snapshots_different_ids(self, engine: CaseRuntimeEngine):
        s1 = engine.case_snapshot("snap1")
        engine.open_case("c1", "t1", "A")
        s2 = engine.case_snapshot("snap2")
        assert s1.total_cases == 0
        assert s2.total_cases == 1
