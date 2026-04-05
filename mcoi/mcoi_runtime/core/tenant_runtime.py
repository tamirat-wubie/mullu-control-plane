"""Purpose: tenant / workspace / environment isolation runtime engine.
Governance scope: registering tenants, workspaces, environments; enforcing
    boundary policies; binding resources to workspaces; promoting environments;
    detecting isolation violations; producing tenant health and closure reports.
Dependencies: tenant_runtime contracts, event_spine, core invariants.
Invariants:
  - Tenants gate all workspaces and environments.
  - Boundary policies enforce isolation.
  - Promotions are gated by compliance checks.
  - Every mutation emits an event.
  - All returns are immutable.
"""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from typing import Any

from ..contracts.tenant_runtime import (
    BoundaryPolicy,
    EnvironmentKind,
    EnvironmentPromotion,
    EnvironmentRecord,
    IsolationLevel,
    IsolationViolation,
    PromotionStatus,
    ScopeBoundaryKind,
    TenantClosureReport,
    TenantDecision,
    TenantHealth,
    TenantRecord,
    TenantStatus,
    WorkspaceBinding,
    WorkspaceRecord,
    WorkspaceStatus,
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
        event_id=stable_identifier("evt-tenant", {"action": action, "ts": now, "cid": cid}),
        event_type=EventType.CUSTOM,
        source=EventSource.COMMUNICATION_SYSTEM,
        correlation_id=cid,
        payload=payload,
        emitted_at=now,
    )
    es.emit(event)
    return event


class TenantRuntimeEngine:
    """Multi-tenant, workspace, and environment isolation engine."""

    def __init__(self, event_spine: EventSpineEngine) -> None:
        if not isinstance(event_spine, EventSpineEngine):
            raise RuntimeCoreInvariantError("event_spine must be an EventSpineEngine")
        self._events = event_spine
        self._tenants: dict[str, TenantRecord] = {}
        self._workspaces: dict[str, WorkspaceRecord] = {}
        self._environments: dict[str, EnvironmentRecord] = {}
        self._policies: dict[str, BoundaryPolicy] = {}
        self._bindings: dict[str, WorkspaceBinding] = {}
        self._promotions: dict[str, EnvironmentPromotion] = {}
        self._violations: dict[str, IsolationViolation] = {}
        self._decisions: dict[str, TenantDecision] = {}

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def tenant_count(self) -> int:
        return len(self._tenants)

    @property
    def workspace_count(self) -> int:
        return len(self._workspaces)

    @property
    def environment_count(self) -> int:
        return len(self._environments)

    @property
    def policy_count(self) -> int:
        return len(self._policies)

    @property
    def binding_count(self) -> int:
        return len(self._bindings)

    @property
    def promotion_count(self) -> int:
        return len(self._promotions)

    @property
    def violation_count(self) -> int:
        return len(self._violations)

    @property
    def decision_count(self) -> int:
        return len(self._decisions)

    # ------------------------------------------------------------------
    # Tenant management
    # ------------------------------------------------------------------

    def register_tenant(
        self,
        tenant_id: str,
        name: str,
        *,
        isolation_level: IsolationLevel = IsolationLevel.STANDARD,
        owner: str = "",
    ) -> TenantRecord:
        """Register a new tenant."""
        if tenant_id in self._tenants:
            raise RuntimeCoreInvariantError("Duplicate tenant_id")
        now = _now_iso()
        tenant = TenantRecord(
            tenant_id=tenant_id,
            name=name,
            status=TenantStatus.ACTIVE,
            isolation_level=isolation_level,
            owner=owner,
            created_at=now,
        )
        self._tenants[tenant_id] = tenant
        _emit(self._events, "tenant_registered", {"tenant_id": tenant_id}, tenant_id)
        return tenant

    def set_tenant_status(
        self, tenant_id: str, status: TenantStatus,
    ) -> TenantRecord:
        """Update a tenant's status."""
        old = self._tenants.get(tenant_id)
        if old is None:
            raise RuntimeCoreInvariantError("Unknown tenant_id")
        now = _now_iso()
        updated = TenantRecord(
            tenant_id=old.tenant_id,
            name=old.name,
            status=status,
            isolation_level=old.isolation_level,
            owner=old.owner,
            workspace_ids=old.workspace_ids,
            created_at=old.created_at,
            updated_at=now,
            metadata=old.metadata,
        )
        self._tenants[tenant_id] = updated
        _emit(self._events, "tenant_status_updated", {
            "tenant_id": tenant_id, "status": status.value,
        }, tenant_id)
        return updated

    def get_tenant(self, tenant_id: str) -> TenantRecord:
        """Get a tenant by ID."""
        t = self._tenants.get(tenant_id)
        if t is None:
            raise RuntimeCoreInvariantError("Unknown tenant_id")
        return t

    # ------------------------------------------------------------------
    # Workspace management
    # ------------------------------------------------------------------

    def register_workspace(
        self,
        workspace_id: str,
        tenant_id: str,
        name: str,
        *,
        isolation_level: IsolationLevel = IsolationLevel.STANDARD,
    ) -> WorkspaceRecord:
        """Register a new workspace within a tenant."""
        if workspace_id in self._workspaces:
            raise RuntimeCoreInvariantError("Duplicate workspace_id")
        tenant = self._tenants.get(tenant_id)
        if tenant is None:
            raise RuntimeCoreInvariantError("Unknown tenant_id")
        now = _now_iso()
        workspace = WorkspaceRecord(
            workspace_id=workspace_id,
            tenant_id=tenant_id,
            name=name,
            status=WorkspaceStatus.ACTIVE,
            isolation_level=isolation_level,
            created_at=now,
        )
        self._workspaces[workspace_id] = workspace
        # Add workspace to tenant's workspace_ids
        updated_tenant = TenantRecord(
            tenant_id=tenant.tenant_id,
            name=tenant.name,
            status=tenant.status,
            isolation_level=tenant.isolation_level,
            owner=tenant.owner,
            workspace_ids=tenant.workspace_ids + (workspace_id,),
            created_at=tenant.created_at,
            updated_at=now,
            metadata=tenant.metadata,
        )
        self._tenants[tenant_id] = updated_tenant
        _emit(self._events, "workspace_registered", {
            "workspace_id": workspace_id, "tenant_id": tenant_id,
        }, workspace_id)
        return workspace

    def set_workspace_status(
        self, workspace_id: str, status: WorkspaceStatus,
    ) -> WorkspaceRecord:
        """Update a workspace's status."""
        old = self._workspaces.get(workspace_id)
        if old is None:
            raise RuntimeCoreInvariantError("Unknown workspace_id")
        now = _now_iso()
        updated = WorkspaceRecord(
            workspace_id=old.workspace_id,
            tenant_id=old.tenant_id,
            name=old.name,
            status=status,
            isolation_level=old.isolation_level,
            environment_ids=old.environment_ids,
            resource_bindings=old.resource_bindings,
            created_at=old.created_at,
            updated_at=now,
            metadata=old.metadata,
        )
        self._workspaces[workspace_id] = updated
        _emit(self._events, "workspace_status_updated", {
            "workspace_id": workspace_id, "status": status.value,
        }, workspace_id)
        return updated

    def get_workspace(self, workspace_id: str) -> WorkspaceRecord:
        """Get a workspace by ID."""
        w = self._workspaces.get(workspace_id)
        if w is None:
            raise RuntimeCoreInvariantError("Unknown workspace_id")
        return w

    def workspaces_for_tenant(self, tenant_id: str) -> tuple[WorkspaceRecord, ...]:
        """Return all workspaces for a tenant."""
        return tuple(w for w in self._workspaces.values() if w.tenant_id == tenant_id)

    # ------------------------------------------------------------------
    # Environment management
    # ------------------------------------------------------------------

    def register_environment(
        self,
        environment_id: str,
        workspace_id: str,
        kind: EnvironmentKind,
        *,
        name: str = "",
    ) -> EnvironmentRecord:
        """Register a new environment within a workspace."""
        if environment_id in self._environments:
            raise RuntimeCoreInvariantError("Duplicate environment_id")
        workspace = self._workspaces.get(workspace_id)
        if workspace is None:
            raise RuntimeCoreInvariantError("Unknown workspace_id")
        now = _now_iso()
        env = EnvironmentRecord(
            environment_id=environment_id,
            workspace_id=workspace_id,
            kind=kind,
            name=name or f"{kind.value}-{environment_id}",
            created_at=now,
        )
        self._environments[environment_id] = env
        # Add environment to workspace's environment_ids
        updated_ws = WorkspaceRecord(
            workspace_id=workspace.workspace_id,
            tenant_id=workspace.tenant_id,
            name=workspace.name,
            status=workspace.status,
            isolation_level=workspace.isolation_level,
            environment_ids=workspace.environment_ids + (environment_id,),
            resource_bindings=workspace.resource_bindings,
            created_at=workspace.created_at,
            updated_at=now,
            metadata=workspace.metadata,
        )
        self._workspaces[workspace_id] = updated_ws
        _emit(self._events, "environment_registered", {
            "environment_id": environment_id, "workspace_id": workspace_id,
            "kind": kind.value,
        }, environment_id)
        return env

    def get_environment(self, environment_id: str) -> EnvironmentRecord:
        """Get an environment by ID."""
        e = self._environments.get(environment_id)
        if e is None:
            raise RuntimeCoreInvariantError("Unknown environment_id")
        return e

    def environments_for_workspace(self, workspace_id: str) -> tuple[EnvironmentRecord, ...]:
        """Return all environments for a workspace."""
        return tuple(e for e in self._environments.values() if e.workspace_id == workspace_id)

    # ------------------------------------------------------------------
    # Boundary policies
    # ------------------------------------------------------------------

    def add_boundary_policy(
        self,
        policy_id: str,
        tenant_id: str,
        boundary_kind: ScopeBoundaryKind,
        *,
        isolation_level: IsolationLevel = IsolationLevel.STRICT,
        enforced: bool = True,
        description: str = "",
    ) -> BoundaryPolicy:
        """Add a boundary policy for a tenant."""
        if policy_id in self._policies:
            raise RuntimeCoreInvariantError("Duplicate policy_id")
        if tenant_id not in self._tenants:
            raise RuntimeCoreInvariantError("Unknown tenant_id")
        now = _now_iso()
        policy = BoundaryPolicy(
            policy_id=policy_id,
            tenant_id=tenant_id,
            boundary_kind=boundary_kind,
            isolation_level=isolation_level,
            enforced=enforced,
            description=description,
            created_at=now,
        )
        self._policies[policy_id] = policy
        _emit(self._events, "boundary_policy_added", {
            "policy_id": policy_id, "tenant_id": tenant_id,
            "boundary_kind": boundary_kind.value,
        }, policy_id)
        return policy

    def policies_for_tenant(self, tenant_id: str) -> tuple[BoundaryPolicy, ...]:
        """Return all boundary policies for a tenant."""
        return tuple(p for p in self._policies.values() if p.tenant_id == tenant_id)

    def enforced_policies_for_tenant(
        self, tenant_id: str, boundary_kind: ScopeBoundaryKind | None = None,
    ) -> tuple[BoundaryPolicy, ...]:
        """Return all enforced policies, optionally filtered by boundary kind."""
        policies = (p for p in self._policies.values()
                     if p.tenant_id == tenant_id and p.enforced)
        if boundary_kind is not None:
            policies = (p for p in policies if p.boundary_kind == boundary_kind)
        return tuple(policies)

    # ------------------------------------------------------------------
    # Workspace resource binding
    # ------------------------------------------------------------------

    def bind_workspace_resource(
        self,
        binding_id: str,
        workspace_id: str,
        resource_ref_id: str,
        resource_type: ScopeBoundaryKind,
        *,
        environment_id: str = "",
    ) -> WorkspaceBinding:
        """Bind a resource to a workspace, checking boundary policies."""
        if binding_id in self._bindings:
            raise RuntimeCoreInvariantError("Duplicate binding_id")
        workspace = self._workspaces.get(workspace_id)
        if workspace is None:
            raise RuntimeCoreInvariantError("Unknown workspace_id")
        if environment_id and environment_id not in self._environments:
            raise RuntimeCoreInvariantError("Unknown environment_id")

        # Check isolation: resource must not already be bound to a different
        # workspace under STRICT isolation
        tenant_id = workspace.tenant_id
        strict_policies = self.enforced_policies_for_tenant(tenant_id, resource_type)
        for policy in strict_policies:
            if policy.isolation_level == IsolationLevel.STRICT:
                # Check if this resource is already bound to another workspace
                for existing in self._bindings.values():
                    if (existing.resource_ref_id == resource_ref_id
                            and existing.resource_type == resource_type
                            and existing.workspace_id != workspace_id):
                        raise RuntimeCoreInvariantError(
                            f"Isolation violation: resource {resource_ref_id} "
                            f"already bound to workspace {existing.workspace_id} "
                            f"under STRICT {resource_type.value} policy"
                        )

        now = _now_iso()
        binding = WorkspaceBinding(
            binding_id=binding_id,
            workspace_id=workspace_id,
            resource_ref_id=resource_ref_id,
            resource_type=resource_type,
            environment_id=environment_id,
            bound_at=now,
        )
        self._bindings[binding_id] = binding
        # Add to workspace's resource_bindings
        updated_ws = WorkspaceRecord(
            workspace_id=workspace.workspace_id,
            tenant_id=workspace.tenant_id,
            name=workspace.name,
            status=workspace.status,
            isolation_level=workspace.isolation_level,
            environment_ids=workspace.environment_ids,
            resource_bindings=workspace.resource_bindings + (binding_id,),
            created_at=workspace.created_at,
            updated_at=now,
            metadata=workspace.metadata,
        )
        self._workspaces[workspace_id] = updated_ws
        _emit(self._events, "workspace_resource_bound", {
            "binding_id": binding_id, "workspace_id": workspace_id,
            "resource_ref_id": resource_ref_id, "resource_type": resource_type.value,
        }, binding_id)
        return binding

    def bindings_for_workspace(
        self, workspace_id: str, resource_type: ScopeBoundaryKind | None = None,
    ) -> tuple[WorkspaceBinding, ...]:
        """Return all bindings for a workspace, optionally filtered by type."""
        bindings = (b for b in self._bindings.values() if b.workspace_id == workspace_id)
        if resource_type is not None:
            bindings = (b for b in bindings if b.resource_type == resource_type)
        return tuple(bindings)

    def bindings_for_environment(self, environment_id: str) -> tuple[WorkspaceBinding, ...]:
        """Return all bindings for a specific environment."""
        return tuple(b for b in self._bindings.values() if b.environment_id == environment_id)

    # ------------------------------------------------------------------
    # Environment promotion
    # ------------------------------------------------------------------

    def promote_environment(
        self,
        promotion_id: str,
        source_environment_id: str,
        target_environment_id: str,
        *,
        compliance_check_passed: bool = False,
        promoted_by: str = "",
    ) -> EnvironmentPromotion:
        """Promote an environment (e.g., dev → staging)."""
        if promotion_id in self._promotions:
            raise RuntimeCoreInvariantError("Duplicate promotion_id")
        source = self._environments.get(source_environment_id)
        if source is None:
            raise RuntimeCoreInvariantError("Unknown source environment_id")
        target = self._environments.get(target_environment_id)
        if target is None:
            raise RuntimeCoreInvariantError("Unknown target environment_id")

        # Validate promotion path: dev→staging, staging→prod, dev→sandbox, sandbox→staging
        valid_paths = {
            (EnvironmentKind.DEVELOPMENT, EnvironmentKind.STAGING),
            (EnvironmentKind.DEVELOPMENT, EnvironmentKind.SANDBOX),
            (EnvironmentKind.STAGING, EnvironmentKind.PRODUCTION),
            (EnvironmentKind.SANDBOX, EnvironmentKind.STAGING),
        }
        if (source.kind, target.kind) not in valid_paths:
            raise RuntimeCoreInvariantError(
                f"Invalid promotion path: {source.kind.value} → {target.kind.value}"
            )

        # Block promotion to prod without compliance check
        if target.kind == EnvironmentKind.PRODUCTION and not compliance_check_passed:
            now = _now_iso()
            promotion = EnvironmentPromotion(
                promotion_id=promotion_id,
                source_environment_id=source_environment_id,
                target_environment_id=target_environment_id,
                status=PromotionStatus.FAILED,
                compliance_check_passed=False,
                promoted_by=promoted_by,
                requested_at=now,
            )
            self._promotions[promotion_id] = promotion
            _emit(self._events, "promotion_blocked", {
                "promotion_id": promotion_id,
                "reason": "compliance_check_not_passed",
            }, promotion_id)
            return promotion

        now = _now_iso()
        promotion = EnvironmentPromotion(
            promotion_id=promotion_id,
            source_environment_id=source_environment_id,
            target_environment_id=target_environment_id,
            status=PromotionStatus.COMPLETED,
            compliance_check_passed=compliance_check_passed,
            promoted_by=promoted_by,
            requested_at=now,
            completed_at=now,
        )
        self._promotions[promotion_id] = promotion

        # Update target environment's promoted_from
        updated_target = EnvironmentRecord(
            environment_id=target.environment_id,
            workspace_id=target.workspace_id,
            kind=target.kind,
            name=target.name,
            promoted_from=source_environment_id,
            connector_ids=target.connector_ids,
            created_at=target.created_at,
            updated_at=now,
            metadata=target.metadata,
        )
        self._environments[target_environment_id] = updated_target

        _emit(self._events, "environment_promoted", {
            "promotion_id": promotion_id,
            "source": source_environment_id,
            "target": target_environment_id,
        }, promotion_id)
        return promotion

    # ------------------------------------------------------------------
    # Isolation violation detection
    # ------------------------------------------------------------------

    def detect_isolation_violations(self) -> tuple[IsolationViolation, ...]:
        """Detect isolation violations across all tenants."""
        new_violations: list[IsolationViolation] = []
        now = _now_iso()

        for policy in self._policies.values():
            if not policy.enforced:
                continue
            if policy.isolation_level != IsolationLevel.STRICT:
                continue

            tenant_id = policy.tenant_id
            tenant_workspaces = {w.workspace_id for w in self.workspaces_for_tenant(tenant_id)}

            # Check: resources bound to workspace in this tenant should not
            # also be bound to workspaces in other tenants
            for binding in self._bindings.values():
                if binding.resource_type != policy.boundary_kind:
                    continue
                if binding.workspace_id not in tenant_workspaces:
                    continue
                # Check if same resource bound to workspace in different tenant
                for other_binding in self._bindings.values():
                    if other_binding.binding_id == binding.binding_id:
                        continue
                    if other_binding.resource_ref_id != binding.resource_ref_id:
                        continue
                    if other_binding.resource_type != binding.resource_type:
                        continue
                    other_ws = self._workspaces.get(other_binding.workspace_id)
                    if other_ws and other_ws.tenant_id != tenant_id:
                        vid = stable_identifier("viol", {
                            "policy": policy.policy_id,
                            "resource": binding.resource_ref_id,
                            "binding": binding.binding_id,
                            "other": other_binding.binding_id,
                        })
                        if vid not in self._violations:
                            violation = IsolationViolation(
                                violation_id=vid,
                                tenant_id=tenant_id,
                                workspace_id=binding.workspace_id,
                                boundary_kind=policy.boundary_kind,
                                violating_resource_ref=binding.resource_ref_id,
                                description=(
                                    f"Resource {binding.resource_ref_id} shared across "
                                    f"tenants {tenant_id} and {other_ws.tenant_id}"
                                ),
                                escalated=True,
                                detected_at=now,
                            )
                            self._violations[vid] = violation
                            new_violations.append(violation)

        if new_violations:
            _emit(self._events, "isolation_violations_detected", {
                "count": len(new_violations),
            }, "violation-scan")
        return tuple(new_violations)

    def violations_for_tenant(self, tenant_id: str) -> tuple[IsolationViolation, ...]:
        """Return all violations for a tenant."""
        return tuple(v for v in self._violations.values() if v.tenant_id == tenant_id)

    # ------------------------------------------------------------------
    # Tenant health
    # ------------------------------------------------------------------

    def tenant_health(self, tenant_id: str) -> TenantHealth:
        """Produce a health snapshot for a tenant."""
        tenant = self._tenants.get(tenant_id)
        if tenant is None:
            raise RuntimeCoreInvariantError("Unknown tenant_id")

        workspaces = self.workspaces_for_tenant(tenant_id)
        active_ws = sum(1 for w in workspaces if w.status == WorkspaceStatus.ACTIVE)
        envs = sum(1 for e in self._environments.values()
                    if self._workspaces.get(e.workspace_id, WorkspaceRecord(
                        workspace_id="x", tenant_id="x", name="x",
                        created_at="2025-01-01T00:00:00Z")).tenant_id == tenant_id)
        tenant_ws_ids = {w.workspace_id for w in workspaces}
        total_bindings = sum(1 for b in self._bindings.values()
                             if b.workspace_id in tenant_ws_ids)
        total_violations = len(self.violations_for_tenant(tenant_id))

        # compliance_pct: ratio of workspaces without violations
        ws_with_violations = {v.workspace_id for v in self._violations.values()
                               if v.tenant_id == tenant_id}
        if len(workspaces) > 0:
            clean = sum(1 for w in workspaces if w.workspace_id not in ws_with_violations)
            compliance_pct = clean / len(workspaces) * 100.0
        else:
            compliance_pct = 100.0

        now = _now_iso()
        health = TenantHealth(
            tenant_id=tenant_id,
            total_workspaces=len(workspaces),
            active_workspaces=active_ws,
            total_environments=envs,
            total_bindings=total_bindings,
            total_violations=total_violations,
            compliance_pct=compliance_pct,
            assessed_at=now,
        )
        _emit(self._events, "tenant_health_assessed", {
            "tenant_id": tenant_id, "compliance_pct": compliance_pct,
        }, tenant_id)
        return health

    # ------------------------------------------------------------------
    # Decisions
    # ------------------------------------------------------------------

    def record_decision(
        self,
        decision_id: str,
        tenant_id: str,
        title: str,
        *,
        description: str = "",
        confidence: float = 0.0,
        decided_by: str = "",
    ) -> TenantDecision:
        """Record a tenant-level decision."""
        if decision_id in self._decisions:
            raise RuntimeCoreInvariantError("Duplicate decision_id")
        if tenant_id not in self._tenants:
            raise RuntimeCoreInvariantError("Unknown tenant_id")
        now = _now_iso()
        decision = TenantDecision(
            decision_id=decision_id,
            tenant_id=tenant_id,
            title=title,
            description=description,
            confidence=confidence,
            decided_by=decided_by,
            decided_at=now,
        )
        self._decisions[decision_id] = decision
        _emit(self._events, "tenant_decision_recorded", {
            "decision_id": decision_id, "tenant_id": tenant_id,
        }, decision_id)
        return decision

    # ------------------------------------------------------------------
    # Closure
    # ------------------------------------------------------------------

    def close_tenant(
        self,
        report_id: str,
        tenant_id: str,
    ) -> TenantClosureReport:
        """Close a tenant and produce a closure report."""
        tenant = self._tenants.get(tenant_id)
        if tenant is None:
            raise RuntimeCoreInvariantError("Unknown tenant_id")
        if report_id in {d.decision_id for d in self._decisions.values()}:
            raise RuntimeCoreInvariantError("Duplicate report_id")

        workspaces = self.workspaces_for_tenant(tenant_id)
        tenant_ws_ids = {w.workspace_id for w in workspaces}
        envs = [e for e in self._environments.values()
                if e.workspace_id in tenant_ws_ids]
        bindings = [b for b in self._bindings.values()
                    if b.workspace_id in tenant_ws_ids]
        promotions = [p for p in self._promotions.values()
                      if self._environments.get(p.source_environment_id) is not None
                      and self._environments[p.source_environment_id].workspace_id in tenant_ws_ids]
        violations = self.violations_for_tenant(tenant_id)
        decisions = [d for d in self._decisions.values() if d.tenant_id == tenant_id]

        health = self.tenant_health(tenant_id)

        now = _now_iso()
        report = TenantClosureReport(
            report_id=report_id,
            tenant_id=tenant_id,
            total_workspaces=len(workspaces),
            total_environments=len(envs),
            total_bindings=len(bindings),
            total_promotions=len(promotions),
            total_violations=len(violations),
            total_decisions=len(decisions),
            compliance_pct=health.compliance_pct,
            closed_at=now,
        )

        # Set tenant to ARCHIVED
        self.set_tenant_status(tenant_id, TenantStatus.ARCHIVED)

        _emit(self._events, "tenant_closed", {
            "report_id": report_id, "tenant_id": tenant_id,
        }, report_id)
        return report

    # ------------------------------------------------------------------
    # State hash
    # ------------------------------------------------------------------

    def state_hash(self) -> str:
        """Compute a hash of the current engine state."""
        parts = [
            f"tenants={self.tenant_count}",
            f"workspaces={self.workspace_count}",
            f"environments={self.environment_count}",
            f"policies={self.policy_count}",
            f"bindings={self.binding_count}",
            f"promotions={self.promotion_count}",
            f"violations={self.violation_count}",
            f"decisions={self.decision_count}",
        ]
        return sha256("|".join(parts).encode()).hexdigest()
