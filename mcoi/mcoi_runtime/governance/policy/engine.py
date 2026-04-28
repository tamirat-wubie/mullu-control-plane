"""Purpose: deterministic policy evaluation for runtime-core requests.
Governance scope: runtime-core policy boundary only.
Dependencies: runtime-core invariant helpers.
Invariants: policy evaluation is deterministic, side-effect free, and separate from adapters and execution.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, Literal, Protocol, TypeVar, cast

from mcoi_runtime.core.invariants import ensure_iso_timestamp, ensure_non_empty_text, stable_identifier

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
    policy_pack_id: str | None = None
    policy_pack_version: str | None = None
    has_write_effects: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(self, "subject_id", ensure_non_empty_text("subject_id", self.subject_id))
        object.__setattr__(self, "goal_id", ensure_non_empty_text("goal_id", self.goal_id))
        object.__setattr__(self, "issued_at", ensure_iso_timestamp("issued_at", self.issued_at))
        for value in self.blocked_knowledge_ids:
            ensure_non_empty_text("blocked_knowledge_id", value)
        for value in self.missing_capability_ids:
            ensure_non_empty_text("missing_capability_id", value)
        if self.policy_pack_id is not None:
            object.__setattr__(
                self,
                "policy_pack_id",
                ensure_non_empty_text("policy_pack_id", self.policy_pack_id),
            )
        if self.policy_pack_version is not None:
            object.__setattr__(
                self,
                "policy_pack_version",
                ensure_non_empty_text("policy_pack_version", self.policy_pack_version),
            )


class PolicyRuleLike(Protocol):
    rule_id: str
    description: str
    condition: str
    action: str


class PolicyPackLike(Protocol):
    pack_id: str
    rules: tuple[PolicyRuleLike, ...]


class PolicyPackResolver(Protocol):
    def get(self, pack_id: str) -> PolicyPackLike | None: ...


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

    def __init__(self, *, pack_resolver: PolicyPackResolver | None = None) -> None:
        self._pack_resolver = pack_resolver

    def _evaluate_default_policy(self, policy_input: PolicyInput) -> tuple[PolicyStatus, tuple[PolicyReason, ...]]:
        if policy_input.blocked_knowledge_ids:
            return (
                "deny",
                (
                    PolicyReason(
                        code="blocked_knowledge",
                        message="blocked knowledge is present in the request",
                    ),
                ),
            )
        if policy_input.missing_capability_ids or policy_input.requires_operator_review:
            return (
                "escalate",
                (
                    PolicyReason(
                        code="operator_review_required",
                        message="operator review is required before execution",
                    ),
                ),
            )
        return (
            "allow",
            (
                PolicyReason(
                    code="policy_conditions_satisfied",
                    message="policy conditions are satisfied",
                ),
            ),
        )

    def _condition_matches(self, condition: str, policy_input: PolicyInput) -> bool:
        if condition == "always":
            return True
        if condition == "blocked_knowledge_present":
            return bool(policy_input.blocked_knowledge_ids)
        if condition == "missing_capabilities":
            return bool(policy_input.missing_capability_ids)
        if condition == "operator_review_required":
            return policy_input.requires_operator_review
        if condition == "has_write_effects":
            return policy_input.has_write_effects
        if condition == "read_only":
            return not policy_input.has_write_effects
        if condition == "all_conditions_satisfied":
            return (
                not policy_input.blocked_knowledge_ids
                and not policy_input.missing_capability_ids
                and not policy_input.requires_operator_review
            )
        return False

    def _evaluate_policy_pack(self, policy_input: PolicyInput) -> tuple[PolicyStatus, tuple[PolicyReason, ...]]:
        if self._pack_resolver is None or policy_input.policy_pack_id is None:
            return self._evaluate_default_policy(policy_input)

        pack = self._pack_resolver.get(policy_input.policy_pack_id)
        if pack is None:
            return (
                "deny",
                (
                    PolicyReason(
                        code="unknown_policy_pack",
                        message="policy pack unavailable",
                    ),
                ),
            )

        for rule in pack.rules:
            if self._condition_matches(rule.condition, policy_input):
                return (
                    cast(PolicyStatus, rule.action),
                    (
                        PolicyReason(
                            code=rule.rule_id,
                            message=rule.description,
                        ),
                    ),
                )

        return (
            "deny",
            (
                PolicyReason(
                    code="no_policy_rule_matched",
                    message="no policy rule matched",
                ),
            ),
        )

    def evaluate(
        self,
        policy_input: PolicyInput,
        decision_factory: PolicyDecisionFactory[DecisionT],
    ) -> DecisionT:
        status, reasons = self._evaluate_policy_pack(policy_input)

        decision_id = stable_identifier(
            "policy",
            {
                "subject_id": policy_input.subject_id,
                "goal_id": policy_input.goal_id,
                "status": status,
                "blocked_knowledge_ids": policy_input.blocked_knowledge_ids,
                "missing_capability_ids": policy_input.missing_capability_ids,
                "requires_operator_review": policy_input.requires_operator_review,
                "policy_pack_id": policy_input.policy_pack_id,
                "policy_pack_version": policy_input.policy_pack_version,
                "has_write_effects": policy_input.has_write_effects,
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
