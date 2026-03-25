"""Purpose: factory / production / quality runtime engine.
Governance scope: registering plants, lines, stations, machines; managing
    work orders and batches; recording quality checks and downtime events;
    detecting factory violations; producing immutable snapshots.
Dependencies: factory_runtime contracts, event_spine, core invariants.
Invariants:
  - Terminal orders cannot transition.
  - Completed batches auto-compute yield from QC.
  - Every mutation emits an event.
  - All returns are immutable.
"""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from typing import Any

from ..contracts.factory_runtime import (
    BatchRecord,
    BatchStatus,
    DowntimeEvent,
    FactoryAssessment,
    FactoryClosureReport,
    FactorySnapshot,
    FactoryStatus,
    LineRecord,
    MachineRecord,
    MachineStatus,
    MaintenanceDisposition,
    PlantRecord,
    QualityCheck,
    QualityVerdict,
    StationRecord,
    WorkOrder,
    WorkOrderStatus,
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
        event_id=stable_identifier("evt-fac", {"action": action, "ts": now, "cid": cid}),
        event_type=EventType.CUSTOM,
        source=EventSource.COMMUNICATION_SYSTEM,
        correlation_id=cid,
        payload=payload,
        emitted_at=now,
    )
    es.emit(event)
    return event


_ORDER_TERMINAL = frozenset({WorkOrderStatus.COMPLETED, WorkOrderStatus.CANCELLED})
_BATCH_TERMINAL = frozenset({BatchStatus.COMPLETED, BatchStatus.REJECTED, BatchStatus.SCRAPPED})


class FactoryRuntimeEngine:
    """Factory, production, and quality engine."""

    def __init__(self, event_spine: EventSpineEngine) -> None:
        if not isinstance(event_spine, EventSpineEngine):
            raise RuntimeCoreInvariantError("event_spine must be an EventSpineEngine")
        self._events = event_spine
        self._plants: dict[str, PlantRecord] = {}
        self._lines: dict[str, LineRecord] = {}
        self._stations: dict[str, StationRecord] = {}
        self._machines: dict[str, MachineRecord] = {}
        self._orders: dict[str, WorkOrder] = {}
        self._batches: dict[str, BatchRecord] = {}
        self._checks: dict[str, QualityCheck] = {}
        self._downtime: dict[str, DowntimeEvent] = {}
        self._violations: dict[str, dict[str, Any]] = {}
        self._snapshot_ids: set[str] = set()

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def plant_count(self) -> int:
        return len(self._plants)

    @property
    def line_count(self) -> int:
        return len(self._lines)

    @property
    def station_count(self) -> int:
        return len(self._stations)

    @property
    def machine_count(self) -> int:
        return len(self._machines)

    @property
    def order_count(self) -> int:
        return len(self._orders)

    @property
    def batch_count(self) -> int:
        return len(self._batches)

    @property
    def check_count(self) -> int:
        return len(self._checks)

    @property
    def downtime_count(self) -> int:
        return len(self._downtime)

    @property
    def violation_count(self) -> int:
        return len(self._violations)

    # ------------------------------------------------------------------
    # Plants
    # ------------------------------------------------------------------

    def register_plant(
        self,
        plant_id: str,
        tenant_id: str,
        display_name: str,
    ) -> PlantRecord:
        """Register a factory plant."""
        if plant_id in self._plants:
            raise RuntimeCoreInvariantError(f"Duplicate plant_id: {plant_id}")
        now = _now_iso()
        plant = PlantRecord(
            plant_id=plant_id,
            tenant_id=tenant_id,
            display_name=display_name,
            status=FactoryStatus.ACTIVE,
            line_count=0,
            created_at=now,
        )
        self._plants[plant_id] = plant
        _emit(self._events, "plant_registered", {
            "plant_id": plant_id, "tenant_id": tenant_id,
        }, plant_id)
        return plant

    def get_plant(self, plant_id: str) -> PlantRecord:
        """Get a plant by ID."""
        p = self._plants.get(plant_id)
        if p is None:
            raise RuntimeCoreInvariantError(f"Unknown plant_id: {plant_id}")
        return p

    def plants_for_tenant(self, tenant_id: str) -> tuple[PlantRecord, ...]:
        """Return all plants for a tenant."""
        return tuple(p for p in self._plants.values() if p.tenant_id == tenant_id)

    # ------------------------------------------------------------------
    # Lines
    # ------------------------------------------------------------------

    def register_line(
        self,
        line_id: str,
        tenant_id: str,
        plant_id: str,
        display_name: str,
    ) -> LineRecord:
        """Register a production line, incrementing the parent plant line_count."""
        if line_id in self._lines:
            raise RuntimeCoreInvariantError(f"Duplicate line_id: {line_id}")
        old_plant = self.get_plant(plant_id)
        now = _now_iso()
        line = LineRecord(
            line_id=line_id,
            tenant_id=tenant_id,
            plant_id=plant_id,
            display_name=display_name,
            station_count=0,
            created_at=now,
        )
        self._lines[line_id] = line
        # Increment plant line_count
        updated_plant = PlantRecord(
            plant_id=old_plant.plant_id,
            tenant_id=old_plant.tenant_id,
            display_name=old_plant.display_name,
            status=old_plant.status,
            line_count=old_plant.line_count + 1,
            created_at=old_plant.created_at,
            metadata=old_plant.metadata,
        )
        self._plants[plant_id] = updated_plant
        _emit(self._events, "line_registered", {
            "line_id": line_id, "plant_id": plant_id,
        }, line_id)
        return line

    def get_line(self, line_id: str) -> LineRecord:
        """Get a line by ID."""
        ln = self._lines.get(line_id)
        if ln is None:
            raise RuntimeCoreInvariantError(f"Unknown line_id: {line_id}")
        return ln

    # ------------------------------------------------------------------
    # Stations
    # ------------------------------------------------------------------

    def register_station(
        self,
        station_id: str,
        tenant_id: str,
        line_id: str,
        display_name: str,
        machine_ref: str,
    ) -> StationRecord:
        """Register a station, incrementing the parent line station_count."""
        if station_id in self._stations:
            raise RuntimeCoreInvariantError(f"Duplicate station_id: {station_id}")
        old_line = self.get_line(line_id)
        now = _now_iso()
        station = StationRecord(
            station_id=station_id,
            tenant_id=tenant_id,
            line_id=line_id,
            display_name=display_name,
            machine_ref=machine_ref,
            created_at=now,
        )
        self._stations[station_id] = station
        # Increment line station_count
        updated_line = LineRecord(
            line_id=old_line.line_id,
            tenant_id=old_line.tenant_id,
            plant_id=old_line.plant_id,
            display_name=old_line.display_name,
            station_count=old_line.station_count + 1,
            created_at=old_line.created_at,
            metadata=old_line.metadata,
        )
        self._lines[line_id] = updated_line
        _emit(self._events, "station_registered", {
            "station_id": station_id, "line_id": line_id,
        }, station_id)
        return station

    # ------------------------------------------------------------------
    # Machines
    # ------------------------------------------------------------------

    def register_machine(
        self,
        machine_id: str,
        tenant_id: str,
        station_ref: str,
        display_name: str,
    ) -> MachineRecord:
        """Register a machine."""
        if machine_id in self._machines:
            raise RuntimeCoreInvariantError(f"Duplicate machine_id: {machine_id}")
        now = _now_iso()
        machine = MachineRecord(
            machine_id=machine_id,
            tenant_id=tenant_id,
            station_ref=station_ref,
            display_name=display_name,
            status=MachineStatus.OPERATIONAL,
            uptime_hours=0,
            created_at=now,
        )
        self._machines[machine_id] = machine
        _emit(self._events, "machine_registered", {
            "machine_id": machine_id, "station_ref": station_ref,
        }, machine_id)
        return machine

    # ------------------------------------------------------------------
    # Work Orders
    # ------------------------------------------------------------------

    def create_work_order(
        self,
        order_id: str,
        tenant_id: str,
        plant_id: str,
        product_ref: str,
        quantity: int,
    ) -> WorkOrder:
        """Create a work order in DRAFT status."""
        if order_id in self._orders:
            raise RuntimeCoreInvariantError(f"Duplicate order_id: {order_id}")
        self.get_plant(plant_id)  # ensure plant exists
        now = _now_iso()
        order = WorkOrder(
            order_id=order_id,
            tenant_id=tenant_id,
            plant_id=plant_id,
            product_ref=product_ref,
            status=WorkOrderStatus.DRAFT,
            quantity=quantity,
            created_at=now,
        )
        self._orders[order_id] = order
        _emit(self._events, "order_created", {
            "order_id": order_id, "plant_id": plant_id,
        }, order_id)
        return order

    def _transition_order(self, order_id: str, target: WorkOrderStatus) -> WorkOrder:
        old = self._orders.get(order_id)
        if old is None:
            raise RuntimeCoreInvariantError(f"Unknown order_id: {order_id}")
        if old.status in _ORDER_TERMINAL:
            raise RuntimeCoreInvariantError(
                f"Cannot transition order in terminal status {old.status.value}"
            )
        updated = WorkOrder(
            order_id=old.order_id,
            tenant_id=old.tenant_id,
            plant_id=old.plant_id,
            product_ref=old.product_ref,
            status=target,
            quantity=old.quantity,
            created_at=old.created_at,
            metadata=old.metadata,
        )
        self._orders[order_id] = updated
        _emit(self._events, f"order_{target.value}", {
            "order_id": order_id,
        }, order_id)
        return updated

    def release_order(self, order_id: str) -> WorkOrder:
        """Release a DRAFT order."""
        old = self._orders.get(order_id)
        if old is None:
            raise RuntimeCoreInvariantError(f"Unknown order_id: {order_id}")
        if old.status != WorkOrderStatus.DRAFT:
            raise RuntimeCoreInvariantError("Can only release DRAFT orders")
        return self._transition_order(order_id, WorkOrderStatus.RELEASED)

    def start_order(self, order_id: str) -> WorkOrder:
        """Start a RELEASED order."""
        old = self._orders.get(order_id)
        if old is None:
            raise RuntimeCoreInvariantError(f"Unknown order_id: {order_id}")
        if old.status != WorkOrderStatus.RELEASED:
            raise RuntimeCoreInvariantError("Can only start RELEASED orders")
        return self._transition_order(order_id, WorkOrderStatus.IN_PROGRESS)

    def complete_order(self, order_id: str) -> WorkOrder:
        """Complete an IN_PROGRESS order."""
        old = self._orders.get(order_id)
        if old is None:
            raise RuntimeCoreInvariantError(f"Unknown order_id: {order_id}")
        if old.status != WorkOrderStatus.IN_PROGRESS:
            raise RuntimeCoreInvariantError("Can only complete IN_PROGRESS orders")
        return self._transition_order(order_id, WorkOrderStatus.COMPLETED)

    def cancel_order(self, order_id: str) -> WorkOrder:
        """Cancel a non-terminal order."""
        return self._transition_order(order_id, WorkOrderStatus.CANCELLED)

    # ------------------------------------------------------------------
    # Batches
    # ------------------------------------------------------------------

    def start_batch(
        self,
        batch_id: str,
        tenant_id: str,
        order_id: str,
        unit_count: int,
    ) -> BatchRecord:
        """Start a batch linked to a work order."""
        if batch_id in self._batches:
            raise RuntimeCoreInvariantError(f"Duplicate batch_id: {batch_id}")
        # Ensure order exists
        self._orders.get(order_id)
        if self._orders.get(order_id) is None:
            raise RuntimeCoreInvariantError(f"Unknown order_id: {order_id}")
        now = _now_iso()
        batch = BatchRecord(
            batch_id=batch_id,
            tenant_id=tenant_id,
            order_id=order_id,
            status=BatchStatus.IN_PROGRESS,
            unit_count=unit_count,
            yield_rate=0.0,
            created_at=now,
        )
        self._batches[batch_id] = batch
        _emit(self._events, "batch_started", {
            "batch_id": batch_id, "order_id": order_id,
        }, batch_id)
        return batch

    def _get_batch(self, batch_id: str) -> BatchRecord:
        b = self._batches.get(batch_id)
        if b is None:
            raise RuntimeCoreInvariantError(f"Unknown batch_id: {batch_id}")
        return b

    def complete_batch(self, batch_id: str) -> BatchRecord:
        """Complete a batch, auto-computing yield_rate from QC checks."""
        old = self._get_batch(batch_id)
        if old.status in _BATCH_TERMINAL:
            raise RuntimeCoreInvariantError(
                f"Cannot complete batch in terminal status {old.status.value}"
            )
        # Compute yield_rate from QC
        checks = self.checks_for_batch(batch_id)
        if checks:
            passed = sum(1 for c in checks if c.verdict == QualityVerdict.PASS)
            yield_rate = passed / len(checks)
        else:
            yield_rate = 1.0
        updated = BatchRecord(
            batch_id=old.batch_id,
            tenant_id=old.tenant_id,
            order_id=old.order_id,
            status=BatchStatus.COMPLETED,
            unit_count=old.unit_count,
            yield_rate=yield_rate,
            created_at=old.created_at,
            metadata=old.metadata,
        )
        self._batches[batch_id] = updated
        _emit(self._events, "batch_completed", {
            "batch_id": batch_id, "yield_rate": yield_rate,
        }, batch_id)
        return updated

    def reject_batch(self, batch_id: str) -> BatchRecord:
        """Reject a batch."""
        old = self._get_batch(batch_id)
        if old.status in _BATCH_TERMINAL:
            raise RuntimeCoreInvariantError(
                f"Cannot reject batch in terminal status {old.status.value}"
            )
        updated = BatchRecord(
            batch_id=old.batch_id,
            tenant_id=old.tenant_id,
            order_id=old.order_id,
            status=BatchStatus.REJECTED,
            unit_count=old.unit_count,
            yield_rate=old.yield_rate,
            created_at=old.created_at,
            metadata=old.metadata,
        )
        self._batches[batch_id] = updated
        _emit(self._events, "batch_rejected", {
            "batch_id": batch_id,
        }, batch_id)
        return updated

    def scrap_batch(self, batch_id: str) -> BatchRecord:
        """Scrap a batch."""
        old = self._get_batch(batch_id)
        if old.status in _BATCH_TERMINAL:
            raise RuntimeCoreInvariantError(
                f"Cannot scrap batch in terminal status {old.status.value}"
            )
        updated = BatchRecord(
            batch_id=old.batch_id,
            tenant_id=old.tenant_id,
            order_id=old.order_id,
            status=BatchStatus.SCRAPPED,
            unit_count=old.unit_count,
            yield_rate=old.yield_rate,
            created_at=old.created_at,
            metadata=old.metadata,
        )
        self._batches[batch_id] = updated
        _emit(self._events, "batch_scrapped", {
            "batch_id": batch_id,
        }, batch_id)
        return updated

    def checks_for_batch(self, batch_id: str) -> tuple[QualityCheck, ...]:
        """Return all quality checks for a batch."""
        return tuple(c for c in self._checks.values() if c.batch_id == batch_id)

    # ------------------------------------------------------------------
    # Quality Checks
    # ------------------------------------------------------------------

    def record_quality_check(
        self,
        check_id: str,
        tenant_id: str,
        batch_id: str,
        verdict: QualityVerdict,
        defect_count: int,
        inspector_ref: str,
    ) -> QualityCheck:
        """Record a quality check for a batch."""
        if check_id in self._checks:
            raise RuntimeCoreInvariantError(f"Duplicate check_id: {check_id}")
        self._get_batch(batch_id)  # ensure batch exists
        now = _now_iso()
        qc = QualityCheck(
            check_id=check_id,
            tenant_id=tenant_id,
            batch_id=batch_id,
            verdict=verdict,
            defect_count=defect_count,
            inspector_ref=inspector_ref,
            checked_at=now,
        )
        self._checks[check_id] = qc
        _emit(self._events, "quality_check_recorded", {
            "check_id": check_id, "batch_id": batch_id, "verdict": verdict.value,
        }, check_id)
        return qc

    # ------------------------------------------------------------------
    # Downtime
    # ------------------------------------------------------------------

    def record_downtime(
        self,
        event_id: str,
        tenant_id: str,
        machine_id: str,
        reason: str,
        duration_minutes: int,
        disposition: MaintenanceDisposition = MaintenanceDisposition.UNSCHEDULED,
    ) -> DowntimeEvent:
        """Record a downtime event for a machine."""
        if event_id in self._downtime:
            raise RuntimeCoreInvariantError(f"Duplicate event_id: {event_id}")
        if machine_id not in self._machines:
            raise RuntimeCoreInvariantError(f"Unknown machine_id: {machine_id}")
        now = _now_iso()
        dt = DowntimeEvent(
            event_id=event_id,
            tenant_id=tenant_id,
            machine_id=machine_id,
            reason=reason,
            duration_minutes=duration_minutes,
            disposition=disposition,
            recorded_at=now,
        )
        self._downtime[event_id] = dt
        _emit(self._events, "downtime_recorded", {
            "event_id": event_id, "machine_id": machine_id,
        }, event_id)
        return dt

    def downtime_for_machine(self, machine_id: str) -> tuple[DowntimeEvent, ...]:
        """Return all downtime events for a machine."""
        return tuple(d for d in self._downtime.values() if d.machine_id == machine_id)

    # ------------------------------------------------------------------
    # Snapshot
    # ------------------------------------------------------------------

    def factory_snapshot(self, snapshot_id: str, tenant_id: str) -> FactorySnapshot:
        """Capture a tenant-scoped point-in-time factory snapshot."""
        if snapshot_id in self._snapshot_ids:
            raise RuntimeCoreInvariantError(f"Duplicate snapshot_id: {snapshot_id}")
        now = _now_iso()
        snap = FactorySnapshot(
            snapshot_id=snapshot_id,
            tenant_id=tenant_id,
            total_plants=self.plant_count,
            total_lines=self.line_count,
            total_orders=self.order_count,
            total_batches=self.batch_count,
            total_checks=self.check_count,
            total_downtime_events=self.downtime_count,
            total_violations=self.violation_count,
            captured_at=now,
        )
        self._snapshot_ids.add(snapshot_id)
        _emit(self._events, "factory_snapshot_captured", {
            "snapshot_id": snapshot_id,
        }, snapshot_id)
        return snap

    # ------------------------------------------------------------------
    # Violation detection
    # ------------------------------------------------------------------

    def detect_factory_violations(self) -> tuple[dict[str, Any], ...]:
        """Detect factory violations (idempotent).

        Rules:
        - order_no_batches: completed order with 0 batches
        - batch_no_qc: completed batch with 0 QC checks
        - machine_excessive_downtime: machine with 3+ downtime events
        """
        now = _now_iso()
        new_violations: list[dict[str, Any]] = []

        # Rule: completed order with 0 batches
        for order in self._orders.values():
            if order.status == WorkOrderStatus.COMPLETED:
                batch_count = sum(
                    1 for b in self._batches.values() if b.order_id == order.order_id
                )
                if batch_count == 0:
                    vid = stable_identifier("viol-fac", {
                        "order": order.order_id, "op": "order_no_batches",
                    })
                    if vid not in self._violations:
                        v = {
                            "violation_id": vid,
                            "tenant_id": order.tenant_id,
                            "operation": "order_no_batches",
                            "reason": f"Completed order {order.order_id} has 0 batches",
                            "detected_at": now,
                        }
                        self._violations[vid] = v
                        new_violations.append(v)

        # Rule: completed batch with 0 QC checks
        for batch in self._batches.values():
            if batch.status == BatchStatus.COMPLETED:
                qc_count = sum(
                    1 for c in self._checks.values() if c.batch_id == batch.batch_id
                )
                if qc_count == 0:
                    vid = stable_identifier("viol-fac", {
                        "batch": batch.batch_id, "op": "batch_no_qc",
                    })
                    if vid not in self._violations:
                        v = {
                            "violation_id": vid,
                            "tenant_id": batch.tenant_id,
                            "operation": "batch_no_qc",
                            "reason": f"Completed batch {batch.batch_id} has 0 QC checks",
                            "detected_at": now,
                        }
                        self._violations[vid] = v
                        new_violations.append(v)

        # Rule: machine with 3+ downtime events
        for machine in self._machines.values():
            dt_count = sum(
                1 for d in self._downtime.values() if d.machine_id == machine.machine_id
            )
            if dt_count >= 3:
                vid = stable_identifier("viol-fac", {
                    "machine": machine.machine_id, "op": "machine_excessive_downtime",
                })
                if vid not in self._violations:
                    v = {
                        "violation_id": vid,
                        "tenant_id": machine.tenant_id,
                        "operation": "machine_excessive_downtime",
                        "reason": f"Machine {machine.machine_id} has {dt_count} downtime events",
                        "detected_at": now,
                    }
                    self._violations[vid] = v
                    new_violations.append(v)

        if new_violations:
            _emit(self._events, "factory_violations_detected", {
                "count": len(new_violations),
            }, "violation-scan")
        return tuple(new_violations)

    # ------------------------------------------------------------------
    # Assessment
    # ------------------------------------------------------------------

    def factory_assessment(self, assessment_id: str, tenant_id: str) -> FactoryAssessment:
        now = _now_iso()
        t_plants = sum(1 for p in self._plants.values() if p.tenant_id == tenant_id)
        t_orders = sum(1 for o in self._orders.values() if o.tenant_id == tenant_id)
        t_batches = sum(1 for b in self._batches.values() if b.tenant_id == tenant_id)
        t_checks = sum(1 for c in self._checks.values() if c.tenant_id == tenant_id)
        t_violations = sum(1 for v in self._violations.values() if v.get("tenant_id") == tenant_id)
        passed = sum(1 for c in self._checks.values() if c.tenant_id == tenant_id and c.verdict == QualityVerdict.PASS)
        rate = passed / t_checks if t_checks else 0.0
        assessment = FactoryAssessment(
            assessment_id=assessment_id, tenant_id=tenant_id,
            total_plants=t_plants, total_orders=t_orders,
            total_batches=t_batches, total_checks=t_checks,
            total_violations=t_violations,
            quality_rate=round(rate, 4),
            assessed_at=now,
        )
        _emit(self._events, "factory_assessment", {"assessment_id": assessment_id}, assessment_id)
        return assessment

    # ------------------------------------------------------------------
    # Closure report
    # ------------------------------------------------------------------

    def factory_closure_report(self, report_id: str, tenant_id: str) -> FactoryClosureReport:
        now = _now_iso()
        report = FactoryClosureReport(
            report_id=report_id, tenant_id=tenant_id,
            total_plants=sum(1 for p in self._plants.values() if p.tenant_id == tenant_id),
            total_orders=sum(1 for o in self._orders.values() if o.tenant_id == tenant_id),
            total_batches=sum(1 for b in self._batches.values() if b.tenant_id == tenant_id),
            total_checks=sum(1 for c in self._checks.values() if c.tenant_id == tenant_id),
            total_violations=sum(1 for v in self._violations.values() if v.get("tenant_id") == tenant_id),
            created_at=now,
        )
        _emit(self._events, "factory_closure_report", {"report_id": report_id}, report_id)
        return report

    # ------------------------------------------------------------------
    # State hash
    # ------------------------------------------------------------------

    def state_hash(self) -> str:
        """Compute a SHA-256 hash of the current engine state (no timestamps)."""
        parts = sorted([
            f"batches={self.batch_count}",
            f"checks={self.check_count}",
            f"downtime={self.downtime_count}",
            f"lines={self.line_count}",
            f"machines={self.machine_count}",
            f"orders={self.order_count}",
            f"plants={self.plant_count}",
            f"stations={self.station_count}",
            f"violations={self.violation_count}",
        ])
        return sha256("|".join(parts).encode()).hexdigest()
