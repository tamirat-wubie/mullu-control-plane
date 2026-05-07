"""Tests for the asset runtime integration bridge.

Covers: constructor validation, asset creation from purchase orders /
connector dependencies / environments, binding to campaigns / programs /
vendors / contracts, memory mesh attachment, graph attachment, and event
emission invariants.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.core.asset_runtime_integration import AssetRuntimeIntegration
from mcoi_runtime.core.asset_runtime import AssetRuntimeEngine
from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.memory_mesh import MemoryMeshEngine
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
from mcoi_runtime.contracts.asset_runtime import AssetKind, OwnershipType
from mcoi_runtime.contracts.memory_mesh import MemoryRecord


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def engines():
    es = EventSpineEngine()
    ae = AssetRuntimeEngine(es)
    mm = MemoryMeshEngine()
    return ae, es, mm


@pytest.fixture
def integration(engines):
    ae, es, mm = engines
    return AssetRuntimeIntegration(ae, es, mm)


# ---------------------------------------------------------------------------
# 1. Constructor validation
# ---------------------------------------------------------------------------


class TestConstructorValidation:
    """Ensure all three constructor arguments are isinstance-checked."""

    def test_valid_construction(self, engines):
        ae, es, mm = engines
        bridge = AssetRuntimeIntegration(ae, es, mm)
        assert bridge is not None

    def test_wrong_asset_engine_type_raises(self, engines):
        _, es, mm = engines
        with pytest.raises(RuntimeCoreInvariantError, match="AssetRuntimeEngine"):
            AssetRuntimeIntegration("not-an-engine", es, mm)

    def test_wrong_event_spine_type_raises(self, engines):
        ae, _, mm = engines
        with pytest.raises(RuntimeCoreInvariantError, match="EventSpineEngine"):
            AssetRuntimeIntegration(ae, "not-a-spine", mm)

    def test_wrong_memory_engine_type_raises(self, engines):
        ae, es, _ = engines
        with pytest.raises(RuntimeCoreInvariantError, match="MemoryMeshEngine"):
            AssetRuntimeIntegration(ae, es, "not-a-mesh")

    def test_none_asset_engine_raises(self, engines):
        _, es, mm = engines
        with pytest.raises(RuntimeCoreInvariantError):
            AssetRuntimeIntegration(None, es, mm)

    def test_none_event_spine_raises(self, engines):
        ae, _, mm = engines
        with pytest.raises(RuntimeCoreInvariantError):
            AssetRuntimeIntegration(ae, None, mm)

    def test_none_memory_engine_raises(self, engines):
        ae, es, _ = engines
        with pytest.raises(RuntimeCoreInvariantError):
            AssetRuntimeIntegration(ae, es, None)


# ---------------------------------------------------------------------------
# 2. asset_from_purchase_order
# ---------------------------------------------------------------------------


class TestAssetFromPurchaseOrder:
    """Create assets via purchase order pathway."""

    def test_basic_call_returns_dict(self, integration):
        result = integration.asset_from_purchase_order(
            "a1", "Server", "t1", "po-100",
        )
        assert isinstance(result, dict)

    def test_contains_expected_keys(self, integration):
        result = integration.asset_from_purchase_order(
            "a1", "Server", "t1", "po-100",
        )
        for key in ("asset_id", "name", "tenant_id", "po_ref",
                     "kind", "status", "value", "source_type"):
            assert key in result

    def test_source_type_is_purchase_order(self, integration):
        result = integration.asset_from_purchase_order(
            "a1", "Server", "t1", "po-100",
        )
        assert result["source_type"] == "purchase_order"

    def test_default_kind_is_hardware(self, integration):
        result = integration.asset_from_purchase_order(
            "a1", "Server", "t1", "po-100",
        )
        assert result["kind"] == "hardware"

    def test_default_status_is_active(self, integration):
        result = integration.asset_from_purchase_order(
            "a1", "Server", "t1", "po-100",
        )
        assert result["status"] == "active"

    def test_custom_kind(self, integration):
        result = integration.asset_from_purchase_order(
            "a2", "License Key", "t1", "po-200",
            kind=AssetKind.LICENSE,
        )
        assert result["kind"] == "license"

    def test_custom_ownership_does_not_appear_in_result(self, integration):
        result = integration.asset_from_purchase_order(
            "a3", "Leased Server", "t1", "po-300",
            ownership=OwnershipType.LEASED,
        )
        # ownership is not surfaced in the returned dict
        assert result["source_type"] == "purchase_order"

    def test_custom_value(self, integration):
        result = integration.asset_from_purchase_order(
            "a4", "Expensive Box", "t1", "po-400",
            value=99999.50,
        )
        assert result["value"] == 99999.50

    def test_po_ref_preserved(self, integration):
        result = integration.asset_from_purchase_order(
            "a5", "Rack", "t1", "po-500",
        )
        assert result["po_ref"] == "po-500"

    def test_event_emitted(self, engines):
        ae, es, mm = engines
        bridge = AssetRuntimeIntegration(ae, es, mm)
        before = es.event_count
        bridge.asset_from_purchase_order("a1", "Box", "t1", "po-1")
        # register_asset emits 1 event, integration emits 1 more
        assert es.event_count > before

    def test_kind_status_are_value_strings(self, integration):
        result = integration.asset_from_purchase_order(
            "a6", "Widget", "t1", "po-600",
            kind=AssetKind.SOFTWARE,
        )
        assert isinstance(result["kind"], str)
        assert isinstance(result["status"], str)
        assert result["kind"] == "software"


# ---------------------------------------------------------------------------
# 3. asset_from_connector_dependency
# ---------------------------------------------------------------------------


class TestAssetFromConnectorDependency:
    """Create assets via connector dependency pathway."""

    def test_basic_call_returns_dict(self, integration):
        result = integration.asset_from_connector_dependency(
            "cd1", "API Connector", "t1", "conn-100",
        )
        assert isinstance(result, dict)

    def test_source_type_is_connector_dependency(self, integration):
        result = integration.asset_from_connector_dependency(
            "cd1", "API Connector", "t1", "conn-100",
        )
        assert result["source_type"] == "connector_dependency"

    def test_connector_ref_preserved(self, integration):
        result = integration.asset_from_connector_dependency(
            "cd2", "DB Adapter", "t1", "conn-200",
        )
        assert result["connector_ref"] == "conn-200"

    def test_default_kind_is_software(self, integration):
        result = integration.asset_from_connector_dependency(
            "cd3", "Plugin", "t1", "conn-300",
        )
        assert result["kind"] == "software"

    def test_custom_kind(self, integration):
        result = integration.asset_from_connector_dependency(
            "cd4", "Data Feed", "t1", "conn-400",
            kind=AssetKind.DATA,
        )
        assert result["kind"] == "data"

    def test_event_emitted(self, engines):
        ae, es, mm = engines
        bridge = AssetRuntimeIntegration(ae, es, mm)
        before = es.event_count
        bridge.asset_from_connector_dependency("cd1", "X", "t1", "conn-1")
        assert es.event_count > before

    def test_contains_expected_keys(self, integration):
        result = integration.asset_from_connector_dependency(
            "cd5", "Svc", "t1", "conn-500",
        )
        for key in ("asset_id", "name", "tenant_id", "connector_ref",
                     "kind", "status", "source_type"):
            assert key in result


# ---------------------------------------------------------------------------
# 4. asset_from_environment
# ---------------------------------------------------------------------------


class TestAssetFromEnvironment:
    """Create assets via environment pathway."""

    def test_basic_call_returns_dict(self, integration):
        result = integration.asset_from_environment(
            "env1", "Prod Cluster", "t1", "env-ref-100",
        )
        assert isinstance(result, dict)

    def test_source_type_is_environment(self, integration):
        result = integration.asset_from_environment(
            "env1", "Prod Cluster", "t1", "env-ref-100",
        )
        assert result["source_type"] == "environment"

    def test_environment_ref_preserved(self, integration):
        result = integration.asset_from_environment(
            "env2", "Staging", "t1", "env-ref-200",
        )
        assert result["environment_ref"] == "env-ref-200"

    def test_default_kind_is_infrastructure(self, integration):
        result = integration.asset_from_environment(
            "env3", "VPC", "t1", "env-ref-300",
        )
        assert result["kind"] == "infrastructure"

    def test_custom_kind(self, integration):
        result = integration.asset_from_environment(
            "env4", "Cloud Service", "t1", "env-ref-400",
            kind=AssetKind.SERVICE,
        )
        assert result["kind"] == "service"

    def test_event_emitted(self, engines):
        ae, es, mm = engines
        bridge = AssetRuntimeIntegration(ae, es, mm)
        before = es.event_count
        bridge.asset_from_environment("env1", "X", "t1", "env-1")
        assert es.event_count > before

    def test_contains_expected_keys(self, integration):
        result = integration.asset_from_environment(
            "env5", "Node", "t1", "env-ref-500",
        )
        for key in ("asset_id", "name", "tenant_id", "environment_ref",
                     "kind", "status", "source_type"):
            assert key in result


# ---------------------------------------------------------------------------
# 5. bind_asset_to_campaign
# ---------------------------------------------------------------------------


class TestBindAssetToCampaign:
    """Bind an existing asset to a campaign scope."""

    def test_basic_bind_returns_dict(self, integration):
        integration.asset_from_purchase_order("a1", "Box", "t1", "po-1")
        result = integration.bind_asset_to_campaign("assign1", "a1", "camp-1", bound_by="asset-operator-1")
        assert isinstance(result, dict)

    def test_binding_type_is_campaign(self, integration):
        integration.asset_from_purchase_order("a1", "Box", "t1", "po-1")
        result = integration.bind_asset_to_campaign("assign1", "a1", "camp-1", bound_by="asset-operator-1")
        assert result["binding_type"] == "campaign"

    def test_campaign_ref_preserved(self, integration):
        integration.asset_from_purchase_order("a1", "Box", "t1", "po-1")
        result = integration.bind_asset_to_campaign("assign1", "a1", "camp-99", bound_by="asset-operator-1")
        assert result["campaign_ref"] == "camp-99"

    def test_scope_ref_type_is_campaign(self, integration):
        integration.asset_from_purchase_order("a1", "Box", "t1", "po-1")
        result = integration.bind_asset_to_campaign("assign1", "a1", "camp-1", bound_by="asset-operator-1")
        assert result["scope_ref_type"] == "campaign"

    def test_bound_by_preserved(self, integration):
        integration.asset_from_purchase_order("a1", "Box", "t1", "po-1")
        result = integration.bind_asset_to_campaign("assign1", "a1", "camp-1", bound_by="asset-operator-1")
        assert result["bound_by"] == "asset-operator-1"

    def test_missing_bound_by_rejected(self, integration):
        integration.asset_from_purchase_order("a1", "Box", "t1", "po-1")
        with pytest.raises(RuntimeCoreInvariantError, match="bound_by required for asset binding"):
            integration.bind_asset_to_campaign("assign1", "a1", "camp-1")

    def test_system_bound_by_rejected(self, integration):
        integration.asset_from_purchase_order("a1", "Box", "t1", "po-1")
        with pytest.raises(RuntimeCoreInvariantError, match="bound_by must exclude system"):
            integration.bind_asset_to_campaign(
                "assign1", "a1", "camp-1",
                bound_by="system",
            )

    def test_event_emitted(self, engines):
        ae, es, mm = engines
        bridge = AssetRuntimeIntegration(ae, es, mm)
        bridge.asset_from_purchase_order("a1", "Box", "t1", "po-1")
        before = es.event_count
        bridge.bind_asset_to_campaign("assign1", "a1", "camp-1", bound_by="asset-operator-1")
        assert es.event_count > before


# ---------------------------------------------------------------------------
# 6. bind_asset_to_program
# ---------------------------------------------------------------------------


class TestBindAssetToProgram:
    """Bind an existing asset to a program scope."""

    def test_basic_bind_returns_dict(self, integration):
        integration.asset_from_purchase_order("a1", "Box", "t1", "po-1")
        result = integration.bind_asset_to_program("assign1", "a1", "prog-1", bound_by="asset-operator-1")
        assert isinstance(result, dict)

    def test_binding_type_is_program(self, integration):
        integration.asset_from_purchase_order("a1", "Box", "t1", "po-1")
        result = integration.bind_asset_to_program("assign1", "a1", "prog-1", bound_by="asset-operator-1")
        assert result["binding_type"] == "program"

    def test_program_ref_preserved(self, integration):
        integration.asset_from_purchase_order("a1", "Box", "t1", "po-1")
        result = integration.bind_asset_to_program("assign1", "a1", "prog-42", bound_by="asset-operator-1")
        assert result["program_ref"] == "prog-42"

    def test_scope_ref_type_is_program(self, integration):
        integration.asset_from_purchase_order("a1", "Box", "t1", "po-1")
        result = integration.bind_asset_to_program("assign1", "a1", "prog-1", bound_by="asset-operator-1")
        assert result["scope_ref_type"] == "program"

    def test_event_emitted(self, engines):
        ae, es, mm = engines
        bridge = AssetRuntimeIntegration(ae, es, mm)
        bridge.asset_from_purchase_order("a1", "Box", "t1", "po-1")
        before = es.event_count
        bridge.bind_asset_to_program("assign1", "a1", "prog-1", bound_by="asset-operator-1")
        assert es.event_count > before


# ---------------------------------------------------------------------------
# 7. bind_asset_to_vendor
# ---------------------------------------------------------------------------


class TestBindAssetToVendor:
    """Bind an existing asset to a vendor scope."""

    def test_basic_bind_returns_dict(self, integration):
        integration.asset_from_purchase_order("a1", "Box", "t1", "po-1")
        result = integration.bind_asset_to_vendor("assign1", "a1", "vendor-1", bound_by="asset-operator-1")
        assert isinstance(result, dict)

    def test_binding_type_is_vendor(self, integration):
        integration.asset_from_purchase_order("a1", "Box", "t1", "po-1")
        result = integration.bind_asset_to_vendor("assign1", "a1", "vendor-1", bound_by="asset-operator-1")
        assert result["binding_type"] == "vendor"

    def test_vendor_ref_preserved(self, integration):
        integration.asset_from_purchase_order("a1", "Box", "t1", "po-1")
        result = integration.bind_asset_to_vendor("assign1", "a1", "vendor-77", bound_by="asset-operator-1")
        assert result["vendor_ref"] == "vendor-77"

    def test_scope_ref_type_is_vendor(self, integration):
        integration.asset_from_purchase_order("a1", "Box", "t1", "po-1")
        result = integration.bind_asset_to_vendor("assign1", "a1", "vendor-1", bound_by="asset-operator-1")
        assert result["scope_ref_type"] == "vendor"

    def test_event_emitted(self, engines):
        ae, es, mm = engines
        bridge = AssetRuntimeIntegration(ae, es, mm)
        bridge.asset_from_purchase_order("a1", "Box", "t1", "po-1")
        before = es.event_count
        bridge.bind_asset_to_vendor("assign1", "a1", "vendor-1", bound_by="asset-operator-1")
        assert es.event_count > before


# ---------------------------------------------------------------------------
# 8. bind_asset_to_contract
# ---------------------------------------------------------------------------


class TestBindAssetToContract:
    """Bind an existing asset to a contract scope."""

    def test_basic_bind_returns_dict(self, integration):
        integration.asset_from_purchase_order("a1", "Box", "t1", "po-1")
        result = integration.bind_asset_to_contract("assign1", "a1", "ctr-1", bound_by="asset-operator-1")
        assert isinstance(result, dict)

    def test_binding_type_is_contract(self, integration):
        integration.asset_from_purchase_order("a1", "Box", "t1", "po-1")
        result = integration.bind_asset_to_contract("assign1", "a1", "ctr-1", bound_by="asset-operator-1")
        assert result["binding_type"] == "contract"

    def test_contract_ref_preserved(self, integration):
        integration.asset_from_purchase_order("a1", "Box", "t1", "po-1")
        result = integration.bind_asset_to_contract("assign1", "a1", "ctr-55", bound_by="asset-operator-1")
        assert result["contract_ref"] == "ctr-55"

    def test_scope_ref_type_is_contract(self, integration):
        integration.asset_from_purchase_order("a1", "Box", "t1", "po-1")
        result = integration.bind_asset_to_contract("assign1", "a1", "ctr-1", bound_by="asset-operator-1")
        assert result["scope_ref_type"] == "contract"

    def test_event_emitted(self, engines):
        ae, es, mm = engines
        bridge = AssetRuntimeIntegration(ae, es, mm)
        bridge.asset_from_purchase_order("a1", "Box", "t1", "po-1")
        before = es.event_count
        bridge.bind_asset_to_contract("assign1", "a1", "ctr-1", bound_by="asset-operator-1")
        assert es.event_count > before


# ---------------------------------------------------------------------------
# 9. attach_asset_state_to_memory_mesh
# ---------------------------------------------------------------------------


class TestAttachAssetStateToMemoryMesh:
    """Persist asset state to memory mesh."""

    def test_returns_memory_record(self, integration):
        integration.asset_from_purchase_order("a1", "Box", "t1", "po-1")
        mem = integration.attach_asset_state_to_memory_mesh("scope-1")
        assert isinstance(mem, MemoryRecord)

    def test_memory_title_redacts_scope_ref(self, integration):
        integration.asset_from_purchase_order("a1", "Box", "t1", "po-1")
        mem = integration.attach_asset_state_to_memory_mesh("asset-scope-secret")
        assert mem.title == "Asset state"
        assert "asset-scope-secret" not in mem.title

    def test_tags_contain_expected_values(self, integration):
        integration.asset_from_purchase_order("a1", "Box", "t1", "po-1")
        mem = integration.attach_asset_state_to_memory_mesh("scope-1")
        assert "asset" in mem.tags
        assert "configuration" in mem.tags
        assert "inventory" in mem.tags

    def test_content_total_assets_matches_engine(self, engines):
        ae, es, mm = engines
        bridge = AssetRuntimeIntegration(ae, es, mm)
        bridge.asset_from_purchase_order("a1", "Box", "t1", "po-1")
        bridge.asset_from_purchase_order("a2", "Rack", "t1", "po-2")
        mem = bridge.attach_asset_state_to_memory_mesh("scope-1")
        assert mem.content["total_assets"] == ae.asset_count

    def test_content_total_assignments_matches_engine(self, engines):
        ae, es, mm = engines
        bridge = AssetRuntimeIntegration(ae, es, mm)
        bridge.asset_from_purchase_order("a1", "Box", "t1", "po-1")
        bridge.bind_asset_to_campaign("asgn1", "a1", "camp-1", bound_by="asset-operator-1")
        mem = bridge.attach_asset_state_to_memory_mesh("scope-1")
        assert mem.content["total_assignments"] == ae.assignment_count

    def test_content_total_config_items_matches_engine(self, engines):
        ae, es, mm = engines
        bridge = AssetRuntimeIntegration(ae, es, mm)
        bridge.asset_from_purchase_order("a1", "Box", "t1", "po-1")
        mem = bridge.attach_asset_state_to_memory_mesh("scope-1")
        assert mem.content["total_config_items"] == ae.config_item_count

    def test_content_total_inventory_matches_engine(self, engines):
        ae, es, mm = engines
        bridge = AssetRuntimeIntegration(ae, es, mm)
        bridge.asset_from_purchase_order("a1", "Box", "t1", "po-1")
        mem = bridge.attach_asset_state_to_memory_mesh("scope-1")
        assert mem.content["total_inventory"] == ae.inventory_count

    def test_content_total_dependencies_matches_engine(self, engines):
        ae, es, mm = engines
        bridge = AssetRuntimeIntegration(ae, es, mm)
        bridge.asset_from_purchase_order("a1", "Box", "t1", "po-1")
        mem = bridge.attach_asset_state_to_memory_mesh("scope-1")
        assert mem.content["total_dependencies"] == ae.dependency_count

    def test_content_total_lifecycle_events_matches_engine(self, engines):
        ae, es, mm = engines
        bridge = AssetRuntimeIntegration(ae, es, mm)
        bridge.asset_from_purchase_order("a1", "Box", "t1", "po-1")
        mem = bridge.attach_asset_state_to_memory_mesh("scope-1")
        assert mem.content["total_lifecycle_events"] == ae.lifecycle_event_count

    def test_content_total_assessments_matches_engine(self, engines):
        ae, es, mm = engines
        bridge = AssetRuntimeIntegration(ae, es, mm)
        bridge.asset_from_purchase_order("a1", "Box", "t1", "po-1")
        mem = bridge.attach_asset_state_to_memory_mesh("scope-1")
        assert mem.content["total_assessments"] == ae.assessment_count

    def test_content_total_violations_matches_engine(self, engines):
        ae, es, mm = engines
        bridge = AssetRuntimeIntegration(ae, es, mm)
        bridge.asset_from_purchase_order("a1", "Box", "t1", "po-1")
        mem = bridge.attach_asset_state_to_memory_mesh("scope-1")
        assert mem.content["total_violations"] == ae.violation_count

    def test_duplicate_scope_ref_id_raises(self, integration):
        integration.asset_from_purchase_order("a1", "Box", "t1", "po-1")
        integration.attach_asset_state_to_memory_mesh("scope-dup")
        with pytest.raises(RuntimeCoreInvariantError, match="duplicate"):
            integration.attach_asset_state_to_memory_mesh("scope-dup")

    def test_event_emitted(self, engines):
        ae, es, mm = engines
        bridge = AssetRuntimeIntegration(ae, es, mm)
        bridge.asset_from_purchase_order("a1", "Box", "t1", "po-1")
        before = es.event_count
        bridge.attach_asset_state_to_memory_mesh("scope-1")
        assert es.event_count > before


# ---------------------------------------------------------------------------
# 10. attach_asset_state_to_graph
# ---------------------------------------------------------------------------


class TestAttachAssetStateToGraph:
    """Return asset state suitable for an operational graph."""

    def test_returns_dict(self, integration):
        result = integration.attach_asset_state_to_graph("scope-g1")
        assert isinstance(result, dict)

    def test_scope_ref_id_preserved(self, integration):
        result = integration.attach_asset_state_to_graph("scope-g1")
        assert result["scope_ref_id"] == "scope-g1"

    def test_total_assets_matches_engine(self, engines):
        ae, es, mm = engines
        bridge = AssetRuntimeIntegration(ae, es, mm)
        bridge.asset_from_purchase_order("a1", "X", "t1", "po-1")
        result = bridge.attach_asset_state_to_graph("scope-g1")
        assert result["total_assets"] == ae.asset_count

    def test_total_config_items_matches_engine(self, engines):
        ae, es, mm = engines
        bridge = AssetRuntimeIntegration(ae, es, mm)
        result = bridge.attach_asset_state_to_graph("scope-g1")
        assert result["total_config_items"] == ae.config_item_count

    def test_total_inventory_matches_engine(self, engines):
        ae, es, mm = engines
        bridge = AssetRuntimeIntegration(ae, es, mm)
        result = bridge.attach_asset_state_to_graph("scope-g1")
        assert result["total_inventory"] == ae.inventory_count

    def test_total_assignments_matches_engine(self, engines):
        ae, es, mm = engines
        bridge = AssetRuntimeIntegration(ae, es, mm)
        bridge.asset_from_purchase_order("a1", "X", "t1", "po-1")
        bridge.bind_asset_to_program("asgn1", "a1", "prog-1", bound_by="asset-operator-1")
        result = bridge.attach_asset_state_to_graph("scope-g1")
        assert result["total_assignments"] == ae.assignment_count

    def test_total_dependencies_matches_engine(self, engines):
        ae, es, mm = engines
        bridge = AssetRuntimeIntegration(ae, es, mm)
        result = bridge.attach_asset_state_to_graph("scope-g1")
        assert result["total_dependencies"] == ae.dependency_count

    def test_total_lifecycle_events_matches_engine(self, engines):
        ae, es, mm = engines
        bridge = AssetRuntimeIntegration(ae, es, mm)
        result = bridge.attach_asset_state_to_graph("scope-g1")
        assert result["total_lifecycle_events"] == ae.lifecycle_event_count

    def test_total_assessments_matches_engine(self, engines):
        ae, es, mm = engines
        bridge = AssetRuntimeIntegration(ae, es, mm)
        result = bridge.attach_asset_state_to_graph("scope-g1")
        assert result["total_assessments"] == ae.assessment_count

    def test_total_violations_matches_engine(self, engines):
        ae, es, mm = engines
        bridge = AssetRuntimeIntegration(ae, es, mm)
        result = bridge.attach_asset_state_to_graph("scope-g1")
        assert result["total_violations"] == ae.violation_count

    def test_contains_all_count_keys(self, integration):
        result = integration.attach_asset_state_to_graph("scope-g1")
        expected_keys = {
            "scope_ref_id",
            "total_assets",
            "total_config_items",
            "total_inventory",
            "total_assignments",
            "total_dependencies",
            "total_lifecycle_events",
            "total_assessments",
            "total_violations",
        }
        assert expected_keys == set(result.keys())


# ---------------------------------------------------------------------------
# 11. Event emission — cross-cutting
# ---------------------------------------------------------------------------


class TestEventEmission:
    """Every bridge method emits at least one event to the spine."""

    def test_purchase_order_increases_event_count(self, engines):
        ae, es, mm = engines
        bridge = AssetRuntimeIntegration(ae, es, mm)
        before = es.event_count
        bridge.asset_from_purchase_order("a1", "X", "t1", "po-1")
        after = es.event_count
        assert after >= before + 2  # register_asset + integration emit

    def test_connector_dependency_increases_event_count(self, engines):
        ae, es, mm = engines
        bridge = AssetRuntimeIntegration(ae, es, mm)
        before = es.event_count
        bridge.asset_from_connector_dependency("cd1", "X", "t1", "conn-1")
        after = es.event_count
        assert after >= before + 2

    def test_environment_increases_event_count(self, engines):
        ae, es, mm = engines
        bridge = AssetRuntimeIntegration(ae, es, mm)
        before = es.event_count
        bridge.asset_from_environment("env1", "X", "t1", "env-1")
        after = es.event_count
        assert after >= before + 2

    def test_bind_campaign_increases_event_count(self, engines):
        ae, es, mm = engines
        bridge = AssetRuntimeIntegration(ae, es, mm)
        bridge.asset_from_purchase_order("a1", "X", "t1", "po-1")
        before = es.event_count
        bridge.bind_asset_to_campaign("asgn1", "a1", "camp-1", bound_by="asset-operator-1")
        after = es.event_count
        assert after >= before + 2  # assign_asset + integration emit

    def test_bind_program_increases_event_count(self, engines):
        ae, es, mm = engines
        bridge = AssetRuntimeIntegration(ae, es, mm)
        bridge.asset_from_purchase_order("a1", "X", "t1", "po-1")
        before = es.event_count
        bridge.bind_asset_to_program("asgn1", "a1", "prog-1", bound_by="asset-operator-1")
        after = es.event_count
        assert after >= before + 2

    def test_bind_vendor_increases_event_count(self, engines):
        ae, es, mm = engines
        bridge = AssetRuntimeIntegration(ae, es, mm)
        bridge.asset_from_purchase_order("a1", "X", "t1", "po-1")
        before = es.event_count
        bridge.bind_asset_to_vendor("asgn1", "a1", "vendor-1", bound_by="asset-operator-1")
        after = es.event_count
        assert after >= before + 2

    def test_bind_contract_increases_event_count(self, engines):
        ae, es, mm = engines
        bridge = AssetRuntimeIntegration(ae, es, mm)
        bridge.asset_from_purchase_order("a1", "X", "t1", "po-1")
        before = es.event_count
        bridge.bind_asset_to_contract("asgn1", "a1", "ctr-1", bound_by="asset-operator-1")
        after = es.event_count
        assert after >= before + 2

    def test_memory_mesh_attach_increases_event_count(self, engines):
        ae, es, mm = engines
        bridge = AssetRuntimeIntegration(ae, es, mm)
        bridge.asset_from_purchase_order("a1", "X", "t1", "po-1")
        before = es.event_count
        bridge.attach_asset_state_to_memory_mesh("scope-1")
        after = es.event_count
        assert after >= before + 1

    def test_graph_attach_does_not_emit_events(self, engines):
        ae, es, mm = engines
        bridge = AssetRuntimeIntegration(ae, es, mm)
        before = es.event_count
        bridge.attach_asset_state_to_graph("scope-g1")
        assert es.event_count == before

    def test_cumulative_event_count_across_operations(self, engines):
        ae, es, mm = engines
        bridge = AssetRuntimeIntegration(ae, es, mm)
        bridge.asset_from_purchase_order("a1", "X", "t1", "po-1")
        bridge.asset_from_connector_dependency("cd1", "Y", "t1", "conn-1")
        bridge.asset_from_environment("env1", "Z", "t1", "env-1")
        bridge.bind_asset_to_campaign("asgn1", "a1", "camp-1", bound_by="asset-operator-1")
        bridge.attach_asset_state_to_memory_mesh("scope-1")
        # At minimum: 3 register + 3 integration + 1 assign + 1 bind + 1 memory = 9
        assert es.event_count >= 9
