"""Gateway temporal kernel.

Purpose: own runtime time truth for governed action scheduling, expiry,
    freshness, budget windows, causal prerequisites, and latency measurement.
Governance scope: wall-clock admission, monotonic duration witness, temporal
    policy decisions, source evidence age, approval validity, and schedule
    deferral before dispatch.
Dependencies: dataclasses, datetime, time, and command-spine canonical hashing.
Invariants:
  - The runtime clock supplies current time; request text never decides now.
  - Wall-clock timestamps are timezone-aware and evaluated in UTC.
  - Monotonic time is used only for duration measurement.
  - Expired approvals or commands deny execution.
  - Future schedules defer execution without terminal closure.
  - Stale evidence escalates rather than silently executing.
  - Temporal receipts are not terminal closure certificates.
"""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field, replace
from datetime import datetime, timedelta, timezone
from typing import Any

from gateway.command_spine import canonical_hash


TEMPORAL_RECEIPT_SCHEMA_REF = "urn:mullusi:schema:temporal-operation-receipt:1"
TEMPORAL_STATUSES = ("allow", "deny", "defer", "escalate")
RISK_LEVELS = ("low", "medium", "high", "critical")
BASE_TEMPORAL_CONTROLS = (
    "runtime_clock",
    "monotonic_duration",
    "temporal_receipt",
    "terminal_closure",
)


@dataclass(frozen=True, slots=True)
class TrustedClock:
    """Runtime-owned clock surface for wall-clock and duration time."""

    def now_utc(self) -> str:
        """Return timezone-aware UTC wall-clock time for audit and policy."""
        return datetime.now(timezone.utc).isoformat()

    def monotonic_ns(self) -> int:
        """Return monotonic nanoseconds for elapsed duration measurement."""
        return time.monotonic_ns()


@dataclass(frozen=True, slots=True)
class TemporalOperationRequest:
    """One action's temporal constraints before dispatch."""

    request_id: str
    tenant_id: str
    actor_id: str
    command_id: str
    action_type: str
    risk_level: str
    requested_at: str
    evidence_refs: list[str]
    execute_at: str = ""
    expires_at: str = ""
    approval_received_at: str = ""
    approval_expires_at: str = ""
    approval_valid_seconds: int = 0
    evidence_observed_at: str = ""
    evidence_fresh_until: str = ""
    freshness_seconds: int = 0
    budget_period_start: str = ""
    budget_period_end: str = ""
    causal_preconditions: list[str] = field(default_factory=list)
    satisfied_preconditions: list[str] = field(default_factory=list)
    timezone_name: str = "UTC"
    original_time_text: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in (
            "request_id",
            "tenant_id",
            "actor_id",
            "command_id",
            "action_type",
            "risk_level",
            "requested_at",
        ):
            value = str(getattr(self, field_name)).strip()
            if not value:
                raise ValueError(f"{field_name}_required")
            object.__setattr__(self, field_name, value)
        if self.risk_level not in RISK_LEVELS:
            raise ValueError("risk_level_invalid")
        if self.approval_valid_seconds < 0:
            raise ValueError("approval_valid_seconds_nonnegative_required")
        if self.freshness_seconds < 0:
            raise ValueError("freshness_seconds_nonnegative_required")
        object.__setattr__(self, "evidence_refs", _normalize_list(self.evidence_refs))
        object.__setattr__(self, "causal_preconditions", _normalize_list(self.causal_preconditions))
        object.__setattr__(self, "satisfied_preconditions", _normalize_list(self.satisfied_preconditions))
        object.__setattr__(self, "timezone_name", str(self.timezone_name).strip() or "UTC")
        object.__setattr__(self, "original_time_text", str(self.original_time_text).strip())
        object.__setattr__(self, "metadata", dict(self.metadata))


@dataclass(frozen=True, slots=True)
class TemporalOperationReceipt:
    """Schema-backed non-terminal receipt for temporal admission."""

    receipt_id: str
    request_id: str
    tenant_id: str
    actor_id: str
    command_id: str
    action_type: str
    risk_level: str
    status: str
    temporal_violations: list[str]
    temporal_warnings: list[str]
    deferral_reasons: list[str]
    required_controls: list[str]
    runtime_now_utc: str
    monotonic_started_ns: int
    monotonic_finished_ns: int
    duration_ns: int
    requested_at: str
    execute_at: str
    expires_at: str
    approval_received_at: str
    approval_expires_at: str
    evidence_observed_at: str
    evidence_fresh_until: str
    budget_period_start: str
    budget_period_end: str
    causal_preconditions: list[str]
    satisfied_preconditions: list[str]
    missing_preconditions: list[str]
    evidence_refs: list[str]
    timezone_name: str
    original_time_text: str
    receipt_schema_ref: str
    terminal_closure_required: bool
    receipt_hash: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.status not in TEMPORAL_STATUSES:
            raise ValueError("temporal_status_invalid")
        if self.monotonic_started_ns < 0 or self.monotonic_finished_ns < 0:
            raise ValueError("monotonic_ns_nonnegative_required")
        if self.duration_ns < 0:
            raise ValueError("duration_ns_nonnegative_required")
        object.__setattr__(self, "temporal_violations", _normalize_list(self.temporal_violations))
        object.__setattr__(self, "temporal_warnings", _normalize_list(self.temporal_warnings))
        object.__setattr__(self, "deferral_reasons", _normalize_list(self.deferral_reasons))
        object.__setattr__(self, "required_controls", _normalize_list(self.required_controls))
        object.__setattr__(self, "causal_preconditions", _normalize_list(self.causal_preconditions))
        object.__setattr__(self, "satisfied_preconditions", _normalize_list(self.satisfied_preconditions))
        object.__setattr__(self, "missing_preconditions", _normalize_list(self.missing_preconditions))
        object.__setattr__(self, "evidence_refs", _normalize_list(self.evidence_refs))
        object.__setattr__(self, "metadata", dict(self.metadata))


class TemporalKernel:
    """Runtime-owned temporal policy evaluator."""

    def __init__(self, clock: TrustedClock | None = None) -> None:
        self._clock = clock or TrustedClock()

    def evaluate(self, request: TemporalOperationRequest) -> TemporalOperationReceipt:
        """Return the temporal decision for one action before dispatch."""
        monotonic_started_ns = self._clock.monotonic_ns()
        runtime_now_utc = self._clock.now_utc()
        temporal_violations: list[str] = []
        temporal_warnings: list[str] = []
        deferral_reasons: list[str] = []
        required_controls = [*BASE_TEMPORAL_CONTROLS]
        parsed = _parse_temporal_request(request, temporal_violations)

        now = _parse_required_instant(runtime_now_utc)
        _apply_schedule_rules(request, parsed, now, deferral_reasons, required_controls)
        _apply_expiry_rules(parsed, now, temporal_violations, required_controls)
        _apply_approval_rules(request, parsed, now, temporal_violations, required_controls)
        approval_expires_at = _approval_expires_at(request, parsed)
        evidence_fresh_until = _evidence_fresh_until(request, parsed)
        _apply_evidence_freshness_rules(
            evidence_fresh_until,
            now,
            temporal_warnings,
            required_controls,
        )
        _apply_budget_window_rules(request, parsed, now, temporal_violations, required_controls)
        missing_preconditions = _missing_preconditions(request)
        if missing_preconditions:
            temporal_violations.append("causal_preconditions_missing")
            required_controls.append("causal_order")
        if not request.evidence_refs:
            temporal_violations.append("evidence_refs_required")
            required_controls.append("evidence_reference")
        if request.risk_level in {"high", "critical"}:
            required_controls.extend(("approval_validity", "evidence_freshness", "causal_order"))

        monotonic_finished_ns = self._clock.monotonic_ns()
        duration_ns = max(0, monotonic_finished_ns - monotonic_started_ns)
        status = _status(temporal_violations, temporal_warnings, deferral_reasons)
        receipt = TemporalOperationReceipt(
            receipt_id="pending",
            request_id=request.request_id,
            tenant_id=request.tenant_id,
            actor_id=request.actor_id,
            command_id=request.command_id,
            action_type=request.action_type,
            risk_level=request.risk_level,
            status=status,
            temporal_violations=_unique(temporal_violations),
            temporal_warnings=_unique(temporal_warnings),
            deferral_reasons=_unique(deferral_reasons),
            required_controls=_unique(required_controls),
            runtime_now_utc=now.isoformat(),
            monotonic_started_ns=monotonic_started_ns,
            monotonic_finished_ns=monotonic_finished_ns,
            duration_ns=duration_ns,
            requested_at=_instant_text(parsed, "requested_at", request.requested_at),
            execute_at=_instant_text(parsed, "execute_at", request.execute_at),
            expires_at=_instant_text(parsed, "expires_at", request.expires_at),
            approval_received_at=_instant_text(
                parsed,
                "approval_received_at",
                request.approval_received_at,
            ),
            approval_expires_at=_instant_text(
                parsed,
                "approval_expires_at",
                approval_expires_at.isoformat() if approval_expires_at else request.approval_expires_at,
            ),
            evidence_observed_at=_instant_text(parsed, "evidence_observed_at", request.evidence_observed_at),
            evidence_fresh_until=evidence_fresh_until.isoformat() if evidence_fresh_until else request.evidence_fresh_until,
            budget_period_start=_instant_text(parsed, "budget_period_start", request.budget_period_start),
            budget_period_end=_instant_text(parsed, "budget_period_end", request.budget_period_end),
            causal_preconditions=request.causal_preconditions,
            satisfied_preconditions=request.satisfied_preconditions,
            missing_preconditions=missing_preconditions,
            evidence_refs=request.evidence_refs,
            timezone_name=request.timezone_name,
            original_time_text=request.original_time_text,
            receipt_schema_ref=TEMPORAL_RECEIPT_SCHEMA_REF,
            terminal_closure_required=True,
            metadata={
                "receipt_is_not_terminal_closure": True,
                "dispatch_allowed": status == "allow",
                "runtime_owns_time_truth": True,
                "wall_clock_used_for_policy": True,
                "monotonic_used_for_duration": True,
                "approval_valid_seconds": request.approval_valid_seconds,
                "freshness_seconds": request.freshness_seconds,
            },
        )
        receipt_hash = canonical_hash(asdict(receipt))
        return replace(
            receipt,
            receipt_id=f"temporal-receipt-{receipt_hash[:16]}",
            receipt_hash=receipt_hash,
        )


def _parse_temporal_request(
    request: TemporalOperationRequest,
    temporal_violations: list[str],
) -> dict[str, datetime]:
    parsed: dict[str, datetime] = {}
    for field_name in (
        "requested_at",
        "execute_at",
        "expires_at",
        "approval_received_at",
        "approval_expires_at",
        "evidence_observed_at",
        "evidence_fresh_until",
        "budget_period_start",
        "budget_period_end",
    ):
        raw_value = str(getattr(request, field_name)).strip()
        if not raw_value:
            continue
        try:
            parsed[field_name] = _parse_required_instant(raw_value)
        except ValueError:
            temporal_violations.append(f"{field_name}_invalid")
    return parsed


def _apply_schedule_rules(
    request: TemporalOperationRequest,
    parsed: dict[str, datetime],
    now: datetime,
    deferral_reasons: list[str],
    required_controls: list[str],
) -> None:
    if request.execute_at:
        required_controls.append("schedule_due")
    execute_at = parsed.get("execute_at")
    if execute_at and now < execute_at:
        deferral_reasons.append("scheduled_for_future")


def _apply_expiry_rules(
    parsed: dict[str, datetime],
    now: datetime,
    temporal_violations: list[str],
    required_controls: list[str],
) -> None:
    expires_at = parsed.get("expires_at")
    if expires_at:
        required_controls.append("command_expiry")
    if expires_at and now > expires_at:
        temporal_violations.append("command_expired")


def _apply_approval_rules(
    request: TemporalOperationRequest,
    parsed: dict[str, datetime],
    now: datetime,
    temporal_violations: list[str],
    required_controls: list[str],
) -> None:
    approval_expires_at = _approval_expires_at(request, parsed)
    if approval_expires_at:
        required_controls.append("approval_validity")
    if approval_expires_at and now > approval_expires_at:
        temporal_violations.append("approval_expired")


def _apply_evidence_freshness_rules(
    evidence_fresh_until: datetime | None,
    now: datetime,
    temporal_warnings: list[str],
    required_controls: list[str],
) -> None:
    if evidence_fresh_until:
        required_controls.append("evidence_freshness")
    if evidence_fresh_until and now > evidence_fresh_until:
        temporal_warnings.append("evidence_stale")


def _apply_budget_window_rules(
    request: TemporalOperationRequest,
    parsed: dict[str, datetime],
    now: datetime,
    temporal_violations: list[str],
    required_controls: list[str],
) -> None:
    if request.budget_period_start or request.budget_period_end:
        required_controls.append("budget_window")
    budget_period_start = parsed.get("budget_period_start")
    budget_period_end = parsed.get("budget_period_end")
    if budget_period_start and now < budget_period_start:
        temporal_violations.append("budget_window_not_started")
    if budget_period_end and now > budget_period_end:
        temporal_violations.append("budget_window_expired")
    if budget_period_start and budget_period_end and budget_period_end <= budget_period_start:
        temporal_violations.append("budget_window_invalid")


def _approval_expires_at(
    request: TemporalOperationRequest,
    parsed: dict[str, datetime],
) -> datetime | None:
    explicit_expiry = parsed.get("approval_expires_at")
    if explicit_expiry:
        return explicit_expiry
    approval_received_at = parsed.get("approval_received_at")
    if approval_received_at and request.approval_valid_seconds > 0:
        return approval_received_at + timedelta(seconds=request.approval_valid_seconds)
    return None


def _evidence_fresh_until(
    request: TemporalOperationRequest,
    parsed: dict[str, datetime],
) -> datetime | None:
    explicit_fresh_until = parsed.get("evidence_fresh_until")
    if explicit_fresh_until:
        return explicit_fresh_until
    evidence_observed_at = parsed.get("evidence_observed_at")
    if evidence_observed_at and request.freshness_seconds > 0:
        return evidence_observed_at + timedelta(seconds=request.freshness_seconds)
    return None


def _missing_preconditions(request: TemporalOperationRequest) -> list[str]:
    satisfied = set(request.satisfied_preconditions)
    return [precondition for precondition in request.causal_preconditions if precondition not in satisfied]


def _status(
    temporal_violations: list[str],
    temporal_warnings: list[str],
    deferral_reasons: list[str],
) -> str:
    if temporal_violations:
        return "deny"
    if temporal_warnings:
        return "escalate"
    if deferral_reasons:
        return "defer"
    return "allow"


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
