"""Purpose: policy enforcement / session authorization runtime engine.
Governance scope: opening and managing live sessions; binding sessions to
    identities, connectors, environments, campaigns; enforcing session-time
    constraints; supporting step-up authorization; revoking or degrading
    sessions on policy/tenant/risk/compliance events; producing immutable
    audits and snapshots.
Dependencies: policy_enforcement contracts, event_spine, core invariants.
Invariants:
  - Enforcement is fail-closed: default decision is DENY.
  - Only ACTIVE sessions may execute actions.
  - Step-up requires explicit approval.
  - Revocations are permanent.
  - Constraints narrow permissions per session.
  - Every mutation emits an event.
  - All returns are immutable.
"""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from typing import Any

from ..contracts.policy_enforcement import (
    EnforcementAuditRecord,
    EnforcementDecision,
    EnforcementEvent,
    PolicySessionBinding,
    PrivilegeElevationDecision,
    PrivilegeElevationRequest,
    PrivilegeLevel,
    RevocationReason,
    RevocationRecord,
    SessionClosureReport,
    SessionConstraint,
    SessionKind,
    SessionRecord,
    SessionSnapshot,
    SessionStatus,
    StepUpStatus,
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
        event_id=stable_identifier("evt-penf", {"action": action, "ts": now, "cid": cid}),
        event_type=EventType.CUSTOM,
        source=EventSource.COMMUNICATION_SYSTEM,
        correlation_id=cid,
        payload=payload,
        emitted_at=now,
    )
    es.emit(event)
    return event


class PolicyEnforcementEngine:
    """Live policy enforcement and session authorization engine."""

    def __init__(self, event_spine: EventSpineEngine) -> None:
        if not isinstance(event_spine, EventSpineEngine):
            raise RuntimeCoreInvariantError("event_spine must be an EventSpineEngine")
        self._events = event_spine
        self._sessions: dict[str, SessionRecord] = {}
        self._constraints: dict[str, SessionConstraint] = {}
        self._step_up_requests: dict[str, PrivilegeElevationRequest] = {}
        self._step_up_decisions: dict[str, PrivilegeElevationDecision] = {}
        self._enforcement_events: dict[str, EnforcementEvent] = {}
        self._revocations: dict[str, RevocationRecord] = {}
        self._bindings: dict[str, PolicySessionBinding] = {}
        self._audits: dict[str, EnforcementAuditRecord] = {}
        self._snapshot_ids: set[str] = set()
        self._closure_reports: dict[str, SessionClosureReport] = {}

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def session_count(self) -> int:
        return len(self._sessions)

    @property
    def active_session_count(self) -> int:
        return sum(1 for s in self._sessions.values() if s.status == SessionStatus.ACTIVE)

    @property
    def constraint_count(self) -> int:
        return len(self._constraints)

    @property
    def step_up_count(self) -> int:
        return len(self._step_up_requests)

    @property
    def enforcement_count(self) -> int:
        return len(self._enforcement_events)

    @property
    def revocation_count(self) -> int:
        return len(self._revocations)

    @property
    def binding_count(self) -> int:
        return len(self._bindings)

    @property
    def audit_count(self) -> int:
        return len(self._audits)

    # ------------------------------------------------------------------
    # Session management
    # ------------------------------------------------------------------

    def open_session(
        self,
        session_id: str,
        identity_id: str,
        *,
        kind: SessionKind = SessionKind.INTERACTIVE,
        privilege_level: PrivilegeLevel = PrivilegeLevel.STANDARD,
        scope_ref_id: str = "",
        environment_id: str = "",
        connector_id: str = "",
        campaign_id: str = "",
        expires_at: str = "",
    ) -> SessionRecord:
        """Open a new live session."""
        if session_id in self._sessions:
            raise RuntimeCoreInvariantError(f"Duplicate session_id: {session_id}")
        now = _now_iso()
        session = SessionRecord(
            session_id=session_id,
            identity_id=identity_id,
            kind=kind,
            status=SessionStatus.ACTIVE,
            privilege_level=privilege_level,
            scope_ref_id=scope_ref_id,
            environment_id=environment_id,
            connector_id=connector_id,
            campaign_id=campaign_id,
            opened_at=now,
            expires_at=expires_at,
        )
        self._sessions[session_id] = session
        _emit(self._events, "session_opened", {
            "session_id": session_id, "identity_id": identity_id,
            "kind": kind.value,
        }, session_id)
        return session

    def get_session(self, session_id: str) -> SessionRecord:
        """Get a session by ID."""
        s = self._sessions.get(session_id)
        if s is None:
            raise RuntimeCoreInvariantError(f"Unknown session_id: {session_id}")
        return s

    def sessions_for_identity(self, identity_id: str) -> tuple[SessionRecord, ...]:
        """Return all sessions for an identity."""
        return tuple(s for s in self._sessions.values() if s.identity_id == identity_id)

    def active_sessions(self) -> tuple[SessionRecord, ...]:
        """Return all active sessions."""
        return tuple(s for s in self._sessions.values() if s.status == SessionStatus.ACTIVE)

    def _update_session_status(
        self, session_id: str, status: SessionStatus,
    ) -> SessionRecord:
        """Internal helper to update session status."""
        old = self._sessions.get(session_id)
        if old is None:
            raise RuntimeCoreInvariantError(f"Unknown session_id: {session_id}")
        now = _now_iso()
        closed_at = now if status in (
            SessionStatus.CLOSED, SessionStatus.REVOKED, SessionStatus.EXPIRED,
        ) else old.closed_at
        updated = SessionRecord(
            session_id=old.session_id,
            identity_id=old.identity_id,
            kind=old.kind,
            status=status,
            privilege_level=old.privilege_level,
            scope_ref_id=old.scope_ref_id,
            environment_id=old.environment_id,
            connector_id=old.connector_id,
            campaign_id=old.campaign_id,
            opened_at=old.opened_at,
            expires_at=old.expires_at,
            closed_at=closed_at,
            metadata=old.metadata,
        )
        self._sessions[session_id] = updated
        return updated

    # ------------------------------------------------------------------
    # Session constraints
    # ------------------------------------------------------------------

    def add_constraint(
        self,
        constraint_id: str,
        session_id: str,
        *,
        resource_type: str = "",
        action: str = "",
        environment_id: str = "",
        connector_id: str = "",
        max_privilege: PrivilegeLevel = PrivilegeLevel.STANDARD,
        valid_from: str = "",
        valid_until: str = "",
    ) -> SessionConstraint:
        """Add a constraint to a session."""
        if constraint_id in self._constraints:
            raise RuntimeCoreInvariantError(f"Duplicate constraint_id: {constraint_id}")
        if session_id not in self._sessions:
            raise RuntimeCoreInvariantError(f"Unknown session_id: {session_id}")
        now = _now_iso()
        constraint = SessionConstraint(
            constraint_id=constraint_id,
            session_id=session_id,
            resource_type=resource_type,
            action=action,
            environment_id=environment_id,
            connector_id=connector_id,
            max_privilege=max_privilege,
            valid_from=valid_from,
            valid_until=valid_until,
            created_at=now,
        )
        self._constraints[constraint_id] = constraint
        _emit(self._events, "constraint_added", {
            "constraint_id": constraint_id, "session_id": session_id,
        }, session_id)
        return constraint

    def constraints_for_session(self, session_id: str) -> tuple[SessionConstraint, ...]:
        """Return all constraints for a session."""
        return tuple(c for c in self._constraints.values() if c.session_id == session_id)

    # ------------------------------------------------------------------
    # Session binding
    # ------------------------------------------------------------------

    def bind_session(
        self,
        binding_id: str,
        session_id: str,
        resource_type: str,
        resource_id: str,
    ) -> PolicySessionBinding:
        """Bind a session to a specific resource."""
        if binding_id in self._bindings:
            raise RuntimeCoreInvariantError(f"Duplicate binding_id: {binding_id}")
        if session_id not in self._sessions:
            raise RuntimeCoreInvariantError(f"Unknown session_id: {session_id}")
        now = _now_iso()
        binding = PolicySessionBinding(
            binding_id=binding_id,
            session_id=session_id,
            resource_type=resource_type,
            resource_id=resource_id,
            bound_at=now,
        )
        self._bindings[binding_id] = binding
        _emit(self._events, "session_bound", {
            "binding_id": binding_id, "session_id": session_id,
            "resource_type": resource_type, "resource_id": resource_id,
        }, session_id)
        return binding

    def bindings_for_session(self, session_id: str) -> tuple[PolicySessionBinding, ...]:
        """Return all bindings for a session."""
        return tuple(b for b in self._bindings.values() if b.session_id == session_id)

    # ------------------------------------------------------------------
    # Session action enforcement
    # ------------------------------------------------------------------

    def evaluate_session_action(
        self,
        session_id: str,
        resource_type: str,
        action: str,
        *,
        environment_id: str = "",
        connector_id: str = "",
        required_privilege: PrivilegeLevel = PrivilegeLevel.STANDARD,
    ) -> EnforcementEvent:
        """Evaluate whether a session may perform an action. Fail-closed."""
        now = _now_iso()
        session = self._sessions.get(session_id)

        # Unknown session → DENY
        if session is None:
            return self._record_enforcement(
                session_id, "", resource_type, action,
                EnforcementDecision.DENIED, "unknown session",
                environment_id, connector_id, now,
            )

        # Non-active session → map status to decision
        if session.status != SessionStatus.ACTIVE:
            decision_map = {
                SessionStatus.SUSPENDED: EnforcementDecision.SUSPENDED,
                SessionStatus.REVOKED: EnforcementDecision.REVOKED,
                SessionStatus.EXPIRED: EnforcementDecision.DENIED,
                SessionStatus.CLOSED: EnforcementDecision.DENIED,
            }
            decision = decision_map.get(session.status, EnforcementDecision.DENIED)
            return self._record_enforcement(
                session_id, session.identity_id, resource_type, action,
                decision, f"session {session.status.value}",
                environment_id, connector_id, now,
            )

        # Check privilege level
        privilege_order = [
            PrivilegeLevel.STANDARD,
            PrivilegeLevel.ELEVATED,
            PrivilegeLevel.ADMIN,
            PrivilegeLevel.SYSTEM,
            PrivilegeLevel.EMERGENCY,
        ]
        session_level_idx = privilege_order.index(session.privilege_level)
        required_level_idx = privilege_order.index(required_privilege)
        if required_level_idx > session_level_idx:
            return self._record_enforcement(
                session_id, session.identity_id, resource_type, action,
                EnforcementDecision.STEP_UP_REQUIRED,
                f"requires {required_privilege.value} privilege",
                environment_id, connector_id, now,
            )

        # Check constraints
        constraints = self.constraints_for_session(session_id)
        for c in constraints:
            # Environment constraint
            if c.environment_id and environment_id and c.environment_id != environment_id:
                return self._record_enforcement(
                    session_id, session.identity_id, resource_type, action,
                    EnforcementDecision.DENIED,
                    f"environment constraint: session bound to {c.environment_id}",
                    environment_id, connector_id, now,
                )
            # Connector constraint
            if c.connector_id and connector_id and c.connector_id != connector_id:
                return self._record_enforcement(
                    session_id, session.identity_id, resource_type, action,
                    EnforcementDecision.DENIED,
                    f"connector constraint: session bound to {c.connector_id}",
                    environment_id, connector_id, now,
                )
            # Resource/action constraint — if constraint specifies a resource_type,
            # only that resource is allowed; same for action
            if c.resource_type and c.resource_type != resource_type:
                return self._record_enforcement(
                    session_id, session.identity_id, resource_type, action,
                    EnforcementDecision.DENIED,
                    f"resource constraint: session limited to {c.resource_type}",
                    environment_id, connector_id, now,
                )
            if c.action and c.action != action:
                return self._record_enforcement(
                    session_id, session.identity_id, resource_type, action,
                    EnforcementDecision.DENIED,
                    f"action constraint: session limited to {c.action}",
                    environment_id, connector_id, now,
                )
            # Privilege cap from constraint
            if c.max_privilege:
                cap_idx = privilege_order.index(c.max_privilege)
                if required_level_idx > cap_idx:
                    return self._record_enforcement(
                        session_id, session.identity_id, resource_type, action,
                        EnforcementDecision.STEP_UP_REQUIRED,
                        f"constraint caps privilege at {c.max_privilege.value}",
                        environment_id, connector_id, now,
                    )

        # All checks passed
        return self._record_enforcement(
            session_id, session.identity_id, resource_type, action,
            EnforcementDecision.ALLOWED, "allowed",
            environment_id, connector_id, now,
        )

    def _record_enforcement(
        self,
        session_id: str,
        identity_id: str,
        resource_type: str,
        action: str,
        decision: EnforcementDecision,
        reason: str,
        environment_id: str,
        connector_id: str,
        now: str,
    ) -> EnforcementEvent:
        eid = stable_identifier("enf", {
            "sid": session_id, "rt": resource_type, "a": action, "ts": now,
        })
        event = EnforcementEvent(
            event_id=eid,
            session_id=session_id,
            identity_id=identity_id or "unknown",
            resource_type=resource_type,
            action=action,
            decision=decision,
            reason=reason,
            environment_id=environment_id,
            connector_id=connector_id,
            evaluated_at=now,
        )
        self._enforcement_events[eid] = event

        # Also create audit record
        audit_id = stable_identifier("aud-enf", {
            "sid": session_id, "a": action, "ts": now,
        })
        audit = EnforcementAuditRecord(
            audit_id=audit_id,
            session_id=session_id,
            identity_id=identity_id or "unknown",
            action=action,
            resource_type=resource_type,
            decision=decision,
            environment_id=environment_id,
            connector_id=connector_id,
            recorded_at=now,
        )
        self._audits[audit_id] = audit
        return event

    # ------------------------------------------------------------------
    # Step-up authorization
    # ------------------------------------------------------------------

    def request_step_up(
        self,
        request_id: str,
        session_id: str,
        identity_id: str,
        *,
        requested_level: PrivilegeLevel = PrivilegeLevel.ELEVATED,
        reason: str = "",
        resource_type: str = "",
        action: str = "",
    ) -> PrivilegeElevationRequest:
        """Request a step-up privilege elevation."""
        if request_id in self._step_up_requests:
            raise RuntimeCoreInvariantError(f"Duplicate step_up request_id: {request_id}")
        if session_id not in self._sessions:
            raise RuntimeCoreInvariantError(f"Unknown session_id: {session_id}")
        now = _now_iso()
        req = PrivilegeElevationRequest(
            request_id=request_id,
            session_id=session_id,
            identity_id=identity_id,
            requested_level=requested_level,
            reason=reason,
            resource_type=resource_type,
            action=action,
            status=StepUpStatus.PENDING,
            requested_at=now,
        )
        self._step_up_requests[request_id] = req
        _emit(self._events, "step_up_requested", {
            "request_id": request_id, "session_id": session_id,
            "level": requested_level.value,
        }, session_id)
        return req

    def approve_step_up(
        self,
        decision_id: str,
        request_id: str,
        approver_id: str,
        *,
        reason: str = "",
    ) -> PrivilegeElevationDecision:
        """Approve a step-up request and elevate the session."""
        req = self._step_up_requests.get(request_id)
        if req is None:
            raise RuntimeCoreInvariantError(f"Unknown step_up request_id: {request_id}")
        if req.status != StepUpStatus.PENDING:
            raise RuntimeCoreInvariantError(
                f"Cannot approve step-up in status {req.status.value}"
            )
        now = _now_iso()

        # Update request status
        updated_req = PrivilegeElevationRequest(
            request_id=req.request_id,
            session_id=req.session_id,
            identity_id=req.identity_id,
            requested_level=req.requested_level,
            reason=req.reason,
            resource_type=req.resource_type,
            action=req.action,
            status=StepUpStatus.APPROVED,
            requested_at=req.requested_at,
            metadata=req.metadata,
        )
        self._step_up_requests[request_id] = updated_req

        # Elevate session privilege
        old_session = self._sessions[req.session_id]
        elevated = SessionRecord(
            session_id=old_session.session_id,
            identity_id=old_session.identity_id,
            kind=old_session.kind,
            status=old_session.status,
            privilege_level=req.requested_level,
            scope_ref_id=old_session.scope_ref_id,
            environment_id=old_session.environment_id,
            connector_id=old_session.connector_id,
            campaign_id=old_session.campaign_id,
            opened_at=old_session.opened_at,
            expires_at=old_session.expires_at,
            closed_at=old_session.closed_at,
            metadata=old_session.metadata,
        )
        self._sessions[req.session_id] = elevated

        decision = PrivilegeElevationDecision(
            decision_id=decision_id,
            request_id=request_id,
            approver_id=approver_id,
            status=StepUpStatus.APPROVED,
            reason=reason,
            decided_at=now,
        )
        self._step_up_decisions[decision_id] = decision
        _emit(self._events, "step_up_approved", {
            "decision_id": decision_id, "request_id": request_id,
            "session_id": req.session_id,
        }, req.session_id)
        return decision

    def deny_step_up(
        self,
        decision_id: str,
        request_id: str,
        approver_id: str,
        *,
        reason: str = "",
    ) -> PrivilegeElevationDecision:
        """Deny a step-up request."""
        req = self._step_up_requests.get(request_id)
        if req is None:
            raise RuntimeCoreInvariantError(f"Unknown step_up request_id: {request_id}")
        if req.status != StepUpStatus.PENDING:
            raise RuntimeCoreInvariantError(
                f"Cannot deny step-up in status {req.status.value}"
            )
        now = _now_iso()

        updated_req = PrivilegeElevationRequest(
            request_id=req.request_id,
            session_id=req.session_id,
            identity_id=req.identity_id,
            requested_level=req.requested_level,
            reason=req.reason,
            resource_type=req.resource_type,
            action=req.action,
            status=StepUpStatus.DENIED,
            requested_at=req.requested_at,
            metadata=req.metadata,
        )
        self._step_up_requests[request_id] = updated_req

        decision = PrivilegeElevationDecision(
            decision_id=decision_id,
            request_id=request_id,
            approver_id=approver_id,
            status=StepUpStatus.DENIED,
            reason=reason,
            decided_at=now,
        )
        self._step_up_decisions[decision_id] = decision
        _emit(self._events, "step_up_denied", {
            "decision_id": decision_id, "request_id": request_id,
            "session_id": req.session_id,
        }, req.session_id)
        return decision

    # ------------------------------------------------------------------
    # Session revocation and expiry
    # ------------------------------------------------------------------

    def revoke_session(
        self,
        session_id: str,
        reason: RevocationReason,
        *,
        detail: str = "",
    ) -> RevocationRecord:
        """Revoke an active or suspended session."""
        old = self._sessions.get(session_id)
        if old is None:
            raise RuntimeCoreInvariantError(f"Unknown session_id: {session_id}")
        if old.status not in (SessionStatus.ACTIVE, SessionStatus.SUSPENDED):
            raise RuntimeCoreInvariantError(
                f"Cannot revoke session in status {old.status.value}"
            )
        now = _now_iso()
        self._update_session_status(session_id, SessionStatus.REVOKED)

        rid = stable_identifier("rev", {"sid": session_id, "ts": now})
        revocation = RevocationRecord(
            revocation_id=rid,
            session_id=session_id,
            identity_id=old.identity_id,
            reason=reason,
            detail=detail,
            revoked_at=now,
        )
        self._revocations[rid] = revocation
        _emit(self._events, "session_revoked", {
            "session_id": session_id, "reason": reason.value,
        }, session_id)
        return revocation

    def expire_session(self, session_id: str) -> SessionRecord:
        """Expire an active session."""
        old = self._sessions.get(session_id)
        if old is None:
            raise RuntimeCoreInvariantError(f"Unknown session_id: {session_id}")
        if old.status != SessionStatus.ACTIVE:
            raise RuntimeCoreInvariantError(
                f"Cannot expire session in status {old.status.value}"
            )
        updated = self._update_session_status(session_id, SessionStatus.EXPIRED)
        _emit(self._events, "session_expired", {"session_id": session_id}, session_id)
        return updated

    def suspend_session(self, session_id: str) -> SessionRecord:
        """Suspend an active session."""
        old = self._sessions.get(session_id)
        if old is None:
            raise RuntimeCoreInvariantError(f"Unknown session_id: {session_id}")
        if old.status != SessionStatus.ACTIVE:
            raise RuntimeCoreInvariantError(
                f"Cannot suspend session in status {old.status.value}"
            )
        updated = self._update_session_status(session_id, SessionStatus.SUSPENDED)
        _emit(self._events, "session_suspended", {"session_id": session_id}, session_id)
        return updated

    def close_session(self, session_id: str) -> SessionClosureReport:
        """Close a session and produce a closure report."""
        old = self._sessions.get(session_id)
        if old is None:
            raise RuntimeCoreInvariantError(f"Unknown session_id: {session_id}")
        if old.status not in (SessionStatus.ACTIVE, SessionStatus.SUSPENDED):
            raise RuntimeCoreInvariantError(
                f"Cannot close session in status {old.status.value}"
            )
        now = _now_iso()
        self._update_session_status(session_id, SessionStatus.CLOSED)

        # Compute stats
        enforcements = [e for e in self._enforcement_events.values() if e.session_id == session_id]
        denials = sum(1 for e in enforcements if e.decision == EnforcementDecision.DENIED)
        step_ups = sum(1 for r in self._step_up_requests.values() if r.session_id == session_id)
        revocations = sum(1 for r in self._revocations.values() if r.session_id == session_id)
        bindings = sum(1 for b in self._bindings.values() if b.session_id == session_id)
        constraints = sum(1 for c in self._constraints.values() if c.session_id == session_id)

        report_id = stable_identifier("closure", {"sid": session_id, "ts": now})
        report = SessionClosureReport(
            report_id=report_id,
            session_id=session_id,
            identity_id=old.identity_id,
            total_enforcements=len(enforcements),
            total_denials=denials,
            total_step_ups=step_ups,
            total_revocations=revocations,
            bindings_count=bindings,
            constraints_count=constraints,
            closed_at=now,
        )
        self._closure_reports[report_id] = report
        _emit(self._events, "session_closed", {
            "session_id": session_id, "report_id": report_id,
        }, session_id)
        return report

    # ------------------------------------------------------------------
    # Snapshot
    # ------------------------------------------------------------------

    def session_snapshot(
        self,
        snapshot_id: str,
        scope_ref_id: str = "",
    ) -> SessionSnapshot:
        """Capture a point-in-time session snapshot."""
        if snapshot_id in self._snapshot_ids:
            raise RuntimeCoreInvariantError(f"Duplicate snapshot_id: {snapshot_id}")
        now = _now_iso()
        active = sum(1 for s in self._sessions.values() if s.status == SessionStatus.ACTIVE)
        suspended = sum(1 for s in self._sessions.values() if s.status == SessionStatus.SUSPENDED)
        revoked = sum(1 for s in self._sessions.values() if s.status == SessionStatus.REVOKED)
        snapshot = SessionSnapshot(
            snapshot_id=snapshot_id,
            scope_ref_id=scope_ref_id,
            total_sessions=self.session_count,
            active_sessions=active,
            suspended_sessions=suspended,
            revoked_sessions=revoked,
            total_constraints=self.constraint_count,
            total_step_ups=self.step_up_count,
            total_revocations=self.revocation_count,
            total_enforcements=self.enforcement_count,
            captured_at=now,
        )
        self._snapshot_ids.add(snapshot_id)
        _emit(self._events, "session_snapshot_captured", {
            "snapshot_id": snapshot_id,
        }, snapshot_id)
        return snapshot

    # ------------------------------------------------------------------
    # Audit queries
    # ------------------------------------------------------------------

    def audits_for_session(self, session_id: str) -> tuple[EnforcementAuditRecord, ...]:
        """Return all audit records for a session."""
        return tuple(a for a in self._audits.values() if a.session_id == session_id)

    def revocations_for_session(self, session_id: str) -> tuple[RevocationRecord, ...]:
        """Return all revocations for a session."""
        return tuple(r for r in self._revocations.values() if r.session_id == session_id)

    def enforcements_for_session(self, session_id: str) -> tuple[EnforcementEvent, ...]:
        """Return all enforcement events for a session."""
        return tuple(e for e in self._enforcement_events.values() if e.session_id == session_id)

    # ------------------------------------------------------------------
    # State hash
    # ------------------------------------------------------------------

    def state_hash(self) -> str:
        """Compute a hash of the current engine state."""
        parts = [
            f"sessions={self.session_count}",
            f"active={self.active_session_count}",
            f"constraints={self.constraint_count}",
            f"step_ups={self.step_up_count}",
            f"enforcements={self.enforcement_count}",
            f"revocations={self.revocation_count}",
            f"bindings={self.binding_count}",
            f"audits={self.audit_count}",
        ]
        return sha256("|".join(parts).encode()).hexdigest()
