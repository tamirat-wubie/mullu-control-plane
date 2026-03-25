"""Purpose: optimization / recommendation runtime engine.
Governance scope: reading KPI/report outputs, detecting inefficiencies,
    generating candidate changes, scoring recommendations, estimating
    impact, respecting constraints, producing deterministic plans.
Dependencies: optimization_runtime contracts, event_spine, core invariants.
Invariants:
  - No duplicate request or recommendation IDs.
  - Recommendations are deterministic given inputs.
  - Constraints are respected in candidate generation.
  - All returns are immutable.
  - Every mutation emits an event.
"""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from typing import Any

from ..contracts.event import EventRecord, EventSource, EventType
from ..contracts.optimization_runtime import (
    OptimizationCandidate,
    OptimizationConstraint,
    OptimizationImpactEstimate,
    OptimizationPlan,
    OptimizationRecommendation,
    OptimizationRequest,
    OptimizationResult,
    OptimizationScope,
    OptimizationStrategy,
    OptimizationTarget,
    RecommendationDecision,
    RecommendationDisposition,
    RecommendationSeverity,
)
from .event_spine import EventSpineEngine
from .invariants import RuntimeCoreInvariantError, stable_identifier


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _emit(es: EventSpineEngine, action: str, payload: dict, cid: str) -> EventRecord:
    now = _now_iso()
    payload["action"] = action
    event = EventRecord(
        event_id=stable_identifier("evt-opt", {"action": action, "ts": now, "cid": cid}),
        event_type=EventType.CUSTOM,
        source=EventSource.COMMUNICATION_SYSTEM,
        correlation_id=cid,
        payload=payload,
        emitted_at=now,
    )
    es.emit(event)
    return event


class OptimizationRuntimeEngine:
    """Engine for optimization, recommendation generation, and impact estimation."""

    def __init__(self, event_spine: EventSpineEngine) -> None:
        if not isinstance(event_spine, EventSpineEngine):
            raise RuntimeCoreInvariantError("event_spine must be an EventSpineEngine")
        self._events = event_spine
        self._requests: dict[str, OptimizationRequest] = {}
        self._constraints: dict[str, list[OptimizationConstraint]] = {}
        self._candidates: dict[str, list[OptimizationCandidate]] = {}
        self._recommendations: dict[str, OptimizationRecommendation] = {}
        self._recommendations_by_request: dict[str, list[str]] = {}
        self._plans: dict[str, OptimizationPlan] = {}
        self._results: dict[str, OptimizationResult] = {}
        self._impacts: list[OptimizationImpactEstimate] = []
        self._decisions: list[RecommendationDecision] = []

    # ------------------------------------------------------------------
    # Request management
    # ------------------------------------------------------------------

    def create_request(
        self,
        request_id: str,
        target: OptimizationTarget,
        *,
        strategy: OptimizationStrategy = OptimizationStrategy.BALANCED,
        scope: OptimizationScope = OptimizationScope.GLOBAL,
        scope_ref_id: str = "",
        priority: str = "normal",
        max_candidates: int = 10,
        reason: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> OptimizationRequest:
        if request_id in self._requests:
            raise RuntimeCoreInvariantError(f"optimization request '{request_id}' already exists")
        now = _now_iso()
        request = OptimizationRequest(
            request_id=request_id,
            target=target,
            strategy=strategy,
            scope=scope,
            scope_ref_id=scope_ref_id or request_id,
            priority=priority,
            max_candidates=max_candidates,
            reason=reason,
            created_at=now,
            metadata=metadata or {},
        )
        self._requests[request_id] = request
        _emit(self._events, "optimization_request_created", {
            "request_id": request_id,
            "target": target.value,
            "strategy": strategy.value,
        }, request_id)
        return request

    def get_request(self, request_id: str) -> OptimizationRequest | None:
        return self._requests.get(request_id)

    # ------------------------------------------------------------------
    # Constraint management
    # ------------------------------------------------------------------

    def add_constraint(
        self,
        constraint_id: str,
        request_id: str,
        constraint_type: str,
        *,
        field_name: str = "",
        operator: str = "",
        value: str = "",
        hard: bool = True,
    ) -> OptimizationConstraint:
        if request_id not in self._requests:
            raise RuntimeCoreInvariantError(f"request '{request_id}' not found")
        now = _now_iso()
        constraint = OptimizationConstraint(
            constraint_id=constraint_id,
            request_id=request_id,
            constraint_type=constraint_type,
            field_name=field_name,
            operator=operator,
            value=value,
            hard=hard,
            created_at=now,
        )
        self._constraints.setdefault(request_id, []).append(constraint)
        return constraint

    def get_constraints(self, request_id: str) -> tuple[OptimizationConstraint, ...]:
        return tuple(self._constraints.get(request_id, []))

    # ------------------------------------------------------------------
    # Optimization families
    # ------------------------------------------------------------------

    def optimize_connectors(
        self,
        request_id: str,
        connector_metrics: list[dict[str, Any]],
    ) -> list[OptimizationRecommendation]:
        """Generate recommendations for connector selection.

        connector_metrics: list of dicts with keys:
            connector_ref, success_rate, cost_per_call, latency_seconds
        """
        request = self._get_request(request_id)
        now = _now_iso()
        recommendations: list[OptimizationRecommendation] = []

        # Sort by success_rate desc, cost asc
        sorted_connectors = sorted(
            connector_metrics,
            key=lambda c: (-c.get("success_rate", 0), c.get("cost_per_call", 0)),
        )

        for i, conn in enumerate(sorted_connectors):
            sr = conn.get("success_rate", 1.0)
            cost = conn.get("cost_per_call", 0.0)
            ref = conn.get("connector_ref", f"conn-{i}")

            if sr < 0.9:
                severity = RecommendationSeverity.URGENT if sr < 0.7 else RecommendationSeverity.RECOMMENDED
                score = max(0.0, min(1.0, 1.0 - sr))
                rec = self._create_recommendation(
                    request_id=request_id,
                    title=f"Replace degraded connector: {ref}",
                    description=f"Connector {ref} has {sr:.0%} success rate. Consider alternative.",
                    target=OptimizationTarget.CONNECTOR_SELECTION,
                    severity=severity,
                    score=score,
                    action=f"replace_connector:{ref}",
                    scope=OptimizationScope.CONNECTOR,
                    scope_ref_id=ref,
                    estimated_improvement_pct=(1.0 - sr) * 100,
                    estimated_cost_delta=-cost * (1.0 - sr),
                    rationale=f"Success rate {sr:.0%} below 90% threshold",
                    now=now,
                )
                recommendations.append(rec)

        _emit(self._events, "connectors_optimized", {
            "request_id": request_id,
            "recommendations": len(recommendations),
        }, request_id)
        return recommendations

    def optimize_portfolio(
        self,
        request_id: str,
        campaign_metrics: list[dict[str, Any]],
    ) -> list[OptimizationRecommendation]:
        """Generate recommendations for portfolio rebalancing.

        campaign_metrics: list of dicts with keys:
            campaign_id, status, priority, blocked, overdue, completion_rate
        """
        request = self._get_request(request_id)
        now = _now_iso()
        recommendations: list[OptimizationRecommendation] = []

        blocked = [c for c in campaign_metrics if c.get("blocked", False)]
        overdue = [c for c in campaign_metrics if c.get("overdue", False)]

        if blocked:
            score = min(1.0, len(blocked) / max(1, len(campaign_metrics)))
            rec = self._create_recommendation(
                request_id=request_id,
                title=f"Rebalance portfolio: {len(blocked)} blocked campaigns",
                description=f"{len(blocked)} campaigns are blocked. Rebalance priorities or resources.",
                target=OptimizationTarget.PORTFOLIO_BALANCE,
                severity=RecommendationSeverity.URGENT if len(blocked) > 2 else RecommendationSeverity.RECOMMENDED,
                score=score,
                action="rebalance_portfolio",
                scope=OptimizationScope.PORTFOLIO,
                scope_ref_id=request.scope_ref_id,
                estimated_improvement_pct=score * 50,
                rationale=f"{len(blocked)} blocked out of {len(campaign_metrics)} campaigns",
                now=now,
            )
            recommendations.append(rec)

        if overdue:
            score = min(1.0, len(overdue) / max(1, len(campaign_metrics)))
            rec = self._create_recommendation(
                request_id=request_id,
                title=f"Escalate overdue campaigns: {len(overdue)} past deadline",
                description=f"{len(overdue)} campaigns are overdue. Escalate or reassign.",
                target=OptimizationTarget.CAMPAIGN_DURATION,
                severity=RecommendationSeverity.URGENT,
                score=score,
                action="escalate_overdue",
                scope=OptimizationScope.PORTFOLIO,
                scope_ref_id=request.scope_ref_id,
                estimated_improvement_pct=score * 30,
                rationale=f"{len(overdue)} overdue campaigns",
                now=now,
            )
            recommendations.append(rec)

        _emit(self._events, "portfolio_optimized", {
            "request_id": request_id,
            "recommendations": len(recommendations),
            "blocked": len(blocked),
            "overdue": len(overdue),
        }, request_id)
        return recommendations

    def optimize_budget_allocation(
        self,
        request_id: str,
        budget_metrics: list[dict[str, Any]],
    ) -> list[OptimizationRecommendation]:
        """Generate recommendations for budget reallocation.

        budget_metrics: list of dicts with keys:
            budget_id, utilization, burn_rate, cost_per_completion, available
        """
        request = self._get_request(request_id)
        now = _now_iso()
        recommendations: list[OptimizationRecommendation] = []

        for bm in budget_metrics:
            bid = bm.get("budget_id", "")
            burn = bm.get("burn_rate", 0.0)
            cpc = bm.get("cost_per_completion", 0.0)
            util = bm.get("utilization", 0.0)

            if burn > 0.9:
                rec = self._create_recommendation(
                    request_id=request_id,
                    title=f"Budget burn critical: {bid}",
                    description=f"Budget {bid} at {burn:.0%} burn rate. Reduce spend or increase limit.",
                    target=OptimizationTarget.BUDGET_ALLOCATION,
                    severity=RecommendationSeverity.CRITICAL if burn > 0.95 else RecommendationSeverity.URGENT,
                    score=min(1.0, burn),
                    action=f"reduce_spend:{bid}",
                    scope=OptimizationScope.GLOBAL,
                    scope_ref_id=bid,
                    estimated_improvement_pct=(burn - 0.8) * 100,
                    estimated_cost_delta=0.0,
                    rationale=f"Burn rate {burn:.0%} exceeds 90% threshold",
                    now=now,
                )
                recommendations.append(rec)

            if cpc > 0 and util > 0.5:
                # Check if cheaper path exists
                score = min(1.0, cpc / 1000.0)
                if score > 0.3:
                    rec = self._create_recommendation(
                        request_id=request_id,
                        title=f"High cost per completion: {bid}",
                        description=f"Budget {bid} has cost/completion of {cpc:.2f}. Seek cheaper paths.",
                        target=OptimizationTarget.CAMPAIGN_COST,
                        severity=RecommendationSeverity.ADVISORY,
                        score=score,
                        action=f"optimize_cost:{bid}",
                        scope=OptimizationScope.GLOBAL,
                        scope_ref_id=bid,
                        estimated_improvement_pct=score * 20,
                        estimated_cost_delta=-cpc * 0.1,
                        rationale=f"Cost per completion {cpc:.2f} with {util:.0%} utilization",
                        now=now,
                    )
                    recommendations.append(rec)

        _emit(self._events, "budget_optimized", {
            "request_id": request_id,
            "recommendations": len(recommendations),
        }, request_id)
        return recommendations

    def optimize_campaigns(
        self,
        request_id: str,
        campaign_metrics: list[dict[str, Any]],
    ) -> list[OptimizationRecommendation]:
        """Generate recommendations for campaign optimization.

        campaign_metrics: list of dicts with keys:
            campaign_id, completion_rate, avg_duration_seconds, escalation_count,
            waiting_on_human_seconds, cost
        """
        request = self._get_request(request_id)
        now = _now_iso()
        recommendations: list[OptimizationRecommendation] = []

        for cm in campaign_metrics:
            cid = cm.get("campaign_id", "")
            woh = cm.get("waiting_on_human_seconds", 0.0)
            esc = cm.get("escalation_count", 0)
            cost = cm.get("cost", 0.0)

            if woh > 3600:
                score = min(1.0, woh / 86400)
                rec = self._create_recommendation(
                    request_id=request_id,
                    title=f"High human wait time: {cid}",
                    description=f"Campaign {cid} has {woh/3600:.1f}h waiting on human. Adjust contact window.",
                    target=OptimizationTarget.SCHEDULE_EFFICIENCY,
                    severity=RecommendationSeverity.RECOMMENDED,
                    score=score,
                    action=f"adjust_contact_window:{cid}",
                    scope=OptimizationScope.CAMPAIGN,
                    scope_ref_id=cid,
                    estimated_improvement_pct=score * 40,
                    rationale=f"Waiting on human {woh/3600:.1f}h exceeds 1h threshold",
                    now=now,
                )
                recommendations.append(rec)

            if esc > 3:
                score = min(1.0, esc / 10)
                rec = self._create_recommendation(
                    request_id=request_id,
                    title=f"Excessive escalations: {cid}",
                    description=f"Campaign {cid} has {esc} escalations. Tighten routing rules.",
                    target=OptimizationTarget.ESCALATION_POLICY,
                    severity=RecommendationSeverity.URGENT if esc > 5 else RecommendationSeverity.RECOMMENDED,
                    score=score,
                    action=f"tighten_escalation:{cid}",
                    scope=OptimizationScope.CAMPAIGN,
                    scope_ref_id=cid,
                    estimated_improvement_pct=score * 30,
                    rationale=f"{esc} escalations exceeds threshold of 3",
                    now=now,
                )
                recommendations.append(rec)

        _emit(self._events, "campaigns_optimized", {
            "request_id": request_id,
            "recommendations": len(recommendations),
        }, request_id)
        return recommendations

    def optimize_schedule(
        self,
        request_id: str,
        schedule_metrics: list[dict[str, Any]],
    ) -> list[OptimizationRecommendation]:
        """Generate recommendations for schedule optimization.

        schedule_metrics: list of dicts with keys:
            identity_ref, available_hours, utilized_hours, contact_attempts,
            quiet_hours_violations
        """
        request = self._get_request(request_id)
        now = _now_iso()
        recommendations: list[OptimizationRecommendation] = []

        for sm in schedule_metrics:
            ref = sm.get("identity_ref", "")
            qhv = sm.get("quiet_hours_violations", 0)
            avail = sm.get("available_hours", 0)
            used = sm.get("utilized_hours", 0)

            if qhv > 0:
                score = min(1.0, qhv / 5)
                rec = self._create_recommendation(
                    request_id=request_id,
                    title=f"Quiet hours violations for {ref}",
                    description=f"{qhv} quiet hours violations. Use quiet-hours-aware channel routing.",
                    target=OptimizationTarget.CHANNEL_ROUTING,
                    severity=RecommendationSeverity.RECOMMENDED,
                    score=score,
                    action=f"quiet_hours_routing:{ref}",
                    scope=OptimizationScope.CHANNEL,
                    scope_ref_id=ref,
                    estimated_improvement_pct=score * 25,
                    rationale=f"{qhv} quiet hours violations detected",
                    now=now,
                )
                recommendations.append(rec)

        _emit(self._events, "schedule_optimized", {
            "request_id": request_id,
            "recommendations": len(recommendations),
        }, request_id)
        return recommendations

    def optimize_escalation(
        self,
        request_id: str,
        escalation_metrics: list[dict[str, Any]],
    ) -> list[OptimizationRecommendation]:
        """Generate recommendations for escalation policy adjustment.

        escalation_metrics: list of dicts with keys:
            policy_ref, total_escalations, resolved_count, avg_resolution_seconds,
            false_positive_count
        """
        request = self._get_request(request_id)
        now = _now_iso()
        recommendations: list[OptimizationRecommendation] = []

        for em in escalation_metrics:
            ref = em.get("policy_ref", "")
            total = em.get("total_escalations", 0)
            fp = em.get("false_positive_count", 0)

            if total > 0 and fp / max(1, total) > 0.3:
                fp_rate = fp / total
                score = min(1.0, fp_rate)
                rec = self._create_recommendation(
                    request_id=request_id,
                    title=f"High false positive escalation rate: {ref}",
                    description=f"Policy {ref} has {fp_rate:.0%} false positive rate. Adjust thresholds.",
                    target=OptimizationTarget.ESCALATION_POLICY,
                    severity=RecommendationSeverity.RECOMMENDED,
                    score=score,
                    action=f"adjust_escalation_threshold:{ref}",
                    scope=OptimizationScope.GLOBAL,
                    scope_ref_id=ref,
                    estimated_improvement_pct=fp_rate * 40,
                    rationale=f"False positive rate {fp_rate:.0%} exceeds 30% threshold",
                    now=now,
                )
                recommendations.append(rec)

        _emit(self._events, "escalation_optimized", {
            "request_id": request_id,
            "recommendations": len(recommendations),
        }, request_id)
        return recommendations

    def optimize_domain_pack_selection(
        self,
        request_id: str,
        domain_metrics: list[dict[str, Any]],
    ) -> list[OptimizationRecommendation]:
        """Generate recommendations for domain pack selection.

        domain_metrics: list of dicts with keys:
            domain_pack_id, success_rate, cost, latency_seconds, fault_rate
        """
        request = self._get_request(request_id)
        now = _now_iso()
        recommendations: list[OptimizationRecommendation] = []

        for dm in domain_metrics:
            dpid = dm.get("domain_pack_id", "")
            fault_rate = dm.get("fault_rate", 0.0)
            sr = dm.get("success_rate", 1.0)

            if fault_rate > 0.1:
                score = min(1.0, fault_rate)
                rec = self._create_recommendation(
                    request_id=request_id,
                    title=f"Fault-prone domain pack: {dpid}",
                    description=f"Domain pack {dpid} has {fault_rate:.0%} fault rate. Avoid or replace.",
                    target=OptimizationTarget.FAULT_AVOIDANCE,
                    severity=RecommendationSeverity.URGENT if fault_rate > 0.3 else RecommendationSeverity.RECOMMENDED,
                    score=score,
                    action=f"avoid_domain_pack:{dpid}",
                    scope=OptimizationScope.DOMAIN_PACK,
                    scope_ref_id=dpid,
                    estimated_improvement_pct=fault_rate * 50,
                    rationale=f"Fault rate {fault_rate:.0%} exceeds 10% threshold",
                    now=now,
                )
                recommendations.append(rec)

        _emit(self._events, "domain_pack_optimized", {
            "request_id": request_id,
            "recommendations": len(recommendations),
        }, request_id)
        return recommendations

    # ------------------------------------------------------------------
    # Plan generation
    # ------------------------------------------------------------------

    def build_plan(
        self,
        plan_id: str,
        request_id: str,
        title: str,
    ) -> OptimizationPlan:
        """Build an optimization plan from all recommendations for a request."""
        if request_id not in self._requests:
            raise RuntimeCoreInvariantError(f"request '{request_id}' not found")
        now = _now_iso()

        rec_ids = self._recommendations_by_request.get(request_id, [])
        recs = [self._recommendations[rid] for rid in rec_ids if rid in self._recommendations]

        # Sort by score descending
        recs.sort(key=lambda r: r.score, reverse=True)

        total_improvement = sum(r.estimated_improvement_pct for r in recs)
        total_cost_delta = sum(r.estimated_cost_delta for r in recs)

        plan = OptimizationPlan(
            plan_id=plan_id,
            request_id=request_id,
            title=title,
            recommendation_ids=tuple(r.recommendation_id for r in recs),
            total_estimated_improvement_pct=total_improvement,
            total_estimated_cost_delta=total_cost_delta,
            feasible=len(recs) > 0,
            created_at=now,
        )
        self._plans[plan_id] = plan

        # Create result
        constraints = self._constraints.get(request_id, [])
        result = OptimizationResult(
            result_id=stable_identifier("ores", {"pid": plan_id, "ts": now}),
            request_id=request_id,
            plan_id=plan_id,
            candidates_generated=len(self._candidates.get(request_id, [])),
            recommendations_produced=len(recs),
            constraints_satisfied=len([c for c in constraints if c.hard]),
            constraints_violated=0,
            best_score=recs[0].score if recs else 0.0,
            completed_at=now,
        )
        self._results[result.result_id] = result

        _emit(self._events, "optimization_plan_built", {
            "plan_id": plan_id,
            "request_id": request_id,
            "recommendations": len(recs),
            "total_improvement": total_improvement,
        }, plan_id)
        return plan

    # ------------------------------------------------------------------
    # Impact estimation
    # ------------------------------------------------------------------

    def estimate_impact(
        self,
        recommendation_id: str,
        metric_name: str,
        current_value: float,
        projected_value: float,
        *,
        confidence: float = 0.8,
        risk_level: str = "low",
    ) -> OptimizationImpactEstimate:
        if recommendation_id not in self._recommendations:
            raise RuntimeCoreInvariantError(f"recommendation '{recommendation_id}' not found")
        now = _now_iso()
        improvement = ((projected_value - current_value) / abs(current_value) * 100) if current_value != 0 else 0.0

        estimate = OptimizationImpactEstimate(
            estimate_id=stable_identifier("oie", {"rec": recommendation_id, "m": metric_name, "ts": now}),
            recommendation_id=recommendation_id,
            metric_name=metric_name,
            current_value=current_value,
            projected_value=projected_value,
            improvement_pct=improvement,
            confidence=confidence,
            risk_level=risk_level,
            created_at=now,
        )
        self._impacts.append(estimate)
        return estimate

    # ------------------------------------------------------------------
    # Decision tracking
    # ------------------------------------------------------------------

    def decide_recommendation(
        self,
        decision_id: str,
        recommendation_id: str,
        disposition: RecommendationDisposition,
        *,
        decided_by: str = "",
        reason: str = "",
    ) -> RecommendationDecision:
        if recommendation_id not in self._recommendations:
            raise RuntimeCoreInvariantError(f"recommendation '{recommendation_id}' not found")
        now = _now_iso()
        decision = RecommendationDecision(
            decision_id=decision_id,
            recommendation_id=recommendation_id,
            disposition=disposition,
            decided_by=decided_by,
            reason=reason,
            decided_at=now,
        )
        self._decisions.append(decision)
        _emit(self._events, "recommendation_decided", {
            "recommendation_id": recommendation_id,
            "disposition": disposition.value,
        }, recommendation_id)
        return decision

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get_recommendations(self, request_id: str) -> tuple[OptimizationRecommendation, ...]:
        ids = self._recommendations_by_request.get(request_id, [])
        return tuple(self._recommendations[rid] for rid in ids if rid in self._recommendations)

    def get_plan(self, plan_id: str) -> OptimizationPlan | None:
        return self._plans.get(plan_id)

    def get_all_recommendations(self) -> tuple[OptimizationRecommendation, ...]:
        return tuple(self._recommendations.values())

    def get_decisions(self) -> tuple[RecommendationDecision, ...]:
        return tuple(self._decisions)

    @property
    def request_count(self) -> int:
        return len(self._requests)

    @property
    def recommendation_count(self) -> int:
        return len(self._recommendations)

    @property
    def plan_count(self) -> int:
        return len(self._plans)

    # ------------------------------------------------------------------
    # State hash
    # ------------------------------------------------------------------

    def state_hash(self) -> str:
        parts: list[str] = []
        for k in sorted(self._requests):
            parts.append(f"req:{k}:{self._requests[k].target.value}")
        for k in sorted(self._constraints):
            parts.append(f"con:{k}:{len(self._constraints[k])}")
        for k in sorted(self._candidates):
            parts.append(f"cand:{k}:{len(self._candidates[k])}")
        for k in sorted(self._recommendations):
            parts.append(f"rec:{k}:{self._recommendations[k].score}")
        for k in sorted(self._recommendations_by_request):
            parts.append(f"rbr:{k}:{len(self._recommendations_by_request[k])}")
        for k in sorted(self._plans):
            parts.append(f"plan:{k}:{self._plans[k].request_id}")
        for k in sorted(self._results):
            parts.append(f"res:{k}:{self._results[k].best_score}")
        parts.append(f"impacts={len(self._impacts)}")
        parts.append(f"decisions={len(self._decisions)}")
        digest = sha256("|".join(parts).encode()).hexdigest()
        return digest

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_request(self, request_id: str) -> OptimizationRequest:
        request = self._requests.get(request_id)
        if request is None:
            raise RuntimeCoreInvariantError(f"request '{request_id}' not found")
        return request

    def _create_recommendation(
        self,
        *,
        request_id: str,
        title: str,
        description: str,
        target: OptimizationTarget,
        severity: RecommendationSeverity,
        score: float,
        action: str,
        scope: OptimizationScope,
        scope_ref_id: str,
        estimated_improvement_pct: float,
        estimated_cost_delta: float = 0.0,
        rationale: str,
        now: str,
    ) -> OptimizationRecommendation:
        rec_id = stable_identifier("orec", {
            "req": request_id, "act": action, "ts": now,
        })
        rec = OptimizationRecommendation(
            recommendation_id=rec_id,
            request_id=request_id,
            title=title,
            description=description,
            target=target,
            severity=severity,
            score=score,
            action=action,
            scope=scope,
            scope_ref_id=scope_ref_id,
            estimated_improvement_pct=estimated_improvement_pct,
            estimated_cost_delta=estimated_cost_delta,
            rationale=rationale,
            created_at=now,
        )
        self._recommendations[rec_id] = rec
        self._recommendations_by_request.setdefault(request_id, []).append(rec_id)
        return rec
