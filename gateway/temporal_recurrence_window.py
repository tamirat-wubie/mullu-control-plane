"""Temporal recurrence-window receipt evaluator.

Purpose: certify the next occurrence of a recurring scheduled command before
that occurrence is admitted, deferred, completed, or blocked.
Governance scope: runtime-owned time truth, recurrence rule parsing, tenant
timezone preservation, duplicate-run prevention, scheduler source linkage,
high-risk reapproval linkage, and non-terminal recurrence receipts.
Dependencies: standard calendar/datetime/hashlib/json/zoneinfo libraries only.
Invariants: recurrence truth is computed by runtime code; unsupported recurrence
rules fail closed; this receipt is not terminal closure.
"""

from __future__ import annotations

import calendar
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
import hashlib
import json
from typing import Any, Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


TEMPORAL_RECURRENCE_WINDOW_RECEIPT_SCHEMA_REF = "urn:mullusi:schema:temporal-recurrence-window-receipt:1"

RiskLevel = Literal["low", "medium", "high", "critical"]
RecurrenceWindowStatus = Literal["next_due", "not_due", "completed", "blocked", "not_required"]
RecurrenceWindowState = Literal[
    "candidate_matches",
    "candidate_future",
    "series_completed",
    "wrong_scope",
    "duplicate_blocked",
    "invalid",
    "not_required",
]

RISK_LEVELS = {"low", "medium", "high", "critical"}
HIGH_RISK_LEVELS = {"high", "critical"}
SUPPORTED_FREQUENCIES = {"DAILY", "WEEKLY", "MONTHLY"}
SUPPORTED_RRULE_KEYS = {"FREQ", "INTERVAL", "COUNT", "UNTIL"}
BASE_REQUIRED_CONTROLS = (
    "runtime_now_utc_injected",
    "recurrence_rule_parsed",
    "tenant_timezone_preserved",
    "scheduler_receipt_linked",
    "evidence_refs_present",
    "terminal_closure_required",
)
HIGH_RISK_REQUIRED_CONTROLS = (
    "reapproval_required_when_due",
    "temporal_policy_receipt_linked_when_due",
)


@dataclass(frozen=True)
class RecurrenceWindowPolicy:
    """Tenant policy for recurrence-window admission."""

    policy_id: str
    tenant_id: str
    timezone_name: str
    requires_recurrence_receipt: bool = True
    high_risk_requires_reapproval_when_due: bool = True
    candidate_tolerance_seconds: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.policy_id.strip():
            raise ValueError("policy_id is required")
        if not self.tenant_id.strip():
            raise ValueError("tenant_id is required")
        if not self.timezone_name.strip():
            raise ValueError("timezone_name is required")
        if self.candidate_tolerance_seconds < 0:
            raise ValueError("candidate_tolerance_seconds must be non-negative")
        _timezone(self.timezone_name)


@dataclass(frozen=True)
class RecurrenceWindowSnapshot:
    """Observed recurring schedule state for the next candidate occurrence."""

    schedule_id: str
    tenant_id: str
    command_id: str
    action_type: str
    recurrence_rule: str
    previous_execute_at: str
    candidate_execute_at: str
    occurrence_index: int
    recurring: bool = True
    last_dispatched_at: str = ""
    terminal_receipt_id: str = ""
    scheduler_receipt_id: str = ""
    evidence_refs: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.schedule_id.strip():
            raise ValueError("schedule_id is required")
        if not self.tenant_id.strip():
            raise ValueError("tenant_id is required")
        if not self.command_id.strip():
            raise ValueError("command_id is required")
        if not self.action_type.strip():
            raise ValueError("action_type is required")
        if self.occurrence_index < 0:
            raise ValueError("occurrence_index must be non-negative")


@dataclass(frozen=True)
class RecurrenceWindowRequest:
    """Input contract for issuing a temporal recurrence-window receipt."""

    request_id: str
    tenant_id: str
    actor_id: str
    command_id: str
    action_type: str
    risk_level: RiskLevel
    policy: RecurrenceWindowPolicy
    snapshot: RecurrenceWindowSnapshot | None = None
    evidence_refs: list[str] = field(default_factory=list)
    source_scheduler_receipt_id: str = ""
    source_temporal_receipt_id: str = ""
    source_missed_run_receipt_id: str = ""
    source_reapproval_receipt_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.request_id.strip():
            raise ValueError("request_id is required")
        if not self.tenant_id.strip():
            raise ValueError("tenant_id is required")
        if not self.actor_id.strip():
            raise ValueError("actor_id is required")
        if not self.command_id.strip():
            raise ValueError("command_id is required")
        if not self.action_type.strip():
            raise ValueError("action_type is required")
        if self.risk_level not in RISK_LEVELS:
            raise ValueError(f"risk_level must be one of {sorted(RISK_LEVELS)}")


@dataclass(frozen=True)
class TemporalRecurrenceWindowReceipt:
    """Proof artifact for recurrence-window admission."""

    receipt_id: str
    request_id: str
    tenant_id: str
    actor_id: str
    command_id: str
    action_type: str
    risk_level: str
    policy_id: str
    schedule_id: str
    status: RecurrenceWindowStatus
    recurrence_state: RecurrenceWindowState
    runtime_now_utc: str
    recurrence_required: bool
    timezone_name: str
    recurrence_rule: str
    frequency: str
    interval: int
    occurrence_index: int
    count_limit: int
    until: str
    previous_execute_at: str
    candidate_execute_at: str
    expected_next_execute_at: str
    candidate_local_time: str
    expected_local_time: str
    candidate_tolerance_seconds: int
    series_completed: bool
    blocked_reasons: list[str]
    deferral_reasons: list[str]
    required_controls: list[str]
    evidence_refs: list[str]
    snapshot_evidence_refs: list[str]
    source_scheduler_receipt_id: str
    source_temporal_receipt_id: str
    source_missed_run_receipt_id: str
    source_reapproval_receipt_id: str
    scheduler_receipt_id: str
    terminal_receipt_id: str
    receipt_schema_ref: str
    terminal_closure_required: bool
    receipt_hash: str
    metadata: dict[str, Any]


def evaluate_temporal_recurrence_window(
    request: RecurrenceWindowRequest,
    *,
    runtime_now_utc: datetime,
) -> TemporalRecurrenceWindowReceipt:
    """Classify the next occurrence of a recurring scheduled command.

    Input contract: request contains tenant/action scope, policy, optional
    recurring schedule snapshot, and upstream receipt references.
    Output contract: returns a schema-backed receipt with status, reasons,
    expected next occurrence, timezone projection, and stable hash.
    Error contract: malformed dataclass fields raise ValueError; semantic
    violations are represented as status="blocked" with blocked_reasons.
    """

    now = _to_utc(runtime_now_utc, "runtime_now_utc")
    recurrence_required = _recurrence_required(request)
    required_controls = _required_controls(request, recurrence_required)
    blocked_reasons: list[str] = []
    deferral_reasons: list[str] = []

    if request.policy.tenant_id != request.tenant_id:
        blocked_reasons.append("policy_tenant_mismatch")

    if not recurrence_required and blocked_reasons:
        return _build_receipt(
            request=request,
            now=now,
            status="blocked",
            recurrence_state="wrong_scope",
            recurrence_required=True,
            snapshot=None,
            parsed_rule={},
            previous_dt=None,
            candidate_dt=None,
            expected_dt=None,
            blocked_reasons=blocked_reasons,
            deferral_reasons=[],
            required_controls=required_controls,
            series_completed=False,
        )

    if not recurrence_required:
        return _build_receipt(
            request=request,
            now=now,
            status="not_required",
            recurrence_state="not_required",
            recurrence_required=False,
            snapshot=None,
            parsed_rule={},
            previous_dt=None,
            candidate_dt=None,
            expected_dt=None,
            blocked_reasons=[],
            deferral_reasons=[],
            required_controls=[],
            series_completed=False,
        )

    snapshot = request.snapshot
    if snapshot is None:
        blocked_reasons.append("recurrence_snapshot_required")
        return _build_receipt(
            request=request,
            now=now,
            status="blocked",
            recurrence_state="invalid",
            recurrence_required=True,
            snapshot=None,
            parsed_rule={},
            previous_dt=None,
            candidate_dt=None,
            expected_dt=None,
            blocked_reasons=blocked_reasons,
            deferral_reasons=[],
            required_controls=required_controls,
            series_completed=False,
        )

    parsed_rule = _parse_recurrence_rule(snapshot.recurrence_rule, blocked_reasons)
    previous_dt = _parse_snapshot_time(snapshot.previous_execute_at, "previous_execute_at", blocked_reasons)
    candidate_dt = _parse_snapshot_time(snapshot.candidate_execute_at, "candidate_execute_at", blocked_reasons)
    last_dispatched_dt = _parse_optional_snapshot_time(snapshot.last_dispatched_at, "last_dispatched_at", blocked_reasons)
    expected_dt = _expected_next_occurrence(request.policy, parsed_rule, previous_dt, blocked_reasons)

    _apply_scope_rules(request, snapshot, blocked_reasons)
    _apply_source_rules(request, snapshot, recurrence_required, now, candidate_dt, blocked_reasons)
    series_completed = _series_completed(snapshot, parsed_rule, expected_dt, blocked_reasons)
    _apply_candidate_rules(
        request=request,
        snapshot=snapshot,
        candidate_dt=candidate_dt,
        expected_dt=expected_dt,
        last_dispatched_dt=last_dispatched_dt,
        blocked_reasons=blocked_reasons,
    )

    status, state = _decide_status_and_state(
        now=now,
        candidate_dt=candidate_dt,
        blocked_reasons=blocked_reasons,
        deferral_reasons=deferral_reasons,
        series_completed=series_completed,
    )

    return _build_receipt(
        request=request,
        now=now,
        status=status,
        recurrence_state=state,
        recurrence_required=True,
        snapshot=snapshot,
        parsed_rule=parsed_rule,
        previous_dt=previous_dt,
        candidate_dt=candidate_dt,
        expected_dt=expected_dt,
        blocked_reasons=blocked_reasons,
        deferral_reasons=deferral_reasons,
        required_controls=required_controls,
        series_completed=series_completed,
    )


def receipt_to_dict(receipt: TemporalRecurrenceWindowReceipt) -> dict[str, Any]:
    """Return a JSON-schema-ready receipt mapping."""

    return {
        "receipt_id": receipt.receipt_id,
        "request_id": receipt.request_id,
        "tenant_id": receipt.tenant_id,
        "actor_id": receipt.actor_id,
        "command_id": receipt.command_id,
        "action_type": receipt.action_type,
        "risk_level": receipt.risk_level,
        "policy_id": receipt.policy_id,
        "schedule_id": receipt.schedule_id,
        "status": receipt.status,
        "recurrence_state": receipt.recurrence_state,
        "runtime_now_utc": receipt.runtime_now_utc,
        "recurrence_required": receipt.recurrence_required,
        "timezone_name": receipt.timezone_name,
        "recurrence_rule": receipt.recurrence_rule,
        "frequency": receipt.frequency,
        "interval": receipt.interval,
        "occurrence_index": receipt.occurrence_index,
        "count_limit": receipt.count_limit,
        "until": receipt.until,
        "previous_execute_at": receipt.previous_execute_at,
        "candidate_execute_at": receipt.candidate_execute_at,
        "expected_next_execute_at": receipt.expected_next_execute_at,
        "candidate_local_time": receipt.candidate_local_time,
        "expected_local_time": receipt.expected_local_time,
        "candidate_tolerance_seconds": receipt.candidate_tolerance_seconds,
        "series_completed": receipt.series_completed,
        "blocked_reasons": receipt.blocked_reasons,
        "deferral_reasons": receipt.deferral_reasons,
        "required_controls": receipt.required_controls,
        "evidence_refs": receipt.evidence_refs,
        "snapshot_evidence_refs": receipt.snapshot_evidence_refs,
        "source_scheduler_receipt_id": receipt.source_scheduler_receipt_id,
        "source_temporal_receipt_id": receipt.source_temporal_receipt_id,
        "source_missed_run_receipt_id": receipt.source_missed_run_receipt_id,
        "source_reapproval_receipt_id": receipt.source_reapproval_receipt_id,
        "scheduler_receipt_id": receipt.scheduler_receipt_id,
        "terminal_receipt_id": receipt.terminal_receipt_id,
        "receipt_schema_ref": receipt.receipt_schema_ref,
        "terminal_closure_required": receipt.terminal_closure_required,
        "receipt_hash": receipt.receipt_hash,
        "metadata": receipt.metadata,
    }


def _recurrence_required(request: RecurrenceWindowRequest) -> bool:
    if request.snapshot and not request.snapshot.recurring:
        return False
    return request.policy.requires_recurrence_receipt


def _required_controls(request: RecurrenceWindowRequest, recurrence_required: bool) -> list[str]:
    if not recurrence_required:
        return []
    controls = list(BASE_REQUIRED_CONTROLS)
    if request.risk_level in HIGH_RISK_LEVELS:
        controls.extend(HIGH_RISK_REQUIRED_CONTROLS)
    return controls


def _apply_scope_rules(
    request: RecurrenceWindowRequest,
    snapshot: RecurrenceWindowSnapshot,
    blocked_reasons: list[str],
) -> None:
    if snapshot.tenant_id != request.tenant_id:
        blocked_reasons.append("snapshot_tenant_mismatch")
    if snapshot.command_id != request.command_id:
        blocked_reasons.append("snapshot_command_mismatch")
    if snapshot.action_type != request.action_type:
        blocked_reasons.append("snapshot_action_type_mismatch")
    if not snapshot.recurring:
        blocked_reasons.append("snapshot_not_recurring")


def _apply_source_rules(
    request: RecurrenceWindowRequest,
    snapshot: RecurrenceWindowSnapshot,
    recurrence_required: bool,
    now: datetime,
    candidate_dt: datetime | None,
    blocked_reasons: list[str],
) -> None:
    if not recurrence_required:
        return
    if not request.evidence_refs:
        blocked_reasons.append("evidence_refs_required")
    if not snapshot.evidence_refs:
        blocked_reasons.append("snapshot_evidence_refs_required")
    if not request.source_scheduler_receipt_id.strip():
        blocked_reasons.append("source_scheduler_receipt_required")
    if snapshot.scheduler_receipt_id and request.source_scheduler_receipt_id != snapshot.scheduler_receipt_id:
        blocked_reasons.append("scheduler_receipt_mismatch")
    if request.risk_level in HIGH_RISK_LEVELS and candidate_dt and candidate_dt <= now:
        if not request.source_temporal_receipt_id.strip():
            blocked_reasons.append("source_temporal_receipt_required_for_high_risk_due_candidate")
        if request.policy.high_risk_requires_reapproval_when_due and not request.source_reapproval_receipt_id.strip():
            blocked_reasons.append("source_reapproval_receipt_required_for_high_risk_due_candidate")


def _apply_candidate_rules(
    *,
    request: RecurrenceWindowRequest,
    snapshot: RecurrenceWindowSnapshot,
    candidate_dt: datetime | None,
    expected_dt: datetime | None,
    last_dispatched_dt: datetime | None,
    blocked_reasons: list[str],
) -> None:
    previous_dt = _parse_optional_snapshot_time(snapshot.previous_execute_at, "previous_execute_at", blocked_reasons)
    if previous_dt and candidate_dt and candidate_dt <= previous_dt:
        blocked_reasons.append("candidate_not_after_previous_execute_at")
    if candidate_dt and expected_dt:
        delta = abs(int((candidate_dt - expected_dt).total_seconds()))
        if delta > request.policy.candidate_tolerance_seconds:
            blocked_reasons.append("candidate_execute_at_not_next_occurrence")
    if last_dispatched_dt and candidate_dt and last_dispatched_dt >= candidate_dt:
        blocked_reasons.append("candidate_already_dispatched")
        if not snapshot.terminal_receipt_id.strip():
            blocked_reasons.append("terminal_receipt_required_for_dispatched_candidate")


def _series_completed(
    snapshot: RecurrenceWindowSnapshot,
    parsed_rule: dict[str, Any],
    expected_dt: datetime | None,
    blocked_reasons: list[str],
) -> bool:
    del blocked_reasons
    count_limit = int(parsed_rule.get("COUNT", 0) or 0)
    if count_limit and snapshot.occurrence_index >= count_limit:
        return True
    until = parsed_rule.get("UNTIL_DT")
    if until and expected_dt and expected_dt > until:
        return True
    return False


def _decide_status_and_state(
    *,
    now: datetime,
    candidate_dt: datetime | None,
    blocked_reasons: list[str],
    deferral_reasons: list[str],
    series_completed: bool,
) -> tuple[RecurrenceWindowStatus, RecurrenceWindowState]:
    if blocked_reasons:
        if any(reason.endswith("_mismatch") or reason == "policy_tenant_mismatch" for reason in blocked_reasons):
            return "blocked", "wrong_scope"
        if any("already_dispatched" in reason for reason in blocked_reasons):
            return "blocked", "duplicate_blocked"
        return "blocked", "invalid"
    if series_completed:
        return "completed", "series_completed"
    if candidate_dt and candidate_dt > now:
        deferral_reasons.append("recurrence_candidate_not_due")
        return "not_due", "candidate_future"
    if candidate_dt:
        return "next_due", "candidate_matches"
    return "blocked", "invalid"


def _build_receipt(
    *,
    request: RecurrenceWindowRequest,
    now: datetime,
    status: RecurrenceWindowStatus,
    recurrence_state: RecurrenceWindowState,
    recurrence_required: bool,
    snapshot: RecurrenceWindowSnapshot | None,
    parsed_rule: dict[str, Any],
    previous_dt: datetime | None,
    candidate_dt: datetime | None,
    expected_dt: datetime | None,
    blocked_reasons: list[str],
    deferral_reasons: list[str],
    required_controls: list[str],
    series_completed: bool,
) -> TemporalRecurrenceWindowReceipt:
    normalized_now = _format_dt(now)
    expected_local_time = _format_local(expected_dt, request.policy.timezone_name)
    candidate_local_time = _format_local(candidate_dt, request.policy.timezone_name)
    receipt_seed = {
        "request_id": request.request_id,
        "tenant_id": request.tenant_id,
        "command_id": request.command_id,
        "status": status,
        "state": recurrence_state,
        "runtime_now_utc": normalized_now,
        "expected_next_execute_at": _format_optional_dt(expected_dt),
        "candidate_execute_at": _format_optional_dt(candidate_dt),
        "blocked_reasons": sorted(set(blocked_reasons)),
    }
    receipt_hash = _stable_hash(receipt_seed)
    metadata = {
        **request.metadata,
        "runtime_owns_time_truth": True,
        "receipt_is_not_terminal_closure": True,
        "recurrence_checked": recurrence_required,
        "dispatch_allowed": status == "next_due",
        "terminal_closure_required": True,
        "timezone_preserved": bool(expected_local_time),
        "high_risk_reapproval_checked": (
            request.risk_level not in HIGH_RISK_LEVELS
            or status != "next_due"
            or bool(request.source_reapproval_receipt_id)
        ),
    }
    return TemporalRecurrenceWindowReceipt(
        receipt_id=f"temporal-recurrence-window-receipt-{receipt_hash[:16]}",
        request_id=request.request_id,
        tenant_id=request.tenant_id,
        actor_id=request.actor_id,
        command_id=request.command_id,
        action_type=request.action_type,
        risk_level=request.risk_level,
        policy_id=request.policy.policy_id,
        schedule_id=snapshot.schedule_id if snapshot else "",
        status=status,
        recurrence_state=recurrence_state,
        runtime_now_utc=normalized_now,
        recurrence_required=recurrence_required,
        timezone_name=request.policy.timezone_name,
        recurrence_rule=snapshot.recurrence_rule if snapshot else "",
        frequency=str(parsed_rule.get("FREQ", "")),
        interval=int(parsed_rule.get("INTERVAL", 0) or 0),
        occurrence_index=snapshot.occurrence_index if snapshot else 0,
        count_limit=int(parsed_rule.get("COUNT", 0) or 0),
        until=_format_optional_dt(parsed_rule.get("UNTIL_DT")),
        previous_execute_at=_format_optional_dt(previous_dt),
        candidate_execute_at=_format_optional_dt(candidate_dt),
        expected_next_execute_at=_format_optional_dt(expected_dt),
        candidate_local_time=candidate_local_time,
        expected_local_time=expected_local_time,
        candidate_tolerance_seconds=request.policy.candidate_tolerance_seconds,
        series_completed=series_completed,
        blocked_reasons=sorted(set(blocked_reasons)),
        deferral_reasons=sorted(set(deferral_reasons)),
        required_controls=required_controls,
        evidence_refs=sorted(set(request.evidence_refs)),
        snapshot_evidence_refs=sorted(set(snapshot.evidence_refs)) if snapshot else [],
        source_scheduler_receipt_id=request.source_scheduler_receipt_id,
        source_temporal_receipt_id=request.source_temporal_receipt_id,
        source_missed_run_receipt_id=request.source_missed_run_receipt_id,
        source_reapproval_receipt_id=request.source_reapproval_receipt_id,
        scheduler_receipt_id=snapshot.scheduler_receipt_id if snapshot else "",
        terminal_receipt_id=snapshot.terminal_receipt_id if snapshot else "",
        receipt_schema_ref=TEMPORAL_RECURRENCE_WINDOW_RECEIPT_SCHEMA_REF,
        terminal_closure_required=True,
        receipt_hash=receipt_hash,
        metadata=metadata,
    )


def _parse_recurrence_rule(value: str, blocked_reasons: list[str]) -> dict[str, Any]:
    if not value.strip():
        blocked_reasons.append("recurrence_rule_required")
        return {}
    parsed: dict[str, Any] = {}
    for part in value.split(";"):
        if "=" not in part:
            blocked_reasons.append("recurrence_rule_invalid_part")
            continue
        key, raw_value = part.split("=", 1)
        key = key.strip().upper()
        raw_value = raw_value.strip()
        if key not in SUPPORTED_RRULE_KEYS:
            blocked_reasons.append(f"recurrence_rule_unsupported_key_{key.lower()}")
            continue
        parsed[key] = raw_value.upper() if key == "FREQ" else raw_value
    frequency = str(parsed.get("FREQ", ""))
    if frequency not in SUPPORTED_FREQUENCIES:
        blocked_reasons.append("recurrence_frequency_unsupported")
    try:
        interval = int(parsed.get("INTERVAL", "1"))
        if interval <= 0:
            raise ValueError
        parsed["INTERVAL"] = interval
    except ValueError:
        blocked_reasons.append("recurrence_interval_invalid")
    if "COUNT" in parsed:
        try:
            count = int(parsed["COUNT"])
            if count <= 0:
                raise ValueError
            parsed["COUNT"] = count
        except ValueError:
            blocked_reasons.append("recurrence_count_invalid")
    if "UNTIL" in parsed:
        until = _parse_optional_snapshot_time(str(parsed["UNTIL"]), "until", blocked_reasons)
        if until:
            parsed["UNTIL_DT"] = until
    return parsed


def _expected_next_occurrence(
    policy: RecurrenceWindowPolicy,
    parsed_rule: dict[str, Any],
    previous_dt: datetime | None,
    blocked_reasons: list[str],
) -> datetime | None:
    if previous_dt is None:
        return None
    frequency = parsed_rule.get("FREQ")
    interval = int(parsed_rule.get("INTERVAL", 0) or 0)
    if frequency not in SUPPORTED_FREQUENCIES or interval <= 0:
        return None
    local_previous = previous_dt.astimezone(_timezone(policy.timezone_name))
    if frequency == "DAILY":
        local_next = local_previous + timedelta(days=interval)
    elif frequency == "WEEKLY":
        local_next = local_previous + timedelta(days=7 * interval)
    elif frequency == "MONTHLY":
        local_next = _add_months(local_previous, interval)
    else:
        blocked_reasons.append("recurrence_frequency_unsupported")
        return None
    return local_next.astimezone(timezone.utc)


def _add_months(value: datetime, months: int) -> datetime:
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return value.replace(year=year, month=month, day=day)


def _parse_snapshot_time(
    value: str,
    field_name: str,
    blocked_reasons: list[str],
) -> datetime | None:
    if not value.strip():
        blocked_reasons.append(f"{field_name}_required")
        return None
    return _parse_optional_snapshot_time(value, field_name, blocked_reasons)


def _parse_optional_snapshot_time(
    value: str,
    field_name: str,
    blocked_reasons: list[str],
) -> datetime | None:
    if not value.strip():
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        blocked_reasons.append(f"{field_name}_invalid_rfc3339")
        return None
    try:
        return _to_utc(parsed, field_name)
    except ValueError:
        blocked_reasons.append(f"{field_name}_timezone_required")
        return None


def _to_utc(value: datetime, field_name: str) -> datetime:
    if value.tzinfo is None:
        raise ValueError(f"{field_name} must be timezone-aware")
    return value.astimezone(timezone.utc)


def _timezone(timezone_name: str) -> ZoneInfo:
    try:
        return ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError as exc:
        raise ValueError("timezone_name_invalid") from exc


def _format_optional_dt(value: datetime | None) -> str:
    if value is None:
        return ""
    return _format_dt(value)


def _format_dt(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _format_local(value: datetime | None, timezone_name: str) -> str:
    if value is None:
        return ""
    return value.astimezone(_timezone(timezone_name)).isoformat()


def _stable_hash(value: dict[str, Any]) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
