"""Purpose: portfolio integration bridge.
Governance scope: composing campaign scheduling with work campaigns, jobs,
    teams/functions, contact identity, communication surface, external connectors,
    supervisor, and memory mesh into portfolio-level coordination.
Dependencies: portfolio engine, work_campaign engine/integration, event_spine,
    memory_mesh, core invariants.
Invariants:
  - Every portfolio operation emits events.
  - Portfolio state is attached to memory mesh.
  - All returns are immutable.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ..contracts.portfolio import (
    CampaignReservation,
    CapacitySnapshot,
    PortfolioClosureReport,
    PortfolioDescriptor,
    PortfolioHealth,
    PortfolioPriority,
    PortfolioStatus,
    PreemptionPolicy,
    PreemptionRecord,
    QuotaReservation,
    ResourceClass,
    ResourceReservation,
    ReservationType,
    SchedulingDecision,
    SchedulingMode,
    SchedulingVerdict,
)
from ..contracts.work_campaign import (
    CampaignPriority,
    CampaignStatus,
)
from ..contracts.event import EventRecord, EventSource, EventType
from ..contracts.memory_mesh import (
    MemoryRecord,
    MemoryScope,
    MemoryTrustLevel,
    MemoryType,
)
from .portfolio import PortfolioEngine
from .work_campaign import WorkCampaignEngine
from .work_campaign_integration import WorkCampaignIntegration
from .event_spine import EventSpineEngine
from .memory_mesh import MemoryMeshEngine
from .invariants import RuntimeCoreInvariantError, stable_identifier


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


class PortfolioIntegration:
    """Integration bridge for portfolio scheduling with all platform layers."""

    def __init__(
        self,
        portfolio_engine: PortfolioEngine,
        campaign_engine: WorkCampaignEngine,
        campaign_integration: WorkCampaignIntegration,
        event_spine: EventSpineEngine,
        memory_engine: MemoryMeshEngine,
    ) -> None:
        if not isinstance(portfolio_engine, PortfolioEngine):
            raise RuntimeCoreInvariantError(
                "portfolio_engine must be a PortfolioEngine"
            )
        if not isinstance(campaign_engine, WorkCampaignEngine):
            raise RuntimeCoreInvariantError(
                "campaign_engine must be a WorkCampaignEngine"
            )
        if not isinstance(campaign_integration, WorkCampaignIntegration):
            raise RuntimeCoreInvariantError(
                "campaign_integration must be a WorkCampaignIntegration"
            )
        if not isinstance(event_spine, EventSpineEngine):
            raise RuntimeCoreInvariantError(
                "event_spine must be an EventSpineEngine"
            )
        if not isinstance(memory_engine, MemoryMeshEngine):
            raise RuntimeCoreInvariantError(
                "memory_engine must be a MemoryMeshEngine"
            )
        self._portfolio = portfolio_engine
        self._campaigns = campaign_engine
        self._campaign_integ = campaign_integration
        self._events = event_spine
        self._memory = memory_engine

    # ------------------------------------------------------------------
    # Campaign scheduling
    # ------------------------------------------------------------------

    def schedule_campaign_run(
        self,
        portfolio_id: str,
        campaign_id: str,
        *,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Schedule and optionally run a campaign within the portfolio."""
        decision = self._portfolio.schedule_next(portfolio_id)

        if decision.verdict == SchedulingVerdict.SCHEDULED:
            # Run the campaign
            result = self._campaign_integ.run_campaign(
                decision.campaign_id, context=context,
            )
            _emit(self._events, "portfolio_campaign_run", {
                "portfolio_id": portfolio_id,
                "campaign_id": decision.campaign_id,
                "verdict": decision.verdict.value,
            }, portfolio_id)

            return {
                "decision": decision,
                "run_result": result,
            }

        _emit(self._events, "portfolio_campaign_not_run", {
            "portfolio_id": portfolio_id,
            "campaign_id": decision.campaign_id,
            "verdict": decision.verdict.value,
            "reason": decision.reason,
        }, portfolio_id)

        return {
            "decision": decision,
            "run_result": None,
        }

    def schedule_from_goal(
        self,
        portfolio_id: str,
        goal_id: str,
        campaign_id: str,
        *,
        priority: CampaignPriority = CampaignPriority.NORMAL,
        deadline: str = "",
    ) -> dict[str, Any]:
        """Register and schedule a campaign derived from a goal."""
        res = self._portfolio.register_campaign(
            portfolio_id, campaign_id, deadline=deadline,
        )
        decision = self._portfolio.schedule_next(portfolio_id)

        _emit(self._events, "portfolio_goal_scheduled", {
            "portfolio_id": portfolio_id,
            "goal_id": goal_id,
            "campaign_id": campaign_id,
        }, portfolio_id)

        return {
            "reservation": res,
            "decision": decision,
            "goal_id": goal_id,
        }

    def schedule_from_obligations(
        self,
        portfolio_id: str,
        obligation_ids: list[str],
        campaign_id: str,
        *,
        deadline: str = "",
        sla_seconds: int = 0,
    ) -> dict[str, Any]:
        """Register and schedule a campaign derived from obligations."""
        res = self._portfolio.register_campaign(
            portfolio_id, campaign_id,
            deadline=deadline, sla_seconds=sla_seconds,
        )
        decision = self._portfolio.schedule_next(portfolio_id)

        _emit(self._events, "portfolio_obligations_scheduled", {
            "portfolio_id": portfolio_id,
            "campaign_id": campaign_id,
            "obligation_count": len(obligation_ids),
        }, portfolio_id)

        return {
            "reservation": res,
            "decision": decision,
            "obligation_ids": obligation_ids,
        }

    # ------------------------------------------------------------------
    # Resource reservations
    # ------------------------------------------------------------------

    def reserve_connector_quota(
        self,
        portfolio_id: str,
        campaign_id: str,
        connector_id: str,
        units: int,
    ) -> QuotaReservation:
        """Reserve connector quota for a campaign."""
        return self._portfolio.reserve_quota(
            portfolio_id, campaign_id, connector_id, units,
        )

    def reserve_team_capacity(
        self,
        portfolio_id: str,
        campaign_id: str,
        team_ref: str,
        units: int = 1,
    ) -> ResourceReservation | None:
        """Reserve team capacity for a campaign."""
        return self._portfolio.reserve_resources(
            portfolio_id, campaign_id, team_ref,
            resource_class=ResourceClass.HUMAN,
            reservation_type=ReservationType.TEAM,
            units=units,
        )

    def reserve_function_capacity(
        self,
        portfolio_id: str,
        campaign_id: str,
        function_ref: str,
        units: int = 1,
    ) -> ResourceReservation | None:
        """Reserve function capacity for a campaign."""
        return self._portfolio.reserve_resources(
            portfolio_id, campaign_id, function_ref,
            resource_class=ResourceClass.SYSTEM,
            reservation_type=ReservationType.FUNCTION,
            units=units,
        )

    # ------------------------------------------------------------------
    # Campaign routing and escalation
    # ------------------------------------------------------------------

    def route_waiting_campaigns(
        self, portfolio_id: str,
    ) -> list[dict[str, Any]]:
        """Route waiting-on-human campaigns — check if they can proceed."""
        blocked = self._portfolio.blocked_campaigns(portfolio_id)
        results: list[dict[str, Any]] = []

        for res in blocked:
            if not res.waiting_on_human:
                continue

            # Check if campaign runs have moved past WAITING
            runs = self._campaigns.list_runs(
                res.campaign_id, status=CampaignStatus.WAITING,
            )
            if not runs:
                # No longer waiting — un-block
                self._portfolio._campaign_reservations[res.campaign_id] = CampaignReservation(
                    reservation_id=res.reservation_id,
                    portfolio_id=res.portfolio_id,
                    campaign_id=res.campaign_id,
                    priority_score=res.priority_score,
                    deadline=res.deadline,
                    sla_seconds=res.sla_seconds,
                    preemptible=res.preemptible,
                    waiting_on_human=False,
                    domain_pack_id=res.domain_pack_id,
                    scheduled=res.scheduled,
                    deferred=res.deferred,
                    deferred_reason=res.deferred_reason,
                    created_at=res.created_at,
                )
                results.append({
                    "campaign_id": res.campaign_id,
                    "action": "unblocked",
                })
            else:
                results.append({
                    "campaign_id": res.campaign_id,
                    "action": "still_waiting",
                    "waiting_runs": len(runs),
                })

        return results

    def escalate_unschedulable_campaigns(
        self, portfolio_id: str,
    ) -> list[dict[str, Any]]:
        """Escalate campaigns that cannot be scheduled."""
        portfolio = self._portfolio.get_portfolio(portfolio_id)
        escalated: list[dict[str, Any]] = []

        for cid in portfolio.campaign_ids:
            res = self._portfolio.get_campaign_reservation(cid)
            if not res or res.scheduled:
                continue

            # Check if deadline has passed
            if res.deadline:
                try:
                    dl = datetime.fromisoformat(res.deadline.replace("Z", "+00:00"))
                    if datetime.now(timezone.utc) > dl:
                        _emit(self._events, "portfolio_campaign_escalated", {
                            "portfolio_id": portfolio_id,
                            "campaign_id": cid,
                            "reason": "deadline_exceeded",
                        }, portfolio_id)
                        escalated.append({
                            "campaign_id": cid,
                            "reason": "deadline_exceeded",
                            "deadline": res.deadline,
                        })
                except (ValueError, TypeError):
                    pass

        return escalated

    # ------------------------------------------------------------------
    # Memory mesh attachment
    # ------------------------------------------------------------------

    def attach_portfolio_to_memory_mesh(
        self, portfolio_id: str,
    ) -> MemoryRecord:
        """Persist portfolio state to memory mesh."""
        portfolio = self._portfolio.get_portfolio(portfolio_id)
        health = self._portfolio.portfolio_health(portfolio_id)
        now = _now_iso()

        mem = MemoryRecord(
            memory_id=stable_identifier("mem-port", {
                "pid": portfolio_id, "ts": now,
            }),
            memory_type=MemoryType.OBSERVATION,
            scope=MemoryScope.GLOBAL,
            scope_ref_id=portfolio_id,
            trust_level=MemoryTrustLevel.VERIFIED,
            title=f"Portfolio state: {portfolio.name}",
            content={
                "portfolio_id": portfolio_id,
                "name": portfolio.name,
                "status": portfolio.status.value,
                "total_campaigns": health.total_campaigns,
                "active_campaigns": health.active_campaigns,
                "deferred_campaigns": health.deferred_campaigns,
                "blocked_campaigns": health.blocked_campaigns,
                "overdue_campaigns": health.overdue_campaigns,
                "utilization": health.utilization,
            },
            source_ids=(portfolio_id,),
            tags=("portfolio", "state"),
            confidence=1.0,
            created_at=now,
            updated_at=now,
        )
        self._memory.add_memory(mem)
        return mem

    def attach_portfolio_to_graph(
        self, portfolio_id: str,
    ) -> dict[str, Any]:
        """Return portfolio state suitable for operational graph consumption."""
        portfolio = self._portfolio.get_portfolio(portfolio_id)
        health = self._portfolio.portfolio_health(portfolio_id)
        snap = self._portfolio.capacity_snapshot(portfolio_id)
        decisions = self._portfolio.get_scheduling_decisions(portfolio_id)
        preemptions = self._portfolio.get_preemption_records(portfolio_id)

        return {
            "portfolio_id": portfolio_id,
            "name": portfolio.name,
            "status": portfolio.status.value,
            "scheduling_mode": portfolio.scheduling_mode.value,
            "preemption_policy": portfolio.preemption_policy.value,
            "campaign_count": len(portfolio.campaign_ids),
            "health": {
                "active": health.active_campaigns,
                "deferred": health.deferred_campaigns,
                "blocked": health.blocked_campaigns,
                "overdue": health.overdue_campaigns,
                "utilization": health.utilization,
            },
            "capacity": {
                "total_workers": snap.total_workers,
                "available_workers": snap.available_workers,
                "active_campaigns": snap.active_campaigns,
                "deferred_campaigns": snap.deferred_campaigns,
            },
            "decision_count": len(decisions),
            "preemption_count": len(preemptions),
        }
