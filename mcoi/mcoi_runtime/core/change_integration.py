"""Purpose: controlled change integration bridge.
Governance scope: composing change runtime with optimization, governance,
    fault campaigns, portfolio, availability, financials, connector routing,
    domain pack resolution, memory mesh, and operational graph.
Dependencies: change_runtime engine, event_spine, memory_mesh,
    core invariants.
Invariants:
  - Every change operation emits events.
  - Change state is attached to memory mesh.
  - All returns are immutable.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ..contracts.change_runtime import (
    ChangeEvidenceKind,
    ChangeScope,
    ChangeStatus,
    ChangeType,
    RolloutMode,
)
from ..contracts.event import EventRecord, EventSource, EventType
from ..contracts.memory_mesh import (
    MemoryRecord,
    MemoryScope,
    MemoryTrustLevel,
    MemoryType,
)
from .change_runtime import ChangeRuntimeEngine
from .event_spine import EventSpineEngine
from .invariants import RuntimeCoreInvariantError, stable_identifier
from .memory_mesh import MemoryMeshEngine


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _emit(es: EventSpineEngine, action: str, payload: dict, cid: str) -> EventRecord:
    now = _now_iso()
    payload["action"] = action
    event = EventRecord(
        event_id=stable_identifier("evt-cint", {"action": action, "ts": now, "cid": cid}),
        event_type=EventType.CUSTOM,
        source=EventSource.COMMUNICATION_SYSTEM,
        correlation_id=cid,
        payload=payload,
        emitted_at=now,
    )
    es.emit(event)
    return event


class ChangeIntegration:
    """Integration bridge for controlled changes with all platform layers."""

    def __init__(
        self,
        change_engine: ChangeRuntimeEngine,
        event_spine: EventSpineEngine,
        memory_engine: MemoryMeshEngine,
    ) -> None:
        if not isinstance(change_engine, ChangeRuntimeEngine):
            raise RuntimeCoreInvariantError("change_engine must be a ChangeRuntimeEngine")
        if not isinstance(event_spine, EventSpineEngine):
            raise RuntimeCoreInvariantError("event_spine must be an EventSpineEngine")
        if not isinstance(memory_engine, MemoryMeshEngine):
            raise RuntimeCoreInvariantError("memory_engine must be a MemoryMeshEngine")
        self._change = change_engine
        self._events = event_spine
        self._memory = memory_engine

    # ------------------------------------------------------------------
    # Source-specific change creation
    # ------------------------------------------------------------------

    def change_from_optimization(
        self,
        change_id: str,
        title: str,
        change_type: ChangeType,
        *,
        recommendation_id: str = "",
        scope: ChangeScope = ChangeScope.GLOBAL,
        scope_ref_id: str = "",
        rollout_mode: RolloutMode = RolloutMode.CANARY,
        approval_required: bool = True,
        reason: str = "",
        steps: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Create a change from an optimization recommendation."""
        cr = self._change.create_change_request(
            change_id, title, change_type,
            recommendation_id=recommendation_id,
            scope=scope,
            scope_ref_id=scope_ref_id,
            rollout_mode=rollout_mode,
            approval_required=approval_required,
            requested_by="optimization_engine",
            reason=reason,
        )
        plan = None
        if steps:
            plan = self._change.plan_change(
                f"{change_id}-plan", change_id, f"Plan: {title}", steps,
                rollout_mode=rollout_mode,
            )

        _emit(self._events, "change_from_optimization", {
            "change_id": change_id,
            "recommendation_id": recommendation_id,
            "change_type": change_type.value,
        }, change_id)
        return {
            "change_id": change_id,
            "source": "optimization",
            "change_type": change_type.value,
            "rollout_mode": rollout_mode.value,
            "approval_required": approval_required,
            "plan_id": plan.plan_id if plan else None,
            "step_count": len(plan.step_ids) if plan else 0,
        }

    def change_from_governance(
        self,
        change_id: str,
        title: str,
        change_type: ChangeType,
        *,
        scope: ChangeScope = ChangeScope.GLOBAL,
        scope_ref_id: str = "",
        rollout_mode: RolloutMode = RolloutMode.IMMEDIATE,
        reason: str = "",
        steps: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Create a change from a governance policy decision."""
        cr = self._change.create_change_request(
            change_id, title, change_type,
            scope=scope,
            scope_ref_id=scope_ref_id,
            rollout_mode=rollout_mode,
            approval_required=False,
            requested_by="governance_engine",
            reason=reason,
        )
        plan = None
        if steps:
            plan = self._change.plan_change(
                f"{change_id}-plan", change_id, f"Plan: {title}", steps,
                rollout_mode=rollout_mode,
            )

        _emit(self._events, "change_from_governance", {
            "change_id": change_id,
            "change_type": change_type.value,
        }, change_id)
        return {
            "change_id": change_id,
            "source": "governance",
            "change_type": change_type.value,
            "rollout_mode": rollout_mode.value,
            "approval_required": False,
            "plan_id": plan.plan_id if plan else None,
            "step_count": len(plan.step_ids) if plan else 0,
        }

    def change_from_fault_campaign(
        self,
        change_id: str,
        title: str,
        change_type: ChangeType,
        *,
        scope: ChangeScope = ChangeScope.GLOBAL,
        scope_ref_id: str = "",
        rollout_mode: RolloutMode = RolloutMode.CANARY,
        approval_required: bool = True,
        reason: str = "",
        steps: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Create a change from a fault campaign result."""
        cr = self._change.create_change_request(
            change_id, title, change_type,
            scope=scope,
            scope_ref_id=scope_ref_id,
            rollout_mode=rollout_mode,
            approval_required=approval_required,
            requested_by="fault_campaign_engine",
            reason=reason,
        )
        plan = None
        if steps:
            plan = self._change.plan_change(
                f"{change_id}-plan", change_id, f"Plan: {title}", steps,
                rollout_mode=rollout_mode,
            )

        _emit(self._events, "change_from_fault_campaign", {
            "change_id": change_id,
            "change_type": change_type.value,
        }, change_id)
        return {
            "change_id": change_id,
            "source": "fault_campaign",
            "change_type": change_type.value,
            "rollout_mode": rollout_mode.value,
            "approval_required": approval_required,
            "plan_id": plan.plan_id if plan else None,
            "step_count": len(plan.step_ids) if plan else 0,
        }

    # ------------------------------------------------------------------
    # Apply change to subsystems
    # ------------------------------------------------------------------

    def apply_change_to_portfolio(
        self,
        change_id: str,
        *,
        portfolio_ref_id: str = "",
        action: str = "update",
    ) -> dict[str, Any]:
        """Execute change steps targeting portfolio subsystem."""
        steps = self._change.get_steps(change_id)
        executed = 0
        for step in steps:
            if step.status == ChangeStatus.DRAFT:
                self._change.execute_change_step(change_id, step.step_id)
                executed += 1
        self._change.collect_evidence(
            change_id, ChangeEvidenceKind.LOG_ENTRY,
            description=f"Applied to portfolio {portfolio_ref_id}: {action}",
        )
        _emit(self._events, "change_applied_to_portfolio", {
            "change_id": change_id,
            "portfolio_ref_id": portfolio_ref_id,
            "steps_executed": executed,
        }, change_id)
        return {
            "change_id": change_id,
            "target": "portfolio",
            "portfolio_ref_id": portfolio_ref_id,
            "steps_executed": executed,
        }

    def apply_change_to_availability(
        self,
        change_id: str,
        *,
        identity_ref_id: str = "",
        action: str = "update",
    ) -> dict[str, Any]:
        """Execute change steps targeting availability subsystem."""
        steps = self._change.get_steps(change_id)
        executed = 0
        for step in steps:
            if step.status == ChangeStatus.DRAFT:
                self._change.execute_change_step(change_id, step.step_id)
                executed += 1
        self._change.collect_evidence(
            change_id, ChangeEvidenceKind.LOG_ENTRY,
            description=f"Applied to availability {identity_ref_id}: {action}",
        )
        _emit(self._events, "change_applied_to_availability", {
            "change_id": change_id,
            "identity_ref_id": identity_ref_id,
            "steps_executed": executed,
        }, change_id)
        return {
            "change_id": change_id,
            "target": "availability",
            "identity_ref_id": identity_ref_id,
            "steps_executed": executed,
        }

    def apply_change_to_financials(
        self,
        change_id: str,
        *,
        budget_ref_id: str = "",
        action: str = "update",
    ) -> dict[str, Any]:
        """Execute change steps targeting financial subsystem."""
        steps = self._change.get_steps(change_id)
        executed = 0
        for step in steps:
            if step.status == ChangeStatus.DRAFT:
                self._change.execute_change_step(change_id, step.step_id)
                executed += 1
        self._change.collect_evidence(
            change_id, ChangeEvidenceKind.LOG_ENTRY,
            description=f"Applied to financials {budget_ref_id}: {action}",
        )
        _emit(self._events, "change_applied_to_financials", {
            "change_id": change_id,
            "budget_ref_id": budget_ref_id,
            "steps_executed": executed,
        }, change_id)
        return {
            "change_id": change_id,
            "target": "financials",
            "budget_ref_id": budget_ref_id,
            "steps_executed": executed,
        }

    def apply_change_to_connector_routing(
        self,
        change_id: str,
        *,
        connector_ref_id: str = "",
        action: str = "update",
    ) -> dict[str, Any]:
        """Execute change steps targeting connector routing subsystem."""
        steps = self._change.get_steps(change_id)
        executed = 0
        for step in steps:
            if step.status == ChangeStatus.DRAFT:
                self._change.execute_change_step(change_id, step.step_id)
                executed += 1
        self._change.collect_evidence(
            change_id, ChangeEvidenceKind.LOG_ENTRY,
            description=f"Applied to connector routing {connector_ref_id}: {action}",
        )
        _emit(self._events, "change_applied_to_connector_routing", {
            "change_id": change_id,
            "connector_ref_id": connector_ref_id,
            "steps_executed": executed,
        }, change_id)
        return {
            "change_id": change_id,
            "target": "connector_routing",
            "connector_ref_id": connector_ref_id,
            "steps_executed": executed,
        }

    def apply_change_to_domain_pack_resolution(
        self,
        change_id: str,
        *,
        domain_pack_ref_id: str = "",
        action: str = "update",
    ) -> dict[str, Any]:
        """Execute change steps targeting domain pack resolution subsystem."""
        steps = self._change.get_steps(change_id)
        executed = 0
        for step in steps:
            if step.status == ChangeStatus.DRAFT:
                self._change.execute_change_step(change_id, step.step_id)
                executed += 1
        self._change.collect_evidence(
            change_id, ChangeEvidenceKind.LOG_ENTRY,
            description=f"Applied to domain pack {domain_pack_ref_id}: {action}",
        )
        _emit(self._events, "change_applied_to_domain_pack", {
            "change_id": change_id,
            "domain_pack_ref_id": domain_pack_ref_id,
            "steps_executed": executed,
        }, change_id)
        return {
            "change_id": change_id,
            "target": "domain_pack",
            "domain_pack_ref_id": domain_pack_ref_id,
            "steps_executed": executed,
        }

    # ------------------------------------------------------------------
    # Memory mesh and graph attachment
    # ------------------------------------------------------------------

    def attach_change_to_memory_mesh(
        self,
        scope_ref_id: str,
    ) -> MemoryRecord:
        """Persist change state to memory mesh."""
        now = _now_iso()

        content: dict[str, Any] = {
            "scope_ref_id": scope_ref_id,
            "total_changes": self._change.change_count,
            "total_plans": self._change.plan_count,
            "total_outcomes": self._change.outcome_count,
        }

        mem = MemoryRecord(
            memory_id=stable_identifier("mem-chg", {"id": scope_ref_id}),
            memory_type=MemoryType.OBSERVATION,
            scope=MemoryScope.GLOBAL,
            scope_ref_id=scope_ref_id,
            trust_level=MemoryTrustLevel.VERIFIED,
            title=f"Change state: {scope_ref_id}",
            content=content,
            source_ids=(scope_ref_id,),
            tags=("change", "controlled", "state"),
            confidence=1.0,
            created_at=now,
            updated_at=now,
        )
        self._memory.add_memory(mem)

        _emit(self._events, "change_attached_to_memory", {
            "scope_ref_id": scope_ref_id,
            "memory_id": mem.memory_id,
        }, scope_ref_id)
        return mem

    def attach_change_to_graph(
        self,
        scope_ref_id: str,
    ) -> dict[str, Any]:
        """Return change state suitable for operational graph consumption."""
        return {
            "scope_ref_id": scope_ref_id,
            "total_changes": self._change.change_count,
            "total_plans": self._change.plan_count,
            "total_outcomes": self._change.outcome_count,
        }
