"""Gateway temporal accepted-risk expiry evaluator.

Purpose: prove an accepted-risk record is still active, scoped, and unexpired
    before governed dispatch or reuse.
Governance scope: runtime-owned expiry checks, accepted-risk lifecycle state,
    tenant and command scope, owner and review obligation, evidence refs,
    high-risk source receipt binding, and non-terminal temporal receipts.
Dependencies: dataclasses, datetime, command-spine canonical hashing, and the
    Temporal Kernel trusted clock.
Invariants:
  - Runtime clock owns accepted-risk expiry truth.
  - Accepted risk cannot authorize dispatch after expiry.
  - Revoked, closed, future-dated, wrong-scope, or wrong-tenant records fail closed.
  - Accepted risk requires owner, approver, case, review obligation, and evidence.
  - High-risk dispatch binds source temporal and causal-order receipts.
  - Temporal accepted-risk expiry receipts are not terminal closure certificates.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from datetime import datetime, timezone
from typing import Any

from gateway.command_spine import canonical_hash
from gateway.temporal_kernel import TrustedClock


TEMPORAL_ACCEPTED_RISK_EXPIRY_RECEIPT_SCHEMA_REF = (
    "urn:mullusi:schema:temporal-accepted-risk-expiry-receipt:1"
)
RISK_LEVELS = ("low", "medium", "high", "critical")
ACCEPTED_RISK_SCOPES = (
    "effect_reconciliation",
    "verification_gap",
    "provider_uncertainty",
    "operational_limitation",
)
ACCEPTED_RISK_DISPOSITIONS = ("active", "expired", "revoked", "closed")
ACCEPTED_RISK_STATUSES = ("risk_active", "expired", "blocked", "not_required")
ACCEPTED_RISK_STATES = (
    "active",
    "expired",
    "revoked",
    "closed",
    "future",
    "wrong_scope",
    "invalid",
    "not_required",
)
HIGH_RISK_LEVELS = frozenset({"high", "critical"})
BASE_ACCEPTED_RISK_CONTROLS = (
    "runtime_clock",
    "accepted_risk_expiry",
    "accepted_risk_scope",
    "accepted_risk_lifecycle",
    "review_obligation",
    "evidence_reference",
    "temporal_accepted_risk_expiry_receipt",
    "terminal_closure",
)


@dataclass(frozen=True, slots=True)
class AcceptedRiskGrant:
    """One accepted-risk record proposed as dispatch authorization."""

    risk_id: str
    tenant_id: str
    command_id: str
    action_type: str
    scope: str
    disposition: str
    accepted_at: str
    expires_at: str
    case_id: str
    owner_id: str
    accepted_by: str
    review_obligation_id: str
    evidence_refs: list[str]
    execution_id: str = ""
    reconciliation_id: str = ""
    source_terminal_closure_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in (
            "risk_id",
            "tenant_id",
            "command_id",
            "action_type",
            "scope",
            "disposition",
            "accepted_at",
            "expires_at",
            "case_id",
            "owner_id",
            "accepted_by",
            "review_obligation_id",
        ):
            value = str(getattr(self, field_name)).strip()
            if not value:
                raise ValueError(f"{field_name}_required")
            object.__setattr__(self, field_name, value)
        if self.scope not in ACCEPTED_RISK_SCOPES:
            raise ValueError("accepted_risk_scope_invalid")
        if self.disposition not in ACCEPTED_RISK_DISPOSITIONS:
            raise ValueError("accepted_risk_disposition_invalid")
        object.__setattr__(self, "evidence_refs", _normalize_list(self.evidence_refs))
        object.__setattr__(self, "execution_id", str(self.execution_id).strip())
        object.__setattr__(self, "reconciliation_id", str(self.reconciliation_id).strip())
        object.__setattr__(self, "source_terminal_closure_id", str(self.source_terminal_closure_id).strip())
        object.__setattr__(self, "metadata", dict(self.metadata))


@dataclass(frozen=True, slots=True)
class TemporalAcceptedRiskPolicy:
    """Tenant policy defining accepted-risk reuse boundaries."""

    policy_id: str
    tenant_id: str
    allowed_scopes: list[str]
    allowed_action_types: list[str] = field(default_factory=list)
    max_acceptance_age_seconds: int = 0
    requires_accepted_risk_check: bool = True
    high_risk_requires_accepted_risk_check: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in ("policy_id", "tenant_id"):
            value = str(getattr(self, field_name)).strip()
            if not value:
                raise ValueError(f"{field_name}_required")
            object.__setattr__(self, field_name, value)
        allowed_scopes = _normalize_list(self.allowed_scopes)
        for scope in allowed_scopes:
            if scope not in ACCEPTED_RISK_SCOPES:
                raise ValueError("accepted_risk_scope_invalid")
        if self.max_acceptance_age_seconds < 0:
            raise ValueError("max_acceptance_age_seconds_nonnegative_required")
        object.__setattr__(self, "allowed_scopes", allowed_scopes)
        object.__setattr__(self, "allowed_action_types", _normalize_list(self.allowed_action_types))
        object.__setattr__(self, "metadata", dict(self.metadata))


@dataclass(frozen=True, slots=True)
class TemporalAcceptedRiskRequest:
    """One request to recheck accepted-risk expiry before dispatch."""

    request_id: str
    tenant_id: str
    actor_id: str
    command_id: str
    action_type: str
    risk_level: str
    policy: TemporalAcceptedRiskPolicy
    evidence_refs: list[str]
    accepted_risk: AcceptedRiskGrant | None = None
    source_temporal_receipt_id: str = ""
    source_causal_order_receipt_id: str = ""
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
            "source_causal_order_receipt_id",
            str(self.source_causal_order_receipt_id).strip(),
        )
        object.__setattr__(self, "source_reapproval_receipt_id", str(self.source_reapproval_receipt_id).strip())
        object.__setattr__(self, "metadata", dict(self.metadata))


@dataclass(frozen=True, slots=True)
class TemporalAcceptedRiskExpiryReceipt:
    """Schema-backed non-terminal receipt for accepted-risk expiry checks."""

    receipt_id: str
    request_id: str
    tenant_id: str
    actor_id: str
    command_id: str
    action_type: str
    risk_level: str
    policy_id: str
    status: str
    risk_state: str
    runtime_now_utc: str
    accepted_risk_required: bool
    risk_id: str
    scope: str
    disposition: str
    accepted_at: str
    expires_at: str
    seconds_until_expiry: int
    accepted_age_seconds: int
    case_id: str
    owner_id: str
    accepted_by: str
    review_obligation_id: str
    allowed_scopes: list[str]
    allowed_action_types: list[str]
    blocked_reasons: list[str]
    warning_reasons: list[str]
    required_controls: list[str]
    evidence_refs: list[str]
    accepted_risk_evidence_refs: list[str]
    source_terminal_closure_id: str
    source_temporal_receipt_id: str
    source_causal_order_receipt_id: str
    source_reapproval_receipt_id: str
    receipt_schema_ref: str
    terminal_closure_required: bool
    receipt_hash: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.status not in ACCEPTED_RISK_STATUSES:
            raise ValueError("temporal_accepted_risk_status_invalid")
        if self.risk_state not in ACCEPTED_RISK_STATES:
            raise ValueError("temporal_accepted_risk_state_invalid")
        if self.seconds_until_expiry < 0 or self.accepted_age_seconds < 0:
            raise ValueError("accepted_risk_seconds_nonnegative_required")
        object.__setattr__(self, "allowed_scopes", _normalize_list(self.allowed_scopes))
        object.__setattr__(self, "allowed_action_types", _normalize_list(self.allowed_action_types))
        object.__setattr__(self, "blocked_reasons", _normalize_list(self.blocked_reasons))
        object.__setattr__(self, "warning_reasons", _normalize_list(self.warning_reasons))
        object.__setattr__(self, "required_controls", _normalize_list(self.required_controls))
        object.__setattr__(self, "evidence_refs", _normalize_list(self.evidence_refs))
        object.__setattr__(self, "accepted_risk_evidence_refs", _normalize_list(self.accepted_risk_evidence_refs))
        object.__setattr__(self, "metadata", dict(self.metadata))


class TemporalAcceptedRiskExpiry:
    """Deterministic runtime accepted-risk expiry evaluator."""

    def __init__(self, clock: TrustedClock | None = None) -> None:
        self._clock = clock or TrustedClock()

    def evaluate(self, request: TemporalAcceptedRiskRequest) -> TemporalAcceptedRiskExpiryReceipt:
        """Return whether an accepted-risk record may still authorize dispatch."""
        now = _parse_required_instant(self._clock.now_utc())
        accepted_risk_required = _accepted_risk_required(request)
        blocked_reasons: list[str] = []
        warning_reasons: list[str] = []
        required_controls = [*BASE_ACCEPTED_RISK_CONTROLS]

        if accepted_risk_required:
            required_controls.append("accepted_risk_policy")
        if request.risk_level in HIGH_RISK_LEVELS:
            required_controls.append("high_risk_accepted_risk")
        if request.source_temporal_receipt_id:
            required_controls.append("source_temporal_receipt")
        if request.source_causal_order_receipt_id:
            required_controls.append("source_causal_order_receipt")
        if request.source_reapproval_receipt_id:
            required_controls.append("source_reapproval_receipt")

        blocked_reasons.extend(_policy_violations(request, accepted_risk_required))
        risk = request.accepted_risk
        parsed_accepted_at: datetime | None = None
        parsed_expires_at: datetime | None = None
        if risk is not None:
            parsed_accepted_at = _parse_optional_instant(
                risk.accepted_at,
                blocked_reasons,
                "accepted_at_invalid",
            )
            parsed_expires_at = _parse_optional_instant(
                risk.expires_at,
                blocked_reasons,
                "expires_at_invalid",
            )
            _apply_risk_record_rules(
                request=request,
                now=now,
                accepted_at=parsed_accepted_at,
                expires_at=parsed_expires_at,
                blocked_reasons=blocked_reasons,
                warning_reasons=warning_reasons,
            )

        seconds_until_expiry = _seconds_until_expiry(now, parsed_expires_at)
        accepted_age_seconds = _accepted_age_seconds(now, parsed_accepted_at)
        status = _status(blocked_reasons, accepted_risk_required)
        risk_state = _risk_state(request.accepted_risk, blocked_reasons, status)
        receipt = TemporalAcceptedRiskExpiryReceipt(
            receipt_id="pending",
            request_id=request.request_id,
            tenant_id=request.tenant_id,
            actor_id=request.actor_id,
            command_id=request.command_id,
            action_type=request.action_type,
            risk_level=request.risk_level,
            policy_id=request.policy.policy_id,
            status=status,
            risk_state=risk_state,
            runtime_now_utc=now.isoformat(),
            accepted_risk_required=accepted_risk_required,
            risk_id=risk.risk_id if risk else "",
            scope=risk.scope if risk else "",
            disposition=risk.disposition if risk else "",
            accepted_at=_instant_text(parsed_accepted_at, risk.accepted_at if risk else ""),
            expires_at=_instant_text(parsed_expires_at, risk.expires_at if risk else ""),
            seconds_until_expiry=seconds_until_expiry,
            accepted_age_seconds=accepted_age_seconds,
            case_id=risk.case_id if risk else "",
            owner_id=risk.owner_id if risk else "",
            accepted_by=risk.accepted_by if risk else "",
            review_obligation_id=risk.review_obligation_id if risk else "",
            allowed_scopes=request.policy.allowed_scopes,
            allowed_action_types=request.policy.allowed_action_types,
            blocked_reasons=_unique(blocked_reasons),
            warning_reasons=_unique(warning_reasons),
            required_controls=_unique(
                required_controls
                if status in {"risk_active", "not_required"}
                else [*required_controls, "accepted_risk_dispatch_block"]
            ),
            evidence_refs=request.evidence_refs,
            accepted_risk_evidence_refs=risk.evidence_refs if risk else [],
            source_terminal_closure_id=risk.source_terminal_closure_id if risk else "",
            source_temporal_receipt_id=request.source_temporal_receipt_id,
            source_causal_order_receipt_id=request.source_causal_order_receipt_id,
            source_reapproval_receipt_id=request.source_reapproval_receipt_id,
            receipt_schema_ref=TEMPORAL_ACCEPTED_RISK_EXPIRY_RECEIPT_SCHEMA_REF,
            terminal_closure_required=True,
            metadata={
                "receipt_is_not_terminal_closure": True,
                "runtime_owns_time_truth": True,
                "dispatch_allowed": status in {"risk_active", "not_required"},
                "accepted_risk_checked": accepted_risk_required,
                "expiry_checked": accepted_risk_required and risk is not None,
                "scope_checked": accepted_risk_required and risk is not None,
                "review_obligation_checked": accepted_risk_required and risk is not None,
                "high_risk_accepted_risk_checked": request.risk_level in HIGH_RISK_LEVELS,
                "source_receipts_checked": _source_receipts_checked(request),
            },
        )
        receipt_hash = canonical_hash(asdict(receipt))
        return replace(
            receipt,
            receipt_id=f"temporal-accepted-risk-expiry-receipt-{receipt_hash[:16]}",
            receipt_hash=receipt_hash,
        )


def _accepted_risk_required(request: TemporalAcceptedRiskRequest) -> bool:
    if request.policy.requires_accepted_risk_check:
        return True
    return request.risk_level in HIGH_RISK_LEVELS and request.policy.high_risk_requires_accepted_risk_check


def _policy_violations(request: TemporalAcceptedRiskRequest, accepted_risk_required: bool) -> list[str]:
    violations: list[str] = []
    if request.policy.tenant_id != request.tenant_id:
        violations.append("policy_tenant_mismatch")
    if not accepted_risk_required:
        return violations
    if not request.policy.allowed_scopes:
        violations.append("allowed_scopes_required")
    if request.accepted_risk is None:
        violations.append("accepted_risk_required")
    if not request.evidence_refs:
        violations.append("evidence_refs_required")
    if request.risk_level in HIGH_RISK_LEVELS and not request.source_temporal_receipt_id:
        violations.append("source_temporal_receipt_required_for_high_risk")
    if request.risk_level in HIGH_RISK_LEVELS and not request.source_causal_order_receipt_id:
        violations.append("source_causal_order_receipt_required_for_high_risk")
    return violations


def _apply_risk_record_rules(
    *,
    request: TemporalAcceptedRiskRequest,
    now: datetime,
    accepted_at: datetime | None,
    expires_at: datetime | None,
    blocked_reasons: list[str],
    warning_reasons: list[str],
) -> None:
    risk = request.accepted_risk
    if risk is None:
        return
    if risk.tenant_id != request.tenant_id:
        blocked_reasons.append("accepted_risk_tenant_mismatch")
    if risk.command_id != request.command_id:
        blocked_reasons.append("accepted_risk_command_mismatch")
    if risk.action_type != request.action_type:
        blocked_reasons.append("accepted_risk_action_type_mismatch")
    if risk.scope not in request.policy.allowed_scopes:
        blocked_reasons.append("accepted_risk_scope_not_allowed")
    if request.policy.allowed_action_types and request.action_type not in request.policy.allowed_action_types:
        blocked_reasons.append("accepted_risk_action_type_not_allowed")
    if risk.disposition != "active":
        blocked_reasons.append(f"accepted_risk_{risk.disposition}")
    if accepted_at and accepted_at > now:
        blocked_reasons.append("accepted_risk_future")
    if expires_at and expires_at <= now:
        blocked_reasons.append("accepted_risk_expired")
    if request.policy.max_acceptance_age_seconds and accepted_at:
        age_seconds = _accepted_age_seconds(now, accepted_at)
        if age_seconds > request.policy.max_acceptance_age_seconds:
            blocked_reasons.append("accepted_risk_too_old")
    if not risk.case_id:
        blocked_reasons.append("case_id_required")
    if not risk.owner_id:
        blocked_reasons.append("owner_id_required")
    if not risk.accepted_by:
        blocked_reasons.append("accepted_by_required")
    if not risk.review_obligation_id:
        blocked_reasons.append("review_obligation_required")
    if not risk.evidence_refs:
        blocked_reasons.append("accepted_risk_evidence_refs_required")
    if request.risk_level in HIGH_RISK_LEVELS and not risk.source_terminal_closure_id:
        blocked_reasons.append("source_terminal_closure_required_for_high_risk")
    if expires_at and expires_at > now and (expires_at - now).total_seconds() <= 900:
        warning_reasons.append("accepted_risk_expiry_near")


def _status(blocked_reasons: list[str], accepted_risk_required: bool) -> str:
    if not accepted_risk_required:
        return "not_required"
    if "accepted_risk_expired" in blocked_reasons:
        return "expired"
    if blocked_reasons:
        return "blocked"
    return "risk_active"


def _risk_state(risk: AcceptedRiskGrant | None, blocked_reasons: list[str], status: str) -> str:
    if status == "not_required":
        return "not_required"
    if risk is None:
        return "invalid"
    if "accepted_risk_expired" in blocked_reasons or risk.disposition == "expired":
        return "expired"
    if risk.disposition == "revoked":
        return "revoked"
    if risk.disposition == "closed":
        return "closed"
    if "accepted_risk_future" in blocked_reasons:
        return "future"
    if "accepted_risk_scope_not_allowed" in blocked_reasons or "accepted_risk_action_type_not_allowed" in blocked_reasons:
        return "wrong_scope"
    if blocked_reasons:
        return "invalid"
    return "active"


def _source_receipts_checked(request: TemporalAcceptedRiskRequest) -> bool:
    if request.risk_level not in HIGH_RISK_LEVELS:
        return False
    return all(
        (
            request.source_temporal_receipt_id,
            request.source_causal_order_receipt_id,
            request.accepted_risk and request.accepted_risk.source_terminal_closure_id,
        )
    )


def _seconds_until_expiry(now: datetime, expires_at: datetime | None) -> int:
    if expires_at is None:
        return 0
    return max(0, int((expires_at - now).total_seconds()))


def _accepted_age_seconds(now: datetime, accepted_at: datetime | None) -> int:
    if accepted_at is None:
        return 0
    return max(0, int((now - accepted_at).total_seconds()))


def _parse_optional_instant(value: str, violations: list[str], reason: str) -> datetime | None:
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


def _instant_text(value: datetime | None, fallback: str) -> str:
    return value.isoformat() if value else fallback


def _normalize_list(values: list[str] | tuple[str, ...]) -> list[str]:
    return [str(value).strip() for value in values if str(value).strip()]


def _unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))
