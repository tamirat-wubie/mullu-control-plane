"""Purpose: 3D / digital twin runtime engine.
Governance scope: managing digital twin models, objects, assemblies, state records,
    telemetry bindings, sync records, violations, assessments, snapshots,
    and closure reports.
Dependencies: digital_twin_runtime contracts, event_spine, core invariants.
Invariants:
  - Model must exist before registering objects.
  - Both parent and child objects must exist before registering assemblies.
  - Object state updates propagate to the object record.
  - Every mutation emits an event.
  - All returns are immutable.
  - Clock is injected for deterministic timestamps.
"""

from __future__ import annotations

from hashlib import sha256
from typing import Any

from mcoi_runtime.core.engine_protocol import Clock, WallClock

from ..contracts.digital_twin_runtime import (
    TwinAssembly,
    TwinAssessment,
    TwinClosureReport,
    TwinModel,
    TwinObject,
    TwinObjectKind,
    TwinSnapshot,
    TwinStateDisposition,
    TwinStateRecord,
    TwinStatus,
    TwinSyncRecord,
    TwinSyncStatus,
    TwinTelemetryBinding,
    TwinViolation,
)
from ..contracts.event import EventRecord, EventSource, EventType
from .event_spine import EventSpineEngine
from .invariants import RuntimeCoreInvariantError, stable_identifier


def _emit(es: EventSpineEngine, action: str, payload: dict, cid: str, now: str) -> EventRecord:
    payload["action"] = action
    event = EventRecord(
        event_id=stable_identifier("evt-dtrt", {"action": action, "seq": str(es.event_count), "cid": cid}),
        event_type=EventType.CUSTOM,
        source=EventSource.COMMUNICATION_SYSTEM,
        correlation_id=cid,
        payload=payload,
        emitted_at=now,
    )
    es.emit(event)
    return event


class DigitalTwinRuntimeEngine:
    """Engine for governed digital twin runtime."""

    def __init__(self, event_spine: EventSpineEngine, *, clock: Any = None) -> None:
        if not isinstance(event_spine, EventSpineEngine):
            raise RuntimeCoreInvariantError("event_spine must be an EventSpineEngine")
        self._events = event_spine
        self._clock: Clock = clock if isinstance(clock, Clock) else WallClock()
        self._models: dict[str, TwinModel] = {}
        self._objects: dict[str, TwinObject] = {}
        self._assemblies: dict[str, TwinAssembly] = {}
        self._states: dict[str, TwinStateRecord] = {}
        self._bindings: dict[str, TwinTelemetryBinding] = {}
        self._syncs: dict[str, TwinSyncRecord] = {}
        self._violations: dict[str, TwinViolation] = {}

    # ------------------------------------------------------------------
    # Clock
    # ------------------------------------------------------------------

    def _now(self) -> str:
        return self._clock.now_iso()

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def model_count(self) -> int:
        return len(self._models)

    @property
    def object_count(self) -> int:
        return len(self._objects)

    @property
    def assembly_count(self) -> int:
        return len(self._assemblies)

    @property
    def state_count(self) -> int:
        return len(self._states)

    @property
    def binding_count(self) -> int:
        return len(self._bindings)

    @property
    def sync_count(self) -> int:
        return len(self._syncs)

    @property
    def violation_count(self) -> int:
        return len(self._violations)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_model(self, model_id: str) -> TwinModel:
        m = self._models.get(model_id)
        if m is None:
            raise RuntimeCoreInvariantError("Unknown model_id")
        return m

    def _get_object(self, object_id: str) -> TwinObject:
        o = self._objects.get(object_id)
        if o is None:
            raise RuntimeCoreInvariantError("Unknown object_id")
        return o

    def _replace_model(self, model_id: str, **kwargs: Any) -> TwinModel:
        old = self._get_model(model_id)
        fields = {
            "model_id": old.model_id,
            "tenant_id": old.tenant_id,
            "display_name": old.display_name,
            "status": old.status,
            "object_count": old.object_count,
            "created_at": old.created_at,
            "metadata": old.metadata,
        }
        fields.update(kwargs)
        updated = TwinModel(**fields)
        self._models[model_id] = updated
        return updated

    def _replace_object(self, object_id: str, **kwargs: Any) -> TwinObject:
        old = self._get_object(object_id)
        fields = {
            "object_id": old.object_id,
            "tenant_id": old.tenant_id,
            "model_ref": old.model_ref,
            "kind": old.kind,
            "display_name": old.display_name,
            "parent_ref": old.parent_ref,
            "state": old.state,
            "created_at": old.created_at,
            "metadata": old.metadata,
        }
        fields.update(kwargs)
        updated = TwinObject(**fields)
        self._objects[object_id] = updated
        return updated

    def _compute_depth(self, parent_object_ref: str) -> int:
        """Compute depth from parent chain of assemblies."""
        depth = 0
        current = parent_object_ref
        visited: set[str] = set()
        while current in visited is False or True:
            # Find assembly where child is current
            found = False
            for asm in self._assemblies.values():
                if asm.child_object_ref == current:
                    depth += 1
                    if current in visited:
                        break
                    visited.add(current)
                    current = asm.parent_object_ref
                    found = True
                    break
            if not found:
                break
        return depth

    # ------------------------------------------------------------------
    # Twin Models
    # ------------------------------------------------------------------

    def register_twin_model(
        self,
        model_id: str,
        tenant_id: str,
        display_name: str,
    ) -> TwinModel:
        """Register a new digital twin model."""
        if model_id in self._models:
            raise RuntimeCoreInvariantError("Duplicate model_id")
        now = self._now()
        model = TwinModel(
            model_id=model_id,
            tenant_id=tenant_id,
            display_name=display_name,
            status=TwinStatus.ACTIVE,
            object_count=0,
            created_at=now,
        )
        self._models[model_id] = model
        _emit(self._events, "twin_model_registered", {
            "model_id": model_id,
        }, model_id, self._now())
        return model

    # ------------------------------------------------------------------
    # Twin Objects
    # ------------------------------------------------------------------

    def register_twin_object(
        self,
        object_id: str,
        tenant_id: str,
        model_ref: str,
        kind: TwinObjectKind,
        display_name: str,
        parent_ref: str = "root",
    ) -> TwinObject:
        """Register a new twin object. Validates model exists, increments object_count."""
        if object_id in self._objects:
            raise RuntimeCoreInvariantError("Duplicate object_id")
        self._get_model(model_ref)  # validates existence
        now = self._now()
        obj = TwinObject(
            object_id=object_id,
            tenant_id=tenant_id,
            model_ref=model_ref,
            kind=kind,
            display_name=display_name,
            parent_ref=parent_ref,
            state=TwinStateDisposition.NOMINAL,
            created_at=now,
        )
        self._objects[object_id] = obj
        # Increment model object_count
        model = self._get_model(model_ref)
        self._replace_model(model_ref, object_count=model.object_count + 1)
        _emit(self._events, "twin_object_registered", {
            "object_id": object_id, "model_ref": model_ref, "kind": kind.value,
        }, object_id, self._now())
        return obj

    # ------------------------------------------------------------------
    # Twin Assemblies
    # ------------------------------------------------------------------

    def register_twin_assembly(
        self,
        assembly_id: str,
        tenant_id: str,
        parent_object_ref: str,
        child_object_ref: str,
    ) -> TwinAssembly:
        """Register an assembly between two objects. Validates both exist."""
        if assembly_id in self._assemblies:
            raise RuntimeCoreInvariantError("Duplicate assembly_id")
        self._get_object(parent_object_ref)
        self._get_object(child_object_ref)
        depth = self._compute_depth(parent_object_ref) + 1
        now = self._now()
        asm = TwinAssembly(
            assembly_id=assembly_id,
            tenant_id=tenant_id,
            parent_object_ref=parent_object_ref,
            child_object_ref=child_object_ref,
            depth=depth,
            created_at=now,
        )
        self._assemblies[assembly_id] = asm
        _emit(self._events, "twin_assembly_registered", {
            "assembly_id": assembly_id, "depth": depth,
        }, assembly_id, self._now())
        return asm

    # ------------------------------------------------------------------
    # State Binding
    # ------------------------------------------------------------------

    def bind_runtime_state(
        self,
        state_id: str,
        tenant_id: str,
        object_ref: str,
        disposition: TwinStateDisposition,
        source_runtime: str,
    ) -> TwinStateRecord:
        """Bind a runtime state to a twin object. Updates object state."""
        if state_id in self._states:
            raise RuntimeCoreInvariantError("Duplicate state_id")
        self._get_object(object_ref)  # validates existence
        now = self._now()
        rec = TwinStateRecord(
            state_id=state_id,
            tenant_id=tenant_id,
            object_ref=object_ref,
            disposition=disposition,
            source_runtime=source_runtime,
            updated_at=now,
        )
        self._states[state_id] = rec
        # Update object state
        self._replace_object(object_ref, state=disposition)
        _emit(self._events, "runtime_state_bound", {
            "state_id": state_id, "object_ref": object_ref, "disposition": disposition.value,
        }, state_id, self._now())
        return rec

    def update_twin_state(
        self,
        object_id: str,
        new_disposition: TwinStateDisposition,
    ) -> TwinObject:
        """Update the state of a twin object."""
        self._get_object(object_id)
        updated = self._replace_object(object_id, state=new_disposition)
        _emit(self._events, "twin_state_updated", {
            "object_id": object_id, "disposition": new_disposition.value,
        }, object_id, self._now())
        return updated

    # ------------------------------------------------------------------
    # Telemetry Binding
    # ------------------------------------------------------------------

    def bind_telemetry(
        self,
        binding_id: str,
        tenant_id: str,
        object_ref: str,
        telemetry_ref: str,
        source_runtime: str,
    ) -> TwinTelemetryBinding:
        """Bind a telemetry source to a twin object."""
        if binding_id in self._bindings:
            raise RuntimeCoreInvariantError("Duplicate binding_id")
        now = self._now()
        binding = TwinTelemetryBinding(
            binding_id=binding_id,
            tenant_id=tenant_id,
            object_ref=object_ref,
            telemetry_ref=telemetry_ref,
            source_runtime=source_runtime,
            bound_at=now,
        )
        self._bindings[binding_id] = binding
        _emit(self._events, "telemetry_bound", {
            "binding_id": binding_id, "object_ref": object_ref,
        }, binding_id, self._now())
        return binding

    # ------------------------------------------------------------------
    # Sync Records
    # ------------------------------------------------------------------

    def record_sync(
        self,
        sync_id: str,
        tenant_id: str,
        object_ref: str,
        status: TwinSyncStatus = TwinSyncStatus.SYNCED,
    ) -> TwinSyncRecord:
        """Record a sync event for a twin object."""
        if sync_id in self._syncs:
            raise RuntimeCoreInvariantError("Duplicate sync_id")
        now = self._now()
        rec = TwinSyncRecord(
            sync_id=sync_id,
            tenant_id=tenant_id,
            object_ref=object_ref,
            status=status,
            last_synced_at=now,
        )
        self._syncs[sync_id] = rec
        _emit(self._events, "sync_recorded", {
            "sync_id": sync_id, "object_ref": object_ref, "status": status.value,
        }, sync_id, self._now())
        return rec

    # ------------------------------------------------------------------
    # Assessment
    # ------------------------------------------------------------------

    def assess_twin_health(
        self,
        assessment_id: str,
        tenant_id: str,
    ) -> TwinAssessment:
        """Assess twin health. health_score = nominal / total_objects or 1.0."""
        now = self._now()
        tenant_objects = [o for o in self._objects.values() if o.tenant_id == tenant_id]
        total = len(tenant_objects)
        nominal = sum(1 for o in tenant_objects if o.state == TwinStateDisposition.NOMINAL)
        degraded = sum(1 for o in tenant_objects if o.state in (
            TwinStateDisposition.DEGRADED, TwinStateDisposition.CRITICAL,
        ))
        score = nominal / total if total > 0 else 1.0
        asm = TwinAssessment(
            assessment_id=assessment_id,
            tenant_id=tenant_id,
            total_objects=total,
            total_nominal=nominal,
            total_degraded=degraded,
            health_score=score,
            assessed_at=now,
        )
        _emit(self._events, "twin_assessed", {
            "assessment_id": assessment_id, "health_score": score,
        }, assessment_id, self._now())
        return asm

    # ------------------------------------------------------------------
    # Snapshot
    # ------------------------------------------------------------------

    def twin_snapshot(
        self,
        snapshot_id: str,
        tenant_id: str,
    ) -> TwinSnapshot:
        """Produce a point-in-time snapshot for a tenant."""
        now = self._now()
        snap = TwinSnapshot(
            snapshot_id=snapshot_id,
            tenant_id=tenant_id,
            total_models=sum(1 for m in self._models.values() if m.tenant_id == tenant_id),
            total_objects=sum(1 for o in self._objects.values() if o.tenant_id == tenant_id),
            total_assemblies=sum(1 for a in self._assemblies.values() if a.tenant_id == tenant_id),
            total_states=sum(1 for s in self._states.values() if s.tenant_id == tenant_id),
            total_bindings=sum(1 for b in self._bindings.values() if b.tenant_id == tenant_id),
            total_violations=sum(1 for v in self._violations.values() if v.tenant_id == tenant_id),
            captured_at=now,
        )
        return snap

    # ------------------------------------------------------------------
    # Closure Report
    # ------------------------------------------------------------------

    def twin_closure_report(
        self,
        report_id: str,
        tenant_id: str,
    ) -> TwinClosureReport:
        """Produce a closure report for a tenant."""
        now = self._now()
        report = TwinClosureReport(
            report_id=report_id,
            tenant_id=tenant_id,
            total_models=sum(1 for m in self._models.values() if m.tenant_id == tenant_id),
            total_objects=sum(1 for o in self._objects.values() if o.tenant_id == tenant_id),
            total_assemblies=sum(1 for a in self._assemblies.values() if a.tenant_id == tenant_id),
            total_states=sum(1 for s in self._states.values() if s.tenant_id == tenant_id),
            total_violations=sum(1 for v in self._violations.values() if v.tenant_id == tenant_id),
            created_at=now,
        )
        return report

    # ------------------------------------------------------------------
    # Violation Detection
    # ------------------------------------------------------------------

    def detect_twin_violations(self, tenant_id: str) -> tuple[TwinViolation, ...]:
        """Detect twin violations for a tenant. Idempotent."""
        now = self._now()
        new_violations: list[TwinViolation] = []

        tenant_objects = [o for o in self._objects.values() if o.tenant_id == tenant_id]
        tenant_syncs = [s for s in self._syncs.values() if s.tenant_id == tenant_id]

        # 1) stale_sync: sync records with STALE or DIVERGED status
        for sync in tenant_syncs:
            if sync.status in (TwinSyncStatus.STALE, TwinSyncStatus.DIVERGED):
                vid = stable_identifier("viol-dtrt", {
                    "sync": sync.sync_id, "op": "stale_sync",
                })
                if vid not in self._violations:
                    v = TwinViolation(
                        violation_id=vid,
                        tenant_id=tenant_id,
                        operation="stale_sync",
                        reason="sync has non-nominal status",
                        detected_at=now,
                    )
                    self._violations[vid] = v
                    new_violations.append(v)

        # 2) missing_assembly: object with parent_ref != "root" but no assembly
        child_refs = {a.child_object_ref for a in self._assemblies.values()}
        for obj in tenant_objects:
            if obj.parent_ref != "root" and obj.object_id not in child_refs:
                vid = stable_identifier("viol-dtrt", {
                    "object": obj.object_id, "op": "missing_assembly",
                })
                if vid not in self._violations:
                    v = TwinViolation(
                        violation_id=vid,
                        tenant_id=tenant_id,
                        operation="missing_assembly",
                        reason="object missing assembly record",
                        detected_at=now,
                    )
                    self._violations[vid] = v
                    new_violations.append(v)

        # 3) degraded_no_state: object DEGRADED but no TwinStateRecord
        state_object_refs = {s.object_ref for s in self._states.values()}
        for obj in tenant_objects:
            if obj.state == TwinStateDisposition.DEGRADED and obj.object_id not in state_object_refs:
                vid = stable_identifier("viol-dtrt", {
                    "object": obj.object_id, "op": "degraded_no_state",
                })
                if vid not in self._violations:
                    v = TwinViolation(
                        violation_id=vid,
                        tenant_id=tenant_id,
                        operation="degraded_no_state",
                        reason="degraded object missing state record",
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
            "assemblies": self._assemblies,
            "bindings": self._bindings,
            "models": self._models,
            "objects": self._objects,
            "states": self._states,
            "syncs": self._syncs,
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
        """Compute a deterministic hash of engine state (sorted keys, full 64-char)."""
        parts = [
            f"assemblies={self.assembly_count}",
            f"bindings={self.binding_count}",
            f"models={self.model_count}",
            f"objects={self.object_count}",
            f"states={self.state_count}",
            f"syncs={self.sync_count}",
            f"violations={self.violation_count}",
        ]
        return sha256("|".join(parts).encode()).hexdigest()
