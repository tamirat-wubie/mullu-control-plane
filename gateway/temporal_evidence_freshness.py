"""Gateway temporal evidence freshness evaluator.

Purpose: recheck evidence freshness before governed dispatch and emit a
    schema-backed receipt that explains accepted, stale, missing, expiring,
    revoked, and blocked evidence.
Governance scope: runtime-owned evidence age, freshness windows, tenant scope,
    required evidence coverage, high-risk verification, refresh deadlines, and
    non-terminal evidence freshness receipts.
Dependencies: dataclasses, datetime, command-spine canonical hashing, and the
    Temporal Kernel trusted clock.
Invariants:
  - Runtime clock owns current time.
  - Required evidence coverage is type-based and explicit.
  - Evidence without a valid freshness window cannot authorize dispatch.
  - Stale required evidence creates refresh work instead of silent execution.
  - Missing required evidence blocks dispatch as insufficient evidence.
  - Revoked, out-of-scope, or unverified high-risk evidence blocks dispatch.
  - Temporal evidence freshness receipts are not terminal closure certificates.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from datetime import datetime, timedelta, timezone
from typing import Any

from gateway.command_spine import canonical_hash
from gateway.temporal_kernel import TrustedClock


TEMPORAL_EVIDENCE_FRESHNESS_RECEIPT_SCHEMA_REF = "urn:mullusi:schema:temporal-evidence-freshness-receipt:1"
RISK_LEVELS = ("low", "medium", "high", "critical")
EVIDENCE_STATES = ("fresh", "expiring_soon", "stale", "blocked")
EVIDENCE_FRESHNESS_STATUSES = ("fresh", "refresh_required", "insufficient_evidence", "blocked")
BASE_EVIDENCE_FRESHNESS_CONTROLS = (
    "runtime_clock",
    "evidence_freshness",
    "required_evidence_coverage",
    "tenant_scope",
    "temporal_evidence_freshness_receipt",
    "terminal_closure",
)


@dataclass(frozen=True, slots=True)
class EvidenceFreshnessClaim:
    """One evidence artifact proposed to support dispatch."""

    evidence_ref: str
    evidence_type: str
    tenant_id: str
    observed_at: str
    source_event_id: str
    freshness_seconds: int = 0
    fresh_until: str = ""
    verified: bool = True
    revoked_at: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in ("evidence_ref", "evidence_type", "tenant_id", "observed_at", "source_event_id"):
            value = str(getattr(self, field_name)).strip()
            if not value:
                raise ValueError(f"{field_name}_required")
            object.__setattr__(self, field_name, value)
        if self.freshness_seconds < 0:
            raise ValueError("freshness_seconds_nonnegative_required")
        object.__setattr__(self, "fresh_until", str(self.fresh_until).strip())
        object.__setattr__(self, "revoked_at", str(self.revoked_at).strip())
        object.__setattr__(self, "metadata", dict(self.metadata))


@dataclass(frozen=True, slots=True)
class EvidenceFreshnessRequest:
    """One request to recheck evidence before governed dispatch."""

    request_id: str
    tenant_id: str
    actor_id: str
    command_id: str
    action_type: str
    risk_level: str
    required_evidence_types: list[str]
    evidence_claims: list[EvidenceFreshnessClaim]
    refresh_window_seconds: int
    expiry_warning_seconds: int = 0
    source_temporal_receipt_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in ("request_id", "tenant_id", "actor_id", "command_id", "action_type", "risk_level"):
            value = str(getattr(self, field_name)).strip()
            if not value:
                raise ValueError(f"{field_name}_required")
            object.__setattr__(self, field_name, value)
        if self.risk_level not in RISK_LEVELS:
            raise ValueError("risk_level_invalid")
        if self.refresh_window_seconds < 0:
            raise ValueError("refresh_window_seconds_nonnegative_required")
        if self.expiry_warning_seconds < 0:
            raise ValueError("expiry_warning_seconds_nonnegative_required")
        object.__setattr__(self, "required_evidence_types", _normalize_list(self.required_evidence_types))
        object.__setattr__(self, "evidence_claims", list(self.evidence_claims))
        object.__setattr__(self, "source_temporal_receipt_id", str(self.source_temporal_receipt_id).strip())
        object.__setattr__(self, "metadata", dict(self.metadata))


@dataclass(frozen=True, slots=True)
class EvidenceFreshnessState:
    """Computed freshness state for one evidence claim."""

    evidence_ref: str
    evidence_type: str
    status: str
    observed_at: str
    fresh_until: str
    age_seconds: int
    freshness_seconds: int
    remaining_fresh_seconds: int
    reasons: list[str]

    def __post_init__(self) -> None:
        if self.status not in EVIDENCE_STATES:
            raise ValueError("evidence_state_invalid")
        if self.age_seconds < 0 or self.freshness_seconds < 0 or self.remaining_fresh_seconds < 0:
            raise ValueError("evidence_state_seconds_nonnegative_required")
        object.__setattr__(self, "reasons", _normalize_list(self.reasons))


@dataclass(frozen=True, slots=True)
class TemporalEvidenceFreshnessReceipt:
    """Schema-backed non-terminal receipt for evidence freshness rechecks."""

    receipt_id: str
    request_id: str
    tenant_id: str
    actor_id: str
    command_id: str
    action_type: str
    risk_level: str
    status: str
    required_evidence_types: list[str]
    evidence_refs: list[str]
    accepted_evidence_refs: list[str]
    stale_evidence_refs: list[str]
    expiring_soon_evidence_refs: list[str]
    blocked_evidence_refs: list[str]
    missing_evidence_types: list[str]
    stale_evidence_types: list[str]
    blocked_reasons: list[str]
    evidence_warnings: list[str]
    required_controls: list[str]
    evidence_states: list[EvidenceFreshnessState]
    runtime_now_utc: str
    earliest_fresh_until: str
    recheck_due_at: str
    refresh_due_at: str
    refresh_window_seconds: int
    expiry_warning_seconds: int
    source_temporal_receipt_id: str
    receipt_schema_ref: str
    terminal_closure_required: bool
    receipt_hash: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.status not in EVIDENCE_FRESHNESS_STATUSES:
            raise ValueError("temporal_evidence_freshness_status_invalid")
        if self.refresh_window_seconds < 0 or self.expiry_warning_seconds < 0:
            raise ValueError("temporal_evidence_freshness_seconds_nonnegative_required")
        object.__setattr__(self, "required_evidence_types", _normalize_list(self.required_evidence_types))
        object.__setattr__(self, "evidence_refs", _normalize_list(self.evidence_refs))
        object.__setattr__(self, "accepted_evidence_refs", _normalize_list(self.accepted_evidence_refs))
        object.__setattr__(self, "stale_evidence_refs", _normalize_list(self.stale_evidence_refs))
        object.__setattr__(self, "expiring_soon_evidence_refs", _normalize_list(self.expiring_soon_evidence_refs))
        object.__setattr__(self, "blocked_evidence_refs", _normalize_list(self.blocked_evidence_refs))
        object.__setattr__(self, "missing_evidence_types", _normalize_list(self.missing_evidence_types))
        object.__setattr__(self, "stale_evidence_types", _normalize_list(self.stale_evidence_types))
        object.__setattr__(self, "blocked_reasons", _normalize_list(self.blocked_reasons))
        object.__setattr__(self, "evidence_warnings", _normalize_list(self.evidence_warnings))
        object.__setattr__(self, "required_controls", _normalize_list(self.required_controls))
        object.__setattr__(self, "evidence_states", list(self.evidence_states))
        object.__setattr__(self, "metadata", dict(self.metadata))


class TemporalEvidenceFreshness:
    """Deterministic evidence freshness recheck evaluator."""

    def __init__(self, clock: TrustedClock | None = None) -> None:
        self._clock = clock or TrustedClock()

    def evaluate(self, request: EvidenceFreshnessRequest) -> TemporalEvidenceFreshnessReceipt:
        """Return whether evidence is fresh enough to support dispatch now."""
        now = _parse_required_instant(self._clock.now_utc())
        required_controls = [*BASE_EVIDENCE_FRESHNESS_CONTROLS]
        blocked_reasons: list[str] = []
        evidence_warnings: list[str] = []
        states = [
            _evaluate_claim(
                claim,
                request=request,
                now=now,
                blocked_reasons=blocked_reasons,
                evidence_warnings=evidence_warnings,
            )
            for claim in request.evidence_claims
        ]
        coverage = _coverage(request.required_evidence_types, states)
        blocked_reasons.extend(coverage["blocked_reasons"])
        evidence_warnings.extend(coverage["evidence_warnings"])

        if not request.required_evidence_types:
            blocked_reasons.append("required_evidence_types_required")
        if not request.evidence_claims:
            evidence_warnings.append("evidence_claims_absent")
        if request.risk_level in {"high", "critical"}:
            required_controls.append("verified_evidence")
        if request.source_temporal_receipt_id:
            required_controls.append("source_temporal_receipt")

        status = _status(blocked_reasons, coverage["missing_evidence_types"], coverage["stale_evidence_types"])
        earliest_fresh_until = _earliest_fresh_until(states)
        recheck_due_at = earliest_fresh_until if status == "fresh" else ""
        refresh_due_at = ""
        if status in {"refresh_required", "insufficient_evidence"} and request.refresh_window_seconds > 0:
            refresh_due_at = (now + timedelta(seconds=request.refresh_window_seconds)).isoformat()
        if status != "fresh":
            required_controls.append("dispatch_block")
        if status in {"refresh_required", "insufficient_evidence"}:
            required_controls.append("evidence_refresh")

        receipt = TemporalEvidenceFreshnessReceipt(
            receipt_id="pending",
            request_id=request.request_id,
            tenant_id=request.tenant_id,
            actor_id=request.actor_id,
            command_id=request.command_id,
            action_type=request.action_type,
            risk_level=request.risk_level,
            status=status,
            required_evidence_types=request.required_evidence_types,
            evidence_refs=[claim.evidence_ref for claim in request.evidence_claims],
            accepted_evidence_refs=coverage["accepted_evidence_refs"],
            stale_evidence_refs=coverage["stale_evidence_refs"],
            expiring_soon_evidence_refs=coverage["expiring_soon_evidence_refs"],
            blocked_evidence_refs=coverage["blocked_evidence_refs"],
            missing_evidence_types=coverage["missing_evidence_types"],
            stale_evidence_types=coverage["stale_evidence_types"],
            blocked_reasons=_unique(blocked_reasons),
            evidence_warnings=_unique(evidence_warnings),
            required_controls=_unique(required_controls),
            evidence_states=states,
            runtime_now_utc=now.isoformat(),
            earliest_fresh_until=earliest_fresh_until,
            recheck_due_at=recheck_due_at,
            refresh_due_at=refresh_due_at,
            refresh_window_seconds=request.refresh_window_seconds,
            expiry_warning_seconds=request.expiry_warning_seconds,
            source_temporal_receipt_id=request.source_temporal_receipt_id,
            receipt_schema_ref=TEMPORAL_EVIDENCE_FRESHNESS_RECEIPT_SCHEMA_REF,
            terminal_closure_required=True,
            metadata={
                "receipt_is_not_terminal_closure": True,
                "runtime_owns_time_truth": True,
                "evidence_fresh_for_dispatch": status == "fresh",
                "refresh_required": status == "refresh_required",
                "recheck_required_before_dispatch": status != "fresh",
                "high_risk_requires_verified_evidence": request.risk_level in {"high", "critical"},
                "evidence_state_count": len(states),
            },
        )
        receipt_hash = canonical_hash(asdict(receipt))
        return replace(
            receipt,
            receipt_id=f"temporal-evidence-freshness-receipt-{receipt_hash[:16]}",
            receipt_hash=receipt_hash,
        )


def _evaluate_claim(
    claim: EvidenceFreshnessClaim,
    *,
    request: EvidenceFreshnessRequest,
    now: datetime,
    blocked_reasons: list[str],
    evidence_warnings: list[str],
) -> EvidenceFreshnessState:
    reasons: list[str] = []
    observed_at = _parse_optional_instant(claim.observed_at, reasons, "observed_at_invalid")
    fresh_until = _fresh_until(claim, observed_at, reasons)
    revoked_at = _parse_optional_instant(claim.revoked_at, reasons, "revoked_at_invalid")
    status = "fresh"

    if claim.tenant_id != request.tenant_id:
        reasons.append("evidence_tenant_mismatch")
    if revoked_at and now >= revoked_at:
        reasons.append("evidence_revoked")
    if request.risk_level in {"high", "critical"} and not claim.verified:
        reasons.append("unverified_evidence_for_high_risk_action")
    if observed_at is None:
        reasons.append("observed_at_required")
    if fresh_until is None:
        reasons.append("freshness_window_required")
    if fresh_until and observed_at and fresh_until <= observed_at:
        reasons.append("freshness_window_invalid")
    if any(reason.endswith("_invalid") or reason in _BLOCKING_EVIDENCE_REASONS for reason in reasons):
        status = "blocked"
    elif fresh_until and now > fresh_until:
        reasons.append("evidence_stale")
        status = "stale"
    elif fresh_until and _is_expiring_soon(now, fresh_until, request.expiry_warning_seconds):
        reasons.append("evidence_expiring_soon")
        status = "expiring_soon"

    if status == "blocked":
        blocked_reasons.extend(f"{claim.evidence_ref}:{reason}" for reason in reasons)
    elif status in {"stale", "expiring_soon"}:
        evidence_warnings.extend(f"{claim.evidence_ref}:{reason}" for reason in reasons)

    age_seconds = _age_seconds(now, observed_at)
    remaining_fresh_seconds = _remaining_seconds(now, fresh_until)
    return EvidenceFreshnessState(
        evidence_ref=claim.evidence_ref,
        evidence_type=claim.evidence_type,
        status=status,
        observed_at=observed_at.isoformat() if observed_at else claim.observed_at,
        fresh_until=fresh_until.isoformat() if fresh_until else claim.fresh_until,
        age_seconds=age_seconds,
        freshness_seconds=claim.freshness_seconds,
        remaining_fresh_seconds=remaining_fresh_seconds,
        reasons=_unique(reasons),
    )


_BLOCKING_EVIDENCE_REASONS = frozenset(
    {
        "evidence_tenant_mismatch",
        "evidence_revoked",
        "unverified_evidence_for_high_risk_action",
        "observed_at_required",
        "freshness_window_required",
        "freshness_window_invalid",
    }
)


def _coverage(required_evidence_types: list[str], states: list[EvidenceFreshnessState]) -> dict[str, list[str]]:
    accepted_evidence_refs: list[str] = []
    stale_evidence_refs: list[str] = []
    expiring_soon_evidence_refs: list[str] = []
    blocked_evidence_refs: list[str] = []
    stale_types: set[str] = set()
    blocked_reasons: list[str] = []
    evidence_warnings: list[str] = []
    covered_types: set[str] = set()
    states_by_type = {evidence_type: [] for evidence_type in required_evidence_types}

    for state in states:
        if state.evidence_type in states_by_type:
            states_by_type[state.evidence_type].append(state)
        if state.status in {"fresh", "expiring_soon"}:
            accepted_evidence_refs.append(state.evidence_ref)
            covered_types.add(state.evidence_type)
        if state.status == "stale":
            stale_evidence_refs.append(state.evidence_ref)
            stale_types.add(state.evidence_type)
        if state.status == "expiring_soon":
            expiring_soon_evidence_refs.append(state.evidence_ref)
            evidence_warnings.append(f"{state.evidence_ref}:evidence_expiring_soon")
        if state.status == "blocked":
            blocked_evidence_refs.append(state.evidence_ref)
            blocked_reasons.extend(f"{state.evidence_ref}:{reason}" for reason in state.reasons)

    missing_evidence_types = [
        evidence_type
        for evidence_type in required_evidence_types
        if evidence_type not in covered_types and evidence_type not in stale_types
    ]
    stale_evidence_types = [
        evidence_type
        for evidence_type in required_evidence_types
        if evidence_type not in covered_types and evidence_type in stale_types
    ]
    return {
        "accepted_evidence_refs": accepted_evidence_refs,
        "stale_evidence_refs": stale_evidence_refs,
        "expiring_soon_evidence_refs": expiring_soon_evidence_refs,
        "blocked_evidence_refs": blocked_evidence_refs,
        "missing_evidence_types": missing_evidence_types,
        "stale_evidence_types": stale_evidence_types,
        "blocked_reasons": blocked_reasons,
        "evidence_warnings": evidence_warnings,
    }


def _status(blocked_reasons: list[str], missing_evidence_types: list[str], stale_evidence_types: list[str]) -> str:
    if blocked_reasons:
        return "blocked"
    if missing_evidence_types:
        return "insufficient_evidence"
    if stale_evidence_types:
        return "refresh_required"
    return "fresh"


def _fresh_until(
    claim: EvidenceFreshnessClaim,
    observed_at: datetime | None,
    reasons: list[str],
) -> datetime | None:
    if claim.fresh_until:
        return _parse_optional_instant(claim.fresh_until, reasons, "fresh_until_invalid")
    if observed_at and claim.freshness_seconds > 0:
        return observed_at + timedelta(seconds=claim.freshness_seconds)
    return None


def _earliest_fresh_until(states: list[EvidenceFreshnessState]) -> str:
    parsed = [
        _parse_required_instant(state.fresh_until)
        for state in states
        if state.status in {"fresh", "expiring_soon"} and state.fresh_until
    ]
    if not parsed:
        return ""
    return min(parsed).isoformat()


def _is_expiring_soon(now: datetime, fresh_until: datetime, expiry_warning_seconds: int) -> bool:
    if expiry_warning_seconds <= 0:
        return False
    return 0 <= (fresh_until - now).total_seconds() <= expiry_warning_seconds


def _age_seconds(now: datetime, observed_at: datetime | None) -> int:
    if observed_at is None:
        return 0
    return max(0, int((now - observed_at).total_seconds()))


def _remaining_seconds(now: datetime, fresh_until: datetime | None) -> int:
    if fresh_until is None:
        return 0
    return max(0, int((fresh_until - now).total_seconds()))


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
