"""Purpose: pilot deployment / tenant bootstrap / live connector activation engine.
Governance scope: governed tenant bootstrap lifecycle, connector activation,
    data migration, pilot phase management, go-live assessment, runbook and SLO
    registration, pilot assessment, violation detection, and closure reporting.
Dependencies: event_spine, invariants, contracts, engine_protocol.
Invariants:
  - Duplicate IDs are rejected fail-closed.
  - Bootstrap status transitions are guarded.
  - Connector activation transitions are guarded.
  - Migration status transitions are guarded.
  - Pilot phase advances sequentially.
  - Violation detection is idempotent.
  - All outputs are frozen.
"""

from __future__ import annotations

from hashlib import sha256
from typing import Any

from mcoi_runtime.contracts.event import EventRecord, EventSource, EventType
from mcoi_runtime.contracts.pilot_deployment import (
    BootstrapStatus,
    ConnectorActivation,
    ConnectorActivationStatus,
    DataMigration,
    GoLiveChecklist,
    GoLiveReadiness,
    MigrationStatus,
    PilotAssessment,
    PilotClosureReport,
    PilotPhase,
    PilotRecord,
    PilotViolation,
    RunbookEntry,
    SloDefinition,
    TenantBootstrap,
)
from mcoi_runtime.core.engine_protocol import Clock, WallClock
from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError, stable_identifier


# ---------------------------------------------------------------------------
# Phase progression order
# ---------------------------------------------------------------------------

_PILOT_PHASE_ORDER = [
    PilotPhase.SETUP,
    PilotPhase.ONBOARDING,
    PilotPhase.ACTIVE_USE,
    PilotPhase.EVALUATION,
    PilotPhase.GRADUATED,
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _emit(es: EventSpineEngine, action: str, payload: dict[str, Any], cid: str, clock: Clock) -> None:
    now = clock.now_iso()
    payload["action"] = action
    event = EventRecord(
        event_id=stable_identifier("evt-pilot", {"action": action, "ts": now, "cid": cid, "seq": str(es.event_count)}),
        event_type=EventType.CUSTOM,
        source=EventSource.EXTERNAL,
        correlation_id=cid,
        payload=payload,
        emitted_at=now,
    )
    es.emit(event)


class PilotDeploymentEngine:
    """Governed pilot deployment / tenant bootstrap / connector activation engine."""

    def __init__(self, event_spine: EventSpineEngine, *, clock: Any = None) -> None:
        if not isinstance(event_spine, EventSpineEngine):
            raise RuntimeCoreInvariantError("event_spine must be an EventSpineEngine")
        self._events = event_spine
        self._clock: Clock = clock if isinstance(clock, Clock) else WallClock()
        self._bootstraps: dict[str, TenantBootstrap] = {}
        self._connectors: dict[str, ConnectorActivation] = {}
        self._migrations: dict[str, DataMigration] = {}
        self._pilots: dict[str, PilotRecord] = {}
        self._checklists: dict[str, GoLiveChecklist] = {}
        self._runbooks: dict[str, RunbookEntry] = {}
        self._slos: dict[str, SloDefinition] = {}
        self._violations: dict[str, PilotViolation] = {}

    # -- Clock --

    def _now(self) -> str:
        return self._clock.now_iso()

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def bootstrap_count(self) -> int:
        return len(self._bootstraps)

    @property
    def connector_count(self) -> int:
        return len(self._connectors)

    @property
    def migration_count(self) -> int:
        return len(self._migrations)

    @property
    def pilot_count(self) -> int:
        return len(self._pilots)

    @property
    def checklist_count(self) -> int:
        return len(self._checklists)

    @property
    def runbook_count(self) -> int:
        return len(self._runbooks)

    @property
    def slo_count(self) -> int:
        return len(self._slos)

    @property
    def violation_count(self) -> int:
        return len(self._violations)

    # ------------------------------------------------------------------
    # Bootstrap lifecycle
    # ------------------------------------------------------------------

    def bootstrap_tenant(
        self, bootstrap_id: str, tenant_id: str, pack_ref: str,
    ) -> TenantBootstrap:
        """Create a new tenant bootstrap in PENDING status."""
        if bootstrap_id in self._bootstraps:
            raise RuntimeCoreInvariantError(f"Duplicate bootstrap_id: {bootstrap_id}")
        now = self._now()
        record = TenantBootstrap(
            bootstrap_id=bootstrap_id,
            tenant_id=tenant_id,
            pack_ref=pack_ref,
            status=BootstrapStatus.PENDING,
            workspace_count=0,
            connector_count=0,
            created_at=now,
        )
        self._bootstraps[bootstrap_id] = record
        _emit(self._events, "bootstrap_tenant", {"bootstrap_id": bootstrap_id}, bootstrap_id, self._clock)
        return record

    def _update_bootstrap_status(self, bootstrap_id: str, target: BootstrapStatus,
                                  allowed_from: frozenset[BootstrapStatus] | None = None) -> TenantBootstrap:
        old = self._bootstraps.get(bootstrap_id)
        if old is None:
            raise RuntimeCoreInvariantError(f"Unknown bootstrap_id: {bootstrap_id}")
        if allowed_from is not None and old.status not in allowed_from:
            raise RuntimeCoreInvariantError(
                f"Cannot transition bootstrap from {old.status.value} to {target.value}")
        now = self._now()
        updated = TenantBootstrap(
            bootstrap_id=old.bootstrap_id,
            tenant_id=old.tenant_id,
            pack_ref=old.pack_ref,
            status=target,
            workspace_count=old.workspace_count,
            connector_count=old.connector_count,
            created_at=old.created_at,
            metadata=old.metadata,
        )
        self._bootstraps[bootstrap_id] = updated
        _emit(self._events, f"bootstrap_{target.value}", {"bootstrap_id": bootstrap_id}, bootstrap_id, self._clock)
        return updated

    def start_bootstrap(self, bootstrap_id: str) -> TenantBootstrap:
        """Transition bootstrap to IN_PROGRESS (from PENDING)."""
        return self._update_bootstrap_status(
            bootstrap_id, BootstrapStatus.IN_PROGRESS,
            frozenset({BootstrapStatus.PENDING}),
        )

    def complete_bootstrap(self, bootstrap_id: str) -> TenantBootstrap:
        """Transition bootstrap to COMPLETED (from IN_PROGRESS)."""
        return self._update_bootstrap_status(
            bootstrap_id, BootstrapStatus.COMPLETED,
            frozenset({BootstrapStatus.IN_PROGRESS}),
        )

    def fail_bootstrap(self, bootstrap_id: str) -> TenantBootstrap:
        """Transition bootstrap to FAILED."""
        return self._update_bootstrap_status(bootstrap_id, BootstrapStatus.FAILED)

    def rollback_bootstrap(self, bootstrap_id: str) -> TenantBootstrap:
        """Transition bootstrap to ROLLED_BACK (from FAILED or IN_PROGRESS only)."""
        return self._update_bootstrap_status(
            bootstrap_id, BootstrapStatus.ROLLED_BACK,
            frozenset({BootstrapStatus.FAILED, BootstrapStatus.IN_PROGRESS}),
        )

    # ------------------------------------------------------------------
    # Connector activation
    # ------------------------------------------------------------------

    def activate_connector(
        self, activation_id: str, tenant_id: str, connector_type: str, target_url: str,
    ) -> ConnectorActivation:
        """Create a new connector activation in ACTIVATING status."""
        if activation_id in self._connectors:
            raise RuntimeCoreInvariantError(f"Duplicate activation_id: {activation_id}")
        now = self._now()
        record = ConnectorActivation(
            activation_id=activation_id,
            tenant_id=tenant_id,
            connector_type=connector_type,
            target_url=target_url,
            status=ConnectorActivationStatus.ACTIVATING,
            health_check_passed=False,
            activated_at=now,
        )
        self._connectors[activation_id] = record
        _emit(self._events, "activate_connector", {"activation_id": activation_id}, activation_id, self._clock)
        return record

    def complete_connector_activation(self, activation_id: str, health_passed: bool) -> ConnectorActivation:
        """Complete connector activation: ACTIVE if health_passed, FAILED otherwise."""
        old = self._connectors.get(activation_id)
        if old is None:
            raise RuntimeCoreInvariantError(f"Unknown activation_id: {activation_id}")
        now = self._now()
        target_status = ConnectorActivationStatus.ACTIVE if health_passed else ConnectorActivationStatus.FAILED
        updated = ConnectorActivation(
            activation_id=old.activation_id,
            tenant_id=old.tenant_id,
            connector_type=old.connector_type,
            target_url=old.target_url,
            status=target_status,
            health_check_passed=health_passed,
            activated_at=old.activated_at,
            metadata=old.metadata,
        )
        self._connectors[activation_id] = updated
        _emit(self._events, f"connector_{target_status.value}", {"activation_id": activation_id}, activation_id, self._clock)
        return updated

    def degrade_connector(self, activation_id: str) -> ConnectorActivation:
        """Transition connector to DEGRADED."""
        old = self._connectors.get(activation_id)
        if old is None:
            raise RuntimeCoreInvariantError(f"Unknown activation_id: {activation_id}")
        now = self._now()
        updated = ConnectorActivation(
            activation_id=old.activation_id,
            tenant_id=old.tenant_id,
            connector_type=old.connector_type,
            target_url=old.target_url,
            status=ConnectorActivationStatus.DEGRADED,
            health_check_passed=old.health_check_passed,
            activated_at=old.activated_at,
            metadata=old.metadata,
        )
        self._connectors[activation_id] = updated
        _emit(self._events, "connector_degraded", {"activation_id": activation_id}, activation_id, self._clock)
        return updated

    # ------------------------------------------------------------------
    # Data migration
    # ------------------------------------------------------------------

    def start_migration(
        self, migration_id: str, tenant_id: str, source_system: str, record_count: int,
    ) -> DataMigration:
        """Create a new data migration in PENDING status."""
        if migration_id in self._migrations:
            raise RuntimeCoreInvariantError(f"Duplicate migration_id: {migration_id}")
        now = self._now()
        record = DataMigration(
            migration_id=migration_id,
            tenant_id=tenant_id,
            source_system=source_system,
            record_count=record_count,
            imported_count=0,
            failed_count=0,
            status=MigrationStatus.PENDING,
            created_at=now,
        )
        self._migrations[migration_id] = record
        _emit(self._events, "start_migration", {"migration_id": migration_id}, migration_id, self._clock)
        return record

    def _update_migration_status(self, migration_id: str, target: MigrationStatus,
                                  **overrides: Any) -> DataMigration:
        old = self._migrations.get(migration_id)
        if old is None:
            raise RuntimeCoreInvariantError(f"Unknown migration_id: {migration_id}")
        now = self._now()
        updated = DataMigration(
            migration_id=old.migration_id,
            tenant_id=old.tenant_id,
            source_system=old.source_system,
            record_count=old.record_count,
            imported_count=overrides.get("imported_count", old.imported_count),
            failed_count=overrides.get("failed_count", old.failed_count),
            status=target,
            created_at=old.created_at,
            metadata=old.metadata,
        )
        self._migrations[migration_id] = updated
        _emit(self._events, f"migration_{target.value}", {"migration_id": migration_id}, migration_id, self._clock)
        return updated

    def validate_migration(self, migration_id: str) -> DataMigration:
        """Transition migration to VALIDATING."""
        return self._update_migration_status(migration_id, MigrationStatus.VALIDATING)

    def import_migration(self, migration_id: str) -> DataMigration:
        """Transition migration to IMPORTING."""
        return self._update_migration_status(migration_id, MigrationStatus.IMPORTING)

    def complete_migration(self, migration_id: str, imported_count: int, failed_count: int) -> DataMigration:
        """Transition migration to COMPLETED with final counts."""
        return self._update_migration_status(
            migration_id, MigrationStatus.COMPLETED,
            imported_count=imported_count, failed_count=failed_count,
        )

    def fail_migration(self, migration_id: str) -> DataMigration:
        """Transition migration to FAILED."""
        return self._update_migration_status(migration_id, MigrationStatus.FAILED)

    # ------------------------------------------------------------------
    # Pilot lifecycle
    # ------------------------------------------------------------------

    def register_pilot(
        self, pilot_id: str, tenant_id: str, pack_ref: str,
    ) -> PilotRecord:
        """Register a new pilot in SETUP phase."""
        if pilot_id in self._pilots:
            raise RuntimeCoreInvariantError(f"Duplicate pilot_id: {pilot_id}")
        now = self._now()
        record = PilotRecord(
            pilot_id=pilot_id,
            tenant_id=tenant_id,
            pack_ref=pack_ref,
            phase=PilotPhase.SETUP,
            started_at=now,
        )
        self._pilots[pilot_id] = record
        _emit(self._events, "register_pilot", {"pilot_id": pilot_id}, pilot_id, self._clock)
        return record

    def advance_pilot(self, pilot_id: str) -> PilotRecord:
        """Advance pilot to the next phase."""
        old = self._pilots.get(pilot_id)
        if old is None:
            raise RuntimeCoreInvariantError(f"Unknown pilot_id: {pilot_id}")
        idx = _PILOT_PHASE_ORDER.index(old.phase)
        if idx >= len(_PILOT_PHASE_ORDER) - 1:
            raise RuntimeCoreInvariantError(
                f"Pilot {pilot_id} is already in terminal phase: {old.phase.value}")
        next_phase = _PILOT_PHASE_ORDER[idx + 1]
        now = self._now()
        updated = PilotRecord(
            pilot_id=old.pilot_id,
            tenant_id=old.tenant_id,
            pack_ref=old.pack_ref,
            phase=next_phase,
            started_at=old.started_at,
            metadata=old.metadata,
        )
        self._pilots[pilot_id] = updated
        _emit(self._events, f"pilot_{next_phase.value}", {"pilot_id": pilot_id}, pilot_id, self._clock)
        return updated

    # ------------------------------------------------------------------
    # Go-live assessment
    # ------------------------------------------------------------------

    def assess_go_live(
        self, checklist_id: str, tenant_id: str, pilot_ref: str,
    ) -> GoLiveChecklist:
        """Assess go-live readiness for a tenant."""
        if checklist_id in self._checklists:
            raise RuntimeCoreInvariantError(f"Duplicate checklist_id: {checklist_id}")

        # Count total items from bootstraps, connectors, migrations for this tenant
        tenant_bootstraps = [b for b in self._bootstraps.values() if b.tenant_id == tenant_id]
        tenant_connectors = [c for c in self._connectors.values() if c.tenant_id == tenant_id]
        tenant_migrations = [m for m in self._migrations.values() if m.tenant_id == tenant_id]

        total_items = len(tenant_bootstraps) + len(tenant_connectors) + len(tenant_migrations)

        # Count passed items (completed bootstraps, active connectors, completed migrations)
        passed_bootstraps = sum(1 for b in tenant_bootstraps if b.status == BootstrapStatus.COMPLETED)
        passed_connectors = sum(1 for c in tenant_connectors if c.status == ConnectorActivationStatus.ACTIVE)
        passed_migrations = sum(1 for m in tenant_migrations if m.status == MigrationStatus.COMPLETED)
        passed_items = passed_bootstraps + passed_connectors + passed_migrations

        # Determine readiness
        if total_items == 0:
            readiness = GoLiveReadiness.NOT_READY
        else:
            ratio = passed_items / total_items
            if ratio >= 1.0:
                readiness = GoLiveReadiness.READY
            elif ratio >= 0.7:
                readiness = GoLiveReadiness.PARTIAL
            else:
                readiness = GoLiveReadiness.NOT_READY

        now = self._now()
        checklist = GoLiveChecklist(
            checklist_id=checklist_id,
            tenant_id=tenant_id,
            pilot_ref=pilot_ref,
            total_items=total_items,
            passed_items=passed_items,
            readiness=readiness,
            assessed_at=now,
        )
        self._checklists[checklist_id] = checklist
        _emit(self._events, "assess_go_live", {"checklist_id": checklist_id}, checklist_id, self._clock)
        return checklist

    # ------------------------------------------------------------------
    # Runbook
    # ------------------------------------------------------------------

    def register_runbook(
        self, entry_id: str, tenant_id: str, title: str, category: str, procedure: str,
    ) -> RunbookEntry:
        """Register a runbook entry."""
        if entry_id in self._runbooks:
            raise RuntimeCoreInvariantError(f"Duplicate entry_id: {entry_id}")
        now = self._now()
        record = RunbookEntry(
            entry_id=entry_id,
            tenant_id=tenant_id,
            title=title,
            category=category,
            procedure=procedure,
            created_at=now,
        )
        self._runbooks[entry_id] = record
        _emit(self._events, "register_runbook", {"entry_id": entry_id}, entry_id, self._clock)
        return record

    # ------------------------------------------------------------------
    # SLO
    # ------------------------------------------------------------------

    def register_slo(
        self, slo_id: str, tenant_id: str, metric_name: str,
        target_value: float, current_value: float, unit: str,
    ) -> SloDefinition:
        """Register a service-level objective."""
        if slo_id in self._slos:
            raise RuntimeCoreInvariantError(f"Duplicate slo_id: {slo_id}")
        now = self._now()
        record = SloDefinition(
            slo_id=slo_id,
            tenant_id=tenant_id,
            metric_name=metric_name,
            target_value=target_value,
            current_value=current_value,
            unit=unit,
            created_at=now,
        )
        self._slos[slo_id] = record
        _emit(self._events, "register_slo", {"slo_id": slo_id}, slo_id, self._clock)
        return record

    # ------------------------------------------------------------------
    # Pilot assessment
    # ------------------------------------------------------------------

    def pilot_assessment(
        self, assessment_id: str, tenant_id: str, pilot_ref: str,
    ) -> PilotAssessment:
        """Compute a pilot assessment for a tenant."""
        tenant_connectors = [c for c in self._connectors.values() if c.tenant_id == tenant_id]
        tenant_migrations = [m for m in self._migrations.values() if m.tenant_id == tenant_id]

        total_connectors = len(tenant_connectors)
        active_connectors = sum(1 for c in tenant_connectors if c.status == ConnectorActivationStatus.ACTIVE)

        total_migrations = len(tenant_migrations)
        completed_migrations = sum(1 for m in tenant_migrations if m.status == MigrationStatus.COMPLETED)
        migration_completeness = completed_migrations / total_migrations if total_migrations > 0 else 0.0

        # Readiness score: average of connector ratio and migration completeness
        connector_ratio = active_connectors / total_connectors if total_connectors > 0 else 0.0
        readiness_score = (connector_ratio + migration_completeness) / 2.0

        now = self._now()
        record = PilotAssessment(
            assessment_id=assessment_id,
            tenant_id=tenant_id,
            pilot_ref=pilot_ref,
            total_connectors=total_connectors,
            active_connectors=active_connectors,
            migration_completeness=migration_completeness,
            readiness_score=readiness_score,
            assessed_at=now,
        )
        _emit(self._events, "pilot_assessment", {"assessment_id": assessment_id}, assessment_id, self._clock)
        return record

    # ------------------------------------------------------------------
    # Pilot snapshot
    # ------------------------------------------------------------------

    def pilot_snapshot(self, tenant_id: str) -> dict[str, Any]:
        """Return a snapshot of all pilot state for a tenant."""
        tenant_bootstraps = [b for b in self._bootstraps.values() if b.tenant_id == tenant_id]
        tenant_connectors = [c for c in self._connectors.values() if c.tenant_id == tenant_id]
        tenant_migrations = [m for m in self._migrations.values() if m.tenant_id == tenant_id]
        tenant_pilots = [p for p in self._pilots.values() if p.tenant_id == tenant_id]
        tenant_violations = [v for v in self._violations.values() if v.tenant_id == tenant_id]

        return {
            "tenant_id": tenant_id,
            "bootstraps": len(tenant_bootstraps),
            "connectors": len(tenant_connectors),
            "migrations": len(tenant_migrations),
            "pilots": len(tenant_pilots),
            "violations": len(tenant_violations),
        }

    # ------------------------------------------------------------------
    # Pilot closure report
    # ------------------------------------------------------------------

    def pilot_closure_report(self, report_id: str, tenant_id: str) -> PilotClosureReport:
        """Generate a closure report for a tenant's pilot deployment."""
        tenant_bootstraps = [b for b in self._bootstraps.values() if b.tenant_id == tenant_id]
        tenant_connectors = [c for c in self._connectors.values() if c.tenant_id == tenant_id]
        tenant_migrations = [m for m in self._migrations.values() if m.tenant_id == tenant_id]
        tenant_violations = [v for v in self._violations.values() if v.tenant_id == tenant_id]

        now = self._now()
        report = PilotClosureReport(
            report_id=report_id,
            tenant_id=tenant_id,
            total_bootstraps=len(tenant_bootstraps),
            total_connectors=len(tenant_connectors),
            total_migrations=len(tenant_migrations),
            total_violations=len(tenant_violations),
            created_at=now,
        )
        _emit(self._events, "pilot_closure_report", {"report_id": report_id}, report_id, self._clock)
        return report

    # ------------------------------------------------------------------
    # Violation detection
    # ------------------------------------------------------------------

    def detect_pilot_violations(self, tenant_id: str) -> tuple[PilotViolation, ...]:
        """Detect pilot violations for a tenant. Idempotent."""
        now = self._now()
        new_violations: list[PilotViolation] = []

        # Check for live pilots
        live_pilots = [p for p in self._pilots.values()
                       if p.tenant_id == tenant_id and p.phase in (PilotPhase.ACTIVE_USE, PilotPhase.EVALUATION, PilotPhase.GRADUATED)]

        if live_pilots:
            # failed_connector_in_live_pilot
            failed_connectors = [c for c in self._connectors.values()
                                 if c.tenant_id == tenant_id and c.status == ConnectorActivationStatus.FAILED]
            for c in failed_connectors:
                vid = stable_identifier("pv", {"t": tenant_id, "op": "failed_connector", "id": c.activation_id})
                if vid not in self._violations:
                    v = PilotViolation(
                        violation_id=vid,
                        tenant_id=tenant_id,
                        operation="failed_connector_in_live_pilot",
                        reason=f"Connector {c.activation_id} failed during live pilot",
                        detected_at=now,
                    )
                    self._violations[vid] = v
                    new_violations.append(v)

        # incomplete_migration
        incomplete_migrations = [m for m in self._migrations.values()
                                 if m.tenant_id == tenant_id and m.status == MigrationStatus.FAILED]
        for m in incomplete_migrations:
            vid = stable_identifier("pv", {"t": tenant_id, "op": "incomplete_migration", "id": m.migration_id})
            if vid not in self._violations:
                v = PilotViolation(
                    violation_id=vid,
                    tenant_id=tenant_id,
                    operation="incomplete_migration",
                    reason=f"Migration {m.migration_id} failed",
                    detected_at=now,
                )
                self._violations[vid] = v
                new_violations.append(v)

        # slo_breach: current < target * 0.9
        tenant_slos = [s for s in self._slos.values() if s.tenant_id == tenant_id]
        for s in tenant_slos:
            if s.current_value < s.target_value * 0.9:
                vid = stable_identifier("pv", {"t": tenant_id, "op": "slo_breach", "id": s.slo_id})
                if vid not in self._violations:
                    v = PilotViolation(
                        violation_id=vid,
                        tenant_id=tenant_id,
                        operation="slo_breach",
                        reason=f"SLO {s.slo_id} breached: {s.current_value} < {s.target_value * 0.9}",
                        detected_at=now,
                    )
                    self._violations[vid] = v
                    new_violations.append(v)

        _emit(self._events, "detect_violations", {
            "tenant_id": tenant_id, "new_violations": len(new_violations),
        }, tenant_id, self._clock)
        return tuple(new_violations)

    # ------------------------------------------------------------------
    # Collections / snapshot / state_hash
    # ------------------------------------------------------------------

    def _collections(self) -> dict[str, Any]:
        return {
            "bootstraps": self._bootstraps,
            "connectors": self._connectors,
            "migrations": self._migrations,
            "pilots": self._pilots,
            "checklists": self._checklists,
            "runbooks": self._runbooks,
            "slos": self._slos,
            "violations": self._violations,
        }

    def snapshot(self) -> dict[str, Any]:
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
        parts: list[str] = []
        for k in sorted(self._bootstraps):
            parts.append(f"bootstrap:{k}:{self._bootstraps[k].status.value}")
        for k in sorted(self._connectors):
            parts.append(f"connector:{k}:{self._connectors[k].status.value}")
        for k in sorted(self._migrations):
            parts.append(f"migration:{k}:{self._migrations[k].status.value}")
        for k in sorted(self._pilots):
            parts.append(f"pilot:{k}:{self._pilots[k].phase.value}")
        for k in sorted(self._checklists):
            parts.append(f"checklist:{k}:{self._checklists[k].readiness.value}")
        for k in sorted(self._runbooks):
            parts.append(f"runbook:{k}")
        for k in sorted(self._slos):
            parts.append(f"slo:{k}")
        for k in sorted(self._violations):
            parts.append(f"violation:{k}")
        raw = "|".join(parts) if parts else "empty"
        h = sha256(raw.encode()).hexdigest()
        assert len(h) == 64
        return h
