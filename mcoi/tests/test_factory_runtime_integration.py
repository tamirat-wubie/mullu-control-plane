"""Tests for FactoryRuntimeIntegration bridge.

Covers: constructor validation, all six bridge methods (procurement,
asset_deployment, workforce_assignment, continuity_event, service_request,
financial_budget), memory mesh attachment, graph attachment, event emission,
immutability, and cross-method interactions.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.memory_mesh import MemoryMeshEngine
from mcoi_runtime.core.factory_runtime import FactoryRuntimeEngine
from mcoi_runtime.core.factory_runtime_integration import FactoryRuntimeIntegration
from mcoi_runtime.contracts.factory_runtime import *
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError


# -----------------------------------------------------------------------
# Fixtures
# -----------------------------------------------------------------------


@pytest.fixture()
def es():
    return EventSpineEngine()


@pytest.fixture()
def mm(es):
    return MemoryMeshEngine()


@pytest.fixture()
def fe(es):
    return FactoryRuntimeEngine(es)


@pytest.fixture()
def bridge(fe, es, mm):
    return FactoryRuntimeIntegration(fe, es, mm)


# -----------------------------------------------------------------------
# Constructor validation (tests 1-6)
# -----------------------------------------------------------------------


class TestConstructorValidation:
    def test_valid_construction(self, fe, es, mm):
        b = FactoryRuntimeIntegration(fe, es, mm)
        assert b is not None

    def test_rejects_non_factory_engine(self, es, mm):
        with pytest.raises(RuntimeCoreInvariantError, match="factory_engine"):
            FactoryRuntimeIntegration("bad", es, mm)

    def test_rejects_non_event_spine(self, fe, mm):
        with pytest.raises(RuntimeCoreInvariantError, match="event_spine"):
            FactoryRuntimeIntegration(fe, "bad", mm)

    def test_rejects_non_memory_engine(self, fe, es):
        with pytest.raises(RuntimeCoreInvariantError, match="memory_engine"):
            FactoryRuntimeIntegration(fe, es, "bad")

    def test_rejects_none_factory_engine(self, es, mm):
        with pytest.raises(RuntimeCoreInvariantError):
            FactoryRuntimeIntegration(None, es, mm)

    def test_rejects_none_event_spine(self, fe, mm):
        with pytest.raises(RuntimeCoreInvariantError):
            FactoryRuntimeIntegration(fe, None, mm)


# -----------------------------------------------------------------------
# factory_from_procurement (tests 7-16)
# -----------------------------------------------------------------------


class TestFactoryFromProcurement:
    def test_returns_dict(self, bridge):
        r = bridge.factory_from_procurement(
            "p1", "t1", "Plant-1", "wo1", "prod-A", 10
        )
        assert isinstance(r, dict)

    def test_source_type_is_procurement(self, bridge):
        r = bridge.factory_from_procurement(
            "p2", "t1", "Plant-2", "wo2", "prod-B", 5
        )
        assert r["source_type"] == "procurement"

    def test_plant_id_preserved(self, bridge):
        r = bridge.factory_from_procurement(
            "p3", "t1", "Plant-3", "wo3", "prod-C", 7
        )
        assert r["plant_id"] == "p3"

    def test_tenant_id_preserved(self, bridge):
        r = bridge.factory_from_procurement(
            "p4", "t2", "Plant-4", "wo4", "prod-D", 3
        )
        assert r["tenant_id"] == "t2"

    def test_display_name_preserved(self, bridge):
        r = bridge.factory_from_procurement(
            "p5", "t1", "My Plant", "wo5", "prod-E", 1
        )
        assert r["display_name"] == "My Plant"

    def test_order_id_preserved(self, bridge):
        r = bridge.factory_from_procurement(
            "p6", "t1", "Plant-6", "wo6", "prod-F", 2
        )
        assert r["order_id"] == "wo6"

    def test_product_ref_preserved(self, bridge):
        r = bridge.factory_from_procurement(
            "p7", "t1", "Plant-7", "wo7", "prod-G", 4
        )
        assert r["product_ref"] == "prod-G"

    def test_quantity_preserved(self, bridge):
        r = bridge.factory_from_procurement(
            "p8", "t1", "Plant-8", "wo8", "prod-H", 99
        )
        assert r["quantity"] == 99

    def test_status_is_draft(self, bridge):
        r = bridge.factory_from_procurement(
            "p9", "t1", "Plant-9", "wo9", "prod-I", 1
        )
        assert r["status"] == "draft"

    def test_emits_event(self, bridge, es):
        before = es.event_count
        bridge.factory_from_procurement(
            "p10", "t1", "Plant-10", "wo10", "prod-J", 1
        )
        # register_plant emits 1 + create_work_order emits 1 + bridge emits 1
        assert es.event_count >= before + 3


# -----------------------------------------------------------------------
# factory_from_asset_deployment (tests 17-22)
# -----------------------------------------------------------------------


class TestFactoryFromAssetDeployment:
    def test_source_type(self, bridge):
        r = bridge.factory_from_asset_deployment(
            "ad-p1", "t1", "AD-Plant", "ad-wo1", "prod-ad", 5
        )
        assert r["source_type"] == "asset_deployment"

    def test_plant_created(self, bridge, fe):
        bridge.factory_from_asset_deployment(
            "ad-p2", "t1", "AD-Plant2", "ad-wo2", "prod-ad2", 3
        )
        plant = fe.get_plant("ad-p2")
        assert plant.plant_id == "ad-p2"

    def test_order_created(self, bridge, fe):
        bridge.factory_from_asset_deployment(
            "ad-p3", "t1", "AD-Plant3", "ad-wo3", "prod-ad3", 7
        )
        assert fe.order_count >= 1

    def test_custom_asset_ref(self, bridge, es):
        before = es.event_count
        bridge.factory_from_asset_deployment(
            "ad-p4", "t1", "AD-Plant4", "ad-wo4", "prod-ad4", 2,
            asset_ref="my-asset-123",
        )
        assert es.event_count > before

    def test_returns_quantity(self, bridge):
        r = bridge.factory_from_asset_deployment(
            "ad-p5", "t1", "AD-Plant5", "ad-wo5", "prod-ad5", 42
        )
        assert r["quantity"] == 42

    def test_emits_three_events(self, bridge, es):
        before = es.event_count
        bridge.factory_from_asset_deployment(
            "ad-p6", "t1", "AD-Plant6", "ad-wo6", "prod-ad6", 1
        )
        assert es.event_count >= before + 3


# -----------------------------------------------------------------------
# factory_from_workforce_assignment (tests 23-28)
# -----------------------------------------------------------------------


class TestFactoryFromWorkforceAssignment:
    def test_source_type(self, bridge):
        r = bridge.factory_from_workforce_assignment(
            "wf-p1", "t1", "WF-Plant", "wf-wo1", "prod-wf", 10
        )
        assert r["source_type"] == "workforce_assignment"

    def test_plant_registered(self, bridge, fe):
        bridge.factory_from_workforce_assignment(
            "wf-p2", "t1", "WF-Plant2", "wf-wo2", "prod-wf2", 5
        )
        assert fe.plant_count >= 1

    def test_order_status_draft(self, bridge):
        r = bridge.factory_from_workforce_assignment(
            "wf-p3", "t1", "WF-Plant3", "wf-wo3", "prod-wf3", 3
        )
        assert r["status"] == "draft"

    def test_custom_workforce_ref(self, bridge, es):
        before = es.event_count
        bridge.factory_from_workforce_assignment(
            "wf-p4", "t1", "WF-Plant4", "wf-wo4", "prod-wf4", 1,
            workforce_ref="crew-alpha",
        )
        assert es.event_count > before

    def test_display_name(self, bridge):
        r = bridge.factory_from_workforce_assignment(
            "wf-p5", "t1", "Workforce Plant", "wf-wo5", "prod-wf5", 2
        )
        assert r["display_name"] == "Workforce Plant"

    def test_product_ref(self, bridge):
        r = bridge.factory_from_workforce_assignment(
            "wf-p6", "t1", "WF-Plant6", "wf-wo6", "special-prod", 8
        )
        assert r["product_ref"] == "special-prod"


# -----------------------------------------------------------------------
# factory_from_continuity_event (tests 29-34)
# -----------------------------------------------------------------------


class TestFactoryFromContinuityEvent:
    def test_source_type(self, bridge):
        r = bridge.factory_from_continuity_event(
            "ce-p1", "t1", "CE-Plant", "ce-wo1", "prod-ce", 10
        )
        assert r["source_type"] == "continuity_event"

    def test_plant_and_order_created(self, bridge, fe):
        bridge.factory_from_continuity_event(
            "ce-p2", "t1", "CE-Plant2", "ce-wo2", "prod-ce2", 4
        )
        assert fe.plant_count >= 1
        assert fe.order_count >= 1

    def test_custom_continuity_ref(self, bridge, es):
        before = es.event_count
        bridge.factory_from_continuity_event(
            "ce-p3", "t1", "CE-Plant3", "ce-wo3", "prod-ce3", 1,
            continuity_ref="disaster-recovery-42",
        )
        assert es.event_count > before

    def test_tenant_preserved(self, bridge):
        r = bridge.factory_from_continuity_event(
            "ce-p4", "t99", "CE-Plant4", "ce-wo4", "prod-ce4", 6
        )
        assert r["tenant_id"] == "t99"

    def test_quantity(self, bridge):
        r = bridge.factory_from_continuity_event(
            "ce-p5", "t1", "CE-Plant5", "ce-wo5", "prod-ce5", 77
        )
        assert r["quantity"] == 77

    def test_emits_events(self, bridge, es):
        before = es.event_count
        bridge.factory_from_continuity_event(
            "ce-p6", "t1", "CE-Plant6", "ce-wo6", "prod-ce6", 1
        )
        assert es.event_count >= before + 3


# -----------------------------------------------------------------------
# factory_from_service_request (tests 35-40)
# -----------------------------------------------------------------------


class TestFactoryFromServiceRequest:
    def test_source_type(self, bridge):
        r = bridge.factory_from_service_request(
            "sr-p1", "t1", "SR-Plant", "sr-wo1", "prod-sr", 10
        )
        assert r["source_type"] == "service_request"

    def test_order_id(self, bridge):
        r = bridge.factory_from_service_request(
            "sr-p2", "t1", "SR-Plant2", "sr-wo2", "prod-sr2", 3
        )
        assert r["order_id"] == "sr-wo2"

    def test_custom_service_ref(self, bridge, es):
        before = es.event_count
        bridge.factory_from_service_request(
            "sr-p3", "t1", "SR-Plant3", "sr-wo3", "prod-sr3", 1,
            service_ref="ticket-9999",
        )
        assert es.event_count > before

    def test_status_draft(self, bridge):
        r = bridge.factory_from_service_request(
            "sr-p4", "t1", "SR-Plant4", "sr-wo4", "prod-sr4", 5
        )
        assert r["status"] == "draft"

    def test_plant_exists_in_engine(self, bridge, fe):
        bridge.factory_from_service_request(
            "sr-p5", "t1", "SR-Plant5", "sr-wo5", "prod-sr5", 2
        )
        p = fe.get_plant("sr-p5")
        assert p.display_name == "SR-Plant5"

    def test_emits_events(self, bridge, es):
        before = es.event_count
        bridge.factory_from_service_request(
            "sr-p6", "t1", "SR-Plant6", "sr-wo6", "prod-sr6", 1
        )
        assert es.event_count >= before + 3


# -----------------------------------------------------------------------
# factory_from_financial_budget (tests 41-46)
# -----------------------------------------------------------------------


class TestFactoryFromFinancialBudget:
    def test_source_type(self, bridge):
        r = bridge.factory_from_financial_budget(
            "fb-p1", "t1", "FB-Plant", "fb-wo1", "prod-fb", 10
        )
        assert r["source_type"] == "financial_budget"

    def test_plant_id(self, bridge):
        r = bridge.factory_from_financial_budget(
            "fb-p2", "t1", "FB-Plant2", "fb-wo2", "prod-fb2", 3
        )
        assert r["plant_id"] == "fb-p2"

    def test_custom_budget_ref(self, bridge, es):
        before = es.event_count
        bridge.factory_from_financial_budget(
            "fb-p3", "t1", "FB-Plant3", "fb-wo3", "prod-fb3", 1,
            budget_ref="budget-2026-q1",
        )
        assert es.event_count > before

    def test_quantity_preserved(self, bridge):
        r = bridge.factory_from_financial_budget(
            "fb-p4", "t1", "FB-Plant4", "fb-wo4", "prod-fb4", 200
        )
        assert r["quantity"] == 200

    def test_order_count_increments(self, bridge, fe):
        before = fe.order_count
        bridge.factory_from_financial_budget(
            "fb-p5", "t1", "FB-Plant5", "fb-wo5", "prod-fb5", 1
        )
        assert fe.order_count == before + 1

    def test_emits_events(self, bridge, es):
        before = es.event_count
        bridge.factory_from_financial_budget(
            "fb-p6", "t1", "FB-Plant6", "fb-wo6", "prod-fb6", 1
        )
        assert es.event_count >= before + 3


# -----------------------------------------------------------------------
# attach_factory_state_to_memory_mesh (tests 47-56)
# -----------------------------------------------------------------------


class TestAttachFactoryStateToMemoryMesh:
    def test_returns_memory_record(self, bridge):
        from mcoi_runtime.contracts.memory_mesh import MemoryRecord
        mem = bridge.attach_factory_state_to_memory_mesh("scope-1")
        assert isinstance(mem, MemoryRecord)

    def test_tags_include_factory(self, bridge):
        mem = bridge.attach_factory_state_to_memory_mesh("scope-2")
        assert "factory" in mem.tags

    def test_tags_include_production(self, bridge):
        mem = bridge.attach_factory_state_to_memory_mesh("scope-3")
        assert "production" in mem.tags

    def test_tags_include_quality(self, bridge):
        mem = bridge.attach_factory_state_to_memory_mesh("scope-4")
        assert "quality" in mem.tags

    def test_scope_ref_id_preserved(self, bridge):
        mem = bridge.attach_factory_state_to_memory_mesh("my-scope-ref")
        assert mem.scope_ref_id == "my-scope-ref"

    def test_title_contains_scope(self, bridge):
        mem = bridge.attach_factory_state_to_memory_mesh("alpha-scope")
        assert "alpha-scope" in mem.title

    def test_content_has_total_plants(self, bridge):
        mem = bridge.attach_factory_state_to_memory_mesh("scope-5")
        assert "total_plants" in mem.content

    def test_content_has_total_orders(self, bridge):
        mem = bridge.attach_factory_state_to_memory_mesh("scope-6")
        assert "total_orders" in mem.content

    def test_memory_count_increments(self, bridge, mm):
        before = mm.memory_count
        bridge.attach_factory_state_to_memory_mesh("scope-7")
        assert mm.memory_count == before + 1

    def test_emits_event(self, bridge, es):
        before = es.event_count
        bridge.attach_factory_state_to_memory_mesh("scope-8")
        assert es.event_count > before


# -----------------------------------------------------------------------
# attach_factory_state_to_graph (tests 57-64)
# -----------------------------------------------------------------------


class TestAttachFactoryStateToGraph:
    def test_returns_dict(self, bridge):
        g = bridge.attach_factory_state_to_graph("graph-1")
        assert isinstance(g, dict)

    def test_scope_ref_id(self, bridge):
        g = bridge.attach_factory_state_to_graph("graph-2")
        assert g["scope_ref_id"] == "graph-2"

    def test_has_total_plants(self, bridge):
        g = bridge.attach_factory_state_to_graph("graph-3")
        assert "total_plants" in g

    def test_has_total_lines(self, bridge):
        g = bridge.attach_factory_state_to_graph("graph-4")
        assert "total_lines" in g

    def test_has_total_orders(self, bridge):
        g = bridge.attach_factory_state_to_graph("graph-5")
        assert "total_orders" in g

    def test_has_total_batches(self, bridge):
        g = bridge.attach_factory_state_to_graph("graph-6")
        assert "total_batches" in g

    def test_has_total_checks(self, bridge):
        g = bridge.attach_factory_state_to_graph("graph-7")
        assert "total_checks" in g

    def test_has_total_downtime_events(self, bridge):
        g = bridge.attach_factory_state_to_graph("graph-8")
        assert "total_downtime_events" in g


# -----------------------------------------------------------------------
# Cross-method and integration tests (tests 65-70)
# -----------------------------------------------------------------------


class TestCrossMethodIntegration:
    def test_multiple_sources_different_plants(self, bridge, fe):
        bridge.factory_from_procurement(
            "cross-p1", "t1", "P1", "cross-wo1", "prod-1", 10
        )
        bridge.factory_from_asset_deployment(
            "cross-p2", "t1", "P2", "cross-wo2", "prod-2", 20
        )
        assert fe.plant_count == 2
        assert fe.order_count == 2

    def test_graph_reflects_bridge_calls(self, bridge):
        bridge.factory_from_procurement(
            "gr-p1", "t1", "P1", "gr-wo1", "prod-1", 5
        )
        g = bridge.attach_factory_state_to_graph("gr-scope")
        assert g["total_plants"] == 1
        assert g["total_orders"] == 1

    def test_memory_reflects_bridge_calls(self, bridge):
        bridge.factory_from_service_request(
            "mr-p1", "t1", "P1", "mr-wo1", "prod-1", 3
        )
        mem = bridge.attach_factory_state_to_memory_mesh("mr-scope")
        assert mem.content["total_plants"] == 1
        assert mem.content["total_orders"] == 1

    def test_duplicate_plant_id_raises(self, bridge):
        bridge.factory_from_procurement(
            "dup-p1", "t1", "P1", "dup-wo1", "prod-1", 1
        )
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate plant_id"):
            bridge.factory_from_procurement(
                "dup-p1", "t1", "P1-dup", "dup-wo2", "prod-2", 1
            )

    def test_all_six_sources_coexist(self, bridge, fe):
        bridge.factory_from_procurement(
            "all-p1", "t1", "A", "all-wo1", "pr", 1
        )
        bridge.factory_from_asset_deployment(
            "all-p2", "t1", "B", "all-wo2", "pr", 1
        )
        bridge.factory_from_workforce_assignment(
            "all-p3", "t1", "C", "all-wo3", "pr", 1
        )
        bridge.factory_from_continuity_event(
            "all-p4", "t1", "D", "all-wo4", "pr", 1
        )
        bridge.factory_from_service_request(
            "all-p5", "t1", "E", "all-wo5", "pr", 1
        )
        bridge.factory_from_financial_budget(
            "all-p6", "t1", "F", "all-wo6", "pr", 1
        )
        assert fe.plant_count == 6
        assert fe.order_count == 6

    def test_graph_has_total_violations_key(self, bridge):
        g = bridge.attach_factory_state_to_graph("viol-scope")
        assert "total_violations" in g
        assert g["total_violations"] == 0
