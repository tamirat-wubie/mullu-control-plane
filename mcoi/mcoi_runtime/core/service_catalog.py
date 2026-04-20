"""Purpose: service catalog / request fulfillment runtime engine.
Governance scope: registering catalog items, accepting service requests,
    evaluating entitlements, routing and assigning requests, creating
    fulfillment tasks, tracking lifecycle, detecting violations, producing
    immutable snapshots and closure reports.
Dependencies: service_catalog contracts, event_spine, core invariants.
Invariants:
  - Requests must reference active catalog items.
  - Entitlement must be evaluated before fulfillment.
  - Terminal requests cannot be re-opened.
  - Every mutation emits an event.
  - All returns are immutable.
"""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from typing import Any

from ..contracts.service_catalog import (
    CatalogAssessment,
    CatalogItemKind,
    EntitlementDisposition,
    EntitlementRule,
    FulfillmentDecision,
    FulfillmentStatus,
    FulfillmentTask,
    RequestAssignment,
    RequestPriority,
    RequestSnapshot,
    RequestStatus,
    RequestViolation,
    ServiceCatalogItem,
    ServiceClosureReport,
    ServiceRequest,
    ServiceStatus,
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
        event_id=stable_identifier("evt-scat", {"action": action, "ts": now, "cid": cid}),
        event_type=EventType.CUSTOM,
        source=EventSource.COMMUNICATION_SYSTEM,
        correlation_id=cid,
        payload=payload,
        emitted_at=now,
    )
    es.emit(event)
    return event


_REQUEST_TERMINAL = frozenset({RequestStatus.FULFILLED, RequestStatus.DENIED, RequestStatus.CANCELLED})
_TASK_TERMINAL = frozenset({FulfillmentStatus.COMPLETED, FulfillmentStatus.FAILED, FulfillmentStatus.CANCELLED})


class ServiceCatalogEngine:
    """Service catalog and request fulfillment engine."""

    def __init__(self, event_spine: EventSpineEngine) -> None:
        if not isinstance(event_spine, EventSpineEngine):
            raise RuntimeCoreInvariantError("event_spine must be an EventSpineEngine")
        self._events = event_spine
        self._catalog: dict[str, ServiceCatalogItem] = {}
        self._requests: dict[str, ServiceRequest] = {}
        self._assignments: dict[str, RequestAssignment] = {}
        self._entitlements: dict[str, EntitlementRule] = {}
        self._tasks: dict[str, FulfillmentTask] = {}
        self._decisions: dict[str, FulfillmentDecision] = {}
        self._violations: dict[str, RequestViolation] = {}
        self._assessments: dict[str, CatalogAssessment] = {}
        self._snapshot_ids: set[str] = set()

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def catalog_count(self) -> int:
        return len(self._catalog)

    @property
    def request_count(self) -> int:
        return len(self._requests)

    @property
    def assignment_count(self) -> int:
        return len(self._assignments)

    @property
    def entitlement_count(self) -> int:
        return len(self._entitlements)

    @property
    def task_count(self) -> int:
        return len(self._tasks)

    @property
    def decision_count(self) -> int:
        return len(self._decisions)

    @property
    def violation_count(self) -> int:
        return len(self._violations)

    @property
    def assessment_count(self) -> int:
        return len(self._assessments)

    # ------------------------------------------------------------------
    # Catalog items
    # ------------------------------------------------------------------

    def register_catalog_item(
        self,
        item_id: str,
        name: str,
        tenant_id: str,
        *,
        kind: CatalogItemKind = CatalogItemKind.INFRASTRUCTURE,
        owner_ref: str = "",
        sla_ref: str = "",
        approval_required: bool = False,
        estimated_cost: float = 0.0,
    ) -> ServiceCatalogItem:
        """Register a service catalog item."""
        if item_id in self._catalog:
            raise RuntimeCoreInvariantError("Duplicate item_id")
        now = _now_iso()
        item = ServiceCatalogItem(
            item_id=item_id, name=name, tenant_id=tenant_id,
            kind=kind, status=ServiceStatus.ACTIVE,
            owner_ref=owner_ref, sla_ref=sla_ref,
            approval_required=approval_required,
            estimated_cost=estimated_cost, created_at=now,
        )
        self._catalog[item_id] = item
        _emit(self._events, "catalog_item_registered", {
            "item_id": item_id, "name": name, "kind": kind.value,
        }, item_id)
        return item

    def get_catalog_item(self, item_id: str) -> ServiceCatalogItem:
        """Get a catalog item by ID."""
        item = self._catalog.get(item_id)
        if item is None:
            raise RuntimeCoreInvariantError("Unknown item_id")
        return item

    def deprecate_catalog_item(self, item_id: str) -> ServiceCatalogItem:
        """Deprecate a catalog item."""
        old = self.get_catalog_item(item_id)
        if old.status != ServiceStatus.ACTIVE:
            raise RuntimeCoreInvariantError("Can only deprecate active catalog items")
        updated = ServiceCatalogItem(
            item_id=old.item_id, name=old.name, tenant_id=old.tenant_id,
            kind=old.kind, status=ServiceStatus.DEPRECATED,
            owner_ref=old.owner_ref, sla_ref=old.sla_ref,
            approval_required=old.approval_required,
            estimated_cost=old.estimated_cost, created_at=old.created_at,
            metadata=old.metadata,
        )
        self._catalog[item_id] = updated
        _emit(self._events, "catalog_item_deprecated", {"item_id": item_id}, item_id)
        return updated

    def retire_catalog_item(self, item_id: str) -> ServiceCatalogItem:
        """Retire a catalog item."""
        old = self.get_catalog_item(item_id)
        if old.status == ServiceStatus.RETIRED:
            raise RuntimeCoreInvariantError("Item already retired")
        updated = ServiceCatalogItem(
            item_id=old.item_id, name=old.name, tenant_id=old.tenant_id,
            kind=old.kind, status=ServiceStatus.RETIRED,
            owner_ref=old.owner_ref, sla_ref=old.sla_ref,
            approval_required=old.approval_required,
            estimated_cost=old.estimated_cost, created_at=old.created_at,
            metadata=old.metadata,
        )
        self._catalog[item_id] = updated
        _emit(self._events, "catalog_item_retired", {"item_id": item_id}, item_id)
        return updated

    def catalog_items_for_tenant(self, tenant_id: str) -> tuple[ServiceCatalogItem, ...]:
        """Return all catalog items for a tenant."""
        return tuple(i for i in self._catalog.values() if i.tenant_id == tenant_id)

    # ------------------------------------------------------------------
    # Requests
    # ------------------------------------------------------------------

    def submit_request(
        self,
        request_id: str,
        item_id: str,
        tenant_id: str,
        requester_ref: str,
        *,
        priority: RequestPriority = RequestPriority.MEDIUM,
        description: str = "",
        estimated_cost: float = 0.0,
        due_at: str = "",
    ) -> ServiceRequest:
        """Submit a new service request."""
        if request_id in self._requests:
            raise RuntimeCoreInvariantError("Duplicate request_id")
        item = self.get_catalog_item(item_id)
        if item.status != ServiceStatus.ACTIVE:
            raise RuntimeCoreInvariantError("Cannot request from non-active catalog item")
        now = _now_iso()
        status = RequestStatus.SUBMITTED
        req = ServiceRequest(
            request_id=request_id, item_id=item_id, tenant_id=tenant_id,
            requester_ref=requester_ref, status=status, priority=priority,
            description=description, estimated_cost=estimated_cost or item.estimated_cost,
            submitted_at=now, due_at=due_at or now,
        )
        self._requests[request_id] = req
        _emit(self._events, "request_submitted", {
            "request_id": request_id, "item_id": item_id,
            "priority": priority.value,
        }, request_id)
        return req

    def get_request(self, request_id: str) -> ServiceRequest:
        """Get a request by ID."""
        req = self._requests.get(request_id)
        if req is None:
            raise RuntimeCoreInvariantError("Unknown request_id")
        return req

    def _update_request_status(self, request_id: str, new_status: RequestStatus) -> ServiceRequest:
        """Internal helper to update request status."""
        old = self.get_request(request_id)
        updated = ServiceRequest(
            request_id=old.request_id, item_id=old.item_id,
            tenant_id=old.tenant_id, requester_ref=old.requester_ref,
            status=new_status, priority=old.priority,
            description=old.description, estimated_cost=old.estimated_cost,
            submitted_at=old.submitted_at, due_at=old.due_at,
            metadata=old.metadata,
        )
        self._requests[request_id] = updated
        return updated

    # ------------------------------------------------------------------
    # Entitlement evaluation
    # ------------------------------------------------------------------

    def evaluate_entitlement(
        self,
        rule_id: str,
        request_id: str,
        *,
        disposition: EntitlementDisposition = EntitlementDisposition.GRANTED,
        scope_ref: str = "",
        reason: str = "",
    ) -> EntitlementRule:
        """Evaluate entitlement for a request."""
        if rule_id in self._entitlements:
            raise RuntimeCoreInvariantError("Duplicate rule_id")
        req = self.get_request(request_id)
        if req.status in _REQUEST_TERMINAL:
            raise RuntimeCoreInvariantError("Cannot evaluate entitlement for terminal request")
        now = _now_iso()
        rule = EntitlementRule(
            rule_id=rule_id, item_id=req.item_id, tenant_id=req.tenant_id,
            disposition=disposition, scope_ref=scope_ref,
            reason=reason, evaluated_at=now,
        )
        self._entitlements[rule_id] = rule

        # Update request status based on disposition
        if disposition == EntitlementDisposition.GRANTED:
            # Check if catalog item requires approval
            item = self.get_catalog_item(req.item_id)
            if item.approval_required:
                self._update_request_status(request_id, RequestStatus.PENDING_APPROVAL)
            else:
                self._update_request_status(request_id, RequestStatus.ENTITLED)
        elif disposition == EntitlementDisposition.REQUIRES_APPROVAL:
            self._update_request_status(request_id, RequestStatus.PENDING_APPROVAL)
        elif disposition == EntitlementDisposition.DENIED:
            self._update_request_status(request_id, RequestStatus.DENIED)
            # Record denial decision
            dec_id = stable_identifier("dec-ent", {"rule": rule_id, "req": request_id})
            decision = FulfillmentDecision(
                decision_id=dec_id, request_id=request_id,
                disposition="denied", decided_by="entitlement_engine",
                reason=reason or "Entitlement denied",
                decided_at=now,
            )
            self._decisions[dec_id] = decision
        elif disposition == EntitlementDisposition.EXPIRED:
            self._update_request_status(request_id, RequestStatus.DENIED)

        _emit(self._events, "entitlement_evaluated", {
            "rule_id": rule_id, "request_id": request_id,
            "disposition": disposition.value,
        }, request_id)
        return rule

    # ------------------------------------------------------------------
    # Approval
    # ------------------------------------------------------------------

    def approve_request(
        self,
        request_id: str,
        *,
        approved_by: str = "system",
        reason: str = "",
    ) -> ServiceRequest:
        """Approve a pending-approval request."""
        req = self.get_request(request_id)
        if req.status != RequestStatus.PENDING_APPROVAL:
            raise RuntimeCoreInvariantError("Can only approve pending-approval requests")
        if req.requester_ref.strip() == approved_by.strip():
            raise RuntimeCoreInvariantError("Requester cannot approve own request")
        now = _now_iso()
        dec_id = stable_identifier("dec-appr", {"req": request_id, "ts": now})
        decision = FulfillmentDecision(
            decision_id=dec_id, request_id=request_id,
            disposition="approved", decided_by=approved_by,
            reason=reason or "Request approved",
            decided_at=now,
        )
        self._decisions[dec_id] = decision
        updated = self._update_request_status(request_id, RequestStatus.APPROVED)
        _emit(self._events, "request_approved", {
            "request_id": request_id, "approved_by": approved_by,
        }, request_id)
        return updated

    def deny_request(
        self,
        request_id: str,
        *,
        denied_by: str = "system",
        reason: str = "",
    ) -> ServiceRequest:
        """Deny a request."""
        req = self.get_request(request_id)
        if req.status in _REQUEST_TERMINAL:
            raise RuntimeCoreInvariantError("Cannot deny terminal request")
        now = _now_iso()
        dec_id = stable_identifier("dec-deny", {"req": request_id, "ts": now})
        decision = FulfillmentDecision(
            decision_id=dec_id, request_id=request_id,
            disposition="denied", decided_by=denied_by,
            reason=reason or "Request denied",
            decided_at=now,
        )
        self._decisions[dec_id] = decision
        updated = self._update_request_status(request_id, RequestStatus.DENIED)
        _emit(self._events, "request_denied", {
            "request_id": request_id, "denied_by": denied_by,
        }, request_id)
        return updated

    def cancel_request(self, request_id: str) -> ServiceRequest:
        """Cancel a request."""
        req = self.get_request(request_id)
        if req.status in _REQUEST_TERMINAL:
            raise RuntimeCoreInvariantError("Cannot cancel terminal request")
        updated = self._update_request_status(request_id, RequestStatus.CANCELLED)
        _emit(self._events, "request_cancelled", {"request_id": request_id}, request_id)
        return updated

    # ------------------------------------------------------------------
    # Assignment
    # ------------------------------------------------------------------

    def assign_request(
        self,
        assignment_id: str,
        request_id: str,
        assignee_ref: str,
        *,
        assigned_by: str = "system",
    ) -> RequestAssignment:
        """Assign a request to an assignee."""
        if assignment_id in self._assignments:
            raise RuntimeCoreInvariantError("Duplicate assignment_id")
        req = self.get_request(request_id)
        if req.status in _REQUEST_TERMINAL:
            raise RuntimeCoreInvariantError("Cannot assign terminal request")
        now = _now_iso()
        assignment = RequestAssignment(
            assignment_id=assignment_id, request_id=request_id,
            assignee_ref=assignee_ref, assigned_by=assigned_by,
            assigned_at=now,
        )
        self._assignments[assignment_id] = assignment
        _emit(self._events, "request_assigned", {
            "assignment_id": assignment_id, "request_id": request_id,
            "assignee_ref": assignee_ref,
        }, request_id)
        return assignment

    def assignments_for_request(self, request_id: str) -> tuple[RequestAssignment, ...]:
        """Return all assignments for a request."""
        return tuple(a for a in self._assignments.values() if a.request_id == request_id)

    # ------------------------------------------------------------------
    # Fulfillment tasks
    # ------------------------------------------------------------------

    def create_fulfillment_task(
        self,
        task_id: str,
        request_id: str,
        assignee_ref: str,
        *,
        description: str = "",
        dependency_ref: str = "",
    ) -> FulfillmentTask:
        """Create a fulfillment task for a request."""
        if task_id in self._tasks:
            raise RuntimeCoreInvariantError("Duplicate task_id")
        req = self.get_request(request_id)
        if req.status in _REQUEST_TERMINAL:
            raise RuntimeCoreInvariantError("Cannot create task for terminal request")
        # Auto-transition to IN_FULFILLMENT if not already
        if req.status not in (RequestStatus.IN_FULFILLMENT, RequestStatus.DENIED, RequestStatus.CANCELLED):
            self._update_request_status(request_id, RequestStatus.IN_FULFILLMENT)
        now = _now_iso()
        task = FulfillmentTask(
            task_id=task_id, request_id=request_id,
            assignee_ref=assignee_ref, status=FulfillmentStatus.PENDING,
            description=description, dependency_ref=dependency_ref,
            created_at=now,
        )
        self._tasks[task_id] = task
        _emit(self._events, "fulfillment_task_created", {
            "task_id": task_id, "request_id": request_id,
        }, request_id)
        return task

    def get_task(self, task_id: str) -> FulfillmentTask:
        """Get a fulfillment task by ID."""
        task = self._tasks.get(task_id)
        if task is None:
            raise RuntimeCoreInvariantError("Unknown task_id")
        return task

    def start_task(self, task_id: str) -> FulfillmentTask:
        """Start a fulfillment task."""
        old = self.get_task(task_id)
        if old.status != FulfillmentStatus.PENDING:
            raise RuntimeCoreInvariantError("Can only start pending tasks")
        updated = FulfillmentTask(
            task_id=old.task_id, request_id=old.request_id,
            assignee_ref=old.assignee_ref, status=FulfillmentStatus.IN_PROGRESS,
            description=old.description, dependency_ref=old.dependency_ref,
            created_at=old.created_at, metadata=old.metadata,
        )
        self._tasks[task_id] = updated
        _emit(self._events, "task_started", {"task_id": task_id}, old.request_id)
        return updated

    def complete_task(self, task_id: str) -> FulfillmentTask:
        """Complete a fulfillment task."""
        old = self.get_task(task_id)
        if old.status in _TASK_TERMINAL:
            raise RuntimeCoreInvariantError("Task already in terminal status")
        now = _now_iso()
        updated = FulfillmentTask(
            task_id=old.task_id, request_id=old.request_id,
            assignee_ref=old.assignee_ref, status=FulfillmentStatus.COMPLETED,
            description=old.description, dependency_ref=old.dependency_ref,
            created_at=old.created_at, completed_at=now,
            metadata=old.metadata,
        )
        self._tasks[task_id] = updated
        _emit(self._events, "task_completed", {"task_id": task_id}, old.request_id)

        # Auto-fulfill request if all tasks completed
        request_tasks = [t for t in self._tasks.values() if t.request_id == old.request_id]
        all_done = all(t.status == FulfillmentStatus.COMPLETED for t in request_tasks)
        if all_done:
            req = self.get_request(old.request_id)
            if req.status == RequestStatus.IN_FULFILLMENT:
                self._update_request_status(old.request_id, RequestStatus.FULFILLED)
                _emit(self._events, "request_fulfilled", {
                    "request_id": old.request_id,
                }, old.request_id)

        return updated

    def fail_task(self, task_id: str) -> FulfillmentTask:
        """Mark a fulfillment task as failed."""
        old = self.get_task(task_id)
        if old.status in _TASK_TERMINAL:
            raise RuntimeCoreInvariantError("Task already in terminal status")
        now = _now_iso()
        updated = FulfillmentTask(
            task_id=old.task_id, request_id=old.request_id,
            assignee_ref=old.assignee_ref, status=FulfillmentStatus.FAILED,
            description=old.description, dependency_ref=old.dependency_ref,
            created_at=old.created_at, completed_at=now,
            metadata=old.metadata,
        )
        self._tasks[task_id] = updated
        _emit(self._events, "task_failed", {"task_id": task_id}, old.request_id)
        return updated

    def cancel_task(self, task_id: str) -> FulfillmentTask:
        """Cancel a fulfillment task."""
        old = self.get_task(task_id)
        if old.status in _TASK_TERMINAL:
            raise RuntimeCoreInvariantError("Task already in terminal status")
        updated = FulfillmentTask(
            task_id=old.task_id, request_id=old.request_id,
            assignee_ref=old.assignee_ref, status=FulfillmentStatus.CANCELLED,
            description=old.description, dependency_ref=old.dependency_ref,
            created_at=old.created_at, metadata=old.metadata,
        )
        self._tasks[task_id] = updated
        _emit(self._events, "task_cancelled", {"task_id": task_id}, old.request_id)
        return updated

    def tasks_for_request(self, request_id: str) -> tuple[FulfillmentTask, ...]:
        """Return all tasks for a request."""
        return tuple(t for t in self._tasks.values() if t.request_id == request_id)

    # ------------------------------------------------------------------
    # Request closure
    # ------------------------------------------------------------------

    def close_request(self, request_id: str) -> ServiceRequest:
        """Close a request (mark as fulfilled)."""
        req = self.get_request(request_id)
        if req.status in _REQUEST_TERMINAL:
            raise RuntimeCoreInvariantError("Request already in terminal status")
        updated = self._update_request_status(request_id, RequestStatus.FULFILLED)
        _emit(self._events, "request_closed", {"request_id": request_id}, request_id)
        return updated

    def requests_for_tenant(self, tenant_id: str) -> tuple[ServiceRequest, ...]:
        """Return all requests for a tenant."""
        return tuple(r for r in self._requests.values() if r.tenant_id == tenant_id)

    # ------------------------------------------------------------------
    # Assessments
    # ------------------------------------------------------------------

    def assess_catalog_item(
        self,
        assessment_id: str,
        item_id: str,
        fulfillment_rate: float,
        satisfaction_score: float,
        *,
        assessed_by: str = "system",
    ) -> CatalogAssessment:
        """Assess a catalog item's health."""
        if assessment_id in self._assessments:
            raise RuntimeCoreInvariantError("Duplicate assessment_id")
        if item_id not in self._catalog:
            raise RuntimeCoreInvariantError("Unknown item_id")
        now = _now_iso()
        assessment = CatalogAssessment(
            assessment_id=assessment_id, item_id=item_id,
            fulfillment_rate=fulfillment_rate,
            satisfaction_score=satisfaction_score,
            assessed_by=assessed_by, assessed_at=now,
        )
        self._assessments[assessment_id] = assessment
        _emit(self._events, "catalog_item_assessed", {
            "assessment_id": assessment_id, "item_id": item_id,
        }, item_id)
        return assessment

    def assessments_for_item(self, item_id: str) -> tuple[CatalogAssessment, ...]:
        """Return all assessments for a catalog item."""
        return tuple(a for a in self._assessments.values() if a.item_id == item_id)

    # ------------------------------------------------------------------
    # Violation detection
    # ------------------------------------------------------------------

    def detect_request_violations(self) -> tuple[RequestViolation, ...]:
        """Detect request and fulfillment violations."""
        now = _now_iso()
        new_violations: list[RequestViolation] = []

        # Requests in fulfillment with all tasks failed
        for req in self._requests.values():
            if req.status == RequestStatus.IN_FULFILLMENT:
                req_tasks = [t for t in self._tasks.values() if t.request_id == req.request_id]
                if req_tasks and all(t.status == FulfillmentStatus.FAILED for t in req_tasks):
                    vid = stable_identifier("viol-scat", {
                        "req": req.request_id, "op": "all_tasks_failed",
                    })
                    if vid not in self._violations:
                        v = RequestViolation(
                            violation_id=vid, request_id=req.request_id,
                            tenant_id=req.tenant_id,
                            operation="all_tasks_failed",
                            reason="All fulfillment tasks failed",
                            detected_at=now,
                        )
                        self._violations[vid] = v
                        new_violations.append(v)

        # Requests submitted but never entitled (stuck)
        for req in self._requests.values():
            if req.status == RequestStatus.SUBMITTED:
                has_entitlement = any(
                    e.item_id == req.item_id and e.tenant_id == req.tenant_id
                    for e in self._entitlements.values()
                )
                if not has_entitlement:
                    vid = stable_identifier("viol-scat", {
                        "req": req.request_id, "op": "no_entitlement",
                    })
                    if vid not in self._violations:
                        v = RequestViolation(
                            violation_id=vid, request_id=req.request_id,
                            tenant_id=req.tenant_id,
                            operation="no_entitlement",
                            reason="Request lacks entitlement evaluation",
                            detected_at=now,
                        )
                        self._violations[vid] = v
                        new_violations.append(v)

        # Requests in fulfillment with no tasks
        for req in self._requests.values():
            if req.status == RequestStatus.IN_FULFILLMENT:
                req_tasks = [t for t in self._tasks.values() if t.request_id == req.request_id]
                if not req_tasks:
                    vid = stable_identifier("viol-scat", {
                        "req": req.request_id, "op": "no_tasks",
                    })
                    if vid not in self._violations:
                        v = RequestViolation(
                            violation_id=vid, request_id=req.request_id,
                            tenant_id=req.tenant_id,
                            operation="no_tasks",
                            reason="Request in fulfillment has no tasks",
                            detected_at=now,
                        )
                        self._violations[vid] = v
                        new_violations.append(v)

        if new_violations:
            _emit(self._events, "request_violations_detected", {
                "count": len(new_violations),
            }, "violation-scan")
        return tuple(new_violations)

    def violations_for_request(self, request_id: str) -> tuple[RequestViolation, ...]:
        """Return all violations for a request."""
        return tuple(v for v in self._violations.values() if v.request_id == request_id)

    # ------------------------------------------------------------------
    # Snapshot
    # ------------------------------------------------------------------

    def request_snapshot(self, snapshot_id: str) -> RequestSnapshot:
        """Capture a point-in-time request snapshot."""
        if snapshot_id in self._snapshot_ids:
            raise RuntimeCoreInvariantError("Duplicate snapshot_id")
        now = _now_iso()
        total_cost = sum(
            r.estimated_cost for r in self._requests.values()
            if r.status not in _REQUEST_TERMINAL
        )
        snap = RequestSnapshot(
            snapshot_id=snapshot_id,
            total_catalog_items=self.catalog_count,
            total_requests=self.request_count,
            total_submitted=sum(1 for r in self._requests.values() if r.status == RequestStatus.SUBMITTED),
            total_in_fulfillment=sum(1 for r in self._requests.values() if r.status == RequestStatus.IN_FULFILLMENT),
            total_fulfilled=sum(1 for r in self._requests.values() if r.status == RequestStatus.FULFILLED),
            total_denied=sum(1 for r in self._requests.values() if r.status == RequestStatus.DENIED),
            total_tasks=self.task_count,
            total_violations=self.violation_count,
            total_estimated_cost=total_cost,
            captured_at=now,
        )
        self._snapshot_ids.add(snapshot_id)
        _emit(self._events, "request_snapshot_captured", {
            "snapshot_id": snapshot_id,
        }, snapshot_id)
        return snap

    # ------------------------------------------------------------------
    # State hash
    # ------------------------------------------------------------------

    def state_hash(self) -> str:
        """Compute a hash of the current engine state."""
        parts = [
            f"catalog={self.catalog_count}",
            f"requests={self.request_count}",
            f"assignments={self.assignment_count}",
            f"entitlements={self.entitlement_count}",
            f"tasks={self.task_count}",
            f"decisions={self.decision_count}",
            f"violations={self.violation_count}",
            f"assessments={self.assessment_count}",
        ]
        return sha256("|".join(parts).encode()).hexdigest()
