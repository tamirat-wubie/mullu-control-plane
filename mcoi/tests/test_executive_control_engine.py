"""Tests for the executive control tower / strategic planning engine."""

import pytest

from mcoi_runtime.core.executive_control import ExecutiveControlEngine
from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
from mcoi_runtime.contracts.executive_control import (
    ControlTowerHealth,
    ControlTowerSnapshot,
    DirectiveStatus,
    DirectiveType,
    ExecutiveIntervention,
    InterventionSeverity,
    ObjectiveStatus,
    PortfolioDirectiveBinding,
    PriorityLevel,
    PriorityShift,
    ScenarioOutcome,
    ScenarioPlan,
    ScenarioStatus,
    StrategicDecision,
    StrategicDirective,
    StrategicObjective,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def es():
    return EventSpineEngine()


@pytest.fixture()
def engine(es):
    return ExecutiveControlEngine(es)


def _register_default_objective(engine, objective_id="obj-1", **kw):
    defaults = dict(
        title="Revenue growth",
        priority=PriorityLevel.P1_HIGH,
        target_kpi="revenue",
        target_value=100.0,
        current_value=80.0,
        tolerance_pct=10.0,
        owner="cto",
    )
    defaults.update(kw)
    return engine.register_objective(objective_id, **defaults)


def _issue_default_directive(engine, directive_id="dir-1", **kw):
    defaults = dict(
        title="Escalate ops",
        directive_type=DirectiveType.ESCALATE,
        objective_id="obj-1",
        reason="KPI off-track",
    )
    defaults.update(kw)
    return engine.issue_directive(directive_id, **defaults)


# ===================================================================
# TestConstructor
# ===================================================================


class TestConstructor:
    def test_valid_construction(self, es):
        eng = ExecutiveControlEngine(es)
        assert eng.objective_count == 0
        assert eng.directive_count == 0

    def test_invalid_type_raises(self):
        with pytest.raises(RuntimeCoreInvariantError):
            ExecutiveControlEngine("not-an-event-spine")

    def test_invalid_none_raises(self):
        with pytest.raises(RuntimeCoreInvariantError):
            ExecutiveControlEngine(None)


# ===================================================================
# TestObjectiveManagement
# ===================================================================


class TestObjectiveManagement:
    def test_register_objective(self, engine):
        obj = _register_default_objective(engine)
        assert isinstance(obj, StrategicObjective)
        assert obj.objective_id == "obj-1"
        assert obj.status == ObjectiveStatus.ACTIVE
        assert obj.priority == PriorityLevel.P1_HIGH
        assert obj.target_value == 100.0
        assert obj.current_value == 80.0
        assert obj.created_at != ""

    def test_get_objective(self, engine):
        _register_default_objective(engine)
        obj = engine.get_objective("obj-1")
        assert obj is not None
        assert obj.objective_id == "obj-1"

    def test_get_missing_returns_none(self, engine):
        assert engine.get_objective("nonexistent") is None

    def test_duplicate_raises(self, engine):
        _register_default_objective(engine)
        with pytest.raises(RuntimeCoreInvariantError, match="already exists"):
            _register_default_objective(engine)

    def test_update_kpi(self, engine):
        _register_default_objective(engine)
        updated = engine.update_objective_kpi("obj-1", 95.0)
        assert updated.current_value == 95.0
        assert updated.target_value == 100.0
        assert updated.updated_at != ""

    def test_update_kpi_missing_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError, match="not found"):
            engine.update_objective_kpi("nonexistent", 10.0)

    def test_set_status(self, engine):
        _register_default_objective(engine)
        updated = engine.set_objective_status("obj-1", ObjectiveStatus.PAUSED)
        assert updated.status == ObjectiveStatus.PAUSED

    def test_set_status_missing_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError, match="not found"):
            engine.set_objective_status("nonexistent", ObjectiveStatus.PAUSED)

    def test_register_with_scope_ref_ids(self, engine):
        obj = _register_default_objective(
            engine, scope_ref_ids=["scope-a", "scope-b"]
        )
        assert obj.scope_ref_ids == ("scope-a", "scope-b")

    def test_register_with_metadata(self, engine):
        obj = _register_default_objective(engine, metadata={"team": "alpha"})
        assert obj.metadata["team"] == "alpha"


# ===================================================================
# TestObjectiveHealth
# ===================================================================


class TestObjectiveHealth:
    def test_on_track(self, engine):
        _register_default_objective(engine, target_value=100.0, current_value=95.0, tolerance_pct=10.0)
        health = engine.check_objective_health("obj-1")
        assert health["on_track"] is True
        assert health["gap_pct"] == 5.0

    def test_off_track(self, engine):
        _register_default_objective(engine, target_value=100.0, current_value=50.0, tolerance_pct=10.0)
        health = engine.check_objective_health("obj-1")
        assert health["on_track"] is False
        assert health["gap_pct"] == 50.0

    def test_target_value_zero(self, engine):
        _register_default_objective(engine, target_value=0.0, current_value=0.0)
        health = engine.check_objective_health("obj-1")
        assert health["gap_pct"] == 0.0
        assert health["on_track"] is True

    def test_missing_objective_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError, match="not found"):
            engine.check_objective_health("nonexistent")

    def test_exact_tolerance_boundary(self, engine):
        # gap_pct == tolerance_pct => on_track (<=)
        _register_default_objective(engine, target_value=100.0, current_value=90.0, tolerance_pct=10.0)
        health = engine.check_objective_health("obj-1")
        assert health["on_track"] is True
        assert health["gap_pct"] == 10.0


# ===================================================================
# TestDirectiveLifecycle
# ===================================================================


class TestDirectiveLifecycle:
    def test_issue_directive(self, engine):
        _register_default_objective(engine)
        d = _issue_default_directive(engine)
        assert isinstance(d, StrategicDirective)
        assert d.status == DirectiveStatus.ISSUED
        assert d.directive_type == DirectiveType.ESCALATE
        assert d.issued_at != ""

    def test_get_directive(self, engine):
        _register_default_objective(engine)
        _issue_default_directive(engine)
        d = engine.get_directive("dir-1")
        assert d is not None
        assert d.directive_id == "dir-1"

    def test_get_missing_returns_none(self, engine):
        assert engine.get_directive("nonexistent") is None

    def test_duplicate_raises(self, engine):
        _register_default_objective(engine)
        _issue_default_directive(engine)
        with pytest.raises(RuntimeCoreInvariantError, match="already exists"):
            _issue_default_directive(engine)

    def test_acknowledge(self, engine):
        _register_default_objective(engine)
        _issue_default_directive(engine)
        acked = engine.acknowledge_directive("dir-1")
        assert acked.status == DirectiveStatus.ACKNOWLEDGED

    def test_acknowledge_non_issued_raises(self, engine):
        _register_default_objective(engine)
        _issue_default_directive(engine)
        engine.acknowledge_directive("dir-1")
        with pytest.raises(RuntimeCoreInvariantError, match="not in ISSUED"):
            engine.acknowledge_directive("dir-1")

    def test_execute_from_issued(self, engine):
        _register_default_objective(engine)
        _issue_default_directive(engine)
        executed = engine.execute_directive("dir-1")
        assert executed.status == DirectiveStatus.EXECUTED

    def test_execute_from_acknowledged(self, engine):
        _register_default_objective(engine)
        _issue_default_directive(engine)
        engine.acknowledge_directive("dir-1")
        executed = engine.execute_directive("dir-1")
        assert executed.status == DirectiveStatus.EXECUTED

    def test_execute_from_wrong_state_raises(self, engine):
        _register_default_objective(engine)
        _issue_default_directive(engine)
        engine.execute_directive("dir-1")
        with pytest.raises(RuntimeCoreInvariantError, match="cannot be executed"):
            engine.execute_directive("dir-1")

    def test_reject(self, engine):
        _register_default_objective(engine)
        _issue_default_directive(engine)
        rejected = engine.reject_directive("dir-1", reason="Not viable")
        assert rejected.status == DirectiveStatus.REJECTED

    def test_execute_rejected_raises(self, engine):
        _register_default_objective(engine)
        _issue_default_directive(engine)
        engine.reject_directive("dir-1")
        with pytest.raises(RuntimeCoreInvariantError, match="cannot be executed"):
            engine.execute_directive("dir-1")


# ===================================================================
# TestPriorityShifts
# ===================================================================


class TestPriorityShifts:
    def test_create_shift(self, engine):
        _register_default_objective(engine)
        _issue_default_directive(engine)
        shift = engine.shift_priority(
            "shift-1", "dir-1", "scope-a",
            PriorityLevel.P3_LOW, PriorityLevel.P1_HIGH,
            reason="Escalation needed",
        )
        assert isinstance(shift, PriorityShift)
        assert shift.shift_id == "shift-1"
        assert shift.from_priority == PriorityLevel.P3_LOW
        assert shift.to_priority == PriorityLevel.P1_HIGH
        assert shift.shifted_at != ""

    def test_get_priority_shifts(self, engine):
        _register_default_objective(engine)
        _issue_default_directive(engine)
        engine.shift_priority(
            "shift-1", "dir-1", "scope-a",
            PriorityLevel.P3_LOW, PriorityLevel.P1_HIGH,
        )
        engine.shift_priority(
            "shift-2", "dir-1", "scope-b",
            PriorityLevel.P2_MEDIUM, PriorityLevel.P0_CRITICAL,
        )
        shifts = engine.get_priority_shifts()
        assert isinstance(shifts, tuple)
        assert len(shifts) == 2
        assert shifts[0].shift_id == "shift-1"
        assert shifts[1].shift_id == "shift-2"

    def test_priority_shift_count(self, engine):
        assert engine.priority_shift_count == 0
        _register_default_objective(engine)
        _issue_default_directive(engine)
        engine.shift_priority(
            "shift-1", "dir-1", "scope-a",
            PriorityLevel.P3_LOW, PriorityLevel.P1_HIGH,
        )
        assert engine.priority_shift_count == 1


# ===================================================================
# TestScenarioPlanning
# ===================================================================


class TestScenarioPlanning:
    def test_create_scenario(self, engine):
        sc = engine.create_scenario("sc-1", "Budget what-if", objective_id="obj-1")
        assert isinstance(sc, ScenarioPlan)
        assert sc.status == ScenarioStatus.DRAFT
        assert sc.scenario_id == "sc-1"
        assert sc.created_at != ""

    def test_duplicate_raises(self, engine):
        engine.create_scenario("sc-1", "Budget what-if")
        with pytest.raises(RuntimeCoreInvariantError, match="already exists"):
            engine.create_scenario("sc-1", "Another")

    def test_run_scenario(self, engine):
        engine.create_scenario("sc-1", "Budget what-if")
        running = engine.run_scenario("sc-1")
        assert running.status == ScenarioStatus.RUNNING

    def test_run_non_draft_raises(self, engine):
        engine.create_scenario("sc-1", "Budget what-if")
        engine.run_scenario("sc-1")
        with pytest.raises(RuntimeCoreInvariantError, match="not in DRAFT"):
            engine.run_scenario("sc-1")

    def test_complete_scenario(self, engine):
        engine.create_scenario("sc-1", "Budget what-if")
        engine.run_scenario("sc-1")
        completed = engine.complete_scenario(
            "sc-1",
            projected_snapshot={"revenue": 120},
            confidence=0.85,
            risk_score=0.1,
        )
        assert completed.status == ScenarioStatus.COMPLETED
        assert completed.confidence == 0.85
        assert completed.risk_score == 0.1
        assert completed.projected_snapshot["revenue"] == 120
        assert completed.completed_at != ""

    def test_complete_non_running_raises(self, engine):
        engine.create_scenario("sc-1", "Budget what-if")
        with pytest.raises(RuntimeCoreInvariantError, match="not RUNNING"):
            engine.complete_scenario("sc-1")

    def test_assess_scenario(self, engine):
        engine.create_scenario("sc-1", "Budget what-if")
        engine.run_scenario("sc-1")
        engine.complete_scenario("sc-1")
        outcome = engine.assess_scenario(
            "out-1", "sc-1", "FAVORABLE",
            projected_improvement_pct=15.0,
            projected_risk_delta=-0.05,
            recommendation="Proceed with reallocation",
        )
        assert isinstance(outcome, ScenarioOutcome)
        assert outcome.verdict == "FAVORABLE"
        assert outcome.projected_improvement_pct == 15.0

    def test_assess_missing_scenario_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError, match="not found"):
            engine.assess_scenario("out-1", "nonexistent", "BAD")

    def test_get_scenario(self, engine):
        engine.create_scenario("sc-1", "Budget what-if")
        assert engine.get_scenario("sc-1") is not None
        assert engine.get_scenario("nonexistent") is None

    def test_get_scenario_outcome(self, engine):
        engine.create_scenario("sc-1", "Budget what-if")
        engine.run_scenario("sc-1")
        engine.complete_scenario("sc-1")
        engine.assess_scenario("out-1", "sc-1", "FAVORABLE")
        assert engine.get_scenario_outcome("out-1") is not None
        assert engine.get_scenario_outcome("nonexistent") is None


# ===================================================================
# TestInterventions
# ===================================================================


class TestInterventions:
    def test_create_intervention(self, engine):
        _register_default_objective(engine)
        _issue_default_directive(engine)
        iv = engine.intervene(
            "iv-1", "dir-1", "halt_loop",
            severity=InterventionSeverity.HIGH,
            target_engine="autonomous_loop",
            reason="KPI critically off-track",
        )
        assert isinstance(iv, ExecutiveIntervention)
        assert iv.intervention_id == "iv-1"
        assert iv.severity == InterventionSeverity.HIGH
        assert iv.resolved_at == ""
        assert iv.intervened_at != ""

    def test_duplicate_raises(self, engine):
        _register_default_objective(engine)
        _issue_default_directive(engine)
        engine.intervene("iv-1", "dir-1", "halt_loop")
        with pytest.raises(RuntimeCoreInvariantError, match="already exists"):
            engine.intervene("iv-1", "dir-1", "halt_loop")

    def test_resolve_intervention(self, engine):
        _register_default_objective(engine)
        _issue_default_directive(engine)
        engine.intervene("iv-1", "dir-1", "halt_loop")
        resolved = engine.resolve_intervention("iv-1")
        assert resolved.resolved_at != ""

    def test_resolve_missing_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError, match="not found"):
            engine.resolve_intervention("nonexistent")

    def test_get_intervention(self, engine):
        _register_default_objective(engine)
        _issue_default_directive(engine)
        engine.intervene("iv-1", "dir-1", "halt_loop")
        assert engine.get_intervention("iv-1") is not None
        assert engine.get_intervention("nonexistent") is None


# ===================================================================
# TestDecisions
# ===================================================================


class TestDecisions:
    def test_record_decision(self, engine):
        dec = engine.record_decision(
            "dec-1", "Approve reallocation",
            objective_id="obj-1",
            directive_ids=["dir-1", "dir-2"],
            rationale="Budget analysis supports this",
            confidence=0.9,
            risk_score=0.15,
        )
        assert isinstance(dec, StrategicDecision)
        assert dec.decision_id == "dec-1"
        assert dec.confidence == 0.9
        assert dec.risk_score == 0.15
        assert dec.directive_ids == ("dir-1", "dir-2")
        assert dec.decided_at != ""

    def test_duplicate_raises(self, engine):
        engine.record_decision("dec-1", "First decision")
        with pytest.raises(RuntimeCoreInvariantError, match="already exists"):
            engine.record_decision("dec-1", "Duplicate")

    def test_get_decision(self, engine):
        engine.record_decision("dec-1", "Approve reallocation")
        assert engine.get_decision("dec-1") is not None
        assert engine.get_decision("nonexistent") is None


# ===================================================================
# TestPortfolioBindings
# ===================================================================


class TestPortfolioBindings:
    def test_bind_directive(self, engine):
        _register_default_objective(engine)
        _issue_default_directive(engine)
        binding = engine.bind_directive_to_portfolio(
            "bind-1", "dir-1",
            portfolio_ref_id="portfolio-alpha",
            effect="budget_increase",
        )
        assert isinstance(binding, PortfolioDirectiveBinding)
        assert binding.binding_id == "bind-1"
        assert binding.directive_id == "dir-1"
        assert binding.portfolio_ref_id == "portfolio-alpha"
        assert binding.bound_at != ""

    def test_missing_directive_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError, match="not found"):
            engine.bind_directive_to_portfolio("bind-1", "nonexistent")

    def test_get_bindings(self, engine):
        _register_default_objective(engine)
        _issue_default_directive(engine)
        engine.bind_directive_to_portfolio("bind-1", "dir-1", portfolio_ref_id="p1")
        engine.bind_directive_to_portfolio("bind-2", "dir-1", portfolio_ref_id="p2")
        bindings = engine.get_bindings()
        assert isinstance(bindings, tuple)
        assert len(bindings) == 2


# ===================================================================
# TestSnapshots
# ===================================================================


class TestSnapshots:
    def test_healthy_snapshot(self, engine):
        _register_default_objective(engine)
        snap = engine.capture_snapshot("snap-1")
        assert isinstance(snap, ControlTowerSnapshot)
        assert snap.health == ControlTowerHealth.HEALTHY
        assert snap.active_objectives == 1
        assert snap.interventions_in_progress == 0

    def test_degraded_snapshot(self, engine):
        _register_default_objective(engine)
        _issue_default_directive(engine)
        engine.intervene("iv-1", "dir-1", "halt_loop", severity=InterventionSeverity.MEDIUM)
        snap = engine.capture_snapshot("snap-1")
        assert snap.health == ControlTowerHealth.DEGRADED
        assert snap.interventions_in_progress == 1

    def test_critical_snapshot(self, engine):
        _register_default_objective(engine)
        _issue_default_directive(engine)
        engine.intervene(
            "iv-1", "dir-1", "emergency_halt",
            severity=InterventionSeverity.CRITICAL,
        )
        snap = engine.capture_snapshot("snap-1")
        assert snap.health == ControlTowerHealth.CRITICAL
        assert snap.interventions_in_progress == 1

    def test_resolved_intervention_restores_healthy(self, engine):
        _register_default_objective(engine)
        _issue_default_directive(engine)
        engine.intervene("iv-1", "dir-1", "halt_loop", severity=InterventionSeverity.HIGH)
        engine.resolve_intervention("iv-1")
        snap = engine.capture_snapshot("snap-1")
        assert snap.health == ControlTowerHealth.HEALTHY
        assert snap.interventions_in_progress == 0

    def test_snapshot_counts(self, engine):
        _register_default_objective(engine)
        _issue_default_directive(engine)
        engine.create_scenario("sc-1", "What-if")
        engine.shift_priority(
            "shift-1", "dir-1", "scope-a",
            PriorityLevel.P3_LOW, PriorityLevel.P1_HIGH,
        )
        engine.record_decision("dec-1", "Decision alpha")
        snap = engine.capture_snapshot("snap-1")
        assert snap.active_objectives == 1
        assert snap.active_directives == 1
        assert snap.pending_scenarios == 1
        assert snap.total_priority_shifts == 1
        assert snap.total_decisions == 1


# ===================================================================
# TestProperties
# ===================================================================


class TestProperties:
    def test_counts_start_at_zero(self, engine):
        assert engine.objective_count == 0
        assert engine.directive_count == 0
        assert engine.scenario_count == 0
        assert engine.intervention_count == 0
        assert engine.decision_count == 0
        assert engine.priority_shift_count == 0
        assert engine.binding_count == 0

    def test_counts_increment(self, engine):
        _register_default_objective(engine)
        assert engine.objective_count == 1

        _issue_default_directive(engine)
        assert engine.directive_count == 1

        engine.create_scenario("sc-1", "Test")
        assert engine.scenario_count == 1

        engine.intervene("iv-1", "dir-1", "halt")
        assert engine.intervention_count == 1

        engine.record_decision("dec-1", "Test decision")
        assert engine.decision_count == 1

        engine.shift_priority(
            "shift-1", "dir-1", "scope-a",
            PriorityLevel.P2_MEDIUM, PriorityLevel.P0_CRITICAL,
        )
        assert engine.priority_shift_count == 1

        engine.bind_directive_to_portfolio("bind-1", "dir-1")
        assert engine.binding_count == 1


# ===================================================================
# TestStateHash
# ===================================================================


class TestStateHash:
    def test_deterministic(self, engine):
        _register_default_objective(engine)
        h1 = engine.state_hash()
        h2 = engine.state_hash()
        assert h1 == h2
        assert isinstance(h1, str)
        assert len(h1) > 0

    def test_changes_after_mutation(self, engine):
        _register_default_objective(engine)
        h1 = engine.state_hash()
        _issue_default_directive(engine)
        h2 = engine.state_hash()
        assert h1 != h2

    def test_changes_after_status_update(self, engine):
        _register_default_objective(engine)
        h1 = engine.state_hash()
        engine.set_objective_status("obj-1", ObjectiveStatus.PAUSED)
        h2 = engine.state_hash()
        assert h1 != h2

    def test_state_hash_is_method(self, engine):
        # Verify state_hash is callable (method, not property)
        assert callable(engine.state_hash)


# ===================================================================
# TestEventEmission
# ===================================================================


class TestEventEmission:
    def test_register_objective_emits(self, es, engine):
        initial = es.event_count
        _register_default_objective(engine)
        assert es.event_count > initial

    def test_issue_directive_emits(self, es, engine):
        _register_default_objective(engine)
        initial = es.event_count
        _issue_default_directive(engine)
        assert es.event_count > initial

    def test_acknowledge_emits(self, es, engine):
        _register_default_objective(engine)
        _issue_default_directive(engine)
        initial = es.event_count
        engine.acknowledge_directive("dir-1")
        assert es.event_count > initial

    def test_execute_emits(self, es, engine):
        _register_default_objective(engine)
        _issue_default_directive(engine)
        initial = es.event_count
        engine.execute_directive("dir-1")
        assert es.event_count > initial

    def test_shift_priority_emits(self, es, engine):
        _register_default_objective(engine)
        _issue_default_directive(engine)
        initial = es.event_count
        engine.shift_priority(
            "shift-1", "dir-1", "scope-a",
            PriorityLevel.P3_LOW, PriorityLevel.P1_HIGH,
        )
        assert es.event_count > initial

    def test_scenario_lifecycle_emits(self, es, engine):
        initial = es.event_count
        engine.create_scenario("sc-1", "Test")
        assert es.event_count > initial
        c1 = es.event_count
        engine.run_scenario("sc-1")
        assert es.event_count > c1
        c2 = es.event_count
        engine.complete_scenario("sc-1")
        assert es.event_count > c2

    def test_intervention_emits(self, es, engine):
        _register_default_objective(engine)
        _issue_default_directive(engine)
        initial = es.event_count
        engine.intervene("iv-1", "dir-1", "halt")
        assert es.event_count > initial
        c1 = es.event_count
        engine.resolve_intervention("iv-1")
        assert es.event_count > c1

    def test_decision_emits(self, es, engine):
        initial = es.event_count
        engine.record_decision("dec-1", "Test decision")
        assert es.event_count > initial

    def test_snapshot_emits(self, es, engine):
        initial = es.event_count
        engine.capture_snapshot("snap-1")
        assert es.event_count > initial

    def test_binding_emits(self, es, engine):
        _register_default_objective(engine)
        _issue_default_directive(engine)
        initial = es.event_count
        engine.bind_directive_to_portfolio("bind-1", "dir-1")
        assert es.event_count > initial


# ===================================================================
# Golden Scenarios
# ===================================================================


class TestGoldenScenario1_DegradingKPI:
    """Degrading KPI -> update objective -> check health off-track ->
    issue escalation directive -> intervention -> resolve."""

    def test_full_flow(self, engine):
        # Register objective with KPI on-track
        _register_default_objective(engine, target_value=100.0, current_value=92.0, tolerance_pct=10.0)
        health = engine.check_objective_health("obj-1")
        assert health["on_track"] is True

        # KPI degrades
        engine.update_objective_kpi("obj-1", 60.0)
        health = engine.check_objective_health("obj-1")
        assert health["on_track"] is False
        assert health["gap_pct"] == 40.0

        # Issue escalation directive
        directive = engine.issue_directive(
            "dir-escalate", "Escalate revenue shortfall",
            DirectiveType.ESCALATE,
            objective_id="obj-1",
            reason="Revenue 40% off target",
        )
        assert directive.status == DirectiveStatus.ISSUED

        # Intervene to halt autonomous loop
        iv = engine.intervene(
            "iv-halt", "dir-escalate", "halt_autonomous_loop",
            severity=InterventionSeverity.HIGH,
            target_engine="optimizer",
            reason="Manual review required",
        )
        assert iv.resolved_at == ""

        # Resolve after manual review
        resolved = engine.resolve_intervention("iv-halt")
        assert resolved.resolved_at != ""

        # Snapshot should be healthy after resolution
        snap = engine.capture_snapshot("snap-post-resolve")
        assert snap.health == ControlTowerHealth.HEALTHY


class TestGoldenScenario2_ReprioritizeTwoPortfolios:
    """Strategic objective reprioritizes two portfolios via directives
    and priority shifts."""

    def test_full_flow(self, engine):
        _register_default_objective(engine, objective_id="obj-strategic")

        # Issue directive to reprioritize
        d = engine.issue_directive(
            "dir-reprioritize", "Reprioritize portfolios",
            DirectiveType.PRIORITY_SHIFT,
            objective_id="obj-strategic",
            reason="Market conditions changed",
        )
        assert d.status == DirectiveStatus.ISSUED

        # Shift portfolio A from LOW to HIGH
        s1 = engine.shift_priority(
            "shift-a", "dir-reprioritize", "portfolio-a",
            PriorityLevel.P3_LOW, PriorityLevel.P1_HIGH,
            reason="Revenue focus",
        )
        assert s1.from_priority == PriorityLevel.P3_LOW
        assert s1.to_priority == PriorityLevel.P1_HIGH

        # Shift portfolio B from HIGH to LOW
        s2 = engine.shift_priority(
            "shift-b", "dir-reprioritize", "portfolio-b",
            PriorityLevel.P1_HIGH, PriorityLevel.P3_LOW,
            reason="De-emphasize expansion",
        )
        assert s2.from_priority == PriorityLevel.P1_HIGH
        assert s2.to_priority == PriorityLevel.P3_LOW

        shifts = engine.get_priority_shifts()
        assert len(shifts) == 2

        # Execute the directive
        executed = engine.execute_directive("dir-reprioritize")
        assert executed.status == DirectiveStatus.EXECUTED


class TestGoldenScenario3_BudgetReallocation:
    """Budget reallocation directive -> bind to portfolio -> execute."""

    def test_full_flow(self, engine):
        _register_default_objective(engine)

        d = engine.issue_directive(
            "dir-budget", "Reallocate Q3 budget",
            DirectiveType.BUDGET_REALLOCATION,
            objective_id="obj-1",
            reason="Underperforming campaign",
            parameters={"amount": 50000, "from": "campaign-old", "to": "campaign-new"},
        )
        assert d.status == DirectiveStatus.ISSUED

        # Bind to portfolio
        binding = engine.bind_directive_to_portfolio(
            "bind-budget", "dir-budget",
            portfolio_ref_id="portfolio-main",
            campaign_ref_id="campaign-new",
            effect="budget_increase",
        )
        assert binding.portfolio_ref_id == "portfolio-main"

        # Acknowledge then execute
        engine.acknowledge_directive("dir-budget")
        executed = engine.execute_directive("dir-budget")
        assert executed.status == DirectiveStatus.EXECUTED

        bindings = engine.get_bindings()
        assert len(bindings) == 1
        assert bindings[0].binding_id == "bind-budget"


class TestGoldenScenario4_InterventionHaltsAutonomousLoop:
    """Executive intervention halts autonomous loop -> resolve intervention."""

    def test_full_flow(self, engine):
        _register_default_objective(engine)
        d = engine.issue_directive(
            "dir-halt", "Halt autonomous optimization",
            DirectiveType.HALT_AUTONOMOUS,
            objective_id="obj-1",
            reason="Anomalous behavior detected",
        )

        # Intervene with CRITICAL severity
        iv = engine.intervene(
            "iv-critical", "dir-halt", "emergency_stop",
            severity=InterventionSeverity.CRITICAL,
            target_engine="autonomous_optimizer",
            reason="Immediate halt required",
        )
        assert iv.severity == InterventionSeverity.CRITICAL

        # Snapshot should be CRITICAL
        snap = engine.capture_snapshot("snap-during")
        assert snap.health == ControlTowerHealth.CRITICAL

        # Resolve
        engine.resolve_intervention("iv-critical")

        # Snapshot should be HEALTHY
        snap2 = engine.capture_snapshot("snap-after")
        assert snap2.health == ControlTowerHealth.HEALTHY


class TestGoldenScenario5_ScenarioPlanToDecision:
    """Scenario plan -> run -> complete -> assess outcome -> record decision."""

    def test_full_flow(self, engine):
        _register_default_objective(engine)

        # Create and run scenario
        sc = engine.create_scenario(
            "sc-budget", "Budget reallocation impact",
            objective_id="obj-1",
            baseline_snapshot={"revenue": 80, "cost": 50},
            assumptions=["Market stable", "No competitor entry"],
        )
        assert sc.status == ScenarioStatus.DRAFT

        running = engine.run_scenario("sc-budget")
        assert running.status == ScenarioStatus.RUNNING

        # Complete with projections
        completed = engine.complete_scenario(
            "sc-budget",
            projected_snapshot={"revenue": 110, "cost": 55},
            confidence=0.85,
            risk_score=0.15,
        )
        assert completed.status == ScenarioStatus.COMPLETED
        assert completed.confidence == 0.85

        # Assess outcome
        outcome = engine.assess_scenario(
            "out-budget", "sc-budget", "FAVORABLE",
            projected_improvement_pct=37.5,
            projected_risk_delta=-0.1,
            recommendation="Proceed with budget reallocation",
        )
        assert outcome.verdict == "FAVORABLE"
        assert outcome.projected_improvement_pct == 37.5

        # Record strategic decision
        dec = engine.record_decision(
            "dec-budget", "Approve Q3 budget reallocation",
            objective_id="obj-1",
            directive_ids=["dir-budget-exec"],
            rationale="Scenario analysis shows 37.5% improvement",
            confidence=0.9,
            risk_score=0.1,
        )
        assert dec.confidence == 0.9
        assert dec.directive_ids == ("dir-budget-exec",)


class TestGoldenScenario6_FullLifecycle:
    """Full lifecycle: objective -> directive -> bind -> shift ->
    scenario -> intervene -> decision -> snapshot."""

    def test_full_flow(self, engine):
        # 1. Register objective
        obj = _register_default_objective(engine, objective_id="obj-main")
        assert obj.status == ObjectiveStatus.ACTIVE

        # 2. Issue directive
        d = engine.issue_directive(
            "dir-main", "Master reallocation",
            DirectiveType.BUDGET_REALLOCATION,
            objective_id="obj-main",
            reason="Strategic pivot",
        )
        assert d.status == DirectiveStatus.ISSUED

        # 3. Bind directive to portfolio
        binding = engine.bind_directive_to_portfolio(
            "bind-main", "dir-main",
            portfolio_ref_id="portfolio-primary",
            effect="rebalance",
        )
        assert binding.directive_id == "dir-main"

        # 4. Priority shift
        shift = engine.shift_priority(
            "shift-main", "dir-main", "portfolio-primary",
            PriorityLevel.P2_MEDIUM, PriorityLevel.P0_CRITICAL,
            reason="Strategic pivot requires critical priority",
        )
        assert shift.to_priority == PriorityLevel.P0_CRITICAL

        # 5. Scenario planning
        engine.create_scenario(
            "sc-main", "Pivot impact analysis",
            objective_id="obj-main",
            baseline_snapshot={"revenue": 80},
        )
        engine.run_scenario("sc-main")
        engine.complete_scenario(
            "sc-main",
            projected_snapshot={"revenue": 120},
            confidence=0.8,
        )

        # 6. Intervene (temporarily)
        engine.intervene(
            "iv-main", "dir-main", "pause_operations",
            severity=InterventionSeverity.MEDIUM,
            target_engine="campaign_engine",
            reason="Awaiting scenario outcome",
        )

        # 7. Snapshot mid-intervention: DEGRADED
        snap_mid = engine.capture_snapshot("snap-mid")
        assert snap_mid.health == ControlTowerHealth.DEGRADED
        assert snap_mid.active_objectives == 1
        assert snap_mid.active_directives == 1
        assert snap_mid.pending_scenarios == 0  # completed
        assert snap_mid.interventions_in_progress == 1
        assert snap_mid.total_priority_shifts == 1

        # 8. Resolve intervention
        engine.resolve_intervention("iv-main")

        # 9. Assess scenario and record decision
        engine.assess_scenario(
            "out-main", "sc-main", "FAVORABLE",
            projected_improvement_pct=50.0,
            recommendation="Full pivot approved",
        )
        engine.record_decision(
            "dec-main", "Approve strategic pivot",
            objective_id="obj-main",
            directive_ids=["dir-main"],
            rationale="Scenario analysis favorable, intervention resolved",
            confidence=0.85,
            risk_score=0.1,
        )

        # 10. Execute directive
        engine.execute_directive("dir-main")

        # 11. Final snapshot: HEALTHY
        snap_final = engine.capture_snapshot("snap-final")
        assert snap_final.health == ControlTowerHealth.HEALTHY
        assert snap_final.interventions_in_progress == 0
        assert snap_final.total_decisions == 1
        assert snap_final.active_directives == 0  # executed, no longer active

        # Verify all counts
        assert engine.objective_count == 1
        assert engine.directive_count == 1
        assert engine.scenario_count == 1
        assert engine.intervention_count == 1
        assert engine.decision_count == 1
        assert engine.priority_shift_count == 1
        assert engine.binding_count == 1
