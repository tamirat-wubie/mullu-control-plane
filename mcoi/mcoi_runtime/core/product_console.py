"""Purpose: public product console / multi-tenant admin surface engine.
Governance scope: registering console surfaces, navigation nodes, admin panels,
    sessions, admin actions, decisions; detecting violations; producing
    immutable snapshots and assessments.
Dependencies: product_console contracts, event_spine, core invariants.
Invariants:
  - Duplicate IDs raise.
  - CLOSED surfaces block new sessions.
  - Cross-tenant access is denied and recorded as a violation.
  - Terminal states are enforced.
  - Every mutation emits an event.
  - All returns are immutable.
  - Clock is injected for deterministic timestamps.
"""

from __future__ import annotations

from hashlib import sha256
from typing import Any

from mcoi_runtime.core.engine_protocol import Clock, WallClock

from ..contracts.product_console import (
    AdminActionRecord,
    AdminActionStatus,
    AdminPanel,
    ConsoleAssessment,
    ConsoleClosureReport,
    ConsoleDecision,
    ConsoleRole,
    ConsoleSession,
    ConsoleSnapshot,
    ConsoleStatus,
    ConsoleSurface,
    ConsoleViolation,
    NavigationNode,
    NavigationScope,
    SurfaceDisposition,
    ViewMode,
)
from ..contracts.event import EventRecord, EventSource, EventType
from .event_spine import EventSpineEngine
from .invariants import RuntimeCoreInvariantError, stable_identifier


def _emit(es: EventSpineEngine, action: str, payload: dict, cid: str, now: str) -> EventRecord:
    payload["action"] = action
    event = EventRecord(
        event_id=stable_identifier("evt-console", {"action": action, "ts": now, "cid": cid, "seq": str(es.event_count)}),
        event_type=EventType.CUSTOM,
        source=EventSource.COMMUNICATION_SYSTEM,
        correlation_id=cid,
        payload=payload,
        emitted_at=now,
    )
    es.emit(event)
    return event


_SURFACE_TERMINAL = frozenset({ConsoleStatus.CLOSED})


class ProductConsoleEngine:
    """Public product console / multi-tenant admin surface engine."""

    def __init__(self, event_spine: EventSpineEngine, *, clock: Any = None) -> None:
        if not isinstance(event_spine, EventSpineEngine):
            raise RuntimeCoreInvariantError("event_spine must be an EventSpineEngine")
        self._events = event_spine
        self._clock: Clock = clock if isinstance(clock, Clock) else WallClock()
        self._surfaces: dict[str, ConsoleSurface] = {}
        self._nodes: dict[str, NavigationNode] = {}
        self._panels: dict[str, AdminPanel] = {}
        self._sessions: dict[str, ConsoleSession] = {}
        self._actions: dict[str, AdminActionRecord] = {}
        self._decisions: dict[str, ConsoleDecision] = {}
        self._violations: dict[str, ConsoleViolation] = {}

    # ------------------------------------------------------------------
    # Clock
    # ------------------------------------------------------------------

    def _now(self) -> str:
        return self._clock.now_iso()

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def surface_count(self) -> int:
        return len(self._surfaces)

    @property
    def node_count(self) -> int:
        return len(self._nodes)

    @property
    def panel_count(self) -> int:
        return len(self._panels)

    @property
    def session_count(self) -> int:
        return len(self._sessions)

    @property
    def action_count(self) -> int:
        return len(self._actions)

    @property
    def decision_count(self) -> int:
        return len(self._decisions)

    @property
    def violation_count(self) -> int:
        return len(self._violations)

    # ------------------------------------------------------------------
    # Surfaces
    # ------------------------------------------------------------------

    def register_surface(
        self,
        surface_id: str,
        tenant_id: str,
        display_name: str,
        role: ConsoleRole = ConsoleRole.TENANT_ADMIN,
        disposition: SurfaceDisposition = SurfaceDisposition.VISIBLE,
    ) -> ConsoleSurface:
        if surface_id in self._surfaces:
            raise RuntimeCoreInvariantError(f"surface already registered: {surface_id}")
        now = self._now()
        record = ConsoleSurface(
            surface_id=surface_id,
            tenant_id=tenant_id,
            display_name=display_name,
            status=ConsoleStatus.ACTIVE,
            disposition=disposition,
            role=role,
            created_at=now,
        )
        self._surfaces[surface_id] = record
        _emit(self._events, "register_surface", {"surface_id": surface_id, "tenant_id": tenant_id}, surface_id, self._now())
        return record

    def get_surface(self, surface_id: str) -> ConsoleSurface:
        if surface_id not in self._surfaces:
            raise RuntimeCoreInvariantError(f"unknown surface: {surface_id}")
        return self._surfaces[surface_id]

    def surfaces_for_tenant(self, tenant_id: str) -> tuple[ConsoleSurface, ...]:
        return tuple(s for s in self._surfaces.values() if s.tenant_id == tenant_id)

    def suspend_surface(self, surface_id: str) -> ConsoleSurface:
        if surface_id not in self._surfaces:
            raise RuntimeCoreInvariantError(f"unknown surface: {surface_id}")
        old = self._surfaces[surface_id]
        if old.status in _SURFACE_TERMINAL:
            raise RuntimeCoreInvariantError(f"surface is in terminal state: {old.status.value}")
        updated = ConsoleSurface(
            surface_id=old.surface_id,
            tenant_id=old.tenant_id,
            display_name=old.display_name,
            status=ConsoleStatus.SUSPENDED,
            disposition=old.disposition,
            role=old.role,
            created_at=old.created_at,
        )
        self._surfaces[surface_id] = updated
        _emit(self._events, "suspend_surface", {"surface_id": surface_id}, surface_id, self._now())
        return updated

    def close_surface(self, surface_id: str) -> ConsoleSurface:
        if surface_id not in self._surfaces:
            raise RuntimeCoreInvariantError(f"unknown surface: {surface_id}")
        old = self._surfaces[surface_id]
        if old.status in _SURFACE_TERMINAL:
            raise RuntimeCoreInvariantError(f"surface already closed: {surface_id}")
        updated = ConsoleSurface(
            surface_id=old.surface_id,
            tenant_id=old.tenant_id,
            display_name=old.display_name,
            status=ConsoleStatus.CLOSED,
            disposition=old.disposition,
            role=old.role,
            created_at=old.created_at,
        )
        self._surfaces[surface_id] = updated
        _emit(self._events, "close_surface", {"surface_id": surface_id}, surface_id, self._now())
        return updated

    def activate_surface(self, surface_id: str) -> ConsoleSurface:
        if surface_id not in self._surfaces:
            raise RuntimeCoreInvariantError(f"unknown surface: {surface_id}")
        old = self._surfaces[surface_id]
        if old.status in _SURFACE_TERMINAL:
            raise RuntimeCoreInvariantError(f"surface is in terminal state: {old.status.value}")
        if old.status != ConsoleStatus.SUSPENDED:
            raise RuntimeCoreInvariantError(f"activate_surface requires SUSPENDED state, got {old.status.value}")
        updated = ConsoleSurface(
            surface_id=old.surface_id,
            tenant_id=old.tenant_id,
            display_name=old.display_name,
            status=ConsoleStatus.ACTIVE,
            disposition=old.disposition,
            role=old.role,
            created_at=old.created_at,
        )
        self._surfaces[surface_id] = updated
        _emit(self._events, "activate_surface", {"surface_id": surface_id}, surface_id, self._now())
        return updated

    # ------------------------------------------------------------------
    # Navigation nodes
    # ------------------------------------------------------------------

    def register_navigation_node(
        self,
        node_id: str,
        tenant_id: str,
        surface_ref: str,
        label: str,
        scope: NavigationScope = NavigationScope.TENANT,
        parent_ref: str = "root",
        order: int = 0,
    ) -> NavigationNode:
        if node_id in self._nodes:
            raise RuntimeCoreInvariantError(f"node already registered: {node_id}")
        now = self._now()
        record = NavigationNode(
            node_id=node_id,
            tenant_id=tenant_id,
            surface_ref=surface_ref,
            parent_ref=parent_ref,
            label=label,
            scope=scope,
            order=order,
            created_at=now,
        )
        self._nodes[node_id] = record
        _emit(self._events, "register_navigation_node", {"node_id": node_id, "tenant_id": tenant_id}, node_id, self._now())
        return record

    def get_node(self, node_id: str) -> NavigationNode:
        if node_id not in self._nodes:
            raise RuntimeCoreInvariantError(f"unknown node: {node_id}")
        return self._nodes[node_id]

    def nodes_for_surface(self, surface_ref: str) -> tuple[NavigationNode, ...]:
        matching = [n for n in self._nodes.values() if n.surface_ref == surface_ref]
        matching.sort(key=lambda n: n.order)
        return tuple(matching)

    # ------------------------------------------------------------------
    # Panels
    # ------------------------------------------------------------------

    def register_panel(
        self,
        panel_id: str,
        tenant_id: str,
        surface_ref: str,
        display_name: str,
        target_runtime: str,
        view_mode: ViewMode = ViewMode.FULL,
    ) -> AdminPanel:
        if panel_id in self._panels:
            raise RuntimeCoreInvariantError(f"panel already registered: {panel_id}")
        now = self._now()
        record = AdminPanel(
            panel_id=panel_id,
            tenant_id=tenant_id,
            surface_ref=surface_ref,
            display_name=display_name,
            target_runtime=target_runtime,
            view_mode=view_mode,
            created_at=now,
        )
        self._panels[panel_id] = record
        _emit(self._events, "register_panel", {"panel_id": panel_id, "tenant_id": tenant_id}, panel_id, self._now())
        return record

    def get_panel(self, panel_id: str) -> AdminPanel:
        if panel_id not in self._panels:
            raise RuntimeCoreInvariantError(f"unknown panel: {panel_id}")
        return self._panels[panel_id]

    def panels_for_surface(self, surface_ref: str) -> tuple[AdminPanel, ...]:
        return tuple(p for p in self._panels.values() if p.surface_ref == surface_ref)

    # ------------------------------------------------------------------
    # Sessions
    # ------------------------------------------------------------------

    def start_console_session(
        self,
        session_id: str,
        tenant_id: str,
        identity_ref: str,
        surface_ref: str,
    ) -> ConsoleSession:
        if session_id in self._sessions:
            raise RuntimeCoreInvariantError(f"session already registered: {session_id}")
        # Validate surface exists and not CLOSED
        if surface_ref not in self._surfaces:
            raise RuntimeCoreInvariantError(f"unknown surface: {surface_ref}")
        surface = self._surfaces[surface_ref]
        if surface.status in _SURFACE_TERMINAL:
            raise RuntimeCoreInvariantError(f"surface is in terminal state: {surface.status.value}")
        # Cross-tenant check
        if surface.tenant_id != tenant_id:
            vid = stable_identifier("viol-console", {"session_id": session_id, "tenant_id": tenant_id, "surface_tenant": surface.tenant_id})
            now = self._now()
            violation = ConsoleViolation(
                violation_id=vid,
                tenant_id=tenant_id,
                operation="start_console_session",
                reason=f"cross-tenant access denied: session tenant {tenant_id} != surface tenant {surface.tenant_id}",
                detected_at=now,
            )
            self._violations[vid] = violation
            _emit(self._events, "cross_tenant_session_denied", {"session_id": session_id, "tenant_id": tenant_id}, session_id, now)
            raise RuntimeCoreInvariantError(f"cross-tenant access denied for session {session_id}")
        now = self._now()
        record = ConsoleSession(
            session_id=session_id,
            tenant_id=tenant_id,
            identity_ref=identity_ref,
            surface_ref=surface_ref,
            status=ConsoleStatus.ACTIVE,
            started_at=now,
        )
        self._sessions[session_id] = record
        _emit(self._events, "start_console_session", {"session_id": session_id, "tenant_id": tenant_id}, session_id, self._now())
        return record

    def end_session(self, session_id: str) -> ConsoleSession:
        if session_id not in self._sessions:
            raise RuntimeCoreInvariantError(f"unknown session: {session_id}")
        old = self._sessions[session_id]
        if old.status != ConsoleStatus.ACTIVE:
            raise RuntimeCoreInvariantError(f"session not active: {old.status.value}")
        updated = ConsoleSession(
            session_id=old.session_id,
            tenant_id=old.tenant_id,
            identity_ref=old.identity_ref,
            surface_ref=old.surface_ref,
            status=ConsoleStatus.CLOSED,
            started_at=old.started_at,
        )
        self._sessions[session_id] = updated
        _emit(self._events, "end_session", {"session_id": session_id}, session_id, self._now())
        return updated

    def lock_session(self, session_id: str) -> ConsoleSession:
        if session_id not in self._sessions:
            raise RuntimeCoreInvariantError(f"unknown session: {session_id}")
        old = self._sessions[session_id]
        if old.status != ConsoleStatus.ACTIVE:
            raise RuntimeCoreInvariantError(f"session not active: {old.status.value}")
        updated = ConsoleSession(
            session_id=old.session_id,
            tenant_id=old.tenant_id,
            identity_ref=old.identity_ref,
            surface_ref=old.surface_ref,
            status=ConsoleStatus.SUSPENDED,
            started_at=old.started_at,
        )
        self._sessions[session_id] = updated
        _emit(self._events, "lock_session", {"session_id": session_id}, session_id, self._now())
        return updated

    # ------------------------------------------------------------------
    # Admin actions
    # ------------------------------------------------------------------

    def record_admin_action(
        self,
        action_id: str,
        tenant_id: str,
        session_ref: str,
        panel_ref: str,
        operation: str,
    ) -> AdminActionRecord:
        if action_id in self._actions:
            raise RuntimeCoreInvariantError(f"action already registered: {action_id}")
        # Validate session exists and is ACTIVE
        if session_ref not in self._sessions:
            vid = stable_identifier("viol-action", {"action_id": action_id, "session_ref": session_ref})
            now = self._now()
            violation = ConsoleViolation(
                violation_id=vid,
                tenant_id=tenant_id,
                operation="record_admin_action",
                reason=f"action_no_session: session {session_ref} not found",
                detected_at=now,
            )
            self._violations[vid] = violation
            raise RuntimeCoreInvariantError(f"unknown session: {session_ref}")
        session = self._sessions[session_ref]
        if session.status != ConsoleStatus.ACTIVE:
            raise RuntimeCoreInvariantError(f"session not active: {session.status.value}")
        # Cross-tenant check
        if session.tenant_id != tenant_id:
            vid = stable_identifier("viol-xtenant-action", {"action_id": action_id, "tenant_id": tenant_id, "session_tenant": session.tenant_id})
            now = self._now()
            violation = ConsoleViolation(
                violation_id=vid,
                tenant_id=tenant_id,
                operation="record_admin_action",
                reason=f"cross_tenant_access: action tenant {tenant_id} != session tenant {session.tenant_id}",
                detected_at=now,
            )
            self._violations[vid] = violation
            _emit(self._events, "cross_tenant_action_denied", {"action_id": action_id, "tenant_id": tenant_id}, action_id, now)
            raise RuntimeCoreInvariantError(f"cross-tenant access denied for action {action_id}")
        now = self._now()
        record = AdminActionRecord(
            action_id=action_id,
            tenant_id=tenant_id,
            session_ref=session_ref,
            panel_ref=panel_ref,
            operation=operation,
            status=AdminActionStatus.PENDING,
            performed_at=now,
        )
        self._actions[action_id] = record
        _emit(self._events, "record_admin_action", {"action_id": action_id, "tenant_id": tenant_id}, action_id, self._now())
        return record

    def execute_action(self, action_id: str) -> AdminActionRecord:
        if action_id not in self._actions:
            raise RuntimeCoreInvariantError(f"unknown action: {action_id}")
        old = self._actions[action_id]
        if old.status != AdminActionStatus.PENDING:
            raise RuntimeCoreInvariantError(f"action not pending: {old.status.value}")
        updated = AdminActionRecord(
            action_id=old.action_id,
            tenant_id=old.tenant_id,
            session_ref=old.session_ref,
            panel_ref=old.panel_ref,
            operation=old.operation,
            status=AdminActionStatus.EXECUTED,
            performed_at=old.performed_at,
        )
        self._actions[action_id] = updated
        _emit(self._events, "execute_action", {"action_id": action_id}, action_id, self._now())
        return updated

    def deny_action(self, action_id: str) -> AdminActionRecord:
        if action_id not in self._actions:
            raise RuntimeCoreInvariantError(f"unknown action: {action_id}")
        old = self._actions[action_id]
        if old.status != AdminActionStatus.PENDING:
            raise RuntimeCoreInvariantError(f"action not pending: {old.status.value}")
        updated = AdminActionRecord(
            action_id=old.action_id,
            tenant_id=old.tenant_id,
            session_ref=old.session_ref,
            panel_ref=old.panel_ref,
            operation=old.operation,
            status=AdminActionStatus.DENIED,
            performed_at=old.performed_at,
        )
        self._actions[action_id] = updated
        _emit(self._events, "deny_action", {"action_id": action_id}, action_id, self._now())
        return updated

    def rollback_action(self, action_id: str) -> AdminActionRecord:
        if action_id not in self._actions:
            raise RuntimeCoreInvariantError(f"unknown action: {action_id}")
        old = self._actions[action_id]
        if old.status != AdminActionStatus.EXECUTED:
            raise RuntimeCoreInvariantError(f"action not executed: {old.status.value}")
        updated = AdminActionRecord(
            action_id=old.action_id,
            tenant_id=old.tenant_id,
            session_ref=old.session_ref,
            panel_ref=old.panel_ref,
            operation=old.operation,
            status=AdminActionStatus.ROLLED_BACK,
            performed_at=old.performed_at,
        )
        self._actions[action_id] = updated
        _emit(self._events, "rollback_action", {"action_id": action_id}, action_id, self._now())
        return updated

    # ------------------------------------------------------------------
    # Decisions
    # ------------------------------------------------------------------

    def resolve_console_decision(
        self,
        decision_id: str,
        tenant_id: str,
        action_ref: str,
        disposition: str,
        reason: str,
    ) -> ConsoleDecision:
        if decision_id in self._decisions:
            raise RuntimeCoreInvariantError(f"decision already registered: {decision_id}")
        now = self._now()
        record = ConsoleDecision(
            decision_id=decision_id,
            tenant_id=tenant_id,
            action_ref=action_ref,
            disposition=disposition,
            reason=reason,
            decided_at=now,
        )
        self._decisions[decision_id] = record
        _emit(self._events, "resolve_console_decision", {"decision_id": decision_id, "tenant_id": tenant_id}, decision_id, self._now())
        return record

    # ------------------------------------------------------------------
    # Assessment
    # ------------------------------------------------------------------

    def console_assessment(self, assessment_id: str, tenant_id: str) -> ConsoleAssessment:
        surfaces = [s for s in self._surfaces.values() if s.tenant_id == tenant_id]
        sessions = [s for s in self._sessions.values() if s.tenant_id == tenant_id and s.status == ConsoleStatus.ACTIVE]
        actions = [a for a in self._actions.values() if a.tenant_id == tenant_id]
        executed = sum(1 for a in actions if a.status == AdminActionStatus.EXECUTED)
        denied = sum(1 for a in actions if a.status == AdminActionStatus.DENIED)
        rolled_back = sum(1 for a in actions if a.status == AdminActionStatus.ROLLED_BACK)
        denom = executed + denied + rolled_back
        rate = executed / denom if denom > 0 else 1.0
        now = self._now()
        record = ConsoleAssessment(
            assessment_id=assessment_id,
            tenant_id=tenant_id,
            total_surfaces=len(surfaces),
            total_active_sessions=len(sessions),
            action_success_rate=rate,
            assessed_at=now,
        )
        _emit(self._events, "console_assessment", {"assessment_id": assessment_id, "tenant_id": tenant_id}, assessment_id, self._now())
        return record

    # ------------------------------------------------------------------
    # Snapshot
    # ------------------------------------------------------------------

    def console_snapshot(self, snapshot_id: str, tenant_id: str) -> ConsoleSnapshot:
        surfaces = [s for s in self._surfaces.values() if s.tenant_id == tenant_id]
        panels = [p for p in self._panels.values() if p.tenant_id == tenant_id]
        sessions = [s for s in self._sessions.values() if s.tenant_id == tenant_id]
        actions = [a for a in self._actions.values() if a.tenant_id == tenant_id]
        violations = [v for v in self._violations.values() if v.tenant_id == tenant_id]
        now = self._now()
        record = ConsoleSnapshot(
            snapshot_id=snapshot_id,
            tenant_id=tenant_id,
            total_surfaces=len(surfaces),
            total_panels=len(panels),
            total_sessions=len(sessions),
            total_actions=len(actions),
            total_violations=len(violations),
            captured_at=now,
        )
        _emit(self._events, "console_snapshot", {"snapshot_id": snapshot_id, "tenant_id": tenant_id}, snapshot_id, self._now())
        return record

    # ------------------------------------------------------------------
    # Violation detection
    # ------------------------------------------------------------------

    def detect_console_violations(self, tenant_id: str) -> tuple[ConsoleViolation, ...]:
        new_violations: list[ConsoleViolation] = []
        now = self._now()

        # session_on_closed_surface
        for s in self._sessions.values():
            if s.tenant_id != tenant_id:
                continue
            if s.status != ConsoleStatus.ACTIVE:
                continue
            if s.surface_ref in self._surfaces:
                surface = self._surfaces[s.surface_ref]
                if surface.status == ConsoleStatus.CLOSED:
                    vid = stable_identifier("viol-closed-surface", {"session_id": s.session_id, "surface_ref": s.surface_ref})
                    if vid not in self._violations:
                        v = ConsoleViolation(
                            violation_id=vid,
                            tenant_id=tenant_id,
                            operation="session_on_closed_surface",
                            reason=f"session {s.session_id} active on closed surface {s.surface_ref}",
                            detected_at=now,
                        )
                        self._violations[vid] = v
                        new_violations.append(v)

        # action_no_session
        for a in self._actions.values():
            if a.tenant_id != tenant_id:
                continue
            if a.session_ref not in self._sessions or self._sessions[a.session_ref].status != ConsoleStatus.ACTIVE:
                vid = stable_identifier("viol-no-session", {"action_id": a.action_id, "session_ref": a.session_ref})
                if vid not in self._violations:
                    v = ConsoleViolation(
                        violation_id=vid,
                        tenant_id=tenant_id,
                        operation="action_no_session",
                        reason=f"action {a.action_id} has no active session {a.session_ref}",
                        detected_at=now,
                    )
                    self._violations[vid] = v
                    new_violations.append(v)

        # cross_tenant_access
        for a in self._actions.values():
            if a.tenant_id != tenant_id:
                continue
            if a.session_ref in self._sessions:
                session = self._sessions[a.session_ref]
                if a.tenant_id != session.tenant_id:
                    vid = stable_identifier("viol-xtenant", {"action_id": a.action_id, "action_tenant": a.tenant_id, "session_tenant": session.tenant_id})
                    if vid not in self._violations:
                        v = ConsoleViolation(
                            violation_id=vid,
                            tenant_id=tenant_id,
                            operation="cross_tenant_access",
                            reason=f"action {a.action_id} tenant {a.tenant_id} != session tenant {session.tenant_id}",
                            detected_at=now,
                        )
                        self._violations[vid] = v
                        new_violations.append(v)

        return tuple(new_violations)

    # ------------------------------------------------------------------
    # Closure report
    # ------------------------------------------------------------------

    def console_closure_report(self, report_id: str, tenant_id: str) -> ConsoleClosureReport:
        surfaces = [s for s in self._surfaces.values() if s.tenant_id == tenant_id]
        panels = [p for p in self._panels.values() if p.tenant_id == tenant_id]
        sessions = [s for s in self._sessions.values() if s.tenant_id == tenant_id]
        actions = [a for a in self._actions.values() if a.tenant_id == tenant_id]
        violations = [v for v in self._violations.values() if v.tenant_id == tenant_id]
        now = self._now()
        return ConsoleClosureReport(
            report_id=report_id,
            tenant_id=tenant_id,
            total_surfaces=len(surfaces),
            total_panels=len(panels),
            total_sessions=len(sessions),
            total_actions=len(actions),
            total_violations=len(violations),
            created_at=now,
        )

    # ------------------------------------------------------------------
    # Persistence protocol
    # ------------------------------------------------------------------

    def _collections(self) -> dict[str, Any]:
        return {
            "surfaces": self._surfaces,
            "nodes": self._nodes,
            "panels": self._panels,
            "sessions": self._sessions,
            "actions": self._actions,
            "decisions": self._decisions,
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
                    v.to_dict() if hasattr(v, "to_dict") else v for v in collection
                ]
            else:
                result[name] = collection
        return result

    def state_hash(self) -> str:
        parts: list[str] = []
        for k in sorted(self._surfaces):
            parts.append(f"sf:{k}")
        for k in sorted(self._nodes):
            parts.append(f"nd:{k}")
        for k in sorted(self._panels):
            parts.append(f"pn:{k}")
        for k in sorted(self._sessions):
            parts.append(f"ss:{k}")
        for k in sorted(self._actions):
            parts.append(f"ac:{k}")
        for k in sorted(self._decisions):
            parts.append(f"dc:{k}")
        for k in sorted(self._violations):
            parts.append(f"vl:{k}")
        return sha256("|".join(parts).encode()).hexdigest()
