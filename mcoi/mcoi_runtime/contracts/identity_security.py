"""Purpose: Identity / security / secrets runtime contracts.
Governance scope: identity descriptors, credential lifecycle, delegation chains,
    privilege elevations, security sessions, vault access, recertification,
    break-glass records, security snapshots, and closure reports.
Dependencies: _base contract utilities.
Invariants:
  - Every identity is tenant-scoped and typed.
  - Credential lifecycle is explicit and traceable.
  - All outputs are frozen and auditable.
  - Break-glass is a privileged escalation that creates a violation.
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
    require_unit_float,
)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class IdentityType(Enum):
    """Type of identity principal."""
    HUMAN = "human"
    MACHINE = "machine"
    SERVICE = "service"
    DELEGATED = "delegated"


class CredentialStatus(Enum):
    """Lifecycle state of a credential."""
    ACTIVE = "active"
    ROTATED = "rotated"
    REVOKED = "revoked"
    EXPIRED = "expired"


class PrivilegeLevel(Enum):
    """Privilege level of an identity."""
    STANDARD = "standard"
    ELEVATED = "elevated"
    ADMIN = "admin"
    BREAK_GLASS = "break_glass"


class SessionSecurityStatus(Enum):
    """Status of a security session."""
    ACTIVE = "active"
    LOCKED = "locked"
    EXPIRED = "expired"
    TERMINATED = "terminated"


class RecertificationStatus(Enum):
    """Status of a recertification request."""
    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"
    EXPIRED = "expired"


class VaultOperation(Enum):
    """Vault access operation type."""
    READ = "read"
    WRITE = "write"
    ROTATE = "rotate"
    DELETE = "delete"
    SEAL = "seal"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class IdentityDescriptor(ContractRecord):
    """A registered identity principal."""

    identity_id: str = ""
    tenant_id: str = ""
    display_name: str = ""
    identity_type: IdentityType = IdentityType.HUMAN
    credential_status: CredentialStatus = CredentialStatus.ACTIVE
    privilege_level: PrivilegeLevel = PrivilegeLevel.STANDARD
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "identity_id", require_non_empty_text(self.identity_id, "identity_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "display_name", require_non_empty_text(self.display_name, "display_name"))
        if not isinstance(self.identity_type, IdentityType):
            raise ValueError("identity_type must be an IdentityType")
        if not isinstance(self.credential_status, CredentialStatus):
            raise ValueError("credential_status must be a CredentialStatus")
        if not isinstance(self.privilege_level, PrivilegeLevel):
            raise ValueError("privilege_level must be a PrivilegeLevel")
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class CredentialRecord(ContractRecord):
    """A credential bound to an identity."""

    credential_id: str = ""
    tenant_id: str = ""
    identity_ref: str = ""
    status: CredentialStatus = CredentialStatus.ACTIVE
    algorithm: str = ""
    expires_at: str = ""
    rotated_at: str = ""
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "credential_id", require_non_empty_text(self.credential_id, "credential_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "identity_ref", require_non_empty_text(self.identity_ref, "identity_ref"))
        if not isinstance(self.status, CredentialStatus):
            raise ValueError("status must be a CredentialStatus")
        object.__setattr__(self, "algorithm", require_non_empty_text(self.algorithm, "algorithm"))
        require_datetime_text(self.expires_at, "expires_at")
        if self.rotated_at:
            require_datetime_text(self.rotated_at, "rotated_at")
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class DelegationChain(ContractRecord):
    """A delegation chain linking delegator to delegate within a scope."""

    chain_id: str = ""
    tenant_id: str = ""
    delegator_ref: str = ""
    delegate_ref: str = ""
    scope_ref: str = ""
    depth: int = 0
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "chain_id", require_non_empty_text(self.chain_id, "chain_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "delegator_ref", require_non_empty_text(self.delegator_ref, "delegator_ref"))
        object.__setattr__(self, "delegate_ref", require_non_empty_text(self.delegate_ref, "delegate_ref"))
        object.__setattr__(self, "scope_ref", require_non_empty_text(self.scope_ref, "scope_ref"))
        object.__setattr__(self, "depth", require_non_negative_int(self.depth, "depth"))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class PrivilegeElevation(ContractRecord):
    """A request or record of privilege elevation."""

    elevation_id: str = ""
    tenant_id: str = ""
    identity_ref: str = ""
    from_level: PrivilegeLevel = PrivilegeLevel.STANDARD
    to_level: PrivilegeLevel = PrivilegeLevel.ELEVATED
    reason: str = ""
    approved_by: str = ""
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "elevation_id", require_non_empty_text(self.elevation_id, "elevation_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "identity_ref", require_non_empty_text(self.identity_ref, "identity_ref"))
        if not isinstance(self.from_level, PrivilegeLevel):
            raise ValueError("from_level must be a PrivilegeLevel")
        if not isinstance(self.to_level, PrivilegeLevel):
            raise ValueError("to_level must be a PrivilegeLevel")
        object.__setattr__(self, "reason", require_non_empty_text(self.reason, "reason"))
        object.__setattr__(self, "approved_by", require_non_empty_text(self.approved_by, "approved_by"))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class SecuritySession(ContractRecord):
    """A security session for an identity."""

    session_id: str = ""
    tenant_id: str = ""
    identity_ref: str = ""
    status: SessionSecurityStatus = SessionSecurityStatus.ACTIVE
    ip_ref: str = ""
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "session_id", require_non_empty_text(self.session_id, "session_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "identity_ref", require_non_empty_text(self.identity_ref, "identity_ref"))
        if not isinstance(self.status, SessionSecurityStatus):
            raise ValueError("status must be a SessionSecurityStatus")
        object.__setattr__(self, "ip_ref", require_non_empty_text(self.ip_ref, "ip_ref"))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class VaultAccessRecord(ContractRecord):
    """A record of vault access."""

    access_id: str = ""
    tenant_id: str = ""
    identity_ref: str = ""
    secret_ref: str = ""
    operation: VaultOperation = VaultOperation.READ
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "access_id", require_non_empty_text(self.access_id, "access_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "identity_ref", require_non_empty_text(self.identity_ref, "identity_ref"))
        object.__setattr__(self, "secret_ref", require_non_empty_text(self.secret_ref, "secret_ref"))
        if not isinstance(self.operation, VaultOperation):
            raise ValueError("operation must be a VaultOperation")
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class RecertificationRecord(ContractRecord):
    """A recertification request for an identity."""

    recert_id: str = ""
    tenant_id: str = ""
    identity_ref: str = ""
    status: RecertificationStatus = RecertificationStatus.PENDING
    reviewer_ref: str = ""
    decided_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "recert_id", require_non_empty_text(self.recert_id, "recert_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "identity_ref", require_non_empty_text(self.identity_ref, "identity_ref"))
        if not isinstance(self.status, RecertificationStatus):
            raise ValueError("status must be a RecertificationStatus")
        object.__setattr__(self, "reviewer_ref", require_non_empty_text(self.reviewer_ref, "reviewer_ref"))
        require_datetime_text(self.decided_at, "decided_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class BreakGlassRecord(ContractRecord):
    """A break-glass emergency access record."""

    break_id: str = ""
    tenant_id: str = ""
    identity_ref: str = ""
    reason: str = ""
    authorized_by: str = ""
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "break_id", require_non_empty_text(self.break_id, "break_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "identity_ref", require_non_empty_text(self.identity_ref, "identity_ref"))
        object.__setattr__(self, "reason", require_non_empty_text(self.reason, "reason"))
        object.__setattr__(self, "authorized_by", require_non_empty_text(self.authorized_by, "authorized_by"))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class SecuritySnapshot(ContractRecord):
    """Point-in-time snapshot of identity/security state."""

    snapshot_id: str = ""
    tenant_id: str = ""
    total_identities: int = 0
    total_credentials: int = 0
    total_sessions: int = 0
    total_elevations: int = 0
    total_vault_accesses: int = 0
    total_violations: int = 0
    captured_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "snapshot_id", require_non_empty_text(self.snapshot_id, "snapshot_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "total_identities", require_non_negative_int(self.total_identities, "total_identities"))
        object.__setattr__(self, "total_credentials", require_non_negative_int(self.total_credentials, "total_credentials"))
        object.__setattr__(self, "total_sessions", require_non_negative_int(self.total_sessions, "total_sessions"))
        object.__setattr__(self, "total_elevations", require_non_negative_int(self.total_elevations, "total_elevations"))
        object.__setattr__(self, "total_vault_accesses", require_non_negative_int(self.total_vault_accesses, "total_vault_accesses"))
        object.__setattr__(self, "total_violations", require_non_negative_int(self.total_violations, "total_violations"))
        require_datetime_text(self.captured_at, "captured_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class SecurityClosureReport(ContractRecord):
    """Closure report for identity/security state."""

    report_id: str = ""
    tenant_id: str = ""
    total_identities: int = 0
    total_credentials: int = 0
    total_sessions: int = 0
    total_violations: int = 0
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "report_id", require_non_empty_text(self.report_id, "report_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "total_identities", require_non_negative_int(self.total_identities, "total_identities"))
        object.__setattr__(self, "total_credentials", require_non_negative_int(self.total_credentials, "total_credentials"))
        object.__setattr__(self, "total_sessions", require_non_negative_int(self.total_sessions, "total_sessions"))
        object.__setattr__(self, "total_violations", require_non_negative_int(self.total_violations, "total_violations"))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class SecurityAssessment(ContractRecord):
    """Assessment of security posture for a tenant."""

    assessment_id: str = ""
    tenant_id: str = ""
    total_identities: int = 0
    total_credentials: int = 0
    total_sessions: int = 0
    total_violations: int = 0
    posture_score: float = 0.0
    assessed_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "assessment_id", require_non_empty_text(self.assessment_id, "assessment_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "total_identities", require_non_negative_int(self.total_identities, "total_identities"))
        object.__setattr__(self, "total_credentials", require_non_negative_int(self.total_credentials, "total_credentials"))
        object.__setattr__(self, "total_sessions", require_non_negative_int(self.total_sessions, "total_sessions"))
        object.__setattr__(self, "total_violations", require_non_negative_int(self.total_violations, "total_violations"))
        object.__setattr__(self, "posture_score", require_unit_float(self.posture_score, "posture_score"))
        require_datetime_text(self.assessed_at, "assessed_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))
