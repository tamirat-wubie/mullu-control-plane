"""Gateway candidate composer.

Purpose: Take a ProblemSignature, generate N candidate solver pipelines from a
    registered method capsule registry, execute each candidate through an
    injected evaluator under identical conditions (same budget, timeout, seed,
    metric definitions), record every result (winner and loser) to the
    candidate ledger, and return a comparison report.
Governance scope: candidate-only composition. The composer NEVER promotes a
    capability, NEVER mutates the capability registry, NEVER unblocks promotion.
    The C0–C7 maturity ladder remains the only path to admitted authority.
    The composer's only output is evidence: which candidate pipelines beat the
    declared baseline on the declared primary metric under the declared
    constraints, with negative results preserved for future composer runs.
Dependencies: gateway.problem_signature, gateway.candidate_ledger, and an
    injected EvaluatorCallback. The composer owns orchestration and fairness —
    evaluators own subsystem logic.
Invariants:
  - Every candidate runs under the same budget, timeout, and seed as every
    other candidate for a given signature; no candidate may inherit easier
    conditions than another.
  - The baseline method family declared on the signature is always run if a
    matching capsule exists; comparison is meaningless without it.
  - Candidates whose method families are forbidden by the signature are never
    composed; candidates whose families are not in the allowed list (when one
    is set) are never composed.
  - Every executed candidate produces a ledger record, whether it passed or
    failed; suppressing negative results is forbidden by construction.
  - The composer returns a report, not a deployment. The forge consumes the
    report; governance decides admission.
"""

from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Iterable

from gateway.candidate_ledger import (
    CANDIDATE_OUTCOMES,
    CandidateLedger,
    CandidateRun,
    CandidateScore,
)
from gateway.problem_signature import ProblemMetric, ProblemSignature


@dataclass(frozen=True, slots=True)
class MethodCapsule:
    """One registered method capsule the composer can include in candidates.

    A capsule is a typed wrapper around a method family. The composer does not
    own the implementation; the evaluator does. The capsule declares what the
    method can do, what it costs, and what it requires.
    """

    capsule_id: str
    method_family: str
    declared_inputs: tuple[str, ...]
    declared_outputs: tuple[str, ...]
    declared_assumptions: tuple[str, ...]
    declared_failure_modes: tuple[str, ...]
    cost_class: str = "unknown"  # low | medium | high | unknown
    explainability: str = "unknown"  # low | medium | high | unknown
    risk_ceiling: str = "low"  # max admissible signature.risk
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.capsule_id.strip():
            raise ValueError("capsule_id_required")
        if not self.method_family.strip():
            raise ValueError("method_family_required")
        object.__setattr__(self, "declared_inputs", tuple(self.declared_inputs))
        object.__setattr__(self, "declared_outputs", tuple(self.declared_outputs))
        object.__setattr__(self, "declared_assumptions", tuple(self.declared_assumptions))
        object.__setattr__(self, "declared_failure_modes", tuple(self.declared_failure_modes))


@dataclass(frozen=True, slots=True)
class CandidatePipeline:
    """An ordered composition of method capsules proposed for a signature."""

    pipeline_id: str
    method_families: tuple[str, ...]
    capsule_ids: tuple[str, ...]
    description: str = ""

    def __post_init__(self) -> None:
        if not self.pipeline_id.strip():
            raise ValueError("pipeline_id_required")
        if not self.capsule_ids:
            raise ValueError("pipeline_must_contain_at_least_one_capsule")
        object.__setattr__(self, "method_families", tuple(self.method_families))
        object.__setattr__(self, "capsule_ids", tuple(self.capsule_ids))


@dataclass(frozen=True, slots=True)
class CandidateEvaluation:
    """Raw evaluation result returned by an injected evaluator.

    The composer post-processes this into a CandidateRun by computing the
    baseline_delta against the recorded baseline for the same signature.
    """

    outcome: str  # must be one of CANDIDATE_OUTCOMES
    scores: tuple[CandidateScore, ...]
    failure_modes: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    cost_units: float = 0.0
    duration_seconds: float = 0.0
    notes: str = ""

    def __post_init__(self) -> None:
        if self.outcome not in CANDIDATE_OUTCOMES:
            raise ValueError(f"outcome_must_be_one_of:{','.join(CANDIDATE_OUTCOMES)}")
        object.__setattr__(self, "scores", tuple(self.scores))
        object.__setattr__(self, "failure_modes", tuple(self.failure_modes))
        object.__setattr__(self, "evidence_refs", tuple(self.evidence_refs))


EvaluatorCallback = Callable[[ProblemSignature, CandidatePipeline, str], CandidateEvaluation]


@dataclass(frozen=True, slots=True)
class AdversarialReviewResult:
    """Outcome of an adversarial-review pass on one candidate pipeline.

    A candidate must clear adversarial review in addition to beating the
    baseline on the primary metric. Findings are appended to the ledger
    record so they remain auditable even if the candidate is later
    discarded.
    """

    passed: bool
    findings: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    notes: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "findings", tuple(self.findings))
        object.__setattr__(self, "evidence_refs", tuple(self.evidence_refs))
        if self.passed and self.findings:
            raise ValueError("adversarial_review_passed_cannot_have_findings")
        if not self.passed and not self.findings:
            raise ValueError("adversarial_review_failed_must_explain_with_findings")


AdversarialReviewCallback = Callable[
    [ProblemSignature, CandidatePipeline, "CandidateEvaluation", str],
    AdversarialReviewResult,
]


@dataclass(frozen=True, slots=True)
class CandidateComparisonReport:
    """Final composer output for one signature run."""

    signature_hash: str
    problem_id: str
    primary_metric_id: str
    baseline_record_hash: str
    candidate_record_hashes: tuple[str, ...]
    winner_record_hashes: tuple[str, ...]
    negative_record_hashes: tuple[str, ...]
    adversarial_review_failed_record_hashes: tuple[str, ...]
    skipped_capsule_ids: tuple[str, ...]
    skipped_reasons: dict[str, str]
    baseline_compromised: bool = False
    baseline_findings: tuple[str, ...] = ()
    notes: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "candidate_record_hashes", tuple(self.candidate_record_hashes))
        object.__setattr__(self, "winner_record_hashes", tuple(self.winner_record_hashes))
        object.__setattr__(self, "negative_record_hashes", tuple(self.negative_record_hashes))
        object.__setattr__(
            self,
            "adversarial_review_failed_record_hashes",
            tuple(self.adversarial_review_failed_record_hashes),
        )
        object.__setattr__(self, "skipped_capsule_ids", tuple(self.skipped_capsule_ids))
        object.__setattr__(self, "skipped_reasons", dict(self.skipped_reasons))
        object.__setattr__(self, "baseline_findings", tuple(self.baseline_findings))


_RISK_RANK = {"low": 0, "medium": 1, "high": 2, "physical": 3}


def _capsule_admits_risk(capsule: MethodCapsule, signature_risk: str) -> bool:
    ceiling = _RISK_RANK.get(capsule.risk_ceiling, 0)
    required = _RISK_RANK.get(signature_risk, 0)
    return required <= ceiling


def _derive_run_seed(signature_hash: str, pipeline_id: str) -> str:
    return hashlib.sha256(f"{signature_hash}:{pipeline_id}".encode()).hexdigest()[:16]


def _primary_success_metric(signature: ProblemSignature) -> ProblemMetric:
    success_metrics = signature.success_metrics()
    if not success_metrics:
        raise ValueError("signature_missing_success_metric")
    return success_metrics[0]


def _delta_from_baseline(
    candidate_scores: Iterable[CandidateScore],
    baseline_scores: Iterable[CandidateScore],
) -> dict[str, float]:
    baseline_by_metric = {score.metric_id: score.value for score in baseline_scores}
    deltas: dict[str, float] = {}
    for score in candidate_scores:
        if score.metric_id in baseline_by_metric:
            deltas[score.metric_id] = score.value - baseline_by_metric[score.metric_id]
    return deltas


class CandidateComposer:
    """Compose, run, and record candidate pipelines for a problem signature."""

    def __init__(
        self,
        ledger: CandidateLedger,
        *,
        capsules: tuple[MethodCapsule, ...] = (),
        adversarial_reviewer: AdversarialReviewCallback | None = None,
    ) -> None:
        self._ledger = ledger
        self._capsules: dict[str, MethodCapsule] = {}
        self._adversarial_reviewer = adversarial_reviewer
        for capsule in capsules:
            self.register_capsule(capsule)

    def register_capsule(self, capsule: MethodCapsule) -> None:
        if capsule.capsule_id in self._capsules:
            raise ValueError(f"duplicate_capsule_id:{capsule.capsule_id}")
        self._capsules[capsule.capsule_id] = capsule

    def capsules(self) -> tuple[MethodCapsule, ...]:
        return tuple(self._capsules.values())

    def admissible_capsules(self, signature: ProblemSignature) -> tuple[MethodCapsule, ...]:
        admissible: list[MethodCapsule] = []
        for capsule in self._capsules.values():
            if not signature.admits_method_family(capsule.method_family):
                continue
            if not _capsule_admits_risk(capsule, signature.risk):
                continue
            admissible.append(capsule)
        return tuple(admissible)

    def compose_pipelines(self, signature: ProblemSignature) -> tuple[CandidatePipeline, ...]:
        """Default composition: one single-capsule pipeline per admissible
        capsule. Callers wanting multi-capsule compositions can subclass and
        override this method without touching orchestration or fairness logic.
        """
        admissible = self.admissible_capsules(signature)
        return tuple(
            CandidatePipeline(
                pipeline_id=f"pipeline:{capsule.capsule_id}",
                method_families=(capsule.method_family,),
                capsule_ids=(capsule.capsule_id,),
                description=f"single-capsule pipeline for {capsule.method_family}",
            )
            for capsule in admissible
        )

    def run(
        self,
        signature: ProblemSignature,
        evaluator: EvaluatorCallback,
    ) -> CandidateComparisonReport:
        """Compose candidates, run them under identical conditions, record
        every result to the ledger, and return a comparison report.
        """
        primary_metric = _primary_success_metric(signature)
        skipped: dict[str, str] = {}

        for capsule in self._capsules.values():
            if not signature.admits_method_family(capsule.method_family):
                skipped[capsule.capsule_id] = "method_family_not_admissible"
                continue
            if not _capsule_admits_risk(capsule, signature.risk):
                skipped[capsule.capsule_id] = "risk_ceiling_below_signature_risk"

        pipelines = self.compose_pipelines(signature)

        baseline_pipeline: CandidatePipeline | None = None
        candidate_pipelines: list[CandidatePipeline] = []
        for pipeline in pipelines:
            if (
                signature.baseline_method_family
                and pipeline.method_families == (signature.baseline_method_family,)
                and baseline_pipeline is None
            ):
                baseline_pipeline = pipeline
            else:
                candidate_pipelines.append(pipeline)

        baseline_record: CandidateRun | None = None
        baseline_record_hash = ""
        baseline_findings: tuple[str, ...] = ()
        if baseline_pipeline is not None:
            seed = _derive_run_seed(signature.signature_hash, baseline_pipeline.pipeline_id)
            evaluation = evaluator(signature, baseline_pipeline, seed)
            review = self._maybe_review(signature, baseline_pipeline, evaluation, seed)
            baseline_record = self._ledger.record(
                signature_hash=signature.signature_hash,
                problem_id=signature.problem_id,
                candidate_pipeline_id=baseline_pipeline.pipeline_id,
                method_families=baseline_pipeline.method_families,
                outcome=evaluation.outcome,
                scores=evaluation.scores,
                baseline_delta={},
                failure_modes=evaluation.failure_modes,
                evidence_refs=evaluation.evidence_refs,
                cost_units=evaluation.cost_units,
                duration_seconds=evaluation.duration_seconds,
                run_seed=seed,
                is_baseline=True,
                notes=evaluation.notes,
                adversarial_review_findings=review.findings if review else (),
                adversarial_review_evidence_refs=review.evidence_refs if review else (),
            )
            baseline_record_hash = baseline_record.record_hash
            if review is not None and not review.passed:
                baseline_findings = review.findings

        baseline_compromised = bool(baseline_findings)

        candidate_hashes: list[str] = []
        winner_hashes: list[str] = []
        negative_hashes: list[str] = []
        review_failed_hashes: list[str] = []

        for pipeline in candidate_pipelines:
            seed = _derive_run_seed(signature.signature_hash, pipeline.pipeline_id)
            evaluation = evaluator(signature, pipeline, seed)
            baseline_delta = (
                _delta_from_baseline(evaluation.scores, baseline_record.scores)
                if baseline_record is not None
                else {}
            )
            review = self._maybe_review(signature, pipeline, evaluation, seed)
            record = self._ledger.record(
                signature_hash=signature.signature_hash,
                problem_id=signature.problem_id,
                candidate_pipeline_id=pipeline.pipeline_id,
                method_families=pipeline.method_families,
                outcome=evaluation.outcome,
                scores=evaluation.scores,
                baseline_delta=baseline_delta,
                failure_modes=evaluation.failure_modes,
                evidence_refs=evaluation.evidence_refs,
                cost_units=evaluation.cost_units,
                duration_seconds=evaluation.duration_seconds,
                run_seed=seed,
                is_baseline=False,
                notes=evaluation.notes,
                adversarial_review_findings=review.findings if review else (),
                adversarial_review_evidence_refs=review.evidence_refs if review else (),
            )
            candidate_hashes.append(record.record_hash)
            if record.outcome != "passed":
                negative_hashes.append(record.record_hash)
                continue
            if review is not None and not review.passed:
                review_failed_hashes.append(record.record_hash)
                continue
            if baseline_compromised:
                continue
            delta = baseline_delta.get(primary_metric.metric_id)
            if delta is None:
                continue
            if primary_metric.direction == "maximize" and delta > 0:
                winner_hashes.append(record.record_hash)
            elif primary_metric.direction == "minimize" and delta < 0:
                winner_hashes.append(record.record_hash)

        notes = ""
        if baseline_record is None and signature.baseline_method_family:
            notes = (
                "baseline_method_family declared on signature but no matching capsule "
                "was registered; winners cannot be claimed without a baseline."
            )
        if baseline_compromised:
            notes = (
                (notes + " " if notes else "")
                + "baseline failed adversarial review; no candidate can claim winner "
                "status against an untrusted baseline."
            )

        return CandidateComparisonReport(
            signature_hash=signature.signature_hash,
            problem_id=signature.problem_id,
            primary_metric_id=primary_metric.metric_id,
            baseline_record_hash=baseline_record_hash,
            candidate_record_hashes=tuple(candidate_hashes),
            winner_record_hashes=tuple(winner_hashes),
            negative_record_hashes=tuple(negative_hashes),
            adversarial_review_failed_record_hashes=tuple(review_failed_hashes),
            skipped_capsule_ids=tuple(skipped.keys()),
            skipped_reasons=skipped,
            baseline_compromised=baseline_compromised,
            baseline_findings=baseline_findings,
            notes=notes,
        )

    def _maybe_review(
        self,
        signature: ProblemSignature,
        pipeline: CandidatePipeline,
        evaluation: CandidateEvaluation,
        seed: str,
    ) -> AdversarialReviewResult | None:
        """Run adversarial review on passing evaluations only.

        Skipping review on failed evaluations is intentional: findings on a
        run that already failed the evaluator add cost without changing the
        outcome — the run was already going to be discarded.
        """
        if self._adversarial_reviewer is None:
            return None
        if evaluation.outcome != "passed":
            return None
        return self._adversarial_reviewer(signature, pipeline, evaluation, seed)


@dataclass(frozen=True, slots=True)
class CompositionSpec:
    """A caller-declared ordered multi-capsule pipeline.

    The Solver Forge composer does not invent compositions. A caller that
    wants to compare multi-step pipelines declares each one explicitly as an
    ordered sequence of registered capsule ids. Data flow between capsules is
    the injected evaluator's responsibility, exactly as for single-capsule
    pipelines — the composer owns orchestration, the evaluator owns subsystem
    logic. The composer never decides how capsules chain; it only declares
    that they do, in the order the caller stated.
    """

    pipeline_id: str
    capsule_ids: tuple[str, ...]
    description: str = ""

    def __post_init__(self) -> None:
        if not self.pipeline_id.strip():
            raise ValueError("pipeline_id_required")
        if not self.capsule_ids:
            raise ValueError("composition_spec_requires_at_least_one_capsule")
        object.__setattr__(self, "capsule_ids", tuple(self.capsule_ids))


@dataclass(frozen=True, slots=True)
class SkippedComposition:
    """Why a declared composition spec was not composed into a pipeline."""

    pipeline_id: str
    reason: str
    offending_capsule_id: str = ""


class DeclaredCompositionComposer(CandidateComposer):
    """Composer that emits caller-declared multi-capsule pipelines.

    Overrides only ``compose_pipelines``. ``run()``, the evaluator gate, the
    adversarial-review gate, per-pipeline seed fairness, the ledger, and the
    comparison report are inherited unchanged from ``CandidateComposer`` — a
    multi-capsule pipeline is recorded, gated, and scored exactly like a
    single-capsule one.

    Chain admissibility rule: EVERY capsule in a declared chain must be
    admissible under the signature (allowed/forbidden method family AND risk
    ceiling). A single inadmissible or unknown capsule poisons the whole
    chain — you cannot run half a pipeline. Poisoned specs are not emitted;
    the reasons are available via ``skipped_compositions()`` for audit,
    mirroring how the base composer surfaces ``skipped_capsule_ids``.

    Baseline contract: ``run()`` still detects the baseline as the pipeline
    whose ``method_families == (signature.baseline_method_family,)`` — a
    single-element tuple. A caller that wants a baseline MUST include a
    single-capsule ``CompositionSpec`` for the baseline family. Multi-capsule
    pipelines can never be mistaken for the baseline. Comparison without a
    baseline yields no winners (same rule as the base composer).
    """

    def __init__(
        self,
        ledger: CandidateLedger,
        *,
        capsules: tuple[MethodCapsule, ...] = (),
        adversarial_reviewer: AdversarialReviewCallback | None = None,
        compositions: tuple[CompositionSpec, ...] = (),
    ) -> None:
        super().__init__(
            ledger,
            capsules=capsules,
            adversarial_reviewer=adversarial_reviewer,
        )
        self._compositions = tuple(compositions)
        self._skipped: list[SkippedComposition] = []

    def skipped_compositions(self) -> tuple[SkippedComposition, ...]:
        """Specs not composed in the most recent ``compose_pipelines`` call."""
        return tuple(self._skipped)

    def compose_pipelines(
        self, signature: ProblemSignature
    ) -> tuple[CandidatePipeline, ...]:
        self._skipped = []
        composed: list[CandidatePipeline] = []
        for spec in self._compositions:
            resolved: list[MethodCapsule] = []
            poisoned = False
            for capsule_id in spec.capsule_ids:
                capsule = self._capsules.get(capsule_id)
                if capsule is None:
                    self._skipped.append(
                        SkippedComposition(
                            pipeline_id=spec.pipeline_id,
                            reason="unknown_capsule_id",
                            offending_capsule_id=capsule_id,
                        )
                    )
                    poisoned = True
                    break
                if not signature.admits_method_family(capsule.method_family):
                    self._skipped.append(
                        SkippedComposition(
                            pipeline_id=spec.pipeline_id,
                            reason="capsule_method_family_not_admissible",
                            offending_capsule_id=capsule_id,
                        )
                    )
                    poisoned = True
                    break
                if not _capsule_admits_risk(capsule, signature.risk):
                    self._skipped.append(
                        SkippedComposition(
                            pipeline_id=spec.pipeline_id,
                            reason="capsule_risk_ceiling_below_signature_risk",
                            offending_capsule_id=capsule_id,
                        )
                    )
                    poisoned = True
                    break
                resolved.append(capsule)
            if poisoned:
                continue
            composed.append(
                CandidatePipeline(
                    pipeline_id=spec.pipeline_id,
                    method_families=tuple(c.method_family for c in resolved),
                    capsule_ids=spec.capsule_ids,
                    description=spec.description,
                )
            )
        return tuple(composed)
