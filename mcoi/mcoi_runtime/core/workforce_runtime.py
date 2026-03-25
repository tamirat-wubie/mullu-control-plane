"""Purpose: organization / workforce / role capacity runtime engine.
Governance scope: registering workers and capacities, accepting assignment
    requests, allocating work based on role/load/priority/availability,
    detecting coverage gaps and overload, producing immutable snapshots.
Dependencies: workforce_runtime contracts, event_spine, core invariants.
Invariants:
  - Duplicate IDs raise.
  - Offboarded workers cannot be assigned.
  - Overloaded workers trigger alternate routing.
  - Every mutation emits an event.
  - All returns are immutable.
"""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from typing import Any

from ..contracts.workforce_runtime import (
    AssignmentDecision,
    AssignmentDisposition,
    AssignmentRequest,
    CapacityStatus,
    CoverageGap,
    CoverageStatus,
    EscalationMode,
    LoadBand,
    LoadSnapshot,
    WorkerRecord,
    WorkerStatus,
    WorkforceAssessment,
    WorkforceClosureReport,
    WorkforceViolation,
    RoleCapacityRecord,
    TeamCapacityRecord,
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
        event_id=stable_identifier("evt-wkf", {"action": action, "ts": now, "cid": cid}),
        event_type=EventType.CUSTOM,
        source=EventSource.COMMUNICATION_SYSTEM,
        correlation_id=cid,
        payload=payload,
        emitted_at=now,
    )
    es.emit(event)
    return event


_WORKER_TERMINAL = frozenset({WorkerStatus.OFFBOARDED})
_WORKER_UNAVAILABLE = frozenset({WorkerStatus.ON_LEAVE, WorkerStatus.UNAVAILABLE, WorkerStatus.SUSPENDED, WorkerStatus.OFFBOARDED})


class WorkforceRuntimeEngine:
    """Organization / workforce / role capacity engine."""

    def __init__(self, event_spine: EventSpineEngine) -> None:
        if not isinstance(event_spine, EventSpineEngine):
            raise RuntimeCoreInvariantError("event_spine must be an EventSpineEngine")
        self._events = event_spine
        self._workers: dict[str, WorkerRecord] = {}
        self._role_capacities: dict[str, RoleCapacityRecord] = {}
        self._team_capacities: dict[str, TeamCapacityRecord] = {}
        self._requests: dict[str, AssignmentRequest] = {}
        self._decisions: dict[str, AssignmentDecision] = {}
        self._gaps: dict[str, CoverageGap] = {}
        self._violations: dict[str, WorkforceViolation] = {}
        self._snapshot_ids: set[str] = set()

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def worker_count(self) -> int:
        return len(self._workers)

    @property
    def role_capacity_count(self) -> int:
        return len(self._role_capacities)

    @property
    def team_capacity_count(self) -> int:
        return len(self._team_capacities)

    @property
    def request_count(self) -> int:
        return len(self._requests)

    @property
    def decision_count(self) -> int:
        return len(self._decisions)

    @property
    def gap_count(self) -> int:
        return len(self._gaps)

    @property
    def violation_count(self) -> int:
        return len(self._violations)

    # ------------------------------------------------------------------
    # Workers
    # ------------------------------------------------------------------

    def register_worker(
        self,
        worker_id: str,
        tenant_id: str,
        role_ref: str,
        team_ref: str,
        display_name: str,
        max_assignments: int = 5,
        status: WorkerStatus = WorkerStatus.ACTIVE,
    ) -> WorkerRecord:
        if worker_id in self._workers:
            raise RuntimeCoreInvariantError(f"worker already registered: {worker_id}")
        now = _now_iso()
        worker = WorkerRecord(
            worker_id=worker_id,
            tenant_id=tenant_id,
            role_ref=role_ref,
            team_ref=team_ref,
            display_name=display_name,
            status=status,
            max_assignments=max_assignments,
            current_assignments=0,
            created_at=now,
        )
        self._workers[worker_id] = worker
        _emit(self._events, "register_worker", {"worker_id": worker_id, "tenant_id": tenant_id}, worker_id)
        return worker

    def get_worker(self, worker_id: str) -> WorkerRecord:
        if worker_id not in self._workers:
            raise RuntimeCoreInvariantError(f"unknown worker: {worker_id}")
        return self._workers[worker_id]

    def update_worker_status(self, worker_id: str, status: WorkerStatus) -> WorkerRecord:
        if worker_id not in self._workers:
            raise RuntimeCoreInvariantError(f"unknown worker: {worker_id}")
        old = self._workers[worker_id]
        if old.status in _WORKER_TERMINAL:
            raise RuntimeCoreInvariantError(f"worker is in terminal state: {old.status.value}")
        updated = WorkerRecord(
            worker_id=old.worker_id,
            tenant_id=old.tenant_id,
            role_ref=old.role_ref,
            team_ref=old.team_ref,
            display_name=old.display_name,
            status=status,
            max_assignments=old.max_assignments,
            current_assignments=old.current_assignments,
            created_at=old.created_at,
        )
        self._workers[worker_id] = updated
        _emit(self._events, "update_worker_status", {"worker_id": worker_id, "status": status.value}, worker_id)
        return updated

    def workers_for_tenant(self, tenant_id: str) -> tuple[WorkerRecord, ...]:
        return tuple(w for w in self._workers.values() if w.tenant_id == tenant_id)

    def workers_for_role(self, tenant_id: str, role_ref: str) -> tuple[WorkerRecord, ...]:
        return tuple(
            w for w in self._workers.values()
            if w.tenant_id == tenant_id and w.role_ref == role_ref
        )

    def available_workers_for_role(self, tenant_id: str, role_ref: str) -> tuple[WorkerRecord, ...]:
        return tuple(
            w for w in self._workers.values()
            if w.tenant_id == tenant_id
            and w.role_ref == role_ref
            and w.status == WorkerStatus.ACTIVE
            and w.current_assignments < w.max_assignments
        )

    # ------------------------------------------------------------------
    # Role capacity
    # ------------------------------------------------------------------

    def register_role_capacity(
        self,
        capacity_id: str,
        tenant_id: str,
        role_ref: str,
    ) -> RoleCapacityRecord:
        if capacity_id in self._role_capacities:
            raise RuntimeCoreInvariantError(f"role capacity already registered: {capacity_id}")
        now = _now_iso()
        # Compute from current workers
        role_workers = [w for w in self._workers.values() if w.tenant_id == tenant_id and w.role_ref == role_ref]
        total_workers = len(role_workers)
        available = len([w for w in role_workers if w.status == WorkerStatus.ACTIVE and w.current_assignments < w.max_assignments])
        total_cap = sum(w.max_assignments for w in role_workers)
        used_cap = sum(w.current_assignments for w in role_workers)
        util = used_cap / total_cap if total_cap > 0 else 0.0
        status = self._derive_capacity_status(util)
        record = RoleCapacityRecord(
            capacity_id=capacity_id,
            tenant_id=tenant_id,
            role_ref=role_ref,
            total_workers=total_workers,
            available_workers=available,
            total_capacity=total_cap,
            used_capacity=used_cap,
            utilization=round(util, 4),
            status=status,
            assessed_at=now,
        )
        self._role_capacities[capacity_id] = record
        _emit(self._events, "register_role_capacity", {"capacity_id": capacity_id, "tenant_id": tenant_id, "role_ref": role_ref}, capacity_id)
        return record

    def get_role_capacity(self, capacity_id: str) -> RoleCapacityRecord:
        if capacity_id not in self._role_capacities:
            raise RuntimeCoreInvariantError(f"unknown role capacity: {capacity_id}")
        return self._role_capacities[capacity_id]

    def role_capacities_for_tenant(self, tenant_id: str) -> tuple[RoleCapacityRecord, ...]:
        return tuple(r for r in self._role_capacities.values() if r.tenant_id == tenant_id)

    # ------------------------------------------------------------------
    # Team capacity
    # ------------------------------------------------------------------

    def register_team_capacity(
        self,
        capacity_id: str,
        tenant_id: str,
        team_ref: str,
    ) -> TeamCapacityRecord:
        if capacity_id in self._team_capacities:
            raise RuntimeCoreInvariantError(f"team capacity already registered: {capacity_id}")
        now = _now_iso()
        team_workers = [w for w in self._workers.values() if w.tenant_id == tenant_id and w.team_ref == team_ref]
        total_members = len(team_workers)
        available = len([w for w in team_workers if w.status == WorkerStatus.ACTIVE and w.current_assignments < w.max_assignments])
        total_cap = sum(w.max_assignments for w in team_workers)
        used_cap = sum(w.current_assignments for w in team_workers)
        util = used_cap / total_cap if total_cap > 0 else 0.0
        status = self._derive_capacity_status(util)
        record = TeamCapacityRecord(
            capacity_id=capacity_id,
            tenant_id=tenant_id,
            team_ref=team_ref,
            total_members=total_members,
            available_members=available,
            total_capacity=total_cap,
            used_capacity=used_cap,
            utilization=round(util, 4),
            status=status,
            assessed_at=now,
        )
        self._team_capacities[capacity_id] = record
        _emit(self._events, "register_team_capacity", {"capacity_id": capacity_id, "tenant_id": tenant_id, "team_ref": team_ref}, capacity_id)
        return record

    def get_team_capacity(self, capacity_id: str) -> TeamCapacityRecord:
        if capacity_id not in self._team_capacities:
            raise RuntimeCoreInvariantError(f"unknown team capacity: {capacity_id}")
        return self._team_capacities[capacity_id]

    def team_capacities_for_tenant(self, tenant_id: str) -> tuple[TeamCapacityRecord, ...]:
        return tuple(t for t in self._team_capacities.values() if t.tenant_id == tenant_id)

    # ------------------------------------------------------------------
    # Assignment requests
    # ------------------------------------------------------------------

    def request_assignment(
        self,
        request_id: str,
        tenant_id: str,
        scope_ref_id: str,
        role_ref: str,
        priority: int = 1,
        source_type: str = "manual",
    ) -> AssignmentRequest:
        if request_id in self._requests:
            raise RuntimeCoreInvariantError(f"assignment request already exists: {request_id}")
        now = _now_iso()
        request = AssignmentRequest(
            request_id=request_id,
            tenant_id=tenant_id,
            scope_ref_id=scope_ref_id,
            role_ref=role_ref,
            priority=priority,
            source_type=source_type,
            requested_at=now,
        )
        self._requests[request_id] = request
        _emit(self._events, "request_assignment", {"request_id": request_id, "tenant_id": tenant_id, "role_ref": role_ref}, request_id)
        return request

    def get_request(self, request_id: str) -> AssignmentRequest:
        if request_id not in self._requests:
            raise RuntimeCoreInvariantError(f"unknown assignment request: {request_id}")
        return self._requests[request_id]

    def requests_for_tenant(self, tenant_id: str) -> tuple[AssignmentRequest, ...]:
        return tuple(r for r in self._requests.values() if r.tenant_id == tenant_id)

    # ------------------------------------------------------------------
    # Assignment decisions
    # ------------------------------------------------------------------

    def decide_assignment(
        self,
        decision_id: str,
        request_id: str,
        worker_id: str = "",
        disposition: AssignmentDisposition = AssignmentDisposition.ASSIGNED,
        reason: str = "",
    ) -> AssignmentDecision:
        if decision_id in self._decisions:
            raise RuntimeCoreInvariantError(f"assignment decision already exists: {decision_id}")
        if request_id not in self._requests:
            raise RuntimeCoreInvariantError(f"unknown assignment request: {request_id}")
        now = _now_iso()

        # If assigning, validate worker
        if disposition == AssignmentDisposition.ASSIGNED:
            if worker_id not in self._workers:
                raise RuntimeCoreInvariantError(f"unknown worker: {worker_id}")
            worker = self._workers[worker_id]
            if worker.status in _WORKER_UNAVAILABLE:
                raise RuntimeCoreInvariantError(f"worker is unavailable: {worker.status.value}")
            if worker.current_assignments >= worker.max_assignments:
                raise RuntimeCoreInvariantError(f"worker is at max assignments: {worker.current_assignments}/{worker.max_assignments}")
            # Increment current_assignments
            updated = WorkerRecord(
                worker_id=worker.worker_id,
                tenant_id=worker.tenant_id,
                role_ref=worker.role_ref,
                team_ref=worker.team_ref,
                display_name=worker.display_name,
                status=worker.status,
                max_assignments=worker.max_assignments,
                current_assignments=worker.current_assignments + 1,
                created_at=worker.created_at,
            )
            self._workers[worker_id] = updated

        effective_worker = worker_id if worker_id else "none"
        decision = AssignmentDecision(
            decision_id=decision_id,
            request_id=request_id,
            worker_id=effective_worker,
            disposition=disposition,
            reason=reason if reason else disposition.value,
            decided_at=now,
        )
        self._decisions[decision_id] = decision
        _emit(self._events, "decide_assignment", {"decision_id": decision_id, "request_id": request_id, "disposition": disposition.value}, decision_id)
        return decision

    def assign_to_lowest_load(
        self,
        decision_id: str,
        request_id: str,
        reason: str = "",
    ) -> AssignmentDecision:
        """Auto-assign to the lowest-load available worker for the request's role."""
        if decision_id in self._decisions:
            raise RuntimeCoreInvariantError(f"assignment decision already exists: {decision_id}")
        if request_id not in self._requests:
            raise RuntimeCoreInvariantError(f"unknown assignment request: {request_id}")
        req = self._requests[request_id]
        available = self.available_workers_for_role(req.tenant_id, req.role_ref)
        if not available:
            # Escalate — no one available
            return self.decide_assignment(
                decision_id=decision_id,
                request_id=request_id,
                worker_id="escalation",
                disposition=AssignmentDisposition.ESCALATED,
                reason=reason if reason else "no_available_workers",
            )
        # Pick lowest load (current_assignments)
        best = min(available, key=lambda w: w.current_assignments)
        return self.decide_assignment(
            decision_id=decision_id,
            request_id=request_id,
            worker_id=best.worker_id,
            disposition=AssignmentDisposition.ASSIGNED,
            reason=reason if reason else "lowest_load",
        )

    def decisions_for_request(self, request_id: str) -> tuple[AssignmentDecision, ...]:
        return tuple(d for d in self._decisions.values() if d.request_id == request_id)

    def decisions_for_worker(self, worker_id: str) -> tuple[AssignmentDecision, ...]:
        return tuple(d for d in self._decisions.values() if d.worker_id == worker_id)

    # ------------------------------------------------------------------
    # Coverage gaps
    # ------------------------------------------------------------------

    def detect_coverage_gaps(self, tenant_id: str) -> tuple[CoverageGap, ...]:
        """Detect roles/teams with insufficient coverage. Idempotent per gap_id."""
        now = _now_iso()
        new_gaps: list[CoverageGap] = []

        # Check by role: roles with zero available workers
        roles_seen: set[str] = set()
        for w in self._workers.values():
            if w.tenant_id == tenant_id:
                roles_seen.add(w.role_ref)

        for role_ref in roles_seen:
            available = self.available_workers_for_role(tenant_id, role_ref)
            all_workers = self.workers_for_role(tenant_id, role_ref)
            if not available and all_workers:
                gap_id = stable_identifier("gap", {"tenant_id": tenant_id, "role_ref": role_ref})
                if gap_id not in self._gaps:
                    # Determine team_ref from first worker
                    team_ref = all_workers[0].team_ref
                    total_count = len(all_workers)
                    status = CoverageStatus.CRITICAL_GAP if total_count >= 3 else CoverageStatus.GAP
                    gap = CoverageGap(
                        gap_id=gap_id,
                        tenant_id=tenant_id,
                        role_ref=role_ref,
                        team_ref=team_ref,
                        status=status,
                        available_workers=0,
                        required_workers=1,
                        escalation_mode=EscalationMode.MANAGER,
                        detected_at=now,
                    )
                    self._gaps[gap_id] = gap
                    new_gaps.append(gap)
                    _emit(self._events, "coverage_gap_detected", {"gap_id": gap_id, "role_ref": role_ref}, gap_id)

        return tuple(new_gaps)

    def gaps_for_tenant(self, tenant_id: str) -> tuple[CoverageGap, ...]:
        return tuple(g for g in self._gaps.values() if g.tenant_id == tenant_id)

    # ------------------------------------------------------------------
    # Load snapshot
    # ------------------------------------------------------------------

    def load_snapshot(self, snapshot_id: str, tenant_id: str) -> LoadSnapshot:
        if snapshot_id in self._snapshot_ids:
            raise RuntimeCoreInvariantError(f"snapshot already exists: {snapshot_id}")
        now = _now_iso()
        tenant_workers = [w for w in self._workers.values() if w.tenant_id == tenant_id]
        total = len(tenant_workers)
        active = len([w for w in tenant_workers if w.status == WorkerStatus.ACTIVE])
        total_assignments = sum(w.current_assignments for w in tenant_workers)
        total_cap = sum(w.max_assignments for w in tenant_workers)
        used_cap = total_assignments
        util = used_cap / total_cap if total_cap > 0 else 0.0
        band = self._derive_load_band(util)

        snapshot = LoadSnapshot(
            snapshot_id=snapshot_id,
            tenant_id=tenant_id,
            total_workers=total,
            active_workers=active,
            total_assignments=total_assignments,
            total_capacity=total_cap,
            used_capacity=used_cap,
            utilization=round(util, 4),
            load_band=band,
            captured_at=now,
        )
        self._snapshot_ids.add(snapshot_id)
        _emit(self._events, "load_snapshot", {"snapshot_id": snapshot_id, "tenant_id": tenant_id}, snapshot_id)
        return snapshot

    # ------------------------------------------------------------------
    # Workforce assessment
    # ------------------------------------------------------------------

    def workforce_assessment(self, assessment_id: str, tenant_id: str) -> WorkforceAssessment:
        now = _now_iso()
        tenant_workers = [w for w in self._workers.values() if w.tenant_id == tenant_id]
        active = len([w for w in tenant_workers if w.status == WorkerStatus.ACTIVE])
        roles = len(set(w.role_ref for w in tenant_workers))
        teams = len(set(w.team_ref for w in tenant_workers))
        reqs = len([r for r in self._requests.values() if r.tenant_id == tenant_id])
        decs = len([d for d in self._decisions.values() if self._requests.get(d.request_id, None) and self._requests[d.request_id].tenant_id == tenant_id])
        gaps = len([g for g in self._gaps.values() if g.tenant_id == tenant_id])
        viols = len([v for v in self._violations.values() if v.tenant_id == tenant_id])

        assessment = WorkforceAssessment(
            assessment_id=assessment_id,
            tenant_id=tenant_id,
            total_workers=len(tenant_workers),
            active_workers=active,
            total_roles=roles,
            total_teams=teams,
            total_requests=reqs,
            total_decisions=decs,
            total_gaps=gaps,
            total_violations=viols,
            assessed_at=now,
        )
        _emit(self._events, "workforce_assessment", {"assessment_id": assessment_id, "tenant_id": tenant_id}, assessment_id)
        return assessment

    # ------------------------------------------------------------------
    # Violations
    # ------------------------------------------------------------------

    def detect_workforce_violations(self, tenant_id: str) -> tuple[WorkforceViolation, ...]:
        """Detect workforce violations. Idempotent per violation_id."""
        now = _now_iso()
        new_violations: list[WorkforceViolation] = []

        # 1. Overloaded workers — current_assignments >= max_assignments and ACTIVE
        for w in self._workers.values():
            if w.tenant_id == tenant_id and w.status == WorkerStatus.ACTIVE and w.current_assignments >= w.max_assignments:
                vid = stable_identifier("viol-wkf", {"type": "overloaded_worker", "worker_id": w.worker_id})
                if vid not in self._violations:
                    v = WorkforceViolation(
                        violation_id=vid,
                        tenant_id=tenant_id,
                        operation="overloaded_worker",
                        reason=f"worker {w.worker_id} at {w.current_assignments}/{w.max_assignments} assignments",
                        detected_at=now,
                    )
                    self._violations[vid] = v
                    new_violations.append(v)

        # 2. Unassigned requests — requests with no decisions
        for r in self._requests.values():
            if r.tenant_id == tenant_id:
                if not any(d.request_id == r.request_id for d in self._decisions.values()):
                    vid = stable_identifier("viol-wkf", {"type": "unassigned_request", "request_id": r.request_id})
                    if vid not in self._violations:
                        v = WorkforceViolation(
                            violation_id=vid,
                            tenant_id=tenant_id,
                            operation="unassigned_request",
                            reason=f"request {r.request_id} has no decision",
                            detected_at=now,
                        )
                        self._violations[vid] = v
                        new_violations.append(v)

        # 3. Roles with no workers
        roles_with_requests = set()
        for r in self._requests.values():
            if r.tenant_id == tenant_id:
                roles_with_requests.add(r.role_ref)
        for role_ref in roles_with_requests:
            all_role_workers = self.workers_for_role(tenant_id, role_ref)
            if not all_role_workers:
                vid = stable_identifier("viol-wkf", {"type": "empty_role", "role_ref": role_ref})
                if vid not in self._violations:
                    v = WorkforceViolation(
                        violation_id=vid,
                        tenant_id=tenant_id,
                        operation="empty_role",
                        reason=f"role {role_ref} has requests but no workers",
                        detected_at=now,
                    )
                    self._violations[vid] = v
                    new_violations.append(v)

        _emit(self._events, "detect_workforce_violations", {"tenant_id": tenant_id, "count": len(new_violations)}, tenant_id)
        return tuple(new_violations)

    def violations_for_tenant(self, tenant_id: str) -> tuple[WorkforceViolation, ...]:
        return tuple(v for v in self._violations.values() if v.tenant_id == tenant_id)

    # ------------------------------------------------------------------
    # Closure report
    # ------------------------------------------------------------------

    def closure_report(self, report_id: str, tenant_id: str) -> WorkforceClosureReport:
        now = _now_iso()
        report = WorkforceClosureReport(
            report_id=report_id,
            tenant_id=tenant_id,
            total_workers=len([w for w in self._workers.values() if w.tenant_id == tenant_id]),
            total_role_capacities=len([r for r in self._role_capacities.values() if r.tenant_id == tenant_id]),
            total_team_capacities=len([t for t in self._team_capacities.values() if t.tenant_id == tenant_id]),
            total_requests=len([r for r in self._requests.values() if r.tenant_id == tenant_id]),
            total_decisions=len([d for d in self._decisions.values() if self._requests.get(d.request_id, None) and self._requests[d.request_id].tenant_id == tenant_id]),
            total_gaps=len([g for g in self._gaps.values() if g.tenant_id == tenant_id]),
            total_violations=len([v for v in self._violations.values() if v.tenant_id == tenant_id]),
            closed_at=now,
        )
        _emit(self._events, "closure_report", {"report_id": report_id, "tenant_id": tenant_id}, report_id)
        return report

    # ------------------------------------------------------------------
    # State hash
    # ------------------------------------------------------------------

    def state_hash(self) -> str:
        parts: list[str] = []
        for k in sorted(self._workers):
            parts.append(f"w:{k}")
        for k in sorted(self._role_capacities):
            parts.append(f"rc:{k}")
        for k in sorted(self._team_capacities):
            parts.append(f"tc:{k}")
        for k in sorted(self._requests):
            parts.append(f"rq:{k}")
        for k in sorted(self._decisions):
            parts.append(f"d:{k}")
        for k in sorted(self._gaps):
            parts.append(f"g:{k}")
        for k in sorted(self._violations):
            parts.append(f"v:{k}")
        return sha256("|".join(parts).encode()).hexdigest()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _derive_capacity_status(utilization: float) -> CapacityStatus:
        if utilization >= 1.0:
            return CapacityStatus.OVERLOADED
        if utilization >= 0.9:
            return CapacityStatus.CRITICAL
        if utilization >= 0.7:
            return CapacityStatus.STRAINED
        if utilization <= 0.0:
            return CapacityStatus.EMPTY
        return CapacityStatus.NOMINAL

    @staticmethod
    def _derive_load_band(utilization: float) -> LoadBand:
        if utilization >= 1.0:
            return LoadBand.OVERLOADED
        if utilization >= 0.8:
            return LoadBand.HIGH
        if utilization >= 0.5:
            return LoadBand.MODERATE
        if utilization > 0.0:
            return LoadBand.LOW
        return LoadBand.IDLE
