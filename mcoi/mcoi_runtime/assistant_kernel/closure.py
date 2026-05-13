"""Purpose: assistant goal closure contracts.
Governance scope: predicate completion, two-confirmation checks, evidence
    references, and terminal closure decisions.
Dependencies: dataclasses and runtime invariant helpers.
Test contract: tests/test_assistant_kernel.py.
Invariants:
  - Closure requires every declared predicate.
  - Two-confirmation mode requires two independent passed observations.
  - Signed evidence bundle presence is an explicit predicate.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from mcoi_runtime.assistant_kernel.goals import FINANCE_OPS_PAYMENT_CLOSURE_PREDICATES
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError, ensure_non_empty_text, stable_identifier


CLOSURE_STATUSES = ("passed", "failed", "unknown")


@dataclass(frozen=True, slots=True)
class ClosureObservation:
    """One observed predicate state for assistant closure."""

    observation_id: str
    predicate_id: str
    status: str
    observed_at: str
    evidence_refs: tuple[str, ...]
    source_ref: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "observation_id", ensure_non_empty_text("observation_id", self.observation_id))
        object.__setattr__(self, "predicate_id", ensure_non_empty_text("predicate_id", self.predicate_id))
        if self.status not in CLOSURE_STATUSES:
            raise RuntimeCoreInvariantError("closure status is not admitted")
        object.__setattr__(self, "observed_at", ensure_non_empty_text("observed_at", self.observed_at))
        object.__setattr__(self, "evidence_refs", _normalize_text_tuple(self.evidence_refs, "evidence_refs"))
        object.__setattr__(self, "metadata", dict(self.metadata))


@dataclass(frozen=True, slots=True)
class ClosureContract:
    """Predicate contract that must pass before an assistant goal closes."""

    contract_id: str
    goal_id: str
    required_predicates: tuple[str, ...]
    two_confirmation_required: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(self, "contract_id", ensure_non_empty_text("contract_id", self.contract_id))
        object.__setattr__(self, "goal_id", ensure_non_empty_text("goal_id", self.goal_id))
        object.__setattr__(
            self,
            "required_predicates",
            _normalize_text_tuple(self.required_predicates, "required_predicates"),
        )
        if not isinstance(self.two_confirmation_required, bool):
            raise RuntimeCoreInvariantError("two_confirmation_required must be boolean")


@dataclass(frozen=True, slots=True)
class ClosureEvaluation:
    """Closure decision for one assistant goal."""

    closed: bool
    reason: str
    missing_predicates: tuple[str, ...]
    unstable_predicates: tuple[str, ...]
    failed_predicates: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    confirmation_counts: dict[str, int]

    def __post_init__(self) -> None:
        object.__setattr__(self, "missing_predicates", tuple(self.missing_predicates))
        object.__setattr__(self, "unstable_predicates", tuple(self.unstable_predicates))
        object.__setattr__(self, "failed_predicates", tuple(self.failed_predicates))
        object.__setattr__(self, "evidence_refs", tuple(self.evidence_refs))
        object.__setattr__(self, "confirmation_counts", dict(self.confirmation_counts))


def finance_ops_payment_closure_contract(goal_id: str) -> ClosureContract:
    """Return the FinanceOps payment terminal closure contract."""
    return ClosureContract(
        contract_id=stable_identifier("assistant-closure-finance-payment", {"goal_id": goal_id}),
        goal_id=goal_id,
        required_predicates=FINANCE_OPS_PAYMENT_CLOSURE_PREDICATES,
        two_confirmation_required=True,
    )


def evaluate_closure(
    contract: ClosureContract,
    observations: tuple[ClosureObservation, ...],
) -> ClosureEvaluation:
    """Evaluate observations against a closure contract."""
    required = set(contract.required_predicates)
    failed = tuple(
        sorted({item.predicate_id for item in observations if item.predicate_id in required and item.status == "failed"})
    )
    passed_counts = {
        predicate: sum(1 for item in observations if item.predicate_id == predicate and item.status == "passed")
        for predicate in contract.required_predicates
    }
    required_count = 2 if contract.two_confirmation_required else 1
    missing = tuple(predicate for predicate, count in passed_counts.items() if count == 0)
    unstable = tuple(predicate for predicate, count in passed_counts.items() if 0 < count < required_count)
    evidence_refs = tuple(dict.fromkeys(ref for item in observations for ref in item.evidence_refs))
    if failed:
        return ClosureEvaluation(False, "closure_predicate_failed", missing, unstable, failed, evidence_refs, passed_counts)
    if missing:
        return ClosureEvaluation(False, "closure_predicate_missing", missing, unstable, (), evidence_refs, passed_counts)
    if unstable:
        return ClosureEvaluation(False, "closure_confirmation_unstable", (), unstable, (), evidence_refs, passed_counts)
    return ClosureEvaluation(True, "closure_verified", (), (), (), evidence_refs, passed_counts)


def closure_observation(
    *,
    predicate_id: str,
    status: str,
    observed_at: str,
    evidence_refs: tuple[str, ...],
    source_ref: str = "",
) -> ClosureObservation:
    """Create a stable closure observation record."""
    return ClosureObservation(
        observation_id=stable_identifier(
            "assistant-closure-observation",
            {
                "predicate_id": predicate_id,
                "status": status,
                "observed_at": observed_at,
                "source_ref": source_ref,
                "evidence_refs": evidence_refs,
            },
        ),
        predicate_id=predicate_id,
        status=status,
        observed_at=observed_at,
        evidence_refs=evidence_refs,
        source_ref=source_ref,
    )


def _normalize_text_tuple(values: tuple[str, ...], field_name: str) -> tuple[str, ...]:
    normalized = tuple(dict.fromkeys(str(value).strip() for value in values if str(value).strip()))
    if not normalized:
        raise RuntimeCoreInvariantError(f"{field_name} must contain at least one item")
    return normalized
