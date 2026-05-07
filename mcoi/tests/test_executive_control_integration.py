"""Integration tests for ExecutiveControlIntegration.

Covers constructor validation, each control_from_* method, issue_*_shift
helpers, memory mesh attachment, graph attachment, event emission, and
six golden scenarios that exercise end-to-end executive control paths.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.core.executive_control_integration import ExecutiveControlIntegration
from mcoi_runtime.core.executive_control import ExecutiveControlEngine
from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.memory_mesh import MemoryMeshEngine
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
from mcoi_runtime.contracts.executive_control import (
    ControlTowerHealth,
    DirectiveStatus,
    DirectiveType,
    InterventionSeverity,
    ObjectiveStatus,
    PriorityLevel,
    ScenarioStatus,
)
from mcoi_runtime.contracts.memory_mesh import MemoryRecord


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def engines():
    """Return (event_spine, control_engine, memory_engine) tuple."""
    es = EventSpineEngine()
    eng = ExecutiveControlEngine(event_spine=es)
    mem = MemoryMeshEngine()
    return es, eng, mem


@pytest.fixture()
def integration(engines):
    """Return a fully-wired ExecutiveControlIntegration."""
    es, eng, mem = engines
    return ExecutiveControlIntegration(eng, es, mem)


@pytest.fixture()
def integration_with_engines(engines):
    """Return (integration, control_engine, event_spine, memory_engine)."""
    es, eng, mem = engines
    eci = ExecutiveControlIntegration(eng, es, mem)
    return eci, eng, es, mem


# ---------------------------------------------------------------------------
# TestConstructor
# ---------------------------------------------------------------------------


class TestConstructor:
    """Constructor type-checks every argument."""

    def test_valid_construction(self, engines):
        es, eng, mem = engines
        eci = ExecutiveControlIntegration(eng, es, mem)
        assert eci is not None

    def test_invalid_control_engine_raises(self, engines):
        es, _, mem = engines
        with pytest.raises(RuntimeCoreInvariantError, match="control_engine"):
            ExecutiveControlIntegration("not-an-engine", es, mem)

    def test_invalid_event_spine_raises(self, engines):
        _, eng, mem = engines
        with pytest.raises(RuntimeCoreInvariantError, match="event_spine"):
            ExecutiveControlIntegration(eng, "not-a-spine", mem)

    def test_invalid_memory_engine_raises(self, engines):
        es, eng, _ = engines
        with pytest.raises(RuntimeCoreInvariantError, match="memory_engine"):
            ExecutiveControlIntegration(eng, es, "not-a-memory")

    def test_none_arguments_raise(self):
        with pytest.raises(RuntimeCoreInvariantError):
            ExecutiveControlIntegration(None, None, None)


# ---------------------------------------------------------------------------
# TestControlFromReporting
# ---------------------------------------------------------------------------


class TestControlFromReporting:
    """control_from_reporting updates KPI, checks health, auto-issues directive."""

    def test_on_track_no_directive(self, integration_with_engines):
        eci, eng, es, mem = integration_with_engines
        eng.register_objective(
            "obj-1", "Revenue Target",
            target_value=1000.0, current_value=980.0, tolerance_pct=5.0,
        )
        result = eci.control_from_reporting("obj-1", 960.0)
        assert result["objective_id"] == "obj-1"
        assert result["current_value"] == 960.0
        assert result["target_value"] == 1000.0
        # gap = (1000-960)/1000*100 = 4.0% <= 5.0% tolerance
        assert result["on_track"] is True
        assert result["directive_issued"] is False
        assert result["directive_id"] is None

    def test_off_track_auto_directive(self, integration_with_engines):
        eci, eng, es, mem = integration_with_engines
        eng.register_objective(
            "obj-2", "Revenue Target",
            target_value=1000.0, current_value=900.0, tolerance_pct=5.0,
        )
        result = eci.control_from_reporting("obj-2", 800.0)
        # gap = (1000-800)/1000*100 = 20% > 5% tolerance
        assert result["on_track"] is False
        assert result["directive_issued"] is True
        assert result["directive_id"] == "dir-rpt-obj-2"
        assert result["gap_pct"] == pytest.approx(20.0)
        directive = eng.get_directive("dir-rpt-obj-2")
        assert directive is not None
        assert directive.title == "KPI degraded"
        assert directive.reason == "objective gap exceeds tolerance"
        assert "obj-2" not in directive.title
        assert "20.0" not in directive.reason
        assert "5.0" not in directive.reason

    def test_repeated_off_track_does_not_fail(self, integration_with_engines):
        """Second call catches RuntimeCoreInvariantError for duplicate directive."""
        eci, eng, es, mem = integration_with_engines
        eng.register_objective(
            "obj-3", "Conv Rate",
            target_value=1000.0, current_value=900.0, tolerance_pct=5.0,
        )
        first = eci.control_from_reporting("obj-3", 800.0)
        assert first["directive_issued"] is True

        # Second update still off-track, but directive already exists
        second = eci.control_from_reporting("obj-3", 750.0)
        # Should not raise; directive_id is None because duplicate was caught
        assert second["on_track"] is False
        assert second["directive_issued"] is False
        assert second["directive_id"] is None

    def test_auto_directive_disabled(self, integration_with_engines):
        eci, eng, es, mem = integration_with_engines
        eng.register_objective(
            "obj-4", "Target",
            target_value=1000.0, current_value=500.0, tolerance_pct=5.0,
        )
        result = eci.control_from_reporting("obj-4", 400.0, auto_directive=False)
        assert result["on_track"] is False
        assert result["directive_issued"] is False
        assert result["directive_id"] is None


# ---------------------------------------------------------------------------
# TestControlFromFinancials
# ---------------------------------------------------------------------------


class TestControlFromFinancials:
    """control_from_financials issues BUDGET_REALLOCATION directive."""

    def test_basic_budget_reallocation(self, integration):
        result = integration.control_from_financials(
            "dir-fin-1", "Reallocate Q4 budget",
            budget_delta=-5000.0,
            target_scope_ref_id="campaign-set-low",
            reason="underperforming campaigns",
        )
        assert result["directive_id"] == "dir-fin-1"
        assert result["source"] == "financials"
        assert result["directive_type"] == DirectiveType.BUDGET_REALLOCATION.value
        assert result["budget_delta"] == -5000.0
        assert result["target_scope_ref_id"] == "campaign-set-low"

    def test_positive_budget_delta(self, integration):
        result = integration.control_from_financials(
            "dir-fin-2", "Boost budget",
            budget_delta=10000.0,
            target_scope_ref_id="campaign-high",
        )
        assert result["budget_delta"] == 10000.0


# ---------------------------------------------------------------------------
# TestControlFromPortfolio
# ---------------------------------------------------------------------------


class TestControlFromPortfolio:
    """control_from_portfolio issues PRIORITY_SHIFT directive + shift."""

    def test_creates_directive_and_shift(self, integration):
        result = integration.control_from_portfolio(
            "dir-port-1", "Reprioritize portfolio A",
            target_scope_ref_id="portfolio-a",
            from_priority=PriorityLevel.P3_LOW,
            to_priority=PriorityLevel.P1_HIGH,
            reason="strategic pivot",
        )
        assert result["directive_id"] == "dir-port-1"
        assert result["source"] == "portfolio"
        assert result["directive_type"] == DirectiveType.PRIORITY_SHIFT.value
        assert result["shift_id"] == "dir-port-1-shift"
        assert result["from_priority"] == PriorityLevel.P3_LOW.value
        assert result["to_priority"] == PriorityLevel.P1_HIGH.value
        assert result["target_scope_ref_id"] == "portfolio-a"

    def test_default_priorities(self, integration):
        result = integration.control_from_portfolio(
            "dir-port-2", "Default shift",
        )
        assert result["from_priority"] == PriorityLevel.P3_LOW.value
        assert result["to_priority"] == PriorityLevel.P1_HIGH.value


# ---------------------------------------------------------------------------
# TestControlFromFaults
# ---------------------------------------------------------------------------


class TestControlFromFaults:
    """control_from_faults issues ESCALATE directive + intervention."""

    def test_creates_directive_and_intervention(self, integration):
        result = integration.control_from_faults(
            "dir-fault-1", "Critical fault detected",
            target_scope_ref_id="campaign-x",
            severity=InterventionSeverity.CRITICAL,
            reason="SLA breach",
        )
        assert result["directive_id"] == "dir-fault-1"
        assert result["source"] == "faults"
        assert result["directive_type"] == DirectiveType.ESCALATE.value
        assert result["intervention_id"] == "dir-fault-1-int"
        assert result["severity"] == InterventionSeverity.CRITICAL.value

    def test_default_severity_is_high(self, integration):
        result = integration.control_from_faults(
            "dir-fault-2", "Fault escalation",
        )
        assert result["severity"] == InterventionSeverity.HIGH.value


# ---------------------------------------------------------------------------
# TestControlFromAutonomousImprovement
# ---------------------------------------------------------------------------


class TestControlFromAutonomousImprovement:
    """control_from_autonomous_improvement halts unsafe autonomous loops."""

    def test_halts_loop(self, integration):
        result = integration.control_from_autonomous_improvement(
            "dir-auto-1", "Halt runaway optimization",
            target_scope_ref_id="auto-loop-7",
            severity=InterventionSeverity.CRITICAL,
            reason="unbounded cost increase",
        )
        assert result["directive_id"] == "dir-auto-1"
        assert result["source"] == "autonomous_improvement"
        assert result["directive_type"] == DirectiveType.HALT_AUTONOMOUS.value
        assert result["intervention_id"] == "dir-auto-1-int"
        assert result["severity"] == InterventionSeverity.CRITICAL.value

    def test_default_severity_is_high(self, integration):
        result = integration.control_from_autonomous_improvement(
            "dir-auto-2", "Halt loop",
        )
        assert result["severity"] == InterventionSeverity.HIGH.value


# ---------------------------------------------------------------------------
# TestIssuePriorityShift
# ---------------------------------------------------------------------------


class TestIssuePriorityShift:
    """issue_priority_shift creates directive, shift, and executes."""

    def test_creates_and_executes(self, integration_with_engines):
        eci, eng, es, mem = integration_with_engines
        result = eci.issue_priority_shift(
            "dir-ps-1", "Shift campaign priority",
            "scope-abc",
            PriorityLevel.P3_LOW, PriorityLevel.P0_CRITICAL,
            reason="urgent strategic need",
        )
        assert result["directive_id"] == "dir-ps-1"
        assert result["shift_id"] == "dir-ps-1-shift"
        assert result["from_priority"] == PriorityLevel.P3_LOW.value
        assert result["to_priority"] == PriorityLevel.P0_CRITICAL.value

        # Verify directive was executed
        directive = eng.get_directive("dir-ps-1")
        assert directive is not None
        assert directive.status == DirectiveStatus.EXECUTED


# ---------------------------------------------------------------------------
# TestIssueBudgetShift
# ---------------------------------------------------------------------------


class TestIssueBudgetShift:
    """issue_budget_shift creates directive and executes."""

    def test_creates_and_executes(self, integration_with_engines):
        eci, eng, es, mem = integration_with_engines
        result = eci.issue_budget_shift(
            "dir-bs-1", "Reallocate budget",
            "scope-xyz", -2500.0,
            reason="cost reduction",
        )
        assert result["directive_id"] == "dir-bs-1"
        assert result["budget_delta"] == -2500.0
        assert result["target_scope_ref_id"] == "scope-xyz"

        directive = eng.get_directive("dir-bs-1")
        assert directive is not None
        assert directive.status == DirectiveStatus.EXECUTED


# ---------------------------------------------------------------------------
# TestIssueCapacityShift
# ---------------------------------------------------------------------------


class TestIssueCapacityShift:
    """issue_capacity_shift creates directive and executes."""

    def test_creates_and_executes(self, integration_with_engines):
        eci, eng, es, mem = integration_with_engines
        result = eci.issue_capacity_shift(
            "dir-cs-1", "Scale up capacity",
            "scope-cap", 50.0,
            reason="demand spike",
        )
        assert result["directive_id"] == "dir-cs-1"
        assert result["capacity_delta"] == 50.0
        assert result["target_scope_ref_id"] == "scope-cap"

        directive = eng.get_directive("dir-cs-1")
        assert directive is not None
        assert directive.status == DirectiveStatus.EXECUTED


# ---------------------------------------------------------------------------
# TestMemoryMeshAttachment
# ---------------------------------------------------------------------------


class TestMemoryMeshAttachment:
    """attach_control_decisions_to_memory_mesh persists state."""

    def test_returns_memory_record(self, integration):
        record = integration.attach_control_decisions_to_memory_mesh("scope-ref-1")
        assert isinstance(record, MemoryRecord)
        assert record.title == "Control tower state"
        assert "scope-ref-1" not in record.title
        assert record.scope_ref_id == "scope-ref-1"
        assert "executive" in record.tags

    def test_duplicate_raises(self, integration):
        integration.attach_control_decisions_to_memory_mesh("scope-ref-dup")
        with pytest.raises(RuntimeCoreInvariantError):
            integration.attach_control_decisions_to_memory_mesh("scope-ref-dup")


# ---------------------------------------------------------------------------
# TestGraphAttachment
# ---------------------------------------------------------------------------


class TestGraphAttachment:
    """attach_control_decisions_to_graph returns counts and shifts."""

    def test_returns_counts_empty(self, integration):
        result = integration.attach_control_decisions_to_graph("scope-g-1")
        assert result["scope_ref_id"] == "scope-g-1"
        assert result["total_objectives"] == 0
        assert result["total_directives"] == 0
        assert result["total_scenarios"] == 0
        assert result["total_interventions"] == 0
        assert result["total_decisions"] == 0
        assert result["total_priority_shifts"] == 0
        assert result["priority_shifts"] == []

    def test_returns_counts_after_operations(self, integration_with_engines):
        eci, eng, es, mem = integration_with_engines
        # Create some state
        eng.register_objective("obj-g", "Test Obj", target_value=100.0)
        eci.control_from_portfolio(
            "dir-g-1", "Portfolio shift",
            target_scope_ref_id="scope-g-target",
            from_priority=PriorityLevel.P3_LOW,
            to_priority=PriorityLevel.P1_HIGH,
        )
        result = eci.attach_control_decisions_to_graph("scope-g-2")
        assert result["total_objectives"] == 1
        assert result["total_directives"] == 1
        assert result["total_priority_shifts"] == 1
        assert len(result["priority_shifts"]) == 1
        shift = result["priority_shifts"][0]
        assert shift["from"] == PriorityLevel.P3_LOW.value
        assert shift["to"] == PriorityLevel.P1_HIGH.value
        assert shift["target"] == "scope-g-target"


# ---------------------------------------------------------------------------
# TestEventEmission
# ---------------------------------------------------------------------------


class TestEventEmission:
    """Every control operation emits at least one event."""

    def _event_count(self, es: EventSpineEngine) -> int:
        return es.event_count

    def test_reporting_emits_event(self, integration_with_engines):
        eci, eng, es, mem = integration_with_engines
        eng.register_objective("obj-evt-1", "Evt Obj", target_value=100.0, tolerance_pct=5.0)
        before = self._event_count(es)
        eci.control_from_reporting("obj-evt-1", 80.0)
        after = self._event_count(es)
        assert after > before

    def test_financials_emits_event(self, integration_with_engines):
        eci, eng, es, mem = integration_with_engines
        before = self._event_count(es)
        eci.control_from_financials("dir-evt-fin", "Budget event")
        after = self._event_count(es)
        assert after > before

    def test_portfolio_emits_event(self, integration_with_engines):
        eci, eng, es, mem = integration_with_engines
        before = self._event_count(es)
        eci.control_from_portfolio("dir-evt-port", "Portfolio event")
        after = self._event_count(es)
        assert after > before

    def test_faults_emits_event(self, integration_with_engines):
        eci, eng, es, mem = integration_with_engines
        before = self._event_count(es)
        eci.control_from_faults("dir-evt-flt", "Fault event")
        after = self._event_count(es)
        assert after > before

    def test_autonomous_emits_event(self, integration_with_engines):
        eci, eng, es, mem = integration_with_engines
        before = self._event_count(es)
        eci.control_from_autonomous_improvement("dir-evt-auto", "Auto event")
        after = self._event_count(es)
        assert after > before

    def test_memory_attachment_emits_event(self, integration_with_engines):
        eci, eng, es, mem = integration_with_engines
        before = self._event_count(es)
        eci.attach_control_decisions_to_memory_mesh("scope-evt-mem")
        after = self._event_count(es)
        assert after > before


# ---------------------------------------------------------------------------
# Golden Scenarios
# ---------------------------------------------------------------------------


class TestGoldenScenario1DegradingKPI:
    """Degrading KPI triggers executive directive.

    Register objective with target=1000, current=900, tol=5%;
    update to 800 via control_from_reporting -> off_track, directive issued.
    """

    def test_degrading_kpi_triggers_directive(self, integration_with_engines):
        eci, eng, es, mem = integration_with_engines
        eng.register_objective(
            "obj-kpi-1", "Revenue KPI",
            target_value=1000.0,
            current_value=900.0,
            tolerance_pct=5.0,
        )
        result = eci.control_from_reporting("obj-kpi-1", 800.0)
        assert result["on_track"] is False
        assert result["directive_issued"] is True
        assert result["directive_id"] == "dir-rpt-obj-kpi-1"
        assert result["gap_pct"] == pytest.approx(20.0)
        assert result["target_value"] == 1000.0
        assert result["current_value"] == 800.0

        # Verify directive exists in engine
        directive = eng.get_directive("dir-rpt-obj-kpi-1")
        assert directive is not None
        assert directive.directive_type == DirectiveType.ESCALATE


class TestGoldenScenario2StrategicReprioritization:
    """Strategic objective reprioritizes two competing portfolios.

    Two control_from_portfolio calls for different portfolios.
    """

    def test_two_portfolio_reprioritizations(self, integration_with_engines):
        eci, eng, es, mem = integration_with_engines

        r1 = eci.control_from_portfolio(
            "dir-strat-a", "Elevate portfolio A",
            target_scope_ref_id="portfolio-a",
            from_priority=PriorityLevel.P3_LOW,
            to_priority=PriorityLevel.P1_HIGH,
            reason="new strategic focus",
        )
        r2 = eci.control_from_portfolio(
            "dir-strat-b", "Demote portfolio B",
            target_scope_ref_id="portfolio-b",
            from_priority=PriorityLevel.P1_HIGH,
            to_priority=PriorityLevel.P3_LOW,
            reason="reduced strategic value",
        )

        assert r1["directive_id"] == "dir-strat-a"
        assert r1["shift_id"] == "dir-strat-a-shift"
        assert r1["to_priority"] == PriorityLevel.P1_HIGH.value

        assert r2["directive_id"] == "dir-strat-b"
        assert r2["shift_id"] == "dir-strat-b-shift"
        assert r2["to_priority"] == PriorityLevel.P3_LOW.value

        # Two priority shifts recorded
        graph = eci.attach_control_decisions_to_graph("strat-ref")
        assert graph["total_priority_shifts"] == 2
        assert len(graph["priority_shifts"]) == 2


class TestGoldenScenario3BudgetSuppression:
    """Budget shift suppresses lower-value campaign set.

    control_from_financials with negative delta.
    """

    def test_budget_suppression(self, integration_with_engines):
        eci, eng, es, mem = integration_with_engines
        result = eci.control_from_financials(
            "dir-budg-sup", "Suppress low-value campaigns",
            budget_delta=-15000.0,
            target_scope_ref_id="campaign-set-low",
            reason="cost optimization",
        )
        assert result["directive_id"] == "dir-budg-sup"
        assert result["source"] == "financials"
        assert result["budget_delta"] == -15000.0
        assert result["target_scope_ref_id"] == "campaign-set-low"
        assert result["directive_type"] == DirectiveType.BUDGET_REALLOCATION.value

        directive = eng.get_directive("dir-budg-sup")
        assert directive is not None
        assert directive.directive_type == DirectiveType.BUDGET_REALLOCATION


class TestGoldenScenario4HaltUnsafeAutonomous:
    """Executive intervention halts unsafe autonomous improvement loop.

    control_from_autonomous_improvement with CRITICAL severity.
    """

    def test_halt_autonomous_loop(self, integration_with_engines):
        eci, eng, es, mem = integration_with_engines
        result = eci.control_from_autonomous_improvement(
            "dir-halt-1", "Halt unsafe auto-optimizer",
            target_scope_ref_id="auto-loop-unsafe",
            severity=InterventionSeverity.CRITICAL,
            reason="cost exceeded 3x projected budget",
        )
        assert result["directive_id"] == "dir-halt-1"
        assert result["source"] == "autonomous_improvement"
        assert result["directive_type"] == DirectiveType.HALT_AUTONOMOUS.value
        assert result["intervention_id"] == "dir-halt-1-int"
        assert result["severity"] == InterventionSeverity.CRITICAL.value

        # Verify intervention exists
        intervention = eng.get_intervention("dir-halt-1-int")
        assert intervention is not None
        assert intervention.severity == InterventionSeverity.CRITICAL
        assert intervention.target_engine == "autonomous_improvement"


class TestGoldenScenario5ScenarioPlan:
    """Scenario plan simulates impact before global connector change.

    Uses ExecutiveControlEngine directly: create_scenario -> run -> complete
    -> assess -> record_decision.
    """

    def test_scenario_plan_simulation(self, integration_with_engines):
        eci, eng, es, mem = integration_with_engines

        # Create scenario
        scenario = eng.create_scenario(
            "sc-conn-1", "Connector migration impact",
            objective_id="obj-conn",
            baseline_snapshot={"latency_ms": 50, "error_rate": 0.01},
            projected_snapshot={"latency_ms": 30, "error_rate": 0.005},
            assumptions=["new connector is 40% faster", "no breaking changes"],
            risk_score=0.3,
            confidence=0.7,
        )
        assert scenario.status == ScenarioStatus.DRAFT

        # Run
        running = eng.run_scenario("sc-conn-1")
        assert running.status == ScenarioStatus.RUNNING

        # Complete
        completed = eng.complete_scenario(
            "sc-conn-1",
            projected_snapshot={"latency_ms": 28, "error_rate": 0.003},
            confidence=0.85,
            risk_score=0.15,
        )
        assert completed.status == ScenarioStatus.COMPLETED
        assert completed.confidence == pytest.approx(0.85)

        # Assess
        outcome = eng.assess_scenario(
            "out-conn-1", "sc-conn-1", "approve",
            projected_improvement_pct=44.0,
            projected_risk_delta=-0.15,
            recommendation="proceed with migration",
        )
        assert outcome.verdict == "approve"
        assert outcome.projected_improvement_pct == pytest.approx(44.0)

        # Record decision
        decision = eng.record_decision(
            "dec-conn-1", "Approve connector migration",
            objective_id="obj-conn",
            directive_ids=["sc-conn-1"],
            rationale="scenario shows 44% improvement with acceptable risk",
            confidence=0.85,
            risk_score=0.15,
        )
        assert decision.decision_id == "dec-conn-1"
        assert decision.confidence == pytest.approx(0.85)


class TestGoldenScenario6FullPipeline:
    """Full pipeline: objective -> reporting -> financials -> portfolio
    -> faults -> autonomous -> memory -> graph.

    Exercises the complete integration lifecycle in a single flow.
    """

    def test_full_pipeline(self, integration_with_engines):
        eci, eng, es, mem = integration_with_engines

        # 1. Register objective
        eng.register_objective(
            "obj-full", "Full Pipeline Objective",
            target_value=1000.0,
            current_value=950.0,
            tolerance_pct=5.0,
            priority=PriorityLevel.P1_HIGH,
        )

        # 2. Reporting — KPI degrades
        rpt = eci.control_from_reporting("obj-full", 800.0)
        assert rpt["on_track"] is False
        assert rpt["directive_issued"] is True

        # 3. Financials — budget reallocation
        fin = eci.control_from_financials(
            "dir-full-fin", "Reallocate from underperformers",
            objective_id="obj-full",
            budget_delta=-3000.0,
            target_scope_ref_id="scope-under",
            reason="redirect funds",
        )
        assert fin["source"] == "financials"

        # 4. Portfolio — reprioritize
        port = eci.control_from_portfolio(
            "dir-full-port", "Elevate critical path",
            objective_id="obj-full",
            target_scope_ref_id="scope-critical",
            from_priority=PriorityLevel.P2_MEDIUM,
            to_priority=PriorityLevel.P0_CRITICAL,
            reason="align with degraded KPI",
        )
        assert port["source"] == "portfolio"
        assert port["shift_id"] == "dir-full-port-shift"

        # 5. Faults — escalate
        flt = eci.control_from_faults(
            "dir-full-fault", "Escalate pipeline failure",
            objective_id="obj-full",
            target_scope_ref_id="scope-faulty",
            severity=InterventionSeverity.HIGH,
            reason="repeated failures",
        )
        assert flt["source"] == "faults"
        assert flt["intervention_id"] == "dir-full-fault-int"

        # 6. Autonomous — halt unsafe loop
        auto = eci.control_from_autonomous_improvement(
            "dir-full-auto", "Halt runaway optimizer",
            objective_id="obj-full",
            target_scope_ref_id="scope-auto",
            severity=InterventionSeverity.CRITICAL,
            reason="cost ceiling breached",
        )
        assert auto["source"] == "autonomous_improvement"
        assert auto["directive_type"] == DirectiveType.HALT_AUTONOMOUS.value

        # 7. Attach to memory mesh
        record = eci.attach_control_decisions_to_memory_mesh("scope-full-pipeline")
        assert isinstance(record, MemoryRecord)
        assert record.content["total_objectives"] == 1
        assert record.content["total_directives"] >= 4  # reporting + fin + port + fault + auto = 5
        assert record.content["total_interventions"] == 2  # fault + auto
        assert record.content["total_priority_shifts"] == 1  # portfolio

        # 8. Attach to graph
        graph = eci.attach_control_decisions_to_graph("scope-full-graph")
        assert graph["total_objectives"] == 1
        assert graph["total_directives"] >= 4
        assert graph["total_priority_shifts"] == 1
        assert len(graph["priority_shifts"]) == 1
        assert graph["priority_shifts"][0]["target"] == "scope-critical"

        # Verify events were emitted throughout
        assert es.event_count > 10  # Many operations, each emitting events
