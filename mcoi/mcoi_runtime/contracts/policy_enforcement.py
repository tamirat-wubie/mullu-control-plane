"""Purpose: policy enforcement / session authorization runtime contracts.
Governance scope: typed descriptors for live sessions, constraints, privilege
    elevation, enforcement decisions, revocations, audits, and snapshots.
Dependencies: _base contract utilities.
Invariants:
  - Every session has explicit kind, identity scope, and creation time.
  - Sessions are fail-closed — default enforcement decision is DENY.
  - Privilege elevation requires explicit approval.
  - Revocations are permanent and audited.
  - All outputs are frozen.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping

from ._base import (
    ContractRecord,
    freeze_value,
    require_datetime_text,
    require_non_empty_text,
    require_non_negative_int,
)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class SessionStatus(Enum):
    """Status of a live session."""
    ACTIVE = "active"
    SUSPENDED = "suspended"
    EXPIRED = "expired"
    REVOKED = "revoked"
    CLOSED = "closed"


class SessionKind(Enum):
    """Kind of session."""
    INTERACTIVE = "interactive"
    SERVICE = "service"
    CONNECTOR = "connector"
    CAMPAIGN = "campaign"
    SYSTEM = "system"


class PrivilegeLevel(Enum):
    """Level of privilege for session actions."""
    STANDARD = "standard"
    ELEVATED = "elevated"
    ADMIN = "admin"
    SYSTEM = "system"
    EMERGENCY = "emergency"


class EnforcementDecision(Enum):
    """Decision from policy enforcement evaluation."""
    ALLOWED = "allowed"
    DENIED = "denied"
    STEP_UP_REQUIRED = "step_up_required"
    SUSPENDED = "suspended"
    REVOKED = "revoked"


class RevocationReason(Enum):
    """Reason a session was revoked."""
    POLICY_VIOLATION = "policy_violation"
    TENANT_CHANGE = "tenant_change"
    ENVIRONMENT_CHANGE = "environment_change"
    RISK_ESCALATION = "risk_escalation"
    COMPLIANCE_FAILURE = "compliance_failure"
    MANUAL_REVOCATION = "manual_revocation"
    DELEGATION_EXPIRED = "delegation_expired"


class StepUpStatus(Enum):
    """Status of a privilege elevation (step-up) request."""
    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"
    EXPIRED = "expired"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class SessionRecord(ContractRecord):
    """A live session in the platform."""

    session_id: str = ""
    identity_id: str = ""
    kind: SessionKind = SessionKind.INTERACTIVE
    status: SessionStatus = SessionStatus.ACTIVE
    privilege_level: PrivilegeLevel = PrivilegeLevel.STANDARD
    scope_ref_id: str = ""
    environment_id: str = ""
    connector_id: str = ""
    campaign_id: str = ""
    opened_at: str = ""
    expires_at: str = ""
    closed_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "session_id", require_non_empty_text(self.session_id, "session_id"))
        object.__setattr__(self, "identity_id", require_non_empty_text(self.identity_id, "identity_id"))
        if not isinstance(self.kind, SessionKind):
            raise ValueError("kind must be a SessionKind")
        if not isinstance(self.status, SessionStatus):
            raise ValueError("status must be a SessionStatus")
        if not isinstance(self.privilege_level, PrivilegeLevel):
            raise ValueError("privilege_level must be a PrivilegeLevel")
        require_datetime_text(self.opened_at, "opened_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class SessionConstraint(ContractRecord):
    """A constraint applied to a session."""

    constraint_id: str = ""
    session_id: str = ""
    resource_type: str = ""
    action: str = ""
    environment_id: str = ""
    connector_id: str = ""
    max_privilege: PrivilegeLevel = PrivilegeLevel.STANDARD
    valid_from: str = ""
    valid_until: str = ""
    created_at: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "constraint_id", require_non_empty_text(self.constraint_id, "constraint_id"))
        object.__setattr__(self, "session_id", require_non_empty_text(self.session_id, "session_id"))
        if not isinstance(self.max_privilege, PrivilegeLevel):
            raise ValueError("max_privilege must be a PrivilegeLevel")
        require_datetime_text(self.created_at, "created_at")


@dataclass(frozen=True, slots=True)
class PrivilegeElevationRequest(ContractRecord):
    """A request to elevate session privileges (step-up)."""

    request_id: str = ""
    session_id: str = ""
    identity_id: str = ""
    requested_level: PrivilegeLevel = PrivilegeLevel.ELEVATED
    reason: str = ""
    resource_type: str = ""
    action: str = ""
    status: StepUpStatus = StepUpStatus.PENDING
    requested_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "request_id", require_non_empty_text(self.request_id, "request_id"))
        object.__setattr__(self, "session_id", require_non_empty_text(self.session_id, "session_id"))
        object.__setattr__(self, "identity_id", require_non_empty_text(self.identity_id, "identity_id"))
        if not isinstance(self.requested_level, PrivilegeLevel):
            raise ValueError("requested_level must be a PrivilegeLevel")
        if not isinstance(self.status, StepUpStatus):
            raise ValueError("status must be a StepUpStatus")
        require_datetime_text(self.requested_at, "requested_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class PrivilegeElevationDecision(ContractRecord):
    """Decision on a privilege elevation request."""

    decision_id: str = ""
    request_id: str = ""
    approver_id: str = ""
    status: StepUpStatus = StepUpStatus.DENIED
    reason: str = ""
    decided_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "decision_id", require_non_empty_text(self.decision_id, "decision_id"))
        object.__setattr__(self, "request_id", require_non_empty_text(self.request_id, "request_id"))
        object.__setattr__(self, "approver_id", require_non_empty_text(self.approver_id, "approver_id"))
        if not isinstance(self.status, StepUpStatus):
            raise ValueError("status must be a StepUpStatus")
        require_datetime_text(self.decided_at, "decided_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class EnforcementEvent(ContractRecord):
    """An enforcement event (decision record for a session action)."""

    event_id: str = ""
    session_id: str = ""
    identity_id: str = ""
    resource_type: str = ""
    action: str = ""
    decision: EnforcementDecision = EnforcementDecision.DENIED
    reason: str = ""
    environment_id: str = ""
    connector_id: str = ""
    evaluated_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "event_id", require_non_empty_text(self.event_id, "event_id"))
        object.__setattr__(self, "session_id", require_non_empty_text(self.session_id, "session_id"))
        object.__setattr__(self, "identity_id", require_non_empty_text(self.identity_id, "identity_id"))
        if not isinstance(self.decision, EnforcementDecision):
            raise ValueError("decision must be an EnforcementDecision")
        require_datetime_text(self.evaluated_at, "evaluated_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class RevocationRecord(ContractRecord):
    """Record of a session revocation."""

    revocation_id: str = ""
    session_id: str = ""
    identity_id: str = ""
    reason: RevocationReason = RevocationReason.MANUAL_REVOCATION
    detail: str = ""
    revoked_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "revocation_id", require_non_empty_text(self.revocation_id, "revocation_id"))
        object.__setattr__(self, "session_id", require_non_empty_text(self.session_id, "session_id"))
        object.__setattr__(self, "identity_id", require_non_empty_text(self.identity_id, "identity_id"))
        if not isinstance(self.reason, RevocationReason):
            raise ValueError("reason must be a RevocationReason")
        require_datetime_text(self.revoked_at, "revoked_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class SessionSnapshot(ContractRecord):
    """Point-in-time session state snapshot."""

    snapshot_id: str = ""
    scope_ref_id: str = ""
    total_sessions: int = 0
    active_sessions: int = 0
    suspended_sessions: int = 0
    revoked_sessions: int = 0
    total_constraints: int = 0
    total_step_ups: int = 0
    total_revocations: int = 0
    total_enforcements: int = 0
    captured_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "snapshot_id", require_non_empty_text(self.snapshot_id, "snapshot_id"))
        object.__setattr__(self, "total_sessions", require_non_negative_int(self.total_sessions, "total_sessions"))
        object.__setattr__(self, "active_sessions", require_non_negative_int(self.active_sessions, "active_sessions"))
        object.__setattr__(self, "suspended_sessions", require_non_negative_int(self.suspended_sessions, "suspended_sessions"))
        object.__setattr__(self, "revoked_sessions", require_non_negative_int(self.revoked_sessions, "revoked_sessions"))
        object.__setattr__(self, "total_constraints", require_non_negative_int(self.total_constraints, "total_constraints"))
        object.__setattr__(self, "total_step_ups", require_non_negative_int(self.total_step_ups, "total_step_ups"))
        object.__setattr__(self, "total_revocations", require_non_negative_int(self.total_revocations, "total_revocations"))
        object.__setattr__(self, "total_enforcements", require_non_negative_int(self.total_enforcements, "total_enforcements"))
        require_datetime_text(self.captured_at, "captured_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class EnforcementAuditRecord(ContractRecord):
    """Audit record for enforcement operations."""

    audit_id: str = ""
    session_id: str = ""
    identity_id: str = ""
    action: str = ""
    resource_type: str = ""
    decision: EnforcementDecision = EnforcementDecision.DENIED
    environment_id: str = ""
    connector_id: str = ""
    recorded_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "audit_id", require_non_empty_text(self.audit_id, "audit_id"))
        object.__setattr__(self, "session_id", require_non_empty_text(self.session_id, "session_id"))
        object.__setattr__(self, "identity_id", require_non_empty_text(self.identity_id, "identity_id"))
        if not isinstance(self.decision, EnforcementDecision):
            raise ValueError("decision must be an EnforcementDecision")
        require_datetime_text(self.recorded_at, "recorded_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class PolicySessionBinding(ContractRecord):
    """Binds a session to a specific resource scope."""

    binding_id: str = ""
    session_id: str = ""
    resource_type: str = ""
    resource_id: str = ""
    bound_at: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "binding_id", require_non_empty_text(self.binding_id, "binding_id"))
        object.__setattr__(self, "session_id", require_non_empty_text(self.session_id, "session_id"))
        object.__setattr__(self, "resource_type", require_non_empty_text(self.resource_type, "resource_type"))
        object.__setattr__(self, "resource_id", require_non_empty_text(self.resource_id, "resource_id"))
        require_datetime_text(self.bound_at, "bound_at")


@dataclass(frozen=True, slots=True)
class SessionClosureReport(ContractRecord):
    """Summary report when a session closes."""

    report_id: str = ""
    session_id: str = ""
    identity_id: str = ""
    total_enforcements: int = 0
    total_denials: int = 0
    total_step_ups: int = 0
    total_revocations: int = 0
    bindings_count: int = 0
    constraints_count: int = 0
    closed_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "report_id", require_non_empty_text(self.report_id, "report_id"))
        object.__setattr__(self, "session_id", require_non_empty_text(self.session_id, "session_id"))
        object.__setattr__(self, "identity_id", require_non_empty_text(self.identity_id, "identity_id"))
        object.__setattr__(self, "total_enforcements", require_non_negative_int(self.total_enforcements, "total_enforcements"))
        object.__setattr__(self, "total_denials", require_non_negative_int(self.total_denials, "total_denials"))
        object.__setattr__(self, "total_step_ups", require_non_negative_int(self.total_step_ups, "total_step_ups"))
        object.__setattr__(self, "total_revocations", require_non_negative_int(self.total_revocations, "total_revocations"))
        object.__setattr__(self, "bindings_count", require_non_negative_int(self.bindings_count, "bindings_count"))
        object.__setattr__(self, "constraints_count", require_non_negative_int(self.constraints_count, "constraints_count"))
        require_datetime_text(self.closed_at, "closed_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))
