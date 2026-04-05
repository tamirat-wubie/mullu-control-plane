"""Purpose: UI / operator workspace runtime engine.
Governance scope: registering views/panels/queues, assembling worklists,
    managing operator actions, enforcing scope-safe visibility,
    detecting violations, producing snapshots.
Dependencies: operator_workspace contracts, event_spine, core invariants.
Invariants:
  - Duplicate IDs raise.
  - Cross-tenant workspace access is denied fail-closed.
  - Every mutation emits an event.
  - All returns are immutable.
"""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from typing import Any

from ..contracts.operator_workspace import (
    OperatorAction,
    OperatorActionStatus,
    PanelKind,
    QueueRecord,
    QueueStatus,
    ViewDisposition,
    WorklistItem,
    WorkspaceAssessment,
    WorkspaceClosureReport,
    WorkspaceDecision,
    WorkspacePanel,
    WorkspaceScope,
    WorkspaceSnapshot,
    WorkspaceStatus,
    WorkspaceView,
    WorkspaceViolation,
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
        event_id=stable_identifier("evt-wks", {"action": action, "ts": now, "cid": cid}),
        event_type=EventType.CUSTOM,
        source=EventSource.COMMUNICATION_SYSTEM,
        correlation_id=cid,
        payload=payload,
        emitted_at=now,
    )
    es.emit(event)
    return event


_VIEW_TERMINAL = frozenset({WorkspaceStatus.RETIRED})
_QUEUE_TERMINAL = frozenset({QueueStatus.COMPLETED})
_ACTION_TERMINAL = frozenset({OperatorActionStatus.COMPLETED, OperatorActionStatus.FAILED, OperatorActionStatus.CANCELLED})


class OperatorWorkspaceEngine:
    """UI / operator workspace runtime engine."""

    def __init__(self, event_spine: EventSpineEngine) -> None:
        if not isinstance(event_spine, EventSpineEngine):
            raise RuntimeCoreInvariantError("event_spine must be an EventSpineEngine")
        self._events = event_spine
        self._views: dict[str, WorkspaceView] = {}
        self._panels: dict[str, WorkspacePanel] = {}
        self._queues: dict[str, QueueRecord] = {}
        self._worklist: dict[str, WorklistItem] = {}
        self._actions: dict[str, OperatorAction] = {}
        self._decisions: dict[str, WorkspaceDecision] = {}
        self._violations: dict[str, WorkspaceViolation] = {}
        self._assessments: dict[str, WorkspaceAssessment] = {}

    # -- Properties ----------------------------------------------------------

    @property
    def view_count(self) -> int:
        return len(self._views)

    @property
    def panel_count(self) -> int:
        return len(self._panels)

    @property
    def queue_count(self) -> int:
        return len(self._queues)

    @property
    def worklist_count(self) -> int:
        return len(self._worklist)

    @property
    def action_count(self) -> int:
        return len(self._actions)

    @property
    def decision_count(self) -> int:
        return len(self._decisions)

    @property
    def violation_count(self) -> int:
        return len(self._violations)

    @property
    def assessment_count(self) -> int:
        return len(self._assessments)

    # -- Views ---------------------------------------------------------------

    def register_view(
        self,
        view_id: str,
        tenant_id: str,
        operator_ref: str,
        display_name: str,
        scope: WorkspaceScope = WorkspaceScope.PERSONAL,
    ) -> WorkspaceView:
        if view_id in self._views:
            raise RuntimeCoreInvariantError("duplicate view_id")
        now = _now_iso()
        view = WorkspaceView(
            view_id=view_id, tenant_id=tenant_id, operator_ref=operator_ref,
            display_name=display_name, scope=scope,
            disposition=ViewDisposition.OPEN, status=WorkspaceStatus.ACTIVE,
            panel_count=0, created_at=now,
        )
        self._views[view_id] = view
        _emit(self._events, "register_view", {"view_id": view_id, "tenant_id": tenant_id}, view_id)
        return view

    def get_view(self, view_id: str) -> WorkspaceView:
        if view_id not in self._views:
            raise RuntimeCoreInvariantError("unknown view_id")
        return self._views[view_id]

    def suspend_view(self, view_id: str) -> WorkspaceView:
        view = self.get_view(view_id)
        if view.status in _VIEW_TERMINAL:
            raise RuntimeCoreInvariantError("view is retired")
        now = _now_iso()
        updated = WorkspaceView(
            view_id=view.view_id, tenant_id=view.tenant_id, operator_ref=view.operator_ref,
            display_name=view.display_name, scope=view.scope,
            disposition=view.disposition, status=WorkspaceStatus.SUSPENDED,
            panel_count=view.panel_count, created_at=now,
        )
        self._views[view_id] = updated
        _emit(self._events, "suspend_view", {"view_id": view_id}, view_id)
        return updated

    def retire_view(self, view_id: str) -> WorkspaceView:
        view = self.get_view(view_id)
        if view.status == WorkspaceStatus.RETIRED:
            raise RuntimeCoreInvariantError("view already retired")
        now = _now_iso()
        updated = WorkspaceView(
            view_id=view.view_id, tenant_id=view.tenant_id, operator_ref=view.operator_ref,
            display_name=view.display_name, scope=view.scope,
            disposition=ViewDisposition.ARCHIVED, status=WorkspaceStatus.RETIRED,
            panel_count=view.panel_count, created_at=now,
        )
        self._views[view_id] = updated
        _emit(self._events, "retire_view", {"view_id": view_id}, view_id)
        return updated

    def views_for_tenant(self, tenant_id: str) -> tuple[WorkspaceView, ...]:
        return tuple(v for v in self._views.values() if v.tenant_id == tenant_id)

    def views_for_operator(self, tenant_id: str, operator_ref: str) -> tuple[WorkspaceView, ...]:
        return tuple(v for v in self._views.values() if v.tenant_id == tenant_id and v.operator_ref == operator_ref)

    # -- Panels --------------------------------------------------------------

    def register_panel(
        self,
        panel_id: str,
        view_id: str,
        tenant_id: str,
        display_name: str,
        kind: PanelKind = PanelKind.QUEUE,
        target_runtime: str = "unknown",
    ) -> WorkspacePanel:
        if panel_id in self._panels:
            raise RuntimeCoreInvariantError("duplicate panel_id")
        if view_id not in self._views:
            raise RuntimeCoreInvariantError("unknown view_id")
        view = self._views[view_id]
        if view.status in _VIEW_TERMINAL:
            raise RuntimeCoreInvariantError("view is retired")
        # Cross-tenant check
        if view.tenant_id != tenant_id:
            raise RuntimeCoreInvariantError("cross-tenant panel creation denied")
        now = _now_iso()
        panel = WorkspacePanel(
            panel_id=panel_id, view_id=view_id, tenant_id=tenant_id,
            display_name=display_name, kind=kind, target_runtime=target_runtime,
            item_count=0, created_at=now,
        )
        self._panels[panel_id] = panel
        # Increment view panel count
        updated_view = WorkspaceView(
            view_id=view.view_id, tenant_id=view.tenant_id, operator_ref=view.operator_ref,
            display_name=view.display_name, scope=view.scope,
            disposition=view.disposition, status=view.status,
            panel_count=view.panel_count + 1, created_at=view.created_at,
        )
        self._views[view_id] = updated_view
        _emit(self._events, "register_panel", {"panel_id": panel_id, "view_id": view_id}, panel_id)
        return panel

    def get_panel(self, panel_id: str) -> WorkspacePanel:
        if panel_id not in self._panels:
            raise RuntimeCoreInvariantError("unknown panel_id")
        return self._panels[panel_id]

    def panels_for_view(self, view_id: str) -> tuple[WorkspacePanel, ...]:
        return tuple(p for p in self._panels.values() if p.view_id == view_id)

    # -- Queues --------------------------------------------------------------

    def enqueue_item(
        self,
        queue_id: str,
        panel_id: str,
        tenant_id: str,
        source_ref: str,
        source_runtime: str,
        assignee_ref: str = "unassigned",
        priority: int = 0,
    ) -> QueueRecord:
        if queue_id in self._queues:
            raise RuntimeCoreInvariantError("duplicate queue_id")
        if panel_id not in self._panels:
            raise RuntimeCoreInvariantError("unknown panel_id")
        panel = self._panels[panel_id]
        if panel.tenant_id != tenant_id:
            raise RuntimeCoreInvariantError("cross-tenant queue access denied")
        now = _now_iso()
        item = QueueRecord(
            queue_id=queue_id, panel_id=panel_id, tenant_id=tenant_id,
            source_ref=source_ref, source_runtime=source_runtime,
            assignee_ref=assignee_ref, priority=priority,
            status=QueueStatus.PENDING, created_at=now,
        )
        self._queues[queue_id] = item
        # Increment panel item count
        updated_panel = WorkspacePanel(
            panel_id=panel.panel_id, view_id=panel.view_id, tenant_id=panel.tenant_id,
            display_name=panel.display_name, kind=panel.kind,
            target_runtime=panel.target_runtime,
            item_count=panel.item_count + 1, created_at=panel.created_at,
        )
        self._panels[panel_id] = updated_panel
        _emit(self._events, "enqueue_item", {"queue_id": queue_id, "source_ref": source_ref}, queue_id)
        return item

    def assign_queue_item(self, queue_id: str, assignee_ref: str) -> QueueRecord:
        item = self._get_queue(queue_id)
        if item.status in _QUEUE_TERMINAL:
            raise RuntimeCoreInvariantError("queue item is completed")
        now = _now_iso()
        updated = QueueRecord(
            queue_id=item.queue_id, panel_id=item.panel_id, tenant_id=item.tenant_id,
            source_ref=item.source_ref, source_runtime=item.source_runtime,
            assignee_ref=assignee_ref, priority=item.priority,
            status=QueueStatus.ASSIGNED, created_at=now,
        )
        self._queues[queue_id] = updated
        _emit(self._events, "assign_queue_item", {"queue_id": queue_id, "assignee": assignee_ref}, queue_id)
        return updated

    def start_queue_item(self, queue_id: str) -> QueueRecord:
        item = self._get_queue(queue_id)
        if item.status in _QUEUE_TERMINAL:
            raise RuntimeCoreInvariantError("queue item is completed")
        now = _now_iso()
        updated = QueueRecord(
            queue_id=item.queue_id, panel_id=item.panel_id, tenant_id=item.tenant_id,
            source_ref=item.source_ref, source_runtime=item.source_runtime,
            assignee_ref=item.assignee_ref, priority=item.priority,
            status=QueueStatus.IN_PROGRESS, created_at=now,
        )
        self._queues[queue_id] = updated
        _emit(self._events, "start_queue_item", {"queue_id": queue_id}, queue_id)
        return updated

    def complete_queue_item(self, queue_id: str) -> QueueRecord:
        item = self._get_queue(queue_id)
        if item.status in _QUEUE_TERMINAL:
            raise RuntimeCoreInvariantError("queue item already completed")
        now = _now_iso()
        updated = QueueRecord(
            queue_id=item.queue_id, panel_id=item.panel_id, tenant_id=item.tenant_id,
            source_ref=item.source_ref, source_runtime=item.source_runtime,
            assignee_ref=item.assignee_ref, priority=item.priority,
            status=QueueStatus.COMPLETED, created_at=now,
        )
        self._queues[queue_id] = updated
        _emit(self._events, "complete_queue_item", {"queue_id": queue_id}, queue_id)
        return updated

    def escalate_queue_item(self, queue_id: str) -> QueueRecord:
        item = self._get_queue(queue_id)
        if item.status in _QUEUE_TERMINAL:
            raise RuntimeCoreInvariantError("queue item is completed")
        now = _now_iso()
        updated = QueueRecord(
            queue_id=item.queue_id, panel_id=item.panel_id, tenant_id=item.tenant_id,
            source_ref=item.source_ref, source_runtime=item.source_runtime,
            assignee_ref=item.assignee_ref, priority=item.priority,
            status=QueueStatus.ESCALATED, created_at=now,
        )
        self._queues[queue_id] = updated
        _emit(self._events, "escalate_queue_item", {"queue_id": queue_id}, queue_id)
        return updated

    def _get_queue(self, queue_id: str) -> QueueRecord:
        if queue_id not in self._queues:
            raise RuntimeCoreInvariantError("unknown queue_id")
        return self._queues[queue_id]

    def queue_items_for_panel(self, panel_id: str) -> tuple[QueueRecord, ...]:
        items = [q for q in self._queues.values() if q.panel_id == panel_id]
        items.sort(key=lambda q: (-q.priority, q.created_at))
        return tuple(items)

    def pending_queue_items(self, tenant_id: str) -> tuple[QueueRecord, ...]:
        return tuple(q for q in self._queues.values() if q.tenant_id == tenant_id and q.status == QueueStatus.PENDING)

    # -- Worklist ------------------------------------------------------------

    def add_worklist_item(
        self,
        item_id: str,
        tenant_id: str,
        operator_ref: str,
        source_ref: str,
        source_runtime: str,
        title: str,
        priority: int = 0,
    ) -> WorklistItem:
        if item_id in self._worklist:
            raise RuntimeCoreInvariantError("duplicate item_id")
        now = _now_iso()
        item = WorklistItem(
            item_id=item_id, tenant_id=tenant_id, operator_ref=operator_ref,
            source_ref=source_ref, source_runtime=source_runtime,
            title=title, priority=priority, status=QueueStatus.PENDING,
            created_at=now,
        )
        self._worklist[item_id] = item
        _emit(self._events, "add_worklist_item", {"item_id": item_id, "title": title}, item_id)
        return item

    def complete_worklist_item(self, item_id: str) -> WorklistItem:
        if item_id not in self._worklist:
            raise RuntimeCoreInvariantError("unknown item_id")
        item = self._worklist[item_id]
        if item.status == QueueStatus.COMPLETED:
            raise RuntimeCoreInvariantError("worklist item already completed")
        now = _now_iso()
        updated = WorklistItem(
            item_id=item.item_id, tenant_id=item.tenant_id, operator_ref=item.operator_ref,
            source_ref=item.source_ref, source_runtime=item.source_runtime,
            title=item.title, priority=item.priority, status=QueueStatus.COMPLETED,
            created_at=now,
        )
        self._worklist[item_id] = updated
        _emit(self._events, "complete_worklist_item", {"item_id": item_id}, item_id)
        return updated

    def worklist_for_operator(self, tenant_id: str, operator_ref: str) -> tuple[WorklistItem, ...]:
        items = [w for w in self._worklist.values() if w.tenant_id == tenant_id and w.operator_ref == operator_ref]
        items.sort(key=lambda w: (-w.priority, w.created_at))
        return tuple(items)

    # -- Operator actions ----------------------------------------------------

    def record_action(
        self,
        action_id: str,
        tenant_id: str,
        operator_ref: str,
        target_ref: str,
        target_runtime: str,
        action_name: str,
    ) -> OperatorAction:
        if action_id in self._actions:
            raise RuntimeCoreInvariantError("duplicate action_id")
        now = _now_iso()
        action = OperatorAction(
            action_id=action_id, tenant_id=tenant_id, operator_ref=operator_ref,
            target_ref=target_ref, target_runtime=target_runtime,
            action_name=action_name, status=OperatorActionStatus.INITIATED,
            created_at=now,
        )
        self._actions[action_id] = action
        _emit(self._events, "record_action", {"action_id": action_id, "action_name": action_name}, action_id)
        return action

    def complete_action(self, action_id: str) -> OperatorAction:
        if action_id not in self._actions:
            raise RuntimeCoreInvariantError("unknown action_id")
        action = self._actions[action_id]
        if action.status in _ACTION_TERMINAL:
            raise RuntimeCoreInvariantError("action is in terminal state")
        now = _now_iso()
        updated = OperatorAction(
            action_id=action.action_id, tenant_id=action.tenant_id,
            operator_ref=action.operator_ref, target_ref=action.target_ref,
            target_runtime=action.target_runtime, action_name=action.action_name,
            status=OperatorActionStatus.COMPLETED, created_at=now,
        )
        self._actions[action_id] = updated
        _emit(self._events, "complete_action", {"action_id": action_id}, action_id)
        return updated

    def fail_action(self, action_id: str) -> OperatorAction:
        if action_id not in self._actions:
            raise RuntimeCoreInvariantError("unknown action_id")
        action = self._actions[action_id]
        if action.status in _ACTION_TERMINAL:
            raise RuntimeCoreInvariantError("action is in terminal state")
        now = _now_iso()
        updated = OperatorAction(
            action_id=action.action_id, tenant_id=action.tenant_id,
            operator_ref=action.operator_ref, target_ref=action.target_ref,
            target_runtime=action.target_runtime, action_name=action.action_name,
            status=OperatorActionStatus.FAILED, created_at=now,
        )
        self._actions[action_id] = updated
        _emit(self._events, "fail_action", {"action_id": action_id}, action_id)
        return updated

    def actions_for_operator(self, tenant_id: str, operator_ref: str) -> tuple[OperatorAction, ...]:
        return tuple(a for a in self._actions.values() if a.tenant_id == tenant_id and a.operator_ref == operator_ref)

    # -- Decisions -----------------------------------------------------------

    def record_decision(
        self,
        decision_id: str,
        tenant_id: str,
        operator_ref: str,
        action_id: str,
        disposition: str = "approved",
        reason: str = "operator decision",
    ) -> WorkspaceDecision:
        if decision_id in self._decisions:
            raise RuntimeCoreInvariantError("duplicate decision_id")
        now = _now_iso()
        decision = WorkspaceDecision(
            decision_id=decision_id, tenant_id=tenant_id,
            operator_ref=operator_ref, action_id=action_id,
            disposition=disposition, reason=reason, decided_at=now,
        )
        self._decisions[decision_id] = decision
        _emit(self._events, "record_decision", {"decision_id": decision_id, "disposition": disposition}, decision_id)
        return decision

    # -- Snapshots -----------------------------------------------------------

    def workspace_snapshot(self, snapshot_id: str, tenant_id: str) -> WorkspaceSnapshot:
        now = _now_iso()
        views = self.views_for_tenant(tenant_id)
        active_views = [v for v in views if v.status == WorkspaceStatus.ACTIVE]
        panels = [p for p in self._panels.values() if p.tenant_id == tenant_id]
        queues = [q for q in self._queues.values() if q.tenant_id == tenant_id]
        pending = [q for q in queues if q.status == QueueStatus.PENDING]
        worklist = [w for w in self._worklist.values() if w.tenant_id == tenant_id]
        actions = [a for a in self._actions.values() if a.tenant_id == tenant_id]

        snap = WorkspaceSnapshot(
            snapshot_id=snapshot_id, tenant_id=tenant_id,
            total_views=len(views), active_views=len(active_views),
            total_panels=len(panels), total_queue_items=len(queues),
            pending_queue_items=len(pending), total_worklist_items=len(worklist),
            total_actions=len(actions), captured_at=now,
        )
        _emit(self._events, "workspace_snapshot", {"snapshot_id": snapshot_id}, snapshot_id)
        return snap

    # -- Assessment ----------------------------------------------------------

    def workspace_assessment(self, assessment_id: str, tenant_id: str) -> WorkspaceAssessment:
        if assessment_id in self._assessments:
            raise RuntimeCoreInvariantError("duplicate assessment_id")
        now = _now_iso()
        views = self.views_for_tenant(tenant_id)
        active = [v for v in views if v.status == WorkspaceStatus.ACTIVE]
        queues = [q for q in self._queues.values() if q.tenant_id == tenant_id]
        pending = [q for q in queues if q.status == QueueStatus.PENDING]
        violations = [v for v in self._violations.values() if v.tenant_id == tenant_id]

        total_q = len(queues)
        pend_rate = len(pending) / total_q if total_q > 0 else 0.0

        assessment = WorkspaceAssessment(
            assessment_id=assessment_id, tenant_id=tenant_id,
            total_views=len(views), active_views=len(active),
            queue_depth=total_q,
            pending_rate=round(min(1.0, max(0.0, pend_rate)), 4),
            total_violations=len(violations), assessed_at=now,
        )
        self._assessments[assessment_id] = assessment
        _emit(self._events, "workspace_assessment", {"assessment_id": assessment_id}, assessment_id)
        return assessment

    # -- Violations ----------------------------------------------------------

    def detect_workspace_violations(self, tenant_id: str) -> tuple[WorkspaceViolation, ...]:
        now = _now_iso()
        new_violations: list[WorkspaceViolation] = []

        # Empty panels (active view panels with no items)
        for panel in self._panels.values():
            if panel.tenant_id != tenant_id:
                continue
            view = self._views.get(panel.view_id)
            if view and view.status == WorkspaceStatus.ACTIVE and panel.item_count == 0:
                vid = stable_identifier("viol-wks", {"op": "empty_panel", "panel_id": panel.panel_id})
                if vid not in self._violations:
                    v = WorkspaceViolation(
                        violation_id=vid, tenant_id=tenant_id,
                        operation="empty_panel",
                        reason="active panel has no items",
                        detected_at=now,
                    )
                    self._violations[vid] = v
                    new_violations.append(v)

        # Stale pending items (pending queue items with escalated priority)
        for q in self._queues.values():
            if q.tenant_id != tenant_id:
                continue
            if q.status == QueueStatus.PENDING and q.priority >= 5:
                vid = stable_identifier("viol-wks", {"op": "high_priority_pending", "queue_id": q.queue_id})
                if vid not in self._violations:
                    v = WorkspaceViolation(
                        violation_id=vid, tenant_id=tenant_id,
                        operation="high_priority_pending",
                        reason="high-priority queue item still pending",
                        detected_at=now,
                    )
                    self._violations[vid] = v
                    new_violations.append(v)

        # Failed actions without decisions
        for action in self._actions.values():
            if action.tenant_id != tenant_id:
                continue
            if action.status == OperatorActionStatus.FAILED:
                has_decision = any(d.action_id == action.action_id for d in self._decisions.values())
                if not has_decision:
                    vid = stable_identifier("viol-wks", {"op": "failed_no_decision", "action_id": action.action_id})
                    if vid not in self._violations:
                        v = WorkspaceViolation(
                            violation_id=vid, tenant_id=tenant_id,
                            operation="failed_no_decision",
                            reason="failed action has no decision record",
                            detected_at=now,
                        )
                        self._violations[vid] = v
                        new_violations.append(v)

        if new_violations:
            _emit(self._events, "detect_workspace_violations", {"tenant_id": tenant_id, "count": len(new_violations)}, tenant_id)
        return tuple(new_violations)

    def violations_for_tenant(self, tenant_id: str) -> tuple[WorkspaceViolation, ...]:
        return tuple(v for v in self._violations.values() if v.tenant_id == tenant_id)

    # -- Closure report ------------------------------------------------------

    def closure_report(self, report_id: str, tenant_id: str) -> WorkspaceClosureReport:
        now = _now_iso()
        report = WorkspaceClosureReport(
            report_id=report_id, tenant_id=tenant_id,
            total_views=len(self.views_for_tenant(tenant_id)),
            total_panels=len([p for p in self._panels.values() if p.tenant_id == tenant_id]),
            total_queue_items=len([q for q in self._queues.values() if q.tenant_id == tenant_id]),
            total_worklist_items=len([w for w in self._worklist.values() if w.tenant_id == tenant_id]),
            total_actions=len([a for a in self._actions.values() if a.tenant_id == tenant_id]),
            total_violations=len(self.violations_for_tenant(tenant_id)),
            created_at=now,
        )
        _emit(self._events, "closure_report", {"report_id": report_id}, report_id)
        return report

    # -- State hash ----------------------------------------------------------

    def state_hash(self) -> str:
        parts: list[str] = []
        for k in sorted(self._views):
            parts.append(f"view:{k}:{self._views[k].status.value}")
        for k in sorted(self._panels):
            parts.append(f"panel:{k}:{self._panels[k].item_count}")
        for k in sorted(self._queues):
            parts.append(f"queue:{k}:{self._queues[k].status.value}")
        for k in sorted(self._worklist):
            parts.append(f"wl:{k}:{self._worklist[k].status.value}")
        for k in sorted(self._actions):
            parts.append(f"action:{k}:{self._actions[k].status.value}")
        for k in sorted(self._violations):
            parts.append(f"violation:{k}")
        return sha256("|".join(parts).encode()).hexdigest()
