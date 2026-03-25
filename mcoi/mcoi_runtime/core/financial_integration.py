"""Purpose: financial integration bridge.
Governance scope: composing budget decisions with campaigns, connectors,
    communication, artifacts, provider routing, governance, portfolio
    scheduling, memory mesh, and operational graph.
Dependencies: financial_runtime engine, event_spine, memory_mesh,
    core invariants.
Invariants:
  - Every financial operation emits events.
  - Financial state is attached to memory mesh.
  - All returns are immutable.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ..contracts.event import EventRecord, EventSource, EventType
from ..contracts.financial_runtime import (
    BudgetDecision,
    BudgetScope,
    ChargeDisposition,
    CostCategory,
    SpendRecord,
)
from ..contracts.memory_mesh import (
    MemoryRecord,
    MemoryScope,
    MemoryTrustLevel,
    MemoryType,
)
from .event_spine import EventSpineEngine
from .financial_runtime import FinancialRuntimeEngine
from .invariants import RuntimeCoreInvariantError, stable_identifier
from .memory_mesh import MemoryMeshEngine


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _emit(es: EventSpineEngine, action: str, payload: dict, cid: str) -> EventRecord:
    now = _now_iso()
    payload["action"] = action
    event = EventRecord(
        event_id=stable_identifier("evt-fint", {"action": action, "ts": now, "cid": cid}),
        event_type=EventType.CUSTOM,
        source=EventSource.COMMUNICATION_SYSTEM,
        correlation_id=cid,
        payload=payload,
        emitted_at=now,
    )
    es.emit(event)
    return event


class FinancialIntegration:
    """Integration bridge for financial runtime with all platform layers."""

    def __init__(
        self,
        financial_engine: FinancialRuntimeEngine,
        event_spine: EventSpineEngine,
        memory_engine: MemoryMeshEngine,
    ) -> None:
        if not isinstance(financial_engine, FinancialRuntimeEngine):
            raise RuntimeCoreInvariantError("financial_engine must be a FinancialRuntimeEngine")
        if not isinstance(event_spine, EventSpineEngine):
            raise RuntimeCoreInvariantError("event_spine must be an EventSpineEngine")
        if not isinstance(memory_engine, MemoryMeshEngine):
            raise RuntimeCoreInvariantError("memory_engine must be a MemoryMeshEngine")
        self._finance = financial_engine
        self._events = event_spine
        self._memory = memory_engine

    # ------------------------------------------------------------------
    # Campaign step reservation
    # ------------------------------------------------------------------

    def reserve_for_campaign_step(
        self,
        budget_id: str,
        campaign_ref: str,
        step_ref: str,
        estimated_amount: float,
        *,
        category: CostCategory = CostCategory.CONNECTOR_CALL,
    ) -> dict[str, Any]:
        """Reserve budget for a campaign step."""
        reservation_id = stable_identifier("res-step", {
            "bid": budget_id, "camp": campaign_ref, "step": step_ref,
        })
        decision = self._finance.reserve_budget(
            reservation_id, budget_id, estimated_amount, category,
            campaign_ref=campaign_ref, step_ref=step_ref,
            reason=f"campaign step: {step_ref}",
        )
        result: dict[str, Any] = {
            "budget_id": budget_id,
            "campaign_ref": campaign_ref,
            "step_ref": step_ref,
            "reservation_id": reservation_id if decision.disposition in (
                ChargeDisposition.APPROVED, ChargeDisposition.WARNING_ISSUED,
            ) else "",
            "disposition": decision.disposition.value,
            "requested_amount": estimated_amount,
            "available_amount": decision.available_amount,
            "reason": decision.reason,
            "approved": decision.disposition in (
                ChargeDisposition.APPROVED, ChargeDisposition.WARNING_ISSUED,
            ),
            "approval_required": decision.approval_required,
        }
        _emit(self._events, "campaign_step_budget_check", {
            "budget_id": budget_id,
            "campaign_ref": campaign_ref,
            "step_ref": step_ref,
            "disposition": decision.disposition.value,
        }, campaign_ref)
        return result

    # ------------------------------------------------------------------
    # Connector call reservation
    # ------------------------------------------------------------------

    def reserve_for_connector_call(
        self,
        budget_id: str,
        connector_ref: str,
        *,
        campaign_ref: str = "",
        step_ref: str = "",
        units: int = 1,
    ) -> dict[str, Any]:
        """Reserve budget for an external connector call."""
        estimate = self._finance.estimate_cost(
            stable_identifier("est-conn", {"conn": connector_ref, "bid": budget_id}),
            CostCategory.CONNECTOR_CALL,
            connector_ref=connector_ref,
            campaign_ref=campaign_ref,
            step_ref=step_ref,
            units=units,
        )

        reservation_id = stable_identifier("res-conn", {
            "bid": budget_id, "conn": connector_ref, "step": step_ref,
        })
        decision = self._finance.reserve_budget(
            reservation_id, budget_id, estimate.estimated_amount,
            CostCategory.CONNECTOR_CALL,
            connector_ref=connector_ref,
            campaign_ref=campaign_ref,
            step_ref=step_ref,
            reason=f"connector call: {connector_ref}",
        )

        result: dict[str, Any] = {
            "budget_id": budget_id,
            "connector_ref": connector_ref,
            "estimated_amount": estimate.estimated_amount,
            "reservation_id": reservation_id if decision.disposition in (
                ChargeDisposition.APPROVED, ChargeDisposition.WARNING_ISSUED,
            ) else "",
            "disposition": decision.disposition.value,
            "available_amount": decision.available_amount,
            "reason": decision.reason,
            "approved": decision.disposition in (
                ChargeDisposition.APPROVED, ChargeDisposition.WARNING_ISSUED,
            ),
        }
        _emit(self._events, "connector_budget_check", {
            "budget_id": budget_id,
            "connector_ref": connector_ref,
            "disposition": decision.disposition.value,
        }, connector_ref)
        return result

    # ------------------------------------------------------------------
    # Communication reservation
    # ------------------------------------------------------------------

    def reserve_for_communication(
        self,
        budget_id: str,
        channel: str,
        estimated_amount: float,
        *,
        campaign_ref: str = "",
    ) -> dict[str, Any]:
        """Reserve budget for a communication action."""
        reservation_id = stable_identifier("res-comm", {
            "bid": budget_id, "ch": channel, "camp": campaign_ref,
        })
        decision = self._finance.reserve_budget(
            reservation_id, budget_id, estimated_amount,
            CostCategory.COMMUNICATION,
            campaign_ref=campaign_ref,
            reason=f"communication via {channel}",
        )
        return {
            "budget_id": budget_id,
            "channel": channel,
            "reservation_id": reservation_id if decision.disposition in (
                ChargeDisposition.APPROVED, ChargeDisposition.WARNING_ISSUED,
            ) else "",
            "disposition": decision.disposition.value,
            "approved": decision.disposition in (
                ChargeDisposition.APPROVED, ChargeDisposition.WARNING_ISSUED,
            ),
            "reason": decision.reason,
        }

    # ------------------------------------------------------------------
    # Artifact parsing reservation
    # ------------------------------------------------------------------

    def reserve_for_artifact_parsing(
        self,
        budget_id: str,
        artifact_ref: str,
        estimated_amount: float,
        *,
        campaign_ref: str = "",
    ) -> dict[str, Any]:
        """Reserve budget for artifact parsing."""
        reservation_id = stable_identifier("res-art", {
            "bid": budget_id, "art": artifact_ref,
        })
        decision = self._finance.reserve_budget(
            reservation_id, budget_id, estimated_amount,
            CostCategory.ARTIFACT_PARSING,
            campaign_ref=campaign_ref,
            reason=f"artifact parsing: {artifact_ref}",
        )
        return {
            "budget_id": budget_id,
            "artifact_ref": artifact_ref,
            "reservation_id": reservation_id if decision.disposition in (
                ChargeDisposition.APPROVED, ChargeDisposition.WARNING_ISSUED,
            ) else "",
            "disposition": decision.disposition.value,
            "approved": decision.disposition in (
                ChargeDisposition.APPROVED, ChargeDisposition.WARNING_ISSUED,
            ),
            "reason": decision.reason,
        }

    # ------------------------------------------------------------------
    # Provider routing reservation
    # ------------------------------------------------------------------

    def reserve_for_provider_routing(
        self,
        budget_id: str,
        provider_ref: str,
        estimated_amount: float,
        *,
        campaign_ref: str = "",
    ) -> dict[str, Any]:
        """Reserve budget for provider routing."""
        reservation_id = stable_identifier("res-prov", {
            "bid": budget_id, "prov": provider_ref,
        })
        decision = self._finance.reserve_budget(
            reservation_id, budget_id, estimated_amount,
            CostCategory.PROVIDER_ROUTING,
            campaign_ref=campaign_ref,
            reason=f"provider routing: {provider_ref}",
        )
        return {
            "budget_id": budget_id,
            "provider_ref": provider_ref,
            "reservation_id": reservation_id if decision.disposition in (
                ChargeDisposition.APPROVED, ChargeDisposition.WARNING_ISSUED,
            ) else "",
            "disposition": decision.disposition.value,
            "approved": decision.disposition in (
                ChargeDisposition.APPROVED, ChargeDisposition.WARNING_ISSUED,
            ),
            "reason": decision.reason,
        }

    # ------------------------------------------------------------------
    # Campaign budget binding
    # ------------------------------------------------------------------

    def bind_budget_to_campaign(
        self,
        budget_id: str,
        campaign_id: str,
        allocated_amount: float,
    ) -> dict[str, Any]:
        """Bind a budget envelope to a campaign."""
        binding_id = stable_identifier("bind", {
            "bid": budget_id, "camp": campaign_id,
        })
        binding = self._finance.bind_campaign_budget(
            binding_id, campaign_id, budget_id, allocated_amount,
        )
        _emit(self._events, "budget_campaign_bound", {
            "budget_id": budget_id,
            "campaign_id": campaign_id,
            "allocated_amount": allocated_amount,
        }, campaign_id)
        return {
            "binding_id": binding.binding_id,
            "budget_id": budget_id,
            "campaign_id": campaign_id,
            "allocated_amount": allocated_amount,
            "currency": binding.currency,
        }

    # ------------------------------------------------------------------
    # Budget gates for governance and portfolio
    # ------------------------------------------------------------------

    def budget_gate_for_governance(
        self,
        budget_id: str,
        requested_amount: float,
        action_description: str = "",
    ) -> dict[str, Any]:
        """Check if a governance action is budget-allowed."""
        decision = self._finance.budget_gate(budget_id, requested_amount)
        result: dict[str, Any] = {
            "budget_id": budget_id,
            "action_description": action_description,
            "disposition": decision.disposition.value,
            "allowed": decision.disposition in (
                ChargeDisposition.APPROVED, ChargeDisposition.WARNING_ISSUED,
            ),
            "requested_amount": requested_amount,
            "available_amount": decision.available_amount,
            "reason": decision.reason,
            "approval_required": decision.approval_required,
        }
        _emit(self._events, "governance_budget_gate", {
            "budget_id": budget_id,
            "disposition": decision.disposition.value,
            "action": action_description,
        }, budget_id)
        return result

    def budget_gate_for_portfolio(
        self,
        budget_id: str,
        campaign_ids: list[str],
        estimated_amounts: list[float],
    ) -> dict[str, Any]:
        """Check if portfolio scheduling is budget-feasible for multiple campaigns."""
        if len(campaign_ids) != len(estimated_amounts):
            raise RuntimeCoreInvariantError(
                "campaign_ids and estimated_amounts must have the same length"
            )

        total_requested = sum(estimated_amounts)
        decision = self._finance.budget_gate(budget_id, total_requested)

        per_campaign: list[dict[str, Any]] = []
        for cid, amt in zip(campaign_ids, estimated_amounts):
            per_campaign.append({
                "campaign_id": cid,
                "estimated_amount": amt,
            })

        result: dict[str, Any] = {
            "budget_id": budget_id,
            "total_requested": total_requested,
            "disposition": decision.disposition.value,
            "all_feasible": decision.disposition in (
                ChargeDisposition.APPROVED, ChargeDisposition.WARNING_ISSUED,
            ),
            "available_amount": decision.available_amount,
            "reason": decision.reason,
            "per_campaign": per_campaign,
            "approval_required": decision.approval_required,
        }
        _emit(self._events, "portfolio_budget_gate", {
            "budget_id": budget_id,
            "total_requested": total_requested,
            "disposition": decision.disposition.value,
            "campaign_count": len(campaign_ids),
        }, budget_id)
        return result

    # ------------------------------------------------------------------
    # Memory mesh and graph attachment
    # ------------------------------------------------------------------

    def attach_financial_record_to_memory_mesh(
        self, budget_id: str,
    ) -> MemoryRecord:
        """Persist financial state to memory mesh."""
        health = self._finance.budget_health(budget_id)
        now = _now_iso()

        content: dict[str, Any] = {
            "budget_id": budget_id,
            "limit_amount": health.limit_amount,
            "consumed_amount": health.consumed_amount,
            "reserved_amount": health.reserved_amount,
            "available_amount": health.available_amount,
            "utilization": health.utilization,
            "currency": health.currency,
            "warning_triggered": health.warning_triggered,
            "hard_stop_triggered": health.hard_stop_triggered,
            "active_reservations": health.active_reservations,
            "total_spend_records": health.total_spend_records,
        }

        mem = MemoryRecord(
            memory_id=stable_identifier("mem-fin", {"id": budget_id}),
            memory_type=MemoryType.OBSERVATION,
            scope=MemoryScope.GLOBAL,
            scope_ref_id=budget_id,
            trust_level=MemoryTrustLevel.VERIFIED,
            title=f"Financial state: {budget_id}",
            content=content,
            source_ids=(budget_id,),
            tags=("financial", "budget", "state"),
            confidence=1.0,
            created_at=now,
            updated_at=now,
        )
        self._memory.add_memory(mem)

        _emit(self._events, "financial_attached_to_memory", {
            "budget_id": budget_id,
            "memory_id": mem.memory_id,
        }, budget_id)
        return mem

    def attach_financial_record_to_graph(
        self, budget_id: str,
    ) -> dict[str, Any]:
        """Return financial state suitable for operational graph consumption."""
        health = self._finance.budget_health(budget_id)
        budget = self._finance.get_budget(budget_id)
        conflicts = self._finance.find_budget_conflicts(budget_id)
        bindings = self._finance.get_bindings_for_budget(budget_id)
        active_res = self._finance.get_active_reservations(budget_id)

        result: dict[str, Any] = {
            "budget_id": budget_id,
            "name": budget.name if budget else "",
            "scope": budget.scope.value if budget else "",
            "limit_amount": health.limit_amount,
            "consumed_amount": health.consumed_amount,
            "reserved_amount": health.reserved_amount,
            "available_amount": health.available_amount,
            "utilization": health.utilization,
            "currency": health.currency,
            "active": budget.active if budget else False,
            "warning_triggered": health.warning_triggered,
            "hard_stop_triggered": health.hard_stop_triggered,
            "conflicts": len(conflicts),
            "bindings": len(bindings),
            "active_reservations": len(active_res),
        }
        return result
