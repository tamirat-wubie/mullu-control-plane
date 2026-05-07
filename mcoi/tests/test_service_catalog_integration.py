"""Comprehensive tests for the ServiceCatalogIntegration bridge.

Covers: constructor validation, request_from_* methods, bind_request_to_* methods,
memory mesh attachment, graph attachment, and event emission invariants.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.core.service_catalog_integration import ServiceCatalogIntegration
from mcoi_runtime.core.service_catalog import ServiceCatalogEngine
from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.memory_mesh import MemoryMeshEngine
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
from mcoi_runtime.contracts.service_catalog import RequestPriority, CatalogItemKind
from mcoi_runtime.contracts.memory_mesh import MemoryRecord


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def engines():
    es = EventSpineEngine()
    ce = ServiceCatalogEngine(es)
    mm = MemoryMeshEngine()
    return ce, es, mm


@pytest.fixture
def integration(engines):
    ce, es, mm = engines
    ce.register_catalog_item("svc-1", "VM Provisioning", "t1")
    return ServiceCatalogIntegration(ce, es, mm)


# ---------------------------------------------------------------------------
# 1. Constructor validation
# ---------------------------------------------------------------------------


class TestConstructorValidation:
    """Validate isinstance checks on all three constructor arguments."""

    def test_valid_construction(self, engines):
        ce, es, mm = engines
        sci = ServiceCatalogIntegration(ce, es, mm)
        assert sci is not None

    def test_wrong_catalog_engine_type(self, engines):
        _ce, es, mm = engines
        with pytest.raises(RuntimeCoreInvariantError, match="catalog_engine"):
            ServiceCatalogIntegration("not-an-engine", es, mm)

    def test_wrong_event_spine_type(self, engines):
        ce, _es, mm = engines
        with pytest.raises(RuntimeCoreInvariantError, match="event_spine"):
            ServiceCatalogIntegration(ce, "not-an-engine", mm)

    def test_wrong_memory_engine_type(self, engines):
        ce, es, _mm = engines
        with pytest.raises(RuntimeCoreInvariantError, match="memory_engine"):
            ServiceCatalogIntegration(ce, es, "not-an-engine")

    def test_none_catalog_engine(self, engines):
        _ce, es, mm = engines
        with pytest.raises(RuntimeCoreInvariantError):
            ServiceCatalogIntegration(None, es, mm)

    def test_none_event_spine(self, engines):
        ce, _es, mm = engines
        with pytest.raises(RuntimeCoreInvariantError):
            ServiceCatalogIntegration(ce, None, mm)

    def test_none_memory_engine(self, engines):
        ce, es, _mm = engines
        with pytest.raises(RuntimeCoreInvariantError):
            ServiceCatalogIntegration(ce, es, None)

    def test_int_catalog_engine(self, engines):
        _ce, es, mm = engines
        with pytest.raises(RuntimeCoreInvariantError):
            ServiceCatalogIntegration(42, es, mm)

    def test_dict_event_spine(self, engines):
        ce, _es, mm = engines
        with pytest.raises(RuntimeCoreInvariantError):
            ServiceCatalogIntegration(ce, {}, mm)


# ---------------------------------------------------------------------------
# 2. request_from_campaign_need
# ---------------------------------------------------------------------------


class TestRequestFromCampaignNeed:
    """Tests for request_from_campaign_need method."""

    def test_basic_return_keys(self, integration):
        result = integration.request_from_campaign_need(
            "r1", "svc-1", "t1", "usr-1", "camp-1",
        )
        assert isinstance(result, dict)
        for key in ("request_id", "item_id", "tenant_id", "campaign_ref",
                     "priority", "status", "source_type"):
            assert key in result

    def test_source_type_is_campaign_need(self, integration):
        result = integration.request_from_campaign_need(
            "r2", "svc-1", "t1", "usr-1", "camp-1",
        )
        assert result["source_type"] == "campaign_need"

    def test_request_id_matches(self, integration):
        result = integration.request_from_campaign_need(
            "r3", "svc-1", "t1", "usr-1", "camp-1",
        )
        assert result["request_id"] == "r3"

    def test_item_id_matches(self, integration):
        result = integration.request_from_campaign_need(
            "r4", "svc-1", "t1", "usr-1", "camp-1",
        )
        assert result["item_id"] == "svc-1"

    def test_tenant_id_matches(self, integration):
        result = integration.request_from_campaign_need(
            "r5", "svc-1", "t1", "usr-1", "camp-1",
        )
        assert result["tenant_id"] == "t1"

    def test_campaign_ref_matches(self, integration):
        result = integration.request_from_campaign_need(
            "r6", "svc-1", "t1", "usr-1", "camp-X",
        )
        assert result["campaign_ref"] == "camp-X"

    def test_default_priority_is_medium(self, integration):
        result = integration.request_from_campaign_need(
            "r7", "svc-1", "t1", "usr-1", "camp-1",
        )
        assert result["priority"] == "medium"

    def test_custom_priority_high(self, integration):
        result = integration.request_from_campaign_need(
            "r8", "svc-1", "t1", "usr-1", "camp-1",
            priority=RequestPriority.HIGH,
        )
        assert result["priority"] == "high"

    def test_custom_priority_critical(self, integration):
        result = integration.request_from_campaign_need(
            "r9", "svc-1", "t1", "usr-1", "camp-1",
            priority=RequestPriority.CRITICAL,
        )
        assert result["priority"] == "critical"

    def test_status_is_submitted(self, integration):
        result = integration.request_from_campaign_need(
            "r10", "svc-1", "t1", "usr-1", "camp-1",
        )
        assert result["status"] == "submitted"

    def test_priority_and_status_are_string_values(self, integration):
        result = integration.request_from_campaign_need(
            "r11", "svc-1", "t1", "usr-1", "camp-1",
        )
        assert isinstance(result["priority"], str)
        assert isinstance(result["status"], str)


# ---------------------------------------------------------------------------
# 3. request_from_program_need
# ---------------------------------------------------------------------------


class TestRequestFromProgramNeed:
    """Tests for request_from_program_need method."""

    def test_basic_return_keys(self, integration):
        result = integration.request_from_program_need(
            "rp1", "svc-1", "t1", "usr-1", "prog-1",
        )
        for key in ("request_id", "item_id", "tenant_id", "program_ref",
                     "priority", "status", "source_type"):
            assert key in result

    def test_source_type_is_program_need(self, integration):
        result = integration.request_from_program_need(
            "rp2", "svc-1", "t1", "usr-1", "prog-1",
        )
        assert result["source_type"] == "program_need"

    def test_program_ref_matches(self, integration):
        result = integration.request_from_program_need(
            "rp3", "svc-1", "t1", "usr-1", "prog-ABC",
        )
        assert result["program_ref"] == "prog-ABC"

    def test_default_priority_medium(self, integration):
        result = integration.request_from_program_need(
            "rp4", "svc-1", "t1", "usr-1", "prog-1",
        )
        assert result["priority"] == "medium"

    def test_custom_priority_low(self, integration):
        result = integration.request_from_program_need(
            "rp5", "svc-1", "t1", "usr-1", "prog-1",
            priority=RequestPriority.LOW,
        )
        assert result["priority"] == "low"

    def test_status_is_submitted(self, integration):
        result = integration.request_from_program_need(
            "rp6", "svc-1", "t1", "usr-1", "prog-1",
        )
        assert result["status"] == "submitted"


# ---------------------------------------------------------------------------
# 4. request_from_asset_gap
# ---------------------------------------------------------------------------


class TestRequestFromAssetGap:
    """Tests for request_from_asset_gap method."""

    def test_basic_return_keys(self, integration):
        result = integration.request_from_asset_gap(
            "ra1", "svc-1", "t1", "usr-1", "asset-1",
        )
        for key in ("request_id", "item_id", "tenant_id", "asset_ref",
                     "priority", "status", "source_type"):
            assert key in result

    def test_source_type_is_asset_gap(self, integration):
        result = integration.request_from_asset_gap(
            "ra2", "svc-1", "t1", "usr-1", "asset-1",
        )
        assert result["source_type"] == "asset_gap"

    def test_default_priority_is_high(self, integration):
        result = integration.request_from_asset_gap(
            "ra3", "svc-1", "t1", "usr-1", "asset-1",
        )
        assert result["priority"] == "high"

    def test_asset_ref_matches(self, integration):
        result = integration.request_from_asset_gap(
            "ra4", "svc-1", "t1", "usr-1", "asset-XYZ",
        )
        assert result["asset_ref"] == "asset-XYZ"

    def test_custom_priority_critical(self, integration):
        result = integration.request_from_asset_gap(
            "ra5", "svc-1", "t1", "usr-1", "asset-1",
            priority=RequestPriority.CRITICAL,
        )
        assert result["priority"] == "critical"

    def test_status_is_submitted(self, integration):
        result = integration.request_from_asset_gap(
            "ra6", "svc-1", "t1", "usr-1", "asset-1",
        )
        assert result["status"] == "submitted"


# ---------------------------------------------------------------------------
# 5. request_from_procurement_need
# ---------------------------------------------------------------------------


class TestRequestFromProcurementNeed:
    """Tests for request_from_procurement_need method."""

    def test_basic_return_keys(self, integration):
        result = integration.request_from_procurement_need(
            "rpr1", "svc-1", "t1", "usr-1", "proc-1",
        )
        for key in ("request_id", "item_id", "tenant_id", "procurement_ref",
                     "estimated_cost", "priority", "status", "source_type"):
            assert key in result

    def test_source_type_is_procurement_need(self, integration):
        result = integration.request_from_procurement_need(
            "rpr2", "svc-1", "t1", "usr-1", "proc-1",
        )
        assert result["source_type"] == "procurement_need"

    def test_procurement_ref_matches(self, integration):
        result = integration.request_from_procurement_need(
            "rpr3", "svc-1", "t1", "usr-1", "proc-ABC",
        )
        assert result["procurement_ref"] == "proc-ABC"

    def test_default_estimated_cost_zero(self, integration):
        result = integration.request_from_procurement_need(
            "rpr4", "svc-1", "t1", "usr-1", "proc-1",
        )
        assert result["estimated_cost"] == 0.0

    def test_custom_estimated_cost(self, integration):
        result = integration.request_from_procurement_need(
            "rpr5", "svc-1", "t1", "usr-1", "proc-1",
            estimated_cost=12500.50,
        )
        assert result["estimated_cost"] == 12500.50

    def test_default_priority_medium(self, integration):
        result = integration.request_from_procurement_need(
            "rpr6", "svc-1", "t1", "usr-1", "proc-1",
        )
        assert result["priority"] == "medium"

    def test_custom_priority_high(self, integration):
        result = integration.request_from_procurement_need(
            "rpr7", "svc-1", "t1", "usr-1", "proc-1",
            priority=RequestPriority.HIGH,
        )
        assert result["priority"] == "high"


# ---------------------------------------------------------------------------
# 6. bind_request_to_budget
# ---------------------------------------------------------------------------


class TestBindRequestToBudget:
    """Tests for bind_request_to_budget method."""

    def _make_request(self, integration, req_id="br1"):
        integration.request_from_campaign_need(
            req_id, "svc-1", "t1", "usr-1", "camp-1",
        )

    def test_basic_return_keys(self, integration):
        self._make_request(integration)
        result = integration.bind_request_to_budget("br1", "budget-1")
        for key in ("request_id", "item_id", "budget_ref",
                     "estimated_cost", "status", "binding_type"):
            assert key in result

    def test_binding_type_is_budget(self, integration):
        self._make_request(integration)
        result = integration.bind_request_to_budget("br1", "budget-1")
        assert result["binding_type"] == "budget"

    def test_budget_ref_matches(self, integration):
        self._make_request(integration)
        result = integration.bind_request_to_budget("br1", "budget-XYZ")
        assert result["budget_ref"] == "budget-XYZ"

    def test_request_id_matches(self, integration):
        self._make_request(integration)
        result = integration.bind_request_to_budget("br1", "budget-1")
        assert result["request_id"] == "br1"

    def test_unknown_request_raises(self, integration):
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown request_id"):
            integration.bind_request_to_budget("nonexistent", "budget-1")


# ---------------------------------------------------------------------------
# 7. bind_request_to_availability
# ---------------------------------------------------------------------------


class TestBindRequestToAvailability:
    """Tests for bind_request_to_availability method."""

    def _make_request(self, integration, req_id="ba1"):
        integration.request_from_campaign_need(
            req_id, "svc-1", "t1", "usr-1", "camp-1",
        )

    def test_basic_return_keys(self, integration):
        self._make_request(integration)
        result = integration.bind_request_to_availability("ba1", "avail-1")
        for key in ("request_id", "item_id", "availability_ref",
                     "status", "binding_type"):
            assert key in result

    def test_binding_type_is_availability(self, integration):
        self._make_request(integration)
        result = integration.bind_request_to_availability("ba1", "avail-1")
        assert result["binding_type"] == "availability"

    def test_availability_ref_matches(self, integration):
        self._make_request(integration)
        result = integration.bind_request_to_availability("ba1", "avail-window-7")
        assert result["availability_ref"] == "avail-window-7"

    def test_unknown_request_raises(self, integration):
        with pytest.raises(RuntimeCoreInvariantError):
            integration.bind_request_to_availability("nonexistent", "avail-1")


# ---------------------------------------------------------------------------
# 8. bind_request_to_contract_sla
# ---------------------------------------------------------------------------


class TestBindRequestToContractSla:
    """Tests for bind_request_to_contract_sla method."""

    def _make_request(self, integration, req_id="bc1"):
        integration.request_from_campaign_need(
            req_id, "svc-1", "t1", "usr-1", "camp-1",
        )

    def test_basic_return_keys(self, integration):
        self._make_request(integration)
        result = integration.bind_request_to_contract_sla("bc1", "contract-1", "sla-1")
        for key in ("request_id", "item_id", "contract_ref", "sla_ref",
                     "status", "binding_type"):
            assert key in result

    def test_binding_type_is_contract_sla(self, integration):
        self._make_request(integration)
        result = integration.bind_request_to_contract_sla("bc1", "contract-1", "sla-1")
        assert result["binding_type"] == "contract_sla"

    def test_contract_ref_matches(self, integration):
        self._make_request(integration)
        result = integration.bind_request_to_contract_sla("bc1", "contract-ABC", "sla-1")
        assert result["contract_ref"] == "contract-ABC"

    def test_sla_ref_matches(self, integration):
        self._make_request(integration)
        result = integration.bind_request_to_contract_sla("bc1", "contract-1", "sla-99")
        assert result["sla_ref"] == "sla-99"

    def test_unknown_request_raises(self, integration):
        with pytest.raises(RuntimeCoreInvariantError):
            integration.bind_request_to_contract_sla("nonexistent", "c1", "s1")


# ---------------------------------------------------------------------------
# 9. bind_request_to_work_campaign
# ---------------------------------------------------------------------------


class TestBindRequestToWorkCampaign:
    """Tests for bind_request_to_work_campaign method."""

    def _make_request(self, integration, req_id="bw1"):
        integration.request_from_campaign_need(
            req_id, "svc-1", "t1", "usr-1", "camp-1",
        )

    def test_basic_return_keys(self, integration):
        self._make_request(integration)
        result = integration.bind_request_to_work_campaign("bw1", "wcamp-1")
        for key in ("request_id", "item_id", "campaign_ref",
                     "status", "binding_type"):
            assert key in result

    def test_binding_type_is_work_campaign(self, integration):
        self._make_request(integration)
        result = integration.bind_request_to_work_campaign("bw1", "wcamp-1")
        assert result["binding_type"] == "work_campaign"

    def test_campaign_ref_matches(self, integration):
        self._make_request(integration)
        result = integration.bind_request_to_work_campaign("bw1", "wcamp-ABC")
        assert result["campaign_ref"] == "wcamp-ABC"

    def test_unknown_request_raises(self, integration):
        with pytest.raises(RuntimeCoreInvariantError):
            integration.bind_request_to_work_campaign("nonexistent", "wcamp-1")


# ---------------------------------------------------------------------------
# 10. attach_request_state_to_memory_mesh
# ---------------------------------------------------------------------------


class TestAttachRequestStateToMemoryMesh:
    """Tests for attach_request_state_to_memory_mesh method."""

    def test_returns_memory_record(self, integration):
        mem = integration.attach_request_state_to_memory_mesh("scope-1")
        assert isinstance(mem, MemoryRecord)

    def test_tags_are_correct(self, integration):
        mem = integration.attach_request_state_to_memory_mesh("scope-2")
        assert mem.tags == ("service_catalog", "request", "fulfillment")

    def test_scope_ref_id_matches(self, integration):
        mem = integration.attach_request_state_to_memory_mesh("scope-3")
        assert mem.scope_ref_id == "scope-3"

    def test_title_contains_scope_ref_id(self, integration):
        mem = integration.attach_request_state_to_memory_mesh("scope-4")
        assert mem.title == "Service catalog state"
        assert "scope-4" not in mem.title

    def test_content_has_catalog_count_key(self, integration):
        mem = integration.attach_request_state_to_memory_mesh("scope-5")
        assert "total_catalog_items" in mem.content

    def test_content_catalog_count_matches_engine(self, engines):
        ce, es, mm = engines
        ce.register_catalog_item("svc-1", "VM Provisioning", "t1")
        ce.register_catalog_item("svc-2", "DB Provisioning", "t1")
        sci = ServiceCatalogIntegration(ce, es, mm)
        mem = sci.attach_request_state_to_memory_mesh("scope-6")
        assert mem.content["total_catalog_items"] == 2

    def test_content_request_count_matches_engine(self, engines):
        ce, es, mm = engines
        ce.register_catalog_item("svc-1", "VM Provisioning", "t1")
        sci = ServiceCatalogIntegration(ce, es, mm)
        sci.request_from_campaign_need("r1", "svc-1", "t1", "usr-1", "camp-1")
        sci.request_from_program_need("r2", "svc-1", "t1", "usr-1", "prog-1")
        mem = sci.attach_request_state_to_memory_mesh("scope-7")
        assert mem.content["total_requests"] == 2

    def test_content_has_all_count_keys(self, integration):
        mem = integration.attach_request_state_to_memory_mesh("scope-8")
        expected_keys = (
            "total_catalog_items", "total_requests", "total_assignments",
            "total_entitlements", "total_tasks", "total_decisions",
            "total_violations", "total_assessments", "scope_ref_id",
        )
        for key in expected_keys:
            assert key in mem.content

    def test_duplicate_scope_ref_id_raises(self, integration):
        integration.attach_request_state_to_memory_mesh("scope-dup")
        with pytest.raises(RuntimeCoreInvariantError, match="duplicate memory_id"):
            integration.attach_request_state_to_memory_mesh("scope-dup")

    def test_confidence_is_one(self, integration):
        mem = integration.attach_request_state_to_memory_mesh("scope-9")
        assert mem.confidence == 1.0

    def test_source_ids_contains_scope_ref(self, integration):
        mem = integration.attach_request_state_to_memory_mesh("scope-10")
        assert "scope-10" in mem.source_ids


# ---------------------------------------------------------------------------
# 11. attach_request_state_to_graph
# ---------------------------------------------------------------------------


class TestAttachRequestStateToGraph:
    """Tests for attach_request_state_to_graph method."""

    def test_returns_dict(self, integration):
        result = integration.attach_request_state_to_graph("scope-g1")
        assert isinstance(result, dict)

    def test_scope_ref_id_matches(self, integration):
        result = integration.attach_request_state_to_graph("scope-g2")
        assert result["scope_ref_id"] == "scope-g2"

    def test_has_all_count_keys(self, integration):
        result = integration.attach_request_state_to_graph("scope-g3")
        expected_keys = (
            "scope_ref_id", "total_catalog_items", "total_requests",
            "total_assignments", "total_entitlements", "total_tasks",
            "total_decisions", "total_violations", "total_assessments",
        )
        for key in expected_keys:
            assert key in result

    def test_catalog_count_matches_engine(self, engines):
        ce, es, mm = engines
        ce.register_catalog_item("svc-1", "VM Provisioning", "t1")
        ce.register_catalog_item("svc-2", "DB Provisioning", "t1")
        ce.register_catalog_item("svc-3", "Net Provisioning", "t1")
        sci = ServiceCatalogIntegration(ce, es, mm)
        result = sci.attach_request_state_to_graph("scope-g4")
        assert result["total_catalog_items"] == 3

    def test_request_count_matches_engine(self, engines):
        ce, es, mm = engines
        ce.register_catalog_item("svc-1", "VM Provisioning", "t1")
        sci = ServiceCatalogIntegration(ce, es, mm)
        sci.request_from_asset_gap("r1", "svc-1", "t1", "usr-1", "asset-1")
        result = sci.attach_request_state_to_graph("scope-g5")
        assert result["total_requests"] == 1

    def test_zero_counts_when_empty(self, engines):
        ce, es, mm = engines
        ce.register_catalog_item("svc-1", "VM Provisioning", "t1")
        sci = ServiceCatalogIntegration(ce, es, mm)
        result = sci.attach_request_state_to_graph("scope-g6")
        assert result["total_requests"] == 0
        assert result["total_assignments"] == 0
        assert result["total_entitlements"] == 0
        assert result["total_tasks"] == 0
        assert result["total_decisions"] == 0
        assert result["total_violations"] == 0
        assert result["total_assessments"] == 0

    def test_can_call_multiple_times_same_scope(self, integration):
        r1 = integration.attach_request_state_to_graph("scope-g7")
        r2 = integration.attach_request_state_to_graph("scope-g7")
        assert r1 == r2


# ---------------------------------------------------------------------------
# 12. Event emission
# ---------------------------------------------------------------------------


class TestEventEmission:
    """Verify that event_spine.event_count increases after each method call."""

    def test_campaign_need_emits_event(self, engines):
        ce, es, mm = engines
        ce.register_catalog_item("svc-1", "VM Provisioning", "t1")
        sci = ServiceCatalogIntegration(ce, es, mm)
        before = es.event_count
        sci.request_from_campaign_need("r1", "svc-1", "t1", "usr-1", "camp-1")
        # submit_request emits 1, request_from_campaign_need emits 1 => +2
        assert es.event_count > before

    def test_program_need_emits_event(self, engines):
        ce, es, mm = engines
        ce.register_catalog_item("svc-1", "VM Provisioning", "t1")
        sci = ServiceCatalogIntegration(ce, es, mm)
        before = es.event_count
        sci.request_from_program_need("r1", "svc-1", "t1", "usr-1", "prog-1")
        assert es.event_count > before

    def test_asset_gap_emits_event(self, engines):
        ce, es, mm = engines
        ce.register_catalog_item("svc-1", "VM Provisioning", "t1")
        sci = ServiceCatalogIntegration(ce, es, mm)
        before = es.event_count
        sci.request_from_asset_gap("r1", "svc-1", "t1", "usr-1", "asset-1")
        assert es.event_count > before

    def test_procurement_need_emits_event(self, engines):
        ce, es, mm = engines
        ce.register_catalog_item("svc-1", "VM Provisioning", "t1")
        sci = ServiceCatalogIntegration(ce, es, mm)
        before = es.event_count
        sci.request_from_procurement_need("r1", "svc-1", "t1", "usr-1", "proc-1")
        assert es.event_count > before

    def test_bind_budget_emits_event(self, engines):
        ce, es, mm = engines
        ce.register_catalog_item("svc-1", "VM Provisioning", "t1")
        sci = ServiceCatalogIntegration(ce, es, mm)
        sci.request_from_campaign_need("r1", "svc-1", "t1", "usr-1", "camp-1")
        before = es.event_count
        sci.bind_request_to_budget("r1", "budget-1")
        assert es.event_count > before

    def test_bind_availability_emits_event(self, engines):
        ce, es, mm = engines
        ce.register_catalog_item("svc-1", "VM Provisioning", "t1")
        sci = ServiceCatalogIntegration(ce, es, mm)
        sci.request_from_campaign_need("r1", "svc-1", "t1", "usr-1", "camp-1")
        before = es.event_count
        sci.bind_request_to_availability("r1", "avail-1")
        assert es.event_count > before

    def test_bind_contract_sla_emits_event(self, engines):
        ce, es, mm = engines
        ce.register_catalog_item("svc-1", "VM Provisioning", "t1")
        sci = ServiceCatalogIntegration(ce, es, mm)
        sci.request_from_campaign_need("r1", "svc-1", "t1", "usr-1", "camp-1")
        before = es.event_count
        sci.bind_request_to_contract_sla("r1", "c-1", "sla-1")
        assert es.event_count > before

    def test_bind_work_campaign_emits_event(self, engines):
        ce, es, mm = engines
        ce.register_catalog_item("svc-1", "VM Provisioning", "t1")
        sci = ServiceCatalogIntegration(ce, es, mm)
        sci.request_from_campaign_need("r1", "svc-1", "t1", "usr-1", "camp-1")
        before = es.event_count
        sci.bind_request_to_work_campaign("r1", "wcamp-1")
        assert es.event_count > before

    def test_memory_mesh_attach_emits_event(self, engines):
        ce, es, mm = engines
        ce.register_catalog_item("svc-1", "VM Provisioning", "t1")
        sci = ServiceCatalogIntegration(ce, es, mm)
        before = es.event_count
        sci.attach_request_state_to_memory_mesh("scope-evt")
        assert es.event_count > before

    def test_graph_attach_does_not_emit_event(self, engines):
        ce, es, mm = engines
        ce.register_catalog_item("svc-1", "VM Provisioning", "t1")
        sci = ServiceCatalogIntegration(ce, es, mm)
        before = es.event_count
        sci.attach_request_state_to_graph("scope-evt")
        assert es.event_count == before

    def test_multiple_requests_accumulate_events(self, engines):
        ce, es, mm = engines
        ce.register_catalog_item("svc-1", "VM Provisioning", "t1")
        sci = ServiceCatalogIntegration(ce, es, mm)
        before = es.event_count
        sci.request_from_campaign_need("r1", "svc-1", "t1", "usr-1", "c1")
        sci.request_from_program_need("r2", "svc-1", "t1", "usr-1", "p1")
        sci.request_from_asset_gap("r3", "svc-1", "t1", "usr-1", "a1")
        after = es.event_count
        # Each request_from_* triggers submit_request (1 event) + _emit (1 event) = 2
        # 3 calls => at least 6 new events
        assert after - before >= 6


class TestBoundedContracts:
    def test_campaign_need_description_redacts_campaign_ref(self, engines):
        ce, es, mm = engines
        ce.register_catalog_item("svc-1", "VM Provisioning", "t1")
        sci = ServiceCatalogIntegration(ce, es, mm)
        sci.request_from_campaign_need("req-camp", "svc-1", "t1", "usr-1", "campaign-secret")
        req = ce.get_request("req-camp")
        assert req.description == "Campaign need"
        assert "campaign-secret" not in req.description

    def test_program_need_description_redacts_program_ref(self, engines):
        ce, es, mm = engines
        ce.register_catalog_item("svc-1", "VM Provisioning", "t1")
        sci = ServiceCatalogIntegration(ce, es, mm)
        sci.request_from_program_need("req-prog", "svc-1", "t1", "usr-1", "program-secret")
        req = ce.get_request("req-prog")
        assert req.description == "Program need"
        assert "program-secret" not in req.description

    def test_asset_gap_description_redacts_asset_ref(self, engines):
        ce, es, mm = engines
        ce.register_catalog_item("svc-1", "VM Provisioning", "t1")
        sci = ServiceCatalogIntegration(ce, es, mm)
        sci.request_from_asset_gap("req-asset", "svc-1", "t1", "usr-1", "asset-secret")
        req = ce.get_request("req-asset")
        assert req.description == "Asset gap"
        assert "asset-secret" not in req.description

    def test_procurement_need_description_redacts_procurement_ref(self, engines):
        ce, es, mm = engines
        ce.register_catalog_item("svc-1", "VM Provisioning", "t1")
        sci = ServiceCatalogIntegration(ce, es, mm)
        sci.request_from_procurement_need(
            "req-proc", "svc-1", "t1", "usr-1", "procurement-secret"
        )
        req = ce.get_request("req-proc")
        assert req.description == "Procurement need"
        assert "procurement-secret" not in req.description
