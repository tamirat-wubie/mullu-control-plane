"""Temporal missed-run receipt evaluator.

Purpose: issue a governed receipt when a scheduled command is late, expired,
or needs recovery review before any skip, retry, or terminal closure decision.
Governance scope: runtime-owned time truth, scheduler source linkage, evidence
freshness linkage, and high-risk reapproval linkage.
Dependencies: standard datetime/hashlib/json libraries only.
Invariants: wall-clock truth comes from the caller-injected runtime timestamp;
this receipt is not terminal closure; required missed-run paths cannot be silent.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import json
from typing import Any, Literal


TEMPORAL_MISSED_RUN_RECEIPT_SCHEMA_REF = "urn:mullusi:schema:temporal-missed-run-receipt:1"

RiskLevel = Literal["low", "medium", "high", "critical"]
MissedRunStatus = Literal[
    "missed",
    "late_within_grace",
    "recovery_due",
    "duplicate_dispatched",
    "blocked",
    "not_required",
]
MissedRunState = Literal[
    "missed_expired",
    "late_allowed",
    "recovery_allowed",
    "already_dispatched",
    "wrong_scope",
    "invalid",
    "not_required",
]

HIGH_RISK_LEVELS = {"high", "critical"}
RISK_LEVELS = {"low", "medium", "high", "critical"}
BASE_REQUIRED_CONTROLS = (
    "runtime_now_utc_injected",
    "scheduler_receipt_linked",
    "evidence_refs_present",
    "missed_run_receipt_emitted",
    "terminal_closure_required",
)
HIGH_RISK_REQUIRED_CONTROLS = (
    "temporal_policy_receipt_linked",
    "reapproval_receipt_linked",
)


@dataclass(frozen=True)
class MissedRunPolicy:
    """Tenant policy for classifying missed scheduled commands."""

    policy_id: str
    tenant_id: str
    scope_id: str
    max_lateness_seconds: int
    grace_seconds: int = 0
    requires_missed_run_receipt: bool = True
    high_risk_requires_missed_run_receipt: bool = True
    allow_recovery_after_miss: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.policy_id.strip():
            raise ValueError("policy_id is required")
        if not self.tenant_id.strip():
            raise ValueError("tenant_id is required")
        if not self.scope_id.strip():
            raise ValueError("scope_id is required")
        if self.max_lateness_seconds < 0:
            raise ValueError("max_lateness_seconds must be non-negative")
        if self.grace_seconds < 0:
            raise ValueError("grace_seconds must be non-negative")


@dataclass(frozen=True)
class MissedRunSnapshot:
    """Observed scheduler state for a command that may have missed its run."""

    schedule_id: str
    tenant_id: str
    command_id: str
    action_type: str
    execute_at: str
    observed_at: str
    expires_at: str = ""
    last_attempt_at: str = ""
    attempt_count: int = 0
    max_attempts: int = 1
    recurring: bool = False
    recurrence_rule: str = ""
    already_dispatched: bool = False
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
        if self.attempt_count < 0:
            raise ValueError("attempt_count must be non-negative")
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")


@dataclass(frozen=True)
class MissedRunRequest:
    """Input contract for issuing a temporal missed-run receipt."""

    request_id: str
    tenant_id: str
    actor_id: str
    command_id: str
    action_type: str
    risk_level: RiskLevel
    policy: MissedRunPolicy
    snapshot: MissedRunSnapshot | None = None
    evidence_refs: list[str] = field(default_factory=list)
    source_temporal_receipt_id: str = ""
    source_scheduler_receipt_id: str = ""
    source_retry_window_receipt_id: str = ""
    source_lease_window_receipt_id: str = ""
    source_idempotency_window_receipt_id: str = ""
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
class TemporalMissedRunReceipt:
    """Proof artifact for a missed scheduled command decision."""

    receipt_id: str
    request_id: str
    tenant_id: str
    actor_id: str
    command_id: str
    action_type: str
    risk_level: str
    policy_id: str
    scope_id: str
    schedule_id: str
    status: MissedRunStatus
    missed_run_state: MissedRunState
    runtime_now_utc: str
    missed_run_required: bool
    execute_at: str
    observed_at: str
    expires_at: str
    last_attempt_at: str
    lateness_seconds: int
    grace_seconds: int
    max_lateness_seconds: int
    attempt_count: int
    max_attempts: int
    recurring: bool
    recurrence_rule: str
    already_dispatched: bool
    terminal_receipt_id: str
    scheduler_receipt_id: str
    missed_reasons: list[str]
    blocked_reasons: list[str]
    recovery_actions: list[str]
    required_controls: list[str]
    evidence_refs: list[str]
    snapshot_evidence_refs: list[str]
    source_temporal_receipt_id: str
    source_scheduler_receipt_id: str
    source_retry_window_receipt_id: str
    source_lease_window_receipt_id: str
    source_idempotency_window_receipt_id: str
    source_reapproval_receipt_id: str
    receipt_schema_ref: str
    terminal_closure_required: bool
    receipt_hash: str
    metadata: dict[str, Any]


def evaluate_temporal_missed_run(
    request: MissedRunRequest,
    *,
    runtime_now_utc: datetime,
) -> TemporalMissedRunReceipt:
    """Classify a scheduled command's missed-run state.

    Input contract: request contains tenant/action scope, policy, optional
    scheduler snapshot, and upstream receipt references.
    Output contract: returns a receipt with status, reasons, controls, and hash.
    Error contract: malformed dataclass fields raise ValueError; semantic
    violations are represented as status="blocked" with blocked_reasons.
    """

    now = _to_utc(runtime_now_utc, "runtime_now_utc")
    missed_required = _missed_run_required(request)
    required_controls = _required_controls(request, missed_required)
    blocked_reasons: list[str] = []
    missed_reasons: list[str] = []
    recovery_actions: list[str] = []

    if request.policy.tenant_id != request.tenant_id:
        blocked_reasons.append("policy_tenant_mismatch")

    if not missed_required and blocked_reasons:
        return _build_receipt(
            request=request,
            now=now,
            status="blocked",
            missed_run_state="wrong_scope",
            missed_run_required=True,
            snapshot=None,
            execute_at_dt=None,
            observed_at_dt=None,
            expires_at_dt=None,
            last_attempt_at_dt=None,
            lateness_seconds=0,
            blocked_reasons=blocked_reasons,
            missed_reasons=[],
            recovery_actions=[],
            required_controls=required_controls,
        )

    if not missed_required:
        return _build_receipt(
            request=request,
            now=now,
            status="not_required",
            missed_run_state="not_required",
            missed_run_required=False,
            snapshot=None,
            execute_at_dt=None,
            observed_at_dt=None,
            expires_at_dt=None,
            last_attempt_at_dt=None,
            lateness_seconds=0,
            blocked_reasons=blocked_reasons,
            missed_reasons=[],
            recovery_actions=[],
            required_controls=required_controls,
        )

    snapshot = request.snapshot
    if snapshot is None:
        blocked_reasons.append("missed_run_snapshot_required")
        return _build_receipt(
            request=request,
            now=now,
            status="blocked",
            missed_run_state="invalid",
            missed_run_required=True,
            snapshot=None,
            execute_at_dt=None,
            observed_at_dt=None,
            expires_at_dt=None,
            last_attempt_at_dt=None,
            lateness_seconds=0,
            blocked_reasons=blocked_reasons,
            missed_reasons=[],
            recovery_actions=[],
            required_controls=required_controls,
        )

    execute_at_dt = _parse_snapshot_time(snapshot.execute_at, "execute_at", blocked_reasons)
    observed_at_dt = _parse_snapshot_time(snapshot.observed_at, "observed_at", blocked_reasons)
    expires_at_dt = _parse_optional_snapshot_time(snapshot.expires_at, "expires_at", blocked_reasons)
    last_attempt_at_dt = _parse_optional_snapshot_time(snapshot.last_attempt_at, "last_attempt_at", blocked_reasons)

    _apply_scope_rules(request, snapshot, blocked_reasons)
    _apply_source_rules(request, snapshot, missed_required, blocked_reasons)
    _apply_temporal_rules(
        request=request,
        snapshot=snapshot,
        now=now,
        execute_at_dt=execute_at_dt,
        observed_at_dt=observed_at_dt,
        expires_at_dt=expires_at_dt,
        last_attempt_at_dt=last_attempt_at_dt,
        blocked_reasons=blocked_reasons,
    )

    lateness_seconds = _lateness_seconds(now, execute_at_dt)
    _apply_miss_classification_rules(
        request=request,
        snapshot=snapshot,
        now=now,
        execute_at_dt=execute_at_dt,
        expires_at_dt=expires_at_dt,
        lateness_seconds=lateness_seconds,
        missed_reasons=missed_reasons,
        recovery_actions=recovery_actions,
    )

    status, state = _decide_status_and_state(
        request=request,
        snapshot=snapshot,
        lateness_seconds=lateness_seconds,
        blocked_reasons=blocked_reasons,
        missed_reasons=missed_reasons,
        recovery_actions=recovery_actions,
    )

    return _build_receipt(
        request=request,
        now=now,
        status=status,
        missed_run_state=state,
        missed_run_required=True,
        snapshot=snapshot,
        execute_at_dt=execute_at_dt,
        observed_at_dt=observed_at_dt,
        expires_at_dt=expires_at_dt,
        last_attempt_at_dt=last_attempt_at_dt,
        lateness_seconds=lateness_seconds,
        blocked_reasons=blocked_reasons,
        missed_reasons=missed_reasons,
        recovery_actions=recovery_actions,
        required_controls=required_controls,
    )


def receipt_to_dict(receipt: TemporalMissedRunReceipt) -> dict[str, Any]:
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
        "scope_id": receipt.scope_id,
        "schedule_id": receipt.schedule_id,
        "status": receipt.status,
        "missed_run_state": receipt.missed_run_state,
        "runtime_now_utc": receipt.runtime_now_utc,
        "missed_run_required": receipt.missed_run_required,
        "execute_at": receipt.execute_at,
        "observed_at": receipt.observed_at,
        "expires_at": receipt.expires_at,
        "last_attempt_at": receipt.last_attempt_at,
        "lateness_seconds": receipt.lateness_seconds,
        "grace_seconds": receipt.grace_seconds,
        "max_lateness_seconds": receipt.max_lateness_seconds,
        "attempt_count": receipt.attempt_count,
        "max_attempts": receipt.max_attempts,
        "recurring": receipt.recurring,
        "recurrence_rule": receipt.recurrence_rule,
        "already_dispatched": receipt.already_dispatched,
        "terminal_receipt_id": receipt.terminal_receipt_id,
        "scheduler_receipt_id": receipt.scheduler_receipt_id,
        "missed_reasons": receipt.missed_reasons,
        "blocked_reasons": receipt.blocked_reasons,
        "recovery_actions": receipt.recovery_actions,
        "required_controls": receipt.required_controls,
        "evidence_refs": receipt.evidence_refs,
        "snapshot_evidence_refs": receipt.snapshot_evidence_refs,
        "source_temporal_receipt_id": receipt.source_temporal_receipt_id,
        "source_scheduler_receipt_id": receipt.source_scheduler_receipt_id,
        "source_retry_window_receipt_id": receipt.source_retry_window_receipt_id,
        "source_lease_window_receipt_id": receipt.source_lease_window_receipt_id,
        "source_idempotency_window_receipt_id": receipt.source_idempotency_window_receipt_id,
        "source_reapproval_receipt_id": receipt.source_reapproval_receipt_id,
        "receipt_schema_ref": receipt.receipt_schema_ref,
        "terminal_closure_required": receipt.terminal_closure_required,
        "receipt_hash": receipt.receipt_hash,
        "metadata": receipt.metadata,
    }


def _missed_run_required(request: MissedRunRequest) -> bool:
    if request.risk_level in HIGH_RISK_LEVELS and request.policy.high_risk_requires_missed_run_receipt:
        return True
    return request.policy.requires_missed_run_receipt


def _required_controls(request: MissedRunRequest, missed_required: bool) -> list[str]:
    if not missed_required:
        return []
    controls = list(BASE_REQUIRED_CONTROLS)
    if request.risk_level in HIGH_RISK_LEVELS:
        controls.extend(HIGH_RISK_REQUIRED_CONTROLS)
    return controls


def _apply_scope_rules(
    request: MissedRunRequest,
    snapshot: MissedRunSnapshot,
    blocked_reasons: list[str],
) -> None:
    if snapshot.tenant_id != request.tenant_id:
        blocked_reasons.append("snapshot_tenant_mismatch")
    if snapshot.command_id != request.command_id:
        blocked_reasons.append("snapshot_command_mismatch")
    if snapshot.action_type != request.action_type:
        blocked_reasons.append("snapshot_action_type_mismatch")
    if snapshot.recurring and not snapshot.recurrence_rule.strip():
        blocked_reasons.append("recurrence_rule_required")
    if snapshot.already_dispatched and not snapshot.terminal_receipt_id.strip():
        blocked_reasons.append("terminal_receipt_required_for_dispatched_run")


def _apply_source_rules(
    request: MissedRunRequest,
    snapshot: MissedRunSnapshot,
    missed_required: bool,
    blocked_reasons: list[str],
) -> None:
    if not missed_required:
        return
    if not request.evidence_refs:
        blocked_reasons.append("evidence_refs_required")
    if not snapshot.evidence_refs:
        blocked_reasons.append("snapshot_evidence_refs_required")
    if not request.source_scheduler_receipt_id.strip():
        blocked_reasons.append("source_scheduler_receipt_required")
    if snapshot.scheduler_receipt_id and request.source_scheduler_receipt_id != snapshot.scheduler_receipt_id:
        blocked_reasons.append("scheduler_receipt_mismatch")
    if request.risk_level in HIGH_RISK_LEVELS:
        if not request.source_temporal_receipt_id.strip():
            blocked_reasons.append("source_temporal_receipt_required_for_high_risk")
        if not request.source_reapproval_receipt_id.strip():
            blocked_reasons.append("source_reapproval_receipt_required_for_high_risk")


def _apply_temporal_rules(
    *,
    request: MissedRunRequest,
    snapshot: MissedRunSnapshot,
    now: datetime,
    execute_at_dt: datetime | None,
    observed_at_dt: datetime | None,
    expires_at_dt: datetime | None,
    last_attempt_at_dt: datetime | None,
    blocked_reasons: list[str],
) -> None:
    del request, snapshot
    if execute_at_dt and execute_at_dt > now:
        blocked_reasons.append("execute_at_in_future_not_missed")
    if observed_at_dt and observed_at_dt > now:
        blocked_reasons.append("observed_at_in_future")
    if last_attempt_at_dt and last_attempt_at_dt > now:
        blocked_reasons.append("last_attempt_at_in_future")
    if execute_at_dt and observed_at_dt and observed_at_dt < execute_at_dt:
        blocked_reasons.append("observed_before_execute_at")
    if execute_at_dt and expires_at_dt and expires_at_dt < execute_at_dt:
        blocked_reasons.append("expires_at_before_execute_at")


def _apply_miss_classification_rules(
    *,
    request: MissedRunRequest,
    snapshot: MissedRunSnapshot,
    now: datetime,
    execute_at_dt: datetime | None,
    expires_at_dt: datetime | None,
    lateness_seconds: int,
    missed_reasons: list[str],
    recovery_actions: list[str],
) -> None:
    if execute_at_dt is None:
        return

    if snapshot.already_dispatched:
        return

    if lateness_seconds <= request.policy.grace_seconds:
        return

    if expires_at_dt and now > expires_at_dt:
        missed_reasons.append("command_expired_before_execution")
    if lateness_seconds > request.policy.max_lateness_seconds:
        missed_reasons.append("lateness_exceeds_policy")
    if snapshot.attempt_count >= snapshot.max_attempts:
        missed_reasons.append("max_attempts_exhausted")

    if not missed_reasons and request.policy.allow_recovery_after_miss:
        missed_reasons.append("missed_run_recovery_due")
        recovery_actions.append("queue_recovery_review")
        if snapshot.recurring:
            recovery_actions.append("schedule_next_occurrence_review")
        if snapshot.attempt_count < snapshot.max_attempts:
            recovery_actions.append("retry_if_governance_allows")

    if not missed_reasons:
        missed_reasons.append("missed_run_detected")


def _decide_status_and_state(
    *,
    request: MissedRunRequest,
    snapshot: MissedRunSnapshot,
    lateness_seconds: int,
    blocked_reasons: list[str],
    missed_reasons: list[str],
    recovery_actions: list[str],
) -> tuple[MissedRunStatus, MissedRunState]:
    if blocked_reasons:
        if any(reason.endswith("_mismatch") for reason in blocked_reasons):
            return "blocked", "wrong_scope"
        return "blocked", "invalid"
    if snapshot.already_dispatched:
        return "duplicate_dispatched", "already_dispatched"
    if lateness_seconds <= request.policy.grace_seconds:
        return "late_within_grace", "late_allowed"
    if recovery_actions:
        return "recovery_due", "recovery_allowed"
    if missed_reasons:
        return "missed", "missed_expired"
    return "blocked", "invalid"


def _build_receipt(
    *,
    request: MissedRunRequest,
    now: datetime,
    status: MissedRunStatus,
    missed_run_state: MissedRunState,
    missed_run_required: bool,
    snapshot: MissedRunSnapshot | None,
    execute_at_dt: datetime | None,
    observed_at_dt: datetime | None,
    expires_at_dt: datetime | None,
    last_attempt_at_dt: datetime | None,
    lateness_seconds: int,
    blocked_reasons: list[str],
    missed_reasons: list[str],
    recovery_actions: list[str],
    required_controls: list[str],
) -> TemporalMissedRunReceipt:
    normalized_now = _format_dt(now)
    receipt_seed = {
        "request_id": request.request_id,
        "tenant_id": request.tenant_id,
        "command_id": request.command_id,
        "status": status,
        "state": missed_run_state,
        "runtime_now_utc": normalized_now,
        "execute_at": _format_optional_dt(execute_at_dt),
        "blocked_reasons": sorted(blocked_reasons),
        "missed_reasons": sorted(missed_reasons),
    }
    receipt_hash = _stable_hash(receipt_seed)
    receipt_id = f"temporal-missed-run-receipt-{receipt_hash[:16]}"
    metadata = {
        **request.metadata,
        "runtime_owns_time_truth": True,
        "receipt_is_not_terminal_closure": True,
        "missed_run_checked": missed_run_required,
        "dispatch_allowed": status == "late_within_grace",
        "recovery_required": status == "recovery_due",
        "terminal_closure_required": True,
        "high_risk_source_receipts_checked": request.risk_level in HIGH_RISK_LEVELS,
    }

    return TemporalMissedRunReceipt(
        receipt_id=receipt_id,
        request_id=request.request_id,
        tenant_id=request.tenant_id,
        actor_id=request.actor_id,
        command_id=request.command_id,
        action_type=request.action_type,
        risk_level=request.risk_level,
        policy_id=request.policy.policy_id,
        scope_id=request.policy.scope_id,
        schedule_id=snapshot.schedule_id if snapshot else "",
        status=status,
        missed_run_state=missed_run_state,
        runtime_now_utc=normalized_now,
        missed_run_required=missed_run_required,
        execute_at=_format_optional_dt(execute_at_dt),
        observed_at=_format_optional_dt(observed_at_dt),
        expires_at=_format_optional_dt(expires_at_dt),
        last_attempt_at=_format_optional_dt(last_attempt_at_dt),
        lateness_seconds=lateness_seconds,
        grace_seconds=request.policy.grace_seconds,
        max_lateness_seconds=request.policy.max_lateness_seconds,
        attempt_count=snapshot.attempt_count if snapshot else 0,
        max_attempts=snapshot.max_attempts if snapshot else 0,
        recurring=snapshot.recurring if snapshot else False,
        recurrence_rule=snapshot.recurrence_rule if snapshot else "",
        already_dispatched=snapshot.already_dispatched if snapshot else False,
        terminal_receipt_id=snapshot.terminal_receipt_id if snapshot else "",
        scheduler_receipt_id=snapshot.scheduler_receipt_id if snapshot else "",
        missed_reasons=sorted(set(missed_reasons)),
        blocked_reasons=sorted(set(blocked_reasons)),
        recovery_actions=sorted(set(recovery_actions)),
        required_controls=required_controls,
        evidence_refs=sorted(set(request.evidence_refs)),
        snapshot_evidence_refs=sorted(set(snapshot.evidence_refs)) if snapshot else [],
        source_temporal_receipt_id=request.source_temporal_receipt_id,
        source_scheduler_receipt_id=request.source_scheduler_receipt_id,
        source_retry_window_receipt_id=request.source_retry_window_receipt_id,
        source_lease_window_receipt_id=request.source_lease_window_receipt_id,
        source_idempotency_window_receipt_id=request.source_idempotency_window_receipt_id,
        source_reapproval_receipt_id=request.source_reapproval_receipt_id,
        receipt_schema_ref=TEMPORAL_MISSED_RUN_RECEIPT_SCHEMA_REF,
        terminal_closure_required=True,
        receipt_hash=receipt_hash,
        metadata=metadata,
    )


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
    try:
        return _to_utc(datetime.fromisoformat(value.replace("Z", "+00:00")), field_name)
    except ValueError:
        blocked_reasons.append(f"{field_name}_invalid_rfc3339")
        return None


def _to_utc(value: datetime, field_name: str) -> datetime:
    if value.tzinfo is None:
        raise ValueError(f"{field_name} must be timezone-aware")
    return value.astimezone(timezone.utc)


def _lateness_seconds(now: datetime, execute_at_dt: datetime | None) -> int:
    if execute_at_dt is None:
        return 0
    return max(0, int((now - execute_at_dt).total_seconds()))


def _format_optional_dt(value: datetime | None) -> str:
    if value is None:
        return ""
    return _format_dt(value)


def _format_dt(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _stable_hash(value: dict[str, Any]) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
