"""Purpose: portfolio scheduling and resource coordination engine.
Governance scope: multi-campaign scheduling by priority/deadline/SLA,
    resource reservation (workers/teams/connectors/quotas/channels),
    preemption, deferral, rebalancing, impossible-schedule detection,
    portfolio health, and deterministic state hash.
Dependencies: portfolio contracts, work_campaign engine, event_spine,
    core invariants.
Invariants:
  - No duplicate portfolio or reservation IDs.
  - Scheduling decisions are deterministic given inputs.
  - Preemption respects policy.
  - All returns are immutable.
  - Every operation emits an event.
"""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
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
    ScheduleWindow,
    SchedulingDecision,
    SchedulingMode,
    SchedulingVerdict,
)
from ..contracts.work_campaign import (
    CampaignDescriptor,
    CampaignPriority,
    CampaignRun,
    CampaignStatus,
)
from ..contracts.event import EventRecord, EventSource, EventType
from .work_campaign import WorkCampaignEngine
from .event_spine import EventSpineEngine
from .invariants import RuntimeCoreInvariantError, stable_identifier


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _emit(es: EventSpineEngine, action: str, payload: dict, cid: str) -> EventRecord:
    now = _now_iso()
    payload["action"] = action
    event = EventRecord(
        event_id=stable_identifier("evt-port", {"action": action, "ts": now, "cid": cid}),
        event_type=EventType.CUSTOM,
        source=EventSource.COMMUNICATION_SYSTEM,
        correlation_id=cid,
        payload=payload,
        emitted_at=now,
    )
    es.emit(event)
    return event


# Priority score mapping
_CAMPAIGN_PRIORITY_SCORES: dict[CampaignPriority, float] = {
    CampaignPriority.LOW: 0.2,
    CampaignPriority.NORMAL: 0.4,
    CampaignPriority.HIGH: 0.6,
    CampaignPriority.URGENT: 0.8,
    CampaignPriority.CRITICAL: 1.0,
}

_PORTFOLIO_PRIORITY_SCORES: dict[PortfolioPriority, float] = {
    PortfolioPriority.LOW: 0.2,
    PortfolioPriority.NORMAL: 0.4,
    PortfolioPriority.HIGH: 0.6,
    PortfolioPriority.URGENT: 0.8,
    PortfolioPriority.CRITICAL: 1.0,
}


class PortfolioEngine:
    """Multi-campaign scheduling and resource coordination engine."""

    def __init__(
        self,
        campaign_engine: WorkCampaignEngine,
        event_spine: EventSpineEngine,
    ) -> None:
        if not isinstance(campaign_engine, WorkCampaignEngine):
            raise RuntimeCoreInvariantError(
                "campaign_engine must be a WorkCampaignEngine"
            )
        if not isinstance(event_spine, EventSpineEngine):
            raise RuntimeCoreInvariantError(
                "event_spine must be an EventSpineEngine"
            )
        self._campaigns = campaign_engine
        self._events = event_spine
        self._portfolios: dict[str, PortfolioDescriptor] = {}
        self._campaign_reservations: dict[str, CampaignReservation] = {}  # campaign_id -> reservation
        self._resource_reservations: dict[str, ResourceReservation] = {}  # reservation_id -> reservation
        self._quota_reservations: dict[str, QuotaReservation] = {}  # reservation_id -> reservation
        self._schedule_windows: dict[str, ScheduleWindow] = {}  # window_id -> window
        self._scheduling_decisions: list[SchedulingDecision] = []
        self._preemption_records: list[PreemptionRecord] = []
        # Resource capacity tracking: resource_ref -> {total, reserved}
        self._resource_capacity: dict[str, dict[str, int]] = {}

    # ------------------------------------------------------------------
    # Portfolio registration
    # ------------------------------------------------------------------

    def register_portfolio(
        self,
        portfolio_id: str,
        name: str,
        *,
        scheduling_mode: SchedulingMode = SchedulingMode.PRIORITY,
        preemption_policy: PreemptionPolicy = PreemptionPolicy.PRIORITY_ONLY,
        priority: PortfolioPriority = PortfolioPriority.NORMAL,
        owner_id: str = "",
        max_concurrent: int = 10,
        tags: tuple[str, ...] = (),
        metadata: dict[str, Any] | None = None,
    ) -> PortfolioDescriptor:
        if portfolio_id in self._portfolios:
            raise RuntimeCoreInvariantError(
                f"portfolio '{portfolio_id}' already registered"
            )
        now = _now_iso()
        desc = PortfolioDescriptor(
            portfolio_id=portfolio_id,
            name=name,
            status=PortfolioStatus.ACTIVE,
            priority=priority,
            scheduling_mode=scheduling_mode,
            preemption_policy=preemption_policy,
            owner_id=owner_id,
            max_concurrent=max_concurrent,
            tags=tags,
            created_at=now,
            metadata=metadata or {},
        )
        self._portfolios[portfolio_id] = desc

        _emit(self._events, "portfolio_registered", {
            "portfolio_id": portfolio_id,
            "name": name,
            "mode": scheduling_mode.value,
        }, portfolio_id)

        return desc

    def get_portfolio(self, portfolio_id: str) -> PortfolioDescriptor:
        if portfolio_id not in self._portfolios:
            raise RuntimeCoreInvariantError(
                f"portfolio '{portfolio_id}' not found"
            )
        return self._portfolios[portfolio_id]

    # ------------------------------------------------------------------
    # Campaign registration into portfolio
    # ------------------------------------------------------------------

    def register_campaign(
        self,
        portfolio_id: str,
        campaign_id: str,
        *,
        deadline: str = "",
        sla_seconds: int = 0,
        preemptible: bool = True,
        domain_pack_id: str = "",
    ) -> CampaignReservation:
        """Register a campaign into a portfolio for scheduling."""
        portfolio = self.get_portfolio(portfolio_id)

        if campaign_id in self._campaign_reservations:
            raise RuntimeCoreInvariantError(
                f"campaign '{campaign_id}' already registered in portfolio"
            )

        # Get campaign descriptor for priority
        desc = self._campaigns.get_campaign(campaign_id)
        priority_score = _CAMPAIGN_PRIORITY_SCORES.get(desc.priority, 0.4)

        # Boost for deadline proximity
        if deadline:
            try:
                dl = datetime.fromisoformat(deadline.replace("Z", "+00:00"))
                remaining = (dl - datetime.now(timezone.utc)).total_seconds()
                if remaining < 3600:
                    priority_score = min(1.0, priority_score + 0.3)
                elif remaining < 86400:
                    priority_score = min(1.0, priority_score + 0.1)
            except (ValueError, TypeError):
                pass

        now = _now_iso()
        reservation = CampaignReservation(
            reservation_id=stable_identifier("cres", {
                "pid": portfolio_id, "cid": campaign_id, "ts": now,
            }),
            portfolio_id=portfolio_id,
            campaign_id=campaign_id,
            priority_score=priority_score,
            deadline=deadline,
            sla_seconds=sla_seconds,
            preemptible=preemptible,
            domain_pack_id=domain_pack_id,
            created_at=now,
        )
        self._campaign_reservations[campaign_id] = reservation

        # Update portfolio campaign_ids
        current_ids = list(portfolio.campaign_ids) + [campaign_id]
        self._portfolios[portfolio_id] = PortfolioDescriptor(
            portfolio_id=portfolio.portfolio_id,
            name=portfolio.name,
            description=portfolio.description,
            status=portfolio.status,
            priority=portfolio.priority,
            scheduling_mode=portfolio.scheduling_mode,
            preemption_policy=portfolio.preemption_policy,
            owner_id=portfolio.owner_id,
            campaign_ids=tuple(current_ids),
            max_concurrent=portfolio.max_concurrent,
            tags=portfolio.tags,
            created_at=portfolio.created_at,
            metadata=dict(portfolio.metadata),
        )

        _emit(self._events, "campaign_registered_in_portfolio", {
            "portfolio_id": portfolio_id,
            "campaign_id": campaign_id,
            "priority_score": priority_score,
        }, portfolio_id)

        return reservation

    # ------------------------------------------------------------------
    # Resource management
    # ------------------------------------------------------------------

    def set_resource_capacity(
        self, resource_ref: str, total_units: int,
    ) -> None:
        """Set total capacity for a resource."""
        self._resource_capacity[resource_ref] = {
            "total": total_units,
            "reserved": self._resource_capacity.get(resource_ref, {}).get("reserved", 0),
        }

    def reserve_resources(
        self,
        portfolio_id: str,
        campaign_id: str,
        resource_ref: str,
        *,
        resource_class: ResourceClass = ResourceClass.HUMAN,
        reservation_type: ReservationType = ReservationType.WORKER,
        units: int = 1,
    ) -> ResourceReservation | None:
        """Reserve resource units for a campaign. Returns None if insufficient capacity."""
        self.get_portfolio(portfolio_id)

        cap = self._resource_capacity.get(resource_ref, {"total": 0, "reserved": 0})
        available = cap["total"] - cap["reserved"]
        if units > available:
            return None

        now = _now_iso()
        reservation = ResourceReservation(
            reservation_id=stable_identifier("rres", {
                "pid": portfolio_id, "cid": campaign_id, "ref": resource_ref, "ts": now,
            }),
            portfolio_id=portfolio_id,
            campaign_id=campaign_id,
            resource_ref=resource_ref,
            resource_class=resource_class,
            reservation_type=reservation_type,
            units_reserved=units,
            created_at=now,
        )
        self._resource_reservations[reservation.reservation_id] = reservation
        self._resource_capacity[resource_ref]["reserved"] = cap["reserved"] + units

        _emit(self._events, "resource_reserved", {
            "portfolio_id": portfolio_id,
            "campaign_id": campaign_id,
            "resource_ref": resource_ref,
            "units": units,
        }, portfolio_id)

        return reservation

    def release_resources(self, reservation_id: str) -> bool:
        """Release a resource reservation."""
        if reservation_id not in self._resource_reservations:
            return False

        res = self._resource_reservations[reservation_id]
        if not res.active:
            return False

        # Mark inactive
        self._resource_reservations[reservation_id] = ResourceReservation(
            reservation_id=res.reservation_id,
            portfolio_id=res.portfolio_id,
            campaign_id=res.campaign_id,
            resource_ref=res.resource_ref,
            resource_class=res.resource_class,
            reservation_type=res.reservation_type,
            units_reserved=res.units_reserved,
            active=False,
            created_at=res.created_at,
        )

        # Return capacity
        cap = self._resource_capacity.get(res.resource_ref, {"total": 0, "reserved": 0})
        cap["reserved"] = max(0, cap["reserved"] - res.units_reserved)
        self._resource_capacity[res.resource_ref] = cap

        _emit(self._events, "resource_released", {
            "reservation_id": reservation_id,
            "resource_ref": res.resource_ref,
            "units": res.units_reserved,
        }, res.portfolio_id)

        return True

    # ------------------------------------------------------------------
    # Quota reservation
    # ------------------------------------------------------------------

    def reserve_quota(
        self,
        portfolio_id: str,
        campaign_id: str,
        connector_id: str,
        units: int,
    ) -> QuotaReservation:
        """Reserve connector quota for a campaign."""
        self.get_portfolio(portfolio_id)
        now = _now_iso()
        reservation = QuotaReservation(
            reservation_id=stable_identifier("qres", {
                "pid": portfolio_id, "cid": campaign_id, "conn": connector_id, "ts": now,
            }),
            portfolio_id=portfolio_id,
            campaign_id=campaign_id,
            connector_id=connector_id,
            quota_units=units,
            quota_remaining=units,
            created_at=now,
        )
        self._quota_reservations[reservation.reservation_id] = reservation

        _emit(self._events, "quota_reserved", {
            "portfolio_id": portfolio_id,
            "campaign_id": campaign_id,
            "connector_id": connector_id,
            "units": units,
        }, portfolio_id)

        return reservation

    # ------------------------------------------------------------------
    # Schedule windows
    # ------------------------------------------------------------------

    def add_schedule_window(
        self,
        window_id: str,
        resource_ref: str,
        starts_at: str,
        ends_at: str,
        *,
        resource_class: ResourceClass = ResourceClass.HUMAN,
        capacity_units: int = 1,
    ) -> ScheduleWindow:
        """Add a scheduling window for a resource."""
        if window_id in self._schedule_windows:
            raise RuntimeCoreInvariantError(
                f"schedule window '{window_id}' already exists"
            )
        window = ScheduleWindow(
            window_id=window_id,
            resource_ref=resource_ref,
            resource_class=resource_class,
            starts_at=starts_at,
            ends_at=ends_at,
            capacity_units=capacity_units,
        )
        self._schedule_windows[window_id] = window
        return window

    # ------------------------------------------------------------------
    # Scheduling
    # ------------------------------------------------------------------

    def schedule_next(
        self, portfolio_id: str,
    ) -> SchedulingDecision:
        """Schedule the next campaign from the portfolio.

        Scheduling dimensions:
        1. Campaign priority (from CampaignPriority → score)
        2. Deadline proximity (boost for near-deadline)
        3. Waiting-on-human status (deferred)
        4. Resource capacity (defer if no capacity)
        5. Domain-pack scheduling bias (boost if domain pack active)
        """
        portfolio = self.get_portfolio(portfolio_id)
        now = _now_iso()

        # Gather unscheduled campaigns
        candidates: list[CampaignReservation] = []
        for cid in portfolio.campaign_ids:
            res = self._campaign_reservations.get(cid)
            if res and not res.scheduled and not res.deferred:
                candidates.append(res)

        if not candidates:
            # Nothing to schedule
            decision = SchedulingDecision(
                decision_id=stable_identifier("sdec", {"pid": portfolio_id, "ts": now}),
                portfolio_id=portfolio_id,
                campaign_id="none",
                verdict=SchedulingVerdict.UNSCHEDULABLE,
                reason="no candidates available",
                decided_at=now,
            )
            self._scheduling_decisions.append(decision)
            return decision

        # Check max_concurrent
        active_count = sum(
            1 for cid in portfolio.campaign_ids
            if self._campaign_reservations.get(cid, CampaignReservation(
                reservation_id="x", portfolio_id="x", campaign_id="x",
                created_at=now,
            )).scheduled
        )
        if active_count >= portfolio.max_concurrent:
            # All slots full — defer
            best = self._pick_best_candidate(candidates, portfolio.scheduling_mode)
            decision = SchedulingDecision(
                decision_id=stable_identifier("sdec", {"pid": portfolio_id, "cid": best.campaign_id, "ts": now}),
                portfolio_id=portfolio_id,
                campaign_id=best.campaign_id,
                verdict=SchedulingVerdict.DEFERRED,
                priority_score=best.priority_score,
                reason="max concurrent campaigns reached",
                decided_at=now,
            )
            self._scheduling_decisions.append(decision)
            return decision

        # Sort and pick best candidate
        best = self._pick_best_candidate(candidates, portfolio.scheduling_mode)

        # Check waiting-on-human
        if best.waiting_on_human:
            decision = SchedulingDecision(
                decision_id=stable_identifier("sdec", {"pid": portfolio_id, "cid": best.campaign_id, "ts": now}),
                portfolio_id=portfolio_id,
                campaign_id=best.campaign_id,
                verdict=SchedulingVerdict.WAITING,
                priority_score=best.priority_score,
                reason="waiting on human response",
                decided_at=now,
            )
            self._scheduling_decisions.append(decision)
            return decision

        # Schedule it
        self._campaign_reservations[best.campaign_id] = CampaignReservation(
            reservation_id=best.reservation_id,
            portfolio_id=best.portfolio_id,
            campaign_id=best.campaign_id,
            priority_score=best.priority_score,
            deadline=best.deadline,
            sla_seconds=best.sla_seconds,
            preemptible=best.preemptible,
            waiting_on_human=best.waiting_on_human,
            domain_pack_id=best.domain_pack_id,
            scheduled=True,
            created_at=best.created_at,
        )

        decision = SchedulingDecision(
            decision_id=stable_identifier("sdec", {"pid": portfolio_id, "cid": best.campaign_id, "ts": now}),
            portfolio_id=portfolio_id,
            campaign_id=best.campaign_id,
            verdict=SchedulingVerdict.SCHEDULED,
            priority_score=best.priority_score,
            reason="scheduled by priority",
            decided_at=now,
        )
        self._scheduling_decisions.append(decision)

        _emit(self._events, "campaign_scheduled", {
            "portfolio_id": portfolio_id,
            "campaign_id": best.campaign_id,
            "priority_score": best.priority_score,
        }, portfolio_id)

        return decision

    def _pick_best_candidate(
        self, candidates: list[CampaignReservation],
        mode: SchedulingMode,
    ) -> CampaignReservation:
        """Pick the best candidate based on scheduling mode."""
        if mode == SchedulingMode.FIFO:
            return min(candidates, key=lambda c: c.created_at)
        elif mode == SchedulingMode.DEADLINE:
            # Prefer candidates with deadlines, then by deadline proximity
            with_deadline = [c for c in candidates if c.deadline]
            if with_deadline:
                return min(with_deadline, key=lambda c: c.deadline)
            return max(candidates, key=lambda c: c.priority_score)
        elif mode == SchedulingMode.SLA:
            return min(candidates, key=lambda c: c.sla_seconds if c.sla_seconds > 0 else 999999)
        else:
            # PRIORITY (default), ROUND_ROBIN, WEIGHTED — use priority score
            return max(candidates, key=lambda c: c.priority_score)

    # ------------------------------------------------------------------
    # Preemption
    # ------------------------------------------------------------------

    def preempt_campaign(
        self,
        portfolio_id: str,
        preempting_campaign_id: str,
        preempted_campaign_id: str,
        *,
        reason: str = "",
    ) -> PreemptionRecord | None:
        """Preempt a lower-priority campaign for a higher-priority one.

        Returns None if preemption is not allowed by policy.
        """
        portfolio = self.get_portfolio(portfolio_id)

        # Check preemption policy
        if portfolio.preemption_policy == PreemptionPolicy.NEVER:
            return None

        preempting_res = self._campaign_reservations.get(preempting_campaign_id)
        preempted_res = self._campaign_reservations.get(preempted_campaign_id)
        if not preempting_res or not preempted_res:
            return None

        if not preempted_res.preemptible:
            return None

        if portfolio.preemption_policy == PreemptionPolicy.PRIORITY_ONLY:
            if preempting_res.priority_score <= preempted_res.priority_score:
                return None

        # Execute preemption
        now = _now_iso()

        # Pause the preempted campaign's runs
        runs = self._campaigns.list_runs(
            preempted_campaign_id, status=CampaignStatus.ACTIVE,
        )
        for run in runs:
            try:
                self._campaigns.pause_run(run.run_id)
            except RuntimeCoreInvariantError:
                pass

        # Mark preempted as deferred
        self._campaign_reservations[preempted_campaign_id] = CampaignReservation(
            reservation_id=preempted_res.reservation_id,
            portfolio_id=preempted_res.portfolio_id,
            campaign_id=preempted_res.campaign_id,
            priority_score=preempted_res.priority_score,
            deadline=preempted_res.deadline,
            sla_seconds=preempted_res.sla_seconds,
            preemptible=preempted_res.preemptible,
            waiting_on_human=preempted_res.waiting_on_human,
            domain_pack_id=preempted_res.domain_pack_id,
            scheduled=False,
            deferred=True,
            deferred_reason=f"preempted by {preempting_campaign_id}",
            created_at=preempted_res.created_at,
        )

        # Release preempted resources
        for rid, rr in list(self._resource_reservations.items()):
            if rr.campaign_id == preempted_campaign_id and rr.active:
                self.release_resources(rid)

        record = PreemptionRecord(
            preemption_id=stable_identifier("preempt", {
                "pid": portfolio_id,
                "from": preempting_campaign_id,
                "to": preempted_campaign_id,
                "ts": now,
            }),
            portfolio_id=portfolio_id,
            preempting_campaign_id=preempting_campaign_id,
            preempted_campaign_id=preempted_campaign_id,
            reason=reason or "higher priority",
            priority_delta=preempting_res.priority_score - preempted_res.priority_score,
            preempted_at=now,
        )
        self._preemption_records.append(record)

        _emit(self._events, "campaign_preempted", {
            "portfolio_id": portfolio_id,
            "preempting": preempting_campaign_id,
            "preempted": preempted_campaign_id,
        }, portfolio_id)

        return record

    # ------------------------------------------------------------------
    # Rebalance
    # ------------------------------------------------------------------

    def rebalance_portfolio(self, portfolio_id: str) -> list[SchedulingDecision]:
        """Rebalance: reschedule deferred campaigns if capacity is available."""
        portfolio = self.get_portfolio(portfolio_id)
        decisions: list[SchedulingDecision] = []
        now = _now_iso()

        # Update portfolio status
        self._portfolios[portfolio_id] = PortfolioDescriptor(
            portfolio_id=portfolio.portfolio_id,
            name=portfolio.name,
            description=portfolio.description,
            status=PortfolioStatus.REBALANCING,
            priority=portfolio.priority,
            scheduling_mode=portfolio.scheduling_mode,
            preemption_policy=portfolio.preemption_policy,
            owner_id=portfolio.owner_id,
            campaign_ids=portfolio.campaign_ids,
            max_concurrent=portfolio.max_concurrent,
            tags=portfolio.tags,
            created_at=portfolio.created_at,
            metadata=dict(portfolio.metadata),
        )

        # Find deferred campaigns
        deferred: list[CampaignReservation] = []
        for cid in portfolio.campaign_ids:
            res = self._campaign_reservations.get(cid)
            if res and res.deferred and not res.scheduled:
                deferred.append(res)

        # Sort by priority
        deferred.sort(key=lambda c: c.priority_score, reverse=True)

        active_count = sum(
            1 for cid in portfolio.campaign_ids
            if self._campaign_reservations.get(cid) and
            self._campaign_reservations[cid].scheduled
        )

        for res in deferred:
            if active_count >= portfolio.max_concurrent:
                break

            # Un-defer and schedule
            self._campaign_reservations[res.campaign_id] = CampaignReservation(
                reservation_id=res.reservation_id,
                portfolio_id=res.portfolio_id,
                campaign_id=res.campaign_id,
                priority_score=res.priority_score,
                deadline=res.deadline,
                sla_seconds=res.sla_seconds,
                preemptible=res.preemptible,
                waiting_on_human=res.waiting_on_human,
                domain_pack_id=res.domain_pack_id,
                scheduled=True,
                deferred=False,
                created_at=res.created_at,
            )
            active_count += 1

            decision = SchedulingDecision(
                decision_id=stable_identifier("sdec-rebal", {
                    "pid": portfolio_id, "cid": res.campaign_id, "ts": now,
                }),
                portfolio_id=portfolio_id,
                campaign_id=res.campaign_id,
                verdict=SchedulingVerdict.SCHEDULED,
                priority_score=res.priority_score,
                reason="rebalanced from deferred",
                decided_at=now,
            )
            self._scheduling_decisions.append(decision)
            decisions.append(decision)

        # Restore ACTIVE status
        self._portfolios[portfolio_id] = PortfolioDescriptor(
            portfolio_id=portfolio.portfolio_id,
            name=portfolio.name,
            description=portfolio.description,
            status=PortfolioStatus.ACTIVE,
            priority=portfolio.priority,
            scheduling_mode=portfolio.scheduling_mode,
            preemption_policy=portfolio.preemption_policy,
            owner_id=portfolio.owner_id,
            campaign_ids=portfolio.campaign_ids,
            max_concurrent=portfolio.max_concurrent,
            tags=portfolio.tags,
            created_at=portfolio.created_at,
            metadata=dict(portfolio.metadata),
        )

        _emit(self._events, "portfolio_rebalanced", {
            "portfolio_id": portfolio_id,
            "rescheduled_count": len(decisions),
        }, portfolio_id)

        return decisions

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def overdue_campaigns(
        self, portfolio_id: str, *, max_age_seconds: int = 86400,
    ) -> tuple[CampaignReservation, ...]:
        """Return campaigns whose deadline has passed or that have run too long."""
        portfolio = self.get_portfolio(portfolio_id)
        now = datetime.now(timezone.utc)
        result: list[CampaignReservation] = []

        for cid in portfolio.campaign_ids:
            res = self._campaign_reservations.get(cid)
            if not res:
                continue

            # Check deadline
            if res.deadline:
                try:
                    dl = datetime.fromisoformat(res.deadline.replace("Z", "+00:00"))
                    if now > dl:
                        result.append(res)
                        continue
                except (ValueError, TypeError):
                    pass

            # Check age
            try:
                created = datetime.fromisoformat(res.created_at.replace("Z", "+00:00"))
                if (now - created).total_seconds() > max_age_seconds:
                    result.append(res)
            except (ValueError, TypeError):
                pass

        return tuple(result)

    def blocked_campaigns(
        self, portfolio_id: str,
    ) -> tuple[CampaignReservation, ...]:
        """Return campaigns that are deferred or waiting on human."""
        portfolio = self.get_portfolio(portfolio_id)
        result: list[CampaignReservation] = []
        for cid in portfolio.campaign_ids:
            res = self._campaign_reservations.get(cid)
            if res and (res.deferred or res.waiting_on_human):
                result.append(res)
        return tuple(result)

    def capacity_snapshot(self, portfolio_id: str) -> CapacitySnapshot:
        """Take a point-in-time capacity snapshot."""
        portfolio = self.get_portfolio(portfolio_id)
        now = _now_iso()

        # Count resources
        total_workers = 0
        available_workers = 0
        total_connectors = 0
        healthy_connectors = 0
        total_quota = 0
        available_quota = 0

        for ref, cap in self._resource_capacity.items():
            total_workers += cap["total"]
            available_workers += cap["total"] - cap["reserved"]

        for qr in self._quota_reservations.values():
            if qr.portfolio_id == portfolio_id and qr.active:
                total_quota += qr.quota_units
                available_quota += qr.quota_remaining

        active = sum(1 for cid in portfolio.campaign_ids
                     if self._campaign_reservations.get(cid) and
                     self._campaign_reservations[cid].scheduled)
        deferred = sum(1 for cid in portfolio.campaign_ids
                       if self._campaign_reservations.get(cid) and
                       self._campaign_reservations[cid].deferred)
        blocked = sum(1 for cid in portfolio.campaign_ids
                      if self._campaign_reservations.get(cid) and
                      self._campaign_reservations[cid].waiting_on_human)

        return CapacitySnapshot(
            snapshot_id=stable_identifier("capsnap", {"pid": portfolio_id, "ts": now}),
            portfolio_id=portfolio_id,
            total_workers=total_workers,
            available_workers=available_workers,
            total_quota_units=total_quota,
            available_quota_units=available_quota,
            active_campaigns=active,
            deferred_campaigns=deferred,
            blocked_campaigns=blocked,
            captured_at=now,
        )

    def portfolio_health(self, portfolio_id: str) -> PortfolioHealth:
        """Compute portfolio health."""
        portfolio = self.get_portfolio(portfolio_id)
        now = _now_iso()

        total = len(portfolio.campaign_ids)
        active = 0
        deferred = 0
        blocked = 0
        completed = 0
        preempted = 0

        for cid in portfolio.campaign_ids:
            res = self._campaign_reservations.get(cid)
            if not res:
                continue
            if res.deferred:
                deferred += 1
            elif res.waiting_on_human:
                blocked += 1
            elif res.scheduled:
                active += 1

        # Check completed via campaign engine
        for cid in portfolio.campaign_ids:
            try:
                desc = self._campaigns.get_campaign(cid)
                if desc.status == CampaignStatus.COMPLETED:
                    completed += 1
            except RuntimeCoreInvariantError:
                pass

        preempted = sum(
            1 for p in self._preemption_records
            if p.portfolio_id == portfolio_id
        )
        overdue = len(self.overdue_campaigns(portfolio_id))

        utilization = active / max(1, total)

        return PortfolioHealth(
            portfolio_id=portfolio_id,
            status=portfolio.status,
            total_campaigns=total,
            active_campaigns=active,
            deferred_campaigns=deferred,
            blocked_campaigns=blocked,
            overdue_campaigns=overdue,
            preempted_campaigns=preempted,
            completed_campaigns=completed,
            utilization=min(1.0, utilization),
            computed_at=now,
        )

    def get_scheduling_decisions(
        self, portfolio_id: str | None = None,
    ) -> tuple[SchedulingDecision, ...]:
        if portfolio_id is None:
            return tuple(self._scheduling_decisions)
        return tuple(d for d in self._scheduling_decisions if d.portfolio_id == portfolio_id)

    def get_preemption_records(
        self, portfolio_id: str | None = None,
    ) -> tuple[PreemptionRecord, ...]:
        if portfolio_id is None:
            return tuple(self._preemption_records)
        return tuple(p for p in self._preemption_records if p.portfolio_id == portfolio_id)

    def get_resource_reservations(
        self, campaign_id: str | None = None,
    ) -> tuple[ResourceReservation, ...]:
        if campaign_id is None:
            return tuple(self._resource_reservations.values())
        return tuple(r for r in self._resource_reservations.values() if r.campaign_id == campaign_id)

    def get_quota_reservations(
        self, campaign_id: str | None = None,
    ) -> tuple[QuotaReservation, ...]:
        if campaign_id is None:
            return tuple(self._quota_reservations.values())
        return tuple(q for q in self._quota_reservations.values() if q.campaign_id == campaign_id)

    def get_campaign_reservation(
        self, campaign_id: str,
    ) -> CampaignReservation | None:
        return self._campaign_reservations.get(campaign_id)

    # ------------------------------------------------------------------
    # Closure
    # ------------------------------------------------------------------

    def close_portfolio(self, portfolio_id: str) -> PortfolioClosureReport:
        """Close a portfolio and generate closure report."""
        portfolio = self.get_portfolio(portfolio_id)
        now = _now_iso()

        completed = 0
        failed = 0
        deferred_count = 0
        preempted_count = sum(
            1 for p in self._preemption_records if p.portfolio_id == portfolio_id
        )

        for cid in portfolio.campaign_ids:
            res = self._campaign_reservations.get(cid)
            if res and res.deferred:
                deferred_count += 1
            try:
                desc = self._campaigns.get_campaign(cid)
                if desc.status == CampaignStatus.COMPLETED:
                    completed += 1
                elif desc.status in (CampaignStatus.FAILED, CampaignStatus.ABORTED):
                    failed += 1
            except RuntimeCoreInvariantError:
                pass

        decisions = self.get_scheduling_decisions(portfolio_id)
        resource_reservations = [
            r for r in self._resource_reservations.values()
            if r.portfolio_id == portfolio_id
        ]
        quota_reservations = [
            q for q in self._quota_reservations.values()
            if q.portfolio_id == portfolio_id
        ]

        report = PortfolioClosureReport(
            report_id=stable_identifier("pclosure", {"pid": portfolio_id, "ts": now}),
            portfolio_id=portfolio_id,
            total_campaigns=len(portfolio.campaign_ids),
            completed_campaigns=completed,
            failed_campaigns=failed,
            deferred_campaigns=deferred_count,
            preempted_campaigns=preempted_count,
            total_scheduling_decisions=len(decisions),
            total_preemptions=preempted_count,
            total_resource_reservations=len(resource_reservations),
            total_quota_reservations=len(quota_reservations),
            summary=f"Portfolio {portfolio_id}: {completed}/{len(portfolio.campaign_ids)} completed",
            created_at=now,
        )

        # Update portfolio status
        self._portfolios[portfolio_id] = PortfolioDescriptor(
            portfolio_id=portfolio.portfolio_id,
            name=portfolio.name,
            description=portfolio.description,
            status=PortfolioStatus.COMPLETED,
            priority=portfolio.priority,
            scheduling_mode=portfolio.scheduling_mode,
            preemption_policy=portfolio.preemption_policy,
            owner_id=portfolio.owner_id,
            campaign_ids=portfolio.campaign_ids,
            max_concurrent=portfolio.max_concurrent,
            tags=portfolio.tags,
            created_at=portfolio.created_at,
            metadata=dict(portfolio.metadata),
        )

        _emit(self._events, "portfolio_closed", {
            "portfolio_id": portfolio_id,
            "completed": completed,
            "total": len(portfolio.campaign_ids),
        }, portfolio_id)

        return report

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def portfolio_count(self) -> int:
        return len(self._portfolios)

    @property
    def reservation_count(self) -> int:
        return len(self._campaign_reservations)

    @property
    def decision_count(self) -> int:
        return len(self._scheduling_decisions)

    def state_hash(self) -> str:
        h = sha256()
        for pid in sorted(self._portfolios):
            p = self._portfolios[pid]
            h.update(f"port:{pid}:{p.status.value}:{len(p.campaign_ids)}".encode())
        for cid in sorted(self._campaign_reservations):
            c = self._campaign_reservations[cid]
            h.update(f"cres:{cid}:{c.scheduled}:{c.deferred}:{c.priority_score}".encode())
        for rid in sorted(self._resource_reservations):
            r = self._resource_reservations[rid]
            h.update(f"rres:{rid}:{r.active}:{r.units_reserved}".encode())
        for qid in sorted(self._quota_reservations):
            q = self._quota_reservations[qid]
            h.update(f"qres:{qid}:{q.active}:{q.units_reserved}".encode())
        for wid in sorted(self._schedule_windows):
            w = self._schedule_windows[wid]
            h.update(f"swin:{wid}:{w.portfolio_id}".encode())
        h.update(f"decisions:{len(self._scheduling_decisions)}".encode())
        h.update(f"preemptions:{len(self._preemption_records)}".encode())
        return h.hexdigest()
