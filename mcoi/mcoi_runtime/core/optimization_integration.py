"""Purpose: optimization / recommendation integration bridge.
Governance scope: composing optimization engine with reporting, financials,
    portfolio, availability, connectors, faults, memory mesh, and
    operational graph.
Dependencies: optimization_runtime engine, event_spine, memory_mesh,
    core invariants.
Invariants:
  - Every optimization operation emits events.
  - Recommendation state is attached to memory mesh.
  - All returns are immutable.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ..contracts.event import EventRecord, EventSource, EventType
from ..contracts.memory_mesh import (
    MemoryRecord,
    MemoryScope,
    MemoryTrustLevel,
    MemoryType,
)
from ..contracts.optimization_runtime import (
    OptimizationScope,
    OptimizationStrategy,
    OptimizationTarget,
    RecommendationDisposition,
)
from .event_spine import EventSpineEngine
from .invariants import RuntimeCoreInvariantError, stable_identifier
from .memory_mesh import MemoryMeshEngine
from .optimization_runtime import OptimizationRuntimeEngine


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _emit(es: EventSpineEngine, action: str, payload: dict, cid: str) -> EventRecord:
    now = _now_iso()
    payload["action"] = action
    event = EventRecord(
        event_id=stable_identifier("evt-oint", {"action": action, "ts": now, "cid": cid}),
        event_type=EventType.CUSTOM,
        source=EventSource.COMMUNICATION_SYSTEM,
        correlation_id=cid,
        payload=payload,
        emitted_at=now,
    )
    es.emit(event)
    return event


class OptimizationIntegration:
    """Integration bridge for optimization with all platform layers."""

    def __init__(
        self,
        optimization_engine: OptimizationRuntimeEngine,
        event_spine: EventSpineEngine,
        memory_engine: MemoryMeshEngine,
    ) -> None:
        if not isinstance(optimization_engine, OptimizationRuntimeEngine):
            raise RuntimeCoreInvariantError("optimization_engine must be an OptimizationRuntimeEngine")
        if not isinstance(event_spine, EventSpineEngine):
            raise RuntimeCoreInvariantError("event_spine must be an EventSpineEngine")
        if not isinstance(memory_engine, MemoryMeshEngine):
            raise RuntimeCoreInvariantError("memory_engine must be a MemoryMeshEngine")
        self._optimization = optimization_engine
        self._events = event_spine
        self._memory = memory_engine

    # ------------------------------------------------------------------
    # Reporting-driven recommendations
    # ------------------------------------------------------------------

    def recommend_from_reporting(
        self,
        request_id: str,
        *,
        connector_metrics: list[dict[str, Any]] | None = None,
        campaign_metrics: list[dict[str, Any]] | None = None,
        budget_metrics: list[dict[str, Any]] | None = None,
        strategy: OptimizationStrategy = OptimizationStrategy.BALANCED,
    ) -> dict[str, Any]:
        """Generate recommendations from executive reporting data."""
        req = self._optimization.create_request(
            request_id, OptimizationTarget.CONNECTOR_SELECTION,
            strategy=strategy,
        )
        total_recs = 0

        if connector_metrics:
            recs = self._optimization.optimize_connectors(request_id, connector_metrics)
            total_recs += len(recs)
        if campaign_metrics:
            recs = self._optimization.optimize_campaigns(request_id, campaign_metrics)
            total_recs += len(recs)
        if budget_metrics:
            recs = self._optimization.optimize_budget_allocation(request_id, budget_metrics)
            total_recs += len(recs)

        _emit(self._events, "recommend_from_reporting", {
            "request_id": request_id,
            "total_recommendations": total_recs,
        }, request_id)
        return {
            "request_id": request_id,
            "source": "reporting",
            "total_recommendations": total_recs,
            "strategy": strategy.value,
        }

    # ------------------------------------------------------------------
    # Financial-driven recommendations
    # ------------------------------------------------------------------

    def recommend_from_financials(
        self,
        request_id: str,
        budget_metrics: list[dict[str, Any]],
        *,
        strategy: OptimizationStrategy = OptimizationStrategy.COST_MINIMIZATION,
    ) -> dict[str, Any]:
        """Generate recommendations from financial/budget data."""
        self._optimization.create_request(
            request_id, OptimizationTarget.BUDGET_ALLOCATION,
            strategy=strategy,
        )
        recs = self._optimization.optimize_budget_allocation(request_id, budget_metrics)
        _emit(self._events, "recommend_from_financials", {
            "request_id": request_id,
            "recommendations": len(recs),
        }, request_id)
        return {
            "request_id": request_id,
            "source": "financials",
            "total_recommendations": len(recs),
            "strategy": strategy.value,
        }

    # ------------------------------------------------------------------
    # Portfolio-driven recommendations
    # ------------------------------------------------------------------

    def recommend_from_portfolio(
        self,
        request_id: str,
        campaign_metrics: list[dict[str, Any]],
        *,
        strategy: OptimizationStrategy = OptimizationStrategy.BALANCED,
    ) -> dict[str, Any]:
        """Generate recommendations from portfolio data."""
        self._optimization.create_request(
            request_id, OptimizationTarget.PORTFOLIO_BALANCE,
            strategy=strategy,
        )
        recs = self._optimization.optimize_portfolio(request_id, campaign_metrics)
        _emit(self._events, "recommend_from_portfolio", {
            "request_id": request_id,
            "recommendations": len(recs),
        }, request_id)
        return {
            "request_id": request_id,
            "source": "portfolio",
            "total_recommendations": len(recs),
            "strategy": strategy.value,
        }

    # ------------------------------------------------------------------
    # Availability-driven recommendations
    # ------------------------------------------------------------------

    def recommend_from_availability(
        self,
        request_id: str,
        schedule_metrics: list[dict[str, Any]],
        campaign_metrics: list[dict[str, Any]] | None = None,
        *,
        strategy: OptimizationStrategy = OptimizationStrategy.BALANCED,
    ) -> dict[str, Any]:
        """Generate recommendations from availability/schedule data."""
        self._optimization.create_request(
            request_id, OptimizationTarget.SCHEDULE_EFFICIENCY,
            strategy=strategy,
        )
        total_recs = 0
        recs = self._optimization.optimize_schedule(request_id, schedule_metrics)
        total_recs += len(recs)

        if campaign_metrics:
            crecs = self._optimization.optimize_campaigns(request_id, campaign_metrics)
            total_recs += len(crecs)

        _emit(self._events, "recommend_from_availability", {
            "request_id": request_id,
            "recommendations": total_recs,
        }, request_id)
        return {
            "request_id": request_id,
            "source": "availability",
            "total_recommendations": total_recs,
            "strategy": strategy.value,
        }

    # ------------------------------------------------------------------
    # Connector-driven recommendations
    # ------------------------------------------------------------------

    def recommend_from_connectors(
        self,
        request_id: str,
        connector_metrics: list[dict[str, Any]],
        *,
        strategy: OptimizationStrategy = OptimizationStrategy.RELIABILITY_MAXIMIZATION,
    ) -> dict[str, Any]:
        """Generate recommendations from connector performance data."""
        self._optimization.create_request(
            request_id, OptimizationTarget.CONNECTOR_SELECTION,
            strategy=strategy,
        )
        recs = self._optimization.optimize_connectors(request_id, connector_metrics)
        _emit(self._events, "recommend_from_connectors", {
            "request_id": request_id,
            "recommendations": len(recs),
        }, request_id)
        return {
            "request_id": request_id,
            "source": "connectors",
            "total_recommendations": len(recs),
            "strategy": strategy.value,
        }

    # ------------------------------------------------------------------
    # Fault-driven recommendations
    # ------------------------------------------------------------------

    def recommend_from_faults(
        self,
        request_id: str,
        domain_metrics: list[dict[str, Any]],
        escalation_metrics: list[dict[str, Any]] | None = None,
        *,
        strategy: OptimizationStrategy = OptimizationStrategy.RELIABILITY_MAXIMIZATION,
    ) -> dict[str, Any]:
        """Generate recommendations from fault injection/drill data."""
        self._optimization.create_request(
            request_id, OptimizationTarget.FAULT_AVOIDANCE,
            strategy=strategy,
        )
        total_recs = 0
        recs = self._optimization.optimize_domain_pack_selection(request_id, domain_metrics)
        total_recs += len(recs)

        if escalation_metrics:
            erecs = self._optimization.optimize_escalation(request_id, escalation_metrics)
            total_recs += len(erecs)

        _emit(self._events, "recommend_from_faults", {
            "request_id": request_id,
            "recommendations": total_recs,
        }, request_id)
        return {
            "request_id": request_id,
            "source": "faults",
            "total_recommendations": total_recs,
            "strategy": strategy.value,
        }

    # ------------------------------------------------------------------
    # Plan and decision helpers
    # ------------------------------------------------------------------

    def build_and_decide_plan(
        self,
        plan_id: str,
        request_id: str,
        title: str,
        *,
        disposition: RecommendationDisposition = RecommendationDisposition.PENDING,
        decided_by: str = "",
        reason: str = "",
    ) -> dict[str, Any]:
        """Build a plan and optionally decide on all recommendations."""
        plan = self._optimization.build_plan(plan_id, request_id, title)
        decisions = []

        if disposition != RecommendationDisposition.PENDING:
            for i, rec_id in enumerate(plan.recommendation_ids):
                dec = self._optimization.decide_recommendation(
                    f"{plan_id}-dec-{i}",
                    rec_id,
                    disposition,
                    decided_by=decided_by,
                    reason=reason,
                )
                decisions.append(dec.decision_id)

        _emit(self._events, "plan_built_and_decided", {
            "plan_id": plan_id,
            "request_id": request_id,
            "recommendations": len(plan.recommendation_ids),
            "decisions": len(decisions),
        }, plan_id)
        return {
            "plan_id": plan_id,
            "request_id": request_id,
            "title": title,
            "recommendation_count": len(plan.recommendation_ids),
            "decision_count": len(decisions),
            "disposition": disposition.value,
            "feasible": plan.feasible,
            "total_estimated_improvement_pct": plan.total_estimated_improvement_pct,
        }

    # ------------------------------------------------------------------
    # Memory mesh and graph attachment
    # ------------------------------------------------------------------

    def attach_recommendations_to_memory_mesh(
        self,
        scope_ref_id: str,
    ) -> MemoryRecord:
        """Persist optimization state to memory mesh."""
        now = _now_iso()

        all_recs = self._optimization.get_all_recommendations()
        content: dict[str, Any] = {
            "scope_ref_id": scope_ref_id,
            "total_requests": self._optimization.request_count,
            "total_recommendations": self._optimization.recommendation_count,
            "total_plans": self._optimization.plan_count,
            "recommendation_targets": list(set(
                r.target.value for r in all_recs
            )),
        }

        mem = MemoryRecord(
            memory_id=stable_identifier("mem-opt", {"id": scope_ref_id}),
            memory_type=MemoryType.OBSERVATION,
            scope=MemoryScope.GLOBAL,
            scope_ref_id=scope_ref_id,
            trust_level=MemoryTrustLevel.VERIFIED,
            title="Optimization state",
            content=content,
            source_ids=(scope_ref_id,),
            tags=("optimization", "recommendations", "state"),
            confidence=1.0,
            created_at=now,
            updated_at=now,
        )
        self._memory.add_memory(mem)

        _emit(self._events, "recommendations_attached_to_memory", {
            "scope_ref_id": scope_ref_id,
            "memory_id": mem.memory_id,
        }, scope_ref_id)
        return mem

    def attach_recommendations_to_graph(
        self,
        scope_ref_id: str,
    ) -> dict[str, Any]:
        """Return optimization state suitable for operational graph consumption."""
        all_recs = self._optimization.get_all_recommendations()

        # Group by target
        by_target: dict[str, int] = {}
        for r in all_recs:
            key = r.target.value
            by_target[key] = by_target.get(key, 0) + 1

        return {
            "scope_ref_id": scope_ref_id,
            "total_requests": self._optimization.request_count,
            "total_recommendations": self._optimization.recommendation_count,
            "total_plans": self._optimization.plan_count,
            "recommendations_by_target": by_target,
        }
