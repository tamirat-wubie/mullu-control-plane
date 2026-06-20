"""Purpose: governed Proto-SGI readiness read/simulation kernel for Mullu.
Governance scope: cross-domain transfer, concept-birth admission,
    self-question generation, and autonomy classification only.
Dependencies: Python standard library dataclasses, enum, and contract validators.
Invariants:
  - This module does not execute external actions or mutate runtime state.
  - Core self-modification is classified, never silently admitted.
  - SGI is not claimed; readiness is reported as bounded Proto-SGI evidence.
  - Every blocker is explicit and deterministic.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass
from typing import Sequence

from mcoi_runtime.contracts._base import (
    ContractRecord,
    freeze_value,
    require_non_empty_text,
    require_unit_float,
)


class ReadinessState(enum.Enum):
    """Bounded readiness states; none of these states claim achieved SGI."""

    PROTO_SGI_LEVEL_3 = "proto_sgi_level_3"
    LEVEL_4_CANDIDATE = "level_4_cross_domain_candidate"
    BLOCKED = "blocked"


class Verdict(enum.Enum):
    """Deterministic admission verdicts used by read/simulation checks."""

    ADMITTED = "admitted"
    BLOCKED = "blocked"


class ActionClass(enum.Enum):
    """Governed action classes for autonomy classification."""

    EPISTEMIC = "epistemic"
    STATE_WRITE = "state_write"
    EXTERNAL_EFFECT = "external_effect"
    CORE_MUTATION = "core_mutation"


class AutonomyClass(enum.Enum):
    """Bounded autonomy classes for Mullu cognitive proposals."""

    SAFE = "safe"
    GUARDED = "guarded"
    RESTRICTED = "restricted"
    PROHIBITED = "prohibited"


class AutonomyDecisionStatus(enum.Enum):
    """Execution status for an autonomy proposal."""

    ALLOW = "allow"
    SIMULATION_ONLY = "simulation_only"
    BLOCK = "block"


@dataclass(frozen=True, slots=True)
class HomeostaticVector(ContractRecord):
    """Multi-dimensional system-health vector for cognitive readiness checks."""

    stability: float
    coherence: float
    adaptability: float
    energy_cost: float
    prediction_accuracy: float
    memory_integrity: float
    governance_safety: float

    def __post_init__(self) -> None:
        fields = {
            "stability": self.stability,
            "coherence": self.coherence,
            "adaptability": self.adaptability,
            "energy_cost": self.energy_cost,
            "prediction_accuracy": self.prediction_accuracy,
            "memory_integrity": self.memory_integrity,
            "governance_safety": self.governance_safety,
        }
        for field_name, value in fields.items():
            object.__setattr__(self, field_name, require_unit_float(value, field_name))

    def balance_score(self) -> float:
        """Return a bounded balance score where lower energy cost is better."""

        return (
            self.stability
            + self.coherence
            + self.adaptability
            + (1.0 - self.energy_cost)
            + self.prediction_accuracy
            + self.memory_integrity
            + self.governance_safety
        ) / 7.0


@dataclass(frozen=True, slots=True)
class RewardSignal(ContractRecord):
    """Reward vector that prevents cheap wins from overriding safety or coherence."""

    immediate_utility: float
    long_term_coherence: float
    causal_accuracy: float
    energy_efficiency: float
    safety_compliance: float
    reversibility: float

    def __post_init__(self) -> None:
        fields = {
            "immediate_utility": self.immediate_utility,
            "long_term_coherence": self.long_term_coherence,
            "causal_accuracy": self.causal_accuracy,
            "energy_efficiency": self.energy_efficiency,
            "safety_compliance": self.safety_compliance,
            "reversibility": self.reversibility,
        }
        for field_name, value in fields.items():
            object.__setattr__(self, field_name, require_unit_float(value, field_name))

    def weighted_score(self) -> float:
        """Return the governed weighted reward score."""

        return (
            0.20 * self.immediate_utility
            + 0.25 * self.long_term_coherence
            + 0.20 * self.causal_accuracy
            + 0.10 * self.energy_efficiency
            + 0.15 * self.safety_compliance
            + 0.10 * self.reversibility
        )


@dataclass(frozen=True, slots=True)
class CrossDomainTransferCandidate(ContractRecord):
    """Candidate for transferring an invariant from one domain to another."""

    source_domain: str
    target_domain: str
    source_pattern: str
    target_mapping: str
    invariant_refs: Sequence[str]
    contradiction_refs: Sequence[str] = ()
    confidence: float = 0.0

    def __post_init__(self) -> None:
        object.__setattr__(self, "source_domain", require_non_empty_text(self.source_domain, "source_domain"))
        object.__setattr__(self, "target_domain", require_non_empty_text(self.target_domain, "target_domain"))
        object.__setattr__(self, "source_pattern", require_non_empty_text(self.source_pattern, "source_pattern"))
        object.__setattr__(self, "target_mapping", require_non_empty_text(self.target_mapping, "target_mapping"))
        object.__setattr__(self, "invariant_refs", _text_tuple(self.invariant_refs, "invariant_refs"))
        object.__setattr__(self, "contradiction_refs", _text_tuple(self.contradiction_refs, "contradiction_refs", allow_empty=True))
        object.__setattr__(self, "confidence", require_unit_float(self.confidence, "confidence"))


@dataclass(frozen=True, slots=True)
class ConceptBirthCandidate(ContractRecord):
    """Candidate for admitting a new symbolic concept into the ontology path."""

    concept_id: str
    evidence_refs: Sequence[str]
    necessity_score: float
    overlap_score: float
    governance_refs: Sequence[str]

    def __post_init__(self) -> None:
        object.__setattr__(self, "concept_id", require_non_empty_text(self.concept_id, "concept_id"))
        object.__setattr__(self, "evidence_refs", _text_tuple(self.evidence_refs, "evidence_refs"))
        object.__setattr__(self, "necessity_score", require_unit_float(self.necessity_score, "necessity_score"))
        object.__setattr__(self, "overlap_score", require_unit_float(self.overlap_score, "overlap_score"))
        object.__setattr__(self, "governance_refs", _text_tuple(self.governance_refs, "governance_refs"))


@dataclass(frozen=True, slots=True)
class ActionProposal(ContractRecord):
    """Effect-bearing or epistemic action proposal before governance classification."""

    action_id: str
    action_class: ActionClass
    reversible: bool
    authority_refs: Sequence[str] = ()
    evidence_refs: Sequence[str] = ()
    tags: Sequence[str] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "action_id", require_non_empty_text(self.action_id, "action_id"))
        if not isinstance(self.action_class, ActionClass):
            raise ValueError("action_class must be an ActionClass")
        if not isinstance(self.reversible, bool):
            raise ValueError("reversible must be a boolean")
        object.__setattr__(self, "authority_refs", _text_tuple(self.authority_refs, "authority_refs", allow_empty=True))
        object.__setattr__(self, "evidence_refs", _text_tuple(self.evidence_refs, "evidence_refs", allow_empty=True))
        object.__setattr__(self, "tags", _text_tuple(self.tags, "tags", allow_empty=True))


@dataclass(frozen=True, slots=True)
class GateEvaluation(ContractRecord):
    """Minimal gate-imprint record for reflective trigger memory."""

    gate_id: str
    symbol_id: str
    confidence: float
    outcome_ref: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "gate_id", require_non_empty_text(self.gate_id, "gate_id"))
        object.__setattr__(self, "symbol_id", require_non_empty_text(self.symbol_id, "symbol_id"))
        object.__setattr__(self, "confidence", require_unit_float(self.confidence, "confidence"))
        object.__setattr__(self, "outcome_ref", require_non_empty_text(self.outcome_ref, "outcome_ref"))


@dataclass(frozen=True, slots=True)
class TransferVerdict(ContractRecord):
    """Result of a cross-domain transfer admission check."""

    candidate: CrossDomainTransferCandidate
    verdict: Verdict
    blockers: Sequence[str]
    required_next_evidence: Sequence[str]

    def __post_init__(self) -> None:
        object.__setattr__(self, "blockers", _text_tuple(self.blockers, "blockers", allow_empty=True))
        object.__setattr__(self, "required_next_evidence", _text_tuple(self.required_next_evidence, "required_next_evidence", allow_empty=True))


@dataclass(frozen=True, slots=True)
class ConceptBirthVerdict(ContractRecord):
    """Result of a concept-birth admission check."""

    candidate: ConceptBirthCandidate
    verdict: Verdict
    blockers: Sequence[str]
    required_next_evidence: Sequence[str]

    def __post_init__(self) -> None:
        object.__setattr__(self, "blockers", _text_tuple(self.blockers, "blockers", allow_empty=True))
        object.__setattr__(self, "required_next_evidence", _text_tuple(self.required_next_evidence, "required_next_evidence", allow_empty=True))


@dataclass(frozen=True, slots=True)
class GovernedAutonomyDecision(ContractRecord):
    """Governance decision for an action proposal."""

    proposal: ActionProposal
    autonomy_class: AutonomyClass
    status: AutonomyDecisionStatus
    missing_authority: Sequence[str]
    missing_evidence: Sequence[str]
    blockers: Sequence[str]

    def __post_init__(self) -> None:
        object.__setattr__(self, "missing_authority", _text_tuple(self.missing_authority, "missing_authority", allow_empty=True))
        object.__setattr__(self, "missing_evidence", _text_tuple(self.missing_evidence, "missing_evidence", allow_empty=True))
        object.__setattr__(self, "blockers", _text_tuple(self.blockers, "blockers", allow_empty=True))


@dataclass(frozen=True, slots=True)
class IntrospectionQuestion(ContractRecord):
    """Self-question emitted by the cognitive readiness kernel."""

    question: str
    reason_ref: str
    priority: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "question", require_non_empty_text(self.question, "question"))
        object.__setattr__(self, "reason_ref", require_non_empty_text(self.reason_ref, "reason_ref"))
        object.__setattr__(self, "priority", require_unit_float(self.priority, "priority"))


@dataclass(frozen=True, slots=True)
class CognitiveSGIReadinessReport(ContractRecord):
    """Bounded report summarizing Proto-SGI readiness without claiming SGI."""

    readiness_state: ReadinessState
    homeostatic_score: float
    transfer_verdicts: Sequence[TransferVerdict]
    concept_birth_verdicts: Sequence[ConceptBirthVerdict]
    autonomy_decisions: Sequence[GovernedAutonomyDecision]
    self_questions: Sequence[IntrospectionQuestion]
    blockers: Sequence[str]
    required_next_evidence: Sequence[str]

    def __post_init__(self) -> None:
        object.__setattr__(self, "homeostatic_score", require_unit_float(self.homeostatic_score, "homeostatic_score"))
        object.__setattr__(self, "transfer_verdicts", freeze_value(tuple(self.transfer_verdicts)))
        object.__setattr__(self, "concept_birth_verdicts", freeze_value(tuple(self.concept_birth_verdicts)))
        object.__setattr__(self, "autonomy_decisions", freeze_value(tuple(self.autonomy_decisions)))
        object.__setattr__(self, "self_questions", freeze_value(tuple(self.self_questions)))
        object.__setattr__(self, "blockers", _stable_unique_text_tuple(self.blockers))
        object.__setattr__(self, "required_next_evidence", _stable_unique_text_tuple(self.required_next_evidence))


def evaluate_cross_domain_transfer(candidate: CrossDomainTransferCandidate) -> TransferVerdict:
    """Admit transfer only when invariant evidence exists and contradictions are absent."""

    blockers: list[str] = []
    next_evidence: list[str] = []
    if candidate.source_domain == candidate.target_domain:
        blockers.append("source_and_target_domain_must_differ")
    if candidate.contradiction_refs:
        blockers.append("contradiction_refs_must_be_resolved")
        next_evidence.append("contradiction_resolution_receipt")
    if candidate.confidence < 0.65:
        blockers.append("transfer_confidence_below_threshold")
        next_evidence.append("cross_domain_mapping_validation_receipt")
    verdict = Verdict.BLOCKED if blockers else Verdict.ADMITTED
    return TransferVerdict(
        candidate=candidate,
        verdict=verdict,
        blockers=tuple(blockers),
        required_next_evidence=tuple(next_evidence),
    )


def evaluate_concept_birth(candidate: ConceptBirthCandidate) -> ConceptBirthVerdict:
    """Admit a new concept only when necessity is high and overlap is low."""

    blockers: list[str] = []
    next_evidence: list[str] = []
    if candidate.necessity_score < 0.70:
        blockers.append("concept_necessity_below_threshold")
        next_evidence.append("missing_concept_failure_case")
    if candidate.overlap_score > 0.40:
        blockers.append("concept_overlap_above_threshold")
        next_evidence.append("ontology_non_duplication_receipt")
    required_governance = {"ontology_review_ref", "learning_admission_ref"}
    missing_governance = sorted(required_governance.difference(candidate.governance_refs))
    for ref in missing_governance:
        blockers.append(f"missing_governance:{ref}")
        next_evidence.append(ref)
    verdict = Verdict.BLOCKED if blockers else Verdict.ADMITTED
    return ConceptBirthVerdict(
        candidate=candidate,
        verdict=verdict,
        blockers=tuple(blockers),
        required_next_evidence=tuple(next_evidence),
    )


def classify_governed_autonomy(proposal: ActionProposal) -> GovernedAutonomyDecision:
    """Classify autonomy and block prohibited or insufficiently witnessed actions."""

    prohibited_tags = {"hidden_goal", "bypass_governance", "silent_self_expansion"}
    if prohibited_tags.intersection(proposal.tags):
        blockers = tuple(f"prohibited_tag:{tag}" for tag in sorted(prohibited_tags.intersection(proposal.tags)))
        return GovernedAutonomyDecision(
            proposal=proposal,
            autonomy_class=AutonomyClass.PROHIBITED,
            status=AutonomyDecisionStatus.BLOCK,
            missing_authority=(),
            missing_evidence=(),
            blockers=blockers,
        )

    if proposal.action_class is ActionClass.EPISTEMIC and proposal.reversible:
        return GovernedAutonomyDecision(
            proposal=proposal,
            autonomy_class=AutonomyClass.SAFE,
            status=AutonomyDecisionStatus.ALLOW,
            missing_authority=(),
            missing_evidence=(),
            blockers=(),
        )

    autonomy_class, required_authority, required_evidence = _requirements_for(proposal)
    observed_authority = set(proposal.authority_refs)
    observed_evidence = set(proposal.evidence_refs)
    missing_authority = tuple(ref for ref in required_authority if ref not in observed_authority)
    missing_evidence = tuple(ref for ref in required_evidence if ref not in observed_evidence)
    blockers = tuple(
        [*(f"missing_authority:{ref}" for ref in missing_authority), *(f"missing_evidence:{ref}" for ref in missing_evidence)]
    )
    status = AutonomyDecisionStatus.BLOCK if blockers else AutonomyDecisionStatus.SIMULATION_ONLY
    return GovernedAutonomyDecision(
        proposal=proposal,
        autonomy_class=autonomy_class,
        status=status,
        missing_authority=missing_authority,
        missing_evidence=missing_evidence,
        blockers=blockers,
    )


def generate_self_questions(
    homeostasis: HomeostaticVector,
    transfer_verdicts: Sequence[TransferVerdict],
    concept_birth_verdicts: Sequence[ConceptBirthVerdict],
    autonomy_decisions: Sequence[GovernedAutonomyDecision],
) -> tuple[IntrospectionQuestion, ...]:
    """Generate bounded self-questions from low health and blocked evidence lanes."""

    questions: list[IntrospectionQuestion] = []
    if homeostasis.prediction_accuracy < 0.55:
        questions.append(
            IntrospectionQuestion(
                question="Which causal assumption made the predicted outcome unreliable?",
                reason_ref="prediction_accuracy_below_threshold",
                priority=1.0 - homeostasis.prediction_accuracy,
            )
        )
    if homeostasis.memory_integrity < 0.65:
        questions.append(
            IntrospectionQuestion(
                question="Which memory anchor is missing or inconsistent with the causal trace?",
                reason_ref="memory_integrity_below_threshold",
                priority=1.0 - homeostasis.memory_integrity,
            )
        )
    if homeostasis.governance_safety < 0.80:
        questions.append(
            IntrospectionQuestion(
                question="Which governance witness is needed before the next effect-bearing step?",
                reason_ref="governance_safety_below_threshold",
                priority=1.0 - homeostasis.governance_safety,
            )
        )
    for verdict in transfer_verdicts:
        if verdict.verdict is Verdict.BLOCKED:
            questions.append(
                IntrospectionQuestion(
                    question="What invariant or contradiction must be resolved before this domain transfer is valid?",
                    reason_ref=f"transfer_blocked:{verdict.candidate.source_domain}->{verdict.candidate.target_domain}",
                    priority=0.90,
                )
            )
    for verdict in concept_birth_verdicts:
        if verdict.verdict is Verdict.BLOCKED:
            questions.append(
                IntrospectionQuestion(
                    question="Why is a new concept necessary instead of reusing an existing ontology symbol?",
                    reason_ref=f"concept_birth_blocked:{verdict.candidate.concept_id}",
                    priority=0.85,
                )
            )
    for decision in autonomy_decisions:
        if decision.status is AutonomyDecisionStatus.BLOCK:
            questions.append(
                IntrospectionQuestion(
                    question="Which authority, evidence, or rollback witness is missing for this action?",
                    reason_ref=f"autonomy_blocked:{decision.proposal.action_id}",
                    priority=0.95,
                )
            )
    return tuple(questions)


def build_cognitive_sgi_readiness_report(
    *,
    homeostasis: HomeostaticVector,
    transfer_candidates: Sequence[CrossDomainTransferCandidate] = (),
    concept_birth_candidates: Sequence[ConceptBirthCandidate] = (),
    action_proposals: Sequence[ActionProposal] = (),
) -> CognitiveSGIReadinessReport:
    """Build a deterministic Proto-SGI readiness report from supplied evidence."""

    transfer_verdicts = tuple(evaluate_cross_domain_transfer(candidate) for candidate in transfer_candidates)
    concept_verdicts = tuple(evaluate_concept_birth(candidate) for candidate in concept_birth_candidates)
    autonomy_decisions = tuple(classify_governed_autonomy(proposal) for proposal in action_proposals)
    blockers = _collect_blockers(transfer_verdicts, concept_verdicts, autonomy_decisions)
    next_evidence = _collect_next_evidence(transfer_verdicts, concept_verdicts, autonomy_decisions)
    self_questions = generate_self_questions(homeostasis, transfer_verdicts, concept_verdicts, autonomy_decisions)
    readiness_state = _readiness_state_for(
        homeostasis=homeostasis,
        transfer_verdicts=transfer_verdicts,
        concept_verdicts=concept_verdicts,
        autonomy_decisions=autonomy_decisions,
        blockers=blockers,
    )
    return CognitiveSGIReadinessReport(
        readiness_state=readiness_state,
        homeostatic_score=homeostasis.balance_score(),
        transfer_verdicts=transfer_verdicts,
        concept_birth_verdicts=concept_verdicts,
        autonomy_decisions=autonomy_decisions,
        self_questions=self_questions,
        blockers=blockers,
        required_next_evidence=next_evidence,
    )


def _requirements_for(proposal: ActionProposal) -> tuple[AutonomyClass, tuple[str, ...], tuple[str, ...]]:
    if proposal.action_class is ActionClass.CORE_MUTATION:
        return (
            AutonomyClass.RESTRICTED,
            ("phi_gov_authority_ref",),
            ("mutation_sandbox_receipt", "rollback_ref", "invariant_check_passed"),
        )
    if proposal.action_class is ActionClass.EXTERNAL_EFFECT or not proposal.reversible:
        return (
            AutonomyClass.GUARDED,
            ("uao_policy_ref", "life_meaning_judgment_ref"),
            ("rollback_ref", "effect_boundary_receipt"),
        )
    return (AutonomyClass.GUARDED, ("uao_policy_ref",), ("rollback_ref",))


def _readiness_state_for(
    *,
    homeostasis: HomeostaticVector,
    transfer_verdicts: Sequence[TransferVerdict],
    concept_verdicts: Sequence[ConceptBirthVerdict],
    autonomy_decisions: Sequence[GovernedAutonomyDecision],
    blockers: Sequence[str],
) -> ReadinessState:
    if blockers or homeostasis.governance_safety < 0.70:
        return ReadinessState.BLOCKED
    has_admitted_transfer = any(verdict.verdict is Verdict.ADMITTED for verdict in transfer_verdicts)
    has_admitted_concept = any(verdict.verdict is Verdict.ADMITTED for verdict in concept_verdicts)
    autonomy_non_blocked = all(decision.status is not AutonomyDecisionStatus.BLOCK for decision in autonomy_decisions)
    if has_admitted_transfer and has_admitted_concept and autonomy_non_blocked and homeostasis.balance_score() >= 0.70:
        return ReadinessState.LEVEL_4_CANDIDATE
    return ReadinessState.PROTO_SGI_LEVEL_3


def _collect_blockers(
    transfer_verdicts: Sequence[TransferVerdict],
    concept_verdicts: Sequence[ConceptBirthVerdict],
    autonomy_decisions: Sequence[GovernedAutonomyDecision],
) -> tuple[str, ...]:
    blockers: list[str] = []
    for verdict in transfer_verdicts:
        blockers.extend(f"transfer:{blocker}" for blocker in verdict.blockers)
    for verdict in concept_verdicts:
        blockers.extend(f"concept_birth:{blocker}" for blocker in verdict.blockers)
    for decision in autonomy_decisions:
        blockers.extend(f"autonomy:{blocker}" for blocker in decision.blockers)
    return _stable_unique_text_tuple(blockers)


def _collect_next_evidence(
    transfer_verdicts: Sequence[TransferVerdict],
    concept_verdicts: Sequence[ConceptBirthVerdict],
    autonomy_decisions: Sequence[GovernedAutonomyDecision],
) -> tuple[str, ...]:
    evidence: list[str] = []
    for verdict in transfer_verdicts:
        evidence.extend(verdict.required_next_evidence)
    for verdict in concept_verdicts:
        evidence.extend(verdict.required_next_evidence)
    for decision in autonomy_decisions:
        evidence.extend(decision.missing_authority)
        evidence.extend(decision.missing_evidence)
    return _stable_unique_text_tuple(evidence)


def _text_tuple(values: Sequence[str], field_name: str, *, allow_empty: bool = False) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)) or not isinstance(values, (tuple, list)):
        raise ValueError(f"{field_name} must be an array")
    normalized: list[str] = []
    for index, value in enumerate(values):
        normalized.append(require_non_empty_text(value, f"{field_name}[{index}]"))
    if not normalized and not allow_empty:
        raise ValueError(f"{field_name} must contain at least one item")
    return tuple(normalized)


def _stable_unique_text_tuple(values: Sequence[str]) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)) or not isinstance(values, (tuple, list)):
        raise ValueError("values must be an array")
    return tuple(sorted(dict.fromkeys(require_non_empty_text(value, "value") for value in values)))
