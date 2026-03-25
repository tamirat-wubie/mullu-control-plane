"""Purpose: data quality / schema evolution / lineage runtime engine.
Governance scope: registering quality records; managing schema versions;
    detecting drift; tracking lineage and duplicates; reconciliation;
    source quality policies; computing trust scores; producing snapshots,
    violations, and closure reports.
Dependencies: data_quality contracts, event_spine, core invariants.
Invariants:
  - Schema evolution follows CURRENT -> MIGRATING -> DEPRECATED -> RETIRED.
  - RETIRED is terminal (no further transitions).
  - Trust scores are deterministic: 0 errors=HIGH, 1-3=MEDIUM, 4-9=LOW, 10+=UNTRUSTED.
  - Every mutation emits an event.
  - All returns are immutable.
"""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from typing import Any

from ..contracts.data_quality import (
    DataQualityClosureReport,
    DataQualityRecord,
    DataQualitySnapshot,
    DataQualityStatus,
    DataQualityViolation,
    DriftDetection,
    DriftSeverity,
    DuplicateDisposition,
    DuplicateRecord,
    LineageDisposition,
    LineageRecord,
    ReconciliationRecord,
    SchemaEvolutionStatus,
    SchemaVersion,
    SourceQualityPolicy,
    TrustScore,
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
        event_id=stable_identifier("evt-dq", {"action": action, "ts": now, "cid": cid}),
        event_type=EventType.CUSTOM,
        source=EventSource.COMMUNICATION_SYSTEM,
        correlation_id=cid,
        payload=payload,
        emitted_at=now,
    )
    es.emit(event)
    return event


# ---------------------------------------------------------------------------
# Trust score computation
# ---------------------------------------------------------------------------

_TRUST_THRESHOLDS: list[tuple[int, TrustScore]] = [
    (0, TrustScore.HIGH),
    (3, TrustScore.MEDIUM),
    (9, TrustScore.LOW),
]


def compute_trust_score(error_count: int) -> TrustScore:
    """Compute trust score from error count: 0=HIGH, 1-3=MEDIUM, 4-9=LOW, 10+=UNTRUSTED."""
    if error_count <= 0:
        return TrustScore.HIGH
    if error_count <= 3:
        return TrustScore.MEDIUM
    if error_count <= 9:
        return TrustScore.LOW
    return TrustScore.UNTRUSTED


# ---------------------------------------------------------------------------
# Drift severity auto-detection
# ---------------------------------------------------------------------------

_FUNDAMENTAL_MISMATCHES = frozenset({
    ("str", "int"), ("int", "str"),
    ("str", "bool"), ("bool", "str"),
    ("int", "bool"), ("bool", "int"),
    ("str", "float"), ("float", "str"),
    ("int", "float"), ("float", "int"),
    ("list", "dict"), ("dict", "list"),
})


def _auto_drift_severity(expected_type: str, actual_type: str, field_name: str) -> DriftSeverity:
    """Auto-classify drift severity."""
    if expected_type == actual_type:
        return DriftSeverity.NONE
    pair = (expected_type.lower(), actual_type.lower())
    if pair in _FUNDAMENTAL_MISMATCHES:
        return DriftSeverity.BREAKING
    # Field added or removed (empty vs non-empty)
    if not expected_type.strip() or not actual_type.strip():
        return DriftSeverity.MAJOR
    # Type widened (e.g. int -> number)
    return DriftSeverity.MINOR


class DataQualityEngine:
    """Data quality, schema evolution, and lineage engine."""

    def __init__(self, event_spine: EventSpineEngine) -> None:
        if not isinstance(event_spine, EventSpineEngine):
            raise RuntimeCoreInvariantError("event_spine must be an EventSpineEngine")
        self._events = event_spine
        self._records: dict[str, DataQualityRecord] = {}
        self._schemas: dict[str, SchemaVersion] = {}
        self._drifts: dict[str, DriftDetection] = {}
        self._lineages: dict[str, LineageRecord] = {}
        self._duplicates: dict[str, DuplicateRecord] = {}
        self._reconciliations: dict[str, ReconciliationRecord] = {}
        self._policies: dict[str, SourceQualityPolicy] = {}
        self._violations: dict[str, DataQualityViolation] = {}
        self._snapshot_ids: set[str] = set()

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def record_count(self) -> int:
        return len(self._records)

    @property
    def schema_count(self) -> int:
        return len(self._schemas)

    @property
    def drift_count(self) -> int:
        return len(self._drifts)

    @property
    def lineage_count(self) -> int:
        return len(self._lineages)

    @property
    def duplicate_count(self) -> int:
        return len(self._duplicates)

    @property
    def reconciliation_count(self) -> int:
        return len(self._reconciliations)

    @property
    def policy_count(self) -> int:
        return len(self._policies)

    @property
    def violation_count(self) -> int:
        return len(self._violations)

    # ------------------------------------------------------------------
    # Quality record management
    # ------------------------------------------------------------------

    def register_quality_record(
        self,
        record_id: str,
        tenant_id: str,
        source_ref: str,
        *,
        status: DataQualityStatus = DataQualityStatus.CLEAN,
        error_count: int = 0,
    ) -> DataQualityRecord:
        """Register a data quality record."""
        if record_id in self._records:
            raise RuntimeCoreInvariantError(f"Duplicate record_id: {record_id}")
        now = _now_iso()
        trust = compute_trust_score(error_count)
        record = DataQualityRecord(
            record_id=record_id,
            tenant_id=tenant_id,
            source_ref=source_ref,
            status=status,
            trust_score=trust,
            error_count=error_count,
            checked_at=now,
        )
        self._records[record_id] = record
        _emit(self._events, "quality_record_registered", {
            "record_id": record_id, "status": status.value,
            "trust_score": trust.value, "error_count": error_count,
        }, record_id)
        return record

    def get_record(self, record_id: str) -> DataQualityRecord:
        """Get a quality record by ID."""
        r = self._records.get(record_id)
        if r is None:
            raise RuntimeCoreInvariantError(f"Unknown record_id: {record_id}")
        return r

    def records_for_tenant(self, tenant_id: str) -> tuple[DataQualityRecord, ...]:
        """Return all quality records for a tenant."""
        return tuple(r for r in self._records.values() if r.tenant_id == tenant_id)

    # ------------------------------------------------------------------
    # Schema version management
    # ------------------------------------------------------------------

    def register_schema_version(
        self,
        version_id: str,
        tenant_id: str,
        schema_ref: str,
        *,
        version_number: int = 0,
        field_count: int = 0,
    ) -> SchemaVersion:
        """Register a schema version. Raises on duplicate."""
        if version_id in self._schemas:
            raise RuntimeCoreInvariantError(f"Duplicate version_id: {version_id}")
        now = _now_iso()
        schema = SchemaVersion(
            version_id=version_id,
            tenant_id=tenant_id,
            schema_ref=schema_ref,
            status=SchemaEvolutionStatus.CURRENT,
            version_number=version_number,
            field_count=field_count,
            created_at=now,
        )
        self._schemas[version_id] = schema
        _emit(self._events, "schema_version_registered", {
            "version_id": version_id, "schema_ref": schema_ref,
            "version_number": version_number,
        }, version_id)
        return schema

    def deprecate_schema(self, version_id: str) -> SchemaVersion:
        """Transition a schema to DEPRECATED."""
        schema = self._schemas.get(version_id)
        if schema is None:
            raise RuntimeCoreInvariantError(f"Unknown version_id: {version_id}")
        if schema.status == SchemaEvolutionStatus.RETIRED:
            raise RuntimeCoreInvariantError("Cannot transition from RETIRED (terminal state)")
        updated = SchemaVersion(
            version_id=schema.version_id,
            tenant_id=schema.tenant_id,
            schema_ref=schema.schema_ref,
            status=SchemaEvolutionStatus.DEPRECATED,
            version_number=schema.version_number,
            field_count=schema.field_count,
            created_at=schema.created_at,
            metadata=schema.metadata,
        )
        self._schemas[version_id] = updated
        _emit(self._events, "schema_deprecated", {
            "version_id": version_id,
        }, version_id)
        return updated

    def retire_schema(self, version_id: str) -> SchemaVersion:
        """Transition a schema to RETIRED (terminal)."""
        schema = self._schemas.get(version_id)
        if schema is None:
            raise RuntimeCoreInvariantError(f"Unknown version_id: {version_id}")
        if schema.status == SchemaEvolutionStatus.RETIRED:
            raise RuntimeCoreInvariantError("Cannot transition from RETIRED (terminal state)")
        updated = SchemaVersion(
            version_id=schema.version_id,
            tenant_id=schema.tenant_id,
            schema_ref=schema.schema_ref,
            status=SchemaEvolutionStatus.RETIRED,
            version_number=schema.version_number,
            field_count=schema.field_count,
            created_at=schema.created_at,
            metadata=schema.metadata,
        )
        self._schemas[version_id] = updated
        _emit(self._events, "schema_retired", {
            "version_id": version_id,
        }, version_id)
        return updated

    # ------------------------------------------------------------------
    # Drift detection
    # ------------------------------------------------------------------

    def detect_drift(
        self,
        detection_id: str,
        tenant_id: str,
        schema_ref: str,
        field_name: str,
        expected_type: str,
        actual_type: str,
    ) -> DriftDetection:
        """Create a drift detection with auto-computed severity."""
        if detection_id in self._drifts:
            raise RuntimeCoreInvariantError(f"Duplicate detection_id: {detection_id}")
        severity = _auto_drift_severity(expected_type, actual_type, field_name)
        now = _now_iso()
        drift = DriftDetection(
            detection_id=detection_id,
            tenant_id=tenant_id,
            schema_ref=schema_ref,
            severity=severity,
            field_name=field_name,
            expected_type=expected_type,
            actual_type=actual_type,
            detected_at=now,
        )
        self._drifts[detection_id] = drift
        _emit(self._events, "drift_detected", {
            "detection_id": detection_id, "severity": severity.value,
            "field_name": field_name,
        }, detection_id)
        return drift

    # ------------------------------------------------------------------
    # Lineage
    # ------------------------------------------------------------------

    def register_lineage(
        self,
        lineage_id: str,
        tenant_id: str,
        source_ref: str,
        target_ref: str,
        *,
        hop_count: int = 1,
    ) -> LineageRecord:
        """Register a lineage record."""
        if lineage_id in self._lineages:
            raise RuntimeCoreInvariantError(f"Duplicate lineage_id: {lineage_id}")
        now = _now_iso()
        lineage = LineageRecord(
            lineage_id=lineage_id,
            tenant_id=tenant_id,
            source_ref=source_ref,
            target_ref=target_ref,
            disposition=LineageDisposition.UNVERIFIED,
            hop_count=hop_count,
            created_at=now,
        )
        self._lineages[lineage_id] = lineage
        _emit(self._events, "lineage_registered", {
            "lineage_id": lineage_id, "source_ref": source_ref,
            "target_ref": target_ref,
        }, lineage_id)
        return lineage

    def get_lineage(self, lineage_id: str) -> LineageRecord:
        """Get a lineage record by ID."""
        lr = self._lineages.get(lineage_id)
        if lr is None:
            raise RuntimeCoreInvariantError(f"Unknown lineage_id: {lineage_id}")
        return lr

    def verify_lineage(self, lineage_id: str, verified: bool = True) -> LineageRecord:
        """Mark a lineage as VERIFIED or BROKEN."""
        lr = self._lineages.get(lineage_id)
        if lr is None:
            raise RuntimeCoreInvariantError(f"Unknown lineage_id: {lineage_id}")
        new_disp = LineageDisposition.VERIFIED if verified else LineageDisposition.BROKEN
        updated = LineageRecord(
            lineage_id=lr.lineage_id,
            tenant_id=lr.tenant_id,
            source_ref=lr.source_ref,
            target_ref=lr.target_ref,
            disposition=new_disp,
            hop_count=lr.hop_count,
            created_at=lr.created_at,
            metadata=lr.metadata,
        )
        self._lineages[lineage_id] = updated
        _emit(self._events, "lineage_verified", {
            "lineage_id": lineage_id, "disposition": new_disp.value,
        }, lineage_id)
        return updated

    # ------------------------------------------------------------------
    # Duplicate detection
    # ------------------------------------------------------------------

    def detect_duplicate(
        self,
        duplicate_id: str,
        tenant_id: str,
        record_ref_a: str,
        record_ref_b: str,
        *,
        confidence: float = 0.5,
    ) -> DuplicateRecord:
        """Register a suspected duplicate."""
        if duplicate_id in self._duplicates:
            raise RuntimeCoreInvariantError(f"Duplicate duplicate_id: {duplicate_id}")
        now = _now_iso()
        dup = DuplicateRecord(
            duplicate_id=duplicate_id,
            tenant_id=tenant_id,
            record_ref_a=record_ref_a,
            record_ref_b=record_ref_b,
            disposition=DuplicateDisposition.SUSPECTED,
            confidence=confidence,
            detected_at=now,
        )
        self._duplicates[duplicate_id] = dup
        _emit(self._events, "duplicate_detected", {
            "duplicate_id": duplicate_id, "confidence": confidence,
        }, duplicate_id)
        return dup

    def merge_duplicate(self, duplicate_id: str) -> DuplicateRecord:
        """Transition CONFIRMED -> MERGED."""
        dup = self._duplicates.get(duplicate_id)
        if dup is None:
            raise RuntimeCoreInvariantError(f"Unknown duplicate_id: {duplicate_id}")
        if dup.disposition != DuplicateDisposition.CONFIRMED:
            raise RuntimeCoreInvariantError("Only CONFIRMED duplicates can be MERGED")
        updated = DuplicateRecord(
            duplicate_id=dup.duplicate_id,
            tenant_id=dup.tenant_id,
            record_ref_a=dup.record_ref_a,
            record_ref_b=dup.record_ref_b,
            disposition=DuplicateDisposition.MERGED,
            confidence=dup.confidence,
            detected_at=dup.detected_at,
            metadata=dup.metadata,
        )
        self._duplicates[duplicate_id] = updated
        _emit(self._events, "duplicate_merged", {
            "duplicate_id": duplicate_id,
        }, duplicate_id)
        return updated

    def dismiss_duplicate(self, duplicate_id: str) -> DuplicateRecord:
        """Dismiss a suspected duplicate -> UNIQUE."""
        dup = self._duplicates.get(duplicate_id)
        if dup is None:
            raise RuntimeCoreInvariantError(f"Unknown duplicate_id: {duplicate_id}")
        updated = DuplicateRecord(
            duplicate_id=dup.duplicate_id,
            tenant_id=dup.tenant_id,
            record_ref_a=dup.record_ref_a,
            record_ref_b=dup.record_ref_b,
            disposition=DuplicateDisposition.UNIQUE,
            confidence=dup.confidence,
            detected_at=dup.detected_at,
            metadata=dup.metadata,
        )
        self._duplicates[duplicate_id] = updated
        _emit(self._events, "duplicate_dismissed", {
            "duplicate_id": duplicate_id,
        }, duplicate_id)
        return updated

    def _confirm_duplicate(self, duplicate_id: str) -> DuplicateRecord:
        """Confirm a suspected duplicate -> CONFIRMED (internal)."""
        dup = self._duplicates.get(duplicate_id)
        if dup is None:
            raise RuntimeCoreInvariantError(f"Unknown duplicate_id: {duplicate_id}")
        updated = DuplicateRecord(
            duplicate_id=dup.duplicate_id,
            tenant_id=dup.tenant_id,
            record_ref_a=dup.record_ref_a,
            record_ref_b=dup.record_ref_b,
            disposition=DuplicateDisposition.CONFIRMED,
            confidence=dup.confidence,
            detected_at=dup.detected_at,
            metadata=dup.metadata,
        )
        self._duplicates[duplicate_id] = updated
        return updated

    # ------------------------------------------------------------------
    # Reconciliation
    # ------------------------------------------------------------------

    def reconcile_record(
        self,
        reconciliation_id: str,
        tenant_id: str,
        source_ref: str,
        canonical_ref: str,
        *,
        resolved: bool = True,
    ) -> ReconciliationRecord:
        """Create a reconciliation record."""
        if reconciliation_id in self._reconciliations:
            raise RuntimeCoreInvariantError(f"Duplicate reconciliation_id: {reconciliation_id}")
        now = _now_iso()
        rec = ReconciliationRecord(
            reconciliation_id=reconciliation_id,
            tenant_id=tenant_id,
            source_ref=source_ref,
            canonical_ref=canonical_ref,
            resolved=resolved,
            created_at=now,
        )
        self._reconciliations[reconciliation_id] = rec
        _emit(self._events, "record_reconciled", {
            "reconciliation_id": reconciliation_id, "resolved": resolved,
        }, reconciliation_id)
        return rec

    # ------------------------------------------------------------------
    # Source quality policies
    # ------------------------------------------------------------------

    def register_source_policy(
        self,
        policy_id: str,
        tenant_id: str,
        source_ref: str,
        *,
        min_trust: TrustScore = TrustScore.MEDIUM,
        max_errors: int = 10,
    ) -> SourceQualityPolicy:
        """Register a source quality policy."""
        if policy_id in self._policies:
            raise RuntimeCoreInvariantError(f"Duplicate policy_id: {policy_id}")
        now = _now_iso()
        policy = SourceQualityPolicy(
            policy_id=policy_id,
            tenant_id=tenant_id,
            source_ref=source_ref,
            min_trust=min_trust,
            max_errors=max_errors,
            created_at=now,
        )
        self._policies[policy_id] = policy
        _emit(self._events, "source_policy_registered", {
            "policy_id": policy_id, "min_trust": min_trust.value,
        }, policy_id)
        return policy

    # ------------------------------------------------------------------
    # Snapshot
    # ------------------------------------------------------------------

    def data_quality_snapshot(
        self,
        snapshot_id: str,
        tenant_id: str,
    ) -> DataQualitySnapshot:
        """Capture a tenant-scoped snapshot."""
        if snapshot_id in self._snapshot_ids:
            raise RuntimeCoreInvariantError(f"Duplicate snapshot_id: {snapshot_id}")
        now = _now_iso()
        tenant_records = sum(1 for r in self._records.values() if r.tenant_id == tenant_id)
        tenant_schemas = sum(1 for s in self._schemas.values() if s.tenant_id == tenant_id)
        tenant_drifts = sum(1 for d in self._drifts.values() if d.tenant_id == tenant_id)
        tenant_duplicates = sum(1 for d in self._duplicates.values() if d.tenant_id == tenant_id)
        tenant_lineages = sum(1 for l in self._lineages.values() if l.tenant_id == tenant_id)
        tenant_violations = sum(1 for v in self._violations.values() if v.tenant_id == tenant_id)
        snapshot = DataQualitySnapshot(
            snapshot_id=snapshot_id,
            tenant_id=tenant_id,
            total_records=tenant_records,
            total_schemas=tenant_schemas,
            total_drifts=tenant_drifts,
            total_duplicates=tenant_duplicates,
            total_lineages=tenant_lineages,
            total_violations=tenant_violations,
            captured_at=now,
        )
        self._snapshot_ids.add(snapshot_id)
        _emit(self._events, "data_quality_snapshot_captured", {
            "snapshot_id": snapshot_id,
        }, snapshot_id)
        return snapshot

    # ------------------------------------------------------------------
    # Violations
    # ------------------------------------------------------------------

    def detect_data_quality_violations(
        self,
        tenant_id: str,
    ) -> tuple[DataQualityViolation, ...]:
        """Detect data quality violations (idempotent).

        Violation rules:
        - dirty_no_quarantine: DIRTY record not QUARANTINED
        - breaking_drift_unresolved: BREAKING drift exists
        - broken_lineage: BROKEN lineage exists
        """
        now = _now_iso()
        new_violations: list[DataQualityViolation] = []

        # dirty_no_quarantine
        for rec in self._records.values():
            if rec.tenant_id != tenant_id:
                continue
            if rec.status == DataQualityStatus.DIRTY:
                vid = stable_identifier("viol-dq", {"rule": "dirty_no_quarantine", "rec": rec.record_id})
                if vid in self._violations:
                    continue
                violation = DataQualityViolation(
                    violation_id=vid,
                    tenant_id=tenant_id,
                    operation="dirty_no_quarantine",
                    reason=f"Record {rec.record_id} is DIRTY but not quarantined",
                    detected_at=now,
                )
                self._violations[vid] = violation
                new_violations.append(violation)

        # breaking_drift_unresolved
        for drift in self._drifts.values():
            if drift.tenant_id != tenant_id:
                continue
            if drift.severity == DriftSeverity.BREAKING:
                vid = stable_identifier("viol-dq", {"rule": "breaking_drift", "det": drift.detection_id})
                if vid in self._violations:
                    continue
                violation = DataQualityViolation(
                    violation_id=vid,
                    tenant_id=tenant_id,
                    operation="breaking_drift_unresolved",
                    reason=f"Breaking drift {drift.detection_id} on field {drift.field_name}",
                    detected_at=now,
                )
                self._violations[vid] = violation
                new_violations.append(violation)

        # broken_lineage
        for lin in self._lineages.values():
            if lin.tenant_id != tenant_id:
                continue
            if lin.disposition == LineageDisposition.BROKEN:
                vid = stable_identifier("viol-dq", {"rule": "broken_lineage", "lin": lin.lineage_id})
                if vid in self._violations:
                    continue
                violation = DataQualityViolation(
                    violation_id=vid,
                    tenant_id=tenant_id,
                    operation="broken_lineage",
                    reason=f"Lineage {lin.lineage_id} is BROKEN",
                    detected_at=now,
                )
                self._violations[vid] = violation
                new_violations.append(violation)

        if new_violations:
            _emit(self._events, "data_quality_violations_detected", {
                "count": len(new_violations),
            }, "violation-scan")
        return tuple(new_violations)

    # ------------------------------------------------------------------
    # Closure report
    # ------------------------------------------------------------------

    def dq_closure_report(self, report_id: str, tenant_id: str) -> DataQualityClosureReport:
        now = _now_iso()
        report = DataQualityClosureReport(
            report_id=report_id, tenant_id=tenant_id,
            total_records=sum(1 for r in self._records.values() if r.tenant_id == tenant_id),
            total_schemas=sum(1 for s in self._schemas.values() if s.tenant_id == tenant_id),
            total_drifts=sum(1 for d in self._drifts.values() if d.tenant_id == tenant_id),
            total_duplicates=sum(1 for d in self._duplicates.values() if d.tenant_id == tenant_id),
            total_violations=sum(1 for v in self._violations.values() if v.tenant_id == tenant_id),
            created_at=now,
        )
        _emit(self._events, "dq_closure_report", {"report_id": report_id}, report_id)
        return report

    # ------------------------------------------------------------------
    # State hash
    # ------------------------------------------------------------------

    def state_hash(self) -> str:
        """Compute a SHA256 hash of the current engine state (sorted keys)."""
        parts = sorted([
            f"drifts={self.drift_count}",
            f"duplicates={self.duplicate_count}",
            f"lineages={self.lineage_count}",
            f"policies={self.policy_count}",
            f"reconciliations={self.reconciliation_count}",
            f"records={self.record_count}",
            f"schemas={self.schema_count}",
            f"violations={self.violation_count}",
        ])
        return sha256("|".join(parts).encode()).hexdigest()
