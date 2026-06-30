"""Purpose: immutable Operator Console First runtime contracts.
Governance scope: episode admission, approval leases, side-effect manifests,
    external-effect gateway dispatch, verification records, and receipts.
Dependencies: shared contract helpers and Python standard library enums.
Invariants:
  - Every effect-bearing action declares side effects and recovery before dispatch.
  - Approval leases bind to exact plan, target-state hash, risk ceiling, and scope.
  - Tool-reported success is separate from independently verified task success.
  - Every terminal episode state can emit a bounded receipt.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Mapping

from ._base import (
    ContractRecord,
    freeze_value,
    require_datetime_text,
    require_non_empty_text,
    require_non_negative_float,
    require_unit_float,
)


def _freeze_text_tuple(
    values: tuple[str, ...] | list[str],
    field_name: str,
    *,
    allow_empty: bool,
) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)) or not isinstance(values, (tuple, list)):
        raise ValueError(f"{field_name} must be an array")
    frozen = freeze_value(list(values))
    if not isinstance(frozen, tuple):
        raise ValueError(f"{field_name} must be an array")
    if not frozen and not allow_empty:
        raise ValueError(f"{field_name} must contain at least one item")
    for index, value in enumerate(frozen):
        require_non_empty_text(value, f"{field_name}[{index}]")
    return frozen


def _freeze_mapping(value: Mapping[str, Any], field_name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field_name} must be a mapping")
    return freeze_value(value)


def _require_risk_score(value: int, field_name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"{field_name} must be an integer")
    if value < 0 or value > 100:
        raise ValueError(f"{field_name} must be between 0 and 100")
    return value


class ConsoleIntentClass(StrEnum):
    """Governed intent lane compiled from the operator request."""

    OBSERVE = "observe"
    DRAFT = "draft"
    INTERNAL_REVERSIBLE = "internal_reversible"
    EXTERNAL_REVERSIBLE = "external_reversible"
    EXTERNAL_IRREVERSIBLE = "external_irreversible"
    CRITICAL = "critical"


class ConsoleEpisodeStatus(StrEnum):
    """Lifecycle state for one console-governed episode."""

    CAPTURED = "captured"
    BOUNDED = "bounded"
    SNAPSHOTTED = "snapshotted"
    PLANNED = "planned"
    WAITING_APPROVAL = "waiting_approval"
    APPROVED = "approved"
    DISPATCHING = "dispatching"
    VERIFYING = "verifying"
    CLOSED = "closed"
    BLOCKED = "blocked"
    APPROVAL_EXPIRED = "approval_expired"
    STALE_STATE = "stale_state"
    POLICY_DENIED = "policy_denied"
    ABORTED = "aborted"
    QUARANTINED = "quarantined"


class ConsoleFinalStatus(StrEnum):
    """Terminal outcome for a console episode receipt."""

    VERIFIED_SUCCESS = "verified_success"
    UNVERIFIED_SUCCESS = "unverified_success"
    PARTIAL_SUCCESS = "partial_success"
    BLOCKED = "blocked"
    FAILED_RECOVERABLE = "failed_recoverable"
    FAILED_UNRECOVERABLE = "failed_unrecoverable"
    ABORTED = "aborted"
    QUARANTINED = "quarantined"


class RecoveryClass(StrEnum):
    """Recovery class mapped to effect-bearing actions."""

    R0_NONE = "r0_none"
    R1_DIRECT_ROLLBACK = "r1_direct_rollback"
    R2_COMPENSATING_ACTION = "r2_compensating_action"
    R3_CONTAINMENT = "r3_containment"
    R4_MANUAL_ESCALATION = "r4_manual_escalation"


class ApprovalMode(StrEnum):
    """Approval strength selected from risk and recovery constraints."""

    AUTO = "auto"
    SOFT_NOTIFY = "soft_notify"
    EXPLICIT = "explicit"
    STRONG = "strong"
    BLOCKED = "blocked"


@dataclass(frozen=True, slots=True)
class SideEffectManifest(ContractRecord):
    """Declared side-effect surface for a capability action."""

    reads_data: bool = False
    writes_data: bool = False
    sends_external_data: bool = False
    changes_permissions: bool = False
    changes_money: bool = False
    changes_public_state: bool = False
    uses_network: bool = False
    stores_logs: bool = False
    touches_secrets: bool = False

    def __post_init__(self) -> None:
        for field_name in (
            "reads_data",
            "writes_data",
            "sends_external_data",
            "changes_permissions",
            "changes_money",
            "changes_public_state",
            "uses_network",
            "stores_logs",
            "touches_secrets",
        ):
            if not isinstance(getattr(self, field_name), bool):
                raise ValueError(f"{field_name} must be a boolean")

    @property
    def effect_bearing(self) -> bool:
        return any(
            (
                self.writes_data,
                self.sends_external_data,
                self.changes_permissions,
                self.changes_money,
                self.changes_public_state,
                self.uses_network,
                self.stores_logs,
                self.touches_secrets,
            )
        )


@dataclass(frozen=True, slots=True)
class StateSnapshot(ContractRecord):
    """Freshness-bound state snapshot used for approval and dispatch."""

    source: str
    captured_at: str
    expires_at: str
    state_hash: str
    trust_level: float
    missing_fields: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "source", require_non_empty_text(self.source, "source"))
        object.__setattr__(
            self,
            "captured_at",
            require_datetime_text(self.captured_at, "captured_at"),
        )
        object.__setattr__(
            self,
            "expires_at",
            require_datetime_text(self.expires_at, "expires_at"),
        )
        object.__setattr__(
            self,
            "state_hash",
            require_non_empty_text(self.state_hash, "state_hash"),
        )
        object.__setattr__(
            self,
            "trust_level",
            require_unit_float(self.trust_level, "trust_level"),
        )
        object.__setattr__(
            self,
            "missing_fields",
            _freeze_text_tuple(self.missing_fields, "missing_fields", allow_empty=True),
        )


@dataclass(frozen=True, slots=True)
class EpisodeLimits(ContractRecord):
    """Bounded episode budget and blast-radius controls."""

    max_cost: float = 0.0
    max_runtime_seconds: int = 0
    max_external_messages: int = 0
    max_api_calls: int = 0
    max_retry_count: int = 0
    max_data_exposure: int = 0

    def __post_init__(self) -> None:
        object.__setattr__(self, "max_cost", require_non_negative_float(self.max_cost, "max_cost"))
        for field_name in (
            "max_runtime_seconds",
            "max_external_messages",
            "max_api_calls",
            "max_retry_count",
            "max_data_exposure",
        ):
            value = getattr(self, field_name)
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise ValueError(f"{field_name} must be a non-negative integer")


@dataclass(frozen=True, slots=True)
class ApprovalLease(ContractRecord):
    """State-bound and plan-bound approval grant."""

    operator_id: str
    plan_hash: str
    target_state_hash: str
    risk_ceiling: int
    scope: Mapping[str, Any]
    issued_at: str
    expires_at: str
    allowed_actions: tuple[str, ...]

    def __post_init__(self) -> None:
        for field_name in ("operator_id", "plan_hash", "target_state_hash"):
            object.__setattr__(
                self,
                field_name,
                require_non_empty_text(getattr(self, field_name), field_name),
            )
        object.__setattr__(self, "risk_ceiling", _require_risk_score(self.risk_ceiling, "risk_ceiling"))
        object.__setattr__(self, "scope", _freeze_mapping(self.scope, "scope"))
        object.__setattr__(self, "issued_at", require_datetime_text(self.issued_at, "issued_at"))
        object.__setattr__(self, "expires_at", require_datetime_text(self.expires_at, "expires_at"))
        object.__setattr__(
            self,
            "allowed_actions",
            _freeze_text_tuple(self.allowed_actions, "allowed_actions", allow_empty=False),
        )


@dataclass(frozen=True, slots=True)
class ConsolePlannedAction(ContractRecord):
    """One proposed action inside an operator-console episode plan."""

    action_id: str
    capability_id: str
    intent_class: ConsoleIntentClass
    risk_score: int
    expected_effects: tuple[str, ...]
    side_effects_declared: bool
    side_effects: SideEffectManifest
    recovery_class: RecoveryClass
    recovery_plan_ref: str = ""
    evidence_required: tuple[str, ...] = ()
    estimated_cost: float = 0.0

    def __post_init__(self) -> None:
        object.__setattr__(self, "action_id", require_non_empty_text(self.action_id, "action_id"))
        object.__setattr__(
            self,
            "capability_id",
            require_non_empty_text(self.capability_id, "capability_id"),
        )
        if not isinstance(self.intent_class, ConsoleIntentClass):
            raise ValueError("intent_class must be a ConsoleIntentClass value")
        object.__setattr__(self, "risk_score", _require_risk_score(self.risk_score, "risk_score"))
        object.__setattr__(
            self,
            "expected_effects",
            _freeze_text_tuple(self.expected_effects, "expected_effects", allow_empty=True),
        )
        if not isinstance(self.side_effects_declared, bool):
            raise ValueError("side_effects_declared must be a boolean")
        if not isinstance(self.side_effects, SideEffectManifest):
            raise ValueError("side_effects must be a SideEffectManifest")
        if not isinstance(self.recovery_class, RecoveryClass):
            raise ValueError("recovery_class must be a RecoveryClass value")
        if self.recovery_plan_ref:
            object.__setattr__(
                self,
                "recovery_plan_ref",
                require_non_empty_text(self.recovery_plan_ref, "recovery_plan_ref"),
            )
        object.__setattr__(
            self,
            "evidence_required",
            _freeze_text_tuple(self.evidence_required, "evidence_required", allow_empty=True),
        )
        object.__setattr__(
            self,
            "estimated_cost",
            require_non_negative_float(self.estimated_cost, "estimated_cost"),
        )

    @property
    def recovery_declared(self) -> bool:
        if self.recovery_class is RecoveryClass.R0_NONE:
            return True
        return bool(self.recovery_plan_ref)


@dataclass(frozen=True, slots=True)
class ConsoleEvent(ContractRecord):
    """Bounded event persisted to the episode causal ledger."""

    event_type: str
    occurred_at: str
    details: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "event_type", require_non_empty_text(self.event_type, "event_type"))
        object.__setattr__(self, "occurred_at", require_datetime_text(self.occurred_at, "occurred_at"))
        object.__setattr__(self, "details", _freeze_mapping(self.details, "details"))


@dataclass(frozen=True, slots=True)
class OperatorConsoleEpisode(ContractRecord):
    """Complete operator-visible episode state."""

    episode_id: str
    operator_id: str
    raw_request: str
    intent_class: ConsoleIntentClass
    governed_goal: Mapping[str, Any]
    scope: Mapping[str, Any]
    status: ConsoleEpisodeStatus
    snapshot: StateSnapshot | None = None
    plan: tuple[ConsolePlannedAction, ...] = ()
    approval_lease: ApprovalLease | None = None
    events: tuple[ConsoleEvent, ...] = ()
    limits: EpisodeLimits = field(default_factory=EpisodeLimits)

    def __post_init__(self) -> None:
        for field_name in ("episode_id", "operator_id", "raw_request"):
            object.__setattr__(
                self,
                field_name,
                require_non_empty_text(getattr(self, field_name), field_name),
            )
        if not isinstance(self.intent_class, ConsoleIntentClass):
            raise ValueError("intent_class must be a ConsoleIntentClass value")
        if not isinstance(self.status, ConsoleEpisodeStatus):
            raise ValueError("status must be a ConsoleEpisodeStatus value")
        object.__setattr__(self, "governed_goal", _freeze_mapping(self.governed_goal, "governed_goal"))
        object.__setattr__(self, "scope", _freeze_mapping(self.scope, "scope"))
        if self.snapshot is not None and not isinstance(self.snapshot, StateSnapshot):
            raise ValueError("snapshot must be a StateSnapshot")
        if self.approval_lease is not None and not isinstance(self.approval_lease, ApprovalLease):
            raise ValueError("approval_lease must be an ApprovalLease")
        object.__setattr__(self, "plan", self._freeze_plan(self.plan))
        object.__setattr__(self, "events", self._freeze_events(self.events))
        if not isinstance(self.limits, EpisodeLimits):
            raise ValueError("limits must be an EpisodeLimits")

    @staticmethod
    def _freeze_plan(values: tuple[ConsolePlannedAction, ...] | list[ConsolePlannedAction]) -> tuple[ConsolePlannedAction, ...]:
        if isinstance(values, (str, bytes)) or not isinstance(values, (tuple, list)):
            raise ValueError("plan must be an array")
        frozen = freeze_value(list(values))
        if not isinstance(frozen, tuple):
            raise ValueError("plan must be an array")
        action_ids: set[str] = set()
        for index, action in enumerate(frozen):
            if not isinstance(action, ConsolePlannedAction):
                raise ValueError(f"plan[{index}] must be a ConsolePlannedAction")
            if action.action_id in action_ids:
                raise ValueError("plan action_id values must be unique")
            action_ids.add(action.action_id)
        return frozen

    @staticmethod
    def _freeze_events(values: tuple[ConsoleEvent, ...] | list[ConsoleEvent]) -> tuple[ConsoleEvent, ...]:
        if isinstance(values, (str, bytes)) or not isinstance(values, (tuple, list)):
            raise ValueError("events must be an array")
        frozen = freeze_value(list(values))
        if not isinstance(frozen, tuple):
            raise ValueError("events must be an array")
        for index, event in enumerate(frozen):
            if not isinstance(event, ConsoleEvent):
                raise ValueError(f"events[{index}] must be a ConsoleEvent")
        return frozen


@dataclass(frozen=True, slots=True)
class GatewayDispatchResult(ContractRecord):
    """Bounded result returned by the mandatory external-effect gateway."""

    action_id: str
    tool_success: bool
    observed_effects: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    actual_side_effects: SideEffectManifest | None = None
    failure_reason: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "action_id", require_non_empty_text(self.action_id, "action_id"))
        if not isinstance(self.tool_success, bool):
            raise ValueError("tool_success must be a boolean")
        object.__setattr__(
            self,
            "observed_effects",
            _freeze_text_tuple(self.observed_effects, "observed_effects", allow_empty=True),
        )
        object.__setattr__(
            self,
            "evidence_refs",
            _freeze_text_tuple(self.evidence_refs, "evidence_refs", allow_empty=True),
        )
        if self.actual_side_effects is not None and not isinstance(
            self.actual_side_effects,
            SideEffectManifest,
        ):
            raise ValueError("actual_side_effects must be a SideEffectManifest")
        if self.failure_reason:
            object.__setattr__(
                self,
                "failure_reason",
                require_non_empty_text(self.failure_reason, "failure_reason"),
            )


@dataclass(frozen=True, slots=True)
class DispatchDecision(ContractRecord):
    """Pre-dispatch gateway decision for one action."""

    allowed: bool
    reason: str
    approval_mode: ApprovalMode
    evaluated_at: str

    def __post_init__(self) -> None:
        if not isinstance(self.allowed, bool):
            raise ValueError("allowed must be a boolean")
        object.__setattr__(self, "reason", require_non_empty_text(self.reason, "reason"))
        if not isinstance(self.approval_mode, ApprovalMode):
            raise ValueError("approval_mode must be an ApprovalMode value")
        object.__setattr__(
            self,
            "evaluated_at",
            require_datetime_text(self.evaluated_at, "evaluated_at"),
        )


@dataclass(frozen=True, slots=True)
class VerificationRecord(ContractRecord):
    """Independent verification result separated from tool success."""

    action_id: str
    tool_reported_success: bool
    independently_verified: bool
    observed_effects: tuple[str, ...] = ()
    missing_effects: tuple[str, ...] = ()
    mismatch_reasons: tuple[str, ...] = ()
    verified_at: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "action_id", require_non_empty_text(self.action_id, "action_id"))
        for field_name in ("tool_reported_success", "independently_verified"):
            if not isinstance(getattr(self, field_name), bool):
                raise ValueError(f"{field_name} must be a boolean")
        for field_name in ("observed_effects", "missing_effects", "mismatch_reasons"):
            object.__setattr__(
                self,
                field_name,
                _freeze_text_tuple(getattr(self, field_name), field_name, allow_empty=True),
            )
        object.__setattr__(self, "verified_at", require_datetime_text(self.verified_at, "verified_at"))


@dataclass(frozen=True, slots=True)
class OperatorConsoleReceipt(ContractRecord):
    """Terminal receipt for all completed, blocked, failed, or aborted episodes."""

    receipt_id: str
    episode_id: str
    final_status: ConsoleFinalStatus
    actions_attempted: tuple[str, ...]
    actions_blocked: tuple[str, ...]
    verification_records: tuple[VerificationRecord, ...]
    evidence_refs: tuple[str, ...]
    unverified_claims: tuple[str, ...]
    issued_at: str
    receipt_hash: str

    def __post_init__(self) -> None:
        for field_name in ("receipt_id", "episode_id", "receipt_hash"):
            object.__setattr__(
                self,
                field_name,
                require_non_empty_text(getattr(self, field_name), field_name),
            )
        if not isinstance(self.final_status, ConsoleFinalStatus):
            raise ValueError("final_status must be a ConsoleFinalStatus value")
        for field_name in ("actions_attempted", "actions_blocked", "evidence_refs", "unverified_claims"):
            object.__setattr__(
                self,
                field_name,
                _freeze_text_tuple(getattr(self, field_name), field_name, allow_empty=True),
            )
        if isinstance(self.verification_records, (str, bytes)) or not isinstance(
            self.verification_records,
            (tuple, list),
        ):
            raise ValueError("verification_records must be an array")
        frozen_records = freeze_value(list(self.verification_records))
        if not isinstance(frozen_records, tuple):
            raise ValueError("verification_records must be an array")
        for index, record in enumerate(frozen_records):
            if not isinstance(record, VerificationRecord):
                raise ValueError(f"verification_records[{index}] must be a VerificationRecord")
        object.__setattr__(self, "verification_records", frozen_records)
        object.__setattr__(self, "issued_at", require_datetime_text(self.issued_at, "issued_at"))
