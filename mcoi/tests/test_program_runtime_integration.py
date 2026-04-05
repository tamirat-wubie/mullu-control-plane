"""Tests for mcoi.mcoi_runtime.core.program_runtime_integration.

Covers: constructor validation, all integration bridge methods,
memory mesh attachment, graph attachment, event emission,
and six golden end-to-end scenarios.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.core.program_runtime_integration import ProgramRuntimeIntegration
from mcoi_runtime.core.program_runtime import ProgramRuntimeEngine
from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.memory_mesh import MemoryMeshEngine
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
from mcoi_runtime.contracts.program_runtime import (
    AttainmentLevel,
    DependencyKind,
    InitiativeStatus,
    MilestoneStatus,
)
from mcoi_runtime.contracts.memory_mesh import MemoryRecord


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def es() -> EventSpineEngine:
    return EventSpineEngine()


@pytest.fixture()
def mem() -> MemoryMeshEngine:
    return MemoryMeshEngine()


@pytest.fixture()
def eng(es: EventSpineEngine) -> ProgramRuntimeEngine:
    return ProgramRuntimeEngine(event_spine=es)


@pytest.fixture()
def bridge(eng: ProgramRuntimeEngine, es: EventSpineEngine, mem: MemoryMeshEngine) -> ProgramRuntimeIntegration:
    return ProgramRuntimeIntegration(eng, es, mem)


def _two_initiative_specs() -> list[dict]:
    return [
        {"initiative_id": "ini-a", "title": "Alpha Initiative", "priority": 1, "owner": "alice"},
        {"initiative_id": "ini-b", "title": "Beta Initiative", "priority": 2, "owner": "bob"},
    ]


# ===================================================================
# TestConstructor
# ===================================================================


class TestConstructor:
    """Validate ProgramRuntimeIntegration constructor."""

    def test_valid_construction(self, eng, es, mem):
        bridge = ProgramRuntimeIntegration(eng, es, mem)
        assert bridge is not None

    def test_invalid_program_engine_type(self, es, mem):
        with pytest.raises(RuntimeCoreInvariantError, match="program_engine"):
            ProgramRuntimeIntegration("not-an-engine", es, mem)

    def test_invalid_event_spine_type(self, eng, mem):
        with pytest.raises(RuntimeCoreInvariantError, match="event_spine"):
            ProgramRuntimeIntegration(eng, "not-a-spine", mem)

    def test_invalid_memory_engine_type(self, eng, es):
        with pytest.raises(RuntimeCoreInvariantError, match="memory_engine"):
            ProgramRuntimeIntegration(eng, es, "not-a-mesh")

    def test_none_arguments(self, eng, es, mem):
        with pytest.raises(RuntimeCoreInvariantError):
            ProgramRuntimeIntegration(None, es, mem)
        with pytest.raises(RuntimeCoreInvariantError):
            ProgramRuntimeIntegration(eng, None, mem)
        with pytest.raises(RuntimeCoreInvariantError):
            ProgramRuntimeIntegration(eng, es, None)


# ===================================================================
# TestProgramFromExecutiveObjective
# ===================================================================


class TestProgramFromExecutiveObjective:
    """Test program_from_executive_objective method."""

    def test_creates_all_components(self, bridge, eng):
        result = bridge.program_from_executive_objective(
            "prog-1", "obj-1", "Revenue Growth",
            target_value=1_000_000.0,
            unit="USD",
            initiative_specs=_two_initiative_specs(),
            owner="ceo",
        )

        assert result["program_id"] == "prog-1"
        assert result["objective_id"] == "obj-1"
        assert result["initiative_ids"] == ["ini-a", "ini-b"]
        assert result["title"] == "Revenue Growth"
        assert result["target_value"] == 1_000_000.0

        # Verify engine state
        assert eng.get_objective("obj-1") is not None
        assert eng.get_program("prog-1") is not None
        assert eng.get_initiative("ini-a") is not None
        assert eng.get_initiative("ini-b") is not None

    def test_empty_initiative_specs(self, bridge):
        result = bridge.program_from_executive_objective(
            "prog-2", "obj-2", "Empty Program",
        )
        assert result["initiative_ids"] == []
        assert result["target_value"] == 0.0

    def test_none_initiative_specs(self, bridge):
        result = bridge.program_from_executive_objective(
            "prog-3", "obj-3", "No Specs",
            initiative_specs=None,
        )
        assert result["initiative_ids"] == []

    def test_default_keyword_args(self, bridge):
        result = bridge.program_from_executive_objective(
            "prog-4", "obj-4", "Defaults",
        )
        assert result["target_value"] == 0.0
        assert result["title"] == "Defaults"


# ===================================================================
# TestBindings
# ===================================================================


class TestBindings:
    """Test bind_campaign_to_initiative and bind_portfolio_to_program."""

    def test_bind_campaign(self, bridge):
        bridge.program_from_executive_objective(
            "prog-b1", "obj-b1", "Campaign Binding Test",
            initiative_specs=[{"initiative_id": "ini-b1", "title": "Ini B1"}],
        )

        result = bridge.bind_campaign_to_initiative(
            "bind-c1", "ini-b1", "campaign-001",
            objective_id="obj-b1",
            weight=0.7,
        )

        assert result["binding_id"] == "bind-c1"
        assert result["initiative_id"] == "ini-b1"
        assert result["campaign_ref_id"] == "campaign-001"
        assert result["weight"] == 0.7

    def test_bind_portfolio(self, bridge):
        bridge.program_from_executive_objective(
            "prog-b2", "obj-b2", "Portfolio Binding Test",
            initiative_specs=[{"initiative_id": "ini-b2", "title": "Ini B2"}],
        )

        result = bridge.bind_portfolio_to_program(
            "bind-p1", "ini-b2", "portfolio-001",
            objective_id="obj-b2",
            weight=0.5,
        )

        assert result["binding_id"] == "bind-p1"
        assert result["initiative_id"] == "ini-b2"
        assert result["portfolio_ref_id"] == "portfolio-001"
        assert result["weight"] == 0.5

    def test_bind_campaign_default_weight(self, bridge):
        bridge.program_from_executive_objective(
            "prog-b3", "obj-b3", "Default Weight",
            initiative_specs=[{"initiative_id": "ini-b3", "title": "Ini B3"}],
        )
        result = bridge.bind_campaign_to_initiative("bind-c2", "ini-b3", "campaign-002")
        assert result["weight"] == 1.0

    def test_bind_portfolio_default_weight(self, bridge):
        bridge.program_from_executive_objective(
            "prog-b4", "obj-b4", "Default Weight Portfolio",
            initiative_specs=[{"initiative_id": "ini-b4", "title": "Ini B4"}],
        )
        result = bridge.bind_portfolio_to_program("bind-p2", "ini-b4", "portfolio-002")
        assert result["weight"] == 1.0


# ===================================================================
# TestUpdateFromCampaignOutcomes
# ===================================================================


class TestUpdateFromCampaignOutcomes:
    """Test update_from_campaign_outcomes method."""

    def test_update_progress(self, bridge):
        bridge.program_from_executive_objective(
            "prog-uc1", "obj-uc1", "Campaign Update",
            initiative_specs=[{"initiative_id": "ini-uc1", "title": "Ini UC1"}],
        )

        result = bridge.update_from_campaign_outcomes("ini-uc1", 55.0)
        assert result["initiative_id"] == "ini-uc1"
        assert result["progress_pct"] == 55.0
        assert result["status"] == InitiativeStatus.ACTIVE.value

    def test_zero_progress(self, bridge):
        bridge.program_from_executive_objective(
            "prog-uc2", "obj-uc2", "Zero Progress",
            initiative_specs=[{"initiative_id": "ini-uc2", "title": "Ini UC2"}],
        )
        result = bridge.update_from_campaign_outcomes("ini-uc2", 0.0)
        assert result["progress_pct"] == 0.0

    def test_full_progress(self, bridge):
        bridge.program_from_executive_objective(
            "prog-uc3", "obj-uc3", "Full Progress",
            initiative_specs=[{"initiative_id": "ini-uc3", "title": "Ini UC3"}],
        )
        result = bridge.update_from_campaign_outcomes("ini-uc3", 100.0)
        assert result["progress_pct"] == 100.0


# ===================================================================
# TestUpdateFromFinancials
# ===================================================================


class TestUpdateFromFinancials:
    """Test update_from_financials method."""

    def test_update_value(self, bridge):
        bridge.program_from_executive_objective(
            "prog-uf1", "obj-uf1", "Financial Update",
            target_value=100.0,
        )

        result = bridge.update_from_financials("obj-uf1", 95.0)
        assert result["objective_id"] == "obj-uf1"
        assert result["current_value"] == 95.0
        assert result["attainment"] == AttainmentLevel.ON_TRACK.value

    def test_exceeded_attainment(self, bridge):
        bridge.program_from_executive_objective(
            "prog-uf2", "obj-uf2", "Exceeded",
            target_value=100.0,
        )
        result = bridge.update_from_financials("obj-uf2", 115.0)
        assert result["attainment"] == AttainmentLevel.EXCEEDED.value

    def test_behind_attainment(self, bridge):
        bridge.program_from_executive_objective(
            "prog-uf3", "obj-uf3", "Behind",
            target_value=100.0,
        )
        result = bridge.update_from_financials("obj-uf3", 50.0)
        assert result["attainment"] == AttainmentLevel.BEHIND.value


# ===================================================================
# TestUpdateFromReporting
# ===================================================================


class TestUpdateFromReporting:
    """Test update_from_reporting method."""

    def test_update_value(self, bridge):
        bridge.program_from_executive_objective(
            "prog-ur1", "obj-ur1", "Reporting Update",
            target_value=200.0,
        )

        result = bridge.update_from_reporting("obj-ur1", 180.0)
        assert result["objective_id"] == "obj-ur1"
        assert result["current_value"] == 180.0
        assert result["attainment"] == AttainmentLevel.ON_TRACK.value

    def test_at_risk_attainment(self, bridge):
        bridge.program_from_executive_objective(
            "prog-ur2", "obj-ur2", "At Risk",
            target_value=200.0,
        )
        result = bridge.update_from_reporting("obj-ur2", 150.0)
        assert result["attainment"] == AttainmentLevel.AT_RISK.value

    def test_not_started_attainment(self, bridge):
        bridge.program_from_executive_objective(
            "prog-ur3", "obj-ur3", "Not Started",
            target_value=200.0,
        )
        result = bridge.update_from_reporting("obj-ur3", 0.0)
        assert result["attainment"] == AttainmentLevel.NOT_STARTED.value


# ===================================================================
# TestUpdateFromOptimization
# ===================================================================


class TestUpdateFromOptimization:
    """Test update_from_optimization method."""

    def test_update_progress(self, bridge):
        bridge.program_from_executive_objective(
            "prog-uo1", "obj-uo1", "Optimization Update",
            initiative_specs=[{"initiative_id": "ini-uo1", "title": "Ini UO1"}],
        )

        result = bridge.update_from_optimization("ini-uo1", 80.0)
        assert result["initiative_id"] == "ini-uo1"
        assert result["progress_pct"] == 80.0
        assert result["status"] == InitiativeStatus.ACTIVE.value

    def test_zero_optimization(self, bridge):
        bridge.program_from_executive_objective(
            "prog-uo2", "obj-uo2", "Zero Opt",
            initiative_specs=[{"initiative_id": "ini-uo2", "title": "Ini UO2"}],
        )
        result = bridge.update_from_optimization("ini-uo2", 0.0)
        assert result["progress_pct"] == 0.0


# ===================================================================
# TestMemoryMeshAttachment
# ===================================================================


class TestMemoryMeshAttachment:
    """Test attach_program_state_to_memory_mesh method."""

    def test_returns_memory_record(self, bridge):
        bridge.program_from_executive_objective(
            "prog-m1", "obj-m1", "Memory Test",
            initiative_specs=[{"initiative_id": "ini-m1", "title": "Ini M1"}],
        )

        record = bridge.attach_program_state_to_memory_mesh("scope-m1")
        assert isinstance(record, MemoryRecord)
        assert record.scope_ref_id == "scope-m1"
        assert record.title == "Program state"
        assert "scope-m1" not in record.title
        assert "program" in record.tags
        assert record.content["total_programs"] == 1
        assert record.content["total_objectives"] == 1
        assert record.content["total_initiatives"] == 1

    def test_duplicate_scope_ref_raises(self, bridge):
        bridge.program_from_executive_objective(
            "prog-m2", "obj-m2", "Dup Test",
        )
        bridge.attach_program_state_to_memory_mesh("scope-m2")

        with pytest.raises(RuntimeCoreInvariantError, match="duplicate memory_id"):
            bridge.attach_program_state_to_memory_mesh("scope-m2")

    def test_memory_content_counts(self, bridge, eng):
        bridge.program_from_executive_objective(
            "prog-m3", "obj-m3", "Counts Test",
            initiative_specs=_two_initiative_specs(),
        )
        eng.register_milestone("ms-m3", "ini-a", "Milestone A")

        record = bridge.attach_program_state_to_memory_mesh("scope-m3")
        assert record.content["total_initiatives"] == 2
        assert record.content["total_milestones"] == 1


# ===================================================================
# TestGraphAttachment
# ===================================================================


class TestGraphAttachment:
    """Test attach_program_state_to_graph method."""

    def test_returns_counts(self, bridge):
        bridge.program_from_executive_objective(
            "prog-g1", "obj-g1", "Graph Test",
            initiative_specs=_two_initiative_specs(),
        )

        result = bridge.attach_program_state_to_graph("scope-g1")
        assert result["scope_ref_id"] == "scope-g1"
        assert result["total_programs"] == 1
        assert result["total_objectives"] == 1
        assert result["total_initiatives"] == 2
        assert result["blocked_initiatives"] == []

    def test_blocked_list_populated(self, bridge, eng):
        bridge.program_from_executive_objective(
            "prog-g2", "obj-g2", "Blocked Graph",
            initiative_specs=[{"initiative_id": "ini-g2", "title": "Ini G2"}],
        )
        eng.set_initiative_status("ini-g2", InitiativeStatus.BLOCKED)

        result = bridge.attach_program_state_to_graph("scope-g2")
        assert "ini-g2" in result["blocked_initiatives"]

    def test_graph_includes_milestones_and_bindings(self, bridge, eng):
        bridge.program_from_executive_objective(
            "prog-g3", "obj-g3", "Full Graph",
            initiative_specs=[{"initiative_id": "ini-g3", "title": "Ini G3"}],
        )
        eng.register_milestone("ms-g3", "ini-g3", "MS G3")
        bridge.bind_campaign_to_initiative("bind-g3", "ini-g3", "camp-g3")

        result = bridge.attach_program_state_to_graph("scope-g3")
        assert result["total_milestones"] == 1
        assert result["total_bindings"] == 1


# ===================================================================
# TestEventEmission
# ===================================================================


class TestEventEmission:
    """Verify that integration methods emit events to the event spine."""

    def test_program_from_executive_emits(self, bridge, es):
        initial = es.event_count
        bridge.program_from_executive_objective(
            "prog-ev1", "obj-ev1", "Event Test",
            initiative_specs=[{"initiative_id": "ini-ev1", "title": "Ini EV1"}],
        )
        # Objective registration + program registration + initiative registration + integration event
        assert es.event_count > initial

    def test_bind_campaign_emits(self, bridge, es):
        bridge.program_from_executive_objective(
            "prog-ev2", "obj-ev2", "Bind Event",
            initiative_specs=[{"initiative_id": "ini-ev2", "title": "Ini EV2"}],
        )
        before = es.event_count
        bridge.bind_campaign_to_initiative("bind-ev2", "ini-ev2", "camp-ev2")
        assert es.event_count > before

    def test_bind_portfolio_emits(self, bridge, es):
        bridge.program_from_executive_objective(
            "prog-ev3", "obj-ev3", "Portfolio Event",
            initiative_specs=[{"initiative_id": "ini-ev3", "title": "Ini EV3"}],
        )
        before = es.event_count
        bridge.bind_portfolio_to_program("bind-ev3", "ini-ev3", "port-ev3")
        assert es.event_count > before

    def test_update_from_campaign_emits(self, bridge, es):
        bridge.program_from_executive_objective(
            "prog-ev4", "obj-ev4", "Campaign Outcome Event",
            initiative_specs=[{"initiative_id": "ini-ev4", "title": "Ini EV4"}],
        )
        before = es.event_count
        bridge.update_from_campaign_outcomes("ini-ev4", 50.0)
        assert es.event_count > before

    def test_update_from_financials_emits(self, bridge, es):
        bridge.program_from_executive_objective(
            "prog-ev5", "obj-ev5", "Financial Event",
            target_value=100.0,
        )
        before = es.event_count
        bridge.update_from_financials("obj-ev5", 75.0)
        assert es.event_count > before

    def test_update_from_reporting_emits(self, bridge, es):
        bridge.program_from_executive_objective(
            "prog-ev6", "obj-ev6", "Reporting Event",
            target_value=100.0,
        )
        before = es.event_count
        bridge.update_from_reporting("obj-ev6", 60.0)
        assert es.event_count > before

    def test_update_from_optimization_emits(self, bridge, es):
        bridge.program_from_executive_objective(
            "prog-ev7", "obj-ev7", "Optimization Event",
            initiative_specs=[{"initiative_id": "ini-ev7", "title": "Ini EV7"}],
        )
        before = es.event_count
        bridge.update_from_optimization("ini-ev7", 90.0)
        assert es.event_count > before

    def test_memory_attachment_emits(self, bridge, es):
        bridge.program_from_executive_objective(
            "prog-ev8", "obj-ev8", "Memory Event",
        )
        before = es.event_count
        bridge.attach_program_state_to_memory_mesh("scope-ev8")
        assert es.event_count > before


# ===================================================================
# Golden Scenarios
# ===================================================================


class TestGoldenScenario1_ExecutiveObjectiveCreatesProgramWithTwoInitiatives:
    """Scenario 1: Executive objective creates program with 2 initiatives."""

    def test_full_creation(self, bridge, eng):
        specs = [
            {"initiative_id": "gs1-ini-a", "title": "Launch Campaign", "priority": 1, "owner": "alice"},
            {"initiative_id": "gs1-ini-b", "title": "Optimize Funnel", "priority": 2, "owner": "bob"},
        ]
        result = bridge.program_from_executive_objective(
            "gs1-prog", "gs1-obj", "Q4 Revenue Target",
            target_value=500_000.0,
            unit="USD",
            initiative_specs=specs,
            owner="cfo",
        )

        assert result["program_id"] == "gs1-prog"
        assert result["objective_id"] == "gs1-obj"
        assert len(result["initiative_ids"]) == 2
        assert result["target_value"] == 500_000.0

        # Verify engine internals
        obj = eng.get_objective("gs1-obj")
        assert obj is not None
        assert obj.target_value == 500_000.0
        assert obj.owner == "cfo"

        prog = eng.get_program("gs1-prog")
        assert prog is not None
        assert "gs1-obj" in prog.objective_ids
        assert "gs1-ini-a" in prog.initiative_ids
        assert "gs1-ini-b" in prog.initiative_ids

        ini_a = eng.get_initiative("gs1-ini-a")
        assert ini_a.priority == 1
        assert ini_a.owner == "alice"

        ini_b = eng.get_initiative("gs1-ini-b")
        assert ini_b.priority == 2
        assert ini_b.owner == "bob"


class TestGoldenScenario2_TwoCampaignsRollUpIntoInitiativeAttainment:
    """Scenario 2: Two campaigns roll up into initiative attainment."""

    def test_two_campaigns_roll_up(self, bridge, eng):
        bridge.program_from_executive_objective(
            "gs2-prog", "gs2-obj", "Multi Campaign",
            initiative_specs=[{"initiative_id": "gs2-ini", "title": "Main Initiative"}],
        )

        # Bind two campaigns
        bridge.bind_campaign_to_initiative("gs2-bind-1", "gs2-ini", "camp-1", weight=0.6)
        bridge.bind_campaign_to_initiative("gs2-bind-2", "gs2-ini", "camp-2", weight=0.4)

        # Update from first campaign
        r1 = bridge.update_from_campaign_outcomes("gs2-ini", 40.0)
        assert r1["progress_pct"] == 40.0

        # Update from second campaign (overwrites to higher progress)
        r2 = bridge.update_from_campaign_outcomes("gs2-ini", 75.0)
        assert r2["progress_pct"] == 75.0

        # Verify initiative state via engine
        ini = eng.get_initiative("gs2-ini")
        assert ini.progress_pct == 75.0
        assert ini.status == InitiativeStatus.ACTIVE

        # Verify both campaigns are tracked on the initiative
        assert "camp-1" in ini.campaign_ids
        assert "camp-2" in ini.campaign_ids


class TestGoldenScenario3_MissedMilestoneDegradesProgramHealth:
    """Scenario 3: Missed milestone degrades program health."""

    def test_missed_milestone_degrades_health(self, bridge, eng):
        bridge.program_from_executive_objective(
            "gs3-prog", "gs3-obj", "Milestone Health Test",
            initiative_specs=[{"initiative_id": "gs3-ini", "title": "Main Initiative"}],
        )

        # Register milestone via engine
        eng.register_milestone("gs3-ms", "gs3-ini", "Critical Deadline")

        # Record progress as MISSED
        eng.record_milestone_progress("gs3-ms", 30.0, status=MilestoneStatus.MISSED)

        # Check program health via engine
        health = eng.program_health("gs3-prog", "gs3-health")
        assert health.total_milestones == 1
        assert health.missed_milestones == 1
        assert health.achieved_milestones == 0


class TestGoldenScenario4_BlockedDependencyEscalates:
    """Scenario 4: Blocked dependency escalates."""

    def test_blocked_dependency_escalates(self, bridge, eng):
        bridge.program_from_executive_objective(
            "gs4-prog", "gs4-obj", "Dependency Escalation",
            initiative_specs=[
                {"initiative_id": "gs4-ini-a", "title": "Upstream"},
                {"initiative_id": "gs4-ini-b", "title": "Downstream"},
            ],
        )

        # Add dependency: gs4-ini-b REQUIRES gs4-ini-a
        eng.add_dependency(
            "gs4-dep", "gs4-ini-b", "gs4-ini-a",
            kind=DependencyKind.REQUIRES,
        )

        # Fail the target initiative (upstream)
        eng.set_initiative_status("gs4-ini-a", InitiativeStatus.FAILED)

        # Check blocked initiatives via engine
        blocked = eng.blocked_initiatives()
        blocked_ids = [b.initiative_id for b in blocked]
        assert "gs4-ini-b" in blocked_ids

        # Graph attachment should also reflect blocked
        graph = bridge.attach_program_state_to_graph("gs4-graph")
        assert "gs4-ini-b" in graph["blocked_initiatives"]


class TestGoldenScenario5_FinancialAndReportingDataChangesAttainment:
    """Scenario 5: Financial/reporting data changes attainment."""

    def test_financial_then_reporting_updates_attainment(self, bridge):
        bridge.program_from_executive_objective(
            "gs5-prog", "gs5-obj", "Attainment Tracking",
            target_value=1000.0,
            unit="USD",
        )

        # Financial update: behind
        r1 = bridge.update_from_financials("gs5-obj", 400.0)
        assert r1["attainment"] == AttainmentLevel.BEHIND.value
        assert r1["current_value"] == 400.0

        # Reporting update: on track
        r2 = bridge.update_from_reporting("gs5-obj", 950.0)
        assert r2["attainment"] == AttainmentLevel.ON_TRACK.value
        assert r2["current_value"] == 950.0

        # Reporting update: exceeded
        r3 = bridge.update_from_reporting("gs5-obj", 1150.0)
        assert r3["attainment"] == AttainmentLevel.EXCEEDED.value


class TestGoldenScenario6_FullPipeline:
    """Scenario 6: Full pipeline from executive objective through memory and graph."""

    def test_full_pipeline(self, bridge, eng, es, mem):
        initial_events = es.event_count

        # Step 1: Create program from executive objective
        specs = [
            {"initiative_id": "gs6-ini-a", "title": "Digital Transformation", "priority": 1, "owner": "alice"},
            {"initiative_id": "gs6-ini-b", "title": "Market Expansion", "priority": 2, "owner": "bob"},
        ]
        result = bridge.program_from_executive_objective(
            "gs6-prog", "gs6-obj", "Strategic Growth FY26",
            target_value=10_000_000.0,
            unit="USD",
            initiative_specs=specs,
            owner="ceo",
        )
        assert len(result["initiative_ids"]) == 2

        # Step 2: Bind campaigns
        bridge.bind_campaign_to_initiative("gs6-bind-c1", "gs6-ini-a", "camp-digital", weight=0.8)
        bridge.bind_campaign_to_initiative("gs6-bind-c2", "gs6-ini-b", "camp-market", weight=0.7)

        # Step 3: Bind portfolio
        bridge.bind_portfolio_to_program("gs6-bind-p1", "gs6-ini-a", "portfolio-tech", weight=1.0)

        # Step 4: Update from campaign outcomes
        r_camp = bridge.update_from_campaign_outcomes("gs6-ini-a", 60.0)
        assert r_camp["progress_pct"] == 60.0

        # Step 5: Update from optimization
        r_opt = bridge.update_from_optimization("gs6-ini-b", 45.0)
        assert r_opt["progress_pct"] == 45.0

        # Step 6: Update from financials
        r_fin = bridge.update_from_financials("gs6-obj", 7_500_000.0)
        assert r_fin["attainment"] == AttainmentLevel.AT_RISK.value

        # Step 7: Update from reporting
        r_rep = bridge.update_from_reporting("gs6-obj", 9_200_000.0)
        assert r_rep["attainment"] == AttainmentLevel.ON_TRACK.value

        # Step 8: Attach to memory mesh
        mem_record = bridge.attach_program_state_to_memory_mesh("gs6-scope")
        assert isinstance(mem_record, MemoryRecord)
        assert mem_record.content["total_programs"] == 1
        assert mem_record.content["total_objectives"] == 1
        assert mem_record.content["total_initiatives"] == 2
        assert mem_record.content["total_bindings"] == 3  # 2 campaigns + 1 portfolio

        # Step 9: Attach to graph
        graph = bridge.attach_program_state_to_graph("gs6-graph")
        assert graph["total_programs"] == 1
        assert graph["total_objectives"] == 1
        assert graph["total_initiatives"] == 2
        assert graph["total_bindings"] == 3
        assert graph["blocked_initiatives"] == []

        # Verify events were emitted throughout
        assert es.event_count > initial_events

        # Verify engine state is consistent
        prog = eng.get_program("gs6-prog")
        assert len(prog.initiative_ids) == 2

        ini_a = eng.get_initiative("gs6-ini-a")
        assert ini_a.progress_pct == 60.0
        assert "camp-digital" in ini_a.campaign_ids
        assert "portfolio-tech" in ini_a.portfolio_ids

        ini_b = eng.get_initiative("gs6-ini-b")
        assert ini_b.progress_pct == 45.0
        assert "camp-market" in ini_b.campaign_ids

        obj = eng.get_objective("gs6-obj")
        assert obj.current_value == 9_200_000.0
        assert obj.attainment == AttainmentLevel.ON_TRACK
