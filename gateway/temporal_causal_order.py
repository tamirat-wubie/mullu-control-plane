"""Gateway temporal causal-order evaluator.

Purpose: prove timestamped causal prerequisites before governed dispatch.
Governance scope: runtime-owned event order, tenant and command scope,
    predecessor edges, source receipt binding, missing events, out-of-order
    events, and non-terminal temporal causal-order receipts.
Dependencies: dataclasses, datetime, command-spine canonical hashing, and the
    Temporal Kernel trusted clock.
Invariants:
  - Runtime clock owns causal-order admission time.
  - Required event types must be present before dispatch.
  - Events must match tenant and command scope.
  - Predecessor edges must point to earlier observed events.
  - High-risk and critical dispatch require source temporal receipts.
  - Temporal causal-order receipts are not terminal closure certificates.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from datetime import datetime, timezone
from typing import Any

from gateway.command_spine import canonical_hash
from gateway.temporal_kernel import TrustedClock


TEMPORAL_CAUSAL_ORDER_RECEIPT_SCHEMA_REF = "urn:mullusi:schema:temporal-causal-order-receipt:1"
RISK_LEVELS = ("low", "medium", "high", "critical")
CAUSAL_ORDER_STATUSES = ("order_valid", "blocked", "not_required")
ORDER_STATES = ("valid", "missing", "out_of_order", "invalid", "not_required")
HIGH_RISK_LEVELS = frozenset({"high", "critical"})
BASE_CAUSAL_ORDER_CONTROLS = (
    "runtime_clock",
    "tenant_scope",
    "command_scope",
    "event_order_policy",
    "timestamped_events",
    "source_receipt_binding",
    "temporal_causal_order_receipt",
    "terminal_closure",
)


@dataclass(frozen=True, slots=True)
class TemporalCausalEvent:
    """One timestamped event in a command causal chain."""

    event_id: str
    event_type: str
    tenant_id: str
    command_id: str
    occurred_at: str
    source_receipt_id: str = ""
    predecessor_event_ids: list[str] = field(default_factory=list)
    evidence_refs: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in ("event_id", "event_type", "tenant_id", "command_id", "occurred_at"):
            value = str(getattr(self, field_name)).strip()
            if not value:
                raise ValueError(f"{field_name}_required")
            object.__setattr__(self, field_name, value)
        object.__setattr__(self, "source_receipt_id", str(self.source_receipt_id).strip())
        object.__setattr__(self, "predecessor_event_ids", _normalize_list(self.predecessor_event_ids))
        object.__setattr__(self, "evidence_refs", _normalize_list(self.evidence_refs))
        object.__setattr__(self, "metadata", dict(self.metadata))


@dataclass(frozen=True, slots=True)
class TemporalCausalOrderPolicy:
    """Tenant policy defining required causal events and order."""

    policy_id: str
    tenant_id: str
    required_event_types: list[str]
    ordered_event_types: list[str]
    requires_causal_order: bool = True
    high_risk_requires_causal_order: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in ("policy_id", "tenant_id"):
            value = str(getattr(self, field_name)).strip()
            if not value:
                raise ValueError(f"{field_name}_required")
            object.__setattr__(self, field_name, value)
        object.__setattr__(self, "required_event_types", _normalize_list(self.required_event_types))
        object.__setattr__(self, "ordered_event_types", _normalize_list(self.ordered_event_types))
        object.__setattr__(self, "metadata", dict(self.metadata))


@dataclass(frozen=True, slots=True)
class TemporalCausalOrderRequest:
    """One request to prove causal-order admission before dispatch."""

    request_id: str
    tenant_id: str
    actor_id: str
    command_id: str
    action_type: str
    risk_level: str
    policy: TemporalCausalOrderPolicy
    events: list[TemporalCausalEvent]
    evidence_refs: list[str]
    source_temporal_receipt_id: str = ""
    source_dispatch_window_receipt_id: str = ""
    source_budget_window_receipt_id: str = ""
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
        object.__setattr__(self, "events", list(self.events))
        object.__setattr__(self, "evidence_refs", _normalize_list(self.evidence_refs))
        object.__setattr__(self, "source_temporal_receipt_id", str(self.source_temporal_receipt_id).strip())
        object.__setattr__(
            self,
            "source_dispatch_window_receipt_id",
            str(self.source_dispatch_window_receipt_id).strip(),
        )
        object.__setattr__(self, "source_budget_window_receipt_id", str(self.source_budget_window_receipt_id).strip())
        object.__setattr__(self, "source_reapproval_receipt_id", str(self.source_reapproval_receipt_id).strip())
        object.__setattr__(self, "metadata", dict(self.metadata))


@dataclass(frozen=True, slots=True)
class TemporalCausalOrderReceipt:
    """Schema-backed non-terminal receipt for causal-order checks."""

    receipt_id: str
    request_id: str
    tenant_id: str
    actor_id: str
    command_id: str
    action_type: str
    risk_level: str
    policy_id: str
    status: str
    order_state: str
    runtime_now_utc: str
    earliest_event_at: str
    latest_event_at: str
    required_event_types: list[str]
    ordered_event_types: list[str]
    observed_event_types: list[str]
    missing_event_types: list[str]
    out_of_order_event_ids: list[str]
    invalid_event_ids: list[str]
    event_count: int
    required_controls: list[str]
    evidence_refs: list[str]
    event_evidence_refs: list[str]
    source_temporal_receipt_id: str
    source_dispatch_window_receipt_id: str
    source_budget_window_receipt_id: str
    source_reapproval_receipt_id: str
    blocked_reasons: list[str]
    receipt_schema_ref: str
    terminal_closure_required: bool
    receipt_hash: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.status not in CAUSAL_ORDER_STATUSES:
            raise ValueError("temporal_causal_order_status_invalid")
        if self.order_state not in ORDER_STATES:
            raise ValueError("temporal_causal_order_state_invalid")
        object.__setattr__(self, "required_event_types", _normalize_list(self.required_event_types))
        object.__setattr__(self, "ordered_event_types", _normalize_list(self.ordered_event_types))
        object.__setattr__(self, "observed_event_types", _normalize_list(self.observed_event_types))
        object.__setattr__(self, "missing_event_types", _normalize_list(self.missing_event_types))
        object.__setattr__(self, "out_of_order_event_ids", _normalize_list(self.out_of_order_event_ids))
        object.__setattr__(self, "invalid_event_ids", _normalize_list(self.invalid_event_ids))
        object.__setattr__(self, "required_controls", _normalize_list(self.required_controls))
        object.__setattr__(self, "evidence_refs", _normalize_list(self.evidence_refs))
        object.__setattr__(self, "event_evidence_refs", _normalize_list(self.event_evidence_refs))
        object.__setattr__(self, "blocked_reasons", _normalize_list(self.blocked_reasons))
        object.__setattr__(self, "metadata", dict(self.metadata))


class TemporalCausalOrder:
    """Deterministic runtime causal-order evaluator."""

    def __init__(self, clock: TrustedClock | None = None) -> None:
        self._clock = clock or TrustedClock()

    def evaluate(self, request: TemporalCausalOrderRequest) -> TemporalCausalOrderReceipt:
        """Return whether required events satisfy causal order before dispatch."""
        now = _parse_required_instant(self._clock.now_utc())
        causal_order_required = _causal_order_required(request)
        blocked_reasons: list[str] = []
        invalid_event_ids: list[str] = []
        out_of_order_event_ids: list[str] = []
        required_controls = [*BASE_CAUSAL_ORDER_CONTROLS]

        if causal_order_required:
            required_controls.append("causal_order_policy")
        if request.risk_level in HIGH_RISK_LEVELS:
            required_controls.append("high_risk_causal_order")
        if request.source_temporal_receipt_id:
            required_controls.append("source_temporal_receipt")
        if request.source_dispatch_window_receipt_id:
            required_controls.append("source_dispatch_window_receipt")
        if request.source_budget_window_receipt_id:
            required_controls.append("source_budget_window_receipt")
        if request.source_reapproval_receipt_id:
            required_controls.append("source_reapproval_receipt")

        blocked_reasons.extend(_policy_violations(request, causal_order_required))
        parsed_events = _parse_events(
            request=request,
            now=now,
            causal_order_required=causal_order_required,
            blocked_reasons=blocked_reasons,
            invalid_event_ids=invalid_event_ids,
        )
        _validate_predecessors(
            parsed_events=parsed_events,
            blocked_reasons=blocked_reasons,
            invalid_event_ids=invalid_event_ids,
            out_of_order_event_ids=out_of_order_event_ids,
        )
        observed_event_types = _observed_event_types(parsed_events)
        missing_event_types = _missing_event_types(
            request.policy.required_event_types,
            observed_event_types,
            causal_order_required,
        )
        for event_type in missing_event_types:
            blocked_reasons.append(f"required_event_missing:{event_type}")
        out_of_order_event_ids.extend(
            _ordered_sequence_violations(
                ordered_event_types=request.policy.ordered_event_types,
                parsed_events=parsed_events,
                invalid_event_ids=invalid_event_ids,
                blocked_reasons=blocked_reasons,
                causal_order_required=causal_order_required,
            )
        )

        blocked_reasons = _unique(blocked_reasons)
        invalid_event_ids = _unique(invalid_event_ids)
        out_of_order_event_ids = _unique(out_of_order_event_ids)
        status = _status(blocked_reasons, causal_order_required)
        order_state = _order_state(
            status=status,
            missing_event_types=missing_event_types,
            out_of_order_event_ids=out_of_order_event_ids,
            invalid_event_ids=invalid_event_ids,
        )
        valid_event_times = _valid_event_times(parsed_events, invalid_event_ids)

        receipt = TemporalCausalOrderReceipt(
            receipt_id="pending",
            request_id=request.request_id,
            tenant_id=request.tenant_id,
            actor_id=request.actor_id,
            command_id=request.command_id,
            action_type=request.action_type,
            risk_level=request.risk_level,
            policy_id=request.policy.policy_id,
            status=status,
            order_state=order_state,
            runtime_now_utc=now.isoformat(),
            earliest_event_at=_instant_text(min(valid_event_times) if valid_event_times else None),
            latest_event_at=_instant_text(max(valid_event_times) if valid_event_times else None),
            required_event_types=request.policy.required_event_types if causal_order_required else [],
            ordered_event_types=request.policy.ordered_event_types if causal_order_required else [],
            observed_event_types=observed_event_types,
            missing_event_types=missing_event_types,
            out_of_order_event_ids=out_of_order_event_ids,
            invalid_event_ids=invalid_event_ids,
            event_count=len(request.events),
            required_controls=_unique(
                required_controls
                if status in {"order_valid", "not_required"}
                else [*required_controls, "causal_dispatch_block"]
            ),
            evidence_refs=request.evidence_refs,
            event_evidence_refs=_event_evidence_refs(request.events),
            source_temporal_receipt_id=request.source_temporal_receipt_id,
            source_dispatch_window_receipt_id=request.source_dispatch_window_receipt_id,
            source_budget_window_receipt_id=request.source_budget_window_receipt_id,
            source_reapproval_receipt_id=request.source_reapproval_receipt_id,
            blocked_reasons=blocked_reasons,
            receipt_schema_ref=TEMPORAL_CAUSAL_ORDER_RECEIPT_SCHEMA_REF,
            terminal_closure_required=True,
            metadata={
                "receipt_is_not_terminal_closure": True,
                "runtime_owns_time_truth": True,
                "dispatch_allowed": status in {"order_valid", "not_required"},
                "causal_order_checked": causal_order_required,
                "high_risk_causal_order_checked": request.risk_level in HIGH_RISK_LEVELS,
                "source_receipts_checked": _source_receipts_checked(request),
            },
        )
        receipt_hash = canonical_hash(asdict(receipt))
        return replace(
            receipt,
            receipt_id=f"temporal-causal-order-receipt-{receipt_hash[:16]}",
            receipt_hash=receipt_hash,
        )


def _causal_order_required(request: TemporalCausalOrderRequest) -> bool:
    if request.policy.requires_causal_order:
        return True
    return request.risk_level in HIGH_RISK_LEVELS and request.policy.high_risk_requires_causal_order


def _policy_violations(request: TemporalCausalOrderRequest, causal_order_required: bool) -> list[str]:
    violations: list[str] = []
    if request.policy.tenant_id != request.tenant_id:
        violations.append("policy_tenant_mismatch")
    if not causal_order_required:
        return violations
    if not request.policy.required_event_types:
        violations.append("required_event_types_required")
    if not request.policy.ordered_event_types:
        violations.append("ordered_event_types_required")
    if not request.events:
        violations.append("causal_events_required")
    if not request.evidence_refs:
        violations.append("evidence_refs_required")
    if request.risk_level in HIGH_RISK_LEVELS and not request.source_temporal_receipt_id:
        violations.append("source_temporal_receipt_required_for_high_risk")
    if request.risk_level in HIGH_RISK_LEVELS and not request.source_dispatch_window_receipt_id:
        violations.append("source_dispatch_window_receipt_required_for_high_risk")
    if request.risk_level in HIGH_RISK_LEVELS and not request.source_budget_window_receipt_id:
        violations.append("source_budget_window_receipt_required_for_high_risk")
    if request.risk_level in HIGH_RISK_LEVELS and not request.source_reapproval_receipt_id:
        violations.append("source_reapproval_receipt_required_for_high_risk")
    return violations


def _parse_events(
    *,
    request: TemporalCausalOrderRequest,
    now: datetime,
    causal_order_required: bool,
    blocked_reasons: list[str],
    invalid_event_ids: list[str],
) -> list[tuple[TemporalCausalEvent, datetime | None]]:
    parsed_events: list[tuple[TemporalCausalEvent, datetime | None]] = []
    seen_event_ids: set[str] = set()
    for event in request.events:
        parsed_at = _parse_optional_instant(
            value=event.occurred_at,
            violations=blocked_reasons,
            reason=f"event_occurred_at_invalid:{event.event_id}",
        )
        parsed_events.append((event, parsed_at))
        if event.event_id in seen_event_ids:
            blocked_reasons.append(f"event_id_duplicate:{event.event_id}")
            invalid_event_ids.append(event.event_id)
        seen_event_ids.add(event.event_id)
        if event.tenant_id != request.tenant_id:
            blocked_reasons.append(f"event_tenant_mismatch:{event.event_id}")
            invalid_event_ids.append(event.event_id)
        if event.command_id != request.command_id:
            blocked_reasons.append(f"event_command_mismatch:{event.event_id}")
            invalid_event_ids.append(event.event_id)
        if parsed_at is None:
            invalid_event_ids.append(event.event_id)
            continue
        if parsed_at > now:
            blocked_reasons.append(f"event_future:{event.event_id}")
            invalid_event_ids.append(event.event_id)
        if causal_order_required and not event.evidence_refs:
            blocked_reasons.append(f"event_evidence_refs_required:{event.event_id}")
            invalid_event_ids.append(event.event_id)
    return parsed_events


def _validate_predecessors(
    *,
    parsed_events: list[tuple[TemporalCausalEvent, datetime | None]],
    blocked_reasons: list[str],
    invalid_event_ids: list[str],
    out_of_order_event_ids: list[str],
) -> None:
    event_times = {
        event.event_id: parsed_at
        for event, parsed_at in parsed_events
        if parsed_at is not None and event.event_id not in invalid_event_ids
    }
    for event, parsed_at in parsed_events:
        if parsed_at is None or event.event_id in invalid_event_ids:
            continue
        for predecessor_id in event.predecessor_event_ids:
            predecessor_at = event_times.get(predecessor_id)
            if predecessor_at is None:
                blocked_reasons.append(f"event_predecessor_missing:{event.event_id}:{predecessor_id}")
                invalid_event_ids.append(event.event_id)
                continue
            if predecessor_at >= parsed_at:
                blocked_reasons.append(f"predecessor_order_violation:{event.event_id}:{predecessor_id}")
                out_of_order_event_ids.append(event.event_id)


def _ordered_sequence_violations(
    *,
    ordered_event_types: list[str],
    parsed_events: list[tuple[TemporalCausalEvent, datetime | None]],
    invalid_event_ids: list[str],
    blocked_reasons: list[str],
    causal_order_required: bool,
) -> list[str]:
    if not causal_order_required:
        return []
    earliest_by_type: dict[str, tuple[str, datetime]] = {}
    invalid_ids = set(invalid_event_ids)
    for event, parsed_at in parsed_events:
        if parsed_at is None or event.event_id in invalid_ids:
            continue
        existing = earliest_by_type.get(event.event_type)
        if existing is None or parsed_at < existing[1]:
            earliest_by_type[event.event_type] = (event.event_id, parsed_at)

    out_of_order_event_ids: list[str] = []
    previous_type = ""
    previous_time: datetime | None = None
    for event_type in ordered_event_types:
        current = earliest_by_type.get(event_type)
        if current is None:
            continue
        event_id, current_time = current
        if previous_time is not None and current_time <= previous_time:
            blocked_reasons.append(f"causal_order_violation:{previous_type}:{event_type}")
            out_of_order_event_ids.append(event_id)
        previous_type = event_type
        previous_time = current_time
    return out_of_order_event_ids


def _observed_event_types(parsed_events: list[tuple[TemporalCausalEvent, datetime | None]]) -> list[str]:
    return _unique([event.event_type for event, parsed_at in parsed_events if parsed_at is not None])


def _missing_event_types(
    required_event_types: list[str],
    observed_event_types: list[str],
    causal_order_required: bool,
) -> list[str]:
    if not causal_order_required:
        return []
    observed = set(observed_event_types)
    return [event_type for event_type in required_event_types if event_type not in observed]


def _valid_event_times(
    parsed_events: list[tuple[TemporalCausalEvent, datetime | None]],
    invalid_event_ids: list[str],
) -> list[datetime]:
    invalid_ids = set(invalid_event_ids)
    return [
        parsed_at
        for event, parsed_at in parsed_events
        if parsed_at is not None and event.event_id not in invalid_ids
    ]


def _event_evidence_refs(events: list[TemporalCausalEvent]) -> list[str]:
    refs: list[str] = []
    for event in events:
        refs.extend(event.evidence_refs)
        if event.source_receipt_id:
            refs.append(event.source_receipt_id)
    return _unique(refs)


def _source_receipts_checked(request: TemporalCausalOrderRequest) -> bool:
    if request.risk_level not in HIGH_RISK_LEVELS:
        return False
    return all(
        (
            request.source_temporal_receipt_id,
            request.source_dispatch_window_receipt_id,
            request.source_budget_window_receipt_id,
            request.source_reapproval_receipt_id,
        )
    )


def _status(blocked_reasons: list[str], causal_order_required: bool) -> str:
    if blocked_reasons:
        return "blocked"
    if not causal_order_required:
        return "not_required"
    return "order_valid"


def _order_state(
    *,
    status: str,
    missing_event_types: list[str],
    out_of_order_event_ids: list[str],
    invalid_event_ids: list[str],
) -> str:
    if status == "not_required":
        return "not_required"
    if missing_event_types:
        return "missing"
    if out_of_order_event_ids:
        return "out_of_order"
    if invalid_event_ids or status == "blocked":
        return "invalid"
    return "valid"


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


def _instant_text(value: datetime | None) -> str:
    return value.isoformat() if value else ""


def _normalize_list(values: list[str] | tuple[str, ...]) -> list[str]:
    return [str(value).strip() for value in values if str(value).strip()]


def _unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))
