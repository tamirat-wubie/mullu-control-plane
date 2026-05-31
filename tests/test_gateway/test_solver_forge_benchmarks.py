"""Tests for the solver-forge reference benchmark (duplicate invoice detection)."""

from __future__ import annotations

from gateway.candidate_composer import CandidatePipeline
from gateway.problem_signature import ProblemSignature
from gateway.solver_forge_benchmarks import (
    DUPLICATE_INVOICE_SIGNATURE,
    INVOICE_FIXTURE,
    BENCHMARKS,
    detect_exact,
    detect_graph,
    detect_overflag,
    get_benchmark,
    reference_evaluator,
    run_benchmark,
    _true_pairs,
)
from gateway.solver_forge_bridge import forge_input_for_winner, is_winner


def _score_of(run, metric_id: str) -> float:
    return next(s.value for s in run.scores if s.metric_id == metric_id)


def _pipeline_for(capsule_id: str) -> CandidatePipeline:
    return CandidatePipeline(
        pipeline_id=f"pipeline:{capsule_id}",
        method_families=("x",),
        capsule_ids=(capsule_id,),
    )


# --------------------------- detector ground truth ------------------------- #


def test_detect_exact_is_high_precision_low_recall():
    predicted = detect_exact(INVOICE_FIXTURE)
    truth = _true_pairs()
    assert predicted <= truth  # no false positives
    assert predicted == {frozenset(("001", "002")), frozenset(("004", "011")), frozenset(("009", "010"))}
    assert len(predicted) == 3 and len(truth) == 6  # recall 0.5


def test_detect_graph_finds_all_true_pairs_without_false_positives():
    predicted = detect_graph(INVOICE_FIXTURE)
    assert predicted == _true_pairs()  # precision 1.0 AND recall 1.0


def test_detect_overflag_is_high_recall_low_precision():
    predicted = detect_overflag(INVOICE_FIXTURE)
    truth = _true_pairs()
    assert truth <= predicted  # recall 1.0
    assert len(predicted) == 18  # 12 false positives
    assert len(predicted & truth) == 6


# ------------------------------ evaluator ---------------------------------- #


def test_evaluator_is_deterministic():
    pipe = _pipeline_for("capsule:graph_match.vendor_amount_proximity.v1")
    a = reference_evaluator(DUPLICATE_INVOICE_SIGNATURE, pipe, "seed")
    b = reference_evaluator(DUPLICATE_INVOICE_SIGNATURE, pipe, "seed")
    assert a.scores == b.scores and a.outcome == b.outcome


def test_evaluator_skips_unknown_capsule_instead_of_fabricating():
    ev = reference_evaluator(DUPLICATE_INVOICE_SIGNATURE, _pipeline_for("capsule:unknown"), "s")
    assert ev.outcome == "skipped"
    assert ev.scores == ()


def test_benchmark_signature_is_valid_and_f1_is_primary():
    sig = DUPLICATE_INVOICE_SIGNATURE
    assert isinstance(sig, ProblemSignature)
    assert sig.success_metrics()[0].metric_id == "f1_score"  # primary metric


# --------------------------- end-to-end loop ------------------------------- #


def test_run_benchmark_selects_graph_match_as_sole_winner():
    report, ledger = run_benchmark("invoice_duplicate_detection.v1")
    runs = {r.candidate_pipeline_id: r for r in ledger.for_signature(report.signature_hash)}

    # Baseline established, nothing compromised, every detector ran (no negatives).
    assert report.baseline_record_hash
    assert report.baseline_compromised is False
    assert report.negative_record_hashes == ()

    # Exactly one winner, and it is the graph-match pipeline.
    assert len(report.winner_record_hashes) == 1
    winner = next(r for r in runs.values() if r.record_hash == report.winner_record_hashes[0])
    assert winner.method_families == ("graph_match",)
    assert winner.baseline_delta["f1_score"] > 0


def test_overflag_trap_passes_but_is_refused_as_winner():
    """The recall-only trap runs successfully and even has higher recall than
    the baseline, yet must not win because the primary metric is F1."""
    report, ledger = run_benchmark("invoice_duplicate_detection.v1")
    runs = {r.method_families: r for r in ledger.for_signature(report.signature_hash)}

    baseline = runs[("rule_based",)]
    overflag = runs[("statistical_anomaly",)]
    graph = runs[("graph_match",)]

    # Measured, not declared.
    assert _score_of(baseline, "precision") == 1.0
    assert _score_of(baseline, "recall") == 0.5
    assert _score_of(graph, "f1_score") == 1.0
    assert _score_of(overflag, "recall") == 1.0  # beats baseline on recall...
    assert _score_of(overflag, "precision") < _score_of(baseline, "precision")
    assert _score_of(overflag, "f1_score") < _score_of(baseline, "f1_score")  # ...but loses on F1

    # The overflag candidate passed and was recorded, but is NOT a winner.
    assert overflag.outcome == "passed"
    assert overflag.record_hash in report.candidate_record_hashes
    assert overflag.record_hash not in report.winner_record_hashes
    assert overflag.baseline_delta["f1_score"] < 0


def test_winner_crosses_bridge_and_overflag_does_not():
    report, ledger = run_benchmark("invoice_duplicate_detection.v1")
    runs = {r.method_families: r for r in ledger.for_signature(report.signature_hash)}
    sig = get_benchmark("invoice_duplicate_detection.v1").signature

    graph = runs[("graph_match",)]
    overflag = runs[("statistical_anomaly",)]

    assert is_winner(graph, sig) is True
    assert is_winner(overflag, sig) is False

    forge_input = forge_input_for_winner(
        winner=graph,
        signature=sig,
        capability_id="finance.duplicate_invoice_guard.v1",
        version="0.1.0",
        api_docs_ref="docs/api/duplicate_invoice_guard.md",
        input_schema_ref="schemas/dig.input.schema.json",
        output_schema_ref="schemas/dig.output.schema.json",
        owner_team="finance-platform",
    )
    # Domain/risk inherited from the signature (no laundering), provenance stamped.
    assert forge_input.domain == sig.domain
    assert forge_input.risk == "medium"
    assert "solver_forge" in forge_input.metadata
    assert forge_input.metadata["solver_forge"]["primary_metric_id"] == "f1_score"


def test_winners_for_ledger_matches_report():
    report, ledger = run_benchmark("invoice_duplicate_detection.v1")
    winners = ledger.winners_for(report.signature_hash, primary_metric_id="f1_score")
    assert {w.record_hash for w in winners} == set(report.winner_record_hashes)


def test_catalog_exposes_benchmark():
    assert "invoice_duplicate_detection.v1" in BENCHMARKS
    assert get_benchmark("invoice_duplicate_detection.v1").signature is DUPLICATE_INVOICE_SIGNATURE
