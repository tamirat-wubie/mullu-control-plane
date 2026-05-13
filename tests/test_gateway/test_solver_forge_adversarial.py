"""Gateway solver-forge adversarial-review tests.

Purpose: verify the second-gate adversarial-review hook layered onto the
    candidate composer. A candidate must clear both the evaluator and the
    adversarial reviewer to be declared a winner. A baseline that fails
    adversarial review disqualifies the entire signature run — no candidate
    can claim to beat an untrusted baseline.
Invariants tested:
  - AdversarialReviewResult refuses inconsistent shapes
    (passed=True with findings, passed=False without findings).
  - Composer without a reviewer behaves exactly as before
    (no findings on records, same winner semantics).
  - Reviewer is only called on passing evaluations; failed evaluator
    outcomes skip the reviewer.
  - Findings are recorded onto the ledger record verbatim.
  - A passing-but-review-failing candidate appears in
    `adversarial_review_failed_record_hashes` and NOT in
    `winner_record_hashes`, even when its baseline_delta beats the baseline.
  - A baseline with findings flips `baseline_compromised=True` and zeroes
    out winner_record_hashes for the entire run.
  - `CandidateLedger.winners_for` excludes runs with findings.
  - The bridge's `is_winner` returns False for runs with findings;
    `build_provenance` raises `winner_failed_adversarial_review`.
"""

from __future__ import annotations

from typing import Any

import pytest

from gateway.candidate_composer import (
    AdversarialReviewResult,
    CandidateComposer,
    CandidateEvaluation,
    CandidatePipeline,
    MethodCapsule,
)
from gateway.candidate_ledger import (
    CandidateLedger,
    CandidateScore,
    InMemoryCandidateLedgerStore,
)
from gateway.problem_signature import (
    ProblemMetric,
    ProblemSignature,
)
from gateway.solver_forge_bridge import (
    build_provenance,
    forge_input_for_winner,
    is_winner,
)


def _signature() -> ProblemSignature:
    return ProblemSignature(
        problem_id="invoice_duplicate_detection.v1",
        domain="finance_ops",
        goal="detect duplicate invoice before payment",
        inputs=("invoice",),
        constraints=(),
        risk="low",
        metrics=(
            ProblemMetric(
                metric_id="precision",
                metric_kind="success",
                direction="maximize",
                threshold=0.5,
            ),
        ),
        required_evidence=(),
        baseline_method_family="rule_based",
    )


def _capsule(method_family: str, *, risk_ceiling: str = "low") -> MethodCapsule:
    return MethodCapsule(
        capsule_id=f"capsule:{method_family}",
        method_family=method_family,
        declared_inputs=("invoice",),
        declared_outputs=("duplicate_flag",),
        declared_assumptions=(),
        declared_failure_modes=(),
        risk_ceiling=risk_ceiling,
    )


def _evaluator(scores_by_family: dict[str, float], outcomes: dict[str, str] | None = None):
    def evaluator(signature, pipeline, seed):
        family = pipeline.method_families[0]
        outcome = (outcomes or {}).get(family, "passed")
        return CandidateEvaluation(
            outcome=outcome,
            scores=(
                CandidateScore(
                    metric_id="precision",
                    value=scores_by_family[family],
                    direction="maximize",
                ),
            ),
            failure_modes=("simulated",) if outcome != "passed" else (),
            cost_units=1.0,
            duration_seconds=0.01,
        )
    return evaluator


def _reviewer(findings_by_family: dict[str, tuple[str, ...]], record_calls: list | None = None):
    def reviewer(signature, pipeline, evaluation, seed):
        family = pipeline.method_families[0]
        findings = findings_by_family.get(family, ())
        if record_calls is not None:
            record_calls.append((family, evaluation.outcome))
        return AdversarialReviewResult(
            passed=not findings,
            findings=findings,
            evidence_refs=(f"redteam/{family}.json",) if findings else (),
        )
    return reviewer


def _make_ledger() -> CandidateLedger:
    return CandidateLedger(InMemoryCandidateLedgerStore())


# --- AdversarialReviewResult shape ------------------------------------------


def test_review_result_passed_cannot_have_findings() -> None:
    with pytest.raises(ValueError, match="adversarial_review_passed_cannot_have_findings"):
        AdversarialReviewResult(passed=True, findings=("leaked_secret",))


def test_review_result_failed_must_explain_with_findings() -> None:
    with pytest.raises(ValueError, match="adversarial_review_failed_must_explain_with_findings"):
        AdversarialReviewResult(passed=False, findings=())


def test_review_result_passed_with_no_findings_is_valid() -> None:
    result = AdversarialReviewResult(passed=True, findings=())
    assert result.passed is True
    assert result.findings == ()


# --- Composer without a reviewer: no behavioral change ----------------------


def test_composer_without_reviewer_records_no_findings() -> None:
    ledger = _make_ledger()
    composer = CandidateComposer(
        ledger,
        capsules=(_capsule("rule_based"), _capsule("graph_match")),
    )
    report = composer.run(_signature(), _evaluator({"rule_based": 0.5, "graph_match": 0.8}))
    assert report.adversarial_review_failed_record_hashes == ()
    assert report.baseline_compromised is False
    for run in ledger.for_signature(report.signature_hash):
        assert run.adversarial_review_findings == ()


# --- Reviewer is gated on passing evaluations only --------------------------


def test_reviewer_only_called_on_passing_evaluations() -> None:
    ledger = _make_ledger()
    calls: list = []
    composer = CandidateComposer(
        ledger,
        capsules=(_capsule("rule_based"), _capsule("graph_match"), _capsule("llm_only")),
        adversarial_reviewer=_reviewer({}, record_calls=calls),
    )
    composer.run(
        _signature(),
        _evaluator(
            {"rule_based": 0.5, "graph_match": 0.8, "llm_only": 0.9},
            outcomes={"llm_only": "failed"},
        ),
    )
    families_reviewed = {family for family, _ in calls}
    assert families_reviewed == {"rule_based", "graph_match"}
    assert "llm_only" not in families_reviewed


# --- Review-failing candidate is excluded from winners ----------------------


def test_review_failing_candidate_is_not_a_winner_even_if_it_beat_baseline() -> None:
    ledger = _make_ledger()
    composer = CandidateComposer(
        ledger,
        capsules=(_capsule("rule_based"), _capsule("graph_match"), _capsule("llm_only")),
        adversarial_reviewer=_reviewer({"llm_only": ("prompt_injection_succeeded",)}),
    )
    report = composer.run(
        _signature(),
        _evaluator({"rule_based": 0.5, "graph_match": 0.8, "llm_only": 0.95}),
    )
    # llm_only beat the baseline on raw precision (0.95 vs 0.5) but failed
    # adversarial review, so it must not be a winner.
    winner_families = {
        next(
            r.method_families[0]
            for r in ledger.for_signature(report.signature_hash)
            if r.record_hash == h
        )
        for h in report.winner_record_hashes
    }
    assert "llm_only" not in winner_families
    assert "graph_match" in winner_families

    # The review-failing run is still recorded — first-class evidence.
    review_failed = {
        next(
            r.method_families[0]
            for r in ledger.for_signature(report.signature_hash)
            if r.record_hash == h
        )
        for h in report.adversarial_review_failed_record_hashes
    }
    assert review_failed == {"llm_only"}

    # Findings are recorded on the ledger record.
    for run in ledger.for_signature(report.signature_hash):
        if run.method_families == ("llm_only",):
            assert run.adversarial_review_findings == ("prompt_injection_succeeded",)
            assert run.adversarial_review_evidence_refs == ("redteam/llm_only.json",)


# --- Compromised baseline disqualifies the whole run ------------------------


def test_baseline_failing_review_disqualifies_all_winners() -> None:
    ledger = _make_ledger()
    composer = CandidateComposer(
        ledger,
        capsules=(_capsule("rule_based"), _capsule("graph_match"), _capsule("constraint_solver")),
        adversarial_reviewer=_reviewer({"rule_based": ("baseline_audit_tamper",)}),
    )
    report = composer.run(
        _signature(),
        _evaluator(
            {"rule_based": 0.5, "graph_match": 0.8, "constraint_solver": 0.85}
        ),
    )
    assert report.baseline_compromised is True
    assert report.baseline_findings == ("baseline_audit_tamper",)
    assert report.winner_record_hashes == ()
    assert "untrusted baseline" in report.notes


# --- ledger.winners_for excludes findings-bearing runs ----------------------


def test_ledger_winners_for_excludes_findings_bearing_runs() -> None:
    ledger = _make_ledger()
    composer = CandidateComposer(
        ledger,
        capsules=(_capsule("rule_based"), _capsule("graph_match")),
        adversarial_reviewer=_reviewer({"graph_match": ("policy_bypass",)}),
    )
    report = composer.run(
        _signature(),
        _evaluator({"rule_based": 0.5, "graph_match": 0.9}),
    )
    winners = ledger.winners_for(report.signature_hash, primary_metric_id="precision")
    assert winners == ()


# --- Bridge respects adversarial findings -----------------------------------


def test_is_winner_returns_false_for_run_with_findings() -> None:
    ledger = _make_ledger()
    signature = _signature()
    composer = CandidateComposer(
        ledger,
        capsules=(_capsule("rule_based"), _capsule("graph_match")),
        adversarial_reviewer=_reviewer({"graph_match": ("policy_bypass",)}),
    )
    composer.run(signature, _evaluator({"rule_based": 0.5, "graph_match": 0.9}))
    graph_run = next(
        run
        for run in ledger.for_signature(signature.signature_hash)
        if run.method_families == ("graph_match",)
    )
    assert is_winner(graph_run, signature) is False


def test_build_provenance_refuses_run_with_findings() -> None:
    ledger = _make_ledger()
    signature = _signature()
    composer = CandidateComposer(
        ledger,
        capsules=(_capsule("rule_based"), _capsule("graph_match")),
        adversarial_reviewer=_reviewer({"graph_match": ("policy_bypass",)}),
    )
    composer.run(signature, _evaluator({"rule_based": 0.5, "graph_match": 0.9}))
    graph_run = next(
        run
        for run in ledger.for_signature(signature.signature_hash)
        if run.method_families == ("graph_match",)
    )
    with pytest.raises(ValueError, match="winner_failed_adversarial_review:policy_bypass"):
        build_provenance(graph_run, signature)


def test_forge_input_for_winner_refuses_run_with_findings() -> None:
    ledger = _make_ledger()
    signature = _signature()
    composer = CandidateComposer(
        ledger,
        capsules=(_capsule("rule_based"), _capsule("graph_match")),
        adversarial_reviewer=_reviewer({"graph_match": ("policy_bypass",)}),
    )
    composer.run(signature, _evaluator({"rule_based": 0.5, "graph_match": 0.9}))
    graph_run = next(
        run
        for run in ledger.for_signature(signature.signature_hash)
        if run.method_families == ("graph_match",)
    )
    with pytest.raises(ValueError, match="winner_failed_adversarial_review"):
        forge_input_for_winner(
            winner=graph_run,
            signature=signature,
            capability_id="finance.duplicate_invoice_guard.v1",
            version="0.1.0",
            api_docs_ref="docs/api.md",
            input_schema_ref="schemas/in.json",
            output_schema_ref="schemas/out.json",
            owner_team="finance-platform",
        )


# --- End-to-end loop with both gates ----------------------------------------


def test_end_to_end_winner_clears_both_gates() -> None:
    ledger = _make_ledger()
    signature = _signature()
    composer = CandidateComposer(
        ledger,
        capsules=(
            _capsule("rule_based"),
            _capsule("graph_match"),
            _capsule("llm_only"),
            _capsule("constraint_solver"),
        ),
        adversarial_reviewer=_reviewer(
            {
                "llm_only": ("prompt_injection_succeeded",),
                # graph_match and constraint_solver pass review
            }
        ),
    )
    report = composer.run(
        signature,
        _evaluator(
            {
                "rule_based": 0.5,
                "graph_match": 0.85,
                "llm_only": 0.99,
                "constraint_solver": 0.7,
            }
        ),
    )
    winners = ledger.winners_for(report.signature_hash, primary_metric_id="precision")
    winner_families = {w.method_families[0] for w in winners}
    # llm_only excluded by adversarial gate; rule_based is baseline; all other
    # passing-and-beating candidates make it through.
    assert winner_families == {"graph_match", "constraint_solver"}

    # Pick the strongest winner and round-trip through the bridge.
    best = max(winners, key=lambda w: w.baseline_delta["precision"])
    forge_input = forge_input_for_winner(
        winner=best,
        signature=signature,
        capability_id=f"finance.{best.method_families[0]}_guard.v1",
        version="0.1.0",
        api_docs_ref="docs/api.md",
        input_schema_ref="schemas/in.json",
        output_schema_ref="schemas/out.json",
        owner_team="finance-platform",
    )
    assert forge_input.metadata["solver_forge"]["winner_record_hash"] == best.record_hash
