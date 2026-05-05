"""Gateway temporal memory evaluator.

Purpose: govern whether a memory record may be used at the current runtime
    instant based on validity windows, evidence freshness, confidence decay,
    supersession, tenant scope, owner scope, and permitted use.
Governance scope: temporal memory admission for planning and dispatch support,
    stale evidence escalation, supersession blocking, confidence decay, and
    non-terminal memory receipts.
Dependencies: dataclasses, datetime, command-spine canonical hashing, and the
    Temporal Kernel trusted clock.
Invariants:
  - Runtime clock owns the current time.
  - Memory use is tenant, owner, and use-context scoped.
  - Expired or future-dated memory is blocked.
  - Superseded memory is not usable.
  - Stale evidence requires refresh instead of silent use.
  - Confidence decay is deterministic and bounded.
  - Temporal memory receipts are not terminal closure certificates.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from datetime import datetime, timezone
from typing import Any

from gateway.command_spine import canonical_hash
from gateway.temporal_kernel import TrustedClock


TEMPORAL_MEMORY_RECEIPT_SCHEMA_REF = "urn:mullusi:schema:temporal-memory-receipt:1"
MEMORY_STATUSES = ("usable", "refresh_required", "blocked", "superseded")
RISK_LEVELS = ("low", "medium", "high", "critical")
BASE_MEMORY_CONTROLS = (
    "runtime_clock",
    "memory_validity",
    "evidence_freshness",
    "confidence_decay",
    "supersession",
    "temporal_memory_receipt",
    "terminal_closure",
)


@dataclass(frozen=True, slots=True)
class TemporalMemoryRecord:
    """One temporally governed memory fact proposed for use."""

    memory_id: str
    tenant_id: str
    owner_id: str
    scope: str
    subject: str
    value: str
    source_event_id: str
    observed_at: str
    learned_at: str
    evidence_refs: list[str] = field(default_factory=list)
    allowed_use: list[str] = field(default_factory=list)
    forbidden_use: list[str] = field(default_factory=list)
    last_confirmed_at: str = ""
    valid_from: str = ""
    valid_until: str = ""
    supersedes: str = ""
    superseded_by: str = ""
    confidence: float = 1.0
    freshness_seconds: int = 0
    confidence_decay_per_day: float = 0.0
    min_confidence: float = 0.0
    sensitivity: str = "low"
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in (
            "memory_id",
            "tenant_id",
            "owner_id",
            "scope",
            "subject",
            "value",
            "source_event_id",
            "observed_at",
            "learned_at",
        ):
            value = str(getattr(self, field_name)).strip()
            if not value:
                raise ValueError(f"{field_name}_required")
            object.__setattr__(self, field_name, value)
        if self.confidence < 0.0 or self.confidence > 1.0:
            raise ValueError("confidence_out_of_range")
        if self.min_confidence < 0.0 or self.min_confidence > 1.0:
            raise ValueError("min_confidence_out_of_range")
        if self.freshness_seconds < 0:
            raise ValueError("freshness_seconds_nonnegative_required")
        if self.confidence_decay_per_day < 0.0:
            raise ValueError("confidence_decay_per_day_nonnegative_required")
        object.__setattr__(self, "evidence_refs", _normalize_list(self.evidence_refs))
        object.__setattr__(self, "allowed_use", _normalize_list(self.allowed_use))
        object.__setattr__(self, "forbidden_use", _normalize_list(self.forbidden_use))
        object.__setattr__(self, "last_confirmed_at", str(self.last_confirmed_at).strip())
        object.__setattr__(self, "valid_from", str(self.valid_from).strip())
        object.__setattr__(self, "valid_until", str(self.valid_until).strip())
        object.__setattr__(self, "supersedes", str(self.supersedes).strip())
        object.__setattr__(self, "superseded_by", str(self.superseded_by).strip())
        object.__setattr__(self, "sensitivity", str(self.sensitivity).strip() or "low")
        object.__setattr__(self, "metadata", dict(self.metadata))


@dataclass(frozen=True, slots=True)
class TemporalMemoryUseRequest:
    """One request to use a memory record for a governed action."""

    request_id: str
    tenant_id: str
    owner_id: str
    action_type: str
    risk_level: str
    use_context: str
    memory: TemporalMemoryRecord

    def __post_init__(self) -> None:
        for field_name in ("request_id", "tenant_id", "owner_id", "action_type", "risk_level", "use_context"):
            value = str(getattr(self, field_name)).strip()
            if not value:
                raise ValueError(f"{field_name}_required")
            object.__setattr__(self, field_name, value)
        if self.risk_level not in RISK_LEVELS:
            raise ValueError("risk_level_invalid")


@dataclass(frozen=True, slots=True)
class TemporalMemoryReceipt:
    """Schema-backed non-terminal receipt for temporal memory use."""

    receipt_id: str
    request_id: str
    memory_id: str
    tenant_id: str
    owner_id: str
    scope: str
    subject: str
    action_type: str
    risk_level: str
    use_context: str
    status: str
    temporal_violations: list[str]
    temporal_warnings: list[str]
    supersession_reasons: list[str]
    required_controls: list[str]
    runtime_now_utc: str
    observed_at: str
    learned_at: str
    last_confirmed_at: str
    valid_from: str
    valid_until: str
    age_seconds: int
    freshness_seconds: int
    stale_seconds: int
    confidence: float
    decayed_confidence: float
    min_confidence: float
    confidence_decay_per_day: float
    supersedes: str
    superseded_by: str
    source_event_id: str
    evidence_refs: list[str]
    allowed_use: list[str]
    forbidden_use: list[str]
    receipt_schema_ref: str
    terminal_closure_required: bool
    receipt_hash: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.status not in MEMORY_STATUSES:
            raise ValueError("temporal_memory_status_invalid")
        if self.age_seconds < 0 or self.freshness_seconds < 0 or self.stale_seconds < 0:
            raise ValueError("temporal_memory_seconds_nonnegative_required")
        object.__setattr__(self, "temporal_violations", _normalize_list(self.temporal_violations))
        object.__setattr__(self, "temporal_warnings", _normalize_list(self.temporal_warnings))
        object.__setattr__(self, "supersession_reasons", _normalize_list(self.supersession_reasons))
        object.__setattr__(self, "required_controls", _normalize_list(self.required_controls))
        object.__setattr__(self, "evidence_refs", _normalize_list(self.evidence_refs))
        object.__setattr__(self, "allowed_use", _normalize_list(self.allowed_use))
        object.__setattr__(self, "forbidden_use", _normalize_list(self.forbidden_use))
        object.__setattr__(self, "metadata", dict(self.metadata))


class TemporalMemory:
    """Deterministic temporal memory use evaluator."""

    def __init__(self, clock: TrustedClock | None = None) -> None:
        self._clock = clock or TrustedClock()

    def evaluate(self, request: TemporalMemoryUseRequest) -> TemporalMemoryReceipt:
        """Return whether the memory record may be used at runtime now."""
        now = _parse_required_instant(self._clock.now_utc())
        temporal_violations: list[str] = []
        temporal_warnings: list[str] = []
        supersession_reasons: list[str] = []
        required_controls = [*BASE_MEMORY_CONTROLS]
        parsed = _parse_memory_times(request.memory, temporal_violations)

        _apply_scope_rules(request, temporal_violations, required_controls)
        _apply_use_rules(request, temporal_violations, required_controls)
        _apply_validity_rules(parsed, now, temporal_violations)
        _apply_evidence_rules(request, temporal_violations, required_controls)
        _apply_supersession_rules(request.memory, supersession_reasons)

        age_seconds = _age_seconds(request.memory, parsed, now)
        stale_seconds = _stale_seconds(age_seconds, request.memory.freshness_seconds)
        if stale_seconds > 0:
            temporal_warnings.append("memory_evidence_stale")
        if request.risk_level in {"high", "critical"} and request.memory.freshness_seconds == 0:
            temporal_violations.append("freshness_window_required_for_high_risk_memory")
        decayed_confidence = _decayed_confidence(request.memory, age_seconds)
        if decayed_confidence < request.memory.min_confidence:
            temporal_violations.append("memory_confidence_below_minimum")

        status = _status(temporal_violations, supersession_reasons, temporal_warnings)
        receipt = TemporalMemoryReceipt(
            receipt_id="pending",
            request_id=request.request_id,
            memory_id=request.memory.memory_id,
            tenant_id=request.memory.tenant_id,
            owner_id=request.memory.owner_id,
            scope=request.memory.scope,
            subject=request.memory.subject,
            action_type=request.action_type,
            risk_level=request.risk_level,
            use_context=request.use_context,
            status=status,
            temporal_violations=_unique(temporal_violations),
            temporal_warnings=_unique(temporal_warnings),
            supersession_reasons=_unique(supersession_reasons),
            required_controls=_unique(required_controls),
            runtime_now_utc=now.isoformat(),
            observed_at=_instant_text(parsed, "observed_at", request.memory.observed_at),
            learned_at=_instant_text(parsed, "learned_at", request.memory.learned_at),
            last_confirmed_at=_instant_text(parsed, "last_confirmed_at", request.memory.last_confirmed_at),
            valid_from=_instant_text(parsed, "valid_from", request.memory.valid_from),
            valid_until=_instant_text(parsed, "valid_until", request.memory.valid_until),
            age_seconds=age_seconds,
            freshness_seconds=request.memory.freshness_seconds,
            stale_seconds=stale_seconds,
            confidence=request.memory.confidence,
            decayed_confidence=decayed_confidence,
            min_confidence=request.memory.min_confidence,
            confidence_decay_per_day=request.memory.confidence_decay_per_day,
            supersedes=request.memory.supersedes,
            superseded_by=request.memory.superseded_by,
            source_event_id=request.memory.source_event_id,
            evidence_refs=request.memory.evidence_refs,
            allowed_use=request.memory.allowed_use,
            forbidden_use=request.memory.forbidden_use,
            receipt_schema_ref=TEMPORAL_MEMORY_RECEIPT_SCHEMA_REF,
            terminal_closure_required=True,
            metadata={
                "receipt_is_not_terminal_closure": True,
                "memory_usable": status == "usable",
                "runtime_owns_time_truth": True,
                "evidence_refresh_required": status == "refresh_required",
                "supersession_checked": True,
                "confidence_decay_applied": request.memory.confidence_decay_per_day > 0.0,
            },
        )
        receipt_hash = canonical_hash(asdict(receipt))
        return replace(
            receipt,
            receipt_id=f"temporal-memory-receipt-{receipt_hash[:16]}",
            receipt_hash=receipt_hash,
        )


def _parse_memory_times(
    memory: TemporalMemoryRecord,
    temporal_violations: list[str],
) -> dict[str, datetime]:
    parsed: dict[str, datetime] = {}
    for field_name in (
        "observed_at",
        "learned_at",
        "last_confirmed_at",
        "valid_from",
        "valid_until",
    ):
        raw_value = str(getattr(memory, field_name)).strip()
        if not raw_value:
            continue
        try:
            parsed[field_name] = _parse_required_instant(raw_value)
        except ValueError:
            temporal_violations.append(f"{field_name}_invalid")
    return parsed


def _apply_scope_rules(
    request: TemporalMemoryUseRequest,
    temporal_violations: list[str],
    required_controls: list[str],
) -> None:
    required_controls.append("tenant_owner_scope")
    if request.memory.tenant_id != request.tenant_id:
        temporal_violations.append("memory_tenant_mismatch")
    if request.memory.owner_id != request.owner_id:
        temporal_violations.append("memory_owner_mismatch")


def _apply_use_rules(
    request: TemporalMemoryUseRequest,
    temporal_violations: list[str],
    required_controls: list[str],
) -> None:
    required_controls.append("allowed_use")
    if request.use_context in request.memory.forbidden_use:
        temporal_violations.append("memory_use_forbidden")
    if request.use_context not in request.memory.allowed_use:
        temporal_violations.append("memory_use_not_allowed")


def _apply_validity_rules(
    parsed: dict[str, datetime],
    now: datetime,
    temporal_violations: list[str],
) -> None:
    valid_from = parsed.get("valid_from")
    valid_until = parsed.get("valid_until")
    if valid_from and now < valid_from:
        temporal_violations.append("memory_not_yet_valid")
    if valid_until and now > valid_until:
        temporal_violations.append("memory_validity_expired")
    if valid_from and valid_until and valid_until <= valid_from:
        temporal_violations.append("memory_validity_window_invalid")


def _apply_evidence_rules(
    request: TemporalMemoryUseRequest,
    temporal_violations: list[str],
    required_controls: list[str],
) -> None:
    required_controls.append("evidence_reference")
    if not request.memory.evidence_refs:
        temporal_violations.append("evidence_refs_required")


def _apply_supersession_rules(memory: TemporalMemoryRecord, supersession_reasons: list[str]) -> None:
    if memory.superseded_by:
        supersession_reasons.append("memory_superseded")


def _age_seconds(memory: TemporalMemoryRecord, parsed: dict[str, datetime], now: datetime) -> int:
    reference = parsed.get("last_confirmed_at") or parsed.get("observed_at") or parsed.get("learned_at")
    if reference is None:
        return 0
    return max(0, int((now - reference).total_seconds()))


def _stale_seconds(age_seconds: int, freshness_seconds: int) -> int:
    if freshness_seconds <= 0:
        return 0
    return max(0, age_seconds - freshness_seconds)


def _decayed_confidence(memory: TemporalMemoryRecord, age_seconds: int) -> float:
    age_days = age_seconds / 86_400
    decayed = memory.confidence - (memory.confidence_decay_per_day * age_days)
    return round(min(1.0, max(0.0, decayed)), 6)


def _status(
    temporal_violations: list[str],
    supersession_reasons: list[str],
    temporal_warnings: list[str],
) -> str:
    if temporal_violations:
        return "blocked"
    if supersession_reasons:
        return "superseded"
    if temporal_warnings:
        return "refresh_required"
    return "usable"


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
