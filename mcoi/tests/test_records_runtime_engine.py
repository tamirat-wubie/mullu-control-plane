"""Purpose: comprehensive tests for the RecordsRuntimeEngine.
Governance scope: runtime-core records / retention / legal hold tests only.
Dependencies: RecordsRuntimeEngine, EventSpineEngine, records_runtime contracts, invariants.
Invariants:
  - Disposal is fail-closed: default decision is DENY.
  - Legal holds override normal disposal.
  - Evidence records are immutable once preserved.
  - Every mutation emits an event.
  - All returns are immutable.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.records_runtime import RecordsRuntimeEngine
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
    RetentionSchedule,
    RetentionStatus,
)
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_engine() -> RecordsRuntimeEngine:
    return RecordsRuntimeEngine(EventSpineEngine())


def _engine_with_record(
    record_id: str = "r-1",
    tenant_id: str = "t-1",
    title: str = "Test Record",
    kind: RecordKind = RecordKind.OPERATIONAL,
    authority: RecordAuthority = RecordAuthority.SYSTEM,
    evidence_grade: EvidenceGrade = EvidenceGrade.PRIMARY,
) -> RecordsRuntimeEngine:
    eng = _make_engine()
    eng.register_record(
        record_id, tenant_id, title,
        kind=kind, authority=authority,
        evidence_grade=evidence_grade,
    )
    return eng


def _engine_with_record_and_schedule(
    record_id: str = "r-1",
    tenant_id: str = "t-1",
    schedule_id: str = "s-1",
    retention_days: int = 365,
    disposal_disposition: DisposalDisposition = DisposalDisposition.DELETE,
    kind: RecordKind = RecordKind.OPERATIONAL,
) -> RecordsRuntimeEngine:
    eng = _make_engine()
    eng.register_record(record_id, tenant_id, "Test Record", kind=kind)
    eng.bind_retention_schedule(
        schedule_id, record_id, tenant_id,
        retention_days=retention_days,
        disposal_disposition=disposal_disposition,
    )
    return eng


# ===================================================================
# 1. Constructor
# ===================================================================


class TestConstructor:
    def test_accepts_event_spine(self) -> None:
        eng = RecordsRuntimeEngine(EventSpineEngine())
        assert eng.record_count == 0

    def test_rejects_none(self) -> None:
        with pytest.raises(RuntimeCoreInvariantError):
            RecordsRuntimeEngine(None)  # type: ignore[arg-type]

    def test_rejects_string(self) -> None:
        with pytest.raises(RuntimeCoreInvariantError):
            RecordsRuntimeEngine("not-an-engine")  # type: ignore[arg-type]

    def test_rejects_dict(self) -> None:
        with pytest.raises(RuntimeCoreInvariantError):
            RecordsRuntimeEngine({})  # type: ignore[arg-type]

    def test_rejects_int(self) -> None:
        with pytest.raises(RuntimeCoreInvariantError):
            RecordsRuntimeEngine(42)  # type: ignore[arg-type]


# ===================================================================
# 2. Properties (fresh engine)
# ===================================================================


class TestPropertiesFresh:
    def test_record_count_zero(self) -> None:
        assert _make_engine().record_count == 0

    def test_schedule_count_zero(self) -> None:
        assert _make_engine().schedule_count == 0

    def test_hold_count_zero(self) -> None:
        assert _make_engine().hold_count == 0

    def test_active_hold_count_zero(self) -> None:
        assert _make_engine().active_hold_count == 0

    def test_link_count_zero(self) -> None:
        assert _make_engine().link_count == 0

    def test_disposal_count_zero(self) -> None:
        assert _make_engine().disposal_count == 0

    def test_violation_count_zero(self) -> None:
        assert _make_engine().violation_count == 0

    def test_review_count_zero(self) -> None:
        assert _make_engine().review_count == 0


# ===================================================================
# 3. Registration & retrieval
# ===================================================================


class TestRegisterRecord:
    def test_register_returns_descriptor(self) -> None:
        eng = _make_engine()
        rec = eng.register_record("r-1", "t-1", "Title")
        assert isinstance(rec, RecordDescriptor)

    def test_register_sets_record_id(self) -> None:
        eng = _make_engine()
        rec = eng.register_record("r-1", "t-1", "Title")
        assert rec.record_id == "r-1"

    def test_register_sets_tenant_id(self) -> None:
        eng = _make_engine()
        rec = eng.register_record("r-1", "t-1", "Title")
        assert rec.tenant_id == "t-1"

    def test_register_sets_title(self) -> None:
        eng = _make_engine()
        rec = eng.register_record("r-1", "t-1", "My Title")
        assert rec.title == "My Title"

    def test_register_default_kind_operational(self) -> None:
        eng = _make_engine()
        rec = eng.register_record("r-1", "t-1", "Title")
        assert rec.kind == RecordKind.OPERATIONAL

    def test_register_default_authority_system(self) -> None:
        eng = _make_engine()
        rec = eng.register_record("r-1", "t-1", "Title")
        assert rec.authority == RecordAuthority.SYSTEM

    def test_register_default_evidence_grade_primary(self) -> None:
        eng = _make_engine()
        rec = eng.register_record("r-1", "t-1", "Title")
        assert rec.evidence_grade == EvidenceGrade.PRIMARY

    def test_register_created_at_populated(self) -> None:
        eng = _make_engine()
        rec = eng.register_record("r-1", "t-1", "Title")
        assert rec.created_at != ""

    def test_register_increments_count(self) -> None:
        eng = _make_engine()
        eng.register_record("r-1", "t-1", "Title")
        assert eng.record_count == 1

    def test_register_duplicate_raises(self) -> None:
        eng = _make_engine()
        eng.register_record("r-1", "t-1", "Title")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate record_id"):
            eng.register_record("r-1", "t-1", "Title2")


class TestRegisterRecordKindCombinations:
    @pytest.mark.parametrize("kind", list(RecordKind))
    def test_register_all_kinds(self, kind: RecordKind) -> None:
        eng = _make_engine()
        rec = eng.register_record("r-1", "t-1", "Title", kind=kind)
        assert rec.kind == kind

    @pytest.mark.parametrize("grade", list(EvidenceGrade))
    def test_register_all_evidence_grades(self, grade: EvidenceGrade) -> None:
        eng = _make_engine()
        rec = eng.register_record("r-1", "t-1", "Title", evidence_grade=grade)
        assert rec.evidence_grade == grade

    @pytest.mark.parametrize("auth", list(RecordAuthority))
    def test_register_all_authorities(self, auth: RecordAuthority) -> None:
        eng = _make_engine()
        rec = eng.register_record("r-1", "t-1", "Title", authority=auth)
        assert rec.authority == auth

    def test_register_with_source_type_and_id(self) -> None:
        eng = _make_engine()
        rec = eng.register_record("r-1", "t-1", "Title", source_type="email", source_id="e-123")
        assert rec.source_type == "email"
        assert rec.source_id == "e-123"

    def test_register_with_classification(self) -> None:
        eng = _make_engine()
        rec = eng.register_record("r-1", "t-1", "Title", classification="confidential")
        assert rec.classification == "confidential"

    def test_register_evidence_with_legal_authority(self) -> None:
        eng = _make_engine()
        rec = eng.register_record(
            "r-1", "t-1", "Evidence",
            kind=RecordKind.EVIDENCE,
            authority=RecordAuthority.LEGAL,
            evidence_grade=EvidenceGrade.PRIMARY,
        )
        assert rec.kind == RecordKind.EVIDENCE
        assert rec.authority == RecordAuthority.LEGAL

    def test_register_compliance_with_executive(self) -> None:
        eng = _make_engine()
        rec = eng.register_record(
            "r-1", "t-1", "Compliance Doc",
            kind=RecordKind.COMPLIANCE,
            authority=RecordAuthority.EXECUTIVE,
            evidence_grade=EvidenceGrade.SECONDARY,
        )
        assert rec.kind == RecordKind.COMPLIANCE
        assert rec.authority == RecordAuthority.EXECUTIVE
        assert rec.evidence_grade == EvidenceGrade.SECONDARY

    def test_register_audit_with_derived_grade(self) -> None:
        eng = _make_engine()
        rec = eng.register_record(
            "r-1", "t-1", "Audit Trail",
            kind=RecordKind.AUDIT,
            evidence_grade=EvidenceGrade.DERIVED,
        )
        assert rec.kind == RecordKind.AUDIT
        assert rec.evidence_grade == EvidenceGrade.DERIVED


class TestGetRecord:
    def test_get_existing_record(self) -> None:
        eng = _engine_with_record()
        rec = eng.get_record("r-1")
        assert rec.record_id == "r-1"

    def test_get_missing_record_raises(self) -> None:
        eng = _make_engine()
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown record_id"):
            eng.get_record("nope")

    def test_get_preserves_all_fields(self) -> None:
        eng = _make_engine()
        eng.register_record(
            "r-1", "t-1", "Title",
            kind=RecordKind.LEGAL,
            authority=RecordAuthority.COMPLIANCE,
            evidence_grade=EvidenceGrade.COPY,
            source_type="archive",
            source_id="a-99",
            classification="secret",
        )
        rec = eng.get_record("r-1")
        assert rec.kind == RecordKind.LEGAL
        assert rec.authority == RecordAuthority.COMPLIANCE
        assert rec.evidence_grade == EvidenceGrade.COPY
        assert rec.source_type == "archive"
        assert rec.source_id == "a-99"
        assert rec.classification == "secret"


class TestRecordsForTenant:
    def test_returns_empty_for_unknown_tenant(self) -> None:
        eng = _make_engine()
        assert eng.records_for_tenant("t-99") == ()

    def test_returns_only_matching_tenant(self) -> None:
        eng = _make_engine()
        eng.register_record("r-1", "t-1", "A")
        eng.register_record("r-2", "t-2", "B")
        eng.register_record("r-3", "t-1", "C")
        result = eng.records_for_tenant("t-1")
        assert len(result) == 2
        ids = {r.record_id for r in result}
        assert ids == {"r-1", "r-3"}

    def test_returns_tuple(self) -> None:
        eng = _engine_with_record()
        result = eng.records_for_tenant("t-1")
        assert isinstance(result, tuple)


# ===================================================================
# 4. Links (evidence lineage)
# ===================================================================


class TestAddLink:
    def test_add_link_returns_record_link(self) -> None:
        eng = _engine_with_record()
        link = eng.add_link("l-1", "r-1", "document", "doc-42")
        assert isinstance(link, RecordLink)

    def test_add_link_sets_fields(self) -> None:
        eng = _engine_with_record()
        link = eng.add_link("l-1", "r-1", "document", "doc-42", "references")
        assert link.link_id == "l-1"
        assert link.record_id == "r-1"
        assert link.target_type == "document"
        assert link.target_id == "doc-42"
        assert link.relationship == "references"

    def test_add_link_default_relationship(self) -> None:
        eng = _engine_with_record()
        link = eng.add_link("l-1", "r-1", "doc", "d-1")
        assert link.relationship == "source"

    def test_add_link_created_at_populated(self) -> None:
        eng = _engine_with_record()
        link = eng.add_link("l-1", "r-1", "doc", "d-1")
        assert link.created_at != ""

    def test_add_link_increments_count(self) -> None:
        eng = _engine_with_record()
        eng.add_link("l-1", "r-1", "doc", "d-1")
        assert eng.link_count == 1

    def test_add_link_duplicate_raises(self) -> None:
        eng = _engine_with_record()
        eng.add_link("l-1", "r-1", "doc", "d-1")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate link_id"):
            eng.add_link("l-1", "r-1", "doc", "d-2")

    def test_add_link_unknown_record_raises(self) -> None:
        eng = _make_engine()
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown record_id"):
            eng.add_link("l-1", "no-rec", "doc", "d-1")

    def test_link_is_frozen(self) -> None:
        eng = _engine_with_record()
        link = eng.add_link("l-1", "r-1", "doc", "d-1")
        with pytest.raises(AttributeError):
            link.link_id = "changed"  # type: ignore[misc]


class TestLinksForRecord:
    def test_returns_empty_for_no_links(self) -> None:
        eng = _engine_with_record()
        assert eng.links_for_record("r-1") == ()

    def test_returns_correct_links(self) -> None:
        eng = _make_engine()
        eng.register_record("r-1", "t-1", "A")
        eng.register_record("r-2", "t-1", "B")
        eng.add_link("l-1", "r-1", "doc", "d-1")
        eng.add_link("l-2", "r-1", "email", "e-1")
        eng.add_link("l-3", "r-2", "doc", "d-2")
        result = eng.links_for_record("r-1")
        assert len(result) == 2
        ids = {lnk.link_id for lnk in result}
        assert ids == {"l-1", "l-2"}

    def test_returns_tuple(self) -> None:
        eng = _engine_with_record()
        assert isinstance(eng.links_for_record("r-1"), tuple)


# ===================================================================
# 5. Retention schedules
# ===================================================================


class TestBindRetentionSchedule:
    def test_bind_returns_schedule(self) -> None:
        eng = _engine_with_record()
        sched = eng.bind_retention_schedule("s-1", "r-1", "t-1")
        assert isinstance(sched, RetentionSchedule)

    def test_bind_sets_fields(self) -> None:
        eng = _engine_with_record()
        sched = eng.bind_retention_schedule(
            "s-1", "r-1", "t-1",
            retention_days=730,
            disposal_disposition=DisposalDisposition.ARCHIVE,
        )
        assert sched.schedule_id == "s-1"
        assert sched.record_id == "r-1"
        assert sched.tenant_id == "t-1"
        assert sched.retention_days == 730
        assert sched.disposal_disposition == DisposalDisposition.ARCHIVE

    def test_bind_default_active_status(self) -> None:
        eng = _engine_with_record()
        sched = eng.bind_retention_schedule("s-1", "r-1", "t-1")
        assert sched.status == RetentionStatus.ACTIVE

    def test_bind_default_retention_days(self) -> None:
        eng = _engine_with_record()
        sched = eng.bind_retention_schedule("s-1", "r-1", "t-1")
        assert sched.retention_days == 365

    def test_bind_default_disposal_delete(self) -> None:
        eng = _engine_with_record()
        sched = eng.bind_retention_schedule("s-1", "r-1", "t-1")
        assert sched.disposal_disposition == DisposalDisposition.DELETE

    def test_bind_created_at_populated(self) -> None:
        eng = _engine_with_record()
        sched = eng.bind_retention_schedule("s-1", "r-1", "t-1")
        assert sched.created_at != ""

    def test_bind_increments_count(self) -> None:
        eng = _engine_with_record()
        eng.bind_retention_schedule("s-1", "r-1", "t-1")
        assert eng.schedule_count == 1

    def test_bind_duplicate_raises(self) -> None:
        eng = _engine_with_record()
        eng.bind_retention_schedule("s-1", "r-1", "t-1")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate schedule_id"):
            eng.bind_retention_schedule("s-1", "r-1", "t-1")

    def test_bind_unknown_record_raises(self) -> None:
        eng = _make_engine()
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown record_id"):
            eng.bind_retention_schedule("s-1", "no-rec", "t-1")

    def test_bind_with_scope_ref_id(self) -> None:
        eng = _engine_with_record()
        sched = eng.bind_retention_schedule("s-1", "r-1", "t-1", scope_ref_id="policy-99")
        assert sched.scope_ref_id == "policy-99"

    def test_bind_with_expires_at(self) -> None:
        eng = _engine_with_record()
        sched = eng.bind_retention_schedule("s-1", "r-1", "t-1", expires_at="2030-01-01T00:00:00+00:00")
        assert sched.expires_at == "2030-01-01T00:00:00+00:00"

    def test_schedule_is_frozen(self) -> None:
        eng = _engine_with_record()
        sched = eng.bind_retention_schedule("s-1", "r-1", "t-1")
        with pytest.raises(AttributeError):
            sched.status = RetentionStatus.EXPIRED  # type: ignore[misc]


class TestSchedulesForRecord:
    def test_returns_empty_when_none(self) -> None:
        eng = _engine_with_record()
        assert eng.schedules_for_record("r-1") == ()

    def test_returns_matching_schedules(self) -> None:
        eng = _make_engine()
        eng.register_record("r-1", "t-1", "A")
        eng.register_record("r-2", "t-1", "B")
        eng.bind_retention_schedule("s-1", "r-1", "t-1")
        eng.bind_retention_schedule("s-2", "r-1", "t-1", retention_days=730)
        eng.bind_retention_schedule("s-3", "r-2", "t-1")
        result = eng.schedules_for_record("r-1")
        assert len(result) == 2
        ids = {s.schedule_id for s in result}
        assert ids == {"s-1", "s-2"}

    def test_returns_tuple(self) -> None:
        eng = _engine_with_record()
        assert isinstance(eng.schedules_for_record("r-1"), tuple)


# ===================================================================
# 6. Legal holds
# ===================================================================


class TestPlaceHold:
    def test_place_hold_returns_hold(self) -> None:
        eng = _engine_with_record()
        hold = eng.place_hold("h-1", "r-1", "t-1")
        assert isinstance(hold, LegalHoldRecord)

    def test_place_hold_sets_fields(self) -> None:
        eng = _engine_with_record()
        hold = eng.place_hold("h-1", "r-1", "t-1", reason="litigation", authority=RecordAuthority.LEGAL)
        assert hold.hold_id == "h-1"
        assert hold.record_id == "r-1"
        assert hold.tenant_id == "t-1"
        assert hold.reason == "litigation"
        assert hold.authority == RecordAuthority.LEGAL

    def test_place_hold_active_status(self) -> None:
        eng = _engine_with_record()
        hold = eng.place_hold("h-1", "r-1", "t-1")
        assert hold.status == HoldStatus.ACTIVE

    def test_place_hold_placed_at_populated(self) -> None:
        eng = _engine_with_record()
        hold = eng.place_hold("h-1", "r-1", "t-1")
        assert hold.placed_at != ""

    def test_place_hold_increments_count(self) -> None:
        eng = _engine_with_record()
        eng.place_hold("h-1", "r-1", "t-1")
        assert eng.hold_count == 1
        assert eng.active_hold_count == 1

    def test_place_hold_duplicate_raises(self) -> None:
        eng = _engine_with_record()
        eng.place_hold("h-1", "r-1", "t-1")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate hold_id"):
            eng.place_hold("h-1", "r-1", "t-1")

    def test_place_hold_unknown_record_raises(self) -> None:
        eng = _make_engine()
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown record_id"):
            eng.place_hold("h-1", "no-rec", "t-1")

    def test_place_hold_changes_schedules_to_held(self) -> None:
        eng = _engine_with_record_and_schedule()
        eng.place_hold("h-1", "r-1", "t-1")
        scheds = eng.schedules_for_record("r-1")
        assert all(s.status == RetentionStatus.HELD for s in scheds)

    def test_place_hold_changes_multiple_schedules_to_held(self) -> None:
        eng = _engine_with_record()
        eng.bind_retention_schedule("s-1", "r-1", "t-1")
        eng.bind_retention_schedule("s-2", "r-1", "t-1", retention_days=730)
        eng.place_hold("h-1", "r-1", "t-1")
        scheds = eng.schedules_for_record("r-1")
        assert len(scheds) == 2
        assert all(s.status == RetentionStatus.HELD for s in scheds)

    def test_place_hold_does_not_change_other_records_schedules(self) -> None:
        eng = _make_engine()
        eng.register_record("r-1", "t-1", "A")
        eng.register_record("r-2", "t-1", "B")
        eng.bind_retention_schedule("s-1", "r-1", "t-1")
        eng.bind_retention_schedule("s-2", "r-2", "t-1")
        eng.place_hold("h-1", "r-1", "t-1")
        s2 = eng.schedules_for_record("r-2")
        assert all(s.status == RetentionStatus.ACTIVE for s in s2)

    def test_hold_is_frozen(self) -> None:
        eng = _engine_with_record()
        hold = eng.place_hold("h-1", "r-1", "t-1")
        with pytest.raises(AttributeError):
            hold.status = HoldStatus.RELEASED  # type: ignore[misc]


class TestReleaseHold:
    def test_release_returns_updated_hold(self) -> None:
        eng = _engine_with_record()
        eng.place_hold("h-1", "r-1", "t-1")
        released = eng.release_hold("h-1")
        assert isinstance(released, LegalHoldRecord)
        assert released.status == HoldStatus.RELEASED

    def test_release_sets_released_at(self) -> None:
        eng = _engine_with_record()
        eng.place_hold("h-1", "r-1", "t-1")
        released = eng.release_hold("h-1")
        assert released.released_at != ""

    def test_release_unknown_hold_raises(self) -> None:
        eng = _make_engine()
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown hold_id"):
            eng.release_hold("nope")

    def test_release_already_released_raises(self) -> None:
        eng = _engine_with_record()
        eng.place_hold("h-1", "r-1", "t-1")
        eng.release_hold("h-1")
        with pytest.raises(RuntimeCoreInvariantError, match="Cannot release hold"):
            eng.release_hold("h-1")

    def test_release_decrements_active_hold_count(self) -> None:
        eng = _engine_with_record()
        eng.place_hold("h-1", "r-1", "t-1")
        assert eng.active_hold_count == 1
        eng.release_hold("h-1")
        assert eng.active_hold_count == 0
        # total hold count stays the same
        assert eng.hold_count == 1

    def test_release_restores_schedules_when_no_active_holds(self) -> None:
        eng = _engine_with_record_and_schedule()
        eng.place_hold("h-1", "r-1", "t-1")
        scheds = eng.schedules_for_record("r-1")
        assert scheds[0].status == RetentionStatus.HELD
        eng.release_hold("h-1")
        scheds = eng.schedules_for_record("r-1")
        assert scheds[0].status == RetentionStatus.ACTIVE

    def test_release_does_not_restore_schedules_with_remaining_holds(self) -> None:
        eng = _engine_with_record_and_schedule()
        eng.place_hold("h-1", "r-1", "t-1")
        eng.place_hold("h-2", "r-1", "t-1")
        eng.release_hold("h-1")
        scheds = eng.schedules_for_record("r-1")
        assert scheds[0].status == RetentionStatus.HELD

    def test_release_both_holds_then_restores(self) -> None:
        eng = _engine_with_record_and_schedule()
        eng.place_hold("h-1", "r-1", "t-1")
        eng.place_hold("h-2", "r-1", "t-1")
        eng.release_hold("h-1")
        eng.release_hold("h-2")
        scheds = eng.schedules_for_record("r-1")
        assert scheds[0].status == RetentionStatus.ACTIVE


class TestHoldsForRecord:
    def test_returns_empty_when_none(self) -> None:
        eng = _engine_with_record()
        assert eng.holds_for_record("r-1") == ()

    def test_returns_correct_holds(self) -> None:
        eng = _make_engine()
        eng.register_record("r-1", "t-1", "A")
        eng.register_record("r-2", "t-1", "B")
        eng.place_hold("h-1", "r-1", "t-1")
        eng.place_hold("h-2", "r-1", "t-1")
        eng.place_hold("h-3", "r-2", "t-1")
        result = eng.holds_for_record("r-1")
        assert len(result) == 2

    def test_returns_tuple(self) -> None:
        eng = _engine_with_record()
        assert isinstance(eng.holds_for_record("r-1"), tuple)


class TestActiveHoldsForRecord:
    def test_returns_only_active(self) -> None:
        eng = _engine_with_record()
        eng.place_hold("h-1", "r-1", "t-1")
        eng.place_hold("h-2", "r-1", "t-1")
        eng.release_hold("h-1")
        active = eng.active_holds_for_record("r-1")
        assert len(active) == 1
        assert active[0].hold_id == "h-2"

    def test_returns_empty_when_all_released(self) -> None:
        eng = _engine_with_record()
        eng.place_hold("h-1", "r-1", "t-1")
        eng.release_hold("h-1")
        assert eng.active_holds_for_record("r-1") == ()


class TestIsUnderHold:
    def test_false_when_no_holds(self) -> None:
        eng = _engine_with_record()
        assert eng.is_under_hold("r-1") is False

    def test_true_when_active_hold(self) -> None:
        eng = _engine_with_record()
        eng.place_hold("h-1", "r-1", "t-1")
        assert eng.is_under_hold("r-1") is True

    def test_false_after_release(self) -> None:
        eng = _engine_with_record()
        eng.place_hold("h-1", "r-1", "t-1")
        eng.release_hold("h-1")
        assert eng.is_under_hold("r-1") is False

    def test_true_with_one_active_one_released(self) -> None:
        eng = _engine_with_record()
        eng.place_hold("h-1", "r-1", "t-1")
        eng.place_hold("h-2", "r-1", "t-1")
        eng.release_hold("h-1")
        assert eng.is_under_hold("r-1") is True


# ===================================================================
# 7. Disposal evaluation (fail-closed)
# ===================================================================


class TestEvaluateDisposal:
    def test_unknown_record_raises(self) -> None:
        eng = _make_engine()
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown record_id"):
            eng.evaluate_disposal("nope")

    def test_under_hold_returns_deny(self) -> None:
        eng = _engine_with_record()
        eng.place_hold("h-1", "r-1", "t-1")
        dec = eng.evaluate_disposal("r-1")
        assert dec.disposition == DisposalDisposition.DENY
        assert "hold" in dec.reason

    def test_active_retention_returns_deny(self) -> None:
        eng = _engine_with_record_and_schedule()
        dec = eng.evaluate_disposal("r-1")
        assert dec.disposition == DisposalDisposition.DENY
        assert "retention" in dec.reason

    def test_evidence_without_legal_authority_returns_deny(self) -> None:
        eng = _engine_with_record(kind=RecordKind.EVIDENCE)
        dec = eng.evaluate_disposal("r-1", authority=RecordAuthority.SYSTEM)
        assert dec.disposition == DisposalDisposition.DENY
        assert "evidence" in dec.reason

    def test_evidence_without_operator_authority_returns_deny(self) -> None:
        eng = _engine_with_record(kind=RecordKind.EVIDENCE)
        dec = eng.evaluate_disposal("r-1", authority=RecordAuthority.OPERATOR)
        assert dec.disposition == DisposalDisposition.DENY

    def test_evidence_without_compliance_authority_returns_deny(self) -> None:
        eng = _engine_with_record(kind=RecordKind.EVIDENCE)
        dec = eng.evaluate_disposal("r-1", authority=RecordAuthority.COMPLIANCE)
        assert dec.disposition == DisposalDisposition.DENY

    def test_evidence_without_automated_authority_returns_deny(self) -> None:
        eng = _engine_with_record(kind=RecordKind.EVIDENCE)
        dec = eng.evaluate_disposal("r-1", authority=RecordAuthority.AUTOMATED)
        assert dec.disposition == DisposalDisposition.DENY

    def test_evidence_with_legal_authority_allows(self) -> None:
        eng = _engine_with_record(kind=RecordKind.EVIDENCE)
        dec = eng.evaluate_disposal("r-1", authority=RecordAuthority.LEGAL)
        assert dec.disposition != DisposalDisposition.DENY

    def test_evidence_with_executive_authority_allows(self) -> None:
        eng = _engine_with_record(kind=RecordKind.EVIDENCE)
        dec = eng.evaluate_disposal("r-1", authority=RecordAuthority.EXECUTIVE)
        assert dec.disposition != DisposalDisposition.DENY

    def test_no_schedule_defaults_to_delete(self) -> None:
        eng = _engine_with_record()
        dec = eng.evaluate_disposal("r-1")
        assert dec.disposition == DisposalDisposition.DELETE

    def test_expired_schedule_uses_disposal_disposition(self) -> None:
        eng = _engine_with_record()
        eng.bind_retention_schedule(
            "s-1", "r-1", "t-1",
            disposal_disposition=DisposalDisposition.ARCHIVE,
        )
        sched = eng._schedules["s-1"]
        expired = RetentionSchedule(
            schedule_id=sched.schedule_id,
            record_id=sched.record_id,
            tenant_id=sched.tenant_id,
            retention_days=sched.retention_days,
            status=RetentionStatus.EXPIRED,
            disposal_disposition=DisposalDisposition.ARCHIVE,
            scope_ref_id=sched.scope_ref_id,
            created_at=sched.created_at,
            expires_at=sched.expires_at,
        )
        eng._schedules["s-1"] = expired
        dec = eng.evaluate_disposal("r-1")
        assert dec.disposition == DisposalDisposition.ARCHIVE

    def test_expired_schedule_anonymize(self) -> None:
        eng = _engine_with_record()
        eng.bind_retention_schedule(
            "s-1", "r-1", "t-1",
            disposal_disposition=DisposalDisposition.ANONYMIZE,
        )
        sched = eng._schedules["s-1"]
        expired = RetentionSchedule(
            schedule_id=sched.schedule_id,
            record_id=sched.record_id,
            tenant_id=sched.tenant_id,
            retention_days=sched.retention_days,
            status=RetentionStatus.EXPIRED,
            disposal_disposition=DisposalDisposition.ANONYMIZE,
            scope_ref_id=sched.scope_ref_id,
            created_at=sched.created_at,
            expires_at=sched.expires_at,
        )
        eng._schedules["s-1"] = expired
        dec = eng.evaluate_disposal("r-1")
        assert dec.disposition == DisposalDisposition.ANONYMIZE

    def test_expired_schedule_transfer(self) -> None:
        eng = _engine_with_record()
        eng.bind_retention_schedule(
            "s-1", "r-1", "t-1",
            disposal_disposition=DisposalDisposition.TRANSFER,
        )
        sched = eng._schedules["s-1"]
        expired = RetentionSchedule(
            schedule_id=sched.schedule_id,
            record_id=sched.record_id,
            tenant_id=sched.tenant_id,
            retention_days=sched.retention_days,
            status=RetentionStatus.EXPIRED,
            disposal_disposition=DisposalDisposition.TRANSFER,
            scope_ref_id=sched.scope_ref_id,
            created_at=sched.created_at,
            expires_at=sched.expires_at,
        )
        eng._schedules["s-1"] = expired
        dec = eng.evaluate_disposal("r-1")
        assert dec.disposition == DisposalDisposition.TRANSFER

    def test_decision_returns_disposal_decision(self) -> None:
        eng = _engine_with_record()
        dec = eng.evaluate_disposal("r-1")
        assert isinstance(dec, DisposalDecision)

    def test_decision_has_record_id(self) -> None:
        eng = _engine_with_record()
        dec = eng.evaluate_disposal("r-1")
        assert dec.record_id == "r-1"

    def test_decision_has_tenant_id(self) -> None:
        eng = _engine_with_record()
        dec = eng.evaluate_disposal("r-1")
        assert dec.tenant_id == "t-1"

    def test_decision_has_decided_at(self) -> None:
        eng = _engine_with_record()
        dec = eng.evaluate_disposal("r-1")
        assert dec.decided_at != ""

    def test_decision_has_decision_id(self) -> None:
        eng = _engine_with_record()
        dec = eng.evaluate_disposal("r-1")
        assert dec.decision_id != ""

    def test_hold_overrides_expired_schedule(self) -> None:
        """Legal hold should deny even if schedule is expired."""
        eng = _engine_with_record()
        eng.bind_retention_schedule("s-1", "r-1", "t-1")
        sched = eng._schedules["s-1"]
        expired = RetentionSchedule(
            schedule_id=sched.schedule_id,
            record_id=sched.record_id,
            tenant_id=sched.tenant_id,
            retention_days=sched.retention_days,
            status=RetentionStatus.EXPIRED,
            disposal_disposition=sched.disposal_disposition,
            scope_ref_id=sched.scope_ref_id,
            created_at=sched.created_at,
            expires_at=sched.expires_at,
        )
        eng._schedules["s-1"] = expired
        eng.place_hold("h-1", "r-1", "t-1")
        dec = eng.evaluate_disposal("r-1")
        assert dec.disposition == DisposalDisposition.DENY


class TestDisposeRecord:
    def test_dispose_denied_returns_deny(self) -> None:
        eng = _engine_with_record()
        eng.place_hold("h-1", "r-1", "t-1")
        dec = eng.dispose_record("r-1")
        assert dec.disposition == DisposalDisposition.DENY

    def test_dispose_allowed_returns_disposition(self) -> None:
        eng = _engine_with_record()
        dec = eng.dispose_record("r-1")
        assert dec.disposition == DisposalDisposition.DELETE

    def test_dispose_marks_schedules_disposed(self) -> None:
        eng = _engine_with_record()
        eng.bind_retention_schedule("s-1", "r-1", "t-1")
        sched = eng._schedules["s-1"]
        expired = RetentionSchedule(
            schedule_id=sched.schedule_id,
            record_id=sched.record_id,
            tenant_id=sched.tenant_id,
            retention_days=sched.retention_days,
            status=RetentionStatus.EXPIRED,
            disposal_disposition=sched.disposal_disposition,
            scope_ref_id=sched.scope_ref_id,
            created_at=sched.created_at,
            expires_at=sched.expires_at,
        )
        eng._schedules["s-1"] = expired
        eng.dispose_record("r-1")
        scheds = eng.schedules_for_record("r-1")
        assert scheds[0].status == RetentionStatus.DISPOSED

    def test_dispose_increments_disposal_count(self) -> None:
        eng = _engine_with_record()
        assert eng.disposal_count == 0
        eng.dispose_record("r-1")
        assert eng.disposal_count == 1

    def test_dispose_denied_does_not_increment_disposal_count(self) -> None:
        eng = _engine_with_record()
        eng.place_hold("h-1", "r-1", "t-1")
        eng.dispose_record("r-1")
        assert eng.disposal_count == 0

    def test_dispose_unknown_record_raises(self) -> None:
        eng = _make_engine()
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown record_id"):
            eng.dispose_record("nope")


# ===================================================================
# 8. Preservation decisions
# ===================================================================


class TestPreservationDecision:
    def test_returns_preservation_decision(self) -> None:
        eng = _engine_with_record()
        dec = eng.preservation_decision("r-1")
        assert isinstance(dec, PreservationDecision)

    def test_default_preserve_true(self) -> None:
        eng = _engine_with_record()
        dec = eng.preservation_decision("r-1")
        assert dec.preserve is True

    def test_preserve_false(self) -> None:
        eng = _engine_with_record()
        dec = eng.preservation_decision("r-1", preserve=False)
        assert dec.preserve is False

    def test_sets_record_id(self) -> None:
        eng = _engine_with_record()
        dec = eng.preservation_decision("r-1")
        assert dec.record_id == "r-1"

    def test_sets_reason(self) -> None:
        eng = _engine_with_record()
        dec = eng.preservation_decision("r-1", reason="litigation hold")
        assert dec.reason == "litigation hold"

    def test_sets_authority(self) -> None:
        eng = _engine_with_record()
        dec = eng.preservation_decision("r-1", authority=RecordAuthority.LEGAL)
        assert dec.authority == RecordAuthority.LEGAL

    def test_sets_decided_at(self) -> None:
        eng = _engine_with_record()
        dec = eng.preservation_decision("r-1")
        assert dec.decided_at != ""

    def test_sets_decision_id(self) -> None:
        eng = _engine_with_record()
        dec = eng.preservation_decision("r-1")
        assert dec.decision_id != ""

    def test_unknown_record_raises(self) -> None:
        eng = _make_engine()
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown record_id"):
            eng.preservation_decision("nope")

    def test_decision_is_frozen(self) -> None:
        eng = _engine_with_record()
        dec = eng.preservation_decision("r-1")
        with pytest.raises(AttributeError):
            dec.preserve = False  # type: ignore[misc]


# ===================================================================
# 9. Reviews
# ===================================================================


class TestSubmitReview:
    def test_returns_disposition_review(self) -> None:
        eng = _engine_with_record()
        rev = eng.submit_review("rev-1", "r-1", "reviewer-1")
        assert isinstance(rev, DispositionReview)

    def test_sets_fields(self) -> None:
        eng = _engine_with_record()
        rev = eng.submit_review(
            "rev-1", "r-1", "reviewer-1",
            decision=DisposalDisposition.ARCHIVE,
            reason="retain for audit",
        )
        assert rev.review_id == "rev-1"
        assert rev.record_id == "r-1"
        assert rev.reviewer_id == "reviewer-1"
        assert rev.decision == DisposalDisposition.ARCHIVE
        assert rev.reason == "retain for audit"

    def test_default_decision_deny(self) -> None:
        eng = _engine_with_record()
        rev = eng.submit_review("rev-1", "r-1", "reviewer-1")
        assert rev.decision == DisposalDisposition.DENY

    def test_reviewed_at_populated(self) -> None:
        eng = _engine_with_record()
        rev = eng.submit_review("rev-1", "r-1", "reviewer-1")
        assert rev.reviewed_at != ""

    def test_increments_review_count(self) -> None:
        eng = _engine_with_record()
        eng.submit_review("rev-1", "r-1", "reviewer-1")
        assert eng.review_count == 1

    def test_duplicate_review_raises(self) -> None:
        eng = _engine_with_record()
        eng.submit_review("rev-1", "r-1", "reviewer-1")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate review_id"):
            eng.submit_review("rev-1", "r-1", "reviewer-1")

    def test_unknown_record_raises(self) -> None:
        eng = _make_engine()
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown record_id"):
            eng.submit_review("rev-1", "nope", "reviewer-1")

    def test_review_is_frozen(self) -> None:
        eng = _engine_with_record()
        rev = eng.submit_review("rev-1", "r-1", "reviewer-1")
        with pytest.raises(AttributeError):
            rev.decision = DisposalDisposition.DELETE  # type: ignore[misc]

    @pytest.mark.parametrize("decision", list(DisposalDisposition))
    def test_all_decisions(self, decision: DisposalDisposition) -> None:
        eng = _engine_with_record()
        rev = eng.submit_review(f"rev-{decision.value}", "r-1", "reviewer-1", decision=decision)
        assert rev.decision == decision


# ===================================================================
# 10. Violations
# ===================================================================


class TestDetectRecordViolations:
    def test_no_violations_initially(self) -> None:
        eng = _make_engine()
        result = eng.detect_record_violations()
        assert result == ()

    def test_deny_disposal_creates_violation(self) -> None:
        eng = _engine_with_record()
        eng.place_hold("h-1", "r-1", "t-1")
        eng.evaluate_disposal("r-1")
        viols = eng.detect_record_violations()
        assert len(viols) == 1

    def test_violation_fields(self) -> None:
        eng = _engine_with_record()
        eng.place_hold("h-1", "r-1", "t-1")
        eng.evaluate_disposal("r-1")
        viols = eng.detect_record_violations()
        v = viols[0]
        assert isinstance(v, RecordViolation)
        assert v.record_id == "r-1"
        assert v.tenant_id == "t-1"
        assert v.operation == "disposal_denied"
        assert v.detected_at != ""

    def test_violation_increments_count(self) -> None:
        eng = _engine_with_record()
        eng.place_hold("h-1", "r-1", "t-1")
        eng.evaluate_disposal("r-1")
        eng.detect_record_violations()
        assert eng.violation_count == 1

    def test_idempotent_detection(self) -> None:
        eng = _engine_with_record()
        eng.place_hold("h-1", "r-1", "t-1")
        eng.evaluate_disposal("r-1")
        eng.detect_record_violations()
        second = eng.detect_record_violations()
        assert second == ()
        assert eng.violation_count == 1

    def test_multiple_deny_multiple_violations(self) -> None:
        eng = _make_engine()
        eng.register_record("r-1", "t-1", "A")
        eng.register_record("r-2", "t-1", "B")
        eng.place_hold("h-1", "r-1", "t-1")
        eng.place_hold("h-2", "r-2", "t-1")
        eng.evaluate_disposal("r-1")
        eng.evaluate_disposal("r-2")
        viols = eng.detect_record_violations()
        assert len(viols) == 2

    def test_allowed_disposal_no_violation(self) -> None:
        eng = _engine_with_record()
        eng.evaluate_disposal("r-1")
        viols = eng.detect_record_violations()
        assert viols == ()

    def test_violation_is_frozen(self) -> None:
        eng = _engine_with_record()
        eng.place_hold("h-1", "r-1", "t-1")
        eng.evaluate_disposal("r-1")
        viols = eng.detect_record_violations()
        with pytest.raises(AttributeError):
            viols[0].operation = "changed"  # type: ignore[misc]


class TestViolationsForTenant:
    def test_returns_empty_for_unknown_tenant(self) -> None:
        eng = _make_engine()
        assert eng.violations_for_tenant("t-99") == ()

    def test_filters_by_tenant(self) -> None:
        eng = _make_engine()
        eng.register_record("r-1", "t-1", "A")
        eng.register_record("r-2", "t-2", "B")
        eng.place_hold("h-1", "r-1", "t-1")
        eng.place_hold("h-2", "r-2", "t-2")
        eng.evaluate_disposal("r-1")
        eng.evaluate_disposal("r-2")
        eng.detect_record_violations()
        t1_viols = eng.violations_for_tenant("t-1")
        t2_viols = eng.violations_for_tenant("t-2")
        assert len(t1_viols) == 1
        assert len(t2_viols) == 1
        assert t1_viols[0].tenant_id == "t-1"
        assert t2_viols[0].tenant_id == "t-2"

    def test_returns_tuple(self) -> None:
        eng = _make_engine()
        assert isinstance(eng.violations_for_tenant("t-1"), tuple)


# ===================================================================
# 11. Snapshots & state
# ===================================================================


class TestRecordsSnapshot:
    def test_returns_snapshot(self) -> None:
        eng = _make_engine()
        snap = eng.records_snapshot("snap-1")
        assert isinstance(snap, RecordSnapshot)

    def test_snapshot_captures_all_counters_empty(self) -> None:
        eng = _make_engine()
        snap = eng.records_snapshot("snap-1")
        assert snap.total_records == 0
        assert snap.total_schedules == 0
        assert snap.total_holds == 0
        assert snap.active_holds == 0
        assert snap.total_links == 0
        assert snap.total_disposals == 0
        assert snap.total_violations == 0

    def test_snapshot_captures_counters_after_operations(self) -> None:
        eng = _make_engine()
        eng.register_record("r-1", "t-1", "A")
        eng.register_record("r-2", "t-1", "B")
        eng.bind_retention_schedule("s-1", "r-1", "t-1")
        eng.place_hold("h-1", "r-1", "t-1")
        eng.add_link("l-1", "r-1", "doc", "d-1")
        snap = eng.records_snapshot("snap-1")
        assert snap.total_records == 2
        assert snap.total_schedules == 1
        assert snap.total_holds == 1
        assert snap.active_holds == 1
        assert snap.total_links == 1

    def test_snapshot_sets_id(self) -> None:
        eng = _make_engine()
        snap = eng.records_snapshot("snap-1")
        assert snap.snapshot_id == "snap-1"

    def test_snapshot_sets_scope_ref_id(self) -> None:
        eng = _make_engine()
        snap = eng.records_snapshot("snap-1", scope_ref_id="scope-42")
        assert snap.scope_ref_id == "scope-42"

    def test_snapshot_captured_at(self) -> None:
        eng = _make_engine()
        snap = eng.records_snapshot("snap-1")
        assert snap.captured_at != ""

    def test_duplicate_snapshot_raises(self) -> None:
        eng = _make_engine()
        eng.records_snapshot("snap-1")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate snapshot_id"):
            eng.records_snapshot("snap-1")

    def test_snapshot_is_frozen(self) -> None:
        eng = _make_engine()
        snap = eng.records_snapshot("snap-1")
        with pytest.raises(AttributeError):
            snap.total_records = 99  # type: ignore[misc]


class TestStateHash:
    def test_returns_string(self) -> None:
        eng = _make_engine()
        h = eng.state_hash()
        assert isinstance(h, str)
        assert len(h) == 64

    def test_deterministic_for_same_state(self) -> None:
        eng = _make_engine()
        h1 = eng.state_hash()
        h2 = eng.state_hash()
        assert h1 == h2

    def test_changes_after_register(self) -> None:
        eng = _make_engine()
        h1 = eng.state_hash()
        eng.register_record("r-1", "t-1", "A")
        h2 = eng.state_hash()
        assert h1 != h2

    def test_changes_after_schedule(self) -> None:
        eng = _engine_with_record()
        h1 = eng.state_hash()
        eng.bind_retention_schedule("s-1", "r-1", "t-1")
        h2 = eng.state_hash()
        assert h1 != h2

    def test_changes_after_hold(self) -> None:
        eng = _engine_with_record()
        h1 = eng.state_hash()
        eng.place_hold("h-1", "r-1", "t-1")
        h2 = eng.state_hash()
        assert h1 != h2

    def test_changes_after_link(self) -> None:
        eng = _engine_with_record()
        h1 = eng.state_hash()
        eng.add_link("l-1", "r-1", "doc", "d-1")
        h2 = eng.state_hash()
        assert h1 != h2

    def test_changes_after_disposal(self) -> None:
        eng = _engine_with_record()
        h1 = eng.state_hash()
        eng.dispose_record("r-1")
        h2 = eng.state_hash()
        assert h1 != h2

    def test_changes_after_violation(self) -> None:
        eng = _engine_with_record()
        eng.place_hold("h-1", "r-1", "t-1")
        eng.evaluate_disposal("r-1")
        h1 = eng.state_hash()
        eng.detect_record_violations()
        h2 = eng.state_hash()
        assert h1 != h2


# ===================================================================
# 12. Count properties after operations
# ===================================================================


class TestCountProperties:
    def test_record_count_increments(self) -> None:
        eng = _make_engine()
        for i in range(5):
            eng.register_record(f"r-{i}", "t-1", f"Title {i}")
        assert eng.record_count == 5

    def test_schedule_count_increments(self) -> None:
        eng = _engine_with_record()
        for i in range(3):
            eng.bind_retention_schedule(f"s-{i}", "r-1", "t-1")
        assert eng.schedule_count == 3

    def test_hold_count_includes_released(self) -> None:
        eng = _engine_with_record()
        eng.place_hold("h-1", "r-1", "t-1")
        eng.place_hold("h-2", "r-1", "t-1")
        eng.release_hold("h-1")
        assert eng.hold_count == 2
        assert eng.active_hold_count == 1

    def test_link_count_increments(self) -> None:
        eng = _engine_with_record()
        for i in range(4):
            eng.add_link(f"l-{i}", "r-1", "doc", f"d-{i}")
        assert eng.link_count == 4

    def test_disposal_count_only_non_deny(self) -> None:
        eng = _make_engine()
        eng.register_record("r-1", "t-1", "A")
        eng.register_record("r-2", "t-1", "B")
        eng.place_hold("h-1", "r-1", "t-1")
        eng.dispose_record("r-1")  # denied
        eng.dispose_record("r-2")  # allowed
        assert eng.disposal_count == 1

    def test_violation_count_after_detection(self) -> None:
        eng = _make_engine()
        eng.register_record("r-1", "t-1", "A")
        eng.register_record("r-2", "t-1", "B")
        eng.register_record("r-3", "t-1", "C")
        eng.place_hold("h-1", "r-1", "t-1")
        eng.place_hold("h-2", "r-2", "t-1")
        eng.evaluate_disposal("r-1")
        eng.evaluate_disposal("r-2")
        eng.detect_record_violations()
        assert eng.violation_count == 2


# ===================================================================
# 13. Golden scenarios
# ===================================================================


class TestGoldenScenario1CampaignRecordLifecycle:
    """Campaign record -> retention schedule -> hold -> attempted disposal denied
    -> release hold -> disposal succeeds."""

    def test_full_lifecycle(self) -> None:
        eng = _make_engine()

        # 1. Register campaign record
        rec = eng.register_record("camp-1", "t-adv", "Q4 Campaign", kind=RecordKind.OPERATIONAL)
        assert rec.kind == RecordKind.OPERATIONAL
        assert eng.record_count == 1

        # 2. Bind retention schedule
        sched = eng.bind_retention_schedule(
            "rs-1", "camp-1", "t-adv",
            retention_days=180,
            disposal_disposition=DisposalDisposition.ARCHIVE,
        )
        assert sched.status == RetentionStatus.ACTIVE
        assert eng.schedule_count == 1

        # 3. Place legal hold
        hold = eng.place_hold("lh-1", "camp-1", "t-adv", reason="FTC inquiry")
        assert hold.status == HoldStatus.ACTIVE
        assert eng.active_hold_count == 1

        # Verify schedule changed to HELD
        scheds = eng.schedules_for_record("camp-1")
        assert scheds[0].status == RetentionStatus.HELD

        # 4. Attempt disposal — should be denied
        dec = eng.dispose_record("camp-1")
        assert dec.disposition == DisposalDisposition.DENY

        # 5. Release hold
        released = eng.release_hold("lh-1")
        assert released.status == HoldStatus.RELEASED
        assert eng.active_hold_count == 0

        # Schedule should be restored to ACTIVE
        scheds = eng.schedules_for_record("camp-1")
        assert scheds[0].status == RetentionStatus.ACTIVE

        # 6. Expire the schedule manually, then dispose
        sched = eng._schedules["rs-1"]
        eng._schedules["rs-1"] = RetentionSchedule(
            schedule_id=sched.schedule_id, record_id=sched.record_id,
            tenant_id=sched.tenant_id, retention_days=sched.retention_days,
            status=RetentionStatus.EXPIRED, disposal_disposition=sched.disposal_disposition,
            scope_ref_id=sched.scope_ref_id, created_at=sched.created_at,
            expires_at=sched.expires_at,
        )

        dec2 = eng.dispose_record("camp-1")
        assert dec2.disposition == DisposalDisposition.ARCHIVE

        # Schedule should now be DISPOSED
        scheds = eng.schedules_for_record("camp-1")
        assert scheds[0].status == RetentionStatus.DISPOSED


class TestGoldenScenario2EvidenceRecordLineage:
    """Evidence record lineage: register + 3 links + preservation decision."""

    def test_evidence_lineage(self) -> None:
        eng = _make_engine()

        # Register evidence record
        rec = eng.register_record(
            "ev-1", "t-legal", "Deposition Transcript",
            kind=RecordKind.EVIDENCE,
            authority=RecordAuthority.LEGAL,
            evidence_grade=EvidenceGrade.PRIMARY,
        )
        assert rec.kind == RecordKind.EVIDENCE

        # Add 3 links
        eng.add_link("l-1", "ev-1", "audio", "audio-001", "source")
        eng.add_link("l-2", "ev-1", "video", "video-001", "source")
        eng.add_link("l-3", "ev-1", "transcript", "txt-001", "derived_from")
        assert eng.link_count == 3

        links = eng.links_for_record("ev-1")
        assert len(links) == 3
        relationships = {lnk.relationship for lnk in links}
        assert "source" in relationships
        assert "derived_from" in relationships

        # Preservation decision
        pres = eng.preservation_decision("ev-1", reason="litigation", authority=RecordAuthority.LEGAL)
        assert pres.preserve is True
        assert pres.authority == RecordAuthority.LEGAL

        # Evidence record should require legal/executive authority for disposal
        dec = eng.evaluate_disposal("ev-1", authority=RecordAuthority.SYSTEM)
        assert dec.disposition == DisposalDisposition.DENY

        dec2 = eng.evaluate_disposal("ev-1", authority=RecordAuthority.LEGAL)
        assert dec2.disposition != DisposalDisposition.DENY


class TestGoldenScenario3MultiTenantIsolation:
    """Multi-tenant isolation: records from different tenants don't cross."""

    def test_tenant_isolation(self) -> None:
        eng = _make_engine()

        # Register records for two tenants
        eng.register_record("r-t1-a", "tenant-alpha", "Alpha Record A")
        eng.register_record("r-t1-b", "tenant-alpha", "Alpha Record B")
        eng.register_record("r-t2-a", "tenant-beta", "Beta Record A")
        eng.register_record("r-t2-b", "tenant-beta", "Beta Record B")
        eng.register_record("r-t2-c", "tenant-beta", "Beta Record C")

        # Tenant filtering
        alpha_recs = eng.records_for_tenant("tenant-alpha")
        beta_recs = eng.records_for_tenant("tenant-beta")
        assert len(alpha_recs) == 2
        assert len(beta_recs) == 3
        assert all(r.tenant_id == "tenant-alpha" for r in alpha_recs)
        assert all(r.tenant_id == "tenant-beta" for r in beta_recs)

        # Unknown tenant returns nothing
        assert eng.records_for_tenant("tenant-gamma") == ()

        # Holds on one tenant don't affect other tenant's records
        eng.bind_retention_schedule("s-a1", "r-t1-a", "tenant-alpha")
        eng.bind_retention_schedule("s-b1", "r-t2-a", "tenant-beta")
        eng.place_hold("h-alpha", "r-t1-a", "tenant-alpha")
        assert eng.is_under_hold("r-t1-a") is True
        assert eng.is_under_hold("r-t2-a") is False

        # Schedule for alpha record should be HELD, beta should remain ACTIVE
        alpha_scheds = eng.schedules_for_record("r-t1-a")
        beta_scheds = eng.schedules_for_record("r-t2-a")
        assert alpha_scheds[0].status == RetentionStatus.HELD
        assert beta_scheds[0].status == RetentionStatus.ACTIVE

        # Violations per tenant
        eng.evaluate_disposal("r-t1-a")
        eng.detect_record_violations()
        alpha_viols = eng.violations_for_tenant("tenant-alpha")
        beta_viols = eng.violations_for_tenant("tenant-beta")
        assert len(alpha_viols) == 1
        assert len(beta_viols) == 0


class TestGoldenScenario4HoldThenReleaseLifecycle:
    """Hold changes schedules to HELD, release restores to ACTIVE."""

    def test_hold_release_lifecycle(self) -> None:
        eng = _make_engine()
        eng.register_record("r-1", "t-1", "Record")
        eng.bind_retention_schedule("s-1", "r-1", "t-1", retention_days=365)
        eng.bind_retention_schedule("s-2", "r-1", "t-1", retention_days=730)

        # Both schedules ACTIVE
        scheds = eng.schedules_for_record("r-1")
        assert all(s.status == RetentionStatus.ACTIVE for s in scheds)

        # Place hold -> HELD
        eng.place_hold("h-1", "r-1", "t-1", reason="investigation")
        scheds = eng.schedules_for_record("r-1")
        assert all(s.status == RetentionStatus.HELD for s in scheds)

        # Place second hold
        eng.place_hold("h-2", "r-1", "t-1", reason="second investigation")
        assert eng.active_hold_count == 2

        # Release first hold — schedules should stay HELD
        eng.release_hold("h-1")
        scheds = eng.schedules_for_record("r-1")
        assert all(s.status == RetentionStatus.HELD for s in scheds)
        assert eng.active_hold_count == 1

        # Release second hold — schedules should restore to ACTIVE
        eng.release_hold("h-2")
        scheds = eng.schedules_for_record("r-1")
        assert all(s.status == RetentionStatus.ACTIVE for s in scheds)
        assert eng.active_hold_count == 0

        # Hold count includes released
        assert eng.hold_count == 2


class TestGoldenScenario5ViolationDetection:
    """Multiple DENY disposals -> detect violations -> verify counts."""

    def test_violation_detection(self) -> None:
        eng = _make_engine()

        # Create several records with holds
        for i in range(5):
            eng.register_record(f"r-{i}", "t-1", f"Record {i}")
            eng.place_hold(f"h-{i}", f"r-{i}", "t-1")

        # Attempt disposal on all — all should be denied
        for i in range(5):
            dec = eng.evaluate_disposal(f"r-{i}")
            assert dec.disposition == DisposalDisposition.DENY

        # Detect violations
        viols = eng.detect_record_violations()
        assert len(viols) == 5
        assert eng.violation_count == 5

        # All violations belong to t-1
        t1_viols = eng.violations_for_tenant("t-1")
        assert len(t1_viols) == 5

        # Second detection is idempotent
        new_viols = eng.detect_record_violations()
        assert new_viols == ()
        assert eng.violation_count == 5

        # Create one more denied disposal
        eng.register_record("r-extra", "t-2", "Extra")
        eng.place_hold("h-extra", "r-extra", "t-2")
        eng.evaluate_disposal("r-extra")
        extra_viols = eng.detect_record_violations()
        assert len(extra_viols) == 1
        assert eng.violation_count == 6

        t2_viols = eng.violations_for_tenant("t-2")
        assert len(t2_viols) == 1


class TestGoldenScenario6FullClosure:
    """Records + schedules + holds + links + disposals + violations + snapshot
    captures everything."""

    def test_full_closure(self) -> None:
        eng = _make_engine()

        # --- Register records ---
        eng.register_record("r-1", "t-1", "Operational Record", kind=RecordKind.OPERATIONAL)
        eng.register_record("r-2", "t-1", "Evidence Record", kind=RecordKind.EVIDENCE)
        eng.register_record("r-3", "t-1", "Compliance Record", kind=RecordKind.COMPLIANCE)
        assert eng.record_count == 3

        # --- Links ---
        eng.add_link("l-1", "r-1", "email", "e-1")
        eng.add_link("l-2", "r-2", "deposition", "dep-1")
        eng.add_link("l-3", "r-2", "exhibit", "ex-1")
        assert eng.link_count == 3

        # --- Retention schedules ---
        eng.bind_retention_schedule("s-1", "r-1", "t-1", retention_days=90, disposal_disposition=DisposalDisposition.DELETE)
        eng.bind_retention_schedule("s-2", "r-2", "t-1", retention_days=365, disposal_disposition=DisposalDisposition.ARCHIVE)
        eng.bind_retention_schedule("s-3", "r-3", "t-1", retention_days=180, disposal_disposition=DisposalDisposition.ANONYMIZE)
        assert eng.schedule_count == 3

        # --- Legal holds ---
        eng.place_hold("h-1", "r-1", "t-1", reason="investigation")
        eng.place_hold("h-2", "r-2", "t-1", reason="lawsuit")
        assert eng.hold_count == 2
        assert eng.active_hold_count == 2

        # Schedules for r-1 and r-2 are HELD
        assert eng.schedules_for_record("r-1")[0].status == RetentionStatus.HELD
        assert eng.schedules_for_record("r-2")[0].status == RetentionStatus.HELD
        assert eng.schedules_for_record("r-3")[0].status == RetentionStatus.ACTIVE

        # --- Disposal attempts ---
        dec_r1 = eng.dispose_record("r-1")
        assert dec_r1.disposition == DisposalDisposition.DENY

        dec_r2 = eng.dispose_record("r-2")
        assert dec_r2.disposition == DisposalDisposition.DENY

        dec_r3 = eng.dispose_record("r-3")
        assert dec_r3.disposition == DisposalDisposition.DENY

        assert eng.disposal_count == 0  # all denied

        # --- Detect violations ---
        viols = eng.detect_record_violations()
        assert len(viols) == 3
        assert eng.violation_count == 3

        # --- Release holds ---
        eng.release_hold("h-1")
        eng.release_hold("h-2")
        assert eng.active_hold_count == 0

        # Schedules restored for r-1 and r-2
        assert eng.schedules_for_record("r-1")[0].status == RetentionStatus.ACTIVE
        assert eng.schedules_for_record("r-2")[0].status == RetentionStatus.ACTIVE

        # --- Expire and dispose r-1 ---
        sched = eng._schedules["s-1"]
        eng._schedules["s-1"] = RetentionSchedule(
            schedule_id=sched.schedule_id, record_id=sched.record_id,
            tenant_id=sched.tenant_id, retention_days=sched.retention_days,
            status=RetentionStatus.EXPIRED, disposal_disposition=sched.disposal_disposition,
            scope_ref_id=sched.scope_ref_id, created_at=sched.created_at,
            expires_at=sched.expires_at,
        )
        dec_r1b = eng.dispose_record("r-1")
        assert dec_r1b.disposition == DisposalDisposition.DELETE
        assert eng.disposal_count == 1

        # --- Reviews ---
        eng.submit_review("rev-1", "r-1", "admin-1", decision=DisposalDisposition.DELETE, reason="approved")
        eng.submit_review("rev-2", "r-2", "admin-1", decision=DisposalDisposition.DENY, reason="retain")
        assert eng.review_count == 2

        # --- Preservation decision ---
        eng.preservation_decision("r-2", reason="key evidence", authority=RecordAuthority.LEGAL)

        # --- Snapshot captures everything ---
        snap = eng.records_snapshot("final-snap", scope_ref_id="closure-2025")
        assert snap.total_records == 3
        assert snap.total_schedules == 3
        assert snap.total_holds == 2
        assert snap.active_holds == 0
        assert snap.total_links == 3
        assert snap.total_disposals == 1
        assert snap.total_violations == 3
        assert snap.scope_ref_id == "closure-2025"

        # State hash should be deterministic
        h1 = eng.state_hash()
        h2 = eng.state_hash()
        assert h1 == h2


# ===================================================================
# 14. Event emission
# ===================================================================


class TestEventEmission:
    def test_register_emits_event(self) -> None:
        es = EventSpineEngine()
        eng = RecordsRuntimeEngine(es)
        eng.register_record("r-1", "t-1", "Title")
        assert es.event_count >= 1

    def test_add_link_emits_event(self) -> None:
        es = EventSpineEngine()
        eng = RecordsRuntimeEngine(es)
        eng.register_record("r-1", "t-1", "Title")
        before = es.event_count
        eng.add_link("l-1", "r-1", "doc", "d-1")
        assert es.event_count > before

    def test_bind_schedule_emits_event(self) -> None:
        es = EventSpineEngine()
        eng = RecordsRuntimeEngine(es)
        eng.register_record("r-1", "t-1", "Title")
        before = es.event_count
        eng.bind_retention_schedule("s-1", "r-1", "t-1")
        assert es.event_count > before

    def test_place_hold_emits_event(self) -> None:
        es = EventSpineEngine()
        eng = RecordsRuntimeEngine(es)
        eng.register_record("r-1", "t-1", "Title")
        before = es.event_count
        eng.place_hold("h-1", "r-1", "t-1")
        assert es.event_count > before

    def test_release_hold_emits_event(self) -> None:
        es = EventSpineEngine()
        eng = RecordsRuntimeEngine(es)
        eng.register_record("r-1", "t-1", "Title")
        eng.place_hold("h-1", "r-1", "t-1")
        before = es.event_count
        eng.release_hold("h-1")
        assert es.event_count > before

    def test_evaluate_disposal_emits_event(self) -> None:
        es = EventSpineEngine()
        eng = RecordsRuntimeEngine(es)
        eng.register_record("r-1", "t-1", "Title")
        before = es.event_count
        eng.evaluate_disposal("r-1")
        assert es.event_count > before

    def test_dispose_record_emits_event(self) -> None:
        es = EventSpineEngine()
        eng = RecordsRuntimeEngine(es)
        eng.register_record("r-1", "t-1", "Title")
        before = es.event_count
        eng.dispose_record("r-1")
        assert es.event_count > before

    def test_preservation_decision_emits_event(self) -> None:
        es = EventSpineEngine()
        eng = RecordsRuntimeEngine(es)
        eng.register_record("r-1", "t-1", "Title")
        before = es.event_count
        eng.preservation_decision("r-1")
        assert es.event_count > before

    def test_submit_review_emits_event(self) -> None:
        es = EventSpineEngine()
        eng = RecordsRuntimeEngine(es)
        eng.register_record("r-1", "t-1", "Title")
        before = es.event_count
        eng.submit_review("rev-1", "r-1", "reviewer-1")
        assert es.event_count > before

    def test_detect_violations_emits_event_when_found(self) -> None:
        es = EventSpineEngine()
        eng = RecordsRuntimeEngine(es)
        eng.register_record("r-1", "t-1", "Title")
        eng.place_hold("h-1", "r-1", "t-1")
        eng.evaluate_disposal("r-1")
        before = es.event_count
        eng.detect_record_violations()
        assert es.event_count > before

    def test_snapshot_emits_event(self) -> None:
        es = EventSpineEngine()
        eng = RecordsRuntimeEngine(es)
        before = es.event_count
        eng.records_snapshot("snap-1")
        assert es.event_count > before


# ===================================================================
# 15. Immutability
# ===================================================================


class TestImmutability:
    def test_record_descriptor_frozen(self) -> None:
        eng = _engine_with_record()
        rec = eng.get_record("r-1")
        with pytest.raises(AttributeError):
            rec.title = "changed"  # type: ignore[misc]

    def test_retention_schedule_frozen(self) -> None:
        eng = _engine_with_record()
        sched = eng.bind_retention_schedule("s-1", "r-1", "t-1")
        with pytest.raises(AttributeError):
            sched.retention_days = 999  # type: ignore[misc]

    def test_legal_hold_frozen(self) -> None:
        eng = _engine_with_record()
        hold = eng.place_hold("h-1", "r-1", "t-1")
        with pytest.raises(AttributeError):
            hold.reason = "changed"  # type: ignore[misc]

    def test_disposal_decision_frozen(self) -> None:
        eng = _engine_with_record()
        dec = eng.evaluate_disposal("r-1")
        with pytest.raises(AttributeError):
            dec.disposition = DisposalDisposition.ARCHIVE  # type: ignore[misc]

    def test_preservation_decision_frozen(self) -> None:
        eng = _engine_with_record()
        dec = eng.preservation_decision("r-1")
        with pytest.raises(AttributeError):
            dec.preserve = False  # type: ignore[misc]

    def test_disposition_review_frozen(self) -> None:
        eng = _engine_with_record()
        rev = eng.submit_review("rev-1", "r-1", "reviewer-1")
        with pytest.raises(AttributeError):
            rev.reason = "changed"  # type: ignore[misc]

    def test_record_violation_frozen(self) -> None:
        eng = _engine_with_record()
        eng.place_hold("h-1", "r-1", "t-1")
        eng.evaluate_disposal("r-1")
        viols = eng.detect_record_violations()
        with pytest.raises(AttributeError):
            viols[0].reason = "changed"  # type: ignore[misc]

    def test_snapshot_frozen(self) -> None:
        eng = _make_engine()
        snap = eng.records_snapshot("snap-1")
        with pytest.raises(AttributeError):
            snap.total_records = 99  # type: ignore[misc]


# ===================================================================
# 16. to_dict preserves enum objects
# ===================================================================


class TestToDict:
    def test_record_to_dict_preserves_kind_enum(self) -> None:
        eng = _engine_with_record(kind=RecordKind.EVIDENCE)
        rec = eng.get_record("r-1")
        d = rec.to_dict()
        assert d["kind"] is RecordKind.EVIDENCE

    def test_record_to_dict_preserves_authority_enum(self) -> None:
        eng = _engine_with_record(authority=RecordAuthority.LEGAL)
        rec = eng.get_record("r-1")
        d = rec.to_dict()
        assert d["authority"] is RecordAuthority.LEGAL

    def test_record_to_dict_preserves_evidence_grade_enum(self) -> None:
        eng = _engine_with_record(evidence_grade=EvidenceGrade.DERIVED)
        rec = eng.get_record("r-1")
        d = rec.to_dict()
        assert d["evidence_grade"] is EvidenceGrade.DERIVED

    def test_schedule_to_dict_preserves_status_enum(self) -> None:
        eng = _engine_with_record()
        sched = eng.bind_retention_schedule("s-1", "r-1", "t-1")
        d = sched.to_dict()
        assert d["status"] is RetentionStatus.ACTIVE

    def test_hold_to_dict_preserves_status_enum(self) -> None:
        eng = _engine_with_record()
        hold = eng.place_hold("h-1", "r-1", "t-1")
        d = hold.to_dict()
        assert d["status"] is HoldStatus.ACTIVE

    def test_disposal_to_dict_preserves_disposition_enum(self) -> None:
        eng = _engine_with_record()
        dec = eng.evaluate_disposal("r-1")
        d = dec.to_dict()
        assert d["disposition"] is DisposalDisposition.DELETE

    def test_review_to_dict_preserves_decision_enum(self) -> None:
        eng = _engine_with_record()
        rev = eng.submit_review("rev-1", "r-1", "reviewer-1", decision=DisposalDisposition.ARCHIVE)
        d = rev.to_dict()
        assert d["decision"] is DisposalDisposition.ARCHIVE


class TestBoundedContractWitnesses:
    def test_invariant_messages_do_not_reflect_ids(self) -> None:
        eng = _engine_with_record(record_id="r-secret")

        with pytest.raises(RuntimeCoreInvariantError) as duplicate_exc:
            eng.register_record("r-secret", "t-1", "Again")
        duplicate_message = str(duplicate_exc.value)
        assert duplicate_message == "Duplicate record_id"
        assert "r-secret" not in duplicate_message
        assert "record_id" in duplicate_message

        with pytest.raises(RuntimeCoreInvariantError) as unknown_hold_exc:
            eng.release_hold("hold-secret")
        unknown_hold_message = str(unknown_hold_exc.value)
        assert unknown_hold_message == "Unknown hold_id"
        assert "hold-secret" not in unknown_hold_message
        assert "hold_id" in unknown_hold_message

    def test_release_hold_message_does_not_reflect_status(self) -> None:
        eng = _engine_with_record(record_id="r-secret")
        eng.place_hold("hold-secret", "r-secret", "t-1")
        eng.release_hold("hold-secret")

        with pytest.raises(RuntimeCoreInvariantError) as released_exc:
            eng.release_hold("hold-secret")
        released_message = str(released_exc.value)
        assert released_message == "Cannot release hold in current status"
        assert "released" not in released_message
        assert "current status" in released_message

    def test_snapshot_message_does_not_reflect_snapshot_id(self) -> None:
        eng = _engine_with_record(record_id="r-secret")
        eng.records_snapshot("snap-secret")

        with pytest.raises(RuntimeCoreInvariantError) as snapshot_exc:
            eng.records_snapshot("snap-secret")
        snapshot_message = str(snapshot_exc.value)
        assert snapshot_message == "Duplicate snapshot_id"
        assert "snap-secret" not in snapshot_message
        assert "snapshot_id" in snapshot_message
