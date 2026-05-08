"""Gateway temporal lease window evaluator.

Purpose: prove lease ownership before governed worker dispatch.
Governance scope: runtime-owned lease timing, tenant and command scope,
    resource scope, worker ownership, fencing tokens, expiry, renewal warning
    windows, evidence refs, high-risk source receipt binding, and non-terminal
    receipts.
Dependencies: dataclasses, datetime, fnmatch, command-spine canonical hashing,
    and the Temporal Kernel trusted clock.
Invariants:
  - Runtime clock owns lease timing truth.
  - A worker may dispatch only with an active, scoped, unreleased lease.
  - Lease expiry and max-age policy fail closed.
  - Near-expiry leases warn and require renewal before subsequent dispatch.
  - Fencing tokens and positive sequence numbers are required.
  - High-risk dispatch binds temporal and reapproval receipts.
  - Temporal lease window receipts are not terminal closure certificates.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from datetime import datetime, timezone
from fnmatch import fnmatchcase
from typing import Any

from gateway.command_spine import canonical_hash
from gateway.temporal_kernel import TrustedClock


TEMPORAL_LEASE_WINDOW_RECEIPT_SCHEMA_REF = "urn:mullusi:schema:temporal-lease-window-receipt:1"
RISK_LEVELS = ("low", "medium", "high", "critical")
LEASE_STATUSES = ("lease_active", "lease_expiring", "lease_expired", "blocked", "not_required")
LEASE_STATES = ("active", "expiring", "expired", "released", "revoked", "wrong_scope", "invalid", "not_required")
HIGH_RISK_LEVELS = frozenset({"high", "critical"})
BASE_LEASE_WINDOW_CONTROLS = (
    "runtime_clock",
    "lease_window",
    "tenant_scope",
    "command_scope",
    "resource_scope",
    "worker_scope",
    "lease_owner_scope",
    "fencing_token",
    "lease_expiry",
    "renewal_window",
    "evidence_reference",
    "temporal_lease_window_receipt",
    "terminal_closure",
)


@dataclass(frozen=True, slots=True)
class LeaseWindowPolicy:
    """Tenant policy defining one governed lease window."""

    policy_id: str
    tenant_id: str
    scope_id: str
    allowed_resource_patterns: list[str]
    max_lease_seconds: int
    renewal_grace_seconds: int
    requires_lease_window: bool = True
    high_risk_requires_lease_window: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in ("policy_id", "tenant_id", "scope_id"):
            value = str(getattr(self, field_name)).strip()
            if not value:
                raise ValueError(f"{field_name}_required")
            object.__setattr__(self, field_name, value)
        if self.max_lease_seconds < 1:
            raise ValueError("max_lease_seconds_positive_required")
        if self.renewal_grace_seconds < 0:
            raise ValueError("renewal_grace_seconds_nonnegative_required")
        allowed_resource_patterns = _normalize_list(self.allowed_resource_patterns)
        if not allowed_resource_patterns:
            raise ValueError("allowed_resource_patterns_required")
        object.__setattr__(self, "allowed_resource_patterns", allowed_resource_patterns)
        object.__setattr__(self, "metadata", dict(self.metadata))


@dataclass(frozen=True, slots=True)
class LeaseSnapshot:
    """Observed lease ownership state for one worker/resource pair."""

    lease_id: str
    tenant_id: str
    command_id: str
    resource_id: str
    worker_id: str
    lease_owner_id: str
    acquired_at: str
    lease_expires_at: str
    fencing_token: str
    sequence: int
    last_renewed_at: str = ""
    released: bool = False
    revoked: bool = False
    evidence_refs: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in (
            "lease_id",
            "tenant_id",
            "command_id",
            "resource_id",
            "worker_id",
            "lease_owner_id",
            "acquired_at",
            "lease_expires_at",
        ):
            value = str(getattr(self, field_name)).strip()
            if not value:
                raise ValueError(f"{field_name}_required")
            object.__setattr__(self, field_name, value)
        object.__setattr__(self, "fencing_token", str(self.fencing_token).strip())
        object.__setattr__(self, "last_renewed_at", str(self.last_renewed_at).strip())
        object.__setattr__(self, "evidence_refs", _normalize_list(self.evidence_refs))
        object.__setattr__(self, "metadata", dict(self.metadata))


@dataclass(frozen=True, slots=True)
class LeaseWindowRequest:
    """One request to prove lease admission before worker dispatch."""

    request_id: str
    tenant_id: str
    actor_id: str
    command_id: str
    action_type: str
    risk_level: str
    resource_id: str
    worker_id: str
    lease_owner_id: str
    policy: LeaseWindowPolicy
    evidence_refs: list[str]
    snapshot: LeaseSnapshot | None = None
    source_temporal_receipt_id: str = ""
    source_scheduler_receipt_id: str = ""
    source_retry_window_receipt_id: str = ""
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
            "resource_id",
            "worker_id",
            "lease_owner_id",
        ):
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
            "source_retry_window_receipt_id",
            str(self.source_retry_window_receipt_id).strip(),
        )
        object.__setattr__(self, "source_reapproval_receipt_id", str(self.source_reapproval_receipt_id).strip())
        object.__setattr__(self, "metadata", dict(self.metadata))


@dataclass(frozen=True, slots=True)
class TemporalLeaseWindowReceipt:
    """Schema-backed non-terminal receipt for lease window checks."""

    receipt_id: str
    request_id: str
    tenant_id: str
    actor_id: str
    command_id: str
    action_type: str
    risk_level: str
    policy_id: str
    scope_id: str
    lease_id: str
    resource_id: str
    worker_id: str
    lease_owner_id: str
    status: str
    lease_state: str
    runtime_now_utc: str
    lease_required: bool
    acquired_at: str
    last_renewed_at: str
    lease_expires_at: str
    lease_age_seconds: int
    seconds_until_expiry: int
    max_lease_seconds: int
    renewal_grace_seconds: int
    fencing_token: str
    sequence: int
    released: bool
    revoked: bool
    blocked_reasons: list[str]
    warning_reasons: list[str]
    required_controls: list[str]
    evidence_refs: list[str]
    lease_evidence_refs: list[str]
    source_temporal_receipt_id: str
    source_scheduler_receipt_id: str
    source_retry_window_receipt_id: str
    source_reapproval_receipt_id: str
    receipt_schema_ref: str
    terminal_closure_required: bool
    receipt_hash: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.status not in LEASE_STATUSES:
            raise ValueError("temporal_lease_window_status_invalid")
        if self.lease_state not in LEASE_STATES:
            raise ValueError("temporal_lease_window_state_invalid")
        for field_name in (
            "lease_age_seconds",
            "seconds_until_expiry",
            "max_lease_seconds",
            "renewal_grace_seconds",
            "sequence",
        ):
            if int(getattr(self, field_name)) < 0:
                raise ValueError("temporal_lease_window_counter_nonnegative_required")
        object.__setattr__(self, "blocked_reasons", _normalize_list(self.blocked_reasons))
        object.__setattr__(self, "warning_reasons", _normalize_list(self.warning_reasons))
        object.__setattr__(self, "required_controls", _normalize_list(self.required_controls))
        object.__setattr__(self, "evidence_refs", _normalize_list(self.evidence_refs))
        object.__setattr__(self, "lease_evidence_refs", _normalize_list(self.lease_evidence_refs))
        object.__setattr__(self, "metadata", dict(self.metadata))


class TemporalLeaseWindow:
    """Deterministic runtime lease-window evaluator."""

    def __init__(self, clock: TrustedClock | None = None) -> None:
        self._clock = clock or TrustedClock()

    def evaluate(self, request: LeaseWindowRequest) -> TemporalLeaseWindowReceipt:
        """Return whether this worker owns a valid lease for dispatch."""
        now = _parse_required_instant(self._clock.now_utc())
        lease_required = _lease_required(request)
        snapshot = request.snapshot if lease_required else None
        blocked_reasons: list[str] = []
        warning_reasons: list[str] = []
        required_controls = [*BASE_LEASE_WINDOW_CONTROLS]

        if lease_required:
            required_controls.append("active_lease_window")
        if request.risk_level in HIGH_RISK_LEVELS:
            required_controls.append("high_risk_lease_binding")
        if request.source_temporal_receipt_id:
            required_controls.append("source_temporal_receipt")
        if request.source_scheduler_receipt_id:
            required_controls.append("source_scheduler_receipt")
        if request.source_retry_window_receipt_id:
            required_controls.append("source_retry_window_receipt")
        if request.source_reapproval_receipt_id:
            required_controls.append("source_reapproval_receipt")

        blocked_reasons.extend(_policy_violations(request, lease_required))
        acquired_at: datetime | None = None
        last_renewed_at: datetime | None = None
        lease_expires_at: datetime | None = None
        if snapshot is not None:
            acquired_at = _parse_optional_instant(snapshot.acquired_at, blocked_reasons, "acquired_at_invalid")
            last_renewed_at = _parse_optional_instant(
                snapshot.last_renewed_at or snapshot.acquired_at,
                blocked_reasons,
                "last_renewed_at_invalid",
            )
            lease_expires_at = _parse_optional_instant(
                snapshot.lease_expires_at,
                blocked_reasons,
                "lease_expires_at_invalid",
            )
            _apply_snapshot_rules(
                request=request,
                now=now,
                acquired_at=acquired_at,
                last_renewed_at=last_renewed_at,
                lease_expires_at=lease_expires_at,
                blocked_reasons=blocked_reasons,
                warning_reasons=warning_reasons,
            )

        lease_age_seconds = _lease_age_seconds(now, acquired_at, lease_required)
        seconds_until_expiry = _seconds_until_expiry(now, lease_expires_at, lease_required)
        status = _status(
            blocked_reasons=blocked_reasons,
            warning_reasons=warning_reasons,
            lease_required=lease_required,
            now=now,
            lease_expires_at=lease_expires_at,
        )
        lease_state = _lease_state(
            status=status,
            snapshot=snapshot,
            blocked_reasons=blocked_reasons,
        )
        receipt = TemporalLeaseWindowReceipt(
            receipt_id="pending",
            request_id=request.request_id,
            tenant_id=request.tenant_id,
            actor_id=request.actor_id,
            command_id=request.command_id,
            action_type=request.action_type,
            risk_level=request.risk_level,
            policy_id=request.policy.policy_id,
            scope_id=request.policy.scope_id,
            lease_id=snapshot.lease_id if snapshot else "",
            resource_id=request.resource_id if lease_required else "",
            worker_id=request.worker_id if lease_required else "",
            lease_owner_id=request.lease_owner_id if lease_required else "",
            status=status,
            lease_state=lease_state,
            runtime_now_utc=now.isoformat(),
            lease_required=lease_required,
            acquired_at=_instant_text(acquired_at),
            last_renewed_at=_instant_text(last_renewed_at),
            lease_expires_at=_instant_text(lease_expires_at),
            lease_age_seconds=lease_age_seconds,
            seconds_until_expiry=seconds_until_expiry,
            max_lease_seconds=request.policy.max_lease_seconds if lease_required else 0,
            renewal_grace_seconds=request.policy.renewal_grace_seconds if lease_required else 0,
            fencing_token=snapshot.fencing_token if snapshot else "",
            sequence=snapshot.sequence if snapshot else 0,
            released=bool(snapshot.released) if snapshot else False,
            revoked=bool(snapshot.revoked) if snapshot else False,
            blocked_reasons=_unique(blocked_reasons),
            warning_reasons=_unique(warning_reasons),
            required_controls=_unique(_required_controls_for_status(required_controls, status)),
            evidence_refs=request.evidence_refs,
            lease_evidence_refs=snapshot.evidence_refs if snapshot else [],
            source_temporal_receipt_id=request.source_temporal_receipt_id,
            source_scheduler_receipt_id=request.source_scheduler_receipt_id,
            source_retry_window_receipt_id=request.source_retry_window_receipt_id,
            source_reapproval_receipt_id=request.source_reapproval_receipt_id,
            receipt_schema_ref=TEMPORAL_LEASE_WINDOW_RECEIPT_SCHEMA_REF,
            terminal_closure_required=True,
            metadata={
                "receipt_is_not_terminal_closure": True,
                "runtime_owns_time_truth": True,
                "dispatch_allowed": status in {"lease_active", "lease_expiring", "not_required"},
                "lease_checked": lease_required,
                "lease_scope_checked": lease_required and snapshot is not None,
                "lease_expiry_checked": lease_required and snapshot is not None,
                "fencing_token_checked": lease_required and snapshot is not None,
                "renewal_required": status == "lease_expiring",
                "high_risk_source_receipts_checked": _source_receipts_checked(request),
            },
        )
        receipt_hash = canonical_hash(asdict(receipt))
        return replace(
            receipt,
            receipt_id=f"temporal-lease-window-receipt-{receipt_hash[:16]}",
            receipt_hash=receipt_hash,
        )


def _lease_required(request: LeaseWindowRequest) -> bool:
    if request.policy.requires_lease_window:
        return True
    return request.risk_level in HIGH_RISK_LEVELS and request.policy.high_risk_requires_lease_window


def _policy_violations(request: LeaseWindowRequest, lease_required: bool) -> list[str]:
    violations: list[str] = []
    if request.policy.tenant_id != request.tenant_id:
        violations.append("policy_tenant_mismatch")
    if not lease_required:
        return violations
    if not _resource_allowed(request.resource_id, request.policy.allowed_resource_patterns):
        violations.append("resource_not_allowed")
    if request.snapshot is None:
        violations.append("lease_snapshot_required")
    if not request.evidence_refs:
        violations.append("evidence_refs_required")
    if request.risk_level in HIGH_RISK_LEVELS and not request.source_temporal_receipt_id:
        violations.append("source_temporal_receipt_required_for_high_risk")
    if request.risk_level in HIGH_RISK_LEVELS and not request.source_reapproval_receipt_id:
        violations.append("source_reapproval_receipt_required_for_high_risk")
    return violations


def _apply_snapshot_rules(
    *,
    request: LeaseWindowRequest,
    now: datetime,
    acquired_at: datetime | None,
    last_renewed_at: datetime | None,
    lease_expires_at: datetime | None,
    blocked_reasons: list[str],
    warning_reasons: list[str],
) -> None:
    snapshot = request.snapshot
    if snapshot is None:
        return
    if snapshot.tenant_id != request.tenant_id:
        blocked_reasons.append("snapshot_tenant_mismatch")
    if snapshot.command_id != request.command_id:
        blocked_reasons.append("snapshot_command_mismatch")
    if snapshot.resource_id != request.resource_id:
        blocked_reasons.append("snapshot_resource_mismatch")
    if snapshot.worker_id != request.worker_id:
        blocked_reasons.append("snapshot_worker_mismatch")
    if snapshot.lease_owner_id != request.lease_owner_id:
        blocked_reasons.append("snapshot_lease_owner_mismatch")
    if not snapshot.evidence_refs:
        blocked_reasons.append("lease_evidence_refs_required")
    if not snapshot.fencing_token:
        blocked_reasons.append("fencing_token_required")
    if snapshot.sequence <= 0:
        blocked_reasons.append("fencing_sequence_positive_required")
    if snapshot.released:
        blocked_reasons.append("lease_released")
    if snapshot.revoked:
        blocked_reasons.append("lease_revoked")
    if acquired_at and acquired_at > now:
        blocked_reasons.append("lease_acquired_in_future")
    if last_renewed_at and last_renewed_at > now:
        blocked_reasons.append("lease_renewed_in_future")
    if acquired_at and last_renewed_at and last_renewed_at < acquired_at:
        blocked_reasons.append("lease_renewal_order_invalid")
    if acquired_at and lease_expires_at and lease_expires_at <= acquired_at:
        blocked_reasons.append("lease_window_invalid")
    if acquired_at and lease_expires_at:
        lease_window_seconds = int((lease_expires_at - acquired_at).total_seconds())
        if lease_window_seconds > request.policy.max_lease_seconds:
            blocked_reasons.append("lease_window_exceeds_policy")
    if acquired_at:
        lease_age_seconds = int((now - acquired_at).total_seconds())
        if lease_age_seconds > request.policy.max_lease_seconds:
            blocked_reasons.append("lease_age_exceeds_policy")
    if lease_expires_at and now < lease_expires_at:
        seconds_until_expiry = int((lease_expires_at - now).total_seconds())
        if seconds_until_expiry <= request.policy.renewal_grace_seconds:
            warning_reasons.append("lease_renewal_required")


def _resource_allowed(resource_id: str, allowed_patterns: list[str]) -> bool:
    return any(fnmatchcase(resource_id, pattern) for pattern in allowed_patterns)


def _status(
    *,
    blocked_reasons: list[str],
    warning_reasons: list[str],
    lease_required: bool,
    now: datetime,
    lease_expires_at: datetime | None,
) -> str:
    if blocked_reasons:
        return "blocked"
    if not lease_required:
        return "not_required"
    if lease_expires_at and now >= lease_expires_at:
        return "lease_expired"
    if warning_reasons:
        return "lease_expiring"
    return "lease_active"


def _lease_state(*, status: str, snapshot: LeaseSnapshot | None, blocked_reasons: list[str]) -> str:
    if status == "not_required":
        return "not_required"
    if snapshot and snapshot.released:
        return "released"
    if snapshot and snapshot.revoked:
        return "revoked"
    if any(reason.endswith("_mismatch") for reason in blocked_reasons) or "resource_not_allowed" in blocked_reasons:
        return "wrong_scope"
    if status == "lease_expired":
        return "expired"
    if status == "lease_expiring":
        return "expiring"
    if blocked_reasons:
        return "invalid"
    return "active"


def _lease_age_seconds(now: datetime, acquired_at: datetime | None, lease_required: bool) -> int:
    if not lease_required or acquired_at is None:
        return 0
    return max(0, int((now - acquired_at).total_seconds()))


def _seconds_until_expiry(now: datetime, lease_expires_at: datetime | None, lease_required: bool) -> int:
    if not lease_required or lease_expires_at is None:
        return 0
    return max(0, int((lease_expires_at - now).total_seconds()))


def _required_controls_for_status(required_controls: list[str], status: str) -> list[str]:
    if status == "lease_active":
        return [*required_controls, "lease_admission"]
    if status == "lease_expiring":
        return [*required_controls, "lease_admission", "lease_renewal_warning"]
    if status == "lease_expired":
        return [*required_controls, "lease_expiry_block"]
    if status == "blocked":
        return [*required_controls, "lease_dispatch_block"]
    return required_controls


def _source_receipts_checked(request: LeaseWindowRequest) -> bool:
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
