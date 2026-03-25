"""Purpose: policy enforcement integration bridge.
Governance scope: composing policy enforcement with campaign, connector,
    budget, environment promotion, change execution, and executive
    intervention authorization; memory mesh and operational graph attachment.
Dependencies: policy_enforcement engine, event_spine, memory_mesh,
    core invariants.
Invariants:
  - Every enforcement emits events.
  - Enforcement audit state is attached to memory mesh.
  - All returns are immutable.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ..contracts.policy_enforcement import (
    EnforcementDecision,
    PrivilegeLevel,
    SessionStatus,
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
from .policy_enforcement import PolicyEnforcementEngine


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _emit(es: EventSpineEngine, action: str, payload: dict, cid: str) -> EventRecord:
    now = _now_iso()
    payload["action"] = action
    event = EventRecord(
        event_id=stable_identifier("evt-pint", {"action": action, "ts": now, "cid": cid}),
        event_type=EventType.CUSTOM,
        source=EventSource.COMMUNICATION_SYSTEM,
        correlation_id=cid,
        payload=payload,
        emitted_at=now,
    )
    es.emit(event)
    return event


class PolicyEnforcementIntegration:
    """Integration bridge for policy enforcement with platform layers."""

    def __init__(
        self,
        enforcement_engine: PolicyEnforcementEngine,
        event_spine: EventSpineEngine,
        memory_engine: MemoryMeshEngine,
    ) -> None:
        if not isinstance(enforcement_engine, PolicyEnforcementEngine):
            raise RuntimeCoreInvariantError(
                "enforcement_engine must be a PolicyEnforcementEngine"
            )
        if not isinstance(event_spine, EventSpineEngine):
            raise RuntimeCoreInvariantError("event_spine must be an EventSpineEngine")
        if not isinstance(memory_engine, MemoryMeshEngine):
            raise RuntimeCoreInvariantError("memory_engine must be a MemoryMeshEngine")
        self._enforcement = enforcement_engine
        self._events = event_spine
        self._memory = memory_engine

    # ------------------------------------------------------------------
    # Enforcement helpers
    # ------------------------------------------------------------------

    def enforce_campaign_action(
        self,
        session_id: str,
        action: str,
        *,
        environment_id: str = "",
        required_privilege: PrivilegeLevel = PrivilegeLevel.STANDARD,
    ) -> dict[str, Any]:
        """Enforce a campaign action within a session."""
        ev = self._enforcement.evaluate_session_action(
            session_id, "campaign", action,
            environment_id=environment_id,
            required_privilege=required_privilege,
        )
        _emit(self._events, "campaign_action_enforced", {
            "session_id": session_id, "act": action,
            "decision": ev.decision.value,
        }, session_id)
        return {
            "session_id": session_id,
            "resource_type": "campaign",
            "action": action,
            "decision": ev.decision.value,
            "reason": ev.reason,
        }

    def enforce_connector_action(
        self,
        session_id: str,
        action: str,
        *,
        connector_id: str = "",
        environment_id: str = "",
        required_privilege: PrivilegeLevel = PrivilegeLevel.STANDARD,
    ) -> dict[str, Any]:
        """Enforce a connector action within a session."""
        ev = self._enforcement.evaluate_session_action(
            session_id, "connector", action,
            environment_id=environment_id,
            connector_id=connector_id,
            required_privilege=required_privilege,
        )
        _emit(self._events, "connector_action_enforced", {
            "session_id": session_id, "act": action,
            "decision": ev.decision.value,
        }, session_id)
        return {
            "session_id": session_id,
            "resource_type": "connector",
            "action": action,
            "decision": ev.decision.value,
            "reason": ev.reason,
        }

    def enforce_budget_action(
        self,
        session_id: str,
        action: str = "modify",
        *,
        required_privilege: PrivilegeLevel = PrivilegeLevel.ELEVATED,
    ) -> dict[str, Any]:
        """Enforce a budget action within a session."""
        ev = self._enforcement.evaluate_session_action(
            session_id, "budget", action,
            required_privilege=required_privilege,
        )
        _emit(self._events, "budget_action_enforced", {
            "session_id": session_id, "act": action,
            "decision": ev.decision.value,
        }, session_id)
        return {
            "session_id": session_id,
            "resource_type": "budget",
            "action": action,
            "decision": ev.decision.value,
            "reason": ev.reason,
        }

    def enforce_environment_promotion(
        self,
        session_id: str,
        *,
        environment_id: str = "",
        required_privilege: PrivilegeLevel = PrivilegeLevel.ELEVATED,
    ) -> dict[str, Any]:
        """Enforce an environment promotion within a session."""
        ev = self._enforcement.evaluate_session_action(
            session_id, "environment", "promote",
            environment_id=environment_id,
            required_privilege=required_privilege,
        )
        _emit(self._events, "environment_promotion_enforced", {
            "session_id": session_id, "decision": ev.decision.value,
        }, session_id)
        return {
            "session_id": session_id,
            "resource_type": "environment",
            "action": "promote",
            "decision": ev.decision.value,
            "reason": ev.reason,
        }

    def enforce_change_execution(
        self,
        session_id: str,
        resource_type: str,
        action: str,
        *,
        environment_id: str = "",
        required_privilege: PrivilegeLevel = PrivilegeLevel.STANDARD,
    ) -> dict[str, Any]:
        """Enforce a generic change execution within a session."""
        ev = self._enforcement.evaluate_session_action(
            session_id, resource_type, action,
            environment_id=environment_id,
            required_privilege=required_privilege,
        )
        _emit(self._events, "change_execution_enforced", {
            "session_id": session_id, "resource_type": resource_type,
            "act": action, "decision": ev.decision.value,
        }, session_id)
        return {
            "session_id": session_id,
            "resource_type": resource_type,
            "action": action,
            "decision": ev.decision.value,
            "reason": ev.reason,
        }

    def enforce_executive_intervention(
        self,
        session_id: str,
        action: str = "override",
        *,
        required_privilege: PrivilegeLevel = PrivilegeLevel.ADMIN,
    ) -> dict[str, Any]:
        """Enforce an executive intervention within a session."""
        ev = self._enforcement.evaluate_session_action(
            session_id, "executive", action,
            required_privilege=required_privilege,
        )
        _emit(self._events, "executive_intervention_enforced", {
            "session_id": session_id, "act": action,
            "decision": ev.decision.value,
        }, session_id)
        return {
            "session_id": session_id,
            "resource_type": "executive",
            "action": action,
            "decision": ev.decision.value,
            "reason": ev.reason,
        }

    # ------------------------------------------------------------------
    # Memory mesh and graph attachment
    # ------------------------------------------------------------------

    def attach_session_audit_to_memory_mesh(
        self,
        scope_ref_id: str,
    ) -> MemoryRecord:
        """Persist session audit state to memory mesh."""
        now = _now_iso()
        content: dict[str, Any] = {
            "scope_ref_id": scope_ref_id,
            "total_sessions": self._enforcement.session_count,
            "active_sessions": self._enforcement.active_session_count,
            "total_constraints": self._enforcement.constraint_count,
            "total_step_ups": self._enforcement.step_up_count,
            "total_enforcements": self._enforcement.enforcement_count,
            "total_revocations": self._enforcement.revocation_count,
            "total_bindings": self._enforcement.binding_count,
            "total_audits": self._enforcement.audit_count,
        }

        mem = MemoryRecord(
            memory_id=stable_identifier("mem-penf", {"id": scope_ref_id}),
            memory_type=MemoryType.OBSERVATION,
            scope=MemoryScope.GLOBAL,
            scope_ref_id=scope_ref_id,
            trust_level=MemoryTrustLevel.VERIFIED,
            title=f"Session enforcement state: {scope_ref_id}",
            content=content,
            source_ids=(scope_ref_id,),
            tags=("session", "enforcement", "policy"),
            confidence=1.0,
            created_at=now,
            updated_at=now,
        )
        self._memory.add_memory(mem)

        _emit(self._events, "session_audit_attached_to_memory", {
            "scope_ref_id": scope_ref_id,
            "memory_id": mem.memory_id,
        }, scope_ref_id)
        return mem

    def attach_session_audit_to_graph(
        self,
        scope_ref_id: str,
    ) -> dict[str, Any]:
        """Return session audit state suitable for operational graph."""
        return {
            "scope_ref_id": scope_ref_id,
            "total_sessions": self._enforcement.session_count,
            "active_sessions": self._enforcement.active_session_count,
            "total_constraints": self._enforcement.constraint_count,
            "total_step_ups": self._enforcement.step_up_count,
            "total_enforcements": self._enforcement.enforcement_count,
            "total_revocations": self._enforcement.revocation_count,
            "total_bindings": self._enforcement.binding_count,
            "total_audits": self._enforcement.audit_count,
        }
