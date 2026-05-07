"""Comprehensive tests for mcoi.mcoi_runtime.core.program_runtime.ProgramRuntimeEngine."""

from __future__ import annotations

import pytest

from mcoi_runtime.core.program_runtime import ProgramRuntimeEngine
from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
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
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def spine() -> EventSpineEngine:
    return EventSpineEngine()


@pytest.fixture()
def engine(spine: EventSpineEngine) -> ProgramRuntimeEngine:
    return ProgramRuntimeEngine(spine)


def _seed_program(engine: ProgramRuntimeEngine, *, obj_id: str = "obj-1",
                  prog_id: str = "prog-1") -> tuple[ObjectiveRecord, ProgramRecord]:
    """Register an objective and a program linked to it."""
    obj = engine.register_objective(obj_id, "Revenue Target", target_value=100.0, unit="USD")
    prog = engine.register_program(prog_id, "Growth Program", objective_ids=[obj_id])
    return obj, prog


def _seed_initiative(engine: ProgramRuntimeEngine, *, init_id: str = "ini-1",
                     prog_id: str = "prog-1", obj_id: str = "obj-1") -> InitiativeRecord:
    return engine.register_initiative(init_id, prog_id, "Initiative Alpha", objective_id=obj_id)


def _seed_full(engine: ProgramRuntimeEngine):
    """Seed objective -> program -> initiative -> milestone."""
    obj, prog = _seed_program(engine)
    ini = _seed_initiative(engine)
    ms = engine.register_milestone("ms-1", "ini-1", "First Milestone")
    return obj, prog, ini, ms


# ===========================================================================
# TestConstructor
# ===========================================================================


class TestConstructor:
    def test_valid_construction(self, spine: EventSpineEngine) -> None:
        eng = ProgramRuntimeEngine(spine)
        assert eng.objective_count == 0
        assert eng.program_count == 0
        assert eng.initiative_count == 0
        assert eng.milestone_count == 0

    def test_invalid_spine_raises(self) -> None:
        with pytest.raises(RuntimeCoreInvariantError):
            ProgramRuntimeEngine("not-a-spine")  # type: ignore[arg-type]

    def test_initial_counts_all_zero(self, engine: ProgramRuntimeEngine) -> None:
        assert engine.binding_count == 0
        assert engine.dependency_count == 0
        assert engine.decision_count == 0


# ===========================================================================
# TestObjectiveManagement
# ===========================================================================


class TestObjectiveManagement:
    def test_register_and_get(self, engine: ProgramRuntimeEngine) -> None:
        rec = engine.register_objective("o1", "Grow Revenue", target_value=1000.0, unit="USD")
        assert isinstance(rec, ObjectiveRecord)
        assert rec.objective_id == "o1"
        assert rec.title == "Grow Revenue"
        assert rec.attainment == AttainmentLevel.NOT_STARTED
        assert rec.target_value == 1000.0
        fetched = engine.get_objective("o1")
        assert fetched is not None
        assert fetched.objective_id == "o1"

    def test_get_missing_returns_none(self, engine: ProgramRuntimeEngine) -> None:
        assert engine.get_objective("nope") is None

    def test_duplicate_raises(self, engine: ProgramRuntimeEngine) -> None:
        engine.register_objective("o1", "Objective 1")
        with pytest.raises(RuntimeCoreInvariantError, match="already exists"):
            engine.register_objective("o1", "Objective 1 again")

    def test_register_with_all_optional_params(self, engine: ProgramRuntimeEngine) -> None:
        rec = engine.register_objective(
            "o2", "KR-1",
            description="Key result",
            objective_type=ObjectiveType.KEY_RESULT,
            parent_objective_id="o1",
            target_value=50.0,
            current_value=10.0,
            unit="points",
            weight=0.5,
            owner="alice",
            metadata={"tag": "kr"},
        )
        assert rec.objective_type == ObjectiveType.KEY_RESULT
        assert rec.parent_objective_id == "o1"
        assert rec.weight == 0.5
        assert rec.metadata["tag"] == "kr"

    def test_update_value_missing_raises(self, engine: ProgramRuntimeEngine) -> None:
        with pytest.raises(RuntimeCoreInvariantError, match="not found"):
            engine.update_objective_value("ghost", 42.0)

    def test_update_value_updates_current(self, engine: ProgramRuntimeEngine) -> None:
        engine.register_objective("o1", "Rev", target_value=100.0)
        updated = engine.update_objective_value("o1", 95.0)
        assert updated.current_value == 95.0
        assert updated.attainment == AttainmentLevel.ON_TRACK

    def test_objective_count_increments(self, engine: ProgramRuntimeEngine) -> None:
        engine.register_objective("a", "A")
        engine.register_objective("b", "B")
        assert engine.objective_count == 2


# ===========================================================================
# TestAttainmentComputation
# ===========================================================================


class TestAttainmentComputation:
    """Tests _compute_attainment_level thresholds via update_objective_value."""

    def _register_and_update(self, engine, target, current):
        engine.register_objective("o", "O", target_value=target)
        return engine.update_objective_value("o", current)

    def test_exceeded_at_110_pct(self, engine: ProgramRuntimeEngine) -> None:
        rec = self._register_and_update(engine, 100.0, 110.0)
        assert rec.attainment == AttainmentLevel.EXCEEDED

    def test_exceeded_above_110(self, engine: ProgramRuntimeEngine) -> None:
        rec = self._register_and_update(engine, 100.0, 150.0)
        assert rec.attainment == AttainmentLevel.EXCEEDED

    def test_on_track_at_95_pct(self, engine: ProgramRuntimeEngine) -> None:
        rec = self._register_and_update(engine, 100.0, 95.0)
        assert rec.attainment == AttainmentLevel.ON_TRACK

    def test_on_track_at_90_pct(self, engine: ProgramRuntimeEngine) -> None:
        rec = self._register_and_update(engine, 100.0, 90.0)
        assert rec.attainment == AttainmentLevel.ON_TRACK

    def test_at_risk_at_75_pct(self, engine: ProgramRuntimeEngine) -> None:
        rec = self._register_and_update(engine, 100.0, 75.0)
        assert rec.attainment == AttainmentLevel.AT_RISK

    def test_at_risk_at_70_pct(self, engine: ProgramRuntimeEngine) -> None:
        rec = self._register_and_update(engine, 100.0, 70.0)
        assert rec.attainment == AttainmentLevel.AT_RISK

    def test_behind_at_50_pct(self, engine: ProgramRuntimeEngine) -> None:
        rec = self._register_and_update(engine, 100.0, 50.0)
        assert rec.attainment == AttainmentLevel.BEHIND

    def test_behind_at_small_positive(self, engine: ProgramRuntimeEngine) -> None:
        rec = self._register_and_update(engine, 100.0, 1.0)
        assert rec.attainment == AttainmentLevel.BEHIND

    def test_not_started_at_zero(self, engine: ProgramRuntimeEngine) -> None:
        rec = self._register_and_update(engine, 100.0, 0.0)
        assert rec.attainment == AttainmentLevel.NOT_STARTED

    def test_target_zero_returns_on_track(self, engine: ProgramRuntimeEngine) -> None:
        rec = self._register_and_update(engine, 0.0, 42.0)
        assert rec.attainment == AttainmentLevel.ON_TRACK

    def test_target_zero_current_zero(self, engine: ProgramRuntimeEngine) -> None:
        rec = self._register_and_update(engine, 0.0, 0.0)
        assert rec.attainment == AttainmentLevel.ON_TRACK

    def test_boundary_just_below_110(self, engine: ProgramRuntimeEngine) -> None:
        rec = self._register_and_update(engine, 100.0, 109.99)
        assert rec.attainment == AttainmentLevel.ON_TRACK

    def test_boundary_just_below_90(self, engine: ProgramRuntimeEngine) -> None:
        rec = self._register_and_update(engine, 100.0, 89.99)
        assert rec.attainment == AttainmentLevel.AT_RISK

    def test_boundary_just_below_70(self, engine: ProgramRuntimeEngine) -> None:
        rec = self._register_and_update(engine, 100.0, 69.99)
        assert rec.attainment == AttainmentLevel.BEHIND

    def test_compute_attainment_snapshot_missing_raises(self, engine: ProgramRuntimeEngine) -> None:
        with pytest.raises(RuntimeCoreInvariantError, match="not found"):
            engine.compute_attainment("ghost", "snap-1")

    def test_compute_attainment_snapshot_basic(self, engine: ProgramRuntimeEngine) -> None:
        _seed_program(engine)
        _seed_initiative(engine)
        engine.update_objective_value("obj-1", 95.0)
        snap = engine.compute_attainment("obj-1", "snap-1")
        assert isinstance(snap, AttainmentSnapshot)
        assert snap.objective_id == "obj-1"
        assert snap.initiative_count == 1
        assert snap.progress_pct == 95.0  # target=100, current=95

    def test_compute_attainment_no_target_uses_initiative_ratio(self, engine: ProgramRuntimeEngine) -> None:
        engine.register_objective("o", "O", target_value=0.0)
        engine.register_program("p", "P", objective_ids=["o"])
        i1 = engine.register_initiative("i1", "p", "I1", objective_id="o")
        engine.set_initiative_status("i1", InitiativeStatus.COMPLETED)
        engine.register_initiative("i2", "p", "I2", objective_id="o")
        snap = engine.compute_attainment("o", "snap-x")
        assert snap.initiative_count == 2
        assert snap.completed_initiatives == 1
        assert snap.progress_pct == 50.0


# ===========================================================================
# TestProgramManagement
# ===========================================================================


class TestProgramManagement:
    def test_register_and_get(self, engine: ProgramRuntimeEngine) -> None:
        rec = engine.register_program("p1", "Alpha Program")
        assert isinstance(rec, ProgramRecord)
        assert rec.program_id == "p1"
        assert rec.status == ProgramStatus.ACTIVE
        assert engine.get_program("p1") is not None

    def test_get_missing_returns_none(self, engine: ProgramRuntimeEngine) -> None:
        assert engine.get_program("nope") is None

    def test_duplicate_raises(self, engine: ProgramRuntimeEngine) -> None:
        engine.register_program("p1", "Alpha")
        with pytest.raises(RuntimeCoreInvariantError, match="already exists"):
            engine.register_program("p1", "Alpha 2")

    def test_register_with_objective_ids(self, engine: ProgramRuntimeEngine) -> None:
        engine.register_objective("o1", "O1")
        rec = engine.register_program("p1", "P1", objective_ids=["o1"])
        assert "o1" in rec.objective_ids

    def test_set_status(self, engine: ProgramRuntimeEngine) -> None:
        engine.register_program("p1", "P1")
        updated = engine.set_program_status("p1", ProgramStatus.PAUSED)
        assert updated.status == ProgramStatus.PAUSED

    def test_set_status_missing_raises(self, engine: ProgramRuntimeEngine) -> None:
        with pytest.raises(RuntimeCoreInvariantError, match="not found"):
            engine.set_program_status("ghost", ProgramStatus.ACTIVE)

    def test_program_count(self, engine: ProgramRuntimeEngine) -> None:
        engine.register_program("p1", "P1")
        engine.register_program("p2", "P2")
        assert engine.program_count == 2


# ===========================================================================
# TestInitiativeManagement
# ===========================================================================


class TestInitiativeManagement:
    def test_register_and_get(self, engine: ProgramRuntimeEngine) -> None:
        _seed_program(engine)
        ini = engine.register_initiative("i1", "prog-1", "Init Alpha", objective_id="obj-1")
        assert isinstance(ini, InitiativeRecord)
        assert ini.initiative_id == "i1"
        assert ini.status == InitiativeStatus.ACTIVE
        assert ini.progress_pct == 0.0
        assert engine.get_initiative("i1") is not None

    def test_get_missing_returns_none(self, engine: ProgramRuntimeEngine) -> None:
        assert engine.get_initiative("nope") is None

    def test_duplicate_raises(self, engine: ProgramRuntimeEngine) -> None:
        _seed_program(engine)
        engine.register_initiative("i1", "prog-1", "Init")
        with pytest.raises(RuntimeCoreInvariantError, match="already exists"):
            engine.register_initiative("i1", "prog-1", "Init 2")

    def test_missing_program_raises(self, engine: ProgramRuntimeEngine) -> None:
        with pytest.raises(RuntimeCoreInvariantError, match="not found"):
            engine.register_initiative("i1", "ghost-prog", "Init")

    def test_adds_to_program_initiative_ids(self, engine: ProgramRuntimeEngine) -> None:
        _seed_program(engine)
        engine.register_initiative("i1", "prog-1", "Init")
        prog = engine.get_program("prog-1")
        assert "i1" in prog.initiative_ids

    def test_set_status(self, engine: ProgramRuntimeEngine) -> None:
        _seed_program(engine)
        engine.register_initiative("i1", "prog-1", "Init")
        updated = engine.set_initiative_status("i1", InitiativeStatus.BLOCKED)
        assert updated.status == InitiativeStatus.BLOCKED

    def test_set_status_missing_raises(self, engine: ProgramRuntimeEngine) -> None:
        with pytest.raises(RuntimeCoreInvariantError, match="not found"):
            engine.set_initiative_status("ghost", InitiativeStatus.ACTIVE)

    def test_update_progress(self, engine: ProgramRuntimeEngine) -> None:
        _seed_program(engine)
        engine.register_initiative("i1", "prog-1", "Init")
        updated = engine.update_initiative_progress("i1", 55.0)
        assert updated.progress_pct == 55.0

    def test_update_progress_missing_raises(self, engine: ProgramRuntimeEngine) -> None:
        with pytest.raises(RuntimeCoreInvariantError, match="not found"):
            engine.update_initiative_progress("ghost", 10.0)

    def test_initiative_count(self, engine: ProgramRuntimeEngine) -> None:
        _seed_program(engine)
        engine.register_initiative("i1", "prog-1", "A")
        engine.register_initiative("i2", "prog-1", "B")
        assert engine.initiative_count == 2


# ===========================================================================
# TestMilestoneManagement
# ===========================================================================


class TestMilestoneManagement:
    def test_register_and_get(self, engine: ProgramRuntimeEngine) -> None:
        _seed_program(engine)
        _seed_initiative(engine)
        ms = engine.register_milestone("m1", "ini-1", "Milestone One")
        assert isinstance(ms, MilestoneRecord)
        assert ms.milestone_id == "m1"
        assert ms.status == MilestoneStatus.PENDING
        assert ms.progress_pct == 0.0
        assert engine.get_milestone("m1") is not None

    def test_get_missing_returns_none(self, engine: ProgramRuntimeEngine) -> None:
        assert engine.get_milestone("nope") is None

    def test_duplicate_raises(self, engine: ProgramRuntimeEngine) -> None:
        _seed_program(engine)
        _seed_initiative(engine)
        engine.register_milestone("m1", "ini-1", "MS1")
        with pytest.raises(RuntimeCoreInvariantError, match="already exists"):
            engine.register_milestone("m1", "ini-1", "MS1 dup")

    def test_missing_initiative_raises(self, engine: ProgramRuntimeEngine) -> None:
        with pytest.raises(RuntimeCoreInvariantError, match="not found"):
            engine.register_milestone("m1", "ghost-ini", "MS1")

    def test_adds_to_initiative_milestone_ids(self, engine: ProgramRuntimeEngine) -> None:
        _seed_program(engine)
        _seed_initiative(engine)
        engine.register_milestone("m1", "ini-1", "MS1")
        ini = engine.get_initiative("ini-1")
        assert "m1" in ini.milestone_ids

    def test_record_progress(self, engine: ProgramRuntimeEngine) -> None:
        _seed_program(engine)
        _seed_initiative(engine)
        engine.register_milestone("m1", "ini-1", "MS1")
        updated = engine.record_milestone_progress("m1", 60.0)
        assert updated.progress_pct == 60.0
        assert updated.status == MilestoneStatus.PENDING  # no auto-change below 100

    def test_auto_achieved_at_100(self, engine: ProgramRuntimeEngine) -> None:
        _seed_program(engine)
        _seed_initiative(engine)
        engine.register_milestone("m1", "ini-1", "MS1")
        updated = engine.record_milestone_progress("m1", 100.0)
        assert updated.status == MilestoneStatus.ACHIEVED
        assert updated.completed_date != ""

    def test_explicit_status_overrides(self, engine: ProgramRuntimeEngine) -> None:
        _seed_program(engine)
        _seed_initiative(engine)
        engine.register_milestone("m1", "ini-1", "MS1")
        updated = engine.record_milestone_progress("m1", 50.0, status=MilestoneStatus.MISSED)
        assert updated.status == MilestoneStatus.MISSED

    def test_record_progress_missing_raises(self, engine: ProgramRuntimeEngine) -> None:
        with pytest.raises(RuntimeCoreInvariantError, match="not found"):
            engine.record_milestone_progress("ghost", 50.0)

    def test_milestone_count(self, engine: ProgramRuntimeEngine) -> None:
        _seed_program(engine)
        _seed_initiative(engine)
        engine.register_milestone("m1", "ini-1", "A")
        engine.register_milestone("m2", "ini-1", "B")
        assert engine.milestone_count == 2


# ===========================================================================
# TestBindings
# ===========================================================================


class TestBindings:
    def test_bind_campaign(self, engine: ProgramRuntimeEngine) -> None:
        _seed_program(engine)
        _seed_initiative(engine)
        b = engine.bind_campaign("b1", "ini-1", "camp-1", objective_id="obj-1", weight=0.8)
        assert isinstance(b, ObjectiveBinding)
        assert b.binding_id == "b1"
        assert b.campaign_ref_id == "camp-1"
        assert b.weight == 0.8

    def test_bind_campaign_missing_initiative_raises(self, engine: ProgramRuntimeEngine) -> None:
        with pytest.raises(RuntimeCoreInvariantError, match="not found"):
            engine.bind_campaign("b1", "ghost", "camp-1")

    def test_bind_campaign_adds_to_initiative_campaign_ids(self, engine: ProgramRuntimeEngine) -> None:
        _seed_program(engine)
        _seed_initiative(engine)
        engine.bind_campaign("b1", "ini-1", "camp-1")
        ini = engine.get_initiative("ini-1")
        assert "camp-1" in ini.campaign_ids

    def test_bind_portfolio(self, engine: ProgramRuntimeEngine) -> None:
        _seed_program(engine)
        _seed_initiative(engine)
        b = engine.bind_portfolio("b2", "ini-1", "port-1", objective_id="obj-1", weight=0.6)
        assert isinstance(b, ObjectiveBinding)
        assert b.portfolio_ref_id == "port-1"

    def test_bind_portfolio_missing_initiative_raises(self, engine: ProgramRuntimeEngine) -> None:
        with pytest.raises(RuntimeCoreInvariantError, match="not found"):
            engine.bind_portfolio("b2", "ghost", "port-1")

    def test_bind_portfolio_adds_to_initiative_portfolio_ids(self, engine: ProgramRuntimeEngine) -> None:
        _seed_program(engine)
        _seed_initiative(engine)
        engine.bind_portfolio("b2", "ini-1", "port-1")
        ini = engine.get_initiative("ini-1")
        assert "port-1" in ini.portfolio_ids

    def test_binding_count(self, engine: ProgramRuntimeEngine) -> None:
        _seed_program(engine)
        _seed_initiative(engine)
        engine.bind_campaign("b1", "ini-1", "c1")
        engine.bind_portfolio("b2", "ini-1", "p1")
        assert engine.binding_count == 2

    def test_get_bindings(self, engine: ProgramRuntimeEngine) -> None:
        _seed_program(engine)
        _seed_initiative(engine)
        engine.bind_campaign("b1", "ini-1", "c1")
        bindings = engine.get_bindings()
        assert isinstance(bindings, tuple)
        assert len(bindings) == 1


# ===========================================================================
# TestDependencies
# ===========================================================================


class TestDependencies:
    def test_add_dependency(self, engine: ProgramRuntimeEngine) -> None:
        _seed_program(engine)
        engine.register_initiative("i1", "prog-1", "I1")
        engine.register_initiative("i2", "prog-1", "I2")
        dep = engine.add_dependency("d1", "i2", "i1", kind=DependencyKind.REQUIRES)
        assert isinstance(dep, InitiativeDependency)
        assert dep.dependency_id == "d1"
        assert dep.from_initiative_id == "i2"
        assert dep.to_initiative_id == "i1"
        assert dep.kind == DependencyKind.REQUIRES

    def test_dependency_count(self, engine: ProgramRuntimeEngine) -> None:
        _seed_program(engine)
        engine.register_initiative("i1", "prog-1", "I1")
        engine.register_initiative("i2", "prog-1", "I2")
        engine.add_dependency("d1", "i2", "i1")
        engine.add_dependency("d2", "i1", "i2", kind=DependencyKind.ENHANCES)
        assert engine.dependency_count == 2

    def test_get_dependencies(self, engine: ProgramRuntimeEngine) -> None:
        _seed_program(engine)
        engine.register_initiative("i1", "prog-1", "I1")
        engine.register_initiative("i2", "prog-1", "I2")
        engine.add_dependency("d1", "i2", "i1")
        deps = engine.get_dependencies()
        assert isinstance(deps, tuple)
        assert len(deps) == 1

    def test_dependency_kinds(self, engine: ProgramRuntimeEngine) -> None:
        _seed_program(engine)
        engine.register_initiative("i1", "prog-1", "I1")
        engine.register_initiative("i2", "prog-1", "I2")
        for idx, kind in enumerate(DependencyKind):
            dep = engine.add_dependency(f"d{idx}", "i1", "i2", kind=kind)
            assert dep.kind == kind


# ===========================================================================
# TestBlockedInitiatives
# ===========================================================================


class TestBlockedInitiatives:
    def test_no_blocked_initially(self, engine: ProgramRuntimeEngine) -> None:
        assert engine.blocked_initiatives() == ()

    def test_explicitly_blocked(self, engine: ProgramRuntimeEngine) -> None:
        _seed_program(engine)
        engine.register_initiative("i1", "prog-1", "I1")
        engine.set_initiative_status("i1", InitiativeStatus.BLOCKED)
        blocked = engine.blocked_initiatives()
        assert len(blocked) == 1
        assert blocked[0].initiative_id == "i1"

    def test_dependency_blocked_requires_failed(self, engine: ProgramRuntimeEngine) -> None:
        """i2 REQUIRES i1; i1 is FAILED -> i2 appears in blocked."""
        _seed_program(engine)
        engine.register_initiative("i1", "prog-1", "I1")
        engine.register_initiative("i2", "prog-1", "I2")
        engine.add_dependency("d1", "i2", "i1", kind=DependencyKind.REQUIRES)
        engine.set_initiative_status("i1", InitiativeStatus.FAILED)
        blocked = engine.blocked_initiatives()
        ids = [b.initiative_id for b in blocked]
        assert "i2" in ids

    def test_dependency_blocked_requires_cancelled(self, engine: ProgramRuntimeEngine) -> None:
        _seed_program(engine)
        engine.register_initiative("i1", "prog-1", "I1")
        engine.register_initiative("i2", "prog-1", "I2")
        engine.add_dependency("d1", "i2", "i1", kind=DependencyKind.REQUIRES)
        engine.set_initiative_status("i1", InitiativeStatus.CANCELLED)
        blocked = engine.blocked_initiatives()
        ids = [b.initiative_id for b in blocked]
        assert "i2" in ids

    def test_dependency_blocked_blocks_kind(self, engine: ProgramRuntimeEngine) -> None:
        _seed_program(engine)
        engine.register_initiative("i1", "prog-1", "I1")
        engine.register_initiative("i2", "prog-1", "I2")
        engine.add_dependency("d1", "i2", "i1", kind=DependencyKind.BLOCKS)
        engine.set_initiative_status("i1", InitiativeStatus.BLOCKED)
        blocked = engine.blocked_initiatives()
        ids = [b.initiative_id for b in blocked]
        assert "i2" in ids

    def test_enhances_does_not_block(self, engine: ProgramRuntimeEngine) -> None:
        _seed_program(engine)
        engine.register_initiative("i1", "prog-1", "I1")
        engine.register_initiative("i2", "prog-1", "I2")
        engine.add_dependency("d1", "i2", "i1", kind=DependencyKind.ENHANCES)
        engine.set_initiative_status("i1", InitiativeStatus.FAILED)
        blocked = engine.blocked_initiatives()
        ids = [b.initiative_id for b in blocked]
        assert "i2" not in ids

    def test_active_dependency_no_block(self, engine: ProgramRuntimeEngine) -> None:
        _seed_program(engine)
        engine.register_initiative("i1", "prog-1", "I1")
        engine.register_initiative("i2", "prog-1", "I2")
        engine.add_dependency("d1", "i2", "i1", kind=DependencyKind.REQUIRES)
        # i1 stays ACTIVE -> i2 should not be blocked
        blocked = engine.blocked_initiatives()
        assert len(blocked) == 0


# ===========================================================================
# TestProgramHealth
# ===========================================================================


class TestProgramHealth:
    def test_basic_health(self, engine: ProgramRuntimeEngine) -> None:
        _seed_program(engine)
        _seed_initiative(engine)
        engine.register_milestone("m1", "ini-1", "MS1")
        health = engine.program_health("prog-1", "h1")
        assert isinstance(health, ProgramHealth)
        assert health.program_id == "prog-1"
        assert health.total_initiatives == 1
        assert health.active_initiatives == 1
        assert health.total_milestones == 1

    def test_health_missing_program_raises(self, engine: ProgramRuntimeEngine) -> None:
        with pytest.raises(RuntimeCoreInvariantError, match="not found"):
            engine.program_health("ghost", "h1")

    def test_overall_progress_average(self, engine: ProgramRuntimeEngine) -> None:
        _seed_program(engine)
        engine.register_initiative("i1", "prog-1", "I1")
        engine.register_initiative("i2", "prog-1", "I2")
        engine.update_initiative_progress("i1", 60.0)
        engine.update_initiative_progress("i2", 80.0)
        health = engine.program_health("prog-1", "h1")
        assert health.overall_progress_pct == pytest.approx(70.0)

    def test_health_counts_blocked_and_completed(self, engine: ProgramRuntimeEngine) -> None:
        _seed_program(engine)
        engine.register_initiative("i1", "prog-1", "I1")
        engine.register_initiative("i2", "prog-1", "I2")
        engine.register_initiative("i3", "prog-1", "I3")
        engine.set_initiative_status("i1", InitiativeStatus.COMPLETED)
        engine.set_initiative_status("i2", InitiativeStatus.BLOCKED)
        health = engine.program_health("prog-1", "h1")
        assert health.completed_initiatives == 1
        assert health.blocked_initiatives == 1
        assert health.active_initiatives == 1

    def test_health_milestones_achieved_missed(self, engine: ProgramRuntimeEngine) -> None:
        _seed_program(engine)
        _seed_initiative(engine)
        engine.register_milestone("m1", "ini-1", "MS1")
        engine.register_milestone("m2", "ini-1", "MS2")
        engine.record_milestone_progress("m1", 100.0)  # auto-ACHIEVED
        engine.record_milestone_progress("m2", 30.0, status=MilestoneStatus.MISSED)
        health = engine.program_health("prog-1", "h1")
        assert health.achieved_milestones == 1
        assert health.missed_milestones == 1

    def test_empty_program_health(self, engine: ProgramRuntimeEngine) -> None:
        engine.register_program("p1", "Empty")
        health = engine.program_health("p1", "h1")
        assert health.total_initiatives == 0
        assert health.overall_progress_pct == 0.0


# ===========================================================================
# TestDecisions
# ===========================================================================


class TestDecisions:
    def test_record_and_get(self, engine: ProgramRuntimeEngine) -> None:
        dec = engine.record_decision("d1", "Pivot Strategy", rationale="Market shift")
        assert isinstance(dec, ProgramDecision)
        assert dec.decision_id == "d1"
        assert dec.title == "Pivot Strategy"
        assert dec.confidence == 0.8  # default
        fetched = engine.get_decision("d1")
        assert fetched is not None

    def test_get_missing_returns_none(self, engine: ProgramRuntimeEngine) -> None:
        assert engine.get_decision("nope") is None

    def test_duplicate_raises(self, engine: ProgramRuntimeEngine) -> None:
        engine.record_decision("d1", "Decision 1")
        with pytest.raises(RuntimeCoreInvariantError, match="already exists"):
            engine.record_decision("d1", "Decision 1 again")

    def test_full_params(self, engine: ProgramRuntimeEngine) -> None:
        dec = engine.record_decision(
            "d2", "Reallocate Budget",
            program_id="p1",
            initiative_id="i1",
            rationale="Over budget",
            action="Cut scope",
            confidence=0.95,
            metadata={"approver": "cto"},
        )
        assert dec.program_id == "p1"
        assert dec.confidence == 0.95
        assert dec.metadata["approver"] == "cto"

    def test_decision_count(self, engine: ProgramRuntimeEngine) -> None:
        engine.record_decision("d1", "D1")
        engine.record_decision("d2", "D2")
        assert engine.decision_count == 2


# ===========================================================================
# TestClosure
# ===========================================================================


class TestClosure:
    def test_basic_closure(self, engine: ProgramRuntimeEngine) -> None:
        _seed_program(engine)
        _seed_initiative(engine)
        engine.set_initiative_status("ini-1", InitiativeStatus.COMPLETED)
        report = engine.close_program("r1", "prog-1")
        assert isinstance(report, ProgramClosureReport)
        assert report.report_id == "r1"
        assert report.program_id == "prog-1"
        assert report.final_status == ProgramStatus.COMPLETED
        assert report.completed_initiatives == 1
        assert report.overall_attainment_pct == 100.0

    def test_closure_sets_program_status(self, engine: ProgramRuntimeEngine) -> None:
        _seed_program(engine)
        engine.close_program("r1", "prog-1", final_status=ProgramStatus.CANCELLED)
        prog = engine.get_program("prog-1")
        assert prog.status == ProgramStatus.CANCELLED

    def test_closure_missing_program_raises(self, engine: ProgramRuntimeEngine) -> None:
        with pytest.raises(RuntimeCoreInvariantError, match="not found"):
            engine.close_program("r1", "ghost")

    def test_closure_with_lessons(self, engine: ProgramRuntimeEngine) -> None:
        _seed_program(engine)
        report = engine.close_program("r1", "prog-1", lessons=["Lesson 1", "Lesson 2"])
        assert len(report.lessons) == 2
        assert "Lesson 1" in report.lessons

    def test_closure_attainment_partial(self, engine: ProgramRuntimeEngine) -> None:
        _seed_program(engine)
        engine.register_initiative("i1", "prog-1", "I1")
        engine.register_initiative("i2", "prog-1", "I2")
        engine.set_initiative_status("i1", InitiativeStatus.COMPLETED)
        # i2 stays ACTIVE
        report = engine.close_program("r1", "prog-1")
        assert report.total_initiatives == 2
        assert report.completed_initiatives == 1
        assert report.overall_attainment_pct == pytest.approx(50.0)

    def test_closure_counts_milestones(self, engine: ProgramRuntimeEngine) -> None:
        _seed_program(engine)
        _seed_initiative(engine)
        engine.register_milestone("m1", "ini-1", "MS1")
        engine.register_milestone("m2", "ini-1", "MS2")
        engine.record_milestone_progress("m1", 100.0)
        engine.record_milestone_progress("m2", 30.0, status=MilestoneStatus.MISSED)
        report = engine.close_program("r1", "prog-1")
        assert report.total_milestones == 2
        assert report.achieved_milestones == 1
        assert report.missed_milestones == 1

    def test_closure_empty_program(self, engine: ProgramRuntimeEngine) -> None:
        engine.register_program("p1", "Empty")
        report = engine.close_program("r1", "p1")
        assert report.total_initiatives == 0
        assert report.overall_attainment_pct == 0.0


# ===========================================================================
# TestProperties
# ===========================================================================


class TestProperties:
    def test_all_counts_after_seeding(self, engine: ProgramRuntimeEngine) -> None:
        _seed_full(engine)
        assert engine.objective_count == 1
        assert engine.program_count == 1
        assert engine.initiative_count == 1
        assert engine.milestone_count == 1
        assert engine.binding_count == 0
        assert engine.dependency_count == 0
        assert engine.decision_count == 0

    def test_counts_increase_with_operations(self, engine: ProgramRuntimeEngine) -> None:
        _seed_full(engine)
        engine.bind_campaign("b1", "ini-1", "c1")
        engine.add_dependency("d1", "ini-1", "ini-1")
        engine.record_decision("dec-1", "Dec")
        assert engine.binding_count == 1
        assert engine.dependency_count == 1
        assert engine.decision_count == 1


# ===========================================================================
# TestStateHash
# ===========================================================================


class TestStateHash:
    def test_returns_string(self, engine: ProgramRuntimeEngine) -> None:
        h = engine.state_hash()
        assert isinstance(h, str)
        assert len(h) == 64

    def test_hash_changes_on_mutation(self, engine: ProgramRuntimeEngine) -> None:
        h1 = engine.state_hash()
        engine.register_objective("o1", "O1")
        h2 = engine.state_hash()
        assert h1 != h2

    def test_hash_deterministic(self, engine: ProgramRuntimeEngine) -> None:
        engine.register_objective("o1", "O1")
        h1 = engine.state_hash()
        h2 = engine.state_hash()
        assert h1 == h2

    def test_hash_changes_with_status(self, engine: ProgramRuntimeEngine) -> None:
        engine.register_program("p1", "P1")
        h1 = engine.state_hash()
        engine.set_program_status("p1", ProgramStatus.PAUSED)
        h2 = engine.state_hash()
        assert h1 != h2

    def test_hash_changes_with_attainment(self, engine: ProgramRuntimeEngine) -> None:
        engine.register_objective("o1", "O1", target_value=100.0)
        h1 = engine.state_hash()
        engine.update_objective_value("o1", 95.0)
        h2 = engine.state_hash()
        assert h1 != h2


# ===========================================================================
# TestEventEmission
# ===========================================================================


class TestEventEmission:
    def test_register_objective_emits(self, spine: EventSpineEngine, engine: ProgramRuntimeEngine) -> None:
        before = spine.event_count
        engine.register_objective("o1", "O1")
        assert spine.event_count > before

    def test_update_objective_emits(self, spine: EventSpineEngine, engine: ProgramRuntimeEngine) -> None:
        engine.register_objective("o1", "O1", target_value=100.0)
        before = spine.event_count
        engine.update_objective_value("o1", 50.0)
        assert spine.event_count > before

    def test_register_program_emits(self, spine: EventSpineEngine, engine: ProgramRuntimeEngine) -> None:
        before = spine.event_count
        engine.register_program("p1", "P1")
        assert spine.event_count > before

    def test_set_program_status_emits(self, spine: EventSpineEngine, engine: ProgramRuntimeEngine) -> None:
        engine.register_program("p1", "P1")
        before = spine.event_count
        engine.set_program_status("p1", ProgramStatus.PAUSED)
        assert spine.event_count > before

    def test_register_initiative_emits(self, spine: EventSpineEngine, engine: ProgramRuntimeEngine) -> None:
        _seed_program(engine)
        before = spine.event_count
        engine.register_initiative("i1", "prog-1", "I1")
        assert spine.event_count > before

    def test_set_initiative_status_emits(self, spine: EventSpineEngine, engine: ProgramRuntimeEngine) -> None:
        _seed_program(engine)
        engine.register_initiative("i1", "prog-1", "I1")
        before = spine.event_count
        engine.set_initiative_status("i1", InitiativeStatus.BLOCKED)
        assert spine.event_count > before

    def test_register_milestone_emits(self, spine: EventSpineEngine, engine: ProgramRuntimeEngine) -> None:
        _seed_program(engine)
        _seed_initiative(engine)
        before = spine.event_count
        engine.register_milestone("m1", "ini-1", "MS1")
        assert spine.event_count > before

    def test_milestone_progress_emits(self, spine: EventSpineEngine, engine: ProgramRuntimeEngine) -> None:
        _seed_program(engine)
        _seed_initiative(engine)
        engine.register_milestone("m1", "ini-1", "MS1")
        before = spine.event_count
        engine.record_milestone_progress("m1", 50.0)
        assert spine.event_count > before

    def test_bind_campaign_emits(self, spine: EventSpineEngine, engine: ProgramRuntimeEngine) -> None:
        _seed_program(engine)
        _seed_initiative(engine)
        before = spine.event_count
        engine.bind_campaign("b1", "ini-1", "c1")
        assert spine.event_count > before

    def test_bind_portfolio_emits(self, spine: EventSpineEngine, engine: ProgramRuntimeEngine) -> None:
        _seed_program(engine)
        _seed_initiative(engine)
        before = spine.event_count
        engine.bind_portfolio("b1", "ini-1", "p1")
        assert spine.event_count > before

    def test_add_dependency_emits(self, spine: EventSpineEngine, engine: ProgramRuntimeEngine) -> None:
        _seed_program(engine)
        engine.register_initiative("i1", "prog-1", "I1")
        engine.register_initiative("i2", "prog-1", "I2")
        before = spine.event_count
        engine.add_dependency("d1", "i2", "i1")
        assert spine.event_count > before

    def test_compute_attainment_emits(self, spine: EventSpineEngine, engine: ProgramRuntimeEngine) -> None:
        _seed_program(engine)
        before = spine.event_count
        engine.compute_attainment("obj-1", "snap-1")
        assert spine.event_count > before

    def test_program_health_emits(self, spine: EventSpineEngine, engine: ProgramRuntimeEngine) -> None:
        _seed_program(engine)
        before = spine.event_count
        engine.program_health("prog-1", "h1")
        assert spine.event_count > before

    def test_record_decision_emits(self, spine: EventSpineEngine, engine: ProgramRuntimeEngine) -> None:
        before = spine.event_count
        engine.record_decision("d1", "D1")
        assert spine.event_count > before

    def test_close_program_emits(self, spine: EventSpineEngine, engine: ProgramRuntimeEngine) -> None:
        _seed_program(engine)
        before = spine.event_count
        engine.close_program("r1", "prog-1")
        assert spine.event_count > before


# ===========================================================================
# Golden Scenarios
# ===========================================================================


class TestGoldenScenario1ExecutiveObjectiveFullChain:
    """Executive objective -> program -> 2 initiatives -> milestones -> campaigns -> attainment."""

    def test_full_chain(self, engine: ProgramRuntimeEngine) -> None:
        # 1. Register executive objective
        obj = engine.register_objective(
            "obj-rev", "Annual Revenue Target",
            objective_type=ObjectiveType.STRATEGIC,
            target_value=1_000_000.0,
            unit="USD",
            owner="CEO",
        )
        assert obj.attainment == AttainmentLevel.NOT_STARTED

        # 2. Register program
        prog = engine.register_program(
            "prog-growth", "Revenue Growth Program",
            objective_ids=["obj-rev"],
            owner="VP-Sales",
        )
        assert prog.status == ProgramStatus.ACTIVE

        # 3. Register two initiatives
        ini1 = engine.register_initiative(
            "ini-enterprise", "prog-growth", "Enterprise Sales Push",
            objective_id="obj-rev", priority=1,
        )
        ini2 = engine.register_initiative(
            "ini-smb", "prog-growth", "SMB Expansion",
            objective_id="obj-rev", priority=2,
        )
        assert engine.initiative_count == 2

        # 4. Register milestones
        ms1 = engine.register_milestone("ms-q1", "ini-enterprise", "Q1 Pipeline Built")
        ms2 = engine.register_milestone("ms-q2", "ini-enterprise", "Q2 Deals Closed")
        ms3 = engine.register_milestone("ms-smb-launch", "ini-smb", "SMB Launch")

        # 5. Bind campaigns
        engine.bind_campaign("b1", "ini-enterprise", "camp-enterprise-outbound", objective_id="obj-rev")
        engine.bind_campaign("b2", "ini-smb", "camp-smb-digital", objective_id="obj-rev")

        # 6. Progress
        engine.record_milestone_progress("ms-q1", 100.0)
        engine.record_milestone_progress("ms-q2", 50.0)
        engine.record_milestone_progress("ms-smb-launch", 80.0)
        engine.update_initiative_progress("ini-enterprise", 60.0)
        engine.update_initiative_progress("ini-smb", 40.0)
        engine.update_objective_value("obj-rev", 950_000.0)

        # 7. Compute attainment snapshot
        snap = engine.compute_attainment("obj-rev", "snap-annual")
        assert snap.attainment == AttainmentLevel.ON_TRACK  # 95%
        assert snap.initiative_count == 2
        assert snap.progress_pct == 95.0


class TestGoldenScenario2TwoCampaignsRollUp:
    """Two campaigns roll up into one initiative progress."""

    def test_two_campaigns(self, engine: ProgramRuntimeEngine) -> None:
        engine.register_objective("o1", "Market Penetration", target_value=0.0)
        engine.register_program("p1", "Marketing", objective_ids=["o1"])
        engine.register_initiative("i1", "p1", "Brand Awareness", objective_id="o1")

        # Bind two campaigns
        engine.bind_campaign("b1", "i1", "camp-social")
        engine.bind_campaign("b2", "i1", "camp-events")

        ini = engine.get_initiative("i1")
        assert "camp-social" in ini.campaign_ids
        assert "camp-events" in ini.campaign_ids
        assert len(ini.campaign_ids) == 2

        # Update initiative progress reflecting campaign results
        engine.update_initiative_progress("i1", 75.0)
        updated = engine.get_initiative("i1")
        assert updated.progress_pct == 75.0


class TestGoldenScenario3MissedMilestoneDegradeHealth:
    """Missed milestone degrades program health."""

    def test_missed_milestone(self, engine: ProgramRuntimeEngine) -> None:
        engine.register_objective("o1", "Delivery Quality")
        engine.register_program("p1", "Delivery Program", objective_ids=["o1"])
        engine.register_initiative("i1", "p1", "Feature Delivery", objective_id="o1")
        engine.register_milestone("m1", "i1", "Alpha Release")
        engine.register_milestone("m2", "i1", "Beta Release")

        # One achieved, one missed
        engine.record_milestone_progress("m1", 100.0)
        engine.record_milestone_progress("m2", 40.0, status=MilestoneStatus.MISSED)

        health = engine.program_health("p1", "h1")
        assert health.achieved_milestones == 1
        assert health.missed_milestones == 1
        assert health.total_milestones == 2


class TestGoldenScenario4BlockedDependencyEscalation:
    """i2 REQUIRES i1; i1 FAILED -> i2 appears in blocked_initiatives."""

    def test_blocked_escalation(self, engine: ProgramRuntimeEngine) -> None:
        engine.register_objective("o1", "Integration")
        engine.register_program("p1", "Integration Program")
        engine.register_initiative("i1", "p1", "Core API")
        engine.register_initiative("i2", "p1", "Client SDK")

        # i2 requires i1
        engine.add_dependency("dep-1", "i2", "i1", kind=DependencyKind.REQUIRES,
                              description="SDK needs API")

        # i1 fails
        engine.set_initiative_status("i1", InitiativeStatus.FAILED)

        blocked = engine.blocked_initiatives()
        blocked_ids = [b.initiative_id for b in blocked]
        assert "i2" in blocked_ids

        # Also check health reflects blocked
        health = engine.program_health("p1", "h1")
        # i1 is FAILED (not counted as blocked in health), i2 is ACTIVE but dependency-blocked
        # health counts status-level blocked only
        assert health.total_initiatives == 2


class TestGoldenScenario5FinancialDataUpdatesAttainment:
    """Financial/reporting data updates attainment level through thresholds."""

    def test_financial_attainment_progression(self, engine: ProgramRuntimeEngine) -> None:
        engine.register_objective("o-revenue", "Q4 Revenue", target_value=500_000.0, unit="USD")

        # Start: NOT_STARTED
        obj = engine.get_objective("o-revenue")
        assert obj.attainment == AttainmentLevel.NOT_STARTED

        # Small revenue: BEHIND
        engine.update_objective_value("o-revenue", 50_000.0)  # 10%
        obj = engine.get_objective("o-revenue")
        assert obj.attainment == AttainmentLevel.BEHIND

        # Growing: AT_RISK
        engine.update_objective_value("o-revenue", 375_000.0)  # 75%
        obj = engine.get_objective("o-revenue")
        assert obj.attainment == AttainmentLevel.AT_RISK

        # On track: ON_TRACK
        engine.update_objective_value("o-revenue", 475_000.0)  # 95%
        obj = engine.get_objective("o-revenue")
        assert obj.attainment == AttainmentLevel.ON_TRACK

        # Exceeded
        engine.update_objective_value("o-revenue", 600_000.0)  # 120%
        obj = engine.get_objective("o-revenue")
        assert obj.attainment == AttainmentLevel.EXCEEDED


class TestGoldenScenario6FullLifecycle:
    """Full lifecycle: objective -> program -> initiatives -> milestones -> progress -> health -> close."""

    def test_full_lifecycle(self, engine: ProgramRuntimeEngine) -> None:
        # 1. Objective
        engine.register_objective("obj-launch", "Product Launch", target_value=100.0, unit="percent")

        # 2. Program
        engine.register_program("prog-launch", "Launch Program", objective_ids=["obj-launch"])

        # 3. Initiatives
        engine.register_initiative("ini-dev", "prog-launch", "Development", objective_id="obj-launch")
        engine.register_initiative("ini-mkt", "prog-launch", "Marketing", objective_id="obj-launch")

        # 4. Milestones
        engine.register_milestone("ms-mvp", "ini-dev", "MVP Complete")
        engine.register_milestone("ms-beta", "ini-dev", "Beta Launch")
        engine.register_milestone("ms-campaign", "ini-mkt", "Campaign Live")

        # 5. Dependencies
        engine.add_dependency("dep-mkt-dev", "ini-mkt", "ini-dev", kind=DependencyKind.REQUIRES)

        # 6. Bindings
        engine.bind_campaign("bind-1", "ini-mkt", "camp-launch-ads")
        engine.bind_portfolio("bind-2", "ini-dev", "port-engineering")

        # 7. Progress milestones
        engine.record_milestone_progress("ms-mvp", 100.0)
        engine.record_milestone_progress("ms-beta", 100.0)
        engine.record_milestone_progress("ms-campaign", 100.0)

        # 8. Update initiative progress
        engine.update_initiative_progress("ini-dev", 100.0)
        engine.update_initiative_progress("ini-mkt", 100.0)
        engine.set_initiative_status("ini-dev", InitiativeStatus.COMPLETED)
        engine.set_initiative_status("ini-mkt", InitiativeStatus.COMPLETED)

        # 9. Update objective
        engine.update_objective_value("obj-launch", 110.0)

        # 10. Health check
        health = engine.program_health("prog-launch", "h-final")
        assert health.total_initiatives == 2
        assert health.completed_initiatives == 2
        assert health.overall_progress_pct == 100.0
        assert health.achieved_milestones == 3
        assert health.missed_milestones == 0

        # 11. Decision
        engine.record_decision(
            "dec-ship", "Ship to Production",
            program_id="prog-launch",
            rationale="All milestones achieved",
            action="Deploy",
            confidence=0.99,
        )

        # 12. Attainment
        snap = engine.compute_attainment("obj-launch", "snap-final")
        assert snap.attainment == AttainmentLevel.EXCEEDED
        assert snap.completed_initiatives == 2

        # 13. Close program
        report = engine.close_program(
            "rpt-final", "prog-launch",
            final_status=ProgramStatus.COMPLETED,
            lessons=["Ship earlier", "Invest in automation"],
        )
        assert report.final_status == ProgramStatus.COMPLETED
        assert report.completed_initiatives == 2
        assert report.overall_attainment_pct == 100.0
        assert len(report.lessons) == 2

        # Program status updated
        prog = engine.get_program("prog-launch")
        assert prog.status == ProgramStatus.COMPLETED

        # Final counts
        assert engine.objective_count == 1
        assert engine.program_count == 1
        assert engine.initiative_count == 2
        assert engine.milestone_count == 3
        assert engine.binding_count == 2
        assert engine.dependency_count == 1
        assert engine.decision_count == 1

        # State hash is stable
        h1 = engine.state_hash()
        h2 = engine.state_hash()
        assert h1 == h2
        assert len(h1) == 64


class TestBoundedContracts:
    def test_objective_and_program_contracts_do_not_reflect_ids(
        self, engine: ProgramRuntimeEngine
    ) -> None:
        engine.register_objective("obj-secret", "Revenue")
        with pytest.raises(RuntimeCoreInvariantError) as dup_obj_exc:
            engine.register_objective("obj-secret", "Revenue Again")
        dup_obj_message = str(dup_obj_exc.value)
        assert dup_obj_message == "objective already exists"
        assert "obj-secret" not in dup_obj_message
        assert "already exists" in dup_obj_message

        with pytest.raises(RuntimeCoreInvariantError) as missing_obj_exc:
            engine.update_objective_value("obj-missing", 42.0)
        missing_obj_message = str(missing_obj_exc.value)
        assert missing_obj_message == "objective not found"
        assert "obj-missing" not in missing_obj_message
        assert "not found" in missing_obj_message

        engine.register_program("prog-secret", "Launch")
        with pytest.raises(RuntimeCoreInvariantError) as dup_prog_exc:
            engine.register_program("prog-secret", "Launch Again")
        dup_prog_message = str(dup_prog_exc.value)
        assert dup_prog_message == "program already exists"
        assert "prog-secret" not in dup_prog_message
        assert "already exists" in dup_prog_message

    def test_initiative_milestone_and_decision_contracts_do_not_reflect_ids(
        self, engine: ProgramRuntimeEngine
    ) -> None:
        _seed_program(engine, obj_id="obj-secret", prog_id="prog-secret")
        engine.register_initiative("ini-secret", "prog-secret", "Initiative", objective_id="obj-secret")

        with pytest.raises(RuntimeCoreInvariantError) as dup_ini_exc:
            engine.register_initiative("ini-secret", "prog-secret", "Again", objective_id="obj-secret")
        dup_ini_message = str(dup_ini_exc.value)
        assert dup_ini_message == "initiative already exists"
        assert "ini-secret" not in dup_ini_message
        assert "already exists" in dup_ini_message

        with pytest.raises(RuntimeCoreInvariantError) as missing_ms_exc:
            engine.record_milestone_progress("ms-missing", 50.0)
        missing_ms_message = str(missing_ms_exc.value)
        assert missing_ms_message == "milestone not found"
        assert "ms-missing" not in missing_ms_message
        assert "not found" in missing_ms_message

        engine.record_decision("dec-secret", "Ship")
        with pytest.raises(RuntimeCoreInvariantError) as dup_dec_exc:
            engine.record_decision("dec-secret", "Ship Again")
        dup_dec_message = str(dup_dec_exc.value)
        assert dup_dec_message == "decision already exists"
        assert "dec-secret" not in dup_dec_message
        assert "already exists" in dup_dec_message
