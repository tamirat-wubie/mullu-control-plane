"""Tests for candidate-specific adversarial capsule probes."""

from __future__ import annotations

import pytest

from gateway.candidate_composer import (
    AdversarialReviewResult,
    CandidateComposer,
    CandidateEvaluation,
    CandidatePipeline,
    MethodCapsule,
)
from gateway.candidate_ledger import CandidateLedger, CandidateScore
from gateway.method_registry import default_registry
from gateway.problem_signature import ProblemMetric, ProblemSignature
from gateway.solver_forge_capsule_probes import (
    CapsuleProbeReviewer,
    CompositeAdversarialReviewer,
    probe_high_risk_low_oversight,
    probe_injection_surface,
    probe_unguarded_external_state,
)


def _cap(
    cid: str,
    family: str,
    *,
    inputs: tuple[str, ...] = ("records",),
    assumptions: tuple[str, ...] = (),
    failure_modes: tuple[str, ...] = (),
    risk: str = "medium",
    explainability: str = "high",
) -> MethodCapsule:
    return MethodCapsule(
        capsule_id=cid,
        method_family=family,
        declared_inputs=inputs,
        declared_outputs=("out",),
        declared_assumptions=assumptions,
        declared_failure_modes=failure_modes,
        risk_ceiling=risk,
        explainability=explainability,
    )


def _pipeline(*caps: MethodCapsule) -> CandidatePipeline:
    return CandidatePipeline(
        pipeline_id="pipeline:" + "+".join(c.capsule_id for c in caps),
        method_families=tuple(c.method_family for c in caps),
        capsule_ids=tuple(c.capsule_id for c in caps),
    )


_SIG = ProblemSignature(
    problem_id="probe.test.v1",
    domain="d",
    goal="g",
    inputs=("x",),
    constraints=(),
    risk="medium",
    metrics=(ProblemMetric(metric_id="m", metric_kind="success", direction="maximize"),),
    required_evidence=(),
    budget_units=1.0,
    timeout_seconds=1.0,
)
_EVAL = CandidateEvaluation(outcome="passed", scores=(CandidateScore(metric_id="m", value=1.0),))


# ------------------------------- probe units ------------------------------- #


def test_injection_probe_flags_llm_without_mitigation():
    c = _cap("c:llm", "llm_planner")
    assert probe_injection_surface(c, (c,)) == "unmitigated_injection_surface:c:llm"


def test_injection_probe_clean_when_mitigation_declared():
    c = _cap("c:llm", "llm_planner", failure_modes=("prompt injection via untrusted input",))
    assert probe_injection_surface(c, (c,)) is None


def test_injection_probe_flags_text_input_even_for_non_llm():
    c = _cap("c:x", "rule_based", inputs=("document_text",))
    assert probe_injection_surface(c, (c,)) is not None


def test_external_state_probe_flags_then_clears():
    flagged = _cap("c:g", "graph_match", assumptions=("vendor graph exists",))
    assert probe_unguarded_external_state(flagged, (flagged,)) is not None
    clean = _cap(
        "c:g2", "graph_match", assumptions=("vendor graph exists",), failure_modes=("stale graph",)
    )
    assert probe_unguarded_external_state(clean, (clean,)) is None


def test_high_risk_low_oversight_probe_and_human_mitigation():
    risky = _cap("c:r", "optimization_solver", risk="high", explainability="low")
    assert probe_high_risk_low_oversight(risky, (risky,)) is not None
    human = _cap("c:h", "human_review_gate")
    assert probe_high_risk_low_oversight(risky, (risky, human)) is None


# ------------------------------- reviewer ---------------------------------- #


def test_reviewer_flags_and_is_deterministic():
    bad = _cap("c:llm", "llm_planner")
    reviewer = CapsuleProbeReviewer({bad.capsule_id: bad})
    r1 = reviewer(_SIG, _pipeline(bad), _EVAL, "s")
    r2 = reviewer(_SIG, _pipeline(bad), _EVAL, "s")
    assert r1.passed is False
    assert r1.findings == ("unmitigated_injection_surface:c:llm",)
    assert r1.findings == r2.findings and r1.evidence_refs == r2.evidence_refs
    assert r1.evidence_refs[0].startswith("capsule_probe:")


def test_reviewer_passes_clean_capsule():
    good = _cap("c:rb", "rule_based")
    reviewer = CapsuleProbeReviewer({good.capsule_id: good})
    result = reviewer(_SIG, _pipeline(good), _EVAL, "s")
    assert result.passed is True and result.findings == ()


def test_reviewer_is_candidate_specific():
    bad = _cap("c:llm", "llm_planner")
    good = _cap("c:rb", "rule_based")
    reviewer = CapsuleProbeReviewer({c.capsule_id: c for c in (bad, good)})
    assert reviewer(_SIG, _pipeline(bad), _EVAL, "s").findings  # one candidate flagged
    assert not reviewer(_SIG, _pipeline(good), _EVAL, "s").findings  # the other clean


def test_from_registry_flags_llm_capsules_but_not_benchmark_capsules():
    reviewer = CapsuleProbeReviewer.from_registry(default_registry())
    flagged_families = set()
    for capsule in default_registry().all_capsules():
        result = reviewer(_SIG, _pipeline(capsule), _EVAL, "s")
        if not result.passed:
            flagged_families.add(capsule.method_family)
    # LLM-backed families lack a declared injection failure mode -> flagged.
    assert {"llm_planner", "llm_reviewer", "multi_agent_debate"} <= flagged_families
    # The duplicate-invoice benchmark capsules are clean, so probes can be
    # attached to that benchmark without compromising its baseline.
    assert "rule_based" not in flagged_families
    assert "graph_match" not in flagged_families
    assert "statistical_anomaly" not in flagged_families


# ------------------------------- composite --------------------------------- #


def _always_pass(signature, pipeline, evaluation, seed):
    return AdversarialReviewResult(passed=True, findings=(), evidence_refs=("ok",))


def test_composite_unions_findings():
    bad = _cap("c:llm", "llm_planner")
    composite = CompositeAdversarialReviewer((CapsuleProbeReviewer({bad.capsule_id: bad}), _always_pass))
    result = composite(_SIG, _pipeline(bad), _EVAL, "s")
    assert result.passed is False
    assert "unmitigated_injection_surface:c:llm" in result.findings


def test_composite_passes_when_all_pass():
    good = _cap("c:rb", "rule_based")
    composite = CompositeAdversarialReviewer((CapsuleProbeReviewer({good.capsule_id: good}), _always_pass))
    assert composite(_SIG, _pipeline(good), _EVAL, "s").passed is True


def test_composite_requires_a_reviewer():
    with pytest.raises(ValueError, match="composite_reviewer_requires"):
        CompositeAdversarialReviewer(())


# --------------------------- composer integration -------------------------- #


def _integration_signature(baseline_family: str) -> ProblemSignature:
    return ProblemSignature(
        problem_id="probe.integ.v1",
        domain="d",
        goal="g",
        inputs=("x",),
        constraints=(),
        risk="medium",
        metrics=(ProblemMetric(metric_id="m", metric_kind="success", direction="maximize"),),
        required_evidence=(),
        budget_units=1.0,
        timeout_seconds=1.0,
        allowed_method_families=("rule_based", "llm_planner"),
        baseline_method_family=baseline_family,
    )


def _evaluator_favoring(winning_family: str):
    def evaluator(signature, pipeline, seed):
        value = 0.9 if pipeline.method_families == (winning_family,) else 0.5
        return CandidateEvaluation(outcome="passed", scores=(CandidateScore(metric_id="m", value=value),))

    return evaluator


def test_composer_excludes_candidate_that_fails_its_capsule_probe():
    # Baseline is clean; the candidate beats it on the metric but its capsule
    # has an unguarded injection surface -> excluded by the second gate.
    baseline = _cap("c:base", "rule_based")
    candidate = _cap("c:llm", "llm_planner")
    ledger = CandidateLedger()
    reviewer = CapsuleProbeReviewer({c.capsule_id: c for c in (baseline, candidate)})
    composer = CandidateComposer(ledger, capsules=(baseline, candidate), adversarial_reviewer=reviewer)

    report = composer.run(_integration_signature("rule_based"), _evaluator_favoring("llm_planner"))
    assert report.baseline_compromised is False
    assert report.winner_record_hashes == ()
    assert len(report.adversarial_review_failed_record_hashes) == 1


def test_composer_baseline_compromise_when_baseline_capsule_flagged():
    # If the BASELINE capsule itself fails review, no candidate may win.
    baseline = _cap("c:llm", "llm_planner")  # flagged
    candidate = _cap("c:rb", "rule_based")  # clean and would beat baseline
    ledger = CandidateLedger()
    reviewer = CapsuleProbeReviewer({c.capsule_id: c for c in (baseline, candidate)})
    composer = CandidateComposer(ledger, capsules=(baseline, candidate), adversarial_reviewer=reviewer)

    report = composer.run(_integration_signature("llm_planner"), _evaluator_favoring("rule_based"))
    assert report.baseline_compromised is True
    assert report.winner_record_hashes == ()
