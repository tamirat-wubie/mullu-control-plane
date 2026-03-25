"""Purpose: financial / cost / budget runtime engine.
Governance scope: budget registration, spend reservation/consumption/release,
    cost estimation, spend forecasting, budget conflict detection, budget
    gating for governance and portfolio decisions, approval threshold
    enforcement.
Dependencies: financial_runtime contracts, event_spine, core invariants.
Invariants:
  - consumed + reserved ≤ limit at all times.
  - No negative spend amounts.
  - Currency consistency enforced per budget.
  - Immutable returns.
  - Every mutation emits an event.
  - Deterministic reservation ordering.
"""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from typing import Any

from ..contracts.event import EventRecord, EventSource, EventType
from ..contracts.financial_runtime import (
    ApprovalThreshold,
    ApprovalThresholdMode,
    BudgetClosureReport,
    BudgetConflict,
    BudgetConflictKind,
    BudgetDecision,
    BudgetEnvelope,
    BudgetReservation,
    BudgetScope,
    CampaignBudgetBinding,
    ChargeDisposition,
    ConnectorCostProfile,
    CostCategory,
    CostEstimate,
    FinancialHealthSnapshot,
    SpendForecast,
    SpendRecord,
    SpendStatus,
)
from .event_spine import EventSpineEngine
from .invariants import RuntimeCoreInvariantError, stable_identifier


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _emit(es: EventSpineEngine, action: str, payload: dict, cid: str) -> EventRecord:
    now = _now_iso()
    payload["action"] = action
    event = EventRecord(
        event_id=stable_identifier("evt-fin", {"action": action, "ts": now, "cid": cid}),
        event_type=EventType.CUSTOM,
        source=EventSource.COMMUNICATION_SYSTEM,
        correlation_id=cid,
        payload=payload,
        emitted_at=now,
    )
    es.emit(event)
    return event


class FinancialRuntimeEngine:
    """Engine for budget management, spend tracking, and cost-aware decisions."""

    def __init__(self, event_spine: EventSpineEngine) -> None:
        if not isinstance(event_spine, EventSpineEngine):
            raise RuntimeCoreInvariantError("event_spine must be an EventSpineEngine")
        self._events = event_spine
        self._budgets: dict[str, BudgetEnvelope] = {}
        self._spend_records: dict[str, SpendRecord] = {}
        self._reservations: dict[str, BudgetReservation] = {}
        self._bindings: dict[str, CampaignBudgetBinding] = {}
        self._connector_profiles: dict[str, ConnectorCostProfile] = {}
        self._thresholds: dict[str, ApprovalThreshold] = {}
        self._decisions: list[BudgetDecision] = []
        self._conflicts: list[BudgetConflict] = []
        self._forecasts: list[SpendForecast] = []
        self._warnings_issued: int = 0
        self._hard_stops_triggered: int = 0

    # ------------------------------------------------------------------
    # Budget registration
    # ------------------------------------------------------------------

    def register_budget(
        self,
        budget_id: str,
        name: str,
        scope: BudgetScope,
        scope_ref_id: str,
        *,
        currency: str = "USD",
        limit_amount: float = 0.0,
        warning_threshold: float = 0.8,
        hard_stop_threshold: float = 1.0,
        tags: tuple[str, ...] = (),
        metadata: dict[str, Any] | None = None,
    ) -> BudgetEnvelope:
        if budget_id in self._budgets:
            raise RuntimeCoreInvariantError(f"budget '{budget_id}' already exists")
        now = _now_iso()
        budget = BudgetEnvelope(
            budget_id=budget_id,
            name=name,
            scope=scope,
            scope_ref_id=scope_ref_id,
            currency=currency,
            limit_amount=limit_amount,
            warning_threshold=warning_threshold,
            hard_stop_threshold=hard_stop_threshold,
            tags=tags,
            created_at=now,
            updated_at=now,
            metadata=metadata or {},
        )
        self._budgets[budget_id] = budget
        _emit(self._events, "budget_registered", {
            "budget_id": budget_id,
            "scope": scope.value,
            "limit_amount": limit_amount,
            "currency": currency,
        }, budget_id)
        return budget

    def get_budget(self, budget_id: str) -> BudgetEnvelope | None:
        return self._budgets.get(budget_id)

    # ------------------------------------------------------------------
    # Campaign budget binding
    # ------------------------------------------------------------------

    def bind_campaign_budget(
        self,
        binding_id: str,
        campaign_id: str,
        budget_id: str,
        allocated_amount: float,
    ) -> CampaignBudgetBinding:
        if binding_id in self._bindings:
            raise RuntimeCoreInvariantError(f"binding '{binding_id}' already exists")
        budget = self._budgets.get(budget_id)
        if budget is None:
            raise RuntimeCoreInvariantError(f"budget '{budget_id}' not found")
        if allocated_amount < 0:
            raise RuntimeCoreInvariantError("allocated_amount must be non-negative")

        now = _now_iso()
        binding = CampaignBudgetBinding(
            binding_id=binding_id,
            campaign_id=campaign_id,
            budget_id=budget_id,
            allocated_amount=allocated_amount,
            currency=budget.currency,
            created_at=now,
        )
        self._bindings[binding_id] = binding
        _emit(self._events, "campaign_budget_bound", {
            "binding_id": binding_id,
            "campaign_id": campaign_id,
            "budget_id": budget_id,
            "allocated_amount": allocated_amount,
        }, campaign_id)
        return binding

    def get_binding(self, binding_id: str) -> CampaignBudgetBinding | None:
        return self._bindings.get(binding_id)

    def get_bindings_for_campaign(self, campaign_id: str) -> tuple[CampaignBudgetBinding, ...]:
        return tuple(b for b in self._bindings.values() if b.campaign_id == campaign_id and b.active)

    def get_bindings_for_budget(self, budget_id: str) -> tuple[CampaignBudgetBinding, ...]:
        return tuple(b for b in self._bindings.values() if b.budget_id == budget_id and b.active)

    # ------------------------------------------------------------------
    # Connector cost profiles
    # ------------------------------------------------------------------

    def register_connector_cost_profile(
        self,
        profile_id: str,
        connector_ref: str,
        *,
        cost_per_call: float = 0.0,
        cost_per_unit: float = 0.0,
        currency: str = "USD",
        unit_name: str = "call",
        monthly_minimum: float = 0.0,
        monthly_cap: float = 0.0,
        tier: str = "standard",
        metadata: dict[str, Any] | None = None,
    ) -> ConnectorCostProfile:
        if profile_id in self._connector_profiles:
            raise RuntimeCoreInvariantError(f"connector profile '{profile_id}' already exists")
        now = _now_iso()
        profile = ConnectorCostProfile(
            profile_id=profile_id,
            connector_ref=connector_ref,
            cost_per_call=cost_per_call,
            cost_per_unit=cost_per_unit,
            currency=currency,
            unit_name=unit_name,
            monthly_minimum=monthly_minimum,
            monthly_cap=monthly_cap,
            tier=tier,
            created_at=now,
            metadata=metadata or {},
        )
        self._connector_profiles[profile_id] = profile
        _emit(self._events, "connector_cost_profile_registered", {
            "profile_id": profile_id,
            "connector_ref": connector_ref,
            "cost_per_call": cost_per_call,
        }, connector_ref)
        return profile

    def get_connector_cost_profile(self, connector_ref: str) -> ConnectorCostProfile | None:
        for p in self._connector_profiles.values():
            if p.connector_ref == connector_ref:
                return p
        return None

    # ------------------------------------------------------------------
    # Approval thresholds
    # ------------------------------------------------------------------

    def set_approval_threshold(
        self,
        threshold_id: str,
        budget_id: str,
        mode: ApprovalThresholdMode,
        amount: float,
        approver_ref: str,
        *,
        auto_approve_below: float = 0.0,
    ) -> ApprovalThreshold:
        if budget_id not in self._budgets:
            raise RuntimeCoreInvariantError(f"budget '{budget_id}' not found")
        now = _now_iso()
        threshold = ApprovalThreshold(
            threshold_id=threshold_id,
            budget_id=budget_id,
            mode=mode,
            amount=amount,
            currency=self._budgets[budget_id].currency,
            approver_ref=approver_ref,
            auto_approve_below=auto_approve_below,
            created_at=now,
        )
        self._thresholds[threshold_id] = threshold
        _emit(self._events, "approval_threshold_set", {
            "threshold_id": threshold_id,
            "budget_id": budget_id,
            "amount": amount,
        }, budget_id)
        return threshold

    def get_thresholds_for_budget(self, budget_id: str) -> tuple[ApprovalThreshold, ...]:
        return tuple(t for t in self._thresholds.values() if t.budget_id == budget_id)

    # ------------------------------------------------------------------
    # Budget reservation (hold funds before spend)
    # ------------------------------------------------------------------

    def reserve_budget(
        self,
        reservation_id: str,
        budget_id: str,
        amount: float,
        category: CostCategory,
        *,
        campaign_ref: str = "",
        step_ref: str = "",
        connector_ref: str = "",
        reason: str = "",
    ) -> BudgetDecision:
        """Reserve funds from a budget. Returns a BudgetDecision with disposition."""
        if reservation_id in self._reservations:
            raise RuntimeCoreInvariantError(f"reservation '{reservation_id}' already exists")
        budget = self._budgets.get(budget_id)
        if budget is None:
            raise RuntimeCoreInvariantError(f"budget '{budget_id}' not found")
        if amount < 0:
            raise RuntimeCoreInvariantError("reservation amount must be non-negative")

        now = _now_iso()
        available = budget.limit_amount - budget.consumed_amount - budget.reserved_amount

        # Check currency consistency
        # (currency is validated at contract level via _require_currency)

        # Check hard stop
        new_utilization = (budget.consumed_amount + budget.reserved_amount + amount) / budget.limit_amount if budget.limit_amount > 0 else 1.0
        if new_utilization > budget.hard_stop_threshold:
            decision = BudgetDecision(
                decision_id=stable_identifier("bdec", {"rid": reservation_id, "ts": now}),
                budget_id=budget_id,
                disposition=ChargeDisposition.DENIED_HARD_STOP,
                requested_amount=amount,
                available_amount=available,
                currency=budget.currency,
                reason=f"hard stop: utilization would be {new_utilization:.2%}, threshold is {budget.hard_stop_threshold:.2%}",
                decided_at=now,
            )
            self._decisions.append(decision)
            self._hard_stops_triggered += 1
            _emit(self._events, "budget_hard_stop", {
                "budget_id": budget_id,
                "requested": amount,
                "available": available,
            }, budget_id)
            return decision

        # Check insufficient funds
        if amount > available:
            decision = BudgetDecision(
                decision_id=stable_identifier("bdec", {"rid": reservation_id, "ts": now}),
                budget_id=budget_id,
                disposition=ChargeDisposition.DENIED_INSUFFICIENT,
                requested_amount=amount,
                available_amount=available,
                currency=budget.currency,
                reason=f"insufficient funds: requested {amount}, available {available}",
                decided_at=now,
            )
            self._decisions.append(decision)
            _emit(self._events, "budget_insufficient", {
                "budget_id": budget_id,
                "requested": amount,
                "available": available,
            }, budget_id)
            return decision

        # Check approval threshold
        approval_needed, approver = self._check_approval_needed(budget_id, amount)
        if approval_needed:
            decision = BudgetDecision(
                decision_id=stable_identifier("bdec", {"rid": reservation_id, "ts": now}),
                budget_id=budget_id,
                disposition=ChargeDisposition.PENDING_APPROVAL,
                requested_amount=amount,
                available_amount=available,
                currency=budget.currency,
                reason=f"approval required from {approver}",
                reservation_id=reservation_id,
                approval_required=True,
                approver_ref=approver,
                decided_at=now,
            )
            self._decisions.append(decision)
            _emit(self._events, "budget_approval_required", {
                "budget_id": budget_id,
                "amount": amount,
                "approver": approver,
            }, budget_id)
            return decision

        # Check warning threshold
        warning = False
        if new_utilization >= budget.warning_threshold:
            warning = True
            self._warnings_issued += 1
            _emit(self._events, "budget_warning", {
                "budget_id": budget_id,
                "utilization": new_utilization,
                "threshold": budget.warning_threshold,
            }, budget_id)

        # Create reservation
        reservation = BudgetReservation(
            reservation_id=reservation_id,
            budget_id=budget_id,
            amount=amount,
            currency=budget.currency,
            category=category,
            campaign_ref=campaign_ref,
            step_ref=step_ref,
            connector_ref=connector_ref,
            reason=reason,
            created_at=now,
        )
        self._reservations[reservation_id] = reservation

        # Update budget reserved_amount
        self._update_budget_reserved(budget_id, budget.reserved_amount + amount)

        disposition = ChargeDisposition.WARNING_ISSUED if warning else ChargeDisposition.APPROVED
        decision = BudgetDecision(
            decision_id=stable_identifier("bdec", {"rid": reservation_id, "ts": now}),
            budget_id=budget_id,
            disposition=disposition,
            requested_amount=amount,
            available_amount=available - amount,
            currency=budget.currency,
            reason="reserved" if not warning else f"reserved with warning: utilization {new_utilization:.2%}",
            reservation_id=reservation_id,
            decided_at=now,
        )
        self._decisions.append(decision)
        _emit(self._events, "budget_reserved", {
            "budget_id": budget_id,
            "reservation_id": reservation_id,
            "amount": amount,
        }, budget_id)
        return decision

    # ------------------------------------------------------------------
    # Consume budget (confirm spend)
    # ------------------------------------------------------------------

    def consume_budget(
        self,
        spend_id: str,
        reservation_id: str,
        *,
        actual_amount: float | None = None,
    ) -> SpendRecord:
        """Consume a reservation, creating a spend record."""
        if spend_id in self._spend_records:
            raise RuntimeCoreInvariantError(f"spend record '{spend_id}' already exists")
        reservation = self._reservations.get(reservation_id)
        if reservation is None:
            raise RuntimeCoreInvariantError(f"reservation '{reservation_id}' not found")
        if not reservation.active:
            raise RuntimeCoreInvariantError(f"reservation '{reservation_id}' is not active")

        amount = actual_amount if actual_amount is not None else reservation.amount
        if amount < 0:
            raise RuntimeCoreInvariantError("consume amount must be non-negative")

        budget = self._budgets[reservation.budget_id]
        now = _now_iso()

        # Create spend record
        record = SpendRecord(
            spend_id=spend_id,
            budget_id=reservation.budget_id,
            category=reservation.category,
            status=SpendStatus.CONSUMED,
            amount=amount,
            currency=budget.currency,
            campaign_ref=reservation.campaign_ref,
            step_ref=reservation.step_ref,
            connector_ref=reservation.connector_ref,
            reason=reservation.reason,
            created_at=now,
        )
        self._spend_records[spend_id] = record

        # Deactivate reservation
        self._deactivate_reservation(reservation_id)

        # Update budget: move from reserved to consumed
        new_reserved = max(0.0, budget.reserved_amount - reservation.amount)
        new_consumed = budget.consumed_amount + amount
        self._update_budget_amounts(reservation.budget_id, new_consumed, new_reserved)

        # Update campaign binding if applicable
        if reservation.campaign_ref:
            self._update_binding_consumed(reservation.campaign_ref, amount)

        _emit(self._events, "budget_consumed", {
            "budget_id": reservation.budget_id,
            "spend_id": spend_id,
            "amount": amount,
            "reservation_id": reservation_id,
        }, reservation.budget_id)
        return record

    # ------------------------------------------------------------------
    # Release budget (cancel reservation)
    # ------------------------------------------------------------------

    def release_budget(
        self,
        reservation_id: str,
        *,
        reason: str = "released",
    ) -> SpendRecord:
        """Release a reservation, returning funds to available."""
        reservation = self._reservations.get(reservation_id)
        if reservation is None:
            raise RuntimeCoreInvariantError(f"reservation '{reservation_id}' not found")
        if not reservation.active:
            raise RuntimeCoreInvariantError(f"reservation '{reservation_id}' is not active")

        budget = self._budgets[reservation.budget_id]
        now = _now_iso()

        # Create released spend record
        record = SpendRecord(
            spend_id=stable_identifier("spr", {"rid": reservation_id, "ts": now}),
            budget_id=reservation.budget_id,
            category=reservation.category,
            status=SpendStatus.RELEASED,
            amount=reservation.amount,
            currency=budget.currency,
            campaign_ref=reservation.campaign_ref,
            step_ref=reservation.step_ref,
            connector_ref=reservation.connector_ref,
            reason=reason,
            created_at=now,
        )
        self._spend_records[record.spend_id] = record

        # Deactivate reservation
        self._deactivate_reservation(reservation_id)

        # Update budget: reduce reserved
        new_reserved = max(0.0, budget.reserved_amount - reservation.amount)
        self._update_budget_reserved(reservation.budget_id, new_reserved)

        _emit(self._events, "budget_released", {
            "budget_id": reservation.budget_id,
            "reservation_id": reservation_id,
            "amount": reservation.amount,
            "reason": reason,
        }, reservation.budget_id)
        return record

    # ------------------------------------------------------------------
    # Cost estimation
    # ------------------------------------------------------------------

    def estimate_cost(
        self,
        estimate_id: str,
        category: CostCategory,
        *,
        connector_ref: str = "",
        campaign_ref: str = "",
        step_ref: str = "",
        units: int = 1,
    ) -> CostEstimate:
        """Estimate cost for an operation based on connector profiles."""
        now = _now_iso()
        amount = 0.0
        confidence = 1.0

        if connector_ref:
            profile = self.get_connector_cost_profile(connector_ref)
            if profile:
                amount = profile.cost_per_call + (profile.cost_per_unit * units)
                currency = profile.currency
            else:
                # No profile — zero cost with low confidence
                amount = 0.0
                confidence = 0.5
                currency = "USD"
        else:
            currency = "USD"

        estimate = CostEstimate(
            estimate_id=estimate_id,
            category=category,
            estimated_amount=amount,
            currency=currency,
            confidence=confidence,
            connector_ref=connector_ref,
            campaign_ref=campaign_ref,
            step_ref=step_ref,
            created_at=now,
        )
        _emit(self._events, "cost_estimated", {
            "estimate_id": estimate_id,
            "amount": amount,
            "category": category.value,
        }, estimate_id)
        return estimate

    # ------------------------------------------------------------------
    # Spend forecast
    # ------------------------------------------------------------------

    def forecast_spend(
        self,
        forecast_id: str,
        budget_id: str,
        period_start: str,
        period_end: str,
        *,
        breakdown: dict[str, float] | None = None,
    ) -> SpendForecast:
        """Project future spend for a budget based on current burn rate."""
        budget = self._budgets.get(budget_id)
        if budget is None:
            raise RuntimeCoreInvariantError(f"budget '{budget_id}' not found")

        now = _now_iso()
        # Simple projection: current consumed + active reservations
        active_res_amount = sum(
            r.amount for r in self._reservations.values()
            if r.budget_id == budget_id and r.active
        )
        projected = budget.consumed_amount + active_res_amount

        forecast = SpendForecast(
            forecast_id=forecast_id,
            budget_id=budget_id,
            projected_amount=projected,
            currency=budget.currency,
            period_start=period_start,
            period_end=period_end,
            breakdown=breakdown or {},
            created_at=now,
        )
        self._forecasts.append(forecast)
        _emit(self._events, "spend_forecasted", {
            "budget_id": budget_id,
            "projected_amount": projected,
        }, budget_id)
        return forecast

    # ------------------------------------------------------------------
    # Budget health
    # ------------------------------------------------------------------

    def budget_health(self, budget_id: str) -> FinancialHealthSnapshot:
        """Return point-in-time financial health for a budget."""
        budget = self._budgets.get(budget_id)
        if budget is None:
            raise RuntimeCoreInvariantError(f"budget '{budget_id}' not found")

        now = _now_iso()
        available = budget.limit_amount - budget.consumed_amount - budget.reserved_amount
        utilization = (budget.consumed_amount + budget.reserved_amount) / budget.limit_amount if budget.limit_amount > 0 else 0.0

        active_res = sum(1 for r in self._reservations.values() if r.budget_id == budget_id and r.active)
        total_spends = sum(1 for s in self._spend_records.values() if s.budget_id == budget_id)

        return FinancialHealthSnapshot(
            snapshot_id=stable_identifier("fhs", {"bid": budget_id, "ts": now}),
            budget_id=budget_id,
            limit_amount=budget.limit_amount,
            consumed_amount=budget.consumed_amount,
            reserved_amount=budget.reserved_amount,
            available_amount=max(0.0, available),
            utilization=min(1.0, utilization),
            currency=budget.currency,
            warning_triggered=utilization >= budget.warning_threshold,
            hard_stop_triggered=utilization >= budget.hard_stop_threshold,
            active_reservations=active_res,
            total_spend_records=total_spends,
            captured_at=now,
        )

    # ------------------------------------------------------------------
    # Conflict detection
    # ------------------------------------------------------------------

    def find_budget_conflicts(self, budget_id: str) -> tuple[BudgetConflict, ...]:
        """Detect conflicts in a budget's state."""
        budget = self._budgets.get(budget_id)
        if budget is None:
            raise RuntimeCoreInvariantError(f"budget '{budget_id}' not found")

        now = _now_iso()
        conflicts: list[BudgetConflict] = []

        # Over-limit check
        total_committed = budget.consumed_amount + budget.reserved_amount
        if total_committed > budget.limit_amount:
            conflicts.append(BudgetConflict(
                conflict_id=stable_identifier("bcon", {"bid": budget_id, "kind": "over_limit", "ts": now}),
                budget_id=budget_id,
                kind=BudgetConflictKind.OVER_LIMIT,
                description=f"committed {total_committed} exceeds limit {budget.limit_amount}",
                severity=3,
                detected_at=now,
            ))

        # Orphaned reservations (inactive budget with active reservations)
        if not budget.active:
            active_res = [r for r in self._reservations.values() if r.budget_id == budget_id and r.active]
            if active_res:
                conflicts.append(BudgetConflict(
                    conflict_id=stable_identifier("bcon", {"bid": budget_id, "kind": "orphaned", "ts": now}),
                    budget_id=budget_id,
                    kind=BudgetConflictKind.ORPHANED_RESERVATION,
                    description=f"{len(active_res)} active reservations on inactive budget",
                    severity=2,
                    detected_at=now,
                ))

        # Threshold breach
        utilization = total_committed / budget.limit_amount if budget.limit_amount > 0 else 0.0
        if utilization >= budget.hard_stop_threshold and budget.active:
            conflicts.append(BudgetConflict(
                conflict_id=stable_identifier("bcon", {"bid": budget_id, "kind": "threshold", "ts": now}),
                budget_id=budget_id,
                kind=BudgetConflictKind.THRESHOLD_BREACH,
                description=f"utilization {utilization:.2%} at or above hard stop {budget.hard_stop_threshold:.2%}",
                severity=3,
                detected_at=now,
            ))

        return tuple(conflicts)

    # ------------------------------------------------------------------
    # Budget gating
    # ------------------------------------------------------------------

    def budget_gate(
        self,
        budget_id: str,
        requested_amount: float,
    ) -> BudgetDecision:
        """Check if a spend of requested_amount would be allowed. Read-only gate."""
        budget = self._budgets.get(budget_id)
        if budget is None:
            raise RuntimeCoreInvariantError(f"budget '{budget_id}' not found")

        now = _now_iso()
        available = budget.limit_amount - budget.consumed_amount - budget.reserved_amount

        if not budget.active:
            return BudgetDecision(
                decision_id=stable_identifier("bgate", {"bid": budget_id, "ts": now}),
                budget_id=budget_id,
                disposition=ChargeDisposition.DENIED_HARD_STOP,
                requested_amount=requested_amount,
                available_amount=available,
                currency=budget.currency,
                reason="budget is inactive",
                decided_at=now,
            )

        new_utilization = (budget.consumed_amount + budget.reserved_amount + requested_amount) / budget.limit_amount if budget.limit_amount > 0 else 1.0

        if new_utilization > budget.hard_stop_threshold:
            return BudgetDecision(
                decision_id=stable_identifier("bgate", {"bid": budget_id, "ts": now}),
                budget_id=budget_id,
                disposition=ChargeDisposition.DENIED_HARD_STOP,
                requested_amount=requested_amount,
                available_amount=available,
                currency=budget.currency,
                reason=f"hard stop: utilization would be {new_utilization:.2%}",
                decided_at=now,
            )

        if requested_amount > available:
            return BudgetDecision(
                decision_id=stable_identifier("bgate", {"bid": budget_id, "ts": now}),
                budget_id=budget_id,
                disposition=ChargeDisposition.DENIED_INSUFFICIENT,
                requested_amount=requested_amount,
                available_amount=available,
                currency=budget.currency,
                reason=f"insufficient: requested {requested_amount}, available {available}",
                decided_at=now,
            )

        approval_needed, approver = self._check_approval_needed(budget_id, requested_amount)
        if approval_needed:
            return BudgetDecision(
                decision_id=stable_identifier("bgate", {"bid": budget_id, "ts": now}),
                budget_id=budget_id,
                disposition=ChargeDisposition.PENDING_APPROVAL,
                requested_amount=requested_amount,
                available_amount=available,
                currency=budget.currency,
                reason=f"approval required from {approver}",
                approval_required=True,
                approver_ref=approver,
                decided_at=now,
            )

        disposition = ChargeDisposition.APPROVED
        reason = "approved"
        if new_utilization >= budget.warning_threshold:
            disposition = ChargeDisposition.WARNING_ISSUED
            reason = f"approved with warning: utilization would be {new_utilization:.2%}"

        return BudgetDecision(
            decision_id=stable_identifier("bgate", {"bid": budget_id, "ts": now}),
            budget_id=budget_id,
            disposition=disposition,
            requested_amount=requested_amount,
            available_amount=available,
            currency=budget.currency,
            reason=reason,
            decided_at=now,
        )

    # ------------------------------------------------------------------
    # Budget closure
    # ------------------------------------------------------------------

    def close_budget(self, budget_id: str) -> BudgetClosureReport:
        """Close a budget and produce a closure report."""
        budget = self._budgets.get(budget_id)
        if budget is None:
            raise RuntimeCoreInvariantError(f"budget '{budget_id}' not found")

        now = _now_iso()

        # Release all active reservations
        active_res = [r for r in self._reservations.values() if r.budget_id == budget_id and r.active]
        total_released = 0.0
        for res in active_res:
            self.release_budget(res.reservation_id, reason="budget closure")
            total_released += res.amount

        # Deactivate budget
        budget_obj = self._budgets[budget_id]
        self._budgets[budget_id] = BudgetEnvelope(
            budget_id=budget_obj.budget_id,
            name=budget_obj.name,
            scope=budget_obj.scope,
            scope_ref_id=budget_obj.scope_ref_id,
            currency=budget_obj.currency,
            limit_amount=budget_obj.limit_amount,
            reserved_amount=0.0,
            consumed_amount=budget_obj.consumed_amount,
            warning_threshold=budget_obj.warning_threshold,
            hard_stop_threshold=budget_obj.hard_stop_threshold,
            active=False,
            tags=budget_obj.tags,
            created_at=budget_obj.created_at,
            updated_at=now,
            metadata=dict(budget_obj.metadata),
        )

        total_spend_records = sum(1 for s in self._spend_records.values() if s.budget_id == budget_id)
        total_reservations = sum(1 for r in self._reservations.values() if r.budget_id == budget_id)

        under_budget = budget_obj.consumed_amount <= budget_obj.limit_amount
        overspend = max(0.0, budget_obj.consumed_amount - budget_obj.limit_amount)

        report = BudgetClosureReport(
            report_id=stable_identifier("bcr", {"bid": budget_id, "ts": now}),
            budget_id=budget_id,
            limit_amount=budget_obj.limit_amount,
            total_consumed=budget_obj.consumed_amount,
            total_released=total_released,
            total_reservations=total_reservations,
            total_spend_records=total_spend_records,
            currency=budget_obj.currency,
            under_budget=under_budget,
            overspend_amount=overspend,
            warnings_issued=self._warnings_issued,
            hard_stops_triggered=self._hard_stops_triggered,
            closed_at=now,
        )

        _emit(self._events, "budget_closed", {
            "budget_id": budget_id,
            "total_consumed": budget_obj.consumed_amount,
            "under_budget": under_budget,
        }, budget_id)
        return report

    # ------------------------------------------------------------------
    # Cheaper connector fallback
    # ------------------------------------------------------------------

    def find_cheapest_connector(
        self,
        connector_refs: list[str],
        budget_id: str,
    ) -> dict[str, Any]:
        """Find the cheapest viable connector under budget pressure."""
        budget = self._budgets.get(budget_id)
        if budget is None:
            raise RuntimeCoreInvariantError(f"budget '{budget_id}' not found")

        available = budget.limit_amount - budget.consumed_amount - budget.reserved_amount
        candidates: list[dict[str, Any]] = []

        for ref in connector_refs:
            profile = self.get_connector_cost_profile(ref)
            if profile:
                cost = profile.cost_per_call
                viable = cost <= available
                candidates.append({
                    "connector_ref": ref,
                    "cost_per_call": cost,
                    "currency": profile.currency,
                    "viable": viable,
                })
            else:
                candidates.append({
                    "connector_ref": ref,
                    "cost_per_call": 0.0,
                    "currency": budget.currency,
                    "viable": True,
                })

        # Sort by cost ascending, viable first
        viable_candidates = [c for c in candidates if c["viable"]]
        viable_candidates.sort(key=lambda c: c["cost_per_call"])

        chosen = viable_candidates[0] if viable_candidates else None

        return {
            "budget_id": budget_id,
            "available": available,
            "candidates": candidates,
            "chosen": chosen,
            "all_blocked": not bool(viable_candidates),
        }

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get_spend_records(self, budget_id: str) -> tuple[SpendRecord, ...]:
        return tuple(s for s in self._spend_records.values() if s.budget_id == budget_id)

    def get_active_reservations(self, budget_id: str) -> tuple[BudgetReservation, ...]:
        return tuple(r for r in self._reservations.values() if r.budget_id == budget_id and r.active)

    def get_decisions(self, budget_id: str) -> tuple[BudgetDecision, ...]:
        return tuple(d for d in self._decisions if d.budget_id == budget_id)

    @property
    def budget_count(self) -> int:
        return len(self._budgets)

    @property
    def reservation_count(self) -> int:
        return sum(1 for r in self._reservations.values() if r.active)

    @property
    def spend_record_count(self) -> int:
        return len(self._spend_records)

    # ------------------------------------------------------------------
    # State hash
    # ------------------------------------------------------------------

    def state_hash(self) -> str:
        parts: list[str] = []
        for k in sorted(self._budgets):
            b = self._budgets[k]
            parts.append(f"bud:{k}:{b.consumed_amount}:{b.reserved_amount}")
        for k in sorted(self._spend_records):
            parts.append(f"spd:{k}:{self._spend_records[k].status.value}")
        for k in sorted(self._reservations):
            parts.append(f"rsv:{k}:{self._reservations[k].active}")
        for k in sorted(self._bindings):
            parts.append(f"bnd:{k}:{self._bindings[k].budget_id}")
        for k in sorted(self._connector_profiles):
            parts.append(f"cpr:{k}:{self._connector_profiles[k].cost_per_call}")
        for k in sorted(self._thresholds):
            parts.append(f"thr:{k}:{self._thresholds[k].mode.value}")
        parts.append(f"decisions={len(self._decisions)}")
        parts.append(f"conflicts={len(self._conflicts)}")
        parts.append(f"forecasts={len(self._forecasts)}")
        digest = sha256("|".join(parts).encode()).hexdigest()
        return digest

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _update_budget_reserved(self, budget_id: str, new_reserved: float) -> None:
        b = self._budgets[budget_id]
        self._budgets[budget_id] = BudgetEnvelope(
            budget_id=b.budget_id,
            name=b.name,
            scope=b.scope,
            scope_ref_id=b.scope_ref_id,
            currency=b.currency,
            limit_amount=b.limit_amount,
            reserved_amount=new_reserved,
            consumed_amount=b.consumed_amount,
            warning_threshold=b.warning_threshold,
            hard_stop_threshold=b.hard_stop_threshold,
            active=b.active,
            tags=b.tags,
            created_at=b.created_at,
            updated_at=_now_iso(),
            metadata=dict(b.metadata),
        )

    def _update_budget_amounts(self, budget_id: str, new_consumed: float, new_reserved: float) -> None:
        b = self._budgets[budget_id]
        self._budgets[budget_id] = BudgetEnvelope(
            budget_id=b.budget_id,
            name=b.name,
            scope=b.scope,
            scope_ref_id=b.scope_ref_id,
            currency=b.currency,
            limit_amount=b.limit_amount,
            reserved_amount=new_reserved,
            consumed_amount=new_consumed,
            warning_threshold=b.warning_threshold,
            hard_stop_threshold=b.hard_stop_threshold,
            active=b.active,
            tags=b.tags,
            created_at=b.created_at,
            updated_at=_now_iso(),
            metadata=dict(b.metadata),
        )

    def _deactivate_reservation(self, reservation_id: str) -> None:
        r = self._reservations[reservation_id]
        self._reservations[reservation_id] = BudgetReservation(
            reservation_id=r.reservation_id,
            budget_id=r.budget_id,
            amount=r.amount,
            currency=r.currency,
            category=r.category,
            campaign_ref=r.campaign_ref,
            step_ref=r.step_ref,
            connector_ref=r.connector_ref,
            active=False,
            reason=r.reason,
            created_at=r.created_at,
            expires_at=r.expires_at,
        )

    def _update_binding_consumed(self, campaign_ref: str, amount: float) -> None:
        for bid, binding in list(self._bindings.items()):
            if binding.campaign_id == campaign_ref and binding.active:
                new_consumed = binding.consumed_amount + amount
                self._bindings[bid] = CampaignBudgetBinding(
                    binding_id=binding.binding_id,
                    campaign_id=binding.campaign_id,
                    budget_id=binding.budget_id,
                    allocated_amount=binding.allocated_amount,
                    consumed_amount=min(new_consumed, binding.allocated_amount),
                    currency=binding.currency,
                    active=binding.active,
                    created_at=binding.created_at,
                )
                break

    def _check_approval_needed(self, budget_id: str, amount: float) -> tuple[bool, str]:
        """Check if amount triggers an approval threshold. Returns (needed, approver)."""
        budget = self._budgets[budget_id]
        for threshold in self._thresholds.values():
            if threshold.budget_id != budget_id:
                continue

            if threshold.mode == ApprovalThresholdMode.PER_TRANSACTION:
                if amount >= threshold.amount and amount >= threshold.auto_approve_below:
                    return True, threshold.approver_ref

            elif threshold.mode == ApprovalThresholdMode.CUMULATIVE:
                total = budget.consumed_amount + budget.reserved_amount + amount
                if total >= threshold.amount:
                    return True, threshold.approver_ref

            elif threshold.mode == ApprovalThresholdMode.PERCENTAGE_OF_LIMIT:
                if budget.limit_amount > 0:
                    pct = (budget.consumed_amount + budget.reserved_amount + amount) / budget.limit_amount
                    if pct >= threshold.amount / 100.0:
                        return True, threshold.approver_ref

            elif threshold.mode == ApprovalThresholdMode.REMAINING_BUDGET:
                remaining = budget.limit_amount - budget.consumed_amount - budget.reserved_amount
                if remaining - amount < threshold.amount:
                    return True, threshold.approver_ref

        return False, ""
