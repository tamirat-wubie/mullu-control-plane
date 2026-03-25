"""Purpose: asset / configuration / inventory runtime engine.
Governance scope: registering assets and configuration items, managing
    inventory, assigning ownership, tracking lifecycle events, detecting
    dependency and inventory violations, producing immutable snapshots.
Dependencies: asset_runtime contracts, event_spine, core invariants.
Invariants:
  - Retired/disposed assets cannot be assigned.
  - Depleted inventory blocks assignment.
  - Every mutation emits an event.
  - All returns are immutable.
"""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from typing import Any

from ..contracts.asset_runtime import (
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
from ..contracts.event import EventRecord, EventSource, EventType
from .event_spine import EventSpineEngine
from .invariants import RuntimeCoreInvariantError, stable_identifier


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _emit(es: EventSpineEngine, action: str, payload: dict, cid: str) -> EventRecord:
    now = _now_iso()
    payload["action"] = action
    event = EventRecord(
        event_id=stable_identifier("evt-asst", {"action": action, "ts": now, "cid": cid}),
        event_type=EventType.CUSTOM,
        source=EventSource.COMMUNICATION_SYSTEM,
        correlation_id=cid,
        payload=payload,
        emitted_at=now,
    )
    es.emit(event)
    return event


_ASSET_TERMINAL = frozenset({AssetStatus.RETIRED, AssetStatus.DISPOSED})


class AssetRuntimeEngine:
    """Asset, configuration, and inventory engine."""

    def __init__(self, event_spine: EventSpineEngine) -> None:
        if not isinstance(event_spine, EventSpineEngine):
            raise RuntimeCoreInvariantError("event_spine must be an EventSpineEngine")
        self._events = event_spine
        self._assets: dict[str, AssetRecord] = {}
        self._config_items: dict[str, ConfigurationItem] = {}
        self._inventory: dict[str, InventoryRecord] = {}
        self._assignments: dict[str, AssetAssignment] = {}
        self._dependencies: dict[str, AssetDependency] = {}
        self._lifecycle: dict[str, LifecycleEvent] = {}
        self._assessments: dict[str, AssetAssessment] = {}
        self._violations: dict[str, AssetViolation] = {}
        self._snapshot_ids: set[str] = set()

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def asset_count(self) -> int:
        return len(self._assets)

    @property
    def config_item_count(self) -> int:
        return len(self._config_items)

    @property
    def inventory_count(self) -> int:
        return len(self._inventory)

    @property
    def assignment_count(self) -> int:
        return len(self._assignments)

    @property
    def dependency_count(self) -> int:
        return len(self._dependencies)

    @property
    def lifecycle_event_count(self) -> int:
        return len(self._lifecycle)

    @property
    def assessment_count(self) -> int:
        return len(self._assessments)

    @property
    def violation_count(self) -> int:
        return len(self._violations)

    # ------------------------------------------------------------------
    # Assets
    # ------------------------------------------------------------------

    def register_asset(
        self,
        asset_id: str,
        name: str,
        tenant_id: str,
        *,
        kind: AssetKind = AssetKind.HARDWARE,
        ownership: OwnershipType = OwnershipType.OWNED,
        owner_ref: str = "",
        vendor_ref: str = "",
        value: float = 0.0,
    ) -> AssetRecord:
        """Register an asset."""
        if asset_id in self._assets:
            raise RuntimeCoreInvariantError(f"Duplicate asset_id: {asset_id}")
        now = _now_iso()
        a = AssetRecord(
            asset_id=asset_id, name=name, tenant_id=tenant_id,
            kind=kind, status=AssetStatus.ACTIVE, ownership=ownership,
            owner_ref=owner_ref, vendor_ref=vendor_ref, value=value,
            registered_at=now,
        )
        self._assets[asset_id] = a
        _emit(self._events, "asset_registered", {
            "asset_id": asset_id, "name": name, "kind": kind.value,
        }, asset_id)
        return a

    def get_asset(self, asset_id: str) -> AssetRecord:
        """Get an asset by ID."""
        a = self._assets.get(asset_id)
        if a is None:
            raise RuntimeCoreInvariantError(f"Unknown asset_id: {asset_id}")
        return a

    def deactivate_asset(self, asset_id: str) -> AssetRecord:
        """Deactivate an asset."""
        old = self.get_asset(asset_id)
        if old.status != AssetStatus.ACTIVE:
            raise RuntimeCoreInvariantError("Can only deactivate ACTIVE assets")
        updated = AssetRecord(
            asset_id=old.asset_id, name=old.name, tenant_id=old.tenant_id,
            kind=old.kind, status=AssetStatus.INACTIVE, ownership=old.ownership,
            owner_ref=old.owner_ref, vendor_ref=old.vendor_ref, value=old.value,
            registered_at=old.registered_at, metadata=old.metadata,
        )
        self._assets[asset_id] = updated
        _emit(self._events, "asset_deactivated", {"asset_id": asset_id}, asset_id)
        return updated

    def maintain_asset(self, asset_id: str) -> AssetRecord:
        """Place an asset in maintenance."""
        old = self.get_asset(asset_id)
        if old.status in _ASSET_TERMINAL:
            raise RuntimeCoreInvariantError(
                f"Cannot maintain asset in status {old.status.value}"
            )
        updated = AssetRecord(
            asset_id=old.asset_id, name=old.name, tenant_id=old.tenant_id,
            kind=old.kind, status=AssetStatus.MAINTENANCE, ownership=old.ownership,
            owner_ref=old.owner_ref, vendor_ref=old.vendor_ref, value=old.value,
            registered_at=old.registered_at, metadata=old.metadata,
        )
        self._assets[asset_id] = updated
        _emit(self._events, "asset_maintenance", {"asset_id": asset_id}, asset_id)
        return updated

    def retire_asset(self, asset_id: str) -> AssetRecord:
        """Retire an asset."""
        old = self.get_asset(asset_id)
        if old.status in _ASSET_TERMINAL:
            raise RuntimeCoreInvariantError(
                f"Asset already in status {old.status.value}"
            )
        updated = AssetRecord(
            asset_id=old.asset_id, name=old.name, tenant_id=old.tenant_id,
            kind=old.kind, status=AssetStatus.RETIRED, ownership=old.ownership,
            owner_ref=old.owner_ref, vendor_ref=old.vendor_ref, value=old.value,
            registered_at=old.registered_at, metadata=old.metadata,
        )
        self._assets[asset_id] = updated
        _emit(self._events, "asset_retired", {"asset_id": asset_id}, asset_id)
        return updated

    def dispose_asset(self, asset_id: str) -> AssetRecord:
        """Dispose of an asset."""
        old = self.get_asset(asset_id)
        if old.status == AssetStatus.DISPOSED:
            raise RuntimeCoreInvariantError("Asset already disposed")
        updated = AssetRecord(
            asset_id=old.asset_id, name=old.name, tenant_id=old.tenant_id,
            kind=old.kind, status=AssetStatus.DISPOSED, ownership=old.ownership,
            owner_ref=old.owner_ref, vendor_ref=old.vendor_ref, value=old.value,
            registered_at=old.registered_at, metadata=old.metadata,
        )
        self._assets[asset_id] = updated
        _emit(self._events, "asset_disposed", {"asset_id": asset_id}, asset_id)
        return updated

    def assets_for_tenant(self, tenant_id: str) -> tuple[AssetRecord, ...]:
        """Return all assets for a tenant."""
        return tuple(a for a in self._assets.values() if a.tenant_id == tenant_id)

    # ------------------------------------------------------------------
    # Configuration items
    # ------------------------------------------------------------------

    def register_config_item(
        self,
        ci_id: str,
        asset_id: str,
        name: str,
        *,
        environment_ref: str = "",
        workspace_ref: str = "",
        version: str = "",
    ) -> ConfigurationItem:
        """Register a configuration item linked to an asset."""
        if ci_id in self._config_items:
            raise RuntimeCoreInvariantError(f"Duplicate ci_id: {ci_id}")
        if asset_id not in self._assets:
            raise RuntimeCoreInvariantError(f"Unknown asset_id: {asset_id}")
        now = _now_iso()
        ci = ConfigurationItem(
            ci_id=ci_id, asset_id=asset_id, name=name,
            status=ConfigurationItemStatus.ACTIVE,
            environment_ref=environment_ref, workspace_ref=workspace_ref,
            version=version, created_at=now,
        )
        self._config_items[ci_id] = ci
        _emit(self._events, "config_item_registered", {
            "ci_id": ci_id, "asset_id": asset_id,
        }, ci_id)
        return ci

    def get_config_item(self, ci_id: str) -> ConfigurationItem:
        """Get a configuration item by ID."""
        ci = self._config_items.get(ci_id)
        if ci is None:
            raise RuntimeCoreInvariantError(f"Unknown ci_id: {ci_id}")
        return ci

    def deprecate_config_item(self, ci_id: str) -> ConfigurationItem:
        """Deprecate a configuration item."""
        old = self.get_config_item(ci_id)
        if old.status in (ConfigurationItemStatus.DEPRECATED, ConfigurationItemStatus.ARCHIVED):
            raise RuntimeCoreInvariantError(
                f"Config item already in status {old.status.value}"
            )
        updated = ConfigurationItem(
            ci_id=old.ci_id, asset_id=old.asset_id, name=old.name,
            status=ConfigurationItemStatus.DEPRECATED,
            environment_ref=old.environment_ref, workspace_ref=old.workspace_ref,
            version=old.version, created_at=old.created_at, metadata=old.metadata,
        )
        self._config_items[ci_id] = updated
        _emit(self._events, "config_item_deprecated", {"ci_id": ci_id}, ci_id)
        return updated

    def archive_config_item(self, ci_id: str) -> ConfigurationItem:
        """Archive a configuration item."""
        old = self.get_config_item(ci_id)
        if old.status == ConfigurationItemStatus.ARCHIVED:
            raise RuntimeCoreInvariantError("Config item already archived")
        updated = ConfigurationItem(
            ci_id=old.ci_id, asset_id=old.asset_id, name=old.name,
            status=ConfigurationItemStatus.ARCHIVED,
            environment_ref=old.environment_ref, workspace_ref=old.workspace_ref,
            version=old.version, created_at=old.created_at, metadata=old.metadata,
        )
        self._config_items[ci_id] = updated
        _emit(self._events, "config_item_archived", {"ci_id": ci_id}, ci_id)
        return updated

    def config_items_for_asset(self, asset_id: str) -> tuple[ConfigurationItem, ...]:
        """Return all configuration items for an asset."""
        return tuple(ci for ci in self._config_items.values() if ci.asset_id == asset_id)

    # ------------------------------------------------------------------
    # Inventory
    # ------------------------------------------------------------------

    def register_inventory(
        self,
        inventory_id: str,
        asset_id: str,
        tenant_id: str,
        total_quantity: int,
    ) -> InventoryRecord:
        """Register an inventory record."""
        if inventory_id in self._inventory:
            raise RuntimeCoreInvariantError(f"Duplicate inventory_id: {inventory_id}")
        if asset_id not in self._assets:
            raise RuntimeCoreInvariantError(f"Unknown asset_id: {asset_id}")
        now = _now_iso()
        inv = InventoryRecord(
            inventory_id=inventory_id, asset_id=asset_id, tenant_id=tenant_id,
            disposition=InventoryDisposition.AVAILABLE,
            total_quantity=total_quantity, assigned_quantity=0,
            available_quantity=total_quantity, updated_at=now,
        )
        self._inventory[inventory_id] = inv
        _emit(self._events, "inventory_registered", {
            "inventory_id": inventory_id, "asset_id": asset_id,
            "total_quantity": total_quantity,
        }, inventory_id)
        return inv

    def get_inventory(self, inventory_id: str) -> InventoryRecord:
        """Get an inventory record by ID."""
        inv = self._inventory.get(inventory_id)
        if inv is None:
            raise RuntimeCoreInvariantError(f"Unknown inventory_id: {inventory_id}")
        return inv

    def assign_inventory(self, inventory_id: str, quantity: int) -> InventoryRecord:
        """Assign inventory quantity."""
        old = self.get_inventory(inventory_id)
        if old.disposition == InventoryDisposition.DEPLETED:
            raise RuntimeCoreInvariantError("Cannot assign from depleted inventory")
        effective = min(quantity, old.available_quantity)
        if effective <= 0:
            raise RuntimeCoreInvariantError("No available inventory to assign")
        new_assigned = old.assigned_quantity + effective
        new_available = old.available_quantity - effective
        disposition = InventoryDisposition.DEPLETED if new_available <= 0 else InventoryDisposition.ASSIGNED
        now = _now_iso()
        updated = InventoryRecord(
            inventory_id=old.inventory_id, asset_id=old.asset_id,
            tenant_id=old.tenant_id, disposition=disposition,
            total_quantity=old.total_quantity, assigned_quantity=new_assigned,
            available_quantity=new_available, updated_at=now,
            metadata=old.metadata,
        )
        self._inventory[inventory_id] = updated
        _emit(self._events, "inventory_assigned", {
            "inventory_id": inventory_id, "quantity": effective,
        }, inventory_id)
        return updated

    def release_inventory(self, inventory_id: str, quantity: int) -> InventoryRecord:
        """Release assigned inventory back to available."""
        old = self.get_inventory(inventory_id)
        effective = min(quantity, old.assigned_quantity)
        if effective <= 0:
            raise RuntimeCoreInvariantError("No assigned inventory to release")
        new_assigned = old.assigned_quantity - effective
        new_available = old.available_quantity + effective
        disposition = InventoryDisposition.AVAILABLE if new_assigned == 0 else InventoryDisposition.ASSIGNED
        now = _now_iso()
        updated = InventoryRecord(
            inventory_id=old.inventory_id, asset_id=old.asset_id,
            tenant_id=old.tenant_id, disposition=disposition,
            total_quantity=old.total_quantity, assigned_quantity=new_assigned,
            available_quantity=new_available, updated_at=now,
            metadata=old.metadata,
        )
        self._inventory[inventory_id] = updated
        _emit(self._events, "inventory_released", {
            "inventory_id": inventory_id, "quantity": effective,
        }, inventory_id)
        return updated

    def inventory_for_asset(self, asset_id: str) -> tuple[InventoryRecord, ...]:
        """Return all inventory records for an asset."""
        return tuple(inv for inv in self._inventory.values() if inv.asset_id == asset_id)

    # ------------------------------------------------------------------
    # Assignments
    # ------------------------------------------------------------------

    def assign_asset(
        self,
        assignment_id: str,
        asset_id: str,
        scope_ref_id: str,
        scope_ref_type: str,
        *,
        assigned_by: str = "system",
    ) -> AssetAssignment:
        """Assign an asset to a scope."""
        if assignment_id in self._assignments:
            raise RuntimeCoreInvariantError(f"Duplicate assignment_id: {assignment_id}")
        asset = self.get_asset(asset_id)
        if asset.status in _ASSET_TERMINAL:
            raise RuntimeCoreInvariantError(
                f"Cannot assign asset in status {asset.status.value}"
            )
        now = _now_iso()
        aa = AssetAssignment(
            assignment_id=assignment_id, asset_id=asset_id,
            scope_ref_id=scope_ref_id, scope_ref_type=scope_ref_type,
            assigned_by=assigned_by, assigned_at=now,
        )
        self._assignments[assignment_id] = aa
        _emit(self._events, "asset_assigned", {
            "assignment_id": assignment_id, "asset_id": asset_id,
            "scope_ref_id": scope_ref_id,
        }, assignment_id)
        return aa

    def assignments_for_asset(self, asset_id: str) -> tuple[AssetAssignment, ...]:
        """Return all assignments for an asset."""
        return tuple(a for a in self._assignments.values() if a.asset_id == asset_id)

    # ------------------------------------------------------------------
    # Dependencies
    # ------------------------------------------------------------------

    def register_dependency(
        self,
        dependency_id: str,
        asset_id: str,
        depends_on_asset_id: str,
        *,
        description: str = "",
    ) -> AssetDependency:
        """Register a dependency between two assets."""
        if dependency_id in self._dependencies:
            raise RuntimeCoreInvariantError(f"Duplicate dependency_id: {dependency_id}")
        if asset_id not in self._assets:
            raise RuntimeCoreInvariantError(f"Unknown asset_id: {asset_id}")
        if depends_on_asset_id not in self._assets:
            raise RuntimeCoreInvariantError(f"Unknown depends_on_asset_id: {depends_on_asset_id}")
        now = _now_iso()
        dep = AssetDependency(
            dependency_id=dependency_id, asset_id=asset_id,
            depends_on_asset_id=depends_on_asset_id,
            description=description, created_at=now,
        )
        self._dependencies[dependency_id] = dep
        _emit(self._events, "dependency_registered", {
            "dependency_id": dependency_id, "asset_id": asset_id,
            "depends_on": depends_on_asset_id,
        }, dependency_id)
        return dep

    def dependencies_for_asset(self, asset_id: str) -> tuple[AssetDependency, ...]:
        """Return all dependencies where asset_id depends on something."""
        return tuple(d for d in self._dependencies.values() if d.asset_id == asset_id)

    # ------------------------------------------------------------------
    # Lifecycle events
    # ------------------------------------------------------------------

    def record_lifecycle_event(
        self,
        event_id: str,
        asset_id: str,
        disposition: LifecycleDisposition,
        *,
        description: str = "",
        performed_by: str = "system",
    ) -> LifecycleEvent:
        """Record a lifecycle event for an asset."""
        if event_id in self._lifecycle:
            raise RuntimeCoreInvariantError(f"Duplicate event_id: {event_id}")
        if asset_id not in self._assets:
            raise RuntimeCoreInvariantError(f"Unknown asset_id: {asset_id}")
        now = _now_iso()
        le = LifecycleEvent(
            event_id=event_id, asset_id=asset_id, disposition=disposition,
            description=description, performed_by=performed_by,
            performed_at=now,
        )
        self._lifecycle[event_id] = le
        _emit(self._events, "lifecycle_event_recorded", {
            "event_id": event_id, "asset_id": asset_id,
            "disposition": disposition.value,
        }, asset_id)
        return le

    def lifecycle_events_for_asset(self, asset_id: str) -> tuple[LifecycleEvent, ...]:
        """Return all lifecycle events for an asset."""
        return tuple(le for le in self._lifecycle.values() if le.asset_id == asset_id)

    # ------------------------------------------------------------------
    # Assessments
    # ------------------------------------------------------------------

    def assess_asset(
        self,
        assessment_id: str,
        asset_id: str,
        health_score: float,
        risk_score: float,
        *,
        assessed_by: str = "system",
    ) -> AssetAssessment:
        """Assess an asset's health and risk."""
        if assessment_id in self._assessments:
            raise RuntimeCoreInvariantError(f"Duplicate assessment_id: {assessment_id}")
        if asset_id not in self._assets:
            raise RuntimeCoreInvariantError(f"Unknown asset_id: {asset_id}")
        now = _now_iso()
        aa = AssetAssessment(
            assessment_id=assessment_id, asset_id=asset_id,
            health_score=health_score, risk_score=risk_score,
            assessed_by=assessed_by, assessed_at=now,
        )
        self._assessments[assessment_id] = aa
        _emit(self._events, "asset_assessed", {
            "assessment_id": assessment_id, "asset_id": asset_id,
            "health_score": health_score, "risk_score": risk_score,
        }, asset_id)
        return aa

    def assessments_for_asset(self, asset_id: str) -> tuple[AssetAssessment, ...]:
        """Return all assessments for an asset."""
        return tuple(a for a in self._assessments.values() if a.asset_id == asset_id)

    # ------------------------------------------------------------------
    # Violation detection
    # ------------------------------------------------------------------

    def detect_asset_violations(self) -> tuple[AssetViolation, ...]:
        """Detect asset and inventory violations."""
        now = _now_iso()
        new_violations: list[AssetViolation] = []

        # Retired/disposed assets with active assignments
        for asset in self._assets.values():
            if asset.status in _ASSET_TERMINAL:
                active_assignments = [
                    a for a in self._assignments.values()
                    if a.asset_id == asset.asset_id
                ]
                if active_assignments:
                    vid = stable_identifier("viol-asst", {
                        "asset": asset.asset_id, "op": "retired_with_assignments",
                    })
                    if vid not in self._violations:
                        v = AssetViolation(
                            violation_id=vid, asset_id=asset.asset_id,
                            tenant_id=asset.tenant_id,
                            operation="retired_with_assignments",
                            reason=f"Asset {asset.asset_id} is {asset.status.value} but has {len(active_assignments)} active assignments",
                            detected_at=now,
                        )
                        self._violations[vid] = v
                        new_violations.append(v)

        # Dependencies on retired/disposed assets
        for dep in self._dependencies.values():
            target = self._assets.get(dep.depends_on_asset_id)
            if target and target.status in _ASSET_TERMINAL:
                vid = stable_identifier("viol-asst", {
                    "dep": dep.dependency_id, "op": "depends_on_retired",
                })
                if vid not in self._violations:
                    v = AssetViolation(
                        violation_id=vid, asset_id=dep.asset_id,
                        tenant_id=target.tenant_id,
                        operation="depends_on_retired",
                        reason=f"Asset {dep.asset_id} depends on {dep.depends_on_asset_id} which is {target.status.value}",
                        detected_at=now,
                    )
                    self._violations[vid] = v
                    new_violations.append(v)

        # Depleted inventory
        for inv in self._inventory.values():
            if inv.disposition == InventoryDisposition.DEPLETED:
                vid = stable_identifier("viol-asst", {
                    "inv": inv.inventory_id, "op": "depleted_inventory",
                })
                if vid not in self._violations:
                    v = AssetViolation(
                        violation_id=vid, asset_id=inv.asset_id,
                        tenant_id=inv.tenant_id,
                        operation="depleted_inventory",
                        reason=f"Inventory {inv.inventory_id} is depleted",
                        detected_at=now,
                    )
                    self._violations[vid] = v
                    new_violations.append(v)

        if new_violations:
            _emit(self._events, "asset_violations_detected", {
                "count": len(new_violations),
            }, "violation-scan")
        return tuple(new_violations)

    def violations_for_asset(self, asset_id: str) -> tuple[AssetViolation, ...]:
        """Return all violations for an asset."""
        return tuple(v for v in self._violations.values() if v.asset_id == asset_id)

    # ------------------------------------------------------------------
    # Asset snapshot
    # ------------------------------------------------------------------

    def asset_snapshot(self, snapshot_id: str) -> AssetSnapshot:
        """Capture a point-in-time asset snapshot."""
        if snapshot_id in self._snapshot_ids:
            raise RuntimeCoreInvariantError(f"Duplicate snapshot_id: {snapshot_id}")
        now = _now_iso()
        total_value = sum(
            a.value for a in self._assets.values()
            if a.status not in _ASSET_TERMINAL
        )
        snap = AssetSnapshot(
            snapshot_id=snapshot_id,
            total_assets=self.asset_count,
            total_active=sum(1 for a in self._assets.values() if a.status == AssetStatus.ACTIVE),
            total_retired=sum(1 for a in self._assets.values() if a.status in _ASSET_TERMINAL),
            total_config_items=self.config_item_count,
            total_inventory=self.inventory_count,
            total_assignments=self.assignment_count,
            total_dependencies=self.dependency_count,
            total_violations=self.violation_count,
            total_asset_value=total_value,
            captured_at=now,
        )
        self._snapshot_ids.add(snapshot_id)
        _emit(self._events, "asset_snapshot_captured", {
            "snapshot_id": snapshot_id,
        }, snapshot_id)
        return snap

    # ------------------------------------------------------------------
    # State hash
    # ------------------------------------------------------------------

    def state_hash(self) -> str:
        """Compute a hash of the current engine state."""
        parts = [
            f"assets={self.asset_count}",
            f"config_items={self.config_item_count}",
            f"inventory={self.inventory_count}",
            f"assignments={self.assignment_count}",
            f"dependencies={self.dependency_count}",
            f"lifecycle={self.lifecycle_event_count}",
            f"assessments={self.assessment_count}",
            f"violations={self.violation_count}",
        ]
        return sha256("|".join(parts).encode()).hexdigest()
