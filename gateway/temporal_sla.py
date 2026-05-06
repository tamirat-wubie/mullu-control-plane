"""Gateway temporal SLA evaluator.

Purpose: govern SLA and business-window decisions before operational
    escalation, dispatch, or deadline claims.
Governance scope: runtime-owned clock use, business calendar windows,
    response and resolution deadlines, breach detection, warning escalation,
    tenant scope, and non-terminal SLA receipts.
Dependencies: dataclasses, datetime, zoneinfo, command-spine canonical hashing,
    and the Temporal Kernel trusted clock.
Invariants:
  - Runtime clock owns current time.
  - SLA deadlines are calculated from explicit policy and case timestamps.
  - Business-time deadlines skip closed windows and holidays.
  - Tenant and evidence scope are checked before SLA state can guide action.
  - Breached or approaching deadlines produce explicit escalation reasons.
  - Temporal SLA receipts are not terminal closure certificates.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from datetime import date, datetime, time, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from gateway.command_spine import canonical_hash
from gateway.temporal_kernel import TrustedClock


TEMPORAL_SLA_RECEIPT_SCHEMA_REF = "urn:mullusi:schema:temporal-sla-receipt:1"
SLA_STATUSES = ("on_track", "warning", "breached", "blocked", "outside_business_window")
SEVERITY_LEVELS = ("low", "medium", "high", "critical")
BASE_SLA_CONTROLS = (
    "runtime_clock",
    "business_calendar",
    "sla_deadline",
    "evidence_reference",
    "temporal_sla_receipt",
    "terminal_closure",
)


@dataclass(frozen=True, slots=True)
class BusinessWindow:
    """One local weekly business window in the policy timezone."""

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
class SlaPolicy:
    """Tenant SLA policy with business-calendar controls."""

    policy_id: str
    tenant_id: str
    severity: str
    timezone_name: str
    target_response_seconds: int
    target_resolution_seconds: int
    warning_seconds: int
    business_windows: list[BusinessWindow]
    holidays: list[str] = field(default_factory=list)
    escalation_contacts: list[str] = field(default_factory=list)
    count_business_time_only: bool = True
    requires_business_window: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in ("policy_id", "tenant_id", "severity", "timezone_name"):
            value = str(getattr(self, field_name)).strip()
            if not value:
                raise ValueError(f"{field_name}_required")
            object.__setattr__(self, field_name, value)
        if self.severity not in SEVERITY_LEVELS:
            raise ValueError("severity_invalid")
        if self.target_response_seconds <= 0:
            raise ValueError("target_response_seconds_positive_required")
        if self.target_resolution_seconds <= 0:
            raise ValueError("target_resolution_seconds_positive_required")
        if self.warning_seconds < 0:
            raise ValueError("warning_seconds_nonnegative_required")
        object.__setattr__(self, "business_windows", list(self.business_windows))
        object.__setattr__(self, "holidays", _normalize_list(self.holidays))
        object.__setattr__(self, "escalation_contacts", _normalize_list(self.escalation_contacts))
        object.__setattr__(self, "metadata", dict(self.metadata))


@dataclass(frozen=True, slots=True)
class SlaCase:
    """One operational case whose deadlines are evaluated."""

    case_id: str
    tenant_id: str
    owner_id: str
    severity: str
    opened_at: str
    evidence_refs: list[str]
    last_response_at: str = ""
    resolved_at: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in ("case_id", "tenant_id", "owner_id", "severity", "opened_at"):
            value = str(getattr(self, field_name)).strip()
            if not value:
                raise ValueError(f"{field_name}_required")
            object.__setattr__(self, field_name, value)
        if self.severity not in SEVERITY_LEVELS:
            raise ValueError("severity_invalid")
        object.__setattr__(self, "evidence_refs", _normalize_list(self.evidence_refs))
        object.__setattr__(self, "last_response_at", str(self.last_response_at).strip())
        object.__setattr__(self, "resolved_at", str(self.resolved_at).strip())
        object.__setattr__(self, "metadata", dict(self.metadata))


@dataclass(frozen=True, slots=True)
class TemporalSlaRequest:
    """One request to evaluate an operational case against an SLA policy."""

    request_id: str
    tenant_id: str
    actor_id: str
    action_type: str
    case: SlaCase
    policy: SlaPolicy

    def __post_init__(self) -> None:
        for field_name in ("request_id", "tenant_id", "actor_id", "action_type"):
            value = str(getattr(self, field_name)).strip()
            if not value:
                raise ValueError(f"{field_name}_required")
            object.__setattr__(self, field_name, value)


@dataclass(frozen=True, slots=True)
class TemporalSlaReceipt:
    """Schema-backed non-terminal receipt for SLA and business-window state."""

    receipt_id: str
    request_id: str
    case_id: str
    policy_id: str
    tenant_id: str
    actor_id: str
    owner_id: str
    action_type: str
    severity: str
    status: str
    temporal_violations: list[str]
    temporal_warnings: list[str]
    breach_reasons: list[str]
    escalation_reasons: list[str]
    required_controls: list[str]
    runtime_now_utc: str
    timezone_name: str
    local_now: str
    business_window_status: str
    active_business_window_start: str
    active_business_window_end: str
    next_business_window_start: str
    opened_at: str
    response_deadline_at: str
    resolution_deadline_at: str
    response_satisfied_at: str
    resolved_at: str
    response_seconds_remaining: int
    resolution_seconds_remaining: int
    target_response_seconds: int
    target_resolution_seconds: int
    warning_seconds: int
    count_business_time_only: bool
    requires_business_window: bool
    holidays: list[str]
    evidence_refs: list[str]
    escalation_contacts: list[str]
    receipt_schema_ref: str
    terminal_closure_required: bool
    receipt_hash: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.status not in SLA_STATUSES:
            raise ValueError("temporal_sla_status_invalid")
        if self.response_seconds_remaining < 0 or self.resolution_seconds_remaining < 0:
            raise ValueError("sla_remaining_seconds_nonnegative_required")
        object.__setattr__(self, "temporal_violations", _normalize_list(self.temporal_violations))
        object.__setattr__(self, "temporal_warnings", _normalize_list(self.temporal_warnings))
        object.__setattr__(self, "breach_reasons", _normalize_list(self.breach_reasons))
        object.__setattr__(self, "escalation_reasons", _normalize_list(self.escalation_reasons))
        object.__setattr__(self, "required_controls", _normalize_list(self.required_controls))
        object.__setattr__(self, "holidays", _normalize_list(self.holidays))
        object.__setattr__(self, "evidence_refs", _normalize_list(self.evidence_refs))
        object.__setattr__(self, "escalation_contacts", _normalize_list(self.escalation_contacts))
        object.__setattr__(self, "metadata", dict(self.metadata))


class TemporalSla:
    """Deterministic SLA and business-calendar evaluator."""

    def __init__(self, clock: TrustedClock | None = None) -> None:
        self._clock = clock or TrustedClock()

    def evaluate(self, request: TemporalSlaRequest) -> TemporalSlaReceipt:
        """Return the SLA state for one case at runtime now."""
        now = _parse_required_instant(self._clock.now_utc())
        temporal_violations: list[str] = []
        temporal_warnings: list[str] = []
        breach_reasons: list[str] = []
        escalation_reasons: list[str] = []
        required_controls = [*BASE_SLA_CONTROLS]

        timezone_info = _timezone(request.policy.timezone_name, temporal_violations)
        parsed = _parse_case_times(request.case, temporal_violations)
        window_errors = _validate_business_windows(request.policy)
        temporal_violations.extend(window_errors)
        _apply_scope_rules(request, temporal_violations)
        _apply_evidence_rules(request, temporal_violations)
        _apply_escalation_contact_rules(request.policy, temporal_violations)

        opened_at = parsed.get("opened_at") or now
        response_deadline_at = _deadline(
            opened_at,
            request.policy.target_response_seconds,
            request.policy,
            timezone_info,
            temporal_violations,
        )
        resolution_deadline_at = _deadline(
            opened_at,
            request.policy.target_resolution_seconds,
            request.policy,
            timezone_info,
            temporal_violations,
        )
        response_satisfied_at = parsed.get("last_response_at") or parsed.get("resolved_at")
        resolved_at = parsed.get("resolved_at")

        window_state = _business_window_state(now, request.policy, timezone_info, temporal_violations)
        _apply_deadline_rules(
            now=now,
            response_deadline_at=response_deadline_at,
            resolution_deadline_at=resolution_deadline_at,
            response_satisfied_at=response_satisfied_at,
            resolved_at=resolved_at,
            warning_seconds=request.policy.warning_seconds,
            breach_reasons=breach_reasons,
            temporal_warnings=temporal_warnings,
            escalation_reasons=escalation_reasons,
        )
        if breach_reasons or temporal_warnings:
            required_controls.append("escalation")
        if request.policy.count_business_time_only:
            required_controls.append("business_time_deadline")
        if request.policy.requires_business_window:
            required_controls.append("business_window_dispatch")

        status = _status(temporal_violations, breach_reasons, temporal_warnings, window_state["inside_business_window"], request.policy)
        receipt = TemporalSlaReceipt(
            receipt_id="pending",
            request_id=request.request_id,
            case_id=request.case.case_id,
            policy_id=request.policy.policy_id,
            tenant_id=request.tenant_id,
            actor_id=request.actor_id,
            owner_id=request.case.owner_id,
            action_type=request.action_type,
            severity=request.case.severity,
            status=status,
            temporal_violations=_unique(temporal_violations),
            temporal_warnings=_unique(temporal_warnings),
            breach_reasons=_unique(breach_reasons),
            escalation_reasons=_unique(escalation_reasons),
            required_controls=_unique(required_controls),
            runtime_now_utc=now.isoformat(),
            timezone_name=request.policy.timezone_name,
            local_now=now.astimezone(timezone_info).isoformat(),
            business_window_status=window_state["status"],
            active_business_window_start=window_state["active_start"],
            active_business_window_end=window_state["active_end"],
            next_business_window_start=window_state["next_start"],
            opened_at=_instant_text(parsed, "opened_at", request.case.opened_at),
            response_deadline_at=response_deadline_at.isoformat(),
            resolution_deadline_at=resolution_deadline_at.isoformat(),
            response_satisfied_at=response_satisfied_at.isoformat() if response_satisfied_at else request.case.last_response_at,
            resolved_at=resolved_at.isoformat() if resolved_at else request.case.resolved_at,
            response_seconds_remaining=_seconds_remaining(now, response_deadline_at),
            resolution_seconds_remaining=_seconds_remaining(now, resolution_deadline_at),
            target_response_seconds=request.policy.target_response_seconds,
            target_resolution_seconds=request.policy.target_resolution_seconds,
            warning_seconds=request.policy.warning_seconds,
            count_business_time_only=request.policy.count_business_time_only,
            requires_business_window=request.policy.requires_business_window,
            holidays=request.policy.holidays,
            evidence_refs=request.case.evidence_refs,
            escalation_contacts=request.policy.escalation_contacts,
            receipt_schema_ref=TEMPORAL_SLA_RECEIPT_SCHEMA_REF,
            terminal_closure_required=True,
            metadata={
                "receipt_is_not_terminal_closure": True,
                "runtime_owns_time_truth": True,
                "deadline_calculation": "business_time" if request.policy.count_business_time_only else "wall_clock",
                "dispatch_allowed": status in {"on_track", "warning", "breached"},
                "escalation_required": bool(breach_reasons or temporal_warnings),
                "business_window_checked": True,
            },
        )
        receipt_hash = canonical_hash(asdict(receipt))
        return replace(
            receipt,
            receipt_id=f"temporal-sla-receipt-{receipt_hash[:16]}",
            receipt_hash=receipt_hash,
        )


def _parse_case_times(case: SlaCase, temporal_violations: list[str]) -> dict[str, datetime]:
    parsed: dict[str, datetime] = {}
    for field_name in ("opened_at", "last_response_at", "resolved_at"):
        raw_value = str(getattr(case, field_name)).strip()
        if not raw_value:
            continue
        try:
            parsed[field_name] = _parse_required_instant(raw_value)
        except ValueError:
            temporal_violations.append(f"{field_name}_invalid")
    return parsed


def _apply_scope_rules(request: TemporalSlaRequest, temporal_violations: list[str]) -> None:
    if request.case.tenant_id != request.tenant_id:
        temporal_violations.append("case_tenant_mismatch")
    if request.policy.tenant_id != request.tenant_id:
        temporal_violations.append("policy_tenant_mismatch")
    if request.case.severity != request.policy.severity:
        temporal_violations.append("sla_policy_severity_mismatch")


def _apply_evidence_rules(request: TemporalSlaRequest, temporal_violations: list[str]) -> None:
    if not request.case.evidence_refs:
        temporal_violations.append("evidence_refs_required")


def _apply_escalation_contact_rules(policy: SlaPolicy, temporal_violations: list[str]) -> None:
    if policy.severity in {"high", "critical"} and not policy.escalation_contacts:
        temporal_violations.append("escalation_contacts_required_for_high_severity_sla")


def _apply_deadline_rules(
    *,
    now: datetime,
    response_deadline_at: datetime,
    resolution_deadline_at: datetime,
    response_satisfied_at: datetime | None,
    resolved_at: datetime | None,
    warning_seconds: int,
    breach_reasons: list[str],
    temporal_warnings: list[str],
    escalation_reasons: list[str],
) -> None:
    if _deadline_breached(now, response_deadline_at, response_satisfied_at):
        breach_reasons.append("response_sla_breached")
        escalation_reasons.append("response_escalation_required")
    elif response_satisfied_at is None and _within_warning(now, response_deadline_at, warning_seconds):
        temporal_warnings.append("response_deadline_approaching")
        escalation_reasons.append("response_warning_escalation_required")

    if _deadline_breached(now, resolution_deadline_at, resolved_at):
        breach_reasons.append("resolution_sla_breached")
        escalation_reasons.append("resolution_escalation_required")
    elif resolved_at is None and _within_warning(now, resolution_deadline_at, warning_seconds):
        temporal_warnings.append("resolution_deadline_approaching")
        escalation_reasons.append("resolution_warning_escalation_required")


def _deadline_breached(now: datetime, deadline_at: datetime, satisfied_at: datetime | None) -> bool:
    if satisfied_at is not None:
        return satisfied_at > deadline_at
    return now > deadline_at


def _within_warning(now: datetime, deadline_at: datetime, warning_seconds: int) -> bool:
    if warning_seconds <= 0 or now > deadline_at:
        return False
    return (deadline_at - now).total_seconds() <= warning_seconds


def _deadline(
    opened_at: datetime,
    target_seconds: int,
    policy: SlaPolicy,
    timezone_info: ZoneInfo,
    temporal_violations: list[str],
) -> datetime:
    if not policy.count_business_time_only:
        return opened_at + timedelta(seconds=target_seconds)
    try:
        return _add_business_seconds(opened_at, target_seconds, policy, timezone_info)
    except ValueError as exc:
        temporal_violations.append(str(exc))
        return opened_at + timedelta(seconds=target_seconds)


def _add_business_seconds(
    start: datetime,
    target_seconds: int,
    policy: SlaPolicy,
    timezone_info: ZoneInfo,
) -> datetime:
    remaining = target_seconds
    cursor = start.astimezone(timezone_info)
    for _ in range(370):
        window = _current_or_next_window(cursor, policy, timezone_info)
        if window is None:
            raise ValueError("business_window_not_found")
        window_start, window_end = window
        if cursor < window_start:
            cursor = window_start
        available = int((window_end - cursor).total_seconds())
        if remaining <= available:
            return (cursor + timedelta(seconds=remaining)).astimezone(timezone.utc)
        remaining -= available
        cursor = window_end + timedelta(seconds=1)
    raise ValueError("business_deadline_search_exhausted")


def _business_window_state(
    now: datetime,
    policy: SlaPolicy,
    timezone_info: ZoneInfo,
    temporal_violations: list[str],
) -> dict[str, Any]:
    local_now = now.astimezone(timezone_info)
    active = _active_window(local_now, policy, timezone_info)
    next_start = _next_window_start(local_now, policy, timezone_info)
    if active:
        active_start, active_end = active
        next_start = _next_window_start(active_end + timedelta(seconds=1), policy, timezone_info)
        return {
            "inside_business_window": True,
            "status": "inside",
            "active_start": active_start.astimezone(timezone.utc).isoformat(),
            "active_end": active_end.astimezone(timezone.utc).isoformat(),
            "next_start": next_start.astimezone(timezone.utc).isoformat() if next_start else "",
        }
    if next_start is None:
        temporal_violations.append("business_window_not_found")
    return {
        "inside_business_window": False,
        "status": "outside",
        "active_start": "",
        "active_end": "",
        "next_start": next_start.astimezone(timezone.utc).isoformat() if next_start else "",
    }


def _current_or_next_window(
    local_cursor: datetime,
    policy: SlaPolicy,
    timezone_info: ZoneInfo,
) -> tuple[datetime, datetime] | None:
    active = _active_window(local_cursor, policy, timezone_info)
    if active:
        return active
    next_start = _next_window_start(local_cursor, policy, timezone_info)
    if next_start is None:
        return None
    next_active = _active_window(next_start, policy, timezone_info)
    if next_active:
        return next_active
    return None


def _active_window(
    local_cursor: datetime,
    policy: SlaPolicy,
    timezone_info: ZoneInfo,
) -> tuple[datetime, datetime] | None:
    for window in policy.business_windows:
        bounds = _window_bounds(local_cursor.date(), window, timezone_info)
        if bounds is None:
            continue
        window_start, window_end = bounds
        if _closed_date(window_start.date(), policy.holidays):
            continue
        if window_start <= local_cursor < window_end:
            return window_start, window_end
    return None


def _next_window_start(
    local_cursor: datetime,
    policy: SlaPolicy,
    timezone_info: ZoneInfo,
) -> datetime | None:
    for day_offset in range(14):
        candidate_date = local_cursor.date() + timedelta(days=day_offset)
        if _closed_date(candidate_date, policy.holidays):
            continue
        starts: list[datetime] = []
        for window in policy.business_windows:
            bounds = _window_bounds(candidate_date, window, timezone_info)
            if bounds is None:
                continue
            window_start, window_end = bounds
            if window_end <= local_cursor:
                continue
            starts.append(max(window_start, local_cursor) if window_start <= local_cursor < window_end else window_start)
        future_starts = [start for start in starts if start >= local_cursor]
        if future_starts:
            return min(future_starts)
    return None


def _window_bounds(
    local_day: date,
    window: BusinessWindow,
    timezone_info: ZoneInfo,
) -> tuple[datetime, datetime] | None:
    if local_day.weekday() != window.weekday:
        return None
    start_time = _parse_local_time(window.start_time)
    end_time = _parse_local_time(window.end_time)
    if start_time is None or end_time is None or end_time <= start_time:
        return None
    start_at = datetime.combine(local_day, start_time).replace(tzinfo=timezone_info)
    end_at = datetime.combine(local_day, end_time).replace(tzinfo=timezone_info)
    return start_at, end_at


def _validate_business_windows(policy: SlaPolicy) -> list[str]:
    violations: list[str] = []
    if not policy.business_windows:
        return ["business_windows_required"]
    for window in policy.business_windows:
        start_time = _parse_local_time(window.start_time)
        end_time = _parse_local_time(window.end_time)
        if start_time is None:
            violations.append("business_window_start_time_invalid")
        if end_time is None:
            violations.append("business_window_end_time_invalid")
        if start_time is not None and end_time is not None and end_time <= start_time:
            violations.append("business_window_range_invalid")
    for holiday in policy.holidays:
        try:
            date.fromisoformat(holiday)
        except ValueError:
            violations.append("holiday_date_invalid")
    return _unique(violations)


def _parse_local_time(value: str) -> time | None:
    try:
        return time.fromisoformat(value)
    except ValueError:
        return None


def _closed_date(local_day: date, holidays: list[str]) -> bool:
    return local_day.isoformat() in set(holidays)


def _timezone(timezone_name: str, temporal_violations: list[str]) -> ZoneInfo:
    try:
        return ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        temporal_violations.append("timezone_invalid")
        return ZoneInfo("UTC")


def _status(
    temporal_violations: list[str],
    breach_reasons: list[str],
    temporal_warnings: list[str],
    inside_business_window: bool,
    policy: SlaPolicy,
) -> str:
    if temporal_violations:
        return "blocked"
    if breach_reasons:
        return "breached"
    if temporal_warnings:
        return "warning"
    if policy.requires_business_window and not inside_business_window:
        return "outside_business_window"
    return "on_track"


def _seconds_remaining(now: datetime, deadline_at: datetime) -> int:
    return max(0, int((deadline_at - now).total_seconds()))


def _parse_required_instant(value: str) -> datetime:
    text = value.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise ValueError("instant_invalid") from exc
    if parsed.tzinfo is None:
        raise ValueError("instant_timezone_required")
    return parsed.astimezone(timezone.utc)


def _instant_text(parsed: dict[str, datetime], field_name: str, fallback: str) -> str:
    instant = parsed.get(field_name)
    if instant:
        return instant.isoformat()
    return fallback


def _normalize_list(values: list[str] | tuple[str, ...]) -> list[str]:
    return [str(value).strip() for value in values if str(value).strip()]


def _unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))
