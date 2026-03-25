"""Purpose: comprehensive tests for the meta-orchestration integration bridge.
Governance scope: MetaOrchestrationIntegration — all 8 public methods.
Dependencies: pytest, mcoi_runtime core engines and contracts.
Invariants: every test is isolated, deterministic, and side-effect free.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.memory_mesh import MemoryMeshEngine
from mcoi_runtime.core.meta_orchestration import MetaOrchestrationEngine
from mcoi_runtime.core.meta_orchestration_integration import MetaOrchestrationIntegration
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
from mcoi_runtime.contracts.memory_mesh import MemoryRecord


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def engines():
    es = EventSpineEngine()
    mm = MemoryMeshEngine()
    eng = MetaOrchestrationEngine(es)
    return eng, es, mm


@pytest.fixture()
def bridge(engines):
    eng, es, mm = engines
    return MetaOrchestrationIntegration(eng, es, mm)


@pytest.fixture()
def bridge_and_engines(engines):
    eng, es, mm = engines
    b = MetaOrchestrationIntegration(eng, es, mm)
    return b, eng, es, mm


# ---------------------------------------------------------------------------
# Constructor invariant tests
# ---------------------------------------------------------------------------


class TestConstructorInvariants:
    """Constructor must reject non-engine arguments."""

    def test_rejects_none_orchestration_engine(self, engines):
        _, es, mm = engines
        with pytest.raises(RuntimeCoreInvariantError, match="orchestration_engine"):
            MetaOrchestrationIntegration(None, es, mm)

    def test_rejects_string_orchestration_engine(self, engines):
        _, es, mm = engines
        with pytest.raises(RuntimeCoreInvariantError, match="orchestration_engine"):
            MetaOrchestrationIntegration("not-an-engine", es, mm)

    def test_rejects_none_event_spine(self, engines):
        eng, _, mm = engines
        with pytest.raises(RuntimeCoreInvariantError, match="event_spine"):
            MetaOrchestrationIntegration(eng, None, mm)

    def test_rejects_string_event_spine(self, engines):
        eng, _, mm = engines
        with pytest.raises(RuntimeCoreInvariantError, match="event_spine"):
            MetaOrchestrationIntegration(eng, "not-an-engine", mm)

    def test_rejects_none_memory_engine(self, engines):
        eng, es, _ = engines
        with pytest.raises(RuntimeCoreInvariantError, match="memory_engine"):
            MetaOrchestrationIntegration(eng, es, None)

    def test_rejects_dict_memory_engine(self, engines):
        eng, es, _ = engines
        with pytest.raises(RuntimeCoreInvariantError, match="memory_engine"):
            MetaOrchestrationIntegration(eng, es, {})

    def test_valid_construction(self, bridge):
        assert bridge is not None


# ---------------------------------------------------------------------------
# orchestrate_service_to_campaign
# ---------------------------------------------------------------------------


class TestServiceToCampaign:

    def test_returns_dict(self, bridge):
        r = bridge.orchestrate_service_to_campaign("p1", "t1", "svc-1", "camp-1")
        assert isinstance(r, dict)

    def test_plan_id_matches(self, bridge):
        r = bridge.orchestrate_service_to_campaign("p1", "t1", "svc-1", "camp-1")
        assert r["plan_id"] == "p1"

    def test_tenant_id_matches(self, bridge):
        r = bridge.orchestrate_service_to_campaign("p1", "t1", "svc-1", "camp-1")
        assert r["tenant_id"] == "t1"

    def test_service_ref(self, bridge):
        r = bridge.orchestrate_service_to_campaign("p1", "t1", "svc-1", "camp-1")
        assert r["service_ref"] == "svc-1"

    def test_campaign_ref(self, bridge):
        r = bridge.orchestrate_service_to_campaign("p1", "t1", "svc-1", "camp-1")
        assert r["campaign_ref"] == "camp-1"

    def test_step_count(self, bridge):
        r = bridge.orchestrate_service_to_campaign("p1", "t1", "svc-1", "camp-1")
        assert r["step_count"] == 2

    def test_coordination_mode(self, bridge):
        r = bridge.orchestrate_service_to_campaign("p1", "t1", "svc-1", "camp-1")
        assert r["coordination_mode"] == "sequential"

    def test_source_type(self, bridge):
        r = bridge.orchestrate_service_to_campaign("p1", "t1", "svc-1", "camp-1")
        assert r["source_type"] == "service_to_campaign"

    def test_emits_event(self, bridge_and_engines):
        b, _, es, _ = bridge_and_engines
        before = es.event_count
        b.orchestrate_service_to_campaign("p1", "t1", "svc-1", "camp-1")
        after = es.event_count
        assert after > before

    def test_has_all_expected_keys(self, bridge):
        r = bridge.orchestrate_service_to_campaign("p1", "t1", "svc-1", "camp-1")
        expected = {"plan_id", "tenant_id", "service_ref", "campaign_ref",
                    "step_count", "coordination_mode", "source_type"}
        assert set(r.keys()) == expected


# ---------------------------------------------------------------------------
# orchestrate_case_to_remediation
# ---------------------------------------------------------------------------


class TestCaseToRemediation:

    def test_returns_dict(self, bridge):
        r = bridge.orchestrate_case_to_remediation("p2", "t1", "case-1", "rem-1")
        assert isinstance(r, dict)

    def test_plan_id(self, bridge):
        r = bridge.orchestrate_case_to_remediation("p2", "t1", "case-1", "rem-1")
        assert r["plan_id"] == "p2"

    def test_tenant_id(self, bridge):
        r = bridge.orchestrate_case_to_remediation("p2", "t1", "case-1", "rem-1")
        assert r["tenant_id"] == "t1"

    def test_case_ref(self, bridge):
        r = bridge.orchestrate_case_to_remediation("p2", "t1", "case-1", "rem-1")
        assert r["case_ref"] == "case-1"

    def test_remediation_ref(self, bridge):
        r = bridge.orchestrate_case_to_remediation("p2", "t1", "case-1", "rem-1")
        assert r["remediation_ref"] == "rem-1"

    def test_step_count(self, bridge):
        r = bridge.orchestrate_case_to_remediation("p2", "t1", "case-1", "rem-1")
        assert r["step_count"] == 2

    def test_coordination_mode(self, bridge):
        r = bridge.orchestrate_case_to_remediation("p2", "t1", "case-1", "rem-1")
        assert r["coordination_mode"] == "sequential"

    def test_source_type(self, bridge):
        r = bridge.orchestrate_case_to_remediation("p2", "t1", "case-1", "rem-1")
        assert r["source_type"] == "case_to_remediation"

    def test_emits_event(self, bridge_and_engines):
        b, _, es, _ = bridge_and_engines
        before = es.event_count
        b.orchestrate_case_to_remediation("p2", "t1", "case-1", "rem-1")
        after = es.event_count
        assert after > before

    def test_has_all_expected_keys(self, bridge):
        r = bridge.orchestrate_case_to_remediation("p2", "t1", "case-1", "rem-1")
        expected = {"plan_id", "tenant_id", "case_ref", "remediation_ref",
                    "step_count", "coordination_mode", "source_type"}
        assert set(r.keys()) == expected


# ---------------------------------------------------------------------------
# orchestrate_contract_to_billing
# ---------------------------------------------------------------------------


class TestContractToBilling:

    def test_returns_dict(self, bridge):
        r = bridge.orchestrate_contract_to_billing("p3", "t1", "ctr-1", "bill-1")
        assert isinstance(r, dict)

    def test_plan_id(self, bridge):
        r = bridge.orchestrate_contract_to_billing("p3", "t1", "ctr-1", "bill-1")
        assert r["plan_id"] == "p3"

    def test_tenant_id(self, bridge):
        r = bridge.orchestrate_contract_to_billing("p3", "t1", "ctr-1", "bill-1")
        assert r["tenant_id"] == "t1"

    def test_contract_ref(self, bridge):
        r = bridge.orchestrate_contract_to_billing("p3", "t1", "ctr-1", "bill-1")
        assert r["contract_ref"] == "ctr-1"

    def test_billing_ref(self, bridge):
        r = bridge.orchestrate_contract_to_billing("p3", "t1", "ctr-1", "bill-1")
        assert r["billing_ref"] == "bill-1"

    def test_step_count(self, bridge):
        r = bridge.orchestrate_contract_to_billing("p3", "t1", "ctr-1", "bill-1")
        assert r["step_count"] == 2

    def test_coordination_mode(self, bridge):
        r = bridge.orchestrate_contract_to_billing("p3", "t1", "ctr-1", "bill-1")
        assert r["coordination_mode"] == "sequential"

    def test_source_type(self, bridge):
        r = bridge.orchestrate_contract_to_billing("p3", "t1", "ctr-1", "bill-1")
        assert r["source_type"] == "contract_to_billing"

    def test_emits_event(self, bridge_and_engines):
        b, _, es, _ = bridge_and_engines
        before = es.event_count
        b.orchestrate_contract_to_billing("p3", "t1", "ctr-1", "bill-1")
        after = es.event_count
        assert after > before

    def test_has_all_expected_keys(self, bridge):
        r = bridge.orchestrate_contract_to_billing("p3", "t1", "ctr-1", "bill-1")
        expected = {"plan_id", "tenant_id", "contract_ref", "billing_ref",
                    "step_count", "coordination_mode", "source_type"}
        assert set(r.keys()) == expected


# ---------------------------------------------------------------------------
# orchestrate_release_to_marketplace
# ---------------------------------------------------------------------------


class TestReleaseToMarketplace:

    def test_returns_dict(self, bridge):
        r = bridge.orchestrate_release_to_marketplace("p4", "t1", "rel-1", "off-1")
        assert isinstance(r, dict)

    def test_plan_id(self, bridge):
        r = bridge.orchestrate_release_to_marketplace("p4", "t1", "rel-1", "off-1")
        assert r["plan_id"] == "p4"

    def test_tenant_id(self, bridge):
        r = bridge.orchestrate_release_to_marketplace("p4", "t1", "rel-1", "off-1")
        assert r["tenant_id"] == "t1"

    def test_release_ref(self, bridge):
        r = bridge.orchestrate_release_to_marketplace("p4", "t1", "rel-1", "off-1")
        assert r["release_ref"] == "rel-1"

    def test_offering_ref(self, bridge):
        r = bridge.orchestrate_release_to_marketplace("p4", "t1", "rel-1", "off-1")
        assert r["offering_ref"] == "off-1"

    def test_step_count(self, bridge):
        r = bridge.orchestrate_release_to_marketplace("p4", "t1", "rel-1", "off-1")
        assert r["step_count"] == 2

    def test_coordination_mode(self, bridge):
        r = bridge.orchestrate_release_to_marketplace("p4", "t1", "rel-1", "off-1")
        assert r["coordination_mode"] == "sequential"

    def test_source_type(self, bridge):
        r = bridge.orchestrate_release_to_marketplace("p4", "t1", "rel-1", "off-1")
        assert r["source_type"] == "release_to_marketplace"

    def test_emits_event(self, bridge_and_engines):
        b, _, es, _ = bridge_and_engines
        before = es.event_count
        b.orchestrate_release_to_marketplace("p4", "t1", "rel-1", "off-1")
        after = es.event_count
        assert after > before


# ---------------------------------------------------------------------------
# orchestrate_continuity_to_customer
# ---------------------------------------------------------------------------


class TestContinuityToCustomer:

    def test_returns_dict(self, bridge):
        r = bridge.orchestrate_continuity_to_customer("p5", "t1", "cont-1", "cust-1")
        assert isinstance(r, dict)

    def test_plan_id(self, bridge):
        r = bridge.orchestrate_continuity_to_customer("p5", "t1", "cont-1", "cust-1")
        assert r["plan_id"] == "p5"

    def test_tenant_id(self, bridge):
        r = bridge.orchestrate_continuity_to_customer("p5", "t1", "cont-1", "cust-1")
        assert r["tenant_id"] == "t1"

    def test_continuity_ref(self, bridge):
        r = bridge.orchestrate_continuity_to_customer("p5", "t1", "cont-1", "cust-1")
        assert r["continuity_ref"] == "cont-1"

    def test_customer_ref(self, bridge):
        r = bridge.orchestrate_continuity_to_customer("p5", "t1", "cont-1", "cust-1")
        assert r["customer_ref"] == "cust-1"

    def test_step_count(self, bridge):
        r = bridge.orchestrate_continuity_to_customer("p5", "t1", "cont-1", "cust-1")
        assert r["step_count"] == 2

    def test_coordination_mode_fallback(self, bridge):
        r = bridge.orchestrate_continuity_to_customer("p5", "t1", "cont-1", "cust-1")
        assert r["coordination_mode"] == "fallback"

    def test_source_type(self, bridge):
        r = bridge.orchestrate_continuity_to_customer("p5", "t1", "cont-1", "cust-1")
        assert r["source_type"] == "continuity_to_customer"

    def test_emits_event(self, bridge_and_engines):
        b, _, es, _ = bridge_and_engines
        before = es.event_count
        b.orchestrate_continuity_to_customer("p5", "t1", "cont-1", "cust-1")
        after = es.event_count
        assert after > before

    def test_has_all_expected_keys(self, bridge):
        r = bridge.orchestrate_continuity_to_customer("p5", "t1", "cont-1", "cust-1")
        expected = {"plan_id", "tenant_id", "continuity_ref", "customer_ref",
                    "step_count", "coordination_mode", "source_type"}
        assert set(r.keys()) == expected


# ---------------------------------------------------------------------------
# orchestrate_program_to_reporting
# ---------------------------------------------------------------------------


class TestProgramToReporting:

    def test_returns_dict(self, bridge):
        r = bridge.orchestrate_program_to_reporting("p6", "t1", "prog-1", "rpt-1")
        assert isinstance(r, dict)

    def test_plan_id(self, bridge):
        r = bridge.orchestrate_program_to_reporting("p6", "t1", "prog-1", "rpt-1")
        assert r["plan_id"] == "p6"

    def test_tenant_id(self, bridge):
        r = bridge.orchestrate_program_to_reporting("p6", "t1", "prog-1", "rpt-1")
        assert r["tenant_id"] == "t1"

    def test_program_ref(self, bridge):
        r = bridge.orchestrate_program_to_reporting("p6", "t1", "prog-1", "rpt-1")
        assert r["program_ref"] == "prog-1"

    def test_reporting_ref(self, bridge):
        r = bridge.orchestrate_program_to_reporting("p6", "t1", "prog-1", "rpt-1")
        assert r["reporting_ref"] == "rpt-1"

    def test_step_count(self, bridge):
        r = bridge.orchestrate_program_to_reporting("p6", "t1", "prog-1", "rpt-1")
        assert r["step_count"] == 2

    def test_coordination_mode_parallel(self, bridge):
        r = bridge.orchestrate_program_to_reporting("p6", "t1", "prog-1", "rpt-1")
        assert r["coordination_mode"] == "parallel"

    def test_source_type(self, bridge):
        r = bridge.orchestrate_program_to_reporting("p6", "t1", "prog-1", "rpt-1")
        assert r["source_type"] == "program_to_reporting"

    def test_emits_event(self, bridge_and_engines):
        b, _, es, _ = bridge_and_engines
        before = es.event_count
        b.orchestrate_program_to_reporting("p6", "t1", "prog-1", "rpt-1")
        after = es.event_count
        assert after > before

    def test_has_all_expected_keys(self, bridge):
        r = bridge.orchestrate_program_to_reporting("p6", "t1", "prog-1", "rpt-1")
        expected = {"plan_id", "tenant_id", "program_ref", "reporting_ref",
                    "step_count", "coordination_mode", "source_type"}
        assert set(r.keys()) == expected


# ---------------------------------------------------------------------------
# attach_orchestration_to_memory_mesh
# ---------------------------------------------------------------------------


class TestAttachToMemoryMesh:

    def test_returns_memory_record(self, bridge):
        mem = bridge.attach_orchestration_to_memory_mesh("scope-1")
        assert isinstance(mem, MemoryRecord)

    def test_scope_ref_id(self, bridge):
        mem = bridge.attach_orchestration_to_memory_mesh("scope-1")
        assert mem.scope_ref_id == "scope-1"

    def test_tags_meta_orchestration(self, bridge):
        mem = bridge.attach_orchestration_to_memory_mesh("scope-1")
        assert "meta_orchestration" in mem.tags

    def test_tags_composition(self, bridge):
        mem = bridge.attach_orchestration_to_memory_mesh("scope-1")
        assert "composition" in mem.tags

    def test_tags_cross_runtime(self, bridge):
        mem = bridge.attach_orchestration_to_memory_mesh("scope-1")
        assert "cross_runtime" in mem.tags

    def test_content_has_total_plans(self, bridge):
        mem = bridge.attach_orchestration_to_memory_mesh("scope-1")
        assert "total_plans" in mem.content

    def test_content_has_active_plans(self, bridge):
        mem = bridge.attach_orchestration_to_memory_mesh("scope-1")
        assert "active_plans" in mem.content

    def test_content_has_total_steps(self, bridge):
        mem = bridge.attach_orchestration_to_memory_mesh("scope-1")
        assert "total_steps" in mem.content

    def test_content_has_completed_steps(self, bridge):
        mem = bridge.attach_orchestration_to_memory_mesh("scope-1")
        assert "completed_steps" in mem.content

    def test_content_has_failed_steps(self, bridge):
        mem = bridge.attach_orchestration_to_memory_mesh("scope-1")
        assert "failed_steps" in mem.content

    def test_content_has_total_traces(self, bridge):
        mem = bridge.attach_orchestration_to_memory_mesh("scope-1")
        assert "total_traces" in mem.content

    def test_content_has_total_violations(self, bridge):
        mem = bridge.attach_orchestration_to_memory_mesh("scope-1")
        assert "total_violations" in mem.content

    def test_content_has_seven_keys(self, bridge):
        mem = bridge.attach_orchestration_to_memory_mesh("scope-1")
        assert len(mem.content) == 7

    def test_emits_event(self, bridge_and_engines):
        b, _, es, _ = bridge_and_engines
        before = es.event_count
        b.attach_orchestration_to_memory_mesh("scope-1")
        after = es.event_count
        assert after > before

    def test_memory_id_is_nonempty(self, bridge):
        mem = bridge.attach_orchestration_to_memory_mesh("scope-1")
        assert len(mem.memory_id) > 0

    def test_title_contains_scope(self, bridge):
        mem = bridge.attach_orchestration_to_memory_mesh("scope-abc")
        assert "scope-abc" in mem.title

    def test_after_plan_total_plans_nonzero(self, bridge):
        bridge.orchestrate_service_to_campaign("px", "t1", "s", "c")
        mem = bridge.attach_orchestration_to_memory_mesh("t1")
        assert mem.content["total_plans"] >= 1

    def test_after_plan_total_steps_nonzero(self, bridge):
        bridge.orchestrate_service_to_campaign("py", "t1", "s", "c")
        mem = bridge.attach_orchestration_to_memory_mesh("t1")
        assert mem.content["total_steps"] >= 2


# ---------------------------------------------------------------------------
# attach_orchestration_to_graph
# ---------------------------------------------------------------------------


class TestAttachToGraph:

    def test_returns_dict(self, bridge):
        r = bridge.attach_orchestration_to_graph("scope-1")
        assert isinstance(r, dict)

    def test_scope_ref_id_key(self, bridge):
        r = bridge.attach_orchestration_to_graph("scope-1")
        assert r["scope_ref_id"] == "scope-1"

    def test_has_total_plans(self, bridge):
        r = bridge.attach_orchestration_to_graph("scope-1")
        assert "total_plans" in r

    def test_has_active_plans(self, bridge):
        r = bridge.attach_orchestration_to_graph("scope-1")
        assert "active_plans" in r

    def test_has_total_steps(self, bridge):
        r = bridge.attach_orchestration_to_graph("scope-1")
        assert "total_steps" in r

    def test_has_completed_steps(self, bridge):
        r = bridge.attach_orchestration_to_graph("scope-1")
        assert "completed_steps" in r

    def test_has_failed_steps(self, bridge):
        r = bridge.attach_orchestration_to_graph("scope-1")
        assert "failed_steps" in r

    def test_has_total_traces(self, bridge):
        r = bridge.attach_orchestration_to_graph("scope-1")
        assert "total_traces" in r

    def test_has_total_violations(self, bridge):
        r = bridge.attach_orchestration_to_graph("scope-1")
        assert "total_violations" in r

    def test_has_eight_keys(self, bridge):
        r = bridge.attach_orchestration_to_graph("scope-1")
        assert len(r) == 8

    def test_after_plan_total_plans_nonzero(self, bridge):
        bridge.orchestrate_program_to_reporting("pz", "t1", "p", "r")
        r = bridge.attach_orchestration_to_graph("t1")
        assert r["total_plans"] >= 1
