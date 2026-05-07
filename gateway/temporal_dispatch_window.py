"""Gateway temporal dispatch-window evaluator.

Purpose: recheck whether a governed action may dispatch at runtime now.
Governance scope: runtime-owned local time, tenant timezone, allowed dispatch
    windows, blackout windows, holidays, tenant scope, high-risk source receipt
    binding, evidence refs, and non-terminal temporal dispatch-window receipts.
Dependencies: dataclasses, datetime, zoneinfo, command-spine canonical hashing,
    and the Temporal Kernel trusted clock.
Invariants:
  - Runtime clock owns current time.
  - UTC runtime time is converted into the tenant policy timezone.
  - High-risk and critical actions require explicit dispatch-window control.
  - Active blackout windows defer dispatch before worker execution.
  - Invalid windows, invalid timezones, tenant mismatch, or missing evidence fail closed.
  - Temporal dispatch-window receipts are not terminal closure certificates.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from datetime import date, datetime, time, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from gateway.command_spine import canonical_hash
from gateway.temporal_kernel import TrustedClock


TEMPORAL_DISPATCH_WINDOW_RECEIPT_SCHEMA_REF = "urn:mullusi:schema:temporal-dispatch-window-receipt:1"
RISK_LEVELS = ("low", "medium", "high", "critical")
DISPATCH_WINDOW_STATUSES = ("within_window", "deferred", "blocked", "not_required")
WINDOW_STATES = ("inside", "outside", "not_required")
HOLIDAY_STATES = ("open", "closed")
BASE_DISPATCH_WINDOW_CONTROLS = (
    "runtime_clock",
    "timezone_resolution",
    "tenant_scope",
    "dispatch_window_policy",
    "blackout_window",
    "evidence_reference",
    "temporal_dispatch_window_receipt",
    "terminal_closure",
)
HIGH_RISK_LEVELS = frozenset({"high", "critical"})


@dataclass(frozen=True, slots=True)
class DispatchAllowedWindow:
    """One local weekly dispatch window in the policy timezone."""

    weekday: int
    start_time: str
    end_time: str
    label: str = ""

    def __post_init__(self) -> None:
        if self.weekday < 0 or self.weekday > 6:
            raise ValueError("weekday_out_of_range")
        object.__setattr__(self, "start_time", str(self.start_time).strip())
        object.__setattr__(self, "end_time", str(self.end_time).strip())
        object.__setattr__(self, "label", str(self.label).strip())


@dataclass(frozen=True, slots=True)
class DispatchBlackoutWindow:
    """One absolute UTC blackout interval that can defer dispatch."""

    blackout_id: str
    starts_at: str
    ends_at: str
    reason: str
    action_types: list[str] = field(default_factory=list)
    risk_levels: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in ("blackout_id", "starts_at", "ends_at", "reason"):
            value = str(getattr(self, field_name)).strip()
            if not value:
                raise ValueError(f"{field_name}_required")
            object.__setattr__(self, field_name, value)
        object.__setattr__(self, "action_types", _normalize_list(self.action_types))
        object.__setattr__(self, "risk_levels", _normalize_list(self.risk_levels))
        object.__setattr__(self, "metadata", dict(self.metadata))


@dataclass(frozen=True, slots=True)
class DispatchWindowPolicy:
    """Tenant dispatch-window policy for action admission."""

    policy_id: str
    tenant_id: str
    timezone_name: str
    allowed_windows: list[DispatchAllowedWindow]
    blackout_windows: list[DispatchBlackoutWindow] = field(default_factory=list)
    holidays: list[str] = field(default_factory=list)
    requires_allowed_window: bool = True
    high_risk_requires_allowed_window: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in ("policy_id", "tenant_id", "timezone_name"):
            value = str(getattr(self, field_name)).strip()
            if not value:
                raise ValueError(f"{field_name}_required")
            object.__setattr__(self, field_name, value)
        object.__setattr__(self, "allowed_windows", list(self.allowed_windows))
        object.__setattr__(self, "blackout_windows", list(self.blackout_windows))
        object.__setattr__(self, "holidays", _normalize_list(self.holidays))
        object.__setattr__(self, "metadata", dict(self.metadata))


@dataclass(frozen=True, slots=True)
class DispatchWindowRequest:
    """One request to recheck runtime dispatch-window admission."""

    request_id: str
    tenant_id: str
    actor_id: str
    command_id: str
    action_type: str
    risk_level: str
    policy: DispatchWindowPolicy
    evidence_refs: list[str]
    source_schedule_receipt_id: str = ""
    source_reapproval_receipt_id: str = ""
    source_temporal_receipt_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in ("request_id", "tenant_id", "actor_id", "command_id", "action_type", "risk_level"):
            value = str(getattr(self, field_name)).strip()
            if not value:
                raise ValueError(f"{field_name}_required")
            object.__setattr__(self, field_name, value)
        if self.risk_level not in RISK_LEVELS:
            raise ValueError("risk_level_invalid")
        object.__setattr__(self, "evidence_refs", _normalize_list(self.evidence_refs))
        object.__setattr__(self, "source_schedule_receipt_id", str(self.source_schedule_receipt_id).strip())
        object.__setattr__(self, "source_reapproval_receipt_id", str(self.source_reapproval_receipt_id).strip())
        object.__setattr__(self, "source_temporal_receipt_id", str(self.source_temporal_receipt_id).strip())
        object.__setattr__(self, "metadata", dict(self.metadata))


@dataclass(frozen=True, slots=True)
class TemporalDispatchWindowReceipt:
    """Schema-backed non-terminal receipt for dispatch-window checks."""

    receipt_id: str
    request_id: str
    tenant_id: str
    actor_id: str
    command_id: str
    action_type: str
    risk_level: str
    policy_id: str
    status: str
    timezone_name: str
    runtime_now_utc: str
    local_now: str
    local_date: str
    allowed_window_required: bool
    allowed_window_status: str
    holiday_status: str
    active_allowed_window_start: str
    active_allowed_window_end: str
    next_allowed_window_start: str
    next_allowed_window_end: str
    defer_until: str
    active_blackout_ids: list[str]
    deferral_reasons: list[str]
    blocked_reasons: list[str]
    required_controls: list[str]
    evidence_refs: list[str]
    holidays: list[str]
    source_schedule_receipt_id: str
    source_reapproval_receipt_id: str
    source_temporal_receipt_id: str
    receipt_schema_ref: str
    terminal_closure_required: bool
    receipt_hash: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.status not in DISPATCH_WINDOW_STATUSES:
            raise ValueError("temporal_dispatch_window_status_invalid")
        if self.allowed_window_status not in WINDOW_STATES:
            raise ValueError("dispatch_window_state_invalid")
        if self.holiday_status not in HOLIDAY_STATES:
            raise ValueError("holiday_state_invalid")
        object.__setattr__(self, "active_blackout_ids", _normalize_list(self.active_blackout_ids))
        object.__setattr__(self, "deferral_reasons", _normalize_list(self.deferral_reasons))
        object.__setattr__(self, "blocked_reasons", _normalize_list(self.blocked_reasons))
        object.__setattr__(self, "required_controls", _normalize_list(self.required_controls))
        object.__setattr__(self, "evidence_refs", _normalize_list(self.evidence_refs))
        object.__setattr__(self, "holidays", _normalize_list(self.holidays))
        object.__setattr__(self, "metadata", dict(self.metadata))


class TemporalDispatchWindow:
    """Deterministic runtime dispatch-window evaluator."""

    def __init__(self, clock: TrustedClock | None = None) -> None:
        self._clock = clock or TrustedClock()

    def evaluate(self, request: DispatchWindowRequest) -> TemporalDispatchWindowReceipt:
        """Return whether this action may dispatch under the time-window policy."""
        now = _parse_required_instant(self._clock.now_utc())
        blocked_reasons: list[str] = []
        deferral_reasons: list[str] = []
        required_controls = [*BASE_DISPATCH_WINDOW_CONTROLS]

        timezone_info = _timezone(request.policy.timezone_name, blocked_reasons)
        local_now = now.astimezone(timezone_info)
        allowed_window_required = _allowed_window_required(request)
        blocked_reasons.extend(_policy_violations(request, allowed_window_required))
        blocked_reasons.extend(_allowed_window_violations(request.policy))
        active_blackouts, blackout_end_at = _active_blackouts(request, now, blocked_reasons)
        active_window = _active_allowed_window(local_now, request.policy, timezone_info)
        next_window = _next_allowed_window(local_now, request.policy, timezone_info)
        holiday_status = "closed" if _closed_date(local_now.date(), request.policy.holidays) else "open"

        if allowed_window_required:
            required_controls.append("allowed_dispatch_window")
        if request.risk_level in HIGH_RISK_LEVELS:
            required_controls.append("high_risk_dispatch_window")
        if request.source_schedule_receipt_id:
            required_controls.append("source_schedule_receipt")
        if request.source_reapproval_receipt_id:
            required_controls.append("source_reapproval_receipt")
        if request.source_temporal_receipt_id:
            required_controls.append("source_temporal_receipt")

        if active_blackouts:
            deferral_reasons.append("blackout_window_active")
        if allowed_window_required and active_window is None:
            deferral_reasons.append("outside_allowed_dispatch_window")
        if holiday_status == "closed" and allowed_window_required:
            deferral_reasons.append("holiday_closed")
        if allowed_window_required and active_window is None and next_window is None:
            blocked_reasons.append("next_allowed_window_not_found")

        status = _status(
            blocked_reasons=blocked_reasons,
            deferral_reasons=deferral_reasons,
            allowed_window_required=allowed_window_required,
        )
        defer_until = _defer_until(
            status=status,
            active_window=active_window,
            next_window=next_window,
            blackout_end_at=blackout_end_at,
            timezone_info=timezone_info,
        )
        receipt = TemporalDispatchWindowReceipt(
            receipt_id="pending",
            request_id=request.request_id,
            tenant_id=request.tenant_id,
            actor_id=request.actor_id,
            command_id=request.command_id,
            action_type=request.action_type,
            risk_level=request.risk_level,
            policy_id=request.policy.policy_id,
            status=status,
            timezone_name=request.policy.timezone_name,
            runtime_now_utc=now.isoformat(),
            local_now=local_now.isoformat(),
            local_date=local_now.date().isoformat(),
            allowed_window_required=allowed_window_required,
            allowed_window_status=_window_status(active_window, allowed_window_required),
            holiday_status=holiday_status,
            active_allowed_window_start=_window_start(active_window),
            active_allowed_window_end=_window_end(active_window),
            next_allowed_window_start=_window_start(next_window),
            next_allowed_window_end=_window_end(next_window),
            defer_until=defer_until,
            active_blackout_ids=[blackout.blackout_id for blackout in active_blackouts],
            deferral_reasons=_unique(deferral_reasons),
            blocked_reasons=_unique(blocked_reasons),
            required_controls=_unique(
                required_controls
                if status in {"within_window", "not_required"}
                else [*required_controls, "dispatch_block"]
            ),
            evidence_refs=request.evidence_refs,
            holidays=request.policy.holidays,
            source_schedule_receipt_id=request.source_schedule_receipt_id,
            source_reapproval_receipt_id=request.source_reapproval_receipt_id,
            source_temporal_receipt_id=request.source_temporal_receipt_id,
            receipt_schema_ref=TEMPORAL_DISPATCH_WINDOW_RECEIPT_SCHEMA_REF,
            terminal_closure_required=True,
            metadata={
                "receipt_is_not_terminal_closure": True,
                "runtime_owns_time_truth": True,
                "dispatch_allowed": status in {"within_window", "not_required"},
                "defer_required": status == "deferred",
                "window_policy_checked": True,
                "blackout_window_checked": True,
                "high_risk_window_checked": request.risk_level in HIGH_RISK_LEVELS,
            },
        )
        receipt_hash = canonical_hash(asdict(receipt))
        return replace(
            receipt,
            receipt_id=f"temporal-dispatch-window-receipt-{receipt_hash[:16]}",
            receipt_hash=receipt_hash,
        )


def _allowed_window_required(request: DispatchWindowRequest) -> bool:
    if request.policy.requires_allowed_window:
        return True
    return request.risk_level in HIGH_RISK_LEVELS and request.policy.high_risk_requires_allowed_window


def _policy_violations(request: DispatchWindowRequest, allowed_window_required: bool) -> list[str]:
    violations: list[str] = []
    if request.policy.tenant_id != request.tenant_id:
        violations.append("policy_tenant_mismatch")
    if not request.evidence_refs:
        violations.append("evidence_refs_required")
    if allowed_window_required and not request.policy.allowed_windows:
        violations.append("allowed_windows_required")
    if request.risk_level in HIGH_RISK_LEVELS and not request.source_schedule_receipt_id:
        violations.append("source_schedule_receipt_required_for_high_risk")
    if request.risk_level in HIGH_RISK_LEVELS and not request.source_reapproval_receipt_id:
        violations.append("source_reapproval_receipt_required_for_high_risk")
    return violations


def _allowed_window_violations(policy: DispatchWindowPolicy) -> list[str]:
    violations: list[str] = []
    for window in policy.allowed_windows:
        start_time = _parse_local_time(window.start_time)
        end_time = _parse_local_time(window.end_time)
        if start_time is None:
            violations.append("allowed_window_start_time_invalid")
        if end_time is None:
            violations.append("allowed_window_end_time_invalid")
        if start_time is not None and end_time is not None and end_time <= start_time:
            violations.append("allowed_window_range_invalid")
    for holiday in policy.holidays:
        try:
            date.fromisoformat(holiday)
        except ValueError:
            violations.append("holiday_date_invalid")
    return _unique(violations)


def _active_blackouts(
    request: DispatchWindowRequest,
    now: datetime,
    blocked_reasons: list[str],
) -> tuple[list[DispatchBlackoutWindow], datetime | None]:
    active: list[DispatchBlackoutWindow] = []
    active_ends: list[datetime] = []
    for blackout in request.policy.blackout_windows:
        starts_at = _parse_optional_instant(
            blackout.starts_at,
            blocked_reasons,
            f"{blackout.blackout_id}:blackout_starts_at_invalid",
        )
        ends_at = _parse_optional_instant(
            blackout.ends_at,
            blocked_reasons,
            f"{blackout.blackout_id}:blackout_ends_at_invalid",
        )
        if starts_at and ends_at and ends_at <= starts_at:
            blocked_reasons.append(f"{blackout.blackout_id}:blackout_window_range_invalid")
        if not _blackout_applies(blackout, request):
            continue
        if starts_at and ends_at and starts_at <= now < ends_at:
            active.append(blackout)
            active_ends.append(ends_at)
    return active, max(active_ends) if active_ends else None


def _blackout_applies(blackout: DispatchBlackoutWindow, request: DispatchWindowRequest) -> bool:
    action_type_applies = (
        not blackout.action_types
        or request.action_type in blackout.action_types
        or "*" in blackout.action_types
    )
    risk_level_applies = (
        not blackout.risk_levels
        or request.risk_level in blackout.risk_levels
        or "*" in blackout.risk_levels
    )
    return action_type_applies and risk_level_applies


def _active_allowed_window(
    local_now: datetime,
    policy: DispatchWindowPolicy,
    timezone_info: ZoneInfo,
) -> tuple[datetime, datetime] | None:
    if _closed_date(local_now.date(), policy.holidays):
        return None
    for window in policy.allowed_windows:
        bounds = _window_bounds(local_now.date(), window, timezone_info)
        if bounds is None:
            continue
        starts_at, ends_at = bounds
        if starts_at <= local_now < ends_at:
            return starts_at, ends_at
    return None


def _next_allowed_window(
    local_now: datetime,
    policy: DispatchWindowPolicy,
    timezone_info: ZoneInfo,
) -> tuple[datetime, datetime] | None:
    for day_offset in range(14):
        candidate_date = local_now.date() + timedelta(days=day_offset)
        if _closed_date(candidate_date, policy.holidays):
            continue
        candidates: list[tuple[datetime, datetime]] = []
        for window in policy.allowed_windows:
            bounds = _window_bounds(candidate_date, window, timezone_info)
            if bounds is None:
                continue
            starts_at, ends_at = bounds
            if ends_at <= local_now:
                continue
            candidates.append((starts_at, ends_at))
        future_candidates = [
            candidate
            for candidate in candidates
            if candidate[0] >= local_now or candidate[0] <= local_now < candidate[1]
        ]
        if future_candidates:
            return min(future_candidates, key=lambda candidate: candidate[0])
    return None


def _window_bounds(
    local_day: date,
    window: DispatchAllowedWindow,
    timezone_info: ZoneInfo,
) -> tuple[datetime, datetime] | None:
    if local_day.weekday() != window.weekday:
        return None
    start_time = _parse_local_time(window.start_time)
    end_time = _parse_local_time(window.end_time)
    if start_time is None or end_time is None or end_time <= start_time:
        return None
    starts_at = datetime.combine(local_day, start_time).replace(tzinfo=timezone_info)
    ends_at = datetime.combine(local_day, end_time).replace(tzinfo=timezone_info)
    return starts_at, ends_at


def _status(
    *,
    blocked_reasons: list[str],
    deferral_reasons: list[str],
    allowed_window_required: bool,
) -> str:
    if blocked_reasons:
        return "blocked"
    if deferral_reasons:
        return "deferred"
    if not allowed_window_required:
        return "not_required"
    return "within_window"


def _defer_until(
    *,
    status: str,
    active_window: tuple[datetime, datetime] | None,
    next_window: tuple[datetime, datetime] | None,
    blackout_end_at: datetime | None,
    timezone_info: ZoneInfo,
) -> str:
    if status != "deferred":
        return ""
    if blackout_end_at and active_window:
        local_blackout_end = blackout_end_at.astimezone(timezone_info)
        if active_window[0] <= local_blackout_end < active_window[1]:
            return blackout_end_at.isoformat()
    if next_window:
        return next_window[0].astimezone(timezone.utc).isoformat()
    if blackout_end_at:
        return blackout_end_at.isoformat()
    return ""


def _window_status(active_window: tuple[datetime, datetime] | None, allowed_window_required: bool) -> str:
    if not allowed_window_required:
        return "not_required"
    return "inside" if active_window else "outside"


def _window_start(window: tuple[datetime, datetime] | None) -> str:
    return window[0].astimezone(timezone.utc).isoformat() if window else ""


def _window_end(window: tuple[datetime, datetime] | None) -> str:
    return window[1].astimezone(timezone.utc).isoformat() if window else ""


def _parse_local_time(value: str) -> time | None:
    try:
        return time.fromisoformat(value)
    except ValueError:
        return None


def _closed_date(local_day: date, holidays: list[str]) -> bool:
    return local_day.isoformat() in set(holidays)


def _timezone(timezone_name: str, blocked_reasons: list[str]) -> ZoneInfo:
    try:
        return ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        blocked_reasons.append("timezone_invalid")
        return ZoneInfo("UTC")


def _parse_optional_instant(value: str, blocked_reasons: list[str], reason: str) -> datetime | None:
    if not value:
        return None
    try:
        return _parse_required_instant(value)
    except ValueError:
        blocked_reasons.append(reason)
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


def _normalize_list(values: list[str] | tuple[str, ...]) -> list[str]:
    return [str(value).strip() for value in values if str(value).strip()]


def _unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))
