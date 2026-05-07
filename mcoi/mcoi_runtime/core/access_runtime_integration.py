"""Purpose: access runtime integration bridge.
Governance scope: composing access runtime with campaign, portfolio,
    connector, budget, program, and environment promotion authorization;
    memory mesh and operational graph attachment.
Dependencies: access_runtime engine, event_spine, memory_mesh,
    core invariants.
Invariants:
  - Every authorization emits events.
  - Access audit state is attached to memory mesh.
  - All returns are immutable.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ..contracts.access_runtime import (
    AccessDecision,
    AuthContextKind,
    DelegationStatus,
    PermissionEffect,
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
from mcoi_runtime.governance.guards.access import AccessRuntimeEngine


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _emit(es: EventSpineEngine, action: str, payload: dict, cid: str) -> EventRecord:
    now = _now_iso()
    payload["action"] = action
    event = EventRecord(
        event_id=stable_identifier("evt-aint", {"action": action, "ts": now, "cid": cid}),
        event_type=EventType.CUSTOM,
        source=EventSource.COMMUNICATION_SYSTEM,
        correlation_id=cid,
        payload=payload,
        emitted_at=now,
    )
    es.emit(event)
    return event


class AccessRuntimeIntegration:
    """Integration bridge for access runtime with platform layers."""

    def __init__(
        self,
        access_engine: AccessRuntimeEngine,
        event_spine: EventSpineEngine,
        memory_engine: MemoryMeshEngine,
    ) -> None:
        if not isinstance(access_engine, AccessRuntimeEngine):
            raise RuntimeCoreInvariantError("access_engine must be an AccessRuntimeEngine")
        if not isinstance(event_spine, EventSpineEngine):
            raise RuntimeCoreInvariantError("event_spine must be an EventSpineEngine")
        if not isinstance(memory_engine, MemoryMeshEngine):
            raise RuntimeCoreInvariantError("memory_engine must be a MemoryMeshEngine")
        self._access = access_engine
        self._events = event_spine
        self._memory = memory_engine

    # ------------------------------------------------------------------
    # Authorization helpers
    # ------------------------------------------------------------------

    def authorize_campaign_action(
        self,
        request_id: str,
        identity_id: str,
        action: str,
        *,
        scope_kind: AuthContextKind = AuthContextKind.WORKSPACE,
        scope_ref_id: str = "*",
    ) -> dict[str, Any]:
        """Authorize a campaign action."""
        ev = self._access.evaluate_access(
            request_id, identity_id, "campaign", action,
            scope_kind=scope_kind, scope_ref_id=scope_ref_id,
        )
        _emit(self._events, "campaign_action_authorized", {
            "request_id": request_id, "identity_id": identity_id,
            "action": action, "decision": ev.decision.value,
        }, request_id)
        return {
            "request_id": request_id,
            "identity_id": identity_id,
            "resource_type": "campaign",
            "action": action,
            "decision": ev.decision.value,
            "reason": ev.reason,
        }

    def authorize_portfolio_action(
        self,
        request_id: str,
        identity_id: str,
        action: str,
        *,
        scope_kind: AuthContextKind = AuthContextKind.WORKSPACE,
        scope_ref_id: str = "*",
    ) -> dict[str, Any]:
        """Authorize a portfolio action."""
        ev = self._access.evaluate_access(
            request_id, identity_id, "portfolio", action,
            scope_kind=scope_kind, scope_ref_id=scope_ref_id,
        )
        _emit(self._events, "portfolio_action_authorized", {
            "request_id": request_id, "identity_id": identity_id,
            "action": action, "decision": ev.decision.value,
        }, request_id)
        return {
            "request_id": request_id,
            "identity_id": identity_id,
            "resource_type": "portfolio",
            "action": action,
            "decision": ev.decision.value,
            "reason": ev.reason,
        }

    def authorize_connector_use(
        self,
        request_id: str,
        identity_id: str,
        *,
        scope_kind: AuthContextKind = AuthContextKind.ENVIRONMENT,
        scope_ref_id: str = "*",
    ) -> dict[str, Any]:
        """Authorize connector usage."""
        ev = self._access.evaluate_access(
            request_id, identity_id, "connector", "use",
            scope_kind=scope_kind, scope_ref_id=scope_ref_id,
        )
        _emit(self._events, "connector_use_authorized", {
            "request_id": request_id, "identity_id": identity_id,
            "decision": ev.decision.value,
        }, request_id)
        return {
            "request_id": request_id,
            "identity_id": identity_id,
            "resource_type": "connector",
            "action": "use",
            "decision": ev.decision.value,
            "reason": ev.reason,
        }

    def authorize_budget_change(
        self,
        request_id: str,
        identity_id: str,
        action: str = "modify",
        *,
        scope_kind: AuthContextKind = AuthContextKind.TENANT,
        scope_ref_id: str = "*",
    ) -> dict[str, Any]:
        """Authorize a budget change."""
        ev = self._access.evaluate_access(
            request_id, identity_id, "budget", action,
            scope_kind=scope_kind, scope_ref_id=scope_ref_id,
        )
        _emit(self._events, "budget_change_authorized", {
            "request_id": request_id, "identity_id": identity_id,
            "action": action, "decision": ev.decision.value,
        }, request_id)
        return {
            "request_id": request_id,
            "identity_id": identity_id,
            "resource_type": "budget",
            "action": action,
            "decision": ev.decision.value,
            "reason": ev.reason,
        }

    def authorize_program_change(
        self,
        request_id: str,
        identity_id: str,
        action: str = "modify",
        *,
        scope_kind: AuthContextKind = AuthContextKind.TENANT,
        scope_ref_id: str = "*",
    ) -> dict[str, Any]:
        """Authorize a program change."""
        ev = self._access.evaluate_access(
            request_id, identity_id, "program", action,
            scope_kind=scope_kind, scope_ref_id=scope_ref_id,
        )
        _emit(self._events, "program_change_authorized", {
            "request_id": request_id, "identity_id": identity_id,
            "action": action, "decision": ev.decision.value,
        }, request_id)
        return {
            "request_id": request_id,
            "identity_id": identity_id,
            "resource_type": "program",
            "action": action,
            "decision": ev.decision.value,
            "reason": ev.reason,
        }

    def authorize_environment_promotion(
        self,
        request_id: str,
        identity_id: str,
        *,
        scope_kind: AuthContextKind = AuthContextKind.ENVIRONMENT,
        scope_ref_id: str = "*",
    ) -> dict[str, Any]:
        """Authorize an environment promotion."""
        ev = self._access.evaluate_access(
            request_id, identity_id, "environment", "promote",
            scope_kind=scope_kind, scope_ref_id=scope_ref_id,
        )
        _emit(self._events, "environment_promotion_authorized", {
            "request_id": request_id, "identity_id": identity_id,
            "decision": ev.decision.value,
        }, request_id)
        return {
            "request_id": request_id,
            "identity_id": identity_id,
            "resource_type": "environment",
            "action": "promote",
            "decision": ev.decision.value,
            "reason": ev.reason,
        }

    # ------------------------------------------------------------------
    # Memory mesh and graph attachment
    # ------------------------------------------------------------------

    def attach_access_audit_to_memory_mesh(
        self,
        scope_ref_id: str,
    ) -> MemoryRecord:
        """Persist access audit state to memory mesh."""
        now = _now_iso()
        violations = list(self._access._violations.values())
        content: dict[str, Any] = {
            "scope_ref_id": scope_ref_id,
            "total_identities": self._access.identity_count,
            "total_roles": self._access.role_count,
            "total_bindings": self._access.binding_count,
            "total_rules": self._access.rule_count,
            "total_delegations": self._access.delegation_count,
            "total_evaluations": self._access.evaluation_count,
            "total_violations": self._access.violation_count,
            "total_audits": self._access.audit_count,
        }

        mem = MemoryRecord(
            memory_id=stable_identifier("mem-access", {"id": scope_ref_id}),
            memory_type=MemoryType.OBSERVATION,
            scope=MemoryScope.GLOBAL,
            scope_ref_id=scope_ref_id,
            trust_level=MemoryTrustLevel.VERIFIED,
            title="Access audit state",
            content=content,
            source_ids=(scope_ref_id,),
            tags=("access", "identity", "authorization"),
            confidence=1.0,
            created_at=now,
            updated_at=now,
        )
        self._memory.add_memory(mem)

        _emit(self._events, "access_audit_attached_to_memory", {
            "scope_ref_id": scope_ref_id,
            "memory_id": mem.memory_id,
        }, scope_ref_id)
        return mem

    def attach_access_audit_to_graph(
        self,
        scope_ref_id: str,
    ) -> dict[str, Any]:
        """Return access audit state suitable for operational graph."""
        active_delegations = sum(
            1 for d in self._access._delegations.values()
            if d.status == DelegationStatus.ACTIVE
        )
        return {
            "scope_ref_id": scope_ref_id,
            "total_identities": self._access.identity_count,
            "total_roles": self._access.role_count,
            "total_bindings": self._access.binding_count,
            "total_violations": self._access.violation_count,
            "active_delegations": active_delegations,
            "total_evaluations": self._access.evaluation_count,
            "total_audits": self._access.audit_count,
        }
