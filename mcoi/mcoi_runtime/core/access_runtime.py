"""Purpose: identity / access / authorization runtime engine.
Governance scope: registering identities and roles; binding roles to scopes;
    evaluating permissions deterministically (fail-closed); managing delegations;
    recording audits; detecting violations; producing access snapshots.
Dependencies: access_runtime contracts, event_spine, core invariants.
Invariants:
  - Evaluation is fail-closed: default is DENY.
  - DENY rules take precedence over ALLOW.
  - Disabled identities are always denied.
  - Expired delegations are not considered.
  - Every mutation emits an event.
  - All returns are immutable.
"""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from typing import Any

from ..contracts.access_runtime import (
    AccessAuditRecord,
    AccessDecision,
    AccessEvaluation,
    AccessRequest,
    AccessSnapshot,
    AccessViolation,
    AuthContextKind,
    DelegationRecord,
    DelegationStatus,
    IdentityKind,
    IdentityRecord,
    PermissionEffect,
    PermissionRule,
    RoleBinding,
    RoleKind,
    RoleRecord,
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
        event_id=stable_identifier("evt-access", {"action": action, "ts": now, "cid": cid}),
        event_type=EventType.CUSTOM,
        source=EventSource.COMMUNICATION_SYSTEM,
        correlation_id=cid,
        payload=payload,
        emitted_at=now,
    )
    es.emit(event)
    return event


class AccessRuntimeEngine:
    """Identity, access, and authorization engine."""

    def __init__(self, event_spine: EventSpineEngine) -> None:
        if not isinstance(event_spine, EventSpineEngine):
            raise RuntimeCoreInvariantError("event_spine must be an EventSpineEngine")
        self._events = event_spine
        self._identities: dict[str, IdentityRecord] = {}
        self._roles: dict[str, RoleRecord] = {}
        self._rules: dict[str, PermissionRule] = {}
        self._bindings: dict[str, RoleBinding] = {}
        self._delegations: dict[str, DelegationRecord] = {}
        self._evaluations: dict[str, AccessEvaluation] = {}
        self._violations: dict[str, AccessViolation] = {}
        self._audits: dict[str, AccessAuditRecord] = {}
        self._snapshot_ids: set[str] = set()

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def identity_count(self) -> int:
        return len(self._identities)

    @property
    def role_count(self) -> int:
        return len(self._roles)

    @property
    def rule_count(self) -> int:
        return len(self._rules)

    @property
    def binding_count(self) -> int:
        return len(self._bindings)

    @property
    def delegation_count(self) -> int:
        return len(self._delegations)

    @property
    def evaluation_count(self) -> int:
        return len(self._evaluations)

    @property
    def violation_count(self) -> int:
        return len(self._violations)

    @property
    def audit_count(self) -> int:
        return len(self._audits)

    # ------------------------------------------------------------------
    # Identity management
    # ------------------------------------------------------------------

    def register_identity(
        self,
        identity_id: str,
        name: str,
        *,
        kind: IdentityKind = IdentityKind.HUMAN,
        tenant_id: str,
        enabled: bool = True,
    ) -> IdentityRecord:
        """Register a new identity."""
        if identity_id in self._identities:
            raise RuntimeCoreInvariantError(f"Duplicate identity_id: {identity_id}")
        now = _now_iso()
        identity = IdentityRecord(
            identity_id=identity_id,
            name=name,
            kind=kind,
            tenant_id=tenant_id,
            enabled=enabled,
            created_at=now,
        )
        self._identities[identity_id] = identity
        _emit(self._events, "identity_registered", {"identity_id": identity_id}, identity_id)
        return identity

    def disable_identity(self, identity_id: str) -> IdentityRecord:
        """Disable an identity."""
        old = self._identities.get(identity_id)
        if old is None:
            raise RuntimeCoreInvariantError(f"Unknown identity_id: {identity_id}")
        updated = IdentityRecord(
            identity_id=old.identity_id,
            name=old.name,
            kind=old.kind,
            tenant_id=old.tenant_id,
            enabled=False,
            created_at=old.created_at,
            metadata=old.metadata,
        )
        self._identities[identity_id] = updated
        _emit(self._events, "identity_disabled", {"identity_id": identity_id}, identity_id)
        return updated

    def enable_identity(self, identity_id: str) -> IdentityRecord:
        """Enable an identity."""
        old = self._identities.get(identity_id)
        if old is None:
            raise RuntimeCoreInvariantError(f"Unknown identity_id: {identity_id}")
        updated = IdentityRecord(
            identity_id=old.identity_id,
            name=old.name,
            kind=old.kind,
            tenant_id=old.tenant_id,
            enabled=True,
            created_at=old.created_at,
            metadata=old.metadata,
        )
        self._identities[identity_id] = updated
        _emit(self._events, "identity_enabled", {"identity_id": identity_id}, identity_id)
        return updated

    def get_identity(self, identity_id: str) -> IdentityRecord:
        """Get an identity by ID."""
        i = self._identities.get(identity_id)
        if i is None:
            raise RuntimeCoreInvariantError(f"Unknown identity_id: {identity_id}")
        return i

    def identities_for_tenant(self, tenant_id: str) -> tuple[IdentityRecord, ...]:
        """Return all identities for a tenant."""
        return tuple(i for i in self._identities.values() if i.tenant_id == tenant_id)

    # ------------------------------------------------------------------
    # Role management
    # ------------------------------------------------------------------

    def register_role(
        self,
        role_id: str,
        name: str,
        *,
        kind: RoleKind = RoleKind.VIEWER,
        permissions: list[str] | None = None,
        description: str = "",
    ) -> RoleRecord:
        """Register a new role."""
        if role_id in self._roles:
            raise RuntimeCoreInvariantError(f"Duplicate role_id: {role_id}")
        now = _now_iso()
        role = RoleRecord(
            role_id=role_id,
            name=name,
            kind=kind,
            permissions=tuple(permissions or []),
            description=description,
            created_at=now,
        )
        self._roles[role_id] = role
        _emit(self._events, "role_registered", {"role_id": role_id}, role_id)
        return role

    # ------------------------------------------------------------------
    # Permission rules
    # ------------------------------------------------------------------

    def add_permission_rule(
        self,
        rule_id: str,
        resource_type: str,
        action: str,
        effect: PermissionEffect,
        *,
        scope_kind: AuthContextKind = AuthContextKind.TENANT,
        scope_ref_id: str = "*",
        conditions: dict[str, Any] | None = None,
    ) -> PermissionRule:
        """Add a permission rule."""
        if rule_id in self._rules:
            raise RuntimeCoreInvariantError(f"Duplicate rule_id: {rule_id}")
        now = _now_iso()
        rule = PermissionRule(
            rule_id=rule_id,
            resource_type=resource_type,
            action=action,
            effect=effect,
            scope_kind=scope_kind,
            scope_ref_id=scope_ref_id,
            conditions=conditions or {},
            created_at=now,
        )
        self._rules[rule_id] = rule
        _emit(self._events, "permission_rule_added", {"rule_id": rule_id}, rule_id)
        return rule

    # ------------------------------------------------------------------
    # Role binding
    # ------------------------------------------------------------------

    def bind_role(
        self,
        binding_id: str,
        identity_id: str,
        role_id: str,
        *,
        scope_kind: AuthContextKind = AuthContextKind.TENANT,
        scope_ref_id: str = "*",
    ) -> RoleBinding:
        """Bind a role to an identity within a scope."""
        if binding_id in self._bindings:
            raise RuntimeCoreInvariantError(f"Duplicate binding_id: {binding_id}")
        if identity_id not in self._identities:
            raise RuntimeCoreInvariantError(f"Unknown identity_id: {identity_id}")
        if role_id not in self._roles:
            raise RuntimeCoreInvariantError(f"Unknown role_id: {role_id}")
        now = _now_iso()
        binding = RoleBinding(
            binding_id=binding_id,
            identity_id=identity_id,
            role_id=role_id,
            scope_kind=scope_kind,
            scope_ref_id=scope_ref_id,
            bound_at=now,
        )
        self._bindings[binding_id] = binding
        _emit(self._events, "role_bound", {
            "binding_id": binding_id, "identity_id": identity_id, "role_id": role_id,
        }, binding_id)
        return binding

    def bindings_for_identity(
        self, identity_id: str, scope_kind: AuthContextKind | None = None,
    ) -> tuple[RoleBinding, ...]:
        """Return all role bindings for an identity."""
        bindings = (b for b in self._bindings.values() if b.identity_id == identity_id)
        if scope_kind is not None:
            bindings = (b for b in bindings if b.scope_kind == scope_kind)
        return tuple(bindings)

    # ------------------------------------------------------------------
    # Delegation
    # ------------------------------------------------------------------

    def delegate_permission(
        self,
        delegation_id: str,
        from_identity_id: str,
        to_identity_id: str,
        role_id: str,
        *,
        scope_kind: AuthContextKind = AuthContextKind.WORKSPACE,
        scope_ref_id: str = "*",
        expires_at: str = "",
    ) -> DelegationRecord:
        """Delegate a role to another identity."""
        if delegation_id in self._delegations:
            raise RuntimeCoreInvariantError(f"Duplicate delegation_id: {delegation_id}")
        if from_identity_id not in self._identities:
            raise RuntimeCoreInvariantError(f"Unknown from_identity_id: {from_identity_id}")
        if to_identity_id not in self._identities:
            raise RuntimeCoreInvariantError(f"Unknown to_identity_id: {to_identity_id}")
        if role_id not in self._roles:
            raise RuntimeCoreInvariantError(f"Unknown role_id: {role_id}")
        now = _now_iso()
        delegation = DelegationRecord(
            delegation_id=delegation_id,
            from_identity_id=from_identity_id,
            to_identity_id=to_identity_id,
            role_id=role_id,
            scope_kind=scope_kind,
            scope_ref_id=scope_ref_id,
            status=DelegationStatus.ACTIVE,
            expires_at=expires_at,
            delegated_at=now,
        )
        self._delegations[delegation_id] = delegation
        _emit(self._events, "permission_delegated", {
            "delegation_id": delegation_id,
            "from": from_identity_id, "to": to_identity_id,
        }, delegation_id)
        return delegation

    def revoke_delegation(self, delegation_id: str) -> DelegationRecord:
        """Revoke a delegation."""
        old = self._delegations.get(delegation_id)
        if old is None:
            raise RuntimeCoreInvariantError(f"Unknown delegation_id: {delegation_id}")
        if old.status != DelegationStatus.ACTIVE:
            raise RuntimeCoreInvariantError(
                f"Cannot revoke delegation in status {old.status.value}"
            )
        now = _now_iso()
        updated = DelegationRecord(
            delegation_id=old.delegation_id,
            from_identity_id=old.from_identity_id,
            to_identity_id=old.to_identity_id,
            role_id=old.role_id,
            scope_kind=old.scope_kind,
            scope_ref_id=old.scope_ref_id,
            status=DelegationStatus.REVOKED,
            expires_at=old.expires_at,
            delegated_at=old.delegated_at,
            revoked_at=now,
            metadata=old.metadata,
        )
        self._delegations[delegation_id] = updated
        _emit(self._events, "delegation_revoked", {"delegation_id": delegation_id}, delegation_id)
        return updated

    def expire_delegation(self, delegation_id: str) -> DelegationRecord:
        """Mark a delegation as expired."""
        old = self._delegations.get(delegation_id)
        if old is None:
            raise RuntimeCoreInvariantError(f"Unknown delegation_id: {delegation_id}")
        if old.status != DelegationStatus.ACTIVE:
            raise RuntimeCoreInvariantError(
                f"Cannot expire delegation in status {old.status.value}"
            )
        now = _now_iso()
        updated = DelegationRecord(
            delegation_id=old.delegation_id,
            from_identity_id=old.from_identity_id,
            to_identity_id=old.to_identity_id,
            role_id=old.role_id,
            scope_kind=old.scope_kind,
            scope_ref_id=old.scope_ref_id,
            status=DelegationStatus.EXPIRED,
            expires_at=old.expires_at,
            delegated_at=old.delegated_at,
            revoked_at=now,
            metadata=old.metadata,
        )
        self._delegations[delegation_id] = updated
        _emit(self._events, "delegation_expired", {"delegation_id": delegation_id}, delegation_id)
        return updated

    def active_delegations_for_identity(
        self, identity_id: str,
    ) -> tuple[DelegationRecord, ...]:
        """Return all active delegations to an identity."""
        return tuple(
            d for d in self._delegations.values()
            if d.to_identity_id == identity_id and d.status == DelegationStatus.ACTIVE
        )

    # ------------------------------------------------------------------
    # Permission evaluation
    # ------------------------------------------------------------------

    def _effective_role_ids(
        self, identity_id: str, scope_kind: AuthContextKind, scope_ref_id: str,
    ) -> set[str]:
        """Collect all role IDs for an identity including delegations."""
        role_ids: set[str] = set()

        # Direct bindings
        for b in self._bindings.values():
            if b.identity_id != identity_id:
                continue
            # GLOBAL bindings always apply
            if b.scope_kind == AuthContextKind.GLOBAL:
                role_ids.add(b.role_id)
            # Matching scope
            elif b.scope_kind == scope_kind and (
                b.scope_ref_id == "*" or b.scope_ref_id == scope_ref_id
            ):
                role_ids.add(b.role_id)
            # Broader scope: TENANT binding applies to WORKSPACE/ENVIRONMENT
            elif (b.scope_kind == AuthContextKind.TENANT
                  and scope_kind in (AuthContextKind.WORKSPACE, AuthContextKind.ENVIRONMENT)):
                role_ids.add(b.role_id)
            # WORKSPACE binding applies to ENVIRONMENT
            elif (b.scope_kind == AuthContextKind.WORKSPACE
                  and scope_kind == AuthContextKind.ENVIRONMENT):
                role_ids.add(b.role_id)

        # Active delegations
        for d in self._delegations.values():
            if d.to_identity_id != identity_id:
                continue
            if d.status != DelegationStatus.ACTIVE:
                continue
            if d.scope_kind == AuthContextKind.GLOBAL:
                role_ids.add(d.role_id)
            elif d.scope_kind == scope_kind and (
                d.scope_ref_id == "*" or d.scope_ref_id == scope_ref_id
            ):
                role_ids.add(d.role_id)
            elif (d.scope_kind == AuthContextKind.TENANT
                  and scope_kind in (AuthContextKind.WORKSPACE, AuthContextKind.ENVIRONMENT)):
                role_ids.add(d.role_id)
            elif (d.scope_kind == AuthContextKind.WORKSPACE
                  and scope_kind == AuthContextKind.ENVIRONMENT):
                role_ids.add(d.role_id)

        return role_ids

    def list_effective_permissions(
        self, identity_id: str, scope_kind: AuthContextKind, scope_ref_id: str = "*",
    ) -> tuple[str, ...]:
        """List all effective permissions for an identity in a scope."""
        if identity_id not in self._identities:
            raise RuntimeCoreInvariantError(f"Unknown identity_id: {identity_id}")
        identity = self._identities[identity_id]
        if not identity.enabled:
            return ()

        role_ids = self._effective_role_ids(identity_id, scope_kind, scope_ref_id)
        permissions: set[str] = set()
        for rid in role_ids:
            role = self._roles.get(rid)
            if role:
                permissions.update(role.permissions)
        return tuple(sorted(permissions))

    def evaluate_access(
        self,
        request_id: str,
        identity_id: str,
        resource_type: str,
        action: str,
        *,
        scope_kind: AuthContextKind = AuthContextKind.TENANT,
        scope_ref_id: str = "*",
    ) -> AccessEvaluation:
        """Evaluate an access request. Fail-closed: default is DENY."""
        now = _now_iso()

        # Create request record
        request = AccessRequest(
            request_id=request_id,
            identity_id=identity_id,
            resource_type=resource_type,
            action=action,
            scope_kind=scope_kind,
            scope_ref_id=scope_ref_id,
            requested_at=now,
        )

        identity = self._identities.get(identity_id)
        if identity is None:
            eval_record = self._make_evaluation(
                request_id, AccessDecision.DENIED, (), (), "unknown identity", now,
            )
            self._record_audit(identity_id, action, resource_type, AccessDecision.DENIED,
                               scope_kind, scope_ref_id, now)
            return eval_record

        if not identity.enabled:
            eval_record = self._make_evaluation(
                request_id, AccessDecision.DENIED, (), (), "identity disabled", now,
            )
            self._record_audit(identity_id, action, resource_type, AccessDecision.DENIED,
                               scope_kind, scope_ref_id, now)
            return eval_record

        # Collect effective roles
        role_ids = self._effective_role_ids(identity_id, scope_kind, scope_ref_id)

        # Collect all permissions from roles
        all_permissions: set[str] = set()
        for rid in role_ids:
            role = self._roles.get(rid)
            if role:
                all_permissions.update(role.permissions)

        # Find matching rules
        matching_rules: list[PermissionRule] = []
        for rule in self._rules.values():
            if rule.resource_type != resource_type and rule.resource_type != "*":
                continue
            if rule.action != action and rule.action != "*":
                continue
            # Check scope match
            if rule.scope_kind == AuthContextKind.GLOBAL:
                matching_rules.append(rule)
            elif rule.scope_kind == scope_kind and (
                rule.scope_ref_id == "*" or rule.scope_ref_id == scope_ref_id
            ):
                matching_rules.append(rule)
            elif (rule.scope_kind == AuthContextKind.TENANT
                  and scope_kind in (AuthContextKind.WORKSPACE, AuthContextKind.ENVIRONMENT)):
                matching_rules.append(rule)
            elif (rule.scope_kind == AuthContextKind.WORKSPACE
                  and scope_kind == AuthContextKind.ENVIRONMENT):
                matching_rules.append(rule)

        # Check if identity has required role/permission for matching rules
        # Also check for explicit DENY rules
        matching_rule_ids: list[str] = []
        matching_role_ids: list[str] = list(role_ids)

        # Evaluate: DENY takes precedence, then REQUIRE_APPROVAL, then ALLOW
        has_deny = False
        has_require_approval = False
        has_allow = False

        for rule in matching_rules:
            # Check if any role grants the permission implied by this rule
            permission_key = f"{resource_type}:{action}"
            role_has_permission = (
                permission_key in all_permissions
                or f"{resource_type}:*" in all_permissions
                or "*:*" in all_permissions
            )

            if rule.effect == PermissionEffect.DENY:
                has_deny = True
                matching_rule_ids.append(rule.rule_id)
            elif rule.effect == PermissionEffect.REQUIRE_APPROVAL:
                if role_has_permission:
                    has_require_approval = True
                    matching_rule_ids.append(rule.rule_id)
            elif rule.effect == PermissionEffect.ALLOW:
                if role_has_permission:
                    has_allow = True
                    matching_rule_ids.append(rule.rule_id)

        # If no explicit rules but has permission via role, allow
        if not matching_rules and (
            f"{resource_type}:{action}" in all_permissions
            or f"{resource_type}:*" in all_permissions
            or "*:*" in all_permissions
        ):
            has_allow = True

        # Determine decision (DENY > REQUIRE_APPROVAL > ALLOW > DENY)
        if has_deny:
            decision = AccessDecision.DENIED
            reason = "explicit deny rule"
        elif has_require_approval:
            decision = AccessDecision.REQUIRES_APPROVAL
            reason = "requires approval"
        elif has_allow:
            decision = AccessDecision.ALLOWED
            reason = "allowed by role/rule"
        else:
            decision = AccessDecision.DENIED
            reason = "no matching permission"

        eval_record = self._make_evaluation(
            request_id, decision,
            tuple(matching_rule_ids), tuple(matching_role_ids),
            reason, now,
        )
        self._record_audit(identity_id, action, resource_type, decision,
                           scope_kind, scope_ref_id, now)

        _emit(self._events, "access_evaluated", {
            "request_id": request_id, "identity_id": identity_id,
            "decision": decision.value,
        }, request_id)
        return eval_record

    def _make_evaluation(
        self,
        request_id: str,
        decision: AccessDecision,
        matching_rule_ids: tuple[str, ...],
        matching_role_ids: tuple[str, ...],
        reason: str,
        now: str,
    ) -> AccessEvaluation:
        eval_id = stable_identifier("eval", {"req": request_id, "ts": now})
        evaluation = AccessEvaluation(
            evaluation_id=eval_id,
            request_id=request_id,
            decision=decision,
            matching_rule_ids=matching_rule_ids,
            matching_role_ids=matching_role_ids,
            reason=reason,
            evaluated_at=now,
        )
        self._evaluations[eval_id] = evaluation
        return evaluation

    def _record_audit(
        self,
        identity_id: str,
        action: str,
        resource_type: str,
        decision: AccessDecision,
        scope_kind: AuthContextKind,
        scope_ref_id: str,
        now: str,
    ) -> AccessAuditRecord:
        audit_id = stable_identifier("audit", {
            "identity": identity_id, "action": action, "ts": now,
        })
        audit = AccessAuditRecord(
            audit_id=audit_id,
            identity_id=identity_id,
            action=action,
            resource_type=resource_type,
            decision=decision,
            scope_kind=scope_kind,
            scope_ref_id=scope_ref_id,
            recorded_at=now,
        )
        self._audits[audit_id] = audit
        return audit

    # ------------------------------------------------------------------
    # Violation detection
    # ------------------------------------------------------------------

    def detect_violations(self) -> tuple[AccessViolation, ...]:
        """Detect access violations from audit trail."""
        now = _now_iso()
        new_violations: list[AccessViolation] = []

        for audit in self._audits.values():
            if audit.decision != AccessDecision.DENIED:
                continue
            vid = stable_identifier("viol-access", {
                "audit": audit.audit_id,
            })
            if vid in self._violations:
                continue
            # Check if identity is cross-tenant
            identity = self._identities.get(audit.identity_id)
            reason = "denied access attempt"
            if identity and identity.tenant_id and audit.scope_ref_id:
                if identity.tenant_id != audit.scope_ref_id:
                    reason = f"cross-tenant access attempt from {identity.tenant_id}"

            violation = AccessViolation(
                violation_id=vid,
                identity_id=audit.identity_id,
                resource_type=audit.resource_type,
                action=audit.action,
                scope_kind=audit.scope_kind,
                scope_ref_id=audit.scope_ref_id,
                reason=reason,
                detected_at=now,
            )
            self._violations[vid] = violation
            new_violations.append(violation)

        if new_violations:
            _emit(self._events, "access_violations_detected", {
                "count": len(new_violations),
            }, "violation-scan")
        return tuple(new_violations)

    def violations_for_identity(self, identity_id: str) -> tuple[AccessViolation, ...]:
        """Return all violations for an identity."""
        return tuple(v for v in self._violations.values() if v.identity_id == identity_id)

    # ------------------------------------------------------------------
    # Access snapshot
    # ------------------------------------------------------------------

    def access_snapshot(
        self,
        snapshot_id: str,
        scope_ref_id: str = "*",
    ) -> AccessSnapshot:
        """Capture a point-in-time access snapshot."""
        if snapshot_id in self._snapshot_ids:
            raise RuntimeCoreInvariantError(f"Duplicate snapshot_id: {snapshot_id}")

        active_delegations = sum(
            1 for d in self._delegations.values()
            if d.status == DelegationStatus.ACTIVE
        )
        now = _now_iso()
        snapshot = AccessSnapshot(
            snapshot_id=snapshot_id,
            scope_ref_id=scope_ref_id,
            total_identities=self.identity_count,
            total_roles=self.role_count,
            total_bindings=self.binding_count,
            total_rules=self.rule_count,
            active_delegations=active_delegations,
            total_violations=self.violation_count,
            total_evaluations=self.evaluation_count,
            captured_at=now,
        )
        self._snapshot_ids.add(snapshot_id)
        _emit(self._events, "access_snapshot_captured", {
            "snapshot_id": snapshot_id,
        }, snapshot_id)
        return snapshot

    # ------------------------------------------------------------------
    # Audit trail queries
    # ------------------------------------------------------------------

    def audits_for_identity(self, identity_id: str) -> tuple[AccessAuditRecord, ...]:
        """Return all audit records for an identity."""
        return tuple(a for a in self._audits.values() if a.identity_id == identity_id)

    # ------------------------------------------------------------------
    # State hash
    # ------------------------------------------------------------------

    def state_hash(self) -> str:
        """Compute a hash of the current engine state."""
        parts = [
            f"identities={self.identity_count}",
            f"roles={self.role_count}",
            f"rules={self.rule_count}",
            f"bindings={self.binding_count}",
            f"delegations={self.delegation_count}",
            f"evaluations={self.evaluation_count}",
            f"violations={self.violation_count}",
            f"audits={self.audit_count}",
        ]
        return sha256("|".join(parts).encode()).hexdigest()
