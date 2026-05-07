"""Purpose: canonical reactive orchestration contracts for event-driven reactions,
decision gating, backpressure, and idempotency.
Governance scope: reaction plane contract typing only.
Dependencies: shared contract base helpers, event contracts, obligation contracts.
Invariants:
  - Every reaction passes through decision gating (simulation, utility, meta-reasoning).
  - No direct event-to-action shortcuts — all paths are auditable.
  - Backpressure policies bound reaction throughput.
  - Idempotency windows prevent duplicate work from replayed events.
  - Reaction decisions are immutable records of what was decided and why.
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
    require_non_empty_tuple,
    require_non_negative_int,
    require_positive_int,
    require_unit_float,
)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class ReactionVerdict(StrEnum):
    """Outcome of evaluating whether a reaction should proceed."""

    PROCEED = "proceed"
    DEFER = "defer"
    REJECT = "reject"
    ESCALATE = "escalate"
    REQUIRES_APPROVAL = "requires_approval"


class ReactionTargetKind(StrEnum):
    """What a reaction intends to do."""

    CREATE_OBLIGATION = "create_obligation"
    ACTIVATE_WORKFLOW = "activate_workflow"
    RESUME_JOB = "resume_job"
    ESCALATE = "escalate"
    NOTIFY = "notify"
    CREATE_INCIDENT = "create_incident"
    CLOSE_OBLIGATION = "close_obligation"
    TRANSFER_OBLIGATION = "transfer_obligation"
    REQUEST_APPROVAL = "request_approval"
    CUSTOM = "custom"


class BackpressureStrategy(StrEnum):
    """How the reactive layer handles overload."""

    DROP_OLDEST = "drop_oldest"
    DROP_NEWEST = "drop_newest"
    PAUSE_INTAKE = "pause_intake"
    RATE_LIMIT = "rate_limit"


# ---------------------------------------------------------------------------
# Reaction condition and rule
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ReactionCondition(ContractRecord):
    """A single predicate that must be true for a rule to fire.

    Conditions are evaluated against event payload and system state.
    field_path is a dot-separated path into the event payload.
    operator is one of: eq, neq, gt, gte, lt, lte, contains, in, exists.
    expected_value is the value to compare against.
    """

    condition_id: str
    field_path: str
    operator: str
    expected_value: Any

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "condition_id",
            require_non_empty_text(self.condition_id, "condition_id"),
        )
        object.__setattr__(
            self, "field_path",
            require_non_empty_text(self.field_path, "field_path"),
        )
        valid_ops = ("eq", "neq", "gt", "gte", "lt", "lte", "contains", "in", "exists")
        if self.operator not in valid_ops:
            raise ValueError("operator has unsupported value")
        object.__setattr__(self, "expected_value", freeze_value(self.expected_value))


@dataclass(frozen=True, slots=True)
class ReactionTarget(ContractRecord):
    """What a reaction rule intends to produce when it fires."""

    target_id: str
    kind: ReactionTargetKind
    target_ref_id: str
    parameters: Mapping[str, Any]

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "target_id",
            require_non_empty_text(self.target_id, "target_id"),
        )
        if not isinstance(self.kind, ReactionTargetKind):
            raise ValueError("kind must be a ReactionTargetKind value")
        object.__setattr__(
            self, "target_ref_id",
            require_non_empty_text(self.target_ref_id, "target_ref_id"),
        )
        object.__setattr__(self, "parameters", freeze_value(dict(self.parameters)))


@dataclass(frozen=True, slots=True)
class ReactionRule(ContractRecord):
    """A named rule binding event conditions to a reaction target.

    Rules are evaluated deterministically.  All conditions must match
    for the rule to fire.  The target describes what the reaction does.
    priority controls evaluation order (lower = higher priority).
    """

    rule_id: str
    name: str
    event_type: str
    conditions: tuple[ReactionCondition, ...]
    target: ReactionTarget
    priority: int = 0
    enabled: bool = True
    created_at: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "rule_id",
            require_non_empty_text(self.rule_id, "rule_id"),
        )
        object.__setattr__(
            self, "name",
            require_non_empty_text(self.name, "name"),
        )
        object.__setattr__(
            self, "event_type",
            require_non_empty_text(self.event_type, "event_type"),
        )
        if not isinstance(self.conditions, tuple):
            raise ValueError("conditions must be a tuple")
        if not self.conditions:
            raise ValueError("conditions must contain at least one ReactionCondition")
        for c in self.conditions:
            if not isinstance(c, ReactionCondition):
                raise ValueError("each condition must be a ReactionCondition")
        if not isinstance(self.target, ReactionTarget):
            raise ValueError("target must be a ReactionTarget")
        object.__setattr__(
            self, "priority",
            require_non_negative_int(self.priority, "priority"),
        )
        object.__setattr__(
            self, "created_at",
            require_datetime_text(self.created_at, "created_at"),
        )


# ---------------------------------------------------------------------------
# Decision gating record
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ReactionGateResult(ContractRecord):
    """Result of passing a candidate reaction through decision gating.

    Captures simulation, utility, and meta-reasoning assessments that
    informed the final verdict.
    """

    gate_id: str
    rule_id: str
    event_id: str
    verdict: ReactionVerdict
    simulation_safe: bool
    utility_acceptable: bool
    meta_reasoning_clear: bool
    confidence: float
    reason: str
    gated_at: str

    def __post_init__(self) -> None:
        for f in ("gate_id", "rule_id", "event_id", "reason"):
            object.__setattr__(self, f, require_non_empty_text(getattr(self, f), f))
        if not isinstance(self.verdict, ReactionVerdict):
            raise ValueError("verdict must be a ReactionVerdict value")
        object.__setattr__(
            self, "confidence",
            require_unit_float(self.confidence, "confidence"),
        )
        object.__setattr__(
            self, "gated_at",
            require_datetime_text(self.gated_at, "gated_at"),
        )


# ---------------------------------------------------------------------------
# Reaction execution record
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ReactionExecutionRecord(ContractRecord):
    """Immutable record of a reaction that was evaluated and possibly executed.

    Every reaction — whether it proceeded, was deferred, or was rejected —
    gets an execution record for full auditability.
    """

    execution_id: str
    rule_id: str
    event_id: str
    correlation_id: str
    target: ReactionTarget
    gate_result: ReactionGateResult
    executed: bool
    result_ref_id: str
    execution_notes: str
    executed_at: str

    def __post_init__(self) -> None:
        for f in ("execution_id", "rule_id", "event_id", "correlation_id"):
            object.__setattr__(self, f, require_non_empty_text(getattr(self, f), f))
        if not isinstance(self.target, ReactionTarget):
            raise ValueError("target must be a ReactionTarget")
        if not isinstance(self.gate_result, ReactionGateResult):
            raise ValueError("gate_result must be a ReactionGateResult")
        object.__setattr__(
            self, "executed_at",
            require_datetime_text(self.executed_at, "executed_at"),
        )


# ---------------------------------------------------------------------------
# Backpressure and idempotency
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class BackpressurePolicy(ContractRecord):
    """Bounds on how fast the reactive layer processes events.

    max_concurrent: maximum reactions executing simultaneously.
    max_per_window: maximum reactions in a time window.
    window_seconds: size of the rate-limiting window.
    strategy: what to do when limits are hit.
    """

    policy_id: str
    max_concurrent: int
    max_per_window: int
    window_seconds: int
    strategy: BackpressureStrategy

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "policy_id",
            require_non_empty_text(self.policy_id, "policy_id"),
        )
        object.__setattr__(
            self, "max_concurrent",
            require_positive_int(self.max_concurrent, "max_concurrent"),
        )
        object.__setattr__(
            self, "max_per_window",
            require_positive_int(self.max_per_window, "max_per_window"),
        )
        object.__setattr__(
            self, "window_seconds",
            require_positive_int(self.window_seconds, "window_seconds"),
        )
        if not isinstance(self.strategy, BackpressureStrategy):
            raise ValueError("strategy must be a BackpressureStrategy value")


@dataclass(frozen=True, slots=True)
class IdempotencyWindow(ContractRecord):
    """Tracks processed events to prevent duplicate reactions on replay.

    Each entry records that an event was already processed by a rule,
    so replaying the same event does not duplicate work.
    """

    window_id: str
    event_id: str
    rule_id: str
    execution_id: str
    processed_at: str
    expires_at: str

    def __post_init__(self) -> None:
        for f in ("window_id", "event_id", "rule_id", "execution_id"):
            object.__setattr__(self, f, require_non_empty_text(getattr(self, f), f))
        object.__setattr__(
            self, "processed_at",
            require_datetime_text(self.processed_at, "processed_at"),
        )
        object.__setattr__(
            self, "expires_at",
            require_datetime_text(self.expires_at, "expires_at"),
        )


@dataclass(frozen=True, slots=True)
class ReactionDecision(ContractRecord):
    """Top-level decision record summarizing a reactive cycle.

    One event may match multiple rules.  This record captures the
    full set of evaluations and the final outcome for each.
    """

    decision_id: str
    event_id: str
    correlation_id: str
    rules_evaluated: int
    rules_matched: int
    rules_executed: int
    rules_deferred: int
    rules_rejected: int
    executions: tuple[ReactionExecutionRecord, ...]
    decided_at: str

    def __post_init__(self) -> None:
        for f in ("decision_id", "event_id", "correlation_id"):
            object.__setattr__(self, f, require_non_empty_text(getattr(self, f), f))
        object.__setattr__(
            self, "rules_evaluated",
            require_non_negative_int(self.rules_evaluated, "rules_evaluated"),
        )
        object.__setattr__(
            self, "rules_matched",
            require_non_negative_int(self.rules_matched, "rules_matched"),
        )
        object.__setattr__(
            self, "rules_executed",
            require_non_negative_int(self.rules_executed, "rules_executed"),
        )
        object.__setattr__(
            self, "rules_deferred",
            require_non_negative_int(self.rules_deferred, "rules_deferred"),
        )
        object.__setattr__(
            self, "rules_rejected",
            require_non_negative_int(self.rules_rejected, "rules_rejected"),
        )
        if not isinstance(self.executions, tuple):
            raise ValueError("executions must be a tuple")
        for e in self.executions:
            if not isinstance(e, ReactionExecutionRecord):
                raise ValueError("each execution must be a ReactionExecutionRecord")
        object.__setattr__(
            self, "decided_at",
            require_datetime_text(self.decided_at, "decided_at"),
        )
