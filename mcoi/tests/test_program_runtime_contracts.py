"""Tests for program / initiative / OKR runtime contracts."""

from __future__ import annotations

import dataclasses
from types import MappingProxyType

import pytest

from mcoi_runtime.contracts.program_runtime import (
    AttainmentLevel,
    AttainmentSnapshot,
    DependencyKind,
    InitiativeDependency,
    InitiativeRecord,
    InitiativeStatus,
    MilestoneRecord,
    MilestoneStatus,
    ObjectiveBinding,
    ObjectiveRecord,
    ObjectiveType,
    ProgramClosureReport,
    ProgramDecision,
    ProgramHealth,
    ProgramRecord,
    ProgramStatus,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

TS = "2025-06-01T12:00:00+00:00"
TS2 = "2025-06-15T09:00:00+00:00"


def _objective(**overrides) -> ObjectiveRecord:
    defaults = dict(
        objective_id="obj-001",
        title="Revenue target",
        created_at=TS,
    )
    defaults.update(overrides)
    return ObjectiveRecord(**defaults)


def _initiative(**overrides) -> InitiativeRecord:
    defaults = dict(
        initiative_id="init-001",
        title="Launch campaign",
        created_at=TS,
    )
    defaults.update(overrides)
    return InitiativeRecord(**defaults)


def _program(**overrides) -> ProgramRecord:
    defaults = dict(
        program_id="prog-001",
        title="Q3 Growth",
        created_at=TS,
    )
    defaults.update(overrides)
    return ProgramRecord(**defaults)


def _milestone(**overrides) -> MilestoneRecord:
    defaults = dict(
        milestone_id="ms-001",
        initiative_id="init-001",
        title="MVP delivery",
        created_at=TS,
    )
    defaults.update(overrides)
    return MilestoneRecord(**defaults)


def _binding(**overrides) -> ObjectiveBinding:
    defaults = dict(
        binding_id="bind-001",
        bound_at=TS,
    )
    defaults.update(overrides)
    return ObjectiveBinding(**defaults)


def _dependency(**overrides) -> InitiativeDependency:
    defaults = dict(
        dependency_id="dep-001",
        from_initiative_id="init-001",
        to_initiative_id="init-002",
        created_at=TS,
    )
    defaults.update(overrides)
    return InitiativeDependency(**defaults)


def _snapshot(**overrides) -> AttainmentSnapshot:
    defaults = dict(
        snapshot_id="snap-001",
        objective_id="obj-001",
        captured_at=TS,
    )
    defaults.update(overrides)
    return AttainmentSnapshot(**defaults)


def _health(**overrides) -> ProgramHealth:
    defaults = dict(
        health_id="hlth-001",
        program_id="prog-001",
        assessed_at=TS,
    )
    defaults.update(overrides)
    return ProgramHealth(**defaults)


def _decision(**overrides) -> ProgramDecision:
    defaults = dict(
        decision_id="dec-001",
        title="Pause initiative",
        confidence=0.8,
        decided_at=TS,
    )
    defaults.update(overrides)
    return ProgramDecision(**defaults)


def _closure(**overrides) -> ProgramClosureReport:
    defaults = dict(
        report_id="rpt-001",
        program_id="prog-001",
        closed_at=TS,
    )
    defaults.update(overrides)
    return ProgramClosureReport(**defaults)


# ---------------------------------------------------------------------------
# Enum members
# ---------------------------------------------------------------------------


class TestEnumMembers:
    def test_program_status_members(self):
        expected = {"DRAFT", "ACTIVE", "PAUSED", "COMPLETED", "CANCELLED", "FAILED"}
        assert {m.name for m in ProgramStatus} == expected
        assert len(ProgramStatus) == 6

    def test_initiative_status_members(self):
        expected = {"DRAFT", "ACTIVE", "BLOCKED", "PAUSED", "COMPLETED", "CANCELLED", "FAILED"}
        assert {m.name for m in InitiativeStatus} == expected
        assert len(InitiativeStatus) == 7

    def test_milestone_status_members(self):
        expected = {"PENDING", "IN_PROGRESS", "ACHIEVED", "MISSED", "DEFERRED"}
        assert {m.name for m in MilestoneStatus} == expected
        assert len(MilestoneStatus) == 5

    def test_objective_type_members(self):
        expected = {"STRATEGIC", "TACTICAL", "OPERATIONAL", "KEY_RESULT"}
        assert {m.name for m in ObjectiveType} == expected
        assert len(ObjectiveType) == 4

    def test_attainment_level_members(self):
        expected = {"EXCEEDED", "ON_TRACK", "AT_RISK", "BEHIND", "FAILED", "NOT_STARTED"}
        assert {m.name for m in AttainmentLevel} == expected
        assert len(AttainmentLevel) == 6

    def test_dependency_kind_members(self):
        expected = {"BLOCKS", "REQUIRES", "ENHANCES", "CONFLICTS"}
        assert {m.name for m in DependencyKind} == expected
        assert len(DependencyKind) == 4


# ---------------------------------------------------------------------------
# Construction tests (one class per dataclass)
# ---------------------------------------------------------------------------


class TestObjectiveRecordConstruction:
    def test_minimal(self):
        o = _objective()
        assert o.objective_id == "obj-001"
        assert o.title == "Revenue target"
        assert o.description == ""
        assert o.objective_type is ObjectiveType.STRATEGIC
        assert o.attainment is AttainmentLevel.NOT_STARTED
        assert o.weight == 1.0
        assert o.created_at == TS

    def test_full(self):
        o = _objective(
            description="Revenue growth objective",
            objective_type=ObjectiveType.TACTICAL,
            parent_objective_id="obj-000",
            target_value=100.0,
            current_value=42.0,
            unit="USD",
            attainment=AttainmentLevel.ON_TRACK,
            weight=0.75,
            owner="alice",
            updated_at=TS2,
            metadata={"source": "cfo"},
        )
        assert o.objective_type is ObjectiveType.TACTICAL
        assert o.parent_objective_id == "obj-000"
        assert o.target_value == 100.0
        assert o.current_value == 42.0
        assert o.unit == "USD"
        assert o.attainment is AttainmentLevel.ON_TRACK
        assert o.weight == 0.75
        assert o.owner == "alice"
        assert o.updated_at == TS2
        assert o.metadata["source"] == "cfo"


class TestInitiativeRecordConstruction:
    def test_minimal(self):
        i = _initiative()
        assert i.initiative_id == "init-001"
        assert i.title == "Launch campaign"
        assert i.status is InitiativeStatus.DRAFT
        assert i.priority == 0
        assert i.progress_pct == 0.0
        assert i.campaign_ids == ()
        assert i.portfolio_ids == ()
        assert i.milestone_ids == ()

    def test_full(self):
        i = _initiative(
            program_id="prog-001",
            objective_id="obj-001",
            description="Full launch",
            status=InitiativeStatus.ACTIVE,
            priority=3,
            progress_pct=55.5,
            campaign_ids=("c-1", "c-2"),
            portfolio_ids=("p-1",),
            milestone_ids=("ms-1", "ms-2"),
            owner="bob",
            updated_at=TS2,
            metadata={"region": "EMEA"},
        )
        assert i.status is InitiativeStatus.ACTIVE
        assert i.campaign_ids == ("c-1", "c-2")
        assert i.metadata["region"] == "EMEA"


class TestProgramRecordConstruction:
    def test_minimal(self):
        p = _program()
        assert p.program_id == "prog-001"
        assert p.title == "Q3 Growth"
        assert p.status is ProgramStatus.DRAFT
        assert p.objective_ids == ()
        assert p.initiative_ids == ()

    def test_full(self):
        p = _program(
            description="Growth program",
            status=ProgramStatus.ACTIVE,
            objective_ids=("obj-1",),
            initiative_ids=("init-1", "init-2"),
            owner="carol",
            updated_at=TS2,
            metadata={"fiscal_year": 2025},
        )
        assert p.status is ProgramStatus.ACTIVE
        assert p.objective_ids == ("obj-1",)
        assert p.initiative_ids == ("init-1", "init-2")


class TestMilestoneRecordConstruction:
    def test_minimal(self):
        m = _milestone()
        assert m.milestone_id == "ms-001"
        assert m.initiative_id == "init-001"
        assert m.title == "MVP delivery"
        assert m.status is MilestoneStatus.PENDING
        assert m.progress_pct == 0.0

    def test_full(self):
        m = _milestone(
            description="First deliverable",
            status=MilestoneStatus.ACHIEVED,
            target_date=TS,
            completed_date=TS2,
            progress_pct=100.0,
            metadata={"reviewer": "dan"},
        )
        assert m.status is MilestoneStatus.ACHIEVED
        assert m.completed_date == TS2


class TestObjectiveBindingConstruction:
    def test_minimal(self):
        b = _binding()
        assert b.binding_id == "bind-001"
        assert b.objective_id == ""
        assert b.initiative_id == ""
        assert b.campaign_ref_id == ""
        assert b.portfolio_ref_id == ""
        assert b.weight == 1.0
        assert b.bound_at == TS

    def test_full(self):
        b = _binding(
            objective_id="obj-001",
            initiative_id="init-001",
            campaign_ref_id="camp-1",
            portfolio_ref_id="port-1",
            weight=0.5,
        )
        assert b.objective_id == "obj-001"
        assert b.weight == 0.5


class TestInitiativeDependencyConstruction:
    def test_minimal(self):
        d = _dependency()
        assert d.dependency_id == "dep-001"
        assert d.from_initiative_id == "init-001"
        assert d.to_initiative_id == "init-002"
        assert d.kind is DependencyKind.REQUIRES
        assert d.description == ""

    def test_full(self):
        d = _dependency(
            kind=DependencyKind.BLOCKS,
            description="Must complete first",
        )
        assert d.kind is DependencyKind.BLOCKS
        assert d.description == "Must complete first"


class TestAttainmentSnapshotConstruction:
    def test_minimal(self):
        s = _snapshot()
        assert s.snapshot_id == "snap-001"
        assert s.attainment is AttainmentLevel.NOT_STARTED
        assert s.initiative_count == 0
        assert s.completed_initiatives == 0
        assert s.blocked_initiatives == 0

    def test_full(self):
        s = _snapshot(
            attainment=AttainmentLevel.ON_TRACK,
            target_value=100.0,
            current_value=60.0,
            progress_pct=60.0,
            initiative_count=5,
            completed_initiatives=3,
            blocked_initiatives=1,
            metadata={"source": "auto"},
        )
        assert s.initiative_count == 5
        assert s.metadata["source"] == "auto"


class TestProgramHealthConstruction:
    def test_minimal(self):
        h = _health()
        assert h.health_id == "hlth-001"
        assert h.program_id == "prog-001"
        assert h.status is ProgramStatus.ACTIVE
        assert h.total_initiatives == 0
        assert h.overall_progress_pct == 0.0

    def test_full(self):
        h = _health(
            status=ProgramStatus.COMPLETED,
            total_initiatives=10,
            active_initiatives=0,
            blocked_initiatives=0,
            completed_initiatives=10,
            total_milestones=20,
            achieved_milestones=18,
            missed_milestones=2,
            overall_progress_pct=90.0,
        )
        assert h.completed_initiatives == 10
        assert h.missed_milestones == 2


class TestProgramDecisionConstruction:
    def test_minimal(self):
        d = _decision()
        assert d.decision_id == "dec-001"
        assert d.title == "Pause initiative"
        assert d.confidence == 0.8
        assert d.program_id == ""
        assert d.initiative_id == ""

    def test_full(self):
        d = _decision(
            program_id="prog-001",
            initiative_id="init-001",
            rationale="Too many blockers",
            action="pause",
            confidence=0.95,
            metadata={"approver": "eve"},
        )
        assert d.rationale == "Too many blockers"
        assert d.metadata["approver"] == "eve"


class TestProgramClosureReportConstruction:
    def test_minimal(self):
        c = _closure()
        assert c.report_id == "rpt-001"
        assert c.program_id == "prog-001"
        assert c.final_status is ProgramStatus.COMPLETED
        assert c.lessons == ()

    def test_full(self):
        c = _closure(
            final_status=ProgramStatus.FAILED,
            total_initiatives=8,
            completed_initiatives=3,
            failed_initiatives=5,
            total_milestones=16,
            achieved_milestones=6,
            missed_milestones=10,
            overall_attainment_pct=37.5,
            lessons=("lesson 1", "lesson 2"),
            metadata={"post_mortem": True},
        )
        assert c.final_status is ProgramStatus.FAILED
        assert c.lessons == ("lesson 1", "lesson 2")
        assert c.metadata["post_mortem"] is True


# ---------------------------------------------------------------------------
# Frozen immutability
# ---------------------------------------------------------------------------


class TestFrozenImmutability:
    def test_objective_record_frozen(self):
        o = _objective()
        with pytest.raises((dataclasses.FrozenInstanceError, AttributeError)):
            o.title = "changed"  # type: ignore[misc]

    def test_initiative_record_frozen(self):
        i = _initiative()
        with pytest.raises((dataclasses.FrozenInstanceError, AttributeError)):
            i.title = "changed"  # type: ignore[misc]

    def test_program_record_frozen(self):
        p = _program()
        with pytest.raises((dataclasses.FrozenInstanceError, AttributeError)):
            p.title = "changed"  # type: ignore[misc]

    def test_milestone_record_frozen(self):
        m = _milestone()
        with pytest.raises((dataclasses.FrozenInstanceError, AttributeError)):
            m.title = "changed"  # type: ignore[misc]

    def test_objective_binding_frozen(self):
        b = _binding()
        with pytest.raises((dataclasses.FrozenInstanceError, AttributeError)):
            b.weight = 0.0  # type: ignore[misc]

    def test_initiative_dependency_frozen(self):
        d = _dependency()
        with pytest.raises((dataclasses.FrozenInstanceError, AttributeError)):
            d.description = "x"  # type: ignore[misc]

    def test_attainment_snapshot_frozen(self):
        s = _snapshot()
        with pytest.raises((dataclasses.FrozenInstanceError, AttributeError)):
            s.progress_pct = 1.0  # type: ignore[misc]

    def test_program_health_frozen(self):
        h = _health()
        with pytest.raises((dataclasses.FrozenInstanceError, AttributeError)):
            h.overall_progress_pct = 1.0  # type: ignore[misc]

    def test_program_decision_frozen(self):
        d = _decision()
        with pytest.raises((dataclasses.FrozenInstanceError, AttributeError)):
            d.confidence = 0.5  # type: ignore[misc]

    def test_program_closure_report_frozen(self):
        c = _closure()
        with pytest.raises((dataclasses.FrozenInstanceError, AttributeError)):
            c.report_id = "x"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# require_non_empty_text (only * fields)
# ---------------------------------------------------------------------------


class TestRequireNonEmptyText:
    # ObjectiveRecord
    def test_objective_empty_id(self):
        with pytest.raises(ValueError, match="objective_id"):
            _objective(objective_id="")

    def test_objective_whitespace_id(self):
        with pytest.raises(ValueError, match="objective_id"):
            _objective(objective_id="   ")

    def test_objective_empty_title(self):
        with pytest.raises(ValueError, match="title"):
            _objective(title="")

    # InitiativeRecord
    def test_initiative_empty_id(self):
        with pytest.raises(ValueError, match="initiative_id"):
            _initiative(initiative_id="")

    def test_initiative_empty_title(self):
        with pytest.raises(ValueError, match="title"):
            _initiative(title="")

    # ProgramRecord
    def test_program_empty_id(self):
        with pytest.raises(ValueError, match="program_id"):
            _program(program_id="")

    def test_program_empty_title(self):
        with pytest.raises(ValueError, match="title"):
            _program(title="")

    # MilestoneRecord
    def test_milestone_empty_id(self):
        with pytest.raises(ValueError, match="milestone_id"):
            _milestone(milestone_id="")

    def test_milestone_empty_initiative_id(self):
        with pytest.raises(ValueError, match="initiative_id"):
            _milestone(initiative_id="")

    def test_milestone_empty_title(self):
        with pytest.raises(ValueError, match="title"):
            _milestone(title="")

    # ObjectiveBinding
    def test_binding_empty_id(self):
        with pytest.raises(ValueError, match="binding_id"):
            _binding(binding_id="")

    # InitiativeDependency
    def test_dependency_empty_id(self):
        with pytest.raises(ValueError, match="dependency_id"):
            _dependency(dependency_id="")

    def test_dependency_empty_from(self):
        with pytest.raises(ValueError, match="from_initiative_id"):
            _dependency(from_initiative_id="")

    def test_dependency_empty_to(self):
        with pytest.raises(ValueError, match="to_initiative_id"):
            _dependency(to_initiative_id="")

    # AttainmentSnapshot
    def test_snapshot_empty_id(self):
        with pytest.raises(ValueError, match="snapshot_id"):
            _snapshot(snapshot_id="")

    def test_snapshot_empty_objective_id(self):
        with pytest.raises(ValueError, match="objective_id"):
            _snapshot(objective_id="")

    # ProgramHealth
    def test_health_empty_id(self):
        with pytest.raises(ValueError, match="health_id"):
            _health(health_id="")

    def test_health_empty_program_id(self):
        with pytest.raises(ValueError, match="program_id"):
            _health(program_id="")

    # ProgramDecision
    def test_decision_empty_id(self):
        with pytest.raises(ValueError, match="decision_id"):
            _decision(decision_id="")

    def test_decision_empty_title(self):
        with pytest.raises(ValueError, match="title"):
            _decision(title="")

    # ProgramClosureReport
    def test_closure_empty_report_id(self):
        with pytest.raises(ValueError, match="report_id"):
            _closure(report_id="")

    def test_closure_empty_program_id(self):
        with pytest.raises(ValueError, match="program_id"):
            _closure(program_id="")


# ---------------------------------------------------------------------------
# require_unit_float
# ---------------------------------------------------------------------------


class TestRequireUnitFloat:
    def test_confidence_zero(self):
        d = _decision(confidence=0.0)
        assert d.confidence == 0.0

    def test_confidence_one(self):
        d = _decision(confidence=1.0)
        assert d.confidence == 1.0

    def test_confidence_mid(self):
        d = _decision(confidence=0.5)
        assert d.confidence == 0.5

    def test_confidence_negative_rejected(self):
        with pytest.raises(ValueError, match="confidence"):
            _decision(confidence=-0.1)

    def test_confidence_above_one_rejected(self):
        with pytest.raises(ValueError, match="confidence"):
            _decision(confidence=1.01)

    def test_confidence_nan_rejected(self):
        with pytest.raises(ValueError, match="confidence"):
            _decision(confidence=float("nan"))

    def test_confidence_inf_rejected(self):
        with pytest.raises(ValueError, match="confidence"):
            _decision(confidence=float("inf"))

    def test_confidence_bool_rejected(self):
        with pytest.raises(ValueError, match="confidence"):
            _decision(confidence=True)


# ---------------------------------------------------------------------------
# require_non_negative_int
# ---------------------------------------------------------------------------


class TestRequireNonNegativeInt:
    # AttainmentSnapshot
    def test_snapshot_initiative_count_zero(self):
        s = _snapshot(initiative_count=0)
        assert s.initiative_count == 0

    def test_snapshot_initiative_count_positive(self):
        s = _snapshot(initiative_count=5)
        assert s.initiative_count == 5

    def test_snapshot_initiative_count_negative_rejected(self):
        with pytest.raises(ValueError, match="initiative_count"):
            _snapshot(initiative_count=-1)

    def test_snapshot_completed_initiatives_negative_rejected(self):
        with pytest.raises(ValueError, match="completed_initiatives"):
            _snapshot(completed_initiatives=-1)

    def test_snapshot_blocked_initiatives_negative_rejected(self):
        with pytest.raises(ValueError, match="blocked_initiatives"):
            _snapshot(blocked_initiatives=-1)

    # ProgramHealth
    def test_health_total_initiatives_negative_rejected(self):
        with pytest.raises(ValueError, match="total_initiatives"):
            _health(total_initiatives=-1)

    def test_health_active_initiatives_negative_rejected(self):
        with pytest.raises(ValueError, match="active_initiatives"):
            _health(active_initiatives=-1)

    def test_health_blocked_initiatives_negative_rejected(self):
        with pytest.raises(ValueError, match="blocked_initiatives"):
            _health(blocked_initiatives=-1)

    def test_health_completed_initiatives_negative_rejected(self):
        with pytest.raises(ValueError, match="completed_initiatives"):
            _health(completed_initiatives=-1)

    def test_health_total_milestones_negative_rejected(self):
        with pytest.raises(ValueError, match="total_milestones"):
            _health(total_milestones=-1)

    def test_health_achieved_milestones_negative_rejected(self):
        with pytest.raises(ValueError, match="achieved_milestones"):
            _health(achieved_milestones=-1)

    def test_health_missed_milestones_negative_rejected(self):
        with pytest.raises(ValueError, match="missed_milestones"):
            _health(missed_milestones=-1)

    # ProgramClosureReport
    def test_closure_total_initiatives_negative_rejected(self):
        with pytest.raises(ValueError, match="total_initiatives"):
            _closure(total_initiatives=-1)

    def test_closure_completed_initiatives_negative_rejected(self):
        with pytest.raises(ValueError, match="completed_initiatives"):
            _closure(completed_initiatives=-1)

    def test_closure_failed_initiatives_negative_rejected(self):
        with pytest.raises(ValueError, match="failed_initiatives"):
            _closure(failed_initiatives=-1)

    def test_closure_total_milestones_negative_rejected(self):
        with pytest.raises(ValueError, match="total_milestones"):
            _closure(total_milestones=-1)

    def test_closure_achieved_milestones_negative_rejected(self):
        with pytest.raises(ValueError, match="achieved_milestones"):
            _closure(achieved_milestones=-1)

    def test_closure_missed_milestones_negative_rejected(self):
        with pytest.raises(ValueError, match="missed_milestones"):
            _closure(missed_milestones=-1)

    def test_bool_rejected_as_int(self):
        with pytest.raises(ValueError, match="total_initiatives"):
            _health(total_initiatives=True)


# ---------------------------------------------------------------------------
# require_non_negative_float
# ---------------------------------------------------------------------------


class TestRequireNonNegativeFloat:
    # weight on ObjectiveRecord
    def test_objective_weight_zero(self):
        o = _objective(weight=0.0)
        assert o.weight == 0.0

    def test_objective_weight_negative_rejected(self):
        with pytest.raises(ValueError, match="weight"):
            _objective(weight=-0.1)

    # weight on ObjectiveBinding
    def test_binding_weight_negative_rejected(self):
        with pytest.raises(ValueError, match="weight"):
            _binding(weight=-1.0)

    # progress_pct on InitiativeRecord
    def test_initiative_progress_pct_negative_rejected(self):
        with pytest.raises(ValueError, match="progress_pct"):
            _initiative(progress_pct=-0.01)

    # progress_pct on MilestoneRecord
    def test_milestone_progress_pct_negative_rejected(self):
        with pytest.raises(ValueError, match="progress_pct"):
            _milestone(progress_pct=-5.0)

    # progress_pct on AttainmentSnapshot
    def test_snapshot_progress_pct_negative_rejected(self):
        with pytest.raises(ValueError, match="progress_pct"):
            _snapshot(progress_pct=-1.0)

    # overall_progress_pct on ProgramHealth
    def test_health_overall_progress_pct_negative_rejected(self):
        with pytest.raises(ValueError, match="overall_progress_pct"):
            _health(overall_progress_pct=-0.1)

    # overall_attainment_pct on ProgramClosureReport
    def test_closure_overall_attainment_pct_negative_rejected(self):
        with pytest.raises(ValueError, match="overall_attainment_pct"):
            _closure(overall_attainment_pct=-1.0)

    def test_nan_rejected(self):
        with pytest.raises(ValueError, match="weight"):
            _objective(weight=float("nan"))

    def test_inf_rejected(self):
        with pytest.raises(ValueError, match="progress_pct"):
            _initiative(progress_pct=float("inf"))

    def test_bool_rejected(self):
        with pytest.raises(ValueError, match="weight"):
            _objective(weight=True)


# ---------------------------------------------------------------------------
# require_datetime_text
# ---------------------------------------------------------------------------


class TestRequireDatetimeText:
    def test_objective_invalid_created_at(self):
        with pytest.raises(ValueError, match="created_at"):
            _objective(created_at="not-a-date")

    def test_initiative_invalid_created_at(self):
        with pytest.raises(ValueError, match="created_at"):
            _initiative(created_at="nope")

    def test_program_invalid_created_at(self):
        with pytest.raises(ValueError, match="created_at"):
            _program(created_at="invalid")

    def test_milestone_invalid_created_at(self):
        with pytest.raises(ValueError, match="created_at"):
            _milestone(created_at="xyz")

    def test_binding_invalid_bound_at(self):
        with pytest.raises(ValueError, match="bound_at"):
            _binding(bound_at="bad")

    def test_dependency_invalid_created_at(self):
        with pytest.raises(ValueError, match="created_at"):
            _dependency(created_at="bad")

    def test_snapshot_invalid_captured_at(self):
        with pytest.raises(ValueError, match="captured_at"):
            _snapshot(captured_at="bad")

    def test_health_invalid_assessed_at(self):
        with pytest.raises(ValueError, match="assessed_at"):
            _health(assessed_at="bad")

    def test_decision_invalid_decided_at(self):
        with pytest.raises(ValueError, match="decided_at"):
            _decision(decided_at="bad")

    def test_closure_invalid_closed_at(self):
        with pytest.raises(ValueError, match="closed_at"):
            _closure(closed_at="bad")

    def test_iso_z_suffix_accepted(self):
        o = _objective(created_at="2025-06-01T12:00:00Z")
        assert o.created_at == "2025-06-01T12:00:00Z"

    def test_empty_created_at_rejected(self):
        with pytest.raises(ValueError, match="created_at"):
            _objective(created_at="")


# ---------------------------------------------------------------------------
# Enum type validation
# ---------------------------------------------------------------------------


class TestEnumTypeValidation:
    def test_objective_type_string_rejected(self):
        with pytest.raises(ValueError, match="objective_type"):
            _objective(objective_type="strategic")

    def test_attainment_string_rejected(self):
        with pytest.raises(ValueError, match="attainment"):
            _objective(attainment="on_track")

    def test_initiative_status_string_rejected(self):
        with pytest.raises(ValueError, match="status"):
            _initiative(status="active")

    def test_program_status_string_rejected(self):
        with pytest.raises(ValueError, match="status"):
            _program(status="draft")

    def test_milestone_status_string_rejected(self):
        with pytest.raises(ValueError, match="status"):
            _milestone(status="pending")

    def test_dependency_kind_string_rejected(self):
        with pytest.raises(ValueError, match="kind"):
            _dependency(kind="blocks")

    def test_health_status_string_rejected(self):
        with pytest.raises(ValueError, match="status"):
            _health(status="active")

    def test_closure_final_status_string_rejected(self):
        with pytest.raises(ValueError, match="final_status"):
            _closure(final_status="completed")

    def test_snapshot_attainment_string_rejected(self):
        with pytest.raises(ValueError, match="attainment"):
            _snapshot(attainment="on_track")


# ---------------------------------------------------------------------------
# freeze_value (metadata, tuple fields, lessons)
# ---------------------------------------------------------------------------


class TestFreezeValue:
    def test_objective_metadata_frozen(self):
        o = _objective(metadata={"k": "v"})
        assert isinstance(o.metadata, MappingProxyType)
        with pytest.raises(TypeError):
            o.metadata["new"] = "x"  # type: ignore[index]

    def test_initiative_metadata_frozen(self):
        i = _initiative(metadata={"k": "v"})
        assert isinstance(i.metadata, MappingProxyType)

    def test_program_metadata_frozen(self):
        p = _program(metadata={"k": "v"})
        assert isinstance(p.metadata, MappingProxyType)

    def test_milestone_metadata_frozen(self):
        m = _milestone(metadata={"k": "v"})
        assert isinstance(m.metadata, MappingProxyType)

    def test_snapshot_metadata_frozen(self):
        s = _snapshot(metadata={"k": "v"})
        assert isinstance(s.metadata, MappingProxyType)

    def test_decision_metadata_frozen(self):
        d = _decision(metadata={"k": "v"})
        assert isinstance(d.metadata, MappingProxyType)

    def test_closure_metadata_frozen(self):
        c = _closure(metadata={"k": "v"})
        assert isinstance(c.metadata, MappingProxyType)

    def test_initiative_campaign_ids_tuple(self):
        i = _initiative(campaign_ids=["c-1", "c-2"])
        assert isinstance(i.campaign_ids, tuple)
        assert i.campaign_ids == ("c-1", "c-2")

    def test_initiative_portfolio_ids_tuple(self):
        i = _initiative(portfolio_ids=["p-1"])
        assert isinstance(i.portfolio_ids, tuple)

    def test_initiative_milestone_ids_tuple(self):
        i = _initiative(milestone_ids=["ms-1"])
        assert isinstance(i.milestone_ids, tuple)

    def test_program_objective_ids_tuple(self):
        p = _program(objective_ids=["obj-1"])
        assert isinstance(p.objective_ids, tuple)

    def test_program_initiative_ids_tuple(self):
        p = _program(initiative_ids=["init-1"])
        assert isinstance(p.initiative_ids, tuple)

    def test_closure_lessons_tuple(self):
        c = _closure(lessons=["a", "b"])
        assert isinstance(c.lessons, tuple)
        assert c.lessons == ("a", "b")

    def test_nested_metadata_frozen(self):
        o = _objective(metadata={"nested": {"inner": 1}})
        assert isinstance(o.metadata["nested"], MappingProxyType)
        with pytest.raises(TypeError):
            o.metadata["nested"]["new"] = 2  # type: ignore[index]

    def test_list_to_tuple_in_metadata(self):
        o = _objective(metadata={"tags": [1, 2, 3]})
        assert isinstance(o.metadata["tags"], tuple)
        assert o.metadata["tags"] == (1, 2, 3)


# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------


class TestDefaults:
    def test_objective_defaults(self):
        o = _objective()
        assert o.description == ""
        assert o.objective_type is ObjectiveType.STRATEGIC
        assert o.parent_objective_id == ""
        assert o.target_value == 0.0
        assert o.current_value == 0.0
        assert o.unit == ""
        assert o.attainment is AttainmentLevel.NOT_STARTED
        assert o.weight == 1.0
        assert o.owner == ""
        assert o.updated_at == ""
        assert o.metadata == {}

    def test_initiative_defaults(self):
        i = _initiative()
        assert i.description == ""
        assert i.status is InitiativeStatus.DRAFT
        assert i.priority == 0
        assert i.progress_pct == 0.0
        assert i.owner == ""
        assert i.updated_at == ""

    def test_program_defaults(self):
        p = _program()
        assert p.description == ""
        assert p.status is ProgramStatus.DRAFT
        assert p.owner == ""
        assert p.updated_at == ""

    def test_milestone_defaults(self):
        m = _milestone()
        assert m.description == ""
        assert m.status is MilestoneStatus.PENDING
        assert m.target_date == ""
        assert m.completed_date == ""
        assert m.progress_pct == 0.0

    def test_binding_defaults(self):
        b = _binding()
        assert b.objective_id == ""
        assert b.initiative_id == ""
        assert b.campaign_ref_id == ""
        assert b.portfolio_ref_id == ""
        assert b.weight == 1.0

    def test_dependency_defaults(self):
        d = _dependency()
        assert d.kind is DependencyKind.REQUIRES
        assert d.description == ""

    def test_snapshot_defaults(self):
        s = _snapshot()
        assert s.attainment is AttainmentLevel.NOT_STARTED
        assert s.target_value == 0.0
        assert s.current_value == 0.0
        assert s.progress_pct == 0.0
        assert s.initiative_count == 0
        assert s.completed_initiatives == 0
        assert s.blocked_initiatives == 0

    def test_health_defaults(self):
        h = _health()
        assert h.status is ProgramStatus.ACTIVE
        assert h.total_initiatives == 0
        assert h.active_initiatives == 0
        assert h.blocked_initiatives == 0
        assert h.completed_initiatives == 0
        assert h.total_milestones == 0
        assert h.achieved_milestones == 0
        assert h.missed_milestones == 0
        assert h.overall_progress_pct == 0.0

    def test_decision_defaults(self):
        d = _decision()
        assert d.program_id == ""
        assert d.initiative_id == ""
        assert d.rationale == ""
        assert d.action == ""

    def test_closure_defaults(self):
        c = _closure()
        assert c.final_status is ProgramStatus.COMPLETED
        assert c.total_initiatives == 0
        assert c.completed_initiatives == 0
        assert c.failed_initiatives == 0
        assert c.total_milestones == 0
        assert c.achieved_milestones == 0
        assert c.missed_milestones == 0
        assert c.overall_attainment_pct == 0.0
        assert c.lessons == ()


# ---------------------------------------------------------------------------
# Edge-case boundaries
# ---------------------------------------------------------------------------


class TestEdgeCaseBoundaries:
    def test_weight_zero_accepted(self):
        o = _objective(weight=0.0)
        assert o.weight == 0.0

    def test_large_progress_pct_accepted(self):
        i = _initiative(progress_pct=999.9)
        assert i.progress_pct == 999.9

    def test_int_coerced_to_float_for_weight(self):
        o = _objective(weight=2)
        assert o.weight == 2.0
        assert isinstance(o.weight, float)

    def test_int_coerced_to_float_for_confidence(self):
        d = _decision(confidence=1)
        assert d.confidence == 1.0
        assert isinstance(d.confidence, float)

    def test_all_enum_values_for_program_status(self):
        for status in ProgramStatus:
            p = _program(status=status)
            assert p.status is status

    def test_all_enum_values_for_initiative_status(self):
        for status in InitiativeStatus:
            i = _initiative(status=status)
            assert i.status is status

    def test_all_enum_values_for_milestone_status(self):
        for status in MilestoneStatus:
            m = _milestone(status=status)
            assert m.status is status

    def test_all_enum_values_for_objective_type(self):
        for ot in ObjectiveType:
            o = _objective(objective_type=ot)
            assert o.objective_type is ot

    def test_all_enum_values_for_attainment_level(self):
        for al in AttainmentLevel:
            o = _objective(attainment=al)
            assert o.attainment is al

    def test_all_enum_values_for_dependency_kind(self):
        for kind in DependencyKind:
            d = _dependency(kind=kind)
            assert d.kind is kind

    def test_confidence_exact_boundaries(self):
        assert _decision(confidence=0.0).confidence == 0.0
        assert _decision(confidence=1.0).confidence == 1.0

    def test_empty_metadata_is_mapping_proxy(self):
        o = _objective()
        assert isinstance(o.metadata, MappingProxyType)

    def test_whitespace_only_id_rejected(self):
        with pytest.raises(ValueError, match="objective_id"):
            _objective(objective_id="\t\n ")


# ---------------------------------------------------------------------------
# to_dict serialization
# ---------------------------------------------------------------------------


class TestToDictSerialization:
    def test_objective_to_dict_preserves_enums(self):
        o = _objective(
            objective_type=ObjectiveType.TACTICAL,
            attainment=AttainmentLevel.ON_TRACK,
            metadata={"k": "v"},
        )
        d = o.to_dict()
        assert d["objective_id"] == "obj-001"
        assert d["title"] == "Revenue target"
        assert d["objective_type"] is ObjectiveType.TACTICAL
        assert d["attainment"] is AttainmentLevel.ON_TRACK
        assert d["metadata"] == {"k": "v"}
        assert isinstance(d["metadata"], dict)

    def test_initiative_to_dict_tuples_become_lists(self):
        i = _initiative(
            campaign_ids=("c-1", "c-2"),
            status=InitiativeStatus.ACTIVE,
        )
        d = i.to_dict()
        assert d["campaign_ids"] == ["c-1", "c-2"]
        assert isinstance(d["campaign_ids"], list)
        assert d["status"] is InitiativeStatus.ACTIVE

    def test_program_to_dict(self):
        p = _program(
            objective_ids=("obj-1",),
            initiative_ids=("init-1",),
            status=ProgramStatus.ACTIVE,
        )
        d = p.to_dict()
        assert d["objective_ids"] == ["obj-1"]
        assert d["initiative_ids"] == ["init-1"]
        assert d["status"] is ProgramStatus.ACTIVE

    def test_milestone_to_dict(self):
        m = _milestone(status=MilestoneStatus.ACHIEVED)
        d = m.to_dict()
        assert d["milestone_id"] == "ms-001"
        assert d["status"] is MilestoneStatus.ACHIEVED

    def test_binding_to_dict(self):
        b = _binding(weight=0.5)
        d = b.to_dict()
        assert d["binding_id"] == "bind-001"
        assert d["weight"] == 0.5

    def test_dependency_to_dict(self):
        dep = _dependency(kind=DependencyKind.BLOCKS)
        d = dep.to_dict()
        assert d["kind"] is DependencyKind.BLOCKS

    def test_snapshot_to_dict(self):
        s = _snapshot(attainment=AttainmentLevel.EXCEEDED, metadata={"x": 1})
        d = s.to_dict()
        assert d["attainment"] is AttainmentLevel.EXCEEDED
        assert d["metadata"] == {"x": 1}

    def test_health_to_dict(self):
        h = _health(status=ProgramStatus.COMPLETED, total_initiatives=5)
        d = h.to_dict()
        assert d["status"] is ProgramStatus.COMPLETED
        assert d["total_initiatives"] == 5

    def test_decision_to_dict(self):
        dec = _decision(confidence=0.9, metadata={"tag": "urgent"})
        d = dec.to_dict()
        assert d["confidence"] == 0.9
        assert d["metadata"] == {"tag": "urgent"}

    def test_closure_to_dict_lessons_become_list(self):
        c = _closure(lessons=("a", "b"), metadata={"done": True})
        d = c.to_dict()
        assert d["lessons"] == ["a", "b"]
        assert isinstance(d["lessons"], list)
        assert d["metadata"] == {"done": True}
        assert d["final_status"] is ProgramStatus.COMPLETED

    def test_to_json_produces_string(self):
        b = _binding(weight=0.5)
        j = b.to_json()
        assert isinstance(j, str)
        assert '"binding_id":"bind-001"' in j
