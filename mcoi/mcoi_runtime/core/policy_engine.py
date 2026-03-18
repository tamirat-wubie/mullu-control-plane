"""Purpose: deterministic policy evaluation for runtime-core requests.
Governance scope: runtime-core policy boundary only.
Dependencies: runtime-core invariant helpers.
Invariants: policy evaluation is deterministic, side-effect free, and separate from adapters and execution.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, Literal, Protocol, TypeVar

from .invariants import ensure_iso_timestamp, ensure_non_empty_text, stable_identifier

PolicyStatus = Literal["allow", "deny", "escalate"]
DecisionT = TypeVar("DecisionT")


@dataclass(frozen=True, slots=True)
class PolicyReason:
    code: str
    message: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "code", ensure_non_empty_text("code", self.code))
        object.__setattr__(self, "message", ensure_non_empty_text("message", self.message))


@dataclass(frozen=True, slots=True)
class PolicyInput:
    subject_id: str
    goal_id: str
    issued_at: str
    blocked_knowledge_ids: tuple[str, ...] = ()
    missing_capability_ids: tuple[str, ...] = ()
    requires_operator_review: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "subject_id", ensure_non_empty_text("subject_id", self.subject_id))
        object.__setattr__(self, "goal_id", ensure_non_empty_text("goal_id", self.goal_id))
        object.__setattr__(self, "issued_at", ensure_iso_timestamp("issued_at", self.issued_at))
        for value in self.blocked_knowledge_ids:
            ensure_non_empty_text("blocked_knowledge_id", value)
        for value in self.missing_capability_ids:
            ensure_non_empty_text("missing_capability_id", value)


class PolicyDecisionFactory(Protocol[DecisionT]):
    def __call__(
        self,
        *,
        decision_id: str,
        subject_id: str,
        goal_id: str,
        status: PolicyStatus,
        reasons: tuple[PolicyReason, ...],
        issued_at: str,
    ) -> DecisionT: ...


class PolicyEngine(Generic[DecisionT]):
    """Pure policy mapper that returns caller-supplied typed decision records."""

    def evaluate(
        self,
        policy_input: PolicyInput,
        decision_factory: PolicyDecisionFactory[DecisionT],
    ) -> DecisionT:
        reasons: tuple[PolicyReason, ...]
        status: PolicyStatus

        if policy_input.blocked_knowledge_ids:
            status = "deny"
            reasons = (
                PolicyReason(
                    code="blocked_knowledge",
                    message="blocked knowledge is present in the request",
                ),
            )
        elif policy_input.missing_capability_ids or policy_input.requires_operator_review:
            status = "escalate"
            reasons = (
                PolicyReason(
                    code="operator_review_required",
                    message="operator review is required before execution",
                ),
            )
        else:
            status = "allow"
            reasons = (
                PolicyReason(
                    code="policy_conditions_satisfied",
                    message="policy conditions are satisfied",
                ),
            )

        decision_id = stable_identifier(
            "policy",
            {
                "subject_id": policy_input.subject_id,
                "goal_id": policy_input.goal_id,
                "status": status,
                "blocked_knowledge_ids": policy_input.blocked_knowledge_ids,
                "missing_capability_ids": policy_input.missing_capability_ids,
                "requires_operator_review": policy_input.requires_operator_review,
                "issued_at": policy_input.issued_at,
            },
        )
        return decision_factory(
            decision_id=decision_id,
            subject_id=policy_input.subject_id,
            goal_id=policy_input.goal_id,
            status=status,
            reasons=reasons,
            issued_at=policy_input.issued_at,
        )
