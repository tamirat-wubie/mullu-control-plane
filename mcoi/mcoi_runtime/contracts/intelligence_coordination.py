"""Purpose: intelligence coordination contracts for constraint-first reasoning.
Governance scope: symbolic intelligence episode typing, method arbitration proofs,
    constraint satisfiability reports, counterfactual branches, and world-model deltas.
Dependencies: shared contract base helpers only.
Invariants:
  - Hard constraints with Unknown or Fail block execution.
  - Method selection is explicit and proof-carrying.
  - Counterfactual branches reference immutable baseline snapshots.
  - World-model deltas are evidence-bound and governance-bound.
  - No coordination artifact silently hides uncertainty or rejected methods.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Mapping, TypeVar, cast

from ._base import (
    ContractRecord,
    freeze_value,
    require_datetime_text,
    require_non_empty_text,
    require_non_negative_float,
    require_non_negative_int,
    require_unit_float,
)


ContractT = TypeVar("ContractT", bound=ContractRecord)


def _freeze_text_array(
    values: object,
    field_name: str,
    *,
    allow_empty: bool = True,
) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)) or not isinstance(values, (tuple, list)):
        raise ValueError(f"{field_name} must be an array")
    frozen = cast(tuple[Any, ...], freeze_value(list(values)))
    if not allow_empty and not frozen:
        raise ValueError(f"{field_name} must contain at least one item")
    for idx, value in enumerate(frozen):
        require_non_empty_text(value, f"{field_name}[{idx}]")
    if len(set(frozen)) != len(frozen):
        raise ValueError(f"{field_name} must contain unique values")
    return cast(tuple[str, ...], frozen)


def _freeze_contract_array(
    values: object,
    field_name: str,
    record_type: type[ContractT],
    *,
    allow_empty: bool = True,
) -> tuple[ContractT, ...]:
    if isinstance(values, (str, bytes)) or not isinstance(values, (tuple, list)):
        raise ValueError(f"{field_name} must be an array")
    frozen = cast(tuple[Any, ...], freeze_value(list(values)))
    if not allow_empty and not frozen:
        raise ValueError(f"{field_name} must contain at least one item")
    for idx, value in enumerate(frozen):
        if not isinstance(value, record_type):
            raise ValueError(f"{field_name}[{idx}] must be a {record_type.__name__}")
    return cast(tuple[ContractT, ...], frozen)


class ProofState(StrEnum):
    """Typed uncertainty state for governed reasoning."""

    PASS = "Pass"
    FAIL = "Fail"
    UNKNOWN = "Unknown"
    BUDGET_UNKNOWN = "BudgetUnknown"


class SolverTerminalOutcome(StrEnum):
    """Terminal outcome taxonomy for coordination episodes."""

    SOLVED_VERIFIED = "SolvedVerified"
    SOLVED_UNVERIFIED = "SolvedUnverified"
    AWAITING_EVIDENCE = "AwaitingEvidence"
    SAFE_HALT = "SafeHalt"
    GOVERNANCE_BLOCKED = "GovernanceBlocked"
    BUDGET_EXHAUSTED = "BudgetExhausted"
    IMPOSSIBLE_PROVED = "ImpossibleProved"
    MODEL_INVALIDATED = "ModelInvalidated"


class OrchestrationReadinessVerdict(StrEnum):
    """Aggregate readiness verdict before execution."""

    READY = "ready"
    REPLAN_REQUIRED = "replan_required"
    BLOCKED = "blocked"


class CoordinationConstraintKind(StrEnum):
    """Constraint categories evaluated by the coordination kernel."""

    HARD_LAW = "hard_law"
    HARD_PHYSICAL = "hard_physical"
    TEMPORAL = "temporal"
    CAUSAL = "causal"
    INTERFACE = "interface"
    RESOURCE = "resource"
    SOFT_UTILITY = "soft_utility"


class MethodProblemSignature(StrEnum):
    """Problem shapes used by method arbitration."""

    BOOLEAN_FEASIBILITY = "boolean_feasibility"
    LINEAR_RESOURCE_ALLOCATION = "linear_resource_allocation"
    ORDERED_SCHEDULING = "ordered_scheduling"
    SYMBOL_REWRITE = "symbol_rewrite"
    GRAPH_DEPENDENCY = "graph_dependency"
    CAUSAL_DIAGNOSIS = "causal_diagnosis"
    LOCAL_SEARCH_LANDSCAPE = "local_search_landscape"
    HIGH_UNCERTAINTY_FORECAST = "high_uncertainty_forecast"


class MethodFamily(StrEnum):
    """Reasoning method family selected for a problem signature."""

    SAT = "sat"
    ILP = "ilp"
    TEMPORAL_PROPAGATION = "temporal_propagation"
    REWRITE_SYSTEM = "rewrite_system"
    GRAPH_METHOD = "graph_method"
    CAUSAL_GRAPH = "causal_graph"
    BOUNDED_SEARCH = "bounded_search"
    PROBABILISTIC_MODEL = "probabilistic_model"


class FailureSeverity(StrEnum):
    """Severity of a projected failure path."""

    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    CRITICAL = "critical"


class DiagnosisSeverity(StrEnum):
    """Severity of an episode-local self-diagnosis finding."""

    INFO = "info"
    WARNING = "warning"
    BLOCKING = "blocking"


class ReplanTrigger(StrEnum):
    """Trigger that caused adaptive planning to request a new plan."""

    NONE = "none"
    UNCERTAINTY_HIGH = "uncertainty_high"
    DIAGNOSIS_BLOCKING = "diagnosis_blocking"
    FAILURE_BLOCKED = "failure_blocked"
    SAFETY_MARGIN_LOW = "safety_margin_low"
    RESOURCE_PRESSURE_HIGH = "resource_pressure_high"
    RESOURCE_EXHAUSTED = "resource_exhausted"


class TemporalCheckStatus(StrEnum):
    """Status for an episode-local temporal ordering check."""

    ORDERED = "ordered"
    VIOLATED = "violated"
    INCOMPLETE = "incomplete"


class CausalDynamicsStatus(StrEnum):
    """Status for an episode-local causal graph dynamics check."""

    ACYCLIC = "acyclic"
    FEEDBACK_PRESENT = "feedback_present"
    DISCONNECTED = "disconnected"


class AbstractionScale(StrEnum):
    """Abstraction scale for episode-local symbolic layers."""

    MICRO = "micro"
    MESO = "meso"
    MACRO = "macro"


class AbstractionControlStatus(StrEnum):
    """Status for abstraction-scale coverage and boundary checks."""

    CONSISTENT = "consistent"
    GAP_PRESENT = "gap_present"
    COLLAPSED = "collapsed"


class CoordinationResourceKind(StrEnum):
    """Bounded resource kinds tracked during coordination."""

    COMPUTE = "compute"
    MEMORY = "memory"
    TIME = "time"
    ATTENTION = "attention"


class ResourceBoundStatus(StrEnum):
    """Status for explicit resource budget usage."""

    NORMAL = "normal"
    DEGRADED = "degraded"
    EXHAUSTED = "exhausted"
    OVERRUN = "overrun"


class SemanticGroundingKind(StrEnum):
    """Grounding target kind for a symbol."""

    OBSERVABLE_STATE = "observable_state"
    EXECUTABLE_ACTION = "executable_action"
    MEASURABLE_CONSEQUENCE = "measurable_consequence"
    PHYSICAL_EFFECT = "physical_effect"


class SemanticGroundingStatus(StrEnum):
    """Status for symbol grounding coverage."""

    GROUNDED = "grounded"
    PARTIAL = "partial"
    UNGROUNDED = "ungrounded"


class PerspectiveKind(StrEnum):
    """Perspective lens used for multi-perspective reasoning."""

    MODEL = "model"
    ASSUMPTION = "assumption"
    INCENTIVE = "incentive"
    SCALE = "scale"


class PerspectiveComparisonStatus(StrEnum):
    """Status for perspective coverage and disagreement."""

    ALIGNED = "aligned"
    DIVERGENT = "divergent"
    UNDERCOVERED = "undercovered"


class PatternDiscoveryStatus(StrEnum):
    """Status for compression and reusable structure discovery."""

    STABLE = "stable"
    REDUNDANT = "redundant"
    UNDERCOMPRESSED = "undercompressed"


class CorrectionActionKind(StrEnum):
    """Self-correction action kind for post-episode repair."""

    CONTRADICTION_REPAIR = "contradiction_repair"
    ROLLBACK = "rollback"
    REPLAN = "replan"
    EVIDENCE_REQUEST = "evidence_request"


class CorrectionRepairStatus(StrEnum):
    """Status for correction and repair readiness."""

    CLEAN = "clean"
    REPAIR_RECOMMENDED = "repair_recommended"
    ROLLBACK_RECOMMENDED = "rollback_recommended"


class WorldContinuityStatus(StrEnum):
    """Status for dynamic world-model continuity."""

    CONTINUOUS = "continuous"
    FRAGMENTED = "fragmented"
    IDENTITY_DRIFT = "identity_drift"


@dataclass(frozen=True, slots=True)
class CoordinationConstraint(ContractRecord):
    """A proof-state-bearing constraint assertion consumed by the kernel."""

    constraint_id: str
    kind: CoordinationConstraintKind
    proof_state: ProofState
    statement: str
    source_refs: tuple[str, ...]
    dependency_ids: tuple[str, ...] = ()
    reason_code: str | None = None
    evaluated_at: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "constraint_id", require_non_empty_text(self.constraint_id, "constraint_id"))
        if not isinstance(self.kind, CoordinationConstraintKind):
            raise ValueError("kind must be a CoordinationConstraintKind value")
        if not isinstance(self.proof_state, ProofState):
            raise ValueError("proof_state must be a ProofState value")
        object.__setattr__(self, "statement", require_non_empty_text(self.statement, "statement"))
        object.__setattr__(self, "source_refs", _freeze_text_array(self.source_refs, "source_refs", allow_empty=False))
        object.__setattr__(self, "dependency_ids", _freeze_text_array(self.dependency_ids, "dependency_ids"))
        if self.reason_code is not None:
            object.__setattr__(self, "reason_code", require_non_empty_text(self.reason_code, "reason_code"))
        if self.evaluated_at is not None:
            object.__setattr__(self, "evaluated_at", require_datetime_text(self.evaluated_at, "evaluated_at"))

    @property
    def is_hard(self) -> bool:
        return self.kind != CoordinationConstraintKind.SOFT_UTILITY


@dataclass(frozen=True, slots=True)
class ConstraintSatisfiabilityReport(ContractRecord):
    """Kernel output that records satisfied, violated, unknown, and blocked constraints."""

    report_id: str
    evaluated_constraint_ids: tuple[str, ...]
    satisfied_constraint_ids: tuple[str, ...]
    violated_constraint_ids: tuple[str, ...]
    unknown_constraint_ids: tuple[str, ...]
    propagated_dependencies: tuple[str, ...]
    contradiction_record_ids: tuple[str, ...]
    blocked_branch_ids: tuple[str, ...]
    proof_state: ProofState
    terminal_outcome: SolverTerminalOutcome
    generated_at: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "report_id", require_non_empty_text(self.report_id, "report_id"))
        for field_name in (
            "evaluated_constraint_ids",
            "satisfied_constraint_ids",
            "violated_constraint_ids",
            "unknown_constraint_ids",
            "propagated_dependencies",
            "contradiction_record_ids",
            "blocked_branch_ids",
        ):
            object.__setattr__(self, field_name, _freeze_text_array(getattr(self, field_name), field_name))
        if not isinstance(self.proof_state, ProofState):
            raise ValueError("proof_state must be a ProofState value")
        if not isinstance(self.terminal_outcome, SolverTerminalOutcome):
            raise ValueError("terminal_outcome must be a SolverTerminalOutcome value")
        object.__setattr__(self, "generated_at", require_datetime_text(self.generated_at, "generated_at"))


@dataclass(frozen=True, slots=True)
class MethodCandidate(ContractRecord):
    """A candidate method considered by the arbiter."""

    method_id: str
    family: MethodFamily
    compatible_signatures: tuple[MethodProblemSignature, ...]
    estimated_cost: float
    confidence: float
    resource_requirement: float = 0.0

    def __post_init__(self) -> None:
        object.__setattr__(self, "method_id", require_non_empty_text(self.method_id, "method_id"))
        if not isinstance(self.family, MethodFamily):
            raise ValueError("family must be a MethodFamily value")
        if isinstance(self.compatible_signatures, (str, bytes)) or not isinstance(
            self.compatible_signatures, (tuple, list)
        ):
            raise ValueError("compatible_signatures must be an array")
        frozen = tuple(self.compatible_signatures)
        if not frozen:
            raise ValueError("compatible_signatures must contain at least one item")
        for idx, signature in enumerate(frozen):
            if not isinstance(signature, MethodProblemSignature):
                raise ValueError(f"compatible_signatures[{idx}] must be a MethodProblemSignature value")
        if len(set(frozen)) != len(frozen):
            raise ValueError("compatible_signatures must contain unique values")
        object.__setattr__(self, "compatible_signatures", frozen)
        object.__setattr__(self, "estimated_cost", require_non_negative_float(self.estimated_cost, "estimated_cost"))
        object.__setattr__(self, "confidence", require_unit_float(self.confidence, "confidence"))
        object.__setattr__(
            self,
            "resource_requirement",
            require_non_negative_float(self.resource_requirement, "resource_requirement"),
        )


@dataclass(frozen=True, slots=True)
class MethodArbitrationProof(ContractRecord):
    """Proof that records selected and rejected reasoning methods."""

    proof_id: str
    problem_signature: MethodProblemSignature
    selected_method_id: str
    candidate_method_ids: tuple[str, ...]
    rejected_method_ids: tuple[str, ...]
    rejection_reasons: Mapping[str, str]
    selected_score: float
    resource_budget: float
    decided_at: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "proof_id", require_non_empty_text(self.proof_id, "proof_id"))
        if not isinstance(self.problem_signature, MethodProblemSignature):
            raise ValueError("problem_signature must be a MethodProblemSignature value")
        object.__setattr__(self, "selected_method_id", require_non_empty_text(self.selected_method_id, "selected_method_id"))
        object.__setattr__(
            self,
            "candidate_method_ids",
            _freeze_text_array(self.candidate_method_ids, "candidate_method_ids", allow_empty=False),
        )
        object.__setattr__(self, "rejected_method_ids", _freeze_text_array(self.rejected_method_ids, "rejected_method_ids"))
        if self.selected_method_id not in self.candidate_method_ids:
            raise ValueError("selected_method_id must be present in candidate_method_ids")
        if self.selected_method_id in self.rejected_method_ids:
            raise ValueError("selected_method_id must not be rejected")
        missing_reasons = set(self.rejected_method_ids) - set(self.rejection_reasons)
        if missing_reasons:
            raise ValueError("every rejected method requires a rejection reason")
        for method_id, reason in self.rejection_reasons.items():
            require_non_empty_text(method_id, "method_id")
            require_non_empty_text(reason, "reason")
        object.__setattr__(self, "rejection_reasons", freeze_value(dict(self.rejection_reasons)))
        object.__setattr__(self, "selected_score", require_unit_float(self.selected_score, "selected_score"))
        object.__setattr__(self, "resource_budget", require_non_negative_float(self.resource_budget, "resource_budget"))
        object.__setattr__(self, "decided_at", require_datetime_text(self.decided_at, "decided_at"))


@dataclass(frozen=True, slots=True)
class CounterfactualBranch(ContractRecord):
    """A simulated intervention branch that does not mutate baseline state."""

    branch_id: str
    baseline_snapshot_ref: str
    intervention: str
    affected_entity_ids: tuple[str, ...]
    affected_relation_ids: tuple[str, ...]
    predicted_delta_refs: tuple[str, ...]
    reversible_step_ids: tuple[str, ...]
    irreversible_risk_ids: tuple[str, ...]
    confidence_lower: float
    confidence_upper: float

    def __post_init__(self) -> None:
        for field_name in ("branch_id", "baseline_snapshot_ref", "intervention"):
            object.__setattr__(self, field_name, require_non_empty_text(getattr(self, field_name), field_name))
        for field_name in (
            "affected_entity_ids",
            "affected_relation_ids",
            "predicted_delta_refs",
            "reversible_step_ids",
            "irreversible_risk_ids",
        ):
            object.__setattr__(self, field_name, _freeze_text_array(getattr(self, field_name), field_name))
        object.__setattr__(self, "confidence_lower", require_unit_float(self.confidence_lower, "confidence_lower"))
        object.__setattr__(self, "confidence_upper", require_unit_float(self.confidence_upper, "confidence_upper"))
        if self.confidence_lower > self.confidence_upper:
            raise ValueError("confidence_lower must be <= confidence_upper")


@dataclass(frozen=True, slots=True)
class GovernedWorldModelDelta(ContractRecord):
    """Evidence-bound world-model delta proposed by a coordination episode."""

    delta_id: str
    source_episode_id: str
    source_evidence_ids: tuple[str, ...]
    prior_snapshot_ref: str
    proposed_entity_change_refs: tuple[str, ...]
    proposed_relation_change_refs: tuple[str, ...]
    proposed_confidence_change_refs: tuple[str, ...]
    contradictions_created: tuple[str, ...]
    contradictions_resolved: tuple[str, ...]
    governance_decision_ref: str

    def __post_init__(self) -> None:
        for field_name in ("delta_id", "source_episode_id", "prior_snapshot_ref", "governance_decision_ref"):
            object.__setattr__(self, field_name, require_non_empty_text(getattr(self, field_name), field_name))
        object.__setattr__(
            self,
            "source_evidence_ids",
            _freeze_text_array(self.source_evidence_ids, "source_evidence_ids", allow_empty=False),
        )
        for field_name in (
            "proposed_entity_change_refs",
            "proposed_relation_change_refs",
            "proposed_confidence_change_refs",
            "contradictions_created",
            "contradictions_resolved",
        ):
            object.__setattr__(self, field_name, _freeze_text_array(getattr(self, field_name), field_name))


@dataclass(frozen=True, slots=True)
class FailureMode(ContractRecord):
    """A projected failure path with trigger, cascade, and mitigation trace."""

    failure_id: str
    source_ref: str
    severity: FailureSeverity
    trigger_constraint_ids: tuple[str, ...]
    affected_entity_ids: tuple[str, ...]
    cascade_failure_ids: tuple[str, ...]
    hidden_assumption_ids: tuple[str, ...]
    invariant_violation_ids: tuple[str, ...]
    mitigation_refs: tuple[str, ...]
    likelihood: float
    impact: float
    reversible: bool
    detected_at: str

    def __post_init__(self) -> None:
        for field_name in ("failure_id", "source_ref"):
            object.__setattr__(self, field_name, require_non_empty_text(getattr(self, field_name), field_name))
        if not isinstance(self.severity, FailureSeverity):
            raise ValueError("severity must be a FailureSeverity value")
        for field_name in (
            "trigger_constraint_ids",
            "affected_entity_ids",
            "cascade_failure_ids",
            "hidden_assumption_ids",
            "invariant_violation_ids",
            "mitigation_refs",
        ):
            object.__setattr__(self, field_name, _freeze_text_array(getattr(self, field_name), field_name))
        if not self.trigger_constraint_ids and not self.hidden_assumption_ids and not self.invariant_violation_ids:
            raise ValueError("failure mode requires a trigger constraint, hidden assumption, or invariant violation")
        object.__setattr__(self, "likelihood", require_unit_float(self.likelihood, "likelihood"))
        object.__setattr__(self, "impact", require_unit_float(self.impact, "impact"))
        if not isinstance(self.reversible, bool):
            raise ValueError("reversible must be a bool")
        object.__setattr__(self, "detected_at", require_datetime_text(self.detected_at, "detected_at"))


@dataclass(frozen=True, slots=True)
class FailureReasoningMap(ContractRecord):
    """Episode-local failure map produced before execution planning."""

    map_id: str
    source_episode_id: str
    failure_modes: tuple[FailureMode, ...]
    blocked_failure_ids: tuple[str, ...]
    dominant_failure_id: str | None
    residual_risk: float
    generated_at: str

    def __post_init__(self) -> None:
        for field_name in ("map_id", "source_episode_id"):
            object.__setattr__(self, field_name, require_non_empty_text(getattr(self, field_name), field_name))
        object.__setattr__(
            self,
            "failure_modes",
            _freeze_contract_array(self.failure_modes, "failure_modes", FailureMode),
        )
        failure_ids = {failure.failure_id for failure in self.failure_modes}
        if len(failure_ids) != len(self.failure_modes):
            raise ValueError("failure_modes must declare unique failure_id values")
        object.__setattr__(self, "blocked_failure_ids", _freeze_text_array(self.blocked_failure_ids, "blocked_failure_ids"))
        unknown_blocked = set(self.blocked_failure_ids) - failure_ids
        if unknown_blocked:
            raise ValueError("blocked_failure_ids must reference failure modes")
        if self.dominant_failure_id is not None:
            object.__setattr__(
                self,
                "dominant_failure_id",
                require_non_empty_text(self.dominant_failure_id, "dominant_failure_id"),
            )
            if self.dominant_failure_id not in failure_ids:
                raise ValueError("dominant_failure_id must reference a failure mode")
        object.__setattr__(self, "residual_risk", require_unit_float(self.residual_risk, "residual_risk"))
        object.__setattr__(self, "generated_at", require_datetime_text(self.generated_at, "generated_at"))


@dataclass(frozen=True, slots=True)
class TradeoffOption(ContractRecord):
    """A candidate option with bounded benefit, cost, risk, and confidence."""

    option_id: str
    label: str
    benefit: float
    cost: float
    risk: float
    confidence: float
    constraint_refs: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "option_id", require_non_empty_text(self.option_id, "option_id"))
        object.__setattr__(self, "label", require_non_empty_text(self.label, "label"))
        object.__setattr__(self, "benefit", require_unit_float(self.benefit, "benefit"))
        object.__setattr__(self, "cost", require_unit_float(self.cost, "cost"))
        object.__setattr__(self, "risk", require_unit_float(self.risk, "risk"))
        object.__setattr__(self, "confidence", require_unit_float(self.confidence, "confidence"))
        object.__setattr__(self, "constraint_refs", _freeze_text_array(self.constraint_refs, "constraint_refs"))


@dataclass(frozen=True, slots=True)
class TradeoffReasoningReport(ContractRecord):
    """Proof-carrying tradeoff report for competing bounded options."""

    report_id: str
    source_episode_id: str
    option_ids: tuple[str, ...]
    selected_option_id: str
    rejected_option_ids: tuple[str, ...]
    pareto_frontier_option_ids: tuple[str, ...]
    selection_rationale: str
    selected_utility: float
    safety_margin: float
    generated_at: str
    dominated_option_ids: tuple[str, ...] = ()
    utility_tension: float = 0.0
    constraint_tension: float = 0.0
    resource_tension: float = 0.0
    grounding_tension: float = 0.0
    perspective_tension: float = 0.0

    def __post_init__(self) -> None:
        for field_name in ("report_id", "source_episode_id", "selected_option_id", "selection_rationale"):
            object.__setattr__(self, field_name, require_non_empty_text(getattr(self, field_name), field_name))
        object.__setattr__(self, "option_ids", _freeze_text_array(self.option_ids, "option_ids", allow_empty=False))
        object.__setattr__(self, "rejected_option_ids", _freeze_text_array(self.rejected_option_ids, "rejected_option_ids"))
        object.__setattr__(
            self,
            "pareto_frontier_option_ids",
            _freeze_text_array(self.pareto_frontier_option_ids, "pareto_frontier_option_ids", allow_empty=False),
        )
        option_ids = set(self.option_ids)
        if self.selected_option_id not in option_ids:
            raise ValueError("selected_option_id must reference an option")
        if self.selected_option_id in self.rejected_option_ids:
            raise ValueError("selected_option_id must not be rejected")
        if set(self.rejected_option_ids) - option_ids:
            raise ValueError("rejected_option_ids must reference options")
        if set(self.pareto_frontier_option_ids) - option_ids:
            raise ValueError("pareto_frontier_option_ids must reference options")
        object.__setattr__(self, "dominated_option_ids", _freeze_text_array(self.dominated_option_ids, "dominated_option_ids"))
        if set(self.dominated_option_ids) - option_ids:
            raise ValueError("dominated_option_ids must reference options")
        object.__setattr__(self, "selected_utility", require_unit_float(self.selected_utility, "selected_utility"))
        object.__setattr__(self, "safety_margin", require_unit_float(self.safety_margin, "safety_margin"))
        object.__setattr__(self, "utility_tension", require_unit_float(self.utility_tension, "utility_tension"))
        object.__setattr__(self, "constraint_tension", require_unit_float(self.constraint_tension, "constraint_tension"))
        object.__setattr__(self, "resource_tension", require_unit_float(self.resource_tension, "resource_tension"))
        object.__setattr__(self, "grounding_tension", require_unit_float(self.grounding_tension, "grounding_tension"))
        object.__setattr__(self, "perspective_tension", require_unit_float(self.perspective_tension, "perspective_tension"))
        object.__setattr__(self, "generated_at", require_datetime_text(self.generated_at, "generated_at"))


@dataclass(frozen=True, slots=True)
class UncertaintyPropagationReport(ContractRecord):
    """Episode-local uncertainty envelope after constraints, failures, and tradeoffs."""

    report_id: str
    source_episode_id: str
    uncertainty_source_refs: tuple[str, ...]
    ambiguity_refs: tuple[str, ...]
    confidence_lower: float
    confidence_upper: float
    accumulated_uncertainty: float
    evidence_gap_refs: tuple[str, ...]
    generated_at: str

    def __post_init__(self) -> None:
        for field_name in ("report_id", "source_episode_id"):
            object.__setattr__(self, field_name, require_non_empty_text(getattr(self, field_name), field_name))
        for field_name in ("uncertainty_source_refs", "ambiguity_refs", "evidence_gap_refs"):
            object.__setattr__(self, field_name, _freeze_text_array(getattr(self, field_name), field_name))
        object.__setattr__(self, "confidence_lower", require_unit_float(self.confidence_lower, "confidence_lower"))
        object.__setattr__(self, "confidence_upper", require_unit_float(self.confidence_upper, "confidence_upper"))
        if self.confidence_lower > self.confidence_upper:
            raise ValueError("confidence_lower must be <= confidence_upper")
        object.__setattr__(
            self,
            "accumulated_uncertainty",
            require_unit_float(self.accumulated_uncertainty, "accumulated_uncertainty"),
        )
        object.__setattr__(self, "generated_at", require_datetime_text(self.generated_at, "generated_at"))


@dataclass(frozen=True, slots=True)
class SelfDiagnosisReport(ContractRecord):
    """Episode-local self-diagnosis report for reasoning quality and escalation."""

    report_id: str
    source_episode_id: str
    uncertainty_report_ref: str
    failure_map_ref: str
    tradeoff_report_ref: str
    finding_refs: tuple[str, ...]
    broken_assumption_refs: tuple[str, ...]
    resource_pressure: float
    hallucination_risk: float
    severity: DiagnosisSeverity
    escalation_required: bool
    generated_at: str

    def __post_init__(self) -> None:
        for field_name in (
            "report_id",
            "source_episode_id",
            "uncertainty_report_ref",
            "failure_map_ref",
            "tradeoff_report_ref",
        ):
            object.__setattr__(self, field_name, require_non_empty_text(getattr(self, field_name), field_name))
        for field_name in ("finding_refs", "broken_assumption_refs"):
            object.__setattr__(self, field_name, _freeze_text_array(getattr(self, field_name), field_name))
        object.__setattr__(self, "resource_pressure", require_unit_float(self.resource_pressure, "resource_pressure"))
        object.__setattr__(self, "hallucination_risk", require_unit_float(self.hallucination_risk, "hallucination_risk"))
        if not isinstance(self.severity, DiagnosisSeverity):
            raise ValueError("severity must be a DiagnosisSeverity value")
        if not isinstance(self.escalation_required, bool):
            raise ValueError("escalation_required must be a bool")
        object.__setattr__(self, "generated_at", require_datetime_text(self.generated_at, "generated_at"))


@dataclass(frozen=True, slots=True)
class CorrectionRepairAction(ContractRecord):
    """One explicit self-correction or rollback action recommendation."""

    action_id: str
    kind: CorrectionActionKind
    target_ref: str
    reason_refs: tuple[str, ...]
    reversible: bool

    def __post_init__(self) -> None:
        for field_name in ("action_id", "target_ref"):
            object.__setattr__(self, field_name, require_non_empty_text(getattr(self, field_name), field_name))
        if not isinstance(self.kind, CorrectionActionKind):
            raise ValueError("kind must be a CorrectionActionKind value")
        object.__setattr__(self, "reason_refs", _freeze_text_array(self.reason_refs, "reason_refs", allow_empty=False))
        if not isinstance(self.reversible, bool):
            raise ValueError("reversible must be a bool")


@dataclass(frozen=True, slots=True)
class CorrectionRepairReport(ContractRecord):
    """Episode-local correction report for contradictions, rollback, and repair."""

    report_id: str
    source_episode_id: str
    action_ids: tuple[str, ...]
    contradiction_refs: tuple[str, ...]
    rollback_action_ids: tuple[str, ...]
    repair_action_ids: tuple[str, ...]
    evidence_request_action_ids: tuple[str, ...]
    status: CorrectionRepairStatus
    repair_pressure: float
    generated_at: str

    def __post_init__(self) -> None:
        for field_name in ("report_id", "source_episode_id"):
            object.__setattr__(self, field_name, require_non_empty_text(getattr(self, field_name), field_name))
        for field_name in (
            "action_ids",
            "contradiction_refs",
            "rollback_action_ids",
            "repair_action_ids",
            "evidence_request_action_ids",
        ):
            object.__setattr__(self, field_name, _freeze_text_array(getattr(self, field_name), field_name))
        action_ids = set(self.action_ids)
        for field_name in ("rollback_action_ids", "repair_action_ids", "evidence_request_action_ids"):
            if set(getattr(self, field_name)) - action_ids:
                raise ValueError(f"{field_name} must reference action_ids")
        if not isinstance(self.status, CorrectionRepairStatus):
            raise ValueError("status must be a CorrectionRepairStatus value")
        object.__setattr__(self, "repair_pressure", require_unit_float(self.repair_pressure, "repair_pressure"))
        object.__setattr__(self, "generated_at", require_datetime_text(self.generated_at, "generated_at"))


@dataclass(frozen=True, slots=True)
class WorldSnapshotLineageLink(ContractRecord):
    """Directed lineage link between world-model snapshots."""

    link_id: str
    prior_snapshot_ref: str
    next_snapshot_ref: str
    delta_ref: str | None = None

    def __post_init__(self) -> None:
        for field_name in ("link_id", "prior_snapshot_ref", "next_snapshot_ref"):
            object.__setattr__(self, field_name, require_non_empty_text(getattr(self, field_name), field_name))
        if self.delta_ref is not None:
            object.__setattr__(self, "delta_ref", require_non_empty_text(self.delta_ref, "delta_ref"))


@dataclass(frozen=True, slots=True)
class WorldIdentityContinuityCheck(ContractRecord):
    """Identity-preservation check for an entity across world snapshots."""

    check_id: str
    entity_ref: str
    prior_snapshot_ref: str
    next_snapshot_ref: str
    preserved: bool
    evidence_refs: tuple[str, ...]

    def __post_init__(self) -> None:
        for field_name in ("check_id", "entity_ref", "prior_snapshot_ref", "next_snapshot_ref"):
            object.__setattr__(self, field_name, require_non_empty_text(getattr(self, field_name), field_name))
        if not isinstance(self.preserved, bool):
            raise ValueError("preserved must be a bool")
        object.__setattr__(self, "evidence_refs", _freeze_text_array(self.evidence_refs, "evidence_refs"))


@dataclass(frozen=True, slots=True)
class DynamicWorldModelContinuityReport(ContractRecord):
    """Episode-local world-model continuity report for lineage and identity."""

    report_id: str
    source_episode_id: str
    lineage_link_ids: tuple[str, ...]
    identity_check_ids: tuple[str, ...]
    broken_lineage_link_ids: tuple[str, ...]
    drifted_identity_check_ids: tuple[str, ...]
    persistent_causal_chain_refs: tuple[str, ...]
    status: WorldContinuityStatus
    continuity_score: float
    generated_at: str

    def __post_init__(self) -> None:
        for field_name in ("report_id", "source_episode_id"):
            object.__setattr__(self, field_name, require_non_empty_text(getattr(self, field_name), field_name))
        for field_name in (
            "lineage_link_ids",
            "identity_check_ids",
            "broken_lineage_link_ids",
            "drifted_identity_check_ids",
            "persistent_causal_chain_refs",
        ):
            object.__setattr__(self, field_name, _freeze_text_array(getattr(self, field_name), field_name))
        lineage_link_ids = set(self.lineage_link_ids)
        identity_check_ids = set(self.identity_check_ids)
        if set(self.broken_lineage_link_ids) - lineage_link_ids:
            raise ValueError("broken_lineage_link_ids must reference lineage_link_ids")
        if set(self.drifted_identity_check_ids) - identity_check_ids:
            raise ValueError("drifted_identity_check_ids must reference identity_check_ids")
        if not isinstance(self.status, WorldContinuityStatus):
            raise ValueError("status must be a WorldContinuityStatus value")
        object.__setattr__(self, "continuity_score", require_unit_float(self.continuity_score, "continuity_score"))
        object.__setattr__(self, "generated_at", require_datetime_text(self.generated_at, "generated_at"))


@dataclass(frozen=True, slots=True)
class OrchestrationReadinessReport(ContractRecord):
    """Aggregate pre-execution readiness report over all coordination artifacts."""

    report_id: str
    source_episode_id: str
    report_refs: tuple[str, ...]
    hard_block_refs: tuple[str, ...]
    replan_refs: tuple[str, ...]
    soft_risk_refs: tuple[str, ...]
    verdict: OrchestrationReadinessVerdict
    readiness_score: float
    generated_at: str

    def __post_init__(self) -> None:
        for field_name in ("report_id", "source_episode_id"):
            object.__setattr__(self, field_name, require_non_empty_text(getattr(self, field_name), field_name))
        for field_name in ("report_refs", "hard_block_refs", "replan_refs", "soft_risk_refs"):
            object.__setattr__(self, field_name, _freeze_text_array(getattr(self, field_name), field_name))
        if not isinstance(self.verdict, OrchestrationReadinessVerdict):
            raise ValueError("verdict must be an OrchestrationReadinessVerdict value")
        object.__setattr__(self, "readiness_score", require_unit_float(self.readiness_score, "readiness_score"))
        object.__setattr__(self, "generated_at", require_datetime_text(self.generated_at, "generated_at"))


@dataclass(frozen=True, slots=True)
class AdaptiveReplanRecommendation(ContractRecord):
    """Episode-local adaptive planning recommendation."""

    recommendation_id: str
    source_episode_id: str
    uncertainty_report_ref: str
    self_diagnosis_ref: str
    failure_map_ref: str
    tradeoff_report_ref: str
    trigger: ReplanTrigger
    recommended_plan_ref: str
    blocked_plan_ref: str | None
    reason_refs: tuple[str, ...]
    urgency: float
    replan_required: bool
    generated_at: str

    def __post_init__(self) -> None:
        for field_name in (
            "recommendation_id",
            "source_episode_id",
            "uncertainty_report_ref",
            "self_diagnosis_ref",
            "failure_map_ref",
            "tradeoff_report_ref",
            "recommended_plan_ref",
        ):
            object.__setattr__(self, field_name, require_non_empty_text(getattr(self, field_name), field_name))
        if self.blocked_plan_ref is not None:
            object.__setattr__(self, "blocked_plan_ref", require_non_empty_text(self.blocked_plan_ref, "blocked_plan_ref"))
        object.__setattr__(self, "reason_refs", _freeze_text_array(self.reason_refs, "reason_refs"))
        if not isinstance(self.trigger, ReplanTrigger):
            raise ValueError("trigger must be a ReplanTrigger value")
        object.__setattr__(self, "urgency", require_unit_float(self.urgency, "urgency"))
        if not isinstance(self.replan_required, bool):
            raise ValueError("replan_required must be a bool")
        if self.trigger == ReplanTrigger.NONE and self.replan_required:
            raise ValueError("replan_required must be false when trigger is none")
        if self.trigger != ReplanTrigger.NONE and not self.replan_required:
            raise ValueError("replan_required must be true when trigger is not none")
        if self.replan_required and self.blocked_plan_ref is None:
            raise ValueError("blocked_plan_ref is required when replanning is required")
        object.__setattr__(self, "generated_at", require_datetime_text(self.generated_at, "generated_at"))


@dataclass(frozen=True, slots=True)
class CoordinationTemporalEvent(ContractRecord):
    """Episode-local temporal event used for state-evolution validation."""

    event_id: str
    occurred_at: str
    state_ref: str
    predecessor_event_ids: tuple[str, ...]
    delayed_effect_refs: tuple[str, ...]
    persistence_refs: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "event_id", require_non_empty_text(self.event_id, "event_id"))
        object.__setattr__(self, "occurred_at", require_datetime_text(self.occurred_at, "occurred_at"))
        object.__setattr__(self, "state_ref", require_non_empty_text(self.state_ref, "state_ref"))
        for field_name in ("predecessor_event_ids", "delayed_effect_refs", "persistence_refs"):
            object.__setattr__(self, field_name, _freeze_text_array(getattr(self, field_name), field_name))


@dataclass(frozen=True, slots=True)
class TemporalStateEvolutionReport(ContractRecord):
    """Episode-local temporal report for event ordering and state evolution."""

    report_id: str
    source_episode_id: str
    event_ids: tuple[str, ...]
    ordered_event_ids: tuple[str, ...]
    violated_event_ids: tuple[str, ...]
    incomplete_event_ids: tuple[str, ...]
    delayed_effect_refs: tuple[str, ...]
    persistence_refs: tuple[str, ...]
    status: TemporalCheckStatus
    deadline_pressure: float
    generated_at: str

    def __post_init__(self) -> None:
        for field_name in ("report_id", "source_episode_id"):
            object.__setattr__(self, field_name, require_non_empty_text(getattr(self, field_name), field_name))
        for field_name in (
            "event_ids",
            "ordered_event_ids",
            "violated_event_ids",
            "incomplete_event_ids",
            "delayed_effect_refs",
            "persistence_refs",
        ):
            object.__setattr__(self, field_name, _freeze_text_array(getattr(self, field_name), field_name))
        event_ids = set(self.event_ids)
        if set(self.ordered_event_ids) - event_ids:
            raise ValueError("ordered_event_ids must reference event_ids")
        if set(self.violated_event_ids) - event_ids:
            raise ValueError("violated_event_ids must reference event_ids")
        if set(self.incomplete_event_ids) - event_ids:
            raise ValueError("incomplete_event_ids must reference event_ids")
        if not isinstance(self.status, TemporalCheckStatus):
            raise ValueError("status must be a TemporalCheckStatus value")
        object.__setattr__(self, "deadline_pressure", require_unit_float(self.deadline_pressure, "deadline_pressure"))
        object.__setattr__(self, "generated_at", require_datetime_text(self.generated_at, "generated_at"))


@dataclass(frozen=True, slots=True)
class CoordinationCausalNode(ContractRecord):
    """Episode-local causal graph node used for influence-flow analysis."""

    node_id: str
    label: str
    role_refs: tuple[str, ...] = ()
    protected: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "node_id", require_non_empty_text(self.node_id, "node_id"))
        object.__setattr__(self, "label", require_non_empty_text(self.label, "label"))
        object.__setattr__(self, "role_refs", _freeze_text_array(self.role_refs, "role_refs"))
        if not isinstance(self.protected, bool):
            raise ValueError("protected must be a bool")


@dataclass(frozen=True, slots=True)
class CoordinationCausalEdge(ContractRecord):
    """Directed causal influence edge between two episode-local nodes."""

    edge_id: str
    cause_node_id: str
    effect_node_id: str
    strength: float
    evidence_refs: tuple[str, ...] = ()
    delay_ref: str | None = None

    def __post_init__(self) -> None:
        for field_name in ("edge_id", "cause_node_id", "effect_node_id"):
            object.__setattr__(self, field_name, require_non_empty_text(getattr(self, field_name), field_name))
        object.__setattr__(self, "strength", require_unit_float(self.strength, "strength"))
        object.__setattr__(self, "evidence_refs", _freeze_text_array(self.evidence_refs, "evidence_refs"))
        if self.delay_ref is not None:
            object.__setattr__(self, "delay_ref", require_non_empty_text(self.delay_ref, "delay_ref"))


@dataclass(frozen=True, slots=True)
class CausalGraphDynamicsReport(ContractRecord):
    """Episode-local causal report for cycles, bottlenecks, bridges, and fragility."""

    report_id: str
    source_episode_id: str
    node_ids: tuple[str, ...]
    edge_ids: tuple[str, ...]
    feedback_cycle_node_ids: tuple[str, ...]
    feedback_edge_ids: tuple[str, ...]
    bottleneck_node_ids: tuple[str, ...]
    bridge_node_ids: tuple[str, ...]
    orphan_node_ids: tuple[str, ...]
    protected_node_ids: tuple[str, ...]
    status: CausalDynamicsStatus
    structural_fragility: float
    generated_at: str

    def __post_init__(self) -> None:
        for field_name in ("report_id", "source_episode_id"):
            object.__setattr__(self, field_name, require_non_empty_text(getattr(self, field_name), field_name))
        for field_name in (
            "node_ids",
            "edge_ids",
            "feedback_cycle_node_ids",
            "feedback_edge_ids",
            "bottleneck_node_ids",
            "bridge_node_ids",
            "orphan_node_ids",
            "protected_node_ids",
        ):
            object.__setattr__(self, field_name, _freeze_text_array(getattr(self, field_name), field_name))
        node_ids = set(self.node_ids)
        edge_ids = set(self.edge_ids)
        for field_name in (
            "feedback_cycle_node_ids",
            "bottleneck_node_ids",
            "bridge_node_ids",
            "orphan_node_ids",
            "protected_node_ids",
        ):
            if set(getattr(self, field_name)) - node_ids:
                raise ValueError(f"{field_name} must reference node_ids")
        if set(self.feedback_edge_ids) - edge_ids:
            raise ValueError("feedback_edge_ids must reference edge_ids")
        if not isinstance(self.status, CausalDynamicsStatus):
            raise ValueError("status must be a CausalDynamicsStatus value")
        object.__setattr__(
            self,
            "structural_fragility",
            require_unit_float(self.structural_fragility, "structural_fragility"),
        )
        object.__setattr__(self, "generated_at", require_datetime_text(self.generated_at, "generated_at"))


@dataclass(frozen=True, slots=True)
class CoordinationAbstractionLayer(ContractRecord):
    """Episode-local abstraction layer with evidence-bound parent links."""

    layer_id: str
    scale: AbstractionScale
    symbol_refs: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    parent_layer_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "layer_id", require_non_empty_text(self.layer_id, "layer_id"))
        if not isinstance(self.scale, AbstractionScale):
            raise ValueError("scale must be an AbstractionScale value")
        object.__setattr__(self, "symbol_refs", _freeze_text_array(self.symbol_refs, "symbol_refs", allow_empty=False))
        object.__setattr__(self, "evidence_refs", _freeze_text_array(self.evidence_refs, "evidence_refs", allow_empty=False))
        object.__setattr__(self, "parent_layer_ids", _freeze_text_array(self.parent_layer_ids, "parent_layer_ids"))


@dataclass(frozen=True, slots=True)
class AbstractionControlReport(ContractRecord):
    """Episode-local report for scale coverage, compression, and boundary collapse."""

    report_id: str
    source_episode_id: str
    layer_ids: tuple[str, ...]
    micro_layer_ids: tuple[str, ...]
    meso_layer_ids: tuple[str, ...]
    macro_layer_ids: tuple[str, ...]
    missing_scale_refs: tuple[str, ...]
    collapsed_layer_ids: tuple[str, ...]
    orphan_layer_ids: tuple[str, ...]
    status: AbstractionControlStatus
    scale_coverage: float
    compression_ratio: float
    generated_at: str

    def __post_init__(self) -> None:
        for field_name in ("report_id", "source_episode_id"):
            object.__setattr__(self, field_name, require_non_empty_text(getattr(self, field_name), field_name))
        for field_name in (
            "layer_ids",
            "micro_layer_ids",
            "meso_layer_ids",
            "macro_layer_ids",
            "missing_scale_refs",
            "collapsed_layer_ids",
            "orphan_layer_ids",
        ):
            object.__setattr__(self, field_name, _freeze_text_array(getattr(self, field_name), field_name))
        layer_ids = set(self.layer_ids)
        for field_name in ("micro_layer_ids", "meso_layer_ids", "macro_layer_ids", "collapsed_layer_ids", "orphan_layer_ids"):
            if set(getattr(self, field_name)) - layer_ids:
                raise ValueError(f"{field_name} must reference layer_ids")
        for scale_ref in self.missing_scale_refs:
            if scale_ref not in {scale.value for scale in AbstractionScale}:
                raise ValueError("missing_scale_refs must contain known abstraction scales")
        if not isinstance(self.status, AbstractionControlStatus):
            raise ValueError("status must be an AbstractionControlStatus value")
        object.__setattr__(self, "scale_coverage", require_unit_float(self.scale_coverage, "scale_coverage"))
        object.__setattr__(self, "compression_ratio", require_unit_float(self.compression_ratio, "compression_ratio"))
        object.__setattr__(self, "generated_at", require_datetime_text(self.generated_at, "generated_at"))


@dataclass(frozen=True, slots=True)
class CoordinationResourceLimit(ContractRecord):
    """Explicit resource budget and usage for bounded coordination."""

    limit_id: str
    kind: CoordinationResourceKind
    budget: float
    used: float
    unit: str
    hard_limit: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(self, "limit_id", require_non_empty_text(self.limit_id, "limit_id"))
        if not isinstance(self.kind, CoordinationResourceKind):
            raise ValueError("kind must be a CoordinationResourceKind value")
        object.__setattr__(self, "budget", require_non_negative_float(self.budget, "budget"))
        object.__setattr__(self, "used", require_non_negative_float(self.used, "used"))
        object.__setattr__(self, "unit", require_non_empty_text(self.unit, "unit"))
        if not isinstance(self.hard_limit, bool):
            raise ValueError("hard_limit must be a bool")


@dataclass(frozen=True, slots=True)
class ResourceBoundedControlReport(ContractRecord):
    """Episode-local report for bounded compute, memory, time, and attention."""

    report_id: str
    source_episode_id: str
    limit_ids: tuple[str, ...]
    degraded_limit_ids: tuple[str, ...]
    exhausted_limit_ids: tuple[str, ...]
    overrun_limit_ids: tuple[str, ...]
    hard_block_limit_ids: tuple[str, ...]
    status: ResourceBoundStatus
    max_pressure: float
    generated_at: str

    def __post_init__(self) -> None:
        for field_name in ("report_id", "source_episode_id"):
            object.__setattr__(self, field_name, require_non_empty_text(getattr(self, field_name), field_name))
        for field_name in (
            "limit_ids",
            "degraded_limit_ids",
            "exhausted_limit_ids",
            "overrun_limit_ids",
            "hard_block_limit_ids",
        ):
            object.__setattr__(self, field_name, _freeze_text_array(getattr(self, field_name), field_name))
        limit_ids = set(self.limit_ids)
        for field_name in ("degraded_limit_ids", "exhausted_limit_ids", "overrun_limit_ids", "hard_block_limit_ids"):
            if set(getattr(self, field_name)) - limit_ids:
                raise ValueError(f"{field_name} must reference limit_ids")
        if not isinstance(self.status, ResourceBoundStatus):
            raise ValueError("status must be a ResourceBoundStatus value")
        object.__setattr__(self, "max_pressure", require_unit_float(self.max_pressure, "max_pressure"))
        object.__setattr__(self, "generated_at", require_datetime_text(self.generated_at, "generated_at"))


@dataclass(frozen=True, slots=True)
class CoordinationGroundingClaim(ContractRecord):
    """Evidence-backed binding between a symbol and an observable/actionable target."""

    claim_id: str
    symbol_ref: str
    kind: SemanticGroundingKind
    target_ref: str
    confidence: float
    evidence_refs: tuple[str, ...]

    def __post_init__(self) -> None:
        for field_name in ("claim_id", "symbol_ref", "target_ref"):
            object.__setattr__(self, field_name, require_non_empty_text(getattr(self, field_name), field_name))
        if not isinstance(self.kind, SemanticGroundingKind):
            raise ValueError("kind must be a SemanticGroundingKind value")
        object.__setattr__(self, "confidence", require_unit_float(self.confidence, "confidence"))
        object.__setattr__(self, "evidence_refs", _freeze_text_array(self.evidence_refs, "evidence_refs", allow_empty=False))


@dataclass(frozen=True, slots=True)
class SemanticGroundingReport(ContractRecord):
    """Episode-local report for symbol bindings to observable or executable ground."""

    report_id: str
    source_episode_id: str
    claim_ids: tuple[str, ...]
    grounded_claim_ids: tuple[str, ...]
    weak_claim_ids: tuple[str, ...]
    missing_symbol_refs: tuple[str, ...]
    status: SemanticGroundingStatus
    grounding_coverage: float
    min_confidence: float
    generated_at: str

    def __post_init__(self) -> None:
        for field_name in ("report_id", "source_episode_id"):
            object.__setattr__(self, field_name, require_non_empty_text(getattr(self, field_name), field_name))
        for field_name in ("claim_ids", "grounded_claim_ids", "weak_claim_ids", "missing_symbol_refs"):
            object.__setattr__(self, field_name, _freeze_text_array(getattr(self, field_name), field_name))
        claim_ids = set(self.claim_ids)
        for field_name in ("grounded_claim_ids", "weak_claim_ids"):
            if set(getattr(self, field_name)) - claim_ids:
                raise ValueError(f"{field_name} must reference claim_ids")
        if not isinstance(self.status, SemanticGroundingStatus):
            raise ValueError("status must be a SemanticGroundingStatus value")
        object.__setattr__(self, "grounding_coverage", require_unit_float(self.grounding_coverage, "grounding_coverage"))
        object.__setattr__(self, "min_confidence", require_unit_float(self.min_confidence, "min_confidence"))
        object.__setattr__(self, "generated_at", require_datetime_text(self.generated_at, "generated_at"))


@dataclass(frozen=True, slots=True)
class CoordinationPerspective(ContractRecord):
    """Episode-local perspective with explicit assumptions, incentives, and model refs."""

    perspective_id: str
    kind: PerspectiveKind
    model_ref: str
    assumption_refs: tuple[str, ...]
    incentive_refs: tuple[str, ...]
    scale_refs: tuple[str, ...]
    conclusion_refs: tuple[str, ...]
    confidence: float

    def __post_init__(self) -> None:
        for field_name in ("perspective_id", "model_ref"):
            object.__setattr__(self, field_name, require_non_empty_text(getattr(self, field_name), field_name))
        if not isinstance(self.kind, PerspectiveKind):
            raise ValueError("kind must be a PerspectiveKind value")
        for field_name in ("assumption_refs", "incentive_refs", "scale_refs", "conclusion_refs"):
            object.__setattr__(self, field_name, _freeze_text_array(getattr(self, field_name), field_name))
        object.__setattr__(self, "confidence", require_unit_float(self.confidence, "confidence"))


@dataclass(frozen=True, slots=True)
class MultiPerspectiveReasoningReport(ContractRecord):
    """Episode-local report comparing assumptions, incentives, scales, and models."""

    report_id: str
    source_episode_id: str
    perspective_ids: tuple[str, ...]
    represented_kind_refs: tuple[str, ...]
    missing_kind_refs: tuple[str, ...]
    divergent_perspective_ids: tuple[str, ...]
    low_confidence_perspective_ids: tuple[str, ...]
    shared_conclusion_refs: tuple[str, ...]
    status: PerspectiveComparisonStatus
    agreement_score: float
    generated_at: str

    def __post_init__(self) -> None:
        for field_name in ("report_id", "source_episode_id"):
            object.__setattr__(self, field_name, require_non_empty_text(getattr(self, field_name), field_name))
        for field_name in (
            "perspective_ids",
            "represented_kind_refs",
            "missing_kind_refs",
            "divergent_perspective_ids",
            "low_confidence_perspective_ids",
            "shared_conclusion_refs",
        ):
            object.__setattr__(self, field_name, _freeze_text_array(getattr(self, field_name), field_name))
        perspective_ids = set(self.perspective_ids)
        for field_name in ("divergent_perspective_ids", "low_confidence_perspective_ids"):
            if set(getattr(self, field_name)) - perspective_ids:
                raise ValueError(f"{field_name} must reference perspective_ids")
        valid_kind_refs = {kind.value for kind in PerspectiveKind}
        for field_name in ("represented_kind_refs", "missing_kind_refs"):
            if set(getattr(self, field_name)) - valid_kind_refs:
                raise ValueError(f"{field_name} must contain known perspective kinds")
        if not isinstance(self.status, PerspectiveComparisonStatus):
            raise ValueError("status must be a PerspectiveComparisonStatus value")
        object.__setattr__(self, "agreement_score", require_unit_float(self.agreement_score, "agreement_score"))
        object.__setattr__(self, "generated_at", require_datetime_text(self.generated_at, "generated_at"))


@dataclass(frozen=True, slots=True)
class CoordinationPatternCandidate(ContractRecord):
    """Candidate invariant, motif, or reusable structure discovered in an episode."""

    pattern_id: str
    symbol_refs: tuple[str, ...]
    invariant_refs: tuple[str, ...]
    motif_refs: tuple[str, ...]
    reusable_structure_refs: tuple[str, ...]
    redundancy_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "pattern_id", require_non_empty_text(self.pattern_id, "pattern_id"))
        for field_name in (
            "symbol_refs",
            "invariant_refs",
            "motif_refs",
            "reusable_structure_refs",
            "redundancy_refs",
        ):
            object.__setattr__(self, field_name, _freeze_text_array(getattr(self, field_name), field_name))


@dataclass(frozen=True, slots=True)
class CompressionPatternDiscoveryReport(ContractRecord):
    """Episode-local report for invariant extraction, motifs, and redundancy."""

    report_id: str
    source_episode_id: str
    pattern_ids: tuple[str, ...]
    invariant_refs: tuple[str, ...]
    motif_refs: tuple[str, ...]
    reusable_structure_refs: tuple[str, ...]
    redundant_symbol_refs: tuple[str, ...]
    status: PatternDiscoveryStatus
    compression_ratio: float
    reuse_score: float
    generated_at: str

    def __post_init__(self) -> None:
        for field_name in ("report_id", "source_episode_id"):
            object.__setattr__(self, field_name, require_non_empty_text(getattr(self, field_name), field_name))
        for field_name in (
            "pattern_ids",
            "invariant_refs",
            "motif_refs",
            "reusable_structure_refs",
            "redundant_symbol_refs",
        ):
            object.__setattr__(self, field_name, _freeze_text_array(getattr(self, field_name), field_name))
        if not isinstance(self.status, PatternDiscoveryStatus):
            raise ValueError("status must be a PatternDiscoveryStatus value")
        object.__setattr__(self, "compression_ratio", require_unit_float(self.compression_ratio, "compression_ratio"))
        object.__setattr__(self, "reuse_score", require_unit_float(self.reuse_score, "reuse_score"))
        object.__setattr__(self, "generated_at", require_datetime_text(self.generated_at, "generated_at"))


@dataclass(frozen=True, slots=True)
class IntelligenceCoordinationEpisode(ContractRecord):
    """Top-level episode artifact for governed coordination."""

    episode_id: str
    goal_id: str
    input_symbol_mesh_ref: str
    world_snapshot_ref: str
    active_constraints_ref: str
    causal_graph_ref: str
    uncertainty_envelope_ref: str
    problem_signature: MethodProblemSignature
    method_candidates: tuple[MethodCandidate, ...]
    selected_method_id: str
    rejected_method_ids: tuple[str, ...]
    counterfactual_branches: tuple[CounterfactualBranch, ...]
    failure_map_ref: str
    tradeoff_report_ref: str
    execution_plan_ref: str
    diagnosis_report_ref: str
    world_model_delta_ref: str | None
    proof_record_ref: str
    terminal_outcome: SolverTerminalOutcome
    created_at: str
    coordination_depth: int = 0
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in (
            "episode_id",
            "goal_id",
            "input_symbol_mesh_ref",
            "world_snapshot_ref",
            "active_constraints_ref",
            "causal_graph_ref",
            "uncertainty_envelope_ref",
            "selected_method_id",
            "failure_map_ref",
            "tradeoff_report_ref",
            "execution_plan_ref",
            "diagnosis_report_ref",
            "proof_record_ref",
        ):
            object.__setattr__(self, field_name, require_non_empty_text(getattr(self, field_name), field_name))
        if not isinstance(self.problem_signature, MethodProblemSignature):
            raise ValueError("problem_signature must be a MethodProblemSignature value")
        object.__setattr__(
            self,
            "method_candidates",
            _freeze_contract_array(self.method_candidates, "method_candidates", MethodCandidate, allow_empty=False),
        )
        candidate_ids = {candidate.method_id for candidate in self.method_candidates}
        if len(candidate_ids) != len(self.method_candidates):
            raise ValueError("method_candidates must declare unique method_id values")
        if self.selected_method_id not in candidate_ids:
            raise ValueError("selected_method_id must reference a method candidate")
        object.__setattr__(self, "rejected_method_ids", _freeze_text_array(self.rejected_method_ids, "rejected_method_ids"))
        if self.selected_method_id in self.rejected_method_ids:
            raise ValueError("selected_method_id must not be rejected")
        unknown_rejected = set(self.rejected_method_ids) - candidate_ids
        if unknown_rejected:
            raise ValueError("rejected_method_ids must reference method candidates")
        object.__setattr__(
            self,
            "counterfactual_branches",
            _freeze_contract_array(self.counterfactual_branches, "counterfactual_branches", CounterfactualBranch),
        )
        if self.world_model_delta_ref is not None:
            object.__setattr__(
                self,
                "world_model_delta_ref",
                require_non_empty_text(self.world_model_delta_ref, "world_model_delta_ref"),
            )
        if not isinstance(self.terminal_outcome, SolverTerminalOutcome):
            raise ValueError("terminal_outcome must be a SolverTerminalOutcome value")
        object.__setattr__(self, "created_at", require_datetime_text(self.created_at, "created_at"))
        object.__setattr__(self, "coordination_depth", require_non_negative_int(self.coordination_depth, "coordination_depth"))
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))
