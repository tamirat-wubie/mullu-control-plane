"""Gateway temporal scheduler.

Purpose: govern scheduled command wakeups through due checks, missed-run
    receipts, retry windows, idempotency, approval rechecks, and leases.
Governance scope: future execution admission, recurrence declarations,
    execution leases, retry timing, duplicate prevention, and non-terminal
    scheduler receipts.
Dependencies: dataclasses, datetime, command-spine canonical hashing, and the
    Temporal Kernel clock surface.
Invariants:
  - Scheduled commands without execute_at fail closed.
  - Recurring commands must declare recurrence_rule.
  - Commands cannot execute after expires_at.
  - Retries require retry_after and max_attempts.
  - Execution requires idempotency_key.
  - High-risk scheduled commands require approval and temporal recheck proof.
  - A command must acquire a lease before dispatch.
  - Scheduler receipts are not terminal closure certificates.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from datetime import datetime, timedelta, timezone
from typing import Any

from gateway.command_spine import canonical_hash
from gateway.temporal_kernel import TrustedClock


TEMPORAL_SCHEDULER_RECEIPT_SCHEMA_REF = "urn:mullusi:schema:temporal-scheduler-receipt:1"
SCHEDULER_STATUSES = ("leased", "deferred", "blocked", "missed", "retry_wait")
RISK_LEVELS = ("low", "medium", "high", "critical")
BASE_SCHEDULER_CONTROLS = (
    "runtime_clock",
    "schedule_due",
    "idempotency",
    "lease",
    "temporal_receipt",
    "terminal_closure",
)
HIGH_RISK_CONTROLS = (
    "approval_recheck",
    "temporal_policy_recheck",
)


@dataclass(frozen=True, slots=True)
class ScheduledCommand:
    """One scheduled command awaiting governed wakeup."""

    schedule_id: str
    command_id: str
    tenant_id: str
    actor_id: str
    action_type: str
    risk_level: str
    requested_at: str
    execute_at: str
    idempotency_key: str
    evidence_refs: list[str] = field(default_factory=list)
    recurring: bool = False
    recurrence_rule: str = ""
    expires_at: str = ""
    approval_ref: str = ""
    temporal_receipt_ref: str = ""
    retry_after: str = ""
    max_attempts: int = 1
    attempt_count: int = 0
    last_attempt_at: str = ""
    lease_id: str = ""
    lease_owner: str = ""
    lease_expires_at: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in (
            "schedule_id",
            "command_id",
            "tenant_id",
            "actor_id",
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
        if self.max_attempts <= 0:
            raise ValueError("max_attempts_positive_required")
        if self.attempt_count < 0:
            raise ValueError("attempt_count_nonnegative_required")
        object.__setattr__(self, "execute_at", str(self.execute_at).strip())
        object.__setattr__(self, "idempotency_key", str(self.idempotency_key).strip())
        object.__setattr__(self, "evidence_refs", _normalize_list(self.evidence_refs))
        object.__setattr__(self, "recurrence_rule", str(self.recurrence_rule).strip())
        object.__setattr__(self, "expires_at", str(self.expires_at).strip())
        object.__setattr__(self, "approval_ref", str(self.approval_ref).strip())
        object.__setattr__(self, "temporal_receipt_ref", str(self.temporal_receipt_ref).strip())
        object.__setattr__(self, "retry_after", str(self.retry_after).strip())
        object.__setattr__(self, "last_attempt_at", str(self.last_attempt_at).strip())
        object.__setattr__(self, "lease_id", str(self.lease_id).strip())
        object.__setattr__(self, "lease_owner", str(self.lease_owner).strip())
        object.__setattr__(self, "lease_expires_at", str(self.lease_expires_at).strip())
        object.__setattr__(self, "metadata", dict(self.metadata))


@dataclass(frozen=True, slots=True)
class TemporalSchedulerReceipt:
    """Schema-backed non-terminal scheduler wakeup receipt."""

    receipt_id: str
    schedule_id: str
    command_id: str
    tenant_id: str
    actor_id: str
    action_type: str
    risk_level: str
    status: str
    blocked_reasons: list[str]
    deferral_reasons: list[str]
    missed_reasons: list[str]
    retry_reasons: list[str]
    required_controls: list[str]
    runtime_now_utc: str
    requested_at: str
    execute_at: str
    expires_at: str
    recurring: bool
    recurrence_rule: str
    retry_after: str
    max_attempts: int
    attempt_count: int
    last_attempt_at: str
    idempotency_key: str
    approval_ref: str
    temporal_receipt_ref: str
    lease_id: str
    lease_owner: str
    lease_expires_at: str
    lease_hash: str
    lease_acquired: bool
    evidence_refs: list[str]
    receipt_schema_ref: str
    terminal_closure_required: bool
    receipt_hash: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.status not in SCHEDULER_STATUSES:
            raise ValueError("scheduler_status_invalid")
        object.__setattr__(self, "blocked_reasons", _normalize_list(self.blocked_reasons))
        object.__setattr__(self, "deferral_reasons", _normalize_list(self.deferral_reasons))
        object.__setattr__(self, "missed_reasons", _normalize_list(self.missed_reasons))
        object.__setattr__(self, "retry_reasons", _normalize_list(self.retry_reasons))
        object.__setattr__(self, "required_controls", _normalize_list(self.required_controls))
        object.__setattr__(self, "evidence_refs", _normalize_list(self.evidence_refs))
        object.__setattr__(self, "metadata", dict(self.metadata))


class TemporalScheduler:
    """Deterministic scheduler admission and lease issuer."""

    def __init__(
        self,
        *,
        clock: TrustedClock | None = None,
        lease_ttl_seconds: int = 300,
        lease_owner: str = "temporal-scheduler",
    ) -> None:
        if lease_ttl_seconds <= 0:
            raise ValueError("lease_ttl_seconds_positive_required")
        self._clock = clock or TrustedClock()
        self._lease_ttl_seconds = lease_ttl_seconds
        self._lease_owner = lease_owner

    def evaluate(self, command: ScheduledCommand) -> TemporalSchedulerReceipt:
        """Return scheduler wakeup decision and lease evidence for one command."""
        now = _parse_required_instant(self._clock.now_utc())
        blocked_reasons: list[str] = []
        deferral_reasons: list[str] = []
        missed_reasons: list[str] = []
        retry_reasons: list[str] = []
        required_controls = [*BASE_SCHEDULER_CONTROLS]
        parsed = _parse_command_times(command, blocked_reasons)

        _apply_required_command_rules(command, blocked_reasons, required_controls)
        _apply_schedule_rules(parsed, now, deferral_reasons)
        _apply_expiry_rules(parsed, now, missed_reasons)
        _apply_retry_rules(command, parsed, now, blocked_reasons, retry_reasons, required_controls)
        _apply_high_risk_rules(command, blocked_reasons, required_controls)
        _apply_existing_lease_rules(command, parsed, now, blocked_reasons, required_controls)

        status = _status(missed_reasons, blocked_reasons, retry_reasons, deferral_reasons)
        lease_acquired = status == "leased"
        lease_id = ""
        lease_expires_at = ""
        lease_hash = ""
        if lease_acquired:
            lease_expires_at = (now + timedelta(seconds=self._lease_ttl_seconds)).isoformat()
            lease_payload = {
                "schedule_id": command.schedule_id,
                "command_id": command.command_id,
                "tenant_id": command.tenant_id,
                "lease_owner": self._lease_owner,
                "runtime_now_utc": now.isoformat(),
                "lease_expires_at": lease_expires_at,
                "idempotency_key": command.idempotency_key,
            }
            lease_hash = canonical_hash(lease_payload)
            lease_id = f"temporal-lease-{lease_hash[:16]}"

        receipt = TemporalSchedulerReceipt(
            receipt_id="pending",
            schedule_id=command.schedule_id,
            command_id=command.command_id,
            tenant_id=command.tenant_id,
            actor_id=command.actor_id,
            action_type=command.action_type,
            risk_level=command.risk_level,
            status=status,
            blocked_reasons=_unique(blocked_reasons),
            deferral_reasons=_unique(deferral_reasons),
            missed_reasons=_unique(missed_reasons),
            retry_reasons=_unique(retry_reasons),
            required_controls=_unique(required_controls),
            runtime_now_utc=now.isoformat(),
            requested_at=_instant_text(parsed, "requested_at", command.requested_at),
            execute_at=_instant_text(parsed, "execute_at", command.execute_at),
            expires_at=_instant_text(parsed, "expires_at", command.expires_at),
            recurring=command.recurring,
            recurrence_rule=command.recurrence_rule,
            retry_after=_instant_text(parsed, "retry_after", command.retry_after),
            max_attempts=command.max_attempts,
            attempt_count=command.attempt_count,
            last_attempt_at=_instant_text(parsed, "last_attempt_at", command.last_attempt_at),
            idempotency_key=command.idempotency_key,
            approval_ref=command.approval_ref,
            temporal_receipt_ref=command.temporal_receipt_ref,
            lease_id=lease_id or command.lease_id,
            lease_owner=self._lease_owner if lease_acquired else command.lease_owner,
            lease_expires_at=lease_expires_at or _instant_text(
                parsed,
                "lease_expires_at",
                command.lease_expires_at,
            ),
            lease_hash=lease_hash,
            lease_acquired=lease_acquired,
            evidence_refs=command.evidence_refs,
            receipt_schema_ref=TEMPORAL_SCHEDULER_RECEIPT_SCHEMA_REF,
            terminal_closure_required=True,
            metadata={
                "receipt_is_not_terminal_closure": True,
                "dispatch_allowed": lease_acquired,
                "missed_run_receipt": status == "missed",
                "retry_window_checked": command.attempt_count > 0,
                "lease_required_before_dispatch": True,
                "idempotency_required": True,
            },
        )
        receipt_hash = canonical_hash(asdict(receipt))
        return replace(
            receipt,
            receipt_id=f"scheduler-receipt-{receipt_hash[:16]}",
            receipt_hash=receipt_hash,
        )


def _parse_command_times(command: ScheduledCommand, blocked_reasons: list[str]) -> dict[str, datetime]:
    parsed: dict[str, datetime] = {}
    for field_name in (
        "requested_at",
        "execute_at",
        "expires_at",
        "retry_after",
        "last_attempt_at",
        "lease_expires_at",
    ):
        raw_value = str(getattr(command, field_name)).strip()
        if not raw_value:
            continue
        try:
            parsed[field_name] = _parse_required_instant(raw_value)
        except ValueError:
            blocked_reasons.append(f"{field_name}_invalid")
    return parsed


def _apply_required_command_rules(
    command: ScheduledCommand,
    blocked_reasons: list[str],
    required_controls: list[str],
) -> None:
    if not command.execute_at:
        blocked_reasons.append("execute_at_required")
    if not command.idempotency_key:
        blocked_reasons.append("idempotency_key_required")
    if not command.evidence_refs:
        blocked_reasons.append("evidence_refs_required")
    if command.recurring:
        required_controls.append("recurrence_rule")
    if command.recurring and not command.recurrence_rule:
        blocked_reasons.append("recurrence_rule_required")


def _apply_schedule_rules(
    parsed: dict[str, datetime],
    now: datetime,
    deferral_reasons: list[str],
) -> None:
    execute_at = parsed.get("execute_at")
    if execute_at and now < execute_at:
        deferral_reasons.append("scheduled_for_future")


def _apply_expiry_rules(
    parsed: dict[str, datetime],
    now: datetime,
    missed_reasons: list[str],
) -> None:
    expires_at = parsed.get("expires_at")
    if expires_at and now > expires_at:
        missed_reasons.append("command_expired_before_execution")


def _apply_retry_rules(
    command: ScheduledCommand,
    parsed: dict[str, datetime],
    now: datetime,
    blocked_reasons: list[str],
    retry_reasons: list[str],
    required_controls: list[str],
) -> None:
    if command.attempt_count == 0:
        return
    required_controls.append("retry_window")
    if command.attempt_count >= command.max_attempts:
        blocked_reasons.append("max_attempts_exhausted")
    retry_after = parsed.get("retry_after")
    if not command.retry_after:
        blocked_reasons.append("retry_after_required")
        return
    if retry_after and now < retry_after:
        retry_reasons.append("retry_window_not_due")


def _apply_high_risk_rules(
    command: ScheduledCommand,
    blocked_reasons: list[str],
    required_controls: list[str],
) -> None:
    if command.risk_level not in {"high", "critical"}:
        return
    required_controls.extend(HIGH_RISK_CONTROLS)
    if not command.approval_ref:
        blocked_reasons.append("approval_recheck_required")
    if not command.temporal_receipt_ref:
        blocked_reasons.append("temporal_policy_recheck_required")


def _apply_existing_lease_rules(
    command: ScheduledCommand,
    parsed: dict[str, datetime],
    now: datetime,
    blocked_reasons: list[str],
    required_controls: list[str],
) -> None:
    if not command.lease_id:
        return
    required_controls.append("duplicate_execution_prevention")
    lease_expires_at = parsed.get("lease_expires_at")
    if lease_expires_at and now < lease_expires_at:
        blocked_reasons.append("active_lease_exists")


def _status(
    missed_reasons: list[str],
    blocked_reasons: list[str],
    retry_reasons: list[str],
    deferral_reasons: list[str],
) -> str:
    if missed_reasons:
        return "missed"
    if blocked_reasons:
        return "blocked"
    if retry_reasons:
        return "retry_wait"
    if deferral_reasons:
        return "deferred"
    return "leased"


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
