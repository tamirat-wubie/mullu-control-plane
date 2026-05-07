"""Gateway temporal reapproval evaluator.

Purpose: recheck approval grants at execution time before high-risk dispatch.
Governance scope: runtime-owned approval age, expiry, revocation, tenant scope,
    execution scope, approver role coverage, approval evidence refs, and
    non-terminal temporal reapproval receipts.
Dependencies: dataclasses, datetime, command-spine canonical hashing, and the
    Temporal Kernel trusted clock.
Invariants:
  - Runtime clock owns current time.
  - High-risk and critical actions require explicit approver role coverage.
  - Expired approvals cannot authorize dispatch.
  - Revoked, future-dated, out-of-scope, or wrong-tenant approvals block dispatch.
  - Approval grants without evidence refs cannot authorize dispatch.
  - Temporal reapproval receipts are not terminal closure certificates.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from datetime import datetime, timedelta, timezone
from typing import Any

from gateway.command_spine import canonical_hash
from gateway.temporal_kernel import TrustedClock


TEMPORAL_REAPPROVAL_RECEIPT_SCHEMA_REF = "urn:mullusi:schema:temporal-reapproval-receipt:1"
RISK_LEVELS = ("low", "medium", "high", "critical")
REAPPROVAL_STATUSES = ("not_required", "approved", "reapproval_required", "blocked")
APPROVAL_STATES = ("valid", "expired", "revoked", "future", "wrong_scope", "blocked")
BASE_REAPPROVAL_CONTROLS = (
    "runtime_clock",
    "approval_validity",
    "approval_scope",
    "approver_role_coverage",
    "temporal_reapproval_receipt",
    "terminal_closure",
)
HIGH_RISK_LEVELS = frozenset({"high", "critical"})
BLOCKING_APPROVAL_STATES = frozenset({"blocked", "revoked", "future", "wrong_scope"})


@dataclass(frozen=True, slots=True)
class ApprovalGrant:
    """One approval grant proposed to authorize execution."""

    approval_id: str
    tenant_id: str
    approver_id: str
    approver_role: str
    approval_scope: str
    granted_at: str
    evidence_refs: list[str]
    expires_at: str = ""
    revoked_at: str = ""
    source_event_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in (
            "approval_id",
            "tenant_id",
            "approver_id",
            "approver_role",
            "approval_scope",
            "granted_at",
        ):
            value = str(getattr(self, field_name)).strip()
            if not value:
                raise ValueError(f"{field_name}_required")
            object.__setattr__(self, field_name, value)
        object.__setattr__(self, "evidence_refs", _normalize_list(self.evidence_refs))
        object.__setattr__(self, "expires_at", str(self.expires_at).strip())
        object.__setattr__(self, "revoked_at", str(self.revoked_at).strip())
        object.__setattr__(self, "source_event_id", str(self.source_event_id).strip())
        object.__setattr__(self, "metadata", dict(self.metadata))


@dataclass(frozen=True, slots=True)
class ReapprovalRequest:
    """One execution-time approval recheck request."""

    request_id: str
    tenant_id: str
    actor_id: str
    command_id: str
    action_type: str
    risk_level: str
    execution_scope: str
    required_approver_roles: list[str]
    minimum_approval_count: int
    approval_grants: list[ApprovalGrant]
    max_approval_age_seconds: int
    reapproval_window_seconds: int = 0
    source_schedule_receipt_id: str = ""
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
            "execution_scope",
        ):
            value = str(getattr(self, field_name)).strip()
            if not value:
                raise ValueError(f"{field_name}_required")
            object.__setattr__(self, field_name, value)
        if self.risk_level not in RISK_LEVELS:
            raise ValueError("risk_level_invalid")
        if self.minimum_approval_count < 0:
            raise ValueError("minimum_approval_count_nonnegative_required")
        if self.max_approval_age_seconds < 0:
            raise ValueError("max_approval_age_seconds_nonnegative_required")
        if self.reapproval_window_seconds < 0:
            raise ValueError("reapproval_window_seconds_nonnegative_required")
        object.__setattr__(self, "required_approver_roles", _normalize_list(self.required_approver_roles))
        object.__setattr__(self, "approval_grants", list(self.approval_grants))
        object.__setattr__(self, "source_schedule_receipt_id", str(self.source_schedule_receipt_id).strip())
        object.__setattr__(self, "source_temporal_receipt_id", str(self.source_temporal_receipt_id).strip())
        object.__setattr__(self, "metadata", dict(self.metadata))


@dataclass(frozen=True, slots=True)
class ApprovalGrantState:
    """Computed execution-time validity for one approval grant."""

    approval_id: str
    approver_id: str
    approver_role: str
    status: str
    granted_at: str
    expires_at: str
    age_seconds: int
    seconds_until_expiry: int
    reasons: list[str]

    def __post_init__(self) -> None:
        if self.status not in APPROVAL_STATES:
            raise ValueError("approval_state_invalid")
        if self.age_seconds < 0 or self.seconds_until_expiry < 0:
            raise ValueError("approval_state_seconds_nonnegative_required")
        object.__setattr__(self, "reasons", _normalize_list(self.reasons))


@dataclass(frozen=True, slots=True)
class TemporalReapprovalReceipt:
    """Schema-backed non-terminal receipt for execution-time reapproval."""

    receipt_id: str
    request_id: str
    tenant_id: str
    actor_id: str
    command_id: str
    action_type: str
    risk_level: str
    status: str
    execution_scope: str
    required_approver_roles: list[str]
    minimum_approval_count: int
    approval_ids: list[str]
    valid_approval_ids: list[str]
    expired_approval_ids: list[str]
    revoked_approval_ids: list[str]
    future_approval_ids: list[str]
    blocked_approval_ids: list[str]
    missing_approver_roles: list[str]
    approved_role_count: int
    valid_approval_count: int
    reapproval_reasons: list[str]
    blocked_reasons: list[str]
    required_controls: list[str]
    approval_states: list[ApprovalGrantState]
    runtime_now_utc: str
    earliest_approval_expiry_at: str
    reapproval_due_at: str
    max_approval_age_seconds: int
    reapproval_window_seconds: int
    source_schedule_receipt_id: str
    source_temporal_receipt_id: str
    receipt_schema_ref: str
    terminal_closure_required: bool
    receipt_hash: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.status not in REAPPROVAL_STATUSES:
            raise ValueError("temporal_reapproval_status_invalid")
        if self.minimum_approval_count < 0:
            raise ValueError("minimum_approval_count_nonnegative_required")
        if self.max_approval_age_seconds < 0 or self.reapproval_window_seconds < 0:
            raise ValueError("temporal_reapproval_seconds_nonnegative_required")
        if self.approved_role_count < 0 or self.valid_approval_count < 0:
            raise ValueError("approval_count_nonnegative_required")
        object.__setattr__(self, "required_approver_roles", _normalize_list(self.required_approver_roles))
        object.__setattr__(self, "approval_ids", _normalize_list(self.approval_ids))
        object.__setattr__(self, "valid_approval_ids", _normalize_list(self.valid_approval_ids))
        object.__setattr__(self, "expired_approval_ids", _normalize_list(self.expired_approval_ids))
        object.__setattr__(self, "revoked_approval_ids", _normalize_list(self.revoked_approval_ids))
        object.__setattr__(self, "future_approval_ids", _normalize_list(self.future_approval_ids))
        object.__setattr__(self, "blocked_approval_ids", _normalize_list(self.blocked_approval_ids))
        object.__setattr__(self, "missing_approver_roles", _normalize_list(self.missing_approver_roles))
        object.__setattr__(self, "reapproval_reasons", _normalize_list(self.reapproval_reasons))
        object.__setattr__(self, "blocked_reasons", _normalize_list(self.blocked_reasons))
        object.__setattr__(self, "required_controls", _normalize_list(self.required_controls))
        object.__setattr__(self, "approval_states", list(self.approval_states))
        object.__setattr__(self, "metadata", dict(self.metadata))


class TemporalReapproval:
    """Deterministic execution-time approval grant evaluator."""

    def __init__(self, clock: TrustedClock | None = None) -> None:
        self._clock = clock or TrustedClock()

    def evaluate(self, request: ReapprovalRequest) -> TemporalReapprovalReceipt:
        """Return whether approval grants still authorize dispatch now."""
        now = _parse_required_instant(self._clock.now_utc())
        required_controls = [*BASE_REAPPROVAL_CONTROLS]
        blocked_reasons = _configuration_blockers(request)
        if request.risk_level in HIGH_RISK_LEVELS:
            required_controls.append("high_risk_runtime_reapproval")
        if request.source_schedule_receipt_id:
            required_controls.append("source_schedule_receipt")
        if request.source_temporal_receipt_id:
            required_controls.append("source_temporal_receipt")
        if request.max_approval_age_seconds > 0:
            required_controls.append("approval_age_window")

        states = [_evaluate_grant(grant, request=request, now=now) for grant in request.approval_grants]
        blocked_reasons.extend(_state_blockers(states))
        reapproval_reasons = _reapproval_reasons(request, states)
        coverage = _role_coverage(request.required_approver_roles, states)
        valid_ids = [state.approval_id for state in states if state.status == "valid"]
        expired_ids = [state.approval_id for state in states if state.status == "expired"]
        revoked_ids = [state.approval_id for state in states if state.status == "revoked"]
        future_ids = [state.approval_id for state in states if state.status == "future"]
        blocked_ids = [state.approval_id for state in states if state.status in {"blocked", "wrong_scope"}]
        missing_roles = coverage["missing_approver_roles"]
        if missing_roles:
            reapproval_reasons.extend(f"missing_approver_role:{role}" for role in missing_roles)
        if len(valid_ids) < request.minimum_approval_count:
            reapproval_reasons.append("minimum_approval_count_not_met")
        if not request.approval_grants and request.risk_level in HIGH_RISK_LEVELS:
            reapproval_reasons.append("approval_grants_required")

        status = _status(request, blocked_reasons, reapproval_reasons)
        if status not in {"approved", "not_required"}:
            required_controls.append("dispatch_block")
        if status == "reapproval_required":
            required_controls.append("fresh_approval_required")
        earliest_expiry = _earliest_approval_expiry(states)
        reapproval_due_at = ""
        if status == "reapproval_required" and request.reapproval_window_seconds > 0:
            reapproval_due_at = (now + timedelta(seconds=request.reapproval_window_seconds)).isoformat()

        receipt = TemporalReapprovalReceipt(
            receipt_id="pending",
            request_id=request.request_id,
            tenant_id=request.tenant_id,
            actor_id=request.actor_id,
            command_id=request.command_id,
            action_type=request.action_type,
            risk_level=request.risk_level,
            status=status,
            execution_scope=request.execution_scope,
            required_approver_roles=request.required_approver_roles,
            minimum_approval_count=request.minimum_approval_count,
            approval_ids=[grant.approval_id for grant in request.approval_grants],
            valid_approval_ids=valid_ids,
            expired_approval_ids=expired_ids,
            revoked_approval_ids=revoked_ids,
            future_approval_ids=future_ids,
            blocked_approval_ids=blocked_ids,
            missing_approver_roles=missing_roles,
            approved_role_count=coverage["approved_role_count"],
            valid_approval_count=len(valid_ids),
            reapproval_reasons=_unique(reapproval_reasons),
            blocked_reasons=_unique(blocked_reasons),
            required_controls=_unique(required_controls),
            approval_states=states,
            runtime_now_utc=now.isoformat(),
            earliest_approval_expiry_at=earliest_expiry,
            reapproval_due_at=reapproval_due_at,
            max_approval_age_seconds=request.max_approval_age_seconds,
            reapproval_window_seconds=request.reapproval_window_seconds,
            source_schedule_receipt_id=request.source_schedule_receipt_id,
            source_temporal_receipt_id=request.source_temporal_receipt_id,
            receipt_schema_ref=TEMPORAL_REAPPROVAL_RECEIPT_SCHEMA_REF,
            terminal_closure_required=True,
            metadata={
                "receipt_is_not_terminal_closure": True,
                "runtime_owns_time_truth": True,
                "dispatch_allowed": status in {"approved", "not_required"},
                "reapproval_required": status == "reapproval_required",
                "high_risk_reapproval_checked": request.risk_level in HIGH_RISK_LEVELS,
                "source_schedule_bound": bool(request.source_schedule_receipt_id),
                "approval_state_count": len(states),
            },
        )
        receipt_hash = canonical_hash(asdict(receipt))
        return replace(
            receipt,
            receipt_id=f"temporal-reapproval-receipt-{receipt_hash[:16]}",
            receipt_hash=receipt_hash,
        )


def _configuration_blockers(request: ReapprovalRequest) -> list[str]:
    blockers: list[str] = []
    if request.risk_level in HIGH_RISK_LEVELS and not request.required_approver_roles:
        blockers.append("required_approver_roles_required_for_high_risk")
    if request.risk_level in HIGH_RISK_LEVELS and request.minimum_approval_count <= 0:
        blockers.append("minimum_approval_count_required_for_high_risk")
    if request.minimum_approval_count > 0 and not request.required_approver_roles:
        blockers.append("required_approver_roles_required")
    return blockers


def _evaluate_grant(grant: ApprovalGrant, *, request: ReapprovalRequest, now: datetime) -> ApprovalGrantState:
    reasons: list[str] = []
    granted_at = _parse_optional_instant(grant.granted_at, reasons, "granted_at_invalid")
    expires_at = _parse_optional_instant(grant.expires_at, reasons, "expires_at_invalid")
    revoked_at = _parse_optional_instant(grant.revoked_at, reasons, "revoked_at_invalid")

    if grant.tenant_id != request.tenant_id:
        reasons.append("approval_tenant_mismatch")
    if grant.approval_scope not in {request.execution_scope, "*"}:
        reasons.append("approval_scope_mismatch")
    if granted_at is None:
        reasons.append("granted_at_required")
    if not grant.expires_at:
        reasons.append("expires_at_required")
    if expires_at is None:
        reasons.append("approval_expiry_required")
    if not grant.evidence_refs:
        reasons.append("approval_evidence_refs_required")
    if revoked_at and now >= revoked_at:
        reasons.append("approval_revoked")
    if granted_at and now < granted_at:
        reasons.append("approval_granted_in_future")
    if expires_at and now > expires_at:
        reasons.append("approval_expired")
    if granted_at and request.max_approval_age_seconds > 0:
        age_seconds = int((now - granted_at).total_seconds())
        if age_seconds > request.max_approval_age_seconds:
            reasons.append("approval_age_exceeds_max_seconds")

    status = _grant_status(reasons)
    return ApprovalGrantState(
        approval_id=grant.approval_id,
        approver_id=grant.approver_id,
        approver_role=grant.approver_role,
        status=status,
        granted_at=granted_at.isoformat() if granted_at else grant.granted_at,
        expires_at=expires_at.isoformat() if expires_at else grant.expires_at,
        age_seconds=_age_seconds(now, granted_at),
        seconds_until_expiry=_remaining_seconds(now, expires_at),
        reasons=_unique(reasons),
    )


def _grant_status(reasons: list[str]) -> str:
    if "approval_scope_mismatch" in reasons:
        return "wrong_scope"
    if "approval_revoked" in reasons:
        return "revoked"
    if "approval_granted_in_future" in reasons:
        return "future"
    if "approval_expired" in reasons or "approval_age_exceeds_max_seconds" in reasons:
        return "expired"
    if any(reason in _BLOCKING_APPROVAL_REASONS or reason.endswith("_invalid") for reason in reasons):
        return "blocked"
    return "valid"


_BLOCKING_APPROVAL_REASONS = frozenset(
    {
        "approval_tenant_mismatch",
        "granted_at_required",
        "expires_at_required",
        "approval_expiry_required",
        "approval_evidence_refs_required",
    }
)


def _state_blockers(states: list[ApprovalGrantState]) -> list[str]:
    return [
        f"{state.approval_id}:{reason}"
        for state in states
        if state.status in BLOCKING_APPROVAL_STATES
        for reason in state.reasons
    ]


def _reapproval_reasons(request: ReapprovalRequest, states: list[ApprovalGrantState]) -> list[str]:
    reasons: list[str] = []
    for state in states:
        if state.status == "expired":
            reasons.extend(f"{state.approval_id}:{reason}" for reason in state.reasons)
    if states and not any(state.status == "valid" for state in states):
        reasons.append("no_valid_approval_grants")
    if request.risk_level in HIGH_RISK_LEVELS and not request.source_schedule_receipt_id:
        reasons.append("source_schedule_receipt_required_for_high_risk")
    return reasons


def _role_coverage(required_roles: list[str], states: list[ApprovalGrantState]) -> dict[str, Any]:
    valid_roles = {state.approver_role for state in states if state.status == "valid"}
    missing_roles = [role for role in required_roles if role not in valid_roles]
    return {
        "missing_approver_roles": missing_roles,
        "approved_role_count": len(valid_roles.intersection(required_roles)),
    }


def _status(
    request: ReapprovalRequest,
    blocked_reasons: list[str],
    reapproval_reasons: list[str],
) -> str:
    if (
        request.risk_level not in HIGH_RISK_LEVELS
        and not request.required_approver_roles
        and request.minimum_approval_count == 0
        and not request.approval_grants
        and not blocked_reasons
    ):
        return "not_required"
    if blocked_reasons:
        return "blocked"
    if reapproval_reasons:
        return "reapproval_required"
    return "approved"


def _earliest_approval_expiry(states: list[ApprovalGrantState]) -> str:
    expiries = [
        _parse_required_instant(state.expires_at)
        for state in states
        if state.status == "valid" and state.expires_at
    ]
    if not expiries:
        return ""
    return min(expiries).isoformat()


def _age_seconds(now: datetime, granted_at: datetime | None) -> int:
    if granted_at is None or now < granted_at:
        return 0
    return int((now - granted_at).total_seconds())


def _remaining_seconds(now: datetime, expires_at: datetime | None) -> int:
    if expires_at is None or now > expires_at:
        return 0
    return int((expires_at - now).total_seconds())


def _parse_optional_instant(value: str, reasons: list[str], reason: str) -> datetime | None:
    if not value:
        return None
    try:
        return _parse_required_instant(value)
    except ValueError:
        reasons.append(reason)
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


def _normalize_list(values: list[str] | tuple[str, ...]) -> list[str]:
    return [str(value).strip() for value in values if str(value).strip()]


def _unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))
