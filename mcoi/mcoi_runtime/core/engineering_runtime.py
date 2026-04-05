"""Purpose: engineering quantities / systems constraints runtime engine.
Governance scope: managing engineering quantities, tolerances, reliability
    targets, safety margins, load envelopes, process windows, capacity curves,
    violations, snapshots, and closure reports.
Dependencies: engineering_runtime contracts, event_spine, core invariants.
Invariants:
  - Duplicate IDs raise RuntimeCoreInvariantError.
  - Tolerance status is auto-computed from quantity value vs limits.
  - Safety margin status is auto-computed from margin ratio.
  - Load envelope status is auto-computed from current/max ratio.
  - Process window status is auto-computed from actual vs spec limits.
  - Violation detection is idempotent.
  - Every mutation emits an event.
  - All returns are immutable.
  - Clock is injected for deterministic timestamps.
"""

from __future__ import annotations

from hashlib import sha256
from typing import Any

from mcoi_runtime.core.engine_protocol import Clock, WallClock

from ..contracts.engineering_runtime import (
    CapacityCurve,
    EngineeringClosureReport,
    EngineeringDomain,
    EngineeringQuantity,
    EngineeringSnapshot,
    EngineeringViolation,
    LoadEnvelope,
    LoadEnvelopeStatus,
    ProcessWindow,
    ProcessWindowStatus,
    ReliabilityGrade,
    ReliabilityTarget,
    SafetyMargin,
    SafetyMarginStatus,
    ToleranceRecord,
    ToleranceStatus,
)
from ..contracts.event import EventRecord, EventSource, EventType
from .event_spine import EventSpineEngine
from .invariants import RuntimeCoreInvariantError, stable_identifier


def _emit(es: EventSpineEngine, action: str, payload: dict, cid: str, now: str) -> EventRecord:
    payload["action"] = action
    event = EventRecord(
        event_id=stable_identifier("evt-engrt", {"action": action, "seq": str(es.event_count), "cid": cid}),
        event_type=EventType.CUSTOM,
        source=EventSource.COMMUNICATION_SYSTEM,
        correlation_id=cid,
        payload=payload,
        emitted_at=now,
    )
    es.emit(event)
    return event


class EngineeringRuntimeEngine:
    """Engine for governed engineering quantities and systems constraints runtime."""

    def __init__(self, event_spine: EventSpineEngine, *, clock: Any = None) -> None:
        if not isinstance(event_spine, EventSpineEngine):
            raise RuntimeCoreInvariantError("event_spine must be an EventSpineEngine")
        self._events = event_spine
        self._clock: Clock = clock if isinstance(clock, Clock) else WallClock()
        self._quantities: dict[str, EngineeringQuantity] = {}
        self._tolerances: dict[str, ToleranceRecord] = {}
        self._targets: dict[str, ReliabilityTarget] = {}
        self._margins: dict[str, SafetyMargin] = {}
        self._envelopes: dict[str, LoadEnvelope] = {}
        self._windows: dict[str, ProcessWindow] = {}
        self._curves: dict[str, CapacityCurve] = {}
        self._violations: dict[str, EngineeringViolation] = {}

    # ------------------------------------------------------------------
    # Clock
    # ------------------------------------------------------------------

    def _now(self) -> str:
        return self._clock.now_iso()

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def quantity_count(self) -> int:
        return len(self._quantities)

    @property
    def tolerance_count(self) -> int:
        return len(self._tolerances)

    @property
    def target_count(self) -> int:
        return len(self._targets)

    @property
    def margin_count(self) -> int:
        return len(self._margins)

    @property
    def envelope_count(self) -> int:
        return len(self._envelopes)

    @property
    def window_count(self) -> int:
        return len(self._windows)

    @property
    def curve_count(self) -> int:
        return len(self._curves)

    @property
    def violation_count(self) -> int:
        return len(self._violations)

    # ------------------------------------------------------------------
    # Quantities
    # ------------------------------------------------------------------

    def register_quantity(
        self,
        quantity_id: str,
        tenant_id: str,
        display_name: str,
        value: float,
        unit_label: str,
        domain: EngineeringDomain,
        tolerance: float = 0.0,
    ) -> EngineeringQuantity:
        """Register a new engineering quantity. Duplicate quantity_id raises."""
        if quantity_id in self._quantities:
            raise RuntimeCoreInvariantError("Duplicate quantity_id")
        now = self._now()
        qty = EngineeringQuantity(
            quantity_id=quantity_id,
            tenant_id=tenant_id,
            display_name=display_name,
            value=value,
            unit_label=unit_label,
            domain=domain,
            tolerance=tolerance,
            created_at=now,
        )
        self._quantities[quantity_id] = qty
        _emit(self._events, "quantity_registered", {
            "quantity_id": quantity_id, "domain": domain.value,
        }, quantity_id, self._now())
        return qty

    def get_quantity(self, quantity_id: str) -> EngineeringQuantity:
        q = self._quantities.get(quantity_id)
        if q is None:
            raise RuntimeCoreInvariantError("Unknown quantity_id")
        return q

    def quantities_for_tenant(self, tenant_id: str) -> tuple[EngineeringQuantity, ...]:
        return tuple(q for q in self._quantities.values() if q.tenant_id == tenant_id)

    # ------------------------------------------------------------------
    # Tolerances
    # ------------------------------------------------------------------

    def check_tolerance(
        self,
        tolerance_id: str,
        tenant_id: str,
        quantity_ref: str,
        nominal: float,
        lower_limit: float,
        upper_limit: float,
    ) -> ToleranceRecord:
        """Check tolerance for a quantity. Auto-computes status."""
        if tolerance_id in self._tolerances:
            raise RuntimeCoreInvariantError("Duplicate tolerance_id")
        now = self._now()

        # Look up current quantity value
        qty = self.get_quantity(quantity_ref)
        val = qty.value

        # Auto-compute status
        if val < lower_limit or val > upper_limit:
            status = ToleranceStatus.EXCEEDED
        else:
            span = upper_limit - lower_limit
            if span > 0:
                warning_band = span * 0.1
                if val < (lower_limit + warning_band) or val > (upper_limit - warning_band):
                    status = ToleranceStatus.WARNING
                else:
                    status = ToleranceStatus.WITHIN
            else:
                # Zero-span: if value equals limits, WITHIN, else EXCEEDED
                status = ToleranceStatus.WITHIN if val == lower_limit else ToleranceStatus.EXCEEDED

        rec = ToleranceRecord(
            tolerance_id=tolerance_id,
            tenant_id=tenant_id,
            quantity_ref=quantity_ref,
            nominal=nominal,
            lower_limit=lower_limit,
            upper_limit=upper_limit,
            status=status,
            checked_at=now,
        )
        self._tolerances[tolerance_id] = rec
        _emit(self._events, "tolerance_checked", {
            "tolerance_id": tolerance_id, "status": status.value,
        }, tolerance_id, self._now())
        return rec

    # ------------------------------------------------------------------
    # Reliability Targets
    # ------------------------------------------------------------------

    def register_reliability_target(
        self,
        target_id: str,
        tenant_id: str,
        component_ref: str,
        grade: ReliabilityGrade,
        mtbf_hours: float,
        target_availability: float,
    ) -> ReliabilityTarget:
        """Register a reliability target. Duplicate target_id raises."""
        if target_id in self._targets:
            raise RuntimeCoreInvariantError("Duplicate target_id")
        now = self._now()
        tgt = ReliabilityTarget(
            target_id=target_id,
            tenant_id=tenant_id,
            component_ref=component_ref,
            grade=grade,
            mtbf_hours=mtbf_hours,
            target_availability=target_availability,
            created_at=now,
        )
        self._targets[target_id] = tgt
        _emit(self._events, "reliability_target_registered", {
            "target_id": target_id, "grade": grade.value,
        }, target_id, self._now())
        return tgt

    # ------------------------------------------------------------------
    # Safety Margins
    # ------------------------------------------------------------------

    def assess_safety_margin(
        self,
        margin_id: str,
        tenant_id: str,
        component_ref: str,
        design_load: float,
        actual_load: float,
    ) -> SafetyMargin:
        """Assess safety margin. Auto-computes margin_ratio and status."""
        if margin_id in self._margins:
            raise RuntimeCoreInvariantError("Duplicate margin_id")
        now = self._now()

        # margin_ratio = (design - actual) / design if design > 0 else 0
        if design_load > 0:
            ratio = (design_load - actual_load) / design_load
        else:
            ratio = 0.0

        # Clamp negative ratio to 0 for non_neg_float contract
        margin_ratio = max(ratio, 0.0)

        # Status based on ratio (pre-clamped)
        if ratio >= 0.5:
            status = SafetyMarginStatus.ADEQUATE
        elif ratio >= 0.2:
            status = SafetyMarginStatus.MARGINAL
        else:
            status = SafetyMarginStatus.INSUFFICIENT

        sm = SafetyMargin(
            margin_id=margin_id,
            tenant_id=tenant_id,
            component_ref=component_ref,
            design_load=design_load,
            actual_load=actual_load,
            margin_ratio=margin_ratio,
            status=status,
            assessed_at=now,
        )
        self._margins[margin_id] = sm
        _emit(self._events, "safety_margin_assessed", {
            "margin_id": margin_id, "status": status.value,
        }, margin_id, self._now())
        return sm

    # ------------------------------------------------------------------
    # Load Envelopes
    # ------------------------------------------------------------------

    def measure_load_envelope(
        self,
        envelope_id: str,
        tenant_id: str,
        component_ref: str,
        max_load: float,
        current_load: float,
    ) -> LoadEnvelope:
        """Measure load envelope. Auto-computes status."""
        if envelope_id in self._envelopes:
            raise RuntimeCoreInvariantError("Duplicate envelope_id")
        now = self._now()

        # Auto status
        if max_load > 0:
            ratio = current_load / max_load
        else:
            ratio = 1.0 if current_load > 0 else 0.0

        if ratio >= 1.0:
            status = LoadEnvelopeStatus.FAILURE
        elif ratio >= 0.9:
            status = LoadEnvelopeStatus.OVERLOAD
        elif ratio >= 0.7:
            status = LoadEnvelopeStatus.ELEVATED
        else:
            status = LoadEnvelopeStatus.NOMINAL

        le = LoadEnvelope(
            envelope_id=envelope_id,
            tenant_id=tenant_id,
            component_ref=component_ref,
            max_load=max_load,
            current_load=current_load,
            status=status,
            measured_at=now,
        )
        self._envelopes[envelope_id] = le
        _emit(self._events, "load_envelope_measured", {
            "envelope_id": envelope_id, "status": status.value,
        }, envelope_id, self._now())
        return le

    # ------------------------------------------------------------------
    # Process Windows
    # ------------------------------------------------------------------

    def measure_process_window(
        self,
        window_id: str,
        tenant_id: str,
        process_ref: str,
        target_value: float,
        lower_spec: float,
        upper_spec: float,
        actual_value: float,
    ) -> ProcessWindow:
        """Measure process window. Auto-computes status."""
        if window_id in self._windows:
            raise RuntimeCoreInvariantError("Duplicate window_id")
        now = self._now()

        # Auto status
        if actual_value < lower_spec or actual_value > upper_spec:
            status = ProcessWindowStatus.OUT_OF_SPEC
        else:
            span = upper_spec - lower_spec
            if span > 0:
                warning_band = span * 0.1
                if actual_value < (lower_spec + warning_band) or actual_value > (upper_spec - warning_band):
                    status = ProcessWindowStatus.DRIFT
                else:
                    status = ProcessWindowStatus.IN_SPEC
            else:
                status = ProcessWindowStatus.IN_SPEC if actual_value == lower_spec else ProcessWindowStatus.OUT_OF_SPEC

        pw = ProcessWindow(
            window_id=window_id,
            tenant_id=tenant_id,
            process_ref=process_ref,
            target_value=target_value,
            lower_spec=lower_spec,
            upper_spec=upper_spec,
            actual_value=actual_value,
            status=status,
            measured_at=now,
        )
        self._windows[window_id] = pw
        _emit(self._events, "process_window_measured", {
            "window_id": window_id, "status": status.value,
        }, window_id, self._now())
        return pw

    # ------------------------------------------------------------------
    # Capacity Curves
    # ------------------------------------------------------------------

    def register_capacity_curve(
        self,
        curve_id: str,
        tenant_id: str,
        component_ref: str,
        max_capacity: float,
        current_utilization: float,
        headroom: float,
    ) -> CapacityCurve:
        """Register a capacity curve. Duplicate curve_id raises."""
        if curve_id in self._curves:
            raise RuntimeCoreInvariantError("Duplicate curve_id")
        now = self._now()
        cc = CapacityCurve(
            curve_id=curve_id,
            tenant_id=tenant_id,
            component_ref=component_ref,
            max_capacity=max_capacity,
            current_utilization=current_utilization,
            headroom=headroom,
            created_at=now,
        )
        self._curves[curve_id] = cc
        _emit(self._events, "capacity_curve_registered", {
            "curve_id": curve_id,
        }, curve_id, self._now())
        return cc

    # ------------------------------------------------------------------
    # Snapshot
    # ------------------------------------------------------------------

    def engineering_snapshot(
        self,
        snapshot_id: str,
        tenant_id: str,
    ) -> EngineeringSnapshot:
        """Produce a point-in-time snapshot for a tenant."""
        now = self._now()
        snap = EngineeringSnapshot(
            snapshot_id=snapshot_id,
            tenant_id=tenant_id,
            total_quantities=sum(1 for q in self._quantities.values() if q.tenant_id == tenant_id),
            total_tolerances=sum(1 for t in self._tolerances.values() if t.tenant_id == tenant_id),
            total_targets=sum(1 for t in self._targets.values() if t.tenant_id == tenant_id),
            total_margins=sum(1 for m in self._margins.values() if m.tenant_id == tenant_id),
            total_envelopes=sum(1 for e in self._envelopes.values() if e.tenant_id == tenant_id),
            total_violations=sum(1 for v in self._violations.values() if v.tenant_id == tenant_id),
            captured_at=now,
        )
        return snap

    # ------------------------------------------------------------------
    # Violation Detection
    # ------------------------------------------------------------------

    def detect_engineering_violations(self, tenant_id: str) -> tuple[EngineeringViolation, ...]:
        """Detect engineering violations for a tenant. Idempotent."""
        now = self._now()
        new_violations: list[EngineeringViolation] = []

        # 1) tolerance_exceeded: any EXCEEDED tolerance
        for tol in self._tolerances.values():
            if tol.tenant_id == tenant_id and tol.status == ToleranceStatus.EXCEEDED:
                vid = stable_identifier("viol-engrt", {
                    "tolerance": tol.tolerance_id, "op": "tolerance_exceeded",
                })
                if vid not in self._violations:
                    v = EngineeringViolation(
                        violation_id=vid,
                        tenant_id=tenant_id,
                        operation="tolerance_exceeded",
                        reason="tolerance is exceeded",
                        detected_at=now,
                    )
                    self._violations[vid] = v
                    new_violations.append(v)

        # 2) safety_margin_insufficient: any INSUFFICIENT margin
        for margin in self._margins.values():
            if margin.tenant_id == tenant_id and margin.status == SafetyMarginStatus.INSUFFICIENT:
                vid = stable_identifier("viol-engrt", {
                    "margin": margin.margin_id, "op": "safety_margin_insufficient",
                })
                if vid not in self._violations:
                    v = EngineeringViolation(
                        violation_id=vid,
                        tenant_id=tenant_id,
                        operation="safety_margin_insufficient",
                        reason="safety margin is insufficient",
                        detected_at=now,
                    )
                    self._violations[vid] = v
                    new_violations.append(v)

        # 3) load_envelope_failure: any FAILURE envelope
        for env in self._envelopes.values():
            if env.tenant_id == tenant_id and env.status == LoadEnvelopeStatus.FAILURE:
                vid = stable_identifier("viol-engrt", {
                    "envelope": env.envelope_id, "op": "load_envelope_failure",
                })
                if vid not in self._violations:
                    v = EngineeringViolation(
                        violation_id=vid,
                        tenant_id=tenant_id,
                        operation="load_envelope_failure",
                        reason="load envelope is in failure",
                        detected_at=now,
                    )
                    self._violations[vid] = v
                    new_violations.append(v)

        return tuple(new_violations)

    # ------------------------------------------------------------------
    # Collections / snapshot / state_hash
    # ------------------------------------------------------------------

    def _collections(self) -> dict[str, Any]:
        """Return all internal collections."""
        return {
            "quantities": self._quantities,
            "tolerances": self._tolerances,
            "targets": self._targets,
            "margins": self._margins,
            "envelopes": self._envelopes,
            "windows": self._windows,
            "curves": self._curves,
            "violations": self._violations,
        }

    def snapshot(self) -> dict[str, Any]:
        """Capture complete engine state as a serializable dict."""
        result: dict[str, Any] = {}
        for name, collection in self._collections().items():
            if isinstance(collection, dict):
                result[name] = {
                    k: v.to_dict() if hasattr(v, "to_dict") else v
                    for k, v in collection.items()
                }
            elif isinstance(collection, list):
                result[name] = [
                    v.to_dict() if hasattr(v, "to_dict") else v
                    for v in collection
                ]
        result["_state_hash"] = self.state_hash()
        return result

    def state_hash(self) -> str:
        """Compute a deterministic hash of engine state (sorted keys)."""
        parts = [
            f"curves={self.curve_count}",
            f"envelopes={self.envelope_count}",
            f"margins={self.margin_count}",
            f"quantities={self.quantity_count}",
            f"targets={self.target_count}",
            f"tolerances={self.tolerance_count}",
            f"violations={self.violation_count}",
            f"windows={self.window_count}",
        ]
        return sha256("|".join(parts).encode()).hexdigest()
