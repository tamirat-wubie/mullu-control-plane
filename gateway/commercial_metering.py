"""Gateway commercial metering foundation.

Purpose: convert governed platform activity into tenant usage, provider cost,
    plan-limit, invoice-readiness, and gross-margin evidence.
Governance scope: tenant metering, pricing dimensions, provider-cost accounting,
    commercial limit decisions, invoice readiness, and operator margin proof.
Dependencies: dataclasses, enum, decimal, typing, and command-spine hashing.
Invariants:
  - Usage is tenant-bound, dimension-bound, and non-negative.
  - Provider cost is never negative and is tied to tenant and capability scope.
  - Plan-limit excess fails closed before invoice readiness is claimed.
  - Gross-margin evidence is explicit whenever revenue is recognized.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from decimal import Decimal, ROUND_HALF_UP
from enum import StrEnum
from typing import Any

from gateway.command_spine import canonical_hash


class UsageDimension(StrEnum):
    """Commercial pricing and metering dimensions."""

    GOVERNED_ACTION = "governed_action"
    CERTIFIED_CAPABILITY = "certified_capability"
    CONNECTOR_INVOCATION = "connector_invocation"
    WORKFLOW_RUN = "workflow_run"
    APPROVAL_CASE = "approval_case"
    AUDIT_EXPORT = "audit_export"
    PROVIDER_COST_PASS_THROUGH = "provider_cost_pass_through"


class CommercialVerdict(StrEnum):
    """Commercial admission verdict."""

    ALLOW = "allow"
    DENY = "deny"
    REVIEW = "review"


@dataclass(frozen=True, slots=True)
class PlanLimit:
    """Limit for one commercial usage dimension."""

    dimension: UsageDimension
    included_quantity: Decimal
    overage_unit_price_usd: Decimal

    def __post_init__(self) -> None:
        if not isinstance(self.dimension, UsageDimension):
            raise ValueError("usage_dimension_invalid")
        object.__setattr__(self, "included_quantity", _money(self.included_quantity, "included_quantity"))
        object.__setattr__(self, "overage_unit_price_usd", _money(self.overage_unit_price_usd, "overage_unit_price_usd"))


@dataclass(frozen=True, slots=True)
class PricingPlan:
    """Tenant-facing pricing plan with explicit meter dimensions."""

    plan_id: str
    name: str
    base_price_monthly_usd: Decimal
    limits: tuple[PlanLimit, ...]
    minimum_gross_margin_percent: Decimal
    plan_hash: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_text(self.plan_id, "plan_id")
        _require_text(self.name, "name")
        object.__setattr__(self, "base_price_monthly_usd", _money(self.base_price_monthly_usd, "base_price_monthly_usd"))
        object.__setattr__(self, "minimum_gross_margin_percent", _money(self.minimum_gross_margin_percent, "minimum_gross_margin_percent"))
        if self.minimum_gross_margin_percent > Decimal("100.00"):
            raise ValueError("minimum_gross_margin_percent_out_of_range")
        limits = tuple(self.limits)
        if not limits:
            raise ValueError("plan_limits_required")
        if len({limit.dimension for limit in limits}) != len(limits):
            raise ValueError("plan_limit_dimensions_must_be_unique")
        object.__setattr__(self, "limits", limits)
        object.__setattr__(self, "metadata", dict(self.metadata))

    def to_json_dict(self) -> dict[str, Any]:
        """Return a schema-oriented JSON object."""
        return _json_ready(asdict(self))


@dataclass(frozen=True, slots=True)
class TenantCommercialAccount:
    """Commercial account binding a tenant to a pricing plan."""

    account_id: str
    tenant_id: str
    plan_id: str
    billing_currency: str
    billing_period_start: str
    billing_period_end: str
    account_hash: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in ("account_id", "tenant_id", "plan_id", "billing_currency", "billing_period_start", "billing_period_end"):
            _require_text(getattr(self, field_name), field_name)
        if self.billing_currency != "USD":
            raise ValueError("only_usd_billing_supported")
        object.__setattr__(self, "metadata", dict(self.metadata))

    def to_json_dict(self) -> dict[str, Any]:
        """Return a schema-oriented JSON object."""
        return _json_ready(asdict(self))


@dataclass(frozen=True, slots=True)
class UsageRecord:
    """Tenant usage event for one priced dimension."""

    usage_id: str
    tenant_id: str
    dimension: UsageDimension
    quantity: Decimal
    source_ref: str
    occurred_at: str
    usage_hash: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in ("usage_id", "tenant_id", "source_ref", "occurred_at"):
            _require_text(getattr(self, field_name), field_name)
        if not isinstance(self.dimension, UsageDimension):
            raise ValueError("usage_dimension_invalid")
        object.__setattr__(self, "quantity", _money(self.quantity, "quantity"))
        object.__setattr__(self, "metadata", dict(self.metadata))

    def to_json_dict(self) -> dict[str, Any]:
        """Return a schema-oriented JSON object."""
        return _json_ready(asdict(self))


@dataclass(frozen=True, slots=True)
class ProviderCostRecord:
    """Provider cost event tied to tenant and capability scope."""

    cost_id: str
    tenant_id: str
    provider: str
    capability: str
    amount_usd: Decimal
    source_ref: str
    incurred_at: str
    cost_hash: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in ("cost_id", "tenant_id", "provider", "capability", "source_ref", "incurred_at"):
            _require_text(getattr(self, field_name), field_name)
        object.__setattr__(self, "amount_usd", _money(self.amount_usd, "amount_usd"))
        object.__setattr__(self, "metadata", dict(self.metadata))

    def to_json_dict(self) -> dict[str, Any]:
        """Return a schema-oriented JSON object."""
        return _json_ready(asdict(self))


@dataclass(frozen=True, slots=True)
class CommercialDecision:
    """Decision emitted for plan limits, invoice readiness, or margin checks."""

    decision_id: str
    tenant_id: str
    verdict: CommercialVerdict
    reason: str
    dimension: UsageDimension | None
    current_quantity: Decimal
    limit_quantity: Decimal
    revenue_usd: Decimal
    provider_cost_usd: Decimal
    gross_margin_percent: Decimal
    required_actions: tuple[str, ...]
    decision_hash: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in ("decision_id", "tenant_id", "reason"):
            _require_text(getattr(self, field_name), field_name)
        if not isinstance(self.verdict, CommercialVerdict):
            raise ValueError("commercial_verdict_invalid")
        if self.dimension is not None and not isinstance(self.dimension, UsageDimension):
            raise ValueError("usage_dimension_invalid")
        for field_name in ("current_quantity", "limit_quantity", "revenue_usd", "provider_cost_usd", "gross_margin_percent"):
            object.__setattr__(self, field_name, _money(getattr(self, field_name), field_name))
        object.__setattr__(self, "required_actions", _normalize_text_tuple(self.required_actions, "required_actions", allow_empty=True))
        object.__setattr__(self, "metadata", dict(self.metadata))

    def to_json_dict(self) -> dict[str, Any]:
        """Return a schema-oriented JSON object."""
        return _json_ready(asdict(self))


@dataclass(frozen=True, slots=True)
class TenantCommercialSummary:
    """Computed commercial state for one tenant."""

    tenant_id: str
    plan_id: str
    usage_revenue_usd: Decimal
    base_revenue_usd: Decimal
    total_revenue_usd: Decimal
    provider_cost_usd: Decimal
    gross_margin_percent: Decimal
    invoice_ready: bool
    exceeded_dimensions: tuple[UsageDimension, ...]
    summary_hash: str = ""

    def __post_init__(self) -> None:
        _require_text(self.tenant_id, "tenant_id")
        _require_text(self.plan_id, "plan_id")
        for field_name in ("usage_revenue_usd", "base_revenue_usd", "total_revenue_usd", "provider_cost_usd", "gross_margin_percent"):
            object.__setattr__(self, field_name, _money(getattr(self, field_name), field_name))
        object.__setattr__(self, "exceeded_dimensions", tuple(self.exceeded_dimensions))

    def to_json_dict(self) -> dict[str, Any]:
        """Return a schema-oriented JSON object."""
        return _json_ready(asdict(self))


@dataclass(frozen=True, slots=True)
class CommercialMeteringSnapshot:
    """Operator read model for commercial state."""

    snapshot_id: str
    plans: tuple[PricingPlan, ...]
    accounts: tuple[TenantCommercialAccount, ...]
    usage_records: tuple[UsageRecord, ...]
    provider_costs: tuple[ProviderCostRecord, ...]
    decisions: tuple[CommercialDecision, ...]
    tenant_summaries: tuple[TenantCommercialSummary, ...]
    total_revenue_usd: Decimal
    total_provider_cost_usd: Decimal
    gross_margin_percent: Decimal
    invoice_ready_count: int
    snapshot_hash: str = ""

    def __post_init__(self) -> None:
        _require_text(self.snapshot_id, "snapshot_id")
        for field_name in ("plans", "accounts", "usage_records", "provider_costs", "decisions", "tenant_summaries"):
            object.__setattr__(self, field_name, tuple(getattr(self, field_name)))
        for field_name in ("total_revenue_usd", "total_provider_cost_usd", "gross_margin_percent"):
            object.__setattr__(self, field_name, _money(getattr(self, field_name), field_name))
        if self.invoice_ready_count < 0:
            raise ValueError("invoice_ready_count_non_negative")

    def to_json_dict(self) -> dict[str, Any]:
        """Return a schema-oriented JSON object."""
        return _json_ready(asdict(self))


class CommercialMeteringLedger:
    """In-memory commercial ledger for tenant metering and margin proof."""

    def __init__(self, *, snapshot_id: str = "commercial-metering-snapshot") -> None:
        self._snapshot_id = snapshot_id
        self._plans: dict[str, PricingPlan] = {}
        self._accounts: dict[str, TenantCommercialAccount] = {}
        self._usage: dict[str, UsageRecord] = {}
        self._costs: dict[str, ProviderCostRecord] = {}
        self._decisions: list[CommercialDecision] = []

    def register_plan(self, plan: PricingPlan) -> PricingPlan:
        """Register one stamped pricing plan."""
        stamped = _stamp_plan(plan)
        self._plans[stamped.plan_id] = stamped
        return stamped

    def register_account(self, account: TenantCommercialAccount) -> TenantCommercialAccount:
        """Bind one tenant to an existing pricing plan."""
        if account.plan_id not in self._plans:
            raise ValueError("pricing_plan_missing")
        stamped = _stamp_account(account)
        self._accounts[stamped.tenant_id] = stamped
        return stamped

    def record_usage(self, record: UsageRecord) -> CommercialDecision:
        """Record usage and return the resulting plan-limit decision."""
        self._require_account(record.tenant_id)
        stamped = _stamp_usage(record)
        self._usage[stamped.usage_id] = stamped
        return self.evaluate_limit(record.tenant_id, record.dimension)

    def record_provider_cost(self, record: ProviderCostRecord) -> CommercialDecision:
        """Record provider cost and return the resulting margin decision."""
        self._require_account(record.tenant_id)
        stamped = _stamp_cost(record)
        self._costs[stamped.cost_id] = stamped
        return self.evaluate_invoice_readiness(record.tenant_id)

    def evaluate_limit(self, tenant_id: str, dimension: UsageDimension) -> CommercialDecision:
        """Evaluate one tenant/dimension against plan limits."""
        account = self._require_account(tenant_id)
        plan = self._plans[account.plan_id]
        limit = _limit_for(plan, dimension)
        current_quantity = self._tenant_quantity(tenant_id, dimension)
        over_limit = current_quantity > limit.included_quantity
        decision = CommercialDecision(
            decision_id="pending",
            tenant_id=tenant_id,
            verdict=CommercialVerdict.REVIEW if over_limit else CommercialVerdict.ALLOW,
            reason="plan_limit_exceeded" if over_limit else "plan_limit_satisfied",
            dimension=dimension,
            current_quantity=current_quantity,
            limit_quantity=limit.included_quantity,
            revenue_usd=self._tenant_revenue(tenant_id),
            provider_cost_usd=self._tenant_cost(tenant_id),
            gross_margin_percent=self._tenant_margin(tenant_id),
            required_actions=("upgrade_plan_or_approve_overage",) if over_limit else (),
        )
        return self._record_decision(decision)

    def evaluate_invoice_readiness(self, tenant_id: str) -> CommercialDecision:
        """Evaluate whether a tenant can be invoiced without commercial review."""
        account = self._require_account(tenant_id)
        plan = self._plans[account.plan_id]
        exceeded = self._exceeded_dimensions(tenant_id, plan)
        revenue = self._tenant_revenue(tenant_id)
        cost = self._tenant_cost(tenant_id)
        margin = _margin(revenue, cost)
        if exceeded:
            decision = CommercialDecision(
                decision_id="pending",
                tenant_id=tenant_id,
                verdict=CommercialVerdict.REVIEW,
                reason="plan_limit_review_required",
                dimension=exceeded[0],
                current_quantity=self._tenant_quantity(tenant_id, exceeded[0]),
                limit_quantity=_limit_for(plan, exceeded[0]).included_quantity,
                revenue_usd=revenue,
                provider_cost_usd=cost,
                gross_margin_percent=margin,
                required_actions=("resolve_plan_limit_review",),
            )
            return self._record_decision(decision)
        if revenue > Decimal("0.00") and margin < plan.minimum_gross_margin_percent:
            decision = CommercialDecision(
                decision_id="pending",
                tenant_id=tenant_id,
                verdict=CommercialVerdict.REVIEW,
                reason="gross_margin_below_plan_floor",
                dimension=None,
                current_quantity=Decimal("0.00"),
                limit_quantity=Decimal("0.00"),
                revenue_usd=revenue,
                provider_cost_usd=cost,
                gross_margin_percent=margin,
                required_actions=("review_provider_cost_or_price",),
            )
            return self._record_decision(decision)
        decision = CommercialDecision(
            decision_id="pending",
            tenant_id=tenant_id,
            verdict=CommercialVerdict.ALLOW,
            reason="invoice_ready",
            dimension=None,
            current_quantity=Decimal("0.00"),
            limit_quantity=Decimal("0.00"),
            revenue_usd=revenue,
            provider_cost_usd=cost,
            gross_margin_percent=margin,
            required_actions=(),
        )
        return self._record_decision(decision)

    def snapshot(self) -> CommercialMeteringSnapshot:
        """Return a stamped operator commercial read model."""
        summaries = tuple(self._tenant_summary(account.tenant_id) for account in sorted(self._accounts.values(), key=lambda item: item.tenant_id))
        total_revenue = sum((summary.total_revenue_usd for summary in summaries), Decimal("0.00"))
        total_cost = sum((summary.provider_cost_usd for summary in summaries), Decimal("0.00"))
        snapshot = CommercialMeteringSnapshot(
            snapshot_id=self._snapshot_id,
            plans=tuple(sorted(self._plans.values(), key=lambda item: item.plan_id)),
            accounts=tuple(sorted(self._accounts.values(), key=lambda item: item.tenant_id)),
            usage_records=tuple(sorted(self._usage.values(), key=lambda item: item.usage_id)),
            provider_costs=tuple(sorted(self._costs.values(), key=lambda item: item.cost_id)),
            decisions=tuple(self._decisions),
            tenant_summaries=summaries,
            total_revenue_usd=total_revenue,
            total_provider_cost_usd=total_cost,
            gross_margin_percent=_margin(total_revenue, total_cost),
            invoice_ready_count=sum(1 for summary in summaries if summary.invoice_ready),
        )
        payload = snapshot.to_json_dict()
        payload["snapshot_hash"] = ""
        return replace(snapshot, snapshot_hash=canonical_hash(payload))

    def _tenant_summary(self, tenant_id: str) -> TenantCommercialSummary:
        account = self._require_account(tenant_id)
        plan = self._plans[account.plan_id]
        usage_revenue = self._tenant_usage_revenue(tenant_id, plan)
        total_revenue = plan.base_price_monthly_usd + usage_revenue
        cost = self._tenant_cost(tenant_id)
        exceeded = self._exceeded_dimensions(tenant_id, plan)
        margin = _margin(total_revenue, cost)
        summary = TenantCommercialSummary(
            tenant_id=tenant_id,
            plan_id=plan.plan_id,
            usage_revenue_usd=usage_revenue,
            base_revenue_usd=plan.base_price_monthly_usd,
            total_revenue_usd=total_revenue,
            provider_cost_usd=cost,
            gross_margin_percent=margin,
            invoice_ready=not exceeded and margin >= plan.minimum_gross_margin_percent,
            exceeded_dimensions=exceeded,
        )
        payload = summary.to_json_dict()
        payload["summary_hash"] = ""
        return replace(summary, summary_hash=canonical_hash(payload))

    def _tenant_revenue(self, tenant_id: str) -> Decimal:
        account = self._require_account(tenant_id)
        plan = self._plans[account.plan_id]
        return plan.base_price_monthly_usd + self._tenant_usage_revenue(tenant_id, plan)

    def _tenant_usage_revenue(self, tenant_id: str, plan: PricingPlan) -> Decimal:
        revenue = Decimal("0.00")
        for limit in plan.limits:
            quantity = self._tenant_quantity(tenant_id, limit.dimension)
            overage_quantity = max(Decimal("0.00"), quantity - limit.included_quantity)
            revenue += overage_quantity * limit.overage_unit_price_usd
        return _money(revenue, "usage_revenue_usd")

    def _tenant_quantity(self, tenant_id: str, dimension: UsageDimension) -> Decimal:
        return sum(
            (record.quantity for record in self._usage.values() if record.tenant_id == tenant_id and record.dimension == dimension),
            Decimal("0.00"),
        )

    def _tenant_cost(self, tenant_id: str) -> Decimal:
        return sum((record.amount_usd for record in self._costs.values() if record.tenant_id == tenant_id), Decimal("0.00"))

    def _tenant_margin(self, tenant_id: str) -> Decimal:
        return _margin(self._tenant_revenue(tenant_id), self._tenant_cost(tenant_id))

    def _exceeded_dimensions(self, tenant_id: str, plan: PricingPlan) -> tuple[UsageDimension, ...]:
        return tuple(limit.dimension for limit in plan.limits if self._tenant_quantity(tenant_id, limit.dimension) > limit.included_quantity)

    def _require_account(self, tenant_id: str) -> TenantCommercialAccount:
        _require_text(tenant_id, "tenant_id")
        account = self._accounts.get(tenant_id)
        if account is None:
            raise ValueError("tenant_commercial_account_missing")
        return account

    def _record_decision(self, decision: CommercialDecision) -> CommercialDecision:
        payload = decision.to_json_dict()
        payload["decision_hash"] = ""
        decision_hash = canonical_hash(payload)
        stamped = replace(decision, decision_id=f"commercial-decision-{decision_hash[:16]}", decision_hash=decision_hash)
        self._decisions.append(stamped)
        return stamped


def commercial_metering_snapshot_to_json_dict(snapshot: CommercialMeteringSnapshot) -> dict[str, Any]:
    """Return the public JSON-contract representation of commercial state."""
    return snapshot.to_json_dict()


def _limit_for(plan: PricingPlan, dimension: UsageDimension) -> PlanLimit:
    for limit in plan.limits:
        if limit.dimension == dimension:
            return limit
    raise ValueError("plan_limit_missing_for_dimension")


def _stamp_plan(plan: PricingPlan) -> PricingPlan:
    payload = plan.to_json_dict()
    payload["plan_hash"] = ""
    return replace(plan, plan_hash=canonical_hash(payload))


def _stamp_account(account: TenantCommercialAccount) -> TenantCommercialAccount:
    payload = account.to_json_dict()
    payload["account_hash"] = ""
    return replace(account, account_hash=canonical_hash(payload))


def _stamp_usage(record: UsageRecord) -> UsageRecord:
    payload = record.to_json_dict()
    payload["usage_hash"] = ""
    return replace(record, usage_hash=canonical_hash(payload))


def _stamp_cost(record: ProviderCostRecord) -> ProviderCostRecord:
    payload = record.to_json_dict()
    payload["cost_hash"] = ""
    return replace(record, cost_hash=canonical_hash(payload))


def _margin(revenue: Decimal, cost: Decimal) -> Decimal:
    if revenue == Decimal("0.00"):
        return Decimal("0.00") if cost else Decimal("100.00")
    return _money(((revenue - cost) / revenue) * Decimal("100.00"), "gross_margin_percent")


def _money(value: Decimal | int | float | str, field_name: str) -> Decimal:
    decimal_value = Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if decimal_value < Decimal("0.00"):
        raise ValueError(f"{field_name}_non_negative")
    return decimal_value


def _normalize_text_tuple(values: tuple[str, ...], field_name: str, *, allow_empty: bool = False) -> tuple[str, ...]:
    normalized = tuple(dict.fromkeys(str(value).strip() for value in values if str(value).strip()))
    if not normalized and not allow_empty:
        raise ValueError(f"{field_name}_required")
    return normalized


def _require_text(value: str, field_name: str) -> None:
    if not str(value).strip():
        raise ValueError(f"{field_name}_required")


def _json_ready(value: Any) -> Any:
    if isinstance(value, Decimal):
        return f"{value:.2f}"
    if isinstance(value, StrEnum):
        return value.value
    if isinstance(value, dict):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_json_ready(item) for item in value]
    if isinstance(value, list):
        return [_json_ready(item) for item in value]
    if value is None:
        return None
    return value
