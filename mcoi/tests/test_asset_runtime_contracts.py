"""Comprehensive tests for asset runtime contracts.

Tests cover: enum membership, dataclass construction, validation failures,
frozen immutability, metadata freezing, and to_dict() serialization.
"""

from __future__ import annotations

import dataclasses
import math
from types import MappingProxyType

import pytest

from mcoi_runtime.contracts.asset_runtime import (
    AssetAssessment,
    AssetAssignment,
    AssetClosureReport,
    AssetDependency,
    AssetKind,
    AssetRecord,
    AssetSnapshot,
    AssetStatus,
    AssetViolation,
    ConfigurationItem,
    ConfigurationItemStatus,
    InventoryDisposition,
    InventoryRecord,
    LifecycleDisposition,
    LifecycleEvent,
    OwnershipType,
)


# ===================================================================
# Helpers: valid kwargs for each dataclass
# ===================================================================

def _asset_record_kw(**overrides):
    base = dict(
        asset_id="a-1", name="Server A", tenant_id="t-1",
        kind=AssetKind.HARDWARE, status=AssetStatus.ACTIVE,
        ownership=OwnershipType.OWNED, owner_ref="own-1",
        vendor_ref="ven-1", value=1000.0,
        registered_at="2025-06-01T00:00:00",
    )
    base.update(overrides)
    return base


def _config_item_kw(**overrides):
    base = dict(
        ci_id="ci-1", asset_id="a-1", name="Config A",
        status=ConfigurationItemStatus.ACTIVE,
        environment_ref="env-1", workspace_ref="ws-1",
        version="1.0", created_at="2025-06-01T00:00:00",
    )
    base.update(overrides)
    return base


def _inventory_record_kw(**overrides):
    base = dict(
        inventory_id="inv-1", asset_id="a-1", tenant_id="t-1",
        disposition=InventoryDisposition.AVAILABLE,
        total_quantity=100, assigned_quantity=20, available_quantity=80,
        updated_at="2025-06-01T00:00:00",
    )
    base.update(overrides)
    return base


def _asset_assignment_kw(**overrides):
    base = dict(
        assignment_id="asg-1", asset_id="a-1",
        scope_ref_id="scope-1", scope_ref_type="campaign",
        assigned_by="user-1", assigned_at="2025-06-01T00:00:00",
    )
    base.update(overrides)
    return base


def _asset_dependency_kw(**overrides):
    base = dict(
        dependency_id="dep-1", asset_id="a-1",
        depends_on_asset_id="a-2", description="needs db",
        created_at="2025-06-01T00:00:00",
    )
    base.update(overrides)
    return base


def _lifecycle_event_kw(**overrides):
    base = dict(
        event_id="evt-1", asset_id="a-1",
        disposition=LifecycleDisposition.PROVISIONED,
        description="initial provision", performed_by="admin-1",
        performed_at="2025-06-01T00:00:00",
    )
    base.update(overrides)
    return base


def _asset_assessment_kw(**overrides):
    base = dict(
        assessment_id="assess-1", asset_id="a-1",
        health_score=0.9, risk_score=0.1,
        assessed_by="auditor-1",
        assessed_at="2025-06-01T00:00:00",
    )
    base.update(overrides)
    return base


def _asset_snapshot_kw(**overrides):
    base = dict(
        snapshot_id="snap-1",
        total_assets=50, total_active=40, total_retired=10,
        total_config_items=30, total_inventory=20,
        total_assignments=15, total_dependencies=5,
        total_violations=2, total_asset_value=500000.0,
        captured_at="2025-06-01T00:00:00",
    )
    base.update(overrides)
    return base


def _asset_violation_kw(**overrides):
    base = dict(
        violation_id="viol-1", asset_id="a-1", tenant_id="t-1",
        operation="assign", reason="retired asset",
        detected_at="2025-06-01T00:00:00",
    )
    base.update(overrides)
    return base


def _asset_closure_report_kw(**overrides):
    base = dict(
        report_id="rpt-1", tenant_id="t-1",
        total_assets=100, total_active=80, total_retired=20,
        total_assignments=50, total_dependencies=10,
        total_asset_value=1000000.0,
        closed_at="2025-06-01T00:00:00",
    )
    base.update(overrides)
    return base


# ===================================================================
# 1. ENUM COVERAGE
# ===================================================================


class TestAssetStatusEnum:
    def test_active_value(self):
        assert AssetStatus.ACTIVE.value == "active"

    def test_inactive_value(self):
        assert AssetStatus.INACTIVE.value == "inactive"

    def test_maintenance_value(self):
        assert AssetStatus.MAINTENANCE.value == "maintenance"

    def test_retired_value(self):
        assert AssetStatus.RETIRED.value == "retired"

    def test_disposed_value(self):
        assert AssetStatus.DISPOSED.value == "disposed"

    def test_member_count(self):
        assert len(AssetStatus) == 5

    def test_all_are_enum_instances(self):
        for member in AssetStatus:
            assert isinstance(member, AssetStatus)

    def test_lookup_by_value(self):
        assert AssetStatus("active") is AssetStatus.ACTIVE

    def test_invalid_value_raises(self):
        with pytest.raises(ValueError):
            AssetStatus("nonexistent")


class TestAssetKindEnum:
    def test_hardware_value(self):
        assert AssetKind.HARDWARE.value == "hardware"

    def test_software_value(self):
        assert AssetKind.SOFTWARE.value == "software"

    def test_license_value(self):
        assert AssetKind.LICENSE.value == "license"

    def test_service_value(self):
        assert AssetKind.SERVICE.value == "service"

    def test_infrastructure_value(self):
        assert AssetKind.INFRASTRUCTURE.value == "infrastructure"

    def test_data_value(self):
        assert AssetKind.DATA.value == "data"

    def test_member_count(self):
        assert len(AssetKind) == 6

    def test_all_are_enum_instances(self):
        for member in AssetKind:
            assert isinstance(member, AssetKind)

    def test_lookup_by_value(self):
        assert AssetKind("software") is AssetKind.SOFTWARE

    def test_invalid_value_raises(self):
        with pytest.raises(ValueError):
            AssetKind("cloud")


class TestConfigurationItemStatusEnum:
    def test_active_value(self):
        assert ConfigurationItemStatus.ACTIVE.value == "active"

    def test_pending_value(self):
        assert ConfigurationItemStatus.PENDING.value == "pending"

    def test_deprecated_value(self):
        assert ConfigurationItemStatus.DEPRECATED.value == "deprecated"

    def test_archived_value(self):
        assert ConfigurationItemStatus.ARCHIVED.value == "archived"

    def test_member_count(self):
        assert len(ConfigurationItemStatus) == 4

    def test_all_are_enum_instances(self):
        for member in ConfigurationItemStatus:
            assert isinstance(member, ConfigurationItemStatus)

    def test_lookup_by_value(self):
        assert ConfigurationItemStatus("pending") is ConfigurationItemStatus.PENDING

    def test_invalid_value_raises(self):
        with pytest.raises(ValueError):
            ConfigurationItemStatus("deleted")


class TestInventoryDispositionEnum:
    def test_available_value(self):
        assert InventoryDisposition.AVAILABLE.value == "available"

    def test_assigned_value(self):
        assert InventoryDisposition.ASSIGNED.value == "assigned"

    def test_reserved_value(self):
        assert InventoryDisposition.RESERVED.value == "reserved"

    def test_depleted_value(self):
        assert InventoryDisposition.DEPLETED.value == "depleted"

    def test_expired_value(self):
        assert InventoryDisposition.EXPIRED.value == "expired"

    def test_member_count(self):
        assert len(InventoryDisposition) == 5

    def test_all_are_enum_instances(self):
        for member in InventoryDisposition:
            assert isinstance(member, InventoryDisposition)

    def test_lookup_by_value(self):
        assert InventoryDisposition("reserved") is InventoryDisposition.RESERVED

    def test_invalid_value_raises(self):
        with pytest.raises(ValueError):
            InventoryDisposition("lost")


class TestOwnershipTypeEnum:
    def test_owned_value(self):
        assert OwnershipType.OWNED.value == "owned"

    def test_leased_value(self):
        assert OwnershipType.LEASED.value == "leased"

    def test_licensed_value(self):
        assert OwnershipType.LICENSED.value == "licensed"

    def test_shared_value(self):
        assert OwnershipType.SHARED.value == "shared"

    def test_vendor_managed_value(self):
        assert OwnershipType.VENDOR_MANAGED.value == "vendor_managed"

    def test_member_count(self):
        assert len(OwnershipType) == 5

    def test_all_are_enum_instances(self):
        for member in OwnershipType:
            assert isinstance(member, OwnershipType)

    def test_lookup_by_value(self):
        assert OwnershipType("leased") is OwnershipType.LEASED

    def test_invalid_value_raises(self):
        with pytest.raises(ValueError):
            OwnershipType("rented")


class TestLifecycleDispositionEnum:
    def test_provisioned_value(self):
        assert LifecycleDisposition.PROVISIONED.value == "provisioned"

    def test_deployed_value(self):
        assert LifecycleDisposition.DEPLOYED.value == "deployed"

    def test_upgraded_value(self):
        assert LifecycleDisposition.UPGRADED.value == "upgraded"

    def test_decommissioned_value(self):
        assert LifecycleDisposition.DECOMMISSIONED.value == "decommissioned"

    def test_transferred_value(self):
        assert LifecycleDisposition.TRANSFERRED.value == "transferred"

    def test_renewed_value(self):
        assert LifecycleDisposition.RENEWED.value == "renewed"

    def test_member_count(self):
        assert len(LifecycleDisposition) == 6

    def test_all_are_enum_instances(self):
        for member in LifecycleDisposition:
            assert isinstance(member, LifecycleDisposition)

    def test_lookup_by_value(self):
        assert LifecycleDisposition("upgraded") is LifecycleDisposition.UPGRADED

    def test_invalid_value_raises(self):
        with pytest.raises(ValueError):
            LifecycleDisposition("destroyed")


# ===================================================================
# 2. DATACLASS CONSTRUCTION — valid cases
# ===================================================================


class TestAssetRecordConstruction:
    def test_valid_construction(self):
        rec = AssetRecord(**_asset_record_kw())
        assert rec.asset_id == "a-1"
        assert rec.name == "Server A"
        assert rec.tenant_id == "t-1"
        assert rec.kind is AssetKind.HARDWARE
        assert rec.status is AssetStatus.ACTIVE
        assert rec.ownership is OwnershipType.OWNED

    def test_all_kinds(self):
        for k in AssetKind:
            rec = AssetRecord(**_asset_record_kw(kind=k))
            assert rec.kind is k

    def test_all_statuses(self):
        for s in AssetStatus:
            rec = AssetRecord(**_asset_record_kw(status=s))
            assert rec.status is s

    def test_all_ownership_types(self):
        for o in OwnershipType:
            rec = AssetRecord(**_asset_record_kw(ownership=o))
            assert rec.ownership is o

    def test_zero_value(self):
        rec = AssetRecord(**_asset_record_kw(value=0.0))
        assert rec.value == 0.0

    def test_large_value(self):
        rec = AssetRecord(**_asset_record_kw(value=1e12))
        assert rec.value == 1e12

    def test_integer_value_coerced(self):
        rec = AssetRecord(**_asset_record_kw(value=100))
        assert rec.value == 100.0

    def test_metadata_default_empty(self):
        rec = AssetRecord(**_asset_record_kw())
        assert rec.metadata == {}

    def test_metadata_with_content(self):
        rec = AssetRecord(**_asset_record_kw(metadata={"rack": "A3"}))
        assert rec.metadata["rack"] == "A3"

    def test_date_only_registered_at(self):
        rec = AssetRecord(**_asset_record_kw(registered_at="2025-06-01"))
        assert rec.registered_at == "2025-06-01"

    def test_datetime_with_tz(self):
        rec = AssetRecord(**_asset_record_kw(registered_at="2025-06-01T12:00:00+03:00"))
        assert rec.registered_at == "2025-06-01T12:00:00+03:00"

    def test_datetime_with_z(self):
        rec = AssetRecord(**_asset_record_kw(registered_at="2025-06-01T12:00:00Z"))
        assert rec.registered_at == "2025-06-01T12:00:00Z"


class TestConfigurationItemConstruction:
    def test_valid_construction(self):
        ci = ConfigurationItem(**_config_item_kw())
        assert ci.ci_id == "ci-1"
        assert ci.asset_id == "a-1"
        assert ci.name == "Config A"
        assert ci.status is ConfigurationItemStatus.ACTIVE

    def test_all_statuses(self):
        for s in ConfigurationItemStatus:
            ci = ConfigurationItem(**_config_item_kw(status=s))
            assert ci.status is s

    def test_empty_version_allowed(self):
        # version is not validated as non-empty
        ci = ConfigurationItem(**_config_item_kw(version=""))
        assert ci.version == ""

    def test_metadata_default(self):
        ci = ConfigurationItem(**_config_item_kw())
        assert ci.metadata == {}


class TestInventoryRecordConstruction:
    def test_valid_construction(self):
        inv = InventoryRecord(**_inventory_record_kw())
        assert inv.inventory_id == "inv-1"
        assert inv.total_quantity == 100
        assert inv.assigned_quantity == 20
        assert inv.available_quantity == 80

    def test_all_dispositions(self):
        for d in InventoryDisposition:
            inv = InventoryRecord(**_inventory_record_kw(disposition=d))
            assert inv.disposition is d

    def test_zero_quantities(self):
        inv = InventoryRecord(**_inventory_record_kw(
            total_quantity=0, assigned_quantity=0, available_quantity=0))
        assert inv.total_quantity == 0

    def test_metadata_default(self):
        inv = InventoryRecord(**_inventory_record_kw())
        assert inv.metadata == {}


class TestAssetAssignmentConstruction:
    def test_valid_construction(self):
        asg = AssetAssignment(**_asset_assignment_kw())
        assert asg.assignment_id == "asg-1"
        assert asg.scope_ref_type == "campaign"

    def test_different_scope_type(self):
        asg = AssetAssignment(**_asset_assignment_kw(scope_ref_type="environment"))
        assert asg.scope_ref_type == "environment"

    def test_metadata_default(self):
        asg = AssetAssignment(**_asset_assignment_kw())
        assert asg.metadata == {}


class TestAssetDependencyConstruction:
    def test_valid_construction(self):
        dep = AssetDependency(**_asset_dependency_kw())
        assert dep.dependency_id == "dep-1"
        assert dep.depends_on_asset_id == "a-2"

    def test_empty_description_allowed(self):
        # description is not validated as non-empty
        dep = AssetDependency(**_asset_dependency_kw(description=""))
        assert dep.description == ""

    def test_metadata_default(self):
        dep = AssetDependency(**_asset_dependency_kw())
        assert dep.metadata == {}


class TestLifecycleEventConstruction:
    def test_valid_construction(self):
        evt = LifecycleEvent(**_lifecycle_event_kw())
        assert evt.event_id == "evt-1"
        assert evt.disposition is LifecycleDisposition.PROVISIONED

    def test_all_dispositions(self):
        for d in LifecycleDisposition:
            evt = LifecycleEvent(**_lifecycle_event_kw(disposition=d))
            assert evt.disposition is d

    def test_metadata_default(self):
        evt = LifecycleEvent(**_lifecycle_event_kw())
        assert evt.metadata == {}


class TestAssetAssessmentConstruction:
    def test_valid_construction(self):
        a = AssetAssessment(**_asset_assessment_kw())
        assert a.assessment_id == "assess-1"
        assert a.health_score == 0.9
        assert a.risk_score == 0.1

    def test_scores_at_zero(self):
        a = AssetAssessment(**_asset_assessment_kw(health_score=0.0, risk_score=0.0))
        assert a.health_score == 0.0
        assert a.risk_score == 0.0

    def test_scores_at_one(self):
        a = AssetAssessment(**_asset_assessment_kw(health_score=1.0, risk_score=1.0))
        assert a.health_score == 1.0
        assert a.risk_score == 1.0

    def test_scores_at_boundary_half(self):
        a = AssetAssessment(**_asset_assessment_kw(health_score=0.5, risk_score=0.5))
        assert a.health_score == 0.5

    def test_integer_scores_coerced(self):
        a = AssetAssessment(**_asset_assessment_kw(health_score=0, risk_score=1))
        assert a.health_score == 0.0
        assert a.risk_score == 1.0

    def test_metadata_default(self):
        a = AssetAssessment(**_asset_assessment_kw())
        assert a.metadata == {}


class TestAssetSnapshotConstruction:
    def test_valid_construction(self):
        snap = AssetSnapshot(**_asset_snapshot_kw())
        assert snap.snapshot_id == "snap-1"
        assert snap.total_assets == 50
        assert snap.total_asset_value == 500000.0

    def test_all_zeros(self):
        snap = AssetSnapshot(**_asset_snapshot_kw(
            total_assets=0, total_active=0, total_retired=0,
            total_config_items=0, total_inventory=0,
            total_assignments=0, total_dependencies=0,
            total_violations=0, total_asset_value=0.0))
        assert snap.total_assets == 0
        assert snap.total_asset_value == 0.0

    def test_metadata_default(self):
        snap = AssetSnapshot(**_asset_snapshot_kw())
        assert snap.metadata == {}


class TestAssetViolationConstruction:
    def test_valid_construction(self):
        v = AssetViolation(**_asset_violation_kw())
        assert v.violation_id == "viol-1"
        assert v.operation == "assign"

    def test_empty_reason_allowed(self):
        # reason is not validated as non-empty in __post_init__
        v = AssetViolation(**_asset_violation_kw(reason=""))
        assert v.reason == ""

    def test_metadata_default(self):
        v = AssetViolation(**_asset_violation_kw())
        assert v.metadata == {}


class TestAssetClosureReportConstruction:
    def test_valid_construction(self):
        rpt = AssetClosureReport(**_asset_closure_report_kw())
        assert rpt.report_id == "rpt-1"
        assert rpt.total_assets == 100
        assert rpt.total_asset_value == 1000000.0

    def test_all_zeros(self):
        rpt = AssetClosureReport(**_asset_closure_report_kw(
            total_assets=0, total_active=0, total_retired=0,
            total_assignments=0, total_dependencies=0,
            total_asset_value=0.0))
        assert rpt.total_assets == 0

    def test_metadata_default(self):
        rpt = AssetClosureReport(**_asset_closure_report_kw())
        assert rpt.metadata == {}


# ===================================================================
# 3. VALIDATION FAILURES — empty text fields
# ===================================================================


class TestAssetRecordEmptyTextValidation:
    def test_empty_asset_id(self):
        with pytest.raises(ValueError):
            AssetRecord(**_asset_record_kw(asset_id=""))

    def test_whitespace_asset_id(self):
        with pytest.raises(ValueError):
            AssetRecord(**_asset_record_kw(asset_id="   "))

    def test_empty_name(self):
        with pytest.raises(ValueError):
            AssetRecord(**_asset_record_kw(name=""))

    def test_whitespace_name(self):
        with pytest.raises(ValueError):
            AssetRecord(**_asset_record_kw(name="\t"))

    def test_empty_tenant_id(self):
        with pytest.raises(ValueError):
            AssetRecord(**_asset_record_kw(tenant_id=""))

    def test_whitespace_tenant_id(self):
        with pytest.raises(ValueError):
            AssetRecord(**_asset_record_kw(tenant_id=" \n "))

    def test_empty_registered_at(self):
        with pytest.raises(ValueError):
            AssetRecord(**_asset_record_kw(registered_at=""))


class TestConfigurationItemEmptyTextValidation:
    def test_empty_ci_id(self):
        with pytest.raises(ValueError):
            ConfigurationItem(**_config_item_kw(ci_id=""))

    def test_whitespace_ci_id(self):
        with pytest.raises(ValueError):
            ConfigurationItem(**_config_item_kw(ci_id="  "))

    def test_empty_asset_id(self):
        with pytest.raises(ValueError):
            ConfigurationItem(**_config_item_kw(asset_id=""))

    def test_empty_name(self):
        with pytest.raises(ValueError):
            ConfigurationItem(**_config_item_kw(name=""))

    def test_empty_created_at(self):
        with pytest.raises(ValueError):
            ConfigurationItem(**_config_item_kw(created_at=""))


class TestInventoryRecordEmptyTextValidation:
    def test_empty_inventory_id(self):
        with pytest.raises(ValueError):
            InventoryRecord(**_inventory_record_kw(inventory_id=""))

    def test_empty_asset_id(self):
        with pytest.raises(ValueError):
            InventoryRecord(**_inventory_record_kw(asset_id=""))

    def test_empty_tenant_id(self):
        with pytest.raises(ValueError):
            InventoryRecord(**_inventory_record_kw(tenant_id=""))

    def test_empty_updated_at(self):
        with pytest.raises(ValueError):
            InventoryRecord(**_inventory_record_kw(updated_at=""))


class TestAssetAssignmentEmptyTextValidation:
    def test_empty_assignment_id(self):
        with pytest.raises(ValueError):
            AssetAssignment(**_asset_assignment_kw(assignment_id=""))

    def test_empty_asset_id(self):
        with pytest.raises(ValueError):
            AssetAssignment(**_asset_assignment_kw(asset_id=""))

    def test_empty_scope_ref_id(self):
        with pytest.raises(ValueError):
            AssetAssignment(**_asset_assignment_kw(scope_ref_id=""))

    def test_empty_scope_ref_type(self):
        with pytest.raises(ValueError):
            AssetAssignment(**_asset_assignment_kw(scope_ref_type=""))

    def test_empty_assigned_by(self):
        with pytest.raises(ValueError):
            AssetAssignment(**_asset_assignment_kw(assigned_by=""))

    def test_empty_assigned_at(self):
        with pytest.raises(ValueError):
            AssetAssignment(**_asset_assignment_kw(assigned_at=""))


class TestAssetDependencyEmptyTextValidation:
    def test_empty_dependency_id(self):
        with pytest.raises(ValueError):
            AssetDependency(**_asset_dependency_kw(dependency_id=""))

    def test_empty_asset_id(self):
        with pytest.raises(ValueError):
            AssetDependency(**_asset_dependency_kw(asset_id=""))

    def test_empty_depends_on_asset_id(self):
        with pytest.raises(ValueError):
            AssetDependency(**_asset_dependency_kw(depends_on_asset_id=""))

    def test_empty_created_at(self):
        with pytest.raises(ValueError):
            AssetDependency(**_asset_dependency_kw(created_at=""))


class TestLifecycleEventEmptyTextValidation:
    def test_empty_event_id(self):
        with pytest.raises(ValueError):
            LifecycleEvent(**_lifecycle_event_kw(event_id=""))

    def test_empty_asset_id(self):
        with pytest.raises(ValueError):
            LifecycleEvent(**_lifecycle_event_kw(asset_id=""))

    def test_empty_performed_by(self):
        with pytest.raises(ValueError):
            LifecycleEvent(**_lifecycle_event_kw(performed_by=""))

    def test_empty_performed_at(self):
        with pytest.raises(ValueError):
            LifecycleEvent(**_lifecycle_event_kw(performed_at=""))


class TestAssetAssessmentEmptyTextValidation:
    def test_empty_assessment_id(self):
        with pytest.raises(ValueError):
            AssetAssessment(**_asset_assessment_kw(assessment_id=""))

    def test_empty_asset_id(self):
        with pytest.raises(ValueError):
            AssetAssessment(**_asset_assessment_kw(asset_id=""))

    def test_empty_assessed_by(self):
        with pytest.raises(ValueError):
            AssetAssessment(**_asset_assessment_kw(assessed_by=""))

    def test_empty_assessed_at(self):
        with pytest.raises(ValueError):
            AssetAssessment(**_asset_assessment_kw(assessed_at=""))


class TestAssetSnapshotEmptyTextValidation:
    def test_empty_snapshot_id(self):
        with pytest.raises(ValueError):
            AssetSnapshot(**_asset_snapshot_kw(snapshot_id=""))

    def test_whitespace_snapshot_id(self):
        with pytest.raises(ValueError):
            AssetSnapshot(**_asset_snapshot_kw(snapshot_id="  "))

    def test_empty_captured_at(self):
        with pytest.raises(ValueError):
            AssetSnapshot(**_asset_snapshot_kw(captured_at=""))


class TestAssetViolationEmptyTextValidation:
    def test_empty_violation_id(self):
        with pytest.raises(ValueError):
            AssetViolation(**_asset_violation_kw(violation_id=""))

    def test_empty_asset_id(self):
        with pytest.raises(ValueError):
            AssetViolation(**_asset_violation_kw(asset_id=""))

    def test_empty_tenant_id(self):
        with pytest.raises(ValueError):
            AssetViolation(**_asset_violation_kw(tenant_id=""))

    def test_empty_operation(self):
        with pytest.raises(ValueError):
            AssetViolation(**_asset_violation_kw(operation=""))

    def test_empty_detected_at(self):
        with pytest.raises(ValueError):
            AssetViolation(**_asset_violation_kw(detected_at=""))


class TestAssetClosureReportEmptyTextValidation:
    def test_empty_report_id(self):
        with pytest.raises(ValueError):
            AssetClosureReport(**_asset_closure_report_kw(report_id=""))

    def test_empty_tenant_id(self):
        with pytest.raises(ValueError):
            AssetClosureReport(**_asset_closure_report_kw(tenant_id=""))

    def test_empty_closed_at(self):
        with pytest.raises(ValueError):
            AssetClosureReport(**_asset_closure_report_kw(closed_at=""))


# ===================================================================
# 3b. VALIDATION FAILURES — invalid datetime strings
# ===================================================================


class TestInvalidDatetimeStrings:
    def test_asset_record_bad_datetime(self):
        with pytest.raises(ValueError):
            AssetRecord(**_asset_record_kw(registered_at="not-a-date"))

    def test_config_item_bad_datetime(self):
        with pytest.raises(ValueError):
            ConfigurationItem(**_config_item_kw(created_at="yesterday"))

    def test_inventory_record_bad_datetime(self):
        with pytest.raises(ValueError):
            InventoryRecord(**_inventory_record_kw(updated_at="abc"))

    def test_asset_assignment_bad_datetime(self):
        with pytest.raises(ValueError):
            AssetAssignment(**_asset_assignment_kw(assigned_at="13/06/2025"))

    def test_asset_dependency_bad_datetime(self):
        with pytest.raises(ValueError):
            AssetDependency(**_asset_dependency_kw(created_at="June 1st 2025"))

    def test_lifecycle_event_bad_datetime(self):
        with pytest.raises(ValueError):
            LifecycleEvent(**_lifecycle_event_kw(performed_at="2025-99-99"))

    def test_asset_assessment_bad_datetime(self):
        with pytest.raises(ValueError):
            AssetAssessment(**_asset_assessment_kw(assessed_at="foobar"))

    def test_asset_snapshot_bad_datetime(self):
        with pytest.raises(ValueError):
            AssetSnapshot(**_asset_snapshot_kw(captured_at="not-valid"))

    def test_asset_violation_bad_datetime(self):
        with pytest.raises(ValueError):
            AssetViolation(**_asset_violation_kw(detected_at="not-a-date"))

    def test_asset_closure_report_bad_datetime(self):
        with pytest.raises(ValueError):
            AssetClosureReport(**_asset_closure_report_kw(closed_at="not-a-date"))


# ===================================================================
# 3c. VALIDATION FAILURES — negative numeric values
# ===================================================================


class TestAssetRecordNegativeValue:
    def test_negative_value(self):
        with pytest.raises(ValueError):
            AssetRecord(**_asset_record_kw(value=-1.0))

    def test_negative_value_small(self):
        with pytest.raises(ValueError):
            AssetRecord(**_asset_record_kw(value=-0.01))

    def test_nan_value(self):
        with pytest.raises(ValueError):
            AssetRecord(**_asset_record_kw(value=float("nan")))

    def test_inf_value(self):
        with pytest.raises(ValueError):
            AssetRecord(**_asset_record_kw(value=float("inf")))

    def test_neg_inf_value(self):
        with pytest.raises(ValueError):
            AssetRecord(**_asset_record_kw(value=float("-inf")))

    def test_bool_value_rejected(self):
        with pytest.raises(ValueError):
            AssetRecord(**_asset_record_kw(value=True))


class TestInventoryRecordNegativeQuantities:
    def test_negative_total_quantity(self):
        with pytest.raises(ValueError):
            InventoryRecord(**_inventory_record_kw(total_quantity=-1))

    def test_negative_assigned_quantity(self):
        with pytest.raises(ValueError):
            InventoryRecord(**_inventory_record_kw(assigned_quantity=-1))

    def test_negative_available_quantity(self):
        with pytest.raises(ValueError):
            InventoryRecord(**_inventory_record_kw(available_quantity=-1))

    def test_float_total_quantity_rejected(self):
        with pytest.raises(ValueError):
            InventoryRecord(**_inventory_record_kw(total_quantity=1.5))

    def test_bool_total_quantity_rejected(self):
        with pytest.raises(ValueError):
            InventoryRecord(**_inventory_record_kw(total_quantity=True))

    def test_bool_assigned_quantity_rejected(self):
        with pytest.raises(ValueError):
            InventoryRecord(**_inventory_record_kw(assigned_quantity=False))


class TestAssetSnapshotNegativeValues:
    def test_negative_total_assets(self):
        with pytest.raises(ValueError):
            AssetSnapshot(**_asset_snapshot_kw(total_assets=-1))

    def test_negative_total_active(self):
        with pytest.raises(ValueError):
            AssetSnapshot(**_asset_snapshot_kw(total_active=-1))

    def test_negative_total_retired(self):
        with pytest.raises(ValueError):
            AssetSnapshot(**_asset_snapshot_kw(total_retired=-1))

    def test_negative_total_config_items(self):
        with pytest.raises(ValueError):
            AssetSnapshot(**_asset_snapshot_kw(total_config_items=-1))

    def test_negative_total_inventory(self):
        with pytest.raises(ValueError):
            AssetSnapshot(**_asset_snapshot_kw(total_inventory=-1))

    def test_negative_total_assignments(self):
        with pytest.raises(ValueError):
            AssetSnapshot(**_asset_snapshot_kw(total_assignments=-1))

    def test_negative_total_dependencies(self):
        with pytest.raises(ValueError):
            AssetSnapshot(**_asset_snapshot_kw(total_dependencies=-1))

    def test_negative_total_violations(self):
        with pytest.raises(ValueError):
            AssetSnapshot(**_asset_snapshot_kw(total_violations=-1))

    def test_negative_total_asset_value(self):
        with pytest.raises(ValueError):
            AssetSnapshot(**_asset_snapshot_kw(total_asset_value=-1.0))

    def test_nan_total_asset_value(self):
        with pytest.raises(ValueError):
            AssetSnapshot(**_asset_snapshot_kw(total_asset_value=float("nan")))

    def test_inf_total_asset_value(self):
        with pytest.raises(ValueError):
            AssetSnapshot(**_asset_snapshot_kw(total_asset_value=float("inf")))

    def test_bool_total_assets_rejected(self):
        with pytest.raises(ValueError):
            AssetSnapshot(**_asset_snapshot_kw(total_assets=True))


class TestAssetClosureReportNegativeValues:
    def test_negative_total_assets(self):
        with pytest.raises(ValueError):
            AssetClosureReport(**_asset_closure_report_kw(total_assets=-1))

    def test_negative_total_active(self):
        with pytest.raises(ValueError):
            AssetClosureReport(**_asset_closure_report_kw(total_active=-1))

    def test_negative_total_retired(self):
        with pytest.raises(ValueError):
            AssetClosureReport(**_asset_closure_report_kw(total_retired=-1))

    def test_negative_total_assignments(self):
        with pytest.raises(ValueError):
            AssetClosureReport(**_asset_closure_report_kw(total_assignments=-1))

    def test_negative_total_dependencies(self):
        with pytest.raises(ValueError):
            AssetClosureReport(**_asset_closure_report_kw(total_dependencies=-1))

    def test_negative_total_asset_value(self):
        with pytest.raises(ValueError):
            AssetClosureReport(**_asset_closure_report_kw(total_asset_value=-100.0))

    def test_nan_total_asset_value(self):
        with pytest.raises(ValueError):
            AssetClosureReport(**_asset_closure_report_kw(total_asset_value=float("nan")))

    def test_bool_total_assets_rejected(self):
        with pytest.raises(ValueError):
            AssetClosureReport(**_asset_closure_report_kw(total_assets=False))


# ===================================================================
# 3d. VALIDATION FAILURES — unit float out-of-range (health_score, risk_score)
# ===================================================================


class TestAssetAssessmentUnitFloatValidation:
    def test_health_score_negative(self):
        with pytest.raises(ValueError):
            AssetAssessment(**_asset_assessment_kw(health_score=-0.01))

    def test_health_score_above_one(self):
        with pytest.raises(ValueError):
            AssetAssessment(**_asset_assessment_kw(health_score=1.01))

    def test_health_score_way_above(self):
        with pytest.raises(ValueError):
            AssetAssessment(**_asset_assessment_kw(health_score=5.0))

    def test_health_score_nan(self):
        with pytest.raises(ValueError):
            AssetAssessment(**_asset_assessment_kw(health_score=float("nan")))

    def test_health_score_inf(self):
        with pytest.raises(ValueError):
            AssetAssessment(**_asset_assessment_kw(health_score=float("inf")))

    def test_health_score_neg_inf(self):
        with pytest.raises(ValueError):
            AssetAssessment(**_asset_assessment_kw(health_score=float("-inf")))

    def test_health_score_bool_rejected(self):
        with pytest.raises(ValueError):
            AssetAssessment(**_asset_assessment_kw(health_score=True))

    def test_risk_score_negative(self):
        with pytest.raises(ValueError):
            AssetAssessment(**_asset_assessment_kw(risk_score=-0.5))

    def test_risk_score_above_one(self):
        with pytest.raises(ValueError):
            AssetAssessment(**_asset_assessment_kw(risk_score=1.001))

    def test_risk_score_nan(self):
        with pytest.raises(ValueError):
            AssetAssessment(**_asset_assessment_kw(risk_score=float("nan")))

    def test_risk_score_inf(self):
        with pytest.raises(ValueError):
            AssetAssessment(**_asset_assessment_kw(risk_score=float("inf")))

    def test_risk_score_bool_rejected(self):
        with pytest.raises(ValueError):
            AssetAssessment(**_asset_assessment_kw(risk_score=False))


# ===================================================================
# 3e. VALIDATION FAILURES — wrong enum types
# ===================================================================


class TestWrongEnumTypeValidation:
    def test_asset_record_kind_string(self):
        with pytest.raises(ValueError):
            AssetRecord(**_asset_record_kw(kind="hardware"))

    def test_asset_record_kind_wrong_enum(self):
        with pytest.raises(ValueError):
            AssetRecord(**_asset_record_kw(kind=AssetStatus.ACTIVE))

    def test_asset_record_status_string(self):
        with pytest.raises(ValueError):
            AssetRecord(**_asset_record_kw(status="active"))

    def test_asset_record_status_wrong_enum(self):
        with pytest.raises(ValueError):
            AssetRecord(**_asset_record_kw(status=AssetKind.HARDWARE))

    def test_asset_record_ownership_string(self):
        with pytest.raises(ValueError):
            AssetRecord(**_asset_record_kw(ownership="owned"))

    def test_asset_record_ownership_wrong_enum(self):
        with pytest.raises(ValueError):
            AssetRecord(**_asset_record_kw(ownership=LifecycleDisposition.DEPLOYED))

    def test_config_item_status_string(self):
        with pytest.raises(ValueError):
            ConfigurationItem(**_config_item_kw(status="active"))

    def test_config_item_status_wrong_enum(self):
        with pytest.raises(ValueError):
            ConfigurationItem(**_config_item_kw(status=AssetStatus.ACTIVE))

    def test_inventory_record_disposition_string(self):
        with pytest.raises(ValueError):
            InventoryRecord(**_inventory_record_kw(disposition="available"))

    def test_inventory_record_disposition_wrong_enum(self):
        with pytest.raises(ValueError):
            InventoryRecord(**_inventory_record_kw(disposition=AssetStatus.ACTIVE))

    def test_lifecycle_event_disposition_string(self):
        with pytest.raises(ValueError):
            LifecycleEvent(**_lifecycle_event_kw(disposition="provisioned"))

    def test_lifecycle_event_disposition_wrong_enum(self):
        with pytest.raises(ValueError):
            LifecycleEvent(**_lifecycle_event_kw(disposition=InventoryDisposition.AVAILABLE))


# ===================================================================
# 4. FROZEN IMMUTABILITY
# ===================================================================


class TestAssetRecordFrozen:
    def test_cannot_set_asset_id(self):
        rec = AssetRecord(**_asset_record_kw())
        with pytest.raises(dataclasses.FrozenInstanceError):
            rec.asset_id = "new-id"

    def test_cannot_set_name(self):
        rec = AssetRecord(**_asset_record_kw())
        with pytest.raises(dataclasses.FrozenInstanceError):
            rec.name = "New Name"

    def test_cannot_set_tenant_id(self):
        rec = AssetRecord(**_asset_record_kw())
        with pytest.raises(dataclasses.FrozenInstanceError):
            rec.tenant_id = "t-new"

    def test_cannot_set_kind(self):
        rec = AssetRecord(**_asset_record_kw())
        with pytest.raises(dataclasses.FrozenInstanceError):
            rec.kind = AssetKind.SOFTWARE

    def test_cannot_set_value(self):
        rec = AssetRecord(**_asset_record_kw())
        with pytest.raises(dataclasses.FrozenInstanceError):
            rec.value = 9999.0

    def test_cannot_set_metadata(self):
        rec = AssetRecord(**_asset_record_kw())
        with pytest.raises(dataclasses.FrozenInstanceError):
            rec.metadata = {}


class TestConfigurationItemFrozen:
    def test_cannot_set_ci_id(self):
        ci = ConfigurationItem(**_config_item_kw())
        with pytest.raises(dataclasses.FrozenInstanceError):
            ci.ci_id = "new"

    def test_cannot_set_status(self):
        ci = ConfigurationItem(**_config_item_kw())
        with pytest.raises(dataclasses.FrozenInstanceError):
            ci.status = ConfigurationItemStatus.DEPRECATED


class TestInventoryRecordFrozen:
    def test_cannot_set_inventory_id(self):
        inv = InventoryRecord(**_inventory_record_kw())
        with pytest.raises(dataclasses.FrozenInstanceError):
            inv.inventory_id = "new"

    def test_cannot_set_total_quantity(self):
        inv = InventoryRecord(**_inventory_record_kw())
        with pytest.raises(dataclasses.FrozenInstanceError):
            inv.total_quantity = 999


class TestAssetAssignmentFrozen:
    def test_cannot_set_assignment_id(self):
        asg = AssetAssignment(**_asset_assignment_kw())
        with pytest.raises(dataclasses.FrozenInstanceError):
            asg.assignment_id = "new"

    def test_cannot_set_assigned_by(self):
        asg = AssetAssignment(**_asset_assignment_kw())
        with pytest.raises(dataclasses.FrozenInstanceError):
            asg.assigned_by = "other"


class TestAssetDependencyFrozen:
    def test_cannot_set_dependency_id(self):
        dep = AssetDependency(**_asset_dependency_kw())
        with pytest.raises(dataclasses.FrozenInstanceError):
            dep.dependency_id = "new"

    def test_cannot_set_depends_on_asset_id(self):
        dep = AssetDependency(**_asset_dependency_kw())
        with pytest.raises(dataclasses.FrozenInstanceError):
            dep.depends_on_asset_id = "a-99"


class TestLifecycleEventFrozen:
    def test_cannot_set_event_id(self):
        evt = LifecycleEvent(**_lifecycle_event_kw())
        with pytest.raises(dataclasses.FrozenInstanceError):
            evt.event_id = "new"

    def test_cannot_set_disposition(self):
        evt = LifecycleEvent(**_lifecycle_event_kw())
        with pytest.raises(dataclasses.FrozenInstanceError):
            evt.disposition = LifecycleDisposition.DEPLOYED


class TestAssetAssessmentFrozen:
    def test_cannot_set_assessment_id(self):
        a = AssetAssessment(**_asset_assessment_kw())
        with pytest.raises(dataclasses.FrozenInstanceError):
            a.assessment_id = "new"

    def test_cannot_set_health_score(self):
        a = AssetAssessment(**_asset_assessment_kw())
        with pytest.raises(dataclasses.FrozenInstanceError):
            a.health_score = 0.5


class TestAssetSnapshotFrozen:
    def test_cannot_set_snapshot_id(self):
        snap = AssetSnapshot(**_asset_snapshot_kw())
        with pytest.raises(dataclasses.FrozenInstanceError):
            snap.snapshot_id = "new"

    def test_cannot_set_total_assets(self):
        snap = AssetSnapshot(**_asset_snapshot_kw())
        with pytest.raises(dataclasses.FrozenInstanceError):
            snap.total_assets = 999


class TestAssetViolationFrozen:
    def test_cannot_set_violation_id(self):
        v = AssetViolation(**_asset_violation_kw())
        with pytest.raises(dataclasses.FrozenInstanceError):
            v.violation_id = "new"

    def test_cannot_set_operation(self):
        v = AssetViolation(**_asset_violation_kw())
        with pytest.raises(dataclasses.FrozenInstanceError):
            v.operation = "other"


class TestAssetClosureReportFrozen:
    def test_cannot_set_report_id(self):
        rpt = AssetClosureReport(**_asset_closure_report_kw())
        with pytest.raises(dataclasses.FrozenInstanceError):
            rpt.report_id = "new"

    def test_cannot_set_total_asset_value(self):
        rpt = AssetClosureReport(**_asset_closure_report_kw())
        with pytest.raises(dataclasses.FrozenInstanceError):
            rpt.total_asset_value = 0.0


# ===================================================================
# 5. METADATA FREEZING
# ===================================================================


class TestAssetRecordMetadataFreezing:
    def test_metadata_is_mapping_proxy(self):
        rec = AssetRecord(**_asset_record_kw(metadata={"k": "v"}))
        assert isinstance(rec.metadata, MappingProxyType)

    def test_empty_metadata_is_mapping_proxy(self):
        rec = AssetRecord(**_asset_record_kw())
        assert isinstance(rec.metadata, MappingProxyType)

    def test_metadata_mutation_raises(self):
        rec = AssetRecord(**_asset_record_kw(metadata={"k": "v"}))
        with pytest.raises(TypeError):
            rec.metadata["k"] = "new"

    def test_metadata_add_raises(self):
        rec = AssetRecord(**_asset_record_kw(metadata={"k": "v"}))
        with pytest.raises(TypeError):
            rec.metadata["new_key"] = "val"

    def test_nested_dict_frozen(self):
        rec = AssetRecord(**_asset_record_kw(metadata={"nested": {"a": 1}}))
        assert isinstance(rec.metadata["nested"], MappingProxyType)

    def test_list_in_metadata_becomes_tuple(self):
        rec = AssetRecord(**_asset_record_kw(metadata={"tags": [1, 2, 3]}))
        assert isinstance(rec.metadata["tags"], tuple)
        assert rec.metadata["tags"] == (1, 2, 3)

    def test_nested_list_in_dict_becomes_tuple(self):
        rec = AssetRecord(**_asset_record_kw(metadata={"data": {"items": ["a", "b"]}}))
        assert isinstance(rec.metadata["data"]["items"], tuple)

    def test_set_in_metadata_becomes_frozenset(self):
        rec = AssetRecord(**_asset_record_kw(metadata={"s": {1, 2}}))
        assert isinstance(rec.metadata["s"], frozenset)


class TestConfigurationItemMetadataFreezing:
    def test_metadata_is_mapping_proxy(self):
        ci = ConfigurationItem(**_config_item_kw(metadata={"k": "v"}))
        assert isinstance(ci.metadata, MappingProxyType)

    def test_list_becomes_tuple(self):
        ci = ConfigurationItem(**_config_item_kw(metadata={"lst": [1, 2]}))
        assert isinstance(ci.metadata["lst"], tuple)


class TestInventoryRecordMetadataFreezing:
    def test_metadata_is_mapping_proxy(self):
        inv = InventoryRecord(**_inventory_record_kw(metadata={"k": "v"}))
        assert isinstance(inv.metadata, MappingProxyType)

    def test_list_becomes_tuple(self):
        inv = InventoryRecord(**_inventory_record_kw(metadata={"lst": [1]}))
        assert isinstance(inv.metadata["lst"], tuple)


class TestAssetAssignmentMetadataFreezing:
    def test_metadata_is_mapping_proxy(self):
        asg = AssetAssignment(**_asset_assignment_kw(metadata={"k": "v"}))
        assert isinstance(asg.metadata, MappingProxyType)


class TestAssetDependencyMetadataFreezing:
    def test_metadata_is_mapping_proxy(self):
        dep = AssetDependency(**_asset_dependency_kw(metadata={"k": "v"}))
        assert isinstance(dep.metadata, MappingProxyType)


class TestLifecycleEventMetadataFreezing:
    def test_metadata_is_mapping_proxy(self):
        evt = LifecycleEvent(**_lifecycle_event_kw(metadata={"k": "v"}))
        assert isinstance(evt.metadata, MappingProxyType)


class TestAssetAssessmentMetadataFreezing:
    def test_metadata_is_mapping_proxy(self):
        a = AssetAssessment(**_asset_assessment_kw(metadata={"k": "v"}))
        assert isinstance(a.metadata, MappingProxyType)


class TestAssetSnapshotMetadataFreezing:
    def test_metadata_is_mapping_proxy(self):
        snap = AssetSnapshot(**_asset_snapshot_kw(metadata={"k": "v"}))
        assert isinstance(snap.metadata, MappingProxyType)


class TestAssetViolationMetadataFreezing:
    def test_metadata_is_mapping_proxy(self):
        v = AssetViolation(**_asset_violation_kw(metadata={"k": "v"}))
        assert isinstance(v.metadata, MappingProxyType)


class TestAssetClosureReportMetadataFreezing:
    def test_metadata_is_mapping_proxy(self):
        rpt = AssetClosureReport(**_asset_closure_report_kw(metadata={"k": "v"}))
        assert isinstance(rpt.metadata, MappingProxyType)


# ===================================================================
# 6. to_dict() SERIALIZATION
# ===================================================================


class TestAssetRecordToDict:
    def test_returns_dict(self):
        rec = AssetRecord(**_asset_record_kw())
        d = rec.to_dict()
        assert isinstance(d, dict)

    def test_contains_all_keys(self):
        rec = AssetRecord(**_asset_record_kw())
        d = rec.to_dict()
        expected_keys = {
            "asset_id", "name", "tenant_id", "kind", "status",
            "ownership", "owner_ref", "vendor_ref", "value",
            "registered_at", "metadata",
        }
        assert set(d.keys()) == expected_keys

    def test_enum_values_remain_enum(self):
        rec = AssetRecord(**_asset_record_kw())
        d = rec.to_dict()
        assert isinstance(d["kind"], AssetKind)
        assert isinstance(d["status"], AssetStatus)
        assert isinstance(d["ownership"], OwnershipType)

    def test_string_fields_preserved(self):
        rec = AssetRecord(**_asset_record_kw())
        d = rec.to_dict()
        assert d["asset_id"] == "a-1"
        assert d["name"] == "Server A"
        assert d["tenant_id"] == "t-1"

    def test_numeric_field_preserved(self):
        rec = AssetRecord(**_asset_record_kw(value=42.5))
        d = rec.to_dict()
        assert d["value"] == 42.5

    def test_metadata_thawed_to_dict(self):
        rec = AssetRecord(**_asset_record_kw(metadata={"k": "v"}))
        d = rec.to_dict()
        assert isinstance(d["metadata"], dict)
        assert d["metadata"]["k"] == "v"

    def test_nested_metadata_thawed(self):
        rec = AssetRecord(**_asset_record_kw(metadata={"nested": {"a": 1}}))
        d = rec.to_dict()
        assert isinstance(d["metadata"]["nested"], dict)

    def test_list_metadata_thawed_to_list(self):
        rec = AssetRecord(**_asset_record_kw(metadata={"items": [1, 2]}))
        d = rec.to_dict()
        # tuples are thawed back to lists by thaw_value
        assert isinstance(d["metadata"]["items"], list)


class TestConfigurationItemToDict:
    def test_returns_dict(self):
        ci = ConfigurationItem(**_config_item_kw())
        d = ci.to_dict()
        assert isinstance(d, dict)

    def test_contains_all_keys(self):
        ci = ConfigurationItem(**_config_item_kw())
        d = ci.to_dict()
        expected_keys = {
            "ci_id", "asset_id", "name", "status",
            "environment_ref", "workspace_ref", "version",
            "created_at", "metadata",
        }
        assert set(d.keys()) == expected_keys

    def test_enum_values_remain_enum(self):
        ci = ConfigurationItem(**_config_item_kw())
        d = ci.to_dict()
        assert isinstance(d["status"], ConfigurationItemStatus)

    def test_string_fields_preserved(self):
        ci = ConfigurationItem(**_config_item_kw())
        d = ci.to_dict()
        assert d["ci_id"] == "ci-1"


class TestInventoryRecordToDict:
    def test_returns_dict(self):
        inv = InventoryRecord(**_inventory_record_kw())
        d = inv.to_dict()
        assert isinstance(d, dict)

    def test_contains_all_keys(self):
        inv = InventoryRecord(**_inventory_record_kw())
        d = inv.to_dict()
        expected_keys = {
            "inventory_id", "asset_id", "tenant_id", "disposition",
            "total_quantity", "assigned_quantity", "available_quantity",
            "updated_at", "metadata",
        }
        assert set(d.keys()) == expected_keys

    def test_enum_values_remain_enum(self):
        inv = InventoryRecord(**_inventory_record_kw())
        d = inv.to_dict()
        assert isinstance(d["disposition"], InventoryDisposition)

    def test_int_fields_preserved(self):
        inv = InventoryRecord(**_inventory_record_kw())
        d = inv.to_dict()
        assert d["total_quantity"] == 100
        assert d["assigned_quantity"] == 20
        assert d["available_quantity"] == 80


class TestAssetAssignmentToDict:
    def test_returns_dict(self):
        asg = AssetAssignment(**_asset_assignment_kw())
        d = asg.to_dict()
        assert isinstance(d, dict)

    def test_contains_all_keys(self):
        asg = AssetAssignment(**_asset_assignment_kw())
        d = asg.to_dict()
        expected_keys = {
            "assignment_id", "asset_id", "scope_ref_id",
            "scope_ref_type", "assigned_by", "assigned_at", "metadata",
        }
        assert set(d.keys()) == expected_keys

    def test_string_fields_preserved(self):
        asg = AssetAssignment(**_asset_assignment_kw())
        d = asg.to_dict()
        assert d["assignment_id"] == "asg-1"
        assert d["scope_ref_type"] == "campaign"


class TestAssetDependencyToDict:
    def test_returns_dict(self):
        dep = AssetDependency(**_asset_dependency_kw())
        d = dep.to_dict()
        assert isinstance(d, dict)

    def test_contains_all_keys(self):
        dep = AssetDependency(**_asset_dependency_kw())
        d = dep.to_dict()
        expected_keys = {
            "dependency_id", "asset_id", "depends_on_asset_id",
            "description", "created_at", "metadata",
        }
        assert set(d.keys()) == expected_keys

    def test_string_fields_preserved(self):
        dep = AssetDependency(**_asset_dependency_kw())
        d = dep.to_dict()
        assert d["depends_on_asset_id"] == "a-2"


class TestLifecycleEventToDict:
    def test_returns_dict(self):
        evt = LifecycleEvent(**_lifecycle_event_kw())
        d = evt.to_dict()
        assert isinstance(d, dict)

    def test_contains_all_keys(self):
        evt = LifecycleEvent(**_lifecycle_event_kw())
        d = evt.to_dict()
        expected_keys = {
            "event_id", "asset_id", "disposition", "description",
            "performed_by", "performed_at", "metadata",
        }
        assert set(d.keys()) == expected_keys

    def test_enum_values_remain_enum(self):
        evt = LifecycleEvent(**_lifecycle_event_kw())
        d = evt.to_dict()
        assert isinstance(d["disposition"], LifecycleDisposition)


class TestAssetAssessmentToDict:
    def test_returns_dict(self):
        a = AssetAssessment(**_asset_assessment_kw())
        d = a.to_dict()
        assert isinstance(d, dict)

    def test_contains_all_keys(self):
        a = AssetAssessment(**_asset_assessment_kw())
        d = a.to_dict()
        expected_keys = {
            "assessment_id", "asset_id", "health_score", "risk_score",
            "assessed_by", "assessed_at", "metadata",
        }
        assert set(d.keys()) == expected_keys

    def test_float_fields_preserved(self):
        a = AssetAssessment(**_asset_assessment_kw())
        d = a.to_dict()
        assert d["health_score"] == 0.9
        assert d["risk_score"] == 0.1


class TestAssetSnapshotToDict:
    def test_returns_dict(self):
        snap = AssetSnapshot(**_asset_snapshot_kw())
        d = snap.to_dict()
        assert isinstance(d, dict)

    def test_contains_all_keys(self):
        snap = AssetSnapshot(**_asset_snapshot_kw())
        d = snap.to_dict()
        expected_keys = {
            "snapshot_id", "total_assets", "total_active", "total_retired",
            "total_config_items", "total_inventory", "total_assignments",
            "total_dependencies", "total_violations", "total_asset_value",
            "captured_at", "metadata",
        }
        assert set(d.keys()) == expected_keys

    def test_int_fields_preserved(self):
        snap = AssetSnapshot(**_asset_snapshot_kw())
        d = snap.to_dict()
        assert d["total_assets"] == 50
        assert d["total_violations"] == 2

    def test_float_field_preserved(self):
        snap = AssetSnapshot(**_asset_snapshot_kw())
        d = snap.to_dict()
        assert d["total_asset_value"] == 500000.0


class TestAssetViolationToDict:
    def test_returns_dict(self):
        v = AssetViolation(**_asset_violation_kw())
        d = v.to_dict()
        assert isinstance(d, dict)

    def test_contains_all_keys(self):
        v = AssetViolation(**_asset_violation_kw())
        d = v.to_dict()
        expected_keys = {
            "violation_id", "asset_id", "tenant_id", "operation",
            "reason", "detected_at", "metadata",
        }
        assert set(d.keys()) == expected_keys

    def test_string_fields_preserved(self):
        v = AssetViolation(**_asset_violation_kw())
        d = v.to_dict()
        assert d["operation"] == "assign"
        assert d["reason"] == "retired asset"


class TestAssetClosureReportToDict:
    def test_returns_dict(self):
        rpt = AssetClosureReport(**_asset_closure_report_kw())
        d = rpt.to_dict()
        assert isinstance(d, dict)

    def test_contains_all_keys(self):
        rpt = AssetClosureReport(**_asset_closure_report_kw())
        d = rpt.to_dict()
        expected_keys = {
            "report_id", "tenant_id", "total_assets", "total_active",
            "total_retired", "total_assignments", "total_dependencies",
            "total_asset_value", "closed_at", "metadata",
        }
        assert set(d.keys()) == expected_keys

    def test_int_fields_preserved(self):
        rpt = AssetClosureReport(**_asset_closure_report_kw())
        d = rpt.to_dict()
        assert d["total_assets"] == 100

    def test_float_field_preserved(self):
        rpt = AssetClosureReport(**_asset_closure_report_kw())
        d = rpt.to_dict()
        assert d["total_asset_value"] == 1000000.0


# ===================================================================
# 7. ADDITIONAL EDGE CASES
# ===================================================================


class TestAssetRecordNonIntegerTextFieldTypes:
    """Test that non-string types are rejected for text fields."""

    def test_int_asset_id_rejected(self):
        with pytest.raises((ValueError, TypeError)):
            AssetRecord(**_asset_record_kw(asset_id=123))

    def test_none_asset_id_rejected(self):
        with pytest.raises((ValueError, TypeError)):
            AssetRecord(**_asset_record_kw(asset_id=None))

    def test_int_name_rejected(self):
        with pytest.raises((ValueError, TypeError)):
            AssetRecord(**_asset_record_kw(name=456))

    def test_none_tenant_id_rejected(self):
        with pytest.raises((ValueError, TypeError)):
            AssetRecord(**_asset_record_kw(tenant_id=None))


class TestConfigurationItemNonStringFields:
    def test_int_ci_id_rejected(self):
        with pytest.raises((ValueError, TypeError)):
            ConfigurationItem(**_config_item_kw(ci_id=42))

    def test_none_name_rejected(self):
        with pytest.raises((ValueError, TypeError)):
            ConfigurationItem(**_config_item_kw(name=None))


class TestInventoryRecordNonStringFields:
    def test_int_inventory_id_rejected(self):
        with pytest.raises((ValueError, TypeError)):
            InventoryRecord(**_inventory_record_kw(inventory_id=99))

    def test_none_asset_id_rejected(self):
        with pytest.raises((ValueError, TypeError)):
            InventoryRecord(**_inventory_record_kw(asset_id=None))


class TestAssetAssignmentNonStringFields:
    def test_int_assignment_id_rejected(self):
        with pytest.raises((ValueError, TypeError)):
            AssetAssignment(**_asset_assignment_kw(assignment_id=1))

    def test_none_scope_ref_id_rejected(self):
        with pytest.raises((ValueError, TypeError)):
            AssetAssignment(**_asset_assignment_kw(scope_ref_id=None))


class TestAssetDependencyNonStringFields:
    def test_int_dependency_id_rejected(self):
        with pytest.raises((ValueError, TypeError)):
            AssetDependency(**_asset_dependency_kw(dependency_id=7))


class TestLifecycleEventNonStringFields:
    def test_int_event_id_rejected(self):
        with pytest.raises((ValueError, TypeError)):
            LifecycleEvent(**_lifecycle_event_kw(event_id=1))

    def test_none_performed_by_rejected(self):
        with pytest.raises((ValueError, TypeError)):
            LifecycleEvent(**_lifecycle_event_kw(performed_by=None))


class TestAssetAssessmentNonStringFields:
    def test_int_assessment_id_rejected(self):
        with pytest.raises((ValueError, TypeError)):
            AssetAssessment(**_asset_assessment_kw(assessment_id=1))

    def test_string_health_score_rejected(self):
        with pytest.raises((ValueError, TypeError)):
            AssetAssessment(**_asset_assessment_kw(health_score="0.5"))


class TestAssetSnapshotNonStringFields:
    def test_int_snapshot_id_rejected(self):
        with pytest.raises((ValueError, TypeError)):
            AssetSnapshot(**_asset_snapshot_kw(snapshot_id=1))

    def test_string_total_assets_rejected(self):
        with pytest.raises((ValueError, TypeError)):
            AssetSnapshot(**_asset_snapshot_kw(total_assets="50"))


class TestAssetViolationNonStringFields:
    def test_int_violation_id_rejected(self):
        with pytest.raises((ValueError, TypeError)):
            AssetViolation(**_asset_violation_kw(violation_id=1))


class TestAssetClosureReportNonStringFields:
    def test_int_report_id_rejected(self):
        with pytest.raises((ValueError, TypeError)):
            AssetClosureReport(**_asset_closure_report_kw(report_id=1))

    def test_string_total_assets_rejected(self):
        with pytest.raises((ValueError, TypeError)):
            AssetClosureReport(**_asset_closure_report_kw(total_assets="100"))


# ===================================================================
# 8. DATACLASS PROPERTIES — slots and frozen flags
# ===================================================================


class TestDataclassFlags:
    """Verify all contract dataclasses use frozen=True, slots=True."""

    @pytest.mark.parametrize("cls", [
        AssetRecord, ConfigurationItem, InventoryRecord,
        AssetAssignment, AssetDependency, LifecycleEvent,
        AssetAssessment, AssetSnapshot, AssetViolation,
        AssetClosureReport,
    ])
    def test_frozen_flag(self, cls):
        assert dataclasses.fields(cls) is not None  # is a dataclass
        # Frozen dataclasses have __delattr__ that raises FrozenInstanceError
        # Slots dataclasses have __slots__
        assert hasattr(cls, "__slots__")

    @pytest.mark.parametrize("cls,factory", [
        (AssetRecord, _asset_record_kw),
        (ConfigurationItem, _config_item_kw),
        (InventoryRecord, _inventory_record_kw),
        (AssetAssignment, _asset_assignment_kw),
        (AssetDependency, _asset_dependency_kw),
        (LifecycleEvent, _lifecycle_event_kw),
        (AssetAssessment, _asset_assessment_kw),
        (AssetSnapshot, _asset_snapshot_kw),
        (AssetViolation, _asset_violation_kw),
        (AssetClosureReport, _asset_closure_report_kw),
    ])
    def test_delattr_raises_frozen(self, cls, factory):
        obj = cls(**factory())
        first_field = dataclasses.fields(cls)[0].name
        with pytest.raises(dataclasses.FrozenInstanceError):
            delattr(obj, first_field)


# ===================================================================
# 9. EQUALITY AND IDENTITY
# ===================================================================


class TestEquality:
    def test_identical_asset_records_equal(self):
        a = AssetRecord(**_asset_record_kw())
        b = AssetRecord(**_asset_record_kw())
        assert a == b

    def test_different_asset_records_not_equal(self):
        a = AssetRecord(**_asset_record_kw(asset_id="a-1"))
        b = AssetRecord(**_asset_record_kw(asset_id="a-2"))
        assert a != b

    def test_identical_config_items_equal(self):
        a = ConfigurationItem(**_config_item_kw())
        b = ConfigurationItem(**_config_item_kw())
        assert a == b

    def test_identical_inventory_records_equal(self):
        a = InventoryRecord(**_inventory_record_kw())
        b = InventoryRecord(**_inventory_record_kw())
        assert a == b

    def test_identical_assignments_equal(self):
        a = AssetAssignment(**_asset_assignment_kw())
        b = AssetAssignment(**_asset_assignment_kw())
        assert a == b

    def test_identical_dependencies_equal(self):
        a = AssetDependency(**_asset_dependency_kw())
        b = AssetDependency(**_asset_dependency_kw())
        assert a == b

    def test_identical_lifecycle_events_equal(self):
        a = LifecycleEvent(**_lifecycle_event_kw())
        b = LifecycleEvent(**_lifecycle_event_kw())
        assert a == b

    def test_identical_assessments_equal(self):
        a = AssetAssessment(**_asset_assessment_kw())
        b = AssetAssessment(**_asset_assessment_kw())
        assert a == b

    def test_identical_snapshots_equal(self):
        a = AssetSnapshot(**_asset_snapshot_kw())
        b = AssetSnapshot(**_asset_snapshot_kw())
        assert a == b

    def test_identical_violations_equal(self):
        a = AssetViolation(**_asset_violation_kw())
        b = AssetViolation(**_asset_violation_kw())
        assert a == b

    def test_identical_closure_reports_equal(self):
        a = AssetClosureReport(**_asset_closure_report_kw())
        b = AssetClosureReport(**_asset_closure_report_kw())
        assert a == b

    def test_different_types_not_equal(self):
        rec = AssetRecord(**_asset_record_kw())
        ci = ConfigurationItem(**_config_item_kw())
        assert rec != ci
