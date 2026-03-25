"""Phase 136 — Internal Service Delivery Automation Tests."""
import pytest
from mcoi_runtime.pilot.internal_ops import (
    INTERNAL_PACK_CAPABILITIES, IMPLEMENTATION_STAGES, STANDARD_MILESTONES,
    InternalOpsEngine, CompanyOperatingState,
)

class TestInternalPack:
    def test_10_capabilities(self):
        assert len(INTERNAL_PACK_CAPABILITIES) == 10
    def test_8_implementation_stages(self):
        assert len(IMPLEMENTATION_STAGES) == 8
        assert IMPLEMENTATION_STAGES[0] == "deal_closed"
        assert IMPLEMENTATION_STAGES[-1] == "steady_state"
    def test_8_standard_milestones(self):
        assert len(STANDARD_MILESTONES) == 8

class TestImplementation:
    def test_create_project(self):
        engine = InternalOpsEngine()
        proj = engine.create_project("p1", "c1", "regulated_ops")
        assert proj.status == "deal_closed"
        assert proj.tasks_total == 8

    def test_advance_project(self):
        engine = InternalOpsEngine()
        engine.create_project("p1", "c1", "regulated_ops")
        engine.advance_project("p1")
        assert engine._projects["p1"].status == "tenant_created"

    def test_full_advancement(self):
        engine = InternalOpsEngine()
        engine.create_project("p1", "c1", "regulated_ops")
        for _ in range(7):
            engine.advance_project("p1")
        assert engine._projects["p1"].status == "steady_state"

class TestSupport:
    def test_create_case(self):
        engine = InternalOpsEngine()
        case = engine.create_support_case("s1", "c1", "critical", "connector")
        assert case.sla_deadline_hours == 4.0

    def test_assign_and_resolve(self):
        engine = InternalOpsEngine()
        engine.create_support_case("s1", "c1", "high", "break_fix")
        engine.assign_case("s1", "eng-1")
        engine.resolve_case("s1")
        state = engine.operating_state()
        assert state.open_support_cases == 0

    def test_escalation(self):
        engine = InternalOpsEngine()
        engine.create_support_case("s1", "c1", "critical", "connector")
        engine.escalate_case("s1")
        case = [c for c in engine._support_cases if c.case_id == "s1"][0]
        assert case.escalated is True

class TestSuccessMilestones:
    def test_create_milestones(self):
        engine = InternalOpsEngine()
        milestones = engine.create_milestones("c1")
        assert len(milestones) == 8

    def test_complete_milestone(self):
        engine = InternalOpsEngine()
        engine.create_milestones("c1")
        engine.complete_milestone("ms-c1-first_case_completed")
        ms = [m for m in engine._milestones if m.milestone_id == "ms-c1-first_case_completed"][0]
        assert ms.completed is True

class TestOperatingDashboard:
    def test_healthy_state(self):
        engine = InternalOpsEngine()
        state = engine.operating_state()
        assert state.operating_health == "healthy"

    def test_strained_state(self):
        engine = InternalOpsEngine()
        for i in range(3):
            engine.create_support_case(f"crit-{i}", f"c{i}", "critical", "break_fix")
        state = engine.operating_state()
        assert state.operating_health == "strained"

class TestGoldenProof:
    """Phase 136F — 7-point golden proof."""

    def test_company_runs_on_platform(self):
        engine = InternalOpsEngine()

        # 1. Deal closes → project enters implementation
        proj = engine.create_project("impl-1", "acme", "regulated_ops")
        assert proj.status == "deal_closed"

        # 2. Deployment tasks assigned and tracked
        engine.advance_project("impl-1")  # → tenant_created
        engine.advance_project("impl-1")  # → deploying
        engine.complete_project_task("impl-1")
        assert engine._projects["impl-1"].progress > 0

        # 3. Support incidents route by severity
        case = engine.create_support_case("sup-1", "acme", "high", "connector")
        assert case.sla_deadline_hours == 8.0
        engine.assign_case("sup-1", "support-eng-1")

        # 4. CSM milestones track risk
        milestones = engine.create_milestones("acme")
        assert len(milestones) == 8
        engine.complete_milestone("ms-acme-first_case_completed")

        # 5. Advance to live
        for _ in range(3):  # deploying → training → go_live_pending → live
            engine.advance_project("impl-1")

        # 6. Resolve support, check state
        engine.resolve_case("sup-1")

        # 7. Executive dashboard shows company state
        state = engine.operating_state()
        assert state.live_customers >= 1
        assert state.live_customers >= 1
        assert state.open_support_cases == 0
        assert state.operating_health == "healthy"

        # Company is running on its own platform
        assert engine.project_count == 1
        assert engine.case_count == 1
        assert engine.milestone_count == 8
