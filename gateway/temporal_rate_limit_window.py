"""Gateway temporal rate-limit window evaluator.

Purpose: prove rate-limit window admission before governed dispatch.
Governance scope: runtime-owned rate-limit timing, tenant scope, endpoint
    scope, identity scope, token projection, burst limits, retry-after timing,
    evidence refs, high-risk source receipt binding, and non-terminal receipts.
Dependencies: dataclasses, datetime, decimal, command-spine canonical hashing,
    and the Temporal Kernel trusted clock.
Invariants:
  - Runtime clock owns rate-limit window truth.
  - Token projection must be computed before dispatch admission.
  - Exhausted windows return retry-after timing instead of silent denial.
  - Tenant, endpoint, identity, and scope mismatches fail closed.
  - High-risk dispatch binds temporal and reapproval receipts.
  - Temporal rate-limit window receipts are not terminal closure certificates.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from datetime import datetime, timezone
from decimal import Decimal, ROUND_CEILING
from typing import Any

from gateway.command_spine import canonical_hash
from gateway.temporal_kernel import TrustedClock


TEMPORAL_RATE_LIMIT_WINDOW_RECEIPT_SCHEMA_REF = "urn:mullusi:schema:temporal-rate-limit-window-receipt:1"
RISK_LEVELS = ("low", "medium", "high", "critical")
RATE_LIMIT_STATUSES = ("within_limit", "throttled", "deferred", "blocked", "not_required")
RATE_LIMIT_STATES = ("available", "exhausted", "future", "expired", "wrong_scope", "invalid", "not_required")
HIGH_RISK_LEVELS = frozenset({"high", "critical"})
BASE_RATE_LIMIT_WINDOW_CONTROLS = (
    "runtime_clock",
    "rate_limit_window",
    "tenant_scope",
    "endpoint_scope",
    "identity_scope",
    "token_projection",
    "retry_after",
    "evidence_reference",
    "temporal_rate_limit_window_receipt",
    "terminal_closure",
)


@dataclass(frozen=True, slots=True)
class RateLimitWindowPolicy:
    """Tenant policy defining one governed rate-limit window."""

    policy_id: str
    tenant_id: str
    scope_id: str
    endpoint_patterns: list[str]
    max_tokens: int
    refill_rate_per_second: Decimal | int | float | str
    burst_limit: int
    window_seconds: int
    requires_rate_limit_window: bool = True
    high_risk_requires_rate_limit_window: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in ("policy_id", "tenant_id", "scope_id"):
            value = str(getattr(self, field_name)).strip()
            if not value:
                raise ValueError(f"{field_name}_required")
            object.__setattr__(self, field_name, value)
        if self.max_tokens < 1:
            raise ValueError("max_tokens_positive_required")
        if self.burst_limit < 1:
            raise ValueError("burst_limit_positive_required")
        if self.window_seconds < 1:
            raise ValueError("window_seconds_positive_required")
        endpoint_patterns = _normalize_list(self.endpoint_patterns)
        if not endpoint_patterns:
            raise ValueError("endpoint_patterns_required")
        object.__setattr__(self, "endpoint_patterns", endpoint_patterns)
        object.__setattr__(
            self,
            "refill_rate_per_second",
            _positive_decimal(self.refill_rate_per_second, "refill_rate_per_second"),
        )
        object.__setattr__(self, "metadata", dict(self.metadata))


@dataclass(frozen=True, slots=True)
class RateLimitWindowSnapshot:
    """Observed token bucket state for one rate-limit scope."""

    snapshot_id: str
    tenant_id: str
    scope_id: str
    bucket_key: str
    endpoint: str
    identity_id: str
    window_start: str
    window_end: str
    observed_at: str
    remaining_tokens: int
    consumed_tokens: int
    denied_count: int = 0
    evidence_refs: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in (
            "snapshot_id",
            "tenant_id",
            "scope_id",
            "bucket_key",
            "endpoint",
            "window_start",
            "window_end",
            "observed_at",
        ):
            value = str(getattr(self, field_name)).strip()
            if not value:
                raise ValueError(f"{field_name}_required")
            object.__setattr__(self, field_name, value)
        if self.remaining_tokens < 0 or self.consumed_tokens < 0 or self.denied_count < 0:
            raise ValueError("rate_limit_counter_nonnegative_required")
        object.__setattr__(self, "identity_id", str(self.identity_id).strip())
        object.__setattr__(self, "evidence_refs", _normalize_list(self.evidence_refs))
        object.__setattr__(self, "metadata", dict(self.metadata))


@dataclass(frozen=True, slots=True)
class RateLimitWindowRequest:
    """One request to prove rate-limit admission before dispatch."""

    request_id: str
    tenant_id: str
    actor_id: str
    command_id: str
    action_type: str
    risk_level: str
    endpoint: str
    identity_id: str
    tokens_requested: int
    policy: RateLimitWindowPolicy
    evidence_refs: list[str]
    snapshot: RateLimitWindowSnapshot | None = None
    source_temporal_receipt_id: str = ""
    source_dispatch_window_receipt_id: str = ""
    source_reapproval_receipt_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in (
            "request_id",
            "tenant_id",
            "actor_id",
            "command_id",
            "action_type",
            "risk_level",
            "endpoint",
        ):
            value = str(getattr(self, field_name)).strip()
            if not value:
                raise ValueError(f"{field_name}_required")
            object.__setattr__(self, field_name, value)
        if self.risk_level not in RISK_LEVELS:
            raise ValueError("risk_level_invalid")
        if self.tokens_requested < 1:
            raise ValueError("tokens_requested_positive_required")
        object.__setattr__(self, "identity_id", str(self.identity_id).strip())
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
class TemporalRateLimitWindowReceipt:
    """Schema-backed non-terminal receipt for rate-limit window checks."""

    receipt_id: str
    request_id: str
    tenant_id: str
    actor_id: str
    command_id: str
    action_type: str
    risk_level: str
    policy_id: str
    scope_id: str
    endpoint: str
    identity_id: str
    bucket_key: str
    status: str
    rate_limit_state: str
    runtime_now_utc: str
    window_start: str
    window_end: str
    reset_at: str
    retry_after_seconds: int
    rate_limit_required: bool
    max_tokens: int
    remaining_tokens: int
    consumed_tokens: int
    denied_count: int
    tokens_requested: int
    projected_remaining_tokens: int
    deficit_tokens: int
    refill_rate_per_second: str
    burst_limit: int
    window_seconds: int
    blocked_reasons: list[str]
    deferral_reasons: list[str]
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
        if self.status not in RATE_LIMIT_STATUSES:
            raise ValueError("temporal_rate_limit_window_status_invalid")
        if self.rate_limit_state not in RATE_LIMIT_STATES:
            raise ValueError("temporal_rate_limit_window_state_invalid")
        for field_name in (
            "retry_after_seconds",
            "max_tokens",
            "remaining_tokens",
            "consumed_tokens",
            "denied_count",
            "tokens_requested",
            "projected_remaining_tokens",
            "deficit_tokens",
            "burst_limit",
            "window_seconds",
        ):
            if int(getattr(self, field_name)) < 0:
                raise ValueError("rate_limit_receipt_counter_nonnegative_required")
        object.__setattr__(self, "blocked_reasons", _normalize_list(self.blocked_reasons))
        object.__setattr__(self, "deferral_reasons", _normalize_list(self.deferral_reasons))
        object.__setattr__(self, "required_controls", _normalize_list(self.required_controls))
        object.__setattr__(self, "evidence_refs", _normalize_list(self.evidence_refs))
        object.__setattr__(self, "snapshot_evidence_refs", _normalize_list(self.snapshot_evidence_refs))
        object.__setattr__(self, "metadata", dict(self.metadata))


class TemporalRateLimitWindow:
    """Deterministic runtime rate-limit window evaluator."""

    def __init__(self, clock: TrustedClock | None = None) -> None:
        self._clock = clock or TrustedClock()

    def evaluate(self, request: RateLimitWindowRequest) -> TemporalRateLimitWindowReceipt:
        """Return whether this action fits the active rate-limit window."""
        now = _parse_required_instant(self._clock.now_utc())
        rate_limit_required = _rate_limit_required(request)
        snapshot = request.snapshot if rate_limit_required else None
        blocked_reasons: list[str] = []
        deferral_reasons: list[str] = []
        required_controls = [*BASE_RATE_LIMIT_WINDOW_CONTROLS]

        if rate_limit_required:
            required_controls.append("active_rate_limit_window")
        if request.risk_level in HIGH_RISK_LEVELS:
            required_controls.append("high_risk_rate_limit_window")
        if request.source_temporal_receipt_id:
            required_controls.append("source_temporal_receipt")
        if request.source_dispatch_window_receipt_id:
            required_controls.append("source_dispatch_window_receipt")
        if request.source_reapproval_receipt_id:
            required_controls.append("source_reapproval_receipt")

        blocked_reasons.extend(_policy_violations(request, rate_limit_required))
        window_start: datetime | None = None
        window_end: datetime | None = None
        observed_at: datetime | None = None
        if snapshot is not None:
            window_start = _parse_optional_instant(snapshot.window_start, blocked_reasons, "snapshot_window_start_invalid")
            window_end = _parse_optional_instant(snapshot.window_end, blocked_reasons, "snapshot_window_end_invalid")
            observed_at = _parse_optional_instant(snapshot.observed_at, blocked_reasons, "snapshot_observed_at_invalid")
            _apply_snapshot_rules(
                request=request,
                now=now,
                window_start=window_start,
                window_end=window_end,
                observed_at=observed_at,
                blocked_reasons=blocked_reasons,
                deferral_reasons=deferral_reasons,
            )

        remaining_tokens = snapshot.remaining_tokens if snapshot else 0
        consumed_tokens = snapshot.consumed_tokens if snapshot else 0
        denied_count = snapshot.denied_count if snapshot else 0
        deficit_tokens = _deficit_tokens(request.tokens_requested, remaining_tokens, rate_limit_required)
        projected_remaining_tokens = _projected_remaining_tokens(
            request.tokens_requested,
            remaining_tokens,
            rate_limit_required,
        )
        if rate_limit_required and deficit_tokens > 0:
            required_controls.append("rate_limit_throttle")

        status = _status(
            blocked_reasons=blocked_reasons,
            deferral_reasons=deferral_reasons,
            deficit_tokens=deficit_tokens,
            rate_limit_required=rate_limit_required,
        )
        retry_after_seconds = _retry_after_seconds(
            status=status,
            now=now,
            window_start=window_start,
            deficit_tokens=deficit_tokens,
            refill_rate=request.policy.refill_rate_per_second,
        )
        rate_limit_state = _rate_limit_state(
            status=status,
            blocked_reasons=blocked_reasons,
            deferral_reasons=deferral_reasons,
            deficit_tokens=deficit_tokens,
        )
        receipt = TemporalRateLimitWindowReceipt(
            receipt_id="pending",
            request_id=request.request_id,
            tenant_id=request.tenant_id,
            actor_id=request.actor_id,
            command_id=request.command_id,
            action_type=request.action_type,
            risk_level=request.risk_level,
            policy_id=request.policy.policy_id,
            scope_id=request.policy.scope_id,
            endpoint=request.endpoint,
            identity_id=request.identity_id,
            bucket_key=snapshot.bucket_key if snapshot else "",
            status=status,
            rate_limit_state=rate_limit_state,
            runtime_now_utc=now.isoformat(),
            window_start=_instant_text(window_start),
            window_end=_instant_text(window_end),
            reset_at=_reset_at(status, window_start, window_end),
            retry_after_seconds=retry_after_seconds,
            rate_limit_required=rate_limit_required,
            max_tokens=request.policy.max_tokens if rate_limit_required else 0,
            remaining_tokens=remaining_tokens,
            consumed_tokens=consumed_tokens,
            denied_count=denied_count,
            tokens_requested=request.tokens_requested,
            projected_remaining_tokens=projected_remaining_tokens,
            deficit_tokens=deficit_tokens,
            refill_rate_per_second=_decimal_text(request.policy.refill_rate_per_second),
            burst_limit=request.policy.burst_limit if rate_limit_required else 0,
            window_seconds=request.policy.window_seconds if rate_limit_required else 0,
            blocked_reasons=_unique(blocked_reasons),
            deferral_reasons=_unique(deferral_reasons),
            required_controls=_unique(_required_controls_for_status(required_controls, status)),
            evidence_refs=request.evidence_refs,
            snapshot_evidence_refs=snapshot.evidence_refs if snapshot else [],
            source_temporal_receipt_id=request.source_temporal_receipt_id,
            source_dispatch_window_receipt_id=request.source_dispatch_window_receipt_id,
            source_reapproval_receipt_id=request.source_reapproval_receipt_id,
            receipt_schema_ref=TEMPORAL_RATE_LIMIT_WINDOW_RECEIPT_SCHEMA_REF,
            terminal_closure_required=True,
            metadata={
                "receipt_is_not_terminal_closure": True,
                "runtime_owns_time_truth": True,
                "dispatch_allowed": status in {"within_limit", "not_required"},
                "retry_after_required": status in {"throttled", "deferred"},
                "rate_limit_checked": rate_limit_required,
                "token_projection_checked": rate_limit_required and snapshot is not None,
                "window_bounds_checked": rate_limit_required and snapshot is not None,
                "high_risk_source_receipts_checked": _source_receipts_checked(request),
            },
        )
        receipt_hash = canonical_hash(asdict(receipt))
        return replace(
            receipt,
            receipt_id=f"temporal-rate-limit-window-receipt-{receipt_hash[:16]}",
            receipt_hash=receipt_hash,
        )


def _rate_limit_required(request: RateLimitWindowRequest) -> bool:
    if request.policy.requires_rate_limit_window:
        return True
    return request.risk_level in HIGH_RISK_LEVELS and request.policy.high_risk_requires_rate_limit_window


def _policy_violations(request: RateLimitWindowRequest, rate_limit_required: bool) -> list[str]:
    violations: list[str] = []
    if request.policy.tenant_id != request.tenant_id:
        violations.append("policy_tenant_mismatch")
    if not rate_limit_required:
        return violations
    if not _endpoint_allowed(request.endpoint, request.policy.endpoint_patterns):
        violations.append("endpoint_not_allowed")
    if request.tokens_requested > request.policy.burst_limit:
        violations.append("burst_limit_exceeded")
    if request.snapshot is None:
        violations.append("rate_limit_snapshot_required")
    if not request.evidence_refs:
        violations.append("evidence_refs_required")
    if request.risk_level in HIGH_RISK_LEVELS and not request.source_temporal_receipt_id:
        violations.append("source_temporal_receipt_required_for_high_risk")
    if request.risk_level in HIGH_RISK_LEVELS and not request.source_reapproval_receipt_id:
        violations.append("source_reapproval_receipt_required_for_high_risk")
    return violations


def _apply_snapshot_rules(
    *,
    request: RateLimitWindowRequest,
    now: datetime,
    window_start: datetime | None,
    window_end: datetime | None,
    observed_at: datetime | None,
    blocked_reasons: list[str],
    deferral_reasons: list[str],
) -> None:
    snapshot = request.snapshot
    if snapshot is None:
        return
    if snapshot.tenant_id != request.tenant_id:
        blocked_reasons.append("snapshot_tenant_mismatch")
    if snapshot.scope_id != request.policy.scope_id:
        blocked_reasons.append("snapshot_scope_mismatch")
    if snapshot.endpoint != request.endpoint:
        blocked_reasons.append("snapshot_endpoint_mismatch")
    if snapshot.identity_id != request.identity_id:
        blocked_reasons.append("snapshot_identity_mismatch")
    if not snapshot.evidence_refs:
        blocked_reasons.append("snapshot_evidence_refs_required")
    if observed_at and observed_at > now:
        blocked_reasons.append("snapshot_observed_in_future")
    if window_start and window_end and window_end <= window_start:
        blocked_reasons.append("snapshot_window_invalid")
        return
    if window_start and now < window_start:
        deferral_reasons.append("rate_limit_window_not_started")
    if window_end and now >= window_end:
        blocked_reasons.append("rate_limit_snapshot_expired")


def _endpoint_allowed(endpoint: str, endpoint_patterns: list[str]) -> bool:
    for pattern in endpoint_patterns:
        if pattern == endpoint:
            return True
        if pattern.endswith("*") and endpoint.startswith(pattern[:-1]):
            return True
    return False


def _deficit_tokens(tokens_requested: int, remaining_tokens: int, rate_limit_required: bool) -> int:
    if not rate_limit_required:
        return 0
    return max(0, tokens_requested - remaining_tokens)


def _projected_remaining_tokens(tokens_requested: int, remaining_tokens: int, rate_limit_required: bool) -> int:
    if not rate_limit_required:
        return 0
    return max(0, remaining_tokens - tokens_requested)


def _status(
    *,
    blocked_reasons: list[str],
    deferral_reasons: list[str],
    deficit_tokens: int,
    rate_limit_required: bool,
) -> str:
    if blocked_reasons:
        return "blocked"
    if deferral_reasons:
        return "deferred"
    if not rate_limit_required:
        return "not_required"
    if deficit_tokens > 0:
        return "throttled"
    return "within_limit"


def _rate_limit_state(
    *,
    status: str,
    blocked_reasons: list[str],
    deferral_reasons: list[str],
    deficit_tokens: int,
) -> str:
    if status == "not_required":
        return "not_required"
    if "snapshot_tenant_mismatch" in blocked_reasons or "snapshot_scope_mismatch" in blocked_reasons:
        return "wrong_scope"
    if "endpoint_not_allowed" in blocked_reasons or "snapshot_endpoint_mismatch" in blocked_reasons:
        return "wrong_scope"
    if "snapshot_identity_mismatch" in blocked_reasons:
        return "wrong_scope"
    if "rate_limit_window_not_started" in deferral_reasons:
        return "future"
    if "rate_limit_snapshot_expired" in blocked_reasons:
        return "expired"
    if blocked_reasons:
        return "invalid"
    if deficit_tokens > 0:
        return "exhausted"
    return "available"


def _retry_after_seconds(
    *,
    status: str,
    now: datetime,
    window_start: datetime | None,
    deficit_tokens: int,
    refill_rate: Decimal,
) -> int:
    if status == "deferred" and window_start:
        return max(1, int((window_start - now).total_seconds()))
    if status != "throttled" or deficit_tokens <= 0:
        return 0
    return max(1, int((Decimal(deficit_tokens) / refill_rate).to_integral_value(rounding=ROUND_CEILING)))


def _reset_at(status: str, window_start: datetime | None, window_end: datetime | None) -> str:
    if status == "deferred" and window_start:
        return window_start.isoformat()
    return window_end.isoformat() if window_end else ""


def _required_controls_for_status(required_controls: list[str], status: str) -> list[str]:
    if status == "within_limit":
        return [*required_controls, "rate_limit_admission"]
    if status == "throttled":
        return [*required_controls, "rate_limit_throttle_receipt", "retry_after_receipt"]
    if status == "deferred":
        return [*required_controls, "rate_limit_defer"]
    if status == "blocked":
        return [*required_controls, "rate_limit_dispatch_block"]
    return required_controls


def _source_receipts_checked(request: RateLimitWindowRequest) -> bool:
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


def _positive_decimal(value: Decimal | int | float | str, field_name: str) -> Decimal:
    decimal_value = Decimal(str(value))
    if decimal_value <= Decimal("0"):
        raise ValueError(f"{field_name}_positive_required")
    return decimal_value


def _decimal_text(value: Decimal) -> str:
    return format(value.normalize(), "f")


def _normalize_list(values: list[str] | tuple[str, ...]) -> list[str]:
    return [str(value).strip() for value in values if str(value).strip()]


def _unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))
