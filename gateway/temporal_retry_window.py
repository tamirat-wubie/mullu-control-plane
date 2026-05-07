"""Gateway temporal retry window evaluator.

Purpose: prove retry admission before a governed worker repeats an action.
Governance scope: runtime-owned retry timing, retry-after floors, cooldowns,
    max-attempt limits, expiry, tenant and command scope, evidence refs,
    high-risk source receipt binding, and non-terminal receipts.
Dependencies: dataclasses, datetime, command-spine canonical hashing, and the
    Temporal Kernel trusted clock.
Invariants:
  - Runtime clock owns retry timing truth.
  - Retry-after and cooldown windows must be checked before dispatch.
  - Exhausted or expired retry windows fail closed.
  - Tenant and command scope mismatches fail closed.
  - High-risk retries bind temporal and reapproval receipts.
  - Temporal retry window receipts are not terminal closure certificates.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from datetime import datetime, timedelta, timezone
from typing import Any

from gateway.command_spine import canonical_hash
from gateway.temporal_kernel import TrustedClock


TEMPORAL_RETRY_WINDOW_RECEIPT_SCHEMA_REF = "urn:mullusi:schema:temporal-retry-window-receipt:1"
RISK_LEVELS = ("low", "medium", "high", "critical")
RETRY_STATUSES = ("retry_allowed", "retry_deferred", "retry_exhausted", "retry_expired", "blocked", "not_required")
RETRY_STATES = (
    "eligible",
    "cooldown",
    "max_attempts_reached",
    "expired",
    "terminal_failure",
    "wrong_scope",
    "invalid",
    "not_required",
)
HIGH_RISK_LEVELS = frozenset({"high", "critical"})
BASE_RETRY_WINDOW_CONTROLS = (
    "runtime_clock",
    "retry_window",
    "retry_after_floor",
    "cooldown_window",
    "max_attempts",
    "tenant_scope",
    "command_scope",
    "evidence_reference",
    "temporal_retry_window_receipt",
    "terminal_closure",
)


@dataclass(frozen=True, slots=True)
class RetryWindowPolicy:
    """Tenant policy defining one governed retry window."""

    policy_id: str
    tenant_id: str
    scope_id: str
    retryable_action_types: list[str]
    max_attempts: int
    retry_after_seconds: int
    cooldown_seconds: int
    max_retry_window_seconds: int
    requires_retry_window: bool = True
    high_risk_requires_retry_window: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in ("policy_id", "tenant_id", "scope_id"):
            value = str(getattr(self, field_name)).strip()
            if not value:
                raise ValueError(f"{field_name}_required")
            object.__setattr__(self, field_name, value)
        if self.max_attempts < 1:
            raise ValueError("max_attempts_positive_required")
        if self.retry_after_seconds < 0 or self.cooldown_seconds < 0:
            raise ValueError("retry_window_seconds_nonnegative_required")
        if self.max_retry_window_seconds < 1:
            raise ValueError("max_retry_window_seconds_positive_required")
        retryable_action_types = _normalize_list(self.retryable_action_types)
        if not retryable_action_types:
            raise ValueError("retryable_action_types_required")
        object.__setattr__(self, "retryable_action_types", retryable_action_types)
        object.__setattr__(self, "metadata", dict(self.metadata))


@dataclass(frozen=True, slots=True)
class RetryAttemptSnapshot:
    """Observed retry state for one command."""

    attempt_id: str
    tenant_id: str
    command_id: str
    first_attempt_at: str
    last_attempt_at: str
    next_retry_at: str
    expires_at: str
    attempt_number: int
    failure_count: int
    terminal_failure: bool = False
    previous_attempt_id: str = ""
    last_failure_reason: str = ""
    evidence_refs: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in (
            "attempt_id",
            "tenant_id",
            "command_id",
            "first_attempt_at",
            "last_attempt_at",
            "next_retry_at",
            "expires_at",
        ):
            value = str(getattr(self, field_name)).strip()
            if not value:
                raise ValueError(f"{field_name}_required")
            object.__setattr__(self, field_name, value)
        if self.attempt_number < 0 or self.failure_count < 0:
            raise ValueError("retry_attempt_counters_nonnegative_required")
        object.__setattr__(self, "previous_attempt_id", str(self.previous_attempt_id).strip())
        object.__setattr__(self, "last_failure_reason", str(self.last_failure_reason).strip())
        object.__setattr__(self, "evidence_refs", _normalize_list(self.evidence_refs))
        object.__setattr__(self, "metadata", dict(self.metadata))


@dataclass(frozen=True, slots=True)
class RetryWindowRequest:
    """One request to prove retry admission before repeated dispatch."""

    request_id: str
    tenant_id: str
    actor_id: str
    command_id: str
    action_type: str
    risk_level: str
    policy: RetryWindowPolicy
    evidence_refs: list[str]
    snapshot: RetryAttemptSnapshot | None = None
    source_temporal_receipt_id: str = ""
    source_dispatch_window_receipt_id: str = ""
    source_rate_limit_window_receipt_id: str = ""
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
        object.__setattr__(self, "evidence_refs", _normalize_list(self.evidence_refs))
        object.__setattr__(self, "source_temporal_receipt_id", str(self.source_temporal_receipt_id).strip())
        object.__setattr__(
            self,
            "source_dispatch_window_receipt_id",
            str(self.source_dispatch_window_receipt_id).strip(),
        )
        object.__setattr__(
            self,
            "source_rate_limit_window_receipt_id",
            str(self.source_rate_limit_window_receipt_id).strip(),
        )
        object.__setattr__(self, "source_reapproval_receipt_id", str(self.source_reapproval_receipt_id).strip())
        object.__setattr__(self, "metadata", dict(self.metadata))


@dataclass(frozen=True, slots=True)
class TemporalRetryWindowReceipt:
    """Schema-backed non-terminal receipt for retry window checks."""

    receipt_id: str
    request_id: str
    tenant_id: str
    actor_id: str
    command_id: str
    action_type: str
    risk_level: str
    policy_id: str
    scope_id: str
    attempt_id: str
    previous_attempt_id: str
    status: str
    retry_state: str
    runtime_now_utc: str
    retry_window_required: bool
    first_attempt_at: str
    last_attempt_at: str
    next_retry_at: str
    retry_after_due_at: str
    expires_at: str
    retry_after_seconds: int
    cooldown_remaining_seconds: int
    attempt_number: int
    failure_count: int
    max_attempts: int
    attempts_remaining: int
    retry_window_seconds: int
    terminal_failure: bool
    last_failure_reason: str
    blocked_reasons: list[str]
    deferral_reasons: list[str]
    required_controls: list[str]
    evidence_refs: list[str]
    attempt_evidence_refs: list[str]
    source_temporal_receipt_id: str
    source_dispatch_window_receipt_id: str
    source_rate_limit_window_receipt_id: str
    source_reapproval_receipt_id: str
    receipt_schema_ref: str
    terminal_closure_required: bool
    receipt_hash: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.status not in RETRY_STATUSES:
            raise ValueError("temporal_retry_window_status_invalid")
        if self.retry_state not in RETRY_STATES:
            raise ValueError("temporal_retry_window_state_invalid")
        for field_name in (
            "retry_after_seconds",
            "cooldown_remaining_seconds",
            "attempt_number",
            "failure_count",
            "max_attempts",
            "attempts_remaining",
            "retry_window_seconds",
        ):
            if int(getattr(self, field_name)) < 0:
                raise ValueError("temporal_retry_window_counter_nonnegative_required")
        object.__setattr__(self, "blocked_reasons", _normalize_list(self.blocked_reasons))
        object.__setattr__(self, "deferral_reasons", _normalize_list(self.deferral_reasons))
        object.__setattr__(self, "required_controls", _normalize_list(self.required_controls))
        object.__setattr__(self, "evidence_refs", _normalize_list(self.evidence_refs))
        object.__setattr__(self, "attempt_evidence_refs", _normalize_list(self.attempt_evidence_refs))
        object.__setattr__(self, "metadata", dict(self.metadata))


class TemporalRetryWindow:
    """Deterministic runtime retry-window evaluator."""

    def __init__(self, clock: TrustedClock | None = None) -> None:
        self._clock = clock or TrustedClock()

    def evaluate(self, request: RetryWindowRequest) -> TemporalRetryWindowReceipt:
        """Return whether this retry is inside the governed retry window."""
        now = _parse_required_instant(self._clock.now_utc())
        retry_required = _retry_required(request)
        snapshot = request.snapshot if retry_required else None
        blocked_reasons: list[str] = []
        deferral_reasons: list[str] = []
        required_controls = [*BASE_RETRY_WINDOW_CONTROLS]

        if retry_required:
            required_controls.append("retry_policy_check")
        if request.risk_level in HIGH_RISK_LEVELS:
            required_controls.append("high_risk_retry_binding")
        if request.source_temporal_receipt_id:
            required_controls.append("source_temporal_receipt")
        if request.source_dispatch_window_receipt_id:
            required_controls.append("source_dispatch_window_receipt")
        if request.source_rate_limit_window_receipt_id:
            required_controls.append("source_rate_limit_window_receipt")
        if request.source_reapproval_receipt_id:
            required_controls.append("source_reapproval_receipt")

        blocked_reasons.extend(_policy_violations(request, retry_required))
        first_attempt_at: datetime | None = None
        last_attempt_at: datetime | None = None
        next_retry_at: datetime | None = None
        expires_at: datetime | None = None
        retry_after_due_at: datetime | None = None
        if snapshot is not None:
            first_attempt_at = _parse_optional_instant(
                snapshot.first_attempt_at,
                blocked_reasons,
                "first_attempt_at_invalid",
            )
            last_attempt_at = _parse_optional_instant(
                snapshot.last_attempt_at,
                blocked_reasons,
                "last_attempt_at_invalid",
            )
            next_retry_at = _parse_optional_instant(snapshot.next_retry_at, blocked_reasons, "next_retry_at_invalid")
            expires_at = _parse_optional_instant(snapshot.expires_at, blocked_reasons, "expires_at_invalid")
            retry_after_due_at = _retry_after_due_at(
                last_attempt_at=last_attempt_at,
                next_retry_at=next_retry_at,
                retry_after_seconds=request.policy.retry_after_seconds,
                cooldown_seconds=request.policy.cooldown_seconds,
            )
            _apply_snapshot_rules(
                request=request,
                now=now,
                first_attempt_at=first_attempt_at,
                last_attempt_at=last_attempt_at,
                next_retry_at=next_retry_at,
                retry_after_due_at=retry_after_due_at,
                expires_at=expires_at,
                blocked_reasons=blocked_reasons,
                deferral_reasons=deferral_reasons,
            )

        attempt_number = snapshot.attempt_number if snapshot else 0
        failure_count = snapshot.failure_count if snapshot else 0
        attempts_remaining = _attempts_remaining(
            request.policy.max_attempts,
            attempt_number,
            failure_count,
            retry_required,
        )
        status = _status(
            blocked_reasons=blocked_reasons,
            deferral_reasons=deferral_reasons,
            retry_required=retry_required,
            attempts_remaining=attempts_remaining,
            now=now,
            expires_at=expires_at,
        )
        cooldown_remaining_seconds = _cooldown_remaining_seconds(status, now, retry_after_due_at)
        retry_state = _retry_state(
            status=status,
            blocked_reasons=blocked_reasons,
            deferral_reasons=deferral_reasons,
        )
        receipt = TemporalRetryWindowReceipt(
            receipt_id="pending",
            request_id=request.request_id,
            tenant_id=request.tenant_id,
            actor_id=request.actor_id,
            command_id=request.command_id,
            action_type=request.action_type,
            risk_level=request.risk_level,
            policy_id=request.policy.policy_id,
            scope_id=request.policy.scope_id,
            attempt_id=snapshot.attempt_id if snapshot else "",
            previous_attempt_id=snapshot.previous_attempt_id if snapshot else "",
            status=status,
            retry_state=retry_state,
            runtime_now_utc=now.isoformat(),
            retry_window_required=retry_required,
            first_attempt_at=_instant_text(first_attempt_at),
            last_attempt_at=_instant_text(last_attempt_at),
            next_retry_at=_instant_text(next_retry_at),
            retry_after_due_at=_instant_text(retry_after_due_at),
            expires_at=_instant_text(expires_at),
            retry_after_seconds=cooldown_remaining_seconds,
            cooldown_remaining_seconds=cooldown_remaining_seconds,
            attempt_number=attempt_number,
            failure_count=failure_count,
            max_attempts=request.policy.max_attempts if retry_required else 0,
            attempts_remaining=attempts_remaining,
            retry_window_seconds=request.policy.max_retry_window_seconds if retry_required else 0,
            terminal_failure=bool(snapshot.terminal_failure) if snapshot else False,
            last_failure_reason=snapshot.last_failure_reason if snapshot else "",
            blocked_reasons=_unique(blocked_reasons),
            deferral_reasons=_unique(deferral_reasons),
            required_controls=_unique(_required_controls_for_status(required_controls, status)),
            evidence_refs=request.evidence_refs,
            attempt_evidence_refs=snapshot.evidence_refs if snapshot else [],
            source_temporal_receipt_id=request.source_temporal_receipt_id,
            source_dispatch_window_receipt_id=request.source_dispatch_window_receipt_id,
            source_rate_limit_window_receipt_id=request.source_rate_limit_window_receipt_id,
            source_reapproval_receipt_id=request.source_reapproval_receipt_id,
            receipt_schema_ref=TEMPORAL_RETRY_WINDOW_RECEIPT_SCHEMA_REF,
            terminal_closure_required=True,
            metadata={
                "receipt_is_not_terminal_closure": True,
                "runtime_owns_time_truth": True,
                "dispatch_allowed": status in {"retry_allowed", "not_required"},
                "retry_checked": retry_required,
                "retry_after_checked": retry_required and snapshot is not None,
                "cooldown_checked": retry_required and snapshot is not None,
                "attempts_checked": retry_required and snapshot is not None,
                "expiry_checked": retry_required and snapshot is not None,
                "high_risk_source_receipts_checked": _source_receipts_checked(request),
            },
        )
        receipt_hash = canonical_hash(asdict(receipt))
        return replace(
            receipt,
            receipt_id=f"temporal-retry-window-receipt-{receipt_hash[:16]}",
            receipt_hash=receipt_hash,
        )


def _retry_required(request: RetryWindowRequest) -> bool:
    if request.policy.requires_retry_window:
        return True
    return request.risk_level in HIGH_RISK_LEVELS and request.policy.high_risk_requires_retry_window


def _policy_violations(request: RetryWindowRequest, retry_required: bool) -> list[str]:
    violations: list[str] = []
    if request.policy.tenant_id != request.tenant_id:
        violations.append("policy_tenant_mismatch")
    if not retry_required:
        return violations
    if request.action_type not in request.policy.retryable_action_types:
        violations.append("action_type_not_retryable")
    if request.snapshot is None:
        violations.append("retry_snapshot_required")
    if not request.evidence_refs:
        violations.append("evidence_refs_required")
    if request.risk_level in HIGH_RISK_LEVELS and not request.source_temporal_receipt_id:
        violations.append("source_temporal_receipt_required_for_high_risk")
    if request.risk_level in HIGH_RISK_LEVELS and not request.source_reapproval_receipt_id:
        violations.append("source_reapproval_receipt_required_for_high_risk")
    return violations


def _apply_snapshot_rules(
    *,
    request: RetryWindowRequest,
    now: datetime,
    first_attempt_at: datetime | None,
    last_attempt_at: datetime | None,
    next_retry_at: datetime | None,
    retry_after_due_at: datetime | None,
    expires_at: datetime | None,
    blocked_reasons: list[str],
    deferral_reasons: list[str],
) -> None:
    snapshot = request.snapshot
    if snapshot is None:
        return
    if snapshot.tenant_id != request.tenant_id:
        blocked_reasons.append("snapshot_tenant_mismatch")
    if snapshot.command_id != request.command_id:
        blocked_reasons.append("snapshot_command_mismatch")
    if not snapshot.evidence_refs:
        blocked_reasons.append("attempt_evidence_refs_required")
    if snapshot.terminal_failure:
        blocked_reasons.append("terminal_failure_recorded")
    if first_attempt_at and first_attempt_at > now:
        blocked_reasons.append("first_attempt_in_future")
    if last_attempt_at and last_attempt_at > now:
        blocked_reasons.append("last_attempt_in_future")
    if first_attempt_at and last_attempt_at and last_attempt_at < first_attempt_at:
        blocked_reasons.append("attempt_order_invalid")
    if first_attempt_at and expires_at and expires_at < first_attempt_at:
        blocked_reasons.append("retry_window_invalid")
    if first_attempt_at and expires_at:
        window_seconds = int((expires_at - first_attempt_at).total_seconds())
        if window_seconds > request.policy.max_retry_window_seconds:
            blocked_reasons.append("retry_window_exceeds_policy")
    if last_attempt_at and next_retry_at:
        retry_floor = last_attempt_at + timedelta(seconds=request.policy.retry_after_seconds)
        if next_retry_at < retry_floor:
            blocked_reasons.append("next_retry_before_policy_floor")
    if not blocked_reasons and retry_after_due_at and now < retry_after_due_at:
        deferral_reasons.append("retry_after_not_elapsed")


def _retry_after_due_at(
    *,
    last_attempt_at: datetime | None,
    next_retry_at: datetime | None,
    retry_after_seconds: int,
    cooldown_seconds: int,
) -> datetime | None:
    candidates = []
    if last_attempt_at:
        candidates.append(last_attempt_at + timedelta(seconds=retry_after_seconds))
        candidates.append(last_attempt_at + timedelta(seconds=cooldown_seconds))
    if next_retry_at:
        candidates.append(next_retry_at)
    return max(candidates) if candidates else None


def _attempts_remaining(
    max_attempts: int,
    attempt_number: int,
    failure_count: int,
    retry_required: bool,
) -> int:
    if not retry_required:
        return 0
    return max(0, max_attempts - max(attempt_number, failure_count))


def _status(
    *,
    blocked_reasons: list[str],
    deferral_reasons: list[str],
    retry_required: bool,
    attempts_remaining: int,
    now: datetime,
    expires_at: datetime | None,
) -> str:
    if blocked_reasons:
        return "blocked"
    if not retry_required:
        return "not_required"
    if expires_at and now > expires_at:
        return "retry_expired"
    if attempts_remaining <= 0:
        return "retry_exhausted"
    if deferral_reasons:
        return "retry_deferred"
    return "retry_allowed"


def _retry_state(*, status: str, blocked_reasons: list[str], deferral_reasons: list[str]) -> str:
    if status == "not_required":
        return "not_required"
    if "terminal_failure_recorded" in blocked_reasons:
        return "terminal_failure"
    if "snapshot_tenant_mismatch" in blocked_reasons or "snapshot_command_mismatch" in blocked_reasons:
        return "wrong_scope"
    if status == "retry_expired":
        return "expired"
    if status == "retry_exhausted":
        return "max_attempts_reached"
    if "retry_after_not_elapsed" in deferral_reasons:
        return "cooldown"
    if blocked_reasons:
        return "invalid"
    return "eligible"


def _cooldown_remaining_seconds(status: str, now: datetime, retry_after_due_at: datetime | None) -> int:
    if status != "retry_deferred" or retry_after_due_at is None:
        return 0
    return max(1, int((retry_after_due_at - now).total_seconds()))


def _required_controls_for_status(required_controls: list[str], status: str) -> list[str]:
    if status == "retry_allowed":
        return [*required_controls, "retry_admission"]
    if status == "retry_deferred":
        return [*required_controls, "retry_defer", "retry_after_receipt"]
    if status == "retry_exhausted":
        return [*required_controls, "retry_exhaustion_receipt"]
    if status == "retry_expired":
        return [*required_controls, "retry_expiry_block"]
    if status == "blocked":
        return [*required_controls, "retry_dispatch_block"]
    return required_controls


def _source_receipts_checked(request: RetryWindowRequest) -> bool:
    if request.risk_level not in HIGH_RISK_LEVELS:
        return False
    return all((request.source_temporal_receipt_id, request.source_reapproval_receipt_id))


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


def _normalize_list(values: list[str] | tuple[str, ...]) -> list[str]:
    return [str(value).strip() for value in values if str(value).strip()]


def _unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))
