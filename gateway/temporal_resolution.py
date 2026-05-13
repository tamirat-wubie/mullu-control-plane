"""Gateway temporal phrase resolution evaluator.

Purpose: resolve bounded temporal phrases into runtime-owned timestamps before
    scheduling, SLA, or dispatch policy consumes them.
Governance scope: trusted runtime clock, tenant timezone, original text
    preservation, ambiguity detection, business-calendar resolution, high-risk
    clarification, evidence refs, and non-terminal temporal resolution receipts.
Dependencies: dataclasses, datetime, re, zoneinfo, command-spine canonical
    hashing, and the Temporal Kernel trusted clock.
Invariants:
  - Runtime clock owns the meaning of "now".
  - Original temporal text is preserved on every receipt.
  - Tenant timezone is explicit and used for local phrases.
  - Ambiguous high-risk phrases require clarification before execution.
  - Unsupported phrases fail closed instead of guessing.
  - Temporal resolution receipts are not terminal closure certificates.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from datetime import date, datetime, time, timedelta, timezone
import re
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from gateway.command_spine import canonical_hash
from gateway.temporal_kernel import TrustedClock


TEMPORAL_RESOLUTION_RECEIPT_SCHEMA_REF = "urn:mullusi:schema:temporal-resolution-receipt:1"
RISK_LEVELS = ("low", "medium", "high", "critical")
HIGH_RISK_LEVELS = frozenset({"high", "critical"})
RESOLUTION_STATUSES = ("resolved", "needs_clarification", "blocked", "unsupported", "not_required")
RESOLUTION_STATES = (
    "absolute_instant",
    "local_datetime",
    "relative_duration",
    "tomorrow_explicit",
    "tomorrow_defaulted",
    "business_day",
    "end_of_day",
    "unsupported",
    "invalid",
    "not_required",
)
AMBIGUITY_LEVELS = ("none", "defaulted", "high", "unsupported")
BASE_RESOLUTION_CONTROLS = (
    "runtime_now_utc_injected",
    "tenant_timezone_resolved",
    "original_text_preserved",
    "bounded_phrase_parser",
    "evidence_refs_present",
    "temporal_resolution_receipt",
    "terminal_closure_required",
)


@dataclass(frozen=True, slots=True)
class TemporalResolutionPolicy:
    """Tenant policy for bounded phrase-to-time resolution."""

    policy_id: str
    tenant_id: str
    timezone_name: str
    default_morning_time: str = "09:00"
    default_due_time: str = "09:00"
    business_day_start_time: str = "09:00"
    business_day_end_time: str = "17:00"
    business_weekdays: list[int] = field(default_factory=lambda: [0, 1, 2, 3, 4])
    holidays: list[str] = field(default_factory=list)
    high_risk_requires_explicit_time: bool = True
    max_future_days: int = 366
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in ("policy_id", "tenant_id", "timezone_name"):
            value = str(getattr(self, field_name)).strip()
            if not value:
                raise ValueError(f"{field_name}_required")
            object.__setattr__(self, field_name, value)
        for field_name in (
            "default_morning_time",
            "default_due_time",
            "business_day_start_time",
            "business_day_end_time",
        ):
            object.__setattr__(self, field_name, str(getattr(self, field_name)).strip())
        object.__setattr__(self, "business_weekdays", list(self.business_weekdays))
        object.__setattr__(self, "holidays", _normalize_list(self.holidays))
        object.__setattr__(self, "metadata", dict(self.metadata))
        if self.max_future_days < 0:
            raise ValueError("max_future_days_nonnegative_required")


@dataclass(frozen=True, slots=True)
class TemporalResolutionRequest:
    """One request to resolve temporal language into a governed timestamp."""

    request_id: str
    tenant_id: str
    actor_id: str
    command_id: str
    action_type: str
    risk_level: str
    original_text: str
    policy: TemporalResolutionPolicy
    evidence_refs: list[str]
    resolution_required: bool = True
    source_clock_sample_id: str = ""
    source_temporal_receipt_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in (
            "request_id",
            "tenant_id",
            "actor_id",
            "command_id",
            "action_type",
            "risk_level",
            "original_text",
        ):
            value = str(getattr(self, field_name)).strip()
            if not value:
                raise ValueError(f"{field_name}_required")
            object.__setattr__(self, field_name, value)
        if self.risk_level not in RISK_LEVELS:
            raise ValueError("risk_level_invalid")
        object.__setattr__(self, "evidence_refs", _normalize_list(self.evidence_refs))
        object.__setattr__(self, "source_clock_sample_id", str(self.source_clock_sample_id).strip())
        object.__setattr__(self, "source_temporal_receipt_id", str(self.source_temporal_receipt_id).strip())
        object.__setattr__(self, "metadata", dict(self.metadata))


@dataclass(frozen=True, slots=True)
class TemporalResolutionReceipt:
    """Schema-backed non-terminal receipt for temporal phrase resolution."""

    receipt_id: str
    request_id: str
    tenant_id: str
    actor_id: str
    command_id: str
    action_type: str
    risk_level: str
    policy_id: str
    status: str
    resolution_state: str
    original_text: str
    normalized_text: str
    runtime_now_utc: str
    timezone_name: str
    local_now: str
    resolved_execute_at: str
    local_resolved_time: str
    safe_default_execute_at: str
    resolution_basis: str
    ambiguity_level: str
    clarification_required: bool
    business_calendar_used: bool
    business_day_count: int
    holidays: list[str]
    blocked_reasons: list[str]
    warning_reasons: list[str]
    required_controls: list[str]
    evidence_refs: list[str]
    source_clock_sample_id: str
    source_temporal_receipt_id: str
    receipt_schema_ref: str
    terminal_closure_required: bool
    receipt_hash: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.status not in RESOLUTION_STATUSES:
            raise ValueError("temporal_resolution_status_invalid")
        if self.resolution_state not in RESOLUTION_STATES:
            raise ValueError("temporal_resolution_state_invalid")
        if self.ambiguity_level not in AMBIGUITY_LEVELS:
            raise ValueError("temporal_resolution_ambiguity_invalid")
        if self.business_day_count < 0:
            raise ValueError("business_day_count_nonnegative_required")
        object.__setattr__(self, "holidays", _normalize_list(self.holidays))
        object.__setattr__(self, "blocked_reasons", _normalize_list(self.blocked_reasons))
        object.__setattr__(self, "warning_reasons", _normalize_list(self.warning_reasons))
        object.__setattr__(self, "required_controls", _normalize_list(self.required_controls))
        object.__setattr__(self, "evidence_refs", _normalize_list(self.evidence_refs))
        object.__setattr__(self, "metadata", dict(self.metadata))


@dataclass(frozen=True, slots=True)
class _ResolvedPhrase:
    state: str
    basis: str
    resolved_at: datetime | None
    safe_default_at: datetime | None
    ambiguity_level: str
    business_calendar_used: bool
    business_day_count: int = 0
    warning_reasons: tuple[str, ...] = ()


class TemporalResolution:
    """Deterministic temporal phrase resolver."""

    def __init__(self, clock: TrustedClock | None = None) -> None:
        self._clock = clock or TrustedClock()

    def evaluate(self, request: TemporalResolutionRequest) -> TemporalResolutionReceipt:
        """Resolve a bounded phrase using the runtime clock."""
        return evaluate_temporal_resolution(
            request,
            runtime_now_utc=_parse_required_instant(self._clock.now_utc(), "runtime_now_utc"),
        )


def evaluate_temporal_resolution(
    request: TemporalResolutionRequest,
    *,
    runtime_now_utc: datetime,
) -> TemporalResolutionReceipt:
    """Resolve a bounded temporal phrase into a schema-backed receipt.

    Input contract: request carries tenant/action scope, original text, policy,
    and evidence refs.
    Output contract: returns a non-terminal receipt with resolved timestamp,
    ambiguity state, clarification requirement, and stable hash.
    Error contract: malformed dataclass fields and naive runtime clocks raise
    ValueError; semantic policy problems are represented in blocked_reasons.
    """

    now = _to_utc(runtime_now_utc, "runtime_now_utc")
    blocked_reasons: list[str] = []
    warning_reasons: list[str] = []
    required_controls = [*BASE_RESOLUTION_CONTROLS]
    timezone_info = _timezone(request.policy.timezone_name, blocked_reasons)
    local_now = now.astimezone(timezone_info)
    normalized_text = _normalize_text(request.original_text)

    if request.policy.tenant_id != request.tenant_id:
        blocked_reasons.append("policy_tenant_mismatch")
    if request.resolution_required and not request.evidence_refs:
        blocked_reasons.append("evidence_refs_required")
    if request.risk_level in HIGH_RISK_LEVELS:
        required_controls.append("high_risk_ambiguity_gate")
        if not request.source_clock_sample_id:
            blocked_reasons.append("source_clock_sample_required_for_high_risk")

    blocked_reasons.extend(_policy_violations(request.policy))

    if not request.resolution_required:
        resolved = _ResolvedPhrase(
            state="not_required",
            basis="resolution_not_required",
            resolved_at=None,
            safe_default_at=None,
            ambiguity_level="none",
            business_calendar_used=False,
        )
    elif blocked_reasons:
        resolved = _ResolvedPhrase(
            state="invalid",
            basis="policy_violation",
            resolved_at=None,
            safe_default_at=None,
            ambiguity_level="none",
            business_calendar_used=False,
        )
    else:
        resolved = _resolve_phrase(normalized_text, now, local_now, timezone_info, request.policy)
        warning_reasons.extend(resolved.warning_reasons)
        blocked_reasons.extend(_resolved_time_violations(now, resolved, request.policy))

    clarification_required = _clarification_required(request, resolved)
    if clarification_required:
        required_controls.append("operator_clarification")
        warning_reasons.append("clarification_required")

    status = _status(request, resolved, blocked_reasons, clarification_required)
    executable_resolved_at = resolved.resolved_at if status == "resolved" else None
    safe_default_at = resolved.safe_default_at or resolved.resolved_at
    local_resolved_at = executable_resolved_at.astimezone(timezone_info) if executable_resolved_at else None

    receipt = TemporalResolutionReceipt(
        receipt_id="pending",
        request_id=request.request_id,
        tenant_id=request.tenant_id,
        actor_id=request.actor_id,
        command_id=request.command_id,
        action_type=request.action_type,
        risk_level=request.risk_level,
        policy_id=request.policy.policy_id,
        status=status,
        resolution_state=resolved.state,
        original_text=request.original_text,
        normalized_text=normalized_text,
        runtime_now_utc=now.isoformat(),
        timezone_name=request.policy.timezone_name,
        local_now=local_now.isoformat(),
        resolved_execute_at=executable_resolved_at.isoformat() if executable_resolved_at else "",
        local_resolved_time=local_resolved_at.isoformat() if local_resolved_at else "",
        safe_default_execute_at=safe_default_at.isoformat() if safe_default_at else "",
        resolution_basis=resolved.basis,
        ambiguity_level=resolved.ambiguity_level,
        clarification_required=clarification_required,
        business_calendar_used=resolved.business_calendar_used,
        business_day_count=resolved.business_day_count,
        holidays=request.policy.holidays,
        blocked_reasons=_unique(blocked_reasons),
        warning_reasons=_unique(warning_reasons),
        required_controls=_unique(
            []
            if status == "not_required"
            else required_controls if status == "resolved" else [*required_controls, "resolution_block"]
        ),
        evidence_refs=request.evidence_refs,
        source_clock_sample_id=request.source_clock_sample_id,
        source_temporal_receipt_id=request.source_temporal_receipt_id,
        receipt_schema_ref=TEMPORAL_RESOLUTION_RECEIPT_SCHEMA_REF,
        terminal_closure_required=True,
        metadata={
            **request.metadata,
            "runtime_owns_time_truth": True,
            "receipt_is_not_terminal_closure": True,
            "original_text_preserved": True,
            "timezone_preserved": True,
            "temporal_phrase_resolved": status == "resolved",
            "safe_default_used": resolved.ambiguity_level == "defaulted",
            "high_risk_clarification_checked": request.risk_level in HIGH_RISK_LEVELS,
            "terminal_closure_required": True,
        },
    )
    receipt_hash = canonical_hash(asdict(receipt))
    return replace(
        receipt,
        receipt_id=f"temporal-resolution-receipt-{receipt_hash[:16]}",
        receipt_hash=receipt_hash,
    )


def receipt_to_dict(receipt: TemporalResolutionReceipt) -> dict[str, Any]:
    """Return a JSON-serializable receipt dictionary."""
    return asdict(receipt)


def _resolve_phrase(
    text: str,
    now_utc: datetime,
    local_now: datetime,
    timezone_info: ZoneInfo,
    policy: TemporalResolutionPolicy,
) -> _ResolvedPhrase:
    iso_resolved = _parse_absolute_instant(text)
    if iso_resolved is not None:
        return _ResolvedPhrase(
            state="absolute_instant",
            basis="absolute_iso_instant",
            resolved_at=iso_resolved,
            safe_default_at=None,
            ambiguity_level="none",
            business_calendar_used=False,
        )

    local_datetime = _parse_local_datetime(text, timezone_info)
    if local_datetime is not None:
        return _ResolvedPhrase(
            state="local_datetime",
            basis="local_datetime_text",
            resolved_at=local_datetime.astimezone(timezone.utc),
            safe_default_at=None,
            ambiguity_level="none",
            business_calendar_used=False,
        )

    duration = _parse_duration(text)
    if duration is not None:
        return _ResolvedPhrase(
            state="relative_duration",
            basis="relative_duration_from_runtime_now",
            resolved_at=now_utc + duration,
            safe_default_at=None,
            ambiguity_level="none",
            business_calendar_used=False,
        )

    tomorrow_time = _parse_tomorrow_explicit(text, policy)
    if tomorrow_time is not None:
        resolved = _combine_local(local_now.date() + timedelta(days=1), tomorrow_time, timezone_info)
        return _ResolvedPhrase(
            state="tomorrow_explicit",
            basis="tomorrow_with_explicit_local_time",
            resolved_at=resolved.astimezone(timezone.utc),
            safe_default_at=None,
            ambiguity_level="none",
            business_calendar_used=False,
        )

    if text in {"tomorrow morning", "tomorrow"}:
        default_time = _parse_policy_time(
            policy.default_morning_time if text == "tomorrow morning" else policy.default_due_time
        )
        if default_time is None:
            return _invalid("default_time_invalid")
        resolved = _combine_local(local_now.date() + timedelta(days=1), default_time, timezone_info)
        return _ResolvedPhrase(
            state="tomorrow_defaulted",
            basis="tomorrow_default_policy_time",
            resolved_at=resolved.astimezone(timezone.utc),
            safe_default_at=resolved.astimezone(timezone.utc),
            ambiguity_level="defaulted",
            business_calendar_used=False,
            warning_reasons=("ambiguous_time_defaulted",),
        )

    business_days = _parse_business_days(text)
    if business_days is not None:
        count, mode = business_days
        target_day = _add_business_days(local_now.date(), count, policy)
        if target_day is None:
            return _invalid("business_day_search_exhausted")
        target_time = _parse_policy_time(
            policy.business_day_end_time if mode == "within" else policy.business_day_start_time
        )
        if target_time is None:
            return _invalid("business_day_time_invalid")
        resolved = _combine_local(target_day, target_time, timezone_info)
        return _ResolvedPhrase(
            state="business_day",
            basis=f"{mode}_business_days",
            resolved_at=resolved.astimezone(timezone.utc),
            safe_default_at=resolved.astimezone(timezone.utc),
            ambiguity_level="defaulted",
            business_calendar_used=True,
            business_day_count=count,
            warning_reasons=("business_day_time_defaulted",),
        )

    if text == "next business day":
        target_day = _add_business_days(local_now.date(), 1, policy)
        target_time = _parse_policy_time(policy.business_day_start_time)
        if target_day is None or target_time is None:
            return _invalid("next_business_day_invalid")
        resolved = _combine_local(target_day, target_time, timezone_info)
        return _ResolvedPhrase(
            state="business_day",
            basis="next_business_day",
            resolved_at=resolved.astimezone(timezone.utc),
            safe_default_at=resolved.astimezone(timezone.utc),
            ambiguity_level="defaulted",
            business_calendar_used=True,
            business_day_count=1,
            warning_reasons=("business_day_time_defaulted",),
        )

    if text in {"end of day", "eod", "before end of day"}:
        target_time = _parse_policy_time(policy.business_day_end_time)
        if target_time is None:
            return _invalid("business_day_end_time_invalid")
        resolved = _combine_local(local_now.date(), target_time, timezone_info)
        return _ResolvedPhrase(
            state="end_of_day",
            basis="local_business_day_end",
            resolved_at=resolved.astimezone(timezone.utc),
            safe_default_at=resolved.astimezone(timezone.utc),
            ambiguity_level="defaulted",
            business_calendar_used=True,
            warning_reasons=("business_day_end_defaulted",),
        )

    return _ResolvedPhrase(
        state="unsupported",
        basis="unsupported_temporal_phrase",
        resolved_at=None,
        safe_default_at=None,
        ambiguity_level="unsupported",
        business_calendar_used=False,
    )


def _parse_absolute_instant(text: str) -> datetime | None:
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}t\d{2}:\d{2}(:\d{2})?([+-]\d{2}:\d{2}|z)", text):
        return None
    try:
        return _parse_required_instant(text, "absolute_instant")
    except ValueError:
        return None


def _parse_local_datetime(text: str, timezone_info: ZoneInfo) -> datetime | None:
    match = re.fullmatch(r"(\d{4}-\d{2}-\d{2})[ t](\d{1,2}:\d{2})(:\d{2})?", text)
    if not match:
        return None
    local_day = date.fromisoformat(match.group(1))
    local_time = _parse_policy_time(match.group(2) + (match.group(3) or ""))
    if local_time is None:
        return None
    return _combine_local(local_day, local_time, timezone_info)


def _parse_duration(text: str) -> timedelta | None:
    match = re.fullmatch(r"in\s+(\d+)\s+(minute|minutes|hour|hours|day|days)", text)
    if not match:
        return None
    value = int(match.group(1))
    unit = match.group(2)
    if value <= 0:
        return None
    if unit.startswith("minute"):
        return timedelta(minutes=value)
    if unit.startswith("hour"):
        return timedelta(hours=value)
    return timedelta(days=value)


def _parse_tomorrow_explicit(text: str, policy: TemporalResolutionPolicy) -> time | None:
    if not text.startswith("tomorrow"):
        return None
    match = re.fullmatch(r"tomorrow(?:\s+at)?\s+(.+)", text)
    if not match:
        return None
    candidate = match.group(1).strip()
    if candidate in {"morning", "eod", "end of day"}:
        return None
    return _parse_human_time(candidate)


def _parse_business_days(text: str) -> tuple[int, str] | None:
    match = re.fullmatch(r"(within|in)\s+(\d+)\s+business\s+days?", text)
    if not match:
        return None
    count = int(match.group(2))
    if count <= 0:
        return None
    return count, match.group(1)


def _parse_human_time(value: str) -> time | None:
    compact = value.strip().lower().replace(" ", "")
    match = re.fullmatch(r"(\d{1,2})(?::(\d{2}))?(am|pm)?", compact)
    if not match:
        return _parse_policy_time(value)
    hour = int(match.group(1))
    minute = int(match.group(2) or "0")
    suffix = match.group(3)
    if suffix:
        if hour < 1 or hour > 12:
            return None
        if suffix == "pm" and hour != 12:
            hour += 12
        if suffix == "am" and hour == 12:
            hour = 0
    if hour > 23 or minute > 59:
        return None
    return time(hour=hour, minute=minute)


def _parse_policy_time(value: str) -> time | None:
    try:
        parsed = time.fromisoformat(value)
    except ValueError:
        return None
    return parsed.replace(microsecond=0)


def _policy_violations(policy: TemporalResolutionPolicy) -> list[str]:
    violations: list[str] = []
    timezone_errors: list[str] = []
    _timezone(policy.timezone_name, timezone_errors)
    violations.extend(timezone_errors)
    for field_name in (
        "default_morning_time",
        "default_due_time",
        "business_day_start_time",
        "business_day_end_time",
    ):
        if _parse_policy_time(str(getattr(policy, field_name))) is None:
            violations.append(f"{field_name}_invalid")
    for weekday in policy.business_weekdays:
        if weekday < 0 or weekday > 6:
            violations.append("business_weekday_invalid")
    for holiday in policy.holidays:
        try:
            date.fromisoformat(holiday)
        except ValueError:
            violations.append("holiday_date_invalid")
    start_time = _parse_policy_time(policy.business_day_start_time)
    end_time = _parse_policy_time(policy.business_day_end_time)
    if start_time is not None and end_time is not None and end_time <= start_time:
        violations.append("business_day_window_invalid")
    return _unique(violations)


def _resolved_time_violations(
    now: datetime,
    resolved: _ResolvedPhrase,
    policy: TemporalResolutionPolicy,
) -> list[str]:
    violations: list[str] = []
    candidate = resolved.resolved_at or resolved.safe_default_at
    if candidate is None:
        return violations
    if candidate <= now:
        violations.append("resolved_time_not_future")
    if candidate - now > timedelta(days=policy.max_future_days):
        violations.append("resolved_time_exceeds_policy_horizon")
    return violations


def _clarification_required(request: TemporalResolutionRequest, resolved: _ResolvedPhrase) -> bool:
    return (
        request.resolution_required
        and request.risk_level in HIGH_RISK_LEVELS
        and request.policy.high_risk_requires_explicit_time
        and resolved.ambiguity_level in {"defaulted", "high"}
    )


def _status(
    request: TemporalResolutionRequest,
    resolved: _ResolvedPhrase,
    blocked_reasons: list[str],
    clarification_required: bool,
) -> str:
    if not request.resolution_required:
        return "not_required" if not blocked_reasons else "blocked"
    if blocked_reasons:
        return "blocked"
    if resolved.state == "unsupported":
        return "unsupported"
    if clarification_required:
        return "needs_clarification"
    return "resolved"


def _add_business_days(
    start_day: date,
    business_day_count: int,
    policy: TemporalResolutionPolicy,
) -> date | None:
    observed = 0
    candidate = start_day
    for _ in range(max(policy.max_future_days, business_day_count + 7) + 1):
        candidate += timedelta(days=1)
        if _is_business_day(candidate, policy):
            observed += 1
            if observed == business_day_count:
                return candidate
    return None


def _is_business_day(candidate: date, policy: TemporalResolutionPolicy) -> bool:
    return candidate.weekday() in policy.business_weekdays and candidate.isoformat() not in policy.holidays


def _combine_local(local_day: date, local_time: time, timezone_info: ZoneInfo) -> datetime:
    return datetime.combine(local_day, local_time, tzinfo=timezone_info)


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().lower())


def _invalid(reason: str) -> _ResolvedPhrase:
    return _ResolvedPhrase(
        state="invalid",
        basis=reason,
        resolved_at=None,
        safe_default_at=None,
        ambiguity_level="none",
        business_calendar_used=False,
    )


def _timezone(timezone_name: str, blocked_reasons: list[str]) -> ZoneInfo:
    try:
        return ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        blocked_reasons.append("timezone_invalid")
        return ZoneInfo("UTC")


def _parse_required_instant(value: str, field_name: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field_name}_invalid") from exc
    return _to_utc(parsed, field_name)


def _to_utc(value: datetime, field_name: str) -> datetime:
    if value.tzinfo is None:
        raise ValueError(f"{field_name}_timezone_required")
    return value.astimezone(timezone.utc).replace(microsecond=0)


def _normalize_list(values: list[str]) -> list[str]:
    return _unique([str(value).strip() for value in values if str(value).strip()])


def _unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    unique_values: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            unique_values.append(value)
    return unique_values
