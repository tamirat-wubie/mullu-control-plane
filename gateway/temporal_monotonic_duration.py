"""Gateway temporal monotonic-duration evaluator.

Purpose: prove elapsed duration using runtime-owned monotonic time before
    governed dispatch, retry, cooldown, watchdog, or timeout decisions.
Governance scope: monotonic clock readings, duration bounds, cooldown lower
    bounds, high-risk source receipt binding, evidence refs, and non-terminal
    temporal monotonic-duration receipts.
Dependencies: dataclasses, datetime, command-spine canonical hashing, and the
    Temporal Kernel trusted clock.
Invariants:
  - Runtime monotonic clock owns elapsed duration truth.
  - Wall-clock time is audit-only and never used for duration measurement.
  - Negative or regressed monotonic readings fail closed.
  - Duration limits block dispatch when exceeded.
  - Cooldown and retry lower bounds defer dispatch until elapsed.
  - Temporal monotonic-duration receipts are not terminal closure certificates.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from datetime import datetime, timezone
from typing import Any

from gateway.command_spine import canonical_hash
from gateway.temporal_kernel import TrustedClock


TEMPORAL_MONOTONIC_DURATION_RECEIPT_SCHEMA_REF = (
    "urn:mullusi:schema:temporal-monotonic-duration-receipt:1"
)
RISK_LEVELS = ("low", "medium", "high", "critical")
DURATION_KINDS = ("latency", "timeout", "cooldown", "retry_delay", "watchdog")
DURATION_STATUSES = ("within_duration", "deferred", "blocked", "not_required")
DURATION_STATES = ("within", "over_limit", "cooldown_wait", "invalid", "not_required")
HIGH_RISK_LEVELS = frozenset({"high", "critical"})
COOLDOWN_KINDS = frozenset({"cooldown", "retry_delay"})
BASE_MONOTONIC_DURATION_CONTROLS = (
    "runtime_clock",
    "monotonic_clock",
    "duration_policy",
    "evidence_reference",
    "temporal_monotonic_duration_receipt",
    "terminal_closure",
)


@dataclass(frozen=True, slots=True)
class TemporalMonotonicDurationPolicy:
    """Tenant policy defining monotonic duration admission bounds."""

    policy_id: str
    tenant_id: str
    duration_kind: str
    max_duration_ns: int = 0
    min_elapsed_ns: int = 0
    requires_monotonic_duration: bool = True
    high_risk_requires_monotonic_duration: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in ("policy_id", "tenant_id", "duration_kind"):
            value = str(getattr(self, field_name)).strip()
            if not value:
                raise ValueError(f"{field_name}_required")
            object.__setattr__(self, field_name, value)
        if self.duration_kind not in DURATION_KINDS:
            raise ValueError("duration_kind_invalid")
        if self.max_duration_ns < 0:
            raise ValueError("max_duration_ns_nonnegative_required")
        if self.min_elapsed_ns < 0:
            raise ValueError("min_elapsed_ns_nonnegative_required")
        object.__setattr__(self, "metadata", dict(self.metadata))


@dataclass(frozen=True, slots=True)
class TemporalMonotonicDurationRequest:
    """One request to prove monotonic duration before dispatch."""

    request_id: str
    tenant_id: str
    actor_id: str
    command_id: str
    action_type: str
    risk_level: str
    policy: TemporalMonotonicDurationPolicy
    evidence_refs: list[str]
    source_temporal_receipt_id: str = ""
    source_scheduler_receipt_id: str = ""
    source_causal_order_receipt_id: str = ""
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
        object.__setattr__(self, "source_scheduler_receipt_id", str(self.source_scheduler_receipt_id).strip())
        object.__setattr__(
            self,
            "source_causal_order_receipt_id",
            str(self.source_causal_order_receipt_id).strip(),
        )
        object.__setattr__(self, "metadata", dict(self.metadata))


@dataclass(frozen=True, slots=True)
class TemporalMonotonicDurationReceipt:
    """Schema-backed non-terminal receipt for monotonic duration checks."""

    receipt_id: str
    request_id: str
    tenant_id: str
    actor_id: str
    command_id: str
    action_type: str
    risk_level: str
    policy_id: str
    duration_kind: str
    status: str
    duration_state: str
    runtime_now_utc: str
    monotonic_started_ns: int
    monotonic_finished_ns: int
    duration_ns: int
    min_elapsed_ns: int
    max_duration_ns: int
    remaining_ns: int
    overage_ns: int
    duration_required: bool
    deferral_reasons: list[str]
    blocked_reasons: list[str]
    required_controls: list[str]
    evidence_refs: list[str]
    source_temporal_receipt_id: str
    source_scheduler_receipt_id: str
    source_causal_order_receipt_id: str
    receipt_schema_ref: str
    terminal_closure_required: bool
    receipt_hash: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.status not in DURATION_STATUSES:
            raise ValueError("temporal_monotonic_duration_status_invalid")
        if self.duration_state not in DURATION_STATES:
            raise ValueError("temporal_monotonic_duration_state_invalid")
        if self.monotonic_started_ns < 0 or self.monotonic_finished_ns < 0:
            raise ValueError("monotonic_ns_nonnegative_required")
        if self.duration_ns < 0 or self.remaining_ns < 0 or self.overage_ns < 0:
            raise ValueError("duration_measure_nonnegative_required")
        object.__setattr__(self, "deferral_reasons", _normalize_list(self.deferral_reasons))
        object.__setattr__(self, "blocked_reasons", _normalize_list(self.blocked_reasons))
        object.__setattr__(self, "required_controls", _normalize_list(self.required_controls))
        object.__setattr__(self, "evidence_refs", _normalize_list(self.evidence_refs))
        object.__setattr__(self, "metadata", dict(self.metadata))


class TemporalMonotonicDuration:
    """Deterministic runtime monotonic-duration evaluator."""

    def __init__(self, clock: TrustedClock | None = None) -> None:
        self._clock = clock or TrustedClock()

    def evaluate(self, request: TemporalMonotonicDurationRequest) -> TemporalMonotonicDurationReceipt:
        """Return whether elapsed monotonic duration fits policy bounds."""
        runtime_now = _parse_required_instant(self._clock.now_utc())
        monotonic_started_ns = self._clock.monotonic_ns()
        monotonic_finished_ns = self._clock.monotonic_ns()
        duration_required = _duration_required(request)
        blocked_reasons: list[str] = []
        deferral_reasons: list[str] = []
        required_controls = [*BASE_MONOTONIC_DURATION_CONTROLS]

        if duration_required:
            required_controls.append("monotonic_duration_policy")
        if request.risk_level in HIGH_RISK_LEVELS:
            required_controls.append("high_risk_duration")
        if request.source_temporal_receipt_id:
            required_controls.append("source_temporal_receipt")
        if request.source_scheduler_receipt_id:
            required_controls.append("source_scheduler_receipt")
        if request.source_causal_order_receipt_id:
            required_controls.append("source_causal_order_receipt")

        blocked_reasons.extend(_policy_violations(request, duration_required))
        if monotonic_started_ns < 0 or monotonic_finished_ns < 0:
            blocked_reasons.append("monotonic_reading_negative")
        if monotonic_finished_ns < monotonic_started_ns:
            blocked_reasons.append("monotonic_clock_regressed")

        duration_ns = max(0, monotonic_finished_ns - monotonic_started_ns)
        remaining_ns = _remaining_ns(duration_ns, request.policy.min_elapsed_ns, duration_required)
        overage_ns = _overage_ns(duration_ns, request.policy.max_duration_ns, duration_required)
        if overage_ns > 0:
            blocked_reasons.append("duration_limit_exceeded")
        if remaining_ns > 0:
            deferral_reasons.append("duration_window_not_elapsed")

        status = _status(
            blocked_reasons=blocked_reasons,
            deferral_reasons=deferral_reasons,
            duration_required=duration_required,
        )
        duration_state = _duration_state(
            status=status,
            blocked_reasons=blocked_reasons,
            overage_ns=overage_ns,
            remaining_ns=remaining_ns,
        )
        receipt = TemporalMonotonicDurationReceipt(
            receipt_id="pending",
            request_id=request.request_id,
            tenant_id=request.tenant_id,
            actor_id=request.actor_id,
            command_id=request.command_id,
            action_type=request.action_type,
            risk_level=request.risk_level,
            policy_id=request.policy.policy_id,
            duration_kind=request.policy.duration_kind,
            status=status,
            duration_state=duration_state,
            runtime_now_utc=runtime_now.isoformat(),
            monotonic_started_ns=monotonic_started_ns,
            monotonic_finished_ns=monotonic_finished_ns,
            duration_ns=duration_ns,
            min_elapsed_ns=request.policy.min_elapsed_ns,
            max_duration_ns=request.policy.max_duration_ns,
            remaining_ns=remaining_ns,
            overage_ns=overage_ns,
            duration_required=duration_required,
            deferral_reasons=_unique(deferral_reasons),
            blocked_reasons=_unique(blocked_reasons),
            required_controls=_unique(
                required_controls
                if status in {"within_duration", "not_required"}
                else [*required_controls, "duration_dispatch_block"]
            ),
            evidence_refs=request.evidence_refs,
            source_temporal_receipt_id=request.source_temporal_receipt_id,
            source_scheduler_receipt_id=request.source_scheduler_receipt_id,
            source_causal_order_receipt_id=request.source_causal_order_receipt_id,
            receipt_schema_ref=TEMPORAL_MONOTONIC_DURATION_RECEIPT_SCHEMA_REF,
            terminal_closure_required=True,
            metadata={
                "receipt_is_not_terminal_closure": True,
                "runtime_owns_time_truth": True,
                "monotonic_used_for_duration": True,
                "wall_clock_not_used_for_duration": True,
                "dispatch_allowed": status in {"within_duration", "not_required"},
                "defer_required": status == "deferred",
                "duration_limit_checked": duration_required and request.policy.max_duration_ns > 0,
                "cooldown_checked": duration_required and request.policy.duration_kind in COOLDOWN_KINDS,
                "high_risk_duration_checked": request.risk_level in HIGH_RISK_LEVELS,
            },
        )
        receipt_hash = canonical_hash(asdict(receipt))
        return replace(
            receipt,
            receipt_id=f"temporal-monotonic-duration-receipt-{receipt_hash[:16]}",
            receipt_hash=receipt_hash,
        )


def _duration_required(request: TemporalMonotonicDurationRequest) -> bool:
    if request.policy.requires_monotonic_duration:
        return True
    return request.risk_level in HIGH_RISK_LEVELS and request.policy.high_risk_requires_monotonic_duration


def _policy_violations(request: TemporalMonotonicDurationRequest, duration_required: bool) -> list[str]:
    violations: list[str] = []
    if request.policy.tenant_id != request.tenant_id:
        violations.append("policy_tenant_mismatch")
    if not duration_required:
        return violations
    if request.policy.max_duration_ns == 0 and request.policy.min_elapsed_ns == 0:
        violations.append("duration_bound_required")
    if not request.evidence_refs:
        violations.append("evidence_refs_required")
    if request.risk_level in HIGH_RISK_LEVELS and not request.source_temporal_receipt_id:
        violations.append("source_temporal_receipt_required_for_high_risk")
    if (
        request.risk_level in HIGH_RISK_LEVELS
        and request.policy.duration_kind in COOLDOWN_KINDS
        and not request.source_scheduler_receipt_id
    ):
        violations.append("source_scheduler_receipt_required_for_high_risk_cooldown")
    return violations


def _remaining_ns(duration_ns: int, min_elapsed_ns: int, duration_required: bool) -> int:
    if not duration_required or min_elapsed_ns == 0:
        return 0
    return max(0, min_elapsed_ns - duration_ns)


def _overage_ns(duration_ns: int, max_duration_ns: int, duration_required: bool) -> int:
    if not duration_required or max_duration_ns == 0:
        return 0
    return max(0, duration_ns - max_duration_ns)


def _status(
    *,
    blocked_reasons: list[str],
    deferral_reasons: list[str],
    duration_required: bool,
) -> str:
    if blocked_reasons:
        return "blocked"
    if deferral_reasons:
        return "deferred"
    if not duration_required:
        return "not_required"
    return "within_duration"


def _duration_state(
    *,
    status: str,
    blocked_reasons: list[str],
    overage_ns: int,
    remaining_ns: int,
) -> str:
    if status == "not_required":
        return "not_required"
    if "monotonic_clock_regressed" in blocked_reasons or "monotonic_reading_negative" in blocked_reasons:
        return "invalid"
    if overage_ns > 0:
        return "over_limit"
    if remaining_ns > 0:
        return "cooldown_wait"
    if status == "blocked":
        return "invalid"
    return "within"


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
