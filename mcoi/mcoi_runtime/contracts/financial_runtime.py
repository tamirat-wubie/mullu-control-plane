"""Purpose: financial / cost / budget runtime contracts.
Governance scope: typed descriptors for budget envelopes, spend records,
    cost estimates, connector cost profiles, campaign budget bindings,
    approval thresholds, budget reservations, spend forecasts, budget
    conflicts, budget decisions, financial health snapshots, and budget
    closure reports.
Dependencies: _base contract utilities.
Invariants:
  - Every budget has explicit scope and currency.
  - consumed + reserved ≤ limit.
  - No negative spend amounts.
  - Currency consistency is enforced per budget.
  - Immutable returns, deterministic serialization.
  - All outputs are frozen.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Mapping

from ._base import (
    ContractRecord,
    freeze_value,
    require_datetime_text,
    require_non_empty_text,
    require_non_negative_float,
    require_non_negative_int,
    require_unit_float,
)


def _parse_datetime_text(value: str, field_name: str) -> datetime:
    """Parse a validated datetime text deterministically."""
    require_datetime_text(value, field_name)
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _require_period_start_before_end(period_start: str, period_end: str) -> None:
    """Validate that a financial period has a strict forward ordering."""
    start_dt = _parse_datetime_text(period_start, "period_start")
    end_dt = _parse_datetime_text(period_end, "period_end")
    if start_dt >= end_dt:
        raise ValueError("period_start must be before period_end")


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class BudgetScope(Enum):
    """Scope at which a budget envelope applies."""
    GLOBAL = "global"
    PORTFOLIO = "portfolio"
    CAMPAIGN = "campaign"
    CONNECTOR = "connector"
    CHANNEL = "channel"
    TEAM = "team"
    FUNCTION = "function"


class CostCategory(Enum):
    """Category of a cost or spend record."""
    CONNECTOR_CALL = "connector_call"
    COMMUNICATION = "communication"
    ARTIFACT_PARSING = "artifact_parsing"
    PROVIDER_ROUTING = "provider_routing"
    COMPUTE = "compute"
    HUMAN_LABOR = "human_labor"
    ESCALATION = "escalation"
    OVERHEAD = "overhead"


class SpendStatus(Enum):
    """Lifecycle status of a spend record."""
    RESERVED = "reserved"
    CONSUMED = "consumed"
    RELEASED = "released"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"


class ApprovalThresholdMode(Enum):
    """How approval thresholds are evaluated."""
    PER_TRANSACTION = "per_transaction"
    CUMULATIVE = "cumulative"
    PERCENTAGE_OF_LIMIT = "percentage_of_limit"
    REMAINING_BUDGET = "remaining_budget"


class ChargeDisposition(Enum):
    """Outcome disposition for a budget decision."""
    APPROVED = "approved"
    DENIED_HARD_STOP = "denied_hard_stop"
    DENIED_INSUFFICIENT = "denied_insufficient"
    PENDING_APPROVAL = "pending_approval"
    WARNING_ISSUED = "warning_issued"
    FALLBACK_SUGGESTED = "fallback_suggested"


class BudgetConflictKind(Enum):
    """Kind of budget conflict detected."""
    OVER_LIMIT = "over_limit"
    CURRENCY_MISMATCH = "currency_mismatch"
    DOUBLE_RESERVATION = "double_reservation"
    ORPHANED_RESERVATION = "orphaned_reservation"
    NEGATIVE_BALANCE = "negative_balance"
    THRESHOLD_BREACH = "threshold_breach"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _require_currency(value: str, field_name: str) -> str:
    """Validate currency is a non-empty uppercase string (e.g. USD, EUR)."""
    v = require_non_empty_text(value, field_name)
    if not v.isalpha() or not v.isupper() or len(v) < 3 or len(v) > 3:
        raise ValueError("currency must be a 3-letter uppercase code")
    return v


def _require_amounts_consistent(
    consumed: float, reserved: float, limit: float,
) -> None:
    """Validate consumed + reserved ≤ limit."""
    if consumed + reserved > limit:
        raise ValueError("consumed and reserved amounts exceed limit")


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class BudgetEnvelope(ContractRecord):
    """A budget envelope with scope, currency, limits, and thresholds."""

    budget_id: str = ""
    name: str = ""
    scope: BudgetScope = BudgetScope.CAMPAIGN
    scope_ref_id: str = ""
    currency: str = "USD"
    limit_amount: float = 0.0
    reserved_amount: float = 0.0
    consumed_amount: float = 0.0
    warning_threshold: float = 0.8
    hard_stop_threshold: float = 1.0
    active: bool = True
    tags: tuple[str, ...] = ()
    created_at: str = ""
    updated_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "budget_id", require_non_empty_text(self.budget_id, "budget_id"))
        object.__setattr__(self, "name", require_non_empty_text(self.name, "name"))
        if not isinstance(self.scope, BudgetScope):
            raise ValueError("scope must be a BudgetScope")
        object.__setattr__(self, "scope_ref_id", require_non_empty_text(self.scope_ref_id, "scope_ref_id"))
        object.__setattr__(self, "currency", _require_currency(self.currency, "currency"))
        object.__setattr__(self, "limit_amount", require_non_negative_float(self.limit_amount, "limit_amount"))
        object.__setattr__(self, "reserved_amount", require_non_negative_float(self.reserved_amount, "reserved_amount"))
        object.__setattr__(self, "consumed_amount", require_non_negative_float(self.consumed_amount, "consumed_amount"))
        _require_amounts_consistent(self.consumed_amount, self.reserved_amount, self.limit_amount)
        object.__setattr__(self, "warning_threshold", require_unit_float(self.warning_threshold, "warning_threshold"))
        object.__setattr__(self, "hard_stop_threshold", require_unit_float(self.hard_stop_threshold, "hard_stop_threshold"))
        if self.warning_threshold > self.hard_stop_threshold:
            raise ValueError("warning threshold must not exceed hard stop threshold")
        if not isinstance(self.active, bool):
            raise ValueError("active must be a boolean")
        object.__setattr__(self, "tags", freeze_value(list(self.tags)))
        require_datetime_text(self.created_at, "created_at")
        require_datetime_text(self.updated_at, "updated_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class SpendRecord(ContractRecord):
    """A single spend event against a budget."""

    spend_id: str = ""
    budget_id: str = ""
    category: CostCategory = CostCategory.CONNECTOR_CALL
    status: SpendStatus = SpendStatus.RESERVED
    amount: float = 0.0
    currency: str = "USD"
    campaign_ref: str = ""
    step_ref: str = ""
    connector_ref: str = ""
    reason: str = ""
    created_at: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "spend_id", require_non_empty_text(self.spend_id, "spend_id"))
        object.__setattr__(self, "budget_id", require_non_empty_text(self.budget_id, "budget_id"))
        if not isinstance(self.category, CostCategory):
            raise ValueError("category must be a CostCategory")
        if not isinstance(self.status, SpendStatus):
            raise ValueError("status must be a SpendStatus")
        object.__setattr__(self, "amount", require_non_negative_float(self.amount, "amount"))
        object.__setattr__(self, "currency", _require_currency(self.currency, "currency"))
        require_datetime_text(self.created_at, "created_at")


@dataclass(frozen=True, slots=True)
class CostEstimate(ContractRecord):
    """Pre-action cost estimate for budgeting decisions."""

    estimate_id: str = ""
    category: CostCategory = CostCategory.CONNECTOR_CALL
    estimated_amount: float = 0.0
    currency: str = "USD"
    confidence: float = 1.0
    connector_ref: str = ""
    campaign_ref: str = ""
    step_ref: str = ""
    created_at: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "estimate_id", require_non_empty_text(self.estimate_id, "estimate_id"))
        if not isinstance(self.category, CostCategory):
            raise ValueError("category must be a CostCategory")
        object.__setattr__(self, "estimated_amount", require_non_negative_float(self.estimated_amount, "estimated_amount"))
        object.__setattr__(self, "currency", _require_currency(self.currency, "currency"))
        object.__setattr__(self, "confidence", require_unit_float(self.confidence, "confidence"))
        require_datetime_text(self.created_at, "created_at")


@dataclass(frozen=True, slots=True)
class ConnectorCostProfile(ContractRecord):
    """Cost profile for an external connector."""

    profile_id: str = ""
    connector_ref: str = ""
    cost_per_call: float = 0.0
    cost_per_unit: float = 0.0
    currency: str = "USD"
    unit_name: str = "call"
    monthly_minimum: float = 0.0
    monthly_cap: float = 0.0
    tier: str = "standard"
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "profile_id", require_non_empty_text(self.profile_id, "profile_id"))
        object.__setattr__(self, "connector_ref", require_non_empty_text(self.connector_ref, "connector_ref"))
        object.__setattr__(self, "cost_per_call", require_non_negative_float(self.cost_per_call, "cost_per_call"))
        object.__setattr__(self, "cost_per_unit", require_non_negative_float(self.cost_per_unit, "cost_per_unit"))
        object.__setattr__(self, "currency", _require_currency(self.currency, "currency"))
        object.__setattr__(self, "unit_name", require_non_empty_text(self.unit_name, "unit_name"))
        object.__setattr__(self, "monthly_minimum", require_non_negative_float(self.monthly_minimum, "monthly_minimum"))
        object.__setattr__(self, "monthly_cap", require_non_negative_float(self.monthly_cap, "monthly_cap"))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class CampaignBudgetBinding(ContractRecord):
    """Binding between a campaign and a budget envelope."""

    binding_id: str = ""
    campaign_id: str = ""
    budget_id: str = ""
    allocated_amount: float = 0.0
    consumed_amount: float = 0.0
    currency: str = "USD"
    active: bool = True
    created_at: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "binding_id", require_non_empty_text(self.binding_id, "binding_id"))
        object.__setattr__(self, "campaign_id", require_non_empty_text(self.campaign_id, "campaign_id"))
        object.__setattr__(self, "budget_id", require_non_empty_text(self.budget_id, "budget_id"))
        object.__setattr__(self, "allocated_amount", require_non_negative_float(self.allocated_amount, "allocated_amount"))
        object.__setattr__(self, "consumed_amount", require_non_negative_float(self.consumed_amount, "consumed_amount"))
        if self.consumed_amount > self.allocated_amount:
            raise ValueError("consumed amount must not exceed allocated amount")
        object.__setattr__(self, "currency", _require_currency(self.currency, "currency"))
        if not isinstance(self.active, bool):
            raise ValueError("active must be a boolean")
        require_datetime_text(self.created_at, "created_at")


@dataclass(frozen=True, slots=True)
class ApprovalThreshold(ContractRecord):
    """Configuration for spend approval thresholds."""

    threshold_id: str = ""
    budget_id: str = ""
    mode: ApprovalThresholdMode = ApprovalThresholdMode.PER_TRANSACTION
    amount: float = 0.0
    currency: str = "USD"
    approver_ref: str = ""
    auto_approve_below: float = 0.0
    created_at: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "threshold_id", require_non_empty_text(self.threshold_id, "threshold_id"))
        object.__setattr__(self, "budget_id", require_non_empty_text(self.budget_id, "budget_id"))
        if not isinstance(self.mode, ApprovalThresholdMode):
            raise ValueError("mode must be an ApprovalThresholdMode")
        object.__setattr__(self, "amount", require_non_negative_float(self.amount, "amount"))
        object.__setattr__(self, "currency", _require_currency(self.currency, "currency"))
        object.__setattr__(self, "approver_ref", require_non_empty_text(self.approver_ref, "approver_ref"))
        object.__setattr__(self, "auto_approve_below", require_non_negative_float(self.auto_approve_below, "auto_approve_below"))
        if self.auto_approve_below > self.amount:
            raise ValueError("auto-approve threshold must not exceed approval amount")
        require_datetime_text(self.created_at, "created_at")


@dataclass(frozen=True, slots=True)
class BudgetReservation(ContractRecord):
    """A hold on budget funds before spend is confirmed."""

    reservation_id: str = ""
    budget_id: str = ""
    amount: float = 0.0
    currency: str = "USD"
    category: CostCategory = CostCategory.CONNECTOR_CALL
    campaign_ref: str = ""
    step_ref: str = ""
    connector_ref: str = ""
    active: bool = True
    reason: str = ""
    created_at: str = ""
    expires_at: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "reservation_id", require_non_empty_text(self.reservation_id, "reservation_id"))
        object.__setattr__(self, "budget_id", require_non_empty_text(self.budget_id, "budget_id"))
        object.__setattr__(self, "amount", require_non_negative_float(self.amount, "amount"))
        object.__setattr__(self, "currency", _require_currency(self.currency, "currency"))
        if not isinstance(self.category, CostCategory):
            raise ValueError("category must be a CostCategory")
        if not isinstance(self.active, bool):
            raise ValueError("active must be a boolean")
        require_datetime_text(self.created_at, "created_at")


@dataclass(frozen=True, slots=True)
class SpendForecast(ContractRecord):
    """Projected future spend for a budget."""

    forecast_id: str = ""
    budget_id: str = ""
    projected_amount: float = 0.0
    currency: str = "USD"
    period_start: str = ""
    period_end: str = ""
    confidence: float = 1.0
    breakdown: Mapping[str, float] = field(default_factory=dict)
    created_at: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "forecast_id", require_non_empty_text(self.forecast_id, "forecast_id"))
        object.__setattr__(self, "budget_id", require_non_empty_text(self.budget_id, "budget_id"))
        object.__setattr__(self, "projected_amount", require_non_negative_float(self.projected_amount, "projected_amount"))
        object.__setattr__(self, "currency", _require_currency(self.currency, "currency"))
        _require_period_start_before_end(self.period_start, self.period_end)
        object.__setattr__(self, "confidence", require_unit_float(self.confidence, "confidence"))
        object.__setattr__(self, "breakdown", freeze_value(dict(self.breakdown)))
        require_datetime_text(self.created_at, "created_at")


@dataclass(frozen=True, slots=True)
class BudgetConflict(ContractRecord):
    """A detected conflict in budget state."""

    conflict_id: str = ""
    budget_id: str = ""
    kind: BudgetConflictKind = BudgetConflictKind.OVER_LIMIT
    description: str = ""
    severity: int = 1
    detected_at: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "conflict_id", require_non_empty_text(self.conflict_id, "conflict_id"))
        object.__setattr__(self, "budget_id", require_non_empty_text(self.budget_id, "budget_id"))
        if not isinstance(self.kind, BudgetConflictKind):
            raise ValueError("kind must be a BudgetConflictKind")
        object.__setattr__(self, "severity", require_non_negative_int(self.severity, "severity"))
        require_datetime_text(self.detected_at, "detected_at")


@dataclass(frozen=True, slots=True)
class BudgetDecision(ContractRecord):
    """Result of a budget gate check."""

    decision_id: str = ""
    budget_id: str = ""
    disposition: ChargeDisposition = ChargeDisposition.APPROVED
    requested_amount: float = 0.0
    available_amount: float = 0.0
    currency: str = "USD"
    reason: str = ""
    reservation_id: str = ""
    approval_required: bool = False
    approver_ref: str = ""
    decided_at: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "decision_id", require_non_empty_text(self.decision_id, "decision_id"))
        object.__setattr__(self, "budget_id", require_non_empty_text(self.budget_id, "budget_id"))
        if not isinstance(self.disposition, ChargeDisposition):
            raise ValueError("disposition must be a ChargeDisposition")
        object.__setattr__(self, "requested_amount", require_non_negative_float(self.requested_amount, "requested_amount"))
        object.__setattr__(self, "available_amount", require_non_negative_float(self.available_amount, "available_amount"))
        object.__setattr__(self, "currency", _require_currency(self.currency, "currency"))
        if not isinstance(self.approval_required, bool):
            raise ValueError("approval_required must be a boolean")
        if self.approval_required and not self.approver_ref:
            raise ValueError("approver_ref must be non-empty when approval_required is True")
        require_datetime_text(self.decided_at, "decided_at")


@dataclass(frozen=True, slots=True)
class FinancialHealthSnapshot(ContractRecord):
    """Point-in-time financial health of a budget."""

    snapshot_id: str = ""
    budget_id: str = ""
    limit_amount: float = 0.0
    consumed_amount: float = 0.0
    reserved_amount: float = 0.0
    available_amount: float = 0.0
    utilization: float = 0.0
    currency: str = "USD"
    warning_triggered: bool = False
    hard_stop_triggered: bool = False
    active_reservations: int = 0
    total_spend_records: int = 0
    captured_at: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "snapshot_id", require_non_empty_text(self.snapshot_id, "snapshot_id"))
        object.__setattr__(self, "budget_id", require_non_empty_text(self.budget_id, "budget_id"))
        object.__setattr__(self, "limit_amount", require_non_negative_float(self.limit_amount, "limit_amount"))
        object.__setattr__(self, "consumed_amount", require_non_negative_float(self.consumed_amount, "consumed_amount"))
        object.__setattr__(self, "reserved_amount", require_non_negative_float(self.reserved_amount, "reserved_amount"))
        object.__setattr__(self, "available_amount", require_non_negative_float(self.available_amount, "available_amount"))
        object.__setattr__(self, "utilization", require_unit_float(self.utilization, "utilization"))
        object.__setattr__(self, "currency", _require_currency(self.currency, "currency"))
        if not isinstance(self.warning_triggered, bool):
            raise ValueError("warning_triggered must be a boolean")
        if not isinstance(self.hard_stop_triggered, bool):
            raise ValueError("hard_stop_triggered must be a boolean")
        object.__setattr__(self, "active_reservations", require_non_negative_int(self.active_reservations, "active_reservations"))
        object.__setattr__(self, "total_spend_records", require_non_negative_int(self.total_spend_records, "total_spend_records"))
        require_datetime_text(self.captured_at, "captured_at")


@dataclass(frozen=True, slots=True)
class BudgetClosureReport(ContractRecord):
    """Final closure report for a budget envelope."""

    report_id: str = ""
    budget_id: str = ""
    limit_amount: float = 0.0
    total_consumed: float = 0.0
    total_released: float = 0.0
    total_reservations: int = 0
    total_spend_records: int = 0
    currency: str = "USD"
    under_budget: bool = True
    overspend_amount: float = 0.0
    warnings_issued: int = 0
    hard_stops_triggered: int = 0
    closed_at: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "report_id", require_non_empty_text(self.report_id, "report_id"))
        object.__setattr__(self, "budget_id", require_non_empty_text(self.budget_id, "budget_id"))
        object.__setattr__(self, "limit_amount", require_non_negative_float(self.limit_amount, "limit_amount"))
        object.__setattr__(self, "total_consumed", require_non_negative_float(self.total_consumed, "total_consumed"))
        object.__setattr__(self, "total_released", require_non_negative_float(self.total_released, "total_released"))
        object.__setattr__(self, "total_reservations", require_non_negative_int(self.total_reservations, "total_reservations"))
        object.__setattr__(self, "total_spend_records", require_non_negative_int(self.total_spend_records, "total_spend_records"))
        object.__setattr__(self, "currency", _require_currency(self.currency, "currency"))
        if not isinstance(self.under_budget, bool):
            raise ValueError("under_budget must be a boolean")
        object.__setattr__(self, "overspend_amount", require_non_negative_float(self.overspend_amount, "overspend_amount"))
        object.__setattr__(self, "warnings_issued", require_non_negative_int(self.warnings_issued, "warnings_issued"))
        object.__setattr__(self, "hard_stops_triggered", require_non_negative_int(self.hard_stops_triggered, "hard_stops_triggered"))
        require_datetime_text(self.closed_at, "closed_at")
