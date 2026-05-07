"""Gateway temporal retention window evaluator.

Purpose: prove a data lifecycle action is inside the governed retention
    window before deletion, archive, anonymization, or retention review.
Governance scope: runtime-owned retention timing, delete-after windows,
    legal hold, tenant scope, retention policy refs, evidence refs, high-risk
    source receipt binding, and non-terminal temporal receipts.
Dependencies: dataclasses, datetime, command-spine canonical hashing, and the
    Temporal Kernel trusted clock.
Invariants:
  - Runtime clock owns retention and delete-after truth.
  - Data cannot be deleted before delete_after.
  - Archive and anonymization cannot run before retention_until.
  - Legal hold blocks lifecycle actions regardless of retention age.
  - High-risk lifecycle actions bind temporal, reapproval, and data-decision receipts.
  - Temporal retention window receipts are not terminal closure certificates.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from datetime import datetime, timezone
from typing import Any

from gateway.command_spine import canonical_hash
from gateway.temporal_kernel import TrustedClock


TEMPORAL_RETENTION_WINDOW_RECEIPT_SCHEMA_REF = "urn:mullusi:schema:temporal-retention-window-receipt:1"
RISK_LEVELS = ("low", "medium", "high", "critical")
RETENTION_ACTIONS = ("delete", "archive", "anonymize", "review", "retain")
RETENTION_STATUSES = ("retention_active", "action_due", "overdue", "blocked", "not_required")
RETENTION_STATES = ("retained", "action_due", "overdue", "legal_hold", "wrong_scope", "invalid", "not_required")
HIGH_RISK_LEVELS = frozenset({"high", "critical"})
DESTRUCTIVE_ACTIONS = frozenset({"delete", "anonymize"})
BASE_RETENTION_WINDOW_CONTROLS = (
    "runtime_clock",
    "retention_window",
    "delete_after_window",
    "legal_hold",
    "tenant_scope",
    "retention_policy",
    "evidence_reference",
    "temporal_retention_window_receipt",
    "terminal_closure",
)


@dataclass(frozen=True, slots=True)
class RetentionSubject:
    """One governed data record proposed for lifecycle action."""

    data_id: str
    tenant_id: str
    classification: str
    purpose: str
    created_at: str
    retention_until: str
    delete_after: str
    retention_policy_ref: str
    owner_id: str
    evidence_refs: list[str]
    legal_hold: bool = False
    source_event_id: str = ""
    record_hash: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in (
            "data_id",
            "tenant_id",
            "classification",
            "purpose",
            "created_at",
            "retention_until",
            "delete_after",
            "retention_policy_ref",
            "owner_id",
        ):
            value = str(getattr(self, field_name)).strip()
            if not value:
                raise ValueError(f"{field_name}_required")
            object.__setattr__(self, field_name, value)
        object.__setattr__(self, "evidence_refs", _normalize_list(self.evidence_refs))
        object.__setattr__(self, "source_event_id", str(self.source_event_id).strip())
        object.__setattr__(self, "record_hash", str(self.record_hash).strip())
        object.__setattr__(self, "metadata", dict(self.metadata))


@dataclass(frozen=True, slots=True)
class TemporalRetentionPolicy:
    """Tenant policy defining retention timing checks for lifecycle actions."""

    policy_id: str
    tenant_id: str
    allowed_actions: list[str]
    overdue_warning_seconds: int = 0
    requires_retention_check: bool = True
    high_risk_requires_retention_check: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in ("policy_id", "tenant_id"):
            value = str(getattr(self, field_name)).strip()
            if not value:
                raise ValueError(f"{field_name}_required")
            object.__setattr__(self, field_name, value)
        allowed_actions = _normalize_list(self.allowed_actions)
        for action in allowed_actions:
            if action not in RETENTION_ACTIONS:
                raise ValueError("retention_action_invalid")
        if self.overdue_warning_seconds < 0:
            raise ValueError("overdue_warning_seconds_nonnegative_required")
        object.__setattr__(self, "allowed_actions", allowed_actions)
        object.__setattr__(self, "metadata", dict(self.metadata))


@dataclass(frozen=True, slots=True)
class TemporalRetentionRequest:
    """One request to check retention timing before a lifecycle action."""

    request_id: str
    tenant_id: str
    actor_id: str
    command_id: str
    action_type: str
    risk_level: str
    policy: TemporalRetentionPolicy
    subject: RetentionSubject | None
    evidence_refs: list[str]
    source_temporal_receipt_id: str = ""
    source_reapproval_receipt_id: str = ""
    source_data_decision_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in ("request_id", "tenant_id", "actor_id", "command_id", "action_type", "risk_level"):
            value = str(getattr(self, field_name)).strip()
            if not value:
                raise ValueError(f"{field_name}_required")
            object.__setattr__(self, field_name, value)
        if self.action_type not in RETENTION_ACTIONS:
            raise ValueError("retention_action_invalid")
        if self.risk_level not in RISK_LEVELS:
            raise ValueError("risk_level_invalid")
        object.__setattr__(self, "evidence_refs", _normalize_list(self.evidence_refs))
        object.__setattr__(self, "source_temporal_receipt_id", str(self.source_temporal_receipt_id).strip())
        object.__setattr__(self, "source_reapproval_receipt_id", str(self.source_reapproval_receipt_id).strip())
        object.__setattr__(self, "source_data_decision_id", str(self.source_data_decision_id).strip())
        object.__setattr__(self, "metadata", dict(self.metadata))


@dataclass(frozen=True, slots=True)
class TemporalRetentionWindowReceipt:
    """Schema-backed non-terminal receipt for retention window checks."""

    receipt_id: str
    request_id: str
    tenant_id: str
    actor_id: str
    command_id: str
    action_type: str
    risk_level: str
    policy_id: str
    status: str
    retention_state: str
    runtime_now_utc: str
    retention_check_required: bool
    data_id: str
    subject_tenant_id: str
    classification: str
    purpose: str
    created_at: str
    retention_until: str
    delete_after: str
    target_action_due_at: str
    seconds_until_retention_until: int
    seconds_until_delete_after: int
    seconds_until_action_due: int
    overdue_seconds: int
    retention_policy_ref: str
    owner_id: str
    legal_hold: bool
    allowed_actions: list[str]
    blocked_reasons: list[str]
    warning_reasons: list[str]
    required_controls: list[str]
    evidence_refs: list[str]
    subject_evidence_refs: list[str]
    source_temporal_receipt_id: str
    source_reapproval_receipt_id: str
    source_data_decision_id: str
    receipt_schema_ref: str
    terminal_closure_required: bool
    receipt_hash: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.status not in RETENTION_STATUSES:
            raise ValueError("temporal_retention_status_invalid")
        if self.retention_state not in RETENTION_STATES:
            raise ValueError("temporal_retention_state_invalid")
        if (
            self.seconds_until_retention_until < 0
            or self.seconds_until_delete_after < 0
            or self.seconds_until_action_due < 0
            or self.overdue_seconds < 0
        ):
            raise ValueError("temporal_retention_seconds_nonnegative_required")
        object.__setattr__(self, "allowed_actions", _normalize_list(self.allowed_actions))
        object.__setattr__(self, "blocked_reasons", _normalize_list(self.blocked_reasons))
        object.__setattr__(self, "warning_reasons", _normalize_list(self.warning_reasons))
        object.__setattr__(self, "required_controls", _normalize_list(self.required_controls))
        object.__setattr__(self, "evidence_refs", _normalize_list(self.evidence_refs))
        object.__setattr__(self, "subject_evidence_refs", _normalize_list(self.subject_evidence_refs))
        object.__setattr__(self, "metadata", dict(self.metadata))


class TemporalRetentionWindow:
    """Deterministic runtime retention-window evaluator."""

    def __init__(self, clock: TrustedClock | None = None) -> None:
        self._clock = clock or TrustedClock()

    def evaluate(self, request: TemporalRetentionRequest) -> TemporalRetentionWindowReceipt:
        """Return whether a data lifecycle action is due under retention policy."""
        now = _parse_required_instant(self._clock.now_utc())
        retention_check_required = _retention_check_required(request)
        blocked_reasons: list[str] = []
        warning_reasons: list[str] = []
        required_controls = [*BASE_RETENTION_WINDOW_CONTROLS]

        if retention_check_required:
            required_controls.append("retention_policy_check")
        if request.risk_level in HIGH_RISK_LEVELS:
            required_controls.append("high_risk_lifecycle_binding")
        if request.source_temporal_receipt_id:
            required_controls.append("source_temporal_receipt")
        if request.source_reapproval_receipt_id:
            required_controls.append("source_reapproval_receipt")
        if request.source_data_decision_id:
            required_controls.append("source_data_decision")

        blocked_reasons.extend(_policy_violations(request, retention_check_required))
        subject = request.subject if retention_check_required else None
        created_at: datetime | None = None
        retention_until: datetime | None = None
        delete_after: datetime | None = None
        target_due_at: datetime | None = None
        if subject is not None:
            created_at = _parse_optional_instant(subject.created_at, blocked_reasons, "created_at_invalid")
            retention_until = _parse_optional_instant(
                subject.retention_until,
                blocked_reasons,
                "retention_until_invalid",
            )
            delete_after = _parse_optional_instant(subject.delete_after, blocked_reasons, "delete_after_invalid")
            target_due_at = _target_due_at(request.action_type, retention_until, delete_after)
            _apply_subject_rules(
                request=request,
                now=now,
                created_at=created_at,
                retention_until=retention_until,
                delete_after=delete_after,
                target_due_at=target_due_at,
                blocked_reasons=blocked_reasons,
                warning_reasons=warning_reasons,
            )

        status = _status(
            blocked_reasons=blocked_reasons,
            warning_reasons=warning_reasons,
            now=now,
            target_due_at=target_due_at,
            retention_check_required=retention_check_required,
        )
        retention_state = _retention_state(subject, blocked_reasons, status)
        required_controls = _required_controls_for_status(required_controls, status)
        receipt = TemporalRetentionWindowReceipt(
            receipt_id="pending",
            request_id=request.request_id,
            tenant_id=request.tenant_id,
            actor_id=request.actor_id,
            command_id=request.command_id,
            action_type=request.action_type,
            risk_level=request.risk_level,
            policy_id=request.policy.policy_id,
            status=status,
            retention_state=retention_state,
            runtime_now_utc=now.isoformat(),
            retention_check_required=retention_check_required,
            data_id=subject.data_id if subject else "",
            subject_tenant_id=subject.tenant_id if subject else "",
            classification=subject.classification if subject else "",
            purpose=subject.purpose if subject else "",
            created_at=_instant_text(created_at, subject.created_at if subject else ""),
            retention_until=_instant_text(retention_until, subject.retention_until if subject else ""),
            delete_after=_instant_text(delete_after, subject.delete_after if subject else ""),
            target_action_due_at=_instant_text(target_due_at, ""),
            seconds_until_retention_until=_seconds_until(now, retention_until),
            seconds_until_delete_after=_seconds_until(now, delete_after),
            seconds_until_action_due=_seconds_until(now, target_due_at),
            overdue_seconds=_overdue_seconds(now, target_due_at),
            retention_policy_ref=subject.retention_policy_ref if subject else "",
            owner_id=subject.owner_id if subject else "",
            legal_hold=subject.legal_hold if subject else False,
            allowed_actions=request.policy.allowed_actions,
            blocked_reasons=_unique(blocked_reasons),
            warning_reasons=_unique(warning_reasons),
            required_controls=_unique(required_controls),
            evidence_refs=request.evidence_refs,
            subject_evidence_refs=subject.evidence_refs if subject else [],
            source_temporal_receipt_id=request.source_temporal_receipt_id,
            source_reapproval_receipt_id=request.source_reapproval_receipt_id,
            source_data_decision_id=request.source_data_decision_id,
            receipt_schema_ref=TEMPORAL_RETENTION_WINDOW_RECEIPT_SCHEMA_REF,
            terminal_closure_required=True,
            metadata={
                "receipt_is_not_terminal_closure": True,
                "runtime_owns_time_truth": True,
                "lifecycle_action_allowed": status in {"action_due", "overdue", "not_required"},
                "retention_checked": retention_check_required,
                "delete_after_checked": retention_check_required and subject is not None,
                "legal_hold_checked": retention_check_required and subject is not None,
                "tenant_scope_checked": retention_check_required and subject is not None,
                "high_risk_source_receipts_checked": _source_receipts_checked(request),
            },
        )
        receipt_hash = canonical_hash(asdict(receipt))
        return replace(
            receipt,
            receipt_id=f"temporal-retention-window-receipt-{receipt_hash[:16]}",
            receipt_hash=receipt_hash,
        )


def _retention_check_required(request: TemporalRetentionRequest) -> bool:
    if request.policy.requires_retention_check:
        return True
    return request.risk_level in HIGH_RISK_LEVELS and request.policy.high_risk_requires_retention_check


def _policy_violations(request: TemporalRetentionRequest, retention_check_required: bool) -> list[str]:
    violations: list[str] = []
    if request.policy.tenant_id != request.tenant_id:
        violations.append("policy_tenant_mismatch")
    if not retention_check_required:
        return violations
    if not request.policy.allowed_actions:
        violations.append("allowed_actions_required")
    if request.action_type not in request.policy.allowed_actions:
        violations.append("retention_action_not_allowed")
    if request.subject is None:
        violations.append("retention_subject_required")
    if not request.evidence_refs:
        violations.append("evidence_refs_required")
    if request.risk_level in HIGH_RISK_LEVELS and not request.source_temporal_receipt_id:
        violations.append("source_temporal_receipt_required_for_high_risk")
    if request.risk_level in HIGH_RISK_LEVELS and not request.source_reapproval_receipt_id:
        violations.append("source_reapproval_receipt_required_for_high_risk")
    if request.risk_level in HIGH_RISK_LEVELS and not request.source_data_decision_id:
        violations.append("source_data_decision_required_for_high_risk")
    return violations


def _apply_subject_rules(
    *,
    request: TemporalRetentionRequest,
    now: datetime,
    created_at: datetime | None,
    retention_until: datetime | None,
    delete_after: datetime | None,
    target_due_at: datetime | None,
    blocked_reasons: list[str],
    warning_reasons: list[str],
) -> None:
    subject = request.subject
    if subject is None:
        return
    if subject.tenant_id != request.tenant_id:
        blocked_reasons.append("retention_subject_tenant_mismatch")
    if subject.legal_hold:
        blocked_reasons.append("legal_hold_blocks_lifecycle_action")
    if created_at and created_at > now:
        blocked_reasons.append("retention_subject_created_in_future")
    if retention_until and delete_after and delete_after < retention_until:
        blocked_reasons.append("delete_after_precedes_retention_until")
    if not subject.retention_policy_ref:
        blocked_reasons.append("retention_policy_ref_required")
    if not subject.owner_id:
        blocked_reasons.append("owner_id_required")
    if not subject.evidence_refs:
        blocked_reasons.append("subject_evidence_refs_required")
    if target_due_at is None:
        blocked_reasons.append("target_action_due_at_required")
    elif target_due_at > now:
        warning_reasons.append("retention_window_not_expired")
    elif _overdue_seconds(now, target_due_at) > request.policy.overdue_warning_seconds:
        warning_reasons.append("retention_action_overdue")
    if request.action_type in DESTRUCTIVE_ACTIONS and request.risk_level in HIGH_RISK_LEVELS:
        if not request.source_reapproval_receipt_id:
            blocked_reasons.append("destructive_action_reapproval_required")


def _status(
    *,
    blocked_reasons: list[str],
    warning_reasons: list[str],
    now: datetime,
    target_due_at: datetime | None,
    retention_check_required: bool,
) -> str:
    if blocked_reasons:
        return "blocked"
    if not retention_check_required:
        return "not_required"
    if target_due_at and target_due_at > now:
        return "retention_active"
    if "retention_action_overdue" in warning_reasons:
        return "overdue"
    return "action_due"


def _retention_state(subject: RetentionSubject | None, blocked_reasons: list[str], status: str) -> str:
    if status == "not_required":
        return "not_required"
    if subject is None:
        return "invalid"
    if "legal_hold_blocks_lifecycle_action" in blocked_reasons:
        return "legal_hold"
    if "retention_subject_tenant_mismatch" in blocked_reasons or "retention_action_not_allowed" in blocked_reasons:
        return "wrong_scope"
    if status == "retention_active":
        return "retained"
    if status == "action_due":
        return "action_due"
    if status == "overdue":
        return "overdue"
    if blocked_reasons:
        return "invalid"
    return "retained"


def _required_controls_for_status(required_controls: list[str], status: str) -> list[str]:
    if status == "retention_active":
        return [*required_controls, "retention_defer"]
    if status == "action_due":
        return [*required_controls, "lifecycle_action_receipt", "audit_trail"]
    if status == "overdue":
        return [*required_controls, "retention_overdue_review", "lifecycle_action_receipt", "audit_trail"]
    if status == "blocked":
        return [*required_controls, "retention_lifecycle_block"]
    return required_controls


def _source_receipts_checked(request: TemporalRetentionRequest) -> bool:
    if request.risk_level not in HIGH_RISK_LEVELS:
        return False
    return all(
        (
            request.source_temporal_receipt_id,
            request.source_reapproval_receipt_id,
            request.source_data_decision_id,
        )
    )


def _target_due_at(
    action_type: str,
    retention_until: datetime | None,
    delete_after: datetime | None,
) -> datetime | None:
    if action_type == "delete":
        return delete_after
    if action_type in {"archive", "anonymize", "review"}:
        return retention_until
    if action_type == "retain":
        return None
    return None


def _seconds_until(now: datetime, target: datetime | None) -> int:
    if target is None:
        return 0
    return max(0, int((target - now).total_seconds()))


def _overdue_seconds(now: datetime, target: datetime | None) -> int:
    if target is None:
        return 0
    return max(0, int((now - target).total_seconds()))


def _parse_optional_instant(value: str, violations: list[str], reason: str) -> datetime | None:
    if not value:
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


def _instant_text(value: datetime | None, fallback: str) -> str:
    return value.isoformat() if value else fallback


def _normalize_list(values: list[str] | tuple[str, ...]) -> list[str]:
    return [str(value).strip() for value in values if str(value).strip()]


def _unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))
