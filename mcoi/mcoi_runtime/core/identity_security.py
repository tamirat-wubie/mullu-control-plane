"""Purpose: Identity / security / secrets runtime engine.
Governance scope: governed identity registration, credential lifecycle,
    delegation chains, privilege elevation, security sessions, vault access,
    recertification, break-glass records, and security violation detection.
Dependencies: event_spine, invariants, identity_security contracts.
Invariants:
  - Every identity is tenant-scoped and typed.
  - Duplicate IDs are rejected fail-closed.
  - Terminal credential/session states block further mutations.
  - Break-glass creates an auto-elevation and a violation.
  - All outputs are frozen.
"""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from typing import Any

from mcoi_runtime.contracts.event import EventRecord, EventSource, EventType
from mcoi_runtime.contracts.identity_security import (
    BreakGlassRecord,
    CredentialRecord,
    CredentialStatus,
    DelegationChain,
    IdentityDescriptor,
    IdentityType,
    PrivilegeElevation,
    PrivilegeLevel,
    RecertificationRecord,
    RecertificationStatus,
    SecurityAssessment,
    SecurityClosureReport,
    SecuritySession,
    SecuritySnapshot,
    SessionSecurityStatus,
    VaultAccessRecord,
    VaultOperation,
)
from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError, stable_identifier


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_CREDENTIAL_TERMINAL = frozenset({CredentialStatus.REVOKED, CredentialStatus.EXPIRED})
_SESSION_TERMINAL = frozenset({SessionSecurityStatus.EXPIRED, SessionSecurityStatus.TERMINATED})
_RECERT_TERMINAL = frozenset({RecertificationStatus.APPROVED, RecertificationStatus.DENIED, RecertificationStatus.EXPIRED})


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _emit(es: EventSpineEngine, action: str, payload: dict[str, Any], cid: str) -> None:
    now = _now_iso()
    payload["action"] = action
    event = EventRecord(
        event_id=stable_identifier("evt-idsec", {"action": action, "ts": now, "cid": cid}),
        event_type=EventType.CUSTOM,
        source=EventSource.COMMUNICATION_SYSTEM,
        correlation_id=cid,
        payload=payload,
        emitted_at=now,
    )
    es.emit(event)


class IdentitySecurityEngine:
    """Governed identity and security engine."""

    def __init__(self, event_spine: EventSpineEngine) -> None:
        if not isinstance(event_spine, EventSpineEngine):
            raise RuntimeCoreInvariantError("event_spine must be an EventSpineEngine")
        self._events = event_spine
        self._identities: dict[str, IdentityDescriptor] = {}
        self._credentials: dict[str, CredentialRecord] = {}
        self._chains: dict[str, DelegationChain] = {}
        self._elevations: dict[str, PrivilegeElevation] = {}
        self._sessions: dict[str, SecuritySession] = {}
        self._vault_accesses: dict[str, VaultAccessRecord] = {}
        self._recertifications: dict[str, RecertificationRecord] = {}
        self._break_glass: dict[str, BreakGlassRecord] = {}
        self._violations: dict[str, dict[str, Any]] = {}

    # -- Properties --

    @property
    def identity_count(self) -> int:
        return len(self._identities)

    @property
    def credential_count(self) -> int:
        return len(self._credentials)

    @property
    def chain_count(self) -> int:
        return len(self._chains)

    @property
    def elevation_count(self) -> int:
        return len(self._elevations)

    @property
    def session_count(self) -> int:
        return len(self._sessions)

    @property
    def vault_access_count(self) -> int:
        return len(self._vault_accesses)

    @property
    def recertification_count(self) -> int:
        return len(self._recertifications)

    @property
    def break_glass_count(self) -> int:
        return len(self._break_glass)

    @property
    def violation_count(self) -> int:
        return len(self._violations)

    # -- Identities --

    def register_identity(
        self,
        identity_id: str,
        tenant_id: str,
        display_name: str,
        identity_type: IdentityType = IdentityType.HUMAN,
        privilege_level: PrivilegeLevel = PrivilegeLevel.STANDARD,
    ) -> IdentityDescriptor:
        if identity_id in self._identities:
            raise RuntimeCoreInvariantError("duplicate identity_id")
        now = _now_iso()
        identity = IdentityDescriptor(
            identity_id=identity_id, tenant_id=tenant_id,
            display_name=display_name, identity_type=identity_type,
            credential_status=CredentialStatus.ACTIVE,
            privilege_level=privilege_level, created_at=now,
        )
        self._identities[identity_id] = identity
        _emit(self._events, "register_identity", {"identity_id": identity_id}, identity_id)
        return identity

    def get_identity(self, identity_id: str) -> IdentityDescriptor:
        if identity_id not in self._identities:
            raise RuntimeCoreInvariantError("unknown identity_id")
        return self._identities[identity_id]

    def identities_for_tenant(self, tenant_id: str) -> tuple[IdentityDescriptor, ...]:
        return tuple(i for i in self._identities.values() if i.tenant_id == tenant_id)

    # -- Credentials --

    def register_credential(
        self,
        credential_id: str,
        tenant_id: str,
        identity_ref: str,
        algorithm: str = "RSA-256",
        expires_at: str = "",
    ) -> CredentialRecord:
        if credential_id in self._credentials:
            raise RuntimeCoreInvariantError("duplicate credential_id")
        now = _now_iso()
        if not expires_at:
            expires_at = now
        cred = CredentialRecord(
            credential_id=credential_id, tenant_id=tenant_id,
            identity_ref=identity_ref, status=CredentialStatus.ACTIVE,
            algorithm=algorithm, expires_at=expires_at, created_at=now,
        )
        self._credentials[credential_id] = cred
        _emit(self._events, "register_credential", {"credential_id": credential_id}, credential_id)
        return cred

    def rotate_credential(self, credential_id: str, new_credential_id: str) -> CredentialRecord:
        if credential_id not in self._credentials:
            raise RuntimeCoreInvariantError("unknown credential_id")
        old = self._credentials[credential_id]
        if old.status in _CREDENTIAL_TERMINAL:
            raise RuntimeCoreInvariantError("credential is in terminal state")
        now = _now_iso()
        # Mark old as ROTATED
        rotated = CredentialRecord(
            credential_id=old.credential_id, tenant_id=old.tenant_id,
            identity_ref=old.identity_ref, status=CredentialStatus.ROTATED,
            algorithm=old.algorithm, expires_at=old.expires_at,
            rotated_at=now, created_at=old.created_at,
        )
        self._credentials[credential_id] = rotated
        # Create new credential linked to same identity
        if new_credential_id in self._credentials:
            raise RuntimeCoreInvariantError("duplicate credential_id")
        new_cred = CredentialRecord(
            credential_id=new_credential_id, tenant_id=old.tenant_id,
            identity_ref=old.identity_ref, status=CredentialStatus.ACTIVE,
            algorithm=old.algorithm, expires_at=old.expires_at,
            created_at=now,
        )
        self._credentials[new_credential_id] = new_cred
        _emit(self._events, "rotate_credential", {
            "old_credential_id": credential_id, "new_credential_id": new_credential_id,
        }, credential_id)
        return new_cred

    def revoke_credential(self, credential_id: str) -> CredentialRecord:
        if credential_id not in self._credentials:
            raise RuntimeCoreInvariantError("unknown credential_id")
        old = self._credentials[credential_id]
        if old.status in _CREDENTIAL_TERMINAL:
            raise RuntimeCoreInvariantError("credential is in terminal state")
        now = _now_iso()
        updated = CredentialRecord(
            credential_id=old.credential_id, tenant_id=old.tenant_id,
            identity_ref=old.identity_ref, status=CredentialStatus.REVOKED,
            algorithm=old.algorithm, expires_at=old.expires_at,
            rotated_at=old.rotated_at, created_at=now,
        )
        self._credentials[credential_id] = updated
        _emit(self._events, "revoke_credential", {"credential_id": credential_id}, credential_id)
        return updated

    def expire_credential(self, credential_id: str) -> CredentialRecord:
        if credential_id not in self._credentials:
            raise RuntimeCoreInvariantError("unknown credential_id")
        old = self._credentials[credential_id]
        if old.status in _CREDENTIAL_TERMINAL:
            raise RuntimeCoreInvariantError("credential is in terminal state")
        now = _now_iso()
        updated = CredentialRecord(
            credential_id=old.credential_id, tenant_id=old.tenant_id,
            identity_ref=old.identity_ref, status=CredentialStatus.EXPIRED,
            algorithm=old.algorithm, expires_at=old.expires_at,
            rotated_at=old.rotated_at, created_at=now,
        )
        self._credentials[credential_id] = updated
        _emit(self._events, "expire_credential", {"credential_id": credential_id}, credential_id)
        return updated

    # -- Delegation Chains --

    def create_delegation_chain(
        self,
        chain_id: str,
        tenant_id: str,
        delegator_ref: str,
        delegate_ref: str,
        scope_ref: str,
        depth: int = 0,
    ) -> DelegationChain:
        if chain_id in self._chains:
            raise RuntimeCoreInvariantError("duplicate chain_id")
        # Validate delegator exists
        if delegator_ref not in self._identities:
            raise RuntimeCoreInvariantError("unknown delegator identity")
        now = _now_iso()
        chain = DelegationChain(
            chain_id=chain_id, tenant_id=tenant_id,
            delegator_ref=delegator_ref, delegate_ref=delegate_ref,
            scope_ref=scope_ref, depth=depth, created_at=now,
        )
        self._chains[chain_id] = chain
        _emit(self._events, "create_delegation_chain", {"chain_id": chain_id}, chain_id)
        return chain

    def get_chain(self, chain_id: str) -> DelegationChain:
        if chain_id not in self._chains:
            raise RuntimeCoreInvariantError("unknown chain_id")
        return self._chains[chain_id]

    # -- Privilege Elevation --

    def request_elevation(
        self,
        elevation_id: str,
        tenant_id: str,
        identity_ref: str,
        to_level: PrivilegeLevel,
        reason: str,
        approved_by: str = "pending",
    ) -> PrivilegeElevation:
        if elevation_id in self._elevations:
            raise RuntimeCoreInvariantError("duplicate elevation_id")
        identity = self.get_identity(identity_ref)
        now = _now_iso()
        elevation = PrivilegeElevation(
            elevation_id=elevation_id, tenant_id=tenant_id,
            identity_ref=identity_ref, from_level=identity.privilege_level,
            to_level=to_level, reason=reason, approved_by=approved_by,
            created_at=now,
        )
        self._elevations[elevation_id] = elevation
        _emit(self._events, "request_elevation", {"elevation_id": elevation_id}, elevation_id)
        return elevation

    def approve_elevation(self, elevation_id: str, approved_by: str) -> PrivilegeElevation:
        if elevation_id not in self._elevations:
            raise RuntimeCoreInvariantError("unknown elevation_id")
        old = self._elevations[elevation_id]
        now = _now_iso()
        updated = PrivilegeElevation(
            elevation_id=old.elevation_id, tenant_id=old.tenant_id,
            identity_ref=old.identity_ref, from_level=old.from_level,
            to_level=old.to_level, reason=old.reason,
            approved_by=approved_by, created_at=now,
        )
        self._elevations[elevation_id] = updated
        # Update the identity's privilege level
        identity = self._identities[old.identity_ref]
        updated_identity = IdentityDescriptor(
            identity_id=identity.identity_id, tenant_id=identity.tenant_id,
            display_name=identity.display_name, identity_type=identity.identity_type,
            credential_status=identity.credential_status,
            privilege_level=old.to_level, created_at=identity.created_at,
            metadata=dict(identity.metadata),
        )
        self._identities[old.identity_ref] = updated_identity
        _emit(self._events, "approve_elevation", {"elevation_id": elevation_id}, elevation_id)
        return updated

    # -- Security Sessions --

    def create_session(
        self,
        session_id: str,
        tenant_id: str,
        identity_ref: str,
        ip_ref: str = "0.0.0.0",
    ) -> SecuritySession:
        if session_id in self._sessions:
            raise RuntimeCoreInvariantError("duplicate session_id")
        now = _now_iso()
        session = SecuritySession(
            session_id=session_id, tenant_id=tenant_id,
            identity_ref=identity_ref, status=SessionSecurityStatus.ACTIVE,
            ip_ref=ip_ref, created_at=now,
        )
        self._sessions[session_id] = session
        _emit(self._events, "create_session", {"session_id": session_id}, session_id)
        return session

    def _update_session_status(self, session_id: str, new_status: SessionSecurityStatus) -> SecuritySession:
        if session_id not in self._sessions:
            raise RuntimeCoreInvariantError("unknown session_id")
        old = self._sessions[session_id]
        if old.status in _SESSION_TERMINAL:
            raise RuntimeCoreInvariantError("session is in terminal state")
        now = _now_iso()
        updated = SecuritySession(
            session_id=old.session_id, tenant_id=old.tenant_id,
            identity_ref=old.identity_ref, status=new_status,
            ip_ref=old.ip_ref, created_at=now,
        )
        self._sessions[session_id] = updated
        return updated

    def lock_session(self, session_id: str) -> SecuritySession:
        updated = self._update_session_status(session_id, SessionSecurityStatus.LOCKED)
        _emit(self._events, "lock_session", {"session_id": session_id}, session_id)
        return updated

    def expire_session(self, session_id: str) -> SecuritySession:
        updated = self._update_session_status(session_id, SessionSecurityStatus.EXPIRED)
        _emit(self._events, "expire_session", {"session_id": session_id}, session_id)
        return updated

    def terminate_session(self, session_id: str) -> SecuritySession:
        updated = self._update_session_status(session_id, SessionSecurityStatus.TERMINATED)
        _emit(self._events, "terminate_session", {"session_id": session_id}, session_id)
        return updated

    # -- Vault Access --

    def record_vault_access(
        self,
        access_id: str,
        tenant_id: str,
        identity_ref: str,
        secret_ref: str,
        operation: VaultOperation = VaultOperation.READ,
    ) -> VaultAccessRecord:
        if access_id in self._vault_accesses:
            raise RuntimeCoreInvariantError("duplicate access_id")
        now = _now_iso()
        record = VaultAccessRecord(
            access_id=access_id, tenant_id=tenant_id,
            identity_ref=identity_ref, secret_ref=secret_ref,
            operation=operation, created_at=now,
        )
        self._vault_accesses[access_id] = record
        _emit(self._events, "record_vault_access", {"access_id": access_id}, access_id)
        return record

    # -- Recertification --

    def request_recertification(
        self,
        recert_id: str,
        tenant_id: str,
        identity_ref: str,
        reviewer_ref: str,
    ) -> RecertificationRecord:
        if recert_id in self._recertifications:
            raise RuntimeCoreInvariantError("duplicate recert_id")
        now = _now_iso()
        record = RecertificationRecord(
            recert_id=recert_id, tenant_id=tenant_id,
            identity_ref=identity_ref, status=RecertificationStatus.PENDING,
            reviewer_ref=reviewer_ref, decided_at=now,
        )
        self._recertifications[recert_id] = record
        _emit(self._events, "request_recertification", {"recert_id": recert_id}, recert_id)
        return record

    def _update_recert_status(self, recert_id: str, new_status: RecertificationStatus) -> RecertificationRecord:
        if recert_id not in self._recertifications:
            raise RuntimeCoreInvariantError("unknown recert_id")
        old = self._recertifications[recert_id]
        if old.status in _RECERT_TERMINAL:
            raise RuntimeCoreInvariantError("recertification is in terminal state")
        now = _now_iso()
        updated = RecertificationRecord(
            recert_id=old.recert_id, tenant_id=old.tenant_id,
            identity_ref=old.identity_ref, status=new_status,
            reviewer_ref=old.reviewer_ref, decided_at=now,
        )
        self._recertifications[recert_id] = updated
        return updated

    def approve_recertification(self, recert_id: str) -> RecertificationRecord:
        updated = self._update_recert_status(recert_id, RecertificationStatus.APPROVED)
        _emit(self._events, "approve_recertification", {"recert_id": recert_id}, recert_id)
        return updated

    def deny_recertification(self, recert_id: str) -> RecertificationRecord:
        updated = self._update_recert_status(recert_id, RecertificationStatus.DENIED)
        _emit(self._events, "deny_recertification", {"recert_id": recert_id}, recert_id)
        return updated

    # -- Break Glass --

    def record_break_glass(
        self,
        break_id: str,
        tenant_id: str,
        identity_ref: str,
        reason: str,
        authorized_by: str,
    ) -> BreakGlassRecord:
        if break_id in self._break_glass:
            raise RuntimeCoreInvariantError("duplicate break_id")
        now = _now_iso()
        record = BreakGlassRecord(
            break_id=break_id, tenant_id=tenant_id,
            identity_ref=identity_ref, reason=reason,
            authorized_by=authorized_by, created_at=now,
        )
        self._break_glass[break_id] = record

        # Auto-create BREAK_GLASS elevation
        elev_id = stable_identifier("elev-bg", {"break_id": break_id})
        if elev_id not in self._elevations:
            identity = self.get_identity(identity_ref)
            elevation = PrivilegeElevation(
                elevation_id=elev_id, tenant_id=tenant_id,
                identity_ref=identity_ref, from_level=identity.privilege_level,
                to_level=PrivilegeLevel.BREAK_GLASS, reason=reason,
                approved_by=authorized_by, created_at=now,
            )
            self._elevations[elev_id] = elevation
            # Update identity to BREAK_GLASS
            updated_identity = IdentityDescriptor(
                identity_id=identity.identity_id, tenant_id=identity.tenant_id,
                display_name=identity.display_name, identity_type=identity.identity_type,
                credential_status=identity.credential_status,
                privilege_level=PrivilegeLevel.BREAK_GLASS, created_at=identity.created_at,
                metadata=dict(identity.metadata),
            )
            self._identities[identity_ref] = updated_identity

        # Auto-create violation
        vid = stable_identifier("viol-idsec", {"break_id": break_id, "reason": "break_glass"})
        if vid not in self._violations:
            self._violations[vid] = {
                "violation_id": vid, "tenant_id": tenant_id,
                "identity_ref": identity_ref, "operation": "break_glass",
                "reason": "break-glass access active",
            }

        _emit(self._events, "record_break_glass", {"break_id": break_id}, break_id)
        return record

    # -- Snapshot --

    def security_snapshot(self, snapshot_id: str, tenant_id: str) -> SecuritySnapshot:
        now = _now_iso()
        snap = SecuritySnapshot(
            snapshot_id=snapshot_id, tenant_id=tenant_id,
            total_identities=len([i for i in self._identities.values() if i.tenant_id == tenant_id]),
            total_credentials=len([c for c in self._credentials.values() if c.tenant_id == tenant_id]),
            total_sessions=len([s for s in self._sessions.values() if s.tenant_id == tenant_id]),
            total_elevations=len([e for e in self._elevations.values() if e.tenant_id == tenant_id]),
            total_vault_accesses=len([v for v in self._vault_accesses.values() if v.tenant_id == tenant_id]),
            total_violations=len([v for v in self._violations.values() if v.get("tenant_id") == tenant_id]),
            captured_at=now,
        )
        _emit(self._events, "security_snapshot", {"snapshot_id": snapshot_id}, snapshot_id)
        return snap

    # -- Violation Detection --

    def detect_security_violations(self, tenant_id: str) -> tuple[dict[str, Any], ...]:
        new_violations: list[dict[str, Any]] = []

        # 1. Expired credential still ACTIVE on identity
        for cred in self._credentials.values():
            if cred.tenant_id != tenant_id:
                continue
            if cred.status == CredentialStatus.EXPIRED:
                # Check if the identity still has ACTIVE credential_status
                if cred.identity_ref in self._identities:
                    identity = self._identities[cred.identity_ref]
                    if identity.credential_status == CredentialStatus.ACTIVE:
                        vid = stable_identifier("viol-idsec", {
                            "credential_id": cred.credential_id, "reason": "expired_credential_active",
                        })
                        if vid not in self._violations:
                            v = {
                                "violation_id": vid, "tenant_id": tenant_id,
                                "credential_id": cred.credential_id,
                                "identity_ref": cred.identity_ref,
                                "operation": "expired_credential_active",
                                "reason": "expired credential remains active on identity",
                            }
                            self._violations[vid] = v
                            new_violations.append(v)

        # 2. Session without valid identity
        for session in self._sessions.values():
            if session.tenant_id != tenant_id:
                continue
            if session.status == SessionSecurityStatus.ACTIVE:
                if session.identity_ref not in self._identities:
                    vid = stable_identifier("viol-idsec", {
                        "session_id": session.session_id, "reason": "session_without_identity",
                    })
                    if vid not in self._violations:
                        v = {
                            "violation_id": vid, "tenant_id": tenant_id,
                            "session_id": session.session_id,
                            "operation": "session_without_identity",
                            "reason": "active session has no valid identity",
                        }
                        self._violations[vid] = v
                        new_violations.append(v)

        # 3. Elevation with no approval (approved_by == "pending")
        for elev in self._elevations.values():
            if elev.tenant_id != tenant_id:
                continue
            if elev.approved_by == "pending":
                vid = stable_identifier("viol-idsec", {
                    "elevation_id": elev.elevation_id, "reason": "elevation_no_approval",
                })
                if vid not in self._violations:
                    v = {
                        "violation_id": vid, "tenant_id": tenant_id,
                        "elevation_id": elev.elevation_id,
                        "operation": "elevation_no_approval",
                        "reason": "elevation has no approval",
                    }
                    self._violations[vid] = v
                    new_violations.append(v)

        # 4. Break-glass unresolved (identity still at BREAK_GLASS level)
        for bg in self._break_glass.values():
            if bg.tenant_id != tenant_id:
                continue
            if bg.identity_ref in self._identities:
                identity = self._identities[bg.identity_ref]
                if identity.privilege_level == PrivilegeLevel.BREAK_GLASS:
                    vid = stable_identifier("viol-idsec", {
                        "break_id": bg.break_id, "reason": "break_glass_unresolved",
                    })
                    if vid not in self._violations:
                        v = {
                            "violation_id": vid, "tenant_id": tenant_id,
                            "break_id": bg.break_id,
                            "identity_ref": bg.identity_ref,
                            "operation": "break_glass_unresolved",
                            "reason": "break-glass access remains active",
                        }
                        self._violations[vid] = v
                        new_violations.append(v)

        if new_violations:
            _emit(self._events, "detect_security_violations", {
                "tenant_id": tenant_id, "count": len(new_violations),
            }, tenant_id)
        return tuple(new_violations)

    # -- Assessment --

    def security_assessment(self, assessment_id: str, tenant_id: str) -> SecurityAssessment:
        now = _now_iso()
        t_identities = len([i for i in self._identities.values() if i.tenant_id == tenant_id])
        t_credentials = len([c for c in self._credentials.values() if c.tenant_id == tenant_id])
        t_sessions = len([s for s in self._sessions.values() if s.tenant_id == tenant_id])
        t_violations = len([v for v in self._violations.values() if v.get("tenant_id") == tenant_id])
        active_creds = len([c for c in self._credentials.values() if c.tenant_id == tenant_id and c.status == CredentialStatus.ACTIVE])
        rate = active_creds / t_credentials if t_credentials else 0.0
        assessment = SecurityAssessment(
            assessment_id=assessment_id, tenant_id=tenant_id,
            total_identities=t_identities, total_credentials=t_credentials,
            total_sessions=t_sessions, total_violations=t_violations,
            posture_score=round(rate, 4),
            assessed_at=now,
        )
        _emit(self._events, "security_assessment", {"assessment_id": assessment_id}, assessment_id)
        return assessment

    # -- Closure report --

    def security_closure_report(self, report_id: str, tenant_id: str) -> SecurityClosureReport:
        now = _now_iso()
        report = SecurityClosureReport(
            report_id=report_id, tenant_id=tenant_id,
            total_identities=len([i for i in self._identities.values() if i.tenant_id == tenant_id]),
            total_credentials=len([c for c in self._credentials.values() if c.tenant_id == tenant_id]),
            total_sessions=len([s for s in self._sessions.values() if s.tenant_id == tenant_id]),
            total_violations=len([v for v in self._violations.values() if v.get("tenant_id") == tenant_id]),
            created_at=now,
        )
        _emit(self._events, "security_closure_report", {"report_id": report_id}, report_id)
        return report

    # -- State hash --

    def state_hash(self) -> str:
        parts: list[str] = []
        for k in sorted(self._identities):
            parts.append(f"identity:{k}:{self._identities[k].privilege_level.value}")
        for k in sorted(self._credentials):
            parts.append(f"credential:{k}:{self._credentials[k].status.value}")
        for k in sorted(self._chains):
            parts.append(f"chain:{k}")
        for k in sorted(self._elevations):
            parts.append(f"elevation:{k}:{self._elevations[k].to_level.value}")
        for k in sorted(self._sessions):
            parts.append(f"session:{k}:{self._sessions[k].status.value}")
        for k in sorted(self._vault_accesses):
            parts.append(f"vault:{k}:{self._vault_accesses[k].operation.value}")
        for k in sorted(self._recertifications):
            parts.append(f"recert:{k}:{self._recertifications[k].status.value}")
        for k in sorted(self._break_glass):
            parts.append(f"breakglass:{k}")
        for k in sorted(self._violations):
            parts.append(f"violation:{k}")
        return sha256("|".join(parts).encode()).hexdigest()
