"""Gateway temporal budget-window evaluator.

Purpose: prove active tenant-local budget periods before governed dispatch.
Governance scope: runtime-owned budget period windows, tenant timezone,
    reset cadence, spend snapshots, reservation projection, high-risk source
    receipt binding, evidence refs, and non-terminal budget-window receipts.
Dependencies: dataclasses, datetime, decimal, zoneinfo, command-spine canonical
    hashing, and the Temporal Kernel trusted clock.
Invariants:
  - Runtime clock owns the active budget period calculation.
  - Daily, weekly, monthly, and custom windows resolve in tenant-local time.
  - Spend plus reserved plus estimated amount must not exceed the active limit.
  - High-risk and critical dispatch require temporal and reapproval evidence.
  - Tenant, budget id, snapshot period, and evidence refs fail closed.
  - Temporal budget-window receipts are not terminal closure certificates.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from gateway.command_spine import canonical_hash
from gateway.temporal_kernel import TrustedClock


TEMPORAL_BUDGET_WINDOW_RECEIPT_SCHEMA_REF = "urn:mullusi:schema:temporal-budget-window-receipt:1"
RISK_LEVELS = ("low", "medium", "high", "critical")
PERIOD_KINDS = ("daily", "weekly", "monthly", "custom")
BUDGET_WINDOW_STATUSES = ("within_budget", "blocked", "deferred", "not_required")
PERIOD_STATES = ("active", "future", "expired", "invalid", "not_required")
BUDGET_STATES = ("sufficient", "exhausted", "not_required")
HIGH_RISK_LEVELS = frozenset({"high", "critical"})
BASE_BUDGET_WINDOW_CONTROLS = (
    "runtime_clock",
    "timezone_resolution",
    "tenant_scope",
    "budget_window_policy",
    "budget_period_reset",
    "spend_snapshot",
    "evidence_reference",
    "temporal_budget_window_receipt",
    "terminal_closure",
)


@dataclass(frozen=True, slots=True)
class BudgetWindowPolicy:
    """Tenant budget window policy for one budget scope."""

    policy_id: str
    tenant_id: str
    budget_id: str
    timezone_name: str
    period_kind: str
    limit_amount_usd: Decimal | int | float | str
    custom_period_start: str = ""
    custom_period_end: str = ""
    week_start_weekday: int = 0
    requires_budget_window: bool = True
    high_risk_requires_budget_window: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in ("policy_id", "tenant_id", "budget_id", "timezone_name", "period_kind"):
            value = str(getattr(self, field_name)).strip()
            if not value:
                raise ValueError(f"{field_name}_required")
            object.__setattr__(self, field_name, value)
        if self.period_kind not in PERIOD_KINDS:
            raise ValueError("budget_period_kind_invalid")
        if self.week_start_weekday < 0 or self.week_start_weekday > 6:
            raise ValueError("week_start_weekday_out_of_range")
        object.__setattr__(self, "limit_amount_usd", _money(self.limit_amount_usd, "limit_amount_usd"))
        object.__setattr__(self, "custom_period_start", str(self.custom_period_start).strip())
        object.__setattr__(self, "custom_period_end", str(self.custom_period_end).strip())
        object.__setattr__(self, "metadata", dict(self.metadata))


@dataclass(frozen=True, slots=True)
class BudgetSpendSnapshot:
    """Observed spend state for one tenant budget period."""

    snapshot_id: str
    tenant_id: str
    budget_id: str
    period_start: str
    period_end: str
    spent_amount_usd: Decimal | int | float | str
    reserved_amount_usd: Decimal | int | float | str = Decimal("0.00")
    evidence_refs: list[str] = field(default_factory=list)
    observed_at: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in ("snapshot_id", "tenant_id", "budget_id", "period_start", "period_end"):
            value = str(getattr(self, field_name)).strip()
            if not value:
                raise ValueError(f"{field_name}_required")
            object.__setattr__(self, field_name, value)
        object.__setattr__(self, "spent_amount_usd", _money(self.spent_amount_usd, "spent_amount_usd"))
        object.__setattr__(self, "reserved_amount_usd", _money(self.reserved_amount_usd, "reserved_amount_usd"))
        object.__setattr__(self, "evidence_refs", _normalize_list(self.evidence_refs))
        object.__setattr__(self, "observed_at", str(self.observed_at).strip())
        object.__setattr__(self, "metadata", dict(self.metadata))


@dataclass(frozen=True, slots=True)
class BudgetWindowRequest:
    """One request to prove budget-window admission before dispatch."""

    request_id: str
    tenant_id: str
    actor_id: str
    command_id: str
    action_type: str
    risk_level: str
    policy: BudgetWindowPolicy
    estimated_amount_usd: Decimal | int | float | str
    evidence_refs: list[str]
    spend_snapshot: BudgetSpendSnapshot | None = None
    source_temporal_receipt_id: str = ""
    source_dispatch_window_receipt_id: str = ""
    source_reapproval_receipt_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in ("request_id", "tenant_id", "actor_id", "command_id", "action_type", "risk_level"):
            value = str(getattr(self, field_name)).strip()
            if not value:
                raise ValueError(f"{field_name}_required")
            object.__setattr__(self, field_name, value)
        if self.risk_level not in RISK_LEVELS:
            raise ValueError("risk_level_invalid")
        object.__setattr__(self, "estimated_amount_usd", _money(self.estimated_amount_usd, "estimated_amount_usd"))
        object.__setattr__(self, "evidence_refs", _normalize_list(self.evidence_refs))
        object.__setattr__(self, "source_temporal_receipt_id", str(self.source_temporal_receipt_id).strip())
        object.__setattr__(
            self,
            "source_dispatch_window_receipt_id",
            str(self.source_dispatch_window_receipt_id).strip(),
        )
        object.__setattr__(self, "source_reapproval_receipt_id", str(self.source_reapproval_receipt_id).strip())
        object.__setattr__(self, "metadata", dict(self.metadata))


@dataclass(frozen=True, slots=True)
class TemporalBudgetWindowReceipt:
    """Schema-backed non-terminal receipt for budget-window checks."""

    receipt_id: str
    request_id: str
    tenant_id: str
    actor_id: str
    command_id: str
    action_type: str
    risk_level: str
    policy_id: str
    budget_id: str
    status: str
    timezone_name: str
    period_kind: str
    runtime_now_utc: str
    local_now: str
    period_start: str
    period_end: str
    defer_until: str
    budget_window_required: bool
    period_state: str
    budget_state: str
    limit_amount_usd: str
    spent_amount_usd: str
    reserved_amount_usd: str
    estimated_amount_usd: str
    projected_amount_usd: str
    available_amount_usd: str
    overage_amount_usd: str
    deferral_reasons: list[str]
    blocked_reasons: list[str]
    required_controls: list[str]
    evidence_refs: list[str]
    snapshot_evidence_refs: list[str]
    source_temporal_receipt_id: str
    source_dispatch_window_receipt_id: str
    source_reapproval_receipt_id: str
    receipt_schema_ref: str
    terminal_closure_required: bool
    receipt_hash: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.status not in BUDGET_WINDOW_STATUSES:
            raise ValueError("temporal_budget_window_status_invalid")
        if self.period_state not in PERIOD_STATES:
            raise ValueError("budget_period_state_invalid")
        if self.budget_state not in BUDGET_STATES:
            raise ValueError("budget_state_invalid")
        object.__setattr__(self, "deferral_reasons", _normalize_list(self.deferral_reasons))
        object.__setattr__(self, "blocked_reasons", _normalize_list(self.blocked_reasons))
        object.__setattr__(self, "required_controls", _normalize_list(self.required_controls))
        object.__setattr__(self, "evidence_refs", _normalize_list(self.evidence_refs))
        object.__setattr__(self, "snapshot_evidence_refs", _normalize_list(self.snapshot_evidence_refs))
        object.__setattr__(self, "metadata", dict(self.metadata))


class TemporalBudgetWindow:
    """Deterministic runtime budget-window evaluator."""

    def __init__(self, clock: TrustedClock | None = None) -> None:
        self._clock = clock or TrustedClock()

    def evaluate(self, request: BudgetWindowRequest) -> TemporalBudgetWindowReceipt:
        """Return whether this action fits the active budget window."""
        now = _parse_required_instant(self._clock.now_utc())
        blocked_reasons: list[str] = []
        deferral_reasons: list[str] = []
        required_controls = [*BASE_BUDGET_WINDOW_CONTROLS]

        timezone_info = _timezone(request.policy.timezone_name, blocked_reasons)
        local_now = now.astimezone(timezone_info)
        budget_window_required = _budget_window_required(request)
        expected_period = _expected_period(request.policy, local_now, timezone_info, blocked_reasons)
        period_start, period_end = expected_period if expected_period else (None, None)
        period_state = _period_state(now, period_start, period_end, budget_window_required)
        snapshot = request.spend_snapshot

        if budget_window_required:
            required_controls.append("active_budget_window")
        if request.risk_level in HIGH_RISK_LEVELS:
            required_controls.append("high_risk_budget_window")
        if request.source_temporal_receipt_id:
            required_controls.append("source_temporal_receipt")
        if request.source_dispatch_window_receipt_id:
            required_controls.append("source_dispatch_window_receipt")
        if request.source_reapproval_receipt_id:
            required_controls.append("source_reapproval_receipt")

        blocked_reasons.extend(_policy_violations(request, budget_window_required))
        blocked_reasons.extend(_snapshot_violations(request, period_start, period_end, budget_window_required))

        if period_state == "future":
            deferral_reasons.append("budget_window_not_started")
        if period_state == "expired":
            blocked_reasons.append("budget_window_expired")
        if period_state == "invalid" and budget_window_required:
            blocked_reasons.append("budget_window_invalid")

        spent = snapshot.spent_amount_usd if snapshot else Decimal("0.00")
        reserved = snapshot.reserved_amount_usd if snapshot else Decimal("0.00")
        projected = spent + reserved + request.estimated_amount_usd
        available = max(Decimal("0.00"), request.policy.limit_amount_usd - spent - reserved)
        overage = max(Decimal("0.00"), projected - request.policy.limit_amount_usd)
        budget_state = _budget_state(budget_window_required, overage)
        if budget_window_required and overage > Decimal("0.00"):
            blocked_reasons.append("budget_limit_exceeded")

        status = _status(
            blocked_reasons=blocked_reasons,
            deferral_reasons=deferral_reasons,
            budget_window_required=budget_window_required,
        )
        receipt = TemporalBudgetWindowReceipt(
            receipt_id="pending",
            request_id=request.request_id,
            tenant_id=request.tenant_id,
            actor_id=request.actor_id,
            command_id=request.command_id,
            action_type=request.action_type,
            risk_level=request.risk_level,
            policy_id=request.policy.policy_id,
            budget_id=request.policy.budget_id,
            status=status,
            timezone_name=request.policy.timezone_name,
            period_kind=request.policy.period_kind,
            runtime_now_utc=now.isoformat(),
            local_now=local_now.isoformat(),
            period_start=_instant_text(period_start),
            period_end=_instant_text(period_end),
            defer_until=_defer_until(status, period_start),
            budget_window_required=budget_window_required,
            period_state=period_state,
            budget_state=budget_state,
            limit_amount_usd=_money_text(request.policy.limit_amount_usd),
            spent_amount_usd=_money_text(spent),
            reserved_amount_usd=_money_text(reserved),
            estimated_amount_usd=_money_text(request.estimated_amount_usd),
            projected_amount_usd=_money_text(projected),
            available_amount_usd=_money_text(available),
            overage_amount_usd=_money_text(overage),
            deferral_reasons=_unique(deferral_reasons),
            blocked_reasons=_unique(blocked_reasons),
            required_controls=_unique(
                required_controls
                if status in {"within_budget", "not_required"}
                else [*required_controls, "budget_dispatch_block"]
            ),
            evidence_refs=request.evidence_refs,
            snapshot_evidence_refs=snapshot.evidence_refs if snapshot else [],
            source_temporal_receipt_id=request.source_temporal_receipt_id,
            source_dispatch_window_receipt_id=request.source_dispatch_window_receipt_id,
            source_reapproval_receipt_id=request.source_reapproval_receipt_id,
            receipt_schema_ref=TEMPORAL_BUDGET_WINDOW_RECEIPT_SCHEMA_REF,
            terminal_closure_required=True,
            metadata={
                "receipt_is_not_terminal_closure": True,
                "runtime_owns_time_truth": True,
                "dispatch_allowed": status in {"within_budget", "not_required"},
                "defer_required": status == "deferred",
                "budget_window_checked": True,
                "reset_window_checked": budget_window_required,
                "spend_projection_checked": budget_window_required,
                "high_risk_budget_checked": request.risk_level in HIGH_RISK_LEVELS,
            },
        )
        receipt_hash = canonical_hash(asdict(receipt))
        return replace(
            receipt,
            receipt_id=f"temporal-budget-window-receipt-{receipt_hash[:16]}",
            receipt_hash=receipt_hash,
        )


def _budget_window_required(request: BudgetWindowRequest) -> bool:
    if request.policy.requires_budget_window:
        return True
    return request.risk_level in HIGH_RISK_LEVELS and request.policy.high_risk_requires_budget_window


def _policy_violations(request: BudgetWindowRequest, budget_window_required: bool) -> list[str]:
    violations: list[str] = []
    if request.policy.tenant_id != request.tenant_id:
        violations.append("policy_tenant_mismatch")
    if budget_window_required and request.policy.limit_amount_usd <= Decimal("0.00"):
        violations.append("budget_limit_positive_required")
    if budget_window_required and request.spend_snapshot is None:
        violations.append("spend_snapshot_required")
    if not request.evidence_refs and budget_window_required:
        violations.append("evidence_refs_required")
    if request.risk_level in HIGH_RISK_LEVELS and not request.source_temporal_receipt_id:
        violations.append("source_temporal_receipt_required_for_high_risk")
    if request.risk_level in HIGH_RISK_LEVELS and not request.source_reapproval_receipt_id:
        violations.append("source_reapproval_receipt_required_for_high_risk")
    return violations


def _snapshot_violations(
    request: BudgetWindowRequest,
    period_start: datetime | None,
    period_end: datetime | None,
    budget_window_required: bool,
) -> list[str]:
    snapshot = request.spend_snapshot
    if snapshot is None:
        return []
    violations: list[str] = []
    if snapshot.tenant_id != request.tenant_id:
        violations.append("snapshot_tenant_mismatch")
    if snapshot.budget_id != request.policy.budget_id:
        violations.append("snapshot_budget_mismatch")
    if budget_window_required and not snapshot.evidence_refs:
        violations.append("snapshot_evidence_refs_required")
    snapshot_start = _parse_optional_instant(snapshot.period_start, violations, "snapshot_period_start_invalid")
    snapshot_end = _parse_optional_instant(snapshot.period_end, violations, "snapshot_period_end_invalid")
    if snapshot_start and snapshot_end and snapshot_end <= snapshot_start:
        violations.append("snapshot_period_invalid")
    if period_start and snapshot_start and snapshot_start != period_start:
        violations.append("snapshot_period_mismatch")
    if period_end and snapshot_end and snapshot_end != period_end:
        violations.append("snapshot_period_mismatch")
    return _unique(violations)


def _expected_period(
    policy: BudgetWindowPolicy,
    local_now: datetime,
    timezone_info: ZoneInfo,
    blocked_reasons: list[str],
) -> tuple[datetime, datetime] | None:
    if policy.period_kind == "daily":
        start = datetime.combine(local_now.date(), datetime.min.time()).replace(tzinfo=timezone_info)
        return start.astimezone(timezone.utc), (start + timedelta(days=1)).astimezone(timezone.utc)
    if policy.period_kind == "weekly":
        days_since_start = (local_now.weekday() - policy.week_start_weekday) % 7
        week_start = local_now.date() - timedelta(days=days_since_start)
        start = datetime.combine(week_start, datetime.min.time()).replace(tzinfo=timezone_info)
        return start.astimezone(timezone.utc), (start + timedelta(days=7)).astimezone(timezone.utc)
    if policy.period_kind == "monthly":
        start_date = date(local_now.year, local_now.month, 1)
        next_month = date(local_now.year + 1, 1, 1) if local_now.month == 12 else date(local_now.year, local_now.month + 1, 1)
        start = datetime.combine(start_date, datetime.min.time()).replace(tzinfo=timezone_info)
        end = datetime.combine(next_month, datetime.min.time()).replace(tzinfo=timezone_info)
        return start.astimezone(timezone.utc), end.astimezone(timezone.utc)
    starts_at = _parse_optional_instant(policy.custom_period_start, blocked_reasons, "custom_period_start_invalid")
    ends_at = _parse_optional_instant(policy.custom_period_end, blocked_reasons, "custom_period_end_invalid")
    if starts_at and ends_at and ends_at <= starts_at:
        blocked_reasons.append("custom_period_invalid")
    if starts_at and ends_at and ends_at > starts_at:
        return starts_at, ends_at
    return None


def _period_state(
    now: datetime,
    period_start: datetime | None,
    period_end: datetime | None,
    budget_window_required: bool,
) -> str:
    if not budget_window_required:
        return "not_required"
    if period_start is None or period_end is None or period_end <= period_start:
        return "invalid"
    if now < period_start:
        return "future"
    if now >= period_end:
        return "expired"
    return "active"


def _budget_state(budget_window_required: bool, overage: Decimal) -> str:
    if not budget_window_required:
        return "not_required"
    return "exhausted" if overage > Decimal("0.00") else "sufficient"


def _status(
    *,
    blocked_reasons: list[str],
    deferral_reasons: list[str],
    budget_window_required: bool,
) -> str:
    if blocked_reasons:
        return "blocked"
    if deferral_reasons:
        return "deferred"
    if not budget_window_required:
        return "not_required"
    return "within_budget"


def _defer_until(status: str, period_start: datetime | None) -> str:
    if status == "deferred" and period_start:
        return period_start.isoformat()
    return ""


def _timezone(timezone_name: str, blocked_reasons: list[str]) -> ZoneInfo:
    try:
        return ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        blocked_reasons.append("timezone_invalid")
        return ZoneInfo("UTC")


def _parse_optional_instant(value: str, violations: list[str], reason: str) -> datetime | None:
    if not value:
        violations.append(reason)
        return None
    try:
        return _parse_required_instant(value)
    except ValueError:
        violations.append(reason)
        return None


def _parse_required_instant(value: str) -> datetime:
    text = value.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise ValueError("instant_invalid") from exc
    if parsed.tzinfo is None:
        raise ValueError("instant_timezone_required")
    return parsed.astimezone(timezone.utc)


def _instant_text(value: datetime | None) -> str:
    return value.isoformat() if value else ""


def _money(value: Decimal | int | float | str, field_name: str) -> Decimal:
    decimal_value = Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if decimal_value < Decimal("0.00"):
        raise ValueError(f"{field_name}_non_negative")
    return decimal_value


def _money_text(value: Decimal) -> str:
    return f"{_money(value, 'amount'):.2f}"


def _normalize_list(values: list[str] | tuple[str, ...]) -> list[str]:
    return [str(value).strip() for value in values if str(value).strip()]


def _unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))
