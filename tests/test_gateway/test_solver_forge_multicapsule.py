"""Gateway solver-forge multi-capsule composition tests.

Purpose: verify DeclaredCompositionComposer emits caller-declared ordered
    multi-capsule pipelines, poisons a whole chain on any inadmissible or
    unknown capsule, leaves base single-capsule behavior untouched, and runs
    a multi-capsule winner through both gates and the ledger end-to-end.
Invariants tested:
  - A declared 3-capsule spec emits one CandidatePipeline with 3 ordered
    method_families and 3 capsule_ids.
  - A chain with one forbidden-family capsule is skipped entirely; its
    admissible siblings still compose. Skip reason is auditable.
  - A chain referencing an unknown capsule id is skipped with a precise
    reason naming the offending id.
  - A chain with one capsule whose risk_ceiling is below the signature risk
    is skipped.
  - run() detects the single-capsule baseline spec; multi-capsule pipelines
    are never mistaken for the baseline.
  - A multi-capsule candidate that beats the baseline AND clears adversarial
    review is a winner; the ledger and report agree.
  - The base CandidateComposer is unchanged: same capsules, single-capsule
    behavior identical (no regression from adding the subclass).
"""

from __future__ import annotations

import pytest

from gateway.candidate_composer import (
    AdversarialReviewResult,
    CandidateComposer,
    CandidateEvaluation,
    CandidatePipeline,
    CompositionSpec,
    DeclaredCompositionComposer,
    MethodCapsule,
    SkippedComposition,
)
from gateway.candidate_ledger import (
    CandidateLedger,
    CandidateScore,
    InMemoryCandidateLedgerStore,
)
from gateway.problem_signature import ProblemMetric, ProblemSignature


def _signature(*, risk: str = "low", forbidden: tuple[str, ...] = ()) -> ProblemSignature:
    budget = 0.0 if risk == "low" else 100.0
    timeout = 0.0 if risk == "low" else 5.0
    return ProblemSignature(
        problem_id="invoice_duplicate_detection.v1",
        domain="finance_ops",
        goal="detect duplicate invoice before payment",
        inputs=("invoice",),
        constraints=(),
        risk=risk,
        metrics=(
            ProblemMetric(
                metric_id="precision",
                metric_kind="success",
                direction="maximize",
                threshold=0.5,
            ),
        ),
        required_evidence=(),
        budget_units=budget,
        timeout_seconds=timeout,
        forbidden_method_families=forbidden,
        baseline_method_family="rule_based",
    )


def _capsule(family: str, *, risk_ceiling: str = "low") -> MethodCapsule:
    return MethodCapsule(
        capsule_id=f"capsule:{family}",
        method_family=family,
        declared_inputs=("invoice",),
        declared_outputs=("duplicate_flag",),
        declared_assumptions=(),
        declared_failure_modes=(),
        risk_ceiling=risk_ceiling,
    )


def _ledger() -> CandidateLedger:
    return CandidateLedger(InMemoryCandidateLedgerStore())


# --- CompositionSpec shape --------------------------------------------------


def test_composition_spec_requires_pipeline_id() -> None:
    with pytest.raises(ValueError, match="pipeline_id_required"):
        CompositionSpec(pipeline_id="  ", capsule_ids=("capsule:rule_based",))


def test_composition_spec_requires_at_least_one_capsule() -> None:
    with pytest.raises(ValueError, match="composition_spec_requires_at_least_one_capsule"):
        CompositionSpec(pipeline_id="p", capsule_ids=())


# --- compose_pipelines: multi-capsule emission ------------------------------


def test_declared_three_capsule_chain_emits_ordered_pipeline() -> None:
    composer = DeclaredCompositionComposer(
        _ledger(),
        capsules=(
            _capsule("ocr"),
            _capsule("field_extractor"),
            _capsule("graph_match"),
        ),
        compositions=(
            CompositionSpec(
                pipeline_id="pipe:extract-then-match",
                capsule_ids=(
                    "capsule:ocr",
                    "capsule:field_extractor",
                    "capsule:graph_match",
                ),
                description="ocr -> extract -> match",
            ),
        ),
    )
    pipelines = composer.compose_pipelines(_signature())
    assert len(pipelines) == 1
    p = pipelines[0]
    assert p.pipeline_id == "pipe:extract-then-match"
    assert p.method_families == ("ocr", "field_extractor", "graph_match")
    assert p.capsule_ids == (
        "capsule:ocr",
        "capsule:field_extractor",
        "capsule:graph_match",
    )
    assert composer.skipped_compositions() == ()


# --- Poisoned-chain rules ---------------------------------------------------


def test_chain_with_forbidden_capsule_is_skipped_siblings_survive() -> None:
    composer = DeclaredCompositionComposer(
        _ledger(),
        capsules=(
            _capsule("rule_based"),
            _capsule("graph_match"),
            _capsule("llm_only"),
        ),
        compositions=(
            CompositionSpec(
                pipeline_id="pipe:clean",
                capsule_ids=("capsule:rule_based", "capsule:graph_match"),
            ),
            CompositionSpec(
                pipeline_id="pipe:poisoned",
                capsule_ids=("capsule:graph_match", "capsule:llm_only"),
            ),
        ),
    )
    pipelines = composer.compose_pipelines(_signature(forbidden=("llm_only",)))
    assert {p.pipeline_id for p in pipelines} == {"pipe:clean"}
    skipped = composer.skipped_compositions()
    assert len(skipped) == 1
    assert skipped[0] == SkippedComposition(
        pipeline_id="pipe:poisoned",
        reason="capsule_method_family_not_admissible",
        offending_capsule_id="capsule:llm_only",
    )


def test_chain_with_unknown_capsule_is_skipped_with_precise_reason() -> None:
    composer = DeclaredCompositionComposer(
        _ledger(),
        capsules=(_capsule("rule_based"),),
        compositions=(
            CompositionSpec(
                pipeline_id="pipe:typo",
                capsule_ids=("capsule:rule_based", "capsule:does_not_exist"),
            ),
        ),
    )
    pipelines = composer.compose_pipelines(_signature())
    assert pipelines == ()
    skipped = composer.skipped_compositions()
    assert skipped == (
        SkippedComposition(
            pipeline_id="pipe:typo",
            reason="unknown_capsule_id",
            offending_capsule_id="capsule:does_not_exist",
        ),
    )


def test_chain_with_capsule_below_risk_ceiling_is_skipped() -> None:
    composer = DeclaredCompositionComposer(
        _ledger(),
        capsules=(
            _capsule("rule_based", risk_ceiling="high"),
            _capsule("weak_link", risk_ceiling="low"),
        ),
        compositions=(
            CompositionSpec(
                pipeline_id="pipe:risky",
                capsule_ids=("capsule:rule_based", "capsule:weak_link"),
            ),
        ),
    )
    pipelines = composer.compose_pipelines(_signature(risk="high"))
    assert pipelines == ()
    assert composer.skipped_compositions()[0].reason == (
        "capsule_risk_ceiling_below_signature_risk"
    )
    assert composer.skipped_compositions()[0].offending_capsule_id == "capsule:weak_link"


def test_compose_pipelines_resets_skipped_each_call() -> None:
    composer = DeclaredCompositionComposer(
        _ledger(),
        capsules=(_capsule("rule_based"),),
        compositions=(
            CompositionSpec(pipeline_id="pipe:bad", capsule_ids=("capsule:ghost",)),
        ),
    )
    composer.compose_pipelines(_signature())
    assert len(composer.skipped_compositions()) == 1
    # Second call must not accumulate.
    composer.compose_pipelines(_signature())
    assert len(composer.skipped_compositions()) == 1


# --- Baseline detection with multi-capsule candidates -----------------------


def test_single_capsule_baseline_detected_multi_capsule_never_baseline() -> None:
    ledger = _ledger()
    composer = DeclaredCompositionComposer(
        ledger,
        capsules=(
            _capsule("rule_based"),
            _capsule("ocr"),
            _capsule("graph_match"),
        ),
        compositions=(
            CompositionSpec(
                pipeline_id="pipe:baseline",
                capsule_ids=("capsule:rule_based",),
            ),
            CompositionSpec(
                pipeline_id="pipe:multi",
                capsule_ids=("capsule:ocr", "capsule:graph_match"),
            ),
        ),
    )

    def evaluator(signature, pipeline, seed):
        # baseline (single rule_based) scores 0.5; multi-capsule scores 0.8
        score = 0.5 if pipeline.method_families == ("rule_based",) else 0.8
        return CandidateEvaluation(
            outcome="passed",
            scores=(CandidateScore(metric_id="precision", value=score, direction="maximize"),),
        )

    report = composer.run(_signature(), evaluator)
    assert report.baseline_record_hash != ""
    # The multi-capsule pipeline is a candidate, beats baseline → winner.
    winners = ledger.winners_for(report.signature_hash, primary_metric_id="precision")
    assert len(winners) == 1
    assert winners[0].method_families == ("ocr", "graph_match")
    assert winners[0].is_baseline is False


# --- End-to-end through both gates ------------------------------------------


def test_multi_capsule_winner_clears_evaluator_and_adversarial_gates() -> None:
    ledger = _ledger()

    def reviewer(signature, pipeline, evaluation, seed):
        # Fail review only for a chain containing llm_only.
        if "llm_only" in pipeline.method_families:
            return AdversarialReviewResult(
                passed=False, findings=("prompt_injection_succeeded",)
            )
        return AdversarialReviewResult(passed=True)

    composer = DeclaredCompositionComposer(
        ledger,
        capsules=(
            _capsule("rule_based"),
            _capsule("ocr"),
            _capsule("graph_match"),
            _capsule("llm_only"),
        ),
        adversarial_reviewer=reviewer,
        compositions=(
            CompositionSpec(pipeline_id="pipe:baseline", capsule_ids=("capsule:rule_based",)),
            CompositionSpec(
                pipeline_id="pipe:safe-chain",
                capsule_ids=("capsule:ocr", "capsule:graph_match"),
            ),
            CompositionSpec(
                pipeline_id="pipe:unsafe-chain",
                capsule_ids=("capsule:ocr", "capsule:llm_only"),
            ),
        ),
    )

    def evaluator(signature, pipeline, seed):
        if pipeline.method_families == ("rule_based",):
            score = 0.5
        elif "llm_only" in pipeline.method_families:
            score = 0.99  # highest raw score but fails adversarial gate
        else:
            score = 0.8
        return CandidateEvaluation(
            outcome="passed",
            scores=(CandidateScore(metric_id="precision", value=score, direction="maximize"),),
        )

    report = composer.run(_signature(), evaluator)
    winners = ledger.winners_for(report.signature_hash, primary_metric_id="precision")
    winner_pipelines = {w.candidate_pipeline_id for w in winners}
    # safe-chain wins; unsafe-chain (higher raw score) excluded by gate 2.
    assert winner_pipelines == {"pipe:safe-chain"}
    assert len(report.adversarial_review_failed_record_hashes) == 1


# --- Base composer regression guard -----------------------------------------


def test_base_composer_single_capsule_behavior_unchanged() -> None:
    """Adding the subclass must not alter base CandidateComposer behavior."""
    ledger = _ledger()
    base = CandidateComposer(
        ledger,
        capsules=(_capsule("rule_based"), _capsule("graph_match")),
    )
    pipelines = base.compose_pipelines(_signature())
    # One single-capsule pipeline per admissible capsule, exactly as before.
    assert {p.pipeline_id for p in pipelines} == {
        "pipeline:capsule:rule_based",
        "pipeline:capsule:graph_match",
    }
    for p in pipelines:
        assert len(p.capsule_ids) == 1
        assert len(p.method_families) == 1


# --- Audit refinements: truthful skip reporting + duplicate-id safety -------


def _passing_evaluator(signature, pipeline, seed):
    fam = pipeline.method_families[0]
    score = 0.5 if fam == "rule_based" else 0.8
    return CandidateEvaluation(
        outcome="passed",
        scores=(CandidateScore(metric_id="precision", value=score, direction="maximize"),),
    )


def test_report_skip_fields_describe_composition_skips_not_capsule_fiction() -> None:
    """Regression: for the declared composer, report.skipped_* must describe
    the composition-level skips (keyed by pipeline id), NOT the base composer's
    single-capsule admissibility view, which never ran for this strategy.
    """
    ledger = _ledger()
    composer = DeclaredCompositionComposer(
        ledger,
        capsules=(_capsule("rule_based"), _capsule("graph_match"), _capsule("llm_only")),
        compositions=(
            CompositionSpec(pipeline_id="pipe:baseline", capsule_ids=("capsule:rule_based",)),
            CompositionSpec(pipeline_id="pipe:cand", capsule_ids=("capsule:graph_match",)),
            CompositionSpec(pipeline_id="pipe:poison", capsule_ids=("capsule:llm_only",)),
        ),
    )
    report = composer.run(_signature(forbidden=("llm_only",)), _passing_evaluator)
    # The skipped UNIT is the composition pipe:poison, with the offending
    # capsule encoded in the reason — not a bare capsule id.
    assert report.skipped_capsule_ids == ("pipe:poison",)
    assert report.skipped_reasons == {
        "pipe:poison": "capsule_method_family_not_admissible:capsule:llm_only"
    }
    # The detailed record remains available via skipped_compositions().
    assert composer.skipped_compositions()[0].offending_capsule_id == "capsule:llm_only"
    # And the candidate that survived is still the real winner.
    winners = ledger.winners_for(report.signature_hash, primary_metric_id="precision")
    assert {w.candidate_pipeline_id for w in winners} == {"pipe:cand"}


def test_risk_ceiling_chain_skip_surfaces_in_report() -> None:
    """A chain poisoned by a below-ceiling capsule is reported with the
    risk reason and the offending capsule, keyed by the composition id.
    """
    ledger = _ledger()
    composer = DeclaredCompositionComposer(
        ledger,
        capsules=(
            _capsule("rule_based", risk_ceiling="high"),
            _capsule("weak_link", risk_ceiling="low"),
        ),
        compositions=(
            CompositionSpec(pipeline_id="pipe:baseline", capsule_ids=("capsule:rule_based",)),
            CompositionSpec(
                pipeline_id="pipe:risky",
                capsule_ids=("capsule:rule_based", "capsule:weak_link"),
            ),
        ),
    )
    report = composer.run(_signature(risk="high"), _passing_evaluator)
    assert report.skipped_capsule_ids == ("pipe:risky",)
    assert report.skipped_reasons == {
        "pipe:risky": "capsule_risk_ceiling_below_signature_risk:capsule:weak_link"
    }


def test_duplicate_pipeline_id_is_skipped_not_crashed() -> None:
    """Regression: two CompositionSpecs sharing a pipeline_id must not crash
    mid-run with an opaque duplicate_record_hash. The later duplicate is
    skipped with a clear reason; the run completes and the first occurrence
    is the one that reaches the ledger.
    """
    ledger = _ledger()
    composer = DeclaredCompositionComposer(
        ledger,
        capsules=(_capsule("rule_based"), _capsule("graph_match")),
        compositions=(
            CompositionSpec(pipeline_id="pipe:baseline", capsule_ids=("capsule:rule_based",)),
            CompositionSpec(pipeline_id="dup", capsule_ids=("capsule:graph_match",)),
            CompositionSpec(pipeline_id="dup", capsule_ids=("capsule:graph_match",)),
        ),
    )
    # Must not raise.
    report = composer.run(_signature(), _passing_evaluator)

    dup_skips = [
        s for s in composer.skipped_compositions() if s.reason == "duplicate_pipeline_id"
    ]
    assert [s.pipeline_id for s in dup_skips] == ["dup"]
    # Exactly two records reach the ledger: baseline + the first 'dup'.
    assert len(ledger.for_signature(report.signature_hash)) == 2
    assert "dup" in report.skipped_reasons
    assert report.skipped_reasons["dup"] == "duplicate_pipeline_id"
    # The first 'dup' still competed and won.
    winners = ledger.winners_for(report.signature_hash, primary_metric_id="precision")
    assert {w.candidate_pipeline_id for w in winners} == {"dup"}


def test_base_composer_skip_report_unchanged_after_refactor() -> None:
    """Belt-and-suspenders: extracting _composer_skips() must keep the base
    composer's report skip fields keyed by capsule id with the original
    reasons.
    """
    from gateway.candidate_composer import CandidateScore as _CS  # noqa: F401

    ledger = _ledger()
    base = CandidateComposer(
        ledger,
        capsules=(_capsule("rule_based"), _capsule("graph_match"), _capsule("forbidden_fam")),
    )

    def evaluator(signature, pipeline, seed):
        fam = pipeline.method_families[0]
        score = 0.5 if fam == "rule_based" else 0.8
        return CandidateEvaluation(
            outcome="passed",
            scores=(CandidateScore(metric_id="precision", value=score, direction="maximize"),),
        )

    report = base.run(_signature(forbidden=("forbidden_fam",)), evaluator)
    assert report.skipped_capsule_ids == ("capsule:forbidden_fam",)
    assert report.skipped_reasons == {"capsule:forbidden_fam": "method_family_not_admissible"}
