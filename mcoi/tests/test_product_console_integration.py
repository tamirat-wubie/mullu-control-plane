"""Tests for product console integration bridge."""

from __future__ import annotations

import pytest

from mcoi_runtime.contracts.product_console import (
    ConsoleRole,
    SurfaceDisposition,
    ViewMode,
)
from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
from mcoi_runtime.core.memory_mesh import MemoryMeshEngine
from mcoi_runtime.core.product_console import ProductConsoleEngine
from mcoi_runtime.core.product_console_integration import ProductConsoleIntegration


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_integration() -> tuple[EventSpineEngine, ProductConsoleEngine, MemoryMeshEngine, ProductConsoleIntegration]:
    es = EventSpineEngine()
    eng = ProductConsoleEngine(es)
    mem = MemoryMeshEngine()
    integ = ProductConsoleIntegration(eng, es, mem)
    return es, eng, mem, integ


# ====================================================================
# CONSTRUCTOR TESTS
# ====================================================================


class TestIntegrationConstructor:
    def test_valid_construction(self):
        es, eng, mem, integ = _make_integration()
        assert integ is not None

    def test_invalid_console_engine(self):
        es = EventSpineEngine()
        mem = MemoryMeshEngine()
        with pytest.raises(RuntimeCoreInvariantError, match="console_engine must be a ProductConsoleEngine"):
            ProductConsoleIntegration("not_an_engine", es, mem)

    def test_invalid_event_spine(self):
        es = EventSpineEngine()
        eng = ProductConsoleEngine(es)
        mem = MemoryMeshEngine()
        with pytest.raises(RuntimeCoreInvariantError, match="event_spine must be an EventSpineEngine"):
            ProductConsoleIntegration(eng, "not_an_es", mem)

    def test_invalid_memory_engine(self):
        es = EventSpineEngine()
        eng = ProductConsoleEngine(es)
        with pytest.raises(RuntimeCoreInvariantError, match="memory_engine must be a MemoryMeshEngine"):
            ProductConsoleIntegration(eng, es, "not_a_mem")

    def test_none_console_engine(self):
        es = EventSpineEngine()
        mem = MemoryMeshEngine()
        with pytest.raises(RuntimeCoreInvariantError):
            ProductConsoleIntegration(None, es, mem)

    def test_none_event_spine(self):
        es = EventSpineEngine()
        eng = ProductConsoleEngine(es)
        mem = MemoryMeshEngine()
        with pytest.raises(RuntimeCoreInvariantError):
            ProductConsoleIntegration(eng, None, mem)

    def test_none_memory_engine(self):
        es = EventSpineEngine()
        eng = ProductConsoleEngine(es)
        with pytest.raises(RuntimeCoreInvariantError):
            ProductConsoleIntegration(eng, es, None)


# ====================================================================
# CONSOLE FROM CUSTOMER RUNTIME
# ====================================================================


class TestConsoleFromCustomerRuntime:
    def test_basic(self):
        es, eng, mem, integ = _make_integration()
        result = integ.console_from_customer_runtime(
            "t-001", "cust-ref", "surf-cust", "panel-cust"
        )
        assert result["surface_id"] == "surf-cust"
        assert result["panel_id"] == "panel-cust"
        assert result["tenant_id"] == "t-001"
        assert result["customer_ref"] == "cust-ref"
        assert result["role"] == ConsoleRole.CUSTOMER_ADMIN.value
        assert result["target_runtime"] == "customer_runtime"
        assert result["source_type"] == "customer_runtime"

    def test_creates_surface(self):
        es, eng, mem, integ = _make_integration()
        integ.console_from_customer_runtime("t-001", "cust", "s1", "p1")
        assert eng.surface_count == 1
        s = eng.get_surface("s1")
        assert s.role == ConsoleRole.CUSTOMER_ADMIN

    def test_creates_panel(self):
        es, eng, mem, integ = _make_integration()
        integ.console_from_customer_runtime("t-001", "cust", "s1", "p1")
        assert eng.panel_count == 1
        p = eng.get_panel("p1")
        assert p.target_runtime == "customer_runtime"

    def test_custom_display_name(self):
        es, eng, mem, integ = _make_integration()
        result = integ.console_from_customer_runtime(
            "t-001", "cust", "s1", "p1", display_name="Custom Console"
        )
        assert result["display_name"] == "Custom Console"

    def test_emits_event(self):
        es, eng, mem, integ = _make_integration()
        count_before = es.event_count
        integ.console_from_customer_runtime("t-001", "cust", "s1", "p1")
        assert es.event_count > count_before

    def test_duplicate_surface_raises(self):
        es, eng, mem, integ = _make_integration()
        integ.console_from_customer_runtime("t-001", "cust", "s1", "p1")
        with pytest.raises(RuntimeCoreInvariantError):
            integ.console_from_customer_runtime("t-001", "cust", "s1", "p2")


# ====================================================================
# CONSOLE FROM MARKETPLACE RUNTIME
# ====================================================================


class TestConsoleFromMarketplaceRuntime:
    def test_basic(self):
        es, eng, mem, integ = _make_integration()
        result = integ.console_from_marketplace_runtime(
            "t-001", "mkt-ref", "surf-mkt", "panel-mkt"
        )
        assert result["surface_id"] == "surf-mkt"
        assert result["panel_id"] == "panel-mkt"
        assert result["marketplace_ref"] == "mkt-ref"
        assert result["role"] == ConsoleRole.PARTNER_ADMIN.value
        assert result["target_runtime"] == "marketplace_runtime"
        assert result["source_type"] == "marketplace_runtime"

    def test_creates_surface_with_partner_role(self):
        es, eng, mem, integ = _make_integration()
        integ.console_from_marketplace_runtime("t-001", "mkt", "s1", "p1")
        s = eng.get_surface("s1")
        assert s.role == ConsoleRole.PARTNER_ADMIN

    def test_creates_panel_with_marketplace_runtime(self):
        es, eng, mem, integ = _make_integration()
        integ.console_from_marketplace_runtime("t-001", "mkt", "s1", "p1")
        p = eng.get_panel("p1")
        assert p.target_runtime == "marketplace_runtime"

    def test_emits_event(self):
        es, eng, mem, integ = _make_integration()
        count_before = es.event_count
        integ.console_from_marketplace_runtime("t-001", "mkt", "s1", "p1")
        assert es.event_count > count_before


# ====================================================================
# CONSOLE FROM SERVICE CATALOG
# ====================================================================


class TestConsoleFromServiceCatalog:
    def test_basic(self):
        es, eng, mem, integ = _make_integration()
        result = integ.console_from_service_catalog(
            "t-001", "svc-ref", "surf-svc", "panel-svc"
        )
        assert result["surface_id"] == "surf-svc"
        assert result["service_ref"] == "svc-ref"
        assert result["role"] == ConsoleRole.OPERATIONS_MANAGER.value
        assert result["target_runtime"] == "service_catalog"
        assert result["source_type"] == "service_catalog"

    def test_creates_surface_with_ops_role(self):
        es, eng, mem, integ = _make_integration()
        integ.console_from_service_catalog("t-001", "svc", "s1", "p1")
        s = eng.get_surface("s1")
        assert s.role == ConsoleRole.OPERATIONS_MANAGER

    def test_emits_event(self):
        es, eng, mem, integ = _make_integration()
        count_before = es.event_count
        integ.console_from_service_catalog("t-001", "svc", "s1", "p1")
        assert es.event_count > count_before


# ====================================================================
# CONSOLE FROM WORKFORCE RUNTIME
# ====================================================================


class TestConsoleFromWorkforceRuntime:
    def test_basic(self):
        es, eng, mem, integ = _make_integration()
        result = integ.console_from_workforce_runtime(
            "t-001", "wf-ref", "surf-wf", "panel-wf"
        )
        assert result["surface_id"] == "surf-wf"
        assert result["workforce_ref"] == "wf-ref"
        assert result["role"] == ConsoleRole.WORKSPACE_ADMIN.value
        assert result["target_runtime"] == "workforce_runtime"
        assert result["source_type"] == "workforce_runtime"

    def test_creates_surface_with_workspace_admin_role(self):
        es, eng, mem, integ = _make_integration()
        integ.console_from_workforce_runtime("t-001", "wf", "s1", "p1")
        s = eng.get_surface("s1")
        assert s.role == ConsoleRole.WORKSPACE_ADMIN

    def test_emits_event(self):
        es, eng, mem, integ = _make_integration()
        count_before = es.event_count
        integ.console_from_workforce_runtime("t-001", "wf", "s1", "p1")
        assert es.event_count > count_before


# ====================================================================
# CONSOLE FROM BILLING AND SETTLEMENT
# ====================================================================


class TestConsoleFromBillingAndSettlement:
    def test_basic(self):
        es, eng, mem, integ = _make_integration()
        result = integ.console_from_billing_and_settlement(
            "t-001", "bill-ref", "surf-bill", "panel-bill"
        )
        assert result["surface_id"] == "surf-bill"
        assert result["billing_ref"] == "bill-ref"
        assert result["role"] == ConsoleRole.TENANT_ADMIN.value
        assert result["target_runtime"] == "billing_settlement"
        assert result["source_type"] == "billing_settlement"

    def test_creates_surface_with_tenant_admin_role(self):
        es, eng, mem, integ = _make_integration()
        integ.console_from_billing_and_settlement("t-001", "bill", "s1", "p1")
        s = eng.get_surface("s1")
        assert s.role == ConsoleRole.TENANT_ADMIN

    def test_emits_event(self):
        es, eng, mem, integ = _make_integration()
        count_before = es.event_count
        integ.console_from_billing_and_settlement("t-001", "bill", "s1", "p1")
        assert es.event_count > count_before


# ====================================================================
# CONSOLE FROM CONSTITUTIONAL GOVERNANCE
# ====================================================================


class TestConsoleFromConstitutionalGovernance:
    def test_basic(self):
        es, eng, mem, integ = _make_integration()
        result = integ.console_from_constitutional_governance(
            "t-001", "gov-ref", "surf-gov", "panel-gov"
        )
        assert result["surface_id"] == "surf-gov"
        assert result["governance_ref"] == "gov-ref"
        assert result["role"] == ConsoleRole.COMPLIANCE_VIEWER.value
        assert result["target_runtime"] == "constitutional_governance"
        assert result["source_type"] == "constitutional_governance"

    def test_creates_surface_with_compliance_viewer_role(self):
        es, eng, mem, integ = _make_integration()
        integ.console_from_constitutional_governance("t-001", "gov", "s1", "p1")
        s = eng.get_surface("s1")
        assert s.role == ConsoleRole.COMPLIANCE_VIEWER

    def test_emits_event(self):
        es, eng, mem, integ = _make_integration()
        count_before = es.event_count
        integ.console_from_constitutional_governance("t-001", "gov", "s1", "p1")
        assert es.event_count > count_before


# ====================================================================
# MEMORY MESH ATTACHMENT
# ====================================================================


class TestAttachConsoleStateToMemoryMesh:
    def test_basic(self):
        es, eng, mem, integ = _make_integration()
        integ.console_from_customer_runtime("t-001", "cust", "s1", "p1")
        record = integ.attach_console_state_to_memory_mesh("scope-ref-1")
        assert record.title == "Product console state"
        assert "product_console" in record.tags

    def test_memory_content_reflects_state(self):
        es, eng, mem, integ = _make_integration()
        integ.console_from_customer_runtime("t-001", "cust", "s1", "p1")
        record = integ.attach_console_state_to_memory_mesh("scope-ref-1")
        assert record.content["surfaces"] == 1
        assert record.content["panels"] == 1

    def test_adds_to_memory_engine(self):
        es, eng, mem, integ = _make_integration()
        integ.console_from_customer_runtime("t-001", "cust", "s1", "p1")
        before = mem.memory_count
        integ.attach_console_state_to_memory_mesh("scope-ref-1")
        assert mem.memory_count == before + 1

    def test_emits_event(self):
        es, eng, mem, integ = _make_integration()
        integ.console_from_customer_runtime("t-001", "cust", "s1", "p1")
        count_before = es.event_count
        integ.attach_console_state_to_memory_mesh("scope-ref-1")
        assert es.event_count > count_before

    def test_multiple_attachments(self):
        es, eng, mem, integ = _make_integration()
        integ.console_from_customer_runtime("t-001", "cust", "s1", "p1")
        integ.attach_console_state_to_memory_mesh("scope-1")
        integ.console_from_marketplace_runtime("t-001", "mkt", "s2", "p2")
        integ.attach_console_state_to_memory_mesh("scope-2")
        assert mem.memory_count >= 2


# ====================================================================
# GRAPH ATTACHMENT
# ====================================================================


class TestAttachConsoleStateToGraph:
    def test_basic(self):
        es, eng, mem, integ = _make_integration()
        integ.console_from_customer_runtime("t-001", "cust", "s1", "p1")
        result = integ.attach_console_state_to_graph("scope-ref-1")
        assert result["scope_ref_id"] == "scope-ref-1"
        assert result["surfaces"] == 1
        assert result["panels"] == 1

    def test_reflects_multiple_surfaces(self):
        es, eng, mem, integ = _make_integration()
        integ.console_from_customer_runtime("t-001", "cust", "s1", "p1")
        integ.console_from_marketplace_runtime("t-001", "mkt", "s2", "p2")
        result = integ.attach_console_state_to_graph("scope")
        assert result["surfaces"] == 2
        assert result["panels"] == 2

    def test_empty_state(self):
        es, eng, mem, integ = _make_integration()
        result = integ.attach_console_state_to_graph("scope")
        assert result["surfaces"] == 0
        assert result["panels"] == 0
        assert result["sessions"] == 0

    def test_includes_all_counts(self):
        es, eng, mem, integ = _make_integration()
        result = integ.attach_console_state_to_graph("scope")
        assert "surfaces" in result
        assert "nodes" in result
        assert "panels" in result
        assert "sessions" in result
        assert "actions" in result
        assert "decisions" in result
        assert "violations" in result


# ====================================================================
# CROSS-LAYER INTEGRATION
# ====================================================================


class TestCrossLayerIntegration:
    def test_all_runtime_sources(self):
        """All six runtime sources create surfaces and panels."""
        es, eng, mem, integ = _make_integration()
        integ.console_from_customer_runtime("t-001", "c", "s1", "p1")
        integ.console_from_marketplace_runtime("t-001", "m", "s2", "p2")
        integ.console_from_service_catalog("t-001", "sc", "s3", "p3")
        integ.console_from_workforce_runtime("t-001", "w", "s4", "p4")
        integ.console_from_billing_and_settlement("t-001", "b", "s5", "p5")
        integ.console_from_constitutional_governance("t-001", "g", "s6", "p6")
        assert eng.surface_count == 6
        assert eng.panel_count == 6

    def test_multi_tenant_integration(self):
        """Different tenants get separate surfaces."""
        es, eng, mem, integ = _make_integration()
        integ.console_from_customer_runtime("t-001", "c1", "s1", "p1")
        integ.console_from_customer_runtime("t-002", "c2", "s2", "p2")
        assert len(eng.surfaces_for_tenant("t-001")) == 1
        assert len(eng.surfaces_for_tenant("t-002")) == 1

    def test_integration_then_session_and_action(self):
        """Full flow: create via integration, then session and action."""
        es, eng, mem, integ = _make_integration()
        result = integ.console_from_billing_and_settlement("t-001", "bill", "bs", "bp")
        eng.start_console_session("bsess", "t-001", "admin-1", "bs")
        act = eng.record_admin_action("bact", "t-001", "bsess", "bp", "approve_invoice")
        eng.execute_action("bact")
        assert eng.action_count == 1

    def test_memory_reflects_full_state(self):
        """Memory mesh records the full engine state."""
        es, eng, mem, integ = _make_integration()
        integ.console_from_customer_runtime("t-001", "c", "s1", "p1")
        integ.console_from_marketplace_runtime("t-001", "m", "s2", "p2")
        eng.start_console_session("sess-001", "t-001", "id-001", "s1")
        eng.register_navigation_node("n1", "t-001", "s1", "Nav")
        record = integ.attach_console_state_to_memory_mesh("full-state")
        assert record.content["surfaces"] == 2
        assert record.content["panels"] == 2
        assert record.content["sessions"] == 1
        assert record.content["nodes"] == 1
