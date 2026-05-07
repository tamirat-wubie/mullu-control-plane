"""Purpose: engineering puzzle kernel contracts for governed arrangement search.
Governance scope: episode framing, observer binding, candidate judgment, and
verification witness typing only.
Dependencies: shared contract base helpers.
Invariants:
  - Goal is immutable inside one episode and appears as goal:<goal> in invariants.
  - Observer is modeled as a governed node inside the puzzle boundary.
  - Candidate filter results are explicit for every ordered filter level.
  - Verified judgments require dual verification witness evidence.
  - History is carried as immutable append-only event tuples.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Mapping, Sequence

from ._base import (
    ContractRecord,
    freeze_value,
    require_finite_float,
    require_non_empty_text,
    require_non_empty_tuple,
    require_unit_float,
)


class EngineeringVerdict(StrEnum):
    """Closed verdict taxonomy for the engineering puzzle kernel."""

    SOLVED_VERIFIED = "SolvedVerified"
    SOLVED_UNVERIFIED = "SolvedUnverified"
    AWAITING_EVIDENCE = "AwaitingEvidence"
    GOVERNANCE_BLOCKED = "GovernanceBlocked"
    BUDGET_EXHAUSTED = "BudgetExhausted"
    IMPOSSIBLE_PROVED = "ImpossibleProved"
    MODEL_INVALIDATED = "ModelInvalidated"
    SAFE_HALT = "SafeHalt"
    GOAL_MUTATED = "GoalMutated"
    AWAITING_NEW_EPISODE = "AwaitingNewEpisode"


class FilterLevel(StrEnum):
    """Ordered candidate filter stack levels."""

    L0_FEASIBILITY = "L0_feasibility"
    L1_IDENTITY = "L1_identity"
    L2_SURVIVAL = "L2_survival"
    L3_NORMATIVE = "L3_normative"
    L4_INTERFACE = "L4_interface"
    L5_OPTIMIZATION = "L5_optimization"
    L6_LEARNING = "L6_learning"


class GoalDeltaKind(StrEnum):
    """Classification of a goal text change inside an episode."""

    CLARIFICATION = "clarification"
    MUTATION = "mutation"


FILTER_STACK_LEVELS: tuple[FilterLevel, ...] = (
    FilterLevel.L0_FEASIBILITY,
    FilterLevel.L1_IDENTITY,
    FilterLevel.L2_SURVIVAL,
    FilterLevel.L3_NORMATIVE,
    FilterLevel.L4_INTERFACE,
    FilterLevel.L5_OPTIMIZATION,
    FilterLevel.L6_LEARNING,
)


def _freeze_text_tuple(values: Sequence[str], field_name: str) -> tuple[str, ...]:
    frozen = require_non_empty_tuple(values, field_name)
    for item in frozen:
        require_non_empty_text(item, field_name)
    return frozen


def _freeze_optional_text_tuple(
    values: Sequence[str],
    field_name: str,
) -> tuple[str, ...]:
    frozen = freeze_value(list(values))
    if not isinstance(frozen, tuple):
        raise ValueError(f"{field_name} must be a sequence")
    for item in frozen:
        require_non_empty_text(item, field_name)
    return frozen


def _freeze_mapping(value: Mapping[str, Any], field_name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field_name} must be a mapping")
    return freeze_value(value)


def _freeze_history(
    history: Sequence[Mapping[str, Any]],
) -> tuple[Mapping[str, Any], ...]:
    frozen = freeze_value(list(history))
    if not isinstance(frozen, tuple):
        raise ValueError("history must be a sequence")
    for event in frozen:
        if not isinstance(event, Mapping):
            raise ValueError("history events must be mappings")
        require_non_empty_text(str(event.get("event", "")), "history.event")
    return frozen


def _normalize_filter_results(
    results: Mapping[str | FilterLevel, bool],
) -> Mapping[str, bool]:
    if not isinstance(results, Mapping):
        raise ValueError("filter_results must be a mapping")

    normalized: dict[str, bool] = {}
    for key, value in results.items():
        try:
            level = key if isinstance(key, FilterLevel) else FilterLevel(str(key))
        except ValueError as exc:
            raise ValueError(f"unknown filter level: {key}") from exc
        if not isinstance(value, bool):
            raise ValueError(f"filter result {level.value} must be a boolean")
        normalized[level.value] = value

    required = {level.value for level in FILTER_STACK_LEVELS}
    actual = set(normalized)
    if actual != required:
        missing = sorted(required - actual)
        extra = sorted(actual - required)
        raise ValueError(
            f"filter_results must declare every filter level; "
            f"missing={missing}, extra={extra}"
        )
    return freeze_value(normalized)


@dataclass(frozen=True, slots=True)
class ObserverNode(ContractRecord):
    """Architect/observer node bound inside the engineering puzzle."""

    observer_id: str
    invariants: tuple[str, ...]
    rules: tuple[str, ...]
    assumptions: tuple[str, ...]
    known_unknowns: tuple[str, ...]
    risk_margins: tuple[str, ...]
    fragile_points: tuple[str, ...]
    interfaces: tuple[str, ...]
    history_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "observer_id",
            require_non_empty_text(self.observer_id, "observer_id"),
        )
        object.__setattr__(self, "invariants", _freeze_text_tuple(self.invariants, "invariants"))
        object.__setattr__(self, "rules", _freeze_text_tuple(self.rules, "rules"))
        object.__setattr__(self, "assumptions", _freeze_text_tuple(self.assumptions, "assumptions"))
        object.__setattr__(
            self,
            "known_unknowns",
            _freeze_optional_text_tuple(self.known_unknowns, "known_unknowns"),
        )
        object.__setattr__(
            self,
            "risk_margins",
            _freeze_optional_text_tuple(self.risk_margins, "risk_margins"),
        )
        object.__setattr__(
            self,
            "fragile_points",
            _freeze_optional_text_tuple(self.fragile_points, "fragile_points"),
        )
        object.__setattr__(self, "interfaces", _freeze_text_tuple(self.interfaces, "interfaces"))
        object.__setattr__(
            self,
            "history_refs",
            _freeze_optional_text_tuple(self.history_refs, "history_refs"),
        )


@dataclass(frozen=True, slots=True)
class VerificationWitness(ContractRecord):
    """Dual-channel evidence comparing model prediction with observation."""

    witness_id: str
    model_evidence: tuple[str, ...]
    observation_evidence: tuple[str, ...]
    prediction: str
    observation: str
    mismatch_margin: float
    threshold: float
    passed: bool

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "witness_id",
            require_non_empty_text(self.witness_id, "witness_id"),
        )
        object.__setattr__(
            self,
            "model_evidence",
            _freeze_text_tuple(self.model_evidence, "model_evidence"),
        )
        object.__setattr__(
            self,
            "observation_evidence",
            _freeze_text_tuple(self.observation_evidence, "observation_evidence"),
        )
        object.__setattr__(self, "prediction", require_non_empty_text(self.prediction, "prediction"))
        object.__setattr__(self, "observation", require_non_empty_text(self.observation, "observation"))
        object.__setattr__(
            self,
            "mismatch_margin",
            require_finite_float(self.mismatch_margin, "mismatch_margin"),
        )
        object.__setattr__(self, "threshold", require_unit_float(self.threshold, "threshold"))
        if not isinstance(self.passed, bool):
            raise ValueError("passed must be a boolean")
        if self.passed and self.mismatch_margin > self.threshold:
            raise ValueError("passed witness cannot exceed threshold")


@dataclass(frozen=True, slots=True)
class JudgmentEnvelope(ContractRecord):
    """Full judgment envelope returned by the engineering kernel."""

    verdict: EngineeringVerdict
    confidence: float
    margin: float | None
    fragile: bool
    assumptions: tuple[str, ...]
    unknowns: tuple[str, ...]
    rejected_alternatives: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.verdict, EngineeringVerdict):
            raise ValueError("verdict must be an EngineeringVerdict value")
        object.__setattr__(self, "confidence", require_unit_float(self.confidence, "confidence"))
        if self.margin is not None:
            object.__setattr__(self, "margin", require_finite_float(self.margin, "margin"))
        if not isinstance(self.fragile, bool):
            raise ValueError("fragile must be a boolean")
        object.__setattr__(
            self,
            "assumptions",
            _freeze_optional_text_tuple(self.assumptions, "assumptions"),
        )
        object.__setattr__(
            self,
            "unknowns",
            _freeze_optional_text_tuple(self.unknowns, "unknowns"),
        )
        object.__setattr__(
            self,
            "rejected_alternatives",
            _freeze_optional_text_tuple(self.rejected_alternatives, "rejected_alternatives"),
        )


@dataclass(frozen=True, slots=True)
class EngineeringPuzzle(ContractRecord):
    """Frozen episode model for governed arrangement search."""

    invariants: tuple[str, ...]
    rules: tuple[str, ...]
    state: Mapping[str, Any]
    interfaces: tuple[str, ...]
    history: tuple[Mapping[str, Any], ...]
    goal: str
    episode_model_hash: str
    observer: ObserverNode
    witness: VerificationWitness | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "invariants", _freeze_text_tuple(self.invariants, "invariants"))
        object.__setattr__(self, "rules", _freeze_text_tuple(self.rules, "rules"))
        object.__setattr__(self, "state", _freeze_mapping(self.state, "state"))
        object.__setattr__(self, "interfaces", _freeze_text_tuple(self.interfaces, "interfaces"))
        object.__setattr__(self, "history", _freeze_history(self.history))
        object.__setattr__(self, "goal", require_non_empty_text(self.goal, "goal"))
        object.__setattr__(
            self,
            "episode_model_hash",
            require_non_empty_text(self.episode_model_hash, "episode_model_hash"),
        )
        if f"goal:{self.goal}" not in self.invariants:
            raise ValueError("invariants must include goal:<goal>")
        if not isinstance(self.observer, ObserverNode):
            raise ValueError("observer must be an ObserverNode instance")
        if self.witness is not None and not isinstance(self.witness, VerificationWitness):
            raise ValueError("witness must be a VerificationWitness instance")


@dataclass(frozen=True, slots=True)
class CandidateArrangement(ContractRecord):
    """Proposed state delta plus all governance and verification promises."""

    candidate_id: str
    state_delta: Mapping[str, Any]
    filter_results: Mapping[str | FilterLevel, bool]
    confidence: float
    authority_ref: str
    governance_certified: bool
    rollback_plan: str
    verification_plan: str
    assumptions: tuple[str, ...] = ()
    unknowns: tuple[str, ...] = ()
    rejected_alternatives: tuple[str, ...] = ()
    fragile: bool = False
    witness: VerificationWitness | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "candidate_id",
            require_non_empty_text(self.candidate_id, "candidate_id"),
        )
        object.__setattr__(self, "state_delta", _freeze_mapping(self.state_delta, "state_delta"))
        object.__setattr__(
            self,
            "filter_results",
            _normalize_filter_results(self.filter_results),
        )
        object.__setattr__(self, "confidence", require_unit_float(self.confidence, "confidence"))
        if self.authority_ref:
            object.__setattr__(
                self,
                "authority_ref",
                require_non_empty_text(self.authority_ref, "authority_ref"),
            )
        if not isinstance(self.governance_certified, bool):
            raise ValueError("governance_certified must be a boolean")
        if self.governance_certified and not self.authority_ref:
            raise ValueError("authority_ref is required when governance_certified is true")
        object.__setattr__(self, "rollback_plan", require_non_empty_text(self.rollback_plan, "rollback_plan"))
        object.__setattr__(
            self,
            "verification_plan",
            require_non_empty_text(self.verification_plan, "verification_plan"),
        )
        object.__setattr__(
            self,
            "assumptions",
            _freeze_optional_text_tuple(self.assumptions, "assumptions"),
        )
        object.__setattr__(self, "unknowns", _freeze_optional_text_tuple(self.unknowns, "unknowns"))
        object.__setattr__(
            self,
            "rejected_alternatives",
            _freeze_optional_text_tuple(self.rejected_alternatives, "rejected_alternatives"),
        )
        if not isinstance(self.fragile, bool):
            raise ValueError("fragile must be a boolean")
        if self.witness is not None and not isinstance(self.witness, VerificationWitness):
            raise ValueError("witness must be a VerificationWitness instance")


@dataclass(frozen=True, slots=True)
class FilterEvaluation(ContractRecord):
    """Result of evaluating the ordered filter stack."""

    passed: bool
    evaluated_levels: tuple[FilterLevel, ...]
    failed_level: FilterLevel | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.passed, bool):
            raise ValueError("passed must be a boolean")
        frozen = freeze_value(list(self.evaluated_levels))
        if not isinstance(frozen, tuple):
            raise ValueError("evaluated_levels must be a sequence")
        for level in frozen:
            if not isinstance(level, FilterLevel):
                raise ValueError("evaluated_levels must contain FilterLevel values")
        object.__setattr__(self, "evaluated_levels", frozen)
        if self.failed_level is not None and not isinstance(self.failed_level, FilterLevel):
            raise ValueError("failed_level must be a FilterLevel value")
        if self.passed and self.failed_level is not None:
            raise ValueError("passed evaluation cannot have failed_level")
        if not self.passed and self.failed_level is None:
            raise ValueError("failed evaluation must declare failed_level")


@dataclass(frozen=True, slots=True)
class GoalDeltaDecision(ContractRecord):
    """Decision produced when a proposed goal delta is evaluated."""

    kind: GoalDeltaKind
    active_puzzle: EngineeringPuzzle
    judgment: JudgmentEnvelope
    closed_puzzle: EngineeringPuzzle | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.kind, GoalDeltaKind):
            raise ValueError("kind must be a GoalDeltaKind value")
        if not isinstance(self.active_puzzle, EngineeringPuzzle):
            raise ValueError("active_puzzle must be an EngineeringPuzzle instance")
        if not isinstance(self.judgment, JudgmentEnvelope):
            raise ValueError("judgment must be a JudgmentEnvelope instance")
        if self.closed_puzzle is not None and not isinstance(self.closed_puzzle, EngineeringPuzzle):
            raise ValueError("closed_puzzle must be an EngineeringPuzzle instance")
