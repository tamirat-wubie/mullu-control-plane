"""Bridge Phi-GPS problem objects into read-only InceptaDive reports.

Purpose: enrich governed Phi-GPS v3 problem objects with InceptaDive-M
structural findings without granting execution authority.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: Phi-GPS v3 contracts, Concept Box projections, axis traversal,
and public Incepta Sigma/Mesh scoring.
Invariants:
  - Bridge output is advisory and never authorizes execution.
  - ProblemStar field order and identity are preserved.
  - Every emitted layer, finding, score, and gap is traceable to a field.
  - Scoring uses the audited InceptaMesh denominator guard.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping, Sequence

from mcoi_runtime.core.concept_box_ledger import ConceptBox, ConceptBoxType
from mcoi_runtime.core.incepta_scoring_adapter import (
    InceptaScore,
    PromotionRecommendation,
    ResonanceLinks,
    ScoringInput,
    score_axis_finding,
)
from mcoi_runtime.core.inceptadive_axis_traversal import (
    AxisFinding,
    AxisTraversalPolicy,
    DeltaType,
    SuppressionVector,
    traverse_concept_box,
)
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError, stable_identifier
from mcoi_runtime.core.note_memory_mesh import ProofState as MeshProofState
from mcoi_runtime.core.phi_gps import (
    CompiledProblem,
    ProblemFieldStatus,
    ProblemStar,
    ProblemStarField,
    SolverMode,
)


__all__ = [
    "PhiInceptaDiveLayer",
    "PhiInceptaDiveReport",
    "build_phi_inceptadive_report",
    "build_compiled_problem_dive_report",
    "problem_star_to_concept_boxes",
]


_FIELD_LAYER_LABELS: Mapping[str, str] = {
    "W": "world-state",
    "B": "belief-state",
    "O": "observation-model",
    "I": "interface-boundary",
    "G": "goal-region",
    "U": "utility-model",
    "Lambda": "hard-law-set",
    "N": "norm-set",
    "A_e": "epistemic-actions",
    "A_w": "world-actions",
    "T": "transition-model",
    "R": "resource-envelope",
    "K": "knowledge-base",
    "Pi": "proof-obligations",
}

_EPISTEMIC_FIELDS = frozenset({"B", "O", "A_e", "K"})
_ACTION_FIELDS = frozenset({"A_e", "A_w", "T"})
_GOVERNANCE_FIELDS = frozenset({"I", "Lambda", "N", "R", "Pi"})
_GOAL_FIELDS = frozenset({"G", "U", "Pi"})


@dataclass(frozen=True, slots=True)
class PhiInceptaDiveLayer:
    """One field-derived structural layer in the Phi-GPS/InceptaDive bridge."""

    layer_id: str
    field_name: str
    layer_label: str
    status: ProblemFieldStatus
    concept_box_id: str
    evidence_refs: tuple[str, ...]
    hidden_assumption: bool
    proof_gap: bool

    def __post_init__(self) -> None:
        if not self.layer_id.strip():
            raise RuntimeCoreInvariantError("layer_id must be non-empty")
        if not self.field_name.strip():
            raise RuntimeCoreInvariantError("field_name must be non-empty")
        if not self.layer_label.strip():
            raise RuntimeCoreInvariantError("layer_label must be non-empty")
        if not self.concept_box_id.strip():
            raise RuntimeCoreInvariantError("concept_box_id must be non-empty")
        if not isinstance(self.status, ProblemFieldStatus):
            object.__setattr__(self, "status", ProblemFieldStatus(str(self.status)))
        object.__setattr__(self, "evidence_refs", _text_tuple(self.evidence_refs))

    def to_dict(self) -> dict[str, object]:
        """Return a deterministic JSON-compatible layer."""

        return {
            "layer_id": self.layer_id,
            "field_name": self.field_name,
            "layer_label": self.layer_label,
            "status": self.status.value,
            "concept_box_id": self.concept_box_id,
            "evidence_refs": list(self.evidence_refs),
            "hidden_assumption": self.hidden_assumption,
            "proof_gap": self.proof_gap,
        }


@dataclass(frozen=True, slots=True)
class PhiInceptaDiveReport:
    """Advisory InceptaDive report derived from a governed Phi-GPS problem."""

    report_id: str
    problem_id: str
    layers: tuple[PhiInceptaDiveLayer, ...]
    concept_boxes: tuple[ConceptBox, ...]
    axis_findings: tuple[AxisFinding, ...]
    scores: tuple[InceptaScore, ...]
    suggested_solver_modes: tuple[SolverMode, ...]
    proof_gaps: tuple[str, ...]
    hidden_assumptions: tuple[str, ...]
    repair_recommendations: tuple[str, ...]
    lineage: tuple[str, ...] = ("Phi-GPS-v3", "InceptaDive-M", "InceptaMesh")
    execution_approval: bool = False

    def __post_init__(self) -> None:
        if not self.report_id.strip():
            raise RuntimeCoreInvariantError("report_id must be non-empty")
        if not self.problem_id.strip():
            raise RuntimeCoreInvariantError("problem_id must be non-empty")
        if not self.layers:
            raise RuntimeCoreInvariantError("Phi-InceptaDive report requires layers")
        if self.execution_approval:
            raise RuntimeCoreInvariantError("Phi-InceptaDive report cannot approve execution")
        object.__setattr__(self, "suggested_solver_modes", _solver_modes(self.suggested_solver_modes))
        object.__setattr__(self, "proof_gaps", _text_tuple(self.proof_gaps))
        object.__setattr__(self, "hidden_assumptions", _text_tuple(self.hidden_assumptions))
        object.__setattr__(self, "repair_recommendations", _text_tuple(self.repair_recommendations))
        object.__setattr__(self, "lineage", _text_tuple(self.lineage))

    @property
    def fracture_count(self) -> int:
        """Return the number of fracture findings in the report."""

        return sum(1 for finding in self.axis_findings if finding.delta_type == DeltaType.FRACTURE)

    @property
    def promotion_candidate_count(self) -> int:
        """Return the number of candidate scores strong enough to promote."""

        return sum(
            1
            for score in self.scores
            if score.promotion_recommendation == PromotionRecommendation.PROMOTE_CANDIDATE
        )

    @property
    def requires_repair(self) -> bool:
        """Return whether the report contains bounded repair work."""

        return bool(self.proof_gaps or self.repair_recommendations or self.fracture_count)

    def to_dict(self) -> dict[str, object]:
        """Return a deterministic JSON-compatible report."""

        return {
            "report_id": self.report_id,
            "problem_id": self.problem_id,
            "layers": [layer.to_dict() for layer in self.layers],
            "concept_boxes": [box.to_dict() for box in self.concept_boxes],
            "axis_findings": [finding.to_dict() for finding in self.axis_findings],
            "scores": [score.to_dict() for score in self.scores],
            "suggested_solver_modes": [mode.value for mode in self.suggested_solver_modes],
            "proof_gaps": list(self.proof_gaps),
            "hidden_assumptions": list(self.hidden_assumptions),
            "repair_recommendations": list(self.repair_recommendations),
            "fracture_count": self.fracture_count,
            "promotion_candidate_count": self.promotion_candidate_count,
            "requires_repair": self.requires_repair,
            "lineage": list(self.lineage),
            "execution_approval": False,
        }


def build_compiled_problem_dive_report(
    compiled: CompiledProblem,
    *,
    max_depth: int = 3,
    max_findings: int = 32,
) -> PhiInceptaDiveReport:
    """Build an advisory InceptaDive report from a compiled Phi-GPS problem."""

    base_report = build_phi_inceptadive_report(
        compiled.kernel_draft,
        max_depth=max_depth,
        max_findings=max_findings,
    )
    compiler_gaps = tuple(
        f"compiler_unknown:{unknown.dimension}" for unknown in compiled.unknowns
    ) + tuple(
        f"compiler_contradiction:{contradiction.contradiction_id}"
        for contradiction in compiled.contradictions
    )
    compiler_assumptions = tuple(
        f"compiler_assumption:{assumption.assumption_id}" for assumption in compiled.assumptions
    )
    repair_recommendations = tuple(base_report.repair_recommendations) + tuple(
        f"resolve {gap}" for gap in compiler_gaps
    )
    payload = {
        "base_report": base_report.report_id,
        "compiler_gaps": compiler_gaps,
        "compiler_assumptions": compiler_assumptions,
    }
    return PhiInceptaDiveReport(
        report_id=stable_identifier("phi-inceptadive-report", payload),
        problem_id=compiled.problem_id,
        layers=base_report.layers,
        concept_boxes=base_report.concept_boxes,
        axis_findings=base_report.axis_findings,
        scores=base_report.scores,
        suggested_solver_modes=base_report.suggested_solver_modes,
        proof_gaps=_dedupe_text(tuple(base_report.proof_gaps) + compiler_gaps),
        hidden_assumptions=_dedupe_text(tuple(base_report.hidden_assumptions) + compiler_assumptions),
        repair_recommendations=_dedupe_text(repair_recommendations),
    )


def build_phi_inceptadive_report(
    problem: ProblemStar,
    *,
    max_depth: int = 3,
    max_findings: int = 32,
) -> PhiInceptaDiveReport:
    """Bridge one Phi-GPS v3 ProblemStar into an advisory InceptaDive report."""

    if max_findings < 1:
        raise RuntimeCoreInvariantError("max_findings must be positive")
    boxes = problem_star_to_concept_boxes(problem)
    if not boxes:
        raise RuntimeCoreInvariantError("ProblemStar produced no Concept Boxes")
    traversal_policy = AxisTraversalPolicy(max_depth=max_depth)
    layers = tuple(_layer_from_box(problem.field(box.identity_facets[0]), box) for box in boxes)
    findings = _bounded_findings(
        finding
        for box in boxes
        for finding in traverse_concept_box(
            box,
            related_boxes=tuple(related for related in boxes if related.box_id != box.box_id),
            policy=traversal_policy,
        ).findings
    )[:max_findings]
    scores = _score_findings(findings)
    proof_gaps = _proof_gaps(problem, scores)
    hidden_assumptions = _hidden_assumptions(problem)
    repair_recommendations = _repair_recommendations(findings, scores, proof_gaps)
    suggested_modes = _suggest_solver_modes(problem, findings, scores, proof_gaps)
    report_payload = {
        "problem_id": problem.problem_id,
        "boxes": [box.box_id for box in boxes],
        "findings": [finding.finding_id for finding in findings],
        "scores": [score.score_id for score in scores],
        "proof_gaps": proof_gaps,
    }
    return PhiInceptaDiveReport(
        report_id=stable_identifier("phi-inceptadive-report", report_payload),
        problem_id=problem.problem_id,
        layers=layers,
        concept_boxes=boxes,
        axis_findings=findings,
        scores=scores,
        suggested_solver_modes=suggested_modes,
        proof_gaps=proof_gaps,
        hidden_assumptions=hidden_assumptions,
        repair_recommendations=repair_recommendations,
    )


def problem_star_to_concept_boxes(problem: ProblemStar) -> tuple[ConceptBox, ...]:
    """Project canonical ProblemStar fields into InceptaDive Concept Boxes."""

    boxes = tuple(_field_to_concept_box(problem, field) for field in problem.fields)
    _assert_unique_box_ids(boxes)
    return boxes


def _field_to_concept_box(problem: ProblemStar, field: ProblemStarField) -> ConceptBox:
    label = _FIELD_LAYER_LABELS.get(field.name, field.name)
    status_text = f"status:{field.status.value}"
    identity = (field.name, f"{label}:{status_text}")
    evidence_refs = field.evidence_refs or ((problem.input_hash,) if problem.input_hash else ("phi-gps-kernel",))
    return ConceptBox(
        box_id="pending",
        box_type=ConceptBoxType.PROCESS,
        source_note_ids=(problem.problem_id,),
        source_event_ids=(f"{problem.problem_id}:{field.name}",),
        identity_facets=identity,
        behavior_facets=_field_behavior_facets(field),
        intention_facets=_field_intention_facets(field),
        cause_facets=_field_cause_facets(problem, field),
        effect_facets=_field_effect_facets(field),
        risk_facets=_field_risk_facets(field),
        evidence_refs=evidence_refs,
        created_at="1970-01-01T00:00:00+00:00",
        updated_at="1970-01-01T00:00:00+00:00",
        lineage=("Phi-GPS-v3", "InceptaDive-M", "ProblemStar-field"),
        proof_state=_mesh_proof_state(field.status),
    ).with_integrity()


def _field_behavior_facets(field: ProblemStarField) -> tuple[str, ...]:
    facets: list[str] = []
    if field.name in _EPISTEMIC_FIELDS:
        facets.append(f"{field.name}:supports knowing")
    if field.name in _ACTION_FIELDS:
        facets.append(f"{field.name}:controls possible action")
    if field.status == ProblemFieldStatus.UNKNOWN:
        facets.append(f"{field.name}:requires sensing before closure")
    return tuple(facets)


def _field_intention_facets(field: ProblemStarField) -> tuple[str, ...]:
    if field.name in _GOAL_FIELDS:
        return (f"{field.name}:defines closure or value",)
    return ()


def _field_cause_facets(problem: ProblemStar, field: ProblemStarField) -> tuple[str, ...]:
    if field.evidence_refs:
        return tuple(f"evidence:{ref}" for ref in field.evidence_refs)
    if problem.input_hash:
        return (f"input_hash:{problem.input_hash}",)
    return ()


def _field_effect_facets(field: ProblemStarField) -> tuple[str, ...]:
    if field.name in _GOVERNANCE_FIELDS:
        return (f"{field.name}:constrains admissible solution",)
    if field.name in _ACTION_FIELDS:
        return (f"{field.name}:changes route or preflight",)
    return ()


def _field_risk_facets(field: ProblemStarField) -> tuple[str, ...]:
    facets: list[str] = []
    if field.status in (
        ProblemFieldStatus.UNKNOWN,
        ProblemFieldStatus.CONFLICTING,
        ProblemFieldStatus.FORBIDDEN,
        ProblemFieldStatus.HYPOTHESIZED,
    ):
        facets.append(f"{field.name}:status {field.status.value}")
    if field.name in ("Lambda", "N", "A_w", "Pi"):
        facets.append(f"{field.name}:governance sensitive")
    return tuple(facets)


def _mesh_proof_state(status: ProblemFieldStatus) -> MeshProofState:
    if status == ProblemFieldStatus.KNOWN:
        return MeshProofState.PASS
    if status in (ProblemFieldStatus.CONFLICTING, ProblemFieldStatus.FORBIDDEN):
        return MeshProofState.FAIL
    return MeshProofState.UNKNOWN


def _layer_from_box(field: ProblemStarField, box: ConceptBox) -> PhiInceptaDiveLayer:
    return PhiInceptaDiveLayer(
        layer_id=stable_identifier("phi-inceptadive-layer", {"field": field.name, "box": box.box_id}),
        field_name=field.name,
        layer_label=_FIELD_LAYER_LABELS.get(field.name, field.name),
        status=field.status,
        concept_box_id=box.box_id,
        evidence_refs=box.evidence_refs,
        hidden_assumption=field.status == ProblemFieldStatus.HYPOTHESIZED,
        proof_gap=field.status
        in (
            ProblemFieldStatus.UNKNOWN,
            ProblemFieldStatus.CONFLICTING,
            ProblemFieldStatus.FORBIDDEN,
        ),
    )


def _bounded_findings(findings: Iterable[AxisFinding]) -> tuple[AxisFinding, ...]:
    return tuple(
        sorted(
            findings,
            key=lambda finding: (
                finding.delta_type != DeltaType.FRACTURE,
                -finding.confidence,
                finding.finding_id,
            ),
        )
    )


def _score_findings(findings: Sequence[AxisFinding]) -> tuple[InceptaScore, ...]:
    scores: list[InceptaScore] = []
    prior_deltas: list[float] = []
    for index, finding in enumerate(findings, start=1):
        score = score_axis_finding(
            ScoringInput(
                finding=finding,
                layer_index=index,
                semantic_delta_magnitude=1.0,
                resonance_links=_resonance_for_finding(finding),
                observer_penalty=finding.suppression.scope_mismatch,
                history_penalty=finding.suppression.staleness,
                prior_deltas=tuple(prior_deltas[-3:]),
            )
        )
        scores.append(score)
        prior_deltas.append(score.true_delta_score)
    return tuple(scores)


def _resonance_for_finding(finding: AxisFinding) -> ResonanceLinks:
    structural_match = 0.8 if finding.evidence_refs else 0.55
    causal_coherence = 0.85 if "cause" in finding.claim.lower() or "feedback" in finding.claim.lower() else 0.65
    mfidel_judgment = 1.0
    min_alignment = max(0.2, 1.0 - finding.suppression.mean)
    if finding.delta_type == DeltaType.FRACTURE:
        min_alignment = min(min_alignment, 0.75)
    return ResonanceLinks(
        structural_match=structural_match,
        causal_coherence=causal_coherence,
        mfidel_judgment=mfidel_judgment,
        min_alignment=min_alignment,
    )


def _proof_gaps(problem: ProblemStar, scores: Sequence[InceptaScore]) -> tuple[str, ...]:
    gaps: list[str] = []
    for field in problem.fields:
        if field.status in (ProblemFieldStatus.UNKNOWN, ProblemFieldStatus.CONFLICTING, ProblemFieldStatus.FORBIDDEN):
            gaps.append(f"{field.name}:{field.status.value}")
        if field.name == "Pi" and field.status == ProblemFieldStatus.PARTIAL:
            gaps.append("Pi:partial-proof-obligation")
        if field.name in _GOVERNANCE_FIELDS and field.status == ProblemFieldStatus.HYPOTHESIZED:
            gaps.append(f"{field.name}:hypothesized-governance-field")
    gaps.extend(
        f"score:{score.finding_id}:repair-required"
        for score in scores
        if score.promotion_recommendation == PromotionRecommendation.REPAIR_REQUIRED
    )
    return _dedupe_text(gaps)


def _hidden_assumptions(problem: ProblemStar) -> tuple[str, ...]:
    return _dedupe_text(
        f"{field.name}:hypothesized" for field in problem.fields if field.status == ProblemFieldStatus.HYPOTHESIZED
    )


def _repair_recommendations(
    findings: Sequence[AxisFinding],
    scores: Sequence[InceptaScore],
    proof_gaps: Sequence[str],
) -> tuple[str, ...]:
    repairs: list[str] = []
    repairs.extend(finding.repair_requirement for finding in findings if finding.repair_requirement)
    repairs.extend(score.repair_recommendation for score in scores if score.repair_recommendation)
    repairs.extend(f"close proof gap: {gap}" for gap in proof_gaps)
    return _dedupe_text(repairs)


def _suggest_solver_modes(
    problem: ProblemStar,
    findings: Sequence[AxisFinding],
    scores: Sequence[InceptaScore],
    proof_gaps: Sequence[str],
) -> tuple[SolverMode, ...]:
    modes: list[SolverMode] = []
    if problem.unknown_fields or proof_gaps:
        _append_mode(modes, SolverMode.DIAGNOSIS)
    if any(field.name in _GOVERNANCE_FIELDS and field.status != ProblemFieldStatus.KNOWN for field in problem.fields):
        _append_mode(modes, SolverMode.PROOF_CONSTRUCTION)
    if any(finding.delta_type == DeltaType.FRACTURE for finding in findings):
        _append_mode(modes, SolverMode.RISK_CONTAINMENT)
    if any(score.promotion_recommendation == PromotionRecommendation.PROMOTE_CANDIDATE for score in scores):
        _append_mode(modes, SolverMode.DESIGN_SYNTHESIS)
    if not modes:
        _append_mode(modes, SolverMode.SEARCH)
    return tuple(modes)


def _append_mode(modes: list[SolverMode], mode: SolverMode) -> None:
    if mode not in modes:
        modes.append(mode)


def _solver_modes(values: Sequence[SolverMode]) -> tuple[SolverMode, ...]:
    modes = tuple(value if isinstance(value, SolverMode) else SolverMode(str(value)) for value in values)
    if not modes:
        raise RuntimeCoreInvariantError("suggested_solver_modes must be non-empty")
    return modes


def _dedupe_text(values: Iterable[str]) -> tuple[str, ...]:
    observed: list[str] = []
    for value in values:
        text = str(value).strip()
        if text and text not in observed:
            observed.append(text)
    return tuple(observed)


def _text_tuple(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(str(value).strip() for value in values if str(value).strip())


def _assert_unique_box_ids(boxes: Sequence[ConceptBox]) -> None:
    box_ids = [box.box_id for box in boxes]
    if len(box_ids) != len(set(box_ids)):
        raise RuntimeCoreInvariantError("Phi-InceptaDive bridge produced duplicate Concept Box ids")
