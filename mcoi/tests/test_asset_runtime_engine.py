"""Purpose: verify asset runtime engine — asset registration, config items,
    inventory, assignments, dependencies, lifecycle events, assessments,
    violation detection, snapshots, and state hashing.
Governance scope: asset-runtime plane tests only.
Dependencies: asset_runtime engine, event_spine, contracts, invariants.
Invariants:
  - Retired/disposed assets cannot be assigned.
  - Depleted inventory blocks further assignment.
  - Every mutation emits an event.
  - All returns are immutable (frozen dataclasses / tuples).
  - Duplicate IDs always raise RuntimeCoreInvariantError.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.core.asset_runtime import AssetRuntimeEngine
from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
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


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def spine() -> EventSpineEngine:
    """Fresh event spine for each test."""
    return EventSpineEngine()


@pytest.fixture()
def engine(spine: EventSpineEngine) -> AssetRuntimeEngine:
    """Fresh asset runtime engine backed by a clean event spine."""
    return AssetRuntimeEngine(spine)


def _register_default_asset(
    eng: AssetRuntimeEngine,
    asset_id: str = "a-1",
    name: str = "Server Alpha",
    tenant_id: str = "t-1",
    **kwargs,
) -> AssetRecord:
    """Helper to register a default asset."""
    return eng.register_asset(asset_id, name, tenant_id, **kwargs)


# ===================================================================
# 1. Constructor tests
# ===================================================================


class TestConstructor:
    """Validate engine construction invariants."""

    def test_valid_construction(self, spine: EventSpineEngine) -> None:
        eng = AssetRuntimeEngine(spine)
        assert eng is not None

    def test_invalid_type_none_raises(self) -> None:
        with pytest.raises(RuntimeCoreInvariantError):
            AssetRuntimeEngine(None)  # type: ignore[arg-type]

    def test_invalid_type_string_raises(self) -> None:
        with pytest.raises(RuntimeCoreInvariantError):
            AssetRuntimeEngine("not-a-spine")  # type: ignore[arg-type]

    def test_invalid_type_int_raises(self) -> None:
        with pytest.raises(RuntimeCoreInvariantError):
            AssetRuntimeEngine(42)  # type: ignore[arg-type]

    def test_invalid_type_dict_raises(self) -> None:
        with pytest.raises(RuntimeCoreInvariantError):
            AssetRuntimeEngine({})  # type: ignore[arg-type]

    def test_initial_asset_count_zero(self, engine: AssetRuntimeEngine) -> None:
        assert engine.asset_count == 0

    def test_initial_config_item_count_zero(self, engine: AssetRuntimeEngine) -> None:
        assert engine.config_item_count == 0

    def test_initial_inventory_count_zero(self, engine: AssetRuntimeEngine) -> None:
        assert engine.inventory_count == 0

    def test_initial_assignment_count_zero(self, engine: AssetRuntimeEngine) -> None:
        assert engine.assignment_count == 0

    def test_initial_dependency_count_zero(self, engine: AssetRuntimeEngine) -> None:
        assert engine.dependency_count == 0

    def test_initial_lifecycle_event_count_zero(self, engine: AssetRuntimeEngine) -> None:
        assert engine.lifecycle_event_count == 0

    def test_initial_assessment_count_zero(self, engine: AssetRuntimeEngine) -> None:
        assert engine.assessment_count == 0

    def test_initial_violation_count_zero(self, engine: AssetRuntimeEngine) -> None:
        assert engine.violation_count == 0


# ===================================================================
# 2. Asset registration and retrieval
# ===================================================================


class TestRegisterAsset:
    """Validate register_asset behaviour."""

    def test_returns_asset_record(self, engine: AssetRuntimeEngine) -> None:
        rec = _register_default_asset(engine)
        assert isinstance(rec, AssetRecord)

    def test_status_is_active(self, engine: AssetRuntimeEngine) -> None:
        rec = _register_default_asset(engine)
        assert rec.status == AssetStatus.ACTIVE

    def test_asset_id_preserved(self, engine: AssetRuntimeEngine) -> None:
        rec = _register_default_asset(engine, asset_id="a-42")
        assert rec.asset_id == "a-42"

    def test_name_preserved(self, engine: AssetRuntimeEngine) -> None:
        rec = _register_default_asset(engine, name="My Server")
        assert rec.name == "My Server"

    def test_tenant_id_preserved(self, engine: AssetRuntimeEngine) -> None:
        rec = _register_default_asset(engine, tenant_id="t-99")
        assert rec.tenant_id == "t-99"

    def test_default_kind_hardware(self, engine: AssetRuntimeEngine) -> None:
        rec = _register_default_asset(engine)
        assert rec.kind == AssetKind.HARDWARE

    def test_custom_kind_software(self, engine: AssetRuntimeEngine) -> None:
        rec = _register_default_asset(engine, kind=AssetKind.SOFTWARE)
        assert rec.kind == AssetKind.SOFTWARE

    def test_custom_kind_license(self, engine: AssetRuntimeEngine) -> None:
        rec = _register_default_asset(engine, kind=AssetKind.LICENSE)
        assert rec.kind == AssetKind.LICENSE

    def test_custom_kind_service(self, engine: AssetRuntimeEngine) -> None:
        rec = _register_default_asset(engine, kind=AssetKind.SERVICE)
        assert rec.kind == AssetKind.SERVICE

    def test_custom_kind_infrastructure(self, engine: AssetRuntimeEngine) -> None:
        rec = _register_default_asset(engine, kind=AssetKind.INFRASTRUCTURE)
        assert rec.kind == AssetKind.INFRASTRUCTURE

    def test_custom_kind_data(self, engine: AssetRuntimeEngine) -> None:
        rec = _register_default_asset(engine, kind=AssetKind.DATA)
        assert rec.kind == AssetKind.DATA

    def test_default_ownership_owned(self, engine: AssetRuntimeEngine) -> None:
        rec = _register_default_asset(engine)
        assert rec.ownership == OwnershipType.OWNED

    def test_custom_ownership_leased(self, engine: AssetRuntimeEngine) -> None:
        rec = _register_default_asset(engine, ownership=OwnershipType.LEASED)
        assert rec.ownership == OwnershipType.LEASED

    def test_custom_ownership_licensed(self, engine: AssetRuntimeEngine) -> None:
        rec = _register_default_asset(engine, ownership=OwnershipType.LICENSED)
        assert rec.ownership == OwnershipType.LICENSED

    def test_custom_ownership_shared(self, engine: AssetRuntimeEngine) -> None:
        rec = _register_default_asset(engine, ownership=OwnershipType.SHARED)
        assert rec.ownership == OwnershipType.SHARED

    def test_custom_ownership_vendor_managed(self, engine: AssetRuntimeEngine) -> None:
        rec = _register_default_asset(engine, ownership=OwnershipType.VENDOR_MANAGED)
        assert rec.ownership == OwnershipType.VENDOR_MANAGED

    def test_default_value_zero(self, engine: AssetRuntimeEngine) -> None:
        rec = _register_default_asset(engine)
        assert rec.value == 0.0

    def test_custom_value(self, engine: AssetRuntimeEngine) -> None:
        rec = _register_default_asset(engine, value=5000.0)
        assert rec.value == 5000.0

    def test_default_owner_ref_empty(self, engine: AssetRuntimeEngine) -> None:
        rec = _register_default_asset(engine)
        assert rec.owner_ref == ""

    def test_custom_owner_ref(self, engine: AssetRuntimeEngine) -> None:
        rec = _register_default_asset(engine, owner_ref="team-infra")
        assert rec.owner_ref == "team-infra"

    def test_default_vendor_ref_empty(self, engine: AssetRuntimeEngine) -> None:
        rec = _register_default_asset(engine)
        assert rec.vendor_ref == ""

    def test_custom_vendor_ref(self, engine: AssetRuntimeEngine) -> None:
        rec = _register_default_asset(engine, vendor_ref="vendor-xyz")
        assert rec.vendor_ref == "vendor-xyz"

    def test_registered_at_populated(self, engine: AssetRuntimeEngine) -> None:
        rec = _register_default_asset(engine)
        assert rec.registered_at != ""

    def test_asset_count_increments(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine, asset_id="a-1")
        assert engine.asset_count == 1
        _register_default_asset(engine, asset_id="a-2", name="Beta")
        assert engine.asset_count == 2

    def test_duplicate_asset_id_raises(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine, asset_id="a-dup")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate asset_id"):
            _register_default_asset(engine, asset_id="a-dup", name="Another")

    def test_multiple_assets_different_ids(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine, asset_id="a-1")
        _register_default_asset(engine, asset_id="a-2", name="Beta")
        _register_default_asset(engine, asset_id="a-3", name="Gamma")
        assert engine.asset_count == 3


class TestGetAsset:
    """Validate get_asset behaviour."""

    def test_get_registered_asset(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine, asset_id="a-1")
        rec = engine.get_asset("a-1")
        assert rec.asset_id == "a-1"

    def test_unknown_asset_raises(self, engine: AssetRuntimeEngine) -> None:
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown asset_id"):
            engine.get_asset("nonexistent")

    def test_get_returns_same_data(self, engine: AssetRuntimeEngine) -> None:
        original = _register_default_asset(engine, asset_id="a-1", name="Alpha", value=100.0)
        fetched = engine.get_asset("a-1")
        assert fetched.name == original.name
        assert fetched.value == original.value

    def test_get_after_multiple_registrations(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine, asset_id="a-1")
        _register_default_asset(engine, asset_id="a-2", name="Beta")
        assert engine.get_asset("a-1").asset_id == "a-1"
        assert engine.get_asset("a-2").asset_id == "a-2"


# ===================================================================
# 2b. Asset status transitions
# ===================================================================


class TestDeactivateAsset:
    """Validate deactivate_asset behaviour."""

    def test_active_to_inactive(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine)
        rec = engine.deactivate_asset("a-1")
        assert rec.status == AssetStatus.INACTIVE

    def test_deactivate_returns_asset_record(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine)
        rec = engine.deactivate_asset("a-1")
        assert isinstance(rec, AssetRecord)

    def test_deactivate_preserves_name(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine, name="MyServer")
        rec = engine.deactivate_asset("a-1")
        assert rec.name == "MyServer"

    def test_deactivate_preserves_value(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine, value=1000.0)
        rec = engine.deactivate_asset("a-1")
        assert rec.value == 1000.0

    def test_inactive_cannot_deactivate(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine)
        engine.deactivate_asset("a-1")
        with pytest.raises(RuntimeCoreInvariantError):
            engine.deactivate_asset("a-1")

    def test_maintenance_cannot_deactivate(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine)
        engine.maintain_asset("a-1")
        with pytest.raises(RuntimeCoreInvariantError):
            engine.deactivate_asset("a-1")

    def test_retired_cannot_deactivate(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine)
        engine.retire_asset("a-1")
        with pytest.raises(RuntimeCoreInvariantError):
            engine.deactivate_asset("a-1")

    def test_disposed_cannot_deactivate(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine)
        engine.dispose_asset("a-1")
        with pytest.raises(RuntimeCoreInvariantError):
            engine.deactivate_asset("a-1")

    def test_deactivate_unknown_raises(self, engine: AssetRuntimeEngine) -> None:
        with pytest.raises(RuntimeCoreInvariantError):
            engine.deactivate_asset("nonexistent")


class TestMaintainAsset:
    """Validate maintain_asset behaviour."""

    def test_active_to_maintenance(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine)
        rec = engine.maintain_asset("a-1")
        assert rec.status == AssetStatus.MAINTENANCE

    def test_inactive_to_maintenance(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine)
        engine.deactivate_asset("a-1")
        rec = engine.maintain_asset("a-1")
        assert rec.status == AssetStatus.MAINTENANCE

    def test_maintenance_to_maintenance(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine)
        engine.maintain_asset("a-1")
        rec = engine.maintain_asset("a-1")
        assert rec.status == AssetStatus.MAINTENANCE

    def test_retired_cannot_maintain(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine)
        engine.retire_asset("a-1")
        with pytest.raises(RuntimeCoreInvariantError, match="Cannot maintain"):
            engine.maintain_asset("a-1")

    def test_disposed_cannot_maintain(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine)
        engine.dispose_asset("a-1")
        with pytest.raises(RuntimeCoreInvariantError, match="Cannot maintain"):
            engine.maintain_asset("a-1")

    def test_maintain_unknown_raises(self, engine: AssetRuntimeEngine) -> None:
        with pytest.raises(RuntimeCoreInvariantError):
            engine.maintain_asset("nonexistent")

    def test_maintain_preserves_tenant(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine, tenant_id="t-99")
        rec = engine.maintain_asset("a-1")
        assert rec.tenant_id == "t-99"


class TestRetireAsset:
    """Validate retire_asset behaviour."""

    def test_active_to_retired(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine)
        rec = engine.retire_asset("a-1")
        assert rec.status == AssetStatus.RETIRED

    def test_inactive_to_retired(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine)
        engine.deactivate_asset("a-1")
        rec = engine.retire_asset("a-1")
        assert rec.status == AssetStatus.RETIRED

    def test_maintenance_to_retired(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine)
        engine.maintain_asset("a-1")
        rec = engine.retire_asset("a-1")
        assert rec.status == AssetStatus.RETIRED

    def test_retired_cannot_retire_again(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine)
        engine.retire_asset("a-1")
        with pytest.raises(RuntimeCoreInvariantError, match="already in status"):
            engine.retire_asset("a-1")

    def test_disposed_cannot_retire(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine)
        engine.dispose_asset("a-1")
        with pytest.raises(RuntimeCoreInvariantError, match="already in status"):
            engine.retire_asset("a-1")

    def test_retire_unknown_raises(self, engine: AssetRuntimeEngine) -> None:
        with pytest.raises(RuntimeCoreInvariantError):
            engine.retire_asset("nonexistent")

    def test_retire_preserves_kind(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine, kind=AssetKind.SOFTWARE)
        rec = engine.retire_asset("a-1")
        assert rec.kind == AssetKind.SOFTWARE


class TestDisposeAsset:
    """Validate dispose_asset behaviour."""

    def test_active_to_disposed(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine)
        rec = engine.dispose_asset("a-1")
        assert rec.status == AssetStatus.DISPOSED

    def test_inactive_to_disposed(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine)
        engine.deactivate_asset("a-1")
        rec = engine.dispose_asset("a-1")
        assert rec.status == AssetStatus.DISPOSED

    def test_maintenance_to_disposed(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine)
        engine.maintain_asset("a-1")
        rec = engine.dispose_asset("a-1")
        assert rec.status == AssetStatus.DISPOSED

    def test_retired_to_disposed(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine)
        engine.retire_asset("a-1")
        rec = engine.dispose_asset("a-1")
        assert rec.status == AssetStatus.DISPOSED

    def test_disposed_cannot_dispose_again(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine)
        engine.dispose_asset("a-1")
        with pytest.raises(RuntimeCoreInvariantError, match="already disposed"):
            engine.dispose_asset("a-1")

    def test_dispose_unknown_raises(self, engine: AssetRuntimeEngine) -> None:
        with pytest.raises(RuntimeCoreInvariantError):
            engine.dispose_asset("nonexistent")

    def test_dispose_preserves_ownership(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine, ownership=OwnershipType.LEASED)
        rec = engine.dispose_asset("a-1")
        assert rec.ownership == OwnershipType.LEASED


class TestAssetsForTenant:
    """Validate assets_for_tenant behaviour."""

    def test_empty_when_no_assets(self, engine: AssetRuntimeEngine) -> None:
        result = engine.assets_for_tenant("t-1")
        assert result == ()

    def test_returns_tuple(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine, tenant_id="t-1")
        result = engine.assets_for_tenant("t-1")
        assert isinstance(result, tuple)

    def test_filters_by_tenant(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine, asset_id="a-1", tenant_id="t-1")
        _register_default_asset(engine, asset_id="a-2", name="Beta", tenant_id="t-2")
        _register_default_asset(engine, asset_id="a-3", name="Gamma", tenant_id="t-1")
        result = engine.assets_for_tenant("t-1")
        assert len(result) == 2
        ids = {r.asset_id for r in result}
        assert ids == {"a-1", "a-3"}

    def test_unknown_tenant_returns_empty(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine, tenant_id="t-1")
        assert engine.assets_for_tenant("t-999") == ()

    def test_all_for_single_tenant(self, engine: AssetRuntimeEngine) -> None:
        for i in range(5):
            _register_default_asset(engine, asset_id=f"a-{i}", name=f"Asset {i}", tenant_id="t-1")
        assert len(engine.assets_for_tenant("t-1")) == 5


# ===================================================================
# 3. Configuration items
# ===================================================================


class TestRegisterConfigItem:
    """Validate register_config_item behaviour."""

    def test_returns_configuration_item(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine)
        ci = engine.register_config_item("ci-1", "a-1", "db-config")
        assert isinstance(ci, ConfigurationItem)

    def test_status_is_active(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine)
        ci = engine.register_config_item("ci-1", "a-1", "db-config")
        assert ci.status == ConfigurationItemStatus.ACTIVE

    def test_ci_id_preserved(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine)
        ci = engine.register_config_item("ci-42", "a-1", "db-config")
        assert ci.ci_id == "ci-42"

    def test_asset_id_preserved(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine)
        ci = engine.register_config_item("ci-1", "a-1", "db-config")
        assert ci.asset_id == "a-1"

    def test_name_preserved(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine)
        ci = engine.register_config_item("ci-1", "a-1", "my-config")
        assert ci.name == "my-config"

    def test_default_environment_ref_empty(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine)
        ci = engine.register_config_item("ci-1", "a-1", "db-config")
        assert ci.environment_ref == ""

    def test_custom_environment_ref(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine)
        ci = engine.register_config_item("ci-1", "a-1", "db-config", environment_ref="prod")
        assert ci.environment_ref == "prod"

    def test_default_workspace_ref_empty(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine)
        ci = engine.register_config_item("ci-1", "a-1", "db-config")
        assert ci.workspace_ref == ""

    def test_custom_workspace_ref(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine)
        ci = engine.register_config_item("ci-1", "a-1", "db-config", workspace_ref="ws-1")
        assert ci.workspace_ref == "ws-1"

    def test_default_version_empty(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine)
        ci = engine.register_config_item("ci-1", "a-1", "db-config")
        assert ci.version == ""

    def test_custom_version(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine)
        ci = engine.register_config_item("ci-1", "a-1", "db-config", version="2.0")
        assert ci.version == "2.0"

    def test_created_at_populated(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine)
        ci = engine.register_config_item("ci-1", "a-1", "db-config")
        assert ci.created_at != ""

    def test_config_item_count_increments(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine)
        engine.register_config_item("ci-1", "a-1", "db-config")
        assert engine.config_item_count == 1
        engine.register_config_item("ci-2", "a-1", "app-config")
        assert engine.config_item_count == 2

    def test_duplicate_ci_id_raises(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine)
        engine.register_config_item("ci-1", "a-1", "db-config")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate ci_id"):
            engine.register_config_item("ci-1", "a-1", "another")

    def test_unknown_asset_id_raises(self, engine: AssetRuntimeEngine) -> None:
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown asset_id"):
            engine.register_config_item("ci-1", "nonexistent", "db-config")


class TestGetConfigItem:
    """Validate get_config_item behaviour."""

    def test_get_registered_config_item(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine)
        engine.register_config_item("ci-1", "a-1", "db-config")
        ci = engine.get_config_item("ci-1")
        assert ci.ci_id == "ci-1"

    def test_unknown_ci_raises(self, engine: AssetRuntimeEngine) -> None:
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown ci_id"):
            engine.get_config_item("nonexistent")


class TestDeprecateConfigItem:
    """Validate deprecate_config_item behaviour."""

    def test_active_to_deprecated(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine)
        engine.register_config_item("ci-1", "a-1", "db-config")
        ci = engine.deprecate_config_item("ci-1")
        assert ci.status == ConfigurationItemStatus.DEPRECATED

    def test_pending_to_deprecated(self, engine: AssetRuntimeEngine) -> None:
        # Only DEPRECATED and ARCHIVED block deprecation; PENDING should succeed
        # but we can only create ACTIVE items via register, so we test ACTIVE
        _register_default_asset(engine)
        engine.register_config_item("ci-1", "a-1", "db-config")
        ci = engine.deprecate_config_item("ci-1")
        assert ci.status == ConfigurationItemStatus.DEPRECATED

    def test_deprecated_cannot_deprecate_again(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine)
        engine.register_config_item("ci-1", "a-1", "db-config")
        engine.deprecate_config_item("ci-1")
        with pytest.raises(RuntimeCoreInvariantError, match="already in status"):
            engine.deprecate_config_item("ci-1")

    def test_archived_cannot_deprecate(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine)
        engine.register_config_item("ci-1", "a-1", "db-config")
        engine.archive_config_item("ci-1")
        with pytest.raises(RuntimeCoreInvariantError, match="already in status"):
            engine.deprecate_config_item("ci-1")

    def test_deprecate_unknown_raises(self, engine: AssetRuntimeEngine) -> None:
        with pytest.raises(RuntimeCoreInvariantError):
            engine.deprecate_config_item("nonexistent")

    def test_deprecate_preserves_name(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine)
        engine.register_config_item("ci-1", "a-1", "my-config")
        ci = engine.deprecate_config_item("ci-1")
        assert ci.name == "my-config"

    def test_deprecate_preserves_version(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine)
        engine.register_config_item("ci-1", "a-1", "db-config", version="3.0")
        ci = engine.deprecate_config_item("ci-1")
        assert ci.version == "3.0"


class TestArchiveConfigItem:
    """Validate archive_config_item behaviour."""

    def test_active_to_archived(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine)
        engine.register_config_item("ci-1", "a-1", "db-config")
        ci = engine.archive_config_item("ci-1")
        assert ci.status == ConfigurationItemStatus.ARCHIVED

    def test_deprecated_to_archived(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine)
        engine.register_config_item("ci-1", "a-1", "db-config")
        engine.deprecate_config_item("ci-1")
        ci = engine.archive_config_item("ci-1")
        assert ci.status == ConfigurationItemStatus.ARCHIVED

    def test_archived_cannot_archive_again(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine)
        engine.register_config_item("ci-1", "a-1", "db-config")
        engine.archive_config_item("ci-1")
        with pytest.raises(RuntimeCoreInvariantError, match="already archived"):
            engine.archive_config_item("ci-1")

    def test_archive_unknown_raises(self, engine: AssetRuntimeEngine) -> None:
        with pytest.raises(RuntimeCoreInvariantError):
            engine.archive_config_item("nonexistent")

    def test_archive_preserves_asset_id(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine)
        engine.register_config_item("ci-1", "a-1", "db-config")
        ci = engine.archive_config_item("ci-1")
        assert ci.asset_id == "a-1"


class TestConfigItemsForAsset:
    """Validate config_items_for_asset behaviour."""

    def test_empty_when_none(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine)
        assert engine.config_items_for_asset("a-1") == ()

    def test_returns_tuple(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine)
        engine.register_config_item("ci-1", "a-1", "db-config")
        result = engine.config_items_for_asset("a-1")
        assert isinstance(result, tuple)

    def test_filters_by_asset(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine, asset_id="a-1")
        _register_default_asset(engine, asset_id="a-2", name="Beta")
        engine.register_config_item("ci-1", "a-1", "db-config")
        engine.register_config_item("ci-2", "a-2", "app-config")
        engine.register_config_item("ci-3", "a-1", "cache-config")
        result = engine.config_items_for_asset("a-1")
        assert len(result) == 2

    def test_unknown_asset_returns_empty(self, engine: AssetRuntimeEngine) -> None:
        assert engine.config_items_for_asset("nonexistent") == ()


# ===================================================================
# 4. Inventory
# ===================================================================


class TestRegisterInventory:
    """Validate register_inventory behaviour."""

    def test_returns_inventory_record(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine)
        inv = engine.register_inventory("inv-1", "a-1", "t-1", 100)
        assert isinstance(inv, InventoryRecord)

    def test_disposition_available(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine)
        inv = engine.register_inventory("inv-1", "a-1", "t-1", 100)
        assert inv.disposition == InventoryDisposition.AVAILABLE

    def test_available_quantity_equals_total(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine)
        inv = engine.register_inventory("inv-1", "a-1", "t-1", 50)
        assert inv.available_quantity == 50

    def test_assigned_quantity_zero(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine)
        inv = engine.register_inventory("inv-1", "a-1", "t-1", 50)
        assert inv.assigned_quantity == 0

    def test_total_quantity_preserved(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine)
        inv = engine.register_inventory("inv-1", "a-1", "t-1", 200)
        assert inv.total_quantity == 200

    def test_inventory_id_preserved(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine)
        inv = engine.register_inventory("inv-42", "a-1", "t-1", 10)
        assert inv.inventory_id == "inv-42"

    def test_asset_id_preserved(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine)
        inv = engine.register_inventory("inv-1", "a-1", "t-1", 10)
        assert inv.asset_id == "a-1"

    def test_tenant_id_preserved(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine)
        inv = engine.register_inventory("inv-1", "a-1", "t-99", 10)
        assert inv.tenant_id == "t-99"

    def test_updated_at_populated(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine)
        inv = engine.register_inventory("inv-1", "a-1", "t-1", 10)
        assert inv.updated_at != ""

    def test_inventory_count_increments(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine)
        engine.register_inventory("inv-1", "a-1", "t-1", 10)
        assert engine.inventory_count == 1
        engine.register_inventory("inv-2", "a-1", "t-1", 20)
        assert engine.inventory_count == 2

    def test_duplicate_inventory_id_raises(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine)
        engine.register_inventory("inv-1", "a-1", "t-1", 10)
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate inventory_id"):
            engine.register_inventory("inv-1", "a-1", "t-1", 20)

    def test_unknown_asset_id_raises(self, engine: AssetRuntimeEngine) -> None:
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown asset_id"):
            engine.register_inventory("inv-1", "nonexistent", "t-1", 10)


class TestGetInventory:
    """Validate get_inventory behaviour."""

    def test_get_registered_inventory(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine)
        engine.register_inventory("inv-1", "a-1", "t-1", 100)
        inv = engine.get_inventory("inv-1")
        assert inv.inventory_id == "inv-1"

    def test_unknown_inventory_raises(self, engine: AssetRuntimeEngine) -> None:
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown inventory_id"):
            engine.get_inventory("nonexistent")


class TestAssignInventory:
    """Validate assign_inventory behaviour."""

    def test_partial_assign(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine)
        engine.register_inventory("inv-1", "a-1", "t-1", 100)
        inv = engine.assign_inventory("inv-1", 30)
        assert inv.assigned_quantity == 30
        assert inv.available_quantity == 70

    def test_disposition_assigned(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine)
        engine.register_inventory("inv-1", "a-1", "t-1", 100)
        inv = engine.assign_inventory("inv-1", 30)
        assert inv.disposition == InventoryDisposition.ASSIGNED

    def test_full_assign_depleted(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine)
        engine.register_inventory("inv-1", "a-1", "t-1", 100)
        inv = engine.assign_inventory("inv-1", 100)
        assert inv.disposition == InventoryDisposition.DEPLETED
        assert inv.available_quantity == 0
        assert inv.assigned_quantity == 100

    def test_over_assign_capped(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine)
        engine.register_inventory("inv-1", "a-1", "t-1", 50)
        inv = engine.assign_inventory("inv-1", 999)
        assert inv.assigned_quantity == 50
        assert inv.available_quantity == 0
        assert inv.disposition == InventoryDisposition.DEPLETED

    def test_depleted_cannot_assign(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine)
        engine.register_inventory("inv-1", "a-1", "t-1", 10)
        engine.assign_inventory("inv-1", 10)
        with pytest.raises(RuntimeCoreInvariantError, match="depleted"):
            engine.assign_inventory("inv-1", 1)

    def test_assign_zero_raises(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine)
        engine.register_inventory("inv-1", "a-1", "t-1", 10)
        with pytest.raises(RuntimeCoreInvariantError, match="No available"):
            engine.assign_inventory("inv-1", 0)

    def test_sequential_assigns(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine)
        engine.register_inventory("inv-1", "a-1", "t-1", 100)
        engine.assign_inventory("inv-1", 20)
        inv = engine.assign_inventory("inv-1", 30)
        assert inv.assigned_quantity == 50
        assert inv.available_quantity == 50

    def test_assign_unknown_raises(self, engine: AssetRuntimeEngine) -> None:
        with pytest.raises(RuntimeCoreInvariantError):
            engine.assign_inventory("nonexistent", 10)

    def test_total_quantity_unchanged_after_assign(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine)
        engine.register_inventory("inv-1", "a-1", "t-1", 100)
        inv = engine.assign_inventory("inv-1", 30)
        assert inv.total_quantity == 100


class TestReleaseInventory:
    """Validate release_inventory behaviour."""

    def test_partial_release(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine)
        engine.register_inventory("inv-1", "a-1", "t-1", 100)
        engine.assign_inventory("inv-1", 50)
        inv = engine.release_inventory("inv-1", 20)
        assert inv.assigned_quantity == 30
        assert inv.available_quantity == 70

    def test_full_release_available(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine)
        engine.register_inventory("inv-1", "a-1", "t-1", 100)
        engine.assign_inventory("inv-1", 50)
        inv = engine.release_inventory("inv-1", 50)
        assert inv.disposition == InventoryDisposition.AVAILABLE
        assert inv.assigned_quantity == 0
        assert inv.available_quantity == 100

    def test_partial_release_stays_assigned(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine)
        engine.register_inventory("inv-1", "a-1", "t-1", 100)
        engine.assign_inventory("inv-1", 50)
        inv = engine.release_inventory("inv-1", 10)
        assert inv.disposition == InventoryDisposition.ASSIGNED

    def test_over_release_capped(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine)
        engine.register_inventory("inv-1", "a-1", "t-1", 100)
        engine.assign_inventory("inv-1", 30)
        inv = engine.release_inventory("inv-1", 999)
        assert inv.assigned_quantity == 0
        assert inv.available_quantity == 100

    def test_release_with_no_assigned_raises(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine)
        engine.register_inventory("inv-1", "a-1", "t-1", 100)
        with pytest.raises(RuntimeCoreInvariantError, match="No assigned"):
            engine.release_inventory("inv-1", 10)

    def test_release_zero_raises(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine)
        engine.register_inventory("inv-1", "a-1", "t-1", 100)
        with pytest.raises(RuntimeCoreInvariantError, match="No assigned"):
            engine.release_inventory("inv-1", 0)

    def test_release_unknown_raises(self, engine: AssetRuntimeEngine) -> None:
        with pytest.raises(RuntimeCoreInvariantError):
            engine.release_inventory("nonexistent", 10)

    def test_total_quantity_unchanged_after_release(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine)
        engine.register_inventory("inv-1", "a-1", "t-1", 100)
        engine.assign_inventory("inv-1", 40)
        inv = engine.release_inventory("inv-1", 20)
        assert inv.total_quantity == 100

    def test_release_from_depleted_succeeds(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine)
        engine.register_inventory("inv-1", "a-1", "t-1", 10)
        engine.assign_inventory("inv-1", 10)
        inv = engine.release_inventory("inv-1", 5)
        assert inv.disposition == InventoryDisposition.ASSIGNED
        assert inv.available_quantity == 5


class TestInventoryForAsset:
    """Validate inventory_for_asset behaviour."""

    def test_empty_when_none(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine)
        assert engine.inventory_for_asset("a-1") == ()

    def test_returns_tuple(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine)
        engine.register_inventory("inv-1", "a-1", "t-1", 10)
        result = engine.inventory_for_asset("a-1")
        assert isinstance(result, tuple)

    def test_filters_by_asset(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine, asset_id="a-1")
        _register_default_asset(engine, asset_id="a-2", name="Beta")
        engine.register_inventory("inv-1", "a-1", "t-1", 10)
        engine.register_inventory("inv-2", "a-2", "t-1", 20)
        engine.register_inventory("inv-3", "a-1", "t-1", 30)
        result = engine.inventory_for_asset("a-1")
        assert len(result) == 2

    def test_unknown_asset_returns_empty(self, engine: AssetRuntimeEngine) -> None:
        assert engine.inventory_for_asset("nonexistent") == ()


# ===================================================================
# 5. Assignments
# ===================================================================


class TestAssignAsset:
    """Validate assign_asset behaviour."""

    def test_returns_asset_assignment(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine)
        aa = engine.assign_asset("asgn-1", "a-1", "campaign-1", "campaign")
        assert isinstance(aa, AssetAssignment)

    def test_assignment_id_preserved(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine)
        aa = engine.assign_asset("asgn-42", "a-1", "campaign-1", "campaign")
        assert aa.assignment_id == "asgn-42"

    def test_asset_id_preserved(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine)
        aa = engine.assign_asset("asgn-1", "a-1", "campaign-1", "campaign")
        assert aa.asset_id == "a-1"

    def test_scope_ref_id_preserved(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine)
        aa = engine.assign_asset("asgn-1", "a-1", "campaign-1", "campaign")
        assert aa.scope_ref_id == "campaign-1"

    def test_scope_ref_type_preserved(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine)
        aa = engine.assign_asset("asgn-1", "a-1", "campaign-1", "campaign")
        assert aa.scope_ref_type == "campaign"

    def test_default_assigned_by(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine)
        aa = engine.assign_asset("asgn-1", "a-1", "campaign-1", "campaign")
        assert aa.assigned_by == "system"

    def test_custom_assigned_by(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine)
        aa = engine.assign_asset("asgn-1", "a-1", "campaign-1", "campaign", assigned_by="admin")
        assert aa.assigned_by == "admin"

    def test_assigned_at_populated(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine)
        aa = engine.assign_asset("asgn-1", "a-1", "campaign-1", "campaign")
        assert aa.assigned_at != ""

    def test_assignment_count_increments(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine)
        engine.assign_asset("asgn-1", "a-1", "campaign-1", "campaign")
        assert engine.assignment_count == 1
        engine.assign_asset("asgn-2", "a-1", "campaign-2", "campaign")
        assert engine.assignment_count == 2

    def test_duplicate_assignment_id_raises(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine)
        engine.assign_asset("asgn-1", "a-1", "campaign-1", "campaign")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate assignment_id"):
            engine.assign_asset("asgn-1", "a-1", "campaign-2", "campaign")

    def test_unknown_asset_raises(self, engine: AssetRuntimeEngine) -> None:
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown asset_id"):
            engine.assign_asset("asgn-1", "nonexistent", "campaign-1", "campaign")

    def test_retired_asset_cannot_be_assigned(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine)
        engine.retire_asset("a-1")
        with pytest.raises(RuntimeCoreInvariantError, match="Cannot assign"):
            engine.assign_asset("asgn-1", "a-1", "campaign-1", "campaign")

    def test_disposed_asset_cannot_be_assigned(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine)
        engine.dispose_asset("a-1")
        with pytest.raises(RuntimeCoreInvariantError, match="Cannot assign"):
            engine.assign_asset("asgn-1", "a-1", "campaign-1", "campaign")

    def test_inactive_asset_can_be_assigned(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine)
        engine.deactivate_asset("a-1")
        aa = engine.assign_asset("asgn-1", "a-1", "campaign-1", "campaign")
        assert aa.asset_id == "a-1"

    def test_maintenance_asset_can_be_assigned(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine)
        engine.maintain_asset("a-1")
        aa = engine.assign_asset("asgn-1", "a-1", "campaign-1", "campaign")
        assert aa.asset_id == "a-1"


class TestAssignmentsForAsset:
    """Validate assignments_for_asset behaviour."""

    def test_empty_when_none(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine)
        assert engine.assignments_for_asset("a-1") == ()

    def test_returns_tuple(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine)
        engine.assign_asset("asgn-1", "a-1", "campaign-1", "campaign")
        result = engine.assignments_for_asset("a-1")
        assert isinstance(result, tuple)

    def test_filters_by_asset(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine, asset_id="a-1")
        _register_default_asset(engine, asset_id="a-2", name="Beta")
        engine.assign_asset("asgn-1", "a-1", "campaign-1", "campaign")
        engine.assign_asset("asgn-2", "a-2", "campaign-2", "campaign")
        engine.assign_asset("asgn-3", "a-1", "campaign-3", "campaign")
        result = engine.assignments_for_asset("a-1")
        assert len(result) == 2

    def test_unknown_asset_returns_empty(self, engine: AssetRuntimeEngine) -> None:
        assert engine.assignments_for_asset("nonexistent") == ()

    def test_multiple_assignments_same_asset(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine)
        for i in range(5):
            engine.assign_asset(f"asgn-{i}", "a-1", f"scope-{i}", "campaign")
        assert len(engine.assignments_for_asset("a-1")) == 5


# ===================================================================
# 6. Dependencies
# ===================================================================


class TestRegisterDependency:
    """Validate register_dependency behaviour."""

    def test_returns_asset_dependency(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine, asset_id="a-1")
        _register_default_asset(engine, asset_id="a-2", name="Beta")
        dep = engine.register_dependency("dep-1", "a-1", "a-2")
        assert isinstance(dep, AssetDependency)

    def test_dependency_id_preserved(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine, asset_id="a-1")
        _register_default_asset(engine, asset_id="a-2", name="Beta")
        dep = engine.register_dependency("dep-42", "a-1", "a-2")
        assert dep.dependency_id == "dep-42"

    def test_asset_id_preserved(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine, asset_id="a-1")
        _register_default_asset(engine, asset_id="a-2", name="Beta")
        dep = engine.register_dependency("dep-1", "a-1", "a-2")
        assert dep.asset_id == "a-1"

    def test_depends_on_preserved(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine, asset_id="a-1")
        _register_default_asset(engine, asset_id="a-2", name="Beta")
        dep = engine.register_dependency("dep-1", "a-1", "a-2")
        assert dep.depends_on_asset_id == "a-2"

    def test_default_description_empty(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine, asset_id="a-1")
        _register_default_asset(engine, asset_id="a-2", name="Beta")
        dep = engine.register_dependency("dep-1", "a-1", "a-2")
        assert dep.description == ""

    def test_custom_description(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine, asset_id="a-1")
        _register_default_asset(engine, asset_id="a-2", name="Beta")
        dep = engine.register_dependency("dep-1", "a-1", "a-2", description="needs DB")
        assert dep.description == "needs DB"

    def test_created_at_populated(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine, asset_id="a-1")
        _register_default_asset(engine, asset_id="a-2", name="Beta")
        dep = engine.register_dependency("dep-1", "a-1", "a-2")
        assert dep.created_at != ""

    def test_dependency_count_increments(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine, asset_id="a-1")
        _register_default_asset(engine, asset_id="a-2", name="Beta")
        _register_default_asset(engine, asset_id="a-3", name="Gamma")
        engine.register_dependency("dep-1", "a-1", "a-2")
        assert engine.dependency_count == 1
        engine.register_dependency("dep-2", "a-1", "a-3")
        assert engine.dependency_count == 2

    def test_duplicate_dependency_id_raises(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine, asset_id="a-1")
        _register_default_asset(engine, asset_id="a-2", name="Beta")
        engine.register_dependency("dep-1", "a-1", "a-2")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate dependency_id"):
            engine.register_dependency("dep-1", "a-1", "a-2")

    def test_unknown_asset_id_raises(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine, asset_id="a-2", name="Beta")
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown asset_id"):
            engine.register_dependency("dep-1", "nonexistent", "a-2")

    def test_unknown_depends_on_asset_id_raises(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine, asset_id="a-1")
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown depends_on_asset_id"):
            engine.register_dependency("dep-1", "a-1", "nonexistent")

    def test_both_unknown_asset_id_raises(self, engine: AssetRuntimeEngine) -> None:
        with pytest.raises(RuntimeCoreInvariantError):
            engine.register_dependency("dep-1", "nonexistent-a", "nonexistent-b")


class TestDependenciesForAsset:
    """Validate dependencies_for_asset behaviour."""

    def test_empty_when_none(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine)
        assert engine.dependencies_for_asset("a-1") == ()

    def test_returns_tuple(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine, asset_id="a-1")
        _register_default_asset(engine, asset_id="a-2", name="Beta")
        engine.register_dependency("dep-1", "a-1", "a-2")
        result = engine.dependencies_for_asset("a-1")
        assert isinstance(result, tuple)

    def test_filters_by_asset(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine, asset_id="a-1")
        _register_default_asset(engine, asset_id="a-2", name="Beta")
        _register_default_asset(engine, asset_id="a-3", name="Gamma")
        engine.register_dependency("dep-1", "a-1", "a-2")
        engine.register_dependency("dep-2", "a-2", "a-3")
        engine.register_dependency("dep-3", "a-1", "a-3")
        result = engine.dependencies_for_asset("a-1")
        assert len(result) == 2

    def test_unknown_asset_returns_empty(self, engine: AssetRuntimeEngine) -> None:
        assert engine.dependencies_for_asset("nonexistent") == ()


# ===================================================================
# 7. Lifecycle events
# ===================================================================


class TestRecordLifecycleEvent:
    """Validate record_lifecycle_event behaviour."""

    def test_returns_lifecycle_event(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine)
        le = engine.record_lifecycle_event("le-1", "a-1", LifecycleDisposition.PROVISIONED)
        assert isinstance(le, LifecycleEvent)

    def test_event_id_preserved(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine)
        le = engine.record_lifecycle_event("le-42", "a-1", LifecycleDisposition.PROVISIONED)
        assert le.event_id == "le-42"

    def test_asset_id_preserved(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine)
        le = engine.record_lifecycle_event("le-1", "a-1", LifecycleDisposition.PROVISIONED)
        assert le.asset_id == "a-1"

    def test_disposition_provisioned(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine)
        le = engine.record_lifecycle_event("le-1", "a-1", LifecycleDisposition.PROVISIONED)
        assert le.disposition == LifecycleDisposition.PROVISIONED

    def test_disposition_deployed(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine)
        le = engine.record_lifecycle_event("le-1", "a-1", LifecycleDisposition.DEPLOYED)
        assert le.disposition == LifecycleDisposition.DEPLOYED

    def test_disposition_upgraded(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine)
        le = engine.record_lifecycle_event("le-1", "a-1", LifecycleDisposition.UPGRADED)
        assert le.disposition == LifecycleDisposition.UPGRADED

    def test_disposition_decommissioned(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine)
        le = engine.record_lifecycle_event("le-1", "a-1", LifecycleDisposition.DECOMMISSIONED)
        assert le.disposition == LifecycleDisposition.DECOMMISSIONED

    def test_disposition_transferred(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine)
        le = engine.record_lifecycle_event("le-1", "a-1", LifecycleDisposition.TRANSFERRED)
        assert le.disposition == LifecycleDisposition.TRANSFERRED

    def test_disposition_renewed(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine)
        le = engine.record_lifecycle_event("le-1", "a-1", LifecycleDisposition.RENEWED)
        assert le.disposition == LifecycleDisposition.RENEWED

    def test_default_description_empty(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine)
        le = engine.record_lifecycle_event("le-1", "a-1", LifecycleDisposition.PROVISIONED)
        assert le.description == ""

    def test_custom_description(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine)
        le = engine.record_lifecycle_event(
            "le-1", "a-1", LifecycleDisposition.PROVISIONED, description="Initial provisioning"
        )
        assert le.description == "Initial provisioning"

    def test_default_performed_by(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine)
        le = engine.record_lifecycle_event("le-1", "a-1", LifecycleDisposition.PROVISIONED)
        assert le.performed_by == "system"

    def test_custom_performed_by(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine)
        le = engine.record_lifecycle_event(
            "le-1", "a-1", LifecycleDisposition.PROVISIONED, performed_by="admin"
        )
        assert le.performed_by == "admin"

    def test_performed_at_populated(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine)
        le = engine.record_lifecycle_event("le-1", "a-1", LifecycleDisposition.PROVISIONED)
        assert le.performed_at != ""

    def test_lifecycle_event_count_increments(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine)
        engine.record_lifecycle_event("le-1", "a-1", LifecycleDisposition.PROVISIONED)
        assert engine.lifecycle_event_count == 1
        engine.record_lifecycle_event("le-2", "a-1", LifecycleDisposition.DEPLOYED)
        assert engine.lifecycle_event_count == 2

    def test_duplicate_event_id_raises(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine)
        engine.record_lifecycle_event("le-1", "a-1", LifecycleDisposition.PROVISIONED)
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate event_id"):
            engine.record_lifecycle_event("le-1", "a-1", LifecycleDisposition.DEPLOYED)

    def test_unknown_asset_raises(self, engine: AssetRuntimeEngine) -> None:
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown asset_id"):
            engine.record_lifecycle_event("le-1", "nonexistent", LifecycleDisposition.PROVISIONED)


class TestLifecycleEventsForAsset:
    """Validate lifecycle_events_for_asset behaviour."""

    def test_empty_when_none(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine)
        assert engine.lifecycle_events_for_asset("a-1") == ()

    def test_returns_tuple(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine)
        engine.record_lifecycle_event("le-1", "a-1", LifecycleDisposition.PROVISIONED)
        result = engine.lifecycle_events_for_asset("a-1")
        assert isinstance(result, tuple)

    def test_filters_by_asset(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine, asset_id="a-1")
        _register_default_asset(engine, asset_id="a-2", name="Beta")
        engine.record_lifecycle_event("le-1", "a-1", LifecycleDisposition.PROVISIONED)
        engine.record_lifecycle_event("le-2", "a-2", LifecycleDisposition.DEPLOYED)
        engine.record_lifecycle_event("le-3", "a-1", LifecycleDisposition.UPGRADED)
        result = engine.lifecycle_events_for_asset("a-1")
        assert len(result) == 2

    def test_unknown_asset_returns_empty(self, engine: AssetRuntimeEngine) -> None:
        assert engine.lifecycle_events_for_asset("nonexistent") == ()


# ===================================================================
# 8. Assessments
# ===================================================================


class TestAssessAsset:
    """Validate assess_asset behaviour."""

    def test_returns_asset_assessment(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine)
        aa = engine.assess_asset("assess-1", "a-1", 0.9, 0.1)
        assert isinstance(aa, AssetAssessment)

    def test_assessment_id_preserved(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine)
        aa = engine.assess_asset("assess-42", "a-1", 0.9, 0.1)
        assert aa.assessment_id == "assess-42"

    def test_asset_id_preserved(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine)
        aa = engine.assess_asset("assess-1", "a-1", 0.9, 0.1)
        assert aa.asset_id == "a-1"

    def test_health_score_preserved(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine)
        aa = engine.assess_asset("assess-1", "a-1", 0.85, 0.1)
        assert aa.health_score == 0.85

    def test_risk_score_preserved(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine)
        aa = engine.assess_asset("assess-1", "a-1", 0.9, 0.42)
        assert aa.risk_score == 0.42

    def test_default_assessed_by(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine)
        aa = engine.assess_asset("assess-1", "a-1", 0.9, 0.1)
        assert aa.assessed_by == "system"

    def test_custom_assessed_by(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine)
        aa = engine.assess_asset("assess-1", "a-1", 0.9, 0.1, assessed_by="auditor")
        assert aa.assessed_by == "auditor"

    def test_assessed_at_populated(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine)
        aa = engine.assess_asset("assess-1", "a-1", 0.9, 0.1)
        assert aa.assessed_at != ""

    def test_assessment_count_increments(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine)
        engine.assess_asset("assess-1", "a-1", 0.9, 0.1)
        assert engine.assessment_count == 1
        engine.assess_asset("assess-2", "a-1", 0.8, 0.2)
        assert engine.assessment_count == 2

    def test_duplicate_assessment_id_raises(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine)
        engine.assess_asset("assess-1", "a-1", 0.9, 0.1)
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate assessment_id"):
            engine.assess_asset("assess-1", "a-1", 0.8, 0.2)

    def test_unknown_asset_raises(self, engine: AssetRuntimeEngine) -> None:
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown asset_id"):
            engine.assess_asset("assess-1", "nonexistent", 0.9, 0.1)

    def test_health_score_zero(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine)
        aa = engine.assess_asset("assess-1", "a-1", 0.0, 0.5)
        assert aa.health_score == 0.0

    def test_health_score_one(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine)
        aa = engine.assess_asset("assess-1", "a-1", 1.0, 0.5)
        assert aa.health_score == 1.0

    def test_risk_score_zero(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine)
        aa = engine.assess_asset("assess-1", "a-1", 0.5, 0.0)
        assert aa.risk_score == 0.0

    def test_risk_score_one(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine)
        aa = engine.assess_asset("assess-1", "a-1", 0.5, 1.0)
        assert aa.risk_score == 1.0


class TestAssessmentsForAsset:
    """Validate assessments_for_asset behaviour."""

    def test_empty_when_none(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine)
        assert engine.assessments_for_asset("a-1") == ()

    def test_returns_tuple(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine)
        engine.assess_asset("assess-1", "a-1", 0.9, 0.1)
        result = engine.assessments_for_asset("a-1")
        assert isinstance(result, tuple)

    def test_filters_by_asset(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine, asset_id="a-1")
        _register_default_asset(engine, asset_id="a-2", name="Beta")
        engine.assess_asset("assess-1", "a-1", 0.9, 0.1)
        engine.assess_asset("assess-2", "a-2", 0.8, 0.2)
        engine.assess_asset("assess-3", "a-1", 0.7, 0.3)
        result = engine.assessments_for_asset("a-1")
        assert len(result) == 2

    def test_unknown_asset_returns_empty(self, engine: AssetRuntimeEngine) -> None:
        assert engine.assessments_for_asset("nonexistent") == ()


# ===================================================================
# 9. Violation detection
# ===================================================================


class TestDetectAssetViolations:
    """Validate detect_asset_violations behaviour."""

    def test_no_violations_empty_engine(self, engine: AssetRuntimeEngine) -> None:
        result = engine.detect_asset_violations()
        assert result == ()

    def test_no_violations_active_asset(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine)
        engine.assign_asset("asgn-1", "a-1", "campaign-1", "campaign")
        result = engine.detect_asset_violations()
        assert result == ()

    def test_retired_with_assignments_violation(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine)
        engine.assign_asset("asgn-1", "a-1", "campaign-1", "campaign")
        engine.retire_asset("a-1")
        result = engine.detect_asset_violations()
        assert len(result) == 1
        assert result[0].operation == "retired_with_assignments"

    def test_disposed_with_assignments_violation(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine)
        engine.assign_asset("asgn-1", "a-1", "campaign-1", "campaign")
        engine.dispose_asset("a-1")
        result = engine.detect_asset_violations()
        assert len(result) == 1
        assert result[0].operation == "retired_with_assignments"

    def test_depends_on_retired_violation(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine, asset_id="a-1")
        _register_default_asset(engine, asset_id="a-2", name="Beta")
        engine.register_dependency("dep-1", "a-1", "a-2")
        engine.retire_asset("a-2")
        result = engine.detect_asset_violations()
        assert len(result) == 1
        assert result[0].operation == "depends_on_retired"

    def test_depends_on_disposed_violation(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine, asset_id="a-1")
        _register_default_asset(engine, asset_id="a-2", name="Beta")
        engine.register_dependency("dep-1", "a-1", "a-2")
        engine.dispose_asset("a-2")
        result = engine.detect_asset_violations()
        assert len(result) == 1
        assert result[0].operation == "depends_on_retired"

    def test_depleted_inventory_violation(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine)
        engine.register_inventory("inv-1", "a-1", "t-1", 10)
        engine.assign_inventory("inv-1", 10)
        result = engine.detect_asset_violations()
        assert len(result) == 1
        assert result[0].operation == "depleted_inventory"

    def test_multiple_violations_at_once(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine, asset_id="a-1")
        _register_default_asset(engine, asset_id="a-2", name="Beta")
        engine.assign_asset("asgn-1", "a-1", "campaign-1", "campaign")
        engine.register_dependency("dep-1", "a-2", "a-1")
        engine.retire_asset("a-1")
        engine.register_inventory("inv-1", "a-2", "t-1", 5)
        engine.assign_inventory("inv-1", 5)
        result = engine.detect_asset_violations()
        ops = {v.operation for v in result}
        assert "retired_with_assignments" in ops
        assert "depends_on_retired" in ops
        assert "depleted_inventory" in ops

    def test_idempotent_second_scan_empty(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine)
        engine.assign_asset("asgn-1", "a-1", "campaign-1", "campaign")
        engine.retire_asset("a-1")
        first = engine.detect_asset_violations()
        assert len(first) >= 1
        second = engine.detect_asset_violations()
        assert second == ()

    def test_violation_has_asset_id(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine)
        engine.assign_asset("asgn-1", "a-1", "campaign-1", "campaign")
        engine.retire_asset("a-1")
        result = engine.detect_asset_violations()
        assert result[0].asset_id == "a-1"

    def test_violation_has_tenant_id(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine, tenant_id="t-99")
        engine.assign_asset("asgn-1", "a-1", "campaign-1", "campaign")
        engine.retire_asset("a-1")
        result = engine.detect_asset_violations()
        assert result[0].tenant_id == "t-99"

    def test_violation_has_reason(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine)
        engine.assign_asset("asgn-1", "a-1", "campaign-1", "campaign")
        engine.retire_asset("a-1")
        result = engine.detect_asset_violations()
        assert result[0].reason != ""

    def test_violation_has_detected_at(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine)
        engine.assign_asset("asgn-1", "a-1", "campaign-1", "campaign")
        engine.retire_asset("a-1")
        result = engine.detect_asset_violations()
        assert result[0].detected_at != ""

    def test_violation_is_asset_violation_type(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine)
        engine.assign_asset("asgn-1", "a-1", "campaign-1", "campaign")
        engine.retire_asset("a-1")
        result = engine.detect_asset_violations()
        assert isinstance(result[0], AssetViolation)

    def test_no_violation_for_dependency_on_active(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine, asset_id="a-1")
        _register_default_asset(engine, asset_id="a-2", name="Beta")
        engine.register_dependency("dep-1", "a-1", "a-2")
        result = engine.detect_asset_violations()
        assert result == ()

    def test_no_violation_for_available_inventory(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine)
        engine.register_inventory("inv-1", "a-1", "t-1", 100)
        result = engine.detect_asset_violations()
        assert result == ()

    def test_no_violation_for_assigned_non_depleted(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine)
        engine.register_inventory("inv-1", "a-1", "t-1", 100)
        engine.assign_inventory("inv-1", 50)
        result = engine.detect_asset_violations()
        assert result == ()

    def test_violation_count_property_updated(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine)
        engine.assign_asset("asgn-1", "a-1", "campaign-1", "campaign")
        engine.retire_asset("a-1")
        assert engine.violation_count == 0
        engine.detect_asset_violations()
        assert engine.violation_count >= 1


class TestViolationsForAsset:
    """Validate violations_for_asset behaviour."""

    def test_empty_when_none(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine)
        assert engine.violations_for_asset("a-1") == ()

    def test_returns_tuple(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine)
        engine.assign_asset("asgn-1", "a-1", "campaign-1", "campaign")
        engine.retire_asset("a-1")
        engine.detect_asset_violations()
        result = engine.violations_for_asset("a-1")
        assert isinstance(result, tuple)

    def test_filters_by_asset(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine, asset_id="a-1")
        _register_default_asset(engine, asset_id="a-2", name="Beta")
        engine.assign_asset("asgn-1", "a-1", "campaign-1", "campaign")
        engine.assign_asset("asgn-2", "a-2", "campaign-2", "campaign")
        engine.retire_asset("a-1")
        engine.retire_asset("a-2")
        engine.detect_asset_violations()
        result_a1 = engine.violations_for_asset("a-1")
        result_a2 = engine.violations_for_asset("a-2")
        assert len(result_a1) >= 1
        assert len(result_a2) >= 1
        assert all(v.asset_id == "a-1" for v in result_a1)
        assert all(v.asset_id == "a-2" for v in result_a2)

    def test_unknown_asset_returns_empty(self, engine: AssetRuntimeEngine) -> None:
        assert engine.violations_for_asset("nonexistent") == ()


# ===================================================================
# 10. Snapshot
# ===================================================================


class TestAssetSnapshot:
    """Validate asset_snapshot behaviour."""

    def test_returns_asset_snapshot(self, engine: AssetRuntimeEngine) -> None:
        snap = engine.asset_snapshot("snap-1")
        assert isinstance(snap, AssetSnapshot)

    def test_snapshot_id_preserved(self, engine: AssetRuntimeEngine) -> None:
        snap = engine.asset_snapshot("snap-42")
        assert snap.snapshot_id == "snap-42"

    def test_duplicate_snapshot_id_raises(self, engine: AssetRuntimeEngine) -> None:
        engine.asset_snapshot("snap-1")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate snapshot_id"):
            engine.asset_snapshot("snap-1")

    def test_empty_engine_snapshot(self, engine: AssetRuntimeEngine) -> None:
        snap = engine.asset_snapshot("snap-1")
        assert snap.total_assets == 0
        assert snap.total_active == 0
        assert snap.total_retired == 0
        assert snap.total_config_items == 0
        assert snap.total_inventory == 0
        assert snap.total_assignments == 0
        assert snap.total_dependencies == 0
        assert snap.total_violations == 0
        assert snap.total_asset_value == 0.0

    def test_total_assets_matches(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine, asset_id="a-1")
        _register_default_asset(engine, asset_id="a-2", name="Beta")
        snap = engine.asset_snapshot("snap-1")
        assert snap.total_assets == 2

    def test_total_active_matches(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine, asset_id="a-1")
        _register_default_asset(engine, asset_id="a-2", name="Beta")
        engine.retire_asset("a-2")
        snap = engine.asset_snapshot("snap-1")
        assert snap.total_active == 1

    def test_total_retired_includes_retired_and_disposed(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine, asset_id="a-1")
        _register_default_asset(engine, asset_id="a-2", name="Beta")
        _register_default_asset(engine, asset_id="a-3", name="Gamma")
        engine.retire_asset("a-1")
        engine.dispose_asset("a-2")
        snap = engine.asset_snapshot("snap-1")
        assert snap.total_retired == 2

    def test_total_config_items_matches(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine)
        engine.register_config_item("ci-1", "a-1", "cfg-a")
        engine.register_config_item("ci-2", "a-1", "cfg-b")
        snap = engine.asset_snapshot("snap-1")
        assert snap.total_config_items == 2

    def test_total_inventory_matches(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine)
        engine.register_inventory("inv-1", "a-1", "t-1", 10)
        snap = engine.asset_snapshot("snap-1")
        assert snap.total_inventory == 1

    def test_total_assignments_matches(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine)
        engine.assign_asset("asgn-1", "a-1", "scope-1", "campaign")
        snap = engine.asset_snapshot("snap-1")
        assert snap.total_assignments == 1

    def test_total_dependencies_matches(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine, asset_id="a-1")
        _register_default_asset(engine, asset_id="a-2", name="Beta")
        engine.register_dependency("dep-1", "a-1", "a-2")
        snap = engine.asset_snapshot("snap-1")
        assert snap.total_dependencies == 1

    def test_total_violations_matches(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine)
        engine.assign_asset("asgn-1", "a-1", "scope-1", "campaign")
        engine.retire_asset("a-1")
        engine.detect_asset_violations()
        snap = engine.asset_snapshot("snap-1")
        assert snap.total_violations >= 1

    def test_total_asset_value_excludes_terminal(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine, asset_id="a-1", value=1000.0)
        _register_default_asset(engine, asset_id="a-2", name="Beta", value=2000.0)
        _register_default_asset(engine, asset_id="a-3", name="Gamma", value=500.0)
        engine.retire_asset("a-2")
        snap = engine.asset_snapshot("snap-1")
        assert snap.total_asset_value == 1500.0

    def test_captured_at_populated(self, engine: AssetRuntimeEngine) -> None:
        snap = engine.asset_snapshot("snap-1")
        assert snap.captured_at != ""

    def test_multiple_snapshots_different_ids(self, engine: AssetRuntimeEngine) -> None:
        snap1 = engine.asset_snapshot("snap-1")
        _register_default_asset(engine)
        snap2 = engine.asset_snapshot("snap-2")
        assert snap1.total_assets == 0
        assert snap2.total_assets == 1


# ===================================================================
# 11. State hash
# ===================================================================


class TestStateHash:
    """Validate state_hash behaviour."""

    def test_returns_string(self, engine: AssetRuntimeEngine) -> None:
        h = engine.state_hash()
        assert isinstance(h, str)

    def test_is_method_not_property(self, engine: AssetRuntimeEngine) -> None:
        assert callable(engine.state_hash)

    def test_deterministic(self, engine: AssetRuntimeEngine) -> None:
        h1 = engine.state_hash()
        h2 = engine.state_hash()
        assert h1 == h2

    def test_changes_after_asset_registration(self, engine: AssetRuntimeEngine) -> None:
        h1 = engine.state_hash()
        _register_default_asset(engine)
        h2 = engine.state_hash()
        assert h1 != h2

    def test_changes_after_config_item(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine)
        h1 = engine.state_hash()
        engine.register_config_item("ci-1", "a-1", "db-config")
        h2 = engine.state_hash()
        assert h1 != h2

    def test_changes_after_inventory(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine)
        h1 = engine.state_hash()
        engine.register_inventory("inv-1", "a-1", "t-1", 10)
        h2 = engine.state_hash()
        assert h1 != h2

    def test_changes_after_assignment(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine)
        h1 = engine.state_hash()
        engine.assign_asset("asgn-1", "a-1", "scope-1", "campaign")
        h2 = engine.state_hash()
        assert h1 != h2

    def test_changes_after_dependency(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine, asset_id="a-1")
        _register_default_asset(engine, asset_id="a-2", name="Beta")
        h1 = engine.state_hash()
        engine.register_dependency("dep-1", "a-1", "a-2")
        h2 = engine.state_hash()
        assert h1 != h2

    def test_changes_after_lifecycle_event(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine)
        h1 = engine.state_hash()
        engine.record_lifecycle_event("le-1", "a-1", LifecycleDisposition.PROVISIONED)
        h2 = engine.state_hash()
        assert h1 != h2

    def test_changes_after_assessment(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine)
        h1 = engine.state_hash()
        engine.assess_asset("assess-1", "a-1", 0.9, 0.1)
        h2 = engine.state_hash()
        assert h1 != h2

    def test_changes_after_violation_detection(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine)
        engine.assign_asset("asgn-1", "a-1", "scope-1", "campaign")
        engine.retire_asset("a-1")
        h1 = engine.state_hash()
        engine.detect_asset_violations()
        h2 = engine.state_hash()
        assert h1 != h2

    def test_hash_length(self, engine: AssetRuntimeEngine) -> None:
        h = engine.state_hash()
        assert len(h) == 64

    def test_hash_is_hex(self, engine: AssetRuntimeEngine) -> None:
        h = engine.state_hash()
        int(h, 16)  # Should not raise


# ===================================================================
# 12. Event emission
# ===================================================================


class TestEventEmission:
    """Validate event_spine.event_count increases after mutations."""

    def test_event_after_register_asset(self, engine: AssetRuntimeEngine, spine: EventSpineEngine) -> None:
        before = spine.event_count
        _register_default_asset(engine)
        assert spine.event_count > before

    def test_event_after_deactivate(self, engine: AssetRuntimeEngine, spine: EventSpineEngine) -> None:
        _register_default_asset(engine)
        before = spine.event_count
        engine.deactivate_asset("a-1")
        assert spine.event_count > before

    def test_event_after_maintain(self, engine: AssetRuntimeEngine, spine: EventSpineEngine) -> None:
        _register_default_asset(engine)
        before = spine.event_count
        engine.maintain_asset("a-1")
        assert spine.event_count > before

    def test_event_after_retire(self, engine: AssetRuntimeEngine, spine: EventSpineEngine) -> None:
        _register_default_asset(engine)
        before = spine.event_count
        engine.retire_asset("a-1")
        assert spine.event_count > before

    def test_event_after_dispose(self, engine: AssetRuntimeEngine, spine: EventSpineEngine) -> None:
        _register_default_asset(engine)
        before = spine.event_count
        engine.dispose_asset("a-1")
        assert spine.event_count > before

    def test_event_after_register_config_item(self, engine: AssetRuntimeEngine, spine: EventSpineEngine) -> None:
        _register_default_asset(engine)
        before = spine.event_count
        engine.register_config_item("ci-1", "a-1", "db-config")
        assert spine.event_count > before

    def test_event_after_deprecate_config(self, engine: AssetRuntimeEngine, spine: EventSpineEngine) -> None:
        _register_default_asset(engine)
        engine.register_config_item("ci-1", "a-1", "db-config")
        before = spine.event_count
        engine.deprecate_config_item("ci-1")
        assert spine.event_count > before

    def test_event_after_archive_config(self, engine: AssetRuntimeEngine, spine: EventSpineEngine) -> None:
        _register_default_asset(engine)
        engine.register_config_item("ci-1", "a-1", "db-config")
        before = spine.event_count
        engine.archive_config_item("ci-1")
        assert spine.event_count > before

    def test_event_after_register_inventory(self, engine: AssetRuntimeEngine, spine: EventSpineEngine) -> None:
        _register_default_asset(engine)
        before = spine.event_count
        engine.register_inventory("inv-1", "a-1", "t-1", 10)
        assert spine.event_count > before

    def test_event_after_assign_inventory(self, engine: AssetRuntimeEngine, spine: EventSpineEngine) -> None:
        _register_default_asset(engine)
        engine.register_inventory("inv-1", "a-1", "t-1", 100)
        before = spine.event_count
        engine.assign_inventory("inv-1", 10)
        assert spine.event_count > before

    def test_event_after_release_inventory(self, engine: AssetRuntimeEngine, spine: EventSpineEngine) -> None:
        _register_default_asset(engine)
        engine.register_inventory("inv-1", "a-1", "t-1", 100)
        engine.assign_inventory("inv-1", 50)
        before = spine.event_count
        engine.release_inventory("inv-1", 10)
        assert spine.event_count > before

    def test_event_after_assign_asset(self, engine: AssetRuntimeEngine, spine: EventSpineEngine) -> None:
        _register_default_asset(engine)
        before = spine.event_count
        engine.assign_asset("asgn-1", "a-1", "scope-1", "campaign")
        assert spine.event_count > before

    def test_event_after_register_dependency(self, engine: AssetRuntimeEngine, spine: EventSpineEngine) -> None:
        _register_default_asset(engine, asset_id="a-1")
        _register_default_asset(engine, asset_id="a-2", name="Beta")
        before = spine.event_count
        engine.register_dependency("dep-1", "a-1", "a-2")
        assert spine.event_count > before

    def test_event_after_lifecycle(self, engine: AssetRuntimeEngine, spine: EventSpineEngine) -> None:
        _register_default_asset(engine)
        before = spine.event_count
        engine.record_lifecycle_event("le-1", "a-1", LifecycleDisposition.PROVISIONED)
        assert spine.event_count > before

    def test_event_after_assess(self, engine: AssetRuntimeEngine, spine: EventSpineEngine) -> None:
        _register_default_asset(engine)
        before = spine.event_count
        engine.assess_asset("assess-1", "a-1", 0.9, 0.1)
        assert spine.event_count > before

    def test_event_after_violation_detection(self, engine: AssetRuntimeEngine, spine: EventSpineEngine) -> None:
        _register_default_asset(engine)
        engine.assign_asset("asgn-1", "a-1", "scope-1", "campaign")
        engine.retire_asset("a-1")
        before = spine.event_count
        engine.detect_asset_violations()
        assert spine.event_count > before

    def test_event_after_snapshot(self, engine: AssetRuntimeEngine, spine: EventSpineEngine) -> None:
        before = spine.event_count
        engine.asset_snapshot("snap-1")
        assert spine.event_count > before


# ===================================================================
# 13. Properties
# ===================================================================


class TestProperties:
    """Validate all count properties."""

    def test_asset_count_is_property(self, engine: AssetRuntimeEngine) -> None:
        assert isinstance(type(engine).asset_count, property)

    def test_config_item_count_is_property(self, engine: AssetRuntimeEngine) -> None:
        assert isinstance(type(engine).config_item_count, property)

    def test_inventory_count_is_property(self, engine: AssetRuntimeEngine) -> None:
        assert isinstance(type(engine).inventory_count, property)

    def test_assignment_count_is_property(self, engine: AssetRuntimeEngine) -> None:
        assert isinstance(type(engine).assignment_count, property)

    def test_dependency_count_is_property(self, engine: AssetRuntimeEngine) -> None:
        assert isinstance(type(engine).dependency_count, property)

    def test_lifecycle_event_count_is_property(self, engine: AssetRuntimeEngine) -> None:
        assert isinstance(type(engine).lifecycle_event_count, property)

    def test_assessment_count_is_property(self, engine: AssetRuntimeEngine) -> None:
        assert isinstance(type(engine).assessment_count, property)

    def test_violation_count_is_property(self, engine: AssetRuntimeEngine) -> None:
        assert isinstance(type(engine).violation_count, property)

    def test_asset_count_after_multiple(self, engine: AssetRuntimeEngine) -> None:
        for i in range(10):
            _register_default_asset(engine, asset_id=f"a-{i}", name=f"Asset {i}")
        assert engine.asset_count == 10

    def test_config_count_after_multiple(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine)
        for i in range(5):
            engine.register_config_item(f"ci-{i}", "a-1", f"cfg-{i}")
        assert engine.config_item_count == 5

    def test_inventory_count_after_multiple(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine)
        for i in range(3):
            engine.register_inventory(f"inv-{i}", "a-1", "t-1", 10 * (i + 1))
        assert engine.inventory_count == 3

    def test_assignment_count_after_multiple(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine)
        for i in range(4):
            engine.assign_asset(f"asgn-{i}", "a-1", f"scope-{i}", "campaign")
        assert engine.assignment_count == 4

    def test_dependency_count_after_multiple(self, engine: AssetRuntimeEngine) -> None:
        for i in range(4):
            _register_default_asset(engine, asset_id=f"a-{i}", name=f"Asset {i}")
        engine.register_dependency("dep-1", "a-0", "a-1")
        engine.register_dependency("dep-2", "a-0", "a-2")
        engine.register_dependency("dep-3", "a-0", "a-3")
        assert engine.dependency_count == 3

    def test_lifecycle_count_after_multiple(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine)
        engine.record_lifecycle_event("le-1", "a-1", LifecycleDisposition.PROVISIONED)
        engine.record_lifecycle_event("le-2", "a-1", LifecycleDisposition.DEPLOYED)
        assert engine.lifecycle_event_count == 2

    def test_assessment_count_after_multiple(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine)
        engine.assess_asset("assess-1", "a-1", 0.9, 0.1)
        engine.assess_asset("assess-2", "a-1", 0.8, 0.2)
        engine.assess_asset("assess-3", "a-1", 0.7, 0.3)
        assert engine.assessment_count == 3


# ===================================================================
# 14. Golden scenarios
# ===================================================================


class TestGoldenScenarios:
    """End-to-end golden scenarios exercising full engine workflows."""

    def test_gs1_register_config_inventory_snapshot(
        self, engine: AssetRuntimeEngine, spine: EventSpineEngine,
    ) -> None:
        """GS-1: Register asset, config item, inventory, assign inventory, snapshot."""
        asset = engine.register_asset("a-1", "Server Alpha", "t-1", value=5000.0)
        assert asset.status == AssetStatus.ACTIVE

        ci = engine.register_config_item("ci-1", "a-1", "db-config", version="1.0")
        assert ci.status == ConfigurationItemStatus.ACTIVE

        inv = engine.register_inventory("inv-1", "a-1", "t-1", 100)
        assert inv.disposition == InventoryDisposition.AVAILABLE

        inv = engine.assign_inventory("inv-1", 40)
        assert inv.assigned_quantity == 40
        assert inv.available_quantity == 60

        snap = engine.asset_snapshot("snap-1")
        assert snap.total_assets == 1
        assert snap.total_active == 1
        assert snap.total_config_items == 1
        assert snap.total_inventory == 1
        assert snap.total_asset_value == 5000.0
        assert snap.total_retired == 0
        assert snap.total_violations == 0

        assert engine.asset_count == 1
        assert engine.config_item_count == 1
        assert engine.inventory_count == 1
        assert spine.event_count > 0

    def test_gs2_dependency_on_retired_violation(
        self, engine: AssetRuntimeEngine,
    ) -> None:
        """GS-2: Register two assets, dependency, retire depended-on, detect violation."""
        engine.register_asset("a-app", "App Server", "t-1")
        engine.register_asset("a-db", "Database", "t-1")
        engine.register_dependency("dep-1", "a-app", "a-db", description="App needs DB")

        engine.retire_asset("a-db")

        violations = engine.detect_asset_violations()
        assert len(violations) >= 1
        dep_violations = [v for v in violations if v.operation == "depends_on_retired"]
        assert len(dep_violations) == 1
        assert dep_violations[0].asset_id == "a-app"
        assert "a-db" in dep_violations[0].reason

    def test_gs3_retired_with_assignments_violation(
        self, engine: AssetRuntimeEngine,
    ) -> None:
        """GS-3: Register asset, assign to campaign, retire, detect violation."""
        engine.register_asset("a-1", "Campaign Server", "t-1")
        engine.assign_asset("asgn-1", "a-1", "campaign-x", "campaign")
        engine.retire_asset("a-1")

        violations = engine.detect_asset_violations()
        assign_violations = [v for v in violations if v.operation == "retired_with_assignments"]
        assert len(assign_violations) == 1
        assert assign_violations[0].asset_id == "a-1"
        assert "1 active assignments" in assign_violations[0].reason

    def test_gs4_depleted_inventory_violation_then_release(
        self, engine: AssetRuntimeEngine,
    ) -> None:
        """GS-4: Register, deplete inventory, detect violation, release, re-detect idempotent."""
        engine.register_asset("a-1", "License Pool", "t-1")
        engine.register_inventory("inv-1", "a-1", "t-1", 10)
        engine.assign_inventory("inv-1", 10)

        violations = engine.detect_asset_violations()
        dep_violations = [v for v in violations if v.operation == "depleted_inventory"]
        assert len(dep_violations) == 1

        engine.release_inventory("inv-1", 5)

        # Second scan: same violation already recorded, no new ones
        second_violations = engine.detect_asset_violations()
        assert second_violations == ()

    def test_gs5_full_lifecycle_maintain_then_retire_blocks_assign(
        self, engine: AssetRuntimeEngine,
    ) -> None:
        """GS-5: Full lifecycle: register, maintain, try deactivate from maintenance
        (should raise since only ACTIVE can deactivate), retire, attempt assign blocked.
        """
        engine.register_asset("a-1", "Lifecycle Asset", "t-1")

        engine.maintain_asset("a-1")
        assert engine.get_asset("a-1").status == AssetStatus.MAINTENANCE

        # Deactivate from MAINTENANCE should raise (only ACTIVE -> INACTIVE)
        with pytest.raises(RuntimeCoreInvariantError):
            engine.deactivate_asset("a-1")

        engine.retire_asset("a-1")
        assert engine.get_asset("a-1").status == AssetStatus.RETIRED

        with pytest.raises(RuntimeCoreInvariantError, match="Cannot assign"):
            engine.assign_asset("asgn-1", "a-1", "scope-1", "campaign")

    def test_gs6_multi_tenant_isolation(self, engine: AssetRuntimeEngine) -> None:
        """GS-6: Multi-tenant isolation. Each tenant sees only its own assets."""
        engine.register_asset("a-t1-1", "Alpha", "tenant-a")
        engine.register_asset("a-t1-2", "Beta", "tenant-a")
        engine.register_asset("a-t2-1", "Gamma", "tenant-b")
        engine.register_asset("a-t2-2", "Delta", "tenant-b")
        engine.register_asset("a-t2-3", "Epsilon", "tenant-b")

        tenant_a = engine.assets_for_tenant("tenant-a")
        tenant_b = engine.assets_for_tenant("tenant-b")
        tenant_c = engine.assets_for_tenant("tenant-c")

        assert len(tenant_a) == 2
        assert len(tenant_b) == 3
        assert len(tenant_c) == 0

        assert all(a.tenant_id == "tenant-a" for a in tenant_a)
        assert all(a.tenant_id == "tenant-b" for a in tenant_b)

        ids_a = {a.asset_id for a in tenant_a}
        ids_b = {a.asset_id for a in tenant_b}
        assert ids_a == {"a-t1-1", "a-t1-2"}
        assert ids_b == {"a-t2-1", "a-t2-2", "a-t2-3"}


# ===================================================================
# 15. Additional edge cases and immutability
# ===================================================================


class TestImmutability:
    """Validate that returned records are frozen / immutable."""

    def test_asset_record_frozen(self, engine: AssetRuntimeEngine) -> None:
        rec = _register_default_asset(engine)
        with pytest.raises(AttributeError):
            rec.name = "mutated"  # type: ignore[misc]

    def test_config_item_frozen(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine)
        ci = engine.register_config_item("ci-1", "a-1", "db-config")
        with pytest.raises(AttributeError):
            ci.name = "mutated"  # type: ignore[misc]

    def test_inventory_record_frozen(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine)
        inv = engine.register_inventory("inv-1", "a-1", "t-1", 100)
        with pytest.raises(AttributeError):
            inv.total_quantity = 999  # type: ignore[misc]

    def test_assignment_frozen(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine)
        aa = engine.assign_asset("asgn-1", "a-1", "scope-1", "campaign")
        with pytest.raises(AttributeError):
            aa.scope_ref_id = "mutated"  # type: ignore[misc]

    def test_dependency_frozen(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine, asset_id="a-1")
        _register_default_asset(engine, asset_id="a-2", name="Beta")
        dep = engine.register_dependency("dep-1", "a-1", "a-2")
        with pytest.raises(AttributeError):
            dep.description = "mutated"  # type: ignore[misc]

    def test_lifecycle_event_frozen(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine)
        le = engine.record_lifecycle_event("le-1", "a-1", LifecycleDisposition.PROVISIONED)
        with pytest.raises(AttributeError):
            le.description = "mutated"  # type: ignore[misc]

    def test_assessment_frozen(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine)
        aa = engine.assess_asset("assess-1", "a-1", 0.9, 0.1)
        with pytest.raises(AttributeError):
            aa.health_score = 0.0  # type: ignore[misc]

    def test_snapshot_frozen(self, engine: AssetRuntimeEngine) -> None:
        snap = engine.asset_snapshot("snap-1")
        with pytest.raises(AttributeError):
            snap.total_assets = 999  # type: ignore[misc]

    def test_violation_frozen(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine)
        engine.assign_asset("asgn-1", "a-1", "scope-1", "campaign")
        engine.retire_asset("a-1")
        violations = engine.detect_asset_violations()
        with pytest.raises(AttributeError):
            violations[0].reason = "mutated"  # type: ignore[misc]

    def test_assets_for_tenant_returns_tuple(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine)
        result = engine.assets_for_tenant("t-1")
        assert isinstance(result, tuple)

    def test_config_items_for_asset_returns_tuple(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine)
        engine.register_config_item("ci-1", "a-1", "cfg")
        result = engine.config_items_for_asset("a-1")
        assert isinstance(result, tuple)

    def test_inventory_for_asset_returns_tuple(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine)
        engine.register_inventory("inv-1", "a-1", "t-1", 10)
        result = engine.inventory_for_asset("a-1")
        assert isinstance(result, tuple)

    def test_assignments_for_asset_returns_tuple(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine)
        engine.assign_asset("asgn-1", "a-1", "scope-1", "campaign")
        result = engine.assignments_for_asset("a-1")
        assert isinstance(result, tuple)

    def test_dependencies_for_asset_returns_tuple(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine, asset_id="a-1")
        _register_default_asset(engine, asset_id="a-2", name="Beta")
        engine.register_dependency("dep-1", "a-1", "a-2")
        result = engine.dependencies_for_asset("a-1")
        assert isinstance(result, tuple)

    def test_lifecycle_events_for_asset_returns_tuple(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine)
        engine.record_lifecycle_event("le-1", "a-1", LifecycleDisposition.PROVISIONED)
        result = engine.lifecycle_events_for_asset("a-1")
        assert isinstance(result, tuple)

    def test_assessments_for_asset_returns_tuple(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine)
        engine.assess_asset("assess-1", "a-1", 0.9, 0.1)
        result = engine.assessments_for_asset("a-1")
        assert isinstance(result, tuple)

    def test_violations_for_asset_returns_tuple(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine)
        engine.assign_asset("asgn-1", "a-1", "scope-1", "campaign")
        engine.retire_asset("a-1")
        engine.detect_asset_violations()
        result = engine.violations_for_asset("a-1")
        assert isinstance(result, tuple)

    def test_detect_violations_returns_tuple(self, engine: AssetRuntimeEngine) -> None:
        result = engine.detect_asset_violations()
        assert isinstance(result, tuple)


class TestEdgeCases:
    """Additional edge-case coverage."""

    def test_register_asset_all_kwargs(self, engine: AssetRuntimeEngine) -> None:
        rec = engine.register_asset(
            "a-full", "Full Asset", "t-1",
            kind=AssetKind.DATA,
            ownership=OwnershipType.VENDOR_MANAGED,
            owner_ref="team-data",
            vendor_ref="vendor-abc",
            value=99999.0,
        )
        assert rec.kind == AssetKind.DATA
        assert rec.ownership == OwnershipType.VENDOR_MANAGED
        assert rec.owner_ref == "team-data"
        assert rec.vendor_ref == "vendor-abc"
        assert rec.value == 99999.0

    def test_dispose_from_all_non_disposed_states(self, engine: AssetRuntimeEngine) -> None:
        """Ensure dispose works from ACTIVE, INACTIVE, MAINTENANCE, RETIRED."""
        for i, transition in enumerate([
            lambda e: None,                         # ACTIVE
            lambda e: e.deactivate_asset(f"a-{i}"), # INACTIVE
            lambda e: e.maintain_asset(f"a-{i}"),   # MAINTENANCE
            lambda e: e.retire_asset(f"a-{i}"),     # RETIRED
        ]):
            aid = f"a-{i}"
            _register_default_asset(engine, asset_id=aid, name=f"Asset {i}")
            transition(engine)
            rec = engine.dispose_asset(aid)
            assert rec.status == AssetStatus.DISPOSED

    def test_assign_inventory_exactly_available(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine)
        engine.register_inventory("inv-1", "a-1", "t-1", 5)
        inv = engine.assign_inventory("inv-1", 5)
        assert inv.disposition == InventoryDisposition.DEPLETED
        assert inv.available_quantity == 0
        assert inv.assigned_quantity == 5

    def test_release_inventory_exactly_assigned(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine)
        engine.register_inventory("inv-1", "a-1", "t-1", 10)
        engine.assign_inventory("inv-1", 7)
        inv = engine.release_inventory("inv-1", 7)
        assert inv.disposition == InventoryDisposition.AVAILABLE
        assert inv.assigned_quantity == 0
        assert inv.available_quantity == 10

    def test_many_config_items_for_single_asset(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine)
        for i in range(20):
            engine.register_config_item(f"ci-{i}", "a-1", f"config-{i}")
        assert len(engine.config_items_for_asset("a-1")) == 20

    def test_many_lifecycle_events_for_single_asset(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine)
        dispositions = list(LifecycleDisposition)
        for i, disp in enumerate(dispositions):
            engine.record_lifecycle_event(f"le-{i}", "a-1", disp)
        assert len(engine.lifecycle_events_for_asset("a-1")) == len(dispositions)

    def test_many_assessments_for_single_asset(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine)
        for i in range(10):
            engine.assess_asset(f"assess-{i}", "a-1", i / 10, (10 - i) / 10)
        assert len(engine.assessments_for_asset("a-1")) == 10

    def test_snapshot_after_retirement_value_excluded(self, engine: AssetRuntimeEngine) -> None:
        engine.register_asset("a-1", "Alpha", "t-1", value=100.0)
        engine.register_asset("a-2", "Beta", "t-1", value=200.0)
        engine.retire_asset("a-1")
        snap = engine.asset_snapshot("snap-1")
        assert snap.total_asset_value == 200.0

    def test_snapshot_after_disposal_value_excluded(self, engine: AssetRuntimeEngine) -> None:
        engine.register_asset("a-1", "Alpha", "t-1", value=300.0)
        engine.register_asset("a-2", "Beta", "t-1", value=400.0)
        engine.dispose_asset("a-1")
        snap = engine.asset_snapshot("snap-1")
        assert snap.total_asset_value == 400.0

    def test_state_hash_same_for_identical_engines(self, spine: EventSpineEngine) -> None:
        e1 = AssetRuntimeEngine(EventSpineEngine())
        e2 = AssetRuntimeEngine(EventSpineEngine())
        assert e1.state_hash() == e2.state_hash()

    def test_multiple_violations_types_all_detected(self, engine: AssetRuntimeEngine) -> None:
        engine.register_asset("a-1", "Server", "t-1")
        engine.register_asset("a-2", "DB", "t-1")
        engine.assign_asset("asgn-1", "a-1", "scope-1", "campaign")
        engine.register_dependency("dep-1", "a-2", "a-1")
        engine.register_inventory("inv-1", "a-2", "t-1", 1)
        engine.assign_inventory("inv-1", 1)
        engine.retire_asset("a-1")

        violations = engine.detect_asset_violations()
        ops = {v.operation for v in violations}
        assert "retired_with_assignments" in ops
        assert "depends_on_retired" in ops
        assert "depleted_inventory" in ops

    def test_assign_asset_to_different_scope_types(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine)
        engine.assign_asset("asgn-1", "a-1", "campaign-1", "campaign")
        engine.assign_asset("asgn-2", "a-1", "program-1", "program")
        engine.assign_asset("asgn-3", "a-1", "env-1", "environment")
        assignments = engine.assignments_for_asset("a-1")
        types = {a.scope_ref_type for a in assignments}
        assert types == {"campaign", "program", "environment"}

    def test_dependency_self_reference(self, engine: AssetRuntimeEngine) -> None:
        """Self-dependency: both asset_id and depends_on_asset_id are the same."""
        _register_default_asset(engine)
        dep = engine.register_dependency("dep-self", "a-1", "a-1")
        assert dep.asset_id == "a-1"
        assert dep.depends_on_asset_id == "a-1"

    def test_violation_scan_no_event_when_no_violations(
        self, engine: AssetRuntimeEngine, spine: EventSpineEngine,
    ) -> None:
        _register_default_asset(engine)
        before = spine.event_count
        engine.detect_asset_violations()
        # No violations means no event emitted
        assert spine.event_count == before

    def test_get_asset_reflects_latest_status(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine)
        assert engine.get_asset("a-1").status == AssetStatus.ACTIVE
        engine.deactivate_asset("a-1")
        assert engine.get_asset("a-1").status == AssetStatus.INACTIVE
        engine.maintain_asset("a-1")
        assert engine.get_asset("a-1").status == AssetStatus.MAINTENANCE
        engine.retire_asset("a-1")
        assert engine.get_asset("a-1").status == AssetStatus.RETIRED

    def test_config_item_get_reflects_latest_status(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine)
        engine.register_config_item("ci-1", "a-1", "cfg")
        assert engine.get_config_item("ci-1").status == ConfigurationItemStatus.ACTIVE
        engine.deprecate_config_item("ci-1")
        assert engine.get_config_item("ci-1").status == ConfigurationItemStatus.DEPRECATED
        engine.archive_config_item("ci-1")
        assert engine.get_config_item("ci-1").status == ConfigurationItemStatus.ARCHIVED

    def test_inventory_get_reflects_latest_state(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine)
        engine.register_inventory("inv-1", "a-1", "t-1", 10)
        assert engine.get_inventory("inv-1").disposition == InventoryDisposition.AVAILABLE
        engine.assign_inventory("inv-1", 5)
        assert engine.get_inventory("inv-1").disposition == InventoryDisposition.ASSIGNED
        engine.assign_inventory("inv-1", 5)
        assert engine.get_inventory("inv-1").disposition == InventoryDisposition.DEPLETED

    def test_retired_asset_multiple_assignments_violation_count(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine)
        engine.assign_asset("asgn-1", "a-1", "scope-1", "campaign")
        engine.assign_asset("asgn-2", "a-1", "scope-2", "campaign")
        engine.assign_asset("asgn-3", "a-1", "scope-3", "campaign")
        engine.retire_asset("a-1")
        violations = engine.detect_asset_violations()
        v = [x for x in violations if x.operation == "retired_with_assignments"]
        assert len(v) == 1
        assert "3 active assignments" in v[0].reason

    def test_two_engines_independent(self, spine: EventSpineEngine) -> None:
        s1 = EventSpineEngine()
        s2 = EventSpineEngine()
        e1 = AssetRuntimeEngine(s1)
        e2 = AssetRuntimeEngine(s2)
        _register_default_asset(e1, asset_id="a-1")
        assert e1.asset_count == 1
        assert e2.asset_count == 0

    def test_snapshot_counts_all_terminal_as_retired(self, engine: AssetRuntimeEngine) -> None:
        engine.register_asset("a-1", "Alpha", "t-1")
        engine.register_asset("a-2", "Beta", "t-1")
        engine.register_asset("a-3", "Gamma", "t-1")
        engine.register_asset("a-4", "Delta", "t-1")
        engine.retire_asset("a-1")
        engine.dispose_asset("a-2")
        snap = engine.asset_snapshot("snap-1")
        assert snap.total_retired == 2
        assert snap.total_active == 2

    def test_maintain_from_inactive(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine)
        engine.deactivate_asset("a-1")
        rec = engine.maintain_asset("a-1")
        assert rec.status == AssetStatus.MAINTENANCE

    def test_dispose_preserves_value(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine, value=7777.0)
        rec = engine.dispose_asset("a-1")
        assert rec.value == 7777.0

    def test_retire_preserves_value(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine, value=3333.0)
        rec = engine.retire_asset("a-1")
        assert rec.value == 3333.0

    def test_asset_snapshot_value_zero_when_all_terminal(self, engine: AssetRuntimeEngine) -> None:
        engine.register_asset("a-1", "Alpha", "t-1", value=100.0)
        engine.register_asset("a-2", "Beta", "t-1", value=200.0)
        engine.retire_asset("a-1")
        engine.dispose_asset("a-2")
        snap = engine.asset_snapshot("snap-1")
        assert snap.total_asset_value == 0.0

    def test_multiple_dependencies_different_targets(self, engine: AssetRuntimeEngine) -> None:
        for i in range(5):
            _register_default_asset(engine, asset_id=f"a-{i}", name=f"Asset {i}")
        engine.register_dependency("dep-01", "a-0", "a-1")
        engine.register_dependency("dep-02", "a-0", "a-2")
        engine.register_dependency("dep-03", "a-0", "a-3")
        engine.register_dependency("dep-04", "a-0", "a-4")
        deps = engine.dependencies_for_asset("a-0")
        assert len(deps) == 4
        targets = {d.depends_on_asset_id for d in deps}
        assert targets == {"a-1", "a-2", "a-3", "a-4"}

    def test_multiple_depends_on_retired_violations(self, engine: AssetRuntimeEngine) -> None:
        engine.register_asset("a-1", "Alpha", "t-1")
        engine.register_asset("a-2", "Beta", "t-1")
        engine.register_asset("a-target", "Target", "t-1")
        engine.register_dependency("dep-1", "a-1", "a-target")
        engine.register_dependency("dep-2", "a-2", "a-target")
        engine.retire_asset("a-target")
        violations = engine.detect_asset_violations()
        dep_v = [v for v in violations if v.operation == "depends_on_retired"]
        assert len(dep_v) == 2
        v_assets = {v.asset_id for v in dep_v}
        assert v_assets == {"a-1", "a-2"}

    def test_register_config_item_with_all_kwargs(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine)
        ci = engine.register_config_item(
            "ci-full", "a-1", "full-config",
            environment_ref="staging",
            workspace_ref="ws-dev",
            version="4.2.1",
        )
        assert ci.environment_ref == "staging"
        assert ci.workspace_ref == "ws-dev"
        assert ci.version == "4.2.1"

    def test_lifecycle_event_all_dispositions_same_asset(self, engine: AssetRuntimeEngine) -> None:
        _register_default_asset(engine)
        for i, disp in enumerate(LifecycleDisposition):
            engine.record_lifecycle_event(f"le-{i}", "a-1", disp)
        events = engine.lifecycle_events_for_asset("a-1")
        dispositions = {e.disposition for e in events}
        assert dispositions == set(LifecycleDisposition)
