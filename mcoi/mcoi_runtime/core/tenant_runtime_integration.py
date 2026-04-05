"""Purpose: tenant runtime integration bridge.
Governance scope: composing tenant runtime with campaign, portfolio, budget,
    connector, memory, program, and graph scopes; workspace-scoped bindings;
    memory mesh and operational graph attachment.
Dependencies: tenant_runtime engine, event_spine, memory_mesh,
    core invariants.
Invariants:
  - Every tenant operation emits events.
  - Tenant state is attached to memory mesh.
  - All returns are immutable.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ..contracts.tenant_runtime import (
    EnvironmentKind,
    IsolationLevel,
    ScopeBoundaryKind,
    TenantStatus,
    WorkspaceStatus,
)
from ..contracts.event import EventRecord, EventSource, EventType
from ..contracts.memory_mesh import (
    MemoryRecord,
    MemoryScope,
    MemoryTrustLevel,
    MemoryType,
)
from .event_spine import EventSpineEngine
from .invariants import RuntimeCoreInvariantError, stable_identifier
from .memory_mesh import MemoryMeshEngine
from .tenant_runtime import TenantRuntimeEngine


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _emit(es: EventSpineEngine, action: str, payload: dict, cid: str) -> EventRecord:
    now = _now_iso()
    payload["action"] = action
    event = EventRecord(
        event_id=stable_identifier("evt-tint", {"action": action, "ts": now, "cid": cid}),
        event_type=EventType.CUSTOM,
        source=EventSource.COMMUNICATION_SYSTEM,
        correlation_id=cid,
        payload=payload,
        emitted_at=now,
    )
    es.emit(event)
    return event


class TenantRuntimeIntegration:
    """Integration bridge for tenant runtime with platform layers."""

    def __init__(
        self,
        tenant_engine: TenantRuntimeEngine,
        event_spine: EventSpineEngine,
        memory_engine: MemoryMeshEngine,
    ) -> None:
        if not isinstance(tenant_engine, TenantRuntimeEngine):
            raise RuntimeCoreInvariantError("tenant_engine must be a TenantRuntimeEngine")
        if not isinstance(event_spine, EventSpineEngine):
            raise RuntimeCoreInvariantError("event_spine must be an EventSpineEngine")
        if not isinstance(memory_engine, MemoryMeshEngine):
            raise RuntimeCoreInvariantError("memory_engine must be a MemoryMeshEngine")
        self._tenant = tenant_engine
        self._events = event_spine
        self._memory = memory_engine

    # ------------------------------------------------------------------
    # Resource binding helpers
    # ------------------------------------------------------------------

    def bind_campaign_to_workspace(
        self,
        binding_id: str,
        workspace_id: str,
        campaign_ref_id: str,
        *,
        environment_id: str = "",
    ) -> dict[str, Any]:
        """Bind a campaign to a workspace."""
        binding = self._tenant.bind_workspace_resource(
            binding_id, workspace_id, campaign_ref_id,
            ScopeBoundaryKind.CAMPAIGN,
            environment_id=environment_id,
        )
        _emit(self._events, "campaign_bound_to_workspace", {
            "binding_id": binding_id,
            "workspace_id": workspace_id,
            "campaign_ref_id": campaign_ref_id,
        }, binding_id)
        return {
            "binding_id": binding_id,
            "workspace_id": workspace_id,
            "resource_ref_id": campaign_ref_id,
            "resource_type": "campaign",
        }

    def bind_portfolio_to_workspace(
        self,
        binding_id: str,
        workspace_id: str,
        portfolio_ref_id: str,
        *,
        environment_id: str = "",
    ) -> dict[str, Any]:
        """Bind a portfolio to a workspace."""
        binding = self._tenant.bind_workspace_resource(
            binding_id, workspace_id, portfolio_ref_id,
            ScopeBoundaryKind.CAMPAIGN,
            environment_id=environment_id,
        )
        _emit(self._events, "portfolio_bound_to_workspace", {
            "binding_id": binding_id,
            "workspace_id": workspace_id,
            "portfolio_ref_id": portfolio_ref_id,
        }, binding_id)
        return {
            "binding_id": binding_id,
            "workspace_id": workspace_id,
            "resource_ref_id": portfolio_ref_id,
            "resource_type": "portfolio",
        }

    def bind_budget_to_tenant(
        self,
        binding_id: str,
        workspace_id: str,
        budget_ref_id: str,
    ) -> dict[str, Any]:
        """Bind a budget to a workspace (tenant-scoped via workspace)."""
        binding = self._tenant.bind_workspace_resource(
            binding_id, workspace_id, budget_ref_id,
            ScopeBoundaryKind.BUDGET,
        )
        _emit(self._events, "budget_bound_to_tenant", {
            "binding_id": binding_id,
            "workspace_id": workspace_id,
            "budget_ref_id": budget_ref_id,
        }, binding_id)
        return {
            "binding_id": binding_id,
            "workspace_id": workspace_id,
            "resource_ref_id": budget_ref_id,
            "resource_type": "budget",
        }

    def bind_connector_to_environment(
        self,
        binding_id: str,
        workspace_id: str,
        connector_ref_id: str,
        environment_id: str,
    ) -> dict[str, Any]:
        """Bind a connector to a specific environment within a workspace."""
        binding = self._tenant.bind_workspace_resource(
            binding_id, workspace_id, connector_ref_id,
            ScopeBoundaryKind.CONNECTOR,
            environment_id=environment_id,
        )
        _emit(self._events, "connector_bound_to_environment", {
            "binding_id": binding_id,
            "workspace_id": workspace_id,
            "connector_ref_id": connector_ref_id,
            "environment_id": environment_id,
        }, binding_id)
        return {
            "binding_id": binding_id,
            "workspace_id": workspace_id,
            "resource_ref_id": connector_ref_id,
            "environment_id": environment_id,
            "resource_type": "connector",
        }

    def bind_memory_scope_to_workspace(
        self,
        binding_id: str,
        workspace_id: str,
        memory_scope_ref_id: str,
    ) -> dict[str, Any]:
        """Bind a memory scope to a workspace."""
        binding = self._tenant.bind_workspace_resource(
            binding_id, workspace_id, memory_scope_ref_id,
            ScopeBoundaryKind.MEMORY,
        )
        _emit(self._events, "memory_scope_bound_to_workspace", {
            "binding_id": binding_id,
            "workspace_id": workspace_id,
            "memory_scope_ref_id": memory_scope_ref_id,
        }, binding_id)
        return {
            "binding_id": binding_id,
            "workspace_id": workspace_id,
            "resource_ref_id": memory_scope_ref_id,
            "resource_type": "memory",
        }

    def bind_program_to_tenant(
        self,
        binding_id: str,
        workspace_id: str,
        program_ref_id: str,
    ) -> dict[str, Any]:
        """Bind a program to a workspace (tenant-scoped via workspace)."""
        binding = self._tenant.bind_workspace_resource(
            binding_id, workspace_id, program_ref_id,
            ScopeBoundaryKind.PROGRAM,
        )
        _emit(self._events, "program_bound_to_tenant", {
            "binding_id": binding_id,
            "workspace_id": workspace_id,
            "program_ref_id": program_ref_id,
        }, binding_id)
        return {
            "binding_id": binding_id,
            "workspace_id": workspace_id,
            "resource_ref_id": program_ref_id,
            "resource_type": "program",
        }

    # ------------------------------------------------------------------
    # Memory mesh and graph attachment
    # ------------------------------------------------------------------

    def attach_tenant_state_to_memory_mesh(
        self,
        tenant_id: str,
    ) -> MemoryRecord:
        """Persist tenant state to memory mesh."""
        now = _now_iso()
        workspaces = self._tenant.workspaces_for_tenant(tenant_id)
        ws_ids = [w.workspace_id for w in workspaces]
        violations = self._tenant.violations_for_tenant(tenant_id)
        content: dict[str, Any] = {
            "tenant_id": tenant_id,
            "total_workspaces": len(workspaces),
            "workspace_ids": ws_ids,
            "total_environments": self._tenant.environment_count,
            "total_bindings": self._tenant.binding_count,
            "total_policies": self._tenant.policy_count,
            "total_violations": len(violations),
            "total_promotions": self._tenant.promotion_count,
            "total_decisions": self._tenant.decision_count,
        }

        mem = MemoryRecord(
            memory_id=stable_identifier("mem-tenant", {"id": tenant_id}),
            memory_type=MemoryType.OBSERVATION,
            scope=MemoryScope.GLOBAL,
            scope_ref_id=tenant_id,
            trust_level=MemoryTrustLevel.VERIFIED,
            title="Tenant state",
            content=content,
            source_ids=(tenant_id,),
            tags=("tenant", "workspace", "environment"),
            confidence=1.0,
            created_at=now,
            updated_at=now,
        )
        self._memory.add_memory(mem)

        _emit(self._events, "tenant_attached_to_memory", {
            "tenant_id": tenant_id,
            "memory_id": mem.memory_id,
        }, tenant_id)
        return mem

    def attach_tenant_state_to_graph(
        self,
        tenant_id: str,
    ) -> dict[str, Any]:
        """Return tenant state suitable for operational graph consumption."""
        workspaces = self._tenant.workspaces_for_tenant(tenant_id)
        violations = self._tenant.violations_for_tenant(tenant_id)
        return {
            "tenant_id": tenant_id,
            "total_workspaces": len(workspaces),
            "active_workspaces": sum(1 for w in workspaces if w.status == WorkspaceStatus.ACTIVE),
            "total_environments": self._tenant.environment_count,
            "total_bindings": self._tenant.binding_count,
            "total_violations": len(violations),
            "violation_ids": [v.violation_id for v in violations],
            "total_promotions": self._tenant.promotion_count,
        }
