"""Gateway temporal memory refresh workflow.

Purpose: convert stale or refresh-required temporal memory receipts into
    governed refresh tasks with explicit evidence coverage, ownership, due
    windows, activation blocks, and non-terminal receipts.
Governance scope: source memory receipt status, tenant-owner scope, runtime
    clock authority, refresh evidence requirements, review readiness, and
    activation blocking before refreshed memory can guide action.
Dependencies: dataclasses, datetime, command-spine canonical hashing,
    TemporalMemoryReceipt, and the Temporal Kernel trusted clock.
Invariants:
  - Runtime clock owns current time.
  - Source temporal memory receipt identity and scope are preserved.
  - Usable memory does not create refresh work.
  - Stale memory creates a bounded refresh task.
  - Refresh readiness requires evidence coverage for every required type.
  - Blocked or superseded memory cannot silently reactivate.
  - Temporal memory refresh receipts are not terminal closure certificates.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from datetime import datetime, timedelta, timezone
from typing import Any

from gateway.command_spine import canonical_hash
from gateway.temporal_kernel import TrustedClock
from gateway.temporal_memory import TemporalMemoryReceipt


TEMPORAL_MEMORY_REFRESH_RECEIPT_SCHEMA_REF = "urn:mullusi:schema:temporal-memory-refresh-receipt:1"
SOURCE_MEMORY_STATUSES = ("usable", "refresh_required", "blocked", "superseded")
MEMORY_REFRESH_STATUSES = ("not_required", "refresh_required", "ready_for_review", "blocked", "superseded")
RISK_LEVELS = ("low", "medium", "high", "critical")
BASE_REFRESH_CONTROLS = (
    "runtime_clock",
    "source_temporal_memory_receipt",
    "tenant_owner_scope",
    "memory_refresh_policy",
    "activation_block",
    "temporal_memory_refresh_receipt",
    "terminal_closure",
)


@dataclass(frozen=True, slots=True)
class MemoryRefreshRequest:
    """One request to plan refresh work for a temporal memory receipt."""

    request_id: str
    tenant_id: str
    owner_id: str
    actor_id: str
    refresh_owner_id: str
    risk_level: str
    source_receipt: TemporalMemoryReceipt
    refresh_window_seconds: int
    required_evidence_types: list[str] = field(default_factory=list)
    candidate_evidence_refs: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in ("request_id", "tenant_id", "owner_id", "actor_id", "refresh_owner_id", "risk_level"):
            value = str(getattr(self, field_name)).strip()
            if not value:
                raise ValueError(f"{field_name}_required")
            object.__setattr__(self, field_name, value)
        if self.risk_level not in RISK_LEVELS:
            raise ValueError("risk_level_invalid")
        if self.source_receipt.status not in SOURCE_MEMORY_STATUSES:
            raise ValueError("source_memory_status_invalid")
        if self.refresh_window_seconds < 0:
            raise ValueError("refresh_window_seconds_nonnegative_required")
        object.__setattr__(self, "required_evidence_types", _normalize_list(self.required_evidence_types))
        object.__setattr__(self, "candidate_evidence_refs", _normalize_list(self.candidate_evidence_refs))
        object.__setattr__(self, "metadata", dict(self.metadata))


@dataclass(frozen=True, slots=True)
class TemporalMemoryRefreshReceipt:
    """Schema-backed non-terminal receipt for a memory refresh workflow."""

    receipt_id: str
    request_id: str
    memory_id: str
    tenant_id: str
    owner_id: str
    actor_id: str
    refresh_owner_id: str
    scope: str
    subject: str
    risk_level: str
    status: str
    source_memory_status: str
    source_memory_receipt_id: str
    refresh_task_id: str
    refresh_due_at: str
    refresh_window_seconds: int
    stale_seconds: int
    freshness_seconds: int
    required_evidence_types: list[str]
    candidate_evidence_refs: list[str]
    accepted_evidence_refs: list[str]
    rejected_evidence_refs: list[str]
    missing_evidence_types: list[str]
    refresh_reasons: list[str]
    blocked_reasons: list[str]
    supersession_reasons: list[str]
    required_controls: list[str]
    runtime_now_utc: str
    source_runtime_now_utc: str
    receipt_schema_ref: str
    terminal_closure_required: bool
    receipt_hash: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.status not in MEMORY_REFRESH_STATUSES:
            raise ValueError("temporal_memory_refresh_status_invalid")
        if self.source_memory_status not in SOURCE_MEMORY_STATUSES:
            raise ValueError("source_memory_status_invalid")
        if self.refresh_window_seconds < 0 or self.stale_seconds < 0 or self.freshness_seconds < 0:
            raise ValueError("temporal_memory_refresh_seconds_nonnegative_required")
        object.__setattr__(self, "required_evidence_types", _normalize_list(self.required_evidence_types))
        object.__setattr__(self, "candidate_evidence_refs", _normalize_list(self.candidate_evidence_refs))
        object.__setattr__(self, "accepted_evidence_refs", _normalize_list(self.accepted_evidence_refs))
        object.__setattr__(self, "rejected_evidence_refs", _normalize_list(self.rejected_evidence_refs))
        object.__setattr__(self, "missing_evidence_types", _normalize_list(self.missing_evidence_types))
        object.__setattr__(self, "refresh_reasons", _normalize_list(self.refresh_reasons))
        object.__setattr__(self, "blocked_reasons", _normalize_list(self.blocked_reasons))
        object.__setattr__(self, "supersession_reasons", _normalize_list(self.supersession_reasons))
        object.__setattr__(self, "required_controls", _normalize_list(self.required_controls))
        object.__setattr__(self, "metadata", dict(self.metadata))


class TemporalMemoryRefresh:
    """Deterministic temporal memory refresh planner."""

    def __init__(self, clock: TrustedClock | None = None) -> None:
        self._clock = clock or TrustedClock()

    def evaluate(self, request: MemoryRefreshRequest) -> TemporalMemoryRefreshReceipt:
        """Return the governed refresh state for one source memory receipt."""
        now = _parse_required_instant(self._clock.now_utc())
        blocked_reasons: list[str] = []
        refresh_reasons: list[str] = []
        supersession_reasons: list[str] = []
        required_controls = [*BASE_REFRESH_CONTROLS]

        _apply_scope_rules(request, blocked_reasons)
        source_runtime_now = _parse_source_runtime_now(request, now, blocked_reasons)
        _apply_source_status_rules(request, refresh_reasons, blocked_reasons, supersession_reasons)
        _apply_refresh_policy_rules(request, required_controls, blocked_reasons)
        evidence = _evidence_coverage(request.required_evidence_types, request.candidate_evidence_refs)

        status = _status(request, blocked_reasons, supersession_reasons, evidence["missing_evidence_types"])
        if status in {"refresh_required", "ready_for_review"}:
            required_controls.extend(("refresh_task", "evidence_refresh"))
        if status == "ready_for_review":
            required_controls.append("operator_review")
        if status in {"blocked", "superseded"}:
            required_controls.append("reactivation_block")

        refresh_due_at = ""
        refresh_task_id = ""
        if status in {"refresh_required", "ready_for_review"}:
            refresh_due_at = (now + timedelta(seconds=request.refresh_window_seconds)).isoformat()
            task_seed = _task_seed(request, now.isoformat(), evidence["accepted_evidence_refs"])
            refresh_task_id = f"temporal-memory-refresh-task-{canonical_hash(task_seed)[:16]}"

        receipt = TemporalMemoryRefreshReceipt(
            receipt_id="pending",
            request_id=request.request_id,
            memory_id=request.source_receipt.memory_id,
            tenant_id=request.source_receipt.tenant_id,
            owner_id=request.source_receipt.owner_id,
            actor_id=request.actor_id,
            refresh_owner_id=request.refresh_owner_id,
            scope=request.source_receipt.scope,
            subject=request.source_receipt.subject,
            risk_level=request.risk_level,
            status=status,
            source_memory_status=request.source_receipt.status,
            source_memory_receipt_id=request.source_receipt.receipt_id,
            refresh_task_id=refresh_task_id,
            refresh_due_at=refresh_due_at,
            refresh_window_seconds=request.refresh_window_seconds,
            stale_seconds=request.source_receipt.stale_seconds,
            freshness_seconds=request.source_receipt.freshness_seconds,
            required_evidence_types=request.required_evidence_types,
            candidate_evidence_refs=request.candidate_evidence_refs,
            accepted_evidence_refs=evidence["accepted_evidence_refs"],
            rejected_evidence_refs=evidence["rejected_evidence_refs"],
            missing_evidence_types=evidence["missing_evidence_types"],
            refresh_reasons=_unique(refresh_reasons),
            blocked_reasons=_unique(blocked_reasons),
            supersession_reasons=_unique(supersession_reasons),
            required_controls=_unique(required_controls),
            runtime_now_utc=now.isoformat(),
            source_runtime_now_utc=source_runtime_now.isoformat(),
            receipt_schema_ref=TEMPORAL_MEMORY_REFRESH_RECEIPT_SCHEMA_REF,
            terminal_closure_required=True,
            metadata={
                "receipt_is_not_terminal_closure": True,
                "runtime_owns_time_truth": True,
                "activation_blocked_until_refresh": status != "not_required",
                "memory_refresh_task_created": status in {"refresh_required", "ready_for_review"},
                "review_required": status == "ready_for_review",
                "source_memory_usable": request.source_receipt.status == "usable",
                "evidence_type_coverage_complete": not evidence["missing_evidence_types"],
            },
        )
        receipt_hash = canonical_hash(asdict(receipt))
        return replace(
            receipt,
            receipt_id=f"temporal-memory-refresh-receipt-{receipt_hash[:16]}",
            receipt_hash=receipt_hash,
        )


def _apply_scope_rules(request: MemoryRefreshRequest, blocked_reasons: list[str]) -> None:
    if request.source_receipt.tenant_id != request.tenant_id:
        blocked_reasons.append("source_memory_tenant_mismatch")
    if request.source_receipt.owner_id != request.owner_id:
        blocked_reasons.append("source_memory_owner_mismatch")


def _parse_source_runtime_now(
    request: MemoryRefreshRequest,
    now: datetime,
    blocked_reasons: list[str],
) -> datetime:
    try:
        source_runtime_now = _parse_required_instant(request.source_receipt.runtime_now_utc)
    except ValueError:
        blocked_reasons.append("source_runtime_now_invalid")
        return now
    if source_runtime_now > now:
        blocked_reasons.append("source_memory_receipt_from_future")
    return source_runtime_now


def _apply_source_status_rules(
    request: MemoryRefreshRequest,
    refresh_reasons: list[str],
    blocked_reasons: list[str],
    supersession_reasons: list[str],
) -> None:
    source = request.source_receipt
    if source.status == "refresh_required":
        refresh_reasons.extend(source.temporal_warnings or ["source_memory_refresh_required"])
        return
    if source.status == "blocked":
        blocked_reasons.extend(source.temporal_violations or ["source_memory_blocked"])
        return
    if source.status == "superseded":
        supersession_reasons.extend(source.supersession_reasons or ["source_memory_superseded"])


def _apply_refresh_policy_rules(
    request: MemoryRefreshRequest,
    required_controls: list[str],
    blocked_reasons: list[str],
) -> None:
    if request.source_receipt.status != "refresh_required":
        return
    required_controls.append("refresh_window")
    if request.refresh_window_seconds <= 0:
        blocked_reasons.append("refresh_window_seconds_positive_required")
    if not request.required_evidence_types:
        blocked_reasons.append("required_evidence_types_required")


def _evidence_coverage(required_evidence_types: list[str], candidate_evidence_refs: list[str]) -> dict[str, list[str]]:
    required_types = _normalize_list(required_evidence_types)
    accepted_evidence_refs: list[str] = []
    rejected_evidence_refs: list[str] = []
    covered_types: set[str] = set()
    for evidence_ref in candidate_evidence_refs:
        evidence_type = _evidence_type(evidence_ref)
        if evidence_type in required_types:
            accepted_evidence_refs.append(evidence_ref)
            covered_types.add(evidence_type)
        else:
            rejected_evidence_refs.append(evidence_ref)
    return {
        "accepted_evidence_refs": accepted_evidence_refs,
        "rejected_evidence_refs": rejected_evidence_refs,
        "missing_evidence_types": [evidence_type for evidence_type in required_types if evidence_type not in covered_types],
    }


def _status(
    request: MemoryRefreshRequest,
    blocked_reasons: list[str],
    supersession_reasons: list[str],
    missing_evidence_types: list[str],
) -> str:
    if blocked_reasons:
        return "blocked"
    if supersession_reasons:
        return "superseded"
    if request.source_receipt.status == "usable":
        return "not_required"
    if request.source_receipt.status == "refresh_required":
        if missing_evidence_types:
            return "refresh_required"
        return "ready_for_review"
    return "blocked"


def _task_seed(request: MemoryRefreshRequest, runtime_now_utc: str, accepted_evidence_refs: list[str]) -> dict[str, Any]:
    return {
        "request_id": request.request_id,
        "memory_id": request.source_receipt.memory_id,
        "source_memory_receipt_id": request.source_receipt.receipt_id,
        "runtime_now_utc": runtime_now_utc,
        "refresh_owner_id": request.refresh_owner_id,
        "accepted_evidence_refs": accepted_evidence_refs,
    }


def _parse_required_instant(value: str) -> datetime:
    text = value.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise ValueError("instant_invalid") from exc
    if parsed.tzinfo is None:
        raise ValueError("instant_timezone_required")
    return parsed.astimezone(timezone.utc)


def _evidence_type(evidence_ref: str) -> str:
    return evidence_ref.split(":", 1)[0].strip()


def _normalize_list(values: list[str] | tuple[str, ...]) -> list[str]:
    return [str(value).strip() for value in values if str(value).strip()]


def _unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))
