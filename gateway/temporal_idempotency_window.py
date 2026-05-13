"""Gateway temporal idempotency window evaluator.

Purpose: prove idempotency-key admission before governed effect dispatch.
Governance scope: runtime-owned replay windows, tenant and command scope,
    action scope, request fingerprints, committed effects, terminal receipt
    binding, evidence refs, high-risk source receipt binding, and non-terminal
    receipts.
Dependencies: dataclasses, datetime, command-spine canonical hashing, and the
    Temporal Kernel trusted clock.
Invariants:
  - Runtime clock owns idempotency window truth.
  - Duplicate committed effects never dispatch again.
  - Matching, uncommitted replays may dispatch only inside the replay window.
  - Fingerprint, tenant, command, and action mismatches fail closed.
  - High-risk dispatch binds temporal and reapproval receipts.
  - Temporal idempotency window receipts are not terminal closure certificates.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from datetime import datetime, timedelta, timezone
from typing import Any

from gateway.command_spine import canonical_hash
from gateway.temporal_kernel import TrustedClock


TEMPORAL_IDEMPOTENCY_WINDOW_RECEIPT_SCHEMA_REF = "urn:mullusi:schema:temporal-idempotency-window-receipt:1"
RISK_LEVELS = ("low", "medium", "high", "critical")
IDEMPOTENCY_STATUSES = (
    "admit_new",
    "admit_replay",
    "duplicate_committed",
    "idempotency_expired",
    "blocked",
    "not_required",
)
IDEMPOTENCY_STATES = (
    "new_key",
    "matching_replay",
    "committed",
    "expired",
    "wrong_scope",
    "fingerprint_mismatch",
    "attempts_exceeded",
    "invalid",
    "not_required",
)
HIGH_RISK_LEVELS = frozenset({"high", "critical"})
BASE_IDEMPOTENCY_WINDOW_CONTROLS = (
    "runtime_clock",
    "idempotency_window",
    "idempotency_key",
    "request_fingerprint",
    "tenant_scope",
    "command_scope",
    "action_scope",
    "replay_window",
    "committed_effect",
    "evidence_reference",
    "temporal_idempotency_window_receipt",
    "terminal_closure",
)


@dataclass(frozen=True, slots=True)
class IdempotencyWindowPolicy:
    """Tenant policy defining one governed idempotency replay window."""

    policy_id: str
    tenant_id: str
    scope_id: str
    idempotent_action_types: list[str]
    window_seconds: int
    max_replay_attempts: int
    requires_idempotency_window: bool = True
    high_risk_requires_idempotency_window: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in ("policy_id", "tenant_id", "scope_id"):
            value = str(getattr(self, field_name)).strip()
            if not value:
                raise ValueError(f"{field_name}_required")
            object.__setattr__(self, field_name, value)
        if self.window_seconds < 1:
            raise ValueError("window_seconds_positive_required")
        if self.max_replay_attempts < 1:
            raise ValueError("max_replay_attempts_positive_required")
        idempotent_action_types = _normalize_list(self.idempotent_action_types)
        if not idempotent_action_types:
            raise ValueError("idempotent_action_types_required")
        object.__setattr__(self, "idempotent_action_types", idempotent_action_types)
        object.__setattr__(self, "metadata", dict(self.metadata))


@dataclass(frozen=True, slots=True)
class IdempotencySnapshot:
    """Observed idempotency state for one key and command scope."""

    idempotency_key: str
    tenant_id: str
    command_id: str
    action_type: str
    request_fingerprint: str
    first_seen_at: str
    last_seen_at: str
    expires_at: str
    attempt_count: int
    effect_committed: bool = False
    terminal_receipt_id: str = ""
    prior_receipt_id: str = ""
    evidence_refs: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in (
            "idempotency_key",
            "tenant_id",
            "command_id",
            "action_type",
            "request_fingerprint",
            "first_seen_at",
            "last_seen_at",
            "expires_at",
        ):
            value = str(getattr(self, field_name)).strip()
            if not value:
                raise ValueError(f"{field_name}_required")
            object.__setattr__(self, field_name, value)
        if self.attempt_count < 0:
            raise ValueError("idempotency_attempt_count_nonnegative_required")
        object.__setattr__(self, "terminal_receipt_id", str(self.terminal_receipt_id).strip())
        object.__setattr__(self, "prior_receipt_id", str(self.prior_receipt_id).strip())
        object.__setattr__(self, "evidence_refs", _normalize_list(self.evidence_refs))
        object.__setattr__(self, "metadata", dict(self.metadata))


@dataclass(frozen=True, slots=True)
class IdempotencyWindowRequest:
    """One request to prove idempotency admission before effect dispatch."""

    request_id: str
    tenant_id: str
    actor_id: str
    command_id: str
    action_type: str
    risk_level: str
    idempotency_key: str
    request_fingerprint: str
    policy: IdempotencyWindowPolicy
    evidence_refs: list[str]
    snapshot: IdempotencySnapshot | None = None
    source_temporal_receipt_id: str = ""
    source_scheduler_receipt_id: str = ""
    source_retry_window_receipt_id: str = ""
    source_lease_window_receipt_id: str = ""
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
        object.__setattr__(self, "idempotency_key", str(self.idempotency_key).strip())
        object.__setattr__(self, "request_fingerprint", str(self.request_fingerprint).strip())
        object.__setattr__(self, "evidence_refs", _normalize_list(self.evidence_refs))
        object.__setattr__(self, "source_temporal_receipt_id", str(self.source_temporal_receipt_id).strip())
        object.__setattr__(self, "source_scheduler_receipt_id", str(self.source_scheduler_receipt_id).strip())
        object.__setattr__(
            self,
            "source_retry_window_receipt_id",
            str(self.source_retry_window_receipt_id).strip(),
        )
        object.__setattr__(
            self,
            "source_lease_window_receipt_id",
            str(self.source_lease_window_receipt_id).strip(),
        )
        object.__setattr__(self, "source_reapproval_receipt_id", str(self.source_reapproval_receipt_id).strip())
        object.__setattr__(self, "metadata", dict(self.metadata))


@dataclass(frozen=True, slots=True)
class TemporalIdempotencyWindowReceipt:
    """Schema-backed non-terminal receipt for idempotency window checks."""

    receipt_id: str
    request_id: str
    tenant_id: str
    actor_id: str
    command_id: str
    action_type: str
    risk_level: str
    policy_id: str
    scope_id: str
    idempotency_key: str
    status: str
    idempotency_state: str
    runtime_now_utc: str
    idempotency_required: bool
    first_seen_at: str
    last_seen_at: str
    expires_at: str
    window_age_seconds: int
    seconds_until_expiry: int
    attempt_count: int
    max_replay_attempts: int
    effect_committed: bool
    request_fingerprint: str
    stored_request_fingerprint: str
    terminal_receipt_id: str
    prior_receipt_id: str
    blocked_reasons: list[str]
    required_controls: list[str]
    evidence_refs: list[str]
    snapshot_evidence_refs: list[str]
    source_temporal_receipt_id: str
    source_scheduler_receipt_id: str
    source_retry_window_receipt_id: str
    source_lease_window_receipt_id: str
    source_reapproval_receipt_id: str
    receipt_schema_ref: str
    terminal_closure_required: bool
    receipt_hash: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.status not in IDEMPOTENCY_STATUSES:
            raise ValueError("temporal_idempotency_window_status_invalid")
        if self.idempotency_state not in IDEMPOTENCY_STATES:
            raise ValueError("temporal_idempotency_window_state_invalid")
        for field_name in ("window_age_seconds", "seconds_until_expiry", "attempt_count", "max_replay_attempts"):
            if int(getattr(self, field_name)) < 0:
                raise ValueError("temporal_idempotency_window_counter_nonnegative_required")
        object.__setattr__(self, "blocked_reasons", _normalize_list(self.blocked_reasons))
        object.__setattr__(self, "required_controls", _normalize_list(self.required_controls))
        object.__setattr__(self, "evidence_refs", _normalize_list(self.evidence_refs))
        object.__setattr__(self, "snapshot_evidence_refs", _normalize_list(self.snapshot_evidence_refs))
        object.__setattr__(self, "metadata", dict(self.metadata))


class TemporalIdempotencyWindow:
    """Deterministic runtime idempotency-window evaluator."""

    def __init__(self, clock: TrustedClock | None = None) -> None:
        self._clock = clock or TrustedClock()

    def evaluate(self, request: IdempotencyWindowRequest) -> TemporalIdempotencyWindowReceipt:
        """Return whether this request may dispatch under idempotency rules."""
        now = _parse_required_instant(self._clock.now_utc())
        idempotency_required = _idempotency_required(request)
        snapshot = request.snapshot if idempotency_required else None
        blocked_reasons: list[str] = []
        required_controls = [*BASE_IDEMPOTENCY_WINDOW_CONTROLS]

        if idempotency_required:
            required_controls.append("idempotency_policy_check")
        if request.risk_level in HIGH_RISK_LEVELS:
            required_controls.append("high_risk_idempotency_binding")
        if request.source_temporal_receipt_id:
            required_controls.append("source_temporal_receipt")
        if request.source_scheduler_receipt_id:
            required_controls.append("source_scheduler_receipt")
        if request.source_retry_window_receipt_id:
            required_controls.append("source_retry_window_receipt")
        if request.source_lease_window_receipt_id:
            required_controls.append("source_lease_window_receipt")
        if request.source_reapproval_receipt_id:
            required_controls.append("source_reapproval_receipt")

        blocked_reasons.extend(_policy_violations(request, idempotency_required))
        first_seen_at: datetime | None = None
        last_seen_at: datetime | None = None
        expires_at: datetime | None = None
        if snapshot is not None:
            first_seen_at = _parse_optional_instant(
                snapshot.first_seen_at,
                blocked_reasons,
                "first_seen_at_invalid",
            )
            last_seen_at = _parse_optional_instant(
                snapshot.last_seen_at,
                blocked_reasons,
                "last_seen_at_invalid",
            )
            expires_at = _parse_optional_instant(snapshot.expires_at, blocked_reasons, "expires_at_invalid")
            _apply_snapshot_rules(
                request=request,
                now=now,
                first_seen_at=first_seen_at,
                last_seen_at=last_seen_at,
                expires_at=expires_at,
                blocked_reasons=blocked_reasons,
            )
        elif idempotency_required:
            first_seen_at = now
            last_seen_at = now
            expires_at = now + timedelta(seconds=request.policy.window_seconds)

        status = _status(
            blocked_reasons=blocked_reasons,
            idempotency_required=idempotency_required,
            snapshot=snapshot,
            now=now,
            expires_at=expires_at,
        )
        idempotency_state = _idempotency_state(
            status=status,
            snapshot=snapshot,
            blocked_reasons=blocked_reasons,
        )
        receipt = TemporalIdempotencyWindowReceipt(
            receipt_id="pending",
            request_id=request.request_id,
            tenant_id=request.tenant_id,
            actor_id=request.actor_id,
            command_id=request.command_id,
            action_type=request.action_type,
            risk_level=request.risk_level,
            policy_id=request.policy.policy_id,
            scope_id=request.policy.scope_id,
            idempotency_key=request.idempotency_key if idempotency_required else "",
            status=status,
            idempotency_state=idempotency_state,
            runtime_now_utc=now.isoformat(),
            idempotency_required=idempotency_required,
            first_seen_at=_instant_text(first_seen_at),
            last_seen_at=_instant_text(last_seen_at),
            expires_at=_instant_text(expires_at),
            window_age_seconds=_window_age_seconds(now, first_seen_at, idempotency_required),
            seconds_until_expiry=_seconds_until_expiry(now, expires_at, idempotency_required),
            attempt_count=_attempt_count(snapshot, idempotency_required),
            max_replay_attempts=request.policy.max_replay_attempts if idempotency_required else 0,
            effect_committed=bool(snapshot.effect_committed) if snapshot else False,
            request_fingerprint=request.request_fingerprint if idempotency_required else "",
            stored_request_fingerprint=snapshot.request_fingerprint if snapshot else "",
            terminal_receipt_id=snapshot.terminal_receipt_id if snapshot else "",
            prior_receipt_id=snapshot.prior_receipt_id if snapshot else "",
            blocked_reasons=_unique(blocked_reasons),
            required_controls=_unique(_required_controls_for_status(required_controls, status)),
            evidence_refs=request.evidence_refs,
            snapshot_evidence_refs=snapshot.evidence_refs if snapshot else [],
            source_temporal_receipt_id=request.source_temporal_receipt_id,
            source_scheduler_receipt_id=request.source_scheduler_receipt_id,
            source_retry_window_receipt_id=request.source_retry_window_receipt_id,
            source_lease_window_receipt_id=request.source_lease_window_receipt_id,
            source_reapproval_receipt_id=request.source_reapproval_receipt_id,
            receipt_schema_ref=TEMPORAL_IDEMPOTENCY_WINDOW_RECEIPT_SCHEMA_REF,
            terminal_closure_required=True,
            metadata={
                "receipt_is_not_terminal_closure": True,
                "runtime_owns_time_truth": True,
                "dispatch_allowed": status in {"admit_new", "admit_replay", "not_required"},
                "idempotency_checked": idempotency_required,
                "idempotency_scope_checked": idempotency_required and bool(request.idempotency_key),
                "request_fingerprint_checked": idempotency_required and bool(request.request_fingerprint),
                "committed_effect_checked": idempotency_required and snapshot is not None,
                "high_risk_source_receipts_checked": _source_receipts_checked(request),
            },
        )
        receipt_hash = canonical_hash(asdict(receipt))
        return replace(
            receipt,
            receipt_id=f"temporal-idempotency-window-receipt-{receipt_hash[:16]}",
            receipt_hash=receipt_hash,
        )


def _idempotency_required(request: IdempotencyWindowRequest) -> bool:
    if request.policy.requires_idempotency_window:
        return True
    return request.risk_level in HIGH_RISK_LEVELS and request.policy.high_risk_requires_idempotency_window


def _policy_violations(request: IdempotencyWindowRequest, idempotency_required: bool) -> list[str]:
    violations: list[str] = []
    if request.policy.tenant_id != request.tenant_id:
        violations.append("policy_tenant_mismatch")
    if not idempotency_required:
        return violations
    if request.action_type not in request.policy.idempotent_action_types:
        violations.append("action_type_not_idempotent")
    if not request.idempotency_key:
        violations.append("idempotency_key_required")
    if not request.request_fingerprint:
        violations.append("request_fingerprint_required")
    if not request.evidence_refs:
        violations.append("evidence_refs_required")
    if request.risk_level in HIGH_RISK_LEVELS and not request.source_temporal_receipt_id:
        violations.append("source_temporal_receipt_required_for_high_risk")
    if request.risk_level in HIGH_RISK_LEVELS and not request.source_reapproval_receipt_id:
        violations.append("source_reapproval_receipt_required_for_high_risk")
    return violations


def _apply_snapshot_rules(
    *,
    request: IdempotencyWindowRequest,
    now: datetime,
    first_seen_at: datetime | None,
    last_seen_at: datetime | None,
    expires_at: datetime | None,
    blocked_reasons: list[str],
) -> None:
    snapshot = request.snapshot
    if snapshot is None:
        return
    if snapshot.idempotency_key != request.idempotency_key:
        blocked_reasons.append("snapshot_idempotency_key_mismatch")
    if snapshot.tenant_id != request.tenant_id:
        blocked_reasons.append("snapshot_tenant_mismatch")
    if snapshot.command_id != request.command_id:
        blocked_reasons.append("snapshot_command_mismatch")
    if snapshot.action_type != request.action_type:
        blocked_reasons.append("snapshot_action_mismatch")
    if snapshot.request_fingerprint != request.request_fingerprint:
        blocked_reasons.append("request_fingerprint_mismatch")
    if not snapshot.evidence_refs:
        blocked_reasons.append("snapshot_evidence_refs_required")
    if snapshot.effect_committed and not snapshot.terminal_receipt_id:
        blocked_reasons.append("terminal_receipt_required_for_committed_effect")
    if first_seen_at and first_seen_at > now:
        blocked_reasons.append("first_seen_in_future")
    if last_seen_at and last_seen_at > now:
        blocked_reasons.append("last_seen_in_future")
    if first_seen_at and last_seen_at and last_seen_at < first_seen_at:
        blocked_reasons.append("idempotency_seen_order_invalid")
    if first_seen_at and expires_at and expires_at <= first_seen_at:
        blocked_reasons.append("idempotency_window_invalid")
    if first_seen_at and expires_at:
        window_seconds = int((expires_at - first_seen_at).total_seconds())
        if window_seconds > request.policy.window_seconds:
            blocked_reasons.append("idempotency_window_exceeds_policy")
    if not snapshot.effect_committed and snapshot.attempt_count >= request.policy.max_replay_attempts:
        blocked_reasons.append("max_replay_attempts_exceeded")


def _status(
    *,
    blocked_reasons: list[str],
    idempotency_required: bool,
    snapshot: IdempotencySnapshot | None,
    now: datetime,
    expires_at: datetime | None,
) -> str:
    if blocked_reasons:
        return "blocked"
    if not idempotency_required:
        return "not_required"
    if expires_at and now >= expires_at:
        return "idempotency_expired"
    if snapshot is None:
        return "admit_new"
    if snapshot.effect_committed:
        return "duplicate_committed"
    return "admit_replay"


def _idempotency_state(
    *,
    status: str,
    snapshot: IdempotencySnapshot | None,
    blocked_reasons: list[str],
) -> str:
    if status == "not_required":
        return "not_required"
    scope_mismatch = any(
        reason in blocked_reasons
        for reason in (
            "snapshot_idempotency_key_mismatch",
            "snapshot_tenant_mismatch",
            "snapshot_command_mismatch",
            "snapshot_action_mismatch",
            "action_type_not_idempotent",
        )
    )
    if scope_mismatch:
        return "wrong_scope"
    if "request_fingerprint_mismatch" in blocked_reasons:
        return "fingerprint_mismatch"
    if "max_replay_attempts_exceeded" in blocked_reasons:
        return "attempts_exceeded"
    if status == "idempotency_expired":
        return "expired"
    if status == "duplicate_committed":
        return "committed"
    if status == "admit_new":
        return "new_key"
    if status == "admit_replay":
        return "matching_replay"
    if snapshot and snapshot.effect_committed:
        return "committed"
    return "invalid"


def _window_age_seconds(now: datetime, first_seen_at: datetime | None, idempotency_required: bool) -> int:
    if not idempotency_required or first_seen_at is None:
        return 0
    return max(0, int((now - first_seen_at).total_seconds()))


def _seconds_until_expiry(now: datetime, expires_at: datetime | None, idempotency_required: bool) -> int:
    if not idempotency_required or expires_at is None:
        return 0
    return max(0, int((expires_at - now).total_seconds()))


def _attempt_count(snapshot: IdempotencySnapshot | None, idempotency_required: bool) -> int:
    if not idempotency_required:
        return 0
    if snapshot is None:
        return 1
    return snapshot.attempt_count


def _required_controls_for_status(required_controls: list[str], status: str) -> list[str]:
    if status == "admit_new":
        return [*required_controls, "new_idempotency_key_admission"]
    if status == "admit_replay":
        return [*required_controls, "matching_replay_admission"]
    if status == "duplicate_committed":
        return [*required_controls, "duplicate_dispatch_block", "terminal_receipt_reuse"]
    if status == "idempotency_expired":
        return [*required_controls, "idempotency_expiry_block"]
    if status == "blocked":
        return [*required_controls, "idempotency_dispatch_block"]
    return required_controls


def _source_receipts_checked(request: IdempotencyWindowRequest) -> bool:
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
