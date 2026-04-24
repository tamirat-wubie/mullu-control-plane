"""Tests for ProcurementRuntimeIntegration bridge.

Covers constructor validation, all 9 methods (procurement creation from budget,
contract renewal, connector requirement, asset need; vendor risk from faults;
PO-to-financial binding; vendor-to-contract binding; memory mesh attachment;
graph attachment), event emission, and a full lifecycle golden path.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
from mcoi_runtime.core.memory_mesh import MemoryMeshEngine
from mcoi_runtime.core.procurement_runtime import ProcurementRuntimeEngine
from mcoi_runtime.core.procurement_runtime_integration import ProcurementRuntimeIntegration
from mcoi_runtime.contracts.memory_mesh import MemoryRecord


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def event_spine() -> EventSpineEngine:
    return EventSpineEngine()


@pytest.fixture()
def procurement_engine(event_spine: EventSpineEngine) -> ProcurementRuntimeEngine:
    engine = ProcurementRuntimeEngine(event_spine)
    engine.register_vendor("v1", "Acme", "t1")
    return engine


@pytest.fixture()
def memory_engine() -> MemoryMeshEngine:
    return MemoryMeshEngine()


@pytest.fixture()
def integration(
    procurement_engine: ProcurementRuntimeEngine,
    event_spine: EventSpineEngine,
    memory_engine: MemoryMeshEngine,
) -> ProcurementRuntimeIntegration:
    return ProcurementRuntimeIntegration(procurement_engine, event_spine, memory_engine)


def _create_po(procurement_engine: ProcurementRuntimeEngine) -> str:
    """Helper: create a PO via the full request lifecycle. Returns po_id."""
    procurement_engine.create_request("req-po", "v1", "t1", 5000.0)
    procurement_engine.submit_request("req-po")
    procurement_engine.approve_request("req-po", decided_by="approver-1")
    procurement_engine.issue_po("po-1", "req-po")
    return "po-1"


# ---------------------------------------------------------------------------
# Constructor validation
# ---------------------------------------------------------------------------


class TestConstructorValidation:
    def test_rejects_wrong_procurement_engine_type(
        self, event_spine: EventSpineEngine, memory_engine: MemoryMeshEngine
    ) -> None:
        with pytest.raises(RuntimeCoreInvariantError, match="procurement_engine"):
            ProcurementRuntimeIntegration("not-an-engine", event_spine, memory_engine)

    def test_rejects_wrong_event_spine_type(
        self, procurement_engine: ProcurementRuntimeEngine, memory_engine: MemoryMeshEngine
    ) -> None:
        with pytest.raises(RuntimeCoreInvariantError, match="event_spine"):
            ProcurementRuntimeIntegration(procurement_engine, "not-a-spine", memory_engine)

    def test_rejects_wrong_memory_engine_type(
        self, procurement_engine: ProcurementRuntimeEngine, event_spine: EventSpineEngine
    ) -> None:
        with pytest.raises(RuntimeCoreInvariantError, match="memory_engine"):
            ProcurementRuntimeIntegration(procurement_engine, event_spine, 42)

    def test_accepts_valid_arguments(
        self,
        procurement_engine: ProcurementRuntimeEngine,
        event_spine: EventSpineEngine,
        memory_engine: MemoryMeshEngine,
    ) -> None:
        pri = ProcurementRuntimeIntegration(procurement_engine, event_spine, memory_engine)
        assert pri is not None


# ---------------------------------------------------------------------------
# procurement_from_budget_need
# ---------------------------------------------------------------------------


class TestProcurementFromBudgetNeed:
    def test_returns_expected_keys(self, integration: ProcurementRuntimeIntegration) -> None:
        result = integration.procurement_from_budget_need(
            "req-1", "v1", "t1", "budget-ref-1", 1000.0
        )
        assert set(result.keys()) == {
            "request_id", "vendor_id", "tenant_id", "budget_ref",
            "estimated_amount", "status", "source_type",
        }

    def test_source_type_is_budget_need(self, integration: ProcurementRuntimeIntegration) -> None:
        result = integration.procurement_from_budget_need(
            "req-1", "v1", "t1", "budget-ref-1", 1000.0
        )
        assert result["source_type"] == "budget_need"

    def test_status_is_draft(self, integration: ProcurementRuntimeIntegration) -> None:
        result = integration.procurement_from_budget_need(
            "req-1", "v1", "t1", "budget-ref-1", 1000.0
        )
        assert result["status"] == "draft"

    def test_request_id_matches(self, integration: ProcurementRuntimeIntegration) -> None:
        result = integration.procurement_from_budget_need(
            "req-99", "v1", "t1", "budget-ref-1", 500.0
        )
        assert result["request_id"] == "req-99"

    def test_vendor_id_matches(self, integration: ProcurementRuntimeIntegration) -> None:
        result = integration.procurement_from_budget_need(
            "req-1", "v1", "t1", "budget-ref-1", 500.0
        )
        assert result["vendor_id"] == "v1"

    def test_tenant_id_matches(self, integration: ProcurementRuntimeIntegration) -> None:
        result = integration.procurement_from_budget_need(
            "req-1", "v1", "t1", "budget-ref-1", 500.0
        )
        assert result["tenant_id"] == "t1"

    def test_budget_ref_matches(self, integration: ProcurementRuntimeIntegration) -> None:
        result = integration.procurement_from_budget_need(
            "req-1", "v1", "t1", "budget-ref-42", 500.0
        )
        assert result["budget_ref"] == "budget-ref-42"

    def test_estimated_amount_matches(self, integration: ProcurementRuntimeIntegration) -> None:
        result = integration.procurement_from_budget_need(
            "req-1", "v1", "t1", "budget-ref-1", 2345.67
        )
        assert result["estimated_amount"] == 2345.67

    def test_custom_currency(self, integration: ProcurementRuntimeIntegration) -> None:
        result = integration.procurement_from_budget_need(
            "req-1", "v1", "t1", "budget-ref-1", 100.0, currency="EUR"
        )
        assert result["source_type"] == "budget_need"

    def test_description_is_bounded(
        self,
        integration: ProcurementRuntimeIntegration,
        procurement_engine: ProcurementRuntimeEngine,
    ) -> None:
        result = integration.procurement_from_budget_need(
            "req-bounded", "v1", "t1", "budget-ref-secret", 1000.0
        )
        request = procurement_engine.get_request(result["request_id"])
        assert request.description == "Budget need"
        assert "budget-ref-secret" not in request.description
        assert request.request_id == "req-bounded"


# ---------------------------------------------------------------------------
# procurement_from_contract_renewal
# ---------------------------------------------------------------------------


class TestProcurementFromContractRenewal:
    def test_returns_expected_keys(self, integration: ProcurementRuntimeIntegration) -> None:
        result = integration.procurement_from_contract_renewal(
            "ren-1", "v1", "contract-ref-1", "2026-01-01", "2026-12-31"
        )
        assert set(result.keys()) == {
            "renewal_id", "vendor_id", "contract_ref", "disposition", "source_type",
        }

    def test_source_type_is_contract_renewal(self, integration: ProcurementRuntimeIntegration) -> None:
        result = integration.procurement_from_contract_renewal(
            "ren-1", "v1", "contract-ref-1", "2026-01-01", "2026-12-31"
        )
        assert result["source_type"] == "contract_renewal"

    def test_disposition_is_pending(self, integration: ProcurementRuntimeIntegration) -> None:
        result = integration.procurement_from_contract_renewal(
            "ren-1", "v1", "contract-ref-1", "2026-01-01", "2026-12-31"
        )
        assert result["disposition"] == "pending"

    def test_renewal_id_matches(self, integration: ProcurementRuntimeIntegration) -> None:
        result = integration.procurement_from_contract_renewal(
            "ren-55", "v1", "contract-ref-1", "2026-01-01", "2026-12-31"
        )
        assert result["renewal_id"] == "ren-55"

    def test_vendor_id_matches(self, integration: ProcurementRuntimeIntegration) -> None:
        result = integration.procurement_from_contract_renewal(
            "ren-1", "v1", "contract-ref-1", "2026-01-01", "2026-12-31"
        )
        assert result["vendor_id"] == "v1"

    def test_contract_ref_matches(self, integration: ProcurementRuntimeIntegration) -> None:
        result = integration.procurement_from_contract_renewal(
            "ren-1", "v1", "contract-ref-77", "2026-01-01", "2026-12-31"
        )
        assert result["contract_ref"] == "contract-ref-77"


# ---------------------------------------------------------------------------
# procurement_from_connector_requirement
# ---------------------------------------------------------------------------


class TestProcurementFromConnectorRequirement:
    def test_returns_expected_keys(self, integration: ProcurementRuntimeIntegration) -> None:
        result = integration.procurement_from_connector_requirement(
            "req-c1", "v1", "t1", "conn-ref-1", 800.0
        )
        assert set(result.keys()) == {
            "request_id", "vendor_id", "tenant_id", "connector_ref",
            "estimated_amount", "status", "source_type",
        }

    def test_source_type_is_connector_requirement(self, integration: ProcurementRuntimeIntegration) -> None:
        result = integration.procurement_from_connector_requirement(
            "req-c1", "v1", "t1", "conn-ref-1", 800.0
        )
        assert result["source_type"] == "connector_requirement"

    def test_status_is_draft(self, integration: ProcurementRuntimeIntegration) -> None:
        result = integration.procurement_from_connector_requirement(
            "req-c1", "v1", "t1", "conn-ref-1", 800.0
        )
        assert result["status"] == "draft"

    def test_connector_ref_matches(self, integration: ProcurementRuntimeIntegration) -> None:
        result = integration.procurement_from_connector_requirement(
            "req-c1", "v1", "t1", "conn-ref-42", 800.0
        )
        assert result["connector_ref"] == "conn-ref-42"

    def test_estimated_amount_matches(self, integration: ProcurementRuntimeIntegration) -> None:
        result = integration.procurement_from_connector_requirement(
            "req-c1", "v1", "t1", "conn-ref-1", 1234.56
        )
        assert result["estimated_amount"] == 1234.56

    def test_description_is_bounded(
        self,
        integration: ProcurementRuntimeIntegration,
        procurement_engine: ProcurementRuntimeEngine,
    ) -> None:
        result = integration.procurement_from_connector_requirement(
            "req-connector-bounded", "v1", "t1", "conn-ref-secret", 800.0
        )
        request = procurement_engine.get_request(result["request_id"])
        assert request.description == "Connector requirement"
        assert "conn-ref-secret" not in request.description
        assert request.request_id == "req-connector-bounded"


# ---------------------------------------------------------------------------
# procurement_from_asset_need
# ---------------------------------------------------------------------------


class TestProcurementFromAssetNeed:
    def test_returns_expected_keys(self, integration: ProcurementRuntimeIntegration) -> None:
        result = integration.procurement_from_asset_need(
            "req-a1", "v1", "t1", "asset-ref-1", 600.0
        )
        assert set(result.keys()) == {
            "request_id", "vendor_id", "tenant_id", "asset_ref",
            "estimated_amount", "status", "source_type",
        }

    def test_source_type_is_asset_need(self, integration: ProcurementRuntimeIntegration) -> None:
        result = integration.procurement_from_asset_need(
            "req-a1", "v1", "t1", "asset-ref-1", 600.0
        )
        assert result["source_type"] == "asset_need"

    def test_status_is_draft(self, integration: ProcurementRuntimeIntegration) -> None:
        result = integration.procurement_from_asset_need(
            "req-a1", "v1", "t1", "asset-ref-1", 600.0
        )
        assert result["status"] == "draft"

    def test_asset_ref_matches(self, integration: ProcurementRuntimeIntegration) -> None:
        result = integration.procurement_from_asset_need(
            "req-a1", "v1", "t1", "asset-ref-77", 600.0
        )
        assert result["asset_ref"] == "asset-ref-77"

    def test_estimated_amount_matches(self, integration: ProcurementRuntimeIntegration) -> None:
        result = integration.procurement_from_asset_need(
            "req-a1", "v1", "t1", "asset-ref-1", 999.99
        )
        assert result["estimated_amount"] == 999.99

    def test_description_is_bounded(
        self,
        integration: ProcurementRuntimeIntegration,
        procurement_engine: ProcurementRuntimeEngine,
    ) -> None:
        result = integration.procurement_from_asset_need(
            "req-asset-bounded", "v1", "t1", "asset-ref-secret", 600.0
        )
        request = procurement_engine.get_request(result["request_id"])
        assert request.description == "Asset need"
        assert "asset-ref-secret" not in request.description
        assert request.request_id == "req-asset-bounded"


# ---------------------------------------------------------------------------
# vendor_risk_from_faults
# ---------------------------------------------------------------------------


class TestVendorRiskFromFaults:
    def test_returns_expected_keys(self, integration: ProcurementRuntimeIntegration) -> None:
        result = integration.vendor_risk_from_faults("assess-1", "v1", 0.9, 0)
        assert set(result.keys()) == {
            "assessment_id", "vendor_id", "risk_level", "performance_score",
            "fault_count", "source_type",
        }

    def test_source_type_is_fault_history(self, integration: ProcurementRuntimeIntegration) -> None:
        result = integration.vendor_risk_from_faults("assess-1", "v1", 0.9, 0)
        assert result["source_type"] == "fault_history"

    def test_low_risk_for_good_vendor(self, integration: ProcurementRuntimeIntegration) -> None:
        result = integration.vendor_risk_from_faults("assess-1", "v1", 0.95, 0)
        assert result["risk_level"] == "low"

    def test_medium_risk_for_one_fault(self, integration: ProcurementRuntimeIntegration) -> None:
        result = integration.vendor_risk_from_faults("assess-1", "v1", 0.85, 1)
        assert result["risk_level"] == "medium"

    def test_high_risk_for_many_faults(self, integration: ProcurementRuntimeIntegration) -> None:
        result = integration.vendor_risk_from_faults("assess-1", "v1", 0.6, 3)
        assert result["risk_level"] == "high"

    def test_critical_risk_for_severe_faults(self, integration: ProcurementRuntimeIntegration) -> None:
        result = integration.vendor_risk_from_faults("assess-1", "v1", 0.1, 5)
        assert result["risk_level"] == "critical"

    def test_assessment_id_matches(self, integration: ProcurementRuntimeIntegration) -> None:
        result = integration.vendor_risk_from_faults("assess-42", "v1", 0.9, 0)
        assert result["assessment_id"] == "assess-42"

    def test_vendor_id_matches(self, integration: ProcurementRuntimeIntegration) -> None:
        result = integration.vendor_risk_from_faults("assess-1", "v1", 0.9, 0)
        assert result["vendor_id"] == "v1"

    def test_performance_score_matches(self, integration: ProcurementRuntimeIntegration) -> None:
        result = integration.vendor_risk_from_faults("assess-1", "v1", 0.77, 0)
        assert result["performance_score"] == 0.77

    def test_fault_count_matches(self, integration: ProcurementRuntimeIntegration) -> None:
        result = integration.vendor_risk_from_faults("assess-1", "v1", 0.9, 2)
        assert result["fault_count"] == 2

    def test_custom_assessed_by(self, integration: ProcurementRuntimeIntegration) -> None:
        result = integration.vendor_risk_from_faults(
            "assess-1", "v1", 0.9, 0, assessed_by="custom_engine"
        )
        assert result["source_type"] == "fault_history"


# ---------------------------------------------------------------------------
# bind_po_to_financial_runtime
# ---------------------------------------------------------------------------


class TestBindPoToFinancialRuntime:
    def test_returns_expected_keys(
        self,
        integration: ProcurementRuntimeIntegration,
        procurement_engine: ProcurementRuntimeEngine,
    ) -> None:
        _create_po(procurement_engine)
        result = integration.bind_po_to_financial_runtime("po-1", "inv-ref-1")
        assert set(result.keys()) == {
            "po_id", "vendor_id", "amount", "invoice_ref", "status", "binding_type",
        }

    def test_binding_type_is_financial(
        self,
        integration: ProcurementRuntimeIntegration,
        procurement_engine: ProcurementRuntimeEngine,
    ) -> None:
        _create_po(procurement_engine)
        result = integration.bind_po_to_financial_runtime("po-1", "inv-ref-1")
        assert result["binding_type"] == "financial"

    def test_po_id_matches(
        self,
        integration: ProcurementRuntimeIntegration,
        procurement_engine: ProcurementRuntimeEngine,
    ) -> None:
        _create_po(procurement_engine)
        result = integration.bind_po_to_financial_runtime("po-1", "inv-ref-1")
        assert result["po_id"] == "po-1"

    def test_vendor_id_matches(
        self,
        integration: ProcurementRuntimeIntegration,
        procurement_engine: ProcurementRuntimeEngine,
    ) -> None:
        _create_po(procurement_engine)
        result = integration.bind_po_to_financial_runtime("po-1", "inv-ref-1")
        assert result["vendor_id"] == "v1"

    def test_amount_matches(
        self,
        integration: ProcurementRuntimeIntegration,
        procurement_engine: ProcurementRuntimeEngine,
    ) -> None:
        _create_po(procurement_engine)
        result = integration.bind_po_to_financial_runtime("po-1", "inv-ref-1")
        assert result["amount"] == 5000.0

    def test_invoice_ref_matches(
        self,
        integration: ProcurementRuntimeIntegration,
        procurement_engine: ProcurementRuntimeEngine,
    ) -> None:
        _create_po(procurement_engine)
        result = integration.bind_po_to_financial_runtime("po-1", "inv-ref-77")
        assert result["invoice_ref"] == "inv-ref-77"

    def test_status_is_lowercase(
        self,
        integration: ProcurementRuntimeIntegration,
        procurement_engine: ProcurementRuntimeEngine,
    ) -> None:
        _create_po(procurement_engine)
        result = integration.bind_po_to_financial_runtime("po-1", "inv-ref-1")
        assert result["status"] == result["status"].lower()


# ---------------------------------------------------------------------------
# bind_vendor_to_contract_runtime
# ---------------------------------------------------------------------------


class TestBindVendorToContractRuntime:
    def test_returns_expected_keys(self, integration: ProcurementRuntimeIntegration) -> None:
        result = integration.bind_vendor_to_contract_runtime(
            "commit-1", "v1", "contract-ref-1"
        )
        assert set(result.keys()) == {
            "commitment_id", "vendor_id", "contract_ref", "binding_type",
        }

    def test_binding_type_is_contract(self, integration: ProcurementRuntimeIntegration) -> None:
        result = integration.bind_vendor_to_contract_runtime(
            "commit-1", "v1", "contract-ref-1"
        )
        assert result["binding_type"] == "contract"

    def test_commitment_id_matches(self, integration: ProcurementRuntimeIntegration) -> None:
        result = integration.bind_vendor_to_contract_runtime(
            "commit-42", "v1", "contract-ref-1"
        )
        assert result["commitment_id"] == "commit-42"

    def test_vendor_id_matches(self, integration: ProcurementRuntimeIntegration) -> None:
        result = integration.bind_vendor_to_contract_runtime(
            "commit-1", "v1", "contract-ref-1"
        )
        assert result["vendor_id"] == "v1"

    def test_contract_ref_matches(self, integration: ProcurementRuntimeIntegration) -> None:
        result = integration.bind_vendor_to_contract_runtime(
            "commit-1", "v1", "contract-ref-99"
        )
        assert result["contract_ref"] == "contract-ref-99"

    def test_with_description_and_target_value(self, integration: ProcurementRuntimeIntegration) -> None:
        result = integration.bind_vendor_to_contract_runtime(
            "commit-1", "v1", "contract-ref-1",
            description="SLA commitment", target_value="99.9%",
        )
        assert result["binding_type"] == "contract"


# ---------------------------------------------------------------------------
# attach_procurement_to_memory_mesh
# ---------------------------------------------------------------------------


class TestAttachProcurementToMemoryMesh:
    def test_returns_memory_record(
        self, integration: ProcurementRuntimeIntegration
    ) -> None:
        mem = integration.attach_procurement_to_memory_mesh("scope-1")
        assert isinstance(mem, MemoryRecord)

    def test_tags_contain_expected_values(
        self, integration: ProcurementRuntimeIntegration
    ) -> None:
        mem = integration.attach_procurement_to_memory_mesh("scope-1")
        assert "procurement" in mem.tags
        assert "vendor" in mem.tags
        assert "purchasing" in mem.tags

    def test_tags_are_tuple(self, integration: ProcurementRuntimeIntegration) -> None:
        mem = integration.attach_procurement_to_memory_mesh("scope-1")
        assert isinstance(mem.tags, tuple)
        assert mem.tags == ("procurement", "vendor", "purchasing")

    def test_title_is_bounded(
        self, integration: ProcurementRuntimeIntegration
    ) -> None:
        mem = integration.attach_procurement_to_memory_mesh("my-scope")
        assert mem.title == "Procurement state"
        assert "my-scope" not in mem.title
        assert mem.scope_ref_id == "my-scope"

    def test_memory_id_is_string(self, integration: ProcurementRuntimeIntegration) -> None:
        mem = integration.attach_procurement_to_memory_mesh("scope-1")
        assert isinstance(mem.memory_id, str)
        assert len(mem.memory_id) > 0

    def test_memory_added_to_engine(
        self,
        integration: ProcurementRuntimeIntegration,
        memory_engine: MemoryMeshEngine,
    ) -> None:
        mem = integration.attach_procurement_to_memory_mesh("scope-1")
        retrieved = memory_engine.get_memory(mem.memory_id)
        assert retrieved is not None
        assert retrieved.memory_id == mem.memory_id


# ---------------------------------------------------------------------------
# attach_procurement_to_graph
# ---------------------------------------------------------------------------


class TestAttachProcurementToGraph:
    def test_returns_expected_keys(
        self, integration: ProcurementRuntimeIntegration
    ) -> None:
        result = integration.attach_procurement_to_graph("scope-1")
        expected_keys = {
            "scope_ref_id",
            "total_vendors",
            "total_requests",
            "total_purchase_orders",
            "total_assessments",
            "total_commitments",
            "total_renewals",
            "total_violations",
        }
        assert set(result.keys()) == expected_keys

    def test_scope_ref_id_matches(
        self, integration: ProcurementRuntimeIntegration
    ) -> None:
        result = integration.attach_procurement_to_graph("scope-99")
        assert result["scope_ref_id"] == "scope-99"

    def test_values_match_engine_state_with_vendor(
        self, integration: ProcurementRuntimeIntegration
    ) -> None:
        result = integration.attach_procurement_to_graph("scope-1")
        assert result["total_vendors"] == 1  # vendor registered in fixture
        assert result["total_requests"] == 0
        assert result["total_purchase_orders"] == 0
        assert result["total_assessments"] == 0
        assert result["total_commitments"] == 0
        assert result["total_renewals"] == 0
        assert result["total_violations"] == 0

    def test_values_reflect_created_request(
        self, integration: ProcurementRuntimeIntegration
    ) -> None:
        integration.procurement_from_budget_need("req-1", "v1", "t1", "bref", 100.0)
        result = integration.attach_procurement_to_graph("scope-1")
        assert result["total_requests"] == 1

    def test_values_reflect_created_renewal(
        self, integration: ProcurementRuntimeIntegration
    ) -> None:
        integration.procurement_from_contract_renewal(
            "ren-1", "v1", "cref", "2026-01-01", "2026-12-31"
        )
        result = integration.attach_procurement_to_graph("scope-1")
        assert result["total_renewals"] == 1


# ---------------------------------------------------------------------------
# Event emission
# ---------------------------------------------------------------------------


class TestEventEmission:
    def test_budget_need_emits_events(
        self,
        integration: ProcurementRuntimeIntegration,
        event_spine: EventSpineEngine,
    ) -> None:
        before = event_spine.event_count
        integration.procurement_from_budget_need("req-1", "v1", "t1", "bref", 100.0)
        after = event_spine.event_count
        assert after > before

    def test_contract_renewal_emits_events(
        self,
        integration: ProcurementRuntimeIntegration,
        event_spine: EventSpineEngine,
    ) -> None:
        before = event_spine.event_count
        integration.procurement_from_contract_renewal(
            "ren-1", "v1", "cref", "2026-01-01", "2026-12-31"
        )
        after = event_spine.event_count
        assert after > before

    def test_connector_requirement_emits_events(
        self,
        integration: ProcurementRuntimeIntegration,
        event_spine: EventSpineEngine,
    ) -> None:
        before = event_spine.event_count
        integration.procurement_from_connector_requirement(
            "req-c1", "v1", "t1", "conn-ref", 500.0
        )
        after = event_spine.event_count
        assert after > before

    def test_asset_need_emits_events(
        self,
        integration: ProcurementRuntimeIntegration,
        event_spine: EventSpineEngine,
    ) -> None:
        before = event_spine.event_count
        integration.procurement_from_asset_need("req-a1", "v1", "t1", "aref", 300.0)
        after = event_spine.event_count
        assert after > before

    def test_vendor_risk_emits_events(
        self,
        integration: ProcurementRuntimeIntegration,
        event_spine: EventSpineEngine,
    ) -> None:
        before = event_spine.event_count
        integration.vendor_risk_from_faults("assess-1", "v1", 0.9, 0)
        after = event_spine.event_count
        assert after > before

    def test_po_binding_emits_events(
        self,
        integration: ProcurementRuntimeIntegration,
        procurement_engine: ProcurementRuntimeEngine,
        event_spine: EventSpineEngine,
    ) -> None:
        _create_po(procurement_engine)
        before = event_spine.event_count
        integration.bind_po_to_financial_runtime("po-1", "inv-ref-1")
        after = event_spine.event_count
        assert after > before

    def test_vendor_contract_binding_emits_events(
        self,
        integration: ProcurementRuntimeIntegration,
        event_spine: EventSpineEngine,
    ) -> None:
        before = event_spine.event_count
        integration.bind_vendor_to_contract_runtime("commit-1", "v1", "cref")
        after = event_spine.event_count
        assert after > before

    def test_memory_mesh_attachment_emits_event(
        self,
        integration: ProcurementRuntimeIntegration,
        event_spine: EventSpineEngine,
    ) -> None:
        before = event_spine.event_count
        integration.attach_procurement_to_memory_mesh("scope-1")
        after = event_spine.event_count
        assert after > before


# ---------------------------------------------------------------------------
# Golden path: full lifecycle
# ---------------------------------------------------------------------------


class TestGoldenPathFullLifecycle:
    def test_full_lifecycle(
        self,
        integration: ProcurementRuntimeIntegration,
        procurement_engine: ProcurementRuntimeEngine,
        event_spine: EventSpineEngine,
        memory_engine: MemoryMeshEngine,
    ) -> None:
        # 1. Create procurement from budget need
        budget = integration.procurement_from_budget_need(
            "req-1", "v1", "t1", "budget-ref-1", 1000.0
        )
        assert budget["source_type"] == "budget_need"
        assert budget["status"] == "draft"
        assert budget["request_id"] == "req-1"
        assert budget["vendor_id"] == "v1"
        assert budget["tenant_id"] == "t1"
        assert budget["budget_ref"] == "budget-ref-1"
        assert budget["estimated_amount"] == 1000.0

        # 2. Schedule a contract renewal
        renewal = integration.procurement_from_contract_renewal(
            "ren-1", "v1", "contract-ref-1", "2026-01-01", "2026-12-31"
        )
        assert renewal["source_type"] == "contract_renewal"
        assert renewal["disposition"] == "pending"
        assert renewal["renewal_id"] == "ren-1"
        assert renewal["contract_ref"] == "contract-ref-1"

        # 3. Create procurement from connector requirement
        connector = integration.procurement_from_connector_requirement(
            "req-c1", "v1", "t1", "conn-ref-1", 800.0
        )
        assert connector["source_type"] == "connector_requirement"
        assert connector["status"] == "draft"
        assert connector["connector_ref"] == "conn-ref-1"

        # 4. Create procurement from asset need
        asset = integration.procurement_from_asset_need(
            "req-a1", "v1", "t1", "asset-ref-1", 600.0
        )
        assert asset["source_type"] == "asset_need"
        assert asset["status"] == "draft"
        assert asset["asset_ref"] == "asset-ref-1"

        # 5. Assess vendor risk from faults
        risk = integration.vendor_risk_from_faults("assess-1", "v1", 0.85, 1)
        assert risk["source_type"] == "fault_history"
        assert risk["risk_level"] == "medium"
        assert risk["performance_score"] == 0.85
        assert risk["fault_count"] == 1

        # 6. Create a PO and bind to financial runtime
        procurement_engine.create_request("req-po", "v1", "t1", 5000.0)
        procurement_engine.submit_request("req-po")
        procurement_engine.approve_request("req-po", decided_by="approver-1")
        procurement_engine.issue_po("po-1", "req-po")
        po_bind = integration.bind_po_to_financial_runtime("po-1", "inv-ref-1")
        assert po_bind["binding_type"] == "financial"
        assert po_bind["po_id"] == "po-1"
        assert po_bind["vendor_id"] == "v1"
        assert po_bind["amount"] == 5000.0
        assert po_bind["invoice_ref"] == "inv-ref-1"

        # 7. Bind vendor to contract runtime
        contract_bind = integration.bind_vendor_to_contract_runtime(
            "commit-1", "v1", "contract-ref-1",
            description="SLA", target_value="99.9%",
        )
        assert contract_bind["binding_type"] == "contract"
        assert contract_bind["commitment_id"] == "commit-1"
        assert contract_bind["vendor_id"] == "v1"
        assert contract_bind["contract_ref"] == "contract-ref-1"

        # 8. Attach procurement state to memory mesh
        mem = integration.attach_procurement_to_memory_mesh("lifecycle-scope")
        assert isinstance(mem, MemoryRecord)
        assert "procurement" in mem.tags
        assert "vendor" in mem.tags
        assert "purchasing" in mem.tags
        assert memory_engine.get_memory(mem.memory_id) is not None

        # 9. Attach procurement state to graph
        graph = integration.attach_procurement_to_graph("lifecycle-scope")
        assert graph["scope_ref_id"] == "lifecycle-scope"
        assert graph["total_vendors"] == 1
        assert graph["total_requests"] == 4  # req-1, req-c1, req-a1, req-po
        assert graph["total_purchase_orders"] == 1
        assert graph["total_assessments"] == 1
        assert graph["total_commitments"] == 1
        assert graph["total_renewals"] == 1

        # 10. Verify events were emitted throughout
        assert event_spine.event_count >= 9
